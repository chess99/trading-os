from __future__ import annotations

import math
from typing import Any

import pandas as pd


def detect_technical_setup(symbol: str, bars: Any) -> dict[str, Any]:
    if not symbol:
        return _insufficient_bars(symbol)
    if bars is None or getattr(bars, "empty", False):
        return _insufficient_bars(symbol)
    if "symbol" not in bars.columns or "ts" not in bars.columns or "close" not in bars.columns:
        return _insufficient_bars(symbol)

    rows = bars[bars["symbol"].astype(str) == symbol].copy()
    if rows.empty:
        return _insufficient_bars(symbol)

    rows = rows.sort_values("ts")
    rows["close"] = pd.to_numeric(rows["close"], errors="coerce")
    rows = rows[rows["close"].map(math.isfinite)]
    if rows.empty:
        return _insufficient_bars(symbol)

    closes = rows["close"]
    pivot = float(closes.tail(min(len(closes), 60)).max())
    if "volume" in rows.columns:
        volume_window = rows.tail(min(len(rows), 50))
        volumes = pd.to_numeric(volume_window["volume"], errors="coerce").dropna()
        volumes = volumes[volumes.map(math.isfinite)]
        volume_baseline = (
            float(volumes.tail(min(len(volumes), 50)).mean()) if not volumes.empty else 0.0
        )
    else:
        volume_baseline = 0.0

    return {
        "symbol": symbol,
        "status": "wait_for_breakout",
        "pivot_price": round(pivot, 4),
        "buy_zone_high": round(pivot * 1.05, 4),
        "stop_loss": round(pivot * 0.92, 4),
        "volume_baseline": round(volume_baseline, 4),
    }


def _insufficient_bars(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "status": "insufficient_bars",
        "pivot_price": None,
        "buy_zone_high": None,
        "stop_loss": None,
        "volume_baseline": None,
    }
