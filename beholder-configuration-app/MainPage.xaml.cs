using beholder_configuration_app.Models;
using beholder_configuration_app.Services;
using System.Text.Json;

namespace beholder_configuration_app
{
    public partial class MainPage : ContentPage
    {
        private readonly BeholderWebSocketService _webSocketService;
        private BeholderStatus? _status;
        /// <summary>
        /// Start up the main page of the MAUI app
        /// </summary>
        /// <param name="webSocketService"></param>
        public MainPage(BeholderWebSocketService webSocketService)
        {
            InitializeComponent();
            _webSocketService = webSocketService;

            _webSocketService.MessageReceived += OnMessageReceived;
            _webSocketService.ConnectionChanged += OnConnectionChanged;
        }
        private async void OnConnectClicked(object sender, EventArgs e)
        {
            try
            {
                MessageLabel.Text = "Connecting...";
                await _webSocketService.ConnectAsync();
            }
            catch (Exception exception)
            {
                MessageLabel.Text = exception.ToString();
            }
        }

        private void OnMessageReceived(string message)
        {
            MainThread.BeginInvokeOnMainThread(() =>
            {
                try
                {
                    _status = JsonSerializer.Deserialize<BeholderStatus>(message);
                    MessageLabel.Text = _status?.ToString();
                }
                catch (Exception exception) 
                {
                    MessageLabel.Text = exception.ToString();
                }
            });
        }

        private void OnConnectionChanged(bool connected)
        {
            MainThread.BeginInvokeOnMainThread(() =>
            {
                ConnectionLabel.Text = connected ? "Connected" : "Disconnected";

                ConnectionLabel.TextColor = connected ? Colors.LimeGreen: Colors.Orange;
            });
        }

    }
}
