


namespace beholder_configuration_app.Services.WebServices
{
    public class BeholderConnectionSettings
    {
        /// <summary>
        /// Cached IP Addresses for Easier access.
        /// </summary>
        public Dictionary<string, string> PresetAddresses { get; } = new()
        {
            { "BEHOLDER Wi-Fi", "192.168.50.1" },
            { "BEHOLDER Ethernet", "192.168.60.1" },
            { "HOME-WIFI", "192.168.0.130" }
        };

        public string Address { get; set; } = "192.168.50.1";
        public int Port { get; set; } = 8000;

        public string HttpBaseAddress =>
            $"http://{Address}:{Port}";

        public string WebSocketAddress =>
            $"ws://{Address}:{Port}/ws";

        public void SetAddressPort(string address, int port)
        {
            Address = address;
            Port = port;
        }
    }
}