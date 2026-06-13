from __future__ import annotations

from typing import Any


def build_canslim_decisions(
    candidates: list[dict[str, Any]],
    setups: dict[str, dict[str, Any]],
    *,
    as_of: str,
    source_run_id: str,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("classification") != "strict_canslim_candidate":
            continue

        symbol = str(candidate["symbol"])
        setup = setups.get(symbol, {})
        pivot = setup.get("pivot_price")
        stop_loss = setup.get("stop_loss")

        if pivot and stop_loss:
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
