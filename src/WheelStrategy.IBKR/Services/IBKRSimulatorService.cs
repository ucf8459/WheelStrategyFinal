using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;

namespace WheelStrategy.IBKR.Services;

/// <summary>
/// IBKR Simulator Service - Provides SAMPLE DATA for testing when real IBKR is not available
/// All data is clearly labeled as SAMPLE for testing purposes
/// </summary>
public class IBKRSimulatorService : IMarketDataService
{
    private readonly ILogger<IBKRSimulatorService> _logger;
    private readonly WheelStrategyOptions _options;

    public IBKRSimulatorService(
        ILogger<IBKRSimulatorService> logger,
        IOptions<WheelStrategyOptions> options)
    {
        _logger = logger;
        _options = options.Value;
    }

    /// <summary>
    /// Gets SAMPLE account summary data for testing
    /// </summary>
    public async Task<Dictionary<string, object>> GetAccountSummaryAsync()
    {
        _logger.LogInformation("Getting SAMPLE account summary data for testing");
        
        // Simulate network delay
        await Task.Delay(100);
        
        var accountData = new Dictionary<string, object>
        {
            ["NetLiquidation"] = "125000.00",
            ["AvailableFunds"] = "35000.00",
            ["UnrealizedPnL"] = "2200.00",
            ["TotalCashValue"] = "35000.00",
            ["BuyingPower"] = "70000.00",
            ["AccountValue"] = 125000.00m,
            ["CashPercentage"] = 0.28m,
            ["IsSampleData"] = true,
            ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
        };
        
        return accountData;
    }

    /// <summary>
    /// Gets SAMPLE positions data for testing
    /// </summary>
    public async Task<List<Dictionary<string, object>>> GetPositionsAsync()
    {
        _logger.LogInformation("Getting SAMPLE positions data for testing");
        
        // Simulate network delay
        await Task.Delay(150);
        
        var positions = new List<Dictionary<string, object>>
        {
            new Dictionary<string, object>
            {
                ["symbol"] = "AAPL",
                ["secType"] = "OPT",
                ["position"] = -2,
                ["marketValue"] = -450.00,
                ["avgCost"] = 2.25,
                ["unrealizedPnL"] = 75.00,
                ["strike"] = 175.00,
                ["right"] = "P",
                ["expiry"] = "2024-12-20",
                ["dte"] = 45,
                ["estimatedDelta"] = -0.32,
                ["stockPrice"] = 178.50,
                ["totalCredits"] = 450.00,
                ["pnl"] = 16.7,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            },
            new Dictionary<string, object>
            {
                ["symbol"] = "MSFT",
                ["secType"] = "STK",
                ["position"] = 200,
                ["marketValue"] = 75000.00,
                ["avgCost"] = 350.00,
                ["unrealizedPnL"] = 5000.00,
                ["strike"] = null,
                ["right"] = null,
                ["expiry"] = null,
                ["dte"] = null,
                ["estimatedDelta"] = 1.0,
                ["stockPrice"] = 375.00,
                ["totalCredits"] = 0.00,
                ["pnl"] = 14.3,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            },
            new Dictionary<string, object>
            {
                ["symbol"] = "NVDA",
                ["secType"] = "OPT",
                ["position"] = -1,
                ["marketValue"] = -320.00,
                ["avgCost"] = 3.20,
                ["unrealizedPnL"] = -25.00,
                ["strike"] = 420.00,
                ["right"] = "P",
                ["expiry"] = "2024-11-15",
                ["dte"] = 12,
                ["estimatedDelta"] = -0.45,
                ["stockPrice"] = 415.00,
                ["totalCredits"] = 320.00,
                ["pnl"] = -7.8,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            }
        };
        
        return positions;
    }

    /// <summary>
    /// Gets SAMPLE option data for testing
    /// </summary>
    public async Task<Dictionary<string, object>> GetOptionDataAsync(string symbol, decimal strike, string expiry, string right)
    {
        _logger.LogInformation("Getting SAMPLE option data for {Symbol} {Strike} {Right} {Expiry}", symbol, strike, right, expiry);
        
        // Simulate network delay
        await Task.Delay(200);
        
        var optionData = new Dictionary<string, object>
        {
            ["symbol"] = symbol,
            ["strike"] = strike,
            ["expiry"] = expiry,
            ["right"] = right,
            ["delta"] = right == "P" ? -0.35 : 0.35,
            ["gamma"] = 0.02,
            ["vega"] = 0.15,
            ["theta"] = -0.08,
            ["bid"] = 2.50,
            ["ask"] = 2.60,
            ["last"] = 2.55,
            ["volume"] = 150,
            ["openInterest"] = 1250,
            ["impliedVolatility"] = 0.25,
            ["IsSampleData"] = true,
            ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
        };
        
        return optionData;
    }

    /// <summary>
    /// Gets SAMPLE stock data for testing
    /// </summary>
    public async Task<Dictionary<string, object>> GetStockDataAsync(string symbol)
    {
        _logger.LogInformation("Getting SAMPLE stock data for {Symbol}", symbol);
        
        // Simulate network delay
        await Task.Delay(100);
        
        var stockPrices = new Dictionary<string, Dictionary<string, object>>
        {
            ["AAPL"] = new Dictionary<string, object>
            {
                ["symbol"] = "AAPL",
                ["bid"] = 178.45,
                ["ask"] = 178.55,
                ["last"] = 178.50,
                ["volume"] = 2500000,
                ["marketCap"] = 2800000000000,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            },
            ["MSFT"] = new Dictionary<string, object>
            {
                ["symbol"] = "MSFT",
                ["bid"] = 374.90,
                ["ask"] = 375.10,
                ["last"] = 375.00,
                ["volume"] = 1800000,
                ["marketCap"] = 2800000000000,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            },
            ["NVDA"] = new Dictionary<string, object>
            {
                ["symbol"] = "NVDA",
                ["bid"] = 414.80,
                ["ask"] = 415.20,
                ["last"] = 415.00,
                ["volume"] = 3200000,
                ["marketCap"] = 1020000000000,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            },
            ["^VIX"] = new Dictionary<string, object>
            {
                ["symbol"] = "^VIX",
                ["bid"] = 18.75,
                ["ask"] = 18.85,
                ["last"] = 18.80,
                ["volume"] = 0,
                ["marketCap"] = 0,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            },
            ["SPY"] = new Dictionary<string, object>
            {
                ["symbol"] = "SPY",
                ["bid"] = 485.20,
                ["ask"] = 485.30,
                ["last"] = 485.25,
                ["volume"] = 45000000,
                ["marketCap"] = 0,
                ["IsSampleData"] = true,
                ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
            }
        };

        if (stockPrices.ContainsKey(symbol))
        {
            return stockPrices[symbol];
        }

        return new Dictionary<string, object>
        {
            ["symbol"] = symbol,
            ["bid"] = 150.00,
            ["ask"] = 150.10,
            ["last"] = 150.05,
            ["volume"] = 1000000,
            ["IsSampleData"] = true,
            ["SampleDataLabel"] = "SAMPLE DATA - For Testing Only"
        };
    }
} 