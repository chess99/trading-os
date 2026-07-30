from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .models import canonical_company_name
from .research_allocation import (
    ResearchAllocationError,
    evaluate_quick_profile,
)
from .sealing import canonical_json_bytes, seal_json, verify_sealed

PACKAGE_KEYS = {
    "schema_version",
    "cycle_id",
    "company_name",
    "profile",
    "price_as_of",
    "price_source_id",
    "provenance",
    "analysis",
    "sources",
}
PROVENANCE_KEYS = {"agent", "model", "tools", "generated_at"}
PROFILE_DECISION_PACKAGE_KEYS = {
    "schema_version",
    "cycle_id",
    "evaluated_stage",
    "comparison_sha256",
    "decisions",
    "provenance",
}
PROFILE_DECISION_KEYS = {
    "symbol",
    "decision",
    "reason",
    "decisive_question",
    "counterevidence_considered",
}
ANALYSIS_KEYS = {
    "business_summary",
    "owner_earnings_and_cycle",
    "survival",
    "governance",
    "valuation_basis",
    "market_mispricing",
    "decisive_unknowns",
}
ANALYSIS_ITEM_KEYS = {"conclusion", "source_ids"}
SOURCE_KEYS = {
    "source_id",
    "tier",
    "title",
    "publisher",
    "published_at",
    "accessed_at",
    "url",
    "local_path",
    "supports",
}
SOURCE_TIERS = {"S1", "S2", "S3"}
RESEARCH_STAGES = {"targeted_followup", "scoped_research", "deep_research"}
TERMINAL_STAGES = {
    "profile_candidate",
    "deep_candidate",
    "price_watch",
    "reassign_or_stop",
    "conditional_stop",
}
CYCLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@serialized_coverage_write
def claim_profile_task(
    *,
    root: str | Path,
    agent: str,
    claimed_at: dt.datetime,
    symbol: str | None = None,
    lens: str | None = None,
) -> dict[str, Any]:
    """Atomically claim one unassigned profile or deep-research task."""

    _require_aware_datetime(claimed_at, "claimed_at")
    agent_name = _text(agent, "agent")
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    queue = read_jsonl(queue_path)
    running = [
        item
        for item in queue
        if item.get("assigned_agent") == agent_name and item.get("status") == "running"
    ]
    if len(running) > 1:
        raise ResearchAllocationError(f"agent has multiple running tasks: {agent_name}")
    if running:
        current = running[0]
        if symbol is not None and current.get("symbol") != symbol:
            raise ResearchAllocationError(
                f"agent already has a different running task: {current.get('symbol')}"
            )
        return _claimed_task_payload(current, idempotent=True)

    candidates = [
        item
        for item in queue
        if item.get("task_type")
        in {"quick_profile", "targeted_followup", "scoped_research", "deep_research"}
        and item.get("status") == "pending"
        and item.get("assigned_agent") is None
    ]
    if symbol is not None:
        if not re.fullmatch(r"CN:[0-9]{6}", symbol):
            raise ResearchAllocationError("claim symbol is invalid")
        candidates = [item for item in candidates if item.get("symbol") == symbol]
    if lens is not None:
        lens_name = _text(lens, "lens")
        candidates = [
            item for item in candidates if lens_name in (item.get("selected_by") or [])
        ]
    if not candidates:
        raise ResearchAllocationError("no eligible profile task is available")
    candidates.sort(
        key=lambda item: (
            int(item.get("priority", 5)),
            {"scoped_research": 0, "targeted_followup": 1}.get(
                str(item.get("task_type")), 2
            ),
            str(item.get("symbol")),
        )
    )
    selected = dict(candidates[0])
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
    return _claimed_task_payload(selected, idempotent=False)


