from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from typing import TYPE_CHECKING

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd_types

from ..schema import BarColumns, Exchange


@dataclass(frozen=True, slots=True)
class SyntheticBarsConfig:
    start: datetime
    days: int = 60
    start_price: float = 100.0
    daily_return: float = 0.001  # deterministic drift
    daily_vol: float = 0.01  # deterministic range amplitude
    volume: float = 1_000_000.0


def make_daily_bars(
    ticker: str,
    *,
    exchange: Exchange,
    config: SyntheticBarsConfig | None = None,
) -> pd.DataFrame:
    """Generate deterministic daily OHLCV bars for offline testing."""
    if pd is None:  # pragma: no cover
        raise RuntimeError(
            "synthetic source requires optional dependencies. "
            "Install: `pip install -e .[data_lake]`"
        )
    cfg = config or SyntheticBarsConfig(start=datetime(2020, 1, 1, tzinfo=timezone.utc))
    if cfg.start.tzinfo is None:
        raise ValueError("SyntheticBarsConfig.start must be timezone-aware (UTC recommended)")
    if cfg.days <= 0:
        raise ValueError("days must be > 0")

    ts = [cfg.start + timedelta(days=i) for i in range(cfg.days)]
    close = []
    price = cfg.start_price
    for i in range(cfg.days):
        price *= 1.0 + cfg.daily_return
        # deterministic "wiggle"
        price *= 1.0 + (cfg.daily_vol * ((i % 10) - 5) / 50.0)
        close.append(price)

    close_s = pd.Series(close, dtype="float64")  # type: ignore[union-attr]
    open_s = close_s.shift(1).fillna(close_s.iloc[0]).astype("float64")
    high_s = pd.concat([open_s, close_s], axis=1).max(axis=1) * (1.0 + cfg.daily_vol)
    low_s = pd.concat([open_s, close_s], axis=1).min(axis=1) * (1.0 - cfg.daily_vol)

    out = pd.DataFrame(  # type: ignore[union-attr]
        {
            BarColumns.symbol: f"{exchange.value}:{ticker}",
            BarColumns.ts: pd.to_datetime(pd.Series(ts)).dt.tz_convert(timezone.utc),
            BarColumns.open: open_s,
            BarColumns.high: high_s.astype("float64"),
            BarColumns.low: low_s.astype("float64"),
            BarColumns.close: close_s,
            BarColumns.volume: float(cfg.volume),
        }
    )
    return out

