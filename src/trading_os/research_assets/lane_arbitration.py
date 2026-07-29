from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .sealing import SealingError, seal_json, verify_sealed

SCHEMA_VERSION = 1
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROTECTED_TASK_TYPES = {
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
}


class LaneArbitrationError(ValueError):
    """Raised when frozen baseline and incremental lanes cannot be reconciled."""


@serialized_coverage_write
def freeze_lane_arbitration(
    *,
    root: str | Path,
    run_id: str,
    frozen_at: dt.datetime,
    scope_manifest_path: str | Path | None = None,
    baseline_intake_path: str | Path | None = None,
    trigger_hit_checkpoint_path: str | Path | None = None,
    baseline_minimum_slots: int = 1,
    apply_coverage: bool = True,
) -> dict[str, Any]:
    """Seal incremental intake and lane decisions before queue materialization."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _run_id(run_id)
    sealed_at = _aware(frozen_at, "frozen_at")
    if (
        isinstance(baseline_minimum_slots, bool)
        or not isinstance(baseline_minimum_slots, int)
        or baseline_minimum_slots < 1
    ):
        raise LaneArbitrationError("baseline_minimum_slots must be a positive integer")
    scope_dir = base / "scopes" / run
    scope_path = _resolve(
        scope_manifest_path or scope_dir / "manifest.json", repository_root
    )
    baseline_path = _resolve(
        baseline_intake_path or scope_dir / "baseline-intake.json", repository_root
    )
    checkpoint_path = _resolve(
        trigger_hit_checkpoint_path or scope_dir / "trigger-hit-checkpoint.json",
        repository_root,
    )
    scope, scope_sha = _load_sealed(
        scope_path, artifact_type="all_a_scope_manifest", label="scope manifest"
    )
    baseline, baseline_sha = _load_sealed(
        baseline_path, artifact_type="all_a_baseline_intake", label="baseline intake"
    )
    checkpoint, checkpoint_sha = _load_sealed(
        checkpoint_path,
        artifact_type="trigger_hit_checkpoint",
        label="trigger-hit checkpoint",
    )
    _validate_bindings(
        run=run,
        scope=scope,
        scope_sha=scope_sha,
        baseline=baseline,
        checkpoint=checkpoint,
    )
    scope_cutoff = _parse_datetime(scope.get("scope_cutoff"), "scope_cutoff")
    if sealed_at < _parse_datetime(checkpoint.get("checkpointed_at"), "checkpointed_at"):
        raise LaneArbitrationError("frozen_at cannot be before trigger-hit checkpoint")

    queue_path = base / RESEARCH_QUEUE_FILE
    queue_by_symbol = _unique_queue(read_jsonl(queue_path))
    scope_by_symbol = _scope_members(scope)
    baseline_by_symbol = _baseline_members(baseline)

    incremental_path = scope_dir / "incremental-intake.json"
    if incremental_path.exists():
        incremental, incremental_sha = _load_sealed(
            incremental_path,
            artifact_type="all_a_incremental_intake",
            label="incremental intake",
        )
        _validate_incremental(
            incremental,
            run=run,
            scope_sha=scope_sha,
            checkpoint_sha=checkpoint_sha,
        )
    else:
        incremental = _build_incremental_intake(
            run=run,
            scope_cutoff=scope_cutoff,
            scope_path=scope_path,
            scope_sha=scope_sha,
            checkpoint_path=checkpoint_path,
            checkpoint_sha=checkpoint_sha,
            checkpoint=checkpoint,
            scope_by_symbol=scope_by_symbol,
            repository_root=repository_root,
        )
        incremental_seal = seal_json(
            incremental_path,
            incremental,
            artifact_type="all_a_incremental_intake",
            sealed_at=sealed_at,
        )
        incremental_sha = incremental_seal.sha256

    arbitration_path = scope_dir / "lane-arbitration.json"
    if arbitration_path.exists():
        arbitration, arbitration_sha = _load_sealed(
            arbitration_path,
            artifact_type="all_a_lane_arbitration",
            label="lane arbitration",
        )
        _validate_arbitration(
            arbitration,
            run=run,
            scope_sha=scope_sha,
            baseline_sha=baseline_sha,
            checkpoint_sha=checkpoint_sha,
            incremental_sha=incremental_sha,
            baseline_minimum_slots=baseline_minimum_slots,
        )
    else:
        arbitration = _build_arbitration(
            run=run,
            scope_cutoff=scope_cutoff,
            scope_path=scope_path,
            scope_sha=scope_sha,
            baseline_path=baseline_path,
            baseline_sha=baseline_sha,
            checkpoint_path=checkpoint_path,
            checkpoint_sha=checkpoint_sha,
            incremental_path=incremental_path,
            incremental_sha=incremental_sha,
            incremental=incremental,
            baseline_by_symbol=baseline_by_symbol,
            scope_by_symbol=scope_by_symbol,
            queue_by_symbol=queue_by_symbol,
            baseline_minimum_slots=baseline_minimum_slots,
            repository_root=repository_root,
        )
        arbitration_seal = seal_json(
            arbitration_path,
            arbitration,
            artifact_type="all_a_lane_arbitration",
            sealed_at=sealed_at,
        )
        arbitration_sha = arbitration_seal.sha256

    materialization = {
        "applied": False,
        "changed_count": 0,
        "protected_count": 0,
        "created_count": 0,
        "repaired_count": 0,
    }
    if apply_coverage:
        materialization = _materialize_arbitration(
            arbitration=arbitration,
            queue_by_symbol=queue_by_symbol,
            queue_path=queue_path,
            incremental_path=_relative(incremental_path, repository_root),
            incremental_sha=incremental_sha,
            arbitration_path=_relative(arbitration_path, repository_root),
            arbitration_sha=arbitration_sha,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run,
        "scope_cutoff": scope_cutoff.isoformat(),
        "incremental_intake_path": _relative(incremental_path, repository_root),
        "incremental_intake_sha256": incremental_sha,
        "lane_arbitration_path": _relative(arbitration_path, repository_root),
        "lane_arbitration_sha256": arbitration_sha,
        "incremental_counts": incremental["counts"],
        "arbitration_counts": arbitration["counts"],
        "materialization": materialization,
        "portfolio_action": None,
    }


def verify_lane_arbitration(*, root: str | Path, run_id: str) -> dict[str, Any]:
    base = Path(root)
    run = _run_id(run_id)
    scope_dir = base / "scopes" / run
    scope, scope_sha = _load_sealed(
        scope_dir / "manifest.json",
        artifact_type="all_a_scope_manifest",
        label="scope manifest",
    )
    baseline, baseline_sha = _load_sealed(
        scope_dir / "baseline-intake.json",
        artifact_type="all_a_baseline_intake",
        label="baseline intake",
    )
    checkpoint, checkpoint_sha = _load_sealed(
        scope_dir / "trigger-hit-checkpoint.json",
        artifact_type="trigger_hit_checkpoint",
        label="trigger-hit checkpoint",
    )
    incremental, incremental_sha = _load_sealed(
        scope_dir / "incremental-intake.json",
        artifact_type="all_a_incremental_intake",
        label="incremental intake",
    )
    arbitration, arbitration_sha = _load_sealed(
        scope_dir / "lane-arbitration.json",
        artifact_type="all_a_lane_arbitration",
        label="lane arbitration",
    )
    _validate_bindings(
        run=run,
        scope=scope,
        scope_sha=scope_sha,
        baseline=baseline,
        checkpoint=checkpoint,
    )
    _validate_incremental(
        incremental,
        run=run,
        scope_sha=scope_sha,
        checkpoint_sha=checkpoint_sha,
    )
    _validate_arbitration(
        arbitration,
        run=run,
        scope_sha=scope_sha,
        baseline_sha=baseline_sha,
        checkpoint_sha=checkpoint_sha,
        incremental_sha=incremental_sha,
        baseline_minimum_slots=arbitration["contract"]["baseline_minimum_slots"],
    )
    queue_by_symbol = _unique_queue(read_jsonl(base / RESEARCH_QUEUE_FILE))
    drift = []
    for decision in arbitration["decisions"]:
        if decision["materialization_action"] in {"baseline_only", "portfolio_only"}:
            continue
        queued = queue_by_symbol.get(decision["symbol"])
        context = _find_context(queued, run) if queued is not None else None
        if context is None or context.get("hit_ids") != decision["company_hit_ids"]:
            drift.append(decision["symbol"])
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run,
        "incremental_intake_sha256": incremental_sha,
        "lane_arbitration_sha256": arbitration_sha,
        "counts": arbitration["counts"],
        "queue_materialization_drift_count": len(drift),
        "queue_materialization_drift_sample": drift[:50],
        "ok": not drift,
        "portfolio_action": None,
    }


def _build_incremental_intake(
    *,
    run: str,
    scope_cutoff: dt.datetime,
    scope_path: Path,
    scope_sha: str,
    checkpoint_path: Path,
    checkpoint_sha: str,
    checkpoint: Mapping[str, Any],
    scope_by_symbol: Mapping[str, Mapping[str, Any]],
    repository_root: Path,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    raw_hits = checkpoint.get("hits")
    if not isinstance(raw_hits, list):
        raise LaneArbitrationError("trigger-hit checkpoint hits must be an array")
    seen_hits: set[str] = set()
    for raw in raw_hits:
        if not isinstance(raw, Mapping):
            raise LaneArbitrationError("trigger-hit checkpoint hit must be an object")
        symbol = _symbol(raw.get("symbol"))
        if symbol not in scope_by_symbol:
            raise LaneArbitrationError(f"checkpoint hit is outside frozen scope: {symbol}")
        hit_id = _sha256(raw.get("hit_id"), "hit_id")
        if hit_id in seen_hits:
            raise LaneArbitrationError(f"duplicate hit_id in checkpoint: {hit_id}")
        seen_hits.add(hit_id)
        effective_at = _parse_datetime(raw.get("effective_at"), "hit effective_at")
        if effective_at > scope_cutoff:
            raise LaneArbitrationError("checkpoint contains a hit after scope_cutoff")
        target = raw.get("workflow_target")
        if target not in {"company_research", "portfolio_refresh"}:
            raise LaneArbitrationError(f"checkpoint workflow_target is invalid: {target}")
        grouped.setdefault(symbol, []).append(
            {
                "hit_id": hit_id,
                "dedupe_key": _sha256(raw.get("dedupe_key"), "dedupe_key"),
                "symbol": symbol,
                "workflow_target": target,
                "trigger_id": _text(raw.get("trigger_id"), "trigger_id"),
                "trigger_type": _text(raw.get("trigger_type"), "trigger_type"),
                "definition_sha256": _sha256(
                    raw.get("definition_sha256"), "definition_sha256"
                ),
                "effective_at": effective_at.isoformat(),
                "observed_at": _parse_datetime(
                    raw.get("observed_at"), "hit observed_at"
                ).isoformat(),
                "occurrence_key": _text(raw.get("occurrence_key"), "occurrence_key"),
                "observed_event_id": _sha256(
                    raw.get("observed_event_id"), "observed_event_id"
                ),
            }
        )

    dispatch_order = sorted(
        grouped,
        key=lambda symbol: (
            min(_parse_datetime(item["effective_at"], "effective_at") for item in grouped[symbol]),
            symbol,
        ),
    )
    dispatch_ordinal = {symbol: index for index, symbol in enumerate(dispatch_order, 1)}
    members = []
    for symbol in sorted(grouped):
        hits = sorted(
            grouped[symbol], key=lambda item: (item["effective_at"], item["hit_id"])
        )
        company_hits = [
            item["hit_id"] for item in hits if item["workflow_target"] == "company_research"
        ]
        portfolio_hits = [
            item["hit_id"] for item in hits if item["workflow_target"] == "portfolio_refresh"
        ]
        scope_member = scope_by_symbol[symbol]
        members.append(
            {
                "ordinal": len(members) + 1,
                "administrative_order": dispatch_ordinal[symbol],
                "symbol": symbol,
                "name": _text(scope_member.get("name"), f"{symbol}.name"),
                "hit_ids": [item["hit_id"] for item in hits],
                "company_research_hit_ids": company_hits,
                "portfolio_refresh_hit_ids": portfolio_hits,
                "hit_count": len(hits),
                "earliest_effective_at": hits[0]["effective_at"],
                "latest_effective_at": max(item["effective_at"] for item in hits),
                "trigger_types": sorted({str(item["trigger_type"]) for item in hits}),
                "hits": hits,
            }
        )
    counts = {
        "hit_count": len(seen_hits),
        "symbol_count": len(members),
        "company_research_hit_count": sum(
            len(item["company_research_hit_ids"]) for item in members
        ),
        "portfolio_refresh_hit_count": sum(
            len(item["portfolio_refresh_hit_ids"]) for item in members
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run,
        "lane": "incremental",
        "scope_cutoff": scope_cutoff.isoformat(),
        "scope_manifest_path": _relative(scope_path, repository_root),
        "scope_manifest_sha256": scope_sha,
        "trigger_hit_checkpoint_path": _relative(checkpoint_path, repository_root),
        "trigger_hit_checkpoint_sha256": checkpoint_sha,
        "selection_basis": (
            "all open trigger hits in the sealed checkpoint, merged by symbol; "
            "administrative order uses earliest effective_at then symbol only; no investment "
            "score, rank, valuation, market cap, liquidity, profitability, or prior rating"
        ),
        "counts": counts,
        "members": members,
        "portfolio_action": None,
    }


def _build_arbitration(
    *,
    run: str,
    scope_cutoff: dt.datetime,
    scope_path: Path,
    scope_sha: str,
    baseline_path: Path,
    baseline_sha: str,
    checkpoint_path: Path,
    checkpoint_sha: str,
    incremental_path: Path,
    incremental_sha: str,
    incremental: Mapping[str, Any],
    baseline_by_symbol: Mapping[str, Mapping[str, Any]],
    scope_by_symbol: Mapping[str, Mapping[str, Any]],
    queue_by_symbol: Mapping[str, Mapping[str, Any]],
    baseline_minimum_slots: int,
    repository_root: Path,
) -> dict[str, Any]:
    incremental_by_symbol = {item["symbol"]: item for item in incremental["members"]}
    symbols = sorted(set(baseline_by_symbol) | set(incremental_by_symbol))
    decisions = []
    for symbol in symbols:
        baseline_required = symbol in baseline_by_symbol
        incremental_member = incremental_by_symbol.get(symbol)
        company_hit_ids = (
            list(incremental_member["company_research_hit_ids"])
            if incremental_member is not None
            else []
        )
        portfolio_hit_ids = (
            list(incremental_member["portfolio_refresh_hit_ids"])
            if incremental_member is not None
            else []
        )
        queued = queue_by_symbol.get(symbol)
        if not company_hit_ids:
            action = "baseline_only" if baseline_required else "portfolio_only"
        elif queued is not None and _is_protected(queued):
            action = "merge_active_or_deeper"
        elif baseline_required:
            action = "merge_into_baseline"
        else:
            action = "create_incremental_rapid_triage"
        effective_lane = (
            "merged"
            if baseline_required and company_hit_ids
            else "baseline"
            if baseline_required
            else "incremental"
        )
        prior_queue = {
            "present": queued is not None,
            "task_type": queued.get("task_type") if queued else None,
            "status": queued.get("status") if queued else None,
            "assigned_agent": queued.get("assigned_agent") if queued else None,
            "lease_id": queued.get("lease_id") if queued else None,
            "lease_expires_at": queued.get("lease_expires_at") if queued else None,
        }
        decisions.append(
            {
                "ordinal": len(decisions) + 1,
                "symbol": symbol,
                "name": _text(scope_by_symbol[symbol].get("name"), f"{symbol}.name"),
                "baseline_required": baseline_required,
                "company_hit_ids": company_hit_ids,
                "portfolio_hit_ids": portfolio_hit_ids,
                "effective_lane": effective_lane,
                "materialization_action": action,
                "prior_queue": prior_queue,
                "reason_codes": _decision_reasons(
                    action=action,
                    baseline_required=baseline_required,
                    company_hit_count=len(company_hit_ids),
                ),
            }
        )
    counts = {
        "symbol_count": len(decisions),
        "baseline_symbol_count": sum(item["baseline_required"] for item in decisions),
        "incremental_symbol_count": sum(bool(item["company_hit_ids"]) for item in decisions),
        "merged_symbol_count": sum(item["effective_lane"] == "merged" for item in decisions),
        "protected_symbol_count": sum(
            item["materialization_action"] == "merge_active_or_deeper"
            for item in decisions
        ),
        "portfolio_only_symbol_count": sum(
            item["materialization_action"] == "portfolio_only" for item in decisions
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run,
        "scope_cutoff": scope_cutoff.isoformat(),
        "scope_manifest_path": _relative(scope_path, repository_root),
        "scope_manifest_sha256": scope_sha,
        "baseline_intake_path": _relative(baseline_path, repository_root),
        "baseline_intake_sha256": baseline_sha,
        "trigger_hit_checkpoint_path": _relative(checkpoint_path, repository_root),
        "trigger_hit_checkpoint_sha256": checkpoint_sha,
        "incremental_intake_path": _relative(incremental_path, repository_root),
        "incremental_intake_sha256": incremental_sha,
        "contract": {
            "baseline_minimum_slots": baseline_minimum_slots,
            "baseline_reservation_rule": (
                "when baseline backlog is non-empty, every administrative dispatch wave "
                "reserves at least baseline_minimum_slots for baseline or merged work"
            ),
            "single_mutable_owner": True,
            "running_lease_preemption": "never_automatic",
            "active_or_deeper_task_policy": "merge_context_without_overwriting_task_owner",
            "new_incremental_task_policy": (
                "create rapid_triage intake only when no running or deeper task exists"
            ),
            "hit_consumption_policy": (
                "hits remain open until a sealed result is published to the immutable company "
                "timeline and the trigger-hit ledger records consumption"
            ),
            "ordering_policy": (
                "incremental earliest effective_at then symbol; baseline stable scope order; "
                "investment attractiveness fields are forbidden"
            ),
        },
        "counts": counts,
        "decisions": decisions,
        "portfolio_action": None,
    }


def _materialize_arbitration(
    *,
    arbitration: Mapping[str, Any],
    queue_by_symbol: dict[str, dict[str, Any]],
    queue_path: Path,
    incremental_path: str,
    incremental_sha: str,
    arbitration_path: str,
    arbitration_sha: str,
) -> dict[str, Any]:
    run = arbitration["run_id"]
    changed_count = 0
    protected_count = 0
    created_count = 0
    repaired_count = 0
    for decision in arbitration["decisions"]:
        action = decision["materialization_action"]
        if action in {"baseline_only", "portfolio_only"}:
            continue
        symbol = decision["symbol"]
        existing = queue_by_symbol.get(symbol)
        context = {
            "run_id": run,
            "scope_cutoff": arbitration["scope_cutoff"],
            "lane": decision["effective_lane"],
            "hit_ids": list(decision["company_hit_ids"]),
            "incremental_intake_path": incremental_path,
            "incremental_intake_sha256": incremental_sha,
            "lane_arbitration_path": arbitration_path,
            "lane_arbitration_sha256": arbitration_sha,
            "status": (
                "attached_existing_task"
                if action == "merge_active_or_deeper"
                else "pending"
            ),
            "consume_after_timeline_publish": True,
        }
        if existing is not None and _is_protected(existing):
            updated, changed = _attach_context(existing, context)
            if changed:
                queue_by_symbol[symbol] = updated
                changed_count += 1
            protected_count += 1
            continue
        prior_context = _find_context(existing, run) if existing is not None else None
        if prior_context is not None and existing.get("status") in {"running", "completed"}:
            continue
        updated = _new_incremental_row(
            existing=existing,
            decision=decision,
            context=context,
            arbitration=arbitration,
        )
        if existing != updated:
            queue_by_symbol[symbol] = updated
            changed_count += 1
            if existing is None:
                created_count += 1
            else:
                repaired_count += 1
    if changed_count:
        write_jsonl(queue_path, list(queue_by_symbol.values()))
    return {
        "applied": True,
        "changed_count": changed_count,
        "protected_count": protected_count,
        "created_count": created_count,
        "repaired_count": repaired_count,
    }


def _attach_context(
    existing: Mapping[str, Any], context: Mapping[str, Any]
) -> tuple[dict[str, Any], bool]:
    updated = dict(existing)
    contexts = list(existing.get("incremental_contexts") or [])
    prior = next((item for item in contexts if item.get("run_id") == context["run_id"]), None)
    if prior is not None:
        if prior != context:
            raise LaneArbitrationError(
                f"incremental context conflicts for {existing.get('symbol')}"
            )
        return updated, False
    contexts.append(dict(context))
    contexts.sort(key=lambda item: item["run_id"])
    updated["incremental_contexts"] = contexts
    return updated, True


def _new_incremental_row(
    *,
    existing: Mapping[str, Any] | None,
    decision: Mapping[str, Any],
    context: Mapping[str, Any],
    arbitration: Mapping[str, Any],
) -> dict[str, Any]:
    updated = dict(existing or {})
    history = list(updated.get("stage_history") or [])
    contexts = [
        dict(item)
        for item in (updated.get("incremental_contexts") or [])
        if isinstance(item, Mapping) and item.get("run_id") != arbitration["run_id"]
    ]
    contexts.append(dict(context))
    contexts.sort(key=lambda item: item["run_id"])
    history_event = {
        "stage": "lane_arbitration_intake",
        "status": "pending",
        "finished_at": arbitration["scope_cutoff"],
        "scope_run_id": arbitration["run_id"],
        "lane": decision["effective_lane"],
        "handled_hit_ids": list(decision["company_hit_ids"]),
        "prior_task_type": existing.get("task_type") if existing else None,
        "prior_status": existing.get("status") if existing else None,
        "prior_result_path": existing.get("result_path") if existing else None,
    }
    if not any(
        item.get("stage") == history_event["stage"]
        and item.get("scope_run_id") == arbitration["run_id"]
        for item in history
    ):
        history.append(history_event)
    updated.update(
        {
            "symbol": decision["symbol"],
            "name": decision["name"],
            "task_type": "rapid_triage",
            "priority": 3,
            "status": (
                "requires_rebaseline" if decision["baseline_required"] else "pending"
            ),
            "reason": (
                "Frozen lane arbitration intake: process all bound trigger hits and, when "
                "required, satisfy the baseline rapid-triage protocol. Administrative only; "
                "no investment ranking was used."
            ),
            "target_company_dir": f"research/companies/CN/{decision['symbol'].split(':')[1]}",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "result_path": None,
            "failure_reason": None,
            "next_action": (
                "Freeze into an administrative cohort and assign one independent company Agent."
            ),
            "effort_budget_hours": 0.25,
            "preceding_stage": "lane_arbitration_intake",
            "scope_run_id": arbitration["run_id"],
            "research_lane": decision["effective_lane"],
            "bound_trigger_hit_ids": list(decision["company_hit_ids"]),
            "incremental_contexts": contexts,
            "stage_history": history,
        }
    )
    for stale in (
        "cohort_path",
        "cohort_sha256",
        "cohort_ordinal",
        "triage_cycle_id",
        "triage_disposition",
        "triage_selection_path",
        "triage_selection_sha256",
    ):
        updated.pop(stale, None)
    return updated


def _validate_bindings(
    *,
    run: str,
    scope: Mapping[str, Any],
    scope_sha: str,
    baseline: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
) -> None:
    cutoff = scope.get("scope_cutoff")
    if scope.get("run_id") != run:
        raise LaneArbitrationError("scope manifest run_id mismatch")
    if (
        baseline.get("run_id") != run
        or baseline.get("lane") != "baseline"
        or baseline.get("scope_manifest_sha256") != scope_sha
        or baseline.get("scope_cutoff") != cutoff
    ):
        raise LaneArbitrationError("baseline intake does not bind frozen scope")
    if (
        checkpoint.get("run_id") != run
        or checkpoint.get("scope_manifest_sha256") != scope_sha
        or checkpoint.get("scope_cutoff") != cutoff
    ):
        raise LaneArbitrationError("trigger-hit checkpoint does not bind frozen scope")


def _validate_incremental(
    payload: Mapping[str, Any], *, run: str, scope_sha: str, checkpoint_sha: str
) -> None:
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("run_id") != run
        or payload.get("lane") != "incremental"
        or payload.get("scope_manifest_sha256") != scope_sha
        or payload.get("trigger_hit_checkpoint_sha256") != checkpoint_sha
    ):
        raise LaneArbitrationError("incremental intake binding is invalid")
    members = payload.get("members")
    if not isinstance(members, list):
        raise LaneArbitrationError("incremental intake members must be an array")
    symbols = [_symbol(item.get("symbol")) for item in members]
    if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
        raise LaneArbitrationError("incremental intake symbols are not stable and unique")


def _validate_arbitration(
    payload: Mapping[str, Any],
    *,
    run: str,
    scope_sha: str,
    baseline_sha: str,
    checkpoint_sha: str,
    incremental_sha: str,
    baseline_minimum_slots: int,
) -> None:
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("run_id") != run
        or payload.get("scope_manifest_sha256") != scope_sha
        or payload.get("baseline_intake_sha256") != baseline_sha
        or payload.get("trigger_hit_checkpoint_sha256") != checkpoint_sha
        or payload.get("incremental_intake_sha256") != incremental_sha
        or payload.get("contract", {}).get("baseline_minimum_slots")
        != baseline_minimum_slots
    ):
        raise LaneArbitrationError("lane arbitration binding is invalid")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise LaneArbitrationError("lane arbitration decisions must be an array")
    symbols = [_symbol(item.get("symbol")) for item in decisions]
    if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
        raise LaneArbitrationError("lane arbitration symbols are not stable and unique")
    if payload.get("contract", {}).get("single_mutable_owner") is not True:
        raise LaneArbitrationError("lane arbitration must enforce one mutable owner")


def _scope_members(scope: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    members = scope.get("members")
    if not isinstance(members, list):
        raise LaneArbitrationError("scope members must be an array")
    result = {}
    for member in members:
        symbol = _symbol(member.get("symbol"))
        if symbol in result:
            raise LaneArbitrationError(f"duplicate scope symbol: {symbol}")
        result[symbol] = dict(member)
    return result


def _baseline_members(baseline: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    members = baseline.get("members")
    if not isinstance(members, list):
        raise LaneArbitrationError("baseline members must be an array")
    result = {}
    for member in members:
        symbol = _symbol(member.get("symbol"))
        if symbol in result:
            raise LaneArbitrationError(f"duplicate baseline symbol: {symbol}")
        result[symbol] = dict(member)
    return result


def _unique_queue(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for record in records:
        symbol = _symbol(record.get("symbol"))
        if symbol in result:
            raise LaneArbitrationError(f"duplicate research queue symbol: {symbol}")
        result[symbol] = record
    return result


def _is_protected(row: Mapping[str, Any]) -> bool:
    return row.get("status") == "running" or row.get("task_type") in PROTECTED_TASK_TYPES


def _find_context(row: Mapping[str, Any] | None, run_id: str) -> Mapping[str, Any] | None:
    if row is None:
        return None
    contexts = row.get("incremental_contexts")
    if not isinstance(contexts, list):
        return None
    return next(
        (
            item
            for item in contexts
            if isinstance(item, Mapping) and item.get("run_id") == run_id
        ),
        None,
    )


def _decision_reasons(
    *, action: str, baseline_required: bool, company_hit_count: int
) -> list[str]:
    reasons = []
    if baseline_required:
        reasons.append("missing_current_protocol_terminal")
    if company_hit_count:
        reasons.append("checkpoint_contains_observed_trigger_hits")
    reasons.append(action)
    if action == "merge_active_or_deeper":
        reasons.extend(["single_mutable_owner", "running_lease_not_preempted"])
    return reasons


def _load_sealed(
    path: Path, *, artifact_type: str, label: str
) -> tuple[dict[str, Any], str]:
    try:
        sealed = verify_sealed(path)
    except (OSError, SealingError) as exc:
        raise LaneArbitrationError(f"{label} is not validly sealed") from exc
    if sealed.artifact_type != artifact_type:
        raise LaneArbitrationError(f"{label} has an unexpected artifact type")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LaneArbitrationError(f"{label} is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise LaneArbitrationError(f"{label} must be an object")
    return payload, sealed.sha256


def _resolve(value: str | Path, repository_root: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repository_root / path).resolve()


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise LaneArbitrationError(f"path must stay inside repository: {path}") from exc


def _run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise LaneArbitrationError("run_id is invalid")
    return value


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not SYMBOL_RE.fullmatch(value):
        raise LaneArbitrationError(f"symbol is invalid: {value}")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise LaneArbitrationError(f"{label} must be a lowercase SHA-256")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LaneArbitrationError(f"{label} must be a non-empty string")
    return value.strip()


def _aware(value: dt.datetime, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LaneArbitrationError(f"{label} must include timezone information")
    return value


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise LaneArbitrationError(f"{label} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise LaneArbitrationError(f"{label} must be an ISO timestamp") from exc
    return _aware(parsed, label)
