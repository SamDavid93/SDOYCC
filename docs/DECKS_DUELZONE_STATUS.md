# Decks und DuelZone: aktueller Abschlussstand

Stand: **12.10.2026**. Die nachstehenden Funktionen sind lokal umgesetzt und mit isolierten Konten, Datenbanken und Ports geprüft. Die echte Datenbank enthält inzwischen zusätzlich das geprüfte Regel-/Kartenprofil für den Deckeditor. Produktionskonfiguration, echte Konten, Guthaben, Kartenbestände und Journale wurden dabei nicht geändert. Die öffentliche DuelZone ist weiterhin deaktiviert.

**Alpha-Vorbereitung am 12.10.2026:** Repository nach `git fetch` abgeglichen: lokaler Ausgangscommit und `origin/main` identisch (`a38d407`), keine neueren Branches oder Datenbankdateien; jüngste Remote-Katalogjobs übersprungen. Die lokale SQLite-Datenbank bleibt maßgeblich. Produktionsworker ausdrücklich über `ENABLE_DUEL_ALPHA` einschaltbar, Demo weiterhin gesperrt. Konfiguration und Datenbank vor dem Start gesichert. 246 Backendtests, native Zwei-Browser-Prüfung und Frontendbuild bestanden. Eine Regelprofilfreigabe bleibt eine passwortbestätigte Eigentümeraktion; sie wurde nicht per SQL erteilt. Betriebsanleitung: [Online-Alpha](ALPHA_START.md). Diese Ergänzung beschreibt die Alpha-Vorbereitung; ältere Angaben zur unveränderten Produktionskonfiguration oben beziehen sich auf den vorherigen Kartenimport.

## Decks und Vorlagen

**Intuitiver Editor, 12.10.2026:** Jede Katalogkarte zeigt farbig und mit Text „Erlaubt“, „Ausgeschöpft“, „Verboten“ oder „Nicht freigegeben“. Besessen, frei, im Deck und noch hinzufügbar stehen direkt auf der Karte. Frei berücksichtigt Reservierungen; die Restmenge berücksichtigt zusätzlich Bestand, Kopienlimits über alle Bereiche und Illustrationen sowie die Bereichsgröße. Nicht zulässige oder ausgeschöpfte Karten sind nicht ziehbar; ein Klick erklärt die Sperre, ohne eine Karte hinzuzufügen. Auch Plus-Schaltflächen und schnelle aufeinanderfolgende Klicks beachten dieselben Grenzen. Bekannte Fehlbestände in alten Decks dürfen reduziert werden; neue ungültige Exemplare werden beim Erstellen, Speichern und YDK-Import serverseitig zurückgewiesen. Vorlagen ohne den benötigten eigenen Bestand lassen sich nicht mehr als neues Deck übernehmen. Wunschkarten lassen sich im Gesamtkatalog ansehen, aber nicht neu hinzufügen. Frühere Aussagen zur freien Wunschdeck-Erstellung beschreiben das alte Verhalten.

Kartengruppen sind über direkte Schaltflächen wählbar. Erlaubnisfilter und serverseitige Sortierung nach Name, Besitz, Angriff und Stufe/Rang wirken über die gesamte Ergebnisliste. Das eigene Deck besitzt eine separate Suche und Sortierung; Füllstände zeigen fehlende Mindestkarten und freie Plätze. Mobile Deckkarten stehen in zwei lesbaren Spalten. Fehlversuche geben eine sichtbare, schließbare Meldung; erfolgreiche Änderungen entfernen veraltete Hinweise. Nachweise: `artifacts/deck-intuitive-tests.log`, `artifacts/deck-intuitive-targeted.log`, `artifacts/deck-intuitive-full-tests.log`, `artifacts/deck-intuitive-browser.log` und `artifacts/deck-intuitive-build.log`.

