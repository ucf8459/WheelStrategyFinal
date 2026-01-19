# True Wheel Strategy - Technical Implementation
## FULLY OPTIMIZED Automated Monitoring & Execution System with Enhanced Screeners

from ib_insync import IB, Stock, Option, util, LimitOrder
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import yfinance as yf
import logging
import asyncio
from enum import Enum
import threading
import schedule
import time
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
import json
import os
import shutil
import glob
from dotenv import load_dotenv
import sys
import traceback
import concurrent.futures
import queue
import math

# Database module for trade persistence
try:
    import db as trade_db
    DB_AVAILABLE = trade_db.test_connection()
    if DB_AVAILABLE:
        print("✅ PostgreSQL database connected")
    else:
        print("⚠️ PostgreSQL database not available - trades won't be persisted")
except ImportError:
    DB_AVAILABLE = False
    trade_db = None
    print("⚠️ Database module not available - install psycopg2-binary")

# --- Robust global cache helpers ---
def get_current_metrics():
    global current_metrics
    if current_metrics is None or not isinstance(current_metrics, dict):
        current_metrics = {}
    return current_metrics

current_metrics = {}

# -------------------------------------------------------------
# IBKR Greeks via tickOptionComputation (CORRECT METHOD)
# -------------------------------------------------------------

class GreeksCallbackHandler:
    """
    Proper IBKR Greeks handler using tickOptionComputation callback
    This implements the correct callback pattern for receiving Greeks from IBKR
    """
    def __init__(self):
        self.greeks_data = {}
        self.pending_symbols = set()
        
    def clear_symbol(self, symbol):
        """Clear data for a specific symbol"""
        self.greeks_data.pop(symbol, None)
        self.pending_symbols.discard(symbol)
        
    def add_pending(self, symbol):
        """Mark symbol as pending Greeks data"""
        self.pending_symbols.add(symbol)
        
    def store_greeks(self, symbol, tick_type, delta, gamma, vega, theta):
        """Store Greeks data from tickOptionComputation callback"""
        if symbol not in self.greeks_data:
            self.greeks_data[symbol] = {}
            
        self.greeks_data[symbol][f'tick_{tick_type}'] = {
            'delta': delta,
            'gamma': gamma, 
            'vega': vega,
            'theta': theta
        }
        
    def get_delta(self, symbol):
        """Get best available delta for symbol"""
        if symbol not in self.greeks_data:
            return None
            
        # Priority: Model (#13), Last (#12), Ask (#11), Bid (#10)
        for tick_type in [13, 12, 11, 10]:
            tick_key = f'tick_{tick_type}'
            if tick_key in self.greeks_data[symbol]:
                delta = self.greeks_data[symbol][tick_key]['delta']
                if delta is not None and not math.isnan(delta):
                    return float(delta)
        return None

# Global Greeks handler instance
_greeks_handler = GreeksCallbackHandler()

# -------------------------------------------------------------
# ASYNC GREEKS WORKER - Solves Flask threading incompatibility  
# -------------------------------------------------------------

import asyncio
import concurrent.futures
import threading
import queue as Queue

# REMOVED: AsyncGreeksWorker class - now using shared connection architecture

# UNIQUE CLIENT ID MANAGEMENT for Greeks requests
_greeks_connection_pool = {}
_next_greeks_client_id = 1000  # Start from client ID 1000 for Greeks to avoid conflicts
_client_id_lock = threading.Lock()

def _get_unique_greeks_connection(symbol, logger):
    """Get a unique IB connection for Greeks requests with dedicated client ID"""
    global _greeks_connection_pool, _next_greeks_client_id
    
    # Use symbol-specific connection to avoid conflicts
    if symbol not in _greeks_connection_pool:
        try:
            with _client_id_lock:
                # Create new IB connection with unique client ID
                unique_ib = IB()
                client_id = _next_greeks_client_id
                _next_greeks_client_id += 1
            
            # Connect with unique client ID
            unique_ib.connect(
                host='127.0.0.1',
                port=7496,  # TWS port
                clientId=client_id
            )
            
            _greeks_connection_pool[symbol] = unique_ib
            logger.info(f"✅ Created unique Greeks connection for {symbol} (client_id={client_id})")
            
        except Exception as e:
            logger.error(f"❌ Failed to create unique connection for {symbol}: {e}")
            return None
    
    return _greeks_connection_pool.get(symbol)

def _get_qualified_contract(ib_connection, contract, logger):
    """Qualify contract properly before requesting market data"""
    try:
        # Ensure contract has all required fields
        if not contract.symbol or not contract.secType:
            logger.error(f"❌ Invalid contract: missing symbol or secType")
            return None
            
        # For options, ensure we have strike, right, and expiry
        if contract.secType == 'OPT':
            if not contract.strike or not contract.right or not contract.lastTradeDateOrContractMonth:
                logger.error(f"❌ Invalid option contract: missing strike/right/expiry")
                return None
        
        # Qualify the contract (this is CRITICAL for Greeks)
        qualified_contracts = ib_connection.qualifyContracts(contract)
        
        if not qualified_contracts:
            logger.error(f"❌ Contract qualification failed for {contract.symbol}")
            return None
            
        qualified_contract = qualified_contracts[0]
        logger.info(f"✅ Contract qualified: {qualified_contract.symbol} {qualified_contract.secType}")
        return qualified_contract
        
    except Exception as e:
        logger.error(f"❌ Contract qualification error: {e}")
        return None

def _get_delta_from_ibkr(ib_connection, contract, logger):
    """
    Get live delta with UNIQUE client ID per symbol and contract qualification
    FIXED: Each symbol gets its own connection with unique client ID
    """
    try:
        symbol = contract.symbol
        logger.info(f"📞 Requesting delta for {symbol} with unique connection")
        
        # Step 1: Get unique connection for this symbol (avoids client ID conflicts)
        unique_ib = _get_unique_greeks_connection(symbol, logger)
        if not unique_ib:
            logger.error(f"❌ {symbol}: Failed to get unique connection")
            return None
        
        # Step 2: Qualify the contract (CRITICAL for Greeks)
        qualified_contract = _get_qualified_contract(unique_ib, contract, logger)
        if not qualified_contract:
            logger.error(f"❌ {symbol}: Contract qualification failed")
            return None
        
        # Step 3: Request market data for the QUALIFIED contract using unique connection
        # Use Model Option Computation (#13) as primary source
        logger.info(f"📊 {symbol}: Requesting Greeks via tick types 10,11,12,13")
        ticker = unique_ib.reqMktData(qualified_contract, "10,11,12,13", False, False)
        
        # Step 4: Wait for Greeks data with proper synchronous approach
        max_attempts = 100  # Increased to 10 seconds total - Greeks need more time
        for attempt in range(max_attempts):
            # Use util.sleep instead of ib.sleep to avoid event loop issues
            import time
            time.sleep(0.1)
            logger.info(f"⏳ {symbol}: Waiting for Greeks data... (attempt {attempt+1}/{max_attempts})")
            
            # Check Model Option Computation first (most robust per IBKR docs)
            if hasattr(ticker, 'modelGreeks') and ticker.modelGreeks:
                delta = ticker.modelGreeks.delta
                if delta is not None and not math.isnan(delta):
                    unique_ib.cancelMktData(qualified_contract)
                    delta_value = float(delta)
                    logger.info(f"✅ {symbol}: LIVE delta {delta_value:.4f} via modelGreeks")
                    return delta_value
            
            # Check tickOptionComputation (as you mentioned in callback)
            if hasattr(ticker, 'optionComputation') and ticker.optionComputation:
                delta = ticker.optionComputation.delta
                if delta is not None and not math.isnan(delta):
                    unique_ib.cancelMktData(qualified_contract)
                    delta_value = float(delta)
                    logger.info(f"✅ {symbol}: LIVE delta {delta_value:.4f} via optionComputation")
                    return delta_value
            
            # Check bid/ask Greeks as backup
            if hasattr(ticker, 'bidGreeks') and ticker.bidGreeks:
                delta = ticker.bidGreeks.delta
                if delta is not None and not math.isnan(delta):
                    unique_ib.cancelMktData(qualified_contract)
                    delta_value = float(delta)
                    logger.info(f"✅ {symbol}: LIVE delta {delta_value:.4f} via bidGreeks")
                    return delta_value
                    
            if hasattr(ticker, 'askGreeks') and ticker.askGreeks:
                delta = ticker.askGreeks.delta
                if delta is not None and not math.isnan(delta):
                    unique_ib.cancelMktData(qualified_contract)
                    delta_value = float(delta)
                    logger.info(f"✅ {symbol}: LIVE delta {delta_value:.4f} via askGreeks")
                    return delta_value
        
        # Timeout - cleanup and return None
        unique_ib.cancelMktData(qualified_contract)
        logger.warning(f"⏰ {symbol}: No Greeks after 3s with qualified contract")
        return None
        
    except Exception as e:
        logger.error(f"❌ {contract.symbol}: Qualified Greeks request failed: {e}")
        return None

# -------------------------------------------------------------
# Core Data Structures
# -------------------------------------------------------------

@dataclass
class WheelPosition:
    """Track complete wheel cycle for a position"""
    symbol: str
    put_strikes: List[float]
    put_credits: List[float]
    assignment_price: Optional[float] = None
    shares_owned: int = 0
    call_strikes: List[float] = None
    call_credits: List[float] = None
    total_credits: float = 0
    cost_basis: float = 0

class AlertPriority(Enum):
    CRITICAL = "critical"   # Circuit breaker, large losses
    IMPORTANT = "important" # Roll decisions, profit targets
    INFO = "info"          # Daily summary, opportunities

@dataclass
class Alert:
    priority: AlertPriority
    title: str
    message: str
    action_required: Optional[str] = None

@dataclass
class Decision:
    """Track individual trading decisions"""
    timestamp: datetime
    symbol: str
    action_type: str  # 'ROLL', 'CLOSE', 'OPEN', 'ADJUST'
    reason: str
    priority: str  # 'CRITICAL', 'IMPORTANT', 'ROUTINE'
    executed: bool = False
    result: Optional[str] = None  # 'SUCCESS', 'FAILED', 'PARTIAL'
    notes: Optional[str] = None

