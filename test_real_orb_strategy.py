#!/usr/bin/env python3
"""
Backtesting de la Estrategia ORB REAL según TrendSpider:
- Stop Loss: -0.5% (NO -1%)
- Take Profit: +4%
- Cierre forzado: 15:00 (3 PM ET)
- Solo datos intradía reales
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import os

def download_intraday_data(symbol="NVDA", period="60d"):
    """
    Descargar datos intradía REALES de 15 minutos
    Máximo 60 días por limitaciones de Yahoo Finance
    """
    print(f"📥 Descargando datos REALES de 15min de {symbol}...")
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Intentar 15min primero, luego 5min si no funciona
        for interval in ["15m", "5m", "1h"]:
            try:
                print(f"   Intentando intervalo {interval}...")
                data = ticker.history(period=period, interval=interval, prepost=False)
                
                if not data.empty:
                    print(f"✅ Datos obtenidos: {len(data)} barras de {interval}")
                    return data, interval
                    
            except Exception as e:
                print(f"   ❌ Error con {interval}: {e}")
                continue
        
        print("❌ No se pudieron obtener datos intradía")
        return None, None
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        return None, None

def test_real_orb_strategy(data, interval, symbol="NVDA"):
    """
    Implementar la estrategia ORB EXACTA según TrendSpider:
    
    ENTRADA: 15min candle cierra > ORB High (primer 15min del día)
    SALIDA: +4% TP, -0.5% SL, o 15:00 ET
    """
    if data is None or data.empty:
        return None
    
    print(f"🚀 Probando estrategia ORB REAL con datos {interval}")
    print("📋 Configuración ORIGINAL TrendSpider:")
    print("   • Stop Loss: -0.5%")
    print("   • Take Profit: +4%") 
    print("   • Cierre forzado: 15:00 ET")
    print("   • Solo breakouts del ORB de 9:30-9:45\n")
    
    # Configuración EXACTA según TrendSpider
    STOP_LOSS_PCT = -0.005  # -0.5%
    TAKE_PROFIT_PCT = 0.04  # +4%
    MAX_POSITION_SIZE = 500
    
    # Preparar datos
    data = data.reset_index()
    data.columns = [col.lower() for col in data.columns]
    
    # Convertir a Eastern Time
    ny_tz = pytz.timezone('America/New_York')
    data['datetime'] = pd.to_datetime(data['datetime'])
    
    if data['datetime'].dt.tz is None:
        data['datetime'] = data['datetime'].dt.tz_localize('UTC').dt.tz_convert(ny_tz)
    else:
        data['datetime'] = data['datetime'].dt.tz_convert(ny_tz)
    
    # Filtrar horario de mercado (9:30 AM - 4:00 PM ET)
    data = data[data['datetime'].dt.time >= time(9, 30)]
    data = data[data['datetime'].dt.time <= time(16, 0)]
    data = data[data['datetime'].dt.weekday < 5]  # Solo lunes-viernes
    
    if data.empty:
        print("❌ No hay datos de horario de mercado")
        return None
    
    print(f"📊 Datos filtrados: {len(data)} barras en horario de mercado")
    
    trades = []
    data['date'] = data['datetime'].dt.date
    
    # Agrupar por día
    for date, day_data in data.groupby('date'):
        day_data = day_data.sort_values('datetime').reset_index(drop=True)
        
        if len(day_data) < 2:
            continue
        
        # 1. ESTABLECER ORB (Opening Range)
        # Primer candle del día (9:30-9:45 o equivalente según intervalo)
        if interval == "15m":
            # Primer candle de 15min = ORB range completo
            orb_candle = day_data.iloc[0]
            orb_high = orb_candle['high']
            orb_low = orb_candle['low']
            post_orb_data = day_data.iloc[1:]  # Desde el segundo candle
        elif interval == "5m":
            # Primeros 3 candles de 5min = 15min ORB
            orb_candles = day_data.iloc[:3]
            if len(orb_candles) < 3:
                continue
            orb_high = orb_candles['high'].max()
            orb_low = orb_candles['low'].min()
            post_orb_data = day_data.iloc[3:]
        else:  # 1h o otros
            # Usar primer candle como aproximación
            orb_candle = day_data.iloc[0]
            orb_high = orb_candle['high']
            orb_low = orb_candle['low']
            post_orb_data = day_data.iloc[1:]
        
        if post_orb_data.empty:
            continue
        
        # 2. BUSCAR BREAKOUT
        # Condición: candle CIERRA por encima del ORB high
        for idx, row in post_orb_data.iterrows():
            # No operar después de las 15:00 (3 PM)
            if row['datetime'].time() >= time(15, 0):
                break
            
            # ¿Candle cierra por encima del ORB high?
            if row['close'] > orb_high:
                # ENTRADA en el CLOSE del candle de breakout
                entry_price = row['close']
                entry_time = row['datetime']
                
                # Calcular niveles
                stop_price = entry_price * (1 + STOP_LOSS_PCT)
                target_price = entry_price * (1 + TAKE_PROFIT_PCT)
                
                # Calcular posición
                shares = int(MAX_POSITION_SIZE / entry_price)
                if shares == 0:
                    continue
                
                # 3. GESTIONAR SALIDA
                # Buscar en candles futuros del mismo día
                future_data = post_orb_data[post_orb_data['datetime'] > entry_time]
                
                exit_price = entry_price
                exit_time = entry_time
                exit_reason = "EOD"
                
                for _, future_candle in future_data.iterrows():
                    current_time = future_candle['datetime'].time()
                    
                    # CIERRE FORZADO a las 15:00
                    if current_time >= time(15, 0):
                        exit_price = future_candle['open']  # Precio de apertura del candle de 15:00
                        exit_time = future_candle['datetime']
                        exit_reason = "TIME_EXIT_15:00"
                        break
                    
                    # STOP LOSS: si toca el nivel de stop
                    if future_candle['low'] <= stop_price:
                        exit_price = stop_price
                        exit_time = future_candle['datetime'] 
                        exit_reason = "STOP_LOSS"
                        break
                    
                    # TAKE PROFIT: si toca el nivel de target
                    if future_candle['high'] >= target_price:
                        exit_price = target_price
                        exit_time = future_candle['datetime']
                        exit_reason = "TAKE_PROFIT"
                        break
                
                # Si llegamos al final del día sin salida
                if exit_reason == "EOD":
                    last_candle = future_data.iloc[-1] if not future_data.empty else row
                    exit_price = last_candle['close']
                    exit_time = last_candle['datetime']
                    exit_reason = "END_OF_DAY"
                
                # Calcular resultado del trade
                pnl = (exit_price - entry_price) * shares
                return_pct = (exit_price - entry_price) / entry_price * 100
                hold_minutes = (exit_time - entry_time).total_seconds() / 60
                
                trades.append({
                    'date': date,
                    'entry_time': entry_time.time(),
                    'exit_time': exit_time.time(),
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': shares,
                    'pnl': pnl,
                    'return_pct': return_pct,
                    'exit_reason': exit_reason,
                    'hold_minutes': hold_minutes,
                    'orb_high': orb_high,
                    'stop_price': stop_price,
                    'target_price': target_price
                })
                
                # Log del trade
                status = "📈" if pnl > 0 else "📉"
                print(f"{status} {date} {entry_time.time()}-{exit_time.time()}: "
                      f"${entry_price:.2f}→${exit_price:.2f} = ${pnl:+.2f} ({exit_reason})")
                
                # Solo un trade por día (primera señal)
                break
    
    return trades

def analyze_real_strategy_results(trades, symbol="NVDA"):
    """Analizar resultados de la estrategia REAL"""
    if not trades:
        print("❌ No se ejecutaron trades")
        return None
    
    df = pd.DataFrame(trades)
    
    # Estadísticas básicas
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    losing_trades = total_trades - winning_trades
    win_rate = winning_trades / total_trades
    
    # P&L
    total_pnl = df['pnl'].sum()
    avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
    best_trade = df['pnl'].max()
    worst_trade = df['pnl'].min()
    
    # Risk/Reward
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    
    # Exit reasons
    exit_reasons = df['exit_reason'].value_counts()
    
    # Tiempo promedio de hold
    avg_hold_minutes = df['hold_minutes'].mean()
    
    # Simulación de portfolio growth
    initial_capital = 10000  # $10k inicial para ver crecimiento
    portfolio_values = [initial_capital]
    current_capital = initial_capital
    
    for pnl in df['pnl']:
        current_capital += pnl
        portfolio_values.append(current_capital)
    
    total_return = (current_capital - initial_capital) / initial_capital * 100
    
    return {
        'symbol': symbol,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'best_trade': best_trade,
        'worst_trade': worst_trade,
        'rr_ratio': rr_ratio,
        'avg_hold_minutes': avg_hold_minutes,
        'total_return': total_return,
        'final_capital': current_capital,
        'exit_reasons': exit_reasons,
        'trades_df': df
    }

def print_real_strategy_results(results):
    """Imprimir resultados de la estrategia REAL"""
    if not results:
        return
    
    print(f"\n🏆 RESULTADOS ESTRATEGIA ORB REAL - {results['symbol']}")
    print("="*60)
    print("📋 Configuración TrendSpider:")
    print("   • Stop Loss: -0.5%")
    print("   • Take Profit: +4%")
    print("   • Cierre: 15:00 ET forzado")
    print("   • Capital por trade: $500")
    
    print(f"\n📊 PERFORMANCE:")
    print(f"   Total Trades: {results['total_trades']}")
    print(f"   Trades Ganadores: {results['winning_trades']}")
    print(f"   Trades Perdedores: {results['losing_trades']}")
    print(f"   Win Rate: {results['win_rate']:.1%}")
    print(f"   Total P&L: ${results['total_pnl']:+,.2f}")
    print(f"   Retorno Total: {results['total_return']:+.1f}%")
    
    print(f"\n💰 ANÁLISIS DE TRADES:")
    print(f"   Ganancia Promedio: ${results['avg_win']:+.2f}")
    print(f"   Pérdida Promedio: ${results['avg_loss']:+.2f}")
    print(f"   Risk/Reward Ratio: {results['rr_ratio']:.2f}")
    print(f"   Mejor Trade: ${results['best_trade']:+.2f}")
    print(f"   Peor Trade: ${results['worst_trade']:+.2f}")
    print(f"   Tiempo Promedio: {results['avg_hold_minutes']:.0f} minutos")
    
    print(f"\n🚪 RAZONES DE SALIDA:")
    for reason, count in results['exit_reasons'].items():
        pct = count / results['total_trades'] * 100
        print(f"   {reason}: {count} ({pct:.1f}%)")
    
    # Comparar con nuestras simulaciones anteriores
    print(f"\n🔄 COMPARACIÓN vs SIMULACIONES ANTERIORES:")
    print(f"   REAL (-0.5% SL): ${results['total_pnl']:+.2f}")
    print(f"   SIMULADO (-5% SL): +$53.32 (NVDA)")
    print(f"   SIMULADO (-8% SL): +$80.93 (TSLA)")
    print(f"\n💡 La estrategia REAL con SL tight puede ser muy diferente!")

def main():
    """Función principal"""
    print("🔍 TESTING DE LA ESTRATEGIA ORB REAL")
    print("="*50)
    print("📋 Según TrendSpider:")
    print("   • Stop Loss: -0.5% (NO -1%)")
    print("   • Take Profit: +4%")
    print("   • Datos: 15min intradía REALES")
    print("   • Cierre forzado: 15:00 ET")
    print("   • Solo NVDA optimizado\n")
    
    # Probar con NVDA (símbolo original)
    symbol = "NVDA"
    data, interval = download_intraday_data(symbol, period="60d")
    
    if data is None:
        print("❌ No se pudieron obtener datos intradía")
        return
    
    # Ejecutar estrategia REAL
    trades = test_real_orb_strategy(data, interval, symbol)
    
    if not trades:
        print("❌ No se ejecutaron trades con la estrategia real")
        return
    
    # Analizar resultados
    results = analyze_real_strategy_results(trades, symbol)
    print_real_strategy_results(results)
    
    # Exportar resultados
    os.makedirs("data", exist_ok=True)
    results['trades_df'].to_csv("data/real_orb_strategy_results.csv", index=False)
    print(f"\n📄 Resultados exportados a data/real_orb_strategy_results.csv")
    
    print("\n✅ Test de estrategia ORB REAL completado!")

if __name__ == "__main__":
    main()