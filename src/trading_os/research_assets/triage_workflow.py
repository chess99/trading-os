from __future__ import annotations

import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .company_timeline import publish_rapid_triage_to_company_timeline
from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    coverage_write_lock,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .models import canonical_company_name
from .research_allocation import ResearchAllocationError
from .sealing import seal_json, verify_sealed
from .triage_cohort import load_rapid_triage_cohort
from .trigger_hits import consume_trigger_hits

PACKAGE_KEYS = {
    "schema_version",
    "cycle_id",
    "symbol",
    "company_name",
    "as_of",
    "information_cutoff",
    "price_as_of",
    "price_source_id",
    "current_price",
    "review_mode",
    "prior_research_path",
    "trigger_context",
    "business_summary",
    "change_summary",
    "normalized_earnings_view",
    "expectations_view",
    "counterevidence",
    "business_legibility",
    "survival_status",
    "governance_status",
    "earnings_legibility",
    "valuation_signal",
    "research_value",
    "decisive_question",
    "reason_codes",
    "revisit_triggers",
    "sources",
    "provenance",
}
OPTIONAL_PACKAGE_KEYS = {"handled_hit_ids"}
PROVENANCE_KEYS = {"agent", "model", "tools", "generated_at"}
SOURCE_KEYS = {
    "source_id",
    "tier",
    "title",
    "accessed_at",
    "url",
    "local_path",
    "supports",
}
TRIGGER_KEYS = {"trigger_id", "type", "condition", "reason"}
SOURCE_TIERS = {"S1", "S2", "S3"}
TRIGGER_TYPES = {"filing", "price", "date", "event", "thesis", "ttl"}
REVIEW_MODES = {"baseline_recheck", "triggered_update"}
DECISION_PACKAGE_KEYS = {
    "schema_version",
    "cycle_id",
    "comparison_sha256",
    "decisions",
    "provenance",
}
DECISION_KEYS = {
    "symbol",
    "decision",
    "reason",
    "decisive_question",
    "counterevidence_considered",
}
DECISIONS = {"select_quick_profile", "defer"}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
CYCLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@serialized_coverage_write
def claim_rapid_triage_task(
    *,
    root: str | Path,
    agent: str,
    claimed_at: dt.datetime,
    symbol: str | None = None,
    lens: str | None = None,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    """Claim one L1.5 task while binding one agent to one company."""

    _aware(claimed_at, "claimed_at")
    agent_name = _text(agent, "agent")
    cycle = _cycle(cycle_id) if cycle_id is not None else None
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    queue = read_jsonl(queue_path)
    running = [
        item
        for item in queue
        if item.get("task_type") == "rapid_triage"
        and item.get("status") == "running"
        and item.get("assigned_agent") == agent_name
    ]
    if len(running) > 1:
        raise ResearchAllocationError(
            f"agent has multiple running rapid-triage tasks: {agent_name}"
        )
    if running:
        current = running[0]
        if symbol is not None and current.get("symbol") != symbol:
            raise ResearchAllocationError(
                f"agent already has a different rapid-triage task: {current.get('symbol')}"
            )
        if cycle is not None and current.get("triage_cycle_id") != cycle:
            raise ResearchAllocationError(
                f"agent already has a rapid-triage task in another cycle: "
                f"{current.get('triage_cycle_id')}"
            )
        return _claim_payload(current, idempotent=True)

    candidates = [
        item
        for item in queue
        if item.get("task_type") == "rapid_triage"
        and item.get("status") == "pending"
        and item.get("assigned_agent") is None
        and (_has_cohort_binding(item) or bool(item.get("selected_by")))
    ]
    if cycle is not None:
        candidates = [item for item in candidates if item.get("triage_cycle_id") == cycle]
    if symbol is not None:
        _symbol(symbol)
        candidates = [item for item in candidates if item.get("symbol") == symbol]
    if lens is not None:
        lens_name = _text(lens, "lens")
        candidates = [item for item in candidates if lens_name in (item.get("selected_by") or [])]
    if not candidates:
        raise ResearchAllocationError("no eligible rapid-triage task is available")
    candidates.sort(key=_claim_order)
    selected = dict(candidates[0])
    if _has_cohort_binding(selected):
        _verify_queue_cohort_binding(base, selected, expected_cycle=cycle)
    selected.update(
        {
            "status": "running",
            "assigned_agent": agent_name,
            "started_at": claimed_at.isoformat(),
            "finished_at": None,
            "failure_reason": None,
        }
    )
    write_jsonl(
        queue_path,
        [selected if item.get("symbol") == selected["symbol"] else item for item in queue],
    )
    return _claim_payload(selected, idempotent=False)


@serialized_coverage_write
def release_rapid_triage_task(
    *,
    root: str | Path,
    agent: str,
    symbol: str,
    failure_reason: str,
    released_at: dt.datetime,
) -> dict[str, Any]:
    """Release a failed L1.5 claim without losing the attempt audit."""

    _aware(released_at, "released_at")
    agent_name = _text(agent, "agent")
    ticker_symbol = _symbol(symbol)
    reason = _text(failure_reason, "failure_reason")
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    queue = read_jsonl(queue_path)
    record = _one(queue, ticker_symbol, "research queue")
    if record.get("task_type") != "rapid_triage":
        raise ResearchAllocationError(f"task is not rapid triage: {ticker_symbol}")
    if record.get("status") != "running":
        raise ResearchAllocationError(f"rapid-triage task is not running: {ticker_symbol}")
    if record.get("assigned_agent") != agent_name:
        raise ResearchAllocationError(
            f"only the assigned agent can release rapid triage: {ticker_symbol}"
        )
    attempts = list(record.get("attempt_history") or [])
    attempts.append(
        {
            "agent": agent_name,
            "started_at": record.get("started_at"),
            "finished_at": released_at.isoformat(),
            "status": "failed",
            "failure_reason": reason,
        }
    )
    updated = dict(record)
    updated.update(
        {
            "status": "pending",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "failure_reason": None,
            "attempt_history": attempts,
        }
    )
    write_jsonl(
        queue_path,
        [updated if item.get("symbol") == ticker_symbol else item for item in queue],
    )
    return {
        "schema_version": 1,
        "symbol": ticker_symbol,
        "status": "pending",
        "released_agent": agent_name,
        "attempt_count": len(attempts),
        "portfolio_action": None,
    }


def record_rapid_triage_package(
    package: Mapping[str, Any],
    *,
    root: str | Path,
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Publish one result, then consume any bound trigger hits.

    Trigger consumption deliberately happens after the package, company
    timeline, and coverage materialization commit.  If that final append fails,
    replaying this function repairs the ledger without rewriting the immutable
    research result.
    """

    with coverage_write_lock(root):
        normalized = _normalize_package(package, recorded_at=recorded_at)
        result = _record_rapid_triage_package_locked(
            normalized,
            root=root,
            recorded_at=recorded_at,
        )
    handled_hit_ids = normalized["handled_hit_ids"]
    if handled_hit_ids:
        ticker = normalized["symbol"].split(":", 1)[1]
        result["trigger_consumption"] = consume_trigger_hits(
            root=root,
            package_path=result["triage_path"],
            handled_hit_ids=handled_hit_ids,
            timeline_evidence={
                "meta_path": f"research/companies/CN/{ticker}/meta.json"
            },
            consumed_at=recorded_at,
            actor=normalized["provenance"]["agent"],
        )
    else:
        result["trigger_consumption"] = None
    return result


def _record_rapid_triage_package_locked(
    package: Mapping[str, Any],
    *,
    root: str | Path,
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Materialize one result while the caller owns the coverage write lock."""

    _aware(recorded_at, "recorded_at")
    normalized = _normalize_package(package, recorded_at=recorded_at)
    symbol = normalized["symbol"]
    ticker = symbol.split(":", 1)[1]
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    queue_record = _one(queue, symbol, "research queue")
    screening_record = _one(screening, symbol, "screening")
    evaluation = evaluate_rapid_triage(normalized)
    timestamp = recorded_at.strftime("%Y%m%dT%H%M%S%z")
    artifact_dir = base / "triage" / normalized["cycle_id"] / ticker
    package_path = artifact_dir / f"{timestamp}.triage.json"
    repository_root = base.parent.parent
    relative_path = package_path.relative_to(repository_root).as_posix()

    repeated = _verify_rapid_triage_record_replay(
        base=base,
        queue=queue,
        queue_record=queue_record,
        screening_record=screening_record,
        normalized=normalized,
        evaluation=evaluation,
        package_path=package_path,
        relative_path=relative_path,
        recorded_at=recorded_at,
    )
    if repeated is not None:
        return repeated

    if queue_record.get("task_type") != "rapid_triage":
        raise ResearchAllocationError(f"task is not rapid triage: {symbol}")
    if queue_record.get("status") not in {"pending", "running"}:
        raise ResearchAllocationError(
            f"rapid triage cannot be recorded from status {queue_record.get('status')}: {symbol}"
        )
    if canonical_company_name(normalized["company_name"]) != canonical_company_name(
        str(queue_record.get("name"))
    ):
        raise ResearchAllocationError(f"company name does not match queue: {symbol}")
    assigned = queue_record.get("assigned_agent")
    if assigned is not None and assigned != normalized["provenance"]["agent"]:
        raise ResearchAllocationError(
            f"rapid-triage provenance agent does not match assignment: {symbol}"
        )
    expected_hit_ids = (
        queue_record.get("bound_trigger_hit_ids")
        if queue_record.get("bound_trigger_hit_ids") is not None
        else queue_record.get("trigger_hit_ids")
    ) or []
    if not isinstance(expected_hit_ids, list) or not all(
        isinstance(value, str) for value in expected_hit_ids
    ):
        raise ResearchAllocationError(f"queue trigger_hit_ids are invalid: {symbol}")
    if expected_hit_ids and normalized["handled_hit_ids"] != expected_hit_ids:
        raise ResearchAllocationError(
            f"rapid-triage handled_hit_ids do not match lane intake: {symbol}"
        )
    binding = _resolve_triage_binding(
        base,
        queue,
        queue_record,
        expected_cycle=normalized["cycle_id"],
    )
    _validate_local_sources(normalized["sources"], repository_root=base.parent.parent)
    _validate_prior_research_path(
        normalized["prior_research_path"], repository_root=base.parent.parent
    )

    sealed = seal_json(
        package_path,
        normalized,
        artifact_type="rapid_triage_package",
        sealed_at=recorded_at,
    )
    timeline_result = publish_rapid_triage_to_company_timeline(
        repository_root=repository_root,
        package_path=package_path,
        published_at=recorded_at,
        review_mode=normalized["review_mode"],
    )

    updated_screening = dict(screening_record)
    updated_screening.update(
        {
            "decision": evaluation["disposition"],
            "reason": _disposition_reason(evaluation["disposition"]),
            "evidence": [
                f"rapid_triage:{relative_path}",
                f"rapid_triage_sha256:{sealed.sha256}",
                f"{binding['evidence_prefix']}:{binding['sha256']}",
                f"triage_reason_codes:{','.join(normalized['reason_codes'])}",
            ],
            "next_action": _disposition_action(evaluation["disposition"]),
            "triage_cycle_id": normalized["cycle_id"],
            "triage_result_path": relative_path,
            "triage_recorded_at": recorded_at.isoformat(),
        }
    )
    history = list(queue_record.get("stage_history") or [])
    history.append(
        {
            "stage": "rapid_triage",
            "status": "completed",
            "finished_at": recorded_at.isoformat(),
            "agent": normalized["provenance"]["agent"],
            "result_path": relative_path,
            "disposition": evaluation["disposition"],
            "cycle_id": normalized["cycle_id"],
        }
    )
    updated_queue = dict(queue_record)
    updated_queue.pop("triage_priority_score", None)
    updated_queue.update(
        {
            "status": "completed",
            "finished_at": recorded_at.isoformat(),
            "result_path": relative_path,
            "failure_reason": None,
            "next_action": _disposition_action(evaluation["disposition"]),
            "stage_history": history,
            "triage_cycle_id": normalized["cycle_id"],
            "triage_disposition": evaluation["disposition"],
            "triage_review_mode": normalized["review_mode"],
            "handled_hit_ids": normalized["handled_hit_ids"],
            "revisit_triggers": normalized["revisit_triggers"],
            "company_timeline_report_path": timeline_result["company_report_path"],
        }
    )
    write_jsonl(
        screening_path,
        [updated_screening if item.get("symbol") == symbol else item for item in screening],
    )
    write_jsonl(
        queue_path,
        [updated_queue if item.get("symbol") == symbol else item for item in queue],
    )
    return {
        "schema_version": 1,
        "symbol": symbol,
        "disposition": evaluation["disposition"],
        "triage_path": relative_path,
        "triage_sha256": sealed.sha256,
        "company_timeline_report_path": timeline_result["company_report_path"],
        "awaiting_cohort_comparison": (evaluation["disposition"] == "triage_candidate"),
        "idempotent": False,
        "portfolio_action": None,
    }


def _verify_rapid_triage_record_replay(
    *,
    base: Path,
    queue: list[dict[str, Any]],
    queue_record: Mapping[str, Any],
    screening_record: Mapping[str, Any],
    normalized: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    package_path: Path,
    relative_path: str,
    recorded_at: dt.datetime,
) -> dict[str, Any] | None:
    """Verify a completed record without rematerializing mutable coverage state."""

    cycle = str(normalized["cycle_id"])
    completed = [
        item
        for item in queue_record.get("stage_history") or []
        if isinstance(item, Mapping)
        and item.get("stage") == "rapid_triage"
        and item.get("status") == "completed"
        and item.get("cycle_id") == cycle
    ]
    if not completed:
        if (
            queue_record.get("task_type") == "rapid_triage"
            and queue_record.get("status") == "completed"
            and queue_record.get("triage_cycle_id") == cycle
        ):
            raise ResearchAllocationError(
                f"completed rapid triage lacks a unique stage-history record: "
                f"{normalized['symbol']}"
            )
        return None
    if len(completed) != 1:
        raise ResearchAllocationError(
            f"rapid triage has duplicate completed stage-history records: {normalized['symbol']}"
        )

    history = completed[0]
    expected_history = {
        "finished_at": recorded_at.isoformat(),
        "agent": normalized["provenance"]["agent"],
        "result_path": relative_path,
        "disposition": evaluation["disposition"],
        "cycle_id": cycle,
    }
    mismatched_history = [
        field for field, expected in expected_history.items() if history.get(field) != expected
    ]
    if mismatched_history:
        raise ResearchAllocationError(
            "rapid-triage replay conflicts with completed stage history "
            f"({', '.join(mismatched_history)}): {normalized['symbol']}"
        )

    try:
        sealed = verify_sealed(package_path)
    except ValueError as exc:
        raise ResearchAllocationError(
            f"completed rapid-triage package is not validly sealed: {normalized['symbol']}"
        ) from exc
    if sealed.artifact_type != "rapid_triage_package":
        raise ResearchAllocationError(
            f"completed rapid-triage package has the wrong artifact type: {normalized['symbol']}"
        )
    if sealed.sealed_at != recorded_at:
        raise ResearchAllocationError(
            f"rapid-triage replay recorded_at conflicts with the package seal: "
            f"{normalized['symbol']}"
        )
    try:
        existing_package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError(
            f"completed rapid-triage package cannot be read: {normalized['symbol']}"
        ) from exc
    if existing_package != normalized:
        raise ResearchAllocationError(
            f"rapid-triage replay conflicts with the sealed package: {normalized['symbol']}"
        )

    binding = _resolve_cycle_cohort(base, queue, cycle)
    if normalized["symbol"] not in {item.get("symbol") for item in binding["members"]}:
        raise ResearchAllocationError(
            f"rapid-triage replay is not a member of its sealed cycle: {normalized['symbol']}"
        )
    binding["evidence_prefix"] = (
        "triage_cohort_sha256"
        if binding["type"] == "cohort"
        else "allocation_sha256"
    )
    coverage_advanced = _rapid_triage_coverage_has_verified_successor(
        base,
        queue_record,
        cycle=cycle,
        symbol=str(normalized["symbol"]),
    )
    if not coverage_advanced:
        expected_queue = {
            "triage_cycle_id": cycle,
            "triage_disposition": evaluation["disposition"],
            "triage_review_mode": normalized["review_mode"],
            "revisit_triggers": normalized["revisit_triggers"],
        }
        mismatched_queue = [
            field
            for field, expected in expected_queue.items()
            if queue_record.get(field) != expected
        ]
        if mismatched_queue:
            raise ResearchAllocationError(
                "rapid-triage queue materialization is inconsistent "
                f"({', '.join(mismatched_queue)}): {normalized['symbol']}"
            )

        expected_screening = {
            "triage_cycle_id": cycle,
            "triage_result_path": relative_path,
            "triage_recorded_at": recorded_at.isoformat(),
        }
        mismatched_screening = [
            field
            for field, expected in expected_screening.items()
            if screening_record.get(field) != expected
        ]
        evidence = screening_record.get("evidence")
        expected_evidence = {
            f"rapid_triage:{relative_path}",
            f"rapid_triage_sha256:{sealed.sha256}",
            f"{binding['evidence_prefix']}:{binding['sha256']}",
            f"triage_reason_codes:{','.join(normalized['reason_codes'])}",
        }
        if not isinstance(evidence, list) or not expected_evidence.issubset(set(evidence)):
            mismatched_screening.append("evidence")
        if mismatched_screening:
            raise ResearchAllocationError(
                "rapid-triage screening materialization is inconsistent "
                f"({', '.join(mismatched_screening)}): {normalized['symbol']}"
            )

    repository_root = base.parent.parent

    timeline_result = publish_rapid_triage_to_company_timeline(
        repository_root=repository_root,
        package_path=package_path,
        published_at=recorded_at,
        review_mode=str(normalized["review_mode"]),
    )
    company_report_path = timeline_result.get("company_report_path")
    if (
        timeline_result.get("idempotent") is not True
        or not isinstance(company_report_path, str)
        or timeline_result.get("source_package_sha256") != sealed.sha256
    ):
        raise ResearchAllocationError(
            f"rapid-triage company timeline replay was not idempotent: {normalized['symbol']}"
        )
    if (
        not coverage_advanced
        and queue_record.get("company_timeline_report_path") != company_report_path
    ):
        raise ResearchAllocationError(
            f"rapid-triage queue and company timeline paths disagree: {normalized['symbol']}"
        )
    return {
        "schema_version": 1,
        "symbol": normalized["symbol"],
        "disposition": evaluation["disposition"],
        "triage_path": relative_path,
        "triage_sha256": sealed.sha256,
        "company_timeline_report_path": company_report_path,
        "awaiting_cohort_comparison": (
            evaluation["disposition"] == "triage_candidate"
            and not coverage_advanced
            and not isinstance(queue_record.get("triage_selection_path"), str)
        ),
        "idempotent": True,
        "portfolio_action": None,
    }


def evaluate_rapid_triage(package: Mapping[str, Any]) -> dict[str, Any]:
    """Derive a stop/candidate disposition from one Agent's explicit findings."""

    survival = package["survival_status"]
    governance = package["governance_status"]
    legibility = package["business_legibility"]
    valuation = package["valuation_signal"]
    research_value = package["research_value"]
    if survival == "fail" or governance == "uninvestable":
        disposition = "conditional_stop"
    elif legibility == "opaque":
        disposition = "reassign_or_stop"
    elif valuation == "unattractive":
        disposition = "price_watch"
    elif research_value == "low":
        disposition = "catalog"
    else:
        disposition = "triage_candidate"
    if disposition != "triage_candidate" and not package["revisit_triggers"]:
        raise ResearchAllocationError(f"{disposition} rapid triage requires a revisit trigger")

    return {
        "schema_version": 1,
        "symbol": package["symbol"],
        "disposition": disposition,
        "portfolio_action": None,
    }


def build_rapid_triage_comparison_packet(
    *, root: str | Path, cycle_id: str, created_at: dt.datetime
) -> dict[str, Any]:
    """Seal a score-free packet for an independent cross-company Agent."""

    _aware(created_at, "created_at")
    cycle = _cycle(cycle_id)
    base = Path(root)
    repository_root = base.parent.parent
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    binding = _resolve_cycle_cohort(base, queue, cycle)
    quality_gate = _require_cycle_quality_gate(base=base, cycle=cycle, binding=binding)
    comparison_path = base / "triage" / cycle / "comparison.json"
    relative = comparison_path.relative_to(repository_root).as_posix()
    if comparison_path.exists():
        sealed = verify_sealed(comparison_path)
        payload = json.loads(comparison_path.read_text(encoding="utf-8"))
        if payload.get("cycle_id") != cycle or payload.get("binding_sha256") != binding["sha256"]:
            raise ResearchAllocationError(
                f"sealed comparison packet conflicts with cycle binding: {cycle}"
            )
        if payload.get("quality_audit") != quality_gate:
            raise ResearchAllocationError(
                f"sealed comparison quality binding conflicts with cycle: {cycle}"
            )
        return {
            "schema_version": 1,
            "cycle_id": cycle,
            "cohort_count": payload["cohort_count"],
            "eligible_count": payload["eligible_count"],
            "comparison_path": relative,
            "comparison_sha256": sealed.sha256,
            "idempotent": True,
            "portfolio_action": None,
        }

    allow_unscoped_history = _allow_unscoped_history(binding)
    packages = _completed_cohort_packages(
        binding["members"],
        cycle=cycle,
        repository_root=repository_root,
        allow_unscoped_history=allow_unscoped_history,
        package_overrides={
            row["symbol"]: row
            for row in (quality_gate or {}).get("resolved_packages", [])
        },
    )
    rows: list[dict[str, Any]] = []
    for ordinal, (queued, package, sealed) in enumerate(packages, 1):
        disposition = evaluate_rapid_triage(package)["disposition"]
        rows.append(
            {
                "ordinal": ordinal,
                "symbol": queued["symbol"],
                "name": queued["name"],
                "triage_disposition": disposition,
                "eligible_for_quick_profile": disposition == "triage_candidate",
                "review_mode": package.get("review_mode"),
                "prior_research_path": package.get("prior_research_path"),
                "trigger_context": package.get("trigger_context"),
                "business_summary": package.get("business_summary"),
                "change_summary": package.get("change_summary"),
                "normalized_earnings_view": package.get("normalized_earnings_view"),
                "expectations_view": package.get("expectations_view"),
                "counterevidence": package.get("counterevidence") or [],
                "decisive_question": package.get("decisive_question"),
                "reason_codes": package.get("reason_codes") or [],
                "revisit_triggers": package.get("revisit_triggers") or [],
                # The quality gate may replace the cohort package with a sealed
                # correction package.  Bind the comparison row to the artifact
                # that was actually verified, not the superseded history path.
                "triage_path": sealed.path.relative_to(repository_root).as_posix(),
                "triage_sha256": sealed.sha256,
                "research_agent": (package.get("provenance") or {}).get("agent"),
            }
        )
    payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "binding_type": binding["type"],
        "binding_path": binding["path"],
        "binding_sha256": binding["sha256"],
        "created_at": created_at.isoformat(),
        "cohort_count": len(rows),
        "eligible_count": sum(row["eligible_for_quick_profile"] for row in rows),
        "principle": (
            "Every company was reviewed before allocation. The packet is in frozen "
            "cohort order and contains no programmatic investment score or ranking."
        ),
        "rows": rows,
        "portfolio_action": None,
    }
    if quality_gate is not None:
        payload["quality_audit"] = quality_gate
    sealed = seal_json(
        comparison_path,
        payload,
        artifact_type="rapid_triage_comparison_packet",
        sealed_at=created_at,
    )
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "cohort_count": len(rows),
        "eligible_count": payload["eligible_count"],
        "comparison_path": relative,
        "comparison_sha256": sealed.sha256,
        "idempotent": False,
        "portfolio_action": None,
    }


