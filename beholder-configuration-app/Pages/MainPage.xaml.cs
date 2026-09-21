using beholder_configuration_app.Models;
using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using Microsoft.Maui.Controls.Shapes;
using System.Text.Json;

namespace beholder_configuration_app
{
    public partial class MainPage : ContentPage
    {
        private readonly BeholderWebSocketService _webSocketService;
        private readonly AppLogService _logService;

        private BeholderStatus? _status;
        /// <summary>
        /// Start up the main page of the MAUI app
        /// </summary>
        /// <param name="webSocketService"></param>
        public MainPage(BeholderWebSocketService webSocketService, AppLogService logService)
        {
            InitializeComponent();
            _webSocketService = webSocketService;
            _logService = logService;

            _webSocketService.MessageReceived += OnMessageReceived;
            _webSocketService.ConnectionChanged += OnConnectionChanged;
        }
        

        private void OnMessageReceived(string message)
        {
            MainThread.BeginInvokeOnMainThread(() =>
            {
                try
                {
                    _status = JsonSerializer.Deserialize<BeholderStatus>(message);
                    UpdateDashboard();
                }
                catch (Exception exception)
                {
                    _logService.Error(exception);
                }
            });
        }

        private void UpdateDashboard()
        {
            if (_status.System != null)
            {
                TemperatureLabel.Text = $"{_status.System.TemperatureC:F1} °C";
                StorageLabel.Text = $"{_status.System.StorageFreeGb:F1} GB";

                if (_status.System.Battery != null)
                {
                    BatteryLabel.Text = $"{_status.System.Battery.Percentage:F0}%";
                }
            }

            if (_status.Project != null)
            {
                ProjectNameLabel.Text = _status.Project.Name;
                CaptureIdLabel.Text = $"#{_status.Project.LastCaptureId}";
            }
            else
            {
                ProjectNameLabel.Text = "No project selected";
                CaptureIdLabel.Text = "#—";
            }

            if (_status.Capture != null)
            {
                bool automatic = _status.Capture.Mode == "automatic";

                AutomaticIntervalPanel.IsVisible = automatic;
                AutomaticIntervalLabel.Text = $"{_status.Capture.AutomaticIntervalSeconds:F2} s";

                SingleModeButton.BackgroundColor = automatic ? Color.FromArgb("#22252B") : Color.FromArgb("#3AA0FF");
                AutomaticModeButton.BackgroundColor = automatic ? Color.FromArgb("#3AA0FF") : Color.FromArgb("#22252B");

                if (_status.Capture.Capturing)
                {
                    CaptureStatusLabel.Text = "Capturing";
                    CaptureStatusIndicator.Color = Color.FromArgb("#F4B400");
                }
                else if (_status.Capture.AutomaticRunning)
                {
                    CaptureStatusLabel.Text = "Automatic Running";
                    CaptureStatusIndicator.Color = Color.FromArgb("#3AA0FF");
                }
                else
                {
                    CaptureStatusLabel.Text = "Idle";
                    CaptureStatusIndicator.Color = Color.FromArgb("#2ECC71");
                }

                CaptureButton.Text = _status.Capture.AutomaticRunning ? "STOP AUTOMATIC" : automatic ? "START AUTOMATIC" : "CAPTURE";
            }

            if (_status.Cameras != null)
            {
                CameraCountLabel.Text = $"{_status.Cameras.ActiveCount} / " + $"{_status.Cameras.DetectedCount}";
                UpdateCameraList(_status.Cameras.Items);
            }
        }

        private void UpdateCameraList(List<CameraStatus> cameras)
        {
            CameraList.Clear();

            foreach (CameraStatus camera in cameras)
            {
                Grid row = new()
                {
                    ColumnDefinitions =
                    {
                        new ColumnDefinition(GridLength.Star),
                        new ColumnDefinition(GridLength.Auto),
                        new ColumnDefinition(GridLength.Auto)
                    }
                };

                Label name = new()
                {
                    Text = camera.Name,
                    TextColor = Colors.White,
                    VerticalOptions = LayoutOptions.Center
                };

                Label active = new()
                {
                    Text = camera.Active ? "ACTIVE" : "OFF",
                    TextColor = camera.Active ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C"),
                    FontAttributes = FontAttributes.Bold,
                    Margin = new Thickness(10, 0)
                };

                Label slot = new()
                {
                    Text = camera.Slot,
                    TextColor = Color.FromArgb("#8B949E"),
                    VerticalOptions = LayoutOptions.Center
                };

                row.Add(name, 0);
                row.Add(active, 1);
                row.Add(slot, 2);

                Border card = new()
                {
                    BackgroundColor = Color.FromArgb("#191919"),
                    Stroke = Color.FromArgb("#444444"),
                    StrokeThickness = 1,
                    Padding = new Thickness(14),
                    StrokeShape = new RoundRectangle
                    {
                        CornerRadius = 8
                    },
                    Content = row
                };

                CameraList.Add(card);
            }
        }

        private async void OnConnectionClicked(object sender, EventArgs e)
        {
            await Shell.Current.GoToAsync(nameof(ConnectionPage));
        }

        private void OnConnectionChanged(bool connected)
        {
            MainThread.BeginInvokeOnMainThread(() =>
            {
                ConnectionLabel.Text = connected ? "LIVE" : "OFFLINE";
                ConnectionLabel.TextColor = connected ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C");
                ConnectionIndicator.Color = connected ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C");
                //ConnectionButton.TextColor = connected ? Color.FromArgb("#2ECC71") : Colors.White;
            });
        }

    }
}
