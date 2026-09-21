using Microsoft.Extensions.Logging;
using beholder_configuration_app.Services;

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
            //Websocket Service:
            builder.Services.AddSingleton<BeholderWebSocketService>();
            //App pages:
            builder.Services.AddSingleton<MainPage>();
            builder.Services.AddSingleton<ConnectionPage>();
            builder.Services.AddSingleton<ProjectsPage>();
            builder.Services.AddSingleton<SettingsPage>();
            builder.Services.AddSingleton<CamerasPage>();
            //App Shell:
            builder.Services.AddSingleton<AppShell>();

            return builder.Build();
        }
    }
}
