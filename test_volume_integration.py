#!/usr/bin/env python3
"""
Test script to verify volume data integration
"""

import asyncio
import logging
from src.utils.volume_data_provider import VolumeDataProvider
from src.strategies.orb_strategy import ORBStrategy, ORBSetup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

async def test_volume_integration():
    """Test the volume data integration with ORB strategy"""
    
    print("🧪 Testing Volume Data Integration")
    print("=" * 50)
    
    # Test 1: VolumeDataProvider
    print("\n1. Testing VolumeDataProvider...")
    provider = VolumeDataProvider()
    
    # Test getting 20-day average volume
    avg_volume = provider.get_20_day_average_volume('NVDA')
    print(f"   20-day average volume: {avg_volume:,}")
    
    if avg_volume > 0:
        print("   ✅ Volume data provider working correctly")
    else:
        print("   ❌ Volume data provider failed")
        return False
    
    # Test 2: ORB Strategy integration
    print("\n2. Testing ORB Strategy integration...")
    strategy = ORBStrategy(ORBSetup())
    
    # Set historical volume
    strategy.set_historical_volume(avg_volume)
    
    # Check if volume was set correctly
    if strategy.avg_volume_20d == avg_volume:
        print("   ✅ ORB Strategy volume integration working correctly")
    else:
        print("   ❌ ORB Strategy volume integration failed")
        return False
    
    # Test 3: Volume statistics
    print("\n3. Getting comprehensive volume statistics...")
    stats = provider.get_volume_statistics('NVDA')
    
    if stats and 'avg_volume_20d' in stats:
        print("   ✅ Volume statistics working correctly")
        print(f"   Statistics: {stats}")
    else:
        print("   ❌ Volume statistics failed")
        return False
    
    # Test 4: Check volume filter
    print("\n4. Testing volume filter...")
    
    # Create a mock opening range for testing
    from src.strategies.orb_strategy import ORBRange
    from datetime import datetime
    
    # Simulate opening range with volume
    strategy.opening_range = ORBRange(
        high=150.0,
        low=148.0,
        timestamp=datetime.now(),
        volume=1000000,
        avg_volume_20d=avg_volume,
        current_volume=int(avg_volume * 1.6)  # 1.6x average volume
    )
    
    volume_ok = strategy.check_volume_filter()
    if volume_ok:
        print("   ✅ Volume filter working correctly (volume sufficient)")
    else:
        print("   ❌ Volume filter failed")
        return False
    
    # Test 5: Test with insufficient volume
    print("\n5. Testing volume filter with insufficient volume...")
    
    strategy.opening_range.current_volume = int(avg_volume * 0.5)  # 0.5x average volume
    volume_ok = strategy.check_volume_filter()
    if not volume_ok:
        print("   ✅ Volume filter correctly rejected insufficient volume")
    else:
        print("   ❌ Volume filter should have rejected insufficient volume")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed! Volume integration is working correctly.")
    print("   The trader should now work properly with volume data.")
    return True

if __name__ == "__main__":
    asyncio.run(test_volume_integration())