# Admin-Testduelle gegen die KI

In der Duellzone ein eigenes gültiges Deck auswählen, unter **Gegner** die
**Test-KI** wählen und **KI-Testduell starten** drücken. Die Auswahl sehen
Administratoren und Hauptadministratoren. Der API-Endpunkt prüft diese Rechte
unabhängig von der Oberfläche.

Der einfache Testgegner spielt ein automatisch zusammengestelltes, regelkonformes
40-Karten-Deck aus normalen Monstern bis Stufe 4. Er beschwört, greift an,
beantwortet Auswahlfragen und wechselt selbst die Phasen. Er ist für Ablauf- und
Darstellungstests gedacht, nicht als strategisch anspruchsvoller Gegner.

Testduelle laufen als Einzelduell im regulären isolierten Regelkern. Deckregeln,
Profilfreigabe, Duellsperren, Wartung, Kapazitätsgrenzen und die ursprüngliche
Anmeldung werden geprüft. Testkarten sind flüchtige Kopien: Es werden keine
Bestände verändert oder reserviert und keine Belohnungen ausgezahlt. Die
Startquittung, Prozesszuordnung und Beendigung werden wie bei anderen Duellen
dauerhaft erfasst; ein Serverneustart verwendet dieselbe sichere Prozessbereinigung.

Die KI bekommt nur ihre eigene gefilterte Ansicht. Jede Antwort muss die
vorhandene Promptvalidierung passieren. Unbekannte oder zu komplexe Entscheidungen
beenden den Test kontrolliert. Rollenentzug oder eine beendete Anmeldung stoppen
das Testduell ebenfalls. Aufgeben funktioniert über das Duellmenü.

Prüfungen (PowerShell im Projektverzeichnis):

```powershell
$env:PYTHONPATH='backend;backend/tests'
.\.venv\Scripts\python.exe -m unittest test_duel_practice -v
.\.venv\Scripts\python.exe backend/tests/duel_practice_browser_checks.py
```

Der Browsertest startet eigene lokale Server und eine temporäre Datenbank. Er
prüft den echten nativen Regelkern, Admin-Auswahl, Zugriffsschutz, private Hände,
automatische Beschwörung/Angriff/Zugende, Lebenspunkteschaden, Neuladen, Aufgabe
und unveränderten Bestand.
