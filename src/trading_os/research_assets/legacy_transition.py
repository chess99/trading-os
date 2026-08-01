from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .company import AssetValidationError, validate_company_dir
from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .manager_screen_terminal_governance import (
    ManagerScreenTerminalGovernanceError,
    manager_screen_terminal_governance_locked,
    require_manager_screen_terminal_governance_open,
)
from .sealing import (
    SealedArtifact,
    SealingError,
    atomic_write_bytes,
    canonical_json_bytes,
    seal_json,
    verify_sealed,
)

TRANSITION_ID = "legacy-transition-001"
ROUTES = {"pass", "watch", "send_to_analyst"}
CONFIDENCES = {"low", "medium", "high"}
FORMAL_STAGES = {
    "quick_profile": 1,
    "targeted_followup": 2,
    "scoped_research": 3,
    "deep_research": 4,
}
LIVE_LEGACY_FIELDS = (
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
    "triage_cycle_id",
    "triage_disposition",
    "triage_selection_path",
    "triage_selection_sha256",
    "cohort_path",
    "cohort_sha256",
    "cohort_ordinal",
)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")


class LegacyTransitionError(ValueError):
    """Raised when the one-time legacy transition cannot be verified or applied."""


def _require_terminal_governance_open(
    *,
    base: Path,
    run_id: str,
    operation: str,
) -> None:
    try:
        require_manager_screen_terminal_governance_open(
            root=base,
            run_id=run_id,
            operation=operation,
        )
    except ManagerScreenTerminalGovernanceError as exc:
        raise LegacyTransitionError(str(exc)) from exc


def _terminal_governance_locked(*, base: Path, run_id: str) -> bool:
    try:
        return manager_screen_terminal_governance_locked(
            root=base,
            run_id=run_id,
        )
    except ManagerScreenTerminalGovernanceError as exc:
        raise LegacyTransitionError(str(exc)) from exc