**Alpha-Korrektur der Deckbereiche, 12.10.2026:** Fehlende Engine-Zuordnungen führten im Editor bisher dazu, dass Fusion-, Synchro-, Xyz- und Linkkarten in den geöffneten Hauptdeckbereich eingefügt werden konnten. Die Platzierung verwendet jetzt bei fehlender oder veralteter Regelzuordnung die eindeutig bekannten Katalogtypen; Pendel-Hybridtypen werden berücksichtigt. Ritual und gewöhnliche Pendelmonster bleiben im Hauptdeck, Extra-Pendelmonster im Extra-Deck; das Side-Deck erlaubt weiterhin beide Gruppen. Diese Platzierungshilfe erteilt keine Engine-, Identitäts- oder TCG-Freigabe. Falsche Bereiche werden auch für nicht freigegebene Karten in der Deckprüfung gemeldet. Katalogfilter berücksichtigen bekannte Typen ohne Engine-Zuordnung, und das Verschiebemenü bietet nur passende Zielbereiche an. Zusätzliche Regressionen prüfen alle vier Extra-Typen ohne Namenszuordnung sowie Ritual/Pendel. Nachweise: `artifacts/deck-placement-tests.log`, `artifacts/deck-placement-regression-browser.log` und `artifacts/deck-placement-build.log`.

Private Deckverwaltung mit Haupt-/Extra-/Side-Deck, Besitz- und Regelprüfung, Variantenreservierungen, Suche, Vorschau, Notizen, Testhand, YDK, Autospeichern und Versionskonflikten. Vorlagen veröffentlichen bewusst eine unveränderliche Deckrevision für 30 Tage. Links sind widerrufbar; Notizen und Besitzdaten werden nicht geteilt. Kopieren erstellt einen eigenen Entwurf und vergibt keine Karten. Anonyme Vorlagenansicht und Übernahme durch ein zweites Konto sind im Browser geprüft.

Der Editor zeigt zunächst alle eigenen Karten einschließlich bereits reservierter Exemplare samt frei/besessen-Anzeige. Linksklick auf das Kartenbild fügt ein Exemplar hinzu; Rechtsklick entfernt eines. Eine eigene Detailschaltfläche öffnet die Vorschau. Karten können aus der Sammlung auf einen Deckbereich gezogen, zwischen Bereichen verschoben oder zum Entfernen in die Sammlung zurückgezogen werden. Beim Verschieben bleibt die Gesamtmenge erhalten; bekannte Haupt-/Extra-Typen werden berücksichtigt. Entwürfe dürfen weiterhin Wunschkarten enthalten, doch der Duellstart verlangt tatsächlich verfügbare Exemplare und gültige Kopienlimits.

Die Datenbankvorbereitung wurde erst an einer konsistenten Kopie und danach an der echten SQLite-Datenbank ausgeführt. 13.823 von 14.600 Katalogkarten sind eindeutig zugeordnet; 490 unterschiedliche bereits erworbene Karten sind darunter. Weitere 16 erworbene Karten bleiben wegen Namensabweichungen oder fehlender TCG-Zuordnung gesperrt. Eine neue Karte wird nicht allein aufgrund einer ähnlich klingenden Bezeichnung freigegeben. Das importierte offizielle Listenarchiv gilt ab 18.05.2026; dieser festgeschriebene Stand ist kein Nachweis einer tagesaktuellen Turnierliste. Profilfreigaben bleiben ausstehend. Bericht: `artifacts/deck-database-report.json`. Eine SQLite-Sicherung liegt im dort dokumentierten Pfad unter `artifacts/database-backups/`. Geschützte Konten-, Bestands- und Journalzeilen wurden innerhalb der Schreibtransaktion vor und nach dem Import gehasht und unverändert bestätigt.

Vorbereitung erneut prüfen: `.venv\Scripts\python.exe backend/scripts/prepare_deck_database.py`. Mit `--apply` wird vor dem wiederholbaren Profilimport eine neue konsistente Sicherung angelegt. Es werden keine Karten, Guthaben oder Benutzer verändert. Bei einem abweichenden Variantenbestand stoppt die Vorbereitung, statt Mengen zu erraten. Der normale Hub verwendet diese echte Sammlung; der manuelle Zwei-Fenster-Teststarter verwendet weiterhin ausschließlich temporäre Testkonten.

