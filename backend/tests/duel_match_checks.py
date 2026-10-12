"""Actual native multi-game match, sideboarding UI and stock checks in a disposable Hub."""
import gc
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

import httpx
from playwright.sync_api import sync_playwright, expect
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from browser_smoke import ROOT, free_port, wait_ready
from duel_worker_browser_checks import seed_worker_database


def decide(prompt):
    choices = prompt['choices']
    if prompt.get('select'):
        return list(range(prompt.get('minimum', 0)))
    if prompt['title'] == 'Aktion w\u00e4hlen':
        for label in ('Beschw', 'Angreifen', 'Kampfphase', 'Zug beenden', 'Hauptphase 2'):
            candidates = [i for i, choice in enumerate(choices) if choice['label'].startswith(label)]
            if candidates: return [max(candidates, key=lambda i: (choices[i].get('card') or {}).get('atk', 0))]
    no_chain = [i for i, choice in enumerate(choices) if choice['label'] == 'Nicht anketten']
    return [no_chain[0] if no_chain else 0]


def run():
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{ui_port}'
    artifacts = ROOT / 'artifacts/duel-match'; artifacts.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    processes = []
    with tempfile.TemporaryDirectory() as tmp, (artifacts / 'servers.log').open('w', encoding='utf8') as log:
        database = Path(tmp) / 'match.db'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(database), 'APP_ENV': 'development', 'ENABLE_DEMO_AUTH': 'true',
            'ENABLE_DUEL_WORKER_LAB': 'true', 'CORS_ORIGINS': ui_url, 'VITE_API_BASE_URL': api_url + '/api', 'VITE_BASE_PATH': '/'}
        try:
            backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--port', str(api_port)], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags); processes.append(backend)
            node = os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe' if os.name == 'nt' else 'node')
            frontend = subprocess.Popen([node, str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(ui_port), '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, creationflags=flags); processes.append(frontend)
            wait_ready(api_url + '/api/health', backend); wait_ready(ui_url, frontend)
            host, guest, host_deck, guest_deck, baseline = seed_worker_database(database)
            from app.db.models import PlayerDeck
            fixture_engine = create_engine('sqlite:///' + str(database))
            with Session(fixture_engine) as db:
                for deck_id in (host_deck, guest_deck):
                    deck = db.get(PlayerDeck, deck_id); entries = json.loads(deck.entries_json)
                    entries.append({'card_id': entries[-1]['card_id'], 'section': 'side', 'quantity': 2})
                    deck.entries_json = json.dumps(entries); deck.version += 1
                db.commit()
            fixture_engine.dispose()
            tokens = [host, guest]
            with httpx.Client(base_url=api_url, timeout=20) as client, sync_playwright() as pw:
                def post(path, body, seat):
                    response = client.post('/api' + path, json=body, headers={'Authorization': 'Bearer ' + tokens[seat], 'Idempotency-Key': str(uuid4())})
                    response.raise_for_status(); return response.json()
                room = post('/duel-zone/lobbies', {'deck_id': host_deck, 'mode': 'match'}, 0)
                room = post('/duel-zone/join', {'code': room['code']}, 1)
                base = '/duel-zone/lobbies/' + room['id']
                room = post(base + '/guest', {'version': room['version'], 'accept': True}, 0)
                room = post(base + '/deck', {'version': room['version'], 'deck_id': guest_deck}, 1)
                for seat in (0, 1): room = post(base + '/confirm-deck', {'version': room['version'], 'confirmed': True}, seat)
                for seat in (0, 1): room = post('/duel-zone/worker/consent', {'lobby_id': room['id'], 'version': room['version'], 'consent': True}, seat)
                game = post('/duel-zone/worker/start', {'lobby_id': room['id'], 'version': room['version']}, 0)
                run_id = game['id']; path = '/duel-zone/worker/runs/' + run_id
                def views():
                    results = []
                    for token in tokens:
                        response = client.get('/api' + path, headers={'Authorization': 'Bearer ' + token}); response.raise_for_status(); results.append(response.json())
                    return results
                browser = pw.chromium.launch(channel='msedge', headless=True)
                pages, errors = [], []
                for token in tokens:
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    context.add_init_script('sessionStorage.setItem("hub-session", ' + json.dumps(token) + ')')
                    page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                    page.goto(ui_url + '/#/duel-zone'); pages.append(page)
                sideboarding = 0; responses = 0
                for step in range(1200):
                    state = views()
                    if state[0]['state'] == 'finished': break
                    if state[0]['state'] != 'running': raise AssertionError('Native match aborted: ' + str(state[0]['reason']))
                    if state[0]['match']['phase'] == 'sideboarding':
                        sideboarding += 1
                        for page in pages: expect(page.get_by_role('heading', name='Sideboarding nach Spiel ' + str(state[0]['match']['game']), exact=True)).to_be_visible(timeout=10000)
                        chooser = state[0]['match']['chooser']
                        # Swap two DIFFERENT normal-monster identities through the real UI.
                        panel = pages[chooser].locator('.duel-sideboard')
                        panel.locator('details').nth(0).locator('select').first.select_option('side')
                        panel.locator('details').nth(2).locator('select').first.select_option('main')
                        pages[chooser].get_by_label('Wer beginnt das n\u00e4chste Spiel?').select_option(str(chooser))
                        pages[chooser].get_by_role('button', name='Side-Deck best\u00e4tigen und bereit', exact=True).click()
                        expect(pages[1-chooser].get_by_text('Gegner: bereit', exact=False)).to_be_visible(timeout=10000)
                        pages[1-chooser].get_by_role('button', name='Side-Deck best\u00e4tigen und bereit', exact=True).click()
                        expect(pages[0].get_by_role('heading', name='Sideboarding nach Spiel ' + str(state[0]['match']['game']), exact=True)).not_to_be_visible(timeout=10000)
                        continue
                    actor = next((seat for seat in (0, 1) if state[seat]['board']['prompt']), None)
                    if actor is None: raise AssertionError('Native match has no decision')
                    prompt = state[actor]['board']['prompt']
                    post(path + '/answer', {'prompt': prompt['id'], 'selected': decide(prompt)}, actor); responses += 1
                else: raise AssertionError('Native match exceeded bounded test actions')
                final = views()[0]
                assert max(final['match']['score']) == 2 and sideboarding >= 1
                winner = final['winner_seat']
                expect(pages[winner].get_by_role('heading', name='Du hast gewonnen', exact=True)).to_be_visible(timeout=10000)
                assert not errors, errors
                browser.close()
            from app.db.models import VariantInventory, InventoryTransaction, DuelMatchProgress
            engine = create_engine('sqlite:///' + str(database))
            with Session(engine) as db:
                assert db.scalar(select(func.sum(VariantInventory.reserved))) == 0
                assert baseline == (db.scalar(select(func.sum(VariantInventory.quantity))), db.scalar(select(func.count(InventoryTransaction.id))))
                progress = json.loads(db.get(DuelMatchProgress, run_id).progress_json)
                assert max(progress['score']) == 2 and progress['phase'] == 'finished'
                assert any(progress['decks'][seat] != progress['original'][seat] for seat in (0, 1))
            engine.dispose()
            report = {'status': 'passed', 'native_core': True, 'production_modified': False, 'responses': responses,
                'games': len(progress['results']), 'score': progress['score'], 'sideboarding_rounds': sideboarding, 'console_errors': errors}
            (artifacts / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8'); print(json.dumps(report))
        finally:
            for process in processes:
                if process.poll() is None: process.terminate()
            for process in processes:
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
            gc.collect()


if __name__ == '__main__': run()
