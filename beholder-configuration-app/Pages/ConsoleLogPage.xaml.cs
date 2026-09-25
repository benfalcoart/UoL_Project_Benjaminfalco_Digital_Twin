using beholder_configuration_app.Services.Logging;
using System.Text;
using beholder_configuration_app.Services.Audio;

namespace beholder_configuration_app.Pages;

public partial class ConsoleLogPage : ContentPage
{

    private readonly AppLogService _logService;
    private readonly SoundManager _soundManager;

    public ConsoleLogPage(AppLogService logService, SoundManager soundManager)
	{
		InitializeComponent();
        _logService = logService;
        _soundManager = soundManager;
        LogCollection.ItemsSource = _logService.Entries;
    }
    /// <summary>
    /// Copy the console to the Clipboard for debugging and logging.
    /// </summary>
    /// <param name="sender"></param>
    /// <param name="e"></param>
    private async void OnCopyClicked(object sender, EventArgs e)
    {
        if (LogCollection.ItemsSource is not IEnumerable<LogEntry> entries)
        {
            return;
        }

        StringBuilder logText = new();

        foreach (LogEntry entry in entries)
        {
            logText.AppendLine($"[{entry.Timestamp:HH:mm:ss}] [{entry.Level}] {entry.Message}");
        }
        _ = _soundManager.PlayAsync(SoundEffect.Click);
        _logService.Info("Diagnostic log copied to clipboard.");
        await Clipboard.Default.SetTextAsync(logText.ToString());
    }

    private void OnClearClicked(object sender, EventArgs e)
    {
        _ = _soundManager.PlayAsync(SoundEffect.Click);
        _logService.Clear();
    }

}