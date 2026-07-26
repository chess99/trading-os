from __future__ import annotations

import datetime as dt
import json
import math
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
from .research_allocation import ResearchAllocationError
from .sealing import seal_json, verify_sealed


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
TRIGGER_KEYS = {"type", "condition", "reason"}
SOURCE_TIERS = {"S1", "S2", "S3"}
TRIGGER_TYPES = {"filing", "price", "event", "thesis"}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
CYCLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def claim_rapid_triage_task(
    *,
    root: str | Path,
    agent: str,
    claimed_at: dt.datetime,
    symbol: str | None = None,
    lens: str | None = None,
) -> dict[str, Any]:
    """Claim one L1.5 task while binding one agent to one company."""

    _aware(claimed_at, "claimed_at")
    agent_name = _text(agent, "agent")
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
                f"agent already has a different rapid-triage task: "
                f"{current.get('symbol')}"
            )
        return _claim_payload(current, idempotent=True)

    candidates = [
        item
        for item in queue
        if item.get("task_type") == "rapid_triage"
        and item.get("status") == "pending"
        and item.get("assigned_agent") is None
        and bool(item.get("selected_by"))
    ]
    if symbol is not None:
        _symbol(symbol)
        candidates = [item for item in candidates if item.get("symbol") == symbol]
    if lens is not None:
        lens_name = _text(lens, "lens")
        candidates = [
            item
            for item in candidates
            if lens_name in (item.get("selected_by") or [])
        ]
    if not candidates:
        raise ResearchAllocationError("no eligible rapid-triage task is available")
    candidates.sort(
        key=lambda item: (int(item.get("priority", 5)), str(item.get("symbol")))
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
        [
            selected if item.get("symbol") == selected["symbol"] else item
            for item in queue
        ],
    )
    return _claim_payload(selected, idempotent=False)


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
        raise ResearchAllocationError(
            f"rapid-triage task is not running: {ticker_symbol}"
        )
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
    """Seal one L1.5 result; never promote before cohort comparison."""

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
    if queue_record.get("task_type") != "rapid_triage":
        raise ResearchAllocationError(f"task is not rapid triage: {symbol}")
    if queue_record.get("status") not in {"pending", "running"}:
        raise ResearchAllocationError(
            f"rapid triage cannot be recorded from status "
            f"{queue_record.get('status')}: {symbol}"
        )
    if normalized["company_name"] != queue_record.get("name"):
        raise ResearchAllocationError(f"company name does not match queue: {symbol}")
    assigned = queue_record.get("assigned_agent")
    if assigned is not None and assigned != normalized["provenance"]["agent"]:
        raise ResearchAllocationError(
            f"rapid-triage provenance agent does not match assignment: {symbol}"
        )
    allocation_sha = queue_record.get("allocation_sha256")
    if not isinstance(allocation_sha, str) or len(allocation_sha) != 64:
        raise ResearchAllocationError(f"rapid triage lacks allocation binding: {symbol}")
    bound_cycles = {
        item.get("triage_cycle_id")
        for item in queue
        if item.get("allocation_sha256") == allocation_sha
        and item.get("triage_cycle_id") is not None
    }
    if bound_cycles and bound_cycles != {normalized["cycle_id"]}:
        raise ResearchAllocationError(
            f"allocation is already bound to another triage cycle: "
            f"{sorted(bound_cycles)}"
        )
    _validate_local_sources(normalized["sources"], repository_root=base.parent.parent)

    evaluation = evaluate_rapid_triage(normalized)
    timestamp = recorded_at.strftime("%Y%m%dT%H%M%S%z")
    artifact_dir = base / "triage" / normalized["cycle_id"] / ticker
    package_path = artifact_dir / f"{timestamp}.triage.json"
    sealed = seal_json(
        package_path,
        normalized,
        artifact_type="rapid_triage_package",
        sealed_at=recorded_at,
    )
    repository_root = base.parent.parent
    relative_path = package_path.relative_to(repository_root).as_posix()

    updated_screening = dict(screening_record)
    updated_screening.update(
        {
            "decision": evaluation["disposition"],
            "reason": _disposition_reason(evaluation["disposition"]),
            "evidence": [
                f"rapid_triage:{relative_path}",
                f"rapid_triage_sha256:{sealed.sha256}",
                f"allocation_sha256:{allocation_sha}",
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
        }
    )
    updated_queue = dict(queue_record)
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
            "triage_priority_score": evaluation["research_priority_score"],
            "revisit_triggers": normalized["revisit_triggers"],
        }
    )
    write_jsonl(
        screening_path,
        [
            updated_screening if item.get("symbol") == symbol else item
            for item in screening
        ],
    )
    write_jsonl(
        queue_path,
        [updated_queue if item.get("symbol") == symbol else item for item in queue],
    )
    return {
        "schema_version": 1,
        "symbol": symbol,
        "disposition": evaluation["disposition"],
        "research_priority_score": evaluation["research_priority_score"],
        "triage_path": relative_path,
        "triage_sha256": sealed.sha256,
        "awaiting_cohort_comparison": (
            evaluation["disposition"] == "triage_candidate"
        ),
        "portfolio_action": None,
    }


