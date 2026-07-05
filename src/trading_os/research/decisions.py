from __future__ import annotations

import math
from typing import Any


def build_canslim_decisions(
    candidates: list[dict[str, Any]],
    setups: dict[str, dict[str, Any]],
    *,
    as_of: str,
    source_run_id: str,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for candidate in candidates:
        if candidate.get("classification") != "strict_canslim_candidate":
            continue

        symbol = str(candidate.get("symbol", "")).strip()
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)

        setup = setups.get(symbol, {})
        pivot = setup.get("pivot_price")
        stop_loss = setup.get("stop_loss")

        if _is_finite_positive_number(pivot) and _is_finite_positive_number(stop_loss):
            decision = setup.get("status") or "wait_for_breakout"
            confidence = 0.75
            reason = "strict CANSLIM evidence with defined technical setup"
        else:
            decision = "research_only"
            confidence = 0.45
            reason = "strict CANSLIM evidence but technical setup is incomplete"

        decisions.append(
            {
                "symbol": symbol,
                "as_of": as_of,
                "decision": decision,
                "confidence": confidence,
                "reason": reason,
                "score": candidate.get("score"),
                "pivot_price": pivot,
                "buy_zone_high": setup.get("buy_zone_high"),
                "stop_loss": stop_loss,
                "source_run_id": source_run_id,
            }
        )

    return decisions


def _is_finite_positive_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(value)
        and value > 0
    )
