# Einheitliche SDOYCC-Packcover

## Deutsche EU-Produktbilder (14.10.2026)

Die [deutsche offizielle Produktübersicht](https://www.yugioh-card.com/eu/de/product-category/booster-packs-de/)
hat Vorrang. `backend/scripts/sync_eu_product_covers.py` liest sämtliche Folgeseiten
der Kategorien Booster, Structure Decks, Starter Decks, Tins, Andere, OTS und
Speed Duel sowie die tatsächlichen Bildergalerien der Produktdetailseiten.
Deutsche Bilder werden bevorzugt, darunter einzelne Booster statt Displays.
Die Bilddateien werden unverändert lokal gespeichert; es werden keine
niedrig aufgelösten Vorschaubilder hochskaliert oder Bildnamen erraten.

128 offizielle EU-Produkte wurden übernommen, davon 90 mit deutscher
Sprachkennung. Zusammen mit verbleibenden US-Archivbildern enthält das Manifest
165 unterschiedliche geprüfte Dateien und 167 Namenszuordnungen. Im bestehenden
lokalen Katalog passen 151 Produkte, darunter 11 Structure Decks; 85 dieser
Produkte erhalten ein Bild mit deutscher Sprachkennung.

Deutsche und englische Produktnamen werden über die offiziellen Sprachversionen
zugeordnet. Die Prüfung umfasst Bildformat, Abmessungen und SHA-256 aller
Dateien. Nicht geeignete Bilder und Quellenausfälle ersetzen keine vorhandenen
Cover. Der US-Import bewahrt bereits geprüfte EU-Cover. Produkte ohne passenden
offiziellen Treffer zeigen weiterhin das SDOYCC-Cover. Alle Ansichten einschließlich
Packöffnung verwenden dasselbe Manifest. Datenbank und Spielstände bleiben
unverändert. Importbericht: `artifacts/official-eu-product-covers.json`;
Zuordnungs- und Integritätsprüfung: `artifacts/eu-cover-validation.json`.

Die großen weißen Studioränder werden nur durch einen SVG-Bildausschnitt
ausgeblendet. Das Manifest enthält dafür die gemessenen `focus`-Koordinaten;
die Originaldateien und ihre Prüfsummen bleiben erhalten. Fehlende Bilder
lösen auch in dieser Darstellung zuverlässig das SDOYCC-Ersatzcover aus.
Der Frontend-Build, die isolierte Seitenprüfung mit 197 Prüfungen sowie eine
separate Covervorschau mit offiziellen Bildern, Handyansicht und simuliertem
Bildausfall waren erfolgreich (`artifacts/eu-cover-browser/`).

## Bisheriger US-Import und SDOYCC-Ersatzcover

Stand: 12.10.2026. Passende, ausreichend große offizielle Bilder haben Vorrang vor den eigenen SDOYCC-Covern. Die alten niedrig aufgelösten Produktbild-URLs bleiben als Katalogmetadaten erhalten, werden für die Packdarstellung aber nicht mehr geladen. Bestände, Kartenpools, Preise und Kaufregeln sind unverändert.

Quelle sind die [offizielle Boosterübersicht](https://www.yugioh-card.com/en/products/booster-pack/) und das [offizielle Archiv](https://www.yugioh-card.com/en/products/past_products/booster-pack-archive/). 95 Originalbilder wurden unverändert lokal unter `frontend/public/booster-covers/` abgelegt; 90 vorhandene Packdatensätze sind über ihren Setnamen zugeordnet. Das Manifest `frontend/src/data/officialBoosterCovers.json` enthält Produktseite, Bildquelle, Abmessungen und SHA-256 für jedes Bild. Die Zuordnung entfernt nur den technischen Namenszusatz „Booster“, Satzzeichen und Akzente; sie ordnet keine ähnlich klingenden Sets und keine eigenen SDOYCC-Packs fremden Produkten zu. Offizielle aktuelle Verpackungen können Wiederauflagen zeigen und sind kein Nachweis einer historischen Erstausgabe. Die Bildrechte bleiben bei den jeweiligen Rechteinhabern.

`backend/scripts/sync_booster_covers.py` aktualisiert den Cache, ohne die Datenbank zu verändern. Er akzeptiert ausschließlich überprüfte Bilder von den offiziellen Bildhosts, mindestens 240 × 400 Pixel mit passendem Seitenverhältnis und höchstens 6 MiB. Die 210-Pixel-Bilder vieler archivierter Produkte werden verworfen. Ausfälle entfernen keine bisherigen Cacheeinträge; das Manifest wird atomar ersetzt. Fehlende oder nicht ladbare lokale Originalbilder zeigen das SDOYCC-Cover desselben Packs.

`frontend/src/components/BoosterArtwork.tsx` zeichnet eine skalierbare SVG-Verpackung mit Folienkanten, Kristallmotiv, Setname und optionalem Setcode. Eine feste Namenszuordnung wählt eine von sechs Farbvarianten; sie stellt keine Kartenseltenheit dar. Hauptansicht und Öffnungsanimation verwenden dieselbe Komponente. Eigene Gradient-IDs verhindern Konflikte bei mehreren Packs und bei den beiden Hälften der Öffnungsanimation. SVG und Schrift bleiben bei Vergrößerung scharf. Der vollständige Packname steht auch im zugänglichen Bildtitel.

Diese Verpackungen sind SDOYCC-Sammeleditionen und keine Abbildungen der originalen physischen Produkte. Die gemeinsame Darstellung gilt für Shop, Setlisten, Setdetails, Packdetails, eigenen Packbestand und Öffnungsanimation einschließlich Structure Decks.

Geprüft: Frontendbuild und vollständiger isolierter Hub-Browserablauf einschließlich Kauf, Packbestand, Öffnung, Structure Decks und Handyansicht. Zusätzlich wird die Anzeige eines echten lokalen Originalcovers und der Rückfall bei einem blockierten Bild geprüft. Nachweise: `artifacts/official-booster-covers.json`, `artifacts/official-pack-build.log`, `artifacts/official-pack-browser.log` und `artifacts/official-pack-cover-desktop.png`.
