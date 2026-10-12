# Einheitliche SDOYCC-Packcover

Stand: 12.10.2026. Alle Pack- und Setansichten verwenden die eigenen SDOYCC-Cover. Die alten Produktbild-URLs bleiben als Katalogmetadaten erhalten, werden für die Packdarstellung aber nicht mehr geladen. Bestände, Kartenpools, Preise und Kaufregeln sind unverändert.

`frontend/src/components/BoosterArtwork.tsx` zeichnet eine skalierbare SVG-Verpackung mit Folienkanten, Kristallmotiv, Setname und optionalem Setcode. Eine feste Namenszuordnung wählt eine von sechs Farbvarianten; sie stellt keine Kartenseltenheit dar. Hauptansicht und Öffnungsanimation verwenden dieselbe Komponente. Eigene Gradient-IDs verhindern Konflikte bei mehreren Packs und bei den beiden Hälften der Öffnungsanimation. SVG und Schrift bleiben bei Vergrößerung scharf. Der vollständige Packname steht auch im zugänglichen Bildtitel.

Diese Verpackungen sind SDOYCC-Sammeleditionen und keine Abbildungen der originalen physischen Produkte. Die gemeinsame Darstellung gilt für Shop, Setlisten, Setdetails, Packdetails, eigenen Packbestand und Öffnungsanimation einschließlich Structure Decks.

Geprüft: Frontendbuild und vollständiger isolierter Hub-Browserablauf einschließlich Kauf, Packbestand, Öffnung, Structure Decks und Handyansicht. Ein gesperrtes altes Bild beeinflusst die neuen Cover nicht. Nachweise: `artifacts/booster-cover-build.log`, `artifacts/booster-cover-browser.log`, `artifacts/sdoycc-custom-covers-desktop.png` und `artifacts/sdoycc-custom-covers-mobile.png`.
