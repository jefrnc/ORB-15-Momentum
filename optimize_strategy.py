#!/usr/bin/env python3
"""
Optimizador de Parámetros ORB
Encuentra los mejores parámetros para la estrategia
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
from itertools import product
from src.core.orb_config import ORBConfig

def test_parameters(data, stop_loss_pct, take_profit_pct, max_position_size=500):
    """Testear una combinación específica de parámetros"""
    
    # Filtrar datos para horario de mercado
    ny_tz = pytz.timezone('America/New_York')
    data_copy = data.copy()
    data_copy['datetime'] = pd.to_datetime(data_copy['datetime'])
    
    if data_copy['datetime'].dt.tz is None:
        data_copy['datetime'] = data_copy['datetime'].dt.tz_localize('UTC').dt.tz_convert(ny_tz)
    else:
        data_copy['datetime'] = data_copy['datetime'].dt.tz_convert(ny_tz)
    
    data_copy = data_copy[data_copy['datetime'].dt.time >= time(9, 30)]
    data_copy = data_copy[data_copy['datetime'].dt.time <= time(16, 0)]
    data_copy = data_copy[data_copy['datetime'].dt.weekday < 5]
    
    if data_copy.empty:
        return None
    
    trades = []
    data_copy['date'] = data_copy['datetime'].dt.date
    
    for date, day_data in data_copy.groupby('date'):
        day_data = day_data.sort_values('datetime').reset_index(drop=True)
        
        # ORB range
        orb_data = day_data[day_data['datetime'].dt.time <= time(9, 45)]
        if len(orb_data) == 0:
            continue
        
        orb_high = orb_data['high'].max()
        post_orb = day_data[day_data['datetime'].dt.time > time(9, 45)]
        
        for idx, row in post_orb.iterrows():
            if row['datetime'].time() >= time(15, 0):
                break
            
            if row['close'] > orb_high:
                entry_price = row['close']
                stop_price = entry_price * (1 + stop_loss_pct)
                target_price = entry_price * (1 + take_profit_pct)
                
                future_data = post_orb[post_orb['datetime'] > row['datetime']]
                
                exit_price = entry_price
                exit_reason = "EOD"
                
                for _, future_row in future_data.iterrows():
                    if future_row['low'] <= stop_price:
                        exit_price = stop_price
                        exit_reason = "STOP_LOSS"
                        break
                    elif future_row['high'] >= target_price:
                        exit_price = target_price
                        exit_reason = "TAKE_PROFIT"
                        break
                    elif future_row['datetime'].time() >= time(15, 0):
                        exit_price = future_row['close']
                        exit_reason = "TIME_EXIT"
                        break
                
                shares = int(max_position_size / entry_price)
                pnl = (exit_price - entry_price) * shares
                
                trades.append({
                    'pnl': pnl,
                    'return_pct': (exit_price - entry_price) / entry_price * 100,
                    'exit_reason': exit_reason
                })
                break
    
    if not trades:
        return None
    
    df = pd.DataFrame(trades)
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    total_pnl = df['pnl'].sum()
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': total_pnl / total_trades,
        'best_trade': df['pnl'].max(),
        'worst_trade': df['pnl'].min(),
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct,
        'take_profit_rate': len(df[df['exit_reason'] == 'TAKE_PROFIT']) / total_trades
    }

def optimize_strategy():
    """Optimizar parámetros de la estrategia"""
    print("🔧 OPTIMIZADOR DE ESTRATEGIA ORB")
    print("="*50)
    
    # Descargar datos
    print("📥 Descargando datos de NVDA...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    nvda = yf.Ticker("NVDA")
    data = nvda.history(start=start_date, end=end_date, interval="1h", prepost=False)
    
    if data.empty:
        print("❌ No se pudieron obtener datos")
        return
    
    data = data.reset_index()
    data.columns = [col.lower() for col in data.columns]
    print(f"✅ Datos obtenidos: {len(data)} barras")
    
    # Rangos de parámetros a probar
    stop_loss_range = [-0.005, -0.008, -0.01, -0.012, -0.015, -0.02]  # -0.5% a -2%
    take_profit_range = [0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05]  # 1.5% a 5%
    
    print(f"🧪 Probando {len(stop_loss_range)} × {len(take_profit_range)} = {len(stop_loss_range) * len(take_profit_range)} combinaciones")
    
    best_results = []
    
    for stop_loss, take_profit in product(stop_loss_range, take_profit_range):
        result = test_parameters(data, stop_loss, take_profit)
        
        if result and result['total_trades'] >= 3:  # Mínimo 3 trades
            result['profit_factor'] = abs(result['total_pnl']) if result['total_pnl'] > 0 else 0
            result['score'] = (result['win_rate'] * 0.4 + 
                             (result['total_pnl'] / abs(result['worst_trade']) if result['worst_trade'] < 0 else 1) * 0.3 +
                             result['take_profit_rate'] * 0.3)
            best_results.append(result)
    
    if not best_results:
        print("❌ No se encontraron resultados válidos")
        return
    
    # Ordenar por score
    best_results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n🏆 TOP 5 COMBINACIONES DE PARÁMETROS:")
    print("-" * 80)
    print(f"{'Rank':<4} {'Stop%':<6} {'Target%':<7} {'Trades':<6} {'Win%':<6} {'P&L':<8} {'TP Rate':<7} {'Score':<6}")
    print("-" * 80)
    
    for i, result in enumerate(best_results[:5]):
        print(f"{i+1:<4} {result['stop_loss_pct']*100:>5.1f} {result['take_profit_pct']*100:>6.1f} "
              f"{result['total_trades']:>5} {result['win_rate']*100:>5.1f} "
              f"${result['total_pnl']:>+6.2f} {result['take_profit_rate']*100:>6.1f} {result['score']:>5.3f}")
    
    # Mostrar detalles del mejor
    best = best_results[0]
    print(f"\n🥇 MEJOR COMBINACIÓN:")
    print(f"   Stop Loss: {best['stop_loss_pct']*100:.1f}%")
    print(f"   Take Profit: {best['take_profit_pct']*100:.1f}%")
    print(f"   Total Trades: {best['total_trades']}")
    print(f"   Win Rate: {best['win_rate']:.1%}")
    print(f"   Total P&L: ${best['total_pnl']:+.2f}")
    print(f"   Promedio por Trade: ${best['avg_pnl']:+.2f}")
    print(f"   Take Profit Rate: {best['take_profit_rate']:.1%}")
    
    # Comparar con configuración actual
    config = ORBConfig.load_from_file()
    current_result = test_parameters(data, config.stop_loss_pct, config.take_profit_pct)
    
    if current_result:
        print(f"\n📊 CONFIGURACIÓN ACTUAL:")
        print(f"   Stop Loss: {config.stop_loss_pct*100:.1f}%")
        print(f"   Take Profit: {config.take_profit_pct*100:.1f}%")
        print(f"   Total P&L: ${current_result['total_pnl']:+.2f}")
        print(f"   Win Rate: {current_result['win_rate']:.1%}")
        
        improvement = best['total_pnl'] - current_result['total_pnl']
        print(f"\n💡 MEJORA POTENCIAL: ${improvement:+.2f}")
    
    print("\n🔧 Para aplicar la mejor configuración, edita configs/orb_config.json:")
    print(f'   "stop_loss_pct": {best["stop_loss_pct"]},')
    print(f'   "take_profit_pct": {best["take_profit_pct"]},')

if __name__ == "__main__":
    optimize_strategy()