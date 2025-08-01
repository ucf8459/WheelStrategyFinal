# IBKR Real Data Connectivity Setup Guide

## Overview

This guide will help you connect your .NET Wheel Strategy system to real Interactive Brokers (IBKR) data and trading functionality.

## Prerequisites

### 1. IBKR Account Setup
- **Paper Trading Account**: For testing (recommended to start)
- **Live Trading Account**: For real trading (when ready)
- **TWS or IB Gateway**: Must be installed and running

### 2. Software Requirements
- **TWS (Trader Workstation)** or **IB Gateway**
- **API Permissions**: Enabled in TWS/Gateway
- **Firewall**: Ports 7496 (live) and 7497 (paper) open

## Step-by-Step Setup

### Step 1: Install TWS or IB Gateway

#### Option A: TWS (Trader Workstation)
1. Download from: https://www.interactivebrokers.com/en/trading/tws.php
2. Install and launch TWS
3. Log in with your IBKR credentials

#### Option B: IB Gateway (Recommended for Production)
1. Download from: https://www.interactivebrokers.com/en/trading/ib-api.php
2. Install and launch IB Gateway
3. Log in with your IBKR credentials

### Step 2: Configure API Settings

#### In TWS/Gateway:
1. **File → Global Configuration** (TWS) or **Edit → Settings** (Gateway)
2. **API → Settings**
3. **Enable ActiveX and Socket Clients**: ✅ Checked
4. **Socket port**: 7496 (live) or 7497 (paper)
5. **Read-Only API**: Unchecked (for trading)
6. **Allow connections from localhost**: ✅ Checked
7. **Download open orders on connection**: ✅ Checked
8. **Include FX positions**: ✅ Checked
9. **Create API message log file**: ✅ Checked (for debugging)

### Step 3: Configure Application Settings

#### Update `appsettings.json`:

```json
{
  "WheelStrategy": {
    "IBKR": {
      "Host": "127.0.0.1",
      "Port": 7497,
      "ClientId": 1,
      "UsePaperTrading": true,
      "ConnectionTimeout": 30,
      "ReconnectAttempts": 3,
      "PaperTradingPort": 7497,
      "LiveTradingPort": 7496,
      "GatewayHost": "127.0.0.1",
      "TWSHost": "127.0.0.1"
    }
  }
}
```

#### For Live Trading:
```json
{
  "WheelStrategy": {
    "IBKR": {
      "Host": "127.0.0.1",
      "Port": 7496,
      "ClientId": 1,
      "UsePaperTrading": false,
      "ConnectionTimeout": 30,
      "ReconnectAttempts": 3,
      "PaperTradingPort": 7497,
      "LiveTradingPort": 7496,
      "GatewayHost": "127.0.0.1",
      "TWSHost": "127.0.0.1"
    }
  }
}
```

### Step 4: Test Connection

#### 1. Start TWS/Gateway
```bash
# Ensure TWS or IB Gateway is running and logged in
```

#### 2. Test Console Application
```bash
cd src/WheelStrategy.Console
dotnet run
```

**Expected Output:**
```
info: WheelStrategy.IBKR.Services.IBKRMarketDataService[0]
      Connected to IBKR
info: WheelStrategy.Console.Program[0]
      Starting Wheel Strategy Console Application
info: WheelStrategy.Console.Program[0]
      Starting monitoring loop
info: WheelStrategy.IBKR.Services.IBKRMarketDataService[0]
      Getting account summary
info: WheelStrategy.IBKR.Services.IBKRMarketDataService[0]
      Getting positions
```

#### 3. Test Web Dashboard
```bash
cd src/WheelStrategy.Web
dotnet run --urls http://localhost:7001
```

**Expected Output:**
```
info: Microsoft.Hosting.Lifetime[14]
      Now listening on: http://localhost:7001
info: WheelStrategy.IBKR.Services.IBKRMarketDataService[0]
      Connected to IBKR
```

### Step 5: Verify Real Data

#### Check Dashboard Features:
1. **Portfolio Overview**: Real account values
2. **Active Positions**: Live position data
3. **Market Data**: Real-time prices
4. **Order Execution**: Test with paper trading

## Troubleshooting

### Common Issues

#### 1. Connection Failed
**Symptoms:**
```
error: Failed to connect to IBKR within timeout period
```

**Solutions:**
- Verify TWS/Gateway is running
- Check port settings (7496/7497)
- Ensure API is enabled in TWS
- Check firewall settings

#### 2. Authentication Error
**Symptoms:**
```
error: IBKR Error: Authentication failed
```

