from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .manager_screen_decision_quality import (
    ManagerScreenDecisionQualityError,
    build_decision_support,
    validate_canonical_reason,
    validate_decision_support,
    validate_risk_acknowledgements,
)
from .models import PolicyKind, load_policy
from .sealing import (
    SealingError,
    canonical_json_bytes,
    seal_json,
    verify_sealed,
)

DEFAULT_ABSOLUTE_PRICE_CHANGE_PCT = 20.0
PRICE_CHANGE_POLICY_KEY = "quote_amendment_review_absolute_price_change_pct"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
ROUTES = {"pass", "watch", "send_to_analyst"}
CONFIDENCES = {"low", "medium", "high"}
TRIGGER_TYPES = {"filing", "price", "date", "ttl", "event", "thesis"}
PROTECTED_TASK_TYPES = {
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
}
MANAGER_KEYS = {"agent", "model", "tools"}
DECISION_KEYS = {
    "symbol",
    "route",
    "one_line_reason",
    "decisive_question",
    "revisit_triggers",
    "confidence",
    "evidence_ids",
}
DECISION_V2_KEYS = DECISION_KEYS | {"risk_acknowledgements"}
DECISION_V2_POLICY_KEYS = {
    "decision_contract_version",
    "mandatory_risk_acknowledgement",
    "canonical_fact_line_required",
    "high_liability_to_assets_pct",
}
REVIEW_KEYS = {"symbol", "action", "replacement"}
SUBMISSION_KEYS = {"schema_version", "manager", "reviews"}
VALUATION_FIELDS = (
    "market_cap_cny",
    "float_market_cap_cny",
    "pe_ttm",
    "pb",
)


class ManagerScreenQuoteImpactError(ValueError):
    """Raised when a completed-batch quote-impact review is invalid."""


