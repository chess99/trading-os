from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .quality_audit import (
    QualityAuditError,
    load_quality_audit_policy,
    quality_audit_status,
    quality_policy_sha256,
    seal_cycle_quality_audit_plan,
    seal_scope_identity_audit_plan,
    validate_quality_audit_policy,
)
from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed
from .triage_cohort import ResearchAllocationError, load_rapid_triage_cohort
from .triage_workflow import (
    evaluate_rapid_triage,
    validate_rapid_triage_package,
)


class QualityWorkflowError(ValueError):
    """Raised when production quality-audit inputs or bindings are invalid."""


POLICY_SNAPSHOT_ARTIFACT_TYPE = "triage_quality_audit_policy_snapshot"
WORKFLOW_BINDING_ARTIFACT_TYPE = "quality_audit_workflow_binding"
SUBJECT_KINDS = {"scope_identity", "triage_false_negative"}
STOP_DISPOSITIONS = {
    "catalog",
    "price_watch",
    "conditional_stop",
    "reassign_or_stop",
}
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def scope_quality_root(root: str | Path, run_id: str) -> Path:
    return Path(root) / "scopes" / _identifier(run_id, "run_id") / "quality" / "identity"


def cycle_quality_root(root: str | Path, cycle_id: str) -> Path:
    return Path(root) / "triage" / _identifier(cycle_id, "cycle_id") / "quality"


def seal_quality_policy_snapshot(
    *,
    output_dir: str | Path,
    policy_path: str | Path,
    repository_root: str | Path,
    subject_kind: str,
    subject_id: str,
    sealed_at: dt.datetime,
) -> dict[str, Any]:
    """Seal the exact policy file and normalized policy used by one audit."""

    _aware(sealed_at, "sealed_at")
    kind = _subject_kind(subject_kind)
    subject = _identifier(subject_id, "subject_id")
    repository = Path(repository_root).resolve()
    source = _resolve_path(policy_path, repository)
    if not source.is_file():
        raise QualityWorkflowError(f"quality policy is missing: {source}")
    try:
        raw_bytes = source.read_bytes()
        policy = load_quality_audit_policy(source)
    except (OSError, QualityAuditError) as exc:
        raise QualityWorkflowError(f"quality policy is invalid: {source}: {exc}") from exc
    if policy.get("kind") != "triage_quality_audit":
        raise QualityWorkflowError("quality policy kind must be triage_quality_audit")
    payload = {
        "schema_version": 1,
        "subject_kind": kind,
        "subject_id": subject,
        "created_at": sealed_at.isoformat(),
        "policy_path": _repository_path(source, repository),
        "policy_file_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "policy_sha256": quality_policy_sha256(policy),
        "policy": policy,
        "portfolio_action": None,
    }
    target = Path(output_dir) / "policy-snapshot.json"
    sealed = _seal(target, payload, POLICY_SNAPSHOT_ARTIFACT_TYPE, sealed_at)
    return {
        "schema_version": 1,
        "subject_kind": kind,
        "subject_id": subject,
        "snapshot_path": str(target),
        "snapshot_sha256": sealed.sha256,
        "policy_path": payload["policy_path"],
        "policy_file_sha256": payload["policy_file_sha256"],
        "policy_sha256": payload["policy_sha256"],
    }


def load_quality_policy_snapshot(
    *,
    snapshot_path: str | Path,
    expected_subject_kind: str | None = None,
    expected_subject_id: str | None = None,
) -> dict[str, Any]:
    target = Path(snapshot_path)
    sealed, payload = _load_sealed_json(
        target,
        artifact_type=POLICY_SNAPSHOT_ARTIFACT_TYPE,
        label="quality policy snapshot",
    )
    expected_fields = {
        "schema_version",
        "subject_kind",
        "subject_id",
        "created_at",
        "policy_path",
        "policy_file_sha256",
        "policy_sha256",
        "policy",
        "portfolio_action",
    }
    if set(payload) != expected_fields or payload.get("schema_version") != 1:
        raise QualityWorkflowError("quality policy snapshot fields do not match contract")
    kind = _subject_kind(payload.get("subject_kind"))
    subject = _identifier(payload.get("subject_id"), "subject_id")
    _aware(_datetime(payload.get("created_at"), "created_at"), "created_at")
    _text(payload.get("policy_path"), "policy_path")
    _sha256(payload.get("policy_file_sha256"), "policy_file_sha256")
    policy_sha = _sha256(payload.get("policy_sha256"), "policy_sha256")
    if payload.get("portfolio_action") is not None:
        raise QualityWorkflowError("quality policy snapshot cannot contain portfolio action")
    try:
        normalized = validate_quality_audit_policy(payload.get("policy"))
    except QualityAuditError as exc:
        raise QualityWorkflowError(f"snapshot policy is invalid: {exc}") from exc
    if normalized.get("kind") != "triage_quality_audit":
        raise QualityWorkflowError("snapshot policy kind must be triage_quality_audit")
    if quality_policy_sha256(normalized) != policy_sha:
        raise QualityWorkflowError("snapshot normalized policy sha256 does not match")
    if expected_subject_kind is not None and kind != _subject_kind(expected_subject_kind):
        raise QualityWorkflowError("quality policy snapshot subject kind does not match")
    if expected_subject_id is not None and subject != _identifier(
        expected_subject_id, "expected_subject_id"
    ):
        raise QualityWorkflowError("quality policy snapshot subject id does not match")
    result = copy.deepcopy(payload)
    result["policy"] = normalized
    result["snapshot_sha256"] = sealed.sha256
    result["snapshot_path"] = str(target)
    return result


