# Deutsche Kartenbilder

Der Endpunkt `/api/cards/{id}/art/de` bevorzugt eindeutig geprüfte deutsche
Cardcluster-Scans (500 Pixel breit, 727–734 Pixel hoch). Derzeit sind zwölf Karten hinterlegt:
Blauäugiger weißer Drache, Dunkler Magier, Aschenblüte & Freudiger Frühling,
Rotäugiger schwarzer Drache, Zugangskodier-Sprecher, Topf der Gier,
Unendliche Unbeständigkeit, Vom Grab gerufen, Wiedergeburt, Raigeki,
Feierliches Urteil und Nibiru, das Urwesen.

Die Zuordnung in `backend/app/modules/cardcluster_images.py` verwendet Konami-IDs.
Sie ändert weder Kartenbesitz noch Decks oder Kartendaten. Die Bilder werden
unverändert lokal zwischengespeichert; verschiedene Druckeditionen können andere
Illustrationen verwenden. Die Abbildung ist keine Aussage zur besessenen Edition.

Quellen der geprüften Zuordnungen:

| Konami-ID | Cardcluster-Kartenseite |
| --- | --- |
| 4007 | https://cardcluster.de/card/blue-eyes-white-dragon |
| 4041 | https://cardcluster.de/card/dark-magician |
| 12950 | https://cardcluster.de/card/ash-blossom-joyous-spring |
| 4088 | https://cardcluster.de/card/red-eyes-black-dragon |
| 15032 | https://cardcluster.de/card/accesscode-talker |
| 4844 | https://cardcluster.de/card/pot-of-greed |
| 13631 | https://cardcluster.de/card/infinite-impermanence |
| 13619 | https://cardcluster.de/card/called-by-the-grave |
| 4842 | https://cardcluster.de/card/monster-reborn |
| 4343 | https://cardcluster.de/card/raigeki |
| 4861 | https://cardcluster.de/card/solemn-judgment |
| 14741 | https://cardcluster.de/card/nibiru-the-primal-being |

Die hinterlegten Bilddateien wurden direkt geprüft.
Kartenseiten blockieren automatische HTTP-Abfragen; es gibt daher
keinen vollständigen Cardcluster-Import und keine Umgehung dieser Zugriffssperre.
Neue Zuordnungen benötigen eine geprüfte deutsche Bild-URL und eindeutige Karten-ID.

Bei fehlender Zuordnung oder Downloadfehler bleiben die bisherigen deutschen
Bildquellen aktiv. Fehlgeschlagene Downloads werden eine Stunde nicht wiederholt.
Bereits vorhandene ältere deutsche Bilder verhindern die bevorzugte Quelle nicht.
Der Cache liegt in `backend/cache/cards-cardcluster-de` und gehört nicht zur Datenbank.
