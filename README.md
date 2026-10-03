# SDOYCC – SamDavidOfficial's Yu-Gi-Oh Card Collector

Trading-Card-Hub für **SamDavidOfficial**: **1.000 Twitch-Kanalpunkte → 100 Tradingpoints → Booster → Kartensammlung**.

## Aktueller Funktionsumfang

- Registrierung über einen öffentlichen Chat-Link und !confirm-Bestätigung mit festem Twitch-Benutzernamen.
- Danach Anmeldung mit Hub-Passwort und zeitlich begrenzten Sessions; keine eigene Twitch-Developer-App.
- Authentifizierte Streamer.bot-Anfragen für Kanalpunkte-Einlösungen.
- Sofortige Gutschrift beim Einlösen; anschließend automatischer Abschluss der Twitch-Warteschlange. Wiederholte Ereignisse buchen nicht doppelt.
- Neue Twitch-Konten starten mit 0 Tradingpoints. Einlösungen vor dem ersten Login werden derselben Twitch-ID zugeordnet.
- Booster kosten beim Kauf Tradingpoints. Vorhandene Packs werden **kostenlos** geöffnet.
- Kauf und Öffnung sind atomar und unterstützen `Idempotency-Key`. Der Browser verwendet denselben Schlüssel erneut, wenn eine Antwort ausbleibt.
- Echtes Inventar, Kontostand, Kontostatistiken, Buchungsjournal und Öffnungshistorie.
- Karten-/Set-Katalog mit Suche und Seitennavigation.
- Katalogimport erhält bestehende IDs und Booster-Bestände; bei Fehlern wird der gesamte Import zurückgerollt.
- Vollständiger Kartenpaket-Handel mit Reservierungen, atomarem Tausch, Belegen und Moderation.
- Kostenloser Saisonpass mit Admin-Planung, echten Öffnungs-XP, Aufgaben, Belohnungen und Archiv.
- Sonderkarten, Bestandskorrekturen, fortsetzbare Sammelvergaben und Betriebsprüfung im Admin-Bereich.

Der aktuelle Abschlussstand, Bedienwege und die noch fehlende öffentliche Einrichtung stehen in [docs/FINAL_STATUS.md](docs/FINAL_STATUS.md). Die Entwicklungshistorie steht in [WORK_PLAN.md](WORK_PLAN.md).

## Architektur

- `frontend/`: React, TypeScript, Vite, HashRouter. Statisches Hosting, etwa GitHub Pages.
- `backend/`: FastAPI und SQLAlchemy. Separater API-Server erforderlich.
- `sdoycc.db`: lokale SQLite-Datenbank; alternativ PostgreSQL mit `postgresql+psycopg://...`.
- `backend/app/modules/economy.py`: Buchungen und Wiederholungsschutz.
- `backend/app/modules/accounts.py`: Registrierung, Passwort-Anmeldung und Sessions.
- `backend/app/modules/streamerbot.py`: authentifizierte Einladungen und Kanalpunkte-Ereignisse.
- `integrations/streamerbot/`: C#-Aktionen und Einrichtung für Streamer.bot 1.0.7.
- `backend/scripts/sync_catalog.py`: YGOPRODeck-Import und Generierung von Set-Boostern.

Intern bleibt das vorhandene Datenbankfeld `credits` erhalten. Die API ergänzt `diamonds` und `diamonds_remaining`; die Oberfläche nennt die Währung **Tradingpoints**. Die drei Begriffe bezeichnen dasselbe Guthaben.

## Lokal starten

Alle Befehle im Projektverzeichnis ausführen. Python 3.12+ und Node.js 22+ werden benötigt.

