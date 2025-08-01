using Microsoft.AspNetCore.SignalR;
using Microsoft.Extensions.Logging;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;

namespace WheelStrategy.Web.Hubs;

/// <summary>
/// SignalR hub for real-time dashboard updates
/// </summary>
public class DashboardHub : Hub
{
    private readonly ILogger<DashboardHub> _logger;
    private readonly IWheelMonitor _wheelMonitor;
    private readonly IWheelScanner _wheelScanner;
    
    public DashboardHub(
        ILogger<DashboardHub> logger,
        IWheelMonitor wheelMonitor,
        IWheelScanner wheelScanner)
    {
        _logger = logger;
        _wheelMonitor = wheelMonitor;
        _wheelScanner = wheelScanner;
    }
    
    public override async Task OnConnectedAsync()
    {
        _logger.LogInformation("Client connected: {ConnectionId}", Context.ConnectionId);
        await base.OnConnectedAsync();
    }
    
    public override async Task OnDisconnectedAsync(Exception? exception)
    {
        _logger.LogInformation("Client disconnected: {ConnectionId}", Context.ConnectionId);
        await base.OnDisconnectedAsync(exception);
    }
    
    /// <summary>
    /// Sends portfolio metrics to all connected clients
    /// </summary>
    public async Task SendPortfolioMetricsAsync()
    {
        try
        {
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            await Clients.All.SendAsync("ReceivePortfolioMetrics", metrics);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send portfolio metrics");
        }
    }
    
    /// <summary>
    /// Sends wheel positions to all connected clients
    /// </summary>
    public async Task SendWheelPositionsAsync()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            await Clients.All.SendAsync("ReceiveWheelPositions", positions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send wheel positions");
        }
    }
    
    /// <summary>
    /// Sends opportunities to all connected clients
    /// </summary>
    public async Task SendOpportunitiesAsync()
    {
        try
        {
            var opportunities = await _wheelScanner.ScanOpportunitiesAsync();
            await Clients.All.SendAsync("ReceiveOpportunities", opportunities);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send opportunities");
        }
    }
    
    /// <summary>
    /// Sends alerts to all connected clients
    /// </summary>
    public async Task SendAlertAsync(Alert alert)
    {
        try
        {
            await Clients.All.SendAsync("ReceiveAlert", alert);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send alert");
        }
    }
} 