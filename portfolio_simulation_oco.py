#!/usr/bin/env python3
"""
Simulación de Portfolio con Órdenes OCO (One-Cancels-Other)
Comparación: Cerrar en el día vs Dejar órdenes abiertas hasta ser ejecutadas
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

def simulate_oco_strategy(data, symbol, initial_capital=500, stop_loss_pct=-0.05, take_profit_pct=0.025, max_hold_days=5):
    """
    Simular estrategia con órdenes OCO que permanecen activas múltiples días
    max_hold_days: máximo días que una orden puede permanecer abierta
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
    open_positions = []  # Lista de posiciones abiertas con órdenes OCO
    total_trades = 0
    winning_trades = 0
    
    # Seed para reproducibilidad
    np.random.seed(42)
    
    print(f"🚀 Simulando portfolio {symbol} con OCO desde ${initial_capital:,.2f}")
    print(f"📊 Configuración: {stop_loss_pct*100:.1f}% SL, {take_profit_pct*100:.1f}% TP")
    print(f"⏱️  Max hold: {max_hold_days} días\n")
    
    for i, row in data.iterrows():
        date = row['date'].date()
        
        # Estado del portfolio al inicio del día
        day_start_capital = current_capital
        daily_pnl = 0
        trades_closed_today = 0
        
        # 1. REVISAR POSICIONES ABIERTAS PRIMERO
        positions_to_remove = []
        
        for pos_idx, position in enumerate(open_positions):
            days_open = (date - position['entry_date']).days
            
            # Cerrar posición si excede máximo días
            if days_open >= max_hold_days:
                # Cerrar en precio de apertura con slippage
                exit_price = row['open'] * np.random.uniform(0.998, 1.002)
                exit_reason = "MAX_DAYS"
            
            # Verificar si toca stop loss
            elif row['low'] <= position['stop_price']:
                # Probabilidad de ejecución del stop
                prob_execution = 0.90 if symbol == "TSLA" else 0.85
                if np.random.random() < prob_execution:
                    exit_price = position['stop_price']
                    exit_reason = "STOP_LOSS"
                else:
                    # Gap down, peor precio que el stop
                    exit_price = position['stop_price'] * np.random.uniform(0.992, 0.998)
                    exit_reason = "STOP_SLIPPAGE"
            
            # Verificar si toca take profit
            elif row['high'] >= position['target_price']:
                # Probabilidad de alcanzar target completo
                if symbol == "TSLA":
                    target_prob = 0.75  # TSLA tiende a tener movimientos más extremos
                else:  # NVDA
                    target_prob = 0.70
                
                if np.random.random() < target_prob:
                    exit_price = position['target_price']
                    exit_reason = "TAKE_PROFIT"
                else:
                    # Cerca del target pero no completamente
                    exit_price = position['target_price'] * np.random.uniform(0.995, 0.999)
                    exit_reason = "NEAR_TARGET"
            
            else:
                # Posición sigue abierta
                continue
            
            # CERRAR POSICIÓN
            trade_pnl = (exit_price - position['entry_price']) * position['shares']
            current_capital += trade_pnl
            daily_pnl += trade_pnl
            total_trades += 1
            trades_closed_today += 1
            
            if trade_pnl > 0:
                winning_trades += 1
            
            # Log del trade cerrado
            hold_days = (date - position['entry_date']).days
            print(f"{'📈' if trade_pnl > 0 else '📉'} {date}: ${position['entry_price']:.2f}→${exit_price:.2f} = ${trade_pnl:+.2f} ({hold_days}d, {exit_reason})")
            
            positions_to_remove.append(pos_idx)
        
        # Remover posiciones cerradas
        for idx in reversed(positions_to_remove):
            open_positions.pop(idx)
        
        # 2. VERIFICAR SI HAY NUEVO BREAKOUT ORB
        # Solo abrir nueva posición si tenemos capital libre
        available_capital = current_capital * 0.9  # Usar máximo 90% del capital
        max_position_per_trade = min(500, available_capital / max(1, len(open_positions) + 1))
        
        if max_position_per_trade >= 50:  # Mínimo $50 para abrir posición
            # Calcular si hay breakout ORB
            daily_range_pct = (row['high'] - row['low']) / row['open']
            
            # Ajustar probabilidad de ORB según símbolo
            if symbol == "TSLA":
                orb_range_pct = daily_range_pct * np.random.uniform(0.20, 0.35)
            else:  # NVDA
                orb_range_pct = daily_range_pct * np.random.uniform(0.15, 0.25)
            
            orb_high = row['open'] * (1 + orb_range_pct * np.random.uniform(0.3, 0.7))
            
            # ¿Hay breakout hoy?
            if row['high'] >= orb_high:
                # ABRIR NUEVA POSICIÓN CON OCO
                entry_price = orb_high * np.random.uniform(1.0, 1.005)
                shares = int(max_position_per_trade / entry_price)
                
                if shares > 0:
                    actual_position = shares * entry_price
                    stop_price = entry_price * (1 + stop_loss_pct)
                    target_price = entry_price * (1 + take_profit_pct)
                    
                    # Agregar posición a lista de abiertas
                    new_position = {
                        'entry_date': date,
                        'entry_price': entry_price,
                        'stop_price': stop_price,
                        'target_price': target_price,
                        'shares': shares,
                        'position_size': actual_position
                    }
                    
                    open_positions.append(new_position)
                    current_capital -= actual_position  # Restar capital usado
                    
                    print(f"🟢 {date}: Nueva posición ${entry_price:.2f} ({shares} shares, ${actual_position:.2f})")
        
        # Registrar estado del día
        portfolio_history.append({
            'date': date,
            'capital_start': day_start_capital,
            'capital_end': current_capital,
            'daily_pnl': daily_pnl,
            'trades_closed': trades_closed_today,
            'open_positions': len(open_positions),
            'capital_in_positions': sum(pos['position_size'] for pos in open_positions),
            'free_capital': current_capital,
            'total_capital': current_capital + sum(pos['position_size'] for pos in open_positions),
            'cumulative_return': ((current_capital + sum(pos['position_size'] for pos in open_positions) - initial_capital) / initial_capital * 100)
        })
    
    # Cerrar todas las posiciones abiertas al final
    final_date = data.iloc[-1]['date'].date()
    final_close = data.iloc[-1]['close']
    
    for position in open_positions:
        # Cerrar en precio de cierre
        exit_price = final_close * np.random.uniform(0.998, 1.002)
        trade_pnl = (exit_price - position['entry_price']) * position['shares']
        current_capital += trade_pnl
        total_trades += 1
        
        if trade_pnl > 0:
            winning_trades += 1
        
        hold_days = (final_date - position['entry_date']).days
        print(f"🔴 {final_date}: Cierre final ${position['entry_price']:.2f}→${exit_price:.2f} = ${trade_pnl:+.2f} ({hold_days}d)")
    
    # Estadísticas finales
    df = pd.DataFrame(portfolio_history)
    
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    total_return = (current_capital - initial_capital) / initial_capital * 100
    final_pnl = current_capital - initial_capital
    
    # Calcular drawdown máximo
    df['peak'] = df['total_capital'].cummax()
    df['drawdown'] = (df['total_capital'] - df['peak']) / df['peak'] * 100
    max_drawdown = df['drawdown'].min()
    
    return {
        'symbol': symbol,
        'strategy': 'OCO',
        'initial_capital': initial_capital,
        'final_capital': current_capital,
        'total_pnl': final_pnl,
        'total_return': total_return,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'max_hold_days': max_hold_days,
        'portfolio_history': df,
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct
    }

