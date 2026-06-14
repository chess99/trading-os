from __future__ import annotations

from datetime import date
from typing import Any


def canonical_from_vendor_code(value: Any) -> str | None:
    text = str(value)
    if "." not in text:
        return None
    ticker, suffix = text.split(".", 1)
    exchange = {
        "XSHG": "SSE",
        "SH": "SSE",
        "XSHE": "SZSE",
        "SZ": "SZSE",
        "XBSE": "BSE",
        "BJ": "BSE",
    }.get(suffix.upper())
    if exchange is None:
        return None
    return f"{exchange}:{ticker.zfill(6)}"


def vendor_code_from_canonical(symbol: str, *, style: str) -> str:
    exchange, ticker = symbol.split(":", 1)
    if style == "rqdata":
        suffix = {"SSE": "XSHG", "SZSE": "XSHE", "BSE": "XBSE"}[exchange]
    elif style == "jqdata":
        suffix = {"SSE": "XSHG", "SZSE": "XSHE", "BSE": "XBSE"}[exchange]
    else:
        raise ValueError(f"unknown vendor style: {style}")
    return f"{ticker}.{suffix}"


def normalize_price_frame(raw: Any, *, symbol_column: str, date_column: str) -> Any:
    import pandas as pd

    out = pd.DataFrame(
        {
            "symbol": raw[symbol_column].map(canonical_from_vendor_code),
            "ts": pd.to_datetime(raw[date_column], errors="coerce"),
            "open": pd.to_numeric(raw.get("open"), errors="coerce"),
            "high": pd.to_numeric(raw.get("high"), errors="coerce"),
            "low": pd.to_numeric(raw.get("low"), errors="coerce"),
            "close": pd.to_numeric(raw.get("close"), errors="coerce"),
            "volume": pd.to_numeric(raw.get("volume"), errors="coerce"),
            "amount": pd.to_numeric(
                raw.get("total_turnover", raw.get("money")),
                errors="coerce",
            ),
        }
    )
    return out.dropna(subset=["symbol", "ts"]).sort_values(["symbol", "ts"]).reset_index(drop=True)


def normalize_fundamentals(raw: Any, *, symbol_column: str) -> Any:
    import pandas as pd

    if raw is None or raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out["symbol"] = out[symbol_column].map(canonical_from_vendor_code)
    return out.dropna(subset=["symbol"]).reset_index(drop=True)


def ymd(value: date) -> str:
    return value.isoformat()
