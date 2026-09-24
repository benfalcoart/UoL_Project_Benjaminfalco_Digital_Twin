


namespace beholder_configuration_app.Services.WebServices
{
    public class BeholderConnectionSettings
    {
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