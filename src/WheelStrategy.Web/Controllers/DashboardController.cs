using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;

namespace WheelStrategy.Web.Controllers;

/// <summary>
/// Dashboard API controller
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class DashboardController : ControllerBase
{
    private readonly ILogger<DashboardController> _logger;
    private readonly IWheelMonitor _wheelMonitor;
    private readonly IWheelScanner _wheelScanner;
    private readonly IAlertManager _alertManager;
    
    public DashboardController(
        ILogger<DashboardController> logger,
        IWheelMonitor wheelMonitor,
        IWheelScanner wheelScanner,
        IAlertManager alertManager)
    {
        _logger = logger;
        _wheelMonitor = wheelMonitor;
        _wheelScanner = wheelScanner;
        _alertManager = alertManager;
    }
    
    /// <summary>
    /// Gets portfolio metrics
    /// </summary>
    [HttpGet("metrics")]
    public async Task<ActionResult<PortfolioMetrics>> GetMetrics()
    {
        try
        {
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            return Ok(metrics);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get portfolio metrics");
            return StatusCode(500, "Failed to get portfolio metrics");
        }
    }
    
    /// <summary>
    /// Gets wheel positions
    /// </summary>
    [HttpGet("positions")]
    public async Task<ActionResult<List<WheelPosition>>> GetPositions()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            return Ok(positions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get wheel positions");
            return StatusCode(500, "Failed to get wheel positions");
        }
    }
    
    /// <summary>
    /// Gets opportunities
    /// </summary>
    [HttpGet("opportunities")]
    public async Task<ActionResult<List<OptionOpportunity>>> GetOpportunities()
    {
        try
        {
            var opportunities = await _wheelScanner.ScanOpportunitiesAsync();
            return Ok(opportunities);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get opportunities");
            return StatusCode(500, "Failed to get opportunities");
        }
    }
    
    /// <summary>
    /// Gets recent alerts
    /// </summary>
    [HttpGet("alerts")]
    public async Task<ActionResult<List<Alert>>> GetAlerts([FromQuery] int count = 50)
    {
        try
        {
            var alerts = await _alertManager.GetRecentAlertsAsync(count);
            return Ok(alerts);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get alerts");
            return StatusCode(500, "Failed to get alerts");
        }
    }
    
    /// <summary>
    /// Gets recent trades
    /// </summary>
    [HttpGet("trades")]
    public async Task<ActionResult<List<Dictionary<string, object>>>> GetTrades([FromQuery] int count = 20)
    {
        try
        {
            var trades = await _wheelMonitor.GetRecentTradesAsync(count);
            return Ok(trades);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get trades");
            return StatusCode(500, "Failed to get trades");
        }
    }
    
    /// <summary>
    /// Gets market regime
    /// </summary>
    [HttpGet("market-regime")]
    public async Task<ActionResult<string>> GetMarketRegime()
    {
        try
        {
            var regime = await _wheelMonitor.GetMarketRegimeAsync();
            return Ok(regime);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get market regime");
            return StatusCode(500, "Failed to get market regime");
        }
    }
    
    /// <summary>
    /// Gets VIX percentile
    /// </summary>
    [HttpGet("vix-percentile")]
    public async Task<ActionResult<decimal>> GetVIXPercentile()
    {
        try
        {
            var percentile = await _wheelMonitor.GetVIXPercentileAsync();
            return Ok(percentile);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get VIX percentile");
            return StatusCode(500, "Failed to get VIX percentile");
        }
    }
    
    /// <summary>
    /// Gets sector allocations
    /// </summary>
    [HttpGet("sector-allocations")]
    public async Task<ActionResult<Dictionary<string, decimal>>> GetSectorAllocations()
    {
        try
        {
            var allocations = await _wheelMonitor.GetSectorAllocationsAsync();
            return Ok(allocations);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get sector allocations");
            return StatusCode(500, "Failed to get sector allocations");
        }
    }
} 