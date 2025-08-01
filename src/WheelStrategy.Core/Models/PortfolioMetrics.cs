namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents portfolio performance metrics
/// </summary>
public class PortfolioMetrics
{
    public decimal AccountValue { get; set; }
    public decimal AvailableFunds { get; set; }
    public decimal UnrealizedPnL { get; set; }
    public decimal CashPercentage { get; set; }
    public decimal TotalIncome { get; set; }
    public decimal WinRate { get; set; }
    public decimal AverageReturn { get; set; }
    public decimal MaxDrawdown { get; set; }
    public decimal SharpeRatio { get; set; }
    public int TotalTrades { get; set; }
    public int WinningTrades { get; set; }
    public int LosingTrades { get; set; }
    public decimal VIXLevel { get; set; }
    public decimal VIXPercentile { get; set; }
    public string MarketRegime { get; set; } = string.Empty;
    public decimal Correlation { get; set; }
    public Dictionary<string, decimal> SectorAllocations { get; set; } = new();
    public DateTime LastUpdated { get; set; } = DateTime.UtcNow;
} 