from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .coverage_store import (
    COMPANIES_FILE,
    RESEARCH_QUEUE_FILE,
    RUNS_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .sealing import SealingError, atomic_write_bytes, seal_json, verify_sealed
from .triage_workflow import validate_rapid_triage_package

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
MODES = {"auto", "baseline", "incremental"}
HARD_EXCLUSION_DECISIONS = {"hard_exclusion", "skip_not_in_scope", "skip_risk"}
EXCEPTION_DECISIONS = {"needs_manual_review", "skip_too_small"}
PROTECTED_TASK_TYPES = {
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
}
SCOPE_KEYS = {
    "schema_version",
    "run_id",
    "market",
    "mode",
    "scope_cutoff",
    "frozen_at",
    "universe_source",
    "protocol",
    "counts",
    "members",
    "conservation",
    "portfolio_action",
}
INTAKE_KEYS = {
    "schema_version",
    "run_id",
    "lane",
    "scope_cutoff",
    "scope_manifest_path",
    "scope_manifest_sha256",
    "selection_basis",
    "counts",
    "members",
    "portfolio_action",
}


class ScopeWorkflowError(ValueError):
    """Raised when a frozen all-A scope cannot be created or verified."""


@serialized_coverage_write
def freeze_all_a_scope(
    *,
    root: str | Path,
    run_id: str,
    scope_cutoff: dt.datetime,
    frozen_at: dt.datetime,
    mode: str = "auto",
    universe_path: str | Path | None = None,
    apply_intake: bool = True,
) -> dict[str, Any]:
    """Freeze the repository universe and materialize the baseline backlog.

    The immutable scope and intake artifacts are the source of truth. Coverage
    JSONL rows are only resumable materializations and can be repaired by
    replaying this function with the same arguments.
    """

    base = Path(root)
    repository_root = base.parent.parent
    run = _run_id(run_id)
    cutoff = _aware(scope_cutoff, "scope_cutoff")
    frozen = _aware(frozen_at, "frozen_at")
    if frozen < cutoff:
        raise ScopeWorkflowError("frozen_at cannot be before scope_cutoff")
    if mode not in MODES:
        raise ScopeWorkflowError(f"unsupported scope mode: {mode}")

    source_path = Path(universe_path) if universe_path is not None else base / COMPANIES_FILE
    if not source_path.is_absolute():
        source_path = repository_root / source_path
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise ScopeWorkflowError(f"universe source is missing: {source_path}")
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    companies = read_jsonl(source_path)
    screening = read_jsonl(base / SCREENING_FILE)
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    company_by_symbol = _unique_by_symbol(companies, "universe source")
    screening_by_symbol = _unique_by_symbol(screening, "screening")
    queue_by_symbol = _unique_by_symbol(queue, "research queue")

    scope_dir = base / "scopes" / run
    manifest_path = scope_dir / "manifest.json"
    intake_path = scope_dir / "baseline-intake.json"
    manifest_relative = _relative(manifest_path, repository_root)
    intake_relative = _relative(intake_path, repository_root)
    source_relative = _relative_or_absolute(source_path, repository_root)

    if manifest_path.exists():
        manifest_seal = verify_sealed(manifest_path)
        if manifest_seal.artifact_type != "all_a_scope_manifest":
            raise ScopeWorkflowError("scope manifest has an unexpected artifact type")
        manifest = _read_object(manifest_path)
        _validate_scope_manifest(manifest)
        if (
            manifest["run_id"] != run
            or manifest["mode"] != mode
            or manifest["scope_cutoff"] != cutoff.isoformat()
            or manifest["universe_source"]["path"] != source_relative
        ):
            raise ScopeWorkflowError(f"sealed scope conflicts with freeze request: {run}")
    else:
        members = []
        for symbol in sorted(company_by_symbol):
            company = company_by_symbol[symbol]
            screen = screening_by_symbol.get(symbol)
            partition, reason_codes = _partition(company, screen)
            terminal = _verified_current_screening_terminal(
                queue_by_symbol.get(symbol),
                root=base,
                repository_root=repository_root,
                symbol=symbol,
                scope_cutoff=cutoff,
            )
            members.append(
                {
                    "ordinal": len(members) + 1,
                    "symbol": symbol,
                    "ticker": _text(company.get("ticker"), f"{symbol}.ticker"),
                    "name": _text(company.get("name"), f"{symbol}.name"),
                    "exchange": _text(company.get("exchange"), f"{symbol}.exchange"),
                    "security_type": _text(company.get("security_type"), f"{symbol}.security_type"),
                    "listing_status": _text(
                        company.get("listing_status"), f"{symbol}.listing_status"
                    ),
                    "partition": partition,
                    "partition_reason_codes": reason_codes,
                    "current_protocol_terminal": terminal is not None,
                    "terminal_path": terminal[0] if terminal else None,
                    "terminal_sha256": terminal[1] if terminal else None,
                }
            )

        counts = _scope_counts(members)
        source_dates = sorted(
            {value for item in companies if isinstance((value := item.get("as_of")), str) and value}
        )
        sources = sorted(
            {
                value
                for item in companies
                if isinstance((value := item.get("source")), str) and value
            }
        )
        manifest = {
            "schema_version": 1,
            "run_id": run,
            "market": "CN",
            "mode": mode,
            "scope_cutoff": cutoff.isoformat(),
            "frozen_at": frozen.isoformat(),
            "universe_source": {
                "path": source_relative,
                "sha256": source_sha256,
                "byte_size": len(source_bytes),
                "record_count": len(companies),
                "as_of_values": source_dates,
                "sources": sources,
            },
            "protocol": {
                "manager_screen": "manager_screen.schema_v1",
                "legacy_rapid_triage": "rapid_triage.schema_v2.read_only",
                "baseline_definition": (
                    "eligible or exception member without a validly sealed manager-screen "
                    "terminal or a legacy schema-v2 rapid-triage terminal at scope freeze"
                ),
            },
            "counts": counts,
            "members": members,
            "conservation": {
                "equation": "eligible + hard_excluded + exception = universe",
                "satisfied": (
                    counts["eligible"] + counts["hard_excluded"] + counts["exception"]
                    == counts["universe"]
                ),
            },
            "portfolio_action": None,
        }
        _validate_scope_manifest(manifest)
        manifest_seal = _seal_or_verify(
            manifest_path,
            manifest,
            artifact_type="all_a_scope_manifest",
            sealed_at=frozen,
        )

    members = list(manifest["members"])
    counts = dict(manifest["counts"])
    sealed_at = _parse_datetime(manifest["frozen_at"], "frozen_at")
    if intake_path.exists():
        intake_seal = verify_sealed(intake_path)
        if intake_seal.artifact_type != "all_a_baseline_intake":
            raise ScopeWorkflowError("baseline intake has an unexpected artifact type")
        intake = _read_object(intake_path)
        _validate_baseline_intake(intake, manifest)
        if intake["scope_manifest_sha256"] != manifest_seal.sha256:
            raise ScopeWorkflowError("baseline intake does not bind the scope manifest")
    else:
        intake_members = _build_baseline_intake_members(
            members,
            queue_by_symbol=queue_by_symbol,
        )
        intake = {
            "schema_version": 1,
            "run_id": run,
            "lane": "baseline",
            "scope_cutoff": cutoff.isoformat(),
            "scope_manifest_path": manifest_relative,
            "scope_manifest_sha256": manifest_seal.sha256,
            "selection_basis": (
                "scope membership minus valid manager-screen or legacy rapid-triage terminals; "
                "no investment score, factor rank, valuation, market cap, liquidity, "
                "profit sign, industry preference, or completion order was used"
            ),
            "counts": _intake_counts(intake_members),
            "members": intake_members,
            "portfolio_action": None,
        }
        _validate_baseline_intake(intake, manifest)
        intake_seal = _seal_or_verify(
            intake_path,
            intake,
            artifact_type="all_a_baseline_intake",
            sealed_at=sealed_at,
        )
    intake_counts = dict(intake["counts"])

    materialized_count = 0
    if apply_intake:
        materialized_count = _materialize_baseline_intake(
            intake,
            queue_by_symbol=queue_by_symbol,
            queue_path=base / RESEARCH_QUEUE_FILE,
            manifest_sha256=manifest_seal.sha256,
            intake_sha256=intake_seal.sha256,
        )

    event_path = scope_dir / "events.jsonl"
    event_relative = _relative(event_path, repository_root)
    event = {
        "event_id": f"scope-frozen:{manifest_seal.sha256}",
        "run_id": run,
        "event_type": "scope_frozen",
        "recorded_at": sealed_at.isoformat(),
        "scope_manifest_path": manifest_relative,
        "scope_manifest_sha256": manifest_seal.sha256,
        "baseline_intake_path": intake_relative,
        "baseline_intake_sha256": intake_seal.sha256,
    }
    _append_idempotent_event(event_path, event)
    _upsert_run_record(
        base / RUNS_FILE,
        {
            "run_id": run,
            "as_of": cutoff.date().isoformat(),
            "run_type": "all_a_continuous_research",
            "mode": mode,
            "scope_cutoff": cutoff.isoformat(),
            "started_at": cutoff.isoformat(),
            "finished_at": None,
            "status": "scope_frozen",
            "market_coverage_count": counts["universe"],
            "eligible_count": counts["eligible"],
            "hard_excluded_count": counts["hard_excluded"],
            "exception_count": counts["exception"],
            "current_protocol_terminal_count": counts["current_protocol_terminal"],
            "baseline_backlog_count": counts["baseline_backlog"],
            "scope_manifest_path": manifest_relative,
            "scope_manifest_sha256": manifest_seal.sha256,
            "baseline_intake_path": intake_relative,
            "baseline_intake_sha256": intake_seal.sha256,
            "event_log_path": event_relative,
            "failure_reason": None,
            "errors": [],
        },
    )

    return {
        "schema_version": 1,
        "run_id": run,
        "mode": mode,
        "scope_cutoff": cutoff.isoformat(),
        "scope_manifest_path": manifest_relative,
        "scope_manifest_sha256": manifest_seal.sha256,
        "baseline_intake_path": intake_relative,
        "baseline_intake_sha256": intake_seal.sha256,
        "counts": counts,
        "intake_counts": intake_counts,
        "materialized_count": materialized_count,
        "portfolio_action": None,
    }


def all_a_scope_status(*, root: str | Path, run_id: str) -> dict[str, Any]:
    base = Path(root)
    repository_root = base.parent.parent
    run = _run_id(run_id)
    scope_dir = base / "scopes" / run
    manifest_path = scope_dir / "manifest.json"
    intake_path = scope_dir / "baseline-intake.json"
    try:
        manifest_seal = verify_sealed(manifest_path)
        intake_seal = verify_sealed(intake_path)
    except (OSError, SealingError) as exc:
        raise ScopeWorkflowError(f"scope artifacts are not validly sealed: {run}") from exc
    if manifest_seal.artifact_type != "all_a_scope_manifest":
        raise ScopeWorkflowError("scope manifest has an unexpected artifact type")
    if intake_seal.artifact_type != "all_a_baseline_intake":
        raise ScopeWorkflowError("baseline intake has an unexpected artifact type")
    manifest = _read_object(manifest_path)
    intake = _read_object(intake_path)
    _validate_scope_manifest(manifest)
    _validate_baseline_intake(intake, manifest)
    if intake["scope_manifest_sha256"] != manifest_seal.sha256:
        raise ScopeWorkflowError("baseline intake does not bind the scope manifest")

    queue_by_symbol = _unique_by_symbol(read_jsonl(base / RESEARCH_QUEUE_FILE), "research queue")
    drift = []
    for item in intake["members"]:
        if item["materialization_action"] != "normalize_queue":
            continue
        queued = queue_by_symbol.get(item["symbol"])
        if (
            queued is None
            or queued.get("scope_run_id") != run
            or queued.get("scope_manifest_sha256") != manifest_seal.sha256
            or queued.get("baseline_intake_sha256") != intake_seal.sha256
        ):
            drift.append(item["symbol"])

    source = manifest["universe_source"]
    source_path = _resolve_repository_path(str(source["path"]), repository_root)
    current_source_sha256 = (
        hashlib.sha256(source_path.read_bytes()).hexdigest() if source_path.is_file() else None
    )
    trigger_checkpoint_status: dict[str, Any] | None = None
    if (scope_dir / "trigger-hit-checkpoint.json").exists():
        from .trigger_hits import verify_trigger_hit_checkpoint

        trigger_checkpoint_status = verify_trigger_hit_checkpoint(
            root=base,
            checkpoint_path=scope_dir / "trigger-hit-checkpoint.json",
        )
    lane_status: dict[str, Any] | None = None
    if (scope_dir / "lane-arbitration.json").exists():
        from .lane_arbitration import verify_lane_arbitration

        lane_status = verify_lane_arbitration(root=base, run_id=run)
    quality_status: dict[str, Any] | None = None
    if (scope_dir / "quality" / "identity" / "binding.json").exists():
        from .quality_workflow import scope_quality_status

        quality_status = scope_quality_status(root=base, run_id=run)
    return {
        "schema_version": 1,
        "run_id": run,
        "scope_manifest_path": _relative(manifest_path, repository_root),
        "scope_manifest_sha256": manifest_seal.sha256,
        "baseline_intake_path": _relative(intake_path, repository_root),
        "baseline_intake_sha256": intake_seal.sha256,
        "scope_cutoff": manifest["scope_cutoff"],
        "counts": manifest["counts"],
        "intake_counts": intake["counts"],
        "conservation_satisfied": manifest["conservation"]["satisfied"],
        "source_snapshot_matches_current_file": current_source_sha256 == source["sha256"],
        "queue_materialization_drift_count": len(drift),
        "queue_materialization_drift_sample": drift[:50],
        "queue_materialization_drift_sample_truncated": len(drift) > 50,
        "trigger_checkpoint": trigger_checkpoint_status,
        "lane_arbitration": lane_status,
        "scope_identity_quality_audit": quality_status,
        "ok": manifest["conservation"]["satisfied"] and not drift,
        "portfolio_action": None,
    }


def _build_baseline_intake_members(
    scope_members: list[dict[str, Any]],
    *,
    queue_by_symbol: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for member in scope_members:
        if member["partition"] == "hard_excluded" or member["current_protocol_terminal"]:
            continue
        queued = queue_by_symbol.get(member["symbol"])
        if member["partition"] == "exception":
            action = "manual_identity_review"
        elif queued is not None and (
            queued.get("status") == "running" or queued.get("task_type") in PROTECTED_TASK_TYPES
        ):
            action = "defer_active_or_deeper_stage"
        else:
            action = "normalize_queue"
        result.append(
            {
                "ordinal": len(result) + 1,
                "symbol": member["symbol"],
                "name": member["name"],
                "partition": member["partition"],
                "intake_reason_codes": [
                    "missing_current_manager_screen_terminal",
                    (
                        "missing_queue_row"
                        if queued is None
                        else f"prior_status:{queued.get('status')}"
                    ),
                ],
                "prior_task_type": queued.get("task_type") if queued else None,
                "prior_status": queued.get("status") if queued else None,
                "materialization_action": action,
            }
        )
    return result


def _materialize_baseline_intake(
    intake: Mapping[str, Any],
    *,
    queue_by_symbol: dict[str, dict[str, Any]],
    queue_path: Path,
    manifest_sha256: str,
    intake_sha256: str,
) -> int:
    changed = 0
    for member in intake["members"]:
        if member["materialization_action"] != "normalize_queue":
            continue
        symbol = str(member["symbol"])
        existing = queue_by_symbol.get(symbol)
        if existing is not None and (
            existing.get("scope_run_id") == intake["run_id"]
            and existing.get("scope_manifest_sha256") == manifest_sha256
            and existing.get("baseline_intake_sha256") == intake_sha256
        ):
            continue
        if existing is not None and (
            existing.get("status") == "running" or existing.get("task_type") in PROTECTED_TASK_TYPES
        ):
            raise ScopeWorkflowError(f"baseline intake became protected after freeze: {symbol}")
        history = list((existing or {}).get("stage_history") or [])
        history.append(
            {
                "stage": "scope_to_queue_intake",
                "status": "requires_rebaseline",
                "finished_at": intake["scope_cutoff"],
                "scope_run_id": intake["run_id"],
                "scope_manifest_sha256": manifest_sha256,
                "baseline_intake_sha256": intake_sha256,
            }
        )
        normalized = dict(existing or {})
        normalized.update(
            {
                "symbol": symbol,
                "name": member["name"],
                "task_type": "manager_screen",
                "priority": 3,
                "status": "requires_rebaseline",
                "reason": (
                    "Frozen baseline intake: the company lacks a valid current-protocol "
                    "manager-screen terminal. No investment ranking was applied."
                ),
                "target_company_dir": f"research/companies/CN/{symbol.split(':', 1)[1]}",
                "assigned_agent": None,
                "started_at": None,
                "finished_at": None,
                "result_path": None,
                "failure_reason": None,
                "next_action": (
                    "Freeze into a 100-200 company manager-screen batch; the same investment "
                    "manager Agent must judge the whole batch."
                ),
                "scope_run_id": intake["run_id"],
                "scope_manifest_path": intake["scope_manifest_path"],
                "scope_manifest_sha256": manifest_sha256,
                "baseline_intake_path": (
                    f"coverage/cn-a/scopes/{intake['run_id']}/baseline-intake.json"
                ),
                "baseline_intake_sha256": intake_sha256,
                "research_lane": "baseline",
                "intake_reason_codes": list(member["intake_reason_codes"]),
                "stage_history": history,
            }
        )
        for stale in (
            "allocation_sha256",
            "selected_by",
            "profile_cycle_id",
            "profile_evaluation_path",
            "profile_recorded_at",
            "profile_quick_selection_path",
            "profile_scoped_selection_path",
            "profile_priority_score",
            "triage_priority_score",
            "triage_allocation_decision",
            "triage_selection_reason",
            "triage_review_mode",
            "effort_budget_hours",
            "preceding_stage",
            "stop_conditions",
            "triage_cycle_id",
            "triage_disposition",
            "triage_selection_path",
            "triage_selection_sha256",
            "cohort_path",
            "cohort_sha256",
            "cohort_ordinal",
            "revisit_triggers",
            "manager_screen_run_id",
            "manager_screen_batch_id",
            "manager_screen_route",
            "manager_screen_result_path",
            "manager_screen_result_sha256",
            "decisive_question",
            "evidence_ids",
        ):
            normalized.pop(stale, None)
        queue_by_symbol[symbol] = normalized
        changed += 1
    if changed:
        write_jsonl(queue_path, list(queue_by_symbol.values()))
    return changed


def _verified_current_screening_terminal(
    queued: Mapping[str, Any] | None,
    *,
    root: Path,
    repository_root: Path,
    symbol: str,
    scope_cutoff: dt.datetime,
) -> tuple[str, str] | None:
    from .manager_screening import verify_manager_screen_terminal

    manager_terminal = verify_manager_screen_terminal(
        root=root,
        queued=queued,
        symbol=symbol,
        scope_cutoff=scope_cutoff,
    )
    if manager_terminal is not None:
        return manager_terminal
    return _verified_rapid_triage_terminal(
        queued,
        repository_root=repository_root,
        symbol=symbol,
        scope_cutoff=scope_cutoff,
    )


def _verified_rapid_triage_terminal(
    queued: Mapping[str, Any] | None,
    *,
    repository_root: Path,
    symbol: str,
    scope_cutoff: dt.datetime,
) -> tuple[str, str] | None:
    if queued is None:
        return None
    candidate_paths: list[str] = []
    history = queued.get("stage_history")
    if isinstance(history, list):
        for event in reversed(history):
            if (
                isinstance(event, Mapping)
                and event.get("stage") == "rapid_triage"
                and event.get("status") == "completed"
                and isinstance(event.get("result_path"), str)
            ):
                candidate_paths.append(str(event["result_path"]))
    if queued.get("task_type") == "rapid_triage" and queued.get("status") == "completed":
        if isinstance(queued.get("result_path"), str):
            candidate_paths.append(str(queued["result_path"]))
    for relative in dict.fromkeys(candidate_paths):
        path = _resolve_repository_path(relative, repository_root)
        try:
            sealed = verify_sealed(path)
            package = _read_object(path)
            package = validate_rapid_triage_package(
                package,
                recorded_at=sealed.sealed_at,
            )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if sealed.artifact_type != "rapid_triage_package":
            continue
        if package.get("symbol") != symbol:
            continue
        try:
            information_cutoff = dt.datetime.fromisoformat(str(package.get("information_cutoff")))
        except ValueError:
            continue
        if information_cutoff.tzinfo is None or information_cutoff > scope_cutoff:
            continue
        meta_path = (
            repository_root
            / "research"
            / "companies"
            / "CN"
            / symbol.split(":", 1)[1]
            / "meta.json"
        )
        try:
            meta = _read_object(meta_path)
            latest = meta["research"]["latest_rapid_triage"]
            report_path = meta_path.parent / latest["report_path"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
        if (
            meta.get("schema_version") != 2
            or meta.get("identity", {}).get("symbol") != symbol
            or latest.get("source_package_path") != relative
            or latest.get("source_package_sha256") != sealed.sha256
            or not report_path.is_file()
            or meta.get("reports", {}).get("latest_by_type", {}).get("rapid_triage")
            != latest.get("report_path")
        ):
            continue
        return _relative(path, repository_root), sealed.sha256
    return None


def _partition(
    company: Mapping[str, Any], screen: Mapping[str, Any] | None
) -> tuple[str, list[str]]:
    decision = screen.get("decision") if screen else None
    security_type = company.get("security_type")
    listing_status = company.get("listing_status")
    if security_type != "common_stock":
        return "hard_excluded", [f"security_type:{security_type}"]
    if listing_status != "listed":
        return "hard_excluded", [f"listing_status:{listing_status}"]
    if decision in HARD_EXCLUSION_DECISIONS:
        return "hard_excluded", [f"screening_decision:{decision}"]
    if screen is None:
        return "exception", ["missing_screening_row"]
    if decision in EXCEPTION_DECISIONS:
        return "exception", [f"screening_decision:{decision}"]
    return "eligible", ["listed_common_stock"]


def _scope_counts(members: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "universe": len(members),
        "eligible": 0,
        "hard_excluded": 0,
        "exception": 0,
        "current_protocol_terminal": 0,
        "baseline_backlog": 0,
    }
    for member in members:
        counts[member["partition"]] += 1
        if member["current_protocol_terminal"]:
            counts["current_protocol_terminal"] += 1
        elif member["partition"] != "hard_excluded":
            counts["baseline_backlog"] += 1
    return counts


def _intake_counts(members: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(members),
        "normalize_queue": 0,
        "manual_identity_review": 0,
        "defer_active_or_deeper_stage": 0,
    }
    for member in members:
        counts[member["materialization_action"]] += 1
    return counts


def _validate_scope_manifest(payload: Mapping[str, Any]) -> None:
    if set(payload) != SCOPE_KEYS or payload.get("schema_version") != 1:
        raise ScopeWorkflowError("scope manifest fields do not match the v1 contract")
    _run_id(payload.get("run_id"))
    if payload.get("market") != "CN" or payload.get("mode") not in MODES:
        raise ScopeWorkflowError("scope manifest market or mode is invalid")
    _parse_datetime(payload.get("scope_cutoff"), "scope_cutoff")
    _parse_datetime(payload.get("frozen_at"), "frozen_at")
    if payload.get("portfolio_action") is not None:
        raise ScopeWorkflowError("scope manifest cannot contain portfolio action")
    members = payload.get("members")
    if not isinstance(members, list) or not members:
        raise ScopeWorkflowError("scope manifest members must not be empty")
    symbols = []
    for ordinal, member in enumerate(members, 1):
        if not isinstance(member, Mapping) or member.get("ordinal") != ordinal:
            raise ScopeWorkflowError("scope manifest member ordinal is invalid")
        symbol = _symbol(member.get("symbol"))
        symbols.append(symbol)
        if member.get("partition") not in {"eligible", "hard_excluded", "exception"}:
            raise ScopeWorkflowError(f"scope partition is invalid: {symbol}")
    if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
        raise ScopeWorkflowError("scope symbols must be unique and stable-sorted")
    counts = _scope_counts([dict(item) for item in members])
    if payload.get("counts") != counts:
        raise ScopeWorkflowError("scope counts do not match members")
    if not payload.get("conservation", {}).get("satisfied"):
        raise ScopeWorkflowError("scope conservation is not satisfied")


def _validate_baseline_intake(intake: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    if set(intake) != INTAKE_KEYS or intake.get("schema_version") != 1:
        raise ScopeWorkflowError("baseline intake fields do not match the v1 contract")
    if intake.get("run_id") != manifest.get("run_id") or intake.get("lane") != "baseline":
        raise ScopeWorkflowError("baseline intake run or lane is invalid")
    if intake.get("portfolio_action") is not None:
        raise ScopeWorkflowError("baseline intake cannot contain portfolio action")
    members = intake.get("members")
    if not isinstance(members, list):
        raise ScopeWorkflowError("baseline intake members must be an array")
    symbols = []
    for ordinal, member in enumerate(members, 1):
        if not isinstance(member, Mapping) or member.get("ordinal") != ordinal:
            raise ScopeWorkflowError("baseline intake member ordinal is invalid")
        symbols.append(_symbol(member.get("symbol")))
    if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
        raise ScopeWorkflowError("baseline intake symbols must be unique and stable-sorted")
    if intake.get("counts") != _intake_counts([dict(item) for item in members]):
        raise ScopeWorkflowError("baseline intake counts do not match members")
    expected = {
        item["symbol"]
        for item in manifest["members"]
        if item["partition"] != "hard_excluded" and not item["current_protocol_terminal"]
    }
    if set(symbols) != expected:
        raise ScopeWorkflowError("baseline intake does not conserve the frozen scope backlog")


def _seal_or_verify(
    path: Path,
    payload: Mapping[str, Any],
    *,
    artifact_type: str,
    sealed_at: dt.datetime,
):
    try:
        return seal_json(path, payload, artifact_type=artifact_type, sealed_at=sealed_at)
    except SealingError as exc:
        raise ScopeWorkflowError(str(exc)) from exc


def _append_idempotent_event(path: Path, event: dict[str, Any]) -> None:
    events = read_jsonl(path)
    existing = [item for item in events if item.get("event_id") == event["event_id"]]
    if existing:
        if len(existing) != 1 or existing[0] != event:
            raise ScopeWorkflowError(
                f"run event conflicts with existing ledger: {event['event_id']}"
            )
        return
    events.append(event)
    write_jsonl(path, events, sort_key="recorded_at")


def _upsert_run_record(path: Path, record: dict[str, Any]) -> None:
    raw_lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    parsed_lines: list[tuple[str, dict[str, Any]]] = []
    for line_no, line in enumerate(raw_lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScopeWorkflowError(f"invalid run ledger JSON at line {line_no}") from exc
        if not isinstance(value, dict):
            raise ScopeWorkflowError(f"run ledger row {line_no} must be an object")
        parsed_lines.append((line, value))
    existing = [item for _, item in parsed_lines if item.get("run_id") == record["run_id"]]
    if existing and any(
        item.get("run_type") != record["run_type"]
        or item.get("scope_manifest_sha256") != record["scope_manifest_sha256"]
        for item in existing
    ):
        raise ScopeWorkflowError(f"run ledger conflicts with frozen scope: {record['run_id']}")
    encoded_record = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    output: list[str] = []
    replaced = False
    for original, item in parsed_lines:
        if item.get("run_id") == record["run_id"]:
            if not replaced:
                output.append(encoded_record)
                replaced = True
            continue
        output.append(original)
    if not replaced:
        output.append(encoded_record)
    atomic_write_bytes(path, ("\n".join(output) + "\n").encode("utf-8"))


def _unique_by_symbol(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {}
    for record in records:
        symbol = _symbol(record.get("symbol"))
        if symbol in result:
            raise ScopeWorkflowError(f"duplicate symbol in {label}: {symbol}")
        result[symbol] = record
    return result


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ScopeWorkflowError(f"JSON artifact must be an object: {path}")
    return value


def _resolve_repository_path(value: str, repository_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repository_root / path


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ScopeWorkflowError(f"artifact must be inside the repository: {path}") from exc


def _relative_or_absolute(path: Path, repository_root: Path) -> str:
    try:
        return path.relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise ScopeWorkflowError("run_id is invalid")
    return value


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not SYMBOL_RE.fullmatch(value):
        raise ScopeWorkflowError(f"symbol is invalid: {value}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScopeWorkflowError(f"{label} must be a non-empty string")
    return value.strip()


def _aware(value: dt.datetime, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ScopeWorkflowError(f"{label} must include timezone information")
    return value


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ScopeWorkflowError(f"{label} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ScopeWorkflowError(f"{label} must be an ISO timestamp") from exc
    return _aware(parsed, label)
