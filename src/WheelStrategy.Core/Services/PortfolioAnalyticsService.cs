using Microsoft.Extensions.Logging;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Services;

/// <summary>
/// Service for portfolio analytics and performance tracking
/// </summary>
public class PortfolioAnalyticsService : IPortfolioAnalyticsService
{
    private readonly ILogger<PortfolioAnalyticsService> _logger;
    private readonly IWheelMonitor _wheelMonitor;
    private readonly IMarketDataService _marketDataService;
    private readonly List<RealizedPnL> _realizedTrades;
    private readonly List<PortfolioPerformancePoint> _performanceHistory;
    
    public PortfolioAnalyticsService(
        ILogger<PortfolioAnalyticsService> logger,
        IWheelMonitor wheelMonitor,
        IMarketDataService marketDataService)
    {
        _logger = logger;
        _wheelMonitor = wheelMonitor;
        _marketDataService = marketDataService;
        _realizedTrades = new List<RealizedPnL>();
        _performanceHistory = new List<PortfolioPerformancePoint>();
        
        // Initialize with sample data for demonstration
        InitializeSampleData();
    }
    
    public async Task<PortfolioAnalyticsSummary> GetPortfolioAnalyticsAsync()
    {
        try
        {
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            
            var summary = new PortfolioAnalyticsSummary
            {
                TotalUnrealizedPnL = metrics.UnrealizedPnL,
                PerformanceHistory = await GetPerformanceHistoryAsync(),
                RecentTrades = await GetRealizedPnLAsync(),
                MonthlyPnL = await GetMonthlyPnLAsync(DateTime.Now.Year),
                QuarterlyPnL = await GetQuarterlyPnLAsync(DateTime.Now.Year),
                YearlyPnL = await GetYearlyPnLAsync()
            };
            
            // Calculate derived metrics
            summary.TotalRealizedPnL = summary.RecentTrades.Sum(t => t.RealizedPnLAmount);
            summary.TotalPnL = summary.TotalRealizedPnL + summary.TotalUnrealizedPnL;
            
            if (summary.RecentTrades.Any())
            {
                var winningTrades = summary.RecentTrades.Where(t => t.RealizedPnLAmount > 0).ToList();
                summary.WinRate = (decimal)winningTrades.Count / summary.RecentTrades.Count * 100;
                summary.AverageWin = winningTrades.Any() ? winningTrades.Average(t => t.RealizedPnLAmount) : 0;
                summary.AverageLoss = summary.RecentTrades.Where(t => t.RealizedPnLAmount < 0).Average(t => t.RealizedPnLAmount);
                summary.ProfitFactor = summary.AverageWin != 0 ? Math.Abs(summary.AverageWin / summary.AverageLoss) : 0;
            }
            
            // Calculate rolling returns
            var rollingReturns = await GetRollingReturnsAsync();
            summary.Rolling30DayReturn = rollingReturns.GetValueOrDefault("30Day", 0);
            summary.Rolling90DayReturn = rollingReturns.GetValueOrDefault("90Day", 0);
            summary.Rolling1YearReturn = rollingReturns.GetValueOrDefault("1Year", 0);
            
            // Calculate max drawdown
            var drawdowns = await GetDrawdownAnalysisAsync();
            summary.MaxDrawdown = drawdowns.Any() ? drawdowns.Max(d => d.DrawdownPercent) : 0;
            
            // Calculate Sharpe ratio (simplified)
            summary.SharpeRatio = CalculateSharpeRatio(summary.PerformanceHistory);
            
            _logger.LogInformation("Generated portfolio analytics summary with {TradeCount} trades, {WinRate:F1}% win rate",
                summary.RecentTrades.Count, summary.WinRate);
            
            return summary;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get portfolio analytics");
            throw;
        }
    }
    
    public async Task<List<PortfolioPerformancePoint>> GetPerformanceHistoryAsync(DateTime? startDate = null, DateTime? endDate = null)
    {
        try
        {
            var start = startDate ?? DateTime.Today.AddDays(-365);
            var end = endDate ?? DateTime.Today;
            
            var filteredHistory = _performanceHistory
                .Where(p => p.Date >= start && p.Date <= end)
                .OrderBy(p => p.Date)
                .ToList();
            
            _logger.LogInformation("Retrieved {Count} performance history points from {StartDate} to {EndDate}",
                filteredHistory.Count, start.ToShortDateString(), end.ToShortDateString());
            
            return filteredHistory;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get performance history");
            throw;
        }
    }
    
