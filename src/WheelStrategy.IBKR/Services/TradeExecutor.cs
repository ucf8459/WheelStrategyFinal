using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using AutoFinance.Broker.InteractiveBrokers.Controllers;
using IBApi;

namespace WheelStrategy.IBKR.Services;

/// <summary>
/// Real IBKR trade execution service using AutoFinance.Broker
/// </summary>
public class TradeExecutor : ITradeExecutor
{
    private readonly ILogger<TradeExecutor> _logger;
    private readonly WheelStrategyOptions _options;
    private readonly IMarketDataService _marketDataService;
    private readonly IBKRConnectionService _connectionService;
    private bool _isConnected = false;

    public TradeExecutor(
        IOptions<WheelStrategyOptions> options,
        IMarketDataService marketDataService,
        IBKRConnectionService connectionService,
        ILogger<TradeExecutor> logger)
    {
        _options = options.Value;
        _marketDataService = marketDataService;
        _connectionService = connectionService;
        _logger = logger;
    }

    /// <summary>
    /// Ensures connection to IBKR
    /// </summary>
    private async Task EnsureConnectionAsync()
    {
        if (!_isConnected && !_connectionService.IsConnected)
        {
            try
            {
                _isConnected = await _connectionService.ConnectAsync();
                if (!_isConnected)
                {
                    throw new Exception("Failed to connect to IBKR using AutoFinance.Broker - Please ensure TWS or IB Gateway is running");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to connect to IBKR using AutoFinance.Broker");
                throw new Exception("IBKR connection failed. Please start TWS or IB Gateway and ensure API connections are enabled.", ex);
            }
        }
    }

    public async Task<Dictionary<string, object>?> SellPutAsync(string symbol, decimal strike, string expiry, decimal premium)
    {
        await EnsureConnectionAsync();
        
        _logger.LogInformation("Selling put: {Symbol} {Strike} {Expiry} for {Premium}", symbol, strike, expiry, premium);

        try
        {
            var twsController = _connectionService.GetTwsController();
            if (twsController == null)
            {
                throw new Exception("IBKR connection not available");
            }

            // Create option contract using AutoFinance.Broker
            var contract = new Contract
            {
                Symbol = symbol,
                SecType = "OPT",
                Strike = (double)strike,
                Right = "P",
                Exchange = "SMART",
                Currency = "USD"
            };

            // Create order using AutoFinance.Broker
            var order = new Order
            {
                Action = "SELL",
                OrderType = "LMT",
                TotalQuantity = 1,
                LmtPrice = (double)premium,
                Tif = "DAY"
            };

            // Get next valid order ID
            var orderId = await twsController.GetNextValidIdAsync();
            
            // Place order using AutoFinance.Broker
            var successfullyPlaced = await twsController.PlaceOrderAsync(orderId, contract, order);
            
            var result = new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["strike"] = strike,
                ["expiry"] = expiry,
                ["premium"] = premium,
                ["action"] = "SELL_PUT",
                ["status"] = successfullyPlaced ? "SUBMITTED" : "FAILED",
                ["orderId"] = orderId,
                ["fillPrice"] = premium,
                ["fillTime"] = DateTime.UtcNow,
                ["timestamp"] = DateTime.UtcNow
            };

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to sell put for {Symbol}", symbol);
            throw new Exception("IBKR connection failed. Please start TWS or IB Gateway and ensure API connections are enabled.", ex);
        }
    }

