#!/usr/bin/env python3
"""
Test script to verify NVDA data reception from IBKR
"""

import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from ib_insync import IB, Stock, util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(f'logs/test_nvda_data_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class NVDADataTester:
    def __init__(self):
        self.ib = IB()
        self.ny_tz = pytz.timezone('America/New_York')
        self.bars_received = 0
        self.tickers_received = 0
        self.running = True
        
    async def connect(self):
        """Connect to IBKR"""
        try:
            # Try both paper and live trading ports
            for port in [7497, 7496]:
                try:
                    logger.info(f"🔌 Attempting connection to IBKR on port {port}")
                    await self.ib.connectAsync('127.0.0.1', port, clientId=10)
                    if self.ib.isConnected():
                        logger.info(f"✅ Connected to IBKR on port {port}")
                        return True
                except Exception as e:
                    logger.warning(f"❌ Failed to connect on port {port}: {e}")
                    continue
                    
            logger.error("❌ Could not connect to IBKR on any port")
            return False
            
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
            
    async def test_nvda_data(self):
        """Test NVDA market data reception"""
        try:
            # Create NVDA contract
            nvda_contract = Stock('NVDA', 'SMART', 'USD')
            logger.info(f"📊 Created NVDA contract: {nvda_contract}")
            
            # Get contract details
            contract_details = self.ib.reqContractDetails(nvda_contract)
            if contract_details:
                logger.info(f"✅ NVDA contract details found: {contract_details[0].contract}")
            else:
                logger.warning("⚠️ No contract details found for NVDA")
            
            # Request market data
            logger.info("📈 Requesting market data for NVDA...")
            ticker = self.ib.reqMktData(nvda_contract, '', False, False)
            logger.info(f"📊 Ticker object: {ticker}")
            
            # Wait for initial market data
            await asyncio.sleep(3)
            
            # Check ticker data
            if ticker.last:
                logger.info(f"✅ NVDA Price Data Available:")
                logger.info(f"   Last: ${ticker.last:.2f}")
                logger.info(f"   Bid: ${ticker.bid:.2f}")
                logger.info(f"   Ask: ${ticker.ask:.2f}")
                logger.info(f"   Volume: {ticker.volume:,}")
            else:
                logger.warning("⚠️ No NVDA price data received yet")
                
            # Subscribe to real-time bars
            logger.info("📊 Subscribing to real-time 5-second bars...")
            
            def on_bar_update(bars, hasNewBar):
                if hasNewBar:
                    self.bars_received += 1
                    bar = bars[-1]
                    logger.info(f"📊 Bar #{self.bars_received}: Time={bar.time}, O={bar.open_}, H={bar.high}, L={bar.low}, C={bar.close}, V={bar.volume}")
                    
            # Subscribe to bar updates
            self.ib.barUpdateEvent += on_bar_update
            bars_subscription = self.ib.reqRealTimeBars(nvda_contract, 5, 'TRADES', False)
            logger.info(f"📈 Bars subscription: {bars_subscription}")
            
            # Monitor data for 30 seconds
            logger.info("⏳ Monitoring NVDA data for 30 seconds...")
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < 30:
                # Update ticker info
                ticker = self.ib.ticker(nvda_contract)
                if ticker and ticker.last:
                    self.tickers_received += 1
                    if self.tickers_received % 10 == 0:
                        logger.info(f"💰 NVDA Price Update #{self.tickers_received}: ${ticker.last:.2f} (Volume: {ticker.volume:,})")
                
                await asyncio.sleep(1)
            
            # Summary
            logger.info(f"📊 Test Summary:")
            logger.info(f"   Real-time bars received: {self.bars_received}")
            logger.info(f"   Ticker updates received: {self.tickers_received}")
            
            if self.bars_received > 0:
                logger.info("✅ SUCCESS: Real-time bars are being received")
            else:
                logger.error("❌ PROBLEM: No real-time bars received")
                
            if self.tickers_received > 0:
                logger.info("✅ SUCCESS: Ticker data is being received")
            else:
                logger.error("❌ PROBLEM: No ticker data received")
                
        except Exception as e:
            logger.error(f"❌ Error testing NVDA data: {e}")
            
    async def run(self):
        """Main test function"""
        logger.info("🚀 Starting NVDA Data Test")
        logger.info(f"📅 Current time: {datetime.now(self.ny_tz)}")
        
        try:
            # Connect
            if not await self.connect():
                logger.error("Failed to connect to IBKR")
                return
                
            # Test data
            await self.test_nvda_data()
            
        except KeyboardInterrupt:
            logger.info("⛔ Test interrupted by user")
        except Exception as e:
            logger.error(f"❌ Test error: {e}")
        finally:
            if self.ib.isConnected():
                self.ib.disconnect()
                logger.info("👋 Disconnected from IBKR")

async def main():
    tester = NVDADataTester()
    await tester.run()

if __name__ == "__main__":
    asyncio.run(main())