Die bereitgestellte Kartenrückseite ist unverändert als `frontend/src/assets/card-back.jpg` eingebunden. Verdeckte Duellkarten, Deckstapel, Pack-Rückseiten und Ladeplatzhalter verwenden dieselbe Datei. Verdeckte eigene Feldkarten lassen sich weiterhin im privaten Lesefenster ansehen; gegnerische verdeckte Identitäten werden nicht übertragen.

## Lobby und tatsächlicher Spielbetrieb

Zwei registrierte Konten, private Raumcodes, Gastgeberbestätigung und beidseitige Zustimmung zu den ausgewählten Deckrevisionen. Der Start reserviert die benötigten gebundenen/ungebundenen Exemplare atomar und lädt ausschließlich den serverseitigen Snapshot. Gegnerische Decknamen und Listen bleiben privat.

Der Entwicklungsworker akzeptiert die vollständig validierten Haupt-/Extra-/Side-Bereiche des festgeschriebenen Regelpakets. Die frühere Beschränkung auf normale Monster bis Stufe 4 und Ookazi ist entfernt. Fehlende Kartenzuordnungen, Skripte, Bestand oder Freigaben bleiben Ausschlussgründe. Dies beweist keine individuelle Abnahme jedes vorhandenen Kartenskripts.

Einzelduell und Match bis zum zweiten Sieg sind bedienbar. Unentschieden erhöhen keinen Siegstand. Zwischen Spielen:
- Reservierungen bleiben bestehen.
- Sideboarding erhält die ursprüngliche Kartenmultimenge und jede Bereichsgröße.
- Haupt-/Extra-Typzuordnung bleibt gültig; neue Karten werden abgewiesen.
- Der Verlierer wählt den Startspieler, nach Unentschieden der bisherige Startspieler.
- Erst beide Bestätigungen starten das nächste Spiel.
- Spielstände, Ergebnisse und Sideboarding-Fortschritt werden gespeichert; alte Antworten/Revisionen werden abgewiesen.
- Engine-Sitzplätze werden bei wechselndem Startspieler korrekt auf Konten und private Ansichten abgebildet.

## Transport, Entscheidungen und Darstellung

Authentifizierte WebSockets mit exakter Origin-Kontrolle, ursprünglicher Hub-Sitzung, einem Socket je Sitzplatz, Größen-/Nachrichtenlimits und Heartbeat. Zugangsdaten stehen im ersten Frame, nicht in URLs. Wiederverbindung holt nur den aktuellen autorisierten Zustand; bereits gesendete Aktionen werden nicht automatisch wiederholt.

Parser und Bedienung für Aktionen, Phasen, Ketten, Ja/Nein, Optionen, Karten-/Tribut-/Summen-/Zählmarkenauswahl, Auswahl/Abwahl, Reihenfolgen, Zonen, Positionen, Schere/Stein/Papier und Ansagen. Lange Auswahllisten sind durchsuchbar. Festgeschriebene englische Systemtexte und Karteneffekte erläutern Engine-Entscheidungen.

Optionale Kettenfenster ohne einen einzigen aktivierbaren Effekt werden vom Server unmittelbar mit „Nicht anketten“ beantwortet, bevor eine Spieleruhr weiterläuft. Sobald ein Effekt auswählbar ist, bleibt die Entscheidung beim Spieler; erzwungene Ketten werden nicht automatisch abgelehnt. Dies gilt beim Start, nach Spieleraktionen und beim nächsten Matchspiel. Eine Grenze für aufeinanderfolgende automatische Antworten verhindert eine Endlosschleife bei fehlerhaften Core-Nachrichten.

