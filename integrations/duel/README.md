# DuelZone – lokales Techniklabor (D0)

Stand: 05.10.2026. Der Ausbau ist freigegeben und begonnen. Dieses Labor weist die Verbindung **Browser → WebSocket → echter EDOPro-Regelkern → private Browseransicht** nach. Es ist noch keine öffentliche DuelZone und kein vollständiger Deck Builder.

## Bisher geprüft

Zusätzlich existiert inzwischen eine **separat abschaltbare Hub-Anbindung** mit echten Hub-Anmeldungen, reservierten Deck-Snapshots, vollständigen Engine-Entscheidungen, Matches mit Sideboarding, Ergebnisfreigabe und Windows-AppContainer. Fünf parallele Matches, Wartung, versionierte Regelfreigaben und befristete Duellsperren sind implementiert. Sie verändert den weiterhin eigenständigen D0-Laborzugang nicht. Aktueller Stand vom 12.10.2026, native Browserprüfung und Grenzen: [Decks und DuelZone](../../docs/DECKS_DUELZONE_STATUS.md).

- Zwei unabhängige Edge-Browsersitzungen spielen ein echtes Duell mit 8.000 LP, normalen Monstern und der geskripteten Zauberkarte Ookazi bis zum Engine-Ergebnis.
- Lokaler Browserlauf: **318 Entscheidungen, 9 Züge, Sieger Spieler 1**, keine JavaScript-Fehler. Ziehen, Beschwörung, Zauberaktivierung, Kettenauflösung, Kämpfe und LP-Veränderungen wurden beobachtet. Die zufällige Deckreihenfolge verändert spätere Testergebnisse.
- Jeder Browser erhält nur die eigene Hand und die eigenen Entscheidungen. Gegnerische Handkarten und verdeckte Feldkarten werden serverseitig verborgen; rohe Engine-Antworten gelangen nicht zum Browser.
- Ungültiger Zugang, falscher Web-Ursprung und doppelte Verbindung für denselben Platz werden abgelehnt. Protokolltests prüfen zusätzlich fremde/veraltete Entscheidungen, ungültige Auswahlen, abgebrochene Nachrichten und unerlaubte Deckbestände innerhalb des Laborpools.
- Deutsche Oberfläche, Kartentextdialog mit Escape, Desktop und 390-Pixel-Mobilansicht ohne horizontalen Seitenüberlauf. Kartennamen/-texte stammen im Labor aus der englischen CDB und sind als Originaltexte gekennzeichnet.
- Erste CSS-Effekte mit voller, schneller oder reduzierter Bewegung; noch keine vollständige Animationsshow.
- **Duell aufgeben** mit Bestätigung, auch während des gegnerischen Zugs. Der Server leitet den Verlierer aus dem angemeldeten Platz ab, beendet den Worker und meldet beiden Spielern das Ergebnis mit dem Grund „Aufgabe“. Weitere Aktionen können das Ergebnis nicht ändern. Abbrechen lässt das Duell weiterlaufen.
- Keine Verbindung zur Hub-Datenbank: keine echten Nutzer, keine Kartenbuchungen, keine Twitch-Nachrichten, keine Guthabenänderung. Der Produktionsdienst wurde dafür nicht neu gestartet.

Prüfartefakte liegen lokal unter `artifacts/duel-lab/`: `report.json`, `surrender-report.json`, `browser-desktop.png`, `browser-mobile.png`, `result-desktop.png`. Binärdateien, Datenpakete und Artefakte sind nicht für Git vorgesehen.

## Lokal ausprobieren

Auf dem **Server-/Entwicklungs-PC** ausführen:

```powershell
.venv\Scripts\python.exe integrations\duel\provision.py
.venv\Scripts\python.exe integrations\duel\run_lab.py
```

Alternativ `start-duel-lab.bat` in diesem Ordner doppelt anklicken. Beim ersten Start lädt es die festgeschriebenen Laufzeitdateien. Die vorhandene Projekt-`.venv` mit FastAPI, Uvicorn und httpx wird verwendet; der Start verändert keine Windows-Installation.

1. `http://127.0.0.1:8014/` einmal im normalen Browserfenster und einmal in einem privaten Fenster öffnen. Zwei Tabs im selben Profil teilen Cookies und genügen dafür nicht.
2. Den jeweils passenden **Laborzugang Spieler 1 / Spieler 2** aus der lokalen Startkonsole eingeben. Diese Zugänge sind unabhängig von Twitch und Hub-Anmeldung.
3. Sobald beide verbunden sind, startet das Duell mit festen Labordecks automatisch. Aktuell erlaubte Entscheidungen stehen unter dem Spielfeld. Karten lassen sich zur Textvorschau anklicken.
4. Mit Strg+C den Laborserver stoppen. Für ein neues Duell neu starten; es gibt noch keine Lobbyverwaltung oder dauerhafte Speicherung.

