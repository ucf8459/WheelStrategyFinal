"""
E*TRADE API Connector for Multi-Brokerage Dashboard
====================================================

This module provides integration with E*TRADE's API for:
- Account information and balances
- Portfolio positions
- Real-time quotes (with limitations)

Authentication: OAuth 1.0a (requires user authorization flow)

Setup:
1. Go to https://developer.etrade.com and create an app
2. Get your Consumer Key and Consumer Secret
3. Add to .env:
   ETRADE_CONSUMER_KEY=your_key
   ETRADE_CONSUMER_SECRET=your_secret
4. Run authorize_etrade() once to get access tokens
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import pyetrade - will be installed via requirements.txt
try:
    import pyetrade
    PYETRADE_AVAILABLE = True
except ImportError:
    PYETRADE_AVAILABLE = False
    logger.warning("pyetrade not installed - E*TRADE integration disabled")


class ETradeConnector:
    """
    E*TRADE API connector for portfolio aggregation.
    
    Handles OAuth authentication and provides methods for:
    - Fetching account list
    - Fetching account balances
    - Fetching positions
    """
    
    def __init__(self, consumer_key: str = None, consumer_secret: str = None):
        """
        Initialize E*TRADE connector.
        
        Args:
            consumer_key: E*TRADE API consumer key (or from env)
            consumer_secret: E*TRADE API consumer secret (or from env)
        """
        self.consumer_key = consumer_key or os.getenv('ETRADE_CONSUMER_KEY')
        self.consumer_secret = consumer_secret or os.getenv('ETRADE_CONSUMER_SECRET')
        
        # Token storage file
        self.token_file = Path(__file__).parent / '.etrade_tokens.json'
        
        # API clients (initialized after auth)
        self.oauth = None
        self.accounts_api = None
        self.market_api = None
        
        # Cached data
        self.accounts_cache = {}
        self.positions_cache = {}
        self.cache_timestamp = None
        self.cache_duration = timedelta(minutes=5)
        
        # Connection status
        self._connected = False
        self._last_error = None
        
        # Sandbox mode for testing (set to False for production)
        # Default to True until production keys are obtained
        self.sandbox = os.getenv('ETRADE_SANDBOX', 'true').lower() == 'true'
        
        if not PYETRADE_AVAILABLE:
            logger.error("pyetrade library not available")
            return
            
        if not self.consumer_key or not self.consumer_secret:
            logger.warning("E*TRADE credentials not configured - set ETRADE_CONSUMER_KEY and ETRADE_CONSUMER_SECRET")
            return
        
        # Try to load existing tokens
        self._load_tokens()
    
    def _load_tokens(self) -> bool:
        """Load saved OAuth tokens from file."""
        if not self.token_file.exists():
            logger.info("No saved E*TRADE tokens found")
            return False
        
        try:
            with open(self.token_file, 'r') as f:
                tokens = json.load(f)
            
            # Check if tokens are expired (E*TRADE tokens last ~2 hours for access, refresh tokens last longer)
            saved_time = datetime.fromisoformat(tokens.get('saved_at', '2000-01-01'))
            if datetime.now() - saved_time > timedelta(hours=2):
                logger.info("E*TRADE access tokens expired, need refresh")
                # Try to refresh using refresh token
                return self._refresh_tokens(tokens)
            
            self.access_token = tokens.get('access_token')
            self.access_token_secret = tokens.get('access_token_secret')
            
            if self.access_token and self.access_token_secret:
                self._initialize_apis()
                return True
                
        except Exception as e:
            logger.error(f"Failed to load E*TRADE tokens: {e}")
        
        return False
    
    def _save_tokens(self, access_token: str, access_token_secret: str):
        """Save OAuth tokens to file."""
        tokens = {
            'access_token': access_token,
            'access_token_secret': access_token_secret,
            'saved_at': datetime.now().isoformat()
        }
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f)
            logger.info("E*TRADE tokens saved")
        except Exception as e:
            logger.error(f"Failed to save E*TRADE tokens: {e}")
    
    def _refresh_tokens(self, old_tokens: dict) -> bool:
        """Attempt to refresh expired tokens."""
        try:
            oauth = pyetrade.ETradeOAuth(self.consumer_key, self.consumer_secret)
            
            # E*TRADE uses OAuth 1.0a - we need to re-authorize if tokens expired
            # The access token can be renewed before it expires
            # For now, we'll require re-authorization
            logger.warning("E*TRADE tokens need refresh - please re-authorize")
            return False
            
        except Exception as e:
            logger.error(f"Failed to refresh E*TRADE tokens: {e}")
            return False
    
    def _initialize_apis(self):
        """Initialize API clients with current tokens."""
        if not PYETRADE_AVAILABLE:
            return
            
        try:
            self.accounts_api = pyetrade.ETradeAccounts(
                self.consumer_key,
                self.consumer_secret,
                self.access_token,
                self.access_token_secret,
                dev=self.sandbox
            )
            
            self.market_api = pyetrade.ETradeMarket(
                self.consumer_key,
                self.consumer_secret,
                self.access_token,
                self.access_token_secret,
                dev=self.sandbox
            )
            
            self._connected = True
            logger.info("E*TRADE API clients initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize E*TRADE APIs: {e}")
            self._connected = False
            self._last_error = str(e)
    
    def get_authorization_url(self) -> Optional[str]:
        """
        Start OAuth flow and get authorization URL.
        
        Returns:
            URL for user to authorize the app, or None if failed
        """
        if not PYETRADE_AVAILABLE:
            return None
            
        if not self.consumer_key or not self.consumer_secret:
            logger.error("E*TRADE credentials not configured")
            return None
        
        try:
            self.oauth = pyetrade.ETradeOAuth(self.consumer_key, self.consumer_secret)
            auth_url = self.oauth.get_request_token()
            logger.info(f"E*TRADE authorization URL generated")
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to get E*TRADE authorization URL: {e}")
            self._last_error = str(e)
            return None
    
    def complete_authorization(self, verifier_code: str) -> bool:
        """
        Complete OAuth flow with verifier code from user.
        
        Args:
            verifier_code: The code shown after user authorizes the app
            
        Returns:
            True if authorization successful
        """
        if not self.oauth:
            logger.error("OAuth flow not started - call get_authorization_url first")
            return False
        
        try:
            tokens = self.oauth.get_access_token(verifier_code)
            
            self.access_token = tokens['oauth_token']
            self.access_token_secret = tokens['oauth_token_secret']
            
            self._save_tokens(self.access_token, self.access_token_secret)
            self._initialize_apis()
            
            return self._connected
            
        except Exception as e:
            logger.error(f"Failed to complete E*TRADE authorization: {e}")
            self._last_error = str(e)
            return False
    
    def is_connected(self) -> bool:
        """Check if connected and authenticated to E*TRADE."""
        return self._connected and self.accounts_api is not None
    
    def get_last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error
    
    def get_accounts(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get list of E*TRADE accounts.
        
        Returns:
            List of account dictionaries with id, name, type, etc.
        """
        if not self.is_connected():
            logger.warning("E*TRADE not connected")
            return []
        
        # Check cache
        if not force_refresh and self.accounts_cache and self.cache_timestamp:
            if datetime.now() - self.cache_timestamp < self.cache_duration:
                return list(self.accounts_cache.values())
        
        try:
            response = self.accounts_api.list_accounts(resp_format='json')
            
            accounts = []
            account_list = response.get('AccountListResponse', {}).get('Accounts', {}).get('Account', [])
            
            # Ensure it's a list
            if isinstance(account_list, dict):
                account_list = [account_list]
            
            for acct in account_list:
                account_info = {
                    'account_id': acct.get('accountId'),
                    'account_id_key': acct.get('accountIdKey'),
                    'account_name': acct.get('accountName', 'E*TRADE Account'),
                    'account_type': acct.get('accountType', 'Unknown'),
                    'institution_type': acct.get('institutionType', 'BROKERAGE'),
                    'account_status': acct.get('accountStatus', 'ACTIVE'),
                    'brokerage': 'ETRADE'
                }
                accounts.append(account_info)
                self.accounts_cache[account_info['account_id_key']] = account_info
            
            self.cache_timestamp = datetime.now()
            logger.info(f"Found {len(accounts)} E*TRADE accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get E*TRADE accounts: {e}")
            self._last_error = str(e)
            return []
    
    def get_account_balance(self, account_id_key: str) -> Optional[Dict]:
        """
        Get balance for a specific E*TRADE account.
        
        Args:
            account_id_key: The account ID key from get_accounts()
            
        Returns:
            Dictionary with balance information
        """
        if not self.is_connected():
            logger.warning("E*TRADE not connected")
            return None
        
        try:
            # realTimeNAV parameter only works in sandbox, not production
            try:
                response = self.accounts_api.get_account_balance(
                    account_id_key,
                    resp_format='json',
                    realTimeNAV=True
                )
            except TypeError:
                # Production API doesn't support realTimeNAV
                response = self.accounts_api.get_account_balance(
                    account_id_key,
                    resp_format='json'
                )
            
            balance_data = response.get('BalanceResponse', {})
            computed = balance_data.get('Computed', {})
            
            return {
                'account_id': balance_data.get('accountId'),
                'account_value': computed.get('RealTimeValues', {}).get('totalAccountValue', 0),
                'cash_available': computed.get('cashAvailableForInvestment', 0),
                'cash_balance': computed.get('cashBalance', 0),
                'margin_buying_power': computed.get('marginBuyingPower', 0),
                'cash_buying_power': computed.get('cashBuyingPower', 0),
                'net_cash': computed.get('netCash', 0),
                'unrealized_pnl': computed.get('RealTimeValues', {}).get('totalGainLoss', 0),
                'unrealized_pnl_pct': computed.get('RealTimeValues', {}).get('totalGainLossPct', 0),
                'day_change': computed.get('RealTimeValues', {}).get('totalMarketValue', 0) - computed.get('RealTimeValues', {}).get('totalAccountValue', 0),
                'brokerage': 'ETRADE',
                'last_updated': datetime.now().isoformat()
            }
            
        except TypeError as e:
            # Handle API parameter differences between sandbox and production
            logger.warning(f"API parameter issue for {account_id_key}, trying without optional params: {e}")
            try:
                response = self.accounts_api.get_account_balance(account_id_key, resp_format='json')
                balance_data = response.get('BalanceResponse', {})
                computed = balance_data.get('Computed', {})
                
                return {
                    'account_id': balance_data.get('accountId'),
                    'account_value': computed.get('RealTimeValues', {}).get('totalAccountValue', 0) or computed.get('totalAccountValue', 0),
                    'cash_available': computed.get('cashAvailableForInvestment', 0),
                    'cash_balance': computed.get('cashBalance', 0),
                    'margin_buying_power': computed.get('marginBuyingPower', 0),
                    'cash_buying_power': computed.get('cashBuyingPower', 0),
                    'net_cash': computed.get('netCash', 0),
                    'unrealized_pnl': computed.get('RealTimeValues', {}).get('totalGainLoss', 0) or 0,
                    'unrealized_pnl_pct': computed.get('RealTimeValues', {}).get('totalGainLossPct', 0) or 0,
                    'brokerage': 'ETRADE',
                    'last_updated': datetime.now().isoformat()
                }
            except Exception as inner_e:
                logger.error(f"Failed to get E*TRADE balance for {account_id_key}: {inner_e}")
                self._last_error = str(inner_e)
                return None
        except Exception as e:
            logger.error(f"Failed to get E*TRADE balance for {account_id_key}: {e}")
            self._last_error = str(e)
            return None
    
    def get_positions(self, account_id_key: str) -> List[Dict]:
        """
        Get positions for a specific E*TRADE account.
        
        Args:
            account_id_key: The account ID key from get_accounts()
            
        Returns:
            List of position dictionaries
        """
        if not self.is_connected():
            logger.warning("E*TRADE not connected")
            return []
        
        try:
            response = self.accounts_api.get_account_portfolio(
                account_id_key,
                resp_format='json'
            )
            
            # Handle empty or error responses
            if not response:
                logger.info(f"No portfolio data for account {account_id_key}")
                return []
            
            positions = []
            portfolio = response.get('PortfolioResponse', {}).get('AccountPortfolio', [])
            
            # Ensure it's a list
            if isinstance(portfolio, dict):
                portfolio = [portfolio]
            
            for acct_portfolio in portfolio:
                position_list = acct_portfolio.get('Position', [])
                
                # Ensure it's a list
                if isinstance(position_list, dict):
                    position_list = [position_list]
                
                for pos in position_list:
                    product = pos.get('Product', {})
                    quick = pos.get('Quick', {})
                    
                    # Determine position type
                    security_type = product.get('securityType', 'EQ')
                    if security_type in ['OPTN', 'OPT']:
                        pos_type = 'OPTION'
                        # Parse option details from symbol
                        call_put = product.get('callPut', '')
                        strike = product.get('strikePrice', 0)
                        expiry = product.get('expiryDate', '')
                    else:
                        pos_type = 'STOCK'
                        call_put = None
                        strike = None
                        expiry = None
                    
                    position_info = {
                        'symbol': product.get('symbol', 'UNKNOWN'),
                        'type': pos_type,
                        'quantity': pos.get('quantity', 0),
                        'cost_basis': pos.get('totalCost', 0),
                        'market_value': pos.get('marketValue', 0),
                        'current_price': quick.get('lastTrade', 0),
                        'day_change': quick.get('change', 0),
                        'day_change_pct': quick.get('changePct', 0),
                        'unrealized_pnl': pos.get('totalGain', 0),
                        'unrealized_pnl_pct': pos.get('totalGainPct', 0),
                        'strike': strike,
                        'expiry': expiry,
                        'call_put': call_put,
                        'brokerage': 'ETRADE',
                        'account_id': account_id_key
                    }
                    positions.append(position_info)
            
            logger.info(f"Found {len(positions)} positions in E*TRADE account {account_id_key}")
            return positions
            
        except json.JSONDecodeError as e:
            # Empty portfolio or API returned non-JSON response
            logger.info(f"No positions or empty response for account {account_id_key}")
            return []
        except Exception as e:
            logger.error(f"Failed to get E*TRADE positions for {account_id_key}: {e}")
            self._last_error = str(e)
            return []
    
    def get_all_positions(self) -> List[Dict]:
        """
        Get positions from all E*TRADE accounts.
        
        Returns:
            List of all positions across all accounts
        """
        all_positions = []
        
        accounts = self.get_accounts()
        for acct in accounts:
            account_id_key = acct.get('account_id_key')
            if account_id_key:
                positions = self.get_positions(account_id_key)
                all_positions.extend(positions)
        
        return all_positions
    
    def get_total_value(self) -> float:
        """
        Get total value across all E*TRADE accounts.
        
        Returns:
            Total account value
        """
        total = 0
        
        accounts = self.get_accounts()
        for acct in accounts:
            account_id_key = acct.get('account_id_key')
            if account_id_key:
                balance = self.get_account_balance(account_id_key)
                if balance:
                    total += balance.get('account_value', 0)
        
        return total
    
    def get_summary(self) -> Dict:
        """
        Get summary of all E*TRADE accounts.
        
        Returns:
            Dictionary with total value, account count, position count
        """
        accounts = self.get_accounts()
        total_value = 0
        total_positions = 0
        account_summaries = []
        
        for acct in accounts:
            account_id_key = acct.get('account_id_key')
            if account_id_key:
                balance = self.get_account_balance(account_id_key)
                positions = self.get_positions(account_id_key)
                
                account_value = balance.get('account_value', 0) if balance else 0
                total_value += account_value
                total_positions += len(positions)
                
                account_summaries.append({
                    'account_name': acct.get('account_name'),
                    'account_type': acct.get('account_type'),
                    'account_value': account_value,
                    'position_count': len(positions),
                    'unrealized_pnl': balance.get('unrealized_pnl', 0) if balance else 0
                })
        
        return {
            'brokerage': 'ETRADE',
            'connected': self.is_connected(),
            'account_count': len(accounts),
            'total_value': total_value,
            'total_positions': total_positions,
            'accounts': account_summaries,
            'last_updated': datetime.now().isoformat()
        }


