#!/usr/bin/env python3
"""
Configuration for ORB (Opening Range Breakout) Strategy
"""

from dataclasses import dataclass
from typing import Optional, Dict
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class ORBConfig:
    """ORB Strategy Configuration"""
    
    # Symbol Configuration
    symbol: str = "NVDA"
    
    # Strategy Parameters
    orb_minutes: int = 30  # Opening range duration (9:30-10:00)
    entry_timeframe: int = 5  # 5-second ticks for real-time entry
    stop_loss_pct: float = -0.005  # -0.5% stop loss
    take_profit_ratio: float = 2.0  # 2:1 risk/reward ratio
    volume_multiplier: float = 1.5  # Volume must be 1.5x average
    
    # Position Sizing
    max_position_size: float = 1000.0  # Max $1,000 per trade (conservative start)
    min_shares: int = 1  # Minimum shares to trade
    
    # Time Settings (EST)
    market_open_time: str = "09:30"
    orb_end_time: str = "10:00"  # 30-minute opening range
    entry_start_time: str = "10:00"  # Start looking for entries
    entry_end_time: str = "15:30"  # Stop looking for entries at 3:30 PM
    position_close_time: str = "15:50"  # 3:50 PM forced exit
    market_close_time: str = "16:00"
    
    # Risk Management
    max_daily_trades: int = 2  # Maximum 2 trades per day
    max_daily_loss: float = 50.0  # Max $50 loss per day
    enable_trailing_stop: bool = True  # Move stop to breakeven at 50% target
    
    # IBKR Configuration
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7496  # TWS live trading port
    ibkr_client_id: int = 5  # Unique client ID for ORB
    
    # Data Configuration
    use_realtime_data: bool = True
    bar_size_seconds: int = 5  # 5-second bars for aggregation
    
    # Execution Configuration
    use_market_orders: bool = True  # Use market orders for entry
    use_oco_orders: bool = True  # Use OCO for stop/target
    slippage_buffer: float = 0.01  # 1 cent slippage buffer
    
    # Logging and Monitoring
    log_level: str = "INFO"
    send_notifications: bool = False
    webhook_url: Optional[str] = os.getenv("ORB_WEBHOOK_URL")
    
    # Backtesting Stats (from TrendSpider)
    historical_win_rate: float = 0.55
    historical_rr_ratio: float = 1.48
    historical_max_drawdown: float = -0.152
    historical_total_return: float = 2.34  # 234%
    historical_trade_count: int = 418
    historical_period_months: float = 18.7
    
    def calculate_expected_value(self) -> float:
        """Calculate expected value per trade"""
        risk_amount = abs(self.stop_loss_pct) * self.max_position_size
        reward_amount = risk_amount * self.take_profit_ratio
        
        ev = (self.historical_win_rate * reward_amount) - ((1 - self.historical_win_rate) * risk_amount)
        return ev
        
    def get_risk_reward_ratio(self) -> float:
        """Get risk/reward ratio"""
        return self.take_profit_ratio
        
    def calculate_take_profit_pct(self) -> float:
        """Calculate take profit percentage based on ratio"""
        return abs(self.stop_loss_pct) * self.take_profit_ratio
        
    def validate(self) -> bool:
        """Validate configuration"""
        errors = []
        
        if self.stop_loss_pct >= 0:
            errors.append("Stop loss must be negative")
            
        if self.take_profit_ratio <= 0:
            errors.append("Take profit ratio must be positive")
            
        if self.max_position_size <= 0:
            errors.append("Max position size must be positive")
            
        if self.orb_minutes <= 0 or self.orb_minutes > 30:
            errors.append("ORB minutes must be between 1 and 30")
            
        if errors:
            for error in errors:
                print(f"❌ Config Error: {error}")
            return False
            
        return True
        
    def display_strategy_summary(self):
        """Display strategy configuration summary"""
        print("\n" + "="*60)
        print("🎯 ORB STRATEGY CONFIGURATION")
        print("="*60)
        print(f"Symbol: {self.symbol}")
        print(f"Opening Range: First {self.orb_minutes} minutes")
        print(f"Entry: Close above ORB high")
        print(f"Stop Loss: {self.stop_loss_pct*100:.1f}%")
        print(f"Take Profit Ratio: 1:{self.take_profit_ratio:.1f}")
        print(f"Volume Multiplier: {self.volume_multiplier:.1f}x")
        print(f"Risk/Reward: 1:{self.get_risk_reward_ratio():.1f}")
        print(f"Max Position: ${self.max_position_size:,.0f}")
        print(f"Time Exit: {self.position_close_time}")
        print(f"Max Daily Trades: {self.max_daily_trades}")
        print(f"Max Daily Loss: ${self.max_daily_loss:.0f}")
        print(f"Trailing Stop: {'Enabled' if self.enable_trailing_stop else 'Disabled'}")
        print("\n📊 HISTORICAL PERFORMANCE")
        print(f"Win Rate: {self.historical_win_rate*100:.0f}%")
        print(f"Avg R/R: {self.historical_rr_ratio:.2f}")
        print(f"Max Drawdown: {self.historical_max_drawdown*100:.1f}%")
        print(f"Total Return: {self.historical_total_return*100:.0f}%")
        print(f"Total Trades: {self.historical_trade_count}")
        print(f"Period: {self.historical_period_months:.1f} months")
        print(f"Expected Value/Trade: ${self.calculate_expected_value():.2f}")
        print("\n💰 POSITION SIZING")
        print(f"Max Position: ${self.max_position_size:,.0f}")
        example_price = 153.0  # Current NVDA price as example
        example_shares = int(self.max_position_size / example_price)
        example_value = example_shares * example_price
        example_risk = example_value * abs(self.stop_loss_pct)
        example_reward = example_risk * self.take_profit_ratio
        print(f"Example @ ${example_price}: {example_shares} shares (${example_value:.0f})")
        print(f"Risk per trade: ${example_risk:.2f} ({self.stop_loss_pct*100:.1f}%)")
        take_profit_pct = self.calculate_take_profit_pct()
        print(f"Target per trade: ${example_reward:.2f} ({take_profit_pct*100:.1f}%)")
        print("="*60)
    
    @classmethod
    def load_from_file(cls, config_path: str = None) -> 'ORBConfig':
        """Load configuration from JSON file"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '../../configs/orb_config.json')
        
        config_path = Path(config_path)
        if not config_path.exists():
            print(f"⚠️ Config file not found: {config_path}")
            return cls()
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Create config instance with loaded values
        config = cls()
        
        # Map JSON to config attributes
        config.symbol = config_data.get('symbol', config.symbol)
        
        # Trading parameters
        trading = config_data.get('trading', {})
        config.max_position_size = trading.get('max_position_size', config.max_position_size)
        config.stop_loss_pct = trading.get('stop_loss_pct', config.stop_loss_pct)
        config.take_profit_ratio = trading.get('take_profit_ratio', config.take_profit_ratio)
        config.volume_multiplier = trading.get('volume_multiplier', config.volume_multiplier)
        config.enable_trailing_stop = trading.get('enable_trailing_stop', config.enable_trailing_stop)
        config.orb_minutes = trading.get('orb_minutes', config.orb_minutes)
        config.position_close_time = trading.get('position_close_time', config.position_close_time)
        config.max_daily_trades = trading.get('max_daily_trades', config.max_daily_trades)
        
        # Risk management
        risk = config_data.get('risk_management', {})
        config.max_daily_loss = risk.get('max_daily_loss', config.max_daily_loss)
        config.min_shares = risk.get('min_shares', config.min_shares)
        
        # Connection settings
        connection = config_data.get('connection', {})
        config.ibkr_host = connection.get('host', config.ibkr_host)
        config.ibkr_port = connection.get('port', config.ibkr_port)
        config.ibkr_client_id = connection.get('client_id', config.ibkr_client_id)
        
        # Execution settings
        execution = config_data.get('execution', {})
        config.use_market_orders = execution.get('use_market_orders', config.use_market_orders)
        config.use_oco_orders = execution.get('use_oco_orders', config.use_oco_orders)
        config.slippage_buffer = execution.get('slippage_buffer', config.slippage_buffer)
        
        # Logging
        logging = config_data.get('logging', {})
        config.log_level = logging.get('level', config.log_level)
        
        return config
    
    def save_to_file(self, config_path: str = None):
        """Save current configuration to JSON file"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '../../configs/orb_config.json')
        
        config_data = {
            "symbol": self.symbol,
            "trading": {
                "max_position_size": self.max_position_size,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_ratio": self.take_profit_ratio,
                "volume_multiplier": self.volume_multiplier,
                "orb_minutes": self.orb_minutes,
                "position_close_time": self.position_close_time,
                "max_daily_trades": self.max_daily_trades,
                "enable_trailing_stop": self.enable_trailing_stop
            },
            "risk_management": {
                "max_daily_loss": self.max_daily_loss,
                "min_shares": self.min_shares
            },
            "connection": {
                "host": self.ibkr_host,
                "port": self.ibkr_port,
                "client_id": self.ibkr_client_id
            },
            "execution": {
                "use_market_orders": self.use_market_orders,
                "use_oco_orders": self.use_oco_orders,
                "slippage_buffer": self.slippage_buffer
            },
            "logging": {
                "level": self.log_level
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"✅ Configuration saved to {config_path}")