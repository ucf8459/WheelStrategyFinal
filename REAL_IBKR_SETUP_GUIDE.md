# Real IBKR Integration Setup Guide

## 🎯 **Overview**
This guide will help you connect your .NET Wheel Strategy system to real Interactive Brokers data and trading functionality.

## 📋 **Prerequisites**

### 1. **Interactive Brokers Account**
- Active IBKR account (Paper or Live)
- API access enabled
- TWS (Trader Workstation) or IB Gateway installed

### 2. **Software Requirements**
- TWS (Trader Workstation) or IB Gateway
- .NET 9.0 Runtime
- Network access to IBKR servers

## 🚀 **Step-by-Step Setup**

### **Step 1: Install TWS or IB Gateway**

#### **Option A: TWS (Trader Workstation)**
1. Download TWS from [Interactive Brokers](https://www.interactivebrokers.com/en/trading/tws.php)
2. Install and launch TWS
3. Log in with your IBKR credentials

#### **Option B: IB Gateway (Recommended)**
1. Download IB Gateway from [Interactive Brokers](https://www.interactivebrokers.com/en/trading/ib-api.php)
2. Install and launch IB Gateway
3. Log in with your IBKR credentials

### **Step 2: Configure API Settings**

#### **In TWS/IB Gateway:**
1. Go to **File → Global Configuration** (TWS) or **Edit → Settings** (Gateway)
2. Navigate to **API → Settings**
3. Enable **Enable ActiveX and Socket Clients**
4. Set **Socket port** to `7496` (Live) or `7497` (Paper)
5. Add your local IP (`127.0.0.1`) to **Trusted IPs**
6. Click **OK** and restart TWS/Gateway

### **Step 3: Configure Application Settings**

#### **Update `appsettings.json`:**
```json
{
  "WheelStrategy": {
    "IBKR": {
      "Host": "127.0.0.1",
      "Port": 7496,           // 7496 for Live, 7497 for Paper
      "ClientId": 1,
      "UsePaperTrading": false, // false for Live, true for Paper
      "ConnectionTimeout": 30,
      "ReconnectAttempts": 3
    }
  }
}
```

### **Step 4: Test Connection**

#### **Start the Application:**
```bash
dotnet run --project src/WheelStrategy.Web --urls http://localhost:7001
```

#### **Verify Connection:**
1. Open browser to `http://localhost:7001`
2. Check logs for connection status
3. Verify data is loading (not sample data)

## 🔧 **Troubleshooting**

### **Common Issues:**

#### **1. Connection Failed**
- **Symptom**: "Failed to connect to IBKR"
- **Solution**: 
  - Ensure TWS/Gateway is running
  - Verify API settings are enabled
  - Check port configuration (7496/7497)
  - Restart TWS/Gateway

#### **2. Port Already in Use**
- **Symptom**: "Address already in use"
- **Solution**:
  - Kill existing processes: `lsof -ti:7001 | xargs kill -9`
  - Use different port: `--urls http://localhost:7002`

#### **3. No Data Loading**
- **Symptom**: Dashboard shows no data
- **Solution**:
  - Check IBKR account has positions
  - Verify market data subscriptions
  - Check API permissions

#### **4. Authentication Issues**
- **Symptom**: "Authentication failed"
- **Solution**:
  - Verify IBKR credentials
  - Check account status
  - Enable API access in account settings

### **Debug Mode:**
Enable detailed logging in `appsettings.json`:
```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Debug",
      "WheelStrategy.IBKR": "Debug"
    }
  }
}
```

## 🔒 **Security Considerations**

### **Production Deployment:**
1. **Use IB Gateway** instead of TWS for production
2. **Secure Network**: Use VPN or private network
3. **Firewall**: Restrict access to IBKR ports
4. **Credentials**: Store securely, never in code
5. **Monitoring**: Set up alerts for connection issues

### **Paper Trading First:**
- Test with paper trading before live
- Verify all functionality works
- Check risk management settings
- Monitor for any issues

## 📊 **Verification Checklist**

### **✅ Connection Test:**
- [ ] TWS/Gateway running
- [ ] API enabled
- [ ] Port configured correctly
- [ ] Application connects successfully
- [ ] No connection errors in logs

### **✅ Data Verification:**
- [ ] Account summary loads
- [ ] Positions display correctly
- [ ] Market data updates
- [ ] No sample data indicators
- [ ] Real-time updates working

### **✅ Trading Verification:**
- [ ] Orders can be placed
- [ ] Position management works
- [ ] Risk checks active
- [ ] Alerts functioning
- [ ] Dashboard responsive

## 🎯 **Next Steps**

### **After Successful Connection:**

1. **Test Paper Trading:**
   - Place test orders
   - Verify position management
   - Check risk controls

2. **Configure Alerts:**
   - Set up email/SMS notifications
   - Configure risk thresholds
   - Test alert system

3. **Monitor Performance:**
   - Track execution quality
   - Monitor system stability
   - Review logs regularly

4. **Go Live (When Ready):**
   - Switch to live account
   - Start with small positions
   - Monitor closely initially

## 📞 **Support**

### **If Issues Persist:**
1. Check IBKR API documentation
2. Review application logs
3. Verify network connectivity
4. Contact IBKR support if needed

### **Useful Commands:**
```bash
# Check if port is in use
lsof -i :7496

# Kill existing processes
lsof -ti:7001 | xargs kill -9

# Test connection
curl http://localhost:7001/api/dashboard/metrics

# View logs
tail -f logs/app.log
```

---

**🎉 Congratulations!** Your .NET Wheel Strategy system is now connected to real IBKR data and ready for live trading! 