@serialized_coverage_write
def finalize_rapid_triage_cycle(
    *,
    root: str | Path,
    cycle_id: str,
    policy: Mapping[str, Any],
    decisions: Mapping[str, Any],
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    """Apply an independent Agent's explicit decisions to a complete cohort."""

    _aware(finalized_at, "finalized_at")
    cycle = _cycle(cycle_id)
    base = Path(root)
    repository_root = base.parent.parent
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    binding = _resolve_cycle_cohort(base, queue, cycle)
    quality_gate = _require_cycle_quality_gate(base=base, cycle=cycle, binding=binding)
    _completed_cohort_packages(
        binding["members"],
        cycle=cycle,
        repository_root=repository_root,
        allow_unscoped_history=_allow_unscoped_history(binding),
    )
    comparison_path = base / "triage" / cycle / "comparison.json"
    if not comparison_path.exists():
        raise ResearchAllocationError(
            "rapid-triage comparison packet is missing; run triage-compare first"
        )
    sealed_comparison = verify_sealed(comparison_path)
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if comparison.get("cycle_id") != cycle or comparison.get("binding_sha256") != binding["sha256"]:
        raise ResearchAllocationError("comparison packet does not match cohort binding")
    if comparison.get("quality_audit") != quality_gate:
        raise ResearchAllocationError("comparison packet quality audit binding is invalid")
    comparison_rows = comparison.get("rows", [])
    if not isinstance(comparison_rows, list) or not all(
        isinstance(row, Mapping) for row in comparison_rows
    ):
        raise ResearchAllocationError("comparison packet rows are invalid")
    eligible_rows = [
        row for row in comparison_rows if row.get("eligible_for_quick_profile") is True
    ]
    normalized_decision = _normalize_decision_package(
        decisions,
        cycle=cycle,
        comparison_sha256=sealed_comparison.sha256,
        comparison_rows=comparison_rows,
        finalized_at=finalized_at,
    )
    if _datetime(
        normalized_decision["provenance"]["generated_at"],
        "decision.provenance.generated_at",
    ) < _datetime(comparison.get("created_at"), "comparison.created_at"):
        raise ResearchAllocationError("Agent decisions cannot predate the sealed comparison packet")
    research_agents = {
        row.get("research_agent")
        for row in comparison.get("rows", [])
        if isinstance(row.get("research_agent"), str)
    }
    if normalized_decision["provenance"]["agent"] in research_agents:
        raise ResearchAllocationError(
            "cross-company allocation Agent must be independent of company triage Agents"
        )
    if quality_gate is not None and normalized_decision["provenance"]["agent"] in set(
        quality_gate["reviewer_agents"]
    ):
        raise ResearchAllocationError(
            "cross-company allocation Agent must differ from quality-audit reviewers"
        )

    capacity = _policy_positive_int(policy, "quick_profile_capacity_per_cycle")
    quick_budget = _policy_budget(policy, "quick_profile")
    selected_symbols = [
        item["symbol"]
        for item in normalized_decision["decisions"]
        if item["decision"] == "select_quick_profile"
    ]
    if len(selected_symbols) > capacity:
        raise ResearchAllocationError(
            f"Agent decisions exceed quick-profile capacity: {len(selected_symbols)} > {capacity}"
        )
    risk_cluster_cap = _policy_stage_cap(
        policy,
        mapping_field="risk_cluster_caps",
        stage="quick_profile",
    )
    if len(selected_symbols) > risk_cluster_cap:
        raise ResearchAllocationError(
            "Agent decisions exceed the conservative unclassified risk-cluster cap: "
            f"{len(selected_symbols)} > {risk_cluster_cap}; establish auditable "
            "economic-risk clusters before using the remaining quick-profile capacity"
        )
    selected_set = set(selected_symbols)
    decisions_by_symbol = {item["symbol"]: item for item in normalized_decision["decisions"]}
    decision_rows = [
        {
            "ordinal": row["ordinal"],
            "symbol": row["symbol"],
            "name": row["name"],
            "selected_for_quick_profile": row["symbol"] in selected_set,
            "selection_reason": decisions_by_symbol[row["symbol"]]["reason"],
            "decisive_question": decisions_by_symbol[row["symbol"]]["decisive_question"],
            "counterevidence_considered": decisions_by_symbol[row["symbol"]][
                "counterevidence_considered"
            ],
        }
        for row in comparison_rows
    ]
    selection_path = base / "triage" / cycle / "selection.json"
    relative_selection = selection_path.relative_to(repository_root).as_posix()
    selection_payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "binding_type": binding["type"],
        "binding_path": binding["path"],
        "binding_sha256": binding["sha256"],
        "comparison_path": comparison_path.relative_to(repository_root).as_posix(),
        "comparison_sha256": sealed_comparison.sha256,
        "finalized_at": finalized_at.isoformat(),
        "cohort_count": len(binding["members"]),
        "eligible_count": len(eligible_rows),
        "reviewed_count": len(decision_rows),
        "quick_profile_capacity": capacity,
        "quick_profile_effort_budget_hours": quick_budget,
        "quick_profile_risk_cluster_cap": risk_cluster_cap,
        "risk_cluster_mode": "conservative_unclassified",
        "selected_count": len(selected_symbols),
        "principle": _policy_text(policy, "comparison_principle"),
        "agent_decision": normalized_decision,
        "decisions": decision_rows,
        # Retained as a compatibility view for the downstream profile workflow.
        # Its order is the frozen cohort order, not an investment ranking.
        "ranking": decision_rows,
        "portfolio_action": None,
    }
    if quality_gate is not None:
        selection_payload["quality_audit"] = quality_gate
    selection_existed = selection_path.exists()
    legacy_policy_unbound = False
    if selection_existed:
        sealed_selection = verify_sealed(selection_path)
        if sealed_selection.artifact_type != "rapid_triage_cross_company_selection":
            raise ResearchAllocationError(
                f"sealed rapid-triage selection has the wrong artifact type: {cycle}"
            )
        existing = json.loads(selection_path.read_text(encoding="utf-8"))
        expected_replay = {
            key: value for key, value in selection_payload.items() if key != "finalized_at"
        }
        actual_replay = {key: value for key, value in existing.items() if key != "finalized_at"}
        legacy_policy_unbound = "quick_profile_effort_budget_hours" not in actual_replay
        for legacy_field in (
            "quick_profile_effort_budget_hours",
            "quick_profile_risk_cluster_cap",
            "risk_cluster_mode",
        ):
            if legacy_field not in actual_replay:
                expected_replay.pop(legacy_field)
        if actual_replay != expected_replay:
            raise ResearchAllocationError(
                f"sealed rapid-triage selection conflicts with Agent decisions: {cycle}"
            )
        materialization_payload = existing
    else:
        sealed_selection = seal_json(
            selection_path,
            selection_payload,
            artifact_type="rapid_triage_cross_company_selection",
            sealed_at=finalized_at,
        )
        materialization_payload = selection_payload

    updated_screening, updated_queue, screening_changed, queue_changed = (
        _materialize_rapid_triage_selection(
            screening=screening,
            queue=queue,
            cycle=cycle,
            decision_rows=materialization_payload["decisions"],
            decisions_by_symbol=decisions_by_symbol,
            comparison_path=materialization_payload["comparison_path"],
            comparison_sha256=sealed_comparison.sha256,
            selection_path=relative_selection,
            selection_sha256=sealed_selection.sha256,
            quick_budget=quick_budget,
            resolved_cycles_by_symbol={
                row["symbol"]: row["cycle_id"]
                for row in (quality_gate or {}).get("resolved_packages", [])
            },
        )
    )
    if selection_existed and legacy_policy_unbound and queue_changed:
        raise ResearchAllocationError(
            "sealed rapid-triage selection predates recoverable policy binding; "
            f"refusing to guess queue budget: {cycle}"
        )
    if screening_changed:
        write_jsonl(screening_path, updated_screening)
    if queue_changed:
        write_jsonl(queue_path, updated_queue)
    return _selection_result(
        materialization_payload,
        selection_path=relative_selection,
        selection_sha256=sealed_selection.sha256,
        idempotent=selection_existed,
    )


