# Structure-Deck-Daten

Stand: 30.09.2026. Alle 59 Structure Decks sind definiert: 57 ausschließlich mit festen Stückzahlen, zwei mit festem Inhalt und einer zusätzlichen zufälligen Bonuskarte.

## Quellen und Zuordnung

Hauptquelle ist [YGOJSON](https://github.com/iconmaster5326/YGOJSON). Die englischen TCG-Ausgaben enthalten Setnummern, Seltenheiten und `qty`-Angaben. Jede Definition im Manifest verweist auf ihren Quelldatensatz. Der lokale Snapshot wird verwendet; das Backend lädt beim Start keine aktuellen Fremddaten nach. Ein SHA-256-Wert schützt bereits installierte Definitionen vor unbeabsichtigtem Austausch beim nächsten Import.

Die Karten werden anhand der Setnummer den vorhandenen Kartenausgaben zugeordnet. Fehlende Token stammen aus einzeln referenzierten YGOJSON-Kartendatensätzen. Fehlende Mengenfelder bedeuten gemäß dem Quellformat ein Exemplar. Unterschiedliche Seltenheitsvarianten werden nicht als zusätzliche garantierte Karten interpretiert.

Als Gegenprüfung wurden die [YDK-Listen von larikk](https://github.com/larikk/ygo-ydk-files/tree/a773da9d9b5a409fcca9f44e542acacfdc637c54/deck) verwendet. Der Commit ist fest referenziert. Für Marik, dessen YGOJSON-Inhaltsliste leer ist, dient die YDK-Liste als Mengenquelle. Alte Passcodes/Artwork-IDs werden anhand des vorhandenen YGOPRODeck-Feeds zugeordnet. Unterschiede des Abgleichs sind im Manifest dokumentiert: insbesondere Token, alternative Nummern und eine fehlende zweite Karte bei Mechanized Madness.

Kontrollbeispiele:

| Produkt | Ausgegebene Karten | Besonderheit |
| --- | ---: | --- |
| Cyber Dragon Revolution | 42 | Enthält mehrere doppelte Karten |
| Beware of Traptrix | 48 | Zwei Karten sind jeweils doppelt enthalten |
| Albaz Strike | 51 | 46 Karten plus fünf Token |
| Mechanized Madness | 42 | Vollständige Stückzahlen statt 41 verschiedener Karten |

Offizielle Gegenprüfungen: [Albaz Strike](https://www.yugioh-card.com/en/products/sdaz/), [Mechanized Madness](https://www.yugioh-card.com/en/products/sr10/), [Cyber Strike](https://www.yugioh-card.com/en/products/sdcs/) und [Fire Kings](https://www.yugioh-card.com/en/products/sdfk/). Nicht jedes einzelne Exemplar wurde anhand eines physischen Decks verifiziert; bei Datenkorrekturen zuerst Quellen und bestehende Käufe prüfen.

## Bonuskarten der beiden Sonderfälle

Die Fortsetzung verwendet die zufällige Bonusauswahl als Annahme, passend zum gewünschten realen Deckaufbau. Diese Hub-Auswahl ist gleichverteilt; sie behauptet keine vom Hersteller bestätigten Produktionsquoten.

| Produkt | Fester Inhalt | Zufälliger Zusatz | Gesamt |
| --- | --- | --- | ---: |
| Blue-Eyes White Destiny | 50 Karten, inklusive dreier Blue-Eyes White Dragon | Eine von drei Secret-Rare-Karten | 51 |
| Spirit Charmers | 41 Karten und eine Spielmarke | Eine von vier Ultra-Rare-Karten | 43 |

[Konami: Blue-Eyes White Destiny](https://www.yugioh-card.com/en/products/sdwd/) bestätigt 50 feste Karten und die zusätzliche Karte. Die [offiziellen Ausgaben von Blue-Eyes White Dragon](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=4007&ope=2&page=2&rp=10) führen EN001, EN002 und EN003 auf. Der Datenfeed fasst diese Bildvarianten zusammen; die Stückzahl wird deshalb ausdrücklich auf drei gesetzt. Alle drei möglichen Bonuskarten sind bereits als Ultra Rare im festen Inhalt vorhanden. Der Bonus erhöht genau eine davon um ein Secret-Rare-Exemplar. Hub-Chance je Bonuskarte: 1/3.

[Konami: Spirit Charmers](https://www.yugioh-card.com/en/products/sdsc/) nennt 42 Karten einschließlich der Bonuskarte sowie eine zusätzliche Spielmarke. Die vier Familiar-Possessed-Karten sind als Common garantiert; genau eine kommt zusätzlich als Ultra Rare dazu. Hub-Chance je Bonuskarte: 1/4. Einschließlich Spielmarke ergeben sich 43 ausgegebene Karten.

**Verbleibende Unterschiede zum physischen Produkt:** Eine Quarter-Century-Aufwertung von Blue-Eyes wird derzeit nicht simuliert, weil die Herstellerbeschreibung keine genaue Quote angibt und noch keine eigene Hub-Quote festgelegt ist. Alternative Kartenbilder und die fünf Spielmarken-Motive von Spirit Charmers bleiben in der bestehenden Darstellung je Kartenidentität zusammengefasst. Kartenanzahl und Mehrfachexemplare sind abgebildet; eine vollständige physische Motiv-/Foil-Simulation ist damit nicht behauptet. Diese Hinweise stehen auch vor dem Kauf auf den Deckdetailseiten.

Die Bonusauswahl besitzt eigene Datenbanktabellen. Sie erhöht die feste Gesamtmenge um genau eine Karte pro Bonusplatz, niemals um die Anzahl möglicher Kandidaten. Liste, Suche und Öffnung nutzen dieselbe Validierung. Ein leerer oder widersprüchlicher Bonusplatz sperrt Kauf und Öffnung. Die ausgewählte Karte wird mit der Öffnung gespeichert; eine idempotente Wiederholung liefert dasselbe Ergebnis ohne neue Ziehung.

## Betrieb und Bestandsschutz

Preis und Kaufgrenze kommen aus `backend/app/core/pricing.py`. Eine Transaktion sperrt zuerst das Benutzer-Guthaben und prüft danach den Kaufzähler; Kauf, Abbuchung und Zählererhöhung werden gemeinsam gespeichert. Öffnen verändert den Kaufzähler nicht. Alte Pack-Bestände plus Öffnungen bilden konservativ die bisherige Bezugsmenge, sofern noch kein Zähler existiert. Spätere Vergaben durch einen Admin benötigen einen getrennten Vergabegrund, damit sie keine Käufe darstellen.

Eine Definition enthält Summe, Quelle, Hash, jede feste Kartenstückzahl und gegebenenfalls zusätzliche Bonusplätze. Unvollständige oder widersprüchliche Listen erlauben weder Kauf noch Öffnung. Karten ohne deutsche Texte verwenden wie bisher das Original. Neue Token ohne verfügbare Abbildung zeigen den bestehenden Bild-Ersatzzustand; es werden keine fremden Motive als passende Karte ausgegeben.

Bei einer Korrektur bereits verkaufter Inhalte zuerst entscheiden, ob Altbesitz eine Inhaltsversion benötigt. Der Import überschreibt solche Inhalte deshalb nicht automatisch. Die kompatible Summe pro Kartenidentität bleibt erhalten. Neue Öffnungen führen Seltenheit und Herkunft zusätzlich im [Variantenbestand samt Journal](INVENTORY.md); ungeklärter Altbestand bleibt gekennzeichnet. Physische Illustrations-/Folierungsvarianten werden weiterhin nicht vollständig abgebildet.
