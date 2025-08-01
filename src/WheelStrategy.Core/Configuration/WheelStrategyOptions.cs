namespace WheelStrategy.Core.Configuration;

/// <summary>
/// Wheel strategy configuration options
/// </summary>
public class WheelStrategyOptions
{
    public const string SectionName = "WheelStrategy";
    
    /// <summary>
    /// IBKR connection settings
    /// </summary>
    public IBKROptions IBKR { get; set; } = new();
    
    /// <summary>
    /// Risk management thresholds
    /// </summary>
    public RiskThresholds RiskThresholds { get; set; } = new();
    
    /// <summary>
    /// Trading symbols to monitor
    /// </summary>
    public List<string> Watchlist { get; set; } = new();
    
    /// <summary>
    /// Alert configuration
    /// </summary>
    public AlertOptions Alerts { get; set; } = new();
    
    /// <summary>
    /// Dashboard configuration
    /// </summary>
    public DashboardOptions Dashboard { get; set; } = new();
}

/// <summary>
/// IBKR connection options
/// </summary>
public class IBKROptions
{
    public string Host { get; set; } = "127.0.0.1";
    public int Port { get; set; } = 7496;
    public int ClientId { get; set; } = 1;
    public bool UsePaperTrading { get; set; } = true;
    public int ConnectionTimeout { get; set; } = 30;
    public int ReconnectAttempts { get; set; } = 3;
}

/// <summary>
/// Risk management thresholds
/// </summary>
public class RiskThresholds
{
    public decimal MaxPositionPercentage { get; set; } = 0.10m; // 10%
    public decimal MaxSectorPercentage { get; set; } = 0.20m; // 20%
    public decimal DrawdownStop { get; set; } = 0.20m; // 20%
    public decimal WeeklyDrawdownStop { get; set; } = 0.10m; // 10%
    public decimal IVRankMinimum { get; set; } = 50m;
    public decimal IVMinimum { get; set; } = 20m;
    public decimal ProfitTarget { get; set; } = 0.50m; // 50%
    public decimal ProfitRoll { get; set; } = 0.80m; // 80%
    public int RollDTE { get; set; } = 21;
    public decimal RollDeltaThreshold { get; set; } = 0.50m;
    public int EarningsBufferDays { get; set; } = 7;
    public decimal CSPStopLossPercentage { get; set; } = 0.10m; // 10%
    public decimal SharesStopLossPercentage { get; set; } = 0.10m; // 10%
    public int MaxStrikesPerSymbol { get; set; } = 2;
    public decimal MinStrikeSeparation { get; set; } = 0.05m; // 5%
    public decimal CorrelationThreshold { get; set; } = 0.80m;
    public decimal CorrelationExtreme { get; set; } = 0.90m;
    public int WinStreakCaution { get; set; } = 10;
    public decimal MinLiquidityScore { get; set; } = 1000m;
}

/// <summary>
/// Alert configuration options
/// </summary>
public class AlertOptions
{
    public bool EnableEmail { get; set; } = false;
    public bool EnableSMS { get; set; } = false;
    public bool EnablePush { get; set; } = false;
    public string? EmailFrom { get; set; }
    public string? EmailTo { get; set; }
    public string? SmtpServer { get; set; }
    public int SmtpPort { get; set; } = 587;
    public string? SmtpPassword { get; set; }
    public string? TwilioAccountSid { get; set; }
    public string? TwilioAuthToken { get; set; }
    public string? TwilioFromNumber { get; set; }
    public string? TwilioToNumber { get; set; }
}

/// <summary>
/// Dashboard configuration options
/// </summary>
public class DashboardOptions
{
    public int Port { get; set; } = 7001;
    public string Host { get; set; } = "localhost";
    public int UpdateIntervalSeconds { get; set; } = 30;
    public bool EnableSignalR { get; set; } = true;
    public bool EnableCORS { get; set; } = true;
} 