@serialized_coverage_write
def freeze_legacy_transition(
    *,
    root: str | Path,
    run_id: str,
    classification: Mapping[str, Any],
    frozen_at: dt.datetime,
) -> dict[str, Any]:
    """Freeze the complete legacy population into adoption/rescreen/defer actions."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    frozen = _aware(frozen_at, "frozen_at")
    normalized = _normalize_classification(classification)
    scope = _load_scope(base=base, run_id=run, repository_root=repository_root)
    if frozen < _parse_datetime(scope["manifest"]["scope_cutoff"], "scope_cutoff"):
        raise LegacyTransitionError("frozen_at cannot be before the scope cutoff")
    transition_dir = base / "manager-screen" / run / TRANSITION_ID
    plan_path = transition_dir / "plan.json"
    packet_path = transition_dir / "packet.json"
    if plan_path.exists() and packet_path.exists():
        verified = _verify_transition_dir(
            transition_dir,
            repository_root=repository_root,
            require_packet=True,
            require_result=False,
        )
        if verified["plan"]["frozen_at"] != frozen.isoformat() or not _classification_matches_plan(
            normalized,
            plan=verified["plan"],
        ):
            raise LegacyTransitionError("sealed legacy transition plan is immutable")
        return _freeze_summary(
            plan=verified["plan"],
            plan_path=plan_path,
            plan_seal=verified["plan_seal"],
            packet_path=packet_path,
            packet_seal=verified["packet_seal"],
            repository_root=repository_root,
        )

    _require_terminal_governance_open(
        base=base,
        run_id=run,
        operation="new legacy transition plan or packet",
    )

    queue = _unique_by_symbol(read_jsonl(base / RESEARCH_QUEUE_FILE), "research queue")
    expected_terminal = {
        item["symbol"]: item
        for item in scope["manifest"]["members"]
        if item.get("current_protocol_terminal") is True
    }
    expected_deferred = {
        item["symbol"]: item
        for item in scope["intake"]["members"]
        if item.get("materialization_action") == "defer_active_or_deeper_stage"
    }
    if set(expected_terminal) & set(expected_deferred):
        raise LegacyTransitionError(
            "sealed legacy terminal and deferred populations must not overlap"
        )
    expected = set(expected_terminal) | set(expected_deferred)
    classified = (
        set(normalized["adoption"]) | set(normalized["rescreen"]) | set(normalized["defer_active"])
    )
    if classified != expected:
        missing = sorted(expected - classified)
        unexpected = sorted(classified - expected)
        raise LegacyTransitionError(
            "classification does not conserve the sealed legacy population; "
            f"missing={missing}, unexpected={unexpected}"
        )

    bridge_by_symbol = {item["symbol"]: item for item in normalized["legacy_bridges"]}
    members: list[dict[str, Any]] = []
    for action in ("adoption", "rescreen", "defer_active"):
        for symbol in normalized[action]:
            current = queue.get(symbol)
            if current is None:
                raise LegacyTransitionError(f"research queue is missing {symbol}")
            terminal = expected_terminal.get(symbol)
            _validate_transition_action_state(
                action=action,
                symbol=symbol,
                queue_record=current,
                is_legacy_terminal=terminal is not None,
            )

            legacy_terminal = (
                _terminal_binding(
                    member=terminal,
                    repository_root=repository_root,
                )
                if terminal is not None
                else None
            )
            formal_source = None
            company_meta = None
            high_watermark = _stage_high_watermark(current)
            if action == "adoption":
                bridge = bridge_by_symbol.get(symbol)
                formal_source = (
                    _legacy_bridge_binding(
                        symbol=symbol,
                        queue_record=current,
                        bridge=bridge,
                        repository_root=repository_root,
                    )
                    if bridge is not None
                    else _sealed_formal_binding(
                        symbol=symbol,
                        queue_record=current,
                        repository_root=repository_root,
                    )
                )
                company_meta = _rebaseline_meta_binding(
                    symbol=symbol,
                    queue_record=current,
                    repository_root=repository_root,
                )
            elif symbol in bridge_by_symbol:
                raise LegacyTransitionError(f"legacy bridge is only valid for adoption: {symbol}")

            members.append(
                {
                    "ordinal": len(members) + 1,
                    "symbol": symbol,
                    "name": _text(current.get("name"), f"{symbol}.name"),
                    "action": action,
                    "source_population": (
                        "legacy_terminal" if terminal is not None else "frozen_deferred"
                    ),
                    "queue_record_sha256": _payload_sha256(current),
                    "queue_state": {
                        "task_type": current.get("task_type"),
                        "status": current.get("status"),
                        "result_path": current.get("result_path"),
                    },
                    "research_stage_high_watermark": high_watermark,
                    "legacy_terminal": legacy_terminal,
                    "formal_source": formal_source,
                    "company_meta": company_meta,
                }
            )

    unused_bridges = sorted(set(bridge_by_symbol) - set(normalized["adoption"]))
    if unused_bridges:
        raise LegacyTransitionError(f"legacy bridges are not adoption members: {unused_bridges}")

    plan = {
        "schema_version": 1,
        "run_id": run,
        "transition_id": TRANSITION_ID,
        "frozen_at": frozen.isoformat(),
        "scope": {
            "manifest_path": _relative(scope["manifest_path"], repository_root),
            "manifest_sha256": scope["manifest_seal"].sha256,
            "baseline_intake_path": _relative(scope["intake_path"], repository_root),
            "baseline_intake_sha256": scope["intake_seal"].sha256,
        },
        "classification": {
            "adoption": len(normalized["adoption"]),
            "rescreen": len(normalized["rescreen"]),
            "defer_active": len(normalized["defer_active"]),
            "total": len(members),
        },
        "members": members,
        "portfolio_action": None,
    }
    _validate_plan(plan)

    if plan_path.exists():
        verified = _verify_transition_dir(
            transition_dir,
            repository_root=repository_root,
            require_packet=False,
            require_result=False,
        )
        if verified["plan"] != plan:
            raise LegacyTransitionError("sealed legacy transition plan is immutable")
        plan_seal = verified["plan_seal"]
    else:
        plan_seal = seal_json(
            plan_path,
            plan,
            artifact_type="manager_screen_legacy_transition_plan",
            sealed_at=frozen,
        )

    packet = _build_packet(
        plan=plan,
        plan_path=plan_path,
        plan_sha256=plan_seal.sha256,
        queue=queue,
        repository_root=repository_root,
    )
    if packet_path.exists():
        verified = _verify_transition_dir(
            transition_dir,
            repository_root=repository_root,
            require_packet=True,
            require_result=False,
        )
        if verified["packet"] != packet:
            raise LegacyTransitionError("sealed legacy transition packet is immutable")
        packet_seal = verified["packet_seal"]
    else:
        packet_seal = seal_json(
            packet_path,
            packet,
            artifact_type="manager_screen_legacy_transition_packet",
            sealed_at=frozen,
        )
    return _freeze_summary(
        plan=plan,
        plan_path=plan_path,
        plan_seal=plan_seal,
        packet_path=packet_path,
        packet_seal=packet_seal,
        repository_root=repository_root,
    )


@serialized_coverage_write
def record_legacy_transition(
    *,
    root: str | Path,
    run_id: str,
    submission: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Seal manager adoption routes and materialize the one-time transition."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    recorded = _aware(recorded_at, "recorded_at")
    transition_dir = base / "manager-screen" / run / TRANSITION_ID
    verified = _verify_transition_dir(
        transition_dir,
        repository_root=repository_root,
        require_packet=True,
        require_result=False,
    )
    plan = verified["plan"]
    packet = verified["packet"]
    if plan["run_id"] != run:
        raise LegacyTransitionError("transition path does not match run_id")
    if recorded < _parse_datetime(plan["frozen_at"], "plan frozen_at"):
        raise LegacyTransitionError("recorded_at cannot be before frozen_at")
    normalized = _normalize_submission(submission, plan=plan)
    result_path = transition_dir / "result.json"

    if result_path.exists():
        complete = _verify_transition_dir(
            transition_dir,
            repository_root=repository_root,
            require_packet=True,
            require_result=True,
        )
        existing = complete["result"]
        if any(existing[key] != normalized[key] for key in ("manager", "decisions")):
            raise LegacyTransitionError("sealed legacy transition result is immutable")
        result_seal = complete["result_seal"]
        if not _terminal_governance_locked(base=base, run_id=run):
            _materialize(
                base=base,
                repository_root=repository_root,
                plan=plan,
                result=existing,
                result_path=result_path,
                result_sha256=result_seal.sha256,
            )
        return _record_summary(
            result=existing,
            result_path=result_path,
            result_seal=result_seal,
            repository_root=repository_root,
        )

    _require_terminal_governance_open(
        base=base,
        run_id=run,
        operation="new legacy transition result",
    )

    _preflight_materialization(base=base, plan=plan)
    result = {
        "schema_version": 1,
        "run_id": run,
        "transition_id": TRANSITION_ID,
        "recorded_at": recorded.isoformat(),
        "plan_path": _relative(verified["plan_path"], repository_root),
        "plan_sha256": verified["plan_seal"].sha256,
        "packet_path": _relative(verified["packet_path"], repository_root),
        "packet_sha256": verified["packet_seal"].sha256,
        "manager": normalized["manager"],
        "decisions": normalized["decisions"],
        "releases": [
            member["symbol"] for member in plan["members"] if member["action"] == "rescreen"
        ],
        "deferred_unchanged": [
            member["symbol"] for member in plan["members"] if member["action"] == "defer_active"
        ],
        "portfolio_action": None,
    }
    _validate_result(
        result,
        plan=plan,
        packet=packet,
        plan_sha256=verified["plan_seal"].sha256,
        packet_sha256=verified["packet_seal"].sha256,
    )
    result_seal = seal_json(
        result_path,
        result,
        artifact_type="manager_screen_legacy_transition_result",
        sealed_at=recorded,
    )
    _materialize(
        base=base,
        repository_root=repository_root,
        plan=plan,
        result=result,
        result_path=result_path,
        result_sha256=result_seal.sha256,
    )
    return _record_summary(
        result=result,
        result_path=result_path,
        result_seal=result_seal,
        repository_root=repository_root,
    )


def legacy_transition_status(
    *,
    root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Verify all transition seals and report materialization progress."""

    base = Path(root)
    repository_root = base.parent.parent
    run = _identifier(run_id, "run_id")
    transition_dir = base / "manager-screen" / run / TRANSITION_ID
    verified = _verify_transition_dir(
        transition_dir,
        repository_root=repository_root,
        require_packet=True,
        require_result=False,
    )
    plan = verified["plan"]
    queue = _unique_by_symbol(read_jsonl(base / RESEARCH_QUEUE_FILE), "research queue")
    result = verified.get("result")
    materialized = Counter()
    meta_sync_planned = sum(
        1 for member in plan["members"] if member.get("company_meta") is not None
    )
    meta_sync_completed = 0
    for member in plan["members"]:
        company_meta = member.get("company_meta")
        if company_meta is None:
            continue
        meta_path = _safe_repository_file(
            company_meta["path"],
            repository_root,
        )
        if _meta_already_transitioned(_read_object(meta_path)):
            meta_sync_completed += 1
    if result is not None:
        result_sha256 = verified["result_seal"].sha256
        for member in plan["members"]:
            current = queue.get(member["symbol"]) or {}
            if (
                current.get("legacy_transition_result_sha256") == result_sha256
                and current.get("legacy_transition_action") == member["action"]
            ):
                materialized[member["action"]] += 1
            elif member["action"] == "defer_active":
                materialized["defer_active"] += 1
    return {
        "schema_version": 1,
        "run_id": run,
        "transition_id": TRANSITION_ID,
        "state": "recorded" if result is not None else "frozen",
        "classification": dict(plan["classification"]),
        "materialized": {
            action: materialized[action] for action in ("adoption", "rescreen", "defer_active")
        },
        "company_meta_sync": {
            "planned": meta_sync_planned,
            "completed": meta_sync_completed,
        },
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


def _validate_transition_action_state(
    *,
    action: str,
    symbol: str,
    queue_record: Mapping[str, Any],
    is_legacy_terminal: bool,
) -> None:
    task_type = queue_record.get("task_type")
    status = queue_record.get("status")
    if action == "adoption":
        if task_type not in FORMAL_STAGES or status != "completed":
            raise LegacyTransitionError(f"adoption requires a completed formal task: {symbol}")
        return
    if not is_legacy_terminal:
        raise LegacyTransitionError(
            f"{action} is only valid for a sealed legacy terminal: {symbol}"
        )
    if action == "rescreen":
        if task_type != "rapid_triage" or status != "completed":
            raise LegacyTransitionError(f"rescreen requires rapid_triage/completed: {symbol}")
        return
    if action == "defer_active":
        if task_type not in FORMAL_STAGES or status not in {"pending", "running"}:
            raise LegacyTransitionError(
                f"defer_active requires a pending or running formal task: {symbol}"
            )
        return
    raise LegacyTransitionError(f"invalid legacy transition action: {action}")


def _normalize_classification(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "adoption",
        "rescreen",
        "defer_active",
        "legacy_bridges",
    }:
        raise LegacyTransitionError("classification fields do not match v1")
    if value.get("schema_version") != 1:
        raise LegacyTransitionError("classification schema_version must be 1")
    result: dict[str, Any] = {"schema_version": 1}
    seen: set[str] = set()
    for action in ("adoption", "rescreen", "defer_active"):
        items = value.get(action)
        if not isinstance(items, list):
            raise LegacyTransitionError(f"classification.{action} must be an array")
        symbols = sorted(_symbol(item) for item in items)
        if len(symbols) != len(set(symbols)):
            raise LegacyTransitionError(f"classification.{action} contains duplicates")
        overlap = seen & set(symbols)
        if overlap:
            raise LegacyTransitionError(f"classification actions overlap: {sorted(overlap)}")
        seen.update(symbols)
        result[action] = symbols
    bridges = value.get("legacy_bridges")
    if not isinstance(bridges, list):
        raise LegacyTransitionError("classification.legacy_bridges must be an array")
    normalized_bridges = []
    bridge_symbols: set[str] = set()
    bridge_keys = {
        "symbol",
        "report_path",
        "report_sha256",
        "meta_path",
        "scoped_profile_path",
        "scoped_profile_sha256",
        "scoped_evaluation_path",
        "scoped_evaluation_sha256",
    }
    for item in bridges:
        if not isinstance(item, Mapping) or set(item) != bridge_keys:
            raise LegacyTransitionError("legacy bridge fields do not match v1")
        symbol = _symbol(item.get("symbol"))
        if symbol in bridge_symbols:
            raise LegacyTransitionError(f"duplicate legacy bridge: {symbol}")
        bridge_symbols.add(symbol)
        normalized_bridges.append(
            {
                "symbol": symbol,
                "report_path": _text(item.get("report_path"), "bridge.report_path"),
                "report_sha256": _sha256(item.get("report_sha256"), "bridge.report_sha256"),
                "meta_path": _text(item.get("meta_path"), "bridge.meta_path"),
                "scoped_profile_path": _text(
                    item.get("scoped_profile_path"), "bridge.scoped_profile_path"
                ),
                "scoped_profile_sha256": _sha256(
                    item.get("scoped_profile_sha256"),
                    "bridge.scoped_profile_sha256",
                ),
                "scoped_evaluation_path": _text(
                    item.get("scoped_evaluation_path"),
                    "bridge.scoped_evaluation_path",
                ),
                "scoped_evaluation_sha256": _sha256(
                    item.get("scoped_evaluation_sha256"),
                    "bridge.scoped_evaluation_sha256",
                ),
            }
        )
    result["legacy_bridges"] = sorted(normalized_bridges, key=lambda item: item["symbol"])
    return result


def _classification_matches_plan(
    classification: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
) -> bool:
    actions = {
        action: sorted(item["symbol"] for item in plan["members"] if item["action"] == action)
        for action in ("adoption", "rescreen", "defer_active")
    }
    if any(actions[action] != classification[action] for action in actions):
        return False
    planned_bridges = {}
    for member in plan["members"]:
        source = member.get("formal_source")
        if not isinstance(source, Mapping) or source.get("kind") != "legacy_report_bridge":
            continue
        planned_bridges[member["symbol"]] = {
            "symbol": member["symbol"],
            "report_path": source["report_path"],
            "report_sha256": source["report_sha256"],
            "meta_path": source["meta_path"],
            "scoped_profile_path": source["scoped_profile_path"],
            "scoped_profile_sha256": source["scoped_profile_sha256"],
            "scoped_evaluation_path": source["scoped_evaluation_path"],
            "scoped_evaluation_sha256": source["scoped_evaluation_sha256"],
        }
    requested_bridges = {item["symbol"]: dict(item) for item in classification["legacy_bridges"]}
    return planned_bridges == requested_bridges


def _load_scope(
    *,
    base: Path,
    run_id: str,
    repository_root: Path,
) -> dict[str, Any]:
    scope_dir = base / "scopes" / run_id
    manifest_path = scope_dir / "manifest.json"
    intake_path = scope_dir / "baseline-intake.json"
    try:
        manifest_seal = verify_sealed(manifest_path)
        intake_seal = verify_sealed(intake_path)
    except (OSError, SealingError) as exc:
        raise LegacyTransitionError("scope manifest or baseline intake is not sealed") from exc
    if manifest_seal.artifact_type != "all_a_scope_manifest":
        raise LegacyTransitionError("scope manifest has an unexpected artifact type")
    if intake_seal.artifact_type != "all_a_baseline_intake":
        raise LegacyTransitionError("baseline intake has an unexpected artifact type")
    manifest = _read_object(manifest_path)
    intake = _read_object(intake_path)
    if manifest.get("run_id") != run_id or intake.get("run_id") != run_id:
        raise LegacyTransitionError("scope artifacts do not match run_id")
    expected_manifest_path = _relative(manifest_path, repository_root)
    if (
        intake.get("scope_manifest_path") != expected_manifest_path
        or intake.get("scope_manifest_sha256") != manifest_seal.sha256
    ):
        raise LegacyTransitionError("baseline intake does not bind the scope manifest")
    if not isinstance(manifest.get("members"), list) or not isinstance(intake.get("members"), list):
        raise LegacyTransitionError("scope member arrays are invalid")
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "manifest_seal": manifest_seal,
        "intake_path": intake_path,
        "intake": intake,
        "intake_seal": intake_seal,
    }


