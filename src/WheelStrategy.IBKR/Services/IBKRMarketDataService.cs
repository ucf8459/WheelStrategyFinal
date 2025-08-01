using InteractiveBrokers;
using Microsoft.Extensions.Logging;
using WheelStrategy.Core.Interfaces;

namespace WheelStrategy.IBKR.Services;

/// <summary>
/// Provides market data from IBKR
/// </summary>
public class IBKRMarketDataService
{
    private readonly IBKRConnectionService _connectionService;
    private readonly ILogger<IBKRMarketDataService> _logger;
    
    public IBKRMarketDataService(
        IBKRConnectionService connectionService,
        ILogger<IBKRMarketDataService> logger)
    {
        _connectionService = connectionService;
        _logger = logger;
    }
    
    /// <summary>
    /// Gets real-time option data including Greeks
    /// </summary>
    public async Task<Dictionary<string, object>> GetOptionDataAsync(string symbol, decimal strike, string expiry, string right)
    {
        var ib = await _connectionService.GetConnectionAsync("MarketData");
        
        try
        {
            var contract = new Contract
            {
                Symbol = symbol,
                SecType = "OPT",
                Strike = (double)strike,
                Right = right,
                Exchange = "SMART",
                Currency = "USD",
                LastTradingDay = expiry
            };
            
            // Qualify the contract
            var qualifiedContracts = await Task.Run(() => ib.QualifyContracts(contract));
            if (!qualifiedContracts.Any())
            {
                throw new InvalidOperationException($"Failed to qualify contract for {symbol} {strike} {right} {expiry}");
            }
            
            var qualifiedContract = qualifiedContracts.First();
            
            // Request market data
            var ticker = await Task.Run(() => ib.RequestMarketData(qualifiedContract, "10,11,12,13", false, false));
            
            // Wait for data
            await Task.Delay(1000);
            
            var result = new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["strike"] = strike,
                ["expiry"] = expiry,
                ["right"] = right
            };
            
            // Extract Greeks from ticker
            if (ticker.ModelGreeks != null)
            {
                result["delta"] = ticker.ModelGreeks.Delta;
                result["gamma"] = ticker.ModelGreeks.Gamma;
                result["vega"] = ticker.ModelGreeks.Vega;
                result["theta"] = ticker.ModelGreeks.Theta;
            }
            
            if (ticker.Bid > 0 && ticker.Ask > 0)
            {
                result["bid"] = ticker.Bid;
                result["ask"] = ticker.Ask;
                result["last"] = ticker.Last;
                result["volume"] = ticker.Volume;
            }
            
            // Cancel market data request
            await Task.Run(() => ib.CancelMarketData(qualifiedContract));
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get option data for {Symbol} {Strike} {Right} {Expiry}", 
                symbol, strike, right, expiry);
            throw;
        }
    }
    
    /// <summary>
    /// Gets stock price data
    /// </summary>
    public async Task<Dictionary<string, object>> GetStockDataAsync(string symbol)
    {
        var ib = await _connectionService.GetConnectionAsync("MarketData");
        
        try
        {
            var contract = new Contract
            {
                Symbol = symbol,
                SecType = "STK",
                Exchange = "SMART",
                Currency = "USD"
            };
            
            var ticker = await Task.Run(() => ib.RequestMarketData(contract, "", false, false));
            
            await Task.Delay(500);
            
            var result = new Dictionary<string, object>
            {
                ["symbol"] = symbol
            };
            
            if (ticker.Bid > 0 && ticker.Ask > 0)
            {
                result["bid"] = ticker.Bid;
                result["ask"] = ticker.Ask;
                result["last"] = ticker.Last;
                result["volume"] = ticker.Volume;
            }
            
            await Task.Run(() => ib.CancelMarketData(contract));
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get stock data for {Symbol}", symbol);
            throw;
        }
    }
    
    /// <summary>
    /// Gets account summary
    /// </summary>
    public async Task<Dictionary<string, object>> GetAccountSummaryAsync()
    {
        var ib = await _connectionService.GetConnectionAsync("Monitor");
        
        try
        {
            var accountSummary = await Task.Run(() => ib.RequestAccountSummary("All"));
            
            await Task.Delay(1000);
            
            var result = new Dictionary<string, object>();
            
            foreach (var item in accountSummary)
            {
                result[item.Tag] = item.Value;
            }
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get account summary");
            throw;
        }
    }
    
    /// <summary>
    /// Gets current positions
    /// </summary>
    public async Task<List<Dictionary<string, object>>> GetPositionsAsync()
    {
        var ib = await _connectionService.GetConnectionAsync("Monitor");
        
        try
        {
            var positions = await Task.Run(() => ib.RequestPositions());
            
            await Task.Delay(1000);
            
            var result = new List<Dictionary<string, object>>();
            
            foreach (var position in positions)
            {
                var pos = new Dictionary<string, object>
                {
                    ["symbol"] = position.Contract.Symbol,
                    ["secType"] = position.Contract.SecType,
                    ["position"] = position.Position,
                    ["marketValue"] = position.MarketValue,
                    ["avgCost"] = position.AvgCost,
                    ["unrealizedPnL"] = position.UnrealizedPnL
                };
                
                if (position.Contract.SecType == "OPT")
                {
                    pos["strike"] = position.Contract.Strike;
                    pos["right"] = position.Contract.Right;
                    pos["expiry"] = position.Contract.LastTradingDay;
                }
                
                result.Add(pos);
            }
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get positions");
            throw;
        }
    }
} 