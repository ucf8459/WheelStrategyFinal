using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using AutoFinance.Broker.InteractiveBrokers.Controllers;
using AutoFinance.Broker.InteractiveBrokers;

namespace WheelStrategy.IBKR.Services;

/// <summary>
/// IBKR Connection Service using AutoFinance.Broker
/// </summary>
public class IBKRConnectionService : IDisposable
{
    private readonly ILogger<IBKRConnectionService> _logger;
    private readonly WheelStrategyOptions _options;
    private ITwsController? _twsController;
    private TwsObjectFactory? _twsObjectFactory;
    private bool _isConnected = false;
    private readonly object _lockObject = new object();
    private int _nextRequestId = 1;

    public IBKRConnectionService(
        ILogger<IBKRConnectionService> logger,
        IOptions<WheelStrategyOptions> options)
    {
        _logger = logger;
        _options = options.Value;
    }

    /// <summary>
    /// Connects to IBKR using AutoFinance.Broker
    /// </summary>
    public async Task<bool> ConnectAsync()
    {
        if (_isConnected) return true;

        lock (_lockObject)
        {
            if (_isConnected) return true;
        }

        try
        {
            _logger.LogInformation("Connecting to IBKR using AutoFinance.Broker at {Host}:{Port}", _options.IBKR.Host, _options.IBKR.Port);

            // Create TWS object factory and controller
            _twsObjectFactory = new TwsObjectFactory(_options.IBKR.Host, _options.IBKR.Port, _options.IBKR.ClientId);
            _twsController = _twsObjectFactory.TwsController;
            
            // Connect to IBKR
            await _twsController.EnsureConnectedAsync();
            
            if (_twsController.Connected)
            {
                lock (_lockObject)
                {
                    _isConnected = true;
                }
                _logger.LogInformation("Successfully connected to IBKR using AutoFinance.Broker");
                return true;
            }
            else
            {
                _logger.LogError("Failed to connect to IBKR - TWS controller not connected");
                return false;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to connect to IBKR using AutoFinance.Broker");
            return false;
        }
    }

    /// <summary>
    /// Gets the TWS controller for API calls
    /// </summary>
    public ITwsController? GetTwsController()
    {
        return _isConnected ? _twsController : null;
    }

    /// <summary>
    /// Gets the next request ID
    /// </summary>
    public int GetNextRequestId()
    {
        return Interlocked.Increment(ref _nextRequestId);
    }

    /// <summary>
    /// Checks if connected to IBKR
    /// </summary>
    public bool IsConnected => _isConnected;

    /// <summary>
    /// Disconnects from IBKR
    /// </summary>
    public void Disconnect()
    {
        lock (_lockObject)
        {
            if (_twsController != null && _twsController.Connected)
            {
                _twsController.DisconnectAsync();
            }
            _isConnected = false;
            _twsController = null;
            _twsObjectFactory = null;
        }
        _logger.LogInformation("Disconnected from IBKR");
    }

    /// <summary>
    /// Disposes the connection
    /// </summary>
    public void Dispose()
    {
        Disconnect();
    }
} 