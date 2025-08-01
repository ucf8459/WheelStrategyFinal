using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;
using WheelStrategy.IBKR.Services;

namespace WheelStrategy.Core.Services;

/// <summary>
/// Wheel strategy opportunity scanner implementation
/// </summary>
public class WheelScanner : IWheelScanner
{
    private readonly ILogger<WheelScanner> _logger;
    private readonly WheelStrategyOptions _options;
    private readonly IBKRMarketDataService _marketDataService;
    private readonly IWheelMonitor _wheelMonitor;
    
    public WheelScanner(
        IOptions<WheelStrategyOptions> options,
        IBKRMarketDataService marketDataService,
        IWheelMonitor wheelMonitor,
        ILogger<WheelScanner> logger)
    {
        _options = options.Value;
        _marketDataService = marketDataService;
        _wheelMonitor = wheelMonitor;
        _logger = logger;
    }
    
    public async Task<List<OptionOpportunity>> ScanOpportunitiesAsync()
    {
        try
        {
            var opportunities = new List<OptionOpportunity>();
            
            foreach (var symbol in _options.Watchlist)
            {
                try
                {
                    var symbolOpportunities = await ScanSymbolOpportunitiesAsync(symbol);
                    opportunities.AddRange(symbolOpportunities);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to scan opportunities for {Symbol}", symbol);
                }
            }
            
            // Sort by annual return and filter by criteria
            var filteredOpportunities = opportunities
                .Where(opp => opp.MeetsCriteria)
                .OrderByDescending(opp => opp.AnnualReturn)
                .ToList();
            
            _logger.LogInformation("Found {Count} opportunities meeting criteria", filteredOpportunities.Count);
            
            return filteredOpportunities;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to scan opportunities");
            return new List<OptionOpportunity>();
        }
    }
    
    public async Task<List<OptionOpportunity>> ScanAllOpportunitiesAsync()
    {
        try
        {
            var opportunities = new List<OptionOpportunity>();
            
            foreach (var symbol in _options.Watchlist)
            {
                try
                {
                    var symbolOpportunities = await ScanSymbolOpportunitiesAsync(symbol);
                    opportunities.AddRange(symbolOpportunities);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to scan opportunities for {Symbol}", symbol);
                }
            }
            
            // Sort by annual return (no filtering)
            return opportunities
                .OrderByDescending(opp => opp.AnnualReturn)
                .ToList();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to scan all opportunities");
            return new List<OptionOpportunity>();
        }
    }
    
    public async Task<List<OptionOpportunity>> GetSectorOpportunitiesAsync(string sector)
    {
        try
        {
            var allOpportunities = await ScanAllOpportunitiesAsync();
            return allOpportunities
                .Where(opp => opp.Sector.Equals(sector, StringComparison.OrdinalIgnoreCase))
                .ToList();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get sector opportunities for {Sector}", sector);
            return new List<OptionOpportunity>();
        }
    }
    
    public async Task<List<Dictionary<string, object>>> GetSectorGapsAsync()
    {
        try
        {
            var currentAllocations = await _wheelMonitor.GetSectorAllocationsAsync();
            var gaps = new List<Dictionary<string, object>>();
            
            // Define target allocations
            var targetAllocations = new Dictionary<string, decimal>
            {
                ["Technology"] = 0.20m,
                ["Financial Services"] = 0.15m,
                ["Healthcare"] = 0.15m,
                ["Consumer Cyclical"] = 0.10m,
                ["Consumer Staples"] = 0.10m,
                ["Industrials"] = 0.10m,
                ["Energy"] = 0.05m,
                ["Utilities"] = 0.05m,
                ["Materials"] = 0.05m,
                ["Real Estate"] = 0.05m
            };
            
            foreach (var target in targetAllocations)
            {
                var current = currentAllocations.GetValueOrDefault(target.Key, 0);
                var gap = target.Value - current;
                
                if (gap > 0.05m) // Only consider meaningful gaps
                {
                    gaps.Add(new Dictionary<string, object>
                    {
                        ["sector"] = target.Key,
                        ["current"] = current,
                        ["target"] = target.Value,
                        ["gap"] = gap,
                        ["priority"] = gap * 10 // Simple priority calculation
                    });
                }
            }
            
            return gaps.OrderByDescending(g => g["priority"]).ToList();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get sector gaps");
            return new List<Dictionary<string, object>>();
        }
    }
    
