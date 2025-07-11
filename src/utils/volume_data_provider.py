#!/usr/bin/env python3
"""
Volume Data Provider using Yahoo Finance
Fetches historical volume data for ORB strategy validation
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)

class VolumeDataProvider:
    """Provides historical volume data using Yahoo Finance API"""
    
    def __init__(self, cache_duration_minutes: int = 30):
        self.cache_duration_minutes = cache_duration_minutes
        self._cache = {}
        self._cache_timestamps = {}
    
    @lru_cache(maxsize=10)
    def get_ticker(self, symbol: str) -> yf.Ticker:
        """Get cached ticker object"""
        return yf.Ticker(symbol)
    
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached data is still valid"""
        if symbol not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[symbol]
        now = datetime.now()
        return (now - cache_time).total_seconds() < (self.cache_duration_minutes * 60)
    
    def get_20_day_average_volume(self, symbol: str) -> int:
        """
        Get 20-day average volume for a symbol
        
        Args:
            symbol: Stock symbol (e.g., 'NVDA')
            
        Returns:
            20-day average volume as integer
        """
        try:
            # Check cache first
            if self._is_cache_valid(symbol):
                logger.info(f"📊 Using cached volume data for {symbol}")
                return self._cache[symbol]
            
            logger.info(f"📥 Fetching 20-day volume data for {symbol}...")
            
            # Get ticker
            ticker = self.get_ticker(symbol)
            
            # Get 25 days of data to ensure we have 20 trading days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=25)
            
            # Download historical data
            hist_data = ticker.history(
                start=start_date,
                end=end_date,
                interval="1d",
                prepost=False
            )
            
            if hist_data.empty:
                logger.error(f"❌ No historical data found for {symbol}")
                return 0
            
            # Calculate average volume for the last 20 trading days
            volumes = hist_data['Volume'].dropna()
            
            if len(volumes) < 10:  # Need at least 10 days of data
                logger.warning(f"⚠️ Only {len(volumes)} days of volume data available for {symbol}")
                return 0
            
            # Get the last 20 days (or available days)
            recent_volumes = volumes.tail(20)
            avg_volume = int(recent_volumes.mean())
            
            # Cache the result
            self._cache[symbol] = avg_volume
            self._cache_timestamps[symbol] = datetime.now()
            
            logger.info(f"✅ 20-day average volume for {symbol}: {avg_volume:,}")
            logger.info(f"📊 Volume data points used: {len(recent_volumes)}")
            
            return avg_volume
            
        except Exception as e:
            logger.error(f"❌ Error fetching volume data for {symbol}: {e}")
            return 0
    
    def get_current_day_volume(self, symbol: str) -> int:
        """
        Get current day's volume so far
        
        Args:
            symbol: Stock symbol (e.g., 'NVDA')
            
        Returns:
            Current day volume as integer
        """
        try:
            ticker = self.get_ticker(symbol)
            
            # Get today's data with 1-minute intervals
            today_data = ticker.history(
                period="1d",
                interval="1m",
                prepost=False
            )
            
            if today_data.empty:
                logger.warning(f"⚠️ No intraday data found for {symbol}")
                return 0
            
            # Sum up the volume for today
            total_volume = int(today_data['Volume'].sum())
            
            logger.info(f"📊 Current day volume for {symbol}: {total_volume:,}")
            return total_volume
            
        except Exception as e:
            logger.error(f"❌ Error fetching current day volume for {symbol}: {e}")
            return 0
    
    def get_opening_range_volume(self, symbol: str, minutes: int = 30) -> int:
        """
        Get volume for the opening range period (first N minutes)
        
        Args:
            symbol: Stock symbol (e.g., 'NVDA')
            minutes: Number of minutes from market open (default 30)
            
        Returns:
            Opening range volume as integer
        """
        try:
            ticker = self.get_ticker(symbol)
            
            # Get today's data with 1-minute intervals
            today_data = ticker.history(
                period="1d",
                interval="1m",
                prepost=False
            )
            
            if today_data.empty:
                logger.warning(f"⚠️ No intraday data found for {symbol}")
                return 0
            
            # Get the first N minutes of data
            opening_data = today_data.head(minutes)
            
            if len(opening_data) < minutes:
                logger.warning(f"⚠️ Only {len(opening_data)} minutes of data available (requested {minutes})")
            
            # Sum up the volume for the opening range
            or_volume = int(opening_data['Volume'].sum())
            
            logger.info(f"📊 Opening range volume ({minutes}min) for {symbol}: {or_volume:,}")
            return or_volume
            
        except Exception as e:
            logger.error(f"❌ Error fetching opening range volume for {symbol}: {e}")
            return 0
    
    def get_volume_statistics(self, symbol: str) -> Dict:
        """
        Get comprehensive volume statistics
        
        Args:
            symbol: Stock symbol (e.g., 'NVDA')
            
        Returns:
            Dictionary with volume statistics
        """
        try:
            avg_volume_20d = self.get_20_day_average_volume(symbol)
            current_volume = self.get_current_day_volume(symbol)
            or_volume = self.get_opening_range_volume(symbol, 30)
            
            stats = {
                'symbol': symbol,
                'avg_volume_20d': avg_volume_20d,
                'current_day_volume': current_volume,
                'opening_range_volume': or_volume,
                'volume_ratio': current_volume / avg_volume_20d if avg_volume_20d > 0 else 0,
                'or_volume_ratio': or_volume / avg_volume_20d if avg_volume_20d > 0 else 0,
                'timestamp': datetime.now()
            }
            
            logger.info(f"📊 Volume statistics for {symbol}:")
            logger.info(f"   20-day average: {avg_volume_20d:,}")
            logger.info(f"   Current day: {current_volume:,}")
            logger.info(f"   Opening range: {or_volume:,}")
            logger.info(f"   Volume ratio: {stats['volume_ratio']:.2f}x")
            logger.info(f"   OR volume ratio: {stats['or_volume_ratio']:.2f}x")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting volume statistics for {symbol}: {e}")
            return {}
    
    def clear_cache(self):
        """Clear the volume data cache"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("🧹 Volume data cache cleared")

# Global instance
volume_provider = VolumeDataProvider()

# Async wrapper for use in async contexts
async def get_volume_data_async(symbol: str) -> int:
    """Async wrapper for getting 20-day average volume"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, volume_provider.get_20_day_average_volume, symbol)

if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)
    
    provider = VolumeDataProvider()
    
    # Test NVDA volume data
    print("Testing NVDA volume data...")
    stats = provider.get_volume_statistics("NVDA")
    print(f"Results: {stats}")