Einmalig eine lokale Konfiguration anlegen; eine vorhandene `.env` nicht überschreiben:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m pip install -r backend/requirements.txt
npm ci
$env:PYTHONPATH = "backend"
python backend/scripts/migrate_database.py
```

Die Migration sichert eine vorhandene SQLite-Datenbank in `artifacts/db-backups/`. Sie erhält Guthaben, Karten, Booster-Bestände und alte Öffnungen. Bestehende Guthaben erhalten eine Anfangsbuchung; frühere Öffnungskosten werden nicht automatisch erstattet.

Backend per Doppelklick auf [`start-backend.bat`](start-backend.bat) starten. Die Datei verwendet bevorzugt die lokale `.venv`, sichert die SQLite-Datenbank vor der Schemaprüfung und startet die API unter `http://127.0.0.1:8002`. Das Fenster bleibt während des Betriebs geöffnet; mit **Strg+C** lässt sich der Server beenden. Das Frontend wird separat gestartet.

Alternativ im Terminal:

```powershell
python -m uvicorn app.main:app --app-dir backend --port 8002 --reload --no-access-log
```

Frontend per Doppelklick auf [`start-frontend.bat`](start-frontend.bat) starten oder in einem zweiten Terminal:

```powershell
npm run dev
```

Öffne `http://localhost:5173`. Mit `APP_ENV=development` und `ENABLE_DEMO_AUTH=true` erscheint **Lokale Demo öffnen**. Der Demo-Zugang ist in Produktion unabhängig von dieser Einstellung gesperrt. Für dein echtes Konto zuerst die unten beschriebene Streamer.bot-Registrierung einrichten.

Bei fehlendem `npm` im PowerShell-Suchpfad:

```powershell
$env:Path = "C:/Program Files/nodejs;" + $env:Path
npm.cmd run dev
```

API-Dokumentation: `http://localhost:8002/docs`.

## Registrierung und Anmeldung einrichten

Die vollständige Anleitung steht in [integrations/streamerbot/README.md](integrations/streamerbot/README.md).

1. Backend und Frontend über die beiden BAT-Dateien starten.
2. Einmalig die manuelle Streamer.bot-Setup-Aktion mit [SetupTradingHub.cs](integrations/streamerbot/SetupTradingHub.cs) ausführen. Sie lädt den Schlüssel aus der lokalen `.env` und prüft Backend und Kanal.
3. `!register` und `!confirm` mit derselben Registrierungsaktion und [TradingHub.cs](integrations/streamerbot/TradingHub.cs) verbinden. Für `!confirm` den Command-Modus **Starts With** verwenden. Setup selbst hat keinen Chat-Trigger.
4. `!register` im Twitch-Chat senden und den Link aus der öffentlichen Antwort öffnen.
5. Im Browser **Bestätigungscode erstellen** anklicken und den angezeigten Befehl `!confirm CODE` mit demselben Twitch-Konto senden.
6. Die Seite wird automatisch freigeschaltet. Ein Hub-Passwort mit mindestens 12 Zeichen festlegen.
7. Später mit Twitch-Benutzername und Hub-Passwort anmelden.

Der Ablauf funktioniert auch für **SamDavidOfficial selbst**. Die Antworten kommen als normale Chat-Nachrichten vom Broadcaster; es werden keine Flüsternachrichten verwendet.

Der öffentliche Link und der sichtbare Bestätigungscode allein erlauben keine Passwortsetzung. Der Server prüft die tatsächliche Twitch-ID und verlangt zusätzlich den geheimen Schlüssel aus dem Browser, der den Code erstellt hat. Nur selbst angeforderte Codes bestätigen. Neue Code-Anfragen anderer Besucher machen eine bestätigte Registrierung nicht ungültig. Eine vom Kontoinhaber bestätigte andere Browser-Sitzung ersetzt die vorherige.

Bestätigungen gelten standardmäßig 30 Minuten und werden bei erfolgreicher Registrierung verbraucht. Bestehende Passwörter werden nie überschrieben. Bei verlorenem Passwort kann ein Administrator ausschließlich die Anmeldung zurücksetzen; danach erneut per Twitch bestätigen. Eine eigenständige Wiederherstellung ohne Admin ist nicht Teil dieser Version. Alte private Links werden nicht mehr akzeptiert; Guthaben und bestehende Logins bleiben erhalten.

