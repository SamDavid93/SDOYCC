# Crafting und Zerlegen

Spieler erreichen die Werkstatt unter `/#/crafting`, die Verwaltung unter
`/#/admin/crafting`. Auch Sammlung, Kartenansicht und Inventardetails verlinken
auf die passende Karte beziehungsweise Druckversion.

## Wirtschaft und Bedienung

Jede bereits gepflegte, normalisierte Rarität erhält eine eigene CP-Währung.
Der Startwert beträgt 10 CP beim Zerlegen und 30 CP beim Herstellen. Es gibt
keine Umwandlung zwischen Währungen und keine Verwendung im normalen Shop.
`other` bleibt zunächst deaktiviert. Neue Zuordnungen müssen auf tatsächlich
vorhandenen Katalograritäten beruhen; Beispielraritäten werden nicht angelegt.

Die Werkstatt zeigt konkrete Druckversionen samt Set, Rarität, Besitz, freien
Exemplaren und Kosten. Suche und Filter berücksichtigen auch Kartentyp,
Archetyp, bezahlbare Karten und Duplikate. Die Bestätigung verwendet immer
ein serverseitiges Angebot mit den tatsächlichen Vorher-/Nachher-Werten.
Veraltete Angebote werden zurückgewiesen und müssen neu geprüft werden.

Favoriten und geschützte Mengen gelten pro Druckversion. Standardmäßig bleibt
mindestens ein Exemplar erhalten; die persönliche Einstellung lässt sich ändern.
Die Sammelzerlegung behält standardmäßig drei Exemplare und zeigt vor der
Bestätigung Karten und CP-Erträge je Währung. Gebundene Karten, unbekannte
Legacy-Raritäten und begrenzte Sonderkarten werden nicht zerlegt.

## Besitz und Migration

`variant_inventory` ist der kanonische Bestand. Er enthält jetzt direkt
`card_printing_id`; `variant_id` bewahrt zusätzlich Herkunft und bestehende
Reservierungsbezüge. `inventory_items` bleibt eine abgeleitete Zusammenfassung
nach Karte für Sammlung und Deckbau, kein zweiter unabhängiger Bestand.

Die additive Migration erhält Bestands- und Reservierungs-IDs sowie Mengen.
Eindeutige vorhandene Druckversionen werden verknüpft. Bei mehrdeutigen alten
Beständen entsteht eine lokale Druckversion mit den belegbaren Metadaten;
Edition, Sprache oder Seltenheit werden nicht erfunden. Unbekannte Raritäten
bleiben für Crafting gesperrt.

Vor einer Veröffentlichung kann die Migration gefahrlos auf einer Onlinekopie
der SQLite-Datenbank geprüft werden:

```powershell
$env:PYTHONPATH='backend'
& .\.venv\Scripts\python.exe backend/scripts/check_crafting_migration.py
```

Das Ergebnis liegt unter `artifacts/crafting-migration-audit.json`.
Die Produktionsdatenbank wird von diesem Prüflauf nicht verändert.

## Transaktionen und Administration

CP-Buchung, Bestandsänderung, Historie und Ereignisse erfolgen atomar unter den
gemeinsamen Benutzersperren. Handels- und Duellreservierungen sowie gebundene
und geschützte Mengen begrenzen die Zerlegung. Wiederholte Requests verwenden
Idempotenzschlüssel. Die Datenbank erzwingt nichtnegative Guthaben.

Die Verwaltung bietet Kennzahlen, Raritätsregeln, Buchungen, Spielerguthaben und
Betriebsschalter. Änderungen benötigen gemäß bestehender Eigentümerrichtlinie
Administratorpasswort und Begründung und werden auditiert. Regelversionen
verhindern das Überschreiben paralleler Änderungen. Kosten müssen über dem
Zerlegeertrag liegen. Tageskennzahlen sind ausdrücklich in UTC angegeben.

Spieler-API unter `/api/crafting`: `balances`, `rules`, `filters`, `cards`,
`cards/{printing_id}`, `preview`, `craft`, `dismantle`, `history`, `settings`,
`cards/{printing_id}/preference`, `duplicates/preview`, `duplicates/dismantle`.
Verwaltungs-API unter `/api/admin/crafting`: `rules`, `rules/{id}`,
`transactions`, `users/{id}/balances`, `users/{id}/adjust`, `stats`, `settings`.

## Belohnungen und Saisonmissionen

Der zentrale Grant-/Reward-Weg unterstützt `kind: crafting_currency` mit
`currency_key` und `quantity`; es gibt keinen parallelen Belohnungsdienst.
Er schreibt ebenfalls die Crafting-Buchungshistorie.

Persistierte Ereignisse heißen `card_dismantled`, `card_crafted`,
`crafting_currency_earned` und `crafting_currency_spent`. Saisonmissionen können
`dismantle_card`, `craft_card`, `craft_rarity`, `earn_crafting_currency` und
`spend_crafting_currency` zählen. Diese Missionen vergeben keine normalen XP;
administrative Guthabenkorrekturen erzeugen keinen Missionsfortschritt.

## Prüfung

`backend/tests/test_crafting.py` prüft Transaktionen, konkurrierende Ausgaben,
Reservierungen, Schutz, Migration, Administration, Belohnungen und Missionen.
`backend/tests/crafting_browser_checks.py` prüft die echte Oberfläche gegen
eine isolierte Testdatenbank, einschließlich Mobilansicht und Adminabläufen.