@serialized_coverage_write
def prepare_manager_screen_quote_impact(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    review_id: str,
    quote_amendment_path: str | Path,
    prepared_at: dt.datetime,
    policy_path: str | Path = "policies/manager-screening.json",
) -> dict[str, Any]:
    """Seal administrative candidates caused by a full-universe quote amendment."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    batch = _identifier(batch_id, "batch_id")
    review = _identifier(review_id, "review_id")
    prepared = _aware(prepared_at, "prepared_at")
    inputs = _load_completed_inputs(
        base=base,
        repository_root=repository_root,
        run_id=run,
        batch_id=batch,
        quote_amendment_path=quote_amendment_path,
        policy_path=policy_path,
    )
    if prepared < _parse_datetime(
        inputs["amendment"]["effective_at"],
        "quote amendment effective_at",
    ):
        raise ManagerScreenQuoteImpactError(
            "prepared_at cannot predate quote amendment effective_at"
        )
    if prepared < _parse_datetime(
        inputs["result"]["recorded_at"],
        "manager result recorded_at",
    ):
        raise ManagerScreenQuoteImpactError("prepared_at cannot predate manager result")

    rows = _candidate_rows(inputs)
    review_dir = base / "manager-screen" / run / batch / "quote-impact-reviews" / review
    plan_path = review_dir / "plan.json"
    packet_path = review_dir / "packet.json"
    plan = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch,
        "review_id": review,
        "prepared_at": prepared.isoformat(),
        "batch_path": _relative(inputs["batch_path"], repository_root),
        "batch_sha256": inputs["batch_seal"].sha256,
        "original_packet_path": _relative(
            inputs["packet_path"],
            repository_root,
        ),
        "original_packet_sha256": inputs["packet_seal"].sha256,
        "original_result_path": _relative(
            inputs["result_path"],
            repository_root,
        ),
        "original_result_sha256": inputs["result_seal"].sha256,
        "quote_amendment_path": _relative(
            inputs["amendment_path"],
            repository_root,
        ),
        "quote_amendment_sha256": inputs["amendment_seal"].sha256,
        "policy": inputs["policy_ref"],
        "candidate_count": len(rows),
        "candidate_symbols": [row["symbol"] for row in rows],
        "selection_rule": {
            "kind": "absolute_price_change_pct",
            "threshold_pct": inputs["policy_ref"]["absolute_price_change_pct"],
            "administrative_candidates_only": True,
            "programmatic_route_change": False,
        },
        "portfolio_action": None,
    }
    if plan_path.exists():
        existing, plan_seal = _sealed_object(
            plan_path,
            artifact_type="manager_screen_quote_impact_plan",
        )
        if existing != plan:
            raise ManagerScreenQuoteImpactError(
                "sealed quote-impact plan conflicts with prepare request"
            )
    else:
        plan_seal = seal_json(
            plan_path,
            plan,
            artifact_type="manager_screen_quote_impact_plan",
            sealed_at=prepared,
        )

    instructions = [
        "Price movement only creates an administrative review candidate.",
        "Do not infer or change a route programmatically.",
        "The original investment manager must review every candidate.",
        (
            "Provide a complete replacement manager-screen decision; v2 keep "
            "is forbidden because its canonical fact line contains stale valuation."
            if inputs["decision_contract_version"] == 2
            else "Choose keep or provide a complete replacement manager-screen decision."
        ),
    ]
    packet = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch,
        "review_id": review,
        "created_at": prepared.isoformat(),
        "plan_path": _relative(plan_path, repository_root),
        "plan_sha256": plan_seal.sha256,
        "instructions": instructions,
        "candidate_count": len(rows),
        "rows": rows,
        "portfolio_action": None,
    }
    if packet_path.exists():
        existing, packet_seal = _sealed_object(
            packet_path,
            artifact_type="manager_screen_quote_impact_packet",
        )
        if existing != packet:
            raise ManagerScreenQuoteImpactError(
                "sealed quote-impact packet conflicts with prepare request"
            )
    else:
        packet_seal = seal_json(
            packet_path,
            packet,
            artifact_type="manager_screen_quote_impact_packet",
            sealed_at=prepared,
        )
    return {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch,
        "review_id": review,
        "state": "prepared",
        "candidate_count": len(rows),
        "candidate_symbols": [row["symbol"] for row in rows],
        "plan_path": _relative(plan_path, repository_root),
        "plan_sha256": plan_seal.sha256,
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_seal.sha256,
        "portfolio_action": None,
    }


@serialized_coverage_write
def record_manager_screen_quote_impact(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    review_id: str,
    submission: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Seal original-manager decisions and crash-safely materialize replacements."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    batch = _identifier(batch_id, "batch_id")
    review = _identifier(review_id, "review_id")
    recorded = _aware(recorded_at, "recorded_at")
    verified = _verify_review(
        base=base,
        repository_root=repository_root,
        run_id=run,
        batch_id=batch,
        review_id=review,
        require_result=False,
    )
    _validate_verified_review_semantics(verified)
    plan = verified["plan"]
    packet = verified["packet"]
    if recorded < _parse_datetime(plan["prepared_at"], "plan prepared_at"):
        raise ManagerScreenQuoteImpactError("recorded_at cannot predate quote-impact preparation")
    normalized = _normalize_submission(
        submission,
        packet=packet,
        plan=plan,
    )
    original_manager = verified["original_result"].get("manager")
    if not isinstance(original_manager, Mapping) or normalized["manager"] != dict(original_manager):
        expected_agent = (
            original_manager.get("agent") if isinstance(original_manager, Mapping) else None
        )
        raise ManagerScreenQuoteImpactError(
            "quote-impact review must be recorded by the original investment "
            f"manager with identical provenance: expected {expected_agent}"
        )

    result_path = verified["review_dir"] / "result.json"
    if result_path.exists():
        complete = _verify_review(
            base=base,
            repository_root=repository_root,
            run_id=run,
            batch_id=batch,
            review_id=review,
            require_result=True,
        )
        existing = complete["result"]
        if any(existing[key] != normalized[key] for key in ("manager", "reviews", "decisions")):
            raise ManagerScreenQuoteImpactError("sealed quote-impact result is immutable")
        _enforce_capacity(
            base=base,
            run_id=run,
            plan=plan,
            reviews=existing["reviews"],
        )
        _materialize_replacements(
            base=base,
            repository_root=repository_root,
            plan=plan,
            packet=packet,
            result=existing,
            result_path=result_path,
            result_sha256=complete["result_seal"].sha256,
        )
        return _record_summary(
            existing,
            result_path=result_path,
            result_sha256=complete["result_seal"].sha256,
            repository_root=repository_root,
            idempotent=True,
        )

    _enforce_capacity(
        base=base,
        run_id=run,
        plan=plan,
        reviews=normalized["reviews"],
    )
    result = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch,
        "review_id": review,
        "recorded_at": recorded.isoformat(),
        "plan_path": _relative(verified["plan_path"], repository_root),
        "plan_sha256": verified["plan_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "original_result_path": plan["original_result_path"],
        "original_result_sha256": plan["original_result_sha256"],
        "quote_amendment_path": plan["quote_amendment_path"],
        "quote_amendment_sha256": plan["quote_amendment_sha256"],
        "policy_payload_sha256": plan["policy"]["payload_sha256"],
        "manager": normalized["manager"],
        "reviews": normalized["reviews"],
        "decisions": normalized["decisions"],
        "summary": {
            "candidate_count": len(normalized["reviews"]),
            "keep_count": sum(row["action"] == "keep" for row in normalized["reviews"]),
            "replacement_count": sum(
                row["action"] == "replacement" for row in normalized["reviews"]
            ),
            "new_send_to_analyst_count": sum(
                row["action"] == "replacement"
                and row["old_route"] != "send_to_analyst"
                and row["effective_decision"]["route"] == "send_to_analyst"
                for row in normalized["reviews"]
            ),
        },
        "portfolio_action": None,
    }
    result_seal = seal_json(
        result_path,
        result,
        artifact_type="manager_screen_quote_impact_result",
        sealed_at=recorded,
    )
    _materialize_replacements(
        base=base,
        repository_root=repository_root,
        plan=plan,
        packet=packet,
        result=result,
        result_path=result_path,
        result_sha256=result_seal.sha256,
    )
    return _record_summary(
        result,
        result_path=result_path,
        result_sha256=result_seal.sha256,
        repository_root=repository_root,
        idempotent=False,
    )


def manager_screen_quote_impact_status(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    review_id: str,
) -> dict[str, Any]:
    base = Path(root)
    repository_root = base.parent.parent.resolve()
    verified = _verify_review(
        base=base,
        repository_root=repository_root,
        run_id=_identifier(run_id, "run_id"),
        batch_id=_identifier(batch_id, "batch_id"),
        review_id=_identifier(review_id, "review_id"),
        require_result=False,
    )
    _validate_verified_review_semantics(verified)
    result = verified.get("result")
    materialized = 0
    if result is not None:
        queue = {
            row["symbol"]: row
            for row in read_jsonl(base / RESEARCH_QUEUE_FILE)
            if isinstance(row.get("symbol"), str)
        }
        result_relative = _relative(verified["result_path"], repository_root)
        result_sha256 = verified["result_seal"].sha256
        materialized = sum(
            row["action"] == "replacement"
            and (queue.get(row["symbol"]) or {}).get("manager_screen_result_path")
            == result_relative
            and (queue.get(row["symbol"]) or {}).get("manager_screen_result_sha256")
            == result_sha256
            for row in result["reviews"]
        )
    return {
        "schema_version": 1,
        "run_id": verified["plan"]["run_id"],
        "batch_id": verified["plan"]["batch_id"],
        "review_id": verified["plan"]["review_id"],
        "state": "recorded" if result is not None else "prepared",
        "candidate_count": verified["plan"]["candidate_count"],
        "replacement_count": (result["summary"]["replacement_count"] if result is not None else 0),
        "materialized_replacement_count": materialized,
        "plan_path": _relative(verified["plan_path"], repository_root),
        "plan_sha256": verified["plan_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "result_path": (
            _relative(verified["result_path"], repository_root) if result is not None else None
        ),
        "result_sha256": (verified["result_seal"].sha256 if result is not None else None),
        "portfolio_action": None,
    }


def load_manager_screen_quote_impact_overlay(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
) -> dict[str, Any]:
    """Discover and verify the single quote-impact overlay for a completed batch."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    batch = _identifier(batch_id, "batch_id")
    reviews_root = base / "manager-screen" / run / batch / "quote-impact-reviews"
    empty = {
        "state": "absent",
        "review_id": None,
        "candidate_count": 0,
        "keep_count": 0,
        "replacement_count": 0,
        "new_send_to_analyst_count": 0,
        "plan_path": None,
        "plan_sha256": None,
        "packet_path": None,
        "packet_sha256": None,
        "result_path": None,
        "result_sha256": None,
        "effective_route_delta": {route: 0 for route in sorted(ROUTES)},
        "decisions": [],
        "reviews": [],
        "quick_profile_effort_budget_hours": None,
    }
    if not reviews_root.exists():
        return empty
    if not reviews_root.is_dir():
        raise ManagerScreenQuoteImpactError(
            "quote-impact reviews path is not a directory"
        )
    entries = sorted(reviews_root.iterdir(), key=lambda path: path.name)
    if any(not entry.is_dir() for entry in entries):
        raise ManagerScreenQuoteImpactError(
            "quote-impact reviews directory contains an unexpected file"
        )
    if not entries:
        return empty
    if len(entries) != 1:
        raise ManagerScreenQuoteImpactError(
            "manager-screen batch must have at most one quote-impact review"
        )
    review_id = _identifier(entries[0].name, "review_id")
    verified = _verify_review(
        base=base,
        repository_root=repository_root,
        run_id=run,
        batch_id=batch,
        review_id=review_id,
        require_result=False,
    )
    _validate_verified_review_semantics(verified)
    plan = verified["plan"]
    result = verified["result"]
    common = {
        **empty,
        "state": "recorded" if result is not None else "prepared",
        "review_id": review_id,
        "candidate_count": plan["candidate_count"],
        "plan_path": _relative(verified["plan_path"], repository_root),
        "plan_sha256": verified["plan_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "quick_profile_effort_budget_hours": plan["policy"][
            "quick_profile_effort_budget_hours"
        ],
    }
    if result is None:
        return common
    route_delta: Counter[str] = Counter()
    for review in result["reviews"]:
        if review["action"] != "replacement":
            continue
        route_delta[review["old_route"]] -= 1
        route_delta[review["effective_decision"]["route"]] += 1
    return {
        **common,
        "keep_count": result["summary"]["keep_count"],
        "replacement_count": result["summary"]["replacement_count"],
        "new_send_to_analyst_count": result["summary"][
            "new_send_to_analyst_count"
        ],
        "result_path": _relative(verified["result_path"], repository_root),
        "result_sha256": verified["result_seal"].sha256,
        "effective_route_delta": {
            route: route_delta[route] for route in sorted(ROUTES)
        },
        "decisions": [dict(decision) for decision in result["decisions"]],
        "reviews": [dict(review) for review in result["reviews"]],
    }


