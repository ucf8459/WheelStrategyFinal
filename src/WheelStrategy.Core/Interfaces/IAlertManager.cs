using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Alert management interface
/// </summary>
public interface IAlertManager
{
    /// <summary>
    /// Sends an alert
    /// </summary>
    Task SendAlertAsync(Alert alert);
    
    /// <summary>
    /// Sends a critical alert
    /// </summary>
    Task SendCriticalAlertAsync(string title, string message, string? actionRequired = null);
    
    /// <summary>
    /// Sends an important alert
    /// </summary>
    Task SendImportantAlertAsync(string title, string message, string? actionRequired = null);
    
    /// <summary>
    /// Sends an info alert
    /// </summary>
    Task SendInfoAlertAsync(string title, string message);
    
    /// <summary>
    /// Gets recent alerts
    /// </summary>
    Task<List<Alert>> GetRecentAlertsAsync(int count = 50);
    
    /// <summary>
    /// Marks an alert as read
    /// </summary>
    Task MarkAlertAsReadAsync(string alertId);
    
    /// <summary>
    /// Sends a screener report
    /// </summary>
    Task SendScreenerReportAsync(string reportType, List<OptionOpportunity> opportunities, Dictionary<string, object> sectorAnalysis, Dictionary<string, object> summaryStats);
} 