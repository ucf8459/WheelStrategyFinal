# Wheel Strategy Dashboard Training Guide
## Complete User Manual for Dashboard Navigation & Usage

## Table of Contents
1. [Dashboard Overview](#dashboard-overview)
2. [Header Section](#header-section)
3. [Portfolio Overview](#portfolio-overview)
4. [Active Positions](#active-positions)
5. [Decision Support](#decision-support)
6. [Market Conditions](#market-conditions)
7. [Win Streak Management](#win-streak-management)
8. [Opportunity Scanner](#opportunity-scanner)
9. [System Status](#system-status)
10. [Income Tracking](#income-tracking)
11. [Color Coding & Visual Indicators](#color-coding--visual-indicators)
12. [Daily Dashboard Workflow](#daily-dashboard-workflow)
13. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## Dashboard Overview

The Wheel Strategy Dashboard is your central command center for monitoring and managing your options trading positions. It provides real-time data, actionable insights, and automated alerts to help you execute the wheel strategy effectively while maintaining strict risk controls.

### Key Design Principles
- **Information Hierarchy**: Most critical information appears at the top and left
- **Color-Coded Alerts**: Visual indicators for quick decision-making
- **3-Decision Limit**: Built-in safeguards to prevent overtrading
- **Mobile Responsive**: Works on desktop, tablet, and mobile devices

### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│                    HEADER (System Status)                    │
├────────────────────────────────────┬────────────────────────┤
│                                    │                        │
│         MAIN CONTENT               │      SIDEBAR           │
│                                    │                        │
│  • Portfolio Overview              │  • Market Conditions   │
│  • Active Positions                │  • Win Streak Mgmt     │
│  • Decision Support                │  • Opportunity Scanner │
│                                    │  • System Status       │
│                                    │  • Income Tracking     │
└────────────────────────────────────┴────────────────────────┘
```

---

## Header Section

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│  Wheel Strategy Dashboard          [●] System Active         │
└─────────────────────────────────────────────────────────────┘
```

### Components

**1. Logo/Title**
- Displays "Wheel Strategy Dashboard"
- Clicking returns you to the main dashboard view

**2. System Status Indicator**
- **Green dot [●] + "System Active"**: All systems functioning normally
- **Yellow dot [●] + "System Warning"**: Minor issues detected
- **Red dot [●] + "System Error"**: Critical issues requiring attention

### Usage
- Check system status first thing each morning
- If yellow/red status appears, check System Status card for details
- Status updates every 30 seconds automatically

---

## Portfolio Overview

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Portfolio Overview                    BULL | Updated: 14:35  │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│ │Account Value│ │Cash Available│ │Realized P&L │            │
│ │  $246,890   │ │   $72,350    │ │   +$2,184   │            │
│ │  +3.2% Today│ │29.3% of Port │ │ MTD: +$7,450│            │
│ └─────────────┘ └─────────────┘ └─────────────┘            │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│ │Premium Coll.│ │  Win Rate    │ │Active Pos.  │            │
│ │   $1,876    │ │     87%      │ │    8/10     │            │
│ │ MTD: $5,230 │ │ Last 30 Days │ │Utiliz: 71%  │            │
│ └─────────────┘ └─────────────┘ └─────────────┘            │
│                                                              │
│ [====== Portfolio Performance Chart Area ======]             │
└─────────────────────────────────────────────────────────────┘
```

### Key Metrics Explained

**1. Account Value**
- **Definition**: Total value of all positions + cash
- **Usage**: Monitor daily changes and compare to peak value
- **Alert Triggers**: 
  - Yellow if down >5% from yesterday
  - Red if down >10% from peak (approaching circuit breaker)

**2. Cash Available**
- **Definition**: Unallocated cash ready for new positions
- **Usage**: Ensure proper cash management per VIX levels
- **Target Ranges**:
  - VIX <20: 5% minimum
  - VIX 20-30: 10% minimum
  - VIX >30: 15% minimum

**3. Realized P&L**
- **Definition**: Actual profits/losses from closed positions
- **Display**: Today's P&L and Month-to-Date (MTD)
- **Usage**: Track actual performance vs paper gains

**4. Premium Collected**
- **Definition**: Option premium income received
- **Display**: Today's premium and MTD total
- **Usage**: Compare against monthly income targets

**5. Win Rate**
- **Definition**: Percentage of profitable trades (last 30 days)
- **Target**: >75%
- **Alert**: Yellow if <70%, Red if <65%

**6. Active Positions**
- **Definition**: Current positions vs maximum allowed
- **Display**: "8/10" means 8 active out of 10 maximum
- **Utilization**: Percentage of capital deployed

### Performance Chart
- Shows 30-day portfolio value trend
- Green line = portfolio value
- Gray line = SPY benchmark
- Shaded area = drawdown periods

### How to Use This Section
1. **Morning Review**: Check account value change and cash levels
2. **Position Planning**: Verify you have room for new positions
3. **Performance Check**: Compare win rate to target
4. **Risk Assessment**: Monitor drawdown from peak

---

## Active Positions

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Active Positions                              [Refresh]      │
├─────────────────────────────────────────────────────────────┤
│ Symbol │Type│Strike │Expiry    │DTE│Premium│P&L % │Delta│Action    │
├────────┼────┼───────┼──────────┼───┼───────┼──────┼─────┼──────────┤
│ AAPL   │CSP │$175.00│Jul 25, 25│22 │ $3.45 │[+42%]│0.32 │[Roll][Close] │
│ MSFT   │CSP │$310.00│Jul 18, 25│15 │ $4.20 │[+65%]│0.28 │[Roll][Close] │
│ NVDA   │CSP │$420.00│Jul 11, 25│8  │ $5.65 │[-12%]│0.48 │[Roll Def.]  │
│ GOOGL  │CC  │$165.00│Jul 25, 25│22 │ $2.85 │[+38%]│0.35 │[Close]      │
└─────────────────────────────────────────────────────────────┘
```

### Column Definitions

**Symbol**
- The underlying stock ticker
- Click to view detailed stock information

**Type**
- **CSP**: Cash-Secured Put (selling puts)
- **CC**: Covered Call (selling calls on owned shares)
- **Shares**: Stock positions without options

**Strike**
- Option strike price
- For shares, displays "-"

**Expiry**
- Option expiration date
- Format: Month Day, Year

**DTE (Days to Expiration)**
- Days remaining until option expires
- Color coding:
  - Red: <7 days (immediate attention)
  - Yellow: 7-14 days (plan action)
  - White: >14 days (monitor)

**Premium**
- Credit received per contract
- Displayed in dollars per share

**P&L %**
- Current profit/loss percentage
- Color-coded badges:
  - Green [+X%]: Profitable
  - Yellow [-X%]: Small loss (<20%)
  - Red [-X%]: Significant loss (>20%)

**Delta**
- Option's delta (rate of price change)
- Key thresholds:
  - >0.50: High risk of assignment
  - 0.30-0.50: Monitor closely
  - <0.30: Relatively safe

**Action Buttons**
- **[Roll]**: Move position to later date/different strike
- **[Close]**: Exit the position
- **[Monitor]**: No immediate action needed
- **[Roll Def.]**: Urgent defensive roll needed

### Position Management Rules

**When to Roll**
1. Delta exceeds 0.50 (defensive roll)
2. At 21 DTE (time-based roll)
3. At 80%+ profit with >7 DTE (efficiency roll)

**When to Close**
1. Covered calls at 50% profit
2. Any position at 90%+ profit
3. When original thesis no longer valid

**Color Priority System**
- Red buttons: Handle first
- Yellow buttons: Handle second
- Blue buttons: Optional actions
- Gray buttons: Information only

### How to Use This Section
1. **Sort by DTE**: Focus on positions expiring soon
2. **Check Deltas**: Identify defensive roll candidates
3. **Review P&L**: Take profits on winners
4. **Plan Actions**: Never exceed 3 trades per day

---

## Decision Support

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Decision Support              Max 3 decisions today | Used: 1│
├─────────────────────────────────────────────────────────────┤
│ Today's Priorities:                                          │
│                                                              │
│ ┌─[CRITICAL]─────────────────────────────────[Take Action]─┐│
│ │ Roll NVDA $420 put (delta > 0.45) - Defensive required   ││
│ └────────────────────────────────────────────────────────────┘│
│                                                              │
│ ┌─[IMPORTANT]────────────────────────────────[Take Action]─┐│
│ │ Close MSFT $310 put (65% profit) - Early profit taking   ││
│ └────────────────────────────────────────────────────────────┘│
│                                                              │
│ ┌─[INFO]─────────────────────────────────────[View Details]┐│
│ │ Consider selling XOM put after earnings stabilization     ││
│ └────────────────────────────────────────────────────────────┘│
│                                                              │
│ Upcoming Expirations (7 days):                              │
│ Symbol│Expiry    │Strike │Current│Status  │Recommendation  │
│ NVDA  │Jul 11, 25│$420.00│$417.35│At Risk │Roll Aug 8 @$400│
│ UNH   │Jul 11, 25│$550.00│$570.20│Safe OTM│Let expire      │
└─────────────────────────────────────────────────────────────┘
```

### Priority Levels

**CRITICAL (Red Alert)**
- Immediate defensive action required
- Examples:
  - Delta >0.50 on short puts
  - Positions down >20%
  - Expiring positions needing rolls
- Action: Address these first

**IMPORTANT (Yellow Alert)**
- Time-sensitive but not urgent
- Examples:
  - Profit targets hit (50-80%)
  - Positions at 21 DTE
  - Sector concentration warnings
- Action: Handle after critical items

**INFO (Blue Alert)**
- Opportunities and suggestions
- Examples:
  - New trade setups
  - Post-earnings opportunities
  - Market observations
- Action: Consider if decision count allows

### Decision Counter
- Shows "Max 3 decisions today | Used: X"
- Resets at midnight ET
- Prevents overtrading and emotional decisions

### Upcoming Expirations Table

**Purpose**: Preview positions expiring within 7 days

**Columns**:
- **Symbol**: Underlying ticker
- **Expiry**: Exact expiration date
- **Strike**: Option strike price
- **Current Price**: Live stock price
- **Status**: 
  - "Safe OTM": Out of money, likely to expire
  - "At Risk": Close to strike, monitor
  - "ITM": In the money, action needed
- **Recommendation**: System-generated action suggestion

### How to Use This Section

**Daily Workflow**:
1. **Morning (9:00 AM)**: Review all alerts, plan 1-3 actions
2. **Afternoon (2:30 PM)**: Execute planned actions
3. **Never exceed 3 decisions**: Quality over quantity

**Decision Priority Matrix**:
```
If CRITICAL alerts exist → Handle these first
Else if IMPORTANT alerts exist → Handle these
Else if INFO opportunities exist AND decisions < 3 → Consider new trades
Else → No action needed
```

**Best Practices**:
- Write down your 3 planned actions in the morning
- Don't deviate unless new CRITICAL alerts appear
- If you need >3 decisions, your position sizing is wrong

---

## Market Conditions

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Market Conditions                                            │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│ │   VIX    │ │  Regime  │ │Correlation│ │A/D Ratio │       │
│ │  18.75   │ │   BULL   │ │   0.65    │ │   1.8    │       │
│ │30th %ile │ │Strong    │ │ Moderate  │ │ Healthy  │       │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│ Sector Exposure (Top 3):                                     │
│ Technology    [████████████░░░░░] 40%                       │
│ Financials    [██████░░░░░░░░░░] 20%                       │
│ Consumer      [████░░░░░░░░░░░░] 15%                       │
│                                                              │
│ Seasonal Pattern:                                            │
│ Earnings Season: July                                        │
│ Focus on post-earnings IV crush opportunities                │
└─────────────────────────────────────────────────────────────┘
```

### VIX (Volatility Index)

**Display Format**: Current value + percentile ranking

**Interpretation**:
- **<15**: Low volatility (reduce position sizes)
- **15-20**: Normal volatility (standard sizing)
- **20-30**: Elevated volatility (opportunity zone)
- **>30**: High volatility (reduce risk)

**Percentile Context**:
- "30th percentile" = VIX is lower than 70% of the past year
- Higher percentile = more fear in market

### Market Regime

**Three Regimes**:

**BULL**
- SPY > 50-day MA > 200-day MA
- VIX <20
- Strategy: Higher deltas (30-40), growth stocks

**BEAR**
- SPY < 50-day MA < 200-day MA
- VIX >25
- Strategy: Lower deltas (15-25), defensive stocks

**NEUTRAL**
- Mixed signals
- Strategy: Balanced approach (25-30 delta)

### Correlation

**Definition**: Average correlation between major sectors

**Risk Levels**:
- **<0.60**: Normal (good diversification)
- **0.60-0.80**: Moderate (monitor closely)
- **>0.80**: High (reduce positions)
- **>0.90**: Extreme (activate crisis protocols)

### A/D Ratio (Advance/Decline)

**Definition**: Ratio of advancing stocks to declining stocks

**Interpretation**:
- **>1.5**: Healthy market breadth
- **1.0-1.5**: Neutral breadth
- **<1.0**: Weak breadth (be cautious)
- **<0.5**: Very weak (consider reducing exposure)

### Sector Exposure

**Visual Progress Bars**: Show allocation by sector

**Color Coding**:
- Green bar: Within target range
- Yellow bar: Approaching limit
- Red bar: Over limit

**Usage**:
- Avoid new positions in red sectors
- Prioritize opportunities in underweight sectors
- Rebalance if any sector >25%

### Seasonal Pattern

**Displays**: Current market seasonal tendency

**Examples**:
- "January Effect": Small-cap outperformance
- "Earnings Season": Higher volatility
- "Summer Doldrums": Lower volatility
- "September Volatility": Historically weak

**Usage**: Adjust strategy based on seasonal patterns

### How to Use This Section
1. **Check VIX first**: Determines position sizing
2. **Confirm regime**: Guides strike selection
3. **Monitor correlation**: Watch for crisis conditions
4. **Review sectors**: Ensure proper diversification
5. **Note seasonality**: Prepare for typical patterns

---

## Win Streak Management

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Win Streak Management                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│     [7]     Consecutive Wins                                 │
│             No size adjustment needed yet                    │
│                                                              │
│ Risk Check:                                                  │
│ ┌─[INFO]────────────────────────────────────────────────┐  │
│ │ No risk creep detected - All positions within limits   │  │
│ └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Consecutive Wins Display

**Large Number**: Current consecutive winning trades

**Thresholds & Actions**:
- **0-4 wins**: Normal trading
- **5-7 wins**: Caution zone (monitor for risk creep)
- **8-9 wins**: Reduce position sizes by 25%
- **10+ wins**: Reduce position sizes by 50%

### Risk Creep Indicators

**System Monitors For**:
1. **DTE Creep**: Entering shorter expirations
2. **Delta Creep**: Taking higher-risk strikes
3. **Size Creep**: Increasing position sizes
4. **Liquidity Creep**: Trading less liquid names

**Alert Types**:
- "No risk creep detected" (Green): Continue normal trading
- "Warning signs detected" (Yellow): Review recent trades
- "Risk creep confirmed" (Red): Mandatory size reduction

### Psychology Behind the Feature

**Why It Matters**:
- Winning streaks create overconfidence
- Overconfidence leads to larger losses
- Small position sizes protect during inevitable drawdowns

**The Math**:
- 10 wins at 2% = +20%
- 1 loss at 10% = -10%
- Net = +10% (vs +18% without the big loss)

### How to Use This Section
1. **Celebrate milestones**: 5, 10, 15 consecutive wins
2. **Accept size reductions**: They protect your capital
3. **Review trades**: Look for subtle risk increases
4. **Reset mindset**: Each trade is independent

---

## Opportunity Scanner

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Opportunity Scanner                                          │
├─────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────────[Trade]────┐    │
│ │ AMD $180 Put               27.5% Annualized          │    │
│ │ 30 DTE | IV Rank: 72%                                │    │
│ └───────────────────────────────────────────────────────┘    │
│                                                              │
│ ┌───────────────────────────────────────────[Trade]────┐    │
│ │ XOM $115 Put               22.8% Annualized          │    │
│ │ 45 DTE | Post-Earnings                               │    │
│ └───────────────────────────────────────────────────────┘    │
│                                                              │
│ ┌───────────────────────────────────────────[Trade]────┐    │
│ │ WMT $65 Put                19.2% Annualized          │    │
│ │ 30 DTE | IV Rank: 65%                                │    │
│ └───────────────────────────────────────────────────────┘    │
│                                                              │
│                    [View All Opportunities]                  │
└─────────────────────────────────────────────────────────────┘
```

### Opportunity Card Components

**Symbol & Strike**
- Example: "AMD $180 Put"
- Only shows liquid, wheelable stocks

**Opportunity Details**
- **DTE**: Days to expiration (typically 30-45)
- **IV Rank**: Implied volatility ranking (must be >50%)
- **Post-Earnings**: Indicates IV crush opportunity

**Expected Return**
- Annualized return percentage
- Calculated as: (Premium/Strike) × (365/DTE)
- Only shows opportunities >20% annualized

**Trade Button**
- Blue button: Opens order entry screen
- Pre-fills recommended parameters

### Screening Criteria

All opportunities must pass:
1. **IV Rank >50%**: High relative volatility
2. **IV >20%**: Sufficient absolute volatility
3. **Liquidity score >1000**: Tight spreads, good volume
4. **7+ days from earnings**: No earnings risk
5. **Sector limits OK**: Won't exceed concentration
6. **Valuation reasonable**: Strike represents fair value

### Special Opportunity Types

**Post-Earnings IV Crush**
- Appears 1-3 days after earnings
- Requires >30% IV drop
- Stock price stable (±5%)
- Size at 50% normal

**Sector Rotation**
- Identifies sector momentum shifts
- Prioritizes lagging sectors
- Helps maintain balance

### How to Use This Section
1. **Review all opportunities**: Even if not trading today
2. **Compare returns**: Higher isn't always better
3. **Check sector balance**: Prioritize underweight sectors
4. **Plan ahead**: Note opportunities for tomorrow
5. **Click "View All"**: See complete opportunity list

---

## System Status

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ System Status                                                │
├─────────────────────────────────────────────────────────────┤
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐│
│ │Circuit     │ │Black Swan  │ │API Connect.│ │Last Update││
│ │Breaker     │ │Protocol    │ │            │ │           ││
│ │[Inactive]  │ │[Inactive]  │ │[Connected] │ │14:35 ET   ││
│ └────────────┘ └────────────┘ └────────────┘ └───────────┘│
│                                                              │
│ Daily Workflow:                                              │
│ Morning Routine     [Completed] 09:05 ET                     │
│ Afternoon Check-in  [Completed] 14:32 ET                     │
│ EOD Routine         [Pending]   16:15 ET                     │
└─────────────────────────────────────────────────────────────┘
```

### Status Indicators

**Circuit Breaker**
- **Inactive (Green)**: Normal trading allowed
- **Active (Red)**: New trades blocked due to:
  - 20% drawdown from peak
  - 10% weekly loss
  - 3 consecutive losing days
- **Recovery**: Shows days until restriction lifts

**Black Swan Protocol**
- **Inactive (Green)**: Normal market conditions
- **Stage 1-4 (Yellow)**: Recovery in progress
- **Active (Red)**: Extreme conditions, enhanced protection

**API Connection**
- **Connected (Green)**: Live data flowing
- **Reconnecting (Yellow)**: Temporary disruption
- **Disconnected (Red)**: Manual trading mode

**Last Update**
- Shows timestamp of last data refresh
- Should update every 30 seconds
- If stale >5 minutes, check connection

### Daily Workflow Status

**Three Checkpoints**:

1. **Morning Routine (9:00 AM ET)**
   - Status: Completed/Pending
   - Reviews overnight changes
   - Plans day's actions

2. **Afternoon Check-in (2:30 PM ET)**
   - Status: Completed/Pending
   - Executes planned trades
   - Adjusts for market changes

3. **EOD Routine (4:15 PM ET)**
   - Status: Completed/Pending
   - Logs results
   - Prepares next day

### How to Use This Section
1. **First check each morning**: Ensure all systems green
2. **Monitor throughout day**: Watch for status changes
3. **Follow workflow**: Complete each routine on schedule
4. **Document issues**: Note any system problems

---

## Income Tracking

### Visual Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Income Tracking                                              │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌──────────────┐                          │
│ │Monthly Target│ │  Collected   │                          │
│ │   $3,750     │ │   $2,450     │                          │
│ │1.5% of capital│ │65% of target │                          │
│ └──────────────┘ └──────────────┘                          │
│                                                              │
│ Progress to Goal:                                            │
│ [█████████████░░░░░░░░░░░] 65%                             │
│                                     13 days remaining        │
└─────────────────────────────────────────────────────────────┘
```

### Monthly Target

**Calculation**: Based on market regime
- Bull market: 1.5-2.0% of capital
- Neutral: 1.0-1.5% of capital  
- Bear market: 0.7-1.0% of capital

**Example**: $250k account in bull market
- Target: $3,750 (1.5%)
- Stretch goal: $5,000 (2.0%)

### Progress Tracking

**Collected Amount**
- Premium received month-to-date
- Includes all closed and open positions
- Updates real-time

**Progress Bar**
- Visual representation of goal completion
- Green: On track (pro-rated for day of month)
- Yellow: Slightly behind
- Red: Significantly behind

**Days Remaining**
- Calendar days left in month
- Helps pace your trading

### Income Management

**If Ahead of Target**:
1. Consider banking profits
2. Reduce position deltas
3. Extend DTEs
4. Build cash reserves

**If Behind Target**:
1. Don't chase yield
2. Maintain discipline
3. Review missed opportunities
4. Accept lower months

### How to Use This Section
1. **Weekly check**: Assess progress each Friday
2. **Mid-month review**: Adjust strategy if needed
3. **Never compromise rules**: to hit targets
4. **Plan next month**: Based on market conditions

---

## Color Coding & Visual Indicators

### Status Color Legend
```
[●] Green  = Positive/Safe/Good
[●] Yellow = Caution/Monitor/Warning  
[●] Red    = Danger/Action Required
[●] Blue   = Information/Neutral
```

### Badge Examples
```
[+42%] = Green profit badge
[-12%] = Yellow/Red loss badge
[CRITICAL] = Red priority alert
[INFO] = Blue information alert
```

### Visual Hierarchy

1. **Red items**: Handle first
2. **Yellow items**: Handle second
3. **Green items**: Good news, no action
4. **Blue items**: Review when time permits

---

## Daily Dashboard Workflow

### Morning Routine Timeline (9:00 AM ET)
```
┌─────────────────────────────────────────────────────────────┐
│ 9:00 │ System Check      │ Verify all green status (1 min) │
│ 9:01 │ Portfolio Review  │ Check value & cash (2 min)      │
│ 9:03 │ Position Scan     │ Review DTE & deltas (3 min)     │
│ 9:06 │ Decision Planning │ Select 1-3 actions (3 min)      │
│ 9:09 │ Market Check      │ VIX, regime, sectors (1 min)    │
│ 9:10 │ Complete          │ Total: 10 minutes               │
└─────────────────────────────────────────────────────────────┘
```

### Afternoon Check-in (2:30 PM ET)
```
┌─────────────────────────────────────────────────────────────┐
│ 2:30 │ Execute Trades    │ Implement plan (5 min)          │
│ 2:35 │ Opportunity Review│ Scan new setups (2 min)         │
│ 2:37 │ Adjustment Check  │ 80% profits, rolls (3 min)      │
│ 2:40 │ Complete          │ Total: 10 minutes               │
└─────────────────────────────────────────────────────────────┘
```

### End of Day (4:15 PM ET)
```
┌─────────────────────────────────────────────────────────────┐
│ 4:15 │ Results Log       │ Record trades & P&L (3 min)     │
│ 4:18 │ Tomorrow Prep     │ Check earnings/expiry (3 min)   │
│ 4:21 │ Weekly Prep       │ Fridays only (2 min)            │
│ 4:23 │ Complete          │ Total: 6-8 minutes              │
└─────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting Common Issues

### Quick Reference Table
```
┌─────────────────────────────────────────────────────────────┐
│ Issue              │ Symptom           │ First Action       │
├────────────────────┼───────────────────┼────────────────────┤
│ Not Updating       │ Stale prices      │ Check connection   │
│ Wrong Data         │ P&L incorrect     │ Hit Refresh button │
│ Too Many Alerts    │ Alert fatigue     │ Adjust thresholds  │
│ Slow Performance   │ Delayed loading   │ Clear browser cache│
│ Mobile Issues      │ Cut-off display   │ Use landscape mode │
└─────────────────────────────────────────────────────────────┘
```

### Dashboard Not Updating

**Symptoms**: 
- Last update >5 minutes old
- Prices appear stale
- Positions not changing

**Solutions**:
1. Check internet connection
2. Verify API connection status
3. Refresh browser (Ctrl+F5)
4. Check if market is open
5. Restart system if needed

### Incorrect Position Data

**Symptoms**:
- P&L seems wrong
- Positions missing
- Wrong quantities shown

**Solutions**:
1. Click "Refresh" button
2. Compare with broker platform
3. Check for corporate actions
4. Run position reconciliation
5. Contact support if persists

### Alert Overload

**Symptoms**:
- Too many alerts
- Repeated notifications
- Alert fatigue

**Solutions**:
1. Adjust alert thresholds
2. Set quiet hours
3. Prioritize critical only
4. Review alert settings
5. Clear old alerts daily

### Performance Issues

**Symptoms**:
- Slow loading
- Delayed updates
- Browser freezing

**Solutions**:
1. Close other browser tabs
2. Clear browser cache
3. Use Chrome/Firefox (recommended)
4. Check computer resources
5. Reduce position count if >20

### Mobile Display Issues

**Symptoms**:
- Tables cut off
- Buttons too small
- Charts not visible

**Solutions**:
1. Use landscape mode
2. Pinch to zoom key sections
3. Use mobile-optimized view
4. Access from tablet for best experience
5. Use desktop for complex operations

---

## Best Practices Summary

### The Golden Rules
1. **Check system status first every day**
2. **Never exceed 3 decisions per day**
3. **Red → Yellow → Blue priority always**
4. **Complete all daily routines on schedule**
5. **Trust the system's safeguards**

### Dashboard Navigation Tips
- Use keyboard shortcuts (if available)
- Bookmark frequently used sections
- Set up multiple monitors if possible
- Take screenshots of unusual events
- Export data weekly for backup

### Daily Discipline
1. **Always check system status first**
2. **Never exceed 3 decisions per day**
3. **Follow the priority system (Red → Yellow → Blue)**
4. **Document unusual events**
5. **Complete all scheduled routines**

### Risk Management
1. **Monitor win streaks carefully**
2. **Respect circuit breaker activations**
3. **Maintain sector balance**
4. **Keep adequate cash reserves**
5. **Size down in high correlation markets**

### Performance Optimization
1. **Take profits at target levels**
2. **Roll positions proactively**
3. **Focus on high-probability setups**
4. **Avoid chasing income targets**
5. **Review and adapt weekly**

### System Maintenance
1. **Clear alerts daily**
2. **Verify data accuracy weekly**
3. **Back up settings monthly**
4. **Update watchlists quarterly**
5. **Review performance annually**

---

## Conclusion

The Wheel Strategy Dashboard is a powerful tool that enforces discipline while providing flexibility. By following this guide and maintaining consistent daily routines, you'll maximize the strategy's effectiveness while minimizing risks.

Remember: The dashboard is your co-pilot, not your pilot. Always verify critical decisions and maintain oversight of your trading system.

**Key Takeaway**: Use every section of the dashboard daily, follow the workflows religiously, and let the system's built-in safeguards protect you from common trading mistakes.

**Final Tip**: Print this guide or keep it open in a separate window during your first week using the dashboard. Refer to it whenever you're unsure about any feature or indicator.