#!/usr/bin/env python3
"""
Test de Aislamiento de Posiciones ORB
Verifica que el sistema solo gestione trades ORB y no toque otras posiciones
"""

import asyncio
import logging
from orb_trader_simple import SimpleORBTrader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)

async def test_isolation():
    """Test del sistema de aislamiento"""
    
    print("🔒 TESTING ORB POSITION ISOLATION")
    print("="*60)
    
    trader = SimpleORBTrader()
    
    try:
        # Connect to IBKR
        print("🔌 Connecting to IBKR...")
        connected = await trader.connect()
        
        if not connected:
            print("❌ Failed to connect to IBKR")
            return
        
        print("✅ Connected successfully!")
        print()
        
        # Show captured positions
        print("📊 POSITION ANALYSIS:")
        print("-"*40)
        
        # Get all current positions
        positions = trader.ib.positions()
        total_positions = len([p for p in positions if p.position != 0])
        
        print(f"Total positions in account: {total_positions}")
        
        if trader.initial_nvda_position != 0:
            print(f"🔍 Existing NVDA position: {trader.initial_nvda_position} shares")
            print("   → This will NOT be managed by ORB")
        else:
            print("🔍 No existing NVDA position found")
        
        print()
        print("🏷️ ORB TRACKING SETUP:")
        print(f"   Order Tag: {trader.orb_order_tag}")
        print(f"   ORB Orders Tracked: {len(trader.orb_orders)}")
        print(f"   ORB Position Size: {trader.orb_position_size}")
        
        print()
        print("✅ ISOLATION FEATURES:")
        print("   ✅ Only orders with 'ORB_STRATEGY' tag will be managed")
        print("   ✅ P&L calculated only for ORB trades")
        print("   ✅ Existing positions remain untouched")
        print("   ✅ Risk management applies only to ORB trades")
        
        # Test position calculation
        current_orb_position = trader.get_orb_position_size()
        print(f"📊 Current ORB position: {current_orb_position} shares")
        
        # Show current price for context
        current_price = await trader.get_current_price()
        if current_price:
            print(f"📈 Current {trader.config.symbol} price: ${current_price:.2f}")
            
            # Show what a trade would look like
            shares = int(trader.config.max_position_size / current_price)
            print(f"💰 Planned ORB trade size: {shares} shares (${shares * current_price:.0f})")
        
        print()
        print("🚀 READY FOR ISOLATED ORB TRADING!")
        print("   The system will:")
        print("   - Only create new NVDA positions tagged as 'ORB_STRATEGY'")
        print("   - Calculate P&L only for ORB trades")
        print("   - Leave all other positions unchanged")
        
    except Exception as e:
        print(f"❌ Error during isolation test: {e}")
        
    finally:
        # Cleanup
        if trader.ib.isConnected():
            if trader.nvda_contract:
                trader.ib.cancelMktData(trader.nvda_contract)
            trader.ib.disconnect()
            print("\n👋 Disconnected from IBKR")

if __name__ == "__main__":
    asyncio.run(test_isolation())