@serialized_coverage_write
def release_profile_task(
    *,
    root: str | Path,
    agent: str,
    symbol: str,
    failure_reason: str,
    released_at: dt.datetime,
) -> dict[str, Any]:
    """Release one failed L2/L3 claim while preserving an auditable attempt."""

    _require_aware_datetime(released_at, "released_at")
    agent_name = _text(agent, "agent")
    reason = _text(failure_reason, "failure_reason")
    if not re.fullmatch(r"CN:[0-9]{6}", symbol):
        raise ResearchAllocationError("release symbol is invalid")
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    queue = read_jsonl(queue_path)
    record = _one_record(queue, symbol, "research queue")
    if record.get("status") != "running":
        raise ResearchAllocationError(f"profile task is not running: {symbol}")
    if record.get("assigned_agent") != agent_name:
        raise ResearchAllocationError(
            f"only the assigned agent can release profile task: {symbol}"
        )
    if record.get("task_type") not in {
        "quick_profile",
        "targeted_followup",
        "scoped_research",
        "deep_research",
    }:
        raise ResearchAllocationError(
            f"task type cannot be released by profile workflow: {record.get('task_type')}"
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
    released = dict(record)
    released.update(
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
        [released if item.get("symbol") == symbol else item for item in queue],
    )
    return {
        "schema_version": 1,
        "symbol": symbol,
        "released_agent": agent_name,
        "failure_reason": reason,
        "released_at": released_at.isoformat(),
        "attempt_count": len(attempts),
        "status": "pending",
        "portfolio_action": None,
    }


@serialized_coverage_write
def record_profile_package(
    package: Mapping[str, Any],
    *,
    root: str | Path,
    policy: Mapping[str, Any],
    policy_reference: str,
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Seal one company profile and materialize its deterministic next stage."""

    _require_aware_datetime(recorded_at, "recorded_at")
    normalized = _validate_package(package, recorded_at=recorded_at)
    profile = normalized["profile"]
    evaluation = evaluate_quick_profile(profile, policy=policy)
    symbol = profile["symbol"]
    ticker = symbol.split(":", 1)[1]
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue_records = read_jsonl(queue_path)
    screening_records = read_jsonl(screening_path)
    queue_record = _one_record(queue_records, symbol, "research queue")
    screening_record = _one_record(screening_records, symbol, "screening")

    timestamp = recorded_at.strftime("%Y%m%dT%H%M%S%z")
    artifact_dir = base / "profiles" / normalized["cycle_id"] / ticker
    profile_path = artifact_dir / f"{timestamp}.profile.json"
    evaluation_path = artifact_dir / f"{timestamp}.evaluation.json"
    repository_root = base.parent.parent
    relative_profile = profile_path.relative_to(repository_root).as_posix()
    relative_evaluation = evaluation_path.relative_to(repository_root).as_posix()
    policy_sha = hashlib.sha256(canonical_json_bytes(dict(policy))).hexdigest()
    replayed = _verify_profile_record_replay(
        normalized=normalized,
        raw_evaluation=evaluation,
        queue_record=queue_record,
        profile_path=profile_path,
        evaluation_path=evaluation_path,
        relative_profile=relative_profile,
        relative_evaluation=relative_evaluation,
        policy_reference=_text(policy_reference, "policy_reference"),
        policy_sha256=policy_sha,
        recorded_at=recorded_at,
    )
    if replayed is not None:
        return replayed
    _validate_local_sources(normalized["sources"], repository_root=repository_root)
    _validate_industry_evidence(
        normalized,
        queue_record=queue_record,
        policy=policy,
    )

    queued_stage = str(queue_record.get("task_type"))
    expected_profile_stage = (
        queue_record.get("preceding_stage")
        if queued_stage == "targeted_followup"
        else queued_stage
    )
    if expected_profile_stage != profile["research_stage"]:
        raise ResearchAllocationError(
            f"queued stage does not match profile for {symbol}: "
            f"{queued_stage} expects {expected_profile_stage}, got "
            f"{profile['research_stage']}"
        )
    if queue_record.get("status") not in {"pending", "running"}:
        raise ResearchAllocationError(
            f"profile cannot be recorded from queue status "
            f"{queue_record.get('status')}: {symbol}"
        )
    if canonical_company_name(normalized["company_name"]) != canonical_company_name(
        str(queue_record.get("name"))
    ):
        raise ResearchAllocationError(f"company name does not match queue: {symbol}")
    assigned_agent = queue_record.get("assigned_agent")
    if assigned_agent is not None and assigned_agent != normalized["provenance"]["agent"]:
        raise ResearchAllocationError(
            f"profile provenance agent does not match queue assignment: {symbol}"
        )
    manager_screen_binding = (
        queued_stage == "quick_profile"
        and queue_record.get("preceding_stage") == "manager_screen"
        and isinstance(queue_record.get("manager_screen_result_path"), str)
    )
    allocation_sha = (
        None if manager_screen_binding else queue_record.get("allocation_sha256")
    )
    if allocation_sha is not None:
        bound_cycles = {
            item.get("profile_cycle_id")
            for item in queue_records
            if item.get("allocation_sha256") == allocation_sha
            and item.get("profile_cycle_id") is not None
        }
        if bound_cycles and bound_cycles != {normalized["cycle_id"]}:
            raise ResearchAllocationError(
                f"allocation is already bound to another profile cycle: {sorted(bound_cycles)}"
            )

    sealed_profile = seal_json(
        profile_path,
        normalized,
        artifact_type="quick_profile_package",
        sealed_at=recorded_at,
    )
    evaluation, next_stage = _adjust_profile_evaluation(evaluation, queued_stage=queued_stage)
    if next_stage not in RESEARCH_STAGES | TERMINAL_STAGES:
        raise ResearchAllocationError(f"unsupported profile next stage: {next_stage}")

    next_status = "completed"
    capacity_wait = False
    if next_stage in RESEARCH_STAGES:
        next_status = "pending"
        capacity = _stage_capacity(policy, next_stage)
        if capacity is not None:
            active_count = sum(
                1
                for item in queue_records
                if item.get("symbol") != symbol
                and item.get("task_type") == next_stage
                and item.get("status") in {"pending", "running"}
            )
            if active_count >= capacity:
                next_status = "requires_rebaseline"
                capacity_wait = True

    evaluation_payload = {
        "schema_version": 2,
        "cycle_id": normalized["cycle_id"],
        "symbol": symbol,
        "company_name": normalized["company_name"],
        "recorded_at": recorded_at.isoformat(),
        "profile_path": relative_profile,
        "profile_sha256": sealed_profile.sha256,
        "policy_reference": _text(policy_reference, "policy_reference"),
        "policy_payload_sha256": policy_sha,
        "allocation_sha256": allocation_sha,
        "evaluation": evaluation,
        "queue_status": next_status,
        "capacity_wait": capacity_wait,
        "portfolio_action": None,
    }
    sealed_evaluation = seal_json(
        evaluation_path,
        evaluation_payload,
        artifact_type="quick_profile_evaluation",
        sealed_at=recorded_at,
    )

    updated_screening = dict(screening_record)
    updated_screening.update(
        {
            "decision": next_stage,
            "reason": _screening_reason(next_stage, capacity_wait),
            "evidence": [
                f"profile:{relative_profile}",
                f"profile_sha256:{sealed_profile.sha256}",
                f"evaluation:{relative_evaluation}",
                f"evaluation_sha256:{sealed_evaluation.sha256}",
                f"policy:{policy_reference}",
                f"s1_sources:{profile['s1_source_count']}",
            ],
            "next_action": _next_action(next_stage, capacity_wait),
            "profile_cycle_id": normalized["cycle_id"],
            "profile_evaluation_path": relative_evaluation,
            "profile_recorded_at": recorded_at.isoformat(),
        }
    )

    history = list(queue_record.get("stage_history") or [])
    history.append(
        {
            "stage": queued_stage,
            "status": "completed",
            "finished_at": recorded_at.isoformat(),
            "agent": normalized["provenance"]["agent"],
            "result_path": relative_profile,
            "evaluation_path": relative_evaluation,
            "next_stage": next_stage,
        }
    )
    updated_queue = dict(queue_record)
    if manager_screen_binding:
        for stale in (
            "allocation_sha256",
            "selected_by",
            "triage_selection_path",
            "triage_selection_sha256",
            "triage_allocation_decision",
            "triage_selection_reason",
            "triage_review_mode",
            "profile_cycle_id",
            "profile_evaluation_path",
            "profile_recorded_at",
            "profile_quick_selection_path",
            "profile_scoped_selection_path",
            "profile_priority_score",
        ):
            updated_queue.pop(stale, None)
    updated_queue.update(
        {
            "task_type": next_stage if next_stage in RESEARCH_STAGES else queued_stage,
            "status": next_status,
            "reason": _screening_reason(next_stage, capacity_wait),
            "assigned_agent": (
                None if next_stage in RESEARCH_STAGES else normalized["provenance"]["agent"]
            ),
            "started_at": None if next_stage in RESEARCH_STAGES else queue_record.get("started_at"),
            "finished_at": None if next_stage in RESEARCH_STAGES else recorded_at.isoformat(),
            "result_path": relative_evaluation,
            "failure_reason": None,
            "next_action": _next_action(next_stage, capacity_wait),
            "preceding_stage": queued_stage,
            "stage_history": history,
            "profile_cycle_id": normalized["cycle_id"],
            "profile_priority_score": _profile_priority_score(
                profile,
                priority=int(queue_record.get("priority", 5)),
            ),
        }
    )
    if next_stage in RESEARCH_STAGES:
        updated_queue["effort_budget_hours"] = _effort_budget(policy, next_stage)
        updated_queue["stop_conditions"] = _stop_conditions(next_stage)

    write_jsonl(
        screening_path,
        [updated_screening if item.get("symbol") == symbol else item for item in screening_records],
    )
    write_jsonl(
        queue_path,
        [updated_queue if item.get("symbol") == symbol else item for item in queue_records],
    )
    return _profile_record_result(
        evaluation_payload,
        profile_sha256=sealed_profile.sha256,
        evaluation_path=relative_evaluation,
        evaluation_sha256=sealed_evaluation.sha256,
        idempotent=False,
    )


def _adjust_profile_evaluation(
    evaluation: Mapping[str, Any], *, queued_stage: str
) -> tuple[dict[str, Any], str]:
    """Apply the queue-stage gates that precede cross-company promotion."""

    adjusted = dict(evaluation)
    next_stage = str(adjusted.get("next_stage"))
    if queued_stage == "quick_profile" and next_stage == "scoped_research":
        next_stage = "profile_candidate"
        adjusted["next_stage"] = next_stage
        adjusted["maximum_additional_effort_hours"] = 0.0
        adjusted["reason_codes"] = sorted(
            set(adjusted["reason_codes"])
            | {"awaiting_cross_company_profile_comparison"}
        )
    elif queued_stage == "scoped_research" and next_stage == "deep_research":
        next_stage = "deep_candidate"
        adjusted["next_stage"] = next_stage
        adjusted["maximum_additional_effort_hours"] = 0.0
        adjusted["reason_codes"] = sorted(
            set(adjusted["reason_codes"])
            | {"awaiting_cross_company_deep_research_comparison"}
        )
    if queued_stage == "targeted_followup" and next_stage == "targeted_followup":
        next_stage = "reassign_or_stop"
        adjusted["next_stage"] = next_stage
        adjusted["maximum_additional_effort_hours"] = 0.0
        adjusted["reason_codes"] = sorted(
            set(adjusted["reason_codes"]) | {"targeted_followup_exhausted"}
        )
    return adjusted, next_stage


def _verify_profile_record_replay(
    *,
    normalized: Mapping[str, Any],
    raw_evaluation: Mapping[str, Any],
    queue_record: Mapping[str, Any],
    profile_path: Path,
    evaluation_path: Path,
    relative_profile: str,
    relative_evaluation: str,
    policy_reference: str,
    policy_sha256: str,
    recorded_at: dt.datetime,
) -> dict[str, Any] | None:
    """Return a read-only result for one fully materialized sealed profile."""

    matches = [
        item
        for item in queue_record.get("stage_history") or []
        if isinstance(item, Mapping)
        and item.get("status") == "completed"
        and item.get("result_path") == relative_profile
        and item.get("evaluation_path") == relative_evaluation
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ResearchAllocationError(
            f"profile replay has duplicate completed history: {normalized['profile']['symbol']}"
        )
    history = matches[0]
    recorded_stage = _text(history.get("stage"), "profile history stage")
    profile_stage = str(normalized["profile"].get("research_stage"))
    if recorded_stage != "targeted_followup" and recorded_stage != profile_stage:
        raise ResearchAllocationError(
            f"profile replay stage conflicts with completed history: "
            f"{normalized['profile']['symbol']}"
        )
    adjusted_evaluation, next_stage = _adjust_profile_evaluation(
        raw_evaluation,
        queued_stage=recorded_stage,
    )
    expected_history = {
        "finished_at": recorded_at.isoformat(),
        "agent": normalized["provenance"]["agent"],
        "result_path": relative_profile,
        "evaluation_path": relative_evaluation,
        "next_stage": next_stage,
    }
    mismatched_history = [
        field
        for field, expected in expected_history.items()
        if history.get(field) != expected
    ]
    if mismatched_history:
        raise ResearchAllocationError(
            "profile replay conflicts with completed history "
            f"({', '.join(mismatched_history)}): {normalized['profile']['symbol']}"
        )

    try:
        sealed_profile = verify_sealed(profile_path)
    except ValueError as exc:
        raise ResearchAllocationError(
            f"completed profile package is not validly sealed: "
            f"{normalized['profile']['symbol']}"
        ) from exc
    if sealed_profile.artifact_type != "quick_profile_package":
        raise ResearchAllocationError(
            f"completed profile package has the wrong artifact type: "
            f"{normalized['profile']['symbol']}"
        )
    if sealed_profile.sealed_at != recorded_at:
        raise ResearchAllocationError(
            f"profile replay recorded_at conflicts with the package seal: "
            f"{normalized['profile']['symbol']}"
        )
    try:
        existing_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError(
            f"completed profile package cannot be read: {normalized['profile']['symbol']}"
        ) from exc
    if existing_profile != normalized:
        raise ResearchAllocationError(
            f"profile replay conflicts with the sealed package: "
            f"{normalized['profile']['symbol']}"
        )

    try:
        sealed_evaluation = verify_sealed(evaluation_path)
    except ValueError as exc:
        raise ResearchAllocationError(
            f"completed profile evaluation is not validly sealed: "
            f"{normalized['profile']['symbol']}"
        ) from exc
    if sealed_evaluation.artifact_type != "quick_profile_evaluation":
        raise ResearchAllocationError(
            f"completed profile evaluation has the wrong artifact type: "
            f"{normalized['profile']['symbol']}"
        )
    if sealed_evaluation.sealed_at != recorded_at:
        raise ResearchAllocationError(
            f"profile replay recorded_at conflicts with the evaluation seal: "
            f"{normalized['profile']['symbol']}"
        )
    try:
        evaluation_payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError(
            f"completed profile evaluation cannot be read: "
            f"{normalized['profile']['symbol']}"
        ) from exc
    expected_fields = {
        "schema_version",
        "cycle_id",
        "symbol",
        "company_name",
        "recorded_at",
        "profile_path",
        "profile_sha256",
        "policy_reference",
        "policy_payload_sha256",
        "allocation_sha256",
        "evaluation",
        "queue_status",
        "capacity_wait",
        "portfolio_action",
    }
    if not isinstance(evaluation_payload, dict) or set(evaluation_payload) != expected_fields:
        raise ResearchAllocationError(
            f"completed profile evaluation fields do not match contract: "
            f"{normalized['profile']['symbol']}"
        )
    expected_values = {
        "schema_version": 2,
        "cycle_id": normalized["cycle_id"],
        "symbol": normalized["profile"]["symbol"],
        "company_name": normalized["company_name"],
        "recorded_at": recorded_at.isoformat(),
        "profile_path": relative_profile,
        "profile_sha256": sealed_profile.sha256,
        "policy_reference": policy_reference,
        "policy_payload_sha256": policy_sha256,
        "evaluation": adjusted_evaluation,
        "portfolio_action": None,
    }
    mismatched_evaluation = [
        field
        for field, expected in expected_values.items()
        if evaluation_payload.get(field) != expected
    ]
    queue_status = evaluation_payload.get("queue_status")
    capacity_wait = evaluation_payload.get("capacity_wait")
    if next_stage in RESEARCH_STAGES:
        if queue_status not in {"pending", "requires_rebaseline"}:
            mismatched_evaluation.append("queue_status")
        if capacity_wait is not (queue_status == "requires_rebaseline"):
            mismatched_evaluation.append("capacity_wait")
    elif queue_status != "completed" or capacity_wait is not False:
        mismatched_evaluation.extend(["queue_status", "capacity_wait"])
    if mismatched_evaluation:
        raise ResearchAllocationError(
            "profile replay conflicts with the sealed evaluation "
            f"({', '.join(sorted(set(mismatched_evaluation)))}): "
            f"{normalized['profile']['symbol']}"
        )
    return _profile_record_result(
        evaluation_payload,
        profile_sha256=sealed_profile.sha256,
        evaluation_path=relative_evaluation,
        evaluation_sha256=sealed_evaluation.sha256,
        idempotent=True,
    )


def _profile_record_result(
    evaluation_payload: Mapping[str, Any],
    *,
    profile_sha256: str,
    evaluation_path: str,
    evaluation_sha256: str,
    idempotent: bool,
) -> dict[str, Any]:
    evaluation = evaluation_payload["evaluation"]
    return {
        "schema_version": 2,
        "symbol": evaluation_payload["symbol"],
        "next_stage": evaluation["next_stage"],
        "queue_status": evaluation_payload["queue_status"],
        "capacity_wait": evaluation_payload["capacity_wait"],
        "profile_path": evaluation_payload["profile_path"],
        "profile_sha256": profile_sha256,
        "evaluation_path": evaluation_path,
        "evaluation_sha256": evaluation_sha256,
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def build_profile_comparison_packet(
    *,
    root: str | Path,
    cycle_id: str,
    stage: str,
    created_at: dt.datetime,
) -> dict[str, Any]:
    """Seal a score-free L2/L3 packet for an independent allocation Agent."""

    _require_aware_datetime(created_at, "created_at")
    cycle = _text(cycle_id, "cycle_id")
    if not CYCLE_RE.fullmatch(cycle):
        raise ResearchAllocationError("cycle_id is invalid")
    config = _profile_stage_config(stage)
    base = Path(root)
    repository_root = base.parent.parent
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    _, binding, binding_sha, cohort = _complete_profile_cohort(
        queue,
        repository_root=repository_root,
        cycle=cycle,
        stage=stage,
    )
    comparison_path = base / "profiles" / cycle / config["comparison_name"]
    relative = comparison_path.relative_to(repository_root).as_posix()
    if comparison_path.exists():
        sealed = verify_sealed(comparison_path)
        if sealed.artifact_type != f"{stage}_comparison_packet":
            raise ResearchAllocationError(
                f"sealed {stage} comparison has the wrong artifact type"
            )
        payload = json.loads(comparison_path.read_text(encoding="utf-8"))
        expected = {
            "cycle_id": cycle,
            "evaluated_stage": stage,
            "predecessor_selection_path": binding,
            "predecessor_selection_sha256": binding_sha,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ResearchAllocationError(
                f"sealed {stage} comparison conflicts with cycle binding"
            )
        return _profile_comparison_result(
            payload,
            comparison_path=relative,
            comparison_sha256=sealed.sha256,
            idempotent=True,
        )

    rows = [
        _profile_comparison_row(
            item,
            ordinal=ordinal,
            cycle=cycle,
            stage=stage,
            repository_root=repository_root,
        )
        for ordinal, item in enumerate(cohort, 1)
    ]
    payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "evaluated_stage": stage,
        "next_stage": config["next_stage"],
        "predecessor_selection_path": binding,
        "predecessor_selection_sha256": binding_sha,
        "created_at": created_at.isoformat(),
        "cohort_count": len(rows),
        "principle": (
            "Every company in the complete sealed stage cohort is shown in frozen "
            "predecessor order. The packet contains no programmatic investment "
            "score, priority, or ranking."
        ),
        "rows": rows,
        "portfolio_action": None,
    }
    sealed = seal_json(
        comparison_path,
        payload,
        artifact_type=f"{stage}_comparison_packet",
        sealed_at=created_at,
    )
    return _profile_comparison_result(
        payload,
        comparison_path=relative,
        comparison_sha256=sealed.sha256,
        idempotent=False,
    )


@serialized_coverage_write
def finalize_profile_stage_with_agent_decisions(
    *,
    root: str | Path,
    cycle_id: str,
    stage: str,
    policy: Mapping[str, Any],
    decisions: Mapping[str, Any],
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    """Grant L3/L4 budget from an independent Agent's explicit full decisions."""

    _require_aware_datetime(finalized_at, "finalized_at")
    cycle = _text(cycle_id, "cycle_id")
    if not CYCLE_RE.fullmatch(cycle):
        raise ResearchAllocationError("cycle_id is invalid")
    config = _profile_stage_config(stage)
    base = Path(root)
    repository_root = base.parent.parent
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    _, binding, binding_sha, cohort = _complete_profile_cohort(
        queue,
        repository_root=repository_root,
        cycle=cycle,
        stage=stage,
    )
    comparison_path = base / "profiles" / cycle / config["comparison_name"]
    if not comparison_path.exists():
        raise ResearchAllocationError(
            f"{stage} comparison packet is missing; run profile-compare first"
        )
    sealed_comparison = verify_sealed(comparison_path)
    if sealed_comparison.artifact_type != f"{stage}_comparison_packet":
        raise ResearchAllocationError(
            f"sealed {stage} comparison has the wrong artifact type"
        )
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if (
        comparison.get("cycle_id") != cycle
        or comparison.get("evaluated_stage") != stage
        or comparison.get("predecessor_selection_path") != binding
        or comparison.get("predecessor_selection_sha256") != binding_sha
    ):
        raise ResearchAllocationError(
            f"{stage} comparison packet does not match cohort binding"
        )
    comparison_rows = comparison.get("rows")
    if not isinstance(comparison_rows, list) or not all(
        isinstance(row, Mapping) for row in comparison_rows
    ):
        raise ResearchAllocationError(f"{stage} comparison rows are invalid")
    if len(comparison_rows) != len(cohort):
        raise ResearchAllocationError(f"{stage} comparison cohort count is invalid")
    normalized = _normalize_profile_decision_package(
        decisions,
        cycle=cycle,
        stage=stage,
        comparison_sha256=sealed_comparison.sha256,
        comparison_rows=comparison_rows,
        finalized_at=finalized_at,
    )
    if _datetime(
        normalized["provenance"]["generated_at"],
        "decision.provenance.generated_at",
    ) < _datetime(comparison.get("created_at"), "comparison.created_at"):
        raise ResearchAllocationError(
            "profile allocation decisions cannot predate the sealed comparison"
        )
    research_agents = {
        row.get("research_agent")
        for row in comparison_rows
        if isinstance(row.get("research_agent"), str)
    }
    if normalized["provenance"]["agent"] in research_agents:
        raise ResearchAllocationError(
            "cross-company profile allocation Agent must be independent of "
            "company research Agents"
        )

    next_stage = config["next_stage"]
    select_decision = config["select_decision"]
    selected_symbols = [
        row["symbol"]
        for row in normalized["decisions"]
        if row["decision"] == select_decision
    ]
    capacity = _stage_capacity(policy, next_stage)
    if capacity is None:
        raise ResearchAllocationError(f"stage capacity is invalid: {next_stage}")
    if len(selected_symbols) > capacity:
        raise ResearchAllocationError(
            f"Agent decisions exceed {next_stage} capacity: "
            f"{len(selected_symbols)} > {capacity}"
        )
    risk_cap = _risk_cluster_cap(policy, next_stage)
    if len(selected_symbols) > risk_cap:
        raise ResearchAllocationError(
            "Agent decisions exceed the conservative unclassified risk-cluster "
            f"cap for {next_stage}: {len(selected_symbols)} > {risk_cap}"
        )
    budget = _effort_budget(policy, next_stage)
    selected_set = set(selected_symbols)
    decisions_by_symbol = {
        row["symbol"]: row for row in normalized["decisions"]
    }
    decision_rows = [
        {
            "ordinal": row["ordinal"],
            "symbol": row["symbol"],
            "name": row["name"],
            "selected": row["symbol"] in selected_set,
            "selection_reason": decisions_by_symbol[row["symbol"]]["reason"],
            "decisive_question": decisions_by_symbol[row["symbol"]][
                "decisive_question"
            ],
            "counterevidence_considered": decisions_by_symbol[row["symbol"]][
                "counterevidence_considered"
            ],
        }
        for row in comparison_rows
    ]
    selection_path = base / "profiles" / cycle / config["selection_name"]
    relative_selection = selection_path.relative_to(repository_root).as_posix()
    payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "evaluated_stage": stage,
        "next_stage": next_stage,
        "predecessor_selection_path": binding,
        "predecessor_selection_sha256": binding_sha,
        "comparison_path": comparison_path.relative_to(repository_root).as_posix(),
        "comparison_sha256": sealed_comparison.sha256,
        "finalized_at": finalized_at.isoformat(),
        "cohort_count": len(cohort),
        "eligible_count": len(cohort),
        "reviewed_count": len(decision_rows),
        "capacity": capacity,
        "risk_cluster_cap": risk_cap,
        "risk_cluster_mode": "conservative_unclassified",
        "next_stage_effort_budget_hours": budget,
        "selected_count": len(selected_symbols),
        "principle": policy.get("comparison_principle"),
        "agent_decision": normalized,
        "decisions": decision_rows,
        # Compatibility view for the existing crash-safe materializer. This is
        # frozen cohort order and deliberately is not an investment ranking.
        "ranking": decision_rows,
        "portfolio_action": None,
    }
    existed = selection_path.exists()
    if existed:
        sealed_selection = verify_sealed(selection_path)
        if sealed_selection.artifact_type != f"{stage}_cross_company_selection":
            raise ResearchAllocationError(
                f"sealed {stage} selection has the wrong artifact type"
            )
        existing = json.loads(selection_path.read_text(encoding="utf-8"))
        expected_replay = {k: v for k, v in payload.items() if k != "finalized_at"}
        actual_replay = {
            k: v for k, v in existing.items() if k != "finalized_at"
        }
        if actual_replay != expected_replay:
            raise ResearchAllocationError(
                f"sealed {stage} selection conflicts with Agent decisions"
            )
        materialization_payload = existing
    else:
        sealed_selection = seal_json(
            selection_path,
            payload,
            artifact_type=f"{stage}_cross_company_selection",
            sealed_at=finalized_at,
        )
        materialization_payload = payload
    updated_screening, updated_queue, screening_changed, queue_changed = (
        _materialize_profile_selection(
            screening=screening,
            queue=queue,
            payload=materialization_payload,
            cycle=cycle,
            stage=stage,
            next_stage=next_stage,
            next_binding_field=config["next_binding_field"],
            selection_path=relative_selection,
            selection_sha256=sealed_selection.sha256,
            budget=budget,
        )
    )
    if screening_changed:
        write_jsonl(screening_path, updated_screening)
    if queue_changed:
        write_jsonl(queue_path, updated_queue)
    return _profile_selection_result(
        materialization_payload,
        selection_path=relative_selection,
        selection_sha256=sealed_selection.sha256,
        idempotent=existed,
    )


@serialized_coverage_write
def finalize_profile_stage(
    *,
    root: str | Path,
    cycle_id: str,
    stage: str,
    policy: Mapping[str, Any],
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    """Allocate the next research layer only after a complete peer cohort."""

    _require_aware_datetime(finalized_at, "finalized_at")
    cycle = _text(cycle_id, "cycle_id")
    if not CYCLE_RE.fullmatch(cycle):
        raise ResearchAllocationError("cycle_id is invalid")
    if stage not in {"quick_profile", "scoped_research"}:
        raise ResearchAllocationError(
            "profile comparison stage must be quick_profile or scoped_research"
        )
    base = Path(root)
    repository_root = base.parent.parent
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)

    if stage == "quick_profile":
        binding_field = "triage_selection_path"
        candidate_decision = "profile_candidate"
        next_stage = "scoped_research"
        selection_name = "quick-profile-selection.json"
    else:
        binding_field = "profile_quick_selection_path"
        candidate_decision = "deep_candidate"
        next_stage = "deep_research"
        selection_name = "scoped-research-selection.json"
    next_binding_field = (
        "profile_quick_selection_path"
        if stage == "quick_profile"
        else "profile_scoped_selection_path"
    )

    selection_path = base / "profiles" / cycle / selection_name
    if selection_path.exists():
        verified = verify_sealed(selection_path)
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
        relative = selection_path.relative_to(repository_root).as_posix()
        _validate_profile_selection_payload(
            payload,
            artifact_type=verified.artifact_type,
            cycle=cycle,
            stage=stage,
            next_stage=next_stage,
        )
        bound_budget = payload.get("next_stage_effort_budget_hours")
        updated_screening, updated_queue, screening_changed, queue_changed = (
            _materialize_profile_selection(
                screening=screening,
                queue=queue,
                payload=payload,
                cycle=cycle,
                stage=stage,
                next_stage=next_stage,
                next_binding_field=next_binding_field,
                selection_path=relative,
                selection_sha256=verified.sha256,
                budget=float(bound_budget) if bound_budget is not None else None,
            )
        )
        if screening_changed:
            write_jsonl(screening_path, updated_screening)
        if queue_changed:
            write_jsonl(queue_path, updated_queue)
        return _profile_selection_result(
            payload,
            selection_path=relative,
            selection_sha256=verified.sha256,
            idempotent=True,
        )

    anchors = [
        item
        for item in queue
        if item.get("profile_cycle_id") == cycle
        and _history_completed(item, stage)
        and isinstance(item.get(binding_field), str)
    ]
    if not anchors:
        raise ResearchAllocationError(
            f"no recorded {stage} cohort is available for cycle: {cycle}"
        )
    bindings = {item[binding_field] for item in anchors}
    if len(bindings) != 1:
        raise ResearchAllocationError(
            f"{stage} cycle spans multiple predecessor selections"
        )
    binding = next(iter(bindings))
    cohort = _bound_profile_cohort(
        queue,
        repository_root=repository_root,
        binding_field=binding_field,
        binding=binding,
        stage=stage,
    )
    incomplete = [
        item["symbol"]
        for item in cohort
        if item.get("profile_cycle_id") != cycle
        or not _history_completed(item, stage)
        or (
            item.get("task_type") == "targeted_followup"
            and item.get("preceding_stage") == stage
            and item.get("status") in {"pending", "running"}
        )
    ]
    if incomplete:
        raise ResearchAllocationError(
            "completion-order promotion is forbidden; "
            f"{stage} cohort is incomplete: {incomplete[:10]}"
        )
    screen_by_symbol = {item["symbol"]: dict(item) for item in screening}
    eligible = [
        item
        for item in cohort
        if screen_by_symbol[item["symbol"]].get("decision") == candidate_decision
    ]
    ranked = sorted(
        eligible,
        key=lambda item: (
            -int(item.get("profile_priority_score", 0)),
            int(item.get("priority", 5)),
            str(item["symbol"]),
        ),
    )
    capacities = policy.get("stage_capacity_per_cycle")
    if not isinstance(capacities, Mapping):
        raise ResearchAllocationError("stage capacity policy is invalid")
    capacity = capacities.get(next_stage)
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise ResearchAllocationError(f"stage capacity is invalid: {next_stage}")
    budgets = policy.get("effort_budget_hours")
    if not isinstance(budgets, Mapping):
        raise ResearchAllocationError("effort budget policy is invalid")
    budget = budgets.get(next_stage)
    if (
        isinstance(budget, bool)
        or not isinstance(budget, (int, float))
        or budget <= 0
    ):
        raise ResearchAllocationError(f"effort budget is invalid: {next_stage}")
    risk_cap = _risk_cluster_cap(policy, next_stage)
    selected, capped_symbols = _select_with_risk_cluster_cap(
        ranked,
        capacity=capacity,
        cap=risk_cap,
    )
    selected_symbols = {item["symbol"] for item in selected}
    rows = [
        {
            "rank": rank,
            "symbol": item["symbol"],
            "name": item["name"],
            "research_priority_score": item.get("profile_priority_score", 0),
            "selected": item["symbol"] in selected_symbols,
            "economic_risk_cluster": item.get("economic_risk_cluster"),
            "selection_reason": (
                "selected_within_risk_cluster_cap"
                if item["symbol"] in selected_symbols
                else "risk_cluster_cap_reached"
                if item["symbol"] in capped_symbols
                else "lower_cross_company_priority"
            ),
        }
        for rank, item in enumerate(ranked, 1)
    ]
    selection_payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "evaluated_stage": stage,
        "next_stage": next_stage,
        "predecessor_selection_path": binding,
        "finalized_at": finalized_at.isoformat(),
        "cohort_count": len(cohort),
        "eligible_count": len(eligible),
        "capacity": capacity,
        "risk_cluster_cap": risk_cap,
        "next_stage_effort_budget_hours": float(budget),
        "selected_count": len(selected),
        "principle": policy.get("comparison_principle"),
        "ranking": rows,
        "portfolio_action": None,
    }
    sealed = seal_json(
        selection_path,
        selection_payload,
        artifact_type=f"{stage}_cross_company_selection",
        sealed_at=finalized_at,
    )
    relative_selection = selection_path.relative_to(repository_root).as_posix()
    updated_screening, updated_queue, screening_changed, queue_changed = (
        _materialize_profile_selection(
            screening=screening,
            queue=queue,
            payload=selection_payload,
            cycle=cycle,
            stage=stage,
            next_stage=next_stage,
            next_binding_field=next_binding_field,
            selection_path=relative_selection,
            selection_sha256=sealed.sha256,
            budget=float(budget),
        )
    )
    if screening_changed:
        write_jsonl(screening_path, updated_screening)
    if queue_changed:
        write_jsonl(queue_path, updated_queue)
    return _profile_selection_result(
        selection_payload,
        selection_path=relative_selection,
        selection_sha256=sealed.sha256,
        idempotent=False,
    )


