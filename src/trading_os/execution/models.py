from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    NEW = "NEW"
    REJECTED = "REJECTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    ts: datetime
    symbol: str  # EXCHANGE:TICKER
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    qty: float = 0.0
    reason: str | None = None  # used when rejected


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: str
    ts: datetime
    symbol: str
    side: OrderSide
    qty: float
    price: float
    fee: float
    slippage_bps: float


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    qty: float
    avg_price: float
    entry_ts: datetime | None = None

    def market_value(self, last_price: float) -> float:
        return self.qty * last_price


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    ts: datetime
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    equity: float = 0.0