def evaluate_rapid_triage(package: Mapping[str, Any]) -> dict[str, Any]:
    """Derive a stop/candidate result and a research-priority score."""

    survival = package["survival_status"]
    governance = package["governance_status"]
    legibility = package["business_legibility"]
    valuation = package["valuation_signal"]
    research_value = package["research_value"]
    earnings = package["earnings_legibility"]
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
        raise ResearchAllocationError(
            f"{disposition} rapid triage requires a revisit trigger"
        )

    score = (
        {"high": 6, "medium": 3, "low": 0}[research_value]
        + {"attractive": 6, "possible": 3, "unknown": 0, "unattractive": -10}[
            valuation
        ]
        + {"clear": 3, "uncertain": 1, "opaque": -10}[legibility]
        + {"pass": 2, "concern": 0, "fail": -10}[survival]
        + {"acceptable": 2, "concern": 0, "uninvestable": -10}[governance]
        + {"plausible": 2, "uncertain": 0, "unavailable": -3}[earnings]
    )
    return {
        "schema_version": 1,
        "symbol": package["symbol"],
        "disposition": disposition,
        "research_priority_score": score,
        "portfolio_action": None,
    }


def finalize_rapid_triage_cycle(
    *,
    root: str | Path,
    cycle_id: str,
    policy: Mapping[str, Any],
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    """Compare the complete sealed cohort before granting formal-profile budget."""

    _aware(finalized_at, "finalized_at")
    cycle = _cycle(cycle_id)
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    selection_path = base / "triage" / cycle / "selection.json"
    if selection_path.exists():
        verified = verify_sealed(selection_path)
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
        relative = selection_path.relative_to(base.parent.parent).as_posix()
        selected_symbols = [
            item["symbol"]
            for item in payload["ranking"]
            if item["selected_for_quick_profile"]
        ]
        queue_by_symbol = {item["symbol"]: item for item in queue}
        if not all(
            queue_by_symbol.get(symbol, {}).get("task_type") == "quick_profile"
            and queue_by_symbol[symbol].get("triage_selection_path") == relative
            for symbol in selected_symbols
        ):
            raise ResearchAllocationError(
                "sealed rapid-triage selection exists but queue materialization "
                "is incomplete"
            )
        return {
            "schema_version": 1,
            "cycle_id": cycle,
            "cohort_count": payload["cohort_count"],
            "eligible_count": payload["eligible_count"],
            "selected_count": payload["selected_count"],
            "selected_symbols": selected_symbols,
            "selection_path": relative,
            "selection_sha256": verified.sha256,
            "idempotent": True,
            "portfolio_action": None,
        }
    recorded = [item for item in queue if item.get("triage_cycle_id") == cycle]
    if not recorded:
        raise ResearchAllocationError(f"rapid-triage cycle is empty: {cycle}")
    allocation_shas = {item.get("allocation_sha256") for item in recorded}
    if len(allocation_shas) != 1:
        raise ResearchAllocationError("rapid-triage cycle spans multiple allocations")
    allocation_sha = next(iter(allocation_shas))
    cohort = [
        item
        for item in queue
        if item.get("allocation_sha256") == allocation_sha
        and bool(item.get("selected_by"))
    ]
    incomplete = [
        item["symbol"]
        for item in cohort
        if item.get("task_type") != "rapid_triage"
        or item.get("status") != "completed"
        or item.get("triage_cycle_id") != cycle
        or not item.get("triage_disposition")
    ]
    if incomplete:
        raise ResearchAllocationError(
            "completion-order promotion is forbidden; rapid-triage cohort is "
            f"incomplete: {incomplete[:10]}"
        )
    for item in cohort:
        result_path = item.get("result_path")
        if not isinstance(result_path, str):
            raise ResearchAllocationError(
                f"rapid-triage result path missing: {item['symbol']}"
            )
        verify_sealed(base.parent.parent / result_path)

    capacity = _policy_positive_int(policy, "quick_profile_capacity_per_cycle")
    quick_budget = _policy_budget(policy, "quick_profile")
    eligible = [
        item for item in cohort if item.get("triage_disposition") == "triage_candidate"
    ]
    ranked = sorted(
        eligible,
        key=lambda item: (
            -_comparison_score(item),
            int(item.get("priority", 5)),
            str(item["symbol"]),
        ),
    )
    selected = ranked[:capacity]
    selected_symbols = {item["symbol"] for item in selected}
    comparison_rows = []
    for rank, item in enumerate(ranked, 1):
        comparison_rows.append(
            {
                "rank": rank,
                "symbol": item["symbol"],
                "name": item["name"],
                "research_priority_score": item["triage_priority_score"],
                "comparison_score": _comparison_score(item),
                "selected_for_quick_profile": item["symbol"] in selected_symbols,
                "selected_by": item.get("selected_by") or [],
            }
        )
    selection_payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "allocation_sha256": allocation_sha,
        "finalized_at": finalized_at.isoformat(),
        "cohort_count": len(cohort),
        "eligible_count": len(eligible),
        "quick_profile_capacity": capacity,
        "selected_count": len(selected),
        "principle": _policy_text(policy, "comparison_principle"),
        "ranking": comparison_rows,
        "portfolio_action": None,
    }
    sealed_selection = seal_json(
        selection_path,
        selection_payload,
        artifact_type="rapid_triage_cross_company_selection",
        sealed_at=finalized_at,
    )
    relative_selection = selection_path.relative_to(base.parent.parent).as_posix()

    screen_by_symbol = {item["symbol"]: dict(item) for item in screening}
    queue_by_symbol = {item["symbol"]: dict(item) for item in queue}
    for item in ranked:
        symbol = item["symbol"]
        screen = screen_by_symbol[symbol]
        queued = queue_by_symbol[symbol]
        if symbol in selected_symbols:
            screen.update(
                {
                    "decision": "quick_profile",
                    "reason": "完整快速甄别批次横向比较后获得正式画像预算。",
                    "evidence": list(screen.get("evidence") or [])
                    + [
                        f"triage_selection:{relative_selection}",
                        f"triage_selection_sha256:{sealed_selection.sha256}",
                    ],
                    "next_action": "完成一小时级正式投资画像。",
                    "triage_comparison_rank": next(
                        row["rank"]
                        for row in comparison_rows
                        if row["symbol"] == symbol
                    ),
                }
            )
            queued.update(
                {
                    "task_type": "quick_profile",
                    "status": "pending",
                    "assigned_agent": None,
                    "started_at": None,
                    "finished_at": None,
                    "failure_reason": None,
                    "reason": "完整快速甄别批次横向比较后获得正式画像预算。",
                    "next_action": "完成正式画像；不得直接给买入或仓位。",
                    "effort_budget_hours": quick_budget,
                    "preceding_stage": "rapid_triage",
                    "stop_conditions": [
                        "不存在可信的10%回报路径",
                        "生存、治理或正常化盈利无法建立",
                        "决定性未知数无法由公开证据解决",
                    ],
                    "triage_selection_path": relative_selection,
                }
            )
        else:
            screen.update(
                {
                    "decision": "catalog",
                    "reason": "快速甄别存在研究路径，但横向比较后未获得本周期正式画像容量。",
                    "evidence": list(screen.get("evidence") or [])
                    + [
                        f"triage_selection:{relative_selection}",
                        f"triage_selection_sha256:{sealed_selection.sha256}",
                    ],
                    "next_action": "等待价格、财报、事件、论点变化或下一周期重新竞争。",
                }
            )
            queued.update(
                {
                    "next_action": "等待结构化触发器或下一周期重新竞争正式画像预算。",
                    "triage_selection_path": relative_selection,
                }
            )
    write_jsonl(screening_path, list(screen_by_symbol.values()))
    write_jsonl(queue_path, list(queue_by_symbol.values()))
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "cohort_count": len(cohort),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selected_symbols": [item["symbol"] for item in selected],
        "selection_path": relative_selection,
        "selection_sha256": sealed_selection.sha256,
        "idempotent": False,
        "portfolio_action": None,
    }