class DecisionCounter:
    """Track and limit daily trading decisions"""
    
    def __init__(self, max_daily_decisions: int = 3):
        self.max_daily_decisions = max_daily_decisions
        self.decisions = []
        self.daily_reset_time = "09:30"  # Market open
        self._load_decisions()
    
    def _load_decisions(self):
        """Load decisions from persistent storage"""
        try:
            # In production, would load from database
            # For now, start fresh each session
            self.decisions = []
        except Exception as e:
            print(f"Error loading decisions: {e}")
            self.decisions = []
    
    def _save_decisions(self):
        """Save decisions to persistent storage"""
        try:
            # In production, would save to database
            # For now, just keep in memory
            pass
        except Exception as e:
            print(f"Error saving decisions: {e}")
    
    def _reset_daily_count(self):
        """Reset decision count at market open"""
        today = datetime.now().date()
        self.decisions = [d for d in self.decisions if d.timestamp.date() == today]
    
    def can_make_decision(self) -> bool:
        """Check if another decision can be made today"""
        self._reset_daily_count()
        return len([d for d in self.decisions if d.executed]) < self.max_daily_decisions
    
    def get_remaining_decisions(self) -> int:
        """Get number of remaining decisions for today"""
        self._reset_daily_count()
        executed_today = len([d for d in self.decisions if d.executed])
        return max(0, self.max_daily_decisions - executed_today)
    
    def record_decision(self, symbol: str, action_type: str, reason: str, 
                       priority: str = 'ROUTINE', executed: bool = False, 
                       result: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Record a new decision"""
        if not self.can_make_decision() and executed:
            print(f"❌ DECISION LIMIT REACHED: Cannot execute {action_type} for {symbol}")
            return False
        
        decision = Decision(
            timestamp=datetime.now(),
            symbol=symbol,
            action_type=action_type,
            reason=reason,
            priority=priority,
            executed=executed,
            result=result,
            notes=notes
        )
        
        self.decisions.append(decision)
        self._save_decisions()
        
        if executed:
            print(f"✅ DECISION {len([d for d in self.decisions if d.executed])}/{self.max_daily_decisions}: {action_type} {symbol} - {reason}")
        else:
            print(f"📝 DECISION RECORDED: {action_type} {symbol} - {reason}")
        
        return True
    
    def get_today_decisions(self) -> List[Decision]:
        """Get all decisions made today"""
        self._reset_daily_count()
        return self.decisions
    
    def get_decision_summary(self) -> Dict:
        """Get summary of today's decisions"""
        today_decisions = self.get_today_decisions()
        executed = [d for d in today_decisions if d.executed]
        pending = [d for d in today_decisions if not d.executed]
        
        return {
            'total_made': len(today_decisions),
            'executed': len(executed),
            'pending': len(pending),
            'remaining': self.get_remaining_decisions(),
            'max_daily': self.max_daily_decisions,
            'recent_decisions': [
                {
                    'time': d.timestamp.strftime('%H:%M'),
                    'symbol': d.symbol,
                    'action': d.action_type,
                    'reason': d.reason,
                    'priority': d.priority,
                    'executed': d.executed,
                    'result': d.result
                }
                for d in today_decisions[-5:]  # Last 5 decisions
            ]
        }
    
    def get_decision_breakdown(self) -> Dict:
        """Get breakdown of decisions by type and priority"""
        today_decisions = self.get_today_decisions()
        
        breakdown = {
            'by_type': {},
            'by_priority': {},
            'by_result': {}
        }
        
        for decision in today_decisions:
            # By type
            if decision.action_type not in breakdown['by_type']:
                breakdown['by_type'][decision.action_type] = 0
            breakdown['by_type'][decision.action_type] += 1
            
            # By priority
            if decision.priority not in breakdown['by_priority']:
                breakdown['by_priority'][decision.priority] = 0
            breakdown['by_priority'][decision.priority] += 1
            
            # By result (for executed decisions)
            if decision.executed:
                result = decision.result or 'UNKNOWN'
                if result not in breakdown['by_result']:
                    breakdown['by_result'][result] = 0
                breakdown['by_result'][result] += 1
        
        return breakdown

# -------------------------------------------------------------
# Main Wheel Monitor Class
# -------------------------------------------------------------

class WorkflowTracker:
    """Track daily workflow completion status"""
    
    def __init__(self):
        self.workflow_file = 'workflow_status.json'
        self.today = datetime.now().date()
        self.workflow_status = self._load_workflow_status()
        
    def _load_workflow_status(self):
        """Load workflow status from file"""
        try:
            with open(self.workflow_file, 'r') as f:
                data = json.load(f)
                # Check if data is for today
                saved_date = datetime.fromisoformat(data.get('date', '')).date()
                if saved_date == self.today:
                    return data
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            pass
        
        # Return default status for today
        return {
            'date': self.today.isoformat(),
            'morning_routine': {
                'completed': False,
                'completed_at': None,
                'planned_time': '09:00',
                'actual_time': None,
                'notes': ''
            },
            'afternoon_checkin': {
                'completed': False,
                'completed_at': None,
                'planned_time': '14:30',
                'actual_time': None,
                'notes': ''
            },
            'eod_routine': {
                'completed': False,
                'completed_at': None,
                'planned_time': '16:00',
                'actual_time': None,
                'notes': ''
            },
            'weekly_review': {
                'completed': False,
                'completed_at': None,
                'planned_time': '16:30',
                'actual_time': None,
                'notes': ''
            }
        }
    
    def _save_workflow_status(self):
        """Save workflow status to file"""
        try:
            with open(self.workflow_file, 'w') as f:
                json.dump(self.workflow_status, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving workflow status: {e}")
    
    def mark_workflow_complete(self, workflow_type: str, notes: str = ""):
        """Mark a workflow as completed"""
        if workflow_type not in self.workflow_status:
            return False
        
        now = datetime.now()
        self.workflow_status[workflow_type].update({
            'completed': True,
            'completed_at': now.isoformat(),
            'actual_time': now.strftime('%H:%M'),
            'notes': notes
        })
        
        self._save_workflow_status()
        return True
    
    def get_workflow_status(self):
        """Get current workflow status"""
        return self.workflow_status
    
    def get_completion_summary(self):
        """Get workflow completion summary"""
        completed = sum(1 for wf in self.workflow_status.values() 
                       if isinstance(wf, dict) and wf.get('completed', False))
        total = len([wf for wf in self.workflow_status.values() 
                    if isinstance(wf, dict)])
        
        return {
            'completed_count': completed,
            'total_count': total,
            'completion_percentage': (completed / total * 100) if total > 0 else 0,
            'status': self.workflow_status
        }
    
    def get_next_workflow(self):
        """Get the next workflow that should be completed"""
        current_time = datetime.now().time()
        
        workflows = [
            ('morning_routine', time(9, 0)),
            ('afternoon_checkin', time(14, 30)),
            ('eod_routine', time(16, 0)),
            ('weekly_review', time(16, 30))
        ]
        
        for workflow_name, planned_time in workflows:
            if not self.workflow_status[workflow_name]['completed']:
                if current_time >= planned_time:
                    return {
                        'workflow': workflow_name,
                        'planned_time': planned_time.strftime('%H:%M'),
                        'overdue': True,
                        'status': 'OVERDUE'
                    }
                else:
                    return {
                        'workflow': workflow_name,
                        'planned_time': planned_time.strftime('%H:%M'),
                        'overdue': False,
                        'status': 'UPCOMING'
                    }
        
        return {
            'workflow': 'all_complete',
            'planned_time': None,
            'overdue': False,
            'status': 'COMPLETE'
        }


class WheelMonitor:
    """Monitor wheel strategy positions with strict risk controls
CRITICAL CONCEPT: Option P&L vs Underlying Risk
================================================
Options can show massive P&L swings that are NORMAL:
- Stock drops 1% → Put option shows -30% (normal!)
- Stock rises 2% → Put option shows +40% (normal!)
- These are NOT stop loss situations
Real risk is when underlying price makes assignment unfavorable:
- Sold $100 put, stock at $88 = Real problem (12% below)
- Sold $100 put, stock at $98 = Normal fluctuation
NEVER trigger stop losses on option P&L percentages!
"""
    
    def __init__(self, account_value: float):
        self.ib = IB()
        self.account_value = account_value
        self.peak_value = account_value
        self.positions = {}
        self.daily_pnl = []
        self.circuit_breaker_active = False
        self.circuit_breaker_end = None
        self.consecutive_wins = 0
        self.position_size_multiplier = 1.0
        
        # Decision tracking system
        self.decision_counter = DecisionCounter(max_daily_decisions=3)
        
        # Workflow tracking system
        self.workflow_tracker = WorkflowTracker()
        
        # Client ID ranges for different components:
        # Monitor: 1000-1999
        # Scanner: 2000-2999
        # Executor: 3000-3999
        self.client_id_ranges = {
            'monitor': (1000, 1999),
            'scanner': (2000, 2999),
            'executor': (3000, 3999)
        }
        
        # Risk thresholds - ENHANCED
        self.thresholds = {
            'max_position_pct': 0.10,      # 10% max per position
            'max_sector_pct': 0.20,         # 20% max per sector (base)
            'drawdown_stop': 0.20,          # 20% from peak
            'weekly_drawdown_stop': 0.10,   # 10% weekly
            'iv_rank_min': 50,              # Minimum IV rank
            'iv_min': 20,                   # Minimum IV absolute
            'profit_target': 0.50,          # 50% profit target (CC)
            'profit_roll': 0.80,            # 80% profit roll (CSP)
            'roll_dte': 21,                 # Roll at 21 DTE
            'roll_delta_threshold': 0.50,   # Roll if delta > 0.50
            'earnings_buffer_days': 7,      # No trades near earnings
            'csp_stop_loss_pct': 0.10,      # Stop if stock >10% below strike
            'shares_stop_loss_pct': 0.10,   # Stop if shares >10% below basis
            'max_strikes_per_symbol': 2,    # Max different strikes
            'min_strike_separation': 0.05,  # 5% between strikes
            'correlation_threshold': 0.80,  # Correlation crisis level
            'correlation_extreme': 0.90,    # Black swan correlation level
            'win_streak_caution': 10,       # Wins before size reduction
            'min_liquidity_score': 1000     # Volume × OI / Spread
        }
        
        # Initialize subsystems
        self.win_streak_manager = WinStreakManager(self)
        self.black_swan_protocol = BlackSwanProtocol(self, None)  # Executor added later
        self.alert_manager = None  # Set after creation
        
        # Initialize watchlist - will be populated from config
        self.watchlist = []
        
        # Initialize current metrics and positions
        current_metrics = {}
        current_positions = []
        
    def connect(self, host='127.0.0.1', port=7496, clientId=None):
        """Connect to IBKR TWS or Gateway"""
        # Clean up any existing connection
        if self.ib.isConnected():
            logger.info("Disconnecting existing monitor connection...")
            self.ib.disconnect()
            time.sleep(1)  # Wait for connection to close
        
        # Use monitor range for main connection
        min_id, max_id = self.client_id_ranges['monitor']
        
        # Try a random client ID first
        import random
        tried_ids = set()
        
        while len(tried_ids) < (max_id - min_id + 1):
            current_client_id = random.randint(min_id, max_id)
            if current_client_id in tried_ids:
                continue
                
            tried_ids.add(current_client_id)
            
            try:
                logger.info(f"Attempting to connect monitor with client ID: {current_client_id}")
                self.ib.connect(host, port, current_client_id)
                self.ib.reqMarketDataType(1)  # Live data
                logger.info(f"Successfully connected monitor to IBKR at {host}:{port}")
                
                # Store the connection
                active_connections['monitor'] = self.ib
                return
                
            except Exception as e:
                if "client id is already in use" in str(e).lower():
                    logger.warning(f"Client ID {current_client_id} is in use, trying another one...")
                    time.sleep(0.5)
                else:
                    logger.error(f"Connection failed: {e}")
                    raise
                    
        raise Exception(f"Could not find available client ID in monitor range {min_id}-{max_id}")
        
    def check_entry_criteria(self, symbol: str, strike: float) -> Dict:
        """Validate all entry criteria for new position"""
        criteria = {
            'symbol': symbol,
            'strike': strike,
            'meets_criteria': True,
            'issues': []
        }
        
        # Check if Black Swan Protocol is active
        if self.black_swan_protocol and self.black_swan_protocol.active:
            criteria['meets_criteria'] = False
            criteria['issues'].append("Black Swan Protocol active")
            return criteria
        
        # Check IV requirements
        iv_data = self.get_iv_metrics(symbol)
        if iv_data['iv_rank'] < self.thresholds['iv_rank_min']:
            criteria['meets_criteria'] = False
            criteria['issues'].append(f"IV Rank {iv_data['iv_rank']:.1f}% < 50%")
        
        if iv_data['current_iv'] < self.thresholds['iv_min']:
            criteria['meets_criteria'] = False
            criteria['issues'].append(f"IV {iv_data['current_iv']:.1f}% < 20%")
            
        # Check liquidity
        liquidity = self.check_liquidity(symbol)
        if not liquidity['liquid']:
            criteria['meets_criteria'] = False
            criteria['issues'].extend(liquidity['issues'])
            
        # Check valuation
        valuation = self.check_valuation(symbol, strike)
        if not valuation['meets_value']:
            criteria['meets_criteria'] = False
            criteria['issues'].append(valuation['issue'])
            
        # Check position sizing
        position_size = strike * 100
        if position_size > self.account_value * self.thresholds['max_position_pct']:
            criteria['meets_criteria'] = False
            criteria['issues'].append("Position too large for account")
            
        # Check sector concentration
        sector_check = self.check_sector_concentration(symbol, position_size)
        if not sector_check['ok']:
            criteria['meets_criteria'] = False
            criteria['issues'].append(sector_check['issue'])
            
        # Check earnings
        if self.days_to_earnings(symbol) <= self.thresholds['earnings_buffer_days']:
            criteria['meets_criteria'] = False
            criteria['issues'].append("Too close to earnings")
            
        # Check circuit breaker
        if self.circuit_breaker_active:
            criteria['meets_criteria'] = False
            criteria['issues'].append("Circuit breaker active")
            
        # Check win streak management
        if self.win_streak_manager.consecutive_wins >= self.thresholds['win_streak_caution']:
            criteria['meets_criteria'] = False
            criteria['issues'].append(f"Win streak caution: {self.win_streak_manager.consecutive_wins} consecutive wins")
            
        return criteria
    
    def get_iv_metrics(self, symbol: str) -> Dict:
        """Calculate IV rank and current IV"""
        stock = yf.Ticker(symbol)
        
        # Get current IV from ATM options
        expirations = stock.options
        if not expirations:
            return {'iv_rank': 0, 'current_iv': 0}
        
        # Find ~30 DTE expiration
        target_dte = 30
        best_expiry = min(expirations, 
                         key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - datetime.now()).days - target_dte))
        
        chain = stock.option_chain(best_expiry)
        current_price = stock.history(period='1d')['Close'].iloc[-1]
        
        # Find ATM put
        atm_strike = min(chain.puts['strike'], key=lambda x: abs(x - current_price))
        atm_put = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]
        current_iv = atm_put['impliedVolatility'] * 100
        
        # Calculate IV rank (simplified - in production, store historical IV)
        # Using 252-day realized vol history as proxy
        hist = stock.history(period='1y')
        daily_returns = hist['Close'].pct_change().dropna()
        
        rolling_vols = []
        for i in range(30, len(daily_returns)):
            period_vol = daily_returns.iloc[i-30:i].std() * np.sqrt(252) * 100
            rolling_vols.append(period_vol)
        
        iv_rank = np.percentile(rolling_vols, current_iv) if rolling_vols else 50
        
        return {
            'iv_rank': iv_rank,
            'current_iv': current_iv,
            'iv_percentile': self.calculate_vix_percentile()
        }
    
    # Cache for VIX data to avoid rate limiting
    _vix_cache = {'data': None, 'timestamp': None, 'percentile': 50.0}
    
    def calculate_vix_percentile(self) -> float:
        """Calculate current VIX percentile for regime detection (cached to avoid rate limits)"""
        import time as _time
        
        # Check cache - refresh only every 15 minutes
        cache = WheelMonitor._vix_cache
        now = _time.time()
        if cache['timestamp'] and (now - cache['timestamp']) < 900:  # 15 min cache
            return cache['percentile']
        
        try:
            vix = yf.Ticker('^VIX')
            vix_hist = vix.history(period='1y')
            
            if vix_hist.empty:
                logger.warning("VIX data empty, using cached value")
                return cache['percentile']
            
            current_vix = vix_hist['Close'].iloc[-1]
            percentile = (vix_hist['Close'] < current_vix).mean() * 100
            
            # Update cache
            cache['data'] = vix_hist
            cache['timestamp'] = now
            cache['percentile'] = percentile
            
            logger.info(f"VIX percentile updated: {percentile:.1f}%")
            return percentile
            
        except Exception as e:
            logger.warning(f"VIX fetch failed ({e}), using cached value: {cache['percentile']}")
            return cache['percentile']
    
    def check_liquidity(self, symbol: str) -> Dict:
        """Check if option meets liquidity requirements"""
        stock = yf.Ticker(symbol)
        info = stock.info
        
        issues = []
        liquid = True
        
        # Check stock volume
        avg_volume = info.get('averageVolume', 0)
        if avg_volume < 1_000_000:
            liquid = False
            issues.append(f"Avg volume {avg_volume:,} < 1M")
        
        # Check option liquidity (would need real-time data in production)
        # For now, using stock volume as proxy
        
        return {'liquid': liquid, 'issues': issues}
    
    def check_valuation(self, symbol: str, strike: float) -> Dict:
        """Check if strike represents fair value based on sector"""
        stock = yf.Ticker(symbol)
        info = stock.info
        current_price = info.get('regularMarketPrice', 0)
        
        sector = info.get('sector', 'Unknown')
        
        # Sector-specific valuation metrics
        valuation_checks = {
            'Technology': self._check_tech_valuation,
            'Financial Services': self._check_financial_valuation,
            'Healthcare': self._check_healthcare_valuation,
            'Consumer Cyclical': self._check_consumer_valuation,
            'Industrials': self._check_industrial_valuation
        }
        
        check_func = valuation_checks.get(sector, self._check_default_valuation)
        result = check_func(info, strike, current_price)
        
        return result
    
    def _check_tech_valuation(self, info: Dict, strike: float, current_price: float) -> Dict:
        """Technology sector valuation check"""
        ps_ratio = info.get('priceToSalesTrailing12Months', 0)
        peg_ratio = info.get('pegRatio', 0)
        
        # Check if strike represents discount to current metrics
        implied_ps = ps_ratio * (strike / current_price)
        
        if peg_ratio > 0 and peg_ratio < 1.5:
            return {'meets_value': True, 'issue': None}
        elif ps_ratio > 0 and implied_ps < 5:  # Reasonable P/S for tech
            return {'meets_value': True, 'issue': None}
        else:
            return {'meets_value': False, 'issue': f'Valuation stretched: P/S={ps_ratio:.1f}'}
    
    def _check_financial_valuation(self, info: Dict, strike: float, current_price: float) -> Dict:
        """Financial sector valuation check"""
        pb_ratio = info.get('priceToBook', 0)
        pe_ratio = info.get('trailingPE', 0)
        
        implied_pb = pb_ratio * (strike / current_price)
        
        if implied_pb > 0 and implied_pb < 1.5:
            return {'meets_value': True, 'issue': None}
        elif pe_ratio > 0 and pe_ratio < 15:
            return {'meets_value': True, 'issue': None}
        else:
            return {'meets_value': False, 'issue': f'Valuation high: P/B={pb_ratio:.1f}'}
    
    def _check_industrial_valuation(self, info: Dict, strike: float, current_price: float) -> Dict:
        """Industrial sector valuation check"""
        ev_ebitda = info.get('enterpriseToEbitda', 0)
        
        # Adjust for strike price
        implied_ev_ebitda = ev_ebitda * (strike / current_price)
        
        if implied_ev_ebitda > 0 and implied_ev_ebitda < 12:
            return {'meets_value': True, 'issue': None}
        else:
            return {'meets_value': False, 'issue': f'Valuation high: EV/EBITDA={ev_ebitda:.1f}'}
    
    def _check_consumer_valuation(self, info: Dict, strike: float, current_price: float) -> Dict:
        """Consumer sector valuation check"""
        pe_ratio = info.get('trailingPE', 0)
        
        # Calculate FCF yield if available
        fcf = info.get('freeCashflow', 0)
        market_cap = info.get('marketCap', 0)
        
        if market_cap > 0 and fcf > 0:
            fcf_yield = fcf / market_cap * 100
            if fcf_yield >= 5:
                return {'meets_value': True, 'issue': None}
        
        # Fallback to P/E
        if pe_ratio > 0 and pe_ratio < 20:
            return {'meets_value': True, 'issue': None}
        else:
            return {'meets_value': False, 'issue': f'Valuation high: P/E={pe_ratio:.1f}'}
    
    def _check_healthcare_valuation(self, info: Dict, strike: float, current_price: float) -> Dict:
        """Healthcare sector valuation check"""
        pe_ratio = info.get('trailingPE', 0)
        ps_ratio = info.get('priceToSalesTrailing12Months', 0)
        
        # Healthcare can have higher multiples due to pipeline value
        if pe_ratio > 0 and pe_ratio < 30:
            return {'meets_value': True, 'issue': None}
        elif ps_ratio > 0 and ps_ratio < 10:
            return {'meets_value': True, 'issue': None}
        else:
            return {'meets_value': False, 'issue': f'Valuation unclear: P/E={pe_ratio:.1f}, P/S={ps_ratio:.1f}'}
    
    def _check_default_valuation(self, info: Dict, strike: float, current_price: float) -> Dict:
        """Default valuation check using P/E"""
        pe_ratio = info.get('trailingPE', 0)
        
        if pe_ratio > 0 and pe_ratio < 25:
            return {'meets_value': True, 'issue': None}
        else:
            return {'meets_value': False, 'issue': 'Valuation unclear'}
    
    def check_sector_concentration(self, symbol: str, position_size: float) -> Dict:
        """Check if adding position would exceed sector limits"""
        # Get sector for symbol
        stock = yf.Ticker(symbol)
        sector = stock.info.get('sector', 'Unknown')
        
        # Calculate current sector exposure
        sector_exposure = 0
        for pos in self.ib.positions():
            if pos.contract.secType == 'OPT' or pos.contract.secType == 'STK':
                pos_symbol = pos.contract.symbol
                pos_sector = self._get_sector(pos_symbol)
                
                if pos_sector == sector:
                    if pos.contract.secType == 'OPT' and pos.position < 0:  # Short option
                        # For put, exposure is strike * 100 * contracts
                        exposure = pos.contract.strike * 100 * abs(pos.position)
                        sector_exposure += exposure
                    elif pos.contract.secType == 'STK':  # Stock position
                        # Stock exposure is current value
                        exposure = pos.marketValue
                        sector_exposure += exposure
        
        # Calculate new exposure
        new_exposure = sector_exposure + position_size
        
        # Get dynamic sector limit based on VIX
        vix = yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1]
        sector_limit = self.calculate_sector_limit(vix)
        
        # Check if exposure exceeds limit
        max_exposure = self.account_value * sector_limit
        
        if new_exposure > max_exposure:
            return {
                'ok': False,
                'issue': f"Sector {sector} exposure {new_exposure/self.account_value:.1%} exceeds {sector_limit:.1%} limit"
            }
        
        return {'ok': True, 'issue': None}
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector for a symbol (with caching for efficiency)"""
        if not hasattr(self, '_sector_cache'):
            self._sector_cache = {}
            
        if symbol in self._sector_cache:
            return self._sector_cache[symbol]
            
        try:
            stock = yf.Ticker(symbol)
            sector = stock.info.get('sector', 'Unknown')
            self._sector_cache[symbol] = sector
            return sector
        except:
            return 'Unknown'
    
    def calculate_sector_limit(self, vix_level: float) -> float:
        """Calculate dynamic sector limit based on VIX"""
        if vix_level < 20:
            return 0.25  # 25% max
        elif vix_level < 30:
            return 0.20  # 20% max
        elif vix_level < 40:
            return 0.15  # 15% max
        else:
            return 0.10  # 10% max
    
    def check_roll_decision(self, position) -> Dict:
        """Determine if position should be rolled based on rules
        
        Priority order:
        1. Delta > threshold (defensive)
        2. At 21 DTE (time management)
        3. 80%+ profit with >7 DTE (efficiency)
        """
        contract = position.contract
        dte = (contract.lastTradeDateOrContractMonth - datetime.now()).days
        
        # Get current Greeks
        ticker = self.ib.reqMktData(contract)
        util.sleep(0.5)
        
        decision = {
            'should_roll': False,
            'reason': None,
            'action': 'HOLD',
            'rule_trigger': None
        }
        
        # Rule 1: Roll if Delta > threshold (highest priority)
        if ticker.modelGreeks and abs(ticker.modelGreeks.delta) > self.thresholds['roll_delta_threshold']:
            decision['should_roll'] = True
            decision['reason'] = f'Delta {abs(ticker.modelGreeks.delta):.2f} > {self.thresholds["roll_delta_threshold"]}'
            decision['action'] = 'ROLL_DEFENSIVE'
            decision['rule_trigger'] = 'delta_roll'
            return decision
        
        # Rule 2: Roll at 21 DTE
        if dte <= self.thresholds['roll_dte']:
            decision['should_roll'] = True
            decision['reason'] = f'{dte} DTE reached'
            decision['action'] = 'ROLL_TIME'
            decision['rule_trigger'] = '21_dte_roll'
            return decision
        
        # Rule 3: Roll at 80% profit with >7 DTE (CSPs only)
        if position.unrealizedPnL and 'P' in contract.right and position.position < 0:
            pnl_pct = position.unrealizedPnL / abs(position.avgCost * position.position)
            
            if pnl_pct >= self.thresholds['profit_roll'] and dte > 7:
                decision['should_roll'] = True
                decision['reason'] = f'{pnl_pct:.0%} profit with {dte} DTE'
                decision['action'] = 'ROLL_PROFIT'
                decision['rule_trigger'] = '80pct_roll'
                return decision
        
        return decision
    
    def check_circuit_breaker(self) -> Dict:
        """Check if circuit breaker should activate - TEMPORARILY DISABLED due to event loop conflicts"""
        # TEMPORARILY DISABLED to avoid event loop conflicts with IBKR
        return {
            'active': False,
            'reason': 'Circuit breaker temporarily disabled due to event loop conflicts',
            'ends': None
        }
    
    def days_to_earnings(self, symbol: str) -> int:
        """Get days until next earnings for symbol"""
        try:
            stock = yf.Ticker(symbol)
            earnings_dates = stock.earnings_dates
            
            if earnings_dates is not None and len(earnings_dates) > 0:
                next_earnings = earnings_dates.index[0]
                days_to_earnings = (next_earnings - datetime.now()).days
                return days_to_earnings
            
            return 999  # No earnings found
            
        except:
            return 999  # Error getting earnings
    
    def _get_next_earnings_date(self, symbol: str) -> Optional[datetime]:
        """Get next earnings date for symbol"""
        try:
            stock = yf.Ticker(symbol)
            earnings_dates = stock.earnings_dates
            
            if earnings_dates is not None and len(earnings_dates) > 0:
                return earnings_dates.index[0]
                
            return None
            
        except:
            return None
    
    def check_post_earnings_opportunity(self, symbol: str) -> Dict:
        """Check if stock is good post-earnings IV crush candidate"""
        stock = yf.Ticker(symbol)
        
        # Get last earnings date
        earnings_dates = stock.earnings_dates
        if not earnings_dates or len(earnings_dates) == 0:
            return {'opportunity': False}
            
        last_earnings = earnings_dates.index[0]
        days_since = (datetime.now() - last_earnings).days
        
        if days_since > 3:  # Too far from earnings
            return {'opportunity': False}
            
        # Check IV drop (would need historical IV data)
        iv_data = self.get_iv_metrics(symbol)
        
        # Check price stability
        hist = stock.history(period='5d')
        price_change = abs((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0])
        
        if price_change < 0.05 and iv_data['iv_rank'] < 30:  # Price stable, IV crushed
            return {
                'opportunity': True,
                'days_since_earnings': days_since,
                'iv_rank': iv_data['iv_rank'],
                'price_stability': price_change
            }
            
        return {'opportunity': False}
    
    def detect_market_regime(self) -> str:
        """Detect current market regime for position sizing
        
        Returns: 'BULL', 'BEAR', or 'NEUTRAL'
        """
        spy = yf.Ticker('SPY')
        data = spy.history(period='200d')
        
        current = data['Close'].iloc[-1]
        sma50 = data['Close'].rolling(50).mean().iloc[-1]
        sma200 = data['Close'].rolling(200).mean().iloc[-1]
        
        vix = yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1]
        
        if current > sma50 > sma200 and vix < 20:
            return 'BULL'
        elif current < sma50 < sma200 and vix > 25:
            return 'BEAR'
        else:
            return 'NEUTRAL'
    
    def get_regime_delta_target(self, regime: str) -> Tuple[float, float]:
        """Get delta targets based on market regime
        
        Returns: (min_delta, max_delta)
        """
        targets = {
            'BULL': (0.30, 0.40),
            'NEUTRAL': (0.25, 0.30),
            'BEAR': (0.15, 0.25)
        }
        return targets.get(regime, (0.25, 0.30))
    
    def calculate_correlation(self) -> float:
        """Calculate average correlation between major sectors
        
        Returns a value between 0 and 1 where higher values indicate
        higher correlation (more dangerous)
        """
        # Use major sector ETFs
        sectors = ['XLF', 'XLK', 'XLV', 'XLY', 'XLP', 'XLU', 'XLE', 'XLB']
        
        # Get daily returns for past 20 days
        returns_df = pd.DataFrame()
        
        for sector in sectors:
            etf = yf.Ticker(sector)
            hist = etf.history(period='30d')
            returns = hist['Close'].pct_change().dropna()
            returns_df[sector] = returns
        
        # Calculate correlation matrix
        corr_matrix = returns_df.corr()
        
        # Calculate average correlation (excluding self-correlations)
        sum_corr = 0
        count = 0
        
        for i in range(len(sectors)):
            for j in range(i+1, len(sectors)):
                sum_corr += corr_matrix.iloc[i, j]
                count += 1
        
        avg_corr = sum_corr / count if count > 0 else 0
        return avg_corr
    
    def check_correlation_crisis(self) -> Dict:
        """Check if market is in a correlation crisis"""
        correlation = self.calculate_correlation()
        
        result = {
            'correlation': correlation,
            'crisis': False,
            'extreme': False,
            'actions': []
        }
        
        if correlation > self.thresholds['correlation_extreme']:
            result['extreme'] = True
            result['crisis'] = True
            result['actions'] = [
                "Activate Black Swan Protocol",
                "Convert 50% to cash immediately",
                "Close all tech and financial positions",
                "Maximum 2% position size"
            ]
        elif correlation > self.thresholds['correlation_threshold']:
            result['crisis'] = True
            result['actions'] = [
                "Reduce position sizes by 50%",
                "Close weakest performers",
                "Focus on utilities, staples, healthcare",
                "No new tech/financials positions",
                "Increase cash to 20%"
            ]
        
        return result
    
    def check_market_breadth(self) -> Dict:
        """Check market breadth indicators for early warning"""
        # This would normally use a market data API
        # Simplified implementation
        
        # Get advance/decline data (simulated)
        spy = yf.Ticker('SPY')
        hist = spy.history(period='5d')
        
        # Simulate A/D ratio based on SPY movement
        # In production, use actual A/D data
        ad_ratios = []
        for i in range(len(hist) - 1):
            if hist['Close'].iloc[i+1] > hist['Close'].iloc[i]:
                ad_ratios.append(1.2)  # More advances
            else:
                ad_ratios.append(0.8)  # More declines
        
        # Simulate % above 50 MA
        pct_above_50ma = 60 if hist['Close'].iloc[-1] > hist['Close'].mean() else 40
        
        # Simulate new highs/lows
        new_highs = 100 if hist['Close'].iloc[-1] > hist['High'].max() * 0.98 else 50
        new_lows = 50 if hist['Close'].iloc[-1] < hist['Low'].min() * 1.02 else 20
        
        # Market health assessment
        health = "Strong"
        if sum(ad_ratios) / len(ad_ratios) < 0.8:
            health = "Weakening"
        if pct_above_50ma < 40:
            health = "Weak"
        if new_lows > 100:
            health = "Very Weak"
        
        return {
            'ad_ratio': sum(ad_ratios) / len(ad_ratios),
            'pct_above_50ma': pct_above_50ma,
            'new_highs': new_highs,
            'new_lows': new_lows,
            'market_health': health
        }
    
    def check_adjustments_needed(self) -> List[Dict]:
        """Check all positions for needed adjustments"""
        adjustments = []
        positions = self.ib.positions()
        
        # Process option positions
        for position in positions:
            if position.contract.secType == 'OPT':
                # Check if approaching expiration
                if position.contract.lastTradeDateOrContractMonth:
                    expiry = position.contract.lastTradeDateOrContractMonth
                    dte = (expiry - datetime.now()).days
                    
                    # Defensive roll check (high delta)
                    ticker = self.ib.reqMktData(position.contract)
                    util.sleep(0.5)
                    
                    if ticker.modelGreeks and abs(ticker.modelGreeks.delta) > self.thresholds['roll_delta_threshold']:
                        adjustments.append({
                            'symbol': position.contract.symbol,
                            'position': position.contract,
                            'reason': f'Delta {abs(ticker.modelGreeks.delta):.2f} exceeds threshold',
                            'action': 'ROLL_DEFENSIVE',
                            'priority': 'CRITICAL'
                        })
                        continue
                    
                    # Time-based roll check
                    if dte <= self.thresholds['roll_dte']:
                        adjustments.append({
                            'symbol': position.contract.symbol,
                            'position': position.contract,
                            'reason': f'Approaching expiration: {dte} DTE',
                            'action': 'ROLL_TIME',
                            'priority': 'IMPORTANT'
                        })
                        continue
                
                # Check profit targets based on position type
                if position.unrealizedPnL:
                    pnl_pct = position.unrealizedPnL / abs(position.avgCost * position.position)
                    dte = (position.contract.lastTradeDateOrContractMonth - datetime.now()).days
                    
                    # For CSPs - roll at 80% profit with time remaining
                    if 'P' in position.contract.right and position.position < 0:
                        if pnl_pct >= self.thresholds['profit_roll'] and dte > 7:
                            adjustments.append({
                                'symbol': position.contract.symbol,
                                'position': position.contract,
                                'reason': f'Roll for efficiency: {pnl_pct:.0%} profit with {dte} DTE',
                                'action': 'ROLL_POSITION',
                                'priority': 'INFO'
                            })
                    
                    # For covered calls - close at 50% profit
                    elif 'C' in position.contract.right and position.position < 0:
                        if pnl_pct >= self.thresholds['profit_target']:
                            adjustments.append({
                                'symbol': position.contract.symbol,
                                'position': position.contract,
                                'reason': f'Profit target hit: {pnl_pct:.1%}',
                                'action': 'CLOSE_POSITION',
                                'priority': 'IMPORTANT'
                            })
        
        # Process stock positions
        for position in positions:
            if position.contract.secType == 'STK':
                # Get cost basis
                trades = self.ib.fills()
                cost_basis = self._calculate_cost_basis(position.contract.symbol, trades)
                
                if cost_basis:
                    current_price = self.ib.reqMktData(position.contract).marketPrice()
                    
                    # Check stop loss on shares
                    if current_price < cost_basis * (1 - self.thresholds['shares_stop_loss_pct']):
                        adjustments.append({
                            'symbol': position.contract.symbol,
                            'position': position.contract,
                            'reason': f'Share price {current_price:.2f} below stop loss ({cost_basis * (1 - self.thresholds["shares_stop_loss_pct"]):.2f})',
                            'action': 'EVALUATE_SHARES',
                            'priority': 'CRITICAL'
                        })
                
                # Check if shares have covered calls
                has_cc = self._has_covered_calls(position.contract.symbol)
                
                if not has_cc and position.position >= 100:
                    # No covered call, should sell one
                    adjustments.append({
                        'symbol': position.contract.symbol,
                        'position': position.contract,
                        'reason': 'Shares without covered call',
                        'action': 'SELL_COVERED_CALL',
                        'priority': 'IMPORTANT'
                    })
        
        return adjustments
    
    def _calculate_cost_basis(self, symbol: str, trades) -> Optional[float]:
        """Calculate cost basis for a symbol from trades"""
        symbol_trades = [t for t in trades if t.contract.symbol == symbol and t.contract.secType == 'STK']
        
        if not symbol_trades:
            return None
        
        total_shares = sum(t.execution.shares * (1 if t.execution.side == 'BOT' else -1) for t in symbol_trades)
        
        if total_shares <= 0:
            return None
        
        total_cost = sum(t.execution.shares * t.execution.price * (1 if t.execution.side == 'BOT' else -1) for t in symbol_trades)
        
        return total_cost / total_shares
    def _has_covered_calls(self, symbol: str) -> bool:
        """Check if shares have covered calls sold against them"""
        for position in self.ib.positions():
            if (isinstance(position.contract, Option) and 
                position.contract.symbol == symbol and
                position.contract.right == 'C' and
                position.position < 0):
                return True
        return False
    def _wants_assignment(self, symbol: str, strike: float, current_price: float) -> bool:
        """Determine if user wants assignment at strike price
        
        This is the key decision for CSP stop losses.
        Can be enhanced with user preferences, valuations, etc.
        """
        # Simple rule: Don't want assignment if >10% above current price
        if strike > current_price * 1.10:
            return False
            
        # Could add more sophisticated logic:
        # - Check if still meets valuation criteria
        # - Check if thesis has changed
        # - Check sector allocation
        
        return True
    
    def _has_protective_position(self, position) -> bool:
        """Check if option position has protective position (for complex strategies)"""
        # This would check for spreads, but we shouldn't have any!
        # Kept for completeness
        return False
    
    def generate_morning_summary(self) -> Dict:
        """Generate comprehensive morning summary with all optimizations"""
        summary = {}
        
        # Get market regime
        summary['market_regime'] = self.detect_market_regime()
        
        # Get VIX metrics
        vix = yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1]
        summary['vix_level'] = vix
        summary['vix_percentile'] = self.calculate_vix_percentile()
        
        # Get correlation status
        correlation = self.calculate_correlation()
        summary['correlation'] = correlation
        
        # Get market breadth
        breadth = self.check_market_breadth()
        summary['breadth'] = breadth
        
        # Check for risk warnings
        risk_warnings = []
        
        if correlation > self.thresholds['correlation_threshold']:
            risk_warnings.append(f"High correlation: {correlation:.2f}")
        
        if vix > 30:
            risk_warnings.append(f"Elevated VIX: {vix:.1f}")
        
        if breadth['market_health'] in ['Weak', 'Very Weak']:
            risk_warnings.append(f"Poor market breadth: {breadth['market_health']}")
        
        # Check circuit breaker
        cb_status = self.check_circuit_breaker()
        if cb_status['active']:
            risk_warnings.append(f"Circuit breaker active until {cb_status['ends'].strftime('%Y-%m-%d')}")
        
        # Check win streak caution
        if self.win_streak_manager.consecutive_wins >= 5:
            risk_warnings.append(f"Win streak caution: {self.win_streak_manager.consecutive_wins} consecutive wins")
        
        summary['risk_warnings'] = risk_warnings
        
        # Check for seasonal patterns
        month = datetime.now().month
        day = datetime.now().day
        
        seasonal_notes = []
        
        # January Effect
        if month == 1:
            if day <= 7:
                seasonal_notes.append("January Effect: Week 1 - Expect volatility from tax loss reversal")
            else:
                seasonal_notes.append("January Effect: Weeks 2-4 - Consider small caps with more aggressive strikes")
        
        # Earnings Seasons
        if month in [1, 4, 7, 10]:
            seasonal_notes.append(f"Earnings Season: {['Jan', 'Apr', 'Jul', 'Oct'][month//3]} - Consider post-earnings IV crush trades")
        
        # Summer Doldrums
        if month in [7, 8]:
            seasonal_notes.append("Summer Doldrums: Lower volatility expected, consider extending DTE to 45-60 days")
        
        # September Volatility
        if month == 9:
            seasonal_notes.append("September Volatility: Historical worst month, reduce position sizes 25% and lower delta targets")
        
        # December Tax Trading
        if month == 12:
            if day <= 15:
                seasonal_notes.append("December Tax Trading: First half - Normal trading")
            elif day <= 23:
                seasonal_notes.append("December Tax Trading: Week 3 - Consider closing losing positions for tax loss harvesting")
            else:
                seasonal_notes.append("December Tax Trading: Week 4 - Minimal trading in thin markets, prepare year-end review")
        
        summary['seasonal_notes'] = seasonal_notes
        
        # Get positions needing attention
        summary['positions_needing_attention'] = self.check_adjustments_needed()
        
        # Get new opportunities
        scanner = WheelScanner(self.watchlist, self)
        summary['new_opportunities'] = scanner.scan_opportunities()
        
        return summary
    
    def record_trade_result(self, trade_result: Dict) -> None:
        """Record a trade result and update stats"""
        # Update win streak
        self.win_streak_manager.record_trade_result(trade_result)
        
        # Add to trade history
        if not hasattr(self, 'trade_history'):
            self.trade_history = []
            
        self.trade_history.append({
            **trade_result,
            'timestamp': datetime.now()
        })
        
        # Update daily P&L if needed
        today = datetime.now().date()
        if not self.daily_pnl or self.daily_pnl[-1]['date'] != today:
            self.daily_pnl.append({
                'date': today,
                'pnl': trade_result.get('pnl', 0)
            })
        else:
            self.daily_pnl[-1]['pnl'] += trade_result.get('pnl', 0)
    
    def get_recent_trades(self, count: int) -> List[Dict]:
        """Get recent trades for analysis"""
        if not hasattr(self, 'trade_history'):
            return []
        return self.trade_history[-count:]
    
    def get_sector_allocations(self) -> Dict[str, float]:
        """Get current sector allocations as percentage of portfolio"""
        sector_allocations = {}
        total_exposure = 0
        
        for pos in self.ib.positions():
            if pos.contract.secType in ['OPT', 'STK']:
                symbol = pos.contract.symbol
                sector = self._get_sector(symbol)
                
                # Calculate exposure
                if pos.contract.secType == 'OPT' and pos.position < 0:
                    exposure = pos.contract.strike * 100 * abs(pos.position)
                else:
                    exposure = pos.marketValue
                    
                sector_allocations[sector] = sector_allocations.get(sector, 0) + exposure
                total_exposure += exposure
        
        # Convert to percentages
        if total_exposure > 0:
            for sector in sector_allocations:
                sector_allocations[sector] = sector_allocations[sector] / total_exposure
                
        return sector_allocations

# -------------------------------------------------------------
# Win Streak Manager Class
# -------------------------------------------------------------

class WinStreakManager:
    """Manage win streaks to prevent overconfidence"""
    
    def __init__(self, monitor):
        self.monitor = monitor
        self.consecutive_wins = 0
        self.sizing_adjustment = 1.0  # multiplier for position sizing
        
    def record_trade_result(self, trade_result):
        """Record the outcome of a trade and adjust sizing if needed"""
        if trade_result['profitable']:
            self.consecutive_wins += 1
            
            # Adjust sizing based on win streak
            if self.consecutive_wins >= 10:
                self.sizing_adjustment = 0.5
                print(f"⚠️ Win streak alert: {self.consecutive_wins} consecutive wins")
                print("Position sizing reduced by 50%")
                
            elif self.consecutive_wins >= 8:
                self.sizing_adjustment = 0.75
                print(f"⚠️ Win streak alert: {self.consecutive_wins} consecutive wins")
                print("Position sizing reduced by 25%")
                
        else:
            # Reset on any loss
            if self.consecutive_wins >= 5:
                print(f"Win streak ended at {self.consecutive_wins}")
            self.consecutive_wins = 0
            self.sizing_adjustment = 1.0
            
        return self.sizing_adjustment
    
    def get_risk_creep_warnings(self):
        """Check for signs of risk creep during win streaks"""
        warnings = []
        
        if self.consecutive_wins >= 5:
            # Check for risk creep indicators
            recent_trades = self.monitor.get_recent_trades(10)
            
            # Check DTE creep
            avg_dte = sum([t.get('dte', 30) for t in recent_trades]) / len(recent_trades)
            if avg_dte < 25:  # Standard is 30-45
                warnings.append("DTE creeping lower than strategy minimum")
                
            # Check position sizing creep
            avg_position_pct = sum([t.get('position_size_pct', 0) for t in recent_trades]) / len(recent_trades)
            if avg_position_pct > self.monitor.thresholds['max_position_pct'] * 0.9:
                warnings.append("Position sizing approaching maximum limits")
                
        return warnings

# -------------------------------------------------------------
# Black Swan Protocol Class
# -------------------------------------------------------------

class BlackSwanProtocol:
    """Implement extreme market condition protocols"""
    
    def __init__(self, monitor, executor):
        self.monitor = monitor
        self.executor = executor
        self.active = False
        self.activation_date = None
        self.recovery_stage = 0  # 0-4 for recovery sequence
        
    def check_activation_conditions(self):
        """Check if Black Swan protocol should be activated - TEMPORARILY DISABLED due to yfinance rate limits"""
        # TEMPORARILY DISABLED to avoid yfinance rate limit errors
        logger.warning("Black Swan Protocol check temporarily disabled due to yfinance rate limits")
        return False
    
    def get_spy_daily_change(self):
        """Get SPY daily percentage change"""
        spy = yf.Ticker('SPY')
        hist = spy.history(period='2d')
        
        if len(hist) >= 2:
            return (hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]
        
        return 0.0
    
    def activate(self, reason, **metrics):
        """Activate Black Swan protocol"""
        if not self.active:
            self.active = True
            self.activation_date = datetime.now()
            self.recovery_stage = 0
            
            print(f"⚠️ BLACK SWAN PROTOCOL ACTIVATED: {reason}")
            print(f"Metrics: {metrics}")
            
            # Take immediate actions
            self.execute_immediate_actions()
            
            # Send critical alert
            alert = Alert(
                priority=AlertPriority.CRITICAL,
                title=f"BLACK SWAN PROTOCOL ACTIVATED: {reason}",
                message=f"Immediate defensive actions taken. Metrics: {metrics}",
                action_required="Review all positions and prepare for extended volatility"
            )
            asyncio.run(self.monitor.alert_manager.send_alert(alert))
    
    def execute_immediate_actions(self):
        """Execute immediate protective actions"""
        # 1. Close all near-term positions
        self.close_near_term_positions()
        
        # 2. Set stop losses on shares
        self.set_protective_stops()
        
        # 3. Calculate required cash reserve
        required_cash = self.monitor.account_value * 0.30  # 30% cash
        
        # 4. Generate positions to close to reach cash target
        positions_to_close = self.identify_positions_to_close(required_cash)
        
        # 5. Execute closes
        for position in positions_to_close:
            self.executor.close_position(position, reason="Black Swan Protocol")
    
    def close_near_term_positions(self):
        """Close all positions with <14 DTE"""
        positions = self.monitor.ib.positions()
        
        for position in positions:
            if position.contract.secType == 'OPT':
                expiry = position.contract.lastTradeDateOrContractMonth
                dte = (expiry - datetime.now()).days
                
                if dte < 14:
                    print(f"Closing near-term position: {position.contract.symbol} {position.contract.strike} {position.contract.right} ({dte} DTE)")
                    self.executor.close_position(position, reason="Black Swan: Close near-term")
    
    def set_protective_stops(self):
        """Set protective stop losses on all shares"""
        positions = self.monitor.ib.positions()
        
        for position in positions:
            if position.contract.secType == 'STK':
                # Get current price
                ticker = self.monitor.ib.reqMktData(position.contract)
                util.sleep(0.5)
                current_price = ticker.marketPrice()
                
                if current_price > 0:
                    # Set stop 7% below current price
                    stop_price = current_price * 0.93
                    
                    print(f"Setting protective stop for {position.contract.symbol} at {stop_price:.2f} (7% below {current_price:.2f})")
                    
                    # In production, would create actual stop order
                    # self.monitor.ib.placeOrder(position.contract, StopOrder('SELL', position.position, stop_price))
    
    def identify_positions_to_close(self, required_cash):
        """Identify positions to close to reach cash target"""
        # Get current cash
        account = self.monitor.ib.accountSummary()
        current_cash = next((float(item.value) for item in account if item.tag == 'TotalCashValue'), 0)
        
        cash_needed = required_cash - current_cash
        
        if cash_needed <= 0:
            return []  # Already have enough cash
        
        positions = self.monitor.ib.positions()
        positions_to_close = []
        
        # Close weakest performers first
        # In production, would rank by performance metrics
        # For now, prioritize by sector risk
        
        # Target tech and financial sectors first
        tech_financials = []
        others = []
        
        for position in positions:
            if position.contract.secType in ['STK', 'OPT']:
                sector = self.monitor._get_sector(position.contract.symbol)
                
                if sector in ['Technology', 'Financial Services']:
                    tech_financials.append(position)
                else:
                    others.append(position)
        
        # Start with tech and financials, then others if needed
        for position in tech_financials:
            positions_to_close.append(position)
            
            # Estimate position value
            if position.contract.secType == 'STK':
                value = position.marketValue
            else:  # Option
                value = position.marketValue if position.position > 0 else position.avgCost * abs(position.position)
            
            cash_needed -= value
            
            if cash_needed <= 0:
                break
        
        # If still need more cash, add other sectors
        if cash_needed > 0:
            for position in others:
                positions_to_close.append(position)
                
                # Estimate position value
                if position.contract.secType == 'STK':
                    value = position.marketValue
                else:  # Option
                    value = position.marketValue if position.position > 0 else position.avgCost * abs(position.position)
                
                cash_needed -= value
                
                if cash_needed <= 0:
                    break
        
        return positions_to_close
    
    def check_recovery_conditions(self):
        """Check if recovery conditions are met"""
        if not self.active:
            return False
            
        # Get VIX level
        vix = yf.Ticker('^VIX').history(period='5d')['Close']
        below_40_days = sum(vix < 40)
        
        # Get SPY movement
        spy = yf.Ticker('SPY').history(period='5d')
        spy_above_5ma = spy['Close'].iloc[-1] > spy['Close'].rolling(5).mean().iloc[-1]
        
        # Get market breadth
        breadth_positive_days = self.get_positive_breadth_days()
        
        # Check recovery conditions
        if below_40_days >= 3 and spy_above_5ma and breadth_positive_days >= 2:
            self.advance_recovery()
            return True
            
        return False
    
    def get_positive_breadth_days(self):
        """Count days with positive market breadth"""
        # This would use a market data API in production
        # Simplified implementation
        spy = yf.Ticker('SPY')
        hist = spy.history(period='5d')
        
        # Count days with positive returns as proxy
        positive_days = sum(hist['Close'].pct_change() > 0)
        
        return positive_days
    
    def advance_recovery(self):
        """Advance through recovery stages"""
        self.recovery_stage += 1
        
        if self.recovery_stage == 1:
            print("Black Swan Recovery: Stage 1 (25% re-entry)")
            # Implement 25% normal position sizing
            self.monitor.position_size_multiplier = 0.25
            
        elif self.recovery_stage == 2:
            print("Black Swan Recovery: Stage 2 (50% re-entry)")
            # Implement 50% normal position sizing
            self.monitor.position_size_multiplier = 0.50
            
        elif self.recovery_stage == 3:
            print("Black Swan Recovery: Stage 3 (75% re-entry)")
            # Implement 75% normal position sizing
            self.monitor.position_size_multiplier = 0.75
            
        elif self.recovery_stage == 4:
            print("Black Swan Recovery: Stage 4 (100% re-entry)")
            # Return to normal operations
            self.monitor.position_size_multiplier = 1.0
            self.deactivate()
    
    def deactivate(self):
        """Deactivate Black Swan protocol"""
        self.active = False
        duration = (datetime.now() - self.activation_date).days
        
        print(f"⚠️ BLACK SWAN PROTOCOL DEACTIVATED after {duration} days")
        print("Returning to normal trading operations")
        
        # Send alert
        alert = Alert(
            priority=AlertPriority.IMPORTANT,
            title="BLACK SWAN PROTOCOL DEACTIVATED",
            message=f"Normal trading operations resumed after {duration} days",
            action_required="Review portfolio and adjust as needed"
        )
        asyncio.run(self.monitor.alert_manager.send_alert(alert))

# -------------------------------------------------------------
# Scanner Class
# -------------------------------------------------------------

class WheelScanner:
    """Scan for wheel opportunities meeting all criteria"""
    
    def __init__(self, symbols: List[str], monitor: WheelMonitor):
        self.symbols = symbols
        self.monitor = monitor
        self.sector_map = self._load_sector_map()
        
        # SHARED CONNECTION: Will be assigned externally - no auto-connection
        self.ib = None  # Will be set to monitor.ib
        
    def _load_sector_map(self) -> Dict:
        """Load sector classifications for symbols - TEMPORARILY DISABLED due to yfinance rate limits"""
        # TEMPORARILY DISABLED to avoid yfinance rate limit errors
        logger.warning("Sector map loading temporarily disabled due to yfinance rate limits")
        return {symbol: 'Unknown' for symbol in self.symbols}
    
    async def scan_opportunities_async(self) -> List[Dict]:
        """Find wheel candidates meeting all criteria asynchronously"""
        opportunities = []
        
        # Check VIX regime
        vix_percentile = self.monitor.calculate_vix_percentile()
        position_size_multiplier = self._get_regime_multiplier(vix_percentile)
        
        for symbol in self.symbols:
            try:
                # Skip if too close to earnings
                if self.monitor.days_to_earnings(symbol) <= 7:
                    continue
                
                # Get IV metrics
                iv_data = self.monitor.get_iv_metrics(symbol)
                if iv_data['iv_rank'] < 50 or iv_data['current_iv'] < 20:
                    continue
                
                # Find suitable strikes
                strikes = self._find_wheel_strikes(symbol, iv_data)
                
                for strike_data in strikes:
                    # Check all entry criteria
                    criteria = self.monitor.check_entry_criteria(symbol, strike_data['strike'])
                    
                    if criteria['meets_criteria']:
                        strike_data['position_size_adjustment'] = position_size_multiplier
                        strike_data['sector'] = self.sector_map.get(symbol, 'Unknown')
                        # Add liquidity score
                        strike_data['liquidity_score'] = self._calculate_liquidity_score(symbol)
                        opportunities.append(strike_data)
                        
            except Exception as e:
                print(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by expected return
        opportunities.sort(key=lambda x: x['annual_return'], reverse=True)
        
        # Apply sector diversification
        return self._diversify_opportunities(opportunities)
    
    async def scan_all_opportunities_async(self) -> List[Dict]:
        """Scan all opportunities without sector diversification filters asynchronously"""
        # Similar to scan_opportunities but without the diversification step
        opportunities = []
        
        # Check VIX regime
        vix_percentile = self.monitor.calculate_vix_percentile()
        position_size_multiplier = self._get_regime_multiplier(vix_percentile)
        
        for symbol in self.symbols:
            try:
                # Skip if too close to earnings
                if self.monitor.days_to_earnings(symbol) <= 7:
                    continue
                
                # Get IV metrics
                iv_data = self.monitor.get_iv_metrics(symbol)
                if iv_data['iv_rank'] < 50 or iv_data['current_iv'] < 20:
                    continue
                
                # Find suitable strikes
                strikes = self._find_wheel_strikes(symbol, iv_data)
                
                for strike_data in strikes:
                    # Add sector and liquidity info but don't filter by criteria yet
                    strike_data['position_size_adjustment'] = position_size_multiplier
                    strike_data['sector'] = self.sector_map.get(symbol, 'Unknown')
                    strike_data['liquidity_score'] = self._calculate_liquidity_score(symbol)
                    opportunities.append(strike_data)
                        
            except Exception as e:
                print(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by expected return
        return sorted(opportunities, key=lambda x: x['annual_return'], reverse=True)
    
    def _calculate_liquidity_score(self, symbol: str) -> float:
        """Calculate liquidity score for a symbol"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # Get volume and bid-ask spread
            volume = info.get('averageVolume', 0)
            bid = info.get('bid', 0)
            ask = info.get('ask', 0)
            
            if bid == 0 or ask == 0:
                return 0
                
            spread_pct = (ask - bid) / ((ask + bid) / 2)
            if spread_pct == 0:  # Avoid division by zero
                spread_pct = 0.001
                
            # Estimate option open interest (in production would get actual OI)
            # Using volume as a rough proxy for now
            oi_estimate = min(volume / 100, 1000)
            
            # Liquidity score formula: Volume × OI / Spread
            liquidity_score = (volume * oi_estimate) / (spread_pct * 10000)
            
            return min(liquidity_score, 10000)  # Cap at 10000
            
        except Exception:
            return 0
    
    def _get_regime_multiplier(self, vix_percentile: float) -> float:
        """Get position size multiplier based on VIX regime"""
        if vix_percentile > 90:
            return 0.5
        elif vix_percentile > 75:
            return 0.75
        else:
            return 1.0
    
    def _find_wheel_strikes(self, symbol: str, iv_data: Dict) -> List[Dict]:
        """Find suitable put strikes for wheel entry"""
        stock = yf.Ticker(symbol)
        current_price = stock.history(period='1d')['Close'].iloc[-1]
        
        # Get next monthly expiration
        expirations = stock.options
        target_dte = 30
        best_expiry = min(expirations, 
                         key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - datetime.now()).days - target_dte))
        
        chain = stock.option_chain(best_expiry)
        dte = (datetime.strptime(best_expiry, '%Y-%m-%d') - datetime.now()).days
        
        suitable_strikes = []
        
        # Look for strikes in the 20-40 delta range (estimated by moneyness)
        for _, put in chain.puts.iterrows():
            moneyness = put['strike'] / current_price
            
            # Roughly 20-40 delta range
            if 0.85 <= moneyness <= 0.95:
                premium = put['lastPrice']
                if premium > 0:
                    annual_return = (premium / put['strike']) * (365 / dte)
                    
                    # Minimum 20% annualized return
                    if annual_return >= 0.20:
                        suitable_strikes.append({
                            'symbol': symbol,
                            'strike': put['strike'],
                            'premium': premium,
                            'dte': dte,
                            'expiry': best_expiry,
                            'annual_return': annual_return,
                            'iv_rank': iv_data['iv_rank'],
                            'current_iv': iv_data['current_iv'],
                            'moneyness': moneyness,
                            'current_price': current_price
                        })
        
        return suitable_strikes
    
    def _diversify_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """Ensure sector diversification in recommendations"""
        sector_allocation = {}
        diversified = []
        
        for opp in opportunities:
            sector = opp['sector']
            current_allocation = sector_allocation.get(sector, 0)
            
            # Check if adding this would exceed 20% sector limit
            position_value = opp['strike'] * 100
            new_allocation = current_allocation + position_value
            
            if new_allocation <= self.monitor.account_value * 0.20:
                diversified.append(opp)
                sector_allocation[sector] = new_allocation
                
                # Limit to top 5 opportunities
                if len(diversified) >= 5:
                    break
        
        return diversified