def rapid_triage_cycle_status(*, root: str | Path, cycle_id: str) -> dict[str, Any]:
    cycle = _cycle(cycle_id)
    base = Path(root)
    repository_root = base.parent.parent
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    binding = _resolve_cycle_cohort(base, queue, cycle)
    allow_unscoped_history = _allow_unscoped_history(binding)
    completed = [
        item
        for item in binding["members"]
        if _rapid_triage_completed(
            item,
            cycle,
            allow_unscoped_history=allow_unscoped_history,
        )
    ]
    invalid: list[dict[str, str]] = []
    for item in completed:
        path = _rapid_triage_result_path(
            item,
            cycle,
            allow_unscoped_history=allow_unscoped_history,
        )
        if not isinstance(path, str):
            invalid.append({"symbol": item["symbol"], "error": "result_path_missing"})
            continue
        try:
            verify_sealed(repository_root / path)
        except ValueError as exc:
            invalid.append({"symbol": item["symbol"], "error": str(exc)})
    disposition_counts: dict[str, int] = {}
    for item in completed:
        disposition = str(item.get("triage_disposition"))
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1

    comparison_valid = _verify_optional_cycle_artifact(
        base / "triage" / cycle / "comparison.json",
        label="*comparison*",
        invalid=invalid,
    )
    selection_valid = _verify_optional_cycle_artifact(
        base / "triage" / cycle / "selection.json",
        label="*selection*",
        invalid=invalid,
    )
    audit_status = "not_configured"
    quality_status = _cycle_quality_status_view(base=base, cycle=cycle, binding=binding)
    if selection_valid:
        selection_payload = json.loads(
            (base / "triage" / cycle / "selection.json").read_text(encoding="utf-8")
        )
        decision_rows = selection_payload.get("decisions")
        reviewed_symbols = (
            {
                row.get("symbol")
                for row in decision_rows
                if isinstance(row, Mapping) and isinstance(row.get("symbol"), str)
            }
            if isinstance(decision_rows, list)
            else set()
        )
        cohort_symbols = {item["symbol"] for item in binding["members"]}
        if (
            selection_payload.get("reviewed_count") == len(binding["members"])
            and isinstance(decision_rows, list)
            and len(decision_rows) == len(binding["members"])
            and reviewed_symbols == cohort_symbols
        ):
            audit_status = "completed_full_cross_company_review"
        else:
            audit_status = "incomplete_cross_company_review"
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "binding_type": binding["type"],
        "cohort_path": binding["path"] if binding["type"] == "cohort" else None,
        "cohort_sha256": binding["sha256"] if binding["type"] == "cohort" else None,
        "allocation_sha256": (
            binding["sha256"] if binding["type"] == "legacy_allocation" else None
        ),
        "cohort_count": len(binding["members"]),
        "recorded_count": len(completed),
        "remaining_count": len(binding["members"]) - len(completed),
        "by_disposition": dict(sorted(disposition_counts.items())),
        "comparison_ready": comparison_valid,
        "selection_finalized": selection_valid,
        "audit_status": audit_status,
        "quality_audit_status": quality_status,
        "invalid_artifact_count": len(invalid),
        "invalid_artifacts": invalid,
        "portfolio_action": None,
    }


