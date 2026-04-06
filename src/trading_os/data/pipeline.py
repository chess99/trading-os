"""DataPipeline — the single entry point for all market data.

Key guarantee: ALL data access goes through this class.
The `trading_date` parameter is a hard constraint — no data on or after
that date will ever be returned. This prevents look-ahead bias at the
framework level; strategies don't need to worry about it.

A-share note: daily bar data for date T is published after 15:30 on T.
So when trading_date=T (i.e., we're deciding what to trade on T's open),
we can only use bars with date < T. The pipeline enforces this.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .lake import LocalDataLake
from .schema import Adjustment, BarColumns, Exchange, Timeframe

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)


class DataPipeline:
    """Wraps LocalDataLake with look-ahead bias protection.

    Usage::

        pipeline = DataPipeline(lake)
        bars = pipeline.get_bars(
            symbols=["SSE:600000", "SZSE:000001"],
            trading_date=date(2024, 3, 15),   # signals for this date
            lookback_days=120,                  # how many days of history to load
        )
        # bars contains only dates BEFORE 2024-03-15
    """

    def __init__(self, lake: LocalDataLake) -> None:
        self._lake = lake

    def get_bars(
        self,
        symbols: list[str],
        *,
        trading_date: date,
        lookback_days: int = 252,
        timeframe: Timeframe = Timeframe.D1,
        adjustment: Adjustment = Adjustment.QFQ,
    ) -> "pd.DataFrame":
        """Return historical bars strictly before trading_date.

        Args:
            symbols:       List of canonical symbol ids (e.g. ["SSE:600000"]).
            trading_date:  The date we're generating signals for. Data on or
                           after this date is excluded — always.
            lookback_days: How many calendar days of history to load.
                           252 ≈ 1 trading year.
            timeframe:     Bar frequency (default: daily).
            adjustment:    Price adjustment (default: QFQ / 前复权 for A shares).

        Returns:
            DataFrame sorted by (symbol, ts), with ts < trading_date.
        """
        # Compute the start date for the lookback window
        from datetime import timedelta

        start_date = trading_date - timedelta(days=lookback_days + 30)  # buffer for holidays

        # Convert dates to UTC timestamps for DuckDB filtering
        # end is strictly BEFORE trading_date (T-1 close is the latest)
        end_ts = datetime(
            trading_date.year, trading_date.month, trading_date.day,
            tzinfo=timezone.utc
        ).isoformat()
        start_ts = datetime(
            start_date.year, start_date.month, start_date.day,
            tzinfo=timezone.utc
        ).isoformat()

        df = self._lake.query_bars(
            symbols=symbols,
            timeframe=timeframe,
            adjustment=adjustment,
            start=start_ts,
            end=None,  # we'll filter end ourselves with strict <
        )

        if df is None or df.empty:
            log.warning(
                "No bars found for symbols=%s trading_date=%s", symbols, trading_date
            )
            try:
                import pandas as pd
                return pd.DataFrame()
            except ImportError:
                return None  # type: ignore

        # Strict look-ahead bias protection: drop any bar on or after trading_date
        import pandas as pd

        df[BarColumns.ts] = pd.to_datetime(df[BarColumns.ts], utc=True)
        cutoff = pd.Timestamp(trading_date, tz="UTC")
        df = df[df[BarColumns.ts] < cutoff]

        # Apply start filter
        start_cutoff = pd.Timestamp(start_date, tz="UTC")
        df = df[df[BarColumns.ts] >= start_cutoff]

        df = df.sort_values([BarColumns.symbol, BarColumns.ts]).reset_index(drop=True)
        return df

    def available_symbols(
        self,
        *,
        exchange: Exchange | None = None,
        as_of: date | None = None,
    ) -> list[str]:
        """Return symbols available in the local data lake."""
        self._lake.init()
        with self._lake.connect() as con:
            where = []
            params = []
            if exchange is not None:
                where.append(f"{BarColumns.exchange} = ?")
                params.append(exchange.value)
            if as_of is not None:
                cutoff = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)
                where.append(f"{BarColumns.ts} < ?")
                params.append(cutoff.isoformat())
            sql = f"SELECT DISTINCT {BarColumns.symbol} FROM bars"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += f" ORDER BY {BarColumns.symbol}"
            result = con.execute(sql, params).fetchall()
            return [row[0] for row in result]

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "DataPipeline":
        """Convenience constructor using the standard data directory."""
        lake = LocalDataLake(repo_root / "data")
        return cls(lake)
