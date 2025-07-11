#!/usr/bin/env python3
"""
ORB (Opening Range Breakout) Trader for NVDA
Executes 15-minute ORB strategy during RTH
"""

import asyncio
import logging
import sys
import signal
from datetime import datetime, time, timedelta
from typing import Optional, Dict, List
import pytz
from ib_insync import Stock, MarketOrder, StopOrder, LimitOrder, IB, util

# Import our modules
from src.strategies.orb_strategy import ORBStrategy, ORBSetup, ORBTrade
from src.core.postgresql_storage import PostgreSQLStorage
from src.core.trade_logger import TradeLogger, TradeAction
from src.utils.position_tracker import PositionTracker
from src.core.advanced_logger import get_logger, get_performance_logger
from src.utils.volume_data_provider import VolumeDataProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(f'logs/orb_trader_{datetime.now().strftime("%Y-%m-%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ORBTrader:
    """ORB Trading System for NVDA"""
    
    def __init__(self):
        self.running = True
        self.ny_tz = pytz.timezone('America/New_York')
        
        # Initialize components
        self.ib = IB()
        self.strategy = ORBStrategy(ORBSetup())
        self.storage = PostgreSQLStorage("ORB_NVDA")
        self.trade_logger = TradeLogger()
        self.position_tracker = PositionTracker()
        self.volume_provider = VolumeDataProvider()
        
        # IBKR connection settings
        self.host = '127.0.0.1'
        self.port = 7496  # TWS paper trading port
        self.client_id = 5  # Different from trading console (3,4)
        
        # Trading state
        self.active_order = None
        self.active_position = None
        self.protection_orders = {}
        self.last_candle_time = None
        
        # Candle aggregation
        self.current_candle = None
        self.candle_start_time = None
        
    async def connect(self) -> bool:
        """Connect to IBKR"""
        try:
            logger.info(f"🔌 Connecting to IBKR at {self.host}:{self.port} (Client ID: {self.client_id})")
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            
            if self.ib.isConnected():
                logger.info("✅ Connected to IBKR successfully")
                
                # Request market data for NVDA
                self.nvda_contract = Stock('NVDA', 'SMART', 'USD')
                logger.info(f"📊 Requesting market data for {self.nvda_contract}")
                self.ib.reqMktData(self.nvda_contract, '', False, False)
                
                # Subscribe to real-time bars (5 second bars)
                logger.info("📈 Subscribing to real-time 5-second bars for NVDA")
                bars_subscription = self.ib.reqRealTimeBars(self.nvda_contract, 5, 'TRADES', False)
                logger.info(f"📊 Bars subscription: {bars_subscription}")
                
                # Wait a moment to check if we're receiving data
                await asyncio.sleep(2)
                
                return True
            else:
                logger.error("❌ Failed to connect to IBKR")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
            
    async def disconnect(self):
        """Disconnect from IBKR"""
        try:
            if self.ib.isConnected():
                # Cancel market data
                self.ib.cancelMktData(self.nvda_contract)
                self.ib.cancelRealTimeBars(self.nvda_contract)
                
                # Disconnect
                self.ib.disconnect()
                logger.info("👋 Disconnected from IBKR")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            
    def aggregate_to_15min_candle(self, bar) -> Optional[Dict]:
        """Aggregate 5-second bars into 15-minute candles"""
        bar_time = bar.time
        if bar_time.tzinfo is None:
            bar_time = self.ny_tz.localize(bar_time)
        else:
            bar_time = bar_time.astimezone(self.ny_tz)
            
        # Calculate 15-minute window
        minute = bar_time.minute
        candle_minute = (minute // 15) * 15
        candle_time = bar_time.replace(minute=candle_minute, second=0, microsecond=0)
        
        # Initialize new candle if needed
        if self.candle_start_time != candle_time:
            # Complete previous candle if exists
            completed_candle = None
            if self.current_candle and self.candle_start_time:
                completed_candle = self.current_candle.copy()
                completed_candle['timestamp'] = self.candle_start_time
                
            # Start new candle
            self.candle_start_time = candle_time
            self.current_candle = {
                'open': bar.open_,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'timestamp': candle_time
            }
            
            return completed_candle
            
        # Update current candle
        if self.current_candle:
            self.current_candle['high'] = max(self.current_candle['high'], bar.high)
            self.current_candle['low'] = min(self.current_candle['low'], bar.low)
            self.current_candle['close'] = bar.close
            self.current_candle['volume'] += bar.volume
            
        return None
        
    async def place_orb_trade(self, trade: ORBTrade):
        """Place ORB trade with stop loss and take profit"""
        try:
            logger.info(f"📈 Placing ORB trade: {trade.shares} shares at ${trade.entry_price:.2f}")
            
            # Create market order for entry
            entry_order = MarketOrder('BUY', trade.shares)
            entry_trade = self.ib.placeOrder(self.nvda_contract, entry_order)
            
            # Wait for fill
            await asyncio.sleep(1)
            
            if entry_trade.orderStatus.status == 'Filled':
                fill_price = entry_trade.orderStatus.avgFillPrice
                logger.info(f"✅ Entry filled at ${fill_price:.2f}")
                
                # Update position tracker
                self.position_tracker.add_position(
                    symbol='NVDA',
                    shares=trade.shares,
                    entry_price=fill_price,
                    stop_price=trade.stop_price,
                    target_price=trade.target_price,
                    strategy='ORB'
                )
                
                # Place OCO bracket order for exit
                await self.place_protection_orders(trade)
                
                # Log to database
                if self.storage and self.storage.connected:
                    self.storage.record_trade(
                        symbol='NVDA',
                        entry_price=fill_price,
                        shares=trade.shares,
                        trade_type='LONG',
                        stop_price=trade.stop_price,
                        target_price=trade.target_price,
                        strategy_params={
                            'orb_high': trade.range_high,
                            'entry_time': trade.entry_time.isoformat()
                        }
                    )
                    
                self.active_position = trade
                return True
            else:
                logger.error(f"❌ Entry order not filled: {entry_trade.orderStatus.status}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error placing trade: {e}")
            return False
            
    async def place_protection_orders(self, trade: ORBTrade):
        """Place stop loss and take profit orders"""
        try:
            # Create OCA group for stop and target
            oca_group = f"ORB_NVDA_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Stop loss order
            stop_order = StopOrder('SELL', trade.shares, trade.stop_price)
            stop_order.ocaGroup = oca_group
            stop_order.ocaType = 1  # Cancel all remaining orders with block
            
            # Take profit order
            tp_order = LimitOrder('SELL', trade.shares, trade.target_price)
            tp_order.ocaGroup = oca_group
            tp_order.ocaType = 1
            
            # Place orders
            stop_trade = self.ib.placeOrder(self.nvda_contract, stop_order)
            tp_trade = self.ib.placeOrder(self.nvda_contract, tp_order)
            
            self.protection_orders = {
                'stop': stop_trade,
                'target': tp_trade
            }
            
            logger.info(f"🛡️ Protection orders placed: Stop=${trade.stop_price:.2f}, Target=${trade.target_price:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Error placing protection orders: {e}")
    
    async def initialize_volume_data(self):
        """Initialize historical volume data for the strategy"""
        try:
            logger.info("📊 Initializing volume data from Yahoo Finance...")
            
            # Get 20-day average volume for NVDA
            avg_volume = await asyncio.get_event_loop().run_in_executor(
                None, 
                self.volume_provider.get_20_day_average_volume, 
                'NVDA'
            )
            
            if avg_volume > 0:
                # Set the volume data in the strategy
                self.strategy.set_historical_volume(avg_volume)
                logger.info(f"✅ Volume data initialized: 20-day average = {avg_volume:,}")
            else:
                logger.error("❌ Failed to get volume data from Yahoo Finance")
                
        except Exception as e:
            logger.error(f"❌ Error initializing volume data: {e}")
            
    async def close_position_by_time(self):
        """Close position at 3:00 PM"""
        try:
            if not self.active_position:
                return
                
            logger.info("⏰ Closing position at 3:00 PM")
            
            # Cancel protection orders
            for order_type, trade in self.protection_orders.items():
                if trade.order.orderId:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"🚫 Cancelled {order_type} order")
                    
            # Place market order to close
            close_order = MarketOrder('SELL', self.active_position.shares)
            close_trade = self.ib.placeOrder(self.nvda_contract, close_order)
            
            # Wait for fill
            await asyncio.sleep(1)
            
            if close_trade.orderStatus.status == 'Filled':
                exit_price = close_trade.orderStatus.avgFillPrice
                logger.info(f"✅ Position closed at ${exit_price:.2f}")
                
                # Update position tracker
                self.position_tracker.close_position('NVDA', exit_price, 'TIME_EXIT')
                
                # Clear active position
                self.active_position = None
                self.protection_orders.clear()
                
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            
    async def process_market_data(self):
        """Process real-time market data"""
        # Subscribe to real-time bar updates
        self.ib.pendingTickersEvent += self.on_pending_tickers
        
        # Print initial status report
        self.strategy.print_daily_status()
        
        last_status_time = datetime.now()
        status_interval = timedelta(minutes=30)  # Print status every 30 minutes
        
        bars = []
        bars_received = 0
        
        def on_bar_update(bars_, hasNewBar):
            nonlocal bars_received
            if hasNewBar:
                bar = bars_[-1]
                bars.append(bar)
                bars_received += 1
                if bars_received <= 5:  # Log first 5 bars for debugging
                    logger.info(f"📊 Bar #{bars_received} received: Time={bar.time}, Open={bar.open_}, High={bar.high}, Low={bar.low}, Close={bar.close}, Volume={bar.volume}")
                elif bars_received % 100 == 0:  # Log every 100th bar
                    logger.info(f"📊 {bars_received} bars received so far")
                
        self.ib.barUpdateEvent += on_bar_update
        logger.info("✅ Bar update event handler registered")
        
        while self.running:
            try:
                # Process new bars
                if bars:
                    bar = bars.pop(0)
                    
                    # Aggregate to 15-minute candle
                    completed_candle = self.aggregate_to_15min_candle(bar)
                    
                    if completed_candle:
                        logger.info(f"📊 15-min candle completed: Time={completed_candle['timestamp']}, O={completed_candle['open']:.2f}, H={completed_candle['high']:.2f}, L={completed_candle['low']:.2f}, C={completed_candle['close']:.2f}, V={completed_candle['volume']:,}")
                        
                        # Analyze completed candle
                        signal = self.strategy.analyze_tick(completed_candle)
                        
                        if signal:
                            logger.info(f"🎯 Signal received: {signal}")
                            await self.handle_signal(signal)
                            
                # Check for time-based exit
                if self.active_position and self.strategy.should_close_by_time():
                    await self.close_position_by_time()
                    
                # Print periodic status report
                if datetime.now() - last_status_time >= status_interval:
                    self.strategy.print_daily_status()
                    last_status_time = datetime.now()
                    
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing market data: {e}")
                await asyncio.sleep(1)
                
    def on_pending_tickers(self, tickers):
        """Handle ticker updates"""
        for ticker in tickers:
            if ticker.contract.symbol == 'NVDA':
                # Log current price
                if ticker.last:
                    logger.debug(f"💹 NVDA Ticker: Bid=${ticker.bid:.2f}, Ask=${ticker.ask:.2f}, Last=${ticker.last:.2f}, Volume={ticker.volume}")
                    
    async def handle_signal(self, signal: Dict):
        """Handle trading signals from strategy"""
        action = signal.get('action')
        
        if action == 'ORB_ESTABLISHED':
            logger.info(f"📊 Opening Range established: High=${signal['range_high']:.2f}, Low=${signal['range_low']:.2f}, Volume={signal.get('volume', 0):,}")
            
        elif action == 'ENTER_LONG':
            if not self.active_position:
                trade = signal['trade']
                success = await self.place_orb_trade(trade)
                if success:
                    logger.info(f"🚀 ORB trade executed successfully")
                else:
                    logger.error(f"❌ Failed to execute ORB trade")
                    
        elif action == 'EXIT_TIME':
            await self.close_position_by_time()
            
    async def run(self):
        """Main trading loop"""
        logger.info("🚀 Starting ORB Trader for NVDA")
        
        # Connect to IBKR
        connected = await self.connect()
        if not connected:
            logger.error("Failed to connect to IBKR. Exiting.")
            return
        
        # Initialize volume data
        await self.initialize_volume_data()
            
        try:
            # Wait for market open
            while self.running:
                now_ny = datetime.now(self.ny_tz)
                
                # Check if it's a new day
                if now_ny.time() < time(9, 30) and not self.strategy.opening_range:
                    logger.info(f"⏳ Waiting for market open at 9:30 AM EST... (Current: {now_ny.strftime('%H:%M:%S')})")
                    await asyncio.sleep(30)
                    continue
                    
                # Reset at start of new day
                if now_ny.time() < time(9, 30):
                    self.strategy.reset_daily_state()
                    
                # Check if market is open
                if not self.strategy.is_market_open():
                    logger.info("🔒 Market is closed")
                    await asyncio.sleep(60)
                    continue
                    
                # Process market data during market hours
                logger.info(f"📊 Market is open - monitoring NVDA for ORB setup (Current time: {now_ny.strftime('%H:%M:%S')} ET)")
                
                # Check if we have a valid ticker
                ticker = self.ib.ticker(self.nvda_contract)
                if ticker and ticker.last:
                    logger.info(f"✅ NVDA current price: ${ticker.last:.2f}")
                else:
                    logger.warning("⚠️ No NVDA price data available yet")
                
                await self.process_market_data()
                
        except KeyboardInterrupt:
            logger.info("⛔ Shutdown requested")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            await self.cleanup()
            
    async def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up...")
        
        # Close any open positions
        if self.active_position:
            logger.warning("⚠️ Open position detected during shutdown")
            await self.close_position_by_time()
            
        # Disconnect from IBKR
        await self.disconnect()
        
        # Close storage
        if self.storage:
            self.storage.close()
            
        logger.info("👋 ORB Trader shutdown complete")
        
def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("⛔ Shutdown signal received")
    asyncio.create_task(shutdown())
    
async def shutdown():
    """Graceful shutdown"""
    for task in asyncio.all_tasks():
        task.cancel()
        
def parse_arguments():
    """Parse command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ORB Trading System for NVDA')
    
    # Trading parameters
    parser.add_argument('--symbol', type=str, default='NVDA',
                        help='Symbol to trade (default: NVDA)')
    parser.add_argument('--max-position', type=float, default=1000.0,
                        help='Maximum position size in dollars (default: 1000)')
    parser.add_argument('--stop-loss', type=float, default=-0.01,
                        help='Stop loss percentage (default: -0.01 = -1%%)')
    parser.add_argument('--take-profit', type=float, default=0.04,
                        help='Take profit percentage (default: 0.04 = 4%%)')
    
    # Connection parameters
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='IBKR host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=7496,
                        help='IBKR port (default: 7496 for live)')
    parser.add_argument('--client-id', type=int, default=5,
                        help='IBKR client ID (default: 5)')
    
    # Time parameters
    parser.add_argument('--orb-minutes', type=int, default=15,
                        help='Opening range duration in minutes (default: 15)')
    parser.add_argument('--close-time', type=str, default='15:00',
                        help='Time to close positions (default: 15:00)')
    
    # Other options
    parser.add_argument('--paper', action='store_true',
                        help='Use paper trading port 7497')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to JSON config file (default: configs/orb_config.json)')
    parser.add_argument('--save-config', action='store_true',
                        help='Save current configuration to file')
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse arguments
    args = parse_arguments()
    
    # Configure logging based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load config from file or create default
    from src.core.orb_config import ORBConfig
    
    if args.config:
        config = ORBConfig.load_from_file(args.config)
        logger.info(f"📄 Loaded config from {args.config}")
    else:
        # Try default location
        config = ORBConfig.load_from_file()
    
    # Apply command line overrides (command line takes precedence)
    if args.symbol != 'NVDA':  # Only override if not default
        config.symbol = args.symbol
    if args.max_position != 1000.0:
        config.max_position_size = args.max_position
    if args.stop_loss != -0.01:
        config.stop_loss_pct = args.stop_loss
    if args.take_profit != 0.04:
        config.take_profit_pct = args.take_profit
    if args.host != '127.0.0.1':
        config.ibkr_host = args.host
    if args.paper:
        config.ibkr_port = 7497
    elif args.port != 7496:
        config.ibkr_port = args.port
    if args.client_id != 5:
        config.ibkr_client_id = args.client_id
    if args.orb_minutes != 15:
        config.orb_minutes = args.orb_minutes
    if args.close_time != '15:00':
        config.position_close_time = args.close_time
    
    # Save config if requested
    if args.save_config:
        config.save_to_file()
        logger.info("✅ Configuration saved")
        sys.exit(0)
    
    # Display configuration
    if not args.debug:
        config.display_strategy_summary()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run trader with custom config
    trader = ORBTrader()
    trader.strategy.config = config
    trader.host = config.ibkr_host
    trader.port = config.ibkr_port
    trader.client_id = config.ibkr_client_id
    
    try:
        asyncio.run(trader.run())
    except KeyboardInterrupt:
        logger.info("Shutdown by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)