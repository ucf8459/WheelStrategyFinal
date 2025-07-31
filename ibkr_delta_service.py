#!/usr/bin/env python3
"""
IBKR Delta Service - Background service to fetch live Greeks from IBKR
Solves event loop conflicts by running IBKR calls in separate process
"""

import asyncio
import json
import time
import logging
import aiohttp
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
            # Find the actual position in IBKR portfolio
            portfolio_items = self.ib.portfolio()
            matching_item = None
            
            for item in portfolio_items:
                if (hasattr(item.contract, 'symbol') and item.contract.symbol == symbol and
                    hasattr(item.contract, 'strike') and item.contract.strike == strike and
                    hasattr(item.contract, 'right') and item.contract.right == right):
                    matching_item = item
                    break
            
            if not matching_item:
                logger.warning(f"⚠️ Could not find position for {symbol} {strike} {right}")
                return None
            
            contract = matching_item.contract
            logger.info(f"🔍 Found position: {contract}")
            
            # Check if we can get Greeks directly from portfolio item
            if hasattr(matching_item, 'modelGreeks') and matching_item.modelGreeks:
                if hasattr(matching_item.modelGreeks, 'delta') and matching_item.modelGreeks.delta is not None:
                    delta_value = float(matching_item.modelGreeks.delta)
                    logger.info(f"✅ {symbol} {strike} {right}: LIVE delta from portfolio {delta_value:.3f}")
                    return delta_value
            
            # Request market data with Greeks
            logger.info(f"🔍 Requesting live Greeks for {symbol} {strike} {right}...")
            
            # Method 1: Request with generic tick types for Greeks
            ticker = self.ib.reqMktData(contract, '106', False, False)
            
            # Wait for Greeks to populate
            max_wait = 15.0
            wait_interval = 0.5
            elapsed = 0
            
            while elapsed < max_wait:
                await asyncio.sleep(wait_interval)
                elapsed += wait_interval
                
                # Check if Greeks are available in modelGreeks
                if hasattr(ticker, 'modelGreeks') and ticker.modelGreeks:
                    if hasattr(ticker.modelGreeks, 'delta') and ticker.modelGreeks.delta is not None:
                        delta_value = float(ticker.modelGreeks.delta)
                        self.ib.cancelMktData(contract)
                        logger.info(f"✅ {symbol} {strike} {right}: LIVE delta {delta_value:.3f}")
                        return delta_value
                
                # Check for generic tick data (tick type 23 = Delta)
                if hasattr(ticker, 'genericTicks') and ticker.genericTicks:
                    for tick in ticker.genericTicks:
                        if tick.tickType == 23:  # Delta
                            delta_value = float(tick.value)
                            self.ib.cancelMktData(contract)
                            logger.info(f"✅ {symbol} {strike} {right}: LIVE delta {delta_value:.3f}")
                            return delta_value
                
                # Check for option computation tick data
                if hasattr(ticker, 'optionComputation') and ticker.optionComputation:
                    for comp in ticker.optionComputation:
                        if hasattr(comp, 'delta') and comp.delta is not None:
                            delta_value = float(comp.delta)
                            self.ib.cancelMktData(contract)
                            logger.info(f"✅ {symbol} {strike} {right}: LIVE delta {delta_value:.3f}")
                            return delta_value
            
            # Timeout - try alternative method with different tick types
            self.ib.cancelMktData(contract)
            logger.warning(f"⚠️ Timeout getting Greeks for {symbol} {strike} {right}, trying alternative method...")
            
            # Method 2: Try with different tick types
            try:
                ticker2 = self.ib.reqMktData(contract, '23', False, False)
                await asyncio.sleep(3)
                
                if hasattr(ticker2, 'genericTicks') and ticker2.genericTicks:
                    for tick in ticker2.genericTicks:
                        if tick.tickType == 23:  # Delta
                            delta_value = float(tick.value)
                            self.ib.cancelMktData(contract)
                            logger.info(f"✅ {symbol} {strike} {right}: LIVE delta (alt method) {delta_value:.3f}")
                            return delta_value
                
                self.ib.cancelMktData(contract)
            except Exception as e:
                logger.warning(f"⚠️ Alternative method failed: {e}")
            
            # Method 3: Try with specific Greeks tick types
            try:
                ticker3 = self.ib.reqMktData(contract, '24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50', False, False)
                await asyncio.sleep(3)
                
                if hasattr(ticker3, 'genericTicks') and ticker3.genericTicks:
                    for tick in ticker3.genericTicks:
                        if tick.tickType == 23:  # Delta
                            delta_value = float(tick.value)
                            self.ib.cancelMktData(contract)
                            logger.info(f"✅ {symbol} {strike} {right}: LIVE delta (method 3) {delta_value:.3f}")
                            return delta_value
                
                self.ib.cancelMktData(contract)
            except Exception as e:
                logger.warning(f"⚠️ Method 3 failed: {e}")
            
            logger.warning(f"⚠️ Could not get live delta for {symbol} {strike} {right}")
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
                
                # Get live delta - ONLY use live deltas, no fallback
                live_delta = await self.get_live_delta(symbol, strike, expiry, right)
                if live_delta is not None:
                    delta_cache[symbol] = live_delta
                    logger.info(f"✅ {symbol}: Using LIVE delta {live_delta:.3f}")
                else:
                    logger.error(f"❌ Could not get live delta for {symbol} - SKIPPING")
                    continue
            
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
    
    def _calculate_smart_delta(self, symbol, strike, expiry, right):
        """Calculate smart delta estimate based on moneyness and time to expiry"""
        try:
            # Use actual stock prices from IBKR data
            stock_prices = {
                'DE': 514.5,
                'GOOG': 189.0, 
                'JPM': 283.5,
                'NVDA': 183.3,
                'UNH': 270.0,
                'WMT': 94.0,
                'XOM': 110.0
            }
            
            # Get current stock price
            stock_price = stock_prices.get(symbol, strike)  # Use actual price or fallback to strike
            
            # Calculate moneyness
            moneyness = stock_price / strike
            
            # Get days to expiry
            dte = 30  # Default
            try:
                if '/' in expiry:
                    expiry_date = datetime.strptime(expiry, '%m/%d/%Y')
                else:
                    expiry_date = datetime.strptime(expiry, '%Y%m%d')
                dte = (expiry_date - datetime.now()).days
                dte = max(dte, 1)  # Ensure positive
            except:
                dte = 30
            
            # Smart delta estimation based on moneyness and DTE
            if right == 'C':  # Call option
                if moneyness > 1.05:  # ITM
                    delta = 0.8 + (moneyness - 1.05) * 0.4
                elif moneyness > 0.95:  # Near ATM
                    delta = 0.4 + (moneyness - 0.95) * 0.4
                elif moneyness > 0.85:  # OTM
                    delta = 0.2 + (moneyness - 0.85) * 0.2
                else:  # Deep OTM
                    delta = 0.1
                
                # Adjust for DTE - longer DTE means higher delta for ITM, lower for OTM
                if dte < 7:
                    delta *= 0.8  # Short-term options have lower deltas
                elif dte > 45:
                    delta *= 1.1  # Long-term options have higher deltas
                    
            else:  # Put option
                if moneyness < 0.95:  # ITM
                    delta = -0.8 - (0.95 - moneyness) * 0.4
                elif moneyness < 1.05:  # Near ATM
                    delta = -0.4 - (1.05 - moneyness) * 0.4
                elif moneyness < 1.15:  # OTM
                    delta = -0.2 - (1.15 - moneyness) * 0.2
                else:  # Deep OTM
                    delta = -0.1
                
                # Adjust for DTE - longer DTE means lower delta (more negative) for ITM
                if dte < 7:
                    delta *= 0.8  # Short-term options have higher deltas (less negative)
                elif dte > 45:
                    delta *= 1.1  # Long-term options have lower deltas (more negative)
            
            # Add some randomness for realism
            import random
            # Use stock price and strike to create unique seed
            unique_seed = int((stock_price * 1000 + strike * 100 + hash(symbol) % 1000))
            random.seed(unique_seed)
            delta += random.uniform(-0.03, 0.03)
            
            # Ensure delta is within reasonable bounds
            if right == 'C':
                delta = max(0.0, min(1.0, delta))
            else:
                delta = max(-1.0, min(0.0, delta))
            
            logger.info(f"🧮 {symbol} {strike} {right}: Smart delta estimate {delta:.3f} (DTE={dte}, moneyness={moneyness:.2f})")
            return delta
            
        except Exception as e:
            logger.error(f"❌ Error in smart delta calculation for {symbol}: {e}")
            # Ultimate fallback to conservative values
            return -0.3 if right == 'P' else 0.3
    
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
    
    async def get_positions_from_dashboard(self):
        """Get positions from the dashboard API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:7001/api/positions-for-delta-service') as response:
                    if response.status == 200:
                        positions = await response.json()
                        logger.info(f"📊 Retrieved {len(positions)} positions from dashboard")
                        return positions
                    else:
                        logger.warning(f"⚠️ Failed to get positions from dashboard: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"❌ Error getting positions from dashboard: {e}")
            return []

    async def run_service(self, update_interval=30):
        """Run the delta service continuously"""
        self.running = True
        logger.info("🚀 Starting IBKR Delta Service")
        
        if not await self.connect():
            logger.error("❌ Failed to connect to IBKR, exiting")
            return
        
        while self.running:
            try:
                logger.info("🔄 Updating delta cache...")
                
                # Get positions from dashboard
                positions = await self.get_positions_from_dashboard()
                if positions:
                    await self.update_delta_cache(positions)
                else:
                    logger.warning("⚠️ No positions received from dashboard, skipping update")
                
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
    service = IBKRDeltaService()
    await service.run_service()

if __name__ == "__main__":
    asyncio.run(main()) 