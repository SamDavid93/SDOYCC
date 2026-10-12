"""Five real AppContainer cores plus ordinary Hub reads; disposable DB/accounts only."""
import asyncio
import gc
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx
import psutil
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from browser_smoke import ROOT, free_port, wait_ready
from duel_worker_browser_checks import seed_worker_database


def seed_pairs(path):
    from app.core.auth import create_session
    from app.core.passwords import hash_password
    from app.db.models import User, PlayerDeck, VariantInventory, InventoryTransaction
    from app.modules.inventory import change_stock, variant
    host, guest, host_deck, guest_deck, _ = seed_worker_database(path)
    pairs = [((host, host_deck), (guest, guest_deck))]
    engine = create_engine('sqlite:///' + str(path))
    with Session(engine) as db:
        source = db.get(PlayerDeck, guest_deck)
        owner = db.get(User, db.get(PlayerDeck, host_deck).user_id)
        owner.role = 'super_admin'; owner.password_hash = hash_password('Parallel-duel-test-password')
        for number in range(10):
            user = User(username=f'isolated-load-{number}', display_name=f'Load {number}',
                twitch_id=str(910000 + number), password_hash='isolated-fixture-only', credits=0)
            db.add(user); db.flush()
            for entry in json.loads(source.entries_json):
                change_stock(db, user.id, variant(db, entry['card_id'], 'common'), 3,
                    'isolated_test', f'load:{number}:{entry["card_id"]}', bound=True)
            deck = PlayerDeck(id=str(uuid4()), user_id=user.id, name=f'Private load deck {number}',
                profile_id=source.profile_id, entries_json=source.entries_json)
            db.add(deck); token = create_session(db, user)
            if number % 2 == 0: pair = [(token, deck.id)]
            else: pairs.append(tuple([*pair, (token, deck.id)]))
        db.commit()
        baseline = (db.scalar(select(func.sum(VariantInventory.quantity))), db.scalar(select(func.count(InventoryTransaction.id))))
    engine.dispose()
    return pairs, baseline