def _candidate_rows(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    decisions = {row["symbol"]: row for row in inputs["result"]["decisions"]}
    dossiers = {row["symbol"]: row for row in inputs["packet"]["dossiers"]}
    quotes = {row["symbol"]: row for row in inputs["amendment"]["quotes"]}
    threshold = inputs["policy_ref"]["absolute_price_change_pct"]
    rows = []
    for decision in inputs["result"]["decisions"]:
        symbol = decision["symbol"]
        dossier = dossiers.get(symbol)
        quote = quotes.get(symbol)
        if not isinstance(dossier, Mapping) or not isinstance(quote, Mapping):
            raise ManagerScreenQuoteImpactError(f"quote-impact inputs are missing symbol: {symbol}")
        market = dossier.get("market_snapshot")
        if not isinstance(market, Mapping):
            raise ManagerScreenQuoteImpactError(f"original market snapshot is invalid: {symbol}")
        old_price = _price_for_comparison(market.get("price"))
        new_price = _price_for_comparison(quote.get("price"))
        invalid_price_fields = [
            field
            for field, value in (
                ("old_price", old_price),
                ("new_price", new_price),
            )
            if value is None
        ]
        if invalid_price_fields:
            delta = None
        else:
            delta = round((new_price / old_price - 1.0) * 100.0, 6)
        if delta is not None and abs(delta) + 1e-12 < threshold:
            continue
        quote_evidence_id = f"quote-amendment:{inputs['amendment']['amendment_id']}:{symbol}"
        local_evidence = dossier.get("evidence_catalog")
        local_ids = (
            [
                item["evidence_id"]
                for item in local_evidence
                if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
            ]
            if isinstance(local_evidence, list)
            else []
        )
        row = {
            "ordinal": len(rows) + 1,
            "symbol": symbol,
            "name": dossier.get("name"),
            "old_price": (old_price if old_price is not None else market.get("price")),
            "new_price": (new_price if new_price is not None else quote.get("price")),
            "price_change_pct": delta,
            "absolute_price_change_pct": (abs(delta) if delta is not None else None),
            "old_decision": dict(decisions[symbol]),
            "valuation": {
                "old": {field: market.get(field) for field in VALUATION_FIELDS},
                "new": {field: quote.get(field) for field in VALUATION_FIELDS},
            },
            "quote": {
                "as_of": quote.get("as_of"),
                "source": quote.get("source"),
                "fetched_at": quote.get("fetched_at"),
                "evidence_id": quote_evidence_id,
            },
            "allowed_evidence_ids": list(
                dict.fromkeys(
                    [
                        *local_ids,
                        *decision.get("evidence_ids", []),
                        quote_evidence_id,
                    ]
                )
            ),
        }
        if inputs["decision_contract_version"] == 2:
            row["decision_support"] = _quote_decision_support(
                dossier=dossier,
                quote=quote,
                batch_policy=inputs["batch"]["policy"],
                canonical_source_evidence_id=quote_evidence_id,
            )
        if invalid_price_fields:
            row.update(
                {
                    "comparison_status": "not_comparable",
                    "candidate_reason": "price_not_comparable",
                    "invalid_price_fields": invalid_price_fields,
                    "requires_manual_review": True,
                }
            )
        rows.append(row)
    return rows


def _quote_decision_support(
    *,
    dossier: Mapping[str, Any],
    quote: Mapping[str, Any],
    batch_policy: Mapping[str, Any],
    canonical_source_evidence_id: str,
) -> dict[str, Any]:
    inputs = _quote_decision_support_inputs(
        dossier=dossier,
        quote=quote,
        batch_policy=batch_policy,
        canonical_source_evidence_id=canonical_source_evidence_id,
    )
    try:
        return build_decision_support(**inputs)
    except ManagerScreenDecisionQualityError as exc:
        raise ManagerScreenQuoteImpactError(
            "v2 quote-impact decision support is invalid"
        ) from exc


def _quote_decision_support_inputs(
    *,
    dossier: Mapping[str, Any],
    quote: Mapping[str, Any],
    batch_policy: Mapping[str, Any],
    canonical_source_evidence_id: str,
) -> dict[str, Any]:
    market = dossier.get("market_snapshot")
    if not isinstance(market, Mapping):
        raise ManagerScreenQuoteImpactError(
            "v2 quote-impact dossier market snapshot is invalid"
        )
    amended_market = dict(market)
    amended_market["price"] = quote.get("price")
    for field in VALUATION_FIELDS:
        amended_market[field] = quote.get(field)
    facts = amended_market.get("manager_screen_facts")
    if not isinstance(facts, Mapping):
        raise ManagerScreenQuoteImpactError(
            "v2 quote-impact dossier facts are invalid"
        )
    facts = dict(facts)
    facts.pop("decision_support", None)
    amended_market["manager_screen_facts"] = facts
    threshold = _positive_number(
        batch_policy.get("high_liability_to_assets_pct"),
        "high_liability_to_assets_pct",
    )
    if threshold > 100:
        raise ManagerScreenQuoteImpactError(
            "high_liability_to_assets_pct must be at most 100"
        )
    return {
        "symbol": dossier.get("symbol"),
        "name": dossier.get("name"),
        "market_snapshot": amended_market,
        "facts": facts,
        "prior_screening": (
            dossier.get("prior_screening")
            if isinstance(dossier.get("prior_screening"), Mapping)
            else None
        ),
        "timeline": (
            dossier.get("timeline")
            if isinstance(dossier.get("timeline"), Mapping)
            else None
        ),
        "high_liability_to_assets_pct": threshold,
        "canonical_source_evidence_id": canonical_source_evidence_id,
    }


def _price_for_comparison(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        return None
    return result


def _load_completed_inputs(
    *,
    base: Path,
    repository_root: Path,
    run_id: str,
    batch_id: str,
    quote_amendment_path: str | Path,
    policy_path: str | Path,
) -> dict[str, Any]:
    batch_dir = base / "manager-screen" / run_id / batch_id
    batch_path = batch_dir / "batch.json"
    packet_path = batch_dir / "packet.json"
    result_path = batch_dir / "result.json"
    batch, batch_seal = _sealed_object(
        batch_path,
        artifact_type="manager_screen_batch",
    )
    packet, packet_seal = _sealed_object(
        packet_path,
        artifact_type="manager_screen_packet",
    )
    result, result_seal = _sealed_object(
        result_path,
        artifact_type="manager_screen_result",
    )
    expected_batch_path = _relative(batch_path, repository_root)
    expected_packet_path = _relative(packet_path, repository_root)
    if (
        batch.get("run_id") != run_id
        or batch.get("batch_id") != batch_id
        or packet.get("run_id") != run_id
        or packet.get("batch_id") != batch_id
        or packet.get("batch_path") != expected_batch_path
        or packet.get("batch_sha256") != batch_seal.sha256
        or result.get("run_id") != run_id
        or result.get("batch_id") != batch_id
        or result.get("batch_path") != expected_batch_path
        or result.get("batch_sha256") != batch_seal.sha256
        or result.get("packet_path") != expected_packet_path
        or result.get("packet_sha256") != packet_seal.sha256
    ):
        raise ManagerScreenQuoteImpactError(
            "completed manager-screen inputs do not bind one another"
        )
    decisions = result.get("decisions")
    dossiers = packet.get("dossiers")
    if not isinstance(decisions, list) or not isinstance(dossiers, list):
        raise ManagerScreenQuoteImpactError(
            "completed manager-screen decisions or dossiers are invalid"
        )
    decision_symbols = [row.get("symbol") for row in decisions if isinstance(row, Mapping)]
    dossier_symbols = [row.get("symbol") for row in dossiers if isinstance(row, Mapping)]
    if (
        len(decision_symbols) != len(decisions)
        or decision_symbols != dossier_symbols
        or len(decision_symbols) != len(set(decision_symbols))
    ):
        raise ManagerScreenQuoteImpactError(
            "manager-screen result and packet symbol order is inconsistent"
        )
    batch_policy = batch.get("policy")
    if not isinstance(batch_policy, Mapping):
        raise ManagerScreenQuoteImpactError(
            "sealed manager-screen batch policy is invalid"
        )
    decision_contract_version = batch_policy.get("decision_contract_version", 1)
    if decision_contract_version not in {1, 2}:
        raise ManagerScreenQuoteImpactError(
            "sealed manager-screen decision contract version is invalid"
        )
    if decision_contract_version == 2 and (
        not DECISION_V2_POLICY_KEYS.issubset(batch_policy)
        or batch_policy.get("mandatory_risk_acknowledgement") is not True
        or batch_policy.get("canonical_fact_line_required") is not True
    ):
        raise ManagerScreenQuoteImpactError(
            "sealed manager-screen decision v2 policy is incomplete"
        )
    expected_decision_keys = (
        DECISION_V2_KEYS if decision_contract_version == 2 else DECISION_KEYS
    )
    for decision in decisions:
        if (
            not isinstance(decision, Mapping)
            or set(decision) != expected_decision_keys
        ):
            raise ManagerScreenQuoteImpactError(
                "original manager-screen decision contract is invalid"
            )

    amendment_path = _repository_file(
        quote_amendment_path,
        repository_root=repository_root,
    )
    amendment, amendment_seal = _sealed_object(
        amendment_path,
        artifact_type="manager_screen_quote_amendment",
    )
    if amendment.get("run_id") != run_id:
        raise ManagerScreenQuoteImpactError("quote amendment run does not match manager-screen run")
    quotes = amendment.get("quotes")
    if not isinstance(quotes, list) or amendment.get("quote_count") != len(quotes):
        raise ManagerScreenQuoteImpactError("quote amendment quote_count is invalid")
    quote_symbols = [row.get("symbol") for row in quotes if isinstance(row, Mapping)]
    if len(quote_symbols) != len(quotes) or len(quote_symbols) != len(set(quote_symbols)):
        raise ManagerScreenQuoteImpactError("quote amendment symbols are invalid or duplicated")
    base_snapshot_path = _repository_file(
        amendment.get("base_snapshot_path"),
        repository_root=repository_root,
    )
    if hashlib.sha256(base_snapshot_path.read_bytes()).hexdigest() != amendment.get(
        "base_snapshot_sha256"
    ):
        raise ManagerScreenQuoteImpactError("quote amendment base snapshot binding is invalid")
    base_symbols = [row.get("symbol") for row in read_jsonl(base_snapshot_path)]
    if len(base_symbols) != len(set(base_symbols)) or set(base_symbols) != set(quote_symbols):
        raise ManagerScreenQuoteImpactError(
            "quote amendment does not cover the full frozen universe"
        )

    policy_file = Path(policy_path)
    if not policy_file.is_absolute():
        policy_file = repository_root / policy_file
    policy_file = policy_file.resolve()
    try:
        policy_file.relative_to(repository_root)
    except ValueError as exc:
        raise ManagerScreenQuoteImpactError("manager-screen policy escaped repository") from exc
    policy = load_policy(policy_file)
    if policy.kind != PolicyKind.MANAGER_SCREENING:
        raise ManagerScreenQuoteImpactError("quote-impact policy must be manager_screening")
    payload = dict(policy.payload)
    threshold = payload.get(
        PRICE_CHANGE_POLICY_KEY,
        DEFAULT_ABSOLUTE_PRICE_CHANGE_PCT,
    )
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or float(threshold) <= 0
    ):
        raise ManagerScreenQuoteImpactError(f"{PRICE_CHANGE_POLICY_KEY} must be positive")
    capacity = payload.get("send_to_analyst_capacity_per_run")
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise ManagerScreenQuoteImpactError("send_to_analyst_capacity_per_run must be positive")
    reason_max = _positive_int(
        payload.get("one_line_reason_max_chars"),
        "one_line_reason_max_chars",
    )
    question_max = _positive_int(
        payload.get("decisive_question_max_chars"),
        "decisive_question_max_chars",
    )
    effort = _positive_number(
        payload.get("quick_profile_effort_budget_hours"),
        "quick_profile_effort_budget_hours",
    )
    stops = payload.get("quick_profile_stop_conditions")
    if (
        not isinstance(stops, list)
        or not stops
        or not all(isinstance(row, str) and row.strip() for row in stops)
    ):
        raise ManagerScreenQuoteImpactError("quick_profile_stop_conditions are invalid")
    decision_policy_ref = (
        {
            key: batch_policy[key]
            for key in DECISION_V2_POLICY_KEYS
        }
        if decision_contract_version == 2
        else {}
    )
    return {
        "batch_path": batch_path,
        "batch": batch,
        "batch_seal": batch_seal,
        "packet_path": packet_path,
        "packet": packet,
        "packet_seal": packet_seal,
        "result_path": result_path,
        "result": result,
        "result_seal": result_seal,
        "amendment_path": amendment_path,
        "amendment": amendment,
        "amendment_seal": amendment_seal,
        "policy_ref": {
            "policy_id": policy.policy_id,
            "version": policy.version,
            "path": _relative(policy_file, repository_root),
            "file_sha256": hashlib.sha256(policy_file.read_bytes()).hexdigest(),
            "payload_sha256": hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
            "absolute_price_change_pct": float(threshold),
            "send_to_analyst_capacity_per_run": capacity,
            "one_line_reason_max_chars": reason_max,
            "decisive_question_max_chars": question_max,
            "quick_profile_effort_budget_hours": effort,
            "quick_profile_stop_conditions": [row.strip() for row in stops],
            "payload": payload,
            **decision_policy_ref,
        },
        "decision_contract_version": decision_contract_version,
    }


def _normalize_submission(
    value: Mapping[str, Any],
    *,
    packet: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != SUBMISSION_KEYS:
        raise ManagerScreenQuoteImpactError("quote-impact submission fields do not match v1")
    if value.get("schema_version") != 1:
        raise ManagerScreenQuoteImpactError("quote-impact submission schema_version must be 1")
    manager = _manager(value.get("manager"))
    reviews = value.get("reviews")
    rows = packet.get("rows")
    if not isinstance(reviews, list) or not isinstance(rows, list):
        raise ManagerScreenQuoteImpactError("quote-impact reviews must be an array")
    expected = [row["symbol"] for row in rows]
    received = [row.get("symbol") for row in reviews if isinstance(row, Mapping)]
    if received != expected or len(reviews) != len(expected):
        raise ManagerScreenQuoteImpactError(
            "quote-impact reviews must cover every candidate exactly once and in packet order"
        )
    reason_max = plan["policy"]["one_line_reason_max_chars"]
    question_max = plan["policy"]["decisive_question_max_chars"]
    decision_contract_version = plan["policy"].get(
        "decision_contract_version",
        1,
    )
    normalized_reviews = []
    decisions = []
    for raw, packet_row in zip(reviews, rows, strict=True):
        if not isinstance(raw, Mapping) or set(raw) != REVIEW_KEYS:
            raise ManagerScreenQuoteImpactError("quote-impact review fields do not match v1")
        symbol = _symbol(raw.get("symbol"))
        action = raw.get("action")
        old_decision = dict(packet_row["old_decision"])
        if action == "keep":
            if decision_contract_version == 2:
                raise ManagerScreenQuoteImpactError(
                    f"v2 quote-impact review requires a complete replacement: {symbol}"
                )
            if raw.get("replacement") is not None:
                raise ManagerScreenQuoteImpactError(
                    f"keep review cannot contain replacement: {symbol}"
                )
            effective = old_decision
            replacement = None
        elif action == "replacement":
            effective = _decision(
                raw.get("replacement"),
                symbol=symbol,
                allowed_evidence=set(packet_row["allowed_evidence_ids"]),
                reason_max=reason_max,
                question_max=question_max,
                decision_contract_version=decision_contract_version,
                decision_support=packet_row.get("decision_support"),
            )
            replacement = effective
        else:
            raise ManagerScreenQuoteImpactError(f"invalid quote-impact action: {action}")
        normalized_reviews.append(
            {
                "symbol": symbol,
                "action": action,
                "old_route": old_decision["route"],
                "replacement": replacement,
                "effective_decision": effective,
            }
        )
        decisions.append(effective)
    return {
        "manager": manager,
        "reviews": normalized_reviews,
        "decisions": decisions,
    }


def _decision(
    value: Any,
    *,
    symbol: str,
    allowed_evidence: set[str],
    reason_max: int,
    question_max: int,
    decision_contract_version: int,
    decision_support: Any,
) -> dict[str, Any]:
    expected_keys = (
        DECISION_V2_KEYS if decision_contract_version == 2 else DECISION_KEYS
    )
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ManagerScreenQuoteImpactError(
            f"replacement decision fields do not match contract: {symbol}"
        )
    if _symbol(value.get("symbol")) != symbol:
        raise ManagerScreenQuoteImpactError(f"replacement decision symbol mismatch: {symbol}")
    route = value.get("route")
    if route not in ROUTES:
        raise ManagerScreenQuoteImpactError(f"invalid replacement route: {route}")
    reason = _text(value.get("one_line_reason"), f"{symbol}.one_line_reason")
    if decision_contract_version == 2:
        try:
            reason = validate_canonical_reason(reason, decision_support)
        except ManagerScreenDecisionQualityError as exc:
            raise ManagerScreenQuoteImpactError(
                f"{symbol}.one_line_reason violates the v2 canonical contract"
            ) from exc
    if "\n" in reason or "\r" in reason or len(reason) > reason_max:
        raise ManagerScreenQuoteImpactError(f"{symbol}.one_line_reason is invalid")
    question = _text(
        value.get("decisive_question"),
        f"{symbol}.decisive_question",
    )
    if len(question) > question_max:
        raise ManagerScreenQuoteImpactError(f"{symbol}.decisive_question is too long")
    triggers = _triggers(value.get("revisit_triggers"), symbol=symbol)
    if route in {"pass", "watch"} and not triggers:
        raise ManagerScreenQuoteImpactError(
            f"{route} replacement requires a revisit trigger: {symbol}"
        )
    confidence = value.get("confidence")
    if confidence not in CONFIDENCES:
        raise ManagerScreenQuoteImpactError(f"invalid replacement confidence: {symbol}")
    evidence_ids = value.get("evidence_ids")
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or not all(isinstance(row, str) and row for row in evidence_ids)
        or len(evidence_ids) != len(set(evidence_ids))
        or not set(evidence_ids).issubset(allowed_evidence)
    ):
        raise ManagerScreenQuoteImpactError(
            f"{symbol}.evidence_ids are invalid or outside the packet"
        )
    result = {
        "symbol": symbol,
        "route": route,
        "one_line_reason": reason,
        "decisive_question": question,
        "revisit_triggers": triggers,
        "confidence": confidence,
        "evidence_ids": list(evidence_ids),
    }
    if decision_contract_version == 2:
        try:
            result["risk_acknowledgements"] = validate_risk_acknowledgements(
                value.get("risk_acknowledgements"),
                support=decision_support,
                decision_evidence_ids=evidence_ids,
                one_line_reason=reason,
                decisive_question=question,
            )
        except ManagerScreenDecisionQualityError as exc:
            raise ManagerScreenQuoteImpactError(
                f"{symbol}.risk_acknowledgements violate the v2 contract"
            ) from exc
    return result


def _triggers(value: Any, *, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagerScreenQuoteImpactError(f"{symbol}.revisit_triggers must be an array")
    result = []
    for row in value:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"type", "condition", "reason"}
            or row.get("type") not in TRIGGER_TYPES
        ):
            raise ManagerScreenQuoteImpactError(f"{symbol}.revisit trigger is invalid")
        condition = row.get("condition")
        if isinstance(condition, str):
            condition = _text(
                condition,
                f"{symbol}.trigger.condition",
            )
        elif isinstance(condition, Mapping) and condition:
            condition = dict(condition)
        else:
            raise ManagerScreenQuoteImpactError(f"{symbol}.trigger.condition is invalid")
        result.append(
            {
                "type": row["type"],
                "condition": condition,
                "reason": _text(
                    row.get("reason"),
                    f"{symbol}.trigger.reason",
                ),
            }
        )
    return result


