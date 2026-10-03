"""Called only with browser_smoke's isolated database and servers."""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta

from playwright.sync_api import expect


def check_admin(page, ui_url, database_path, artifacts):
    page.goto(ui_url + '/#/admin')
    expect(page.get_by_role('heading', name='Kein Zugriff')).to_be_visible()
    expect(page.get_by_role('link', name='Admin-Menü', exact=True)).to_have_count(0)
    token = secrets.token_urlsafe(32)
    db = sqlite3.connect(database_path)
    try:
        target_id = db.execute('SELECT id FROM users WHERE password_hash IS NOT NULL LIMIT 1').fetchone()[0]
        db.execute("UPDATE users SET role='super_admin' WHERE id=?", (target_id,))
        db.execute('INSERT INTO auth_sessions (token_hash,user_id,expires_at) VALUES (?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(), target_id, datetime.utcnow() + timedelta(hours=1)))
        db.commit()
    finally:
        db.close()
    page.evaluate('(token) => sessionStorage.setItem("hub-session", token)', token)
    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.reload()
    expect(page.get_by_role('heading', name='Deine Community im Blick')).to_be_visible()
    expect(page.get_by_role('link', name='Admin-Menü', exact=True)).to_be_visible()
    expect(page.locator('.admin-account-row')).to_have_count(2)
    page.screenshot(path=str(artifacts / 'admin-overview-desktop.png'), full_page=True)
    page.get_by_label('Name oder Twitch-ID').fill('jaden')
    page.get_by_role('button', name='Suchen', exact=True).click()
    expect(page.locator('.admin-account-row')).to_have_count(1)
    page.locator('.admin-account-row').click()
    expect(page.get_by_role('heading', name='Kontodetails')).to_be_visible()
    expect(page.locator('.admin-profile')).to_contain_text('jaden-demo')
    expect(page.locator('.admin-entry').first).to_contain_text('Punkte')
    page.get_by_role('button', name='Kartensammlung', exact=True).click()
    expect(page.locator('.admin-entry').first).to_contain_text('×')
    page.locator('.variant-details').first.locator('summary').click()
    expect(page.locator('.variant-details').first).to_contain_text('frei verfügbar')
    page.get_by_role('button', name='Kartenbewegungen', exact=True).click()
    expect(page.locator('.inventory-movement').first).to_contain_text('Pack geöffnet')
    page.get_by_role('button', name='Pack-Bestand', exact=True).click()
    expect(page.locator('.admin-entry').first).to_contain_text('×')
    page.set_viewport_size({'width': 390, 'height': 844})
    if page.locator('.sidebar.is-open').count():
        page.locator('.mobile-close').click()
    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Admin detail mobile overflow'
    page.screenshot(path=str(artifacts / 'admin-account-mobile.png'), full_page=True)
    page.get_by_role('link', name='Alle Konten', exact=True).click()
    expect(page.locator('.admin-account-row')).to_have_count(2)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Admin directory mobile overflow'
    page.screenshot(path=str(artifacts / 'admin-overview-mobile.png'), full_page=True)
    # A real password-backed account in this temporary database only.
    db = sqlite3.connect(database_path)
    try:
        password_hash = db.execute('SELECT password_hash FROM users WHERE id=?', (target_id,)).fetchone()[0]
        db.execute("INSERT INTO users(id,username,display_name,twitch_id,password_hash,role,is_active,credits,created_at) VALUES(900,'resettester','ResetTester','987501',?,'user',1,321,CURRENT_TIMESTAMP)", (password_hash,))
        db.execute('INSERT INTO inventory_items(user_id,card_id,quantity) VALUES(900,1,12)')
        db.execute('INSERT INTO user_boosters(user_id,booster_id,quantity) VALUES(900,1,2)')
        db.commit()
    finally:
        db.close()
    page.goto(ui_url + '/#/admin/users/900')
    expect(page.get_by_role('heading', name='ResetTester', exact=True)).to_be_visible()
    page.get_by_role('button', name='Anmeldung zurücksetzen', exact=True).click()
    dialog = page.get_by_role('dialog', name='Anmeldung zurücksetzen')
    expect(dialog).to_contain_text('Punkte, Karten, Packs, Kaufgrenzen und Historie bleiben erhalten')
    expect(dialog.get_by_role('button', name='Verbindlich ausführen')).to_be_disabled()
    page.keyboard.press('Escape')
    expect(dialog).to_have_count(0)
    page.get_by_role('button', name='Anmeldung zurücksetzen', exact=True).click()
    dialog.get_by_label('Begründung').fill('Anmeldung auf Wunsch des Testnutzers zurücksetzen')
    dialog.get_by_label('Benutzername zur Bestätigung').fill('resettester')
    dialog.get_by_label('Dein Administrator-Passwort').fill('Browser-Test-Passwort-123!')
    assert dialog.evaluate('e => e.scrollWidth <= e.clientWidth'), 'Reset confirmation mobile overflow'
    page.screenshot(path=str(artifacts / 'admin-reset-confirmation-mobile.png'))
    dialog.get_by_role('button', name='Verbindlich ausführen').click()
    expect(page.locator('.success-notice')).to_contain_text('Erfolgreich ausgeführt')
    expect(page.locator('.admin-profile')).to_contain_text('Registrierung offen')
    expect(page.locator('.admin-audit-entry').first).to_contain_text('Anmeldung zurücksetzen')
    for label, state in [('Konto sperren', 'Gesperrt'), ('Konto entsperren', 'Registrierung offen')]:
        page.get_by_role('button', name=label, exact=True).click()
        dialog = page.get_by_role('dialog', name=label)
        dialog.get_by_label('Begründung').fill('Kontostatus im isolierten Browser prüfen')
        dialog.get_by_label('Benutzername zur Bestätigung').fill('resettester')
        dialog.get_by_label('Dein Administrator-Passwort').fill('Browser-Test-Passwort-123!')
        dialog.get_by_role('button', name='Verbindlich ausführen').click()
        expect(page.locator('.admin-profile')).to_contain_text(state)
    db = sqlite3.connect(database_path)
    try:
        assert db.execute('SELECT password_hash,credits,is_active FROM users WHERE id=900').fetchone() == (None, 321, 1)
        assert db.execute('SELECT quantity FROM inventory_items WHERE user_id=900').fetchone()[0] == 12
        assert db.execute('SELECT quantity FROM user_boosters WHERE user_id=900').fetchone()[0] == 2
        assert db.execute('SELECT COUNT(*) FROM admin_audit_events WHERE target_id=900').fetchone()[0] == 3
    finally:
        db.close()
    page.get_by_role('button', name='Menü öffnen').click()
    page.get_by_role('link', name='Admin-Menü', exact=True).click()
    expect(page.get_by_role('heading', name='Deine Community im Blick')).to_be_visible()
    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.screenshot(path=str(artifacts / 'admin-audit-desktop.png'), full_page=True)
    # Mixed grant through the real UI, then inspect the recipient's in-app notice.
    page.goto(ui_url + '/#/admin/users/900')
    page.get_by_role('button', name='Vergabe vorbereiten', exact=True).click()
    grant = page.get_by_role('dialog', name='Vergabe vorbereiten', exact=True)
    grant.get_by_label('Menge', exact=True).fill('100')
    grant.get_by_role('button', name='Position hinzufügen', exact=True).click()
    grant.get_by_role('button', name='Packs', exact=True).click()
    grant.get_by_label('Pack suchen', exact=True).fill('SDOYCC Origins')
    grant.locator('.grant-choices').get_by_role('button', name='SDOYCC Origins', exact=True).click()
    grant.get_by_role('button', name='Position hinzufügen', exact=True).click()
    grant.get_by_role('button', name='Karten', exact=True).click()
    grant.get_by_label('Karte suchen', exact=True).fill('Blue-Eyes White Dragon')
    grant.locator('.grant-choices button').first.click()
    expect(grant.get_by_label('Herkunft und Seltenheit').locator('option')).not_to_have_count(1)
    grant.get_by_label('Herkunft und Seltenheit').select_option(index=1)
    grant.get_by_label('Menge', exact=True).fill('2')
    grant.get_by_role('button', name='Position hinzufügen', exact=True).click()
    grant.get_by_label('Begründung (für den Empfänger sichtbar)').fill('Danke für deine Teilnahme am Community-Test!')
    grant.get_by_role('button', name='Vorschau laden', exact=True).click()
    grant = page.get_by_role('dialog', name='Vergabe prüfen', exact=True)
    expect(grant.locator('.grant-preview li')).to_have_count(3)
    expect(grant).to_contain_text('321 → 421')
    page.set_viewport_size({'width': 390, 'height': 844})
    assert grant.evaluate('e => e.scrollWidth <= e.clientWidth'), 'Grant preview mobile overflow'
    page.screenshot(path=str(artifacts / 'grant-preview-mobile.png'))
    grant.get_by_label('Empfänger zur Bestätigung').fill('resettester')
    grant.get_by_label('Dein Administrator-Passwort').fill('Browser-Test-Passwort-123!')
    grant.get_by_role('button', name='Verbindlich vergeben', exact=True).click()
    success = page.get_by_role('dialog', name='Vergabe erfolgreich', exact=True)
    expect(success.get_by_role('status')).to_contain_text('gebucht')
    page.screenshot(path=str(artifacts / 'grant-receipt-mobile.png'))
    success.get_by_role('button', name='Fertig', exact=True).click()
    expect(page.locator('.success-notice')).to_contain_text('Vergabe #')
    page.locator('.grant-saved-receipt summary').first.click()
    expect(page.locator('.grant-saved-receipt').first).to_contain_text('Bestand bei Vergabe: 321 → 421')
    recipient_token = secrets.token_urlsafe(32)
    db = sqlite3.connect(database_path)
    try:
        assert db.execute('SELECT credits FROM users WHERE id=900').fetchone()[0] == 421
        assert db.execute('SELECT quantity FROM inventory_items WHERE user_id=900 AND card_id=1').fetchone()[0] == 14
        assert db.execute('SELECT quantity FROM user_boosters WHERE user_id=900 AND booster_id=1').fetchone()[0] == 3
        assert db.execute('SELECT COUNT(*) FROM grants WHERE user_id=900').fetchone()[0] == 1
        db.execute('INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',
                   (hashlib.sha256(recipient_token.encode()).hexdigest(), 900, datetime.utcnow() + timedelta(hours=1)))
        db.commit()
    finally:
        db.close()
    page.evaluate('(token) => sessionStorage.setItem("hub-session", token)', recipient_token)
    page.goto(ui_url + '/#/account')
    page.reload()
    page.get_by_role('button', name='Mitteilungen, 1 ungelesen', exact=True).click()
    notice = page.get_by_role('region', name='Mitteilungen', exact=True)
    expect(notice).to_contain_text('Belohnung erhalten')
    expect(notice).to_contain_text('Danke für deine Teilnahme')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Notifications mobile overflow'
    page.screenshot(path=str(artifacts / 'grant-notification-mobile.png'))
    notice.get_by_role('button', name='Als gelesen markieren', exact=True).click()
    expect(page.get_by_role('button', name='Mitteilungen', exact=True)).to_be_visible()
    notice.get_by_role('button', name='Schließen', exact=True).click()
    expect(page.locator('.wallet-row').first).to_contain_text('Admin-Gutschrift')
    page.evaluate('(token) => sessionStorage.setItem("hub-session", token)', token)
    page.goto(ui_url + '/#/admin')
    # The same valid session loses access immediately when its role changes.
    db = sqlite3.connect(database_path)
    try:
        db.execute("UPDATE users SET role='user' WHERE id=?", (target_id,))
        db.commit()
    finally:
        db.close()
    page.reload()
    expect(page.get_by_role('heading', name='Kein Zugriff')).to_be_visible()
