# Wheel Strategy System Configuration

## IBKR API Client ID Ranges

The system uses different client ID ranges for each component to prevent conflicts:

| Component | ID Range    | Purpose |
|-----------|------------|---------|
| Monitor   | 10000-10999| Main monitoring component, handles market data and position tracking |
| Scanner   | 11000-11999| Opportunity scanner, searches for new trading opportunities |
| Executor  | 12000-12999| Trade execution component, handles order placement and management |

### Why These Ranges?
- Each component needs its own connection to IBKR
- Using separate ranges prevents client ID conflicts
- Large ranges allow for multiple instances if needed
- Starting at 10000+ avoids conflicts with common low-number IDs

## Port Configuration

| Environment | Port | Purpose |
|-------------|------|---------|
| Live Trading | 7496 | IBKR TWS/Gateway connection |
| Paper Trading | 7497 | IBKR Paper Trading connection |
| Dashboard | 7001 | Web interface for monitoring |

## Component Architecture

### Monitor Component (10000-10999)
- Handles real-time market data subscription
- Tracks position status and P&L
- Manages risk metrics and circuit breakers
- Updates account summary and portfolio metrics
- Runs on main event loop with 30-second refresh

### Scanner Component (11000-11999)
- Searches for new wheel strategy opportunities
- Calculates IV metrics and option chains
- Performs technical analysis
- Validates entry criteria
- Independent connection to avoid blocking main monitor

### Executor Component (12000-12999)
- Handles all order placement and management
- Manages position rolls and adjustments
- Implements smart order routing
- Separate connection for reliable order execution
- Critical for maintaining order state independence

## System Requirements

### IBKR TWS/Gateway Setup
1. Enable API connections in TWS/Gateway
   - File > Global Configuration > API > Settings
   - Check "Enable ActiveX and Socket Clients"
   - Set "Socket port" to match environment (7496/7497)
   - Allow "127.0.0.1" in trusted IPs

### Required Python Environment
- Python 3.7+
- Virtual environment recommended
- Key dependencies:
  - ib_insync for IBKR connectivity
  - Flask for web dashboard
  - pandas for data analysis
  - yfinance for supplementary data

## Environment Variables
Required variables in `.env` file:
```
# IBKR Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7496  # or 7497 for paper trading

# Optional Email Alerts
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=your-email@gmail.com
EMAIL_PASSWORD=your-app-specific-password

# Optional SMS Alerts
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+0987654321
```

## Web Dashboard
- Accessible at http://localhost:7001
- Updates every 30 seconds
- Shows:
  - Real-time position data
  - Account metrics and P&L
  - Active alerts and warnings
  - New trading opportunities
  - Performance charts

## Performance Considerations

### Memory Usage
- Each IBKR connection maintains its own market data cache
- Monitor component typically uses 100-200MB
- Scanner and Executor use 50-100MB each
- Dashboard web server uses minimal memory

### Network Requirements
- Stable connection to IBKR TWS/Gateway required
- Typical bandwidth usage:
  - Monitor: ~100KB/s during market hours
  - Scanner: Bursts during scans
  - Executor: Minimal except during trades

### Error Handling
- Components will attempt to reconnect on failure
- Each component has its own error recovery
- Critical errors trigger alerts
- Circuit breakers protect during extreme conditions

## Monitoring and Maintenance

### Log Files
- Each component writes to its own log file
- Default location: `logs/` directory
- Log rotation: 7 days retention
- Critical errors trigger immediate alerts

### Health Checks
- Dashboard shows component status
- Connection health monitored
- Automatic reconnection attempts
- Alert on component failures

### Backup and Recovery
- Position data backed up every 30 minutes
- Configuration backed up on changes
- Recovery procedures documented
- Database backups for trade history

## Security Notes
- Keep .env file secure and never commit to git
- Use app-specific passwords for email
- Restrict TWS/Gateway API access to localhost
- Regular audit of active connections
- Monitor API connection logs

## Troubleshooting

### Common Issues
1. Client ID conflicts
   - Check TWS API connections
   - Verify no other instances running
   - Clear stale connections in TWS

2. Connection failures
   - Verify TWS/Gateway is running
   - Check API permissions
   - Confirm port settings
   - Check firewall rules

3. Data delays
   - Verify market data subscriptions
   - Check network latency
   - Monitor system resources

### Recovery Steps
1. Stop all components
2. Restart TWS/Gateway
3. Clear API connection list
4. Restart components in order:
   - Monitor
   - Scanner
   - Executor 