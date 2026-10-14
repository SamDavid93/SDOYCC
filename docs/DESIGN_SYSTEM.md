# SDOYCC: dunkle Spieloberfläche

Stand: 14.10.2026.

Die Oberfläche verwendet durchgehend Nachtblau, warme metallische Goldakzente und
kühles Saphirblau. Der Schwerpunkt liegt auf lesbaren Kartenbildern, klaren
Hauptaktionen und einer zusammenhängenden Gestaltung aller Bereiche.

## Zuständigkeiten

- `frontend/src/master-duel-theme.css`: gemeinsame Farbvariablen, Schriften,
  Navigation, Anmeldung, Eingabefelder, Grundbuttons, Mitteilungen und Footer.
- `frontend/src/master-duel-content.css`: Startseite, Katalog, Sammlung, Shop,
  Pack-Tresor, Detailseiten, Konto, Handel, Saison und Verwaltung.
- `frontend/src/master-duel-game.css`: Deckbau, Lobby und optische Verfeinerungen
  des Spielfelds. Die bestehenden Spielzustände behalten ihre eigenen Farben:
  eigene Phase Saphir, Gegnerphase Rubin, mögliche Effekte Gold; Aktivieren Grün,
  Setzen gestrichelt Blau, Beschwören Gold, Spezialbeschwören Violett.

Die drei Dateien werden nach den bisherigen Grundstilen in `main.tsx` importiert.
Seitenspezifische Selektoren berücksichtigen später geladene CSS-Dateien.
Das aktive Spielfeld nutzt weiterhin die volle verfügbare Breite. Deckeditor und
Duell-Lobby behalten den festen Bildschirmrahmen; Inhalte scrollen in ihren
Bereichen. Bei 720p wird der untere Arena-Innenabstand an die tatsächlichen
Schriftmetriken angepasst, damit der Copyright-Hinweis Platz behält.

Manrope und DM Mono werden mit ihren SIL-OFL-Lizenzen lokal ausgeliefert:
`frontend/src/assets/fonts/`. Für Schriften ist keine externe Verbindung nötig.
Tastaturfokus, mobile Menüsteuerung mit Escape und reduzierte Bewegung werden
berücksichtigt. Der vorgegebene Copyright-Hinweis bleibt unverändert.

## Prüfung

`backend/tests/dark_design_browser_checks.py` öffnet die echte Anwendung mit einer
temporären Datenbank und lokalen Bildfixtures. Die Prüfung erfasst 13 Bereiche
bei 1920×1080, 1280×720 und 390×844 sowie Anmeldung und Kartenvorschau. Sie prüft
Überläufe, dunkle Oberflächen, feste Frames, Footer, Dialoge, Menüfokus und den
unveränderten Testbestand. Nachweise: `artifacts/dark-design/review.json` und
43 Screenshots; 197 Prüfungen bestanden.

Zusätzlich prüfen `backend/tests/browser_smoke.py` bestehende Transaktionen und
`backend/tests/duel_presentation_browser_checks.py` die tatsächliche Arena samt
Auswahlfenstern, Phasen, Effekten und Ergebnisreihenfolge mit dem neuen Theme.
Produktivdaten und Spielregeln werden durch die Designänderung nicht verändert.