def prepare_scope_identity_quality_audit(
    *,
    root: str | Path,
    run_id: str,
    policy_path: str | Path,
    created_at: dt.datetime,
) -> dict[str, Any]:
    """Build a sealed 100% hard-exclusion identity-audit production plan."""

    _aware(created_at, "created_at")
    base = Path(root)
    repository = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    output = scope_quality_root(base, run)
    if (output / "binding.json").exists():
        return scope_quality_status(root=base, run_id=run)

    manifest_path = base / "scopes" / run / "manifest.json"
    manifest_seal, manifest = _load_sealed_json(
        manifest_path,
        artifact_type="all_a_scope_manifest",
        label="scope manifest",
    )
    _validate_scope_manifest(manifest, run_id=run)
    universe = _mapping(manifest.get("universe_source"), "universe_source")
    universe_path = _resolve_path(_text(universe.get("path"), "universe_source.path"), repository)
    universe_bytes = _read_bytes(universe_path, "universe source")
    if hashlib.sha256(universe_bytes).hexdigest() != _sha256(
        universe.get("sha256"), "universe_source.sha256"
    ):
        raise QualityWorkflowError("universe source sha256 does not match scope manifest")
    companies = read_jsonl(universe_path)
    if universe.get("record_count") != len(companies):
        raise QualityWorkflowError("universe source record count does not match scope manifest")
    screening_path = base / SCREENING_FILE
    screening = read_jsonl(screening_path)
    company_by_symbol = _unique_rows(companies, "universe source")
    screening_by_symbol = _unique_rows(screening, "screening")
    hard_exclusions = []
    for member in manifest["members"]:
        if member.get("partition") != "hard_excluded":
            continue
        symbol = _symbol(member.get("symbol"))
        company = company_by_symbol.get(symbol)
        if company is None:
            raise QualityWorkflowError(f"scope member is missing from universe source: {symbol}")
        screen = screening_by_symbol.get(symbol)
        identity_facts = {
            "scope_member": _identity_scope_projection(member),
            "company_identity": _company_identity_projection(company),
            "screening_identity": _screening_identity_projection(screen),
        }
        commitment = {
            "scope_manifest_sha256": manifest_seal.sha256,
            "identity_facts": identity_facts,
        }
        hard_exclusions.append(
            {
                "symbol": symbol,
                "name": _text(member.get("name"), f"{symbol}.name"),
                "source_subject_sha256": _canonical_sha256(commitment),
                "identity_facts": identity_facts,
                "sources": _identity_sources(
                    symbol=symbol,
                    company=company,
                    screen=screen,
                    universe_path=universe_path,
                    screening_path=screening_path,
                    repository=repository,
                    accessed_at=created_at,
                ),
                "original_agent": None,
            }
        )

    snapshot = seal_quality_policy_snapshot(
        output_dir=output,
        policy_path=policy_path,
        repository_root=repository,
        subject_kind="scope_identity",
        subject_id=run,
        sealed_at=created_at,
    )
    snapshot_payload = load_quality_policy_snapshot(
        snapshot_path=snapshot["snapshot_path"],
        expected_subject_kind="scope_identity",
        expected_subject_id=run,
    )
    try:
        plan = seal_scope_identity_audit_plan(
            output_dir=output,
            audit_id=f"{run}:identity",
            scope_id=run,
            scope_path=_repository_path(manifest_path, repository),
            scope_sha256=manifest_seal.sha256,
            hard_exclusions=hard_exclusions,
            policy=snapshot_payload["policy"],
            created_at=created_at,
        )
    except QualityAuditError as exc:
        raise QualityWorkflowError(f"cannot prepare scope quality plan: {exc}") from exc
    _seal_workflow_binding(
        output=output,
        repository=repository,
        subject_kind="scope_identity",
        subject_id=run,
        source_path=manifest_path,
        source_sha256=manifest_seal.sha256,
        source_artifact_type="all_a_scope_manifest",
        snapshot=snapshot,
        plan_path=Path(plan["plan_path"]),
        plan_sha256=plan["plan_sha256"],
        plan_artifact_type="scope_identity_audit_plan",
        created_at=created_at,
    )
    return scope_quality_status(root=base, run_id=run)


