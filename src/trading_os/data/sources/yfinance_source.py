from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from typing import TYPE_CHECKING

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

try:
    import yfinance as yf  # type: ignore
except ImportError:  # pragma: no cover
    yf = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd_types

from ..schema import BarColumns, Exchange


@dataclass(frozen=True, slots=True)
class YFinanceConfig:
    auto_adjust: bool = False


def fetch_daily_bars(
    ticker: str,
    *,
    exchange: Exchange,
    start: str | None = None,
    end: str | None = None,
    config: YFinanceConfig | None = None,
) -> pd.DataFrame:
    """Fetch daily bars via yfinance.

    Notes:
    - yfinance uses Yahoo tickers; for US equities, ticker often matches (e.g. AAPL).
    - `ts` is set to UTC. For daily bars, we treat date index as a timestamp at 00:00 UTC.
      This is acceptable for MVP; later we can map to exchange close time.
    """

    if pd is None or yf is None:  # pragma: no cover
        raise RuntimeError(
            "yfinance source requires optional dependencies. "
            "Install: `pip install -e .[data_lake,data_yahoo]`"
        )

    _ = config or YFinanceConfig()

    df = yf.download(
        tickers=ticker,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if df is None or df.empty:
        return pd.DataFrame(columns=[BarColumns.symbol, BarColumns.ts])  # type: ignore[union-attr]

    df = df.reset_index()
    # columns often: Date, Open, High, Low, Close, Adj Close, Volume
    ts_col = df.columns[0]
    df[BarColumns.ts] = pd.to_datetime(df[ts_col]).dt.tz_localize(timezone.utc)
    out = pd.DataFrame(  # type: ignore[union-attr]
        {
            BarColumns.symbol: f"{exchange.value}:{ticker}",
            BarColumns.ts: df[BarColumns.ts],
            BarColumns.open: df["Open"].astype(float),
            BarColumns.high: df["High"].astype(float),
            BarColumns.low: df["Low"].astype(float),
            BarColumns.close: df["Close"].astype(float),
            BarColumns.volume: df["Volume"].astype(float),
        }
    )
    return out

