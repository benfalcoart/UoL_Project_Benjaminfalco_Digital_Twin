using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace beholder_configuration_app.Services.WebServices.ProjectTransfer
{
    public class TransferManifest
    {
        public string ProjectName { get; set; } = "";
        public int FileCount { get; set; }
        public long TotalBytes { get; set; }
        public List<TransferFile> Files { get; set; } = new();
    }
}
