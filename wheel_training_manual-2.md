## Stock Selection

### Using the Sector-Diversified Watchlist

The system includes a comprehensive sector-diversified watchlist of 100+ pre-vetted stocks specifically selected for wheel strategy suitability. This watchlist is organized by sector and includes important metrics for each candidate.

**Key Benefits of the Watchlist:**
- Pre-filtered for liquidity, IV characteristics, and fundamentals
- Balanced across all 11 market sectors
- Includes different market cap tiers within each sector
- Provides rationale for why each stock is appropriate for the wheel

**How to Use the Watchlist:**

1. **Account Size Matching**
   - Under $100k: Focus on large-cap names and ETFs only
   - $100k-$250k: Include mid-caps from core sectors
   - $250k+: Utilize the full watchlist for maximum diversification

2. **Sector Rotation Navigation**
   - Overweight sectors showing relative strength in bull markets
   - Rotate toward defensive sectors in bear markets
   - Use sector ETFs for broader exposure with less stock-specific risk

3. **IV Rank Targeting**
   - Higher IV Rank stocks (50-70%) for aggressive premium collection
   - Lower IV Rank stocks (30-50%) for more conservative positions
   - Match IV profile to your current strategy objectives

4. **Watchlist Maintenance**
   - The watchlist is updated quarterly based on:
     - Liquidity changes
     - Fundamental developments
     - Technical conditions
     - Sector performance

**Sector Category Guidelines:**

| Sector | Market Characteristics | When to Overweight | When to Underweight |
|--------|------------------------|--------------------|--------------------|
| Technology | Higher growth, higher volatility | Bull markets | Bear markets |
| Financials | Rate sensitive, cyclical | Rising rate environments | Flattening yield curve |
| Healthcare | Defensive, policy sensitive | Market uncertainty | Strong bull markets |
| Consumer Disc. | Cyclical, consumer sentiment | Strong economy | Recession concerns |
| Consumer Staples | Defensive, lower volatility | Bearish environments | Strong bull markets |
| Industrials | Economic cycle sensitive | Early cycle recovery | Late cycle/recession |
| Energy | Commodity price sensitive | Inflation periods | Demand destruction |
| Materials | Cyclical, commodity linked | Early expansion | Late cycle |
| Utilities | Defensive, rate sensitive | Bearish, falling rates | Rising rate environments |
| Real Estate | Income focused, rate sensitive | Stable/falling rates | Rapidly rising rates |
| Communication | Mixed defensive/growth | Neutral markets | Varies by component |

**Best Practices:**
1. Start with 3-5 sectors you understand best
2. Add 1-2 stocks from each selected sector
3. Use the sector exposure calculator to maintain balance
4. Review sector performance quarterly to adjust allocations# True Wheel Strategy System
## Comprehensive Training Manual