def rapid_triage_cycle_status(
    *, root: str | Path, cycle_id: str
) -> dict[str, Any]:
    cycle = _cycle(cycle_id)
    base = Path(root)
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    recorded = [item for item in queue if item.get("triage_cycle_id") == cycle]
    allocation_shas = {item.get("allocation_sha256") for item in recorded}
    allocation_sha = next(iter(allocation_shas), None) if len(allocation_shas) == 1 else None
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
    invalid: list[dict[str, str]] = []
    for item in recorded:
        path = item.get("result_path")
        if not isinstance(path, str):
            invalid.append({"symbol": item["symbol"], "error": "result_path_missing"})
            continue
        try:
            verify_sealed(base.parent.parent / path)
        except ValueError as exc:
            invalid.append({"symbol": item["symbol"], "error": str(exc)})
    disposition_counts: dict[str, int] = {}
    for item in recorded:
        disposition = str(item.get("triage_disposition"))
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
    selection_path = base / "triage" / cycle / "selection.json"
    selection_valid = False
    if selection_path.exists():
        try:
            verify_sealed(selection_path)
            selection_valid = True
        except ValueError as exc:
            invalid.append({"symbol": "*selection*", "error": str(exc)})
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "allocation_sha256": allocation_sha,
        "cohort_count": len(cohort),
        "recorded_count": len(recorded_symbols),
        "remaining_count": len({item["symbol"] for item in cohort} - recorded_symbols),
        "by_disposition": dict(sorted(disposition_counts.items())),
        "selection_finalized": selection_valid,
        "invalid_artifact_count": len(invalid),
        "invalid_artifacts": invalid,
        "portfolio_action": None,
    }


