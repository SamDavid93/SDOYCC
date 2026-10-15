# Kartenanzeige im Duell

Der linke Viewer zeigt Kartenbild und deutsche Metadaten nebeneinander:
Attribut, Stufe/Rang/Linkwert, ATK/DEF, Monstertyp, Beschwörungsart,
Empfängerkennzeichnung und verfügbare Pendelskalen. Linkmonster erhalten keine
DEF-Anzeige. Der Kartentext hat einen eigenen Lesebereich. Die Kartenwahl
erfolgt durch Anklicken; das Überfahren einer Handkarte wechselt den Viewer nicht.

Die Darstellung orientiert sich an der bereitgestellten Master-Duel-Referenz,
behält jedoch die vorhandene Arenafläche bei. Desktop-Zonen sind annähernd
quadratisch und skalieren gemeinsam mit den Karten anhand von Fensterhöhe,
Fensterbreite und Footerhöhe. Es bleiben genau zwei gemeinsame Extra-Monsterzonen.
Das eigene Deck liegt unten rechts, die Extra-Deck-Stapel zeigen Rückseiten,
öffentliche Friedhofs-/Verbannungskarten ihr sichtbares Bild. Verdeckte Karten
werden nicht über die Stapelvorschau aufgedeckt.

Die eigene Hand überlappt und fächert sich auf. Hover oder Tastaturfokus hebt die
Karte über die Nachbarn; Drag-and-drop und die bisherigen Kartenaktionen bleiben
erhalten. Auf kleinen Touchscreens entfällt die Drehung am Fensterrand.
Kampfwerte stehen groß unter offenen Monstern; verdeckte Monster zeigen keine Werte.

Prüfungen: `backend/tests/duel_presentation_browser_checks.py` prüft echte
React-Komponenten mit isolierten Engine-Frames. `SDOYCC_DUEL_LAYOUT_ONLY=1`
erstellt gezielte Ansichten für 1920×1080, 1440×1000, 1280×720 und 390×844.
Die vollständige Prüfung deckt außerdem Kontextwechsel zwischen Kettengliedern,
Aktivierungsvorschau ohne Antwort und die ursprünglichen Auswahlindizes ab.
