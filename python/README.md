# Wheel Strategy Trading System

A comprehensive, automated wheel strategy trading system with real-time portfolio monitoring, IBKR integration, and intelligent option screening.

## 🚀 Features

### Core Trading System
- **Automated Wheel Strategy** - Systematic cash-secured puts and covered calls
- **Real-time IBKR Integration** - Live market data and order execution
- **Intelligent Option Screening** - Pre-market and after-hours analysis
- **Risk Management** - Position sizing and automated alerts
- **Multi-timeframe Analysis** - Support for various expiration cycles

### Web Dashboard
- **Real-time Portfolio Tracking** - Live P&L, positions, and metrics
- **Interactive Charts** - Visual analysis with Chart.js
- **Socket.IO Updates** - Real-time data streaming
- **Responsive Design** - Works on desktop and mobile
- **Live Market Data** - Real-time quotes and Greeks

### Advanced Features
- **VIX-based Market Analysis** - Market sentiment integration
- **Email & SMS Alerts** - Configurable notifications
- **Paper Trading Support** - Risk-free testing environment
- **Comprehensive Logging** - Detailed trade and system logs
- **Database Integration** - Trade history and analytics

## 📋 Prerequisites

- **Python 3.8+** (tested with Python 3.13)
- **Interactive Brokers Account** - Paper or live trading
- **TWS or IB Gateway** - Running and connected
- **Virtual Environment** - Recommended for isolation

## 🛠 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/ucf8459/WheelStrategyFinal.git
cd WheelStrategyFinal
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:
```env
# IBKR Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7496
IBKR_CLIENT_ID=1

# Optional Email Alerts
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=alerts@gmail.com
EMAIL_PASSWORD=your-app-password

# Optional SMS Alerts (Twilio)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+1234567890
```

## 🚀 Quick Start

### 1. Start TWS/IB Gateway
- Launch TWS or IB Gateway
- Enable API connections (Configure → API → Enable ActiveX and Socket Clients)
- Set Socket Port to 7496 (paper) or 7497 (live)
- Create trusted IP: 127.0.0.1

### 2. Run the System
```bash
source venv/bin/activate
python complete-wheel-strategy-system.py
```

### 3. Access Dashboard
Open your browser and navigate to:
```
http://localhost:7001
```

## 📊 Dashboard Features

### Portfolio Overview
- **Account Value** - Real-time net liquidation value
- **Available Funds** - Cash available for trading
- **Unrealized P&L** - Current position gains/losses
- **Cash Percentage** - Portfolio allocation metrics

### Live Positions
- **Stock Holdings** - Current equity positions
- **Option Positions** - Active puts and calls with Greeks
- **P&L Tracking** - Real-time profit/loss analysis
- **Risk Metrics** - Position sizing and exposure

### Market Analysis
- **Option Opportunities** - Screened wheel strategy candidates
- **VIX Integration** - Market volatility analysis
- **Technical Indicators** - Support and resistance levels
- **Volume Analysis** - Liquidity and momentum metrics

## ⚙️ Configuration

### Symbol Watchlist
The system monitors a curated list of liquid, optionable stocks including:
- **Blue Chips**: AAPL, MSFT, GOOGL, AMZN, TSLA
- **Banking**: JPM, BAC, WFC, C
- **Tech**: NVDA, META, NFLX, CRM
- **ETFs**: SPY, QQQ, IWM

### Risk Parameters
- **Position Sizing**: Configurable percentage of portfolio
- **Delta Targets**: Optimal Greeks for entry/exit
- **DTE Management**: Days to expiration thresholds
- **Profit Targets**: Automated profit-taking levels

## 🔧 Advanced Usage

### Customizing Screening Criteria
Edit the screening parameters in `complete-wheel-strategy-system.py`:
```python
# Option screening filters
MIN_VOLUME = 100
MIN_OPEN_INTEREST = 50
MAX_BID_ASK_SPREAD = 0.05
TARGET_DELTA = 0.30
```

