# input: pandas bars DataFrame and DCA configuration values
# output: DCA backtest results, equity curve, and performance metrics
# pos: periodic investing backtest helper; update this header and `src/trading_os/backtest/README.md`
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Iterable

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd_types

from ..data.schema import BarColumns


class DcaFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass(frozen=True, slots=True)
class DcaConfig:
    annual_contribution: float = 120_000.0
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    allow_fractional_shares: bool = True


@dataclass(frozen=True, slots=True)
class DcaResult:
    symbol: str
    bars: "pd_types.DataFrame"
    equity_curve: "pd_types.DataFrame"
    trades: "pd_types.DataFrame"


@dataclass(frozen=True, slots=True)
class DcaMetrics:
    total_invested: float
    final_value: float
    profit: float
    roi: float | None
    cagr: float | None
    max_drawdown: float
    sharpe: float | None
    xirr: float | None
    periods: int
    schedule_count: int


def _require_pandas() -> None:
    if pd is None:  # pragma: no cover
        raise RuntimeError(
            "DCA backtest requires pandas. Install optional deps in Python 3.10–3.12: "
            "`pip install -e .[data_lake]`"
        )


def _periods_per_year(freq: DcaFrequency) -> int:
    if freq == DcaFrequency.DAILY:
        return 252
    if freq == DcaFrequency.WEEKLY:
        return 52
    if freq == DcaFrequency.MONTHLY:
        return 12
    raise ValueError(f"unsupported frequency: {freq}")


def build_investment_schedule(
    bars: "pd_types.DataFrame",
    *,
    frequency: DcaFrequency,
) -> "pd_types.Series":
    _require_pandas()
    if bars is None or bars.empty:
        raise ValueError("bars is empty")
    if BarColumns.ts not in bars.columns:
        raise ValueError(f"bars missing column: {BarColumns.ts}")

    ts = pd.to_datetime(bars[BarColumns.ts], utc=True)
    schedule = pd.Series(False, index=bars.index)

    if frequency == DcaFrequency.DAILY:
        schedule[:] = True
        return schedule

    if frequency == DcaFrequency.WEEKLY:
        cal = ts.dt.isocalendar()
        key = cal["year"].astype(str) + "-" + cal["week"].astype(str)
    elif frequency == DcaFrequency.MONTHLY:
        key = ts.dt.to_period("M").astype(str)
    else:
        raise ValueError(f"unsupported frequency: {frequency}")

    first_idx = (
        pd.DataFrame({"key": key})
        .groupby("key", sort=False)
        .head(1)
        .index
    )
    schedule.loc[first_idx] = True
    return schedule


def run_dca_backtest(
    bars: "pd_types.DataFrame",
    *,
    frequency: DcaFrequency,
    config: DcaConfig,
) -> DcaResult:
    _require_pandas()
    if bars is None or bars.empty:
        raise ValueError("bars is empty")
    if BarColumns.symbol not in bars.columns:
        raise ValueError(f"bars missing column: {BarColumns.symbol}")

    bars = bars.sort_values(BarColumns.ts).reset_index(drop=True).copy()
    symbol = str(bars[BarColumns.symbol].iloc[0])
    if (bars[BarColumns.symbol] != symbol).any():
        raise ValueError("run_dca_backtest currently supports a single symbol only")

    schedule = build_investment_schedule(bars, frequency=frequency)
    per_period = float(config.annual_contribution) / float(_periods_per_year(frequency))

    open_px = bars[BarColumns.open].astype(float)
    close_px = bars[BarColumns.close].astype(float)

    fee = config.fee_bps / 10_000.0
    slip = config.slippage_bps / 10_000.0

    cash = 0.0
    shares = 0.0
    rows = []
    trade_rows = []
    schedule_count = 0

    for i in range(len(bars)):
        ts = bars[BarColumns.ts].iloc[i]
        contribution = 0.0

        if bool(schedule.iloc[i]):
            schedule_count += 1
            contribution = per_period
            cash += contribution

            px_exec = float(open_px.iloc[i])
            if px_exec > 0.0 and cash > 0.0:
                buy_px = px_exec * (1.0 + slip)
                budget = cash
                cost_est = budget * fee
                budget_after_fee = max(0.0, budget - cost_est)
                new_shares = budget_after_fee / buy_px if buy_px > 0 else 0.0
                if not config.allow_fractional_shares:
                    new_shares = float(int(new_shares))
                spend = new_shares * buy_px
                fee_paid = spend * fee
                cash -= spend + fee_paid
                shares += new_shares
                if new_shares > 0.0:
                    trade_rows.append(
                        {
                            "ts": ts,
                            "side": "BUY",
                            "price": buy_px,
                            "shares": new_shares,
                            "fee": fee_paid,
                        }
                    )

        equity = cash + shares * float(close_px.iloc[i])
        rows.append(
            {
                "ts": ts,
                "cash": cash,
                "shares": shares,
                "close": float(close_px.iloc[i]),
                "equity": equity,
                "contribution": contribution,
                "schedule": bool(schedule.iloc[i]),
            }
        )

    equity_curve = pd.DataFrame(rows)  # type: ignore[union-attr]
    trades = pd.DataFrame(trade_rows)  # type: ignore[union-attr]
    return DcaResult(symbol=symbol, bars=bars, equity_curve=equity_curve, trades=trades)


