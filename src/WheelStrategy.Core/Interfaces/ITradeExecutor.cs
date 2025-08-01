using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Trade execution interface
/// </summary>
public interface ITradeExecutor
{
    /// <summary>
    /// Sells a cash-secured put
    /// </summary>
    Task<Dictionary<string, object>?> SellPutAsync(string symbol, decimal strike, string expiry, decimal premium);
    
    /// <summary>
    /// Sells a covered call
    /// </summary>
    Task<Dictionary<string, object>?> SellCoveredCallAsync(string symbol, int shares, decimal strike, string expiry, decimal premium);
    
    /// <summary>
    /// Rolls a position to new strike/expiry
    /// </summary>
    Task<Dictionary<string, object>?> RollPositionAsync(string symbol, decimal oldStrike, string oldExpiry, decimal newStrike, string newExpiry);
    
    /// <summary>
    /// Closes a position
    /// </summary>
    Task<Dictionary<string, object>> ClosePositionAsync(string symbol, decimal strike, string expiry, string reason = "Manual close");
    
    /// <summary>
    /// Checks if current time is optimal for trading
    /// </summary>
    Task<bool> IsOptimalTradeTimeAsync();
    
    /// <summary>
    /// Gets execution quality metrics
    /// </summary>
    Task<Dictionary<string, object>> GetExecutionQualityAsync();
} 