using beholder_configuration_app.Models;
using beholder_configuration_app.Pages;
using beholder_configuration_app.Services.Audio;
using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using beholder_configuration_app.Services.WebServices.ProjectTransfer;
using CommunityToolkit.Maui.Storage;
using System.Net.Http.Json;
using System.Text.Json;

namespace beholder_configuration_app;

public partial class SettingsPage : ContentPage
{
    private BeholderStatus? _status;
    private readonly BeholderWebSocketService _webSocketService;
    private readonly BeholderAPIService _apiService;
    private readonly AppLogService _logService;
    private readonly ProjectTransferService _projectTransferService;
    private readonly IFolderPicker _folderPicker;
    private readonly SoundManager _soundManager;
    private readonly BeholderConnectionSettings _connectionSettings;


    private bool _loadingPreferences;
    public SettingsPage(BeholderWebSocketService webSocketService, BeholderAPIService apiService, AppLogService logService, ProjectTransferService transferService, IFolderPicker folderPicker, SoundManager soundManager, BeholderConnectionSettings connectionSettings)
    {
        InitializeComponent();
        _webSocketService = webSocketService;
        _apiService = apiService;
        _logService = logService;
        _projectTransferService = transferService;
        _folderPicker = folderPicker;
        _soundManager = soundManager;
        _connectionSettings = connectionSettings;

        _webSocketService.MessageReceived += OnMessageReceived;
        _webSocketService.ConnectionChanged += OnConnectionChanged;

        LoadPreferences();
    }

    protected override void OnAppearing()
    {
        base.OnAppearing();
        UpdateConnectionSettings();
        UpdateConnectionStatus(_webSocketService.IsConnected);
    }
    private void UpdateConnectionSettings()
    {
        ConnectionAddressLabel.Text = $"{_connectionSettings.Address}:{_connectionSettings.Port}";
    }
    private void LoadPreferences()
    {
        _loadingPreferences = true;

        KeepScreenAwakeSwitch.IsToggled = Preferences.Default.Get("KeepScreenAwake", true);
        HapticFeedbackSwitch.IsToggled = Preferences.Default.Get("HapticFeedback", true);
        CaptureSoundSwitch.IsToggled = Preferences.Default.Get("CaptureSound", false);
        double interval = Preferences.Default.Get("DefaultAutomaticInterval", 0.5);
        DefaultIntervalEntry.Text = interval.ToString("F2");
        DeviceDisplay.Current.KeepScreenOn = KeepScreenAwakeSwitch.IsToggled;
        _loadingPreferences = false;
    }
    private void OnKeepScreenAwakeToggled(object sender, ToggledEventArgs e)
    {
        if (_loadingPreferences)
        {
            return;
        }
        Preferences.Default.Set("KeepScreenAwake", e.Value);
        DeviceDisplay.Current.KeepScreenOn = e.Value;
        _logService.Info($"Keep screen awake: {e.Value}");
        _ = _soundManager.PlayAsync(SoundEffect.Click);
    }
    private void OnHapticFeedbackToggled(object sender, ToggledEventArgs e)
    {
        if (_loadingPreferences)
        {
            return;
        }
        Preferences.Default.Set("HapticFeedback", e.Value);
        _logService.Info($"Haptic feedback: {e.Value}");
        _ = _soundManager.PlayAsync(SoundEffect.Click);
    }

    //TODO: Add a sound effect to the capture
    private void OnCaptureSoundToggled(object sender, ToggledEventArgs e)
    {
        if (_loadingPreferences)
        {
            return;
        }
        Preferences.Default.Set("CaptureSound", e.Value);

        _logService.Info($"Capture sound: {e.Value}");
        _ = _soundManager.PlayAsync(SoundEffect.Click);
    }
    private void OnDefaultIntervalUnfocused(object sender, FocusEventArgs e)
    {
        if (!double.TryParse(DefaultIntervalEntry.Text, out double interval))
        {
            _logService.Warning("Invalid default automatic interval.");
            DefaultIntervalEntry.Text = Preferences.Default.Get("DefaultAutomaticInterval", 0.5).ToString("F2");
            return;
        }

        if (interval <= 0)
        {
            _logService.Warning("Default interval must be greater than zero.");
            return;
        }

        Preferences.Default.Set("DefaultAutomaticInterval", interval);

        DefaultIntervalEntry.Text = interval.ToString("F2");
        _logService.Info($"Default automatic interval set to {interval:F2}s.");
    }
       