def _cycle_quality_status_view(
    *, base: Path, cycle: str, binding: Mapping[str, Any]
) -> str:
    if binding.get("type") != "cohort":
        return "legacy_not_bound"
    cohort, _, _ = load_rapid_triage_cohort(root=base, cycle_id=cycle)
    schema_version = cohort.get("schema_version")
    if schema_version == 1:
        return "legacy_not_bound"
    if schema_version == 2:
        return "missing_production_quality_contract"
    try:
        from .quality_workflow import cycle_quality_gate_status

        return str(cycle_quality_gate_status(root=base, cycle_id=cycle)["status"])
    except ValueError:
        return "not_prepared"


def _require_cycle_quality_gate(
    *, base: Path, cycle: str, binding: Mapping[str, Any]
) -> dict[str, Any] | None:
    if binding.get("type") != "cohort":
        return None
    cohort, cohort_sha, _ = load_rapid_triage_cohort(root=base, cycle_id=cycle)
    schema_version = cohort.get("schema_version")
    if schema_version == 1:
        return None
    if schema_version == 2:
        raise ResearchAllocationError(
            "schema-v2 parent-scope cohort is legacy and cannot prove new Goal production; "
            "freeze a schema-v3 cohort bound to the passed scope identity audit"
        )
    from .quality_workflow import QualityWorkflowError, cycle_quality_gate_status

    try:
        status = cycle_quality_gate_status(root=base, cycle_id=cycle)
    except QualityWorkflowError as exc:
        raise ResearchAllocationError(
            f"triage quality audit is missing or invalid: {cycle}: {exc}"
        ) from exc
    if status.get("status") != "passed":
        raise ResearchAllocationError(
            f"triage quality audit has not passed: {cycle}: {status.get('status')}"
        )
    if status.get("source_sha256") != cohort_sha:
        raise ResearchAllocationError("triage quality audit does not bind the cohort")
    repository_root = base.parent.parent.resolve()
    canonical = status["canonical_paths"]
    result_path = Path(status["gate_result_path"]).resolve()
    binding_path = Path(canonical["binding"]).resolve()
    snapshot_path = Path(canonical["policy_snapshot"]).resolve()
    try:
        result_seal = verify_sealed(result_path)
        binding_seal = verify_sealed(binding_path)
        snapshot_seal = verify_sealed(snapshot_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError("triage quality audit result is invalid") from exc
    if result_seal.sha256 != status.get("gate_result_sha256"):
        raise ResearchAllocationError("triage quality gate result sha256 is invalid")
    return {
        "binding_path": binding_path.relative_to(repository_root).as_posix(),
        "binding_sha256": binding_seal.sha256,
        "policy_snapshot_path": snapshot_path.relative_to(repository_root).as_posix(),
        "policy_snapshot_sha256": snapshot_seal.sha256,
        "result_path": result_path.relative_to(repository_root).as_posix(),
        "result_sha256": result_seal.sha256,
        "quality_results": status["quality_results"],
        "reviewer_agents": status["reviewer_agents"],
        "resolved_packages": status["resolved_packages"],
        "status": "passed",
    }


def _normalize_package(package: Mapping[str, Any], *, recorded_at: dt.datetime) -> dict[str, Any]:
    if not isinstance(package, Mapping) or set(package) not in {
        frozenset(PACKAGE_KEYS),
        frozenset(PACKAGE_KEYS | OPTIONAL_PACKAGE_KEYS),
    }:
        raise ResearchAllocationError("rapid-triage package fields do not match contract")
    if package.get("schema_version") != 2:
        raise ResearchAllocationError("rapid-triage schema_version must be 2")
    cycle = _cycle(package.get("cycle_id"))
    symbol = _symbol(package.get("symbol"))
    as_of = _date(package.get("as_of"), "as_of")
    cutoff = _datetime(package.get("information_cutoff"), "information_cutoff")
    price_as_of = _datetime(package.get("price_as_of"), "price_as_of")
    if as_of > recorded_at.date() or cutoff > recorded_at or price_as_of > recorded_at:
        raise ResearchAllocationError("rapid-triage timestamps cannot be in the future")
    if recorded_at - price_as_of > dt.timedelta(days=7):
        raise ResearchAllocationError("rapid-triage price is older than seven days")
    if price_as_of > cutoff:
        raise ResearchAllocationError("price_as_of cannot be after information_cutoff")
    current_price = _number(package.get("current_price"), "current_price")
    if current_price <= 0:
        raise ResearchAllocationError("current_price must be positive")

    sources_raw = package.get("sources")
    if not isinstance(sources_raw, list) or len(sources_raw) < 2:
        raise ResearchAllocationError("rapid triage requires at least two sources")
    sources = [_source(item, recorded_at=recorded_at) for item in sources_raw]
    source_ids = [item["source_id"] for item in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ResearchAllocationError("rapid-triage source IDs must be unique")
    if not any(item["tier"] == "S1" for item in sources):
        raise ResearchAllocationError("rapid triage requires at least one S1 source")
    price_source_id = _text(package.get("price_source_id"), "price_source_id")
    if price_source_id not in source_ids:
        raise ResearchAllocationError("price_source_id does not reference a source")
    price_source = next(item for item in sources if item["source_id"] == price_source_id)
    if "current_price" not in price_source["supports"]:
        raise ResearchAllocationError(
            "price_source_id must reference a source supporting current_price"
        )

    provenance_raw = package.get("provenance")
    if not isinstance(provenance_raw, Mapping) or set(provenance_raw) != PROVENANCE_KEYS:
        raise ResearchAllocationError("rapid-triage provenance fields do not match contract")
    generated_at = _datetime(provenance_raw.get("generated_at"), "generated_at")
    if generated_at < cutoff or generated_at > recorded_at:
        raise ResearchAllocationError("rapid-triage generated_at is invalid")
    tools = _text_array(provenance_raw.get("tools"), "tools", allow_empty=False)

    triggers_raw = package.get("revisit_triggers")
    if not isinstance(triggers_raw, list) or not triggers_raw:
        raise ResearchAllocationError(
            "v2 rapid triage requires at least one executable revisit trigger"
        )
    triggers = []
    for raw in triggers_raw:
        if not isinstance(raw, Mapping) or set(raw) != TRIGGER_KEYS:
            raise ResearchAllocationError(
                "rapid-triage revisit trigger fields do not match contract"
            )
        triggers.append(_trigger(raw))
    trigger_ids = [item["trigger_id"] for item in triggers]
    if len(trigger_ids) != len(set(trigger_ids)):
        raise ResearchAllocationError("revisit trigger IDs must be unique")
    for trigger in triggers:
        if (
            trigger["type"] == "date"
            and _date(trigger["condition"]["date"], "trigger.condition.date") <= cutoff.date()
        ):
            raise ResearchAllocationError("date revisit trigger must be after information_cutoff")
        if (
            trigger["type"] == "ttl"
            and "due_at" in trigger["condition"]
            and _datetime(trigger["condition"]["due_at"], "trigger.condition.due_at") <= cutoff
        ):
            raise ResearchAllocationError("ttl revisit trigger must be after information_cutoff")
    prior_research_path = package.get("prior_research_path")
    if prior_research_path is not None:
        prior_research_path = _repository_relative_path(prior_research_path, "prior_research_path")
    raw_handled_hit_ids = package.get("handled_hit_ids", [])
    if not isinstance(raw_handled_hit_ids, list):
        raise ResearchAllocationError("handled_hit_ids must be an array")
    handled_hit_ids = [_sha256(value, "handled_hit_ids") for value in raw_handled_hit_ids]
    if len(handled_hit_ids) != len(set(handled_hit_ids)):
        raise ResearchAllocationError("handled_hit_ids must be unique")
    result = {
        "schema_version": 2,
        "cycle_id": cycle,
        "symbol": symbol,
        "company_name": _text(package.get("company_name"), "company_name"),
        "as_of": as_of.isoformat(),
        "information_cutoff": cutoff.isoformat(),
        "price_as_of": price_as_of.isoformat(),
        "price_source_id": price_source_id,
        "current_price": current_price,
        "review_mode": _enum(package.get("review_mode"), REVIEW_MODES, "review_mode"),
        "prior_research_path": prior_research_path,
        "trigger_context": _text(package.get("trigger_context"), "trigger_context"),
        "handled_hit_ids": handled_hit_ids,
        "business_summary": _text(package.get("business_summary"), "business_summary"),
        "change_summary": _text(package.get("change_summary"), "change_summary"),
        "normalized_earnings_view": _text(
            package.get("normalized_earnings_view"), "normalized_earnings_view"
        ),
        "expectations_view": _text(package.get("expectations_view"), "expectations_view"),
        "counterevidence": _text_array(
            package.get("counterevidence"), "counterevidence", allow_empty=False
        ),
        "business_legibility": _enum(
            package.get("business_legibility"),
            {"clear", "uncertain", "opaque"},
            "business_legibility",
        ),
        "survival_status": _enum(
            package.get("survival_status"),
            {"pass", "concern", "fail"},
            "survival_status",
        ),
        "governance_status": _enum(
            package.get("governance_status"),
            {"acceptable", "concern", "uninvestable"},
            "governance_status",
        ),
        "earnings_legibility": _enum(
            package.get("earnings_legibility"),
            {"plausible", "uncertain", "unavailable"},
            "earnings_legibility",
        ),
        "valuation_signal": _enum(
            package.get("valuation_signal"),
            {"attractive", "possible", "unattractive", "unknown"},
            "valuation_signal",
        ),
        "research_value": _enum(
            package.get("research_value"),
            {"high", "medium", "low"},
            "research_value",
        ),
        "decisive_question": _text(package.get("decisive_question"), "decisive_question"),
        "reason_codes": _text_array(package.get("reason_codes"), "reason_codes", allow_empty=False),
        "revisit_triggers": triggers,
        "sources": sources,
        "provenance": {
            "agent": _text(provenance_raw.get("agent"), "provenance.agent"),
            "model": _text(provenance_raw.get("model"), "provenance.model"),
            "tools": tools,
            "generated_at": generated_at.isoformat(),
        },
    }
    evaluate_rapid_triage(result)
    return result


def validate_rapid_triage_package(
    package: Mapping[str, Any], *, recorded_at: dt.datetime
) -> dict[str, Any]:
    """Validate and normalize one schema-v2 rapid-triage package."""

    return _normalize_package(package, recorded_at=recorded_at)


def _has_cohort_binding(record: Mapping[str, Any]) -> bool:
    return (
        isinstance(record.get("cohort_sha256"), str)
        and len(record["cohort_sha256"]) == 64
        and isinstance(record.get("cohort_path"), str)
        and bool(record["cohort_path"])
        and isinstance(record.get("triage_cycle_id"), str)
    )


def _claim_order(item: Mapping[str, Any]) -> tuple[int, int, str]:
    ordinal = item.get("cohort_ordinal")
    if isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal > 0:
        return (0, ordinal, str(item.get("symbol")))
    return (1, int(item.get("priority", 5)), str(item.get("symbol")))


def _verify_queue_cohort_binding(
    base: Path,
    record: Mapping[str, Any],
    *,
    expected_cycle: str | None,
) -> dict[str, Any]:
    cycle = _cycle(record.get("triage_cycle_id"))
    if expected_cycle is not None and cycle != expected_cycle:
        raise ResearchAllocationError(
            f"rapid-triage task is bound to another cycle: {record.get('symbol')}"
        )
    payload, cohort_sha, cohort_path = load_rapid_triage_cohort(root=base, cycle_id=cycle)
    if record.get("cohort_sha256") != cohort_sha or record.get("cohort_path") != cohort_path:
        raise ResearchAllocationError(
            f"rapid-triage queue binding does not match sealed cohort: {record.get('symbol')}"
        )
    members = {item["symbol"] for item in payload["members"]}
    if record.get("symbol") not in members:
        raise ResearchAllocationError(
            f"rapid-triage symbol is not a sealed cohort member: {record.get('symbol')}"
        )
    return {
        "type": "cohort",
        "path": cohort_path,
        "sha256": cohort_sha,
        "payload": payload,
    }


def _rapid_triage_coverage_has_verified_successor(
    base: Path,
    record: Mapping[str, Any],
    *,
    cycle: str,
    symbol: str,
) -> bool:
    """Distinguish legitimate later work from mutable coverage drift on replay."""

    current_cycle = record.get("triage_cycle_id")
    if (
        current_cycle == cycle
        and record.get("task_type") == "rapid_triage"
        and record.get("status") == "completed"
    ):
        return False

    if isinstance(current_cycle, str) and current_cycle != cycle:
        if not _has_cohort_binding(record):
            raise ResearchAllocationError(
                f"later rapid-triage coverage lacks a sealed cohort binding: {symbol}"
            )
        _verify_queue_cohort_binding(base, record, expected_cycle=current_cycle)
        return True

    successor_task_types = {
        "quick_profile",
        "targeted_followup",
        "scoped_research",
        "deep_research",
        "monitoring_update",
        "followup_review",
    }
    if current_cycle == cycle and record.get("task_type") in successor_task_types:
        selection_path_text = record.get("triage_selection_path")
        selection_sha = record.get("triage_selection_sha256")
        if not isinstance(selection_path_text, str) or not isinstance(selection_sha, str):
            raise ResearchAllocationError(
                f"rapid-triage successor lacks a sealed selection binding: {symbol}"
            )
        repository_root = base.parent.parent.resolve()
        selection_path = (repository_root / selection_path_text).resolve()
        try:
            selection_path.relative_to(repository_root)
            sealed = verify_sealed(selection_path)
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ResearchAllocationError(
                f"rapid-triage successor selection is invalid: {symbol}"
            ) from exc
        if not isinstance(selection, Mapping):
            raise ResearchAllocationError(
                f"rapid-triage successor selection is not an object: {symbol}"
            )
        binding_type = selection.get("binding_type")
        if binding_type == "cohort":
            expected_binding_sha = record.get("cohort_sha256")
            expected_binding_path = record.get("cohort_path")
        elif binding_type == "legacy_allocation":
            expected_binding_sha = record.get("allocation_sha256")
            expected_binding_path = None
        else:
            raise ResearchAllocationError(
                f"rapid-triage successor selection has an unknown binding: {symbol}"
            )
        rows = selection.get("decisions")
        selected = [
            item
            for item in rows or []
            if isinstance(item, Mapping)
            and item.get("symbol") == symbol
            and item.get("selected_for_quick_profile") is True
        ]
        if (
            sealed.artifact_type != "rapid_triage_cross_company_selection"
            or sealed.sha256 != selection_sha
            or selection.get("cycle_id") != cycle
            or selection.get("binding_sha256") != expected_binding_sha
            or selection.get("binding_path") != expected_binding_path
            or len(selected) != 1
            or record.get("triage_allocation_decision") != "select_quick_profile"
        ):
            raise ResearchAllocationError(
                f"rapid-triage successor selection does not match coverage: {symbol}"
            )
        return True

    raise ResearchAllocationError(
        f"rapid-triage replay found unexpected coverage state: {symbol} "
        f"({current_cycle}, {record.get('task_type')}, {record.get('status')})"
    )


def _resolve_triage_binding(
    base: Path,
    queue: list[dict[str, Any]],
    record: Mapping[str, Any],
    *,
    expected_cycle: str,
) -> dict[str, Any]:
    if _has_cohort_binding(record):
        binding = _verify_queue_cohort_binding(base, record, expected_cycle=expected_cycle)
        binding["evidence_prefix"] = "triage_cohort_sha256"
        return binding

    allocation_sha = record.get("allocation_sha256")
    if not isinstance(allocation_sha, str) or len(allocation_sha) != 64:
        raise ResearchAllocationError(
            f"rapid triage lacks a sealed cohort or legacy allocation binding: "
            f"{record.get('symbol')}"
        )
    bound_cycles = {
        item.get("triage_cycle_id")
        for item in queue
        if item.get("allocation_sha256") == allocation_sha
        and item.get("triage_cycle_id") is not None
    }
    if bound_cycles and bound_cycles != {expected_cycle}:
        raise ResearchAllocationError(
            f"legacy allocation is already bound to another triage cycle: {sorted(bound_cycles)}"
        )
    return {
        "type": "legacy_allocation",
        "path": None,
        "sha256": allocation_sha,
        "evidence_prefix": "allocation_sha256",
    }


def _resolve_cycle_cohort(base: Path, queue: list[dict[str, Any]], cycle: str) -> dict[str, Any]:
    cohort_path = base / "triage" / cycle / "cohort.json"
    queue_by_symbol = {item.get("symbol"): item for item in queue}
    if cohort_path.exists():
        payload, cohort_sha, relative = load_rapid_triage_cohort(root=base, cycle_id=cycle)
        members: list[dict[str, Any]] = []
        expected_symbols = {item["symbol"] for item in payload["members"]}
        for member in payload["members"]:
            queued = queue_by_symbol.get(member["symbol"])
            if not isinstance(queued, dict):
                raise ResearchAllocationError(
                    f"sealed cohort member is absent from queue: {member['symbol']}"
                )
            if queued.get("triage_cycle_id") == cycle and queued.get("cohort_sha256") == cohort_sha:
                _verify_queue_cohort_binding(base, queued, expected_cycle=cycle)
                members.append(queued)
                continue
            historical = _historical_member_for_cycle(
                queued,
                cycle=cycle,
                cohort_path=relative,
                cohort_sha256=cohort_sha,
            )
            if historical is None:
                raise ResearchAllocationError(
                    f"sealed cohort member no longer has a verifiable queue history: "
                    f"{member['symbol']}"
                )
            members.append(historical)
        extras = {
            item.get("symbol") for item in queue if item.get("cohort_sha256") == cohort_sha
        } - expected_symbols
        if extras:
            raise ResearchAllocationError(
                f"queue contains symbols outside the sealed cohort: {sorted(extras)}"
            )
        return {
            "type": "cohort",
            "path": relative,
            "sha256": cohort_sha,
            "schema_version": payload.get("schema_version", 1),
            "members": members,
        }

    recorded = [item for item in queue if item.get("triage_cycle_id") == cycle]
    if not recorded:
        raise ResearchAllocationError(f"rapid-triage cycle is empty: {cycle}")
    allocation_shas = {
        item.get("allocation_sha256")
        for item in recorded
        if isinstance(item.get("allocation_sha256"), str)
    }
    if len(allocation_shas) != 1:
        raise ResearchAllocationError(
            "rapid-triage cycle has no cohort and spans multiple legacy allocations"
        )
    allocation_sha = next(iter(allocation_shas))
    members = [
        item
        for item in queue
        if item.get("allocation_sha256") == allocation_sha and bool(item.get("selected_by"))
    ]
    if not members:
        raise ResearchAllocationError("legacy rapid-triage allocation cohort is empty")
    members.sort(key=lambda item: str(item.get("symbol")))
    return {
        "type": "legacy_allocation",
        "path": None,
        "sha256": allocation_sha,
        "schema_version": 0,
        "members": members,
    }


def _historical_member_for_cycle(
    record: Mapping[str, Any],
    *,
    cycle: str,
    cohort_path: str,
    cohort_sha256: str,
) -> dict[str, Any] | None:
    completion = next(
        (
            item
            for item in reversed(record.get("stage_history") or [])
            if isinstance(item, Mapping)
            and item.get("stage") == "rapid_triage"
            and item.get("status") == "completed"
            and item.get("cycle_id") == cycle
            and isinstance(item.get("result_path"), str)
        ),
        None,
    )
    if completion is None:
        return None
    historical = dict(record)
    historical.update(
        {
            "task_type": "rapid_triage",
            "status": "completed",
            "triage_cycle_id": cycle,
            "cohort_path": cohort_path,
            "cohort_sha256": cohort_sha256,
            "result_path": completion["result_path"],
            "triage_disposition": completion.get("disposition"),
        }
    )
    return historical


def _allow_unscoped_history(binding: Mapping[str, Any]) -> bool:
    """Keep legacy cycle recovery without letting old results satisfy schema-v3 work."""

    return binding.get("type") == "legacy_allocation" or binding.get(
        "schema_version", 1
    ) < 3


def _rapid_triage_completed(
    record: Mapping[str, Any],
    cycle: str,
    *,
    allow_unscoped_history: bool = True,
) -> bool:
    history_completed = any(
        isinstance(item, Mapping)
        and item.get("stage") == "rapid_triage"
        and item.get("status") == "completed"
        and (
            item.get("cycle_id") == cycle
            or (allow_unscoped_history and item.get("cycle_id") is None)
        )
        and isinstance(item.get("result_path"), str)
        for item in record.get("stage_history") or []
    )
    if history_completed:
        return True
    return bool(
        record.get("triage_cycle_id") == cycle
        and isinstance(record.get("triage_disposition"), str)
        and _rapid_triage_result_path(
            record,
            cycle,
            allow_unscoped_history=allow_unscoped_history,
        )
        and record.get("task_type") == "rapid_triage"
        and record.get("status") == "completed"
    )


def _rapid_triage_result_path(
    record: Mapping[str, Any],
    cycle: str,
    *,
    allow_unscoped_history: bool = True,
) -> str | None:
    for item in reversed(record.get("stage_history") or []):
        if (
            isinstance(item, Mapping)
            and item.get("stage") == "rapid_triage"
            and item.get("status") == "completed"
            and (
                item.get("cycle_id") == cycle
                or (allow_unscoped_history and item.get("cycle_id") is None)
            )
            and isinstance(item.get("result_path"), str)
        ):
            return str(item["result_path"])
    if (
        record.get("task_type") == "rapid_triage"
        and record.get("triage_cycle_id") == cycle
        and isinstance(record.get("result_path"), str)
    ):
        return str(record["result_path"])
    return None


def _completed_cohort_packages(
    members: list[dict[str, Any]],
    *,
    cycle: str,
    repository_root: Path,
    allow_unscoped_history: bool = True,
    package_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any], Any]]:
    incomplete = [
        item["symbol"]
        for item in members
        if not _rapid_triage_completed(
            item,
            cycle,
            allow_unscoped_history=allow_unscoped_history,
        )
    ]
    if incomplete:
        raise ResearchAllocationError(
            "completion-order promotion is forbidden; rapid-triage cohort is "
            f"incomplete: {incomplete[:10]}"
        )
    result = []
    overrides = package_overrides or {}
    for item in members:
        override = overrides.get(item["symbol"])
        if override is not None:
            path = repository_root / _text(
                override.get("path"), "quality resolution package path"
            )
            sealed = verify_sealed(path)
            package = json.loads(path.read_text(encoding="utf-8"))
            if (
                sealed.sha256 != override.get("sha256")
                or package.get("cycle_id") != override.get("cycle_id")
                or package.get("symbol") != item["symbol"]
                or evaluate_rapid_triage(package)["disposition"]
                != override.get("disposition")
            ):
                raise ResearchAllocationError(
                    f"quality resolution package is invalid: {item['symbol']}"
                )
            result.append((item, package, sealed))
            continue
        result_path = _rapid_triage_result_path(
            item,
            cycle,
            allow_unscoped_history=allow_unscoped_history,
        )
        if result_path is None:
            raise ResearchAllocationError(f"rapid-triage result path is missing: {item['symbol']}")
        path = repository_root / result_path
        sealed = verify_sealed(path)
        package = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(package, dict):
            raise ResearchAllocationError(
                f"rapid-triage result must be an object: {item['symbol']}"
            )
        if package.get("cycle_id") != cycle or package.get("symbol") != item["symbol"]:
            raise ResearchAllocationError(
                f"rapid-triage result identity does not match cohort: {item['symbol']}"
            )
        result.append((item, package, sealed))
    return result


