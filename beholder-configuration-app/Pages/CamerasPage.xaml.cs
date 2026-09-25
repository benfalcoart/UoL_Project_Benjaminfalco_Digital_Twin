using beholder_configuration_app.Models;
using beholder_configuration_app.Services.Audio;
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
    private readonly SoundManager _soundManager;

    private BeholderStatus? _status;

    private readonly Dictionary<int, CameraCardControls> _cameraCards = new();

    //Slot buttons at the top to identify which slot camera is in.
    private readonly Dictionary<string, Button> _slotButtons;

    private List<Color> _cameraColors;
    private readonly Dictionary<int, Color> _selectedCameraColors = new();

    public CamerasPage(BeholderWebSocketService webSocketService, BeholderAPIService apiService, AppLogService logService, SoundManager soundManager)
    {
        InitializeComponent();

        _webSocketService = webSocketService;
        _apiService = apiService;
        _logService = logService;
        _soundManager = soundManager;

        _webSocketService.MessageReceived += OnMessageReceived;
        //Set up the slot "buttons" for visually representing the camera set up.
        _slotButtons = new()
        {
            //TOP
            { "T1", T1Button },
            //UPPER
            { "U1", U1Button },
            { "U2", U2Button },
            { "U3", U3Button },
            { "U4", U4Button },
            { "U5", U5Button },
            //MIDDLE
            { "M1", M1Button },
            { "M2", M2Button },
            { "M3", M3Button },
            { "M4", M4Button },
            { "M5", M5Button },
            { "M6", M6Button },
            { "M7", M7Button },
            { "M8", M8Button },
            { "M9", M9Button },
            //LOWER
            { "L1", L1Button },
            { "L2", L2Button },
            { "L3", L3Button },
            { "L4", L4Button },
            { "L5", L5Button },
            //BOTTOM
            { "B1", B1Button }
        };
        _cameraColors = new()
        {
            Color.FromArgb("#3AA0FF"),
            Color.FromArgb("#9B59B6"),
            Color.FromArgb("#E67E22"),
            Color.FromArgb("#2ECC71"),
            Color.FromArgb("#E74C3C"),
            Color.FromArgb("#F4B400")
        };
        ;
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
        UpdatePhysicalLayout(_status.Cameras.Items);
    }
    private void UpdateCameraConfigurationList(List<CameraStatus> cameras)
    {
        foreach (CameraStatus camera in cameras)
        {
            if (!_cameraCards.TryGetValue(camera.Id, out CameraCardControls? controls))
            {
                controls = CreateCameraCard(camera);
                _cameraCards[camera.Id] = controls;
                CameraConfigurationList.Add(controls.Card);
            }

            UpdateCameraCard(camera, controls);
        }
    }
    private void SetCameraColor(int cameraId, Color color)
    {
        _selectedCameraColors[cameraId] = color;
        if (_status?.Cameras != null)
        {
            UpdatePhysicalLayout(_status.Cameras.Items);
        }
    }
    private CameraCardControls CreateCameraCard(CameraStatus camera)
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

        HorizontalStackLayout colorPicker = new()
        {
            Spacing = 8
        };

        foreach (Color color in _cameraColors)
        {
            Button colorButton = new()
            {
                WidthRequest = 28,
                HeightRequest = 28,
                CornerRadius = 14,
                Padding = 0,
                BackgroundColor = color
            };

            colorButton.Clicked += (_, _) =>
            {
                SetCameraColor(camera.Id, color);
            };

            colorPicker.Add(colorButton);
        }

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

        Image identifyImage = new()
        {
            IsVisible = false,
            HeightRequest = 240,
            Aspect = Aspect.AspectFit
        };

        activeButton.Clicked += async (_, _) =>
        {
            CameraStatus? current = _status?.Cameras?.Items.FirstOrDefault(item => item.Id == camera.Id);
            if (current == null)
            {
                return;
            }
            await SetCameraActiveAsync(camera.Id, !current.Active);
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
                colorPicker,
                buttons,
                identifyImage
            }
        };

        Border card = new()
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

        CameraCardControls controls = new()
        {
            Card = card,
            ActiveLabel = activeLabel,
            ActiveIndicator = activeIndicator,
            RowPicker = rowPicker,
            SlotPicker = slotPicker,
            ActiveButton = activeButton,
            IdentifyImage = identifyImage
        };

        rowPicker.SelectedIndexChanged += async (_, _) =>
        {
            if (controls.UpdatingFromStatus)
            {
                return;
            }

            if (rowPicker.SelectedItem is not string row)
            {
                return;
            }

            controls.UserEditingSlot = true;

            slotPicker.ItemsSource = GetSlotsForRow(row);
            slotPicker.SelectedItem = null;

            if (row == "Unassigned")
            {
                await SetCameraSlotAsync(camera.Id, "unassigned");
                controls.UserEditingSlot = false;
            }
        };

        slotPicker.SelectedIndexChanged += async (_, _) =>
        {
            if (controls.UpdatingFromStatus)
            {
                return;
            }

            if (slotPicker.SelectedItem is not string slot)
            {
                return;
            }

            await SetCameraSlotAsync(camera.Id, slot);

            controls.UserEditingSlot = false;
        };

        return controls;
    }

    private async Task SetCameraSlotAsync(int cameraId, string slot)
    {
        try
        {
            HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.CameraSetSlot, new
            {
                cameraId,
                slot
            });

            if (!response.IsSuccessStatusCode)
            {
                _logService.Warning($"Unable to set camera {cameraId} to slot {slot}. HTTP {(int)response.StatusCode}");
                return;
            }

            _logService.Info($"Camera {cameraId} assigned to {slot}.");
        }
        catch (Exception exception)
        {
            _logService.Error(exception);
        }
    }

    private void UpdatePhysicalLayout(List<CameraStatus> cameras)
    {
        foreach (Button button in _slotButtons.Values)
        {
            button.BackgroundColor = Color.FromArgb("#22252B");
            button.TextColor = Color.FromArgb("#8B949E");
        }

        foreach (CameraStatus camera in cameras)
        {
            if (string.IsNullOrWhiteSpace(camera.Slot) || camera.Slot.Equals("unassigned", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            string slot = camera.Slot.ToUpper();

            if (_slotButtons.TryGetValue(slot, out Button? button))
            {
                Color cameraColor = _selectedCameraColors.TryGetValue(camera.Id, out Color? selectedColor) ? selectedColor : _cameraColors[camera.Id % _cameraColors.Count];
                button.BackgroundColor = cameraColor;
                button.TextColor = Colors.White;
            }
        }
    }
    private void UpdateCameraCard(CameraStatus camera, CameraCardControls controls)
    {
        controls.ActiveIndicator.Color = camera.Active ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C");
        controls.ActiveLabel.Text = camera.Active ? "ACTIVE" : "DISABLED";
        controls.ActiveLabel.TextColor = camera.Active ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C");
        controls.ActiveButton.Text = camera.Active ? "DISABLE" : "ENABLE";
        controls.ActiveButton.TextColor = camera.Active ? Color.FromArgb("#E74C3C") : Color.FromArgb("#2ECC71");

        if (controls.UserEditingSlot)
        {
            return;
        }
        string row = GetRowFromSlot(camera.Slot);
        controls.UpdatingFromStatus = true;

        if (!Equals(controls.RowPicker.SelectedItem, row))
        {
            controls.RowPicker.SelectedItem = row;
            controls.SlotPicker.ItemsSource = GetSlotsForRow(row);
        }

        string? slot = camera.Slot.Equals("unassigned", StringComparison.OrdinalIgnoreCase) ? null : camera.Slot.ToUpper();

        if (!Equals(controls.SlotPicker.SelectedItem, slot))
        {
            controls.SlotPicker.SelectedItem = slot;
        }
        controls.UpdatingFromStatus = false;
    }

    private Picker CreateRowPicker(CameraStatus camera)
    {
        Picker picker = new()
        {
            Title = "Select Row",
            BackgroundColor = Color.FromArgb("#1A1D21")
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
            Title = "Select Slot",
            BackgroundColor = Color.FromArgb("#1A1D21")
        };

        string row = GetRowFromSlot(camera.Slot);

        picker.ItemsSource = GetSlotsForRow(row);

        if (!string.IsNullOrWhiteSpace(camera.Slot) && camera.Slot != "unassigned")
        {
            picker.SelectedItem = camera.Slot.ToUpper();
        }

        return picker;
    }

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
            if (endpoint == APIEndpoint.CameraEnable)
            {
                _ = _soundManager.PlayAsync(SoundEffect.Camera_Click_On);
            }
            else if (endpoint == APIEndpoint.CameraDisable)
            {
                _ = _soundManager.PlayAsync(SoundEffect.Camera_Click_Off);
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

            if (!_cameraCards.TryGetValue(cameraId, out CameraCardControls? controls))
            {
                return;
            }
            //Create the image from the Byte Array.
            byte[] imageBytes = await response.Content.ReadAsByteArrayAsync();

            controls.IdentifyImage.Source = ImageSource.FromStream(() => new MemoryStream(imageBytes));
            controls.IdentifyImage.IsVisible = true;
            _ = _soundManager.PlayAsync(SoundEffect.Camera_Click_On);
            _logService.Info($"Camera {cameraId} identified.");
        }
        catch (Exception exception)
        {
            _logService.Error(exception);
        }
    }
}