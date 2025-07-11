#!/usr/bin/env python3
"""
Estrategia ORB Corregida - Manejo Híbrido OCO + Tiempo
- OCO para stop loss y take profit automático
- Cancelación manual + cierre a las 15:00 ET
- Aislamiento completo de trades
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import json
import os
from ib_insync import *

class ORBStrategyHybrid:
    def __init__(self):
        # Configuración ajustada a métricas históricas exitosas
        self.stop_loss_pct = -0.008  # -0.8%
        self.take_profit_pct = 0.025  # +2.5%
        self.max_position_size = 500  # Fijo $500 USD
        
        # Timezone management
        self.argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        self.et_tz = pytz.timezone('America/New_York')
        
        # Aislamiento de trades
        self.orb_order_tag = "ORB_HYBRID"
        self.orb_positions = {}
        
        # OCO + Time management
        self.use_oco = True
        self.force_close_time = time(15, 0)  # 15:00 ET
        self.active_oco_orders = {}
        
        # IBKR connection
        self.ib = None
        self.connected = False
        
        print("🔄 ORB Strategy Híbrida (OCO + Tiempo)")
        print(f"📊 Configuración:")
        print(f"   • Stop Loss: {self.stop_loss_pct*100:.1f}%")
        print(f"   • Take Profit: {self.take_profit_pct*100:.1f}%") 
        print(f"   • OCO: Sí (solo para precio)")
        print(f"   • Cierre forzado: {self.force_close_time} ET (manual)")
        print(f"   • Posición: ${self.max_position_size}")
    
    def connect_to_ibkr(self, port=7496):
        """Conectar a IBKR con manejo de errores"""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', port, clientId=3)
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
                print(f"⚠️  NVDA posiciones existentes: {total_existing} shares")
                print(f"🔒 ORB aislada - no afectará otras posiciones")
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
        """Verificar si el mercado está abierto"""
        et_now = self.get_current_et_time()
        current_time = et_now.time()
        
        if et_now.weekday() >= 5:  # Weekend
            return False
        
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        return market_open <= current_time <= market_close
    
    def is_orb_time(self):
        """Verificar si estamos en período ORB (9:30-9:45)"""
        et_now = self.get_current_et_time()
        current_time = et_now.time()
        
        orb_start = time(9, 30)
        orb_end = time(9, 45)
        
        return orb_start <= current_time <= orb_end
    
    def should_force_close(self):
        """Verificar si es hora de cerrar posiciones (15:00 ET)"""
        et_now = self.get_current_et_time()
        current_time = et_now.time()
        
        return current_time >= self.force_close_time
    
    def get_current_price(self, symbol='NVDA'):
        """Obtener precio actual"""
        if not self.connected:
            return None
        
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            ticker = self.ib.reqMktData(stock, '', False, False)
            self.ib.sleep(1)
            
            if ticker.last and ticker.last > 0:
                price = float(ticker.last)
                return price
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error obteniendo precio: {e}")
            return None
    
    def download_orb_data(self, symbol='NVDA'):
        """Descargar datos para calcular ORB range"""
        try:
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)
            
            # Intentar diferentes intervalos
            for interval in ['5m', '15m']:
                try:
                    data = ticker.history(
                        start=start_date,
                        end=end_date,
                        interval=interval,
                        prepost=False
                    )
                    
                    if not data.empty:
                        return self.process_orb_data(data, interval)
                        
                except Exception as e:
                    continue
            
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
            return None
        
        # Filtrar período ORB (9:30-9:45)
        orb_data = today_data[
            (today_data['datetime'].dt.time >= time(9, 30)) &
            (today_data['datetime'].dt.time <= time(9, 45))
        ]
        
        if orb_data.empty:
            return None
        
        # Calcular ORB range
        orb_high = orb_data['High'].max()
        orb_low = orb_data['Low'].min()
        orb_range = orb_high - orb_low
        
        print(f"📏 ORB: ${orb_low:.2f} - ${orb_high:.2f} (rango: ${orb_range:.2f})")
        
        return {
            'orb_high': orb_high,
            'orb_low': orb_low,
            'orb_range': orb_range,
            'last_price': today_data.iloc[-1]['Close']
        }
    
    def create_oco_position(self, symbol='NVDA', orb_data=None):
        """
        Crear posición con OCO HÍBRIDA:
        1. OCO para stop loss y take profit (precio)
        2. Cancelación manual a las 15:00 (tiempo)
        """
        if not self.connected or not orb_data:
            return False
        
        current_price = self.get_current_price(symbol)
        if not current_price:
            return False
        
        # Verificar breakout
        if current_price <= orb_data['orb_high']:
            return False
        
        # Calcular posición
        shares = int(self.max_position_size / current_price)
        if shares == 0:
            return False
        
        # Calcular niveles
        stop_price = current_price * (1 + self.stop_loss_pct)
        target_price = current_price * (1 + self.take_profit_pct)
        
        print(f"\n🎯 Creando posición ORB híbrida:")
        print(f"   📊 Breakout: ${current_price:.2f} > ${orb_data['orb_high']:.2f}")
        print(f"   💰 Shares: {shares} (${shares * current_price:.2f})")
        print(f"   🔴 Stop: ${stop_price:.2f} ({self.stop_loss_pct*100:.1f}%)")
        print(f"   🟢 Target: ${target_price:.2f} ({self.take_profit_pct*100:.1f}%)")
        print(f"   ⏰ Cierre forzado: {self.force_close_time}")
        
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            # PASO 1: Crear bracket order (OCO automático)
            bracket_orders = self.ib.bracketOrder(
                'BUY', 
                shares, 
                current_price,    # Entrada a mercado
                target_price,     # Take profit
                stop_price        # Stop loss
            )
            
            # Agregar tags para aislamiento
            for order in bracket_orders:
                order.orderRef = self.orb_order_tag
            
            # PASO 2: Enviar órdenes
            trades = []
            for order in bracket_orders:
                trade = self.ib.placeOrder(stock, order)
                trades.append(trade)
                self.ib.sleep(0.1)  # Pequeña pausa entre órdenes
            
            print(f"✅ OCO enviada - 3 órdenes:")
            print(f"   🟢 BUY {shares} shares (entrada)")
            print(f"   🔴 STOP ${stop_price:.2f}")
            print(f"   🟢 LIMIT ${target_price:.2f}")
            
            # PASO 3: Registrar para manejo de tiempo
            position_id = f"ORB_{datetime.now().strftime('%H%M%S')}"
            self.orb_positions[position_id] = {
                'symbol': symbol,
                'shares': shares,
                'entry_price': current_price,
                'stop_price': stop_price,
                'target_price': target_price,
                'entry_time': datetime.now(),
                'bracket_trades': trades,
                'status': 'OCO_ACTIVE'
            }
            
            # Registrar órdenes OCO para cancelación posterior
            self.active_oco_orders[position_id] = {
                'orders': [trade.order for trade in trades],
                'entry_filled': False
            }
            
            return True
            
        except Exception as e:
            print(f"❌ Error creando OCO híbrida: {e}")
            return False
    
    def monitor_oco_positions(self):
        """
        Monitorear posiciones OCO:
        1. Verificar si entrada se ejecutó
        2. Cancelar OCO + cerrar manual a las 15:00
        """
        if not self.connected:
            return
        
        et_now = self.get_current_et_time()
        current_time = et_now.time()
        
        for pos_id, position in list(self.orb_positions.items()):
            if position['status'] != 'OCO_ACTIVE':
                continue
            
            # Verificar si entrada se ejecutó
            self.check_entry_execution(pos_id)
            
            # CIERRE FORZADO a las 15:00
            if current_time >= self.force_close_time:
                print(f"⏰ 15:00 ET - Cancelando OCO y cerrando {pos_id}")
                self.force_close_oco_position(pos_id)
    
    def check_entry_execution(self, position_id):
        """Verificar si la orden de entrada se ejecutó"""
        if position_id not in self.active_oco_orders:
            return
        
        oco_info = self.active_oco_orders[position_id]
        
        if oco_info['entry_filled']:
            return
        
        # Verificar trades
        position = self.orb_positions[position_id]
        for trade in position['bracket_trades']:
            if trade.orderStatus.status == 'Filled' and trade.order.action == 'BUY':
                print(f"✅ Entrada ejecutada para {position_id}")
                oco_info['entry_filled'] = True
                position['actual_entry_price'] = trade.orderStatus.avgFillPrice
                break
    
    def force_close_oco_position(self, position_id):
        """
        Cerrar posición OCO por tiempo:
        1. Cancelar órdenes OCO pendientes
        2. Cerrar posición a mercado
        """
        if position_id not in self.orb_positions:
            return
        
        position = self.orb_positions[position_id]
        
        try:
            # PASO 1: Cancelar todas las órdenes OCO pendientes
            if position_id in self.active_oco_orders:
                oco_info = self.active_oco_orders[position_id]
                
                for order in oco_info['orders']:
                    try:
                        self.ib.cancelOrder(order)
                        print(f"🚫 Cancelada orden OCO: {order.action} {order.orderType}")
                    except Exception as e:
                        print(f"⚠️  Error cancelando orden: {e}")
                
                del self.active_oco_orders[position_id]
            
            # PASO 2: Verificar si tenemos posición abierta
            current_positions = self.ib.positions()
            nvda_position = None
            
            for pos in current_positions:
                if (pos.contract.symbol == 'NVDA' and 
                    pos.position > self.initial_nvda_position):
                    nvda_position = pos
                    break
            
            # PASO 3: Cerrar posición si existe
            if nvda_position and nvda_position.position > 0:
                shares_to_close = nvda_position.position - self.initial_nvda_position
                
                if shares_to_close > 0:
                    stock = Stock('NVDA', 'SMART', 'USD')
                    self.ib.qualifyContracts(stock)
                    
                    close_order = MarketOrder('SELL', shares_to_close)
                    close_order.orderRef = self.orb_order_tag
                    
                    close_trade = self.ib.placeOrder(stock, close_order)
                    
                    print(f"📤 Orden de cierre enviada: SELL {shares_to_close} shares")
                    
                    # Calcular P&L estimado
                    current_price = self.get_current_price('NVDA')
                    if current_price:
                        entry_price = position.get('actual_entry_price', position['entry_price'])
                        estimated_pnl = (current_price - entry_price) * shares_to_close
                        print(f"💰 P&L estimado: ${estimated_pnl:+.2f}")
            
            # PASO 4: Actualizar status
            position['status'] = 'CLOSED_BY_TIME'
            position['close_time'] = datetime.now()
            position['close_reason'] = 'FORCE_CLOSE_15:00'
            
            print(f"✅ Posición {position_id} cerrada por tiempo")
            
        except Exception as e:
            print(f"❌ Error cerrando posición OCO: {e}")
    
    def get_daily_pnl(self):
        """Calcular P&L diario ORB"""
        if not self.connected:
            return 0
        
        try:
            positions = self.ib.positions()
            total_pnl = 0
            
            for pos in positions:
                if (hasattr(pos.contract, 'symbol') and 
                    pos.contract.symbol == 'NVDA' and
                    pos.position > self.initial_nvda_position):
                    total_pnl += pos.unrealizedPNL if pos.unrealizedPNL else 0
            
            return total_pnl
            
        except Exception as e:
            return 0
    
    def run_strategy(self):
        """Ejecutar estrategia ORB híbrida"""
        print(f"\n🚀 Estrategia ORB Híbrida - OCO + Tiempo")
        print(f"🇦🇷 Argentina: {datetime.now(self.argentina_tz).strftime('%H:%M:%S')}")
        print(f"🇺🇸 ET: {self.get_current_et_time().strftime('%H:%M:%S')}")
        
        if not self.is_market_open():
            print("❌ Mercado cerrado")
            return
        
        if not self.connected:
            if not self.connect_to_ibkr():
                return
        
        try:
            while self.is_market_open():
                et_now = self.get_current_et_time()
                current_time = et_now.time()
                
                # 1. Monitorear posiciones OCO existentes
                self.monitor_oco_positions()
                
                # 2. Buscar nueva entrada en período ORB
                if (self.is_orb_time() and 
                    not self.orb_positions and 
                    current_time < self.force_close_time):
                    
                    print(f"🔍 ORB activo - Buscando breakout...")
                    
                    orb_data = self.download_orb_data()
                    if orb_data:
                        current_price = self.get_current_price()
                        if current_price and current_price > orb_data['orb_high']:
                            if self.create_oco_position('NVDA', orb_data):
                                print(f"✅ Posición OCO híbrida creada")
                
                # 3. Status cada 2 minutos
                if et_now.minute % 2 == 0 and et_now.second < 30:
                    pnl = self.get_daily_pnl()
                    positions_count = len([p for p in self.orb_positions.values() 
                                         if p['status'] == 'OCO_ACTIVE'])
                    print(f"📊 {current_time.strftime('%H:%M')} | P&L: ${pnl:+.2f} | OCO activas: {positions_count}")
                
                # 4. Pausa
                self.ib.sleep(20)  # 20 segundos
                
        except KeyboardInterrupt:
            print("\n⏹️  Estrategia detenida")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpiar recursos"""
        if self.connected:
            print("\n🧹 Limpiando...")
            
            # Cerrar posiciones OCO abiertas
            for pos_id in list(self.orb_positions.keys()):
                if self.orb_positions[pos_id]['status'] == 'OCO_ACTIVE':
                    self.force_close_oco_position(pos_id)
            
            self.ib.disconnect()
            print("✅ Desconectado")

def main():
    """Función principal"""
    print("=" * 60)
    print("🔄 ORB STRATEGY HÍBRIDA - OCO + TIEMPO")
    print("=" * 60)
    print("💡 OCO maneja precio, manual maneja tiempo")
    
    strategy = ORBStrategyHybrid()
    
    try:
        strategy.run_strategy()
    except Exception as e:
        print(f"❌ Error crítico: {e}")
    finally:
        strategy.cleanup()

if __name__ == "__main__":
    main()