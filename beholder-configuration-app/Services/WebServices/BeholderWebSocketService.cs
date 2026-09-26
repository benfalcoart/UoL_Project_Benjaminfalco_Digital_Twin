using beholder_configuration_app.Services.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.WebSockets;
using System.Text;
using System.Threading.Tasks;


namespace beholder_configuration_app.Services.WebServices
{
    public class BeholderWebSocketService
    {
        private ClientWebSocket? _socket;
        private CancellationTokenSource? _cancellationTokenSource;

        private bool _intentionalDisconnect = false;
        private bool _reconnecting = false;

        public event Action<string>? MessageReceived;
        public event Action<bool>? ConnectionChanged;

        public bool IsConnected => _socket?.State == WebSocketState.Open;

        private readonly AppLogService _logService;
        private readonly BeholderConnectionSettings _connectionSettings;


        //private string _wsConnectionUri = "ws://192.168.0.130:8000/ws";
        public BeholderWebSocketService(AppLogService logService, BeholderConnectionSettings connectionSettings)
        {
            _logService = logService;
            _connectionSettings = connectionSettings;
        }
        public async Task ConnectAsync()
        {
            if (IsConnected)
            {
                return;
            }

            _intentionalDisconnect = false;
            await ConnectInternalAsync();
        }
        private async Task ConnectInternalAsync()
        {
            _socket?.Dispose();

            _socket = new ClientWebSocket();
            _socket.Options.KeepAliveInterval = TimeSpan.FromSeconds(15);
            _socket.Options.KeepAliveTimeout = TimeSpan.FromSeconds(30);

            _cancellationTokenSource = new CancellationTokenSource();

            string uri = _connectionSettings.WebSocketAddress;

            await _socket.ConnectAsync(new Uri(uri), _cancellationTokenSource.Token);

            ConnectionChanged?.Invoke(true);

            _ = ReceiveLoopAsync(_cancellationTokenSource.Token);
            _ = HeartbeatLoopAsync(_cancellationTokenSource.Token);
        }

        private async Task ReceiveLoopAsync(CancellationToken cancellationToken)
        {
            byte[] buffer = new byte[8192];

            try
            {
                while (_socket != null && _socket.State == WebSocketState.Open && !cancellationToken.IsCancellationRequested)
                {
                    using MemoryStream messageStream = new();

                    WebSocketReceiveResult result;

                    do
                    {
                        result = await _socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancellationToken);

                        if (result.MessageType == WebSocketMessageType.Close)
                        {
                            return;
                        }

                        messageStream.Write(buffer, 0, result.Count);

                    } while (!result.EndOfMessage);

                    string message = Encoding.UTF8.GetString(messageStream.ToArray());
                    MessageReceived?.Invoke(message);
                }
            }
            catch (OperationCanceledException)
            {
            }
            catch (WebSocketException exception)
            {
                _logService.Error(exception);
            }
            finally
            {
                ConnectionChanged?.Invoke(false);

                if (!_intentionalDisconnect && !cancellationToken.IsCancellationRequested)
                {
                    _ = ReconnectAsync();
                }
            }
        }

        private async Task HeartbeatLoopAsync(CancellationToken cancellationToken)
        {
            try
            {
                while (!cancellationToken.IsCancellationRequested)
                {
                    await Task.Delay(TimeSpan.FromSeconds(10), cancellationToken);

                    if (_socket?.State != WebSocketState.Open)
                    {
                        return;
                    }

                    byte[] heartbeat = Encoding.UTF8.GetBytes("heartbeat");

                    await _socket.SendAsync(
                        new ArraySegment<byte>(heartbeat),
                        WebSocketMessageType.Text,
                        true,
                        cancellationToken);
                }
            }
            catch (OperationCanceledException)
            {
            }
            catch (WebSocketException exception)
            {
                _logService.Error(exception);
                _socket?.Abort();
            }
        }

        private async Task ReconnectAsync()
        {
            if (_reconnecting || _intentionalDisconnect)
            {
                return;
            }

            _reconnecting = true;

            try
            {
                while (!_intentionalDisconnect && !IsConnected)
                {
                    _logService.Warning("WebSocket disconnected. Reconnecting...");

                    await Task.Delay(2000);

                    try
                    {
                        await ConnectInternalAsync();
                        _logService.Info("WebSocket reconnected.");
                        return;
                    }
                    catch (Exception exception)
                    {
                        _logService.Warning($"WebSocket reconnect failed: {exception.Message}");
                    }
                }
            }
            finally
            {
                _reconnecting = false;
            }
        }

        public async Task DisconnectAsync()
        {
            _intentionalDisconnect = true;

            if (_socket == null)
            {
                return;
            }

            _cancellationTokenSource?.Cancel();

            if (_socket.State == WebSocketState.Open)
            {
                try
                {
                    await _socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Client Disconnected", CancellationToken.None);
                }
                catch
                {
                }
            }

            _socket.Dispose();
            _socket = null;

            ConnectionChanged?.Invoke(false);
        }

    }
}