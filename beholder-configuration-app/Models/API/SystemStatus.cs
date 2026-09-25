using Microsoft.Maui.Devices;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models
{
    public class SystemStatus
    {
        [JsonPropertyName("state")]
        public string State { get; set; } = "";

        [JsonPropertyName("temperatureC")]
        public double TemperatureC { get; set; }

        [JsonPropertyName("storageFreeGb")]
        public double StorageFreeGb { get; set; }

        [JsonPropertyName("battery")]
        public BatteryStatus? Battery { get; set; }
    }
}
