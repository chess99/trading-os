from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
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
from .legacy_transition import TRANSITION_ID as LEGACY_TRANSITION_ID
from .manager_screen_allocation_v3 import (
    CONTRACT_ARTIFACT_TYPE,
    CONTRACT_RELATIVE_PATH,
    ManagerScreenAllocationV3Error,
    verify_manager_screen_allocation_v3_contract,
)
from .manager_screen_allocation_v3_suspension import (
    SUSPENSION_ARTIFACT_TYPE,
    SUSPENSION_RELATIVE_PATH,
    ManagerScreenAllocationV3SuspensionError,
    verify_manager_screen_allocation_v3_suspension,
)
from .manager_screen_quote_impact import (
    ManagerScreenQuoteImpactError,
    load_manager_screen_quote_impact_overlay,
)
from .manager_screening import ManagerScreeningError, manager_screen_status
from .models import PolicyKind, PolicyValidationError, load_policy
from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed


class ManagerScreenFullMarketAllocationV3Error(ValueError):
    """Raised when the singleton full-market allocation cannot advance safely."""


WORKFLOW = "manager_screen_full_market_allocation_v3"
WORKFLOW_VERSION = 1
FULL_MARKET_RELATIVE_DIR = Path("governance") / "allocation-v3" / "full-market"
PACKET_RELATIVE_PATH = FULL_MARKET_RELATIVE_DIR / "packet.json"
RESULT_RELATIVE_PATH = FULL_MARKET_RELATIVE_DIR / "result.json"
PACKET_ARTIFACT_TYPE = "manager_screen_full_market_allocation_v3_packet"
RESULT_ARTIFACT_TYPE = "manager_screen_full_market_allocation_v3_result"
GRANTED_STAGE = "quick_profile"
FUNDED_STATE = "funded_quick_profile"
DEFERRED_STATE = "deferred_full_market"
PRECEDING_STAGE = "manager_screen_allocation_v3"
FUND_DECISION = "fund_quick_profile"
DEFER_DECISION = "defer_full_market"
RESOLVED_REMEDIATION = "resolved_by_existing_sealed_work"
TARGETED_REMEDIATION = "targeted_remediation_candidate"
DEFER_REMEDIATION = "defer_remediation"
LOCKED_REMEDIATIONS = {
    RESOLVED_REMEDIATION,
    TARGETED_REMEDIATION,
    DEFER_REMEDIATION,
}
ABSOLUTE_FUNDED_COMPANY_LIMIT = 200
ABSOLUTE_FUNDED_EFFORT_HOURS = 300.0

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MANAGER_KEYS = {"agent", "model", "tools"}
_SUBMISSION_KEYS = {
    "schema_version",
    "manager",
    "decisions",
    "locked_calibration_remediations",
}
_SUBMISSION_DECISION_KEYS = {
    "symbol",
    "candidate_sha256",
    "decision",
    "reason",
    "decisive_question",
    "evidence_ids",
    "revisit_triggers",
}
_LOCKED_REMEDIATION_KEYS = {
    "symbol",
    "locked_calibration_case_sha256",
    "remediation",
    "reason",
    "resolved_work_sha256",
    "decisive_question",
    "evidence_ids",
    "revisit_triggers",
}
_TRIGGER_KEYS = {"type", "condition", "reason"}
_TRIGGER_TYPES = {"filing", "price", "date", "ttl", "event", "thesis"}
_PURCHASE_FIELDS = {
    "effort_budget_hours",
    "preceding_stage",
    "stop_conditions",
}
_PROFILE_FIELDS = {
    "profile_evaluation_path",
    "profile_recorded_at",
    "profile_quick_selection_path",
    "profile_scoped_selection_path",
    "profile_priority_score",
}
_ALLOCATION_BINDING_FIELDS = {
    "manager_screen_allocation_result_path",
    "manager_screen_allocation_result_sha256",
    "manager_screen_allocation_candidate_sha256",
    "manager_screen_allocation_decision",
}
_CALIBRATION_PROJECTION_FIELDS = {
    "manager_screen_calibration_result_path",
    "manager_screen_calibration_result_sha256",
    "manager_screen_calibration_review_sha256",
    "manager_screen_calibration_adjudication_sha256",
}
_LOCKED_REMEDIATION_FIELD = "manager_screen_locked_calibration_remediation"
_SOURCE_TYPES = {
    "manager_screen_result",
    "manager_screen_quote_impact_result",
    "manager_screen_legacy_transition_result",
}
_CALIBRATION_CONTEXT_KEYS = {
    "calibration_result_path",
    "calibration_result_sha256",
    "calibration_result_sealed_at",
    "review",
    "review_sha256",
    "adjudication",
    "adjudication_sha256",
}
_CALIBRATION_REVIEW_KEYS = {
    "symbol",
    "material_errors",
    "route_disagreement",
    "adjudication",
}
_CALIBRATION_ERROR_KEYS = {"type", "finding", "evidence_ids"}
_CALIBRATION_ADJUDICATION_KEYS = {
    "performed",
    "outcome",
    "finding",
    "evidence_ids",
}
_TERMINAL_GOVERNANCE_MANIFEST_KEYS = {
    "path",
    "artifact_type",
    "sha256",
    "sealed_at",
}
_SEAL_SUFFIX = ".seal.json"
_IGNORED_TERMINAL_GOVERNANCE_PATHS = {
    "research-policy.json",
    "research-policy.snapshot.json",
}


@serialized_coverage_write
def prepare_manager_screen_full_market_allocation_v3(
    *,
    root: str | Path,
    run_id: str,
    prepared_at: dt.datetime,
) -> dict[str, Any]:
    """Seal the complete, scope-ordered candidate packet exactly once."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    timestamp = _aware(prepared_at, "prepared_at")
    packet_path = base / "manager-screen" / run / PACKET_RELATIVE_PATH
    result_path = base / "manager-screen" / run / RESULT_RELATIVE_PATH
    _require_pair_or_absent(packet_path, "full-market allocation packet")
    _require_pair_or_absent(result_path, "full-market allocation result")
    if result_path.exists() and not packet_path.exists():
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result exists without its packet"
        )
    if packet_path.exists():
        payload, sealed = _verified_packet(
            base=base,
            run_id=run,
            require_live_pool=not result_path.exists(),
        )
        if payload["prepared_at"] != timestamp.isoformat():
            raise ManagerScreenFullMarketAllocationV3Error(
                "sealed full-market allocation packet conflicts with prepared_at"
            )
        return _packet_summary(
            payload,
            packet_path=packet_path,
            packet_sha256=sealed.sha256,
            repository_root=repository_root,
            idempotent=True,
        )

    contract, contract_path, contract_sha256 = _verified_contract(
        base=base,
        run_id=run,
    )
    suspension, suspension_path, suspension_sha256 = _verified_suspension(
        base=base,
        run_id=run,
    )
    if timestamp < _parse_datetime(suspension["suspended_at"], "suspension.suspended_at"):
        raise ManagerScreenFullMarketAllocationV3Error(
            "prepared_at cannot predate the sealed v3 suspension"
        )
    quote = _fresh_quote_binding(
        base=base,
        run_id=run,
        prepared_at=timestamp,
    )
    status = _require_full_scope_ready(
        base=base,
        run_id=run,
        latest_quote=quote,
    )
    policy = _allocation_policy(
        contract=contract,
        repository_root=repository_root,
    )
    candidates, locked_calibration_cases = _build_candidate_pool(
        base=base,
        run_id=run,
        contract=contract,
        suspension=suspension,
    )
    capacity = _packet_capacity(contract=contract, policy=policy)
    terminal_governance_manifest = _terminal_governance_manifest(
        base=base,
        run_id=run,
        prepared_at=timestamp,
    )
    payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "workflow_version": WORKFLOW_VERSION,
        "run_id": run,
        "prepared_at": timestamp.isoformat(),
        "contract_path": _relative(contract_path, repository_root),
        "contract_sha256": contract_sha256,
        "suspension_path": _relative(suspension_path, repository_root),
        "suspension_sha256": suspension_sha256,
        "scope": dict(contract["scope"]),
        "quote": quote,
        "manager": dict(contract["manager"]),
        "policy": policy,
        "capacity": capacity,
        "full_scope_state": _full_scope_state(status),
        "instructions": _packet_instructions(),
        "candidates": candidates,
        "candidate_count": len(candidates),
        "candidates_sha256": _payload_sha256(candidates),
        "locked_calibration_cases": locked_calibration_cases,
        "locked_calibration_case_count": len(locked_calibration_cases),
        "locked_calibration_cases_sha256": _payload_sha256(
            locked_calibration_cases
        ),
        "terminal_governance_manifest": terminal_governance_manifest,
        "terminal_governance_manifest_count": len(
            terminal_governance_manifest
        ),
        "terminal_governance_manifest_sha256": _payload_sha256(
            terminal_governance_manifest
        ),
        "portfolio_action": None,
    }
    _validate_packet_payload(payload)
    try:
        sealed = seal_json(
            packet_path,
            payload,
            artifact_type=PACKET_ARTIFACT_TYPE,
            sealed_at=timestamp,
        )
    except SealingError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet could not be sealed"
        ) from exc
    return _packet_summary(
        payload,
        packet_path=packet_path,
        packet_sha256=sealed.sha256,
        repository_root=repository_root,
        idempotent=False,
    )


@serialized_coverage_write
def record_manager_screen_full_market_allocation_v3(
    *,
    root: str | Path,
    run_id: str,
    submission: Mapping[str, Any],
    recorded_at: dt.datetime,
) -> dict[str, Any]:
    """Seal the explicit full partition, then project it crash-recoverably."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    timestamp = _aware(recorded_at, "recorded_at")
    result_path = base / "manager-screen" / run / RESULT_RELATIVE_PATH
    _require_pair_or_absent(result_path, "full-market allocation result")
    packet, packet_seal = _verified_packet(
        base=base,
        run_id=run,
        require_live_pool=not result_path.exists(),
    )
    packet_path = base / "manager-screen" / run / PACKET_RELATIVE_PATH
    normalized = _normalize_submission(submission, packet=packet)
    packet_boundary = max(
        _parse_datetime(packet["prepared_at"], "packet.prepared_at"),
        packet_seal.sealed_at,
    )
    if timestamp <= packet_boundary:
        raise ManagerScreenFullMarketAllocationV3Error(
            "recorded_at must be strictly later than the full-market allocation packet"
        )
    latest_quote = _fresh_quote_binding(
        base=base,
        run_id=run,
        prepared_at=timestamp,
    )
    if latest_quote != packet["quote"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet is not bound to the latest quote "
            "amendment at recorded_at"
        )
    _require_quote_fresh_at(packet["quote"], timestamp)
    if result_path.exists():
        result, sealed = _verified_result(base=base, run_id=run)
        if (
            result["recorded_at"] != timestamp.isoformat()
            or result["manager"] != normalized["manager"]
            or result["decisions"] != normalized["decisions"]
            or result["locked_calibration_remediations"]
            != normalized["locked_calibration_remediations"]
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                "sealed full-market allocation result conflicts with request"
            )
        materialization = _materialize(
            base=base,
            repository_root=repository_root,
            packet=packet,
            result=result,
            result_path=result_path,
            result_sha256=sealed.sha256,
        )
        return _result_summary(
            result,
            result_path=result_path,
            result_sha256=sealed.sha256,
            repository_root=repository_root,
            idempotent=True,
            materialization=materialization,
        )

    selected_count = sum(
        decision["decision"] == FUND_DECISION for decision in normalized["decisions"]
    )
    deferred_count = len(normalized["decisions"]) - selected_count
    remediation_counts = {
        action: sum(
            decision["remediation"] == action
            for decision in normalized["locked_calibration_remediations"]
        )
        for action in LOCKED_REMEDIATIONS
    }
    capacity = packet["capacity"]
    if selected_count > capacity["selection_capacity"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            "funded quick-profile selection exceeds the sealed run capacity"
        )
    effort = float(capacity["purchase_effort_budget_hours"])
    locked_count = int(capacity["locked_company_count"])
    locked_hours = float(capacity["locked_effort_budget_hours"])
    effective_count = locked_count + selected_count
    effective_hours = locked_hours + selected_count * effort
    if (
        effective_count > capacity["absolute_funded_company_limit"]
        or effective_hours
        > float(capacity["absolute_funded_effort_budget_hours"]) + 1e-9
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation exceeds the absolute 200-company/300-hour cap"
        )
    profile_cycle_id = f"{run}-full-market-v3"
    _identifier(profile_cycle_id, "profile_cycle_id")
    result = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "workflow_version": WORKFLOW_VERSION,
        "run_id": run,
        "recorded_at": timestamp.isoformat(),
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_seal.sha256,
        "contract_path": packet["contract_path"],
        "contract_sha256": packet["contract_sha256"],
        "suspension_path": packet["suspension_path"],
        "suspension_sha256": packet["suspension_sha256"],
        "manager": normalized["manager"],
        "profile_cycle_id": profile_cycle_id,
        "granted_stage": GRANTED_STAGE,
        "purchase_effort_budget_hours": effort,
        "decisions": normalized["decisions"],
        "locked_calibration_remediations": normalized[
            "locked_calibration_remediations"
        ],
        "summary": {
            "candidate_count": packet["candidate_count"],
            "locked_calibration_case_count": packet[
                "locked_calibration_case_count"
            ],
            "locked_calibration_resolved_count": remediation_counts[
                RESOLVED_REMEDIATION
            ],
            "locked_calibration_targeted_candidate_count": remediation_counts[
                TARGETED_REMEDIATION
            ],
            "locked_calibration_deferred_count": remediation_counts[
                DEFER_REMEDIATION
            ],
            "locked_company_count": locked_count,
            "locked_effort_budget_hours": locked_hours,
            "selected_company_count": selected_count,
            "selected_effort_budget_hours": selected_count * effort,
            "deferred_company_count": deferred_count,
            "unused_company_capacity": capacity["selection_capacity"] - selected_count,
            "unused_effort_budget_hours": (
                capacity["selection_capacity"] - selected_count
            )
            * effort,
            "effective_funded_company_count": effective_count,
            "effective_funded_effort_budget_hours": effective_hours,
            "absolute_funded_company_limit": capacity["absolute_funded_company_limit"],
            "absolute_funded_effort_budget_hours": capacity[
                "absolute_funded_effort_budget_hours"
            ],
        },
        "portfolio_action": None,
    }
    _validate_result_payload(result, packet=packet)
    try:
        sealed = seal_json(
            result_path,
            result,
            artifact_type=RESULT_ARTIFACT_TYPE,
            sealed_at=timestamp,
        )
    except SealingError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result could not be sealed"
        ) from exc
    materialization = _materialize(
        base=base,
        repository_root=repository_root,
        packet=packet,
        result=result,
        result_path=result_path,
        result_sha256=sealed.sha256,
    )
    return _result_summary(
        result,
        result_path=result_path,
        result_sha256=sealed.sha256,
        repository_root=repository_root,
        idempotent=False,
        materialization=materialization,
    )


