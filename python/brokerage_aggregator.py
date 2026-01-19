"""
Multi-Brokerage Aggregator Service
==================================

Aggregates portfolio data from multiple brokerages:
- IBKR (via ib_insync)
- E*TRADE (via pyetrade)

Provides unified view of:
- Total portfolio value
- Combined positions
- Per-brokerage breakdown
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BrokerageStatus:
    """Status information for a single brokerage connection."""
    name: str
    connected: bool
    last_update: Optional[datetime] = None
    error: Optional[str] = None
    account_count: int = 0
    total_value: float = 0
    position_count: int = 0


@dataclass 
class AggregatedPortfolio:
    """Aggregated portfolio data from all brokerages."""
    total_value: float = 0
    total_positions: int = 0
    total_unrealized_pnl: float = 0
    brokerages: Dict[str, BrokerageStatus] = field(default_factory=dict)
    positions: List[Dict] = field(default_factory=list)
    accounts: List[Dict] = field(default_factory=list)
    last_updated: Optional[datetime] = None


class BrokerageAggregator:
    """
    Aggregates data from multiple brokerage connections.
    
    Currently supports:
    - IBKR (Interactive Brokers)
    - E*TRADE
    
    Future support planned for:
    - Schwab
    - Fidelity (via Plaid or CSV)
    """
    
    def __init__(self):
        """Initialize the aggregator."""
        self.ibkr_monitor = None
        self.etrade_connector = None
        
        # Cached aggregated data
        self._cached_portfolio: Optional[AggregatedPortfolio] = None
        self._cache_timestamp: Optional[datetime] = None
        
        # Initialize connectors
        self._init_connectors()
    
    def _init_connectors(self):
        """Initialize brokerage connectors."""
        # E*TRADE connector
        try:
            from etrade_connector import ETradeConnector
            self.etrade_connector = ETradeConnector()
            if self.etrade_connector.is_connected():
                logger.info("✅ E*TRADE connector initialized and connected")
            else:
                logger.info("⚠️ E*TRADE connector initialized but not authenticated")
        except Exception as e:
            logger.warning(f"Failed to initialize E*TRADE connector: {e}")
            self.etrade_connector = None
    
    def set_ibkr_monitor(self, monitor):
        """
        Set the IBKR monitor instance.
        
        Args:
            monitor: WheelMonitor instance from main app
        """
        self.ibkr_monitor = monitor
        logger.info("IBKR monitor set for aggregator")
    
    def get_ibkr_status(self) -> BrokerageStatus:
        """Get IBKR connection status and summary."""
        status = BrokerageStatus(name='IBKR', connected=False)
        
        try:
            import sys
            main_module = sys.modules.get('__main__')
            ib_client = None
            
            # Try to get IB client from dashboard or global monitor
            if main_module:
                dashboard = getattr(main_module, 'dashboard', None)
                monitor = getattr(main_module, 'monitor', None)
                
                if dashboard and hasattr(dashboard, 'monitor') and dashboard.monitor:
                    if hasattr(dashboard.monitor, 'ib') and dashboard.monitor.ib:
                        if dashboard.monitor.ib.isConnected():
                            ib_client = dashboard.monitor.ib
                
                if not ib_client and monitor and hasattr(monitor, 'ib') and monitor.ib:
                    if monitor.ib.isConnected():
                        ib_client = monitor.ib
            
            # Fallback to stored monitor
            if not ib_client and self.ibkr_monitor and self.ibkr_monitor.ib:
                if self.ibkr_monitor.ib.isConnected():
                    ib_client = self.ibkr_monitor.ib
            
            if ib_client:
                status.connected = True
                status.last_update = datetime.now()
                status.account_count = 1
                
                # Use accountValues() - synchronous read of cached data (same as live-metrics endpoint)
                try:
                    account_values = ib_client.accountValues()
                    for av in account_values:
                        if av.tag == 'NetLiquidation' and av.currency == 'USD':
                            status.total_value = float(av.value)
                            break
                    
                    # Get position count from portfolio
                    portfolio_items = ib_client.portfolio()
                    status.position_count = len([p for p in portfolio_items if p.position != 0])
                except Exception as data_err:
                    logger.warning(f"Could not get IBKR data details: {data_err}")
            else:
                status.error = "Not connected to TWS/IB Gateway"
                
        except Exception as e:
            status.error = str(e)
            logger.error(f"Error getting IBKR status: {e}")
        
        return status
    
    def get_etrade_status(self) -> BrokerageStatus:
        """Get E*TRADE connection status and summary."""
        status = BrokerageStatus(name='ETRADE', connected=False)
        
        if not self.etrade_connector:
            status.error = "E*TRADE connector not initialized"
            return status
        
        try:
            if self.etrade_connector.is_connected():
                summary = self.etrade_connector.get_summary()
                status.connected = True
                status.last_update = datetime.now()
                status.account_count = summary.get('account_count', 0)
                status.total_value = summary.get('total_value', 0)
                status.position_count = summary.get('total_positions', 0)
            else:
                status.error = self.etrade_connector.get_last_error() or "Not authenticated"
                
        except Exception as e:
            status.error = str(e)
            logger.error(f"Error getting E*TRADE status: {e}")
        
        return status
    
    def get_ibkr_positions(self) -> List[Dict]:
        """Get positions from IBKR using cached data."""
        positions = []
        
        if not self.ibkr_monitor or not self.ibkr_monitor.ib:
            return positions
        
        try:
            if not self.ibkr_monitor.ib.isConnected():
                return positions
            
            # Use cached positions to avoid event loop issues
            import sys
            main_module = sys.modules.get('__main__')
            if main_module:
                cached_positions = getattr(main_module, 'current_positions', None)
                if cached_positions:
                    # Convert cached positions to aggregator format
                    for pos in cached_positions:
                        position_info = {
                            'symbol': pos.get('symbol', 'UNKNOWN'),
                            'type': pos.get('type', 'UNKNOWN'),
                            'quantity': pos.get('quantity', 0),
                            'cost_basis': pos.get('cost_basis', 0),
                            'market_value': pos.get('market_value', 0),
                            'current_price': pos.get('stock_price', 0),
                            'unrealized_pnl': pos.get('unrealized_pnl', 0),
                            'strike': pos.get('strike'),
                            'expiry': pos.get('expiry'),
                            'call_put': pos.get('call_put'),
                            'brokerage': 'IBKR',
                            'account_id': pos.get('account_id', 'IBKR')
                        }
                        positions.append(position_info)
                    return positions
            
            logger.warning("No cached IBKR positions available")
                
        except Exception as e:
            logger.error(f"Error getting IBKR positions: {e}")
        
        return positions
    
    def get_etrade_positions(self) -> List[Dict]:
        """Get positions from E*TRADE."""
        if not self.etrade_connector or not self.etrade_connector.is_connected():
            return []
        
        try:
            return self.etrade_connector.get_all_positions()
        except Exception as e:
            logger.error(f"Error getting E*TRADE positions: {e}")
            return []
    
    def get_aggregated_portfolio(self, force_refresh: bool = False) -> AggregatedPortfolio:
        """
        Get aggregated portfolio data from all connected brokerages.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            AggregatedPortfolio with combined data from all brokerages
        """
        portfolio = AggregatedPortfolio()
        portfolio.last_updated = datetime.now()
        
        # Get IBKR data
        ibkr_status = self.get_ibkr_status()
        portfolio.brokerages['IBKR'] = ibkr_status
        
        if ibkr_status.connected:
            ibkr_positions = self.get_ibkr_positions()
            portfolio.positions.extend(ibkr_positions)
            portfolio.total_value += ibkr_status.total_value
            portfolio.total_positions += len(ibkr_positions)
            
            # Calculate IBKR unrealized P&L
            ibkr_pnl = sum(p.get('unrealized_pnl', 0) for p in ibkr_positions)
            portfolio.total_unrealized_pnl += ibkr_pnl
            
            portfolio.accounts.append({
                'brokerage': 'IBKR',
                'account_name': 'IBKR Main',
                'account_value': ibkr_status.total_value,
                'position_count': len(ibkr_positions),
                'unrealized_pnl': ibkr_pnl,
                'status': '🟢 LIVE'
            })
        
        # Get E*TRADE data
        etrade_status = self.get_etrade_status()
        portfolio.brokerages['ETRADE'] = etrade_status
        
        if etrade_status.connected:
            etrade_positions = self.get_etrade_positions()
            portfolio.positions.extend(etrade_positions)
            portfolio.total_value += etrade_status.total_value
            portfolio.total_positions += len(etrade_positions)
            
            # Get E*TRADE account details
            if self.etrade_connector:
                summary = self.etrade_connector.get_summary()
                for acct in summary.get('accounts', []):
                    portfolio.accounts.append({
                        'brokerage': 'ETRADE',
                        'account_name': acct.get('account_name', 'E*TRADE'),
                        'account_value': acct.get('account_value', 0),
                        'position_count': acct.get('position_count', 0),
                        'unrealized_pnl': acct.get('unrealized_pnl', 0),
                        'status': '🟢 LIVE'
                    })
                    portfolio.total_unrealized_pnl += acct.get('unrealized_pnl', 0)
        
        self._cached_portfolio = portfolio
        self._cache_timestamp = datetime.now()
        
        return portfolio
    
    def get_status_summary(self) -> Dict:
        """
        Get connection status summary for all brokerages.
        
        Returns:
            Dictionary with status for each brokerage
        """
        ibkr_status = self.get_ibkr_status()
        etrade_status = self.get_etrade_status()
        
        return {
            'IBKR': {
                'connected': ibkr_status.connected,
                'error': ibkr_status.error,
                'account_count': ibkr_status.account_count,
                'total_value': ibkr_status.total_value,
                'position_count': ibkr_status.position_count,
                'last_update': ibkr_status.last_update.isoformat() if ibkr_status.last_update else None
            },
            'ETRADE': {
                'connected': etrade_status.connected,
                'error': etrade_status.error,
                'account_count': etrade_status.account_count,
                'total_value': etrade_status.total_value,
                'position_count': etrade_status.position_count,
                'last_update': etrade_status.last_update.isoformat() if etrade_status.last_update else None
            },
            'summary': {
                'total_connected': sum([ibkr_status.connected, etrade_status.connected]),
                'total_value': ibkr_status.total_value + etrade_status.total_value,
                'total_positions': ibkr_status.position_count + etrade_status.position_count
            }
        }
    
    def to_dashboard_format(self) -> Dict:
        """
        Get portfolio data in format suitable for dashboard display.
        
        Returns:
            Dictionary formatted for dashboard consumption
        """
        portfolio = self.get_aggregated_portfolio()
        
        return {
            'total_value': portfolio.total_value,
            'total_positions': portfolio.total_positions,
            'total_unrealized_pnl': portfolio.total_unrealized_pnl,
            'accounts': portfolio.accounts,
            'positions': portfolio.positions,
            'brokerages': {
                name: {
                    'connected': status.connected,
                    'error': status.error,
                    'value': status.total_value,
                    'positions': status.position_count,
                    'last_update': status.last_update.isoformat() if status.last_update else None
                }
                for name, status in portfolio.brokerages.items()
            },
            'last_updated': portfolio.last_updated.isoformat() if portfolio.last_updated else None
        }


# Global instance
aggregator = BrokerageAggregator()


def get_aggregator() -> BrokerageAggregator:
    """Get the global aggregator instance."""
    return aggregator
