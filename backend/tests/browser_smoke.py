"""Opt-in real-browser check; uses an isolated database and local servers."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time

import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_ready(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError(f"Server exited: {url}")
        try:
            if httpx.get(url).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Server did not start: {url}")


def run():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    node = os.environ.get("NODE_EXE", "C:/Program Files/nodejs/node.exe" if os.name == "nt" else "node")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory() as temporary:
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{Path(temporary) / 'browser.db'}", "APP_ENV": "development",
               "ENABLE_DEMO_AUTH": "true", "CORS_ORIGINS": ui_url, "VITE_API_BASE_URL": api_url + "/api", "VITE_BASE_PATH": "/",
               "FRONTEND_URL": ui_url + "/", "STREAMERBOT_API_KEY": "browser-test-bridge-key-12345678901234567890", "TWITCH_REWARD_ID": "browser-reward"}
        with open(Path(temporary) / "servers.log", "w", encoding="utf8") as log:
            backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--port", str(api_port)], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            frontend = subprocess.Popen([node, str(ROOT / "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", str(ui_port), "--strictPort"], cwd=ROOT / "frontend", env=env, stdout=log, stderr=log, creationflags=flags)
            try:
                wait_ready(api_url + "/api/health", backend)
                wait_ready(ui_url, frontend)
                # A deterministic image fixture verifies actual cover rendering without external requests.
                with sqlite3.connect(Path(temporary) / 'browser.db') as db:
                    db.execute("UPDATE booster_packs SET image_url = ? WHERE id = 1", ("https://example.com/test-pack.svg",))
                    db.execute("UPDATE booster_pool_entries SET rarity = 'ultra_rare'")

                db.close()
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL", "msedge"), headless=True)
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.route("https://example.com/test-pack.svg", lambda route: route.fulfill(content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg" width="150" height="220"><rect width="150" height="220" fill="#145d66"/><text x="16" y="100" fill="white">Test Booster</text></svg>'))
                    errors = []
                    api_requests = []
                    page.on("request", lambda request: api_requests.append(request.url) if request.url.startswith(api_url + "/api/") else None)
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(ui_url)
                    expect(page).to_have_title("SDOYCC – SamDavidOfficial's Yu-Gi-Oh Card Collector")
                    expect(page.locator('.auth-brand-logo')).to_be_visible()
                    page.wait_for_function("document.querySelector('.auth-brand-logo').naturalWidth > 0")
                    page.screenshot(path=str(ROOT / 'artifacts/sdoycc-login-brand.png'), full_page=True)
                    page.get_by_role("button", name="Lokale Demo öffnen").click()
                    expect(page.get_by_role("heading", name="Willkommen, Jaden D.")).to_be_visible()
                    expect(page.locator('.brand-logo')).to_be_visible()
                    page.wait_for_function("document.querySelector('.hub-brand-banner').naturalWidth > 0")
                    page.screenshot(path=str(ROOT / 'artifacts/sdoycc-banner-desktop.png'), full_page=True)
                    expect(page.locator(".currency")).to_contain_text("2.450 Sammelpunkte")
                    page.get_by_role("link", name="Booster", exact=True).first.click()
                    expect(page.locator(".booster-tile .booster-cover img").first).to_have_attribute("src", "https://example.com/test-pack.svg")
                    assert api_requests.count(api_url + "/api/boosters") == 1, "Concurrent/page navigation reads should share cached booster data"
                    progress = page.request.get(api_url + '/api/boosters', headers={'Authorization': 'Bearer demo-token'}).json()[0]['collection_progress']
                    meter = page.locator('.booster-tile .booster-collection-progress').first
                    expect(meter.locator('progress')).to_have_attribute('value', str(progress['owned']))
                    expect(meter.locator('progress')).to_have_attribute('max', str(progress['total']))
                    expect(meter).to_contain_text(f"{progress['owned']} von {progress['total']}")
                    page.screenshot(path=str(ROOT / 'artifacts/booster-progress-desktop.png'), full_page=True)
                    page.route("**/api/boosters/1/purchase", lambda route: route.fulfill(status=400, content_type="application/json", body='{"detail":"Test: Kauf abgelehnt"}'))
                    page.get_by_role("button", name="Kaufen", exact=True).first.click()
                    expect(page.get_by_role("alert").filter(has_text="Test: Kauf abgelehnt")).to_be_visible()
                    expect(page.get_by_role("complementary", name="Kaufbestätigung")).to_have_count(0)
                    expect(page.locator(".currency")).to_contain_text("2.450 Sammelpunkte")
                    page.unroute("**/api/boosters/1/purchase")
                    page.get_by_role("button", name="Kaufen", exact=True).first.click()
                    expect(page.locator(".currency")).to_contain_text("2.350 Sammelpunkte")
                    receipt = page.get_by_role("complementary", name="Kaufbestätigung")
                    expect(receipt).to_be_in_viewport()
                    expect(receipt).to_contain_text("Booster erfolgreich gekauft!")
                    expect(receipt).to_contain_text("1 × SDOYCC Origins")
                    expect(receipt).to_contain_text("100 Sammelpunkte")
                    expect(receipt).to_contain_text("2.350 Sammelpunkte")
                    expect(receipt).to_contain_text("5 Packs")
                    page.set_viewport_size({"width": 390, "height": 844})
                    expect(receipt).to_be_in_viewport(ratio=1)
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Purchase receipt mobile overflow"
                    (ROOT / "artifacts").mkdir(exist_ok=True)
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    page.screenshot(path=str(ROOT / "artifacts/purchase-feedback-mobile.png"), animations="disabled")
                    # Keep the actual opening transaction, but exercise text fallbacks deterministically.
                    opened_cards = []
                    def opening_text_fixture(route):
                        response = route.fetch()
                        payload = response.json()
                        payload['cards'][1]['description'] = 'Original card effect.\nA second effect paragraph.'
                        payload['cards'][1]['description_language'] = 'en'
                        payload['cards'][2]['description'] = '   '
                        opened_cards.extend(payload['cards'])
                        route.fulfill(response=response, json=payload)
                    page.route('**/api/boosters/1/open', opening_text_fixture)
                    receipt.get_by_role("button", name="Jetzt kostenlos öffnen").click()
                    expect(receipt).to_have_count(0)
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    opening = page.locator("dialog.opening-show")
                    expect(opening).to_be_visible()
                    expect(opening.get_by_role("button", name="Karte 1 aufdecken", exact=True)).to_be_visible(timeout=10000)
                    opening.get_by_role("button", name="Karte 1 aufdecken", exact=True).focus()
                    page.keyboard.press("Enter")
                    expect(opening.locator(".is-revealed")).to_have_count(1)
                    expect(opening.locator(".rarity-spotlight.rarity-gold")).to_be_visible()
                    expect(opening.locator(".spotlight-copy")).to_contain_text("Ultraselten")
                    page.screenshot(path=str(ROOT / "artifacts/opening-reveal-desktop.png"), animations="disabled")
                    expect(page.locator('.opening-card-preview')).to_have_count(0)
                    revealed_card = opening.locator('.is-revealed .reveal-card').first
                    revealed_card.focus()
                    requests_before_preview = len(api_requests)
                    page.keyboard.press('Enter')
                    preview = page.get_by_role('dialog', name=opened_cards[0]['name'], exact=True)
                    expect(preview).to_be_visible()
                    expect(preview.locator('.opening-preview-description')).to_have_text(opened_cards[0]['description'])
                    expect(preview.locator('.opening-preview-pack')).to_contain_text('SDOYCC Origins')
                    expect(preview.locator('.opening-preview-rarity')).to_have_text('Ultraselten')
                    expect(preview.locator('.card-rarity-badge')).to_have_attribute('aria-label', 'Seltenheit: Ultraselten')
                    expect(preview.get_by_role('button', name='Kartenvorschau schließen')).to_be_focused()
                    page.keyboard.press('Tab')
                    expect(preview.get_by_role('button', name='Zurück zu deinen Karten')).to_be_focused()
                    page.keyboard.press('Shift+Tab')
                    expect(preview.get_by_role('button', name='Kartenvorschau schließen')).to_be_focused()
                    page.screenshot(path=str(ROOT / 'artifacts/opening-preview-desktop.png'), animations='disabled')
                    page.keyboard.press('Escape')
                    expect(preview).to_have_count(0)
                    expect(opening).to_be_visible()
                    expect(revealed_card).to_be_focused()
                    expect(opening.locator('.is-revealed')).to_have_count(1)
                    assert not any('/open' in url for url in api_requests[requests_before_preview:]), 'Preview must not open another pack'
                    opening.get_by_role("button", name="Alle aufdecken", exact=True).click()
                    expect(opening.locator(".opening-summary-grid .card-visual")).to_have_count(5)
                    summary_cards = opening.locator('.summary-card')
                    summary_cards.nth(1).click()
                    preview = page.locator('dialog.opening-card-preview')
                    expect(preview.locator('.opening-preview-language')).to_contain_text('Englischer Originaltext')
                    expect(preview.locator('.opening-preview-description')).to_have_text('Original card effect.\nA second effect paragraph.')
                    page.set_viewport_size({'width': 390, 'height': 844})
                    expect(preview.get_by_role('button', name='Kartenvorschau schließen')).to_be_in_viewport()
                    assert preview.evaluate('el => el.scrollWidth <= el.clientWidth'), 'Card preview mobile overflow'
                    preview.locator('.opening-preview-description').scroll_into_view_if_needed()
                    expect(preview.locator('.opening-preview-description')).to_be_in_viewport()
                    page.screenshot(path=str(ROOT / 'artifacts/opening-preview-mobile.png'), animations='disabled')
                    preview.get_by_role('button', name='Zurück zu deinen Karten').click()
                    expect(summary_cards.nth(1)).to_be_focused()
                    summary_cards.nth(2).click()
                    expect(preview.locator('.opening-preview-description')).to_have_text('Für diese Karte liegt noch kein Kartentext vor.')
                    expect(preview.locator('.opening-preview-language')).to_have_count(0)
                    preview.get_by_role('button', name='Kartenvorschau schließen').click()
                    expect(opening.locator('.opening-summary-grid .card-visual')).to_have_count(5)
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.unroute('**/api/boosters/1/open', opening_text_fixture)
                    opening.get_by_role("button", name="Zurück zum Hub", exact=True).click()
                    expect(opening).to_have_count(0)
                    expect(page.get_by_role("heading", name="Deine gezogenen Karten")).to_be_visible()
                    expect(page.locator(".result-cards .card-visual")).to_have_count(5)
                    expect(page.locator(".currency")).to_contain_text("2.350 Sammelpunkte")
                    page.get_by_role("link", name="Zur Sammlung", exact=True).click()
                    expect(page.locator(".inventory-summary")).to_contain_text("22")
                    expect(page.locator(".collection-grid .card-visual")).to_have_count(6)
                    page.locator('.variant-details').first.locator('summary').click()
                    expect(page.locator('.variant-details').first).to_contain_text('frei verfügbar')
                    page.get_by_role('button', name='Kartenbewegungen anzeigen', exact=True).click()
                    expect(page.locator('.inventory-movement').first).to_contain_text('Pack geöffnet')
                    page.screenshot(path=str(ROOT / 'artifacts/collection-variants-desktop.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Variant collection mobile overflow'
                    page.screenshot(path=str(ROOT / 'artifacts/collection-variants-mobile.png'), full_page=True)
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.get_by_role('button', name='Kartenbewegungen ausblenden', exact=True).click()
                    assert page.locator(".collection-grid").evaluate("e => getComputedStyle(e).gridTemplateColumns.split(' ').length") == 6, "Six desktop columns"
                    page.get_by_role("button", name="Typ / Unterart", exact=True).click()
                    page.get_by_role("button", name="Drache", exact=True).click()
                    expect(page.locator(".collection-grid .card-visual")).to_have_count(2)
                    page.get_by_role("button", name="Stufe / Rang", exact=True).click()
                    page.locator(".filter-chips").get_by_role("button", name="8", exact=True).click()
                    expect(page.locator(".collection-grid .card-visual")).to_have_count(1)
                    expect(page.locator(".collection-grid")).to_contain_text("Blauäugiger w. Drache")
                    with sqlite3.connect(Path(temporary) / 'browser.db') as db:
                        blue_eyes_drawn = db.execute('SELECT COUNT(*) FROM booster_opening_cards WHERE card_id=1').fetchone()[0] > 0
                    db.close()
                    expected_rarity = 'Ultraselten' if blue_eyes_drawn else 'Ausgabe nicht bestimmt'
                    expect(page.locator(".card-rarity-badge").first).to_have_attribute("aria-label", 'Seltenheit: ' + expected_rarity)
                    page.get_by_role("button", name="Alle Filter zurücksetzen", exact=True).click()
                    page.get_by_role("button", name="Filterauswahl schließen").click()
                    expect(page.locator(".collection-grid .card-visual")).to_have_count(6)
                    held_images = []
                    page.route("**/api/cards/*/art/de", lambda route: held_images.append(route))
                    page.reload()
                    expect(page.locator(".collection-grid .card-visual")).to_have_count(6)
                    expect(page.locator(".collection-grid .loading-card-caption").first).to_have_text("Karte wird geladen")
                    expect(page.locator(".collection-grid .card-visual").first).to_have_attribute("aria-busy", "true")
                    page.screenshot(path=str(ROOT / "artifacts/collection-loading-desktop.png"), animations="disabled")
                    page.unroute("**/api/cards/*/art/de")
                    for route in held_images:
                        route.continue_()
                    expect(page.locator(".collection-grid .card-loaded")).to_have_count(6, timeout=30000)
                    page.screenshot(path=str(ROOT / "artifacts/collection-german-desktop.png"), full_page=True, animations="disabled")
                    # Missing German images fall back once and disclose the original language.
                    page.route("**/api/cards/*/art/de", lambda route: route.fulfill(status=404))
                    page.route("**/api/cards/*/art/original", lambda route: route.fulfill(content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg" width="199" height="290"><rect width="199" height="290" fill="#246b65"/></svg>'))
                    page.reload()
                    expect(page.locator(".collection-grid .image-language-label")).to_have_count(6)
                    expect(page.locator(".collection-grid .card-loaded")).to_have_count(6)
                    expect(page.locator(".collection-grid")).to_contain_text("Blauäugiger w. Drache")
                    page.unroute("**/api/cards/*/art/original")
                    page.route("**/api/cards/*/art/original", lambda route: route.fulfill(status=404))
                    page.reload()
                    expect(page.locator(".collection-grid .image-missing")).to_have_count(6)
                    expect(page.locator(".collection-grid .card-visual[aria-busy='true']")).to_have_count(0)
                    page.unroute("**/api/cards/*/art/de")
                    page.unroute("**/api/cards/*/art/original")
                    page.get_by_role("link", name="Konto & Sammelpunkte").click()
                    expect(page.locator(".wallet-row").filter(has_text="Booster-Kauf")).to_contain_text("-100 Sammelpunkte")
                    page.get_by_role("link", name="Kartenkatalog", exact=True).click()
                    page.get_by_role("textbox", name="Karten suchen").fill("Blue-Eyes")
                    expect(page.locator(".catalog-grid .card-visual")).to_have_count(1)
                    page.locator(".catalog-grid .card-link").first.click()
                    expect(page.get_by_role("heading", name="In diesen Boostern enthalten")).to_be_visible()
                    page.get_by_role("link", name="Enthaltene Karten ansehen").first.click()
                    expect(page.get_by_role("heading", name="Welche Karten kann ich ziehen?")).to_be_visible()
                    page.get_by_role("textbox", name="Karten in diesem Booster suchen").fill("Blauäugiger")
                    expect(page.locator(".pool-panel .card-visual")).to_have_count(1)
                    page.locator(".pool-panel .card-link").first.click()
                    expect(page.get_by_role("heading", name="Blauäugiger w. Drache", exact=True).first).to_be_visible()
                    page.get_by_role("link", name="Booster", exact=True).first.click()
                    page.get_by_role("checkbox", name="Nur meine ungeöffneten Packs").check()
                    expect(page.locator(".booster-tile")).to_have_count(1)
                    expect(page.locator(".stock-label")).to_contain_text("4 im Bestand")
                    page.get_by_role("textbox", name="Booster suchen").fill("not-a-real-pack")
                    expect(page.locator(".booster-tile")).to_have_count(0)
                    page.get_by_role("textbox", name="Booster suchen").fill("")
                    page.get_by_role("checkbox", name="Nur meine ungeöffneten Packs").uncheck()
                    expect(page.locator(".booster-tile")).to_have_count(1)
                    # Image load failure must show the pack's identity, never a different pack's cover.
                    page.route("https://example.com/test-pack.svg", lambda route: route.abort())
                    page.reload()
                    expect(page.locator(".booster-cover-missing")).to_contain_text("Kein Cover verfügbar")
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Booster shop mobile horizontal overflow"
                    page.get_by_role("link", name="Enthaltene Karten ansehen").first.click()
                    expect(page.get_by_role("heading", name="Welche Karten kann ich ziehen?")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Booster detail mobile horizontal overflow"

                    page.get_by_role("button", name="Menü öffnen").click()
                    page.get_by_role("link", name="Meine Sammlung", exact=True).click()
                    expect(page.get_by_role("heading", name="Deine Karten", exact=True)).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile horizontal overflow"
                    screenshot_dir = ROOT / "artifacts"
                    screenshot_dir.mkdir(exist_ok=True)
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    page.screenshot(path=str(screenshot_dir / "inventory-mobile.png"), full_page=True, animations="disabled")
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    page.get_by_role("link", name="Übersicht", exact=True).click()
                    expect(page.get_by_role("link", name="Übersicht", exact=True)).to_have_attribute("aria-current", "page")
                    expect(page.locator(".stats-grid")).to_contain_text("22")
                    page.screenshot(path=str(screenshot_dir / "overview-desktop.png"), full_page=True, animations="disabled")
                    page.get_by_role("button", name="Abmelden", exact=True).click()
                    expect(page.get_by_role("button", name="Lokale Demo öffnen")).to_be_visible()
                    # Simulate only Streamer.bot's trusted HTTP event; no Twitch messages are sent.
                    invitation = httpx.post(api_url + "/api/integrations/streamerbot/redemptions", headers={"X-Streamerbot-Key": env["STREAMERBOT_API_KEY"]}, json={
                        "user_id": "123456", "username": "browserviewer", "display_name": "BrowserViewer", "broadcaster_login": "SamDavidOfficial",
                        "redemption_id": "browser-redemption", "reward_id": "browser-reward", "reward_cost": 1000, "status": "fulfilled",
                    }).json()
                    assert invitation["diamonds"] == 100
                    page.goto(invitation["registration_url"])
                    expect(page.get_by_label("Twitch-Benutzername")).to_have_value("browserviewer")
                    expect(page.get_by_label("Twitch-Benutzername")).to_have_attribute("readonly", "")
                    page.get_by_role("button", name="Bestätigungscode erstellen").click()
                    expect(page.get_by_test_id("confirmation-command")).to_be_visible()
                    command = page.get_by_test_id("confirmation-command").inner_text()
                    expect(page.get_by_label("Neues Passwort", exact=True)).to_have_count(0)
                    page.reload()
                    expect(page.get_by_test_id("confirmation-command")).to_have_text(command)
                    confirmation = httpx.post(api_url + "/api/integrations/streamerbot/confirm", headers={"X-Streamerbot-Key": env["STREAMERBOT_API_KEY"]}, json={
                        "user_id": "123456", "username": "browserviewer", "display_name": "BrowserViewer", "broadcaster_login": "SamDavidOfficial", "code": command.split()[1],
                    })
                    assert confirmation.status_code == 200, confirmation.text
                    expect(page.get_by_label("Neues Passwort", exact=True)).to_be_visible(timeout=10000)
                    page.get_by_label("Neues Passwort", exact=True).fill("Browser-Test-Passwort-123!")
                    page.get_by_label("Passwort wiederholen", exact=True).fill("Browser-Test-Passwort-123!")
                    page.get_by_role("button", name="Passwort festlegen & starten").click()
                    expect(page.get_by_role("heading", name="Willkommen, BrowserViewer.")).to_be_visible()
                    expect(page.locator(".currency")).to_contain_text("100 Sammelpunkte")
                    page.get_by_role("link", name="Booster", exact=True).first.click()
                    page.get_by_role("link", name="Enthaltene Karten ansehen").first.click()
                    page.get_by_role("button", name="Kaufen", exact=True).first.click()
                    expect(page.locator(".currency")).to_contain_text("0 Sammelpunkte")
                    expect(page.get_by_role("complementary", name="Kaufbestätigung")).to_contain_text("1 Pack")
                    page.get_by_role("button", name="Weiter stöbern", exact=True).click()
                    expect(page.get_by_role("complementary", name="Kaufbestätigung")).to_have_count(0)
                    page.emulate_media(reduced_motion="reduce")
                    page.get_by_role("button", name="Kostenlos öffnen", exact=True).click()
                    opening = page.get_by_role("dialog")
                    expect(opening.get_by_role("button", name="Karte 1 aufdecken", exact=True)).to_be_visible()
                    opening.get_by_role("button", name="Animation überspringen").click()
                    expect(opening.locator(".opening-summary-grid .card-visual")).to_have_count(5)
                    opening.get_by_role("button", name="Zurück zum Hub", exact=True).click()
                    page.emulate_media(reduced_motion="no-preference")
                    expect(page.locator(".result-cards .card-visual")).to_have_count(5)
                    page.get_by_role("link", name="Zur Sammlung", exact=True).click()
                    expect(page.locator(".inventory-summary strong").first).to_have_text("5")
                    page.get_by_role("button", name="Abmelden", exact=True).click()
                    page.get_by_label("Twitch-Benutzername").fill("browserviewer")
                    page.get_by_label("Passwort", exact=True).fill("Browser-Test-Passwort-123!")
                    page.get_by_role("button", name="Anmelden", exact=True).click()
                    expect(page.locator(".profile-copy strong")).to_have_text("BrowserViewer")
                    page.get_by_role("link", name="Übersicht", exact=True).click()
                    expect(page.get_by_role("heading", name="Willkommen, BrowserViewer.")).to_be_visible()
                    expect(page.locator(".currency")).to_contain_text("0 Sammelpunkte")
                    expect(page.locator(".stats-grid")).to_contain_text("5")
                    page.locator('.main-nav a[href="#/my-packs"]').click()
                    expect(page.locator(".vault-stack")).to_have_count(0)
                    expect(page.get_by_role("heading", name="Hier beginnt deine nächste Öffnung.")).to_be_visible()
                    # The pack vault groups owned packs; an opening consumes exactly one,
                    # even when the presentation is closed before every reveal.
                    page.get_by_role("button", name="Abmelden", exact=True).click()
                    page.get_by_role("button", name="Lokale Demo öffnen").click()
                    page.locator('.main-nav a[href="#/my-packs"]').click()
                    expect(page.get_by_role("heading", name="Meine Packs", exact=True)).to_be_visible()
                    expect(page.locator(".vault-quantity")).to_contain_text("×4")
                    page.screenshot(path=str(ROOT / "artifacts/pack-vault-desktop.png"), full_page=True, animations="disabled")
                    page.route("**/api/boosters/1/open", lambda route: route.fulfill(status=400, content_type="application/json", body='{"detail":"Test: Opening abgelehnt"}'))
                    page.get_by_role("button", name="Pack öffnen", exact=True).click()
                    expect(page.get_by_role("dialog").get_by_role("alert")).to_contain_text("Opening abgelehnt")
                    page.get_by_role("dialog").get_by_role("button", name="Zurück zum Hub").click()
                    expect(page.locator(".vault-quantity")).to_contain_text("×4")
                    page.unroute("**/api/boosters/1/open")
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Vault mobile overflow"
                    page.screenshot(path=str(ROOT / "artifacts/pack-vault-mobile.png"), full_page=True, animations="disabled")
                    page.get_by_role("button", name="Pack öffnen", exact=True).click()
                    opening = page.get_by_role("dialog")
                    expect(opening.get_by_role("button", name="Animation überspringen")).to_be_enabled()
                    page.screenshot(path=str(ROOT / "artifacts/opening-pack-mobile.png"))
                    expect(opening.get_by_role("button", name="Karte 1 aufdecken", exact=True)).to_be_visible(timeout=10000)
                    assert opening.evaluate("e => e.scrollWidth <= e.clientWidth"), "Opening mobile overflow"
                    opening.get_by_role("button", name="Karte 1 aufdecken", exact=True).click()
                    page.screenshot(path=str(ROOT / "artifacts/opening-reveal-mobile.png"), animations="disabled")
                    page.keyboard.press("Escape")
                    expect(opening).to_have_count(0)
                    expect(page.locator(".vault-quantity")).to_contain_text("×3")
                    page.reload()
                    expect(page.locator(".vault-quantity")).to_contain_text("×3")
                    page.get_by_role("button", name="Menü öffnen").click()
                    page.get_by_role("link", name="Meine Sammlung", exact=True).click()
                    expect(page.locator(".inventory-summary strong").first).to_have_text("27")
                    # Isolated database only: a three-card pool must show and grant three.
                    with sqlite3.connect(Path(temporary) / 'browser.db') as db:
                        db.execute('DELETE FROM booster_pool_entries WHERE booster_id = 1 AND card_id NOT IN (SELECT card_id FROM booster_pool_entries WHERE booster_id = 1 ORDER BY card_id LIMIT 3)')
                    db.close()
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    page.goto(ui_url + '/#/my-packs')
                    page.reload()
                    expect(page.locator('.vault-stack-copy .eyebrow')).to_contain_text('3 KARTEN PRO PACK')
                    expect(page.locator('.vault-stack-copy')).to_contain_text('9 Karten warten')
                    page.get_by_role('button', name='Pack öffnen', exact=True).click()
                    page.get_by_role('dialog').get_by_role('button', name='Animation überspringen').click()
                    expect(page.locator('.opening-summary-grid .card-visual')).to_have_count(3)
                    page.get_by_role('dialog').get_by_role('button', name='Zurück zum Hub', exact=True).click()
                    page.get_by_role('link', name='Meine Sammlung', exact=True).click()
                    expect(page.locator('.inventory-summary strong').first).to_have_text('30')
                    # Fixed deck, purchase cap, and a long opening on mobile (isolated data).
                    with sqlite3.connect(Path(temporary) / 'browser.db') as db:
                        db.execute("INSERT INTO booster_packs (id,key,name,cards_per_pack,product_type,cost,active) VALUES (2000,'structure-test','Structure Deck: Test',42,'structure_deck',600,1)")
                        db.execute("INSERT INTO structure_deck_definitions (booster_id,source,content_hash,card_count) VALUES (2000,'browser fixture','test',42)")
                        db.execute("INSERT INTO structure_deck_items (booster_id,card_id,rarity,quantity) VALUES (2000,1,'rare',3),(2000,2,'common',39)")
                    db.close()
                    page.goto(ui_url + '/#/boosters/2000')
                    page.reload()
                    expect(page.get_by_role('heading', name='42 garantierte Karten für 600 Punkte')).to_be_visible()
                    expect(page.locator('.pool-panel')).to_contain_text('3 × garantiert enthalten')
                    for remaining in [2, 1, 0]:
                        page.get_by_role('button', name='Kaufen', exact=True).click()
                        expect(page.locator('.purchase-feedback')).to_contain_text('600 Sammelpunkte')
                        page.get_by_role('button', name='Weiter stöbern').click()
                        expect(page.locator('.product-limit')).to_contain_text('Kauflimit erreicht' if remaining == 0 else f'Noch {remaining} von 3')
                    expect(page.get_by_role('button', name='Limit erreicht')).to_be_disabled()
                    page.screenshot(path=str(ROOT / 'artifacts/structure-deck-limit.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.get_by_role('button', name='Kostenlos öffnen', exact=True).click()
                    opening = page.get_by_role('dialog')
                    opening.get_by_role('button', name='Animation überspringen').click()
                    expect(opening.locator('.opening-summary-grid .card-visual')).to_have_count(42)
                    assert opening.evaluate('e => e.scrollWidth <= e.clientWidth'), 'Structure opening mobile overflow'
                    opening.get_by_role('button', name='Zurück zum Hub', exact=True).click()
                    page.reload()
                    expect(page.get_by_role('button', name='Limit erreicht')).to_be_disabled()
                    expect(page.locator('.booster-detail-copy')).to_contain_text('2 ungeöffnete Packs')
                    # Bonus choices stay separate from the guaranteed list.
                    with sqlite3.connect(Path(temporary) / 'browser.db') as db:
                        db.execute("UPDATE structure_deck_definitions SET card_count=43, notes='42 feste Karten plus eine Bonuskarte im Hub.' WHERE booster_id=2000")
                        db.execute("INSERT INTO structure_deck_bonus_slots (id,booster_id,name) VALUES (1,2000,'Eine zusätzliche Secret-Rare-Karte')")
                        db.execute("INSERT INTO structure_deck_bonus_choices (slot_id,card_id,rarity) VALUES (1,1,'secret_rare'),(1,2,'secret_rare')")
                    db.close()
                    page.reload()
                    expect(page.get_by_role('heading', name='43 Karten inklusive Bonus für 600 Punkte')).to_be_visible()
                    expect(page.get_by_label('Bonusauswahl').locator('.card-visual')).to_have_count(2)
                    expect(page.get_by_label('Bonusauswahl')).to_contain_text('50% Bonuschance im Hub · nicht garantiert')
                    expect(page.get_by_role('heading', name='Garantierter Deckinhalt')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Bonus choices mobile overflow'
                    page.screenshot(path=str(ROOT / 'artifacts/bonus-deck-mobile.png'), full_page=True)
                    page.get_by_role('button', name='Kostenlos öffnen', exact=True).click()
                    opening = page.get_by_role('dialog')
                    opening.get_by_role('button', name='Animation überspringen').click()
                    expect(opening.locator('.opening-summary-grid .card-visual')).to_have_count(43)
                    expect(opening.locator('.summary-card.rarity-prismatic')).to_have_count(1)
                    opening.get_by_role('button', name='Zurück zum Hub', exact=True).click()
                    page.goto(ui_url + '/#/')
                    expect(page.locator('.hub-brand-banner')).to_be_visible()
                    page.wait_for_function("document.querySelector('.hub-brand-banner').naturalWidth > 0")
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Brand mobile overflow'
                    page.screenshot(path=str(ROOT / 'artifacts/sdoycc-banner-mobile.png'), full_page=True)
                    from admin_browser_checks import check_admin
                    check_admin(page, ui_url, Path(temporary) / 'browser.db', ROOT / 'artifacts')
                    from workflow_browser_checks import check_workflows
                    check_workflows(page, ui_url, api_url, Path(temporary) / "browser.db", ROOT / "artifacts")
                    assert not errors, errors
                    browser.close()
                    print(json.dumps({"browser": "passed", "checks": ["revealed card preview and exact text", "preview keyboard and Escape preserve opening", "summary preview and text fallbacks", "preview mobile layout", "community card image upload and publication", "resumable batch grant", "original-linked correction", "two-account reserved trade and receipt", "season planning and publication", "opening XP and reward claim", "workflow mobile layout", "mixed admin grant preview and submission", "stored grant receipt", "recipient notification and read state", "grant mobile layout", "collection variant quantities", "personal and admin inventory journal", "variant mobile layout", "admin login reset preserves assets", "admin block and unblock", "admin confirmation dialog and audit", "admin sidebar mobile navigation", "admin role access and revocation", "admin search and account details", "admin desktop and mobile layout", "bonus card separated from guaranteed content", "43-card opening with exactly one bonus", "bonus mobile layout", "pack vault", "empty vault", "animated reveal", "rarity spotlight matches result", "keyboard reveal", "reduced motion", "skip animation", "close preserves cards", "failed opening preserves stock", "demo", "purchase", "purchase receipt", "no success receipt on failed purchase", "receipt mobile", "open from receipt", "free opening", "inventory", "wallet", "catalog search", "card-to-booster navigation", "pool search", "actual cover", "cover failure fallback", "owned filter", "mobile", "logout", "public registration link", "chat confirmation", "reload preserves browser challenge", "locked username", "password registration", "precredited balance", "password login"], "console_errors": errors}))
            except Exception:
                log.flush()
                print((Path(temporary) / "servers.log").read_text(encoding="utf8"))
                raise
            finally:
                for process in [frontend, backend]:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
                    else:
                        process.terminate()
                    process.wait(timeout=15)


if __name__ == "__main__":
    run()
