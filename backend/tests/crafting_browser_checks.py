"""Real React + real API crafting checks, isolated stock/accounts/database only."""
import json
import os
import subprocess
import threading
import time

import httpx
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import select

from browser_smoke import ROOT, free_port, wait_ready
from test_crafting import CraftingTests
from app.main import app
from app.db.models import AdminAuditEvent, InventoryItem, InventoryReservation, PlayerDeck, SeasonProgress, VariantInventory


def run():
    CraftingTests.setUpClass()
    fixture = CraftingTests()
    fixture.setUp()
    api_port, ui_port = free_port(), free_port()
    api_url, ui_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{ui_port}'
    app.add_middleware(CORSMiddleware, allow_origins=[ui_url], allow_methods=['*'], allow_headers=['*'])
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=api_port, lifespan='off', log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    env = {**os.environ, 'VITE_API_BASE_URL':api_url+'/api', 'VITE_BASE_PATH':'/'}
    node = os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe')
    try:
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                if httpx.get(api_url+'/api/health',timeout=1).status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(.1)
        with (ROOT/'artifacts/crafting-browser-vite.log').open('w',encoding='utf-8') as log:
            frontend=subprocess.Popen([node,str(ROOT/'node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(ui_port),'--strictPort'],cwd=ROOT/'frontend',env=env,stdout=log,stderr=log,creationflags=flags)
            try:
                wait_ready(ui_url,frontend)
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(channel=os.environ.get('BROWSER_CHANNEL','msedge'),headless=True)
                    page=browser.new_page(viewport={'width':1440,'height':1000})
                    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    page.add_init_script(f"sessionStorage.setItem('hub-session',{json.dumps(fixture.tokens[3]['Authorization'][7:])})")
                    page.route('**/api/cards/*/art/original',lambda route:route.fulfill(content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="160" height="232"><rect width="160" height="232" fill="#286474"/><text x="12" y="110" fill="white">Testkarte</text></svg>'))
                    page.goto(ui_url+'/#/crafting?tab=dismantle')
                    expect(page.get_by_role('heading',name='Crafting',exact=True)).to_be_visible()
                    card=page.locator('[data-printing-id="1"]')
                    expect(card).to_contain_text('Im Besitz: 10')
                    card.get_by_role('button',name='Zerlegen',exact=True).click()
                    dialog=page.get_by_role('dialog')
                    dialog.get_by_label('Menge',exact=True).fill('3')
                    expect(dialog.locator('.craft-quote')).to_contain_text('60 → 90')
                    dialog.get_by_role('button',name='Karten zerlegen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    expect(card).to_contain_text('Im Besitz: 7')
                    page.locator('.craft-tabs').get_by_role('button',name='Herstellen',exact=True).click()
                    target=page.locator('[data-printing-id="2"]')
                    target.get_by_role('button',name='Herstellen',exact=True).click()
                    expect(dialog.locator('.craft-quote')).to_contain_text('90 → 60')
                    dialog.get_by_role('button',name='Karten herstellen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    expect(target).to_contain_text('Im Besitz: 1')
                    page.locator('[data-printing-id="3"]').get_by_role('button',name='Herstellen',exact=True).click()
                    dialog.get_by_label('Menge',exact=True).fill('3')
                    expect(dialog.get_by_role('alert')).to_contain_text('Nicht genügend')
                    expect(dialog.get_by_role('button',name='Karten herstellen',exact=True)).to_be_disabled()
                    dialog.get_by_role('button',name='Abbrechen',exact=True).click()
                    page.locator('.craft-tabs').get_by_role('button',name='Zerlegen',exact=True).click()
                    card.get_by_role('button',name='Zerlegen',exact=True).click()
                    dialog.locator('summary').filter(has_text='Kartenschutz').click()
                    dialog.get_by_label('Geschützte ungebundene Exemplare').fill('5')
                    dialog.get_by_label('Favorit',exact=True).check()
                    dialog.get_by_role('button',name='Schutz speichern',exact=True).click()
                    expect(dialog).to_have_count(0)
                    expect(card).to_contain_text('zerlegbar: 2')
                    with fixture.sessions() as db:
                        stock=db.scalar(select(VariantInventory).where(VariantInventory.user_id==3,VariantInventory.variant_id==fixture.vid))
                        stock.reserved=2;db.add(InventoryReservation(user_id=3,variant_id=fixture.vid,quantity=2,reference='browser-trade',active=True));db.commit()
                    page.reload();expect(card).to_contain_text('zerlegbar: 0')
                    expect(card.get_by_role('button',name='Keine freien Exemplare',exact=True)).to_be_disabled()
                    card.get_by_role('button',name='Test · Ausgabe prüfen',exact=True).click()
                    dialog.locator('summary').filter(has_text='Kartenschutz').click()
                    dialog.get_by_label('Geschützte ungebundene Exemplare').fill('0')
                    dialog.get_by_role('button',name='Schutz speichern',exact=True).click()
                    expect(dialog).to_have_count(0)
                    page.get_by_role('button',name='Duplikate gesammelt prüfen',exact=True).click()
                    expect(dialog).to_contain_text('2 Karten aus 1 Ausgaben')
                    expect(dialog).to_contain_text('+20 rare cp')
                    dialog.get_by_role('button',name='Duplikate zerlegen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    expect(card).to_contain_text('Im Besitz: 5')
                    page.screenshot(path=str(ROOT/'artifacts/crafting-desktop.png'),full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    page.wait_for_timeout(350)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.screenshot(path=str(ROOT/'artifacts/crafting-mobile.png'),full_page=True)
                    page.set_viewport_size({'width':1440,'height':1000})
                    # Same server and wallet, now directly inside a real deck draft.
                    with fixture.sessions() as db:
                        db.add(PlayerDeck(id='cfa10000-0000-4000-8000-000000000001',user_id=3,name='Crafting im Deck',entries_json=json.dumps([{'card_id':2,'section':'main','quantity':1}])))
                        db.commit()
                    page.goto(ui_url+'/#/decks/cfa10000-0000-4000-8000-000000000001')
                    page.get_by_role('button',name='Zielkarte ansehen',exact=True).first.click()
                    workshop=page.get_by_role('region',name='Kartenwerkstatt im Deckeditor')
                    workshop.get_by_label('Ausgabe / Rarität',exact=True).select_option('2')
                    expect(workshop.locator('[data-currency="rare_cp"]')).to_be_visible()
                    expect(workshop).to_contain_text('1× diese Ausgabe')
                    workshop.get_by_role('button').filter(has_text='Herstellen').click()
                    expect(dialog.locator('.craft-quote')).to_contain_text('80 → 50')
                    dialog.get_by_role('button',name='Karten herstellen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    expect(workshop).to_contain_text('2× diese Ausgabe')
                    expect(page.locator('.deck-inspector-budget')).to_contain_text('Besessen 2')
                    workshop.get_by_role('button').filter(has_text='Zerlegen').click()
                    expect(dialog.locator('.craft-quote')).to_contain_text('50 → 60')
                    dialog.get_by_role('button',name='Karten zerlegen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    expect(workshop).to_contain_text('1× diese Ausgabe')
                    expect(workshop.get_by_role('button').filter(has_text='Zerlegen')).to_be_disabled()
                    workshop.get_by_label('Ausgabe / Rarität',exact=True).select_option('3')
                    expect(workshop.locator('[data-currency="ultra_rare_cp"]')).to_be_visible()
                    expect(workshop.get_by_role('button').filter(has_text='Zerlegen')).to_be_disabled()
                    page.screenshot(path=str(ROOT/'artifacts/deck-crafting-desktop.png'),full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    page.wait_for_timeout(350)
                    page.locator('.deck-mobile-tabs').get_by_role('button',name='Karte',exact=True).click()
                    expect(workshop).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.screenshot(path=str(ROOT/'artifacts/deck-crafting-mobile.png'),full_page=True)
                    with fixture.sessions() as db:
                        deck=db.get(PlayerDeck,'cfa10000-0000-4000-8000-000000000001')
                        assert json.loads(deck.entries_json)==[{'card_id':2,'section':'main','quantity':1}]
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.evaluate('(token)=>{sessionStorage.setItem("hub-session",token);window.dispatchEvent(new Event("hub-session-changed"));location.hash="/admin/crafting"}',fixture.tokens[2]['Authorization'][7:])
                    page.get_by_role('button',name='Raritätsregeln',exact=True).click()
                    rule=page.locator('details.content-panel').filter(has=page.locator('summary').filter(has_text='Rare · rare_cp'))
                    rule.locator('summary').click()
                    rule.get_by_label('CP-Kosten beim Herstellen').fill('35')
                    rule.get_by_role('button',name='Änderung prüfen',exact=True).click()
                    dialog.get_by_label('Begründung',exact=True).fill('Browser-Test Regelanpassung')
                    dialog.get_by_label('Dein Administrator-Passwort').fill(fixture.password)
                    dialog.get_by_role('button',name='Verbindlich bestätigen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    expect(page.locator('details.content-panel').filter(has_text='Rare · rare_cp').first).to_contain_text('10 / 35 CP')
                    page.get_by_role('button',name='Spielerguthaben',exact=True).click()
                    page.get_by_label('Spielerkonto suchen').fill('craft3')
                    page.get_by_role('button',name='Craft 3',exact=True).click()
                    page.get_by_label('Währung',exact=True).select_option('rare_cp')
                    page.get_by_label('Änderung (+ / −)').fill('10')
                    page.get_by_role('button',name='Korrektur prüfen',exact=True).click()
                    dialog.get_by_label('Begründung',exact=True).fill('Browser-Test Kontokorrektur')
                    dialog.get_by_label('Dein Administrator-Passwort').fill(fixture.password)
                    dialog.get_by_role('button',name='Verbindlich bestätigen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    page.get_by_role('button',name='Einstellungen',exact=True).click()
                    page.get_by_label('Herstellen aktiv',exact=True).uncheck()
                    page.get_by_role('button',name='Einstellungen prüfen',exact=True).click()
                    dialog.get_by_label('Begründung',exact=True).fill('Browser-Test Betriebsschalter')
                    dialog.get_by_label('Dein Administrator-Passwort').fill(fixture.password)
                    dialog.get_by_role('button',name='Verbindlich bestätigen',exact=True).click()
                    expect(dialog).to_have_count(0)
                    page.screenshot(path=str(ROOT/'artifacts/crafting-admin.png'),full_page=True)
                    assert not errors,errors
                    with fixture.sessions() as db:
                        assert db.scalar(select(InventoryItem.quantity).where(InventoryItem.user_id==3,InventoryItem.card_id==1))==5
                        assert db.scalar(select(InventoryItem.quantity).where(InventoryItem.user_id==3,InventoryItem.card_id==2))==1
                        assert not db.scalars(select(SeasonProgress)).all()
                        assert len(db.scalars(select(AdminAuditEvent)).all())==3
                    browser.close()
                    print(json.dumps({'real_api_craft_dismantle_bulk_protection':'passed','trade_locks_and_disabled_choices':'passed','deck_editor_craft_dismantle_stock_refresh':'passed','printing_currency_icons_and_unchanged_deck':'passed','admin_rules_balance_and_settings':'passed','desktop_mobile_and_no_console_errors':'passed'}))
            finally:
                frontend.terminate();frontend.wait(timeout=10)
    finally:
        server.should_exit=True;thread.join(timeout=10);fixture.tearDown()


if __name__=='__main__': run()
