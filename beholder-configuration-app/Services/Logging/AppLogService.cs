using beholder_configuration_app.Services.Audio;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using System.Collections.ObjectModel;



namespace beholder_configuration_app.Services.Logging
{
    public class AppLogService
    {
        public ObservableCollection<LogEntry> Entries { get; } = new();
        private readonly SoundManager _soundManager;

        public AppLogService(SoundManager soundManager)
        {
            _soundManager = soundManager;
        }
        public void Info(string message)
        {
            Add(LogLevel.Info, message);
        }

        public void Warning(string message)
        {
            Add(LogLevel.Warning, message);
            _ = _soundManager.PlayAsync(SoundEffect.Warning);
        }

        public void Error(string message)
        {
            Add(LogLevel.Error, message);
            _ = _soundManager.PlayAsync(SoundEffect.Error);
        }

        public void Error(Exception exception)
        {
            Add(LogLevel.Error, $"{exception.GetType().Name}: {exception.Message} \n {exception.ToString()}");
            _ = _soundManager.PlayAsync(SoundEffect.Error);
        }

        private void Add(LogLevel level, string message)
        {
            MainThread.BeginInvokeOnMainThread(() =>
            {
                Entries.Add(new LogEntry
                {
                    Timestamp = DateTime.Now,
                    Level = level,
                    Message = message
                });
            });
        }

        public void Clear()
        {
            MainThread.BeginInvokeOnMainThread(() =>
            {
                Entries.Clear();
            });
        }
    }
}