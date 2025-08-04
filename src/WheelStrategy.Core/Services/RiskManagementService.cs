using Microsoft.Extensions.Logging;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;

namespace WheelStrategy.Core.Services;

/// <summary>
/// Service for risk management and analysis
/// </summary>
public class RiskManagementService : IRiskManagementService
{
    private readonly ILogger<RiskManagementService> _logger;
    private readonly IWheelMonitor _wheelMonitor;
    private readonly IMarketDataService _marketDataService;
    private readonly List<RiskAlert> _activeAlerts;
    
    // Risk limits configuration
    private const decimal MaxPositionSizePercent = 20.0m; // Max 20% per position
    private const decimal MaxSectorConcentration = 30.0m; // Max 30% per sector
    private const decimal MaxDeltaExposure = 100.0m; // Max 100 delta exposure
    private const decimal MaxCorrelation = 0.7m; // Max 70% correlation
    
    public RiskManagementService(
        ILogger<RiskManagementService> logger,
        IWheelMonitor wheelMonitor,
        IMarketDataService marketDataService)
    {
        _logger = logger;
        _wheelMonitor = wheelMonitor;
        _marketDataService = marketDataService;
        _activeAlerts = new List<RiskAlert>();
    }
    
    public async Task<RiskManagementSummary> GetRiskManagementSummaryAsync()
    {
        try
        {
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            
            var summary = new RiskManagementSummary
            {
                PositionSizing = await AnalyzePositionSizingAsync(),
                Correlations = await AnalyzeCorrelationsAsync(),
                SectorConcentration = await AnalyzeSectorConcentrationAsync(),
                DeltaExposure = await AnalyzeDeltaExposureAsync(),
                ActiveAlerts = await GetActiveRiskAlertsAsync()
            };
            
            // Calculate overall risk metrics
            var riskMetrics = await CalculateRiskMetricsAsync();
            summary.TotalPortfolioRisk = riskMetrics.GetValueOrDefault("TotalRisk", 0);
            summary.MaxAllowedRisk = 100.0m; // 100% max risk
            summary.IsWithinRiskLimits = await IsWithinRiskLimitsAsync();
            
            // Determine overall risk level
            summary.OverallRiskLevel = DetermineOverallRiskLevel(summary);
            
            _logger.LogInformation("Generated risk management summary with {AlertCount} alerts, risk level: {RiskLevel}",
                summary.ActiveAlerts.Count, summary.OverallRiskLevel);
            
            return summary;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get risk management summary");
            throw;
        }
    }
    
    public async Task<List<PositionSizingAnalysis>> AnalyzePositionSizingAsync()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            var analyses = new List<PositionSizingAnalysis>();
            
            foreach (var position in positions)
            {
                var totalPositionValue = CalculatePositionValue(position);
                var portfolioWeight = (totalPositionValue / metrics.AccountValue) * 100;
                var maxPositionSize = metrics.AccountValue * (MaxPositionSizePercent / 100);
                var recommendedPositionSize = metrics.AccountValue * 0.05m; // 5% recommended
                
                var analysis = new PositionSizingAnalysis
                {
                    Symbol = position.Symbol,
                    CurrentPositionSize = totalPositionValue,
                    RecommendedPositionSize = recommendedPositionSize,
                    MaxPositionSize = maxPositionSize,
                    PortfolioWeight = portfolioWeight,
                    RiskPerPosition = portfolioWeight,
                    MaxRiskPerPosition = MaxPositionSizePercent,
                    IsOverSized = portfolioWeight > MaxPositionSizePercent,
                    Recommendation = portfolioWeight > MaxPositionSizePercent 
                        ? $"Reduce position size. Currently {portfolioWeight:F1}% of portfolio, max allowed {MaxPositionSizePercent}%"
                        : "Position size is within acceptable limits"
                };
                
                analyses.Add(analysis);
            }
            