def _enforce_capacity(
    *,
    base: Path,
    run_id: str,
    plan: Mapping[str, Any],
    reviews: list[Mapping[str, Any]],
) -> None:
    capacity = plan["policy"]["send_to_analyst_capacity_per_run"]
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    queue_by_symbol = {row["symbol"]: row for row in queue if isinstance(row.get("symbol"), str)}
    if len(queue_by_symbol) != len(queue):
        raise ManagerScreenQuoteImpactError("research queue symbols are missing or duplicated")
    final_routes = {
        symbol: row.get("manager_screen_route")
        for symbol, row in queue_by_symbol.items()
        if row.get("manager_screen_run_id") == run_id
    }
    committed_before = sum(route == "send_to_analyst" for route in final_routes.values())
    for review in reviews:
        if review["action"] != "replacement":
            continue
        symbol = review["symbol"]
        current = queue_by_symbol.get(symbol)
        if current is None:
            raise ManagerScreenQuoteImpactError(
                f"research queue is missing replacement candidate: {symbol}"
            )
        if current.get("manager_screen_run_id") != run_id:
            raise ManagerScreenQuoteImpactError(
                f"replacement candidate belongs to a different run: {symbol}"
            )
        final_routes[symbol] = review["effective_decision"]["route"]
    committed_after = sum(route == "send_to_analyst" for route in final_routes.values())
    if committed_after > capacity:
        raise ManagerScreenQuoteImpactError(
            "quote-impact replacements exceed manager-screen "
            "send_to_analyst run capacity after final materialization: "
            f"{committed_before} committed before, "
            f"{committed_after} committed after > {capacity}"
        )


