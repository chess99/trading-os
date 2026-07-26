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
    write_jsonl,
)
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


def claim_profile_task(
    *,
    root: str | Path,
    agent: str,
    claimed_at: dt.datetime,
    symbol: str | None = None,
    lens: str | None = None,
) -> dict[str, Any]:
    """Atomically claim one unassigned L2/L3 profile task for one agent."""

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
        in {"quick_profile", "targeted_followup", "scoped_research"}
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
    _validate_local_sources(normalized["sources"], repository_root=base.parent.parent)

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
    if normalized["company_name"] != queue_record.get("name"):
        raise ResearchAllocationError(f"company name does not match queue: {symbol}")
    assigned_agent = queue_record.get("assigned_agent")
    if assigned_agent is not None and assigned_agent != normalized["provenance"]["agent"]:
        raise ResearchAllocationError(
            f"profile provenance agent does not match queue assignment: {symbol}"
        )
    allocation_sha = queue_record.get("allocation_sha256")
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

    timestamp = recorded_at.strftime("%Y%m%dT%H%M%S%z")
    artifact_dir = base / "profiles" / normalized["cycle_id"] / ticker
    profile_path = artifact_dir / f"{timestamp}.profile.json"
    sealed_profile = seal_json(
        profile_path,
        normalized,
        artifact_type="quick_profile_package",
        sealed_at=recorded_at,
    )
    policy_sha = hashlib.sha256(canonical_json_bytes(dict(policy))).hexdigest()
    relative_profile = profile_path.relative_to(base.parent.parent).as_posix()
    evaluation = dict(evaluation)
    next_stage = evaluation["next_stage"]
    if queued_stage == "quick_profile" and next_stage == "scoped_research":
        next_stage = "profile_candidate"
        evaluation["next_stage"] = next_stage
        evaluation["maximum_additional_effort_hours"] = 0.0
        evaluation["reason_codes"] = sorted(
            set(evaluation["reason_codes"])
            | {"awaiting_cross_company_profile_comparison"}
        )
    elif queued_stage == "scoped_research" and next_stage == "deep_research":
        next_stage = "deep_candidate"
        evaluation["next_stage"] = next_stage
        evaluation["maximum_additional_effort_hours"] = 0.0
        evaluation["reason_codes"] = sorted(
            set(evaluation["reason_codes"])
            | {"awaiting_cross_company_deep_research_comparison"}
        )
    if queued_stage == "targeted_followup" and next_stage == "targeted_followup":
        next_stage = "reassign_or_stop"
        evaluation["next_stage"] = next_stage
        evaluation["maximum_additional_effort_hours"] = 0.0
        evaluation["reason_codes"] = sorted(
            set(evaluation["reason_codes"]) | {"targeted_followup_exhausted"}
        )
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
    evaluation_path = artifact_dir / f"{timestamp}.evaluation.json"
    sealed_evaluation = seal_json(
        evaluation_path,
        evaluation_payload,
        artifact_type="quick_profile_evaluation",
        sealed_at=recorded_at,
    )
    relative_evaluation = evaluation_path.relative_to(base.parent.parent).as_posix()

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
    return {
        "schema_version": 2,
        "symbol": symbol,
        "next_stage": next_stage,
        "queue_status": next_status,
        "capacity_wait": capacity_wait,
        "profile_path": relative_profile,
        "profile_sha256": sealed_profile.sha256,
        "evaluation_path": relative_evaluation,
        "evaluation_sha256": sealed_evaluation.sha256,
        "portfolio_action": None,
    }


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

    selection_path = base / "profiles" / cycle / selection_name
    if selection_path.exists():
        verified = verify_sealed(selection_path)
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
        relative = selection_path.relative_to(repository_root).as_posix()
        selected_symbols = [
            item["symbol"] for item in payload["ranking"] if item["selected"]
        ]
        next_binding_field = (
            "profile_quick_selection_path"
            if stage == "quick_profile"
            else "profile_scoped_selection_path"
        )
        queue_by_symbol = {item["symbol"]: item for item in queue}
        if not all(
            queue_by_symbol.get(symbol, {}).get("task_type") == next_stage
            and queue_by_symbol[symbol].get(next_binding_field) == relative
            for symbol in selected_symbols
        ):
            raise ResearchAllocationError(
                f"sealed {stage} selection exists but queue materialization "
                "is incomplete"
            )
        return {
            "schema_version": 1,
            "cycle_id": cycle,
            "evaluated_stage": stage,
            "next_stage": next_stage,
            "cohort_count": payload["cohort_count"],
            "eligible_count": payload["eligible_count"],
            "selected_count": payload["selected_count"],
            "selected_symbols": selected_symbols,
            "selection_path": relative,
            "selection_sha256": verified.sha256,
            "idempotent": True,
            "portfolio_action": None,
        }

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
    cohort = [
        item
        for item in queue
        if item.get(binding_field) == binding
        and (
            item.get("task_type") == stage
            or any(
                isinstance(history, Mapping) and history.get("stage") == stage
                for history in (item.get("stage_history") or [])
            )
        )
    ]
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
    selected = ranked[:capacity]
    selected_symbols = {item["symbol"] for item in selected}
    rows = [
        {
            "rank": rank,
            "symbol": item["symbol"],
            "name": item["name"],
            "research_priority_score": item.get("profile_priority_score", 0),
            "selected": item["symbol"] in selected_symbols,
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
    queue_by_symbol = {item["symbol"]: dict(item) for item in queue}
    next_binding_field = (
        "profile_quick_selection_path"
        if stage == "quick_profile"
        else "profile_scoped_selection_path"
    )
    for item in ranked:
        symbol = item["symbol"]
        queued = queue_by_symbol[symbol]
        screen = screen_by_symbol[symbol]
        if symbol in selected_symbols:
            screen.update(
                {
                    "decision": next_stage,
                    "reason": (
                        f"完整{stage}批次横向比较后获得{next_stage}预算。"
                    ),
                    "evidence": list(screen.get("evidence") or [])
                    + [
                        f"stage_selection:{relative_selection}",
                        f"stage_selection_sha256:{sealed.sha256}",
                    ],
                    "next_action": _next_action(next_stage, False),
                }
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
                    "effort_budget_hours": float(budget),
                    "preceding_stage": stage,
                    "stop_conditions": _stop_conditions(next_stage),
                    next_binding_field: relative_selection,
                }
            )
        else:
            screen.update(
                {
                    "decision": "catalog",
                    "reason": (
                        f"{stage}支持继续研究，但横向比较后未获得本周期"
                        f"{next_stage}容量。"
                    ),
                    "evidence": list(screen.get("evidence") or [])
                    + [
                        f"stage_selection:{relative_selection}",
                        f"stage_selection_sha256:{sealed.sha256}",
                    ],
                    "next_action": "等待结构化触发器或下一周期重新竞争研究预算。",
                }
            )
            queued["next_action"] = (
                "等待结构化触发器或下一周期重新竞争研究预算。"
            )
            queued[next_binding_field] = relative_selection
    write_jsonl(screening_path, list(screen_by_symbol.values()))
    write_jsonl(queue_path, list(queue_by_symbol.values()))
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "evaluated_stage": stage,
        "next_stage": next_stage,
        "cohort_count": len(cohort),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selected_symbols": [item["symbol"] for item in selected],
        "selection_path": relative_selection,
        "selection_sha256": sealed.sha256,
        "idempotent": False,
        "portfolio_action": None,
    }


