"""Quantitative risk manager — the hard gate before any order executes.

This is NOT an LLM component. It enforces hard limits using math,
not language. An AI strategy cannot bypass these checks.

Checks performed (in order):
    1. Single-stock position limit (default 10% of NAV)
    2. Sector concentration limit (default 30% of NAV)
    3. Daily loss circuit breaker (default -5% from day-start NAV)
    4. Portfolio VaR limit (default 2% daily 95% VaR)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..backtest.runner import Portfolio
    from ..strategy.base import Signal

log = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    # Single-stock position limit as fraction of NAV
    max_position_pct: float = 0.10       # 10%
    # Sector concentration limit as fraction of NAV
    max_sector_pct: float = 0.30         # 30%
    # Daily loss circuit breaker: halt all trading if day P&L < threshold
    daily_loss_limit_pct: float = -0.05  # -5%
    # VaR limit: reject signal if portfolio 1-day 95% VaR exceeds this
    var_limit_pct: float = 0.02          # 2%
    # Minimum lookback bars for VaR calculation
    var_lookback: int = 60


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    check_name: str = ""

    @classmethod
    def approve(cls) -> "RiskDecision":
        return cls(approved=True, reason="")

    @classmethod
    def reject(cls, check: str, reason: str) -> "RiskDecision":
        return cls(approved=False, reason=reason, check_name=check)


# Sector mapping for A-share stocks (simplified)
_A_SHARE_SECTOR_PREFIXES: dict[str, str] = {
    "600": "上证主板",
    "601": "上证金融",
    "603": "上证主板",
    "605": "上证主板",
    "000": "深证主板",
    "001": "深证主板",
    "002": "中小板",
    "003": "深证主板",
    "300": "创业板",
    "301": "创业板",
    "688": "科创板",
    "689": "科创板",
}


def _get_sector(symbol: str) -> str:
    """Simple sector classification by ticker prefix."""
    ticker = symbol.split(":")[-1] if ":" in symbol else symbol
    for prefix, sector in _A_SHARE_SECTOR_PREFIXES.items():
        if ticker.startswith(prefix):
            return sector
    return "其他"


class RiskManager:
    """Enforces hard risk limits on trading signals.

    Usage::

        risk = RiskManager(RiskConfig(max_position_pct=0.10))
        decision = risk.check_signal(signal, portfolio, current_prices)
        if decision.approved:
            broker.execute(order)
        else:
            log.warning("Risk rejected: %s", decision.reason)
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self._day_start_nav: float | None = None
        self._current_date: date | None = None

    def start_of_day(self, trading_date: date, nav: float) -> None:
        """Call at the start of each trading day to reset daily trackers."""
        self._current_date = trading_date
        self._day_start_nav = nav

    def check_signal(
        self,
        signal: "Signal",
        portfolio: "Portfolio",
        current_prices: dict[str, float],
        equity_history: list[float] | None = None,
    ) -> RiskDecision:
        """Check a signal against all risk limits.

        Returns RiskDecision with approved=True or approved=False + reason.
        """
        if signal.action == "HOLD":
            return RiskDecision.approve()

        current_nav = portfolio.mark_to_market(current_prices)
        if current_nav <= 0:
            return RiskDecision.reject("nav", "组合净值为零或负数")

        # 1. Single-stock position limit
        decision = self._check_position_limit(signal, current_nav)
        if not decision.approved:
            return decision

        # 2. Sector concentration limit
        decision = self._check_sector_limit(signal, portfolio, current_prices, current_nav)
        if not decision.approved:
            return decision

        # 3. Daily loss circuit breaker
        decision = self._check_daily_loss(current_nav)
        if not decision.approved:
            return decision

        # 4. VaR limit (only if equity history provided and long enough)
        if equity_history and len(equity_history) >= self.config.var_lookback:
            decision = self._check_var(equity_history)
            if not decision.approved:
                return decision

        return RiskDecision.approve()

    def _check_position_limit(self, signal: "Signal", nav: float) -> RiskDecision:
        if signal.action != "BUY":
            return RiskDecision.approve()
        if signal.size > self.config.max_position_pct:
            return RiskDecision.reject(
                "position_limit",
                f"{signal.symbol} 目标仓位 {signal.size:.1%} 超过单股上限 {self.config.max_position_pct:.1%}",
            )
        return RiskDecision.approve()

    def _check_sector_limit(
        self,
        signal: "Signal",
        portfolio: "Portfolio",
        prices: dict[str, float],
        nav: float,
    ) -> RiskDecision:
        if signal.action != "BUY":
            return RiskDecision.approve()

        target_sector = _get_sector(signal.symbol)
        sector_value = sum(
            pos.shares * prices.get(sym, pos.avg_cost)
            for sym, pos in portfolio.positions.items()
            if _get_sector(sym) == target_sector
        )
        total_after = sector_value + signal.size * nav
        sector_pct = total_after / nav

        if sector_pct > self.config.max_sector_pct:
            return RiskDecision.reject(
                "sector_limit",
                f"{target_sector} 板块集中度 {sector_pct:.1%} 将超过上限 {self.config.max_sector_pct:.1%}",
            )
        return RiskDecision.approve()

    def _check_daily_loss(self, current_nav: float) -> RiskDecision:
        if self._day_start_nav is None or self._day_start_nav <= 0:
            return RiskDecision.approve()
        daily_pnl_pct = (current_nav - self._day_start_nav) / self._day_start_nav
        if daily_pnl_pct < self.config.daily_loss_limit_pct:
            return RiskDecision.reject(
                "circuit_breaker",
                f"日亏损 {daily_pnl_pct:.1%} 触发熔断（上限 {self.config.daily_loss_limit_pct:.1%}）",
            )
        return RiskDecision.approve()

    def _check_var(self, equity_history: list[float]) -> RiskDecision:
        """Simple historical VaR at 95% confidence."""
        if len(equity_history) < 2:
            return RiskDecision.approve()
        returns = [
            (equity_history[i] - equity_history[i - 1]) / equity_history[i - 1]
            for i in range(1, len(equity_history))
        ]
        lookback = min(self.config.var_lookback, len(returns))
        recent = sorted(returns[-lookback:])
        idx = max(0, int(len(recent) * 0.05) - 1)
        var_1d = abs(recent[idx])
        if var_1d > self.config.var_limit_pct:
            return RiskDecision.reject(
                "var_limit",
                f"1日95% VaR {var_1d:.1%} 超过上限 {self.config.var_limit_pct:.1%}",
            )
        return RiskDecision.approve()
