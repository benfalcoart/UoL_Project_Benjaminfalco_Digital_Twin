using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.WebSockets;
using System.Text;
using System.Threading.Tasks;

namespace beholder_configuration_app.Services;

public class BeholderWebSocketService
{
    private ClientWebSocket? _socket;
    private CancellationTokenSource? _cancellationTokenSource;

    public event Action<string>? MessageReceived;
    public event Action<bool>? ConnectionChanged;

    public bool IsConnected => _socket?.State == WebSocketState.Open;

    private string _wsConnectionUri = "ws://192.168.0.130:8000/ws";

    public async Task ConnectAsync()
    {
        if (IsConnected)
        {
            return;
        }

        _socket = new ClientWebSocket();
        _cancellationTokenSource = new CancellationTokenSource();

        await _socket.ConnectAsync(new Uri(_wsConnectionUri), _cancellationTokenSource.Token);

        ConnectionChanged?.Invoke(true);

        _ = ReceiveLoopAsync(_cancellationTokenSource.Token);
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
        catch (OperationCanceledException ocex)
        {
        }
        catch (WebSocketException wsex)
        {
        }
        finally
        {
            ConnectionChanged?.Invoke(false);
        }

    }

    public async Task DisconnectAsync()
    {
        if (_socket == null)
        {
            return;
        }

        _cancellationTokenSource?.Cancel();

        if (_socket.State == WebSocketState.Open)
        {
            await _socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Client Disconnected", CancellationToken.None);
        }

        _socket.Dispose();
        _socket = null;

        ConnectionChanged?.Invoke(false);
    }

}

