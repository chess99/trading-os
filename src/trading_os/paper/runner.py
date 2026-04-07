"""Paper trading runner — simulates live trading using historical daily bars.

Key design decisions:
- Day-level only (no intraday). Consistent with backtest execution model.
- Mark-to-market uses yesterday's close (no live price dependency).
- Risk checks run BEFORE every order (same as backtest).
- All events are written to EventLog for audit.
- confirm_mode='confirm' shows signals and waits for user approval.
- confirm_mode='auto' executes without confirmation (--bypass-confirm).

Execution model (same as BacktestRunner):
    Day T-1 close → DataPipeline.get_bars(trading_date=T)
    Strategy.generate_signals(bars, T)
    RiskManager.check_signal(signal, portfolio, prices)
    BacktestBroker.execute(order, portfolio, open_price=T_open, prev_close=T-1_close)
    Portfolio.update(fill)
    EventLog.write(fill)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ..backtest.runner import BacktestBroker, BacktestConfig, FillEvent, Portfolio, RiskRejectEvent
from ..journal.event_log import EventLog
from ..risk.manager import RiskConfig, RiskManager

if TYPE_CHECKING:
    from ..data.pipeline import DataPipeline
    from ..strategy.base import Strategy

log = logging.getLogger(__name__)


@dataclass
class PaperConfig:
    initial_cash: float = 1_000_000.0
    confirm_mode: Literal["confirm", "auto"] = "confirm"
    # Reuse backtest broker config for fees/slippage/A-share rules
    broker: BacktestConfig = field(default_factory=BacktestConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


@dataclass
class PaperSession:
    """Snapshot of a completed paper trading session."""
    start_date: date
    end_date: date
    initial_cash: float
    final_nav: float
    total_fills: int
    total_rejects: int
    log_path: Path

    @property
    def total_return(self) -> float:
        if self.initial_cash == 0:
            return 0.0
        return (self.final_nav - self.initial_cash) / self.initial_cash

    def summary(self) -> dict:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_cash": self.initial_cash,
            "final_nav": round(self.final_nav, 2),
            "total_return": f"{self.total_return:.2%}",
            "fills": self.total_fills,
            "rejects": self.total_rejects,
            "log": str(self.log_path),
        }


class PaperRunner:
    """Runs a strategy in paper trading mode over a date range.

    Identical execution model to BacktestRunner, but:
    - Uses EventLog for persistent audit trail
    - Supports confirm_mode (show signal, wait for user approval)
    - RiskManager integrated (same as live trading would be)

    Usage::

        runner = PaperRunner(
            strategy=MACrossStrategy(),
            pipeline=DataPipeline.from_repo_root(repo_root),
            config=PaperConfig(confirm_mode="auto"),
            event_log=EventLog.from_repo_root(repo_root),
        )
        session = runner.run(
            symbols=["SSE:600000"],
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
        )
        print(session.summary())
    """

    def __init__(
        self,
        strategy: "Strategy",
        pipeline: "DataPipeline",
        config: PaperConfig | None = None,
        event_log: EventLog | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self.strategy = strategy
        self.pipeline = pipeline
        self.config = config or PaperConfig()
        self._broker = BacktestBroker(self.config.broker)
        self._risk = RiskManager(self.config.risk)
        self._log = event_log or (
            EventLog.from_repo_root(repo_root) if repo_root else EventLog(Path("artifacts/paper.db"))
        )

    def run(
        self,
        symbols: list[str],
        start: date,
        end: date,
        lookback_days: int = 252,
    ) -> PaperSession:
        """Run paper trading over a date range.

        Same execution model as BacktestRunner.run().
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise RuntimeError("PaperRunner requires pandas") from e

        from ..backtest.runner import OrderEvent
        from ..data.schema import BarColumns
        from ..strategy.base import StrategyContext

        # Initialize
        context = StrategyContext(
            trading_date=start,
            symbols=symbols,
            initial_cash=self.config.initial_cash,
        )
        self.strategy.on_start(context)
        portfolio = Portfolio(cash=self.config.initial_cash)

        self._log.write("SESSION_START", {
            "symbols": symbols,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "initial_cash": self.config.initial_cash,
            "confirm_mode": self.config.confirm_mode,
        })

        fills_count = 0
        rejects_count = 0
        equity_history: list[float] = []

        # Get all bars for the full period (for trading date enumeration)
        all_bars = self.pipeline.get_bars(
            symbols=symbols,
            trading_date=end,
            lookback_days=(end - start).days + lookback_days + 30,
        )

        if all_bars is None or all_bars.empty:
            log.warning("No bars found for paper trading period %s–%s", start, end)
            self._log.write("SESSION_END", {"reason": "no_data", "final_nav": self.config.initial_cash})
            return PaperSession(
                start_date=start,
                end_date=end,
                initial_cash=self.config.initial_cash,
                final_nav=self.config.initial_cash,
                total_fills=0,
                total_rejects=0,
                log_path=self._log.path,
            )

        all_bars[BarColumns.ts] = pd.to_datetime(all_bars[BarColumns.ts], utc=True)
        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")

        trading_dates = sorted(
            all_bars[
                (all_bars[BarColumns.ts] >= start_ts) &
                (all_bars[BarColumns.ts] <= end_ts)
            ][BarColumns.ts].dt.normalize().unique()
        )

        final_nav = self.config.initial_cash

        for ts in trading_dates:
            trading_date = ts.date()

            # Bars available for signal generation
            hist_bars = self.pipeline.get_bars(
                symbols=symbols,
                trading_date=trading_date,
                lookback_days=lookback_days,
            )
            if hist_bars is None or hist_bars.empty:
                continue

            # Today's bars for execution prices
            today_bars = all_bars[all_bars[BarColumns.ts].dt.normalize() == ts]

            open_prices: dict[str, float] = {
                row[BarColumns.symbol]: float(row[BarColumns.open])
                for _, row in today_bars.iterrows()
            }
            close_prices: dict[str, float] = {
                row[BarColumns.symbol]: float(row[BarColumns.close])
                for _, row in today_bars.iterrows()
            }
            prev_close_prices: dict[str, float] = {
                sym: float(grp[BarColumns.close].iloc[-1])
                for sym, grp in hist_bars.groupby(BarColumns.symbol)
            }

            current_nav = portfolio.mark_to_market(open_prices)
            self._risk.start_of_day(trading_date, current_nav)

            # Generate signals
            try:
                signals = self.strategy.generate_signals(hist_bars, trading_date)
            except Exception as e:
                log.error("Strategy error on %s: %s", trading_date, e)
                self._log.write("STRATEGY_ERROR", {"date": trading_date.isoformat(), "error": str(e)})
                signals = {}

            # Log signals
            for sym, signal in signals.items():
                if signal.action != "HOLD":
                    self._log.write("SIGNAL", {
                        "date": trading_date.isoformat(),
                        "symbol": sym,
                        "action": signal.action,
                        "size": signal.size,
                        "reason": signal.reason,
                        "confidence": signal.confidence,
                    })

            # Confirm mode: show signals and wait for approval
            if self.config.confirm_mode == "confirm" and signals:
                non_hold = {s: sig for s, sig in signals.items() if sig.action != "HOLD"}
                if non_hold:
                    self._print_signals(trading_date, non_hold, portfolio, open_prices)
                    approved = self._prompt_confirm()
                    if not approved:
                        log.info("User rejected signals for %s", trading_date)
                        continue

            # Process signals → orders → fills
            for sym in sorted(signals.keys()):
                signal = signals[sym]

                if signal.valid_until is not None and signal.valid_until < trading_date:
                    self._log.write("SIGNAL_EXPIRED", {
                        "date": trading_date.isoformat(),
                        "symbol": sym,
                        "valid_until": signal.valid_until.isoformat(),
                    })
                    continue

                if signal.action == "HOLD":
                    continue

                open_px = open_prices.get(sym)
                prev_close = prev_close_prices.get(sym)
                if open_px is None or prev_close is None or open_px <= 0:
                    continue

                # Risk check
                risk_decision = self._risk.check_signal(
                    signal, portfolio, open_prices, equity_history
                )
                if not risk_decision.approved:
                    rejects_count += 1
                    self._log.write("RISK_REJECT", {
                        "date": trading_date.isoformat(),
                        "symbol": sym,
                        "check": risk_decision.check_name,
                        "reason": risk_decision.reason,
                    })
                    log.debug("Risk rejected %s on %s: %s", sym, trading_date, risk_decision.reason)
                    continue

                # Compute order size
                target_value = signal.size * current_nav
                current_pos = portfolio.positions.get(sym)
                current_shares = current_pos.shares if current_pos else 0.0

                if signal.action == "BUY":
                    current_value = current_shares * open_px
                    delta_value = target_value - current_value
                    if delta_value <= 0:
                        continue
                    shares = delta_value / open_px
                    order = OrderEvent(trading_date, sym, "BUY", shares, signal.reason)
                else:
                    target_shares = target_value / open_px if open_px > 0 else 0.0
                    shares_to_sell = current_shares - target_shares
                    if shares_to_sell <= 0:
                        continue
                    order = OrderEvent(trading_date, sym, "SELL", shares_to_sell, signal.reason)

                self._log.write("ORDER", {
                    "date": trading_date.isoformat(),
                    "symbol": sym,
                    "side": order.side,
                    "shares": order.shares,
                    "reason": order.reason,
                })

                result = self._broker.execute(
                    order=order,
                    portfolio=portfolio,
                    open_price=open_px,
                    prev_close=prev_close,
                )

                if isinstance(result, FillEvent):
                    portfolio.apply_fill(result)
                    self.strategy.on_fill(result)
                    fills_count += 1
                    self._log.write("FILL", {
                        "date": trading_date.isoformat(),
                        "symbol": result.symbol,
                        "side": result.side,
                        "shares": result.shares,
                        "price": result.price,
                        "commission": result.commission,
                        "stamp_duty": result.stamp_duty,
                        "net_cash": result.total_cost,
                    })
                elif isinstance(result, RiskRejectEvent):
                    rejects_count += 1
                    self._log.write("RISK_REJECT", {
                        "date": trading_date.isoformat(),
                        "symbol": result.symbol,
                        "check": "broker",
                        "reason": result.reason,
                    })

            # End of day: mark-to-market with close prices
            final_nav = portfolio.mark_to_market(close_prices)
            equity_history.append(final_nav)

        self._log.write("SESSION_END", {
            "final_nav": final_nav,
            "fills": fills_count,
            "rejects": rejects_count,
        })

        return PaperSession(
            start_date=start,
            end_date=end,
            initial_cash=self.config.initial_cash,
            final_nav=final_nav,
            total_fills=fills_count,
            total_rejects=rejects_count,
            log_path=self._log.path,
        )

    def _print_signals(
        self,
        trading_date: date,
        signals: dict,
        portfolio: Portfolio,
        prices: dict[str, float],
    ) -> None:
        nav = portfolio.mark_to_market(prices)
        print(f"\n{'='*60}")
        print(f"  Paper Trading Signals — {trading_date}")
        print(f"  Current NAV: {nav:,.2f} CNY")
        print(f"{'='*60}")
        for sym, sig in sorted(signals.items()):
            target_value = sig.size * nav
            print(f"  {sig.action:4s}  {sym:20s}  size={sig.size:.1%}  "
                  f"target={target_value:,.0f} CNY  reason={sig.reason}")
        print(f"{'='*60}")

    def _prompt_confirm(self) -> bool:
        try:
            ans = input("Execute these signals? [y/N] ").strip().lower()
            return ans in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
