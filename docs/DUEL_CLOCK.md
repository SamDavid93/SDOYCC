# Duellzeit und bedienbare Entscheidungen

Jeder Spieler hat weiterhin 360 Sekunden. Nur die vom Regelkern angeforderte
Entscheidung verbraucht Zeit. Der andere Spieler erhält 50 Prozent dieser
verbrauchten Entscheidungszeit zurück, höchstens bis 360 Sekunden. Ein Zugwechsel
setzt das Budget nicht zurück. In jeder eigenen Standby Phase wird die seit der
vorherigen eigenen Standby Phase erhaltene Gutschrift auf mindestens 60 Sekunden
ergänzt, weiterhin gedeckelt bei 360 Sekunden. Höhere 50-Prozent-Gutschriften
bleiben erhalten. Die Ergänzung erfolgt genau einmal pro Zug, auch wenn die
Engine bereits bis zur Hauptphase weitergelaufen ist. Die separate
Side-Deck-Frist bleibt 180 Sekunden.

Bei laufender eigener Entscheidungszeit ertönen Warnsignale bei 60 und 30
Sekunden, danach bei jeder verbleibenden Sekunde bis 1. Pausen wiederholen
keinen Ton. Die Duell-Lautstärke und Stummschaltung gelten auch für diese Signale.

Bei der Platzwahl nennt `placement_card` die tatsächliche Zielkarte aus dem
rohen Engine-Auswahlhinweis. Die große mittige Anzeige bleibt bis zur Auswahl
sichtbar und fängt keine Mausklicks auf erlaubte Zonen ab. Die Effektkarte wird
nicht als vermeintlich zu platzierende Karte verwendet.

Deutsche Systemhinweise stammen aus der zur Engine passenden
[Project-Ignis-Sprachdatei](https://github.com/ProjectIgnis/Distribution/blob/54a6e2395c532648ff762540e9615319fac4f51b/config/languages/Deutsch/strings.conf).
Kurze Effektoptionen erhalten deutsche Beschreibungen. Fehlt deren Übersetzung,
erscheint der verfügbare deutsche Kartentext ausdrücklich als Kontext und die
Originalbeschreibung kann zusätzlich aufgeklappt werden. Die Reihenfolge der
Kartentextsätze wird niemals als Zuordnung zu Engine-Effektkennungen geraten.

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

Jede angebotene Karte zeigt ihren tatsächlichen Herkunftsort aus
`choice.location.zone` als Symbol und Beschriftung. Gleiche Kartencodes in Hand,
Friedhof, Deck oder Verbannt bleiben getrennte Optionen mit ihrem ursprünglichen
Engine-Antwortindex. Fremde Orte tragen zusätzlich „Gegner“. Die Herkunft wird
nicht aus Kartentext oder Effektziel abgeleitet. Beim Anklicken übernimmt der
Viewer den Ort genau dieses Exemplars; eine allgemeine Liste erwähnter
Effektbereiche wird dort nicht mehr angezeigt.

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
