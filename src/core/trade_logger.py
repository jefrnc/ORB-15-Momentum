#!/usr/bin/env python3
"""
Sistema de logging avanzado para el trading system
- Logs detallados diarios con append mode
- Tracking de posiciones en JSON por día
- Métricas completas para análisis de estrategia
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class TradeAction(Enum):
    REQUESTED = "requested"
    REJECTED = "rejected" 
    QUEUED = "queued"
    EXECUTED = "executed"
    FILLED = "filled"
    STOPPED = "stopped"
    TARGET_HIT = "target_hit"
    TIMEOUT = "timeout"
    CLOSED_TIME = "closed_time"
    CLOSED_MANUAL = "closed_manual"
    CLOSED_EXTERNAL = "closed_external"
    POSITION_SYNC = "position_sync"
    POSITION_IMPORTED = "position_imported"
    TIMEZONE_FIX = "timezone_fix"

class RejectionReason(Enum):
    ALREADY_HAVE_POSITION = "already_have_position"
    MAX_POSITIONS_REACHED = "max_positions_reached"
    NO_MARKET_DATA = "no_market_data"
    INVALID_SETUP = "invalid_setup"
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    RED_PREVIOUS_DAY = "red_previous_day"
    LOW_MARKET_CAP = "low_market_cap"
    CALCULATION_ERROR = "calculation_error"
    ORDER_PLACEMENT_FAILED = "order_placement_failed"

@dataclass
class TradeEvent:
    timestamp: str
    symbol: str
    action: TradeAction
    price: Optional[float] = None
    shares: Optional[int] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    entry_order_id: Optional[int] = None
    queue_type: Optional[str] = None
    stop_order_id: Optional[int] = None
    target_order_id: Optional[int] = None
    rejection_reason: Optional[RejectionReason] = None
    rejection_details: Optional[str] = None
    source: Optional[str] = None
    alert_type: Optional[str] = None
    alert_time: Optional[str] = None
    market_data: Optional[Dict] = None
    pnl: Optional[float] = None
    notes: Optional[str] = None

class TradeLogger:
    def __init__(self, base_dir: str = "logs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        self.today = datetime.now().strftime("%Y-%m-%d")
        
        # Setup detailed logger
        self._setup_detailed_logger()
        
        # Daily events for memory only (not saved to JSON)
        self.daily_events: List[TradeEvent] = []
    
    def _setup_detailed_logger(self):
        """Setup detailed daily logger with append mode"""
        log_file = self.base_dir / f"detailed_trading_{self.today}.log"
        
        # Create detailed logger
        self.detailed_logger = logging.getLogger('detailed_trading')
        self.detailed_logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.detailed_logger.handlers[:]:
            self.detailed_logger.removeHandler(handler)
        
        # File handler with append mode
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.detailed_logger.addHandler(file_handler)
        
        # Don't propagate to root logger
        self.detailed_logger.propagate = False
        
        # Log session start
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info("🚀 TRADING SESSION STARTED")
        self.detailed_logger.info("=" * 80)
    
    def _load_daily_positions(self):
        """DISABLED: Position management moved to ClickHouse completely"""
        # No longer loading positions from JSON - all position data comes from ClickHouse
        self.daily_events = []
    
    def _save_daily_positions(self):
        """DISABLED: Position management moved to ClickHouse completely"""
        # Position events no longer saved to JSON - all position data goes to ClickHouse
        # Only keeping logs for debugging, but position management is 100% ClickHouse
        pass
    
    def _generate_daily_summary(self) -> Dict:
        """Generate daily summary statistics"""
        summary = {
            'total_requested': 0,
            'total_rejected': 0,
            'total_executed': 0,
            'total_filled': 0,
            'total_stopped': 0,
            'total_target_hit': 0,
            'total_timeout': 0,
            'total_closed_time': 0,
            'total_closed_manual': 0,
            'total_closed_external': 0,
            'rejection_reasons': {},
            'sources': {},
            'alert_types': {},
            'symbols_requested': set(),
            'symbols_executed': set(),
            'symbols_filled': set()
        }
        
        for event in self.daily_events:
            action = event.action
            
            if action == TradeAction.REQUESTED:
                summary['total_requested'] += 1
                summary['symbols_requested'].add(event.symbol)
                
                if event.source:
                    summary['sources'][event.source] = summary['sources'].get(event.source, 0) + 1
                if event.alert_type:
                    summary['alert_types'][event.alert_type] = summary['alert_types'].get(event.alert_type, 0) + 1
                    
            elif action == TradeAction.REJECTED:
                summary['total_rejected'] += 1
                if event.rejection_reason:
                    reason = event.rejection_reason.value
                    summary['rejection_reasons'][reason] = summary['rejection_reasons'].get(reason, 0) + 1
                    
            elif action == TradeAction.EXECUTED:
                summary['total_executed'] += 1
                summary['symbols_executed'].add(event.symbol)
                
            elif action == TradeAction.FILLED:
                summary['total_filled'] += 1
                summary['symbols_filled'].add(event.symbol)
                
            elif action == TradeAction.STOPPED:
                summary['total_stopped'] += 1
            elif action == TradeAction.TARGET_HIT:
                summary['total_target_hit'] += 1
            elif action == TradeAction.TIMEOUT:
                summary['total_timeout'] += 1
            elif action == TradeAction.CLOSED_TIME:
                summary['total_closed_time'] += 1
            elif action == TradeAction.CLOSED_MANUAL:
                summary['total_closed_manual'] += 1
            elif action == TradeAction.CLOSED_EXTERNAL:
                summary['total_closed_external'] += 1
        
        # Convert sets to lists for JSON serialization
        summary['symbols_requested'] = list(summary['symbols_requested'])
        summary['symbols_executed'] = list(summary['symbols_executed'])
        summary['symbols_filled'] = list(summary['symbols_filled'])
        
        return summary
    
    def log_trade_requested(self, symbol: str, source: str = None, alert_type: str = None, alert_time: str = None, market_data: Dict = None):
        """Log when a trade is requested"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=TradeAction.REQUESTED,
            source=source,
            alert_type=alert_type,
            alert_time=alert_time,
            market_data=market_data
        )
        
        self.daily_events.append(event)
        
        log_msg = f"📋 TRADE REQUESTED: {symbol}"
        if source:
            log_msg += f" | Source: {source}"
        if alert_type:
            log_msg += f" | Alert: {alert_type}"
        if alert_time:
            log_msg += f" | Time: {alert_time}"
        if market_data:
            log_msg += f" | Price: ${market_data.get('last', 0):.2f}"
            log_msg += f" | Gap: {market_data.get('gap_percent', 0)*100:.1f}%"
            log_msg += f" | Volume: {market_data.get('volume', 0):,}"
            
        self.detailed_logger.info(log_msg)
