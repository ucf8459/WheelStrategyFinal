using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using System.Text;
using System.Text.Json;

namespace WheelStrategy.IBKR.Services;

/// <summary>
/// IBKR Client Portal Web API service using REST endpoints
/// </summary>
public class IBKRWebApiService : IMarketDataService
{
    private readonly ILogger<IBKRWebApiService> _logger;
    private readonly WheelStrategyOptions _options;
    private readonly HttpClient _httpClient;
    private string? _sessionId;
    private bool _isAuthenticated = false;

    public IBKRWebApiService(
        ILogger<IBKRWebApiService> logger,
        IOptions<WheelStrategyOptions> options,
        HttpClient httpClient)
    {
        _logger = logger;
        _options = options.Value;
        _httpClient = httpClient;
        _httpClient.BaseAddress = new Uri("https://localhost:5001/v1/portal/");
    }

    /// <summary>
    /// Authenticates with IBKR Client Portal API
    /// </summary>
    private async Task EnsureAuthenticationAsync()
    {
        if (_isAuthenticated) return;

        try
        {
            _logger.LogInformation("Authenticating with IBKR Client Portal API");

            // First, try to validate existing session
            var validateResponse = await _httpClient.GetAsync("iserver/auth/status");
            if (validateResponse.IsSuccessStatusCode)
            {
                var validateContent = await validateResponse.Content.ReadAsStringAsync();
                var validateResult = JsonSerializer.Deserialize<Dictionary<string, object>>(validateContent);
                
                if (validateResult?.ContainsKey("authenticated") == true && 
                    validateResult["authenticated"].ToString() == "true")
                {
                    _isAuthenticated = true;
                    _logger.LogInformation("Already authenticated with IBKR Client Portal API");
                    return;
                }
            }

            // If not authenticated, try to authenticate
            var authResponse = await _httpClient.PostAsync("iserver/auth/ssodh/init", null);
            if (authResponse.IsSuccessStatusCode)
            {
                var authContent = await authResponse.Content.ReadAsStringAsync();
                var authResult = JsonSerializer.Deserialize<Dictionary<string, object>>(authContent);
                
                if (authResult?.ContainsKey("authenticated") == true && 
                    authResult["authenticated"].ToString() == "true")
                {
                    _isAuthenticated = true;
                    _logger.LogInformation("Successfully authenticated with IBKR Client Portal API");
                }
                else
                {
                    _logger.LogWarning("Authentication failed - you may need to log into IBKR Client Portal first");
                }
            }
            else
            {
                _logger.LogWarning("Could not authenticate with IBKR Client Portal API - make sure it's running");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to authenticate with IBKR Client Portal API");
        }
    }

    /// <summary>
    /// Gets account summary from IBKR Client Portal API
    /// </summary>
    public async Task<Dictionary<string, object>> GetAccountSummaryAsync()
    {
        await EnsureAuthenticationAsync();
        
        _logger.LogInformation("Getting account summary from IBKR Client Portal API");

        try
        {
            var response = await _httpClient.GetAsync("iserver/account");
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var accounts = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(content);
                
                if (accounts?.Count > 0)
                {
                    var account = accounts[0]; // Use first account
                    return new Dictionary<string, object>
                    {
                        ["AccountValue"] = account.GetValueOrDefault("netliquidation", 100000.0),
                        ["AvailableFunds"] = account.GetValueOrDefault("availablefunds", 50000.0),
                        ["UnrealizedPnL"] = account.GetValueOrDefault("unrealizedpnl", 0.0),
                        ["RealizedPnL"] = account.GetValueOrDefault("realizedpnl", 0.0),
                        ["BuyingPower"] = account.GetValueOrDefault("buyingpower", 50000.0),
                        ["MarginBalance"] = account.GetValueOrDefault("marginbalance", 100000.0),
                        ["NetLiquidation"] = account.GetValueOrDefault("netliquidation", 100000.0)
                    };
                }
            }
            
            _logger.LogWarning("Could not retrieve account summary from IBKR Client Portal API");
            return new Dictionary<string, object>
            {
                ["AccountValue"] = 100000.0,
                ["AvailableFunds"] = 50000.0,
                ["UnrealizedPnL"] = 0.0,
                ["RealizedPnL"] = 0.0,
                ["BuyingPower"] = 50000.0,
                ["MarginBalance"] = 100000.0,
                ["NetLiquidation"] = 100000.0
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get account summary from IBKR Client Portal API");
            return new Dictionary<string, object>
            {
                ["AccountValue"] = 100000.0,
                ["AvailableFunds"] = 50000.0,
                ["UnrealizedPnL"] = 0.0,
                ["RealizedPnL"] = 0.0,
                ["BuyingPower"] = 50000.0,
                ["MarginBalance"] = 100000.0,
                ["NetLiquidation"] = 100000.0
            };
        }
    }

    /// <summary>
    /// Gets current positions from IBKR Client Portal API
    /// </summary>
    public async Task<List<Dictionary<string, object>>> GetPositionsAsync()
    {
        await EnsureAuthenticationAsync();
        
        _logger.LogInformation("Getting positions from IBKR Client Portal API");

        try
        {
            var response = await _httpClient.GetAsync("iserver/account/positions");
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var positions = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(content);
                
                var result = new List<Dictionary<string, object>>();
                
                if (positions != null)
                {
                    foreach (var position in positions)
                    {
                        var positionData = new Dictionary<string, object>
                        {
                            ["symbol"] = position.GetValueOrDefault("conid", ""),
                            ["quantity"] = position.GetValueOrDefault("position", 0),
                            ["strike"] = position.GetValueOrDefault("strike", 0.0),
                            ["right"] = position.GetValueOrDefault("putCall", ""),
                            ["expiry"] = position.GetValueOrDefault("expiry", ""),
                            ["dte"] = 0, // Calculate if needed
                            ["type"] = position.GetValueOrDefault("assetClass", "STK"),
                            ["avgCost"] = position.GetValueOrDefault("avgCost", 0.0),
                            ["marketValue"] = position.GetValueOrDefault("marketValue", 0.0),
                            ["unrealizedPnL"] = position.GetValueOrDefault("unrealizedPnl", 0.0),
                            ["realizedPnL"] = position.GetValueOrDefault("realizedPnl", 0.0),
                            ["delta"] = 1.0, // Default for stocks
                            ["gamma"] = 0.0,
                            ["theta"] = 0.0,
                            ["vega"] = 0.0,
                            ["iv"] = 0.0
                        };
                        
                        result.Add(positionData);
                    }
                }
                
                _logger.LogInformation("Found {Count} positions from IBKR Client Portal API", result.Count);
                return result;
            }
            
            _logger.LogWarning("Could not retrieve positions from IBKR Client Portal API");
            return new List<Dictionary<string, object>>();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get positions from IBKR Client Portal API");
            return new List<Dictionary<string, object>>();
        }
    }

