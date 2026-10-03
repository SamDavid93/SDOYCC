using System;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Streamer.bot.Plugin.Interface;

// Streamer.bot 1.0.7: use in a Core > C# > Execute C# Code sub-action.
#if EXTERNAL_EDITOR
public class TradingHub : CPHInlineBase
#else
public class CPHInline
#endif
{
    private static readonly HttpClient Client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false })
    {
        Timeout = TimeSpan.FromSeconds(15)
    };

#if EXTERNAL_EDITOR
    public override bool Execute()
#else
    public bool Execute()
#endif
    {
        try
        {
            string mode;
            CPH.TryGetArg("hubAction", out mode);
            if (mode != "reward")
            {
                string source, command;
                if (!CPH.TryGetArg("commandSource", out source) || source != "twitch" || !CPH.TryGetArg("command", out command))
                    return Fail("Registrierung ist nur ueber einen Twitch-Chat-Befehl erlaubt.");
                if (String.Equals(command, "!register", StringComparison.OrdinalIgnoreCase)) mode = "register";
                else if (String.Equals(command, "!confirm", StringComparison.OrdinalIgnoreCase)) mode = "confirm";
                else return Fail("Unterstuetzte Befehle: !register und !confirm CODE.");
            }

            string userId, userName, displayName;
            if (!CPH.TryGetArg("userId", out userId) || !CPH.TryGetArg("userName", out userName))
                return Fail("Twitch-Benutzerdaten fehlen. Die Aktion muss von einem Twitch-Ereignis stammen.");
            if (!CPH.TryGetArg("user", out displayName)) displayName = userName;

            var broadcaster = CPH.TwitchGetBroadcaster();
            if (broadcaster == null || String.IsNullOrWhiteSpace(broadcaster.UserLogin))
                return Fail("Kein Twitch-Broadcaster verbunden.");
            string endpoint = CPH.GetGlobalVar<string>("hubApiBaseUrl", true);
            string key = CPH.GetGlobalVar<string>("hubApiKey", true);
            if (String.IsNullOrWhiteSpace(endpoint)) endpoint = "http://127.0.0.1:8002/api";
            Uri address;
            if (!Uri.TryCreate(endpoint, UriKind.Absolute, out address) ||
                (address.Scheme != "https" && !(address.Scheme == "http" && address.IsLoopback)))
                return Fail("Die Hub-Adresse muss HTTPS verwenden; lokales HTTP ist nur auf localhost erlaubt.");
            if (String.IsNullOrWhiteSpace(key) || key.Length < 32)
                return Fail("Die persistierte globale Variable hubApiKey fehlt.");

            var payload = JObject.FromObject(new
            {
                user_id = userId,
                username = userName,
                display_name = displayName,
                broadcaster_login = broadcaster.UserLogin
            });
            string path = "/integrations/streamerbot/register";
            if (mode == "confirm")
            {
                string code;
                if (!CPH.TryGetArg("rawInput", out code) || String.IsNullOrWhiteSpace(code))
                    return Chat(userName, "Bitte den Befehl !confirm CODE von deiner Registrierungsseite verwenden.");
                code = code.Trim().ToUpperInvariant();
                if (code.Length != 10 || !IsHexCode(code))
                    return Chat(userName, "Ungueltiges Codeformat. Kopiere !confirm CODE von deiner Registrierungsseite.");
                payload["code"] = code;
                path = "/integrations/streamerbot/confirm";
            }
            if (mode == "reward")
            {
                string redemptionId, rewardId, rewardStatus;
                int cost;
                bool skipsQueue;
                if (!CPH.TryGetArg("redemptionId", out redemptionId) || !CPH.TryGetArg("rewardId", out rewardId) || !CPH.TryGetArg("rewardCost", out cost))
                    return Fail("Die Variablen redemptionId, rewardId oder rewardCost fehlen.");
                if (!CPH.TryGetArg("rewardStatus", out rewardStatus) || String.IsNullOrWhiteSpace(rewardStatus))
                    rewardStatus = CPH.TryGetArg("skipsQueue", out skipsQueue) && skipsQueue ? "fulfilled" : "unfulfilled";
                payload["redemption_id"] = redemptionId;
                payload["reward_id"] = rewardId;
                payload["reward_cost"] = cost;
                payload["status"] = rewardStatus.ToLowerInvariant();
                path = "/integrations/streamerbot/redemptions";
            }

            using (var request = new HttpRequestMessage(HttpMethod.Post, endpoint.TrimEnd('/') + path))
            {
                request.Headers.Add("X-Streamerbot-Key", key);
                request.Content = new StringContent(payload.ToString(Formatting.None), Encoding.UTF8, "application/json");
                using (var response = Client.SendAsync(request).GetAwaiter().GetResult())
                {
                    if (!response.IsSuccessStatusCode)
                    {
                        if (mode == "confirm" && ((int)response.StatusCode == 400 || (int)response.StatusCode == 403))
                            return Chat(userName, "Code ungueltig, abgelaufen oder fuer ein anderes Konto. Bitte nur den Code deiner eigenen Registrierungsseite bestaetigen.");
                        if ((int)response.StatusCode == 429)
                            return Chat(userName, "Zu viele Versuche. Bitte in fuenf Minuten erneut versuchen.");
                        Fail("Hub-Anfrage fehlgeschlagen: HTTP " + (int)response.StatusCode + ". Kanal, Reward-ID und Verbindungsschluessel pruefen.");
                        return Chat(userName, "Der Hub ist gerade nicht bereit. Bitte den Streamer auf das Hub-Log hinweisen.");
                    }
                    var result = JObject.Parse(response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
                    if (mode == "confirm" && (bool?)result["confirmed"] == true)
                        return Chat(userName, "Twitch-Konto bestaetigt. Lege jetzt dein Passwort auf deiner bereits geoeffneten Registrierungsseite fest.");
                    string rewardNotice = "";
                    if (mode == "reward")
                    {
                        if ((bool?)result["credited"] == true)
                        {
                            rewardNotice = "Tradingpoints gutgeschrieben! Neuer Kontostand: " + (int)result["diamonds"] + " Tradingpoints. ";
                            CPH.LogInfo("Trading Hub: Kanalpunkte-Einloesung erfolgreich gutgeschrieben.");
                        }
                        else if ((bool?)result["duplicate"] == true)
                            CPH.LogInfo("Trading Hub: Einloesung bereits verarbeitet; keine doppelte Gutschrift.");
                        else if ((string)result["status"] == "canceled")
                            rewardNotice = "Einloesung storniert; keine Tradingpoints gutgeschrieben. ";

                        // Only complete Twitch's queue item AFTER a committed backend credit.
                        // On retry, the backend confirms the previous credit without booking again.
                        if ((bool?)result["fulfill_required"] == true && (string)payload["status"] == "unfulfilled")
                        {
                            if (!CompleteReward((string)payload["reward_id"], (string)payload["redemption_id"]))
                                rewardNotice += "Die Gutschrift ist verbucht, aber der Twitch-Abschluss steht noch aus. Der Streamer findet Details im Hub-Log. ";
                        }
                        if ((bool?)result["canceled_after_credit"] == true)
                            CPH.LogWarn("Trading Hub: Bereits gutgeschriebene Einloesung wurde in Twitch storniert. Guthaben und Kanalpunkte manuell abgleichen; keine automatische Rueckbuchung.");
                    }
                    string url = (string)result["registration_url"];
                    if (!String.IsNullOrEmpty(url))
                    {
                        // Refuse legacy private invitations if an old backend is still running.
                        if (url.IndexOf("?", StringComparison.Ordinal) >= 0 || url.IndexOf("token=", StringComparison.OrdinalIgnoreCase) >= 0)
                            return Fail("Backend liefert noch einen privaten Link. Backend neu starten; dieser Link wird nicht oeffentlich gepostet.");
                        return Chat(userName, rewardNotice + "Registriere dich hier: " + url + " Erstelle dort deinen Code und bestaetige ihn mit !confirm CODE im Chat. Danach legst du dein Passwort fest.");
                    }
                    if (mode == "register" && (bool?)result["registered"] == true)
                        return Chat(userName, "Dein Konto ist bereits registriert. Anmeldung mit Twitch-Namen und Hub-Passwort: " + (string)result["login_url"]);
                    if (!String.IsNullOrEmpty(rewardNotice)) return Chat(userName, rewardNotice.Trim());
                    return true;
                }
            }
        }
        catch (Exception)
        {
            // Do not log bodies, keys, passwords or registration links.
            return Fail("Hub nicht erreichbar oder ungueltige Antwort. Backend pruefen. Einloesungen nie mit neuer redemptionId wiederholen.");
        }
    }

    private bool Chat(string userName, string message)
    {
        // Public replies use the broadcaster; no Whisper API or bot token is involved.
        CPH.SendMessage("@" + userName + " " + message, false, false);
        return true;
    }

    private bool CompleteReward(string rewardId, string redemptionId)
    {
        try
        {
            if (CPH.TwitchRedemptionFulfill(rewardId, redemptionId))
            {
                CPH.LogInfo("Trading Hub: Einloesung automatisch erfuellt und aus der Twitch-Warteschlange entfernt.");
                return true;
            }
        }
        catch (Exception)
        {
            // The credit has already committed; never report this as a failed credit.
        }
        CPH.LogWarn("Trading Hub: Gutschrift erfolgt, automatisches Erfuellen fehlgeschlagen. Die Belohnung muss von Streamer.bot erstellt/verwaltet sein. Twitch-Verbindung pruefen und dasselbe Original-Ereignis erneut ausfuehren, niemals eine neue redemptionId erfinden.");
        return false;
    }

    private bool IsHexCode(string code)
    {
        foreach (char value in code)
            if (!(value >= '0' && value <= '9') && !(value >= 'A' && value <= 'F')) return false;
        return true;
    }

    private bool Fail(string message)
    {
        CPH.LogWarn("Trading Hub: " + message);
        return false;
    }
}
