from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd_types

from ..data.schema import BarColumns


SignalsFn = Callable[["pd_types.DataFrame"], "pd_types.Series"]


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    fee_bps: float = 1.0  # per trade (round-trip is roughly 2x)
    slippage_bps: float = 2.0  # applied on execution price
    allow_fractional_shares: bool = True


@dataclass(frozen=True, slots=True)
class BacktestResult:
    symbol: str
    bars: "pd_types.DataFrame"
    signals: "pd_types.Series"
    trades: "pd_types.DataFrame"
    equity_curve: "pd_types.DataFrame"


def _require_pandas() -> None:
    if pd is None:  # pragma: no cover
        raise RuntimeError(
            "Backtest requires pandas. Install optional deps in Python 3.10–3.12: "
            "`pip install -e .[data_lake]`"
        )


def run_backtest(
    bars: "pd_types.DataFrame",
    *,
    signals_fn: SignalsFn,
    config: BacktestConfig,
) -> BacktestResult:
    """Run a minimal long-only backtest for a single symbol.

    Anti-lookahead rule:
    - Signals are computed using bar t close.
    - Orders execute at bar t+1 open (next bar open).

    Assumptions (MVP):
    - Long-only, all-in/all-out (position is either 0% or 100% of equity)
    - One symbol
    """
    _require_pandas()

    if bars is None or bars.empty:
        raise ValueError("bars is empty")
    if BarColumns.symbol not in bars.columns:
        raise ValueError(f"bars missing column: {BarColumns.symbol}")

    bars = bars.sort_values(BarColumns.ts).reset_index(drop=True).copy()
    symbol = str(bars[BarColumns.symbol].iloc[0])
    if (bars[BarColumns.symbol] != symbol).any():
        raise ValueError("run_backtest currently supports a single symbol only")

    # Compute signals on available bars (0/1 recommended)
    sig = signals_fn(bars).astype(float)
    sig = sig.clip(lower=0.0, upper=1.0)
    if len(sig) != len(bars):
        raise ValueError("signals_fn must return a series aligned with bars length")

    # execution price is next bar open; so we shift signals by 1
    target_pos = sig.shift(1).fillna(0.0)

    open_px = bars[BarColumns.open].astype(float)
    close_px = bars[BarColumns.close].astype(float)

    fee = config.fee_bps / 10_000.0
    slip = config.slippage_bps / 10_000.0

    cash = config.initial_cash
    shares = 0.0

    rows = []
    trade_rows = []
    last_target = 0.0

    for i in range(len(bars)):
        ts = bars[BarColumns.ts].iloc[i]
        px_exec = float(open_px.iloc[i])

        tgt = float(target_pos.iloc[i])
        if tgt not in (0.0, 1.0):
            # for MVP, we only support 0/1 toggles
            tgt = 1.0 if tgt >= 0.5 else 0.0

        if tgt != last_target:
            # close existing position
            if last_target > 0.0 and shares > 0.0:
                sell_px = px_exec * (1.0 - slip)
                proceeds = shares * sell_px
                cost = proceeds * fee
                cash += proceeds - cost
                trade_rows.append(
                    {"ts": ts, "side": "SELL", "price": sell_px, "shares": shares, "fee": cost}
                )
                shares = 0.0

            # open new position
            if tgt > 0.0:
                buy_px = px_exec * (1.0 + slip)
                budget = cash
                cost_est = budget * fee
                budget_after_fee = max(0.0, budget - cost_est)
                new_shares = budget_after_fee / buy_px
                if not config.allow_fractional_shares:
                    new_shares = float(int(new_shares))
                spend = new_shares * buy_px
                fee_paid = spend * fee
                cash -= spend + fee_paid
                shares = new_shares
                trade_rows.append(
                    {"ts": ts, "side": "BUY", "price": buy_px, "shares": shares, "fee": fee_paid}
                )

            last_target = tgt

        equity = cash + shares * float(close_px.iloc[i])
        rows.append(
            {
                "ts": ts,
                "cash": cash,
                "shares": shares,
                "close": float(close_px.iloc[i]),
                "equity": equity,
                "target_pos": last_target,
                "signal": float(sig.iloc[i]),
            }
        )

    equity_curve = pd.DataFrame(rows)  # type: ignore[union-attr]
    trades = pd.DataFrame(trade_rows)  # type: ignore[union-attr]
    return BacktestResult(symbol=symbol, bars=bars, signals=sig, trades=trades, equity_curve=equity_curve)

