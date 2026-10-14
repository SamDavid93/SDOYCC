"""Opt-in visual review of the real App, using only a disposable Hub database.

Run with .venv/Scripts/python.exe backend/tests/dark_design_browser_checks.py.
Screenshots and the machine-readable review are written to artifacts/dark-design.
No production server, account, inventory, or database is used.
"""
import hashlib
import gc
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from browser_smoke import ROOT, free_port, wait_ready
from deck_browser_checks import seed_fixture


def prepare_review(database_file):
    """Reuse rule fixtures, then create an administrator in this temporary DB."""
    _, _, _, guest_deck_id = seed_fixture(database_file)
    token, deck_id = secrets.token_urlsafe(32), str(uuid4())
    with closing(sqlite3.connect(database_file)) as db, db:
        user_id = db.execute("SELECT id FROM users WHERE username='jaden-demo'").fetchone()[0]
        db.execute("UPDATE users SET role='super_admin',display_name='Alpha Duellant' WHERE id=?", (user_id,))
        db.execute('INSERT INTO auth_sessions (token_hash,user_id,expires_at) VALUES (?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(), user_id,
                    (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)).isoformat(' ')))
        source = db.execute('SELECT profile_id,entries_json FROM player_decks WHERE id=?', (guest_deck_id,)).fetchone()
        db.execute('INSERT INTO player_decks (id,user_id,name,notes,profile_id,entries_json,version,archived,created_at,updated_at) '
                   'VALUES(?,?,?,?,?,?,1,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)',
                   (deck_id, user_id, 'Dunkle Drachen', '', source[0], source[1]))
        card_codes = dict(db.execute("SELECT id,external_id FROM cards"))
        db.commit()
    return token, deck_id, card_codes


