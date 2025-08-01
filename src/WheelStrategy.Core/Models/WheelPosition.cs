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
    public decimal? AssignmentPrice { get; set; }
    public int SharesOwned { get; set; }
    public List<decimal>? CallStrikes { get; set; }
    public List<decimal>? CallCredits { get; set; }
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