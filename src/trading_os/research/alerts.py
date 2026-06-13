from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

_ALERTABLE_STATUSES = {"watching", "actionable"}
_BREAKOUT_TRIGGER = "breakout_confirmed"
_CHINA_TZ = ZoneInfo("Asia/Shanghai")


def evaluate_watchlist_alerts(
    watchlist: list[dict[str, Any]],
    quotes: list[dict[str, Any]],
    *,
    as_of: str,
    existing_cooldowns: set[str],
) -> list[dict[str, Any]]:
    trade_date = _china_date(as_of)
    quote_by_symbol = _index_quotes_by_symbol(quotes)
    seen_cooldowns = set(existing_cooldowns)

    alerts: list[dict[str, Any]] = []
    for item in watchlist:
        symbol = _clean_symbol(item.get("symbol"))
        if symbol is None or item.get("status") not in _ALERTABLE_STATUSES:
            continue

        quote = quote_by_symbol.get(symbol)
        if quote is None:
            continue

        pivot_price = _positive_finite_number(item.get("pivot_price"))
        buy_zone_high = _positive_finite_number(item.get("buy_zone_high"))
        close = _positive_finite_number(quote.get("close"))
        if pivot_price is None or close is None or close < pivot_price:
            continue
        if buy_zone_high is not None and close > buy_zone_high:
            continue

        cooldown_key = f"{symbol}:{_BREAKOUT_TRIGGER}:{trade_date}"
        if cooldown_key in seen_cooldowns:
            continue
        seen_cooldowns.add(cooldown_key)

        alerts.append(
            {
                "alert_id": f"alert-{uuid4().hex}",
                "symbol": symbol,
                "as_of": as_of,
                "trigger_type": _BREAKOUT_TRIGGER,
                "trigger_value": close,
                "pivot_price": pivot_price,
                "status": "pending",
                "cooldown_key": cooldown_key,
            }
        )

    return alerts


def _china_date(as_of: str) -> str:
    if "T" not in as_of:
        return datetime.fromisoformat(as_of).date().isoformat()

    parsed = datetime.fromisoformat(as_of)
    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return parsed.astimezone(_CHINA_TZ).date().isoformat()


def _index_quotes_by_symbol(quotes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    quote_by_symbol: dict[str, dict[str, Any]] = {}
    for quote in quotes:
        symbol = _clean_symbol(quote.get("symbol"))
        if symbol is not None:
            quote_by_symbol[symbol] = quote
    return quote_by_symbol


def _clean_symbol(value: Any) -> str | None:
    if value is None:
        return None
    symbol = str(value).strip()
    if not symbol:
        return None
    return symbol


def _positive_finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number
