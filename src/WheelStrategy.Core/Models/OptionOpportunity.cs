namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents a wheel strategy opportunity
/// </summary>
public class OptionOpportunity
{
    public string Symbol { get; set; } = string.Empty;
    public decimal Strike { get; set; }
    public decimal Premium { get; set; }
    public int DaysToExpiration { get; set; }
    public string Expiry { get; set; } = string.Empty;
    public decimal AnnualReturn { get; set; }
    public decimal IVRank { get; set; }
    public decimal CurrentIV { get; set; }
    public decimal Moneyness { get; set; }
    public decimal CurrentPrice { get; set; }
    public string Sector { get; set; } = string.Empty;
    public decimal LiquidityScore { get; set; }
    public decimal PositionSizeAdjustment { get; set; } = 1.0m;
    public Dictionary<string, object>? Criteria { get; set; }
    public List<string> Issues { get; set; } = new();
    public bool MeetsCriteria { get; set; }
} 