### Kanalpunkte verbinden

`TWITCH_REWARD_ID` in `.env` auf die tatsächliche Belohnungs-ID setzen und das Backend neu starten. In Streamer.bot eine zweite Aktion mit `hubAction=reward` und `TradingHub.cs` anlegen. Beide Trigger **Reward Redemption** und **Reward Redemption Updated** auf diese Belohnung begrenzen.

| Variable | Bedeutung |
| --- | --- |
| `STREAMERBOT_API_KEY` | Gemeinsamer geheimer Schlüssel, nur Backend und Streamer.bot |
| `TWITCH_BROADCASTER_LOGIN` | `SamDavidOfficial` |
| `TWITCH_REWARD_ID` | Tatsächliche Belohnungs-ID aus Streamer.bot |
| `TWITCH_REWARD_COST` | `1000` Kanalpunkte |
| `TWITCH_REWARD_DIAMONDS` | `100` Tradingpoints |
| `REGISTRATION_MINUTES` | `30` Minuten für die Chat-Bestätigung |
| `SESSION_HOURS` | `24` Stunden für eine Sitzung |
| `FRONTEND_URL` | Lokal `http://localhost:5173/`, später die GitHub-Pages-Adresse |

Die Gutschrift erfolgt direkt beim ersten Einlösungsereignis, sobald Twitch die Kanalpunkte abgezogen hat. Nach erfolgreicher Backend-Buchung markiert Streamer.bot die Einlösung automatisch als erfüllt und entfernt sie aus der Warteschlange. Das folgende Updated-Ereignis bucht nichts erneut. Bei Backend-Fehlern wird nicht automatisch abgeschlossen; eine Wiederholung muss dieselbe Einlösungs-ID verwenden.

Das automatische Erfüllen per Streamer.bot setzt eine dort erstellte Belohnung voraus. Alternativ bei der vorhandenen Belohnung in Twitch **Warteschlange überspringen** aktivieren; dann liefert Twitch bereits eine erfüllte Einlösung. Bei dieser Alternative bleibt auch bei einem vorübergehend ausgefallenen Hub keine offene Einlösung zum Nachholen in der Warteschlange.

Bereits stornierte Einlösungen werden nicht gutgeschrieben. Eine Stornierung nach erfolgter Gutschrift wird zur manuellen Klärung protokolliert und nicht automatisch vom Hub-Guthaben abgezogen. Guthaben vor der Passwortregistrierung bleibt derselben Twitch-ID zugeordnet.

### Live-Abnahme und Hosting

Zunächst lokal mit `!register` → öffentlicher Link → Browser-Code → `!confirm CODE` → Passwort setzen → abmelden → erneut anmelden testen. Danach 1.000 Kanalpunkte einlösen, 100 Tradingpoints prüfen, einen Booster kaufen und bei Kontostand 0 kostenlos öffnen.

Die automatisierten Tests simulieren Streamer.bot-Anfragen. Echte Chat-Befehle und Einlösungen sind nach Aktualisierung der Aktionen noch zu prüfen. Verpasste Ereignisse während eines Ausfalls werden derzeit nicht automatisch nachgeladen.

Für Zuschauer sind eine GitHub-Pages-Adresse und ein öffentliches HTTPS-Backend nötig. GitHub Pages stellt nur das Frontend bereit; Python läuft weiterhin lokal. [.env.production.example](.env.production.example) enthält Platzhalter. Noch kein Tunnel und keine öffentliche Adresse eingerichtet. Lokale `localhost`-Links funktionieren nur auf deinem PC.

## Katalogimport

```powershell
$env:PYTHONPATH = "backend"
python backend/scripts/sync_catalog.py
```

Der Import verwendet derzeit ausdrücklich YGOPRODeck. Die älteren Provider-Klassen sind noch keine vollständig austauschbare Import-Pipeline.

