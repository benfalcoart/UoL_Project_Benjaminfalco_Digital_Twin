using beholder_configuration_app.Models;
using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using Microsoft.Maui.Controls.Shapes;
using System.Text.Json;
using System.Diagnostics;
using beholder_configuration_app.Services.Audio;

namespace beholder_configuration_app
{
    public partial class MainPage : ContentPage
    {
        //STRESS TEST
        private readonly Stopwatch _stressTestTimer = new();
        private bool _stressTestRunning = false;
        private const double StressTestBatteryThreshold = 2.0;        

        //SERVICES
        private readonly BeholderWebSocketService _webSocketService;
        private readonly BeholderAPIService _apiService;
        private readonly AppLogService _logService;
        private readonly SoundManager _soundManager;

        private BeholderStatus? _status;

        private bool _automaticIntervalDirty = false;
        private bool _updatingAutomaticIntervalFromStatus = false;

        /// <summary>
        /// Start up the main page of the MAUI app
        /// </summary>
        /// <param name="webSocketService"></param>
        public MainPage(BeholderWebSocketService webSocketService, BeholderAPIService apiService, AppLogService logService, SoundManager soundManager)
        {
            InitializeComponent();
            _webSocketService = webSocketService;
            _apiService = apiService;
            _logService = logService;
            _soundManager = soundManager;

            _webSocketService.MessageReceived += OnMessageReceived;
            _webSocketService.ConnectionChanged += OnConnectionChanged;

           
        }

        protected override void OnAppearing()
        {
            base.OnAppearing();
            bool keepScreenAwake = Preferences.Default.Get("KeepScreenAwake", true);
            DeviceDisplay.Current.KeepScreenOn = keepScreenAwake;
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
            if (_status == null)
            {
                return;
            }
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

                AutomaticOptionsPanel.IsVisible = automatic;

                double serverInterval = _status.Capture.AutomaticIntervalSeconds;

                if (_automaticIntervalDirty)
                {
                    if (double.TryParse(AutomaticIntervalEntry.Text, out double localInterval))
                    {
                        if (Math.Abs(localInterval - serverInterval) < 0.001)
                        {
                            _automaticIntervalDirty = false;
                        }
                    }
                }
                else
                {
                    _updatingAutomaticIntervalFromStatus = true;
                    AutomaticIntervalEntry.Text = serverInterval.ToString("F2");
                    _updatingAutomaticIntervalFromStatus = false;
                }

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

            if (_stressTestRunning)
            {
                if (!_stressTestTimer.IsRunning)
                    _logService.Info($"Stress Test Start at {_status?.System?.Battery?.Percentage:F1}%");
                    _stressTestTimer.Start();

                if (_status?.System?.Battery?.Percentage <= StressTestBatteryThreshold)
                {
                    _logService.Info($"Stress Test Ended at {_status?.System?.Battery?.Percentage:F1}%");
                    _stressTestTimer.Stop();
                    _logService.Info($"Battery life lasts: {_stressTestTimer.Elapsed.ToString()}");
                }
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

        private async void OnSingleModeClicked(object sender, EventArgs e)
        {
            try
            {
                HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.CaptureSetSingleMode, new
                {
                    mode = "single"

                });

                if (!response.IsSuccessStatusCode)
                {
                    _logService.Warning($"Unable to set single capture mode. HTTP {(int)response.StatusCode}");
                }
                else
                {
                   _ = _soundManager.PlayAsync(SoundEffect.Click);
                }
            }
            catch (Exception exception)
            {
                _logService.Error(exception);
            }
        }

        private async void OnAutomaticIntervalApplyClicked(object sender, EventArgs e)
        {
            if (!double.TryParse(AutomaticIntervalEntry.Text, out double seconds))
            {
                _logService.Warning("Invalid automatic capture interval.");
                return;
            }

            if (seconds <= 0)
            {
                _logService.Warning("Automatic capture interval must be greater than zero.");
                return;
            }

            try
            {
                if (_apiService != null)
                {
                    HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.CaptureSetAutomaticInterval,
                        new
                        {
                            seconds
                        });

                    if (!response.IsSuccessStatusCode)
                    {
                        _logService.Warning($"Unable to set automatic interval. HTTP {(int)response.StatusCode}");
                    }
                    else
                    {
                        _logService.Info($"Automatic interval requested: {seconds:F2}s");                        
                        _ = _soundManager.PlayAsync(SoundEffect.Click);
                        
                    }
                }
            }
            catch (Exception exception)
            {
                _logService.Error(exception);
            }
        }

        private async void OnAutomaticModeClicked(object sender, EventArgs e)
        {
            try
            {
                HttpResponseMessage response =
                    await _apiService.SendAsync(APIEndpoint.CaptureSetAutomaticMode, new
                    {
                        mode = "automatic"
                    });

                if (!response.IsSuccessStatusCode)
                {
                    _logService.Warning($"Unable to set automatic capture mode. HTTP {(int)response.StatusCode}");
                }
            }
            catch (Exception exception)
            {
                _logService.Error(exception);
            }
        }

        private void OnAutomaticIntervalTextChanged(object sender, TextChangedEventArgs e)
        {
            if (!_updatingAutomaticIntervalFromStatus)
            {
                _automaticIntervalDirty = true;
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
            });
        }

        private async void OnCaptureClicked(object sender, EventArgs e)
        {
            try
            {
                bool automaticMode = _status?.Capture?.Mode == "automatic";
                bool automaticWasRunning = _status?.Capture?.AutomaticRunning == true;
                HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.CaptureTrigger);

                if (!response.IsSuccessStatusCode)
                {
                    _logService.Warning($"Unable to trigger capture. HTTP {(int)response.StatusCode}");
                }
                if (!automaticMode)
                {
                    _ = _soundManager.PlayAsync(
                        SoundEffect.Camera_Click_On
                    );

                    _logService.Info(
                        "Single capture triggered."
                    );
                }
                else if (automaticWasRunning)
                {
                    _ = _soundManager.PlayAsync(
                        SoundEffect.Camera_Click_Off
                    );

                    _logService.Info(
                        "Automatic capture stop requested."
                    );
                }
                else
                {
                    _ = _soundManager.PlayAsync(
                        SoundEffect.Camera_Click_On
                    );

                    _logService.Info(
                        "Automatic capture started."
                    );
                }
            }
            catch (Exception exception)
            {
                _logService.Error(exception);
            }
        }

    }
}
