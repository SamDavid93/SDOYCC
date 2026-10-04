# Seltene Funde im Twitch-Chat und Booster-Fortschritt

Stand: 04.10.2026. Die Fundmeldung ist entsprechend der Betreiberentscheidung für den **öffentlichen Twitch-Chat** vorgesehen. Die bestehende Öffnungsanimation auf der Website bleibt erhalten.

## Streamer.bot einmalig einrichten

1. Unter **Actions** eine neue Aktion **SDOYCC Seltene Funde** anlegen.
2. **Core → C# → Execute C# Code** hinzufügen und den vollständigen Inhalt von [RarePullAnnouncements.cs](../integrations/streamerbot/RarePullAnnouncements.cs) einfügen. Wie bei der bisherigen Hub-Aktion die Referenz `System.Net.Http.dll` hinzufügen; auf diesem PC liegt sie unter `G:\StreamerBot\dlls\System.Net.Http.dll`. Kompilieren und speichern. Die vorhandenen persistenten Variablen `hubApiBaseUrl` und `hubApiKey` aus der Setup-Aktion werden wiederverwendet.
3. An dieser Aktion den Trigger **Core → Timed Actions** hinzufügen. Einen Timer mit **Interval: 15 Sekunden**, **Lines: 0**, **Repeat: aktiviert**, **Enabled: aktiviert**, **Random: deaktiviert** erstellen und auswählen. Das Broadcaster-Konto muss mit dem Twitch-Chat verbunden sein.

Keine Änderung an der bestehenden Registrierungs- oder Kanalpunkte-Aktion erforderlich. Die neue Aktion benötigt keine Chat-Benutzerargumente und keinen Befehl. Sie versendet über das Broadcaster-Konto. Die gespeicherte Codekopie in Streamer.bot wird durch Projektdateiänderungen nicht automatisch aktualisiert.

Offizielle Anleitungen: [Timer-Trigger](https://docs.streamer.bot/examples/chat-message-timer), [Timer-Einstellungen](https://docs.streamer.bot/guide/core/timers), [SendMessage](https://docs.streamer.bot/api/csharp/methods/twitch/chat/send-message).

## Welche Funde erscheinen?

Neue erfolgreiche Packöffnungen registrierter Twitch-Konten erzeugen Meldungen ab **Ultraselten** sowie für die hinterlegten Secret-, Ultimate-, Ghost-, Starlight-, Quarter-Century-, Platinum-, Collector- und Gold-Seltenheiten. Common, Rare, Super Rare und unbekannte Seltenheit lösen keine Meldung aus. Maßgeblich ist die tatsächlich gezogene Seltenheit der Pack-Ausgabe.

Die Meldung enthält Twitch-Namen, Kartenname, Seltenheit und Packname. Deutsche Kartennamen werden bevorzugt, sonst der Originalname. Mehrere identische Karten derselben Seltenheit innerhalb einer Öffnung werden zusammengefasst:

> Glückwunsch @Zuschauer! 2 × Beispielkarte [Ultraselten] aus Beispiel-Booster gezogen!

Structure Decks werden ebenfalls berücksichtigt; Mehrfachexemplare erscheinen als gemeinsame Mengenangabe. Garantierte Deckkarten ändern dadurch ihre Ziehungsregeln nicht. Lange Namen werden bei Bedarf für die begrenzte Chat-Nachrichtenlänge gekürzt.

Der Timer verarbeitet höchstens eine Meldung pro Ausführung. Ohne wartende Funde bleibt der Chat still. Nach zehn Minuten werden ungesendete Meldungen nicht mehr abgeholt; nach längerer Offline-Zeit gibt es dadurch keine Flut alter Funde. Frühere Öffnungen werden nicht nachträglich angekündigt.

## Zustellung und Wiederholungen

Öffnung, Inventargutschrift und Vormerkung der Meldung werden in derselben Datenbanktransaktion gespeichert. Eine wiederholte Öffnungsanfrage erzeugt keine zweite Meldung. Streamer.bot reserviert eine Meldung 60 Sekunden lang, übergibt sie an den Chat und quittiert sie danach beim Hub. Der Timer merkt sich die letzten 100 übergebenen IDs persistent, damit ein verlorener HTTP-Bestätigungsaufruf nicht zum normalen Doppelversand führt.

`SendMessage` liefert keine Twitch-Empfangsbestätigung. „Verarbeitet“ im Log bedeutet deshalb Übergabe an Streamer.bot, nicht nachgewiesener Empfang bei Zuschauern. Ein Absturz genau zwischen Chat-Übergabe und lokaler Speicherung kann weiterhin eine Wiederholung verursachen. Bei einer unterbrochenen Chat-Verbindung kann eine Nachricht ausbleiben. Käufe und Kartenbesitz hängen nicht von der Chat-Zustellung ab.

## Sammelfortschritt auf der Website

Booster-Kacheln, Booster-Details und Pack-Tresor zeigen **X von Y Karten gesammelt**, einen Prozentwert und einen Fortschrittsbalken. Gezählt werden unterschiedliche Kartenidentitäten im tatsächlich verfügbaren Pool, die das Konto aktuell mindestens einmal besitzt. Ausgabe, Seltenheit und Herkunft des vorhandenen Exemplars sind dabei unerheblich; Duplikate zählen nicht mehrfach. Durch einen vollständigen Wegtausch kann der Fortschritt wieder sinken.

Bei Structure Decks zählen feste Karten und alle möglichen Bonuskarten jeweils einmal. Mehrfach enthaltene Karten erhöhen den Nenner nicht. Nicht ziehbare Einträge und ungültige bzw. ungeprüfte Pools werden ausgeschlossen. Nach einer Öffnung wird die Anzeige ohne Seiten-Neuladen aktualisiert.

## Prüfung

Backend-Tests prüfen Kontentrennung, Duplikate, Nullbestand, ungültige Pools, Deck-Bonusmöglichkeiten, Fortschritt nach Öffnung, gemeinsame Transaktion, Wiederholungen, parallele Abholung, Ablauf, Schlüssel und Kanalbindung. Vier C#-Ablauftests nutzen ausschließlich einen lokalen simulierten Server und eine nachgebildete CPH-Schnittstelle. Es werden dabei keine echten Twitch-Nachrichten gesendet. Der Code wurde außerdem gegen die lokale Streamer.bot-1.0.7-Schnittstelle kompiliert. Die Timer-Aktion und der Empfang einer echten Fundmeldung müssen in Streamer.bot noch eingerichtet bzw. geprüft werden.