def _normalize_decision_package(
    package: Mapping[str, Any],
    *,
    cycle: str,
    comparison_sha256: str,
    comparison_rows: list[Mapping[str, Any]],
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    if not isinstance(package, Mapping) or set(package) != DECISION_PACKAGE_KEYS:
        raise ResearchAllocationError("rapid-triage Agent decision fields do not match contract")
    if package.get("schema_version") != 1:
        raise ResearchAllocationError("rapid-triage Agent decision schema_version must be 1")
    if _cycle(package.get("cycle_id")) != cycle:
        raise ResearchAllocationError("Agent decisions target the wrong triage cycle")
    if package.get("comparison_sha256") != comparison_sha256:
        raise ResearchAllocationError(
            "Agent decisions are not bound to the sealed comparison packet"
        )
    provenance_raw = package.get("provenance")
    if not isinstance(provenance_raw, Mapping) or set(provenance_raw) != PROVENANCE_KEYS:
        raise ResearchAllocationError("Agent decision provenance is invalid")
    generated_at = _datetime(provenance_raw.get("generated_at"), "decision.provenance.generated_at")
    if generated_at > finalized_at:
        raise ResearchAllocationError("Agent decisions cannot be generated in the future")

    decisions_raw = package.get("decisions")
    if not isinstance(decisions_raw, list):
        raise ResearchAllocationError("Agent decisions must be an array")
    normalized_by_symbol: dict[str, dict[str, Any]] = {}
    for raw in decisions_raw:
        if not isinstance(raw, Mapping) or set(raw) != DECISION_KEYS:
            raise ResearchAllocationError("one Agent decision does not match contract")
        symbol = _symbol(raw.get("symbol"))
        if symbol in normalized_by_symbol:
            raise ResearchAllocationError(f"duplicate Agent decision: {symbol}")
        normalized_by_symbol[symbol] = {
            "symbol": symbol,
            "decision": _enum(raw.get("decision"), DECISIONS, "decision"),
            "reason": _text(raw.get("reason"), "decision.reason"),
            "decisive_question": _text(raw.get("decisive_question"), "decision.decisive_question"),
            "counterevidence_considered": _text_array(
                raw.get("counterevidence_considered"),
                "decision.counterevidence_considered",
                allow_empty=False,
            ),
        }
    comparison_symbols = [_symbol(row.get("symbol")) for row in comparison_rows]
    if len(comparison_symbols) != len(set(comparison_symbols)):
        raise ResearchAllocationError("comparison packet rows contain duplicate symbols")
    if set(normalized_by_symbol) != set(comparison_symbols):
        missing = sorted(set(comparison_symbols) - set(normalized_by_symbol))
        extra = sorted(set(normalized_by_symbol) - set(comparison_symbols))
        raise ResearchAllocationError(
            "Agent decisions must cover every comparison row exactly once; "
            f"missing={missing}, extra={extra}"
        )
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "comparison_sha256": comparison_sha256,
        "decisions": [normalized_by_symbol[symbol] for symbol in comparison_symbols],
        "provenance": {
            "agent": _text(provenance_raw.get("agent"), "decision.provenance.agent"),
            "model": _text(provenance_raw.get("model"), "decision.provenance.model"),
            "tools": _text_array(
                provenance_raw.get("tools"),
                "decision.provenance.tools",
                allow_empty=False,
            ),
            "generated_at": generated_at.isoformat(),
        },
    }