    public async Task<List<RealizedPnL>> GetRealizedPnLAsync(DateTime? startDate = null, DateTime? endDate = null)
    {
        try
        {
            var start = startDate ?? DateTime.Today.AddDays(-365);
            var end = endDate ?? DateTime.Today;
            
            var filteredTrades = _realizedTrades
                .Where(t => t.Date >= start && t.Date <= end)
                .OrderByDescending(t => t.Date)
                .ToList();
            
            _logger.LogInformation("Retrieved {Count} realized P&L trades from {StartDate} to {EndDate}",
                filteredTrades.Count, start.ToShortDateString(), end.ToShortDateString());
            
            return filteredTrades;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get realized P&L");
            throw;
        }
    }
    
    public async Task RecordRealizedPnLAsync(RealizedPnL trade)
    {
        try
        {
            _realizedTrades.Add(trade);
            _logger.LogInformation("Recorded realized P&L trade: {Symbol} {PositionType} {PnL:F2}",
                trade.Symbol, trade.PositionType, trade.RealizedPnLAmount);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to record realized P&L");
            throw;
        }
    }
    
    public async Task<List<DrawdownPeriod>> GetDrawdownAnalysisAsync()
    {
        try
        {
            var drawdowns = new List<DrawdownPeriod>();
            var performanceHistory = _performanceHistory.OrderBy(p => p.Date).ToList();
            
            if (!performanceHistory.Any()) return drawdowns;
            
            decimal peakValue = performanceHistory.First().PortfolioValue;
            DateTime peakDate = performanceHistory.First().Date;
            bool inDrawdown = false;
            
            foreach (var point in performanceHistory)
            {
                if (point.PortfolioValue > peakValue)
                {
                    // New peak
                    if (inDrawdown)
                    {
                        // End of drawdown period
                        var drawdown = new DrawdownPeriod
                        {
                            PeakDate = peakDate,
                            TroughDate = point.Date,
                            PeakValue = peakValue,
                            TroughValue = point.PortfolioValue,
                            DrawdownAmount = peakValue - point.PortfolioValue,
                            DrawdownPercent = (peakValue - point.PortfolioValue) / peakValue * 100,
                            Duration = point.Date - peakDate,
                            RecoveryDate = point.Date
                        };
                        drawdowns.Add(drawdown);
                        inDrawdown = false;
                    }
                    
                    peakValue = point.PortfolioValue;
                    peakDate = point.Date;
                }
                else if (point.PortfolioValue < peakValue && !inDrawdown)
                {
                    // Start of drawdown
                    inDrawdown = true;
                }
            }
            
            _logger.LogInformation("Calculated {Count} drawdown periods", drawdowns.Count);
            return drawdowns;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to calculate drawdown analysis");
            throw;
        }
    }
    
    public async Task<List<StrategyPerformance>> GetStrategyPerformanceAsync()
    {
        try
        {
            var strategies = new List<StrategyPerformance>();
            
            // Wheel Strategy
            var wheelTrades = _realizedTrades.Where(t => t.PositionType == "PUT" || t.PositionType == "CALL").ToList();
            if (wheelTrades.Any())
            {
                var wheelPerformance = new StrategyPerformance
                {
                    Strategy = "Wheel Strategy",
                    TotalPnL = wheelTrades.Sum(t => t.RealizedPnLAmount),
                    TotalTrades = wheelTrades.Count,
                    WinningTrades = wheelTrades.Count(t => t.RealizedPnLAmount > 0),
                    AverageReturn = wheelTrades.Average(t => t.RealizedPnLPercent)
                };
                wheelPerformance.WinRate = (decimal)wheelPerformance.WinningTrades / wheelPerformance.TotalTrades * 100;
                strategies.Add(wheelPerformance);
            }
            
            // Covered Calls
            var callTrades = _realizedTrades.Where(t => t.PositionType == "CALL").ToList();
            if (callTrades.Any())
            {
                var callPerformance = new StrategyPerformance
                {
                    Strategy = "Covered Calls",
                    TotalPnL = callTrades.Sum(t => t.RealizedPnLAmount),
                    TotalTrades = callTrades.Count,
                    WinningTrades = callTrades.Count(t => t.RealizedPnLAmount > 0),
                    AverageReturn = callTrades.Average(t => t.RealizedPnLPercent)
                };
                callPerformance.WinRate = (decimal)callPerformance.WinningTrades / callPerformance.TotalTrades * 100;
                strategies.Add(callPerformance);
            }
            
            // Cash Secured Puts
            var putTrades = _realizedTrades.Where(t => t.PositionType == "PUT").ToList();
            if (putTrades.Any())
            {
                var putPerformance = new StrategyPerformance
                {
                    Strategy = "Cash Secured Puts",
                    TotalPnL = putTrades.Sum(t => t.RealizedPnLAmount),
                    TotalTrades = putTrades.Count,
                    WinningTrades = putTrades.Count(t => t.RealizedPnLAmount > 0),
                    AverageReturn = putTrades.Average(t => t.RealizedPnLPercent)
                };
                putPerformance.WinRate = (decimal)putPerformance.WinningTrades / putPerformance.TotalTrades * 100;
                strategies.Add(putPerformance);
            }
            
            _logger.LogInformation("Calculated performance for {StrategyCount} strategies", strategies.Count);
            return strategies;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to calculate strategy performance");
            throw;
        }
    }
    
