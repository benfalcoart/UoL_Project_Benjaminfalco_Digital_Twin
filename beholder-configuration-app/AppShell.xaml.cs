namespace beholder_configuration_app
{
    public partial class AppShell : Shell
    {
        public AppShell(MainPage mainPage)
        {
            InitializeComponent();

            MainShellContent.Content = mainPage;
        }
    }
}
