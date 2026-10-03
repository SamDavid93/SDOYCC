# Streamer.bot 1.0.7: öffentliche Registrierung

Der Hub nutzt öffentliche Chat-Antworten und eine Bestätigung durch das tatsächliche Twitch-Konto. Es gibt keine Flüsternachrichten mehr. Ein separates Bot-Konto und die Telefonbestätigung für Whispers werden für diesen Ablauf nicht benötigt. Der verbundene Broadcaster sendet die Chat-Antworten.

## Bereits vorhandene Aktionen aktualisieren

1. In **TCG Register** die C#-Subaktion öffnen und den gesamten Code durch [TradingHub.cs](TradingHub.cs) ersetzen. **Find Refs**, dann **Save and Compile**.
2. Unter **Commands** zusätzlich `!confirm` anlegen. Modus **Starts With**, Quelle **Twitch Message**. Dadurch enthält `rawInput` nur den Code hinter dem Befehl. Keine Regex und keinen Benutzernamen als Parameter verwenden.
3. In **TCG Register** einen zweiten Trigger **Core > Commands > Command Triggered** hinzufügen und den neuen `!confirm`-Befehl auswählen. Der vorhandene `!register`-Trigger bleibt bestehen. Der Code unterscheidet beide Befehle automatisch; das vorhandene Argument `hubAction=register` kann bleiben.
4. Den Chat-Trigger aus **TCG Setup** entfernen. Setup wird nur manuell ausgeführt. Den Code dort durch [SetupTradingHub.cs](SetupTradingHub.cs) ersetzen; vorhandene globale Variablen bleiben gültig.
5. Backend nach Python-Änderungen neu starten und die Hub-Seite neu laden. Für die aktuelle Umstellung wurde das lokale Backend durch den Assistenten neu gestartet.

Für eine neue Einrichtung zuerst die Setup-Aktion aus dem folgenden Abschnitt ausführen und danach `!register` und `!confirm` wie oben mit derselben Registrierungsaktion verbinden. `!register` kann **Exact** oder **Starts With** verwenden. Geeignete Nutzer-Cooldowns sind 30 Sekunden für `!register` und 5 Sekunden für `!confirm`.

## Ablauf testen – auch als SamDavidOfficial

1. Backend und Frontend über `start-backend.bat` und `start-frontend.bat` starten, sofern sie nicht bereits laufen.
2. Im Twitch-Chat `!register` eingeben.
3. Die öffentliche Antwort enthält beispielsweise `http://localhost:5173/#/register/samdavidofficial`.
4. Diesen Link auf dem Server-PC öffnen und **Bestätigungscode erstellen** anklicken.
5. Den angezeigten Befehl, zum Beispiel `!confirm A12B34C56D`, mit demselben Twitch-Konto im Chat senden.
6. Die bereits geöffnete Seite wird automatisch freigeschaltet. Passwort mit mindestens 12 Zeichen setzen.
7. Abmelden und normal mit Twitch-Benutzername und Hub-Passwort anmelden.

Verwende ausschließlich den Code, den du selbst im eigenen Browser angefordert hast. Ein Code aus dem Chat oder von einer anderen Person kann zu deren Browser gehören. Der öffentliche Registrierungslink selbst enthält kein Geheimnis. Der Server verlangt sowohl die Bestätigung durch die zugeordnete Twitch-ID als auch den geheimen Browser-Schlüssel. Dieser Schlüssel bleibt im `sessionStorage` des Browsers und wird weder im Link noch im Chat ausgegeben.

Andere Nutzer können einen öffentlich sichtbaren Code nicht für sich bestätigen. Der Code allein erlaubt weder Passwortsetzung noch Anmeldung. Nach erfolgreicher Registrierung werden alle offenen Bestätigungen dieses Kontos gelöscht. Bestätigungen sind standardmäßig 30 Minuten gültig; eine erneute Chat-Bestätigung für einen anderen Browser ersetzt die vorherige. Reine Seitenaufrufe oder neue Code-Anfragen entziehen einem bereits bestätigten Browser nicht seine Freigabe.

Ein bestehendes Passwort wird nie über `!register` oder `!confirm` überschrieben. Passwort-Wiederherstellung ist noch nicht implementiert. Alte private Registrierungslinks werden nicht mehr zur Passwortsetzung akzeptiert.

## Setup und Verbindungsschlüssel

Eine manuelle Aktion **TCG Setup** ohne Chat-Trigger anlegen. **Core > C# > Execute C# Code** hinzufügen und [SetupTradingHub.cs](SetupTradingHub.cs) einfügen, kompilieren und die Aktion einmal manuell ausführen.

