# 📊 ORB-15 Momentum Strategy - Technical Details

## 🎯 Strategy Overview

The ORB-15 Momentum strategy is designed to capture intraday momentum following the establishment of an opening range. This document provides detailed technical specifications and implementation details.

## 🕐 Time Management & Timezone Handling

### Critical Timezone Considerations
- **Market Timezone**: Eastern Time (ET) - Market operates 9:30 AM - 4:00 PM ET
- **System Timezone**: Automatically detected and converted to ET
- **Argentina Timezone**: GMT-3 (handled automatically)

### Time Windows
```python
# Opening Range Window
orb_start = time(9, 30)  # 9:30 AM ET
orb_end = time(9, 45)    # 9:45 AM ET (15 minutes)

# Trading Window  
trade_start = time(9, 45)  # After ORB establishment
trade_end = time(15, 0)    # 3:00 PM ET (force close)

# Market Close
market_close = time(16, 0)  # 4:00 PM ET
```

## 📈 Candle Aggregation Process

### Real-time Bar Processing
The system receives 5-second bars from IBKR and aggregates them into 15-minute candles:

```python
def aggregate_to_15min_candle(self, bar):
    bar_time = bar.time.astimezone(self.ny_tz)
    
    # Calculate 15-minute window
    minute = bar_time.minute
    candle_minute = (minute // 15) * 15
    candle_time = bar_time.replace(minute=candle_minute, second=0, microsecond=0)
    
    # Update or create candle
    if self.candle_start_time != candle_time:
        # Complete previous candle and start new one
        completed_candle = self.finalize_candle()
        self.start_new_candle(bar, candle_time)
        return completed_candle
    else:
        # Update current candle
        self.update_current_candle(bar)
        return None
```

### Candle Data Structure
```python
candle = {
    'timestamp': datetime,  # 15-minute boundary (9:30, 9:45, 10:00, etc.)
    'open': float,         # First price in 15-min window
    'high': float,         # Highest price in window  
    'low': float,          # Lowest price in window
    'close': float,        # Last price in window
    'volume': int          # Total volume in window
}
```

## 🎯 Signal Generation

### Opening Range Calculation
```python
def calculate_opening_range(self, candles):
    # Get candles from 9:30-9:45 ET
    orb_candles = []
    for candle in candles:
        if candle_time.hour == 9 and candle_time.minute == 30:
            orb_candles.append(candle)
    
    if orb_candles:
        orb_high = max(candle['high'] for candle in orb_candles)
        orb_low = min(candle['low'] for candle in orb_candles)
        return ORBRange(high=orb_high, low=orb_low)
```

### Breakout Detection
```python
def check_breakout_signal(self, current_candle):
    # Entry signal: 15-min candle closes above ORB high
    close_price = current_candle['close']
    return close_price > self.opening_range.high
```

## 💰 Position Sizing Algorithm

### Fixed Dollar Amount Method
```python
def calculate_position_size(self, entry_price):
    # Fixed dollar amount approach
    shares = int(self.max_position_size / entry_price)
    return max(1, shares)  # Minimum 1 share

# Example with NVDA @ $153
max_position = 1000.0
shares = int(1000 / 153) = 6 shares
actual_position = 6 * 153 = $918
```

### Risk Calculation
```python
def calculate_risk_reward(self, entry_price, shares):
    stop_price = entry_price * (1 + self.stop_loss_pct)  # -1%
    target_price = entry_price * (1 + self.take_profit_pct)  # +4%
    
    risk_amount = (entry_price - stop_price) * shares
    reward_amount = (target_price - entry_price) * shares
    
    rr_ratio = reward_amount / risk_amount  # Should be ~4:1
```

## 🛡️ Order Management

### Entry Order
```python
# Market order for immediate execution
entry_order = MarketOrder('BUY', shares)
```

### Protection Orders (OCO Bracket)
```python
# Create OCA group for linked orders
oca_group = f"ORB_NVDA_{timestamp}"

# Stop loss order
stop_order = StopOrder('SELL', shares, stop_price)
stop_order.ocaGroup = oca_group
stop_order.ocaType = 1  # Cancel remaining when one fills

# Take profit order  
tp_order = LimitOrder('SELL', shares, target_price)
tp_order.ocaGroup = oca_group
tp_order.ocaType = 1
```

## 📊 State Management

### Trading States
```python
class TradingState:
    WAITING_FOR_MARKET = "waiting"
    BUILDING_ORB = "building_orb"      # 9:30-9:45
    LOOKING_FOR_SIGNAL = "scanning"   # 9:45-15:00
    POSITION_OPEN = "in_trade"
    TIME_EXIT = "closing"              # 15:00
    MARKET_CLOSED = "closed"
```

### Daily Reset Logic
```python
def reset_daily_state(self):
    # Reset at start of new trading day
    self.opening_range = None
    self.trade_executed = False
    self.current_trade = None
    self.candle_history.clear()
    
    # Log the reset
    logger.info("🔄 ORB Strategy state reset for new day")
```