def _materialize_replacements(
    *,
    base: Path,
    repository_root: Path,
    plan: Mapping[str, Any],
    packet: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: Path,
    result_sha256: str,
) -> None:
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue_rows = read_jsonl(queue_path)
    screening_rows = read_jsonl(screening_path)
    queue = {row["symbol"]: dict(row) for row in queue_rows}
    screening = {row["symbol"]: dict(row) for row in screening_rows}
    packet_rows = {row["symbol"]: row for row in packet["rows"]}
    result_relative = _relative(result_path, repository_root)
    queue_changed = False
    screening_changed = False
    for review in result["reviews"]:
        if review["action"] != "replacement":
            continue
        symbol = review["symbol"]
        decision = review["effective_decision"]
        current = queue.get(symbol)
        if current is None:
            raise ManagerScreenQuoteImpactError(
                f"research queue is missing replacement candidate: {symbol}"
            )
        binding = current.get("manager_screen_result_path")
        if binding not in {
            plan["original_result_path"],
            result_relative,
        }:
            raise ManagerScreenQuoteImpactError(
                f"coverage has a different manager result binding: {symbol}"
            )
        already_bound = (
            binding == result_relative
            and current.get("manager_screen_result_sha256") == result_sha256
        )
        later_progress = _has_later_progress(current)
        updated = dict(current)
        history = list(updated.get("stage_history") or [])
        if not any(
            isinstance(row, Mapping)
            and row.get("stage") == "manager_screen_quote_impact"
            and row.get("result_sha256") == result_sha256
            for row in history
        ):
            history.append(
                {
                    "stage": "manager_screen_quote_impact",
                    "status": "completed",
                    "finished_at": result["recorded_at"],
                    "run_id": plan["run_id"],
                    "batch_id": plan["batch_id"],
                    "review_id": plan["review_id"],
                    "old_route": review["old_route"],
                    "route": decision["route"],
                    "result_path": result_relative,
                    "result_sha256": result_sha256,
                }
            )
        updated.update(
            {
                "manager_screen_run_id": plan["run_id"],
                "manager_screen_batch_id": plan["batch_id"],
                "manager_screen_route": decision["route"],
                "manager_screen_result_path": result_relative,
                "manager_screen_result_sha256": result_sha256,
                "decisive_question": decision["decisive_question"],
                "revisit_triggers": decision["revisit_triggers"],
                "evidence_ids": decision["evidence_ids"],
                "stage_history": history,
            }
        )
        if not later_progress:
            updated.update(
                {
                    "priority": 3,
                    "reason": decision["one_line_reason"],
                    "assigned_agent": None,
                    "started_at": None,
                    "failure_reason": None,
                }
            )
            if decision["route"] == "send_to_analyst":
                updated.update(
                    {
                        "task_type": "quick_profile",
                        "status": "pending",
                        "finished_at": None,
                        "result_path": None,
                        "next_action": (
                            "Assign one analyst to resolve the amended "
                            "manager-screen decisive question."
                        ),
                        "effort_budget_hours": plan["policy"]["quick_profile_effort_budget_hours"],
                        "preceding_stage": "manager_screen",
                        "stop_conditions": list(plan["policy"]["quick_profile_stop_conditions"]),
                    }
                )
            else:
                updated.update(
                    {
                        "task_type": "manager_screen",
                        "status": "completed",
                        "finished_at": result["recorded_at"],
                        "result_path": result_relative,
                        "next_action": (
                            "Wait for an executable restart trigger."
                            if decision["route"] == "pass"
                            else "Reassess on the sealed watch trigger."
                        ),
                    }
                )
                for field in (
                    "effort_budget_hours",
                    "preceding_stage",
                    "stop_conditions",
                ):
                    updated.pop(field, None)
        if updated != current:
            queue[symbol] = updated
            queue_changed = True

        old_screen = screening.get(symbol)
        if not later_progress:
            screen = dict(old_screen or {})
            screen.update(
                {
                    "symbol": symbol,
                    "name": packet_rows[symbol]["name"],
                    "decision": {
                        "pass": "catalog",
                        "watch": "watch_only",
                        "send_to_analyst": "quick_profile",
                    }[decision["route"]],
                    "priority": None,
                    "reason": decision["one_line_reason"],
                    "evidence": decision["evidence_ids"],
                    "next_action": updated["next_action"],
                    "manager_screen_run_id": plan["run_id"],
                    "manager_screen_batch_id": plan["batch_id"],
                    "manager_screen_route": decision["route"],
                    "manager_screen_result_path": result_relative,
                    "manager_screen_result_sha256": result_sha256,
                    "decisive_question": decision["decisive_question"],
                    "confidence": decision["confidence"],
                    "revisit_triggers": decision["revisit_triggers"],
                }
            )
            if screen != old_screen:
                screening[symbol] = screen
                screening_changed = True
        elif not already_bound:
            # The queue receives the immutable provenance binding, but all
            # operational and screening conclusions belong to later research.
            pass
    if queue_changed:
        write_jsonl(queue_path, list(queue.values()))
    if screening_changed:
        write_jsonl(screening_path, list(screening.values()))


