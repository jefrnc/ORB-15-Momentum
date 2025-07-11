#!/usr/bin/env python3
"""
ORB Trader Simplificado para Testing
Sin PostgreSQL - Solo simulación y tests básicos
"""

import asyncio
import logging
from datetime import datetime, time
from src.strategies.orb_strategy import ORBStrategy, ORBSetup
from src.core.orb_config import ORBConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)

class ORBTestTrader:
    """Trader simplificado para testing sin IBKR"""
    
    def __init__(self):
        # Cargar configuración
        self.config = ORBConfig.load_from_file()
        
        # Crear estrategia
        setup = ORBSetup(
            symbol=self.config.symbol,
            orb_minutes=self.config.orb_minutes,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            max_position_size=self.config.max_position_size
        )
        
        self.strategy = ORBStrategy(setup)
        
    def display_config(self):
        """Mostrar configuración de testing"""
        print("\n" + "="*60)
        print("🧪 ORB TESTING CONFIGURATION")
        print("="*60)
        print(f"Symbol: {self.config.symbol}")
        print(f"Max Position: ${self.config.max_position_size:,.0f}")
        print(f"Stop Loss: {self.config.stop_loss_pct*100:.1f}%")
        print(f"Take Profit: {self.config.take_profit_pct*100:.1f}%")
        print(f"Max Daily Loss: ${self.config.max_daily_loss:,.0f}")
        print(f"Connection: {self.config.ibkr_host}:{self.config.ibkr_port}")
        
        # Ejemplo con precio actual de NVDA (~$130)
        example_price = 130.0
        example_shares = int(self.config.max_position_size / example_price)
        example_value = example_shares * example_price
        risk_amount = example_value * abs(self.config.stop_loss_pct)
        reward_amount = example_value * self.config.take_profit_pct
        
        print(f"\n💰 POSITION SIZING EXAMPLE")
        print(f"NVDA @ ${example_price}: {example_shares} shares = ${example_value:.0f}")
        print(f"Stop Loss: ${example_price * (1 + self.config.stop_loss_pct):.2f} (Risk: ${risk_amount:.2f})")
        print(f"Take Profit: ${example_price * (1 + self.config.take_profit_pct):.2f} (Reward: ${reward_amount:.2f})")
        print(f"Risk/Reward Ratio: 1:{reward_amount/risk_amount:.1f}")
        print("="*60)
        
    def test_basic_functionality(self):
        """Test básico de funcionalidad"""
        print("\n🔧 TESTING BASIC FUNCTIONALITY")
        print("-"*40)
        
        # Test 1: Market hours
        is_open = self.strategy.is_market_open()
        print(f"✓ Market open check: {'Open' if is_open else 'Closed'}")
        
        # Test 2: Position sizing
        test_price = 130.0
        shares = self.strategy.calculate_position_size(test_price)
        position_value = shares * test_price
        print(f"✓ Position sizing: {shares} shares @ ${test_price} = ${position_value:.0f}")
        
        # Test 3: Risk calculations
        from src.strategies.orb_strategy import ORBRange
        self.strategy.opening_range = ORBRange(
            high=test_price - 2,
            low=test_price - 10,
            timestamp=datetime.now(),
            volume=1000000
        )
        
        trade = self.strategy.create_trade_setup(test_price)
        print(f"✓ Trade setup: Entry=${trade.entry_price:.2f}, Stop=${trade.stop_price:.2f}, Target=${trade.target_price:.2f}")
        
        risk_per_share = trade.entry_price - trade.stop_price
        reward_per_share = trade.target_price - trade.entry_price
        total_risk = risk_per_share * trade.shares
        total_reward = reward_per_share * trade.shares
        
        print(f"✓ Risk analysis: Risk=${total_risk:.2f}, Reward=${total_reward:.2f}, R/R=1:{total_reward/total_risk:.1f}")
        
        return True

def main():
    """Función principal de testing"""
    print("🚀 ORB TESTING SYSTEM - SIMPLIFIED VERSION")
    
    try:
        # Crear trader de testing
        trader = ORBTestTrader()
        
        # Mostrar configuración
        trader.display_config()
        
        # Test básico
        trader.test_basic_functionality()
        
        print("\n✅ ALL TESTS PASSED!")
        print("\nNext steps:")
        print("1. Start TWS/IB Gateway on port 7496")
        print("2. Enable API connections in TWS")
        print("3. Use paper trading account for testing")
        print("4. Run: python3 orb_trader.py --paper --max-position 500")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()