### Adding New Symbols
Update the watchlist in the configuration:
```python
SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN',
    # Add your symbols here
]
```

### Alert Configuration
Configure alerts for specific events:
- New wheel opportunities
- Position assignments
- Profit target hits
- Risk threshold breaches

## 📈 Strategy Overview

### The Wheel Strategy
1. **Sell Cash-Secured Puts** - Generate income while waiting for assignment
2. **Stock Assignment** - Acquire shares at a discount if put expires ITM
3. **Sell Covered Calls** - Generate additional income on assigned shares
4. **Share Assignment** - Profit from appreciation if call expires ITM
5. **Repeat Cycle** - Continuous income generation

### Risk Management
- **Position Sizing** - Never risk more than X% on a single trade
- **Diversification** - Spread risk across multiple underlyings
- **Delta Management** - Maintain appropriate directional exposure
- **Volatility Consideration** - Adjust strategy based on VIX levels

## 🔍 Monitoring & Alerts

### Real-time Monitoring
- **Portfolio Updates** - Every 30 seconds during market hours
- **Option Chain Refresh** - Live Greeks and pricing
- **Market Data** - Real-time quotes and volume
- **System Health** - Connection and error monitoring

### Alert Types
- **Email Notifications** - Trade confirmations and opportunities
- **SMS Alerts** - Critical events and risk warnings
- **Dashboard Notifications** - Real-time status updates
- **Log Files** - Comprehensive audit trail

## 🛡️ Security & Safety

### Paper Trading
- **Risk-Free Testing** - Use paper account for initial testing
- **Strategy Validation** - Verify logic before live trading
- **Performance Analysis** - Track historical results

### Risk Controls
- **Position Limits** - Maximum exposure per symbol
- **Loss Limits** - Stop-loss mechanisms
- **Timeout Controls** - Prevent runaway algorithms
- **Manual Override** - Emergency stop functionality

## 📝 Logging & Analytics

### System Logs
- **Trade Execution** - Order details and fills
- **Market Data** - Price and volume tracking
- **System Events** - Connections and errors
- **Performance Metrics** - Strategy effectiveness

### Analytics Dashboard
- **P&L Analysis** - Historical performance tracking
- **Win Rate** - Success percentage by strategy
- **Risk Metrics** - Sharpe ratio and drawdown analysis
- **Market Correlation** - Strategy performance vs market

## 🚨 Troubleshooting

### Common Issues

#### Dashboard Not Loading
```bash
# Check if port 7001 is available
lsof -i :7001

# Kill conflicting processes
pkill -f "python.*complete-wheel-strategy"

# Restart the system
python complete-wheel-strategy-system.py
```

#### IBKR Connection Issues
1. Verify TWS/Gateway is running
2. Check API settings are enabled
3. Confirm correct port (7496/7497)
4. Validate client ID is unique

#### Missing Data
1. Check market hours (system pauses when closed)
2. Verify internet connection
3. Confirm IBKR subscriptions are active
4. Review log files for errors

### Log File Locations
- **System Logs**: `logs/wheel_strategy.log`
- **Trade Logs**: `logs/trades.log`
- **Error Logs**: `logs/errors.log`

## 📚 Documentation

- **[Configuration Guide](CONFIGURATION.md)** - Detailed setup instructions
- **[Training Manual](wheel_training_manual-2.md)** - Strategy education
- **[SOPs](updated_sop.md)** - Standard operating procedures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

**This software is for educational and research purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results. The authors are not responsible for any trading losses incurred using this system.**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For support, questions, or feature requests:
- **Issues**: [GitHub Issues](https://github.com/ucf8459/WheelStrategyFinal/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ucf8459/WheelStrategyFinal/discussions)

## 🎯 Roadmap

### Upcoming Features
- [ ] Advanced Greeks analysis
- [ ] Machine learning price prediction
- [ ] Multi-account support
- [ ] Mobile app development
- [ ] Backtesting framework
- [ ] Social trading integration

---

**Built with ❤️ for systematic options trading** 