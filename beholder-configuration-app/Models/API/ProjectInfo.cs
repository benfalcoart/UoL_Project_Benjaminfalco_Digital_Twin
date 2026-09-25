using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace beholder_configuration_app.Models
{
    class ProjectInfo
    {
        public string Name { get; set; } = "";
        public int ImageCount { get; set; }
        public double SizeGb { get; set; }
        public int LastCaptureId { get; set; }
    }
}