Die Browserdarstellung verwendet eine Arena mit fünf Monster- und fünf Zauber-/Fallenzonen pro Spieler, zwei gemeinsamen Extra-Monsterzonen, Spielfeld-, Deck-, Extra-Deck-, Friedhofs- und Verbannungsbereichen. Kartenbilder liegen in ihren jeweiligen Zonen; Verteidigung wird gedreht dargestellt. Ein Klick auf eine sichtbare Karte öffnet links eine nichtmodale Ansicht mit Bild, Werten und Kartentext. Escape oder „Vorschau schließen“ entfernt die Auswahl. Auf kleinen Bildschirmen steht die Vorschau oberhalb der Arena. Gegnerische verdeckte Karten bleiben reine Rückseiten.

Handkarten mit einer aktuell erlaubten Setz-/Beschwörungsaktion sind ziehbar. Nach dem Ablegen auf einem eigenen freien Feld bietet das Menü über der Handkarte die passenden Aktionen an; die gewünschte Zone wird erst beim tatsächlichen Engine-Platzierungsprompt beantwortet. Erforderliche Tribute, Positionen und weitere Entscheidungen bleiben erhalten. Die Engine entscheidet weiterhin über erlaubte Aktionen und Zonen. Alternativ sind die Aktionen direkt über der Handkarte oder über die bisherigen Buttons erreichbar. Bei einer Zonenauswahl leuchten die angebotenen Felder auf und lassen sich anklicken; Mehrfachauswahlen werden gemeinsam mit den unteren Buttons ausgewählt und bestätigt. Gleichnamige Handkarten werden anhand ihrer konkreten Handposition unterschieden.

Autoritative Core-Abfragen liefern Hand, Monster-/Zauberzonen, Extra-Deck, Friedhof, Verbannung, dynamische Werte, Materialien, Zählmarken, Ziele und Ausrüstung. Gegnerische verdeckte Identitäten, Werte und Materialien werden serverseitig entfernt. Temporäre Enthüllungen und Hinweise werden nur dem durch die Engine bestimmten Empfänger angezeigt. Kartenbilder werden nur für tatsächlich sichtbare Karten angefordert.

Ereignisgesteuerte Bewegungen und Angriffsrichtungen, eigene Effekte für Fusion/Synchro/Xyz/Link/Pendel/Ritual, Kettennummern, Negierung, Positionswechsel, Zerstörung, Verbannung, Token/Zähler, Würfel/Münzen und LP. Voll/schnell/bewegungsarm, optionaler synthetischer Ton und Überspringen ändern keine Spielentscheidung. Eindeutige Ereigniskennungen, Aufholen bei Hintergrund-Tabs und lesbares Protokoll vermeiden doppelte Abläufe. Die visuelle Gleichwertigkeit mit EDOPro und reale mobile Leistungsziele sind noch nicht abgenommen.

## Zeitregeln für den geschlossenen Betrieb

Es gelten eigene Hub-Regeln, keine offiziellen Turnier-Endverfahren:
- 180 Sekunden Bedenkbudget je Spieler; beim eigenen neuen Zug aufgefüllt. Reaktionen verbrauchen das Restbudget. Engine-Rechenzeit wird nicht abgezogen.
- Ein erschöpftes Budget verliert das aktuelle Spiel; im Match folgt gegebenenfalls Sideboarding.
- 180 Sekunden Sideboarding. Ist genau einer bereit, verliert der andere das Match. Fehlen beide Bestätigungen, neutraler Abbruch.
- 60 Sekunden ohne bestätigten Kontakt eines Spielers sowie eine maximale Laufdauer von einer Stunde führen zum neutralen Abbruch.
- Wiederverbindung füllt keine Uhr auf. Die maßgeblichen Werte stammen vom Server.

## Betrieb, Ergebnisse und Wiedergabe

Windows-Jobobjekt begrenzt den Core auf einen Prozess, 512 MiB Prozessspeicher und 120 CPU-Sekunden je Core-Prozess. Jeder neue Match-Spielprozess erhält neue Grenzen. Verlust des Supervisor-Handles beendet den Kindprozess.