async def exercise(url, pairs, supervisor):
    latencies = []
    async with httpx.AsyncClient(base_url=url + '/api', timeout=40) as client:
        async def post(path, body, token, expected=200):
            response = await client.post(path, json=body, headers={'Authorization': 'Bearer ' + token, 'Idempotency-Key': str(uuid4())})
            assert response.status_code == expected, (path, response.status_code, response.text)
            return response.json()
        rooms = []
        for pair in pairs:
            host, guest = pair
            room = await post('/duel-zone/lobbies', {'deck_id': host[1]}, host[0])
            room = await post('/duel-zone/join', {'code': room['code']}, guest[0])
            base = '/duel-zone/lobbies/' + room['id']
            room = await post(base + '/guest', {'version': room['version'], 'accept': True}, host[0])
            room = await post(base + '/deck', {'version': room['version'], 'deck_id': guest[1]}, guest[0])
            for token, _ in pair: room = await post(base + '/confirm-deck', {'version': room['version'], 'confirmed': True}, token)
            for token, _ in pair: room = await post('/duel-zone/worker/consent', {'lobby_id': room['id'], 'version': room['version'], 'consent': True}, token)
            rooms.append(room)
        complete = asyncio.Event()
        async def hub_reads():
            while not complete.is_set():
                for endpoint in ('/health', '/users/me', '/inventory/me', '/packs'):
                    started = time.perf_counter()
                    response = await client.get(endpoint, headers={'Authorization': 'Bearer ' + pairs[0][0][0]})
                    response.raise_for_status(); latencies.append(time.perf_counter() - started)
                await asyncio.sleep(0.05)
        reader = asyncio.create_task(hub_reads())
        try:
            started = time.perf_counter()
            runs = await asyncio.gather(*(post('/duel-zone/worker/start',
                {'lobby_id': room['id'], 'version': room['version']}, pair[0][0]) for room, pair in zip(rooms[:5], pairs[:5])))
            startup_seconds = time.perf_counter() - started
            assert all(run['state'] == 'running' for run in runs)
            cores = [process for process in psutil.Process(supervisor).children(recursive=True)
                if '--hub-run' in process.cmdline()]
            assert len(cores) == 5 and len({run['id'] for run in runs}) == 5
            core_rss = sum(process.memory_info().rss for process in cores)
            cpu_before = sum(sum(process.cpu_times()[:2]) for process in cores)
            await post('/duel-zone/worker/start', {'lobby_id': rooms[5]['id'], 'version': rooms[5]['version']}, pairs[5][0][0], 429)
            async def answer(run, pair):
                prompt = run['board']['prompt']; assert prompt
                result = await post(f'/duel-zone/worker/runs/{run["id"]}/answer', {'prompt': prompt['id'], 'selected': [0]}, pair[0][0])
                assert result['state'] == 'running' and result['board']['revision'] > run['board']['revision']
            await asyncio.gather(*(answer(run, pair) for run, pair in zip(runs, pairs)))
            cpu_seconds = sum(sum(process.cpu_times()[:2]) for process in cores) - cpu_before
            # Administrative maintenance stops admission, never existing matches.
            policy = await post('/admin/duels/policy', {'accepting_new': False, 'version': 1,
                'password': 'Parallel-duel-test-password', 'reason': 'Isolierter Parallelbetrieb-Wartungstest'}, pairs[0][0][0])
            assert not policy['accepting_new'] and policy['active_matches'] == 5
            await post('/duel-zone/worker/start', {'lobby_id': rooms[5]['id'], 'version': rooms[5]['version']}, pairs[5][0][0], 503)
            for run, pair in zip(runs, pairs):
                result = await post(f'/duel-zone/worker/runs/{run["id"]}/surrender', {}, pair[0][0])
                assert result['state'] == 'finished' and result['winner_seat'] == 1
            await post('/admin/duels/policy', {'accepting_new': True, 'version': policy['version'],
                'password': 'Parallel-duel-test-password', 'reason': 'Isolierter Wartungstest abgeschlossen'}, pairs[0][0][0])
            last = await post('/duel-zone/worker/start', {'lobby_id': rooms[5]['id'], 'version': rooms[5]['version']}, pairs[5][0][0])
            assert last['state'] == 'running'
            await post(f'/duel-zone/worker/runs/{last["id"]}/surrender', {}, pairs[5][0][0])
        finally:
            complete.set(); await reader
    assert latencies and max(latencies) < 5, ('Hub response exceeded 5 seconds', latencies)
    return {'parallel_native_matches': 5, 'accounts_playing_simultaneously': 10,
        'sixth_match_rejected': True, 'maintenance_preserves_matches': True, 'slot_reusable': True,
        'native_startup_seconds': round(startup_seconds, 3), 'cores_rss_mib': round(core_rss / 1024**2, 2),
        'core_cpu_seconds_for_five_responses': round(cpu_seconds, 3), 'hub_requests': len(latencies),
        'hub_median_ms': round(statistics.median(latencies) * 1000, 2), 'hub_max_ms': round(max(latencies) * 1000, 2)}


def run():
    from app.db.models import VariantInventory, InventoryTransaction, DuelWorkerRun
    artifacts = ROOT / 'artifacts/duel-load'; artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary, (artifacts / 'servers.log').open('w', encoding='utf8') as log:
        path = Path(temporary) / 'load.db'; port = free_port(); url = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(path), 'APP_ENV': 'development',
            'ENABLE_DEMO_AUTH': 'true', 'ENABLE_DUEL_WORKER_LAB': 'true', 'DUEL_MAX_ACTIVE_MATCHES': '5',
            'CORS_ORIGINS': 'http://127.0.0.1:5173'}
        backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--port', str(port)],
            cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            wait_ready(url + '/api/health', backend)
            pairs, baseline = seed_pairs(path)
            metrics = asyncio.run(exercise(url, pairs, backend.pid))
            engine = create_engine('sqlite:///' + str(path))
            with Session(engine) as db:
                assert db.scalar(select(func.sum(VariantInventory.reserved))) == 0
                assert baseline == (db.scalar(select(func.sum(VariantInventory.quantity))), db.scalar(select(func.count(InventoryTransaction.id))))
                assert db.scalar(select(func.count(DuelWorkerRun.id)).where(DuelWorkerRun.state.in_(('starting', 'running')))) == 0
            engine.dispose()
            report = {'status': 'passed', 'production_modified': False, 'inventory_and_journal_unchanged': True, **metrics}
            (artifacts / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            print(json.dumps(report))
        finally:
            if backend.poll() is None: backend.terminate()
            try: backend.wait(timeout=15)
            except subprocess.TimeoutExpired: backend.kill(); backend.wait(timeout=10)
            gc.collect()


if __name__ == '__main__': run()
