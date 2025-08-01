using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Interfaces;

/// <summary>
/// Wheel strategy opportunity scanner interface
/// </summary>
public interface IWheelScanner
{
    /// <summary>
    /// Scans for wheel opportunities
    /// </summary>
    Task<List<OptionOpportunity>> ScanOpportunitiesAsync();
    
    /// <summary>
    /// Scans all opportunities without filtering
    /// </summary>
    Task<List<OptionOpportunity>> ScanAllOpportunitiesAsync();
    
    /// <summary>
    /// Gets opportunities for a specific sector
    /// </summary>
    Task<List<OptionOpportunity>> GetSectorOpportunitiesAsync(string sector);
    
    /// <summary>
    /// Gets sector gaps (underweight sectors)
    /// </summary>
    Task<List<Dictionary<string, object>>> GetSectorGapsAsync();
    
    /// <summary>
    /// Detects sector rotation patterns
    /// </summary>
    Task<List<Dictionary<string, object>>> DetectSectorRotationAsync();
} 