Eine vor dem Start gespeicherte Prozessidentität ermöglicht geprüfte Neustartbereinigung. PID, Erstellungszeit, Programm-/Skriptpfad und Match-/Generationsmarker werden berücksichtigt. Reservierungen werden erst nach bestätigtem Stopp freigegeben. Nicht beweisbare Altfälle bleiben zur Betriebsprüfung gesperrt.

Der Hub-Worker startet zusätzlich in einem Windows-AppContainer ohne Fähigkeiten und ohne Server-Zugangsdaten in seiner Umgebung. Eine getrennte Laufzeitkopie unter `%LOCALAPPDATA%/SDOYCC-Duel-Runtime/` enthält nur prüfsummenbestätigte Paketdateien und den Worker. Der Container erhält ausschließlich Lese-/Ausführungsrechte darauf. Der Prozess startet angehalten und wird erst nach Zuordnung zum Windows-Job fortgesetzt. AppContainer-Profil und Laufzeitkopie bleiben für weitere Worker und Neustarts erhalten; Dateien außerhalb der Laufzeit erhalten keine Container-Leserechte. Die ursprüngliche Laborintegration bleibt getrennt von diesem Hub-Startpfad.

Zwölf echte Sicherheitsprüfungen belegen AppContainer-Token, fehlende Fähigkeiten, entfernte Test-Zugangsdaten, gesperrtes Lesen einer fremden Testdatei, gesperrtes Schreiben im Paket, gesperrten Zusatzprozess, gesperrte Loopback-/Internetverbindungen und den startfähigen nativen Core API 11. Auch fehlgeschlagene Job-Zuordnung, fehlgeschlagene Thread-Fortsetzung und ein asynchron abgebrochener Start lassen keinen Kindprozess zurück. Der Loopback-Test prüft einen zuvor aus dem Supervisor erfolgreich erreichten TCP-Testserver. Bericht: `artifacts/duel-sandbox-report.json`.

Admin-Betriebsansicht mit Passwort, Begründung und Audit für Abbruch/Wiederherstellung. Ergebnisse und Freigabe sind wiederholbar. Aufgabe, Bedenkzeit, Sideboarding-Verzug, technische Fehler und Neustart haben getrennte Gründe.

Die Zulassung berücksichtigt alle dauerhaft gespeicherten laufenden/startenden Matches, einschließlich ungeklärter Altfälle. Standard sind fünf parallele Matches; `DUEL_MAX_ACTIVE_MATCHES` erlaubt 1–20. Volle Kapazität ergibt HTTP 429, Wartung HTTP 503, jeweils bevor neue Karten reserviert werden. Wiederholte Starts geben das ursprüngliche Match zurück. Der versionierte, passwortbestätigte Wartungsschalter lässt laufende Spiele und Sideboarding weiterlaufen. Die Lobby zeigt den tatsächlichen Startblocker.

Regelprofile können im Adminbereich mit Nachweistext, Passwort, Begründung, Versionsprüfung und Audit freigegeben oder zurückgenommen werden. Neue Engine-Freigaben benötigen den Paketabgleich mit dem installierten Worker; neue Regionsfreigaben benötigen einen eindeutig zugeordneten offiziellen EU-Listenimport mit bereits gültigem Datum. Das dokumentierte Importdatum und der Hash ersetzen weder Rechteprüfung noch tatsächliche Abnahme. Ein neuer Profilimport bleibt weiterhin ungeprüft. Befristete Duellsperren betreffen ausschließlich die Duellteilnahme; Anmeldung und Sammlung bleiben verfügbar. Entzogene Teilnahme- oder Regelfreigaben beenden betroffene Spiele neutral und geben Reservierungen erst nach bestätigtem Prozessstopp frei.

