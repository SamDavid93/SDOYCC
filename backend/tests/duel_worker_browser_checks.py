"""Native worker + real Hub sessions + two browsers, on a disposable database only."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

import httpx
from playwright.sync_api import sync_playwright, expect

from browser_smoke import ROOT, free_port, wait_ready
from deck_browser_checks import seed_fixture


def seed_worker_database(path):
    profile_id, _, guest_token, guest_deck = seed_fixture(path)
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.core.auth import create_session
    from app.db.models import DuelRuleProfile, PlayerDeck, User, VariantInventory, InventoryTransaction
    from sqlalchemy import func
    engine = create_engine('sqlite:///' + str(path))
    with Session(engine) as db:
        # Synthetic approvals on this temporary test database ONLY. Never production.
        profile = db.get(DuelRuleProfile, profile_id)
        profile.engine_approved = profile.region_approved = True
        host = db.scalar(select(User).where(User.username == 'jaden-demo'))
        host_token = create_session(db, host)
        source = db.get(PlayerDeck, guest_deck)
        host_deck = str(uuid4())
        db.add(PlayerDeck(id=host_deck, user_id=host.id, name='Privates Worker-Testdeck', profile_id=profile.id, entries_json=source.entries_json))
        db.commit()
        baseline = (db.scalar(select(func.sum(VariantInventory.quantity))), db.scalar(select(func.count(InventoryTransaction.id))))
    engine.dispose()
    return host_token, guest_token, host_deck, guest_deck, baseline


def run(manual=False):
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{ui_port}'
    node = os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe' if os.name == 'nt' else 'node')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    artifacts = ROOT / 'artifacts/duel-worker'; artifacts.mkdir(exist_ok=True, parents=True)
    run_id = host_token = None
    with tempfile.TemporaryDirectory() as temporary:
        database_file = Path(temporary) / 'worker.db'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(database_file), 'APP_ENV': 'development',
            'ENABLE_DEMO_AUTH': 'true', 'ENABLE_DUEL_WORKER_LAB': 'true', 'CORS_ORIGINS': ui_url,
            'VITE_API_BASE_URL': api_url + '/api', 'VITE_BASE_PATH': '/', 'FRONTEND_URL': ui_url + '/'}
        with (artifacts / 'servers.log').open('w', encoding='utf8') as log:
            backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--port', str(api_port)], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            frontend = subprocess.Popen([node, str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(ui_port), '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, creationflags=flags)
            try:
                # Startup verifies and stages more than 22,000 native engine files.
                # Allow a cold filesystem scan; gameplay assertions keep their own limits.
                wait_ready(api_url + '/api/health', backend, timeout=360); wait_ready(ui_url, frontend)
                host_token, guest_token, host_deck, guest_deck, baseline = seed_worker_database(database_file)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=not manual)
                    contexts = [browser.new_context(viewport={'width': 1440, 'height': 1000}) for _ in range(2)]
                    pages = []; errors = []
                    for context, token in zip(contexts, (host_token, guest_token)):
                        context.add_init_script('sessionStorage.setItem("hub-session", ' + json.dumps(token) + ')')
                        page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(ui_url + '/#/duel-zone'); pages.append(page)
                    host, guest = pages
                    websocket_connections = []
                    for page in pages:
                        page.on('websocket', lambda socket: websocket_connections.append(socket.url))
                    host.get_by_label('Dein Deck', exact=True).select_option(host_deck)
                    if manual:
                        print('\nMANUELLER DUELLTEST: Zwei Edge-Fenster mit getrennten Testkonten sind geöffnet.', flush=True)
                        print('Separate temporäre Datenbank; echte Konten, Karten und .env bleiben unverändert.', flush=True)
                        print('Im ersten Fenster: Private Lobby erstellen. Im zweiten: Code eingeben und beitreten.', flush=True)
                        print('Gast bestätigen, im Gastfenster das vorbereitete Deck auswählen.', flush=True)
                        print('Die Deckauswahl wird sofort gespeichert. Gastgeber drückt Match starten.', flush=True)
                        print('Du kannst Deckverwaltung, Einzelduell/Match, Sideboarding, Neuladen und Historie testen.', flush=True)
                        print('Serveradresse: ' + ui_url + '/#/duel-zone', flush=True)
                        input('\nZum Beenden hier Enter drücken. Die Testdaten werden danach entfernt.\n')
                        browser.close()
                        return
                    host.get_by_role('button', name='Private Lobby erstellen', exact=True).click()
                    expect(host.locator('.duel-room-heading h2')).to_contain_text('SDO-')
                    guest.get_by_text('Mit Code beitreten',exact=True).click()
                    guest.get_by_label('Lobby-Code', exact=True).fill(host.locator('.duel-room-heading h2').inner_text())
                    guest.get_by_role('button', name='Beitreten', exact=True).click()
                    expect(host.get_by_role('button', name='Gast bestätigen', exact=True)).to_be_visible(timeout=10000)
                    host.get_by_role('button', name='Gast bestätigen', exact=True).click()
                    guest.get_by_label('Dein Deck', exact=True).select_option(guest_deck)
                    expect(host.get_by_role('button', name='Match starten', exact=True)).to_be_enabled(timeout=10000)
                    for page in pages:
                        expect(page.locator('.duel-confirmation')).to_have_count(0)
                        expect(page.locator('.duel-worker-optin')).to_have_count(0)
                    # Clearing the selection withdraws readiness without clearing the other player's deck.
                    guest.get_by_label('Dein Deck', exact=True).select_option('')
                    expect(host.get_by_role('button', name='Match starten', exact=True)).to_be_disabled(timeout=10000)
                    expect(host.locator('.duel-seat').first).to_contain_text('Bereit')
                    guest.get_by_label('Dein Deck', exact=True).select_option(guest_deck)
                    expect(host.get_by_role('button', name='Match starten', exact=True)).to_be_enabled(timeout=10000)
                    host.screenshot(path=str(artifacts / 'simple-start-lobby.png'), full_page=True)
                    host.get_by_role('button', name='Match starten', exact=True).click()
                    for page in pages: expect(page.locator('.duel-worker-table')).to_be_visible(timeout=15000)
                    for page in pages: expect(page.locator('.duel-player-field')).to_have_count(2, timeout=15000)
                    for page in pages:
                        expect(page.locator('.arena-slot')).to_have_count(24)
                        expect(page.locator('.arena-extra-row .arena-slot')).to_have_count(2)
                        backs = page.locator('.arena-opponent .arena-hand img')
                        assert backs.count() > 0
                        assert all('card-back' in backs.nth(index).get_attribute('src') for index in range(backs.count()))
                    with httpx.Client(base_url=api_url) as client:
                        headers = {'Authorization': 'Bearer ' + host_token}
                        room = client.get('/api/duel-zone/me', headers=headers).json(); run_id = room['worker_run_id']
                        for token, seat in ((host_token, 0), (guest_token, 1)):
                            result = client.get('/api/duel-zone/worker/runs/' + run_id, headers={'Authorization': 'Bearer ' + token}).json()
                            assert result['state'] == 'running' and result['seat'] == seat
                            assert result['clock']['limit'] == 360 and result['clock']['refill_ratio'] == .5
                            assert all(0 < value <= 360 for value in result['clock']['remaining'])
                            assert max(result['clock']['remaining']) == 360
                            assert all(card is None for card in result['board']['boards'][1-seat]['hand'])
                            assert any(card for card in result['board']['boards'][seat]['hand'])
                    host.locator('.duel-player-field').nth(1).locator('.duel-hand .duel-playing-card').first.click()
                    expect(host.get_by_role('complementary', name='Kartenvorschau').get_by_role('button', name='Vorschau schließen')).to_be_visible()
                    preview_image = host.get_by_role('complementary', name='Kartenvorschau').locator('img')
                    expect(preview_image).to_be_visible(timeout=30000)
                    host.wait_for_function("document.querySelector('.duel-card-inspector img')?.naturalWidth > 0", timeout=30000)
                    host.screenshot(path=str(artifacts / 'card-preview.png'), full_page=True)
                    host.keyboard.press('Escape'); expect(host.get_by_role('button', name='Vorschau schließen')).not_to_be_visible()
                    # Drag a real hand instance; choose Set and let the core
                    # validate the requested destination through its place prompt.
                    host.locator('.arena-own .arena-hand-card').first.drag_to(host.locator('.arena-slot[data-duel-owner="0"][data-duel-zone="4"][data-duel-sequence="2"]'))
                    host.locator('.placement-open').get_by_role('button', name='Setzen', exact=True).click()
                    expect(host.locator('.arena-slot[data-duel-owner="0"][data-duel-zone="4"][data-duel-sequence="2"] .duel-playing-card')).to_be_visible(timeout=10000)
                    host.locator('.arena-phase-orb').click()
                    host.get_by_role('button', name='Endphase · Zug beenden', exact=True).click()
                    for page in (host, guest):
                        expect(page.locator('.duel-event-log')).to_contain_text('Beendet Zug', timeout=10000)
                        expect(page.locator('.duel-event-log')).to_contain_text('Zug beendet', timeout=10000)
                    # The ordinary action buttons lead to the same clickable
                    # place prompt, including correct owner mapping on seat 1.
                    expect(guest.locator('.arena-own .arena-hand-card.action-available').first).to_be_visible(timeout=10000)
                    guest.locator('.arena-own .arena-hand-card.action-available').first.locator('.duel-playing-card').click()
                    guest.locator('.placement-open').get_by_role('button', name='Beschwören', exact=True).click()
                    destination = guest.locator('.arena-slot[data-duel-owner="1"][data-duel-zone="4"][data-duel-sequence="4"]')
                    expect(destination.locator('.arena-zone-choice')).to_be_enabled(timeout=10000)
                    destination.locator('.arena-zone-choice').click()
                    expect(destination.locator('.duel-playing-card')).to_be_visible(timeout=10000)
                    summoned_name = destination.locator('.duel-playing-card').get_attribute('aria-label').removesuffix(' ansehen')
                    for page in (host, guest):
                        expect(page.locator('.duel-event-log li').filter(has_text='Normal-/Tributbeschwörung').last).to_contain_text('Karte: ' + summoned_name)
                    guest.locator('.arena-phase-orb').click()
                    guest.get_by_role('button',name='Kampfphase',exact=True).click()
                    expect(destination.locator('.arena-action-hotspot')).to_be_enabled(timeout=10000)
                    destination.locator('.arena-action-hotspot').click()
                    guest.get_by_role('button',name='Angriff starten',exact=True).click()
                    target=guest.locator('.arena-slot[data-duel-owner="0"][data-duel-zone="4"][data-duel-sequence="2"] .arena-action-hotspot')
                    expect(target).to_be_enabled(timeout=10000)
                    target.dblclick()
                    for page in (host,guest):
                        expect(page.locator('.duel-event-log')).to_contain_text('Angriff',timeout=10000)
                    expect(guest.get_by_role('button',name='Angriff bestätigen',exact=True)).to_have_count(0)
                    expect(host.locator('.duel-player-field')).to_have_count(2)
                    host.screenshot(path=str(artifacts / 'desktop.png'), full_page=True)
                    guest.reload()
                    expect(guest.locator('.duel-player-field')).to_have_count(2, timeout=10000)
                    guest.set_viewport_size({'width': 390, 'height': 844})
                    guest.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    assert guest.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    guest.screenshot(path=str(artifacts / 'mobile.png'), full_page=True)
                    guest.get_by_label('Duellmenü', exact=True).click()
                    guest.once('dialog', lambda dialog: dialog.dismiss())
                    guest.get_by_role('button', name='Duell aufgeben', exact=True).click()
                    expect(guest.get_by_role('button', name='Duell aufgeben', exact=True)).to_be_visible()
                    guest.once('dialog', lambda dialog: dialog.accept())
                    guest.get_by_role('button', name='Duell aufgeben', exact=True).click()
                    expect(guest.get_by_role('heading', name='Du hast verloren', exact=True)).to_be_visible(timeout=10000)
                    expect(host.get_by_role('heading', name='Du hast gewonnen', exact=True)).to_be_visible(timeout=10000)
                    assert len(websocket_connections) >= 3  # Two seats plus guest reload.
                    duel_connections = [url for url in websocket_connections if '/api/duel-zone/worker/runs/' in url]
                    assert len(duel_connections) >= 3
                    assert all('token=' not in url and 'Bearer' not in url for url in duel_connections)
                    host.get_by_role('button', name='Zur Lobby-Übersicht', exact=True).click()
                    host.get_by_text('Meine abgeschlossenen Duelle', exact=True).click()
                    expect(host.get_by_role('button', name='Privaten Spielverlauf ansehen', exact=True)).to_be_visible()
                    host.get_by_role('button', name='Privaten Spielverlauf ansehen', exact=True).click()
                    expect(host.get_by_role('heading', name='Deine damalige Ansicht', exact=True)).to_be_visible()
                    from sqlalchemy import create_engine, select, func
                    from sqlalchemy.orm import Session
                    from app.db.models import VariantInventory, InventoryTransaction, DuelWorkerRun
                    engine = create_engine('sqlite:///' + str(database_file))
                    with Session(engine) as db:
                        assert db.scalar(select(func.sum(VariantInventory.reserved))) == 0
                        assert baseline == (db.scalar(select(func.sum(VariantInventory.quantity))), db.scalar(select(func.count(InventoryTransaction.id))))
                        assert db.scalar(select(func.count(DuelWorkerRun.id))) == 1
                        row = db.get(DuelWorkerRun, run_id); assert row.state == 'finished' and row.reason == 'surrender' and row.winner_seat == 0
                        from app.core.passwords import hash_password
                        from app.db.models import PlayerDeck, User
                        owner = db.get(User, db.get(PlayerDeck, host_deck).user_id)
                        owner.role = 'super_admin'; owner.password_hash = hash_password('Browser-duel-policy-password')
                        db.commit()
                    engine.dispose()
                    host.goto(ui_url + '/#/admin/advanced'); host.reload()
                    host.get_by_role('button', name='Betrieb & Export', exact=True).click()
                    host.get_by_role('button', name='Neue Duelle pausieren', exact=True).click()
                    maintenance = host.get_by_role('dialog', name='Duellbetrieb in Wartung setzen')
                    maintenance.get_by_role('button', name='Abbrechen', exact=True).click()
                    expect(host.get_by_role('button', name='Neue Duelle pausieren', exact=True)).to_be_visible()
                    for button, title in (('Neue Duelle pausieren', 'Duellbetrieb in Wartung setzen'),
                                          ('Neue Duelle wieder zulassen', 'Neue Duelle wieder zulassen')):
                        host.get_by_role('button', name=button, exact=True).click()
                        modal = host.get_by_role('dialog', name=title)
                        modal.get_by_label('Begründung', exact=True).fill('Isolierte Browserabnahme des Wartungsschalters')
                        modal.get_by_label('Dein Administrator-Passwort', exact=True).fill('Browser-duel-policy-password')
                        modal.get_by_role('button', name='Verbindlich bestätigen', exact=True).click()
                        expect(modal).not_to_be_visible(timeout=10000)
                    expect(host.get_by_role('button', name='Neue Duelle pausieren', exact=True)).to_be_visible(timeout=10000)
                    profiles = host.get_by_label('Versioniertes Regelprofil', exact=True)
                    expect(profiles.locator('option')).to_have_count(2)
                    profiles.select_option(index=1)
                    host.get_by_label('Abnahmenachweise und Quellen', exact=True).fill('Künstlicher Browsernachweis nur für die isolierte Testdatenbank.')
                    host.get_by_role('button', name='Regelfreigabe prüfen', exact=True).click()
                    modal = host.get_by_role('dialog', name='Regelfreigabe dokumentieren', exact=True)
                    modal.get_by_label('Begründung', exact=True).fill('Isolierte Prüfung der versionierten Regelfreigabe')
                    modal.get_by_label('Dein Administrator-Passwort', exact=True).fill('Browser-duel-policy-password')
                    modal.get_by_role('button', name='Verbindlich bestätigen', exact=True).click()
                    expect(modal).not_to_be_visible(timeout=10000)
                    picker = host.locator('.workflow-picker').filter(has=host.get_by_label('Konto für Duellsperre suchen', exact=True))
                    picker.locator('.workflow-choices button').first.click()
                    expect(host.get_by_text('Keine aktive Duellsperre', exact=True)).to_be_visible()
                    for button in ('Duellsperre festlegen', 'Duellsperre aufheben'):
                        host.get_by_role('button', name=button, exact=True).click()
                        modal = host.get_by_role('dialog')
                        modal.get_by_label('Begründung', exact=True).fill('Isolierte Browserprüfung einer befristeten Duellsperre')
                        modal.get_by_label('Dein Administrator-Passwort', exact=True).fill('Browser-duel-policy-password')
                        modal.get_by_role('button', name='Verbindlich bestätigen', exact=True).click()
                        expect(modal).not_to_be_visible(timeout=10000)
                    expect(host.get_by_text('Keine aktive Duellsperre', exact=True)).to_be_visible()
                    assert not errors, errors
                    report = {'status': 'passed', 'native_core': True, 'production_modified': False,
                        'tests': ['two-hub-sessions', 'deck-choice-authorizes-start-without-extra-confirmations','deselect-revokes-readiness-without-resetting-other-deck', 'snapshot-worker-start', 'private-hands', 'native-answer','native-double-click-attack-target','360-second-budget-with-50-percent-recovery','named-summon-log-for-both-seats','shared-turn-end-request-and-completion', 'card-preview', 'browser-reload', 'mobile-layout', 'cancel-surrender', 'surrender-and-result', 'reservation-release', 'no-inventory-or-journal-change', 'one-worker-run', 'authenticated-websocket', 'credentials-not-in-urls', 'private-history-playback', 'cancel-maintenance', 'admin-pause-admission', 'admin-resume-admission', 'versioned-rule-review', 'duel-only-restriction', 'duel-restriction-revocation'], 'console_errors': errors}
                    (artifacts / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
                    print(json.dumps(report)); browser.close()
            finally:
                if host_token:
                    try:
                        with httpx.Client(base_url=api_url, timeout=10, headers={'Authorization': 'Bearer ' + host_token}) as client:
                            room = client.get('/api/duel-zone/me').json()
                            active_id = run_id or (room or {}).get('worker_run_id')
                            if active_id: client.post('/api/duel-zone/worker/runs/' + active_id + '/surrender', json={})
                    except Exception: pass
                for process in (frontend, backend):
                    if process.poll() is None: process.terminate()
                for process in (frontend, backend):
                    try: process.wait(timeout=15)
                    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Isolierter nativer Duelltest mit zwei Browserkonten.')
    parser.add_argument('--manual', action='store_true', help='Zwei sichtbare Browserfenster zum selbst Spielen öffnen.')
    run(manual=parser.parse_args().manual)
