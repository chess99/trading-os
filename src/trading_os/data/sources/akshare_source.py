from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from ..schema import Adjustment, Exchange, Symbol, Timeframe

logger = logging.getLogger(__name__)


class AkshareConfig:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout


def fetch_daily_bars(
    ticker: str,
    *,
    exchange: Exchange,
    start: str | date | None = None,
    end: str | date | None = None,
    adjustment: Adjustment = Adjustment.NONE,
    config: AkshareConfig | None = None,  # noqa: ARG001
    asset_type: Any | None = None,
) -> tuple[pd.DataFrame, str]:
    """Fetch A-share daily bars from AkShare EastMoney history endpoint."""
    if asset_type is not None:
        raise ValueError("ResearchStore AkShare adapter only supports A-share equities")
    if exchange not in {Exchange.SSE, Exchange.SZSE}:
        raise ValueError(f"akshare only supports SSE/SZSE A-share equities, got: {exchange}")

    try:
        import akshare as ak
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("akshare is required for A-share data") from exc

    symbol_str = _build_akshare_symbol(ticker, exchange)
    try:
        raw = ak.stock_zh_a_hist(
            symbol=symbol_str,
            period="daily",
            start_date=_ak_date(start),
            end_date=_ak_date(end),
            adjust=_adjustment_value(adjustment),
        )
        if raw is not None and not raw.empty:
            raw = raw.copy()
            if "成交量" in raw.columns:
                raw["成交量"] = raw["成交量"] * 100
            return (
                _normalize_akshare_data(raw, ticker, exchange, adjustment, "eastmoney"),
                "eastmoney",
            )
    except Exception as exc:
        logger.debug("eastmoney daily bars failed for %s:%s: %s", exchange.value, ticker, exc)

    fallback = ak.stock_zh_a_daily(
        symbol=_prefixed_symbol(ticker, exchange),
        start_date=_ak_date(start),
        end_date=_ak_date(end),
        adjust=_adjustment_value(adjustment),
    )
    if fallback is None or fallback.empty:
        return pd.DataFrame(), "sina_daily"
    return _normalize_akshare_data(
        fallback, ticker, exchange, adjustment, "sina_daily"
    ), "sina_daily"


def _ak_date(value: str | date | None) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return value.replace("-", "")


def _adjustment_value(adjustment: Adjustment) -> str:
    if adjustment == Adjustment.QFQ:
        return "qfq"
    if adjustment == Adjustment.HFQ:
        return "hfq"
    return ""


def _build_akshare_symbol(ticker: str, exchange: Exchange) -> str:
    if len(ticker) != 6 or not ticker.isdigit():
        raise ValueError(f"A-share ticker must be 6 digits, got: {ticker}")
    if exchange not in {Exchange.SSE, Exchange.SZSE}:
        raise ValueError(f"unsupported A-share exchange: {exchange}")
    return ticker


def _prefixed_symbol(ticker: str, exchange: Exchange) -> str:
    prefix = "sh" if exchange == Exchange.SSE else "sz"
    return f"{prefix}{ticker}"


def _normalize_akshare_data(
    df: pd.DataFrame,
    ticker: str,
    exchange: Exchange,
    adjustment: Adjustment,
    source_name: str = "eastmoney",
) -> pd.DataFrame:
    column_mapping = {
        "日期": "ts",
        "date": "ts",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    out = df.rename(columns=column_mapping).copy()
    for column in ["ts", "open", "high", "low", "close", "volume"]:
        if column not in out.columns:
            raise ValueError(f"missing required AkShare column: {column}")

    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    out["symbol"] = str(Symbol(exchange=exchange, ticker=ticker))
    out["exchange"] = exchange.value
    out["timeframe"] = Timeframe.D1.value
    out["adjustment"] = adjustment.value
    out["source"] = source_name

    for column in ["open", "high", "low", "close", "volume"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if "amount" in out.columns:
        amount = pd.to_numeric(out["amount"], errors="coerce").fillna(0)
        out["vwap"] = np.where(
            amount > 0,
            amount / out["volume"],
            (out["high"] + out["low"] + out["close"]) / 3,
        )
    else:
        out["vwap"] = (out["high"] + out["low"] + out["close"]) / 3
    out["trades"] = np.floor(out["volume"].fillna(0) / 100).astype(int)

    columns = [
        "symbol",
        "exchange",
        "timeframe",
        "adjustment",
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "trades",
        "source",
    ]
    return out.sort_values("ts").reset_index(drop=True)[columns]


def get_stock_info(ticker: str, exchange: Exchange) -> dict:
    try:
        import akshare as ak

        info = ak.stock_individual_info_em(symbol=_build_akshare_symbol(ticker, exchange))
        if info is None or info.empty:
            return {}
        values = dict(zip(info.get("item", []), info.get("value", []), strict=False))
        return {
            "symbol": str(Symbol(exchange=exchange, ticker=ticker)),
            "name": values.get("股票简称", ""),
            "market_cap": values.get("总市值", 0),
            "industry": values.get("行业", values.get("所属行业", "")),
            "source": "eastmoney",
        }
    except Exception as exc:  # pragma: no cover - diagnostic helper
        logger.warning("failed to fetch stock info for %s:%s: %s", exchange, ticker, exc)
        return {}


def _make_akshare_df_for_test() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "日期": pd.date_range("2024-01-01", periods=5, freq="B"),
            "开盘": [10.0, 10.1, 10.2, 10.3, 10.4],
            "最高": [10.5, 10.6, 10.7, 10.8, 10.9],
            "最低": [9.5, 9.6, 9.7, 9.8, 9.9],
            "收盘": [10.2, 10.3, 10.4, 10.5, 10.6],
            "成交量": [1_000_000] * 5,
            "成交额": [10_000_000.0] * 5,
        }
    )
