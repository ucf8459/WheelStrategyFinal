using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;
using WheelStrategy.IBKR.Services;

namespace WheelStrategy.Core.Services;

/// <summary>
/// Core wheel strategy monitor implementation
/// </summary>
public class WheelMonitor : IWheelMonitor
{
    private readonly ILogger<WheelMonitor> _logger;
    private readonly WheelStrategyOptions _options;
    private readonly IBKRMarketDataService _marketDataService;
    private readonly List<WheelPosition> _wheelPositions = new();
    private readonly List<Dictionary<string, object>> _tradeHistory = new();
    private decimal _accountValue;
    private decimal _peakValue;
    private int _consecutiveWins;
    
    public WheelMonitor(
        IOptions<WheelStrategyOptions> options,
        IBKRMarketDataService marketDataService,
        ILogger<WheelMonitor> logger)
    {
        _options = options.Value;
        _marketDataService = marketDataService;
        _logger = logger;
    }
    
    public async Task<PortfolioMetrics> GetPortfolioMetricsAsync()
    {
        try
        {
            var accountSummary = await _marketDataService.GetAccountSummaryAsync();
            var positions = await _marketDataService.GetPositionsAsync();
            
            // Calculate account value
            _accountValue = decimal.Parse(accountSummary["NetLiquidation"].ToString() ?? "0");
            _peakValue = Math.Max(_peakValue, _accountValue);
            
            var availableFunds = decimal.Parse(accountSummary["AvailableFunds"].ToString() ?? "0");
            var unrealizedPnL = decimal.Parse(accountSummary["UnrealizedPnL"].ToString() ?? "0");
            
            var metrics = new PortfolioMetrics
            {
                AccountValue = _accountValue,
                AvailableFunds = availableFunds,
                UnrealizedPnL = unrealizedPnL,
                CashPercentage = _accountValue > 0 ? availableFunds / _accountValue : 0,
                TotalIncome = CalculateTotalIncome(),
                WinRate = CalculateWinRate(),
                AverageReturn = CalculateAverageReturn(),
                MaxDrawdown = CalculateMaxDrawdown(),
                SharpeRatio = CalculateSharpeRatio(),
                TotalTrades = _tradeHistory.Count,
                WinningTrades = _tradeHistory.Count(t => (bool)t.GetValueOrDefault("profitable", false)),
                LosingTrades = _tradeHistory.Count(t => !(bool)t.GetValueOrDefault("profitable", false)),
                VIXLevel = await GetVIXLevelAsync(),
                VIXPercentile = await GetVIXPercentileAsync(),
                MarketRegime = await GetMarketRegimeAsync(),
                Correlation = await CalculateCorrelationAsync(),
                SectorAllocations = await GetSectorAllocationsAsync(),
                LastUpdated = DateTime.UtcNow
            };
            
            return metrics;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get portfolio metrics");
            throw;
        }
    }
    
    public async Task<List<WheelPosition>> GetWheelPositionsAsync()
    {
        try
        {
            var positions = await _marketDataService.GetPositionsAsync();
            var wheelPositions = new List<WheelPosition>();
            
            // Group positions by symbol
            var symbolGroups = positions
                .Where(p => p["secType"].ToString() == "OPT" || p["secType"].ToString() == "STK")
                .GroupBy(p => p["symbol"].ToString());
            
            foreach (var group in symbolGroups)
            {
                var symbol = group.Key!;
                var wheelPosition = new WheelPosition { Symbol = symbol };
                
                foreach (var position in group)
                {
                    var secType = position["secType"].ToString();
                    var pos = Convert.ToInt32(position["position"]);
                    
                    if (secType == "OPT")
                    {
                        var strike = Convert.ToDecimal(position["strike"]);
                        var right = position["right"].ToString();
                        var marketValue = Convert.ToDecimal(position["marketValue"]);
                        
                        if (right == "P" && pos < 0) // Short put
                        {
                            wheelPosition.PutStrikes.Add(strike);
                            wheelPosition.PutCredits.Add(Math.Abs(marketValue));
                        }
                        else if (right == "C" && pos < 0) // Short call
                        {
                            wheelPosition.CallStrikes ??= new List<decimal>();
                            wheelPosition.CallStrikes.Add(strike);
                            wheelPosition.CallCredits ??= new List<decimal>();
                            wheelPosition.CallCredits.Add(Math.Abs(marketValue));
                        }
                    }
                    else if (secType == "STK" && pos > 0)
                    {
                        wheelPosition.SharesOwned = pos;
                        wheelPosition.AssignmentPrice = Convert.ToDecimal(position["avgCost"]);
                    }
                }
                
                if (wheelPosition.HasActivePuts || wheelPosition.HasShares)
                {
                    wheelPositions.Add(wheelPosition);
                }
            }
            
            return wheelPositions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get wheel positions");
            throw;
        }
    }
    
