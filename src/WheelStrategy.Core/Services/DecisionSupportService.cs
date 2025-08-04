using Microsoft.Extensions.Logging;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Services;

/// <summary>
/// Service for managing decision support and tracking
/// </summary>
public class DecisionSupportService : IDecisionSupportService
{
    private readonly ILogger<DecisionSupportService> _logger;
    private readonly IWheelMonitor _wheelMonitor;
    private readonly IMarketDataService _marketDataService;
    private readonly Dictionary<string, int> _dailyDecisions;
    private readonly object _lockObject = new();
    
    public DecisionSupportService(
        ILogger<DecisionSupportService> logger,
        IWheelMonitor wheelMonitor,
        IMarketDataService marketDataService)
    {
        _logger = logger;
        _wheelMonitor = wheelMonitor;
        _marketDataService = marketDataService;
        _dailyDecisions = new Dictionary<string, int>();
    }
    
    public async Task<DecisionSupportSummary> GetDecisionSupportSummaryAsync()
    {
        try
        {
            var decisionsUsedToday = await GetDecisionsUsedTodayAsync();
            var decisionItems = await AnalyzePositionsForDecisionsAsync();
            var upcomingExpirations = await GetUpcomingExpirationsAsync();
            
            var summary = new DecisionSupportSummary
            {
                DecisionsUsedToday = decisionsUsedToday,
                LastResetDate = DateTime.Today,
                CriticalDecisions = decisionItems.Where(d => d.Priority == DecisionPriority.Critical).ToList(),
                ImportantDecisions = decisionItems.Where(d => d.Priority == DecisionPriority.Important).ToList(),
                InfoDecisions = decisionItems.Where(d => d.Priority == DecisionPriority.Info).ToList(),
                UpcomingExpirations = upcomingExpirations
            };
            
            _logger.LogInformation("Generated decision support summary with {CriticalCount} critical, {ImportantCount} important, {InfoCount} info decisions",
                summary.CriticalDecisions.Count, summary.ImportantDecisions.Count, summary.InfoDecisions.Count);
            
            return summary;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get decision support summary");
            throw;
        }
    }
    
    public async Task RecordDecisionAsync(string decision, string category)
    {
        try
        {
            lock (_lockObject)
            {
                var today = DateTime.Today.ToString("yyyy-MM-dd");
                if (!_dailyDecisions.ContainsKey(today))
                {
                    _dailyDecisions[today] = 0;
                }
                _dailyDecisions[today]++;
            }
            
            _logger.LogInformation("Recorded decision: {Decision} in category {Category}", decision, category);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to record decision");
            throw;
        }
    }
    
    public async Task<List<DecisionItem>> AnalyzePositionsForDecisionsAsync()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            var decisions = new List<DecisionItem>();
            
            foreach (var position in positions)
            {
                // Analyze PUT positions
                for (int i = 0; i < position.PutDeltas.Count; i++)
                {
                    var delta = position.PutDeltas[i];
                    var strike = i < position.PutStrikes.Count ? position.PutStrikes[i] : 0;
                    var dte = i < position.PutDTEs.Count ? position.PutDTEs[i] : 0;
                    var expiry = i < position.PutExpiries.Count ? position.PutExpiries[i] : "";
                    
                    var decision = AnalyzePutPosition(position, delta, strike, dte, expiry);
                    if (decision != null)
                    {
                        decisions.Add(decision);
                    }
                }
                
                // Analyze CALL positions
                if (position.CallDeltas != null)
                {
                    for (int i = 0; i < position.CallDeltas.Count; i++)
                    {
                        var delta = position.CallDeltas[i];
                        var strike = i < (position.CallStrikes?.Count ?? 0) ? position.CallStrikes![i] : 0;
                        var dte = i < (position.CallDTEs?.Count ?? 0) ? position.CallDTEs![i] : 0;
                        var expiry = i < (position.CallExpiries?.Count ?? 0) ? position.CallExpiries![i] : "";
                        
                        var decision = AnalyzeCallPosition(position, delta, strike, dte, expiry);
                        if (decision != null)
                        {
                            decisions.Add(decision);
                        }
                    }
                }
                
                // Analyze stock positions
                if (position.SharesOwned > 0)
                {
                    var decision = AnalyzeStockPosition(position);
                    if (decision != null)
                    {
                        decisions.Add(decision);
                    }
                }
            }
            