Set- und Kartenausgabe-Datensätze werden aktualisiert oder ergänzt; fehlende Quelldatensätze werden nicht automatisch gelöscht. Generierte Set-Produkte behalten ihre IDs; normale Booster kosten 100 Sammelpunkte, Structure Decks 600, während ihre Kartenpools ergänzt beziehungsweise aktualisiert werden. Benutzerdefinierte Produkte bleiben erhalten. Booster-Cover bleiben externe URLs; deutsche Kartenabbildungen werden lokal zwischengespeichert (siehe unten).

Kartenbesitz wird nach Kartenidentität und nach belegter Hub-Variante mit Herkunft/Seltenheit geführt; unbekannte Altbestände bleiben getrennt. Die Ziehung speichert die Seltenheit des Booster-Eintrags in der Historie. Normale Booster enthalten unabhängige gewichtete Ziehungen; Duplikate sind möglich. Structure Decks vergeben dagegen ihre geprüfte feste Deckliste mit Stückzahlen. Zufällige Seltenheitsslots normaler Booster werden noch nicht simuliert.

GitHub Actions enthält einen Import-Workflow alle sechs Stunden. Dafür ist `CARD_DATABASE_URL` als Repository-Secret nötig. Ein SQLite-Pfad im GitHub-Runner synchronisiert keine externe lokale Datenbank; für diesen Workflow muss eine erreichbare gemeinsame Datenbank verwendet werden. Parallele Workflow-Imports sind gesperrt.

## Tests

