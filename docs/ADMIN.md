# Kontoverwaltung

Stand: 03.10.2026. Arbeitspakete A1 bis A7 sind umgesetzt. Angemeldete Konten mit Verwaltungsrechten sehen **Admin-Menü** in der Sidebar; direkter Einstieg: `/#/admin`.

## Verfügbare Ansichten

- Übersicht: Konten, Registrierungsstatus, gesperrte Konten, Gesamtguthaben, Kartenexemplare und ungeöffnete Packs. Die lokale Demo zählt in diesen Summen mit.
- Kontosuche nach Twitch-ID, Benutzername oder Anzeigename; Filter für Rolle und Status, serverseitig paginiert.
- Kontodetails: stabile Kontonummer, Twitch-Zuordnung, Rolle, Anlagezeit und Bestände.
- Buchungen, Karten und Pack-Bestand mit eigener Seitennavigation. Karten führen zum Katalog, Packs zu den Produktdetails.
- „Aktualisieren“ lädt die Daten neu. Kartenbestände lassen sich nach Bestandsvarianten aufklappen. „Kartenbewegungen“ zeigt das Inventarjournal. Details: [Variantenbestand](INVENTORY.md).

## Rechte und erste Einrichtung

`support_admin`, `admin` und `super_admin` dürfen diese Ansichten lesen. Support erhält ausschließlich die expliziten Profil-, Guthaben- und Bestandsfelder dieser Schnittstellen; keine Passwörter, Hashes, Sitzungsschlüssel, Einladungen, Browser-Bestätigungen oder internen Buchungsreferenzen. Support bleibt lesend. Administratoren dürfen normale Twitch-Nutzer verwalten; Hauptadministratoren dürfen zusätzlich Verwaltungsrollen bearbeiten. Jede Anfrage prüft die aktuelle Rolle und den aktiven Kontostatus in der Datenbank. Der öffentliche Demo-Token erlaubt niemals Verwaltungszugriff, selbst bei einer fehlerhaft erhöhten Demo-Rolle.

