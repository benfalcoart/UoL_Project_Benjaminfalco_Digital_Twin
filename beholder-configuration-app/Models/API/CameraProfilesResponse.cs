using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models.API
{
    public class CameraProfilesResponse
    {
        [JsonPropertyName("profiles")]
        public List<CameraProfileSummary> Profiles { get; set; } = new();
    }
}
