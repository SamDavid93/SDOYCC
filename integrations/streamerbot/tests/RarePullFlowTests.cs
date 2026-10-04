// Isolated HTTP/CPH fixtures only; never connects to Twitch or the real backend.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace Streamer.bot.Plugin.Interface
{
    public class CPHInlineBase
    {
        public FakeCPH CPH { get; set; }
        public virtual bool Execute() { return true; }
    }
}
public class FakeUser { public string UserLogin = "samdavidofficial"; }
public class FakeCPH
{
    public string Endpoint;
    public string Sent = "";
    public bool ThrowOnSend;
    public List<string> Messages = new List<string>();
    public FakeUser TwitchGetBroadcaster() { return new FakeUser(); }
    public T GetGlobalVar<T>(string name, bool persisted)
    {
        return (T)(object)(name == "hubApiBaseUrl" ? Endpoint : name == "hubApiKey" ? new string('x', 40) : Sent);
    }
    public void SetGlobalVar<T>(string name, T value, bool persisted) { Sent = value.ToString(); }
    public void SendMessage(string message, bool bot, bool fallback)
    {
        if (bot || fallback) throw new Exception("Must use broadcaster only");
        if (ThrowOnSend) throw new Exception("fixture send failed");
        Messages.Add(message);
    }
    public void LogInfo(string message) { }
    public void LogWarn(string message) { }
}
public static class RarePullFlowTests
{
    private static void Run(string name, bool empty, bool failAck, bool failSend)
    {
        var probe = new TcpListener(IPAddress.Loopback, 0); probe.Start();
        int port = ((IPEndPoint)probe.LocalEndpoint).Port; probe.Stop();
        using (var server = new HttpListener())
        {
            string baseUrl = "http://127.0.0.1:" + port;
            server.Prefixes.Add(baseUrl + "/"); server.Start();
            int requests = empty || failSend ? 1 : failAck ? 4 : 2;
            int acks = 0;
            var worker = Task.Factory.StartNew(() => {
                for (int i = 0; i < requests; i++)
                {
                    var context = server.GetContext();
                    if (context.Request.Headers["X-Streamerbot-Key"] != new string('x', 40)) throw new Exception("Missing bridge key");
                    JObject payload;
                    using (var reader = new StreamReader(context.Request.InputStream)) payload = JObject.Parse(reader.ReadToEnd());
                    if ((string)payload["broadcaster_login"] != "samdavidofficial") throw new Exception("Wrong channel");
                    bool ack = context.Request.Url.AbsolutePath.EndsWith("/ack");
                    string body;
                    if (ack)
                    {
                        acks++;
                        if (failAck && acks == 1) context.Response.StatusCode = 503;
                        if ((string)payload["claim_token"] != new string('a', 48)) throw new Exception("Missing lease token");
                        body = "{\"acknowledged\":true}";
                    }
                    else body = empty ? "{\"announcement\":null}" : "{\"announcement\":{\"id\":42,\"message\":\"Glückwunsch @viewer! Testkarte [Ultraselten] aus Testpack gezogen!\",\"claim_token\":\"" + new string('a', 48) + "\"}}";
                    byte[] bytes = Encoding.UTF8.GetBytes(body);context.Response.ContentType = "application/json";
                    context.Response.OutputStream.Write(bytes, 0, bytes.Length);context.Response.Close();
                }
            });
            var cph = new FakeCPH { Endpoint = baseUrl + "/api", ThrowOnSend = failSend };
            var action = new RarePullAnnouncements { CPH = cph };
            bool success = action.Execute();
            if (success != !(failAck || failSend)) throw new Exception(name + ": wrong result");
            if (failAck)
            {
                action = new RarePullAnnouncements { CPH = cph }; // Simulate script instance restart.
                if (!action.Execute()) throw new Exception("ack retry failed");
            }
            if (!worker.Wait(10000)) throw new Exception("fixture timed out");
            if (cph.Messages.Count != (empty || failSend ? 0 : 1)) throw new Exception(name + ": duplicate or missing message");
            if (failSend && cph.Sent != "") throw new Exception("failed send marked as sent");
            Console.WriteLine("PASS " + name);
        }
    }
    public static void Main()
    {
        Run("empty queue sends nothing", true, false, false);
        Run("claim sends once via broadcaster and acknowledges", false, false, false);
        Run("ack failure and instance restart do not duplicate chat", false, true, false);
        Run("send exception leaves announcement unacknowledged", false, false, true);
    }
}
