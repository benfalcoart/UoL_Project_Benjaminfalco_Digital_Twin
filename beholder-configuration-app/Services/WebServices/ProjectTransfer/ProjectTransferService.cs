using beholder_configuration_app.Services.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http.Json;
using System.Text;
using System.Threading.Tasks;

namespace beholder_configuration_app.Services.WebServices.ProjectTransfer
{
    public class ProjectTransferService
    {
        private readonly BeholderAPIService _apiService;
        private readonly AppLogService _logService;

        public ProjectTransferService(BeholderAPIService apiService, AppLogService logService)
        {
            _apiService = apiService;
            _logService = logService;
        }

        private async Task<TransferManifest> GetManifestAsync(string projectName)
        {
            HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.ProjectTransferManifest, body: new
            {
                projectName
            });

            response.EnsureSuccessStatusCode();
            TransferManifest? manifest = await response.Content.ReadFromJsonAsync<TransferManifest>();
            if (manifest == null)
            {
                throw new InvalidOperationException("BEHOLDER returned an invalid transfer manifest.");
            }

            return manifest;
        }

        public async Task OffloadProjectAsync(string projectName, string destination, IProgress<TransferProgress>? progress = null)
        {
            TransferManifest manifest = await GetManifestAsync(projectName);
            string projectDirectory = Path.Combine(destination, projectName);
            Directory.CreateDirectory(projectDirectory);

            long bytesTransferred = 0;
            int filesTransferred = 0;

            foreach (TransferFile file in manifest.Files)
            {
                HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.ProjectTransferFile, body: new
                {
                    projectName,
                    path = file.Path
                },
                completionOption: HttpCompletionOption.ResponseHeadersRead);

                response.EnsureSuccessStatusCode();

                string localPath = Path.Combine(projectDirectory, file.Path.Replace('/', Path.DirectorySeparatorChar));
                string? directory = Path.GetDirectoryName(localPath);

                if (directory != null)
                {
                    Directory.CreateDirectory(directory);
                }

                await using Stream input = await response.Content.ReadAsStreamAsync();
                await using FileStream output = File.Create(localPath);

                byte[] buffer = new byte[64 * 1024];

                int bytesRead;

                while ((bytesRead = await input.ReadAsync(buffer)) > 0)
                {
                    await output.WriteAsync(buffer.AsMemory(0, bytesRead));
                    bytesTransferred += bytesRead;

                    progress?.Report(new TransferProgress
                    {
                        BytesTransferred = bytesTransferred,
                        TotalBytes = manifest.TotalBytes,
                        FilesTransferred = filesTransferred,
                        TotalFiles = manifest.FileCount,
                        CurrentFile = file.Path
                    });
                }

                filesTransferred++;
            }

            _logService.Info($"Project '{projectName}' offloaded successfully.");
        }
    }
}