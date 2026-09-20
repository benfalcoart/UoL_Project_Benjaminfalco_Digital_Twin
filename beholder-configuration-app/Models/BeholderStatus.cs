using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models
{
    /// <summary>
    /// This class corresponds to the beholder's websocket status update.
    /// </summary>
    public class BeholderStatus
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "";

        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = "";

        [JsonPropertyName("system")]
        public SystemStatus? System { get; set; }

        [JsonPropertyName("project")]
        public ProjectStatus? Project { get; set; }

        [JsonPropertyName("capture")]
        public CaptureStatus? Capture { get; set; }

        [JsonPropertyName("cameras")]
        public CameraCollectionStatus? Cameras { get; set; }

        /// <summary>
        /// Output the Class Data for Debugging and testing
        /// </summary>
        /// <returns></returns>
        public override string ToString()
        {
            StringBuilder output = new();

            output.AppendLine($"Type: {Type}");
            output.AppendLine($"Timestamp: {Timestamp}");
            output.AppendLine();

            if (System != null)
            {
                output.AppendLine("SYSTEM");
                output.AppendLine($"State: {System.State}");
                output.AppendLine($"Temperature: {System.TemperatureC:F1} C");
                output.AppendLine($"Storage Free: {System.StorageFreeGb:F2} GB");

                if (System.Battery != null)
                {
                    output.AppendLine($"Battery: {System.Battery.Percentage:F1}%");
                    output.AppendLine($"Voltage: {System.Battery.Voltage:F3} V");
                    output.AppendLine($"Current: {System.Battery.CurrentA:F4} A");
                    output.AppendLine($"Power: {System.Battery.PowerW:F3} W");
                }

                output.AppendLine();
            }

            output.AppendLine("PROJECT");

            if (Project != null)
            {
                output.AppendLine($"Name: {Project.Name}");
                output.AppendLine($"Last Capture ID: {Project.LastCaptureId}");
            }
            else
            {
                output.AppendLine("No project selected");
            }

            output.AppendLine();

            if (Capture != null)
            {
                output.AppendLine("CAPTURE");
                output.AppendLine($"Mode: {Capture.Mode}");
                output.AppendLine($"Capturing: {Capture.Capturing}");
                output.AppendLine($"Automatic Running: {Capture.AutomaticRunning}");
                output.AppendLine(
                    $"Automatic Interval: {Capture.AutomaticIntervalSeconds:F2} s"
                );

                output.AppendLine();
            }

            if (Cameras != null)
            {
                output.AppendLine("CAMERAS");
                output.AppendLine($"Detected: {Cameras.DetectedCount}");
                output.AppendLine($"Active: {Cameras.ActiveCount}");

                foreach (CameraStatus camera in Cameras.Items)
                {
                    output.AppendLine(
                        $"Camera {camera.Id}: {camera.Name} | " +
                        $"Active: {camera.Active} | " +
                        $"Slot: {camera.Slot}"
                    );
                }
            }

            return output.ToString();
        }

    }
}
