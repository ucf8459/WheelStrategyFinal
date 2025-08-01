namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents a trading decision
/// </summary>
public class Decision
{
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public string Symbol { get; set; } = string.Empty;
    public string ActionType { get; set; } = string.Empty; // ROLL, CLOSE, OPEN, ADJUST
    public string Reason { get; set; } = string.Empty;
    public string Priority { get; set; } = string.Empty; // CRITICAL, IMPORTANT, ROUTINE
    public bool Executed { get; set; }
    public string? Result { get; set; } // SUCCESS, FAILED, PARTIAL
    public string? Notes { get; set; }
    public decimal? PnL { get; set; }
    public Dictionary<string, object>? Metadata { get; set; }
} 