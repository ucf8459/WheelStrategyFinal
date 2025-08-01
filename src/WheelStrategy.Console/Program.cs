using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Models;
using WheelStrategy.IBKR.Services;

namespace WheelStrategy.Console;

/// <summary>
/// Console application for wheel strategy monitoring
/// </summary>
public class Program
{
    public static async Task Main(string[] args)
    {
        var host = CreateHostBuilder(args).Build();
        
        using var scope = host.Services.CreateScope();
        var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();
        
        logger.LogInformation("Starting Wheel Strategy Console Application");
        
        try
        {
            var wheelMonitor = scope.ServiceProvider.GetRequiredService<IWheelMonitor>();
            var wheelScanner = scope.ServiceProvider.GetRequiredService<IWheelScanner>();
            var alertManager = scope.ServiceProvider.GetRequiredService<IAlertManager>();
            
            // Start monitoring loop
            await RunMonitoringLoopAsync(wheelMonitor, wheelScanner, alertManager, logger);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Application failed");
        }
    }
    
    private static IHostBuilder CreateHostBuilder(string[] args) =>
        Host.CreateDefaultBuilder(args)
            .ConfigureServices((context, services) =>
            {
                // Configure options
                services.Configure<WheelStrategyOptions>(
                    context.Configuration.GetSection(WheelStrategyOptions.SectionName));
                
                // Register services
                services.AddSingleton<IBKRConnectionService>();
                services.AddScoped<IBKRMarketDataService>();
                services.AddScoped<IWheelMonitor, WheelMonitor>();
                services.AddScoped<IWheelScanner, WheelScanner>();
                services.AddScoped<ITradeExecutor, TradeExecutor>();
                services.AddScoped<IAlertManager, AlertManager>();
            })
            .ConfigureLogging(logging =>
            {
                logging.ClearProviders();
                logging.AddConsole();
                logging.SetMinimumLevel(LogLevel.Information);
            });
    
    private static async Task RunMonitoringLoopAsync(
        IWheelMonitor wheelMonitor,
        IWheelScanner wheelScanner,
        IAlertManager alertManager,
        ILogger logger)
    {
        logger.LogInformation("Starting monitoring loop");
        
        while (true)
        {
            try
            {
                // Get portfolio metrics
                var metrics = await wheelMonitor.GetPortfolioMetricsAsync();
                logger.LogInformation("Account Value: ${AccountValue:N2}, Cash: {CashPercentage:P2}, P&L: ${UnrealizedPnL:N2}",
                    metrics.AccountValue, metrics.CashPercentage, metrics.UnrealizedPnL);
                
                // Get wheel positions
                var positions = await wheelMonitor.GetWheelPositionsAsync();
                logger.LogInformation("Active Wheel Positions: {Count}", positions.Count);
                
                foreach (var position in positions)
                {
                    logger.LogInformation("  {Symbol}: {PutCount} puts, {ShareCount} shares, Total Income: ${Income:N2}",
                        position.Symbol, position.PutStrikes.Count, position.SharesOwned, position.TotalIncome);
                }
                
                // Get opportunities
                var opportunities = await wheelScanner.ScanOpportunitiesAsync();
                logger.LogInformation("Available Opportunities: {Count}", opportunities.Count);
                
                foreach (var opportunity in opportunities.Take(5))
                {
                    logger.LogInformation("  {Symbol} {Strike}P: {Return:P1} return, {IVRank:F0}% IV rank",
                        opportunity.Symbol, opportunity.Strike, opportunity.AnnualReturn, opportunity.IVRank);
                }
                
                // Check for alerts
                if (metrics.MaxDrawdown > 0.10m)
                {
                    await alertManager.SendImportantAlertAsync(
                        "High Drawdown Alert",
                        $"Portfolio drawdown is {metrics.MaxDrawdown:P1}",
                        "Consider reducing position sizes");
                }
                
                if (metrics.VIXLevel > 30)
                {
                    await alertManager.SendInfoAlertAsync(
                        "High VIX Alert",
                        $"VIX is at {metrics.VIXLevel:F1} - consider defensive positioning");
                }
                
                // Wait before next update
                await Task.Delay(TimeSpan.FromMinutes(5));
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Error in monitoring loop");
                await Task.Delay(TimeSpan.FromMinutes(1));
            }
        }
    }
} 