    public async Task<List<Dictionary<string, object>>> DetectSectorRotationAsync()
    {
        try
        {
            // Simplified sector rotation detection
            // In production, would analyze sector ETF performance over time
            var rotations = new List<Dictionary<string, object>>();
            
            // Simulate rotation detection
            var vixLevel = await _wheelMonitor.GetVIXPercentileAsync();
            
            if (vixLevel > 75)
            {
                // High VIX - defensive rotation
                rotations.Add(new Dictionary<string, object>
                {
                    ["from_sector"] = "Technology",
                    ["to_sector"] = "Utilities",
                    ["reason"] = "High VIX defensive rotation",
                    ["strength"] = 0.8m
                });
            }
            else if (vixLevel < 25)
            {
                // Low VIX - growth rotation
                rotations.Add(new Dictionary<string, object>
                {
                    ["from_sector"] = "Utilities",
                    ["to_sector"] = "Technology",
                    ["reason"] = "Low VIX growth rotation",
                    ["strength"] = 0.7m
                });
            }
            
            return rotations;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to detect sector rotation");
            return new List<Dictionary<string, object>>();
        }
    }
    
    private async Task<List<OptionOpportunity>> ScanSymbolOpportunitiesAsync(string symbol)
    {
        var opportunities = new List<OptionOpportunity>();
        
        try
        {
            // Get stock data
            var stockData = await _marketDataService.GetStockDataAsync(symbol);
            var currentPrice = Convert.ToDecimal(stockData["last"]);
            
            // Get IV metrics
            var (ivRank, currentIV) = await _wheelMonitor.GetIVMetricsAsync(symbol);
            
            // Generate potential strikes (simplified)
            var strikes = GeneratePotentialStrikes(currentPrice);
            
            foreach (var strike in strikes)
            {
                try
                {
                    var opportunity = await CreateOpportunityAsync(symbol, strike, currentPrice, ivRank, currentIV);
                    if (opportunity != null)
                    {
                        opportunities.Add(opportunity);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to create opportunity for {Symbol} {Strike}", symbol, strike);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to scan symbol opportunities for {Symbol}", symbol);
        }
        
        return opportunities;
    }
    
    private List<decimal> GeneratePotentialStrikes(decimal currentPrice)
    {
        var strikes = new List<decimal>();
        
        // Generate strikes from 80% to 95% of current price
        for (int i = 80; i <= 95; i += 5)
        {
            var strike = currentPrice * i / 100;
            strikes.Add(Math.Round(strike, 2));
        }
        
        return strikes;
    }
    
    private async Task<OptionOpportunity?> CreateOpportunityAsync(
        string symbol, 
        decimal strike, 
        decimal currentPrice, 
        decimal ivRank, 
        decimal currentIV)
    {
        try
        {
            // Get option data
            var optionData = await _marketDataService.GetOptionDataAsync(symbol, strike, "20241220", "P");
            
            if (!optionData.ContainsKey("bid") || !optionData.ContainsKey("ask"))
            {
                return null;
            }
            
            var bid = Convert.ToDecimal(optionData["bid"]);
            var ask = Convert.ToDecimal(optionData["ask"]);
            var premium = (bid + ask) / 2; // Mid price
            
            if (premium <= 0)
            {
                return null;
            }
            
            // Calculate metrics
            var dte = 30; // Simplified DTE calculation
            var annualReturn = (premium / strike) * (365m / dte);
            var moneyness = strike / currentPrice;
            var liquidityScore = CalculateLiquidityScore(optionData);
            var sector = await GetSectorAsync(symbol);
            
            // Check entry criteria
            var meetsCriteria = await _wheelMonitor.CheckEntryCriteriaAsync(symbol, strike);
            
            var opportunity = new OptionOpportunity
            {
                Symbol = symbol,
                Strike = strike,
                Premium = premium,
                DaysToExpiration = dte,
                Expiry = "20241220",
                AnnualReturn = annualReturn,
                IVRank = ivRank,
                CurrentIV = currentIV,
                Moneyness = moneyness,
                CurrentPrice = currentPrice,
                Sector = sector,
                LiquidityScore = liquidityScore,
                PositionSizeAdjustment = 1.0m,
                MeetsCriteria = meetsCriteria
            };
            
            // Add issues if criteria not met
            if (!meetsCriteria)
            {
                opportunity.Issues.Add("Does not meet entry criteria");
            }
            
            return opportunity;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create opportunity for {Symbol} {Strike}", symbol, strike);
            return null;
        }
    }
    
    private decimal CalculateLiquidityScore(Dictionary<string, object> optionData)
    {
        try
        {
            var bid = Convert.ToDecimal(optionData["bid"]);
            var ask = Convert.ToDecimal(optionData["ask"]);
            var volume = Convert.ToInt32(optionData.GetValueOrDefault("volume", 0));
            
            if (bid == 0 || ask == 0)
            {
                return 0;
            }
            
            var spread = (ask - bid) / ((ask + bid) / 2);
            var liquidityScore = (volume * 1000) / (spread * 10000);
            
            return Math.Min(liquidityScore, 10000);
        }
        catch
        {
            return 0;
        }
    }
    
    private async Task<string> GetSectorAsync(string symbol)
    {
        // Simplified sector mapping
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
} 