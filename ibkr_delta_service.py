#!/usr/bin/env python3
"""
IBKR Delta Service - Background service to fetch live Greeks from IBKR
Solves event loop conflicts by running IBKR calls in separate process
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from ib_insync import *

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IBKRDeltaService:
    def __init__(self, host='127.0.0.1', port=7496, client_id=9999):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.cache_file = 'delta_cache.json'
        self.running = False
        
    async def connect(self):
        """Connect to IBKR"""
        try:
            await self.ib.connectAsync(self.host, self.port, self.client_id)
            logger.info(f"✅ Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to IBKR: {e}")
            return False
    
    async def get_live_delta(self, symbol, strike, expiry, right):
        """Get live delta from IBKR for a specific option"""
        try:
            # Create option contract
            option = Option(
                symbol=symbol,
                lastTradeDateOrContractMonth=expiry,
                strike=strike,
                right=right,
                exchange='SMART',
                currency='USD'
            )
            
            # Qualify the contract
            qualified_contracts = await self.ib.qualifyContractsAsync(option)
            if not qualified_contracts:
                logger.warning(f"⚠️ Could not qualify contract for {symbol} {strike} {right}")
                return None
            
            qualified_contract = qualified_contracts[0]
            
            # Request market data with Greeks
            ticker = self.ib.reqMktData(qualified_contract, '106', False, False)
            
            # Wait for Greeks to populate
            max_wait = 5.0
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
                    self.ib.cancelMktData(qualified_contract)
                    logger.info(f"✅ {symbol} {strike} {right}: LIVE delta {delta_value:.3f}")
                    return delta_value
            
            # Timeout
            self.ib.cancelMktData(qualified_contract)
            logger.warning(f"⚠️ Timeout getting Greeks for {symbol} {strike} {right}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting delta for {symbol} {strike} {right}: {e}")
            return None
    
    async def update_delta_cache(self, positions):
        """Update delta cache for all positions"""
        try:
            delta_cache = {}
            
            for position in positions:
                symbol = position.get('symbol')
                contract_type = position.get('contract_type', 'STK')
                
                if contract_type == 'STK':
                    # Stock delta is always 1.0
                    delta_cache[symbol] = 1.0
                    continue
                
                # For options, get live delta
                strike = position.get('strike', 0)
                expiry = position.get('expiry', '')
                right = position.get('option_type', '')
                
                if not all([symbol, strike, expiry, right]):
                    logger.warning(f"⚠️ Missing data for {symbol}: strike={strike}, expiry={expiry}, right={right}")
                    continue
                
                # Convert expiry format if needed
                if '/' in expiry:
                    # Convert MM/DD/YYYY to YYYYMMDD
                    try:
                        date_obj = datetime.strptime(expiry, '%m/%d/%Y')
                        expiry = date_obj.strftime('%Y%m%d')
                    except:
                        logger.warning(f"⚠️ Could not parse expiry {expiry} for {symbol}")
                        continue
                
                # Get live delta
                live_delta = await self.get_live_delta(symbol, strike, expiry, right)
                if live_delta is not None:
                    delta_cache[symbol] = live_delta
                else:
                    logger.warning(f"⚠️ Could not get live delta for {symbol}, using estimate")
                    # Fallback to simple estimate
                    if right == 'P':
                        delta_cache[symbol] = -0.3  # Conservative estimate for puts
                    else:
                        delta_cache[symbol] = 0.3   # Conservative estimate for calls
            
            # Save to cache file
            with open(self.cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'deltas': delta_cache
                }, f, indent=2)
            
            logger.info(f"✅ Updated delta cache with {len(delta_cache)} positions")
            return delta_cache
            
        except Exception as e:
            logger.error(f"❌ Error updating delta cache: {e}")
            return {}
    
    def get_cached_deltas(self):
        """Get cached delta values"""
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                return data.get('deltas', {})
        except FileNotFoundError:
            logger.info("📄 No delta cache file found")
            return {}
        except Exception as e:
            logger.error(f"❌ Error reading delta cache: {e}")
            return {}
    
    async def run_service(self, positions, update_interval=30):
        """Run the delta service continuously"""
        self.running = True
        logger.info("🚀 Starting IBKR Delta Service")
        
        if not await self.connect():
            logger.error("❌ Failed to connect to IBKR, exiting")
            return
        
        while self.running:
            try:
                logger.info("🔄 Updating delta cache...")
                await self.update_delta_cache(positions)
                
                # Wait before next update
                logger.info(f"⏰ Waiting {update_interval} seconds before next update...")
                await asyncio.sleep(update_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"❌ Error in delta service: {e}")
                await asyncio.sleep(10)  # Wait before retry
        
        # Cleanup
        if self.ib.isConnected():
            await self.ib.disconnectAsync()
        logger.info("✅ Delta service stopped")

async def main():
    """Main function to run the delta service"""
    # Example positions - this would come from your main application
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
    
    service = IBKRDeltaService()
    await service.run_service(positions)

if __name__ == "__main__":
    asyncio.run(main()) 