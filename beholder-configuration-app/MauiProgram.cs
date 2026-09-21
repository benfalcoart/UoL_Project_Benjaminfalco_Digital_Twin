using beholder_configuration_app.Pages;
using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using Microsoft.Extensions.Logging;

namespace beholder_configuration_app
{
    public static class MauiProgram
    {
        public static MauiApp CreateMauiApp()
        {
            var builder = MauiApp.CreateBuilder();
            builder
                .UseMauiApp<App>()
                .ConfigureFonts(fonts =>
                {
                    fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
                    fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold");
                });

#if DEBUG
    		builder.Logging.AddDebug();
#endif
            //Web Services:
            builder.Services.AddSingleton<BeholderWebSocketService>();
            builder.Services.AddSingleton<BeholderAPIService>();
            //Logging Service:
            builder.Services.AddSingleton<AppLogService>();
            //App pages:
            builder.Services.AddSingleton<MainPage>();
            builder.Services.AddSingleton<ConnectionPage>();
            builder.Services.AddSingleton<ProjectsPage>();
            builder.Services.AddSingleton<SettingsPage>();
            builder.Services.AddSingleton<CamerasPage>();
            builder.Services.AddTransient<ConsoleLogPage>();
            //App Shell:
            builder.Services.AddSingleton<AppShell>();

            return builder.Build();
        }
    }
}