    private void OnMessageReceived(string message)
    {
        MainThread.BeginInvokeOnMainThread(() =>
        {
            try
            {
                _status = JsonSerializer.Deserialize<BeholderStatus>(message);

                UpdateProjectStatus();
            }
            catch (Exception exception)
            {
                _logService.Error(exception);
            }
        });
    }
    private void UpdateConnectionStatus(bool connected)
    {
        SettingsConnectionStatusLabel.Text = connected ? "CONNECTED" : "DISCONNECTED";
        SettingsConnectionStatusLabel.TextColor = connected ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C");
        SettingsConnectionIndicator.Color = connected ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C");
        WebSocketStatusLabel.Text = connected ? "Connected" : "Disconnected";
        WebSocketStatusLabel.TextColor = connected ? Color.FromArgb("#2ECC71") : Color.FromArgb("#E74C3C");
        if (connected)
        {
            ConnectionAddressLabel.Text = $"{_connectionSettings.Address}:{_connectionSettings.Port}";
        }
        else
        {
            ConnectionAddressLabel.Text = "No active connection";
        }
    }
    private void UpdateProjectStatus()
    {
        if (_status?.Project == null)
        {
            TransferProjectNameLabel.Text = "No project selected";
            TransferProjectStatsLabel.Text = "— images · — GB";
            return;
        }

        TransferProjectNameLabel.Text = _status.Project.Name;
        TransferProjectStatsLabel.Text = $"Last capture #{_status.Project.LastCaptureId}";
    }
    private void OnConnectionChanged(bool connected)
    {
        MainThread.BeginInvokeOnMainThread(() =>
        {
            UpdateConnectionSettings();
            UpdateConnectionStatus(connected);
        });
    }
    private async void OnResetPreferencesClicked(object sender, EventArgs e)
    {
        bool confirmed = await DisplayAlert("Reset Preferences", "Reset all BEHOLDER app preferences to their defaults?", "RESET", "CANCEL");

        if (!confirmed)
        {
            return;
        }

        Preferences.Default.Remove("KeepScreenAwake");
        Preferences.Default.Remove("HapticFeedback");
        Preferences.Default.Remove("CaptureSound");
        Preferences.Default.Remove("DefaultAutomaticInterval");

        LoadPreferences();

        _logService.Info("Application preferences reset.");
        _ = _soundManager.PlayAsync(SoundEffect.Click);
    }
    private async void OnOffloadCurrentProjectClicked(object sender, EventArgs e)
    {
        string projectName = TransferProjectNameLabel.Text;

        if (string.IsNullOrWhiteSpace(projectName) || projectName == "No project selected")
        {
            _logService.Warning("No project selected for offload.");
            return;
        }

        FolderPickerResult folderResult = await _folderPicker.PickAsync(CancellationToken.None);

        if (!folderResult.IsSuccessful)
        {
            if (folderResult.Exception != null)
            {
                _logService.Error(folderResult.Exception);
            }
            return;
        }

        string destination = folderResult.Folder.Path;

        Progress<TransferProgress> progress = new(update =>
        {
            TransferProgressBar.Progress = update.Percentage;
            TransferPercentLabel.Text = $"{update.Percentage:P0}";
            TransferStatusLabel.Text = $"{update.FilesTransferred} / {update.TotalFiles} files";
            TransferFileLabel.Text = update.CurrentFile;
        });

        try
        {
            TransferProgressPanel.IsVisible = true;

            TransferProgressBar.Progress = 0;
            TransferPercentLabel.Text = "0%";
            TransferStatusLabel.Text = "Preparing transfer...";
            TransferFileLabel.Text = "";
            _ = _soundManager.PlayAsync(SoundEffect.Click);
            await _projectTransferService.OffloadProjectAsync(projectName, destination, progress);

            TransferProgressBar.Progress = 1;
            TransferPercentLabel.Text = "100%";
            TransferStatusLabel.Text = "Transfer complete";
            _ = _soundManager.PlayAsync(SoundEffect.Success);
            _logService.Info($"Project '{projectName}' offloaded to '{destination}'.");
        }
        catch (Exception exception)
        {
            TransferStatusLabel.Text = "Transfer failed";
            _logService.Error(exception);
        }
    }
    private async void OnOffloadAllProjectsClicked(object sender, EventArgs e)
    {
        FolderPickerResult folderResult = await _folderPicker.PickAsync(CancellationToken.None);

        if (!folderResult.IsSuccessful)
        {
            if (folderResult.Exception != null)
            {
                _logService.Error(folderResult.Exception);
            }
            return;
        }

        string destination = folderResult.Folder.Path;

        try
        {
            HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.ProjectGetAll);

            if (!response.IsSuccessStatusCode)
            {
                _logService.Warning($"Unable to retrieve projects. HTTP {(int)response.StatusCode}");
                return;
            }

            List<ProjectInfo>? projects = await response.Content.ReadFromJsonAsync<List<ProjectInfo>>();

            if (projects == null ||
                projects.Count == 0)
            {
                _logService.Warning("No projects found to offload.");
                return;
            }

            TransferProgressPanel.IsVisible = true;

            TransferProgressBar.Progress = 0;
            TransferPercentLabel.Text = "0%";
            TransferStatusLabel.Text = "Preparing transfer...";
            TransferFileLabel.Text = "";

            for (int i = 0; i < projects.Count; i++)
            {
                ProjectInfo project = projects[i];

                int projectNumber = i + 1;

                Progress<TransferProgress> progress = new(update =>
                    {
                        TransferProgressBar.Progress = update.Percentage;

                        TransferPercentLabel.Text = $"{update.Percentage:P0}";

                        TransferStatusLabel.Text = $"Project {projectNumber} / {projects.Count} · {update.FilesTransferred} / {update.TotalFiles} files";

                        TransferFileLabel.Text = $"{project.Name} · {update.CurrentFile}";
                    });
                _ = _soundManager.PlayAsync(SoundEffect.Click);
                _logService.Info($"Offloading project '{project.Name}'.");
                await _projectTransferService.OffloadProjectAsync(project.Name, destination, progress);
            }

            TransferProgressBar.Progress = 1;
            TransferPercentLabel.Text = "100%";
            _ = _soundManager.PlayAsync(SoundEffect.Success);
            TransferStatusLabel.Text = $"Transfer complete · {projects.Count} projects";
            TransferFileLabel.Text = "";

            _logService.Info($"All {projects.Count} projects offloaded to '{destination}'.");
        }
        catch (Exception exception)
        {
            TransferStatusLabel.Text = "Transfer failed";
            _logService.Error(exception);
        }
    }
}