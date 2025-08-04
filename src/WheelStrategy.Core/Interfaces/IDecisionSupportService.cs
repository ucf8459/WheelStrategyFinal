using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Service for managing decision support and tracking
/// </summary>
public interface IDecisionSupportService
{
    /// <summary>
    /// Gets the current decision support summary
    /// </summary>
    Task<DecisionSupportSummary> GetDecisionSupportSummaryAsync();
    
    /// <summary>
    /// Records a decision made today
    /// </summary>
    Task RecordDecisionAsync(string decision, string category);
    
    /// <summary>
    /// Analyzes positions and generates decision items
    /// </summary>
    Task<List<DecisionItem>> AnalyzePositionsForDecisionsAsync();
    
    /// <summary>
    /// Gets upcoming expirations within the next 7 days
    /// </summary>
    Task<List<UpcomingExpiration>> GetUpcomingExpirationsAsync();
    
    /// <summary>
    /// Resets the daily decision counter (called at midnight)
    /// </summary>
    Task ResetDailyDecisionCounterAsync();
    
    /// <summary>
    /// Gets the current decision count for today
    /// </summary>
    Task<int> GetDecisionsUsedTodayAsync();
} 