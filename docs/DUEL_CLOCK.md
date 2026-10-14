# Duellzeit und bedienbare Entscheidungen

Jeder Spieler hat weiterhin 360 Sekunden. Nur die vom Regelkern angeforderte
Entscheidung verbraucht Zeit. Der andere Spieler erhält 50 Prozent dieser
verbrauchten Entscheidungszeit zurück, höchstens bis 360 Sekunden. Ein Zugwechsel
setzt das Budget nicht zurück. Die separate Side-Deck-Frist bleibt 180 Sekunden.

Die menschliche Entscheidungszeit beginnt erst, wenn die authentifizierte
Duellverbindung `decision_ready` für die aktuelle Prompt-ID und Board-Revision
gemeldet hat. Das Frontend meldet dies nach dem Rendern der bedienbaren Auswahl.
Zusätzlich müssen alle vorausgehenden sichtbaren Ereignisse einschließlich
Zugende, Phasenwechsel und Kettenauflösungen vollständig abgespielt sein.
Vorher bleiben Feldaktionen, Auswahlfenster, Rechtsklick und automatische
Antworten gesperrt. Die Freigabe prüft den Wiedergabestand gegen die neueste
Ereignis-ID und das aktuelle Spiel innerhalb eines Matches. Eine früh empfangene
Standby-Entscheidung kann dadurch nicht während der Darstellung des vorherigen
gegnerischen Zugs beantwortet werden. Auch `decision_ready` wartet auf diesen Stand.
Die Serverantwort enthält `ready_ack`, niemals die Aktionsquittung `ack`.
`clock.readiness_required` kennzeichnet dieses Protokoll; `waiting_for` und
`ready_timeout` beschreiben die noch ausstehende Darstellung.

Die Bestätigung gilt nur für den berechtigten Sitz, dessen ursprüngliche Anmeldung
und dessen aktuelle WebSocket-Verbindung. Veraltete oder fremde Bestätigungen
ändern die Freigabe nicht. Doppelte Bestätigungen setzen keine Zeit zurück.
Eine gültige Spielantwort stoppt die Zeit beim Eingang auf dem Server;
Autorisierungs-, Regelkern- und Übertragungsarbeit zählt nicht als Denkzeit.
Deterministische leere Kettenfenster werden ohne Spielerzeit beantwortet.
Die Test-KI benötigt keine Browserbestätigung und verbraucht nur ihre eigene
Entscheidungszeit. Bereits bedienbare Entscheidungen erhalten keine zusätzliche
Zeit durch rein dekorative, von der Ereigniswiedergabe unabhängige Effekte.

Effektauswahlen nennen die vom Regelkern übermittelte Effektkarte beziehungsweise
die Karte des aktuell aufgelösten Kettenglieds. Der verfügbare Engine-Effekttext
oder Auswahlhinweis steht daneben; andernfalls dient der Kartentext als Rückfall.
Der linke Viewer folgt dieser Quelle und kann durch Anklicken einer Auswahlkarte
zum Nachlesen gewechselt werden. Das horizontale Auswahlfenster liegt transparent
auf der eigenen Spielfeldhälfte. Gegnerische Aktivierungen aktualisieren den
Viewer erst mit ihrem Wiedergabeereignis; eigene behalten ihre direkte Anzeige.

Die Anzeige sitzt als großer Kreis links auf Höhe der Spielfeldmitte gegenüber
der Phasenanzeige. Sie zeigt die eigene Zeit in Minuten und Sekunden, darunter
die gegnerische Zeit. Nur der serverseitig aktive Spieler zählt lokal sichtbar
herunter; bei Verarbeitung oder Wiederverbindung steht die Anzeige auf Pause.
Eingehende Zeitgutschriften werden ausschließlich aus bestätigten Serverständen
übernommen. Die beiden Extra-Monsterzonen behalten ihre festen Positionen.
Bei einem neuen Match-Spiel wird die neue Board-Revision auch dann übernommen,
wenn der Regelkern seine Zählung neu beginnt. Auswahl, Animationen und
Zeitfreigabe wechseln gemeinsam ins neue Spiel.

Jede Entscheidung besitzt insgesamt 30 Sekunden zusätzliche Transportfrist für
Darstellung und Wiederverbindung. Diese Frist wird vom Server gemessen und durch
erneute Verbindungen nicht zurückgesetzt. Fehlt die Bestätigung zu lange, wird
das Duell mit dem vorhandenen neutralen Grund `timeout` beendet; das ist keine
Niederlage wegen verbrauchter Entscheidungszeit.

Eine unterbrochene Verbindung wird erst durch Empfangs-/Sendefehler oder den
bestehenden 20-Sekunden-Heartbeat erkannt. Bei der Erkennung wird unbestätigte
Zeit seit dem letzten serverseitig empfangenen Client-Frame zurückgegeben,
höchstens im Rahmen der restlichen Transportfrist. Die tatsächlich dafür
gutgeschriebene gegnerische Zeit wird ebenfalls zurückgenommen, auch wenn dessen
Budget zwischenzeitlich 360 Sekunden erreicht hatte. Die zurückgegebene Zeit
verbraucht die Transportfrist; wiederholtes Trennen erzeugt keine unbegrenzte
Zusatzzeit. Client-Zeitstempel oder frei wählbare Pausen werden nicht akzeptiert.

Erreicht eine noch unbestätigte Verbindung rechnerisch null Sekunden, wird das
Ergebnis erst nach erneuter beobachteter Client-Aktivität festgestellt. Dadurch
kann eine erkannte Unterbrechung zuerst korrekt verrechnet werden. Ohne erneute
Aktivität greifen die begrenzte Transportfrist und die bestehende Bereinigung.
Eine eingehende Antwort oder ein Heartbeat bestätigt die Verbindung; ein nach
Ablauf eingegangener Spielzug verhindert die Zeitniederlage nicht.

Prüfungen:

```powershell
$env:PYTHONPATH='backend;backend/tests'
& '.\.venv\Scripts\python.exe' -m unittest test_duel_clock test_duel_worker test_duel_matches test_duel_practice -v
```

Abnahme vom 14.10.2026: 293 Backendtests, 51 Protokolltests, vollständige
Präsentationsprüfung, gezielte Timer-/Match-Wechselprüfung, natives
Zwei-Spieler-Duell und natives KI-Testduell bestanden. Nachweise unter
`artifacts/duel-timer-*`. Die nativen Browserprüfungen erlauben 360 Sekunden
Startfrist für die Integritätsprüfung der Engine-Dateien; Spielentscheidungen
erhalten dadurch keine anderen Testgrenzen.
