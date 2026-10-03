// Runs the actual TradingHub.cs against a local fake HTTP server and fake CPH.
// No Twitch requests or chat messages are sent.
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

public class FakeUser
{
    public string UserLogin = "samdavidofficial";
}

public class FakeCPH
{
    public string Endpoint;
    public string Status;
    public bool FulfillSuccess = true;
    public bool FulfillThrows;
    public int FulfillCalls;
    public List<string> Messages = new List<string>();
    public List<string> Logs = new List<string>();
    public bool TryGetArg<T>(string name, out T value)
    {
        var args = new Dictionary<string, object> {
            {"hubAction", "reward"}, {"userId", "456"}, {"userName", "viewer"}, {"user", "Viewer"},
            {"rewardId", "reward-1"}, {"redemptionId", "redemption-1"}, {"rewardCost", 1000}, {"rewardStatus", Status}
        };
        object item;
        if (args.TryGetValue(name, out item)) { value = (T)item; return true; }
        value = default(T); return false;
    }
    public FakeUser TwitchGetBroadcaster() { return new FakeUser(); }
    public T GetGlobalVar<T>(string key, bool persisted)
    {
        return (T)(object)(key == "hubApiBaseUrl" ? Endpoint : new string('x', 40));
    }
    public void SendMessage(string message, bool bot, bool fallback)
    {
        if (bot || fallback) throw new Exception("Unexpected bot sender");
        Messages.Add(message);
    }
    public void LogInfo(string message) { Logs.Add(message); }
    public void LogWarn(string message) { Logs.Add(message); }
    public bool TwitchRedemptionFulfill(string rewardId, string redemptionId)
    {
        if (rewardId != "reward-1" || redemptionId != "redemption-1") throw new Exception("Wrong redemption");
        FulfillCalls++;
        if (FulfillThrows) throw new Exception("Simulated Twitch failure");
        return FulfillSuccess;
    }
}

public class RewardFlowTests
{
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }
    private static void Run(string name, string status, int httpStatus, string responseJson,
                            int fulfillCalls, bool fulfillSuccess = true, bool fulfillThrows = false)
    {
        var server = new TcpListener(IPAddress.Loopback, 0);
        server.Start();
        var fake = new FakeCPH { Endpoint = "http://127.0.0.1:" + ((IPEndPoint)server.LocalEndpoint).Port + "/api",
                                 Status = status, FulfillSuccess = fulfillSuccess, FulfillThrows = fulfillThrows };
        var responseTask = Task.Run(() => {
            using (var connection = server.AcceptTcpClient())
            using (var stream = connection.GetStream())
            using (var reader = new StreamReader(stream, Encoding.UTF8, false, 1024, true))
            {
                string request = reader.ReadLine();
                Check(request.StartsWith("POST /api/integrations/streamerbot/redemptions "), "Wrong endpoint");
                int length = 0;
                string header;
                while (!String.IsNullOrEmpty(header = reader.ReadLine()))
                    if (header.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase)) length = Int32.Parse(header.Substring(15));
                var body = new char[length];
                int read = 0;
                while (read < length) { int count = reader.Read(body, read, length - read); if (count == 0) throw new Exception("Short request"); read += count; }
                Check((string)JObject.Parse(new string(body))["status"] == status, "Event status was changed");
                Check(fake.FulfillCalls == 0, "Twitch was fulfilled before the backend replied");
                byte[] content = Encoding.UTF8.GetBytes(responseJson);
                byte[] headers = Encoding.ASCII.GetBytes("HTTP/1.1 " + httpStatus + " Test\r\nContent-Type: application/json\r\nContent-Length: " + content.Length + "\r\nConnection: close\r\n\r\n");
                stream.Write(headers, 0, headers.Length);
                stream.Write(content, 0, content.Length);
            }
        });
        try
        {
            var action = new TradingHub { CPH = fake };
            Check(action.Execute(), name + ": action failed");
            Check(responseTask.Wait(5000), "HTTP server timeout");
            Check(fake.FulfillCalls == fulfillCalls, name + ": wrong fulfillment count");
            if (!fulfillSuccess || fulfillThrows)
                Check(fake.Messages.Exists(m => m.Contains("Gutschrift ist verbucht")), "Lost credit-success feedback on Twitch failure");
            Console.WriteLine("PASS " + name);
        }
        finally { server.Stop(); }
    }
    public static void Main()
    {
        const string credited = "{\"credited\":true,\"duplicate\":false,\"diamonds\":100,\"status\":\"unfulfilled\",\"fulfill_required\":true}";
        Run("credit then fulfill", "unfulfilled", 200, credited, 1);
        Run("retry credit only fulfills again", "unfulfilled", 200, "{\"credited\":false,\"duplicate\":true,\"diamonds\":100,\"status\":\"unfulfilled\",\"fulfill_required\":true}", 1);
        Run("updated event never fulfills again", "fulfilled", 200, "{\"credited\":false,\"duplicate\":true,\"diamonds\":100,\"status\":\"fulfilled\",\"fulfill_required\":false}", 0);
        Run("canceled never fulfills", "canceled", 200, "{\"credited\":false,\"duplicate\":false,\"diamonds\":0,\"status\":\"canceled\",\"fulfill_required\":false}", 0);
        Run("backend failure leaves queue open", "unfulfilled", 500, "{}", 0);
        Run("no confirmed credit leaves queue open", "unfulfilled", 200, "{\"credited\":false,\"duplicate\":false,\"diamonds\":0,\"status\":\"unfulfilled\",\"fulfill_required\":false}", 0);
        Run("Twitch failure preserves credit feedback", "unfulfilled", 200, credited, 1, false);
        Run("Twitch exception preserves credit feedback", "unfulfilled", 200, credited, 1, true, true);
    }
}