    public async Task<bool> CheckEntryCriteriaAsync(string symbol, decimal strike)
    {
        try
        {
            // Check IV requirements
            var (ivRank, currentIV) = await GetIVMetricsAsync(symbol);
            if (ivRank < _options.RiskThresholds.IVRankMinimum || currentIV < _options.RiskThresholds.IVMinimum)
            {
                return false;
            }
            
            // Check position sizing
            var positionSize = strike * 100;
            if (positionSize > _accountValue * _options.RiskThresholds.MaxPositionPercentage)
            {
                return false;
            }
            
            // Check sector concentration
            var sectorAllocations = await GetSectorAllocationsAsync();
            var sector = await GetSectorAsync(symbol);
            var currentSectorExposure = sectorAllocations.GetValueOrDefault(sector, 0);
            var newExposure = currentSectorExposure + positionSize;
            
            if (newExposure > _accountValue * _options.RiskThresholds.MaxSectorPercentage)
            {
                return false;
            }
            
            // Check earnings buffer
            var daysToEarnings = await GetDaysToEarningsAsync(symbol);
            if (daysToEarnings <= _options.RiskThresholds.EarningsBufferDays)
            {
                return false;
            }
            
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to check entry criteria for {Symbol} {Strike}", symbol, strike);
            return false;
        }
    }
    
    public async Task<(decimal IVRank, decimal CurrentIV)> GetIVMetricsAsync(string symbol)
    {
        // Simplified IV calculation - in production would use real option chain data
        try
        {
            var stockData = await _marketDataService.GetStockDataAsync(symbol);
            var currentPrice = Convert.ToDecimal(stockData["last"]);
            
            // Simulate IV calculation (in production would use actual option data)
            var random = new Random(symbol.GetHashCode());
            var currentIV = 20 + random.Next(0, 40); // 20-60% IV
            var ivRank = random.Next(0, 100); // 0-100% rank
            
            return (ivRank, currentIV);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get IV metrics for {Symbol}", symbol);
            return (0, 0);
        }
    }
    
    public async Task<bool> ShouldRollPositionAsync(string symbol, decimal strike, int daysToExpiration)
    {
        try
        {
            // Check delta threshold
            var optionData = await _marketDataService.GetOptionDataAsync(symbol, strike, "20241220", "P");
            if (optionData.ContainsKey("delta"))
            {
                var delta = Math.Abs(Convert.ToDecimal(optionData["delta"]));
                if (delta > _options.RiskThresholds.RollDeltaThreshold)
                {
                    return true;
                }
            }
            
            // Check DTE threshold
            if (daysToExpiration <= _options.RiskThresholds.RollDTE)
            {
                return true;
            }
            
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to check roll criteria for {Symbol} {Strike}", symbol, strike);
            return false;
        }
    }
    
