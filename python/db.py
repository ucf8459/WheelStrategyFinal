"""
Wheel Strategy Database Module
PostgreSQL persistence for trades, positions, and performance tracking
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'wheel_strategy'),
    'user': os.getenv('DB_USER', os.getenv('USER', 'postgres')),
    'password': os.getenv('DB_PASSWORD', ''),
}


def get_connection():
    """Get a database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


def execute_query(query: str, params: tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
    """Execute a query and optionally fetch results"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                result = [dict(row) for row in cur.fetchall()]
            else:
                result = None
            conn.commit()
            return result
    except Exception as e:
        logger.error(f"Query failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# =============================================================================
# TRADE FUNCTIONS
# =============================================================================

def record_trade(
    symbol: str,
    trade_type: str,
    quantity: int,
    strike: float = None,
    expiry: date = None,
    premium: float = None,
    fill_price: float = None,
    commission: float = 0,
    notes: str = None,
    opening_trade_id: int = None
) -> int:
    """Record a new trade and return its ID"""
    query = """
        INSERT INTO trades (symbol, trade_type, strike, expiry, quantity, premium, 
                           fill_price, commission, notes, opening_trade_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    params = (symbol, trade_type, strike, expiry, quantity, premium, 
              fill_price, commission, notes, opening_trade_id)
    
    result = execute_query(query, params)
    trade_id = result[0]['id'] if result else None
    logger.info(f"📝 Recorded trade: {trade_type} {quantity} {symbol} @ ${strike} (ID: {trade_id})")
    return trade_id


def close_trade(
    opening_trade_id: int,
    close_price: float,
    commission: float = 0,
    notes: str = None
) -> Dict:
    """Close an existing trade and calculate P&L"""
    # Get the opening trade
    opening = get_trade(opening_trade_id)
    if not opening:
        raise ValueError(f"Opening trade {opening_trade_id} not found")
    
    # Calculate P&L
    if 'OPEN' in opening['trade_type']:
        # For short options: profit = premium received - close price
        pnl = (opening['premium'] - close_price) * abs(opening['quantity']) * 100
        pnl -= opening['commission'] + commission
    else:
        pnl = (close_price - opening['fill_price']) * abs(opening['quantity']) * 100
        pnl -= opening['commission'] + commission
    
    pnl_percent = (pnl / (opening['strike'] * 100 * abs(opening['quantity']))) * 100 if opening['strike'] else 0
    hold_days = (datetime.now().date() - opening['trade_date'].date()).days
    
    # Record the closing trade
    close_type = opening['trade_type'].replace('_OPEN', '_CLOSE')
    close_id = record_trade(
        symbol=opening['symbol'],
        trade_type=close_type,
        quantity=-opening['quantity'],
        strike=opening['strike'],
        expiry=opening['expiry'],
        premium=close_price,
        fill_price=close_price,
        commission=commission,
        notes=notes,
        opening_trade_id=opening_trade_id
    )
    
    # Update the closing trade with P&L
    execute_query(
        "UPDATE trades SET pnl = %s, pnl_percent = %s, hold_days = %s WHERE id = %s",
        (pnl, pnl_percent, hold_days, close_id),
        fetch=False
    )
    
    logger.info(f"💰 Closed trade: {opening['symbol']} P&L: ${pnl:.2f} ({pnl_percent:.1f}%) after {hold_days} days")
    
    return {
        'close_id': close_id,
        'pnl': pnl,
        'pnl_percent': pnl_percent,
        'hold_days': hold_days
    }


def get_trade(trade_id: int) -> Optional[Dict]:
    """Get a single trade by ID"""
    result = execute_query("SELECT * FROM trades WHERE id = %s", (trade_id,))
    return result[0] if result else None


def get_recent_trades(limit: int = 20) -> List[Dict]:
    """Get recent trades"""
    return execute_query(
        "SELECT * FROM trades ORDER BY trade_date DESC LIMIT %s",
        (limit,)
    ) or []


def get_trades_by_symbol(symbol: str, limit: int = 50) -> List[Dict]:
    """Get trades for a specific symbol"""
    return execute_query(
        "SELECT * FROM trades WHERE symbol = %s ORDER BY trade_date DESC LIMIT %s",
        (symbol, limit)
    ) or []


def get_trades_summary(start_date: date = None, end_date: date = None) -> Dict:
    """Get trade statistics for a date range"""
    where_clause = "WHERE pnl IS NOT NULL"
    params = []
    
    if start_date:
        where_clause += " AND trade_date >= %s"
        params.append(start_date)
    if end_date:
        where_clause += " AND trade_date <= %s"
        params.append(end_date)
    
    query = f"""
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
            SUM(pnl) as total_pnl,
            AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
            AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
            AVG(hold_days) as avg_hold_days
        FROM trades
        {where_clause}
    """
    
    result = execute_query(query, tuple(params) if params else None)
    if result and result[0]:
        stats = result[0]
        total = stats['total_trades'] or 0
        wins = stats['wins'] or 0
        return {
            'total_trades': total,
            'wins': wins,
            'losses': stats['losses'] or 0,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'total_pnl': float(stats['total_pnl'] or 0),
            'avg_win': float(stats['avg_win'] or 0),
            'avg_loss': float(stats['avg_loss'] or 0),
            'avg_hold_days': float(stats['avg_hold_days'] or 0)
        }
    return {}


# =============================================================================
# POSITION FUNCTIONS
# =============================================================================

def add_position(
    symbol: str,
    position_type: str,
    quantity: int,
    strike: float = None,
    expiry: date = None,
    entry_premium: float = None,
    sector: str = None,
    opening_trade_id: int = None
) -> int:
    """Add a new position"""
    query = """
        INSERT INTO positions (symbol, position_type, strike, expiry, quantity, 
                              entry_premium, entry_date, sector, opening_trade_id)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, %s)
        RETURNING id
    """
    params = (symbol, position_type, strike, expiry, quantity, entry_premium, 
              sector, opening_trade_id)
    
    result = execute_query(query, params)
    position_id = result[0]['id'] if result else None
    logger.info(f"📊 Added position: {position_type} {symbol} @ ${strike} (ID: {position_id})")
    return position_id


def close_position(position_id: int, status: str = 'CLOSED') -> bool:
    """Close a position"""
    execute_query(
        "UPDATE positions SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (status, position_id),
        fetch=False
    )
    logger.info(f"📊 Closed position {position_id} with status: {status}")
    return True


def get_open_positions() -> List[Dict]:
    """Get all open positions"""
    return execute_query(
        "SELECT * FROM positions WHERE status = 'OPEN' ORDER BY entry_date"
    ) or []


def get_positions_by_symbol(symbol: str) -> List[Dict]:
    """Get positions for a specific symbol"""
    return execute_query(
        "SELECT * FROM positions WHERE symbol = %s ORDER BY entry_date DESC",
        (symbol,)
    ) or []


# =============================================================================
# DAILY SNAPSHOT FUNCTIONS
# =============================================================================

def record_daily_snapshot(
    account_value: float,
    buying_power: float = None,
    cash_balance: float = None,
    unrealized_pnl: float = None,
    realized_pnl_day: float = 0,
    position_count: int = 0,
    vix_level: float = None,
    market_regime: str = None
) -> bool:
    """Record a daily snapshot (upsert)"""
    query = """
        INSERT INTO daily_snapshots 
            (snapshot_date, account_value, buying_power, cash_balance, unrealized_pnl,
             realized_pnl_day, position_count, vix_level, market_regime)
        VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_date) 
        DO UPDATE SET 
            account_value = EXCLUDED.account_value,
            buying_power = EXCLUDED.buying_power,
            cash_balance = EXCLUDED.cash_balance,
            unrealized_pnl = EXCLUDED.unrealized_pnl,
            realized_pnl_day = EXCLUDED.realized_pnl_day,
            position_count = EXCLUDED.position_count,
            vix_level = EXCLUDED.vix_level,
            market_regime = EXCLUDED.market_regime
    """
    params = (account_value, buying_power, cash_balance, unrealized_pnl,
              realized_pnl_day, position_count, vix_level, market_regime)
    
    execute_query(query, params, fetch=False)
    logger.info(f"📸 Recorded daily snapshot: ${account_value:,.2f}")
    return True


def get_daily_snapshots(days: int = 30) -> List[Dict]:
    """Get recent daily snapshots"""
    return execute_query(
        """SELECT * FROM daily_snapshots 
           WHERE snapshot_date >= CURRENT_DATE - INTERVAL '%s days'
           ORDER BY snapshot_date""",
        (days,)
    ) or []


def get_performance_history(start_date: date = None) -> List[Dict]:
    """Get performance history with daily returns"""
    where = "WHERE snapshot_date >= %s" if start_date else ""
    params = (start_date,) if start_date else None
    
    query = f"""
        SELECT 
            snapshot_date,
            account_value,
            LAG(account_value) OVER (ORDER BY snapshot_date) as prev_value,
            account_value - LAG(account_value) OVER (ORDER BY snapshot_date) as daily_change,
            realized_pnl_day,
            unrealized_pnl,
            vix_level,
            market_regime
        FROM daily_snapshots
        {where}
        ORDER BY snapshot_date
    """
    
    return execute_query(query, params) or []


# =============================================================================
# MONTHLY SUMMARY FUNCTIONS
# =============================================================================

def update_monthly_summary(year: int, month: int) -> Dict:
    """Update or create monthly summary from trade data"""
    # Calculate from trades
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    
    trades_stats = get_trades_summary(start_date, end_date)
    
    # Get starting/ending account values from snapshots
    snapshots = execute_query(
        """SELECT 
            (SELECT account_value FROM daily_snapshots 
             WHERE snapshot_date >= %s ORDER BY snapshot_date LIMIT 1) as starting_value,
            (SELECT account_value FROM daily_snapshots 
             WHERE snapshot_date < %s ORDER BY snapshot_date DESC LIMIT 1) as ending_value
        """,
        (start_date, end_date)
    )
    
    values = snapshots[0] if snapshots else {}
    
    query = """
        INSERT INTO monthly_summaries 
            (year, month, starting_value, ending_value, total_premium, realized_pnl,
             trade_count, win_count, loss_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (year, month)
        DO UPDATE SET
            ending_value = EXCLUDED.ending_value,
            realized_pnl = EXCLUDED.realized_pnl,
            trade_count = EXCLUDED.trade_count,
            win_count = EXCLUDED.win_count,
            loss_count = EXCLUDED.loss_count
        RETURNING *
    """
    
    params = (
        year, month,
        values.get('starting_value'),
        values.get('ending_value'),
        0,  # total_premium - would need separate tracking
        trades_stats.get('total_pnl', 0),
        trades_stats.get('total_trades', 0),
        trades_stats.get('wins', 0),
        trades_stats.get('losses', 0)
    )
    
    result = execute_query(query, params)
    return result[0] if result else {}


def get_monthly_summaries(year: int = None) -> List[Dict]:
    """Get monthly summaries"""
    if year:
        return execute_query(
            "SELECT * FROM monthly_summaries WHERE year = %s ORDER BY month",
            (year,)
        ) or []
    else:
        return execute_query(
            "SELECT * FROM monthly_summaries ORDER BY year DESC, month DESC LIMIT 12"
        ) or []


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def test_connection() -> bool:
    """Test database connection"""
    try:
        result = execute_query("SELECT 1 as connected")
        return result and result[0].get('connected') == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def get_database_stats() -> Dict:
    """Get database statistics"""
    stats = execute_query("""
        SELECT 
            (SELECT COUNT(*) FROM trades) as total_trades,
            (SELECT COUNT(*) FROM positions WHERE status = 'OPEN') as open_positions,
            (SELECT COUNT(*) FROM daily_snapshots) as snapshot_days,
            (SELECT MAX(snapshot_date) FROM daily_snapshots) as last_snapshot
    """)
    return stats[0] if stats else {}


# Test on import
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    if test_connection():
        print("✅ Database connection successful")
        stats = get_database_stats()
        print(f"📊 Stats: {stats}")
    else:
        print("❌ Database connection failed")

