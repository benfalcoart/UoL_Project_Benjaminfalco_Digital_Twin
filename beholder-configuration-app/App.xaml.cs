using Microsoft.Maui.Controls;

namespace beholder_configuration_app
{
    public partial class App : Application
    {
        private readonly AppShell _appShell;
        Window? mainWindow;
        public App(AppShell appShell)
        {
            InitializeComponent();
            //Change to Dark theme. "We have cookies".
            UserAppTheme = AppTheme.Dark;
            _appShell = appShell;
        }

        protected override Window CreateWindow(IActivationState? activationState)
        {
            mainWindow = new(_appShell);
            return mainWindow;
        }
        

    }
}