Nur der Betreiber benötigt diese lokale Laufzeit. **Spieler benötigen weiterhin ausschließlich einen Browser.** Port 8014 ist getrennt vom Hub-Port 8002. Der Launcher bindet ausschließlich an `127.0.0.1`; dieses Labor noch nicht über den öffentlichen Tunnel anbieten.

## Architektur dieser Erprobung

| Datei | Aufgabe |
| --- | --- |
| `sources.lock.json` / `provision.py` | Exakte Upstream-Adressen und SHA-256; Download und lokale Dateiprüfung |
| `core_worker.py` | Separater 32-Bit-Prozess mit nativem EDOPro-Core API 11 und Lua-Kartenskripten; internes JSON-Zeilenprotokoll |
| `protocol.py` | Engine-Nachrichten lesen, pro Spieler erlaubte Ansicht erstellen, Antworten gegen die aktive Entscheidung prüfen |
| `lab.py` | Isolierter FastAPI/WebSocket-Dienst; zwei zufällige Laborzugänge, Sitzungs-Cookies und Ursprungskontrolle |
| `web/` | Browser-Spielfeld, Entscheidungen, Kartenansicht und erste Animationseffekte |
| `run_lab.py` | Lokaler Start auf eigenem Port |

Der hier verfügbare geprüfte Upstream-Core ist eine Windows-x86-DLL. Deshalb läuft er in einem portablen 32-Bit-Python-Unterprozess und nicht im 64-Bit-Hub. Das Gateway beendet den Worker bei Fehlern, nach dem Ergebnis und beim Herunterfahren; einzelne Engine-Aufrufe haben eine Fünf-Sekunden-Grenze. Das ist **Prozesstrennung, noch keine Betriebssystem-Sandbox**. LUA wird mit deaktiviertem unsicherem Modus geladen; nur das festgeschriebene Paket ist vorgesehen.

**D0-Architekturpräzisierung:** Der technische Nachweis verwendet die direkte Core-API statt eines zunächst vorgeschlagenen Multirole-Umbaus. Dadurch können private Browseransichten und Entscheidungen schon isoliert getestet werden. Multirole ist damit nicht als fertige Lobby-, Reconnect- oder Matchfunktion übernommen; diese Aufgaben müssen für die endgültige Integration ausdrücklich abgedeckt werden. Der volle EDOPro-Core entscheidet weiterhin über die Regeln. Die beschränkte Testoberfläche vereinfacht keine Produktionsregeln: Nicht unterstützte Protokollabläufe stoppen das Labor.

## Grenzen und nächste Arbeit

**D0 ist teilweise, nicht vollständig abgeschlossen.** Zwei getrennte externe Netze/HTTPS/WSS sind noch nicht geprüft. Der Browserlauf fand auf diesem Windows-PC über Loopback statt; weitere Browser und echte Touchgeräte sind noch offen.

Der feste Pool mit 40-Karten-Labordecks dient ausschließlich dem Transport-/Engine-Nachweis. Seine Bestandsprüfung verwendet virtuelle Laborbestände, nicht die echte Sammlung. Bannlistendateien sind heruntergeladen, aber noch nicht an einen vollständigen Deckvalidator gebunden. Daraus folgt keine Freigabe sämtlicher TCG-Karten oder der aktuellen Turnierliste.

Noch nicht vorhanden: echter Konto-/Lobbybezug, gespeicherte Decks/YDK, Kartenidentitäts-/Aliasauflösung, vollständige Extra-/Side-Deck-Bedienung, alle Auswahlarten und Beschwörungen, vollständige Animationen/Ton, mehrere Matches, sichere Spielzeit-/Reconnectregeln, private Replays, Adminbetrieb und Reservierungsintegration. Die Aufgabe ist bisher nur für ein einzelnes Laborduell umgesetzt, nicht für ein Match mit mehreren Spielen. Ein neu verbundener Laborplatz kann die vorhandene Ansicht erhalten; dies ist keine abgenommene Produktions-Wiederverbindung. Labor-Cookies sind lokal und ersetzen nicht die geplanten kurzlebigen Hub-Matchtickets.

Weiterarbeit gemäß [Gesamtplan](../../docs/plans/04-DECKBUILDER-DUELZONE.md):

