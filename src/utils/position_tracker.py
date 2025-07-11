"""
Sistema de tracking en tiempo real de posiciones activas
"""
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class ActivePosition:
    symbol: str
    shares: int
    entry_price: float
    avg_cost: float  # Precio promedio con comisiones incluidas
    stop_price: float
    target_price: float
    entry_time: datetime
    stop_order_id: Optional[int] = None
    target_order_id: Optional[int] = None
    current_price: float = 0.0
    last_update: datetime = None
    pnl_unrealized: float = 0.0
    pnl_percent: float = 0.0
    status: str = "active"  # active, near_stop, near_target, stopped, target_hit
    system_tag: str = "IBKR_AUTO"
    has_real_data: bool = False  # ¿Tenemos datos de mercado reales?
    last_data_update: datetime = None
    data_quality: str = "unknown"  # "real", "delayed", "stale", "none"
    grace_period_minutes: int = 5  # Período de gracia después de entrada (minutos)
    
    def __post_init__(self):
        if self.last_update is None:
            self.last_update = datetime.now()
    
    def update_price(self, new_price: float, data_quality: str = "unknown"):
        """Actualizar precio actual y calcular P&L"""
        self.current_price = new_price
        self.last_update = datetime.now()
        self.data_quality = data_quality
        self.has_real_data = data_quality in ["real", "delayed"]
        self.last_data_update = datetime.now()
        
        # Calcular P&L basado en avg_cost (incluye comisiones)
        # Convertir a float para evitar errores de tipo con Decimal
        avg_cost_float = float(self.avg_cost)
        shares_float = float(self.shares)
        
        self.pnl_unrealized = (new_price - avg_cost_float) * shares_float
        self.pnl_percent = ((new_price - avg_cost_float) / avg_cost_float) * 100
        
        # Actualizar status basado en proximidad a stops/targets
        # Convertir a float para evitar errores de tipo con Decimal
        stop_price_float = float(self.stop_price) if self.stop_price else 0.0
        target_price_float = float(self.target_price) if self.target_price else 0.0
        
        if stop_price_float > 0 and new_price <= stop_price_float * 1.02:  # Dentro del 2% del stop
            self.status = "near_stop"
        elif target_price_float > 0 and new_price >= target_price_float * 0.98:  # Dentro del 2% del target
            self.status = "near_target"
        else:
            self.status = "active"
    
    def is_in_grace_period(self) -> bool:
        """¿Está en período de gracia después de la entrada?"""
        time_since_entry = datetime.now() - self.entry_time
        return time_since_entry.total_seconds() < (self.grace_period_minutes * 60)
    
    def should_auto_close_stop(self) -> bool:
        """¿Debería cerrarse automáticamente por stop loss?"""
        if not self.has_real_data or not self.is_manual_position():
            return False
        
        # 🚨 CRITICAL: No cerrar durante período de gracia
        if self.is_in_grace_period():
            return False
        
        # Auto-cerrar solo si tenemos datos reales y llegamos al stop
        return self.current_price <= self.stop_price
    
    def should_auto_close_target(self) -> bool:
        """¿Debería cerrarse automáticamente por take profit?"""
        if not self.has_real_data or not self.is_manual_position():
            return False
        
        # 🚨 CRITICAL: No cerrar durante período de gracia
        if self.is_in_grace_period():
            return False
        
        # Auto-cerrar solo si tenemos datos reales y llegamos al target
        return self.current_price >= self.target_price
    
    def needs_manual_validation(self) -> bool:
        """¿Necesita validación manual? (sin datos reales pero precio teórico llegó a SL/TP)"""
        if self.has_real_data:
            return False
        
        # 🚨 CRITICAL: No validar durante período de gracia
        if self.is_in_grace_period():
            return False
        
        # Solo alertar si tenemos un precio válido (no $0.00)
        if self.current_price <= 0:
            return False
        
        # Si no tenemos datos reales, pero según nuestros datos debería haber tocado
        return (self.current_price <= self.stop_price or 
                self.current_price >= self.target_price)
    
    def get_data_quality_icon(self) -> str:
        """Icono para mostrar calidad de datos"""
        if self.data_quality == "real":
            return "🟢"  # Datos reales
        elif self.data_quality == "delayed":
            return "🟡"  # Datos con delay
        elif self.data_quality == "stale":
            return "🟠"  # Datos viejos
        else:
            return "🔴"  # Sin datos
    
    def is_profitable(self) -> bool:
        """¿Está la posición en verde?"""
        return self.current_price > self.avg_cost
    
    def get_color_status(self) -> str:
        """Obtener status con color para display"""
        if self.pnl_unrealized > 0:
            return "🟢"  # Verde si está ganando
        elif self.pnl_unrealized < 0:
            return "🔴"  # Rojo si está perdiendo
        else:
            return "⚪"  # Blanco si está en breakeven
    
    def is_manual_position(self) -> bool:
        """¿Es una posición que requiere monitoreo manual?"""
        return "PREMARKET_MANUAL" in self.system_tag or self.stop_order_id is None
    
    def needs_urgent_attention(self) -> bool:
        """¿Necesita atención urgente? (cerca del stop en posición manual)"""
        if not self.is_manual_position():
            return False
        
        # Si es manual y está perdiendo más del 12% (cerca del stop de -15%)
        return self.pnl_percent <= -12.0
    
    def get_alert_status(self) -> str:
        """Obtener status de alerta para posiciones manuales"""
        if not self.is_manual_position():
            return ""
        
        if self.needs_urgent_attention():
            return "🚨 STOP ALERT"
        elif self.pnl_percent <= -8.0:  # Warning a -8%
            return "⚠️ WATCH"
        elif self.pnl_percent >= 15.0:  # Near target at +15%
            return "🎯 NEAR TARGET"
        else:
            return "👁️ MONITOR"

