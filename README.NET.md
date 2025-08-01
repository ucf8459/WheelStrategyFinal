# Wheel Strategy System - .NET Migration

This is a complete migration of the Python wheel strategy trading system to .NET 8. The system provides automated wheel strategy monitoring, opportunity scanning, and trade execution with IBKR integration.

## 🏗️ Architecture

### Solution Structure
```
WheelStrategy.NET/
├── src/
│   ├── WheelStrategy.Core/           # Core domain models and interfaces
│   ├── WheelStrategy.IBKR/           # IBKR integration layer
│   ├── WheelStrategy.Web/            # Web dashboard (ASP.NET Core)
│   └── WheelStrategy.Console/        # Console application
├── tests/
│   └── WheelStrategy.Tests/          # Unit tests
├── appsettings.json                  # Configuration
└── WheelStrategy.NET.sln            # Solution file
```

### Key Components

#### Core Layer (`WheelStrategy.Core`)
- **Models**: Domain entities (WheelPosition, Alert, Decision, etc.)
- **Interfaces**: Service contracts (IWheelMonitor, IWheelScanner, etc.)
- **Configuration**: Options classes for system configuration
- **Services**: Core business logic implementations

#### IBKR Integration (`WheelStrategy.IBKR`)
- **ConnectionService**: Manages multiple IBKR connections with unique client IDs
- **MarketDataService**: Provides real-time market data and Greeks
- **TradeExecution**: Handles order placement and management

#### Web Dashboard (`WheelStrategy.Web`)
- **SignalR Hub**: Real-time updates to connected clients
- **API Controllers**: REST endpoints for dashboard data
- **Configuration**: Dependency injection and service registration

#### Console Application (`WheelStrategy.Console`)
- **Monitoring Loop**: Continuous portfolio monitoring
- **Alert System**: Real-time notifications
- **Logging**: Comprehensive system logging

## 🚀 Getting Started

### Prerequisites
- **.NET 8 SDK** (latest version)
- **Interactive Brokers Account** (paper or live)
- **TWS or IB Gateway** (running and configured)
- **Visual Studio 2022** or **VS Code** (recommended)

### Installation

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd WheelStrategy.NET
   ```

2. **Restore Dependencies**
   ```bash
   dotnet restore
   ```

3. **Build the Solution**
   ```bash
   dotnet build
   ```

4. **Configure IBKR**
   - Launch TWS or IB Gateway
   - Enable API connections (Configure → API → Enable ActiveX and Socket Clients)
   - Set Socket Port to 7496 (paper) or 7497 (live)
   - Add 127.0.0.1 to trusted IPs

5. **Update Configuration**
   Edit `appsettings.json` to match your IBKR settings:
   ```json
   {
     "WheelStrategy": {
       "IBKR": {
         "Host": "127.0.0.1",
         "Port": 7496,
         "UsePaperTrading": true
       }
     }
   }
   ```

## 🏃‍♂️ Running the System

### Console Application
```bash
cd src/WheelStrategy.Console
dotnet run
```

### Web Dashboard
```bash
cd src/WheelStrategy.Web
dotnet run
```
Then open: `http://localhost:7001`

### Running Tests
```bash
cd tests/WheelStrategy.Tests
dotnet test
```

## 📊 Features

### Core Functionality
- **Real-time Portfolio Monitoring**: Live P&L, positions, and metrics
- **Wheel Strategy Tracking**: Complete cycle tracking (puts → shares → calls)
- **Opportunity Scanning**: Automated screening for new trades
- **Risk Management**: Position sizing and sector limits
- **Market Analysis**: VIX integration and regime detection

### IBKR Integration
- **Multi-Connection Architecture**: Separate connections for monitor, scanner, executor
- **Real-time Market Data**: Live quotes, Greeks, and account information
- **Order Management**: Automated trade execution with safety checks
- **Connection Resilience**: Automatic reconnection and error handling

### Web Dashboard
- **Real-time Updates**: SignalR-powered live data streaming
- **Portfolio Overview**: Account value, P&L, cash percentage
- **Position Tracking**: Active wheel positions with Greeks
- **Opportunity Display**: Screened trading opportunities
- **Alert System**: Real-time notifications and alerts

### Risk Management
- **Position Sizing**: Configurable percentage limits per position
- **Sector Limits**: Dynamic sector allocation based on VIX
- **Drawdown Protection**: Circuit breakers and stop losses
- **IV Requirements**: Minimum IV rank and absolute IV thresholds
- **Earnings Buffer**: No trades near earnings dates