**Solutions:**
- Verify IBKR credentials
- Check if TWS requires re-authentication
- Ensure account is active

#### 3. Market Data Not Updating
**Symptoms:**
- Dashboard shows stale data
- No real-time updates

**Solutions:**
- Check market hours
- Verify data subscriptions
- Restart TWS/Gateway
- Check API permissions

#### 4. Order Execution Issues
**Symptoms:**
- Orders not being placed
- Error messages in logs

**Solutions:**
- Verify trading permissions
- Check account balance
- Ensure proper contract specifications
- Test with paper trading first

### Debug Mode

#### Enable Detailed Logging:
```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "WheelStrategy.IBKR": "Debug",
      "Microsoft.AspNetCore": "Warning"
    }
  }
}
```

#### Check TWS API Log:
- **TWS**: Help → About Trader Workstation → API Log
- **Gateway**: View → API Log

## Security Considerations

### 1. Network Security
- **Localhost Only**: API connections restricted to 127.0.0.1
- **Firewall**: Block external access to API ports
- **VPN**: Use VPN for remote access

### 2. Account Security
- **Paper Trading First**: Test thoroughly before live trading
- **Position Limits**: Set maximum position sizes
- **Risk Controls**: Use IBKR's built-in risk controls

### 3. Application Security
- **Read-Only Mode**: Test with read-only API first
- **Order Confirmation**: Always confirm orders before execution
- **Audit Trail**: Log all trading activities

## Production Deployment

### 1. Live Trading Checklist
- [ ] Tested with paper trading for 30+ days
- [ ] Verified all risk controls
- [ ] Set position size limits
- [ ] Configured alerts and notifications
- [ ] Backup and recovery procedures
- [ ] Monitoring and logging setup

### 2. System Requirements
- **CPU**: 4+ cores recommended
- **Memory**: 8GB+ RAM
- **Network**: Stable internet connection
- **Storage**: SSD for fast data access
- **Uptime**: 99.9% availability target

### 3. Monitoring
- **Health Checks**: Regular connection tests
- **Performance**: Monitor response times
- **Errors**: Track and alert on failures
- **Trading**: Monitor order execution quality

## Advanced Configuration

### 1. Multiple Accounts
```json
{
  "WheelStrategy": {
    "IBKR": {
      "Host": "127.0.0.1",
      "Port": 7497,
      "ClientId": 1,
      "UsePaperTrading": true,
      "AccountId": "DU1234567"
    }
  }
}
```

### 2. Custom Risk Limits
```json
{
  "WheelStrategy": {
    "RiskThresholds": {
      "MaxPositionPercentage": 0.05,
      "MaxSectorPercentage": 0.15,
      "DrawdownStop": 0.15,
      "WeeklyDrawdownStop": 0.08
    }
  }
}
```

### 3. Market Hours
```json
{
  "WheelStrategy": {
    "TradingHours": {
      "StartTime": "09:30",
      "EndTime": "16:00",
      "Timezone": "America/New_York"
    }
  }
}
```

## Support and Resources

### IBKR Resources
- **API Documentation**: https://interactivebrokers.github.io/tws-api/
- **TWS API Guide**: https://www.interactivebrokers.com/en/trading/tws-api.php
- **Support**: https://www.interactivebrokers.com/en/support/contact-support.php

### System Documentation
- **Dashboard Guide**: `python/dashboard_training_guide.md`
- **Configuration**: `CONFIGURATION.md`
- **Migration Guide**: `MIGRATION_GUIDE.md`

## Next Steps

1. **Test with Paper Trading**: Run for 30+ days
2. **Monitor Performance**: Track P&L and execution quality
3. **Optimize Settings**: Adjust based on results
4. **Scale Gradually**: Start small, increase position sizes
5. **Regular Reviews**: Weekly performance analysis

## Emergency Procedures

### 1. System Failure
- **Stop Trading**: Immediately halt all automated trading
- **Check Logs**: Review error messages
- **Restart Services**: Restart TWS and application
- **Verify Data**: Confirm account status

### 2. Connection Loss
- **Automatic Reconnection**: System will attempt to reconnect
- **Manual Intervention**: May require manual restart
- **Data Sync**: Verify position data after reconnection

### 3. Order Issues
- **Check TWS**: Verify order status in TWS
- **Cancel Orders**: Cancel any stuck orders
- **Review Logs**: Check for error messages
- **Contact Support**: If issues persist

---

**Important**: Always test thoroughly with paper trading before using real money. The wheel strategy involves significant risk and should only be used by experienced traders who understand options trading. 