class PositionTracker:
    """
    Tracker de posiciones activas con persistencia y updates en tiempo real
    """
    
    def __init__(self, storage=None):
        self.positions: Dict[str, ActivePosition] = {}
        self.running = False
        self.storage = storage  # PostgreSQL Storage para persistencia
        
        # NO CARGAR POSICIONES AQUÍ - Se cargarán después de conectar PostgreSQL Storage
        logger.debug("PositionTracker initialized - waiting for PostgreSQL Storage connection")
    
    def add_position(self, symbol: str, shares: int, entry_price: float, 
                    avg_cost: float, stop_price: float, target_price: float,
                    stop_order_id: int = None, target_order_id: int = None,
                    system_tag: str = "IBKR_AUTO", has_real_data: bool = False,
                    data_quality: str = "unknown", skip_db_save: bool = False):
        """Agregar nueva posición al tracking"""
        position = ActivePosition(
            symbol=symbol,
            shares=shares,
            entry_price=entry_price,
            avg_cost=avg_cost,
            stop_price=stop_price,
            target_price=target_price,
            entry_time=datetime.now(),
            stop_order_id=stop_order_id,
            target_order_id=target_order_id,
            system_tag=system_tag,
            has_real_data=has_real_data,
            data_quality=data_quality
        )
        
        self.positions[symbol] = position
        
        # Guardar en PostgreSQL Storage SOLO si no existe ya
        if self.storage and not skip_db_save:
            try:
                self.storage.add_active_position(
                    symbol=symbol,
                    shares=shares,
                    entry_price=entry_price,
                    avg_cost=avg_cost,
                    stop_price=stop_price,
                    target_price=target_price,
                    source="tracker"
                )
            except Exception as e:
                if "duplicate key value violates unique constraint" in str(e):
                    logger.warning(f"🔄 Position {symbol} already exists in PostgreSQL, skipping DB save")
                else:
                    logger.error(f"❌ Error saving position {symbol} to PostgreSQL: {e}")
                    raise
        
        logger.info(f"📈 Added position to tracker: {symbol} - {shares} shares @ ${avg_cost:.2f}")
        logger.info(f"   Stop: ${stop_price:.2f} | Target: ${target_price:.2f}")
    
    def update_position_price(self, symbol: str, current_price: float, data_quality: str = "unknown"):
        """Actualizar precio actual de una posición"""
        if symbol in self.positions:
            self.positions[symbol].update_price(current_price, data_quality)
            # No guardamos en cada update de precio para no saturar el disco
    
    def remove_position(self, symbol: str, reason: str = "closed"):
        """Remover posición del tracking"""
        if symbol in self.positions:
            position = self.positions[symbol]
            logger.info(f"📉 Removing position from tracker: {symbol} - Reason: {reason}")
            logger.info(f"   Final P&L: ${position.pnl_unrealized:.2f} ({position.pnl_percent:+.1f}%)")
            
            del self.positions[symbol]
            
            # Remover de PostgreSQL Storage
            if self.storage:
                self.storage.remove_active_position(symbol)
    
    def get_position(self, symbol: str) -> Optional[ActivePosition]:
        """Obtener posición específica"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[ActivePosition]:
        """Obtener todas las posiciones activas"""
        return list(self.positions.values())
    
    def get_positions_dict(self) -> Dict[str, ActivePosition]:
        """Obtener diccionario de posiciones activas (symbol -> position)"""
        return self.positions.copy()
    
    def get_positions_count(self) -> int:
        """Número de posiciones activas"""
        return len(self.positions)
    
    def get_total_pnl(self) -> float:
        """P&L total de todas las posiciones"""
        return sum(pos.pnl_unrealized for pos in self.positions.values())
    
    def get_positions_summary(self) -> Dict:
        """Resumen de todas las posiciones"""
        positions = list(self.positions.values())
        if not positions:
            return {
                'total_positions': 0,
                'total_pnl': 0.0,
                'profitable': 0,
                'losing': 0,
                'near_stop': 0,
                'near_target': 0
            }
        
        profitable = sum(1 for p in positions if p.pnl_unrealized > 0)
        losing = sum(1 for p in positions if p.pnl_unrealized < 0)
        near_stop = sum(1 for p in positions if p.status == "near_stop")
        near_target = sum(1 for p in positions if p.status == "near_target")
        
        return {
            'total_positions': len(positions),
            'total_pnl': sum(p.pnl_unrealized for p in positions),
            'profitable': profitable,
            'losing': losing,
            'near_stop': near_stop,
            'near_target': near_target
        }
    
    def display_positions_table(self):
        """Mostrar tabla de posiciones con colores"""
        positions = self.get_all_positions()
        if not positions:
            print("📭 No active positions")
            return
        
        summary = self.get_positions_summary()
        
        # Contar posiciones manuales y alertas
        manual_positions = sum(1 for p in positions if p.is_manual_position())
        urgent_alerts = sum(1 for p in positions if p.needs_urgent_attention())
        
        print(f"\n📊 ACTIVE POSITIONS TRACKER")
        print("=" * 105)
        print(f"Total: {summary['total_positions']} | "
              f"P&L: ${summary['total_pnl']:+.2f} | "
              f"🟢 {summary['profitable']} | "
              f"🔴 {summary['losing']} | "
              f"👁️ Manual: {manual_positions}")
        
        if urgent_alerts > 0:
            print(f"🚨 URGENT: {urgent_alerts} position(s) near stop loss - MANUAL ACTION REQUIRED!")
        
        print("-" * 105)
        print(f"{'SYMBOL':<8} {'QTY':<4} {'ENTRY':<8} {'CURRENT':<8} {'P&L':<10} {'%':<7} {'STOP':<8} {'TARGET':<8} {'DATA':<5} {'ALERT':<13} {'TIME'}")
        print("-" * 105)
        
        # Ordenar por P&L descendente
        sorted_positions = sorted(positions, key=lambda p: p.pnl_unrealized, reverse=True)
        
        for pos in sorted_positions:
            color = pos.get_color_status()
            alert_status = pos.get_alert_status()
            data_icon = pos.get_data_quality_icon()
            
            # Formatear tiempo desde entrada
            time_since = datetime.now() - pos.entry_time
            if time_since.total_seconds() < 3600:  # Menos de 1 hora
                time_str = f"{int(time_since.total_seconds() / 60)}m"
            else:
                time_str = f"{int(time_since.total_seconds() / 3600)}h"
            
            print(f"{pos.symbol:<8} {pos.shares:<4} ${pos.avg_cost:<7.2f} "
                  f"${pos.current_price:<7.2f} {color}${pos.pnl_unrealized:<8.2f} "
                  f"{pos.pnl_percent:+6.1f}% ${pos.stop_price:<7.2f} ${pos.target_price:<7.2f} "
                  f"{data_icon:<5} {alert_status:<13} {time_str}")
        
        print("=" * 105)
    
    def save_positions(self):
        """Save positions to PostgreSQL - JSON completely eliminated"""
        # All persistence is handled by PostgreSQL when positions are added/updated
        # This method exists for compatibility but does nothing
        pass
        
        # OLD JSON SAVING CODE (commented out):
        # try:
        #     data = {}
        #     for symbol, position in self.positions.items():
        #         pos_dict = asdict(position)
        #         # Convertir datetime a string para JSON
        #         pos_dict['entry_time'] = position.entry_time.isoformat()
        #         pos_dict['last_update'] = position.last_update.isoformat()
        #         # Manejar last_data_update que puede ser None
        #         if position.last_data_update:
        #             pos_dict['last_data_update'] = position.last_data_update.isoformat()
        #         else:
        #             pos_dict['last_data_update'] = None
        #         data[symbol] = pos_dict
        #     
        #     with open(self.data_file, 'w') as f:
        #         json.dump(data, f, indent=2)
        #         
        # except Exception as e:
        #     logger.error(f"Error saving positions: {e}")
    
    def load_positions(self):
        """Cargar posiciones desde PostgreSQL Storage como fuente única de verdad"""
        if not self.storage or not self.storage.connected:
            logger.warning("PostgreSQL Storage not available - starting with empty tracker")
            return
        
        try:
            # LIMPIAR posiciones existentes para evitar duplicados
            self.positions.clear()
            logger.info("🧹 Cleared existing positions from tracker")
            
            # Obtener posiciones activas de PostgreSQL Storage
            active_positions = self.storage.get_active_positions()
            
            if not active_positions:
                logger.info("📭 No active positions found in PostgreSQL Storage")
                return
            
            logger.info(f"📋 PostgreSQL Storage returned {len(active_positions)} positions: {[p['symbol'] for p in active_positions]}")
            
            loaded_count = 0
            for pos in active_positions:
                try:
                    symbol = pos['symbol']
                    shares = int(pos['shares'])
                    entry_price = float(pos['entry_price'])
                    avg_cost = float(pos['avg_cost'])
                    stop_price = float(pos.get('stop_price', 0))
                    target_price = float(pos.get('target_price', 0))
                    
                    # Crear ActivePosition
                    position = ActivePosition(
                        symbol=symbol,
                        shares=shares,
                        entry_price=entry_price,
                        avg_cost=avg_cost,
                        stop_price=stop_price,
                        target_price=target_price,
                        entry_time=datetime.now(),  # Aproximado
                        system_tag=pos.get('system_tag', 'LOADED_FROM_STORAGE'),
                        has_real_data=bool(pos.get('has_real_data', False)),
                        data_quality=pos.get('data_quality', 'unknown')
                    )
                    
                    self.positions[symbol] = position
                    loaded_count += 1
                    logger.info(f"✅ Loaded {symbol}: {shares} shares @ ${avg_cost:.2f}")
                    
                except Exception as e:
                    logger.error(f"Failed to load position {pos.get('symbol', 'UNKNOWN')}: {e}")
            
            logger.info(f"📦 Final tracker state: {loaded_count} positions loaded: {list(self.positions.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to load positions from PostgreSQL Storage: {e}")
        
        # OLD JSON LOADING CODE (commented out):
        # try:
        #     if os.path.exists(self.data_file):
        #         with open(self.data_file, 'r') as f:
        #             data = json.load(f)
        #         
        #         for symbol, pos_dict in data.items():
        #             # Convertir strings de datetime de vuelta a datetime
        #             pos_dict['entry_time'] = datetime.fromisoformat(pos_dict['entry_time'])
        #             pos_dict['last_update'] = datetime.fromisoformat(pos_dict['last_update'])
        #             # Manejar last_data_update que puede ser None
        #             if pos_dict.get('last_data_update'):
        #                 pos_dict['last_data_update'] = datetime.fromisoformat(pos_dict['last_data_update'])
        #             else:
        #                 pos_dict['last_data_update'] = None
        #             
        #             position = ActivePosition(**pos_dict)
        #             self.positions[symbol] = position
        #         
        #         logger.info(f"📦 Loaded {len(self.positions)} positions from {self.data_file}")
        #         
        # except Exception as e:
        #     logger.warning(f"Could not load positions: {e}")
    
    async def start_price_updates(self, broker, update_interval: int = 10):
        """Iniciar updates automáticos de precios"""
        self.running = True
        logger.info(f"🔄 Starting position price updates every {update_interval}s")
        
        while self.running:
            try:
                if self.positions:
                    await self._update_all_prices(broker)
                    
                    # Procesar acciones semi-automáticas después de cada update
                    if hasattr(broker, 'trading_console'):
                        await broker.trading_console.process_semi_auto_actions()
                    
                    # Guardar posiciones cada 5 updates (para persistencia sin saturar)
                    if datetime.now().second % 50 == 0:  # Cada ~50 segundos
                        self.save_positions()
                
                await asyncio.sleep(update_interval)
                
            except Exception as e:
                logger.error(f"Error updating positions: {e}")
                await asyncio.sleep(update_interval)
    
    async def _update_all_prices(self, broker):
        """Actualizar precios de todas las posiciones"""
        for symbol in list(self.positions.keys()):
            try:
                # Solicitar datos del mercado
                await broker.request_market_data(symbol)
                await asyncio.sleep(0.5)  # Pequeña pausa entre requests
                
                market_data = broker.get_market_data(symbol)
                if market_data:
                    logger.info(f"📊 MARKET DATA UPDATE for {symbol}:")
                    logger.info(f"   Last: ${market_data.last:.4f}")
                    logger.info(f"   Bid: ${market_data.bid:.4f}")
                    logger.info(f"   Ask: ${market_data.ask:.4f}")
                    logger.info(f"   Volume: {market_data.volume:,}")
                    
                    # Determinar calidad de datos basado en respuesta de IBKR
                    data_quality = self._evaluate_data_quality(market_data, symbol)
                    logger.info(f"   📊 Data quality determined: {data_quality}")
                    
                    if market_data.last > 0:
                        self.update_position_price(symbol, market_data.last, data_quality)
                    else:
                        logger.warning(f"   ⚠️  Skipping price update - invalid price: ${market_data.last:.4f}")
                else:
                    logger.warning(f"   ❌ No market data available for {symbol}")
                    
            except Exception as e:
                logger.warning(f"Could not update price for {symbol}: {e}")
    
    def _evaluate_data_quality(self, market_data, symbol: str) -> str:
        """Evaluar calidad de datos de mercado"""
        import math
        
        # Verificar si tenemos bid/ask válidos (indicador de datos reales)
        has_valid_bid = market_data.bid and market_data.bid > 0 and not math.isnan(market_data.bid)
        has_valid_ask = market_data.ask and market_data.ask > 0 and not math.isnan(market_data.ask)
        has_volume = market_data.volume and market_data.volume > 0
        
        # Si tenemos bid/ask válidos y volumen, datos reales
        if has_valid_bid and has_valid_ask and has_volume:
            return "real"
        
        # Si tenemos bid/ask pero no volumen, datos con delay
        elif has_valid_bid and has_valid_ask:
            return "delayed"
        
        # Si solo tenemos last o close, datos viejos
        elif market_data.last > 0:
            return "stale"
        
        # Sin datos útiles
        else:
            return "none"
    
    def stop_updates(self):
        """Detener updates automáticos"""
        self.running = False
        self.save_positions()  # Guardar antes de salir
        logger.info("🛑 Position tracker stopped")
    
    def get_semi_auto_actions(self) -> Dict[str, List[str]]:
        """Obtener acciones semi-automáticas pendientes"""
        actions = {
            "auto_close_stop": [],      # Cerrar automáticamente por stop loss
            "auto_close_target": [],    # Cerrar automáticamente por take profit  
            "manual_validation": []     # Requiere validación manual
        }
        
        for symbol, position in self.positions.items():
            if position.should_auto_close_stop():
                actions["auto_close_stop"].append({
                    "symbol": symbol,
                    "reason": "stop_loss",
                    "current_price": position.current_price,
                    "stop_price": position.stop_price,
                    "data_quality": position.data_quality
                })
            elif position.should_auto_close_target():
                actions["auto_close_target"].append({
                    "symbol": symbol,
                    "reason": "take_profit",
                    "current_price": position.current_price,
                    "target_price": position.target_price,
                    "data_quality": position.data_quality
                })
            elif position.needs_manual_validation():
                # Determinar si tocó stop o target
                reason = "stop_hit" if position.current_price <= position.stop_price else "target_hit"
                actions["manual_validation"].append({
                    "symbol": symbol,
                    "reason": reason,
                    "current_price": position.current_price,
                    "stop_price": position.stop_price,
                    "target_price": position.target_price,
                    "data_quality": position.data_quality,
                    "command": f"close {symbol}"
                })
        
        return actions
    
    def sync_with_ibkr_positions(self, ibkr_positions):
        """Sincronizar con posiciones reales de IBKR"""
        ibkr_symbols = {pos.contract.symbol for pos in ibkr_positions if pos.position != 0}
        tracked_symbols = set(self.positions.keys())
        
        # Remover posiciones que ya no existen en IBKR
        for symbol in tracked_symbols - ibkr_symbols:
            logger.warning(f"🔄 Position {symbol} no longer in IBKR - removing from tracker")
            self.remove_position(symbol, "closed_external")
        
        # Log de posiciones sin tracking
        for symbol in ibkr_symbols - tracked_symbols:
            logger.warning(f"⚠️  IBKR position {symbol} not tracked - consider adding manually")