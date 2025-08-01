using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Core wheel strategy monitoring interface
/// </summary>
public interface IWheelMonitor
{
    /// <summary>
    /// Gets current portfolio metrics
    /// </summary>
    Task<PortfolioMetrics> GetPortfolioMetricsAsync();
    
    /// <summary>
    /// Gets all wheel positions
    /// </summary>
    Task<List<WheelPosition>> GetWheelPositionsAsync();
    
    /// <summary>
    /// Checks if a position meets entry criteria
    /// </summary>
    Task<bool> CheckEntryCriteriaAsync(string symbol, decimal strike);
    
    /// <summary>
    /// Gets IV metrics for a symbol
    /// </summary>
    Task<(decimal IVRank, decimal CurrentIV)> GetIVMetricsAsync(string symbol);
    
    /// <summary>
    /// Checks if position should be rolled
    /// </summary>
    Task<bool> ShouldRollPositionAsync(string symbol, decimal strike, int daysToExpiration);
    
    /// <summary>
    /// Gets market regime (BULL, BEAR, NEUTRAL)
    /// </summary>
    Task<string> GetMarketRegimeAsync();
    
    /// <summary>
    /// Gets VIX percentile
    /// </summary>
    Task<decimal> GetVIXPercentileAsync();
    
    /// <summary>
    /// Gets sector allocations
    /// </summary>
    Task<Dictionary<string, decimal>> GetSectorAllocationsAsync();
    
    /// <summary>
    /// Records a trade result
    /// </summary>
    Task RecordTradeResultAsync(Dictionary<string, object> tradeResult);
    
    /// <summary>
    /// Gets recent trades
    /// </summary>
    Task<List<Dictionary<string, object>>> GetRecentTradesAsync(int count);
} 