# SDOYCC – Abschlussstand

Stand: **03.10.2026**. Der Sammel-Hub mit Admin A1–A7, Kartenhandel und kostenlosem Saisonpass ist unter [samdavid93.github.io/SDOYCC](https://samdavid93.github.io/SDOYCC/) veröffentlicht. Der lokale Server läuft im Produktionsmodus hinter einem vorübergehenden Cloudflare Quick Tunnel. Demo-Zugang ist deaktiviert. Der Testbetrieb benötigt weiterhin diesen eingeschalteten PC und den laufenden Tunnel; eine feste Backend-Adresse wurde nicht eingerichtet.

## Funktionsübersicht

| Bereich | Umgesetzter Stand |
| --- | --- |
| Twitch & Anmeldung | Streamer.bot-Brücke; öffentlicher Registrierungslink, browsergebundene `!confirm`-Bestätigung, Passwort-Login, Sitzungen und Anmelde-Zurücksetzung durch Admins |
| Sammelpunkte | 1.000 Kanalpunkte → 100 Sammelpunkte; einmalige Gutschrift je Einlösung; C# schließt die Reward-Warteschlange nach erfolgreicher Buchung |
| Booster | Standardpreis 100; Kaufbeleg, Pack-Tresor, kostenlose animierte Öffnung, Historie und Wiederholungsschutz |
| Booster-Fortschritt (04.10.2026) | Anzahl, Prozentwert und Balken auf Kacheln, in Details und im Tresor; unterschiedliche aktuell besessene Karten aus dem gültigen Pool, inklusive Deck-Bonusmöglichkeiten |
| Seltene Funde (04.10.2026) | Chat-Warteschlange ab Ultraselten, mit Karte, Seltenheit und Pack; Streamer.bot-Timer-Aktion vorbereitet. Einrichtung und tatsächliche Chat-Zustellung noch offen: [Anleitung](RARE_FINDS.md) |
| Structure Decks | Preis 600; vollständige hinterlegte Decklisten einschließlich Mehrfachexemplaren/Bonusregeln; höchstens drei Bezüge je Konto/Deck, einschließlich Geschenken |
| Sammlung & Katalog | Suche, Filter, Varianten, Mengen/Reservierungen, Kartenjournal; deutsche Texte/Bilder mit englischem Original als Ersatz |
| Gestaltung | Original-SDOYCC-Logo und Banner; mobile Ansichten, animierte Kartenrückseiten, Seltenheitsanzeige und Pack-Opening |
| Kontoverwaltung | Admin-Einstieg in Sidebar; Suche, Rollen, Sperren, Sitzungswiderruf, Reset ausschließlich der Anmeldung, Audit und Schutz des letzten Hauptadministrators |
| Vergaben | Punkte, Kartenvarianten, ungeöffnete Packs und Community-Sonderkarten; Vorschau, Passwortbestätigung, Journale, Belege und Website-Mitteilungen |
| Sonderkarten | Eigener Community-Namensraum, geprüfter Bild-Upload, Entwurf/Veröffentlichung/Archiv, Edition, Seltenheit, Handelbarkeit und optionale lebenslange Auflage |
| Korrekturen | Begründete Gegenbuchung zu einer positiven Originalbuchung; Schutz vor mehrfacher Rücknahme, negativen und reservierten Beständen; weitergetauschte Varianten erfordern Klärung |
| Sammelvergaben | Feste Empfängerliste, Vorschau je Konto, atomare Ausführung je Empfänger, Wiederaufnahme nach Abbruch, keine erneute Gutschrift an erledigte Empfänger |
| Betrieb | Bestands-/Journal-/Reservierungs-/XP-Vergleich, offene Vorgänge, CSV-Kontenexport, lokale Freigabeprüfung, Ablaufbereinigung und XP-Nachverarbeitung beim Start und alle 60 Sekunden |
| Handel | Anzeigenentwurf, Veröffentlichung mit Reservierung, Kartenpakete, Set-Assistent, strukturierte Filter, verbindliche Gegenpakete, neue Bedingungen mit Versionshistorie, Ablehnen/Zurückziehen, atomarer Abschluss und Belege |
| Handelsmoderation | Meldungen, persönliche Blockierungen, begründete Schließung und befristete Handelssperre; Reservierungen werden aufgehoben |
| Saisonpass | Admin-Entwurf mit Zeitfenster, XP-Kurve, Aufgaben und Belohnungsbudget; Veröffentlichung; echte XP aus Öffnungen, Tages-/Wochenaufgaben, einmalige Abholung, Archiv und versionierte Verlängerung der Abholfrist |

## Einstieg

- `start-backend.bat` und `start-frontend.bat` starten die lokale Anwendung. Website: `http://localhost:5173`.
- **Admin-Menü → Kontodetails**: einzelne Vergaben und Kontoaktionen.
- **Admin-Menü → Sonderkarten, Sammelvergaben, Handel & Saisons**: übrige Verwaltungsfunktionen (`/#/admin/advanced`).
- **Handel**: Kartenpakete anbieten und tauschen (`/#/trade`).
- **Saisonpass**: veröffentlichte Saisons und persönliche Belohnungen (`/#/battle-pass`).
- `check-system.bat` prüft den lokalen Zustand ohne Änderungen; `check-system.bat --public` prüft zusätzlich Produktionsmodus und öffentliche Frontend-/CORS-Adressen.
- Für den öffentlichen Testbetrieb auf diesem PC `start-public-test.bat` verwenden. Die BAT übernimmt eine neue Tunnel-Adresse und stößt den Pages-Build an. `stop-public-test.bat` beendet den Tunnel. [Betriebsanleitung](PUBLISHING.md).

`samdavidofficial` bleibt Hauptadministrator. Die Abschlussarbeiten führen keine Vergaben, Rücksetzungen, Testtausche oder Test-Saisons auf echten Konten aus. Beispielwerte im Saisonformular sind editierbare Entwurfshilfen und keine veröffentlichte Saison.

## Bewusste Regeln der ersten vollständigen Version

**Handel:** ausschließlich virtuelle Kartenpakete, keine Punktepreise, Auktionen oder Boostertransfers. Ein Paket wird vollständig getauscht. Ungeklärter Altbestand und kontogebundene Karten sind ausgeschlossen. Standardgrenzen: zehn Anzeigen/Entwürfe und zehn offene ausgehende Vorschläge pro Konto; Vorschläge höchstens 48 Stunden. Die drei Werte sind als `TRADE_MAX_LISTINGS`, `TRADE_MAX_PROPOSALS`, `TRADE_PROPOSAL_HOURS` konfigurierbar. Anzeigen laufen 1–30 Tage. Ein Paket enthält höchstens 100 Varianten. Größere Sets müssen aufgeteilt werden.

Ein vollständiges Set bedeutet je eine Kartenidentität der beim Anlegen festgehaltenen Setliste. Andere nachgewiesene Ausgaben sind erlaubt. Der Server prüft die Vollständigkeit, wenn der Set-Assistent verwendet wird, und speichert die Definition dauerhaft. Neue Gegenbedingungen heben alle alten Vorschläge auf; deren Reservierungen werden frei. Frühere Bedingungen bleiben lesbar. Die angebotene Seite bleibt bis zur Stornierung, zum Ablauf oder zum Abschluss reserviert.

**Saisons:** eine aktive kostenlose Saison; nicht überlappende Zeiträume. XP und Aufgaben zählen ausschließlich erfolgreiche Packöffnungen, keine Admin-Vergaben oder Hin-und-Her-Tausche. Tageswechsel 00:00 UTC, Wochenwechsel Montag 00:00 UTC; die Oberfläche zeigt Fristen in der lokalen Zeitzone. Veröffentlichung fixiert Regeln und Belohnungen. Die Abholfrist lässt sich mit Begründung und neuer Version um bis zu 90 Tage je Vorgang verlängern. Standardbooster und unbegrenzt verfügbare Sonderkarten sind als zugesagte Pack-/Sonderkartenbelohnungen zulässig; Structure-Deck-Limits und erschöpfbare Sonderauflagen dürfen keine allgemein zugesagte Abholung blockieren.

**Admin:** Sonderkarten-Veröffentlichung, Korrekturen, Saisonverwaltung und Kontenexport sind Hauptadministratoren vorbehalten. Normale Admins dürfen normale Twitch-Konten verwalten und innerhalb ihrer Vergabegrenzen belohnen. Support bleibt lesend. Eine Sammelvergabe enthält höchstens 100 verschiedene Empfänger und 20 Positionen. Ein CSV-Export enthält höchstens 10.000 Treffer und verlangt darüber eine engere Suche; er wird nicht still abgeschnitten.

**Sonderkarten:** PNG/JPEG/WebP, höchstens 4 MB, 100–3000 × 100–4200 Pixel. Der Server dekodiert und prüft das Bild und speichert eine neu kodierte JPEG-Version ohne übernommene Metadaten. Keine SVGs, Animationen oder frei abrufbaren Upload-URLs. Bilder werden in der Datenbank gespeichert und sind Teil der Datenbanksicherung. Veröffentlichte Identitäten werden nicht umgeschrieben; für eine neue Karte eine neue Version anlegen. Archivierung erhält Besitz und Historie. Eine Rücknahme verringert nicht die bereits ausgeschöpfte lebenslange Auflage.

**Korrekturen:** Punkte und Karten beziehen sich auf positive Journalzeilen, ungeöffnete geschenkte Packs auf die ursprüngliche Vergabeposition. Structure-Deck-Bezugszähler werden nicht zurückgesetzt. Nach einem Weiterverkauf/Weiter-Tausch derselben Variante erfolgt keine automatische Rücknahme bei einem anderen Besitzer. Solche Fälle benötigen eine begründete manuelle Klärung.

## Prüfung und Grenzen

Ergänzung vom **04.10.2026**: 149 Backend-Tests erfolgreich; vollständiger bisheriger Browserlauf samt neuer Fortschrittsanzeige und vier C#-Ablauftests erfolgreich. Die neue Fundmeldungs-Aktion kompiliert gegen Streamer.bot 1.0.7. Keine Testnachrichten im echten Chat versendet. Prüfprotokolle: `artifacts/booster-features-tests.log`, `artifacts/booster-features-browser.log`. Die ursprüngliche Abnahme steht nachfolgend zur Einordnung.

Die automatisierten Prüfungen verwenden isolierte SQLite-Datenbanken und separate lokale Server. Sie prüfen unter anderem acht gleichzeitige Veröffentlichungen, doppelte Tauschannahmen, Annahme gegen Stornierung, veraltete Bedingungen, Ablauf, Sperren, Reservierungen, Rollback zwischen Abbuchung und Gutschrift, begrenzte Sonderauflagen, fortsetzbare Sammelvergaben, Saisonfristen und doppelte Belohnungsabholung. Der Browserdurchlauf bedient die Funktionen mit getrennten Testkonten einschließlich Mobilansicht.

**Abnahme:** 132 ursprüngliche Backend-Tests plus sechs Veröffentlichungskonfigurationstests (138 auch auf GitHub erfolgreich), 57 benannte lokale Browser-Prüfpunkte und Produktionsbuild erfolgreich. Keine JavaScript-Fehler beim lokalen Abnahmelauf. Probeübernahme und tatsächliche Übernahme erhielten alle bisherigen fachlichen Daten. Sicherung vor Übernahme: `artifacts/db-backups/sdoycc-20261003T200542291717Z.db`. Lokale und öffentliche Systemprüfung erfolgreich; Pages und HTTPS-Testtunnel sind eingerichtet. Echte Twitch-Ereignisse wurden bei diesen Prüfungen nicht ausgelöst.

Aktuelle Ergebnisse: `artifacts/final-tests.log`, `artifacts/final-browser.log`, `artifacts/final-release-check.json`. Screenshots beginnen mit `artifacts/final-`. PostgreSQL ist konfigurierbar, aber dieser Abschluss wird auf der tatsächlich verwendeten SQLite-Installation geprüft; ein PostgreSQL-Betrieb braucht eine eigene Abnahme.

## Öffentlicher Testbetrieb und verbleibende Abnahme

Die konkrete Einrichtung ist in [PUBLISHING.md](PUBLISHING.md) beschrieben. Pages-Deployment, öffentliche Backend-Health-Prüfung, Produktionskonfiguration und CORS sind erfolgreich. Die automatisierte Browserprüfung verwendet die echte Pages-Adresse ohne Kontoanmeldung.

**Vom Betreiber am 03.10.2026 praktisch bestätigt:** Kanalpunkte einlösen, Gutschrift erhalten, Packs kaufen und öffnen sowie die gezogenen Karten gutgeschrieben bekommen. Damit ist der zentrale Sammelablauf live bestätigt. Der automatische Abschluss der Twitch-Warteschlange und der genaue Vorher-/Nachher-Betrag wurden in dieser Rückmeldung nicht gesondert bestätigt. Neuregistrierung mit einem zweiten Konto und Handel zwischen zwei Konten bleiben offen.

1. Pages ist veröffentlicht, der Quick Tunnel ohne eigene Domain läuft. Für einen späteren dauerhaften Betrieb den vorübergehenden Tunnel durch eine feste Backend-Adresse ersetzen.
2. `FRONTEND_URL`, `CORS_ORIGINS`, `VITE_API_BASE_URL`, `VITE_BASE_PATH`, `APP_ENV=production` und `ENABLE_DEMO_AUTH=false` sind gesetzt. Backend-Schlüssel, Datenbank und Sicherungen bleiben lokal.
3. `check-system.bat --public` und Pages-Build waren erfolgreich. Nach einem Tunnel-Neustart die neue Adresse mit `start-public-test.bat` übernehmen und den Abschluss des Pages-Workflows abwarten.
4. Neuregistrierung eines zweiten Kontos über `!register` und `!confirm` sowie Handel zwischen beiden Konten prüfen. Bei der bestätigten Reward-Einlösung noch den automatischen Queue-Abschluss und den genauen Betrag kontrollieren.
5. Zugriff von einem anderen Gerät und erneute Passwort-Anmeldung prüfen. Einlösung, Kauf, Öffnung und Gutschrift sind vom Betreiber bestätigt. Die erste echte Saison bewusst im Admin-Bereich konfigurieren und veröffentlichen; es wurde keine Testsaison auf der echten Datenbank angelegt.

Verpasste Twitch-Ereignisse werden weiterhin nicht automatisch nachgeladen. Bei einem fehlgeschlagenen Hub-Aufruf denselben Redemption-Vorgang erneut ausführen und die ID beibehalten. Eigenständige Passwort-Wiederherstellung ohne Admin, bezahlte Saisonspuren, Teiltausche und automatische Rückabwicklung bereits weitergetauschter Karten gehören nicht zur definierten ersten Version.

## Sicherung und Rückfall

Vor jeder Schemaänderung `backend/scripts/migrate_database.py` mit `PYTHONPATH=backend` ausführen; die Start-BAT sichert ebenfalls vor ihrer Schemaprüfung. SQLite-Backups liegen in `artifacts/db-backups/`. Diese Sicherungen regelmäßig zusätzlich außerhalb des Serverlaufwerks ablegen.

Bei Rückfall zuerst den Backend-Prozess beenden, den fehlerhaften aktuellen Datenbestand separat sichern und anschließend eine ausdrücklich ausgewählte vorherige Datenbanksicherung zusammen mit dem dazugehörigen Code wiederherstellen. Keine laufende SQLite-Datei mit einer einfachen Dateikopie überschreiben. Ein Backup-Rückfall verliert alle seit dieser Sicherung entstandenen Buchungen; daher zunächst die neue Datenbank zur Klärung aufbewahren. Vor Neustart Integrität und Bestandssummen prüfen. Die finale Übernahme protokolliert den konkreten Sicherungspfad und den Vorher-/Nachher-Vergleich.