## 🔍 Data Quality & Validation

### Market Data Validation
```python
def validate_market_data(self, ticker):
    # Check for real-time data
    has_bid = ticker.bid and ticker.bid > 0
    has_ask = ticker.ask and ticker.ask > 0
    has_last = ticker.last and ticker.last > 0
    
    return has_bid and has_ask and has_last
```

### Symbol Qualification
```python
def qualify_symbol(self, symbol):
    # Minimum criteria for trading
    checks = [
        self.is_liquid_enough(symbol),      # Volume > threshold
        self.price_in_range(symbol),        # $50-$1000 typical range
        self.market_hours_active(),         # During RTH only
        self.has_realtime_data(symbol)      # Not delayed/stale
    ]
    return all(checks)
```

## 📈 Performance Tracking

### Trade Metrics
```python
@dataclass
class TradeMetrics:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    return_pct: float
    exit_reason: str  # 'STOP_LOSS', 'TAKE_PROFIT', 'TIME_EXIT'
    hold_duration: timedelta
    orb_high: float  # Reference ORB high for analysis
```

### Daily Statistics
```python
def calculate_daily_stats(self, trades):
    return {
        'total_trades': len(trades),
        'wins': len([t for t in trades if t.pnl > 0]),
        'losses': len([t for t in trades if t.pnl < 0]),
        'win_rate': wins / total_trades,
        'total_pnl': sum(t.pnl for t in trades),
        'avg_winner': mean([t.pnl for t in trades if t.pnl > 0]),
        'avg_loser': mean([t.pnl for t in trades if t.pnl < 0]),
        'largest_win': max(t.pnl for t in trades),
        'largest_loss': min(t.pnl for t in trades)
    }
```

## 🚨 Error Handling & Recovery

### Connection Management
```python
async def handle_connection_loss(self):
    logger.warning("🔌 Connection lost - attempting reconnect")
    
    for attempt in range(3):
        try:
            await self.ib.connectAsync(self.host, self.port, self.client_id)
            if self.ib.isConnected():
                logger.info(f"✅ Reconnected on attempt {attempt + 1}")
                await self.restore_market_data()
                return True
        except Exception as e:
            logger.error(f"Reconnect attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(5)
    
    return False
```

### Position Recovery
```python
async def restore_positions_on_startup(self):
    # Check for existing positions from previous session
    portfolio = self.ib.portfolio()
    for position in portfolio:
        if position.contract.symbol == self.config.symbol:
            logger.warning(f"🔄 Found existing position: {position}")
            await self.restore_protection_orders(position)
```

## 📝 Logging Architecture

### Structured Logging
```python
# Trade events
logger.info(f"📊 ORB Range: High=${orb_high:.2f}, Low=${orb_low:.2f}")
logger.info(f"🚀 Breakout Signal: Entry=${entry:.2f}")
logger.info(f"✅ Position filled: {shares} shares @ ${fill_price:.2f}")
logger.info(f"🛡️ Protection orders placed: SL=${stop:.2f}, TP=${target:.2f}")

# Performance metrics
logger.info(f"💰 Trade closed: P&L=${pnl:.2f} ({return_pct:.1f}%)")
logger.info(f"⏱️ Hold time: {duration}")
```

### Log Categories
- **Trade Execution**: Entry/exit events
- **Market Data**: Price updates, data quality
- **Risk Management**: Stop/target hits
- **System Events**: Connections, errors
- **Performance**: Daily/weekly summaries

## 🔧 Configuration Management

### Hierarchical Configuration
```python
# Priority order (highest to lowest):
1. Command line arguments    (--max-position 1500)
2. Environment variables     (ORB_MAX_POSITION=1500)  
3. JSON config file         (configs/orb_config.json)
4. Default values           (Built into code)
```

### Dynamic Updates
```python
# Save runtime changes to config
def save_current_config(self):
    config_data = {
        'symbol': self.symbol,
        'max_position_size': self.max_position_size,
        'stop_loss_pct': self.stop_loss_pct,
        'take_profit_pct': self.take_profit_pct
    }
    
    with open('configs/orb_config.json', 'w') as f:
        json.dump(config_data, f, indent=2)
```

## 🧪 Testing Framework

### Simulation Testing
```python
# Run strategy against historical data
def run_simulation(self, historical_data):
    strategy = ORBStrategy()
    results = []
    
    for date, day_data in historical_data.groupby('date'):
        strategy.reset_daily_state()
        
        for candle in day_data.itertuples():
            signal = strategy.analyze_candle(candle)
            if signal:
                result = self.simulate_trade(signal, day_data)
                results.append(result)
    
    return self.calculate_performance_metrics(results)
```

---

**Last Updated**: July 2025  
**Version**: 1.0.0