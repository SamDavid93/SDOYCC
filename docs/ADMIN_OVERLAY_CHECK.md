# Prüfung von Adminpanel und Stream-Overlay

Prüfstand: 7. November 2026. Schreibende Prüfungen laufen ausschließlich gegen
temporäre Datenbanken mit Testkonten. Die Vorschau des laufenden Servers wird
ohne Abholen oder Bestätigen echter Stream-Meldungen geprüft.

## Behobene Fehler

- Das Adminprotokoll benennt jetzt auch Crafting-, Saison-, Sonderkarten-,
  Handels- und Duellaktionen. Vorher-/Nachher-Werte werden ihrem Datentyp
  entsprechend angezeigt. Einstellungen oder Statuswechsel werden nicht mehr
  fälschlich als gesperrtes Konto mit unbekannter Rolle dargestellt. Auch `false`
  und `null` bleiben sichtbar. Authentifizierungsmaterial wird nicht dargestellt.
- Support kann Sammelvergaben lesen, erhält aber keine Vergabeformulare.
  Normale Administratoren erhalten Ausführungsfelder nur für eigene Vergaben.
  Der Hauptadministrator kann weiterhin alle Vergaben ausführen. Die bestehenden
  serverseitigen Berechtigungsprüfungen bleiben maßgeblich.
- Das Overlay zählt identische Karten auch bei unterschiedlichen Schreibweisen
  derselben Rarität korrekt, beispielsweise `Ultra Rare` und `ultra_rare`.

## Verifikation

- Backend-Gesamtsuite: 335 bestehende Tests erfolgreich; zusätzliche gezielte
  Regression für normalisierte Overlay-Mengen und bestehende Workflow-Tests.
- `browser_smoke.py`: Kontosuche, Kontodetails, Rücksetzen der Anmeldung ohne
  Bestandsverlust, Sperren/Entsperren, Rechteentzug, Änderungsprotokoll, gemischte
  Belohnungsvergaben, Belege, Mitteilungen, Sonderkarten, Sammelvergaben,
  Korrekturen, Handel und Saisonveröffentlichung samt Belohnungsabholung.
- `admin_products_browser_checks.py`: Eigentümerrechte, Passwortbestätigung,
  gespeicherte Produktregeln und Mobilansicht.
- `crafting_browser_checks.py`: Regeln, CP-Korrekturen, Betriebsschalter,
  Auditdarstellung verschiedener Datentypen und Rollen bei Sammelvergaben.
- `stream_overlay_browser_checks.py`: Transparenz, Position unten links,
  Ersatzbild, Mengenanzeige, Wiederholung nach Bestätigungsfehlern,
  Duplikatschutz und Neuladen.
- `pack_reveal_browser_checks.py`: keine Meldungsfreigabe vor dem Kartenflip,
  Freigabe nach Flip beziehungsweise Ergebnisansicht und kein Spoiler beim
  Schließen einer verdeckten Öffnung.
- Reine Vorschau des laufenden Servers: erreichbar, transparent, öffentliche
  Hostnamen gesperrt; keine Schreibanfragen und keine echten Meldungen verbraucht.

Die Browser-Gesamtprüfung wurde auf die aktuellen neun Karten pro Pack,
lokale SVG-Cover und seitenweise Structure-Deck-Öffnungen aktualisiert.
Prüfprotokolle und Screenshots liegen lokal unter `artifacts/admin-overlay-*`.

Die Prüfung löst keine echten Twitch-Nachrichten oder Kanalpunkt-Einlösungen
aus. Ob die OBS-Quelle in der aktiven Streamszene sichtbar eingebunden ist,
muss in OBS selbst geprüft werden. Einrichtung und sichere Vorschau:
[STREAM_OVERLAY.md](STREAM_OVERLAY.md).