    public async Task<Dictionary<string, decimal>> GetMonthlyPnLAsync(int year)
    {
        try
        {
            var monthlyPnL = new Dictionary<string, decimal>();
            
            for (int month = 1; month <= 12; month++)
            {
                var monthTrades = _realizedTrades.Where(t => t.Date.Year == year && t.Date.Month == month).ToList();
                var monthPnL = monthTrades.Sum(t => t.RealizedPnLAmount);
                monthlyPnL[GetMonthName(month)] = monthPnL;
            }
            
            return monthlyPnL;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get monthly P&L");
            throw;
        }
    }
    
    public async Task<Dictionary<string, decimal>> GetQuarterlyPnLAsync(int year)
    {
        try
        {
            var quarterlyPnL = new Dictionary<string, decimal>();
            
            for (int quarter = 1; quarter <= 4; quarter++)
            {
                var startMonth = (quarter - 1) * 3 + 1;
                var endMonth = quarter * 3;
                
                var quarterTrades = _realizedTrades.Where(t => 
                    t.Date.Year == year && 
                    t.Date.Month >= startMonth && 
                    t.Date.Month <= endMonth).ToList();
                
                var quarterPnL = quarterTrades.Sum(t => t.RealizedPnLAmount);
                quarterlyPnL[$"Q{quarter}"] = quarterPnL;
            }
            
            return quarterlyPnL;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get quarterly P&L");
            throw;
        }
    }
    
    public async Task<Dictionary<string, decimal>> GetYearlyPnLAsync()
    {
        try
        {
            var yearlyPnL = new Dictionary<string, decimal>();
            var years = _realizedTrades.Select(t => t.Date.Year).Distinct().OrderBy(y => y);
            
            foreach (var year in years)
            {
                var yearTrades = _realizedTrades.Where(t => t.Date.Year == year).ToList();
                var yearPnL = yearTrades.Sum(t => t.RealizedPnLAmount);
                yearlyPnL[year.ToString()] = yearPnL;
            }
            
            return yearlyPnL;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get yearly P&L");
            throw;
        }
    }
    
    public async Task<Dictionary<string, decimal>> GetRollingReturnsAsync()
    {
        try
        {
            var rollingReturns = new Dictionary<string, decimal>();
            var performanceHistory = _performanceHistory.OrderBy(p => p.Date).ToList();
            
            if (performanceHistory.Count < 30) return rollingReturns;
            
            // 30-day rolling return
            var thirtyDaysAgo = DateTime.Today.AddDays(-30);
            var thirtyDayPoint = performanceHistory.FirstOrDefault(p => p.Date >= thirtyDaysAgo);
            if (thirtyDayPoint != null)
            {
                var currentValue = performanceHistory.Last().PortfolioValue;
                var thirtyDayValue = thirtyDayPoint.PortfolioValue;
                rollingReturns["30Day"] = (currentValue - thirtyDayValue) / thirtyDayValue * 100;
            }
            
            // 90-day rolling return
            var ninetyDaysAgo = DateTime.Today.AddDays(-90);
            var ninetyDayPoint = performanceHistory.FirstOrDefault(p => p.Date >= ninetyDaysAgo);
            if (ninetyDayPoint != null)
            {
                var currentValue = performanceHistory.Last().PortfolioValue;
                var ninetyDayValue = ninetyDayPoint.PortfolioValue;
                rollingReturns["90Day"] = (currentValue - ninetyDayValue) / ninetyDayValue * 100;
            }
            
            // 1-year rolling return
            var oneYearAgo = DateTime.Today.AddDays(-365);
            var oneYearPoint = performanceHistory.FirstOrDefault(p => p.Date >= oneYearAgo);
            if (oneYearPoint != null)
            {
                var currentValue = performanceHistory.Last().PortfolioValue;
                var oneYearValue = oneYearPoint.PortfolioValue;
                rollingReturns["1Year"] = (currentValue - oneYearValue) / oneYearValue * 100;
            }
            
            return rollingReturns;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to calculate rolling returns");
            throw;
        }
    }
    