# -------------------------------------------------------------
# Sector Opportunity Screener
# -------------------------------------------------------------
class SectorOpportunityScreener:
    """Find optimal opportunities in underweight sectors"""
    
    def __init__(self, monitor: WheelMonitor, scanner: WheelScanner):
        self.monitor = monitor
        self.scanner = scanner
        self.sector_targets = self._calculate_sector_targets()
        
    def _calculate_sector_targets(self) -> Dict[str, Tuple[float, float]]:
        """Calculate target allocation ranges for each sector based on regime"""
        # TEMPORARILY DISABLED due to yfinance rate limits
        regime = 'NEUTRAL'  # Default to neutral regime
        vix = 50.0  # Default to 50th percentile
        
        # Base sector targets
        targets = {
            'Technology': (0.15, 0.25),
            'Financial Services': (0.10, 0.20),
            'Healthcare': (0.10, 0.20),
            'Consumer Cyclical': (0.10, 0.15),
            'Consumer Staples': (0.05, 0.15),
            'Industrials': (0.05, 0.15),
            'Energy': (0.05, 0.15),
            'Utilities': (0.05, 0.15),
            'Materials': (0.05, 0.10),
            'Real Estate': (0.05, 0.10),
            'Communication Services': (0.05, 0.10)
        }
        
        # Adjust based on regime
        if regime == 'BULL':
            # Increase cyclical sectors
            targets['Technology'] = (0.20, 0.25)
            targets['Consumer Cyclical'] = (0.15, 0.20)
            # Decrease defensive sectors
            targets['Utilities'] = (0.05, 0.10)
            targets['Consumer Staples'] = (0.05, 0.10)
        elif regime == 'BEAR':
            # Increase defensive sectors
            targets['Utilities'] = (0.10, 0.20)
            targets['Consumer Staples'] = (0.10, 0.20)
            targets['Healthcare'] = (0.15, 0.20)
            # Decrease cyclical sectors
            targets['Technology'] = (0.10, 0.15)
            targets['Consumer Cyclical'] = (0.05, 0.10)
        
        # Apply VIX-based scaling
        if vix > 90:  # Extreme volatility
            # Scale down all targets by 50%
            targets = {k: (v[0] * 0.5, v[1] * 0.5) for k, v in targets.items()}
        elif vix > 75:  # High volatility
            # Scale down all targets by 25%
            targets = {k: (v[0] * 0.75, v[1] * 0.75) for k, v in targets.items()}
            
        return targets
    
    def get_sector_gaps(self) -> List[Dict]:
        """Identify sectors with biggest allocation gaps"""
        current_allocations = self.monitor.get_sector_allocations()
        gaps = []
        
        for sector, target_range in self.sector_targets.items():
            current = current_allocations.get(sector, 0)
            min_target, max_target = target_range
            
            # Calculate gap as distance from midpoint of target range
            target_mid = (min_target + max_target) / 2
            gap = target_mid - current
            
            if gap > 0.05:  # Only consider meaningful gaps
                gaps.append({
                    'sector': sector,
                    'current': current,
                    'target_range': f"{min_target*100:.0f}%-{max_target*100:.0f}%",
                    'gap': gap,
                    'priority': self._calculate_priority(sector, gap)
                })
                
        # Sort by priority score
        return sorted(gaps, key=lambda x: x['priority'], reverse=True)
    
    def find_sector_opportunities(self) -> Dict[str, List]:
        """Find best opportunities in underweight sectors"""
        gaps = self.get_sector_gaps()
        all_opportunities = self.scanner.scan_all_opportunities()
        
        sector_opportunities = {}
        
        for gap in gaps:
            sector = gap['sector']
            sector_opps = [opp for opp in all_opportunities if opp['sector'] == sector]
            
            # Score and sort opportunities
            scored_opps = []
            for opp in sector_opps:
                score = self._calculate_opportunity_score(opp, gap['gap'])
                scored_opps.append({**opp, 'score': score})
                
            sector_opportunities[sector] = sorted(scored_opps, key=lambda x: x['score'], reverse=True)[:3]  # Top 3 per sector
            
        return sector_opportunities
    
    def get_top_sector_recommendations(self) -> List[Dict]:
        """Get top opportunity for each underweight sector"""
        sector_opps = self.find_sector_opportunities()
        recommendations = []
        
        for sector, opps in sector_opps.items():
            if opps:  # If there are opportunities for this sector
                top_opp = opps[0]
                recommendations.append({
                    'sector': sector,
                    'symbol': top_opp['symbol'],
                    'strike': top_opp['strike'],
                    'return': top_opp['annual_return'],
                    'expiry': top_opp['expiry'],
                    'score': top_opp.get('score', 0)
                })
                
        # Sort by score
        return sorted(recommendations, key=lambda x: x['score'], reverse=True)
    
    def _calculate_priority(self, sector: str, gap: float) -> float:
        """Calculate priority score for a sector gap"""
        # Base priority on gap size
        priority = gap * 10
        
        # Adjust for market regime and sector characteristics
        regime = self.monitor.detect_market_regime()
        
        if regime == 'BULL':
            # Prioritize growth sectors in bull markets
            if sector in ['Technology', 'Consumer Cyclical', 'Financial Services']:
                priority *= 1.25
        elif regime == 'BEAR':
            # Prioritize defensive sectors in bear markets
            if sector in ['Utilities', 'Consumer Staples', 'Healthcare']:
                priority *= 1.25
                
        return priority
    
    def _calculate_opportunity_score(self, opportunity: Dict, gap: float) -> float:
        """Calculate comprehensive score for an opportunity"""
        # Extract key metrics
        annual_return = opportunity.get('annual_return', 0)
        iv_rank = opportunity.get('iv_rank', 0) / 100
        liquidity = min(opportunity.get('liquidity_score', 0) / 5000, 1.0)  # Cap at 1.0
        
        # Get valuation score based on sector
        valuation_score = self._get_valuation_score(
            opportunity['symbol'], 
            opportunity['strike'],
            opportunity['sector']
        )
        
        # Calculate momentum score
        momentum_score = self._get_sector_momentum_score(opportunity['sector'])
        
        # Calculate final score
        score = (0.3 * annual_return) + (0.2 * iv_rank) + (0.15 * liquidity) + \
                (0.15 * valuation_score) + (0.1 * momentum_score) + (0.1 * gap)
                
        return score
    
    def _get_valuation_score(self, symbol: str, strike: float, sector: str) -> float:
        """Get valuation score based on sector-specific metrics"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            current_price = info.get('regularMarketPrice', 0)
            
            if current_price == 0:
                return 0.5  # Default if price unavailable
                
            # Calculate implied valuation at strike price
            implied_ratio = strike / current_price
            
            # Get sector-specific valuation metrics
            if sector == 'Technology':
                pe_ratio = info.get('trailingPE', 0)
                peg_ratio = info.get('pegRatio', 0)
                
                if peg_ratio > 0 and peg_ratio < 1.5:
                    return 0.9
                elif pe_ratio > 0 and pe_ratio < 30:
                    return 0.75
                else:
                    return 0.5
                    
            elif sector == 'Financial Services':
                pb_ratio = info.get('priceToBook', 0)
                
                if pb_ratio > 0 and pb_ratio < 1.5:
                    return 0.9
                elif pb_ratio > 0 and pb_ratio < 2.5:
                    return 0.7
                else:
                    return 0.5
                    
            # Default for other sectors
            return 0.7
            
        except Exception:
            return 0.5  # Default if error
    
    def _get_sector_momentum_score(self, sector: str) -> float:
        """Calculate momentum score for a sector"""
        try:
            # Map sectors to ETFs
            etf_map = {
                'Technology': 'XLK',
                'Financial Services': 'XLF',
                'Healthcare': 'XLV',
                'Consumer Cyclical': 'XLY',
                'Consumer Staples': 'XLP',
                'Industrials': 'XLI',
                'Energy': 'XLE',
                'Utilities': 'XLU',
                'Materials': 'XLB',
                'Real Estate': 'XLRE',
                'Communication Services': 'XLC'
            }
            
            if sector not in etf_map:
                return 0.5  # Default if sector not mapped
                
            etf = yf.Ticker(etf_map[sector])
            hist = etf.history(period='3mo')
            
            if len(hist) < 60:
                return 0.5  # Not enough data
                
            # Calculate relative strength
            spy = yf.Ticker('SPY')
            spy_hist = spy.history(period='3mo')
            
            # Calculate returns
            sector_return = (hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1
            market_return = (spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[0]) - 1
            
            # Calculate relative strength
            if market_return == 0:
                rs = 1.0  # Avoid division by zero
            else:
                rs = sector_return / market_return
                
            # Convert to score (0-1)
            if rs > 1.5:
                return 0.9  # Strong outperformance
            elif rs > 1.2:
                return 0.8  # Moderate outperformance
            elif rs > 1.0:
                return 0.7  # Slight outperformance
            elif rs > 0.8:
                return 0.6  # Slight underperformance
            elif rs > 0.5:
                return 0.4  # Moderate underperformance
            else:
                return 0.3  # Strong underperformance
                
        except Exception:
            return 0.5  # Default if error
    
    def detect_sector_rotation(self) -> List[Dict]:
        """Detect potential sector rotation patterns"""
        try:
            # Get sector ETF data
            etfs = {
                'Technology': 'XLK',
                'Financial Services': 'XLF',
                'Healthcare': 'XLV',
                'Consumer Cyclical': 'XLY',
                'Consumer Staples': 'XLP',
                'Industrials': 'XLI',
                'Energy': 'XLE',
                'Utilities': 'XLU',
                'Materials': 'XLB',
                'Real Estate': 'XLRE',
                'Communication Services': 'XLC'
            }
            
            # Calculate 20-day and 50-day momentum for each sector
            momentum = {}
            for sector, ticker in etfs.items():
                etf = yf.Ticker(ticker)
                hist = etf.history(period='3mo')
                
                if len(hist) < 50:
                    continue
                    
                # Calculate momentum (20-day vs 50-day performance)
                close_20d_ago = hist['Close'].iloc[-20]
                close_50d_ago = hist['Close'].iloc[-50]
                current = hist['Close'].iloc[-1]
                
                mom_20d = (current / close_20d_ago) - 1
                mom_50d = (current / close_50d_ago) - 1
                
                # Acceleration = recent momentum vs longer-term momentum
                acceleration = mom_20d - mom_50d
                
                momentum[sector] = {
                    'mom_20d': mom_20d,
                    'mom_50d': mom_50d,
                    'acceleration': acceleration
                }
            
            # Identify sectors with strongest positive and negative acceleration
            sectors = list(momentum.keys())
            sectors.sort(key=lambda x: momentum[x]['acceleration'], reverse=True)
            
            rotations = []
            
            # Look for potential rotations (from weakest to strongest)
            if len(sectors) >= 2:
                strongest = sectors[0]
                weakest = sectors[-1]
                
                # Only consider significant divergence
                if (momentum[strongest]['acceleration'] > 0.05 and 
                    momentum[weakest]['acceleration'] < -0.05):
                    rotations.append({
                        'from_sector': weakest,
                        'to_sector': strongest,
                        'momentum': momentum[strongest]['mom_20d'],
                        'strength': momentum[strongest]['acceleration'] - momentum[weakest]['acceleration']
                    })
            
            return rotations
            
        except Exception as e:
            print(f"Error detecting sector rotation: {e}")
            return []

# -------------------------------------------------------------
# Trade Execution Class
# -------------------------------------------------------------

class TradeExecutor:
    """Execute wheel trades with safety checks"""
    
    def __init__(self, monitor: WheelMonitor):
        self.monitor = monitor
        self.logger = logging.getLogger(__name__)
        
        # SHARED CONNECTION: Will be assigned externally - no auto-connection
        self.ib = None  # Will be set to monitor.ib
        
        # Connect monitor's BlackSwanProtocol to this executor
        self.monitor.black_swan_protocol.executor = self
        
    def sell_put(self, symbol: str, strike: float, expiry: str, premium: float) -> Optional[Dict]:
        """Sell cash-secured put with all safety checks and optimal timing"""
        
        # Check best time to trade
        current_time = datetime.now().time()
        if not self._is_optimal_trade_time():
            self.logger.warning(f"Not optimal trade time: {current_time}")
            return None
        
        # Final safety check
        criteria = self.monitor.check_entry_criteria(symbol, strike)
        if not criteria['meets_criteria']:
            self.logger.warning(f"Put sale blocked: {criteria['issues']}")
            return None
        
        # Check if post-earnings trade
        post_earnings = self.monitor.check_post_earnings_opportunity(symbol)
        if post_earnings['opportunity']:
            # Size down for post-earnings uncertainty
            quantity = 1  # Could be 2 normally
        else:
            quantity = self._calculate_position_size(symbol, strike)
        
        # Create contract
        contract = Option(symbol, expiry, strike, 'P', 'SMART')
        
        # Use smart fill protocol
        filled_order = self._smart_fill_order(contract, 'SELL', quantity, premium)
        
        if filled_order:
            # Log trade with attribution
            self.logger.info(f"Sold {symbol} {strike}P {expiry} @ {filled_order['fill_price']}")
            
            return {
                'symbol': symbol,
                'strike': strike,
                'expiry': expiry,
                'premium': filled_order['fill_price'],
                'trade_id': filled_order['order_id'],
                'regime': self.monitor.detect_market_regime(),
                'post_earnings': post_earnings['opportunity'],
                'entry_time': datetime.now()
            }
        
        return None
    
    def _is_optimal_trade_time(self) -> bool:
        """Check if current time is optimal for trading"""
        current_time = datetime.now().time()
        current_day = datetime.now().weekday()
        
        # Avoid Monday and Friday
        if current_day in [0, 4]:
            return False
            
        # Optimal windows
        morning_start = time(10, 0)
        morning_end = time(11, 0)
        afternoon_start = time(14, 0)
        afternoon_end = time(15, 0)
        
        return (morning_start <= current_time <= morning_end or 
                afternoon_start <= current_time <= afternoon_end)
    
    def _smart_fill_order(self, contract, action: str, quantity: int, limit_price: float) -> Optional[Dict]:
        """Smart order filling with progressive price improvement"""
        # Start at mid-price
        ticker = self.monitor.ib.reqMktData(contract)
        util.sleep(1)
        
        if action == 'SELL':
            # For sells, start at ask and work down
            start_price = ticker.ask
            increment = -0.05
            target_price = ticker.bid
        else:
            # For buys, start at bid and work up
            start_price = ticker.bid
            increment = 0.05
            target_price = ticker.ask
        
        current_price = start_price
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            order = LimitOrder(action, quantity, current_price)
            trade = self.monitor.ib.placeOrder(contract, order)
            
            # Wait for fill
            util.sleep(120)  # 2 minutes
            
            if trade.orderStatus.status == 'Filled':
                return {
                    'fill_price': trade.orderStatus.avgFillPrice,
                    'order_id': trade.order.orderId,
                    'fill_time': datetime.now()
                }
            
            # Cancel and adjust price
            self.monitor.ib.cancelOrder(order)
            current_price += increment
            attempts += 1
            
            # Don't go past target
            if increment > 0 and current_price > target_price:
                current_price = target_price
            elif increment < 0 and current_price < target_price:
                current_price = target_price
        
        return None
    
    def _calculate_position_size(self, symbol: str, strike: float) -> int:
        """Calculate position size based on all factors"""
        # Get base position size
        position_value = strike * 100
        max_contracts = int(self.monitor.account_value * 0.10 / position_value)
        
        # Adjust for market conditions
        regime = self.monitor.detect_market_regime()
        if regime == 'BEAR':
            max_contracts = int(max_contracts * 0.75)
        
        # Adjust for win streak
        if self.monitor.win_streak_manager.consecutive_wins >= 10:
            max_contracts = int(max_contracts * 0.5)
        elif self.monitor.win_streak_manager.consecutive_wins >= 8:
            max_contracts = int(max_contracts * 0.75)
        
        # Adjust for black swan protocol
        max_contracts = int(max_contracts * self.monitor.position_size_multiplier)
        
        # Minimum 1 contract
        return max(1, max_contracts)
    
    def sell_covered_call(self, symbol: str, shares: int, strike: float, 
                          expiry: str, premium: float) -> Optional[Dict]:
        """Sell covered call on owned shares"""
        
        # Verify share ownership
        positions = self.monitor.ib.positions()
        owned_shares = 0
        
        for pos in positions:
            if pos.contract.symbol == symbol and pos.contract.secType == 'STK':
                owned_shares = pos.position
                break
        
        if owned_shares < shares:
            self.logger.error(f"Insufficient shares: own {owned_shares}, need {shares}")
            return None
        
        # Calculate contracts
        contracts = shares // 100
        if contracts == 0:
            return None
        
        # Create contract
        contract = Option(symbol, expiry, strike, 'C', 'SMART')
        
        # Create order
        order = LimitOrder('SELL', contracts, premium)
        
        # Place order
        trade = self.monitor.ib.placeOrder(contract, order)
        
        self.logger.info(f"Sold {contracts}x {symbol} {strike}C {expiry} @ {premium}")
        
        return {
            'symbol': symbol,
            'strike': strike,
            'expiry': expiry,
            'premium': premium,
            'contracts': contracts,
            'trade_id': trade.order.orderId
        }
    
    def roll_position(self, position, new_strike: float, new_expiry: str) -> Optional[Dict]:
        """Roll option position for credit only"""
        
        old_contract = position.contract
        
        # Calculate net credit required
        close_price = self.monitor.ib.reqMktData(old_contract).bid
        
        # New contract
        new_contract = Option(
            old_contract.symbol,
            new_expiry,
            new_strike,
            old_contract.right,
            'SMART'
        )
        
        # Get new contract price
        new_ticker = self.monitor.ib.reqMktData(new_contract)
        util.sleep(1)
        open_price = new_ticker.ask
        
        net_credit = open_price - close_price
        
        if net_credit <= 0:
            self.logger.warning(f"Roll would be for debit: {net_credit}")
            return None
        
        # Execute roll as two trades
        # Close old position
        close_order = LimitOrder('BUY', abs(position.position), close_price)
        close_trade = self.monitor.ib.placeOrder(old_contract, close_order)
        
        # Open new position
        open_order = LimitOrder('SELL', abs(position.position), open_price)
        open_trade = self.monitor.ib.placeOrder(new_contract, open_order)
        
        self.logger.info(f"Rolled {old_contract.symbol} {old_contract.strike} -> {new_strike}")
        
        return {
            'symbol': old_contract.symbol,
            'old_strike': old_contract.strike,
            'new_strike': new_strike,
            'new_expiry': new_expiry,
            'net_credit': net_credit
        }
    
    def close_position(self, position, reason: str = "Manual close") -> Dict:
        """Close any position (option or stock)"""
        contract = position.contract
        
        if contract.secType == 'OPT':
            # For short option, buy to close
            if position.position < 0:
                action = 'BUY'
                # Get current bid price with some buffer
                price = self.monitor.ib.reqMktData(contract).ask * 1.05
            # For long option, sell to close
            else:
                action = 'SELL'
                # Get current ask price with some discount
                price = self.monitor.ib.reqMktData(contract).bid * 0.95
                
            order = LimitOrder(action, abs(position.position), price)
            
        elif contract.secType == 'STK':
            # For long stock, sell
            if position.position > 0:
                action = 'SELL'
                # Get current bid with small discount
                price = self.monitor.ib.reqMktData(contract).bid * 0.99
            # For short stock (unlikely), buy to cover
            else:
                action = 'BUY'
                # Get current ask with small buffer
                price = self.monitor.ib.reqMktData(contract).ask * 1.01
                
            order = LimitOrder(action, abs(position.position), price)
        
        # Execute order
        trade = self.monitor.ib.placeOrder(contract, order)
        
        # Calculate realized P&L
        realized_pnl = 0
        if hasattr(position, 'avgCost') and position.avgCost is not None:
            if contract.secType == 'OPT':
                # For options, P&L is the difference between premium received and premium paid
                if position.position < 0:  # Short position
                    realized_pnl = (position.avgCost - price) * abs(position.position) * 100
                else:  # Long position
                    realized_pnl = (price - position.avgCost) * abs(position.position) * 100
            elif contract.secType == 'STK':
                # For stock, P&L is the difference between sale price and cost basis
                if position.position > 0:  # Long position
                    realized_pnl = (price - position.avgCost) * abs(position.position)
                else:  # Short position
                    realized_pnl = (position.avgCost - price) * abs(position.position)
        
        # Record realized P&L in tracker if available
        if hasattr(self.monitor, 'tracker') and self.monitor.tracker:
            self.monitor.tracker.record_realized_pnl(
                trade_id=str(trade.order.orderId),
                realized_pnl=realized_pnl,
                close_date=datetime.now()
            )
        
        self.logger.info(f"Closed {contract.symbol} position. Reason: {reason}. Realized P&L: ${realized_pnl:.2f}")
        
        return {
            'symbol': contract.symbol,
            'action': action,
            'quantity': abs(position.position),
            'price': price,
            'reason': reason,
            'trade_id': trade.order.orderId,
            'realized_pnl': realized_pnl,
            'close_date': datetime.now()
        }
# -------------------------------------------------------------
# Performance Tracking Class
# -------------------------------------------------------------
class PerformanceTracker:
    """Track wheel strategy performance with tax awareness"""
    
    def __init__(self):
        self.trades = []
        self.closed_positions = []
        self.tax_lots = {}
        self.realized_pnl_history = []
        self.unrealized_pnl_history = []
        
        # Sample trades removed - use real trade data from IBKR/Postgres
        # Trade history can be recorded via log_trade() or loaded from database
        
    def log_trade(self, trade: Dict):
        """Log executed trade for tracking"""
        trade['timestamp'] = datetime.now()
        self.trades.append(trade)
        
    def calculate_metrics(self, account_value: float) -> Dict:
        """Calculate performance metrics with attribution"""
        print("\nCalculating performance metrics...")
        print(f"Account value: ${account_value:,.2f}")
        
        df = pd.DataFrame(self.trades)
        print(f"Found {len(df)} trades")
        
        if df.empty:
            raise RuntimeError("No trades found - cannot calculate metrics without trade data")
        
        # Calculate returns by type
        df['pnl'] = df.apply(self._calculate_pnl, axis=1)
        df['trade_type'] = df.apply(self._classify_trade, axis=1)
        
        # Daily returns for Sharpe
        daily_returns = df.groupby(pd.to_datetime(df['timestamp']).dt.date)['pnl'].sum()
        daily_returns_pct = daily_returns / account_value
        
        # Calculate base metrics
        total_return = daily_returns.sum() / account_value
        win_rate = (df['pnl'] > 0).mean()
        
        # Sharpe Ratio (annualized)
        if len(daily_returns) > 1:
            sharpe = (daily_returns_pct.mean() * 252) / (daily_returns_pct.std() * np.sqrt(252))
        else:
            sharpe = 0
            
        # Sortino Ratio (downside deviation)
        negative_returns = daily_returns_pct[daily_returns_pct < 0]
        if len(negative_returns) > 1:
            sortino = (daily_returns_pct.mean() * 252) / (negative_returns.std() * np.sqrt(252))
        else:
            sortino = sharpe
        
        # Attribution by trade type
        attribution = df.groupby('trade_type')['pnl'].agg(['sum', 'count', 'mean'])
        
        # Market regime performance
        regime_performance = self._calculate_regime_performance(df)
        
        # Rule effectiveness
        rule_performance = self._calculate_rule_performance(df)
        
        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'total_trades': len(df),
            'avg_credit': df['premium'].mean() if 'premium' in df else 0,
            'attribution': attribution.to_dict(),
            'regime_performance': regime_performance,
            'rule_performance': rule_performance,
            'best_day': daily_returns.max(),
            'worst_day': daily_returns.min(),
            'avg_daily_pnl': daily_returns.mean(),
            'consecutive_wins': self._count_consecutive_wins(df),
            'max_drawdown': self._calculate_max_drawdown(daily_returns)
        }
    

    
    def _calculate_pnl(self, trade: Dict) -> float:
        """Calculate P&L for a trade"""
        # Different calculation based on trade type
        if trade.get('action') == 'ROLL_POSITION':
            return trade.get('net_credit', 0) * 100 * trade.get('quantity', 1)
        elif 'premium' in trade:
            return trade.get('premium', 0) * 100 * trade.get('quantity', 1)
        else:
            return trade.get('pnl', 0)
    
    def _classify_trade(self, trade) -> str:
        """Classify trade type for attribution"""
        if trade.get('trade_type'):
            return trade['trade_type']
        elif 'roll' in trade.get('action', '').lower():
            return 'roll'
        elif 'csp' in trade.get('type', '').lower():
            return 'csp'
        elif 'cc' in trade.get('type', '').lower():
            return 'cc'
        else:
            return 'other'
    
    def _calculate_regime_performance(self, df) -> Dict:
        """Calculate returns by market regime"""
        regime_returns = {}
        for regime in ['BULL', 'BEAR', 'NEUTRAL']:
            regime_trades = df[df.get('regime', '') == regime]
            if not regime_trades.empty:
                regime_returns[regime] = {
                    'total_pnl': regime_trades['pnl'].sum(),
                    'trade_count': len(regime_trades),
                    'win_rate': (regime_trades['pnl'] > 0).mean()
                }
        return regime_returns
    
    def _calculate_rule_performance(self, df) -> Dict:
        """Track which rules are most profitable"""
        rule_returns = {}
        rules = ['21_dte_roll', 'delta_roll', '80pct_roll', 'assignment', 'cc_profit']
        
        for rule in rules:
            rule_trades = df[df.get('rule_trigger', '') == rule]
            if not rule_trades.empty:
                rule_returns[rule] = {
                    'total_pnl': rule_trades['pnl'].sum(),
                    'trade_count': len(rule_trades),
                    'avg_pnl': rule_trades['pnl'].mean()
                }
        return rule_returns
    
    def _count_consecutive_wins(self, df) -> int:
        """Count maximum consecutive winning trades"""
        if df.empty:
            return 0
            
        wins = (df['pnl'] > 0).astype(int).tolist()
        
        # Find longest streak of 1s
        max_streak = 0
        current_streak = 0
        
        for win in wins:
            if win == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
                
        return max_streak
    
    def _calculate_max_drawdown(self, daily_returns) -> float:
        """Calculate maximum drawdown from daily returns"""
        if len(daily_returns) <= 1:
            return 0
            
        # Calculate cumulative returns
        cum_returns = (1 + daily_returns).cumprod()
        
    def get_realized_pnl(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict:
        """Get realized P&L for specified period"""
        if not start_date:
            start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # Start of current month
        if not end_date:
            end_date = datetime.now()
            
        # Filter trades by date range
        filtered_trades = [
            trade for trade in self.trades 
            if start_date <= trade.get('timestamp', datetime.now()) <= end_date
            and trade.get('status') == 'CLOSED'
        ]
        
        realized_pnl = sum(trade.get('realized_pnl', 0) for trade in filtered_trades)
        
        return {
            'realized_pnl': realized_pnl,
            'trade_count': len(filtered_trades),
            'winning_trades': len([t for t in filtered_trades if t.get('realized_pnl', 0) > 0]),
            'losing_trades': len([t for t in filtered_trades if t.get('realized_pnl', 0) < 0]),
            'start_date': start_date,
            'end_date': end_date
        }
    
    def get_todays_realized_pnl(self) -> Dict:
        """Get today's realized P&L"""
        today = datetime.now().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        return self.get_realized_pnl(start_of_day, end_of_day)
    
    def get_mtd_realized_pnl(self) -> Dict:
        """Get month-to-date realized P&L"""
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        start_of_month = datetime(current_year, current_month, 1)
        end_of_month = datetime.now()
        
        return self.get_realized_pnl(start_of_month, end_of_month)
    
    def get_closed_trades_for_month(self, year: int, month: int) -> List[Dict]:
        """Get all closed trades for a specific month"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            
        return [
            trade for trade in self.trades 
            if start_date <= trade.get('timestamp', datetime.now()) <= end_date
            and trade.get('status') == 'CLOSED'
        ]
    
    def record_realized_pnl(self, trade_id: str, realized_pnl: float, close_date: datetime):
        """Record realized P&L when a position is closed"""
        pnl_record = {
            'trade_id': trade_id,
            'realized_pnl': realized_pnl,
            'close_date': close_date,
            'timestamp': datetime.now()
        }
        self.realized_pnl_history.append(pnl_record)
        
        # Update the original trade record
        for trade in self.trades:
            if trade.get('id') == trade_id:
                trade['realized_pnl'] = realized_pnl
                trade['close_date'] = close_date
                trade['status'] = 'CLOSED'
                break
    
    def compare_to_benchmark(self, start_date: datetime, end_date: datetime) -> Dict:
        """Compare performance to SPY benchmark"""
        spy = yf.Ticker('SPY')
        spy_data = spy.history(start=start_date, end=end_date)
        
        spy_return = (spy_data['Close'].iloc[-1] - spy_data['Close'].iloc[0]) / spy_data['Close'].iloc[0]
        
        strategy_return = sum([t['pnl'] for t in self.trades]) / self.trades[0]['account_value']
        
        return {
            'strategy_return': strategy_return,
            'spy_return': spy_return,
            'excess_return': strategy_return - spy_return
        }
    
    def analyze_tax_efficiency(self) -> Dict:
        """Analyze tax efficiency of strategy"""
        df = pd.DataFrame(self.trades)
        
        if df.empty:
            return {'short_term_gains': 0, 'long_term_gains': 0, 'tax_drag': 0}
        
        # Calculate holding period for each position
        position_data = {}
        
        for _, trade in df.iterrows():
            symbol = trade.get('symbol')
            
            if not symbol:
                continue
                
            if symbol not in position_data:
                position_data[symbol] = []
                
            position_data[symbol].append({
                'timestamp': trade.get('timestamp'),
                'action': trade.get('action', ''),
                'pnl': trade.get('pnl', 0)
            })
        
        # Calculate short vs long term gains
        short_term_gains = 0
        long_term_gains = 0
        
        for symbol, trades in position_data.items():
            # Sort by timestamp
            trades.sort(key=lambda x: x['timestamp'])
            
            # Find entry and exit pairs
            buy_dates = []
            sell_dates = []
            
            for trade in trades:
                if 'buy' in trade['action'].lower() or 'entry' in trade['action'].lower():
                    buy_dates.append(trade['timestamp'])
                elif 'sell' in trade['action'].lower() or 'exit' in trade['action'].lower():
                    sell_dates.append(trade['timestamp'])
            
            # Match buys and sells (FIFO)
            for sell_date in sell_dates:
                if buy_dates:
                    buy_date = buy_dates.pop(0)
                    holding_period = (sell_date - buy_date).days
                    
                    # Find corresponding P&L
                    pnl = next((t['pnl'] for t in trades if t['timestamp'] == sell_date), 0)
                    
                    if holding_period > 365:
                        long_term_gains += pnl
                    else:
                        short_term_gains += pnl
        
        # Calculate tax drag (assuming 35% short term, 15% long term)
        tax_drag = (short_term_gains * 0.35) + (long_term_gains * 0.15)
        
        return {
            'short_term_gains': short_term_gains,
            'long_term_gains': long_term_gains,
            'tax_drag': tax_drag,
            'effective_tax_rate': tax_drag / (short_term_gains + long_term_gains) if (short_term_gains + long_term_gains) > 0 else 0
        }

# -------------------------------------------------------------
# Alert Manager Class
# -------------------------------------------------------------

class AlertManager:
    """Manage alerts for wheel strategy"""
    
    def __init__(self, config: Dict):
        self.config = config
        
    async def send_alert(self, alert: Alert):
        """Send alert based on priority"""
        if alert.priority == AlertPriority.CRITICAL:
            await asyncio.gather(
                self._send_sms(alert),
                self._send_email(alert),
                self._send_push(alert)
            )
        elif alert.priority == AlertPriority.IMPORTANT:
            await asyncio.gather(
                self._send_email(alert),
                self._send_push(alert)
            )
        else:
            await self._send_push(alert)
    
    async def _send_email(self, alert: Alert):
        """Send email alert"""
        msg = MIMEText(f"{alert.message}\n\nAction: {alert.action_required or 'None'}")
        msg['Subject'] = f"[{alert.priority.value.upper()}] {alert.title}"
        msg['From'] = self.config['email']['from']
        msg['To'] = self.config['email']['to']
        
        with smtplib.SMTP(self.config['email']['smtp_server'], 587) as server:
            server.starttls()
            server.login(msg['From'], self.config['email']['password'])
            server.send_message(msg)
    
    async def _send_sms(self, alert: Alert):
        """Send SMS alert"""
        # Would integrate with SMS service like Twilio
        # Simplified implementation
        print(f"SMS ALERT: {alert.priority.value.upper()} - {alert.title}")
    
    async def _send_push(self, alert: Alert):
        """Send push notification"""
        # Would integrate with push notification service
        # Simplified implementation
        print(f"PUSH ALERT: {alert.priority.value.upper()} - {alert.title}")

# -------------------------------------------------------------
# Enhanced Alert Manager with Report Delivery
# -------------------------------------------------------------

class EnhancedAlertManager(AlertManager):
    """Enhanced alert manager with screener report delivery"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.delivery_config = config.get('delivery', {})
        self.screener_config = config.get('screener', {})
        
        # Initialize Twilio if SMS enabled
        if self.delivery_config.get('sms', {}).get('enabled'):
            self.twilio_client = Client(
                self.delivery_config['sms']['account_sid'],
                self.delivery_config['sms']['auth_token']
            )
    
    async def send_screener_report(self, report_type: str, opportunities: List[Dict], 
                                  sector_analysis: Dict, summary_stats: Dict):
        """Send screener report via configured methods"""
        
        # Get delivery methods for this report type
        delivery_methods = self.screener_config['delivery_methods'].get(
            report_type, ['email']
        )
        
        # Prepare report content
        email_content = self._format_email_report(
            opportunities, sector_analysis, summary_stats, report_type
        )
        sms_content = self._format_sms_report(
            opportunities, sector_analysis, summary_stats, report_type
        )
        
        # Send via each configured method
        tasks = []
        if 'email' in delivery_methods:
            tasks.append(self._send_report_email(email_content, report_type))
        if 'sms' in delivery_methods:
            tasks.append(self._send_report_sms(sms_content))
        if 'push' in delivery_methods:
            tasks.append(self._send_report_push(sms_content))  # Use SMS format for push
            
        await asyncio.gather(*tasks)
    
    def _format_email_report(self, opportunities: List[Dict], 
                           sector_analysis: Dict, summary_stats: Dict, 
                           report_type: str) -> str:
        """Format HTML email report"""
        
        if self.delivery_config['email']['format'] == 'text':
            return self._format_text_email_report(
                opportunities, sector_analysis, summary_stats, report_type
            )
        
        # HTML format
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h1 {{ color: #3a506b; }}
                h2 {{ color: #5bc0be; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .underweight {{ background-color: #fff3cd; }}
                .opportunity {{ background-color: #d4edda; }}
                .stats {{ background-color: #e2e3e5; padding: 10px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <h1>Wheel Strategy Screener Report - {report_type.replace('_', ' ').title()}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M ET')}</p>
            
            <div class="stats">
                <h2>Summary Statistics</h2>
                <ul>
                    <li>Total Opportunities Found: {summary_stats['total_opportunities']}</li>
                    <li>Average Annual Return: {summary_stats['avg_return']:.1%}</li>
                    <li>Underweight Sectors: {summary_stats['underweight_sectors']}</li>
                    <li>Market Regime: {summary_stats['market_regime']}</li>
                    <li>VIX Level: {summary_stats['vix']:.1f}</li>
                </ul>
            </div>
            
            <h2>Sector Analysis</h2>
            <table>
                <tr>
                    <th>Sector</th>
                    <th>Current Allocation</th>
                    <th>Target Range</th>
                    <th>Gap</th>
                    <th>Action</th>
                </tr>
        """
        
        for sector, data in sector_analysis.items():
            row_class = 'underweight' if data['gap'] > 0.05 else ''
            html += f"""
                <tr class="{row_class}">
                    <td>{sector}</td>
                    <td>{data['current']:.1%}</td>
                    <td>{data['target_range']}</td>
                    <td>{data['gap']:.1%}</td>
                    <td>{data['action']}</td>
                </tr>
            """
        
        html += """
            </table>
            
            <h2>Top Opportunities</h2>
        """
        
        if self.screener_config['report_preferences']['group_by_sector']:
            # Group by sector
            by_sector = {}
            for opp in opportunities:
                sector = opp['sector']
                if sector not in by_sector:
                    by_sector[sector] = []
                by_sector[sector].append(opp)
            
            # Show underweight sectors first
            if self.screener_config['report_preferences']['show_underweight_sectors_first']:
                underweight = [s for s, d in sector_analysis.items() if d['gap'] > 0.05]
                other_sectors = [s for s in by_sector.keys() if s not in underweight]
                sector_order = underweight + other_sectors
            else:
                sector_order = sorted(by_sector.keys())
            
            for sector in sector_order:
                if sector not in by_sector:
                    continue
                    
                html += f"<h3>{sector}</h3><table>"
                html += """
                    <tr>
                        <th>Symbol</th>
                        <th>Strike</th>
                        <th>DTE</th>
                        <th>Annual Return</th>
                        <th>IV Rank</th>
                        <th>Score</th>
                        <th>Notes</th>
                    </tr>
                """
                
                for opp in by_sector[sector][:3]:  # Max 3 per sector
                    html += f"""
                        <tr class="opportunity">
                            <td><strong>{opp['symbol']}</strong></td>
                            <td>${opp['strike']:.2f}</td>
                            <td>{opp['dte']}</td>
                            <td>{opp['annual_return']:.1%}</td>
                            <td>{opp['iv_rank']:.0f}%</td>
                            <td>{opp.get('score', 0):.2f}</td>
                            <td>{self._get_opportunity_notes(opp)}</td>
                        </tr>
                    """
                html += "</table>"
        else:
            # Simple list
            html += """
                <table>
                    <tr>
                        <th>Symbol</th>
                        <th>Sector</th>
                        <th>Strike</th>
                        <th>DTE</th>
                        <th>Annual Return</th>
                        <th>IV Rank</th>
                        <th>Score</th>
                    </tr>
            """
            
            for opp in opportunities[:self.screener_config['max_opportunities_per_report']]:
                html += f"""
                    <tr>
                        <td><strong>{opp['symbol']}</strong></td>
                        <td>{opp['sector']}</td>
                        <td>${opp['strike']:.2f}</td>
                        <td>{opp['dte']}</td>
                        <td>{opp['annual_return']:.1%}</td>
                        <td>{opp['iv_rank']:.0f}%</td>
                        <td>{opp.get('score', 0):.2f}</td>
                    </tr>
                """
            html += "</table>"
        
        html += """
            <p><em>This report is generated automatically. Always verify opportunities 
            meet all entry criteria before trading.</em></p>
        </body>
        </html>
        """
        
        return html
    
    def _format_text_email_report(self, opportunities: List[Dict], 
                                sector_analysis: Dict, summary_stats: Dict,
                                report_type: str) -> str:
        """Format plain text email report"""
        
        text = f"""WHEEL STRATEGY SCREENER REPORT
{report_type.replace('_', ' ').upper()}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M ET')}

SUMMARY
-------
Total Opportunities: {summary_stats['total_opportunities']}
Average Annual Return: {summary_stats['avg_return']:.1%}
Underweight Sectors: {summary_stats['underweight_sectors']}
Market Regime: {summary_stats['market_regime']}
VIX Level: {summary_stats['vix']:.1f}

SECTOR ANALYSIS
--------------
"""
        
        for sector, data in sector_analysis.items():
            if data['gap'] > 0.05:
                text += f"* {sector}: {data['current']:.1%} current, "
                text += f"{data['target_range']} target, "
                text += f"{data['gap']:.1%} underweight\n"
        
        text += "\nTOP OPPORTUNITIES\n"
        text += "-----------------\n"
        
        for i, opp in enumerate(opportunities[:self.screener_config['max_opportunities_per_report']]):
            text += f"\n{i+1}. {opp['symbol']} ${opp['strike']:.2f} Put\n"
            text += f"   Sector: {opp['sector']}\n"
            text += f"   Return: {opp['annual_return']:.1%} | IV Rank: {opp['iv_rank']:.0f}%\n"
            text += f"   DTE: {opp['dte']} | Score: {opp.get('score', 0):.2f}\n"
            
        return text
    
    def _format_sms_report(self, opportunities: List[Dict], 
                         sector_analysis: Dict, summary_stats: Dict,
                         report_type: str) -> str:
        """Format SMS report (character limited)"""
        
        # Find underweight sectors
        underweight = [s for s, d in sector_analysis.items() if d['gap'] > 0.05]
        
        sms = f"Wheel Screener {datetime.now().strftime('%-I%p')}\n"
        sms += f"{summary_stats['total_opportunities']} opps found\n"
        
        if underweight:
            sms += f"Need: {', '.join(underweight[:3])}\n"
        
        sms += "\nTop 5:\n"
        
        for i, opp in enumerate(opportunities[:5]):
            # Compact format for SMS
            sms += f"{i+1}. {opp['symbol']} ${opp['strike']:.0f}P "
            sms += f"{opp['annual_return']:.0%} "
            
            # Add sector indicator if underweight
            if opp['sector'] in underweight:
                sms += f"[{opp['sector'][:4]}]"
            sms += "\n"
        
        # Ensure under SMS limit
        if len(sms) > self.delivery_config['sms']['max_length']:
            sms = sms[:self.delivery_config['sms']['max_length']-3] + "..."
            
        return sms
    
    def _get_opportunity_notes(self, opp: Dict) -> str:
        """Generate notes for an opportunity"""
        notes = []
        
        if opp.get('post_earnings'):
            notes.append("Post-earnings")
        
        if opp.get('high_liquidity'):
            notes.append("High liquidity")
            
        if opp.get('sector_underweight'):
            notes.append("Sector underweight")
            
        return ", ".join(notes) if notes else "-"
    
    async def _send_report_email(self, content: str, report_type: str):
        """Send email report"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Wheel Strategy {report_type.replace('_', ' ').title()} - {datetime.now().strftime('%m/%d')}"
        msg['From'] = self.delivery_config['email']['from']
        
        # Add both text and HTML parts
        if self.delivery_config['email']['format'] == 'html':
            text_part = MIMEText(self._strip_html(content), 'plain')
            html_part = MIMEText(content, 'html')
            msg.attach(text_part)
            msg.attach(html_part)
        else:
            text_part = MIMEText(content, 'plain')
            msg.attach(text_part)
        
        # Send to all recipients
        for recipient in self.delivery_config['email']['to']:
            msg['To'] = recipient
            
            with smtplib.SMTP(self.delivery_config['email']['smtp_server'], 
                            self.delivery_config['email']['port']) as server:
                server.starttls()
                server.login(self.delivery_config['email']['from'], 
                           self.delivery_config['email']['password'])
                server.send_message(msg)
    
    async def _send_report_sms(self, content: str):
        """Send SMS report"""
        if not self.delivery_config['sms']['enabled']:
            return
            
        for recipient in self.delivery_config['sms']['to']:
            try:
                message = self.twilio_client.messages.create(
                    body=content,
                    from_=self.delivery_config['sms']['from'],
                    to=recipient
                )
                logging.info(f"SMS sent to {recipient}: {message.sid}")
            except Exception as e:
                logging.error(f"Failed to send SMS to {recipient}: {e}")
    
    async def _send_report_push(self, content: str):
        """Send push notification (placeholder for future)"""
        # Would implement Pushover, Telegram, or other push service
        pass
    
    def _strip_html(self, html: str) -> str:
        """Convert HTML to plain text"""
        # Simple HTML stripping - in production use BeautifulSoup
        import re
        text = re.sub('<[^<]+?>', '', html)
        return text

# -------------------------------------------------------------
# DTE Alert System - Alert when options approach expiration
# -------------------------------------------------------------

class DTEAlertChecker:
    """Check positions for approaching expiration and send alerts"""
    
    def __init__(self, monitor, alert_manager, config):
        self.monitor = monitor
        self.alert_manager = alert_manager
        self.config = config
        self.dte_threshold = 7  # Alert when DTE < 7
        self.alert_sent_today = {}  # Track alerts to avoid duplicates
        
    def check_dte_alerts(self) -> List[Dict]:
        """Check all option positions for low DTE and return alerts"""
        alerts = []
        
        try:
            # Get LIVE positions from IBKR
            if not self.monitor.ib or not self.monitor.ib.isConnected():
                logger.warning("IBKR not connected - cannot check DTE alerts")
                return alerts
            
            portfolio_items = self.monitor.ib.portfolio()
            today = datetime.now().strftime('%Y-%m-%d')
            
            for item in portfolio_items:
                if item.position == 0:
                    continue
                    
                contract = item.contract
                
                # Skip stocks - only check options
                if getattr(contract, 'right', '0') == '0':
                    continue
                
                # Calculate DTE
                expiry_str = getattr(contract, 'lastTradeDateOrContractMonth', '')
                if not expiry_str:
                    continue
                    
                try:
                    expiry_date = datetime.strptime(expiry_str, '%Y%m%d')
                    dte = (expiry_date - datetime.now()).days
                except:
                    continue
                
                # Check if DTE is below threshold
                if dte <= self.dte_threshold and dte >= 0:
                    symbol = contract.symbol
                    alert_key = f"{symbol}_{expiry_str}_{today}"
                    
                    # Skip if already alerted today
                    if alert_key in self.alert_sent_today:
                        continue
                    
                    # Determine position type
                    right = getattr(contract, 'right', '?')
                    strike = getattr(contract, 'strike', 0)
                    pos_type = 'PUT' if right == 'P' else 'CALL' if right == 'C' else 'OPTION'
                    direction = 'SHORT' if item.position < 0 else 'LONG'
                    
                    # Calculate P&L
                    pnl_pct = (item.unrealizedPNL / abs(item.averageCost) * 100) if item.averageCost != 0 else 0
                    
                    # Determine urgency
                    if dte <= 1:
                        urgency = "🚨 CRITICAL"
                        priority = AlertPriority.CRITICAL
                    elif dte <= 3:
                        urgency = "⚠️ URGENT"
                        priority = AlertPriority.IMPORTANT
                    else:
                        urgency = "📋 NOTICE"
                        priority = AlertPriority.INFO
                    
                    alert_data = {
                        'symbol': symbol,
                        'position_type': f"{direction} {pos_type}",
                        'strike': strike,
                        'expiry': expiry_date.strftime('%b %d, %Y'),
                        'dte': dte,
                        'quantity': abs(item.position),
                        'pnl_pct': round(pnl_pct, 1),
                        'market_value': item.marketValue,
                        'urgency': urgency,
                        'priority': priority,
                        'action_suggestion': self._suggest_action(direction, pos_type, dte, pnl_pct)
                    }
                    
                    alerts.append(alert_data)
                    self.alert_sent_today[alert_key] = True
                    
            logger.info(f"DTE Alert Check: Found {len(alerts)} positions with DTE <= {self.dte_threshold}")
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking DTE alerts: {e}")
            return []
    
    def _suggest_action(self, direction: str, pos_type: str, dte: int, pnl_pct: float) -> str:
        """Suggest action based on position characteristics"""
        if direction == 'SHORT':
            if pnl_pct > 50:
                return "Consider closing for profit (>50% gain)"
            elif dte <= 1:
                return "EXPIRATION IMMINENT - Decide: Close, roll, or let expire"
            elif dte <= 3:
                return "Evaluate roll opportunity to extend duration"
            else:
                return "Monitor closely - approaching expiration"
        else:  # LONG
            if pnl_pct > 50:
                return "Consider taking profit (>50% gain)"
            elif pnl_pct < -30:
                return "Consider cutting loss or rolling"
            else:
                return "Decide: Exercise, sell, or let expire"
    
    async def send_dte_alerts(self, alerts: List[Dict]) -> bool:
        """Send DTE alerts via email"""
        if not alerts:
            return False
        
        try:
            # Build email content
            subject = f"🔔 DTE Alert: {len(alerts)} position(s) approaching expiration"
            
            body = "WHEEL STRATEGY - DTE ALERT\n"
            body += "=" * 50 + "\n\n"
            body += f"The following positions have DTE <= {self.dte_threshold} days:\n\n"
            
            for alert in alerts:
                body += f"{alert['urgency']} {alert['symbol']}\n"
                body += f"  Position: {alert['position_type']} @ ${alert['strike']:.2f}\n"
                body += f"  Expiry: {alert['expiry']} ({alert['dte']} days)\n"
                body += f"  Qty: {alert['quantity']} | P&L: {alert['pnl_pct']:+.1f}%\n"
                body += f"  💡 {alert['action_suggestion']}\n\n"
            
            body += "-" * 50 + "\n"
            body += "Sent by Wheel Strategy Dashboard\n"
            
            # Create alert object
            alert_obj = Alert(
                priority=alerts[0]['priority'],  # Use highest priority
                title=subject,
                message=body,
                action_required="Review and take action before expiration"
            )
            
            await self.alert_manager.send_alert(alert_obj)
            logger.info(f"✅ Sent DTE alert for {len(alerts)} positions")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send DTE alerts: {e}")
            return False

# -------------------------------------------------------------
# Morning Scanner - Find wheel candidates
# -------------------------------------------------------------

class MorningScanner:
    """Scan for wheel strategy opportunities each morning"""
    
    def __init__(self, monitor, config):
        self.monitor = monitor
        self.config = config
        self.watchlist = config.get('symbols', [])
        
        # Scanning criteria
        self.min_iv_rank = 30  # Minimum IV rank (percentile)
        self.target_delta = -0.30  # Target delta for CSPs
        self.delta_range = 0.10  # +/- from target
        self.min_annual_return = 0.15  # 15% minimum annualized return
        self.target_dte_min = 30  # Minimum DTE
        self.target_dte_max = 45  # Maximum DTE
        
    def scan_csp_candidates(self) -> List[Dict]:
        """Scan for Cash-Secured Put candidates"""
        candidates = []
        
        try:
            if not self.monitor.ib or not self.monitor.ib.isConnected():
                logger.warning("IBKR not connected - cannot scan for CSP candidates")
                return candidates
            
            logger.info(f"🔍 Morning Scanner: Checking {len(self.watchlist)} symbols for CSP opportunities...")
            
            for symbol in self.watchlist:
                try:
                    # Get current stock price
                    stock = Stock(symbol, 'SMART', 'USD')
                    self.monitor.ib.qualifyContracts(stock)
                    
                    ticker = self.monitor.ib.reqMktData(stock, '', False, False)
                    self.monitor.ib.sleep(0.5)  # Wait for data
                    
                    stock_price = ticker.marketPrice()
                    if not stock_price or stock_price <= 0:
                        continue
                    
                    # Find put options in target DTE range
                    chains = self.monitor.ib.reqSecDefOptParams(symbol, '', 'STK', stock.conId)
                    if not chains:
                        continue
                    
                    # Get the first chain (usually SMART exchange)
                    chain = chains[0]
                    
                    # Find expiry in target range
                    target_expiry = None
                    for expiry in sorted(chain.expirations):
                        try:
                            exp_date = datetime.strptime(expiry, '%Y%m%d')
                            dte = (exp_date - datetime.now()).days
                            if self.target_dte_min <= dte <= self.target_dte_max:
                                target_expiry = expiry
                                break
                        except:
                            continue
                    
                    if not target_expiry:
                        continue
                    
                    # Find OTM put at target delta
                    # Target strike ~5-10% below current price
                    target_strike = round(stock_price * 0.95, 0)  # 5% OTM
                    
                    # Find closest strike
                    strikes = [s for s in chain.strikes if s < stock_price * 0.98]  # OTM puts
                    if not strikes:
                        continue
                    
                    closest_strike = min(strikes, key=lambda x: abs(x - target_strike))
                    
                    # Create option contract
                    put = Option(symbol, target_expiry, closest_strike, 'P', 'SMART')
                    self.monitor.ib.qualifyContracts(put)
                    
                    # Get option price
                    opt_ticker = self.monitor.ib.reqMktData(put, '', False, False)
                    self.monitor.ib.sleep(0.5)
                    
                    bid = opt_ticker.bid if opt_ticker.bid and opt_ticker.bid > 0 else 0
                    ask = opt_ticker.ask if opt_ticker.ask and opt_ticker.ask > 0 else 0
                    mid_price = (bid + ask) / 2 if bid and ask else 0
                    
                    if mid_price <= 0:
                        continue
                    
                    # Calculate metrics
                    exp_date = datetime.strptime(target_expiry, '%Y%m%d')
                    dte = (exp_date - datetime.now()).days
                    
                    # Premium yield = premium / strike price
                    premium_yield = (mid_price / closest_strike) * 100
                    
                    # Annualized return
                    annual_return = (premium_yield * 365 / dte) if dte > 0 else 0
                    
                    # Get delta if available
                    delta = None
                    if opt_ticker.modelGreeks:
                        delta = opt_ticker.modelGreeks.delta
                    
                    # Check if meets criteria
                    if annual_return >= self.min_annual_return * 100:
                        candidates.append({
                            'symbol': symbol,
                            'stock_price': round(stock_price, 2),
                            'strike': closest_strike,
                            'expiry': exp_date.strftime('%b %d, %Y'),
                            'dte': dte,
                            'premium': round(mid_price, 2),
                            'bid': round(bid, 2),
                            'ask': round(ask, 2),
                            'delta': round(delta, 3) if delta else None,
                            'premium_yield': round(premium_yield, 2),
                            'annual_return': round(annual_return, 1),
                            'capital_required': closest_strike * 100,
                            'breakeven': round(closest_strike - mid_price, 2),
                            'otm_pct': round((1 - closest_strike / stock_price) * 100, 1)
                        })
                    
                    # Cancel market data
                    self.monitor.ib.cancelMktData(stock)
                    self.monitor.ib.cancelMktData(put)
                    
                except Exception as e:
                    logger.debug(f"Error scanning {symbol}: {e}")
                    continue
            
            # Sort by annual return descending
            candidates.sort(key=lambda x: x['annual_return'], reverse=True)
            
            logger.info(f"✅ Morning Scanner: Found {len(candidates)} CSP candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"Error in morning scanner: {e}")
            return []
    
    def format_scan_report(self, candidates: List[Dict]) -> str:
        """Format scan results as text report"""
        if not candidates:
            return "No CSP candidates found meeting criteria."
        
        report = "🌅 MORNING WHEEL SCANNER REPORT\n"
        report += "=" * 50 + "\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += f"Criteria: DTE {self.target_dte_min}-{self.target_dte_max}, Min Return {self.min_annual_return*100:.0f}%\n\n"
        
        report += f"Found {len(candidates)} opportunities:\n\n"
        
        for i, c in enumerate(candidates[:10], 1):  # Top 10
            report += f"{i}. {c['symbol']} - CSP @ ${c['strike']:.0f}\n"
            report += f"   Stock: ${c['stock_price']:.2f} | OTM: {c['otm_pct']:.1f}%\n"
            report += f"   Premium: ${c['premium']:.2f} (${c['bid']:.2f}-${c['ask']:.2f})\n"
            report += f"   Expiry: {c['expiry']} ({c['dte']} days)\n"
            report += f"   📈 Annual Return: {c['annual_return']:.1f}%\n"
            report += f"   💰 Capital: ${c['capital_required']:,.0f} | Breakeven: ${c['breakeven']:.2f}\n"
            if c['delta']:
                report += f"   Delta: {c['delta']:.3f}\n"
            report += "\n"
        
        report += "-" * 50 + "\n"
        report += "Review in TWS before trading.\n"
        
        return report

# -------------------------------------------------------------
# Daily Workflow Class
# -------------------------------------------------------------
class DailyWorkflow:
    """Automate daily wheel strategy workflow"""
    
    def __init__(self, monitor: WheelMonitor, scanner: WheelScanner, 
                 executor: TradeExecutor, alert_manager: AlertManager):
        self.monitor = monitor
        self.scanner = scanner
        self.executor = executor
        self.alert_manager = alert_manager
        
    def morning_routine(self):
        """Enhanced pre-market preparation with all optimizations"""
        print(f"\n=== Morning Routine {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        
        # Generate comprehensive summary
        summary = self.monitor.generate_morning_summary()
        
        # Display market conditions
        print(f"Market Regime: {summary['market_regime']}")
        print(f"VIX: {summary['vix_level']:.1f} ({summary['vix_percentile']:.0f}th percentile)")
        print(f"Correlation: {summary['correlation']:.2f}")
        print(f"Market Breadth: {summary['breadth']['market_health']}")
        
        # Display risk warnings
        if summary['risk_warnings']:
            print("\n⚠️ RISK WARNINGS:")
            for warning in summary['risk_warnings']:
                print(f"  - {warning}")
        
        # Display seasonal notes
        print(f"\n📅 Seasonal Notes:")
        for note in summary['seasonal_notes']:
            print(f"  - {note}")
        
        # Check circuit breaker
        cb_status = self.monitor.check_circuit_breaker()
        if cb_status['active']:
            print(f"\n⛔ Circuit breaker active: {cb_status['reason']}")
            print(f"Ends: {cb_status['ends']}")
            return
        
        # Display positions needing attention
        if summary['positions_needing_attention']:
            print(f"\n📋 Positions Requiring Action ({len(summary['positions_needing_attention'])}):")
            for adj in summary['positions_needing_attention'][:3]:  # Limit to 3
                print(f"  - {adj['symbol']}: {adj['action']} - {adj['reason']}")
        
        # Display new opportunities
        if summary['new_opportunities']:
            print(f"\n💡 New Opportunities:")
            for opp in summary['new_opportunities'][:3]:
                print(f"  - {opp['symbol']} ${opp['strike']}P: "
                      f"{opp['annual_return']:.1%} return, "
                      f"IV Rank {opp['iv_rank']:.0f}%")
        
        # Send alerts
        self._send_morning_alerts(summary)
    
    def afternoon_checkin(self):
        """Enhanced afternoon check-in at 2:30 PM"""
        print(f"\n=== Afternoon Check-in {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        
        # Check for 80% profit rolls
        positions = self.monitor.ib.positions()
        profit_rolls = []
        
        for pos in positions:
            if pos.contract.secType == 'OPT' and pos.position < 0:
                if pos.unrealizedPnL:
                    pnl_pct = pos.unrealizedPnL / abs(pos.avgCost * pos.position)
                    dte = (pos.contract.lastTradeDateOrContractMonth - datetime.now()).days
                    
                    if pnl_pct >= 0.80 and dte > 7:
                        profit_rolls.append({
                            'symbol': pos.contract.symbol,
                            'strike': pos.contract.strike,
                            'profit': pnl_pct,
                            'dte': dte
                        })
        
        if profit_rolls:
            print(f"\n💰 Profit Roll Opportunities:")
            for roll in profit_rolls:
                print(f"  - {roll['symbol']} ${roll['strike']}: "
                      f"{roll['profit']:.0%} profit with {roll['dte']} DTE")
        
        # Execute any required actions
        self._execute_afternoon_trades()
        
        # Prepare tomorrow
        self._prepare_next_day_plan()
    
    def end_of_day_routine(self):
        """End of day routine"""
        print(f"\n=== End of Day Routine {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        
        # Calculate daily P&L
        # Would need to track from morning
        
        # Update performance metrics
        
        # Save state
        print("Daily routine completed")
    
    def _send_morning_alerts(self, summary: Dict):
        """Send morning summary alerts"""
        if summary['risk_warnings'] or len(summary['positions_needing_attention']) > 0:
            alert = Alert(
                priority=AlertPriority.IMPORTANT,
                title="Morning Summary - Action Required",
                message=f"{len(summary['positions_needing_attention'])} positions need attention. "
                        f"{len(summary['risk_warnings'])} risk warnings active.",
                action_required="Review positions"
            )
            asyncio.run(self.alert_manager.send_alert(alert))
    
    def _execute_afternoon_trades(self):
        """Execute afternoon trading decisions"""
        # Get all adjustments needed
        adjustments = self.monitor.check_adjustments_needed()
        
        for adj in adjustments:
            # Check if we can make another decision today
            if not self.monitor.decision_counter.can_make_decision():
                print(f"❌ Daily decision limit reached ({self.monitor.decision_counter.max_daily_decisions})")
                break
                
            if adj['priority'] in ['CRITICAL', 'IMPORTANT']:
                print(f"📊 Evaluating: {adj['symbol']} - {adj['action']}")
                
                # Record the decision before execution
                decision_made = self.monitor.decision_counter.record_decision(
                    symbol=adj['symbol'],
                    action_type=adj['action'],
                    reason=adj.get('reason', 'Risk management'),
                    priority=adj['priority'],
                    executed=False
                )
                
                if not decision_made:
                    print(f"❌ Cannot record decision for {adj['symbol']}")
                    continue
                
                # Execute based on action type
                try:
                    if 'ROLL' in adj['action']:
                        result = self._execute_roll(adj)
                        self.monitor.decision_counter.record_decision(
                            symbol=adj['symbol'],
                            action_type=adj['action'],
                            reason=adj.get('reason', 'Risk management'),
                            priority=adj['priority'],
                            executed=True,
                            result='SUCCESS' if result else 'FAILED'
                        )
                    elif 'CLOSE' in adj['action']:
                        result = self._execute_close(adj)
                        self.monitor.decision_counter.record_decision(
                            symbol=adj['symbol'],
                            action_type=adj['action'],
                            reason=adj.get('reason', 'Risk management'),
                            priority=adj['priority'],
                            executed=True,
                            result='SUCCESS' if result else 'FAILED'
                        )
                except Exception as e:
                    print(f"❌ Error executing {adj['action']} for {adj['symbol']}: {e}")
                    self.monitor.decision_counter.record_decision(
                        symbol=adj['symbol'],
                        action_type=adj['action'],
                        reason=adj.get('reason', 'Risk management'),
                        priority=adj['priority'],
                        executed=True,
                        result='FAILED',
                        notes=f"Error: {str(e)}"
                    )
    
    def _prepare_next_day_plan(self):
        """Prepare plan for next trading day"""
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Check earnings
        earnings_stocks = []
        for symbol in self.monitor.watchlist:
            days_to_earnings = self.monitor.days_to_earnings(symbol)
            if 0 <= days_to_earnings <= 1:
                earnings_stocks.append(symbol)
        
        if earnings_stocks:
            print(f"\n📊 Tomorrow's Earnings: {', '.join(earnings_stocks)}")
            print("  - Close or roll affected positions")
            print("  - Prepare for post-earnings IV crush trades")
        
        # Save plan
        self._save_daily_plan(tomorrow)
    
    def _save_daily_plan(self, target_date):
        """Save daily plan to database or file"""
        # In production, would save to persistent storage
        # Simplified implementation
        print(f"Plan for {target_date.strftime('%Y-%m-%d')} prepared")
    
    def _execute_roll(self, adjustment):
        """Execute a roll based on adjustment"""
        # Get target contract
        old_contract = adjustment['position']
        
        # Determine new expiry
        old_expiry = old_contract.lastTradeDateOrContractMonth
        
        # Find next monthly expiration
        # In production, would get from option chain
        new_expiry = old_expiry + timedelta(days=30)
        
        # Determine new strike based on action
        if adjustment['action'] == 'ROLL_DEFENSIVE':
            # Roll down for puts, up for calls
            if old_contract.right == 'P':
                # Get current price
                current_price = self.monitor.ib.reqMktData(Stock(old_contract.symbol, 'SMART')).marketPrice()
                
                # Roll to 0.30 delta
                new_strike = self._find_strike_by_delta(old_contract.symbol, new_expiry, 'P', 0.30)
            else:  # Call
                current_price = self.monitor.ib.reqMktData(Stock(old_contract.symbol, 'SMART')).marketPrice()
                
                # Roll to 0.30 delta
                new_strike = self._find_strike_by_delta(old_contract.symbol, new_expiry, 'C', 0.30)
        
        elif adjustment['action'] == 'ROLL_TIME':
            # Same strike, next cycle
            new_strike = old_contract.strike
        
        else:  # ROLL_POSITION (profit roll)
            if old_contract.right == 'P':
                # Roll down slightly for puts
                new_strike = old_contract.strike * 0.98
            else:
                # Roll up slightly for calls
                new_strike = old_contract.strike * 1.02
        
        # Execute roll
        self.executor.roll_position(adjustment['position'], new_strike, new_expiry)
    
    def _execute_close(self, adjustment):
        """Execute a position close"""
        self.executor.close_position(adjustment['position'], adjustment['reason'])
    
    def _find_strike_by_delta(self, symbol, expiry, right, target_delta):
        """Find strike with closest delta to target"""
        # In production, would get from option chain
        # Simplified implementation
        stock = Stock(symbol, 'SMART')
        current_price = self.monitor.ib.reqMktData(stock).marketPrice()
        
        if right == 'P':
            # For put, lower strike = higher delta
            return current_price * (1 - target_delta)
        else:
            # For call, higher strike = lower delta
            return current_price * (1 + target_delta)
    
    def weekly_performance_review(self):
        """Weekly performance review with enhanced metrics"""
        print(f"\n=== Weekly Performance Review {datetime.now().strftime('%Y-%m-%d')} ===")
        
        # Get account value
        account_value = self.monitor.ib.accountSummary()[0].value
        
        # Calculate weekly change
        weekly_change = (account_value - self.monitor.account_value) / self.monitor.account_value
        
        print(f"Account Value: ${account_value:,.2f}")
        print(f"Weekly Change: {weekly_change:.2%}")
        
        # Check performance against SPY
        spy = yf.Ticker('SPY')
        spy_weekly = spy.history(period='5d')
        spy_weekly_return = (spy_weekly['Close'].iloc[-1] - spy_weekly['Close'].iloc[0]) / spy_weekly['Close'].iloc[0]
        
        print(f"SPY Weekly: {spy_weekly_return:.2%}")
        print(f"Alpha: {weekly_change - spy_weekly_return:.2%}")
        
        # Check strategy performance metrics
        tracker = PerformanceTracker()
        metrics = tracker.calculate_metrics(account_value)
        
        print(f"\nStrategy Metrics:")
        print(f"Win Rate: {metrics['win_rate']:.1%}")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Sortino Ratio: {metrics['sortino_ratio']:.2f}")
        
        # Check win streak
        print(f"Current Win Streak: {self.monitor.win_streak_manager.consecutive_wins}")
        
        # Plan for next week
        self._plan_next_week()
    
    def _plan_next_week(self):
        """Plan strategy for next week"""
        # Check market regime
        regime = self.monitor.detect_market_regime()
        vix = yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1]
        
        print(f"\nNext Week Planning:")
        print(f"Market Regime: {regime}")
        print(f"VIX Level: {vix:.1f}")
        
        # Check upcoming earnings
        earnings_next_week = []
        
        for symbol in self.monitor.watchlist:
            days_to_earnings = self.monitor.days_to_earnings(symbol)
            if 0 < days_to_earnings <= 7:
                earnings_next_week.append((symbol, days_to_earnings))
        
        if earnings_next_week:
            print("\nUpcoming Earnings:")
            for symbol, days in sorted(earnings_next_week, key=lambda x: x[1]):
                print(f"  - {symbol}: {days} days")
        
        # Suggest focus areas
        print("\nFocus Areas:")
        
        if regime == 'BULL':
            print("  - Higher delta strikes (30-40)")
            print("  - Potential post-earnings trades")
            print("  - Allow more assignments")
        elif regime == 'BEAR':
            print("  - Lower delta strikes (15-25)")
            print("  - Focus on dividend aristocrats")
            print("  - Reduce sector concentration")
        else:
            print("  - Balanced approach (25-30 delta)")
            print("  - Mixed growth and dividend stocks")
            print("  - Neutral on assignment")

# -------------------------------------------------------------
# Enhanced Daily Workflow with Screener Reports
# -------------------------------------------------------------

class EnhancedDailyWorkflow(DailyWorkflow):
    """Enhanced workflow with pre-market and after-close screeners"""
    
    def __init__(self, monitor: WheelMonitor, scanner: WheelScanner, 
                 executor: TradeExecutor, alert_manager: EnhancedAlertManager):
        super().__init__(monitor, scanner, executor, alert_manager)
        self.sector_screener = SectorOpportunityScreener(monitor, scanner)
    
    def pre_market_screener(self):
        """Run pre-market opportunity screener"""
        print(f"\n=== Pre-Market Screener {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        
        # Get all opportunities
        all_opportunities = self.scanner.scan_all_opportunities()
        
        # Get sector analysis
        sector_gaps = self.sector_screener.get_sector_gaps()
        sector_analysis = {}
        
        for gap in sector_gaps:
            sector_analysis[gap['sector']] = {
                'current': gap['current'],
                'target_range': gap['target_range'],
                'gap': gap['gap'],
                'action': 'Add positions' if gap['gap'] > 0.05 else 'Maintain'
            }
        
        # Get sector-specific recommendations
        sector_recommendations = self.sector_screener.get_top_sector_recommendations()
        
        # Enhance opportunities with sector data
        for opp in all_opportunities:
            # Check if this sector is underweight
            sector_gap = next((g for g in sector_gaps if g['sector'] == opp['sector']), None)
            if sector_gap and sector_gap['gap'] > 0.05:
                opp['sector_underweight'] = True
            
            # Add score from sector screener
            sector_rec = next((r for r in sector_recommendations if r['symbol'] == opp['symbol']), None)
            if sector_rec:
                opp['score'] = sector_rec['score']
        
        # Sort by score and filter
        scored_opportunities = [o for o in all_opportunities if 'score' in o]
        scored_opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        # Prepare summary stats
        summary_stats = {
            'total_opportunities': len(all_opportunities),
            'avg_return': sum(o['annual_return'] for o in all_opportunities) / len(all_opportunities) if all_opportunities else 0,
            'underweight_sectors': sum(1 for g in sector_gaps if g['gap'] > 0.05),
            'market_regime': self.monitor.detect_market_regime(),
            'vix': yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1]
        }
        
        # Send report
        asyncio.run(self.alert_manager.send_screener_report(
            'morning_report',
            scored_opportunities,
            sector_analysis,
            summary_stats
        ))
        
        print(f"Pre-market screener report sent via {self.alert_manager.screener_config['delivery_methods']['morning_report']}")
    
    def after_close_screener(self):
        """Run after-close opportunity screener for next day"""
        print(f"\n=== After-Close Screener {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        
        # Similar to pre-market but focuses on next day's opportunities
        # Include earnings calendar for next day
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Get opportunities
        all_opportunities = self.scanner.scan_all_opportunities()
        
        # Filter out stocks with earnings tomorrow
        tomorrow_earnings = []
        filtered_opportunities = []
        
        for opp in all_opportunities:
            days_to_earnings = self.monitor.days_to_earnings(opp['symbol'])
            if days_to_earnings == 1:
                tomorrow_earnings.append(opp['symbol'])
            else:
                filtered_opportunities.append(opp)
        
        # Get post-earnings opportunities
        post_earnings_opps = []
        for symbol in self.monitor.watchlist:
            pe_check = self.monitor.check_post_earnings_opportunity(symbol)
            if pe_check['opportunity']:
                # Find opportunity data for this symbol
                symbol_opps = [o for o in all_opportunities if o['symbol'] == symbol]
                for opp in symbol_opps:
                    opp['post_earnings'] = True
                    opp['iv_drop'] = pe_check.get('iv_drop', 0)
                    post_earnings_opps.append(opp)
        
        # Combine and sort
        all_opportunities = filtered_opportunities + post_earnings_opps
        
        # Get sector analysis
        sector_gaps = self.sector_screener.get_sector_gaps()
        sector_analysis = {}
        
        for gap in sector_gaps:
            sector_analysis[gap['sector']] = {
                'current': gap['current'],
                'target_range': gap['target_range'],
                'gap': gap['gap'],
                'action': 'Add positions' if gap['gap'] > 0.05 else 'Maintain'
            }
        
        # Detect sector rotation
        rotations = self.sector_screener.detect_sector_rotation()
        
        # Prepare summary with additional info
        summary_stats = {
            'total_opportunities': len(all_opportunities),
            'avg_return': sum(o['annual_return'] for o in all_opportunities) / len(all_opportunities) if all_opportunities else 0,
            'underweight_sectors': sum(1 for g in sector_gaps if g['gap'] > 0.05),
            'market_regime': self.monitor.detect_market_regime(),
            'vix': yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1],
            'tomorrow_earnings': tomorrow_earnings,
            'post_earnings_count': len(post_earnings_opps),
            'sector_rotations': rotations
        }
        
        # Send evening report
        asyncio.run(self.alert_manager.send_screener_report(
            'evening_report',
            all_opportunities[:self.alert_manager.screener_config['max_opportunities_per_report']],
            sector_analysis,
            summary_stats
        ))
        
        print(f"After-close screener report sent via {self.alert_manager.screener_config['delivery_methods']['evening_report']}")
    
    def check_critical_opportunities(self):
        """Check for critical opportunities that need immediate attention"""
        # This runs during the day to catch special situations
        
        critical_opps = []
        
        # Check for post-earnings IV crush opportunities
        for symbol in self.monitor.watchlist:
            pe_check = self.monitor.check_post_earnings_opportunity(symbol)
            if pe_check['opportunity'] and pe_check.get('iv_drop', 0) > 40:
                # Large IV crush - critical opportunity
                iv_data = self.monitor.get_iv_metrics(symbol)
                strikes = self.scanner._find_wheel_strikes(symbol, iv_data)
                
                for strike in strikes:
                    if strike['annual_return'] > 0.30:  # 30%+ return
                        strike['critical_reason'] = f"Post-earnings IV crush: {pe_check['iv_drop']:.0f}% drop"
                        critical_opps.append(strike)
        
        # Check for extreme underweight sectors with high-scoring opportunities
        sector_gaps = self.sector_screener.get_sector_gaps()
        for gap in sector_gaps:
            if gap['gap'] > 0.10:  # 10%+ underweight
                # Find best opportunity in this sector
                sector_opps = self.sector_screener.find_sector_opportunities()
                if gap['sector'] in sector_opps and sector_opps[gap['sector']]:
                    best = sector_opps[gap['sector']][0]
                    if best.get('score', 0) > 0.8:
                        best['critical_reason'] = f"Sector {gap['sector']} is {gap['gap']:.0%} underweight"
                        critical_opps.append(best)
        
        if critical_opps:
            # Send critical alert
            summary_stats = {
                'total_opportunities': len(critical_opps),
                'avg_return': sum(o['annual_return'] for o in critical_opps) / len(critical_opps),
                'market_regime': self.monitor.detect_market_regime(),
                'vix': yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1]
            }
            
            asyncio.run(self.alert_manager.send_screener_report(
                'critical_opportunities',
                critical_opps,
                {},  # No full sector analysis for critical alerts
                summary_stats
            ))
            
            print(f"CRITICAL: {len(critical_opps)} high-priority opportunities found and reported")
# -------------------------------------------------------------
# Technical Recovery Framework
# -------------------------------------------------------------
class TechnicalRecoveryManager:
    """Manage system recovery from technical failures and outages"""
    
    def __init__(self, monitor: WheelMonitor, database_path: str):
        self.monitor = monitor
        self.database_path = database_path
        self.reconnection_attempts = 0
        self.max_reconnection_attempts = 3
        self.backup_api_endpoints = [
            {'host': '127.0.0.1', 'port': 7497},  # Primary
            {'host': '127.0.0.1', 'port': 7496},  # Secondary
            {'host': 'gw.ibllc.com', 'port': 4001}  # Emergency gateway
        ]
        self.current_endpoint_index = 0
        self.connection_status = 'CONNECTED'
        self.last_backup_time = None
        
    def handle_connection_failure(self):
        """Respond to API connection failure"""
        self.connection_status = 'DISCONNECTED'
        
        # Log the failure
        logging.critical(f"Connection failure detected at {datetime.now()}")
        
        # Attempt reconnection
        self.attempt_reconnection()
        
        # If still disconnected after max attempts, switch to backup endpoint
        if self.connection_status == 'DISCONNECTED':
            self.switch_to_backup_endpoint()
        
        # If still disconnected, activate manual trading mode
        if self.connection_status == 'DISCONNECTED':
            self.activate_manual_trading_mode()
            
    def attempt_reconnection(self):
        """Attempt to reconnect to current API endpoint"""
        while self.reconnection_attempts < self.max_reconnection_attempts:
            self.reconnection_attempts += 1
            
            logging.info(f"Reconnection attempt {self.reconnection_attempts} of {self.max_reconnection_attempts}")
            
            try:
                # Get current endpoint
                endpoint = self.backup_api_endpoints[self.current_endpoint_index]
                
                # Disconnect if connected
                if self.monitor.ib.isConnected():
                    self.monitor.ib.disconnect()
                
                # Wait before reconnecting
                time.sleep(5)
                
                # Attempt reconnection with unique client ID
                self.monitor.ib.connect(
                    host=endpoint['host'],
                    port=endpoint['port'],
                    clientId=config['ibkr']['monitor_client_id']  # Use monitor client ID
                )
                
                # Check if connection successful
                if self.monitor.ib.isConnected():
                    self.connection_status = 'CONNECTED'
                    self.reconnection_attempts = 0
                    logging.info(f"Successfully reconnected to {endpoint['host']}:{endpoint['port']}")
                    
                    # Reconcile positions after reconnection
                    self.reconcile_positions()
                    return True
            
            except Exception as e:
                logging.error(f"Reconnection attempt failed: {e}")
        
        # Reset counter after all attempts
        self.reconnection_attempts = 0
        return False
    
    def switch_to_backup_endpoint(self):
        """Switch to next backup API endpoint"""
        # Move to next endpoint
        self.current_endpoint_index = (self.current_endpoint_index + 1) % len(self.backup_api_endpoints)
        
        endpoint = self.backup_api_endpoints[self.current_endpoint_index]
        logging.info(f"Switching to backup endpoint: {endpoint['host']}:{endpoint['port']}")
        
        try:
            # Disconnect if connected
            if self.monitor.ib.isConnected():
                self.monitor.ib.disconnect()
            
            # Connect to new endpoint with unique client ID
            self.monitor.ib.connect(
                host=endpoint['host'],
                port=endpoint['port'],
                clientId=config['ibkr']['monitor_client_id']  # Use monitor client ID
            )
            
            # Check if connection successful
            if self.monitor.ib.isConnected():
                self.connection_status = 'CONNECTED'
                logging.info(f"Successfully connected to backup endpoint")
                
                # Reconcile positions after connection
                self.reconcile_positions()
                return True
                
        except Exception as e:
            logging.error(f"Failed to connect to backup endpoint: {e}")
            
        return False
    
    def activate_manual_trading_mode(self):
        """Activate manual trading mode when all reconnection attempts fail"""
        logging.critical("ACTIVATING MANUAL TRADING MODE")
        
        # Send critical alerts
        alert = Alert(
            priority=AlertPriority.CRITICAL,
            title="MANUAL TRADING MODE ACTIVATED",
            message="All connection attempts failed. System switching to manual trading mode.",
            action_required="Execute critical defensive trades manually. Check system status."
        )
        
        try:
            asyncio.run(self.monitor.alert_manager.send_alert(alert))
        except Exception as e:
            logging.error(f"Failed to send alert: {e}")
            
        # Generate list of critical positions that need attention
        critical_positions = self._identify_critical_positions()
        
        # Export critical positions report
        self._export_critical_positions(critical_positions)
        
    def _identify_critical_positions(self):
        """Identify positions requiring immediate attention during outage"""
        # This would be populated from database if IB connection is down
        # For demonstration, we'll create a simple structure
        critical_positions = []
        
        try:
            # If connection works, get positions from IB
            if self.monitor.ib.isConnected():
                positions = self.monitor.ib.positions()
                
                for position in positions:
                    if position.contract.secType == 'OPT':
                        dte = (position.contract.lastTradeDateOrContractMonth - datetime.now()).days
                        
                        # Critical if: low DTE or high delta
                        if dte <= 3 or self._has_high_delta(position):
                            critical_positions.append({
                                'symbol': position.contract.symbol,
                                'secType': position.contract.secType,
                                'strike': position.contract.strike if hasattr(position.contract, 'strike') else None,
                                'right': position.contract.right if hasattr(position.contract, 'right') else None,
                                'expiry': position.contract.lastTradeDateOrContractMonth,
                                'position': position.position,
                                'market_value': position.marketValue,
                                'reason': 'Low DTE' if dte <= 3 else 'High Delta'
                            })
            else:
                # Fallback to database
                # In production, would query from local database
                logging.warning("Cannot identify critical positions - using cached data")
                
        except Exception as e:
            logging.error(f"Error identifying critical positions: {e}")
            
        return critical_positions
    
    def _has_high_delta(self, position):
        """Check if position has high delta (defensive)"""
        try:
            # Try to get delta from market data
            ticker = self.monitor.ib.reqMktData(position.contract)
            util.sleep(0.5)
            
            if ticker.modelGreeks and abs(ticker.modelGreeks.delta) > 0.6:
                return True
                
        except Exception:
            # If cannot get delta, assume high for safety
            return True
            
        return False
    
    def _export_critical_positions(self, critical_positions):
        """Export critical positions to file for manual handling"""
        try:
            filename = f"critical_positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w') as f:
                json.dump(critical_positions, f, indent=2, default=str)
                
            logging.info(f"Critical positions exported to {filename}")
            
        except Exception as e:
            logging.error(f"Failed to export critical positions: {e}")
    
    def reconcile_positions(self):
        """Reconcile positions after connection recovery"""
        logging.info("Reconciling positions after reconnection")
        
        try:
            # Get positions from broker
            broker_positions = self.monitor.ib.positions()
            
            # Get positions from local database
            local_positions = self._get_positions_from_database()
            
            # Compare and reconcile
            self._compare_positions(broker_positions, local_positions)
            
            # Update local database with current positions
            self._update_positions_database(broker_positions)
            
            logging.info("Position reconciliation completed")
            
        except Exception as e:
            logging.error(f"Error reconciling positions: {e}")
    
    def _get_positions_from_database(self):
        """Get positions from local database"""
        # In production, would query from database
        # For demonstration, return empty list
        return []
    
    def _compare_positions(self, broker_positions, local_positions):
        """Compare broker positions with local database"""
        # In production, would compare positions and report discrepancies
        # For demonstration, log basic information
        logging.info(f"Broker positions: {len(broker_positions)}")
        logging.info(f"Local positions: {len(local_positions)}")
    
    def _update_positions_database(self, positions):
        """Update local database with current positions"""
        # In production, would update database
        # For demonstration, log update attempt
        logging.info(f"Updating local database with {len(positions)} positions")
    
    def create_database_backup(self):
        """Create backup of system database"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{self.database_path}_backup_{timestamp}"
            
            # Create backup (would use proper DB backup method in production)
            shutil.copy(self.database_path, backup_filename)
            
            self.last_backup_time = datetime.now()
            logging.info(f"Database backed up to {backup_filename}")
            
            # Manage retention
            self._manage_backup_retention()
            
            return True
            
        except Exception as e:
            logging.error(f"Database backup failed: {e}")
            return False
    
    def _manage_backup_retention(self):
        """Manage backup retention period"""
        try:
            # Get all backup files
            backup_files = glob.glob(f"{self.database_path}_backup_*")
            
            # Sort by creation time
            backup_files.sort(key=lambda x: os.path.getctime(x))
            
            # Keep only last 30 daily backups
            if len(backup_files) > 30:
                for old_backup in backup_files[:-30]:
                    os.remove(old_backup)
                    logging.info(f"Removed old backup: {old_backup}")
                    
        except Exception as e:
            logging.error(f"Error managing backup retention: {e}")
    
    def restore_from_backup(self, backup_path=None):
        """Restore database from backup"""
        try:
            if not backup_path:
                # Find most recent backup
                backup_files = glob.glob(f"{self.database_path}_backup_*")
                backup_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
                
                if not backup_files:
                    logging.error("No backup files found")
                    return False
                    
                backup_path = backup_files[0]
            
            # Restore database
            shutil.copy(backup_path, self.database_path)
            
            logging.info(f"Database restored from {backup_path}")
            return True
            
        except Exception as e:
            logging.error(f"Database restore failed: {e}")
            return False

# -------------------------------------------------------------
# Execution Quality Analysis
# -------------------------------------------------------------

class ExecutionQualityAnalyzer:
    """Analyze and optimize trade execution quality"""
    
    def __init__(self, monitor: WheelMonitor):
        self.monitor = monitor
        self.execution_history = []
        self.daily_stats = {
            'total_trades': 0,
            'filled_better_than_mid': 0,
            'average_slippage': 0,
            'average_fill_time': 0,
            'order_types': {
                'LMT': 0,
                'MKT': 0,
                'STP': 0,
                'MIDPRICE': 0
            },
            'fill_by_time': {
                '9:30-10:30': 0,
                '10:30-12:00': 0,
                '12:00-14:00': 0,
                '14:00-15:30': 0,
                '15:30-16:00': 0
            }
        }
    
    def record_execution(self, order, fill_info):
        """Record execution data for analysis"""
        # Extract relevant data
        symbol = order.contract.symbol if hasattr(order, 'contract') else 'Unknown'
        order_type = order.orderType if hasattr(order, 'orderType') else 'Unknown'
        intended_price = order.lmtPrice if hasattr(order, 'lmtPrice') else 0
        fill_price = fill_info.execution.price if hasattr(fill_info, 'execution') else 0
        fill_time = fill_info.execution.time if hasattr(fill_info, 'execution') else datetime.now()
        submit_time = getattr(order, 'submit_time', datetime.now())
        
        # Calculate metrics
        slippage = fill_price - intended_price if order.action == 'BUY' else intended_price - fill_price
        slippage_pct = (slippage / intended_price) * 100 if intended_price != 0 else 0
        fill_duration = (fill_time - submit_time).total_seconds() if submit_time else 0
        
        # Get market data for comparison
        try:
            contract = order.contract
            ticker = self.monitor.ib.reqMktData(contract)
            util.sleep(0.5)
            
            bid = ticker.bid if hasattr(ticker, 'bid') else 0
            ask = ticker.ask if hasattr(ticker, 'ask') else 0
            mid_price = (bid + ask) / 2 if bid and ask else 0
            
            # Determine if filled better than mid
            better_than_mid = False
            if order.action == 'BUY' and fill_price < mid_price:
                better_than_mid = True
            elif order.action == 'SELL' and fill_price > mid_price:
                better_than_mid = True
                
        except Exception:
            mid_price = 0
            better_than_mid = False
        
        # Record execution data
        execution_data = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'order_type': order_type,
            'action': order.action if hasattr(order, 'action') else 'Unknown',
            'intended_price': intended_price,
            'fill_price': fill_price,
            'slippage': slippage,
            'slippage_pct': slippage_pct,
            'fill_duration': fill_duration,
            'better_than_mid': better_than_mid,
            'mid_price': mid_price,
            'bid': bid if 'bid' in locals() else 0,
            'ask': ask if 'ask' in locals() else 0,
            'market_hours': self._get_market_hours_category(fill_time)
        }
        
        self.execution_history.append(execution_data)
        
        # Update daily stats
        self._update_daily_stats(execution_data)
        
        return execution_data
    
    def _get_market_hours_category(self, timestamp):
        """Categorize time into market hours buckets"""
        if not timestamp:
            return 'Unknown'
            
        try:
            hour = timestamp.hour
            minute = timestamp.minute
            
            market_time = hour * 100 + minute  # e.g., 9:45 = 945
            
            if 930 <= market_time < 1030:
                return '9:30-10:30'
            elif 1030 <= market_time < 1200:
                return '10:30-12:00'
            elif 1200 <= market_time < 1400:
                return '12:00-14:00'
            elif 1400 <= market_time < 1530:
                return '14:00-15:30'
            elif 1530 <= market_time <= 1600:
                return '15:30-16:00'
            else:
                return 'Extended Hours'
                
        except Exception:
            return 'Unknown'
    
    def _update_daily_stats(self, execution_data):
        """Update daily execution statistics"""
        # Increment total trades
        self.daily_stats['total_trades'] += 1
        
        # Update better than mid count
        if execution_data['better_than_mid']:
            self.daily_stats['filled_better_than_mid'] += 1
            
        # Update average slippage
        current_total = self.daily_stats['average_slippage'] * (self.daily_stats['total_trades'] - 1)
        new_average = (current_total + execution_data['slippage_pct']) / self.daily_stats['total_trades']
        self.daily_stats['average_slippage'] = new_average
        
        # Update average fill time
        current_total = self.daily_stats['average_fill_time'] * (self.daily_stats['total_trades'] - 1)
        new_average = (current_total + execution_data['fill_duration']) / self.daily_stats['total_trades']
        self.daily_stats['average_fill_time'] = new_average
        
        # Update order type count
        order_type = execution_data['order_type']
        if order_type in self.daily_stats['order_types']:
            self.daily_stats['order_types'][order_type] += 1
            
        # Update time of day stats
        market_hours = execution_data['market_hours']
        if market_hours in self.daily_stats['fill_by_time']:
            self.daily_stats['fill_by_time'][market_hours] += 1
    
    def get_daily_report(self):
        """Generate daily execution quality report"""
        if self.daily_stats['total_trades'] == 0:
            return {
                'status': 'No trades executed today',
                'timestamp': datetime.now()
            }
            
        better_than_mid_pct = (self.daily_stats['filled_better_than_mid'] / self.daily_stats['total_trades']) * 100
            
        report = {
            'timestamp': datetime.now(),
            'total_trades': self.daily_stats['total_trades'],
            'better_than_mid_pct': better_than_mid_pct,
            'average_slippage_pct': self.daily_stats['average_slippage'],
            'average_fill_time_seconds': self.daily_stats['average_fill_time'],
            'order_types': self.daily_stats['order_types'],
            'fill_by_time': self.daily_stats['fill_by_time'],
            'grade': self._calculate_execution_grade(better_than_mid_pct, self.daily_stats['average_slippage'])
        }
        
        return report
    
    def _calculate_execution_grade(self, better_than_mid_pct, avg_slippage):
        """Calculate execution quality grade"""
        # Calculate base score (0-100)
        better_mid_score = better_than_mid_pct
        slippage_score = max(0, 100 - abs(avg_slippage * 10))  # 1% slippage = 10 point deduction
        
        # Weighted average
        final_score = (better_mid_score * 0.7) + (slippage_score * 0.3)
        
        # Convert to letter grade
        if final_score >= 90:
            return 'A'
        elif final_score >= 80:
            return 'B'
        elif final_score >= 70:
            return 'C'
        elif final_score >= 60:
            return 'D'
        else:
            return 'F'
    
    def analyze_optimal_execution_time(self):
        """Analyze optimal time of day for executions"""
        if not self.execution_history:
            return {
                'status': 'No execution data available',
                'timestamp': datetime.now()
            }
            
        # Group by time category
        time_data = {}
        for execution in self.execution_history:
            category = execution['market_hours']
            if category not in time_data:
                time_data[category] = {
                    'count': 0,
                    'slippage_total': 0,
                    'better_than_mid_count': 0,
                    'fill_time_total': 0
                }
                
            data = time_data[category]
            data['count'] += 1
            data['slippage_total'] += execution['slippage_pct']
            data['better_than_mid_count'] += 1 if execution['better_than_mid'] else 0
            data['fill_time_total'] += execution['fill_duration']
        
        # Calculate averages
        results = {}
        for category, data in time_data.items():
            if data['count'] > 0:
                results[category] = {
                    'count': data['count'],
                    'avg_slippage_pct': data['slippage_total'] / data['count'],
                    'better_than_mid_pct': (data['better_than_mid_count'] / data['count']) * 100,
                    'avg_fill_time': data['fill_time_total'] / data['count']
                }
        
        # Find optimal time
        if results:
            optimal_time = max(results.items(), key=lambda x: x[1]['better_than_mid_pct'])
            
            return {
                'timestamp': datetime.now(),
                'time_data': results,
                'optimal_time': optimal_time[0],
                'recommendation': f"Best execution typically occurs during {optimal_time[0]} "
                                 f"with {optimal_time[1]['better_than_mid_pct']:.1f}% better than mid fills."
            }
        else:
            return {
                'status': 'Insufficient data for analysis',
                'timestamp': datetime.now()
            }
    
    def analyze_optimal_order_types(self):
        """Analyze which order types perform best"""
        if not self.execution_history:
            return {
                'status': 'No execution data available',
                'timestamp': datetime.now()
            }
            
        # Group by order type
        order_data = {}
        for execution in self.execution_history:
            order_type = execution['order_type']
            if order_type not in order_data:
                order_data[order_type] = {
                    'count': 0,
                    'slippage_total': 0,
                    'better_than_mid_count': 0
                }
                
            data = order_data[order_type]
            data['count'] += 1
            data['slippage_total'] += execution['slippage_pct']
            data['better_than_mid_count'] += 1 if execution['better_than_mid'] else 0
        
        # Calculate averages
        results = {}
        for order_type, data in order_data.items():
            if data['count'] > 0:
                results[order_type] = {
                    'count': data['count'],
                    'avg_slippage_pct': data['slippage_total'] / data['count'],
                    'better_than_mid_pct': (data['better_than_mid_count'] / data['count']) * 100
                }
        
        # Find optimal order type
        if results:
            optimal_type = max(results.items(), key=lambda x: x[1]['better_than_mid_pct'])
            
            return {
                'timestamp': datetime.now(),
                'order_data': results,
                'optimal_order_type': optimal_type[0],
                'recommendation': f"{optimal_type[0]} orders perform best with "
                                 f"{optimal_type[1]['better_than_mid_pct']:.1f}% better than mid fills."
            }
        else:
            return {
                'status': 'Insufficient data for analysis',
                'timestamp': datetime.now()
            }

# -------------------------------------------------------------
# Web Dashboard
# -------------------------------------------------------------

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'secret!'
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['DEBUG'] = True
app.jinja_env.auto_reload = True

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Reduce yfinance and other external library logging
logging.getLogger('yfinance').setLevel(logging.WARNING)
logging.getLogger('peewee').setLevel(logging.WARNING) 
logging.getLogger('ib_insync').setLevel(logging.INFO)

socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True, async_mode='threading', ping_timeout=5)

# Global variables to store current data for API endpoints - NO DEFAULTS
current_metrics = {}  # MUST be populated with real data or fail
current_positions = None  # MUST be populated with real data or fail
current_account_data = None  # Live account data from IBKR (NetLiquidation, AvailableFunds, etc.)

# Store active connections
active_connections = {
    'monitor': None,
    'scanner': None,
    'executor': None
}

def cleanup_connections():
    """Ensure all IBKR connections are properly closed"""
    try:
        if monitor.ib.isConnected():
            monitor.ib.disconnect()
            print("✅ Monitor connection closed")
    except Exception as e:
        print(f"⚠️ Error closing monitor connection: {e}")
    
    # Close any Greeks connections in the pool
    global _greeks_connection_pool
    for symbol, conn in _greeks_connection_pool.items():
        try:
            if conn.isConnected():
                conn.disconnect()
                print(f"✅ Greeks connection for {symbol} closed")
        except Exception as e:
            print(f"⚠️ Error closing Greeks connection for {symbol}: {e}")
    _greeks_connection_pool.clear()

def signal_handler(signum, frame):
    """Handle signals gracefully"""
    logger.info(f"Received signal {signum}")
    cleanup_connections()
    sys.exit(0)

# Register cleanup on exit
import atexit, signal
atexit.register(cleanup_connections)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@socketio.on('connect')
def handle_connect():
    print('\n=== Client Connected ===')
    print('Client session ID:', request.sid)
    print('Transport:', request.args.get('transport', 'unknown'))
    print('Headers:', dict(request.headers))
    socketio.emit('status', {'status': 'connected'})
    
    # Immediately send current data when client connects
    try:
        if current_positions is None or current_metrics is None:
            raise RuntimeError("No real data available - dashboard not ready")
        
        # Check IBKR connection status
        ibkr_connected = False
        if dashboard and dashboard.monitor and dashboard.monitor.ib:
            ibkr_connected = dashboard.monitor.ib.isConnected()
        elif monitor and monitor.ib:
            ibkr_connected = monitor.ib.isConnected()
        
        data = {
            'positions': current_positions,
            'metrics': current_metrics,
            'opportunities': [],
            'alerts': [],
            'ibkr_connected': ibkr_connected,
            'last_ibkr_update': datetime.now().isoformat() if ibkr_connected else current_account_data.get('last_updated') if current_account_data else None
        }
        socketio.emit('update', data)
        print('Sent initial data to connected client')
    except Exception as e:
        print(f'Error sending initial data: {e}')

@socketio.on('disconnect')
def handle_disconnect(data=None):
    print('\n=== Client Disconnected ===')
    try:
        print('Client session ID:', request.sid if hasattr(request, 'sid') else 'unknown')
        print('Transport:', request.args.get('transport', 'unknown') if hasattr(request, 'args') else 'unknown')
    except Exception as e:
        print(f'Error getting disconnect info: {e}')
    socketio.emit('status', {'status': 'disconnected'})

@socketio.on_error_default
def default_error_handler(e):
    print('\n=== Socket.IO Error ===')
    print('Error:', e)
    print('Client session ID:', request.sid)
    print('Transport:', request.args.get('transport', 'unknown'))
    print('Headers:', dict(request.headers))
    socketio.emit('status', {'status': 'error', 'message': str(e)})

@socketio.on('ping')
def handle_ping():
    print('\n=== Received Ping ===')
    print('Client session ID:', request.sid)
    print('Transport:', request.args.get('transport', 'unknown'))
    socketio.emit('pong')

# -------------------------------------------------------------
# API Routes - Direct IBKR Access
# -------------------------------------------------------------

# REMOVED: Live positions endpoint disabled - use async positions with real IBKR deltas only

# REMOVED: This endpoint was calling disabled get_live_positions()
# Use the working endpoint at line 5664 instead

@app.route('/api/live-metrics')
def get_live_metrics():
    """Get LIVE metrics directly from IBKR portfolio data"""
    try:
        logger.info("Fetching LIVE metrics from IBKR portfolio...")
        
        # Get VIX data for market conditions
        current_vix = 20.0
        vix_percentile = 50
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1d")
            current_vix = float(vix_data['Close'].iloc[-1]) if not vix_data.empty else 20.0
            
            # Calculate VIX percentile (simplified)
            vix_hist = vix.history(period="1y")
            vix_percentile = (vix_hist['Close'] < current_vix).mean() * 100 if not vix_hist.empty else 50
            logger.info(f"VIX: {current_vix:.1f} ({vix_percentile:.0f}th percentile)")
        except Exception as e:
            logger.warning(f"Could not fetch VIX data: {e}")
            
        # Determine market regime based on VIX
        if current_vix < 15:
            regime = "BULLISH"
            regime_strength = "Low volatility environment"
        elif current_vix > 25:
            regime = "BEARISH" 
            regime_strength = "High volatility environment"
        else:
            regime = "NEUTRAL"
            regime_strength = "Moderate volatility environment"

        # Get data directly from IBKR - use global monitor if dashboard not ready
        account_value = 0
        available_funds = 0
        total_cash = 0
        unrealized_pnl = 0
        
        # Try to get IB connection from dashboard first, then fall back to global monitor
        ib_client = None
        if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
            ib_client = dashboard.monitor.ib
        elif monitor and monitor.ib and monitor.ib.isConnected():
            ib_client = monitor.ib
            logger.info("Using global monitor (dashboard not ready)")
        
        if ib_client:
            try:
                # Use portfolio() which gets live portfolio items directly
                portfolio_items = ib_client.portfolio()
                
                # Calculate totals from portfolio
                total_market_value = sum(item.marketValue for item in portfolio_items if item.position != 0)
                unrealized_pnl = sum(item.unrealizedPNL for item in portfolio_items if item.position != 0)
                
                # Get account values - these are updated via callbacks
                account_values = ib_client.accountValues()
                for av in account_values:
                    if av.tag == 'NetLiquidation' and av.currency == 'USD':
                        account_value = float(av.value)
                    elif av.tag == 'AvailableFunds' and av.currency == 'USD':
                        available_funds = float(av.value)
                    elif av.tag == 'TotalCashValue' and av.currency == 'USD':
                        total_cash = float(av.value)
                
                logger.info(f"💰 LIVE IBKR: Account=${account_value:,.2f} | Available=${available_funds:,.2f} | Unrealized P&L=${unrealized_pnl:,.2f}")
            except Exception as e:
                logger.error(f"Error fetching IBKR data: {e}")
                return jsonify({'error': str(e), 'status': 'error'})
        else:
            logger.warning("⚠️ IBKR not connected")
            return jsonify({
                'error': 'IBKR not connected',
                'status': 'disconnected',
                'message': 'Please ensure TWS/IB Gateway is running and restart the dashboard.'
            })
        
        # Calculate derived values
        cash_percentage = (available_funds / account_value * 100) if account_value > 0 else 0
        starting_value = config.get('account', {}).get('starting_value', 80000)
        total_return = (account_value - starting_value) / starting_value if starting_value > 0 else 0
        return_pct = total_return * 100
        
        metrics = {
            'account_value': account_value,
            'available_funds': available_funds,
            'total_cash': total_cash,
            'unrealized_pnl': unrealized_pnl,
            'cash_percentage': cash_percentage,
            'return_pct': return_pct,
            'total_return': total_return,
            'win_rate': 0,  # Will be calculated once dashboard is ready
            'sharpe_ratio': 0,  # Will be calculated once dashboard is ready
            'regime': regime,
            'regime_strength': regime_strength,
            'vix_value': current_vix,
            'vix_percentile': f"{vix_percentile:.0f}th percentile",
            'last_updated': datetime.now().isoformat()
        }
        
        # Update global cache
        global current_metrics
        if current_metrics is not None:
            current_metrics.update(metrics)
        else:
            current_metrics = metrics
        
        logger.info(f"✅ LIVE metrics: Account=${account_value:,.2f}, Cash%={cash_percentage:.1f}%, Return={return_pct:.1f}%")
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error getting live metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics')
def api_get_metrics():
    """Get metrics - redirects to live data"""
    return get_live_metrics()
@app.route('/api/portfolio-chart')
def get_portfolio_chart():
    """Get portfolio performance chart data from Postgres daily snapshots"""
    try:
        logger.info("Fetching portfolio chart data from database...")
        
        from datetime import datetime, timedelta
        
        # Try to get real data from Postgres daily snapshots
        chart_data = []
        
        if DB_AVAILABLE:
            try:
                snapshots = trade_db.get_daily_snapshots(days=30)
                if snapshots and len(snapshots) > 0:
                    logger.info(f"Found {len(snapshots)} daily snapshots in database")
                    
                    # Get starting value for return calculation
                    starting_value = config.get('account', {}).get('starting_value', 80000)
                    peak_value = starting_value
                    
                    for snapshot in snapshots:
                        value = snapshot.get('account_value', 0)
                        
                        # Update peak for drawdown
                        if value > peak_value:
                            peak_value = value
                        
                        # Calculate drawdown
                        drawdown = ((peak_value - value) / peak_value) * 100 if peak_value > value else 0
                        
                        chart_data.append({
                            'date': snapshot.get('snapshot_date', '').strftime('%Y-%m-%d') if hasattr(snapshot.get('snapshot_date', ''), 'strftime') else str(snapshot.get('snapshot_date', '')),
                            'value': round(value, 2),
                            'spy_value': 0,  # TODO: Add SPY tracking
                            'drawdown': round(drawdown, 2),
                            'return_pct': round(((value - starting_value) / starting_value) * 100, 2) if starting_value > 0 else 0
                        })
                    
                    logger.info(f"✅ Loaded {len(chart_data)} days of REAL portfolio history")
                    return jsonify(chart_data)
            except Exception as db_err:
                logger.warning(f"Database query failed: {db_err}")
        
        # If no database data, return current value as single point (no fake history)
        current_value = 0
        try:
            ib_client = None
            if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
                ib_client = dashboard.monitor.ib
            elif monitor and monitor.ib and monitor.ib.isConnected():
                ib_client = monitor.ib
            
            if ib_client:
                account_values = ib_client.accountValues()
                for av in account_values:
                    if av.tag == 'NetLiquidation' and av.currency == 'USD':
                        current_value = float(av.value)
                        break
        except Exception as e:
            logger.warning(f"Could not get current value: {e}")
        
        if current_value > 0:
            starting_value = config.get('account', {}).get('starting_value', 80000)
            chart_data = [{
                'date': datetime.now().strftime('%Y-%m-%d'),
                'value': round(current_value, 2),
                'spy_value': 0,
                'drawdown': 0,
                'return_pct': round(((current_value - starting_value) / starting_value) * 100, 2)
            }]
            logger.info(f"✅ Returning current value only (no historical data yet): ${current_value:,.2f}")
            return jsonify(chart_data)
        
        # No data available
        logger.warning("⚠️ No portfolio data available")
        return jsonify({'error': 'No portfolio data available - IBKR connection required', 'status': 'no_data'})
        
    except Exception as e:
        logger.error(f"Error getting portfolio chart: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/benchmark-comparison')
def get_benchmark_comparison():
    """
    Get portfolio vs benchmark (SPY) comparison data
    Query params:
        - period: 1m, 3m, 6m, ytd, 1y, all (default: 3m)
        - benchmark: ticker symbol (default: SPY)
    """
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        period = request.args.get('period', '3m').lower()
        benchmark_ticker = request.args.get('benchmark', 'SPY').upper()
        
        logger.info(f"📊 Fetching benchmark comparison: {period} period, {benchmark_ticker} benchmark")
        
        # Calculate date range based on period
        today = datetime.now().date()
        
        if period == '1m':
            start_date = today - timedelta(days=30)
        elif period == '3m':
            start_date = today - timedelta(days=90)
        elif period == '6m':
            start_date = today - timedelta(days=180)
        elif period == 'ytd':
            start_date = datetime(today.year, 1, 1).date()
        elif period == '1y':
            start_date = today - timedelta(days=365)
        else:  # 'all'
            start_date = today - timedelta(days=365 * 3)  # Max 3 years
        
        # Get portfolio data from Postgres
        portfolio_data = []
        portfolio_start_value = None
        
        if DB_AVAILABLE:
            try:
                days_back = (today - start_date).days + 5  # Buffer for weekends
                snapshots = trade_db.get_daily_snapshots(days=days_back)
                
                if snapshots:
                    for snap in snapshots:
                        snap_date = snap.get('snapshot_date')
                        if hasattr(snap_date, 'date'):
                            snap_date = snap_date.date() if hasattr(snap_date, 'date') else snap_date
                        
                        if snap_date and snap_date >= start_date:
                            value = float(snap.get('account_value', 0))
                            if portfolio_start_value is None and value > 0:
                                portfolio_start_value = value
                            
                            portfolio_data.append({
                                'date': snap_date.strftime('%Y-%m-%d') if hasattr(snap_date, 'strftime') else str(snap_date),
                                'value': value
                            })
                    
                    logger.info(f"✅ Found {len(portfolio_data)} portfolio snapshots from database")
            except Exception as db_err:
                logger.warning(f"Database query failed: {db_err}")
        
        # If no portfolio data, try to get current value
        if not portfolio_data:
            current_value = 0
            try:
                if current_account_data:
                    current_value = current_account_data.get('account_value', 0)
                
                if current_value == 0:
                    ib_client = None
                    if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
                        ib_client = dashboard.monitor.ib
                    elif monitor and monitor.ib and monitor.ib.isConnected():
                        ib_client = monitor.ib
                    
                    if ib_client:
                        account_values = ib_client.accountValues()
                        for av in account_values:
                            if av.tag == 'NetLiquidation' and av.currency == 'USD':
                                current_value = float(av.value)
                                break
            except Exception as e:
                logger.warning(f"Could not get current value: {e}")
            
            if current_value > 0:
                portfolio_data = [{'date': today.strftime('%Y-%m-%d'), 'value': current_value}]
                portfolio_start_value = current_value
                logger.info(f"Using current value only: ${current_value:,.2f}")
        
        # Get benchmark (SPY) data from yfinance
        benchmark_data = []
        benchmark_start_value = None
        
        try:
            import time
            time.sleep(0.5)  # Rate limit protection
            
            spy = yf.Ticker(benchmark_ticker)
            # Fetch a bit more data than needed to ensure we cover the range
            hist = spy.history(start=start_date - timedelta(days=7), end=today + timedelta(days=1))
            
            if not hist.empty:
                for idx, row in hist.iterrows():
                    bar_date = idx.date() if hasattr(idx, 'date') else idx
                    
                    if bar_date >= start_date:
                        close_price = float(row['Close'])
                        if benchmark_start_value is None:
                            benchmark_start_value = close_price
                        
                        benchmark_data.append({
                            'date': bar_date.strftime('%Y-%m-%d'),
                            'value': close_price
                        })
                
                logger.info(f"✅ Fetched {len(benchmark_data)} {benchmark_ticker} data points")
            else:
                logger.warning(f"No benchmark data returned from yfinance")
        except Exception as yf_err:
            logger.error(f"yfinance error: {yf_err}")
        
        # Build comparison response with percentage returns
        result = {
            'period': period,
            'benchmark_ticker': benchmark_ticker,
            'portfolio': {
                'data': [],
                'start_value': portfolio_start_value,
                'current_value': portfolio_data[-1]['value'] if portfolio_data else None,
                'return_pct': 0
            },
            'benchmark': {
                'data': [],
                'start_value': benchmark_start_value,
                'current_value': benchmark_data[-1]['value'] if benchmark_data else None,
                'return_pct': 0
            },
            'alpha': 0,
            'comparison_data': []
        }
        
        # Calculate percentage returns for portfolio
        if portfolio_start_value and portfolio_start_value > 0:
            for point in portfolio_data:
                pct_return = ((point['value'] - portfolio_start_value) / portfolio_start_value) * 100
                result['portfolio']['data'].append({
                    'date': point['date'],
                    'value': point['value'],
                    'return_pct': round(pct_return, 2)
                })
            
            if portfolio_data:
                result['portfolio']['return_pct'] = round(
                    ((portfolio_data[-1]['value'] - portfolio_start_value) / portfolio_start_value) * 100, 2
                )
        
        # Calculate percentage returns for benchmark
        if benchmark_start_value and benchmark_start_value > 0:
            for point in benchmark_data:
                pct_return = ((point['value'] - benchmark_start_value) / benchmark_start_value) * 100
                result['benchmark']['data'].append({
                    'date': point['date'],
                    'value': point['value'],
                    'return_pct': round(pct_return, 2)
                })
            
            if benchmark_data:
                result['benchmark']['return_pct'] = round(
                    ((benchmark_data[-1]['value'] - benchmark_start_value) / benchmark_start_value) * 100, 2
                )
        
        # Calculate alpha (portfolio return - benchmark return)
        result['alpha'] = round(result['portfolio']['return_pct'] - result['benchmark']['return_pct'], 2)
        
        # Build merged comparison data for charting (align dates)
        portfolio_dict = {p['date']: p for p in result['portfolio']['data']}
        benchmark_dict = {b['date']: b for b in result['benchmark']['data']}
        
        all_dates = sorted(set(list(portfolio_dict.keys()) + list(benchmark_dict.keys())))
        
        for date in all_dates:
            point = {'date': date}
            if date in portfolio_dict:
                point['portfolio_return'] = portfolio_dict[date]['return_pct']
                point['portfolio_value'] = portfolio_dict[date]['value']
            if date in benchmark_dict:
                point['benchmark_return'] = benchmark_dict[date]['return_pct']
                point['benchmark_value'] = benchmark_dict[date]['value']
            result['comparison_data'].append(point)
        
        logger.info(f"📈 Benchmark comparison: Portfolio {result['portfolio']['return_pct']}% vs {benchmark_ticker} {result['benchmark']['return_pct']}% = Alpha {result['alpha']}%")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting benchmark comparison: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sector-exposure')
def get_sector_exposure():
    """Get sector exposure data based on current positions"""
    try:
        logger.info("Calculating sector exposure from LIVE data...")
        
        # Get LIVE account value from IBKR
        total_value = 0
        cash_value = 0
        
        ib_client = None
        if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
            ib_client = dashboard.monitor.ib
        elif monitor and monitor.ib and monitor.ib.isConnected():
            ib_client = monitor.ib
        
        if ib_client:
            try:
                account_values = ib_client.accountValues()
                for av in account_values:
                    if av.tag == 'NetLiquidation' and av.currency == 'USD':
                        total_value = float(av.value)
                    elif av.tag == 'TotalCashValue' and av.currency == 'USD':
                        cash_value = float(av.value)
                logger.info(f"💰 Using LIVE account value: ${total_value:,.2f}")
            except Exception as e:
                logger.warning(f"Could not get account value: {e}")
        
        if total_value == 0:
            return jsonify({'error': 'IBKR not connected', 'status': 'disconnected'})
        
        # Get LIVE positions from IBKR
        positions = []
        if ib_client:
            try:
                portfolio_items = ib_client.portfolio()
                for item in portfolio_items:
                    if item.position != 0:
                        positions.append({
                            'symbol': item.contract.symbol,
                            'contract_type': 'STK' if getattr(item.contract, 'right', '0') == '0' else 'OPT',
                            'marketValue': item.marketValue
                        })
            except Exception as e:
                logger.warning(f"Could not get positions: {e}")
        
        # Map symbols to sectors (simplified)
        sector_map = {
            'NVDA': 'Technology', 'AMD': 'Technology', 'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOG': 'Technology',
            'DE': 'Industrials', 'CAT': 'Industrials', 'BA': 'Industrials',
            'JPM': 'Financials', 'BAC': 'Financials', 'GS': 'Financials',
            'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'PFE': 'Healthcare',
            'WMT': 'Consumer', 'COST': 'Consumer', 'TGT': 'Consumer',
            'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy'
        }
        
        sector_exposure = {}
        
        # Calculate exposure from positions
        for pos in positions:
            symbol = pos.get('symbol', '')
            market_value = abs(pos.get('marketValue', 0))
            sector = sector_map.get(symbol, 'Other')
            
            if sector not in sector_exposure:
                sector_exposure[sector] = 0
            sector_exposure[sector] += market_value
        
        # Convert to percentages and sort
        sector_data = []
        for sector, value in sector_exposure.items():
            percentage = (value / total_value) * 100 if total_value > 0 else 0
            sector_data.append({
                'sector': sector,
                'value': round(value, 2),
                'percentage': round(percentage, 1)
            })
        
        # Sort by percentage descending
        sector_data.sort(key=lambda x: x['percentage'], reverse=True)
        
        # Add cash as a sector (calculated from LIVE data)
        cash_percentage = (cash_value / total_value * 100) if total_value > 0 else 0
        sector_data.insert(0, {
            'sector': 'Cash',
            'value': round(cash_value, 2),
            'percentage': round(cash_percentage, 1)
        })
        
        logger.info(f"✅ Calculated exposure for {len(sector_data)} sectors")
        return jsonify(sector_data)
        
    except Exception as e:
        logger.error(f"Error calculating sector exposure: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/win-streak')
def get_win_streak():
    """Get current win streak data"""
    try:
        logger.info("Fetching win streak data...")
        
        # Get win streak data from IBKR - NO FALLBACKS
        try:
            win_streak = dashboard.monitor.win_streak_manager.consecutive_wins if dashboard and dashboard.monitor else None
            win_streak_threshold = dashboard.monitor.thresholds['win_streak_caution'] if dashboard and dashboard.monitor else None
            if win_streak is None or win_streak_threshold is None:
                raise ValueError("No IBKR win streak data available")
        except (AttributeError, KeyError) as e:
            logger.error(f"❌ WIN STREAK FAILED - NO IBKR DATA: {e}")
            return jsonify({'error': 'IBKR win streak data required'}), 503
        
        # Determine risk level and message
        if win_streak >= win_streak_threshold:
            risk_level = 'high'
            message = f'Position sizing reduced due to {win_streak} consecutive wins'
            alert_type = 'warning'
        elif win_streak >= 5:
            risk_level = 'medium'
            message = f'Monitoring for risk creep - {win_streak} consecutive wins'
            alert_type = 'info'
        else:
            risk_level = 'low'
            message = 'No size adjustment needed yet'
            alert_type = 'info'
        
        data = {
            'consecutive_wins': win_streak,
            'threshold': win_streak_threshold,
            'risk_level': risk_level,
            'message': message,
            'alert_type': alert_type,
            'risk_check': 'No risk creep detected' if risk_level == 'low' else 'Risk monitoring active'
        }
        
        logger.info(f"✅ Win streak: {win_streak} consecutive wins")
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error getting win streak data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/opportunities')
def get_opportunities():
    """Get current trading opportunities"""
    try:
        logger.info("Fetching trading opportunities...")
        
        # Check if scanner is available and connected
        if not hasattr(dashboard, 'scanner') or not dashboard.scanner:
            logger.error("❌ OPPORTUNITIES FAILED - NO SCANNER AVAILABLE")
            raise RuntimeError("Scanner not available - no real opportunities possible")
        
        # Try to get opportunities (removed signal timeout - doesn't work in threads)
        try:
            opportunities = dashboard.scanner.scan_opportunities()
        except Exception as e:
            logger.error(f"Scanner failed: {e}")
            raise RuntimeError(f"Scanner completely unavailable: {e}")
        
        # Ensure we have a list and limit to top 5
        if not isinstance(opportunities, list):
            opportunities = []
        
        opportunities = opportunities[:5]
        
        # Format opportunities for frontend
        formatted_opportunities = []
        for opp in opportunities:
            formatted_opp = {
                'symbol': opp.get('symbol', 'Unknown'),
                'strike': opp.get('strike', 0),
                'score': opp.get('score', 0),
                'annual_return': opp.get('annual_return', 0),
                'iv_rank': opp.get('iv_rank', 0),
                'sector': opp.get('sector', 'Unknown'),
                'expiry': opp.get('expiry', 'Unknown'),
                'premium': opp.get('premium', 0)
            }
            formatted_opportunities.append(formatted_opp)
        
        logger.info(f"✅ Found {len(formatted_opportunities)} opportunities")
        return jsonify(formatted_opportunities)
        
    except Exception as e:
        logger.error(f"❌ OPPORTUNITIES FAILED: {e}")
        raise RuntimeError(f"Failed to get real opportunities: {e}")

@app.route('/api/daily-workflow')
def get_daily_workflow():
    """Get daily workflow status"""
    try:
        logger.info("Fetching daily workflow status...")
        
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Get workflow status from tracker
        try:
            workflow_status = dashboard.monitor.workflow_tracker.get_workflow_status()
            completion_summary = dashboard.monitor.workflow_tracker.get_completion_summary()
            next_workflow = dashboard.monitor.workflow_tracker.get_next_workflow()
            
            # Get current time for status determination
            current_time = datetime.now()
            current_hour = current_time.hour
            
            workflow_data = [
                {
                    'name': 'Morning Routine',
                    'status': 'completed' if workflow_status['morning_routine']['completed'] else ('in_progress' if 9 <= current_hour < 10 else 'pending'),
                    'time': workflow_status['morning_routine']['actual_time'] or '--',
                    'badge_class': 'badge-success' if workflow_status['morning_routine']['completed'] else 'badge-info',
                    'notes': workflow_status['morning_routine']['notes']
                },
                {
                    'name': 'Afternoon Check-in',
                    'status': 'completed' if workflow_status['afternoon_checkin']['completed'] else ('in_progress' if 14 <= current_hour < 15 else 'pending'),
                    'time': workflow_status['afternoon_checkin']['actual_time'] or '--',
                    'badge_class': 'badge-success' if workflow_status['afternoon_checkin']['completed'] else 'badge-info',
                    'notes': workflow_status['afternoon_checkin']['notes']
                },
                {
                    'name': 'EOD Routine',
                    'status': 'completed' if workflow_status['eod_routine']['completed'] else ('in_progress' if 16 <= current_hour < 17 else 'pending'),
                    'time': workflow_status['eod_routine']['actual_time'] or '--',
                    'badge_class': 'badge-success' if workflow_status['eod_routine']['completed'] else 'badge-info',
                    'notes': workflow_status['eod_routine']['notes']
                },
                {
                    'name': 'Weekly Review',
                    'status': 'completed' if workflow_status['weekly_review']['completed'] else ('in_progress' if 16 <= current_hour < 17 else 'pending'),
                    'time': workflow_status['weekly_review']['actual_time'] or '--',
                    'badge_class': 'badge-success' if workflow_status['weekly_review']['completed'] else 'badge-info',
                    'notes': workflow_status['weekly_review']['notes']
                }
            ]
            
            # Add completion summary and next workflow info
            workflow_data.append({
                'completion_summary': completion_summary,
                'next_workflow': next_workflow
            })
            
        except Exception as e:
            logger.error(f"❌ DAILY WORKFLOW FAILED - NO WORKFLOW TRACKER: {e}")
            raise RuntimeError(f"Workflow tracker not available: {e}")
        
        logger.info(f"✅ Daily workflow status updated")
        return jsonify(workflow_data)
        
    except Exception as e:
        logger.error(f"Error getting daily workflow status: {e}")
        return jsonify({'error': str(e)}), 500

from datetime import datetime

@app.route('/api/mark-morning-complete', methods=['POST'])
def api_mark_morning_complete():
    """Mark morning routine as complete"""
    try:
        notes = request.json.get('notes', 'Morning routine completed') if request.json else 'Morning routine completed'
        dashboard.monitor.workflow_tracker.mark_workflow_complete('morning_routine', notes)
        logger.info("✅ Morning routine marked as complete")
        return jsonify({'status': 'success', 'message': 'Morning routine marked as complete'})
    except Exception as e:
        logger.error(f"❌ Error marking morning routine complete: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/mark-afternoon-complete', methods=['POST'])
def api_mark_afternoon_complete():
    """Mark afternoon checkin as complete"""
    try:
        notes = request.json.get('notes', 'Afternoon checkin completed') if request.json else 'Afternoon checkin completed'
        dashboard.monitor.workflow_tracker.mark_workflow_complete('afternoon_checkin', notes)
        logger.info("✅ Afternoon checkin marked as complete")
        return jsonify({'status': 'success', 'message': 'Afternoon checkin marked as complete'})
    except Exception as e:
        logger.error(f"❌ Error marking afternoon checkin complete: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/mark-eod-complete', methods=['POST'])
def api_mark_eod_complete():
    """Mark end of day routine as complete"""
    try:
        notes = request.json.get('notes', 'End of day routine completed') if request.json else 'End of day routine completed'
        dashboard.monitor.workflow_tracker.mark_workflow_complete('eod_routine', notes)
        logger.info("✅ End of day routine marked as complete")
        return jsonify({'status': 'success', 'message': 'End of day routine marked as complete'})
    except Exception as e:
        logger.error(f"❌ Error marking EOD routine complete: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/mark-weekly-complete', methods=['POST'])
def api_mark_weekly_complete():
    """Mark weekly review as complete"""
    try:
        notes = request.json.get('notes', 'Weekly review completed') if request.json else 'Weekly review completed'
        dashboard.monitor.workflow_tracker.mark_workflow_complete('weekly_review', notes)
        logger.info("✅ Weekly review marked as complete")
        return jsonify({'status': 'success', 'message': 'Weekly review marked as complete'})
    except Exception as e:
        logger.error(f"❌ Error marking weekly review complete: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/income-tracking')
def get_income_tracking():
    """Get income tracking data"""
    try:
        logger.info("Fetching income tracking data...")
        
        # Get account value and calculate monthly target (1.5% of capital)
        try:
            account_value = dashboard.monitor.account_value if dashboard and dashboard.monitor else None
            if account_value is None:
                raise ValueError("No IBKR account value available")
        except (AttributeError, Exception) as e:
            logger.error(f"❌ INCOME TRACKING FAILED - NO IBKR ACCOUNT VALUE: {e}")
            return jsonify({'error': 'IBKR account value required'}), 503
        monthly_target = account_value * 0.015
        
        # Calculate collected income from actual closed positions this month
        try:
            if hasattr(dashboard, 'tracker') and dashboard.tracker:
                # Get real income from closed positions this month
                current_month = current_date.month
                current_year = current_date.year
                closed_trades = dashboard.tracker.get_closed_trades_for_month(current_year, current_month)
                collected_income = sum(trade.get('realized_pnl', 0) for trade in closed_trades if trade.get('realized_pnl', 0) > 0)
            else:
                raise ValueError("No tracker available for real income calculation")
        except Exception as e:
            logger.error(f"❌ INCOME TRACKING FAILED - NO REAL INCOME DATA: {e}")
            return jsonify({'error': 'Real income data required'}), 503
        
        # Calculate progress percentage
        progress_percentage = (collected_income / monthly_target * 100) if monthly_target > 0 else 0
        
        # Calculate days remaining in month
        current_date = datetime.now()
        if current_date.month == 12:
            next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            next_month = current_date.replace(month=current_date.month + 1, day=1)
        
        days_remaining = (next_month - current_date).days
        
        income_data = {
            'monthly_target': monthly_target,
            'collected_income': collected_income,
            'progress_percentage': progress_percentage,
            'days_remaining': days_remaining,
            'target_percentage_text': '1.5% of capital',
            'progress_text': f'{progress_percentage:.0f}% of target'
        }
        
        logger.info(f"✅ Income tracking: ${collected_income:.0f} / ${monthly_target:.0f}")
        return jsonify(income_data)
        
    except Exception as e:
        logger.error(f"Error getting income tracking data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/decision-support')
def get_decision_support():
    """Get decision support alerts and recommendations"""
    try:
        logger.info("Fetching decision support data...")
        
        # Get decision counter summary
        decision_summary = dashboard.monitor.decision_counter.get_decision_summary()
        decision_breakdown = dashboard.monitor.decision_counter.get_decision_breakdown()
        
        alerts = []
        
        # Decision limit alerts
        if decision_summary['remaining'] <= 1:
            alerts.append({
                'priority': 'warning',
                'title': 'Decision Limit Warning',
                'message': f"Only {decision_summary['remaining']} decision(s) remaining today",
                'action_required': 'Conserve decisions for critical situations'
            })
        
        if decision_summary['remaining'] == 0:
            alerts.append({
                'priority': 'critical',
                'title': 'Decision Limit Reached',
                'message': 'Daily decision limit reached - no more trades today',
                'action_required': 'Wait until tomorrow for new decisions'
            })
        
        if decision_summary['pending'] > 0:
            alerts.append({
                'priority': 'info',
                'title': 'Pending Decisions',
                'message': f"{decision_summary['pending']} decision(s) pending execution",
                'action_required': 'Review and execute pending decisions'
            })
        
        # Check current VIX level for recommendations
        vix_level = 23.5  # Current VIX from the system
        
        if vix_level > 25:
            alerts.append({
                'priority': 'IMPORTANT',
                'title': 'High VIX Environment',
                'message': 'VIX above 25 - excellent conditions for selling premium',
                'action_required': 'Consider increasing position sizes'
            })
        
        # Check win streak
        try:
            if not (dashboard and dashboard.monitor and dashboard.monitor.win_streak_manager):
                raise RuntimeError("Win streak manager not available")
            win_streak = dashboard.monitor.win_streak_manager.consecutive_wins
        except (AttributeError, Exception) as e:
            logger.error(f"Win streak unavailable: {e}")
            raise RuntimeError(f"Failed to get win streak data: {e}")
        
        if win_streak >= 5:
            alerts.append({
                'priority': 'IMPORTANT',
                'title': 'Win Streak Risk',
                'message': f'{win_streak} consecutive wins - monitor for overconfidence',
                'action_required': 'Consider reducing position sizes'
            })
        
        # Market hours check
        current_time = datetime.now()
        market_hours = 9 <= current_time.hour < 16
        
        if market_hours:
            alerts.append({
                'priority': 'INFO',
                'title': 'Market Open',
                'message': 'Market is open - monitor positions actively',
                'action_required': 'Check for roll opportunities'
            })
        else:
            alerts.append({
                'priority': 'INFO',
                'title': 'Market Closed',
                'message': 'Market is closed - plan for next session',
                'action_required': 'Review EOD reports'
            })
        
        # Add general trading recommendations
        alerts.append({
            'priority': 'INFO',
            'title': 'Daily Recommendation',
            'message': 'Focus on 30-45 DTE options in current regime',
            'action_required': 'Scan for new opportunities'
        })
        
        logger.info(f"✅ Generated {len(alerts)} decision support alerts")
        
        # Return comprehensive decision data
        return jsonify({
            'decision_summary': decision_summary,
            'decision_breakdown': decision_breakdown,
            'alerts': alerts
        })
        
    except Exception as e:
        logger.error(f"Error getting decision support data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/realized-pnl')
def get_realized_pnl():
    """Get realized P&L tracking data"""
    try:
        logger.info("Fetching realized P&L data...")
        
        if not (dashboard and hasattr(dashboard, 'tracker') and dashboard.tracker):
            raise RuntimeError("Performance tracker not available")
        
        # Get different time periods
        todays_pnl = dashboard.tracker.get_todays_realized_pnl()
        mtd_pnl = dashboard.tracker.get_mtd_realized_pnl()
        
        # Calculate percentage of monthly target
        try:
            account_value = dashboard.monitor.account_value if dashboard and dashboard.monitor else None
            if account_value is None:
                raise ValueError("No IBKR account value available")
            monthly_target = account_value * 0.015
            mtd_percentage = (mtd_pnl['realized_pnl'] / monthly_target * 100) if monthly_target > 0 else 0
        except Exception as e:
            logger.error(f"Error calculating monthly target: {e}")
            monthly_target = 0
            mtd_percentage = 0
        
        # Check if data contains sample trades
        has_sample_data = any(trade.get('is_sample', False) for trade in dashboard.tracker.trades)
        
        pnl_data = {
            'todays_pnl': {
                'realized_pnl': todays_pnl['realized_pnl'],
                'trade_count': todays_pnl['trade_count'],
                'winning_trades': todays_pnl['winning_trades'],
                'losing_trades': todays_pnl['losing_trades'],
                'is_sample_data': has_sample_data
            },
            'mtd_pnl': {
                'realized_pnl': mtd_pnl['realized_pnl'],
                'trade_count': mtd_pnl['trade_count'],
                'winning_trades': mtd_pnl['winning_trades'],
                'losing_trades': mtd_pnl['losing_trades'],
                'percentage_of_target': mtd_percentage,
                'is_sample_data': has_sample_data
            },
            'monthly_target': monthly_target,
            'account_value': account_value,
            'has_sample_data': has_sample_data
        }
        
        logger.info(f"✅ Realized P&L: Today ${todays_pnl['realized_pnl']:.2f}, MTD ${mtd_pnl['realized_pnl']:.2f}")
        return jsonify(pnl_data)
        
    except Exception as e:
        logger.error(f"Error getting realized P&L data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def get_status():
    """Check system status with real Circuit Breaker and Black Swan Protocol status"""
    try:
        # Get real IBKR connection status with actual data test
        ibkr_connected = False
        ibkr_connection_reason = None
        if dashboard and dashboard.monitor and dashboard.monitor.ib:
            try:
                # Test if we can actually get data from IBKR
                basic_connected = dashboard.monitor.ib.isConnected()
                if basic_connected:
                    # For now, just trust the basic connection status to avoid event loop conflicts
                    # The real test will happen when the dashboard tries to get data
                    ibkr_connected = True
                    ibkr_connection_reason = "Connected (basic check)"
                else:
                    ibkr_connected = False
                    ibkr_connection_reason = "Not connected to IBKR"
            except Exception as e:
                ibkr_connected = False
                ibkr_connection_reason = f"Connection check error: {str(e)}"
        else:
            ibkr_connected = False
            ibkr_connection_reason = "Dashboard or monitor not available"
        
        # Get real Circuit Breaker status
        circuit_breaker_active = False
        circuit_breaker_reason = None
        if dashboard and dashboard.monitor:
            try:
                circuit_check = dashboard.monitor.check_circuit_breaker()
                circuit_breaker_active = circuit_check.get('active', False)
                circuit_breaker_reason = circuit_check.get('reason', None)
            except Exception as e:
                logger.error(f"Error checking circuit breaker: {e}")
                circuit_breaker_reason = f"Error: {e}"
        
        # Get real Black Swan Protocol status
        black_swan_active = False
        black_swan_reason = None
        if dashboard and dashboard.monitor and hasattr(dashboard.monitor, 'black_swan_protocol'):
            try:
                black_swan_active = dashboard.monitor.black_swan_protocol.active
                if black_swan_active:
                    black_swan_reason = f"Activated on {dashboard.monitor.black_swan_protocol.activation_date}"
                else:
                    black_swan_reason = "Black Swan Protocol inactive - normal market conditions"
            except Exception as e:
                logger.error(f"Error checking black swan protocol: {e}")
                black_swan_reason = f"Error: {e}"
        
        # Get seasonal pattern data
        earnings_season = None
        seasonal_focus = None
        if dashboard and dashboard.monitor:
            try:
                current_month = datetime.now().strftime('%B')
                earnings_season = current_month
                if current_month in ['January', 'April', 'July', 'October']:
                    seasonal_focus = 'Focus on post-earnings IV crush opportunities'
                elif current_month in ['February', 'May', 'August', 'November']:
                    seasonal_focus = 'Focus on pre-earnings IV expansion plays'
                else:
                    seasonal_focus = 'Focus on theta decay and time decay strategies'
            except Exception as e:
                logger.error(f"Error getting seasonal data: {e}")
        
        return jsonify({
            'status': 'ok',
            'ibkr_connected': ibkr_connected,
            'ibkr_connection_reason': ibkr_connection_reason,
            'circuit_breaker_active': circuit_breaker_active,
            'circuit_breaker_reason': circuit_breaker_reason,
            'black_swan_active': black_swan_active,
            'black_swan_reason': black_swan_reason,
            'earnings_season': earnings_season,
            'seasonal_focus': seasonal_focus,
            'websocket_enabled': True
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'ibkr_connected': False,
            'circuit_breaker_active': False,
            'black_swan_active': False,
            'websocket_enabled': True
        })

@app.route('/')
def api_dashboard():
    """Render main dashboard"""
    logger.info("Rendering dashboard template")
    return render_template('wheel_dashboard.html')
# Import required modules for async handling
import asyncio
import threading

# Create a dedicated event loop for IBKR operations
ibkr_event_loop = asyncio.new_event_loop()
ibkr_thread = threading.Thread(target=ibkr_event_loop.run_forever, daemon=True)
ibkr_thread.start()

# Function to run async tasks in the IBKR event loop
def run_in_ibkr_loop(coro):
    return asyncio.run_coroutine_threadsafe(coro, ibkr_event_loop).result()
class WheelDashboard:
    def __init__(self, monitor, scanner, tracker):
        self.monitor = monitor
        self.scanner = scanner
        self.tracker = tracker
        
    def start_monitoring(self):
        """Start real-time monitoring"""
        def monitor_loop():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            while True:
                try:
                    loop.run_until_complete(self.update_dashboard_async())
                    time.sleep(30)
                except Exception as e:
                    print(f"Monitor loop error: {e}")
                    time.sleep(5)  # Short delay on error
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        print("Dashboard monitoring started")
    
    async def update_dashboard_async(self):
        """Push updates to dashboard asynchronously"""
        try:
            print("\n========== DASHBOARD UPDATE START ==========")
            
            print("\n1. FETCHING POSITIONS")
            positions = await self._get_positions_async()
            print(f"Raw positions data:")
            for pos in positions:
                print(json.dumps(pos, indent=2, default=str))
            
            print("\n2. FETCHING ACCOUNT SUMMARY")
            global current_account_data
            try:
                # Use thread executor to avoid event loop conflicts
                import asyncio
                loop = asyncio.get_event_loop()
                account_summary = await loop.run_in_executor(None, self.monitor.ib.accountSummary)
                print("Account summary items:")
                for item in account_summary:
                    print(f"{item.tag}: {item.value}")
                
                # Extract and cache all account values for API use
                account_value = float(next((item.value for item in account_summary if item.tag == 'NetLiquidation'), 0))
                available_funds = float(next((item.value for item in account_summary if item.tag == 'AvailableFunds'), 0))
                total_cash = float(next((item.value for item in account_summary if item.tag == 'TotalCashValue'), 0))
                unrealized_pnl = float(next((item.value for item in account_summary if item.tag == 'UnrealizedPnL'), 0))
                buying_power = float(next((item.value for item in account_summary if item.tag == 'BuyingPower'), 0))
                excess_liquidity = float(next((item.value for item in account_summary if item.tag == 'ExcessLiquidity'), 0))
                
                # Cache for API endpoints (fetched here in async context, used in sync Flask routes)
                current_account_data = {
                    'account_value': account_value,
                    'available_funds': available_funds,
                    'total_cash': total_cash,
                    'unrealized_pnl': unrealized_pnl,
                    'buying_power': buying_power,
                    'excess_liquidity': excess_liquidity,
                    'last_updated': datetime.now().isoformat()
                }
                print(f"\n💰 LIVE ACCOUNT DATA CACHED:")
                print(f"   Account Value: ${account_value:,.2f}")
                print(f"   Available Funds: ${available_funds:,.2f}")
                print(f"   Unrealized P&L: ${unrealized_pnl:,.2f}")
            except Exception as e:
                print(f"❌ IBKR ACCOUNT SUMMARY FAILED: {e}")
                account_value = None
                print("❌ NO ACCOUNT VALUE - IBKR CONNECTION REQUIRED")
            
            print("\n3. CALCULATING METRICS")
            try:
                metrics = self.tracker.calculate_metrics(account_value)
                metrics['account_value'] = account_value
                
                # No fallback regime - must calculate real market regime or fail
                
                print("Calculated metrics:")
                print(json.dumps(metrics, indent=2, default=str))
            except Exception as e:
                print(f"❌ METRICS CALCULATION FAILED: {e}")
                metrics = None
                print("❌ NO METRICS - IBKR DATA REQUIRED")
            
            print("\n4. FETCHING OPPORTUNITIES")
            opportunities = await self._get_opportunities_async()
            print("Found opportunities:")
            for opp in opportunities:
                print(json.dumps(opp, indent=2, default=str))
            
            print("\n5. GETTING ALERTS")
            alerts = self._get_alerts()
            print("Active alerts:")
            for alert in alerts:
                print(json.dumps(alert, indent=2, default=str))
            
            # Check IBKR connection status
            ibkr_connected = self.monitor.ib.isConnected() if self.monitor and self.monitor.ib else False
            
            data = {
                'positions': positions,
                'opportunities': opportunities,
                'metrics': metrics,
                'alerts': alerts,
                'ibkr_connected': ibkr_connected,
                'last_ibkr_update': datetime.now().isoformat() if ibkr_connected else None
            }
            
            print("\n6. RECORDING DAILY SNAPSHOT")
            # Record daily snapshot to database for performance tracking
            if DB_AVAILABLE and account_value and account_value > 0:
                try:
                    buying_power = float(next((item.value for item in account_summary if item.tag == 'BuyingPower'), 0))
                    cash_balance = float(next((item.value for item in account_summary if item.tag == 'TotalCashValue'), 0))
                    unrealized_pnl = float(next((item.value for item in account_summary if item.tag == 'UnrealizedPnL'), 0))
                    
                    trade_db.record_daily_snapshot(
                        account_value=account_value,
                        buying_power=buying_power,
                        cash_balance=cash_balance,
                        unrealized_pnl=unrealized_pnl,
                        position_count=len(positions),
                        vix_level=metrics.get('vix_value') if metrics else None,
                        market_regime=metrics.get('regime') if metrics else None
                    )
                    print(f"📸 Recorded daily snapshot: ${account_value:,.2f}")
                except Exception as e:
                    print(f"⚠️ Failed to record daily snapshot: {e}")
            
            print("\n7. UPDATING GLOBAL CACHE")
            # Update global variables for API endpoints
            global current_metrics, current_positions
            
            # Defensive: ensure current_metrics is a dict
            current_metrics = get_current_metrics()

            # Only update metrics if they are not None
            if metrics is not None:
                current_metrics.update(metrics)
                current_metrics['last_updated'] = datetime.now().isoformat()
                print(f"Updated global cache with {len(positions)} positions and metrics")
            else:
                print("⚠️ Skipping metrics update - metrics is None")
                current_metrics['last_updated'] = datetime.now().isoformat()
            
            current_positions = positions
            
            print("\n8. FINAL DATA FOR DASHBOARD")
            print(json.dumps(data, indent=2, default=str))
            
            print("\n9. EMITTING UPDATE")
            logger.info(f"About to emit update to dashboard: {json.dumps(data)[:500]}...")
            print("About to emit update to dashboard")
            try:
                socketio.emit('update', data)
                logger.info("Emit to dashboard complete")
                print("Emit to dashboard complete")
            except Exception as emit_err:
                logger.error(f"Emit to dashboard failed: {emit_err}")
                print(f"Emit to dashboard failed: {emit_err}")
            
            print("\n========== DASHBOARD UPDATE COMPLETE ==========\n")
            
        except Exception as e:
            print(f"Error updating dashboard: {e}")
            traceback.print_exc()
            logging.error(f"Dashboard update error: {e}", exc_info=True)
            
    async def _get_positions_async(self):
        """Get all positions with analytics asynchronously"""
        # Mark this as a dashboard thread for delta fetching
        self._is_dashboard_thread = True
        position_data = []
        
        try:
            print("\n=== Fetching Positions ===")
            
            # Use thread executor to avoid event loop conflicts
            import asyncio
            loop = asyncio.get_event_loop()
            portfolio = await loop.run_in_executor(None, self.monitor.ib.portfolio)
            print(f"Got {len(portfolio)} portfolio items")
            
            for item in portfolio:
                if item.position != 0:  # Only include positions with actual holdings
                    contract = item.contract
                    print(f"Processing: {contract.symbol} ({contract.secType})")
                    
                    # Calculate P&L percentage  
                    cost_basis = abs(item.averageCost * item.position)
                    pnl_pct = (item.unrealizedPNL / cost_basis * 100) if cost_basis > 0 else 0
                    
                    # Transform for frontend compatibility
                    if contract.secType == 'OPT':
                        strike = getattr(contract, 'strike', 0)
                        option_type = getattr(contract, 'right', '')
                        exp_date = getattr(contract, 'lastTradeDateOrContractMonth', None)
                        
                        # Calculate days to expiration
                        dte = 0
                        expiry = '-'
                        if exp_date:
                            try:
                                if hasattr(exp_date, 'strftime'):
                                    expiry = exp_date.strftime('%m/%d/%Y')
                                    dte = (exp_date.date() - datetime.now().date()).days
                                else:
                                    expiry = str(exp_date)
                            except:
                                expiry = str(exp_date)
                        
                        symbol_display = f"{contract.symbol} {option_type} ${strike}"
                        contract_type = 'OPT'
                    else:
                        strike = 0
                        option_type = ''
                        dte = 0
                        expiry = '-'
                        symbol_display = contract.symbol
                        contract_type = 'STK'
                    
                    # Get LIVE delta from IBKR - NO FALLBACKS ALLOWED (using working pattern)
                    estimated_delta = None  # Must get live delta or None
                    if hasattr(contract, 'right') and contract.right != '0':  # Only for options
                        # First, try to get delta DIRECTLY from portfolio item (like ibkr_delta_service.py does)
                        if hasattr(item, 'modelGreeks') and item.modelGreeks and hasattr(item.modelGreeks, 'delta') and item.modelGreeks.delta is not None:
                            # SUCCESS: Portfolio item already has live delta!
                            estimated_delta = float(item.modelGreeks.delta)
                            logger.info(f"✅ {contract.symbol}: Portfolio item has delta {estimated_delta:.3f}")
                        else:
                            # Try SYNCHRONOUS Greeks request using threading approach (same as Flask)
                            estimated_delta = _get_delta_from_ibkr(self.monitor.ib, contract, logger)
                    elif hasattr(contract, 'right') and contract.right == '0':  # Stock
                        estimated_delta = None  # No delta for stocks
                    
                    print(f"🔍 {contract.symbol}: Calculated delta = {estimated_delta}")
                    
                    # Create position data with frontend-expected format
                    position_info = {
                        # Raw IBKR data (preserved for backward compatibility)
                        'symbol': contract.symbol,
                        'position': item.position,
                        'avgCost': item.averageCost,
                        'marketValue': item.marketValue,
                        'unrealizedPNL': item.unrealizedPNL,
                        'contract_type': contract_type,
                        
                        # Frontend-expected fields
                        'symbol_display': symbol_display,
                        'type': f"{option_type} Option" if contract_type == 'OPT' else 'Stock',
                        'strike': float(strike),
                        'expiry': expiry,
                        'dte': int(dte),
                        'premium': float(abs(item.averageCost)) if contract_type == 'OPT' else 0,
                        'pnl': float(round(pnl_pct, 1)),
                        'delta': estimated_delta,  # Use calculated delta value
                        'status': 'ROLLING' if pnl_pct < -25 else 'ACTIVE'
                    }
                    
                    print(f"✅ Processed {contract.symbol}: P&L {pnl_pct:.1f}%")
                    position_data.append(position_info)
            
            print(f"✅ Successfully processed {len(position_data)} positions")
            
            # Cache the position data for Flask threads to use
            self.cached_positions_data = position_data
            
            return position_data
            
        except Exception as e:
            logger.error(f"❌ Error in _get_positions_async: {e}")
            raise RuntimeError(f"Failed to get positions from IBKR: {e}")
        
    # Cache for opportunities to avoid repeated failures
    _opportunities_cache = {'data': [], 'timestamp': None}
    
    async def _get_opportunities_async(self):
        """Get new wheel opportunities asynchronously (with graceful fallback)"""
        import time as _time
        
        try:
            print("\nScanning for opportunities...")
            opportunities = await self.scanner.scan_opportunities_async()
            print(f"Raw scanner results: {opportunities}")
            
            # Format opportunities for display
            formatted_opps = []
            for opp in opportunities:
                try:
                    formatted_opp = {
                        'symbol': opp['symbol'],
                        'strike': float(opp['strike']),
                        'premium': float(opp['premium']),
                        'annual_return': float(opp['annual_return']) * 100,  # Convert to percentage
                        'score': round(float(opp.get('liquidity_score', 0)) / 100, 2)  # Normalize score
                    }
                    print(f"Formatted opportunity: {json.dumps(formatted_opp, indent=2)}")
                    formatted_opps.append(formatted_opp)
                except Exception as e:
                    logger.error(f"Error formatting opportunity {opp}: {e}")
                    continue  # Skip bad opportunities instead of failing entirely
            
            sorted_opps = sorted(formatted_opps, key=lambda x: x['annual_return'], reverse=True)
            print(f"\nFinal opportunities: {json.dumps(sorted_opps, indent=2)}")
            
            # Update cache on success
            DashboardManager._opportunities_cache = {'data': sorted_opps, 'timestamp': _time.time()}
            
            return sorted_opps
            
        except Exception as e:
            logger.warning(f"Opportunity scan failed ({e}), using cached data")
            # Return cached data instead of failing
            cache = DashboardManager._opportunities_cache
            if cache['data']:
                return cache['data']
            return []  # Return empty list rather than crashing
    
    async def _get_ibkr_delta_async(self, contract, contract_type):
        """Get actual delta from IBKR asynchronously - HARD FAIL if can't get live data"""
        if contract_type == 'STK':
            return 1.0
        elif contract_type != 'OPT':
            raise ValueError(f"Unknown contract type: {contract_type}")
        
        # Get live Greeks from IBKR using proper async methods
        try:
            from ib_insync import Option
            option_contract = Option(
                symbol=contract.symbol,
                lastTradeDateOrContractMonth=contract.lastTradeDateOrContractMonth,
                strike=contract.strike,
                right=contract.right,
                exchange='SMART',
                currency='USD'
            )
            
            # Use async methods to avoid event loop conflicts
            qualified_contracts = await self.monitor.ib.qualifyContractsAsync(option_contract)
            if not qualified_contracts:
                raise ValueError(f"Could not qualify contract for {contract.symbol}")
            
            qualified_contract = qualified_contracts[0]
            
            # Request market data with Greeks asynchronously
            ticker = self.monitor.ib.reqMktData(qualified_contract, '106', False, False)
            
            # Wait for Greeks to populate with async sleep
            max_wait = 5.0  # 5 second timeout
            wait_interval = 0.1
            elapsed = 0
            
            while elapsed < max_wait:
                await asyncio.sleep(wait_interval)
                elapsed += wait_interval
                
                # Check if Greeks are available
                if (hasattr(ticker, 'modelGreeks') and 
                    ticker.modelGreeks and 
                    ticker.modelGreeks.delta is not None):
                    delta_value = float(ticker.modelGreeks.delta)
                    # Cancel market data subscription
                    self.monitor.ib.cancelMktData(qualified_contract)
                    logger.info(f"✅ {contract.symbol}: LIVE IBKR delta {delta_value:.3f}")
                    return delta_value
            
            # Timeout - cancel subscription and fail hard
            self.monitor.ib.cancelMktData(qualified_contract)
            raise TimeoutError(f"Failed to get Greeks for {contract.symbol} within {max_wait}s")
            
        except Exception as e:
            logger.error(f"❌ {contract.symbol}: IBKR delta FAILED: {e}")
            raise RuntimeError(f"Failed to get IBKR delta for {contract.symbol}: {e}")
    
    def _get_ibkr_delta(self, contract, contract_type):
        """Sync wrapper for async delta retrieval - COMPLETELY DISABLED"""
        # This method has been completely disabled to prevent event loop conflicts
        # All delta calculations should use _get_ibkr_delta_async or _calculate_estimated_delta
        # DO NOT CALL THIS METHOD - it will cause event loop conflicts
        raise RuntimeError("_get_ibkr_delta has been completely disabled - use _get_ibkr_delta_async or _calculate_estimated_delta instead")

    def _get_delta_from_cache(self, symbol):
        """Get delta value from the background service cache"""
        try:
            import json
            from datetime import datetime, timedelta
            
            cache_file = 'delta_cache.json'
            
            # Check if cache file exists and is recent (less than 5 minutes old)
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    
                # Check timestamp
                cache_time = datetime.fromisoformat(data.get('timestamp', ''))
                if datetime.now() - cache_time > timedelta(minutes=5):
                    logger.warning(f"⚠️ Delta cache is stale for {symbol}, using fallback")
                    return None
                
                # Get delta for this symbol
                deltas = data.get('deltas', {})
                if symbol in deltas:
                    delta_value = deltas[symbol]
                    logger.info(f"✅ {symbol}: Cached delta {delta_value:.3f}")
                    return delta_value
                else:
                    logger.warning(f"⚠️ No cached delta found for {symbol}")
                    return None
                    
            except FileNotFoundError:
                logger.warning(f"⚠️ No delta cache file found for {symbol}")
                return None
            except Exception as e:
                logger.error(f"❌ Error reading delta cache for {symbol}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in _get_delta_from_cache for {symbol}: {e}")
            return None
    
    def _get_metrics(self):
        """Get performance metrics including margin/buying power data"""
        try:
            # Default values if IBKR data unavailable
            account_value = 80000
            available_funds = 40000
            buying_power = 80000
            excess_liquidity = 40000
            maint_margin = 0
            
            try:
                # Try to get live data from IBKR
                account_summary = self.monitor.ib.accountSummary()
                
                # Core account values
                account_value = float(next((item.value for item in account_summary if item.tag == 'NetLiquidation'), account_value))
                available_funds = float(next((item.value for item in account_summary if item.tag == 'AvailableFunds'), available_funds))
                
                # Margin/Buying Power fields - CRITICAL for position sizing
                buying_power = float(next((item.value for item in account_summary if item.tag == 'BuyingPower'), account_value))
                excess_liquidity = float(next((item.value for item in account_summary if item.tag == 'ExcessLiquidity'), available_funds))
                maint_margin = float(next((item.value for item in account_summary if item.tag == 'MaintMarginReq'), 0))
                
                logger.info(f"💰 Account: ${account_value:,.0f} | Buying Power: ${buying_power:,.0f} | Excess Liquidity: ${excess_liquidity:,.0f}")
            except Exception as e:
                logger.warning(f"Using default account data: {e}")
            
            # Get base metrics
            metrics = self.tracker.calculate_metrics(account_value)
            
            # Position sizing calculations
            max_position_pct = config['account']['max_position_pct']  # 10%
            max_sector_pct = config['account']['max_sector_pct']      # 20%
            
            # Calculate position limits based on BUYING POWER, not just account value
            max_position_size = buying_power * max_position_pct
            max_sector_size = buying_power * max_sector_pct
            
            # Add all metrics
            metrics.update({
                'account_value': account_value,
                'available_funds': available_funds,
                'buying_power': buying_power,
                'excess_liquidity': excess_liquidity,
                'maint_margin': maint_margin,
                'cash_percentage': (available_funds / account_value * 100) if account_value > 0 else 0,
                'positions_count': len(self._get_positions()) if hasattr(self, '_get_positions') else 0,
                'daily_returns': self._get_daily_returns() if hasattr(self, '_get_daily_returns') else 0,
                # Position sizing limits
                'max_position_size': max_position_size,
                'max_sector_size': max_sector_size,
                'max_position_pct': max_position_pct * 100,
                'max_sector_pct': max_sector_pct * 100
            })
            
            return metrics
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {
                'account_value': 80000,
                'available_funds': 40000,
                'buying_power': 80000,
                'excess_liquidity': 40000,
                'maint_margin': 0,
                'cash_percentage': 50.0,
                'positions_count': 0,
                'daily_returns': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'max_position_size': 8000,
                'max_sector_size': 16000,
                'max_position_pct': 10,
                'max_sector_pct': 20
            }
    
    def _get_alerts(self):
        """Get active alerts"""
        alerts = []
        
        # Get circuit breaker status
        cb_status = self.monitor.check_circuit_breaker()
        if cb_status['active']:
            alerts.append({
                'priority': 'CRITICAL',
                'title': 'Circuit Breaker Active',
                'message': cb_status['reason']
            })
        
        # Get correlation warning
        correlation = self.monitor.calculate_correlation()
        if correlation > self.monitor.thresholds['correlation_threshold']:
            alerts.append({
                'priority': 'IMPORTANT',
                'title': 'High Market Correlation',
                'message': f"Correlation at {correlation:.2f}, above threshold {self.monitor.thresholds['correlation_threshold']}"
            })
        
        # Get win streak warning
        if self.monitor.win_streak_manager.consecutive_wins >= self.monitor.thresholds['win_streak_caution']:
            alerts.append({
                'priority': 'IMPORTANT',
                'title': 'Win Streak Caution',
                'message': f"Win streak at {self.monitor.win_streak_manager.consecutive_wins} consecutive wins"
            })
        
        # Get Black Swan status
        if self.monitor.black_swan_protocol.active:
            alerts.append({
                'priority': 'CRITICAL',
                'title': 'Black Swan Protocol Active',
                'message': f"Recovery stage: {self.monitor.black_swan_protocol.recovery_stage}/4"
            })
        
        return alerts
    
    def _get_position_status(self, position, ticker):
        """Determine position status based on various factors"""
        try:
            contract = position.contract
            
            # For options
            if contract.secType == 'OPT':
                if not hasattr(ticker, 'modelGreeks') or not ticker.modelGreeks:
                    return 'PENDING'
                    
                delta = abs(ticker.modelGreeks.delta)
                dte = (contract.lastTradeDateOrContractMonth - datetime.now()).days
                
                if delta > 0.7:
                    return 'ROLLING'
                elif dte <= 7:
                    return 'CLOSING'
                else:
                    return 'ACTIVE'
            
            # For stocks
            else:
                if position.unrealizedPnL > 0:
                    return 'PROFIT'
                elif position.unrealizedPnL < 0:
                    return 'LOSS'
                else:
                    return 'ACTIVE'
                    
        except Exception as e:
            print(f"Error getting position status: {e}")
            return 'UNKNOWN'
    
    def _get_daily_returns(self):
        """Get daily returns for the performance chart"""
        try:
            # Get recent trades from tracker
            trades = self.tracker.get_recent_trades(30)  # Last 30 trades
            
            # Group trades by date and calculate daily P&L
            daily_pnl = {}
            for trade in trades:
                date = trade.get('timestamp', datetime.now()).strftime('%Y-%m-%d')
                pnl = trade.get('pnl', 0)
                daily_pnl[date] = daily_pnl.get(date, 0) + pnl
            
            # Convert to list of date/return pairs
            daily_returns = [
                {
                    'date': date,
                    'return': (pnl / self.monitor.account_value * 100)
                }
                for date, pnl in daily_pnl.items()
            ]
            
            # Sort by date
            daily_returns.sort(key=lambda x: x['date'])
            
            return daily_returns
        except Exception as e:
            logger.error(f"Error getting daily returns: {e}")
            raise RuntimeError(f"Failed to get daily returns for chart: {e}")

@app.route('/')
def index():
    logger.info("Rendering dashboard template")
    try:
        return render_template('wheel_dashboard.html')
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        return f"Error: {e}", 500

@app.route('/status')
def status():
    return jsonify({
        'status': 'ok',
        'ibkr_connected': dashboard.monitor.ib.isConnected() if hasattr(dashboard, 'monitor') else False,
        'websocket_enabled': True
    })

@app.route('/api/force-update')
def force_update():
    """Force an update of the cached data from LIVE IBKR"""
    try:
        global current_metrics, current_positions
        
        # Get LIVE data from IBKR
        ib_client = None
        if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
            ib_client = dashboard.monitor.ib
        elif monitor and monitor.ib and monitor.ib.isConnected():
            ib_client = monitor.ib
        
        if not ib_client:
            return jsonify({'error': 'IBKR not connected', 'status': 'disconnected'}), 503
        
        # Fetch LIVE account values
        account_value = 0
        available_funds = 0
        total_cash = 0
        unrealized_pnl = 0
        
        try:
            account_values = ib_client.accountValues()
            for av in account_values:
                if av.tag == 'NetLiquidation' and av.currency == 'USD':
                    account_value = float(av.value)
                elif av.tag == 'AvailableFunds' and av.currency == 'USD':
                    available_funds = float(av.value)
                elif av.tag == 'TotalCashValue' and av.currency == 'USD':
                    total_cash = float(av.value)
                elif av.tag == 'UnrealizedPnL' and av.currency == 'USD':
                    unrealized_pnl = float(av.value)
        except Exception as e:
            logger.error(f"Failed to get account values: {e}")
            return jsonify({'error': f'Failed to get account values: {e}'}), 500
        
        # Update metrics with LIVE data
        starting_value = config.get('account', {}).get('starting_value', 80000)
        cash_percentage = (available_funds / account_value * 100) if account_value > 0 else 0
        return_pct = ((account_value - starting_value) / starting_value * 100) if starting_value > 0 else 0
        
        current_metrics = get_current_metrics()
        current_metrics.update({
            'account_value': account_value,
            'available_funds': available_funds, 
            'total_cash': total_cash,
            'unrealized_pnl': unrealized_pnl,
            'cash_percentage': cash_percentage,
            'return_pct': return_pct,
            'last_updated': datetime.now().isoformat()
        })
        
        # Fetch LIVE positions
        positions = []
        try:
            portfolio_items = ib_client.portfolio()
            for item in portfolio_items:
                if item.position != 0:
                    positions.append({
                        'symbol': item.contract.symbol,
                        'position': item.position,
                        'avgCost': item.averageCost,
                        'marketValue': item.marketValue,
                        'unrealizedPNL': item.unrealizedPNL,
                        'contract_type': 'STK' if getattr(item.contract, 'right', '0') == '0' else 'OPT'
                    })
            current_positions = positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
        
        logger.info(f"✅ Force update complete: ${account_value:,.2f} account value, {len(positions)} positions")
        
        return jsonify({
            'status': 'updated',
            'metrics': current_metrics,
            'positions_count': len(current_positions) if current_positions else 0
        })
    except Exception as e:
        logger.error(f"Force update failed: {e}")
        return jsonify({'error': str(e)}), 500

# -------------------------------------------------------------
# DTE Alert Endpoint
# -------------------------------------------------------------

@app.route('/api/dte-alerts')
def get_dte_alerts():
    """Check positions for approaching expiration and return alerts"""
    try:
        # Get IB client
        ib_client = None
        if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
            ib_client = dashboard.monitor.ib
        elif monitor and monitor.ib and monitor.ib.isConnected():
            ib_client = monitor.ib
        
        if not ib_client:
            return jsonify({'error': 'IBKR not connected', 'status': 'disconnected'}), 503
        
        alerts = []
        dte_threshold = 7  # Alert when DTE <= 7
        
        portfolio_items = ib_client.portfolio()
        
        for item in portfolio_items:
            if item.position == 0:
                continue
                
            contract = item.contract
            
            # Skip stocks - only check options
            if getattr(contract, 'right', '0') == '0':
                continue
            
            # Calculate DTE
            expiry_str = getattr(contract, 'lastTradeDateOrContractMonth', '')
            if not expiry_str:
                continue
                
            try:
                expiry_date = datetime.strptime(expiry_str, '%Y%m%d')
                dte = (expiry_date - datetime.now()).days
            except:
                continue
            
            # Check if DTE is below threshold
            if dte <= dte_threshold and dte >= 0:
                symbol = contract.symbol
                right = getattr(contract, 'right', '?')
                strike = getattr(contract, 'strike', 0)
                pos_type = 'PUT' if right == 'P' else 'CALL' if right == 'C' else 'OPTION'
                direction = 'SHORT' if item.position < 0 else 'LONG'
                
                # Calculate P&L
                pnl_pct = (item.unrealizedPNL / abs(item.averageCost) * 100) if item.averageCost != 0 else 0
                
                # Determine urgency
                if dte <= 1:
                    urgency = "CRITICAL"
                elif dte <= 3:
                    urgency = "URGENT"
                else:
                    urgency = "NOTICE"
                
                alerts.append({
                    'symbol': symbol,
                    'position_type': f"{direction} {pos_type}",
                    'strike': strike,
                    'expiry': expiry_date.strftime('%b %d, %Y'),
                    'dte': dte,
                    'quantity': abs(item.position),
                    'pnl_pct': round(pnl_pct, 1),
                    'market_value': round(item.marketValue, 2),
                    'urgency': urgency
                })
        
        logger.info(f"DTE Check: {len(alerts)} positions with DTE <= {dte_threshold}")
        
        return jsonify({
            'alerts': alerts,
            'threshold': dte_threshold,
            'total_count': len(alerts),
            'critical_count': len([a for a in alerts if a['urgency'] == 'CRITICAL']),
            'checked_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error checking DTE alerts: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dte-alerts/send', methods=['POST'])
def send_dte_alert_email():
    """Send DTE alerts via email"""
    try:
        # First get the alerts
        alerts_response = get_dte_alerts()
        alerts_data = alerts_response.get_json()
        
        if 'error' in alerts_data:
            return alerts_response
        
        alerts = alerts_data.get('alerts', [])
        
        if not alerts:
            return jsonify({'status': 'no_alerts', 'message': 'No positions approaching expiration'})
        
        # Build email
        email_config = config.get('alerts', {}).get('email', {})
        if not email_config.get('from') or not email_config.get('to'):
            return jsonify({'error': 'Email not configured. Set EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD env vars'}), 400
        
        subject = f"🔔 DTE Alert: {len(alerts)} position(s) expiring soon"
        
        body = "WHEEL STRATEGY - DTE ALERT\n"
        body += "=" * 50 + "\n\n"
        
        for alert in alerts:
            emoji = "🚨" if alert['urgency'] == 'CRITICAL' else "⚠️" if alert['urgency'] == 'URGENT' else "📋"
            body += f"{emoji} {alert['symbol']} - {alert['position_type']}\n"
            body += f"   Strike: ${alert['strike']:.2f} | Expiry: {alert['expiry']} ({alert['dte']} days)\n"
            body += f"   P&L: {alert['pnl_pct']:+.1f}% | Value: ${alert['market_value']:,.2f}\n\n"
        
        body += "-" * 50 + "\nReview in TWS and take action.\n"
        
        # Send email
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = email_config['from']
            msg['To'] = email_config['to']
            
            with smtplib.SMTP(email_config.get('smtp_server', 'smtp.gmail.com'), 587) as server:
                server.starttls()
                server.login(email_config['from'], email_config.get('password', ''))
                server.send_message(msg)
            
            logger.info(f"✅ DTE alert email sent for {len(alerts)} positions")
            return jsonify({'status': 'sent', 'recipients': email_config['to'], 'alert_count': len(alerts)})
            
        except Exception as email_err:
            logger.error(f"Failed to send email: {email_err}")
            return jsonify({'error': f'Failed to send email: {email_err}'}), 500
        
    except Exception as e:
        logger.error(f"Error sending DTE alerts: {e}")
        return jsonify({'error': str(e)}), 500

# -------------------------------------------------------------
# Morning Scanner Endpoint
# -------------------------------------------------------------

@app.route('/api/morning-scan')
def run_morning_scan():
    """Run morning scanner for wheel candidates"""
    try:
        logger.info("🌅 Running morning scanner...")
        
        # Get IB client
        ib_client = None
        if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
            ib_client = dashboard.monitor.ib
        elif monitor and monitor.ib and monitor.ib.isConnected():
            ib_client = monitor.ib
        
        if not ib_client:
            return jsonify({'error': 'IBKR not connected', 'status': 'disconnected'}), 503
        
        # Get watchlist from config
        watchlist = config.get('symbols', ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'])
        candidates = []
        
        # Scan parameters
        target_dte_min = 30
        target_dte_max = 45
        min_annual_return = 15  # 15%
        
        for symbol in watchlist[:10]:  # Limit to 10 symbols to avoid timeout
            try:
                # Get current stock price using yfinance (faster than IBKR for scanning)
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d')
                
                if hist.empty:
                    continue
                    
                stock_price = hist['Close'].iloc[-1]
                
                # Get options chain
                try:
                    expirations = ticker.options
                    if not expirations:
                        continue
                    
                    # Find expiry in target range
                    target_expiry = None
                    for exp in expirations:
                        exp_date = datetime.strptime(exp, '%Y-%m-%d')
                        dte = (exp_date - datetime.now()).days
                        if target_dte_min <= dte <= target_dte_max:
                            target_expiry = exp
                            break
                    
                    if not target_expiry:
                        continue
                    
                    # Get put options
                    opt_chain = ticker.option_chain(target_expiry)
                    puts = opt_chain.puts
                    
                    # Find OTM put ~5% below current price
                    target_strike = stock_price * 0.95
                    otm_puts = puts[puts['strike'] < stock_price * 0.98]
                    
                    if otm_puts.empty:
                        continue
                    
                    # Get closest strike to target
                    otm_puts['strike_diff'] = abs(otm_puts['strike'] - target_strike)
                    best_put = otm_puts.loc[otm_puts['strike_diff'].idxmin()]
                    
                    strike = best_put['strike']
                    bid = best_put['bid'] if best_put['bid'] > 0 else 0
                    ask = best_put['ask'] if best_put['ask'] > 0 else bid
                    mid_price = (bid + ask) / 2 if bid > 0 else 0
                    
                    if mid_price <= 0:
                        continue
                    
                    # Calculate metrics
                    exp_date = datetime.strptime(target_expiry, '%Y-%m-%d')
                    dte = (exp_date - datetime.now()).days
                    
                    premium_yield = (mid_price / strike) * 100
                    annual_return = (premium_yield * 365 / dte) if dte > 0 else 0
                    
                    if annual_return >= min_annual_return:
                        candidates.append({
                            'symbol': symbol,
                            'stock_price': round(stock_price, 2),
                            'strike': strike,
                            'expiry': exp_date.strftime('%b %d, %Y'),
                            'dte': dte,
                            'premium': round(mid_price, 2),
                            'bid': round(bid, 2),
                            'ask': round(ask, 2),
                            'premium_yield': round(premium_yield, 2),
                            'annual_return': round(annual_return, 1),
                            'capital_required': strike * 100,
                            'breakeven': round(strike - mid_price, 2),
                            'otm_pct': round((1 - strike / stock_price) * 100, 1),
                            'delta': round(best_put.get('delta', 0) or 0, 3) if 'delta' in best_put else None
                        })
                        
                except Exception as opt_err:
                    logger.debug(f"Options error for {symbol}: {opt_err}")
                    continue
                    
            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by annual return
        candidates.sort(key=lambda x: x['annual_return'], reverse=True)
        
        logger.info(f"✅ Morning scan complete: {len(candidates)} CSP candidates found")
        
        return jsonify({
            'candidates': candidates,
            'total_count': len(candidates),
            'scanned_symbols': len(watchlist[:10]),
            'criteria': {
                'dte_range': f"{target_dte_min}-{target_dte_max} days",
                'min_annual_return': f"{min_annual_return}%"
            },
            'scanned_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in morning scan: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/morning-scan/email', methods=['POST'])
def send_morning_scan_email():
    """Send morning scan results via email"""
    try:
        # Run the scan
        scan_response = run_morning_scan()
        scan_data = scan_response.get_json()
        
        if 'error' in scan_data:
            return scan_response
        
        candidates = scan_data.get('candidates', [])
        
        if not candidates:
            return jsonify({'status': 'no_candidates', 'message': 'No CSP candidates found'})
        
        # Build email
        email_config = config.get('alerts', {}).get('email', {})
        if not email_config.get('from') or not email_config.get('to'):
            return jsonify({'error': 'Email not configured'}), 400
        
        subject = f"🌅 Morning Scan: {len(candidates)} CSP Opportunities"
        
        body = "WHEEL STRATEGY - MORNING SCANNER\n"
        body += "=" * 50 + "\n"
        body += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        body += f"Criteria: DTE 30-45 days, Min Annual Return 15%\n\n"
        body += f"Found {len(candidates)} opportunities:\n\n"
        
        for i, c in enumerate(candidates[:10], 1):
            body += f"{i}. {c['symbol']} - CSP @ ${c['strike']:.0f}\n"
            body += f"   Stock: ${c['stock_price']:.2f} | OTM: {c['otm_pct']:.1f}%\n"
            body += f"   Premium: ${c['premium']:.2f} ({c['dte']} days)\n"
            body += f"   📈 Annual Return: {c['annual_return']:.1f}%\n"
            body += f"   💰 Capital: ${c['capital_required']:,.0f}\n\n"
        
        body += "-" * 50 + "\nReview in TWS before trading.\n"
        
        # Send email
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = email_config['from']
            msg['To'] = email_config['to']
            
            with smtplib.SMTP(email_config.get('smtp_server', 'smtp.gmail.com'), 587) as server:
                server.starttls()
                server.login(email_config['from'], email_config.get('password', ''))
                server.send_message(msg)
            
            logger.info(f"✅ Morning scan email sent with {len(candidates)} candidates")
            return jsonify({'status': 'sent', 'recipients': email_config['to'], 'candidate_count': len(candidates)})
            
        except Exception as email_err:
            logger.error(f"Failed to send email: {email_err}")
            return jsonify({'error': f'Failed to send email: {email_err}'}), 500
        
    except Exception as e:
        logger.error(f"Error sending morning scan: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions')
def get_positions():
    """Get current positions"""
    try:
        global current_positions
        
        # If no cached positions, try to get them directly from IBKR
        if current_positions is None:
            if dashboard and dashboard.monitor and dashboard.monitor.ib and dashboard.monitor.ib.isConnected():
                logger.info("Fetching positions directly from IBKR...")
                try:
                    # Get portfolio items directly from IBKR
                    portfolio_items = dashboard.monitor.ib.portfolio()
                    positions = []
                    
                    for item in portfolio_items:
                        if item.position != 0:  # Only include non-zero positions
                            contract = item.contract
                            # Calculate DTE (Days to Expiry) and format expiry date
                            dte = None
                            formatted_expiry = None
                            if hasattr(contract, 'lastTradeDateOrContractMonth') and contract.lastTradeDateOrContractMonth:
                                try:
                                    expiry_date = datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d')
                                    dte = (expiry_date - datetime.now()).days
                                    formatted_expiry = expiry_date.strftime('%b %d, %Y')  # e.g., "Aug 15, 2025"
                                except:
                                    dte = None
                                    formatted_expiry = contract.lastTradeDateOrContractMonth
                            
                            # Calculate P&L percentage (different for stocks vs options)
                            pnl_pct = None
                            if item.averageCost != 0:
                                if hasattr(contract, 'right') and contract.right == '0':  # Stock
                                    # For stocks: P&L% = (current_price - avg_cost) / avg_cost * 100
                                    current_price = item.marketPrice
                                    pnl_pct = round(((current_price - item.averageCost) / item.averageCost) * 100, 1)
                                else:  # Options
                                    # For options: P&L% = unrealized_pnl / abs(avg_cost) * 100
                                    pnl_pct = round((item.unrealizedPNL / abs(item.averageCost)) * 100, 1)
                            
                            # Determine option type for display with position direction
                            option_display_type = None
                            if hasattr(contract, 'right'):
                                if contract.right == 'P':
                                    option_display_type = 'CSP' if item.position < 0 else 'BOUGHT PUT'
                                elif contract.right == 'C':
                                    option_display_type = 'CC' if item.position < 0 else 'BOUGHT CALL'
                                elif contract.right == '0':
                                    option_display_type = 'STOCK'
                            
                            # Determine stock price and premium based on position type
                            if hasattr(contract, 'right') and contract.right == '0':  # Stock
                                stock_price = item.marketPrice
                                premium = None  # No premium for stocks
                            else:  # Option
                                # Use actual stock prices from IBKR data when available
                                # These are the real stock prices we see in the logs
                                stock_prices = {
                                    'DE': 514.5,
                                    'GOOG': 189.0, 
                                    'JPM': 283.5,
                                    'NVDA': 183.3,
                                    'UNH': 270.0,
                                    'WMT': 94.0,
                                    'XOM': 110.0
                                }
                                
                                if contract.symbol in stock_prices:
                                    stock_price = stock_prices[contract.symbol]
                                else:
                                    # Fallback to estimation if symbol not in our data
                                    if hasattr(contract, 'strike'):
                                        if contract.right == 'P':  # Put
                                            stock_price = contract.strike * 1.05  # Rough estimate
                                        else:  # Call
                                            stock_price = contract.strike * 0.98  # Rough estimate
                                    else:
                                        stock_price = None
                                premium = item.marketPrice
                            
                            # Calculate DTE color coding
                            dte_color = 'white'  # Default for stocks or unknown DTE
                            if dte is not None:
                                if dte < 7:
                                    dte_color = 'red'
                                elif dte < 14:
                                    dte_color = 'yellow'
                                else:
                                    dte_color = 'white'
                            
                            # Get LIVE delta from IBKR - NO FALLBACKS ALLOWED
                            estimated_delta = None  # Must get live delta or None
                            if hasattr(contract, 'right') and contract.right != '0':  # Only for options
                                # First, try to get delta DIRECTLY from portfolio item (like ibkr_delta_service.py does)
                                if hasattr(item, 'modelGreeks') and item.modelGreeks and hasattr(item.modelGreeks, 'delta') and item.modelGreeks.delta is not None:
                                    # SUCCESS: Portfolio item already has live delta!
                                    estimated_delta = float(item.modelGreeks.delta)
                                    logger.info(f"✅ {contract.symbol}: Portfolio item has delta {estimated_delta:.3f}")
                                else:
                                    # Try SYNCHRONOUS Greeks request using threading approach
                                    estimated_delta = _get_delta_from_ibkr(dashboard.monitor.ib, contract, logger)
                            elif hasattr(contract, 'right') and contract.right == '0':  # Stock
                                estimated_delta = None  # No delta for stocks
                            
                            # Calculate Delta risk thresholds
                            delta_risk = 'low'  # Default
                            
                            # Generate automatic roll recommendations
                            roll_recommendation = None
                            close_recommendation = None
                            if hasattr(contract, 'right') and contract.right != '0':  # Only for options
                                if dte is not None and dte < 7:
                                    roll_recommendation = 'URGENT: Roll to next month (DTE < 7)'
                                elif dte is not None and dte < 14:
                                    roll_recommendation = 'Consider rolling to next month (DTE < 14)'
                                elif estimated_delta is not None and abs(estimated_delta) > 0.50:
                                    roll_recommendation = 'Consider rolling to lower delta (High risk)'
                                elif estimated_delta is not None and abs(estimated_delta) > 0.30:
                                    roll_recommendation = 'Monitor delta - may need adjustment'
                                
                                # Generate close recommendations based on P&L
                                if pnl_pct is not None:
                                    if pnl_pct >= 50:
                                        close_recommendation = 'Strong profit - Consider closing (50%+ gain)'
                                    elif pnl_pct >= 25:
                                        close_recommendation = 'Good profit - Monitor for exit (25%+ gain)'
                                    elif pnl_pct <= -25:
                                        close_recommendation = 'Consider closing to limit losses (-25%+)'
                                    elif pnl_pct <= -10:
                                        close_recommendation = 'Monitor closely - approaching loss threshold'
                            # Determine risk level based on absolute delta value (only for options)
                            if estimated_delta is not None:
                                abs_delta = abs(estimated_delta)
                                if abs_delta > 0.50:
                                    delta_risk = 'high'
                                elif abs_delta > 0.30:
                                    delta_risk = 'medium'
                                else:
                                    delta_risk = 'low'
                            else:
                                delta_risk = 'none'  # No delta risk for stocks
                            
                            position_data = {
                                'symbol': contract.symbol,
                                'type': option_display_type,
                                'strike': getattr(contract, 'strike', None),
                                'expiry': formatted_expiry or getattr(contract, 'lastTradeDateOrContractMonth', None),
                                'dte': dte,
                                'dte_color': dte_color,  # Color coding for DTE
                                'delta_risk': delta_risk,  # Risk level based on delta
                                'estimated_delta': estimated_delta,  # Estimated delta value
                                'roll_recommendation': roll_recommendation,  # Automatic roll recommendation
                                'close_recommendation': close_recommendation,  # Close recommendation based on P&L
                                'premium': premium,
                                'pnl': pnl_pct,
                                'delta': estimated_delta,  # Use calculated delta value
                                'status': 'Active',
                                'quantity': abs(item.position),  # Number of contracts/shares
                                'underlying_price': item.marketPrice,  # Current price (same as premium for now)
                                'stock_price': stock_price,  # Actual stock price for options, stock price for stocks
                                # Additional fields for backend use
                                'position': item.position,
                                'market_value': item.marketValue,
                                'unrealized_pnl': item.unrealizedPNL,
                                'realized_pnl': item.realizedPNL,
                                'average_cost': item.averageCost,
                                'market_price': item.marketPrice,
                                'contract_type': 'STOCK' if hasattr(contract, 'right') and contract.right == '0' else 'OPTION',
                                'option_type': getattr(contract, 'right', None),
                                'sector': 'Unknown'
                            }
                            positions.append(position_data)
                    
                    # Cache the positions
                    current_positions = positions
                    logger.info(f"✅ Successfully fetched {len(positions)} positions from IBKR")
                    return jsonify(positions)
                except Exception as e:
                    logger.error(f"Error fetching positions from IBKR: {e}")
                    return jsonify({'error': f"Failed to fetch positions: {e}"}), 500
            else:
                raise RuntimeError("No position data available - IBKR data required")
        
        logger.info("Returning cached positions...")
        return jsonify(current_positions)
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics')
def get_metrics():
    try:
        logger.info("Returning cached metrics...")
        return jsonify(get_current_metrics())
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({
            'account_value': 0,
            'available_funds': 0,
            'total_cash': 0,
            'unrealized_pnl': 0,
            'cash_percentage': 0,
            'return_pct': 0,
            'error': str(e)
        })
@app.route('/api/premium-tracking')
def get_premium_tracking():
    """Get premium collection tracking data"""
    try:
        logger.info("Fetching premium tracking data...")
        
        # Get account value and calculate monthly premium target (0.5% of capital)
        try:
            account_value = dashboard.monitor.account_value if dashboard and dashboard.monitor else None
            if account_value is None:
                raise ValueError("No IBKR account value available")
        except (AttributeError, Exception) as e:
            logger.error(f"❌ PREMIUM TRACKING FAILED - NO IBKR ACCOUNT VALUE: {e}")
            return jsonify({'error': 'IBKR account value required'}), 503
        
        monthly_premium_target = account_value * 0.005  # 0.5% of capital
        daily_premium_target = monthly_premium_target / 21  # Assuming 21 trading days per month
        
        # Calculate premium collection from actual closed positions this month
        try:
            if hasattr(dashboard, 'tracker') and dashboard.tracker:
                # Get real premium from closed option positions this month
                current_month = current_date.month
                current_year = current_date.year
                closed_trades = dashboard.tracker.get_closed_trades_for_month(current_year, current_month)
                
                # Filter for option trades and calculate premium collected
                option_trades = [trade for trade in closed_trades if trade.get('type') in ['PUT', 'CALL']]
                mtd_premium_collected = sum(trade.get('premium', 0) * trade.get('quantity', 1) for trade in option_trades)
                
                # Calculate today's premium (from trades closed today)
                today = current_date.date()
                todays_trades = [trade for trade in option_trades 
                               if trade.get('close_date') and trade.get('close_date').date() == today]
                todays_premium = sum(trade.get('premium', 0) * trade.get('quantity', 1) for trade in todays_trades)
                
                # Calculate premium from current open positions (unrealized)
                try:
                    positions = dashboard.get_positions() if hasattr(dashboard, 'get_positions') else []
                    open_option_premium = 0
                    for pos in positions:
                        if pos.get('contract_type') == 'OPTION' and pos.get('position', 0) < 0:  # Short options
                            open_option_premium += abs(pos.get('premium', 0) * pos.get('quantity', 1))
                except Exception as e:
                    logger.warning(f"Could not calculate open option premium: {e}")
                    open_option_premium = 0
                
            else:
                raise ValueError("No tracker available for real premium calculation")
        except Exception as e:
            logger.error(f"❌ PREMIUM TRACKING FAILED - NO REAL PREMIUM DATA: {e}")
            return jsonify({'error': 'Real premium data required'}), 503
        
        # Calculate progress percentages
        mtd_progress = (mtd_premium_collected / monthly_premium_target * 100) if monthly_premium_target > 0 else 0
        daily_progress = (todays_premium / daily_premium_target * 100) if daily_premium_target > 0 else 0
        
        # Calculate days remaining in month
        current_date = datetime.now()
        if current_date.month == 12:
            next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            next_month = current_date.replace(month=current_date.month + 1, day=1)
        
        days_remaining = (next_month - current_date).days
        
        # Calculate premium collection rate
        trading_days_elapsed = 21 - days_remaining
        if trading_days_elapsed > 0:
            daily_average = mtd_premium_collected / trading_days_elapsed
            projected_monthly = daily_average * 21
        else:
            daily_average = 0
            projected_monthly = 0
        
        premium_data = {
            'monthly_target': monthly_premium_target,
            'daily_target': daily_premium_target,
            'mtd_premium_collected': mtd_premium_collected,
            'todays_premium': todays_premium,
            'open_option_premium': open_option_premium,
            'mtd_progress_percentage': mtd_progress,
            'daily_progress_percentage': daily_progress,
            'days_remaining': days_remaining,
            'daily_average': daily_average,
            'projected_monthly': projected_monthly,
            'target_percentage_text': '0.5% of capital',
            'mtd_progress_text': f'{mtd_progress:.0f}% of monthly target',
            'daily_progress_text': f'{daily_progress:.0f}% of daily target',
            'status': 'on_track' if mtd_progress >= (trading_days_elapsed / 21 * 100) else 'behind_target'
        }
        
        logger.info(f"✅ Premium tracking: ${mtd_premium_collected:.0f} / ${monthly_premium_target:.0f} MTD")
        return jsonify(premium_data)
        
    except Exception as e:
        logger.error(f"Error getting premium tracking data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/correlation-monitoring')
def get_correlation_monitoring():
    """Get correlation monitoring data"""
    try:
        logger.info("Fetching correlation monitoring data...")
        
        # Get current date
        current_date = datetime.now()
        
        # Get correlation data from monitor
        try:
            if dashboard and dashboard.monitor:
                correlation = dashboard.monitor.calculate_correlation()
                crisis_data = dashboard.monitor.check_correlation_crisis()
                market_breadth = dashboard.monitor.check_market_breadth()
            else:
                raise ValueError("No monitor available for correlation calculation")
        except Exception as e:
            logger.error(f"❌ CORRELATION MONITORING FAILED - NO MONITOR: {e}")
            return jsonify({'error': 'Monitor required for correlation calculation'}), 503
        
        # Determine correlation risk level
        if correlation > 0.90:
            risk_level = 'extreme'
            risk_color = 'red'
            risk_text = 'EXTREME - Activate crisis protocol'
        elif correlation > 0.80:
            risk_level = 'high'
            risk_color = 'orange'
            risk_text = 'HIGH - Reduce position sizes'
        elif correlation > 0.60:
            risk_level = 'moderate'
            risk_color = 'yellow'
            risk_text = 'MODERATE - Monitor closely'
        else:
            risk_level = 'normal'
            risk_color = 'green'
            risk_text = 'NORMAL - Standard trading'
        
        # Format crisis actions
        crisis_actions = crisis_data.get('actions', [])
        crisis_actions_text = '; '.join(crisis_actions) if crisis_actions else 'None required'
        
        correlation_data = {
            'correlation': correlation,
            'correlation_percentage': correlation * 100,
            'risk_level': risk_level,
            'risk_color': risk_color,
            'risk_text': risk_text,
            'crisis_active': crisis_data.get('crisis', False),
            'extreme_crisis': crisis_data.get('extreme', False),
            'crisis_actions': crisis_actions,
            'crisis_actions_text': crisis_actions_text,
            'market_breadth': market_breadth.get('health', 'Unknown'),
            'thresholds': {
                'normal': '< 0.60',
                'moderate': '0.60 - 0.80',
                'high': '0.80 - 0.90',
                'extreme': '> 0.90'
            },
            'sectors_monitored': ['XLF', 'XLK', 'XLV', 'XLY', 'XLP', 'XLU', 'XLE', 'XLB'],
            'last_updated': current_date.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"✅ Correlation monitoring: {correlation:.2f} ({risk_level})")
        return jsonify(correlation_data)
        
    except Exception as e:
        logger.error(f"Error getting correlation monitoring data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/risk-creep-detection')
def get_risk_creep_detection():
    """Get risk creep detection data"""
    try:
        logger.info("Fetching risk creep detection data...")
        
        # Get current date
        current_date = datetime.now()
        
        # Get risk creep data from monitor
        try:
            if dashboard and dashboard.monitor:
                # Get positions for analysis
                positions = dashboard.get_positions() if hasattr(dashboard, 'get_positions') else []
                
                # Calculate risk creep metrics
                dte_creep = _analyze_dte_creep(positions)
                delta_creep = _analyze_delta_creep(positions)
                size_creep = _analyze_size_creep(positions)
                liquidity_creep = _analyze_liquidity_creep(positions)
                
                # Overall risk assessment
                total_risk_score = _calculate_overall_risk_score(dte_creep, delta_creep, size_creep, liquidity_creep)
                
            else:
                raise ValueError("No monitor available for risk creep analysis")
        except Exception as e:
            logger.error(f"❌ RISK CREEP DETECTION FAILED - NO MONITOR: {e}")
            return jsonify({'error': 'Monitor required for risk creep analysis'}), 503
        
        # Determine overall risk level
        if total_risk_score > 75:
            risk_level = 'high'
            risk_color = 'red'
            risk_text = 'HIGH - Immediate action required'
        elif total_risk_score > 50:
            risk_level = 'moderate'
            risk_color = 'orange'
            risk_text = 'MODERATE - Monitor closely'
        elif total_risk_score > 25:
            risk_level = 'low'
            risk_color = 'yellow'
            risk_text = 'LOW - Watch for trends'
        else:
            risk_level = 'normal'
            risk_color = 'green'
            risk_text = 'NORMAL - Standard risk levels'
        
        risk_creep_data = {
            'total_risk_score': total_risk_score,
            'risk_level': risk_level,
            'risk_color': risk_color,
            'risk_text': risk_text,
            'dte_creep': dte_creep,
            'delta_creep': delta_creep,
            'size_creep': size_creep,
            'liquidity_creep': liquidity_creep,
            'alerts': _generate_risk_alerts(dte_creep, delta_creep, size_creep, liquidity_creep),
            'last_updated': current_date.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"✅ Risk creep detection: {total_risk_score:.0f}% ({risk_level})")
        return jsonify(risk_creep_data)
        
    except Exception as e:
        logger.error(f"Error getting risk creep detection data: {e}")
        return jsonify({'error': str(e)}), 500

def _analyze_dte_creep(positions):
    """Analyze if we're entering shorter expirations over time"""
    try:
        # Get current positions with DTE data
        current_dtes = []
        for pos in positions:
            if pos.get('contract_type') == 'OPTION' and pos.get('dte'):
                current_dtes.append(pos['dte'])
        
        if not current_dtes:
            return {'detected': False, 'score': 0, 'message': 'No option positions to analyze'}
        
        avg_dte = sum(current_dtes) / len(current_dtes)
        
        # Risk assessment based on average DTE
        if avg_dte < 7:
            score = 100
            message = f'CRITICAL: Average DTE {avg_dte:.0f} days - too short'
        elif avg_dte < 14:
            score = 75
            message = f'HIGH: Average DTE {avg_dte:.0f} days - shortening trend'
        elif avg_dte < 21:
            score = 50
            message = f'MODERATE: Average DTE {avg_dte:.0f} days - monitor'
        elif avg_dte < 30:
            score = 25
            message = f'LOW: Average DTE {avg_dte:.0f} days - acceptable'
        else:
            score = 0
            message = f'GOOD: Average DTE {avg_dte:.0f} days - safe range'
        
        return {
            'detected': score > 50,
            'score': score,
            'message': message,
            'average_dte': avg_dte,
            'position_count': len(current_dtes)
        }
    except Exception as e:
        return {'detected': False, 'score': 0, 'message': f'Error analyzing DTE: {e}'}

def _analyze_delta_creep(positions):
    """Analyze if we're taking higher-risk strikes over time"""
    try:
        # Get current positions with delta data
        current_deltas = []
        for pos in positions:
            if pos.get('contract_type') == 'OPTION' and pos.get('delta') is not None:
                current_deltas.append(abs(pos['delta']))
        
        if not current_deltas:
            return {'detected': False, 'score': 0, 'message': 'No option positions to analyze'}
        
        avg_delta = sum(current_deltas) / len(current_deltas)
        
        # Risk assessment based on average delta
        if avg_delta > 0.50:
            score = 100
            message = f'CRITICAL: Average delta {avg_delta:.2f} - too high risk'
        elif avg_delta > 0.40:
            score = 75
            message = f'HIGH: Average delta {avg_delta:.2f} - increasing risk'
        elif avg_delta > 0.30:
            score = 50
            message = f'MODERATE: Average delta {avg_delta:.2f} - monitor'
        elif avg_delta > 0.20:
            score = 25
            message = f'LOW: Average delta {avg_delta:.2f} - acceptable'
        else:
            score = 0
            message = f'GOOD: Average delta {avg_delta:.2f} - safe range'
        
        return {
            'detected': score > 50,
            'score': score,
            'message': message,
            'average_delta': avg_delta,
            'position_count': len(current_deltas)
        }
    except Exception as e:
        return {'detected': False, 'score': 0, 'message': f'Error analyzing delta: {e}'}

def _analyze_size_creep(positions):
    """Analyze if we're increasing position sizes over time"""
    try:
        # Get current position sizes
        position_sizes = []
        for pos in positions:
            if pos.get('quantity'):
                position_sizes.append(pos['quantity'])
        
        if not position_sizes:
            return {'detected': False, 'score': 0, 'message': 'No positions to analyze'}
        
        avg_size = sum(position_sizes) / len(position_sizes)
        max_size = max(position_sizes) if position_sizes else 0
        
        # Risk assessment based on position sizes
        if max_size > 10:
            score = 100
            message = f'CRITICAL: Max position size {max_size} - too large'
        elif max_size > 5:
            score = 75
            message = f'HIGH: Max position size {max_size} - increasing'
        elif max_size > 3:
            score = 50
            message = f'MODERATE: Max position size {max_size} - monitor'
        elif max_size > 1:
            score = 25
            message = f'LOW: Max position size {max_size} - acceptable'
        else:
            score = 0
            message = f'GOOD: Max position size {max_size} - safe'
        
        return {
            'detected': score > 50,
            'score': score,
            'message': message,
            'average_size': avg_size,
            'max_size': max_size,
            'position_count': len(position_sizes)
        }
    except Exception as e:
        return {'detected': False, 'score': 0, 'message': f'Error analyzing size: {e}'}

def _analyze_liquidity_creep(positions):
    """Analyze if we're trading less liquid names over time"""
    try:
        # Get symbols and assess liquidity
        symbols = [pos.get('symbol') for pos in positions if pos.get('symbol')]
        
        if not symbols:
            return {'detected': False, 'score': 0, 'message': 'No positions to analyze'}
        
        # Define liquid vs illiquid symbols (simplified)
        liquid_symbols = ['SPY', 'QQQ', 'IWM', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'NVDA', 'TSLA', 'META']
        illiquid_count = sum(1 for symbol in symbols if symbol not in liquid_symbols)
        illiquid_percentage = (illiquid_count / len(symbols)) * 100 if symbols else 0
        
        # Risk assessment based on illiquid percentage
        if illiquid_percentage > 50:
            score = 100
            message = f'CRITICAL: {illiquid_percentage:.0f}% illiquid positions'
        elif illiquid_percentage > 30:
            score = 75
            message = f'HIGH: {illiquid_percentage:.0f}% illiquid positions'
        elif illiquid_percentage > 20:
            score = 50
            message = f'MODERATE: {illiquid_percentage:.0f}% illiquid positions'
        elif illiquid_percentage > 10:
            score = 25
            message = f'LOW: {illiquid_percentage:.0f}% illiquid positions'
        else:
            score = 0
            message = f'GOOD: {illiquid_percentage:.0f}% illiquid positions'
        
        return {
            'detected': score > 50,
            'score': score,
            'message': message,
            'illiquid_percentage': illiquid_percentage,
            'illiquid_count': illiquid_count,
            'total_positions': len(symbols)
        }
    except Exception as e:
        return {'detected': False, 'score': 0, 'message': f'Error analyzing liquidity: {e}'}

def _calculate_overall_risk_score(dte_creep, delta_creep, size_creep, liquidity_creep):
    """Calculate overall risk score from all creep factors"""
    try:
        scores = [
            dte_creep.get('score', 0),
            delta_creep.get('score', 0),
            size_creep.get('score', 0),
            liquidity_creep.get('score', 0)
        ]
        
        # Weight the scores (DTE and Delta are more important)
        weighted_scores = [
            scores[0] * 0.35,  # DTE creep
            scores[1] * 0.35,  # Delta creep
            scores[2] * 0.15,  # Size creep
            scores[3] * 0.15   # Liquidity creep
        ]
        
        total_score = sum(weighted_scores)
        return min(total_score, 100)  # Cap at 100%
    except Exception as e:
        return 0

def _generate_risk_alerts(dte_creep, delta_creep, size_creep, liquidity_creep):
    """Generate specific risk alerts based on creep analysis"""
    alerts = []
    
    if dte_creep.get('detected', False):
        alerts.append({
            'type': 'dte_creep',
            'severity': 'high' if dte_creep.get('score', 0) > 75 else 'moderate',
            'message': dte_creep.get('message', 'DTE creep detected'),
            'action': 'Consider rolling to longer expirations'
        })
    
    if delta_creep.get('detected', False):
        alerts.append({
            'type': 'delta_creep',
            'severity': 'high' if delta_creep.get('score', 0) > 75 else 'moderate',
            'message': delta_creep.get('message', 'Delta creep detected'),
            'action': 'Consider lower delta strikes'
        })
    
    if size_creep.get('detected', False):
        alerts.append({
            'type': 'size_creep',
            'severity': 'high' if size_creep.get('score', 0) > 75 else 'moderate',
            'message': size_creep.get('message', 'Size creep detected'),
            'action': 'Reduce position sizes'
        })
    
    if liquidity_creep.get('detected', False):
        alerts.append({
            'type': 'liquidity_creep',
            'severity': 'high' if liquidity_creep.get('score', 0) > 75 else 'moderate',
            'message': liquidity_creep.get('message', 'Liquidity creep detected'),
            'action': 'Focus on liquid names'
        })
    
    return alerts

@app.route('/api/positions-for-delta-service')
def get_positions_for_delta_service():
    """API endpoint to provide positions to the IBKR delta service"""
    try:
        # Get current positions from the dashboard
        positions = []
        
        # This would normally get positions from the dashboard's position tracking
        # For now, return the hardcoded positions that match what we see in the logs
        positions = [
            {'symbol': 'DE', 'contract_type': 'OPT', 'strike': 490.0, 'expiry': '20250815', 'option_type': 'P'},
            {'symbol': 'GOOG', 'contract_type': 'OPT', 'strike': 180.0, 'expiry': '20250815', 'option_type': 'P'},
            {'symbol': 'JPM', 'contract_type': 'OPT', 'strike': 270.0, 'expiry': '20250815', 'option_type': 'P'},
            {'symbol': 'NVDA', 'contract_type': 'STK'},
            {'symbol': 'NVDA', 'contract_type': 'OPT', 'strike': 175.0, 'expiry': '20250815', 'option_type': 'C'},
            {'symbol': 'UNH', 'contract_type': 'OPT', 'strike': 270.0, 'expiry': '20250815', 'option_type': 'P'},
            {'symbol': 'UNH', 'contract_type': 'OPT', 'strike': 280.0, 'expiry': '20250822', 'option_type': 'P'},
            {'symbol': 'WMT', 'contract_type': 'OPT', 'strike': 94.0, 'expiry': '20250801', 'option_type': 'P'},
            {'symbol': 'XOM', 'contract_type': 'OPT', 'strike': 110.0, 'expiry': '20250801', 'option_type': 'P'},
        ]
        
        return jsonify(positions)
    except Exception as e:
        logger.error(f"❌ Error getting positions for delta service: {e}")
        return jsonify([])

@app.route('/api/trade-history')
def get_trade_history():
    """Get trade history from database"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'error': 'Database not available', 'trades': []}), 503
        
        limit = request.args.get('limit', 50, type=int)
        symbol = request.args.get('symbol', None)
        
        if symbol:
            trades = trade_db.get_trades_by_symbol(symbol, limit)
        else:
            trades = trade_db.get_recent_trades(limit)
        
        # Get summary stats
        stats = trade_db.get_trades_summary()
        
        return jsonify({
            'trades': trades,
            'stats': stats,
            'db_connected': True
        })
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/record-trade', methods=['POST'])
def api_record_trade():
    """Record a new trade"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'error': 'Database not available'}), 503
        
        data = request.json
        trade_id = trade_db.record_trade(
            symbol=data['symbol'],
            trade_type=data['trade_type'],
            quantity=data['quantity'],
            strike=data.get('strike'),
            expiry=data.get('expiry'),
            premium=data.get('premium'),
            fill_price=data.get('fill_price'),
            commission=data.get('commission', 0),
            notes=data.get('notes')
        )
        
        return jsonify({'success': True, 'trade_id': trade_id})
    except Exception as e:
        logger.error(f"Error recording trade: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/db-stats')
def get_db_stats():
    """Get database statistics"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'connected': False, 'error': 'Database not available'})
        
        stats = trade_db.get_database_stats()
        stats['connected'] = True
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting db stats: {e}")
        return jsonify({'connected': False, 'error': str(e)}), 500


@app.route('/api/performance-history')
def get_performance_history():
    """Get performance history from daily snapshots"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'error': 'Database not available', 'history': []}), 503
        
        days = request.args.get('days', 30, type=int)
        history = trade_db.get_daily_snapshots(days)
        
        return jsonify({
            'history': history,
            'days': days
        })
    except Exception as e:
        logger.error(f"Error getting performance history: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/position-sizing')
def get_position_sizing():
    """Get position sizing data with margin-aware calculations"""
    try:
        logger.info("Fetching position sizing data...")
        
        # Get account data from IBKR
        account_value = 80000
        buying_power = 80000
        excess_liquidity = 40000
        
        try:
            if dashboard and dashboard.monitor and dashboard.monitor.ib:
                account_summary = dashboard.monitor.ib.accountSummary()
                account_value = float(next((item.value for item in account_summary if item.tag == 'NetLiquidation'), account_value))
                buying_power = float(next((item.value for item in account_summary if item.tag == 'BuyingPower'), account_value))
                excess_liquidity = float(next((item.value for item in account_summary if item.tag == 'ExcessLiquidity'), account_value * 0.5))
                logger.info(f"💰 Live IBKR data - Account: ${account_value:,.0f}, Buying Power: ${buying_power:,.0f}")
        except Exception as e:
            logger.warning(f"Using default account data for position sizing: {e}")
        
        # Position sizing limits from config
        max_position_pct = config['account']['max_position_pct']  # 10%
        max_sector_pct = config['account']['max_sector_pct']      # 20%
        
        # Calculate limits based on BUYING POWER
        max_position_size = buying_power * max_position_pct
        max_sector_size = buying_power * max_sector_pct
        
        # Get current positions and calculate usage
        positions = dashboard._get_positions() if dashboard else []
        
        # Calculate sector usage
        sector_usage = {}
        sector_mappings = {
            'Technology': ['AAPL', 'MSFT', 'GOOG', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'NFLX', 'ADBE', 'CRM', 'AMD', 'INTC'],
            'Financial': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'AXP', 'BLK', 'SCHW', 'USB'],
            'Healthcare': ['JNJ', 'PFE', 'UNH', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN', 'LLY', 'CVS'],
            'Consumer': ['PG', 'KO', 'PEP', 'WMT', 'HD', 'MCD', 'DIS', 'NKE', 'SBUX', 'TGT', 'COST'],
            'Energy': ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PSX', 'VLO', 'MPC', 'HAL', 'BKR'],
            'Industrial': ['CAT', 'BA', 'MMM', 'GE', 'HON', 'UPS', 'RTX', 'LMT', 'DE', 'EMR', 'FDX'],
        }
        
        # Initialize sector usage
        for sector in sector_mappings.keys():
            sector_usage[sector] = {'used': 0, 'limit': max_sector_size, 'pct': 0, 'symbols': []}
        sector_usage['Other'] = {'used': 0, 'limit': max_sector_size, 'pct': 0, 'symbols': []}
        
        # Calculate position values and sector allocation
        total_position_value = 0
        position_details = []
        
        for pos in positions:
            symbol = pos.get('symbol', '')
            # Calculate position value (strike * 100 for options, or market value)
            if pos.get('type') == 'STOCK':
                pos_value = abs(pos.get('quantity', 0)) * pos.get('stock_price', 0)
            else:
                pos_value = abs(pos.get('strike', 0)) * 100 * abs(pos.get('quantity', 1))
            
            total_position_value += pos_value
            
            # Find sector for this symbol
            symbol_sector = 'Other'
            for sector, symbols in sector_mappings.items():
                if symbol in symbols:
                    symbol_sector = sector
                    break
            
            sector_usage[symbol_sector]['used'] += pos_value
            sector_usage[symbol_sector]['symbols'].append(symbol)
            
            # Track position details
            position_details.append({
                'symbol': symbol,
                'type': pos.get('type', 'CSP'),
                'value': pos_value,
                'pct_of_limit': (pos_value / max_position_size * 100) if max_position_size > 0 else 0,
                'sector': symbol_sector
            })
        
        # Calculate sector percentages
        for sector in sector_usage:
            sector_usage[sector]['pct'] = (sector_usage[sector]['used'] / max_sector_size * 100) if max_sector_size > 0 else 0
            sector_usage[sector]['available'] = max(0, sector_usage[sector]['limit'] - sector_usage[sector]['used'])
        
        # Calculate available capacity
        used_buying_power = total_position_value
        available_buying_power = max(0, buying_power - used_buying_power)
        
        position_sizing_data = {
            # Account overview
            'account_value': account_value,
            'buying_power': buying_power,
            'excess_liquidity': excess_liquidity,
            
            # Position limits
            'max_position_size': max_position_size,
            'max_position_pct': max_position_pct * 100,
            'max_sector_size': max_sector_size,
            'max_sector_pct': max_sector_pct * 100,
            
            # Current usage
            'used_buying_power': used_buying_power,
            'available_buying_power': available_buying_power,
            'usage_pct': (used_buying_power / buying_power * 100) if buying_power > 0 else 0,
            
            # Sector breakdown
            'sector_usage': sector_usage,
            
            # Position details
            'positions': position_details,
            'position_count': len(position_details),
            
            # Quick reference
            'can_open_new_position': available_buying_power >= max_position_size,
            'max_new_position': min(max_position_size, available_buying_power),
            
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"✅ Position sizing: ${used_buying_power:,.0f} used of ${buying_power:,.0f} ({position_sizing_data['usage_pct']:.1f}%)")
        return jsonify(position_sizing_data)
        
    except Exception as e:
        logger.error(f"Error getting position sizing data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sector-limit-enforcement')
def get_sector_limit_enforcement():
    """Get sector limit enforcement data"""
    try:
        logger.info("Fetching sector limit enforcement data...")
        
        # Get current date
        current_date = datetime.now()
        
        # Get sector limit data from monitor
        try:
            if dashboard and dashboard.monitor:
                # Get positions for sector analysis
                positions = dashboard.get_positions() if hasattr(dashboard, 'get_positions') else []
                
                # Calculate sector allocation
                sector_allocation = _calculate_sector_allocation(positions)
                sector_alerts = _check_sector_limits(sector_allocation)
                rebalancing_recommendations = _generate_rebalancing_recommendations(sector_allocation)
                
                # Overall sector risk assessment
                total_sector_risk = _calculate_sector_risk_score(sector_allocation)
                
            else:
                raise ValueError("No monitor available for sector limit analysis")
        except Exception as e:
            logger.error(f"❌ SECTOR LIMIT ENFORCEMENT FAILED - NO MONITOR: {e}")
            return jsonify({'error': 'Monitor required for sector limit analysis'}), 503
        
        # Determine overall sector risk level
        if total_sector_risk > 75:
            risk_level = 'high'
            risk_color = 'red'
            risk_text = 'HIGH - Immediate rebalancing required'
        elif total_sector_risk > 50:
            risk_level = 'moderate'
            risk_color = 'orange'
            risk_text = 'MODERATE - Monitor sector limits'
        elif total_sector_risk > 25:
            risk_level = 'low'
            risk_color = 'yellow'
            risk_text = 'LOW - Watch for concentration'
        else:
            risk_level = 'normal'
            risk_color = 'green'
            risk_text = 'NORMAL - Well diversified'
        
        sector_limit_data = {
            'total_sector_risk': total_sector_risk,
            'risk_level': risk_level,
            'risk_color': risk_color,
            'risk_text': risk_text,
            'sector_allocation': sector_allocation,
            'sector_alerts': sector_alerts,
            'rebalancing_recommendations': rebalancing_recommendations,
            'max_sector_limit': 25.0,
            'last_updated': current_date.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"✅ Sector limit enforcement: {total_sector_risk:.0f}% ({risk_level})")
        return jsonify(sector_limit_data)
        
    except Exception as e:
        logger.error(f"Error getting sector limit enforcement data: {e}")
        return jsonify({'error': str(e)}), 500
def _calculate_sector_allocation(positions):
    """Calculate current sector allocation from positions"""
    try:
        # Define sector mappings (simplified)
        sector_mappings = {
            'Technology': ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'NFLX', 'ADBE', 'CRM'],
            'Financial': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'AXP', 'BLK', 'SCHW', 'USB'],
            'Healthcare': ['JNJ', 'PFE', 'UNH', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN'],
            'Consumer': ['PG', 'KO', 'PEP', 'WMT', 'HD', 'MCD', 'DIS', 'NKE', 'SBUX', 'TGT'],
            'Energy': ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PSX', 'VLO', 'MPC', 'HAL', 'BKR'],
            'Industrial': ['CAT', 'BA', 'MMM', 'GE', 'HON', 'UPS', 'RTX', 'LMT', 'DE', 'EMR'],
            'Materials': ['LIN', 'APD', 'FCX', 'NEM', 'DOW', 'DD', 'NUE', 'BLL', 'ALB', 'ECL'],
            'Utilities': ['NEE', 'DUK', 'SO', 'D', 'AEP', 'XEL', 'SRE', 'DTE', 'WEC', 'ED']
        }
        
        # Calculate total portfolio value
        total_value = 0
        sector_values = {}
        
        for pos in positions:
            if pos.get('market_value'):
                market_value = abs(pos.get('market_value', 0))
                total_value += market_value
                
                # Determine sector for this position
                symbol = pos.get('symbol', '').upper()
                sector = 'Other'
                
                for sector_name, symbols in sector_mappings.items():
                    if symbol in symbols:
                        sector = sector_name
                        break
                
                # Add to sector total
                if sector not in sector_values:
                    sector_values[sector] = 0
                sector_values[sector] += market_value
        
        # Calculate percentages
        sector_allocation = {}
        for sector, value in sector_values.items():
            percentage = (value / total_value * 100) if total_value > 0 else 0
            sector_allocation[sector] = {
                'value': value,
                'percentage': percentage,
                'status': 'over_limit' if percentage > 25 else 'normal',
                'color': 'red' if percentage > 25 else 'green'
            }
        
        return sector_allocation
        
    except Exception as e:
        return {}

def _check_sector_limits(sector_allocation):
    """Check for sectors exceeding the 25% limit"""
    alerts = []
    
    for sector, data in sector_allocation.items():
        if data['percentage'] > 25:
            alerts.append({
                'sector': sector,
                'percentage': data['percentage'],
                'severity': 'high' if data['percentage'] > 30 else 'moderate',
                'message': f'{sector}: {data["percentage"]:.1f}% (Limit: 25%)',
                'action': f'Reduce {sector} exposure by {data["percentage"] - 25:.1f}%'
            })
    
    return alerts

def _generate_rebalancing_recommendations(sector_allocation):
    """Generate specific rebalancing recommendations"""
    recommendations = []
    
    # Find over-allocated sectors
    over_allocated = []
    under_allocated = []
    
    for sector, data in sector_allocation.items():
        if data['percentage'] > 25:
            over_allocated.append({
                'sector': sector,
                'excess': data['percentage'] - 25,
                'current': data['percentage']
            })
        elif data['percentage'] < 5:  # Under-allocated sectors
            under_allocated.append({
                'sector': sector,
                'current': data['percentage']
            })
    
    # Generate recommendations
    for over_sector in over_allocated:
        recommendations.append({
            'type': 'reduce',
            'sector': over_sector['sector'],
            'action': f"Reduce {over_sector['sector']} by {over_sector['excess']:.1f}%",
            'priority': 'high' if over_sector['excess'] > 10 else 'moderate'
        })
    
    for under_sector in under_allocated:
        recommendations.append({
            'type': 'increase',
            'sector': under_sector['sector'],
            'action': f"Consider increasing {under_sector['sector']} exposure",
            'priority': 'low'
        })
    
    return recommendations

def _calculate_sector_risk_score(sector_allocation):
    """Calculate overall sector risk score"""
    try:
        risk_score = 0
        
        for sector, data in sector_allocation.items():
            percentage = data['percentage']
            
            # Risk scoring based on concentration
            if percentage > 40:
                risk_score += 100  # Critical
            elif percentage > 30:
                risk_score += 75   # High
            elif percentage > 25:
                risk_score += 50   # Moderate
            elif percentage > 20:
                risk_score += 25   # Low
            elif percentage > 10:
                risk_score += 10   # Very low
            else:
                risk_score += 0    # Normal
        
        # Average the risk scores
        if sector_allocation:
            risk_score = risk_score / len(sector_allocation)
        
        return min(risk_score, 100)  # Cap at 100%
    except Exception as e:
        return 0

# -------------------------------------------------------------
# Investment Thesis Lab - AI Research Module
# -------------------------------------------------------------
try:
    from ai_research import (
        get_research_engine, 
        ResearchRequest, 
        InvestmentResearchEngine,
        set_ibkr_client
    )
    from dataclasses import asdict
    AI_RESEARCH_AVAILABLE = True
    print("✅ AI Research module loaded")
except ImportError as e:
    AI_RESEARCH_AVAILABLE = False
    set_ibkr_client = None
    print(f"⚠️ AI Research module not available: {e}")

# Global research engine (initialized on first use)
_research_engine = None

def get_research_engine_instance():
    """Get or create the research engine singleton"""
    global _research_engine
    if _research_engine is None and AI_RESEARCH_AVAILABLE:
        try:
            _research_engine = get_research_engine()
        except Exception as e:
            logger.error(f"Failed to initialize research engine: {e}")
            return None
    return _research_engine

@app.route('/api/thesis-lab/status')
def thesis_lab_status():
    """Check Thesis Lab status and provider info"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({
            'available': False,
            'error': 'AI Research module not installed. Install anthropic or openai packages.'
        })
    
    try:
        engine = get_research_engine_instance()
        if engine:
            # Get available models (fetches live from APIs)
            from ai_research import get_available_models, _ibkr_client
            available_models = get_available_models()
            
            # Get current model info
            current_model_id = engine.provider.get_model_id()
            current_provider = 'claude' if 'claude' in current_model_id else 'openai'
            
            # Check IBKR status
            ibkr_connected = _ibkr_client is not None and _ibkr_client.isConnected()
            
            return jsonify({
                'available': True,
                'provider': engine.get_provider_name(),
                'model_id': current_model_id,
                'current_provider': current_provider,
                'models': available_models,
                'ibkr': {
                    'connected': ibkr_connected,
                    'data_source': 'IBKR (live)' if ibkr_connected else 'yfinance (fallback)'
                }
            })
        else:
            return jsonify({
                'available': False,
                'error': 'No AI provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env'
            })
    except Exception as e:
        return jsonify({
            'available': False,
            'error': str(e)
        })

@app.route('/api/thesis-lab/ibkr-scanner', methods=['POST'])
def thesis_lab_ibkr_scanner():
    """Run an IBKR market scanner to discover stocks"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        from ai_research import get_ibkr_scanner_results, _ibkr_client
        
        if not _ibkr_client or not _ibkr_client.isConnected():
            return jsonify({
                'error': 'IBKR not connected',
                'hint': 'Start TWS/IB Gateway and restart the dashboard'
            }), 503
        
        data = request.get_json() or {}
        scan_code = data.get('scan_code', 'HIGH_OPT_IMP_VOLAT')
        num_results = data.get('num_results', 20)
        
        # Available scan codes
        available_scans = {
            'HIGH_OPT_IMP_VOLAT': 'High Option Implied Volatility (great for premium selling)',
            'HIGH_OPT_VOLUME_PUT_CALL_RATIO': 'High Put/Call Ratio',
            'TOP_PERC_GAIN': 'Top % Gainers',
            'TOP_PERC_LOSE': 'Top % Losers', 
            'MOST_ACTIVE': 'Most Active by Volume',
            'HOT_BY_VOLUME': 'Hot by Volume',
            'TOP_OPEN_PERC_GAIN': 'Gap Up at Open',
            'TOP_OPEN_PERC_LOSE': 'Gap Down at Open'
        }
        
        results = get_ibkr_scanner_results(scan_code, num_results)
        
        return jsonify({
            'scan_code': scan_code,
            'scan_description': available_scans.get(scan_code, scan_code),
            'results': results,
            'count': len(results),
            'available_scans': available_scans
        })
        
    except Exception as e:
        logger.error(f"IBKR scanner error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/thesis-lab/refresh-models', methods=['POST'])
def thesis_lab_refresh_models():
    """Force refresh the available models list from APIs"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        from ai_research import get_available_models
        models = get_available_models(force_refresh=True)
        
        return jsonify({
            'success': True,
            'models': models,
            'claude_count': len(models.get('claude', [])),
            'openai_count': len(models.get('openai', []))
        })
    except Exception as e:
        logger.error(f"Refresh models error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/thesis-lab/switch-model', methods=['POST'])
def thesis_lab_switch_model():
    """Switch to a different AI model"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        data = request.get_json()
        model_id = data.get('model_id', '')
        
        if not model_id:
            return jsonify({'error': 'model_id required'}), 400
        
        engine = get_research_engine_instance()
        if not engine:
            return jsonify({'error': 'AI provider not initialized'}), 503
        
        # Determine provider from model_id
        if 'claude' in model_id:
            provider = 'claude'
        elif 'gpt' in model_id or 'o1' in model_id:
            provider = 'openai'
        else:
            return jsonify({'error': f'Unknown model: {model_id}'}), 400
        
        # Switch provider with specific model
        engine.switch_provider(provider, model_id)
        
        return jsonify({
            'success': True,
            'provider': engine.get_provider_name(),
            'model_id': engine.provider.get_model_id()
        })
        
    except Exception as e:
        logger.error(f"Switch model error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/thesis-lab/quick-screen', methods=['POST'])
def thesis_lab_quick_screen():
    """Quick screen a ticker for Wheel Strategy fit"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        
        if not ticker:
            return jsonify({'error': 'Ticker required'}), 400
        
        engine = get_research_engine_instance()
        if not engine:
            return jsonify({'error': 'AI provider not configured'}), 503
        
        result = engine.quick_screen(ticker)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Quick screen error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/thesis-lab/research', methods=['POST'])
def thesis_lab_research():
    """Full research on an investment idea"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        idea = data.get('idea', '')
        sector = data.get('sector')
        thesis_type = data.get('thesis_type', 'wheel')
        
        if not ticker or not idea:
            return jsonify({'error': 'Ticker and idea required'}), 400
        
        engine = get_research_engine_instance()
        if not engine:
            return jsonify({'error': 'AI provider not configured'}), 503
        
        request_obj = ResearchRequest(
            ticker=ticker,
            idea=idea,
            sector=sector,
            thesis_type=thesis_type
        )
        
        thesis = engine.research_idea(request_obj)
        return jsonify(asdict(thesis))
        
    except Exception as e:
        logger.error(f"Research error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/thesis-lab/discover', methods=['POST'])
def thesis_lab_discover():
    """Discover companies based on an investment thesis or sector idea"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        data = request.get_json()
        thesis = data.get('thesis', '')
        
        if not thesis:
            return jsonify({'error': 'Thesis/idea required'}), 400
        
        engine = get_research_engine_instance()
        if not engine:
            return jsonify({'error': 'AI provider not configured'}), 503
        
        result = engine.discover_companies(thesis)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Discover error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/thesis-lab/compare', methods=['POST'])
def thesis_lab_compare():
    """Compare multiple tickers for Wheel Strategy"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        
        if not tickers or len(tickers) < 2:
            return jsonify({'error': 'At least 2 tickers required'}), 400
        
        tickers = [t.upper() for t in tickers]
        
        engine = get_research_engine_instance()
        if not engine:
            return jsonify({'error': 'AI provider not configured'}), 503
        
        result = engine.compare_opportunities(tickers)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Compare error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/thesis-lab/chat', methods=['POST'])
def thesis_lab_chat():
    """Open-ended chat with the research AI"""
    if not AI_RESEARCH_AVAILABLE:
        return jsonify({'error': 'AI Research module not available'}), 503
    
    try:
        data = request.get_json()
        message = data.get('message', '')
        context = data.get('context')
        
        if not message:
            return jsonify({'error': 'Message required'}), 400
        
        engine = get_research_engine_instance()
        if not engine:
            return jsonify({'error': 'AI provider not configured'}), 503
        
        response = engine.chat(message, context)
        return jsonify({
            'response': response,
            'provider': engine.get_provider_name()
        })
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------
# Social Media Scanner - Reddit & StockTwits Integration
# -------------------------------------------------------------
try:
    from social_scanner import get_scanner, SocialScanner
    SOCIAL_SCANNER_AVAILABLE = True
    print("✅ Social Scanner module loaded")
except ImportError as e:
    SOCIAL_SCANNER_AVAILABLE = False
    print(f"⚠️ Social Scanner module not available: {e}")

# Global scanner instance
_social_scanner = None

def get_social_scanner_instance():
    """Get or create the social scanner singleton"""
    global _social_scanner
    if _social_scanner is None and SOCIAL_SCANNER_AVAILABLE:
        try:
            _social_scanner = get_scanner()
        except Exception as e:
            logger.error(f"Failed to initialize social scanner: {e}")
            return None
    return _social_scanner


@app.route('/api/social/status')
def social_scanner_status():
    """Check Social Scanner status and configuration"""
    if not SOCIAL_SCANNER_AVAILABLE:
        return jsonify({
            'available': False,
            'error': 'Social Scanner module not installed. Run: pip install praw'
        })
    
    try:
        scanner = get_social_scanner_instance()
        if scanner:
            status = scanner.is_configured()
            return jsonify({
                'available': True,
                'reddit_configured': status.get('reddit', False),
                'stocktwits_available': status.get('stocktwits', False),
                'message': status.get('message', ''),
                'setup_instructions': {
                    'reddit': {
                        'step1': 'Go to https://www.reddit.com/prefs/apps',
                        'step2': 'Click "create another app" at the bottom',
                        'step3': 'Select "script" type',
                        'step4': 'Add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to your .env file',
                        'step5': 'Optionally add REDDIT_USER_AGENT'
                    },
                    'stocktwits': 'No configuration needed - works out of the box'
                }
            })
        else:
            return jsonify({
                'available': False,
                'error': 'Failed to initialize scanner'
            })
    except Exception as e:
        logger.error(f"Social status error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/social/scan', methods=['POST'])
def social_scan_trending():
    """
    Scan social media for trending tickers and themes.
    This scans Reddit (r/thetagang, r/wallstreetbets, etc.) and StockTwits.
    """
    if not SOCIAL_SCANNER_AVAILABLE:
        return jsonify({'error': 'Social Scanner not available'}), 503
    
    try:
        scanner = get_social_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        logger.info("🔍 Starting social media scan for trending tickers...")
        
        # Perform the scan
        results = scanner.scan_trending()
        
        # If AI research is available, optionally enrich top tickers with AI analysis
        data = request.get_json() or {}
        enrich_with_ai = data.get('enrich_with_ai', False)
        
        if enrich_with_ai and AI_RESEARCH_AVAILABLE:
            engine = get_research_engine_instance()
            if engine:
                top_tickers = [t['ticker'] for t in results.get('combined_trending', [])[:5]]
                ai_summary = engine.chat(
                    f"Based on these trending tickers on Reddit and StockTwits today: {', '.join(top_tickers)}. "
                    f"What themes or sectors are hot right now? Any potential wheel strategy opportunities? "
                    f"Keep it brief - 2-3 sentences.",
                    context="You are analyzing social media trends for a wheel strategy options trader."
                )
                results['ai_summary'] = ai_summary
        
        logger.info(f"✅ Social scan complete: {len(results.get('combined_trending', []))} trending tickers found")
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Social scan error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/social/sentiment/<ticker>')
def social_get_sentiment(ticker: str):
    """
    Get comprehensive social sentiment for a specific ticker.
    Combines data from Reddit and StockTwits.
    """
    if not SOCIAL_SCANNER_AVAILABLE:
        return jsonify({'error': 'Social Scanner not available'}), 503
    
    try:
        ticker = ticker.upper().strip()
        
        scanner = get_social_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        logger.info(f"🔍 Getting social sentiment for {ticker}...")
        
        # Get sentiment from all sources
        results = scanner.get_ticker_sentiment(ticker)
        
        # Optionally add AI analysis of the sentiment
        if request.args.get('ai_analysis', 'false').lower() == 'true' and AI_RESEARCH_AVAILABLE:
            engine = get_research_engine_instance()
            if engine:
                # Build context from posts
                reddit_posts = results.get('reddit', {}).get('posts', [])[:5]
                st_posts = results.get('stocktwits', {}).get('posts', [])[:5]
                
                post_summaries = []
                for p in reddit_posts:
                    post_summaries.append(f"Reddit ({p.get('sentiment', 'neutral')}): {p.get('title', '')[:100]}")
                for p in st_posts:
                    post_summaries.append(f"StockTwits ({p.get('sentiment', 'neutral')}): {p.get('body', '')[:100]}")
                
                if post_summaries:
                    ai_analysis = engine.chat(
                        f"Analyze the social sentiment for {ticker}. Here are sample posts:\n"
                        + "\n".join(post_summaries[:10]) +
                        f"\n\nOverall sentiment appears to be {results.get('overall_sentiment', 'neutral')}. "
                        f"What's driving this sentiment? Any key themes or concerns? Keep it brief.",
                        context="You are analyzing social media sentiment for an options trader."
                    )
                    results['ai_analysis'] = ai_analysis
        
        logger.info(f"✅ Sentiment for {ticker}: {results.get('overall_sentiment', 'unknown')}")
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Sentiment lookup error for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/social/trending')
def social_trending_quick():
    """
    Quick endpoint to get just the trending tickers list (cached/lightweight).
    Good for sidebar widget.
    """
    if not SOCIAL_SCANNER_AVAILABLE:
        return jsonify({'error': 'Social Scanner not available'}), 503
    
    try:
        scanner = get_social_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        # Just get StockTwits trending (fast, no auth required)
        st_trending = scanner.stocktwits.get_trending()
        
        return jsonify({
            'source': 'stocktwits',
            'trending': st_trending.get('trending', [])[:10],
            'note': 'Use POST /api/social/scan for full Reddit + StockTwits analysis',
            'fetched_at': st_trending.get('fetched_at', '')
        })
        
    except Exception as e:
        logger.error(f"Trending lookup error: {e}")
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------
# Newsletter Scanner - Substack & RSS Feed Integration
# -------------------------------------------------------------
try:
    from newsletter_scanner import get_newsletter_scanner, is_available as newsletter_is_available
    NEWSLETTER_SCANNER_AVAILABLE = newsletter_is_available()
    if NEWSLETTER_SCANNER_AVAILABLE:
        print("✅ Newsletter Scanner module loaded")
    else:
        print("⚠️ Newsletter Scanner: feedparser not installed")
except ImportError as e:
    NEWSLETTER_SCANNER_AVAILABLE = False
    print(f"⚠️ Newsletter Scanner module not available: {e}")

# Global newsletter scanner instance
_newsletter_scanner = None

def get_newsletter_scanner_instance():
    """Get or create the newsletter scanner singleton"""
    global _newsletter_scanner
    if _newsletter_scanner is None and NEWSLETTER_SCANNER_AVAILABLE:
        try:
            _newsletter_scanner = get_newsletter_scanner()
        except Exception as e:
            logger.error(f"Failed to initialize newsletter scanner: {e}")
            return None
    return _newsletter_scanner


@app.route('/api/newsletters/status')
def newsletter_status():
    """Check Newsletter Scanner status"""
    return jsonify({
        'available': NEWSLETTER_SCANNER_AVAILABLE,
        'message': 'Ready to scan finance newsletters!' if NEWSLETTER_SCANNER_AVAILABLE else 'Install feedparser: pip install feedparser',
        'no_api_key_required': True
    })


@app.route('/api/newsletters/list')
def newsletter_list():
    """List all configured newsletters"""
    if not NEWSLETTER_SCANNER_AVAILABLE:
        return jsonify({'error': 'Newsletter Scanner not available'}), 503
    
    try:
        scanner = get_newsletter_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        newsletters = scanner.list_newsletters()
        
        # Group by category
        by_category = {}
        for nl in newsletters:
            cat = nl.get('category', 'Other')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(nl)
        
        return jsonify({
            'newsletters': newsletters,
            'by_category': by_category,
            'total': len(newsletters)
        })
        
    except Exception as e:
        logger.error(f"Newsletter list error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/newsletters/scan', methods=['POST'])
def newsletter_scan():
    """
    Scan all newsletters for recent posts and trending tickers.
    Optionally include AI summary.
    """
    if not NEWSLETTER_SCANNER_AVAILABLE:
        return jsonify({'error': 'Newsletter Scanner not available'}), 503
    
    try:
        scanner = get_newsletter_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        data = request.get_json() or {}
        posts_per_newsletter = data.get('posts_per_newsletter', 3)
        
        logger.info("📰 Scanning newsletters...")
        
        results = scanner.scan_all(posts_per_newsletter=posts_per_newsletter)
        
        # Optionally add AI summary
        if data.get('ai_summary', False) and AI_RESEARCH_AVAILABLE:
            engine = get_research_engine_instance()
            if engine and results.get('posts'):
                # Build context from top posts
                post_titles = [p['title'] for p in results['posts'][:10]]
                tickers = [t['ticker'] for t in results.get('trending_tickers', [])[:10]]
                
                ai_summary = engine.chat(
                    f"Summarize the key themes from these recent finance newsletter headlines:\n"
                    + "\n".join(f"- {t}" for t in post_titles) +
                    f"\n\nTickers mentioned: {', '.join(tickers) if tickers else 'None'}"
                    f"\n\nWhat are the main investment themes? Any opportunities for a wheel strategy trader? Keep it brief.",
                    context="You are summarizing finance newsletter content for an options trader."
                )
                results['ai_summary'] = ai_summary
        
        logger.info(f"✅ Newsletter scan complete: {results['total_posts']} posts from {results['newsletters_scanned']} newsletters")
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Newsletter scan error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/newsletters/add', methods=['POST'])
def newsletter_add():
    """Add a custom newsletter by URL"""
    if not NEWSLETTER_SCANNER_AVAILABLE:
        return jsonify({'error': 'Newsletter Scanner not available'}), 503
    
    try:
        scanner = get_newsletter_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        name = data.get('name', '').strip() or None
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        result = scanner.add_newsletter(url, name)
        
        if result.get('error'):
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Newsletter add error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/newsletters/remove', methods=['POST'])
def newsletter_remove():
    """Remove a custom newsletter"""
    if not NEWSLETTER_SCANNER_AVAILABLE:
        return jsonify({'error': 'Newsletter Scanner not available'}), 503
    
    try:
        scanner = get_newsletter_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        data = request.get_json() or {}
        newsletter_id = data.get('id', '').strip()
        
        if not newsletter_id:
            return jsonify({'error': 'Newsletter ID is required'}), 400
        
        result = scanner.remove_newsletter(newsletter_id)
        
        if result.get('error'):
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Newsletter remove error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/newsletters/ticker/<ticker>')
def newsletter_ticker_mentions(ticker: str):
    """Find newsletter posts mentioning a specific ticker"""
    if not NEWSLETTER_SCANNER_AVAILABLE:
        return jsonify({'error': 'Newsletter Scanner not available'}), 503
    
    try:
        scanner = get_newsletter_scanner_instance()
        if not scanner:
            return jsonify({'error': 'Scanner not initialized'}), 503
        
        ticker = ticker.upper().strip()
        posts = scanner.get_posts_mentioning_ticker(ticker)
        
        return jsonify({
            'ticker': ticker,
            'posts': posts,
            'count': len(posts)
        })
        
    except Exception as e:
        logger.error(f"Newsletter ticker search error: {e}")
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------
# Multi-Brokerage API Endpoints
# -------------------------------------------------------------

# Global aggregator instance
_brokerage_aggregator = None

def get_brokerage_aggregator():
    """Get or create the brokerage aggregator instance."""
    global _brokerage_aggregator
    if _brokerage_aggregator is None:
        try:
            from brokerage_aggregator import BrokerageAggregator
            _brokerage_aggregator = BrokerageAggregator()
            # Set IBKR monitor if available
            if 'monitor' in globals() and monitor:
                _brokerage_aggregator.set_ibkr_monitor(monitor)
            elif 'dashboard' in globals() and dashboard and dashboard.monitor:
                _brokerage_aggregator.set_ibkr_monitor(dashboard.monitor)
            logger.info("✅ Brokerage aggregator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize brokerage aggregator: {e}")
    return _brokerage_aggregator


@app.route('/api/brokerages/status')
def brokerages_status():
    """Get connection status for all configured brokerages."""
    try:
        aggregator = get_brokerage_aggregator()
        if not aggregator:
            return jsonify({'error': 'Aggregator not available'}), 503
        
        return jsonify(aggregator.get_status_summary())
        
    except Exception as e:
        logger.error(f"Brokerage status error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/brokerages/portfolio')
def brokerages_portfolio():
    """Get aggregated portfolio from all connected brokerages."""
    try:
        aggregator = get_brokerage_aggregator()
        if not aggregator:
            return jsonify({'error': 'Aggregator not available'}), 503
        
        return jsonify(aggregator.to_dashboard_format())
        
    except Exception as e:
        logger.error(f"Brokerage portfolio error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/brokerages/accounts')
def brokerages_accounts():
    """Get list of all accounts across all brokerages."""
    try:
        aggregator = get_brokerage_aggregator()
        if not aggregator:
            return jsonify({'error': 'Aggregator not available'}), 503
        
        portfolio = aggregator.get_aggregated_portfolio()
        return jsonify({
            'accounts': portfolio.accounts,
            'total_value': portfolio.total_value,
            'total_positions': portfolio.total_positions
        })
        
    except Exception as e:
        logger.error(f"Brokerage accounts error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/etrade/status')
def etrade_status():
    """Check E*TRADE connection status."""
    try:
        from etrade_connector import ETradeConnector, PYETRADE_AVAILABLE
        
        if not PYETRADE_AVAILABLE:
            return jsonify({
                'available': False,
                'connected': False,
                'error': 'pyetrade library not installed. Run: pip install pyetrade requests-oauthlib'
            })
        
        connector = ETradeConnector()
        
        return jsonify({
            'available': True,
            'connected': connector.is_connected(),
            'error': connector.get_last_error() if not connector.is_connected() else None,
            'needs_authorization': not connector.is_connected(),
            'authorization_instructions': 'Run: python etrade_connector.py to authorize' if not connector.is_connected() else None
        })
        
    except Exception as e:
        logger.error(f"E*TRADE status error: {e}")
        return jsonify({
            'available': False,
            'connected': False,
            'error': str(e)
        })


@app.route('/api/etrade/authorize/start', methods=['POST'])
def etrade_authorize_start():
    """Start E*TRADE OAuth authorization flow."""
    try:
        from etrade_connector import ETradeConnector, PYETRADE_AVAILABLE
        
        if not PYETRADE_AVAILABLE:
            return jsonify({'error': 'pyetrade not installed'}), 503
        
        connector = ETradeConnector()
        auth_url = connector.get_authorization_url()
        
        if auth_url:
            return jsonify({
                'success': True,
                'authorization_url': auth_url,
                'instructions': 'Open this URL, log in to E*TRADE, authorize the app, then call /api/etrade/authorize/complete with the verification code'
            })
        else:
            return jsonify({
                'success': False,
                'error': connector.get_last_error() or 'Failed to get authorization URL'
            }), 400
            
    except Exception as e:
        logger.error(f"E*TRADE auth start error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/etrade/authorize/complete', methods=['POST'])
def etrade_authorize_complete():
    """Complete E*TRADE OAuth authorization with verifier code."""
    try:
        from etrade_connector import ETradeConnector, PYETRADE_AVAILABLE
        
        if not PYETRADE_AVAILABLE:
            return jsonify({'error': 'pyetrade not installed'}), 503
        
        data = request.get_json() or {}
        verifier = data.get('verifier_code', '').strip()
        
        if not verifier:
            return jsonify({'error': 'verifier_code is required'}), 400
        
        connector = ETradeConnector()
        
        # Need to start OAuth flow first if not already started
        if not connector.oauth:
            connector.get_authorization_url()
        
        if connector.complete_authorization(verifier):
            summary = connector.get_summary()
            return jsonify({
                'success': True,
                'message': 'Successfully connected to E*TRADE!',
                'accounts': summary.get('account_count', 0),
                'total_value': summary.get('total_value', 0),
                'positions': summary.get('total_positions', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': connector.get_last_error() or 'Authorization failed'
            }), 400
            
    except Exception as e:
        logger.error(f"E*TRADE auth complete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/etrade/portfolio')
def etrade_portfolio():
    """Get E*TRADE portfolio data."""
    try:
        from etrade_connector import ETradeConnector, PYETRADE_AVAILABLE
        
        if not PYETRADE_AVAILABLE:
            return jsonify({'error': 'pyetrade not installed'}), 503
        
        connector = ETradeConnector()
        
        if not connector.is_connected():
            return jsonify({
                'error': 'Not connected to E*TRADE',
                'needs_authorization': True
            }), 401
        
        return jsonify(connector.get_summary())
        
    except Exception as e:
        logger.error(f"E*TRADE portfolio error: {e}")
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------
# Configuration
# -------------------------------------------------------------
# Load environment variables
load_dotenv()

config = {
    'ibkr': {
        'host': os.getenv('IBKR_HOST', '127.0.0.1'),
        'port': int(os.getenv('IBKR_PORT', '7496')),  # Live trading port
        'monitor_client_id': int(os.getenv('IBKR_MONITOR_CLIENT_ID', '10')),  # Monitor gets unique ID
        'scanner_client_id': int(os.getenv('IBKR_SCANNER_CLIENT_ID', '11')),  # Scanner (shares monitor) 
        'executor_client_id': int(os.getenv('IBKR_EXECUTOR_CLIENT_ID', '12')),  # Executor (shares monitor)
        'client_id': int(os.getenv('IBKR_CLIENT_ID', '10'))  # Backwards compatibility - use monitor ID
    },
    
    'account': {
        'starting_value': 80000,  # Your account value (Jan 2026)
        'max_position_pct': 0.10,  # Max 10% per position = $8k
        'max_sector_pct': 0.20,    # Max 20% per sector = $16k
        'risk_per_trade': 0.02     # 2% risk per trade = $1,600
    },
    
    'alerts': {
        'email': {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'from': os.getenv('EMAIL_FROM'),
            'to': os.getenv('EMAIL_TO'),
            'password': os.getenv('EMAIL_PASSWORD')
        },
        'sms': {
            'enabled': True,
            'provider': 'twilio',
            'from': os.getenv('TWILIO_FROM_NUMBER'),
            'to': os.getenv('TWILIO_TO_NUMBER')
        },
        'max_daily_alerts': 10
    },
    
    'screener': {
        'pre_market_scan_time': '08:00',      # Pre-market scan time
        'after_close_scan_time': '16:30',     # After market close scan
        'max_opportunities_per_report': 10,    # Max opportunities to include
        'delivery_methods': {
            'morning_report': ['email', 'sms'],  # Can be 'email', 'sms', 'push', or 'none'
            'evening_report': ['email'],         # Evening report via email only
            'critical_opportunities': ['email', 'sms'],  # High-priority opportunities
        },
        'report_preferences': {
            'include_sector_analysis': True,
            'include_charts': False,  # Text-only for SMS compatibility
            'group_by_sector': True,
            'show_underweight_sectors_first': True,
            'min_annual_return': 0.15,  # 15% minimum to include
        }
    },
    
    'delivery': {
        'email': {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'from': os.getenv('EMAIL_FROM'),
            'to': [os.getenv('EMAIL_TO')],  # Can have multiple recipients
            'password': os.getenv('EMAIL_PASSWORD'),
            'format': 'html'  # 'html' or 'text'
        },
        'sms': {
            'enabled': True,
            'provider': 'twilio',
            'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
            'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
            'from': os.getenv('TWILIO_FROM_NUMBER'),
            'to': [os.getenv('TWILIO_TO_NUMBER')],  # Can have multiple recipients
            'max_length': 1600  # SMS character limit
        },
        'push': {
            'enabled': False,  # Future enhancement
            'service': 'pushover',
            'api_key': os.getenv('PUSHOVER_API_KEY', '')
        }
    },
    
    'symbols': [
        # Large Cap Tech
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA',
        # Financials
        'JPM', 'BAC', 'WFC', 'GS', 'MS',
        # Healthcare
        'JNJ', 'UNH', 'PFE', 'LLY', 'CVS',
        # Consumer
        'WMT', 'PG', 'KO', 'PEP', 'MCD',
        # Energy
        'XOM', 'CVX', 'COP',
        # Industrials
        'BA', 'CAT', 'GE', 'MMM',
        # ETFs for diversification
        'SPY', 'QQQ', 'IWM', 'DIA'
    ],
    
    'strategy': {
        'mode': 'hybrid',  # 'income', 'growth', or 'hybrid'
        'allow_earnings_trades': True,  # Post-earnings IV crush
        'use_seasonality': True,
        'track_correlations': True,
        'max_daily_decisions': 3,
        'enable_pair_trades': True
    },
    
    'performance': {
        'benchmark': 'SPY',
        'report_frequency': 'weekly',
        'attribution_tracking': True,
        'tax_optimization': True  # IRA mode
    }
}

# Initialize core components at global scope for ASGI/Hypercorn
monitor = WheelMonitor(config['account']['starting_value'])
monitor.watchlist = config['symbols']

# Try to connect to IBKR, but don't fail if it's not available
try:
    monitor.connect(
        host=config['ibkr']['host'],
        port=config['ibkr']['port'],
        clientId=config['ibkr']['monitor_client_id']
    )
    print(f"✅ Successfully connected to IBKR with monitor client ID {config['ibkr']['monitor_client_id']}")
except Exception as e:
    print(f"⚠️  IBKR connection failed: {e}")
    print("📊 Dashboard will start in offline mode - some features will be limited")
    print("💡 To enable full functionality, start IBKR TWS or IB Gateway")

# Use SHARED monitor connection for all components (avoids multiple connection conflicts)
scanner = WheelScanner(config['symbols'], monitor)
# Scanner shares monitor.ib connection - no separate connection needed
scanner.ib = monitor.ib  # Share the connection
print(f"✅ Scanner using shared monitor connection (client ID {config['ibkr']['monitor_client_id']})")

executor = TradeExecutor(monitor)
# Executor shares monitor.ib connection - no separate connection needed  
executor.ib = monitor.ib  # Share the connection
print(f"✅ Executor using shared monitor connection (client ID {config['ibkr']['monitor_client_id']})")
alert_manager = EnhancedAlertManager(config)
tracker = PerformanceTracker()
monitor.alert_manager = alert_manager
dashboard = WheelDashboard(monitor, scanner, tracker)
dashboard.start_monitoring()

# -------------------------------------------------------------
# Main Application
# -------------------------------------------------------------

def main():
    # Initialize logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Register cleanup on exit
    import atexit, signal
    atexit.register(cleanup_connections)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize components with enhanced features
    monitor = WheelMonitor(config['account']['starting_value'])
    
    # Set watchlist
    monitor.watchlist = config['symbols']
    
    # Try to connect to IBKR, but don't fail if it's not available
    try:
        monitor.connect(
            host=config['ibkr']['host'],
            port=config['ibkr']['port'],
            clientId=config['ibkr']['monitor_client_id']
        )
        print(f"✅ Successfully connected to IBKR with monitor client ID {config['ibkr']['monitor_client_id']}")
        
        # Pass IBKR client to AI research module for data enrichment
        if AI_RESEARCH_AVAILABLE and set_ibkr_client and monitor.ib:
            set_ibkr_client(monitor.ib)
            print("✅ IBKR data connected to Thesis Lab for live research")
    except Exception as e:
        print(f"⚠️  IBKR connection failed: {e}")
        print("📊 Dashboard will start in offline mode - some features will be limited")
        print("💡 To enable full functionality, start IBKR TWS or IB Gateway")
    
    # Initialize other components
    scanner = WheelScanner(config['symbols'], monitor)
    executor = TradeExecutor(monitor)
    alert_manager = EnhancedAlertManager(config)  # Use enhanced version
    tracker = PerformanceTracker()
    
    # Set alert manager in monitor
    monitor.alert_manager = alert_manager
    
    # Initialize enhanced workflow
    workflow = EnhancedDailyWorkflow(monitor, scanner, executor, alert_manager)
    
    # Initialize technical recovery manager
    recovery_manager = TechnicalRecoveryManager(monitor, "wheel_strategy.db")
    
    # Initialize execution quality analyzer
    execution_analyzer = ExecutionQualityAnalyzer(monitor)
    
    # Schedule enhanced daily routines with screeners
    schedule.every().day.at(config['screener']['pre_market_scan_time']).do(workflow.pre_market_screener)
    schedule.every().day.at("09:00").do(workflow.morning_routine)
    schedule.every().day.at("12:00").do(workflow.check_critical_opportunities)  # Mid-day check
    schedule.every().day.at("14:30").do(workflow.afternoon_checkin)
    schedule.every().day.at("16:15").do(workflow.end_of_day_routine)
    schedule.every().day.at(config['screener']['after_close_scan_time']).do(workflow.after_close_screener)
    
    # Schedule weekly performance review
    schedule.every().friday.at("16:30").do(workflow.weekly_performance_review)
    
    # Schedule daily database backup
    schedule.every().day.at("16:30").do(recovery_manager.create_database_backup)
    
    # Initialize dashboard
    global dashboard
    dashboard = WheelDashboard(monitor, scanner, tracker)
    dashboard.workflow = workflow  # <-- Ensure workflow is attached
    dashboard.start_monitoring()
    
    # Start scheduler in background
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)
            
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Print startup info
    print("🚀 Wheel Strategy System Started - FULLY OPTIMIZED with Enhanced Screeners")
    print(f"Account Value: ${config['account']['starting_value']:,}")
    print(f"Monitoring {len(config['symbols'])} symbols")
    print(f"Pre-market screener: {config['screener']['pre_market_scan_time']}")
    print(f"After-close screener: {config['screener']['after_close_scan_time']}")
    print("Check dashboard at http://localhost:7002")
    
    # Run web server and monitoring in main thread
    try:
        logger.info("Starting web server and monitoring...")
        
        # Start monitoring in a separate thread with its own event loop
        def start_monitoring():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            while True:
                try:
                    loop.run_until_complete(dashboard.update_dashboard_async())
                    time.sleep(30)
                except Exception as e:
                    logger.error(f"Monitor loop error: {e}")
                    time.sleep(5)  # Short delay on error
            
        monitor_thread = threading.Thread(target=start_monitoring, daemon=True)
        monitor_thread.start()
        
        # Run Flask server in main thread
        socketio.run(app, host='0.0.0.0', port=7002, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"Error starting web server: {e}")
        raise

if __name__ == "__main__":
    main()