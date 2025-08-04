namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents a decision priority level
/// </summary>
public enum DecisionPriority
{
    Info,
    Important,
    Critical
}

/// <summary>
/// Represents a decision item in the support system
/// </summary>
public class DecisionItem
{
    public DecisionPriority Priority { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string? ActionRequired { get; set; }
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public bool IsCompleted { get; set; }
    public string? Category { get; set; }
    public Dictionary<string, object>? Metadata { get; set; }
    public string? Symbol { get; set; }
    public string? PositionType { get; set; }
    public decimal? Strike { get; set; }
    public DateTime? Expiry { get; set; }
    public int? DTE { get; set; }
    public decimal? Delta { get; set; }
    public decimal? PnLPercent { get; set; }
}

/// <summary>
/// Represents an upcoming expiration
/// </summary>
public class UpcomingExpiration
{
    public string Symbol { get; set; } = string.Empty;
    public DateTime Expiry { get; set; }
    public decimal Strike { get; set; }
    public string PositionType { get; set; } = string.Empty;
    public decimal CurrentPrice { get; set; }
    public string Status { get; set; } = string.Empty; // Safe OTM, At Risk, ITM
    public string Recommendation { get; set; } = string.Empty;
    public int DTE { get; set; }
    public decimal Delta { get; set; }
    public decimal PnLPercent { get; set; }
}

/// <summary>
/// Represents the decision support summary
/// </summary>
public class DecisionSupportSummary
{
    public int MaxDecisionsToday { get; set; } = 3;
    public int DecisionsUsedToday { get; set; }
    public DateTime LastResetDate { get; set; }
    public List<DecisionItem> CriticalDecisions { get; set; } = new();
    public List<DecisionItem> ImportantDecisions { get; set; } = new();
    public List<DecisionItem> InfoDecisions { get; set; } = new();
    public List<UpcomingExpiration> UpcomingExpirations { get; set; } = new();
    public bool IsDecisionLimitReached => DecisionsUsedToday >= MaxDecisionsToday;
} 