Backend-Tests verwenden temporäre Datenbanken und verändern deine Sammlung nicht:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
npm run build
```

Optionaler echter Browserdurchlauf mit lokal installiertem Microsoft Edge:

```powershell
python -m pip install -r backend/requirements-dev.txt
python backend/tests/browser_smoke.py
```

Das Skript startet isolierte Testserver und beendet sie anschließend. Screenshots werden unter `artifacts/` abgelegt. Für ein anderes installiertes Playwright-Browserprofil kann `BROWSER_CHANNEL` gesetzt werden; den Node-Pfad steuert `NODE_EXE`.

## Bereitstellung

- Frontend: GitHub-Pages-Workflow; `VITE_API_BASE_URL` als Repository-Variable auf die öffentliche API inklusive `/api` setzen.
- Backend: separater Python-Dienst mit persistentem Datenbankzugriff.
- Produktion: `APP_ENV=production`, `ENABLE_DEMO_AUTH=false`, korrekte HTTPS-Adressen und CORS-Ursprünge.
- Vor einem Schema-Update eine Datenbanksicherung anlegen. Das Migrationsskript sichert SQLite automatisch; PostgreSQL-Sicherungen erfolgen über den Datenbankbetreiber.
- Hub-Sitzungen liegen serverseitig nur als Token-Hash vor. Der Browser hält das Sitzungstoken in `sessionStorage`; ein neuer Tab verlangt gegebenenfalls eine neue Anmeldung. Der Hub erhält keine Twitch-Zugriffstokens; die Twitch-Verbindung verwaltet Streamer.bot.
- Browser-Schlüssel und Bestätigungscodes werden serverseitig als Hash gespeichert. Browser-Schlüssel, Sitzungstokens und Verbindungsschlüssel nicht veröffentlichen. Registrierungslinks enthalten keine Geheimnisse.



### Karten finden und passende Booster wählen

- **Kartenkatalog:** Wunschkarte suchen und öffnen. „In diesen Boostern enthalten“ zeigt passende aktive Packs anhand ihres tatsächlichen Ziehungspools. Die bekannten Ausgaben führen zu den jeweiligen Sets.
- **Booster:** Nach Booster-/Set-Namen oder Set-Kürzel suchen, mit „Nur meine ungeöffneten Packs“ den Bestand filtern. „Enthaltene Karten ansehen“ öffnet Cover, Kartenpool, Suche und Chancen pro Ziehung.
- **Preis:** Normale Booster kosten 100 Sammelpunkte, Structure Decks 600. Öffnen ist kostenlos. Structure Decks liefern die feste Deckliste und sind dauerhaft auf drei Käufe je Deck und Konto begrenzt.
- **Cover:** Startseite, Shop und Details nutzen die hinterlegten Set-Bilder. Ohne verfügbares Cover erscheint eine benannte Ersatzansicht; keine Verwechslung mit einem anderen Pack.


### Meine Packs und die Opening-Show

Gekaufte Booster findest du unter **Meine Packs**: gleiche Booster werden als Stapel mit Stückzahl angezeigt. Startseite, Seitenleiste und Kopfzeile verlinken auf diesen Bestand. Kaufen bleibt im Booster-Shop; gezogene Karten landen in **Meine Sammlung**.

**Pack öffnen** startet die bildschirmfüllende Show: Energieaufbau, Pack-Aufriss und einzeln aufdeckbare Karten. Super Rare, Ultra Rare und höhere Seltenheiten erhalten farblich passende Effekte; die Inszenierung richtet sich nach der tatsächlich gezogenen Seltenheit. „Alle aufdecken“ oder „Animation überspringen“ führt zur Ergebnisübersicht. Ton lässt sich im Opening einschalten; die Browser-Einstellung für reduzierte Bewegung wird berücksichtigt.

Die Ziehung wird vor dem Aufdecken einmalig vom Backend gespeichert. Überspringen, Escape und Schließen führen keine weitere Ziehung aus und nehmen keine Karten zurück. Bei einem Verbindungsabbruch hilft die Öffnungshistorie; der vorhandene Idempotenzschutz bleibt aktiv. Alle Öffnungen bleiben kostenlos.


### Deutsche Karten, Sammlung und Ladezeiten

Die Oberfläche bezeichnet das Guthaben jetzt einheitlich als **Sammelpunkte**. Bestehende Kontostände, Twitch-Belohnungen und API-Felder bleiben kompatibel.

**Meine Sammlung** zeigt bei Desktopbreite sechs Karten nebeneinander, auf kleineren Bildschirmen vier, drei oder zwei. Kombinierbare Filterbuttons decken Seltenheit, Kartenart, Attribut, Typ, Stufe/Rang, Angriff, Verteidigung, Pendelskala, Linkwert, Linkpfeile, Kartengruppe, Set, Turnierstatus und Duplikate ab. Die Daten kommen in Seiten mit 36 Karten; die Mengenübersicht zählt weiterhin die gesamte Sammlung. Das farbige Seltenheitsabzeichen sitzt rechts oben am Kartenmotiv. Bei mehreren gesammelten Seltenheiten wird die höchste bekannte Variante angezeigt; der Tooltip nennt alle Varianten. Stückzahlen bleiben pro Kartenidentität zusammengefasst.

Deutsche Namen, Texte und zusätzliche Eigenschaften nach dem Katalogimport ergänzen:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe backend/scripts/sync_german.py --refresh
```

Ohne `--refresh` werden vorhandene Quelldaten aus `artifacts/catalog-en.json` und `artifacts/catalog-de.json` wiederverwendet. Der Import ergänzt `card_details`, erhält bestehende Karten-IDs und verändert weder Kontostände noch Sammlungen oder Ziehungspools. Vorher eine Datenbanksicherung erstellen.

