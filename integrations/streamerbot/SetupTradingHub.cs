using System;
using System.IO;
using System.Net.Http;
using Newtonsoft.Json.Linq;
using Streamer.bot.Plugin.Interface;

// Run manually once in Streamer.bot. No chat trigger and no messages sent.
#if EXTERNAL_EDITOR
public class SetupTradingHub : CPHInlineBase
#else
public class CPHInline
#endif
{
#if EXTERNAL_EDITOR
    public override bool Execute()
#else
    public bool Execute()
#endif
    {
        try
        {
            string envPath;
            if (!CPH.TryGetArg("hubEnvPath", out envPath) || String.IsNullOrWhiteSpace(envPath))
                envPath = @"G:\Yugioh Online Trading Card\.env";
            if (!File.Exists(envPath))
                return Fail("Lokale .env fehlt. Setze hubEnvPath auf den vollstaendigen Dateipfad.");

            string key = null;
            foreach (string line in File.ReadAllLines(envPath))
            {
                int separator = line.IndexOf('=');
                if (separator < 0 || line.Substring(0, separator).Trim() != "STREAMERBOT_API_KEY") continue;
                string value = line.Substring(separator + 1).Trim();
                if (value.Length >= 2 && ((value[0] == '"' && value[value.Length - 1] == '"') ||
                    (value[0] == '\'' && value[value.Length - 1] == '\'')))
                    value = value.Substring(1, value.Length - 2);
                key = value;
            }
            if (String.IsNullOrWhiteSpace(key) || key.Length < 32)
                return Fail("STREAMERBOT_API_KEY fehlt oder ist zu kurz. Lokale .env pruefen.");

            const string endpoint = "http://127.0.0.1:8002/api";
            using (var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false }))
            using (var request = new HttpRequestMessage(HttpMethod.Get, endpoint + "/integrations/streamerbot/status"))
            {
                client.Timeout = TimeSpan.FromSeconds(10);
                request.Headers.Add("X-Streamerbot-Key", key);
                using (var response = client.SendAsync(request).GetAwaiter().GetResult())
                {
                    if (!response.IsSuccessStatusCode)
                        return Fail("Backend meldet HTTP " + (int)response.StatusCode + ". Nach .env-Aenderungen Backend neu starten.");
                    var status = JObject.Parse(response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
                    if ((string)status["status"] != "ok") return Fail("Unerwartete Backend-Antwort.");
                    var broadcaster = CPH.TwitchGetBroadcaster();
                    if (broadcaster == null || String.IsNullOrWhiteSpace(broadcaster.UserId))
                        return Fail("Verbinde zuerst dein Broadcaster-Konto in Streamer.bot mit Twitch.");
                    if (!String.Equals(broadcaster.UserLogin, (string)status["channel"], StringComparison.OrdinalIgnoreCase))
                        return Fail("Der verbundene Twitch-Kanal stimmt nicht mit TWITCH_BROADCASTER_LOGIN im Backend ueberein.");

                    CPH.SetGlobalVar("hubApiBaseUrl", endpoint, true);
                    CPH.SetGlobalVar("hubApiKey", key, true);
                    CPH.LogInfo("Trading Hub Setup: Backend und Kanal geprueft; Verbindungseinstellungen gespeichert.");
                    CPH.LogInfo("Trading Hub Setup: Oeffentliche Chat-Registrierung aktiv. !register und !confirm mit derselben Registrierungsaktion verbinden; keine Fluesternachrichten erforderlich.");
                    if ((bool?)status["reward_configured"] != true)
                        CPH.LogWarn("Trading Hub Setup: Reward-ID fehlt noch. !register kann unabhaengig davon eingerichtet und getestet werden.");
                    return true;
                }
            }
        }
        catch (Exception)
        {
            return Fail("Setup fehlgeschlagen. Dateizugriff, laufendes Backend und Twitch-Verbindung pruefen.");
        }
    }

    private bool Fail(string message)
    {
        // Never log secrets, file contents or HTTP response bodies.
        CPH.LogWarn("Trading Hub Setup: " + message);
        return false;
    }
}
