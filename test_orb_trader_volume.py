#!/usr/bin/env python3
"""
Test script to verify that ORB Trader initializes volume data correctly
"""

import asyncio
import logging
from datetime import datetime, timedelta
from orb_trader import ORBTrader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

async def test_orb_trader_volume():
    """Test that ORB Trader initializes volume data correctly"""
    
    print("🧪 Testing ORB Trader Volume Initialization")
    print("=" * 60)
    
    # Create trader instance
    trader = ORBTrader()
    
    # Test volume data initialization without IBKR connection
    print("\n1. Testing volume data initialization...")
    
    try:
        # Initialize volume data directly
        await trader.initialize_volume_data()
        
        # Check if volume data was set in strategy
        if trader.strategy.avg_volume_20d > 0:
            print(f"   ✅ Volume data initialized successfully")
            print(f"   📊 20-day average volume: {trader.strategy.avg_volume_20d:,}")
            
            # Test volume filter functionality
            print("\n2. Testing volume filter with current data...")
            
            # Get current volume statistics
            stats = trader.volume_provider.get_volume_statistics('NVDA')
            
            if stats:
                print(f"   📊 Current day volume: {stats['current_day_volume']:,}")
                print(f"   📊 Opening range volume: {stats['opening_range_volume']:,}")
                print(f"   📊 Volume ratio: {stats['volume_ratio']:.2f}x")
                print(f"   📊 OR volume ratio: {stats['or_volume_ratio']:.2f}x")
                
                # Check if today's volume would pass the filter
                required_volume = trader.strategy.avg_volume_20d * 1.5  # 1.5x multiplier
                current_volume = stats['current_day_volume']
                
                print(f"\n   🎯 Required volume for trading: {required_volume:,}")
                print(f"   📈 Current volume: {current_volume:,}")
                
                if current_volume >= required_volume:
                    print("   ✅ Current volume is sufficient for trading!")
                else:
                    print("   ⚠️ Current volume is insufficient for trading")
                    print(f"   📉 Need {required_volume - current_volume:,} more volume")
                
            else:
                print("   ❌ Failed to get volume statistics")
                return False
                
        else:
            print("   ❌ Volume data initialization failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Error during volume initialization: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ Volume initialization test completed successfully!")
    print("   The trader should now work with real volume data.")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_orb_trader_volume())