"""Interactive acceptance against browser_smoke's disposable database only."""
import hashlib
import io
import secrets
import sqlite3
from datetime import datetime, timedelta
from PIL import Image
from playwright.sync_api import expect


def check_workflows(page, ui_url, api_url, database_path, artifacts):
    db = sqlite3.connect(database_path)
    tokens = {uid: secrets.token_urlsafe(32) for uid in [1001, 1002]}
    root_token = page.evaluate('sessionStorage.getItem("hub-session")')
    root_id, password_hash = db.execute('SELECT users.id,users.password_hash FROM users JOIN auth_sessions ON auth_sessions.user_id=users.id WHERE token_hash=?', (hashlib.sha256(root_token.encode()).hexdigest(),)).fetchone()
    db.execute("UPDATE users SET role='super_admin' WHERE id=?", (root_id,))
    variant_id = db.execute("SELECT id FROM card_variants WHERE card_id=1 AND legacy=0 LIMIT 1").fetchone()[0]
    for uid in tokens:
        db.execute("INSERT INTO users(id,username,display_name,role,is_active,credits,twitch_id,password_hash,created_at) VALUES(?,?,?,'user',1,500,?,?,?)", (uid, f'handel{uid}', f'Handel {uid}', str(uid), password_hash, datetime.utcnow()))
        db.execute('INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES(?,?,?)', (hashlib.sha256(tokens[uid].encode()).hexdigest(), uid, datetime.utcnow()+timedelta(hours=1)))
        db.execute('INSERT INTO inventory_items(user_id,card_id,quantity) VALUES(?,1,10)',(uid,))
        db.execute('INSERT INTO variant_inventory(user_id,variant_id,quantity,reserved,bound) VALUES(?,?,10,0,0)',(uid,variant_id))
        db.execute("INSERT INTO inventory_transactions(user_id,variant_id,bound,amount,balance_after,reason,reference,created_at) VALUES(?,?,0,10,10,'fixture',?,?)",(uid,variant_id,f'browser-fixture:{uid}',datetime.utcnow()))
        db.execute('INSERT INTO user_boosters(user_id,booster_id,quantity) VALUES(?,1,5)',(uid,))
    db.commit(); db.close()
    def login(token, path):
        page.evaluate('(token) => sessionStorage.setItem("hub-session", token)',token)
        page.goto(ui_url+'/#'+path);page.reload()
    def confirm(admin=False):
        dialog = page.get_by_role('dialog')
        expect(dialog).to_be_visible()
        if admin:
            dialog.get_by_label('Begründung',exact=True).fill('Browserprüfung mit isolierten Testkonten')
            dialog.get_by_label('Dein Administrator-Passwort').fill('Browser-Test-Passwort-123!')
        dialog.get_by_role('button',name='Verbindlich bestätigen',exact=True).click()
        expect(dialog).to_have_count(0)
    def fits(): assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Workflow overflows mobile viewport'
    login(root_token,'/admin/advanced')
    page.set_viewport_size({'width':1440,'height':1000})
    expect(page.get_by_role('heading',name='Aktionen & Inhalte')).to_be_visible()
    page.get_by_label('Name',exact=True).fill('Stern der Community')
    page.get_by_label('Edition',exact=True).fill('Browser-Testedition')
    page.get_by_label('Kartentext',exact=True).fill('Eine besondere Karte für unsere Community.')
    data=io.BytesIO();Image.new('RGB',(200,290),'#7c234c').save(data,format='PNG')
    page.get_by_label('Kartenbild · PNG, JPEG oder WebP bis 4 MB').set_input_files({'name':'testkarte.png','mimeType':'image/png','buffer':data.getvalue()})
    page.get_by_role('button',name='Entwurf prüfen',exact=True).click();confirm(True)
    page.get_by_role('button',name='Veröffentlichen',exact=True).click();confirm(True)
    expect(page.get_by_text('Aktiv · 0 / ∞ vergeben',exact=True)).to_be_visible()
    page.set_viewport_size({'width':390,'height':844});fits()
    page.screenshot(path=str(artifacts/'final-special-card-mobile.png'),full_page=True)
    page.get_by_role('button',name='Sammelvergaben',exact=True).click()
    for uid in tokens:
        page.get_by_label('Empfänger auswählen').fill(f'handel{uid}')
        page.get_by_role('button',name=f'Handel {uid}',exact=True).click()
    page.get_by_role('button',name='Position hinzufügen',exact=True).click()
    page.get_by_label('Grund der Belohnung (sichtbar für Empfänger)').fill('Danke für eure Teilnahme am Testevent')
    page.get_by_role('button',name='Alle Empfänger prüfen',exact=True).click()
    expect(page.get_by_role('heading',name='Vorschau · 2 Empfänger')).to_be_visible()
    page.get_by_role('button',name='Sammelvergabe anlegen',exact=True).click();confirm(True)
    page.get_by_label('Dein Administrator-Passwort',exact=True).fill('Browser-Test-Passwort-123!')
    page.get_by_role('button',name='Offene / abgelehnte Zeilen ausführen',exact=True).click()
    expect(page.get_by_text('handel1001:').locator('..')).to_contain_text('Ausgeführt')
    expect(page.get_by_text('handel1002:').locator('..')).to_contain_text('Ausgeführt')
    fits();page.screenshot(path=str(artifacts/'final-batch-mobile.png'),full_page=True)
    page.get_by_role('button',name='Korrekturen',exact=True).click()
    page.get_by_label('Zielkonto',exact=True).fill('handel1001')
    page.get_by_role('button',name='Handel 1001',exact=True).click()
    page.get_by_label('Positive Originalbuchung').select_option(index=1)
    page.get_by_label('Zurückzunehmende Menge').fill('25')
    page.get_by_label('Zielbenutzernamen exakt bestätigen').fill('handel1001')
    page.get_by_label('Grund',exact=True).fill('Doppelte Teilnahme im Testevent korrigieren')
    page.get_by_role('button',name='Korrektur vorschauen',exact=True).click()
    expect(page.get_by_role('heading',name='Bestand: 600 → 575')).to_be_visible()
    page.get_by_role('button',name='Korrektur bestätigen',exact=True).click();confirm(True)
    # Two distinct browsers/accounts give their explicit package confirmations.
    login(tokens[1001],'/trade')
    page.get_by_role('button',name='Anzeige erstellen',exact=True).click()
    page.get_by_label('Titel',exact=True).fill('Mein erstes Kartenpaket')
    page.get_by_label('Beschreibung',exact=True).fill('Zwei Exemplare gegen ein passendes Angebot.')
    page.get_by_label('Menge im Paket').first.fill('2')
    page.get_by_role('button',name='Entwurf prüfen',exact=True).click();confirm()
    expect(page.get_by_role('heading',name='Mein erstes Kartenpaket')).to_be_visible()
    listing_url=page.url
    page.get_by_role('button',name='Veröffentlichen',exact=True).click();confirm()
    fits();page.screenshot(path=str(artifacts/'final-trade-listing-mobile.png'),full_page=True)
    login(tokens[1002],listing_url.split('#')[1])
    page.get_by_label('Menge im Paket').first.fill('1')
    page.get_by_role('button',name='Angebot prüfen',exact=True).click();confirm()
    login(tokens[1001],listing_url.split('#')[1])
    page.get_by_role('button',name='Annehmen',exact=True).click()
    expect(page.get_by_role('dialog')).to_contain_text('Du erhältst')
    fits();page.screenshot(path=str(artifacts/'final-trade-confirmation-mobile.png'),full_page=True)
    confirm()
    expect(page.get_by_text('Abgeschlossen · Version 1',exact=True)).to_be_visible()
    page.get_by_role('button',name='Tauschbelege',exact=True).click()
    page.locator('.content-panel details summary').first.click()
    expect(page.get_by_role('heading',name='Handel 1001 gab')).to_be_visible()
    fits();page.screenshot(path=str(artifacts/'final-trade-receipt-mobile.png'),full_page=True)
    # The admin creates and publishes a disposable test season through the UI.
    login(root_token,'/admin/advanced')
    page.get_by_role('button',name='Saisons',exact=True).click()
    page.get_by_label('Saisonname').fill('Community-Testreise')
    dates=page.evaluate('''() => [2, 1440, 2880].map(minutes => { const d=new Date(Date.now()+minutes*60000); d.setMinutes(d.getMinutes()-d.getTimezoneOffset()); return d.toISOString().slice(0,16); })''')
    for label,value in zip(['Start','Ende des XP-Sammelns','Abholfrist'],dates):page.get_by_label(label,exact=True).fill(value)
    page.get_by_label('XP-Schwelle der nächsten Stufe').fill('10')
    page.get_by_role('button',name='Position hinzufügen',exact=True).click()
    page.get_by_role('button',name='Stufe hinzufügen',exact=True).click()
    page.get_by_role('button',name='Regeln und Belohnungsbudget prüfen',exact=True).click()
    expect(page.get_by_role('heading',name='Budget je vollständig abgeschlossenem Pass')).to_be_visible()
    page.get_by_role('button',name='Entwurf speichern',exact=True).click();confirm(True)
    page.get_by_role('button',name='Veröffentlichen',exact=True).click();confirm(True)
    db=sqlite3.connect(database_path)
    db.execute("UPDATE seasons SET starts_at=? WHERE name='Community-Testreise'",(datetime.utcnow()-timedelta(seconds=5),));db.commit();db.close()
    # A real test opening creates XP through the same API used by the pack animation.
    result=page.request.post(api_url+'/api/boosters/1/open',headers={'Authorization':'Bearer '+tokens[1001],'Idempotency-Key':'browser-season-opening'})
    assert result.status==200,result.text()
    login(tokens[1001],'/battle-pass')
    expect(page.get_by_role('heading',name='Stufe 1 · 10 XP')).to_be_visible()
    fits();page.screenshot(path=str(artifacts/'final-season-mobile.png'),full_page=True)
    page.get_by_role('button',name='Belohnung abholen',exact=True).click();confirm()
    expect(page.get_by_role('heading',name='Belohnung erhalten',exact=False)).to_be_visible()
    expect(page.locator('.currency')).to_contain_text('675 Sammelpunkte')
    fits();page.screenshot(path=str(artifacts/'final-season-reward-mobile.png'),full_page=True)
    db=sqlite3.connect(database_path)
    assert db.execute('SELECT COUNT(*) FROM trade_settlements').fetchone()[0]==1
    assert db.execute('SELECT COUNT(*) FROM season_claims').fetchone()[0]==1
    assert db.execute('SELECT SUM(reserved) FROM variant_inventory').fetchone()[0]==0
    assert db.execute('SELECT credits FROM users WHERE id=1001').fetchone()[0]==675
    db.close()