def prepare_cycle_quality_audit(
    *,
    root: str | Path,
    cycle_id: str,
    policy_path: str | Path,
    created_at: dt.datetime,
) -> dict[str, Any]:
    """Build a sealed stop-strata plan from a production cohort and packages."""

    _aware(created_at, "created_at")
    base = Path(root)
    repository = base.parent.parent.resolve()
    cycle = _identifier(cycle_id, "cycle_id")
    output = cycle_quality_root(base, cycle)
    if (output / "binding.json").exists():
        return cycle_quality_status(root=base, cycle_id=cycle)
    try:
        cohort, cohort_sha, cohort_relative = load_rapid_triage_cohort(
            root=base, cycle_id=cycle
        )
    except (OSError, ValueError, ResearchAllocationError, SealingError) as exc:
        raise QualityWorkflowError(f"rapid-triage cohort is invalid: {exc}") from exc
    if cohort.get("schema_version") not in {2, 3}:
        raise QualityWorkflowError(
            "legacy rapid-triage cohort is not valid production proof for a new Goal"
        )
    cohort_path = base / "triage" / cycle / "cohort.json"
    _validate_parent_scope_binding(
        base=base,
        repository=repository,
        cohort=cohort,
    )
    records = []
    for member in cohort["members"]:
        symbol = _symbol(member.get("symbol"))
        package, package_seal = _load_cycle_package(
            base=base,
            cycle_id=cycle,
            symbol=symbol,
        )
        disposition = evaluate_rapid_triage(package)["disposition"]
        if disposition not in STOP_DISPOSITIONS:
            continue
        records.append(
            {
                "symbol": symbol,
                "name": package["company_name"],
                "disposition": disposition,
                "source_subject_sha256": package_seal.sha256,
                "original_agent": package["provenance"]["agent"],
                "information_cutoff": package["information_cutoff"],
                "price_snapshot": {
                    "price": package["current_price"],
                    "price_as_of": package["price_as_of"],
                    "source_id": package["price_source_id"],
                },
                "sources": package["sources"],
            }
        )

    snapshot = seal_quality_policy_snapshot(
        output_dir=output,
        policy_path=policy_path,
        repository_root=repository,
        subject_kind="triage_false_negative",
        subject_id=cycle,
        sealed_at=created_at,
    )
    snapshot_payload = load_quality_policy_snapshot(
        snapshot_path=snapshot["snapshot_path"],
        expected_subject_kind="triage_false_negative",
        expected_subject_id=cycle,
    )
    try:
        plan = seal_cycle_quality_audit_plan(
            output_dir=output,
            audit_id=f"{cycle}:false-negative",
            cycle_id=cycle,
            cohort_path=cohort_relative,
            cohort_sha256=cohort_sha,
            records=records,
            policy=snapshot_payload["policy"],
            created_at=created_at,
        )
    except QualityAuditError as exc:
        raise QualityWorkflowError(f"cannot prepare cycle quality plan: {exc}") from exc
    _seal_workflow_binding(
        output=output,
        repository=repository,
        subject_kind="triage_false_negative",
        subject_id=cycle,
        source_path=cohort_path,
        source_sha256=cohort_sha,
        source_artifact_type="rapid_triage_cohort",
        snapshot=snapshot,
        plan_path=Path(plan["plan_path"]),
        plan_sha256=plan["plan_sha256"],
        plan_artifact_type="triage_quality_audit_plan",
        created_at=created_at,
    )
    return cycle_quality_status(root=base, cycle_id=cycle)


