using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models.API
{
    public class CameraSettingsResponse
    {
        [JsonPropertyName("cameras")]
        public Dictionary<string, Dictionary<string, int>> Cameras { get; set; } = new();
    }
}
