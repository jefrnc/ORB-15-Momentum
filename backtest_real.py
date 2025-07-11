#!/usr/bin/env python3
"""
Backtester ORB con Datos Reales
Usa datos históricos de Yahoo Finance para evaluar la estrategia
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import logging
from src.core.orb_config import ORBConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

class RealORBBacktester:
    """Backtester con datos reales de Yahoo Finance"""
    
    def __init__(self, config: ORBConfig):
        self.config = config
        self.ny_tz = pytz.timezone('America/New_York')
        self.trades = []
        self.daily_stats = []
        
    def download_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Descargar datos históricos de Yahoo Finance"""
        logger.info(f"📥 Descargando datos de {symbol} desde {start_date} hasta {end_date}")
        
        try:
            ticker = yf.Ticker(symbol)
            
            # Intentar primero con datos de 15 minutos
            try:
                logger.info("Intentando descargar datos de 15 minutos...")
                data = ticker.history(
                    start=start_date,
                    end=end_date,
                    interval="15m",
                    prepost=False
                )
            except:
                # Si falla, usar datos de 1 hora
                logger.info("Datos de 15m no disponibles, usando datos de 1 hora...")
                data = ticker.history(
                    start=start_date,
                    end=end_date,
                    interval="1h",
                    prepost=False
                )
            
            if data.empty:
                logger.error("❌ No se pudieron descargar datos")
                return pd.DataFrame()
            
            # Limpiar y preparar datos
            data = data.reset_index()
            data.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            
            # Filtrar solo horario de mercado (9:30-16:00 EST)
            data['timestamp'] = pd.to_datetime(data['timestamp']).dt.tz_convert(self.ny_tz)
            data = data[data['timestamp'].dt.time >= time(9, 30)]
            data = data[data['timestamp'].dt.time <= time(16, 0)]
            
            # Filtrar solo días de semana
            data = data[data['timestamp'].dt.weekday < 5]
            
            logger.info(f"✅ Descargados {len(data)} barras de 15 minutos")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error descargando datos: {e}")
            return pd.DataFrame()
    
    def run_backtest(self, data: pd.DataFrame) -> dict:
        """Ejecutar backtest con datos reales"""
        logger.info("🚀 Iniciando backtest con datos reales")
        
        if data.empty:
            return {"error": "No hay datos para el backtest"}
        
        # Agrupar por fecha
        data['date'] = data['timestamp'].dt.date
        
        # Configuración inicial
        initial_capital = 100000.0
        current_capital = initial_capital
        total_trades = 0
        winning_trades = 0
        
        # Procesar cada día
        for date, day_data in data.groupby('date'):
            # Reset estado diario
            orb_high = None
            orb_low = None
            trade_taken = False
            
            # Ordenar por tiempo
            day_data = day_data.sort_values('timestamp').reset_index(drop=True)
            
            # Establecer rango ORB (9:30-9:45)
            orb_data = day_data[day_data['timestamp'].dt.time <= time(9, 45)]
            if len(orb_data) == 0:
                continue
                
            orb_high = orb_data['high'].max()
            orb_low = orb_data['low'].min()
            
            # Buscar breakout después de 9:45
            post_orb = day_data[day_data['timestamp'].dt.time > time(9, 45)]
            
            for idx, row in post_orb.iterrows():
                current_time = row['timestamp'].time()
                
                # No operar después de las 15:00
                if current_time >= time(15, 0):
                    break
                
                # Si ya operamos hoy, saltar
                if trade_taken:
                    continue
                
                # Verificar breakout (cierre por encima del ORB high)
                if row['close'] > orb_high:
                    # ¡Señal de entrada!
                    entry_price = row['close']
                    stop_price = entry_price * (1 + self.config.stop_loss_pct)
                    target_price = entry_price * (1 + self.config.take_profit_pct)
                    
                    # Calcular posición con $500 máximo
                    shares = int(self.config.max_position_size / entry_price)
                    if shares == 0:
                        continue
                    
                    position_value = shares * entry_price
                    
                    # Simular salida del trade
                    exit_price, exit_reason = self._simulate_exit(
                        post_orb.iloc[post_orb.index.get_loc(idx):],
                        stop_price,
                        target_price
                    )
                    
                    # Calcular P&L
                    pnl = (exit_price - entry_price) * shares
                    return_pct = (exit_price - entry_price) / entry_price * 100
                    
                    # Actualizar capital
                    current_capital += pnl
                    
                    # Registrar trade
                    trade_record = {
                        'date': date,
                        'entry_time': row['timestamp'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'shares': shares,
                        'position_value': position_value,
                        'pnl': pnl,
                        'return_pct': return_pct,
                        'orb_high': orb_high,
                        'orb_low': orb_low,
                        'capital_after': current_capital
                    }
                    
                    self.trades.append(trade_record)
                    total_trades += 1
                    
                    if pnl > 0:
                        winning_trades += 1
                    
                    trade_taken = True
                    
                    logger.info(f"📈 {date}: Entry=${entry_price:.2f}, Exit=${exit_price:.2f}, P&L=${pnl:+.2f} ({return_pct:+.1f}%)")
        
        # Calcular estadísticas
        return self._calculate_statistics(initial_capital, current_capital)
    
    def _simulate_exit(self, future_data: pd.DataFrame, stop_price: float, target_price: float) -> tuple:
        """Simular cómo habría salido el trade"""
        for idx, row in future_data.iterrows():
            # Verificar stop loss (tocó el mínimo)
            if row['low'] <= stop_price:
                return stop_price, 'STOP_LOSS'
            
            # Verificar take profit (tocó el máximo)
            if row['high'] >= target_price:
                return target_price, 'TAKE_PROFIT'
            
            # Cierre forzado a las 15:00
            if row['timestamp'].time() >= time(15, 0):
                return row['close'], 'TIME_EXIT'
        
        # Si llegamos al final del día sin salir
        return future_data.iloc[-1]['close'], 'EOD'
    
    def _calculate_statistics(self, initial_capital: float, final_capital: float) -> dict:
        """Calcular estadísticas del backtest"""
        if not self.trades:
            return {"error": "No se ejecutaron trades"}
        
        trades_df = pd.DataFrame(self.trades)
        
        # Estadísticas básicas
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # P&L estadísticas
        total_pnl = trades_df['pnl'].sum()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        best_trade = trades_df['pnl'].max()
        worst_trade = trades_df['pnl'].min()
        
        # Risk/Reward ratio
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Drawdown
        trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
        trades_df['peak'] = trades_df['cumulative_pnl'].cummax()
        trades_df['drawdown'] = trades_df['cumulative_pnl'] - trades_df['peak']
        max_drawdown = trades_df['drawdown'].min()
        max_drawdown_pct = max_drawdown / initial_capital if initial_capital > 0 else 0
        
        # Retorno total
        total_return = (final_capital - initial_capital) / initial_capital
        
        # Distribución de salidas
        exit_reasons = trades_df['exit_reason'].value_counts().to_dict()
        
        # Sharpe ratio (aproximado)
        if len(trades_df) > 1:
            daily_returns = trades_df.groupby('date')['return_pct'].sum()
            sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
        else:
            sharpe = 0
        
        return {
            'period': f"{trades_df['date'].min()} to {trades_df['date'].max()}",
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
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'total_return': total_return,
            'final_capital': final_capital,
            'sharpe_ratio': sharpe,
            'exit_reasons': exit_reasons,
            'avg_trade_pnl': total_pnl / total_trades if total_trades > 0 else 0
        }
    
    def print_results(self, stats: dict):
        """Imprimir resultados del backtest"""
        print("\n" + "="*70)
        print("📊 BACKTEST RESULTS - ORB STRATEGY CON DATOS REALES")
        print("="*70)
        print(f"Período: {stats['period']}")
        print(f"Configuración: Max ${self.config.max_position_size} por trade")
        print()
        
        print("🎯 PERFORMANCE:")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1%}")
        print(f"   Avg R/R Ratio: {stats['rr_ratio']:.2f}")
        print(f"   Total Return: {stats['total_return']:.1%}")
        print(f"   Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
        print()
        
        print("💰 P&L ANALYSIS:")
        print(f"   Total P&L: ${stats['total_pnl']:+,.2f}")
        print(f"   Avg Trade: ${stats['avg_trade_pnl']:+.2f}")
        print(f"   Best Trade: ${stats['best_trade']:+.2f}")
        print(f"   Worst Trade: ${stats['worst_trade']:+.2f}")
        print(f"   Avg Winner: ${stats['avg_win']:+.2f}")
        print(f"   Avg Loser: ${stats['avg_loss']:+.2f}")
        print()
        
        print("📉 RISK ANALYSIS:")
        print(f"   Max Drawdown: ${stats['max_drawdown']:+,.2f} ({stats['max_drawdown_pct']:.1%})")
        print(f"   Winning Trades: {stats['winning_trades']}")
        print(f"   Losing Trades: {stats['losing_trades']}")
        print()
        
        print("🚪 EXIT REASONS:")
        for reason, count in stats['exit_reasons'].items():
            pct = count / stats['total_trades'] * 100
            print(f"   {reason}: {count} ({pct:.1f}%)")
        
        print("="*70)
    
    def export_trades(self, filename: str = "backtest_trades.csv"):
        """Exportar trades a CSV"""
        if self.trades:
            df = pd.DataFrame(self.trades)
            df.to_csv(filename, index=False)
            logger.info(f"📄 Trades exportados a {filename}")

def main():
    """Función principal del backtest"""
    print("🚀 ORB BACKTEST CON DATOS REALES")
    
    # Cargar configuración
    config = ORBConfig.load_from_file()
    
    # Crear backtester
    backtester = RealORBBacktester(config)
    
    # Configurar período de prueba (últimos 45 días debido a limitación de Yahoo)
    symbol = config.symbol
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=45)).strftime('%Y-%m-%d')  # 45 días
    
    print(f"📅 Período: {start_date} a {end_date}")
    print(f"📈 Símbolo: {symbol}")
    print(f"💰 Max por posición: ${config.max_position_size}")
    
    # Descargar datos
    data = backtester.download_data(symbol, start_date, end_date)
    
    if data.empty:
        print("❌ No se pudieron obtener datos")
        return
    
    # Ejecutar backtest
    results = backtester.run_backtest(data)
    
    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return
    
    # Mostrar resultados
    backtester.print_results(results)
    
    # Exportar trades
    backtester.export_trades("data/real_backtest_trades.csv")
    
    print("\n✅ Backtest completado!")

if __name__ == "__main__":
    main()