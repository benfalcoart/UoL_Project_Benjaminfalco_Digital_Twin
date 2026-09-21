using Microsoft.Extensions.Logging;

namespace beholder_configuration_app.Services.Logging
{
    public class LogEntry
    {
        public DateTime Timestamp { get; set; }
        public LogLevel Level { get; set; }
        public string Message { get; set; } = "";
    }
}