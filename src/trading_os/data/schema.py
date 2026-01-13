from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Final


class Exchange(str, Enum):
    """Trading venue code.

    Keep this small and opinionated; add venues as needed.
    """

    # China A-share
    SSE = "SSE"  # Shanghai Stock Exchange
    SZSE = "SZSE"  # Shenzhen Stock Exchange

    # US
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"

    # Hong Kong
    HKEX = "HKEX"


class AssetType(str, Enum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    FUND = "FUND"
    BOND = "BOND"
    INDEX = "INDEX"
    FX = "FX"
    CRYPTO = "CRYPTO"


class Timeframe(str, Enum):
    """Bar timeframe."""

    D1 = "1d"
    H1 = "1h"
    M15 = "15m"
    M5 = "5m"
    M1 = "1m"


class Adjustment(str, Enum):
    """Price adjustment regime.

    - NONE: raw (unadjusted)
    - SPLIT_DIV: split/dividend adjusted (typical "adj close" regime)
    - QFQ/HFQ: China-specific 前复权/后复权 (kept for compatibility)
    """

    NONE = "none"
    SPLIT_DIV = "split_div"
    QFQ = "qfq"
    HFQ = "hfq"


@dataclass(frozen=True, slots=True)
class Symbol:
    """Canonical symbol identifier.

    We use `EXCHANGE:TICKER` as the canonical ID, e.g.:
    - SSE:600000
    - SZSE:000001
    - NASDAQ:AAPL
    - HKEX:0700
    """

    exchange: Exchange
    ticker: str
    asset_type: AssetType = AssetType.EQUITY
    currency: str | None = None  # e.g. CNY, USD, HKD

    @property
    def id(self) -> str:
        return f"{self.exchange.value}:{self.ticker}"

    def __str__(self) -> str:  # pragma: no cover
        return self.id


def parse_symbol(symbol_id: str, *, asset_type: AssetType = AssetType.EQUITY) -> Symbol:
    try:
        exch, ticker = symbol_id.split(":", 1)
    except ValueError as e:
        raise ValueError(f"Invalid symbol id: {symbol_id!r} (expected 'EXCHANGE:TICKER')") from e
    return Symbol(exchange=Exchange(exch), ticker=ticker, asset_type=asset_type)


class BarColumns:
    """Canonical OHLCV bar columns."""

    # identifiers
    symbol: Final[str] = "symbol"  # EXCHANGE:TICKER
    exchange: Final[str] = "exchange"  # redundant but useful for filtering
    timeframe: Final[str] = "timeframe"  # '1d', '1h', ...
    adjustment: Final[str] = "adjustment"  # see Adjustment

    # time
    ts: Final[str] = "ts"  # timezone-aware UTC timestamp

    # prices
    open: Final[str] = "open"
    high: Final[str] = "high"
    low: Final[str] = "low"
    close: Final[str] = "close"
    volume: Final[str] = "volume"

    # optional fields for better realism/diagnostics
    vwap: Final[str] = "vwap"
    trades: Final[str] = "trades"
    source: Final[str] = "source"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