            _logger.LogInformation("Analyzed {PositionCount} positions and generated {DecisionCount} decision items", 
                positions.Count, decisions.Count);
            
            return decisions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to analyze positions for decisions");
            throw;
        }
    }
    
    public async Task<List<UpcomingExpiration>> GetUpcomingExpirationsAsync()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            var upcomingExpirations = new List<UpcomingExpiration>();
            var cutoffDate = DateTime.Today.AddDays(7);
            
            foreach (var position in positions)
            {
                // Check PUT expirations
                for (int i = 0; i < position.PutDTEs.Count; i++)
                {
                    var dte = position.PutDTEs[i];
                    if (dte <= 7)
                    {
                        var delta = i < position.PutDeltas.Count ? position.PutDeltas[i] : 0;
                        var strike = i < position.PutStrikes.Count ? position.PutStrikes[i] : 0;
                        var expiry = i < position.PutExpiries.Count ? position.PutExpiries[i] : "";
                        
                        var expiration = CreateUpcomingExpiration(position, delta, strike, dte, expiry, "PUT");
                        upcomingExpirations.Add(expiration);
                    }
                }
                
                // Check CALL expirations
                if (position.CallDTEs != null)
                {
                    for (int i = 0; i < position.CallDTEs.Count; i++)
                    {
                        var dte = position.CallDTEs[i];
                        if (dte <= 7)
                        {
                            var delta = i < (position.CallDeltas?.Count ?? 0) ? position.CallDeltas![i] : 0;
                            var strike = i < (position.CallStrikes?.Count ?? 0) ? position.CallStrikes![i] : 0;
                            var expiry = i < (position.CallExpiries?.Count ?? 0) ? position.CallExpiries![i] : "";
                            
                            var expiration = CreateUpcomingExpiration(position, delta, strike, dte, expiry, "CALL");
                            upcomingExpirations.Add(expiration);
                        }
                    }
                }
            }
            
            _logger.LogInformation("Found {ExpirationCount} upcoming expirations within 7 days", upcomingExpirations.Count);
            
            return upcomingExpirations;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get upcoming expirations");
            throw;
        }
    }
    
    public async Task ResetDailyDecisionCounterAsync()
    {
        try
        {
            lock (_lockObject)
            {
                var today = DateTime.Today.ToString("yyyy-MM-dd");
                _dailyDecisions[today] = 0;
            }
            
            _logger.LogInformation("Reset daily decision counter");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to reset daily decision counter");
            throw;
        }
    }
    
    public async Task<int> GetDecisionsUsedTodayAsync()
    {
        try
        {
            lock (_lockObject)
            {
                var today = DateTime.Today.ToString("yyyy-MM-dd");
                return _dailyDecisions.GetValueOrDefault(today, 0);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get decisions used today");
            throw;
        }
    }
    
    private DecisionItem? AnalyzePutPosition(WheelPosition position, decimal delta, decimal strike, int dte, string expiry)
    {
        // CRITICAL: Delta > 0.50 (defensive roll needed)
        if (delta > 0.50m)
        {
            return new DecisionItem
            {
                Priority = DecisionPriority.Critical,
                Title = $"Defensive Roll Required - {position.Symbol} PUT",
                Description = $"PUT position has delta {delta:F3} > 0.50. Immediate defensive roll required.",
                ActionRequired = "Roll to lower strike immediately",
                Symbol = position.Symbol,
                PositionType = "PUT",
                Strike = strike,
                DTE = dte,
                Delta = delta,
                Category = "Defensive Roll"
            };
        }
        
        // IMPORTANT: At 21 DTE (time-based roll)
        if (dte == 21)
        {
            return new DecisionItem
            {
                Priority = DecisionPriority.Important,
                Title = $"Time-Based Roll - {position.Symbol} PUT",
                Description = $"PUT position at 21 DTE. Consider rolling to next monthly cycle.",
                ActionRequired = "Roll to next monthly expiration",
                Symbol = position.Symbol,
                PositionType = "PUT",
                Strike = strike,
                DTE = dte,
                Category = "Time-Based Roll"
            };
        }
        
        // INFO: High profit positions
        if (delta > 0.80m)
        {
            return new DecisionItem
            {
                Priority = DecisionPriority.Info,
                Title = $"High Profit Opportunity - {position.Symbol} PUT",
                Description = $"PUT position showing high profit. Consider early close or roll.",
                ActionRequired = "Consider closing for profit",
                Symbol = position.Symbol,
                PositionType = "PUT",
                Strike = strike,
                Category = "Profit Taking"
            };
        }
        
        return null;
    }
    
    private DecisionItem? AnalyzeCallPosition(WheelPosition position, decimal delta, decimal strike, int dte, string expiry)
    {
        // IMPORTANT: Covered calls at 50% profit
        if (delta > 0.50m)
        {
            return new DecisionItem
            {
                Priority = DecisionPriority.Important,
                Title = $"Covered Call Profit Target - {position.Symbol}",
                Description = $"Covered call position at 50% profit target. Consider closing.",
                ActionRequired = "Close covered call for profit",
                Symbol = position.Symbol,
                PositionType = "CALL",
                Strike = strike,
                DTE = dte,
                Category = "Profit Taking"
            };
        }
        
        return null;
    }
    
    private DecisionItem? AnalyzeStockPosition(WheelPosition position)
    {
        // INFO: Stock positions with significant P&L
        if (position.SharesOwned > 0 && position.StockPrice.HasValue && position.AssignmentPrice.HasValue)
        {
            var pnlPercent = ((position.StockPrice.Value - position.AssignmentPrice.Value) / position.AssignmentPrice.Value) * 100;
            
            if (Math.Abs(pnlPercent) > 10)
            {
                return new DecisionItem
                {
                    Priority = DecisionPriority.Info,
                    Title = $"Stock Position Review - {position.Symbol}",
                    Description = $"Stock position showing {pnlPercent:F1}% P&L. Review for covered call opportunity.",
                    ActionRequired = "Consider selling covered calls",
                    Symbol = position.Symbol,
                    PositionType = "STOCK",
                    PnLPercent = pnlPercent,
                    Category = "Stock Management"
                };
            }
        }
        
        return null;
    }
    
    private UpcomingExpiration CreateUpcomingExpiration(WheelPosition position, decimal delta, decimal strike, int dte, string expiry, string positionType)
    {
        var currentPrice = position.StockPrice ?? 0;
        
        string status;
        string recommendation;
        
        if (positionType == "PUT")
        {
            if (currentPrice > strike * 1.05m)
            {
                status = "Safe OTM";
                recommendation = "Let expire";
            }
            else if (currentPrice > strike)
            {
                status = "At Risk";
                recommendation = "Monitor closely";
            }
            else
            {
                status = "ITM";
                recommendation = "Roll or accept assignment";
            }
        }
        else // CALL
        {
            if (currentPrice < strike * 0.95m)
            {
                status = "Safe OTM";
                recommendation = "Let expire";
            }
            else if (currentPrice < strike)
            {
                status = "At Risk";
                recommendation = "Monitor closely";
            }
            else
            {
                status = "ITM";
                recommendation = "Roll or let assign";
            }
        }
        
        return new UpcomingExpiration
        {
            Symbol = position.Symbol,
            Expiry = DateTime.Today.AddDays(dte),
            Strike = strike,
            PositionType = positionType,
            CurrentPrice = currentPrice,
            Status = status,
            Recommendation = recommendation,
            DTE = dte,
            Delta = delta
        };
    }
    

} 