def scope_quality_status(*, root: str | Path, run_id: str) -> dict[str, Any]:
    return _workflow_status(
        root=Path(root),
        output=scope_quality_root(root, run_id),
        subject_kind="scope_identity",
        subject_id=_identifier(run_id, "run_id"),
        source_artifact_type="all_a_scope_manifest",
        plan_artifact_type="scope_identity_audit_plan",
        result_artifact_type="scope_identity_audit_result",
    )


def cycle_quality_status(*, root: str | Path, cycle_id: str) -> dict[str, Any]:
    return _workflow_status(
        root=Path(root),
        output=cycle_quality_root(root, cycle_id),
        subject_kind="triage_false_negative",
        subject_id=_identifier(cycle_id, "cycle_id"),
        source_artifact_type="rapid_triage_cohort",
        plan_artifact_type="triage_quality_audit_plan",
        result_artifact_type="triage_quality_audit_result",
    )


@serialized_coverage_write
def materialize_cycle_quality_reopens(
    *, root: str | Path, cycle_id: str
) -> dict[str, Any]:
    """Mark major-disagreement companies for a new independent correction cycle."""

    base = Path(root)
    cycle = _identifier(cycle_id, "cycle_id")
    status = cycle_quality_status(root=base, cycle_id=cycle)
    result_path = Path(status["canonical_paths"]["result"])
    result_seal, result = _load_sealed_json(
        result_path,
        artifact_type="triage_quality_audit_result",
        label="quality audit result",
    )
    reopen_symbols = {
        _symbol(value) for value in _sequence(result.get("reopen_symbols"), "reopen_symbols")
    }
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    changed: set[str] = set()
    updated_queue = []
    for row in queue:
        if row.get("symbol") not in reopen_symbols:
            updated_queue.append(row)
            continue
        item = dict(row)
        item["quality_reopen_required"] = True
        item["quality_audit_result_path"] = _repository_path(
            result_path, base.parent.parent.resolve()
        )
        item["quality_audit_result_sha256"] = result_seal.sha256
        if item.get("triage_cycle_id") == cycle and item.get("task_type") == "rapid_triage":
            item["status"] = "needs_review"
            item["assigned_agent"] = None
            item["started_at"] = None
            item["failure_reason"] = "independent_quality_major_disagreement"
            history = list(item.get("stage_history") or [])
            event = {
                "stage": "quality_audit",
                "status": "reopen_required",
                "finished_at": result["completed_at"],
                "cycle_id": cycle,
                "result_path": item["quality_audit_result_path"],
                "result_sha256": result_seal.sha256,
            }
            if event not in history:
                history.append(event)
            item["stage_history"] = history
        updated_queue.append(item)
        changed.add(str(item["symbol"]))
    updated_screening = []
    for row in screening:
        if row.get("symbol") not in reopen_symbols:
            updated_screening.append(row)
            continue
        item = dict(row)
        item.update(
            {
                "decision": "needs_manual_review",
                "priority": None,
                "reason": "独立质量抽查发现重大分歧，必须由新的单公司 Agent 重开。",
                "next_action": "冻结新的 correction cohort 并由独立 Agent 重新快速甄别。",
                "quality_audit_result_path": _repository_path(
                    result_path, base.parent.parent.resolve()
                ),
                "quality_audit_result_sha256": result_seal.sha256,
            }
        )
        updated_screening.append(item)
    if changed:
        write_jsonl(queue_path, updated_queue)
        write_jsonl(screening_path, updated_screening)
    return {
        "schema_version": 1,
        "cycle_id": cycle,
        "reopen_count": len(reopen_symbols),
        "materialized_count": len(changed),
        "symbols": sorted(reopen_symbols),
        "result_sha256": result_seal.sha256,
        "portfolio_action": None,
    }


