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

    setup_window = rows.tail(min(len(rows), 60)).copy()
    closes = setup_window["close"]
    pivot = float(closes.max())
    prior_pivot = _prior_pivot(closes)
    base_low = float(closes.min())
    base_length_days = int(len(setup_window))
    base_depth_pct = (pivot - base_low) / pivot if pivot > 0 else 0.0
    if "volume" in rows.columns:
        volume_window = rows.tail(min(len(rows), 50))
        volumes = pd.to_numeric(volume_window["volume"], errors="coerce").dropna()
        volumes = volumes[volumes.map(math.isfinite)]
        volume_baseline = (
            float(volumes.tail(min(len(volumes), 50)).mean()) if not volumes.empty else 0.0
        )
        latest_volume = _latest_valid_volume(rows)
    else:
        volume_baseline = 0.0
        latest_volume = 0.0

    latest_close = float(closes.iloc[-1])
    volume_multiple = latest_volume / volume_baseline if volume_baseline > 0 else 0.0
    breakout_volume_confirmed = latest_close >= pivot and volume_multiple >= 1.4
    recovery_pct = _recovery_pct(closes)
    setup_type = _classify_base(base_length_days, base_depth_pct, recovery_pct)
    volume_dry_up = _detect_volume_dry_up(rows)
    risk_flags = _risk_flags(
        latest_close=latest_close,
        prior_pivot=prior_pivot,
        base_depth_pct=base_depth_pct,
        volume_multiple=volume_multiple,
    )
    entry_quality = _entry_quality(
        breakout_volume_confirmed=breakout_volume_confirmed,
        risk_flags=risk_flags,
        volume_dry_up=volume_dry_up,
    )

    return {
        "symbol": symbol,
        "status": "actionable_watch" if breakout_volume_confirmed else "wait_for_breakout",
        "setup_type": setup_type,
        "pivot_price": round(pivot, 4),
        "prior_pivot_price": round(prior_pivot, 4) if prior_pivot is not None else None,
        "buy_zone_high": round(pivot * 1.05, 4),
        "stop_loss": round(pivot * 0.92, 4),
        "volume_baseline": round(volume_baseline, 4),
        "volume_multiple": round(volume_multiple, 4),
        "base_length_days": base_length_days,
        "base_depth_pct": round(base_depth_pct, 4),
        "recovery_pct": round(recovery_pct, 4) if recovery_pct is not None else None,
        "volume_dry_up": volume_dry_up,
        "breakout_volume_confirmed": breakout_volume_confirmed,
        "risk_flags": risk_flags,
        "entry_quality": entry_quality,
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


def _classify_base(
    base_length_days: int, base_depth_pct: float, recovery_pct: float | None
) -> str:
    if base_length_days >= 35 and base_depth_pct <= 0.15:
        return "flat_base_candidate"
    if (
        base_length_days >= 30
        and 0.15 < base_depth_pct <= 0.35
        and recovery_pct is not None
        and recovery_pct >= 0.85
    ):
        return "cup_base_candidate"
    if base_length_days >= 30 and base_depth_pct <= 0.35:
        return "base_candidate"
    return "simple_pivot"


def _prior_pivot(closes: pd.Series) -> float | None:
    if len(closes) < 2:
        return None
    prior = closes.iloc[:-1]
    if prior.empty:
        return None
    return float(prior.max())


def _recovery_pct(closes: pd.Series) -> float | None:
    if len(closes) < 6:
        return None
    left_peak = float(closes.iloc[: max(1, len(closes) // 3)].max())
    base_low = float(closes.min())
    latest_close = float(closes.iloc[-1])
    denominator = left_peak - base_low
    if denominator <= 0:
        return 1.0
    return max(0.0, min(1.5, (latest_close - base_low) / denominator))


def _risk_flags(
    *,
    latest_close: float,
    prior_pivot: float | None,
    base_depth_pct: float,
    volume_multiple: float,
) -> list[str]:
    flags: list[str] = []
    if prior_pivot is not None and prior_pivot > 0 and latest_close > prior_pivot * 1.05:
        flags.append("extended_from_pivot")
    if base_depth_pct > 0.35:
        flags.append("base_too_deep")
    if volume_multiple > 0 and volume_multiple < 0.8:
        flags.append("weak_breakout_volume")
    return flags


def _entry_quality(
    *,
    breakout_volume_confirmed: bool,
    risk_flags: list[str],
    volume_dry_up: bool,
) -> str:
    if "extended_from_pivot" in risk_flags:
        return "extended"
    if breakout_volume_confirmed and not risk_flags:
        return "actionable"
    if volume_dry_up and not risk_flags:
        return "constructive"
    return "watch"


def _latest_valid_volume(rows: pd.DataFrame) -> float:
    volumes = pd.to_numeric(rows["volume"], errors="coerce").dropna()
    volumes = volumes[volumes.map(math.isfinite)]
    if volumes.empty:
        return 0.0
    return float(volumes.iloc[-1])


def _detect_volume_dry_up(rows: pd.DataFrame) -> bool:
    if "volume" not in rows.columns:
        return False
    volumes = pd.to_numeric(rows["volume"], errors="coerce").dropna()
    volumes = volumes[volumes.map(math.isfinite)]
    if len(volumes) < 20:
        return False
    recent = float(volumes.tail(10).mean())
    if len(volumes) >= 40:
        prior = float(volumes.iloc[-40:-10].mean())
    else:
        prior = float(volumes.iloc[:-10].mean())
    return prior > 0 and recent <= prior * 0.8
