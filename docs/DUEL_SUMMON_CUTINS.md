# Beschwörungs-Cut-ins

Große Cut-ins erscheinen bei offen beschworenen gegnerischen Monstern ab
Stufe/Rang 8, Link-3 oder 2.500 ATK. Eigene Monster, Spielmarken und verdeckte
Beschwörungen lösen sie nicht aus. Die Identität verdeckter Monster wird auch
im neuen Ereignisfeld nicht übertragen.

Der Regelkern liefert beim Beschwörungsereignis ein öffentliches Abbild der
Karte einschließlich Stufe/Linkzahl, Attribut, Bild und Basiswerten. Die
Animation verwendet das vorhandene Kartenmotiv mit Lichtstrahlen, Ring,
Partikeln, Blitzen und einem Namensband. Die Farben folgen der Monsterart.
Eine normale Cut-in-Animation dauert 1,45 Sekunden, „Schnell“ 0,65 Sekunden.
„Bewegungsarm“ zeigt stattdessen kurz eine statische kompakte Anzeige.

Eine eigene Entscheidung verkleinert den laufenden Cut-in sofort. Er bleibt
für den Rest seiner Laufzeit kompakt. Alle dekorativen Ebenen ignorieren
Maus- und Touch-Eingaben; es wird keine Engine-Antwort verzögert und kein
Zeitkonto angehalten. Beim Neuladen werden alte Ereignisse nicht abgespielt.
Im Duellmenü lassen sich **Boss-Cut-ins** separat abschalten oder laufende
Animationen überspringen. Die vorhandene Ton- und Lautstärkeeinstellung gilt
auch für Cut-ins.

Die sieben vom Projekteigentümer bereitgestellten Master-Duel-Dateien
`SE_MONSTER_CUTIN_<ATTRIBUT>.wav` werden nach dem Monsterattribut ausgewählt.
Sie sind unverändert unter `frontend/public/duel-sounds/boss-*.wav` gespeichert.
Herkunft und Prüfsummen stehen in `master-duel-source.json`, Hinweise in
`CREDITS.md`. Der Web-Audio-Player blendet die Wiedergabe passend zur kurzen
Animation aus; die Quelldateien werden dabei nicht verändert.

Geprüft werden öffentliche Bilddaten, Schutz verdeckter Karten, Level- und
Link-Grenzen, Ausschluss eigener Monster, passender Sound, automatische
Verkleinerung bei Kettenentscheidungen sowie Desktop-, Mobil- und
bewegungsarme Darstellung in den bestehenden Protokoll- und Browserprüfungen.
