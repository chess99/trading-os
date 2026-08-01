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
from .manager_screen_terminal_governance import (
    ManagerScreenTerminalGovernanceError,
    manager_screen_terminal_governance_locked,
    require_manager_screen_terminal_governance_open,
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
DIRECT_ALLOCATION_ROUTES = {"pass", "watch", "send_to_analyst"}
DEFERRED_ALLOCATION_ROUTES = {"pass", "watch", "research_candidate"}
ROUTES = DIRECT_ALLOCATION_ROUTES | DEFERRED_ALLOCATION_ROUTES
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
DECISION_V3_POLICY_KEYS = {"research_candidate_requires_allocation"}
REVIEW_KEYS = {"symbol", "action", "replacement"}
SUBMISSION_KEYS = {"schema_version", "manager", "reviews"}
VALUATION_FIELDS = (
    "market_cap_cny",
    "float_market_cap_cny",
    "pe_ttm",
    "pb",
)
QUOTE_IMPACT_CHAIN_VERSION = 1
PREDECESSOR_KEYS = {
    "result_artifact_type",
    "result_path",
    "result_sha256",
    "review_id",
    "quote_artifact_type",
    "quote_path",
    "quote_sha256",
}
DECISION_SOURCE_KEYS = {"symbol", "artifact_type", "path", "sha256", "review_id"}


class ManagerScreenQuoteImpactError(ValueError):
    """Raised when a completed-batch quote-impact review is invalid."""


def _terminal_governance_locked(*, base: Path, run_id: str) -> bool:
    try:
        return manager_screen_terminal_governance_locked(
            root=base,
            run_id=run_id,
        )
    except ManagerScreenTerminalGovernanceError as exc:
        raise ManagerScreenQuoteImpactError(str(exc)) from exc


def _routes_for_version(version: int) -> set[str]:
    if version == 3:
        return DEFERRED_ALLOCATION_ROUTES
    return DIRECT_ALLOCATION_ROUTES


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

    chain = _load_quote_impact_chain(
        base=base,
        repository_root=repository_root,
        run_id=run,
        batch_id=batch,
    )
    amendment_relative = _relative(inputs["amendment_path"], repository_root)
    existing_entry = next(
        (entry for entry in chain["entries"] if entry["review_id"] == review),
        None,
    )
    if existing_entry is not None:
        existing_plan = existing_entry["verified"]["plan"]
        if (
            existing_plan.get("prepared_at") != prepared.isoformat()
            or existing_plan.get("quote_amendment_path") != amendment_relative
            or existing_plan.get("quote_amendment_sha256")
            != inputs["amendment_seal"].sha256
            or existing_plan.get("policy", {}).get("payload_sha256")
            != inputs["policy_ref"]["payload_sha256"]
        ):
            raise ManagerScreenQuoteImpactError(
                "sealed quote-impact plan conflicts with prepare request"
            )
        return _chain_entry_summary(
            existing_entry,
            repository_root=repository_root,
        )
    _require_full_market_allocation_open(
        base=base,
        run_id=run,
        operation="new quote-impact review",
    )
    if chain["state"] == "prepared":
        raise ManagerScreenQuoteImpactError(
            "latest quote-impact review must be recorded before preparing its successor"
        )
    if chain["entries"] and prepared <= _parse_datetime(
        chain["entries"][-1]["verified"]["result"]["recorded_at"],
        "predecessor quote-impact recorded_at",
    ):
        raise ManagerScreenQuoteImpactError(
            "prepared_at must be strictly later than the terminal predecessor"
        )
    predecessor = _predecessor_for_new_review(
        inputs=inputs,
        chain=chain,
        repository_root=repository_root,
    )
    _require_new_amendment_after_chain(
        inputs=inputs,
        chain=chain,
        predecessor=predecessor,
    )
    inputs = {
        **inputs,
        "predecessor": predecessor,
        "predecessor_decisions": chain.get("effective_decisions")
        or [dict(decision) for decision in inputs["result"]["decisions"]],
        "predecessor_decision_sources": chain.get("decision_sources")
        or _original_decision_sources(inputs, repository_root=repository_root),
        "predecessor_quotes": chain.get("latest_quotes")
        or _original_packet_quotes(inputs["packet"]),
    }
    rows = _candidate_rows(inputs)
    review_dir = base / "manager-screen" / run / batch / "quote-impact-reviews" / review
    plan_path = review_dir / "plan.json"
    packet_path = review_dir / "packet.json"
    result_path = review_dir / "result.json"
    result_seal_path = result_path.with_name(f"{result_path.name}.seal.json")
    if inputs["decision_contract_version"] in {1, 2} and _allocation_v3_contract_active(
        base=base,
        run_id=run,
    ):
        if result_path.exists() != result_seal_path.exists():
            raise ManagerScreenQuoteImpactError(
                "post-contract quote-impact result is only partially sealed"
            )
        _require_post_contract_quote_suspension(
            base=base,
            run_id=run,
            require_fully_materialized=not result_path.exists(),
        )
    plan = {
        "schema_version": 2,
        "run_id": run,
        "batch_id": batch,
        "review_id": review,
        "chain_version": QUOTE_IMPACT_CHAIN_VERSION,
        "chain_sequence": len(chain["entries"]) + 1,
        "predecessor": predecessor["binding"],
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
            if inputs["decision_contract_version"] in {2, 3}
            else "Choose keep or provide a complete replacement manager-screen decision."
        ),
    ]
    packet = {
        "schema_version": 2,
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
    if not rows:
        result = _build_quote_impact_result(
            run_id=run,
            batch_id=batch,
            review_id=review,
            recorded_at=prepared,
            plan=plan,
            plan_path=plan_path,
            plan_sha256=plan_seal.sha256,
            packet_path=packet_path,
            packet_sha256=packet_seal.sha256,
            manager=dict(inputs["result"]["manager"]),
            reviews=[],
            decisions=[],
            predecessor_effective_decisions=inputs["predecessor_decisions"],
            repository_root=repository_root,
        )
        result_seal = seal_json(
            result_path,
            result,
            artifact_type="manager_screen_quote_impact_result",
            sealed_at=prepared,
        )
        return {
            "schema_version": 2,
            "run_id": run,
            "batch_id": batch,
            "review_id": review,
            "state": "recorded",
            "candidate_count": 0,
            "candidate_symbols": [],
            "plan_path": _relative(plan_path, repository_root),
            "plan_sha256": plan_seal.sha256,
            "packet_path": _relative(packet_path, repository_root),
            "packet_sha256": packet_seal.sha256,
            "result_path": _relative(result_path, repository_root),
            "result_sha256": result_seal.sha256,
            "portfolio_action": None,
        }
    return {
        "schema_version": 2,
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
    chain = _load_quote_impact_chain(
        base=base,
        repository_root=repository_root,
        run_id=run,
        batch_id=batch,
    )
    chain_entry = next(
        (entry for entry in chain["entries"] if entry["review_id"] == review),
        None,
    )
    if chain_entry is None:
        raise ManagerScreenQuoteImpactError("quote-impact review is outside the sealed chain")
    post_contract_pre_v3 = plan["policy"].get("decision_contract_version", 1) in {
        1,
        2,
    } and _allocation_v3_contract_active(base=base, run_id=run)
    suspension_binding = None
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
        if _terminal_governance_locked(base=base, run_id=run):
            return _record_summary(
                existing,
                result_path=result_path,
                result_sha256=complete["result_seal"].sha256,
                repository_root=repository_root,
                idempotent=True,
            )
        if existing.get("automatic_noop") is True:
            return _record_summary(
                existing,
                result_path=result_path,
                result_sha256=complete["result_seal"].sha256,
                repository_root=repository_root,
                idempotent=True,
            )
        if chain["entries"][-1]["review_id"] != review:
            return _record_summary(
                existing,
                result_path=result_path,
                result_sha256=complete["result_seal"].sha256,
                repository_root=repository_root,
                idempotent=True,
            )
        if post_contract_pre_v3:
            suspension_binding = _require_post_contract_quote_suspension(
                base=base,
                run_id=run,
                require_fully_materialized=False,
                allow_absent=True,
            )
        if post_contract_pre_v3 and suspension_binding is None:
            _require_frozen_quote_projection_binding(
                base=base,
                repository_root=repository_root,
                plan=plan,
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
            reviews=existing["reviews"],
            purchases_already_recorded=True,
        )
        _materialize_replacements(
            base=base,
            repository_root=repository_root,
            plan=plan,
            packet=packet,
            result=existing,
            result_path=result_path,
            result_sha256=complete["result_seal"].sha256,
            suspension_binding=suspension_binding,
        )
        return _record_summary(
            existing,
            result_path=result_path,
            result_sha256=complete["result_seal"].sha256,
            repository_root=repository_root,
            idempotent=True,
        )

    _require_full_market_allocation_open(
        base=base,
        run_id=run,
        operation="new quote-impact result",
    )
    if post_contract_pre_v3:
        suspension_binding = _require_post_contract_quote_suspension(
            base=base,
            run_id=run,
            require_fully_materialized=True,
        )
    _enforce_capacity(
        base=base,
        run_id=run,
        plan=plan,
        reviews=normalized["reviews"],
    )
    predecessor_effective = _effective_decisions_before_entry(chain, review_id=review)
    result = _build_quote_impact_result(
        run_id=run,
        batch_id=batch,
        review_id=review,
        recorded_at=recorded,
        plan=plan,
        plan_path=verified["plan_path"],
        plan_sha256=verified["plan_seal"].sha256,
        packet_path=verified["packet_path"],
        packet_sha256=verified["packet_seal"].sha256,
        manager=normalized["manager"],
        reviews=normalized["reviews"],
        decisions=normalized["decisions"],
        predecessor_effective_decisions=predecessor_effective,
        repository_root=repository_root,
    )
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
        suspension_binding=suspension_binding,
    )
    return _record_summary(
        result,
        result_path=result_path,
        result_sha256=result_seal.sha256,
        repository_root=repository_root,
        idempotent=False,
    )


def _allocation_v3_contract_active(*, base: Path, run_id: str) -> bool:
    contract_path = (
        base / "manager-screen" / run_id / "governance" / "allocation-v3" / "contract.json"
    )
    seal_path = contract_path.with_name(f"{contract_path.name}.seal.json")
    artifact = contract_path.exists()
    seal = seal_path.exists()
    if not artifact and not seal:
        return False
    if artifact != seal:
        raise ManagerScreenQuoteImpactError(
            "manager-screen allocation v3 contract is only partially sealed"
        )
    from .manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
        verify_manager_screen_allocation_v3_contract,
    )

    try:
        verify_manager_screen_allocation_v3_contract(root=base, run_id=run_id)
    except ManagerScreenAllocationV3Error as exc:
        raise ManagerScreenQuoteImpactError(
            "manager-screen allocation v3 contract is invalid"
        ) from exc
    return True


