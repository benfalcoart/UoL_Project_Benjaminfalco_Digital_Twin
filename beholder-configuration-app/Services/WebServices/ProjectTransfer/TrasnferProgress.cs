using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace beholder_configuration_app.Services.WebServices.ProjectTransfer
{
    public class TransferProgress
    {
        public long BytesTransferred { get; set; }
        public long TotalBytes { get; set; }

        public int FilesTransferred { get; set; }
        public int TotalFiles { get; set; }

        public string CurrentFile { get; set; } = "";

        public double Percentage => TotalBytes == 0 ? 0 : (double)BytesTransferred / TotalBytes;
    }
}
