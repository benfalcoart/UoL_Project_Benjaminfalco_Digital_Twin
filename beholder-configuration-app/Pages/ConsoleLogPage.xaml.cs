using beholder_configuration_app.Services.Logging;

namespace beholder_configuration_app.Pages;

public partial class ConsoleLogPage : ContentPage
{

    private readonly AppLogService _logService;

    public ConsoleLogPage(AppLogService logService)
	{
		InitializeComponent();
        _logService = logService;
        LogCollection.ItemsSource = _logService.Entries;
    }
    private void OnClearClicked(object sender, EventArgs e)
    {
        _logService.Clear();
    }
}