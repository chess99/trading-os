from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from ..research.store import ResearchStore


class BarProvider(Protocol):
    def period_bars(
        self,
        symbols: list[str],
        *,
        start: date,
        end: date,
        lookback_days: int,
        adjustment: str = "qfq",
    ):
        ...

    def history_for_signal(
        self,
        symbols: list[str],
        *,
        trading_date: date,
        lookback_days: int,
        adjustment: str = "qfq",
    ):
        ...


@dataclass(slots=True)
class ResearchStoreBarProvider:
    store: ResearchStore

    def period_bars(
        self,
        symbols: list[str],
        *,
        start: date,
        end: date,
        lookback_days: int,
        adjustment: str = "qfq",  # noqa: ARG002
    ):
        fetch_start = start - timedelta(days=lookback_days + 31)
        fetch_end = end + timedelta(days=1)
        return self.store.get_bars(symbols, start=fetch_start, end=fetch_end)

    def history_for_signal(
        self,
        symbols: list[str],
        *,
        trading_date: date,
        lookback_days: int,
        adjustment: str = "qfq",  # noqa: ARG002
    ):
        fetch_start = trading_date - timedelta(days=lookback_days + 31)
        return self.store.get_bars(symbols, start=fetch_start, end=trading_date)