# Position saving disabled - all data goes to ClickHouse
    
    def log_trade_rejected(self, symbol: str, reason: RejectionReason, details: str = None):
        """Log when a trade is rejected"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=TradeAction.REJECTED,
            rejection_reason=reason,
            rejection_details=details
        )
        
        self.daily_events.append(event)
        
        log_msg = f"❌ TRADE REJECTED: {symbol} | Reason: {reason.value}"
        if details:
            log_msg += f" | Details: {details}"
            
        self.detailed_logger.info(log_msg)
# Position saving disabled - all data goes to ClickHouse
    
    def log_trade_queued(self, symbol: str, price: float, shares: int, stop_price: float, target_price: float, queue_type: str = "PREMARKET"):
        """Log when a trade is queued for later execution"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=TradeAction.QUEUED,
            price=price,
            shares=shares,
            stop_price=stop_price,
            target_price=target_price,
            queue_type=queue_type
        )
        
        self.daily_events.append(event)
        
        log_msg = f"📋 TRADE QUEUED: {symbol} | Type: {queue_type} | Entry: ${price:.2f} | Shares: {shares} | Stop: ${stop_price:.2f} | Target: ${target_price:.2f}"
        self.detailed_logger.info(log_msg)
    
    def log_trade_executed(self, symbol: str, price: float, shares: int, stop_price: float, target_price: float, 
                         entry_order_id: int, stop_order_id: int, target_order_id: int):
        """Log when a trade is executed (bracket order placed)"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=TradeAction.EXECUTED,
            price=price,
            shares=shares,
            stop_price=stop_price,
            target_price=target_price,
            entry_order_id=entry_order_id,
            stop_order_id=stop_order_id,
            target_order_id=target_order_id
        )
        
        self.daily_events.append(event)
        
        risk_amount = shares * (price - stop_price)
        reward_amount = shares * (target_price - price)
        risk_reward = reward_amount / risk_amount if risk_amount > 0 else 0
        
        log_msg = (f"✅ TRADE EXECUTED: {symbol} | "
                  f"Entry: ${price:.2f} | Shares: {shares} | "
                  f"Stop: ${stop_price:.2f} (-{((price-stop_price)/price)*100:.1f}%) | "
                  f"Target: ${target_price:.2f} (+{((target_price-price)/price)*100:.1f}%) | "
                  f"Risk: ${risk_amount:.2f} | Reward: ${reward_amount:.2f} | "
                  f"R/R: 1:{risk_reward:.1f} | "
                  f"Orders: E#{entry_order_id}, S#{stop_order_id}, T#{target_order_id}")
        
        self.detailed_logger.info(log_msg)
# Position saving disabled - all data goes to ClickHouse
    
    def log_trade_filled(self, symbol: str, actual_price: float, shares: int):
        """Log when entry order is filled"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=TradeAction.FILLED,
            price=actual_price,
            shares=shares
        )
        
        self.daily_events.append(event)
        
        log_msg = f"🎯 POSITION FILLED: {symbol} | Actual Entry: ${actual_price:.2f} | Shares: {shares}"
        self.detailed_logger.info(log_msg)
