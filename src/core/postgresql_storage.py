"""
PostgreSQL Storage - Unified database for trading system
Simple and reliable ACID-compliant storage
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import uuid
import json
from contextlib import contextmanager

from src.core.models import Trade, TradingSession

logger = logging.getLogger(__name__)

class PostgreSQLStorage:
    """Storage usando PostgreSQL - simple, confiable y con transacciones ACID"""
    
    def __init__(self, strategy_name: str = "PreMarket"):
        self.strategy_name = strategy_name
        self.connection_params = {
            'host': 'localhost',
            'port': 5432,
            'dbname': 'trading_db',
            'user': 'trader',
            'password': 'trader_password_2024'
        }
        self.connected = False
        
    @contextmanager
    def get_connection(self):
        """Context manager para manejar conexiones de forma segura"""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def connect(self) -> bool:
        """Conectar y verificar PostgreSQL"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version()")
                    version = cur.fetchone()[0]
                    logger.info(f"Connected to PostgreSQL: {version}")
                    self.connected = True
                    return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False
    
    def save_trade(self, trade: Trade) -> str:
        """Guardar un trade - devuelve UUID"""
        try:
            trade_uuid = str(uuid.uuid4())
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO trades (
                            id, trade_id, strategy, symbol, source, alert_type,
                            alert_price, alert_time, date, order_time,
                            entry_time, exit_time, last_price, bid_price,
                            ask_price, volume, market_cap, previous_close,
                            gap_percentage, lod, volume_premarket, entry_price,
                            stop_price, target_price, shares, position_size,
                            risk_amount, entry_order_id, stop_order_id,
                            target_order_id, status, trade_taken, decision_reason,
                            rejection_reason, entry_filled, exit_filled,
                            exit_price, exit_reason, realized_pnl, commission,
                            duration_minutes, system_tag, notes
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s
                        )
                    """, (
                        trade_uuid,
                        trade.id if trade.id else 0,
                        self.strategy_name,
                        trade.symbol,
                        'manual',
                        'manual',
                        0.0,
                        '',
                        trade.date.date() if hasattr(trade.date, 'date') else trade.date,
                        trade.order_time,
                        trade.entry_time,
                        trade.exit_time,
                        0.0,  # last_price
                        0.0,  # bid_price
                        0.0,  # ask_price
                        0,    # volume
                        0.0,  # market_cap
                        0.0,  # previous_close
                        trade.gap_percent if hasattr(trade, 'gap_percent') else 0.0,
                        trade.lod if hasattr(trade, 'lod') else 0.0,
                        trade.volume_premarket if hasattr(trade, 'volume_premarket') else 0,
                        trade.entry_price,
                        trade.stop_price,
                        trade.target_price,
                        trade.shares,
                        trade.entry_price * trade.shares,  # position_size
                        trade.risk_amount,
                        trade.entry_order_id,
                        trade.stop_order_id,
                        trade.target_order_id,
                        trade.status,
                        trade.status in ['filled', 'partial', 'stopped', 'target_hit'],
                        'TRADE_EXECUTED' if trade.status in ['filled', 'partial'] else trade.status.upper(),
                        '',
                        trade.status == 'filled',
                        trade.status in ['stopped', 'target_hit', 'closed_time'],
                        trade.exit_price if trade.exit_price else 0.0,
                        trade.status if trade.status in ['stopped', 'target_hit'] else '',
                        trade.pnl if hasattr(trade, 'pnl') else 0.0,
                        0.0,  # commission
                        0,    # duration_minutes
                        trade.system_tag if hasattr(trade, 'system_tag') else 'IBKR_AUTO',
                        trade.notes if hasattr(trade, 'notes') else ''
                    ))
            
            logger.info(f"Saved trade {trade.symbol} to PostgreSQL with UUID: {trade_uuid}")
            return trade_uuid
            
        except Exception as e:
            logger.error(f"Error saving trade {trade.symbol}: {e}")
            return ""
    
    def update_trade(self, trade: Trade):
        """Actualizar un trade existente"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Actualizar por symbol y entry_order_id
                    cur.execute("""
                        UPDATE trades
                        SET status = %s,
                            exit_time = %s,
                            exit_price = %s,
                            exit_reason = %s,
                            realized_pnl = %s,
                            trade_taken = %s,
                            entry_filled = %s,
                            exit_filled = %s,
                            updated_at = NOW()
                        WHERE symbol = %s 
                        AND entry_order_id = %s
                        AND strategy = %s
                    """, (
                        trade.status,
                        trade.exit_time,
                        trade.exit_price if trade.exit_price else 0.0,
                        trade.status if trade.status in ['stopped', 'target_hit'] else '',
                        trade.pnl if hasattr(trade, 'pnl') else 0.0,
                        trade.status in ['filled', 'partial', 'stopped', 'target_hit'],
                        trade.status == 'filled',
                        trade.status in ['stopped', 'target_hit', 'closed_time'],
                        trade.symbol,
                        trade.entry_order_id,
                        self.strategy_name
                    ))
                    
            logger.info(f"Updated trade {trade.symbol} in PostgreSQL")
                
        except Exception as e:
            logger.error(f"Error updating trade {trade.symbol}: {e}")
    
    def get_active_trades(self) -> List[Trade]:
        """Obtener trades activos (pending, filled, partial)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM trades
                        WHERE strategy = %s
                        AND status IN ('pending', 'filled', 'partial')
                        ORDER BY created_at DESC
                    """, (self.strategy_name,))
                    
                    rows = cur.fetchall()
                    trades = []
                    for row in rows:
                        trade = self._row_to_trade(row)
                        if trade:
                            trades.append(trade)
                    
                    return trades
            
        except Exception as e:
            logger.error(f"Error getting active trades: {e}")
            return []
    
    def get_trades_by_tag(self, tag: str) -> List[Trade]:
        """Obtener trades activos por system_tag"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM trades
                        WHERE strategy = %s
                        AND system_tag = %s
                        AND status IN ('pending', 'filled', 'partial')
                        ORDER BY created_at DESC
                    """, (self.strategy_name, tag))
                    
                    rows = cur.fetchall()
                    trades = []
                    for row in rows:
                        trade = self._row_to_trade(row)
                        if trade:
                            trades.append(trade)
                    
                    return trades
            
        except Exception as e:
            logger.error(f"Error getting trades by tag {tag}: {e}")
            return []
    
    def get_today_session(self) -> TradingSession:
        """Obtener o crear sesión de trading de hoy"""
        today = date.today()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Buscar sesión existente
                    cur.execute("""
                        SELECT * FROM trading_sessions
                        WHERE strategy = %s AND date = %s
                        LIMIT 1
                    """, (self.strategy_name, today))
                    
                    row = cur.fetchone()
                    if row:
                        return TradingSession(
                            date=datetime.combine(row['date'], datetime.min.time()),
                            total_trades=row['total_trades'],
                            winning_trades=row['winning_trades'],
                            losing_trades=row['losing_trades'],
                            total_pnl=row['total_pnl'],
                            max_drawdown=row['max_drawdown'],
                            status=row['status']
                        )
                    else:
                        # Crear nueva sesión
                        session = TradingSession(date=datetime.now())
                        cur.execute("""
                            INSERT INTO trading_sessions (
                                id, date, strategy, total_trades, winning_trades,
                                losing_trades, total_pnl, max_drawdown, status
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            str(uuid.uuid4()),
                            today,
                            self.strategy_name,
                            0, 0, 0, 0.0, 0.0, 'active'
                        ))
                        
                        logger.info(f"Created new trading session for {today}")
                        return session
                        
        except Exception as e:
            logger.error(f"Error getting today's session: {e}")
            return TradingSession(date=datetime.now())
    
    def update_session(self, session: TradingSession):
        """Actualizar sesión de trading"""
        try:
            session_date = session.date.date() if hasattr(session.date, 'date') else session.date
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE trading_sessions
                        SET total_trades = %s,
                            winning_trades = %s,
                            losing_trades = %s,
                            total_pnl = %s,
                            max_drawdown = %s,
                            status = %s,
                            updated_at = NOW()
                        WHERE strategy = %s AND date = %s
                    """, (
                        session.total_trades,
                        session.winning_trades,
                        session.losing_trades,
                        session.total_pnl,
                        session.max_drawdown,
                        session.status,
                        self.strategy_name,
                        session_date
                    ))
            
            logger.info(f"Updated trading session for {session_date}")
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
    
    def get_daily_report(self, target_date: datetime) -> Dict[str, Any]:
        """Generar reporte diario"""
        target_date_str = target_date.date() if hasattr(target_date, 'date') else target_date
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM trades
                        WHERE strategy = %s
                        AND date = %s
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout')
                    """, (self.strategy_name, target_date_str))
                    
                    rows = cur.fetchall()
                    if not rows:
                        return self._empty_report(target_date_str)
                    
                    completed_trades = []
                    for row in rows:
                        trade = self._row_to_trade(row)
                        if trade:
                            completed_trades.append(trade)
                    
                    winners = [t for t in completed_trades if t.pnl > 0]
                    losers = [t for t in completed_trades if t.pnl <= 0]
                    
                    return {
                        'date': str(target_date_str),
                        'total_trades': len(completed_trades),
                        'winners': len(winners),
                        'losers': len(losers),
                        'win_rate': len(winners) / len(completed_trades) * 100 if completed_trades else 0,
                        'total_pnl': sum(t.pnl for t in completed_trades),
                        'avg_win': sum(t.pnl for t in winners) / len(winners) if winners else 0,
                        'avg_loss': sum(t.pnl for t in losers) / len(losers) if losers else 0,
                        'best_trade': max(t.pnl for t in completed_trades) if completed_trades else 0,
                        'worst_trade': min(t.pnl for t in completed_trades) if completed_trades else 0
                    }
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return self._empty_report(target_date_str)
    
    def _empty_report(self, date_str) -> Dict[str, Any]:
        """Reporte vacío por defecto"""
        return {
            'date': str(date_str),
            'total_trades': 0,
            'winners': 0,
            'losers': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'best_trade': 0,
            'worst_trade': 0
        }
    
    def _row_to_trade(self, row: dict) -> Optional[Trade]:
        """Convertir fila de PostgreSQL a objeto Trade"""
        try:
            return Trade(
                id=row.get('trade_id'),
                symbol=row['symbol'],
                date=datetime.combine(row['date'], datetime.min.time()) if row.get('date') else datetime.now(),
                order_time=row.get('order_time', datetime.now()),
                entry_order_id=row.get('entry_order_id', 0),
                stop_order_id=row.get('stop_order_id', 0),
                target_order_id=row.get('target_order_id', 0),
                entry_price=row.get('entry_price', 0),
                stop_price=row.get('stop_price', 0),
                target_price=row.get('target_price', 0),
                shares=row.get('shares', 0),
                risk_amount=row.get('risk_amount', 0),
                status=row.get('status', 'pending'),
                entry_time=row.get('entry_time'),
                exit_time=row.get('exit_time'),
                exit_price=row.get('exit_price', 0),
                pnl=row.get('realized_pnl', 0),
                gap_percent=row.get('gap_percentage', 0),
                lod=row.get('lod', 0),
                volume_premarket=row.get('volume_premarket', 0),
                notes=row.get('notes', ''),
                system_tag=row.get('system_tag', 'IBKR_AUTO')
            )
        except Exception as e:
            logger.error(f"Error converting row to trade: {e}")
            return None
    
    # =============================================================================
    # ACTIVE POSITIONS MANAGEMENT
    # =============================================================================
    
    def add_active_position(self, symbol: str, shares: int, entry_price: float, 
                           avg_cost: float, stop_price: float, target_price: float,
                           source: str = "imported") -> bool:
        """Agregar posición activa"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO active_positions (
                            id, symbol, strategy, shares, entry_price,
                            avg_cost, stop_price, target_price, source, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(uuid.uuid4()),
                        symbol,
                        self.strategy_name,
                        shares,
                        entry_price,
                        avg_cost,
                        stop_price,
                        target_price,
                        source,
                        'active'
                    ))
            
            logger.info(f"Added active position {symbol} to PostgreSQL")
            return True
            
        except Exception as e:
            logger.error(f"Error adding active position {symbol}: {e}")
            return False
    
    def remove_active_position(self, symbol: str) -> bool:
        """Remover posición activa - elimina del storage"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Simplemente eliminar la posición activa en lugar de marcar como closed
                    # Esto evita problemas con constraints y es más limpio
                    cur.execute("""
                        DELETE FROM active_positions
                        WHERE symbol = %s
                        AND strategy = %s
                        AND status = 'active'
                    """, (symbol, self.strategy_name))
                    
                    rows_affected = cur.rowcount
            
            if rows_affected > 0:
                logger.info(f"Removed active position {symbol} from PostgreSQL")
                return True
            else:
                logger.warning(f"No active position found for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing active position {symbol}: {e}")
            return False
    
    def get_active_positions(self) -> List[dict]:
        """Obtener todas las posiciones activas"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM active_positions
                        WHERE strategy = %s
                        AND status = 'active'
                        ORDER BY updated_at DESC
                    """, (self.strategy_name,))
                    
                    return cur.fetchall()
            
        except Exception as e:
            logger.error(f"Error getting active positions: {e}")
            return []
    
    def clear_active_positions(self) -> bool:
        """Limpiar todas las posiciones activas - marca todas como closed"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE active_positions
                        SET status = 'closed',
                            updated_at = NOW()
                        WHERE strategy = %s
                        AND status = 'active'
                    """, (self.strategy_name,))
                    
                    count = cur.rowcount
            
            logger.info(f"Cleared {count} active positions")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing active positions: {e}")
            return False
    
    def update_position_orders(self, symbol: str, stop_order_id: int = None, target_order_id: int = None) -> bool:
        """Actualizar order IDs de una posición"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if stop_order_id and target_order_id:
                        cur.execute("""
                            UPDATE active_positions
                            SET stop_order_id = %s,
                                target_order_id = %s,
                                updated_at = NOW()
                            WHERE symbol = %s
                            AND strategy = %s
                            AND status = 'active'
                        """, (stop_order_id, target_order_id, symbol, self.strategy_name))
                    elif stop_order_id:
                        cur.execute("""
                            UPDATE active_positions
                            SET stop_order_id = %s,
                                updated_at = NOW()
                            WHERE symbol = %s
                            AND strategy = %s
                            AND status = 'active'
                        """, (stop_order_id, symbol, self.strategy_name))
                    elif target_order_id:
                        cur.execute("""
                            UPDATE active_positions
                            SET target_order_id = %s,
                                updated_at = NOW()
                            WHERE symbol = %s
                            AND strategy = %s
                            AND status = 'active'
                        """, (target_order_id, symbol, self.strategy_name))
            
            logger.info(f"Updated position orders for {symbol}")
            return True
                
        except Exception as e:
            logger.error(f"Error updating position orders {symbol}: {e}")
            return False
    
    def save_order_update(self, order_id: int, symbol: str, status: str, 
                         filled_qty: float = 0, avg_fill_price: float = 0) -> bool:
        """Guardar actualización de orden"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO order_updates (
                            id, order_id, symbol, status,
                            filled_qty, avg_fill_price, strategy
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(uuid.uuid4()),
                        order_id,
                        symbol,
                        status,
                        filled_qty,
                        avg_fill_price,
                        self.strategy_name
                    ))
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving order update: {e}")
            return False
    
    # =============================================================================
    # ANALYTICS AND QUEUE FUNCTIONS
    # =============================================================================
    
    def create_flash_alert(self, symbol: str, source: str, alert_type: str, 
                          alert_price: float = 0, metadata: dict = None) -> str:
        """Crear alerta flash"""
        try:
            alert_id = str(uuid.uuid4())
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO api_invocations (
                            id, strategy_name, endpoint, symbols, source, 
                            alert_type, processing_time_ms, symbols_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        alert_id,
                        self.strategy_name,
                        '/api/trade',
                        [symbol],
                        source,
                        alert_type,
                        0.0,
                        1
                    ))
            
            logger.info(f"Created flash alert for {symbol}")
            return alert_id
        except Exception as e:
            logger.error(f"Error creating flash alert: {e}")
            return ""
    
    def create_trade_queue_entry(self, symbol: str, source: str, alert_type: str,
                                market_data: dict, trade_setup: dict, 
                                decision: str, trade_taken: bool = False) -> str:
        """Crear entrada en cola de trades"""
        try:
            entry_id = str(uuid.uuid4())
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO trade_analysis (
                            id, strategy, symbol, source, alert_type,
                            last_price, bid_price, ask_price, volume, market_cap,
                            trade_taken, decision_reason, entry_price, stop_price,
                            target_price, shares, position_size
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        entry_id,
                        self.strategy_name,
                        symbol,
                        source,
                        alert_type,
                        market_data.get('last_price', 0),
                        market_data.get('bid_price', 0),
                        market_data.get('ask_price', 0),
                        market_data.get('volume', 0),
                        market_data.get('market_cap', 0),
                        trade_taken,
                        decision,
                        trade_setup.get('entry_price', 0),
                        trade_setup.get('stop_price', 0),
                        trade_setup.get('target_price', 0),
                        trade_setup.get('shares', 0),
                        trade_setup.get('position_size', 0)
                    ))
            
            logger.info(f"Created trade queue entry for {symbol}")
            return entry_id
        except Exception as e:
            logger.error(f"Error creating trade queue entry: {e}")
            return ""
    
    def get_premarket_queue(self) -> List[dict]:
        """Obtener cola de premarket"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM trade_analysis
                        WHERE strategy = %s
                        AND trade_taken = false
                        AND timestamp >= CURRENT_DATE
                        ORDER BY timestamp ASC
                    """, (self.strategy_name,))
                    
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting premarket queue: {e}")
            return []
    
    def clear_premarket_queue(self) -> bool:
        """Limpiar cola de premarket"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM trade_analysis
                        WHERE strategy = %s
                        AND trade_taken = false
                        AND timestamp >= CURRENT_DATE
                    """, (self.strategy_name,))
                    
                    count = cur.rowcount
            
            logger.info(f"Cleared {count} items from premarket queue")
            return True
        except Exception as e:
            logger.error(f"Error clearing premarket queue: {e}")
            return False
    
    def update_trade_status(self, trade_id: str, status: str, **kwargs):
        """Actualizar estado de trade"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Simple update de status - PostgreSQL es más flexible
                    cur.execute("""
                        UPDATE trades
                        SET status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        OR (symbol = %s AND strategy = %s)
                    """, (status, trade_id, kwargs.get('symbol', ''), self.strategy_name))
            
            logger.info(f"Updated trade status to {status}")
        except Exception as e:
            logger.error(f"Error updating trade status: {e}")
    
    def get_daily_summary(self, days: int = 7) -> dict:
        """Obtener resumen diario"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            date,
                            COUNT(*) as total_trades,
                            COUNT(*) FILTER (WHERE realized_pnl > 0) as winners,
                            COUNT(*) FILTER (WHERE realized_pnl <= 0) as losers,
                            SUM(realized_pnl) as total_pnl,
                            AVG(realized_pnl) as avg_pnl,
                            MAX(realized_pnl) as best_trade,
                            MIN(realized_pnl) as worst_trade
                        FROM trades
                        WHERE strategy = %s
                        AND date >= CURRENT_DATE - INTERVAL '%s days'
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout')
                        GROUP BY date
                        ORDER BY date DESC
                    """, (self.strategy_name, days))
                    
                    results = cur.fetchall()
                    return {
                        'summary': results,
                        'period_days': days,
                        'total_completed': sum(r['total_trades'] for r in results)
                    }
        except Exception as e:
            logger.error(f"Error getting daily summary: {e}")
            return {'summary': [], 'period_days': days, 'total_completed': 0}
    
    def log_api_invocation(self, endpoint: str, symbols: List[str], source: str, 
                          alert_type: str, processing_time: float = 0):
        """Log invocación API"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO api_invocations (
                            id, strategy_name, endpoint, symbols, source,
                            alert_type, processing_time_ms, symbols_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(uuid.uuid4()),
                        self.strategy_name,
                        endpoint,
                        symbols,
                        source,
                        alert_type,
                        processing_time,
                        len(symbols)
                    ))
            
            logger.debug(f"Logged API invocation: {endpoint}")
        except Exception as e:
            logger.error(f"Error logging API invocation: {e}")
    
    def log_system_metric(self, metric_name: str, metric_value: float, 
                         metric_unit: str = "", tags: dict = None):
        """Log métrica del sistema"""
        # Para simplicidad, no implementamos métricas complejas por ahora
        # PostgreSQL es más apropiado para datos operacionales que métricas
        logger.debug(f"System metric: {metric_name} = {metric_value} {metric_unit}")
    
    def update_position_status(self, symbol: str, status: str, reason: str):
        """Actualizar estado de posición"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Si el status es "closed", eliminar en lugar de actualizar
                    # Esto evita problemas con constraints y mantiene la tabla limpia
                    if status.lower() == "closed":
                        cur.execute("""
                            DELETE FROM active_positions
                            WHERE symbol = %s
                            AND strategy = %s
                            AND status = 'active'
                        """, (symbol, self.strategy_name))
                        
                        if cur.rowcount > 0:
                            logger.info(f"Closed and removed position: {symbol} - {reason}")
                        else:
                            logger.warning(f"No active position found to close: {symbol}")
                    else:
                        # Para otros status, actualizar normalmente
                        cur.execute("""
                            UPDATE active_positions
                            SET status = %s,
                                notes = %s,
                                updated_at = NOW()
                            WHERE symbol = %s
                            AND strategy = %s
                            AND status = 'active'
                        """, (status.lower(), reason, symbol, self.strategy_name))
                        
                        logger.info(f"Updated position status: {symbol} -> {status}")
            
        except Exception as e:
            logger.error(f"Error updating position status: {e}")
    
    def import_position(self, symbol: str, shares: int, avg_cost: float, 
                       entry_price: float, stop_price: float, target_price: float) -> bool:
        """Importar posición"""
        return self.add_active_position(
            symbol=symbol,
            shares=shares,
            entry_price=entry_price,
            avg_cost=avg_cost,
            stop_price=stop_price,
            target_price=target_price,
            source="imported"
        )
    
    def get_comprehensive_analytics(self) -> dict:
        """Obtener analytics completos y profesionales"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    
                    # === RESUMEN GENERAL ===
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_trades,
                            COUNT(*) FILTER (WHERE realized_pnl > 0) as winners,
                            COUNT(*) FILTER (WHERE realized_pnl <= 0) as losers,
                            ROUND(COUNT(*) FILTER (WHERE realized_pnl > 0) * 100.0 / NULLIF(COUNT(*), 0), 1) as win_rate,
                            ROUND(SUM(realized_pnl)::numeric, 2) as total_pnl,
                            ROUND(AVG(realized_pnl)::numeric, 2) as avg_pnl,
                            ROUND(MAX(realized_pnl)::numeric, 2) as best_trade,
                            ROUND(MIN(realized_pnl)::numeric, 2) as worst_trade,
                            ROUND(AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END)::numeric, 2) as avg_win,
                            ROUND(AVG(CASE WHEN realized_pnl <= 0 THEN realized_pnl END)::numeric, 2) as avg_loss
                        FROM trades
                        WHERE strategy = %s
                        AND trade_taken = true
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout', 'closed_external')
                    """, (self.strategy_name,))
                    overall_stats = cur.fetchone()
                    
                    # === PERFORMANCE HOY ===
                    cur.execute("""
                        SELECT 
                            COUNT(*) as trades_today,
                            COUNT(*) FILTER (WHERE realized_pnl > 0) as winners_today,
                            ROUND(SUM(realized_pnl)::numeric, 2) as pnl_today,
                            ROUND(MAX(realized_pnl)::numeric, 2) as best_today,
                            ROUND(MIN(realized_pnl)::numeric, 2) as worst_today
                        FROM trades
                        WHERE strategy = %s
                        AND trade_taken = true
                        AND date = CURRENT_DATE
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout', 'closed_external')
                    """, (self.strategy_name,))
                    today_stats = cur.fetchone()
                    
                    # === ÚLTIMOS 7 DÍAS ===
                    cur.execute("""
                        SELECT 
                            date,
                            COUNT(*) as trades,
                            COUNT(*) FILTER (WHERE realized_pnl > 0) as winners,
                            ROUND(SUM(realized_pnl)::numeric, 2) as daily_pnl,
                            ROUND(MAX(realized_pnl)::numeric, 2) as best,
                            ROUND(MIN(realized_pnl)::numeric, 2) as worst
                        FROM trades
                        WHERE strategy = %s
                        AND trade_taken = true
                        AND date >= CURRENT_DATE - INTERVAL '7 days'
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout', 'closed_external')
                        GROUP BY date
                        ORDER BY date DESC
                    """, (self.strategy_name,))
                    last_7_days = cur.fetchall()
                    
                    # === PERFORMANCE POR MES ===
                    cur.execute("""
                        SELECT 
                            TO_CHAR(date, 'YYYY-MM') as month,
                            COUNT(*) as trades,
                            COUNT(*) FILTER (WHERE realized_pnl > 0) as winners,
                            ROUND(COUNT(*) FILTER (WHERE realized_pnl > 0) * 100.0 / NULLIF(COUNT(*), 0), 1) as win_rate,
                            ROUND(SUM(realized_pnl)::numeric, 2) as monthly_pnl,
                            ROUND(AVG(realized_pnl)::numeric, 2) as avg_trade,
                            ROUND(MAX(realized_pnl)::numeric, 2) as best,
                            ROUND(MIN(realized_pnl)::numeric, 2) as worst
                        FROM trades
                        WHERE strategy = %s
                        AND trade_taken = true
                        AND date >= CURRENT_DATE - INTERVAL '12 months'
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout', 'closed_external')
                        GROUP BY TO_CHAR(date, 'YYYY-MM')
                        ORDER BY month DESC
                    """, (self.strategy_name,))
                    monthly_performance = cur.fetchall()
                    
                    # === TOP SÍMBOLOS ===
                    cur.execute("""
                        SELECT 
                            symbol,
                            COUNT(*) as trades,
                            COUNT(*) FILTER (WHERE realized_pnl > 0) as winners,
                            ROUND(SUM(realized_pnl)::numeric, 2) as total_pnl,
                            ROUND(AVG(realized_pnl)::numeric, 2) as avg_pnl,
                            ROUND(MAX(realized_pnl)::numeric, 2) as best,
                            ROUND(MIN(realized_pnl)::numeric, 2) as worst
                        FROM trades
                        WHERE strategy = %s
                        AND trade_taken = true
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout', 'closed_external')
                        GROUP BY symbol
                        HAVING COUNT(*) >= 2  -- Mínimo 2 trades
                        ORDER BY total_pnl DESC
                        LIMIT 10
                    """, (self.strategy_name,))
                    top_symbols = cur.fetchall()
                    
                    # === MÉTRICAS DE RIESGO ===
                    cur.execute("""
                        SELECT 
                            ROUND(STDDEV(realized_pnl)::numeric, 2) as volatility,
                            ROUND(
                                CASE 
                                    WHEN STDDEV(realized_pnl) > 0 THEN 
                                        AVG(realized_pnl) / STDDEV(realized_pnl)
                                    ELSE 0 
                                END::numeric, 2
                            ) as sharpe_ratio,
                            ROUND(
                                SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END) / 
                                NULLIF(ABS(SUM(CASE WHEN realized_pnl < 0 THEN realized_pnl ELSE 0 END)), 0)::numeric, 2
                            ) as profit_factor
                        FROM trades
                        WHERE strategy = %s
                        AND trade_taken = true
                        AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout', 'closed_external')
                    """, (self.strategy_name,))
                    risk_metrics = cur.fetchone()
                    
                    # === ACTIVITY TRACKING ===
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_analysis,
                            COUNT(*) FILTER (WHERE trade_taken = true) as executed,
                            COUNT(*) FILTER (WHERE trade_taken = false) as rejected,
                            ROUND(COUNT(*) FILTER (WHERE trade_taken = true) * 100.0 / NULLIF(COUNT(*), 0), 1) as execution_rate
                        FROM trade_analysis
                        WHERE strategy = %s
                        AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    """, (self.strategy_name,))
                    activity_stats = cur.fetchone()
                    
                    # === API USAGE ===
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_api_calls,
                            COUNT(DISTINCT DATE(timestamp)) as active_days,
                            ROUND(AVG(symbols_count)::numeric, 1) as avg_symbols_per_call,
                            source,
                            COUNT(*) as calls_by_source
                        FROM api_invocations
                        WHERE strategy_name = %s
                        AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY source
                        ORDER BY calls_by_source DESC
                    """, (self.strategy_name,))
                    api_usage = cur.fetchall()
                    
                    return {
                        'overall_stats': dict(overall_stats) if overall_stats else {},
                        'today_stats': dict(today_stats) if today_stats else {},
                        'last_7_days': [dict(row) for row in last_7_days],
                        'monthly_performance': [dict(row) for row in monthly_performance],
                        'top_symbols': [dict(row) for row in top_symbols],
                        'risk_metrics': dict(risk_metrics) if risk_metrics else {},
                        'activity_stats': dict(activity_stats) if activity_stats else {},
                        'api_usage': [dict(row) for row in api_usage]
                    }
                    
        except Exception as e:
            logger.error(f"Error getting comprehensive analytics: {e}")
            return {}
    
    def get_month_by_month_breakdown(self, months: int = 6) -> List[dict]:
        """Obtener breakdown detallado mes por mes"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        WITH daily_stats AS (
                            SELECT 
                                date,
                                COUNT(*) as trades,
                                COUNT(*) FILTER (WHERE realized_pnl > 0) as winners,
                                SUM(realized_pnl) as daily_pnl
                            FROM trades
                            WHERE strategy = %s
                            AND trade_taken = true
                            AND date >= CURRENT_DATE - INTERVAL '%s months'
                            AND status IN ('stopped', 'target_hit', 'closed_time', 'timeout', 'closed_external')
                            GROUP BY date
                        )
                        SELECT 
                            TO_CHAR(date, 'YYYY-MM') as month,
                            TO_CHAR(date, 'Month YYYY') as month_name,
                            COUNT(*) as trading_days,
                            SUM(trades) as total_trades,
                            SUM(winners) as total_winners,
                            ROUND(SUM(winners) * 100.0 / NULLIF(SUM(trades), 0), 1) as win_rate,
                            ROUND(SUM(daily_pnl)::numeric, 2) as monthly_pnl,
                            ROUND(AVG(daily_pnl)::numeric, 2) as avg_daily_pnl,
                            ROUND(MAX(daily_pnl)::numeric, 2) as best_day,
                            ROUND(MIN(daily_pnl)::numeric, 2) as worst_day,
                            COUNT(*) FILTER (WHERE daily_pnl > 0) as profitable_days,
                            COUNT(*) FILTER (WHERE daily_pnl <= 0) as losing_days
                        FROM daily_stats
                        GROUP BY TO_CHAR(date, 'YYYY-MM'), TO_CHAR(date, 'Month YYYY')
                        ORDER BY month DESC
                    """, (self.strategy_name, months))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting month breakdown: {e}")
            return []
    
    def close(self):
        """Cerrar conexión a PostgreSQL"""
        self.connected = False
        logger.info("PostgreSQLStorage connection closed")