Der Code liest `G:\Yugioh Online Trading Card\.env`. Bei einem anderen Pfad vorher das Argument `hubEnvPath` auf den vollständigen `.env`-Pfad setzen. Er prüft das Backend und den verbundenen Broadcaster und speichert diese persistenten globalen Variablen:

| Variable | Wert |
| --- | --- |
| `hubApiBaseUrl` | `http://127.0.0.1:8002/api` |
| `hubApiKey` | `STREAMERBOT_API_KEY` aus der lokalen `.env` |

Erfolgsmeldung im Log: **Backend und Kanal geprueft; Verbindungseinstellungen gespeichert**. Die Setup-Aktion sendet keine Nachrichten. Der Schlüssel gehört nur in Backend und Streamer.bot, niemals in Chat, Frontend oder GitHub. Nach einer Schlüsseländerung Backend neu starten und Setup erneut ausführen.

## C#-Referenzen

Bei fehlendem `HttpClient` oder `System.Net` im Editor **Find Refs** und danach **Compile** anklicken. Falls nötig im Reiter **References** rechtsklicken und fehlende DLLs manuell hinzufügen:

```text
G:\StreamerBot\dlls\System.Net.Http.dll
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.dll
G:\StreamerBot\Newtonsoft.Json.dll
```

Die HTTP-DLL wurde aus dem lokalen Windows-.NET-Verzeichnis kopiert. Referenzen gelten pro C#-Subaktion. Änderungen an Dateien im Projekt aktualisieren die zuvor eingefügte Codekopie in Streamer.bot nicht automatisch.

## Kanalpunkte-Belohnung

In `.env` die tatsächliche `TWITCH_REWARD_ID` aus Streamer.bot eintragen; `TWITCH_REWARD_COST=1000` und `TWITCH_REWARD_DIAMONDS=100` bleiben bestehen. Backend anschließend neu starten.

Eine eigene Aktion **TCG Kanalpunkte** erstellen:

- Trigger **Twitch > Channel Reward > Reward Redemption** und **Reward Redemption Updated**, beide auf genau diese Belohnung begrenzen.
- Subaktion **Set Argument**: `hubAction=reward`.
- Danach denselben aktuellen Code aus `TradingHub.cs` ausführen.

Die Argument-Subaktion muss vor der C#-Subaktion stehen. Beide Trigger ausdrücklich auf **100 TCG DIAMONDS**, ID `49f31d1c-3709-43a7-9ccf-1248b126b05b`, setzen. Eine eingetragene Reward-ID im Backend allein erstellt noch keinen Trigger in Streamer.bot.

Die Gutschrift erfolgt **direkt beim ersten Reward-Redemption-Ereignis**, auch wenn Twitch noch `unfulfilled` meldet. Erst nach der gespeicherten Gutschrift ruft der Code `CPH.TwitchRedemptionFulfill(rewardId, redemptionId)` auf. Damit wird die Einlösung als erfüllt markiert und aus der Warteschlange entfernt. Das Updated-Ereignis oder eine Wiederholung bucht keine weiteren Tradingpoints.

Für das automatische Erfüllen muss die Belohnung ursprünglich in Streamer.bot erstellt worden sein; **Redemptions Skips Queue** kann dabei deaktiviert bleiben. Bei einer im Twitch-Dashboard erstellten Belohnung kann alternativ dort **Warteschlange überspringen** aktiviert werden: Twitch erfüllt dann unmittelbar, die Gutschrift erfolgt beim ersten Event. Die bestehende Reward-ID kann bei dieser Einstellungsänderung erhalten bleiben. Wird die Belohnung stattdessen in Streamer.bot neu erstellt, müssen die neue ID in .env und beide Trigger angepasst werden.

Die automatische Erfüllung wird nur nach bestätigter Gutschrift angefordert. Bei einem Backend-Fehler bleibt die Einlösung offen. Schlägt nur der Twitch-Abschluss fehl, bleibt die Gutschrift erhalten und Chat/Log melden den offenen Abschluss. Eine Wiederholung des Originalereignisses mit derselben Einlösungs-ID versucht den Abschluss erneut, ohne nochmals gutzuschreiben. Bei aktivem **Warteschlange überspringen** gibt es bei einem Hub-Ausfall dagegen keinen offenen Queue-Eintrag als Nachholhilfe.

Eine schon vor Einrichtung der Aktion erfolgte Einlösung wird nicht automatisch erneut zugestellt. Ist sie noch offen, nach Einrichtung beider Trigger in Twitch als erfüllt markieren. Ist sie bereits erfüllt, muss das ursprüngliche Ereignis mit seiner echten Einlösungs-ID wiederholt oder separat abgeglichen werden; keine erfundene neue ID verwenden.