    public async Task<Dictionary<string, object>?> SellCoveredCallAsync(string symbol, int shares, decimal strike, string expiry, decimal premium)
    {
        await EnsureConnectionAsync();
        
        _logger.LogInformation("Selling covered call: {Symbol} {Strike} {Expiry} for {Premium}", symbol, strike, expiry, premium);

        try
        {
            var twsController = _connectionService.GetTwsController();
            if (twsController == null)
            {
                throw new Exception("IBKR connection not available");
            }

            // Create option contract using AutoFinance.Broker
            var contracts = shares / 100; // Convert shares to contracts
            var contract = new Contract
            {
                Symbol = symbol,
                SecType = "OPT",
                Strike = (double)strike,
                Right = "C",
                Exchange = "SMART",
                Currency = "USD"
            };

            // Create order using AutoFinance.Broker
            var order = new Order
            {
                Action = "SELL",
                OrderType = "LMT",
                TotalQuantity = contracts,
                LmtPrice = (double)premium,
                Tif = "DAY"
            };

            // Get next valid order ID
            var orderId = await twsController.GetNextValidIdAsync();
            
            // Place order using AutoFinance.Broker
            var successfullyPlaced = await twsController.PlaceOrderAsync(orderId, contract, order);
            
            var result = new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["shares"] = shares,
                ["strike"] = strike,
                ["expiry"] = expiry,
                ["premium"] = premium,
                ["action"] = "SELL_COVERED_CALL",
                ["status"] = successfullyPlaced ? "SUBMITTED" : "FAILED",
                ["orderId"] = orderId,
                ["fillPrice"] = premium,
                ["fillTime"] = DateTime.UtcNow,
                ["timestamp"] = DateTime.UtcNow
            };

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to sell covered call for {Symbol}", symbol);
            throw new Exception("IBKR connection failed. Please start TWS or IB Gateway and ensure API connections are enabled.", ex);
        }
    }

    public async Task<Dictionary<string, object>?> RollPositionAsync(string symbol, decimal oldStrike, string oldExpiry, decimal newStrike, string newExpiry)
    {
        await EnsureConnectionAsync();
        
        _logger.LogInformation("Rolling position: {Symbol} from {OldStrike}/{OldExpiry} to {NewStrike}/{NewExpiry}",
            symbol, oldStrike, oldExpiry, newStrike, newExpiry);

        try
        {
            var twsController = _connectionService.GetTwsController();
            if (twsController == null)
            {
                throw new Exception("IBKR connection not available");
            }

            // Close old position
            var closeContract = new Contract
            {
                Symbol = symbol,
                SecType = "OPT",
                Strike = (double)oldStrike,
                Right = "P",
                Exchange = "SMART",
                Currency = "USD"
            };

            var closeOrder = new Order
            {
                Action = "BUY",
                OrderType = "MKT",
                TotalQuantity = 1,
                Tif = "DAY"
            };

            var closeOrderId = await twsController.GetNextValidIdAsync();
            var closeSuccess = await twsController.PlaceOrderAsync(closeOrderId, closeContract, closeOrder);

            // Open new position
            var openContract = new Contract
            {
                Symbol = symbol,
                SecType = "OPT",
                Strike = (double)newStrike,
                Right = "P",
                Exchange = "SMART",
                Currency = "USD"
            };

            var openOrder = new Order
            {
                Action = "SELL",
                OrderType = "LMT",
                TotalQuantity = 1,
                Tif = "DAY"
            };

            var openOrderId = await twsController.GetNextValidIdAsync();
            var openSuccess = await twsController.PlaceOrderAsync(openOrderId, openContract, openOrder);
            
            var result = new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["oldStrike"] = oldStrike,
                ["oldExpiry"] = oldExpiry,
                ["newStrike"] = newStrike,
                ["newExpiry"] = newExpiry,
                ["action"] = "ROLL_POSITION",
                ["status"] = (closeSuccess && openSuccess) ? "SUBMITTED" : "FAILED",
                ["closeOrderId"] = closeOrderId,
                ["openOrderId"] = openOrderId,
                ["closeFillPrice"] = 0.0m,
                ["openFillPrice"] = 0.0m,
                ["timestamp"] = DateTime.UtcNow
            };

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to roll position for {Symbol}", symbol);
            throw new Exception("IBKR connection failed. Please start TWS or IB Gateway and ensure API connections are enabled.", ex);
        }
    }

    public async Task<Dictionary<string, object>> ClosePositionAsync(string symbol, decimal strike, string expiry, string reason = "Manual close")
    {
        await EnsureConnectionAsync();
        
        _logger.LogInformation("Closing position: {Symbol} {Strike} {Expiry} - {Reason}", symbol, strike, expiry, reason);

        try
        {
            var twsController = _connectionService.GetTwsController();
            if (twsController == null)
            {
                throw new Exception("IBKR connection not available");
            }

            // Create option contract using AutoFinance.Broker
            var contract = new Contract
            {
                Symbol = symbol,
                SecType = "OPT",
                Strike = (double)strike,
                Right = "P",
                Exchange = "SMART",
                Currency = "USD"
            };

            // Create order using AutoFinance.Broker
            var order = new Order
            {
                Action = "BUY",
                OrderType = "MKT",
                TotalQuantity = 1,
                Tif = "DAY"
            };

            // Get next valid order ID
            var orderId = await twsController.GetNextValidIdAsync();
            
            // Place order using AutoFinance.Broker
            var successfullyPlaced = await twsController.PlaceOrderAsync(orderId, contract, order);
            
            var result = new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["strike"] = strike,
                ["expiry"] = expiry,
                ["action"] = "CLOSE_POSITION",
                ["reason"] = reason,
                ["status"] = successfullyPlaced ? "SUBMITTED" : "FAILED",
                ["orderId"] = orderId,
                ["fillPrice"] = 0.0m,
                ["fillTime"] = DateTime.UtcNow,
                ["timestamp"] = DateTime.UtcNow
            };

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to close position for {Symbol}", symbol);
            throw new Exception("IBKR connection failed. Please start TWS or IB Gateway and ensure API connections are enabled.", ex);
        }
    }

    public async Task<bool> IsOptimalTradeTimeAsync()
    {
        // Check if current time is optimal for trading
        var now = DateTime.UtcNow;
        var easternTime = TimeZoneInfo.ConvertTimeFromUtc(now, TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"));
        
        // Optimal trading hours: 9:30 AM - 3:30 PM ET
        var marketOpen = new TimeSpan(9, 30, 0);
        var marketClose = new TimeSpan(15, 30, 0);
        
        return easternTime.TimeOfDay >= marketOpen && easternTime.TimeOfDay <= marketClose;
    }

    public async Task<Dictionary<string, object>> GetExecutionQualityAsync()
    {
        await EnsureConnectionAsync();
        
        _logger.LogInformation("Getting execution quality from IBKR using AutoFinance.Broker");

        try
        {
            var twsController = _connectionService.GetTwsController();
            if (twsController == null)
            {
                throw new Exception("IBKR connection not available");
            }

            // For now, return sample data while we implement proper execution quality metrics
            var result = new Dictionary<string, object>
            {
                ["avgFillTime"] = 0.15,
                ["fillRate"] = 0.95,
                ["slippage"] = 0.02,
                ["timestamp"] = DateTime.UtcNow
            };

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get execution quality from IBKR using AutoFinance.Broker");
            throw new Exception("IBKR connection failed. Please start TWS or IB Gateway and ensure API connections are enabled.", ex);
        }
    }
} 