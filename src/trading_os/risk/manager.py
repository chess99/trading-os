from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ..execution.models import Order, OrderSide
from ..execution.portfolio import Portfolio


@dataclass(frozen=True, slots=True)
class RiskConfig:
    max_gross_exposure_pct: float = 1.0  # 1.0 == 100% equity
    max_position_pct: float = 1.0  # per symbol
    cooldown_bars: int = 0  # after a trade, wait N bars before trading same symbol again
    stop_loss_pct: float | None = None  # e.g. 0.1 for 10% stop
    max_daily_loss_pct: float | None = None  # e.g. 0.03 for 3% intraday max loss
    circuit_breaker_drawdown_pct: float | None = None  # e.g. 0.1 for 10% peak-to-valley


@dataclass(frozen=True, slots=True)
class RiskVerdict:
    allowed: bool
    reason: str | None = None


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config
        self._cooldown_until: dict[str, int] = {}
        self._halt_trading: bool = False
        self._halt_reason: str | None = None
        self._peak_equity: float | None = None
        self._day: date | None = None
        self._day_start_equity: float | None = None

    def notify_trade(self, symbol: str, bar_index: int) -> None:
        if self.config.cooldown_bars > 0:
            self._cooldown_until[symbol] = bar_index + self.config.cooldown_bars

    def update_bar(self, ts: datetime, *, equity: float) -> None:
        """Update internal risk state on each bar (for circuit breakers / daily loss)."""
        if equity <= 0:
            return

        d = ts.date()
        if self._day != d:
            self._day = d
            self._day_start_equity = equity

        if self._peak_equity is None or equity > self._peak_equity:
            self._peak_equity = equity

        # max daily loss
        if self.config.max_daily_loss_pct is not None and self._day_start_equity:
            thr = float(self.config.max_daily_loss_pct)
            if thr > 0 and equity <= self._day_start_equity * (1.0 - thr):
                self._halt_trading = True
                self._halt_reason = (
                    f"max_daily_loss_triggered day_start={self._day_start_equity:.2f} "
                    f"equity={equity:.2f}"
                )

        # circuit breaker drawdown from peak equity
        if self.config.circuit_breaker_drawdown_pct is not None and self._peak_equity:
            thr = float(self.config.circuit_breaker_drawdown_pct)
            if thr > 0 and equity <= self._peak_equity * (1.0 - thr):
                self._halt_trading = True
                self._halt_reason = (
                    f"circuit_breaker_triggered peak={self._peak_equity:.2f} equity={equity:.2f}"
                )

    @property
    def halted(self) -> bool:
        return self._halt_trading

    @property
    def halt_reason(self) -> str | None:
        return self._halt_reason

    def check_order(
        self,
        order: Order,
        *,
        portfolio: Portfolio,
        prices: dict[str, float],
        bar_index: int,
    ) -> RiskVerdict:
        if self._halt_trading:
            return RiskVerdict(False, self._halt_reason or "trading_halted")
        # cooldown
        until = self._cooldown_until.get(order.symbol)
        if until is not None and bar_index < until:
            return RiskVerdict(False, f"cooldown_active_until={until}")

        equity = portfolio.equity(prices)
        if equity <= 0:
            return RiskVerdict(False, "equity_non_positive")

        px = float(prices.get(order.symbol, 0.0))
        if px <= 0:
            return RiskVerdict(False, "missing_price")

        # estimate post-trade exposure (market order)
        pos = portfolio.position(order.symbol)
        cur_qty = 0.0 if pos is None else float(pos.qty)
        tgt_qty = cur_qty + (order.qty if order.side == OrderSide.BUY else -order.qty)
        tgt_qty = max(0.0, tgt_qty)
        tgt_val = tgt_qty * px

        max_pos_val = float(self.config.max_position_pct) * equity
        if tgt_val > max_pos_val + 1e-9:
            return RiskVerdict(
                False, f"max_position_exceeded tgt={tgt_val:.2f} max={max_pos_val:.2f}"
            )

        # gross exposure (sum of position values)
        gross = 0.0
        for sym, p in portfolio.positions.items():
            gross += float(prices.get(sym, 0.0)) * float(p.qty)
        # apply this order's delta
        delta = order.qty * px * (1.0 if order.side == OrderSide.BUY else -1.0)
        gross = max(0.0, gross + delta)
        max_gross = float(self.config.max_gross_exposure_pct) * equity
        if gross > max_gross + 1e-9:
            return RiskVerdict(
                False,
                f"max_gross_exposure_exceeded gross={gross:.2f} max={max_gross:.2f}",
            )

        return RiskVerdict(True, None)

    def check_stop_loss(
        self,
        *,
        portfolio: Portfolio,
        prices: dict[str, float],
        ts: datetime,
    ) -> list[str]:
        """Return list of symbols that should be force-closed due to stop-loss."""
        if self.config.stop_loss_pct is None:
            return []
        sl = float(self.config.stop_loss_pct)
        if sl <= 0:
            return []

        to_close: list[str] = []
        for sym, pos in portfolio.positions.items():
            px = float(prices.get(sym, 0.0))
            if px <= 0:
                continue
            if pos.avg_price <= 0:
                continue
            if px <= pos.avg_price * (1.0 - sl):
                to_close.append(sym)
        _ = ts
        return to_close

