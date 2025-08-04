using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Service for risk management and analysis
/// </summary>
public interface IRiskManagementService
{
    /// <summary>
    /// Gets the complete risk management summary
    /// </summary>
    Task<RiskManagementSummary> GetRiskManagementSummaryAsync();
    
    /// <summary>
    /// Analyzes position sizing for all positions
    /// </summary>
    Task<List<PositionSizingAnalysis>> AnalyzePositionSizingAsync();
    
    /// <summary>
    /// Analyzes correlations between positions
    /// </summary>
    Task<List<CorrelationAnalysis>> AnalyzeCorrelationsAsync();
    
    /// <summary>
    /// Analyzes sector concentration
    /// </summary>
    Task<List<SectorConcentrationAnalysis>> AnalyzeSectorConcentrationAsync();
    
    /// <summary>
    /// Analyzes delta exposure
    /// </summary>
    Task<DeltaExposureAnalysis> AnalyzeDeltaExposureAsync();
    
    /// <summary>
    /// Gets active risk alerts
    /// </summary>
    Task<List<RiskAlert>> GetActiveRiskAlertsAsync();
    
    /// <summary>
    /// Acknowledges a risk alert
    /// </summary>
    Task AcknowledgeRiskAlertAsync(string alertId);
    
    /// <summary>
    /// Calculates portfolio risk metrics
    /// </summary>
    Task<Dictionary<string, decimal>> CalculateRiskMetricsAsync();
    
    /// <summary>
    /// Checks if portfolio is within risk limits
    /// </summary>
    Task<bool> IsWithinRiskLimitsAsync();
    
    /// <summary>
    /// Gets recommended position sizes
    /// </summary>
    Task<Dictionary<string, decimal>> GetRecommendedPositionSizesAsync();
} 