def _has_later_progress(queue: Mapping[str, Any]) -> bool:
    task_type = queue.get("task_type")
    if task_type not in PROTECTED_TASK_TYPES:
        return False
    return not (
        task_type == "quick_profile"
        and queue.get("status") == "pending"
        and queue.get("assigned_agent") is None
    )


def _verify_review(
    *,
    base: Path,
    repository_root: Path,
    run_id: str,
    batch_id: str,
    review_id: str,
    require_result: bool,
) -> dict[str, Any]:
    review_dir = base / "manager-screen" / run_id / batch_id / "quote-impact-reviews" / review_id
    plan_path = review_dir / "plan.json"
    packet_path = review_dir / "packet.json"
    plan, plan_seal = _sealed_object(
        plan_path,
        artifact_type="manager_screen_quote_impact_plan",
    )
    packet, packet_seal = _sealed_object(
        packet_path,
        artifact_type="manager_screen_quote_impact_packet",
    )
    if (
        plan.get("run_id") != run_id
        or plan.get("batch_id") != batch_id
        or plan.get("review_id") != review_id
        or packet.get("run_id") != run_id
        or packet.get("batch_id") != batch_id
        or packet.get("review_id") != review_id
        or packet.get("plan_path") != _relative(plan_path, repository_root)
        or packet.get("plan_sha256") != plan_seal.sha256
        or packet.get("candidate_count") != plan.get("candidate_count")
        or [row.get("symbol") for row in packet.get("rows", [])] != plan.get("candidate_symbols")
    ):
        raise ManagerScreenQuoteImpactError("quote-impact plan and packet bindings are invalid")
    original_result_path = _repository_file(
        plan.get("original_result_path"),
        repository_root=repository_root,
    )
    batch_path = _repository_file(
        plan.get("batch_path"),
        repository_root=repository_root,
    )
    batch, batch_seal = _sealed_object(
        batch_path,
        artifact_type="manager_screen_batch",
    )
    original_packet_path = _repository_file(
        plan.get("original_packet_path"),
        repository_root=repository_root,
    )
    original_packet, original_packet_seal = _sealed_object(
        original_packet_path,
        artifact_type="manager_screen_packet",
    )
    original_result, original_result_seal = _sealed_object(
        original_result_path,
        artifact_type="manager_screen_result",
    )
    amendment_path = _repository_file(
        plan.get("quote_amendment_path"),
        repository_root=repository_root,
    )
    amendment, amendment_seal = _sealed_object(
        amendment_path,
        artifact_type="manager_screen_quote_amendment",
    )
    _verify_policy_binding(plan.get("policy"))
    if (
        batch_seal.sha256 != plan.get("batch_sha256")
        or original_packet_seal.sha256 != plan.get("original_packet_sha256")
        or original_result_seal.sha256 != plan.get("original_result_sha256")
        or amendment_seal.sha256 != plan.get("quote_amendment_sha256")
        or batch.get("run_id") != run_id
        or batch.get("batch_id") != batch_id
        or original_packet.get("run_id") != run_id
        or original_packet.get("batch_id") != batch_id
        or original_packet.get("batch_path") != _relative(batch_path, repository_root)
        or original_packet.get("batch_sha256") != batch_seal.sha256
        or original_result.get("run_id") != run_id
        or original_result.get("batch_id") != batch_id
        or original_result.get("batch_path") != _relative(batch_path, repository_root)
        or original_result.get("batch_sha256") != batch_seal.sha256
        or original_result.get("packet_path") != _relative(original_packet_path, repository_root)
        or original_result.get("packet_sha256") != original_packet_seal.sha256
        or amendment.get("run_id") != run_id
    ):
        raise ManagerScreenQuoteImpactError("quote-impact sealed input binding is invalid")
    result_path = review_dir / "result.json"
    result = None
    result_seal = None
    if result_path.exists():
        result, result_seal = _sealed_object(
            result_path,
            artifact_type="manager_screen_quote_impact_result",
        )
        if (
            result.get("run_id") != run_id
            or result.get("batch_id") != batch_id
            or result.get("review_id") != review_id
            or result.get("plan_path") != _relative(plan_path, repository_root)
            or result.get("plan_sha256") != plan_seal.sha256
            or result.get("packet_path") != _relative(packet_path, repository_root)
            or result.get("packet_sha256") != packet_seal.sha256
            or result.get("original_result_sha256") != plan["original_result_sha256"]
            or result.get("quote_amendment_sha256") != plan["quote_amendment_sha256"]
        ):
            raise ManagerScreenQuoteImpactError("quote-impact result bindings are invalid")
    elif require_result:
        raise ManagerScreenQuoteImpactError("quote-impact result is missing")
    return {
        "review_dir": review_dir,
        "plan_path": plan_path,
        "plan": plan,
        "plan_seal": plan_seal,
        "packet_path": packet_path,
        "packet": packet,
        "packet_seal": packet_seal,
        "batch": batch,
        "original_packet": original_packet,
        "original_result": original_result,
        "amendment": amendment,
        "result_path": result_path,
        "result": result,
        "result_seal": result_seal,
    }


