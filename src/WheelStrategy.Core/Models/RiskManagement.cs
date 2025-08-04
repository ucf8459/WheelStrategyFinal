namespace WheelStrategy.Core.Models;

/// <summary>
/// Represents a risk alert
/// </summary>
public enum RiskAlertType
{
    PositionSize,
    Correlation,
    SectorConcentration,
    DeltaExposure,
    ExpirationRisk,
    VolatilitySpike,
    MarginCall
}

/// <summary>
/// Represents a risk alert
/// </summary>
public class RiskAlert
{
    public RiskAlertType Type { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string Symbol { get; set; } = string.Empty;
    public decimal CurrentValue { get; set; }
    public decimal ThresholdValue { get; set; }
    public decimal RiskPercentage { get; set; }
    public string Recommendation { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public bool IsAcknowledged { get; set; }
    public RiskAlertSeverity Severity { get; set; }
}

/// <summary>
/// Represents risk alert severity
/// </summary>
public enum RiskAlertSeverity
{
    Low,
    Medium,
    High,
    Critical
}

/// <summary>
/// Represents position sizing analysis
/// </summary>
public class PositionSizingAnalysis
{
    public string Symbol { get; set; } = string.Empty;
    public decimal CurrentPositionSize { get; set; }
    public decimal RecommendedPositionSize { get; set; }
    public decimal MaxPositionSize { get; set; }
    public decimal PortfolioWeight { get; set; }
    public decimal RiskPerPosition { get; set; }
    public decimal MaxRiskPerPosition { get; set; }
    public bool IsOverSized { get; set; }
    public string Recommendation { get; set; } = string.Empty;
}

/// <summary>
/// Represents correlation analysis
/// </summary>
public class CorrelationAnalysis
{
    public string Symbol1 { get; set; } = string.Empty;
    public string Symbol2 { get; set; } = string.Empty;
    public decimal Correlation { get; set; }
    public bool IsHighCorrelation { get; set; }
    public string RiskLevel { get; set; } = string.Empty; // Low, Medium, High
    public string Recommendation { get; set; } = string.Empty;
}

/// <summary>
/// Represents sector concentration analysis
/// </summary>
public class SectorConcentrationAnalysis
{
    public string Sector { get; set; } = string.Empty;
    public decimal TotalValue { get; set; }
    public decimal PortfolioWeight { get; set; }
    public decimal MaxAllowedWeight { get; set; }
    public bool IsOverConcentrated { get; set; }
    public List<string> Symbols { get; set; } = new();
    public string Recommendation { get; set; } = string.Empty;
}

/// <summary>
/// Represents delta exposure analysis
/// </summary>
public class DeltaExposureAnalysis
{
    public decimal TotalDelta { get; set; }
    public decimal LongDelta { get; set; }
    public decimal ShortDelta { get; set; }
    public decimal NetDelta { get; set; }
    public decimal MaxAllowedDelta { get; set; }
    public bool IsOverExposed { get; set; }
    public string Recommendation { get; set; } = string.Empty;
}

/// <summary>
/// Represents risk management summary
/// </summary>
public class RiskManagementSummary
{
    public List<RiskAlert> ActiveAlerts { get; set; } = new();
    public List<PositionSizingAnalysis> PositionSizing { get; set; } = new();
    public List<CorrelationAnalysis> Correlations { get; set; } = new();
    public List<SectorConcentrationAnalysis> SectorConcentration { get; set; } = new();
    public DeltaExposureAnalysis DeltaExposure { get; set; } = new();
    public decimal TotalPortfolioRisk { get; set; }
    public decimal MaxAllowedRisk { get; set; }
    public bool IsWithinRiskLimits { get; set; }
    public string OverallRiskLevel { get; set; } = string.Empty; // Low, Medium, High, Critical
} 