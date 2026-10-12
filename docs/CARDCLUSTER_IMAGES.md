# Deutsche Kartenbilder

## Aktuelle Bildpriorität

Auf Wunsch des Nutzers werden englische YGOProDeck-Vollbilder bevorzugt.
Katalog, Sammlung, Deckeditor und Packöffnung erhalten diese Bilder über
`/api/cards/{id}/art/original`; deutsche Namen und Effekttexte bleiben erhalten.
Die Vollbilder werden lokal unter `cache/cards-original` zwischengespeichert,
entsprechend https://ygoprodeck.com/api-guide/. Ein geprüftes Beispiel hat
813 × 1185 Pixel. Kleine Vorschaubilder und reine Artwork-Ausschnitte werden
nicht als Kartenabbildungen verwendet.

Wenn das Originalbild nicht geladen werden kann, verwendet die Oberfläche den
bisherigen deutschen Bildendpunkt. Gemeinschaftskarten behalten ihre eigenen
Bilder. Im Duell werden ebenfalls die lokal zwischengespeicherten Originalbilder
verwendet.

## Deutsche Rückfallquelle

Der Endpunkt `/api/cards/{id}/art/de` bevorzugt eindeutig geprüfte deutsche
Cardcluster-Scans (500 Pixel breit). Derzeit sind sechzehn Karten hinterlegt:
Blauäugiger weißer Drache, Dunkler Magier, Aschenblüte & Freudiger Frühling,
Rotäugiger schwarzer Drache, Zugangskodier-Sprecher, Topf der Gier,
Unendliche Unbeständigkeit, Vom Grab gerufen, Wiedergeburt, Raigeki,
Feierliches Urteil, Nibiru, das Urwesen, Kuriboh, Spalt, Mystischer Raum-Taifun
und Blauäugiger ultimativer Drache.

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
| 4064 | https://cardcluster.de/card/kuriboh |
| 4835 | https://cardcluster.de/card/fissure |
| 4909 | https://cardcluster.de/card/mystical-space-typhoon |
| 4386 | https://cardcluster.de/card/blue-eyes-ultimate-dragon |

Die hinterlegten Bilddateien wurden direkt geprüft.
Kartenseiten blockieren automatische HTTP-Abfragen; es gibt daher
keinen vollständigen Cardcluster-Import und keine Umgehung dieser Zugriffssperre.
Neue Zuordnungen benötigen eine geprüfte deutsche Bild-URL und eindeutige Karten-ID.

Bei fehlender Zuordnung oder Downloadfehler bleiben die bisherigen deutschen
Bildquellen aktiv. Fehlgeschlagene Downloads werden eine Stunde nicht wiederholt.
Bereits vorhandene ältere deutsche Bilder verhindern die bevorzugte Quelle nicht.
Der Cache liegt in `cache/cards-cardcluster-de` und gehört nicht zur Datenbank.

## Bestandsabgleich am 12. Oktober 2026

Cardclusters eigene Dokumentation unter
https://help.cardcluster.com/card-database/card-scans.md beschreibt eigene Scans
neu erschienener Karten auf Englisch und Deutsch. Die kleine lokale Auswahl ist
keine Aussage über die Gesamtzahl dort vorhandener deutscher Scans.

Der lokale Katalog enthält 14.600 Karten. Für 13.841 (94,8 %) sind im vorhandenen
sprachspezifischen YGOResources-Manifest deutsche Bild-URLs zugeordnet.
Dies ist **keine Cardcluster-Abdeckungsquote** und beweist auch nicht die aktuelle
Erreichbarkeit jeder einzelnen Datei. Die restlichen 759 Karten sind ungeprüft;
sie werden nicht pauschal als unveröffentlicht oder ohne deutschen Scan eingestuft.

Direkte Kartenseiten-, Setlisten- und Sitemap-Abfragen sowie ein normaler
automatisierter Browser erhielten HTTP 403. Die bestätigten Bilddateien sind
erreichbar. Für einen vollständigen Cardcluster-Abgleich fehlt somit ein
zugänglicher Karten-/Bildindex, nicht der Nachweis, dass weitere deutsche
Kartenbilder existieren. Es wurde keine dokumentierte öffentliche Export-API
gefunden. Die Zugriffssperre wird nicht umgangen.