def _workflow_status(
    *,
    root: Path,
    output: Path,
    subject_kind: str,
    subject_id: str,
    source_artifact_type: str,
    plan_artifact_type: str,
    result_artifact_type: str,
) -> dict[str, Any]:
    repository = root.parent.parent.resolve()
    binding_path = output / "binding.json"
    _, binding = _load_sealed_json(
        binding_path,
        artifact_type=WORKFLOW_BINDING_ARTIFACT_TYPE,
        label="quality workflow binding",
    )
    _validate_binding(binding, subject_kind=subject_kind, subject_id=subject_id)
    source_ref = binding["source"]
    source_path = _resolve_path(source_ref["path"], repository)
    source_seal, _ = _load_sealed_json(
        source_path,
        artifact_type=source_artifact_type,
        label="quality workflow subject source",
    )
    if source_seal.sha256 != source_ref["sha256"]:
        raise QualityWorkflowError("quality workflow source sha256 does not match binding")
    snapshot_ref = binding["policy_snapshot"]
    snapshot_path = _resolve_path(snapshot_ref["path"], repository)
    snapshot = load_quality_policy_snapshot(
        snapshot_path=snapshot_path,
        expected_subject_kind=subject_kind,
        expected_subject_id=subject_id,
    )
    if snapshot["snapshot_sha256"] != snapshot_ref["sha256"]:
        raise QualityWorkflowError("quality policy snapshot sha256 does not match binding")
    if snapshot["policy_file_sha256"] != snapshot_ref["policy_file_sha256"]:
        raise QualityWorkflowError("quality policy file sha256 does not match binding")
    plan_ref = binding["plan"]
    plan_path = _resolve_path(plan_ref["path"], repository)
    plan_seal, plan = _load_sealed_json(
        plan_path,
        artifact_type=plan_artifact_type,
        label="quality audit plan",
    )
    if plan_seal.sha256 != plan_ref["sha256"]:
        raise QualityWorkflowError("quality audit plan sha256 does not match binding")
    if plan.get("subject_kind") != subject_kind:
        raise QualityWorkflowError("quality audit plan subject kind does not match binding")
    source_sha_field = "scope_sha256" if subject_kind == "scope_identity" else "cohort_sha256"
    source_path_field = "scope_path" if subject_kind == "scope_identity" else "cohort_path"
    if (
        plan.get(source_sha_field) != source_seal.sha256
        or plan.get(source_path_field) != source_ref["path"]
    ):
        raise QualityWorkflowError("quality audit plan source binding is invalid")
    policy_ref = _mapping(plan.get("policy"), "plan.policy")
    if policy_ref.get("sha256") != snapshot["policy_sha256"]:
        raise QualityWorkflowError("quality audit plan policy binding is invalid")
    packet_type = (
        "scope_identity_audit_fact_packet"
        if subject_kind == "scope_identity"
        else "triage_quality_audit_fact_packet"
    )
    for item in _sequence(plan.get("items"), "plan.items"):
        row = _mapping(item, "plan item")
        packet_path = plan_path.parent / _text(row.get("facts_packet_path"), "facts_packet_path")
        packet_seal, _ = _load_sealed_json(
            packet_path,
            artifact_type=packet_type,
            label="quality audit fact packet",
        )
        if packet_seal.sha256 != row.get("facts_packet_sha256"):
            raise QualityWorkflowError("quality audit fact packet sha256 does not match plan")
    result_path = output / "result.json"
    status_target = plan_path
    if result_path.exists() or result_path.with_name(result_path.name + ".seal.json").exists():
        _, result = _load_sealed_json(
            result_path,
            artifact_type=result_artifact_type,
            label="quality audit result",
        )
        if result.get("plan_sha256") != plan_seal.sha256:
            raise QualityWorkflowError("quality audit result does not bind the plan")
        status_target = result_path
    try:
        status = quality_audit_status(status_target)
    except QualityAuditError as exc:
        raise QualityWorkflowError(f"quality audit status is invalid: {exc}") from exc
    live_policy_path = _resolve_path(snapshot["policy_path"], repository)
    live_policy_matches = False
    if live_policy_path.is_file():
        live_policy_matches = (
            hashlib.sha256(live_policy_path.read_bytes()).hexdigest()
            == snapshot["policy_file_sha256"]
        )
    return {
        "schema_version": 1,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "status": status["status"],
        "population_count": plan.get("population_count"),
        "sampled_count": plan.get("sampled_count"),
        "live_policy_matches_snapshot": live_policy_matches,
        "canonical_paths": {
            "root": str(output),
            "binding": str(binding_path),
            "policy_snapshot": str(snapshot_path),
            "plan": str(plan_path),
            "result": str(result_path),
            "packets": str(output / "packets"),
        },
        "source_sha256": source_seal.sha256,
        "policy_snapshot_sha256": snapshot["snapshot_sha256"],
        "plan_sha256": plan_seal.sha256,
        "portfolio_action": None,
    }


