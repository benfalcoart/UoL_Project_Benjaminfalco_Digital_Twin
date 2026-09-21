using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using System.Collections.ObjectModel;



namespace beholder_configuration_app.Services.Logging
{
    public class AppLogService
    {
        public ObservableCollection<LogEntry> Entries { get; } = new();

        public void Info(string message)
        {
            Add(LogLevel.Info, message);
        }

        public void Warning(string message)
        {
            Add(LogLevel.Warning, message);
        }

        public void Error(string message)
        {
            Add(LogLevel.Error, message);
        }

        public void Error(Exception exception)
        {
            Add(LogLevel.Error, $"{exception.GetType().Name}: {exception.Message} \n {exception.ToString()}");
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