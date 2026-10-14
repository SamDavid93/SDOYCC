"""Opt-in product-settings UI check; disposable database and local servers only."""
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timedelta

from playwright.sync_api import expect, sync_playwright

from browser_smoke import ROOT, free_port, wait_ready
from dark_design_browser_checks import stop_process


def run():
    sys.stdout.reconfigure(encoding='utf8')
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.core.passwords import hash_password
    password = 'Isolated-products-test-123!'
    token = secrets.token_urlsafe(32)
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{ui_port}'
    artifacts = ROOT / 'artifacts/admin-products'
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sdoycc-product-review-') as temporary:
        database = Path(temporary) / 'products.db'
        env = {**os.environ, 'DATABASE_URL': f'sqlite:///{database}', 'APP_ENV': 'development',
               'ENABLE_DEMO_AUTH': 'true', 'ENABLE_DUEL_WORKER_LAB': 'false', 'ENABLE_DUEL_ALPHA': 'false',
               'CORS_ORIGINS': ui_url, 'VITE_API_BASE_URL': api_url + '/api', 'VITE_BASE_PATH': '/',
               'FRONTEND_URL': ui_url + '/', 'STREAMERBOT_API_KEY': 'isolated-products-no-bridge',
               'TWITCH_REWARD_ID': 'isolated-products-no-reward'}
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        with (artifacts / 'servers.log').open('w', encoding='utf8') as log:
            backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--port', str(api_port)], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            frontend = subprocess.Popen([os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe'), str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(ui_port), '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, creationflags=flags)
            try:
                wait_ready(api_url + '/api/health', backend, timeout=60)
                wait_ready(ui_url, frontend)
                with closing(sqlite3.connect(database)) as db:
                    owner = db.execute('SELECT id FROM users LIMIT 1').fetchone()[0]
                    db.execute("UPDATE users SET role='super_admin',password_hash=?,twitch_id='isolated-owner' WHERE id=?", (hash_password(password), owner))
                    db.execute('INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), owner, datetime.utcnow() + timedelta(hours=1)))
                    pack_id = db.execute("SELECT id FROM booster_packs WHERE key='standard-booster'").fetchone()[0]
                    db.commit()
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.add_init_script('sessionStorage.setItem("hub-session", ' + repr(token) + ')')
                    page.goto(ui_url + '/#/admin')
                    page.get_by_text('Preise & Packinhalt verwalten', exact=True).click()
                    page.get_by_label('Produkt suchen').fill('SDOYCC Origins')
                    page.get_by_role('button', name='Anpassen', exact=True).click()
                    page.get_by_label('Produktpreis', exact=True).fill('25')
                    page.get_by_label('Karten pro Pack', exact=True).fill('12')
                    page.get_by_role('button', name='Änderung prüfen', exact=True).click()
                    dialog = page.get_by_role('dialog', name='Produktregeln ändern')
                    expect(dialog).to_contain_text('100 → 25')
                    expect(dialog).to_contain_text('9 → 12')
                    page.screenshot(path=str(artifacts / 'confirmation-desktop.png'), full_page=True)
                    dialog.get_by_label('Begründung').fill('Produktregeln im isolierten Browser prüfen')
                    dialog.get_by_label('Dein Administrator-Passwort').fill(password)
                    dialog.get_by_role('button', name='Verbindlich bestätigen').click()
                    expect(page.get_by_text('Änderungen gespeichert', exact=False)).to_be_visible()
                    page.screenshot(path=str(artifacts / 'saved-desktop.png'), full_page=True)
                    page.reload()
                    page.get_by_text('Preise & Packinhalt verwalten', exact=True).click()
                    page.get_by_label('Produkt suchen').fill('SDOYCC Origins')
                    expect(page.locator('.admin-entry').filter(has_text='SDOYCC Origins')).to_contain_text('12 Karten')
                    page.get_by_role('button', name='Anpassen', exact=True).click()
                    expect(page.get_by_label('Produktpreis', exact=True)).to_have_value('25')
                    expect(page.get_by_label('Karten pro Pack', exact=True)).to_have_value('12')
                    page.set_viewport_size({'width': 390, 'height': 844})
                    if page.locator('.sidebar.is-open').count():
                        page.locator('.mobile-close').click()
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile product editor overflow'
                    page.screenshot(path=str(artifacts / 'editor-mobile.png'), full_page=True)
                    with closing(sqlite3.connect(database)) as db:
                        assert db.execute('SELECT price_override,draw_count_override FROM booster_packs WHERE id=?', (pack_id,)).fetchone() == (25, 12)
                        db.execute("UPDATE users SET role='admin' WHERE id=?", (owner,))
                        db.commit()
                    page.reload()
                    expect(page.get_by_role('heading', name='Deine Community im Blick')).to_be_visible()
                    expect(page.get_by_text('Preise & Packinhalt verwalten', exact=True)).to_have_count(0)
                    assert not errors, errors
                    browser.close()
                    print('PASS: owner editor, confirmation, persistence, mobile layout, admin restriction, no browser errors', flush=True)
            finally:
                stop_process(frontend)
                stop_process(backend)


if __name__ == '__main__':
    run()
