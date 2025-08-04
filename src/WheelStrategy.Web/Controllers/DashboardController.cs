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
    private readonly IDecisionSupportService _decisionSupportService;
    private readonly IPortfolioAnalyticsService _portfolioAnalyticsService;
    
    public DashboardController(
        ILogger<DashboardController> logger,
        IWheelMonitor wheelMonitor,
        IWheelScanner wheelScanner,
        IAlertManager alertManager,
        IDecisionSupportService decisionSupportService,
        IPortfolioAnalyticsService portfolioAnalyticsService)
    {
        _logger = logger;
        _wheelMonitor = wheelMonitor;
        _wheelScanner = wheelScanner;
        _alertManager = alertManager;
        _decisionSupportService = decisionSupportService;
        _portfolioAnalyticsService = portfolioAnalyticsService;
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
    
    /// <summary>
    /// Gets decision support summary
    /// </summary>
    [HttpGet("decision-support")]
    public async Task<ActionResult<DecisionSupportSummary>> GetDecisionSupport()
    {
        try
        {
            var summary = await _decisionSupportService.GetDecisionSupportSummaryAsync();
            return Ok(summary);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get decision support summary");
            return StatusCode(500, "Failed to get decision support summary");
        }
    }
    
    /// <summary>
    /// Records a decision made today
    /// </summary>
    [HttpPost("record-decision")]
    public async Task<ActionResult> RecordDecision([FromBody] RecordDecisionRequest request)
    {
        try
        {
            await _decisionSupportService.RecordDecisionAsync(request.Decision, request.Category);
            return Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to record decision");
            return StatusCode(500, "Failed to record decision");
        }
    }
    
    /// <summary>
    /// Gets upcoming expirations within 7 days
    /// </summary>
    [HttpGet("upcoming-expirations")]
    public async Task<ActionResult<List<UpcomingExpiration>>> GetUpcomingExpirations()
    {
        try
        {
            var expirations = await _decisionSupportService.GetUpcomingExpirationsAsync();
            return Ok(expirations);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get upcoming expirations");
            return StatusCode(500, "Failed to get upcoming expirations");
        }
    }
    
    /// <summary>
    /// Gets decisions used today
    /// </summary>
    [HttpGet("decisions-used-today")]
    public async Task<ActionResult<int>> GetDecisionsUsedToday()
    {
        try
        {
            var count = await _decisionSupportService.GetDecisionsUsedTodayAsync();
            return Ok(count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get decisions used today");
            return StatusCode(500, "Failed to get decisions used today");
        }
    }
    
    /// <summary>
    /// Gets portfolio analytics summary
    /// </summary>
    [HttpGet("portfolio-analytics")]
    public async Task<ActionResult<PortfolioAnalyticsSummary>> GetPortfolioAnalytics()
    {
        try
        {
            var analytics = await _portfolioAnalyticsService.GetPortfolioAnalyticsAsync();
            return Ok(analytics);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get portfolio analytics");
            return StatusCode(500, "Failed to get portfolio analytics");
        }
    }
    
    /// <summary>
    /// Gets portfolio performance history
    /// </summary>
    [HttpGet("performance-history")]
    public async Task<ActionResult<List<PortfolioPerformancePoint>>> GetPerformanceHistory([FromQuery] DateTime? startDate, [FromQuery] DateTime? endDate)
    {
        try
        {
            var history = await _portfolioAnalyticsService.GetPerformanceHistoryAsync(startDate, endDate);
            return Ok(history);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get performance history");
            return StatusCode(500, "Failed to get performance history");
        }
    }
    
    /// <summary>
    /// Gets realized P&L data
    /// </summary>
    [HttpGet("realized-pnl")]
    public async Task<ActionResult<List<RealizedPnL>>> GetRealizedPnL([FromQuery] DateTime? startDate, [FromQuery] DateTime? endDate)
    {
        try
        {
            var realizedPnL = await _portfolioAnalyticsService.GetRealizedPnLAsync(startDate, endDate);
            return Ok(realizedPnL);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get realized P&L");
            return StatusCode(500, "Failed to get realized P&L");
        }
    }
    
    /// <summary>
    /// Records a realized P&L trade
    /// </summary>
    [HttpPost("record-realized-pnl")]
    public async Task<ActionResult> RecordRealizedPnL([FromBody] RecordRealizedPnLRequest request)
    {
        try
        {
            var trade = new RealizedPnL
            {
                Date = DateTime.UtcNow,
                Symbol = request.Symbol,
                PositionType = request.PositionType,
                Strike = request.Strike,
                Expiry = request.Expiry,
                EntryPrice = request.EntryPrice,
                ExitPrice = request.ExitPrice,
                Quantity = request.Quantity,
                RealizedPnLAmount = (request.ExitPrice - request.EntryPrice) * request.Quantity,
                RealizedPnLPercent = ((request.ExitPrice - request.EntryPrice) / request.EntryPrice) * 100,
                CloseReason = request.CloseReason,
                HoldDuration = request.HoldDuration,
                MaxProfit = request.MaxProfit,
                MaxLoss = request.MaxLoss
            };
            
            await _portfolioAnalyticsService.RecordRealizedPnLAsync(trade);
            return Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to record realized P&L");
            return StatusCode(500, "Failed to record realized P&L");
        }
    }
    
    /// <summary>
    /// Gets drawdown analysis
    /// </summary>
    [HttpGet("drawdown-analysis")]
    public async Task<ActionResult<List<DrawdownPeriod>>> GetDrawdownAnalysis()
    {
        try
        {
            var drawdowns = await _portfolioAnalyticsService.GetDrawdownAnalysisAsync();
            return Ok(drawdowns);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get drawdown analysis");
            return StatusCode(500, "Failed to get drawdown analysis");
        }
    }
    
    /// <summary>
    /// Gets strategy performance
    /// </summary>
    [HttpGet("strategy-performance")]
    public async Task<ActionResult<List<StrategyPerformance>>> GetStrategyPerformance()
    {
        try
        {
            var strategies = await _portfolioAnalyticsService.GetStrategyPerformanceAsync();
            return Ok(strategies);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get strategy performance");
            return StatusCode(500, "Failed to get strategy performance");
        }
    }
    
    /// <summary>
    /// Gets monthly P&L breakdown
    /// </summary>
    [HttpGet("monthly-pnl/{year}")]
    public async Task<ActionResult<Dictionary<string, decimal>>> GetMonthlyPnL(int year)
    {
        try
        {
            var monthlyPnL = await _portfolioAnalyticsService.GetMonthlyPnLAsync(year);
            return Ok(monthlyPnL);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get monthly P&L");
            return StatusCode(500, "Failed to get monthly P&L");
        }
    }
    
    /// <summary>
    /// Gets quarterly P&L breakdown
    /// </summary>
    [HttpGet("quarterly-pnl/{year}")]
    public async Task<ActionResult<Dictionary<string, decimal>>> GetQuarterlyPnL(int year)
    {
        try
        {
            var quarterlyPnL = await _portfolioAnalyticsService.GetQuarterlyPnLAsync(year);
            return Ok(quarterlyPnL);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get quarterly P&L");
            return StatusCode(500, "Failed to get quarterly P&L");
        }
    }
    
    /// <summary>
    /// Gets yearly P&L breakdown
    /// </summary>
    [HttpGet("yearly-pnl")]
    public async Task<ActionResult<Dictionary<string, decimal>>> GetYearlyPnL()
    {
        try
        {
            var yearlyPnL = await _portfolioAnalyticsService.GetYearlyPnLAsync();
            return Ok(yearlyPnL);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get yearly P&L");
            return StatusCode(500, "Failed to get yearly P&L");
        }
    }
    
    /// <summary>
    /// Gets rolling returns
    /// </summary>
    [HttpGet("rolling-returns")]
    public async Task<ActionResult<Dictionary<string, decimal>>> GetRollingReturns()
    {
        try
        {
            var rollingReturns = await _portfolioAnalyticsService.GetRollingReturnsAsync();
            return Ok(rollingReturns);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get rolling returns");
            return StatusCode(500, "Failed to get rolling returns");
        }
    }
}

/// <summary>
/// Request model for recording a decision
/// </summary>
public class RecordDecisionRequest
{
    public string Decision { get; set; } = string.Empty;
    public string Category { get; set; } = string.Empty;
}

/// <summary>
/// Request model for recording realized P&L
/// </summary>
public class RecordRealizedPnLRequest
{
    public string Symbol { get; set; } = string.Empty;
    public string PositionType { get; set; } = string.Empty;
    public decimal Strike { get; set; }
    public DateTime Expiry { get; set; }
    public decimal EntryPrice { get; set; }
    public decimal ExitPrice { get; set; }
    public decimal Quantity { get; set; }
    public string CloseReason { get; set; } = string.Empty;
    public TimeSpan HoldDuration { get; set; }
    public decimal MaxProfit { get; set; }
    public decimal MaxLoss { get; set; }
} 