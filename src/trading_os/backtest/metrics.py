from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TYPE_CHECKING

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd_types


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    total_return: float
    cagr: float | None
    max_drawdown: float
    sharpe: float | None
    trades: int


def _require_pandas() -> None:
    if pd is None:  # pragma: no cover
        raise RuntimeError(
            "Metrics require pandas. Install optional deps in Python 3.10–3.12: "
            "`pip install -e .[data_lake]`"
        )


def compute_performance_metrics(
    equity_curve: "pd_types.DataFrame",
    *,
    periods_per_year: int = 252,
) -> PerformanceMetrics:
    _require_pandas()

    if equity_curve is None or equity_curve.empty:
        raise ValueError("equity_curve is empty")
    if "equity" not in equity_curve.columns:
        raise ValueError("equity_curve missing 'equity' column")

    eq = equity_curve["equity"].astype(float)
    total_return = (eq.iloc[-1] / eq.iloc[0]) - 1.0

    # CAGR (approx, assumes evenly spaced periods)
    n = len(eq)
    years = n / float(periods_per_year) if periods_per_year > 0 else 0.0
    cagr = None
    if years > 0:
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0

    # max drawdown
    peak = eq.cummax()
    dd = (eq / peak) - 1.0
    max_dd = float(dd.min())

    # Sharpe (simple, no risk-free)
    rets = eq.pct_change().dropna()
    sharpe = None
    if len(rets) > 2 and float(rets.std()) > 0:
        sharpe = float(rets.mean() / rets.std()) * sqrt(periods_per_year)

    trades = int(equity_curve.get("target_pos", pd.Series(dtype=float)).diff().abs().sum() / 1.0)  # type: ignore[union-attr]
    return PerformanceMetrics(
        total_return=float(total_return),
        cagr=cagr,
        max_drawdown=max_dd,
        sharpe=sharpe,
        trades=trades,
    )

