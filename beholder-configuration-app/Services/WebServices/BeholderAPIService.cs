using beholder_configuration_app.Services.Logging;
using System;
using System.Collections.Generic;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading.Tasks;

namespace beholder_configuration_app.Services.WebServices
{
    public class BeholderAPIService
    {
        private readonly HttpClient _httpClient;
        private readonly AppLogService _logService;
        private readonly BeholderConnectionSettings _connectionSettings;

        private readonly Dictionary<APIEndpoint, APIEndpointDefinition> _endpoints = new();

        private bool _loaded;
               

        public BeholderAPIService(HttpClient httpClient, AppLogService logService, BeholderConnectionSettings connectionSettings)
        {
            _httpClient = httpClient;
            _logService = logService;
            _connectionSettings = connectionSettings;
        }

        //Load the Endpoints JSON file and parse it. Set up the Dictionary with all the API calls to make.
        public async Task LoadEndPointsAsync()
        {
            if (_loaded)
            {
                return;
            }

            using Stream stream = await FileSystem.OpenAppPackageFileAsync("APIEndPoints.json");

            using JsonDocument document = await JsonDocument.ParseAsync(stream);

            foreach (JsonProperty prop in document.RootElement.EnumerateObject())
            {
                if (!Enum.TryParse(prop.Name, true, out APIEndpoint endpoint))
                {
                    _logService.Warning($"Unknown API endpoint in APIEndpoints.json: {prop.Name}");
                    continue;
                }

                APIEndpointDefinition? definition = prop.Value.Deserialize<APIEndpointDefinition>(new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true,
                });

                if (definition != null)
                {
                    _endpoints[endpoint] = definition;
                }

            }
            //set the loaded flag so that we dont try again
            _loaded = true;
            _logService.Info($"Loaded {_endpoints.Count} API endpoints.");
        }

        //Option to Reload the API Endpoints should something be amiss?
        public async Task ReloadEndPointsAsync()
        {

            _endpoints.Clear();
            _loaded = false;
            await LoadEndPointsAsync();
        }

        private string GetUrl(APIEndpoint endpoint)
        {
            if (!_endpoints.TryGetValue(endpoint, out APIEndpointDefinition? definition))
            {
                throw new KeyNotFoundException($"API endpoint '{endpoint}' was not found.");
            }
            return $"http://{_connectionSettings.Address}:{_connectionSettings.Port}{definition.Path}";
        }

        public async Task<HttpResponseMessage> SendAsync(APIEndpoint endpoint, object? body = null, HttpCompletionOption completionOption = HttpCompletionOption.ResponseContentRead)
        {
            if (!_loaded)
            {
                await LoadEndPointsAsync();
            }

            if (!_endpoints.TryGetValue(endpoint, out APIEndpointDefinition? definition))
            {
                throw new KeyNotFoundException($"API endpoint '{endpoint}' was not found.");
            }

            string url = GetUrl(endpoint);
            HttpRequestMessage request = new(new HttpMethod(definition.Method), url);

            if (body != null)
            {
                request.Content = JsonContent.Create(body);
            }

            return await _httpClient.SendAsync(request, completionOption);
        }
    }
}
