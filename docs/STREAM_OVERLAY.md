# Kartenfunde im Stream-Overlay

Die Ziehungs-Alerts erscheinen im Overlay statt im Twitch-Chat. Registrierung, Kanalpunkte und Öffnungsanimation auf der Website funktionieren weiter wie bisher.

## OBS einrichten

Auf dem PC mit dem Backend eine **Browserquelle** hinzufügen:

- URL: `http://127.0.0.1:8002/api/stream-overlay/rare-pulls`
- Breite **1920**, Höhe **1080** (oder die tatsächliche Stream-Auflösung).
- Quelle über der Spielaufnahme anordnen. Der Hintergrund ist transparent; Alerts erscheinen mit 32 Pixeln Abstand unten links.
- **Quelle deaktivieren, wenn sie nicht sichtbar ist** aktivieren, damit unsichtbare Szenen keine Funde verbrauchen.
- Dieselbe vorhandene Quelle in weiteren Szenen verwenden, statt mehrere unabhängige Quellen anzulegen.

Die Quelle verwendet eine URL, keine lokale HTML-Datei. Sie braucht weder Anmeldung noch Streamer.bot-Schlüssel und ist ausschließlich direkt auf dem Server-PC erreichbar. Zugriffe über den öffentlichen Tunnel und von fremden Webseiten werden abgewiesen. [Offizielle OBS-Anleitung](https://obsproject.com/kb/browser-source).

**Vorschau ohne Kauf:** `http://127.0.0.1:8002/api/stream-overlay/rare-pulls?preview=1` zeigt einmal einen Beispiel-Alert, ohne Meldungen abzuholen oder Kontodaten zu verändern. Für den Live-Betrieb die URL ohne `?preview=1` verwenden.

## Anzeige und Zustellung

Die bisherige Auswahl bleibt erhalten: neue Funde registrierter Twitch-Konten ab **Ultraselten**, einschließlich der hinterlegten Secret-, Ultimate-, Ghost-, Starlight-, Quarter-Century-, Platinum-, Collector- und Gold-Seltenheiten. Common, Rare, Super Rare und unbekannte Seltenheiten erzeugen keinen Alert. Structure Decks werden ebenfalls berücksichtigt.

Ein Alert zeigt Kartenbild, Zuschauername, Kartenname, Menge, Seltenheit und Packname. Deutsche Namen werden bevorzugt. Identische Karten derselben Seltenheit aus einer Öffnung werden zusammengefasst. Bilder verwenden dieselben hochwertigen Originalabbildungen und deutschen Ersatzbilder wie der Katalog. Fehlen beide, bleiben die Textinformationen sichtbar.

Alerts erscheinen nacheinander für jeweils etwa **8,5 Sekunden**. Ohne Funde bleibt die Quelle transparent. Nicht abgeholte Funde verfallen nach zehn Minuten; frühere Öffnungen werden nicht nachträglich angekündigt. Bei Backend-Ausfällen versucht die Quelle automatisch erneut, die Verbindung herzustellen.

`RARE_PULL_DELIVERY=overlay` ist der Standard. Der bisherige Streamer.bot-Timer erhält damit keine neuen Meldungen und kann zusätzlich deaktiviert werden. `RARE_PULL_DELIVERY=chat` stellt bewusst die alte Zustellung wieder her und deaktiviert die Overlay-Abholung. Andere Chat-Aktionen sind davon unabhängig.

Öffnung, Inventargutschrift und Meldung werden gemeinsam in einer Datenbanktransaktion gespeichert. Wiederholte Öffnungsanfragen erzeugen keinen zweiten Alert. Die Browserquelle reserviert einen Fund 60 Sekunden und bestätigt ihn nach der Anzeige. Die letzten 200 angezeigten IDs werden lokal gespeichert, um bei verlorenen Bestätigungen und beim Neuladen Doppelanzeigen zu vermeiden. Bei einem Absturz während der Anzeige kann ein Fund erneut erscheinen. Eine Anzeige in OBS beweist nicht den Empfang beim Zuschauer.

## Prüfung

Backend-Tests prüfen Transaktion, Ablauf, parallele Abholung, Umleitung, Metadaten und die Sperre für öffentliche und fremde Zugriffe. `backend/tests/stream_overlay_browser_checks.py` prüft die echte HTML-Quelle mit simulierten Meldungen: Transparenz, Position, Ersatzbild, Menge, Bestätigung, Duplikatschutz und Neuladen. Diese Prüfungen senden keine Twitch-Nachrichten und verändern keine Benutzerbestände.
