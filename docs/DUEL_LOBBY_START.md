# Vereinfachter Lobby-Start

1. Der Gastgeber wählt sein Deck und erstellt die Lobby.
2. Der Gast tritt über den Lobby-Code bei; der Gastgeber nimmt ihn an.
3. Der Gast wählt sein Deck im Auswahlfeld. Die Auswahl wird sofort gespeichert.
4. Der Gastgeber klickt **Match starten**. Beide Spieler wechseln automatisch ins Duell.

Separate Buttons zum Speichern der Deckauswahl, zur Deckbestätigung und zur Zustimmung zum Duellstart entfallen. Der leere Eintrag im Auswahlfeld nimmt die eigene Bereitschaft zurück. Die andere Person muss ihr unverändertes Deck dann nicht erneut auswählen.

Eine Auswahl ist an Benutzer, ursprüngliche Anmeldung, Lobby, Regelprofil, Deck und Deckversion gebunden. Die Annahme des Gastes bleibt erforderlich. Regeln und verfügbarer Kartenbestand werden bei der Auswahl geprüft und vor der atomaren Reservierung erneut geprüft. Nur der Gastgeber kann starten. Wartung, Kapazitätsgrenzen, Teilnahme- und Regelfreigaben bleiben wirksam.

Die vorhandenen Bestätigungs- und Zustimmungsdatensätze speichern die Auswahlberechtigung; eine Datenbankmigration ist nicht erforderlich. Alte API-Aufrufe bleiben kompatibel. Eine Auswahl mit `ready: true` erteilt beide Berechtigungen für das eigene Deck. Sie startet keinen Worker und reserviert keine Karten. Der Gastgeber-Start verwendet weiterhin den bestehenden Startendpunkt.

Nachweise: `artifacts/duel-simple-start-tests.log`, `artifacts/duel-simple-start-new-tests.log`, `artifacts/duel-simple-start-native.log`, `artifacts/duel-simple-start-decks-browser.log` und `artifacts/duel-simple-start-backend.log`. Der native Browserlauf prüft den Start mit zwei Testkonten ohne weitere Bestätigungsbuttons sowie Zurücknehmen und erneutes Auswählen. Alle Testbestände stammen aus temporären Datenbanken.
