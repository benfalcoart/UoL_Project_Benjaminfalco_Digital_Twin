using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace beholder_configuration_app.Services.WebServices
{
    public class BeholderAPIService
    {
        private readonly HttpClient _httpClient;

        private readonly Dictionary<APIEndpoint, APIEndpointDefinition> _endpoints = new();

        private bool _loaded;

        private string _address = "192.168.0.130"; //This needs to be set dynamically from the app input
        private int _port = 8000;

        public BeholderAPIService(HttpClient httpClient)
        {
            _httpClient = httpClient;
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
                    //TDOO: Maybe add a console or log to the app to look for errors like this?
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
        }

        //Option to Reload the API Endpoints should something be amiss?
        public async Task ReloadEndPointsAsync()
        {
            _loaded = false;
            await LoadEndPointsAsync();
        }
        public void SetConnection(string address, int port)
        {
            _address = address;
            _port = port;
        }

        private string GetUrl(APIEndpoint endpoint)
        {
            if (!_endpoints.TryGetValue(endpoint, out APIEndpointDefinition? definition))
            {
                throw new KeyNotFoundException($"API endpoint '{endpoint}' was not found.");
            }
            return $"http://{_address}:{_port}{definition.Path}";
        }

        public async Task<HttpResponseMessage> SendAsync(APIEndpoint endpoint, object? body = null)
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

            return await _httpClient.SendAsync(request);
        }
    }
}