def _require_full_market_allocation_open(
    *,
    base: Path,
    run_id: str,
    operation: str,
) -> None:
    """Forbid new quote evolution once terminal governance is locked."""

    try:
        require_manager_screen_terminal_governance_open(
            root=base,
            run_id=run_id,
            operation=operation,
        )
    except ManagerScreenTerminalGovernanceError as exc:
        raise ManagerScreenQuoteImpactError(str(exc)) from exc


def _require_post_contract_quote_suspension(
    *,
    base: Path,
    run_id: str,
    require_fully_materialized: bool,
    allow_absent: bool = False,
) -> dict[str, Any] | None:
    """Load the sealed suspension that makes v1/v2 quote evolution budget-neutral."""

    from .manager_screen_allocation_v3_suspension import (
        SUSPENSION_ARTIFACT_TYPE,
        SUSPENSION_RELATIVE_PATH,
        ManagerScreenAllocationV3SuspensionError,
        verify_manager_screen_allocation_v3_suspension,
    )

    path = base / "manager-screen" / run_id / SUSPENSION_RELATIVE_PATH
    seal_path = path.with_name(f"{path.name}.seal.json")
    if not path.exists() and not seal_path.exists():
        if allow_absent:
            return None
        raise ManagerScreenQuoteImpactError(
            "pre-contract v1/v2 quote-impact is read-only until every revocable "
            "purchase has a sealed allocation-v3 suspension"
        )
    if path.exists() != seal_path.exists():
        raise ManagerScreenQuoteImpactError(
            "allocation-v3 suspension is only partially sealed during quote-impact review"
        )
    try:
        status = verify_manager_screen_allocation_v3_suspension(
            root=base,
            run_id=run_id,
        )
        payload, sealed = _sealed_object(
            path,
            artifact_type=SUSPENSION_ARTIFACT_TYPE,
        )
    except (ManagerScreenAllocationV3SuspensionError, OSError, SealingError) as exc:
        raise ManagerScreenQuoteImpactError(
            "allocation-v3 suspension is invalid during quote-impact review"
        ) from exc
    materialization = status.get("materialization")
    if (
        payload.get("run_id") != run_id
        or not isinstance(payload.get("members"), list)
        or not isinstance(materialization, Mapping)
    ):
        raise ManagerScreenQuoteImpactError(
            "allocation-v3 suspension binding is invalid during quote-impact review"
        )
    members = {
        member.get("symbol"): dict(member)
        for member in payload["members"]
        if isinstance(member, Mapping) and isinstance(member.get("symbol"), str)
    }
    if len(members) != len(payload["members"]):
        raise ManagerScreenQuoteImpactError(
            "allocation-v3 suspension members are invalid during quote-impact review"
        )
    binding = {
        "path": _relative(path, base.parent.parent.resolve()),
        "sha256": sealed.sha256,
        "payload": payload,
        "members": members,
        "materialization": dict(materialization),
    }
    if require_fully_materialized and materialization.get("fully_materialized") is not True:
        _require_sealed_suspension_or_quote_evolution(
            base=base,
            repository_root=base.parent.parent.resolve(),
            suspension_binding=binding,
        )
    return binding


def _require_sealed_suspension_or_quote_evolution(
    *,
    base: Path,
    repository_root: Path,
    suspension_binding: Mapping[str, Any],
) -> None:
    """Allow each suspended member to advance once through its sealed batch overlay."""

    from .manager_screen_allocation_v3_suspension import (
        _suspended_queue_row,
        _suspended_screening_row,
    )

    payload = suspension_binding["payload"]
    queue = _quote_rows_by_symbol(base / RESEARCH_QUEUE_FILE, "research queue")
    screening = _quote_rows_by_symbol(base / SCREENING_FILE, "screening")
    errors: list[str] = []
    for member in payload["members"]:
        symbol = member["symbol"]
        expected_queue = _suspended_queue_row(
            member,
            payload=payload,
            suspension_path=suspension_binding["path"],
            suspension_sha256=suspension_binding["sha256"],
        )
        expected_screen = _suspended_screening_row(
            member,
            payload=payload,
            suspension_path=suspension_binding["path"],
            suspension_sha256=suspension_binding["sha256"],
        )
        current_queue = queue.get(symbol)
        current_screen = screening.get(symbol)
        if current_queue == expected_queue and current_screen == expected_screen:
            continue
        try:
            _require_one_sealed_quote_evolution(
                queue=current_queue,
                screen=current_screen,
                member=member,
                suspension_binding=suspension_binding,
                repository_root=repository_root,
                symbol=symbol,
            )
        except ManagerScreenQuoteImpactError as exc:
            errors.append(f"{symbol}: {exc}")
    if errors:
        raise ManagerScreenQuoteImpactError(
            "allocation-v3 suspension has drift outside sealed quote-impact evolution: "
            + "; ".join(errors)
        )


def _require_one_sealed_quote_evolution(
    *,
    queue: Mapping[str, Any] | None,
    screen: Mapping[str, Any] | None,
    member: Mapping[str, Any],
    suspension_binding: Mapping[str, Any],
    repository_root: Path,
    symbol: str,
) -> None:
    if not isinstance(queue, Mapping) or not isinstance(screen, Mapping):
        raise ManagerScreenQuoteImpactError("quote-evolved suspension row is missing")
    result_path = queue.get("manager_screen_result_path")
    result_sha256 = queue.get("manager_screen_result_sha256")
    if not isinstance(result_path, str) or not isinstance(result_sha256, str):
        raise ManagerScreenQuoteImpactError("quote-evolved result binding is missing")
    path = (repository_root / result_path).resolve()
    try:
        path.relative_to(repository_root.resolve())
        sealed = verify_sealed(path)
        result = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenQuoteImpactError(
            "quote-evolved result is not a valid sealed repository artifact"
        ) from exc
    reviews = result.get("reviews") if isinstance(result, Mapping) else None
    matches = [
        review
        for review in (reviews if isinstance(reviews, list) else [])
        if isinstance(review, Mapping) and review.get("symbol") == symbol
    ]
    decision = matches[0].get("effective_decision") if len(matches) == 1 else None
    prior_queue = member.get("prior_queue_row")
    expected_batch_id = (
        prior_queue.get("manager_screen_batch_id")
        if isinstance(prior_queue, Mapping)
        else None
    )
    if expected_batch_id is None:
        expected_batch_id = result.get("batch_id") if isinstance(result, Mapping) else None
    history = queue.get("stage_history")
    if (
        sealed.artifact_type != "manager_screen_quote_impact_result"
        or sealed.sha256 != result_sha256
        or result.get("run_id") != suspension_binding["payload"].get("run_id")
        or not isinstance(expected_batch_id, str)
        or result.get("batch_id") != expected_batch_id
        or result.get("original_result_path") != member.get("manager_screen_result_path")
        or result.get("original_result_sha256")
        != member.get("manager_screen_result_sha256")
        or len(matches) != 1
        or matches[0].get("action") != "replacement"
        or not isinstance(decision, Mapping)
        or queue.get("manager_screen_batch_id") != expected_batch_id
        or queue.get("manager_screen_route") != decision.get("route")
        or queue.get("reason") != decision.get("one_line_reason")
        or queue.get("decisive_question") != decision.get("decisive_question")
        or list(queue.get("evidence_ids") or []) != list(decision.get("evidence_ids") or [])
        or list(queue.get("revisit_triggers") or [])
        != list(decision.get("revisit_triggers") or [])
        or queue.get("task_type") != "manager_screen"
        or queue.get("status") != "completed"
        or queue.get("assigned_agent") is not None
        or queue.get("started_at") is not None
        or queue.get("result_path") != result_path
        or queue.get("research_budget_state") != "candidate_unfunded"
        or queue.get("research_budget_suspension_path") != suspension_binding["path"]
        or queue.get("research_budget_suspension_sha256")
        != suspension_binding["sha256"]
        or not isinstance(history, list)
        or not any(
            isinstance(item, Mapping)
            and item.get("stage") == "manager_screen_quote_impact"
            and item.get("result_sha256") == result_sha256
            for item in history
        )
        or screen.get("manager_screen_batch_id") != expected_batch_id
        or screen.get("manager_screen_result_path") != result_path
        or screen.get("manager_screen_result_sha256") != result_sha256
        or screen.get("manager_screen_route") != decision.get("route")
        or screen.get("reason") != decision.get("one_line_reason")
        or screen.get("decisive_question") != decision.get("decisive_question")
        or list(screen.get("evidence") or []) != list(decision.get("evidence_ids") or [])
        or list(screen.get("revisit_triggers") or [])
        != list(decision.get("revisit_triggers") or [])
        or screen.get("confidence") != decision.get("confidence")
        or screen.get("decision") != "candidate_unfunded"
        or screen.get("state") != "candidate_unfunded"
        or screen.get("research_budget_state") != "candidate_unfunded"
        or screen.get("research_budget_suspension_path") != suspension_binding["path"]
        or screen.get("research_budget_suspension_sha256")
        != suspension_binding["sha256"]
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-evolved rows do not match their sealed replacement"
        )


def _quote_rows_by_symbol(path: Path, label: str) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = row.get("symbol") if isinstance(row, Mapping) else None
        if not isinstance(symbol, str) or symbol in result:
            raise ManagerScreenQuoteImpactError(
                f"{label} contains an invalid or duplicate symbol"
            )
        result[symbol] = dict(row)
    return result


