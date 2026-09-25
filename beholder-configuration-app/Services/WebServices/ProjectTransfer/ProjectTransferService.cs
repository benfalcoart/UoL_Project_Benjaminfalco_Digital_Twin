using beholder_configuration_app.Services.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http.Json;
using System.Text;
using System.Threading.Tasks;
#if ANDROID
using Android.Content;
using Android.Provider;
#endif

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
#if !ANDROID
            Directory.CreateDirectory(projectDirectory);
#endif

            long bytesTransferred = 0;
            int filesTransferred = 0;

            foreach (TransferFile file in manifest.Files)
            {
                using HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.ProjectTransferFile, body: new
                {
                    projectName,
                    path = file.Path
                },
                completionOption: HttpCompletionOption.ResponseHeadersRead).ConfigureAwait(false);
                response.EnsureSuccessStatusCode();
                await using Stream input = await response.Content.ReadAsStreamAsync().ConfigureAwait(false);
#if ANDROID

                await using Stream output = CreateAndroidDownloadStream(projectName, file.Path);

#else

                string localPath = Path.Combine(projectDirectory, file.Path.Replace('/', Path.DirectorySeparatorChar));
                string? directory = Path.GetDirectoryName(localPath);

                if (directory != null)
                {
                    Directory.CreateDirectory(directory);
                }
                await using FileStream output = File.Create(localPath);
#endif

                byte[] buffer = new byte[64 * 1024];

                int bytesRead;

                while ((bytesRead = await input.ReadAsync(buffer)) > 0)
                {
                    await output.WriteAsync(buffer.AsMemory(0, bytesRead)).ConfigureAwait(false);
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

#if ANDROID

    private Stream CreateAndroidDownloadStream(string projectName, string relativeFilePath)
    {
        string normalizedPath = relativeFilePath.Replace('\\', '/');

        string fileName = Path.GetFileName(normalizedPath);

        string? relativeDirectory = Path.GetDirectoryName(normalizedPath)?.Replace('\\', '/');

        string downloadDirectory = $"{Android.OS.Environment.DirectoryDownloads}/BEHOLDER/{projectName}/";

        if (!string.IsNullOrWhiteSpace(relativeDirectory))
        {
            downloadDirectory += $"{relativeDirectory.Trim('/')}/";
        }

        ContentValues values = new();

        values.Put(MediaStore.IMediaColumns.DisplayName, fileName);
        values.Put(MediaStore.IMediaColumns.RelativePath, downloadDirectory);
        values.Put(MediaStore.IMediaColumns.MimeType, GetMimeType(fileName));
        
        ContentResolver resolver = Android.App.Application.Context.ContentResolver;

        Android.Net.Uri? uri = resolver.Insert(MediaStore.Downloads.ExternalContentUri, values);

        if (uri == null)
        {
            throw new IOException($"Unable to create '{fileName}' in '{downloadDirectory}'.");
        }
        Stream? stream = resolver.OpenOutputStream(uri, "w");

        if (stream == null)
        {
            throw new IOException($"Unable to open '{fileName}' for writing.");
        }

        return stream;
    }

    private string GetMimeType(string fileName)
    {
        string extension = Path.GetExtension(fileName).ToLowerInvariant();
        return extension switch
        {
            ".jpg" or ".jpeg" => "image/jpeg",
            ".png" => "image/png",
            ".json" => "application/json",
            ".txt" => "text/plain",
            _ => "application/octet-stream"
        };
    }
#endif
    }
}