def compute_dca_metrics(
    equity_curve: "pd_types.DataFrame",
    *,
    periods_per_year: int,
) -> DcaMetrics:
    _require_pandas()
    if equity_curve is None or equity_curve.empty:
        raise ValueError("equity_curve is empty")
    if "equity" not in equity_curve.columns:
        raise ValueError("equity_curve missing 'equity' column")

    eq = equity_curve["equity"].astype(float)
    contrib = equity_curve.get("contribution", pd.Series(0.0, index=eq.index)).astype(float)

    total_invested = float(contrib.sum())
    final_value = float(eq.iloc[-1])
    profit = final_value - total_invested
    roi = profit / total_invested if total_invested > 0 else None

    peak = eq.cummax()
    dd = (eq / peak) - 1.0
    max_dd = float(dd.min())

    prev_eq = eq.shift(1)
    valid = prev_eq > 0
    rets = ((eq - prev_eq - contrib) / prev_eq).where(valid).dropna()

    cagr = None
    sharpe = None
    if len(rets) > 0:
        cumulative = (1.0 + rets).prod() - 1.0
        years = len(rets) / float(periods_per_year) if periods_per_year > 0 else 0.0
        if years > 0:
            cagr = (1.0 + cumulative) ** (1.0 / years) - 1.0
        if float(rets.std()) > 0:
            sharpe = float(rets.mean() / rets.std()) * (periods_per_year**0.5)

    ts = pd.to_datetime(equity_curve["ts"], utc=True)
    cash_flows = _build_cash_flows(ts, contrib, final_value)
    xirr = _xirr(cash_flows) if cash_flows else None

    schedule_count = int(equity_curve.get("schedule", pd.Series(dtype=bool)).sum())

    return DcaMetrics(
        total_invested=total_invested,
        final_value=final_value,
        profit=profit,
        roi=roi,
        cagr=cagr,
        max_drawdown=max_dd,
        sharpe=sharpe,
        xirr=xirr,
        periods=len(eq),
        schedule_count=schedule_count,
    )


def _build_cash_flows(
    ts: "pd_types.Series",
    contributions: "pd_types.Series",
    final_value: float,
) -> list[tuple["pd_types.Timestamp", float]]:
    flows: list[tuple[pd.Timestamp, float]] = []
    for t, amt in zip(ts, contributions, strict=False):
        amt = float(amt)
        if amt != 0.0:
            flows.append((pd.Timestamp(t), -amt))
    if flows:
        flows.append((pd.Timestamp(ts.iloc[-1]), float(final_value)))
    return flows


def _xirr(
    cash_flows: Iterable[tuple["pd_types.Timestamp", float]],
    *,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float | None:
    flows = list(cash_flows)
    if len(flows) < 2:
        return None
    has_pos = any(cf[1] > 0 for cf in flows)
    has_neg = any(cf[1] < 0 for cf in flows)
    if not (has_pos and has_neg):
        return None

    def xnpv(rate: float) -> float:
        t0 = flows[0][0]
        total = 0.0
        for ts, amount in flows:
            years = (ts - t0).days / 365.0
            total += amount / ((1.0 + rate) ** years)
        return total

    low = -0.999
    high = 10.0
    npv_low = xnpv(low)
    npv_high = xnpv(high)
    if npv_low == 0:
        return low
    if npv_high == 0:
        return high
    if npv_low * npv_high > 0:
        return None

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        npv_mid = xnpv(mid)
        if abs(npv_mid) < tol:
            return mid
        if npv_low * npv_mid < 0:
            high = mid
            npv_high = npv_mid
        else:
            low = mid
            npv_low = npv_mid
    return (low + high) / 2.0
