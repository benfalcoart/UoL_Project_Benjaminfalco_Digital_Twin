using beholder_configuration_app.Models;
using beholder_configuration_app.Services.Audio;
using beholder_configuration_app.Services.Logging;
using beholder_configuration_app.Services.WebServices;
using Microsoft.Maui.Controls.Shapes;
using System.Text.Json;

namespace beholder_configuration_app;

public partial class ProjectsPage : ContentPage
{
    private readonly BeholderAPIService _apiService;
    private readonly BeholderWebSocketService _webSocketService;
    private readonly AppLogService _logService;
    private readonly SoundManager _soundManager;

    private BeholderStatus? _status;
    public ProjectsPage(BeholderAPIService apiService, BeholderWebSocketService webSocketService, AppLogService logService, SoundManager soundManager)
    {
        InitializeComponent();

        _apiService = apiService;
        _webSocketService = webSocketService;
        _logService = logService;
        _soundManager = soundManager;

        _webSocketService.MessageReceived += OnMessageReceived;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();

        await LoadProjectsAsync();
    }

    private void UpdateCurrentProject()
    {
        if (_status?.Project == null)
        {
            CurrentProjectNameLabel.Text = "No project selected";
            CurrentProjectCaptureLabel.Text = "No active capture";
            CurrentProjectStatsLabel.Text = "— images · — GB";
            return;
        }

        CurrentProjectNameLabel.Text = _status.Project.Name;
        CurrentProjectCaptureLabel.Text = $"Last capture #{_status.Project.LastCaptureId}";
    }

    private async void OnNewProjectClicked(object sender, EventArgs e)
    {
        string? projectName = await DisplayPromptAsync("New Project", "Enter a project name:", "CREATE", "CANCEL");

        if (string.IsNullOrWhiteSpace(projectName))
        {
            return;
        }

        try
        {
            HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.ProjectCreate,
                new
                {
                    name = projectName.Trim()
                });

            if (response.IsSuccessStatusCode)
            {
                _logService.Info($"Created project '{projectName}'.");

                await LoadProjectsAsync();
            }
            else
            {
                _logService.Warning($"Unable to create project '{projectName}'. HTTP {(int)response.StatusCode}");
            }
        }
        catch (Exception exception)
        {
            _logService.Error(exception);
        }
    }
    private async Task LoadProjectsAsync()
    {
        try
        {
            HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.ProjectGetAll);

            if (!response.IsSuccessStatusCode)
            {
                _logService.Warning($"Unable to load projects. HTTP {(int)response.StatusCode}");
                return;
            }

            string json = await response.Content.ReadAsStringAsync();

            List<ProjectInfo>? projects = JsonSerializer.Deserialize<List<ProjectInfo>>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

            UpdateProjectList(projects ?? new List<ProjectInfo>());
        }
        catch (Exception exception)
        {
            _logService.Error(exception);
        }
    }
    private void UpdateProjectList(List<ProjectInfo> projects)
    {
        ProjectList.Clear();

        ProjectCountLabel.Text = projects.Count == 1 ? "1 PROJECT" : $"{projects.Count} PROJECTS";

        foreach (ProjectInfo project in projects)
        {
            Label nameLabel = new()
            {
                Text = project.Name,
                FontSize = 18,
                FontAttributes = FontAttributes.Bold,
                TextColor = Colors.White
            };

            Label statsLabel = new()
            {
                Text = $"{project.ImageCount} images · {project.SizeGb:F2} GB",
                TextColor = Color.FromArgb("#C9D1D9")
            };

            Label captureLabel = new()
            {
                Text = $"Last capture #{project.LastCaptureId}",
                FontSize = 12,
                TextColor = Color.FromArgb("#8B949E")
            };

            VerticalStackLayout info = new()
            {
                Spacing = 4,
                Children =
                {
                    nameLabel,
                    statsLabel,
                    captureLabel
                }
            };

            Button openButton = new()
            {
                Text = "OPEN",
                BackgroundColor = Color.FromArgb("#22252B"),
                TextColor = Color.FromArgb("#3AA0FF"),
                CornerRadius = 8,
                VerticalOptions = LayoutOptions.Center
            };

            //discarding the arguments to make this compile:
            openButton.Clicked += async (_,_) =>
            {
                await OpenProjectAsync(project.Name);
            };

            Grid grid = new()
            {
                ColumnDefinitions =
               {
                    new ColumnDefinition(GridLength.Star),
                    new ColumnDefinition(GridLength.Auto)
                }
            };

            grid.Add(info, 0);
            grid.Add(openButton, 1);

            Border card = new()
            {
                BackgroundColor = Color.FromArgb("#191919"),
                Stroke = Color.FromArgb("#444444"),
                StrokeThickness = 1,
                Padding = 16,
                StrokeShape = new RoundRectangle
                {
                    CornerRadius = 8
                },
                Content = grid
            };

            ProjectList.Add(card);
        }
    }

    private async Task OpenProjectAsync(string projectName)
    {
        try
        {
            HttpResponseMessage response = await _apiService.SendAsync(APIEndpoint.ProjectOpen, body: new
            {
                projectName
            });

            if (response.IsSuccessStatusCode)
            {
                _ = _soundManager.PlayAsync(SoundEffect.Success);
                _logService.Info($"Opened project '{projectName}'.");
            }
            else
            {
                _logService.Warning($"Unable to open project '{projectName}'. HTTP {(int)response.StatusCode}");
            }
        }
        catch (Exception exception)
        {
            _logService.Error(exception);
        }
    }

    private void OnMessageReceived(string message)
    {
        MainThread.BeginInvokeOnMainThread(() =>
        {
            try
            {
                _status = JsonSerializer.Deserialize<BeholderStatus>(message);
                UpdateCurrentProject();
            }
            catch (Exception exception)
            {
                _logService.Error(exception);
            }
        });
    }
}