using System.Text.Json.Serialization;

namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents a complete wheel cycle position
/// </summary>
public class WheelPosition
{
    public string Symbol { get; set; } = string.Empty;
    public List<decimal> PutStrikes { get; set; } = new();
    public List<decimal> PutCredits { get; set; } = new();
    public List<int> PutQuantities { get; set; } = new(); // Track quantities for each put strike
    public List<string> PutExpiries { get; set; } = new(); // Expiry dates for puts
    public List<int> PutDTEs { get; set; } = new(); // Days to expiration for puts
    public List<decimal> PutPremiums { get; set; } = new(); // Current premiums for puts
    public List<decimal> PutDeltas { get; set; } = new(); // Delta values for puts
    public List<decimal> PutPnLPercentages { get; set; } = new(); // P&L% for puts
    public decimal? AssignmentPrice { get; set; }
    public int SharesOwned { get; set; }
    public decimal? StockPrice { get; set; } // Current stock price
    public List<decimal>? CallStrikes { get; set; }
    public List<decimal>? CallCredits { get; set; }
    public List<int>? CallQuantities { get; set; } // Track quantities for each call strike
    public List<string>? CallExpiries { get; set; } // Expiry dates for calls
    public List<int>? CallDTEs { get; set; } // Days to expiration for calls
    public List<decimal>? CallPremiums { get; set; } // Current premiums for calls
    public List<decimal>? CallDeltas { get; set; } // Delta values for calls
    public List<decimal>? CallPnLPercentages { get; set; } // P&L% for calls
    public decimal TotalCredits { get; set; }
    public decimal CostBasis { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? LastUpdated { get; set; }
    
    [JsonIgnore]
    public decimal TotalPutCredits => PutCredits.Sum();
    
    [JsonIgnore]
    public decimal TotalCallCredits => CallCredits?.Sum() ?? 0;
    
    [JsonIgnore]
    public decimal TotalIncome => TotalPutCredits + TotalCallCredits;
    
    [JsonIgnore]
    public bool HasShares => SharesOwned > 0;
    
    [JsonIgnore]
    public bool HasActivePuts => PutStrikes.Count > 0;
    
    [JsonIgnore]
    public bool HasActiveCalls => CallStrikes?.Count > 0;
} 