1. D0 vervollständigen: externer Transport, Nachrichten-/Animationsmatrix, kompatibles Enginepaket einschließlich Lizenz-/Quellnachweisen und Betriebsgrenzen.
2. D1/D2: geprüfte Karten-/Regelbasis und Deck Builder mit echter Besitzprüfung.
3. D3: Lobby-ID, zwei Hub-Konten, unveränderlicher Match-Snapshot und atomare Bestandsreservierung.
4. D4–D6: sämtliche Browserentscheidungen und Animationen, Wiederverbindung, Replays/Admin, vollständige geschlossene Abnahme vor öffentlicher Aktivierung.

## Prüfungen wiederholen

```powershell
.venv\Scripts\python.exe integrations\duel\provision.py --verify
.venv\Scripts\python.exe -m unittest discover -s integrations\duel\tests -v
.venv\Scripts\python.exe integrations\duel\tests\browser_lab.py
.venv\Scripts\python.exe integrations\duel\tests\browser_lab.py --surrender
```

Die Unit-Tests benötigen kein natives Paket. Der Browserlauf benötigt das vorbereitete Paket, Playwright und lokal installiertes Edge; er startet einen eigenen kurzlebigen Laborserver auf einem freien Port. Er benutzt keine echte Hub-Datenbank und meldet seine lokale Netzgrenze im Bericht ausdrücklich.

Quellenstände, Lizenzen und offene Herkunftsnachweise: [SOURCES.md](SOURCES.md).


## DuelZone-Fortsetzung am 06.10.2026

WebSockets, gepruefte native Absturz-/Neustartbereinigung, Windows-Ressourcenlimits, Admin-Betrieb, widerrufbare Deckvorlagen und private Ansichtswiedergaben sind umgesetzt. Erweiterte Entscheidungen und autoritative Feldabfragen sind getestet. 229 Backend-Tests, 29 Integrationspruefungen und Frontendbuild erfolgreich. Keine produktive Aktivierung.

Vollstaendiger TCG-Pool, Match-/Side-Deck-Betrieb, komplette Animationsabnahme, EU-Listenabgleich, Quellen-/Rechtenachweise und externe HTTPS/WSS-Abnahme bleiben offen. Aktueller Detailstand: [Decks und DuelZone](../../docs/DECKS_DUELZONE_STATUS.md).


## Aktueller Match-Worker

Die vorherigen Laborgrenzen gelten weiterhin fuer lab.py, nicht fuer den aktuellen Hub-Worker. Der Hub kann validierte Haupt-/Extra-/Side-Snapshots in Einzelduellen und Matches verwenden. Neun reale Core-Mechanikfaelle und ein kompletter Matchlauf mit Side-Deck-Austausch sind erfolgreich. Serveruhren, private Wiedergaben und Adminbetrieb sind umgesetzt. Die produktive Freigabe bleibt gesperrt; aktueller Stand: [Hub-Dokumentation](../../docs/DECKS_DUELZONE_STATUS.md).

Passende Core-/Lua-Quellen vorbereiten: `.venv\Scripts\python.exe integrations/duel/provision_corresponding_source.py`. Die Archive und Revisionen stehen in `corresponding-source.lock.json`. Der Quellstand ist durch den Upstream-Binaercommit zugeordnet, kein lokal byteidentischer Build behauptet.

## Windows-Isolation des Hub-Workers

Der Hub verwendet `windows_sandbox.py`: AppContainer ohne Fähigkeiten, keine Server-Zugangsdaten in der Umgebung und eine prüfsummenbestätigte separate Laufzeit unter `%LOCALAPPDATA%/SDOYCC-Duel-Runtime/`. Nur diese Laufzeit erhält Container-Lese-/Ausführungsrechte. Das benutzerspezifische AppContainer-Profil und die Laufzeitkopie bleiben für Wiederverwendung und Neustart erhalten. Jeder Prozess startet angehalten, erhält zuerst die Windows-Jobgrenzen und wird anschließend fortgesetzt. Die dauerhafte Prozessidentität nennt die tatsächlichen Sandbox-Pfade. Das frühere `lab.py` verwendet seinen eigenen geschlossenen Laborstartpfad.

Echte Sicherheitsproben ausführen: `.venv\Scripts\python.exe integrations/duel/tests/native_sandbox.py`. Zwölf Prüfungen einschließlich Dateizugriff, Netzwerk, Zusatzprozess, Startfehler und Startabbruch; Nachweis: `artifacts/duel-sandbox-report.json`. Dafür werden ausschließlich eigene Testdateien und ein lokaler TCP-Testserver benutzt, keine echten Zugangsdaten oder Hub-Bestände. Die Internetprobe prüft den Windows-Zugriffsfehler beim TCP-Verbindungsversuch; sie benötigt keine erfolgreich erreichbare externe Anwendung.
