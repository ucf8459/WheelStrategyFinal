namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents an alert priority level
/// </summary>
public enum AlertPriority
{
    Info,
    Important,
    Critical
}

/// <summary>
/// Represents a system alert
/// </summary>
public class Alert
{
    public AlertPriority Priority { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public string? ActionRequired { get; set; }
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public bool IsRead { get; set; }
    public string? Category { get; set; }
    public Dictionary<string, object>? Metadata { get; set; }
} 