Stand 30.09.2026: **14.136 von 14.590 Karten** haben einen deutschen Namen, 11.774 einen deutschen Kartentext. Die Basis liefert [YGOPRODeck](https://ygoprodeck.com/api-guide/); der [deutsche Namensindex von YGOResources](https://db.ygoresources.com/about/api) ergänzt 2.362 zuvor fehlende Namen. Alle 14.590 Karten besitzen einen englischen Originaltext als Ersatz. Leere Übersetzungen und Platzhalter wie „Karte 123“ oder „Karte [123]“ werden verworfen: Name und Text fallen jeweils auf das englische Original zurück. Englischer Ersatztext wird in den Kartendetails gekennzeichnet. Offizielle Set- und Kartengruppennamen behalten ihre Quellschreibweise.

Deutsche Kartenbilder werden zuerst anhand des [Bildindexes von YGOResources](https://github.com/yugioh-artworks/artworks-index) geladen, bei Bedarf anschließend über die offizielle Konami-Seite. Der Index weist für **13.841 unserer 14.590 Karten** mindestens eine deutsche Variante aus; das ist keine Garantie für jeden einzelnen Abruf. Zwölf zuvor nicht lokal gespeicherte Varianten wurden beim Einrichten erfolgreich abgerufen. Der Bildabruf hängt nicht mehr davon ab, ob schon ein deutscher Name vorhanden ist.

Schlägt das deutsche Bild fehl, wechselt die Oberfläche automatisch zum vorhandenen Originalbild von YGOPRODeck. Es trägt die Kennzeichnung **Originalbild**. Auch diese Bilder werden lokal gespeichert, nicht bei jedem Seitenaufruf von der Quelle geladen. Erst wenn beide Quellen scheitern, erscheint die gekennzeichnete Rückseite. Die Endpunkte `/api/cards/{id}/art/de` und `/api/cards/{id}/art/original` bleiben sprachlich getrennt; ein Ersatzbild wird nicht als deutsches Bild ausgegeben.

Die deutschen Quellen liefern weiterhin offizielle Vorschauen, häufig mit SAMPLE-Wasserzeichen und ohne Effekttext im Bild. Die Abbildungen werden unverändert gespeichert. Lokale Dateien liegen unter `cache/cards-de/`, `cache/cards-original/` und `cache/artworks-de-index.json` (nicht im Repository). Es wird kein kompletter Bilderbestand heruntergeladen. Ohne lokalen Bildindex wird dieser einmalig beim ersten deutschen Bildabruf geladen; einzelne Bilder werden nur nach Bedarf abgerufen.

Bildindex und zusätzliche deutsche Namen aktualisieren, nach dem normalen Katalog-/Textimport:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe backend/scripts/sync_image_sources.py --refresh
```

Ohne `--refresh` werden bereits gespeicherte Quellen aus `artifacts/` verwendet. Vor dem Namensimport die Datenbank sichern. Nach einer Aktualisierung des Bildindexes das Backend neu starten. Der Namensimport ergänzt ausschließlich fehlende Übersetzungen; Benutzerkonten, Inventar, Guthaben und Booster-Bestand bleiben erhalten.

Beim Laden erscheint eine animierte Kartenrückseite mit Lichtreflex und Ladepunkten. Reduzierte Bewegung wird berücksichtigt. Bilder laden bedarfsgerecht; gespeicherte Vorschauen erhalten sieben Tage Browser-Cache. Gleichzeitige identische API-Leseanfragen werden zusammengeführt und 15 Sekunden pro Sitzung wiederverwendet. Käufe, Öffnungen und Kontowechsel verwerfen diesen Daten-Cache; Kontostände bleiben separat aktualisiert. Zusätzlich: Gzip-Kompression, Datenbankindizes und verzögerte Sucheingaben.


### Booster mit kleinen Kartenpools

Ein Booster gibt höchstens so viele Karten aus, wie unterschiedliche Kartenidentitäten mit positivem Ziehungsgewicht vorhanden sind: `min(konfigurierte Kartenanzahl, ziehbare Kartenarten)`. Ein Pool mit drei Kartenarten ergibt also maximal drei Karten statt fünf. Mehrere Seltenheitseinträge derselben Karte erhöhen diese Grenze nicht. Shop, Details und Pack-Tresor zeigen die effektive Menge an. Gewichtete Ziehungen können weiterhin Duplikate enthalten; die Begrenzung ist keine Garantie unterschiedlicher Karten. Leere/ungültige Pools können nicht gekauft oder geöffnet werden. Der Preis bleibt 100 Sammelpunkte.

### Produktname und nächste Ausbaustufen

Der Produktname lautet **SDOYCC – SamDavidOfficial's Yu-Gi-Oh Card Collector**. Die lokale Datenbank heißt `sdoycc.db`; bei einer bestehenden Installation nicht einfach den Konfigurationspfad ändern und dadurch eine leere Datenbank öffnen. Vor einer Dateiumbenennung sichern und das Backend stoppen. Die Namensmigration des Standard-Boosters erhält dessen ID und alle Besitzverknüpfungen.

Der geplante Ausbau ist lokal umgesetzt: **Admin A1–A7, Kartenhandel und kostenloser Saisonpass**. Die Pläne dokumentieren außerdem bewusst ausgeschlossene spätere Erweiterungen; aktuelle Bedienregeln stehen im [Abschlussstand](docs/FINAL_STATUS.md):

1. [Admin-Verwaltung](docs/plans/01-ADMIN.md): Rollen, Kontoverwaltung, Punkte-/Karten-/Boostervergaben, Sonderkarten, Audit und Variantenbestand.
2. [Handel](docs/plans/02-HANDEL.md): Anzeigen, Karten-/Setpakete, verbindliche Angebote, Reservierungen und atomarer Tausch.
3. [Saisonpass](docs/plans/03-SAISONPASS.md): XP, Aufgaben, saisonale Belohnungen, Fristen und Archiv.

[Gesamter Arbeitsplan und Abhängigkeiten](docs/plans/00-ROADMAP.md). Diese Dokumente enthalten die vorgesehenen Datenmodelle, Abläufe, Schnittstellen, Umsetzungsschritte und Abnahmekriterien; der aktuelle Umsetzungsstand ist je Arbeitspaket markiert. Technische Erwähnungen des unabhängigen Drittanbieters im entsprechenden Adapter und historische Sicherungsnamen bleiben sachlich unverändert.


### Structure Decks: feste Inhalte und Kaufgrenze

- 600 Sammelpunkte je Deck (6 × Standardpreis). Höchstens drei Käufe pro Structure Deck und Konto; auch Mengenbestellungen und gleichzeitige Anfragen unterliegen diesem Limit. Öffnen gibt keine Kaufmöglichkeit zurück.
- Der Server vergibt die vollständige hinterlegte Deckliste einschließlich Mehrfachexemplaren und erfasster Token. Die Grenze kleiner Zufallsbooster gilt hier nicht.
- Alle 59 Structure Decks sind hinterlegt. **Blue-Eyes White Destiny** liefert 50 feste Karten plus eine von drei Secret-Rare-Bonuskarten; **Spirit Charmers** liefert 41 feste Karten, eine Spielmarke und eine von vier Ultra-Rare-Bonuskarten. Der Hub wählt die Bonuskarte gleichverteilt. Quarter-Century-Aufwertungen und unterschiedliche Bild-/Spielmarken-Motive werden derzeit nicht simuliert; die Detailseiten weisen darauf hin. Begleitsets wie „Special Edition“ werden nicht als vollständige Structure Decks verkauft.
- Details trennen garantierte Stückzahlen von zusätzlichen Bonusmöglichkeiten; Shop und Setdetails zeigen verbleibende Käufe. Ein erreichter Grenzwert verhindert weitere Käufe, aber nicht das Öffnen des vorhandenen Bestands.
- `backend/data/structure-decks.json` enthält die geprüften Stückzahlen und Quellen. Der Import erfolgt lokal beim Backendstart, ohne Netzwerkabrufe. Wiederholungen sind wirkungslos; abweichende bereits installierte Listen werden als Konflikt gemeldet und nicht still ersetzt.
- Prüfung: `python backend/scripts/sync_structure_decks.py` mit `PYTHONPATH=backend`; bewusste Übernahme mit `--apply`. Vor Schemaänderungen `backend/scripts/migrate_database.py` verwenden (SQLite-Sicherung). Bestandskonten erhalten als konservative Kaufhistorie vorhandene Packs plus frühere Öffnungen. Historisch verschenkte Packs lassen sich dabei nicht von Käufen unterscheiden. In dieser Installation gab es zuvor keinen Structure-Deck-Besitz.
- Neue Token ohne YGOPRODeck-ID erhalten eine eigene Quellkennung; deutsche Metadaten werden übernommen, soweit vorhanden. Ihre Bilder hängen wie andere Karten von erreichbaren Bildquellen ab. Kartenbesitz wird zusätzlich nach belegter Seltenheit und Herkunftspack geführt; die Summe nach Kartenidentität bleibt erhalten. Nicht eindeutig zuordenbare Altmengen bleiben als unbekannte Ausgabe erhalten.

Quellen und Einschränkungen: [Deckdaten und Prüfung](docs/STRUCTURE_DECKS.md).

### SDOYCC-Bildmarke

Die bereitgestellten Originaldateien liegen unter `frontend/src/assets/sdoycc-logo.png` und `sdoycc-banner.png`. Das Logo erscheint in der Navigation sowie bei Anmeldung und Registrierung; der Banner bildet das Hauptmotiv der Übersicht. Vite liefert beide über versionierte lokale Asset-URLs, auch bei einem GitHub-Pages-Unterpfad. Seitenverhältnisse und Transparenz bleiben erhalten.

### Kontoverwaltung (Admin A1–A7)

Unter **Admin-Menü** in der Sidebar (`/#/admin`) stehen berechtigten Konten eine Community-Übersicht, Kontosuche und Detailansichten für Guthabenbuchungen, Karten und Packs zur Verfügung. Administratoren können Anmeldungen zurücksetzen, Sitzungen beenden und normale Konten sperren oder entsperren. Hauptadministratoren können außerdem Rollen vergeben. Jede Aktion verlangt Passwortbestätigung und wird protokolliert; Spielstände bleiben bei einer Anmelde-Zurücksetzung erhalten. Einrichtung über die verifizierte Twitch-ID, Rollen und Schnittstellen: [Admin-Anleitung](docs/ADMIN.md).

### Bestandsvarianten und Kartenjournal

Unter jeder Karte in **Meine Sammlung** zeigen „Bestandsvarianten“ die tatsächlichen Stückzahlen je belegter Seltenheit/Herkunft. „Kartenbewegungen anzeigen“ öffnet das persönliche Inventarjournal. Dieselben Informationen stehen Administratoren in den Kontodetails zur Verfügung. Migration, Grenzen und Prüfungen: [Variantenbestand](docs/INVENTORY.md).

### Belohnungen vergeben

**Admin-Menü → Kontodetails → Vergabe vorbereiten**: Punkte, Kartenvarianten und Packs in einem Vorgang vergeben. Vorschau und Passwortbestätigung schützen die Ausführung; Belege und Journale machen sie nachvollziehbar. Der Empfänger erhält eine Mitteilung über die Glocke. Structure-Deck-Geschenke zählen zum Limit von drei Bezügen pro Konto. [Bedienung, Limits und Schnittstellen](docs/GRANTS.md).

### Erweiterte Verwaltung, Handel und Saisonpass

Für den letzten Bereitstellungsschritt: [GitHub Pages und HTTPS-Backend einrichten](docs/PUBLISHING.md). `configure-public.bat` bereitet die öffentlichen Adressen als Vorschau vor; `--apply` übernimmt sie mit Sicherung der bestehenden lokalen Konfiguration.

Unter **Admin-Menü → Sonderkarten, Sammelvergaben, Handel & Saisons** stehen die erweiterten Werkzeuge bereit. Der **Handel** und **Saisonpass** sind über die Hauptnavigation erreichbar. [Funktionsübersicht, Regeln, Betrieb und Freigabe](docs/FINAL_STATUS.md). Mit `check-system.bat` lässt sich der lokale Zustand ohne Änderungen prüfen; `--public` ergänzt die Prüfung der öffentlichen Konfiguration.
