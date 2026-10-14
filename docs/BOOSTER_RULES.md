# Booster-Ziehungsregeln

Normale Booster enthalten neun Karten: acht gewichtete Ziehungen aus dem
vollständigen gültigen Pool und eine gewichtete Ziehung aus Rare oder höher.
Mehrfachexemplare sind möglich. Seltenheiten werden vom tatsächlichen
Pooleintrag übernommen; unbekannte Seltenheiten zählen nicht als Rare.

Die bisherige Standardkonfiguration `cards_per_pack=5` wird zur Laufzeit wie
`9` behandelt. Neue Standardpacks werden mit `9` angelegt. Dadurch gilt die
Änderung auch für bereits gekaufte, noch ungeöffnete Standardpacks, ohne
Inventar, Packbestände oder vergangene Öffnungen umzuschreiben.

Structure Decks behalten ihre geprüften festen Decklisten, Mehrfachexemplare,
Bonusplätze und Kauflimits. Abweichende Packgrößen behalten ihre bisherigen
Ziehungsregeln; `0` bleibt gesperrt.

Fehlen gültige Rare-oder-höher-Einträge, ist ein Standardbooster nicht kaufbar
oder zu öffnen. Die Oberfläche zeigt den Prüfstatus; Punkte und Packbestände
werden dabei nicht verbraucht. Solche Pools müssen anhand ihrer tatsächlichen
Set-Seltenheiten berichtigt werden, statt Karten künstlich hochzustufen.

Prüfung des bestehenden lokalen Katalogs am 14.10.2026: 962 Standardbooster,
davon 145 ohne bekannte Rare-oder-höher-Auswahl; 59 Structure Decks unverändert.

## Hauptadministrator: Preise und Kartenanzahl

Im Admin-Menü unter **Preise & Packinhalt verwalten** ein Produkt suchen und
**Anpassen** wählen. Preise sind ganzzahlig von 0 bis 1.000.000 Sammelpunkten;
Booster können individuell 1 bis 100 Karten enthalten. Bei einer individuellen
Anzahl bleibt eine Rare oder höher garantiert. Structure Decks erlauben nur
Preisänderungen; feste Inhalte und Bonusplätze bleiben unverändert.

Leere Felder beziehungsweise **Auf Standard zurücksetzen** entfernen die
individuellen Einstellungen nach der Bestätigung. Jede Änderung erfordert die
bestehende Hauptadmin-Passwortbestätigung samt Begründung und schreibt einen
Beleg mit Vorher-/Nachher-Werten. Andere Adminrollen dürfen weder lesen noch
ändern. Veraltete Änderungen werden abgewiesen; Wiederholungen derselben
bestätigten Anfrage erzeugen keine doppelten Belege.

`price_override` und `draw_count_override` sind separate nullable Datenbankfelder,
die beim Start additiv ergänzt werden. Katalogimporte überschreiben sie nicht.
Preisänderungen betreffen neue Käufe, Änderungen der Kartenanzahl zukünftige
Öffnungen einschließlich bereits gekaufter Packs. Frühere Öffnungen,
Guthaben, Bestände und Kauflimits werden nicht umgeschrieben.
