using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Streamer.bot.Plugin.Interface;

// Streamer.bot 1.0.7: separate action, Core > Timed Actions, repeat every 15s.
// Uses the broadcaster and the existing hubApiBaseUrl/hubApiKey globals.
#if EXTERNAL_EDITOR
public class RarePullAnnouncements : CPHInlineBase
#else
public class CPHInline
#endif
{
    private static readonly object Gate = new object();
    private static readonly HttpClient Client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false })
    {
        Timeout = TimeSpan.FromSeconds(5)
    };

#if EXTERNAL_EDITOR
    public override bool Execute()
#else
    public bool Execute()
#endif
    {
        lock (Gate)
        {
            try
            {
                var broadcaster = CPH.TwitchGetBroadcaster();
                if (broadcaster == null || String.IsNullOrWhiteSpace(broadcaster.UserLogin)) return false;
                string endpoint = CPH.GetGlobalVar<string>("hubApiBaseUrl", true);
                string key = CPH.GetGlobalVar<string>("hubApiKey", true);
                if (String.IsNullOrWhiteSpace(endpoint)) endpoint = "http://127.0.0.1:8002/api";
                Uri address;
                if (!Uri.TryCreate(endpoint, UriKind.Absolute, out address) ||
                    (address.Scheme != "https" && !(address.Scheme == "http" && address.IsLoopback)) ||
                    !String.IsNullOrEmpty(address.UserInfo) || String.IsNullOrWhiteSpace(key) || key.Length < 32)
                    return Fail("Hub-Verbindung fehlt oder ist ungueltig. Setup ausfuehren.");

                var payload = JObject.FromObject(new { broadcaster_login = broadcaster.UserLogin });
                var result = Post(endpoint, key, "/announcements/claim", payload);
                var notice = result["announcement"] as JObject;
                if (notice == null) return true;
                string id = ((long)notice["id"]).ToString(System.Globalization.CultureInfo.InvariantCulture);
                string message = (string)notice["message"];
                string token = (string)notice["claim_token"];
                if (String.IsNullOrWhiteSpace(message) || Encoding.UTF8.GetByteCount(message) > 450 ||
                    message.IndexOf('\r') >= 0 || message.IndexOf('\n') >= 0 || String.IsNullOrWhiteSpace(token))
                    return Fail("Ungueltige Fundmeldung erhalten.");

                // Persist recently submitted IDs BEFORE acknowledging the HTTP queue.
                // An ack timeout or application restart must not routinely repeat chat.
                string history = CPH.GetGlobalVar<string>("hubRarePullSentIds", true) ?? "";
                var sent = new List<string>(history.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
                if (!sent.Contains(id))
                {
                    CPH.SendMessage(message, false, false);
                    sent.Add(id);
                    while (sent.Count > 100) sent.RemoveAt(0);
                    CPH.SetGlobalVar("hubRarePullSentIds", String.Join(",", sent.ToArray()), true);
                }
                payload["claim_token"] = token;
                var ack = Post(endpoint, key, "/announcements/" + id + "/ack", payload);
                if ((bool?)ack["acknowledged"] != true) return Fail("Fundmeldung noch nicht quittiert.");
                CPH.LogInfo("SDOYCC: Fundmeldung " + id + " verarbeitet. Twitch bestaetigt den Empfang hier nicht.");
                return true;
            }
            catch (Exception)
            {
                return Fail("Fundmeldung nicht abgeschlossen. Backend und Broadcaster-Chat pruefen; der Timer versucht es erneut.");
            }
        }
    }

    private JObject Post(string endpoint, string key, string path, JObject payload)
    {
        using (var request = new HttpRequestMessage(HttpMethod.Post, endpoint.TrimEnd('/') + "/integrations/streamerbot" + path))
        {
            request.Headers.Add("X-Streamerbot-Key", key);
            request.Content = new StringContent(payload.ToString(Formatting.None), Encoding.UTF8, "application/json");
            using (var response = Client.SendAsync(request).GetAwaiter().GetResult())
            {
                if (!response.IsSuccessStatusCode) throw new InvalidOperationException("Hub HTTP request failed");
                return JObject.Parse(response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
            }
        }
    }

    private bool Fail(string message)
    {
        // No keys, response bodies, registration links or claim tokens in logs.
        CPH.LogWarn("SDOYCC Fundmeldungen: " + message);
        return false;
    }
}
