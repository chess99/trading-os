from __future__ import annotations

from typing import Any


def detect_technical_setup(symbol: str, bars: Any) -> dict[str, Any]:
    if not symbol:
        return _insufficient_bars(symbol)
    if bars is None or getattr(bars, "empty", False):
        return _insufficient_bars(symbol)
    if "symbol" not in bars.columns or "close" not in bars.columns:
        return _insufficient_bars(symbol)

    rows = bars[bars["symbol"].astype(str) == symbol].copy()
    if rows.empty:
        return _insufficient_bars(symbol)

    rows = rows.sort_values("ts")
    closes = rows["close"].astype(float)
    pivot = float(closes.tail(min(len(closes), 60)).max())
    if "volume" in rows.columns:
        volume_baseline = float(rows["volume"].astype(float).tail(min(len(rows), 50)).mean())
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
