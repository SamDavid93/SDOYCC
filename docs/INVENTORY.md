# Variantenbestand und Kartenjournal

Arbeitspaket A3 ist umgesetzt. In **Meine Sammlung** lassen sich unter jeder Karte die **Bestandsvarianten** aufklappen. Sie zeigen Stückzahl, belegte Seltenheit, Herkunftspack und verfügbare/reservierte Menge. Das Abzeichen auf dem Kartenbild zeigt die höchste belegte Seltenheit dieser Kartenidentität, nicht die Seltenheit aller Exemplare. „?“ bedeutet: Ausgabe nicht bestimmt.

**Kartenbewegungen anzeigen** öffnet das paginierte persönliche Inventarjournal. Im **Admin-Menü → Kontodetails** stehen die Varianten unter „Kartensammlung“ und das Journal unter „Kartenbewegungen“ bereit. Fremde Bestände und Journale benötigen serverseitig Verwaltungsrechte.

## Bestandsregeln

- `CardVariant`: stabile Kennung aus Karten-ID, Herkunftspack und normalisierter Seltenheit; gesonderte Kennung für ungeklärten Altbestand. Optionales `printing_id` ist derzeit leer, weil Öffnungen keine eindeutig bestimmte physische Ausgabe protokollieren. Es wird keine beliebige Katalogausgabe zugeordnet.
- `VariantInventory`: Menge je Konto, Variante und Bindungsstatus; `reserved` ist nicht größer als `quantity`. Der Handelsbereich reserviert angebotene Kartenpakete und zeigt verfügbare und gebundene Mengen getrennt.
- `InventoryTransaction`: Kartenbewegung mit Variante, Menge, Bestand danach, Grund, stabiler Referenz und Zeitpunkt. Bestehende Buchungen werden nicht überschrieben.
- `InventoryItem` bleibt die kompatible Summe je Konto/Kartenidentität. Neue Öffnungen verändern Variantenmenge, Gesamtsumme, Historie, Pack-Bestand und Aktionsbeleg in derselben Transaktion.
- `change_stock` verarbeitet ganze positive oder negative Mengen unter dem Kontoschreiblock. Identische Referenzen werden einmal gebucht; abweichende Wiederverwendung liefert 409. Abzüge können weder reservierte Exemplare verbrauchen noch negative Bestände erzeugen. Abweichungen zwischen Gesamt- und Variantenbestand werden abgewiesen.
- Structure Decks einschließlich Mehrfachexemplaren und Bonuskarten verwenden denselben Buchungsweg. Die Öffnungswiederholung erzeugt keine zweite Kartenbewegung.

Die Variante beschreibt derzeit eine **Hub-Herkunft und Seltenheit**, nicht eine vollständig bestimmte physische Druckausgabe, Sprache, alternative Illustration oder Folierung. Unterschiedliche Herkunftspacks werden getrennt geführt. Diese Unterscheidung ist für späteren Handel sichtbar zu erhalten und darf nicht stillschweigend als identische physische Ausgabe behandelt werden.

## Übernahme vorhandener Karten

Pro Konto und Kartenidentität wird der Gesamtbestand mit der vollständigen Öffnungshistorie verglichen:

1. Stimmen die Mengen exakt überein und sind die Seltenheiten angegeben, erfolgt eine Mengenrekonstruktion nach Herkunftspack und Seltenheit.
2. Bei fehlender Historie, Übermenge, Restbestand oder unklaren Seltenheiten bleibt die gesamte betreffende Altmenge als **Altbestand – Ausgabe nicht bestimmt** erhalten. Es wird keine beliebige Teilmenge oder höchste Seltenheit ausgewählt.
3. Neue Öffnungen ergänzen ab dann eindeutig gebuchte Varianten, auch neben ungeklärtem Altbestand.

Die Rekonstruktion beruht auf der vorhandenen Hub-Historie und übereinstimmenden Mengen. Sie ist kein zusätzlicher Nachweis für historische manuelle Datenbankänderungen. Übernahmebuchungen tragen das Migrationsdatum; sie sind keine neuen Gewinne und verändern keine historischen Öffnungen.

Wiederholte Migrationen verändern bereits aufgeteilte Bestände nicht. Stimmen bestehende Variantenmengen nicht mehr mit der kompatiblen Gesamtsumme überein, bricht die Prüfung ab, statt die Daten automatisch neu zu klassifizieren.

## Betrieb und Prüfung

Vor einer Erstübernahme Backend stoppen und sichern. Im Projektverzeichnis:

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python.exe backend/scripts/migrate_database.py
.venv/Scripts/python.exe backend/scripts/migrate_inventory.py
.venv/Scripts/python.exe backend/scripts/migrate_inventory.py --apply
```

Ohne `--apply` wird die Vorschau vollständig zurückgerollt. Beim Backendstart wird nach Demo-/Katalogeinrichtung dieselbe wiederholbare Bestandsübernahme ausgeführt. Neue Benutzer mit noch leerem Inventar benötigen keine Übernahmebuchung. Bei Bestandsabweichungen Quelle und vorhandene Journale prüfen; keine Tabellen löschen, um den Fehler zu umgehen.

Prüfkriterium je Konto und Karte: **Summe der Variantenmengen = bisheriger Gesamtbestand**. Zusätzlich muss die Summe aller Journalbewegungen je Konto/Variante/Bindungsstatus deren aktuellen Bestand ergeben. Die Produktionsprobe in einer isolierten Kopie ergab 70 rekonstruierte und 37 ungeklärte Exemplare; alle 107 Exemplare blieben erhalten. Bericht: `artifacts/variants-rehearsal.json`.

## Schnittstellen

- `GET /api/collection`: `card.owned_variants` liefert die Varianten je angezeigter Karte. Seltenheitsfilter berücksichtigen tatsächlichen Variantenbesitz; `unknown` findet ungeklärten Bestand. Der Kartenset-Filter bleibt ein Katalogfilter und ist kein Nachweis einer besessenen Druckausgabe.
- `GET /api/inventory/me/journal`: eigene Bewegungen, neueste zuerst.
- `GET /api/admin/users/{id}/inventory`: Kartenmengen mit `variants`.
- `GET /api/admin/users/{id}/inventory-journal`: fremdes Journal mit Verwaltungsrechten.

Journale liefern `items`, `total`, `page`, `page_size`; standardmäßig 25, höchstens 100 Einträge. Für Variantenlisten werden nur die Karten der aktuellen Ergebnisseite geladen. Historische Öffnungen werden für normale Sammlungsabfragen nicht mehr vollständig ausgewertet.

A4/A5 sind inzwischen umgesetzt: [Vergaben für Punkte, Kartenvarianten und Packs](GRANTS.md). Handel und Saisonbelohnungen verwenden inzwischen diese gemeinsame Buchungsgrundlage; siehe [Abschlussstand](FINAL_STATUS.md).
