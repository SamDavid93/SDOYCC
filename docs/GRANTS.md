# Belohnungen vergeben (A4/A5)

Im **Admin-Menü → Konto suchen → Kontodetails → Belohnungen vergeben** können Administratoren eine Vergabe zusammenstellen:

1. Sammelpunkte, Karten oder Packs wählen und die Menge hinzufügen. Bis zu 20 unterschiedliche Positionen sind möglich; gleiche Positionen fasst die Oberfläche zusammen.
2. Bei Karten erst die Karte suchen, dann eine belegte Herkunft/Seltenheit aus einem gültigen Produkt wählen. Optional als kontogebunden kennzeichnen. Ein fehlendes Kartenbild verhindert keine gültige Vergabe.
3. Begründung eingeben. **Diese Begründung ist für den Empfänger sichtbar.**
4. Vorschau laden: Empfänger, jede Position und Bestände vorher/nachher prüfen.
5. Empfängernamen bestätigen und das eigene Administrator-Passwort eingeben. „Verbindlich vergeben“ führt alle Positionen gemeinsam aus.
6. Ergebnisbeleg mit Vergabe- und Protokollnummer prüfen. Der Beleg ist anschließend im Änderungsprotokoll erneut aufklappbar.

Packs werden ungeöffnet in den Pack-Bestand gelegt. Die Vergabe kostet den Empfänger keine Punkte; Produktpreise im Shop ändern sich nicht. **Structure Decks bleiben auf drei Bezüge je Konto begrenzt. Pack-Vergaben zählen zum gemeinsamen Lebenszeitzähler und verbrauchen entsprechend verbleibende Kaufmöglichkeiten.**

## Rechte und Mengenlimits

Support bleibt lesend. Normale Administratoren vergeben ausschließlich an aktive normale Twitch-Nutzer. Hauptadministratoren dürfen auch Verwaltungskonten und das eigene Konto als Empfänger wählen. Demo- und gesperrte Konten sind ausgeschlossen. Bereits per Twitch zugeordnete, noch nicht fertig registrierte Konten dürfen Belohnungen erhalten; die Vergabe registriert sie nicht und verändert kein Passwort.

Standardlimits **pro Vorgang**, als Summe über sämtliche Positionen:

| Rolle | Sammelpunkte | Kartenexemplare | Packs |
| --- | ---: | ---: | ---: |
| Administrator | 10.000 | 30 | 10 |
| Hauptadministrator | 1.000.000 | 1.000 | 100 |

Die normalen Admin-Limits lassen sich serverseitig über `ADMIN_GRANT_POINTS_LIMIT`, `ADMIN_GRANT_CARDS_LIMIT` und `ADMIN_GRANT_PACKS_LIMIT` konfigurieren. Nach Änderung Backend neu starten. Es handelt sich um Vorgangslimits, nicht um Tageskontingente. Die Oberfläche zeigt die aktuell wirksamen Werte; dieselben Grenzen werden auf dem Server geprüft. Passwortbestätigungen teilen das bestehende Limit von 15 Versuchen je fünf Minuten und Administrator.

## Buchung und Wiederholung

`Grant` speichert Empfänger, Akteur, Quelle, Begründung, Nutzdaten-Fingerabdruck und fertigen Ergebnisbeleg. `GrantItem` führt die einzelnen Positionen. Die gemeinsame Buchung verwendet Guthabenjournal, Variantenbestand/Kartenjournal und Pack-Bestand; Structure-Deck-Packs erhöhen außerdem den Bezugszähler. Audit, Mitteilung und Aktionsbeleg gehören zur gleichen Datenbanktransaktion. Schlägt eine Position fehl, bleibt die gesamte Vergabe ungebucht.

Die Vorschau verändert keine Bestände. Vor der Ausführung werden unter den Kontoschreibsperren Rollen, Sitzung, Passwortstand, Zielkonto, Mengenlimits, Produktinhalt, Varianten und Bestände erneut geprüft. Haben sich relevante Werte seit der Vorschau geändert, wird die Vergabe mit 409 abgelehnt; erneut Vorschau laden.

Die Ausführung verlangt eine Aktionskennung. Derselbe Vorgang mit identischen Nutzdaten liefert denselben gespeicherten Beleg; es entsteht keine zweite Gutschrift, Kartenbewegung oder Mitteilung. Veränderte Nutzdaten unter derselben Kennung liefern 409. Das Passwort wird weder im Beleg noch im Audit gespeichert. Bei einem Verbindungsfehler den bestehenden Dialog erneut bestätigen; er behält die Aktionskennung. Eine neue Zusammenstellung ist ein neuer Vorgang.

Vergaben sind positiv. Abzüge, Rücknahmen und Sonderkarten-Veröffentlichungen sind als getrennte Werkzeuge unter Admin → Erweiterte Verwaltung verfügbar. Bestehende Kartenvarianten beschreiben Hub-Herkunft und Seltenheit, keine erfundene physische Druckausgabe. Kontogebundene Karten werden separat gezählt; ungebundene, nachgewiesene Varianten können über den Handelsbereich getauscht werden.

## Mitteilungen und Journale

Die Glocke in der Kopfleiste zeigt persönliche Mitteilungen. Neue Vergaben werden bei sichtbarer Website spätestens mit der nächsten 30-Sekunden-Aktualisierung abgefragt. Der Empfänger sieht Positionen, Begründung und Vergabenummer und kann die Mitteilung als gelesen markieren. Listen sind paginiert; fremde Mitteilungen lassen sich nicht lesen oder ändern.

Es werden ausschließlich Mitteilungen innerhalb des Hubs erzeugt. Es gibt keinen Twitch-, E-Mail- oder anderen externen Versand. Guthabenbuchungen heißen „Admin-Gutschrift“, Kartenbewegungen „Admin-Vergabe“.

## Schnittstellen

| Route | Zweck |
| --- | --- |
| `GET /api/admin/grants/limits` | Wirksame Vorgangslimits |
| `GET /api/admin/grants/catalog` | Paginierte Karten-/Produktsuche |
| `GET /api/admin/grants/card-options/{card_id}` | Zulässige Herkunft/Seltenheit aus aktiven gültigen Produkten |
| `POST /api/admin/grants/preview` | Vorschau ohne Buchung |
| `POST /api/admin/grants` | Atomare Vergabe; Passwort, Zielname, Vorschau-Fingerabdruck und `Idempotency-Key` erforderlich |
| `GET /api/admin/grants/{id}` | Gespeicherter Beleg, nur für vergabeberechtigte Admins |
| `GET /api/notifications` | Eigene Mitteilungen und ungelesene Anzahl |
| `POST /api/notifications/{id}/read` | Eigene Mitteilung als gelesen markieren |

Vor der Schemaübernahme legt `backend/scripts/migrate_database.py` eine SQLite-Sicherung an. Die neuen Tabellen verändern vorhandene Guthaben oder Bestände nicht. Testvergaben ausschließlich mit isolierten Datenbanken durchführen.

## Nächste Ausbaustufen

A6/A7, Handel und Saisonpass sind umgesetzt. [Bedienung, konkrete Grenzen und Abschlussprüfung](FINAL_STATUS.md).