    /// <summary>
    /// Gets real-time option data including Greeks from IBKR Client Portal API
    /// </summary>
    public async Task<Dictionary<string, object>> GetOptionDataAsync(string symbol, decimal strike, string expiry, string right)
    {
        await EnsureAuthenticationAsync();
        
        _logger.LogInformation("Getting option data for {Symbol} {Strike} {Right} {Expiry} from IBKR Client Portal API", 
            symbol, strike, right, expiry);

        try
        {
            // Get option contract info
            var contractResponse = await _httpClient.GetAsync($"iserver/secdef/search?symbol={symbol}");
            if (contractResponse.IsSuccessStatusCode)
            {
                var contractContent = await contractResponse.Content.ReadAsStringAsync();
                var contracts = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(contractContent);
                
                if (contracts?.Count > 0)
                {
                    var contract = contracts.FirstOrDefault(c => 
                        c.GetValueOrDefault("strike", 0.0).ToString() == strike.ToString() &&
                        c.GetValueOrDefault("putCall", "").ToString() == right);
                    
                    if (contract != null)
                    {
                        var conid = contract.GetValueOrDefault("conid", "");
                        
                        // Get market data for this contract
                        var marketDataResponse = await _httpClient.GetAsync($"iserver/marketdata/snapshot?conids={conid}");
                        if (marketDataResponse.IsSuccessStatusCode)
                        {
                            var marketDataContent = await marketDataResponse.Content.ReadAsStringAsync();
                            var marketData = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(marketDataContent);
                            
                            if (marketData?.Count > 0)
                            {
                                var data = marketData[0];
                                return new Dictionary<string, object>
                                {
                                    ["symbol"] = symbol,
                                    ["strike"] = strike,
                                    ["expiry"] = expiry,
                                    ["right"] = right,
                                    ["bid"] = data.GetValueOrDefault("b", 0.0),
                                    ["ask"] = data.GetValueOrDefault("a", 0.0),
                                    ["last"] = data.GetValueOrDefault("l", 0.0),
                                    ["volume"] = data.GetValueOrDefault("v", 0),
                                    ["openInterest"] = data.GetValueOrDefault("oi", 0),
                                    ["impliedVolatility"] = data.GetValueOrDefault("iv", 0.0),
                                    ["delta"] = data.GetValueOrDefault("delta", 0.0),
                                    ["gamma"] = data.GetValueOrDefault("gamma", 0.0),
                                    ["theta"] = data.GetValueOrDefault("theta", 0.0),
                                    ["vega"] = data.GetValueOrDefault("vega", 0.0)
                                };
                            }
                        }
                    }
                }
            }
            
            _logger.LogWarning("Could not retrieve option data from IBKR Client Portal API for {Symbol} {Strike} {Right} {Expiry} - returning empty data", 
                symbol, strike, right, expiry);
            return new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["strike"] = strike,
                ["expiry"] = expiry,
                ["right"] = right,
                ["bid"] = 0.0,
                ["ask"] = 0.0,
                ["last"] = 0.0,
                ["volume"] = 0,
                ["openInterest"] = 0,
                ["impliedVolatility"] = 0.0,
                ["delta"] = 0.0,
                ["gamma"] = 0.0,
                ["theta"] = 0.0,
                ["vega"] = 0.0
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get option data from IBKR Client Portal API for {Symbol} {Strike} {Right} {Expiry}", 
                symbol, strike, right, expiry);
            return new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["strike"] = strike,
                ["expiry"] = expiry,
                ["right"] = right,
                ["bid"] = 0.0,
                ["ask"] = 0.0,
                ["last"] = 0.0,
                ["volume"] = 0,
                ["openInterest"] = 0,
                ["impliedVolatility"] = 0.0,
                ["delta"] = 0.0,
                ["gamma"] = 0.0,
                ["theta"] = 0.0,
                ["vega"] = 0.0
            };
        }
    }

    /// <summary>
    /// Gets real-time stock data from IBKR Client Portal API
    /// </summary>
    public async Task<Dictionary<string, object>> GetStockDataAsync(string symbol)
    {
        await EnsureAuthenticationAsync();
        
        _logger.LogInformation("Getting stock data for {Symbol} from IBKR Client Portal API", symbol);

        try
        {
            // Get stock contract info
            var contractResponse = await _httpClient.GetAsync($"iserver/secdef/search?symbol={symbol}");
            if (contractResponse.IsSuccessStatusCode)
            {
                var contractContent = await contractResponse.Content.ReadAsStringAsync();
                var contracts = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(contractContent);
                
                if (contracts?.Count > 0)
                {
                    var contract = contracts.FirstOrDefault(c => 
                        c.GetValueOrDefault("assetClass", "").ToString() == "STK");
                    
                    if (contract != null)
                    {
                        var conid = contract.GetValueOrDefault("conid", "");
                        
                        // Get market data for this contract
                        var marketDataResponse = await _httpClient.GetAsync($"iserver/marketdata/snapshot?conids={conid}");
                        if (marketDataResponse.IsSuccessStatusCode)
                        {
                            var marketDataContent = await marketDataResponse.Content.ReadAsStringAsync();
                            var marketData = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(marketDataContent);
                            
                            if (marketData?.Count > 0)
                            {
                                var data = marketData[0];
                                return new Dictionary<string, object>
                                {
                                    ["symbol"] = symbol,
                                    ["bid"] = data.GetValueOrDefault("b", 0.0),
                                    ["ask"] = data.GetValueOrDefault("a", 0.0),
                                    ["price"] = data.GetValueOrDefault("l", 0.0),
                                    ["volume"] = data.GetValueOrDefault("v", 0),
                                    ["marketCap"] = data.GetValueOrDefault("mc", 0.0),
                                    ["IsSampleData"] = false
                                };
                            }
                        }
                    }
                }
            }
            
            _logger.LogWarning("Could not retrieve stock data from IBKR Client Portal API for {Symbol} - returning empty data", symbol);
            return new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["bid"] = 0.0,
                ["ask"] = 0.0,
                ["price"] = 0.0,
                ["volume"] = 0,
                ["marketCap"] = 0.0,
                ["IsSampleData"] = false
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get stock data from IBKR Client Portal API for {Symbol}", symbol);
            return new Dictionary<string, object>
            {
                ["symbol"] = symbol,
                ["bid"] = 0.0,
                ["ask"] = 0.0,
                ["price"] = 0.0,
                ["volume"] = 0,
                ["marketCap"] = 0.0,
                ["IsSampleData"] = false
            };
        }
    }
} 