def _seal_workflow_binding(
    *,
    output: Path,
    repository: Path,
    subject_kind: str,
    subject_id: str,
    source_path: Path,
    source_sha256: str,
    source_artifact_type: str,
    snapshot: Mapping[str, Any],
    plan_path: Path,
    plan_sha256: str,
    plan_artifact_type: str,
    created_at: dt.datetime,
) -> None:
    snapshot_path = Path(snapshot["snapshot_path"])
    payload = {
        "schema_version": 1,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "created_at": created_at.isoformat(),
        "source": {
            "path": _repository_path(source_path, repository),
            "sha256": _sha256(source_sha256, "source_sha256"),
            "artifact_type": source_artifact_type,
        },
        "policy_snapshot": {
            "path": _repository_path(snapshot_path, repository),
            "sha256": _sha256(snapshot["snapshot_sha256"], "snapshot_sha256"),
            "artifact_type": POLICY_SNAPSHOT_ARTIFACT_TYPE,
            "policy_path": snapshot["policy_path"],
            "policy_file_sha256": snapshot["policy_file_sha256"],
        },
        "plan": {
            "path": _repository_path(plan_path, repository),
            "sha256": _sha256(plan_sha256, "plan_sha256"),
            "artifact_type": plan_artifact_type,
        },
        "portfolio_action": None,
    }
    _seal(output / "binding.json", payload, WORKFLOW_BINDING_ARTIFACT_TYPE, created_at)


def _validate_binding(
    payload: Mapping[str, Any], *, subject_kind: str, subject_id: str
) -> None:
    fields = {
        "schema_version",
        "subject_kind",
        "subject_id",
        "created_at",
        "source",
        "policy_snapshot",
        "plan",
        "portfolio_action",
    }
    if set(payload) != fields or payload.get("schema_version") != 1:
        raise QualityWorkflowError("quality workflow binding fields do not match contract")
    if payload.get("subject_kind") != subject_kind or payload.get("subject_id") != subject_id:
        raise QualityWorkflowError("quality workflow binding subject does not match")
    _datetime(payload.get("created_at"), "binding.created_at")
    if payload.get("portfolio_action") is not None:
        raise QualityWorkflowError("quality workflow binding cannot contain portfolio action")
    source = _mapping(payload.get("source"), "binding.source")
    snapshot = _mapping(payload.get("policy_snapshot"), "binding.policy_snapshot")
    plan = _mapping(payload.get("plan"), "binding.plan")
    if set(source) != {"path", "sha256", "artifact_type"}:
        raise QualityWorkflowError("quality workflow source reference is invalid")
    if set(snapshot) != {
        "path",
        "sha256",
        "artifact_type",
        "policy_path",
        "policy_file_sha256",
    }:
        raise QualityWorkflowError("quality workflow policy snapshot reference is invalid")
    if set(plan) != {"path", "sha256", "artifact_type"}:
        raise QualityWorkflowError("quality workflow plan reference is invalid")
    for value, label in (
        (source.get("sha256"), "source.sha256"),
        (snapshot.get("sha256"), "policy_snapshot.sha256"),
        (snapshot.get("policy_file_sha256"), "policy_snapshot.policy_file_sha256"),
        (plan.get("sha256"), "plan.sha256"),
    ):
        _sha256(value, label)
    for value, label in (
        (source.get("path"), "source.path"),
        (snapshot.get("path"), "policy_snapshot.path"),
        (snapshot.get("policy_path"), "policy_snapshot.policy_path"),
        (plan.get("path"), "plan.path"),
    ):
        _text(value, label)


def _validate_scope_manifest(payload: Mapping[str, Any], *, run_id: str) -> None:
    if payload.get("schema_version") != 1 or payload.get("run_id") != run_id:
        raise QualityWorkflowError("scope manifest schema or run binding is invalid")
    if payload.get("portfolio_action") is not None:
        raise QualityWorkflowError("scope manifest cannot contain portfolio action")
    members = payload.get("members")
    if not isinstance(members, list) or not members:
        raise QualityWorkflowError("scope manifest members are invalid")
    symbols = []
    for ordinal, item in enumerate(members, 1):
        if not isinstance(item, Mapping) or item.get("ordinal") != ordinal:
            raise QualityWorkflowError("scope manifest member ordinal is invalid")
        symbol = _symbol(item.get("symbol"))
        symbols.append(symbol)
        if item.get("partition") not in {"eligible", "hard_excluded", "exception"}:
            raise QualityWorkflowError(f"scope manifest partition is invalid: {symbol}")
    if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
        raise QualityWorkflowError("scope manifest members are not stable and unique")
    counts = _mapping(payload.get("counts"), "scope counts")
    actual = {
        "universe": len(members),
        "eligible": sum(item["partition"] == "eligible" for item in members),
        "hard_excluded": sum(item["partition"] == "hard_excluded" for item in members),
        "exception": sum(item["partition"] == "exception" for item in members),
    }
    if any(counts.get(key) != value for key, value in actual.items()):
        raise QualityWorkflowError("scope manifest counts do not conserve members")