def _verify_policy_binding(
    value: Any,
) -> None:
    if not isinstance(value, Mapping):
        raise ManagerScreenQuoteImpactError("quote-impact policy binding is invalid")
    for field in ("policy_id", "version", "path"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ManagerScreenQuoteImpactError(
                "quote-impact policy provenance is invalid"
            )
    for field in ("file_sha256", "payload_sha256"):
        digest = value.get(field)
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise ManagerScreenQuoteImpactError(
                "quote-impact policy digest is invalid"
            )
    _positive_number(
        value.get("absolute_price_change_pct"),
        "absolute_price_change_pct",
    )
    _positive_int(
        value.get("send_to_analyst_capacity_per_run"),
        "send_to_analyst_capacity_per_run",
    )
    _positive_int(
        value.get("one_line_reason_max_chars"),
        "one_line_reason_max_chars",
    )
    _positive_int(
        value.get("decisive_question_max_chars"),
        "decisive_question_max_chars",
    )
    _positive_number(
        value.get("quick_profile_effort_budget_hours"),
        "quick_profile_effort_budget_hours",
    )
    stops = value.get("quick_profile_stop_conditions")
    if (
        not isinstance(stops, list)
        or not stops
        or not all(isinstance(row, str) and row.strip() for row in stops)
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact policy stop conditions are invalid"
        )
    if DECISION_V2_POLICY_KEYS.intersection(value):
        if (
            not DECISION_V2_POLICY_KEYS.issubset(value)
            or value.get("decision_contract_version") != 2
            or value.get("mandatory_risk_acknowledgement") is not True
            or value.get("canonical_fact_line_required") is not True
        ):
            raise ManagerScreenQuoteImpactError(
                "quote-impact sealed decision v2 policy is invalid"
            )
        liability_threshold = _positive_number(
            value.get("high_liability_to_assets_pct"),
            "high_liability_to_assets_pct",
        )
        if liability_threshold > 100:
            raise ManagerScreenQuoteImpactError(
                "high_liability_to_assets_pct must be at most 100"
            )
    payload = value.get("payload")
    if payload is None:
        # v1 plans sealed before immutable payload embedding retain the
        # decision-critical fields above. Their provenance hashes remain audit
        # metadata; verification must not depend on the mutable live policy.
        return
    if not isinstance(payload, Mapping):
        raise ManagerScreenQuoteImpactError(
            "quote-impact embedded policy payload is invalid"
        )
    payload = dict(payload)
    payload_threshold = _positive_number(
        payload.get(
            PRICE_CHANGE_POLICY_KEY,
            DEFAULT_ABSOLUTE_PRICE_CHANGE_PCT,
        ),
        PRICE_CHANGE_POLICY_KEY,
    )
    payload_capacity = _positive_int(
        payload.get("send_to_analyst_capacity_per_run"),
        "send_to_analyst_capacity_per_run",
    )
    payload_reason_max = _positive_int(
        payload.get("one_line_reason_max_chars"),
        "one_line_reason_max_chars",
    )
    payload_question_max = _positive_int(
        payload.get("decisive_question_max_chars"),
        "decisive_question_max_chars",
    )
    payload_effort = _positive_number(
        payload.get("quick_profile_effort_budget_hours"),
        "quick_profile_effort_budget_hours",
    )
    payload_stops = payload.get("quick_profile_stop_conditions")
    if (
        hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        != value["payload_sha256"]
        or payload_threshold != float(value["absolute_price_change_pct"])
        or payload_capacity != value["send_to_analyst_capacity_per_run"]
        or payload_reason_max != value["one_line_reason_max_chars"]
        or payload_question_max != value["decisive_question_max_chars"]
        or payload_effort != float(value["quick_profile_effort_budget_hours"])
        or payload_stops != value["quick_profile_stop_conditions"]
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact embedded policy payload does not match the sealed contract"
        )


def _validate_verified_review_semantics(verified: Mapping[str, Any]) -> None:
    plan = verified["plan"]
    packet = verified["packet"]
    batch = verified["batch"]
    original_packet = verified["original_packet"]
    original_result = verified["original_result"]
    sealed_decision_version = batch.get("policy", {}).get(
        "decision_contract_version",
        1,
    )
    plan_decision_version = plan.get("policy", {}).get(
        "decision_contract_version",
        1,
    )
    if sealed_decision_version != plan_decision_version:
        raise ManagerScreenQuoteImpactError(
            "quote-impact decision contract does not match the sealed batch"
        )
    if plan_decision_version == 2 and any(
        plan["policy"].get(key) != batch["policy"].get(key)
        for key in DECISION_V2_POLICY_KEYS
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact decision v2 policy does not match the sealed batch"
        )
    candidate_symbols = plan.get("candidate_symbols")
    rows = packet.get("rows")
    if (
        not isinstance(candidate_symbols, list)
        or not all(isinstance(symbol, str) for symbol in candidate_symbols)
        or len(candidate_symbols) != len(set(candidate_symbols))
        or plan.get("candidate_count") != len(candidate_symbols)
        or not isinstance(rows, list)
        or len(rows) != len(candidate_symbols)
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact candidate plan or packet is invalid"
        )
    original_decisions = original_result.get("decisions")
    if not isinstance(original_decisions, list):
        raise ManagerScreenQuoteImpactError(
            "quote-impact original decisions are invalid"
        )
    original_by_symbol: dict[str, Mapping[str, Any]] = {}
    expected_original_keys = (
        DECISION_V2_KEYS if plan_decision_version == 2 else DECISION_KEYS
    )
    for decision in original_decisions:
        if (
            not isinstance(decision, Mapping)
            or set(decision) != expected_original_keys
        ):
            raise ManagerScreenQuoteImpactError(
                "quote-impact original decision is invalid"
            )
        symbol = decision.get("symbol")
        if not isinstance(symbol, str) or symbol in original_by_symbol:
            raise ManagerScreenQuoteImpactError(
                "quote-impact original decision symbols are invalid"
            )
        original_by_symbol[symbol] = decision
    original_dossiers = {
        dossier.get("symbol"): dossier
        for dossier in original_packet.get("dossiers", [])
        if isinstance(dossier, Mapping)
    }
    amendment_quotes = {
        quote.get("symbol"): quote
        for quote in verified["amendment"].get("quotes", [])
        if isinstance(quote, Mapping)
    }
    for symbol, row in zip(candidate_symbols, rows, strict=True):
        if (
            not isinstance(row, Mapping)
            or row.get("symbol") != symbol
            or not isinstance(row.get("old_decision"), Mapping)
            or dict(row["old_decision"]) != dict(original_by_symbol.get(symbol) or {})
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact packet does not bind the original decision: {symbol}"
            )
        if plan_decision_version == 1:
            if "decision_support" in row:
                raise ManagerScreenQuoteImpactError(
                    f"v1 quote-impact row cannot contain decision support: {symbol}"
                )
            continue
        dossier = original_dossiers.get(symbol)
        quote = amendment_quotes.get(symbol)
        if not isinstance(dossier, Mapping) or not isinstance(quote, Mapping):
            raise ManagerScreenQuoteImpactError(
                f"v2 quote-impact support inputs are missing: {symbol}"
            )
        source_evidence_id = (
            f"quote-amendment:{verified['amendment']['amendment_id']}:{symbol}"
        )
        expected_quote_binding = {
            "as_of": quote.get("as_of"),
            "source": quote.get("source"),
            "fetched_at": quote.get("fetched_at"),
            "evidence_id": source_evidence_id,
        }
        allowed_evidence_ids = row.get("allowed_evidence_ids")
        if (
            row.get("quote") != expected_quote_binding
            or not isinstance(allowed_evidence_ids, list)
            or source_evidence_id not in allowed_evidence_ids
        ):
            raise ManagerScreenQuoteImpactError(
                f"v2 quote-impact canonical evidence binding is invalid: {symbol}"
            )
        valuation = row.get("valuation")
        if (
            not isinstance(valuation, Mapping)
            or valuation.get("new")
            != {field: quote.get(field) for field in VALUATION_FIELDS}
        ):
            raise ManagerScreenQuoteImpactError(
                f"v2 quote-impact amended valuation is invalid: {symbol}"
            )
        support_inputs = _quote_decision_support_inputs(
            dossier=dossier,
            quote=quote,
            batch_policy=batch["policy"],
            canonical_source_evidence_id=source_evidence_id,
        )
        try:
            validate_decision_support(
                row.get("decision_support"),
                **support_inputs,
            )
        except ManagerScreenDecisionQualityError as exc:
            raise ManagerScreenQuoteImpactError(
                f"v2 quote-impact decision support is invalid: {symbol}"
            ) from exc

    result = verified.get("result")
    if result is None:
        return
    reviews = result.get("reviews")
    decisions = result.get("decisions")
    if (
        result.get("schema_version") != 1
        or result.get("original_result_path") != plan.get("original_result_path")
        or result.get("quote_amendment_path") != plan.get("quote_amendment_path")
        or result.get("policy_payload_sha256")
        != plan.get("policy", {}).get("payload_sha256")
        or result.get("manager") != original_result.get("manager")
        or result.get("portfolio_action") is not None
        or not isinstance(reviews, list)
        or not isinstance(decisions, list)
        or len(reviews) != len(candidate_symbols)
        or len(decisions) != len(candidate_symbols)
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact result content is invalid"
        )
    if _parse_datetime(result.get("recorded_at"), "result recorded_at") < _parse_datetime(
        plan.get("prepared_at"),
        "plan prepared_at",
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact result predates its preparation"
        )
    normalized_reviews = []
    normalized_decisions = []
    for symbol, row, review, decision in zip(
        candidate_symbols,
        rows,
        reviews,
        decisions,
        strict=True,
    ):
        if (
            not isinstance(review, Mapping)
            or set(review)
            != {
                "symbol",
                "action",
                "old_route",
                "replacement",
                "effective_decision",
            }
            or review.get("symbol") != symbol
            or review.get("old_route") != row["old_decision"].get("route")
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact review content is invalid: {symbol}"
            )
        action = review.get("action")
        if action == "keep":
            if plan_decision_version == 2:
                raise ManagerScreenQuoteImpactError(
                    f"v2 quote-impact result cannot keep stale price facts: {symbol}"
                )
            if (
                review.get("replacement") is not None
                or review.get("effective_decision") != row["old_decision"]
            ):
                raise ManagerScreenQuoteImpactError(
                    f"quote-impact keep review changed the decision: {symbol}"
                )
            effective = dict(row["old_decision"])
            replacement = None
        elif action == "replacement":
            effective = _decision(
                review.get("replacement"),
                symbol=symbol,
                allowed_evidence=set(row.get("allowed_evidence_ids") or []),
                reason_max=plan["policy"]["one_line_reason_max_chars"],
                question_max=plan["policy"]["decisive_question_max_chars"],
                decision_contract_version=plan_decision_version,
                decision_support=row.get("decision_support"),
            )
            replacement = effective
            if review.get("effective_decision") != effective:
                raise ManagerScreenQuoteImpactError(
                    f"quote-impact replacement decision is inconsistent: {symbol}"
                )
        else:
            raise ManagerScreenQuoteImpactError(
                f"quote-impact review action is invalid: {symbol}"
            )
        if decision != effective:
            raise ManagerScreenQuoteImpactError(
                f"quote-impact effective decision list is inconsistent: {symbol}"
            )
        normalized_reviews.append(
            {
                "symbol": symbol,
                "action": action,
                "old_route": row["old_decision"]["route"],
                "replacement": replacement,
                "effective_decision": effective,
            }
        )
        normalized_decisions.append(effective)
    if reviews != normalized_reviews or decisions != normalized_decisions:
        raise ManagerScreenQuoteImpactError(
            "quote-impact result is not canonically normalized"
        )
    expected_summary = {
        "candidate_count": len(reviews),
        "keep_count": sum(row["action"] == "keep" for row in reviews),
        "replacement_count": sum(row["action"] == "replacement" for row in reviews),
        "new_send_to_analyst_count": sum(
            row["action"] == "replacement"
            and row["old_route"] != "send_to_analyst"
            and row["effective_decision"]["route"] == "send_to_analyst"
            for row in reviews
        ),
    }
    if result.get("summary") != expected_summary:
        raise ManagerScreenQuoteImpactError(
            "quote-impact result summary is inconsistent"
        )


def _record_summary(
    result: Mapping[str, Any],
    *,
    result_path: Path,
    result_sha256: str,
    repository_root: Path,
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": result["run_id"],
        "batch_id": result["batch_id"],
        "review_id": result["review_id"],
        "state": "recorded",
        **dict(result["summary"]),
        "result_path": _relative(result_path, repository_root),
        "result_sha256": result_sha256,
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _sealed_object(
    path: Path,
    *,
    artifact_type: str,
) -> tuple[dict[str, Any], Any]:
    try:
        seal = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenQuoteImpactError(
            f"sealed quote-impact input is invalid: {path}"
        ) from exc
    if seal.artifact_type != artifact_type or not isinstance(payload, dict):
        raise ManagerScreenQuoteImpactError(
            f"sealed quote-impact input has unexpected type: {path}"
        )
    return payload, seal


def _manager(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != MANAGER_KEYS:
        raise ManagerScreenQuoteImpactError("manager fields do not match contract")
    tools = value.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or not all(isinstance(row, str) and row.strip() for row in tools)
    ):
        raise ManagerScreenQuoteImpactError("manager.tools must be non-empty strings")
    return {
        "agent": _text(value.get("agent"), "manager.agent"),
        "model": _text(value.get("model"), "manager.model"),
        "tools": [row.strip() for row in tools],
    }


def _repository_file(
    value: Any,
    *,
    repository_root: Path,
) -> Path:
    if not isinstance(value, (str, Path)):
        raise ManagerScreenQuoteImpactError("repository input path is invalid")
    path = Path(value)
    if not path.is_absolute():
        path = repository_root / path
    path = path.resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreenQuoteImpactError("quote-impact input escaped repository") from exc
    return path


def _identifier(value: Any, field: str) -> str:
    result = _text(value, field)
    if not ID_RE.fullmatch(result):
        raise ManagerScreenQuoteImpactError(f"{field} is invalid")
    return result


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not SYMBOL_RE.fullmatch(value):
        raise ManagerScreenQuoteImpactError(f"invalid CN symbol: {value}")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenQuoteImpactError(f"{field} must be non-empty text")
    return value.strip()


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManagerScreenQuoteImpactError(f"{field} must be a positive integer")
    return value


def _positive_number(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise ManagerScreenQuoteImpactError(f"{field} must be a positive number")
    return float(value)


def _aware(value: dt.datetime, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreenQuoteImpactError(f"{field} must include a UTC offset")
    return value


def _parse_datetime(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ManagerScreenQuoteImpactError(f"{field} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManagerScreenQuoteImpactError(f"{field} must be an ISO timestamp") from exc
    return _aware(parsed, field)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreenQuoteImpactError("quote-impact asset escaped repository") from exc
