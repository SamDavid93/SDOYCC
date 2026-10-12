# Aktionen direkt auf dem Spielfeld

- Der Phasenkreis rechts neben Extra-Monsterzone 2 ist im eigenen Zug saphirblau, im gegnerischen Zug rubinrot. Im eigenen Zug öffnet er die aktuell erlaubten Phasenwechsel.
- Markierte Karten haben eine erlaubte Aktion. Eine Handkarte anklicken, Beschwören/Setzen wählen und anschließend das markierte Zielfeld anklicken. Alternativ die Karte auf ein erlaubtes Feld ziehen.
- Angriffsbereite Monster tragen ein Schwertsymbol. Monster anklicken, den Angriff starten und anschließend ein markiertes Ziel wählen und dort bestätigen. Vor dem Start lässt sich der Angriff abbrechen; eine bereits verpflichtende Engine-Entscheidung folgt den Spielregeln.
- Material- und Zielauswahlen werden auf den betroffenen Karten markiert. Bestätigung und Abwählen erscheinen neben der zuletzt ausgewählten Karte. Andere Entscheidungen, etwa Kettenreaktionen, erscheinen über dem Spielfeld.
- Aktivierte Effektkarten werden beiden Spielern kurz groß in der Mitte angezeigt. Anschließend erscheinen Karte und Effekt im linken Viewer. Verdeckte Karten bleiben verborgen, bis die Regeln sie offenlegen.
- Das Menü oben rechts enthält Ton, Animationen, Vollbild, Duellprotokoll und Aufgabe. Kartenvorschauen bleiben durch Anklicken geöffnet; Escape schließt die Vorschau und lokale Aktionsmenüs.
- Das Duellprotokoll nennt die betroffenen Karten, bei Angriffen getrennt als Angreifer und Ziel. Ketteneinträge nennen die aktivierte Effektkarte und den Auflösungsstatus. Geheime Karten erscheinen für den Gegner als „Verdeckte Karte“. Jeder Eintrag bewahrt den damaligen Kenntnisstand, auch wenn die Karte später aufgedeckt oder das Deck gemischt wird.

Prüfungen: `backend/tests/duel_presentation_browser_checks.py` prüft die visuelle Bedienung mit synthetischen Spielständen; `backend/tests/duel_worker_browser_checks.py` prüft zwei getrennte Hub-Sitzungen mit der echten Engine und einer temporären Datenbank. Die Protokolltests unter `integrations/duel/tests` prüfen unter anderem Sichtbarkeit und unveränderte Antwortindizes.
