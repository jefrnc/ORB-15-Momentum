#!/usr/bin/env python3
"""
Backtester ORB Simplificado con Datos Reales
Evalúa la estrategia ORB con datos de Yahoo Finance
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
from src.core.orb_config import ORBConfig

def download_nvda_data(days=30):
    """Descargar datos recientes de NVDA"""
    print(f"📥 Descargando datos de NVDA de los últimos {days} días...")
    
    try:
        # Usar datos diarios y simular intradía
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        nvda = yf.Ticker("NVDA")
        
        # Intentar diferentes intervalos
        for interval in ["1h", "30m", "15m", "1d"]:
            try:
                print(f"Intentando intervalo {interval}...")
                data = nvda.history(
                    start=start_date,
                    end=end_date,
                    interval=interval,
                    prepost=False
                )
                
                if not data.empty:
                    print(f"✅ Datos obtenidos con intervalo {interval}: {len(data)} barras")
                    return data, interval
                    
            except Exception as e:
                print(f"❌ Error con intervalo {interval}: {e}")
                continue
        
        print("❌ No se pudieron obtener datos de ningún intervalo")
        return None, None
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        return None, None

def simulate_orb_strategy(data, interval, config):
    """Simular estrategia ORB con los datos disponibles"""
    print(f"🚀 Simulando estrategia ORB con datos de {interval}")
    
    if data is None or data.empty:
        return {"error": "No hay datos"}
    
    # Preparar datos
    data = data.reset_index()
    data.columns = [col.lower() for col in data.columns]
    
    # Si son datos diarios, simular comportamiento intradía
    if interval == "1d":
        return simulate_daily_orb(data, config)
    else:
        return simulate_intraday_orb(data, interval, config)

def simulate_daily_orb(data, config):
    """Simular ORB con datos diarios (estimación)"""
    print("📊 Simulando con datos diarios (estimación)")
    
    trades = []
    capital = 100000
    
    for i in range(1, len(data)):
        prev_day = data.iloc[i-1]
        current_day = data.iloc[i]
        
        # Simular que ORB = 2% del rango del día anterior
        orb_range = (prev_day['high'] - prev_day['low']) * 0.15  # 15% del rango
        orb_high = prev_day['close'] + orb_range
        
        # Si el precio abrió cerca del cierre anterior y superó ORB
        if current_day['open'] > orb_high * 0.98:  # Cerca del breakout
            entry_price = orb_high
            stop_price = entry_price * (1 + config.stop_loss_pct)
            target_price = entry_price * (1 + config.take_profit_pct)
            
            # Determinar salida basada en el rango del día
            if current_day['low'] <= stop_price:
                exit_price = stop_price
                exit_reason = "STOP_LOSS"
            elif current_day['high'] >= target_price:
                exit_price = target_price
                exit_reason = "TAKE_PROFIT"
            else:
                exit_price = current_day['close']
                exit_reason = "EOD"
            
            # Calcular trade
            shares = int(config.max_position_size / entry_price)
            pnl = (exit_price - entry_price) * shares
            
            trades.append({
                'date': current_day['datetime'].date(),
                'entry_price': entry_price,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'shares': shares,
                'pnl': pnl,
                'return_pct': (exit_price - entry_price) / entry_price * 100
            })
            
            capital += pnl
            print(f"📈 {current_day['datetime'].date()}: ${entry_price:.2f} → ${exit_price:.2f} = ${pnl:+.2f}")
    
    return analyze_results(trades, capital, 100000)

def simulate_intraday_orb(data, interval, config):
    """Simular ORB con datos intradía"""
    print(f"📊 Simulando con datos de {interval}")
    
    # Filtrar solo horario de mercado
    ny_tz = pytz.timezone('America/New_York')
    data['datetime'] = pd.to_datetime(data['datetime'])
    
    if data['datetime'].dt.tz is None:
        data['datetime'] = data['datetime'].dt.tz_localize('UTC').dt.tz_convert(ny_tz)
    else:
        data['datetime'] = data['datetime'].dt.tz_convert(ny_tz)
    
    # Filtrar horario de mercado
    data = data[data['datetime'].dt.time >= time(9, 30)]
    data = data[data['datetime'].dt.time <= time(16, 0)]
    data = data[data['datetime'].dt.weekday < 5]
    
    if data.empty:
        return {"error": "No hay datos de horario de mercado"}
    
    # Agrupar por día y simular
    trades = []
    capital = 100000
    
    data['date'] = data['datetime'].dt.date
    
    for date, day_data in data.groupby('date'):
        day_data = day_data.sort_values('datetime').reset_index(drop=True)
        
        # Establecer ORB (primeras barras hasta 9:45)
        orb_data = day_data[day_data['datetime'].dt.time <= time(9, 45)]
        if len(orb_data) == 0:
            continue
        
        orb_high = orb_data['high'].max()
        orb_low = orb_data['low'].min()
        
        # Buscar breakout después de 9:45
        post_orb = day_data[day_data['datetime'].dt.time > time(9, 45)]
        
        for idx, row in post_orb.iterrows():
            if row['datetime'].time() >= time(15, 0):  # No operar después de 3 PM
                break
            
            # Verificar breakout
            if row['close'] > orb_high:
                entry_price = row['close']
                stop_price = entry_price * (1 + config.stop_loss_pct)
                target_price = entry_price * (1 + config.take_profit_pct)
                
                # Simular salida
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
                
                # Calcular trade
                shares = int(config.max_position_size / entry_price)
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
                
                capital += pnl
                print(f"📈 {date}: ${entry_price:.2f} → ${exit_price:.2f} = ${pnl:+.2f} ({exit_reason})")
                break  # Solo un trade por día
    
    return analyze_results(trades, capital, 100000)

def analyze_results(trades, final_capital, initial_capital):
    """Analizar resultados del backtest"""
    if not trades:
        return {"error": "No se ejecutaron trades"}
    
    df = pd.DataFrame(trades)
    
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    win_rate = winning_trades / total_trades
    
    total_pnl = df['pnl'].sum()
    avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['pnl'] < 0]['pnl'].mean() if winning_trades < total_trades else 0
    
    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': total_trades - winning_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'best_trade': df['pnl'].max(),
        'worst_trade': df['pnl'].min(),
        'total_return': (final_capital - initial_capital) / initial_capital,
        'final_capital': final_capital,
        'exit_reasons': df['exit_reason'].value_counts().to_dict(),
        'trades': trades
    }

def print_results(results, config):
    """Imprimir resultados del backtest"""
    print("\n" + "="*60)
    print("📊 BACKTEST RESULTS - ESTRATEGIA ORB")
    print("="*60)
    print(f"Configuración: Max ${config.max_position_size} por trade")
    print(f"Stop Loss: {config.stop_loss_pct*100:.1f}%")
    print(f"Take Profit: {config.take_profit_pct*100:.1f}%")
    print()
    
    print("🎯 PERFORMANCE:")
    print(f"   Total Trades: {results['total_trades']}")
    print(f"   Ganadores: {results['winning_trades']}")
    print(f"   Perdedores: {results['losing_trades']}")
    print(f"   Win Rate: {results['win_rate']:.1%}")
    print(f"   Total Return: {results['total_return']:.1%}")
    print()
    
    print("💰 P&L ANALYSIS:")
    print(f"   Total P&L: ${results['total_pnl']:+,.2f}")
    print(f"   Promedio Ganador: ${results['avg_win']:+.2f}")
    print(f"   Promedio Perdedor: ${results['avg_loss']:+.2f}")
    print(f"   Mejor Trade: ${results['best_trade']:+.2f}")
    print(f"   Peor Trade: ${results['worst_trade']:+.2f}")
    print()
    
    print("🚪 RAZONES DE SALIDA:")
    for reason, count in results['exit_reasons'].items():
        pct = count / results['total_trades'] * 100
        print(f"   {reason}: {count} ({pct:.1f}%)")
    
    print("="*60)

def main():
    """Función principal"""
    print("🚀 BACKTEST ORB - VERSIÓN SIMPLIFICADA")
    
    # Cargar configuración
    config = ORBConfig.load_from_file()
    
    # Descargar datos
    data, interval = download_nvda_data(30)
    
    if data is None:
        print("❌ No se pudieron obtener datos")
        return
    
    # Ejecutar simulación
    results = simulate_orb_strategy(data, interval, config)
    
    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return
    
    # Mostrar resultados
    print_results(results, config)
    
    # Exportar trades
    if results.get('trades'):
        df = pd.DataFrame(results['trades'])
        df.to_csv("data/backtest_results.csv", index=False)
        print("\n📄 Resultados guardados en data/backtest_results.csv")
    
    print("\n✅ Backtest completado!")

if __name__ == "__main__":
    main()