def _normalize_package(
    package: Mapping[str, Any], *, recorded_at: dt.datetime
) -> dict[str, Any]:
    if not isinstance(package, Mapping) or set(package) != PACKAGE_KEYS:
        raise ResearchAllocationError(
            "rapid-triage package fields do not match contract"
        )
    if package.get("schema_version") != 1:
        raise ResearchAllocationError("rapid-triage schema_version must be 1")
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

    provenance_raw = package.get("provenance")
    if not isinstance(provenance_raw, Mapping) or set(provenance_raw) != PROVENANCE_KEYS:
        raise ResearchAllocationError(
            "rapid-triage provenance fields do not match contract"
        )
    generated_at = _datetime(provenance_raw.get("generated_at"), "generated_at")
    if generated_at < cutoff or generated_at > recorded_at:
        raise ResearchAllocationError("rapid-triage generated_at is invalid")
    tools = _text_array(provenance_raw.get("tools"), "tools", allow_empty=False)

    triggers_raw = package.get("revisit_triggers")
    if not isinstance(triggers_raw, list):
        raise ResearchAllocationError("revisit_triggers must be an array")
    triggers = []
    for raw in triggers_raw:
        if not isinstance(raw, Mapping) or set(raw) != TRIGGER_KEYS:
            raise ResearchAllocationError(
                "rapid-triage revisit trigger fields do not match contract"
            )
        triggers.append(
            {
                "type": _enum(raw.get("type"), TRIGGER_TYPES, "trigger.type"),
                "condition": _text(raw.get("condition"), "trigger.condition"),
                "reason": _text(raw.get("reason"), "trigger.reason"),
            }
        )
    decisive = package.get("decisive_question")
    if decisive is not None:
        decisive = _text(decisive, "decisive_question")
    result = {
        "schema_version": 1,
        "cycle_id": cycle,
        "symbol": symbol,
        "company_name": _text(package.get("company_name"), "company_name"),
        "as_of": as_of.isoformat(),
        "information_cutoff": cutoff.isoformat(),
        "price_as_of": price_as_of.isoformat(),
        "price_source_id": price_source_id,
        "current_price": current_price,
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
        "decisive_question": decisive,
        "reason_codes": _text_array(
            package.get("reason_codes"), "reason_codes", allow_empty=False
        ),
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


def _comparison_score(item: Mapping[str, Any]) -> int:
    priority = int(item.get("priority", 5))
    lens_count = min(len(item.get("selected_by") or []), 3)
    return int(item["triage_priority_score"]) + (6 - priority) + lens_count


def _claim_payload(record: Mapping[str, Any], *, idempotent: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "symbol": record.get("symbol"),
        "name": record.get("name"),
        "task_type": "rapid_triage",
        "assigned_agent": record.get("assigned_agent"),
        "started_at": record.get("started_at"),
        "effort_budget_hours": record.get("effort_budget_hours"),
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
        raise ResearchAllocationError(
            f"source requires URL or local path: {source_id}"
        )
    return {
        "source_id": source_id,
        "tier": _enum(raw.get("tier"), SOURCE_TIERS, f"{source_id}.tier"),
        "title": _text(raw.get("title"), f"{source_id}.title"),
        "accessed_at": accessed_at.isoformat(),
        "url": url,
        "local_path": local_path,
        "supports": _text_array(
            raw.get("supports"), f"{source_id}.supports", allow_empty=False
        ),
    }


def _validate_local_sources(
    sources: list[dict[str, Any]], *, repository_root: Path
) -> None:
    root = repository_root.resolve()
    for source in sources:
        local_path = source["local_path"]
        if local_path is None:
            continue
        candidate = Path(local_path)
        if candidate.is_absolute():
            raise ResearchAllocationError(
                f"local source paths must be repository-relative: "
                f"{source['source_id']}"
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


def _policy_text(policy: Mapping[str, Any], field: str) -> str:
    return _text(policy.get(field), field)


def _one(
    records: list[dict[str, Any]], symbol: str, label: str
) -> dict[str, Any]:
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
    if (
        not isinstance(value, dt.datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
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