Die Ersteinrichtung erfolgt ausschließlich lokal anhand der **numerischen Twitch-ID** eines aktiven, fertig registrierten Kontos. Im Projektverzeichnis mit PowerShell:

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python.exe backend/scripts/migrate_database.py
.venv/Scripts/python.exe backend/scripts/setup_admin.py --twitch-id DEINE_TWITCH_ID
# Erst nach Prüfung der angezeigten Kontozuordnung dauerhaft übernehmen:
.venv/Scripts/python.exe backend/scripts/setup_admin.py --twitch-id DEINE_TWITCH_ID --apply
```

Ohne `--apply` wird die gesamte Transaktion zurückgerollt. Mit `--apply` werden Rolle und Einrichtungsprotokoll gemeinsam gespeichert. Bereits vorhandene Hauptadministratoren oder ein früherer Einrichtungsbeleg sperren eine erneute Ersteinrichtung; auch parallele Aufrufe erzeugen nur einen Beleg. Das lokale Einrichtungswerkzeug unterstützt SQLite. Es gibt keinen öffentlichen Endpunkt für diese Ersteinrichtung. Weitere Rollenvergaben erfolgen ausschließlich durch einen angemeldeten Hauptadministrator mit frischer Passwortbestätigung.

`admin_audit_events` protokolliert die lokale Einrichtung mit Zielkonto, Zeitpunkt und alter/neuer Rolle. Ein handelndes Konto ist dabei leer, die Quelle `local_cli`. Die allgemeine Auditansicht ist im Admin-Menü und beim jeweiligen Konto verfügbar. Bei Rollenänderungen über das Panel werden die Sitzungen des Zielkontos beendet; anschließend neu anmelden.

## Kontoaktionen im Panel

Im **Admin-Menü → Konto suchen → Kontodetails → Konto verwalten**:

- **Anmeldung zurücksetzen:** Passwort entfernen, alle Sitzungen und alten Registrierungsbestätigungen widerrufen. Der Nutzer verwendet erneut `!register`, öffnet seinen Link, bestätigt einen neuen `!confirm`-Code über sein Twitch-Konto und legt ein neues Passwort fest. Twitch-ID, Rolle, Punkte, Karten, Packs, Kaufgrenzen und Historie bleiben erhalten. Eine bestehende Kontosperre wird dadurch nicht aufgehoben.
- **Alle Sitzungen beenden:** Bestehende Sitzungen widerrufen; das Passwort bleibt gültig.
- **Konto sperren / entsperren:** Globale Sperre bis zur manuellen Entsperrung. Eine Sperre beendet Sitzungen und alte Registrierungscodes. Entsperren reaktiviert keine alten Sitzungen.
- **Rolle ändern:** Nur Hauptadministratoren; Verwaltungsrechte nur für aktive, registrierte Twitch-Konten. Sitzungen und alte Registrierungscodes des Zielkontos werden widerrufen.

Jede Aktion verlangt eine Begründung, den exakt bestätigten Zielbenutzernamen und das eigene Administrator-Passwort. Der Dialog erläutert vorab die Folgen. Das Ergebnis nennt eine Vorgangsnummer; das Protokoll zeigt Akteur, Ziel, Grund, Zeitpunkt und den vorherigen/nachfolgenden Kontozustand. Passwörter, Bestätigungsschlüssel und Sitzungstokens werden nicht protokolliert.

Das eigene Verwaltungskonto kann im Panel nur abgemeldet werden. Demo-Konten sind von Kontoaktionen ausgeschlossen. Die serverseitige Rechteprüfung findet unter Sperre erneut statt. Parallele Rollen-/Sperraktionen können nicht den letzten aktiven Hauptadministrator entfernen. Passwortbestätigungen sind auf 15 Versuche pro fünf Minuten und Administratorkonto begrenzt.

Zurücksetzungen sind ausschließlich **Anmelde-Zurücksetzungen**, wie vom Betreiber festgelegt. Es gibt keine Funktion zum Löschen des Spielstands. Einzelne Sitzungen separat beenden und zeitlich befristete Sperren sind spätere Ergänzungen; aktuell werden sämtliche Sitzungen widerrufen und Sperren manuell aufgehoben.

## Schnittstellen

Alle Routen erfordern eine normale, gültige Sitzung mit Verwaltungsrechten:

| Route | Inhalt |
| --- | --- |
| `GET /api/admin/overview` | Gesamtsummen |
| `GET /api/admin/users` | Suche, Rollen-/Statusfilter, Seiten |
| `GET /api/admin/users/{id}` | Kontoprofil und Besitzsummen |
| `GET /api/admin/users/{id}/wallet` | Guthabenbuchungen, neueste zuerst |
| `GET /api/admin/users/{id}/inventory` | Kartenmengen |
| `GET /api/admin/users/{id}/packs` | Ungeöffnete Produkte |
| `GET /api/admin/audit` | Admin-Protokoll, Filter `user_id` / `action`, paginiert |
| `POST /api/admin/users/{id}/actions` | Kontoaktion mit frischer Passwortbestätigung |

Listen liefern `items`, `total`, `page`, `page_size`. Standard: 25, höchstens 100 Einträge. Suche behandelt SQL-Platzhalter als Text. Nicht angemeldet oder inaktiv: 401; fehlende Rolle: 403; nicht vorhandenes Zielkonto: 404. Antworten werden nicht öffentlich gecacht.

Schreibaufrufe verlangen `Idempotency-Key` (8–100 Zeichen), `action`, `reason`, `confirmation` (Zielbenutzername), `password` (eigenes Admin-Passwort) und nur bei `change_role` zusätzlich `role`. Eine Wiederholung mit gleicher Kennung und gleichen Nutzdaten liefert denselben Vorgang; geänderte Nutzdaten liefern 409. Das Passwort gehört nicht zum gespeicherten Nutzdaten-Fingerabdruck. Alle Änderungen und der Auditbeleg werden gemeinsam committed oder vollständig zurückgerollt. Nach einem Netzwerkfehler kann der Dialog dieselbe Anfrage wiederholen; das Passwort muss erneut eingegeben werden.

Login und Bestandsaktionen prüfen nach dem Kontoschreiblock erneut Passwortstand beziehungsweise Sitzung. Eine während der Zurücksetzung bereits wartende Anmeldung kann deshalb keine neue Sitzung mit dem alten Passwort erzeugen.

## Belohnungen vergeben

Die Kontodetails bieten **Vergabe vorbereiten** für Punkte, konkrete Kartenvarianten und ungeöffnete Packs. Vorschau, Passwortbestätigung und Ergebnisbeleg sind verpflichtend. Empfänger erhalten eine Mitteilung im Hub. Bedienung und Grenzen: [Vergaben](GRANTS.md).

## Nächster Abschnitt

A6/A7, Handel und Saisonpass sind umgesetzt. Bedienung und Grenzen: [Abschlussstand](FINAL_STATUS.md). Vollständige Reihenfolge: [Admin-Plan](plans/01-ADMIN.md).