def _validate_parent_scope_binding(
    *, base: Path, repository: Path, cohort: Mapping[str, Any]
) -> None:
    parent = _mapping(cohort.get("parent_scope"), "cohort.parent_scope")
    run = _identifier(parent.get("run_id"), "parent_scope.run_id")
    manifest_path = _resolve_path(_text(parent.get("manifest_path"), "manifest_path"), repository)
    intake_path = _resolve_path(
        _text(parent.get("baseline_intake_path"), "baseline_intake_path"), repository
    )
    canonical_manifest = (base / "scopes" / run / "manifest.json").resolve()
    canonical_intake = (base / "scopes" / run / "baseline-intake.json").resolve()
    if manifest_path != canonical_manifest or intake_path != canonical_intake:
        raise QualityWorkflowError("cohort parent scope paths are not canonical")
    manifest_seal, manifest = _load_sealed_json(
        manifest_path,
        artifact_type="all_a_scope_manifest",
        label="cohort parent scope manifest",
    )
    intake_seal, intake = _load_sealed_json(
        intake_path,
        artifact_type="all_a_baseline_intake",
        label="cohort parent baseline intake",
    )
    if (
        manifest_seal.sha256 != parent.get("manifest_sha256")
        or intake_seal.sha256 != parent.get("baseline_intake_sha256")
        or manifest.get("run_id") != run
        or intake.get("run_id") != run
        or intake.get("scope_manifest_sha256") != manifest_seal.sha256
        or parent.get("scope_cutoff") != manifest.get("scope_cutoff")
    ):
        raise QualityWorkflowError("cohort parent scope binding is invalid")


def _load_cycle_package(
    *, base: Path, cycle_id: str, symbol: str
) -> tuple[dict[str, Any], Any]:
    ticker = symbol.split(":", 1)[1]
    package_dir = base / "triage" / cycle_id / ticker
    paths = sorted(package_dir.glob("*.triage.json"))
    if not paths:
        raise QualityWorkflowError(f"cohort member has no rapid-triage package: {symbol}")
    valid = []
    for path in paths:
        seal, payload = _load_sealed_json(
            path,
            artifact_type="rapid_triage_package",
            label=f"rapid-triage package {symbol}",
        )
        try:
            normalized = validate_rapid_triage_package(payload, recorded_at=seal.sealed_at)
        except (ValueError, ResearchAllocationError) as exc:
            raise QualityWorkflowError(
                f"rapid-triage package is invalid for {symbol}: {exc}"
            ) from exc
        if normalized["cycle_id"] != cycle_id or normalized["symbol"] != symbol:
            raise QualityWorkflowError(f"rapid-triage package binding is invalid for {symbol}")
        valid.append((seal.sealed_at, seal.sha256, normalized, seal))
    valid.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if len(valid) > 1 and valid[0][0] == valid[1][0] and valid[0][1] != valid[1][1]:
        raise QualityWorkflowError(f"conflicting rapid-triage packages share sealed_at: {symbol}")
    return valid[0][2], valid[0][3]


def _identity_scope_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "symbol",
        "ticker",
        "name",
        "exchange",
        "security_type",
        "listing_status",
        "partition",
        "partition_reason_codes",
    )
    return {field: copy.deepcopy(value.get(field)) for field in fields}


def _company_identity_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "symbol",
        "ticker",
        "name",
        "exchange",
        "security_type",
        "listing_status",
        "as_of",
        "fetched_at",
        "source",
    )
    return {field: copy.deepcopy(value.get(field)) for field in fields}


