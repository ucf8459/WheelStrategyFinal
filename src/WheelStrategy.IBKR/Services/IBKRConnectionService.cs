using InteractiveBrokers;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;

namespace WheelStrategy.IBKR.Services;

/// <summary>
/// Manages IBKR TWS/Gateway connections
/// </summary>
public class IBKRConnectionService : IAsyncDisposable
{
    private readonly ILogger<IBKRConnectionService> _logger;
    private readonly IBKROptions _options;
    private readonly Dictionary<string, IB> _connections = new();
    private readonly object _lock = new();
    
    public IBKRConnectionService(
        IOptions<WheelStrategyOptions> options,
        ILogger<IBKRConnectionService> logger)
    {
        _options = options.Value.IBKR;
        _logger = logger;
    }
    
    /// <summary>
    /// Gets or creates a connection for a specific component
    /// </summary>
    public async Task<IB> GetConnectionAsync(string componentName)
    {
        lock (_lock)
        {
            if (_connections.TryGetValue(componentName, out var existingConnection))
            {
                if (existingConnection.IsConnected())
                {
                    return existingConnection;
                }
                else
                {
                    _connections.Remove(componentName);
                }
            }
        }
        
        var connection = await CreateConnectionAsync(componentName);
        
        lock (_lock)
        {
            _connections[componentName] = connection;
        }
        
        return connection;
    }
    
    /// <summary>
    /// Creates a new IBKR connection
    /// </summary>
    private async Task<IB> CreateConnectionAsync(string componentName)
    {
        var ib = new IB();
        var clientId = GetClientId(componentName);
        
        try
        {
            _logger.LogInformation("Connecting {Component} to IBKR at {Host}:{Port} with client ID {ClientId}", 
                componentName, _options.Host, _options.Port, clientId);
            
            await Task.Run(() =>
            {
                ib.Connect(_options.Host, _options.Port, clientId);
                ib.RequestMarketDataType(1); // Live data
            });
            
            _logger.LogInformation("Successfully connected {Component} to IBKR", componentName);
            return ib;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to connect {Component} to IBKR", componentName);
            throw;
        }
    }
    
    /// <summary>
    /// Gets a unique client ID for a component
    /// </summary>
    private int GetClientId(string componentName)
    {
        var baseClientId = componentName switch
        {
            "Monitor" => 10000,
            "Scanner" => 11000,
            "Executor" => 12000,
            _ => 13000
        };
        
        // Add a small random offset to avoid conflicts
        var random = new Random();
        return baseClientId + random.Next(0, 999);
    }
    
    /// <summary>
    /// Disconnects all connections
    /// </summary>
    public async Task DisconnectAllAsync()
    {
        var tasks = _connections.Values
            .Where(ib => ib.IsConnected())
            .Select(ib => Task.Run(() => ib.Disconnect()));
        
        await Task.WhenAll(tasks);
        
        lock (_lock)
        {
            _connections.Clear();
        }
        
        _logger.LogInformation("Disconnected all IBKR connections");
    }
    
    /// <summary>
    /// Gets connection status for all components
    /// </summary>
    public Dictionary<string, bool> GetConnectionStatus()
    {
        lock (_lock)
        {
            return _connections.ToDictionary(
                kvp => kvp.Key,
                kvp => kvp.Value.IsConnected());
        }
    }
    
    public async ValueTask DisposeAsync()
    {
        await DisconnectAllAsync();
    }
} 