def _validate_profile_selection_payload(
    payload: Any,
    *,
    artifact_type: str,
    cycle: str,
    stage: str,
    next_stage: str,
) -> None:
    expected_artifact_type = f"{stage}_cross_company_selection"
    if artifact_type != expected_artifact_type:
        raise ResearchAllocationError(
            f"sealed {stage} selection has the wrong artifact type: {artifact_type}"
        )
    if not isinstance(payload, Mapping):
        raise ResearchAllocationError(f"sealed {stage} selection must be an object")
    if payload.get("schema_version") != 1:
        raise ResearchAllocationError(f"sealed {stage} selection schema_version must be 1")
    expected_values = {
        "cycle_id": cycle,
        "evaluated_stage": stage,
        "next_stage": next_stage,
        "portfolio_action": None,
    }
    mismatched = [
        field for field, expected in expected_values.items() if payload.get(field) != expected
    ]
    if mismatched:
        raise ResearchAllocationError(
            f"sealed {stage} selection conflicts at {', '.join(mismatched)}"
        )
    for field in ("cohort_count", "eligible_count", "selected_count"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ResearchAllocationError(
                f"sealed {stage} selection {field} must be a non-negative integer"
            )
    ranking = payload.get("ranking")
    if not isinstance(ranking, list):
        raise ResearchAllocationError(f"sealed {stage} selection ranking is invalid")
    symbols: set[str] = set()
    selected_count = 0
    for row in ranking:
        if not isinstance(row, Mapping):
            raise ResearchAllocationError(f"sealed {stage} selection row is invalid")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not re.fullmatch(r"CN:[0-9]{6}", symbol):
            raise ResearchAllocationError(f"sealed {stage} selection symbol is invalid")
        if symbol in symbols:
            raise ResearchAllocationError(
                f"sealed {stage} selection has duplicate symbol: {symbol}"
            )
        symbols.add(symbol)
        if not isinstance(row.get("selected"), bool):
            raise ResearchAllocationError(
                f"sealed {stage} selection selected flag is invalid: {symbol}"
            )
        selected_count += int(row["selected"])
    if len(ranking) != payload["eligible_count"]:
        raise ResearchAllocationError(
            f"sealed {stage} selection ranking does not match eligible_count"
        )
    if selected_count != payload["selected_count"]:
        raise ResearchAllocationError(
            f"sealed {stage} selection ranking does not match selected_count"
        )
    budget = payload.get("next_stage_effort_budget_hours")
    if budget is not None and (
        isinstance(budget, bool) or not isinstance(budget, (int, float)) or budget <= 0
    ):
        raise ResearchAllocationError(
            f"sealed {stage} selection next-stage budget is invalid"
        )


def _materialize_profile_selection(
    *,
    screening: list[dict[str, Any]],
    queue: list[dict[str, Any]],
    payload: Mapping[str, Any],
    cycle: str,
    stage: str,
    next_stage: str,
    next_binding_field: str,
    selection_path: str,
    selection_sha256: str,
    budget: float | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, bool]:
    """Repair only absent selection materialization without regressing later work."""

    screen_by_symbol = {item.get("symbol"): dict(item) for item in screening}
    queue_by_symbol = {item.get("symbol"): dict(item) for item in queue}
    screening_changed = False
    queue_changed = False
    expected_evidence = [
        f"stage_selection:{selection_path}",
        f"stage_selection_sha256:{selection_sha256}",
    ]
    evidence_proof = set(expected_evidence)

    for row in payload["ranking"]:
        symbol = str(row["symbol"])
        if symbol not in screen_by_symbol or symbol not in queue_by_symbol:
            raise ResearchAllocationError(
                f"sealed {stage} selection references a missing coverage row: {symbol}"
            )
        original_queue = queue_by_symbol[symbol]
        original_screen = screen_by_symbol[symbol]
        queued = dict(original_queue)
        screen = dict(original_screen)
        completed_stage = _history_completed(queued, stage)
        if not completed_stage:
            raise ResearchAllocationError(
                f"sealed {stage} selection lacks completed stage history: {symbol}"
            )
        current_cycle = queued.get("profile_cycle_id")
        if isinstance(current_cycle, str) and current_cycle != cycle:
            # A later cycle owns the mutable queue and screening rows now.
            continue

        existing_binding = queued.get(next_binding_field)
        if existing_binding is not None and existing_binding != selection_path:
            raise ResearchAllocationError(
                f"sealed {stage} selection conflicts at {next_binding_field}: {symbol}"
            )
        screen_evidence = screen.get("evidence")
        evidence = list(screen_evidence) if isinstance(screen_evidence, list) else []
        screen_proves_selection = evidence_proof.issubset(set(evidence))
        base_state = bool(
            current_cycle == cycle
            and queued.get("task_type") == stage
            and queued.get("status") == "completed"
        )
        next_stage_state = queued.get("task_type") == next_stage
        completed_followup = bool(
            queued.get("task_type") == "targeted_followup"
            and queued.get("status") == "completed"
            and _history_completed(queued, "targeted_followup")
        )
        candidate_outcome = (
            "profile_candidate" if stage == "quick_profile" else "deep_candidate"
        )
        completed_outcome = _history_completed_outcome(
            queued, "targeted_followup" if completed_followup else stage
        )
        preserve_outcome = bool(
            completed_outcome in TERMINAL_STAGES
            and completed_outcome != candidate_outcome
        )
        later_progress = bool(
            _history_completed(queued, next_stage)
            or (
                queued.get("task_type") not in {stage, next_stage}
                and queued.get("task_type") in RESEARCH_STAGES
            )
        )
        selected = row["selected"] is True

        if selected:
            if base_state:
                if budget is None:
                    raise ResearchAllocationError(
                        f"sealed {stage} selection predates recoverable budget binding: "
                        f"{symbol}"
                    )
                queued.update(
                    {
                        "task_type": next_stage,
                        "status": "pending",
                        "assigned_agent": None,
                        "started_at": None,
                        "finished_at": None,
                        "failure_reason": None,
                        "reason": (
                            f"完整{stage}批次横向比较后获得{next_stage}预算。"
                        ),
                        "next_action": _next_action(next_stage, False),
                        "effort_budget_hours": budget,
                        "preceding_stage": stage,
                        "stop_conditions": _stop_conditions(next_stage),
                        next_binding_field: selection_path,
                    }
                )
                if not screen_proves_selection:
                    screen.update(
                        {
                            "decision": next_stage,
                            "reason": (
                                f"完整{stage}批次横向比较后获得{next_stage}预算。"
                            ),
                            "evidence": list(dict.fromkeys(evidence + expected_evidence)),
                            "next_action": _next_action(next_stage, False),
                        }
                    )
            elif next_stage_state or later_progress:
                # Only add the immutable selection binding. Claim, completion,
                # or deeper-stage fields and conclusions belong to later work.
                queued[next_binding_field] = selection_path
                safe_pending_state = bool(
                    next_stage_state
                    and queued.get("status") == "pending"
                    and queued.get("assigned_agent") is None
                    and not _history_completed(queued, next_stage)
                )
                if safe_pending_state and not screen_proves_selection:
                    screen.update(
                        {
                            "decision": next_stage,
                            "reason": (
                                f"完整{stage}批次横向比较后获得{next_stage}预算。"
                            ),
                            "evidence": list(dict.fromkeys(evidence + expected_evidence)),
                            "next_action": _next_action(next_stage, False),
                        }
                    )
            else:
                raise ResearchAllocationError(
                    f"sealed {stage} selection cannot safely repair queue state: {symbol}"
                )
        elif base_state or completed_followup or existing_binding == selection_path:
            queued[next_binding_field] = selection_path
            if preserve_outcome:
                # A profile or follow-up may already have produced a stronger
                # terminal conclusion such as price_watch or conditional_stop.
                # Bind the allocation decision without regressing that result.
                queued["next_action"] = _next_action(completed_outcome, False)
                screen.update(
                    {
                        "decision": completed_outcome,
                        "reason": _screening_reason(completed_outcome, False),
                        "evidence": list(
                            dict.fromkeys(evidence + expected_evidence)
                        ),
                        "next_action": _next_action(completed_outcome, False),
                    }
                )
            else:
                if base_state:
                    queued["next_action"] = (
                        "等待结构化触发器或下一周期重新竞争研究预算。"
                    )
                if not screen_proves_selection:
                    screen.update(
                        {
                            "decision": "catalog",
                            "reason": (
                                f"{stage}支持继续研究，但横向比较后未获得本周期"
                                f"{next_stage}容量。"
                            ),
                            "evidence": list(
                                dict.fromkeys(evidence + expected_evidence)
                            ),
                            "next_action": "等待结构化触发器或下一周期重新竞争研究预算。",
                        }
                    )
        else:
            raise ResearchAllocationError(
                f"sealed {stage} defer decision cannot safely repair queue state: {symbol}"
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


def _profile_stage_config(stage: str) -> dict[str, str]:
    configs = {
        "quick_profile": {
            "binding_field": "triage_selection_path",
            "next_stage": "scoped_research",
            "next_binding_field": "profile_quick_selection_path",
            "select_decision": "select_scoped_research",
            "comparison_name": "quick-profile-comparison.json",
            "selection_name": "quick-profile-selection.json",
        },
        "scoped_research": {
            "binding_field": "profile_quick_selection_path",
            "next_stage": "deep_research",
            "next_binding_field": "profile_scoped_selection_path",
            "select_decision": "select_deep_research",
            "comparison_name": "scoped-research-comparison.json",
            "selection_name": "scoped-research-selection.json",
        },
    }
    if stage not in configs:
        raise ResearchAllocationError(
            "profile comparison stage must be quick_profile or scoped_research"
        )
    return configs[stage]


def _complete_profile_cohort(
    queue: list[dict[str, Any]],
    *,
    repository_root: Path,
    cycle: str,
    stage: str,
) -> tuple[str, str, str, list[dict[str, Any]]]:
    anchors = []
    for item in queue:
        if item.get("profile_cycle_id") != cycle or not _history_completed(item, stage):
            continue
        binding = _profile_predecessor_binding(item, stage=stage)
        if binding is not None:
            anchors.append(binding)
    if not anchors:
        raise ResearchAllocationError(
            f"no recorded {stage} cohort is available for cycle: {cycle}"
        )
    bindings = set(anchors)
    if len(bindings) != 1:
        raise ResearchAllocationError(
            f"{stage} cycle spans multiple predecessor selections"
        )
    binding_field, binding = next(iter(bindings))
    binding_path = repository_root / binding
    if not binding_path.exists():
        raise ResearchAllocationError(
            f"sealed predecessor selection is required for {stage}: {binding}"
        )
    sealed_binding = verify_sealed(binding_path)
    cohort = _bound_profile_cohort(
        queue,
        repository_root=repository_root,
        binding_field=binding_field,
        binding=binding,
        stage=stage,
    )
    incomplete = [
        item["symbol"]
        for item in cohort
        if item.get("profile_cycle_id") != cycle
        or not _history_completed(item, stage)
        or (
            item.get("task_type") == "targeted_followup"
            and item.get("preceding_stage") == stage
            and item.get("status") in {"pending", "running"}
        )
    ]
    if incomplete:
        raise ResearchAllocationError(
            "completion-order promotion is forbidden; "
            f"{stage} cohort is incomplete: {incomplete[:10]}"
        )
    predecessor = json.loads(binding_path.read_text(encoding="utf-8"))
    order = _profile_predecessor_order(
        predecessor,
        artifact_type=sealed_binding.artifact_type,
        stage=stage,
    )
    by_symbol = {item["symbol"]: item for item in cohort}
    if len(order) != len(set(order)) or set(order) != set(by_symbol):
        raise ResearchAllocationError(
            f"{stage} cohort does not match sealed predecessor selection"
        )
    return (
        binding_field,
        binding,
        sealed_binding.sha256,
        [by_symbol[str(symbol)] for symbol in order],
    )


def _profile_predecessor_binding(
    item: Mapping[str, Any], *, stage: str
) -> tuple[str, str] | None:
    fields = (
        ("manager_screen_result_path", "triage_selection_path")
        if stage == "quick_profile"
        else ("profile_quick_selection_path",)
    )
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value:
            return field, value
    return None


def _profile_predecessor_order(
    payload: Mapping[str, Any], *, artifact_type: str, stage: str
) -> list[str]:
    if stage == "quick_profile" and artifact_type == "manager_screen_result":
        decisions = payload.get("decisions")
        if not isinstance(decisions, list):
            raise ResearchAllocationError("manager-screen predecessor decisions are invalid")
        return [
            str(row["symbol"])
            for row in decisions
            if isinstance(row, Mapping)
            and row.get("route") == "send_to_analyst"
            and isinstance(row.get("symbol"), str)
        ]

    ranking = payload.get("ranking")
    if not isinstance(ranking, list):
        raise ResearchAllocationError("predecessor selection ranking is invalid")
    selected_key = (
        "selected_for_quick_profile" if stage == "quick_profile" else "selected"
    )
    return [
        str(row["symbol"])
        for row in ranking
        if isinstance(row, Mapping)
        and row.get(selected_key) is True
        and isinstance(row.get("symbol"), str)
    ]


def _profile_comparison_row(
    item: Mapping[str, Any],
    *,
    ordinal: int,
    cycle: str,
    stage: str,
    repository_root: Path,
) -> dict[str, Any]:
    symbol = str(item["symbol"])
    profile_relative = _latest_history_path(item, "result_path")
    evaluation_relative = _latest_history_path(item, "evaluation_path")
    if not profile_relative or not evaluation_relative:
        raise ResearchAllocationError(f"profile stage artifacts are missing: {symbol}")
    profile_path = repository_root / profile_relative
    evaluation_path = repository_root / evaluation_relative
    sealed_profile = verify_sealed(profile_path)
    sealed_evaluation = verify_sealed(evaluation_path)
    if sealed_profile.artifact_type != "quick_profile_package":
        raise ResearchAllocationError(f"profile package type is invalid: {symbol}")
    if sealed_evaluation.artifact_type != "quick_profile_evaluation":
        raise ResearchAllocationError(f"profile evaluation type is invalid: {symbol}")
    package = json.loads(profile_path.read_text(encoding="utf-8"))
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    profile = package.get("profile")
    analysis = package.get("analysis")
    evaluated = evaluation.get("evaluation")
    if (
        package.get("cycle_id") != cycle
        or not isinstance(profile, Mapping)
        or profile.get("symbol") != symbol
        or profile.get("research_stage") != stage
        or evaluation.get("cycle_id") != cycle
        or evaluation.get("symbol") != symbol
        or not isinstance(analysis, Mapping)
        or not isinstance(evaluated, Mapping)
    ):
        raise ResearchAllocationError(
            f"profile comparison artifact identity is invalid: {symbol}"
        )
    provenance = package.get("provenance")
    sources = package.get("sources")
    return {
        "ordinal": ordinal,
        "symbol": symbol,
        "name": item.get("name"),
        "evaluated_stage": stage,
        "current_next_stage": evaluated.get("next_stage"),
        "evaluation_reason_codes": evaluated.get("reason_codes") or [],
        "profile": dict(profile),
        "analysis": dict(analysis),
        "source_count": len(sources) if isinstance(sources, list) else 0,
        "profile_path": profile_relative,
        "profile_sha256": sealed_profile.sha256,
        "evaluation_path": evaluation_relative,
        "evaluation_sha256": sealed_evaluation.sha256,
        "research_agent": (
            provenance.get("agent") if isinstance(provenance, Mapping) else None
        ),
    }


def _normalize_profile_decision_package(
    package: Mapping[str, Any],
    *,
    cycle: str,
    stage: str,
    comparison_sha256: str,
    comparison_rows: list[Mapping[str, Any]],
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    if (
        not isinstance(package, Mapping)
        or set(package) != PROFILE_DECISION_PACKAGE_KEYS
    ):
        raise ResearchAllocationError(
            "profile allocation Agent decision fields do not match contract"
        )
    if package.get("schema_version") != 1:
        raise ResearchAllocationError(
            "profile allocation Agent decision schema_version must be 1"
        )
    if package.get("cycle_id") != cycle or package.get("evaluated_stage") != stage:
        raise ResearchAllocationError(
            "profile allocation Agent decisions target the wrong cohort"
        )
    if package.get("comparison_sha256") != comparison_sha256:
        raise ResearchAllocationError(
            "profile allocation Agent decisions are not bound to the comparison"
        )
    provenance = package.get("provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != PROVENANCE_KEYS:
        raise ResearchAllocationError(
            "profile allocation Agent decision provenance is invalid"
        )
    generated_at = _datetime(
        provenance.get("generated_at"), "decision.provenance.generated_at"
    )
    if generated_at > finalized_at:
        raise ResearchAllocationError(
            "profile allocation Agent decisions cannot be generated in the future"
        )
    config = _profile_stage_config(stage)
    allowed = {config["select_decision"], "defer"}
    decisions = package.get("decisions")
    if not isinstance(decisions, list):
        raise ResearchAllocationError(
            "profile allocation Agent decisions must be an array"
        )
    by_symbol: dict[str, dict[str, Any]] = {}
    for raw in decisions:
        if not isinstance(raw, Mapping) or set(raw) != PROFILE_DECISION_KEYS:
            raise ResearchAllocationError(
                "one profile allocation Agent decision does not match contract"
            )
        symbol = _text(raw.get("symbol"), "decision.symbol")
        if not re.fullmatch(r"CN:[0-9]{6}", symbol):
            raise ResearchAllocationError("profile allocation decision symbol is invalid")
        if symbol in by_symbol:
            raise ResearchAllocationError(
                f"duplicate profile allocation Agent decision: {symbol}"
            )
        decision = _text(raw.get("decision"), "decision.decision")
        if decision not in allowed:
            raise ResearchAllocationError(
                f"unsupported profile allocation decision: {decision}"
            )
        by_symbol[symbol] = {
            "symbol": symbol,
            "decision": decision,
            "reason": _text(raw.get("reason"), "decision.reason"),
            "decisive_question": _text(
                raw.get("decisive_question"), "decision.decisive_question"
            ),
            "counterevidence_considered": _text_array(
                raw.get("counterevidence_considered"),
                "decision.counterevidence_considered",
                allow_empty=False,
            ),
        }
    symbols = [_text(row.get("symbol"), "comparison.symbol") for row in comparison_rows]
    if len(symbols) != len(set(symbols)):
        raise ResearchAllocationError("profile comparison rows contain duplicates")
    if set(by_symbol) != set(symbols):
        missing = sorted(set(symbols) - set(by_symbol))
        extra = sorted(set(by_symbol) - set(symbols))
        raise ResearchAllocationError(
            "profile allocation Agent decisions must cover every comparison row "
            f"exactly once; missing={missing}, extra={extra}"
        )
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "evaluated_stage": stage,
        "comparison_sha256": comparison_sha256,
        "decisions": [by_symbol[symbol] for symbol in symbols],
        "provenance": {
            "agent": _text(provenance.get("agent"), "decision.provenance.agent"),
            "model": _text(provenance.get("model"), "decision.provenance.model"),
            "tools": _text_array(
                provenance.get("tools"),
                "decision.provenance.tools",
                allow_empty=False,
            ),
            "generated_at": generated_at.isoformat(),
        },
    }


def _profile_comparison_result(
    payload: Mapping[str, Any],
    *,
    comparison_path: str,
    comparison_sha256: str,
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "cycle_id": payload["cycle_id"],
        "evaluated_stage": payload["evaluated_stage"],
        "next_stage": payload["next_stage"],
        "cohort_count": payload["cohort_count"],
        "comparison_path": comparison_path,
        "comparison_sha256": comparison_sha256,
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _profile_selection_result(
    payload: Mapping[str, Any],
    *,
    selection_path: str,
    selection_sha256: str,
    idempotent: bool,
) -> dict[str, Any]:
    selected_symbols = [
        item["symbol"] for item in payload["ranking"] if item["selected"] is True
    ]
    return {
        "schema_version": 1,
        "cycle_id": payload["cycle_id"],
        "evaluated_stage": payload["evaluated_stage"],
        "next_stage": payload["next_stage"],
        "cohort_count": payload["cohort_count"],
        "eligible_count": payload["eligible_count"],
        "selected_count": payload["selected_count"],
        "selected_symbols": selected_symbols,
        "selection_path": selection_path,
        "selection_sha256": selection_sha256,
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def profile_cycle_status(*, root: str | Path, cycle_id: str) -> dict[str, Any]:
    """Return a verified progress snapshot for one profile allocation cycle."""

    cycle = _text(cycle_id, "cycle_id")
    if not CYCLE_RE.fullmatch(cycle):
        raise ResearchAllocationError("cycle_id is invalid")
    base = Path(root)
    repository_root = base.parent.parent
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    screening = read_jsonl(base / SCREENING_FILE)
    recorded = [item for item in queue if item.get("profile_cycle_id") == cycle]
    allocation_shas = {
        item.get("allocation_sha256")
        for item in recorded
        if item.get("allocation_sha256") is not None
    }
    if len(allocation_shas) > 1:
        raise ResearchAllocationError("profile cycle spans multiple allocations")
    allocation_sha = next(iter(allocation_shas), None)
    quick_profile_bindings = {
        binding
        for item in recorded
        if (binding := _profile_predecessor_binding(item, stage="quick_profile"))
        is not None
    }
    if len(quick_profile_bindings) == 1:
        binding_field, binding_path = next(iter(quick_profile_bindings))
        cohort = _bound_profile_cohort(
            queue,
            repository_root=repository_root,
            binding_field=binding_field,
            binding=binding_path,
            stage="quick_profile",
        )
    else:
        cohort = (
            [
                item
                for item in queue
                if item.get("allocation_sha256") == allocation_sha
                and bool(item.get("selected_by"))
            ]
            if allocation_sha is not None
            else recorded
        )
    recorded_symbols = {item["symbol"] for item in recorded}
    screening_by_symbol = {item.get("symbol"): item for item in screening}
    stage_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    invalid: list[dict[str, str]] = []
    for item in recorded:
        status = str(item.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1
        screen = screening_by_symbol.get(item["symbol"])
        stage = str(screen.get("decision")) if isinstance(screen, Mapping) else "missing"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        for label, relative_path in (
            ("profile", _latest_history_path(item, "result_path")),
            ("evaluation", _latest_history_path(item, "evaluation_path")),
        ):
            if not isinstance(relative_path, str) or not relative_path:
                invalid.append({"symbol": item["symbol"], "error": f"{label}_path_missing"})
                continue
            try:
                verify_sealed(repository_root / relative_path)
            except ValueError as exc:
                invalid.append({"symbol": item["symbol"], "error": f"{label}:{exc}"})
    stage_gates: dict[str, dict[str, Any]] = {}
    for stage in ("quick_profile", "scoped_research"):
        config = _profile_stage_config(stage)
        comparison_path = base / "profiles" / cycle / config["comparison_name"]
        selection_path = base / "profiles" / cycle / config["selection_name"]
        comparison_sealed = False
        selection_finalized = False
        if comparison_path.exists():
            try:
                sealed = verify_sealed(comparison_path)
                comparison_sealed = sealed.artifact_type == f"{stage}_comparison_packet"
                if not comparison_sealed:
                    invalid.append(
                        {
                            "symbol": "__cycle__",
                            "error": f"{stage}_comparison_artifact_type",
                        }
                    )
            except ValueError as exc:
                invalid.append(
                    {"symbol": "__cycle__", "error": f"{stage}_comparison:{exc}"}
                )
        if selection_path.exists():
            try:
                sealed = verify_sealed(selection_path)
                selection_finalized = (
                    sealed.artifact_type == f"{stage}_cross_company_selection"
                )
                if not selection_finalized:
                    invalid.append(
                        {
                            "symbol": "__cycle__",
                            "error": f"{stage}_selection_artifact_type",
                        }
                    )
            except ValueError as exc:
                invalid.append(
                    {"symbol": "__cycle__", "error": f"{stage}_selection:{exc}"}
                )
        stage_gates[stage] = {
            "comparison_sealed": comparison_sealed,
            "selection_finalized": selection_finalized,
        }
    remaining_count = len({item["symbol"] for item in cohort} - recorded_symbols)
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "allocation_sha256": allocation_sha,
        "cohort_count": len(cohort),
        "recorded_count": len(recorded),
        "remaining_count": remaining_count,
        "by_next_stage": dict(sorted(stage_counts.items())),
        "by_queue_status": dict(sorted(status_counts.items())),
        "comparison_ready": remaining_count == 0 and not invalid,
        "stage_gates": stage_gates,
        "invalid_artifact_count": len(invalid),
        "invalid_artifacts": invalid,
    }


def _bound_profile_cohort(
    queue: list[dict[str, Any]],
    *,
    repository_root: Path,
    binding_field: str,
    binding: str,
    stage: str,
) -> list[dict[str, Any]]:
    """Return only companies selected by the sealed predecessor decision.

    Historical stage records are useful for determining whether a selected
    company has completed the current layer, but they must not pull a company
    that lost the current predecessor comparison back into the cohort.
    """

    cohort = [
        item
        for item in queue
        if item.get(binding_field) == binding
        and (
            item.get("task_type") == stage
            or _history_completed(item, stage)
        )
    ]
    selection_path = repository_root / binding
    if not selection_path.exists():
        # Backward compatibility for legacy queues whose predecessor selection
        # was not stored as a sealed repository asset.
        return cohort
    sealed = verify_sealed(selection_path)
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    selected_symbols = set(
        _profile_predecessor_order(
            payload,
            artifact_type=sealed.artifact_type,
            stage=stage,
        )
    )
    if not selected_symbols:
        raise ResearchAllocationError(
            f"predecessor selection has no selected companies for {stage}"
        )
    return [item for item in cohort if item.get("symbol") in selected_symbols]


def _validate_package(
    package: Mapping[str, Any], *, recorded_at: dt.datetime
) -> dict[str, Any]:
    _reject_probable_gbk_mojibake(package)
    if not isinstance(package, Mapping) or set(package) != PACKAGE_KEYS:
        raise ResearchAllocationError("profile package fields do not match contract")
    if package.get("schema_version") != 2:
        raise ResearchAllocationError("profile package schema_version must be 2")
    cycle_id = _text(package.get("cycle_id"), "cycle_id")
    if not CYCLE_RE.fullmatch(cycle_id):
        raise ResearchAllocationError("cycle_id is invalid")
    company_name = _text(package.get("company_name"), "company_name")
    profile = package.get("profile")
    if not isinstance(profile, Mapping):
        raise ResearchAllocationError("profile must be an object")

    provenance = package.get("provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != PROVENANCE_KEYS:
        raise ResearchAllocationError("profile provenance fields do not match contract")
    generated_at = _datetime(provenance.get("generated_at"), "generated_at")
    if generated_at > recorded_at:
        raise ResearchAllocationError("profile generated_at cannot be after recorded_at")
    tools = _text_array(provenance.get("tools"), "tools", allow_empty=False)
    normalized_provenance = {
        "agent": _text(provenance.get("agent"), "agent"),
        "model": _text(provenance.get("model"), "model"),
        "tools": tools,
        "generated_at": generated_at.isoformat(),
    }

    sources = package.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ResearchAllocationError("profile sources must be a non-empty array")
    normalized_sources: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for raw in sources:
        source = _validate_source(raw, recorded_at=recorded_at)
        source_id = source["source_id"]
        if source_id in source_ids:
            raise ResearchAllocationError(f"duplicate profile source_id: {source_id}")
        source_ids.add(source_id)
        normalized_sources.append(source)
    s1_count = sum(1 for source in normalized_sources if source["tier"] == "S1")
    if profile.get("s1_source_count") != s1_count:
        raise ResearchAllocationError("profile s1_source_count does not match sources")

    analysis = package.get("analysis")
    if not isinstance(analysis, Mapping) or set(analysis) != ANALYSIS_KEYS:
        raise ResearchAllocationError("profile analysis fields do not match contract")
    normalized_analysis: dict[str, Any] = {}
    for section in sorted(ANALYSIS_KEYS):
        raw = analysis.get(section)
        if not isinstance(raw, Mapping) or set(raw) != ANALYSIS_ITEM_KEYS:
            raise ResearchAllocationError(f"analysis.{section} fields do not match contract")
        referenced = _text_array(
            raw.get("source_ids"),
            f"analysis.{section}.source_ids",
            allow_empty=False,
        )
        unknown = set(referenced) - source_ids
        if unknown:
            raise ResearchAllocationError(
                f"analysis.{section} references unknown sources: {sorted(unknown)}"
            )
        normalized_analysis[section] = {
            "conclusion": _text(raw.get("conclusion"), f"analysis.{section}.conclusion"),
            "source_ids": referenced,
        }

    price_as_of = _datetime(package.get("price_as_of"), "price_as_of")
    if price_as_of > recorded_at:
        raise ResearchAllocationError("price_as_of cannot be after recorded_at")
    if recorded_at - price_as_of > dt.timedelta(days=7):
        raise ResearchAllocationError("profile price is older than seven days")
    price_source_id = _text(package.get("price_source_id"), "price_source_id")
    if price_source_id not in source_ids:
        raise ResearchAllocationError("price_source_id does not reference a source")
    information_cutoff = _datetime(profile.get("information_cutoff"), "information_cutoff")
    if information_cutoff > recorded_at:
        raise ResearchAllocationError("information_cutoff cannot be after recorded_at")
    as_of = _date(profile.get("as_of"), "as_of")
    if as_of > recorded_at.date():
        raise ResearchAllocationError("profile as_of cannot be after recorded_at")
    if information_cutoff.date() > as_of:
        raise ResearchAllocationError("information_cutoff date cannot be after profile as_of")
    if price_as_of > information_cutoff:
        raise ResearchAllocationError("price_as_of cannot be after information_cutoff")
    if generated_at < information_cutoff:
        raise ResearchAllocationError("profile generated_at cannot precede information_cutoff")

    return {
        "schema_version": 2,
        "cycle_id": cycle_id,
        "company_name": company_name,
        "profile": dict(profile),
        "price_as_of": price_as_of.isoformat(),
        "price_source_id": price_source_id,
        "provenance": normalized_provenance,
        "analysis": normalized_analysis,
        "sources": normalized_sources,
    }


def _reject_probable_gbk_mojibake(value: Any, *, path: str = "package") -> None:
    """Reject GBK bytes accidentally decoded as Latin-1 before sealing a package."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_probable_gbk_mojibake(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_probable_gbk_mojibake(child, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return

    latin1_count = sum(0x80 <= ord(char) <= 0xFF for char in value)
    if latin1_count < 4:
        return
    try:
        decoded = value.encode("latin-1").decode("gb18030")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return
    cjk_count = sum("\u4e00" <= char <= "\u9fff" for char in decoded)
    if cjk_count >= 2 and cjk_count >= len(decoded) // 5:
        raise ResearchAllocationError(
            f"profile package contains probable GBK/Latin-1 mojibake at {path}"
        )


def _claimed_task_payload(record: Mapping[str, Any], *, idempotent: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "symbol": record.get("symbol"),
        "name": record.get("name"),
        "task_type": record.get("task_type"),
        "assigned_agent": record.get("assigned_agent"),
        "started_at": record.get("started_at"),
        "effort_budget_hours": record.get("effort_budget_hours"),
        "selected_by": record.get("selected_by") or [],
        "target_company_dir": record.get("target_company_dir"),
        "stop_conditions": record.get("stop_conditions") or [],
        "result_path": record.get("result_path"),
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _validate_source(raw: Any, *, recorded_at: dt.datetime) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != SOURCE_KEYS:
        raise ResearchAllocationError("profile source fields do not match contract")
    source_id = _text(raw.get("source_id"), "source_id")
    if not SOURCE_ID_RE.fullmatch(source_id):
        raise ResearchAllocationError(f"invalid source_id: {source_id}")
    tier = _text(raw.get("tier"), f"{source_id}.tier")
    if tier not in SOURCE_TIERS:
        raise ResearchAllocationError(f"invalid source tier: {tier}")
    accessed_at = _datetime(raw.get("accessed_at"), f"{source_id}.accessed_at")
    if accessed_at > recorded_at:
        raise ResearchAllocationError(f"source accessed_at is after recorded_at: {source_id}")
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
        raise ResearchAllocationError(f"source requires url or local_path: {source_id}")
    published_at = raw.get("published_at")
    if published_at is not None:
        published_at = _text(published_at, f"{source_id}.published_at")
    return {
        "source_id": source_id,
        "tier": tier,
        "title": _text(raw.get("title"), f"{source_id}.title"),
        "publisher": _text(raw.get("publisher"), f"{source_id}.publisher"),
        "published_at": published_at,
        "accessed_at": accessed_at.isoformat(),
        "url": url,
        "local_path": local_path,
        "supports": _text_array(raw.get("supports"), f"{source_id}.supports", allow_empty=False),
    }


def _one_record(records: list[dict[str, Any]], symbol: str, label: str) -> dict[str, Any]:
    matches = [item for item in records if item.get("symbol") == symbol]
    if len(matches) != 1:
        raise ResearchAllocationError(f"expected exactly one {label} record: {symbol}")
    return matches[0]


def _latest_history_path(record: Mapping[str, Any], key: str) -> str | None:
    history = record.get("stage_history")
    if not isinstance(history, list) or not history:
        return None
    latest = history[-1]
    if not isinstance(latest, Mapping):
        return None
    value = latest.get(key)
    return value if isinstance(value, str) else None


def _validate_local_sources(
    sources: list[dict[str, Any]], *, repository_root: Path
) -> None:
    root = repository_root.resolve()
    for source in sources:
        local_path = source.get("local_path")
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


def _stage_capacity(policy: Mapping[str, Any], stage: str) -> int | None:
    if stage == "targeted_followup":
        return None
    capacities = policy.get("stage_capacity_per_cycle")
    if not isinstance(capacities, Mapping):
        raise ResearchAllocationError("stage capacity policy is invalid")
    value = capacities.get(stage)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResearchAllocationError(f"stage capacity is invalid: {stage}")
    return value


def _effort_budget(policy: Mapping[str, Any], stage: str) -> float:
    budgets = policy.get("effort_budget_hours")
    if not isinstance(budgets, Mapping):
        raise ResearchAllocationError("effort budget policy is invalid")
    value = budgets.get(stage)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ResearchAllocationError(f"effort budget is invalid: {stage}")
    return float(value)


def _screening_reason(stage: str, capacity_wait: bool) -> str:
    if capacity_wait:
        return f"画像支持进入{stage}，但本周期容量已满，进入可恢复等待队列。"
    reasons = {
        "profile_candidate": (
            "正式画像发现可信投资路径，等待完整同层批次横向比较范围研究预算。"
        ),
        "deep_candidate": (
            "范围研究通过证据与粗估值门槛，等待完整同层批次横向比较深研预算。"
        ),
        "targeted_followup": "画像只支持补齐少数决定性证据，暂不扩张研究范围。",
        "scoped_research": "画像发现可信投资路径，追加有限范围研究预算。",
        "deep_research": "范围研究通过证据与粗估值门槛，追加完整深研预算。",
        "price_watch": "公司可能可投，但当前价格不支持继续购买研究预算。",
        "reassign_or_stop": "当前 agent 能力圈不足，转派专门能力或暂停。",
        "conditional_stop": "可靠证据触发结构化停止条件。",
    }
    return reasons[stage]


def _next_action(stage: str, capacity_wait: bool) -> str:
    if capacity_wait:
        return "下一研究周期释放容量后，按画像价值排序重新竞争预算。"
    actions = {
        "profile_candidate": (
            "等待完整正式画像批次封存后统一比较，不得按完成顺序晋级。"
        ),
        "deep_candidate": (
            "等待完整范围研究批次封存后统一比较，不得按完成顺序晋级。"
        ),
        "targeted_followup": "只补画像列出的一个或少数决定性证据缺口。",
        "scoped_research": "在4小时预算内解决一至三个决定性未知数。",
        "deep_research": "按完整公司研究协议重建业务、会计、正常化盈利和估值。",
        "price_watch": "按价格、财报、事件或论点触发器重新评估。",
        "reassign_or_stop": "转派具备相应行业能力的独立 agent；无法转派则暂停。",
        "conditional_stop": "仅在结构化重启条件发生时恢复研究。",
    }
    return actions[stage]


def _stop_conditions(stage: str) -> list[str]:
    values = {
        "targeted_followup": ["决定性证据无法由公开来源补齐", "补证后投资路径不成立"],
        "scoped_research": ["正常化盈利无法建立", "基准回报低于10%", "治理或生存测试不通过"],
        "deep_research": ["完整证据无法支持12%承保参考回报", "会计、治理或永久损失风险不可承保"],
    }
    return values[stage]


def _history_completed(record: Mapping[str, Any], stage: str) -> bool:
    return any(
        isinstance(item, Mapping)
        and item.get("stage") == stage
        and item.get("status") == "completed"
        for item in (record.get("stage_history") or [])
    )


def _history_completed_outcome(
    record: Mapping[str, Any], stage: str
) -> str | None:
    for item in reversed(record.get("stage_history") or []):
        if (
            isinstance(item, Mapping)
            and item.get("stage") == stage
            and item.get("status") == "completed"
            and isinstance(item.get("next_stage"), str)
        ):
            return str(item["next_stage"])
    return None


def _profile_priority_score(
    profile: Mapping[str, Any], *, priority: int
) -> int:
    """Use coarse buckets to rank research value without fake valuation precision."""

    base_return = float(profile["valuation"]["base_expected_annual_return"])
    earnings_plausible = profile["normalized_earnings_status"] == "plausible"
    if not earnings_plausible:
        return_bucket = 0
    elif base_return >= 0.15:
        return_bucket = 3
    elif base_return >= 0.12:
        return_bucket = 2
    elif base_return >= 0.10:
        return_bucket = 1
    else:
        return_bucket = 0
    source_bucket = 2 if int(profile["s1_source_count"]) >= 3 else 1
    unknown_count = len(profile["decisive_unknowns"])
    resolvability_bucket = (
        2 if unknown_count == 1 else 1 if unknown_count <= 3 else 0
    )
    priority_bucket = max(0, 6 - priority)
    return (
        return_bucket * 100
        + source_bucket * 10
        + resolvability_bucket * 3
        + priority_bucket
    )


def _validate_industry_evidence(
    package: Mapping[str, Any],
    *,
    queue_record: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> None:
    requirements = policy.get("industry_evidence_requirements")
    if not isinstance(requirements, Mapping):
        raise ResearchAllocationError("industry evidence policy is invalid")
    cluster = str(queue_record.get("economic_risk_cluster") or "")
    cluster_requirements = requirements.get(cluster)
    if cluster_requirements is None:
        return
    if not isinstance(cluster_requirements, Mapping):
        raise ResearchAllocationError(
            f"industry evidence policy is invalid for {cluster}"
        )
    stage = str(package["profile"]["research_stage"])
    required = cluster_requirements.get(stage, [])
    if not isinstance(required, list) or not all(
        isinstance(item, str) and item.strip() for item in required
    ):
        raise ResearchAllocationError(
            f"industry evidence requirements are invalid for {cluster}.{stage}"
        )
    supported = {
        support
        for source in package["sources"]
        if source.get("tier") == "S1"
        for support in source.get("supports", [])
    }
    missing = sorted(set(required) - supported)
    if missing:
        raise ResearchAllocationError(
            f"{cluster} profile lacks required S1 specialist evidence: {missing}"
        )


def _risk_cluster_cap(policy: Mapping[str, Any], stage: str) -> int:
    caps = policy.get("risk_cluster_caps")
    if not isinstance(caps, Mapping):
        raise ResearchAllocationError("risk cluster cap policy is invalid")
    value = caps.get(stage)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResearchAllocationError(f"risk cluster cap is invalid: {stage}")
    return value


def _select_with_risk_cluster_cap(
    ranked: list[Mapping[str, Any]], *, capacity: int, cap: int
) -> tuple[list[Mapping[str, Any]], set[str]]:
    selected: list[Mapping[str, Any]] = []
    counts: dict[str, int] = {}
    capped: set[str] = set()
    for item in ranked:
        cluster = str(item.get("economic_risk_cluster") or "unclassified")
        if counts.get(cluster, 0) >= cap:
            capped.add(str(item["symbol"]))
            continue
        selected.append(item)
        counts[cluster] = counts.get(cluster, 0) + 1
        if len(selected) >= capacity:
            break
    return selected, capped


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchAllocationError(f"{label} must be a non-empty string")
    return value.strip()


def _text_array(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
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
    _require_aware_datetime(parsed, label)
    return parsed


def _date(value: Any, label: str) -> dt.date:
    text = _text(value, label)
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ResearchAllocationError(f"{label} must be an ISO date") from exc


def _require_aware_datetime(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchAllocationError(f"{label} must include timezone information")
