#!/usr/bin/env python3
"""
Estrategia ORB Final - OCO + Cierre por Horario
- OCO maneja stop loss y take profit automáticamente  
- A las 15:00 ET verifica si posición sigue abierta y la cierra
- Aislamiento total de otras posiciones
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import json
import os
from ib_insync import *

class ORBStrategyFinal:
    def __init__(self):
        # Parámetros ajustados a métricas históricas exitosas
        self.stop_loss_pct = -0.008  # -0.8%
        self.take_profit_pct = 0.025  # +2.5%
        self.max_position_size = 500  # $500 USD
        
        # Timezone management
        self.argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        self.et_tz = pytz.timezone('America/New_York')
        
        # Aislamiento y control
        self.orb_order_tag = "ORB_FINAL"
        self.initial_nvda_position = 0
        self.orb_position_active = False
        self.orb_entry_time = None
        self.orb_shares = 0
        self.orb_entry_price = 0
        
        # IBKR
        self.ib = None
        self.connected = False
        
        print("🎯 ORB Strategy Final - Simple y Efectiva")
        print(f"📊 Parámetros históricos exitosos:")
        print(f"   • Stop Loss: {self.stop_loss_pct*100:.1f}%")
        print(f"   • Take Profit: {self.take_profit_pct*100:.1f}%")
        print(f"   • Posición: ${self.max_position_size}")
        print(f"   • OCO: Maneja precio automático")
        print(f"   • 15:00 ET: Cierre manual si sigue abierta")
    
    def connect_to_ibkr(self, port=7496):  # 7496 puerto real en TWS
        """Conectar a IBKR"""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', port, clientId=4)
            self.connected = True
            
            # Detectar posiciones NVDA existentes para aislamiento
            positions = self.ib.positions()
            nvda_positions = [pos for pos in positions if pos.contract.symbol == 'NVDA']
            
            if nvda_positions:
                self.initial_nvda_position = sum(pos.position for pos in nvda_positions)
                print(f"⚠️  NVDA existentes: {self.initial_nvda_position} shares (aisladas)")
            else:
                self.initial_nvda_position = 0
                print("✅ No hay posiciones NVDA existentes")
            
            print(f"✅ Conectado a IBKR puerto {port}")
            return True
            
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return False
    
    def get_et_time(self):
        """Obtener hora ET desde Argentina"""
        argentina_now = datetime.now(self.argentina_tz)
        return argentina_now.astimezone(self.et_tz)
    
    def is_market_open(self):
        """Verificar horario de mercado (9:30-16:00 ET)"""
        et_now = self.get_et_time()
        if et_now.weekday() >= 5:  # Weekend
            return False
        
        current_time = et_now.time()
        return time(9, 30) <= current_time <= time(16, 0)
    
    def is_orb_period(self):
        """Verificar período ORB (9:30-9:45 ET)"""
        current_time = self.get_et_time().time()
        return time(9, 30) <= current_time <= time(9, 45)
    
    def is_force_close_time(self):
        """Verificar si es hora de cierre forzado (15:00 ET)"""
        current_time = self.get_et_time().time()
        return current_time >= time(15, 0)
    
    def get_current_price(self, symbol='NVDA'):
        """Obtener precio actual de NVDA"""
        try:
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            ticker = self.ib.reqMktData(stock, '', False, False)
            self.ib.sleep(1)
            
            if ticker.last and ticker.last > 0:
                return float(ticker.last)
            return None
                
        except Exception as e:
            print(f"❌ Error precio: {e}")
            return None
    
    def calculate_orb_range(self):
        """Calcular ORB range del día usando datos reales"""
        try:
            ticker = yf.Ticker('NVDA')
            
            # Obtener datos de 5 min recientes
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)
            
            data = ticker.history(start=start_date, end=end_date, interval="5m", prepost=False)
            
            if data.empty:
                return None
            
            # Convertir a ET
            data = data.reset_index()
            data['datetime'] = pd.to_datetime(data['Datetime'])
            
            if data['datetime'].dt.tz is None:
                data['datetime'] = data['datetime'].dt.tz_localize('UTC').dt.tz_convert(self.et_tz)
            else:
                data['datetime'] = data['datetime'].dt.tz_convert(self.et_tz)
            
            # Filtrar solo hoy
            today = self.get_et_time().date()
            today_data = data[data['datetime'].dt.date == today]
            
            if today_data.empty:
                print("⚠️  No hay datos de hoy para ORB")
                return None
            
            # ORB: 9:30-9:45 ET
            orb_data = today_data[
                (today_data['datetime'].dt.time >= time(9, 30)) &
                (today_data['datetime'].dt.time <= time(9, 45))
            ]
            
            if orb_data.empty:
                print("⚠️  No hay datos del período ORB")
                return None
            
            orb_high = orb_data['High'].max()
            orb_low = orb_data['Low'].min()
            
            print(f"📏 ORB calculado: ${orb_low:.2f} - ${orb_high:.2f}")
            return {'high': orb_high, 'low': orb_low}
            
        except Exception as e:
            print(f"❌ Error calculando ORB: {e}")
            return None
    
    def create_orb_position(self, orb_range):
        """
        Crear posición ORB con OCO:
        1. Verificar breakout
        2. Crear OCO (entrada + stop + target)
        3. Marcar posición como activa
        """
        if not self.connected or self.orb_position_active:
            return False
        
        current_price = self.get_current_price()
        if not current_price:
            return False
        
        # Verificar breakout del ORB high
        if current_price <= orb_range['high']:
            print(f"⏳ Esperando breakout: ${current_price:.2f} <= ${orb_range['high']:.2f}")
            return False
        
        # Calcular posición
        shares = int(self.max_position_size / current_price)
        if shares == 0:
            print(f"❌ No se pueden comprar shares con ${self.max_position_size}")
            return False
        
        # Calcular niveles
        stop_price = current_price * (1 + self.stop_loss_pct)
        target_price = current_price * (1 + self.take_profit_pct)
        
        print(f"\n🚀 BREAKOUT DETECTADO - Creando OCO:")
        print(f"   💰 Precio actual: ${current_price:.2f}")
        print(f"   📈 ORB High: ${orb_range['high']:.2f}")
        print(f"   🎯 Shares: {shares} (${shares * current_price:.2f})")
        print(f"   🔴 Stop: ${stop_price:.2f} ({self.stop_loss_pct*100:.1f}%)")
        print(f"   🟢 Target: ${target_price:.2f} ({self.take_profit_pct*100:.1f}%)")
        
        try:
            stock = Stock('NVDA', 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            # Crear bracket order (OCO automático)
            bracket = self.ib.bracketOrder(
                'BUY',           # Acción
                shares,          # Cantidad
                current_price,   # Precio entrada (market)
                target_price,    # Take profit
                stop_price       # Stop loss
            )
            
            # Agregar tag para aislamiento
            for order in bracket:
                order.orderRef = self.orb_order_tag
            
            # Enviar órdenes
            trades = []
            for order in bracket:
                trade = self.ib.placeOrder(stock, order)
                trades.append(trade)
                self.ib.sleep(0.1)
            
            # Marcar posición como activa
            self.orb_position_active = True
            self.orb_entry_time = datetime.now()
            self.orb_shares = shares
            self.orb_entry_price = current_price
            
            print(f"✅ OCO enviada exitosamente:")
            print(f"   🟢 BUY {shares} NVDA")
            print(f"   🔴 STOP ${stop_price:.2f}")
            print(f"   🟢 LIMIT ${target_price:.2f}")
            print(f"   🏷️  Tag: {self.orb_order_tag}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creando OCO: {e}")
            return False
    
    def check_position_status(self):
        """
        Verificar estado de la posición ORB:
        1. Si OCO se ejecutó (stop o target) → marcar como cerrada
        2. Si sigue abierta y es 15:00 → cerrar manual
        """
        if not self.orb_position_active:
            return
        
        try:
            # Verificar posiciones actuales
            positions = self.ib.positions()
            current_nvda_position = 0
            
            for pos in positions:
                if pos.contract.symbol == 'NVDA':
                    current_nvda_position += pos.position
            
            # Calcular posición ORB actual
            orb_position_size = current_nvda_position - self.initial_nvda_position
            
            # ¿La OCO ya se ejecutó completamente?
            if orb_position_size == 0:
                print(f"✅ Posición ORB cerrada por OCO (stop o target)")
                self.orb_position_active = False
                
                # Calcular P&L final
                self.calculate_final_pnl()
                return
            
            # ¿Es hora de cierre forzado? (15:00 ET)
            if self.is_force_close_time():
                print(f"⏰ 15:00 ET - Cerrando posición ORB manualmente")
                self.force_close_position()
                
        except Exception as e:
            print(f"❌ Error verificando posición: {e}")
    
    def force_close_position(self):
        """Cerrar posición ORB manualmente a las 15:00"""
        try:
            # Verificar posición actual
            positions = self.ib.positions()
            nvda_position = None
            
            for pos in positions:
                if pos.contract.symbol == 'NVDA':
                    nvda_position = pos
                    break
            
            if not nvda_position:
                print("⚠️  No se encontró posición NVDA para cerrar")
                return
            
            # Calcular shares a cerrar (solo los de ORB)
            orb_shares_open = nvda_position.position - self.initial_nvda_position
            
            if orb_shares_open <= 0:
                print("✅ No hay posición ORB abierta")
                self.orb_position_active = False
                return
            
            # Crear orden de cierre
            stock = Stock('NVDA', 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            close_order = MarketOrder('SELL', orb_shares_open)
            close_order.orderRef = self.orb_order_tag
            
            # Enviar orden
            close_trade = self.ib.placeOrder(stock, close_order)
            
            print(f"📤 Orden de cierre enviada:")
            print(f"   📉 SELL {orb_shares_open} shares a mercado")
            print(f"   ⏰ Razón: Cierre forzado 15:00 ET")
            
            # Marcar como cerrada
            self.orb_position_active = False
            
            # Calcular P&L estimado
            current_price = self.get_current_price()
            if current_price:
                estimated_pnl = (current_price - self.orb_entry_price) * orb_shares_open
                return_pct = (current_price - self.orb_entry_price) / self.orb_entry_price * 100
                
                print(f"💰 P&L estimado: ${estimated_pnl:+.2f} ({return_pct:+.1f}%)")
            
        except Exception as e:
            print(f"❌ Error cerrando posición: {e}")
    
    def calculate_final_pnl(self):
        """Calcular P&L final cuando la posición se cierra"""
        try:
            # Buscar trades ejecutados con nuestro tag
            trades = self.ib.fills()
            orb_trades = [t for t in trades if t.execution.orderRef == self.orb_order_tag]
            
            if len(orb_trades) >= 2:  # Entrada + salida
                # Calcular P&L real
                total_pnl = sum(t.commissionReport.realizedPNL for t in orb_trades 
                               if t.commissionReport.realizedPNL)
                
                print(f"💰 P&L final ORB: ${total_pnl:+.2f}")
            
        except Exception as e:
            print(f"⚠️  Error calculando P&L: {e}")
    
    def get_current_pnl(self):
        """Obtener P&L no realizado actual"""
        if not self.orb_position_active:
            return 0
        
        try:
            current_price = self.get_current_price()
            if current_price:
                unrealized_pnl = (current_price - self.orb_entry_price) * self.orb_shares
                return unrealized_pnl
            return 0
        except:
            return 0
    
    def run_strategy(self):
        """Ejecutar estrategia ORB final"""
        print(f"\n🚀 Iniciando ORB Strategy Final")
        print(f"🇦🇷 Hora Argentina: {datetime.now(self.argentina_tz).strftime('%H:%M:%S')}")
        print(f"🇺🇸 Hora ET: {self.get_et_time().strftime('%H:%M:%S')}")
        
        if not self.is_market_open():
            print("❌ Mercado cerrado - esperando apertura")
            return
        
        if not self.connected:
            if not self.connect_to_ibkr():
                return
        
        orb_range = None
        last_status_time = datetime.now()
        
        try:
            while self.is_market_open():
                et_now = self.get_et_time()
                current_time = et_now.time()
                
                # 1. Calcular ORB range si estamos en período ORB
                if self.is_orb_period() and not orb_range:
                    orb_range = self.calculate_orb_range()
                    if orb_range:
                        print(f"✅ ORB Range listo para breakout")
                
                # 2. Buscar entrada si tenemos ORB y no hay posición activa
                if (orb_range and 
                    not self.orb_position_active and 
                    current_time < time(15, 0)):  # No entrar después de 15:00
                    
                    self.create_orb_position(orb_range)
                
                # 3. Verificar estado de posición existente
                self.check_position_status()
                
                # 4. Status cada 2 minutos
                if (datetime.now() - last_status_time).seconds >= 120:
                    pnl = self.get_current_pnl()
                    status = "ACTIVA" if self.orb_position_active else "INACTIVA"
                    
                    print(f"📊 {current_time.strftime('%H:%M')} | ORB: {status} | P&L: ${pnl:+.2f}")
                    last_status_time = datetime.now()
                
                # 5. Pausa
                self.ib.sleep(15)  # 15 segundos
                
        except KeyboardInterrupt:
            print("\n⏹️  Estrategia detenida por usuario")
        except Exception as e:
            print(f"❌ Error en estrategia: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpiar al final"""
        print("\n🧹 Finalizando estrategia...")
        
        if self.orb_position_active and self.connected:
            print("⚠️  Cerrando posición ORB abierta...")
            self.force_close_position()
        
        if self.connected:
            self.ib.disconnect()
            print("✅ Desconectado de IBKR")

def main():
    """Función principal"""
    print("=" * 60)
    print("🎯 ORB STRATEGY FINAL - OCO + CIERRE HORARIO")
    print("=" * 60)
    print("💡 OCO maneja precio, 15:00 maneja tiempo")
    print("🔒 Aislamiento total de otras posiciones")
    
    # Verificar horario actual
    from datetime import datetime
    import pytz
    arg_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    et_tz = pytz.timezone('America/New_York')
    
    arg_now = datetime.now(arg_tz)
    et_now = arg_now.astimezone(et_tz)
    
    print(f"\n⏰ HORARIOS ACTUALES:")
    print(f"   🇦🇷 Argentina: {arg_now.strftime('%H:%M:%S')}")
    print(f"   🇺🇸 ET (NYSE): {et_now.strftime('%H:%M:%S')}")
    print(f"   📈 Mercado: {'ABIERTO' if 9.5 <= et_now.hour + et_now.minute/60 < 16 else 'CERRADO'}")
    
    strategy = ORBStrategyFinal()
    
    try:
        strategy.run_strategy()
    except Exception as e:
        print(f"❌ Error crítico: {e}")
    finally:
        strategy.cleanup()

if __name__ == "__main__":
    main()