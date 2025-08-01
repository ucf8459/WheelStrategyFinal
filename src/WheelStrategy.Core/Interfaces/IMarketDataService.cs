namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Market data service interface
/// </summary>
public interface IMarketDataService
{
    /// <summary>
    /// Gets account summary
    /// </summary>
    Task<Dictionary<string, object>> GetAccountSummaryAsync();

    /// <summary>
    /// Gets current positions
    /// </summary>
    Task<List<Dictionary<string, object>>> GetPositionsAsync();

    /// <summary>
    /// Gets option data including Greeks
    /// </summary>
    Task<Dictionary<string, object>> GetOptionDataAsync(string symbol, decimal strike, string expiry, string right);

    /// <summary>
    /// Gets stock price data
    /// </summary>
    Task<Dictionary<string, object>> GetStockDataAsync(string symbol);
} 