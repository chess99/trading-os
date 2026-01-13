from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd_types

from ..data.schema import BarColumns


def _require_pandas() -> None:
    if pd is None:  # pragma: no cover
        raise RuntimeError(
            "Strategies require pandas. Install optional deps in Python 3.10–3.12: "
            "`pip install -e .[data_lake]`"
        )


def buy_and_hold_signals(bars: "pd_types.DataFrame") -> "pd_types.Series":
    """Always 1 (long) after first bar."""
    _require_pandas()
    sig = pd.Series(1.0, index=bars.index)  # type: ignore[union-attr]
    return sig


def sma_crossover_signals(
    bars: "pd_types.DataFrame", *, fast: int = 10, slow: int = 30
) -> "pd_types.Series":
    """Long when fast SMA > slow SMA. Signals are computed on close."""
    _require_pandas()
    if fast <= 0 or slow <= 0 or fast >= slow:
        raise ValueError("Require 0 < fast < slow")

    close = bars[BarColumns.close].astype(float)
    sma_f = close.rolling(fast).mean()
    sma_s = close.rolling(slow).mean()
    sig = (sma_f > sma_s).astype(float)
    sig = sig.fillna(0.0)
    return sig