def _screening_identity_projection(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    fields = (
        "symbol",
        "ticker",
        "name",
        "as_of",
        "decision",
        "reason",
        "evidence",
        "next_action",
        "run_id",
    )
    return {field: copy.deepcopy(value.get(field)) for field in fields}


def _identity_sources(
    *,
    symbol: str,
    company: Mapping[str, Any],
    screen: Mapping[str, Any] | None,
    universe_path: Path,
    screening_path: Path,
    repository: Path,
    accessed_at: dt.datetime,
) -> list[dict[str, Any]]:
    company_source = company.get("source")
    sources = [
        {
            "source_id": f"{symbol.split(':')[1]}-universe",
            "tier": "S2",
            "title": "冻结 universe 中的证券身份记录",
            "accessed_at": accessed_at.isoformat(),
            "url": company_source if _is_url(company_source) else None,
            "local_path": _repository_path(universe_path, repository),
        }
    ]
    ticker = symbol.split(":")[1]
    exchange = str(company.get("exchange") or "").upper()
    official_urls = {
        "SZSE": (
            "深交所上市公司公告与证券状态查询",
            f"https://www.szse.cn/disclosure/listed/notice/index.html?stock={ticker}",
        ),
        "SSE": (
            "上交所上市公司基本资料查询",
            "https://www.sse.com.cn/assortment/stock/list/info/company/"
            f"index.shtml?COMPANY_CODE={ticker}",
        ),
        "BSE": (
            "北交所上市公司信息查询",
            f"https://www.bse.cn/nq/listedcompany.html?companyCode={ticker}",
        ),
    }
    if exchange in official_urls:
        title, url = official_urls[exchange]
        sources.append(
            {
                "source_id": f"{ticker}-exchange-lookup",
                "tier": "S1",
                "title": title,
                "accessed_at": accessed_at.isoformat(),
                "url": url,
                "local_path": None,
            }
        )
    if screen is not None:
        sources.append(
            {
                "source_id": f"{symbol.split(':')[1]}-screening",
                "tier": "S3",
                "title": "冻结范围时使用的 screening 身份判定记录",
                "accessed_at": accessed_at.isoformat(),
                "url": None,
                "local_path": _repository_path(screening_path, repository),
            }
        )
        seen_urls = set()
        for item in screen.get("evidence") or []:
            text = str(item).strip()
            url = text[7:] if text.startswith("source:") else text
            if not _is_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            sources.append(
                {
                    "source_id": f"{symbol.split(':')[1]}-evidence-{len(seen_urls)}",
                    "tier": "S2",
                    "title": "screening 记录引用的证券身份来源",
                    "accessed_at": accessed_at.isoformat(),
                    "url": url,
                    "local_path": None,
                }
            )
    return sources


def _unique_rows(rows: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise QualityWorkflowError(f"{label} row must be an object")
        symbol = _symbol(row.get("symbol"))
        if symbol in result:
            raise QualityWorkflowError(f"duplicate {label} symbol: {symbol}")
        result[symbol] = row
    return result


def _load_sealed_json(
    path: Path, *, artifact_type: str, label: str
) -> tuple[Any, dict[str, Any]]:
    try:
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise QualityWorkflowError(f"{label} is not validly sealed: {path}: {exc}") from exc
    if sealed.artifact_type != artifact_type:
        raise QualityWorkflowError(f"{label} artifact type must be {artifact_type}")
    if not isinstance(payload, dict):
        raise QualityWorkflowError(f"{label} must be an object")
    return sealed, payload


def _seal(path: Path, payload: Mapping[str, Any], artifact_type: str, at: dt.datetime) -> Any:
    try:
        return seal_json(path, payload, artifact_type=artifact_type, sealed_at=at)
    except SealingError as exc:
        raise QualityWorkflowError(f"cannot seal {artifact_type}: {path}: {exc}") from exc


def _resolve_path(value: str | Path, repository: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repository / path
    return path.resolve()


def _repository_path(path: Path, repository: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repository).as_posix()
    except ValueError:
        return str(resolved)


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise QualityWorkflowError(f"{label} is missing or unreadable: {path}") from exc


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _subject_kind(value: Any) -> str:
    if value not in SUBJECT_KINDS:
        raise QualityWorkflowError(f"unsupported quality workflow subject kind: {value}")
    return str(value)


def _identifier(value: Any, label: str) -> str:
    text = _text(value, label)
    if not IDENTIFIER_RE.fullmatch(text):
        raise QualityWorkflowError(f"{label} is invalid")
    return text


def _symbol(value: Any) -> str:
    text = _text(value, "symbol")
    if not re.fullmatch(r"CN:[0-9]{6}", text):
        raise QualityWorkflowError(f"invalid CN symbol: {text}")
    return text


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise QualityWorkflowError(f"{label} is not a lowercase sha256")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityWorkflowError(f"{label} must be a non-empty string")
    return value.strip()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QualityWorkflowError(f"{label} must be an object")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise QualityWorkflowError(f"{label} must be an array")
    return value


def _datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise QualityWorkflowError(f"{label} must be an ISO datetime")
    try:
        result = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise QualityWorkflowError(f"{label} must be an ISO datetime") from exc
    _aware(result, label)
    return result


def _aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise QualityWorkflowError(f"{label} must include timezone information")


def _is_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))
