#!/usr/bin/env python3
"""
ORB Trader Simplificado - Versión para Testing
Conecta a IBKR y ejecuta estrategia ORB con configuración conservadora
"""

import asyncio
import logging
import sys
import signal
from datetime import datetime, time
from ib_insync import IB, Stock, MarketOrder, StopOrder, LimitOrder
from src.strategies.orb_strategy import ORBStrategy, ORBSetup
from src.core.orb_config import ORBConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(f'logs/orb_simple_{datetime.now().strftime("%Y-%m-%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class SimpleORBTrader:
    """ORB Trader Simplificado para Testing"""
    
    def __init__(self):
        # Cargar configuración
        self.config = ORBConfig.load_from_file()
        
        # Initialize components
        self.ib = IB()
        
        # Create strategy
        setup = ORBSetup(
            symbol=self.config.symbol,
            orb_minutes=self.config.orb_minutes,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_ratio=self.config.take_profit_ratio,
            max_position_size=self.config.max_position_size
        )
        self.strategy = ORBStrategy(setup)
        
        # Trading state
        self.nvda_contract = None
        self.current_trade = None
        self.running = False
        
        # ORB-specific tracking (ISOLATION)
        self.orb_order_tag = "ORB_STRATEGY"  # Tag único para identificar órdenes ORB
        self.orb_orders = {}  # Track solo órdenes ORB: {order_id: order_info}
        self.initial_nvda_position = 0  # Posición inicial de NVDA (no-ORB)
        self.orb_position_size = 0  # Solo posición creada por ORB
        
        # Candle aggregation
        self.current_candle = None
        self.candle_start_time = None
        
    async def connect(self):
        """Connect to IBKR"""
        try:
            logger.info(f"🔌 Connecting to IBKR at {self.config.ibkr_host}:{self.config.ibkr_port}")
            await self.ib.connectAsync(
                self.config.ibkr_host, 
                self.config.ibkr_port, 
                clientId=self.config.ibkr_client_id
            )
            
            if self.ib.isConnected():
                logger.info("✅ Connected to IBKR successfully")
                
                # Setup NVDA contract
                self.nvda_contract = Stock(self.config.symbol, 'SMART', 'USD')
                
                # 🔍 CAPTURE INITIAL POSITIONS - CRITICAL FOR ISOLATION
                await self.capture_initial_positions()
                
                # Request market data
                self.ib.reqMktData(self.nvda_contract, '', False, False)
                logger.info(f"📊 Market data requested for {self.config.symbol}")
                
                return True
            else:
                logger.error("❌ Failed to connect to IBKR")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    def display_config(self):
        """Display current configuration"""
        print("\n" + "="*60)
        print("🚀 ORB SIMPLE TRADER - LIVE CONFIGURATION")
        print("="*60)
        print(f"Symbol: {self.config.symbol}")
        print(f"Max Position: ${self.config.max_position_size:,.0f}")
        print(f"Stop Loss: {self.config.stop_loss_pct*100:.1f}%")
        print(f"Take Profit Ratio: 1:{self.config.take_profit_ratio:.1f}")
        print(f"Max Daily Loss: ${self.config.max_daily_loss:,.0f}")
        print(f"Connection: {self.config.ibkr_host}:{self.config.ibkr_port}")
        print(f"Market Hours Only: 9:30 AM - 4:00 PM EST")
        print(f"ORB Window: 9:30 AM - 9:45 AM EST")
        print(f"Force Close: 3:00 PM EST")
        print("")
        print("🔒 POSITION ISOLATION:")
        print(f"   ✅ Only trades tagged '{self.orb_order_tag}' will be managed")
        print(f"   ✅ Existing positions will be ignored")
        print(f"   ✅ ORB P&L calculated separately")
        print("="*60)
    
    async def capture_initial_positions(self):
        """🔍 Capture existing positions to isolate ORB trades"""
        try:
            # Wait for portfolio to update
            await asyncio.sleep(2)
            
            # Get current positions
            positions = self.ib.positions()
            
            # Find existing NVDA position (if any)
            for position in positions:
                if (position.contract.symbol == self.config.symbol and 
                    position.contract.secType == 'STK'):
                    self.initial_nvda_position = position.position
                    logger.info(f"🔍 ISOLATION: Found existing {self.config.symbol} position: {self.initial_nvda_position} shares")
                    break
            
            if self.initial_nvda_position == 0:
                logger.info(f"🔍 ISOLATION: No existing {self.config.symbol} position found - starting clean")
            
            # Log all other positions for reference
            other_positions = [p for p in positions if p.contract.symbol != self.config.symbol and p.position != 0]
            if other_positions:
                logger.info("📊 OTHER POSITIONS (not managed by ORB):")
                for pos in other_positions:
                    logger.info(f"   {pos.contract.symbol}: {pos.position} shares @ ${pos.avgCost:.2f}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not capture initial positions: {e}")
            self.initial_nvda_position = 0
    
    def get_orb_position_size(self):
        """📊 Calculate ORB-only position size"""
        try:
            # Get current NVDA position
            positions = self.ib.positions()
            current_nvda_position = 0
            
            for position in positions:
                if (position.contract.symbol == self.config.symbol and 
                    position.contract.secType == 'STK'):
                    current_nvda_position = position.position
                    break
            
            # ORB position = Current - Initial
            self.orb_position_size = current_nvda_position - self.initial_nvda_position
            return self.orb_position_size
            
        except Exception as e:
            logger.warning(f"Error getting ORB position size: {e}")
            return 0
    
    def is_orb_order(self, order_id):
        """🏷️ Check if order belongs to ORB strategy"""
        return order_id in self.orb_orders
    
    async def get_current_price(self):
        """Get current NVDA price"""
        try:
            ticker = self.ib.ticker(self.nvda_contract)
            if ticker and ticker.last > 0:
                return ticker.last
            return None
        except Exception as e:
            logger.warning(f"Error getting price: {e}")
            return None
    
    async def place_orb_trade(self, signal):
        """🏷️ Place ORB trade with isolation tags"""
        try:
            trade = signal['trade']
            logger.info(f"🚀 Placing ORB trade: {trade.shares} shares at ${trade.entry_price:.2f}")
            
            # Create market order for entry with ORB tag
            entry_order = MarketOrder('BUY', trade.shares)
            entry_order.orderRef = f"{self.orb_order_tag}_{datetime.now().strftime('%H%M%S')}"
            
            entry_trade = self.ib.placeOrder(self.nvda_contract, entry_order)
            
            # 🏷️ TRACK ORB ORDER
            self.orb_orders[entry_trade.order.orderId] = {
                'type': 'ENTRY',
                'symbol': self.config.symbol,
                'shares': trade.shares,
                'timestamp': datetime.now(),
                'order_ref': entry_order.orderRef
            }
            
            logger.info(f"🏷️ ORB order tagged: ID={entry_trade.order.orderId}, Ref={entry_order.orderRef}")
            
            # Wait for fill
            await asyncio.sleep(2)
            
            if entry_trade.orderStatus.status in ['Filled', 'PartiallyFilled']:
                fill_price = entry_trade.orderStatus.avgFillPrice or trade.entry_price
                logger.info(f"✅ ORB Entry filled at ${fill_price:.2f}")
                
                # Update ORB position tracking
                self.orb_position_size = trade.shares
                
                # Place protection orders
                await self.place_protection_orders(trade, fill_price)
                
                self.current_trade = trade
                return True
            else:
                logger.error(f"❌ ORB Entry order not filled: {entry_trade.orderStatus.status}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error placing ORB trade: {e}")
            return False
    
    async def place_protection_orders(self, trade, actual_fill_price):
        """🏷️ Place stop loss and take profit orders with ORB tags"""
        try:
            # Recalculate stops based on actual fill
            actual_stop = actual_fill_price * (1 + self.config.stop_loss_pct)
            actual_target = actual_fill_price * (1 + abs(self.config.stop_loss_pct) * self.config.take_profit_ratio)
            
            # Create OCA group with ORB tag
            oca_group = f"ORB_{self.config.symbol}_{datetime.now().strftime('%H%M%S')}"
            
            # Stop loss order with ORB tag
            stop_order = StopOrder('SELL', trade.shares, actual_stop)
            stop_order.ocaGroup = oca_group
            stop_order.ocaType = 1
            stop_order.orderRef = f"{self.orb_order_tag}_STOP"
            
            # Take profit order with ORB tag
            tp_order = LimitOrder('SELL', trade.shares, actual_target)
            tp_order.ocaGroup = oca_group
            tp_order.ocaType = 1
            tp_order.orderRef = f"{self.orb_order_tag}_TARGET"
            
            # Place orders
            stop_trade = self.ib.placeOrder(self.nvda_contract, stop_order)
            tp_trade = self.ib.placeOrder(self.nvda_contract, tp_order)
            
            # 🏷️ TRACK ORB PROTECTION ORDERS
            self.orb_orders[stop_trade.order.orderId] = {
                'type': 'STOP_LOSS',
                'symbol': self.config.symbol,
                'shares': trade.shares,
                'price': actual_stop,
                'timestamp': datetime.now(),
                'order_ref': stop_order.orderRef
            }
            
            self.orb_orders[tp_trade.order.orderId] = {
                'type': 'TAKE_PROFIT',
                'symbol': self.config.symbol,
                'shares': trade.shares,
                'price': actual_target,
                'timestamp': datetime.now(),
                'order_ref': tp_order.orderRef
            }
            
            logger.info(f"🛡️ ORB Protection orders placed:")
            logger.info(f"   Stop Loss: ${actual_stop:.2f} (ID: {stop_trade.order.orderId})")
            logger.info(f"   Take Profit: ${actual_target:.2f} (ID: {tp_trade.order.orderId})")
            
        except Exception as e:
            logger.error(f"❌ Error placing ORB protection orders: {e}")
    
    async def monitor_market(self):
        """Monitor market for ORB signals"""
        logger.info("📊 Starting market monitoring for ORB signals...")
        
        while self.running:
            try:
                current_time = datetime.now().time()
                
                # Check if market is open
                if not self.strategy.is_market_open():
                    logger.info("🔒 Market is closed - waiting...")
                    await asyncio.sleep(60)
                    continue
                
                # Get current price
                current_price = await self.get_current_price()
                if not current_price:
                    await asyncio.sleep(5)
                    continue
                
                # Create mock candle for testing (in real implementation, aggregate from real-time bars)
                mock_candle = {
                    'timestamp': datetime.now(),
                    'open': current_price,
                    'high': current_price,
                    'low': current_price,
                    'close': current_price,
                    'volume': 1000000
                }
                
                # Analyze for signals
                signal = self.strategy.analyze_tick(mock_candle)
                
                if signal:
                    action = signal.get('action')
                    
                    if action == 'ORB_ESTABLISHED':
                        logger.info(f"📊 ORB Range established: High=${signal['range_high']:.2f}, Low=${signal['range_low']:.2f}")
                        
                    elif action == 'ENTER_LONG' and not self.current_trade:
                        logger.info(f"🎯 ORB Breakout Signal detected at ${current_price:.2f}!")
                        success = await self.place_orb_trade(signal)
                        if success:
                            logger.info("✅ ORB trade executed successfully")
                        
                    elif action == 'EXIT_TIME':
                        logger.info("⏰ Time-based exit at 3:00 PM")
                        await self.close_position_by_time()
                
                # Show current status
                if current_time.minute % 5 == 0 and current_time.second < 10:  # Every 5 minutes
                    await self.show_status(current_price)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in market monitoring: {e}")
                await asyncio.sleep(10)
    
    async def show_status(self, current_price):
        """📊 Show current ORB trading status (isolated from other positions)"""
        logger.info(f"📈 ORB Status: {self.config.symbol} @ ${current_price:.2f}")
        
        # ORB Range status
        if self.strategy.opening_range:
            logger.info(f"   ORB High: ${self.strategy.opening_range.high:.2f}")
            logger.info(f"   ORB Low: ${self.strategy.opening_range.low:.2f}")
        else:
            logger.info("   Waiting for ORB establishment...")
        
        # ORB Position status (isolated)
        orb_position = self.get_orb_position_size()
        if orb_position > 0 and self.current_trade:
            shares = self.current_trade.shares
            entry_price = self.current_trade.entry_price
            pnl = (current_price - entry_price) * shares
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            logger.info(f"   🏷️ ORB Position: {shares} shares @ ${entry_price:.2f}")
            logger.info(f"   💰 ORB P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")
        else:
            logger.info("   🏷️ ORB Position: None")
        
        # Show isolation info
        if self.initial_nvda_position != 0:
            logger.info(f"   📊 Non-ORB NVDA: {self.initial_nvda_position} shares (not managed)")
    
    async def close_position_by_time(self):
        """Close position at 3:00 PM"""
        try:
            if not self.current_trade:
                return
            
            logger.info("⏰ Closing position at 3:00 PM EST")
            
            # Place market order to close
            close_order = MarketOrder('SELL', self.current_trade.shares)
            close_trade = self.ib.placeOrder(self.nvda_contract, close_order)
            
            # Wait for fill
            await asyncio.sleep(2)
            
            if close_trade.orderStatus.status in ['Filled', 'PartiallyFilled']:
                exit_price = close_trade.orderStatus.avgFillPrice
                pnl = (exit_price - self.current_trade.entry_price) * self.current_trade.shares
                logger.info(f"✅ Position closed at ${exit_price:.2f}")
                logger.info(f"💰 Final P&L: ${pnl:+.2f}")
                
                self.current_trade = None
            
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
    
    async def run(self):
        """Main trading loop"""
        self.display_config()
        
        # Connect to IBKR
        connected = await self.connect()
        if not connected:
            logger.error("Failed to connect. Exiting.")
            return
        
        try:
            self.running = True
            logger.info("🚀 ORB Simple Trader started successfully!")
            logger.info("📊 Monitoring market for ORB signals...")
            
            await self.monitor_market()
            
        except KeyboardInterrupt:
            logger.info("⛔ Shutdown requested")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up...")
        
        if self.current_trade:
            logger.warning("⚠️ Open position detected during shutdown")
            await self.close_position_by_time()
        
        if self.ib.isConnected():
            if self.nvda_contract:
                self.ib.cancelMktData(self.nvda_contract)
            self.ib.disconnect()
            logger.info("👋 Disconnected from IBKR")
        
        logger.info("✅ Cleanup complete")

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("⛔ Shutdown signal received")
    sys.exit(0)

async def main():
    """Main function"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run trader
    trader = SimpleORBTrader()
    await trader.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 ORB Simple Trader shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)