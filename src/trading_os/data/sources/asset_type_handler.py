"""Asset-type-aware data handlers.

Each AssetType gets its own handler that encapsulates:
  - fetch: pull data from the right API endpoint
  - normalize: map raw columns to the standard bar schema
  - validate: sanity-check prices before writing to the lake

The dispatcher in akshare_source.fetch_daily_bars selects the handler
based on the caller-supplied asset_type argument.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore[assignment]

from ..schema import Adjustment, Exchange, Symbol, Timeframe
from ..exceptions import DataIntegrityError


class AssetTypeHandler(ABC):
    """Base class for all asset-type handlers."""

    @abstractmethod
    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,
    ) -> tuple[pd.DataFrame, str]:
        """Fetch, normalize, and return (df, source_name).

        The returned df already has all standard bar columns:
        symbol, exchange, timeframe, adjustment, ts, open, high, low,
        close, volume, vwap, trades, source.
        """
        ...

    @abstractmethod
    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        """Sanity-check prices/volume before writing.

        Raises DataIntegrityError if the data looks wrong for this asset type.
        """
        ...


# ── Equity ────────────────────────────────────────────────────────────────────

class EquityHandler(AssetTypeHandler):
    """A-share equity (普通股票). Uses the existing _fetch_with_fallback path."""

    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,
    ) -> tuple[pd.DataFrame, str]:
        # Delegate to the existing equity logic in akshare_source
        from .akshare_source import (
            _fetch_with_fallback,
            _normalize_akshare_data,
            _build_akshare_symbol,
        )
        from datetime import timedelta

        symbol_str = _build_akshare_symbol(ticker, exchange)

        end_str = (end or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        start_str = (
            start
            or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        ).replace("-", "")

        adjust_map = {Adjustment.QFQ: "qfq", Adjustment.HFQ: "hfq", Adjustment.NONE: ""}
        adjust_str = adjust_map.get(adjustment, "")

        df, source = _fetch_with_fallback(ak, symbol_str, exchange, start_str, end_str, adjust_str)
        if df is None or df.empty:
            return pd.DataFrame(), "none"

        df = _normalize_akshare_data(df, ticker, exchange, adjustment)
        return df, source

    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        if df.empty:
            return
        bad = df[df["close"] < 0.01]
        if not bad.empty:
            raise DataIntegrityError(
                symbol=f"{exchange.value}:{ticker}",
                expected_range=(0.01, 10_000.0),
                actual_value=float(bad["close"].iloc[0]),
            )
        bad = df[df["close"] > 10_000]
        if not bad.empty:
            raise DataIntegrityError(
                symbol=f"{exchange.value}:{ticker}",
                expected_range=(0.01, 10_000.0),
                actual_value=float(bad["close"].iloc[0]),
            )


# ── Index ─────────────────────────────────────────────────────────────────────

class IndexHandler(AssetTypeHandler):
    """A-share market index (指数). Uses ak.stock_zh_index_daily — the correct index API."""

    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,  # ignored for indices — always stored as NONE
    ) -> tuple[pd.DataFrame, str]:
        if ak is None:
            raise RuntimeError("akshare is required. Install with: pip install akshare")

        prefix = "sh" if exchange == Exchange.SSE else "sz"
        symbol_str = f"{prefix}{ticker}"

        raw = ak.stock_zh_index_daily(symbol=symbol_str)
        if raw is None or raw.empty:
            return pd.DataFrame(), "none"

        # Filter by date range if provided
        raw["date"] = pd.to_datetime(raw["date"])
        if start:
            raw = raw[raw["date"] >= pd.Timestamp(start)]
        if end:
            raw = raw[raw["date"] <= pd.Timestamp(end)]
        if raw.empty:
            return pd.DataFrame(), "none"

        # Normalize to standard bar schema
        df = raw.rename(columns={"date": "ts"}).copy()
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df["symbol"] = str(Symbol(exchange=exchange, ticker=ticker))
        df["exchange"] = exchange.value
        df["timeframe"] = Timeframe.D1.value
        df["adjustment"] = Adjustment.NONE.value   # always NONE for indices
        df["source"] = "akshare_index"

        # vwap: amount (元) / volume (手*100股) ≈ average price per share
        if "amount" in df.columns and df["amount"].notna().all() and (df["volume"] > 0).all():
            df["vwap"] = df["amount"] / (df["volume"] * 100)
        else:
            df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3

        df["trades"] = 0  # not available from index API

        for col in ["open", "high", "low", "close", "volume", "vwap"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_values("ts").reset_index(drop=True)

        keep = ["symbol", "exchange", "timeframe", "adjustment", "ts",
                "open", "high", "low", "close", "volume", "vwap", "trades", "source"]
        return df[[c for c in keep if c in df.columns]], "akshare_index"

    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        if df.empty:
            return
        symbol_id = f"{exchange.value}:{ticker}"
        # Price sanity: reject obviously wrong values (negative, zero, or absurdly
        # large). We do NOT set a lower bound above ~11 because early 1990s index
        # history starts near 100 and some sector indices are genuinely low.
        # The key defence against equity-price contamination (e.g. 平安银行 ~11 CNY
        # written as 上证指数) is _check_price_continuity in write_bars_parquet,
        # which catches magnitude jumps against existing history.
        bad_price = df[(df["close"] <= 0) | (df["close"] > 50_000)]
        if not bad_price.empty:
            raise DataIntegrityError(
                symbol=symbol_id,
                expected_range=(0.0, 50_000.0),
                actual_value=float(bad_price["close"].iloc[0]),
            )
        # Volume check intentionally omitted: early historical data (pre-2000) has
        # very low volume that would fail any reasonable threshold, and the close
        # price range check already catches the key error case (equity price ~11
        # written as index). _check_price_continuity in write_bars_parquet provides
        # a second layer of defence at write time.


# ── ETF (stub) ────────────────────────────────────────────────────────────────

class EtfHandler(AssetTypeHandler):
    """ETF handler — not yet implemented."""

    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,
    ) -> tuple[pd.DataFrame, str]:
        raise NotImplementedError(
            "EtfHandler is not yet implemented. "
            "Use --asset-type equity for now and handle ETF codes manually."
        )

    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        raise NotImplementedError("EtfHandler is not yet implemented.")


# ── Dispatcher ────────────────────────────────────────────────────────────────

from ..schema import AssetType  # noqa: E402 — import after class defs to avoid circularity

_HANDLERS: dict[AssetType, AssetTypeHandler] = {
    AssetType.EQUITY: EquityHandler(),
    AssetType.INDEX: IndexHandler(),
    AssetType.ETF: EtfHandler(),
}


def get_handler(asset_type: AssetType) -> AssetTypeHandler:
    """Return the handler for the given asset type.

    Raises ValueError for unsupported types.
    """
    handler = _HANDLERS.get(asset_type)
    if handler is None:
        supported = ", ".join(k.value for k in _HANDLERS)
        raise ValueError(
            f"No handler registered for AssetType.{asset_type.value}. "
            f"Supported: {supported}"
        )
    return handler
