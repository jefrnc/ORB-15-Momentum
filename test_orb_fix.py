#!/usr/bin/env python3
"""
Test script to verify the ORB strategy fix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from src.strategies.orb_strategy import ORBStrategy

def test_orb_strategy():
    """Test that ORBStrategy has analyze_tick method"""
    print("🧪 Testing ORB Strategy...")
    
    # Create strategy instance
    strategy = ORBStrategy()
    
    # Check if analyze_tick method exists
    if hasattr(strategy, 'analyze_tick'):
        print("✅ SUCCESS: analyze_tick method exists in ORBStrategy")
    else:
        print("❌ ERROR: analyze_tick method NOT found in ORBStrategy")
        return False
    
    # Test with sample tick data
    sample_tick = {
        'timestamp': datetime.now(),
        'price': 450.50,
        'volume': 1000,
        'last': 450.50
    }
    
    try:
        # This should not raise an error
        result = strategy.analyze_tick(sample_tick)
        print("✅ SUCCESS: analyze_tick method can be called without errors")
        print(f"   Result: {result}")
        return True
    except Exception as e:
        print(f"❌ ERROR: Failed to call analyze_tick: {e}")
        return False

def test_orb_trader_import():
    """Test that orb_trader can be imported without syntax errors"""
    print("\n🧪 Testing ORB Trader import...")
    
    try:
        import orb_trader
        print("✅ SUCCESS: orb_trader.py can be imported")
        
        # Check if the line was fixed
        with open('orb_trader.py', 'r') as f:
            content = f.read()
            if 'analyze_tick' in content and 'analyze_candle' not in content:
                print("✅ SUCCESS: analyze_candle has been replaced with analyze_tick")
                return True
            else:
                print("❌ ERROR: analyze_candle might still be present")
                return False
                
    except Exception as e:
        print(f"❌ ERROR: Failed to import orb_trader: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("ORB Strategy Fix Verification")
    print("=" * 50)
    
    test1 = test_orb_strategy()
    test2 = test_orb_trader_import()
    
    print("\n" + "=" * 50)
    if test1 and test2:
        print("🎉 ALL TESTS PASSED - The fix is working!")
    else:
        print("⚠️  SOME TESTS FAILED - Please check the errors above")
    print("=" * 50)