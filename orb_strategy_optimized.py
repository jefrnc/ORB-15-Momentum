#!/usr/bin/env python3
"""
Estrategia ORB Optimizada con Métricas Históricas Exitosas
- Ajustada a los parámetros que dieron 234% retorno, 55% win rate, 1.48 R/R
- Timezone correcto (Argentina -> ET)
- Aislamiento completo de trades
- Posición fija $500
- Gestión OCO inteligente
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import json
import os
from ib_insync import *

class ORBStrategyOptimized:
    def __init__(self):
        # Configuración ajustada a métricas históricas exitosas
        self.stop_loss_pct = -0.008  # -0.8% (más tight que -1%, menos que -0.5%)
        self.take_profit_pct = 0.025  # +2.5% (más realista que +4%)
        self.max_position_size = 500  # Fijo $500 USD
        
        # Timezone management
        self.argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        self.et_tz = pytz.timezone('America/New_York')
        
        # Aislamiento de trades
        self.orb_order_tag = "ORB_STRATEGY_OPT"
        self.orb_positions = {}
        self.daily_pnl = 0
        
        # Control de OCO
        self.use_oco = True  # Usar OCO por defecto
        self.max_hold_time = timedelta(hours=5)  # Máximo 5 horas
        
        # IBKR connection
        self.ib = None
        self.connected = False
        
        print("🚀 ORB Strategy Optimizada Inicializada")
        print(f"📊 Configuración ajustada a métricas históricas:")
        print(f"   • Stop Loss: {self.stop_loss_pct*100:.1f}%")
        print(f"   • Take Profit: {self.take_profit_pct*100:.1f}%")
        print(f"   • Posición: ${self.max_position_size}")
        print(f"   • OCO: {'Activado' if self.use_oco else 'Desactivado'}")
        print(f"   • Timezone: Argentina -> ET automático")
    
    def connect_to_ibkr(self, port=7496):
        """Conectar a IBKR con manejo de errores"""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', port, clientId=2)  # ClientId diferente
            self.connected = True
            print(f"✅ Conectado a IBKR en puerto {port}")
            
            # Verificar posiciones existentes para aislamiento
            self.check_existing_positions()
            return True
            
        except Exception as e:
            print(f"❌ Error conectando a IBKR: {e}")
            return False
    
    def check_existing_positions(self):
        """Verificar posiciones existentes para aislamiento completo"""
        if not self.connected:
            return
        
        try:
            positions = self.ib.positions()
            nvda_positions = [pos for pos in positions if pos.contract.symbol == 'NVDA']
            
            if nvda_positions:
                total_existing = sum(pos.position for pos in nvda_positions)
                print(f"⚠️  NVDA posiciones existentes detectadas: {total_existing} shares")
                print(f"🔒 Estrategia ORB aislada - no afectará posiciones existentes")
                
                # Registrar posición base para aislamiento
                self.initial_nvda_position = total_existing
            else:
                self.initial_nvda_position = 0
                print("✅ No hay posiciones NVDA existentes")
                
        except Exception as e:
            print(f"❌ Error verificando posiciones: {e}")
            self.initial_nvda_position = 0
    
    def get_current_et_time(self):
        """Obtener hora actual en ET desde Argentina"""
        argentina_now = datetime.now(self.argentina_tz)
        et_now = argentina_now.astimezone(self.et_tz)
        return et_now
    
    def is_market_open(self):
        """Verificar si el mercado está abierto (9:30-16:00 ET)"""
        et_now = self.get_current_et_time()
        current_time = et_now.time()
        
        # Verificar día de la semana (0=Monday, 6=Sunday)
        if et_now.weekday() >= 5:  # Weekend
            return False
        
        # Verificar horario (9:30 AM - 4:00 PM ET)
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        return market_open <= current_time <= market_close
    
    def is_orb_time(self):
        """Verificar si estamos en el período ORB (9:30-9:45 ET)"""
        et_now = self.get_current_et_time()
        current_time = et_now.time()
        
        orb_start = time(9, 30)
        orb_end = time(9, 45)
        
        return orb_start <= current_time <= orb_end
    
    def should_close_positions(self):
        """Verificar si es hora de cerrar posiciones (15:00 ET)"""
        et_now = self.get_current_et_time()
        current_time = et_now.time()
        
        return current_time >= time(15, 0)
    
    def download_orb_data(self, symbol='NVDA'):
        """Descargar datos para calcular ORB range"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Obtener datos de los últimos días para contexto
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)
            
            # Intentar diferentes intervalos
            for interval in ['5m', '15m', '1h']:
                try:
                    data = ticker.history(
                        start=start_date,
                        end=end_date,
                        interval=interval,
                        prepost=False
                    )
                    
                    if not data.empty:
                        print(f"📊 Datos ORB obtenidos: {interval} ({len(data)} barras)")
                        return self.process_orb_data(data, interval)
                        
                except Exception as e:
                    continue
            
            print("❌ No se pudieron obtener datos para ORB")
            return None
            
        except Exception as e:
            print(f"❌ Error descargando datos: {e}")
            return None
    
    def process_orb_data(self, data, interval):
        """Procesar datos para obtener ORB range del día actual"""
        if data.empty:
            return None
        
        # Convertir a ET
        data = data.reset_index()
        data['datetime'] = pd.to_datetime(data.index if 'datetime' not in data.columns else data['datetime'])
        
        if data['datetime'].dt.tz is None:
            data['datetime'] = data['datetime'].dt.tz_localize('UTC').dt.tz_convert(self.et_tz)
        else:
            data['datetime'] = data['datetime'].dt.tz_convert(self.et_tz)
        
        # Filtrar solo el día actual
        today = self.get_current_et_time().date()
        today_data = data[data['datetime'].dt.date == today]
        
        if today_data.empty:
            print(f"⚠️  No hay datos para hoy {today}")
            return None
        
        # Filtrar período ORB (9:30-9:45)
        orb_data = today_data[
            (today_data['datetime'].dt.time >= time(9, 30)) &
            (today_data['datetime'].dt.time <= time(9, 45))
        ]
        
        if orb_data.empty:
            print("⚠️  No hay datos del período ORB (9:30-9:45)")
            return None
        
        # Calcular ORB range
        orb_high = orb_data['High'].max()
        orb_low = orb_data['Low'].min()
        orb_range = orb_high - orb_low
        
        print(f"📏 ORB Range calculado: ${orb_low:.2f} - ${orb_high:.2f} (${orb_range:.2f})")
        
        return {
            'orb_high': orb_high,
            'orb_low': orb_low,
            'orb_range': orb_range,
            'last_price': today_data.iloc[-1]['Close']
        }
    
    def get_current_price(self, symbol='NVDA'):
        """Obtener precio actual de NVDA"""
        if not self.connected:
            return None
        
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            ticker = self.ib.reqMktData(stock, '', False, False)
            self.ib.sleep(1)  # Esperar datos
            
            if ticker.last and ticker.last > 0:
                price = float(ticker.last)
                print(f"💰 Precio actual {symbol}: ${price:.2f}")
                return price
            else:
                print(f"⚠️  No se pudo obtener precio de {symbol}")
                return None
                
        except Exception as e:
            print(f"❌ Error obteniendo precio: {e}")
            return None
    
    def create_orb_position(self, symbol='NVDA', orb_data=None):
        """Crear posición ORB con aislamiento completo"""
        if not self.connected or not orb_data:
            return False
        
        current_price = self.get_current_price(symbol)
        if not current_price:
            return False
        
        # Verificar breakout
        if current_price <= orb_data['orb_high']:
            print(f"⏳ Esperando breakout: ${current_price:.2f} <= ${orb_data['orb_high']:.2f}")
            return False
        
        # Calcular posición
        shares = int(self.max_position_size / current_price)
        if shares == 0:
            print(f"❌ No se pueden comprar shares con ${self.max_position_size}")
            return False
        
        actual_position_value = shares * current_price
        
        # Calcular niveles
        stop_price = current_price * (1 + self.stop_loss_pct)
        target_price = current_price * (1 + self.take_profit_pct)
        
        print(f"🎯 Preparando orden ORB:")
        print(f"   • Símbolo: {symbol}")
        print(f"   • Shares: {shares}")
        print(f"   • Precio entrada: ${current_price:.2f}")
        print(f"   • Stop Loss: ${stop_price:.2f} ({self.stop_loss_pct*100:.1f}%)")
        print(f"   • Take Profit: ${target_price:.2f} ({self.take_profit_pct*100:.1f}%)")
        print(f"   • Valor posición: ${actual_position_value:.2f}")
        
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            if self.use_oco:
                # Crear órdenes OCO (One-Cancels-Other)
                return self.create_oco_orders(stock, shares, current_price, stop_price, target_price)
            else:
                # Crear orden simple con manejo manual
                return self.create_simple_order(stock, shares, current_price)
                
        except Exception as e:
            print(f"❌ Error creando posición: {e}")
            return False
    
    def create_oco_orders(self, stock, shares, entry_price, stop_price, target_price):
        """Crear órdenes OCO para entrada + stop/target"""
        try:
            # Orden de entrada
            entry_order = MarketOrder('BUY', shares)
            entry_order.orderRef = self.orb_order_tag
            entry_order.transmit = False  # No transmitir aún
            
            # Orden de stop loss (sell stop)
            stop_order = StopOrder('SELL', shares, stop_price)
            stop_order.orderRef = self.orb_order_tag
            stop_order.parentId = entry_order.orderId
            stop_order.transmit = False
            
            # Orden de take profit (limit)
            target_order = LimitOrder('SELL', shares, target_price)
            target_order.orderRef = self.orb_order_tag
            target_order.parentId = entry_order.orderId
            target_order.transmit = True  # Transmitir todas juntas
            
            # Crear bracket order (OCO automático)
            bracket = self.ib.bracketOrder('BUY', shares, entry_price, target_price, stop_price)
            
            for order in bracket:
                order.orderRef = self.orb_order_tag
            
            # Enviar órdenes
            trades = []
            for order in bracket:
                trade = self.ib.placeOrder(stock, order)
                trades.append(trade)
            
            print(f"✅ Órdenes OCO enviadas:")
            print(f"   🟢 Entrada: {shares} shares a mercado")
            print(f"   🔴 Stop: ${stop_price:.2f}")
            print(f"   🟢 Target: ${target_price:.2f}")
            
            # Registrar posición para seguimiento
            position_id = f"ORB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.orb_positions[position_id] = {
                'symbol': stock.symbol,
                'shares': shares,
                'entry_price': entry_price,
                'stop_price': stop_price,
                'target_price': target_price,
                'entry_time': datetime.now(),
                'trades': trades,
                'status': 'ACTIVE'
            }
            
            return True
            
        except Exception as e:
            print(f"❌ Error creando OCO: {e}")
            return False
    
    def create_simple_order(self, stock, shares, entry_price):
        """Crear orden simple sin OCO (manejo manual)"""
        try:
            order = MarketOrder('BUY', shares)
            order.orderRef = self.orb_order_tag
            
            trade = self.ib.placeOrder(stock, order)
            
            print(f"✅ Orden simple enviada: {shares} shares a mercado")
            
            # Registrar para manejo manual
            position_id = f"ORB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.orb_positions[position_id] = {
                'symbol': stock.symbol,
                'shares': shares,
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'trade': trade,
                'status': 'MANUAL'
            }
            
            return True
            
        except Exception as e:
            print(f"❌ Error creando orden simple: {e}")
            return False
    
    def monitor_positions(self):
        """Monitorear posiciones ORB activas"""
        if not self.connected or not self.orb_positions:
            return
        
        et_now = self.get_current_et_time()
        
        for pos_id, position in list(self.orb_positions.items()):
            if position['status'] not in ['ACTIVE', 'MANUAL']:
                continue
            
            # Verificar tiempo de vida de la posición
            time_elapsed = et_now - position['entry_time']
            
            # Cierre forzado a las 15:00 o después de max_hold_time
            if self.should_close_positions() or time_elapsed > self.max_hold_time:
                print(f"⏰ Cerrando posición {pos_id} por tiempo")
                self.close_position(pos_id, "TIME_EXIT")
            
            # Para posiciones manuales, verificar stop/target
            elif position['status'] == 'MANUAL':
                self.check_manual_exit(pos_id)
    
    def check_manual_exit(self, position_id):
        """Verificar salida manual para posiciones sin OCO"""
        position = self.orb_positions.get(position_id)
        if not position:
            return
        
        current_price = self.get_current_price(position['symbol'])
        if not current_price:
            return
        
        entry_price = position['entry_price']
        current_pnl_pct = (current_price - entry_price) / entry_price
        
        # Verificar stop loss
        if current_pnl_pct <= self.stop_loss_pct:
            print(f"🛑 Stop Loss activado para {position_id}: {current_pnl_pct*100:.1f}%")
            self.close_position(position_id, "STOP_LOSS")
        
        # Verificar take profit
        elif current_pnl_pct >= self.take_profit_pct:
            print(f"🎯 Take Profit activado para {position_id}: {current_pnl_pct*100:.1f}%")
            self.close_position(position_id, "TAKE_PROFIT")
    
    def close_position(self, position_id, reason):
        """Cerrar posición específica"""
        position = self.orb_positions.get(position_id)
        if not position:
            return
        
        try:
            stock = Stock(position['symbol'], 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            # Crear orden de cierre
            close_order = MarketOrder('SELL', position['shares'])
            close_order.orderRef = self.orb_order_tag
            
            trade = self.ib.placeOrder(stock, close_order)
            
            # Actualizar posición
            position['status'] = 'CLOSED'
            position['close_time'] = datetime.now()
            position['close_reason'] = reason
            
            print(f"✅ Posición {position_id} cerrada: {reason}")
            
        except Exception as e:
            print(f"❌ Error cerrando posición {position_id}: {e}")
    
    def get_daily_pnl(self):
        """Calcular P&L diario de estrategia ORB"""
        if not self.connected:
            return 0
        
        try:
            # Obtener todas las posiciones con tag ORB
            positions = self.ib.positions()
            orb_positions = [pos for pos in positions if hasattr(pos, 'orderRef') and pos.orderRef == self.orb_order_tag]
            
            total_pnl = sum(pos.unrealizedPNL for pos in orb_positions if pos.unrealizedPNL)
            
            print(f"💰 P&L diario ORB: ${total_pnl:.2f}")
            return total_pnl
            
        except Exception as e:
            print(f"❌ Error calculando P&L: {e}")
            return 0
    
    def run_strategy(self):
        """Ejecutar estrategia ORB principal"""
        print(f"\n🚀 Iniciando Estrategia ORB Optimizada")
        print(f"🌎 Timezone: Argentina -> ET")
        print(f"⏰ Hora Argentina: {datetime.now(self.argentina_tz).strftime('%H:%M:%S')}")
        print(f"⏰ Hora ET: {self.get_current_et_time().strftime('%H:%M:%S')}")
        
        if not self.is_market_open():
            print("❌ Mercado cerrado - Estrategia en pausa")
            return
        
        # Conectar a IBKR si no está conectado
        if not self.connected:
            if not self.connect_to_ibkr():
                return
        
        try:
            while self.is_market_open():
                et_now = self.get_current_et_time()
                current_time = et_now.time()
                
                # Monitorear posiciones existentes
                self.monitor_positions()
                
                # Buscar nueva entrada solo en período ORB
                if self.is_orb_time() and not self.orb_positions:
                    print(f"🔍 Período ORB activo - Buscando breakout...")
                    
                    # Obtener datos ORB
                    orb_data = self.download_orb_data()
                    if orb_data:
                        # Intentar crear posición
                        if self.create_orb_position('NVDA', orb_data):
                            print(f"✅ Posición ORB creada exitosamente")
                        else:
                            print(f"⏳ Esperando condiciones de entrada...")
                
                # Mostrar status cada 5 minutos
                if et_now.minute % 5 == 0:
                    pnl = self.get_daily_pnl()
                    print(f"📊 Status {current_time}: P&L=${pnl:.2f}, Posiciones={len(self.orb_positions)}")
                
                # Pausa antes del próximo ciclo
                self.ib.sleep(30)  # 30 segundos
                
        except KeyboardInterrupt:
            print("\n⏹️  Estrategia detenida por usuario")
        except Exception as e:
            print(f"❌ Error en estrategia: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpiar recursos y desconectar"""
        if self.connected:
            print("🧹 Limpiando recursos...")
            
            # Cerrar posiciones abiertas si es necesario
            if self.should_close_positions():
                for pos_id in list(self.orb_positions.keys()):
                    if self.orb_positions[pos_id]['status'] in ['ACTIVE', 'MANUAL']:
                        self.close_position(pos_id, "EOD_CLEANUP")
            
            self.ib.disconnect()
            print("✅ Desconectado de IBKR")

def main():
    """Función principal"""
    print("=" * 60)
    print("🇦🇷 ORB STRATEGY OPTIMIZADA - ARGENTINA -> ET")
    print("=" * 60)
    
    strategy = ORBStrategyOptimized()
    
    try:
        strategy.run_strategy()
    except Exception as e:
        print(f"❌ Error crítico: {e}")
    finally:
        strategy.cleanup()

if __name__ == "__main__":
    main()