def simulate_intraday_strategy(data, symbol, initial_capital=500, stop_loss_pct=-0.05, take_profit_pct=0.025):
    """
    Simular estrategia intradía (cierre forzado al final del día)
    Para comparación con estrategia OCO
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
    
    for i, row in data.iterrows():
        date = row['date'].date()
        day_start_capital = current_capital
        
        # Calcular si hay breakout ORB
        daily_range_pct = (row['high'] - row['low']) / row['open']
        
        if symbol == "TSLA":
            orb_range_pct = daily_range_pct * np.random.uniform(0.20, 0.35)
        else:  # NVDA
            orb_range_pct = daily_range_pct * np.random.uniform(0.15, 0.25)
        
        orb_high = row['open'] * (1 + orb_range_pct * np.random.uniform(0.3, 0.7))
        
        # ¿Hay breakout y capital suficiente?
        if row['high'] >= orb_high and current_capital >= 50:
            position_size = min(current_capital * 0.95, 500)
            entry_price = orb_high * np.random.uniform(1.0, 1.005)
            shares = int(position_size / entry_price)
            
            if shares > 0:
                actual_position = shares * entry_price
                stop_price = entry_price * (1 + stop_loss_pct)
                target_price = entry_price * (1 + take_profit_pct)
                
                # Determinar salida SAME DAY
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
                
                # Time exit (forced end of day)
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
                current_capital += trade_pnl
                total_trades += 1
                
                if trade_pnl > 0:
                    winning_trades += 1
                
                portfolio_history.append({
                    'date': date,
                    'capital_start': day_start_capital,
                    'capital_end': current_capital,
                    'daily_pnl': trade_pnl,
                    'trades_closed': 1,
                    'exit_reason': exit_reason
                })
            else:
                portfolio_history.append({
                    'date': date,
                    'capital_start': day_start_capital,
                    'capital_end': current_capital,
                    'daily_pnl': 0,
                    'trades_closed': 0,
                    'exit_reason': None
                })
        else:
            portfolio_history.append({
                'date': date,
                'capital_start': day_start_capital,
                'capital_end': current_capital,
                'daily_pnl': 0,
                'trades_closed': 0,
                'exit_reason': None
            })
    
    # Estadísticas finales
    df = pd.DataFrame(portfolio_history)
    
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    total_return = (current_capital - initial_capital) / initial_capital * 100
    final_pnl = current_capital - initial_capital
    
    # Calcular drawdown máximo
    df['peak'] = df['capital_end'].cummax()
    df['drawdown'] = (df['capital_end'] - df['peak']) / df['peak'] * 100
    max_drawdown = df['drawdown'].min()
    
    return {
        'symbol': symbol,
        'strategy': 'INTRADAY',
        'initial_capital': initial_capital,
        'final_capital': current_capital,
        'total_pnl': final_pnl,
        'total_return': total_return,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'portfolio_history': df,
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct
    }

def print_comparison_results(oco_results, intraday_results):
    """Comparar resultados de ambas estrategias"""
    symbol = oco_results['symbol']
    
    print(f"\n🔄 COMPARACIÓN {symbol}: OCO vs INTRADÍA")
    print("=" * 60)
    
    print(f"{'Métrica':<25} {'OCO':<15} {'Intradía':<15} {'Diferencia':<12}")
    print("-" * 70)
    
    metrics = [
        ('Capital Final', f"${oco_results['final_capital']:,.2f}", f"${intraday_results['final_capital']:,.2f}"),
        ('P&L Total', f"${oco_results['total_pnl']:+,.2f}", f"${intraday_results['total_pnl']:+,.2f}"),
        ('Retorno %', f"{oco_results['total_return']:+.1f}%", f"{intraday_results['total_return']:+.1f}%"),
        ('Total Trades', f"{oco_results['total_trades']}", f"{intraday_results['total_trades']}"),
        ('Win Rate', f"{oco_results['win_rate']:.1%}", f"{intraday_results['win_rate']:.1%}"),
        ('Max Drawdown', f"{oco_results['max_drawdown']:.1f}%", f"{intraday_results['max_drawdown']:.1f}%")
    ]
    
    for metric, oco_val, intraday_val in metrics:
        if metric in ['Capital Final', 'P&L Total', 'Retorno %']:
            oco_num = float(oco_val.replace('$', '').replace(',', '').replace('%', '').replace('+', ''))
            intraday_num = float(intraday_val.replace('$', '').replace(',', '').replace('%', '').replace('+', ''))
            diff = oco_num - intraday_num
            diff_str = f"${diff:+,.2f}" if '$' in oco_val else f"{diff:+.1f}%"
        else:
            diff_str = "-"
        
        print(f"{metric:<25} {oco_val:<15} {intraday_val:<15} {diff_str:<12}")
    
    # Veredicto
    improvement = oco_results['final_capital'] - intraday_results['final_capital']
    improvement_pct = (improvement / intraday_results['final_capital']) * 100
    
    print(f"\n📊 VEREDICTO {symbol}:")
    if improvement > 0:
        print(f"🏆 OCO ES SUPERIOR: +${improvement:,.2f} ({improvement_pct:+.1f}%)")
        print(f"   Beneficio de mantener órdenes activas vs cierre intradía")
    else:
        print(f"❌ INTRADÍA ES SUPERIOR: ${improvement:,.2f} ({improvement_pct:+.1f}%)")
        print(f"   El cierre intradía previene mayores pérdidas")

def main():
    """Función principal"""
    print("🔄 COMPARACIÓN: OCO vs CIERRE INTRADÍA")
    print("=" * 50)
    print("🎯 OCO: Órdenes permanecen activas hasta ser ejecutadas")
    print("📅 Intradía: Cierre forzado al final del día")
    print("💰 Capital inicial: $500\n")
    
    symbols = ["TSLA", "NVDA"]
    
    for symbol in symbols:
        print(f"\n{'='*20} {symbol} {'='*20}")
        
        # Descargar datos
        data = download_daily_data_2025(symbol)
        if data is None:
            continue
        
        # Simular ambas estrategias
        print(f"\n1️⃣ Simulando {symbol} con OCO (max 5 días)...")
        oco_results = simulate_oco_strategy(data, symbol, max_hold_days=5)
        
        print(f"\n2️⃣ Simulando {symbol} intradía...")
        intraday_results = simulate_intraday_strategy(data, symbol)
        
        # Comparar resultados
        if oco_results and intraday_results:
            print_comparison_results(oco_results, intraday_results)
            
            # Exportar datos
            os.makedirs("data", exist_ok=True)
            oco_results['portfolio_history'].to_csv(f"data/{symbol.lower()}_oco_strategy.csv", index=False)
            intraday_results['portfolio_history'].to_csv(f"data/{symbol.lower()}_intraday_strategy.csv", index=False)
    
    print(f"\n✅ Comparación OCO vs Intradía completada!")
    print(f"📄 Datos exportados a data/")

if __name__ == "__main__":
    main()