## Table of Contents
1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Getting Started](#getting-started)
4. [Dashboard Overview](#dashboard-overview)
5. [Daily Workflow](#daily-workflow)
6. [Decision Making Process](#decision-making-process)
7. [Risk Management Tools](#risk-management-tools)
8. [Performance Tracking](#performance-tracking)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Features](#advanced-features)
11. [Glossary](#glossary)
12. [FAQ](#faq)

---

## Introduction

### What is the True Wheel Strategy System?

The True Wheel Strategy System is a fully optimized, automated trading platform designed for retail options traders. It implements the Wheel Strategy with sophisticated risk management, market regime adaptation, and decision support features. The system automates monitoring and alerting while leaving final trading decisions to you.

### Core Philosophy

1. **Process Over Profits**: Perfect execution of rules outweighs short-term P&L.
2. **Stock Owner First, Option Seller Second**: Only trade stocks you'd want to own.
3. **Assignment is Inventory, Not Failure**: Covered calls generate income while you hold shares.
4. **Simplicity is Edge**: CSP and CC only - no complex multi-leg strategies.
5. **Protect Capital at All Costs**: Strict risk management, position sizing, and circuit breakers.

### System Benefits

- **Reduced Emotion**: Clear, data-driven decisions eliminate emotional trading.
- **Time Efficiency**: Automated monitoring with prioritized alerts saves hours daily.
- **Consistent Execution**: Built-in checklists and protocols ensure rule adherence.
- **Market Adaptation**: Automatically adjusts to bull, bear, and neutral markets.
- **Risk Control**: Multi-layered risk management prevents catastrophic losses.

---

## System Requirements

### Technical Requirements

- **Brokerage Account**: Interactive Brokers account with API access
- **Options Approval**: Level 3 options approval (cash-secured puts, covered calls)
- **Minimum Capital**: $25,000 recommended ($10,000 minimum)
- **Computer**: Any modern Windows, Mac, or Linux computer
- **Internet**: Reliable broadband connection
- **Python**: Python 3.8+ with required libraries

### Installation Requirements

1. **Interactive Brokers TWS or Gateway**:
   - Configure API access (port 7496 for live, 7497 for paper)
   - Enable market data subscriptions
   
2. **Python Environment**:
   - Install required packages: `pip install -r requirements.txt`
   - Verify ib_insync connectivity

3. **Configuration**:
   - Update `config.py` with your account details
   - Set watchlist symbols
   - Configure alert preferences (email, SMS)

---

## Getting Started

### Initial Setup

1. **Clone Repository**:
   ```
   git clone https://github.com/your-username/wheel-strategy-system.git
   cd wheel-strategy-system
   ```

2. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Configure System**:
   - Edit `config.py` with your specific settings
   - Update watchlist with your preferred symbols
   - Set email/SMS notification preferences

4. **Start IBKR Platform**:
   - Launch TWS or IB Gateway
   - Log in to your account
   - Ensure API connectivity is enabled

5. **Run Initial Setup**:
   ```
   python setup.py
   ```
   This will:
   - Validate connectivity
   - Initialize database
   - Generate initial watchlist data
   - Set up logging

6. **Launch System**:
   ```
   python main.py
   ```

7. **Access Dashboard**:
   - Open web browser to `http://localhost:5000`
   - Verify all components are connected

### Configuration Options

#### Core Strategy Settings
```python
'strategy': {
    'mode': 'hybrid',  # 'income', 'growth', or 'hybrid'
    'allow_earnings_trades': True,  # Post-earnings IV crush
    'use_seasonality': True,
    'track_correlations': True,
    'max_daily_decisions': 3,
    'enable_pair_trades': True
}
```

#### Risk Management Settings
```python
'thresholds': {
    'max_position_pct': 0.10,      # 10% max per position
    'max_sector_pct': 0.20,        # 20% max per sector
    'drawdown_stop': 0.20,         # 20% from peak circuit breaker
    'weekly_drawdown_stop': 0.10,  # 10% weekly circuit breaker
    'earnings_buffer_days': 7,     # No trades near earnings
    'correlation_threshold': 0.80, # Correlation crisis level
    'win_streak_caution': 10       # Wins before size reduction
}
```

---

## Dashboard Overview

The dashboard is your command center for monitoring and managing the Wheel Strategy. Here's a breakdown of each section:

### Portfolio Overview
![Portfolio Overview](portfolio_overview.png)

This section provides a high-level view of your account:
- **Account Value**: Current total portfolio value
- **Cash Available**: Liquid funds available for new positions
- **Realized P&L**: Profit/loss from closed positions
- **Premium Collected**: Option premium income
- **Win Rate**: Percentage of profitable trades
- **Active Positions**: Current position count vs maximum

**Key Metrics to Monitor:**
- Premium collected vs monthly target
- Win rate (target: >75%)
- Cash utilization (target: 75-95%)

### Active Positions
![Active Positions](active_positions.png)

This table shows all your current positions with key metrics:
- **Symbol**: Underlying stock
- **Type**: CSP, CC, or Shares
- **Strike**: Option strike price
- **Expiry**: Expiration date
- **DTE**: Days to expiration
- **Premium**: Credit received
- **P&L %**: Current profit/loss
- **Delta**: Current option delta
- **Action**: Available actions for the position

**Color Coding:**
- **Green**: Positions with >40% profit
- **Yellow**: Positions requiring monitoring
- **Red**: Positions requiring immediate action

### Decision Support
![Decision Support](decision_support.png)

This section prioritizes actions needed today:
- **CRITICAL**: Actions needed immediately (deep ITM positions, high delta)
- **IMPORTANT**: Time-sensitive but not urgent (profit targets, DTE thresholds)
- **INFO**: Opportunities and informational alerts

**Decision Limit Counter:**
- Tracks decisions made today vs maximum (default: 3)
- Resets at midnight ET

### Market Conditions
![Market Conditions](market_conditions.png)

Provides current market data impacting strategy decisions:
- **VIX**: Current value and percentile
- **Regime**: BULL, BEAR, or NEUTRAL
- **Correlation**: Cross-sector correlation
- **A/D Ratio**: Market breadth indicator

**Sector Exposure:**
- Visual breakdown of sector allocation
- Comparison to VIX-adjusted limits

### Opportunity Scanner
![Opportunity Scanner](opportunity_scanner.png)

Displays new trading opportunities meeting all criteria:
- Filtered by liquidity, IV rank, and valuation
- Sorted by expected return
- Pre-checked for earnings conflicts
- Respects sector concentration limits

**Quality Indicators:**
- Return percentage (annualized)
- IV rank and percentile
- Post-earnings opportunities

### Sector Opportunity Screener
![Sector Opportunity Screener](sector_screener.png)

This specialized screener helps maintain optimal sector diversification:
- Identifies underweight sectors with allocation gaps
- Suggests best opportunities in sectors needing exposure
- Adjusts targets based on market regime
- Detects sector rotation patterns

**Key Components:**
- **Sector Gap Analysis**: Shows current allocation vs. target range
- **Opportunity Ranking**: Multi-factor scoring of opportunities in underweight sectors
- **Sector Rotation Detection**: Identifies sectors gaining/losing momentum
- **Regime-Based Targets**: Adjusts sector allocation targets based on market conditions

### System Status
![System Status](system_status.png)

Shows health of all system components:
- **Circuit Breaker**: Active/Inactive
- **Black Swan Protocol**: Active/Inactive and stage
- **API Connection**: Connection status
- **Workflow Status**: Morning/Afternoon/EOD routine completion

---

## Daily Workflow

The system is designed around a structured daily workflow that maximizes efficiency while ensuring proper risk management. Follow these routines for optimal results.

### Morning Routine (9:00 AM ET)

**Purpose**: Review overnight market changes, plan day's actions, check for immediate concerns.

#### System Actions
- Analyzes overnight futures and global markets
- Identifies positions requiring attention
- Checks earnings announcements (7-day forward)
- Scans for new opportunities
- Checks sector exposure and correlation

#### Your Actions
1. **Check Alerts (2 min)**
   - Review any CRITICAL alerts first
   - Note IMPORTANT items for afternoon action
   
2. **Review Portfolio Overview (2 min)**
   - Check account value vs previous day
   - Note premium collected vs monthly target
   
3. **Check Market Conditions (2 min)**
   - Note VIX level and percentile
   - Confirm market regime
   - Check correlation levels
   
4. **Plan Day's Actions (3-5 min)**
   - Identify up to 3 key decisions for the day
   - Prioritize by importance (critical → important → info)
   - Avoid overtrading - less is more

**Expected Time**: 10-15 minutes total

### Afternoon Check-in (2:30 PM ET)

**Purpose**: Execute planned actions during optimal market liquidity.

#### System Actions
- Refreshes all position data
- Rechecks profit targets and roll conditions
- Updates opportunity scanner
- Prepares roll recommendations

#### Your Actions
1. **Execute Planned Actions (5-10 min)**
   - Focus on the 1-3 decisions identified in morning
   - Use limit orders with fill improvement protocol
   - Document trade rationale

2. **Check 80% Profit Rolls (2 min)**
   - Review positions highlighted for efficiency rolls
   - Execute if conditions still favorable

3. **Check Earnings Calendar (2 min)**
   - Confirm next-day earnings
   - Plan pre-earnings adjustments if needed

**Expected Time**: 10-15 minutes total

### End of Day Routine (4:00 PM ET)

**Purpose**: Log daily results, set overnight alerts, prepare for next day.

#### System Actions
- Calculates daily P&L
- Updates performance metrics
- Checks for circuit breaker conditions
- Generates next-day watch list

#### Your Actions
1. **Review Day's Performance (3 min)**
   - Check daily P&L
   - Review executed actions
   
2. **Prepare for Tomorrow (5 min)**
   - Note pre-market earnings
   - Review next day's potential actions
   - Set any custom alerts

3. **Journal Key Observations (2 min)**
   - Document anything unusual or noteworthy
   - Note any insights for improvement

**Expected Time**: 10 minutes total

### Weekly Review (Friday 4:30 PM ET)

**Purpose**: Analyze weekly performance, adjust strategy if needed.

#### System Actions
- Generates weekly performance summary
- Compares results vs benchmark
- Analyzes rule effectiveness
- Updates market regime indicators

#### Your Actions
1. **Review Performance Metrics (5 min)**
   - Compare win rate, Sharpe ratio to targets
   - Check sector performance

2. **Plan for Next Week (5 min)**
   - Note upcoming earnings season impacts
   - Review capital allocation

3. **Strategy Adjustment (if needed) (5 min)**
   - Consider delta targets based on regime
   - Check if evolution triggers have been hit

**Expected Time**: 15-20 minutes total

---

## Decision Making Process

The Wheel Strategy System is designed to automate monitoring while leaving final trading decisions to you. Here's a structured approach to making optimal decisions.

### CSP Entry Decisions

**When the system suggests a new CSP opportunity:**

1. **Verify Entry Criteria**
   - Confirm IV Rank > 50% ✓
   - Confirm stock valuation is reasonable ✓
   - Check sector concentration limits ✓
   - Verify not near earnings ✓

2. **Check Market Conditions**
   - In bull market? Consider 30-40 delta strikes
   - In neutral market? Consider 25-30 delta strikes
   - In bear market? Consider 15-25 delta strikes

3. **Stock Owner Mindset Check**
   - Would you want to own this stock if assigned?
   - Is the strike price a good long-term value?
   - Does it fit your portfolio strategy?

4. **Sector Balance Check**
   - Use the Sector Opportunity Screener to identify underweight sectors
   - Prioritize opportunities in sectors with largest allocation gaps
   - Compare expected returns across sectors for optimal allocation

5. **Timing Check**
   - Is this one of the optimal trading windows? (10-11 AM or 2-3 PM ET)
   - Is it Tuesday-Thursday? (avoid Monday/Friday if possible)
   - Has the market been stable in the last hour?

6. **Execution**
   - Use the Fill Improvement Protocol
   - Start at mid-price and adjust every 2 minutes
   - Maximum 3 adjustments before canceling

### Rolling Decisions

**When the system recommends rolling a position:**

1. **Verify Roll Condition**
   - Delta > 0.50? Roll defensively
   - At 21 DTE? Roll for time management
   - At 80%+ profit with >7 DTE? Roll for efficiency

2. **Check Roll Matrix**
   - Review pre-calculated target in roll matrix
   - Verify credit available (never roll for debit)

3. **Underlying Analysis**
   - Has the original thesis changed?
   - Would you still want assignment at the strike?

4. **Roll Execution**
   - For defensive rolls: Roll to ~0.30 delta
   - For time-based rolls: Same strike, next monthly
   - For profit rolls: Consider rolling down slightly

### Assignment Decisions

**When a position is likely to be assigned:**

1. **Pre-Assignment Planning**
   - Verify you still want the shares
   - Review potential covered call strikes
   - Check ex-dividend dates

2. **Post-Assignment Action**
   - Wait for first green day to sell covered call
   - Target delta based on market regime
   - Set GTC order for Monday if assigned on Friday

3. **Covered Call Management**
   - Close at 50-70% profit when reached
   - Roll at <10 DTE if not hitting profit target
   - Let assign if called away (ready to restart wheel)

### Maximum 3 Decisions Per Day

A critical rule of the system is limiting yourself to a maximum of 3 trading decisions per day. This prevents overtrading and forces prioritization.

**If you need more than 3 decisions:**
- Your position sizing is too small
- Your entry timing is clustered
- You're experiencing strategy drift

---

## Risk Management Tools

The system incorporates multiple layers of risk management to protect your capital in all market conditions.

### Position Sizing Controls

**Standard Limits:**
- Maximum 10% of account per position
- Maximum 20% of account per sector (adjusted by VIX)
- Maximum 2 strikes per underlying (separated by 5%+)

**Market-Based Adjustments:**
- VIX >90th percentile: 50% normal size
- VIX 75-90th percentile: 75% normal size
- VIX <75th percentile: Normal sizing

**Win Streak Adjustments:**
- 8 consecutive wins: Reduce size by 25%
- 10+ consecutive wins: Reduce size by 50%
- Reset after any loss

### Circuit Breaker System

The circuit breaker automatically pauses new trade entry during periods of drawdown.

**Activation Conditions (any of these):**
- 20% drawdown from account peak
- 10% drawdown in a single week
- 3 consecutive losing days

**Protocol When Activated:**
1. Stop all new positions
2. Review existing positions with critical lens
3. Complete post-mortem analysis
4. Wait minimum 5 trading days
5. Re-enter gradually (25% → 50% → 75% → 100%)

### Black Swan Protocol

For extreme market conditions, the Black Swan Protocol provides enhanced protection.

**Activation Conditions (any of these):**
- VIX above 50
- Cross-sector correlation above 0.90
- Market circuit breaker Level 3 (20% decline)

**Immediate Actions:**
1. Close all positions with DTE <14 days
2. Reduce all position sizes by 75%
3. Set stop losses on all shares at -7% from current price
4. Hold minimum 30% cash
5. Suspend normal entry criteria

**Recovery Sequence:**
- Stage 1: 25% position sizing when conditions improve
- Stage 2: 50% position sizing after 5 trading days
- Stage 3: 75% position sizing after 5 more days
- Stage 4: Return to normal operations

### Correlation Crisis Management

When markets become highly correlated, sector diversification loses effectiveness.

**When Correlation >0.80:**
1. Reduce all position sizes by 50%
2. Close weakest performers
3. Focus on uncorrelated sectors (utilities, staples)
4. No new tech/financial positions
5. Increase cash to 20%

**When Correlation >0.90:**
1. Activate full Black Swan Protocol
2. Convert 50% to cash immediately
3. Close all tech and financial positions
4. Maximum 2% position size

### Stop Loss Framework

The system uses a nuanced approach to stop losses that focuses on underlying value rather than option P&L.

**For CSPs:**
- Not based on option P&L percentage (misleading)
- Based on "Do I want this stock at this price?"
- Stop loss if strike >10% above current price

**For Shares:**
- Based on YOUR cost basis, not market price
- Consider selling if 10% below your basis
- Continue selling calls if thesis still valid

**Example of Proper Stop Loss:**
- Sold TSLA $325 put for $5
- TSLA drops to $280 (14% below strike)
- Option shows -200% loss (normal fluctuation)
- Decision: Do I want TSLA at $325 when it's at $280? No → Close or roll

---

## Performance Tracking

The system provides comprehensive performance tracking to help you refine your strategy over time.

### Key Performance Indicators

**Core Metrics:**
- **Win Rate**: Percentage of trades that result in profit
  - Target: >75%
  - Calculation: (Profitable Trades) ÷ (Total Trades)

- **Average Return on Capital**: Return per unit of capital employed
  - Target: >25% annualized
  - Calculation: (Premium Collected) ÷ (Capital Required) × (365 ÷ DTE)

- **Sharpe Ratio**: Risk-adjusted return
  - Target: >1.5
  - Calculation: (Return - Risk Free Rate) ÷ StdDev(Returns)

- **Premium Yield**: Monthly income from options
  - Target: 1-2% of account monthly
  - Calculation: (Monthly Premium) ÷ (Account Value)

### Attribution Analysis

The system tracks which specific rules and decisions contribute most to performance:

**Rule Effectiveness:**
- CSP selection (by delta, DTE, IV rank)
- Rolling decisions (time-based, profit-based, defensive)
- Profit taking (early close vs hold to expiration)
- Assignment handling (hold shares vs roll)

**Market Regime Performance:**
- Bull market returns
- Bear market returns
- Neutral market returns

**Sector Performance:**
- Returns by sector
- Win rate by sector
- Assignment rate by sector

### Weekly Report

Every Friday, the system generates a comprehensive weekly report:

**Performance Section:**
- Week's P&L vs SPY benchmark
- Win rate and average credit received
- Current positions by sector
- Realized vs unrealized P&L

**Risk Analysis Section:**
- VIX-adjusted position utilization
- Correlation trends
- Win streak status
- Drawdown metrics

**Opportunity Section:**
- Top scanner results for next week
- Upcoming earnings to monitor
- Recommended focus areas

### Quarterly Review

Every quarter, conduct a deeper review focusing on:

**Strategy Evolution:**
- Compare performance against benchmarks
- Review rule effectiveness ranking
- Identify underperforming rules
- Test potential strategy adjustments

**Sector Rotation:**
- Adjust sector targets based on performance
- Identify new sector opportunities
- Update valuation parameters

**Position Scaling:**
- Adjust position counts as account grows
- Review position sizing effectiveness
- Update maximum limits

---

## Troubleshooting

### Common Issues and Solutions

#### Connection Problems

**Issue**: System shows "Disconnected" status with IBKR API
**Solutions**:
1. Verify TWS or Gateway is running
2. Check API settings in TWS (File > Global Configuration > API)
3. Confirm port numbers match (default: 7496 live, 7497 paper)
4. Restart TWS and the system
5. Check firewall settings

**Issue**: Market data unavailable or delayed
**Solutions**:
1. Verify market data subscriptions in IBKR
2. Check reqMarketDataType setting (1 for live, 2 for frozen)
3. Restart the market data connection

#### Alert Issues

**Issue**: Not receiving email alerts
**Solutions**:
1. Check spam/junk folder
2. Verify SMTP settings in config
3. Test SMTP connection with test script
4. Check daily alert limit hasn't been reached
5. Try alternative email provider

**Issue**: SMS alerts not coming through
**Solutions**:
1. Verify Twilio account status and balance
2. Check phone number format (include country code)
3. Confirm API keys are correct
4. Test with direct Twilio API call

#### Performance Issues

**Issue**: Dashboard slow to load or update
**Solutions**:
1. Reduce position count if over recommended limits
2. Check system resources (CPU, memory)
3. Optimize database with cleanup script
4. Reduce update frequency in settings

**Issue**: High CPU usage
**Solutions**:
1. Disable automatic opportunity scanning
2. Increase scan interval time
3. Reduce watchlist size
4. Close unnecessary browser tabs

#### Trading Errors

**Issue**: Order placement failures
**Solutions**:
1. Check account permissions for options trading
2. Verify sufficient buying power
3. Confirm contract details are valid
4. Check for corporate actions affecting options
5. Verify order parameters (quantity, price)

**Issue**: Incorrect Greeks or pricing
**Solutions**:
1. Check market data subscription level
2. Verify using real-time data (not delayed)
3. Compare with broker platform values
4. Refresh option chain data

### Technical Recovery Framework

#### Connection Failure Protocol
1. **Automatic Recovery**:
   - System attempts 3 automatic reconnections
   - Switches to backup API endpoint if needed
   - Reports connection status in system log

2. **Manual Trading Mode**:
   - Activates when all reconnection attempts fail
   - Sends critical alerts via all configured channels
   - Generates critical position report for manual handling
   - Highlights positions requiring immediate attention

3. **Post-Recovery Steps**:
   - Position reconciliation between broker and system
   - Data integrity verification
   - Manual confirmation of order status

#### Position Reconciliation After Outage
1. Export positions from broker platform
2. Run reconciliation script to compare with system database
3. Manually adjust any discrepancies
4. Verify all Greeks and calculations after restore

#### Database Backup Protocol
- **Daily Backup**: Automated at 4:30 PM ET
- **Retention Policy**: Rolling 30-day retention
- **Recovery Testing**: Monthly recovery test (first Monday)
- **Backup Location**: Primary in system folder, secondary in cloud storage

#### Recovery Verification Checklist
- [ ] All positions match broker statement
- [ ] All Greeks and calculations accurate
- [ ] Alert system functioning properly
- [ ] No pending/stuck orders
- [ ] Correct account balance and buying power

### Recovery Procedures

#### Emergency Shutdown

If you need to shut down the system quickly:

1. Run emergency stop script:
   ```
   python emergency_stop.py
   ```

2. This will:
   - Cancel all pending orders
   - Disconnect from API
   - Save current state
   - Log the emergency event

3. After resolving the issue:
   ```
   python recovery.py
   ```

#### Database Recovery

If database corruption occurs:

1. Stop the system
2. Run database integrity check:
   ```
   python db_check.py
   ```

3. Restore from backup if needed:
   ```
   python db_restore.py --backup=YYYY-MM-DD
   ```

4. Verify positions match your actual account

#### Connection Recovery

If experiencing persistent connection issues:

1. Switch to backup connection method:
   ```
   python main.py --connection=backup
   ```

2. This uses alternative connection parameters
3. Monitor stability before resuming normal operations

---

## Advanced Features

### Cash Management Protocol

The system includes sophisticated cash management to optimize capital usage while maintaining safety buffers.

**Strategic Cash Reserve Levels:**
- 5% minimum cash buffer at all times
- Additional VIX-responsive reserve:
  - VIX <20: +0% (5% total)
  - VIX 20-30: +5% (10% total)
  - VIX 30-40: +10% (15% total)
  - VIX >40: +15% (20% total)

**Opportunity Reserve:**
The system maintains 25% of cash for unexpected opportunities:
- Automatically replenished from premium income weekly
- Deployed strategically during market corrections
- Target deployment within 48 hours of significant drops

**Cash Deployment Schedule:**
- Monday: Analysis only, no new deployments
- Tuesday-Thursday: Systematic deployment of planned trades
- Friday: Accumulate cash for next week's opportunities

**Best Practices:**
1. Never deploy all available cash at once
2. Follow the VIX-based reserve guidelines strictly
3. Use the opportunity reserve only for high-conviction setups
4. Maintain proper cash buffers for each account tier

### Gap Risk Management

The system includes protocols for managing overnight price gaps, which can significantly impact option positions.

**Pre-Market Assessment (8:30 AM ET):**
Each morning, the system scans for potential gaps in your positions:
- Ranks positions by gap magnitude
- Prepares contingency orders for large gaps
- Adjusts morning routine timing if needed

**Gap Response Thresholds:**

| Gap Size | CSP Action | CC Action | Timing |
|----------|------------|-----------|--------|
| 2-3% | Monitor | Monitor | Normal |
| 3-5% | Evaluate roll | Evaluate close | First hour |
| >5% | Defensive roll | Close position | Market open |

**Gap Pattern Recognition:**
The system categorizes gaps to determine appropriate responses:
- Earnings-related: Usually permanent, act immediately
- Market-wide: Evaluate breadth recovery likelihood
- Technical: Often revert, consider waiting for reversion

**Best Practices:**
1. Have contingency plans ready before market open
2. Don't rush to act on gap opens without analysis
3. Consider the gap context before taking action
4. For large gaps, prioritize capital preservation

### Position Repair Toolkit

When standard rolling techniques aren't sufficient, the system offers advanced repair strategies for underwater positions.

**Deep ITM Put Recovery:**
When a put is deeply underwater (>15% ITM):
1. Evaluate ratio roll (1 → 1.5 or 2 contracts at lower strikes)
2. Consider roll to further expiration (60-90 DTE) for more premium
3. Analyze assignment + CC vs continued rolling

**Strike Adjustment Guidelines:**
- Roll down no more than 2% per week of time extension
- Accept assignment if roll credit < 0.5% of strike value
- Split large positions into multiple strikes during repair

**Repair Evaluation Framework:**
For each repair approach, the system calculates:
- Time to breakeven
- Capital efficiency
- Opportunity cost vs. closing for loss
- Probability of eventual profit

**Best Practices:**
1. Begin repair process early - don't wait until expiration
2. Avoid doubling down on broken theses
3. Accept small losses to avoid larger ones
4. Document repair efficiency for future reference

### Execution Quality Analysis

The system continuously monitors trade execution quality to optimize order placement strategies.

**Execution Metrics Tracked:**
- Slippage from intended price
- Fill time (seconds from order submission to execution)
- Fill quality (better/worse than midpoint)
- Performance by time of day
- Performance by order type

**Daily Execution Report:**
The system generates a daily report showing:
- Average slippage across all trades
- Percentage of orders filled better than midpoint
- Best/worst performing order types
- Optimal time of day for executions

**Order Type Optimization:**
Based on historical data, the system recommends:
- Best order type for each market condition
- Optimal limit price placement
- When to use midpoint vs. limit orders
- When to accept market orders for priority execution

**Best Practices:**
1. Review execution quality reports weekly
2. Use recommended order types for each situation
3. Avoid trading during historically poor execution times
4. Monitor broker routing quality over time

### Sector Opportunity Screener

The Sector Opportunity Screener helps maintain optimal sector diversification while maximizing returns.

**Core Functionality:**
1. **Sector Gap Analysis**: Identifies sectors with the largest allocation gaps relative to targets
2. **Multi-Factor Scoring**: Ranks opportunities using a comprehensive scoring model
3. **Regime-Based Allocation**: Adjusts sector targets based on market conditions
4. **Sector Rotation Detection**: Identifies momentum shifts between sectors

**How to Use It:**
1. Access the Sector Opportunity Screener from the dashboard sidebar
2. Review the "Underweight Sectors" table showing sectors with largest gaps
3. Examine the top opportunity for each underweight sector
4. Consider sector rotation signals when planning entries/exits

**Scoring Model Factors:**
- **Premium yield** (30%): Annualized return on capital
- **IV Rank** (20%): Higher IV rank = better opportunity
- **Liquidity** (15%): Volume × OI / Spread metrics
- **Valuation** (15%): Sector-specific fundamental metrics
- **Momentum** (10%): Sector relative strength vs market
- **Allocation Gap** (10%): Difference from target allocation

**Market Regime Integration:**

The screener automatically adjusts sector targets based on market conditions:

**Bull Market:**
- Higher allocations to Technology, Consumer Discretionary, Financials
- Lower allocations to defensive sectors
- Higher delta targets across the board

**Bear Market:**
- Higher allocations to Utilities, Consumer Staples, Healthcare
- Lower allocations to cyclical sectors
- Conservative delta targets

**Neutral Market:**
- Balanced sector targets
- Standard delta settings

**Best Practices:**
1. Always check the Sector Opportunity Screener before entering new positions
2. Prioritize highest-scoring opportunities in the most underweight sectors
3. Pay attention to sector rotation signals for early warning of regime changes
4. Use sector positioning as a risk management tool in volatile markets

### Post-Earnings IV Crush Trading

The system identifies and helps execute post-earnings IV crush opportunities.

**How It Works:**
1. System scans for stocks 1-3 days after earnings
2. Identifies candidates with:
   - >30% IV drop post-earnings
   - Price stable within 5% of pre-earnings
   - No major guidance changes

**Implementation:**
1. Check "Post-Earnings" tab in Opportunity Scanner
2. Verify fundamental thesis still intact
3. Use 30-45 DTE puts at 25-30 delta
4. Size at 50% of normal (higher uncertainty)

**Best Candidates:**
- Large caps with predictable earnings
- Strong companies with temporary volatility
- Avoid biotech or highly speculative names

### Pair Trading Within Wheel

The system supports paired trades for enhanced returns with controlled risk.

**Implementation:**
- Long stronger stock, CSP on weaker (same sector)
- Maximum 2 pairs at once
- Combined exposure counts as 2 positions

**Best Pairs:**
- JPM/BAC (banking)
- GOOGL/GOOG (tech)
- TGT/WMT (retail)
- XOM/CVX (energy)

**Rules:**
1. Only pair companies in same sector
2. Verify correlation >0.80 between pair
3. Use standard position sizing on EACH side
4. Count as TWO positions against maximum

### Seasonal Pattern Adaptation

The system automatically adjusts for known seasonal patterns.

**January Effect:**
- Weeks 2-4: More aggressive strikes on small caps
- Higher expected volatility in Week 1

**Earnings Seasons (Jan/Apr/Jul/Oct):**
- Week before: Reduce new positions 50%
- During: Focus on post-earnings trades
- Week after: Resume normal operations

**Summer Doldrums (Jul-Aug):**
- Extend DTE to 45-60 days
- Focus on dividend aristocrats
- Reduce position count 20%

**September Volatility:**
- Reduce position sizes 25%
- Lower delta targets
- Increase cash buffer

### Tax Optimization

For taxable accounts, the system helps manage tax implications.

**Year-Round Harvesting:**
- Monthly tax loss review (15th of month)
- Identify underwater positions >30 days old
- Calculate tax benefit vs recovery potential

**Strategic Year-End Moves:**
- October: Identify YTD gains
- November: Match potential losses
- December 1-15: Execute final harvesting
- December 16-31: Avoid new wash sales

**IRA/Taxable Integration:**
- Hold highest premium positions in IRA
- Use taxable for potential long-term holds
- Coordinate assignments across accounts

---

## Glossary

**A/D Ratio**: Advance/Decline Ratio - Market breadth indicator showing the ratio of advancing stocks to declining stocks.

**Assignment**: When a put option is exercised, obligating you to purchase shares at the strike price.

**Black Swan Protocol**: Enhanced protection system activated during extreme market conditions.

**Cash-Secured Put (CSP)**: A put option sold with sufficient cash reserved to cover potential assignment.

**Circuit Breaker**: System protection that pauses new trade entry during drawdown periods.

**Correlation Crisis**: When market sectors become highly correlated, reducing diversification benefits.

**Covered Call (CC)**: A call option sold against owned shares of the underlying stock.

**Delta**: Option Greek measuring the expected change in option price for a $1 move in the underlying.

**DTE**: Days To Expiration - The number of days remaining until an option expires.

**IV Crush**: Rapid decline in implied volatility, typically after earnings or major events.

**IV Rank**: Implied Volatility Rank - Percentile of current IV compared to historical IV.

**Roll**: Closing an existing option position and simultaneously opening a new one with different strike and/or expiration.

**Sharpe Ratio**: Measure of risk-adjusted return, calculated as (Return - Risk Free Rate) / Standard Deviation.

**Stop Loss**: Predetermined exit point to limit losses on a position.

**The Wheel**: Strategy of selling CSPs, taking assignment when needed, then selling CCs, repeating the cycle.

**VIX**: CBOE Volatility Index - Measure of market's expectation of 30-day volatility.

**Win Rate**: Percentage of trades that result in a profit.

**Win Streak Management**: System to prevent overconfidence during consecutive winning trades.

---

## FAQ

### General Questions

**Q: How much time will I need to manage this system daily?**
A: Expect to spend 30-45 minutes daily, divided between morning (15 min), afternoon (15 min), and end of day (10 min) routines. Weekly review requires about 20 minutes.

**Q: What's the minimum capital required?**
A: Absolute minimum is $10,000, but $25,000+ is recommended for proper diversification and to avoid pattern day trader restrictions.

**Q: Can I run this on a paper trading account first?**
A: Yes, the system works identically with paper trading. Use port 7497 instead of 7496 in the configuration.

**Q: Is this fully automated or does it require my input?**
A: The system automates monitoring and alerting but requires your final decision on all trades. It's semi-automated by design to maintain human oversight.

### Strategy Questions

**Q: Why only CSPs and CCs? Why not spreads or other strategies?**
A: Simplicity creates edge. Additional strategies add complexity and new ways to lose money. The wheel strategy is proven effective with lower risk when executed properly.

**Q: What's a realistic return expectation?**
A: In normal market conditions, 15-25% annualized is a reasonable target. Bear markets will likely see lower returns, while strong bull markets may exceed this range.

**Q: How do I handle a market crash?**
A: The system includes the Black Swan Protocol specifically for crash scenarios. It will automatically detect severe conditions and guide you through protective measures.

**Q: When should I take assignment vs. rolling puts?**
A: Take assignment when:
- You still want the stock at the strike price
- Rolling would require a significant drop in strike
- You can sell attractive covered calls immediately

Roll when:
- You can get a credit without dropping strike significantly
- Stock thesis has weakened but not broken
- Assignment would create overexposure to a sector

### Technical Questions

**Q: Can I run this on a cloud server instead of my computer?**
A: Yes, the system can run on any cloud server with Python support. You'll need to ensure TWS or Gateway is also accessible.

**Q: What happens if my internet connection drops?**
A: The system includes reconnection logic. When connection is restored, it will perform a position reconciliation to ensure everything is current.

**Q: Can I customize the alerts?**
A: Yes, alert thresholds and delivery methods are fully customizable in the configuration file.

**Q: Does this work with brokers other than Interactive Brokers?**
A: The current implementation uses IBKR's API. Adapters for other brokers (TDA, ETrade) are planned for future releases.

### Troubleshooting Questions

**Q: What should I do if I get a "Market data subscription" error?**
A: This usually means you need to subscribe to specific market data in IBKR. Log into Account Management and review your market data subscriptions.

**Q: The dashboard shows different values than my broker. Why?**
A: This is typically due to data timing differences. The system updates on a set schedule, while your broker may update in real-time. The "Refresh" button will force a data update.

**Q: What if the system recommends more than 3 trades in a day?**
A: Prioritize by criticality: defensive rolls first, profit-taking second, new entries last. Defer lower priority actions to the next day if needed.

**Q: My broker rejected an order. What should I do?**
A: Check the rejection reason in the logs. Common issues include insufficient funds, position limits, or invalid contract specifications. Fix the underlying issue and try again.

---

© 2025 Wheel Strategy System | Version 2.0