def profile_cycle_status(*, root: str | Path, cycle_id: str) -> dict[str, Any]:
    """Return a verified progress snapshot for one profile allocation cycle."""

    cycle = _text(cycle_id, "cycle_id")
    if not CYCLE_RE.fullmatch(cycle):
        raise ResearchAllocationError("cycle_id is invalid")
    base = Path(root)
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
    triage_selection_paths = {
        item.get("triage_selection_path")
        for item in recorded
        if isinstance(item.get("triage_selection_path"), str)
    }
    if len(triage_selection_paths) == 1:
        triage_selection_path = next(iter(triage_selection_paths))
        cohort = [
            item
            for item in queue
            if item.get("triage_selection_path") == triage_selection_path
            and (
                item.get("task_type") == "quick_profile"
                or _history_completed(item, "quick_profile")
            )
        ]
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
    repository_root = base.parent.parent
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
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "allocation_sha256": allocation_sha,
        "cohort_count": len(cohort),
        "recorded_count": len(recorded),
        "remaining_count": len({item["symbol"] for item in cohort} - recorded_symbols),
        "by_next_stage": dict(sorted(stage_counts.items())),
        "by_queue_status": dict(sorted(status_counts.items())),
        "invalid_artifact_count": len(invalid),
        "invalid_artifacts": invalid,
    }


def _validate_package(
    package: Mapping[str, Any], *, recorded_at: dt.datetime
) -> dict[str, Any]:
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


def _profile_priority_score(
    profile: Mapping[str, Any], *, priority: int
) -> int:
    """Use coarse buckets to rank research value without fake valuation precision."""

    base_return = float(profile["valuation"]["base_expected_annual_return"])
    if base_return >= 0.15:
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
