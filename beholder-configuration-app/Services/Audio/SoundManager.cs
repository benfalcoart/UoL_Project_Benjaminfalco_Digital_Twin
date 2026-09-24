using Microsoft.Maui.Storage;
using Plugin.Maui.Audio;

namespace beholder_configuration_app.Services.Audio
{
    public class SoundManager
    {
        private readonly IAudioManager _audioManager;

        private readonly Dictionary<SoundEffect, string> _soundFiles = new()
        {
            { SoundEffect.Error, "Sounds/error.wav" },
            { SoundEffect.Success, "Sounds/success.wav" },
            { SoundEffect.Warning, "Sounds/warning.wav"},
            { SoundEffect.Click, "Sounds/click.wav" },
            { SoundEffect.Camera_Click_On, "Sounds/camera_click_on.wav" },
            { SoundEffect.Camera_Click_Off, "Sounds/camera_click_off.wav" }
        };

        private readonly Dictionary<SoundEffect, IAudioPlayer> _players = new();

        public SoundManager(IAudioManager audioManager)
        {
            _audioManager = audioManager;
        }

        public async Task PlayAsync(SoundEffect sound)
        {
            bool soundEnabled = Preferences.Default.Get("CaptureSound", false);

            if (!soundEnabled)
            {
                return;
            }

            if (!_players.TryGetValue(sound, out IAudioPlayer? player))
            {
                if (!_soundFiles.TryGetValue(sound, out string? fileName))
                {
                    return;
                }

                Stream stream = await FileSystem.OpenAppPackageFileAsync(fileName);

                player = _audioManager.CreatePlayer(stream);

                _players[sound] = player;
            }

            if (player.IsPlaying)
            {
                player.Stop();
            }
            player.Play();
        }
    }
}