## ⚙️ Configuration

### IBKR Settings
```json
{
  "IBKR": {
    "Host": "127.0.0.1",
    "Port": 7496,
    "ClientId": 1,
    "UsePaperTrading": true
  }
}
```

### Risk Thresholds
```json
{
  "RiskThresholds": {
    "MaxPositionPercentage": 0.10,
    "MaxSectorPercentage": 0.20,
    "DrawdownStop": 0.20,
    "IVRankMinimum": 50,
    "ProfitTarget": 0.50,
    "RollDTE": 21
  }
}
```

### Watchlist
```json
{
  "Watchlist": [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "JPM", "BAC", "WFC", "C",
    "SPY", "QQQ", "IWM"
  ]
}
```

## 🔧 Development

### Project Structure
- **Clean Architecture**: Separation of concerns with clear boundaries
- **Dependency Injection**: Microsoft.Extensions.DependencyInjection
- **Configuration**: Microsoft.Extensions.Configuration
- **Logging**: Microsoft.Extensions.Logging
- **Async/Await**: Full async support throughout

### Key Design Patterns
- **Repository Pattern**: Data access abstraction
- **Factory Pattern**: Service creation and configuration
- **Observer Pattern**: Real-time updates via SignalR
- **Strategy Pattern**: Different execution strategies
- **Builder Pattern**: Complex object construction

### Testing Strategy
- **Unit Tests**: xUnit framework
- **Mocking**: Moq for dependency mocking
- **Assertions**: FluentAssertions for readable tests
- **Coverage**: Coverlet for code coverage

## 🔄 Migration from Python

### Key Improvements
1. **Type Safety**: Strong typing throughout the system
2. **Performance**: Better memory management and async patterns
3. **Scalability**: Better support for microservices architecture
4. **Maintainability**: Clean architecture and dependency injection
5. **Testing**: Better unit testing support with mocking

### Feature Parity
- ✅ Real-time IBKR integration
- ✅ Wheel strategy monitoring
- ✅ Opportunity scanning
- ✅ Risk management
- ✅ Web dashboard
- ✅ Alert system
- ✅ Trade execution

### Enhanced Features
- 🔄 Better error handling and resilience
- 🔄 Improved configuration management
- 🔄 Enhanced logging and monitoring
- 🔄 More robust connection management
- 🔄 Better separation of concerns

## 🛡️ Security & Safety

### Paper Trading Support
- Configure `UsePaperTrading: true` for safe testing
- All orders go through paper account first
- No real money at risk during development

### Risk Controls
- Position size limits per symbol
- Sector concentration limits
- Drawdown protection
- Circuit breakers for extreme conditions

### Error Handling
- Comprehensive exception handling
- Automatic reconnection to IBKR
- Graceful degradation on failures
- Detailed logging for debugging

## 📈 Performance

### Optimizations
- **Async Operations**: Non-blocking I/O throughout
- **Connection Pooling**: Reuse IBKR connections
- **Caching**: Cache frequently accessed data
- **Lazy Loading**: Load data only when needed
- **Background Services**: Continuous monitoring

### Monitoring
- **Application Insights**: Azure monitoring (optional)
- **Structured Logging**: JSON format logs
- **Performance Counters**: System metrics
- **Health Checks**: Service health monitoring

## 🚨 Troubleshooting

### Common Issues

#### IBKR Connection Problems
```bash
# Check if TWS/Gateway is running
# Verify API settings are enabled
# Confirm port settings match configuration
# Check firewall rules
```

#### Build Errors
```bash
# Clean and rebuild
dotnet clean
dotnet restore
dotnet build
```

#### Runtime Errors
```bash
# Check logs
tail -f logs/wheel-strategy.log

# Verify configuration
cat appsettings.json
```

### Debug Mode
```bash
# Run with detailed logging
dotnet run --environment Development

# Enable debug output
set ASPNETCORE_ENVIRONMENT=Development
```

## 📚 Documentation

### API Reference
- **Dashboard API**: `/api/dashboard/*`
- **SignalR Hub**: `/dashboardHub`
- **Configuration**: `appsettings.json`

### Architecture Diagrams
- System overview
- Data flow
- Component relationships
- Deployment architecture

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## ⚠️ Disclaimer

**This software is for educational and research purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results. The authors are not responsible for any trading losses incurred using this system.**

---

**Built with ❤️ using .NET 8 for systematic options trading** 