Jede gültige Einlösungs-ID bringt genau einmal 100 Tradingpoints. Bereits stornierte Einlösungen werden mit Betrag 0 gespeichert, damit auch verspätete Ereignisse keine Gutschrift auslösen. Wird eine Einlösung erst nach Gutschrift storniert, weist das Log auf einen nötigen manuellen Abgleich hin; automatische Rückbuchungen sind nicht implementiert. Neue Einlösungen können den öffentlichen Registrierungslink liefern; die Passwortsetzung verlangt weiterhin die Chat-Bestätigung. Guthaben vor der Registrierung bleibt erhalten.

## GitHub Pages und lokales Backend

Aktuell sind weder GitHub Pages noch ein öffentlicher HTTPS-Tunnel eingerichtet. **Localhost-Links funktionieren nur auf deinem Server-PC**, auch wenn sie im öffentlichen Chat stehen. Für externe Zuschauer später konfigurieren:

```dotenv
APP_ENV=production
ENABLE_DEMO_AUTH=false
FRONTEND_URL=https://ACCOUNT.github.io/REPOSITORY/
CORS_ORIGINS=https://ACCOUNT.github.io
```

Im Frontend-Build: `VITE_API_BASE_URL=https://OEFFENTLICHE-BACKEND-ADRESSE/api`. Vorlage: [.env.production.example](../../.env.production.example). Streamer.bot spricht weiterhin lokal mit Port 8002. Nur die Hub-API benötigt eine öffentliche HTTPS-Adresse; die Streamer.bot-Steuerung muss nicht öffentlich erreichbar sein.

## Fehler eingrenzen

- `hubApiKey fehlt`: Setup-Aktion tatsächlich ausführen; Kompilieren allein setzt keine Variablen.
- Keine Reaktion auf `!confirm CODE`: Command-Modus **Starts With**, Twitch-Quelle und zweiter Trigger an TCG Register prüfen.
- Code abgelaufen/falsches Konto: im eigenen Browser neuen Code erstellen und mit dem dort angezeigten Twitch-Konto bestätigen.
- Backend liefert noch privaten Link: Backend läuft mit altem Code. Die C#-Aktion veröffentlicht solche Links ausdrücklich nicht.
- Im Log steht noch `Whisper` beim Hub-Aufruf: In mindestens einer Streamer.bot-Subaktion läuft noch die alte Codekopie. Aktuellen Code überall übernehmen.
- HTTP 503 bei Rewards: zunächst Belohnungs-ID konfigurieren. `!register` und `!confirm` benötigen keine Reward-ID.

## Prüfungen

33 Backend-Tests prüfen unter anderem Sofortgutschrift, Wiederholungen, parallele initiale/Updated-Ereignisse und Stornierungen. 8 C#-Ablauftests führen TradingHub.cs gegen einen lokalen Testserver und eine nachgebildete CPH-Schnittstelle aus: Erfüllung erst nach Backend-Antwort, Wiederholung ohne Doppelbuchung, keine Erfüllung bei Backend-Fehlern und korrekte Meldung bei Twitch-Fehlern. Dabei werden keine Twitch-Anfragen gesendet.

TypeScript-/Vite-Build und Browserdurchlauf für Registrierung, Login, Gutschrift/Kauf/Öffnung bestanden beim Umbau der Registrierung. Die aktuelle Codekopie muss in Streamer.bot eingefügt und der automatische Twitch-Abschluss noch live geprüft werden. TradingHub.cs wurde auch gegen die echte lokale 1.0.7-Schnittstelle kompiliert.

Referenzen zur Erfüllung: [TwitchRedemptionFulfill](https://docs.streamer.bot/api/csharp/methods/twitch/channel-reward/twitch-redemption-fulfill), [Streamer.bot-Voraussetzungen](https://docs.streamer.bot/faq/fulfill-cancel-cpr).

Offizielle Referenzen: [Command Triggered](https://docs.streamer.bot/api/triggers/core/commands/command-triggered), [SendMessage](https://docs.streamer.bot/api/csharp/methods/twitch/chat/send-message), [C#-Referenzen](https://docs.streamer.bot/api/csharp/guide/debugging), [Reward Redemption](https://docs.streamer.bot/api/triggers/twitch/channel-reward/reward-redemption), [Reward Redemption Updated](https://docs.streamer.bot/api/triggers/twitch/channel-reward/reward-redemption-updated).
