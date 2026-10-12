"""Opt-in two-server deck-builder check. Uses only a fresh temporary Hub database."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

from browser_smoke import ROOT, free_port, wait_ready


def seed_fixture(database_file):
    sys.path.insert(0, str(ROOT / 'backend'))
    sys.path.insert(0, str(ROOT / 'backend/scripts'))
    from import_duel_rules import load_source
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.db.models import Card, CardDetails, PlayerDeck, User
    from app.core.auth import create_session
    from app.modules.duel_rules import import_profile
    from app.modules.inventory import change_stock, variant
    data, limits, scripts, name, sources = load_source(ROOT / 'artifacts/duel-probe')
    with sqlite3.connect((ROOT / 'artifacts/duel-probe/cards/cards.cdb').as_uri() + '?mode=ro', uri=True) as cdb:
        rows = cdb.execute('SELECT d.id,t.name,t.desc,d.atk,d.def,d.level FROM datas d JOIN texts t ON d.id=t.id '
                           'WHERE d.type=17 AND d.alias=0 AND d.ot IN (2,3) AND (d.level & 255)<=4 ORDER BY d.id LIMIT 14').fetchall()
    engine = create_engine('sqlite:///' + str(database_file))
    try:
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.username == 'jaden-demo'))
            user.twitch_id = '900001'; user.password_hash = 'isolated-fixture-only'
            fixture_ids = []
            for code, title, desc, atk, defense, level in rows:
                card = Card(external_provider='ygoprodeck', external_id=str(code), name=title, card_set='Labor', set_code='TEST',
                            rarity='common', card_type='Normal Monster', attribute='DARK', image_url=f'https://images.ygoprodeck.com/images/cards/{code}.jpg')
                db.add(card); db.flush()
                fixture_ids.append(card.id)
                db.add(CardDetails(card_id=card.id, description_en=desc, atk=atk, defense=defense, level=level & 255, race='Fiend'))
                kind = variant(db, card.id, 'common')
                change_stock(db, user.id, kind, 3, 'isolated_test', f'deck-browser:{code}', bound=True)
            profile, counts = import_profile(db, db.scalars(select(Card)).all(), data, limits, scripts, name, sources)
            guest = User(username='duel-guest', display_name='Labor-Gegner', twitch_id='900002', password_hash='isolated-fixture-only', credits=0)
            db.add(guest); db.flush()
            guest_token = create_session(db, guest)
            guest_deck_id = str(uuid4())
            entries = [{'card_id': card_id, 'section': 'main', 'quantity': 3 if i < 13 else 1} for i, card_id in enumerate(fixture_ids)]
            for cid in fixture_ids:
                change_stock(db, guest.id, variant(db, cid, 'common'), 3, 'isolated_test', f'guest-browser:{cid}', bound=True)
            db.add(PlayerDeck(id=guest_deck_id, user_id=guest.id, name='Private Gaststrategie', profile_id=profile.id, entries_json=json.dumps(entries)))
            db.commit()
            codes = [row[0] for row in rows]
            return profile.id, codes, guest_token, guest_deck_id
    finally: engine.dispose()


def run():
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{ui_port}'
    node = os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe' if os.name == 'nt' else 'node')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    artifacts = ROOT / 'artifacts/deck-builder'; artifacts.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory() as temporary:
        database_file = Path(temporary) / 'decks.db'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(database_file), 'APP_ENV': 'development',
               'ENABLE_DEMO_AUTH': 'true', 'CORS_ORIGINS': ui_url, 'VITE_API_BASE_URL': api_url + '/api',
               'VITE_BASE_PATH': '/', 'FRONTEND_URL': ui_url + '/'}
        with (artifacts / 'servers.log').open('w', encoding='utf8') as log:
            backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--port', str(api_port)], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            frontend = subprocess.Popen([node, str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(ui_port), '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, creationflags=flags)
            try:
                wait_ready(api_url + '/api/health', backend); wait_ready(ui_url, frontend)
                profile, codes, guest_token, guest_deck_id = seed_fixture(database_file)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width': 1600, 'height': 1100})
                    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('**/api/cards/*/art/**', lambda route: route.fulfill(status=404))
                    page.goto(ui_url)
                    page.get_by_role('button', name='Lokale Demo öffnen').click()
                    page.get_by_role('link', name='Meine Decks', exact=True).first.click()
                    page.get_by_label('Neues Deck', exact=True).fill('Mein Browserdeck')
                    page.get_by_role('button', name='Deck erstellen', exact=True).click()
                    expect(page.get_by_label('Deckname', exact=True)).to_have_value('Mein Browserdeck')
                    expect(page.locator('.deck-library-card').first).to_be_visible()
                    # Rapid edits while debounce is running must all survive.
                    library_card = page.locator('.deck-library-card').first
                    library_card.locator('.deck-card-preview').click()
                    library_card.locator('.deck-card-preview').click()
                    library_card.locator('.deck-card-preview').click(button='right')
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('1')
                    library_card.drag_to(page.locator('.deck-section-tabs button').first)
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('2')
                    page.locator('.deck-entry').first.drag_to(page.locator('.deck-section-tabs button').nth(2))
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('1')
                    expect(page.locator('.deck-section-tabs button').nth(2).locator('b')).to_have_text('1')
                    page.locator('.deck-entry').first.drag_to(page.locator('.deck-section-tabs button').first)
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('2')
                    expect(page.locator('.deck-section-tabs button').nth(2).locator('b')).to_have_text('0')
                    page.locator('.deck-entry .deck-card-preview').first.click(button='right')
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('1')
                    page.locator('.deck-entry .deck-card-preview').first.click()
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('2')
                    page.locator('.deck-entry').first.drag_to(page.locator('.deck-return-zone'))
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('1')
                    library_card.locator('.deck-card-preview').click()
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('2')
                    expect(page.locator('.deck-save-indicator')).to_contain_text('Gespeichert', timeout=10000)
                    deck_id = page.url.split('/')[-1]
                    headers = {'Authorization': 'Bearer demo-token'}
                    result = page.request.get(api_url + '/api/decks/' + deck_id, headers=headers).json()
                    assert result['counts']['main'] == 2
                    # Known passcodes round-trip through the real mapping, preserving ownership.
                    text = '#created by isolated browser test\n#main\n' + '\n'.join(str(code) for code in codes[:13] for _ in range(3)) + f'\n{codes[13]}\n#extra\n!side\n'
                    page.once('dialog', lambda dialog: dialog.accept())
                    page.locator('input[type=file]').set_input_files({'name': 'strategy.ydk', 'mimeType': 'text/plain', 'buffer': text.encode()})
                    expect(page.locator('.deck-section-tabs button').first.locator('b')).to_have_text('40')
                    expect(page.locator('.deck-save-indicator')).to_contain_text('Gespeichert', timeout=10000)
                    expect(page.locator('.deck-status-strip>span').nth(0)).to_have_class('is-good')
                    expect(page.locator('.deck-status-strip>span').nth(1)).to_have_class('is-good')
                    expect(page.locator('.deck-status-strip>span').nth(2)).to_contain_text('Noch ausstehend')
                    page.screenshot(path=str(artifacts / 'desktop.png'), full_page=True)
                    page.get_by_role('button', name='Testhand ziehen', exact=True).click()
                    expect(page.locator('.deck-test-hand .deck-card-preview')).to_have_count(5)
                    page.locator('.deck-test-hand .deck-card-preview').first.click()
                    expect(page.get_by_role('dialog')).to_be_visible()
                    page.keyboard.press('Escape')
                    expect(page.get_by_role('dialog')).to_have_count(0)
                    with page.expect_download() as download:
                        page.get_by_role('button', name='YDK exportieren', exact=True).click()
                    exported = Path(download.value.path()).read_text()
                    assert len([line for line in exported.splitlines() if line.isdigit()]) == 40
                    # Browser Back after a failed save must not destroy the draft.
                    save_url = api_url + '/api/decks/' + deck_id
                    page.route(save_url, lambda route: route.abort() if route.request.method == 'PUT' else route.continue_())
                    page.locator('.deck-notes summary').click()
                    page.get_by_label('Deine privaten Notizen', exact=True).fill('Notizen trotz Verbindungsfehler behalten')
                    expect(page.locator('.deck-save-indicator')).to_contain_text('Nicht gespeichert', timeout=10000)
                    page.unroute(save_url)
                    page.go_back()
                    expect(page.get_by_role('heading', name='Meine Decks', exact=True)).to_be_visible()
                    page.get_by_role('link', name='Mein Browserdeck', exact=True).click()
                    expect(page.get_by_role('region', name='Ungespeicherten Entwurf wiederherstellen')).to_be_visible()
                    page.get_by_role('button', name='Entwurf wiederherstellen', exact=True).click()
                    page.locator('.deck-notes summary').click()
                    expect(page.get_by_label('Deine privaten Notizen', exact=True)).to_have_value('Notizen trotz Verbindungsfehler behalten')
                    expect(page.locator('.deck-save-indicator')).to_contain_text('Gespeichert', timeout=10000)
                    # A separate writer must yield a conflict, not silently overwrite either draft.
                    current = page.request.get(api_url + '/api/decks/' + deck_id, headers=headers).json()
                    payload = {k: current[k] for k in ('name', 'notes', 'entries', 'profile_id', 'version')}
                    changed = page.request.put(api_url + '/api/decks/' + deck_id, headers=headers, data={**payload, 'name': 'Anderer Bearbeitungsstand'})
                    assert changed.status == 200
                    page.get_by_label('Deckname', exact=True).fill('Mein ungespeicherter Stand')
                    expect(page.get_by_role('alert').filter(has_text='inzwischen verändert')).to_be_visible(timeout=10000)
                    expect(page.get_by_label('Deckname', exact=True)).to_have_value('Mein ungespeicherter Stand')
                    page.once('dialog', lambda dialog: dialog.accept())
                    page.get_by_role('button', name='Serverstand laden', exact=True).click()
                    expect(page.get_by_label('Deckname', exact=True)).to_have_value('Anderer Bearbeitungsstand')
                    page.locator('.deck-share-panel summary').click()
                    page.once('dialog', lambda dialog: dialog.accept())
                    page.get_by_role('button', name='Freigabelink erstellen', exact=True).click()
                    expect(page.get_by_label('Vorlagenlink', exact=True)).to_be_visible(timeout=10000)
                    share_url = page.get_by_label('Vorlagenlink', exact=True).input_value()
                    anonymous = browser.new_context().new_page(); anonymous.goto(share_url)
                    expect(anonymous.get_by_role('heading', name='Anderer Bearbeitungsstand', exact=True)).to_be_visible()
                    assert 'Notizen trotz Verbindungsfehler behalten' not in anonymous.locator('body').inner_text()
                    copy_context = browser.new_context()
                    copy_context.add_init_script('sessionStorage.setItem("hub-session", ' + json.dumps(guest_token) + ')')
                    copy_page = copy_context.new_page(); copy_page.goto(share_url)
                    copy_page.get_by_role('button', name='Als eigenen Deckentwurf kopieren', exact=True).click()
                    expect(copy_page.get_by_label('Deckname', exact=True)).to_have_value('Anderer Bearbeitungsstand')
                    copy_page.locator('.deck-notes summary').click()
                    expect(copy_page.get_by_label('Deine privaten Notizen', exact=True)).to_have_value('')
                    page.get_by_role('button', name='Link widerrufen', exact=True).click()
                    expect(page.get_by_label('Vorlagenlink', exact=True)).not_to_be_visible()
                    anonymous.reload()
                    expect(anonymous.get_by_role('alert')).to_contain_text('nicht mehr verfügbar')
                    copy_context.close(); anonymous.context.close()
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    expect(page.locator('.deck-composition')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile deck overflow'
                    page.screenshot(path=str(artifacts / 'mobile.png'), full_page=True)
                    page.get_by_role('button', name='Karten suchen', exact=True).first.click()
                    expect(page.locator('.deck-library')).to_be_visible()
                    page.get_by_role('button', name='Prüfung', exact=True).click()
                    expect(page.locator('.deck-review')).to_be_visible()
                    page.set_viewport_size({'width': 1600, 'height': 1100})
                    page.get_by_role('link', name='Meine Decks', exact=True).last.click()
                    page.get_by_role('button', name='Anderer Bearbeitungsstand archivieren', exact=True).click()
                    expect(page.locator('.deck-tile')).to_have_count(0)
                    page.get_by_role('button', name='Archiv', exact=True).click()
                    expect(page.locator('.deck-tile')).to_have_count(1)
                    page.get_by_role('button', name='Anderer Bearbeitungsstand wiederherstellen', exact=True).click()
                    page.get_by_role('button', name='Aktiv', exact=True).click()
                    page.get_by_role('button', name='Anderer Bearbeitungsstand duplizieren', exact=True).click()
                    expect(page.get_by_label('Deckname', exact=True)).to_have_value('Anderer Bearbeitungsstand (Kopie)')
                    host_deck_id = page.url.split('/')[-1]
                    page.get_by_role('link', name='DuelZone', exact=True).click()
                    page.get_by_label('Dein Deck', exact=True).select_option(host_deck_id)
                    page.get_by_role('button', name='Private Lobby erstellen', exact=True).click()
                    expect(page.locator('.duel-room-heading h2')).to_contain_text('SDO-')
                    code = page.locator('.duel-room-heading h2').inner_text()
                    guest_context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    guest_context.add_init_script('sessionStorage.setItem("hub-session", ' + json.dumps(guest_token) + ')')
                    guest_page = guest_context.new_page()
                    guest_page.on('pageerror', lambda error: errors.append(str(error)))
                    guest_page.goto(ui_url + '/#/duel-zone')
                    guest_page.get_by_label('Lobby-Code', exact=True).fill(code)
                    guest_page.get_by_role('button', name='Beitreten', exact=True).click()
                    expect(guest_page.locator('.duel-room')).to_be_visible()
                    # The guest owns the explicitly shared original name; the
                    # host's private duplicate name must nevertheless stay hidden.
                    assert 'Anderer Bearbeitungsstand (Kopie)' not in guest_page.locator('.duel-room').inner_text()
                    expect(page.get_by_role('button', name='Gast bestätigen', exact=True)).to_be_visible(timeout=10000)
                    page.get_by_role('button', name='Gast bestätigen', exact=True).click()
                    guest_page.get_by_label('Dein Deck', exact=True).select_option(guest_deck_id)
                    expect(guest_page.get_by_role('button', name='Deck auswählen', exact=True)).to_be_enabled(timeout=10000)
                    guest_page.get_by_role('button', name='Deck auswählen', exact=True).click()
                    expect(guest_page.locator('.duel-own-deck>p').first).to_have_text('Private Gaststrategie')
                    assert 'Private Gaststrategie' not in page.locator('.duel-room').inner_text()
                    expect(page.get_by_role('button', name='Mein Deck bestätigen', exact=True)).to_be_enabled(timeout=10000)
                    page.get_by_role('button', name='Mein Deck bestätigen', exact=True).click()
                    expect(guest_page.locator('.duel-confirmation-status span').first).to_contain_text('Deck bestätigt', timeout=10000)
                    guest_page.get_by_role('button', name='Mein Deck bestätigen', exact=True).click()
                    expect(page.get_by_role('region', name='Deckbestätigung')).to_contain_text('Beide Decks bestätigt', timeout=10000)
                    expect(guest_page.locator('.duel-start-note')).to_contain_text('ausgeschaltet')
                    page.screenshot(path=str(artifacts / 'lobby-desktop.png'), full_page=True)
                    guest_page.set_viewport_size({'width': 390, 'height': 844})
                    guest_page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    assert guest_page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile lobby overflow'
                    guest_page.screenshot(path=str(artifacts / 'lobby-mobile.png'), full_page=True)
                    guest_page.get_by_role('button', name='Bestätigung zurücknehmen', exact=True).click()
                    expect(page.locator('.duel-confirmation-status')).not_to_contain_text('Deck bestätigt', timeout=10000)
                    guest_page.get_by_role('button', name='Lobby verlassen', exact=True).click()
                    expect(guest_page.locator('.duel-entry-grid')).to_be_visible()
                    expect(page.locator('.duel-seat').nth(1)).to_contain_text('Platz frei', timeout=10000)
                    page.once('dialog', lambda dialog: dialog.accept())
                    page.get_by_role('button', name='Lobby schließen', exact=True).click()
                    expect(page.locator('.duel-entry-grid')).to_be_visible()
                    assert not errors, errors
                    report = {'status': 'passed', 'tests': ['create', 'rapid-autosave', 'real-rule-ydk-import', 'formal-check', 'ownership', 'engine-gate', 'preview-escape', 'test-hand', 'ydk-export', 'failed-save-draft-recovery', 'edit-conflict', 'mobile-tabs', 'archive-restore', 'duplicate', 'two-account-lobby', 'host-approval', 'private-deck-choice', 'two-account-deck-confirmation', 'withdraw-confirmation', 'mobile-lobby', 'leave-close', 'immutable-share-link', 'anonymous-template-view', 'private-notes-omitted', 'copy-own-draft', 'revoke-link'], 'console_errors': errors, 'production_modified': False}
                    (artifacts / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
                    print(json.dumps(report)); browser.close()
            finally:
                for process in (frontend, backend):
                    if process.poll() is None: process.terminate()
                for process in (frontend, backend):
                    try: process.wait(timeout=15)
                    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)


if __name__ == '__main__': run()
