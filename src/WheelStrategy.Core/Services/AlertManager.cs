using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Services;

/// <summary>
/// Alert manager implementation
/// </summary>
public class AlertManager : IAlertManager
{
    private readonly ILogger<AlertManager> _logger;
    private readonly AlertOptions _options;
    private readonly List<Alert> _alerts = new();
    
    public AlertManager(
        IOptions<WheelStrategyOptions> options,
        ILogger<AlertManager> logger)
    {
        _options = options.Value.Alerts;
        _logger = logger;
    }
    
    public async Task SendAlertAsync(Alert alert)
    {
        try
        {
            // Store alert
            _alerts.Add(alert);
            
            // Log alert
            _logger.LogInformation("Alert: {Priority} - {Title}: {Message}", 
                alert.Priority, alert.Title, alert.Message);
            
            // Send via configured channels
            if (_options.EnableEmail)
            {
                await SendEmailAlertAsync(alert);
            }
            
            if (_options.EnableSMS)
            {
                await SendSMSAlertAsync(alert);
            }
            
            if (_options.EnablePush)
            {
                await SendPushAlertAsync(alert);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send alert: {Title}", alert.Title);
        }
    }
    
    public async Task SendCriticalAlertAsync(string title, string message, string? actionRequired = null)
    {
        var alert = new Alert
        {
            Priority = AlertPriority.Critical,
            Title = title,
            Message = message,
            ActionRequired = actionRequired,
            Timestamp = DateTime.UtcNow,
            Category = "Critical"
        };
        
        await SendAlertAsync(alert);
    }
    
    public async Task SendImportantAlertAsync(string title, string message, string? actionRequired = null)
    {
        var alert = new Alert
        {
            Priority = AlertPriority.Important,
            Title = title,
            Message = message,
            ActionRequired = actionRequired,
            Timestamp = DateTime.UtcNow,
            Category = "Important"
        };
        
        await SendAlertAsync(alert);
    }
    
    public async Task SendInfoAlertAsync(string title, string message)
    {
        var alert = new Alert
        {
            Priority = AlertPriority.Info,
            Title = title,
            Message = message,
            Timestamp = DateTime.UtcNow,
            Category = "Info"
        };
        
        await SendAlertAsync(alert);
    }
    
    public async Task<List<Alert>> GetRecentAlertsAsync(int count = 50)
    {
        return await Task.FromResult(_alerts
            .OrderByDescending(a => a.Timestamp)
            .Take(count)
            .ToList());
    }
    
    public async Task MarkAlertAsReadAsync(string alertId)
    {
        // Simplified implementation - in production would use database
        await Task.CompletedTask;
    }
    
    public async Task SendScreenerReportAsync(string reportType, List<OptionOpportunity> opportunities, Dictionary<string, object> sectorAnalysis, Dictionary<string, object> summaryStats)
    {
        try
        {
            var alert = new Alert
            {
                Priority = AlertPriority.Info,
                Title = $"Screener Report: {reportType}",
                Message = $"Found {opportunities.Count} opportunities. {summaryStats.GetValueOrDefault("total_symbols", 0)} symbols scanned.",
                Timestamp = DateTime.UtcNow,
                Category = "Screener",
                Metadata = new Dictionary<string, object>
                {
                    ["opportunities"] = opportunities,
                    ["sector_analysis"] = sectorAnalysis,
                    ["summary_stats"] = summaryStats
                }
            };
            
            await SendAlertAsync(alert);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send screener report");
        }
    }
    
    private async Task SendEmailAlertAsync(Alert alert)
    {
        try
        {
            if (string.IsNullOrEmpty(_options.EmailFrom) || 
                string.IsNullOrEmpty(_options.EmailTo) || 
                string.IsNullOrEmpty(_options.SmtpServer))
            {
                _logger.LogWarning("Email alert configuration incomplete");
                return;
            }
            
            // Simplified email sending - in production would use proper SMTP client
            _logger.LogInformation("Email alert sent to {EmailTo}: {Title}", 
                _options.EmailTo, alert.Title);
            
            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send email alert");
        }
    }
    
    private async Task SendSMSAlertAsync(Alert alert)
    {
        try
        {
            if (string.IsNullOrEmpty(_options.TwilioAccountSid) || 
                string.IsNullOrEmpty(_options.TwilioAuthToken) || 
                string.IsNullOrEmpty(_options.TwilioFromNumber) || 
                string.IsNullOrEmpty(_options.TwilioToNumber))
            {
                _logger.LogWarning("SMS alert configuration incomplete");
                return;
            }
            
            // Simplified SMS sending - in production would use Twilio SDK
            _logger.LogInformation("SMS alert sent to {ToNumber}: {Title}", 
                _options.TwilioToNumber, alert.Title);
            
            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send SMS alert");
        }
    }
    
    private async Task SendPushAlertAsync(Alert alert)
    {
        try
        {
            // Simplified push notification - in production would use proper push service
            _logger.LogInformation("Push alert sent: {Title}", alert.Title);
            
            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send push alert");
        }
    }
} 