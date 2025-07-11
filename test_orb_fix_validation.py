#!/usr/bin/env python3
"""
Test script to validate the ORB fix with real data from today
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from src.strategies.orb_strategy import ORBStrategy, ORBSetup
from datetime import datetime, time
import pytz
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)

def test_orb_fix():
    """Test the ORB strategy with real data from today's logs"""
    
    # Create strategy instance
    strategy = ORBStrategy(ORBSetup())
    ny_tz = pytz.timezone('America/New_York')
    
    # Test data from today's logs (9:30-10:00 AM)
    test_candles = [
        {
            'timestamp': datetime(2025, 7, 9, 9, 30, 0, tzinfo=ny_tz),
            'open': 161.32,
            'high': 164.12,
            'low': 161.27,
            'close': 163.93,
            'volume': 21453509
        },
        {
            'timestamp': datetime(2025, 7, 9, 9, 45, 0, tzinfo=ny_tz),
            'open': 163.92,
            'high': 164.42,
            'low': 163.68,
            'close': 164.14,
            'volume': 11289741
        },
        {
            'timestamp': datetime(2025, 7, 9, 10, 0, 0, tzinfo=ny_tz),
            'open': 164.14,
            'high': 164.32,
            'low': 163.30,
            'close': 163.53,
            'volume': 8779395
        }
    ]
    
    logger.info("🧪 Testing ORB Strategy with real data from July 9, 2025")
    logger.info("=" * 60)
    
    # Process the candles
    for i, candle in enumerate(test_candles):
        logger.info(f"\n🕯️ Processing candle {i+1}/3:")
        logger.info(f"   Time: {candle['timestamp']}")
        logger.info(f"   OHLCV: {candle['open']:.2f}/{candle['high']:.2f}/{candle['low']:.2f}/{candle['close']:.2f}/{candle['volume']:,}")
        
        # Analyze the candle
        signal = strategy.analyze_tick(candle)
        
        if signal:
            logger.info(f"🎯 Signal generated: {signal}")
        else:
            logger.info("📊 No signal generated")
            
        # Check current ORB range state
        if strategy.opening_range:
            logger.info(f"📈 Current ORB Range: H=${strategy.opening_range.high:.2f}, L=${strategy.opening_range.low:.2f}, V={strategy.opening_range.current_volume:,}")
        else:
            logger.info("📊 ORB Range not yet established")
    
    # Test a breakout scenario
    logger.info("\n🚀 Testing breakout scenario...")
    
    # Create a breakout candle (above the range)
    breakout_candle = {
        'timestamp': datetime(2025, 7, 9, 10, 30, 0, tzinfo=ny_tz),
        'open': 164.50,
        'high': 165.00,  # Above the established range high of 164.42
        'low': 164.30,
        'close': 164.80,
        'volume': 5000000
    }
    
    logger.info(f"🕯️ Breakout candle: H={breakout_candle['high']:.2f} vs ORB H=${strategy.opening_range.high:.2f}")
    
    signal = strategy.analyze_tick(breakout_candle)
    if signal:
        logger.info(f"🎯 Breakout signal: {signal}")
    else:
        logger.info("❌ No breakout signal generated")
    
    # Final results
    logger.info("\n📊 Final Results:")
    logger.info("=" * 60)
    if strategy.opening_range:
        range_span = strategy.opening_range.high - strategy.opening_range.low
        logger.info(f"✅ ORB Range established: ${strategy.opening_range.low:.2f} - ${strategy.opening_range.high:.2f}")
        logger.info(f"📏 Range span: ${range_span:.2f}")
        logger.info(f"📈 Total volume: {strategy.opening_range.current_volume:,}")
    else:
        logger.info("❌ ORB Range not established")

if __name__ == "__main__":
    test_orb_fix()