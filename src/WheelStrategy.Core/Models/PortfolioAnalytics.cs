namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents a portfolio performance data point
/// </summary>
public class PortfolioPerformancePoint
{
    public DateTime Date { get; set; }
    public decimal PortfolioValue { get; set; }
    public decimal SPYValue { get; set; }
    public decimal PortfolioReturn { get; set; }
    public decimal SPYReturn { get; set; }
    public decimal ExcessReturn { get; set; }
    public decimal Drawdown { get; set; }
    public decimal Rolling30DayReturn { get; set; }
}

/// <summary>
/// Represents realized P&L data
/// </summary>
public class RealizedPnL
{
    public DateTime Date { get; set; }
    public string Symbol { get; set; } = string.Empty;
    public string PositionType { get; set; } = string.Empty; // PUT, CALL, STOCK
    public decimal Strike { get; set; }
    public DateTime Expiry { get; set; }
    public decimal EntryPrice { get; set; }
    public decimal ExitPrice { get; set; }
    public decimal Quantity { get; set; }
    public decimal RealizedPnLAmount { get; set; }
    public decimal RealizedPnLPercent { get; set; }
    public string CloseReason { get; set; } = string.Empty; // Expired, Closed, Assigned, Rolled
    public TimeSpan HoldDuration { get; set; }
    public decimal MaxProfit { get; set; }
    public decimal MaxLoss { get; set; }
}

/// <summary>
/// Represents portfolio analytics summary
/// </summary>
public class PortfolioAnalyticsSummary
{
    public decimal TotalRealizedPnL { get; set; }
    public decimal TotalUnrealizedPnL { get; set; }
    public decimal TotalPnL { get; set; }
    public decimal WinRate { get; set; }
    public decimal AverageWin { get; set; }
    public decimal AverageLoss { get; set; }
    public decimal ProfitFactor { get; set; }
    public decimal MaxDrawdown { get; set; }
    public decimal SharpeRatio { get; set; }
    public decimal Rolling30DayReturn { get; set; }
    public decimal Rolling90DayReturn { get; set; }
    public decimal Rolling1YearReturn { get; set; }
    public List<PortfolioPerformancePoint> PerformanceHistory { get; set; } = new();
    public List<RealizedPnL> RecentTrades { get; set; } = new();
    public Dictionary<string, decimal> MonthlyPnL { get; set; } = new();
    public Dictionary<string, decimal> QuarterlyPnL { get; set; } = new();
    public Dictionary<string, decimal> YearlyPnL { get; set; } = new();
}

/// <summary>
/// Represents a drawdown period
/// </summary>
public class DrawdownPeriod
{
    public DateTime PeakDate { get; set; }
    public DateTime TroughDate { get; set; }
    public DateTime? RecoveryDate { get; set; }
    public decimal PeakValue { get; set; }
    public decimal TroughValue { get; set; }
    public decimal DrawdownAmount { get; set; }
    public decimal DrawdownPercent { get; set; }
    public TimeSpan Duration { get; set; }
    public TimeSpan? RecoveryDuration { get; set; }
}

/// <summary>
/// Represents performance attribution by strategy
/// </summary>
public class StrategyPerformance
{
    public string Strategy { get; set; } = string.Empty; // Wheel, Covered Calls, Cash Secured Puts
    public decimal TotalPnL { get; set; }
    public decimal WinRate { get; set; }
    public int TotalTrades { get; set; }
    public int WinningTrades { get; set; }
    public decimal AverageReturn { get; set; }
    public decimal MaxDrawdown { get; set; }
    public decimal SharpeRatio { get; set; }
} 