def _terminal_binding(
    *,
    member: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, str]:
    path = _safe_repository_file(member.get("terminal_path"), repository_root)
    expected_sha256 = _sha256(member.get("terminal_sha256"), "terminal_sha256")
    try:
        sealed = verify_sealed(path)
    except (OSError, SealingError) as exc:
        raise LegacyTransitionError(f"legacy terminal is not sealed: {path}") from exc
    if sealed.sha256 != expected_sha256:
        raise LegacyTransitionError(f"legacy terminal SHA mismatch: {path}")
    if sealed.artifact_type != "rapid_triage_package":
        raise LegacyTransitionError(f"legacy terminal artifact type is invalid: {path}")
    return {
        "path": _relative(path, repository_root),
        "sha256": sealed.sha256,
        "artifact_type": sealed.artifact_type,
    }


def _sealed_formal_binding(
    *,
    symbol: str,
    queue_record: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    stage = str(queue_record.get("task_type"))
    history = [
        item
        for item in queue_record.get("stage_history") or []
        if isinstance(item, Mapping)
        and item.get("stage") == stage
        and item.get("status") == "completed"
        and item.get("result_path")
        and item.get("evaluation_path")
    ]
    if not history:
        raise LegacyTransitionError(
            f"completed formal task lacks a sealed stage-history pair; "
            f"declare a verified legacy bridge if applicable: {symbol}"
        )
    source = history[-1]
    profile = _verify_reference(
        source.get("result_path"),
        repository_root=repository_root,
        label=f"{symbol}.profile",
    )
    evaluation = _verify_reference(
        source.get("evaluation_path"),
        repository_root=repository_root,
        label=f"{symbol}.evaluation",
    )
    if (
        profile.artifact_type != "quick_profile_package"
        or evaluation.artifact_type != "quick_profile_evaluation"
    ):
        raise LegacyTransitionError(f"formal artifact types do not match the queue stage: {symbol}")
    if queue_record.get("result_path") != source.get("evaluation_path"):
        raise LegacyTransitionError(
            f"queue result does not bind the current formal evaluation: {symbol}"
        )
    profile_payload = _read_object(profile.path)
    information_cutoff = _parse_datetime(
        profile_payload.get("profile", {}).get("information_cutoff"),
        f"{symbol}.formal information_cutoff",
    ).isoformat()
    return {
        "kind": "sealed_formal",
        "stage": stage,
        "information_cutoff": information_cutoff,
        "profile_path": _relative(profile.path, repository_root),
        "profile_sha256": profile.sha256,
        "profile_artifact_type": profile.artifact_type,
        "evaluation_path": _relative(evaluation.path, repository_root),
        "evaluation_sha256": evaluation.sha256,
        "evaluation_artifact_type": evaluation.artifact_type,
    }


def _legacy_bridge_binding(
    *,
    symbol: str,
    queue_record: Mapping[str, Any],
    bridge: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    if (
        queue_record.get("task_type") != "deep_research"
        or queue_record.get("status") != "completed"
    ):
        raise LegacyTransitionError(
            f"legacy report bridge requires deep_research/completed: {symbol}"
        )
    report_path = _safe_repository_file(bridge["report_path"], repository_root)
    actual_report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    if actual_report_sha256 != bridge["report_sha256"]:
        raise LegacyTransitionError(f"legacy report SHA mismatch: {symbol}")
    meta_path = _safe_repository_file(bridge["meta_path"], repository_root)
    meta = _read_object(meta_path)
    if meta.get("identity", {}).get("symbol") != symbol:
        raise LegacyTransitionError(f"legacy bridge meta symbol mismatch: {symbol}")
    relative_to_company = _relative(report_path, meta_path.parent)
    history = meta.get("reports", {}).get("history")
    matching = [
        item
        for item in history or []
        if isinstance(item, Mapping)
        and item.get("path") == relative_to_company
        and item.get("sha256") == actual_report_sha256
    ]
    if len(matching) != 1:
        raise LegacyTransitionError(
            f"legacy report is not uniquely bound by company meta: {symbol}"
        )
    target_company = _safe_repository_dir(queue_record.get("target_company_dir"), repository_root)
    queue_report = _safe_child_file(
        target_company,
        queue_record.get("result_path"),
        repository_root=repository_root,
    )
    if queue_report != report_path:
        raise LegacyTransitionError(f"queue does not bind the bridged legacy report: {symbol}")
    profile = _verify_reference(
        bridge["scoped_profile_path"],
        repository_root=repository_root,
        label=f"{symbol}.scoped_profile",
    )
    evaluation = _verify_reference(
        bridge["scoped_evaluation_path"],
        repository_root=repository_root,
        label=f"{symbol}.scoped_evaluation",
    )
    if (
        profile.sha256 != bridge["scoped_profile_sha256"]
        or evaluation.sha256 != bridge["scoped_evaluation_sha256"]
    ):
        raise LegacyTransitionError(f"legacy bridge scoped seal mismatch: {symbol}")
    if (
        profile.artifact_type != "quick_profile_package"
        or evaluation.artifact_type != "quick_profile_evaluation"
    ):
        raise LegacyTransitionError(f"legacy bridge scoped artifact types are invalid: {symbol}")
    scoped_history = [
        item
        for item in queue_record.get("stage_history") or []
        if isinstance(item, Mapping)
        and item.get("stage") == "scoped_research"
        and item.get("status") == "completed"
        and item.get("result_path") == bridge["scoped_profile_path"]
        and item.get("evaluation_path") == bridge["scoped_evaluation_path"]
    ]
    if not scoped_history:
        raise LegacyTransitionError(
            f"legacy bridge is not anchored in scoped stage history: {symbol}"
        )
    return {
        "kind": "legacy_report_bridge",
        "stage": "deep_research",
        "information_cutoff": _parse_datetime(
            meta.get("research", {}).get("information_cutoff"),
            f"{symbol}.legacy report information_cutoff",
        ).isoformat(),
        "report_path": _relative(report_path, repository_root),
        "report_sha256": actual_report_sha256,
        "meta_path": _relative(meta_path, repository_root),
        "meta_snapshot_sha256": hashlib.sha256(meta_path.read_bytes()).hexdigest(),
        "meta_report_id": matching[0].get("report_id"),
        "scoped_profile_path": _relative(profile.path, repository_root),
        "scoped_profile_sha256": profile.sha256,
        "scoped_profile_artifact_type": profile.artifact_type,
        "scoped_evaluation_path": _relative(evaluation.path, repository_root),
        "scoped_evaluation_sha256": evaluation.sha256,
        "scoped_evaluation_artifact_type": evaluation.artifact_type,
    }


def _rebaseline_meta_binding(
    *,
    symbol: str,
    queue_record: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any] | None:
    company_dir = _safe_repository_dir(
        queue_record.get("target_company_dir"),
        repository_root,
    )
    meta_path = company_dir / "meta.json"
    if not meta_path.is_file():
        raise LegacyTransitionError(f"company meta is missing for adoption: {symbol}")
    meta = _read_object(meta_path)
    if meta.get("identity", {}).get("symbol") != symbol:
        raise LegacyTransitionError(f"company meta symbol mismatch: {symbol}")
    research = meta.get("research")
    if not isinstance(research, Mapping):
        raise LegacyTransitionError(f"company research state is invalid: {symbol}")
    if not (
        research.get("coverage_status") == "requires_rebaseline"
        and research.get("rebaseline_required") is True
    ):
        return None
    try:
        validate_company_dir(company_dir)
    except AssetValidationError as exc:
        raise LegacyTransitionError(
            f"rebaseline company meta is invalid before adoption: {symbol}"
        ) from exc
    return {
        "path": _relative(meta_path, repository_root),
        "snapshot_sha256": hashlib.sha256(meta_path.read_bytes()).hexdigest(),
        "research_state": dict(research),
    }


def _build_packet(
    *,
    plan: Mapping[str, Any],
    plan_path: Path,
    plan_sha256: str,
    queue: Mapping[str, Mapping[str, Any]],
    repository_root: Path,
) -> dict[str, Any]:
    adoption = []
    for member in plan["members"]:
        if member["action"] != "adoption":
            continue
        adoption.append(
            {
                "symbol": member["symbol"],
                "name": member["name"],
                "source_population": member["source_population"],
                "queue_state": member["queue_state"],
                "queue_record_sha256": member["queue_record_sha256"],
                "research_stage_high_watermark": member["research_stage_high_watermark"],
                "legacy_terminal": member["legacy_terminal"],
                "formal_source": member["formal_source"],
                "evidence_ids": _transition_evidence_ids(member),
                "prior_reason": queue[member["symbol"]].get("reason"),
                "prior_next_action": queue[member["symbol"]].get("next_action"),
                "prior_revisit_triggers": queue[member["symbol"]].get("revisit_triggers") or [],
            }
        )
    return {
        "schema_version": 1,
        "run_id": plan["run_id"],
        "transition_id": TRANSITION_ID,
        "created_at": plan["frozen_at"],
        "plan_path": _relative(plan_path, repository_root),
        "plan_sha256": plan_sha256,
        "instructions": {
            "role": "one manager adopts completed formal research without rerunning screening",
            "routes": ["pass", "watch", "send_to_analyst"],
            "requirements": [
                "read the bound formal source before choosing a route",
                "choose one explicit route for every adoption member",
                "do not map legacy price_watch or reassign_or_stop automatically",
                "do not downgrade or overwrite the formal research high-watermark",
            ],
        },
        "adoption_dossiers": adoption,
        "rescreen_symbols": [
            item["symbol"] for item in plan["members"] if item["action"] == "rescreen"
        ],
        "defer_active_symbols": [
            item["symbol"] for item in plan["members"] if item["action"] == "defer_active"
        ],
        "portfolio_action": None,
    }


def _normalize_submission(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "manager",
        "decisions",
    }:
        raise LegacyTransitionError("transition submission fields do not match v1")
    if value.get("schema_version") != 1:
        raise LegacyTransitionError("transition submission schema_version must be 1")
    manager = value.get("manager")
    if not isinstance(manager, Mapping) or set(manager) != {"agent", "model", "tools"}:
        raise LegacyTransitionError("manager fields do not match v1")
    tools = manager.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or not all(isinstance(item, str) and item.strip() for item in tools)
    ):
        raise LegacyTransitionError("manager.tools must be a non-empty string array")
    normalized_manager = {
        "agent": _text(manager.get("agent"), "manager.agent"),
        "model": _text(manager.get("model"), "manager.model"),
        "tools": list(tools),
    }
    decisions = value.get("decisions")
    if not isinstance(decisions, list):
        raise LegacyTransitionError("decisions must be an array")
    expected = {item["symbol"] for item in plan["members"] if item["action"] == "adoption"}
    adoption_members = {
        item["symbol"]: item for item in plan["members"] if item["action"] == "adoption"
    }
    normalized_decisions = []
    seen: set[str] = set()
    for item in decisions:
        if not isinstance(item, Mapping) or set(item) != {
            "symbol",
            "route",
            "one_line_reason",
            "decisive_question",
            "revisit_triggers",
            "confidence",
            "evidence_ids",
        }:
            raise LegacyTransitionError("adoption decision fields do not match v1")
        symbol = _symbol(item.get("symbol"))
        if symbol in seen:
            raise LegacyTransitionError(f"duplicate adoption decision: {symbol}")
        if symbol not in expected:
            raise LegacyTransitionError(f"decision is not an adoption member: {symbol}")
        seen.add(symbol)
        route = item.get("route")
        if route not in ROUTES:
            raise LegacyTransitionError(f"invalid adoption route: {route}")
        confidence = item.get("confidence")
        if confidence not in CONFIDENCES:
            raise LegacyTransitionError(f"invalid adoption confidence: {confidence}")
        evidence_ids = item.get("evidence_ids")
        if (
            not isinstance(evidence_ids, list)
            or not evidence_ids
            or not all(isinstance(value, str) and value.strip() for value in evidence_ids)
        ):
            raise LegacyTransitionError(f"{symbol}.evidence_ids must be a non-empty string array")
        member = adoption_members[symbol]
        allowed_evidence = set(_transition_evidence_ids(member))
        unknown_evidence = set(evidence_ids) - allowed_evidence
        if unknown_evidence:
            raise LegacyTransitionError(
                f"{symbol}.evidence_ids are not bound by the transition packet: "
                f"{sorted(unknown_evidence)}"
            )
        triggers = item.get("revisit_triggers")
        if not isinstance(triggers, list):
            raise LegacyTransitionError(f"{symbol}.revisit_triggers must be an array")
        if route in {"pass", "watch"} and not triggers:
            raise LegacyTransitionError(f"{symbol}.{route} requires a revisit trigger")
        normalized_triggers = []
        for trigger in triggers:
            if not isinstance(trigger, Mapping) or set(trigger) != {
                "type",
                "condition",
                "reason",
            }:
                raise LegacyTransitionError(f"{symbol}.revisit trigger fields do not match v1")
            condition = trigger.get("condition")
            if not isinstance(condition, (str, Mapping)):
                raise LegacyTransitionError(
                    f"{symbol}.trigger.condition must be a string or object"
                )
            normalized_triggers.append(
                {
                    "type": _text(trigger.get("type"), f"{symbol}.trigger.type"),
                    "condition": (dict(condition) if isinstance(condition, Mapping) else condition),
                    "reason": _text(trigger.get("reason"), f"{symbol}.trigger.reason"),
                }
            )
        normalized_decisions.append(
            {
                "symbol": symbol,
                "route": route,
                "one_line_reason": _text(item.get("one_line_reason"), f"{symbol}.one_line_reason"),
                "decisive_question": _text(
                    item.get("decisive_question"), f"{symbol}.decisive_question"
                ),
                "revisit_triggers": normalized_triggers,
                "confidence": confidence,
                "evidence_ids": list(evidence_ids),
            }
        )
    if seen != expected:
        raise LegacyTransitionError("adoption decisions must cover exactly the adoption population")
    return {
        "manager": normalized_manager,
        "decisions": sorted(normalized_decisions, key=lambda item: item["symbol"]),
    }


def _materialize(
    *,
    base: Path,
    repository_root: Path,
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: Path,
    result_sha256: str,
) -> None:
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = _unique_by_symbol(read_jsonl(queue_path), "research queue")
    screening = _unique_by_symbol(read_jsonl(screening_path), "screening")
    result_relative = _relative(result_path, repository_root)
    decisions = {item["symbol"]: item for item in result["decisions"]}
    queue_changed = False
    screening_changed = False

    for member in plan["members"]:
        symbol = member["symbol"]
        action = member["action"]
        current = queue.get(symbol)
        if current is None:
            raise LegacyTransitionError(f"research queue is missing {symbol}")
        if action == "defer_active":
            continue
        already_materialized = (
            current.get("legacy_transition_result_sha256") == result_sha256
            and current.get("legacy_transition_action") == action
        )
        if already_materialized:
            if action == "adoption":
                screen = _adoption_screen(
                    member=member,
                    decision=decisions[symbol],
                    plan=plan,
                    result_relative=result_relative,
                    result_sha256=result_sha256,
                )
                existing_screen = screening.get(symbol)
                if (
                    _can_materialize_screen(existing_screen, result_relative)
                    and existing_screen != screen
                ):
                    screening[symbol] = screen
                    screening_changed = True
            continue
        if _payload_sha256(current) != member["queue_record_sha256"]:
            raise LegacyTransitionError(f"queue changed after transition freeze: {symbol}")
        updated = dict(current)
        history = list(updated.get("stage_history") or [])
        live_snapshot = {key: updated[key] for key in LIVE_LEGACY_FIELDS if key in updated}
        if live_snapshot:
            history.append(
                {
                    "stage": "legacy_transition_source_snapshot",
                    "status": "completed",
                    "finished_at": result["recorded_at"],
                    "run_id": plan["run_id"],
                    "transition_id": TRANSITION_ID,
                    "live_fields": live_snapshot,
                }
            )
        for field in LIVE_LEGACY_FIELDS:
            updated.pop(field, None)
        updated.update(
            {
                "legacy_transition_run_id": plan["run_id"],
                "legacy_transition_id": TRANSITION_ID,
                "legacy_transition_action": action,
                "legacy_transition_result_path": result_relative,
                "legacy_transition_result_sha256": result_sha256,
                "stage_history": history,
            }
        )
        high_watermark = member.get("research_stage_high_watermark")
        if high_watermark is not None:
            updated["research_stage_high_watermark"] = high_watermark

        if action == "rescreen":
            history.append(
                {
                    "stage": "legacy_transition",
                    "status": "completed",
                    "finished_at": result["recorded_at"],
                    "run_id": plan["run_id"],
                    "transition_id": TRANSITION_ID,
                    "action": "rescreen",
                    "result_path": result_relative,
                    "result_sha256": result_sha256,
                }
            )
            updated.update(
                {
                    "task_type": "manager_screen",
                    "status": "pending",
                    "reason": ("Released from legacy rapid-triage for ordinary manager-screen."),
                    "assigned_agent": None,
                    "started_at": None,
                    "finished_at": None,
                    "result_path": None,
                    "failure_reason": None,
                    "next_action": ("Wait for the ordinary whole-batch manager-screen workflow."),
                }
            )
            for field in ("effort_budget_hours", "preceding_stage", "stop_conditions"):
                updated.pop(field, None)
        else:
            decision = decisions[symbol]
            history.append(
                {
                    "stage": "manager_screen",
                    "status": "completed",
                    "finished_at": result["recorded_at"],
                    "run_id": plan["run_id"],
                    "batch_id": TRANSITION_ID,
                    "route": decision["route"],
                    "result_path": result_relative,
                    "result_sha256": result_sha256,
                    "adopted_formal_source": member["formal_source"],
                    "research_stage_high_watermark": high_watermark,
                }
            )
            updated.update(
                {
                    "manager_screen_run_id": plan["run_id"],
                    "manager_screen_batch_id": TRANSITION_ID,
                    "manager_screen_route": decision["route"],
                    "manager_screen_result_path": result_relative,
                    "manager_screen_result_sha256": result_sha256,
                    "decisive_question": decision["decisive_question"],
                    "evidence_ids": decision["evidence_ids"],
                    "revisit_triggers": decision["revisit_triggers"],
                    "manager_screen_confidence": decision["confidence"],
                }
            )
            if decision["route"] == "send_to_analyst":
                updated.update(
                    {
                        "reason": decision["one_line_reason"],
                        "failure_reason": None,
                        "next_action": (
                            "Await explicit manager approval before purchasing any "
                            "targeted, scoped, or deep research budget."
                        ),
                    }
                )
            screen = _adoption_screen(
                member=member,
                decision=decision,
                plan=plan,
                result_relative=result_relative,
                result_sha256=result_sha256,
            )
            existing_screen = screening.get(symbol)
            if (
                _can_materialize_screen(existing_screen, result_relative)
                and existing_screen != screen
            ):
                screening[symbol] = screen
                screening_changed = True
        queue[symbol] = updated
        queue_changed = True
    if queue_changed:
        write_jsonl(queue_path, list(queue.values()))
    if screening_changed:
        write_jsonl(screening_path, list(screening.values()))
    _materialize_company_meta(
        repository_root=repository_root,
        plan=plan,
        result=result,
    )


def _preflight_materialization(
    *,
    base: Path,
    plan: Mapping[str, Any],
) -> None:
    queue = _unique_by_symbol(
        read_jsonl(base / RESEARCH_QUEUE_FILE),
        "research queue",
    )
    for member in plan["members"]:
        current = queue.get(member["symbol"])
        if current is None:
            raise LegacyTransitionError(f"research queue is missing {member['symbol']}")
        if _payload_sha256(current) != member["queue_record_sha256"]:
            raise LegacyTransitionError(
                f"queue changed after transition freeze: {member['symbol']}"
            )
        company_meta = member.get("company_meta")
        if company_meta is not None:
            meta_path = _safe_repository_file(
                company_meta["path"],
                base.parent.parent,
            )
            if (
                hashlib.sha256(meta_path.read_bytes()).hexdigest()
                != company_meta["snapshot_sha256"]
            ):
                raise LegacyTransitionError(
                    f"company meta changed after transition freeze: {member['symbol']}"
                )


def _adoption_screen(
    *,
    member: Mapping[str, Any],
    decision: Mapping[str, Any],
    plan: Mapping[str, Any],
    result_relative: str,
    result_sha256: str,
) -> dict[str, Any]:
    screen_decision = {
        "pass": "catalog",
        "watch": "watch_only",
        "send_to_analyst": "profile_candidate",
    }[decision["route"]]
    return {
        "symbol": member["symbol"],
        "name": member["name"],
        "decision": screen_decision,
        "priority": None,
        "reason": decision["one_line_reason"],
        "evidence": [
            f"legacy_transition_result_sha256:{result_sha256}",
            _formal_evidence_token(member["formal_source"]),
        ],
        "next_action": {
            "pass": "Wait for an executable restart trigger.",
            "watch": "Reassess on price, filing, event, or thesis trigger.",
            "send_to_analyst": (
                "Await explicit manager approval before purchasing further research."
            ),
        }[decision["route"]],
        "manager_screen_run_id": plan["run_id"],
        "manager_screen_batch_id": TRANSITION_ID,
        "manager_screen_route": decision["route"],
        "manager_screen_result_path": result_relative,
        "manager_screen_result_sha256": result_sha256,
        "decisive_question": decision["decisive_question"],
        "confidence": decision["confidence"],
        "revisit_triggers": decision["revisit_triggers"],
    }


def _materialize_company_meta(
    *,
    repository_root: Path,
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    for member in plan["members"]:
        company_meta = member.get("company_meta")
        if member["action"] != "adoption" or company_meta is None:
            continue
        meta_path = _safe_repository_file(
            company_meta["path"],
            repository_root,
        )
        company_dir = meta_path.parent
        current_bytes = meta_path.read_bytes()
        current = _read_object(meta_path)
        if _meta_already_transitioned(current):
            continue
        if hashlib.sha256(current_bytes).hexdigest() != company_meta["snapshot_sha256"]:
            raise LegacyTransitionError(
                f"company meta changed before adoption materialization: {member['symbol']}"
            )
        updated = dict(current)
        research = dict(updated["research"])
        research.update(
            {
                "coverage_status": "covered",
                "rebaseline_required": False,
                "information_cutoff": _latest_datetime_text(
                    research.get("information_cutoff"),
                    member["formal_source"]["information_cutoff"],
                ),
            }
        )
        updated["research"] = research
        updated["updated_at"] = result["recorded_at"]
        atomic_write_bytes(meta_path, _pretty_json_bytes(updated))
        try:
            validate_company_dir(company_dir)
        except AssetValidationError as exc:
            atomic_write_bytes(meta_path, current_bytes)
            raise LegacyTransitionError(
                f"adoption would violate company meta v2: {member['symbol']}"
            ) from exc


def _meta_already_transitioned(meta: Mapping[str, Any]) -> bool:
    research = meta.get("research")
    return (
        isinstance(research, Mapping)
        and research.get("coverage_status") == "covered"
        and research.get("rebaseline_required") is False
        and isinstance(research.get("information_cutoff"), str)
    )


def _latest_datetime_text(first: Any, second: Any) -> str:
    values = [
        _parse_datetime(value, "information_cutoff")
        for value in (first, second)
        if value is not None
    ]
    if not values:
        raise LegacyTransitionError("adoption information_cutoff is missing")
    return max(values).isoformat()


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _can_materialize_screen(
    existing: Mapping[str, Any] | None,
    result_relative: str,
) -> bool:
    return existing is None or existing.get("manager_screen_result_path") in {
        None,
        result_relative,
    }


def _verify_transition_dir(
    transition_dir: Path,
    *,
    repository_root: Path,
    require_packet: bool,
    require_result: bool,
) -> dict[str, Any]:
    if transition_dir.name != TRANSITION_ID:
        raise LegacyTransitionError("legacy transition directory name is invalid")
    plan_path = transition_dir / "plan.json"
    packet_path = transition_dir / "packet.json"
    result_path = transition_dir / "result.json"
    try:
        plan_seal = verify_sealed(plan_path)
    except (OSError, SealingError) as exc:
        raise LegacyTransitionError("legacy transition plan is not sealed") from exc
    if plan_seal.artifact_type != "manager_screen_legacy_transition_plan":
        raise LegacyTransitionError("legacy transition plan artifact type is invalid")
    plan = _read_object(plan_path)
    _validate_plan(plan)
    _verify_plan_sources(plan=plan, repository_root=repository_root)
    if transition_dir.parent.name != plan["run_id"] or plan["transition_id"] != TRANSITION_ID:
        raise LegacyTransitionError("legacy transition directory identity mismatch")
    result: dict[str, Any] = {
        "plan_path": plan_path,
        "plan": plan,
        "plan_seal": plan_seal,
        "packet_path": packet_path,
        "result_path": result_path,
    }
    if packet_path.exists():
        try:
            packet_seal = verify_sealed(packet_path)
        except (OSError, SealingError) as exc:
            raise LegacyTransitionError("legacy transition packet is not sealed") from exc
        if packet_seal.artifact_type != "manager_screen_legacy_transition_packet":
            raise LegacyTransitionError("legacy transition packet artifact type is invalid")
        packet = _read_object(packet_path)
        _validate_packet(packet, plan=plan, plan_sha256=plan_seal.sha256)
        if packet["plan_path"] != _relative(plan_path, repository_root):
            raise LegacyTransitionError("transition packet path does not bind plan")
        result.update({"packet": packet, "packet_seal": packet_seal})
    elif require_packet:
        raise LegacyTransitionError("legacy transition packet is missing")
    if result_path.exists():
        if "packet" not in result:
            raise LegacyTransitionError("transition result exists without packet")
        try:
            result_seal = verify_sealed(result_path)
        except (OSError, SealingError) as exc:
            raise LegacyTransitionError("legacy transition result is not sealed") from exc
        if result_seal.artifact_type != "manager_screen_legacy_transition_result":
            raise LegacyTransitionError("legacy transition result artifact type is invalid")
        payload = _read_object(result_path)
        _validate_result(
            payload,
            plan=plan,
            packet=result["packet"],
            plan_sha256=plan_seal.sha256,
            packet_sha256=result["packet_seal"].sha256,
        )
        if payload["plan_path"] != _relative(plan_path, repository_root):
            raise LegacyTransitionError("transition result path does not bind plan")
        if payload["packet_path"] != _relative(packet_path, repository_root):
            raise LegacyTransitionError("transition result path does not bind packet")
        result.update({"result": payload, "result_seal": result_seal})
    elif require_result:
        raise LegacyTransitionError("legacy transition result is missing")
    return result


def _validate_plan(plan: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "run_id",
        "transition_id",
        "frozen_at",
        "scope",
        "classification",
        "members",
        "portfolio_action",
    }
    if not isinstance(plan, Mapping) or set(plan) != required:
        raise LegacyTransitionError("legacy transition plan fields do not match v1")
    if plan.get("schema_version") != 1 or plan.get("portfolio_action") is not None:
        raise LegacyTransitionError("legacy transition plan contract is invalid")
    _identifier(plan.get("run_id"), "plan.run_id")
    if plan.get("transition_id") != TRANSITION_ID:
        raise LegacyTransitionError("legacy transition id is invalid")
    _parse_datetime(plan.get("frozen_at"), "plan.frozen_at")
    scope = plan.get("scope")
    if not isinstance(scope, Mapping) or set(scope) != {
        "manifest_path",
        "manifest_sha256",
        "baseline_intake_path",
        "baseline_intake_sha256",
    }:
        raise LegacyTransitionError("plan scope fields do not match v1")
    _sha256(scope.get("manifest_sha256"), "plan.scope.manifest_sha256")
    _sha256(
        scope.get("baseline_intake_sha256"),
        "plan.scope.baseline_intake_sha256",
    )
    members = plan.get("members")
    if not isinstance(members, list):
        raise LegacyTransitionError("plan.members must be an array")
    member_keys = {
        "ordinal",
        "symbol",
        "name",
        "action",
        "source_population",
        "queue_record_sha256",
        "queue_state",
        "research_stage_high_watermark",
        "legacy_terminal",
        "formal_source",
        "company_meta",
    }
    symbols = []
    for ordinal, item in enumerate(members, 1):
        if not isinstance(item, Mapping) or set(item) != member_keys:
            raise LegacyTransitionError("plan member fields do not match v1")
        if item.get("ordinal") != ordinal:
            raise LegacyTransitionError("plan member ordinals are invalid")
        symbols.append(_symbol(item.get("symbol")))
        _text(item.get("name"), f"plan member {ordinal}.name")
        if item.get("action") not in {"adoption", "rescreen", "defer_active"}:
            raise LegacyTransitionError("plan member action is invalid")
        if item.get("source_population") not in {
            "legacy_terminal",
            "frozen_deferred",
        }:
            raise LegacyTransitionError("plan member source population is invalid")
        _sha256(
            item.get("queue_record_sha256"),
            f"{item['symbol']}.queue_record_sha256",
        )
        if not isinstance(item.get("queue_state"), Mapping) or set(item["queue_state"]) != {
            "task_type",
            "status",
            "result_path",
        }:
            raise LegacyTransitionError("plan member queue state is invalid")
        high_watermark = item.get("research_stage_high_watermark")
        if high_watermark is not None and high_watermark not in FORMAL_STAGES:
            raise LegacyTransitionError("plan member high-watermark is invalid")
        if item["source_population"] == "legacy_terminal":
            if not isinstance(item.get("legacy_terminal"), Mapping):
                raise LegacyTransitionError("legacy terminal binding is missing")
        elif item.get("legacy_terminal") is not None:
            raise LegacyTransitionError("deferred member cannot bind a legacy terminal")
        if item["action"] == "adoption":
            if not isinstance(item.get("formal_source"), Mapping):
                raise LegacyTransitionError("adoption formal source is missing")
        else:
            if item.get("formal_source") is not None:
                raise LegacyTransitionError("non-adoption member cannot bind formal source")
            if item.get("company_meta") is not None:
                raise LegacyTransitionError("non-adoption member cannot bind company meta")
    if len(symbols) != len(members) or len(symbols) != len(set(symbols)):
        raise LegacyTransitionError("plan members are invalid or duplicated")
    actions = Counter(item.get("action") for item in members)
    classification = plan.get("classification")
    if not isinstance(classification, Mapping) or classification != {
        "adoption": actions["adoption"],
        "rescreen": actions["rescreen"],
        "defer_active": actions["defer_active"],
        "total": len(members),
    }:
        raise LegacyTransitionError("plan classification counts are invalid")


def _verify_plan_sources(
    *,
    plan: Mapping[str, Any],
    repository_root: Path,
) -> None:
    scope = plan["scope"]
    manifest_path = _safe_repository_file(scope["manifest_path"], repository_root)
    intake_path = _safe_repository_file(
        scope["baseline_intake_path"],
        repository_root,
    )
    try:
        manifest_seal = verify_sealed(manifest_path)
        intake_seal = verify_sealed(intake_path)
    except (OSError, SealingError) as exc:
        raise LegacyTransitionError("transition scope binding is not sealed") from exc
    if (
        manifest_seal.sha256 != scope["manifest_sha256"]
        or manifest_seal.artifact_type != "all_a_scope_manifest"
        or intake_seal.sha256 != scope["baseline_intake_sha256"]
        or intake_seal.artifact_type != "all_a_baseline_intake"
    ):
        raise LegacyTransitionError("transition scope binding is invalid")
    intake = _read_object(intake_path)
    if (
        intake.get("scope_manifest_path") != scope["manifest_path"]
        or intake.get("scope_manifest_sha256") != manifest_seal.sha256
    ):
        raise LegacyTransitionError("transition intake no longer binds the manifest")

    for member in plan["members"]:
        terminal = member.get("legacy_terminal")
        if terminal is not None:
            if not isinstance(terminal, Mapping) or set(terminal) != {
                "path",
                "sha256",
                "artifact_type",
            }:
                raise LegacyTransitionError("plan legacy terminal fields are invalid")
            sealed = _verify_reference(
                terminal["path"],
                repository_root=repository_root,
                label=f"{member['symbol']}.legacy_terminal",
            )
            if (
                sealed.sha256 != terminal["sha256"]
                or sealed.artifact_type != terminal["artifact_type"]
                or sealed.artifact_type != "rapid_triage_package"
            ):
                raise LegacyTransitionError("plan legacy terminal binding is invalid")
        source = member.get("formal_source")
        company_meta = member.get("company_meta")
        if company_meta is not None:
            if not isinstance(company_meta, Mapping) or set(company_meta) != {
                "path",
                "snapshot_sha256",
                "research_state",
            }:
                raise LegacyTransitionError("plan company meta binding is invalid")
            meta_path = _safe_repository_file(
                company_meta["path"],
                repository_root,
            )
            snapshot_sha256 = _sha256(
                company_meta.get("snapshot_sha256"),
                "company_meta.snapshot_sha256",
            )
            meta = _read_object(meta_path)
            if meta.get("identity", {}).get("symbol") != member["symbol"]:
                raise LegacyTransitionError("plan company meta symbol is invalid")
            research_state = company_meta["research_state"]
            if not isinstance(research_state, Mapping):
                raise LegacyTransitionError("plan company meta research state is invalid")
            if dict(meta.get("research") or {}) == dict(research_state):
                if hashlib.sha256(meta_path.read_bytes()).hexdigest() != snapshot_sha256:
                    raise LegacyTransitionError(
                        "company meta bytes changed after transition freeze"
                    )
            else:
                if not _meta_already_transitioned(meta):
                    raise LegacyTransitionError(
                        "company meta changed incompatibly after transition freeze"
                    )
                try:
                    validate_company_dir(meta_path.parent)
                except AssetValidationError as exc:
                    raise LegacyTransitionError("transitioned company meta violates v2") from exc
        if source is None:
            continue
        kind = source.get("kind")
        if kind == "sealed_formal":
            required = {
                "kind",
                "stage",
                "information_cutoff",
                "profile_path",
                "profile_sha256",
                "profile_artifact_type",
                "evaluation_path",
                "evaluation_sha256",
                "evaluation_artifact_type",
            }
            if set(source) != required or source.get("stage") not in FORMAL_STAGES:
                raise LegacyTransitionError("sealed formal source fields are invalid")
            _parse_datetime(
                source.get("information_cutoff"),
                "sealed formal source information_cutoff",
            )
            profile = _verify_reference(
                source["profile_path"],
                repository_root=repository_root,
                label=f"{member['symbol']}.profile",
            )
            evaluation = _verify_reference(
                source["evaluation_path"],
                repository_root=repository_root,
                label=f"{member['symbol']}.evaluation",
            )
            if (
                profile.sha256 != source["profile_sha256"]
                or profile.artifact_type != source["profile_artifact_type"]
                or profile.artifact_type != "quick_profile_package"
                or evaluation.sha256 != source["evaluation_sha256"]
                or evaluation.artifact_type != source["evaluation_artifact_type"]
                or evaluation.artifact_type != "quick_profile_evaluation"
            ):
                raise LegacyTransitionError("sealed formal source binding is invalid")
        elif kind == "legacy_report_bridge":
            required = {
                "kind",
                "stage",
                "information_cutoff",
                "report_path",
                "report_sha256",
                "meta_path",
                "meta_snapshot_sha256",
                "meta_report_id",
                "scoped_profile_path",
                "scoped_profile_sha256",
                "scoped_profile_artifact_type",
                "scoped_evaluation_path",
                "scoped_evaluation_sha256",
                "scoped_evaluation_artifact_type",
            }
            if set(source) != required or source.get("stage") != "deep_research":
                raise LegacyTransitionError("legacy report bridge fields are invalid")
            _parse_datetime(
                source.get("information_cutoff"),
                "legacy report bridge information_cutoff",
            )
            report_path = _safe_repository_file(
                source["report_path"],
                repository_root,
            )
            if hashlib.sha256(report_path.read_bytes()).hexdigest() != source["report_sha256"]:
                raise LegacyTransitionError("legacy bridge report binding is invalid")
            profile = _verify_reference(
                source["scoped_profile_path"],
                repository_root=repository_root,
                label=f"{member['symbol']}.bridge_profile",
            )
            evaluation = _verify_reference(
                source["scoped_evaluation_path"],
                repository_root=repository_root,
                label=f"{member['symbol']}.bridge_evaluation",
            )
            if (
                profile.sha256 != source["scoped_profile_sha256"]
                or profile.artifact_type != source["scoped_profile_artifact_type"]
                or profile.artifact_type != "quick_profile_package"
                or evaluation.sha256 != source["scoped_evaluation_sha256"]
                or evaluation.artifact_type != source["scoped_evaluation_artifact_type"]
                or evaluation.artifact_type != "quick_profile_evaluation"
            ):
                raise LegacyTransitionError("legacy bridge scoped binding is invalid")
            meta_path = _safe_repository_file(source["meta_path"], repository_root)
            meta = _read_object(meta_path)
            report_relative = _relative(report_path, meta_path.parent)
            if not any(
                isinstance(item, Mapping)
                and item.get("report_id") == source["meta_report_id"]
                and item.get("path") == report_relative
                and item.get("sha256") == source["report_sha256"]
                for item in meta.get("reports", {}).get("history") or []
            ):
                raise LegacyTransitionError("legacy bridge meta binding is invalid")
        else:
            raise LegacyTransitionError("plan formal source kind is invalid")


def _validate_packet(
    packet: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    plan_sha256: str,
) -> None:
    required = {
        "schema_version",
        "run_id",
        "transition_id",
        "created_at",
        "plan_path",
        "plan_sha256",
        "instructions",
        "adoption_dossiers",
        "rescreen_symbols",
        "defer_active_symbols",
        "portfolio_action",
    }
    if not isinstance(packet, Mapping) or set(packet) != required:
        raise LegacyTransitionError("legacy transition packet fields do not match v1")
    if (
        packet.get("schema_version") != 1
        or packet.get("run_id") != plan["run_id"]
        or packet.get("transition_id") != TRANSITION_ID
        or packet.get("plan_sha256") != plan_sha256
        or packet.get("portfolio_action") is not None
    ):
        raise LegacyTransitionError("legacy transition packet binding is invalid")
    expected_adoption = [item["symbol"] for item in plan["members"] if item["action"] == "adoption"]
    if [item.get("symbol") for item in packet.get("adoption_dossiers") or []] != expected_adoption:
        raise LegacyTransitionError("transition packet adoption population is invalid")


def _validate_result(
    result: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    packet: Mapping[str, Any],
    plan_sha256: str,
    packet_sha256: str,
) -> None:
    required = {
        "schema_version",
        "run_id",
        "transition_id",
        "recorded_at",
        "plan_path",
        "plan_sha256",
        "packet_path",
        "packet_sha256",
        "manager",
        "decisions",
        "releases",
        "deferred_unchanged",
        "portfolio_action",
    }
    if not isinstance(result, Mapping) or set(result) != required:
        raise LegacyTransitionError("legacy transition result fields do not match v1")
    if (
        result.get("schema_version") != 1
        or result.get("run_id") != plan["run_id"]
        or result.get("transition_id") != TRANSITION_ID
        or result.get("plan_sha256") != plan_sha256
        or result.get("packet_sha256") != packet_sha256
        or result.get("portfolio_action") is not None
    ):
        raise LegacyTransitionError("legacy transition result binding is invalid")
    normalized = _normalize_submission(
        {
            "schema_version": 1,
            "manager": result.get("manager"),
            "decisions": result.get("decisions"),
        },
        plan=plan,
    )
    if normalized["manager"] != result["manager"] or normalized["decisions"] != result["decisions"]:
        raise LegacyTransitionError("legacy transition result is not normalized")
    if result.get("releases") != packet.get("rescreen_symbols"):
        raise LegacyTransitionError("legacy transition releases are invalid")
    if result.get("deferred_unchanged") != packet.get("defer_active_symbols"):
        raise LegacyTransitionError("legacy transition deferred population is invalid")


def _stage_high_watermark(queue_record: Mapping[str, Any]) -> str | None:
    seen = [
        str(item.get("stage"))
        for item in queue_record.get("stage_history") or []
        if isinstance(item, Mapping)
        and item.get("stage") in FORMAL_STAGES
        and item.get("status") == "completed"
    ]
    if queue_record.get("task_type") in FORMAL_STAGES and queue_record.get("status") == "completed":
        seen.append(str(queue_record["task_type"]))
    if not seen:
        return None
    return max(seen, key=lambda item: FORMAL_STAGES[item])


def _verify_reference(
    value: Any,
    *,
    repository_root: Path,
    label: str,
) -> SealedArtifact:
    path = _safe_repository_file(value, repository_root)
    try:
        return verify_sealed(path)
    except (OSError, SealingError) as exc:
        raise LegacyTransitionError(f"{label} is not validly sealed") from exc


def _safe_repository_file(value: Any, repository_root: Path) -> Path:
    text = _text(value, "repository path")
    candidate = (repository_root / text).resolve()
    root = repository_root.resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise LegacyTransitionError(f"repository file is missing or unsafe: {text}")
    return candidate


def _safe_repository_dir(value: Any, repository_root: Path) -> Path:
    text = _text(value, "repository directory")
    candidate = (repository_root / text).resolve()
    root = repository_root.resolve()
    if not candidate.is_relative_to(root) or not candidate.is_dir():
        raise LegacyTransitionError(f"repository directory is missing or unsafe: {text}")
    return candidate


def _safe_child_file(
    parent: Path,
    value: Any,
    *,
    repository_root: Path,
) -> Path:
    text = _text(value, "child path")
    candidate = (parent / text).resolve()
    if (
        not candidate.is_relative_to(parent.resolve())
        or not candidate.is_relative_to(repository_root.resolve())
        or not candidate.is_file()
    ):
        raise LegacyTransitionError(f"child file is missing or unsafe: {text}")
    return candidate


def _formal_evidence_token(source: Mapping[str, Any]) -> str:
    if source["kind"] == "sealed_formal":
        return f"formal_evaluation_sha256:{source['evaluation_sha256']}"
    return f"legacy_report_sha256:{source['report_sha256']}"


def _transition_evidence_ids(member: Mapping[str, Any]) -> list[str]:
    symbol = str(member["symbol"])
    source = member["formal_source"]
    evidence = [f"transition:formal:{symbol}"]
    if source["kind"] == "legacy_report_bridge":
        evidence.append(f"transition:legacy-report:{symbol}")
    if member.get("legacy_terminal") is not None:
        evidence.append(f"transition:legacy-terminal:{symbol}")
    return evidence


def _freeze_summary(
    *,
    plan: Mapping[str, Any],
    plan_path: Path,
    plan_seal: SealedArtifact,
    packet_path: Path,
    packet_seal: SealedArtifact,
    repository_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": plan["run_id"],
        "transition_id": TRANSITION_ID,
        "classification": dict(plan["classification"]),
        "plan_path": _relative(plan_path, repository_root),
        "plan_sha256": plan_seal.sha256,
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_seal.sha256,
        "portfolio_action": None,
    }


def _record_summary(
    *,
    result: Mapping[str, Any],
    result_path: Path,
    result_seal: SealedArtifact,
    repository_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": result["run_id"],
        "transition_id": TRANSITION_ID,
        "adoption_count": len(result["decisions"]),
        "rescreen_count": len(result["releases"]),
        "defer_active_count": len(result["deferred_unchanged"]),
        "result_path": _relative(result_path, repository_root),
        "result_sha256": result_seal.sha256,
        "portfolio_action": None,
    }


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LegacyTransitionError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise LegacyTransitionError(f"JSON artifact must be an object: {path}")
    return value


def _unique_by_symbol(
    records: Sequence[Mapping[str, Any]],
    label: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in records:
        symbol = _symbol(item.get("symbol"))
        if symbol in result:
            raise LegacyTransitionError(f"duplicate {label} symbol: {symbol}")
        result[symbol] = item
    return result


def _payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise LegacyTransitionError(f"path escapes repository root: {path}") from exc


def _identifier(value: Any, label: str) -> str:
    text = _text(value, label)
    if not ID_RE.fullmatch(text):
        raise LegacyTransitionError(f"{label} is invalid")
    return text


def _symbol(value: Any) -> str:
    text = _text(value, "symbol")
    if not SYMBOL_RE.fullmatch(text):
        raise LegacyTransitionError(f"symbol is invalid: {text}")
    return text


def _sha256(value: Any, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise LegacyTransitionError(f"{label} must be a lowercase SHA-256")
    return text


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LegacyTransitionError(f"{label} must be a non-empty string")
    return value.strip()


def _aware(value: dt.datetime, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LegacyTransitionError(f"{label} must include timezone information")
    return value


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    text = _text(value, label)
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise LegacyTransitionError(f"{label} is invalid") from exc
    return _aware(parsed, label)