def _materialize_rapid_triage_selection(
    *,
    screening: list[dict[str, Any]],
    queue: list[dict[str, Any]],
    cycle: str,
    decision_rows: list[Mapping[str, Any]],
    decisions_by_symbol: Mapping[str, Mapping[str, Any]],
    comparison_path: str,
    comparison_sha256: str,
    selection_path: str,
    selection_sha256: str,
    quick_budget: float,
    resolved_cycles_by_symbol: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, bool]:
    """Apply one sealed selection, repairing only absent materialization state."""

    screen_by_symbol = {item.get("symbol"): dict(item) for item in screening}
    queue_by_symbol = {item.get("symbol"): dict(item) for item in queue}
    screening_changed = False
    queue_changed = False
    expected_evidence = [
        f"triage_comparison:{comparison_path}",
        f"triage_comparison_sha256:{comparison_sha256}",
        f"triage_selection:{selection_path}",
        f"triage_selection_sha256:{selection_sha256}",
    ]
    evidence_proof = set(expected_evidence[-2:])

    for row in decision_rows:
        symbol = _symbol(row.get("symbol"))
        if symbol not in screen_by_symbol or symbol not in queue_by_symbol:
            raise ResearchAllocationError(
                f"sealed rapid-triage selection references a missing coverage row: {symbol}"
            )
        decision = decisions_by_symbol.get(symbol)
        if not isinstance(decision, Mapping):
            raise ResearchAllocationError(
                f"sealed rapid-triage selection lacks an Agent decision: {symbol}"
            )
        expected_decision = (
            "select_quick_profile" if row.get("selected_for_quick_profile") is True else "defer"
        )
        if decision.get("decision") != expected_decision:
            raise ResearchAllocationError(
                f"sealed rapid-triage selection decision is inconsistent: {symbol}"
            )

        original_queue = queue_by_symbol[symbol]
        queued = dict(original_queue)
        original_screen = screen_by_symbol[symbol]
        screen = dict(original_screen)
        queue_markers = {
            "triage_selection_path": selection_path,
            "triage_selection_sha256": selection_sha256,
            "triage_allocation_decision": expected_decision,
        }
        marker_present = False
        for field, expected in queue_markers.items():
            actual = queued.get(field)
            if actual is not None:
                marker_present = True
                if actual != expected:
                    raise ResearchAllocationError(
                        f"rapid-triage selection materialization conflicts at {field}: {symbol}"
                    )

        screen_evidence = screen.get("evidence")
        screen_evidence_set = set(screen_evidence) if isinstance(screen_evidence, list) else set()
        screen_proves_selection = evidence_proof.issubset(screen_evidence_set)
        effective_triage_cycle = resolved_cycles_by_symbol.get(symbol, cycle)
        has_completed_triage = any(
            isinstance(item, Mapping)
            and item.get("stage") == "rapid_triage"
            and item.get("status") == "completed"
            and item.get("cycle_id") == effective_triage_cycle
            for item in queued.get("stage_history") or []
        )
        moved_to_later_cycle = (
            queued.get("triage_cycle_id") != effective_triage_cycle and has_completed_triage
        )
        if moved_to_later_cycle:
            continue

        is_unmaterialized = bool(
            queued.get("triage_cycle_id") == effective_triage_cycle
            and queued.get("task_type") == "rapid_triage"
            and queued.get("status") == "completed"
            and has_completed_triage
        )
        quick_profile_advanced = bool(
            queued.get("task_type") == "quick_profile" and queued.get("status") != "pending"
        )
        completed_quick_profile = any(
            isinstance(item, Mapping)
            and item.get("stage") == "quick_profile"
            and item.get("status") == "completed"
            for item in queued.get("stage_history") or []
        )
        deeper_progress = bool(
            queued.get("task_type") not in {"rapid_triage", "quick_profile"}
            and completed_quick_profile
        )
        preserve_progress = quick_profile_advanced or deeper_progress
        initial_quick_profile = bool(
            queued.get("task_type") == "quick_profile" and queued.get("status") == "pending"
        )

        if expected_decision == "select_quick_profile":
            if preserve_progress or initial_quick_profile:
                if not marker_present and not screen_proves_selection:
                    raise ResearchAllocationError(
                        "sealed rapid-triage selection cannot be attributed to existing "
                        f"quick-profile progress: {symbol}"
                    )
                queued.update(queue_markers)
            elif is_unmaterialized:
                queued.update(
                    {
                        **queue_markers,
                        "task_type": "quick_profile",
                        "status": "pending",
                        "assigned_agent": None,
                        "started_at": None,
                        "finished_at": None,
                        "failure_reason": None,
                        "reason": decision["reason"],
                        "next_action": (
                            "Complete a formal quick profile; do not assign a position."
                        ),
                        "effort_budget_hours": quick_budget,
                        "preceding_stage": "rapid_triage",
                        "stop_conditions": [
                            "no credible path to the required return",
                            ("survival, governance, or normalized earnings cannot be established"),
                            ("the decisive uncertainty cannot be resolved with public evidence"),
                        ],
                    }
                )
            else:
                raise ResearchAllocationError(
                    f"sealed rapid-triage selection cannot safely repair queue state: {symbol}"
                )
        elif is_unmaterialized or marker_present or screen_proves_selection:
            queued.update(queue_markers)
            if is_unmaterialized:
                queued["next_action"] = "Wait for a structured revisit trigger."
        else:
            raise ResearchAllocationError(
                f"sealed rapid-triage defer decision cannot safely repair queue state: {symbol}"
            )

        if not preserve_progress:
            evidence = list(screen_evidence) if isinstance(screen_evidence, list) else []
            screen["evidence"] = list(dict.fromkeys(evidence + expected_evidence))
            if expected_decision == "select_quick_profile":
                screen.update(
                    {
                        "decision": "quick_profile",
                        "reason": decision["reason"],
                        "next_action": (
                            "Complete a formal quick profile; do not make a portfolio action."
                        ),
                    }
                )
            else:
                screen.update(
                    {
                        "decision": "catalog",
                        "reason": decision["reason"],
                        "next_action": (
                            "Wait for a structured trigger or a later research-budget cycle."
                        ),
                    }
                )

        if queued != original_queue:
            queue_by_symbol[symbol] = queued
            queue_changed = True
        if screen != original_screen:
            screen_by_symbol[symbol] = screen
            screening_changed = True

    return (
        [screen_by_symbol[item.get("symbol")] for item in screening],
        [queue_by_symbol[item.get("symbol")] for item in queue],
        screening_changed,
        queue_changed,
    )