# Convenience function for authorization flow
def authorize_etrade():
    """
    Interactive authorization flow for E*TRADE.
    Run this once to authorize the app.
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    connector = ETradeConnector()
    
    if connector.is_connected():
        print("✅ Already connected to E*TRADE!")
        summary = connector.get_summary()
        print(f"   Accounts: {summary['account_count']}")
        print(f"   Total Value: ${summary['total_value']:,.2f}")
        return True
    
    print("\n" + "="*60)
    print("E*TRADE Authorization Flow")
    print("="*60)
    
    if not connector.consumer_key or not connector.consumer_secret:
        print("\n❌ E*TRADE credentials not found!")
        print("\nPlease add to your .env file:")
        print("  ETRADE_CONSUMER_KEY=your_consumer_key")
        print("  ETRADE_CONSUMER_SECRET=your_consumer_secret")
        print("\nGet these from: https://developer.etrade.com")
        return False
    
    print("\n1. Getting authorization URL...")
    auth_url = connector.get_authorization_url()
    
    if not auth_url:
        print(f"❌ Failed to get authorization URL: {connector.get_last_error()}")
        return False
    
    print(f"\n2. Open this URL in your browser:\n")
    print(f"   {auth_url}")
    print("\n3. Log in to E*TRADE and authorize the app")
    print("4. You'll see a verification code - enter it below:\n")
    
    verifier = input("Verification code: ").strip()
    
    if not verifier:
        print("❌ No verification code entered")
        return False
    
    print("\n5. Completing authorization...")
    
    if connector.complete_authorization(verifier):
        print("✅ Successfully connected to E*TRADE!")
        summary = connector.get_summary()
        print(f"\n   Accounts: {summary['account_count']}")
        print(f"   Total Value: ${summary['total_value']:,.2f}")
        print(f"   Positions: {summary['total_positions']}")
        return True
    else:
        print(f"❌ Authorization failed: {connector.get_last_error()}")
        return False


if __name__ == '__main__':
    # Run authorization flow when executed directly
    authorize_etrade()
