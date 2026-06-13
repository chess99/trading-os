from __future__ import annotations

import math
from typing import Any

_DECISION_STATUS = {
    "wait_for_breakout": "watching",
    "actionable_watch": "actionable",
    "reject": "invalidated",
    "research_only": "candidate",
}


def update_watchlist_from_decisions(
    current: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for item in current:
        symbol = _clean_symbol(item.get("symbol"))
        if symbol is None:
            continue
        row = dict(item)
        row["symbol"] = symbol
        by_symbol[symbol] = row

    for decision in decisions:
        symbol = _clean_symbol(decision.get("symbol"))
        if symbol is None:
            continue

        decision_name = decision.get("decision")
        status = _DECISION_STATUS.get(decision_name)
        if status is None:
            continue

        existing = dict(by_symbol.get(symbol, {"symbol": symbol}))
        if decision_name in {"wait_for_breakout", "actionable_watch"} and not _has_valid_levels(
            decision
        ):
            status = "candidate"

        existing["status"] = status
        existing["source_run_id"] = decision.get("source_run_id")
        existing["last_decision"] = decision_name

        if status in {"watching", "actionable"}:
            existing["pivot_price"] = decision.get("pivot_price")
            existing["buy_zone_high"] = decision.get("buy_zone_high")
            existing["stop_loss"] = decision.get("stop_loss")
        else:
            _clear_actionable_levels(existing)

        by_symbol[symbol] = existing

    return sorted(by_symbol.values(), key=lambda row: row["symbol"])


def _clean_symbol(value: Any) -> str | None:
    if value is None:
        return None
    symbol = str(value).strip()
    if not symbol:
        return None
    return symbol


def _has_valid_levels(decision: dict[str, Any]) -> bool:
    return all(
        _is_finite_positive_number(decision.get(field))
        for field in ("pivot_price", "buy_zone_high", "stop_loss")
    )


def _is_finite_positive_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(value)
        and value > 0
    )


def _clear_actionable_levels(row: dict[str, Any]) -> None:
    for field in ("pivot_price", "buy_zone_high", "stop_loss"):
        row.pop(field, None)