Der reale Belastungstest startete fünf AppContainer-Cores für zehn Konten gleichzeitig, wies das sechste Match ab und prüfte Wartung sowie Wiederverwendung eines freien Platzes. Nebenher beantwortete der Hub 188 Leseanfragen: Median 6,16 ms, Maximum 33,23 ms; die fünf Cores belegten zusammen 192,33 MiB RSS. Dies sind lokale Messwerte dieses Rechners, keine Zusage für andere Geräte oder Netze. Paketdateien werden weiterhin einzeln gegen ihre Prüfsummen verifiziert; gemeinsam genutzte Verzeichnispfade werden dabei nur einmal aufgelöst.

Teilnehmer sehen abgeschlossene Ergebnisse und 30 Tage lang ausschließlich ihre eigene damalige Ansicht. Downloads erklären die Offenlegung eigener Handkarten. Aufzeichnung ist auf 1.200 Zustände/8 MiB begrenzt; abgeschnittene Verläufe sind gekennzeichnet. Dies ist eine Ansichtswiedergabe, kein deterministischer Engine-Replay.

## Regel- und Quellenpaket

Der unabhängige EU-Abgleich ordnet alle 226 Einträge der abgerufenen offiziellen Liste eindeutig über Originalnamen und Aliasfamilien zu. Konami-Datenbank-IDs werden nicht als Passcodes verwendet. Das vorbereitete Paket „2026.09 TCG“ unterscheidet sich von der offiziell abgerufenen Liste ab **18.05.2026**. Ein offizieller EU-Kandidat kann separat importiert werden; alte Profile werden nicht überschrieben und dadurch keine Freigaben erteilt.

Der Binärcommit nennt „Update core to efc21aa“. Der entsprechende vollständige Core-Commit ist `efc21aa433b88cd35b7c37db4072a35c58d9d435`, Lua-Submodul `6e22fedb74cf0c9b6656e9fce8b7331db847c605`. Quellenarchive, SHA-256, Lizenzen und Upstream-Buildskripte sind festgeschrieben und lokal bereitgestellt. Kein lokaler byteidentischer Neuaufbau wurde behauptet. Details: [Quellen](../integrations/duel/SOURCES.md).

## Nachweise und Wiederholung

### Selbst im Browser spielen

Im PowerShell-Terminal im Projektordner ausführen:

```powershell
$env:PYTHONPATH='backend'
$env:APP_ENV='development'
.venv\Scripts\python.exe backend/tests/duel_worker_browser_checks.py --manual
```

Der Starter benötigt das vorbereitete native Paket, die vorhandene Python-Umgebung, Node, Playwright und Microsoft Edge. Er startet eigene Server auf freien Ports und öffnet zwei sichtbare Edge-Fenster mit getrennten, bereits angemeldeten Testkonten und vorbereiteten Decks. Die Paketprüfung kann beim Start einige Minuten dauern. Es wird ausschließlich eine temporäre Datenbank verwendet; `.env` und echte Konten/Bestände bleiben unverändert.

Im ersten Fenster das vorbereitete Deck wählen und **Private Lobby erstellen**. Im zweiten Fenster den Lobby-Code eingeben und **Beitreten**. Der Gastgeber bestätigt den Gast; dieser wählt sein vorbereitetes Deck und drückt **Deck auswählen**. Beide drücken **Mein Deck bestätigen** und **Dem lokalen Testduell zustimmen**; der Gastgeber drückt **Lokales Testduell starten**. Für einen Matchlauf vor dem Erstellen den Matchmodus auswählen. Danach können Entscheidungen, Kartenansichten, Neuladen, Sideboarding, Aufgabe und private Historie selbst geprüft werden. Die Testfreigaben gelten nur für die künstliche Datenbank und sind keine Freigabe der Produktionsprofile.

Das Terminal geöffnet lassen. **Enter** im Terminal beendet den Test und entfernt dessen Daten. Ohne `--manual` führt dasselbe Skript die automatisierte Browserprüfung aus.

