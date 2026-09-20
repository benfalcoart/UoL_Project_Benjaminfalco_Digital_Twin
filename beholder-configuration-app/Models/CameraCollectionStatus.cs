using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models
{
    public class CameraCollectionStatus
    {
        [JsonPropertyName("detectedCount")]
        public int DetectedCount { get; set; }

        [JsonPropertyName("activeCount")]
        public int ActiveCount { get; set; }

        [JsonPropertyName("items")]
        public List<CameraStatus> Items { get; set; } = [];
    }

}