    public async Task<string> GetMarketRegimeAsync()
    {
        try
        {
            var spyData = await _marketDataService.GetStockDataAsync("SPY");
            var currentPrice = Convert.ToDecimal(spyData["last"]);
            
            // Simplified regime detection (in production would use more sophisticated analysis)
            var vixLevel = await GetVIXLevelAsync();
            
            if (vixLevel < 20)
            {
                return "BULL";
            }
            else if (vixLevel > 30)
            {
                return "BEAR";
            }
            else
            {
                return "NEUTRAL";
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get market regime");
            return "NEUTRAL";
        }
    }
    
    public async Task<decimal> GetVIXPercentileAsync()
    {
        try
        {
            var vixLevel = await GetVIXLevelAsync();
            
            // Simplified percentile calculation (in production would use historical data)
            if (vixLevel < 15) return 25;
            if (vixLevel < 20) return 50;
            if (vixLevel < 25) return 75;
            if (vixLevel < 30) return 85;
            return 95;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get VIX percentile");
            return 50;
        }
    }
    
    public async Task<Dictionary<string, decimal>> GetSectorAllocationsAsync()
    {
        try
        {
            var positions = await _marketDataService.GetPositionsAsync();
            var allocations = new Dictionary<string, decimal>();
            
            foreach (var position in positions)
            {
                var symbol = position["symbol"].ToString()!;
                var sector = await GetSectorAsync(symbol);
                var marketValue = Convert.ToDecimal(position["marketValue"]);
                
                allocations[sector] = allocations.GetValueOrDefault(sector, 0) + marketValue;
            }
            
            return allocations;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get sector allocations");
            return new Dictionary<string, decimal>();
        }
    }
    
    public async Task RecordTradeResultAsync(Dictionary<string, object> tradeResult)
    {
        try
        {
            _tradeHistory.Add(tradeResult);
            
            var profitable = (bool)tradeResult.GetValueOrDefault("profitable", false);
            if (profitable)
            {
                _consecutiveWins++;
            }
            else
            {
                _consecutiveWins = 0;
            }
            
            _logger.LogInformation("Recorded trade result: {Symbol} {Action} {Result}", 
                tradeResult.GetValueOrDefault("symbol"), 
                tradeResult.GetValueOrDefault("action"),
                profitable ? "WIN" : "LOSS");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to record trade result");
        }
    }
    
    public async Task<List<Dictionary<string, object>>> GetRecentTradesAsync(int count)
    {
        return _tradeHistory
            .OrderByDescending(t => t.GetValueOrDefault("timestamp", DateTime.MinValue))
            .Take(count)
            .ToList();
    }
    
    // Private helper methods
    
    private decimal CalculateTotalIncome()
    {
        return _wheelPositions.Sum(wp => wp.TotalIncome);
    }
    
    private decimal CalculateWinRate()
    {
        if (_tradeHistory.Count == 0) return 0;
        var wins = _tradeHistory.Count(t => (bool)t.GetValueOrDefault("profitable", false));
        return (decimal)wins / _tradeHistory.Count;
    }
    
    private decimal CalculateAverageReturn()
    {
        if (_tradeHistory.Count == 0) return 0;
        var returns = _tradeHistory
            .Where(t => t.ContainsKey("return"))
            .Select(t => Convert.ToDecimal(t["return"]));
        return returns.Any() ? returns.Average() : 0;
    }
    
    private decimal CalculateMaxDrawdown()
    {
        if (_peakValue == 0) return 0;
        return (_peakValue - _accountValue) / _peakValue;
    }
    
    private decimal CalculateSharpeRatio()
    {
        // Simplified Sharpe ratio calculation
        if (_tradeHistory.Count < 2) return 0;
        
        var returns = _tradeHistory
            .Where(t => t.ContainsKey("return"))
            .Select(t => Convert.ToDecimal(t["return"]))
            .ToList();
        
        if (returns.Count < 2) return 0;
        
        var avgReturn = returns.Average();
        var stdDev = (decimal)Math.Sqrt((double)returns.Select(r => (r - avgReturn) * (r - avgReturn)).Average());
        
        return stdDev > 0 ? avgReturn / stdDev : 0;
    }
    
    private async Task<decimal> GetVIXLevelAsync()
    {
        try
        {
            var vixData = await _marketDataService.GetStockDataAsync("^VIX");
            return Convert.ToDecimal(vixData["last"]);
        }
        catch
        {
            return 20; // Default VIX level
        }
    }
    
    private async Task<decimal> CalculateCorrelationAsync()
    {
        // Simplified correlation calculation
        return 0.5m; // Default correlation
    }
    
    private async Task<string> GetSectorAsync(string symbol)
    {
        // Simplified sector mapping (in production would use real sector data)
        var sectorMap = new Dictionary<string, string>
        {
            ["AAPL"] = "Technology",
            ["MSFT"] = "Technology",
            ["GOOGL"] = "Technology",
            ["AMZN"] = "Consumer Cyclical",
            ["TSLA"] = "Consumer Cyclical",
            ["JPM"] = "Financial Services",
            ["BAC"] = "Financial Services",
            ["WFC"] = "Financial Services",
            ["C"] = "Financial Services"
        };
        
        return sectorMap.GetValueOrDefault(symbol, "Unknown");
    }
    
    private async Task<int> GetDaysToEarningsAsync(string symbol)
    {
        // Simplified earnings calculation (in production would use real earnings data)
        return 30; // Default 30 days
    }
} 