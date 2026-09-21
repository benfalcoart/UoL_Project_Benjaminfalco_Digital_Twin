using beholder_configuration_app.Pages;

namespace beholder_configuration_app
{
    public partial class AppShell : Shell
    {
        private const double CompactWidth = 700;

        public AppShell(MainPage mainPage, ConnectionPage connectionPage, ProjectsPage projectsPage, CamerasPage camerasPage, SettingsPage settingsPage)
        {
            InitializeComponent();
            //Page set up for navigation:
            MainShellContent.Content = mainPage;
            ConnectionPage.Content = connectionPage;
            ProjectsContent.Content = projectsPage;
            CamerasContent.Content = camerasPage;
            SettingsContent.Content = settingsPage;

            Routing.RegisterRoute(nameof(ConsoleLogPage), typeof(ConsoleLogPage));


            //Connection Page:
            //Routing.RegisterRoute(nameof(ConnectionPage), typeof(ConnectionPage));
        }

    }
}