    private void InitializeSampleData()
    {
        // Initialize with sample performance history
        var startDate = DateTime.Today.AddDays(-365);
        var currentValue = 83615.00m; // Current portfolio value
        var spyValue = 500.00m; // Sample SPY value
        
        for (int i = 0; i < 365; i++)
        {
            var date = startDate.AddDays(i);
            var portfolioValue = currentValue * (1 + (decimal)(i * 0.0001)); // Simulate growth
            var spyReturn = (decimal)(i * 0.00008); // Simulate SPY growth
            
            _performanceHistory.Add(new PortfolioPerformancePoint
            {
                Date = date,
                PortfolioValue = portfolioValue,
                SPYValue = spyValue * (1 + spyReturn),
                PortfolioReturn = (portfolioValue - currentValue) / currentValue * 100,
                SPYReturn = spyReturn * 100,
                ExcessReturn = ((portfolioValue - currentValue) / currentValue - spyReturn) * 100,
                Drawdown = CalculateDrawdown(portfolioValue, currentValue),
                Rolling30DayReturn = i >= 30 ? (portfolioValue - _performanceHistory[i - 30].PortfolioValue) / _performanceHistory[i - 30].PortfolioValue * 100 : 0
            });
        }
        
        // Initialize with sample realized trades
        _realizedTrades.AddRange(new List<RealizedPnL>
        {
            new RealizedPnL
            {
                Date = DateTime.Today.AddDays(-30),
                Symbol = "NVDA",
                PositionType = "PUT",
                Strike = 150,
                Expiry = DateTime.Today.AddDays(-5),
                EntryPrice = 5.00m,
                ExitPrice = 0.50m,
                Quantity = 1,
                RealizedPnLAmount = 450.00m,
                RealizedPnLPercent = 90.0m,
                CloseReason = "Closed",
                HoldDuration = TimeSpan.FromDays(25),
                MaxProfit = 500.00m,
                MaxLoss = 0.00m
            },
            new RealizedPnL
            {
                Date = DateTime.Today.AddDays(-15),
                Symbol = "XOM",
                PositionType = "CALL",
                Strike = 110,
                Expiry = DateTime.Today.AddDays(-2),
                EntryPrice = 2.50m,
                ExitPrice = 0.10m,
                Quantity = 1,
                RealizedPnLAmount = -240.00m,
                RealizedPnLPercent = -96.0m,
                CloseReason = "Expired",
                HoldDuration = TimeSpan.FromDays(13),
                MaxProfit = 50.00m,
                MaxLoss = -240.00m
            }
        });
    }
    
    private decimal CalculateDrawdown(decimal currentValue, decimal peakValue)
    {
        if (currentValue >= peakValue) return 0;
        return (peakValue - currentValue) / peakValue * 100;
    }
    
    private decimal CalculateSharpeRatio(List<PortfolioPerformancePoint> performanceHistory)
    {
        if (performanceHistory.Count < 2) return 0;
        
        var returns = performanceHistory
            .OrderBy(p => p.Date)
            .Select((p, i) => i > 0 ? (p.PortfolioValue - performanceHistory[i - 1].PortfolioValue) / performanceHistory[i - 1].PortfolioValue : 0m)
            .Where(r => r != 0)
            .ToList();
        
        if (!returns.Any()) return 0;
        
        var averageReturn = returns.Average();
        var variance = returns.Select(r => (r - averageReturn) * (r - averageReturn)).Average();
        var standardDeviation = (decimal)Math.Sqrt((double)variance);
        
        return standardDeviation != 0 ? averageReturn / standardDeviation : 0;
    }
    
    private string GetMonthName(int month)
    {
        return month switch
        {
            1 => "January",
            2 => "February",
            3 => "March",
            4 => "April",
            5 => "May",
            6 => "June",
            7 => "July",
            8 => "August",
            9 => "September",
            10 => "October",
            11 => "November",
            12 => "December",
            _ => "Unknown"
        };
    }
} 