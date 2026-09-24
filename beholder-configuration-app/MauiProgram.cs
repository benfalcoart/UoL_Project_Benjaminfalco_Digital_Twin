using Plugin.Maui.Audio;
using beholder_configuration_app.Services.Audio;
using beholder_configuration_app.Pages;
using beholder_configuration_app.Services;
using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using beholder_configuration_app.Services.WebServices.ProjectTransfer;
using CommunityToolkit.Maui;
using CommunityToolkit.Maui.Storage;
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
                .UseMauiCommunityToolkit()
                .ConfigureFonts(fonts =>
                {
                    fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
                    fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold");
                });

#if DEBUG
    		builder.Logging.AddDebug();
#endif
            //Audio Pluggin:
            builder.AddAudio();
            builder.Services.AddSingleton<SoundManager>();
            //Community Tools Pluggins:
            builder.Services.AddSingleton<IFolderPicker>(FolderPicker.Default);
            //Logging Service:
            builder.Services.AddSingleton<AppLogService>();
            //Web Services:
            builder.Services.AddSingleton<HttpClient>();
            builder.Services.AddSingleton<BeholderConnectionSettings>();
            builder.Services.AddSingleton<BeholderWebSocketService>();
            builder.Services.AddSingleton<BeholderAPIService>();
            builder.Services.AddSingleton<ProjectTransferService>();            
            //App pages:
            builder.Services.AddSingleton<MainPage>();
            builder.Services.AddSingleton<ConnectionPage>();
            builder.Services.AddSingleton<ProjectsPage>();
            builder.Services.AddSingleton<SettingsPage>();
            builder.Services.AddSingleton<CamerasPage>();
            builder.Services.AddSingleton<ConsoleLogPage>();
            //App Shell:
            builder.Services.AddSingleton<AppShell>();

            return builder.Build();
        }
    }
}