            _logger.LogInformation("Analyzed position sizing for {PositionCount} positions", analyses.Count);
            return analyses;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to analyze position sizing");
            throw;
        }
    }
    
    public async Task<List<CorrelationAnalysis>> AnalyzeCorrelationsAsync()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            var correlations = new List<CorrelationAnalysis>();
            
            // Generate sample correlations (in real implementation, this would use historical data)
            var symbols = positions.Select(p => p.Symbol).ToList();
            
            for (int i = 0; i < symbols.Count; i++)
            {
                for (int j = i + 1; j < symbols.Count; j++)
                {
                    var correlation = CalculateCorrelation(symbols[i], symbols[j]);
                    var isHighCorrelation = Math.Abs(correlation) > MaxCorrelation;
                    
                    var analysis = new CorrelationAnalysis
                    {
                        Symbol1 = symbols[i],
                        Symbol2 = symbols[j],
                        Correlation = correlation,
                        IsHighCorrelation = isHighCorrelation,
                        RiskLevel = isHighCorrelation ? "High" : "Low",
                        Recommendation = isHighCorrelation 
                            ? $"High correlation ({correlation:F2}). Consider diversifying positions."
                            : "Correlation is within acceptable limits"
                    };
                    
                    correlations.Add(analysis);
                }
            }
            
            _logger.LogInformation("Analyzed correlations for {CorrelationCount} pairs", correlations.Count);
            return correlations;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to analyze correlations");
            throw;
        }
    }
    
    public async Task<List<SectorConcentrationAnalysis>> AnalyzeSectorConcentrationAsync()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            var sectorAnalysis = new List<SectorConcentrationAnalysis>();
            
            // Group positions by sector (simplified sector mapping)
            var sectorGroups = positions.GroupBy(p => GetSector(p.Symbol)).ToList();
            
            foreach (var group in sectorGroups)
            {
                var sector = group.Key;
                var totalValue = group.Sum(p => CalculatePositionValue(p));
                var portfolioWeight = (totalValue / metrics.AccountValue) * 100;
                var symbols = group.Select(p => p.Symbol).ToList();
                
                var analysis = new SectorConcentrationAnalysis
                {
                    Sector = sector,
                    TotalValue = totalValue,
                    PortfolioWeight = portfolioWeight,
                    MaxAllowedWeight = MaxSectorConcentration,
                    IsOverConcentrated = portfolioWeight > MaxSectorConcentration,
                    Symbols = symbols,
                    Recommendation = portfolioWeight > MaxSectorConcentration
                        ? $"Sector concentration {portfolioWeight:F1}% exceeds {MaxSectorConcentration}% limit. Consider reducing exposure."
                        : "Sector concentration is within acceptable limits"
                };
                
                sectorAnalysis.Add(analysis);
            }
            
            _logger.LogInformation("Analyzed sector concentration for {SectorCount} sectors", sectorAnalysis.Count);
            return sectorAnalysis;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to analyze sector concentration");
            throw;
        }
    }
    
    public async Task<DeltaExposureAnalysis> AnalyzeDeltaExposureAsync()
    {
        try
        {
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            var totalDelta = 0.0m;
            var longDelta = 0.0m;
            var shortDelta = 0.0m;
            
            foreach (var position in positions)
            {
                // Calculate delta for PUT positions (negative delta)
                foreach (var delta in position.PutDeltas)
                {
                    totalDelta += delta;
                    if (delta > 0)
                        longDelta += delta;
                    else
                        shortDelta += Math.Abs(delta);
                }
                
                // Calculate delta for CALL positions (positive delta)
                if (position.CallDeltas != null)
                {
                    foreach (var delta in position.CallDeltas)
                    {
                        totalDelta += delta;
                        if (delta > 0)
                            longDelta += delta;
                        else
                            shortDelta += Math.Abs(delta);
                    }
                }
                
                // Stock positions have delta of 1.0
                if (position.SharesOwned > 0)
                {
                    var stockDelta = position.SharesOwned;
                    totalDelta += stockDelta;
                    longDelta += stockDelta;
                }
            }
            
            var netDelta = longDelta - shortDelta;
            var isOverExposed = Math.Abs(netDelta) > MaxDeltaExposure;
            
            var analysis = new DeltaExposureAnalysis
            {
                TotalDelta = totalDelta,
                LongDelta = longDelta,
                ShortDelta = shortDelta,
                NetDelta = netDelta,
                MaxAllowedDelta = MaxDeltaExposure,
                IsOverExposed = isOverExposed,
                Recommendation = isOverExposed
                    ? $"Delta exposure {Math.Abs(netDelta):F1} exceeds {MaxDeltaExposure} limit. Consider hedging."
                    : "Delta exposure is within acceptable limits"
            };
            
            _logger.LogInformation("Analyzed delta exposure: Total={TotalDelta:F1}, Net={NetDelta:F1}", 
                analysis.TotalDelta, analysis.NetDelta);
            
            return analysis;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to analyze delta exposure");
            throw;
        }
    }
    
    public async Task<List<RiskAlert>> GetActiveRiskAlertsAsync()
    {
        try
        {
            // Generate risk alerts based on current analysis
            var alerts = new List<RiskAlert>();
            
            var positionSizing = await AnalyzePositionSizingAsync();
            var sectorConcentration = await AnalyzeSectorConcentrationAsync();
            var deltaExposure = await AnalyzeDeltaExposureAsync();
            
            // Position size alerts
            foreach (var analysis in positionSizing.Where(a => a.IsOverSized))
            {
                alerts.Add(new RiskAlert
                {
                    Type = RiskAlertType.PositionSize,
                    Title = $"Position Size Alert - {analysis.Symbol}",
                    Description = $"Position size {analysis.PortfolioWeight:F1}% exceeds {MaxPositionSizePercent}% limit",
                    Symbol = analysis.Symbol,
                    CurrentValue = analysis.PortfolioWeight,
                    ThresholdValue = MaxPositionSizePercent,
                    RiskPercentage = analysis.PortfolioWeight - MaxPositionSizePercent,
                    Recommendation = analysis.Recommendation,
                    Severity = analysis.PortfolioWeight > MaxPositionSizePercent * 1.5m ? RiskAlertSeverity.Critical : RiskAlertSeverity.High
                });
            }
            
            // Sector concentration alerts
            foreach (var analysis in sectorConcentration.Where(a => a.IsOverConcentrated))
            {
                alerts.Add(new RiskAlert
                {
                    Type = RiskAlertType.SectorConcentration,
                    Title = $"Sector Concentration Alert - {analysis.Sector}",
                    Description = $"Sector concentration {analysis.PortfolioWeight:F1}% exceeds {MaxSectorConcentration}% limit",
                    Symbol = string.Join(", ", analysis.Symbols),
                    CurrentValue = analysis.PortfolioWeight,
                    ThresholdValue = MaxSectorConcentration,
                    RiskPercentage = analysis.PortfolioWeight - MaxSectorConcentration,
                    Recommendation = analysis.Recommendation,
                    Severity = analysis.PortfolioWeight > MaxSectorConcentration * 1.5m ? RiskAlertSeverity.Critical : RiskAlertSeverity.High
                });
            }
            
            // Delta exposure alerts
            if (deltaExposure.IsOverExposed)
            {
                alerts.Add(new RiskAlert
                {
                    Type = RiskAlertType.DeltaExposure,
                    Title = "Delta Exposure Alert",
                    Description = $"Delta exposure {Math.Abs(deltaExposure.NetDelta):F1} exceeds {MaxDeltaExposure} limit",
                    Symbol = "PORTFOLIO",
                    CurrentValue = Math.Abs(deltaExposure.NetDelta),
                    ThresholdValue = MaxDeltaExposure,
                    RiskPercentage = (Math.Abs(deltaExposure.NetDelta) - MaxDeltaExposure) / MaxDeltaExposure * 100,
                    Recommendation = deltaExposure.Recommendation,
                    Severity = Math.Abs(deltaExposure.NetDelta) > MaxDeltaExposure * 1.5m ? RiskAlertSeverity.Critical : RiskAlertSeverity.High
                });
            }
            
            _logger.LogInformation("Generated {AlertCount} active risk alerts", alerts.Count);
            return alerts;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get active risk alerts");
            throw;
        }
    }
    
    public async Task AcknowledgeRiskAlertAsync(string alertId)
    {
        try
        {
            var alert = _activeAlerts.FirstOrDefault(a => a.Title.Contains(alertId));
            if (alert != null)
            {
                alert.IsAcknowledged = true;
                _logger.LogInformation("Acknowledged risk alert: {AlertTitle}", alert.Title);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to acknowledge risk alert");
            throw;
        }
    }
    
    public async Task<Dictionary<string, decimal>> CalculateRiskMetricsAsync()
    {
        try
        {
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            var positionSizing = await AnalyzePositionSizingAsync();
            var sectorConcentration = await AnalyzeSectorConcentrationAsync();
            var deltaExposure = await AnalyzeDeltaExposureAsync();
            
            var riskMetrics = new Dictionary<string, decimal>
            {
                ["TotalRisk"] = positionSizing.Sum(p => p.RiskPerPosition),
                ["MaxPositionRisk"] = positionSizing.Max(p => p.RiskPerPosition),
                ["SectorRisk"] = sectorConcentration.Sum(s => s.IsOverConcentrated ? s.PortfolioWeight - MaxSectorConcentration : 0),
                ["DeltaRisk"] = deltaExposure.IsOverExposed ? Math.Abs(deltaExposure.NetDelta) - MaxDeltaExposure : 0,
                ["PortfolioConcentration"] = positionSizing.Sum(p => p.PortfolioWeight),
                ["RiskScore"] = CalculateRiskScore(positionSizing, sectorConcentration, deltaExposure)
            };
            
            return riskMetrics;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to calculate risk metrics");
            throw;
        }
    }
    
    public async Task<bool> IsWithinRiskLimitsAsync()
    {
        try
        {
            var riskMetrics = await CalculateRiskMetricsAsync();
            var totalRisk = riskMetrics.GetValueOrDefault("TotalRisk", 0);
            var maxRisk = 100.0m;
            
            return totalRisk <= maxRisk;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to check risk limits");
            throw;
        }
    }
    
    public async Task<Dictionary<string, decimal>> GetRecommendedPositionSizesAsync()
    {
        try
        {
            var metrics = await _wheelMonitor.GetPortfolioMetricsAsync();
            var positions = await _wheelMonitor.GetWheelPositionsAsync();
            var recommendations = new Dictionary<string, decimal>();
            
            foreach (var position in positions)
            {
                var currentValue = CalculatePositionValue(position);
                var currentWeight = (currentValue / metrics.AccountValue) * 100;
                var recommendedWeight = Math.Min(5.0m, MaxPositionSizePercent); // 5% or max allowed
                var recommendedValue = metrics.AccountValue * (recommendedWeight / 100);
                
                recommendations[position.Symbol] = recommendedValue;
            }
            
            return recommendations;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get recommended position sizes");
            throw;
        }
    }
    
    private decimal CalculatePositionValue(WheelPosition position)
    {
        var stockValue = position.SharesOwned * (position.StockPrice ?? 0);
        var putValue = position.PutStrikes.Zip(position.PutQuantities, (strike, qty) => strike * qty).Sum();
        var callValue = position.CallStrikes?.Zip(position.CallQuantities ?? new List<int>(), (strike, qty) => strike * qty).Sum() ?? 0;
        
        return stockValue + putValue + callValue;
    }
    
    private decimal CalculateCorrelation(string symbol1, string symbol2)
    {
        // Simplified correlation calculation (in real implementation, this would use historical data)
        var random = new Random(symbol1.GetHashCode() + symbol2.GetHashCode());
        return (decimal)(random.NextDouble() * 2 - 1); // Random correlation between -1 and 1
    }
    
    private string GetSector(string symbol)
    {
        // Simplified sector mapping
        return symbol switch
        {
            "NVDA" => "Technology",
            "XOM" => "Energy",
            "DE" => "Industrials",
            "GOOG" => "Technology",
            "JPM" => "Financials",
            "UNH" => "Healthcare",
            _ => "Other"
        };
    }
    
    private string DetermineOverallRiskLevel(RiskManagementSummary summary)
    {
        var criticalAlerts = summary.ActiveAlerts.Count(a => a.Severity == RiskAlertSeverity.Critical);
        var highAlerts = summary.ActiveAlerts.Count(a => a.Severity == RiskAlertSeverity.High);
        var mediumAlerts = summary.ActiveAlerts.Count(a => a.Severity == RiskAlertSeverity.Medium);
        
        if (criticalAlerts > 0) return "Critical";
        if (highAlerts > 2) return "High";
        if (highAlerts > 0 || mediumAlerts > 3) return "Medium";
        return "Low";
    }
    
    private decimal CalculateRiskScore(List<PositionSizingAnalysis> positionSizing, List<SectorConcentrationAnalysis> sectorConcentration, DeltaExposureAnalysis deltaExposure)
    {
        var positionRisk = positionSizing.Sum(p => p.IsOverSized ? p.RiskPerPosition - MaxPositionSizePercent : 0);
        var sectorRisk = sectorConcentration.Sum(s => s.IsOverConcentrated ? s.PortfolioWeight - MaxSectorConcentration : 0);
        var deltaRisk = deltaExposure.IsOverExposed ? Math.Abs(deltaExposure.NetDelta) - MaxDeltaExposure : 0;
        
        return positionRisk + sectorRisk + deltaRisk;
    }
} 