def _require_frozen_quote_projection_binding(
    *,
    base: Path,
    repository_root: Path,
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: Path,
    result_sha256: str,
) -> None:
    queue_rows = read_jsonl(base / RESEARCH_QUEUE_FILE)
    queue = {
        row.get("symbol"): row
        for row in queue_rows
        if isinstance(row, Mapping) and isinstance(row.get("symbol"), str)
    }
    if len(queue) != len(queue_rows):
        raise ManagerScreenQuoteImpactError(
            "research queue is invalid during frozen quote-impact replay"
        )
    result_relative = _relative(result_path, repository_root)
    errors = []
    for review in result["reviews"]:
        if review["action"] != "replacement":
            continue
        symbol = review["symbol"]
        decision = review["effective_decision"]
        row = queue.get(symbol)
        history = row.get("stage_history") if isinstance(row, Mapping) else None
        history_bound = isinstance(history, list) and any(
            isinstance(item, Mapping)
            and item.get("stage") == "manager_screen_quote_impact"
            and item.get("result_sha256") == result_sha256
            for item in history
        )
        if (
            not isinstance(row, Mapping)
            or row.get("manager_screen_run_id") != plan["run_id"]
            or row.get("manager_screen_batch_id") != plan["batch_id"]
            or row.get("manager_screen_route") != decision["route"]
            or row.get("manager_screen_result_path") != result_relative
            or row.get("manager_screen_result_sha256") != result_sha256
            or row.get("decisive_question") != decision["decisive_question"]
            or list(row.get("evidence_ids") or []) != list(decision["evidence_ids"])
            or not history_bound
        ):
            errors.append(symbol)
    if errors:
        raise ManagerScreenQuoteImpactError(
            "post-contract v1/v2 quote-impact replay is read-only and its current "
            f"projection binding drifted: {sorted(errors)}"
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
    chain = _load_quote_impact_chain(
        base=base,
        repository_root=repository_root,
        run_id=verified["plan"]["run_id"],
        batch_id=verified["plan"]["batch_id"],
    )
    entry = next(
        item for item in chain["entries"] if item["review_id"] == verified["plan"]["review_id"]
    )
    result = verified.get("result")
    materialized = 0
    was_materialized = 0
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
        was_materialized = sum(
            row["action"] == "replacement"
            and any(
                isinstance(receipt, Mapping)
                and receipt.get("stage") == "manager_screen_quote_impact"
                and receipt.get("result_sha256") == result_sha256
                for receipt in (queue.get(row["symbol"]) or {}).get("stage_history", [])
            )
            for row in result["reviews"]
        )
    return {
        "schema_version": result.get("schema_version", 1),
        "run_id": verified["plan"]["run_id"],
        "batch_id": verified["plan"]["batch_id"],
        "review_id": verified["plan"]["review_id"],
        "state": "recorded" if result is not None else "prepared",
        "candidate_count": verified["plan"]["candidate_count"],
        "replacement_count": (result["summary"]["replacement_count"] if result is not None else 0),
        "materialized_replacement_count": materialized,
        "was_materialized_replacement_count": was_materialized,
        "is_latest_effective": chain["entries"][-1]["review_id"] == entry["review_id"],
        "chain_sequence": entry["sequence"],
        "review_count": len(chain["entries"]),
        "chain_sha256": chain["chain_sha256"],
        "quote_amendment_path": verified["plan"]["quote_amendment_path"],
        "quote_amendment_sha256": verified["plan"]["quote_amendment_sha256"],
        "quote_amendment_effective_at": verified["amendment"]["effective_at"],
        "automatic_noop": bool(result.get("automatic_noop")) if result is not None else False,
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
    """Verify the append-only review chain and return its latest cumulative overlay."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    batch = _identifier(batch_id, "batch_id")
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
        "effective_route_delta": {route: 0 for route in sorted(DIRECT_ALLOCATION_ROUTES)},
        "decisions": [],
        "reviews": [],
        "quick_profile_effort_budget_hours": None,
        "chain_version": QUOTE_IMPACT_CHAIN_VERSION,
        "chain_length": 0,
        "review_count": 0,
        "latest_sequence": None,
        "chain_sha256": hashlib.sha256(canonical_json_bytes([])).hexdigest(),
        "chain_entries": [],
        "quote_amendment_path": None,
        "quote_amendment_sha256": None,
        "quote_amendment_effective_at": None,
        "automatic_noop": False,
        "effective_decisions": [],
        "effective_decision_sources": [],
        "purchase_reviews": [],
        "historical_purchase_company_count": 0,
    }
    chain = _load_quote_impact_chain(
        base=base,
        repository_root=repository_root,
        run_id=run,
        batch_id=batch,
    )
    if not chain["entries"]:
        return empty
    latest = chain["entries"][-1]
    verified = latest["verified"]
    review_id = latest["review_id"]
    plan = verified["plan"]
    result = verified["result"]
    effective_routes = _routes_for_version(plan["policy"].get("decision_contract_version", 1))
    common = {
        **empty,
        "state": "recorded" if result is not None else "prepared",
        "review_id": review_id,
        "candidate_count": plan["candidate_count"],
        "plan_path": _relative(verified["plan_path"], repository_root),
        "plan_sha256": verified["plan_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "quick_profile_effort_budget_hours": plan["policy"]["quick_profile_effort_budget_hours"],
        "effective_route_delta": {route: 0 for route in sorted(effective_routes)},
        "chain_length": len(chain["entries"]),
        "review_count": len(chain["entries"]),
        "latest_sequence": latest["sequence"],
        "chain_sha256": chain["chain_sha256"],
        "chain_entries": chain["public_entries"],
        "quote_amendment_path": plan["quote_amendment_path"],
        "quote_amendment_sha256": plan["quote_amendment_sha256"],
        "quote_amendment_effective_at": verified["amendment"]["effective_at"],
        "automatic_noop": bool(result.get("automatic_noop")) if result is not None else False,
        "effective_decisions": [dict(row) for row in chain["effective_decisions"]],
        "effective_decision_sources": [
            dict(chain["decision_sources"][row["symbol"]])
            for row in chain["effective_decisions"]
        ],
        "purchase_reviews": [dict(row) for row in chain["purchase_reviews"]],
        "historical_purchase_company_count": len(chain["purchase_reviews"]),
    }
    if result is None:
        return common
    route_delta: Counter[str] = Counter()
    original_by_symbol = {
        row["symbol"]: row for row in chain["original_decisions"]
    }
    cumulative_reviews = []
    for decision in chain["effective_decisions"]:
        symbol = decision["symbol"]
        source = chain["decision_sources"][symbol]
        original = original_by_symbol[symbol]
        if source["artifact_type"] == "manager_screen_result":
            continue
        route_delta[original["route"]] -= 1
        route_delta[decision["route"]] += 1
        cumulative_reviews.append(
            {
                "symbol": symbol,
                "action": "replacement",
                "old_route": original["route"],
                "replacement": dict(decision),
                "effective_decision": dict(decision),
                "effective_decision_source_path": source["path"],
                "effective_decision_source_sha256": source["sha256"],
            }
        )
    return {
        **common,
        "keep_count": result["summary"]["keep_count"],
        "replacement_count": result["summary"]["replacement_count"],
        "new_send_to_analyst_count": result["summary"]["new_send_to_analyst_count"],
        "result_path": _relative(verified["result_path"], repository_root),
        "result_sha256": verified["result_seal"].sha256,
        "effective_route_delta": {route: route_delta[route] for route in sorted(effective_routes)},
        "decisions": [dict(decision) for decision in chain["effective_decisions"]],
        "reviews": cumulative_reviews,
    }


def _load_quote_impact_chain(
    *,
    base: Path,
    repository_root: Path,
    run_id: str,
    batch_id: str,
) -> dict[str, Any]:
    reviews_root = base / "manager-screen" / run_id / batch_id / "quote-impact-reviews"
    if not reviews_root.exists():
        return {
            "state": "absent",
            "entries": [],
            "public_entries": [],
            "chain_sha256": hashlib.sha256(canonical_json_bytes([])).hexdigest(),
            "original_decisions": [],
            "effective_decisions": [],
            "decision_sources": {},
            "latest_quotes": {},
            "purchase_reviews": [],
        }
    if not reviews_root.is_dir():
        raise ManagerScreenQuoteImpactError("quote-impact reviews path is not a directory")
    directories = sorted(reviews_root.iterdir(), key=lambda path: path.name)
    if any(not path.is_dir() for path in directories):
        raise ManagerScreenQuoteImpactError(
            "quote-impact reviews directory contains an unexpected file"
        )
    if not directories:
        return {
            "state": "absent",
            "entries": [],
            "public_entries": [],
            "chain_sha256": hashlib.sha256(canonical_json_bytes([])).hexdigest(),
            "original_decisions": [],
            "effective_decisions": [],
            "decision_sources": {},
            "latest_quotes": {},
            "purchase_reviews": [],
        }

    entries = []
    legacy_count = 0
    seen_sequences: set[int] = set()
    for directory in directories:
        review_id = _identifier(directory.name, "review_id")
        result_presence = _sealed_artifact_presence(directory / "result.json")
        if result_presence == "partial":
            raise ManagerScreenQuoteImpactError(
                f"quote-impact result is only partially sealed: {review_id}"
            )
        verified = _verify_review(
            base=base,
            repository_root=repository_root,
            run_id=run_id,
            batch_id=batch_id,
            review_id=review_id,
            require_result=False,
        )
        _validate_verified_review_semantics(verified)
        plan = verified["plan"]
        has_chain_fields = any(
            key in plan for key in ("chain_version", "chain_sequence", "predecessor")
        )
        if not has_chain_fields:
            legacy_count += 1
            sequence = 1
            legacy = True
        else:
            if (
                plan.get("schema_version") != 2
                or plan.get("chain_version") != QUOTE_IMPACT_CHAIN_VERSION
                or isinstance(plan.get("chain_sequence"), bool)
                or not isinstance(plan.get("chain_sequence"), int)
                or plan["chain_sequence"] <= 0
            ):
                raise ManagerScreenQuoteImpactError(
                    f"quote-impact chain metadata is invalid: {review_id}"
                )
            sequence = plan["chain_sequence"]
            legacy = False
        if sequence in seen_sequences:
            raise ManagerScreenQuoteImpactError(
                f"quote-impact chain sequence is duplicated: {sequence}"
            )
        seen_sequences.add(sequence)
        entries.append(
            {
                "review_id": review_id,
                "sequence": sequence,
                "legacy": legacy,
                "verified": verified,
                "state": "recorded" if verified["result"] is not None else "prepared",
            }
        )
    if legacy_count > 1:
        raise ManagerScreenQuoteImpactError(
            "multiple legacy quote-impact siblings cannot be ordered safely"
        )
    entries.sort(key=lambda entry: entry["sequence"])
    if [entry["sequence"] for entry in entries] != list(range(1, len(entries) + 1)):
        raise ManagerScreenQuoteImpactError("quote-impact chain contains a sequence gap")
    if any(entry["state"] == "prepared" for entry in entries[:-1]):
        raise ManagerScreenQuoteImpactError(
            "quote-impact chain cannot continue after a prepared predecessor"
        )

    first = entries[0]["verified"]
    original_result_path = first["plan"]["original_result_path"]
    original_result_sha256 = first["plan"]["original_result_sha256"]
    original_packet_path = first["plan"]["original_packet_path"]
    original_packet_sha256 = first["plan"]["original_packet_sha256"]
    original_decisions = [dict(row) for row in first["original_result"]["decisions"]]
    order = [row["symbol"] for row in original_decisions]
    effective = {row["symbol"]: dict(row) for row in original_decisions}
    sources = {
        symbol: {
            "symbol": symbol,
            "artifact_type": "manager_screen_result",
            "path": original_result_path,
            "sha256": original_result_sha256,
            "review_id": None,
        }
        for symbol in order
    }
    ever_purchased = {
        decision["symbol"]
        for decision in original_decisions
        if decision["route"] == "send_to_analyst"
    }
    purchase_reviews = []
    latest_quotes = _original_packet_quotes(first["original_packet"])
    previous_binding = {
        "result_artifact_type": "manager_screen_result",
        "result_path": original_result_path,
        "result_sha256": original_result_sha256,
        "review_id": None,
        "quote_artifact_type": "manager_screen_packet",
        "quote_path": original_packet_path,
        "quote_sha256": original_packet_sha256,
    }
    seen_amendment_ids: set[str] = set()
    seen_amendment_paths: set[str] = set()
    seen_amendment_sha256: set[str] = set()
    prior_amendment_effective: dt.datetime | None = None
    public_entries = []
    digest_entries = []
    for index, entry in enumerate(entries, start=1):
        verified = entry["verified"]
        plan = verified["plan"]
        if (
            plan["original_result_path"] != original_result_path
            or plan["original_result_sha256"] != original_result_sha256
            or plan["original_packet_path"] != original_packet_path
            or plan["original_packet_sha256"] != original_packet_sha256
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact chain root binding drifted: {entry['review_id']}"
            )
        if not entry["legacy"]:
            predecessor = _validated_predecessor(plan.get("predecessor"))
            if predecessor != previous_binding:
                raise ManagerScreenQuoteImpactError(
                    f"quote-impact predecessor binding is not the unique latest terminal: "
                    f"{entry['review_id']}"
                )
            prepared_at = _parse_datetime(
                plan.get("prepared_at"),
                f"{entry['review_id']} prepared_at",
            )
            if (
                verified["plan_seal"].sealed_at != prepared_at
                or verified["packet_seal"].sealed_at < verified["plan_seal"].sealed_at
                or (
                    verified["result_seal"] is not None
                    and verified["result_seal"].sealed_at < verified["packet_seal"].sealed_at
                )
            ):
                raise ManagerScreenQuoteImpactError(
                    f"quote-impact chain seal chronology is invalid: {entry['review_id']}"
                )
        elif index != 1:
            raise ManagerScreenQuoteImpactError(
                "legacy quote-impact review may only be the first chain entry"
            )
        amendment = verified["amendment"]
        amendment_id = _identifier(amendment.get("amendment_id"), "amendment_id")
        amendment_path = plan["quote_amendment_path"]
        amendment_sha256 = plan["quote_amendment_sha256"]
        if (
            amendment_id in seen_amendment_ids
            or amendment_path in seen_amendment_paths
            or amendment_sha256 in seen_amendment_sha256
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact amendment is duplicated in the chain: {amendment_id}"
            )
        amendment_effective = _parse_datetime(
            amendment.get("effective_at"),
            f"{entry['review_id']} amendment effective_at",
        )
        if (
            prior_amendment_effective is not None
            and amendment_effective <= prior_amendment_effective
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact amendment effective_at is not strictly increasing: "
                f"{entry['review_id']}"
            )
        _require_quote_times_after_predecessor(
            predecessor_quotes=latest_quotes,
            amendment=amendment,
            require_comparable=prior_amendment_effective is not None,
        )
        seen_amendment_ids.add(amendment_id)
        seen_amendment_paths.add(amendment_path)
        seen_amendment_sha256.add(amendment_sha256)
        prior_amendment_effective = amendment_effective
        entry["effective_decisions_before"] = [dict(effective[symbol]) for symbol in order]
        result = verified["result"]
        result_path = _relative(verified["result_path"], repository_root)
        result_sha256 = verified["result_seal"].sha256 if result is not None else None
        if result is not None:
            for review in result["reviews"]:
                symbol = review["symbol"]
                effective[symbol] = dict(review["effective_decision"])
                if review["action"] == "replacement":
                    sources[symbol] = {
                        "symbol": symbol,
                        "artifact_type": "manager_screen_quote_impact_result",
                        "path": result_path,
                        "sha256": result_sha256,
                        "review_id": entry["review_id"],
                    }
                    if (
                        review["old_route"] != "send_to_analyst"
                        and review["effective_decision"]["route"] == "send_to_analyst"
                        and symbol not in ever_purchased
                    ):
                        ever_purchased.add(symbol)
                        purchase_reviews.append(
                            {
                                "symbol": symbol,
                                "sequence": entry["sequence"],
                                "review_id": entry["review_id"],
                                "purchased_at": result["recorded_at"],
                                "effort_budget_hours": plan["policy"][
                                    "quick_profile_effort_budget_hours"
                                ],
                                "result_path": result_path,
                                "result_sha256": result_sha256,
                            }
                        )
            cumulative = [dict(effective[symbol]) for symbol in order]
            if result.get("schema_version") == 2 and (
                result.get("effective_decisions") != cumulative
                or result.get("effective_decisions_sha256") != _payload_sha256(cumulative)
            ):
                raise ManagerScreenQuoteImpactError(
                    f"quote-impact cumulative effective decisions are invalid: "
                    f"{entry['review_id']}"
                )
            latest_quotes = {
                row["symbol"]: dict(row) for row in amendment["quotes"]
            }
            previous_binding = {
                "result_artifact_type": "manager_screen_quote_impact_result",
                "result_path": result_path,
                "result_sha256": result_sha256,
                "review_id": entry["review_id"],
                "quote_artifact_type": "manager_screen_quote_amendment",
                "quote_path": amendment_path,
                "quote_sha256": amendment_sha256,
            }
        public = {
            "sequence": entry["sequence"],
            "review_id": entry["review_id"],
            "state": entry["state"],
            "legacy": entry["legacy"],
            "plan_path": _relative(verified["plan_path"], repository_root),
            "plan_sha256": verified["plan_seal"].sha256,
            "packet_path": _relative(verified["packet_path"], repository_root),
            "packet_sha256": verified["packet_seal"].sha256,
            "result_path": result_path if result is not None else None,
            "result_sha256": result_sha256,
            "quote_amendment_path": amendment_path,
            "quote_amendment_sha256": amendment_sha256,
            "quote_amendment_effective_at": amendment_effective.isoformat(),
            "candidate_count": plan["candidate_count"],
            "automatic_noop": bool(result.get("automatic_noop")) if result is not None else False,
        }
        public_entries.append(public)
        digest_entries.append(public)
    return {
        "state": entries[-1]["state"],
        "entries": entries,
        "public_entries": public_entries,
        "chain_sha256": _payload_sha256(digest_entries),
        "original_decisions": original_decisions,
        "effective_decisions": [dict(effective[symbol]) for symbol in order],
        "decision_sources": sources,
        "latest_quotes": latest_quotes,
        "purchase_reviews": purchase_reviews,
    }


def _predecessor_for_new_review(
    *,
    inputs: Mapping[str, Any],
    chain: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    entries = chain["entries"]
    if not entries:
        binding = {
            "result_artifact_type": "manager_screen_result",
            "result_path": _relative(inputs["result_path"], repository_root),
            "result_sha256": inputs["result_seal"].sha256,
            "review_id": None,
            "quote_artifact_type": "manager_screen_packet",
            "quote_path": _relative(inputs["packet_path"], repository_root),
            "quote_sha256": inputs["packet_seal"].sha256,
        }
    else:
        latest = entries[-1]
        verified = latest["verified"]
        if verified["result"] is None:
            raise ManagerScreenQuoteImpactError(
                "latest quote-impact predecessor is not terminal"
            )
        binding = {
            "result_artifact_type": "manager_screen_quote_impact_result",
            "result_path": _relative(verified["result_path"], repository_root),
            "result_sha256": verified["result_seal"].sha256,
            "review_id": latest["review_id"],
            "quote_artifact_type": "manager_screen_quote_amendment",
            "quote_path": verified["plan"]["quote_amendment_path"],
            "quote_sha256": verified["plan"]["quote_amendment_sha256"],
        }
    return {"binding": binding}


def _require_new_amendment_after_chain(
    *,
    inputs: Mapping[str, Any],
    chain: Mapping[str, Any],
    predecessor: Mapping[str, Any],
) -> None:
    amendment = inputs["amendment"]
    amendment_id = _identifier(amendment.get("amendment_id"), "amendment_id")
    amendment_path = _relative(inputs["amendment_path"], inputs["repository_root"])
    amendment_sha256 = inputs["amendment_seal"].sha256
    for entry in chain["entries"]:
        verified = entry["verified"]
        if (
            verified["amendment"].get("amendment_id") == amendment_id
            or verified["plan"].get("quote_amendment_path") == amendment_path
            or verified["plan"].get("quote_amendment_sha256") == amendment_sha256
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact amendment was already reviewed: {amendment_id}"
            )
    if chain["entries"]:
        previous = chain["entries"][-1]["verified"]["amendment"]
        if _parse_datetime(amendment.get("effective_at"), "quote amendment effective_at") <= (
            _parse_datetime(previous.get("effective_at"), "predecessor amendment effective_at")
        ):
            raise ManagerScreenQuoteImpactError(
                "quote-impact amendment effective_at must be strictly later than its predecessor"
            )
    _require_quote_times_after_predecessor(
        predecessor_quotes=(
            chain["latest_quotes"]
            if chain["entries"]
            else _original_packet_quotes(inputs["packet"])
        ),
        amendment=amendment,
        require_comparable=bool(chain["entries"]),
    )
    _validated_predecessor(predecessor["binding"])


def _require_quote_times_after_predecessor(
    *,
    predecessor_quotes: Mapping[str, Mapping[str, Any]],
    amendment: Mapping[str, Any],
    require_comparable: bool,
) -> None:
    current = {
        row.get("symbol"): row
        for row in amendment.get("quotes", [])
        if isinstance(row, Mapping) and isinstance(row.get("symbol"), str)
    }
    if not set(predecessor_quotes).issubset(current) or (
        require_comparable and set(current) != set(predecessor_quotes)
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact amendment does not cover its predecessor quote set"
        )
    for symbol, old in predecessor_quotes.items():
        old_time = _optional_quote_datetime(old)
        new_time = _optional_quote_datetime(current[symbol])
        if new_time is None or (require_comparable and old_time is None):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact quote chronology is not comparable: {symbol}"
            )
        if old_time is not None and new_time <= old_time:
            raise ManagerScreenQuoteImpactError(
                f"quote-impact quote as_of is not strictly increasing: {symbol}"
            )


def _optional_quote_datetime(value: Mapping[str, Any]) -> dt.datetime | None:
    candidates = [value.get("as_of")]
    facts = value.get("manager_screen_facts")
    if isinstance(facts, Mapping):
        freshness = facts.get("quote_freshness")
        if isinstance(freshness, Mapping):
            candidates.insert(0, freshness.get("quote_as_of"))
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        try:
            parsed = dt.datetime.fromisoformat(raw)
        except ValueError:
            continue
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed
    return None


def _original_packet_quotes(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    dossiers = packet.get("dossiers")
    if not isinstance(dossiers, list):
        raise ManagerScreenQuoteImpactError("manager-screen packet dossiers are invalid")
    result = {}
    for dossier in dossiers:
        symbol = dossier.get("symbol") if isinstance(dossier, Mapping) else None
        quote = dossier.get("market_snapshot") if isinstance(dossier, Mapping) else None
        if not isinstance(symbol, str) or symbol in result or not isinstance(quote, Mapping):
            raise ManagerScreenQuoteImpactError(
                "manager-screen packet quote projection is invalid"
            )
        result[symbol] = dict(quote)
    return result


def _original_decision_sources(
    inputs: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, dict[str, Any]]:
    path = _relative(inputs["result_path"], repository_root)
    sha256 = inputs["result_seal"].sha256
    return {
        decision["symbol"]: {
            "symbol": decision["symbol"],
            "artifact_type": "manager_screen_result",
            "path": path,
            "sha256": sha256,
            "review_id": None,
        }
        for decision in inputs["result"]["decisions"]
    }


def _validated_predecessor(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != PREDECESSOR_KEYS:
        raise ManagerScreenQuoteImpactError("quote-impact predecessor fields are invalid")
    result = dict(value)
    if result["result_artifact_type"] not in {
        "manager_screen_result",
        "manager_screen_quote_impact_result",
    }:
        raise ManagerScreenQuoteImpactError("quote-impact predecessor result type is invalid")
    if result["quote_artifact_type"] not in {
        "manager_screen_packet",
        "manager_screen_quote_amendment",
    }:
        raise ManagerScreenQuoteImpactError("quote-impact predecessor quote type is invalid")
    for field in ("result_path", "quote_path"):
        if (
            not isinstance(result[field], str)
            or not result[field]
            or Path(result[field]).is_absolute()
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact predecessor {field} is invalid"
            )
    for field in ("result_sha256", "quote_sha256"):
        digest = result[field]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ManagerScreenQuoteImpactError(
                f"quote-impact predecessor {field} is invalid"
            )
    review_id = result["review_id"]
    if result["result_artifact_type"] == "manager_screen_result":
        if review_id is not None or result["quote_artifact_type"] != "manager_screen_packet":
            raise ManagerScreenQuoteImpactError(
                "root quote-impact predecessor semantics are invalid"
            )
    elif (
        not isinstance(review_id, str)
        or _identifier(review_id, "predecessor review_id") != review_id
        or result["quote_artifact_type"] != "manager_screen_quote_amendment"
    ):
        raise ManagerScreenQuoteImpactError(
            "chained quote-impact predecessor semantics are invalid"
        )
    return result


def _effective_decisions_before_entry(
    chain: Mapping[str, Any],
    *,
    review_id: str,
) -> list[dict[str, Any]]:
    for entry in chain["entries"]:
        if entry["review_id"] == review_id:
            return [dict(row) for row in entry["effective_decisions_before"]]
    raise ManagerScreenQuoteImpactError("quote-impact review is missing from its chain")


def _build_quote_impact_result(
    *,
    run_id: str,
    batch_id: str,
    review_id: str,
    recorded_at: dt.datetime,
    plan: Mapping[str, Any],
    plan_path: Path,
    plan_sha256: str,
    packet_path: Path,
    packet_sha256: str,
    manager: Mapping[str, Any],
    reviews: list[Mapping[str, Any]],
    decisions: list[Mapping[str, Any]],
    predecessor_effective_decisions: list[Mapping[str, Any]],
    repository_root: Path,
) -> dict[str, Any]:
    effective = {
        decision["symbol"]: dict(decision)
        for decision in predecessor_effective_decisions
    }
    order = [decision["symbol"] for decision in predecessor_effective_decisions]
    for review in reviews:
        effective[review["symbol"]] = dict(review["effective_decision"])
    cumulative = [effective[symbol] for symbol in order]
    automatic_noop = not reviews and plan.get("candidate_count") == 0
    return {
        "schema_version": 2,
        "run_id": run_id,
        "batch_id": batch_id,
        "review_id": review_id,
        "chain_version": QUOTE_IMPACT_CHAIN_VERSION,
        "chain_sequence": plan["chain_sequence"],
        "predecessor": dict(plan["predecessor"]),
        "recorded_at": recorded_at.isoformat(),
        "plan_path": _relative(plan_path, repository_root),
        "plan_sha256": plan_sha256,
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_sha256,
        "original_result_path": plan["original_result_path"],
        "original_result_sha256": plan["original_result_sha256"],
        "quote_amendment_path": plan["quote_amendment_path"],
        "quote_amendment_sha256": plan["quote_amendment_sha256"],
        "policy_payload_sha256": plan["policy"]["payload_sha256"],
        "manager": dict(manager),
        "automatic_noop": automatic_noop,
        "reviews": [dict(row) for row in reviews],
        "decisions": [dict(row) for row in decisions],
        "effective_decisions": cumulative,
        "effective_decisions_sha256": _payload_sha256(cumulative),
        "summary": {
            "candidate_count": len(reviews),
            "keep_count": sum(row["action"] == "keep" for row in reviews),
            "replacement_count": sum(row["action"] == "replacement" for row in reviews),
            "new_send_to_analyst_count": sum(
                row["action"] == "replacement"
                and row["old_route"] != "send_to_analyst"
                and row["effective_decision"]["route"] == "send_to_analyst"
                for row in reviews
            ),
        },
        "portfolio_action": None,
    }


def _chain_entry_summary(
    entry: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    verified = entry["verified"]
    result = verified["result"]
    return {
        "schema_version": verified["plan"].get("schema_version", 1),
        "run_id": verified["plan"]["run_id"],
        "batch_id": verified["plan"]["batch_id"],
        "review_id": entry["review_id"],
        "state": entry["state"],
        "candidate_count": verified["plan"]["candidate_count"],
        "candidate_symbols": list(verified["plan"]["candidate_symbols"]),
        "plan_path": _relative(verified["plan_path"], repository_root),
        "plan_sha256": verified["plan_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "result_path": (
            _relative(verified["result_path"], repository_root) if result is not None else None
        ),
        "result_sha256": verified["result_seal"].sha256 if result is not None else None,
        "portfolio_action": None,
    }


def _sealed_artifact_presence(path: Path) -> str:
    seal = path.with_name(f"{path.name}.seal.json")
    if path.exists() and seal.exists():
        return "complete"
    if path.exists() or seal.exists():
        return "partial"
    return "absent"


def _payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _candidate_rows(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    predecessor_decisions = inputs.get("predecessor_decisions") or inputs["result"]["decisions"]
    decisions = {row["symbol"]: row for row in predecessor_decisions}
    decision_sources = inputs.get("predecessor_decision_sources") or {}
    dossiers = {row["symbol"]: row for row in inputs["packet"]["dossiers"]}
    quotes = {row["symbol"]: row for row in inputs["amendment"]["quotes"]}
    predecessor_quotes = inputs.get("predecessor_quotes") or {
        symbol: dossier.get("market_snapshot")
        for symbol, dossier in dossiers.items()
    }
    threshold = inputs["policy_ref"]["absolute_price_change_pct"]
    rows = []
    for original in inputs["result"]["decisions"]:
        symbol = original["symbol"]
        decision = decisions.get(symbol)
        dossier = dossiers.get(symbol)
        quote = quotes.get(symbol)
        old_quote = predecessor_quotes.get(symbol)
        if (
            not isinstance(decision, Mapping)
            or not isinstance(dossier, Mapping)
            or not isinstance(quote, Mapping)
            or not isinstance(old_quote, Mapping)
        ):
            raise ManagerScreenQuoteImpactError(f"quote-impact inputs are missing symbol: {symbol}")
        old_price = _price_for_comparison(old_quote.get("price"))
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
            "old_price": (old_price if old_price is not None else old_quote.get("price")),
            "new_price": (new_price if new_price is not None else quote.get("price")),
            "price_change_pct": delta,
            "absolute_price_change_pct": (abs(delta) if delta is not None else None),
            "old_decision": dict(decisions[symbol]),
            "old_decision_source": dict(decision_sources.get(symbol) or {}),
            "old_quote_source": dict(inputs.get("predecessor", {}).get("binding") or {}),
            "valuation": {
                "old": {field: old_quote.get(field) for field in VALUATION_FIELDS},
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
        if inputs["decision_contract_version"] in {2, 3}:
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
        raise ManagerScreenQuoteImpactError("v2 quote-impact decision support is invalid") from exc


def _quote_decision_support_inputs(
    *,
    dossier: Mapping[str, Any],
    quote: Mapping[str, Any],
    batch_policy: Mapping[str, Any],
    canonical_source_evidence_id: str,
) -> dict[str, Any]:
    market = dossier.get("market_snapshot")
    if not isinstance(market, Mapping):
        raise ManagerScreenQuoteImpactError("v2 quote-impact dossier market snapshot is invalid")
    amended_market = dict(market)
    amended_market["price"] = quote.get("price")
    for field in VALUATION_FIELDS:
        amended_market[field] = quote.get(field)
    facts = amended_market.get("manager_screen_facts")
    if not isinstance(facts, Mapping):
        raise ManagerScreenQuoteImpactError("v2 quote-impact dossier facts are invalid")
    facts = dict(facts)
    facts.pop("decision_support", None)
    amended_market["manager_screen_facts"] = facts
    threshold = _positive_number(
        batch_policy.get("high_liability_to_assets_pct"),
        "high_liability_to_assets_pct",
    )
    if threshold > 100:
        raise ManagerScreenQuoteImpactError("high_liability_to_assets_pct must be at most 100")
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
            dossier.get("timeline") if isinstance(dossier.get("timeline"), Mapping) else None
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
        raise ManagerScreenQuoteImpactError("sealed manager-screen batch policy is invalid")
    decision_contract_version = batch_policy.get("decision_contract_version", 1)
    if decision_contract_version not in {1, 2, 3}:
        raise ManagerScreenQuoteImpactError(
            "sealed manager-screen decision contract version is invalid"
        )
    if decision_contract_version in {2, 3} and (
        not DECISION_V2_POLICY_KEYS.issubset(batch_policy)
        or batch_policy.get("mandatory_risk_acknowledgement") is not True
        or batch_policy.get("canonical_fact_line_required") is not True
    ):
        raise ManagerScreenQuoteImpactError(
            "sealed manager-screen decision v2 policy is incomplete"
        )
    if decision_contract_version == 3 and (
        not DECISION_V3_POLICY_KEYS.issubset(batch_policy)
        or batch_policy.get("research_candidate_requires_allocation") is not True
    ):
        raise ManagerScreenQuoteImpactError(
            "sealed manager-screen decision v3 policy is incomplete"
        )
    expected_decision_keys = (
        DECISION_V2_KEYS if decision_contract_version in {2, 3} else DECISION_KEYS
    )
    for decision in decisions:
        if not isinstance(decision, Mapping) or set(decision) != expected_decision_keys:
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
            for key in (
                DECISION_V2_POLICY_KEYS
                | (DECISION_V3_POLICY_KEYS if decision_contract_version == 3 else set())
            )
        }
        if decision_contract_version in {2, 3}
        else {}
    )
    return {
        "repository_root": repository_root,
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
            if decision_contract_version in {2, 3}:
                raise ManagerScreenQuoteImpactError(
                    f"v2+ quote-impact review requires a complete replacement: {symbol}"
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
    expected_keys = DECISION_V2_KEYS if decision_contract_version in {2, 3} else DECISION_KEYS
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ManagerScreenQuoteImpactError(
            f"replacement decision fields do not match contract: {symbol}"
        )
    if _symbol(value.get("symbol")) != symbol:
        raise ManagerScreenQuoteImpactError(f"replacement decision symbol mismatch: {symbol}")
    route = value.get("route")
    if route not in _routes_for_version(decision_contract_version):
        raise ManagerScreenQuoteImpactError(f"invalid replacement route: {route}")
    reason = _text(value.get("one_line_reason"), f"{symbol}.one_line_reason")
    if decision_contract_version in {2, 3}:
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
    if decision_contract_version in {2, 3}:
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
    purchases_already_recorded: bool = False,
) -> None:
    capacity = plan["policy"]["send_to_analyst_capacity_per_run"]
    already_purchased = _prior_purchased_symbols_for_plan(base=base, plan=plan)
    new_purchases = sum(
        review["action"] == "replacement"
        and review["old_route"] != "send_to_analyst"
        and review["effective_decision"]["route"] == "send_to_analyst"
        and review["symbol"] not in already_purchased
        for review in reviews
    )
    if purchases_already_recorded:
        # The immutable result passed this check before sealing.  Replays may
        # be repairing a queue/screening crash, so live status can legitimately
        # lag the sealed replacement and must not block deterministic repair.
        return
    if new_purchases:
        _reject_post_contract_direct_quote_purchases(
            base=base,
            run_id=run_id,
        )
    from .manager_screening import ManagerScreeningError, manager_screen_status

    try:
        status = manager_screen_status(root=base, run_id=run_id)
    except ManagerScreeningError as exc:
        raise ManagerScreenQuoteImpactError(
            "manager-screen status is invalid during cumulative quote-impact capacity accounting"
        ) from exc
    budget = status.get("analyst_budget")
    if not isinstance(budget, Mapping):
        raise ManagerScreenQuoteImpactError(
            "manager-screen status is missing cumulative analyst purchases"
        )
    purchased_before = budget.get("purchased_company_count")
    if isinstance(purchased_before, bool) or not isinstance(purchased_before, int):
        raise ManagerScreenQuoteImpactError(
            "manager-screen cumulative analyst purchase count is invalid"
        )
    projected_purchases = purchased_before + new_purchases
    if projected_purchases > capacity:
        raise ManagerScreenQuoteImpactError(
            "quote-impact replacements exceed cumulative manager-screen analyst "
            "purchase capacity: "
            f"{purchased_before} purchased before + "
            f"{new_purchases} new purchases "
            f"> {capacity}"
        )


def _prior_purchased_symbols_for_plan(
    *,
    base: Path,
    plan: Mapping[str, Any],
) -> set[str]:
    original_path = plan.get("original_result_path")
    original_sha256 = plan.get("original_result_sha256")
    run_id = plan.get("run_id")
    batch_id = plan.get("batch_id")
    if not all(isinstance(value, str) and value for value in (
        original_path,
        original_sha256,
        run_id,
        batch_id,
    )):
        return set()
    repository_root = base.parent.parent.resolve()
    payload, sealed = _sealed_object(
        _repository_file(original_path, repository_root=repository_root),
        artifact_type="manager_screen_result",
    )
    if sealed.sha256 != original_sha256:
        raise ManagerScreenQuoteImpactError(
            "quote-impact capacity original result binding is invalid"
        )
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ManagerScreenQuoteImpactError(
            "quote-impact capacity original decisions are invalid"
        )
    purchased = {
        decision["symbol"]
        for decision in decisions
        if isinstance(decision, Mapping)
        and isinstance(decision.get("symbol"), str)
        and decision.get("route") == "send_to_analyst"
    }
    overlay = load_manager_screen_quote_impact_overlay(
        root=base,
        run_id=run_id,
        batch_id=batch_id,
    )
    purchased.update(row["symbol"] for row in overlay["purchase_reviews"])
    return purchased


def _reject_post_contract_direct_quote_purchases(
    *,
    base: Path,
    run_id: str,
) -> None:
    contract_path = (
        base / "manager-screen" / run_id / "governance" / "allocation-v3" / "contract.json"
    )
    seal_path = contract_path.with_name(f"{contract_path.name}.seal.json")
    artifact = contract_path.exists()
    seal = seal_path.exists()
    if not artifact and not seal:
        return
    if artifact != seal:
        raise ManagerScreenQuoteImpactError(
            "allocation v3 contract is only partially sealed; direct quote-impact "
            "analyst purchase is forbidden"
        )
    from .manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
        verify_manager_screen_allocation_v3_contract,
    )

    try:
        verify_manager_screen_allocation_v3_contract(root=base, run_id=run_id)
    except ManagerScreenAllocationV3Error as exc:
        raise ManagerScreenQuoteImpactError(
            "allocation v3 contract is invalid; direct quote-impact analyst purchase is forbidden"
        ) from exc
    raise ManagerScreenQuoteImpactError(
        "post-contract quote-impact review cannot purchase analyst budget directly"
    )


def _require_suspended_quote_projection(
    *,
    current: Mapping[str, Any],
    screen: Mapping[str, Any] | None,
    member: Mapping[str, Any],
    suspension_binding: Mapping[str, Any],
    plan: Mapping[str, Any],
    result_path: str,
    result_sha256: str,
    symbol: str,
    old_decision_source: Mapping[str, Any] | None = None,
) -> None:
    original_path = member.get("manager_screen_result_path")
    original_sha256 = member.get("manager_screen_result_sha256")
    prior_path = (
        old_decision_source.get("path")
        if isinstance(old_decision_source, Mapping)
        else original_path
    )
    prior_sha256 = (
        old_decision_source.get("sha256")
        if isinstance(old_decision_source, Mapping)
        else original_sha256
    )
    allowed_bindings = {(prior_path, prior_sha256), (result_path, result_sha256)}
    history = current.get("stage_history")
    suspension_receipt = isinstance(history, list) and any(
        isinstance(item, Mapping)
        and item.get("stage") == "manager_screen_allocation_v3_suspension"
        and item.get("suspension_sha256") == suspension_binding.get("sha256")
        for item in history
    )
    if (
        member.get("symbol") != symbol
        or original_path != plan.get("original_result_path")
        or original_sha256 != plan.get("original_result_sha256")
        or (
            current.get("manager_screen_result_path"),
            current.get("manager_screen_result_sha256"),
        )
        not in allowed_bindings
        or current.get("manager_screen_run_id") != plan.get("run_id")
        or current.get("manager_screen_batch_id") not in {None, plan.get("batch_id")}
        or current.get("task_type") != "manager_screen"
        or current.get("status") != "completed"
        or current.get("assigned_agent") is not None
        or current.get("started_at") is not None
        or current.get("research_budget_state") != "candidate_unfunded"
        or current.get("research_budget_suspension_path")
        != suspension_binding.get("path")
        or current.get("research_budget_suspension_sha256")
        != suspension_binding.get("sha256")
        or current.get("result_path") != current.get("manager_screen_result_path")
        or not suspension_receipt
        or not isinstance(screen, Mapping)
        or (
            screen.get("manager_screen_result_path"),
            screen.get("manager_screen_result_sha256"),
        )
        not in allowed_bindings
        or screen.get("manager_screen_run_id") != plan.get("run_id")
        or screen.get("manager_screen_batch_id") not in {None, plan.get("batch_id")}
        or screen.get("decision") != "candidate_unfunded"
        or screen.get("state") != "candidate_unfunded"
        or screen.get("research_budget_state") != "candidate_unfunded"
        or screen.get("research_budget_suspension_path")
        != suspension_binding.get("path")
        or screen.get("research_budget_suspension_sha256")
        != suspension_binding.get("sha256")
    ):
        raise ManagerScreenQuoteImpactError(
            "sealed allocation-v3 suspension projection drifted before quote-impact "
            f"evolution: {symbol}"
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
    suspension_binding: Mapping[str, Any] | None = None,
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
        suspended_member = None
        if suspension_binding is not None:
            members = suspension_binding.get("members")
            if not isinstance(members, Mapping):
                raise ManagerScreenQuoteImpactError(
                    "allocation-v3 suspension member index is invalid"
                )
            suspended_member = members.get(symbol)
        if suspended_member is not None:
            _require_suspended_quote_projection(
                current=current,
                screen=screening.get(symbol),
                member=suspended_member,
                suspension_binding=suspension_binding,
                plan=plan,
                result_path=result_relative,
                result_sha256=result_sha256,
                symbol=symbol,
                old_decision_source=packet_rows[symbol].get("old_decision_source"),
            )
        old_source = packet_rows[symbol].get("old_decision_source")
        predecessor_path = (
            old_source.get("path")
            if isinstance(old_source, Mapping)
            else plan["original_result_path"]
        )
        predecessor_sha256 = (
            old_source.get("sha256")
            if isinstance(old_source, Mapping)
            else plan.get("original_result_sha256")
            or current.get("manager_screen_result_sha256")
        )
        binding = (
            current.get("manager_screen_result_path"),
            current.get("manager_screen_result_sha256"),
        )
        if binding not in {
            (predecessor_path, predecessor_sha256),
            (result_relative, result_sha256),
        }:
            raise ManagerScreenQuoteImpactError(
                f"coverage has a different manager result binding: {symbol}"
            )
        already_bound = (
            binding == (result_relative, result_sha256)
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
                    "predecessor_result_path": predecessor_path,
                    "predecessor_result_sha256": predecessor_sha256,
                    "chain_sequence": plan.get("chain_sequence", 1),
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
            if suspended_member is not None:
                updated.update(
                    {
                        "task_type": "manager_screen",
                        "status": "completed",
                        "finished_at": result["recorded_at"],
                        "result_path": result_relative,
                        "next_action": (
                            "Keep as an unfunded candidate until the complete-scope "
                            "sealed allocation partitions the full market."
                        ),
                        "research_budget_state": "candidate_unfunded",
                    }
                )
                for field in (
                    "effort_budget_hours",
                    "preceding_stage",
                    "stop_conditions",
                ):
                    updated.pop(field, None)
            elif decision["route"] == "send_to_analyst":
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
                            else (
                                "Reassess on the sealed watch trigger."
                                if decision["route"] == "watch"
                                else (
                                    "Keep as an unfunded candidate until the full-scope "
                                    "sealed research allocation."
                                )
                            )
                        ),
                    }
                )
                for field in (
                    "effort_budget_hours",
                    "preceding_stage",
                    "stop_conditions",
                ):
                    updated.pop(field, None)
            if suspended_member is not None:
                updated["research_budget_state"] = "candidate_unfunded"
            elif decision["route"] == "research_candidate":
                updated["research_budget_state"] = "candidate_unfunded"
            else:
                updated.pop("research_budget_state", None)
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
                    "decision": (
                        "candidate_unfunded"
                        if suspended_member is not None
                        else {
                            "pass": "catalog",
                            "watch": "watch_only",
                            "send_to_analyst": "quick_profile",
                            "research_candidate": "candidate_unfunded",
                        }[decision["route"]]
                    ),
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
            if suspended_member is not None:
                screen.update(
                    {
                        "state": "candidate_unfunded",
                        "research_budget_state": "candidate_unfunded",
                        "research_budget_suspension_path": suspension_binding["path"],
                        "research_budget_suspension_sha256": suspension_binding["sha256"],
                    }
                )
            elif decision["route"] == "research_candidate":
                screen["research_budget_state"] = "candidate_unfunded"
            else:
                screen.pop("research_budget_state", None)
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
    plan_schema = plan.get("schema_version")
    if plan_schema not in {1, 2} or packet.get("schema_version") != plan_schema:
        raise ManagerScreenQuoteImpactError(
            "quote-impact plan and packet schema versions are invalid"
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
    predecessor = None
    if plan_schema == 2:
        if (
            plan.get("chain_version") != QUOTE_IMPACT_CHAIN_VERSION
            or isinstance(plan.get("chain_sequence"), bool)
            or not isinstance(plan.get("chain_sequence"), int)
            or plan["chain_sequence"] <= 0
        ):
            raise ManagerScreenQuoteImpactError("quote-impact chain metadata is invalid")
        predecessor = _validated_predecessor(plan.get("predecessor"))
        predecessor_result_path = _repository_file(
            predecessor["result_path"],
            repository_root=repository_root,
        )
        _, predecessor_result_seal = _sealed_object(
            predecessor_result_path,
            artifact_type=predecessor["result_artifact_type"],
        )
        predecessor_quote_path = _repository_file(
            predecessor["quote_path"],
            repository_root=repository_root,
        )
        _, predecessor_quote_seal = _sealed_object(
            predecessor_quote_path,
            artifact_type=predecessor["quote_artifact_type"],
        )
        if (
            predecessor_result_seal.sha256 != predecessor["result_sha256"]
            or predecessor_quote_seal.sha256 != predecessor["quote_sha256"]
        ):
            raise ManagerScreenQuoteImpactError(
                "quote-impact predecessor sealed binding is invalid"
            )
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
    result_presence = _sealed_artifact_presence(result_path)
    if result_presence == "partial":
        raise ManagerScreenQuoteImpactError("quote-impact result is only partially sealed")
    if result_presence == "complete":
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
            or (
                plan_schema == 2
                and (
                    result.get("schema_version") != 2
                    or result.get("chain_version") != plan.get("chain_version")
                    or result.get("chain_sequence") != plan.get("chain_sequence")
                    or result.get("predecessor") != predecessor
                )
            )
        ):
            raise ManagerScreenQuoteImpactError("quote-impact result bindings are invalid")
    elif require_result:
        raise ManagerScreenQuoteImpactError("quote-impact result is missing")
    return {
        "repository_root": repository_root,
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
            raise ManagerScreenQuoteImpactError("quote-impact policy provenance is invalid")
    for field in ("file_sha256", "payload_sha256"):
        digest = value.get(field)
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ManagerScreenQuoteImpactError("quote-impact policy digest is invalid")
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
        raise ManagerScreenQuoteImpactError("quote-impact policy stop conditions are invalid")
    if DECISION_V2_POLICY_KEYS.intersection(value):
        contract_version = value.get("decision_contract_version")
        if (
            not DECISION_V2_POLICY_KEYS.issubset(value)
            or contract_version not in {2, 3}
            or value.get("mandatory_risk_acknowledgement") is not True
            or value.get("canonical_fact_line_required") is not True
        ):
            raise ManagerScreenQuoteImpactError(
                "quote-impact sealed decision v2+ policy is invalid"
            )
        if contract_version == 3:
            if (
                not DECISION_V3_POLICY_KEYS.issubset(value)
                or value.get("research_candidate_requires_allocation") is not True
            ):
                raise ManagerScreenQuoteImpactError(
                    "quote-impact sealed decision v3 policy is invalid"
                )
        elif DECISION_V3_POLICY_KEYS.intersection(value):
            raise ManagerScreenQuoteImpactError(
                "quote-impact sealed v2 policy contains v3-only fields"
            )
        liability_threshold = _positive_number(
            value.get("high_liability_to_assets_pct"),
            "high_liability_to_assets_pct",
        )
        if liability_threshold > 100:
            raise ManagerScreenQuoteImpactError("high_liability_to_assets_pct must be at most 100")
    payload = value.get("payload")
    if payload is None:
        # v1 plans sealed before immutable payload embedding retain the
        # decision-critical fields above. Their provenance hashes remain audit
        # metadata; verification must not depend on the mutable live policy.
        return
    if not isinstance(payload, Mapping):
        raise ManagerScreenQuoteImpactError("quote-impact embedded policy payload is invalid")
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
        hashlib.sha256(canonical_json_bytes(payload)).hexdigest() != value["payload_sha256"]
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


def _verified_predecessor_projection(
    verified: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    plan = verified["plan"]
    predecessor = _validated_predecessor(plan.get("predecessor"))
    if predecessor["result_artifact_type"] == "manager_screen_result":
        decisions = [dict(row) for row in verified["original_result"]["decisions"]]
    else:
        path = _repository_file(
            predecessor["result_path"],
            repository_root=verified["repository_root"],
        )
        payload, sealed = _sealed_object(
            path,
            artifact_type="manager_screen_quote_impact_result",
        )
        if (
            sealed.sha256 != predecessor["result_sha256"]
            or payload.get("run_id") != plan["run_id"]
            or payload.get("batch_id") != plan["batch_id"]
            or payload.get("review_id") != predecessor["review_id"]
        ):
            raise ManagerScreenQuoteImpactError(
                "quote-impact predecessor result projection is invalid"
            )
        if payload.get("schema_version") == 2:
            rows = payload.get("effective_decisions")
            if not isinstance(rows, list):
                raise ManagerScreenQuoteImpactError(
                    "quote-impact predecessor effective decisions are missing"
                )
            decisions = [dict(row) for row in rows if isinstance(row, Mapping)]
            if len(decisions) != len(rows):
                raise ManagerScreenQuoteImpactError(
                    "quote-impact predecessor effective decisions are invalid"
                )
        else:
            decisions_by_symbol = {
                row["symbol"]: dict(row) for row in verified["original_result"]["decisions"]
            }
            for review in payload.get("reviews") or []:
                if not isinstance(review, Mapping):
                    raise ManagerScreenQuoteImpactError(
                        "legacy quote-impact predecessor reviews are invalid"
                    )
                decisions_by_symbol[review["symbol"]] = dict(review["effective_decision"])
            decisions = [
                decisions_by_symbol[row["symbol"]]
                for row in verified["original_result"]["decisions"]
            ]
    if predecessor["quote_artifact_type"] == "manager_screen_packet":
        quotes = _original_packet_quotes(verified["original_packet"])
    else:
        path = _repository_file(
            predecessor["quote_path"],
            repository_root=verified["repository_root"],
        )
        payload, sealed = _sealed_object(
            path,
            artifact_type="manager_screen_quote_amendment",
        )
        rows = payload.get("quotes")
        if sealed.sha256 != predecessor["quote_sha256"] or not isinstance(rows, list):
            raise ManagerScreenQuoteImpactError(
                "quote-impact predecessor quote projection is invalid"
            )
        quotes = {
            row["symbol"]: dict(row)
            for row in rows
            if isinstance(row, Mapping) and isinstance(row.get("symbol"), str)
        }
        if len(quotes) != len(rows):
            raise ManagerScreenQuoteImpactError(
                "quote-impact predecessor quote symbols are invalid"
            )
    return decisions, quotes


def _decision_from_bound_source(
    value: Any,
    *,
    repository_root: Path,
    symbol: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != DECISION_SOURCE_KEYS:
        raise ManagerScreenQuoteImpactError(
            f"quote-impact old-decision source is invalid: {symbol}"
        )
    if value.get("symbol") != symbol:
        raise ManagerScreenQuoteImpactError(
            f"quote-impact old-decision source symbol is invalid: {symbol}"
        )
    artifact_type = value.get("artifact_type")
    if artifact_type not in {
        "manager_screen_result",
        "manager_screen_quote_impact_result",
    }:
        raise ManagerScreenQuoteImpactError(
            f"quote-impact old-decision source type is invalid: {symbol}"
        )
    path = _repository_file(value.get("path"), repository_root=repository_root)
    payload, sealed = _sealed_object(path, artifact_type=artifact_type)
    if sealed.sha256 != value.get("sha256"):
        raise ManagerScreenQuoteImpactError(
            f"quote-impact old-decision source SHA is invalid: {symbol}"
        )
    if artifact_type == "manager_screen_result":
        if value.get("review_id") is not None:
            raise ManagerScreenQuoteImpactError(
                f"quote-impact original decision source review is invalid: {symbol}"
            )
        rows = payload.get("decisions") or []
    else:
        if payload.get("review_id") != value.get("review_id"):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact decision source review is invalid: {symbol}"
            )
        if isinstance(payload.get("effective_decisions"), list):
            rows = payload["effective_decisions"]
        else:
            rows = [
                review.get("effective_decision")
                for review in payload.get("reviews") or []
                if isinstance(review, Mapping)
            ]
    matches = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("symbol") == symbol
    ]
    if len(matches) != 1:
        raise ManagerScreenQuoteImpactError(
            f"quote-impact old-decision source is ambiguous: {symbol}"
        )
    return matches[0]


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
    decision_policy_keys = DECISION_V2_POLICY_KEYS | (
        DECISION_V3_POLICY_KEYS if plan_decision_version == 3 else set()
    )
    if plan_decision_version in {2, 3} and any(
        plan["policy"].get(key) != batch["policy"].get(key) for key in decision_policy_keys
    ):
        raise ManagerScreenQuoteImpactError(
            "quote-impact decision v2+ policy does not match the sealed batch"
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
        raise ManagerScreenQuoteImpactError("quote-impact candidate plan or packet is invalid")
    original_decisions = original_result.get("decisions")
    if not isinstance(original_decisions, list):
        raise ManagerScreenQuoteImpactError("quote-impact original decisions are invalid")
    original_by_symbol: dict[str, Mapping[str, Any]] = {}
    expected_original_keys = DECISION_V2_KEYS if plan_decision_version in {2, 3} else DECISION_KEYS
    for decision in original_decisions:
        if not isinstance(decision, Mapping) or set(decision) != expected_original_keys:
            raise ManagerScreenQuoteImpactError("quote-impact original decision is invalid")
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
    if plan.get("schema_version") == 2:
        predecessor_decisions, predecessor_quotes = _verified_predecessor_projection(
            verified,
        )
        expected_old_by_symbol = {
            decision["symbol"]: decision for decision in predecessor_decisions
        }
    else:
        predecessor_quotes = {
            symbol: dossier.get("market_snapshot")
            for symbol, dossier in original_dossiers.items()
        }
        expected_old_by_symbol = original_by_symbol
    for symbol, row in zip(candidate_symbols, rows, strict=True):
        if (
            not isinstance(row, Mapping)
            or row.get("symbol") != symbol
            or not isinstance(row.get("old_decision"), Mapping)
            or dict(row["old_decision"]) != dict(expected_old_by_symbol.get(symbol) or {})
        ):
            raise ManagerScreenQuoteImpactError(
                f"quote-impact packet does not bind the predecessor decision: {symbol}"
            )
        if plan.get("schema_version") == 2:
            source_decision = _decision_from_bound_source(
                row.get("old_decision_source"),
                repository_root=verified["repository_root"],
                symbol=symbol,
            )
            old_quote = predecessor_quotes.get(symbol)
            valuation = row.get("valuation")
            if (
                source_decision != dict(row["old_decision"])
                or row.get("old_quote_source") != plan.get("predecessor")
                or not isinstance(old_quote, Mapping)
                or row.get("old_price")
                != (
                    _price_for_comparison(old_quote.get("price"))
                    if _price_for_comparison(old_quote.get("price")) is not None
                    else old_quote.get("price")
                )
                or not isinstance(valuation, Mapping)
                or valuation.get("old")
                != {field: old_quote.get(field) for field in VALUATION_FIELDS}
            ):
                raise ManagerScreenQuoteImpactError(
                    f"quote-impact packet predecessor projection is invalid: {symbol}"
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
        source_evidence_id = f"quote-amendment:{verified['amendment']['amendment_id']}:{symbol}"
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
        if not isinstance(valuation, Mapping) or valuation.get("new") != {
            field: quote.get(field) for field in VALUATION_FIELDS
        }:
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
    expected_schema = plan.get("schema_version", 1)
    if (
        result.get("schema_version") != expected_schema
        or result.get("original_result_path") != plan.get("original_result_path")
        or result.get("quote_amendment_path") != plan.get("quote_amendment_path")
        or result.get("policy_payload_sha256") != plan.get("policy", {}).get("payload_sha256")
        or result.get("manager") != original_result.get("manager")
        or result.get("portfolio_action") is not None
        or not isinstance(reviews, list)
        or not isinstance(decisions, list)
        or len(reviews) != len(candidate_symbols)
        or len(decisions) != len(candidate_symbols)
        or (
            expected_schema == 2
            and (
                result.get("automatic_noop")
                is not (len(candidate_symbols) == 0)
                or not isinstance(result.get("effective_decisions"), list)
                or result.get("effective_decisions_sha256")
                != _payload_sha256(result["effective_decisions"])
            )
        )
    ):
        raise ManagerScreenQuoteImpactError("quote-impact result content is invalid")
    if _parse_datetime(result.get("recorded_at"), "result recorded_at") < _parse_datetime(
        plan.get("prepared_at"),
        "plan prepared_at",
    ):
        raise ManagerScreenQuoteImpactError("quote-impact result predates its preparation")
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
            raise ManagerScreenQuoteImpactError(f"quote-impact review content is invalid: {symbol}")
        action = review.get("action")
        if action == "keep":
            if plan_decision_version in {2, 3}:
                raise ManagerScreenQuoteImpactError(
                    f"v2+ quote-impact result cannot keep stale price facts: {symbol}"
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
            raise ManagerScreenQuoteImpactError(f"quote-impact review action is invalid: {symbol}")
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
        raise ManagerScreenQuoteImpactError("quote-impact result is not canonically normalized")
    if expected_schema == 2:
        cumulative = {
            decision["symbol"]: dict(decision)
            for decision in predecessor_decisions
        }
        cumulative_order = [decision["symbol"] for decision in predecessor_decisions]
        for review in normalized_reviews:
            cumulative[review["symbol"]] = dict(review["effective_decision"])
        expected_effective = [cumulative[symbol] for symbol in cumulative_order]
        if result["effective_decisions"] != expected_effective:
            raise ManagerScreenQuoteImpactError(
                "quote-impact cumulative effective decisions do not match predecessor"
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
        raise ManagerScreenQuoteImpactError("quote-impact result summary is inconsistent")


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
        "automatic_noop": bool(result.get("automatic_noop")),
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
