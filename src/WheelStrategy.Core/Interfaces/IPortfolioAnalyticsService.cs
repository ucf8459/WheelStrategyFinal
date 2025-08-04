using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Service for portfolio analytics and performance tracking
/// </summary>
public interface IPortfolioAnalyticsService
{
    /// <summary>
    /// Gets the complete portfolio analytics summary
    /// </summary>
    Task<PortfolioAnalyticsSummary> GetPortfolioAnalyticsAsync();
    
    /// <summary>
    /// Gets portfolio performance history with SPY benchmark
    /// </summary>
    Task<List<PortfolioPerformancePoint>> GetPerformanceHistoryAsync(DateTime? startDate = null, DateTime? endDate = null);
    
    /// <summary>
    /// Gets realized P&L data
    /// </summary>
    Task<List<RealizedPnL>> GetRealizedPnLAsync(DateTime? startDate = null, DateTime? endDate = null);
    
    /// <summary>
    /// Records a realized P&L trade
    /// </summary>
    Task RecordRealizedPnLAsync(RealizedPnL trade);
    
    /// <summary>
    /// Gets drawdown analysis
    /// </summary>
    Task<List<DrawdownPeriod>> GetDrawdownAnalysisAsync();
    
    /// <summary>
    /// Gets performance attribution by strategy
    /// </summary>
    Task<List<StrategyPerformance>> GetStrategyPerformanceAsync();
    
    /// <summary>
    /// Gets monthly P&L breakdown
    /// </summary>
    Task<Dictionary<string, decimal>> GetMonthlyPnLAsync(int year);
    
    /// <summary>
    /// Gets quarterly P&L breakdown
    /// </summary>
    Task<Dictionary<string, decimal>> GetQuarterlyPnLAsync(int year);
    
    /// <summary>
    /// Gets yearly P&L breakdown
    /// </summary>
    Task<Dictionary<string, decimal>> GetYearlyPnLAsync();
    
    /// <summary>
    /// Calculates rolling returns
    /// </summary>
    Task<Dictionary<string, decimal>> GetRollingReturnsAsync();
} 