- Vollständige Backend-Suite: `artifacts/duel-finish-backend.log`.
- Aktuelle vollständige Suite: 243 Tests erfolgreich, `artifacts/deck-final-backend.log`.
- 35 Protokoll-/Privatsphären-/Paketprüfungstests: `artifacts/duel-completion-protocol-tests.log`.
- 13 echte Core-Szenarien: Tribut, Fusion, Synchro, Xyz, Link, Ritual, Pendel, Kettennegierung, Zählmarken, Token, Exodia, leeres Nachziehdeck und gleichzeitiger Exodia-Sieg als Unentschieden; `artifacts/duel-completion-native-mechanics.log`. Das native Unentschieden wird als Ergebnis ohne Sieger übertragen.
- Fünf parallele native Matches und gleichzeitige Hub-Nutzung: `artifacts/duel-load/report.json`.
- Native Zwei-Konten-Browserprüfung einschließlich Wartung, Regelfreigabe und Duellsperre: 22 Prüfpunkte erfolgreich, keine JavaScript-Laufzeitfehler; `artifacts/duel-worker/report.json`; aktueller Lauf mit Originalrückseite: `artifacts/deck-final-duel-browser.log`.
- Kompletter nativer Matchlauf mit zwei Browserkonten und echten Side-Deck-Austauschen, mehreren Spielen, Ergebnis und unveränderten Beständen/Journalsummen: `artifacts/native-match-final.log`.
- Deck-/Lobby-/Vorlagenbrowser einschließlich Linksklick, Rechtsklick und Drag & Drop: `artifacts/deck-final-browser.log`.
- Echter Supervisor-Absturz und Neustart, sieben Prüfpunkte: `artifacts/duel-restart/report.json`.
- Vollständiges Match im AppContainer: drei Spiele, zwei Sideboarding-Runden, 680 Engine-Antworten und keine Browser-Konsolenfehler; `artifacts/duel-match/report.json`.
- Aktueller Frontendbuild: `artifacts/deck-final-build.log`.
- Arena-/Kettenänderung: 39 Worker-/Matchtests (`artifacts/duel-arena-backend.log`), 35 Integrationsprüfungen (`artifacts/duel-arena-protocol.log`) und Frontendbuild (`artifacts/duel-arena-build.log`). Der native Browserlauf prüft zusätzlich 24 feste Zonen, die linke Vorschau und das tatsächlich geladene Kartenbild; `artifacts/duel-arena-browser.log` und `artifacts/duel-worker/card-preview.png`.

```powershell
$env:PYTHONPATH='backend'
$env:APP_ENV='development'
.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.venv\Scripts\python.exe -m unittest discover -s integrations/duel/tests -v
.venv\Scripts\python.exe integrations/duel/tests/native_sandbox.py
artifacts\duel-probe\python32\python.exe integrations/duel/tests/native_mechanics.py artifacts/duel-probe
.venv\Scripts\python.exe backend/tests/duel_match_checks.py
.venv\Scripts\python.exe backend/tests/duel_load_checks.py
.venv\Scripts\python.exe backend/tests/duel_worker_browser_checks.py
.venv\Scripts\python.exe backend/tests/deck_browser_checks.py
npm.cmd run build
```

[Gesamtkonzept](plans/04-DECKBUILDER-DUELZONE.md) und [Technikpaket](../integrations/duel/README.md).

## Noch offene externe Abnahme

Die vollständige öffentliche Freigabe ist nicht abgeschlossen: belastbare Nutzungs-/Weitergabenachweise für Kartenbilder und Texte, Software-Lizenzbereitstellung für den gewählten Veröffentlichungsumfang, Abnahme über zwei tatsächlich getrennte externe Netze mit HTTPS/WSS sowie reale Geräte-/Leistungs- und visuelle Referenzabnahme. Lokale Browserkontexte belegen keine getrennten Netze. Es wurden keine öffentlichen Duellzugänge eingerichtet oder ungeprüfte Profile aktiviert.
