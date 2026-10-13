# DuelZone: visuelle Darstellung

Die Arena verwendet eine eigene Vektorgrafik, beleuchtete Feldzonen und Spieleranzeigen mit Lebenspunktbalken. Während eines laufenden Duells erhält das Spielfeld den gesamten Hub-Bereich. Nach dem Duell und beim Sideboarding steht die Hub-Navigation wieder zur Verfügung. Die linke Kartenvorschau wird durch Anklicken fixiert; auf schmalen Geräten steht sie unter der Arena.

Eigene Handkarten sind größer: je nach Desktopgröße 78–110 Pixel breit, auf schmalen Geräten 66 Pixel. Bei vielen Karten überlappen sie, sodass die Hand innerhalb der Arena bleibt. Anklicken fixiert weiterhin die Kartenvorschau.

## Zeitkonto und Kartenauswahl

Jeder Spieler beginnt jedes Duell mit **360 Sekunden**. Nur die Zeit der Person, die eine Engine-Entscheidung treffen muss, wird verbraucht. Die andere Person bekommt **50 % der tatsächlich verbrauchten Zeit** zurück, bis höchstens 360 Sekunden. Beispiel: 20 Sekunden gegnerische Entscheidungszeit geben bis zu zehn Sekunden zurück. Zugwechsel setzen das Konto nicht pauschal zurück. Während der Regelkern verarbeitet oder beim Sideboarding wird keine Duellzeit verbraucht oder gutgeschrieben. Die eigene Sideboarding-Frist beträgt weiterhin 180 Sekunden.

Auswahlfenster zeigen die erforderliche Anzahl, den aktuellen Stand und die noch fehlenden Karten sichtbar an. Das gilt auch für schrittweise Auswahlen, deren Fortschritt direkt vom Regelkern stammt.

Ein Doppelklick wählt eine Karte und bestätigt eine vollständige Auswahl. Werden mehrere Karten benötigt, bleibt das Fenster bis zur erforderlichen Anzahl offen. Bereits gewählte Karten behalten dabei ihre Reihenfolge. Die maximale Anzahl wird nicht überschritten. Bei schrittweisen Auswahlen bestätigt die Oberfläche den nächsten Abschluss nur, wenn der Regelkern ihn ausdrücklich erlaubt. Normale Auswahl- und Bestätigungsbuttons bleiben verfügbar.

Serverantworten auf Aktionen tragen eine ausdrückliche Bestätigung. Regelmäßige Timer-Aktualisierungen geben eine noch laufende Aktion nicht frei; doppelte Übertragungen werden auch vor dem nächsten React-Render verhindert.

Alle Hinweise entstehen aus bestätigten Engine-Ereignissen oder den aktuell erlaubten Entscheidungen. Aktionen, Auswahlindizes und verdeckte Informationen werden weiterhin vom Regelkern bestimmt.

| Ereignis | Darstellung |
| --- | --- |
| Ziehen und Kartenbewegung | Originalrückseite bewegt sich zwischen den betroffenen Orten. |
| Beschwörung | Lichtkreis an der tatsächlichen Zone; eigene Farben für Fusion, Synchro, Xyz, Link, Ritual und Pendel. Verdeckte Beschwörungen zeigen keine Kartenvorderseite. |
| Angriff | Lichtbahn vom Angreifer zum Ziel; direkte Angriffe enden an der gegnerischen Lebenspunktanzeige. |
| Schaden und Heilung | Tatsächliche Lebenspunktänderung als Zahl am betroffenen Spieler. Der Lebenspunktstand bleibt der bestätigte Engine-Wert. |
| Effektaktivierung | Große öffentliche Effektkarte, Kettengliednummer und anschließend fixierte Kartenvorschau. |
| Negierung | Mittiger Hinweis auf die negierte Aktivierung bzw. den negierten Effekt. |
| Phasen und Zugwechsel | Große, mittige Ansage; Saphirblau für den eigenen Zug, Rubinrot für den gegnerischen Zug. „Beendet Zug“ bleibt von „Zug beendet“ getrennt. |
| Duellende | Sieg, Niederlage oder Unentschieden entsprechend dem vom Regelkern bestätigten Sieger. |

Dekoration und Animationen fangen keine Klicks ab. Goldene Hinweise zeigen weiterhin aktivierbare Effekte an Karten, Deck, Extra-Deck, Friedhof und verbannten Karten. Kartenaktionen, Drag & Drop, Auswahlbestätigung und Phasenwechsel erfolgen auf dem Spielfeld.

Im Duellmenü lassen sich Animationen auf **Voll**, **Schnell** oder **Bewegungsarm** stellen und überspringen. Ton und Lautstärke werden gespeichert. Die Betriebssystemeinstellung für reduzierte Bewegung wird ebenfalls berücksichtigt. Sounds und Quellenangaben befinden sich unter `frontend/public/duel-sounds/`.

## Überprüfung

```powershell
$env:PYTHONPATH='backend;backend/tests'
$env:APP_ENV='development'
& '.\.venv\Scripts\python.exe' backend/tests/duel_presentation_browser_checks.py
& '.\.venv\Scripts\python.exe' backend/tests/duel_worker_browser_checks.py
& '.\.venv\Scripts\python.exe' -m unittest discover -s integrations/duel/tests -p 'test_*.py' -q
npm.cmd run build
```

Die Darstellungsprüfung verwendet künstliche Zustände mit den echten React-Komponenten. Sie überprüft unter anderem acht Beschwörungsarten, verdeckte Kartenbewegungen, direkte Angriffe, Schaden, Negierung und Ergebnisanzeigen, Bedienung und Layout bei 1280×720, 1920×1080 und 390×844 Pixeln. Der native Browserlauf verwendet zwei echte Testkonten und einen echten Regelkern auf einer temporären Datenbank. Er verändert keine Produktionsbestände.

Prüfberichte: `artifacts/duel-premium-presentation.log`, `artifacts/duel-premium-native.log`, `artifacts/duel-premium-protocol.log`, `artifacts/duel-premium-build.log`. Bildschirmaufnahmen liegen unter `artifacts/duel-premium-*.png`.

Aktuelle Zeit-/Auswahlprüfungen: `artifacts/duel-time-selection-clock.log`, `artifacts/duel-time-selection-workers.log`, `artifacts/duel-time-selection-backend.log`, `artifacts/duel-time-selection-protocol.log`, `artifacts/duel-time-selection-presentation.log` und `artifacts/duel-time-selection-native.log`. Der echte Browserlauf prüft einen Angriff mit Doppelklick auf das Ziel; die Darstellungsprüfung prüft einfache, mehrfache, geordnete und schrittweise Auswahlen sowie verzögerte Antworten mit zwischenzeitlichen Timerzuständen.