def inventory_totals(database_file):
    with closing(sqlite3.connect(database_file)) as db:
        return {
            'cards': db.execute('SELECT COALESCE(SUM(quantity),0) FROM inventory_items').fetchone()[0],
            'packs': db.execute('SELECT COALESCE(SUM(quantity),0) FROM user_boosters').fetchone()[0],
            'credits': db.execute('SELECT COALESCE(SUM(credits),0) FROM users').fetchone()[0],
        }


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        stopped = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, text=True)
        if stopped.returncode and process.poll() is None:
            raise RuntimeError(f'Could not stop isolated process tree {process.pid}: {stopped.stderr.strip()}')
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def run():
    sys.stdout.reconfigure(encoding='utf8')
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{ui_port}'
    node = os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe' if os.name == 'nt' else 'node')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    artifacts = ROOT / 'artifacts/dark-design'
    artifacts.mkdir(parents=True, exist_ok=True)
    report = {'checks': [], 'screenshots': [], 'page_errors': []}

    def check(name, condition, detail=None):
        report['checks'].append({'name': name, 'passed': bool(condition), 'detail': detail})
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)

    with tempfile.TemporaryDirectory(prefix='sdoycc-dark-review-') as temporary:
        database_file = Path(temporary) / 'visual-review.db'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(database_file), 'APP_ENV': 'development',
               'ENABLE_DEMO_AUTH': 'true', 'ENABLE_DUEL_WORKER_LAB': 'false', 'ENABLE_DUEL_ALPHA': 'false',
               'CORS_ORIGINS': ui_url, 'VITE_API_BASE_URL': api_url + '/api', 'VITE_BASE_PATH': '/',
               'FRONTEND_URL': ui_url + '/', 'STREAMERBOT_API_KEY': 'isolated-visual-review-no-bridge',
               'TWITCH_REWARD_ID': 'isolated-visual-review-no-reward'}
        with (artifacts / 'servers.log').open('w', encoding='utf8') as log:
            backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend',
                                        '--port', str(api_port)], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            frontend = subprocess.Popen([node, str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1',
                                         '--port', str(ui_port), '--strictPort'], cwd=ROOT / 'frontend', env=env,
                                        stdout=log, stderr=log, creationflags=flags)
            try:
                wait_ready(api_url + '/api/health', backend, timeout=60)
                wait_ready(ui_url, frontend)
                token, deck_id, card_codes = prepare_review(database_file)
                initial_inventory = inventory_totals(database_file)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel=os.environ.get('BROWSER_CHANNEL', 'msedge'), headless=True)
                    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
                    page.on('pageerror', lambda error: report['page_errors'].append(str(error)))

                    def card_image(route):
                        match = re.search(r'/api/cards/(\d+)/art/', route.request.url)
                        code = card_codes.get(int(match[1])) if match else None
                        image_file = ROOT / 'cache/cards-original' / f'{code}.img'
                        if code and image_file.is_file():
                            route.fulfill(content_type='image/jpeg', body=image_file.read_bytes())
                        else:
                            route.fulfill(status=404)

                    page.route('**/api/cards/*/art/**', card_image)
                    def external_image(route):
                        match = re.search(r'/([0-9]+)\.jpg', route.request.url)
                        image_file = ROOT / 'cache/cards-original' / f'{match[1] if match else "missing"}.img'
                        if image_file.is_file():
                            route.fulfill(content_type='image/jpeg', body=image_file.read_bytes())
                        else:
                            route.abort()

                    # Original art is served from disk; no remote image requests.
                    page.route('https://images.ygoprodeck.com/**', external_image)

                    def photograph(name, full_page=True):
                        filename = artifacts / f'{name}.png'
                        if full_page:
                            # Bring lazy card art into view before a full-page review image.
                            page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
                            page.wait_for_timeout(100)
                            page.evaluate('window.scrollTo(0,0)')
                            page.wait_for_timeout(100)
                        page.screenshot(path=str(filename), full_page=full_page, animations='disabled')
                        report['screenshots'].append(str(filename.relative_to(ROOT)))

                    def inspect(name, fixed=False):
                        page.evaluate('document.fonts.ready.then(() => true)')
                        page.wait_for_timeout(160)
                        metrics = page.evaluate('''() => {
                          const root=document.documentElement;
                          const rgb=s=>(s.match(/[\\d.]+/g)||[]).slice(0,3).map(Number);
                          const body=getComputedStyle(document.body);
                          const channels=rgb(body.backgroundColor).map(x=>x/255);
                          const luminance=channels.reduce((sum,x,i)=>sum+[.2126,.7152,.0722][i]*(x<=.04045?x/12.92:((x+.055)/1.055)**2.4),0);
                          const lightSurfaces=[...document.querySelectorAll('.content-panel,.stat-card,.card-visual,.vault-stack,.booster-tile,.inventory-summary,.workflow-empty,.empty-state,.deck-panel,.search-field')]
                            .filter(el=>{
                              if(!el.getClientRects().length)return false;
                              const bg=getComputedStyle(el).backgroundColor,values=(bg.match(/[\\d.]+/g)||[]).map(Number);
                              return (values[3]??1)>.95&&rgb(bg).reduce((sum,x)=>sum+x,0)/3>190;
                            }).map(el=>({class:el.className,background:getComputedStyle(el).backgroundColor}));
                          const overflow=[...document.querySelectorAll('.page-wrap *, .topbar, .site-footer')]
                            .filter(el=>{const b=el.getBoundingClientRect();return b.width&&b.left>=0&&b.right>innerWidth+2&&getComputedStyle(el).position!=='fixed'})
                            .slice(0,8).map(el=>({tag:el.tagName,class:el.className,right:el.getBoundingClientRect().right}));
                          return {width:innerWidth,documentWidth:root.scrollWidth,height:innerHeight,
                            documentHeight:root.scrollHeight,bodyLuminance:luminance,background:body.backgroundColor,overflow,lightSurfaces};
                        }''')
                        check(name + ': no horizontal page scroll', metrics['documentWidth'] <= metrics['width'] + 1, metrics)
                        check(name + ': dark background', metrics['bodyLuminance'] < .08, metrics['background'])
                        check(name + ': dark content surfaces', not metrics['lightSurfaces'], metrics['lightSurfaces'])
                        footer = page.locator('footer[aria-label="Copyright notice"]')
                        check(name + ': copyright footer', footer.count() == 1 and '4K Media Inc' in footer.inner_text())
                        if fixed:
                            check(name + ': viewport frame', metrics['documentHeight'] <= metrics['height'] + 1, metrics)
                            page.evaluate('window.scrollTo(0,1000)')
                            check(name + ': document remains fixed', page.evaluate('scrollY') == 0)

                    page.goto(ui_url)
                    expect(page.get_by_role('button', name='Anmelden', exact=True)).to_be_visible()
                    page.locator('.auth-brand-logo').evaluate('image => image.decode()')
                    inspect('login-desktop')
                    photograph('login-desktop')
                    page.set_viewport_size({'width': 390, 'height': 844})
                    inspect('login-mobile')
                    photograph('login-mobile')
                    page.evaluate('(token) => sessionStorage.setItem("hub-session",token)', token)
                    page.reload()
                    expect(page.locator('.sidebar .main-nav')).to_be_attached()
                    routes = [
                        ('home', '/', '.hub-hero'),
                        ('catalog', '/cards', '.catalog-grid .card-visual'),
                        ('boosters', '/boosters', '.booster-tile'),
                        ('vault', '/my-packs', '.vault-hero'),
                        ('collection', '/inventory', '.collection-grid'),
                        ('decks', '/decks', '.deck-tile'),
                        ('editor', '/decks/' + deck_id, '.deck-workbench'),
                        ('duel-lobby', '/duel-zone', '.duel-mode-card'),
                        ('trade', '/trade', '.workflow-hero'),
                        ('season', '/battle-pass', '.workflow-hero'),
                        ('account', '/account', '.account-section'),
                        ('admin', '/admin', '.admin-account-row'),
                        ('admin-advanced', '/admin/advanced', '.workflow-hero'),
                    ]
                    for name, path, ready in routes:
                        page.set_viewport_size({'width': 1920, 'height': 1080})
                        page.goto(ui_url + '/#' + path)
                        try:
                            expect(page.locator(ready).first).to_be_visible(timeout=15000)
                        except AssertionError:
                            # Record a missing route separately and continue collecting visual evidence.
                            check(name + ': route rendered', False, ready)
                            photograph(name + '-failed')
                            continue
                        check(name + ': route rendered', True)
                        for width, height in ((1920, 1080), (1280, 720), (390, 844)):
                            page.set_viewport_size({'width': width, 'height': height})
                            inspect(f'{name}-{width}', fixed=name in ('editor', 'duel-lobby'))
                            photograph(f'{name}-{width}', full_page=name not in ('editor', 'duel-lobby'))
                        if name == 'home':
                            button = page.get_by_role('button', name='Menü öffnen', exact=True)
                            button.focus()
                            page.keyboard.press('Enter')
                            expect(page.locator('.sidebar.is-open')).to_be_visible()
                            check('mobile menu opens by keyboard', page.locator('.sidebar.is-open').count() == 1)
                            page.locator('.sidebar.is-open .main-nav a').first.focus()
                            page.keyboard.press('Enter')
                            expect(page.locator('.sidebar.is-open')).to_have_count(0)
                            check('mobile menu closes after navigation', True)
                            button.focus()
                            page.keyboard.press('Enter')
                            expect(button).to_have_attribute('aria-expanded', 'true')
                            expect(page.locator('#' + button.get_attribute('aria-controls'))).to_be_visible()
                            page.keyboard.press('Escape')
                            expect(button).to_have_attribute('aria-expanded', 'false')
                            expect(button).to_be_focused()
                            check('mobile menu Escape restores focus', True)
                            page.evaluate('document.activeElement?.blur()')
                        if name == 'editor':
                            page.set_viewport_size({'width': 1920, 'height': 1080})
                            page.locator('.deck-extra-tools > summary').click()
                            page.get_by_role('button', name='Testhand ziehen', exact=True).click()
                            page.locator('.deck-test-hand .deck-card-preview').first.click()
                            dialog = page.get_by_role('dialog')
                            expect(dialog).to_be_visible()
                            check('card preview receives focus', dialog.evaluate('el => el.contains(document.activeElement)'))
                            photograph('editor-card-preview')
                            page.set_viewport_size({'width': 390, 'height': 844})
                            check('card preview mobile width', dialog.evaluate('el => el.scrollWidth <= el.clientWidth+1'))
                            photograph('editor-card-preview-mobile')
                            page.keyboard.press('Escape')
                            expect(dialog).to_have_count(0)
                            check('card preview closes with Escape', True)
                    check('no browser runtime errors', not report['page_errors'], report['page_errors'])
                    check('temporary inventory remains unchanged', inventory_totals(database_file) == initial_inventory)
                    browser.close()
            finally:
                stop_process(frontend)
                stop_process(backend)
                gc.collect()
                (artifacts / 'review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    failures = [item for item in report['checks'] if not item['passed']]
    print(f"{len(report['checks']) - len(failures)}/{len(report['checks'])} checks passed; {len(report['screenshots'])} screenshots.")
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    run()
