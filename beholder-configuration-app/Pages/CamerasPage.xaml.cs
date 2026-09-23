using beholder_configuration_app.Models;
using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using Microsoft.Maui.Controls.Shapes;
using System.Text.Json;

namespace beholder_configuration_app;

public partial class CamerasPage : ContentPage
{
    private readonly BeholderWebSocketService _webSocketService;
    private readonly BeholderAPIService _apiService;
    private readonly AppLogService _logService;

    private BeholderStatus? _status;

    public CamerasPage(BeholderWebSocketService webSocketService, BeholderAPIService apiService, AppLogService logService)
    {
        InitializeComponent();

        _webSocketService = webSocketService;
        _apiService = apiService;
        _logService = logService;

        _webSocketService.MessageReceived += OnMessageReceived;
    }

    private void OnMessageReceived(string message)
    {
        MainThread.BeginInvokeOnMainThread(() =>
        {
            try
            {
                _status = JsonSerializer.Deserialize<BeholderStatus>(message);
                UpdateCameras();
            }
            catch (Exception exception)
            {
                _logService.Error(exception);
            }
        });
    }
    private void UpdateCameras()
    {
        if (_status?.Cameras == null)
        {
            return;
        }

        CameraSummaryLabel.Text = $"{_status.Cameras.ActiveCount} / {_status.Cameras.DetectedCount} ACTIVE";
        CameraSummaryLabel.TextColor = _status.Cameras.ActiveCount == _status.Cameras.DetectedCount ? Color.FromArgb("#2ECC71") : Color.FromArgb("#F4B400");

        UpdateCameraConfigurationList(_status.Cameras.Items);
    }
    private void UpdateCameraConfigurationList(List<CameraStatus> cameras)
    {
        CameraConfigurationList.Clear();

        foreach (CameraStatus camera in cameras)
        {
            CameraConfigurationList.Add(CreateCameraCard(camera));
        }
    }

    private Border CreateCameraCard(CameraStatus camera)
    {
        Label nameLabel = new()
        {
            Text = camera.Name,
            FontSize = 18,
            FontAttributes = FontAttributes.Bold,
            TextColor = Colors.White
        };

        BoxView activeIndicator = new()
        {
            WidthRequest = 8,
            HeightRequest = 8,
            CornerRadius = 4,
            Color = camera.Active ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C"),
            VerticalOptions = LayoutOptions.Center
        };

        Label activeLabel = new()
        {
            Text = camera.Active ? "ACTIVE" : "DISABLED",
            FontSize = 12,
            FontAttributes = FontAttributes.Bold,
            TextColor = camera.Active ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C"),
            VerticalOptions = LayoutOptions.Center
        };

        HorizontalStackLayout statusLayout = new()
        {
            Spacing = 6,
            Children =
        {
            activeIndicator,
            activeLabel
        }
        };

        Grid header = new()
        {
            ColumnDefinitions =
        {
            new ColumnDefinition(GridLength.Star),
            new ColumnDefinition(GridLength.Auto)
        }
        };

        header.Add(nameLabel, 0);
        header.Add(statusLayout, 1);

        Picker rowPicker = CreateRowPicker(camera);

        Picker slotPicker = CreateSlotPicker(camera);

        Grid pickerGrid = new()
        {
            ColumnDefinitions =
            {
                new ColumnDefinition(90),
                new ColumnDefinition(GridLength.Star)
            },
            RowDefinitions =
            {
                new RowDefinition(GridLength.Auto),
                new RowDefinition(GridLength.Auto)
            },
            RowSpacing = 10
        };

        Label rowLabel = new()
        {
            Text = "Row",
            TextColor = Color.FromArgb("#C9D1D9"),
            VerticalOptions = LayoutOptions.Center
        };

        Label slotLabel = new()
        {
            Text = "Slot",
            TextColor = Color.FromArgb("#C9D1D9"),
            VerticalOptions = LayoutOptions.Center
        };

        pickerGrid.Add(rowLabel, 0, 0);
        pickerGrid.Add(rowPicker, 1, 0);

        pickerGrid.Add(slotLabel, 0, 1);
        pickerGrid.Add(slotPicker, 1, 1);

        Button identifyButton = new()
        {
            Text = "IDENTIFY",
            BackgroundColor = Color.FromArgb("#22252B"),
            TextColor = Color.FromArgb("#3AA0FF"),
            CornerRadius = 8
        };

        identifyButton.Clicked += async (_, _) =>
        {
            await IdentifyCameraAsync(camera.Id);
        };

        Button activeButton = new()
        {
            Text = camera.Active ? "DISABLE" : "ENABLE",
            BackgroundColor = Color.FromArgb("#22252B"),
            TextColor = camera.Active ? Color.FromArgb("#E74C3C") : Color.FromArgb("#2ECC71"),
            CornerRadius = 8
        };

        activeButton.Clicked += async (_, _) =>
        {
            await SetCameraActiveAsync(camera.Id, !camera.Active);
        };

        Grid buttons = new()
        {
            ColumnDefinitions =
            {
                new ColumnDefinition(GridLength.Star),
                new ColumnDefinition(GridLength.Star)
            },
            ColumnSpacing = 10
        };

        buttons.Add(identifyButton, 0);
        buttons.Add(activeButton, 1);

        VerticalStackLayout content = new()
        {
            Spacing = 12,
            Children =
            {
                header,
                pickerGrid,
                buttons
            }
        };

        return new Border
        {
            BackgroundColor = Color.FromArgb("#191919"),
            Stroke = Color.FromArgb("#444444"),
            StrokeThickness = 1,
            Padding = 16,
            StrokeShape = new RoundRectangle
            {
                CornerRadius = 8
            },
            Content = content
        };
    }
    private Picker CreateRowPicker(CameraStatus camera)
    {
        Picker picker = new()
        {
            Title = "Select Row"
        };

        picker.ItemsSource = new List<string>
        {
            "Unassigned",
            "Top",
            "Upper",
            "Middle",
            "Lower",
            "Bottom"
        };

        picker.SelectedItem = GetRowFromSlot(camera.Slot);
        return picker;
    }
    private string GetRowFromSlot(string slot)
    {
        if (string.IsNullOrWhiteSpace(slot) || slot.Equals("unassigned", StringComparison.OrdinalIgnoreCase))
        {
            return "Unassigned";
        }

        return slot[0] switch
        {
            'T' => "Top",
            'U' => "Upper",
            'M' => "Middle",
            'L' => "Lower",
            'B' => "Bottom",
            _ => "Unassigned"
        };
    }

