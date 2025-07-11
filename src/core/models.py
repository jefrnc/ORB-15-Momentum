"""
Data models for trading system
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Trade:
    """Trade data model"""
    id: Optional[int] = None
    symbol: str = ""
    date: datetime = None
    order_time: datetime = None
    entry_order_id: int = 0
    stop_order_id: int = 0
    target_order_id: int = 0
    entry_price: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0
    shares: int = 0
    risk_amount: float = 0.0
    status: str = "pending"
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    exit_price: float = 0.0
    pnl: float = 0.0
    gap_percent: float = 0.0
    lod: float = 0.0
    volume_premarket: int = 0
    notes: str = ""
    system_tag: str = "IBKR_AUTO"

    def __post_init__(self):
        """Initialize default values"""
        if self.date is None:
            self.date = datetime.now()
        if self.order_time is None:
            self.order_time = datetime.now()


@dataclass
class TradingSession:
    """Trading session data model"""
    date: datetime
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    status: str = "active"

    def __post_init__(self):
        """Initialize default values"""
        if self.date is None:
            self.date = datetime.now()