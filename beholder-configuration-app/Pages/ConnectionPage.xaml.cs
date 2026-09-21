using beholder_configuration_app.Services;
using System;

namespace beholder_configuration_app;

public partial class ConnectionPage : ContentPage
{
    private readonly BeholderWebSocketService _webSocketService;
    public ConnectionPage(BeholderWebSocketService webSocketService)
	{
		InitializeComponent();

		_webSocketService = webSocketService;
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
            StatusLabel.Text = "Connecting...";
            await _webSocketService.ConnectAsync(AddressEntry.Text, port);
            if (_webSocketService.IsConnected)
            {
                StatusLabel.Text = "Connected!";
                //Go back to the dashboard
                await Shell.Current.GoToAsync("..");
            }
            else
            {
                StatusLabel.Text = "Connection Failed!";
            }
        }
        catch (Exception exception)
        {
            StatusLabel.Text = exception.ToString();
        }
    }
}