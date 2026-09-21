using beholder_configuration_app.Pages;

namespace beholder_configuration_app;

public partial class SettingsPage : ContentPage
{
	public SettingsPage()
	{
		InitializeComponent();
	}

    private void OnManageConnectionClicked(object sender, EventArgs e)
    {
        
    }
    private async void OnViewDiagnosticLogClicked(object sender, EventArgs e)
    {
        await Shell.Current.GoToAsync(nameof(ConsoleLogPage));
    }
}