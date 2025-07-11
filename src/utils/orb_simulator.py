#!/usr/bin/env python3
"""
ORB Strategy Simulator/Backtester
Validates the ORB logic with historical data
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import List, Dict, Tuple
import pytz
import logging

logger = logging.getLogger(__name__)

class ORBSimulator:
    """Simulate ORB strategy with historical data"""
    
    def __init__(self, strategy_config):
        self.config = strategy_config
        self.ny_tz = pytz.timezone('America/New_York')
        self.trades = []
        self.equity_curve = []
        
    def load_sample_data(self) -> pd.DataFrame:
        """Load or generate sample NVDA data for testing"""
        # In production, this would load real historical data
        # For now, generate realistic sample data
        
        dates = pd.date_range(
            start='2024-01-01 09:30:00',
            end='2024-01-31 16:00:00',
            freq='15min',
            tz=self.ny_tz
        )
        
        # Filter for market hours only
        dates = [d for d in dates if self._is_market_hours(d)]
        
        # Generate realistic NVDA price data
        np.random.seed(42)
        base_price = 450.0
        
        data = []
        for i, date in enumerate(dates):
            # Add some trend and volatility
            trend = i * 0.01
            volatility = np.random.normal(0, 2)
            
            close = base_price + trend + volatility
            high = close + abs(np.random.normal(0, 0.5))
            low = close - abs(np.random.normal(0, 0.5))
            open_price = close + np.random.normal(0, 0.3)
            
            volume = np.random.randint(1000000, 5000000)
            
            data.append({
                'timestamp': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            
        return pd.DataFrame(data)
        
    def _is_market_hours(self, dt: datetime) -> bool:
        """Check if datetime is during market hours"""
        if dt.weekday() >= 5:  # Weekend
            return False
        market_open = time(9, 30)
        market_close = time(16, 0)
        return market_open <= dt.time() <= market_close
        
    def run_backtest(self, data: pd.DataFrame) -> Dict:
        """Run backtest on historical data"""
        logger.info("🚀 Starting ORB backtest simulation")
        
        # Group by date
        data['date'] = data['timestamp'].dt.date
        
        initial_capital = 100000.0
        current_capital = initial_capital
        
        for date, day_data in data.groupby('date'):
            # Reset daily state
            orb_high = None
            orb_low = None
            trade_taken = False
            
            # Sort by time
            day_data = day_data.sort_values('timestamp')
            
            # Get ORB range (first 15 minutes)
            orb_data = day_data[day_data['timestamp'].dt.time <= time(9, 45)]
            if not orb_data.empty:
                orb_high = orb_data['high'].max()
                orb_low = orb_data['low'].min()
                
            # Look for breakout after 9:45
            post_orb_data = day_data[day_data['timestamp'].dt.time > time(9, 45)]
            
            for idx, row in post_orb_data.iterrows():
                current_time = row['timestamp'].time()
                
                # Skip if already traded today
                if trade_taken:
                    continue
                    
                # Check for breakout
                if orb_high and row['close'] > orb_high:
                    # Enter trade
                    entry_price = row['close']
                    stop_price = entry_price * (1 + self.config.stop_loss_pct)
                    target_price = entry_price * (1 + self.config.take_profit_pct)
                    shares = int(self.config.max_position_size / entry_price)
                    
                    # Simulate trade outcome
                    exit_price, exit_reason = self._simulate_trade_outcome(
                        day_data[day_data['timestamp'] > row['timestamp']],
                        entry_price,
                        stop_price,
                        target_price
                    )
                    
                    # Calculate P&L
                    pnl = (exit_price - entry_price) * shares
                    current_capital += pnl
                    
                    # Record trade
                    self.trades.append({
                        'date': date,
                        'entry_time': row['timestamp'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'shares': shares,
                        'pnl': pnl,
                        'return_pct': (exit_price - entry_price) / entry_price
                    })
                    
                    trade_taken = True
                    
            # Record equity
            self.equity_curve.append({
                'date': date,
                'capital': current_capital
            })
            
        # Calculate statistics
        return self._calculate_statistics(initial_capital)
        
    def _simulate_trade_outcome(self, future_data: pd.DataFrame, 
                               entry_price: float, stop_price: float, 
                               target_price: float) -> Tuple[float, str]:
        """Simulate how a trade would have ended"""
        for idx, row in future_data.iterrows():
            # Check stop loss
            if row['low'] <= stop_price:
                return stop_price, 'STOP_LOSS'
                
            # Check take profit
            if row['high'] >= target_price:
                return target_price, 'TAKE_PROFIT'
                
            # Check time exit (3:00 PM)
            if row['timestamp'].time() >= time(15, 0):
                return row['close'], 'TIME_EXIT'
                
        # Default to last price
        return future_data.iloc[-1]['close'], 'EOD'
        
    def _calculate_statistics(self, initial_capital: float) -> Dict:
        """Calculate backtest statistics"""
        if not self.trades:
            return {'error': 'No trades executed'}
            
        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)
        
        # Win rate
        wins = len(trades_df[trades_df['pnl'] > 0])
        total_trades = len(trades_df)
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        # Average R/R
        avg_win = trades_df[trades_df['pnl'] > 0]['return_pct'].mean() if wins > 0 else 0
        avg_loss = abs(trades_df[trades_df['pnl'] < 0]['return_pct'].mean()) if wins < total_trades else 0
        rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        # Drawdown
        equity_df['peak'] = equity_df['capital'].cummax()
        equity_df['drawdown'] = (equity_df['capital'] - equity_df['peak']) / equity_df['peak']
        max_drawdown = equity_df['drawdown'].min()
        
        # Total return
        final_capital = equity_df['capital'].iloc[-1]
        total_return = (final_capital - initial_capital) / initial_capital
        
        # Exit reasons
        exit_reasons = trades_df['exit_reason'].value_counts().to_dict()
        
        stats = {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'rr_ratio': rr_ratio,
            'max_drawdown': max_drawdown,
            'total_return': total_return,
            'final_capital': final_capital,
            'avg_trade_pnl': trades_df['pnl'].mean(),
            'best_trade': trades_df['pnl'].max(),
            'worst_trade': trades_df['pnl'].min(),
            'exit_reasons': exit_reasons,
            'sharpe_ratio': self._calculate_sharpe_ratio(trades_df)
        }
        
        return stats
        
    def _calculate_sharpe_ratio(self, trades_df: pd.DataFrame) -> float:
        """Calculate Sharpe ratio"""
        if trades_df.empty:
            return 0
            
        # Daily returns
        trades_df['date'] = pd.to_datetime(trades_df['date'])
        daily_returns = trades_df.groupby('date')['return_pct'].sum()
        
        # Annualized Sharpe
        if len(daily_returns) > 1:
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
            return sharpe
        return 0
        
    def print_backtest_results(self, stats: Dict):
        """Print formatted backtest results"""
        print("\n" + "="*60)
        print("📊 ORB BACKTEST RESULTS")
        print("="*60)
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Win Rate: {stats['win_rate']*100:.1f}%")
        print(f"Avg R/R Ratio: {stats['rr_ratio']:.2f}")
        print(f"Max Drawdown: {stats['max_drawdown']*100:.1f}%")
        print(f"Total Return: {stats['total_return']*100:.1f}%")
        print(f"Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
        print(f"Avg Trade P&L: ${stats['avg_trade_pnl']:.2f}")
        print(f"Best Trade: ${stats['best_trade']:.2f}")
        print(f"Worst Trade: ${stats['worst_trade']:.2f}")
        print("\n📈 EXIT REASONS:")
        for reason, count in stats['exit_reasons'].items():
            pct = (count / stats['total_trades']) * 100
            print(f"  {reason}: {count} ({pct:.1f}%)")
        print("="*60)
        
    def export_trades(self, filename: str = "orb_backtest_trades.csv"):
        """Export trades to CSV"""
        if self.trades:
            df = pd.DataFrame(self.trades)
            df.to_csv(filename, index=False)
            logger.info(f"📄 Trades exported to {filename}")