    private Picker CreateSlotPicker(CameraStatus camera)
    {
        Picker picker = new()
        {
            Title = "Select Slot"
        };

        string row =
            GetRowFromSlot(camera.Slot);

        picker.ItemsSource = GetSlotsForRow(row);

        if (!string.IsNullOrWhiteSpace(camera.Slot) &&
            camera.Slot != "unassigned")
        {
            picker.SelectedItem = camera.Slot.ToUpper();
        }

        return picker;
    }
    //TODO: Cache this
    private List<string> GetSlotsForRow(string row)
    {
        return row switch
        {
            "Top" =>
                new()
                {
                "T1"
                },

            "Upper" =>
                new()
                {
                "U1",
                "U2",
                "U3",
                "U4",
                "U5"
                },

            "Middle" =>
                new()
                {
                "M1",
                "M2",
                "M3",
                "M4",
                "M5",
                "M6",
                "M7",
                "M8",
                "M9"
                },

            "Lower" =>
                new()
                {
                "L1",
                "L2",
                "L3",
                "L4",
                "L5"
                },

            "Bottom" =>
                new()
                {
                "B1"
                },

            _ =>
                new()
        };
    }
    private async Task SetCameraActiveAsync(int cameraId, bool active)
    {
        try
        {
            APIEndpoint endpoint = active ? APIEndpoint.CameraEnable : APIEndpoint.CameraDisable;
            HttpResponseMessage response = await _apiService.SendAsync(endpoint, body: new
            {
                cameraId
            });

            if (!response.IsSuccessStatusCode)
            {
                _logService.Warning($"Unable to {(active ? "enable" : "disable")} camera {cameraId}. HTTP {(int)response.StatusCode}");
                return;
            }
            _logService.Info($"Camera {cameraId} {(active ? "enable" : "disable")} requested.");
        }
        catch (Exception exception)
        {
            _logService.Error(exception);
        }
    }
    private async Task IdentifyCameraAsync(int cameraId)
    {
        try
        {
            HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.CameraIdentify, body: new
            {
                cameraId
            });

            if (!response.IsSuccessStatusCode)
            {
                _logService.Warning($"Unable to identify camera {cameraId}. HTTP {(int)response.StatusCode}");
            }
        }
        catch (Exception exception)
        {
            _logService.Error(exception);
        }
    }
}