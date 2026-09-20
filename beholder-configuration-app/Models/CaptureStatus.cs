using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models
{
    public class CaptureStatus
    {
        [JsonPropertyName("mode")]
        public string Mode { get; set; } = "";

        [JsonPropertyName("capturing")]
        public bool Capturing { get; set; }

        [JsonPropertyName("automaticRunning")]
        public bool AutomaticRunning { get; set; }

        [JsonPropertyName("automaticIntervalSeconds")]
        public double AutomaticIntervalSeconds { get; set; }
    }
}