@serialized_coverage_write
def apply_manager_screen_full_market_allocation_v3(
    *,
    root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Resume or replay only the projection of an already sealed result."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    packet, _ = _verified_packet(base=base, run_id=run)
    result, sealed = _verified_result(base=base, run_id=run)
    result_path = base / "manager-screen" / run / RESULT_RELATIVE_PATH
    materialization = _materialize(
        base=base,
        repository_root=repository_root,
        packet=packet,
        result=result,
        result_path=result_path,
        result_sha256=sealed.sha256,
    )
    return _result_summary(
        result,
        result_path=result_path,
        result_sha256=sealed.sha256,
        repository_root=repository_root,
        idempotent=True,
        materialization=materialization,
    )


def manager_screen_full_market_allocation_v3_final_status(
    *,
    root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Verify both seals and report projection state without writing."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    packet, packet_seal = _verified_packet(base=base, run_id=run)
    result, result_seal = _verified_result(base=base, run_id=run)
    result_path = base / "manager-screen" / run / RESULT_RELATIVE_PATH
    projection = _projection_status(
        base=base,
        repository_root=repository_root,
        packet=packet,
        result=result,
        result_path=result_path,
        result_sha256=result_seal.sha256,
    )
    return {
        "schema_version": 1,
        "run_id": run,
        "packet_path": _relative(
            base / "manager-screen" / run / PACKET_RELATIVE_PATH,
            repository_root,
        ),
        "packet_sha256": packet_seal.sha256,
        "result_path": _relative(result_path, repository_root),
        "result_sha256": result_seal.sha256,
        "profile_cycle_id": result["profile_cycle_id"],
        "summary": dict(result["summary"]),
        "materialization": projection,
        "finalized": projection["fully_materialized"],
        "portfolio_action": None,
    }


def verify_manager_screen_full_market_allocation_v3_result(
    *,
    root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Public verifier used by profile claims and cohort binding."""

    result, sealed = _verified_result(base=Path(root), run_id=_identifier(run_id, "run_id"))
    return {**result, "result_sha256": sealed.sha256}


def _verified_contract(
    *,
    base: Path,
    run_id: str,
) -> tuple[dict[str, Any], Path, str]:
    try:
        contract = verify_manager_screen_allocation_v3_contract(root=base, run_id=run_id)
    except ManagerScreenAllocationV3Error as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "sealed allocation v3 contract is invalid"
        ) from exc
    path = base / "manager-screen" / run_id / CONTRACT_RELATIVE_PATH
    try:
        sealed = verify_sealed(path)
    except (OSError, SealingError) as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "sealed allocation v3 contract is invalid"
        ) from exc
    if sealed.artifact_type != CONTRACT_ARTIFACT_TYPE:
        raise ManagerScreenFullMarketAllocationV3Error(
            "allocation v3 contract artifact type is invalid"
        )
    return contract, path, sealed.sha256


def _verified_suspension(
    *,
    base: Path,
    run_id: str,
    require_projection: bool = False,
) -> tuple[dict[str, Any], Path, str]:
    try:
        status = verify_manager_screen_allocation_v3_suspension(root=base, run_id=run_id)
    except ManagerScreenAllocationV3SuspensionError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "sealed allocation v3 suspension is invalid"
        ) from exc
    if require_projection and not status["materialization"]["fully_materialized"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            "allocation v3 suspension must be fully projected before final allocation"
        )
    path = base / "manager-screen" / run_id / SUSPENSION_RELATIVE_PATH
    payload, sealed = _sealed_object(path, artifact_type=SUSPENSION_ARTIFACT_TYPE)
    return payload, path, sealed.sha256


def _verified_packet(
    *,
    base: Path,
    run_id: str,
    require_live_pool: bool = False,
) -> tuple[dict[str, Any], Any]:
    path = base / "manager-screen" / run_id / PACKET_RELATIVE_PATH
    payload, sealed = _sealed_object(path, artifact_type=PACKET_ARTIFACT_TYPE)
    _validate_packet_payload(payload)
    if payload["run_id"] != run_id:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet run_id does not match its path"
        )
    contract, contract_path, contract_sha256 = _verified_contract(base=base, run_id=run_id)
    suspension, suspension_path, suspension_sha256 = _verified_suspension(
        base=base,
        run_id=run_id,
    )
    repository_root = base.parent.parent.resolve()
    prepared_at = _parse_datetime(payload["prepared_at"], "packet.prepared_at")
    expected_terminal_governance_manifest = _terminal_governance_manifest(
        base=base,
        run_id=run_id,
        prepared_at=prepared_at,
    )
    if (
        payload["terminal_governance_manifest"]
        != expected_terminal_governance_manifest
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet terminal governance manifest drifted"
        )
    if prepared_at < _parse_datetime(suspension["suspended_at"], "suspension.suspended_at"):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet predates the sealed suspension"
        )
    expected_quote = _fresh_quote_binding(
        base=base,
        run_id=run_id,
        prepared_at=prepared_at,
    )
    status = _require_full_scope_ready(
        base=base,
        run_id=run_id,
        latest_quote=expected_quote,
    )
    expected_policy = _allocation_policy(
        contract=contract,
        repository_root=repository_root,
    )
    expected_capacity = _packet_capacity(
        contract=contract,
        policy=expected_policy,
    )
    prior_candidates = None
    if not require_live_pool:
        prior_candidates = {
            candidate["symbol"]: candidate for candidate in payload["candidates"]
        }
    prior_locked_calibration_cases = {
        case["symbol"]: case for case in payload["locked_calibration_cases"]
    }
    expected_candidates, expected_locked_calibration_cases = _build_candidate_pool(
        base=base,
        run_id=run_id,
        contract=contract,
        suspension=suspension,
        prior_candidates=prior_candidates,
        prior_locked_calibration_cases=prior_locked_calibration_cases,
    )
    if (
        payload["contract_path"] != _relative(contract_path, repository_root)
        or payload["contract_sha256"] != contract_sha256
        or payload["suspension_path"] != _relative(suspension_path, repository_root)
        or payload["suspension_sha256"] != suspension_sha256
        or payload["manager"] != contract["manager"]
        or payload["scope"] != contract["scope"]
        or payload["quote"] != expected_quote
        or payload["policy"] != expected_policy
        or payload["capacity"] != expected_capacity
        or payload["full_scope_state"] != _full_scope_state(status)
        or payload["instructions"] != _packet_instructions()
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet governance binding is invalid"
        )
    if payload["candidates"] != expected_candidates:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet candidate pool drifted"
        )
    if payload["locked_calibration_cases"] != expected_locked_calibration_cases:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet locked calibration cases drifted"
        )
    return payload, sealed


def _verified_result(
    *,
    base: Path,
    run_id: str,
) -> tuple[dict[str, Any], Any]:
    packet, packet_seal = _verified_packet(base=base, run_id=run_id)
    path = base / "manager-screen" / run_id / RESULT_RELATIVE_PATH
    payload, sealed = _sealed_object(path, artifact_type=RESULT_ARTIFACT_TYPE)
    _validate_result_payload(payload, packet=packet)
    repository_root = base.parent.parent.resolve()
    if _parse_datetime(payload["recorded_at"], "result.recorded_at") <= max(
        _parse_datetime(packet["prepared_at"], "packet.prepared_at"),
        packet_seal.sealed_at,
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result is not strictly later than its packet"
        )
    if (
        payload["run_id"] != run_id
        or payload["packet_path"]
        != _relative(
            base / "manager-screen" / run_id / PACKET_RELATIVE_PATH,
            repository_root,
        )
        or payload["packet_sha256"] != packet_seal.sha256
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result packet binding is invalid"
        )
    return payload, sealed


def _require_full_scope_ready(
    *,
    base: Path,
    run_id: str,
    latest_quote: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        status = manager_screen_status(root=base, run_id=run_id)
    except ManagerScreeningError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "manager-screen scope status is invalid"
        ) from exc
    if (
        status.get("remaining_unbatched_count") != 0
        or status.get("open_batches") != 0
        or status.get("open_company_count") != 0
        or (status.get("control") or {}).get("state") != "paused"
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation requires a complete scope paused with no open work"
        )
    screenable = status.get("screenable_intake_count")
    if isinstance(screenable, int) and (
        status.get("completed_company_count", 0)
        + status.get("deferred_current_state_count", 0)
        != screenable
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation scope conservation is incomplete"
        )
    transition = status.get("legacy_transition")
    if isinstance(transition, Mapping) and transition.get("state") == "frozen":
        raise ManagerScreenFullMarketAllocationV3Error(
            "legacy transition must be recorded before full-market allocation"
        )
    calibration = status.get("calibration")
    if isinstance(calibration, Mapping) and calibration.get("status") in {
        "missing",
        "planned",
    }:
        raise ManagerScreenFullMarketAllocationV3Error(
            "manager-screen calibration/QA must be complete before full-market allocation"
        )
    for batch in status.get("batches") or []:
        batch_calibration = batch.get("calibration") if isinstance(batch, Mapping) else None
        if isinstance(batch_calibration, Mapping):
            calibration_status = batch_calibration.get("status")
            if calibration_status in {"missing", "planned"}:
                raise ManagerScreenFullMarketAllocationV3Error(
                    "every applicable manager-screen calibration must be terminal "
                    "before full-market allocation"
                )
            if calibration_status in {"complete", "material_error"}:
                planned = batch_calibration.get("planned_sample_count")
                reviewed = batch_calibration.get("reviewed_sample_count")
                missing = batch_calibration.get("missing_sample_count")
                if missing != 0 or reviewed != planned:
                    raise ManagerScreenFullMarketAllocationV3Error(
                        "manager-screen calibration coverage must be complete "
                        "before full-market allocation"
                    )
                material_error_symbols = batch_calibration.get(
                    "material_error_symbols",
                    [],
                )
                adjudicated_symbols = batch_calibration.get("adjudicated_symbols", [])
                material_error_count = batch_calibration.get("material_error_count", 0)
                if (
                    not isinstance(material_error_symbols, list)
                    or not isinstance(adjudicated_symbols, list)
                    or any(not isinstance(symbol, str) for symbol in material_error_symbols)
                    or any(not isinstance(symbol, str) for symbol in adjudicated_symbols)
                    or (
                        isinstance(material_error_count, int)
                        and material_error_count > 0
                        and not material_error_symbols
                    )
                    or not set(material_error_symbols).issubset(adjudicated_symbols)
                ):
                    raise ManagerScreenFullMarketAllocationV3Error(
                        "each manager-screen material-error company requires one terminal "
                        "adjudication before full-market allocation"
                    )
        review = batch.get("quote_impact_review") if isinstance(batch, Mapping) else None
        if isinstance(review, Mapping) and review.get("state") == "prepared":
            raise ManagerScreenFullMarketAllocationV3Error(
                "all quote-impact reviews must be terminal before full-market allocation"
            )
    if latest_quote is not None:
        _require_latest_quote_impact_reviews(
            base=base,
            run_id=run_id,
            status=status,
            latest_quote=latest_quote,
        )
    return status


def _require_latest_quote_impact_reviews(
    *,
    base: Path,
    run_id: str,
    status: Mapping[str, Any],
    latest_quote: Mapping[str, Any],
) -> None:
    latest_path = _text(latest_quote.get("path"), "latest quote amendment path")
    latest_sha256 = _sha256(
        latest_quote.get("sha256"),
        "latest quote amendment sha256",
    )
    for batch in status.get("batches") or []:
        if not isinstance(batch, Mapping) or batch.get("status") != "completed":
            continue
        batch_id = _identifier(batch.get("batch_id"), "batch_id")
        original = batch.get("quote_amendment")
        original_is_latest = bool(
            isinstance(original, Mapping)
            and original.get("path") == latest_path
            and original.get("sha256") == latest_sha256
        )
        try:
            overlay = load_manager_screen_quote_impact_overlay(
                root=base,
                run_id=run_id,
                batch_id=batch_id,
            )
        except ManagerScreenQuoteImpactError as exc:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"quote-impact overlay is invalid: {batch_id}"
            ) from exc
        if overlay.get("state") == "prepared":
            raise ManagerScreenFullMarketAllocationV3Error(
                f"latest quote-impact review is unfinished: {batch_id}"
            )
        if original_is_latest and overlay.get("state") == "absent":
            continue
        if (
            overlay.get("state") != "recorded"
            or overlay.get("quote_amendment_path") != latest_path
            or overlay.get("quote_amendment_sha256") != latest_sha256
            or not overlay.get("result_path")
            or not overlay.get("result_sha256")
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                "every completed batch on an older quote amendment requires a sealed "
                f"terminal overlay for the latest amendment: {batch_id}"
            )


def _fresh_quote_binding(
    *,
    base: Path,
    run_id: str,
    prepared_at: dt.datetime,
) -> dict[str, Any]:
    snapshot_path = base / "snapshots" / run_id / "companies.jsonl"
    if not snapshot_path.is_file():
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation requires the frozen company snapshot"
        )
    repository_root = base.parent.parent.resolve()
    try:
        from .manager_screening import _latest_quote_amendment

        reference, amendment = _latest_quote_amendment(
            base=base,
            run_id=run_id,
            base_snapshot_path=snapshot_path,
            frozen_at=prepared_at,
            repository_root=repository_root,
        )
    except (ManagerScreeningError, OSError) as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation quote amendment is invalid"
        ) from exc
    if not isinstance(reference, Mapping) or not isinstance(amendment, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation requires a sealed whole-universe quote amendment"
        )
    quotes = amendment.get("quotes")
    policy = amendment.get("quote_freshness_policy")
    if not isinstance(quotes, list) or not quotes or not isinstance(policy, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation quote amendment is incomplete"
        )
    as_of_values = [
        _parse_datetime(quote.get("as_of"), "quote.as_of")
        for quote in quotes
        if isinstance(quote, Mapping)
    ]
    if len(as_of_values) != len(quotes):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation quote rows are invalid"
        )
    max_age_seconds = _capacity_int(policy.get("max_age_seconds"), "quote.max_age_seconds")
    future_tolerance_seconds = _capacity_int(
        policy.get("future_tolerance_seconds"),
        "quote.future_tolerance_seconds",
    )
    oldest = min(as_of_values)
    newest = max(as_of_values)
    if prepared_at - oldest > dt.timedelta(seconds=max_age_seconds):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation quotes are stale at prepared_at"
        )
    if newest - prepared_at > dt.timedelta(seconds=future_tolerance_seconds):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation quotes are in the future"
        )
    return {
        "amendment_id": reference["amendment_id"],
        "path": reference["path"],
        "sha256": reference["sha256"],
        "effective_at": reference["effective_at"],
        "quote_count": len(quotes),
        "oldest_quote_as_of": oldest.isoformat(),
        "newest_quote_as_of": newest.isoformat(),
        "max_age_seconds": max_age_seconds,
        "future_tolerance_seconds": future_tolerance_seconds,
    }


def _require_quote_fresh_at(quote: Mapping[str, Any], at: dt.datetime) -> None:
    oldest = _parse_datetime(quote.get("oldest_quote_as_of"), "quote.oldest_quote_as_of")
    newest = _parse_datetime(quote.get("newest_quote_as_of"), "quote.newest_quote_as_of")
    if at - oldest > dt.timedelta(seconds=int(quote["max_age_seconds"])):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation quotes became stale before record"
        )
    if newest - at > dt.timedelta(seconds=int(quote["future_tolerance_seconds"])):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation quote timestamp is in the future"
        )


def _allocation_policy(
    *,
    contract: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    path = _repository_path(contract["future_policy"]["path"], repository_root)
    try:
        policy = load_policy(path)
    except (OSError, PolicyValidationError) as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "allocation v3 future policy is invalid"
        ) from exc
    if policy.kind is not PolicyKind.MANAGER_SCREENING:
        raise ManagerScreenFullMarketAllocationV3Error(
            "allocation v3 future policy kind is invalid"
        )
    stops = policy.payload.get("quick_profile_stop_conditions")
    if (
        not isinstance(stops, list)
        or not stops
        or any(not isinstance(item, str) or not item.strip() for item in stops)
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "allocation v3 quick-profile stop conditions are invalid"
        )
    return {
        "path": contract["future_policy"]["path"],
        "file_sha256": contract["future_policy"]["file_sha256"],
        "payload_sha256": contract["future_policy"]["payload_sha256"],
        "quick_profile_effort_budget_hours": contract["future_policy"][
            "quick_profile_effort_budget_hours"
        ],
        "quick_profile_stop_conditions": [item.strip() for item in stops],
    }


def _packet_capacity(
    *,
    contract: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    contract_capacity = contract.get("capacity")
    if not isinstance(contract_capacity, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            "sealed v3 contract capacity is invalid"
        )
    locked = sorted(
        item["symbol"]
        for item in contract["commitment_classification"]
        if item["commitment_class"] == "irreversible"
    )
    absolute_company_limit = _capacity_int(
        contract_capacity.get("absolute_funded_company_limit"),
        "contract.capacity.absolute_funded_company_limit",
    )
    absolute_effort_limit = _positive_hours(
        contract_capacity.get("absolute_funded_effort_budget_hours"),
        "contract.capacity.absolute_funded_effort_budget_hours",
    )
    selection_capacity = _capacity_int(
        contract_capacity.get("post_scope_selection_capacity"),
        "contract.capacity.post_scope_selection_capacity",
    )
    purchase_effort = _positive_hours(
        contract_capacity.get("purchase_effort_budget_hours"),
        "contract.capacity.purchase_effort_budget_hours",
    )
    policy_effort = _positive_hours(
        policy.get("quick_profile_effort_budget_hours"),
        "policy.quick_profile_effort_budget_hours",
    )
    locked_hours = float(
        contract_capacity.get("irreversible_effort_budget_hours", -1)
    )
    if (
        absolute_company_limit != ABSOLUTE_FUNDED_COMPANY_LIMIT
        or not math.isclose(
            absolute_effort_limit,
            ABSOLUTE_FUNDED_EFFORT_HOURS,
            rel_tol=0,
            abs_tol=1e-9,
        )
        or selection_capacity != absolute_company_limit - len(locked)
        or selection_capacity < 0
        or not math.isclose(purchase_effort, policy_effort, rel_tol=0, abs_tol=1e-9)
        or not math.isclose(
            locked_hours,
            len(locked) * purchase_effort,
            rel_tol=0,
            abs_tol=1e-9,
        )
        or locked_hours + selection_capacity * purchase_effort
        > absolute_effort_limit + 1e-9
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "sealed v3 contract capacity must preserve the 200-company/300-hour cap"
        )
    return {
        "absolute_funded_company_limit": absolute_company_limit,
        "absolute_funded_effort_budget_hours": absolute_effort_limit,
        "locked_company_count": len(locked),
        "locked_effort_budget_hours": locked_hours,
        "locked_symbols": locked,
        "selection_capacity": selection_capacity,
        "purchase_effort_budget_hours": purchase_effort,
    }


def _full_scope_state(status: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "screenable_intake_count": status.get("screenable_intake_count"),
        "completed_company_count": status["completed_company_count"],
        "deferred_current_state_count": status.get("deferred_current_state_count", 0),
        "remaining_unbatched_count": status["remaining_unbatched_count"],
        "open_batch_count": status["open_batches"],
        "open_company_count": status["open_company_count"],
        "control_state": status["control"]["state"],
    }


def _packet_instructions() -> dict[str, Any]:
    return {
        "complete_partition_required": True,
        "allowed_decisions": [FUND_DECISION, DEFER_DECISION],
        "ranking_or_score_forbidden": True,
        "granted_stage": GRANTED_STAGE,
        "defer_revisit_triggers_required": True,
        "allocation_research_brief_required": True,
        "calibration_error_evidence_must_be_carried_forward": True,
        "locked_calibration_cases_are_not_selection_candidates": True,
        "locked_calibration_allowed_remediations": [
            RESOLVED_REMEDIATION,
            TARGETED_REMEDIATION,
            DEFER_REMEDIATION,
        ],
        "locked_calibration_remediation_cannot_purchase_budget": True,
        "unused_capacity_is_permanently_forfeited": True,
        "portfolio_action_forbidden": True,
    }


def _build_candidate_pool(
    *,
    base: Path,
    run_id: str,
    contract: Mapping[str, Any],
    suspension: Mapping[str, Any],
    prior_candidates: Mapping[str, Mapping[str, Any]] | None = None,
    prior_locked_calibration_cases: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    repository_root = base.parent.parent.resolve()
    queue = _unique_rows(base / RESEARCH_QUEUE_FILE, "research queue")
    screening = _unique_rows(base / SCREENING_FILE, "screening")
    scope = _scope_members(base=base, run_id=run_id)
    suspension_path = base / "manager-screen" / run_id / SUSPENSION_RELATIVE_PATH
    sealed_suspension, suspension_seal = _sealed_object(
        suspension_path,
        artifact_type=SUSPENSION_ARTIFACT_TYPE,
    )
    if sealed_suspension != suspension:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market candidate pool suspension binding drifted"
        )
    suspension_relative = _relative(suspension_path, repository_root)

    def candidate_rows(symbol: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        prior = prior_candidates.get(symbol) if prior_candidates is not None else None
        if isinstance(prior, Mapping):
            prior_queue = prior.get("prior_queue_row")
            prior_screen = prior.get("prior_screening_row")
            return (
                dict(prior_queue) if isinstance(prior_queue, Mapping) else None,
                dict(prior_screen) if isinstance(prior_screen, Mapping) else None,
            )
        return queue.get(symbol), screening.get(symbol)

    locked_classifications = {
        item["symbol"]: item
        for item in contract["commitment_classification"]
        if item["commitment_class"] == "irreversible"
    }
    locked = set(locked_classifications)
    activation_queue = contract.get("activation_queue")
    if not isinstance(activation_queue, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            "sealed v3 contract activation queue is invalid"
        )
    purchased_states = {
        item["symbol"]: item
        for item in activation_queue.get("purchased_states") or []
        if isinstance(item, Mapping) and isinstance(item.get("symbol"), str)
    }
    inherited_purchases = {
        item["symbol"]: item
        for item in contract.get("inherited_ledger") or []
        if isinstance(item, Mapping) and isinstance(item.get("symbol"), str)
    }
    candidates: dict[str, dict[str, Any]] = {}
    locked_calibration_cases: dict[str, dict[str, Any]] = {}
    for member in suspension["members"]:
        symbol = _symbol(member.get("symbol"))
        if symbol in locked:
            continue
        queued, screen = candidate_rows(symbol)
        if queued is None or screen is None:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"suspended candidate projection is missing: {symbol}"
            )
        source_path, source_sha, sealed, decision = (
            _suspended_candidate_effective_source(
                queued=queued,
                screen=screen,
                member=member,
                symbol=symbol,
                run_id=run_id,
                repository_root=repository_root,
                suspension_relative=suspension_relative,
                suspension_sha256=suspension_seal.sha256,
            )
        )
        candidate = _candidate(
            symbol=symbol,
            origin="suspended_v2",
            source_path=source_path,
            source_sha256=source_sha,
            source_type=sealed.artifact_type,
            decision=decision,
            queued=queued,
            screen=screen,
            scope=scope,
        )
        candidates[symbol] = candidate

    run_dir = base / "manager-screen" / run_id
    for batch_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        batch_path = batch_dir / "batch.json"
        if not batch_path.exists():
            continue
        batch, batch_seal = _sealed_object(batch_path, artifact_type="manager_screen_batch")
        if batch.get("run_id") != run_id or batch.get("batch_id") != batch_dir.name:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"manager-screen batch identity is invalid: {batch_dir.name}"
            )
        supersession_path = batch_dir / "supersession.json"
        _require_pair_or_absent(supersession_path, "manager-screen supersession")
        if supersession_path.exists():
            _sealed_object(
                supersession_path,
                artifact_type="manager_screen_batch_supersession",
            )
            continue
        policy = batch.get("policy")
        if not isinstance(policy, Mapping):
            raise ManagerScreenFullMarketAllocationV3Error(
                f"manager-screen batch policy is invalid: {batch_dir.name}"
            )
        is_v3_batch = policy.get("decision_contract_version") == 3
        result_path = batch_dir / "result.json"
        _require_pair_or_absent(result_path, "manager-screen result")
        if not result_path.exists():
            continue
        result, result_seal = _sealed_object(
            result_path,
            artifact_type="manager_screen_result",
        )
        if (
            result.get("batch_sha256") != batch_seal.sha256
            or result.get("run_id") != run_id
            or result.get("batch_id") != batch_dir.name
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                f"manager-screen result binding is invalid: {batch_dir.name}"
            )
        calibration_contexts = _calibration_material_error_contexts(
            batch_dir=batch_dir,
            run_id=run_id,
            batch_id=batch_dir.name,
            manager_result_sha256=result_seal.sha256,
            repository_root=repository_root,
        )
        if not is_v3_batch and not calibration_contexts:
            continue
        original_path = _relative(result_path, repository_root)
        effective: dict[str, tuple[dict[str, Any], str, str, str]] = {
            decision["symbol"]: (
                dict(decision),
                original_path,
                result_seal.sha256,
                result_seal.artifact_type,
            )
            for decision in result.get("decisions") or []
            if isinstance(decision, Mapping) and isinstance(decision.get("symbol"), str)
        }
        try:
            overlay = load_manager_screen_quote_impact_overlay(
                root=base,
                run_id=run_id,
                batch_id=batch_dir.name,
            )
        except ManagerScreenQuoteImpactError as exc:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"quote-impact overlay is invalid: {batch_dir.name}"
            ) from exc
        if overlay["state"] == "prepared":
            raise ManagerScreenFullMarketAllocationV3Error(
                f"quote-impact overlay is unfinished: {batch_dir.name}"
            )
        if overlay["state"] == "recorded":
            decisions = overlay.get("effective_decisions")
            sources = overlay.get("effective_decision_sources")
            if (
                not isinstance(decisions, list)
                or not isinstance(sources, list)
                or len(decisions) != len(sources)
            ):
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"quote-impact cumulative decisions are invalid: {batch_dir.name}"
                )
            composed: dict[str, tuple[dict[str, Any], str, str, str]] = {}
            for decision, source in zip(decisions, sources, strict=True):
                if (
                    not isinstance(decision, Mapping)
                    or not isinstance(source, Mapping)
                    or decision.get("symbol") != source.get("symbol")
                    or source.get("artifact_type") not in _SOURCE_TYPES
                ):
                    raise ManagerScreenFullMarketAllocationV3Error(
                        f"quote-impact decision source is invalid: {batch_dir.name}"
                    )
                symbol = _symbol(decision.get("symbol"))
                if symbol in composed:
                    raise ManagerScreenFullMarketAllocationV3Error(
                        f"quote-impact cumulative decision is duplicated: {symbol}"
                    )
                composed[symbol] = (
                    dict(decision),
                    _text(source.get("path"), "quote-impact decision source path"),
                    _sha256(
                        source.get("sha256"),
                        "quote-impact decision source sha256",
                    ),
                    str(source["artifact_type"]),
                )
            if set(composed) != set(effective):
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"quote-impact cumulative decision coverage drifted: {batch_dir.name}"
                )
            effective = composed
        members = {
            member["symbol"]: member
            for member in batch.get("members") or []
            if isinstance(member, Mapping) and isinstance(member.get("symbol"), str)
        }
        for symbol, (decision, source_path, source_sha, source_type) in effective.items():
            calibration_context = calibration_contexts.pop(symbol, None)
            is_v3_candidate = bool(
                is_v3_batch and decision.get("route") == "research_candidate"
            )
            if not is_v3_candidate and calibration_context is None:
                continue
            if symbol in locked:
                if calibration_context is None or is_v3_candidate:
                    raise ManagerScreenFullMarketAllocationV3Error(
                        "v3 candidate overlaps an irreversible commitment: "
                        f"{symbol}"
                    )
                if symbol in locked_calibration_cases:
                    raise ManagerScreenFullMarketAllocationV3Error(
                        f"locked calibration case is duplicated: {symbol}"
                    )
                queued, screen = candidate_rows(symbol)
                member = members.get(symbol)
                if queued is None or screen is None or member is None:
                    raise ManagerScreenFullMarketAllocationV3Error(
                        f"locked calibration case projection is missing: {symbol}"
                    )
                prior_case = (
                    prior_locked_calibration_cases.get(symbol)
                    if prior_locked_calibration_cases is not None
                    else None
                )
                locked_calibration_cases[symbol] = _locked_calibration_case(
                    symbol=symbol,
                    source_path=source_path,
                    source_sha256=source_sha,
                    source_type=source_type,
                    decision=decision,
                    calibration_context=calibration_context,
                    classification=locked_classifications[symbol],
                    purchased_state=purchased_states.get(symbol),
                    inherited_purchase=inherited_purchases.get(symbol),
                    queued=queued,
                    screen=screen,
                    scope=scope,
                    prior_case=prior_case,
                    run_id=run_id,
                )
                continue
            existing = candidates.get(symbol)
            if existing is not None:
                if calibration_context is None:
                    raise ManagerScreenFullMarketAllocationV3Error(
                        f"full-market candidate is duplicated: {symbol}"
                    )
                if (
                    existing["effective_decision_source_path"] != source_path
                    or existing["effective_decision_source_sha256"] != source_sha
                    or existing["effective_decision_sha256"] != _payload_sha256(decision)
                ):
                    raise ManagerScreenFullMarketAllocationV3Error(
                        f"calibration context does not match the candidate decision: {symbol}"
                    )
                candidates[symbol] = _candidate_with_calibration_context(
                    existing,
                    calibration_context=calibration_context,
                )
                continue
            queued, screen = candidate_rows(symbol)
            member = members.get(symbol)
            if queued is None or screen is None or member is None:
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"full-market candidate projection is missing: {symbol}"
                )
            if (
                queued.get("manager_screen_run_id") != run_id
                or queued.get("manager_screen_batch_id") != batch_dir.name
                or queued.get("manager_screen_route") != decision.get("route")
                or queued.get("manager_screen_result_path") != source_path
                or queued.get("manager_screen_result_sha256") != source_sha
                or screen.get("manager_screen_result_path") != source_path
                or screen.get("manager_screen_result_sha256") != source_sha
                or (
                    is_v3_candidate
                    and (
                        queued.get("research_budget_state") != "candidate_unfunded"
                        or screen.get("research_budget_state") != "candidate_unfunded"
                    )
                )
                or (
                    not is_v3_candidate
                    and (
                        queued.get("task_type") != "manager_screen"
                        or queued.get("status") != "completed"
                    )
                )
            ):
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"candidate projection drifted from its effective decision: {symbol}"
                )
            candidate = _candidate(
                symbol=symbol,
                origin=(
                    "v3_research_candidate"
                    if is_v3_candidate
                    else "calibration_material_error"
                ),
                source_path=source_path,
                source_sha256=source_sha,
                source_type=source_type,
                decision=decision,
                queued=queued,
                screen=screen,
                scope=scope,
                calibration_material_error=calibration_context,
            )
            if member.get("scope_ordinal") != candidate["scope_ordinal"]:
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"candidate scope ordinal drifted: {symbol}"
                )
            candidates[symbol] = candidate
        if calibration_contexts:
            raise ManagerScreenFullMarketAllocationV3Error(
                "calibration material-error review lacks an effective manager decision: "
                f"{sorted(calibration_contexts)}"
            )
    ordered = sorted(
        candidates.values(),
        key=lambda item: (item["scope_ordinal"], item["symbol"]),
    )
    ordered_locked_cases = sorted(
        locked_calibration_cases.values(),
        key=lambda item: (item["scope_ordinal"], item["symbol"]),
    )
    return ordered, ordered_locked_cases


def _scope_members(
    *,
    base: Path,
    run_id: str,
) -> dict[str, dict[str, Any]]:
    run_dir = base / "manager-screen" / run_id
    if not run_dir.is_dir():
        raise ManagerScreenFullMarketAllocationV3Error(
            "manager-screen run directory is missing"
        )
    result: dict[str, dict[str, Any]] = {}
    for batch_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        batch_path = batch_dir / "batch.json"
        if not batch_path.exists():
            continue
        batch, _ = _sealed_object(batch_path, artifact_type="manager_screen_batch")
        if batch.get("run_id") != run_id or batch.get("batch_id") != batch_dir.name:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"manager-screen batch identity is invalid: {batch_dir.name}"
            )
        supersession_path = batch_dir / "supersession.json"
        _require_pair_or_absent(supersession_path, "manager-screen supersession")
        if supersession_path.exists():
            _sealed_object(
                supersession_path,
                artifact_type="manager_screen_batch_supersession",
            )
            continue
        members = batch.get("members")
        if not isinstance(members, list):
            raise ManagerScreenFullMarketAllocationV3Error(
                f"manager-screen batch members are invalid: {batch_dir.name}"
            )
        for member in members:
            if not isinstance(member, Mapping):
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"manager-screen batch member is invalid: {batch_dir.name}"
                )
            symbol = _symbol(member.get("symbol"))
            if symbol in result:
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"active manager-screen batches duplicate a symbol: {symbol}"
                )
            result[symbol] = {
                "scope_ordinal": _positive_int(
                    member.get("scope_ordinal"),
                    "batch member scope_ordinal",
                ),
                "name": _text(member.get("name"), "batch member name"),
                "batch_id": batch_dir.name,
            }
    transition = _legacy_transition_scope_members(
        base=base,
        run_id=run_id,
        ordinal_offset=max(
            (member["scope_ordinal"] for member in result.values()),
            default=0,
        ),
    )
    duplicated = sorted(set(result) & set(transition))
    if duplicated:
        raise ManagerScreenFullMarketAllocationV3Error(
            "active manager-screen batches overlap legacy transition adoption: "
            f"{duplicated}"
        )
    result.update(transition)
    return result


def _legacy_transition_scope_members(
    *,
    base: Path,
    run_id: str,
    ordinal_offset: int,
) -> dict[str, dict[str, Any]]:
    """Append recorded adoption members after the active manager-screen ordinals."""

    transition_dir = base / "manager-screen" / run_id / LEGACY_TRANSITION_ID
    if not transition_dir.exists():
        return {}
    if not transition_dir.is_dir():
        raise ManagerScreenFullMarketAllocationV3Error(
            "legacy transition path is not a directory"
        )
    plan_path = transition_dir / "plan.json"
    packet_path = transition_dir / "packet.json"
    result_path = transition_dir / "result.json"
    for path, label in (
        (plan_path, "legacy transition plan"),
        (packet_path, "legacy transition packet"),
        (result_path, "legacy transition result"),
    ):
        _require_pair_or_absent(path, label)
        if not path.exists():
            raise ManagerScreenFullMarketAllocationV3Error(
                f"{label} must be sealed before full-market allocation"
            )

    plan, plan_seal = _sealed_object(
        plan_path,
        artifact_type="manager_screen_legacy_transition_plan",
    )
    packet, packet_seal = _sealed_object(
        packet_path,
        artifact_type="manager_screen_legacy_transition_packet",
    )
    transition_result, result_seal = _sealed_object(
        result_path,
        artifact_type="manager_screen_legacy_transition_result",
    )
    repository_root = base.parent.parent.resolve()
    plan_relative = _relative(plan_path, repository_root)
    packet_relative = _relative(packet_path, repository_root)
    result_relative = _relative(result_path, repository_root)
    if (
        plan.get("run_id") != run_id
        or plan.get("transition_id") != LEGACY_TRANSITION_ID
        or packet.get("run_id") != run_id
        or packet.get("transition_id") != LEGACY_TRANSITION_ID
        or packet.get("plan_path") != plan_relative
        or packet.get("plan_sha256") != plan_seal.sha256
        or transition_result.get("run_id") != run_id
        or transition_result.get("transition_id") != LEGACY_TRANSITION_ID
        or transition_result.get("plan_path") != plan_relative
        or transition_result.get("plan_sha256") != plan_seal.sha256
        or transition_result.get("packet_path") != packet_relative
        or transition_result.get("packet_sha256") != packet_seal.sha256
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "legacy transition plan/packet/result binding is invalid"
        )

    members = plan.get("members")
    decisions = transition_result.get("decisions")
    if not isinstance(members, list) or not isinstance(decisions, list):
        raise ManagerScreenFullMarketAllocationV3Error(
            "legacy transition members or decisions are invalid"
        )
    adoption_symbols = []
    ordered_members = []
    for position, member in enumerate(members, 1):
        if not isinstance(member, Mapping) or member.get("ordinal") != position:
            raise ManagerScreenFullMarketAllocationV3Error(
                "legacy transition member order is invalid"
            )
        symbol = _symbol(member.get("symbol"))
        if member.get("action") == "adoption":
            adoption_symbols.append(symbol)
            ordered_members.append((position, member))
    if len(adoption_symbols) != len(set(adoption_symbols)):
        raise ManagerScreenFullMarketAllocationV3Error(
            "legacy transition adoption symbols are duplicated"
        )
    decisions_by_symbol: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, Mapping):
            raise ManagerScreenFullMarketAllocationV3Error(
                "legacy transition decision is invalid"
            )
        symbol = _symbol(decision.get("symbol"))
        if symbol in decisions_by_symbol:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"legacy transition decision is duplicated: {symbol}"
            )
        decisions_by_symbol[symbol] = dict(decision)
    if set(decisions_by_symbol) != set(adoption_symbols):
        raise ManagerScreenFullMarketAllocationV3Error(
            "legacy transition decisions do not cover adoption members exactly"
        )

    result: dict[str, dict[str, Any]] = {}
    for position, member in ordered_members:
        symbol = member["symbol"]
        _text(decisions_by_symbol[symbol].get("route"), "legacy transition route")
        result[symbol] = {
            "scope_ordinal": ordinal_offset + position,
            "name": _text(member.get("name"), "legacy transition member name"),
            "batch_id": LEGACY_TRANSITION_ID,
            "manager_screen_result_path": result_relative,
            "manager_screen_result_sha256": result_seal.sha256,
        }
    return result


def _suspended_candidate_effective_source(
    *,
    queued: Mapping[str, Any],
    screen: Mapping[str, Any],
    member: Mapping[str, Any],
    symbol: str,
    run_id: str,
    repository_root: Path,
    suspension_relative: str,
    suspension_sha256: str,
) -> tuple[str, str, Any, dict[str, Any]]:
    """Accept the sealed suspension baseline or one sealed quote-impact evolution."""

    prior_queue = member.get("prior_queue_row")
    if not isinstance(prior_queue, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"suspended candidate member lacks its prior queue row: {symbol}"
        )
    source_path = _text(
        queued.get("manager_screen_result_path"),
        "manager_screen_result_path",
    )
    source_sha = _sha256(
        queued.get("manager_screen_result_sha256"),
        "manager_screen_result_sha256",
    )
    source, sealed = _sealed_any_source(
        _repository_path(source_path, repository_root),
        expected_sha256=source_sha,
    )
    original_path = _text(
        member.get("manager_screen_result_path"),
        "suspension manager_screen_result_path",
    )
    original_sha = _sha256(
        member.get("manager_screen_result_sha256"),
        "suspension manager_screen_result_sha256",
    )
    evolved = source_path != original_path or source_sha != original_sha
    prior_batch_id = prior_queue.get("manager_screen_batch_id")
    source_batch_id = source.get("batch_id")
    batch_id = prior_batch_id if isinstance(prior_batch_id, str) else source_batch_id
    projected_batch_id = source_batch_id if evolved else prior_batch_id
    if batch_id is not None:
        _identifier(batch_id, "suspended candidate manager_screen_batch_id")
    if (
        queued.get("manager_screen_run_id") != run_id
        or queued.get("manager_screen_batch_id") != projected_batch_id
        or queued.get("task_type") != "manager_screen"
        or queued.get("status") != "completed"
        or queued.get("assigned_agent") is not None
        or queued.get("started_at") is not None
        or queued.get("research_budget_state") != "candidate_unfunded"
        or queued.get("research_budget_suspension_path") != suspension_relative
        or queued.get("research_budget_suspension_sha256") != suspension_sha256
        or queued.get("result_path") != source_path
        or screen.get("manager_screen_run_id") != run_id
        or screen.get("manager_screen_batch_id") != projected_batch_id
        or screen.get("manager_screen_result_path") != source_path
        or screen.get("manager_screen_result_sha256") != source_sha
        or screen.get("manager_screen_route") != queued.get("manager_screen_route")
        or screen.get("decision") != "candidate_unfunded"
        or screen.get("state") != "candidate_unfunded"
        or screen.get("research_budget_state") != "candidate_unfunded"
        or screen.get("research_budget_suspension_path") != suspension_relative
        or screen.get("research_budget_suspension_sha256") != suspension_sha256
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"suspended candidate projection drifted: {symbol}"
        )
    if evolved:
        matching_reviews = [
            review
            for review in source.get("reviews") or []
            if isinstance(review, Mapping) and review.get("symbol") == symbol
        ]
        if (
            sealed.artifact_type != "manager_screen_quote_impact_result"
            or not isinstance(batch_id, str)
            or source.get("run_id") != run_id
            or source.get("batch_id") != batch_id
            or source.get("original_result_path") != original_path
            or source.get("original_result_sha256") != original_sha
            or len(matching_reviews) != 1
            or matching_reviews[0].get("action") != "replacement"
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                f"suspended candidate has no sealed quote-impact evolution: {symbol}"
            )
    decision = _source_decision(
        source,
        artifact_type=sealed.artifact_type,
        symbol=symbol,
    )
    if (
        queued.get("manager_screen_route") != decision.get("route")
        or (
            decision.get("one_line_reason") is not None
            and queued.get("reason") != decision.get("one_line_reason")
        )
        or (
            decision.get("decisive_question") is not None
            and queued.get("decisive_question") != decision.get("decisive_question")
        )
        or (
            decision.get("evidence_ids") is not None
            and list(queued.get("evidence_ids") or [])
            != list(decision.get("evidence_ids") or [])
        )
        or (
            decision.get("decisive_question") is not None
            and screen.get("decisive_question") != decision.get("decisive_question")
        )
        or (
            decision.get("one_line_reason") is not None
            and screen.get("reason") != decision.get("one_line_reason")
        )
        or (
            decision.get("evidence_ids") is not None
            and list(screen.get("evidence") or [])
            != list(decision.get("evidence_ids") or [])
        )
        or (
            decision.get("revisit_triggers") is not None
            and list(queued.get("revisit_triggers") or [])
            != list(decision.get("revisit_triggers") or [])
        )
        or (
            decision.get("revisit_triggers") is not None
            and list(screen.get("revisit_triggers") or [])
            != list(decision.get("revisit_triggers") or [])
        )
        or (
            decision.get("confidence") is not None
            and screen.get("confidence") != decision.get("confidence")
        )
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"suspended candidate decision projection drifted: {symbol}"
        )
    history = queued.get("stage_history")
    if not isinstance(history, list) or not any(
        isinstance(item, Mapping)
        and item.get("stage") == "manager_screen_allocation_v3_suspension"
        and item.get("suspension_sha256") == suspension_sha256
        for item in history
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"suspended candidate lacks its sealed suspension receipt: {symbol}"
        )
    if evolved and not any(
        isinstance(item, Mapping)
        and item.get("stage") == "manager_screen_quote_impact"
        and item.get("result_sha256") == source_sha
        for item in history
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"suspended candidate lacks its quote-impact receipt: {symbol}"
        )
    return source_path, source_sha, sealed, decision


def _calibration_material_error_contexts(
    *,
    batch_dir: Path,
    run_id: str,
    batch_id: str,
    manager_result_sha256: str,
    repository_root: Path,
) -> dict[str, dict[str, Any]]:
    calibration_root = batch_dir / "calibration"
    calibration_dirs = (
        sorted(path for path in calibration_root.iterdir() if path.is_dir())
        if calibration_root.is_dir()
        else []
    )
    if len(calibration_dirs) > 1:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"manager-screen calibration correction chain is forbidden: {batch_id}"
        )
    if not calibration_dirs:
        return {}
    result_path = calibration_dirs[0] / "result.json"
    _require_pair_or_absent(result_path, "manager-screen calibration result")
    if not result_path.exists():
        raise ManagerScreenFullMarketAllocationV3Error(
            f"manager-screen calibration is not terminal: {batch_id}"
        )
    result, sealed = _sealed_object(
        result_path,
        artifact_type="manager_screen_calibration_result",
    )
    if (
        result.get("run_id") != run_id
        or result.get("batch_id") != batch_id
        or result.get("manager_result_sha256") != manager_result_sha256
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"manager-screen calibration result binding is invalid: {batch_id}"
        )
    reviews = result.get("reviews")
    summary = result.get("summary")
    if not isinstance(reviews, list) or not isinstance(summary, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"manager-screen calibration result is invalid: {batch_id}"
        )
    material_error_symbols = {
        review.get("symbol")
        for review in reviews
        if isinstance(review, Mapping) and bool(review.get("material_errors"))
    }
    adjudicated_symbols = {
        review.get("symbol")
        for review in reviews
        if isinstance(review, Mapping)
        and isinstance(review.get("adjudication"), Mapping)
        and review["adjudication"].get("performed") is True
    }
    if (
        summary.get("material_error_symbols") != [
            review.get("symbol")
            for review in reviews
            if isinstance(review, Mapping) and bool(review.get("material_errors"))
        ]
        or summary.get("adjudicated_symbols") != [
            review.get("symbol")
            for review in reviews
            if isinstance(review, Mapping)
            and isinstance(review.get("adjudication"), Mapping)
            and review["adjudication"].get("performed") is True
        ]
        or not material_error_symbols.issubset(adjudicated_symbols)
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"manager-screen calibration adjudication is incomplete: {batch_id}"
        )
    relative = _relative(result_path, repository_root)
    contexts: dict[str, dict[str, Any]] = {}
    for review in reviews:
        if not isinstance(review, Mapping) or not review.get("material_errors"):
            continue
        symbol = _symbol(review.get("symbol"))
        adjudication = review.get("adjudication")
        if not isinstance(adjudication, Mapping) or adjudication.get("performed") is not True:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"material-error calibration lacks terminal adjudication: {symbol}"
            )
        outcome = adjudication.get("outcome")
        if outcome == "manager_upheld":
            continue
        if outcome != "material_error_confirmed":
            raise ManagerScreenFullMarketAllocationV3Error(
                f"material-error calibration outcome is not terminal: {symbol}"
            )
        context = {
            "calibration_result_path": relative,
            "calibration_result_sha256": sealed.sha256,
            "calibration_result_sealed_at": sealed.sealed_at.isoformat(),
            "review": dict(review),
            "review_sha256": _payload_sha256(review),
            "adjudication": dict(adjudication),
            "adjudication_sha256": _payload_sha256(adjudication),
        }
        _validate_calibration_material_error_context(context, symbol=symbol)
        contexts[symbol] = context
    return contexts


def _candidate_with_calibration_context(
    candidate: Mapping[str, Any],
    *,
    calibration_context: Mapping[str, Any],
) -> dict[str, Any]:
    if candidate.get("calibration_material_error") is not None:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate has duplicate calibration context: {candidate.get('symbol')}"
        )
    core = {key: value for key, value in candidate.items() if key != "candidate_sha256"}
    core["calibration_material_error"] = dict(calibration_context)
    return {**core, "candidate_sha256": _payload_sha256(core)}


def _locked_calibration_case(
    *,
    symbol: str,
    source_path: str,
    source_sha256: str,
    source_type: str,
    decision: Mapping[str, Any],
    calibration_context: Mapping[str, Any],
    classification: Mapping[str, Any],
    purchased_state: Mapping[str, Any] | None,
    inherited_purchase: Mapping[str, Any] | None,
    queued: Mapping[str, Any],
    screen: Mapping[str, Any],
    scope: Mapping[str, Mapping[str, Any]],
    prior_case: Mapping[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    scope_member = scope.get(symbol)
    if scope_member is None:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration case is outside the sealed scope: {symbol}"
        )
    if (
        classification.get("symbol") != symbol
        or classification.get("commitment_class") != "irreversible"
        or not isinstance(purchased_state, Mapping)
        or purchased_state.get("symbol") != symbol
        or not isinstance(inherited_purchase, Mapping)
        or inherited_purchase.get("symbol") != symbol
        or classification.get("queue_record_sha256")
        != purchased_state.get("queue_record_sha256")
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration case lacks its sealed commitment binding: {symbol}"
        )
    if (
        purchased_state.get("manager_screen_result_path")
        != inherited_purchase.get("source_path")
        or purchased_state.get("manager_screen_result_sha256")
        != inherited_purchase.get("source_sha256")
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration case purchase binding drifted: {symbol}"
        )
    _validate_locked_live_rows(
        symbol=symbol,
        run_id=run_id,
        batch_id=scope_member.get("batch_id"),
        source_path=source_path,
        source_sha256=source_sha256,
        route=decision.get("route"),
        queued=queued,
        screen=screen,
    )
    prepared_queue = dict(queued)
    prepared_screen = dict(screen)
    if prior_case is not None:
        _validate_locked_calibration_case(prior_case)
        prepared_queue = dict(prior_case["prepared_queue_row"])
        prepared_screen = dict(prior_case["prepared_screening_row"])

    evidence_ids = decision.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration case manager evidence is invalid: {symbol}"
        )
    core = {
        "scope_ordinal": scope_member["scope_ordinal"],
        "symbol": symbol,
        "name": scope_member["name"],
        "batch_id": scope_member.get("batch_id"),
        "effective_decision_source_path": source_path,
        "effective_decision_source_sha256": source_sha256,
        "effective_decision_source_type": source_type,
        "effective_decision_sha256": _payload_sha256(decision),
        "original_route": _text(decision.get("route"), "decision.route"),
        "original_decisive_question": _text(
            decision.get("decisive_question"),
            "decision.decisive_question",
        ),
        "original_evidence_ids": [
            _text(item, "decision.evidence_id") for item in evidence_ids
        ],
        "calibration_material_error": dict(calibration_context),
        "commitment_classification": dict(classification),
        "commitment_classification_sha256": _payload_sha256(classification),
        "activation_purchased_state": dict(purchased_state),
        "activation_purchased_state_sha256": _payload_sha256(purchased_state),
        "inherited_purchase": dict(inherited_purchase),
        "inherited_purchase_sha256": _payload_sha256(inherited_purchase),
        "prepared_queue_row": prepared_queue,
        "prepared_queue_row_sha256": _payload_sha256(prepared_queue),
        "prepared_screening_row": prepared_screen,
        "prepared_screening_row_sha256": _payload_sha256(prepared_screen),
    }
    return {**core, "locked_calibration_case_sha256": _payload_sha256(core)}


def _validate_locked_live_rows(
    *,
    symbol: str,
    run_id: str,
    batch_id: Any,
    source_path: str,
    source_sha256: str,
    route: Any,
    queued: Mapping[str, Any],
    screen: Mapping[str, Any],
) -> None:
    if (
        queued.get("symbol") != symbol
        or queued.get("manager_screen_run_id") != run_id
        or queued.get("manager_screen_batch_id") != batch_id
        or queued.get("manager_screen_route") != route
        or queued.get("manager_screen_result_path") != source_path
        or queued.get("manager_screen_result_sha256") != source_sha256
        or screen.get("symbol") != symbol
        or screen.get("manager_screen_run_id") != run_id
        or screen.get("manager_screen_batch_id") != batch_id
        or screen.get("manager_screen_route") != route
        or screen.get("manager_screen_result_path") != source_path
        or screen.get("manager_screen_result_sha256") != source_sha256
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration case lost its manager-screen binding: {symbol}"
        )


def _validate_locked_calibration_case(value: Any) -> None:
    keys = {
        "scope_ordinal",
        "symbol",
        "name",
        "batch_id",
        "effective_decision_source_path",
        "effective_decision_source_sha256",
        "effective_decision_source_type",
        "effective_decision_sha256",
        "original_route",
        "original_decisive_question",
        "original_evidence_ids",
        "calibration_material_error",
        "commitment_classification",
        "commitment_classification_sha256",
        "activation_purchased_state",
        "activation_purchased_state_sha256",
        "inherited_purchase",
        "inherited_purchase_sha256",
        "prepared_queue_row",
        "prepared_queue_row_sha256",
        "prepared_screening_row",
        "prepared_screening_row_sha256",
        "locked_calibration_case_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ManagerScreenFullMarketAllocationV3Error(
            "locked calibration case fields do not match the contract"
        )
    symbol = _symbol(value.get("symbol"))
    _positive_int(value.get("scope_ordinal"), "locked calibration scope_ordinal")
    _text(value.get("name"), "locked calibration name")
    _text(
        value.get("effective_decision_source_path"),
        "locked calibration source path",
    )
    _sha256(
        value.get("effective_decision_source_sha256"),
        "locked calibration source sha256",
    )
    if value.get("effective_decision_source_type") not in _SOURCE_TYPES:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration source type is invalid: {symbol}"
        )
    _sha256(
        value.get("effective_decision_sha256"),
        "locked calibration decision sha256",
    )
    _text(value.get("original_route"), "locked calibration original route")
    _text(
        value.get("original_decisive_question"),
        "locked calibration original decisive question",
    )
    original_evidence = value.get("original_evidence_ids")
    if not isinstance(original_evidence, list) or not original_evidence:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration original evidence is invalid: {symbol}"
        )
    for evidence_id in original_evidence:
        _text(evidence_id, "locked calibration original evidence_id")
    _validate_calibration_material_error_context(
        value.get("calibration_material_error"),
        symbol=symbol,
    )
    classification = value.get("commitment_classification")
    purchased_state = value.get("activation_purchased_state")
    inherited_purchase = value.get("inherited_purchase")
    if (
        not isinstance(classification, Mapping)
        or classification.get("symbol") != symbol
        or classification.get("commitment_class") != "irreversible"
        or value.get("commitment_classification_sha256")
        != _payload_sha256(classification)
        or not isinstance(purchased_state, Mapping)
        or purchased_state.get("symbol") != symbol
        or value.get("activation_purchased_state_sha256")
        != _payload_sha256(purchased_state)
        or not isinstance(inherited_purchase, Mapping)
        or inherited_purchase.get("symbol") != symbol
        or value.get("inherited_purchase_sha256")
        != _payload_sha256(inherited_purchase)
        or classification.get("queue_record_sha256")
        != purchased_state.get("queue_record_sha256")
        or purchased_state.get("manager_screen_result_path")
        != inherited_purchase.get("source_path")
        or purchased_state.get("manager_screen_result_sha256")
        != inherited_purchase.get("source_sha256")
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration commitment binding is invalid: {symbol}"
        )
    prepared_queue = value.get("prepared_queue_row")
    prepared_screen = value.get("prepared_screening_row")
    if (
        not isinstance(prepared_queue, Mapping)
        or prepared_queue.get("symbol") != symbol
        or value.get("prepared_queue_row_sha256") != _payload_sha256(prepared_queue)
        or not isinstance(prepared_screen, Mapping)
        or prepared_screen.get("symbol") != symbol
        or value.get("prepared_screening_row_sha256")
        != _payload_sha256(prepared_screen)
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration prepared projection binding is invalid: {symbol}"
        )
    core = {
        key: value[key]
        for key in value
        if key != "locked_calibration_case_sha256"
    }
    if value.get("locked_calibration_case_sha256") != _payload_sha256(core):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration case SHA is invalid: {symbol}"
        )


def _validate_calibration_material_error_context(
    value: Any,
    *,
    symbol: str,
) -> None:
    if not isinstance(value, Mapping) or set(value) != _CALIBRATION_CONTEXT_KEYS:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration context fields are invalid: {symbol}"
        )
    _text(
        value.get("calibration_result_path"),
        "candidate calibration result path",
    )
    _sha256(
        value.get("calibration_result_sha256"),
        "candidate calibration result sha256",
    )
    _parse_datetime(
        value.get("calibration_result_sealed_at"),
        "candidate calibration result sealed_at",
    )
    review = value.get("review")
    adjudication = value.get("adjudication")
    if not isinstance(review, Mapping) or set(review) != _CALIBRATION_REVIEW_KEYS:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration review fields are invalid: {symbol}"
        )
    if review.get("symbol") != symbol:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration review symbol mismatch: {symbol}"
        )
    material_errors = review.get("material_errors")
    if not isinstance(material_errors, list) or not material_errors:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration review lacks a material error: {symbol}"
        )
    for error in material_errors:
        if not isinstance(error, Mapping) or set(error) != _CALIBRATION_ERROR_KEYS:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"candidate calibration material-error fields are invalid: {symbol}"
            )
        _text(error.get("type"), "candidate calibration material-error type")
        _text(error.get("finding"), "candidate calibration material-error finding")
        evidence_ids = error.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"candidate calibration material-error evidence is invalid: {symbol}"
            )
        for evidence_id in evidence_ids:
            _text(evidence_id, "candidate calibration material-error evidence_id")
    review_adjudication = review.get("adjudication")
    if (
        not isinstance(adjudication, Mapping)
        or set(adjudication) != _CALIBRATION_ADJUDICATION_KEYS
        or not isinstance(review_adjudication, Mapping)
        or dict(review_adjudication) != dict(adjudication)
        or adjudication.get("performed") is not True
        or adjudication.get("outcome") != "material_error_confirmed"
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration adjudication is invalid: {symbol}"
        )
    _text(adjudication.get("finding"), "candidate calibration adjudication finding")
    adjudication_evidence = adjudication.get("evidence_ids")
    if not isinstance(adjudication_evidence, list) or not adjudication_evidence:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration adjudication evidence is invalid: {symbol}"
        )
    for evidence_id in adjudication_evidence:
        _text(evidence_id, "candidate calibration adjudication evidence_id")
    if value.get("review_sha256") != _payload_sha256(review):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration review SHA is invalid: {symbol}"
        )
    if value.get("adjudication_sha256") != _payload_sha256(adjudication):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate calibration adjudication SHA is invalid: {symbol}"
        )


def _candidate(
    *,
    symbol: str,
    origin: str,
    source_path: str,
    source_sha256: str,
    source_type: str,
    decision: Mapping[str, Any],
    queued: Mapping[str, Any],
    screen: Mapping[str, Any],
    scope: Mapping[str, Mapping[str, Any]],
    calibration_material_error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scope_member = scope.get(symbol)
    if scope_member is None:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate is outside the sealed scope: {symbol}"
        )
    if queued.get("manager_screen_batch_id") != scope_member.get("batch_id"):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate is not bound to its sealed active batch member: {symbol}"
        )
    expected_source_path = scope_member.get("manager_screen_result_path")
    expected_source_sha256 = scope_member.get("manager_screen_result_sha256")
    if expected_source_path is not None and (
        source_path != expected_source_path or source_sha256 != expected_source_sha256
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate is not bound to its sealed legacy transition result: {symbol}"
        )
    reason = decision.get("one_line_reason", queued.get("reason"))
    question = decision.get("decisive_question", queued.get("decisive_question"))
    evidence = decision.get("evidence_ids", queued.get("evidence_ids"))
    triggers = decision.get("revisit_triggers", queued.get("revisit_triggers", []))
    confidence = decision.get("confidence", screen.get("confidence"))
    risk = decision.get("risk_acknowledgements", [])
    if not isinstance(evidence, list) or not evidence:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate evidence binding is invalid: {symbol}"
        )
    if not isinstance(triggers, list) or not isinstance(risk, list):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate decision arrays are invalid: {symbol}"
        )
    core = {
        "scope_ordinal": scope_member["scope_ordinal"],
        "symbol": symbol,
        "name": scope_member["name"],
        "origin": origin,
        "effective_decision_source_path": source_path,
        "effective_decision_source_sha256": source_sha256,
        "effective_decision_source_type": source_type,
        "effective_decision_sha256": _payload_sha256(decision),
        "original_route": _text(decision.get("route"), "decision.route"),
        "one_line_reason": _text(reason, "decision.one_line_reason"),
        "decisive_question": _text(question, "decision.decisive_question"),
        "evidence_ids": [_text(item, "decision.evidence_id") for item in evidence],
        "revisit_triggers": [dict(item) for item in triggers],
        "confidence": confidence,
        "risk_acknowledgements": [dict(item) for item in risk],
        "calibration_material_error": (
            dict(calibration_material_error)
            if calibration_material_error is not None
            else None
        ),
        "prior_queue_row": dict(queued),
        "prior_queue_row_sha256": _payload_sha256(queued),
        "prior_screening_row": dict(screen),
        "prior_screening_row_sha256": _payload_sha256(screen),
    }
    return {**core, "candidate_sha256": _payload_sha256(core)}


def _verify_candidate_source(
    candidate: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    source, sealed = _sealed_any_source(
        _repository_path(candidate["effective_decision_source_path"], repository_root),
        expected_sha256=candidate["effective_decision_source_sha256"],
    )
    if sealed.artifact_type != candidate["effective_decision_source_type"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate source type drifted: {candidate['symbol']}"
        )
    decision = _source_decision(
        source,
        artifact_type=sealed.artifact_type,
        symbol=candidate["symbol"],
    )
    if _payload_sha256(decision) != candidate["effective_decision_sha256"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate effective decision drifted: {candidate['symbol']}"
        )


def _source_decision(
    payload: Mapping[str, Any],
    *,
    artifact_type: str,
    symbol: str,
) -> dict[str, Any]:
    if artifact_type == "manager_screen_quote_impact_result":
        effective = payload.get("effective_decisions")
        if isinstance(effective, list):
            rows = [
                item
                for item in effective
                if isinstance(item, Mapping) and item.get("symbol") == symbol
            ]
        else:
            rows = [
                item.get("effective_decision")
                for item in payload.get("reviews") or []
                if isinstance(item, Mapping) and item.get("symbol") == symbol
            ]
    else:
        rows = [
            item
            for item in payload.get("decisions") or []
            if isinstance(item, Mapping) and item.get("symbol") == symbol
        ]
    if len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate source does not contain exactly one decision: {symbol}"
        )
    return dict(rows[0])


def _normalize_submission(
    value: Any,
    *,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _SUBMISSION_KEYS:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation submission fields do not match the contract"
        )
    if value.get("schema_version") != 1:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation submission schema_version must be 1"
        )
    manager = _manager(value.get("manager"))
    if manager != packet["manager"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation must be recorded by the contract manager"
        )
    raw = value.get("decisions")
    if not isinstance(raw, list) or len(raw) != packet["candidate_count"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation must explicitly partition every candidate"
        )
    expected = packet["candidates"]
    normalized = []
    for candidate, decision in zip(expected, raw, strict=True):
        if not isinstance(decision, Mapping) or set(decision) != _SUBMISSION_DECISION_KEYS:
            raise ManagerScreenFullMarketAllocationV3Error(
                "full-market allocation decision fields do not match the contract"
            )
        if (
            decision.get("symbol") != candidate["symbol"]
            or decision.get("candidate_sha256") != candidate["candidate_sha256"]
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                "full-market allocation decisions must follow packet order and candidate SHA"
            )
        action = decision.get("decision")
        if action not in {FUND_DECISION, DEFER_DECISION}:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"invalid full-market allocation decision: {action}"
            )
        triggers = _normalize_triggers(
            decision.get("revisit_triggers"),
            symbol=candidate["symbol"],
        )
        if action == DEFER_DECISION and not triggers:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"defer_full_market requires revisit triggers: {candidate['symbol']}"
            )
        normalized.append(
            {
                "symbol": candidate["symbol"],
                "candidate_sha256": candidate["candidate_sha256"],
                "decision": action,
                "reason": _text(decision.get("reason"), "decision.reason"),
                **_normalize_allocation_research_brief(
                    decision,
                    candidate=candidate,
                ),
                "revisit_triggers": triggers,
            }
        )
    remediations = _normalize_locked_calibration_remediations(
        value.get("locked_calibration_remediations"),
        packet=packet,
    )
    return {
        "manager": manager,
        "decisions": normalized,
        "locked_calibration_remediations": remediations,
    }


def _normalize_locked_calibration_remediations(
    value: Any,
    *,
    packet: Mapping[str, Any],
) -> list[dict[str, Any]]:
    cases = packet["locked_calibration_cases"]
    if not isinstance(value, list) or len(value) != len(cases):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation must explicitly remediate every locked calibration case"
        )
    normalized = []
    for case, decision in zip(cases, value, strict=True):
        symbol = case["symbol"]
        if not isinstance(decision, Mapping) or set(decision) != _LOCKED_REMEDIATION_KEYS:
            raise ManagerScreenFullMarketAllocationV3Error(
                "locked calibration remediation fields do not match the contract"
            )
        if (
            decision.get("symbol") != symbol
            or decision.get("locked_calibration_case_sha256")
            != case["locked_calibration_case_sha256"]
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                "locked calibration remediations must follow packet order and case SHA"
            )
        action = decision.get("remediation")
        if action not in LOCKED_REMEDIATIONS:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"invalid locked calibration remediation: {action}"
            )
        raw_question = decision.get("decisive_question")
        raw_evidence = decision.get("evidence_ids")
        resolved_work_sha256 = decision.get("resolved_work_sha256")
        triggers = _normalize_triggers(
            decision.get("revisit_triggers"),
            symbol=symbol,
        )
        if action == RESOLVED_REMEDIATION:
            sealed_progress = case["commitment_classification"].get("sealed_progress")
            if not isinstance(sealed_progress, list) or not sealed_progress:
                raise ManagerScreenFullMarketAllocationV3Error(
                    "resolved_by_existing_sealed_work requires sealed formal progress: "
                    f"{symbol}"
                )
            chosen_work = [
                item
                for item in sealed_progress
                if isinstance(item, Mapping)
                and item.get("sha256") == resolved_work_sha256
            ]
            if len(chosen_work) != 1:
                raise ManagerScreenFullMarketAllocationV3Error(
                    "resolved_by_existing_sealed_work must bind one sealed work artifact: "
                    f"{symbol}"
                )
            work_sealed_at = _parse_datetime(
                chosen_work[0].get("sealed_at"),
                f"{symbol}.resolved_work.sealed_at",
            )
            calibration_sealed_at = _parse_datetime(
                case["calibration_material_error"].get(
                    "calibration_result_sealed_at"
                ),
                f"{symbol}.calibration_result_sealed_at",
            )
            if work_sealed_at < calibration_sealed_at:
                raise ManagerScreenFullMarketAllocationV3Error(
                    "resolved work must postdate the confirmed calibration error: "
                    f"{symbol}"
                )
            if raw_question is not None or triggers:
                raise ManagerScreenFullMarketAllocationV3Error(
                    "resolved_by_existing_sealed_work cannot create a new research brief: "
                    f"{symbol}"
                )
            question = None
            evidence_ids = _normalize_locked_calibration_evidence(
                raw_evidence,
                case=case,
            )
        else:
            if resolved_work_sha256 is not None:
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"{action} cannot bind resolved work: {symbol}"
                )
            question = _text(
                raw_question,
                f"{symbol}.locked_calibration.decisive_question",
            )
            if question.strip() == case["original_decisive_question"].strip():
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"{symbol}.locked calibration error requires a revised decisive question"
                )
            evidence_ids = _normalize_locked_calibration_evidence(
                raw_evidence,
                case=case,
            )
            if action == TARGETED_REMEDIATION:
                prepared_queue = case["prepared_queue_row"]
                prepared_screen = case["prepared_screening_row"]
                if (
                    prepared_queue.get("task_type")
                    not in {"quick_profile", "scoped_research"}
                    or prepared_queue.get("status") != "completed"
                    or prepared_screen.get("decision")
                    != "targeted_followup_candidate"
                    or not isinstance(prepared_queue.get("profile_cycle_id"), str)
                    or not prepared_queue.get("profile_cycle_id")
                ):
                    raise ManagerScreenFullMarketAllocationV3Error(
                        "targeted_remediation_candidate must already be consumable by "
                        f"explicit targeted-followup approval: {symbol}"
                    )
            if action == DEFER_REMEDIATION and not triggers:
                raise ManagerScreenFullMarketAllocationV3Error(
                    f"defer_remediation requires revisit triggers: {symbol}"
                )
            if action == TARGETED_REMEDIATION and triggers:
                raise ManagerScreenFullMarketAllocationV3Error(
                    "targeted_remediation_candidate does not accept defer triggers: "
                    f"{symbol}"
                )
        normalized.append(
            {
                "symbol": symbol,
                "locked_calibration_case_sha256": case[
                    "locked_calibration_case_sha256"
                ],
                "remediation": action,
                "reason": _text(
                    decision.get("reason"),
                    f"{symbol}.locked_calibration.reason",
                ),
                "resolved_work_sha256": resolved_work_sha256,
                "decisive_question": question,
                "evidence_ids": evidence_ids,
                "revisit_triggers": triggers,
            }
        )
    return normalized


def _normalize_locked_calibration_evidence(
    value: Any,
    *,
    case: Mapping[str, Any],
) -> list[str]:
    symbol = case["symbol"]
    if not isinstance(value, list) or not value:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.locked calibration evidence_ids must be a non-empty array"
        )
    evidence_ids = [
        _text(item, f"{symbol}.locked calibration evidence_id") for item in value
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.locked calibration evidence_ids contains duplicates"
        )
    allowed = set(case["original_evidence_ids"])
    required: set[str] = set()
    calibration = case["calibration_material_error"]
    for error in calibration["review"]["material_errors"]:
        required.update(error["evidence_ids"])
    required.update(calibration["adjudication"]["evidence_ids"])
    allowed.update(required)
    unknown = set(evidence_ids) - allowed
    if unknown:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.locked calibration evidence is outside sealed context: "
            f"{sorted(unknown)}"
        )
    if not required.issubset(evidence_ids):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.locked remediation omits confirmed calibration-error evidence"
        )
    return evidence_ids


def _normalize_allocation_research_brief(
    value: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    symbol = str(candidate.get("symbol"))
    question = _text(
        value.get("decisive_question"),
        f"{symbol}.decisive_question",
    )
    raw_evidence = value.get("evidence_ids")
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.evidence_ids must be a non-empty array"
        )
    evidence_ids = [
        _text(item, f"{symbol}.evidence_id") for item in raw_evidence
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.evidence_ids contains duplicates"
        )
    allowed = set(candidate.get("evidence_ids") or [])
    required_calibration: set[str] = set()
    calibration = candidate.get("calibration_material_error")
    if isinstance(calibration, Mapping):
        if question.strip() == str(candidate.get("decisive_question", "")).strip():
            raise ManagerScreenFullMarketAllocationV3Error(
                f"{symbol}.confirmed calibration error requires a revised decisive question"
            )
        review = calibration.get("review")
        adjudication = calibration.get("adjudication")
        if isinstance(review, Mapping):
            for error in review.get("material_errors") or []:
                if isinstance(error, Mapping):
                    required_calibration.update(error.get("evidence_ids") or [])
        if isinstance(adjudication, Mapping):
            required_calibration.update(adjudication.get("evidence_ids") or [])
        allowed.update(required_calibration)
    unknown = set(evidence_ids) - allowed
    if unknown:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.evidence_ids are outside the sealed candidate context: {sorted(unknown)}"
        )
    if not required_calibration.issubset(evidence_ids):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.research brief omits confirmed calibration-error evidence"
        )
    return {
        "decisive_question": question,
        "evidence_ids": evidence_ids,
    }


def _materialize(
    *,
    base: Path,
    repository_root: Path,
    packet: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: Path,
    result_sha256: str,
) -> dict[str, Any]:
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = _unique_rows(queue_path, "research queue")
    screening = _unique_rows(screening_path, "screening")
    relative = _relative(result_path, repository_root)
    decisions = {item["symbol"]: item for item in result["decisions"]}
    remediations = {
        item["symbol"]: item
        for item in result["locked_calibration_remediations"]
    }
    queue_updates: dict[str, dict[str, Any]] = {}
    screen_updates: dict[str, dict[str, Any]] = {}
    errors = []
    for candidate in packet["candidates"]:
        symbol = candidate["symbol"]
        decision = decisions[symbol]
        expected_queue = _projected_queue_row(
            candidate,
            decision=decision,
            result=result,
            result_path=relative,
            result_sha256=result_sha256,
            policy=packet["policy"],
        )
        expected_screen = _projected_screening_row(
            candidate,
            decision=decision,
            result=result,
            result_path=relative,
            result_sha256=result_sha256,
        )
        try:
            queue_state = _projection_row_state(
                queue.get(symbol),
                prior=candidate["prior_queue_row"],
                prior_sha256=candidate["prior_queue_row_sha256"],
                expected=expected_queue,
                label="research queue",
                symbol=symbol,
            )
            screen_state = _projection_row_state(
                screening.get(symbol),
                prior=candidate["prior_screening_row"],
                prior_sha256=candidate["prior_screening_row_sha256"],
                expected=expected_screen,
                label="screening",
                symbol=symbol,
            )
            if queue_state == "prior":
                queue_updates[symbol] = expected_queue
            if screen_state == "prior":
                screen_updates[symbol] = expected_screen
        except ManagerScreenFullMarketAllocationV3Error as exc:
            errors.append(f"{symbol}: {exc}")
    for case in packet["locked_calibration_cases"]:
        symbol = case["symbol"]
        try:
            current_queue = queue.get(symbol)
            current_screen = screening.get(symbol)
            if current_queue is None or current_screen is None:
                raise ManagerScreenFullMarketAllocationV3Error(
                    "locked remediation projection row is missing"
                )
            _validate_locked_live_rows(
                symbol=symbol,
                run_id=result["run_id"],
                batch_id=case["batch_id"],
                source_path=case["effective_decision_source_path"],
                source_sha256=case["effective_decision_source_sha256"],
                route=case["original_route"],
                queued=current_queue,
                screen=current_screen,
            )
            binding = _locked_remediation_binding(
                case,
                remediation=remediations[symbol],
                result=result,
                result_path=relative,
                result_sha256=result_sha256,
            )
            projected_queue, queue_changed = _project_locked_remediation_queue(
                current_queue,
                binding=binding,
                symbol=symbol,
            )
            projected_screen, screen_changed = _project_locked_remediation_screen(
                current_screen,
                binding=binding,
                symbol=symbol,
            )
            if queue_changed:
                queue_updates[symbol] = projected_queue
            if screen_changed:
                screen_updates[symbol] = projected_screen
        except ManagerScreenFullMarketAllocationV3Error as exc:
            errors.append(f"{symbol}: {exc}")
    if errors:
        raise ManagerScreenFullMarketAllocationV3Error(
            "sealed full-market allocation projection drifted; refusing all writes: "
            + "; ".join(errors)
        )
    if queue_updates:
        queue.update(queue_updates)
        write_jsonl(queue_path, list(queue.values()))
    if screen_updates:
        screening.update(screen_updates)
        write_jsonl(screening_path, list(screening.values()))
    return {
        "queue_materialized_count": len(packet["candidates"]),
        "screening_materialized_count": len(packet["candidates"]),
        "queue_repaired_count": len(queue_updates),
        "screening_repaired_count": len(screen_updates),
        "locked_remediation_queue_materialized_count": len(
            packet["locked_calibration_cases"]
        ),
        "locked_remediation_screening_materialized_count": len(
            packet["locked_calibration_cases"]
        ),
        "fully_materialized": True,
        "drift": [],
    }


def _projection_status(
    *,
    base: Path,
    repository_root: Path,
    packet: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: Path,
    result_sha256: str,
) -> dict[str, Any]:
    queue = _unique_rows(base / RESEARCH_QUEUE_FILE, "research queue")
    screening = _unique_rows(base / SCREENING_FILE, "screening")
    relative = _relative(result_path, repository_root)
    decisions = {item["symbol"]: item for item in result["decisions"]}
    remediations = {
        item["symbol"]: item
        for item in result["locked_calibration_remediations"]
    }
    queue_count = 0
    screen_count = 0
    drift = []
    for candidate in packet["candidates"]:
        symbol = candidate["symbol"]
        decision = decisions[symbol]
        expected_queue = _projected_queue_row(
            candidate,
            decision=decision,
            result=result,
            result_path=relative,
            result_sha256=result_sha256,
            policy=packet["policy"],
        )
        expected_screen = _projected_screening_row(
            candidate,
            decision=decision,
            result=result,
            result_path=relative,
            result_sha256=result_sha256,
        )
        if queue.get(symbol) == expected_queue:
            queue_count += 1
        else:
            drift.append({"symbol": symbol, "projection": "research_queue"})
        if screening.get(symbol) == expected_screen:
            screen_count += 1
        else:
            drift.append({"symbol": symbol, "projection": "screening"})
    locked_queue_count = 0
    locked_screen_count = 0
    for case in packet["locked_calibration_cases"]:
        symbol = case["symbol"]
        binding = _locked_remediation_binding(
            case,
            remediation=remediations[symbol],
            result=result,
            result_path=relative,
            result_sha256=result_sha256,
        )
        current_queue = queue.get(symbol)
        current_screen = screening.get(symbol)
        if _locked_queue_projection_is_materialized(current_queue, binding=binding):
            locked_queue_count += 1
        else:
            drift.append({"symbol": symbol, "projection": "locked_research_queue"})
        if _locked_screen_projection_is_materialized(current_screen, binding=binding):
            locked_screen_count += 1
        else:
            drift.append({"symbol": symbol, "projection": "locked_screening"})
    return {
        "queue_materialized_count": queue_count,
        "screening_materialized_count": screen_count,
        "queue_repaired_count": 0,
        "screening_repaired_count": 0,
        "locked_remediation_queue_materialized_count": locked_queue_count,
        "locked_remediation_screening_materialized_count": locked_screen_count,
        "fully_materialized": not drift,
        "drift": drift,
    }


def _locked_remediation_binding(
    case: Mapping[str, Any],
    *,
    remediation: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: str,
    result_sha256: str,
) -> dict[str, Any]:
    calibration = case["calibration_material_error"]
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "run_id": result["run_id"],
        "recorded_at": result["recorded_at"],
        "allocation_result_path": result_path,
        "allocation_result_sha256": result_sha256,
        "locked_calibration_case_sha256": case[
            "locked_calibration_case_sha256"
        ],
        "remediation": remediation["remediation"],
        "reason": remediation["reason"],
        "resolved_work_sha256": remediation["resolved_work_sha256"],
        "decisive_question": remediation["decisive_question"],
        "evidence_ids": list(remediation["evidence_ids"]),
        "revisit_triggers": list(remediation["revisit_triggers"]),
        "calibration_result_path": calibration["calibration_result_path"],
        "calibration_result_sha256": calibration["calibration_result_sha256"],
        "calibration_result_sealed_at": calibration[
            "calibration_result_sealed_at"
        ],
        "calibration_review_sha256": calibration["review_sha256"],
        "calibration_adjudication_sha256": calibration[
            "adjudication_sha256"
        ],
    }


def _locked_remediation_history_event(binding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": "manager_screen_locked_calibration_remediation",
        "status": "completed",
        "action": binding["remediation"],
        "finished_at": binding["recorded_at"],
        "run_id": binding["run_id"],
        "result_path": binding["allocation_result_path"],
        "result_sha256": binding["allocation_result_sha256"],
        "locked_calibration_case_sha256": binding[
            "locked_calibration_case_sha256"
        ],
    }


def _project_locked_remediation_queue(
    current: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    symbol: str,
) -> tuple[dict[str, Any], bool]:
    updated = dict(current)
    existing = updated.get(_LOCKED_REMEDIATION_FIELD)
    if existing is not None and existing != binding:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration remediation binding conflicts: {symbol}"
        )
    changed = existing is None
    updated[_LOCKED_REMEDIATION_FIELD] = dict(binding)
    history = updated.get("stage_history")
    if history is None:
        history = []
    if not isinstance(history, list):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration remediation stage history is invalid: {symbol}"
        )
    event = _locked_remediation_history_event(binding)
    conflicting = [
        item
        for item in history
        if isinstance(item, Mapping)
        and item.get("stage") == event["stage"]
        and item.get("result_sha256") == event["result_sha256"]
        and dict(item) != event
    ]
    if conflicting:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration remediation receipt conflicts: {symbol}"
        )
    if event not in history:
        history = [*history, event]
        changed = True
    updated["stage_history"] = history
    return updated, changed


def _project_locked_remediation_screen(
    current: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    symbol: str,
) -> tuple[dict[str, Any], bool]:
    updated = dict(current)
    existing = updated.get(_LOCKED_REMEDIATION_FIELD)
    if existing is not None and existing != binding:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"locked calibration screening binding conflicts: {symbol}"
        )
    changed = existing is None
    updated[_LOCKED_REMEDIATION_FIELD] = dict(binding)
    return updated, changed


def _locked_queue_projection_is_materialized(
    current: Mapping[str, Any] | None,
    *,
    binding: Mapping[str, Any],
) -> bool:
    if not isinstance(current, Mapping) or current.get(_LOCKED_REMEDIATION_FIELD) != binding:
        return False
    history = current.get("stage_history")
    return isinstance(history, list) and _locked_remediation_history_event(binding) in history


def _locked_screen_projection_is_materialized(
    current: Mapping[str, Any] | None,
    *,
    binding: Mapping[str, Any],
) -> bool:
    return bool(
        isinstance(current, Mapping)
        and current.get(_LOCKED_REMEDIATION_FIELD) == binding
    )


def _projected_queue_row(
    candidate: Mapping[str, Any],
    *,
    decision: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: str,
    result_sha256: str,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    updated = dict(candidate["prior_queue_row"])
    history = list(updated.get("stage_history") or [])
    event = {
        "stage": PRECEDING_STAGE,
        "status": "completed",
        "action": decision["decision"],
        "finished_at": result["recorded_at"],
        "run_id": result["run_id"],
        "result_path": result_path,
        "result_sha256": result_sha256,
        "candidate_sha256": candidate["candidate_sha256"],
        "profile_cycle_id": result["profile_cycle_id"],
    }
    if not any(
        isinstance(item, Mapping)
        and item.get("stage") == PRECEDING_STAGE
        and item.get("result_sha256") == result_sha256
        for item in history
    ):
        history.append(event)
    updated.update(
        {
            "reason": decision["reason"],
            "decisive_question": decision["decisive_question"],
            "evidence_ids": list(decision["evidence_ids"]),
            "assigned_agent": None,
            "started_at": None,
            "failure_reason": None,
            "revisit_triggers": list(decision["revisit_triggers"]),
            "stage_history": history,
            "manager_screen_allocation_result_path": result_path,
            "manager_screen_allocation_result_sha256": result_sha256,
            "manager_screen_allocation_candidate_sha256": candidate["candidate_sha256"],
            "manager_screen_allocation_decision": decision["decision"],
        }
    )
    _project_calibration_binding(updated, candidate=candidate)
    if decision["decision"] == FUND_DECISION:
        updated.update(
            {
                "task_type": "quick_profile",
                "status": "pending",
                "finished_at": None,
                "result_path": None,
                "next_action": (
                    "由一名研究员回答原 manager-screen 决定性问题；"
                    "后续预算仍需投资经理显式批准。"
                ),
                "research_budget_state": FUNDED_STATE,
                "effort_budget_hours": policy["quick_profile_effort_budget_hours"],
                "preceding_stage": PRECEDING_STAGE,
                "stop_conditions": list(policy["quick_profile_stop_conditions"]),
                "profile_cycle_id": result["profile_cycle_id"],
                "allocation_sha256": result_sha256,
            }
        )
        for stale in _PROFILE_FIELDS:
            updated.pop(stale, None)
    else:
        updated.update(
            {
                "task_type": "manager_screen",
                "status": "completed",
                "finished_at": result["recorded_at"],
                "result_path": candidate["effective_decision_source_path"],
                "next_action": "等待封存的可执行重启条件命中；本轮未使用的研究槽位永久放弃。",
                "research_budget_state": DEFERRED_STATE,
            }
        )
        for stale in _PURCHASE_FIELDS | _PROFILE_FIELDS | {"profile_cycle_id", "allocation_sha256"}:
            updated.pop(stale, None)
    return updated


def _projected_screening_row(
    candidate: Mapping[str, Any],
    *,
    decision: Mapping[str, Any],
    result: Mapping[str, Any],
    result_path: str,
    result_sha256: str,
) -> dict[str, Any]:
    updated = dict(candidate["prior_screening_row"])
    state = "quick_profile" if decision["decision"] == FUND_DECISION else DEFERRED_STATE
    updated.update(
        {
            "decision": state,
            "state": state,
            "reason": decision["reason"],
            "decisive_question": decision["decisive_question"],
            "evidence": list(decision["evidence_ids"]),
            "next_action": (
                "由一名研究员回答原 manager-screen 决定性问题。"
                if decision["decision"] == FUND_DECISION
                else "等待封存的可执行重启条件命中；本轮未使用的研究槽位永久放弃。"
            ),
            "revisit_triggers": list(decision["revisit_triggers"]),
            "research_budget_state": (
                FUNDED_STATE if decision["decision"] == FUND_DECISION else DEFERRED_STATE
            ),
            "manager_screen_allocation_result_path": result_path,
            "manager_screen_allocation_result_sha256": result_sha256,
            "manager_screen_allocation_candidate_sha256": candidate["candidate_sha256"],
            "manager_screen_allocation_decision": decision["decision"],
        }
    )
    _project_calibration_binding(updated, candidate=candidate)
    if decision["decision"] == FUND_DECISION:
        updated["profile_cycle_id"] = result["profile_cycle_id"]
    else:
        updated.pop("profile_cycle_id", None)
    return updated


def _project_calibration_binding(
    target: dict[str, Any],
    *,
    candidate: Mapping[str, Any],
) -> None:
    calibration = candidate.get("calibration_material_error")
    if not isinstance(calibration, Mapping):
        for field in _CALIBRATION_PROJECTION_FIELDS:
            target.pop(field, None)
        return
    target.update(
        {
            "manager_screen_calibration_result_path": calibration[
                "calibration_result_path"
            ],
            "manager_screen_calibration_result_sha256": calibration[
                "calibration_result_sha256"
            ],
            "manager_screen_calibration_review_sha256": calibration[
                "review_sha256"
            ],
            "manager_screen_calibration_adjudication_sha256": calibration[
                "adjudication_sha256"
            ],
        }
    )


def _projection_row_state(
    current: Mapping[str, Any] | None,
    *,
    prior: Mapping[str, Any],
    prior_sha256: str,
    expected: Mapping[str, Any],
    label: str,
    symbol: str,
) -> str:
    if current is None:
        raise ManagerScreenFullMarketAllocationV3Error(f"{label} row is missing: {symbol}")
    if dict(current) == dict(expected):
        return "materialized"
    if dict(current) == dict(prior) and _payload_sha256(current) == prior_sha256:
        return "prior"
    raise ManagerScreenFullMarketAllocationV3Error(
        f"{label} row matches neither sealed prior nor allocation projection"
    )


def _validate_packet_payload(value: Any) -> None:
    required = {
        "schema_version",
        "workflow",
        "workflow_version",
        "run_id",
        "prepared_at",
        "contract_path",
        "contract_sha256",
        "suspension_path",
        "suspension_sha256",
        "scope",
        "quote",
        "manager",
        "policy",
        "capacity",
        "full_scope_state",
        "instructions",
        "candidates",
        "candidate_count",
        "candidates_sha256",
        "locked_calibration_cases",
        "locked_calibration_case_count",
        "locked_calibration_cases_sha256",
        "terminal_governance_manifest",
        "terminal_governance_manifest_count",
        "terminal_governance_manifest_sha256",
        "portfolio_action",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet fields do not match the contract"
        )
    if (
        value.get("schema_version") != 1
        or value.get("workflow") != WORKFLOW
        or value.get("workflow_version") != WORKFLOW_VERSION
        or value.get("portfolio_action") is not None
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation packet constants are invalid"
        )
    _identifier(value.get("run_id"), "run_id")
    _parse_datetime(value.get("prepared_at"), "prepared_at")
    _text(value.get("contract_path"), "contract_path")
    _sha256(value.get("contract_sha256"), "contract_sha256")
    _text(value.get("suspension_path"), "suspension_path")
    _sha256(value.get("suspension_sha256"), "suspension_sha256")
    _manager(value.get("manager"))
    candidates = value.get("candidates")
    if not isinstance(candidates, list):
        raise ManagerScreenFullMarketAllocationV3Error("packet candidates must be an array")
    order_keys = []
    symbols = []
    for candidate in candidates:
        _validate_candidate(candidate)
        order_keys.append((candidate["scope_ordinal"], candidate["symbol"]))
        symbols.append(candidate["symbol"])
    if order_keys != sorted(order_keys):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet candidates must be sorted by sealed batch scope ordinal and symbol"
        )
    if len(symbols) != len(set(symbols)):
        raise ManagerScreenFullMarketAllocationV3Error("packet candidate symbols are duplicated")
    if value.get("candidate_count") != len(candidates):
        raise ManagerScreenFullMarketAllocationV3Error("packet candidate_count is invalid")
    if value.get("candidates_sha256") != _payload_sha256(candidates):
        raise ManagerScreenFullMarketAllocationV3Error("packet candidates_sha256 is invalid")
    locked_cases = value.get("locked_calibration_cases")
    if not isinstance(locked_cases, list):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet locked_calibration_cases must be an array"
        )
    locked_order = []
    locked_symbols = []
    for case in locked_cases:
        _validate_locked_calibration_case(case)
        locked_order.append((case["scope_ordinal"], case["symbol"]))
        locked_symbols.append(case["symbol"])
    if locked_order != sorted(locked_order):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet locked calibration cases must follow scope order"
        )
    if len(locked_symbols) != len(set(locked_symbols)):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet locked calibration symbols are duplicated"
        )
    if set(locked_symbols) & set(symbols):
        raise ManagerScreenFullMarketAllocationV3Error(
            "locked calibration cases cannot consume candidate selection capacity"
        )
    if value.get("locked_calibration_case_count") != len(locked_cases):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet locked_calibration_case_count is invalid"
        )
    if value.get("locked_calibration_cases_sha256") != _payload_sha256(locked_cases):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet locked_calibration_cases_sha256 is invalid"
        )
    terminal_manifest = value.get("terminal_governance_manifest")
    _validate_terminal_governance_manifest(terminal_manifest)
    if value.get("terminal_governance_manifest_count") != len(terminal_manifest):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet terminal_governance_manifest_count is invalid"
        )
    if value.get("terminal_governance_manifest_sha256") != _payload_sha256(
        terminal_manifest
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet terminal_governance_manifest_sha256 is invalid"
        )


def _validate_candidate(value: Any) -> None:
    keys = {
        "scope_ordinal",
        "symbol",
        "name",
        "origin",
        "effective_decision_source_path",
        "effective_decision_source_sha256",
        "effective_decision_source_type",
        "effective_decision_sha256",
        "original_route",
        "one_line_reason",
        "decisive_question",
        "evidence_ids",
        "revisit_triggers",
        "confidence",
        "risk_acknowledgements",
        "calibration_material_error",
        "prior_queue_row",
        "prior_queue_row_sha256",
        "prior_screening_row",
        "prior_screening_row_sha256",
        "candidate_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market candidate fields do not match the contract"
        )
    _positive_int(value.get("scope_ordinal"), "scope_ordinal")
    _symbol(value.get("symbol"))
    _text(value.get("name"), "candidate.name")
    if value.get("origin") not in {
        "suspended_v2",
        "v3_research_candidate",
        "calibration_material_error",
    }:
        raise ManagerScreenFullMarketAllocationV3Error("candidate origin is invalid")
    _text(value.get("effective_decision_source_path"), "candidate source path")
    _sha256(value.get("effective_decision_source_sha256"), "candidate source sha256")
    if value.get("effective_decision_source_type") not in _SOURCE_TYPES:
        raise ManagerScreenFullMarketAllocationV3Error("candidate source type is invalid")
    _sha256(value.get("effective_decision_sha256"), "candidate decision sha256")
    _text(value.get("original_route"), "candidate original route")
    _text(value.get("one_line_reason"), "candidate reason")
    _text(value.get("decisive_question"), "candidate question")
    if not isinstance(value.get("evidence_ids"), list) or not value["evidence_ids"]:
        raise ManagerScreenFullMarketAllocationV3Error("candidate evidence_ids are invalid")
    if not isinstance(value.get("revisit_triggers"), list) or not isinstance(
        value.get("risk_acknowledgements"), list
    ):
        raise ManagerScreenFullMarketAllocationV3Error("candidate decision arrays are invalid")
    calibration = value.get("calibration_material_error")
    if calibration is not None:
        _validate_calibration_material_error_context(
            calibration,
            symbol=value["symbol"],
        )
    queue = value.get("prior_queue_row")
    screen = value.get("prior_screening_row")
    if not isinstance(queue, Mapping) or not isinstance(screen, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error("candidate prior rows are invalid")
    if queue.get("symbol") != value["symbol"] or screen.get("symbol") != value["symbol"]:
        raise ManagerScreenFullMarketAllocationV3Error("candidate prior row symbol mismatch")
    if value.get("prior_queue_row_sha256") != _payload_sha256(queue):
        raise ManagerScreenFullMarketAllocationV3Error("candidate prior queue SHA is invalid")
    if value.get("prior_screening_row_sha256") != _payload_sha256(screen):
        raise ManagerScreenFullMarketAllocationV3Error("candidate prior screening SHA is invalid")
    core = {key: value[key] for key in value if key != "candidate_sha256"}
    if value.get("candidate_sha256") != _payload_sha256(core):
        raise ManagerScreenFullMarketAllocationV3Error("candidate SHA is invalid")


def _validate_result_payload(value: Any, *, packet: Mapping[str, Any]) -> None:
    keys = {
        "schema_version",
        "workflow",
        "workflow_version",
        "run_id",
        "recorded_at",
        "packet_path",
        "packet_sha256",
        "contract_path",
        "contract_sha256",
        "suspension_path",
        "suspension_sha256",
        "manager",
        "profile_cycle_id",
        "granted_stage",
        "purchase_effort_budget_hours",
        "decisions",
        "locked_calibration_remediations",
        "summary",
        "portfolio_action",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result fields do not match the contract"
        )
    if (
        value.get("schema_version") != 1
        or value.get("workflow") != WORKFLOW
        or value.get("workflow_version") != WORKFLOW_VERSION
        or value.get("granted_stage") != GRANTED_STAGE
        or value.get("portfolio_action") is not None
        or value.get("contract_path") != packet["contract_path"]
        or value.get("contract_sha256") != packet["contract_sha256"]
        or value.get("suspension_path") != packet["suspension_path"]
        or value.get("suspension_sha256") != packet["suspension_sha256"]
        or value.get("manager") != packet["manager"]
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result constants or bindings are invalid"
        )
    _identifier(value.get("run_id"), "result.run_id")
    recorded_at = _parse_datetime(value.get("recorded_at"), "result.recorded_at")
    if recorded_at <= _parse_datetime(packet["prepared_at"], "packet.prepared_at"):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result is not strictly later than its packet"
        )
    _require_quote_fresh_at(packet["quote"], recorded_at)
    profile_cycle_id = _identifier(value.get("profile_cycle_id"), "result.profile_cycle_id")
    if profile_cycle_id != f"{packet['run_id']}-full-market-v3":
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result profile cycle is not canonical"
        )
    _positive_hours(value.get("purchase_effort_budget_hours"), "purchase effort")
    decisions = value.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != packet["candidate_count"]:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result does not partition the packet"
        )
    for candidate, decision in zip(packet["candidates"], decisions, strict=True):
        if (
            not isinstance(decision, Mapping)
            or set(decision) != _SUBMISSION_DECISION_KEYS
            or decision.get("symbol") != candidate["symbol"]
            or decision.get("candidate_sha256") != candidate["candidate_sha256"]
            or decision.get("decision") not in {FUND_DECISION, DEFER_DECISION}
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                "full-market allocation result decision is invalid"
            )
        _text(decision.get("reason"), "result decision reason")
        normalized_brief = _normalize_allocation_research_brief(
            decision,
            candidate=candidate,
        )
        if any(decision.get(key) != value for key, value in normalized_brief.items()):
            raise ManagerScreenFullMarketAllocationV3Error(
                "full-market allocation result research brief is not canonical"
            )
        normalized_triggers = _normalize_triggers(
            decision.get("revisit_triggers"),
            symbol=candidate["symbol"],
        )
        if decision["revisit_triggers"] != normalized_triggers:
            raise ManagerScreenFullMarketAllocationV3Error(
                "full-market allocation result triggers are not canonical"
            )
        if decision["decision"] == DEFER_DECISION and not normalized_triggers:
            raise ManagerScreenFullMarketAllocationV3Error(
                "deferred result decision lacks revisit triggers"
            )
    locked_remediations = _normalize_locked_calibration_remediations(
        value.get("locked_calibration_remediations"),
        packet=packet,
    )
    if value.get("locked_calibration_remediations") != locked_remediations:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market locked calibration remediations are not canonical"
        )
    summary = value.get("summary")
    if not isinstance(summary, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error("result summary is invalid")
    selected = sum(item["decision"] == FUND_DECISION for item in decisions)
    deferred = len(decisions) - selected
    capacity = packet["capacity"]
    effort = float(value["purchase_effort_budget_hours"])
    locked = int(capacity["locked_company_count"])
    locked_hours = float(capacity["locked_effort_budget_hours"])
    policy_effort = float(packet["policy"]["quick_profile_effort_budget_hours"])
    if (
        not math.isclose(effort, policy_effort, rel_tol=0, abs_tol=1e-9)
        or not math.isclose(
            effort,
            float(capacity["purchase_effort_budget_hours"]),
            rel_tol=0,
            abs_tol=1e-9,
        )
        or capacity["absolute_funded_company_limit"]
        != ABSOLUTE_FUNDED_COMPANY_LIMIT
        or not math.isclose(
            float(capacity["absolute_funded_effort_budget_hours"]),
            ABSOLUTE_FUNDED_EFFORT_HOURS,
            rel_tol=0,
            abs_tol=1e-9,
        )
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result effort or hard capacity is invalid"
        )
    expected = {
        "candidate_count": len(decisions),
        "locked_calibration_case_count": len(locked_remediations),
        "locked_calibration_resolved_count": sum(
            item["remediation"] == RESOLVED_REMEDIATION
            for item in locked_remediations
        ),
        "locked_calibration_targeted_candidate_count": sum(
            item["remediation"] == TARGETED_REMEDIATION
            for item in locked_remediations
        ),
        "locked_calibration_deferred_count": sum(
            item["remediation"] == DEFER_REMEDIATION
            for item in locked_remediations
        ),
        "locked_company_count": locked,
        "locked_effort_budget_hours": locked_hours,
        "selected_company_count": selected,
        "selected_effort_budget_hours": selected * effort,
        "deferred_company_count": deferred,
        "unused_company_capacity": capacity["selection_capacity"] - selected,
        "unused_effort_budget_hours": (capacity["selection_capacity"] - selected) * effort,
        "effective_funded_company_count": locked + selected,
        "effective_funded_effort_budget_hours": locked_hours + selected * effort,
        "absolute_funded_company_limit": capacity["absolute_funded_company_limit"],
        "absolute_funded_effort_budget_hours": capacity[
            "absolute_funded_effort_budget_hours"
        ],
    }
    if (
        dict(summary) != expected
        or selected > capacity["selection_capacity"]
        or locked + selected > ABSOLUTE_FUNDED_COMPANY_LIMIT
        or locked_hours + selected * effort > ABSOLUTE_FUNDED_EFFORT_HOURS + 1e-9
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation result summary or capacity is invalid"
        )


def _normalize_triggers(value: Any, *, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{symbol}.revisit_triggers must be an array"
        )
    result = []
    for trigger in value:
        if not isinstance(trigger, Mapping) or set(trigger) != _TRIGGER_KEYS:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"{symbol}.revisit trigger fields are invalid"
            )
        trigger_type = trigger.get("type")
        if trigger_type not in _TRIGGER_TYPES:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"{symbol}.revisit trigger type is invalid"
            )
        condition = trigger.get("condition")
        normalized_condition: str | dict[str, Any]
        if isinstance(condition, str):
            normalized_condition = condition.strip()
            valid_condition = bool(normalized_condition)
        elif isinstance(condition, Mapping):
            normalized_condition = dict(condition)
            valid_condition = bool(normalized_condition)
        else:
            normalized_condition = ""
            valid_condition = False
        if not valid_condition:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"{symbol}.revisit trigger condition is invalid"
            )
        result.append(
            {
                "type": trigger_type,
                "condition": normalized_condition,
                "reason": _text(trigger.get("reason"), "trigger.reason"),
            }
        )
    return result


def _packet_summary(
    payload: Mapping[str, Any],
    *,
    packet_path: Path,
    packet_sha256: str,
    repository_root: Path,
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": payload["run_id"],
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_sha256,
        "prepared_at": payload["prepared_at"],
        "candidate_count": payload["candidate_count"],
        "locked_calibration_case_count": payload[
            "locked_calibration_case_count"
        ],
        "selection_capacity": payload["capacity"]["selection_capacity"],
        "locked_company_count": payload["capacity"]["locked_company_count"],
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _result_summary(
    payload: Mapping[str, Any],
    *,
    result_path: Path,
    result_sha256: str,
    repository_root: Path,
    idempotent: bool,
    materialization: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": payload["run_id"],
        "result_path": _relative(result_path, repository_root),
        "result_sha256": result_sha256,
        "recorded_at": payload["recorded_at"],
        "profile_cycle_id": payload["profile_cycle_id"],
        "summary": dict(payload["summary"]),
        "idempotent": idempotent,
        "materialization": dict(materialization),
        "portfolio_action": None,
    }


def _terminal_governance_manifest(
    *,
    base: Path,
    run_id: str,
    prepared_at: dt.datetime,
) -> list[dict[str, Any]]:
    """Bind every sealed upstream governance artifact present at terminal prepare."""

    run_dir = base / "manager-screen" / run_id
    repository_root = base.parent.parent.resolve()
    if not run_dir.is_dir():
        raise ManagerScreenFullMarketAllocationV3Error(
            "manager-screen run directory is missing"
        )

    artifacts: dict[str, Path] = {}
    sidecars: dict[str, Path] = {}
    for path in run_dir.rglob("*.json"):
        if not path.is_file():
            continue
        relative = path.relative_to(run_dir).as_posix()
        artifact_relative = (
            relative[: -len(_SEAL_SUFFIX)]
            if relative.endswith(_SEAL_SUFFIX)
            else relative
        )
        if _ignored_terminal_governance_path(artifact_relative):
            continue
        if not _is_terminal_governance_upstream_path(artifact_relative):
            raise ManagerScreenFullMarketAllocationV3Error(
                "manager-screen run contains an unknown terminal governance JSON: "
                f"{relative}"
            )
        if relative.endswith(_SEAL_SUFFIX):
            sidecars[artifact_relative] = path
        else:
            artifacts[artifact_relative] = path

    missing_seals = sorted(set(artifacts) - set(sidecars))
    if missing_seals:
        raise ManagerScreenFullMarketAllocationV3Error(
            "terminal governance artifact is not sealed: " + missing_seals[0]
        )
    orphan_seals = sorted(set(sidecars) - set(artifacts))
    if orphan_seals:
        raise ManagerScreenFullMarketAllocationV3Error(
            "terminal governance seal has no artifact: " + orphan_seals[0]
        )

    rows: list[dict[str, Any]] = []
    for relative in sorted(artifacts):
        path = artifacts[relative]
        try:
            sealed = verify_sealed(path)
        except (OSError, SealingError) as exc:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"terminal governance artifact is invalid: {relative}"
            ) from exc
        if sealed.sealed_at >= prepared_at:
            raise ManagerScreenFullMarketAllocationV3Error(
                "terminal governance dependency must be sealed strictly before "
                f"prepared_at: {relative}"
            )
        rows.append(
            {
                "path": _relative(path, repository_root),
                "artifact_type": sealed.artifact_type,
                "sha256": sealed.sha256,
                "sealed_at": sealed.sealed_at.isoformat(),
            }
        )
    rows.sort(key=lambda row: row["path"])
    return rows


def _ignored_terminal_governance_path(relative: str) -> bool:
    full_market_prefix = FULL_MARKET_RELATIVE_DIR.as_posix() + "/"
    return (
        relative in _IGNORED_TERMINAL_GOVERNANCE_PATHS
        or (
            "/" not in relative
            and relative.startswith("research-policy")
            and relative.endswith(".json")
        )
        or relative.startswith(full_market_prefix)
    )


def _is_terminal_governance_upstream_path(relative: str) -> bool:
    parts = relative.split("/")
    if len(parts) == 2 and parts[0] == "control":
        return parts[1].endswith(".json")
    if parts and parts[0].startswith("batch-"):
        if len(parts) == 2:
            return parts[1] in {
                "batch.json",
                "packet.json",
                "result.json",
                "supersession.json",
                "freeze-journal.json",
            }
        if len(parts) == 4 and parts[1] == "calibration":
            return parts[3] in {"packet.json", "result.json"}
        if len(parts) == 4 and parts[1] == "quote-impact-reviews":
            return parts[3] in {"plan.json", "packet.json", "result.json"}
        return False
    if len(parts) == 2 and parts[0].startswith("legacy-transition-"):
        return parts[1] in {"plan.json", "packet.json", "result.json"}
    if len(parts) == 3 and parts[:2] == [
        "governance",
        "quote-impact-evolution",
    ]:
        return parts[2].endswith(".json")
    return parts == ["governance", "allocation-v3", "contract.json"] or parts == [
        "governance",
        "allocation-v3",
        "suspension.json",
    ]


def _validate_terminal_governance_manifest(value: Any) -> None:
    if not isinstance(value, list):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet terminal_governance_manifest must be an array"
        )
    paths: list[str] = []
    for row in value:
        if not isinstance(row, Mapping) or set(row) != _TERMINAL_GOVERNANCE_MANIFEST_KEYS:
            raise ManagerScreenFullMarketAllocationV3Error(
                "packet terminal governance manifest row is invalid"
            )
        path = _text(row.get("path"), "terminal governance path")
        parts = path.split("/")
        if (
            row.get("path") != path
            or "\\" in path
            or path.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or not path.endswith(".json")
            or path.endswith(_SEAL_SUFFIX)
        ):
            raise ManagerScreenFullMarketAllocationV3Error(
                "packet terminal governance manifest path is invalid"
            )
        _text(row.get("artifact_type"), "terminal governance artifact_type")
        _sha256(row.get("sha256"), "terminal governance sha256")
        _parse_datetime(row.get("sealed_at"), "terminal governance sealed_at")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ManagerScreenFullMarketAllocationV3Error(
            "packet terminal governance manifest must be uniquely path-sorted"
        )


def _sealed_any_source(path: Path, *, expected_sha256: str) -> tuple[dict[str, Any], Any]:
    try:
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate decision source is invalid: {path}"
        ) from exc
    if (
        sealed.sha256 != expected_sha256
        or sealed.artifact_type not in _SOURCE_TYPES
        or not isinstance(payload, Mapping)
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"candidate decision source binding is invalid: {path}"
        )
    return dict(payload), sealed


def _sealed_object(path: Path, *, artifact_type: str) -> tuple[dict[str, Any], Any]:
    try:
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"sealed full-market allocation dependency is invalid: {path}"
        ) from exc
    if sealed.artifact_type != artifact_type or not isinstance(payload, Mapping):
        raise ManagerScreenFullMarketAllocationV3Error(
            f"sealed artifact type is invalid: {path}"
        )
    return dict(payload), sealed


def _require_pair_or_absent(path: Path, label: str) -> None:
    seal = path.with_name(f"{path.name}.seal.json")
    if path.exists() != seal.exists():
        raise ManagerScreenFullMarketAllocationV3Error(f"{label} is only partially sealed")


def _unique_rows(path: Path, label: str) -> dict[str, dict[str, Any]]:
    try:
        rows = read_jsonl(path)
    except (OSError, ValueError) as exc:
        raise ManagerScreenFullMarketAllocationV3Error(f"{label} is invalid") from exc
    result = {}
    for row in rows:
        symbol = _symbol(row.get("symbol"))
        if symbol in result:
            raise ManagerScreenFullMarketAllocationV3Error(
                f"{label} contains a duplicate symbol: {symbol}"
            )
        result[symbol] = dict(row)
    return result


def _manager(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _MANAGER_KEYS:
        raise ManagerScreenFullMarketAllocationV3Error(
            "manager fields do not match the contract"
        )
    tools = value.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or any(not isinstance(item, str) or not item.strip() for item in tools)
    ):
        raise ManagerScreenFullMarketAllocationV3Error(
            "manager.tools must be non-empty strings"
        )
    normalized_tools = [item.strip() for item in tools]
    if len(normalized_tools) != len(set(normalized_tools)):
        raise ManagerScreenFullMarketAllocationV3Error("manager.tools must be unique")
    return {
        "agent": _text(value.get("agent"), "manager.agent"),
        "model": _text(value.get("model"), "manager.model"),
        "tools": normalized_tools,
    }


def _repository_path(value: Any, repository_root: Path) -> Path:
    text = _text(value, "repository path")
    path = Path(text)
    if path.is_absolute():
        raise ManagerScreenFullMarketAllocationV3Error(
            "repository binding paths must be relative"
        )
    resolved = (repository_root / path).resolve()
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "repository binding path escapes the repository"
        ) from exc
    return resolved


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"path is outside the repository: {path}"
        ) from exc


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if not _ID_RE.fullmatch(text):
        raise ManagerScreenFullMarketAllocationV3Error(f"{field} is invalid")
    return text


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not _SYMBOL_RE.fullmatch(value):
        raise ManagerScreenFullMarketAllocationV3Error(f"invalid CN symbol: {value}")
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ManagerScreenFullMarketAllocationV3Error(f"{field} must be lowercase SHA-256")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenFullMarketAllocationV3Error(f"{field} must be non-empty text")
    return value.strip()


def _aware(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{field} must be timezone-aware"
        )
    return value


def _parse_datetime(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ManagerScreenFullMarketAllocationV3Error(f"{field} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{field} must be an ISO datetime"
        ) from exc
    return _aware(parsed, field)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManagerScreenFullMarketAllocationV3Error(f"{field} must be a positive integer")
    return value


def _capacity_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManagerScreenFullMarketAllocationV3Error(
            f"{field} must be a non-negative integer"
        )
    return value


def _positive_hours(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise ManagerScreenFullMarketAllocationV3Error(f"{field} must be positive hours")
    return float(value)


def _payload_sha256(value: Any) -> str:
    try:
        return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    except SealingError as exc:
        raise ManagerScreenFullMarketAllocationV3Error(
            "full-market allocation payload is not canonical JSON"
        ) from exc
