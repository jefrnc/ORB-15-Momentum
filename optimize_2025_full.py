#!/usr/bin/env python3
"""
Optimizador Completo 2025 - Búsqueda Exhaustiva de Parámetros
Prueba todas las combinaciones posibles para encontrar los mejores parámetros
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
from itertools import product
import os

def download_daily_data_2025():
    """Descargar datos diarios de NVDA para todo 2025"""
    print("📥 Descargando datos diarios de NVDA para 2025...")
    
    try:
        start_date = "2025-01-01"
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        nvda = yf.Ticker("NVDA")
        data = nvda.history(start=start_date, end=end_date, interval="1d")
        
        if data.empty:
            print("❌ No se pudieron obtener datos")
            return None
        
        data = data.reset_index()
        data.columns = [col.lower() for col in data.columns]
        
        # Filtrar solo días de trading (lunes a viernes)
        data['date'] = pd.to_datetime(data['date'])
        data = data[data['date'].dt.weekday < 5]
        
        print(f"✅ Datos obtenidos: {len(data)} días de trading en 2025")
        return data
        
    except Exception as e:
        print(f"❌ Error descargando datos: {e}")
        return None

def simulate_orb_with_params(data, stop_loss_pct, take_profit_pct, max_position_size=500):
    """
    Simular ORB con parámetros específicos usando datos diarios
    """
    if data is None or data.empty:
        return None
    
    trades = []
    
    # Seed para reproducibilidad
    np.random.seed(42)
    
    for i in range(len(data)):
        row = data.iloc[i]
        
        # Calcular rango intradía esperado
        daily_range_pct = (row['high'] - row['low']) / row['open']
        
        # Simular ORB range (15-25% del rango diario)
        orb_range_pct = daily_range_pct * np.random.uniform(0.15, 0.25)
        
        # ORB high estimado
        orb_high = row['open'] * (1 + orb_range_pct * np.random.uniform(0.3, 0.7))
        
        # Solo considerar breakout si el precio superó ORB high durante el día
        if row['high'] >= orb_high:
            # Entrada cerca del ORB high
            entry_price = orb_high * np.random.uniform(1.0, 1.005)
            
            # Calcular stops
            stop_price = entry_price * (1 + stop_loss_pct)
            target_price = entry_price * (1 + take_profit_pct)
            
            # Determinar salida
            exit_price = entry_price
            exit_reason = "TIME_EXIT"
            
            # ¿Tocó el stop loss?
            if row['low'] <= stop_price:
                if np.random.random() < 0.85:  # 85% probabilidad de ejecución
                    exit_price = stop_price
                    exit_reason = "STOP_LOSS"
                else:
                    exit_price = stop_price * np.random.uniform(1.002, 1.008)
                    exit_reason = "NEAR_STOP"
            
            # ¿Tocó el take profit?
            elif row['high'] >= target_price:
                target_probability = 0.3 + (0.4 * (daily_range_pct > 0.03))
                if np.random.random() < target_probability:
                    exit_price = target_price
                    exit_reason = "TAKE_PROFIT"
                else:
                    exit_price = target_price * np.random.uniform(0.992, 0.998)
                    exit_reason = "NEAR_TARGET"
            
            # Si no tocó stops, salida cerca del close
            else:
                close_weight = 0.7
                random_weight = 0.3
                exit_price = (row['close'] * close_weight + 
                            entry_price * random_weight +
                            np.random.normal(0, entry_price * 0.002))
                exit_reason = "TIME_EXIT"
            
            # Calcular trade
            shares = int(max_position_size / entry_price)
            if shares == 0:
                continue
            
            pnl = (exit_price - entry_price) * shares
            return_pct = (exit_price - entry_price) / entry_price * 100
            
            trades.append({
                'pnl': pnl,
                'return_pct': return_pct,
                'exit_reason': exit_reason
            })
    
    return trades

def evaluate_parameters(data, stop_loss_pct, take_profit_pct):
    """Evaluar una combinación específica de parámetros"""
    trades = simulate_orb_with_params(data, stop_loss_pct, take_profit_pct)
    
    if not trades or len(trades) < 5:  # Mínimo 5 trades para ser válido
        return None
    
    df = pd.DataFrame(trades)
    
    # Métricas básicas
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    losing_trades = total_trades - winning_trades
    win_rate = winning_trades / total_trades
    
    # P&L estadísticas
    total_pnl = df['pnl'].sum()
    avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
    
    # Risk/Reward
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    # Drawdown simulation
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['peak'] = df['cumulative_pnl'].cummax()
    df['drawdown'] = df['cumulative_pnl'] - df['peak']
    max_drawdown = df['drawdown'].min()
    
    # Profit factor
    gross_profit = df[df['pnl'] > 0]['pnl'].sum() if winning_trades > 0 else 0
    gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum()) if losing_trades > 0 else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Score compuesto (múltiples factores)
    # Priorizamos: 1) P&L total, 2) Win rate, 3) Profit factor, 4) Drawdown bajo
    pnl_score = max(0, total_pnl / 1000)  # Normalizar P&L
    win_rate_score = win_rate
    pf_score = min(profit_factor / 2, 1)  # Normalizar profit factor
    dd_score = max(0, 1 + max_drawdown / 1000)  # Penalizar drawdown alto
    
    composite_score = (pnl_score * 0.4 + 
                      win_rate_score * 0.3 + 
                      pf_score * 0.2 + 
                      dd_score * 0.1)
    
    return {
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'rr_ratio': rr_ratio,
        'max_drawdown': max_drawdown,
        'profit_factor': profit_factor,
        'composite_score': composite_score,
        'take_profit_rate': len(df[df['exit_reason'] == 'TAKE_PROFIT']) / total_trades
    }

def optimize_parameters(data):
    """Optimización exhaustiva de parámetros"""
    print("🔧 OPTIMIZADOR EXHAUSTIVO DE PARÁMETROS ORB 2025")
    print("="*60)
    
    # Rangos de parámetros más amplios
    stop_loss_range = [
        -0.005, -0.008, -0.01, -0.012, -0.015, -0.018, -0.02, 
        -0.022, -0.025, -0.03, -0.035, -0.04, -0.05
    ]  # -0.5% a -5%
    
    take_profit_range = [
        0.008, 0.01, 0.012, 0.015, 0.018, 0.02, 0.022, 
        0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.06, 0.08, 0.1
    ]  # 0.8% a 10%
    
    total_combinations = len(stop_loss_range) * len(take_profit_range)
    print(f"🧪 Probando {len(stop_loss_range)} × {len(take_profit_range)} = {total_combinations} combinaciones")
    print("⏱️  Esto puede tomar algunos minutos...\n")
    
    results = []
    processed = 0
    
    for stop_loss, take_profit in product(stop_loss_range, take_profit_range):
        # Filtrar combinaciones ilógicas (TP muy bajo vs SL muy alto)
        risk_reward_ratio = take_profit / abs(stop_loss)
        if risk_reward_ratio < 0.3 or risk_reward_ratio > 10:  # Filtrar RR extremos
            continue
        
        result = evaluate_parameters(data, stop_loss, take_profit)
        if result:
            results.append(result)
        
        processed += 1
        if processed % 50 == 0:
            print(f"   Procesadas: {processed}/{total_combinations} combinaciones...")
    
    if not results:
        print("❌ No se encontraron combinaciones válidas")
        return None
    
    print(f"✅ Evaluadas {len(results)} combinaciones válidas\n")
    
    # Ordenar por diferentes métricas
    by_pnl = sorted(results, key=lambda x: x['total_pnl'], reverse=True)
    by_win_rate = sorted(results, key=lambda x: x['win_rate'], reverse=True)
    by_profit_factor = sorted(results, key=lambda x: x['profit_factor'], reverse=True)
    by_composite = sorted(results, key=lambda x: x['composite_score'], reverse=True)
    
    return {
        'all_results': results,
        'by_pnl': by_pnl,
        'by_win_rate': by_win_rate,
        'by_profit_factor': by_profit_factor,
        'by_composite': by_composite
    }

def print_optimization_results(optimization_results):
    """Imprimir resultados de optimización"""
    if not optimization_results:
        return
    
    print("🏆 TOP 10 MEJORES CONFIGURACIONES POR P&L TOTAL:")
    print("-" * 100)
    print(f"{'Rank':<4} {'SL%':<6} {'TP%':<6} {'Trades':<7} {'Win%':<6} {'P&L':<10} {'Avg':<8} {'PF':<6} {'Max DD':<8}")
    print("-" * 100)
    
    for i, result in enumerate(optimization_results['by_pnl'][:10]):
        print(f"{i+1:<4} {result['stop_loss_pct']*100:>5.1f} {result['take_profit_pct']*100:>5.1f} "
              f"{result['total_trades']:>6} {result['win_rate']*100:>5.1f} "
              f"${result['total_pnl']:>+8.2f} ${result['total_pnl']/result['total_trades']:>+6.2f} "
              f"{result['profit_factor']:>5.2f} ${result['max_drawdown']:>+6.2f}")
    
    print("\n🎯 TOP 5 MEJORES POR WIN RATE:")
    print("-" * 85)
    print(f"{'Rank':<4} {'SL%':<6} {'TP%':<6} {'Win%':<6} {'Trades':<7} {'P&L':<10} {'PF':<6}")
    print("-" * 85)
    
    for i, result in enumerate(optimization_results['by_win_rate'][:5]):
        print(f"{i+1:<4} {result['stop_loss_pct']*100:>5.1f} {result['take_profit_pct']*100:>5.1f} "
              f"{result['win_rate']*100:>5.1f} {result['total_trades']:>6} "
              f"${result['total_pnl']:>+8.2f} {result['profit_factor']:>5.2f}")
    
    print("\n💎 TOP 5 MEJORES POR SCORE COMPUESTO:")
    print("-" * 90)
    print(f"{'Rank':<4} {'SL%':<6} {'TP%':<6} {'Score':<6} {'P&L':<10} {'Win%':<6} {'PF':<6}")
    print("-" * 90)
    
    for i, result in enumerate(optimization_results['by_composite'][:5]):
        print(f"{i+1:<4} {result['stop_loss_pct']*100:>5.1f} {result['take_profit_pct']*100:>5.1f} "
              f"{result['composite_score']:>5.3f} ${result['total_pnl']:>+8.2f} "
              f"{result['win_rate']*100:>5.1f} {result['profit_factor']:>5.2f}")
    
    # Análisis detallado del mejor
    best = optimization_results['by_pnl'][0]
    print(f"\n📊 ANÁLISIS DETALLADO - MEJOR CONFIGURACIÓN:")
    print("=" * 50)
    print(f"Stop Loss: {best['stop_loss_pct']*100:.2f}%")
    print(f"Take Profit: {best['take_profit_pct']*100:.2f}%")
    print(f"Risk/Reward Ratio: {best['take_profit_pct']/abs(best['stop_loss_pct']):.2f}")
    print(f"Total Trades: {best['total_trades']}")
    print(f"Win Rate: {best['win_rate']:.1%}")
    print(f"Total P&L: ${best['total_pnl']:+,.2f}")
    print(f"Avg Win: ${best['avg_win']:+.2f}")
    print(f"Avg Loss: ${best['avg_loss']:+.2f}")
    print(f"R/R Ratio: {best['rr_ratio']:.2f}")
    print(f"Profit Factor: {best['profit_factor']:.2f}")
    print(f"Max Drawdown: ${best['max_drawdown']:+.2f}")
    print(f"Take Profit Rate: {best['take_profit_rate']:.1%}")
    print(f"Composite Score: {best['composite_score']:.3f}")
    
    # Comparar con configuraciones estándar
    print(f"\n🔄 COMPARACIÓN CON CONFIGURACIONES ESTÁNDAR:")
    standard_configs = [
        {"name": "Original", "sl": -0.01, "tp": 0.04},
        {"name": "Tu Sugerencia", "sl": -0.01, "tp": 0.02},
        {"name": "Conservadora", "sl": -0.015, "tp": 0.015}
    ]
    
    for config in standard_configs:
        # Buscar la configuración más cercana en los resultados
        closest = min(optimization_results['all_results'], 
                     key=lambda x: abs(x['stop_loss_pct'] - config['sl']) + 
                                  abs(x['take_profit_pct'] - config['tp']))
        
        improvement = best['total_pnl'] - closest['total_pnl']
        print(f"   vs {config['name']}: ${improvement:+.2f} mejora")

def export_results(optimization_results):
    """Exportar resultados a CSV"""
    if not optimization_results:
        return
    
    # Crear directorio data si no existe
    os.makedirs("data", exist_ok=True)
    
    df = pd.DataFrame(optimization_results['all_results'])
    df.to_csv("data/optimization_results_2025.csv", index=False)
    print(f"\n📄 Resultados completos exportados a data/optimization_results_2025.csv")
    
    # Exportar solo los top 20
    top_20 = pd.DataFrame(optimization_results['by_pnl'][:20])
    top_20.to_csv("data/top_20_configurations.csv", index=False)
    print(f"📄 Top 20 configuraciones exportadas a data/top_20_configurations.csv")

def main():
    """Función principal"""
    print("🚀 OPTIMIZADOR EXHAUSTIVO ORB 2025")
    print("="*50)
    
    # Descargar datos
    data = download_daily_data_2025()
    if data is None:
        return
    
    print(f"📅 Período: 2025-01-01 hasta {datetime.now().strftime('%Y-%m-%d')}")
    print(f"📊 Días de trading: {len(data)}")
    print(f"💰 Posición máxima: $500 por trade\n")
    
    # Ejecutar optimización
    results = optimize_parameters(data)
    
    if results:
        # Mostrar resultados
        print_optimization_results(results)
        
        # Exportar resultados
        export_results(results)
    
    print("\n✅ Optimización completa finalizada!")

if __name__ == "__main__":
    main()