using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models
{
    public class BatteryStatus
    {
        [JsonPropertyName("percentage")]
        public double Percentage { get; set; }

        [JsonPropertyName("voltage")]
        public double Voltage { get; set; }

        [JsonPropertyName("currentA")]
        public double CurrentA { get; set; }

        [JsonPropertyName("powerW")]
        public double PowerW { get; set; }
    }
}
