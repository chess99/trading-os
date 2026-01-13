from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd_types

from ..data.schema import BarColumns
from ..journal.event_log import EventLog
from ..risk.manager import RiskManager
from .models import Fill, Order, OrderSide, OrderStatus
from .portfolio import Portfolio


SignalsFn = Callable[["pd_types.DataFrame"], "pd_types.Series"]


@dataclass(frozen=True, slots=True)
class PaperEngineConfig:
    initial_cash: float = 100_000.0
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    allow_fractional_shares: bool = True


def _require_pandas() -> None:
    if pd is None:  # pragma: no cover
        raise RuntimeError(
            "PaperTradingEngine requires pandas. Install optional deps in Python 3.10–3.12: "
            "`pip install -e .[data_lake]`"
        )


class PaperTradingEngine:
    """A simple daily-bar paper trading engine.

    Execution model:
    - Strategy produces signals on close of bar t.
    - Orders execute on open of bar t+1.
    """

    def __init__(self, *, config: PaperEngineConfig, risk: RiskManager, event_log: EventLog):
        self.config = config
        self.risk = risk
        self.log = event_log

    def run_single_symbol(
        self,
        bars: "pd_types.DataFrame",
        *,
        signals_fn: SignalsFn,
    ) -> "pd_types.DataFrame":
        _require_pandas()
        if bars is None or bars.empty:
            raise ValueError("bars is empty")
        bars = bars.sort_values(BarColumns.ts).reset_index(drop=True).copy()
        symbol = str(bars[BarColumns.symbol].iloc[0])
        if (bars[BarColumns.symbol] != symbol).any():
            raise ValueError("run_single_symbol supports single symbol only")

        sig = signals_fn(bars).astype(float).clip(lower=0.0, upper=1.0)
        target_pos = sig.shift(1).fillna(0.0)

        portfolio = Portfolio.with_cash(self.config.initial_cash)
        fee = self.config.fee_bps / 10_000.0
        slip = self.config.slippage_bps / 10_000.0

        rows = []
        last_target = 0.0

        for i in range(len(bars)):
            ts = bars[BarColumns.ts].iloc[i]
            px_open = float(bars[BarColumns.open].iloc[i])
            px_close = float(bars[BarColumns.close].iloc[i])

            prices = {symbol: px_open}
            # update circuit breakers based on current portfolio equity (use open price)
            self.risk.update_bar(ts, equity=portfolio.equity(prices))
            if self.risk.halted:
                self.log.write_obj("risk_halt", {"reason": self.risk.halt_reason}, ts=ts)

            # stop-loss (checked on open price for MVP)
            to_close = self.risk.check_stop_loss(portfolio=portfolio, prices=prices, ts=ts)
            if symbol in to_close and portfolio.position(symbol) is not None:
                last_target = 0.0

            tgt = float(target_pos.iloc[i])
            tgt = 1.0 if tgt >= 0.5 else 0.0

            # desired change?
            if tgt != last_target:
                order_side = OrderSide.BUY if tgt > last_target else OrderSide.SELL
                # all-in/all-out sizing
                pos = portfolio.position(symbol)
                cur_qty = 0.0 if pos is None else float(pos.qty)
                if order_side == OrderSide.BUY:
                    exec_px = px_open * (1.0 + slip)
                    budget = portfolio.cash
                    # buy with (1-fee) cash
                    qty = (budget * (1.0 - fee)) / exec_px if exec_px > 0 else 0.0
                    if not self.config.allow_fractional_shares:
                        qty = float(int(qty))
                else:
                    qty = cur_qty

                order = Order(
                    order_id=str(uuid.uuid4()),
                    ts=ts,
                    symbol=symbol,
                    side=order_side,
                    qty=float(max(0.0, qty)),
                )

                verdict = self.risk.check_order(order, portfolio=portfolio, prices=prices, bar_index=i)
                if not verdict.allowed:
                    self.log.write_obj("order_rejected", order, ts=ts, extra={"reason": verdict.reason})
                else:
                    # fill immediately at open (with slippage)
                    fill_px = px_open * (1.0 + slip) if order.side == OrderSide.BUY else px_open * (1.0 - slip)
                    fill_fee = order.qty * fill_px * fee
                    fill = Fill(
                        order_id=order.order_id,
                        ts=ts,
                        symbol=symbol,
                        side=order.side,
                        qty=order.qty,
                        price=float(fill_px),
                        fee=float(fill_fee),
                        slippage_bps=float(self.config.slippage_bps),
                    )
                    portfolio.apply_fill(fill)
                    self.risk.notify_trade(symbol, bar_index=i)
                    self.log.write_obj("order_filled", {"order": order.__dict__, "fill": fill.__dict__}, ts=ts)
                    last_target = tgt

            snap = portfolio.snapshot(ts=ts, prices={symbol: px_close})
            self.log.write_obj("portfolio", snap, ts=ts)
            rows.append(
                {
                    "ts": ts,
                    "symbol": symbol,
                    "signal": float(sig.iloc[i]),
                    "target_pos": float(last_target),
                    "cash": snap.cash,
                    "equity": snap.equity,
                }
            )

        return pd.DataFrame(rows)  # type: ignore[union-attr]

