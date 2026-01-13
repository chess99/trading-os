from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import Fill, OrderSide, Position, PortfolioSnapshot


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, Position]

    @classmethod
    def with_cash(cls, cash: float) -> "Portfolio":
        return cls(cash=float(cash), positions={})

    def position(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)

    def equity(self, prices: dict[str, float]) -> float:
        eq = self.cash
        for sym, pos in self.positions.items():
            px = float(prices.get(sym, 0.0))
            eq += pos.market_value(px)
        return float(eq)

    def apply_fill(self, fill: Fill) -> None:
        """Update cash/positions for a fill."""
        sym = fill.symbol
        qty = float(fill.qty)
        px = float(fill.price)
        fee = float(fill.fee)

        if fill.side == OrderSide.BUY:
            cost = qty * px + fee
            self.cash -= cost
            prev = self.positions.get(sym)
            if prev is None or prev.qty == 0:
                self.positions[sym] = Position(symbol=sym, qty=qty, avg_price=px, entry_ts=fill.ts)
            else:
                new_qty = prev.qty + qty
                new_avg = (prev.avg_price * prev.qty + px * qty) / new_qty
                self.positions[sym] = Position(symbol=sym, qty=new_qty, avg_price=new_avg, entry_ts=prev.entry_ts)
        else:
            proceeds = qty * px - fee
            self.cash += proceeds
            prev = self.positions.get(sym)
            if prev is None:
                return
            new_qty = prev.qty - qty
            if new_qty <= 1e-12:
                self.positions.pop(sym, None)
            else:
                self.positions[sym] = Position(symbol=sym, qty=new_qty, avg_price=prev.avg_price, entry_ts=prev.entry_ts)

    def snapshot(self, ts: datetime, prices: dict[str, float]) -> PortfolioSnapshot:
        return PortfolioSnapshot(ts=ts, cash=float(self.cash), positions=dict(self.positions), equity=self.equity(prices))