# Position saving disabled - all data goes to ClickHouse
    
    def log_trade_exit(self, symbol: str, exit_action: TradeAction, exit_price: float, shares: int, pnl: float, notes: str = None):
        """Log when trade is closed (stop hit, target hit, timeout, manual close, etc.)"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=exit_action,
            price=exit_price,
            shares=shares,
            pnl=pnl,
            notes=notes
        )
        
        self.daily_events.append(event)
        
        action_names = {
            TradeAction.STOPPED: "🛑 STOP HIT",
            TradeAction.TARGET_HIT: "🎯 TARGET HIT", 
            TradeAction.TIMEOUT: "⏰ TIMEOUT",
            TradeAction.CLOSED_TIME: "🕐 CLOSED AT 13:30",
            TradeAction.CLOSED_MANUAL: "👤 MANUAL CLOSE",
            TradeAction.CLOSED_EXTERNAL: "🔄 CLOSED EXTERNAL"
        }
        
        action_name = action_names.get(exit_action, "❓ UNKNOWN EXIT")
        pnl_sign = "+" if pnl >= 0 else ""
        
        log_msg = (f"{action_name}: {symbol} | "
                  f"Exit: ${exit_price:.2f} | Shares: {shares} | "
                  f"P&L: {pnl_sign}${pnl:.2f}")
        
        if notes:
            log_msg += f" | Notes: {notes}"
            
        self.detailed_logger.info(log_msg)
# Position saving disabled - all data goes to ClickHouse
    
    def log_session_end(self):
        """Log session end with summary"""
        summary = self._generate_daily_summary()
        
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info("📊 DAILY TRADING SUMMARY")
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info(f"📋 Total Requested: {summary['total_requested']}")
        self.detailed_logger.info(f"❌ Total Rejected: {summary['total_rejected']}")
        self.detailed_logger.info(f"✅ Total Executed: {summary['total_executed']}")
        self.detailed_logger.info(f"🎯 Total Filled: {summary['total_filled']}")
        self.detailed_logger.info(f"🛑 Stop Hits: {summary['total_stopped']}")
        self.detailed_logger.info(f"🎯 Target Hits: {summary['total_target_hit']}")
        self.detailed_logger.info(f"⏰ Timeouts: {summary['total_timeout']}")
        self.detailed_logger.info(f"🕐 Time Closes: {summary['total_closed_time']}")
        self.detailed_logger.info(f"👤 Manual Closes: {summary['total_closed_manual']}")
        self.detailed_logger.info(f"🔄 External Closes: {summary['total_closed_external']}")
        
        if summary['rejection_reasons']:
            self.detailed_logger.info("❌ Rejection Reasons:")
            for reason, count in summary['rejection_reasons'].items():
                self.detailed_logger.info(f"   - {reason}: {count}")
        
        if summary['sources']:
            self.detailed_logger.info("📡 Sources:")
            for source, count in summary['sources'].items():
                self.detailed_logger.info(f"   - {source}: {count}")
        
        self.detailed_logger.info(f"📈 Symbols Requested: {len(summary['symbols_requested'])}")
        self.detailed_logger.info(f"🎯 Symbols Executed: {len(summary['symbols_executed'])}")
        self.detailed_logger.info(f"✅ Symbols Filled: {len(summary['symbols_filled'])}")
        
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info("👋 TRADING SESSION ENDED")
        self.detailed_logger.info("=" * 80)
        
# Position saving disabled - all data goes to ClickHouse
    
    def get_daily_summary(self) -> Dict:
        """Get current daily summary"""
        return self._generate_daily_summary()
    
    def get_symbol_history(self, symbol: str) -> List[TradeEvent]:
        """Get all events for a specific symbol today"""
        return [event for event in self.daily_events if event.symbol == symbol]
    
    # 🔧 NEW METHODS FOR ENHANCED LOGGING (Added 2025-06-30)
    
    def log_position_sync(self, sync_report: Dict):
        """Log position synchronization between tracker and IBKR"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol="SYSTEM",
            action=TradeAction.POSITION_SYNC,
            notes=f"Sync report: {len(sync_report.get('actions_needed', []))} actions needed"
        )
        
        self.daily_events.append(event)
        
        # Detailed sync logging
        self.detailed_logger.info("🔄 POSITION SYNC REPORT")
        self.detailed_logger.info("=" * 50)
        
        if sync_report.get('ibkr_only'):
            self.detailed_logger.info("📊 IBKR Only (need to add to tracker):")
            for symbol, pos in sync_report['ibkr_only'].items():
                self.detailed_logger.info(f"   + {symbol}: {pos['shares']} shares @ ${pos['avg_cost']:.2f}")
        
        if sync_report.get('tracker_only'):
            self.detailed_logger.info("📱 Tracker Only (closed externally):")
            for symbol, pos in sync_report['tracker_only'].items():
                self.detailed_logger.info(f"   - {symbol}: {pos['shares']} shares (remove from tracker)")
        
        if sync_report.get('mismatched'):
            self.detailed_logger.info("⚠️ Quantity Mismatches:")
            for symbol, data in sync_report['mismatched'].items():
                ibkr_qty = data['ibkr']['shares']
                tracker_qty = data['tracker']['shares']
                self.detailed_logger.info(f"   ≠ {symbol}: IBKR={ibkr_qty} vs Tracker={tracker_qty}")
        
        if sync_report.get('matched'):
            self.detailed_logger.info("✅ Matched Positions:")
            for symbol, pos in sync_report['matched'].items():
                self.detailed_logger.info(f"   ✓ {symbol}: {pos['shares']} shares @ ${pos['avg_cost']:.2f}")
        
        self.detailed_logger.info(f"🔧 Actions Needed: {len(sync_report.get('actions_needed', []))}")
        for action in sync_report.get('actions_needed', []):
            self.detailed_logger.info(f"   → {action}")
        
        self.detailed_logger.info("=" * 50)
    
    def log_timezone_fix(self, old_time: str, new_time: str, timezone_name: str):
        """Log timezone correction events"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol="SYSTEM",
            action=TradeAction.TIMEZONE_FIX,
            notes=f"Fixed: {old_time} → {new_time} ({timezone_name})"
        )
        
        self.daily_events.append(event)
        
        self.detailed_logger.info(f"🕐 TIMEZONE FIX: {old_time} → {new_time} using {timezone_name}")
    
    def log_position_imported(self, symbol: str, shares: int, avg_cost: float, source: str = "IBKR"):
        """Log when a position is imported from external source"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=TradeAction.POSITION_IMPORTED,
            shares=shares,
            price=avg_cost,
            notes=f"Imported from {source}"
        )
        
        self.daily_events.append(event)
        
        self.detailed_logger.info(f"📥 POSITION IMPORTED: {symbol} | {shares} shares @ ${avg_cost:.2f} | Source: {source}")
    
    def log_system_event(self, event_type: str, details: str, data: Dict = None):
        """Log general system events (startup, shutdown, errors, etc.)"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol="SYSTEM",
            action=TradeAction.REQUESTED,  # Using generic action for system events
            notes=f"{event_type}: {details}"
        )
        
        self.daily_events.append(event)
        
        log_msg = f"🔧 SYSTEM: {event_type} | {details}"
        if data:
            log_msg += f" | Data: {data}"
        
        self.detailed_logger.info(log_msg)
    
    def log_command_execution(self, command: str, args: List[str] = None, result: str = "SUCCESS", error: str = None):
        """Log console command executions for debugging"""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            symbol="COMMAND",
            action=TradeAction.EXECUTED,
            notes=f"Command: {command} {' '.join(args or [])} → {result}"
        )
        
        self.daily_events.append(event)
        
        log_msg = f"⌨️ COMMAND: {command}"
        if args:
            log_msg += f" {' '.join(args)}"
        log_msg += f" → {result}"
        if error:
            log_msg += f" | Error: {error}"
        
        self.detailed_logger.info(log_msg)