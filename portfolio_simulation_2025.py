#!/usr/bin/env python3
"""
Simulación de Portfolio Real 2025
Proyección de crecimiento desde $500 inicial con estrategia ORB optimizada
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import matplotlib.pyplot as plt
import os

def download_daily_data_2025(symbol):
    """Descargar datos diarios para todo 2025"""
    print(f"📥 Descargando datos diarios de {symbol} para 2025...")
    
    try:
        start_date = "2025-01-01"
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start_date, end=end_date, interval="1d")
        
        if data.empty:
            return None
        
        data = data.reset_index()
        data.columns = [col.lower() for col in data.columns]
        data['date'] = pd.to_datetime(data['date'])
        data = data[data['date'].dt.weekday < 5]  # Solo días de trading
        
        return data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def simulate_portfolio_growth(data, symbol, initial_capital=500, stop_loss_pct=-0.05, take_profit_pct=0.025):
    """
    Simular crecimiento del portfolio día a día
    Usando capital compuesto - reinvirtiendo ganancias
    """
    if data is None or data.empty:
        return None
    
    # Configuraciones optimizadas
    if symbol == "NVDA":
        stop_loss_pct = -0.05  # -5%
        take_profit_pct = 0.025  # +2.5%
    elif symbol == "TSLA":
        stop_loss_pct = -0.08  # -8%
        take_profit_pct = 0.03   # +3%
    
    portfolio_history = []
    current_capital = initial_capital
    total_trades = 0
    winning_trades = 0
    
    # Seed para reproducibilidad
    np.random.seed(42)
    
    print(f"🚀 Simulando portfolio {symbol} desde ${initial_capital:,.2f}")
    print(f"📊 Configuración: {stop_loss_pct*100:.1f}% SL, {take_profit_pct*100:.1f}% TP\n")
    
    for i, row in data.iterrows():
        date = row['date'].date()
        
        # Estado del portfolio al inicio del día
        portfolio_history.append({
            'date': date,
            'capital_start': current_capital,
            'capital_end': current_capital,
            'trade_pnl': 0,
            'trade_executed': False,
            'exit_reason': None,
            'daily_return': 0,
            'cumulative_return': (current_capital - initial_capital) / initial_capital * 100
        })
        
        # Calcular si hay breakout ORB
        daily_range_pct = (row['high'] - row['low']) / row['open']
        
        # Ajustar probabilidad de ORB según símbolo
        if symbol == "TSLA":
            orb_range_pct = daily_range_pct * np.random.uniform(0.20, 0.35)
        else:  # NVDA
            orb_range_pct = daily_range_pct * np.random.uniform(0.15, 0.25)
        
        orb_high = row['open'] * (1 + orb_range_pct * np.random.uniform(0.3, 0.7))
        
        # ¿Hay breakout?
        if row['high'] >= orb_high and current_capital >= 50:  # Mínimo $50 para operar
            # Calcular posición basada en capital actual
            position_size = min(current_capital * 0.95, 500)  # Máximo $500 o 95% del capital
            
            # Entrada
            entry_price = orb_high * np.random.uniform(1.0, 1.005)
            shares = int(position_size / entry_price)
            
            if shares > 0:
                actual_position = shares * entry_price
                stop_price = entry_price * (1 + stop_loss_pct)
                target_price = entry_price * (1 + take_profit_pct)
                
                # Determinar salida
                exit_price = entry_price
                exit_reason = "TIME_EXIT"
                
                # Stop loss
                if row['low'] <= stop_price:
                    prob_execution = 0.90 if symbol == "TSLA" else 0.85
                    if np.random.random() < prob_execution:
                        exit_price = stop_price
                        exit_reason = "STOP_LOSS"
                    else:
                        exit_price = stop_price * np.random.uniform(1.002, 1.008)
                        exit_reason = "NEAR_STOP"
                
                # Take profit
                elif row['high'] >= target_price:
                    if symbol == "TSLA":
                        target_prob = 0.35 + (0.5 * (daily_range_pct > 0.04))
                    else:  # NVDA
                        target_prob = 0.3 + (0.4 * (daily_range_pct > 0.03))
                    
                    if np.random.random() < target_prob:
                        exit_price = target_price
                        exit_reason = "TAKE_PROFIT"
                    else:
                        exit_price = target_price * np.random.uniform(0.992, 0.998)
                        exit_reason = "NEAR_TARGET"
                
                # Time exit
                else:
                    close_weight = 0.6 if symbol == "TSLA" else 0.7
                    random_weight = 1 - close_weight
                    noise_factor = 0.004 if symbol == "TSLA" else 0.002
                    
                    exit_price = (row['close'] * close_weight + 
                                entry_price * random_weight +
                                np.random.normal(0, entry_price * noise_factor))
                    exit_reason = "TIME_EXIT"
                
                # Calcular P&L
                trade_pnl = (exit_price - entry_price) * shares
                return_pct = (exit_price - entry_price) / entry_price * 100
                
                # Actualizar capital
                current_capital += trade_pnl
                total_trades += 1
                
                if trade_pnl > 0:
                    winning_trades += 1
                
                # Actualizar registro del día
                portfolio_history[-1].update({
                    'capital_end': current_capital,
                    'trade_pnl': trade_pnl,
                    'trade_executed': True,
                    'exit_reason': exit_reason,
                    'daily_return': return_pct,
                    'cumulative_return': (current_capital - initial_capital) / initial_capital * 100,
                    'position_size': actual_position,
                    'shares': shares,
                    'entry_price': entry_price,
                    'exit_price': exit_price
                })
                
                # Log de trades importantes
                if abs(trade_pnl) > 20 or total_trades % 20 == 0:
                    status = "📈" if trade_pnl > 0 else "📉"
                    print(f"{status} {date}: ${entry_price:.2f}→${exit_price:.2f} = ${trade_pnl:+.2f} | Capital: ${current_capital:,.2f}")
    
    # Estadísticas finales
    df = pd.DataFrame(portfolio_history)
    trades_df = df[df['trade_executed'] == True]
    
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    total_return = (current_capital - initial_capital) / initial_capital * 100
    final_pnl = current_capital - initial_capital
    
    # Calcular drawdown máximo
    df['peak'] = df['capital_end'].cummax()
    df['drawdown'] = (df['capital_end'] - df['peak']) / df['peak'] * 100
    max_drawdown = df['drawdown'].min()
    
    return {
        'symbol': symbol,
        'initial_capital': initial_capital,
        'final_capital': current_capital,
        'total_pnl': final_pnl,
        'total_return': total_return,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'portfolio_history': df,
        'trades_history': trades_df,
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct
    }

def create_portfolio_chart(results, symbol):
    """Crear gráfico de evolución del portfolio"""
    if not results:
        return
    
    df = results['portfolio_history']
    
    plt.figure(figsize=(14, 8))
    
    # Subplot 1: Evolución del capital
    plt.subplot(2, 1, 1)
    plt.plot(df['date'], df['capital_end'], linewidth=2, color='blue', label=f'{symbol} Portfolio')
    plt.axhline(y=results['initial_capital'], color='gray', linestyle='--', alpha=0.7, label='Capital Inicial')
    plt.title(f'📈 Evolución Portfolio {symbol} - ${results["initial_capital"]:,.0f} → ${results["final_capital"]:,.2f} ({results["total_return"]:+.1f}%)')
    plt.ylabel('Capital ($)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Subplot 2: Drawdown
    plt.subplot(2, 1, 2)
    plt.fill_between(df['date'], df['drawdown'], 0, color='red', alpha=0.3, label='Drawdown')
    plt.axhline(y=results['max_drawdown'], color='red', linestyle='--', label=f'Max DD: {results["max_drawdown"]:.1f}%')
    plt.title('📉 Drawdown del Portfolio')
    plt.ylabel('Drawdown (%)')
    plt.xlabel('Fecha')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Guardar gráfico
    os.makedirs("data", exist_ok=True)
    plt.savefig(f'data/portfolio_evolution_{symbol}_2025.png', dpi=150, bbox_inches='tight')
    print(f"📊 Gráfico guardado: data/portfolio_evolution_{symbol}_2025.png")
    plt.close()

def print_portfolio_results(results):
    """Imprimir resultados detallados del portfolio"""
    if not results:
        return
    
    symbol = results['symbol']
    
    print(f"\n🏆 RESULTADOS PORTFOLIO {symbol} - ENERO A JULIO 2025")
    print("=" * 65)
    
    print(f"💰 PERFORMANCE:")
    print(f"   Capital Inicial: ${results['initial_capital']:,.2f}")
    print(f"   Capital Final: ${results['final_capital']:,.2f}")
    print(f"   P&L Total: ${results['total_pnl']:+,.2f}")
    print(f"   Retorno Total: {results['total_return']:+.2f}%")
    print(f"   Retorno Anualizado: {(results['total_return'] * 12/6):+.1f}%")  # 6 meses aprox
    
    print(f"\n📊 ESTADÍSTICAS DE TRADING:")
    print(f"   Total Trades: {results['total_trades']}")
    print(f"   Trades Ganadores: {results['winning_trades']}")
    print(f"   Win Rate: {results['win_rate']:.1%}")
    print(f"   Max Drawdown: {results['max_drawdown']:.1f}%")
    print(f"   Config: {results['stop_loss_pct']*100:.1f}% SL, {results['take_profit_pct']*100:.1f}% TP")
    
    # Análisis mensual
    df = results['portfolio_history']
    df['month'] = pd.to_datetime(df['date']).dt.to_period('M')
    monthly_trades = df[df['trade_executed'] == True].groupby('month').agg({
        'trade_pnl': ['sum', 'count']
    }).round(2)
    
    print(f"\n📅 PERFORMANCE MENSUAL:")
    if not monthly_trades.empty:
        monthly_trades.columns = ['P&L', 'Trades']
        for month, row in monthly_trades.iterrows():
            print(f"   {month}: {int(row['Trades'])} trades, ${row['P&L']:+.2f} P&L")
    
    # Estadísticas de trades
    trades_df = results['trades_history']
    if not trades_df.empty:
        print(f"\n🎯 ANÁLISIS DE TRADES:")
        avg_win = trades_df[trades_df['trade_pnl'] > 0]['trade_pnl'].mean()
        avg_loss = trades_df[trades_df['trade_pnl'] < 0]['trade_pnl'].mean()
        best_trade = trades_df['trade_pnl'].max()
        worst_trade = trades_df['trade_pnl'].min()
        
        print(f"   Ganancia Promedio: ${avg_win:+.2f}")
        print(f"   Pérdida Promedio: ${avg_loss:+.2f}")
        print(f"   Mejor Trade: ${best_trade:+.2f}")
        print(f"   Peor Trade: ${worst_trade:+.2f}")
        
        # Exit reasons
        exit_reasons = trades_df['exit_reason'].value_counts()
        print(f"\n🚪 RAZONES DE SALIDA:")
        for reason, count in exit_reasons.items():
            pct = count / len(trades_df) * 100
            print(f"   {reason}: {count} ({pct:.1f}%)")

def compare_portfolios(nvda_results, tsla_results):
    """Comparar resultados de ambos portfolios"""
    if not nvda_results or not tsla_results:
        return
    
    print(f"\n🥊 COMPARACIÓN DIRECTA: NVDA vs TSLA")
    print("=" * 60)
    
    print(f"{'Métrica':<20} {'NVDA':<15} {'TSLA':<15} {'Ganador':<10}")
    print("-" * 60)
    
    metrics = [
        ('Capital Final', f"${nvda_results['final_capital']:,.2f}", f"${tsla_results['final_capital']:,.2f}"),
        ('P&L Total', f"${nvda_results['total_pnl']:+,.2f}", f"${tsla_results['total_pnl']:+,.2f}"),
        ('Retorno %', f"{nvda_results['total_return']:+.1f}%", f"{tsla_results['total_return']:+.1f}%"),
        ('Total Trades', f"{nvda_results['total_trades']}", f"{tsla_results['total_trades']}"),
        ('Win Rate', f"{nvda_results['win_rate']:.1%}", f"{tsla_results['win_rate']:.1%}"),
        ('Max Drawdown', f"{nvda_results['max_drawdown']:.1f}%", f"{tsla_results['max_drawdown']:.1f}%")
    ]
    
    for metric, nvda_val, tsla_val in metrics:
        if metric in ['Capital Final', 'P&L Total', 'Retorno %']:
            nvda_num = float(nvda_val.replace('$', '').replace(',', '').replace('%', '').replace('+', ''))
            tsla_num = float(tsla_val.replace('$', '').replace(',', '').replace('%', '').replace('+', ''))
            winner = "🏆 TSLA" if tsla_num > nvda_num else "🏆 NVDA"
        elif metric == 'Win Rate':
            winner = "🏆 NVDA" if nvda_results['win_rate'] > tsla_results['win_rate'] else "🏆 TSLA"
        elif metric == 'Max Drawdown':
            winner = "🏆 NVDA" if nvda_results['max_drawdown'] > tsla_results['max_drawdown'] else "🏆 TSLA"
        else:
            winner = "-"
        
        print(f"{metric:<20} {nvda_val:<15} {tsla_val:<15} {winner:<10}")
    
    # Veredicto final
    nvda_score = 0
    tsla_score = 0
    
    if nvda_results['final_capital'] > tsla_results['final_capital']:
        nvda_score += 1
    else:
        tsla_score += 1
    
    if nvda_results['win_rate'] > tsla_results['win_rate']:
        nvda_score += 1
    else:
        tsla_score += 1
    
    if nvda_results['max_drawdown'] > tsla_results['max_drawdown']:
        nvda_score += 1
    else:
        tsla_score += 1
    
    print(f"\n🏁 VEREDICTO FINAL:")
    if tsla_score > nvda_score:
        difference = tsla_results['final_capital'] - nvda_results['final_capital']
        print(f"🏆 TSLA ES SUPERIOR - Diferencia: ${difference:+,.2f}")
    elif nvda_score > tsla_score:
        difference = nvda_results['final_capital'] - tsla_results['final_capital']
        print(f"🏆 NVDA ES SUPERIOR - Diferencia: ${difference:+,.2f}")
    else:
        print(f"🤝 EMPATE - Ambas estrategias son similares")

def main():
    """Función principal"""
    print("💼 SIMULACIÓN DE PORTFOLIO REAL 2025")
    print("=" * 50)
    print("🎯 Objetivo: Simular crecimiento desde $500 iniciales")
    print("📈 Estrategia: ORB con parámetros optimizados")
    print("🔄 Reinversión: Capital compuesto\n")
    
    initial_capital = 500
    
    # Simular NVDA
    print("1️⃣ SIMULANDO NVDA...")
    nvda_data = download_daily_data_2025("NVDA")
    nvda_results = simulate_portfolio_growth(nvda_data, "NVDA", initial_capital)
    
    if nvda_results:
        print_portfolio_results(nvda_results)
        create_portfolio_chart(nvda_results, "NVDA")
    
    print("\n" + "="*70 + "\n")
    
    # Simular TSLA
    print("2️⃣ SIMULANDO TSLA...")
    tsla_data = download_daily_data_2025("TSLA")
    tsla_results = simulate_portfolio_growth(tsla_data, "TSLA", initial_capital)
    
    if tsla_results:
        print_portfolio_results(tsla_results)
        create_portfolio_chart(tsla_results, "TSLA")
    
    # Comparación final
    if nvda_results and tsla_results:
        compare_portfolios(nvda_results, tsla_results)
        
        # Exportar datos
        os.makedirs("data", exist_ok=True)
        nvda_results['portfolio_history'].to_csv("data/nvda_portfolio_2025.csv", index=False)
        tsla_results['portfolio_history'].to_csv("data/tsla_portfolio_2025.csv", index=False)
        print(f"\n📄 Datos exportados a data/nvda_portfolio_2025.csv y data/tsla_portfolio_2025.csv")
    
    print("\n✅ Simulación de portfolio completada!")

if __name__ == "__main__":
    main()