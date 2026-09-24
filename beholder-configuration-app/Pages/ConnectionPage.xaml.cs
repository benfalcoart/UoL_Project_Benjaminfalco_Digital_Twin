using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using System;

namespace beholder_configuration_app;

public partial class ConnectionPage : ContentPage
{
    private readonly BeholderWebSocketService _webSocketService;
    private readonly AppLogService _logService;
    private readonly BeholderConnectionSettings _connectionSettings;
    public ConnectionPage(BeholderWebSocketService webSocketService, AppLogService logService, BeholderConnectionSettings connectionSettings)
	{
		InitializeComponent();

		_webSocketService = webSocketService;
        _logService = logService;
        _connectionSettings = connectionSettings;
	}

    private async void OnConnectClicked(object sender, EventArgs e)
    {
        if (!int.TryParse(PortEntry.Text, out int port))
        {
            StatusLabel.Text = "Invalid port";
            return;
        }

        try
        {
            string status = $"Connecting to {AddressEntry.Text}:{PortEntry.Text}";
            StatusLabel.Text = status;
            _logService.Info(status);
            _connectionSettings.SetAddressPort(AddressEntry.Text, port);
            await _webSocketService.ConnectAsync();
            if (_webSocketService.IsConnected)
            {
                status = $"Successfully connected to {AddressEntry.Text}:{PortEntry.Text}";
                StatusLabel.Text = status;
                _logService.Info(status);
                //Go back to the dashboard
                await Shell.Current.GoToAsync("..");
            }
            else
            {
                status = $"Connection to {AddressEntry.Text}:{PortEntry.Text} Failed!";
                StatusLabel.Text = status;
                _logService.Error(status);

            }
        }
        catch (Exception exception)
        {
            StatusLabel.Text = $"{exception.GetType().Name}: {exception.Message}";
            _connectionSettings.SetAddressPort("",-1);
            _logService.Error(exception);

        }
    }
}