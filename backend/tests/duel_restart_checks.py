"""Kill/restart an OWN disposable API and native worker; never production."""
import json
import gc
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

import httpx
import psutil
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from browser_smoke import ROOT, free_port, wait_ready
from duel_worker_browser_checks import seed_worker_database


def run():
    artifacts = ROOT / 'artifacts/duel-restart'; artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary, (artifacts / 'servers.log').open('w', encoding='utf8') as log:
        database_file = Path(temporary) / 'restart.db'
        port = free_port(); url = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(database_file), 'APP_ENV': 'development',
            'ENABLE_DEMO_AUTH': 'true', 'ENABLE_DUEL_WORKER_LAB': 'true', 'CORS_ORIGINS': 'http://127.0.0.1:5173'}
        def launch():
            return subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--port', str(port)],
                cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        backend = launch()
        try:
            wait_ready(url + '/api/health', backend)
            host, guest, host_deck, guest_deck, baseline = seed_worker_database(database_file)
            with httpx.Client(base_url=url, timeout=30) as client:
                def post(path, body, token):
                    response = client.post('/api' + path, json=body, headers={'Authorization': 'Bearer ' + token, 'Idempotency-Key': str(uuid4())})
                    response.raise_for_status(); return response.json()
                room = post('/duel-zone/lobbies', {'deck_id': host_deck}, host)
                room = post('/duel-zone/join', {'code': room['code']}, guest)
                base = '/duel-zone/lobbies/' + room['id']
                room = post(base + '/guest', {'version': room['version'], 'accept': True}, host)
                room = post(base + '/deck', {'version': room['version'], 'deck_id': guest_deck}, guest)
                for token in (host, guest): room = post(base + '/confirm-deck', {'version': room['version'], 'confirmed': True}, token)
                for token in (host, guest): room = post('/duel-zone/worker/consent', {'lobby_id': room['id'], 'version': room['version'], 'consent': True}, token)
                game = post('/duel-zone/worker/start', {'lobby_id': room['id'], 'version': room['version']}, host)
                assert game['state'] == 'running'
                children = [process for process in psutil.Process(backend.pid).children(recursive=True)
                    if '--hub-run' in process.cmdline() and game['id'] in process.cmdline()]
                assert len(children) == 1
                # The only terminated supervisor is the Popen object created above.
                backend.kill(); backend.wait(timeout=10)
                children[0].wait(timeout=10)  # Kernel Job kills the native child.
                env['ENABLE_DEMO_AUTH'] = 'false'
                backend = launch(); wait_ready(url + '/api/health', backend)
                response = client.get('/api/duel-zone/worker/runs/' + game['id'], headers={'Authorization': 'Bearer ' + host})
                response.raise_for_status(); result = response.json()
                assert result['state'] == 'aborted' and result['reason'] == 'server_restart' and result['winner_seat'] is None
            from app.db.models import VariantInventory, InventoryTransaction, DuelWorkerRun
            engine = create_engine('sqlite:///' + str(database_file))
            with Session(engine) as db:
                assert db.scalar(select(func.sum(VariantInventory.reserved))) == 0
                assert baseline == (db.scalar(select(func.sum(VariantInventory.quantity))), db.scalar(select(func.count(InventoryTransaction.id))))
                assert db.get(DuelWorkerRun, game['id']).state == 'aborted'
            engine.dispose()
            report = {'status': 'passed', 'native_core': True, 'production_modified': False,
                'tests': ['committed-process-identity', 'native-process-started', 'kernel-child-stop-on-supervisor-crash',
                    'new-instance-recovers-orphan', 'neutral-terminal-receipt', 'all-reservations-released', 'inventory-and-journal-unchanged']}
            (artifacts / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            print(json.dumps(report))
        finally:
            if backend.poll() is None: backend.terminate()
            try: backend.wait(timeout=15)
            except subprocess.TimeoutExpired: backend.kill(); backend.wait(timeout=10)
            gc.collect()  # Release cyclic SQLite statement/ORM references on Windows.


if __name__ == '__main__': run()
