#!/usr/bin/env python3
"""
Test de parámetros específicos: -1% SL, +2% TP
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz

def test_1percent_sl_2percent_tp():
    """Probar específicamente -1% SL y +2% TP"""
    print("🧪 TESTING ESPECÍFICO: -1% SL, +2% TP")
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
    
    # Configuraciones a comparar
    configs = [
        {"name": "Original", "sl": -0.01, "tp": 0.04},
        {"name": "Tu Sugerencia", "sl": -0.01, "tp": 0.02},
        {"name": "Optimizada", "sl": -0.02, "tp": 0.015},
        {"name": "Conservadora", "sl": -0.008, "tp": 0.015},
        {"name": "Agresiva", "sl": -0.015, "tp": 0.025}
    ]
    
    results = []
    
    for config in configs:
        result = simulate_with_params(data, config["sl"], config["tp"])
        if result:
            result["name"] = config["name"]
            result["sl"] = config["sl"]
            result["tp"] = config["tp"]
            results.append(result)
    
    # Mostrar comparación
    print("\n📊 COMPARACIÓN DE CONFIGURACIONES:")
    print("-" * 85)
    print(f"{'Config':<12} {'SL%':<5} {'TP%':<5} {'Trades':<6} {'Win%':<6} {'P&L':<8} {'Avg':<6} {'TP Rate':<7}")
    print("-" * 85)
    
    for result in results:
        print(f"{result['name']:<12} {result['sl']*100:>4.1f} {result['tp']*100:>4.1f} "
              f"{result['total_trades']:>5} {result['win_rate']*100:>5.1f} "
              f"${result['total_pnl']:>+6.2f} ${result['avg_pnl']:>+5.2f} {result['tp_rate']*100:>6.1f}")
    
    # Análisis detallado de tu sugerencia
    tu_config = next((r for r in results if r["name"] == "Tu Sugerencia"), None)
    if tu_config:
        print(f"\n🎯 ANÁLISIS DETALLADO: -1% SL, +2% TP")
        print("-" * 40)
        print(f"Total Trades: {tu_config['total_trades']}")
        print(f"Win Rate: {tu_config['win_rate']:.1%}")
        print(f"Total P&L: ${tu_config['total_pnl']:+.2f}")
        print(f"Promedio por Trade: ${tu_config['avg_pnl']:+.2f}")
        print(f"Take Profit Rate: {tu_config['tp_rate']:.1%}")
        print(f"Mejor Trade: ${tu_config['best_trade']:+.2f}")
        print(f"Peor Trade: ${tu_config['worst_trade']:+.2f}")
        
        # Comparar con original
        original = next((r for r in results if r["name"] == "Original"), None)
        if original:
            improvement = tu_config['total_pnl'] - original['total_pnl']
            print(f"\n💡 vs Configuración Original:")
            print(f"   Mejora en P&L: ${improvement:+.2f}")
            print(f"   TP Rate: {tu_config['tp_rate']:.1%} vs {original['tp_rate']:.1%}")
            
            if improvement > 0:
                print("✅ Tu sugerencia ES MEJOR que la configuración original")
            else:
                print("❌ La configuración original es mejor")
    
    # Mostrar trades detallados de tu configuración
    print(f"\n📈 TRADES DETALLADOS (-1% SL, +2% TP):")
    detailed_trades = get_detailed_trades(data, -0.01, 0.02)
    print("-" * 70)
    print(f"{'Fecha':<12} {'Entry':<8} {'Exit':<8} {'P&L':<8} {'%':<6} {'Razón':<12}")
    print("-" * 70)
    
    for trade in detailed_trades:
        print(f"{str(trade['date']):<12} ${trade['entry_price']:<7.2f} ${trade['exit_price']:<7.2f} "
              f"${trade['pnl']:>+6.2f} {trade['return_pct']:>+5.1f}% {trade['exit_reason']:<12}")

def simulate_with_params(data, stop_loss_pct, take_profit_pct):
    """Simular con parámetros específicos"""
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
    max_position_size = 500
    
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
    tp_count = len(df[df['exit_reason'] == 'TAKE_PROFIT'])
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': total_pnl / total_trades,
        'best_trade': df['pnl'].max(),
        'worst_trade': df['pnl'].min(),
        'tp_rate': tp_count / total_trades
    }

def get_detailed_trades(data, stop_loss_pct, take_profit_pct):
    """Obtener trades detallados"""
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
    
    trades = []
    data_copy['date'] = data_copy['datetime'].dt.date
    max_position_size = 500
    
    for date, day_data in data_copy.groupby('date'):
        day_data = day_data.sort_values('datetime').reset_index(drop=True)
        
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
                    'date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'shares': shares,
                    'pnl': pnl,
                    'return_pct': (exit_price - entry_price) / entry_price * 100
                })
                break
    
    return trades

if __name__ == "__main__":
    test_1percent_sl_2percent_tp()