def _selection_result(
    payload: Mapping[str, Any],
    *,
    selection_path: str,
    selection_sha256: str,
    idempotent: bool,
) -> dict[str, Any]:
    selected_symbols = [
        item["symbol"] for item in payload["ranking"] if item["selected_for_quick_profile"]
    ]
    return {
        "schema_version": 1,
        "cycle_id": payload["cycle_id"],
        "cohort_count": payload["cohort_count"],
        "eligible_count": payload["eligible_count"],
        "reviewed_count": payload.get("reviewed_count", len(payload["ranking"])),
        "selected_count": len(selected_symbols),
        "selected_symbols": selected_symbols,
        "selection_path": selection_path,
        "selection_sha256": selection_sha256,
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _verify_optional_cycle_artifact(
    path: Path, *, label: str, invalid: list[dict[str, str]]
) -> bool:
    if not path.exists():
        return False
    try:
        verify_sealed(path)
        return True
    except ValueError as exc:
        invalid.append({"symbol": label, "error": str(exc)})
        return False


def _claim_payload(record: Mapping[str, Any], *, idempotent: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "symbol": record.get("symbol"),
        "name": record.get("name"),
        "task_type": "rapid_triage",
        "assigned_agent": record.get("assigned_agent"),
        "started_at": record.get("started_at"),
        "effort_budget_hours": record.get("effort_budget_hours"),
        "cycle_id": record.get("triage_cycle_id"),
        "cohort_path": record.get("cohort_path"),
        "cohort_sha256": record.get("cohort_sha256"),
        "cohort_ordinal": record.get("cohort_ordinal"),
        "intake_reason_codes": record.get("intake_reason_codes") or [],
        "selected_by": record.get("selected_by") or [],
        "stop_conditions": record.get("stop_conditions") or [],
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _disposition_reason(disposition: str) -> str:
    return {
        "triage_candidate": "快速甄别未发现立即停止项，等待完整候选批次横向比较。",
        "price_watch": "快速甄别认为公司可能可研究，但当前价格缺乏赔率。",
        "conditional_stop": "快速甄别发现经一手来源支持的生存或治理阻断项。",
        "reassign_or_stop": "业务无法在当前能力圈内快速解释，转派或暂停。",
        "catalog": "继续购买研究信息的预期价值较低，返回动态目录。",
    }[disposition]


def _disposition_action(disposition: str) -> str:
    return {
        "triage_candidate": "等待全批次完成后统一比较，不得按完成顺序晋级。",
        "price_watch": "按明确价格、财报或事件触发器重启。",
        "conditional_stop": "仅在结构化重启条件发生时恢复。",
        "reassign_or_stop": "转派具备相应能力圈的agent；无法转派则暂停。",
        "catalog": "保留在全市场目录，由价格、财报、事件或论点变化重启。",
    }[disposition]


def _trigger(raw: Mapping[str, Any]) -> dict[str, Any]:
    trigger_id = _text(raw.get("trigger_id"), "trigger.trigger_id")
    if not SOURCE_ID_RE.fullmatch(trigger_id):
        raise ResearchAllocationError(f"invalid trigger_id: {trigger_id}")
    trigger_type = _enum(raw.get("type"), TRIGGER_TYPES, "trigger.type")
    condition = raw.get("condition")
    if not isinstance(condition, Mapping):
        raise ResearchAllocationError("trigger.condition must be an object")
    if trigger_type == "price":
        if set(condition) != {"operator", "threshold"}:
            raise ResearchAllocationError(
                "price trigger condition must contain operator and threshold"
            )
        operator = _enum(
            condition.get("operator"),
            {"price_lte", "price_gte"},
            "trigger.condition.operator",
        )
        threshold = _positive_number(condition.get("threshold"), "trigger.condition.threshold")
        normalized_condition: dict[str, Any] = {
            "operator": operator,
            "threshold": threshold,
        }
    elif trigger_type == "date":
        if set(condition) != {"date"}:
            raise ResearchAllocationError("date trigger condition must contain date")
        normalized_condition = {
            "date": _date(condition.get("date"), "trigger.condition.date").isoformat()
        }
    elif trigger_type == "ttl":
        if set(condition) == {"days"}:
            days = condition.get("days")
            if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
                raise ResearchAllocationError(
                    "ttl trigger condition.days must be a positive integer"
                )
            normalized_condition = {"days": days}
        elif set(condition) == {"due_at"}:
            normalized_condition = {
                "due_at": _datetime(condition.get("due_at"), "trigger.condition.due_at").isoformat()
            }
        else:
            raise ResearchAllocationError(
                "ttl trigger condition must contain exactly one of days or due_at"
            )
    else:
        if set(condition) != {"description"}:
            raise ResearchAllocationError(
                f"{trigger_type} trigger condition must contain description"
            )
        normalized_condition = {
            "description": _text(condition.get("description"), "trigger.condition.description")
        }
    return {
        "trigger_id": trigger_id,
        "type": trigger_type,
        "condition": normalized_condition,
        "reason": _text(raw.get("reason"), "trigger.reason"),
    }


def _repository_relative_path(value: Any, label: str) -> str:
    text = _text(value, label)
    path = Path(text)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ResearchAllocationError(f"{label} must be repository-relative")
    return path.as_posix()


def _source(raw: Any, *, recorded_at: dt.datetime) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != SOURCE_KEYS:
        raise ResearchAllocationError("rapid-triage source fields do not match contract")
    source_id = _text(raw.get("source_id"), "source_id")
    if not SOURCE_ID_RE.fullmatch(source_id):
        raise ResearchAllocationError(f"invalid source_id: {source_id}")
    accessed_at = _datetime(raw.get("accessed_at"), f"{source_id}.accessed_at")
    if accessed_at > recorded_at:
        raise ResearchAllocationError(f"source accessed_at is in the future: {source_id}")
    url = raw.get("url")
    local_path = raw.get("local_path")
    if url is not None:
        url = _text(url, f"{source_id}.url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ResearchAllocationError(f"source URL is invalid: {source_id}")
    if local_path is not None:
        local_path = _text(local_path, f"{source_id}.local_path")
    if url is None and local_path is None:
        raise ResearchAllocationError(f"source requires URL or local path: {source_id}")
    return {
        "source_id": source_id,
        "tier": _enum(raw.get("tier"), SOURCE_TIERS, f"{source_id}.tier"),
        "title": _text(raw.get("title"), f"{source_id}.title"),
        "accessed_at": accessed_at.isoformat(),
        "url": url,
        "local_path": local_path,
        "supports": _text_array(raw.get("supports"), f"{source_id}.supports", allow_empty=False),
    }


def _validate_local_sources(sources: list[dict[str, Any]], *, repository_root: Path) -> None:
    root = repository_root.resolve()
    for source in sources:
        local_path = source["local_path"]
        if local_path is None:
            continue
        candidate = Path(local_path)
        if candidate.is_absolute():
            raise ResearchAllocationError(
                f"local source paths must be repository-relative: {source['source_id']}"
            )
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ResearchAllocationError(
                f"local source path escapes repository: {source['source_id']}"
            ) from exc
        if not resolved.is_file():
            raise ResearchAllocationError(
                f"local source file does not exist: {source['source_id']}"
            )


def _validate_prior_research_path(
    prior_research_path: str | None, *, repository_root: Path
) -> None:
    if prior_research_path is None:
        return
    root = repository_root.resolve()
    candidate = (root / prior_research_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ResearchAllocationError("prior_research_path escapes repository") from exc
    if not candidate.is_file():
        raise ResearchAllocationError(f"prior research file does not exist: {prior_research_path}")


def _policy_budget(policy: Mapping[str, Any], stage: str) -> float:
    budgets = policy.get("effort_budget_hours")
    if not isinstance(budgets, Mapping):
        raise ResearchAllocationError("effort budget policy is invalid")
    return _positive_number(budgets.get(stage), f"effort_budget_hours.{stage}")


def _policy_positive_int(policy: Mapping[str, Any], field: str) -> int:
    value = policy.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResearchAllocationError(f"policy field must be positive integer: {field}")
    return value


def _policy_stage_cap(
    policy: Mapping[str, Any], *, mapping_field: str, stage: str
) -> int:
    values = policy.get(mapping_field)
    if not isinstance(values, Mapping):
        raise ResearchAllocationError(f"policy mapping is invalid: {mapping_field}")
    value = values.get(stage)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResearchAllocationError(
            f"policy field must be positive integer: {mapping_field}.{stage}"
        )
    return value


def _policy_text(policy: Mapping[str, Any], field: str) -> str:
    return _text(policy.get(field), field)


def _one(records: list[dict[str, Any]], symbol: str, label: str) -> dict[str, Any]:
    matches = [item for item in records if item.get("symbol") == symbol]
    if len(matches) != 1:
        raise ResearchAllocationError(f"expected exactly one {label}: {symbol}")
    return matches[0]


def _cycle(value: Any) -> str:
    result = _text(value, "cycle_id")
    if not CYCLE_RE.fullmatch(result):
        raise ResearchAllocationError("cycle_id is invalid")
    return result


def _symbol(value: Any) -> str:
    result = _text(value, "symbol")
    if not SYMBOL_RE.fullmatch(result):
        raise ResearchAllocationError("symbol must match CN:000000")
    return result


def _sha256(value: Any, label: str) -> str:
    result = _text(value, label)
    if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
        raise ResearchAllocationError(f"{label} must be a lowercase SHA-256")
    return result


def _enum(value: Any, allowed: set[str], label: str) -> str:
    result = _text(value, label)
    if result not in allowed:
        raise ResearchAllocationError(f"unsupported {label}: {result}")
    return result


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchAllocationError(f"{label} must be a non-empty string")
    return value.strip()


def _text_array(value: Any, label: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ResearchAllocationError(f"{label} must be a string array")
    result = [item.strip() for item in value]
    if not allow_empty and not result:
        raise ResearchAllocationError(f"{label} must not be empty")
    if len(result) != len(set(result)):
        raise ResearchAllocationError(f"{label} must not contain duplicates")
    return result


def _datetime(value: Any, label: str) -> dt.datetime:
    text = _text(value, label)
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise ResearchAllocationError(f"{label} must be an ISO datetime") from exc
    _aware(parsed, label)
    return parsed


def _date(value: Any, label: str) -> dt.date:
    text = _text(value, label)
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ResearchAllocationError(f"{label} must be an ISO date") from exc


def _aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchAllocationError(f"{label} must include timezone information")


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResearchAllocationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ResearchAllocationError(f"{label} must be finite")
    return result


def _positive_number(value: Any, label: str) -> float:
    result = _number(value, label)
    if result <= 0:
        raise ResearchAllocationError(f"{label} must be positive")
    return result
