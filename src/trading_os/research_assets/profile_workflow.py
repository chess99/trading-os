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
from .models import PolicyKind, canonical_company_name, load_policy
from .profile_stage_claims import (
    ProfileStageClaimError,
    assert_agent_profile_stage_claim_capacity,
    claim_profile_stage_attempt,
    profile_stage_claim_reservation_agent,
    release_profile_stage_attempt,
    seal_profile_stage_success,
    sealed_profile_stage_claim_authority_exists,
    verify_active_profile_stage_claim,
    verify_profile_stage_success,
)
from .research_allocation import (
    ResearchAllocationError,
    evaluate_quick_profile,
)
from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed

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
MANAGER_BOUND_PACKAGE_KEYS = PACKAGE_KEYS | {
    "manager_screen_binding",
    "decisive_answer",
}
ADJUDICATED_MANAGER_BOUND_PACKAGE_KEYS = MANAGER_BOUND_PACKAGE_KEYS | {
    "profile_adjudication_binding",
}
PROFILE_CLAIM_ATTEMPT_KEYS = {
    "path",
    "sha256",
    "sealed_at",
    "attempt_number",
    "agent",
    "stage_authorization",
}
PROFILE_CLAIM_AUTHORIZATION_KEYS = {
    "path",
    "sha256",
    "artifact_type",
    "sealed_at",
}
MANAGER_SCREEN_BINDING_KEYS = {
    "result_path",
    "result_sha256",
    "decisive_question",
    "evidence_ids",
}
PROFILE_ADJUDICATION_RESEARCH_BINDING_KEYS = {
    "path",
    "sha256",
    "corrected_decisive_question",
    "evidence_ids",
}
FULL_MARKET_ALLOCATION_BINDING_FIELDS = (
    "manager_screen_allocation_result_path",
    "manager_screen_allocation_result_sha256",
    "manager_screen_allocation_candidate_sha256",
    "manager_screen_allocation_decision",
)
FULL_MARKET_CALIBRATION_BINDING_FIELDS = (
    "manager_screen_calibration_result_path",
    "manager_screen_calibration_result_sha256",
    "manager_screen_calibration_review_sha256",
    "manager_screen_calibration_adjudication_sha256",
)
LOCKED_CALIBRATION_REMEDIATION_FIELD = "manager_screen_locked_calibration_remediation"
LOCKED_CALIBRATION_REMEDIATION_KEYS = {
    "schema_version",
    "workflow",
    "run_id",
    "recorded_at",
    "allocation_result_path",
    "allocation_result_sha256",
    "locked_calibration_case_sha256",
    "remediation",
    "reason",
    "resolved_work_sha256",
    "decisive_question",
    "evidence_ids",
    "revisit_triggers",
    "calibration_result_path",
    "calibration_result_sha256",
    "calibration_result_sealed_at",
    "calibration_review_sha256",
    "calibration_adjudication_sha256",
}
MANAGER_SCREEN_PROVENANCE_FIELDS = (
    "manager_screen_batch_id",
    "manager_screen_route",
    "manager_screen_result_path",
    "manager_screen_result_sha256",
    *FULL_MARKET_ALLOCATION_BINDING_FIELDS,
    *FULL_MARKET_CALIBRATION_BINDING_FIELDS,
)
RESEARCH_POLICY_BINDING_KEYS = {
    "policy_id",
    "version",
    "path",
    "file_sha256",
    "payload_sha256",
}
DECISIVE_ANSWER_KEYS = {"conclusion", "source_ids", "unresolved_reason"}
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
    "targeted_followup_candidate",
    "price_watch",
    "reassign_or_stop",
    "watch_only",
    "conditional_stop",
    "needs_manual_review",
}
TARGETED_FOLLOWUP_DECLINE_OUTCOMES = {
    "price_watch",
    "watch_only",
    "conditional_stop",
}
REACTIVATION_TRIGGER_TYPES = {
    "filing",
    "price",
    "date",
    "ttl",
    "event",
    "thesis",
}
REACTIVATION_TRIGGER_KEYS = {"type", "condition", "reason"}
PROFILE_ADJUDICATION_SUBMISSION_KEYS = {
    "schema_version",
    "profile_cycle_id",
    "stage",
    "profile_path",
    "profile_sha256",
    "evaluation_path",
    "evaluation_sha256",
    "claim_path",
    "claim_sha256",
    "success_path",
    "success_sha256",
    "full_market_result_path",
    "full_market_result_sha256",
    "full_market_candidate_sha256",
    "reviewer",
    "manager",
    "outcome",
    "reason",
    "material_errors",
    "evidence",
    "qa_sources",
    "corrected_decisive_question",
    "corrected_decisive_answer",
    "restart_triggers",
    "additional_budget_hours",
    "portfolio_action",
}
PROFILE_ADJUDICATION_PAYLOAD_KEYS = PROFILE_ADJUDICATION_SUBMISSION_KEYS | {
    "workflow",
    "adjudicated_at",
    "research_agent",
    "original_effective_outcome",
    "prior_queue_row",
    "prior_screening_row",
}
PROFILE_ADJUDICATION_ERROR_KEYS = {
    "error_id",
    "error_type",
    "finding",
    "evidence_ids",
}
PROFILE_ADJUDICATION_EVIDENCE_KEYS = {
    "evidence_id",
    "description",
    "source_ids",
}
PROFILE_ADJUDICATION_SOURCE_KEYS = {"source_id", "path", "sha256"}
PROFILE_ADJUDICATION_OUTCOMES = {"manager_upheld", "material_error_confirmed"}
PROFILE_ADJUDICATION_ERROR_TYPES = {
    "verifiable_factual_error",
    "cash_bridge_error",
    "valuation_bridge_error",
    "source_mismatch",
    "material_risk_omission",
    "contract_violation",
}
PROFILE_ADJUDICATION_BINDING_FIELDS = (
    "profile_adjudication_path",
    "profile_adjudication_sha256",
    "profile_adjudication_outcome",
)
PROFILE_ADJUDICATION_BRIEF_FIELDS = (
    "profile_adjudication_cycle_id",
    "profile_adjudication_decisive_question",
    "profile_adjudication_evidence_ids",
)
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
    run_id: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """Atomically claim one profile task.

    A symbol-less claim is production-safe by default: it only considers
    manager-screen-bound tasks from one run and one stage.  When ``run_id`` is
    omitted, the lexicographically latest eligible manager-screen run is the
    current run.  Run IDs are date-prefixed by contract, so this is stable and
    does not mix legacy or cross-run work.
    """

    _require_aware_datetime(claimed_at, "claimed_at")
    agent_name = _text(agent, "agent")
    base = Path(root)
    repository_root = base.parent.parent
    queue_path = base / RESEARCH_QUEUE_FILE
    queue = read_jsonl(queue_path)
    if symbol is not None and not re.fullmatch(r"CN:[0-9]{6}", symbol):
        raise ResearchAllocationError("claim symbol is invalid")
    if symbol is not None and _canonical_profile_adjudication_paths(
        base=base,
        symbol=symbol,
    ):
        raise ResearchAllocationError(
            "a sealed profile adjudication forbids new profile claims until "
            f"a sealed successor workflow exists: {symbol}"
        )
    try:
        sealed_active_symbol = assert_agent_profile_stage_claim_capacity(
            root=base,
            queue_records=queue,
            agent=agent_name,
            requested_symbol=symbol,
        )
    except ProfileStageClaimError as exc:
        raise ResearchAllocationError(str(exc)) from exc
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
        _validate_profile_claim_stage_authorization(
            current,
            base=base,
            repository_root=repository_root,
        )
        if not _allocation_v3_claimable_candidates([current], base=base):
            raise ResearchAllocationError(
                "running profile task is no longer authorized by its allocation contract"
            )
        _require_full_market_profile_claim_activation(
            current,
            base=base,
            repository_root=repository_root,
            claimed_at=claimed_at,
        )
        if _requires_authenticated_profile_stage_claim(
            current,
            base=base,
            repository_root=repository_root,
        ):
            try:
                verify_active_profile_stage_claim(
                    root=base,
                    queue_record=current,
                    stage=str(current.get("task_type")),
                )
            except ProfileStageClaimError as exc:
                raise ResearchAllocationError(str(exc)) from exc
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
        for item in candidates:
            if item.get("symbol") == symbol:
                _manager_screen_run_id_for_record(
                    item,
                    context="profile claim",
                )
    if sealed_active_symbol is not None:
        candidates = [item for item in candidates if item.get("symbol") == sealed_active_symbol]
    candidates = [
        item
        for item in candidates
        if item.get("task_type") != "targeted_followup"
        or _targeted_followup_task_has_valid_approval(
            item,
            repository_root=repository_root,
        )
    ]
    requested_stage = _claim_stage(stage, default_for_symbol_less=symbol is None)
    if requested_stage is not None:
        candidates = [item for item in candidates if item.get("task_type") == requested_stage]
    requested_run = _optional_identifier(run_id, "run_id")
    if symbol is None:
        candidates = [
            item
            for item in candidates
            if isinstance(item.get("manager_screen_run_id"), str)
            and isinstance(item.get("manager_screen_result_path"), str)
            and isinstance(item.get("manager_screen_result_sha256"), str)
        ]
        eligible_runs = sorted({str(item["manager_screen_run_id"]) for item in candidates})
        if requested_run is None:
            if not eligible_runs:
                raise ResearchAllocationError("no eligible manager-bound profile task is available")
            requested_run = eligible_runs[-1]
        candidates = [
            item for item in candidates if item.get("manager_screen_run_id") == requested_run
        ]
    elif requested_run is not None:
        candidates = [
            item for item in candidates if item.get("manager_screen_run_id") == requested_run
        ]
    if symbol is not None:
        candidates = [item for item in candidates if item.get("symbol") == symbol]
    if lens is not None:
        lens_name = _text(lens, "lens")
        candidates = [item for item in candidates if lens_name in (item.get("selected_by") or [])]
    candidates = _allocation_v3_claimable_candidates(
        candidates,
        base=base,
    )
    claimable_candidates = []
    for item in candidates:
        if not _requires_authenticated_profile_stage_claim(
            item,
            base=base,
            repository_root=repository_root,
        ):
            claimable_candidates.append(item)
            continue
        try:
            reserved_agent = profile_stage_claim_reservation_agent(
                root=base,
                queue_record=item,
            )
        except ProfileStageClaimError as exc:
            raise ResearchAllocationError(str(exc)) from exc
        if reserved_agent in {None, agent_name}:
            claimable_candidates.append(item)
    candidates = claimable_candidates
    if not candidates:
        raise ResearchAllocationError("no eligible profile task is available")
    if symbol is None:
        candidates.sort(
            key=lambda item: (
                str(item.get("manager_screen_batch_id") or ""),
                str(item.get("symbol")),
            )
        )
    else:
        candidates.sort(
            key=lambda item: (
                int(item.get("priority", 5)),
                {"scoped_research": 0, "targeted_followup": 1}.get(str(item.get("task_type")), 2),
                str(item.get("symbol")),
            )
        )
    selected = dict(candidates[0])
    _validate_profile_claim_stage_authorization(
        selected,
        base=base,
        repository_root=repository_root,
    )
    _require_full_market_profile_claim_activation(
        selected,
        base=base,
        repository_root=repository_root,
        claimed_at=claimed_at,
    )
    if _requires_authenticated_profile_stage_claim(
        selected,
        base=base,
        repository_root=repository_root,
    ):
        try:
            selected, _ = claim_profile_stage_attempt(
                root=base,
                queue_record=selected,
                agent=agent_name,
                claimed_at=claimed_at,
            )
        except ProfileStageClaimError as exc:
            raise ResearchAllocationError(str(exc)) from exc
    else:
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


def _allocation_v3_claimable_candidates(
    candidates: list[Mapping[str, Any]],
    *,
    base: Path,
) -> list[Mapping[str, Any]]:
    """Fail closed on inherited quick-profile work after a v3 migration freeze."""

    by_run: dict[str, list[Mapping[str, Any]]] = {}
    passthrough: list[Mapping[str, Any]] = []
    for item in candidates:
        run_id = _manager_screen_run_id_for_record(
            item,
            context="profile claim",
        )
        if item.get("task_type") != "quick_profile" or not isinstance(run_id, str):
            passthrough.append(item)
            continue
        by_run.setdefault(run_id, []).append(item)

    allowed = list(passthrough)
    for run_id, rows in by_run.items():
        governance_dir = base / "manager-screen" / run_id / "governance" / "allocation-v3"
        contract_path = governance_dir / "contract.json"
        contract_seal_path = contract_path.with_name(f"{contract_path.name}.seal.json")
        suspension_path = governance_dir / "suspension.json"
        suspension_seal_path = suspension_path.with_name(f"{suspension_path.name}.seal.json")
        full_market_dir = governance_dir / "full-market"
        full_packet_path = full_market_dir / "packet.json"
        full_packet_seal_path = full_packet_path.with_name(f"{full_packet_path.name}.seal.json")
        full_result_path = full_market_dir / "result.json"
        full_result_seal_path = full_result_path.with_name(f"{full_result_path.name}.seal.json")
        contract_presence = (contract_path.exists(), contract_seal_path.exists())
        suspension_presence = (suspension_path.exists(), suspension_seal_path.exists())
        full_packet_presence = (full_packet_path.exists(), full_packet_seal_path.exists())
        full_result_presence = (full_result_path.exists(), full_result_seal_path.exists())
        if contract_presence == (False, False):
            if suspension_presence != (False, False):
                raise ResearchAllocationError(
                    f"allocation v3 suspension exists without its sealed contract: {run_id}"
                )
            allowed.extend(rows)
            continue
        if contract_presence[0] != contract_presence[1]:
            raise ResearchAllocationError(
                f"allocation v3 contract is only partially sealed: {run_id}"
            )
        if suspension_presence[0] != suspension_presence[1]:
            raise ResearchAllocationError(
                f"allocation v3 suspension is only partially sealed: {run_id}"
            )
        if full_packet_presence[0] != full_packet_presence[1]:
            raise ResearchAllocationError(
                f"allocation v3 full-market packet is only partially sealed: {run_id}"
            )
        if full_result_presence[0] != full_result_presence[1]:
            raise ResearchAllocationError(
                f"allocation v3 full-market result is only partially sealed: {run_id}"
            )
        if full_result_presence == (True, True) and full_packet_presence != (True, True):
            raise ResearchAllocationError(
                f"allocation v3 full-market result exists without its packet: {run_id}"
            )

        from .manager_screen_allocation_v3 import (
            ManagerScreenAllocationV3Error,
            verify_manager_screen_allocation_v3_contract,
        )

        try:
            contract = verify_manager_screen_allocation_v3_contract(
                root=base,
                run_id=run_id,
            )
        except ManagerScreenAllocationV3Error as exc:
            raise ResearchAllocationError(
                f"allocation v3 contract is invalid during profile claim: {run_id}"
            ) from exc
        if suspension_presence == (True, True):
            from .manager_screen_allocation_v3_suspension import (
                ManagerScreenAllocationV3SuspensionError,
                verify_manager_screen_allocation_v3_suspension,
            )

            try:
                verify_manager_screen_allocation_v3_suspension(
                    root=base,
                    run_id=run_id,
                )
            except ManagerScreenAllocationV3SuspensionError as exc:
                raise ResearchAllocationError(
                    f"allocation v3 suspension is invalid during profile claim: {run_id}"
                ) from exc
        classifications = {
            item["symbol"]: item["commitment_class"]
            for item in contract["commitment_classification"]
        }
        final_result = None
        full_market_grant_context: Mapping[str, Any] | None = None
        final_decisions: dict[str, Mapping[str, Any]] = {}
        screening_by_symbol: dict[str, Mapping[str, Any]] = {}
        if full_result_presence == (True, True):
            from .manager_screen_full_market_allocation_v3 import (
                ManagerScreenFullMarketAllocationV3Error,
                verify_manager_screen_full_market_allocation_v3_result,
            )

            try:
                final_result = verify_manager_screen_full_market_allocation_v3_result(
                    root=base,
                    run_id=run_id,
                )
            except ManagerScreenFullMarketAllocationV3Error as exc:
                raise ResearchAllocationError(
                    f"allocation v3 full-market result is invalid during profile claim: {run_id}"
                ) from exc
            full_market_grant_context = _load_full_market_profile_grant_context(
                root=base,
                repository_root=base.parent.parent.resolve(),
                run_id=run_id,
                verified_result=final_result,
            )
            final_decisions = {
                item["symbol"]: item
                for item in final_result["decisions"]
                if isinstance(item, Mapping)
            }
            screening_by_symbol = {
                item["symbol"]: item
                for item in read_jsonl(base / SCREENING_FILE)
                if isinstance(item.get("symbol"), str)
            }
        for item in rows:
            symbol = str(item.get("symbol"))
            commitment_class = classifications.get(symbol)
            if commitment_class == "irreversible":
                allowed.append(item)
            elif final_result is not None:
                decision = final_decisions.get(symbol)
                screen = screening_by_symbol.get(symbol)
                if (
                    isinstance(decision, Mapping)
                    and decision.get("decision") == "fund_quick_profile"
                    and _full_market_profile_binding_is_claimable(
                        item,
                        screen=screen,
                        grant_context=full_market_grant_context,
                        root=base,
                        repository_root=base.parent.parent.resolve(),
                    )
                ):
                    allowed.append(item)
                else:
                    raise ResearchAllocationError(
                        "quick-profile task is not authorized by the sealed full-market "
                        f"allocation: {run_id}/{symbol}"
                    )
            elif commitment_class == "revocable":
                # A sealed suspension may not yet have projected its JSONL row
                # after a crash.  The contract classification alone is enough
                # to prevent a new claim in that window.
                continue
            else:
                raise ResearchAllocationError(
                    "quick-profile task is not authorized by the allocation v3 "
                    f"inherited ledger: {run_id}/{symbol}"
                )
    return allowed


def _requires_sealed_profile_stage_claim(record: Mapping[str, Any]) -> bool:
    if record.get("task_type") not in {
        "quick_profile",
        "targeted_followup",
        "scoped_research",
        "deep_research",
    }:
        return False
    return bool(
        record.get("manager_screen_run_id") is not None
        or _has_manager_screen_provenance(record)
        or any(
            record.get(field) is not None
            for field in (
                "profile_stage_claim_attempt_path",
                "profile_stage_claim_attempt_sha256",
            )
        )
    )


def _requires_authenticated_profile_stage_claim(
    record: Mapping[str, Any],
    *,
    base: Path,
    repository_root: Path,
) -> bool:
    """Require receipts when either the queue or immutable authority is modern.

    Mutable queue provenance can be incomplete after a projection crash or
    deliberate tampering.  Claim/release and record must therefore make the
    same decision from the sealed authority ledger; otherwise a targeted or
    scoped task could be claimed through the legacy mutable path and then be
    impossible to complete under the stricter record contract.
    """

    if _requires_sealed_profile_stage_claim(record):
        return True
    symbol = record.get("symbol")
    stage = record.get("task_type")
    if not isinstance(symbol, str) or not isinstance(stage, str):
        return False
    return _sealed_modern_profile_authority_exists(
        base=base,
        repository_root=repository_root,
        queue_record=record,
        symbol=symbol,
        stage=stage,
    )


def _full_market_profile_binding_is_claimable(
    row: Mapping[str, Any],
    *,
    screen: Mapping[str, Any] | None,
    grant_context: Mapping[str, Any] | None,
    root: Path,
    repository_root: Path,
) -> bool:
    if screen is None or grant_context is None:
        return False
    try:
        _verify_funded_full_market_profile_grant(
            queue_record=row,
            screen_record=screen,
            root=root,
            repository_root=repository_root,
            symbol=_text(row.get("symbol"), "research_queue.symbol"),
            expected_cycle_id=row.get("profile_cycle_id"),
            required=True,
            context="profile claim",
            grant_context=grant_context,
            require_screen_research_brief=True,
        )
    except ResearchAllocationError:
        return False
    return True


def _require_full_market_profile_claim_activation(
    queue_record: Mapping[str, Any],
    *,
    base: Path,
    repository_root: Path,
    claimed_at: dt.datetime,
) -> None:
    """Latch a globally finalized allocation before its first company claim.

    ``final-status`` compares JSONL rows with their pre-work projection, so the
    first legitimate ``pending -> running`` claim makes the live status false.
    The singleton gate proves that the whole projection was finalized before
    work began.  Per-symbol receipts then distinguish legitimate later work
    from drift in a company that was never activated.
    """

    if queue_record.get("task_type") != "quick_profile" or not (
        _requires_funded_full_market_grant(queue_record)
    ):
        return
    run_id = _text(queue_record.get("manager_screen_run_id"), "manager_screen_run_id")
    cycle = _text(queue_record.get("profile_cycle_id"), "profile_cycle_id")
    symbol = _text(queue_record.get("symbol"), "research_queue.symbol")
    from .manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        manager_screen_full_market_allocation_v3_final_status,
        verify_manager_screen_full_market_allocation_v3_result,
    )

    try:
        result = verify_manager_screen_full_market_allocation_v3_result(
            root=base,
            run_id=run_id,
        )
        status = manager_screen_full_market_allocation_v3_final_status(
            root=base,
            run_id=run_id,
        )
    except ManagerScreenFullMarketAllocationV3Error as exc:
        raise ResearchAllocationError(
            f"full-market final-status is invalid during profile claim: {run_id}"
        ) from exc
    if result.get("profile_cycle_id") != cycle:
        raise ResearchAllocationError(
            f"full-market profile claim cycle does not match its result: {symbol}"
        )

    gate, gate_sha256, gate_relative = _load_or_create_full_market_claim_gate(
        base=base,
        repository_root=repository_root,
        queue_record=queue_record,
        result=result,
        status=status,
        claimed_at=claimed_at,
    )
    _validate_full_market_claim_status_binding(
        status,
        gate=gate,
        result=result,
    )
    if status.get("finalized") is not True:
        _validate_full_market_claim_drift_receipts(
            base=base,
            repository_root=repository_root,
            result=result,
            status=status,
            gate=gate,
            gate_sha256=gate_sha256,
            gate_relative=gate_relative,
        )
    _load_or_create_full_market_claim_receipt(
        base=base,
        repository_root=repository_root,
        result=result,
        symbol=symbol,
        gate=gate,
        gate_sha256=gate_sha256,
        gate_relative=gate_relative,
        activated_at=claimed_at,
        allow_create=queue_record.get("status") == "pending",
    )


def _full_market_claim_activation_dir(base: Path, cycle: str) -> Path:
    return base / "profiles" / cycle / "full-market-claim-activation"


def _seal_sidecar(path: Path) -> Path:
    return path.with_name(f"{path.name}.seal.json")


def _load_or_create_full_market_claim_gate(
    *,
    base: Path,
    repository_root: Path,
    queue_record: Mapping[str, Any],
    result: Mapping[str, Any],
    status: Mapping[str, Any],
    claimed_at: dt.datetime,
) -> tuple[dict[str, Any], str, str]:
    cycle = _text(result.get("profile_cycle_id"), "full_market_result.profile_cycle_id")
    gate_path = _full_market_claim_activation_dir(base, cycle) / "gate.json"
    gate_relative = gate_path.resolve().relative_to(repository_root.resolve()).as_posix()
    pair = (gate_path.exists(), _seal_sidecar(gate_path).exists())
    if pair[0] != pair[1]:
        raise ResearchAllocationError("full-market profile claim gate is only partially sealed")
    if pair == (False, False):
        if status.get("finalized") is not True:
            raise ResearchAllocationError(
                "full-market allocation final-status must be finalized before the first "
                "profile claim"
            )
        expected_status = {
            "run_id": result.get("run_id"),
            "result_path": queue_record.get("manager_screen_allocation_result_path"),
            "result_sha256": result.get("result_sha256"),
            "profile_cycle_id": cycle,
            "finalized": True,
        }
        if any(status.get(key) != value for key, value in expected_status.items()):
            raise ResearchAllocationError(
                "full-market final-status does not match the profile claim binding"
            )
        payload = {
            "schema_version": 1,
            "run_id": result["run_id"],
            "profile_cycle_id": cycle,
            "stage": "quick_profile",
            "allocation_packet_path": status["packet_path"],
            "allocation_packet_sha256": status["packet_sha256"],
            "allocation_result_path": status["result_path"],
            "allocation_result_sha256": status["result_sha256"],
            "final_status_sha256": _canonical_full_market_final_status_sha256(
                status=status,
                result=result,
            ),
            "finalized": True,
            "activated_at": claimed_at.isoformat(),
            "portfolio_action": None,
        }
        try:
            sealed = seal_json(
                gate_path,
                payload,
                artifact_type="full_market_profile_claim_activation_gate",
                sealed_at=claimed_at,
            )
        except (OSError, SealingError) as exc:
            raise ResearchAllocationError(
                "full-market profile claim gate could not be sealed"
            ) from exc
        return payload, sealed.sha256, gate_relative

    payload, sha256 = _verify_full_market_claim_gate(
        gate_path,
        result=result,
        status=status,
        claimed_at=claimed_at,
    )
    return payload, sha256, gate_relative


def _verify_full_market_claim_gate(
    gate_path: Path,
    *,
    result: Mapping[str, Any],
    status: Mapping[str, Any],
    claimed_at: dt.datetime,
) -> tuple[dict[str, Any], str]:
    try:
        sealed = verify_sealed(gate_path)
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError("full-market profile claim gate is invalid") from exc
    expected_keys = {
        "schema_version",
        "run_id",
        "profile_cycle_id",
        "stage",
        "allocation_packet_path",
        "allocation_packet_sha256",
        "allocation_result_path",
        "allocation_result_sha256",
        "final_status_sha256",
        "finalized",
        "activated_at",
        "portfolio_action",
    }
    if (
        sealed.artifact_type != "full_market_profile_claim_activation_gate"
        or not isinstance(payload, dict)
        or set(payload) != expected_keys
        or payload.get("schema_version") != 1
        or payload.get("run_id") != result.get("run_id")
        or payload.get("profile_cycle_id") != result.get("profile_cycle_id")
        or payload.get("stage") != "quick_profile"
        or payload.get("allocation_packet_path") != status.get("packet_path")
        or payload.get("allocation_packet_sha256") != status.get("packet_sha256")
        or payload.get("allocation_result_path") != status.get("result_path")
        or payload.get("allocation_result_sha256") != result.get("result_sha256")
        or payload.get("final_status_sha256")
        != _canonical_full_market_final_status_sha256(
            status=status,
            result=result,
        )
        or payload.get("finalized") is not True
        or payload.get("portfolio_action") is not None
    ):
        raise ResearchAllocationError(
            "full-market profile claim gate does not match its allocation"
        )
    activated_at = _datetime(payload.get("activated_at"), "claim_gate.activated_at")
    if activated_at > claimed_at:
        raise ResearchAllocationError("full-market profile claim gate is from the future")
    return payload, sealed.sha256


def _canonical_full_market_final_status_sha256(
    *,
    status: Mapping[str, Any],
    result: Mapping[str, Any],
) -> str:
    """Rebuild the only finalized status the sealed allocation can have.

    Live ``final-status`` necessarily drifts once work starts.  A gate must
    therefore bind the canonical *pre-work* projection, not merely contain a
    digest-looking string and not hash the later mutable projection.  The
    verified result is a complete partition of the packet, so every decision
    had one queue and one screening projection when the gate was created.
    """

    decisions = result.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ResearchAllocationError(
            "full-market claim gate cannot rebuild its finalized projection"
        )
    candidate_count = len(decisions)
    locked_remediations = result.get("locked_calibration_remediations", [])
    if not isinstance(locked_remediations, list):
        raise ResearchAllocationError(
            "full-market claim gate locked remediation projection is invalid"
        )
    locked_count = len(locked_remediations)
    canonical = dict(status)
    materialization = {
        "queue_materialized_count": candidate_count,
        "screening_materialized_count": candidate_count,
        "queue_repaired_count": 0,
        "screening_repaired_count": 0,
        "fully_materialized": True,
        "drift": [],
    }
    if (
        "locked_calibration_remediations" in result
        or "locked_remediation_queue_materialized_count" in (status.get("materialization") or {})
    ):
        materialization.update(
            {
                "locked_remediation_queue_materialized_count": locked_count,
                "locked_remediation_screening_materialized_count": locked_count,
            }
        )
    canonical["materialization"] = materialization
    canonical["finalized"] = True
    return hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()


def _validate_full_market_claim_status_binding(
    status: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    expected = {
        "run_id": gate.get("run_id"),
        "packet_path": gate.get("allocation_packet_path"),
        "packet_sha256": gate.get("allocation_packet_sha256"),
        "result_path": gate.get("allocation_result_path"),
        "result_sha256": gate.get("allocation_result_sha256"),
        "profile_cycle_id": gate.get("profile_cycle_id"),
    }
    if any(status.get(key) != value for key, value in expected.items()) or result.get(
        "result_sha256"
    ) != gate.get("allocation_result_sha256"):
        raise ResearchAllocationError(
            "full-market claim gate does not match the current final-status"
        )


def _validate_full_market_claim_drift_receipts(
    *,
    base: Path,
    repository_root: Path,
    result: Mapping[str, Any],
    status: Mapping[str, Any],
    gate: Mapping[str, Any],
    gate_sha256: str,
    gate_relative: str,
) -> None:
    materialization = status.get("materialization")
    drift = materialization.get("drift") if isinstance(materialization, Mapping) else None
    if not isinstance(drift, list) or not drift:
        raise ResearchAllocationError(
            "full-market final-status is not finalized without explicit projection drift"
        )
    drift_symbols: set[str] = set()
    for item in drift:
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("symbol"), str)
            or item.get("projection") not in {"research_queue", "screening"}
        ):
            raise ResearchAllocationError("full-market final-status drift payload is invalid")
        drift_symbols.add(str(item["symbol"]))
    queue = {
        item["symbol"]: item
        for item in read_jsonl(base / RESEARCH_QUEUE_FILE)
        if isinstance(item.get("symbol"), str)
    }
    screening = {
        item["symbol"]: item
        for item in read_jsonl(base / SCREENING_FILE)
        if isinstance(item.get("symbol"), str)
    }
    grant_context = _load_full_market_profile_grant_context(
        root=base,
        repository_root=repository_root,
        run_id=_text(result.get("run_id"), "full_market_result.run_id"),
        verified_result=result,
    )
    for symbol in sorted(drift_symbols):
        _load_or_create_full_market_claim_receipt(
            base=base,
            repository_root=repository_root,
            result=result,
            symbol=symbol,
            gate=gate,
            gate_sha256=gate_sha256,
            gate_relative=gate_relative,
            activated_at=None,
            allow_create=False,
        )
        queue_record = queue.get(symbol)
        screen_record = screening.get(symbol)
        if not isinstance(queue_record, Mapping) or not isinstance(screen_record, Mapping):
            raise ResearchAllocationError(
                f"full-market activated projection row is missing: {symbol}"
            )
        _validate_full_market_activated_allocation_identity(
            symbol=symbol,
            queue_record=queue_record,
            screen_record=screen_record,
            grant_context=grant_context,
        )


def _validate_full_market_activated_allocation_identity(
    *,
    symbol: str,
    queue_record: Mapping[str, Any],
    screen_record: Mapping[str, Any],
    grant_context: Mapping[str, Any],
) -> None:
    """Keep activation identity immutable while later workflows own live state.

    The receipt proves that the symbol passed the global pre-work gate.  Queue
    status, rationale, attempt history, and downstream stage fields are mutable
    workflow projections and are deliberately outside this check.  Each later
    stage must validate its own sealed approval/selection when it is used.
    """

    candidate = grant_context["candidates"].get(symbol)
    decision = grant_context["decisions"].get(symbol)
    result = grant_context["result"]
    if not isinstance(candidate, Mapping) or not isinstance(decision, Mapping):
        raise ResearchAllocationError(
            f"full-market activated symbol is absent from its sealed allocation: {symbol}"
        )
    prior_queue = candidate.get("prior_queue_row")
    expected = {
        "manager_screen_run_id": result.get("run_id"),
        "manager_screen_batch_id": (
            prior_queue.get("manager_screen_batch_id") if isinstance(prior_queue, Mapping) else None
        ),
        "manager_screen_route": candidate.get("original_route"),
        "manager_screen_result_path": candidate.get("effective_decision_source_path"),
        "manager_screen_result_sha256": candidate.get("effective_decision_source_sha256"),
        "manager_screen_allocation_result_path": grant_context.get("result_path"),
        "manager_screen_allocation_result_sha256": grant_context.get("result_sha256"),
        "manager_screen_allocation_candidate_sha256": candidate.get("candidate_sha256"),
        "manager_screen_allocation_decision": "fund_quick_profile",
        "profile_cycle_id": result.get("profile_cycle_id"),
    }
    if (
        decision.get("decision") != "fund_quick_profile"
        or decision.get("candidate_sha256") != candidate.get("candidate_sha256")
        or any(queue_record.get(field) != value for field, value in expected.items())
        or any(screen_record.get(field) != value for field, value in expected.items())
        or queue_record.get("allocation_sha256") != grant_context.get("result_sha256")
    ):
        raise ResearchAllocationError(
            f"full-market activated immutable allocation binding drifted: {symbol}"
        )
    expected_calibration = _full_market_calibration_projection(candidate)
    _validate_full_market_calibration_projection(
        queue_record,
        expected=expected_calibration,
        context="activated full-market queue",
    )
    _validate_full_market_calibration_projection(
        screen_record,
        expected=expected_calibration,
        context="activated full-market screening",
    )


def _load_or_create_full_market_claim_receipt(
    *,
    base: Path,
    repository_root: Path,
    result: Mapping[str, Any],
    symbol: str,
    gate: Mapping[str, Any],
    gate_sha256: str,
    gate_relative: str,
    activated_at: dt.datetime | None,
    allow_create: bool,
) -> tuple[dict[str, Any], str]:
    decisions = [
        item
        for item in result.get("decisions") or []
        if isinstance(item, Mapping) and item.get("symbol") == symbol
    ]
    decision = decisions[0] if len(decisions) == 1 else None
    if not isinstance(decision, Mapping) or decision.get("decision") != "fund_quick_profile":
        raise ResearchAllocationError(
            f"full-market projection drift is not an activated quick-profile claim: {symbol}"
        )
    cycle = _text(result.get("profile_cycle_id"), "full_market_result.profile_cycle_id")
    filename = f"{symbol.replace(':', '-')}.json"
    receipt_path = _full_market_claim_activation_dir(base, cycle) / "receipts" / filename
    pair = (receipt_path.exists(), _seal_sidecar(receipt_path).exists())
    if pair[0] != pair[1]:
        raise ResearchAllocationError(
            f"full-market profile claim receipt is only partially sealed: {symbol}"
        )
    expected = {
        "schema_version": 1,
        "run_id": result["run_id"],
        "profile_cycle_id": cycle,
        "stage": "quick_profile",
        "symbol": symbol,
        "allocation_result_path": gate["allocation_result_path"],
        "allocation_result_sha256": result["result_sha256"],
        "allocation_candidate_sha256": decision["candidate_sha256"],
        "activation_gate_path": gate_relative,
        "activation_gate_sha256": gate_sha256,
        "portfolio_action": None,
    }
    if pair == (False, False):
        if not allow_create or activated_at is None:
            raise ResearchAllocationError(
                f"full-market projection drift lacks a sealed claim activation receipt: {symbol}"
            )
        payload = {**expected, "activated_at": activated_at.isoformat()}
        try:
            sealed = seal_json(
                receipt_path,
                payload,
                artifact_type="full_market_profile_claim_activation_receipt",
                sealed_at=activated_at,
            )
        except (OSError, SealingError) as exc:
            raise ResearchAllocationError(
                f"full-market profile claim receipt could not be sealed: {symbol}"
            ) from exc
        return payload, sealed.sha256
    try:
        sealed = verify_sealed(receipt_path)
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError(
            f"full-market profile claim receipt is invalid: {symbol}"
        ) from exc
    if (
        sealed.artifact_type != "full_market_profile_claim_activation_receipt"
        or not isinstance(payload, dict)
        or set(payload) != set(expected) | {"activated_at"}
        or any(payload.get(key) != value for key, value in expected.items())
    ):
        raise ResearchAllocationError(
            f"full-market profile claim receipt does not match its allocation: {symbol}"
        )
    receipt_at = _datetime(payload.get("activated_at"), "claim_receipt.activated_at")
    gate_at = _datetime(gate.get("activated_at"), "claim_gate.activated_at")
    if receipt_at < gate_at:
        raise ResearchAllocationError(
            f"full-market profile claim receipt predates its gate: {symbol}"
        )
    # ``activated_at`` is the first durable authorization event.  A crash may
    # happen before the queue's ``started_at`` projection, so a later retry
    # deliberately keeps this receipt timestamp while recording its real,
    # later task start time.
    if activated_at is not None and receipt_at > activated_at:
        raise ResearchAllocationError(
            f"full-market profile claim receipt is from the future: {symbol}"
        )
    return payload, sealed.sha256


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
        raise ResearchAllocationError(f"only the assigned agent can release profile task: {symbol}")
    if record.get("task_type") not in {
        "quick_profile",
        "targeted_followup",
        "scoped_research",
        "deep_research",
    }:
        raise ResearchAllocationError(
            f"task type cannot be released by profile workflow: {record.get('task_type')}"
        )

    if _requires_authenticated_profile_stage_claim(
        record,
        base=base,
        repository_root=base.parent.parent,
    ):
        try:
            released, _ = release_profile_stage_attempt(
                root=base,
                queue_record=record,
                agent=agent_name,
                failure_reason=reason,
                released_at=released_at,
            )
        except ProfileStageClaimError as exc:
            raise ResearchAllocationError(str(exc)) from exc
        write_jsonl(
            queue_path,
            [released if item.get("symbol") == symbol else item for item in queue],
        )
        return released

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


def _targeted_locked_calibration_remediation(
    queue_record: Mapping[str, Any],
    *,
    screen_record: Mapping[str, Any],
    repository_root: Path,
    symbol: str,
) -> dict[str, Any] | None:
    queue_binding = queue_record.get(LOCKED_CALIBRATION_REMEDIATION_FIELD)
    screen_binding = screen_record.get(LOCKED_CALIBRATION_REMEDIATION_FIELD)
    if queue_binding is None and screen_binding is None:
        return None
    if queue_binding != screen_binding:
        raise ResearchAllocationError(
            f"locked calibration remediation projection is inconsistent: {symbol}"
        )
    return _validate_locked_calibration_remediation_binding(
        queue_binding,
        repository_root=repository_root,
        symbol=symbol,
    )


def _validate_locked_calibration_remediation_binding(
    value: Any,
    *,
    repository_root: Path,
    symbol: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != LOCKED_CALIBRATION_REMEDIATION_KEYS:
        raise ResearchAllocationError(
            f"locked calibration remediation binding fields are invalid: {symbol}"
        )
    binding = dict(value)
    evidence_ids = _text_array(
        binding.get("evidence_ids"),
        "locked_calibration.evidence_ids",
        allow_empty=False,
    )
    if (
        binding.get("schema_version") != 1
        or binding.get("workflow") != "manager_screen_full_market_allocation_v3"
        or binding.get("remediation") != "targeted_remediation_candidate"
        or binding.get("resolved_work_sha256") is not None
        or binding.get("revisit_triggers") != []
        or not isinstance(binding.get("run_id"), str)
        or not isinstance(binding.get("decisive_question"), str)
        or not binding["decisive_question"].strip()
        or binding.get("evidence_ids") != evidence_ids
    ):
        raise ResearchAllocationError(
            f"locked calibration targeted remediation is invalid: {symbol}"
        )
    for field in (
        "allocation_result_sha256",
        "locked_calibration_case_sha256",
        "calibration_result_sha256",
        "calibration_review_sha256",
        "calibration_adjudication_sha256",
    ):
        if not isinstance(binding.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", str(binding.get(field))
        ):
            raise ResearchAllocationError(
                f"locked calibration remediation {field} is invalid: {symbol}"
            )
    relative = _text(
        binding.get("allocation_result_path"),
        "locked_calibration.allocation_result_path",
    )
    result_path = (repository_root / relative).resolve()
    try:
        result_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            f"locked calibration allocation result escapes repository: {symbol}"
        ) from exc
    relative_parts = Path(relative).parts
    try:
        manager_screen_index = relative_parts.index("manager-screen")
    except ValueError as exc:
        raise ResearchAllocationError(
            f"locked calibration allocation result path is invalid: {symbol}"
        ) from exc
    coverage_root = repository_root.joinpath(*relative_parts[:manager_screen_index])
    from .manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        verify_manager_screen_full_market_allocation_v3_result,
    )

    try:
        verified = verify_manager_screen_full_market_allocation_v3_result(
            root=coverage_root,
            run_id=str(binding["run_id"]),
        )
        result_seal = verify_sealed(result_path)
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (
        ManagerScreenFullMarketAllocationV3Error,
        OSError,
        json.JSONDecodeError,
        SealingError,
    ) as exc:
        raise ResearchAllocationError(
            f"locked calibration allocation result is invalid: {symbol}"
        ) from exc
    if (
        result_seal.artifact_type != "manager_screen_full_market_allocation_v3_result"
        or result_seal.sha256 != binding["allocation_result_sha256"]
        or verified.get("result_sha256") != result_seal.sha256
        or result.get("run_id") != binding["run_id"]
        or result.get("recorded_at") != binding["recorded_at"]
    ):
        raise ResearchAllocationError(
            f"locked calibration allocation result binding is invalid: {symbol}"
        )
    remediations = [
        item
        for item in result.get("locked_calibration_remediations") or []
        if isinstance(item, Mapping) and item.get("symbol") == symbol
    ]
    if len(remediations) != 1:
        raise ResearchAllocationError(
            f"locked calibration allocation result lacks one remediation: {symbol}"
        )
    remediation = remediations[0]
    expected_remediation = {
        "locked_calibration_case_sha256": binding["locked_calibration_case_sha256"],
        "remediation": binding["remediation"],
        "reason": binding["reason"],
        "resolved_work_sha256": binding["resolved_work_sha256"],
        "decisive_question": binding["decisive_question"],
        "evidence_ids": binding["evidence_ids"],
        "revisit_triggers": binding["revisit_triggers"],
    }
    if any(remediation.get(key) != expected for key, expected in expected_remediation.items()):
        raise ResearchAllocationError(
            f"locked calibration remediation drifted from allocation result: {symbol}"
        )
    packet_path = (repository_root / _text(result.get("packet_path"), "packet_path")).resolve()
    try:
        packet_seal = verify_sealed(packet_path)
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError(
            f"locked calibration allocation packet is invalid: {symbol}"
        ) from exc
    if (
        packet_seal.artifact_type != "manager_screen_full_market_allocation_v3_packet"
        or packet_seal.sha256 != result.get("packet_sha256")
    ):
        raise ResearchAllocationError(
            f"locked calibration allocation packet binding is invalid: {symbol}"
        )
    cases = [
        item
        for item in packet.get("locked_calibration_cases") or []
        if isinstance(item, Mapping) and item.get("symbol") == symbol
    ]
    if (
        len(cases) != 1
        or cases[0].get("locked_calibration_case_sha256")
        != binding["locked_calibration_case_sha256"]
    ):
        raise ResearchAllocationError(
            f"locked calibration allocation packet lacks the bound case: {symbol}"
        )
    calibration = cases[0].get("calibration_material_error")
    expected_calibration = {
        "calibration_result_path": binding["calibration_result_path"],
        "calibration_result_sha256": binding["calibration_result_sha256"],
        "calibration_result_sealed_at": binding["calibration_result_sealed_at"],
        "review_sha256": binding["calibration_review_sha256"],
        "adjudication_sha256": binding["calibration_adjudication_sha256"],
    }
    if not isinstance(calibration, Mapping) or any(
        calibration.get(key) != expected for key, expected in expected_calibration.items()
    ):
        raise ResearchAllocationError(f"locked calibration evidence binding is invalid: {symbol}")
    manager = result.get("manager")
    if not isinstance(manager, Mapping):
        raise ResearchAllocationError(f"locked calibration allocation manager is missing: {symbol}")
    return {
        "binding": binding,
        "manager_agent": _text(manager.get("agent"), "locked_calibration.manager"),
        "decisive_question": binding["decisive_question"].strip(),
        "evidence_ids": evidence_ids,
    }


@serialized_coverage_write
def approve_targeted_followup(
    *,
    root: str | Path,
    symbol: str,
    manager: str,
    reason: str,
    policy: Mapping[str, Any],
    approved_at: dt.datetime,
    policy_path: str | Path = "policies/research-allocation.json",
    decisive_question: str | None = None,
    evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Explicitly purchase one targeted-followup budget after analyst work."""

    _require_aware_datetime(approved_at, "approved_at")
    if not re.fullmatch(r"CN:[0-9]{6}", symbol):
        raise ResearchAllocationError("approval symbol is invalid")
    manager_name = _text(manager, "manager")
    approval_reason = _text(reason, "reason")
    base = Path(root)
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    queued = _one_record(queue, symbol, "research queue")
    screen = _one_record(screening, symbol, "screening")
    repository_root = base.parent.parent
    if _canonical_profile_adjudication_paths(base=base, symbol=symbol):
        raise ResearchAllocationError(
            "a sealed profile adjudication forbids targeted-followup budget "
            f"until a sealed successor workflow exists: {symbol}"
        )
    cycle = _text(queued.get("profile_cycle_id"), "profile_cycle_id")
    locked_remediation = _targeted_locked_calibration_remediation(
        queued,
        screen_record=screen,
        repository_root=repository_root,
        symbol=symbol,
    )
    if locked_remediation is not None:
        submitted_question = (
            locked_remediation["decisive_question"]
            if decisive_question is None
            else _text(
                decisive_question,
                "locked_calibration.decisive_question",
            )
        )
        submitted_evidence = (
            locked_remediation["evidence_ids"]
            if evidence_ids is None
            else _text_array(
                evidence_ids,
                "locked_calibration.evidence_ids",
                allow_empty=False,
            )
        )
        if (
            submitted_question != locked_remediation["decisive_question"]
            or submitted_evidence != locked_remediation["evidence_ids"]
        ):
            raise ResearchAllocationError(
                "targeted-followup approval must submit the sealed locked-calibration "
                f"research brief: {symbol}"
            )
    elif decisive_question is not None or evidence_ids is not None:
        raise ResearchAllocationError(
            "targeted-followup research brief is only accepted for locked calibration "
            f"remediation: {symbol}"
        )
    legacy_pending_followup = bool(
        queued.get("task_type") == "targeted_followup"
        and queued.get("status") == "pending"
        and queued.get("preceding_stage") in {"quick_profile", "scoped_research"}
        and screen.get("decision") == "targeted_followup"
        and not queued.get("targeted_followup_approval_path")
        and not queued.get("targeted_followup_approval_sha256")
        and _latest_cycle_stage_completion(
            queued,
            base=base,
            stage="targeted_followup",
            cycle=cycle,
        )
        is None
    )
    legacy_profile_row: Mapping[str, Any] | None = None
    if legacy_pending_followup:
        preceding_stage = str(queued["preceding_stage"])
        legacy_profile_row = _profile_comparison_row(
            queued,
            ordinal=1,
            cycle=_text(queued.get("profile_cycle_id"), "profile_cycle_id"),
            stage=preceding_stage,
            base=base,
            repository_root=repository_root,
        )
        if legacy_profile_row.get("current_next_stage") not in {
            "targeted_followup",
            "targeted_followup_candidate",
        }:
            raise ResearchAllocationError(
                "legacy targeted followup is not backed by a sealed analyst "
                f"recommendation: {symbol}"
            )
    research_agent = (
        legacy_profile_row.get("research_agent")
        if legacy_profile_row is not None
        else queued.get("assigned_agent")
    )
    if research_agent == manager_name:
        raise ResearchAllocationError(
            "targeted-followup manager must be independent of the research agent"
        )
    manager_screen_run_id = _manager_screen_run_id_for_record(
        queued,
        context="targeted-followup approval",
    )
    if isinstance(manager_screen_run_id, str):
        if _requires_funded_full_market_grant(queued):
            _verify_funded_full_market_profile_grant(
                queue_record=queued,
                screen_record=screen,
                root=base,
                repository_root=repository_root,
                symbol=symbol,
                expected_cycle_id=cycle,
                required=True,
                context="targeted-followup approval",
            )
        expected_manager = (
            locked_remediation["manager_agent"]
            if locked_remediation is not None
            else _investment_manager_for_cohort(
                [queued],
                repository_root=repository_root,
            )
        )
        if expected_manager is None or manager_name != expected_manager:
            raise ResearchAllocationError(
                "targeted-followup approval must come from the original "
                f"investment manager: expected {expected_manager}"
            )
    approval_path = (
        base
        / "profiles"
        / cycle
        / "targeted-followup-approvals"
        / f"{symbol.split(':', 1)[1]}.json"
    )
    decline_path = (
        base / "profiles" / cycle / "targeted-followup-declines" / f"{symbol.split(':', 1)[1]}.json"
    )
    if (
        queued.get("targeted_followup_decline_path") is not None
        or queued.get("targeted_followup_decline_sha256") is not None
        or decline_path.exists()
        or decline_path.with_name(f"{decline_path.name}.seal.json").exists()
    ):
        raise ResearchAllocationError(f"targeted followup already has a sealed decline: {symbol}")
    if (
        approval_path.exists()
        or approval_path.with_name(f"{approval_path.name}.seal.json").exists()
    ):
        approval, approval_seal = _load_targeted_followup_approval(
            approval_path,
            repository_root=repository_root,
        )
        if (
            approval["symbol"] != symbol
            or approval["manager"] != manager_name
            or approval["reason"] != approval_reason
            or approval.get("locked_calibration_remediation")
            != (locked_remediation["binding"] if locked_remediation is not None else None)
        ):
            if (
                queued.get("status") != "completed"
                or screen.get("decision") != "targeted_followup_candidate"
                or queued.get("task_type") not in {"quick_profile", "scoped_research"}
            ):
                raise ResearchAllocationError(
                    f"targeted followup is not awaiting manager approval: {symbol}"
                )
            raise ResearchAllocationError(
                f"sealed targeted-followup approval conflicts with request: {symbol}"
            )
        if isinstance(manager_screen_run_id, str):
            capacity = _stage_capacity(policy, "targeted_followup")
            if capacity is None:
                raise ResearchAllocationError("targeted_followup run capacity policy is invalid")
            _enforce_targeted_followup_approval_capacity(
                base=base,
                repository_root=repository_root,
                manager_screen_run_id=manager_screen_run_id,
                capacity=capacity,
                symbol=symbol,
                expected_path=approval_path,
                expected_sha256=approval_seal.sha256,
            )
        return _materialize_targeted_followup_approval(
            base=base,
            queue=queue,
            screening=screening,
            approval=approval,
            approval_path=approval_path,
            approval_sha256=approval_seal.sha256,
            repository_root=repository_root,
            idempotent=True,
        )
    if not legacy_pending_followup and (
        queued.get("status") != "completed"
        or screen.get("decision") != "targeted_followup_candidate"
        or queued.get("task_type") not in {"quick_profile", "scoped_research"}
    ):
        raise ResearchAllocationError(
            f"targeted followup is not awaiting manager approval: {symbol}"
        )
    if isinstance(manager_screen_run_id, str):
        capacity = _stage_capacity(policy, "targeted_followup")
        if capacity is None:
            raise ResearchAllocationError("targeted_followup run capacity policy is invalid")
        _enforce_targeted_followup_approval_capacity(
            base=base,
            repository_root=repository_root,
            manager_screen_run_id=manager_screen_run_id,
            capacity=capacity,
            symbol=symbol,
        )
    policy_binding = _research_policy_binding(
        repository_root=repository_root,
        policy=policy,
        policy_path=policy_path,
    )
    if isinstance(manager_screen_run_id, str):
        _bind_research_policy_for_run(
            base=base,
            run_id=manager_screen_run_id,
            policy_binding=policy_binding,
            bound_at=approved_at,
        )
    approval = {
        "schema_version": 2 if locked_remediation is not None else 1,
        "symbol": symbol,
        "profile_cycle_id": cycle,
        "manager_screen_run_id": manager_screen_run_id,
        "approved_at": approved_at.isoformat(),
        "manager": manager_name,
        "reason": approval_reason,
        "preceding_stage": (
            str(queued["preceding_stage"]) if legacy_pending_followup else str(queued["task_type"])
        ),
        "next_stage": "targeted_followup",
        "effort_budget_hours": _effort_budget(policy, "targeted_followup"),
        "stop_conditions": _stop_conditions("targeted_followup"),
        "research_policy": policy_binding,
        "portfolio_action": None,
    }
    if locked_remediation is not None:
        approval["locked_calibration_remediation"] = locked_remediation["binding"]
    approval_seal = seal_json(
        approval_path,
        approval,
        artifact_type="targeted_followup_approval",
        sealed_at=approved_at,
    )
    return _materialize_targeted_followup_approval(
        base=base,
        queue=queue,
        screening=screening,
        approval=approval,
        approval_path=approval_path,
        approval_sha256=approval_seal.sha256,
        repository_root=repository_root,
        idempotent=False,
    )


def _load_targeted_followup_approval(
    approval_path: Path,
    *,
    repository_root: Path,
) -> tuple[dict[str, Any], Any]:
    try:
        sealed = verify_sealed(approval_path)
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError(
            f"targeted-followup approval is not validly sealed: {approval_path}"
        ) from exc
    if sealed.artifact_type != "targeted_followup_approval":
        raise ResearchAllocationError("targeted-followup approval has the wrong artifact type")
    base_keys = {
        "schema_version",
        "symbol",
        "profile_cycle_id",
        "manager_screen_run_id",
        "approved_at",
        "manager",
        "reason",
        "preceding_stage",
        "next_stage",
        "effort_budget_hours",
        "stop_conditions",
        "research_policy",
        "portfolio_action",
    }
    schema_version = approval.get("schema_version") if isinstance(approval, dict) else None
    expected_keys = (
        base_keys | {"locked_calibration_remediation"} if schema_version == 2 else base_keys
    )
    if (
        not isinstance(approval, dict)
        or set(approval) != expected_keys
        or schema_version not in {1, 2}
        or approval.get("next_stage") != "targeted_followup"
        or approval.get("portfolio_action") is not None
    ):
        raise ResearchAllocationError("targeted-followup approval fields do not match its schema")
    if schema_version == 2:
        locked = _validate_locked_calibration_remediation_binding(
            approval.get("locked_calibration_remediation"),
            repository_root=repository_root,
            symbol=_text(approval.get("symbol"), "targeted_followup.symbol"),
        )
        if approval.get("manager") != locked["manager_agent"]:
            raise ResearchAllocationError(
                "targeted-followup approval manager does not match locked remediation"
            )
    _normalize_research_policy_binding(approval.get("research_policy"))
    try:
        approval_path.resolve().relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError("targeted-followup approval escapes repository root") from exc
    return approval, sealed


def _targeted_followup_task_has_valid_approval(
    queue_record: Mapping[str, Any],
    *,
    repository_root: Path,
) -> bool:
    try:
        _validate_targeted_followup_task_approval(
            queue_record,
            repository_root=repository_root,
        )
    except ResearchAllocationError:
        return False
    return True


def _validate_targeted_followup_task_approval(
    queue_record: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    """Fail closed unless a targeted task binds one valid manager approval."""

    if queue_record.get("task_type") != "targeted_followup":
        return
    symbol = _text(queue_record.get("symbol"), "research_queue.symbol")
    relative_path = queue_record.get("targeted_followup_approval_path")
    expected_sha256 = queue_record.get("targeted_followup_approval_sha256")
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or not isinstance(expected_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
    ):
        raise ResearchAllocationError(
            f"targeted followup is missing explicit manager approval: {symbol}"
        )
    approval_path = (repository_root / relative_path).resolve()
    try:
        approval_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            f"targeted-followup approval escapes repository root: {symbol}"
        ) from exc
    approval, sealed = _load_targeted_followup_approval(
        approval_path,
        repository_root=repository_root,
    )
    locked_remediation = approval.get("locked_calibration_remediation")
    if isinstance(locked_remediation, Mapping):
        if (
            queue_record.get(LOCKED_CALIBRATION_REMEDIATION_FIELD) != locked_remediation
            or queue_record.get("decisive_question") != locked_remediation.get("decisive_question")
            or list(queue_record.get("evidence_ids") or [])
            != list(locked_remediation.get("evidence_ids") or [])
        ):
            raise ResearchAllocationError(
                f"targeted-followup task lost its locked calibration brief: {symbol}"
            )
    policy = approval["research_policy"]
    history = queue_record.get("stage_history")
    if (
        sealed.sha256 != expected_sha256
        or approval["symbol"] != symbol
        or approval["profile_cycle_id"] != queue_record.get("profile_cycle_id")
        or approval["manager_screen_run_id"] != queue_record.get("manager_screen_run_id")
        or approval["preceding_stage"] != queue_record.get("preceding_stage")
        or float(approval["effort_budget_hours"])
        != float(queue_record.get("effort_budget_hours", 0.0))
        or queue_record.get("research_policy_path") != policy["path"]
        or queue_record.get("research_policy_file_sha256") != policy["file_sha256"]
        or queue_record.get("research_policy_payload_sha256") != policy["payload_sha256"]
        or not isinstance(history, list)
        or not any(
            isinstance(item, Mapping)
            and item.get("stage") == "targeted_followup_approval"
            and item.get("status") == "completed"
            and item.get("approval_path") == relative_path
            and item.get("approval_sha256") == expected_sha256
            for item in history
        )
    ):
        raise ResearchAllocationError(
            f"targeted-followup task does not match its sealed approval: {symbol}"
        )


def _validate_profile_claim_stage_authorization(
    queue_record: Mapping[str, Any],
    *,
    base: Path,
    repository_root: Path,
) -> None:
    """Require the immutable authorization that purchased the queued stage."""

    stage = queue_record.get("task_type")
    symbol = _text(queue_record.get("symbol"), "research_queue.symbol")
    if _canonical_profile_adjudication_paths(base=base, symbol=symbol):
        raise ResearchAllocationError(
            "a sealed profile adjudication forbids new profile claims until "
            f"a sealed successor workflow exists: {symbol}"
        )
    _profile_adjudication_for_profile_row(
        queue_record,
        symbol=symbol,
        repository_root=repository_root,
        base=base,
    )
    if stage == "targeted_followup":
        _validate_targeted_followup_task_approval(
            queue_record,
            repository_root=repository_root,
        )
        return
    configs = {
        "scoped_research": {
            "preceding_stage": "quick_profile",
            "binding_field": "profile_quick_selection_path",
            "binding_sha_field": "profile_quick_selection_sha256",
            "selection_name": "quick-profile-selection.json",
            "comparison_name": "quick-profile-comparison.json",
        },
        "deep_research": {
            "preceding_stage": "scoped_research",
            "binding_field": "profile_scoped_selection_path",
            "binding_sha_field": "profile_scoped_selection_sha256",
            "selection_name": "scoped-research-selection.json",
            "comparison_name": "scoped-research-comparison.json",
        },
    }
    config = configs.get(stage)
    if config is None:
        return

    cycle = _text(queue_record.get("profile_cycle_id"), "profile_cycle_id")
    if not CYCLE_RE.fullmatch(cycle):
        raise ResearchAllocationError(f"profile stage claim has an invalid cycle: {symbol}")
    preceding_stage = config["preceding_stage"]
    if queue_record.get("preceding_stage") != preceding_stage:
        raise ResearchAllocationError(f"{stage} claim does not follow {preceding_stage}: {symbol}")
    binding_field = config["binding_field"]
    relative = queue_record.get(binding_field)
    if not isinstance(relative, str) or not relative:
        raise ResearchAllocationError(
            f"{stage} claim is missing its sealed {preceding_stage} selection: {symbol}"
        )
    selection_path = (repository_root / relative).resolve()
    expected_path = (base / "profiles" / cycle / config["selection_name"]).resolve()
    try:
        selection_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            f"{stage} selection escapes repository root: {symbol}"
        ) from exc
    if selection_path != expected_path:
        raise ResearchAllocationError(
            f"{stage} claim does not bind its canonical sealed selection: {symbol}"
        )
    try:
        sealed = verify_sealed(selection_path)
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError(
            f"{stage} claim references an invalid sealed selection: {symbol}"
        ) from exc
    _validate_profile_selection_payload(
        payload,
        artifact_type=sealed.artifact_type,
        cycle=cycle,
        stage=preceding_stage,
        next_stage=str(stage),
    )
    _validate_profile_stage_selection_semantics(
        payload,
        base=base,
        repository_root=repository_root,
        cycle=cycle,
        stage=preceding_stage,
        next_stage=str(stage),
        comparison_name=config["comparison_name"],
    )

    screen = _one_record(read_jsonl(base / SCREENING_FILE), symbol, "screening")
    expected_evidence = {
        f"stage_selection:{relative}",
        f"stage_selection_sha256:{sealed.sha256}",
    }
    screen_evidence = screen.get("evidence")
    screen_proves_sha = bool(
        isinstance(screen_evidence, list) and expected_evidence.issubset(set(screen_evidence))
    )
    bound_sha256 = queue_record.get(config["binding_sha_field"])
    legacy_sha_binding = bound_sha256 is None and screen_proves_sha
    if not (
        legacy_sha_binding
        or (isinstance(bound_sha256, str) and bound_sha256 == sealed.sha256 and screen_proves_sha)
    ):
        raise ResearchAllocationError(
            f"{stage} claim does not match its immutable selection SHA binding: {symbol}"
        )

    queue_run_id = queue_record.get("manager_screen_run_id")
    selection_run_id = payload.get("manager_screen_run_id")
    legacy_run_omission = bool(
        selection_run_id is None
        and "manager_screen_run_id" not in payload
        and "research_policy" not in payload
    )
    predecessor_requires_claim = not legacy_run_omission
    if selection_run_id != queue_run_id and not legacy_run_omission:
        raise ResearchAllocationError(
            f"{stage} selection belongs to a different manager-screen run: {symbol}"
        )
    matching = [
        row
        for row in payload["ranking"]
        if isinstance(row, Mapping) and row.get("symbol") == symbol
    ]
    if len(matching) != 1 or matching[0].get("selected") is not True:
        raise ResearchAllocationError(
            f"sealed {preceding_stage} selection did not purchase {stage}: {symbol}"
        )
    sealed_budget = payload.get("next_stage_effort_budget_hours")
    queue_budget = queue_record.get("effort_budget_hours")
    if (
        isinstance(sealed_budget, bool)
        or not isinstance(sealed_budget, (int, float))
        or isinstance(queue_budget, bool)
        or not isinstance(queue_budget, (int, float))
        or float(queue_budget) != float(sealed_budget)
    ):
        raise ResearchAllocationError(
            f"{stage} effort budget does not match its sealed selection: {symbol}"
        )
    if (
        _latest_cycle_stage_authorization_completion(
            queue_record,
            base=base,
            stage=preceding_stage,
            cycle=cycle,
            require_claim=predecessor_requires_claim,
        )
        is None
    ):
        raise ResearchAllocationError(
            f"{stage} claim lacks completed {preceding_stage} history: {symbol}"
        )
    if (
        _latest_cycle_stage_authorization_completion(
            queue_record,
            base=base,
            stage=str(stage),
            cycle=cycle,
            require_claim=predecessor_requires_claim,
        )
        is not None
    ):
        raise ResearchAllocationError(f"completed profile stage cannot be claimed again: {symbol}")


def _validate_profile_stage_selection_semantics(
    payload: Mapping[str, Any],
    *,
    base: Path,
    repository_root: Path,
    cycle: str,
    stage: str,
    next_stage: str,
    comparison_name: str,
) -> None:
    """Verify modern comparison/policy bindings while accepting old score selections."""

    modern_fields = {
        "comparison_path",
        "comparison_sha256",
        "predecessor_selection_sha256",
        "agent_decision",
        "research_policy",
    }
    present = modern_fields & set(payload)
    run_bound = isinstance(payload.get("manager_screen_run_id"), str)
    if not present and not run_bound:
        return
    required = {
        "comparison_path",
        "comparison_sha256",
        "predecessor_selection_path",
        "predecessor_selection_sha256",
        "agent_decision",
        "research_policy",
    }
    if not required.issubset(payload):
        raise ResearchAllocationError(
            f"sealed {stage} selection has an incomplete modern authorization chain"
        )
    comparison_relative = _text(payload.get("comparison_path"), "comparison_path")
    comparison_sha256 = _text(payload.get("comparison_sha256"), "comparison_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", comparison_sha256):
        raise ResearchAllocationError(f"sealed {stage} selection comparison SHA is invalid")
    comparison_path = (repository_root / comparison_relative).resolve()
    canonical_comparison = (base / "profiles" / cycle / comparison_name).resolve()
    try:
        comparison_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            f"sealed {stage} selection comparison escapes repository root"
        ) from exc
    if comparison_path != canonical_comparison:
        raise ResearchAllocationError(f"sealed {stage} selection comparison path is not canonical")
    try:
        comparison_seal = verify_sealed(comparison_path)
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError(f"sealed {stage} selection comparison is invalid") from exc
    agent_decision = payload.get("agent_decision")
    if (
        comparison_seal.artifact_type != f"{stage}_comparison_packet"
        or comparison_seal.sha256 != comparison_sha256
        or not isinstance(comparison, Mapping)
        or comparison.get("cycle_id") != cycle
        or comparison.get("evaluated_stage") != stage
        or comparison.get("next_stage") != next_stage
        or comparison.get("predecessor_selection_path") != payload.get("predecessor_selection_path")
        or comparison.get("predecessor_selection_sha256")
        != payload.get("predecessor_selection_sha256")
        or not isinstance(agent_decision, Mapping)
        or agent_decision.get("cycle_id") != cycle
        or agent_decision.get("evaluated_stage") != stage
        or agent_decision.get("comparison_sha256") != comparison_sha256
    ):
        raise ResearchAllocationError(
            f"sealed {stage} selection does not match its comparison chain"
        )

    policy = _normalize_research_policy_binding(payload.get("research_policy"))
    run_id = payload.get("manager_screen_run_id")
    if isinstance(run_id, str):
        _verify_run_research_policy_snapshot(
            base=base,
            run_id=run_id,
            expected_policy=policy,
            context=f"sealed {stage} selection",
        )
        return

    # A modern selection without manager-run provenance predates the run-level
    # snapshot contract.  Keep its legacy live-file validation, but never use
    # this mutable fallback for a run-bound authorization.
    policy_path = (repository_root / policy["path"]).resolve()
    try:
        policy_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            f"sealed {stage} selection policy escapes repository root"
        ) from exc
    if not policy_path.is_file():
        raise ResearchAllocationError(f"sealed {stage} selection policy is missing")
    loaded_policy = load_policy(policy_path)
    if (
        loaded_policy.policy_id != policy["policy_id"]
        or loaded_policy.version != policy["version"]
        or hashlib.sha256(policy_path.read_bytes()).hexdigest() != policy["file_sha256"]
        or hashlib.sha256(canonical_json_bytes(dict(loaded_policy.payload))).hexdigest()
        != policy["payload_sha256"]
    ):
        raise ResearchAllocationError(f"sealed {stage} selection policy binding is invalid")


def _enforce_targeted_followup_approval_capacity(
    *,
    base: Path,
    repository_root: Path,
    manager_screen_run_id: str,
    capacity: int,
    symbol: str,
    expected_path: Path | None = None,
    expected_sha256: str | None = None,
) -> None:
    """Conserve purchased follow-up budgets from the immutable approval ledger."""

    ledger = _targeted_followup_approval_ledger(
        base=base,
        repository_root=repository_root,
        manager_screen_run_id=manager_screen_run_id,
    )
    existing = ledger.get(symbol)
    if expected_path is not None or expected_sha256 is not None:
        if (
            expected_path is None
            or expected_sha256 is None
            or existing is None
            or existing["path"] != expected_path.resolve()
            or existing["sha256"] != expected_sha256
        ):
            raise ResearchAllocationError(
                f"targeted-followup approval ledger does not bind replay: {symbol}"
            )
    elif existing is not None:
        raise ResearchAllocationError(
            f"targeted-followup approval ledger already contains symbol: {symbol}"
        )
    projected = len(ledger) + (0 if existing is not None else 1)
    if projected > capacity:
        raise ResearchAllocationError(
            "targeted_followup run capacity is exhausted: "
            f"{len(ledger)} sealed + {0 if existing is not None else 1} requested "
            f"> {capacity}"
        )


def _targeted_followup_approval_ledger(
    *,
    base: Path,
    repository_root: Path,
    manager_screen_run_id: str,
) -> dict[str, dict[str, Any]]:
    profiles_root = base / "profiles"
    ledger: dict[str, dict[str, Any]] = {}
    approval_dirs = (
        sorted(profiles_root.rglob("targeted-followup-approvals")) if profiles_root.is_dir() else []
    )
    for approval_dir in approval_dirs:
        if not approval_dir.is_dir():
            continue
        payload_paths = {
            path.resolve()
            for path in approval_dir.glob("*.json")
            if not path.name.endswith(".seal.json")
        }
        sealed_payload_paths = {
            path.with_name(path.name[: -len(".seal.json")]).resolve()
            for path in approval_dir.glob("*.json.seal.json")
        }
        if payload_paths != sealed_payload_paths:
            raise ResearchAllocationError(
                "targeted-followup approval ledger contains a half-sealed artifact"
            )
        for approval_path in sorted(payload_paths):
            approval, sealed = _load_targeted_followup_approval(
                approval_path,
                repository_root=repository_root,
            )
            approval_symbol = approval.get("symbol")
            cycle = approval.get("profile_cycle_id")
            run_id = approval.get("manager_screen_run_id")
            if (
                not isinstance(approval_symbol, str)
                or not re.fullmatch(r"CN:[0-9]{6}", approval_symbol)
                or not isinstance(cycle, str)
                or not cycle
                or (run_id is not None and (not isinstance(run_id, str) or not run_id))
            ):
                raise ResearchAllocationError(
                    "targeted-followup approval ledger identity is invalid"
                )
            canonical_path = (
                profiles_root
                / cycle
                / "targeted-followup-approvals"
                / f"{approval_symbol.split(':', 1)[1]}.json"
            ).resolve()
            if approval_path != canonical_path:
                raise ResearchAllocationError(
                    "targeted-followup approval ledger path does not match identity"
                )
            if run_id != manager_screen_run_id:
                continue
            if approval_symbol in ledger:
                raise ResearchAllocationError(
                    "targeted-followup approval ledger contains duplicate run symbols"
                )
            ledger[approval_symbol] = {
                "path": approval_path,
                "sha256": sealed.sha256,
            }
    inherited = _sealed_inherited_stage_commitment_ledger(
        base=base,
        repository_root=repository_root,
        manager_screen_run_id=manager_screen_run_id,
        stage="targeted_followup",
    )
    for symbol, commitment in inherited.items():
        ledger.setdefault(
            symbol,
            {
                "path": (repository_root / commitment["selection_path"]).resolve(),
                "sha256": commitment["selection_sha256"],
            },
        )
    return ledger


def _materialize_targeted_followup_approval(
    *,
    base: Path,
    queue: list[dict[str, Any]],
    screening: list[dict[str, Any]],
    approval: Mapping[str, Any],
    approval_path: Path,
    approval_sha256: str,
    repository_root: Path,
    idempotent: bool,
) -> dict[str, Any]:
    symbol = str(approval["symbol"])
    queued = dict(_one_record(queue, symbol, "research queue"))
    screen = dict(_one_record(screening, symbol, "screening"))
    locked_remediation = approval.get("locked_calibration_remediation")
    relative = approval_path.relative_to(repository_root).as_posix()
    history = list(queued.get("stage_history") or [])
    if not any(
        item.get("approval_sha256") == approval_sha256
        for item in history
        if isinstance(item, Mapping)
    ):
        history.append(
            {
                "stage": "targeted_followup_approval",
                "status": "completed",
                "started_at": None,
                "finished_at": approval["approved_at"],
                "agent": approval["manager"],
                "reason": approval["reason"],
                "next_stage": "targeted_followup",
                "approval_path": relative,
                "approval_sha256": approval_sha256,
                **(
                    {
                        "locked_calibration_case_sha256": locked_remediation[
                            "locked_calibration_case_sha256"
                        ]
                    }
                    if isinstance(locked_remediation, Mapping)
                    else {}
                ),
            }
        )
    base_state = bool(
        queued.get("task_type") == approval["preceding_stage"]
        and queued.get("status") == "completed"
    )
    later_state = bool(
        queued.get("task_type") == "targeted_followup"
        or _latest_cycle_stage_completion(
            queued,
            base=base,
            stage="targeted_followup",
            cycle=_text(approval.get("profile_cycle_id"), "profile_cycle_id"),
        )
        is not None
    )
    if (
        isinstance(locked_remediation, Mapping)
        and later_state
        and (
            queued.get(LOCKED_CALIBRATION_REMEDIATION_FIELD) != locked_remediation
            or queued.get("decisive_question") != locked_remediation.get("decisive_question")
            or list(queued.get("evidence_ids") or [])
            != list(locked_remediation.get("evidence_ids") or [])
        )
    ):
        raise ResearchAllocationError(
            f"sealed targeted-followup approval cannot repair a drifted locked brief: {symbol}"
        )
    if base_state:
        queued.update(
            {
                "task_type": "targeted_followup",
                "status": "pending",
                "reason": approval["reason"],
                "assigned_agent": None,
                "started_at": None,
                "finished_at": None,
                "failure_reason": None,
                "next_action": _next_action("targeted_followup", False),
                "preceding_stage": approval["preceding_stage"],
                "effort_budget_hours": approval["effort_budget_hours"],
                "stop_conditions": list(approval["stop_conditions"]),
                **(
                    {
                        "decisive_question": locked_remediation["decisive_question"],
                        "evidence_ids": list(locked_remediation["evidence_ids"]),
                    }
                    if isinstance(locked_remediation, Mapping)
                    else {}
                ),
            }
        )
    elif not later_state:
        raise ResearchAllocationError(
            f"sealed targeted-followup approval cannot repair queue state: {symbol}"
        )
    elif (
        queued.get("task_type") == "targeted_followup"
        and queued.get("status") == "pending"
        and not queued.get("targeted_followup_approval_path")
        and not queued.get("targeted_followup_approval_sha256")
    ):
        # A small number of tasks were materialized by the legacy evaluator
        # before explicit manager approval became mandatory.  Keep the sealed
        # analyst recommendation, but replace the mutable queue rationale with
        # the manager's explicit budget decision while adding the approval
        # ledger binding below.
        queued.update(
            {
                "reason": approval["reason"],
                "effort_budget_hours": approval["effort_budget_hours"],
                "stop_conditions": list(approval["stop_conditions"]),
            }
        )
    queued.update(
        {
            "targeted_followup_approval_path": relative,
            "targeted_followup_approval_sha256": approval_sha256,
            "research_policy_path": approval["research_policy"]["path"],
            "research_policy_file_sha256": approval["research_policy"]["file_sha256"],
            "research_policy_payload_sha256": approval["research_policy"]["payload_sha256"],
            "stage_history": history,
        }
    )
    evidence = (
        list(locked_remediation["evidence_ids"])
        if isinstance(locked_remediation, Mapping)
        else list(screen.get("evidence") or [])
    )
    approval_evidence = [
        f"targeted_followup_approval:{relative}",
        f"targeted_followup_approval_sha256:{approval_sha256}",
    ]
    if screen.get("decision") == "targeted_followup_candidate":
        screen.update(
            {
                "decision": "targeted_followup",
                "reason": approval["reason"],
                "next_action": _next_action("targeted_followup", False),
                **(
                    {
                        "decisive_question": locked_remediation["decisive_question"],
                        "evidence": list(locked_remediation["evidence_ids"]),
                    }
                    if isinstance(locked_remediation, Mapping)
                    else {}
                ),
            }
        )
    elif screen.get("decision") == "targeted_followup" and queued.get("status") == "pending":
        screen["reason"] = approval["reason"]
    screen["evidence"] = list(dict.fromkeys(evidence + approval_evidence))
    write_jsonl(
        base / RESEARCH_QUEUE_FILE,
        [queued if item.get("symbol") == symbol else item for item in queue],
    )
    write_jsonl(
        base / SCREENING_FILE,
        [screen if item.get("symbol") == symbol else item for item in screening],
    )
    return {
        "schema_version": 1,
        "symbol": symbol,
        "task_type": queued["task_type"],
        "status": queued["status"],
        "effort_budget_hours": queued.get("effort_budget_hours"),
        "approved_by": approval["manager"],
        "approved_at": approval["approved_at"],
        "approval_path": relative,
        "approval_sha256": approval_sha256,
        "research_policy": dict(approval["research_policy"]),
        "idempotent": idempotent,
        "portfolio_action": None,
    }


@serialized_coverage_write
def decline_targeted_followup(
    *,
    root: str | Path,
    symbol: str,
    manager: str,
    outcome: str,
    reason: str,
    restart_triggers: list[Mapping[str, Any]],
    declined_at: dt.datetime,
) -> dict[str, Any]:
    """Seal a manager decision not to purchase targeted-followup research.

    The decision is append-only and may close one legacy pending task that was
    materialized before explicit approvals became mandatory.  It never creates
    an approval ledger entry and therefore never consumes follow-up capacity.
    """

    _require_aware_datetime(declined_at, "declined_at")
    if not re.fullmatch(r"CN:[0-9]{6}", symbol):
        raise ResearchAllocationError("decline symbol is invalid")
    manager_name = _text(manager, "manager")
    terminal_outcome = _targeted_followup_decline_outcome(outcome)
    decline_reason = _text(reason, "reason")
    triggers = _normalize_reactivation_triggers(
        restart_triggers,
        outcome=terminal_outcome,
    )
    base = Path(root)
    repository_root = base.parent.parent
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    screening = read_jsonl(base / SCREENING_FILE)
    queued = _one_record(queue, symbol, "research queue")
    screen = _one_record(screening, symbol, "screening")
    if _canonical_profile_adjudication_paths(base=base, symbol=symbol):
        raise ResearchAllocationError(
            "a sealed profile adjudication forbids a targeted-followup decline "
            f"until a sealed successor workflow exists: {symbol}"
        )
    cycle = _text(queued.get("profile_cycle_id"), "profile_cycle_id")
    ticker = symbol.split(":", 1)[1]
    decline_path = base / "profiles" / cycle / "targeted-followup-declines" / f"{ticker}.json"
    approval_path = base / "profiles" / cycle / "targeted-followup-approvals" / f"{ticker}.json"
    if (
        queued.get("targeted_followup_approval_path") is not None
        or queued.get("targeted_followup_approval_sha256") is not None
        or approval_path.exists()
        or approval_path.with_name(f"{approval_path.name}.seal.json").exists()
    ):
        raise ResearchAllocationError(
            f"targeted followup already has an approval commitment: {symbol}"
        )
    if (
        queued.get("task_type") == "targeted_followup"
        and queued.get("status") == "completed"
    ) or (
        _latest_cycle_stage_completion(
            queued,
            base=base,
            stage="targeted_followup",
            cycle=cycle,
        )
        is not None
    ):
        raise ResearchAllocationError(f"completed targeted followup cannot be declined: {symbol}")

    decline_exists = (
        decline_path.exists() or decline_path.with_name(f"{decline_path.name}.seal.json").exists()
    )
    if decline_exists:
        decline, decline_seal = _load_or_complete_targeted_followup_decline(
            decline_path,
            repository_root=repository_root,
        )
        if (
            decline["symbol"] != symbol
            or decline["profile_cycle_id"] != cycle
            or decline["manager"] != manager_name
            or decline["outcome"] != terminal_outcome
            or decline["reason"] != decline_reason
            or decline["restart_triggers"] != triggers
        ):
            raise ResearchAllocationError(
                f"sealed targeted-followup decline conflicts with request: {symbol}"
            )
        recommendation = _targeted_followup_recommendation_binding(
            queued,
            base=base,
            repository_root=repository_root,
            legacy_auto_materialized=decline["legacy_auto_materialized"],
        )
        manager_binding = _targeted_followup_manager_binding(
            queued,
            screen=screen,
            symbol=symbol,
            manager=manager_name,
            root=base,
            repository_root=repository_root,
        )
        _validate_targeted_followup_decline_bindings(
            decline,
            recommendation=recommendation,
            manager_binding=manager_binding,
        )
        return _materialize_targeted_followup_decline(
            base=base,
            queue=queue,
            screening=screening,
            decline=decline,
            decline_path=decline_path,
            decline_sha256=decline_seal.sha256,
            repository_root=repository_root,
            idempotent=True,
        )

    state = _declinable_targeted_followup_state(queued, screen=screen)
    legacy_auto_materialized = state == "legacy_auto_materialized_pending"
    if legacy_auto_materialized and (
        _record_has_full_market_v3_profile_authority(queued)
        or _record_has_canonical_full_market_v3_profile_authority(
            queued,
            base=base,
            cycle=cycle,
        )
    ):
        raise ResearchAllocationError(
            "full-market-v3 profile work cannot use the legacy targeted-followup decline path"
        )
    recommendation = _targeted_followup_recommendation_binding(
        queued,
        base=base,
        repository_root=repository_root,
        legacy_auto_materialized=legacy_auto_materialized,
    )
    manager_binding = _targeted_followup_manager_binding(
        queued,
        screen=screen,
        symbol=symbol,
        manager=manager_name,
        root=base,
        repository_root=repository_root,
    )
    if recommendation["research_agent"] == manager_name:
        raise ResearchAllocationError(
            "targeted-followup decline manager must be independent of the research agent"
        )
    decline = {
        "schema_version": 1,
        "symbol": symbol,
        "profile_cycle_id": cycle,
        "declined_at": declined_at.isoformat(),
        "manager": manager_name,
        "budget_decision": "declined",
        "additional_budget_hours": 0.0,
        "outcome": terminal_outcome,
        "reason": decline_reason,
        "restart_triggers": triggers,
        "legacy_auto_materialized": legacy_auto_materialized,
        "manager_screen_binding": manager_binding,
        "analyst_recommendation": recommendation,
        "portfolio_action": None,
    }
    decline_seal = seal_json(
        decline_path,
        decline,
        artifact_type="targeted_followup_decline",
        sealed_at=declined_at,
    )
    return _materialize_targeted_followup_decline(
        base=base,
        queue=queue,
        screening=screening,
        decline=decline,
        decline_path=decline_path,
        decline_sha256=decline_seal.sha256,
        repository_root=repository_root,
        idempotent=False,
    )


def _declinable_targeted_followup_state(
    queued: Mapping[str, Any],
    *,
    screen: Mapping[str, Any],
) -> str:
    symbol = str(queued.get("symbol"))
    candidate = bool(
        queued.get("task_type") in {"quick_profile", "scoped_research"}
        and queued.get("status") == "completed"
        and screen.get("decision") == "targeted_followup_candidate"
    )
    attempts = queued.get("attempt_history")
    legacy_pending = bool(
        queued.get("task_type") == "targeted_followup"
        and queued.get("status") == "pending"
        and queued.get("preceding_stage") in {"quick_profile", "scoped_research"}
        and screen.get("decision") == "targeted_followup"
        and queued.get("assigned_agent") is None
        and queued.get("started_at") is None
        and queued.get("finished_at") is None
        and (attempts is None or attempts == [])
    )
    if candidate:
        return "analyst_candidate"
    if legacy_pending:
        return "legacy_auto_materialized_pending"
    raise ResearchAllocationError(
        "targeted followup decline requires an unstarted analyst candidate or "
        f"one unstarted legacy pending task: {symbol}"
    )


def _targeted_followup_recommendation_binding(
    queued: Mapping[str, Any],
    *,
    base: Path,
    repository_root: Path,
    legacy_auto_materialized: bool,
) -> dict[str, Any]:
    preceding_stage = (
        str(queued.get("preceding_stage"))
        if queued.get("task_type") == "targeted_followup"
        else str(queued.get("task_type"))
    )
    if preceding_stage not in {"quick_profile", "scoped_research"}:
        raise ResearchAllocationError(
            "targeted-followup recommendation has an invalid preceding stage"
        )
    history = queued.get("stage_history")
    matching_history = [
        item
        for item in (history if isinstance(history, list) else [])
        if isinstance(item, Mapping)
        and item.get("stage") == preceding_stage
        and item.get("status") == "completed"
        and isinstance(item.get("result_path"), str)
        and isinstance(item.get("evaluation_path"), str)
    ]
    if not matching_history:
        raise ResearchAllocationError(
            "targeted followup is not backed by a completed analyst recommendation"
        )
    recommendation_record = dict(queued)
    recommendation_record["stage_history"] = [dict(matching_history[-1])]
    if legacy_auto_materialized:
        # The compatibility path describes analyst work completed before a
        # manager-screen binding was grafted onto the pending evaluator task.
        # Authenticate the sealed same-cycle package itself; do not pretend it
        # had a claim contract that did not yet exist.
        recommendation_record.pop("manager_screen_run_id", None)
        for field in MANAGER_SCREEN_PROVENANCE_FIELDS:
            recommendation_record.pop(field, None)
    row = _profile_comparison_row(
        recommendation_record,
        ordinal=1,
        cycle=_text(queued.get("profile_cycle_id"), "profile_cycle_id"),
        stage=preceding_stage,
        base=base,
        repository_root=repository_root,
    )
    recommended_next_stage = row.get("current_next_stage")
    if recommended_next_stage not in {
        "targeted_followup",
        "targeted_followup_candidate",
    }:
        raise ResearchAllocationError(
            "sealed analyst evaluation does not recommend targeted followup"
        )
    profile_path = (repository_root / str(row["profile_path"])).resolve()
    evaluation_path = (repository_root / str(row["evaluation_path"])).resolve()
    for artifact_path in (profile_path, evaluation_path):
        try:
            artifact_path.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise ResearchAllocationError(
                "targeted-followup recommendation escapes repository root"
            ) from exc
    package = json.loads(profile_path.read_text(encoding="utf-8"))
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    if (
        evaluation.get("profile_path") != row["profile_path"]
        or evaluation.get("profile_sha256") != row["profile_sha256"]
    ):
        raise ResearchAllocationError("sealed analyst evaluation does not bind its profile package")
    package_binding = package.get("manager_screen_binding")
    full_market_binding = _requires_funded_full_market_grant(queued)
    expected_package_binding = {
        "result_path": queued.get(
            "manager_screen_allocation_result_path"
            if full_market_binding
            else "manager_screen_result_path"
        ),
        "result_sha256": queued.get(
            "manager_screen_allocation_result_sha256"
            if full_market_binding
            else "manager_screen_result_sha256"
        ),
        "decisive_question": queued.get("decisive_question"),
        "evidence_ids": list(queued.get("evidence_ids") or []),
    }
    if package_binding is None:
        if not legacy_auto_materialized:
            raise ResearchAllocationError(
                "current analyst candidate is missing its manager-screen binding"
            )
        manager_binding_mode = "legacy_queue_sealed_result"
    elif not isinstance(package_binding, Mapping) or dict(package_binding) != (
        expected_package_binding
    ):
        raise ResearchAllocationError(
            "sealed analyst recommendation conflicts with its manager-screen binding"
        )
    else:
        if not isinstance(package.get("decisive_answer"), Mapping):
            raise ResearchAllocationError(
                "sealed analyst recommendation is missing its decisive answer"
            )
        manager_binding_mode = "manager_bound_package"
    research_agent = _text(row.get("research_agent"), "analyst recommendation agent")
    return {
        "preceding_stage": preceding_stage,
        "recommended_next_stage": recommended_next_stage,
        "profile_path": row["profile_path"],
        "profile_sha256": row["profile_sha256"],
        "evaluation_path": row["evaluation_path"],
        "evaluation_sha256": row["evaluation_sha256"],
        "research_agent": research_agent,
        "manager_binding_mode": manager_binding_mode,
    }


def _targeted_followup_manager_binding(
    queued: Mapping[str, Any],
    *,
    screen: Mapping[str, Any],
    symbol: str,
    manager: str,
    root: Path,
    repository_root: Path,
) -> dict[str, Any]:
    run_id = _text(queued.get("manager_screen_run_id"), "manager_screen_run_id")
    expected_manager = _investment_manager_for_cohort(
        [queued],
        repository_root=repository_root,
    )
    if expected_manager is None or manager != expected_manager:
        raise ResearchAllocationError(
            "targeted-followup decline must come from the original investment "
            f"manager: expected {expected_manager}"
        )
    if _requires_funded_full_market_grant(queued):
        grant = _verify_funded_full_market_profile_grant(
            queue_record=queued,
            screen_record=screen,
            root=root,
            repository_root=repository_root,
            symbol=symbol,
            expected_cycle_id=_text(queued.get("profile_cycle_id"), "profile_cycle_id"),
            required=True,
            context="targeted-followup decline",
        )
        if grant is None:  # pragma: no cover - required=True is fail closed
            raise ResearchAllocationError("targeted-followup decline lacks its full-market grant")
        candidate = grant["candidate"]
        return {
            "run_id": run_id,
            "batch_id": queued.get("manager_screen_batch_id"),
            "result_path": candidate["effective_decision_source_path"],
            "result_sha256": candidate["effective_decision_source_sha256"],
            "decision_sha256": candidate["effective_decision_sha256"],
            "route": candidate["original_route"],
            "manager": manager,
        }
    relative = _text(
        queued.get("manager_screen_result_path"),
        "manager_screen_result_path",
    )
    expected_sha256 = _text(
        queued.get("manager_screen_result_sha256"),
        "manager_screen_result_sha256",
    )
    result_path = (repository_root / relative).resolve()
    sealed = verify_sealed(result_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    decisions = result.get("decisions")
    matches = [
        item
        for item in (decisions if isinstance(decisions, list) else [])
        if isinstance(item, Mapping) and item.get("symbol") == symbol
    ]
    if len(matches) != 1 or matches[0].get("route") != "send_to_analyst":
        raise ResearchAllocationError(
            "manager-screen result does not contain one eligible analyst-candidate decision"
        )
    decision = matches[0]
    if (
        sealed.sha256 != expected_sha256
        or result.get("run_id") not in {None, run_id}
        or (
            isinstance(queued.get("manager_screen_batch_id"), str)
            and result.get("batch_id") not in {None, queued.get("manager_screen_batch_id")}
        )
        or (
            isinstance(queued.get("manager_screen_route"), str)
            and queued.get("manager_screen_route") != decision.get("route")
        )
    ):
        raise ResearchAllocationError(
            "manager-screen decision does not match the follow-up queue binding"
        )
    return {
        "run_id": run_id,
        "batch_id": queued.get("manager_screen_batch_id"),
        "result_path": relative,
        "result_sha256": expected_sha256,
        "decision_sha256": hashlib.sha256(canonical_json_bytes(dict(decision))).hexdigest(),
        "route": decision["route"],
        "manager": manager,
    }


def _load_or_complete_targeted_followup_decline(
    decline_path: Path,
    *,
    repository_root: Path,
) -> tuple[dict[str, Any], Any]:
    manifest_path = decline_path.with_name(f"{decline_path.name}.seal.json")
    try:
        if decline_path.is_file() and not manifest_path.exists():
            raw = decline_path.read_bytes()
            decline = json.loads(raw.decode("utf-8"))
            if canonical_json_bytes(decline) != raw:
                raise ResearchAllocationError(
                    "unsealed targeted-followup decline is not canonical JSON"
                )
            normalized = _validate_targeted_followup_decline_payload(decline)
            sealed = seal_json(
                decline_path,
                normalized,
                artifact_type="targeted_followup_decline",
                sealed_at=_datetime(normalized["declined_at"], "declined_at"),
            )
        else:
            sealed = verify_sealed(decline_path)
            decline = json.loads(decline_path.read_text(encoding="utf-8"))
            normalized = _validate_targeted_followup_decline_payload(decline)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError(
            f"targeted-followup decline is not validly sealed: {decline_path}"
        ) from exc
    if sealed.artifact_type != "targeted_followup_decline":
        raise ResearchAllocationError("targeted-followup decline has the wrong artifact type")
    try:
        decline_path.resolve().relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError("targeted-followup decline escapes repository root") from exc
    return normalized, sealed


def _validate_targeted_followup_decline_payload(value: Any) -> dict[str, Any]:
    expected_keys = {
        "schema_version",
        "symbol",
        "profile_cycle_id",
        "declined_at",
        "manager",
        "budget_decision",
        "additional_budget_hours",
        "outcome",
        "reason",
        "restart_triggers",
        "legacy_auto_materialized",
        "manager_screen_binding",
        "analyst_recommendation",
        "portfolio_action",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_keys
        or value.get("schema_version") != 1
        or value.get("budget_decision") != "declined"
        or isinstance(value.get("additional_budget_hours"), bool)
        or not isinstance(value.get("additional_budget_hours"), (int, float))
        or value.get("additional_budget_hours") != 0.0
        or not isinstance(value.get("legacy_auto_materialized"), bool)
        or value.get("portfolio_action") is not None
    ):
        raise ResearchAllocationError("targeted-followup decline fields do not match v1")
    symbol = _text(value.get("symbol"), "decline.symbol")
    if not re.fullmatch(r"CN:[0-9]{6}", symbol):
        raise ResearchAllocationError("targeted-followup decline symbol is invalid")
    outcome = _targeted_followup_decline_outcome(value.get("outcome"))
    triggers = _normalize_reactivation_triggers(
        value.get("restart_triggers"),
        outcome=outcome,
    )
    _datetime(value.get("declined_at"), "declined_at")
    manager_binding = value.get("manager_screen_binding")
    recommendation = value.get("analyst_recommendation")
    manager_keys = {
        "run_id",
        "batch_id",
        "result_path",
        "result_sha256",
        "decision_sha256",
        "route",
        "manager",
    }
    recommendation_keys = {
        "preceding_stage",
        "recommended_next_stage",
        "profile_path",
        "profile_sha256",
        "evaluation_path",
        "evaluation_sha256",
        "research_agent",
        "manager_binding_mode",
    }
    if not isinstance(manager_binding, Mapping) or set(manager_binding) != manager_keys:
        raise ResearchAllocationError("decline manager-screen binding is invalid")
    if not isinstance(recommendation, Mapping) or set(recommendation) != recommendation_keys:
        raise ResearchAllocationError("decline analyst recommendation binding is invalid")
    for field in ("result_sha256", "decision_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(manager_binding.get(field))):
            raise ResearchAllocationError(f"decline {field} is invalid")
    for field in ("profile_sha256", "evaluation_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(recommendation.get(field))):
            raise ResearchAllocationError(f"decline {field} is invalid")
    normalized_manager_binding = {
        "run_id": _text(manager_binding.get("run_id"), "decline.manager.run_id"),
        "batch_id": (
            None
            if manager_binding.get("batch_id") is None
            else _text(manager_binding.get("batch_id"), "decline.manager.batch_id")
        ),
        "result_path": _text(
            manager_binding.get("result_path"),
            "decline.manager.result_path",
        ),
        "result_sha256": str(manager_binding["result_sha256"]),
        "decision_sha256": str(manager_binding["decision_sha256"]),
        "route": _text(manager_binding.get("route"), "decline.manager.route"),
        "manager": _text(
            manager_binding.get("manager"),
            "decline.manager.manager",
        ),
    }
    normalized_recommendation = {
        "preceding_stage": _text(
            recommendation.get("preceding_stage"),
            "decline.recommendation.preceding_stage",
        ),
        "recommended_next_stage": _text(
            recommendation.get("recommended_next_stage"),
            "decline.recommendation.recommended_next_stage",
        ),
        "profile_path": _text(
            recommendation.get("profile_path"),
            "decline.recommendation.profile_path",
        ),
        "profile_sha256": str(recommendation["profile_sha256"]),
        "evaluation_path": _text(
            recommendation.get("evaluation_path"),
            "decline.recommendation.evaluation_path",
        ),
        "evaluation_sha256": str(recommendation["evaluation_sha256"]),
        "research_agent": _text(
            recommendation.get("research_agent"),
            "decline.recommendation.research_agent",
        ),
        "manager_binding_mode": _text(
            recommendation.get("manager_binding_mode"),
            "decline.recommendation.manager_binding_mode",
        ),
    }
    if (
        normalized_manager_binding["route"] not in {"send_to_analyst", "research_candidate"}
        or normalized_manager_binding["manager"] != value.get("manager")
        or normalized_recommendation["preceding_stage"] not in {"quick_profile", "scoped_research"}
        or normalized_recommendation["recommended_next_stage"]
        not in {"targeted_followup", "targeted_followup_candidate"}
        or normalized_recommendation["manager_binding_mode"]
        not in {"manager_bound_package", "legacy_queue_sealed_result"}
        or normalized_recommendation["research_agent"] == value.get("manager")
    ):
        raise ResearchAllocationError("targeted-followup decline source bindings are inconsistent")
    return {
        **dict(value),
        "profile_cycle_id": _text(
            value.get("profile_cycle_id"),
            "decline.profile_cycle_id",
        ),
        "manager": _text(value.get("manager"), "decline.manager"),
        "reason": _text(value.get("reason"), "decline.reason"),
        "outcome": outcome,
        "restart_triggers": triggers,
        "manager_screen_binding": normalized_manager_binding,
        "analyst_recommendation": normalized_recommendation,
    }


def _validate_targeted_followup_decline_bindings(
    decline: Mapping[str, Any],
    *,
    recommendation: Mapping[str, Any],
    manager_binding: Mapping[str, Any],
) -> None:
    if (
        dict(decline["analyst_recommendation"]) != dict(recommendation)
        or dict(decline["manager_screen_binding"]) != dict(manager_binding)
        or recommendation.get("research_agent") == decline.get("manager")
    ):
        raise ResearchAllocationError(
            "sealed targeted-followup decline no longer matches its source bindings"
        )


def _materialize_targeted_followup_decline(
    *,
    base: Path,
    queue: list[dict[str, Any]],
    screening: list[dict[str, Any]],
    decline: Mapping[str, Any],
    decline_path: Path,
    decline_sha256: str,
    repository_root: Path,
    idempotent: bool,
) -> dict[str, Any]:
    symbol = str(decline["symbol"])
    queued = dict(_one_record(queue, symbol, "research queue"))
    screen = dict(_one_record(screening, symbol, "screening"))
    relative = decline_path.relative_to(repository_root).as_posix()
    existing_path = queued.get("targeted_followup_decline_path")
    existing_sha256 = queued.get("targeted_followup_decline_sha256")
    if (existing_path is None) != (existing_sha256 is None):
        raise ResearchAllocationError(
            f"targeted-followup decline queue binding is incomplete: {symbol}"
        )
    already_bound = existing_path == relative and existing_sha256 == decline_sha256
    if existing_path is not None and not already_bound:
        raise ResearchAllocationError(
            f"targeted-followup decline queue binding conflicts: {symbol}"
        )
    legacy = bool(decline["legacy_auto_materialized"])
    initial_queue_state = bool(
        (
            legacy
            and queued.get("task_type") == "targeted_followup"
            and queued.get("status") == "pending"
            and queued.get("assigned_agent") is None
            and queued.get("started_at") is None
        )
        or (
            not legacy
            and queued.get("task_type") == decline["analyst_recommendation"]["preceding_stage"]
            and queued.get("status") == "completed"
        )
    )
    materialized_queue_state = bool(
        already_bound
        and (
            (
                legacy
                and queued.get("task_type") == "targeted_followup"
                and queued.get("status") == "skipped"
            )
            or (
                not legacy
                and queued.get("task_type") == decline["analyst_recommendation"]["preceding_stage"]
                and queued.get("status") == "completed"
            )
        )
    )
    if not initial_queue_state and not materialized_queue_state:
        raise ResearchAllocationError(
            f"sealed targeted-followup decline cannot repair queue state: {symbol}"
        )
    history = list(queued.get("stage_history") or [])
    if not any(
        isinstance(item, Mapping)
        and item.get("stage") == "targeted_followup_decline"
        and item.get("decline_sha256") == decline_sha256
        for item in history
    ):
        history.append(
            {
                "stage": "targeted_followup_decline",
                "status": "completed",
                "started_at": None,
                "finished_at": decline["declined_at"],
                "agent": decline["manager"],
                "reason": decline["reason"],
                "next_stage": decline["outcome"],
                "restart_triggers": list(decline["restart_triggers"]),
                "decline_path": relative,
                "decline_sha256": decline_sha256,
                "legacy_auto_materialized": legacy,
            }
        )
    next_action = _targeted_followup_decline_next_action(decline["restart_triggers"])
    queued.update(
        {
            "reason": decline["reason"],
            "next_action": next_action,
            "revisit_triggers": list(decline["restart_triggers"]),
            "targeted_followup_decline_path": relative,
            "targeted_followup_decline_sha256": decline_sha256,
            "stage_history": history,
            "failure_reason": None,
        }
    )
    if legacy:
        queued.update(
            {
                "status": "skipped",
                "assigned_agent": None,
                "started_at": None,
                "finished_at": decline["declined_at"],
            }
        )
    allowed_screen_states = {
        "targeted_followup" if legacy else "targeted_followup_candidate",
        decline["outcome"],
    }
    if screen.get("decision") not in allowed_screen_states:
        raise ResearchAllocationError(
            f"sealed targeted-followup decline cannot repair screening state: {symbol}"
        )
    evidence = list(screen.get("evidence") or [])
    screen.update(
        {
            "decision": decline["outcome"],
            "reason": decline["reason"],
            "next_action": next_action,
            "revisit_triggers": list(decline["restart_triggers"]),
            "evidence": list(
                dict.fromkeys(
                    evidence
                    + [
                        f"targeted_followup_decline:{relative}",
                        f"targeted_followup_decline_sha256:{decline_sha256}",
                    ]
                )
            ),
        }
    )
    write_jsonl(
        base / RESEARCH_QUEUE_FILE,
        [queued if item.get("symbol") == symbol else item for item in queue],
    )
    write_jsonl(
        base / SCREENING_FILE,
        [screen if item.get("symbol") == symbol else item for item in screening],
    )
    return {
        "schema_version": 1,
        "symbol": symbol,
        "outcome": decline["outcome"],
        "queue_status": queued["status"],
        "additional_budget_hours": 0.0,
        "declined_by": decline["manager"],
        "declined_at": decline["declined_at"],
        "decline_path": relative,
        "decline_sha256": decline_sha256,
        "restart_triggers": list(decline["restart_triggers"]),
        "legacy_auto_materialized": legacy,
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _targeted_followup_decline_outcome(value: Any) -> str:
    if value not in TARGETED_FOLLOWUP_DECLINE_OUTCOMES:
        raise ResearchAllocationError(
            "targeted-followup decline outcome must be price_watch, watch_only, or conditional_stop"
        )
    return str(value)


def _normalize_reactivation_triggers(
    value: Any,
    *,
    outcome: str,
) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ResearchAllocationError(
            "targeted-followup decline requires at least one restart trigger"
        )
    normalized: list[dict[str, str]] = []
    seen: set[bytes] = set()
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != REACTIVATION_TRIGGER_KEYS:
            raise ResearchAllocationError(
                "targeted-followup restart trigger fields do not match contract"
            )
        trigger_type = _text(raw.get("type"), "restart trigger type")
        if trigger_type not in REACTIVATION_TRIGGER_TYPES:
            raise ResearchAllocationError(
                f"unsupported targeted-followup restart trigger type: {trigger_type}"
            )
        trigger = {
            "type": trigger_type,
            "condition": _text(raw.get("condition"), "restart trigger condition"),
            "reason": _text(raw.get("reason"), "restart trigger reason"),
        }
        identity = canonical_json_bytes(trigger)
        if identity in seen:
            raise ResearchAllocationError("targeted-followup restart triggers must be unique")
        seen.add(identity)
        normalized.append(trigger)
    if outcome == "price_watch" and not any(trigger["type"] == "price" for trigger in normalized):
        raise ResearchAllocationError("price_watch decline requires a price trigger")
    return normalized


def _targeted_followup_decline_next_action(
    triggers: list[Mapping[str, Any]],
) -> str:
    conditions = "；".join(f"{trigger['type']}：{trigger['condition']}" for trigger in triggers)
    return f"不购买定向补证预算；仅在以下已封存条件命中时重新评估：{conditions}"


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
    symbol = profile["symbol"]
    ticker = symbol.split(":", 1)[1]
    base = Path(root)
    if _canonical_profile_adjudication_paths(base=base, symbol=symbol):
        raise ResearchAllocationError(
            "a sealed profile adjudication forbids profile package replay or "
            f"recording until a sealed successor workflow exists: {symbol}"
        )
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue_records = read_jsonl(queue_path)
    screening_records = read_jsonl(screening_path)
    queue_record = _one_record(queue_records, symbol, "research queue")
    screening_record = _one_record(screening_records, symbol, "screening")
    current_cycle = queue_record.get("profile_cycle_id")
    if isinstance(current_cycle, str) and current_cycle != normalized["cycle_id"]:
        raise ResearchAllocationError(
            f"profile package cycle does not match the current queue: {symbol}"
        )
    _manager_screen_run_id_for_record(
        queue_record,
        context="profile record",
    )
    evaluation = evaluate_quick_profile(profile, policy=policy)

    timestamp = recorded_at.strftime("%Y%m%dT%H%M%S%z")
    artifact_dir = base / "profiles" / normalized["cycle_id"] / ticker
    profile_path = artifact_dir / f"{timestamp}.profile.json"
    evaluation_path = artifact_dir / f"{timestamp}.evaluation.json"
    repository_root = base.parent.parent
    relative_profile = profile_path.relative_to(repository_root).as_posix()
    relative_evaluation = evaluation_path.relative_to(repository_root).as_posix()
    policy_sha = hashlib.sha256(canonical_json_bytes(dict(policy))).hexdigest()
    replayed = _verify_profile_record_replay(
        root=base,
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
        _repair_profile_terminal_replay_projection(
            normalized=normalized,
            evaluation_payload=replayed["evaluation_payload"],
            recorded_stage=replayed["recorded_stage"],
            queue_record=queue_record,
            screening_record=screening_record,
            queue_records=queue_records,
            screening_records=screening_records,
            queue_path=queue_path,
            screening_path=screening_path,
            relative_profile=relative_profile,
            relative_evaluation=relative_evaluation,
            profile_sha256=replayed["result"]["profile_sha256"],
            evaluation_sha256=replayed["result"]["evaluation_sha256"],
            policy_reference=_text(policy_reference, "policy_reference"),
            recorded_at=recorded_at,
        )
        return replayed["result"]
    if queue_record.get("task_type") == "deep_research":
        raise ResearchAllocationError(
            "deep_research completion must use the formal company research/claims workflow, "
            "not record_profile_package"
        )
    _validate_profile_claim_stage_authorization(
        queue_record,
        base=base,
        repository_root=repository_root,
    )
    full_market_grant = _validate_full_market_profile_binding(
        normalized,
        queue_record=queue_record,
        screen_record=screening_record,
        root=base,
        repository_root=repository_root,
        symbol=symbol,
    )
    claim_attempt = _validate_manager_bound_submission(
        normalized,
        queue_record=queue_record,
        base=base,
        repository_root=repository_root,
        symbol=symbol,
        full_market_grant=full_market_grant,
    )
    if claim_attempt is not None:
        claim_attempt = _normalize_profile_claim_attempt_binding(claim_attempt)
        claim_at = _datetime(claim_attempt["sealed_at"], "claim_attempt.sealed_at")
        generated_at = _datetime(
            normalized["provenance"]["generated_at"],
            "provenance.generated_at",
        )
        if recorded_at <= claim_at:
            raise ResearchAllocationError("profile recorded_at must be later than the sealed claim")
        if generated_at < claim_at:
            raise ResearchAllocationError("profile generated_at cannot predate the sealed claim")
    _validate_local_sources(normalized["sources"], repository_root=repository_root)
    _validate_industry_evidence(
        normalized,
        queue_record=queue_record,
        policy=policy,
    )

    queued_stage = str(queue_record.get("task_type"))
    expected_profile_stage = (
        queue_record.get("preceding_stage") if queued_stage == "targeted_followup" else queued_stage
    )
    if expected_profile_stage != profile["research_stage"]:
        raise ResearchAllocationError(
            f"queued stage does not match profile for {symbol}: "
            f"{queued_stage} expects {expected_profile_stage}, got "
            f"{profile['research_stage']}"
        )
    if queue_record.get("status") not in {"pending", "running"}:
        raise ResearchAllocationError(
            f"profile cannot be recorded from queue status {queue_record.get('status')}: {symbol}"
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
    allocation_sha = None if manager_screen_binding else queue_record.get("allocation_sha256")
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

    sealed_package = dict(normalized)
    if claim_attempt is not None:
        sealed_package["schema_version"] = 3
        sealed_package["claim_attempt"] = dict(claim_attempt)
    sealed_profile = seal_json(
        profile_path,
        sealed_package,
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
            manager_screen_run_id = queue_record.get("manager_screen_run_id")
            consumed_count = (
                _committed_stage_count_for_run(
                    queue_records,
                    manager_screen_run_id=manager_screen_run_id,
                    stage=next_stage,
                    exclude_symbols={symbol},
                )
                if isinstance(manager_screen_run_id, str)
                else sum(
                    1
                    for item in queue_records
                    if item.get("symbol") != symbol
                    and item.get("task_type") == next_stage
                    and item.get("status") in {"pending", "running"}
                )
            )
            if consumed_count >= capacity:
                next_status = "requires_rebaseline"
                capacity_wait = True

    evaluation_payload = {
        "schema_version": 3 if claim_attempt is not None else 2,
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
    if claim_attempt is not None:
        evaluation_payload["claim_attempt"] = dict(claim_attempt)
    sealed_evaluation = seal_json(
        evaluation_path,
        evaluation_payload,
        artifact_type="quick_profile_evaluation",
        sealed_at=recorded_at,
    )
    success_receipt = None
    if claim_attempt is not None:
        try:
            success_receipt = seal_profile_stage_success(
                root=base,
                queue_record=queue_record,
                agent=normalized["provenance"]["agent"],
                profile_path=relative_profile,
                profile_sha256=sealed_profile.sha256,
                evaluation_path=relative_evaluation,
                evaluation_sha256=sealed_evaluation.sha256,
                succeeded_at=recorded_at,
            )
        except ProfileStageClaimError as exc:
            raise ResearchAllocationError(str(exc)) from exc

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
            "revisit_triggers": list(evaluation["revisit_triggers"]),
            "profile_cycle_id": normalized["cycle_id"],
            "profile_evaluation_path": relative_evaluation,
            "profile_recorded_at": recorded_at.isoformat(),
        }
    )

    history = list(queue_record.get("stage_history") or [])
    completed_history = {
        "stage": queued_stage,
        "status": "completed",
        "started_at": queue_record.get("started_at"),
        "finished_at": recorded_at.isoformat(),
        "agent": normalized["provenance"]["agent"],
        "result_path": relative_profile,
        "result_sha256": sealed_profile.sha256,
        "evaluation_path": relative_evaluation,
        "evaluation_sha256": sealed_evaluation.sha256,
        "next_stage": next_stage,
    }
    if claim_attempt is not None:
        assert success_receipt is not None
        completed_history.update(
            {
                "claim_path": claim_attempt["path"],
                "claim_sha256": claim_attempt["sha256"],
                "claim_attempt_number": claim_attempt["attempt_number"],
                "success_path": success_receipt["path"],
                "success_sha256": success_receipt["sha256"],
            }
        )
    history.append(completed_history)
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
            "revisit_triggers": list(evaluation["revisit_triggers"]),
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
        idempotent=bool(success_receipt and success_receipt["idempotent"]),
    )


def _adjust_profile_evaluation(
    evaluation: Mapping[str, Any], *, queued_stage: str
) -> tuple[dict[str, Any], str]:
    """Apply the queue-stage gates that precede cross-company promotion."""

    adjusted = dict(evaluation)
    next_stage = str(adjusted.get("next_stage"))
    evaluated_stage = str(adjusted.get("evaluated_stage"))
    if next_stage == "targeted_followup":
        exhausted = queued_stage == "targeted_followup"
        next_stage = "reassign_or_stop" if exhausted else "targeted_followup_candidate"
        adjusted["next_stage"] = next_stage
        adjusted["maximum_additional_effort_hours"] = 0.0
        adjusted["reason_codes"] = sorted(
            set(adjusted["reason_codes"])
            | {
                (
                    "targeted_followup_exhausted"
                    if exhausted
                    else "awaiting_manager_targeted_followup_approval"
                )
            }
        )
    elif evaluated_stage == "quick_profile" and next_stage == "scoped_research":
        next_stage = "profile_candidate"
        adjusted["next_stage"] = next_stage
        adjusted["maximum_additional_effort_hours"] = 0.0
        adjusted["reason_codes"] = sorted(
            set(adjusted["reason_codes"]) | {"awaiting_cross_company_profile_comparison"}
        )
    elif evaluated_stage == "scoped_research" and next_stage == "deep_research":
        next_stage = "deep_candidate"
        adjusted["next_stage"] = next_stage
        adjusted["maximum_additional_effort_hours"] = 0.0
        adjusted["reason_codes"] = sorted(
            set(adjusted["reason_codes"]) | {"awaiting_cross_company_deep_research_comparison"}
        )
    return adjusted, next_stage


def _verify_profile_record_replay(
    *,
    root: Path,
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
    if not _cycle_stage_completion_is_authenticated(
        queue_record,
        history,
        base=root,
        stage=recorded_stage,
        cycle=str(normalized["cycle_id"]),
    ):
        raise ResearchAllocationError(
            f"profile replay lacks an authenticated current-cycle completion: "
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
        field for field, expected in expected_history.items() if history.get(field) != expected
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
            f"completed profile package is not validly sealed: {normalized['profile']['symbol']}"
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
    if not isinstance(existing_profile, dict):
        raise ResearchAllocationError(
            f"completed profile package must be an object: {normalized['profile']['symbol']}"
        )
    existing_profile = dict(existing_profile)
    claim_attempt = existing_profile.pop("claim_attempt", None)
    sealed_profile_schema = existing_profile.get("schema_version")
    if claim_attempt is not None:
        if sealed_profile_schema != 3:
            raise ResearchAllocationError("claim-bound profile package must use schema_version 3")
        existing_profile["schema_version"] = 2
    elif sealed_profile_schema != 2:
        raise ResearchAllocationError("legacy profile package must use schema_version 2")
    if existing_profile != normalized:
        raise ResearchAllocationError(
            f"profile replay conflicts with the sealed package: {normalized['profile']['symbol']}"
        )
    if claim_attempt is not None:
        claim_attempt = _normalize_profile_claim_attempt_binding(claim_attempt)
        expected_claim_history = {
            "claim_path": claim_attempt["path"],
            "claim_sha256": claim_attempt["sha256"],
            "claim_attempt_number": claim_attempt["attempt_number"],
        }
        if any(
            history.get(field) != expected for field, expected in expected_claim_history.items()
        ):
            raise ResearchAllocationError(
                "profile replay claim attempt does not match completed history: "
                f"{normalized['profile']['symbol']}"
            )

    try:
        sealed_evaluation = verify_sealed(evaluation_path)
    except ValueError as exc:
        raise ResearchAllocationError(
            f"completed profile evaluation is not validly sealed: {normalized['profile']['symbol']}"
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
            f"completed profile evaluation cannot be read: {normalized['profile']['symbol']}"
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
    if claim_attempt is not None:
        expected_fields.add("claim_attempt")
    if not isinstance(evaluation_payload, dict) or set(evaluation_payload) != expected_fields:
        raise ResearchAllocationError(
            f"completed profile evaluation fields do not match contract: "
            f"{normalized['profile']['symbol']}"
        )
    expected_values = {
        "schema_version": 3 if claim_attempt is not None else 2,
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
    if claim_attempt is not None:
        expected_values["claim_attempt"] = claim_attempt
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
    if claim_attempt is not None and (
        history.get("result_sha256") != sealed_profile.sha256
        or history.get("evaluation_sha256") != sealed_evaluation.sha256
    ):
        raise ResearchAllocationError(
            "profile replay artifact SHA bindings do not match completed history: "
            f"{normalized['profile']['symbol']}"
        )
    if claim_attempt is not None:
        try:
            verify_profile_stage_success(
                root=root,
                claim_attempt=claim_attempt,
                history_event=history,
            )
        except ProfileStageClaimError as exc:
            raise ResearchAllocationError(str(exc)) from exc
    return {
        "result": _profile_record_result(
            evaluation_payload,
            profile_sha256=sealed_profile.sha256,
            evaluation_path=relative_evaluation,
            evaluation_sha256=sealed_evaluation.sha256,
            idempotent=True,
        ),
        "evaluation_payload": evaluation_payload,
        "recorded_stage": recorded_stage,
    }


def _repair_profile_terminal_replay_projection(
    *,
    normalized: Mapping[str, Any],
    evaluation_payload: Mapping[str, Any],
    recorded_stage: str,
    queue_record: Mapping[str, Any],
    screening_record: Mapping[str, Any],
    queue_records: list[dict[str, Any]],
    screening_records: list[dict[str, Any]],
    queue_path: Path,
    screening_path: Path,
    relative_profile: str,
    relative_evaluation: str,
    profile_sha256: str,
    evaluation_sha256: str,
    policy_reference: str,
    recorded_at: dt.datetime,
) -> None:
    """Repair only the deterministic terminal projection of an identical replay."""

    evaluation = evaluation_payload["evaluation"]
    next_stage = str(evaluation["next_stage"])
    if next_stage in RESEARCH_STAGES:
        return
    history = list(queue_record.get("stage_history") or [])
    matching_indexes = [
        index
        for index, item in enumerate(history)
        if isinstance(item, Mapping)
        and item.get("status") == "completed"
        and item.get("result_path") == relative_profile
        and item.get("evaluation_path") == relative_evaluation
    ]
    if len(matching_indexes) != 1:
        raise ResearchAllocationError(
            "profile terminal replay history is missing or duplicated: "
            f"{normalized['profile']['symbol']}"
        )
    if matching_indexes[0] != len(history) - 1:
        # A later workflow owns the live projection.  The sealed profile replay
        # remains read-only and must not roll that state back.
        return
    terminal_envelope = (
        queue_record.get("task_type") == recorded_stage
        and queue_record.get("status") == "completed"
        and queue_record.get("result_path") == relative_evaluation
        and queue_record.get("preceding_stage") == recorded_stage
    )
    if not terminal_envelope:
        if queue_record.get("task_type") in RESEARCH_STAGES:
            return
        raise ResearchAllocationError(
            f"profile replay terminal queue projection drifted: {normalized['profile']['symbol']}"
        )

    capacity_wait = bool(evaluation_payload["capacity_wait"])
    expected_reason = _screening_reason(next_stage, capacity_wait)
    expected_next_action = _next_action(next_stage, capacity_wait)
    expected_triggers = list(evaluation["revisit_triggers"])
    history_row = history[matching_indexes[0]]
    expected_queue_fields = {
        "symbol": normalized["profile"]["symbol"],
        "task_type": recorded_stage,
        "status": "completed",
        "reason": expected_reason,
        "assigned_agent": normalized["provenance"]["agent"],
        "started_at": history_row.get("started_at"),
        "finished_at": recorded_at.isoformat(),
        "result_path": relative_evaluation,
        "failure_reason": None,
        "next_action": expected_next_action,
        "preceding_stage": recorded_stage,
        "profile_cycle_id": normalized["cycle_id"],
        "profile_priority_score": _profile_priority_score(
            normalized["profile"],
            priority=int(queue_record.get("priority", 5)),
        ),
    }
    queue_drift = [
        field
        for field, expected in expected_queue_fields.items()
        if queue_record.get(field) != expected
    ]
    expected_evidence = [
        f"profile:{relative_profile}",
        f"profile_sha256:{profile_sha256}",
        f"evaluation:{relative_evaluation}",
        f"evaluation_sha256:{evaluation_sha256}",
        f"policy:{policy_reference}",
        f"s1_sources:{normalized['profile']['s1_source_count']}",
    ]
    expected_screen_fields = {
        "symbol": normalized["profile"]["symbol"],
        "decision": next_stage,
        "reason": expected_reason,
        "evidence": expected_evidence,
        "next_action": expected_next_action,
        "profile_cycle_id": normalized["cycle_id"],
        "profile_evaluation_path": relative_evaluation,
        "profile_recorded_at": recorded_at.isoformat(),
    }
    screen_drift = [
        field
        for field, expected in expected_screen_fields.items()
        if screening_record.get(field) != expected
    ]
    if queue_drift or screen_drift:
        details = sorted(
            {f"queue.{field}" for field in queue_drift}
            | {f"screening.{field}" for field in screen_drift}
        )
        raise ResearchAllocationError(
            "profile replay terminal projection conflicts outside the repairable "
            f"trigger field ({', '.join(details)}): "
            f"{normalized['profile']['symbol']}"
        )

    queue_triggers = queue_record.get("revisit_triggers")
    screen_triggers = screening_record.get("revisit_triggers")
    for label, current in (
        ("queue", queue_triggers),
        ("screening", screen_triggers),
    ):
        if current == expected_triggers:
            continue
        if expected_triggers and (current is None or current == [] or current == ()):
            continue
        raise ResearchAllocationError(
            f"profile replay {label} revisit_triggers conflict with the sealed "
            f"evaluation: {normalized['profile']['symbol']}"
        )

    queue_changed = queue_triggers != expected_triggers
    screen_changed = screen_triggers != expected_triggers
    if not queue_changed and not screen_changed:
        return
    updated_queue = dict(queue_record)
    updated_screening = dict(screening_record)
    updated_queue["revisit_triggers"] = expected_triggers
    updated_screening["revisit_triggers"] = expected_triggers
    if screen_changed:
        write_jsonl(
            screening_path,
            [
                updated_screening if item.get("symbol") == normalized["profile"]["symbol"] else item
                for item in screening_records
            ],
        )
    if queue_changed:
        write_jsonl(
            queue_path,
            [
                updated_queue if item.get("symbol") == normalized["profile"]["symbol"] else item
                for item in queue_records
            ],
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


def _validate_profile_adjudication_ledger_for_comparison(
    *, base: Path, cycle: str
) -> dict[str, Any]:
    adjudications = profile_adjudication_ledger_status(root=base, cycle_id=cycle)
    if adjudications["invalid_artifact_count"]:
        first = adjudications["invalid_artifacts"][0]
        raise ResearchAllocationError(
            "profile comparison is blocked by an invalid adjudication ledger: "
            f"{first['symbol']}: {first['error']}"
        )
    return adjudications


def _validate_comparison_profile_adjudications(
    rows: list[Mapping[str, Any]],
    *,
    adjudications: Mapping[str, Any],
    compared_at: dt.datetime,
) -> None:
    symbols = {str(row.get("symbol")) for row in rows}
    expected = {
        str(item["symbol"]): item
        for item in adjudications["profile_adjudications"]
        if str(item["symbol"]) in symbols
    }
    actual = {
        str(row["symbol"]): row["profile_adjudication"]
        for row in rows
        if isinstance(row.get("profile_adjudication"), Mapping)
    }
    if actual != expected:
        raise ResearchAllocationError(
            "profile comparison is stale relative to the adjudication ledger"
        )
    for row in rows:
        adjudication = row.get("profile_adjudication")
        if isinstance(adjudication, Mapping) and compared_at <= _datetime(
            adjudication.get("adjudicated_at"),
            "profile_adjudication.adjudicated_at",
        ):
            raise ResearchAllocationError(
                "profile comparison must be later than every sealed adjudication"
            )


def build_profile_comparison_packet(
    *,
    root: str | Path,
    cycle_id: str,
    stage: str,
    created_at: dt.datetime,
) -> dict[str, Any]:
    """Seal a score-free L2/L3 packet for the investment manager."""

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
        base=base,
        repository_root=repository_root,
        cycle=cycle,
        stage=stage,
    )
    investment_manager_agent = _investment_manager_for_cohort(
        cohort,
        repository_root=repository_root,
    )
    adjudications = _validate_profile_adjudication_ledger_for_comparison(
        base=base,
        cycle=cycle,
    )
    full_market_authority = _full_market_v3_cycle_authority(
        base=base,
        repository_root=repository_root,
        cycle=cycle,
    )
    full_market_symbols = (
        set(full_market_authority["selected"])
        if full_market_authority is not None
        else set()
    )
    comparison_path = base / "profiles" / cycle / config["comparison_name"]
    relative = comparison_path.relative_to(repository_root).as_posix()
    if comparison_path.exists():
        sealed = verify_sealed(comparison_path)
        if sealed.artifact_type != f"{stage}_comparison_packet":
            raise ResearchAllocationError(f"sealed {stage} comparison has the wrong artifact type")
        payload = json.loads(comparison_path.read_text(encoding="utf-8"))
        comparison_rows = payload.get("rows")
        if not isinstance(comparison_rows, list) or not all(
            isinstance(row, Mapping) for row in comparison_rows
        ):
            raise ResearchAllocationError(f"sealed {stage} comparison rows are invalid")
        _validate_comparison_profile_adjudications(
            comparison_rows,
            adjudications=adjudications,
            compared_at=_datetime(payload.get("created_at"), "comparison.created_at"),
        )
        expected = {
            "cycle_id": cycle,
            "evaluated_stage": stage,
            "predecessor_selection_path": binding,
            "predecessor_selection_sha256": binding_sha,
            "investment_manager_agent": investment_manager_agent,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ResearchAllocationError(f"sealed {stage} comparison conflicts with cycle binding")
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
            base=base,
            repository_root=repository_root,
            canonical_full_market_v3=item.get("symbol") in full_market_symbols,
        )
        for ordinal, item in enumerate(cohort, 1)
    ]
    _validate_comparison_profile_adjudications(
        rows,
        adjudications=adjudications,
        compared_at=created_at,
    )
    payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "evaluated_stage": stage,
        "next_stage": config["next_stage"],
        "predecessor_selection_path": binding,
        "predecessor_selection_sha256": binding_sha,
        "investment_manager_agent": investment_manager_agent,
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
    policy_path: str | Path = "policies/research-allocation.json",
) -> dict[str, Any]:
    """Grant L3/L4 budget from the investment manager's explicit decisions."""

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
        base=base,
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
        raise ResearchAllocationError(f"sealed {stage} comparison has the wrong artifact type")
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    investment_manager_agent = _investment_manager_for_cohort(
        cohort,
        repository_root=repository_root,
    )
    if (
        comparison.get("cycle_id") != cycle
        or comparison.get("evaluated_stage") != stage
        or comparison.get("predecessor_selection_path") != binding
        or comparison.get("predecessor_selection_sha256") != binding_sha
        or comparison.get("investment_manager_agent") != investment_manager_agent
    ):
        raise ResearchAllocationError(f"{stage} comparison packet does not match cohort binding")
    comparison_rows = comparison.get("rows")
    if not isinstance(comparison_rows, list) or not all(
        isinstance(row, Mapping) for row in comparison_rows
    ):
        raise ResearchAllocationError(f"{stage} comparison rows are invalid")
    if len(comparison_rows) != len(cohort):
        raise ResearchAllocationError(f"{stage} comparison cohort count is invalid")
    adjudications = _validate_profile_adjudication_ledger_for_comparison(
        base=base,
        cycle=cycle,
    )
    _validate_comparison_profile_adjudications(
        comparison_rows,
        adjudications=adjudications,
        compared_at=_datetime(comparison.get("created_at"), "comparison.created_at"),
    )
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
            "cross-company investment manager must be independent of company research Agents"
        )
    if (
        investment_manager_agent is not None
        and normalized["provenance"]["agent"] != investment_manager_agent
    ):
        raise ResearchAllocationError(
            "profile allocation must be approved by the original "
            f"investment manager: expected {investment_manager_agent}"
        )

    next_stage = config["next_stage"]
    select_decision = config["select_decision"]
    selected_symbols = [
        row["symbol"] for row in normalized["decisions"] if row["decision"] == select_decision
    ]
    capacity = _stage_capacity(policy, next_stage)
    if capacity is None:
        raise ResearchAllocationError(f"stage capacity is invalid: {next_stage}")
    manager_screen_run_id = _manager_screen_run_id_for_cohort(cohort)
    selection_path = base / "profiles" / cycle / config["selection_name"]
    relative_selection = selection_path.relative_to(repository_root).as_posix()
    committed_count = 0
    if manager_screen_run_id is not None:
        ledger = _sealed_stage_commitment_ledger(
            base=base,
            repository_root=repository_root,
            manager_screen_run_id=manager_screen_run_id,
            next_stage=next_stage,
        )
        duplicates = sorted(
            symbol
            for symbol in selected_symbols
            if symbol in ledger and ledger[symbol]["selection_path"] != relative_selection
        )
        if duplicates:
            raise ResearchAllocationError(
                f"{next_stage} budget was already purchased in another sealed profile cycle: "
                f"{duplicates}"
            )
        committed_count = sum(
            1 for item in ledger.values() if item["selection_path"] != relative_selection
        )
    if committed_count + len(selected_symbols) > capacity:
        raise ResearchAllocationError(
            f"Agent decisions exceed {next_stage} run capacity: "
            f"{committed_count} committed + {len(selected_symbols)} selected "
            f"> {capacity}"
        )
    risk_cap = _risk_cluster_cap(policy, next_stage)
    if len(selected_symbols) > risk_cap:
        raise ResearchAllocationError(
            "Agent decisions exceed the conservative unclassified risk-cluster "
            f"cap for {next_stage}: {len(selected_symbols)} > {risk_cap}"
        )
    budget = _effort_budget(policy, next_stage)
    policy_binding = _research_policy_binding(
        repository_root=repository_root,
        policy=policy,
        policy_path=policy_path,
    )
    if manager_screen_run_id is not None:
        _bind_research_policy_for_run(
            base=base,
            run_id=manager_screen_run_id,
            policy_binding=policy_binding,
            bound_at=finalized_at,
        )
    selected_set = set(selected_symbols)
    decisions_by_symbol = {row["symbol"]: row for row in normalized["decisions"]}
    decision_rows = [
        {
            "ordinal": row["ordinal"],
            "symbol": row["symbol"],
            "name": row["name"],
            "selected": row["symbol"] in selected_set,
            "selection_reason": decisions_by_symbol[row["symbol"]]["reason"],
            "decisive_question": decisions_by_symbol[row["symbol"]]["decisive_question"],
            "counterevidence_considered": decisions_by_symbol[row["symbol"]][
                "counterevidence_considered"
            ],
            **(
                {"profile_adjudication": dict(row["profile_adjudication"])}
                if isinstance(row.get("profile_adjudication"), Mapping)
                else {}
            ),
        }
        for row in comparison_rows
    ]
    payload = {
        "schema_version": 1,
        "cycle_id": cycle,
        "manager_screen_run_id": manager_screen_run_id,
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
        "research_policy": policy_binding,
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
            raise ResearchAllocationError(f"sealed {stage} selection has the wrong artifact type")
        existing = json.loads(selection_path.read_text(encoding="utf-8"))
        compatibility_omissions = (
            {"manager_screen_run_id", "research_policy"}
            if "research_policy" not in existing
            else set()
        )
        expected_replay = {
            k: v
            for k, v in payload.items()
            if k != "finalized_at" and k not in compatibility_omissions
        }
        actual_replay = {
            k: v
            for k, v in existing.items()
            if k != "finalized_at" and k not in compatibility_omissions
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
            base=base,
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
    _reject_legacy_finalize_for_manager_screen(
        queue,
        base=base,
        cycle=cycle,
        stage=stage,
    )

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
        _reject_legacy_finalize_for_manager_screen(
            queue,
            base=base,
            cycle=cycle,
            stage=stage,
            bound_symbols={
                str(row["symbol"])
                for row in payload["ranking"]
                if isinstance(row, Mapping) and isinstance(row.get("symbol"), str)
            },
        )
        bound_budget = payload.get("next_stage_effort_budget_hours")
        updated_screening, updated_queue, screening_changed, queue_changed = (
            _materialize_profile_selection(
                base=base,
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
        and _latest_cycle_stage_completion_for_legacy_materialization(
            item,
            base=base,
            stage=stage,
            cycle=cycle,
        )
        is not None
        and isinstance(item.get(binding_field), str)
    ]
    if not anchors:
        raise ResearchAllocationError(f"no recorded {stage} cohort is available for cycle: {cycle}")
    bindings = {item[binding_field] for item in anchors}
    if len(bindings) != 1:
        raise ResearchAllocationError(f"{stage} cycle spans multiple predecessor selections")
    binding = next(iter(bindings))
    cohort = _bound_profile_cohort(
        queue,
        base=base,
        repository_root=repository_root,
        binding_field=binding_field,
        binding=binding,
        cycle=cycle,
        stage=stage,
    )
    if any(item.get(binding_field) != binding for item in cohort):
        raise ResearchAllocationError(
            f"{stage} cohort mutable predecessor binding drifted from its sealed selection"
        )
    _manager_screen_run_id_for_cohort(cohort)
    if _manager_screen_run_id_for_cohort(cohort) is not None:
        raise ResearchAllocationError(
            "legacy score-based profile-finalize is forbidden for "
            "manager-screen-bound cohorts; use profile-compare/profile-select "
            "with the original investment manager"
        )
    incomplete = [
        item["symbol"]
        for item in cohort
        if item.get("profile_cycle_id") != cycle
        or _latest_cycle_stage_completion_for_legacy_materialization(
            item,
            base=base,
            stage=stage,
            cycle=cycle,
        )
        is None
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
    capacity = _stage_capacity(policy, next_stage)
    if capacity is None:
        raise ResearchAllocationError(f"stage capacity is invalid: {next_stage}")
    manager_screen_run_id = _manager_screen_run_id_for_cohort(cohort)
    committed_count = (
        _committed_stage_count_for_run(
            queue,
            manager_screen_run_id=manager_screen_run_id,
            stage=next_stage,
            exclude_symbols={str(item["symbol"]) for item in cohort},
        )
        if manager_screen_run_id is not None
        else 0
    )
    remaining_capacity = capacity - committed_count
    if remaining_capacity < 0:
        raise ResearchAllocationError(
            f"{next_stage} run capacity is already exceeded: "
            f"{committed_count} committed > {capacity}"
        )
    budgets = policy.get("effort_budget_hours")
    if not isinstance(budgets, Mapping):
        raise ResearchAllocationError("effort budget policy is invalid")
    budget = budgets.get(next_stage)
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or budget <= 0:
        raise ResearchAllocationError(f"effort budget is invalid: {next_stage}")
    risk_cap = _risk_cluster_cap(policy, next_stage)
    selected, capped_symbols = _select_with_risk_cluster_cap(
        ranked,
        capacity=remaining_capacity,
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
            base=base,
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


def _reject_legacy_finalize_for_manager_screen(
    queue: list[Mapping[str, Any]],
    *,
    base: Path,
    cycle: str,
    stage: str,
    bound_symbols: set[str] | None = None,
) -> None:
    if bound_symbols is None:
        candidates = [
            item
            for item in queue
            if item.get("profile_cycle_id") == cycle
            and _latest_cycle_stage_completion(
                item,
                base=base,
                stage=stage,
                cycle=cycle,
            )
            is not None
        ]
    else:
        candidates = [item for item in queue if item.get("symbol") in bound_symbols]
    if any(
        isinstance(item.get("manager_screen_run_id"), str)
        or isinstance(item.get("manager_screen_result_path"), str)
        for item in candidates
    ):
        raise ResearchAllocationError(
            "legacy score-based profile-finalize is forbidden for "
            "manager-screen-bound cohorts; use profile-compare/profile-select "
            "with the original investment manager"
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
    if "research_policy" in payload:
        _normalize_research_policy_binding(payload.get("research_policy"))
    manager_screen_run_id = payload.get("manager_screen_run_id")
    if manager_screen_run_id is not None and (
        not isinstance(manager_screen_run_id, str) or not manager_screen_run_id
    ):
        raise ResearchAllocationError(f"sealed {stage} selection manager_screen_run_id is invalid")
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
        adjudication = row.get("profile_adjudication")
        if adjudication is not None:
            if (
                not isinstance(adjudication, Mapping)
                or adjudication.get("symbol") != symbol
                or adjudication.get("profile_cycle_id") != cycle
                or adjudication.get("outcome") not in PROFILE_ADJUDICATION_OUTCOMES
                or not isinstance(adjudication.get("adjudication_path"), str)
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(adjudication.get("adjudication_sha256")),
                )
                or adjudication.get("additional_budget_hours") != 0.0
                or adjudication.get("portfolio_action") is not None
            ):
                raise ResearchAllocationError(
                    f"sealed {stage} selection profile adjudication is invalid: {symbol}"
                )
            if row["selected"] is True:
                raise ResearchAllocationError(
                    "sealed selection cannot fund a terminal profile adjudication: "
                    f"{symbol}"
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
        raise ResearchAllocationError(f"sealed {stage} selection next-stage budget is invalid")


def _materialize_profile_selection(
    *,
    base: Path,
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

    selection_sha_field = {
        "profile_quick_selection_path": "profile_quick_selection_sha256",
        "profile_scoped_selection_path": "profile_scoped_selection_sha256",
    }.get(next_binding_field)
    if selection_sha_field is None:
        raise ResearchAllocationError(
            f"unsupported profile selection binding field: {next_binding_field}"
        )
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
        current_cycle = queued.get("profile_cycle_id")
        if isinstance(current_cycle, str) and current_cycle != cycle:
            # A later cycle owns the mutable queue and screening rows now.
            continue
        completed_event = _latest_cycle_stage_completion_for_legacy_materialization(
            queued,
            base=base,
            stage=stage,
            cycle=cycle,
        )
        if completed_event is None:
            raise ResearchAllocationError(
                f"sealed {stage} selection lacks authenticated current-cycle completion: "
                f"{symbol}"
            )
        current_adjudication = _profile_adjudication_for_profile_row(
            queued,
            symbol=symbol,
            repository_root=base.parent.parent,
            base=base,
        )
        sealed_adjudication = row.get("profile_adjudication")
        if (
            (current_adjudication is None) != (sealed_adjudication is None)
            or (
                current_adjudication is not None
                and (
                    not isinstance(sealed_adjudication, Mapping)
                    or current_adjudication != dict(sealed_adjudication)
                )
            )
        ):
            raise ResearchAllocationError(
                f"sealed {stage} selection does not match the profile adjudication: {symbol}"
            )

        existing_binding = queued.get(next_binding_field)
        if existing_binding is not None and existing_binding != selection_path:
            raise ResearchAllocationError(
                f"sealed {stage} selection conflicts at {next_binding_field}: {symbol}"
            )
        existing_sha256 = queued.get(selection_sha_field)
        if existing_sha256 is not None and existing_sha256 != selection_sha256:
            raise ResearchAllocationError(
                f"sealed {stage} selection conflicts at {selection_sha_field}: {symbol}"
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
        completed_followup_event = _latest_cycle_stage_completion_for_legacy_materialization(
            queued,
            base=base,
            stage="targeted_followup",
            cycle=cycle,
        )
        completed_followup = bool(
            queued.get("task_type") == "targeted_followup"
            and queued.get("status") == "completed"
            and completed_followup_event is not None
        )
        declined_followup_event = _latest_cycle_stage_completion_for_legacy_materialization(
            queued,
            base=base,
            stage="targeted_followup_decline",
            cycle=cycle,
        )
        declined_followup = declined_followup_event is not None
        candidate_outcome = "profile_candidate" if stage == "quick_profile" else "deep_candidate"
        outcome_event = (
            declined_followup_event
            if declined_followup
            else completed_followup_event
            if completed_followup
            else completed_event
        )
        completed_outcome = outcome_event.get("next_stage")
        preserve_outcome = bool(
            completed_outcome in TERMINAL_STAGES and completed_outcome != candidate_outcome
        )
        completed_next_stage = _latest_cycle_stage_completion_for_legacy_materialization(
            queued,
            base=base,
            stage=next_stage,
            cycle=cycle,
        )
        later_progress = bool(
            completed_next_stage is not None
            or (
                queued.get("task_type") not in {stage, next_stage}
                and queued.get("task_type") in RESEARCH_STAGES
            )
        )
        selected = row["selected"] is True

        if current_adjudication is not None:
            if selected:
                raise ResearchAllocationError(
                    f"terminal profile adjudication cannot receive {next_stage} budget: "
                    f"{symbol}"
                )
            if not base_state and existing_binding != selection_path:
                raise ResearchAllocationError(
                    f"quarantined profile selection cannot safely repair queue state: {symbol}"
                )
            queued[next_binding_field] = selection_path
            queued[selection_sha_field] = selection_sha256
            screen["evidence"] = list(dict.fromkeys(evidence + expected_evidence))
            if (
                screen.get("decision") != current_adjudication["effective_outcome"]
                or queued.get("profile_adjudication_outcome")
                != current_adjudication["outcome"]
            ):
                raise ResearchAllocationError(
                    f"quarantined profile adjudication projection drift: {symbol}"
                )
            if queued != original_queue:
                queue_by_symbol[symbol] = queued
                queue_changed = True
            if screen != original_screen:
                screen_by_symbol[symbol] = screen
                screening_changed = True
            continue

        if selected:
            if declined_followup:
                raise ResearchAllocationError(
                    "profile selection cannot override a sealed targeted-followup "
                    f"decline without a new trigger workflow: {symbol}"
                )
            if base_state:
                if budget is None:
                    raise ResearchAllocationError(
                        f"sealed {stage} selection predates recoverable budget binding: {symbol}"
                    )
                queued.update(
                    {
                        "task_type": next_stage,
                        "status": "pending",
                        "assigned_agent": None,
                        "started_at": None,
                        "finished_at": None,
                        "failure_reason": None,
                        "reason": (f"完整{stage}批次横向比较后获得{next_stage}预算。"),
                        "next_action": _next_action(next_stage, False),
                        "effort_budget_hours": budget,
                        "preceding_stage": stage,
                        "stop_conditions": _stop_conditions(next_stage),
                        next_binding_field: selection_path,
                        selection_sha_field: selection_sha256,
                    }
                )
                if not screen_proves_selection:
                    screen.update(
                        {
                            "decision": next_stage,
                            "reason": (f"完整{stage}批次横向比较后获得{next_stage}预算。"),
                            "evidence": list(dict.fromkeys(evidence + expected_evidence)),
                            "next_action": _next_action(next_stage, False),
                        }
                    )
            elif next_stage_state or later_progress:
                # Only add the immutable selection binding. Claim, completion,
                # or deeper-stage fields and conclusions belong to later work.
                queued[next_binding_field] = selection_path
                queued[selection_sha_field] = selection_sha256
                safe_pending_state = bool(
                    next_stage_state
                    and queued.get("status") == "pending"
                    and queued.get("assigned_agent") is None
                    and completed_next_stage is None
                )
                if safe_pending_state and not screen_proves_selection:
                    screen.update(
                        {
                            "decision": next_stage,
                            "reason": (f"完整{stage}批次横向比较后获得{next_stage}预算。"),
                            "evidence": list(dict.fromkeys(evidence + expected_evidence)),
                            "next_action": _next_action(next_stage, False),
                        }
                    )
            else:
                raise ResearchAllocationError(
                    f"sealed {stage} selection cannot safely repair queue state: {symbol}"
                )
        elif (
            base_state
            or completed_followup
            or declined_followup
            or existing_binding == selection_path
        ):
            queued[next_binding_field] = selection_path
            queued[selection_sha_field] = selection_sha256
            if preserve_outcome:
                # A profile or follow-up may already have produced a stronger
                # terminal conclusion such as price_watch or conditional_stop.
                # Bind the allocation decision without regressing that result.
                queued["next_action"] = _next_action(completed_outcome, False)
                screen.update(
                    {
                        "decision": completed_outcome,
                        "reason": _screening_reason(completed_outcome, False),
                        "evidence": list(dict.fromkeys(evidence + expected_evidence)),
                        "next_action": _next_action(completed_outcome, False),
                    }
                )
            else:
                if base_state:
                    queued["next_action"] = "等待结构化触发器或下一周期重新竞争研究预算。"
                if not screen_proves_selection:
                    screen.update(
                        {
                            "decision": "catalog",
                            "reason": (
                                f"{stage}支持继续研究，但横向比较后未获得本周期{next_stage}容量。"
                            ),
                            "evidence": list(dict.fromkeys(evidence + expected_evidence)),
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
    base: Path,
    repository_root: Path,
    cycle: str,
    stage: str,
) -> tuple[str, str, str, list[dict[str, Any]]]:
    full_market_authority = _full_market_v3_cycle_authority(
        base=base,
        repository_root=repository_root,
        cycle=cycle,
    )
    full_market_symbols = (
        set(full_market_authority["selected"])
        if full_market_authority is not None
        else set()
    )
    anchors = []
    for item in queue:
        if (
            item.get("profile_cycle_id") != cycle
            or _latest_cycle_stage_completion_with_legacy_decline_migration(
                item,
                base=base,
                stage=stage,
                cycle=cycle,
                canonical_full_market_v3=item.get("symbol") in full_market_symbols,
            )
            is None
        ):
            continue
        binding = _profile_predecessor_binding(item, stage=stage)
        if binding is not None:
            anchors.append(binding)
    if not anchors:
        raise ResearchAllocationError(f"no recorded {stage} cohort is available for cycle: {cycle}")
    bindings = set(anchors)
    if len(bindings) != 1:
        raise ResearchAllocationError(f"{stage} cycle spans multiple predecessor selections")
    binding_field, binding = next(iter(bindings))
    binding_path = repository_root / binding
    if not binding_path.exists():
        raise ResearchAllocationError(
            f"sealed predecessor selection is required for {stage}: {binding}"
        )
    sealed_binding = verify_sealed(binding_path)
    cohort = _bound_profile_cohort(
        queue,
        base=base,
        repository_root=repository_root,
        binding_field=binding_field,
        binding=binding,
        cycle=cycle,
        stage=stage,
    )
    if any(item.get(binding_field) != binding for item in cohort):
        raise ResearchAllocationError(
            f"{stage} cohort mutable predecessor binding drifted from its sealed selection"
        )
    predecessor_sha_field = {
        "manager_screen_allocation_result_path": ("manager_screen_allocation_result_sha256"),
        "manager_screen_result_path": "manager_screen_result_sha256",
        "triage_selection_path": "triage_selection_sha256",
    }.get(binding_field)
    requires_predecessor_sha = binding_field == "manager_screen_allocation_result_path"
    if predecessor_sha_field is not None and any(
        (requires_predecessor_sha or predecessor_sha_field in item)
        and item.get(predecessor_sha_field) != sealed_binding.sha256
        for item in cohort
    ):
        raise ResearchAllocationError(f"{stage} cohort predecessor SHA binding is inconsistent")
    incomplete = [
        item["symbol"]
        for item in cohort
        if item.get("profile_cycle_id") != cycle
        or _latest_cycle_stage_completion_with_legacy_decline_migration(
            item,
            base=base,
            stage=stage,
            cycle=cycle,
            canonical_full_market_v3=item.get("symbol") in full_market_symbols,
        )
        is None
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
        raise ResearchAllocationError(f"{stage} cohort does not match sealed predecessor selection")
    ordered = [by_symbol[str(symbol)] for symbol in order]
    cohort_run_id = _manager_screen_run_id_for_cohort(ordered)
    sealed_run_id = predecessor.get("manager_screen_run_id")
    if sealed_run_id is None and sealed_binding.artifact_type in {
        "manager_screen_full_market_allocation_v3_result",
        "manager_screen_result",
        "manager_screen_legacy_transition_result",
        "manager_screen_quote_impact_result",
    }:
        sealed_run_id = predecessor.get("run_id")
    if sealed_run_id is not None:
        if not isinstance(sealed_run_id, str) or not sealed_run_id:
            raise ResearchAllocationError(
                f"sealed {stage} predecessor manager-screen run_id is invalid"
            )
        if cohort_run_id is None:
            raise ResearchAllocationError(
                f"manager-bound {stage} cohort cannot drop its manager-screen run binding"
            )
        if cohort_run_id != sealed_run_id:
            raise ResearchAllocationError(
                f"{stage} cohort manager-screen run does not match its sealed predecessor"
            )
    return (
        binding_field,
        binding,
        sealed_binding.sha256,
        ordered,
    )


def _profile_predecessor_binding(item: Mapping[str, Any], *, stage: str) -> tuple[str, str] | None:
    fields = (
        (
            "manager_screen_allocation_result_path",
            "manager_screen_result_path",
            "triage_selection_path",
        )
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
    if (
        stage == "quick_profile"
        and artifact_type == "manager_screen_full_market_allocation_v3_result"
    ):
        decisions = payload.get("decisions")
        if not isinstance(decisions, list):
            raise ResearchAllocationError("full-market allocation decisions are invalid")
        return [
            str(row["symbol"])
            for row in decisions
            if isinstance(row, Mapping)
            and row.get("decision") == "fund_quick_profile"
            and isinstance(row.get("symbol"), str)
        ]
    if stage == "quick_profile" and artifact_type in {
        "manager_screen_result",
        "manager_screen_legacy_transition_result",
        "manager_screen_quote_impact_result",
    }:
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
    selected_key = "selected_for_quick_profile" if stage == "quick_profile" else "selected"
    return [
        str(row["symbol"])
        for row in ranking
        if isinstance(row, Mapping)
        and row.get(selected_key) is True
        and isinstance(row.get("symbol"), str)
    ]


def _investment_manager_for_cohort(
    cohort: list[Mapping[str, Any]],
    *,
    repository_root: Path,
) -> str | None:
    """Return the sealed manager identity for a manager-screen cohort."""

    run_id = _manager_screen_run_id_for_cohort(cohort)
    if run_id is None:
        return None
    allocation_bindings = {
        (
            item.get("manager_screen_allocation_result_path"),
            item.get("manager_screen_allocation_result_sha256"),
        )
        for item in cohort
        if item.get("manager_screen_allocation_result_path") is not None
        or item.get("manager_screen_allocation_result_sha256") is not None
    }
    if allocation_bindings:
        if len(allocation_bindings) != 1 or len(allocation_bindings) != len(
            {
                (
                    item.get("manager_screen_allocation_result_path"),
                    item.get("manager_screen_allocation_result_sha256"),
                )
                for item in cohort
            }
        ):
            raise ResearchAllocationError(
                "manager-bound profile cohort has inconsistent full-market bindings"
            )
        relative, expected_sha256 = next(iter(allocation_bindings))
        if not isinstance(relative, str) or not isinstance(expected_sha256, str):
            raise ResearchAllocationError("full-market allocation binding is incomplete")
        path = (repository_root / relative).resolve()
        try:
            path.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise ResearchAllocationError(
                "full-market allocation binding escapes repository root"
            ) from exc
        sealed = verify_sealed(path)
        if (
            sealed.artifact_type != "manager_screen_full_market_allocation_v3_result"
            or sealed.sha256 != expected_sha256
        ):
            raise ResearchAllocationError(
                "full-market allocation seal does not match the profile cohort"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("run_id") != run_id:
            raise ResearchAllocationError(
                "full-market allocation run does not match the profile cohort"
            )
        manager = payload.get("manager")
        if not isinstance(manager, Mapping):
            raise ResearchAllocationError(
                "full-market allocation is missing investment-manager provenance"
            )
        return _text(manager.get("agent"), "full_market_allocation.manager.agent")
    bindings = {
        (
            item.get("manager_screen_result_path"),
            item.get("manager_screen_result_sha256"),
        )
        for item in cohort
    }
    if len(bindings) != 1 or not all(
        isinstance(value, str) and value for binding in bindings for value in binding
    ):
        raise ResearchAllocationError(
            "manager-bound profile cohort has inconsistent result bindings"
        )
    relative, expected_sha256 = next(iter(bindings))
    path = (repository_root / str(relative)).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            "manager-screen result binding escapes repository root"
        ) from exc
    sealed = verify_sealed(path)
    if (
        sealed.artifact_type
        not in {
            "manager_screen_result",
            "manager_screen_legacy_transition_result",
            "manager_screen_quote_impact_result",
        }
        or sealed.sha256 != expected_sha256
    ):
        raise ResearchAllocationError(
            "manager-screen result seal does not match the profile cohort"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("run_id") not in {None, run_id}:
        raise ResearchAllocationError("manager-screen result run does not match the profile cohort")
    manager = payload.get("manager")
    if not isinstance(manager, Mapping):
        raise ResearchAllocationError(
            "manager-screen result is missing investment-manager provenance"
        )
    return _text(manager.get("agent"), "manager_screen_result.manager.agent")


def _profile_comparison_row(
    item: Mapping[str, Any],
    *,
    ordinal: int,
    cycle: str,
    stage: str,
    base: Path,
    repository_root: Path,
    canonical_full_market_v3: bool | None = None,
) -> dict[str, Any]:
    symbol = str(item["symbol"])
    completion = _latest_cycle_stage_completion_with_legacy_decline_migration(
        item,
        base=base,
        stage=stage,
        cycle=cycle,
        canonical_full_market_v3=canonical_full_market_v3,
    )
    profile_relative = completion.get("result_path") if completion is not None else None
    evaluation_relative = (
        completion.get("evaluation_path") if completion is not None else None
    )
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
        raise ResearchAllocationError(f"profile comparison artifact identity is invalid: {symbol}")
    provenance = package.get("provenance")
    sources = package.get("sources")
    adjudication = _profile_adjudication_for_profile_row(
        item,
        symbol=symbol,
        repository_root=repository_root,
        base=base,
    )
    current_next_stage = evaluated.get("next_stage")
    if (
        adjudication is not None
        and adjudication.get("profile_cycle_id") == cycle
        and adjudication.get("stage") == stage
    ):
        current_next_stage = adjudication["effective_outcome"]
    row = {
        "ordinal": ordinal,
        "symbol": symbol,
        "name": item.get("name"),
        "evaluated_stage": stage,
        "current_next_stage": current_next_stage,
        "evaluation_reason_codes": evaluated.get("reason_codes") or [],
        "profile": dict(profile),
        "analysis": dict(analysis),
        "source_count": len(sources) if isinstance(sources, list) else 0,
        "profile_path": profile_relative,
        "profile_sha256": sealed_profile.sha256,
        "evaluation_path": evaluation_relative,
        "evaluation_sha256": sealed_evaluation.sha256,
        "research_agent": (provenance.get("agent") if isinstance(provenance, Mapping) else None),
    }
    if adjudication is not None:
        row["profile_adjudication"] = adjudication
    return row


def _normalize_profile_decision_package(
    package: Mapping[str, Any],
    *,
    cycle: str,
    stage: str,
    comparison_sha256: str,
    comparison_rows: list[Mapping[str, Any]],
    finalized_at: dt.datetime,
) -> dict[str, Any]:
    if not isinstance(package, Mapping) or set(package) != PROFILE_DECISION_PACKAGE_KEYS:
        raise ResearchAllocationError(
            "profile allocation Agent decision fields do not match contract"
        )
    if package.get("schema_version") != 1:
        raise ResearchAllocationError("profile allocation Agent decision schema_version must be 1")
    if package.get("cycle_id") != cycle or package.get("evaluated_stage") != stage:
        raise ResearchAllocationError("profile allocation Agent decisions target the wrong cohort")
    if package.get("comparison_sha256") != comparison_sha256:
        raise ResearchAllocationError(
            "profile allocation Agent decisions are not bound to the comparison"
        )
    provenance = package.get("provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != PROVENANCE_KEYS:
        raise ResearchAllocationError("profile allocation Agent decision provenance is invalid")
    generated_at = _datetime(provenance.get("generated_at"), "decision.provenance.generated_at")
    if generated_at > finalized_at:
        raise ResearchAllocationError(
            "profile allocation Agent decisions cannot be generated in the future"
        )
    config = _profile_stage_config(stage)
    allowed = {config["select_decision"], "defer"}
    decisions = package.get("decisions")
    if not isinstance(decisions, list):
        raise ResearchAllocationError("profile allocation Agent decisions must be an array")
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
            raise ResearchAllocationError(f"duplicate profile allocation Agent decision: {symbol}")
        decision = _text(raw.get("decision"), "decision.decision")
        if decision not in allowed:
            raise ResearchAllocationError(f"unsupported profile allocation decision: {decision}")
        by_symbol[symbol] = {
            "symbol": symbol,
            "decision": decision,
            "reason": _text(raw.get("reason"), "decision.reason"),
            "decisive_question": _text(raw.get("decisive_question"), "decision.decisive_question"),
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
    for row in comparison_rows:
        symbol = str(row["symbol"])
        adjudication = row.get("profile_adjudication")
        adjudicated_terminal = bool(
            isinstance(adjudication, Mapping)
            or row.get("current_next_stage") == "needs_manual_review"
        )
        if adjudicated_terminal and by_symbol[symbol]["decision"] != "defer":
            raise ResearchAllocationError(
                "terminal profile adjudications must be deferred "
                f"without additional budget: {symbol}"
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
    selected_symbols = [item["symbol"] for item in payload["ranking"] if item["selected"] is True]
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
    screening_by_symbol = {item.get("symbol"): item for item in screening}
    adjudication_status = profile_adjudication_ledger_status(
        root=base,
        cycle_id=cycle,
    )
    full_market_authority = _full_market_v3_cycle_authority(
        base=base,
        repository_root=repository_root,
        cycle=cycle,
    )
    authority_errors: list[dict[str, str]] = []
    if full_market_authority is not None:
        selected = full_market_authority["selected"]
        cohort = (
            _bound_profile_cohort(
                queue,
                base=base,
                repository_root=repository_root,
                binding_field="manager_screen_allocation_result_path",
                binding=full_market_authority["result_path"],
                cycle=cycle,
                stage="quick_profile",
            )
            if selected
            else []
        )
        for item in cohort:
            symbol = str(item.get("symbol"))
            decision = selected[symbol]
            expected_queue = {
                "profile_cycle_id": cycle,
                "manager_screen_run_id": full_market_authority["run_id"],
                "manager_screen_allocation_result_path": full_market_authority[
                    "result_path"
                ],
                "manager_screen_allocation_result_sha256": full_market_authority[
                    "result_sha256"
                ],
                "manager_screen_allocation_candidate_sha256": selected[symbol][
                    "candidate_sha256"
                ],
                "manager_screen_allocation_decision": "fund_quick_profile",
                "research_budget_state": "funded_quick_profile",
                "decisive_question": decision["decisive_question"],
                "evidence_ids": list(decision["evidence_ids"]),
            }
            drifted = [
                f"queue.{field}"
                for field, value in expected_queue.items()
                if item.get(field) != value
            ]
            screen = screening_by_symbol.get(symbol)
            expected_screen = {
                "profile_cycle_id": cycle,
                "manager_screen_run_id": full_market_authority["run_id"],
                "manager_screen_allocation_result_path": full_market_authority[
                    "result_path"
                ],
                "manager_screen_allocation_result_sha256": full_market_authority[
                    "result_sha256"
                ],
                "manager_screen_allocation_candidate_sha256": decision[
                    "candidate_sha256"
                ],
                "manager_screen_allocation_decision": "fund_quick_profile",
                "research_budget_state": "funded_quick_profile",
                "decisive_question": decision["decisive_question"],
            }
            if not isinstance(screen, Mapping):
                drifted.append("screening.missing")
            else:
                drifted.extend(
                    f"screening.{field}"
                    for field, value in expected_screen.items()
                    if screen.get(field) != value
                )
            if drifted:
                authority_errors.append(
                    {
                        "symbol": symbol,
                        "error": "full_market_v3_authority_drift:" + ",".join(drifted),
                    }
                )
        cycle_rows = cohort
        allocation_sha = full_market_authority["result_sha256"]
    else:
        cycle_rows = [item for item in queue if item.get("profile_cycle_id") == cycle]
        cohort = []
        allocation_sha = None
    authority_error_symbols = {item["symbol"] for item in authority_errors}
    completion_by_symbol: dict[str, Mapping[str, Any]] = {}
    invalid_completion_symbols: list[str] = []
    for item in cycle_rows:
        symbol = str(item.get("symbol"))
        if symbol in authority_error_symbols:
            continue
        completion = _latest_cycle_stage_completion_with_legacy_decline_migration(
            item,
            base=base,
            stage="quick_profile",
            cycle=cycle,
            canonical_full_market_v3=(
                full_market_authority is not None and symbol in full_market_authority["selected"]
            ),
        )
        if completion is not None:
            completion_by_symbol[symbol] = completion
        elif _record_claims_cycle_stage_completion(
            item,
            stage="quick_profile",
            cycle=cycle,
        ):
            invalid_completion_symbols.append(symbol)
    recorded = [
        item for item in cycle_rows if str(item.get("symbol")) in completion_by_symbol
    ]
    if full_market_authority is None:
        allocation_shas = {
            item.get("allocation_sha256")
            for item in cycle_rows
            if item.get("allocation_sha256") is not None
        }
        if len(allocation_shas) > 1:
            raise ResearchAllocationError("profile cycle spans multiple allocations")
        allocation_sha = next(iter(allocation_shas), None)
        quick_profile_bindings = {
            binding
            for item in cycle_rows
            if (binding := _profile_predecessor_binding(item, stage="quick_profile")) is not None
        }
        if len(quick_profile_bindings) == 1:
            binding_field, binding_path = next(iter(quick_profile_bindings))
            cohort = _bound_profile_cohort(
                queue,
                base=base,
                repository_root=repository_root,
                binding_field=binding_field,
                binding=binding_path,
                cycle=cycle,
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
                else cycle_rows
            )
    recorded_symbols = {item["symbol"] for item in recorded}
    stage_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    invalid: list[dict[str, str]] = (
        authority_errors
        + list(adjudication_status["invalid_artifacts"])
        + [
        {
            "symbol": symbol,
            "error": "quick_profile_completion_authentication_failed",
        }
        for symbol in sorted(set(invalid_completion_symbols))
        ]
    )
    for item in recorded:
        completion = completion_by_symbol[str(item["symbol"])]
        status = str(item.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1
        screen = screening_by_symbol.get(item["symbol"])
        stage = str(screen.get("decision")) if isinstance(screen, Mapping) else "missing"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        for label, relative_path in (
            (
                "profile",
                completion.get("result_path"),
            ),
            (
                "evaluation",
                completion.get("evaluation_path"),
            ),
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
                invalid.append({"symbol": "__cycle__", "error": f"{stage}_comparison:{exc}"})
        if selection_path.exists():
            try:
                sealed = verify_sealed(selection_path)
                selection_finalized = sealed.artifact_type == f"{stage}_cross_company_selection"
                if not selection_finalized:
                    invalid.append(
                        {
                            "symbol": "__cycle__",
                            "error": f"{stage}_selection_artifact_type",
                        }
                    )
            except ValueError as exc:
                invalid.append({"symbol": "__cycle__", "error": f"{stage}_selection:{exc}"})
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
        "profile_adjudications": list(adjudication_status["profile_adjudications"]),
        "material_error_confirmed_count": adjudication_status[
            "material_error_confirmed_count"
        ],
        "manager_upheld_count": adjudication_status["manager_upheld_count"],
        "quarantined_count": adjudication_status["quarantined_count"],
        "quarantined_symbols": list(adjudication_status["quarantined_symbols"]),
        "stage_gates": stage_gates,
        "invalid_artifact_count": len(invalid),
        "invalid_artifacts": invalid,
    }


def _full_market_v3_cycle_authority(
    *,
    base: Path,
    repository_root: Path,
    cycle: str,
) -> dict[str, Any] | None:
    """Resolve a full-market profile cohort from its sealed singleton result.

    Queue fields are a mutable projection and cannot decide whether a v3 cycle
    still has v3 authority.  The canonical cycle name identifies the run; when
    its singleton result exists, that sealed result defines membership and all
    per-company bindings used by status authentication.
    """

    suffix = "-full-market-v3"
    if not cycle.endswith(suffix):
        return None
    run_id = cycle[: -len(suffix)]
    if not run_id or not CYCLE_RE.fullmatch(run_id):
        return None
    result_path = (
        base
        / "manager-screen"
        / run_id
        / "governance"
        / "allocation-v3"
        / "full-market"
        / "result.json"
    )
    seal_path = result_path.with_name(f"{result_path.name}.seal.json")
    if not result_path.exists() and not seal_path.exists():
        raise ResearchAllocationError(
            f"canonical full-market v3 profile authority singleton is missing: {cycle}"
        )
    try:
        from .manager_screen_full_market_allocation_v3 import (
            ManagerScreenFullMarketAllocationV3Error,
            load_manager_screen_full_market_allocation_v3_queue_bindings,
        )

        bindings = load_manager_screen_full_market_allocation_v3_queue_bindings(
            root=base,
            run_id=run_id,
        )
        sealed = verify_sealed(result_path)
    except (
        ManagerScreenFullMarketAllocationV3Error,
        OSError,
        SealingError,
        ValueError,
    ) as exc:
        raise ResearchAllocationError(
            f"full-market v3 profile authority is invalid: {cycle}"
        ) from exc
    if sealed.artifact_type != "manager_screen_full_market_allocation_v3_result":
        raise ResearchAllocationError(
            f"full-market v3 profile authority type is invalid: {cycle}"
        )
    relative = result_path.resolve().relative_to(repository_root.resolve()).as_posix()
    if any(
        binding.get("result_path") != relative
        or binding.get("result_sha256") != sealed.sha256
        for binding in bindings.values()
    ):
        raise ResearchAllocationError(
            f"full-market v3 profile bindings are inconsistent: {cycle}"
        )
    selected = {
        symbol: dict(binding)
        for symbol, binding in bindings.items()
        if binding.get("decision") == "fund_quick_profile"
    }
    return {
        "run_id": run_id,
        "result_path": relative,
        "result_sha256": sealed.sha256,
        "selected": selected,
    }


def _bound_profile_cohort(
    queue: list[dict[str, Any]],
    *,
    base: Path,
    repository_root: Path,
    binding_field: str,
    binding: str,
    cycle: str,
    stage: str,
) -> list[dict[str, Any]]:
    """Return the full cohort selected by its immutable predecessor.

    The sealed predecessor defines membership.  Mutable task/history fields
    may report completion or drift, but must never silently shrink the cohort.
    """

    selection_path = repository_root / binding
    if not selection_path.exists():
        # Backward compatibility for legacy queues whose predecessor selection
        # was not stored as a sealed repository asset.
        legacy_rows = [
            item
            for item in queue
            if item.get(binding_field) == binding
            and (
                item.get("task_type") == stage
                or _latest_cycle_stage_completion(
                    item,
                    base=base,
                    stage=stage,
                    cycle=cycle,
                )
                is not None
            )
        ]
        if binding_field in {
            "manager_screen_allocation_result_path",
            "manager_screen_result_path",
        } or any(
            item.get("manager_screen_run_id") is not None
            or _has_manager_screen_provenance(item)
            for item in legacy_rows
        ):
            raise ResearchAllocationError(
                f"manager-bound {stage} predecessor selection is missing: {binding}"
            )
        return legacy_rows
    sealed = verify_sealed(selection_path)
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    selected_symbols = list(
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
    if len(selected_symbols) != len(set(selected_symbols)):
        raise ResearchAllocationError(f"predecessor selection duplicates a {stage} symbol")
    queue_by_symbol: dict[str, dict[str, Any]] = {}
    for item in queue:
        symbol = item.get("symbol")
        if not isinstance(symbol, str):
            continue
        if symbol in queue_by_symbol:
            raise ResearchAllocationError(f"research queue duplicates one symbol: {symbol}")
        queue_by_symbol[symbol] = item
    missing = [symbol for symbol in selected_symbols if symbol not in queue_by_symbol]
    if missing:
        raise ResearchAllocationError(
            f"predecessor selection references missing queue symbols: {missing[:10]}"
        )
    return [queue_by_symbol[symbol] for symbol in selected_symbols]


def _validate_package(package: Mapping[str, Any], *, recorded_at: dt.datetime) -> dict[str, Any]:
    _reject_probable_gbk_mojibake(package)
    if not isinstance(package, Mapping) or set(package) not in {
        frozenset(PACKAGE_KEYS),
        frozenset(MANAGER_BOUND_PACKAGE_KEYS),
        frozenset(ADJUDICATED_MANAGER_BOUND_PACKAGE_KEYS),
    }:
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
    manager_binding = None
    adjudication_binding = None
    decisive_answer = None
    if "manager_screen_binding" in package:
        manager_binding = _normalize_manager_screen_binding(package.get("manager_screen_binding"))
        decisive_answer = _normalize_decisive_answer(
            package.get("decisive_answer"),
            source_ids=source_ids,
        )
        if "profile_adjudication_binding" in package:
            adjudication_binding = _normalize_profile_adjudication_research_binding(
                package.get("profile_adjudication_binding")
            )
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

    normalized = {
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
    if manager_binding is not None:
        normalized["manager_screen_binding"] = manager_binding
        normalized["decisive_answer"] = decisive_answer
    if adjudication_binding is not None:
        normalized["profile_adjudication_binding"] = adjudication_binding
    return normalized


def _normalize_manager_screen_binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != MANAGER_SCREEN_BINDING_KEYS:
        raise ResearchAllocationError("manager_screen_binding fields do not match contract")
    result_sha256 = _text(value.get("result_sha256"), "manager_screen_binding.result_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", result_sha256):
        raise ResearchAllocationError(
            "manager_screen_binding.result_sha256 must be lowercase SHA-256"
        )
    return {
        "result_path": _text(value.get("result_path"), "manager_screen_binding.result_path"),
        "result_sha256": result_sha256,
        "decisive_question": _text(
            value.get("decisive_question"),
            "manager_screen_binding.decisive_question",
        ),
        "evidence_ids": _text_array(
            value.get("evidence_ids"),
            "manager_screen_binding.evidence_ids",
            allow_empty=False,
        ),
    }


def _normalize_profile_adjudication_research_binding(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != PROFILE_ADJUDICATION_RESEARCH_BINDING_KEYS
    ):
        raise ResearchAllocationError(
            "profile_adjudication_binding fields do not match contract"
        )
    sha256 = _profile_adjudication_sha256(
        value.get("sha256"),
        "profile_adjudication_binding.sha256",
    )
    return {
        "path": _text(value.get("path"), "profile_adjudication_binding.path"),
        "sha256": sha256,
        "corrected_decisive_question": _text(
            value.get("corrected_decisive_question"),
            "profile_adjudication_binding.corrected_decisive_question",
        ),
        "evidence_ids": _text_array(
            value.get("evidence_ids"),
            "profile_adjudication_binding.evidence_ids",
            allow_empty=False,
        ),
    }


def _normalize_profile_claim_attempt_binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != PROFILE_CLAIM_ATTEMPT_KEYS:
        raise ResearchAllocationError("profile claim_attempt fields do not match contract")
    sha256 = _text(value.get("sha256"), "claim_attempt.sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ResearchAllocationError("claim_attempt.sha256 must be lowercase SHA-256")
    attempt_number = value.get("attempt_number")
    if (
        not isinstance(attempt_number, int)
        or isinstance(attempt_number, bool)
        or attempt_number < 1
    ):
        raise ResearchAllocationError("claim_attempt.attempt_number is invalid")
    authorization = value.get("stage_authorization")
    if (
        not isinstance(authorization, Mapping)
        or set(authorization) != PROFILE_CLAIM_AUTHORIZATION_KEYS
    ):
        raise ResearchAllocationError(
            "claim_attempt.stage_authorization fields do not match contract"
        )
    authorization_sha256 = _text(
        authorization.get("sha256"),
        "claim_attempt.stage_authorization.sha256",
    )
    if not re.fullmatch(r"[0-9a-f]{64}", authorization_sha256):
        raise ResearchAllocationError(
            "claim_attempt.stage_authorization.sha256 must be lowercase SHA-256"
        )
    return {
        "path": _text(value.get("path"), "claim_attempt.path"),
        "sha256": sha256,
        "sealed_at": _datetime(
            value.get("sealed_at"),
            "claim_attempt.sealed_at",
        ).isoformat(),
        "attempt_number": attempt_number,
        "agent": _text(value.get("agent"), "claim_attempt.agent"),
        "stage_authorization": {
            "path": _text(
                authorization.get("path"),
                "claim_attempt.stage_authorization.path",
            ),
            "sha256": authorization_sha256,
            "artifact_type": _text(
                authorization.get("artifact_type"),
                "claim_attempt.stage_authorization.artifact_type",
            ),
            "sealed_at": _datetime(
                authorization.get("sealed_at"),
                "claim_attempt.stage_authorization.sealed_at",
            ).isoformat(),
        },
    }


def _normalize_decisive_answer(value: Any, *, source_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != DECISIVE_ANSWER_KEYS:
        raise ResearchAllocationError("decisive_answer fields do not match contract")
    referenced = _text_array(
        value.get("source_ids"), "decisive_answer.source_ids", allow_empty=False
    )
    unknown = set(referenced) - source_ids
    if unknown:
        raise ResearchAllocationError(
            f"decisive_answer references unknown sources: {sorted(unknown)}"
        )
    unresolved = value.get("unresolved_reason")
    if unresolved is not None:
        unresolved = _text(unresolved, "decisive_answer.unresolved_reason")
    return {
        "conclusion": _text(value.get("conclusion"), "decisive_answer.conclusion"),
        "source_ids": referenced,
        "unresolved_reason": unresolved,
    }


def _validate_manager_bound_submission(
    package: Mapping[str, Any],
    *,
    queue_record: Mapping[str, Any],
    base: Path,
    repository_root: Path,
    symbol: str,
    full_market_grant: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    claim_attempt = None
    sealed_authority_exists = _sealed_modern_profile_authority_exists(
        base=base,
        repository_root=repository_root,
        queue_record=queue_record,
        symbol=symbol,
        stage=str(queue_record.get("task_type")),
    )
    if _requires_sealed_profile_stage_claim(queue_record) or sealed_authority_exists:
        try:
            claim_attempt = verify_active_profile_stage_claim(
                root=base,
                queue_record=queue_record,
                stage=str(queue_record.get("task_type")),
            )
        except ProfileStageClaimError as exc:
            raise ResearchAllocationError(str(exc)) from exc
        if claim_attempt.get("agent") != package["provenance"]["agent"]:
            raise ResearchAllocationError(
                "profile provenance agent does not match the sealed active claim"
            )
    _require_profile_adjudication_package_binding(
        package,
        queue_record=queue_record,
        symbol=symbol,
        base=base,
        repository_root=repository_root,
    )
    result_path = queue_record.get("manager_screen_result_path")
    if (not isinstance(result_path, str) or not result_path) and full_market_grant is None:
        return claim_attempt
    binding = package.get("manager_screen_binding")
    answer = package.get("decisive_answer")
    if not isinstance(binding, Mapping) or not isinstance(answer, Mapping):
        raise ResearchAllocationError(
            "manager-bound profile requires manager_screen_binding and decisive_answer"
        )
    locked_remediation = queue_record.get(LOCKED_CALIBRATION_REMEDIATION_FIELD)
    if (
        queue_record.get("task_type") == "targeted_followup"
        and isinstance(locked_remediation, Mapping)
        and locked_remediation.get("remediation") == "targeted_remediation_candidate"
    ):
        _validate_targeted_followup_task_approval(
            queue_record,
            repository_root=repository_root,
        )
        expected = {
            "result_path": locked_remediation.get("allocation_result_path"),
            "result_sha256": locked_remediation.get("allocation_result_sha256"),
            "decisive_question": locked_remediation.get("decisive_question"),
            "evidence_ids": list(locked_remediation.get("evidence_ids") or []),
        }
        if dict(binding) != expected:
            raise ResearchAllocationError(
                "profile manager_screen_binding does not match the locked calibration brief"
            )
        if queue_record.get("status") != "running":
            raise ResearchAllocationError(
                "manager-bound profile must be claimed before it can be recorded"
            )
        if queue_record.get("assigned_agent") != package["provenance"]["agent"]:
            raise ResearchAllocationError(
                "manager-bound profile provenance must match the claimed agent"
            )
        return claim_attempt
    if full_market_grant is None:
        expected = {
            "result_path": result_path,
            "result_sha256": queue_record.get("manager_screen_result_sha256"),
            "decisive_question": queue_record.get("decisive_question"),
            "evidence_ids": list(queue_record.get("evidence_ids") or []),
        }
    else:
        decision = full_market_grant["decision"]
        expected = {
            "result_path": full_market_grant["result_path"],
            "result_sha256": full_market_grant["result_sha256"],
            "decisive_question": decision["decisive_question"],
            "evidence_ids": list(decision["evidence_ids"]),
        }
    if dict(binding) != expected:
        raise ResearchAllocationError(
            "profile manager_screen_binding does not match the claimed manager decision"
        )
    if full_market_grant is not None:
        if queue_record.get("status") != "running":
            raise ResearchAllocationError(
                "manager-bound profile must be claimed before it can be recorded"
            )
        if queue_record.get("assigned_agent") != package["provenance"]["agent"]:
            raise ResearchAllocationError(
                "manager-bound profile provenance must match the claimed agent"
            )
        return claim_attempt
    sealed_result_path = (repository_root / result_path).resolve()
    try:
        sealed_result_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            "manager-screen result binding escapes repository root"
        ) from exc
    try:
        sealed = verify_sealed(sealed_result_path)
        result = json.loads(sealed_result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError(
            "manager-bound profile references an invalid sealed manager result"
        ) from exc
    if (
        sealed.artifact_type
        not in {
            "manager_screen_result",
            "manager_screen_quote_impact_result",
            "manager_screen_legacy_transition_result",
        }
        or sealed.sha256 != expected["result_sha256"]
        or not isinstance(result, Mapping)
    ):
        raise ResearchAllocationError(
            "manager-bound profile result seal does not match the claimed manager decision"
        )
    run_id = queue_record.get("manager_screen_run_id")
    batch_id = queue_record.get("manager_screen_batch_id")
    if (isinstance(run_id, str) and result.get("run_id") not in {None, run_id}) or (
        isinstance(batch_id, str) and result.get("batch_id") not in {None, batch_id}
    ):
        raise ResearchAllocationError(
            "manager-bound profile result identity does not match the queue"
        )
    decisions = result.get("decisions")
    matching = (
        [
            decision
            for decision in decisions
            if isinstance(decision, Mapping) and decision.get("symbol") == symbol
        ]
        if isinstance(decisions, list)
        else []
    )
    if len(matching) != 1:
        raise ResearchAllocationError(
            "manager-bound profile result does not contain exactly one company decision"
        )
    sealed_decision = matching[0]
    sealed_expected = {
        "decisive_question": sealed_decision.get("decisive_question"),
        "evidence_ids": list(sealed_decision.get("evidence_ids") or []),
    }
    if (
        expected["decisive_question"] != sealed_expected["decisive_question"]
        or expected["evidence_ids"] != sealed_expected["evidence_ids"]
        or (
            isinstance(queue_record.get("manager_screen_route"), str)
            and queue_record.get("manager_screen_route") != sealed_decision.get("route")
        )
    ):
        raise ResearchAllocationError(
            "manager-bound profile queue fields do not match the sealed manager decision"
        )
    if queue_record.get("status") != "running":
        raise ResearchAllocationError(
            "manager-bound profile must be claimed before it can be recorded"
        )
    if queue_record.get("assigned_agent") != package["provenance"]["agent"]:
        raise ResearchAllocationError(
            "manager-bound profile provenance must match the claimed agent"
        )
    return claim_attempt


def _sealed_modern_profile_authority_exists(
    *,
    base: Path,
    repository_root: Path,
    queue_record: Mapping[str, Any],
    symbol: str,
    stage: str,
) -> bool:
    """Rebuild modern authority from seals when mutable provenance was stripped."""

    if stage not in {"quick_profile", "targeted_followup", "scoped_research", "deep_research"}:
        return False
    try:
        if sealed_profile_stage_claim_authority_exists(
            root=base,
            symbol=symbol,
            stage=stage,
        ):
            return True
    except ProfileStageClaimError as exc:
        raise ResearchAllocationError(str(exc)) from exc

    relevant_types = {
        "quick_profile": {
            "manager_screen_result",
            "manager_screen_quote_impact_result",
            "manager_screen_legacy_transition_result",
            "manager_screen_full_market_allocation_v3_result",
        },
        "targeted_followup": {"targeted_followup_approval"},
        "scoped_research": {"quick_profile_cross_company_selection"},
        "deep_research": {"scoped_research_cross_company_selection"},
    }[stage]
    roots = [base / "manager-screen"] if stage == "quick_profile" else [base / "profiles"]
    expected_run = queue_record.get("manager_screen_run_id")
    expected_cycle = queue_record.get("profile_cycle_id")
    for root in roots:
        if not root.is_dir():
            continue
        for payload_path in sorted(root.rglob("*.json")):
            if payload_path.name.endswith(".seal.json"):
                continue
            seal_path = payload_path.with_name(f"{payload_path.name}.seal.json")
            if not seal_path.is_file():
                raise ResearchAllocationError(
                    "modern profile authority ledger contains a payload without seal"
                )
        for seal_path in sorted(root.rglob("*.seal.json")):
            payload_path = seal_path.with_name(seal_path.name[: -len(".seal.json")])
            if not payload_path.is_file():
                raise ResearchAllocationError(
                    "modern profile authority ledger contains a seal without payload"
                )
            try:
                sealed = verify_sealed(payload_path)
            except (OSError, SealingError, ValueError) as exc:
                raise ResearchAllocationError(
                    "modern profile authority ledger contains an invalid seal"
                ) from exc
            if sealed.artifact_type not in relevant_types:
                continue
            try:
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ResearchAllocationError(
                    "modern profile authority payload is invalid"
                ) from exc
            if not isinstance(payload, Mapping):
                raise ResearchAllocationError("modern profile authority payload must be an object")
            payload_run = payload.get("manager_screen_run_id", payload.get("run_id"))
            payload_cycle = payload.get("cycle_id", payload.get("profile_cycle_id"))
            if isinstance(expected_run, str) and payload_run not in {None, expected_run}:
                continue
            if isinstance(expected_cycle, str) and payload_cycle not in {None, expected_cycle}:
                continue
            if _sealed_authority_selects_symbol(
                payload,
                artifact_type=sealed.artifact_type,
                symbol=symbol,
            ):
                try:
                    payload_path.resolve().relative_to(repository_root.resolve())
                except ValueError as exc:
                    raise ResearchAllocationError(
                        "modern profile authority path escapes repository root"
                    ) from exc
                return True
    return False


def _sealed_authority_selects_symbol(
    payload: Mapping[str, Any],
    *,
    artifact_type: str,
    symbol: str,
) -> bool:
    if artifact_type == "targeted_followup_approval":
        return payload.get("symbol") == symbol
    decisions = payload.get("decisions")
    if isinstance(decisions, list):
        matching = [
            row for row in decisions if isinstance(row, Mapping) and row.get("symbol") == symbol
        ]
        if len(matching) > 1:
            raise ResearchAllocationError("modern profile authority duplicates one symbol")
        if matching:
            decision = matching[0]
            return bool(
                decision.get("decision") == "fund_quick_profile"
                or decision.get("route") in {"send_to_analyst", "research_candidate"}
            )
    ranking = payload.get("ranking")
    if isinstance(ranking, list):
        matching = [
            row for row in ranking if isinstance(row, Mapping) and row.get("symbol") == symbol
        ]
        if len(matching) > 1:
            raise ResearchAllocationError("modern profile stage selection duplicates one symbol")
        return bool(matching and matching[0].get("selected") is True)
    return False


def _validate_full_market_profile_binding(
    package: Mapping[str, Any],
    *,
    queue_record: Mapping[str, Any],
    screen_record: Mapping[str, Any],
    root: Path,
    repository_root: Path,
    symbol: str,
) -> Mapping[str, Any] | None:
    required = _requires_funded_full_market_grant(queue_record)
    return _verify_funded_full_market_profile_grant(
        queue_record=queue_record,
        screen_record=screen_record,
        root=root,
        repository_root=repository_root,
        symbol=symbol,
        expected_cycle_id=package.get("cycle_id"),
        required=required,
        context="profile record",
        require_screen_research_brief=True,
    )


def _requires_funded_full_market_grant(record: Mapping[str, Any]) -> bool:
    return bool(
        record.get("manager_screen_route") == "research_candidate"
        or record.get("preceding_stage") == "manager_screen_allocation_v3"
        or any(record.get(field) is not None for field in FULL_MARKET_ALLOCATION_BINDING_FIELDS)
    )


def _record_has_full_market_v3_profile_authority(record: Mapping[str, Any]) -> bool:
    if _requires_funded_full_market_grant(record):
        return True
    history = record.get("stage_history")
    return bool(
        isinstance(history, list)
        and any(
            isinstance(event, Mapping)
            and event.get("stage") == "manager_screen_allocation_v3"
            and event.get("status") == "completed"
            for event in history
        )
    )


def _record_has_canonical_full_market_v3_profile_authority(
    record: Mapping[str, Any],
    *,
    base: Path,
    cycle: str,
) -> bool:
    symbol = record.get("symbol")
    if not isinstance(symbol, str):
        return False
    authority = _full_market_v3_cycle_authority(
        base=base,
        repository_root=base.parent.parent,
        cycle=cycle,
    )
    return bool(authority is not None and symbol in authority["selected"])


def _load_full_market_profile_grant_context(
    *,
    root: Path,
    repository_root: Path,
    run_id: str,
    verified_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load one verified result/packet pair for semantic profile checks.

    The public full-market verifier authenticates the complete packet and all
    of its source dependencies.  This loader then keeps the exact packet
    candidate beside the result decision so claim, record, and follow-up paths
    cannot validate only the mutable JSONL projection.
    """

    from .manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        verify_manager_screen_full_market_allocation_v3_result,
    )

    try:
        result = (
            dict(verified_result)
            if verified_result is not None
            else verify_manager_screen_full_market_allocation_v3_result(
                root=root,
                run_id=run_id,
            )
        )
    except ManagerScreenFullMarketAllocationV3Error as exc:
        raise ResearchAllocationError("sealed full-market allocation result is invalid") from exc
    result_path = (
        root
        / "manager-screen"
        / run_id
        / "governance"
        / "allocation-v3"
        / "full-market"
        / "result.json"
    ).resolve()
    packet_path = result_path.with_name("packet.json")
    try:
        result_relative = result_path.relative_to(repository_root.resolve()).as_posix()
        packet_relative = packet_path.relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ResearchAllocationError(
            "full-market allocation path escapes repository root"
        ) from exc
    try:
        packet_seal = verify_sealed(packet_path)
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ResearchAllocationError("sealed full-market allocation packet is invalid") from exc
    if (
        packet_seal.artifact_type != "manager_screen_full_market_allocation_v3_packet"
        or not isinstance(packet, Mapping)
        or packet.get("run_id") != run_id
        or result.get("run_id") != run_id
        or result.get("packet_path") != packet_relative
        or result.get("packet_sha256") != packet_seal.sha256
        or not re.fullmatch(r"[0-9a-f]{64}", str(result.get("result_sha256")))
    ):
        raise ResearchAllocationError("full-market allocation result and packet binding is invalid")
    raw_decisions = result.get("decisions")
    raw_candidates = packet.get("candidates")
    if not isinstance(raw_decisions, list) or not isinstance(raw_candidates, list):
        raise ResearchAllocationError("full-market allocation grant arrays are invalid")
    decisions = {
        item.get("symbol"): item
        for item in raw_decisions
        if isinstance(item, Mapping) and isinstance(item.get("symbol"), str)
    }
    candidates = {
        item.get("symbol"): item
        for item in raw_candidates
        if isinstance(item, Mapping) and isinstance(item.get("symbol"), str)
    }
    if len(decisions) != len(raw_decisions) or len(candidates) != len(raw_candidates):
        raise ResearchAllocationError(
            "full-market allocation grant symbols are missing or duplicated"
        )
    return {
        "run_id": run_id,
        "result": result,
        "result_path": result_relative,
        "result_sha256": result["result_sha256"],
        "packet": packet,
        "decisions": decisions,
        "candidates": candidates,
    }


def _full_market_calibration_projection(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    calibration = candidate.get("calibration_material_error")
    if not isinstance(calibration, Mapping):
        return {}
    return {
        "manager_screen_calibration_result_path": calibration.get("calibration_result_path"),
        "manager_screen_calibration_result_sha256": calibration.get("calibration_result_sha256"),
        "manager_screen_calibration_review_sha256": calibration.get("review_sha256"),
        "manager_screen_calibration_adjudication_sha256": calibration.get("adjudication_sha256"),
    }


def _validate_full_market_calibration_projection(
    record: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    context: str,
) -> None:
    for field in FULL_MARKET_CALIBRATION_BINDING_FIELDS:
        if field in expected:
            if record.get(field) != expected[field]:
                raise ResearchAllocationError(
                    f"{context} calibration binding does not match the sealed candidate"
                )
        elif field in record:
            raise ResearchAllocationError(
                f"{context} has a calibration binding absent from the sealed candidate"
            )


def _verify_funded_full_market_profile_grant(
    *,
    queue_record: Mapping[str, Any],
    screen_record: Mapping[str, Any] | None,
    root: Path,
    repository_root: Path,
    symbol: str,
    expected_cycle_id: Any,
    required: bool,
    context: str,
    grant_context: Mapping[str, Any] | None = None,
    require_screen_research_brief: bool = False,
) -> Mapping[str, Any] | None:
    """Verify one funded grant against its result, packet, and live projection."""

    result_relative = queue_record.get("manager_screen_allocation_result_path")
    if result_relative is None:
        if required:
            raise ResearchAllocationError(
                f"{context} is not backed by a funded full-market allocation"
            )
        return None
    if not isinstance(result_relative, str) or not result_relative:
        raise ResearchAllocationError("full-market allocation result path is invalid")
    run_id = queue_record.get("manager_screen_run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ResearchAllocationError("full-market allocation run binding is missing")
    loaded = (
        dict(grant_context)
        if grant_context is not None
        else _load_full_market_profile_grant_context(
            root=root,
            repository_root=repository_root,
            run_id=run_id,
        )
    )
    if loaded.get("run_id") != run_id:
        raise ResearchAllocationError(f"{context} full-market grant context belongs to another run")
    result = loaded["result"]
    decision = loaded["decisions"].get(symbol)
    candidate = loaded["candidates"].get(symbol)
    expected_relative = loaded["result_path"]
    common_projection = {
        "manager_screen_allocation_result_path": expected_relative,
        "manager_screen_allocation_result_sha256": loaded["result_sha256"],
        "manager_screen_allocation_candidate_sha256": (
            decision.get("candidate_sha256") if isinstance(decision, Mapping) else None
        ),
        "manager_screen_allocation_decision": "fund_quick_profile",
    }
    source_projection = {
        "manager_screen_run_id": run_id,
        "manager_screen_batch_id": (
            candidate.get("prior_queue_row", {}).get("manager_screen_batch_id")
            if isinstance(candidate, Mapping)
            and isinstance(candidate.get("prior_queue_row"), Mapping)
            else None
        ),
        "manager_screen_route": (
            candidate.get("original_route") if isinstance(candidate, Mapping) else None
        ),
        "manager_screen_result_path": (
            candidate.get("effective_decision_source_path")
            if isinstance(candidate, Mapping)
            else None
        ),
        "manager_screen_result_sha256": (
            candidate.get("effective_decision_source_sha256")
            if isinstance(candidate, Mapping)
            else None
        ),
    }
    if (
        result.get("run_id") != run_id
        or not isinstance(decision, Mapping)
        or not isinstance(candidate, Mapping)
        or decision.get("decision") != "fund_quick_profile"
        or decision.get("candidate_sha256") != candidate.get("candidate_sha256")
        or any(queue_record.get(key) != value for key, value in common_projection.items())
        or any(queue_record.get(key) != value for key, value in source_projection.items())
        or queue_record.get("decisive_question") != decision.get("decisive_question")
        or list(queue_record.get("evidence_ids") or []) != list(decision.get("evidence_ids") or [])
        or queue_record.get("allocation_sha256") != loaded["result_sha256"]
        or queue_record.get("profile_cycle_id") != result.get("profile_cycle_id")
        or expected_cycle_id != result.get("profile_cycle_id")
        or queue_record.get("research_budget_state") != "funded_quick_profile"
        or (
            screen_record is not None
            and (
                any(screen_record.get(key) != value for key, value in common_projection.items())
                or any(screen_record.get(key) != value for key, value in source_projection.items())
                or screen_record.get("profile_cycle_id") != result.get("profile_cycle_id")
                or screen_record.get("research_budget_state") != "funded_quick_profile"
                or screen_record.get("decisive_question") != decision.get("decisive_question")
                or (
                    require_screen_research_brief
                    and list(screen_record.get("evidence") or [])
                    != list(decision.get("evidence_ids") or [])
                )
            )
        )
    ):
        raise ResearchAllocationError(
            f"{context} does not match its sealed full-market allocation grant"
        )
    expected_calibration = _full_market_calibration_projection(candidate)
    _validate_full_market_calibration_projection(
        queue_record,
        expected=expected_calibration,
        context=f"{context} queue",
    )
    if screen_record is not None:
        _validate_full_market_calibration_projection(
            screen_record,
            expected=expected_calibration,
            context=f"{context} screening",
        )
    return {
        **loaded,
        "decision": decision,
        "candidate": candidate,
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
    payload = {
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
        "manager_screen_run_id": record.get("manager_screen_run_id"),
        "manager_screen_batch_id": record.get("manager_screen_batch_id"),
        "manager_screen_result_path": record.get("manager_screen_result_path"),
        "manager_screen_result_sha256": record.get("manager_screen_result_sha256"),
        "manager_screen_allocation_result_path": record.get(
            "manager_screen_allocation_result_path"
        ),
        "manager_screen_allocation_result_sha256": record.get(
            "manager_screen_allocation_result_sha256"
        ),
        "manager_screen_allocation_candidate_sha256": record.get(
            "manager_screen_allocation_candidate_sha256"
        ),
        "manager_screen_allocation_decision": record.get("manager_screen_allocation_decision"),
        "manager_screen_calibration_result_path": record.get(
            "manager_screen_calibration_result_path"
        ),
        "manager_screen_calibration_result_sha256": record.get(
            "manager_screen_calibration_result_sha256"
        ),
        "manager_screen_calibration_review_sha256": record.get(
            "manager_screen_calibration_review_sha256"
        ),
        "manager_screen_calibration_adjudication_sha256": record.get(
            "manager_screen_calibration_adjudication_sha256"
        ),
        "profile_cycle_id": record.get("profile_cycle_id"),
        "decisive_question": record.get("decisive_question"),
        "evidence_ids": record.get("evidence_ids") or [],
        "idempotent": idempotent,
        "portfolio_action": None,
    }
    if isinstance(record.get("profile_adjudication_path"), str):
        evidence_ids = record.get("profile_adjudication_evidence_ids")
        payload["profile_adjudication_binding"] = {
            "path": record.get("profile_adjudication_path"),
            "sha256": record.get("profile_adjudication_sha256"),
            "corrected_decisive_question": record.get(
                "profile_adjudication_decisive_question"
            ),
            "evidence_ids": list(evidence_ids) if isinstance(evidence_ids, list) else [],
        }
        payload["profile_adjudication_outcome"] = record.get(
            "profile_adjudication_outcome"
        )
    return payload


def _claim_stage(value: str | None, *, default_for_symbol_less: bool) -> str | None:
    if value is None:
        return "quick_profile" if default_for_symbol_less else None
    result = _text(value, "stage")
    allowed = {
        "quick_profile",
        "targeted_followup",
        "scoped_research",
        "deep_research",
    }
    if result not in allowed:
        raise ResearchAllocationError(f"unsupported profile claim stage: {result}")
    return result


def _optional_identifier(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    result = _text(value, label)
    if not CYCLE_RE.fullmatch(result):
        raise ResearchAllocationError(f"{label} is invalid")
    return result


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


def _latest_cycle_stage_completion(
    record: Mapping[str, Any],
    *,
    base: Path,
    stage: str,
    cycle: str,
    require_claim: bool = False,
) -> Mapping[str, Any] | None:
    """Return the latest authenticated completion in one profile cycle.

    ``stage_history`` is a mutable projection and is therefore only an index.
    A path that happens to contain the cycle identifier is not completion
    evidence.  Profile stages must resolve to their sealed package/evaluation
    pair and, when a sealed stage authority exists, to the canonical
    claim/success chain.  Manager declines and deep research use their own
    sealed terminal receipts.
    """

    history = record.get("stage_history")
    if not isinstance(history, list) or not history:
        return None
    for item in reversed(history):
        if (
            not isinstance(item, Mapping)
            or item.get("stage") != stage
            or item.get("status") != "completed"
        ):
            continue
        if not _completion_event_claims_cycle(item, stage=stage, cycle=cycle):
            continue
        if (
            _completion_event_is_unique(record, item, stage=stage)
            and _cycle_stage_completion_is_authenticated(
                record,
                item,
                base=base,
                stage=stage,
                cycle=cycle,
                require_claim=require_claim,
            )
        ):
            return item
        # A newest same-cycle completion claim that fails authentication is an
        # integrity error.  Never fall back to an older event and hide it.
        return None
    return None


def _latest_cycle_stage_history_path(
    record: Mapping[str, Any],
    *,
    base: Path,
    stage: str,
    cycle: str,
    key: str,
) -> str | None:
    completion = _latest_cycle_stage_completion(
        record,
        base=base,
        stage=stage,
        cycle=cycle,
    )
    value = completion.get(key) if completion is not None else None
    return value if isinstance(value, str) else None


def _completion_event_claims_cycle(
    event: Mapping[str, Any],
    *,
    stage: str,
    cycle: str,
) -> bool:
    keys = (
        ("decline_path",)
        if stage == "targeted_followup_decline"
        else ("completion_path", "claim_path")
        if stage == "deep_research"
        else ("result_path", "evaluation_path", "claim_path", "success_path")
    )
    cycle_segment = f"/profiles/{cycle}/"
    return any(
        isinstance(event.get(key), str)
        and cycle_segment in ("/" + str(event[key]).replace("\\", "/"))
        for key in keys
    )


def _record_claims_cycle_stage_completion(
    record: Mapping[str, Any],
    *,
    stage: str,
    cycle: str,
) -> bool:
    history = record.get("stage_history")
    return bool(
        isinstance(history, list)
        and any(
            isinstance(event, Mapping)
            and event.get("stage") == stage
            and event.get("status") == "completed"
            and _completion_event_claims_cycle(event, stage=stage, cycle=cycle)
            for event in history
        )
    )


def _completion_event_is_unique(
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    stage: str,
) -> bool:
    if isinstance(event.get("claim_path"), str):
        identity_keys = ("claim_path", "claim_sha256")
    elif stage == "targeted_followup_decline":
        identity_keys = ("decline_path", "decline_sha256")
    elif stage == "deep_research":
        identity_keys = ("completion_path", "completion_sha256")
    else:
        identity_keys = ("result_path", "evaluation_path")
    identity = tuple(event.get(key) for key in identity_keys)
    if any(not isinstance(value, str) or not value for value in identity):
        return False
    matches = [
        candidate
        for candidate in (record.get("stage_history") or [])
        if isinstance(candidate, Mapping)
        and candidate.get("stage") == stage
        and candidate.get("status") == "completed"
        and tuple(candidate.get(key) for key in identity_keys) == identity
    ]
    return len(matches) == 1


def _latest_cycle_stage_completion_for_legacy_materialization(
    record: Mapping[str, Any],
    *,
    base: Path,
    stage: str,
    cycle: str,
) -> Mapping[str, Any] | None:
    """Preserve score-era replay fixtures without weakening manager workflows.

    The legacy score-based finalizer predates sealed per-stage receipts.  It is
    still retained for historical compatibility, but is forbidden as soon as
    manager-screen provenance exists.  Modern comparison, status and claim
    paths never use this fallback.
    """

    canonical_full_market_v3 = (
        _record_has_canonical_full_market_v3_profile_authority(
            record,
            base=base,
            cycle=cycle,
        )
    )
    modern_authority = bool(
        record.get("manager_screen_run_id") is not None
        or _has_manager_screen_provenance(record)
        or canonical_full_market_v3
    )
    authenticated = _latest_cycle_stage_completion(
        record,
        base=base,
        stage=stage,
        cycle=cycle,
        require_claim=modern_authority,
    )
    if authenticated is not None:
        return authenticated
    if (
        record.get("profile_cycle_id") != cycle
        or modern_authority
    ):
        return None
    history = record.get("stage_history")
    if not isinstance(history, list):
        return None
    for event in reversed(history):
        if (
            isinstance(event, Mapping)
            and event.get("stage") == stage
            and event.get("status") == "completed"
        ):
            return event
    return None


def _latest_cycle_stage_completion_with_legacy_decline_migration(
    record: Mapping[str, Any],
    *,
    base: Path,
    stage: str,
    cycle: str,
    canonical_full_market_v3: bool | None = None,
) -> Mapping[str, Any] | None:
    """Accept one explicitly sealed migration of pre-claim analyst work."""

    if canonical_full_market_v3 is None:
        canonical_full_market_v3 = (
            _record_has_canonical_full_market_v3_profile_authority(
                record,
                base=base,
                cycle=cycle,
            )
        )
    modern_full_market_v3 = bool(
        _record_has_full_market_v3_profile_authority(record)
        or canonical_full_market_v3
    )
    authenticated = _latest_cycle_stage_completion(
        record,
        base=base,
        stage=stage,
        cycle=cycle,
        require_claim=modern_full_market_v3,
    )
    if authenticated is not None or stage not in {"quick_profile", "scoped_research"}:
        return authenticated
    if modern_full_market_v3:
        # Full-market v3 explicitly requires an exact allocation-bound claim
        # and success receipt.  Legacy evaluator migration can never downgrade
        # that immutable authority.
        return None
    decline = _latest_cycle_stage_completion(
        record,
        base=base,
        stage="targeted_followup_decline",
        cycle=cycle,
    )
    if decline is None or decline.get("legacy_auto_materialized") is not True:
        return None
    migrated = dict(record)
    migrated.pop("manager_screen_run_id", None)
    for field in MANAGER_SCREEN_PROVENANCE_FIELDS:
        migrated.pop(field, None)
    if stage == "scoped_research":
        migrated.pop("profile_quick_selection_path", None)
        migrated.pop("profile_quick_selection_sha256", None)
    return _latest_cycle_stage_completion(
        migrated,
        base=base,
        stage=stage,
        cycle=cycle,
    )


def _latest_cycle_stage_authorization_completion(
    record: Mapping[str, Any],
    *,
    base: Path,
    stage: str,
    cycle: str,
    require_claim: bool,
) -> Mapping[str, Any] | None:
    """Authenticate a predecessor completion for a sealed stage selection.

    Modern completions use their claim/success chain.  A limited compatibility
    path remains for score-era profile packages that were sealed before stage
    claims existed and were subsequently selected by a sealed manager decision.
    That path must still verify the package/evaluation pair; mutable history
    paths that merely contain the current cycle are never completion evidence.
    """

    # A modern sealed selection is an authorization fact, not a read-only
    # compatibility view.  It must therefore carry the formal claim/success
    # receipt even when mutable manager provenance was stripped.  Only the
    # score-era selection contract (no run and no policy snapshot) may consume
    # an authenticated schema-v2 predecessor.
    return _latest_cycle_stage_completion(
        record,
        base=base,
        stage=stage,
        cycle=cycle,
        require_claim=require_claim,
    )


def _cycle_stage_completion_is_authenticated(
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    base: Path,
    stage: str,
    cycle: str,
    require_claim: bool = False,
) -> bool:
    if stage == "targeted_followup_decline":
        return _targeted_followup_decline_completion_is_authenticated(
            record,
            event,
            base=base,
            cycle=cycle,
        )
    if stage == "deep_research":
        return _deep_research_completion_is_authenticated(
            record,
            event,
            base=base,
            cycle=cycle,
        )
    return _profile_completion_is_authenticated(
        record,
        event,
        base=base,
        stage=stage,
        cycle=cycle,
        require_claim=require_claim,
    )


def _profile_completion_is_authenticated(
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    base: Path,
    stage: str,
    cycle: str,
    require_claim: bool = False,
) -> bool:
    repository_root = base.parent.parent.resolve()
    symbol = record.get("symbol")
    if not isinstance(symbol, str) or not re.fullmatch(r"CN:[0-9]{6}", symbol):
        return False
    ticker = symbol.split(":", 1)[1]
    relative_profile = event.get("result_path")
    relative_evaluation = event.get("evaluation_path")
    if not isinstance(relative_profile, str) or not isinstance(relative_evaluation, str):
        return False
    try:
        profile_path = (repository_root / relative_profile).resolve()
        evaluation_path = (repository_root / relative_evaluation).resolve()
        profile_path.relative_to(repository_root)
        evaluation_path.relative_to(repository_root)
        expected_dir = (base / "profiles" / cycle / ticker).resolve()
        if profile_path.parent != expected_dir or evaluation_path.parent != expected_dir:
            return False
        if not profile_path.name.endswith(".profile.json"):
            return False
        expected_evaluation_name = (
            f"{profile_path.name[:-len('.profile.json')]}.evaluation.json"
        )
        if evaluation_path.name != expected_evaluation_name:
            return False

        profile_seal = verify_sealed(profile_path)
        evaluation_seal = verify_sealed(evaluation_path)
        if (
            profile_seal.artifact_type != "quick_profile_package"
            or evaluation_seal.artifact_type != "quick_profile_evaluation"
            or event.get("result_sha256") != profile_seal.sha256
            or event.get("evaluation_sha256") != evaluation_seal.sha256
        ):
            return False
        finished_at = _datetime(event.get("finished_at"), "profile completion finished_at")
        if profile_seal.sealed_at != finished_at or evaluation_seal.sealed_at != finished_at:
            return False
        profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
        evaluation_payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        SealingError,
        ValueError,
        ResearchAllocationError,
    ):
        return False
    if not isinstance(profile_payload, Mapping) or not isinstance(
        evaluation_payload, Mapping
    ):
        return False
    profile_claim = profile_payload.get("claim_attempt")
    evaluation_claim = evaluation_payload.get("claim_attempt")
    profile_contract = dict(profile_payload)
    profile_contract.pop("claim_attempt", None)
    sealed_profile_schema = profile_contract.get("schema_version")
    if profile_claim is not None:
        if sealed_profile_schema != 3:
            return False
        profile_contract["schema_version"] = 2
    elif sealed_profile_schema != 2:
        return False
    try:
        normalized_profile = _validate_package(
            profile_contract,
            recorded_at=finished_at,
        )
    except (ResearchAllocationError, ValueError):
        return False
    if normalized_profile != profile_contract:
        return False

    evaluation_fields = {
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
    if profile_claim is not None:
        evaluation_fields.add("claim_attempt")
    if set(evaluation_payload) != evaluation_fields:
        return False
    profile = normalized_profile.get("profile")
    provenance = normalized_profile.get("provenance")
    evaluated = evaluation_payload.get("evaluation")
    if (
        not isinstance(profile, Mapping)
        or not isinstance(provenance, Mapping)
        or not isinstance(evaluated, Mapping)
    ):
        return False
    profile_stage = profile.get("research_stage")
    accepted_profile_stages = (
        {"quick_profile", "scoped_research"}
        if stage == "targeted_followup"
        else {stage}
    )
    if (
        normalized_profile.get("cycle_id") != cycle
        or profile.get("symbol") != symbol
        or profile_stage not in accepted_profile_stages
        or evaluation_payload.get("cycle_id") != cycle
        or evaluation_payload.get("symbol") != symbol
        or evaluation_payload.get("company_name") != normalized_profile.get("company_name")
        or evaluation_payload.get("recorded_at") != event.get("finished_at")
        or evaluation_payload.get("profile_path") != relative_profile
        or evaluation_payload.get("profile_sha256") != profile_seal.sha256
        or evaluated.get("evaluated_stage") != profile_stage
        or evaluated.get("next_stage") != event.get("next_stage")
        or provenance.get("agent") != event.get("agent")
        or evaluation_payload.get("portfolio_action") is not None
    ):
        return False
    next_stage = evaluated.get("next_stage")
    queue_status = evaluation_payload.get("queue_status")
    capacity_wait = evaluation_payload.get("capacity_wait")
    if next_stage in RESEARCH_STAGES:
        if queue_status not in {"pending", "requires_rebaseline"} or capacity_wait is not (
            queue_status == "requires_rebaseline"
        ):
            return False
    elif queue_status != "completed" or capacity_wait is not False:
        return False
    if profile_claim is None and evaluation_claim is None:
        return bool(
            profile_payload.get("schema_version") == 2
            and evaluation_payload.get("schema_version") == 2
            and not require_claim
            and not _profile_completion_requires_claim(record, stage=stage)
        )
    if (
        profile_payload.get("schema_version") != 3
        or evaluation_payload.get("schema_version") != 3
        or profile_claim != evaluation_claim
    ):
        return False
    try:
        claim_attempt = _normalize_profile_claim_attempt_binding(profile_claim)
        verify_profile_stage_success(
            root=base,
            claim_attempt=claim_attempt,
            history_event=event,
        )
    except (ProfileStageClaimError, ResearchAllocationError, ValueError):
        return False
    expected_authorization = _profile_completion_authorization_binding(
        record,
        stage=stage,
    )
    if expected_authorization is not None:
        authorization = claim_attempt.get("stage_authorization")
        if not isinstance(authorization, Mapping) or any(
            authorization.get(key) != value
            for key, value in expected_authorization.items()
        ):
            return False
    return True


def _profile_completion_authorization_binding(
    record: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, str] | None:
    if stage == "quick_profile":
        candidates = (
            (
                "manager_screen_allocation_result_path",
                "manager_screen_allocation_result_sha256",
            ),
            ("manager_screen_result_path", "manager_screen_result_sha256"),
        )
    elif stage == "targeted_followup":
        candidates = (
            ("targeted_followup_approval_path", "targeted_followup_approval_sha256"),
        )
    elif stage == "scoped_research":
        candidates = (("profile_quick_selection_path", "profile_quick_selection_sha256"),)
    elif stage == "deep_research":
        candidates = (("profile_scoped_selection_path", "profile_scoped_selection_sha256"),)
    else:
        return None
    for path_field, sha_field in candidates:
        path = record.get(path_field)
        sha256 = record.get(sha_field)
        if path is None and sha256 is None:
            continue
        if (
            not isinstance(path, str)
            or not path
            or not isinstance(sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
        ):
            return {"path": "__invalid__", "sha256": "__invalid__"}
        return {"path": path, "sha256": sha256}
    return None


def _profile_completion_requires_claim(
    record: Mapping[str, Any],
    *,
    stage: str,
) -> bool:
    return bool(
        _has_manager_screen_provenance(record)
        or _profile_completion_authorization_binding(record, stage=stage) is not None
    )


def _targeted_followup_decline_completion_is_authenticated(
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    base: Path,
    cycle: str,
) -> bool:
    symbol = record.get("symbol")
    relative = event.get("decline_path")
    expected_sha256 = event.get("decline_sha256")
    if (
        not isinstance(symbol, str)
        or not re.fullmatch(r"CN:[0-9]{6}", symbol)
        or not isinstance(relative, str)
        or not isinstance(expected_sha256, str)
    ):
        return False
    repository_root = base.parent.parent.resolve()
    path = (repository_root / relative).resolve()
    expected_path = (
        base
        / "profiles"
        / cycle
        / "targeted-followup-declines"
        / f"{symbol.split(':', 1)[1]}.json"
    ).resolve()
    try:
        path.relative_to(repository_root)
        if path != expected_path:
            return False
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        normalized = _validate_targeted_followup_decline_payload(payload)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        SealingError,
        ValueError,
        ResearchAllocationError,
    ):
        return False
    return bool(
        sealed.artifact_type == "targeted_followup_decline"
        and sealed.sha256 == expected_sha256
        and normalized.get("profile_cycle_id") == cycle
        and normalized.get("symbol") == symbol
        and normalized.get("declined_at") == event.get("finished_at")
        and normalized.get("outcome") == event.get("next_stage")
        and normalized.get("legacy_auto_materialized")
        == event.get("legacy_auto_materialized")
    )


def _deep_research_completion_is_authenticated(
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    base: Path,
    cycle: str,
) -> bool:
    symbol = record.get("symbol")
    if not isinstance(symbol, str) or not re.fullmatch(r"CN:[0-9]{6}", symbol):
        return False
    try:
        from .deep_research_completion import (
            DeepResearchCompletionError,
            deep_research_completion_status,
        )

        status = deep_research_completion_status(root=base, symbol=symbol)
    except (DeepResearchCompletionError, OSError, ValueError, ResearchAllocationError):
        return False
    return bool(
        status.get("finalized") is True
        and status.get("profile_cycle_id") == cycle
        and status.get("receipt_path") == event.get("completion_path")
        and status.get("receipt_sha256") == event.get("completion_sha256")
        and status.get("claim_attempt_path") == event.get("claim_path")
        and status.get("claim_attempt_sha256") == event.get("claim_sha256")
    )


def _validate_local_sources(sources: list[dict[str, Any]], *, repository_root: Path) -> None:
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
        per_run = policy.get("stage_capacity_per_run")
        value = (
            per_run.get(stage)
            if isinstance(per_run, Mapping) and stage in per_run
            else policy.get("quick_profile_capacity_per_cycle")
        )
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ResearchAllocationError("stage capacity is invalid: targeted_followup")
        return value
    capacities = policy.get("stage_capacity_per_run")
    if capacities is None:
        capacities = policy.get("stage_capacity_per_cycle")
    if not isinstance(capacities, Mapping):
        raise ResearchAllocationError("stage capacity policy is invalid")
    value = capacities.get(stage)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResearchAllocationError(f"stage capacity is invalid: {stage}")
    return value


def _manager_screen_run_id_for_cohort(
    cohort: list[Mapping[str, Any]],
) -> str | None:
    bound = [_has_manager_screen_provenance(item) for item in cohort]
    if any(bound) and not all(bound):
        raise ResearchAllocationError("profile cohort mixes manager-bound and legacy predecessors")
    run_ids = {
        _manager_screen_run_id_for_record(
            item,
            context="manager-bound profile cohort",
        )
        for item in cohort
    }
    if run_ids == {None}:
        return None
    if len(run_ids) != 1 or not all(isinstance(run_id, str) for run_id in run_ids):
        raise ResearchAllocationError(
            "manager-bound profile cohort spans multiple manager-screen runs"
        )
    return str(next(iter(run_ids)))


def _has_manager_screen_provenance(record: Mapping[str, Any]) -> bool:
    if any(record.get(field) is not None for field in MANAGER_SCREEN_PROVENANCE_FIELDS):
        return True
    history = record.get("stage_history")
    return bool(
        isinstance(history, list)
        and any(
            isinstance(item, Mapping)
            and isinstance(item.get("stage"), str)
            and (
                str(item["stage"]).startswith("manager_screen")
                or item.get("stage") == "legacy_transition"
            )
            for item in history
        )
    )


def _manager_screen_run_id_for_record(
    record: Mapping[str, Any],
    *,
    context: str,
) -> str | None:
    value = record.get("manager_screen_run_id")
    if not _has_manager_screen_provenance(record):
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ResearchAllocationError(f"{context} manager-screen run_id is invalid")
        return value
    if not isinstance(value, str) or not value:
        raise ResearchAllocationError(f"{context} cannot drop its manager-screen run binding")
    return value


def _research_policy_binding(
    *,
    repository_root: Path,
    policy: Mapping[str, Any],
    policy_path: str | Path,
) -> dict[str, Any]:
    path = Path(policy_path)
    if not path.is_absolute():
        path = repository_root / path
    path = path.resolve()
    try:
        relative = path.relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ResearchAllocationError(
            "research-allocation policy must stay inside the repository"
        ) from exc
    if not path.is_file():
        raise ResearchAllocationError(f"research-allocation policy is missing: {path}")
    loaded = load_policy(path)
    if loaded.kind != PolicyKind.RESEARCH_ALLOCATION:
        raise ResearchAllocationError("research-allocation policy kind must be research_allocation")
    if dict(loaded.payload) != dict(policy):
        raise ResearchAllocationError(
            "research-allocation policy payload does not match the bound policy file"
        )
    raw = path.read_bytes()
    return {
        "policy_id": loaded.policy_id,
        "version": loaded.version,
        "path": relative,
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_sha256": hashlib.sha256(canonical_json_bytes(dict(loaded.payload))).hexdigest(),
    }


def _normalize_research_policy_binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != RESEARCH_POLICY_BINDING_KEYS:
        raise ResearchAllocationError("research policy binding fields do not match contract")
    normalized = {
        "policy_id": _text(value.get("policy_id"), "research_policy.policy_id"),
        "version": _text(value.get("version"), "research_policy.version"),
        "path": _text(value.get("path"), "research_policy.path"),
        "file_sha256": _text(value.get("file_sha256"), "research_policy.file_sha256"),
        "payload_sha256": _text(value.get("payload_sha256"), "research_policy.payload_sha256"),
    }
    for field in ("file_sha256", "payload_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", normalized[field]):
            raise ResearchAllocationError(f"research_policy.{field} must be lowercase SHA-256")
    return normalized


def _research_policy_document_for_binding(
    *,
    repository_root: Path,
    policy_binding: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = _normalize_research_policy_binding(policy_binding)
    policy_path = (repository_root / normalized["path"]).resolve()
    try:
        policy_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError("research-allocation policy escapes repository root") from exc
    try:
        document = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError("research-allocation policy is invalid") from exc
    if not isinstance(document, Mapping) or not isinstance(document.get("payload"), Mapping):
        raise ResearchAllocationError("research-allocation policy document is invalid")
    actual = _research_policy_binding(
        repository_root=repository_root,
        policy=document["payload"],
        policy_path=policy_path,
    )
    if actual != normalized:
        raise ResearchAllocationError(
            "research-allocation policy differs from its requested run binding"
        )
    return dict(document)


def _verify_run_research_policy_snapshot(
    *,
    base: Path,
    run_id: str,
    expected_policy: Mapping[str, Any],
    context: str,
) -> dict[str, Any]:
    """Authenticate a run policy without consulting the mutable live file."""

    normalized = _normalize_research_policy_binding(expected_policy)
    run_dir = base / "manager-screen" / run_id
    contract_path = run_dir / "research-policy.json"
    snapshot_path = run_dir / "research-policy.snapshot.json"
    try:
        contract_seal = verify_sealed(contract_path)
        snapshot_seal = verify_sealed(snapshot_path)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError, ValueError) as exc:
        raise ResearchAllocationError(f"{context} run policy contract/snapshot is invalid") from exc
    contract_keys = {
        "schema_version",
        "run_id",
        "bound_at",
        "policy",
        "portfolio_action",
    }
    snapshot_payload = snapshot.get("payload") if isinstance(snapshot, Mapping) else None
    if (
        contract_seal.artifact_type != "manager_screen_research_policy_contract"
        or snapshot_seal.artifact_type != "manager_screen_research_policy_snapshot"
        or not isinstance(contract, Mapping)
        or set(contract) != contract_keys
        or contract.get("schema_version") != 1
        or contract.get("run_id") != run_id
        or contract.get("portfolio_action") is not None
        or _normalize_research_policy_binding(contract.get("policy")) != normalized
        or not isinstance(snapshot, Mapping)
        or snapshot.get("kind") != PolicyKind.RESEARCH_ALLOCATION.value
        or snapshot.get("policy_id") != normalized["policy_id"]
        or snapshot.get("version") != normalized["version"]
        or not isinstance(snapshot_payload, Mapping)
        or hashlib.sha256(canonical_json_bytes(dict(snapshot_payload))).hexdigest()
        != normalized["payload_sha256"]
    ):
        raise ResearchAllocationError(f"{context} run policy contract/snapshot does not match")
    _datetime(contract.get("bound_at"), "research_policy.bound_at")
    return dict(snapshot)


def _bind_research_policy_for_run(
    *,
    base: Path,
    run_id: str,
    policy_binding: Mapping[str, Any],
    bound_at: dt.datetime,
) -> dict[str, Any]:
    canonical_path = "policies/research-allocation.json"
    normalized = _normalize_research_policy_binding(policy_binding)
    if normalized["path"] != canonical_path:
        raise ResearchAllocationError(
            f"manager-screen research budget must use the canonical {canonical_path} policy"
        )
    contract_path = base / "manager-screen" / run_id / "research-policy.json"
    snapshot_path = contract_path.with_name("research-policy.snapshot.json")
    repository_root = base.parent.parent.resolve()
    contract = {
        "schema_version": 1,
        "run_id": run_id,
        "bound_at": bound_at.isoformat(),
        "policy": normalized,
        "portfolio_action": None,
    }
    if (
        contract_path.exists()
        or contract_path.with_name(f"{contract_path.name}.seal.json").exists()
    ):
        try:
            sealed = verify_sealed(contract_path)
            existing = json.loads(contract_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, SealingError) as exc:
            raise ResearchAllocationError(
                f"manager-screen research policy contract is invalid: {run_id}"
            ) from exc
        if (
            sealed.artifact_type != "manager_screen_research_policy_contract"
            or not isinstance(existing, Mapping)
            or existing.get("schema_version") != 1
            or existing.get("run_id") != run_id
            or existing.get("portfolio_action") is not None
        ):
            raise ResearchAllocationError(
                f"manager-screen research policy contract is invalid: {run_id}"
            )
        existing_policy = _normalize_research_policy_binding(existing.get("policy"))
        if existing_policy != normalized:
            raise ResearchAllocationError(
                f"research-allocation policy is already bound for manager-screen run {run_id}"
            )
        snapshot_pair = (
            snapshot_path.exists(),
            snapshot_path.with_name(f"{snapshot_path.name}.seal.json").exists(),
        )
        if snapshot_pair[0] != snapshot_pair[1]:
            raise ResearchAllocationError(
                f"manager-screen research policy snapshot is only partially sealed: {run_id}"
            )
        if snapshot_pair == (False, False):
            policy_document = _research_policy_document_for_binding(
                repository_root=repository_root,
                policy_binding=normalized,
            )
            seal_json(
                snapshot_path,
                policy_document,
                artifact_type="manager_screen_research_policy_snapshot",
                sealed_at=bound_at,
            )
        _verify_run_research_policy_snapshot(
            base=base,
            run_id=run_id,
            expected_policy=normalized,
            context="manager-screen research policy",
        )
        return dict(existing)
    policy_document = _research_policy_document_for_binding(
        repository_root=repository_root,
        policy_binding=normalized,
    )
    seal_json(
        contract_path,
        contract,
        artifact_type="manager_screen_research_policy_contract",
        sealed_at=bound_at,
    )
    seal_json(
        snapshot_path,
        policy_document,
        artifact_type="manager_screen_research_policy_snapshot",
        sealed_at=bound_at,
    )
    _verify_run_research_policy_snapshot(
        base=base,
        run_id=run_id,
        expected_policy=normalized,
        context="manager-screen research policy",
    )
    return contract


def _sealed_stage_evidence_proves(
    evidence_stages: set[str],
    *,
    stage: str,
) -> bool:
    """Apply the conservative inherited-stage high-watermark rules."""

    if stage == "targeted_followup":
        return stage in evidence_stages
    if stage == "scoped_research":
        return bool(evidence_stages & {"scoped_research", "deep_research"})
    if stage == "deep_research":
        return stage in evidence_stages
    raise ResearchAllocationError(f"unsupported sealed inherited stage: {stage}")


def _sealed_inherited_stage_commitment_ledger(
    *,
    base: Path,
    repository_root: Path,
    manager_screen_run_id: str,
    stage: str,
) -> dict[str, dict[str, Any]]:
    """Rebuild inherited stage purchases without consulting the mutable queue.

    A recorded legacy transition freezes both the formal artifact bound for an
    adoption and the queue-derived stage high-watermark in its sealed plan.
    The allocation-v3 migration contract independently freezes any formal
    progress that made a historical quick-profile commitment irreversible.
    Both sources can describe the same purchase, so this ledger conserves one
    budget per ``(stage, symbol)`` while preferring the legacy transition as
    the older canonical source.
    """

    _sealed_stage_evidence_proves(set(), stage=stage)
    repository = repository_root.resolve()
    ledger: dict[str, dict[str, Any]] = {}

    transition_dir = base / "manager-screen" / manager_screen_run_id / "legacy-transition-001"
    if transition_dir.exists():
        from .legacy_transition import LegacyTransitionError, _verify_transition_dir

        try:
            plan_path = transition_dir / "plan.json"
            plan_seal = verify_sealed(plan_path)
            plan_preview = json.loads(plan_path.read_text(encoding="utf-8"))
            preview_members = plan_preview.get("members")
            if plan_seal.artifact_type != "manager_screen_legacy_transition_plan" or not isinstance(
                preview_members, list
            ):
                raise ResearchAllocationError("legacy transition stage-evidence preview is invalid")
            has_stage_evidence = any(
                isinstance(member, Mapping)
                and (
                    "research_stage_high_watermark" in member
                    or isinstance(member.get("formal_source"), Mapping)
                )
                for member in preview_members
            )
            if not has_stage_evidence:
                transition = None
            else:
                transition = _verify_transition_dir(
                    transition_dir,
                    repository_root=repository,
                    require_packet=True,
                    require_result=True,
                )
        except (
            json.JSONDecodeError,
            LegacyTransitionError,
            OSError,
            SealingError,
            ValueError,
        ) as exc:
            raise ResearchAllocationError(
                "sealed inherited stage ledger has an invalid legacy transition: "
                f"{manager_screen_run_id}"
            ) from exc
        if transition is None:
            transition_members: list[Mapping[str, Any]] = []
            result_relative = ""
            result_sha256 = ""
        else:
            result_path = transition["result_path"].resolve()
            result_relative = result_path.relative_to(repository).as_posix()
            result_sha256 = transition["result_seal"].sha256
            transition_members = transition["plan"]["members"]
        for member in transition_members:
            evidence_stages = {
                value
                for value in (
                    member.get("research_stage_high_watermark"),
                    (member.get("formal_source") or {}).get("stage"),
                )
                if isinstance(value, str)
            }
            if not _sealed_stage_evidence_proves(evidence_stages, stage=stage):
                continue
            symbol = str(member["symbol"])
            ledger[symbol] = {
                "manager_screen_run_id": manager_screen_run_id,
                "stage": stage,
                "symbol": symbol,
                "profile_cycle_id": "legacy-transition-001",
                "selection_path": result_relative,
                "selection_sha256": result_sha256,
            }

    contract_path = (
        base
        / "manager-screen"
        / manager_screen_run_id
        / "governance"
        / "allocation-v3"
        / "contract.json"
    )
    contract_pair = (contract_path.exists(), _seal_sidecar(contract_path).exists())
    if contract_pair != (False, False):
        from .manager_screen_allocation_v3 import (
            ManagerScreenAllocationV3Error,
            verify_manager_screen_allocation_v3_contract,
        )

        try:
            contract = verify_manager_screen_allocation_v3_contract(
                root=base,
                run_id=manager_screen_run_id,
            )
            contract_seal = verify_sealed(contract_path)
        except (
            ManagerScreenAllocationV3Error,
            OSError,
            SealingError,
            ValueError,
        ) as exc:
            raise ResearchAllocationError(
                "sealed inherited stage ledger has an invalid allocation-v3 contract: "
                f"{manager_screen_run_id}"
            ) from exc
        contract_relative = contract_path.resolve().relative_to(repository).as_posix()
        for classification in contract["commitment_classification"]:
            if classification["commitment_class"] != "irreversible":
                continue
            evidence_stages = {
                str(reference["research_stage"]) for reference in classification["sealed_progress"]
            }
            if not _sealed_stage_evidence_proves(evidence_stages, stage=stage):
                continue
            symbol = str(classification["symbol"])
            ledger.setdefault(
                symbol,
                {
                    "manager_screen_run_id": manager_screen_run_id,
                    "stage": stage,
                    "symbol": symbol,
                    "profile_cycle_id": "allocation-v3-migration",
                    "selection_path": contract_relative,
                    "selection_sha256": contract_seal.sha256,
                },
            )
    return ledger


def _sealed_stage_commitment_ledger(
    *,
    base: Path,
    repository_root: Path,
    manager_screen_run_id: str,
    next_stage: str,
) -> dict[str, dict[str, Any]]:
    """Rebuild one run's L3/L4 purchases from sealed canonical selections."""

    configs = {
        "scoped_research": {
            "evaluated_stage": "quick_profile",
            "selection_name": "quick-profile-selection.json",
            "comparison_name": "quick-profile-comparison.json",
        },
        "deep_research": {
            "evaluated_stage": "scoped_research",
            "selection_name": "scoped-research-selection.json",
            "comparison_name": "scoped-research-comparison.json",
        },
    }
    config = configs.get(next_stage)
    if config is None:
        raise ResearchAllocationError(f"unsupported sealed stage ledger: {next_stage}")
    ledger: dict[str, dict[str, Any]] = {}
    profiles_root = base / "profiles"
    cycle_dirs = (
        sorted(path for path in profiles_root.iterdir() if path.is_dir())
        if profiles_root.is_dir()
        else []
    )
    for cycle_dir in cycle_dirs:
        selection_path = cycle_dir / config["selection_name"]
        pair = (selection_path.exists(), _seal_sidecar(selection_path).exists())
        if pair == (False, False):
            continue
        if pair[0] != pair[1]:
            raise ResearchAllocationError(
                f"sealed {next_stage} commitment is only partially present: {cycle_dir.name}"
            )
        try:
            sealed = verify_sealed(selection_path)
            payload = json.loads(selection_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, SealingError) as exc:
            raise ResearchAllocationError(
                f"sealed {next_stage} commitment is invalid: {cycle_dir.name}"
            ) from exc
        cycle = _text(payload.get("cycle_id"), "selection.cycle_id")
        if cycle != cycle_dir.name:
            raise ResearchAllocationError(
                f"sealed {next_stage} commitment cycle path is not canonical: {cycle_dir.name}"
            )
        evaluated_stage = config["evaluated_stage"]
        _validate_profile_selection_payload(
            payload,
            artifact_type=sealed.artifact_type,
            cycle=cycle,
            stage=evaluated_stage,
            next_stage=next_stage,
        )
        if payload.get("manager_screen_run_id") != manager_screen_run_id:
            continue
        _validate_profile_stage_selection_semantics(
            payload,
            base=base,
            repository_root=repository_root,
            cycle=cycle,
            stage=evaluated_stage,
            next_stage=next_stage,
            comparison_name=config["comparison_name"],
        )
        relative = selection_path.relative_to(repository_root).as_posix()
        for row in payload["ranking"]:
            if row["selected"] is not True:
                continue
            symbol = str(row["symbol"])
            prior = ledger.get(symbol)
            if prior is not None:
                raise ResearchAllocationError(
                    f"duplicate sealed {next_stage} budget across profile cycles: "
                    f"{symbol} in {prior['selection_path']} and {relative}"
                )
            ledger[symbol] = {
                "manager_screen_run_id": manager_screen_run_id,
                "stage": next_stage,
                "symbol": symbol,
                "profile_cycle_id": cycle,
                "selection_path": relative,
                "selection_sha256": sealed.sha256,
            }
    inherited = _sealed_inherited_stage_commitment_ledger(
        base=base,
        repository_root=repository_root,
        manager_screen_run_id=manager_screen_run_id,
        stage=next_stage,
    )
    for symbol, commitment in inherited.items():
        ledger.setdefault(symbol, commitment)
    return ledger


def _committed_stage_count_for_run(
    queue: list[Mapping[str, Any]],
    *,
    manager_screen_run_id: str,
    stage: str,
    exclude_symbols: set[str] | None = None,
) -> int:
    """Count every stage budget ever purchased within one manager-screen run."""

    excluded = exclude_symbols or set()
    return sum(
        1
        for item in queue
        if item.get("symbol") not in excluded
        and item.get("manager_screen_run_id") == manager_screen_run_id
        and (
            (
                item.get("task_type") == stage
                and item.get("status") in {"pending", "running", "completed"}
            )
            or _history_completed(item, stage)
        )
    )


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
        "profile_candidate": ("正式画像发现可信投资路径，等待完整同层批次横向比较范围研究预算。"),
        "targeted_followup_candidate": (
            "研究员建议补齐少数决定性证据，等待投资经理显式批准追加预算。"
        ),
        "deep_candidate": ("范围研究通过证据与粗估值门槛，等待完整同层批次横向比较深研预算。"),
        "targeted_followup": "画像只支持补齐少数决定性证据，暂不扩张研究范围。",
        "scoped_research": "画像发现可信投资路径，追加有限范围研究预算。",
        "deep_research": "范围研究通过证据与粗估值门槛，追加完整深研预算。",
        "price_watch": "公司可能可投，但当前价格不支持继续购买研究预算。",
        "reassign_or_stop": "当前 agent 能力圈不足，转派专门能力或暂停。",
        "watch_only": "当前不购买追加研究预算，等待已定义事实触发器。",
        "conditional_stop": "可靠证据触发结构化停止条件。",
    }
    return reasons[stage]


def _next_action(stage: str, capacity_wait: bool) -> str:
    if capacity_wait:
        return "下一研究周期释放容量后，按画像价值排序重新竞争预算。"
    actions = {
        "profile_candidate": ("等待完整正式画像批次封存后统一比较，不得按完成顺序晋级。"),
        "targeted_followup_candidate": ("等待投资经理比较同层结果并显式批准，不自动创建补证任务。"),
        "deep_candidate": ("等待完整范围研究批次封存后统一比较，不得按完成顺序晋级。"),
        "targeted_followup": "只补画像列出的一个或少数决定性证据缺口。",
        "scoped_research": "在4小时预算内解决一至三个决定性未知数。",
        "deep_research": "按完整公司研究协议重建业务、会计、正常化盈利和估值。",
        "price_watch": "按价格、财报、事件或论点触发器重新评估。",
        "reassign_or_stop": "转派具备相应行业能力的独立 agent；无法转派则暂停。",
        "watch_only": "仅在已封存的价格、财报、事件或论点触发器命中时重新评估。",
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


def _history_completed_outcome(record: Mapping[str, Any], stage: str) -> str | None:
    for item in reversed(record.get("stage_history") or []):
        if (
            isinstance(item, Mapping)
            and item.get("stage") == stage
            and item.get("status") == "completed"
            and isinstance(item.get("next_stage"), str)
        ):
            return str(item["next_stage"])
    return None


def _profile_priority_score(profile: Mapping[str, Any], *, priority: int) -> int:
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
    resolvability_bucket = 2 if unknown_count == 1 else 1 if unknown_count <= 3 else 0
    priority_bucket = max(0, 6 - priority)
    return return_bucket * 100 + source_bucket * 10 + resolvability_bucket * 3 + priority_bucket


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
        raise ResearchAllocationError(f"industry evidence policy is invalid for {cluster}")
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
    if capacity <= 0:
        return [], set()
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

def _normalize_profile_adjudication_submission(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != PROFILE_ADJUDICATION_SUBMISSION_KEYS
        or value.get("schema_version") != 1
        or value.get("stage") != "quick_profile"
        or value.get("portfolio_action") is not None
        or not isinstance(value.get("additional_budget_hours"), float)
        or value.get("additional_budget_hours") != 0.0
    ):
        raise ResearchAllocationError(
            "profile adjudication submission fields do not match the v1 contract"
        )
    cycle = _text(value.get("profile_cycle_id"), "profile_cycle_id")
    if not CYCLE_RE.fullmatch(cycle):
        raise ResearchAllocationError("profile adjudication cycle_id is invalid")
    path_fields = (
        "profile_path",
        "evaluation_path",
        "claim_path",
        "success_path",
        "full_market_result_path",
    )
    sha_fields = (
        "profile_sha256",
        "evaluation_sha256",
        "claim_sha256",
        "success_sha256",
        "full_market_result_sha256",
        "full_market_candidate_sha256",
    )
    paths = {field: _text(value.get(field), field) for field in path_fields}
    hashes = {
        field: _profile_adjudication_sha256(value.get(field), field)
        for field in sha_fields
    }
    reviewer = _text(value.get("reviewer"), "reviewer")
    manager = _text(value.get("manager"), "manager")
    outcome = _text(value.get("outcome"), "outcome")
    if outcome not in PROFILE_ADJUDICATION_OUTCOMES:
        raise ResearchAllocationError(f"unsupported profile adjudication outcome: {outcome}")
    evidence = _normalize_profile_adjudication_evidence(value.get("evidence"))
    qa_sources = _normalize_profile_adjudication_sources(value.get("qa_sources"))
    evidence_ids = {item["evidence_id"] for item in evidence}
    material_errors = _normalize_profile_adjudication_errors(
        value.get("material_errors"),
        evidence_ids=evidence_ids,
    )
    source_ids = {
        source_id
        for item in evidence
        for source_id in item["source_ids"]
    }
    corrected = value.get("corrected_decisive_answer")
    if not isinstance(corrected, Mapping) or set(corrected) != DECISIVE_ANSWER_KEYS:
        raise ResearchAllocationError(
            "corrected_decisive_answer fields do not match contract"
        )
    corrected_source_ids = _text_array(
        corrected.get("source_ids"),
        "corrected_decisive_answer.source_ids",
        allow_empty=False,
    )
    unknown_corrected_sources = sorted(set(corrected_source_ids) - source_ids)
    if unknown_corrected_sources:
        raise ResearchAllocationError(
            "corrected_decisive_answer references evidence sources absent from the QA ledger: "
            f"{unknown_corrected_sources}"
        )
    normalized_corrected = {
        "conclusion": _text(
            corrected.get("conclusion"),
            "corrected_decisive_answer.conclusion",
        ),
        "source_ids": corrected_source_ids,
        "unresolved_reason": _text(
            corrected.get("unresolved_reason"),
            "corrected_decisive_answer.unresolved_reason",
        ),
    }
    return {
        "schema_version": 1,
        "profile_cycle_id": cycle,
        "stage": "quick_profile",
        **paths,
        **hashes,
        "reviewer": reviewer,
        "manager": manager,
        "outcome": outcome,
        "reason": _text(value.get("reason"), "reason"),
        "material_errors": material_errors,
        "evidence": evidence,
        "qa_sources": qa_sources,
        "corrected_decisive_question": _text(
            value.get("corrected_decisive_question"),
            "corrected_decisive_question",
        ),
        "corrected_decisive_answer": normalized_corrected,
        "restart_triggers": _normalize_reactivation_triggers(
            value.get("restart_triggers"),
            outcome="watch_only",
        ),
        "additional_budget_hours": 0.0,
        "portfolio_action": None,
    }


def _normalize_profile_adjudication_errors(
    value: Any,
    *,
    evidence_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ResearchAllocationError("profile adjudication requires material error findings")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != PROFILE_ADJUDICATION_ERROR_KEYS:
            raise ResearchAllocationError(
                "profile adjudication material error fields do not match contract"
            )
        error_id = _text(raw.get("error_id"), "material_error.error_id")
        if not SOURCE_ID_RE.fullmatch(error_id) or error_id in seen:
            raise ResearchAllocationError(
                "profile adjudication material error IDs must be valid and unique"
            )
        error_type = _text(raw.get("error_type"), "material_error.error_type")
        if error_type not in PROFILE_ADJUDICATION_ERROR_TYPES:
            raise ResearchAllocationError(
                f"unsupported profile adjudication material error type: {error_type}"
            )
        refs = _text_array(
            raw.get("evidence_ids"),
            f"material_error.{error_id}.evidence_ids",
            allow_empty=False,
        )
        unknown = sorted(set(refs) - evidence_ids)
        if unknown:
            raise ResearchAllocationError(
                f"profile adjudication material error references unknown evidence: {unknown}"
            )
        seen.add(error_id)
        normalized.append(
            {
                "error_id": error_id,
                "error_type": error_type,
                "finding": _text(raw.get("finding"), f"material_error.{error_id}.finding"),
                "evidence_ids": refs,
            }
        )
    return normalized


def _normalize_profile_adjudication_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ResearchAllocationError("profile adjudication requires QA evidence")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != PROFILE_ADJUDICATION_EVIDENCE_KEYS:
            raise ResearchAllocationError(
                "profile adjudication evidence fields do not match contract"
            )
        evidence_id = _text(raw.get("evidence_id"), "evidence.evidence_id")
        if not SOURCE_ID_RE.fullmatch(evidence_id) or evidence_id in seen:
            raise ResearchAllocationError(
                "profile adjudication evidence IDs must be valid and unique"
            )
        seen.add(evidence_id)
        normalized.append(
            {
                "evidence_id": evidence_id,
                "description": _text(
                    raw.get("description"),
                    f"evidence.{evidence_id}.description",
                ),
                "source_ids": _text_array(
                    raw.get("source_ids"),
                    f"evidence.{evidence_id}.source_ids",
                    allow_empty=False,
                ),
            }
        )
    return normalized


def _normalize_profile_adjudication_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ResearchAllocationError("profile adjudication qa_sources must be an array")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != PROFILE_ADJUDICATION_SOURCE_KEYS:
            raise ResearchAllocationError(
                "profile adjudication QA source fields do not match contract"
            )
        source_id = _text(raw.get("source_id"), "qa_source.source_id")
        if not SOURCE_ID_RE.fullmatch(source_id) or source_id in seen:
            raise ResearchAllocationError(
                "profile adjudication QA source IDs must be valid and unique"
            )
        seen.add(source_id)
        normalized.append(
            {
                "source_id": source_id,
                "path": _text(raw.get("path"), f"qa_source.{source_id}.path"),
                "sha256": _profile_adjudication_sha256(
                    raw.get("sha256"),
                    f"qa_source.{source_id}.sha256",
                ),
            }
        )
    return normalized


def _profile_adjudication_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ResearchAllocationError(f"{field} must be lowercase SHA-256")
    return value


def _profile_adjudication_submission_from_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {field: payload.get(field) for field in PROFILE_ADJUDICATION_SUBMISSION_KEYS}


def _profile_adjudication_path(
    *,
    base: Path,
    cycle: str,
    stage: str,
    symbol: str,
) -> Path:
    # The full profile SHA remains sealed in the payload.  A fixed filename
    # keeps atomic temp-file paths below the Windows MAX_PATH boundary while
    # the ticker directory still enforces one decision per cycle/stage/symbol.
    ticker = symbol.split(":", 1)[1]
    return (
        base
        / "profiles"
        / cycle
        / "profile-adjudications"
        / stage
        / ticker
        / "adjudication.json"
    )


def _canonical_profile_adjudication_paths(
    *,
    base: Path,
    symbol: str,
    allow_unsealed_path: Path | None = None,
) -> list[Path]:
    """Find and authenticate canonical adjudications without trusting live rows."""

    ticker = symbol.split(":", 1)[1]
    profiles_root = base / "profiles"
    if not profiles_root.exists():
        return []
    payload_paths = {
        path.resolve()
        for path in profiles_root.glob(
            f"*/profile-adjudications/*/{ticker}/adjudication.json"
        )
        if path.is_file()
    }
    seal_payload_paths = {
        path.with_name("adjudication.json").resolve()
        for path in profiles_root.glob(
            f"*/profile-adjudications/*/{ticker}/adjudication.json.seal.json"
        )
        if path.is_file()
    }
    paths = sorted(payload_paths | seal_payload_paths, key=lambda path: path.as_posix())
    allowed_unsealed = (
        allow_unsealed_path.resolve() if allow_unsealed_path is not None else None
    )
    for path in paths:
        seal_path = path.with_name(f"{path.name}.seal.json")
        if not path.exists():
            raise ResearchAllocationError(
                f"profile adjudication seal exists without its payload: {symbol}"
            )
        if not seal_path.exists():
            if allowed_unsealed == path:
                continue
            raise ResearchAllocationError(
                f"profile adjudication payload exists without its seal: {symbol}"
            )
        payload, _sealed = _verify_profile_adjudication_artifact(path, base=base)
        if payload["prior_queue_row"].get("symbol") != symbol:
            raise ResearchAllocationError(
                f"canonical profile adjudication targets another symbol: {symbol}"
            )
    return paths


def _targeted_followup_decision_artifact_paths(
    *,
    base: Path,
    cycle: str,
    symbol: str,
) -> list[Path]:
    """Return any canonical targeted decision payload or seal, including half writes."""

    ticker = symbol.split(":", 1)[1]
    cycle_root = base / "profiles" / cycle
    paths: set[Path] = set()
    for directory in ("targeted-followup-approvals", "targeted-followup-declines"):
        payload_path = cycle_root / directory / f"{ticker}.json"
        seal_path = payload_path.with_name(f"{payload_path.name}.seal.json")
        if payload_path.exists():
            paths.add(payload_path.resolve())
        if seal_path.exists():
            paths.add(seal_path.resolve())
    return sorted(paths, key=lambda path: path.as_posix())


def _profile_adjudication_next_action(
    *,
    outcome: str,
    triggers: list[Mapping[str, Any]],
) -> str:
    conditions = "；".join(f"{item['type']}：{item['condition']}" for item in triggers)
    if outcome == "material_error_confirmed":
        return f"画像因重大事实或桥接错误被隔离；仅在以下条件命中后重新评估：{conditions}"
    return f"采用裁决后的限定结论，不使用被降格的旧定量值；按以下条件更新：{conditions}"


@serialized_coverage_write
def record_profile_adjudication(
    *,
    root: str | Path,
    symbol: str,
    submission: Mapping[str, Any],
    adjudicated_at: dt.datetime,
) -> dict[str, Any]:
    """Seal one terminal quick-profile QA adjudication and project it safely."""

    _require_aware_datetime(adjudicated_at, "adjudicated_at")
    if not re.fullmatch(r"CN:[0-9]{6}", symbol):
        raise ResearchAllocationError("profile adjudication symbol is invalid")
    normalized = _normalize_profile_adjudication_submission(submission)
    base = Path(root)
    repository_root = base.parent.parent.resolve()
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = read_jsonl(queue_path)
    screening = read_jsonl(screening_path)
    queued = _one_record(queue, symbol, "research queue")
    screen = _one_record(screening, symbol, "screening")
    if normalized["profile_cycle_id"] != queued.get("profile_cycle_id"):
        raise ResearchAllocationError("profile adjudication targets the wrong current cycle")
    target = _profile_adjudication_path(
        base=base,
        cycle=normalized["profile_cycle_id"],
        stage=normalized["stage"],
        symbol=symbol,
    )
    if _targeted_followup_decision_artifact_paths(
        base=base,
        cycle=normalized["profile_cycle_id"],
        symbol=symbol,
    ):
        raise ResearchAllocationError(
            "profile adjudication conflicts with an existing targeted-followup "
            f"decision artifact: {symbol}"
        )
    canonical_paths = _canonical_profile_adjudication_paths(
        base=base,
        symbol=symbol,
        allow_unsealed_path=target,
    )
    if any(path != target.resolve() for path in canonical_paths):
        raise ResearchAllocationError(
            "a second profile adjudication requires a sealed successor workflow"
        )
    _reject_second_profile_adjudication(target)
    payload_exists = target.exists()
    seal_path = target.with_name(f"{target.name}.seal.json")
    seal_exists = seal_path.exists()
    if seal_exists and not payload_exists:
        raise ResearchAllocationError("profile adjudication seal exists without its payload")
    if payload_exists:
        payload = _read_profile_adjudication_payload(target)
        validated = _validate_profile_adjudication_payload(
            payload,
            base=base,
            expected_path=target,
        )
        if _profile_adjudication_submission_from_payload(validated) != normalized:
            raise ResearchAllocationError(
                f"sealed profile adjudication conflicts with request: {symbol}"
            )
        if not seal_exists:
            if queued != validated["prior_queue_row"] or screen != validated[
                "prior_screening_row"
            ]:
                raise ResearchAllocationError(
                    "unsealed profile adjudication cannot be recovered after projection drift"
                )
            sealed = seal_json(
                target,
                validated,
                artifact_type="profile_adjudication",
                sealed_at=_datetime(validated["adjudicated_at"], "adjudicated_at"),
            )
        else:
            sealed = verify_sealed(target)
            if (
                sealed.artifact_type != "profile_adjudication"
                or sealed.sealed_at
                != _datetime(validated["adjudicated_at"], "adjudicated_at")
            ):
                raise ResearchAllocationError("profile adjudication seal is invalid")
        return _materialize_profile_adjudication(
            base=base,
            queue=queue,
            screening=screening,
            payload=validated,
            path=target,
            sha256=sealed.sha256,
            repository_root=repository_root,
            idempotent=True,
        )

    if any(queued.get(field) is not None for field in PROFILE_ADJUDICATION_BINDING_FIELDS) or any(
        screen.get(field) is not None for field in PROFILE_ADJUDICATION_BINDING_FIELDS
    ):
        raise ResearchAllocationError(
            "profile adjudication projection exists without its canonical sealed artifact"
        )
    comparison_path = (
        base
        / "profiles"
        / normalized["profile_cycle_id"]
        / _profile_stage_config(normalized["stage"])["comparison_name"]
    )
    selection_path = comparison_path.with_name(
        _profile_stage_config(normalized["stage"])["selection_name"]
    )
    if comparison_path.exists() or selection_path.exists():
        raise ResearchAllocationError(
            "profile adjudication must be sealed before the stage comparison/selection"
        )
    context = _validate_profile_adjudication_authority(
        normalized,
        base=base,
        queue_record=queued,
        screen_record=screen,
        symbol=symbol,
        adjudicated_at=adjudicated_at,
    )
    payload = {
        **normalized,
        "workflow": "profile_adjudication",
        "adjudicated_at": adjudicated_at.isoformat(),
        "research_agent": context["research_agent"],
        "original_effective_outcome": context["original_effective_outcome"],
        "prior_queue_row": dict(queued),
        "prior_screening_row": dict(screen),
    }
    # ``seal_json`` writes atomically inside the destination directory, so the
    # canonical directory must exist before the first seal.  Do this only after
    # every authority and input check above has passed; rejected submissions
    # must not leave misleading empty adjudication directories behind.
    target.parent.mkdir(parents=True, exist_ok=True)
    sealed = seal_json(
        target,
        payload,
        artifact_type="profile_adjudication",
        sealed_at=adjudicated_at,
    )
    return _materialize_profile_adjudication(
        base=base,
        queue=queue,
        screening=screening,
        payload=payload,
        path=target,
        sha256=sealed.sha256,
        repository_root=repository_root,
        idempotent=False,
    )


def _reject_second_profile_adjudication(target: Path) -> None:
    directory = target.parent
    if not directory.exists():
        return
    payloads = {
        path.resolve()
        for path in directory.iterdir()
        if path.is_file() and path.name.endswith(".json") and not path.name.endswith(".seal.json")
    }
    sealed_payloads = {
        path.with_name(path.name[: -len(".seal.json")]).resolve()
        for path in directory.iterdir()
        if path.is_file() and path.name.endswith(".seal.json")
    }
    unexpected = (payloads | sealed_payloads) - {target.resolve()}
    if unexpected:
        raise ResearchAllocationError(
            "a second profile adjudication is forbidden for the same cycle/stage/symbol"
        )


def _read_profile_adjudication_payload(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResearchAllocationError("profile adjudication payload is invalid") from exc
    if not isinstance(value, dict):
        raise ResearchAllocationError("profile adjudication payload must be an object")
    return value


def _validate_profile_adjudication_payload(
    value: Any,
    *,
    base: Path,
    expected_path: Path | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != PROFILE_ADJUDICATION_PAYLOAD_KEYS
        or value.get("workflow") != "profile_adjudication"
    ):
        raise ResearchAllocationError("profile adjudication payload fields do not match contract")
    normalized_submission = _normalize_profile_adjudication_submission(
        _profile_adjudication_submission_from_payload(value)
    )
    adjudicated_at = _datetime(value.get("adjudicated_at"), "adjudicated_at")
    prior_queue = value.get("prior_queue_row")
    prior_screen = value.get("prior_screening_row")
    if not isinstance(prior_queue, Mapping) or not isinstance(prior_screen, Mapping):
        raise ResearchAllocationError("profile adjudication prior projections are invalid")
    symbol = prior_queue.get("symbol")
    if symbol != prior_screen.get("symbol") or not isinstance(symbol, str):
        raise ResearchAllocationError("profile adjudication prior projection symbols differ")
    context = _validate_profile_adjudication_authority(
        normalized_submission,
        base=base,
        queue_record=prior_queue,
        screen_record=prior_screen,
        symbol=symbol,
        adjudicated_at=adjudicated_at,
    )
    if (
        value.get("research_agent") != context["research_agent"]
        or value.get("original_effective_outcome")
        != context["original_effective_outcome"]
    ):
        raise ResearchAllocationError("profile adjudication derived authority fields drifted")
    canonical_path = _profile_adjudication_path(
        base=base,
        cycle=normalized_submission["profile_cycle_id"],
        stage=normalized_submission["stage"],
        symbol=symbol,
    ).resolve()
    if expected_path is not None and canonical_path != expected_path.resolve():
        raise ResearchAllocationError("profile adjudication path is not canonical")
    normalized = {
        **normalized_submission,
        "workflow": "profile_adjudication",
        "adjudicated_at": adjudicated_at.isoformat(),
        "research_agent": context["research_agent"],
        "original_effective_outcome": context["original_effective_outcome"],
        "prior_queue_row": dict(prior_queue),
        "prior_screening_row": dict(prior_screen),
    }
    if dict(value) != normalized:
        raise ResearchAllocationError("profile adjudication payload is not canonical")
    return normalized


def _validate_profile_adjudication_authority(
    submission: Mapping[str, Any],
    *,
    base: Path,
    queue_record: Mapping[str, Any],
    screen_record: Mapping[str, Any],
    symbol: str,
    adjudicated_at: dt.datetime,
) -> dict[str, Any]:
    cycle = str(submission["profile_cycle_id"])
    stage = str(submission["stage"])
    repository_root = base.parent.parent.resolve()
    if (
        queue_record.get("symbol") != symbol
        or screen_record.get("symbol") != symbol
        or queue_record.get("profile_cycle_id") != cycle
        or queue_record.get("task_type") != stage
        or queue_record.get("status") != "completed"
    ):
        raise ResearchAllocationError(
            "profile adjudication requires the completed current quick-profile projection"
        )
    completion = _latest_cycle_stage_completion(
        queue_record,
        base=base,
        stage=stage,
        cycle=cycle,
        require_claim=True,
    )
    if completion is None:
        raise ResearchAllocationError(
            "profile adjudication lacks an authenticated claim/success completion"
        )
    profile_path = (repository_root / str(completion.get("result_path"))).resolve()
    evaluation_path = (repository_root / str(completion.get("evaluation_path"))).resolve()
    try:
        profile_path.relative_to(repository_root)
        evaluation_path.relative_to(repository_root)
        profile_seal = verify_sealed(profile_path)
        evaluation_seal = verify_sealed(evaluation_path)
        profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
        evaluation_payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError, ValueError) as exc:
        raise ResearchAllocationError(
            "profile adjudication source profile/evaluation is invalid"
        ) from exc
    evaluated = evaluation_payload.get("evaluation")
    sources = profile_payload.get("sources")
    if not isinstance(evaluated, Mapping) or not isinstance(sources, list):
        raise ResearchAllocationError("profile adjudication source payload is invalid")
    original_outcome = _text(evaluated.get("next_stage"), "evaluation.next_stage")
    if original_outcome not in TERMINAL_STAGES - {"needs_manual_review"}:
        raise ResearchAllocationError(
            "profile adjudication requires a terminal sealed profile evaluation"
        )
    source_ids = {
        item.get("source_id")
        for item in sources
        if isinstance(item, Mapping) and isinstance(item.get("source_id"), str)
    }
    qa_source_ids: set[str] = set()
    for qa_source in submission["qa_sources"]:
        source_id = str(qa_source["source_id"])
        if source_id in source_ids or source_id in qa_source_ids:
            raise ResearchAllocationError(
                f"profile adjudication QA source ID is not unique: {source_id}"
            )
        source_path = (repository_root / str(qa_source["path"])).resolve()
        try:
            source_path.relative_to(repository_root)
            actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        except (OSError, ValueError) as exc:
            raise ResearchAllocationError(
                f"profile adjudication QA source is unavailable: {source_id}"
            ) from exc
        if actual_sha256 != qa_source["sha256"]:
            raise ResearchAllocationError(
                f"profile adjudication QA source SHA mismatch: {source_id}"
            )
        qa_source_ids.add(source_id)
    adjudication_source_ids = {
        source_id
        for item in submission["evidence"]
        for source_id in item["source_ids"]
    }
    if not adjudication_source_ids <= source_ids | qa_source_ids:
        raise ResearchAllocationError(
            "profile adjudication QA evidence references unknown sealed sources"
        )
    expected_bindings = {
        "profile_path": completion.get("result_path"),
        "profile_sha256": profile_seal.sha256,
        "evaluation_path": completion.get("evaluation_path"),
        "evaluation_sha256": evaluation_seal.sha256,
        "claim_path": completion.get("claim_path"),
        "claim_sha256": completion.get("claim_sha256"),
        "success_path": completion.get("success_path"),
        "success_sha256": completion.get("success_sha256"),
    }
    if any(submission.get(field) != expected for field, expected in expected_bindings.items()):
        raise ResearchAllocationError(
            "profile adjudication does not bind the authenticated profile completion"
        )
    if (
        queue_record.get("result_path") != completion.get("evaluation_path")
        or screen_record.get("profile_evaluation_path") != completion.get("evaluation_path")
        or screen_record.get("decision") != original_outcome
    ):
        raise ResearchAllocationError(
            "profile adjudication prior projection is not the canonical profile terminal state"
        )
    grant = _verify_funded_full_market_profile_grant(
        queue_record=queue_record,
        screen_record=screen_record,
        root=base,
        repository_root=repository_root,
        symbol=symbol,
        expected_cycle_id=cycle,
        required=True,
        context="profile adjudication",
        require_screen_research_brief=False,
    )
    assert grant is not None
    full_market_bindings = {
        "full_market_result_path": grant["result_path"],
        "full_market_result_sha256": grant["result_sha256"],
        "full_market_candidate_sha256": grant["decision"]["candidate_sha256"],
    }
    if any(
        submission.get(field) != expected
        for field, expected in full_market_bindings.items()
    ):
        raise ResearchAllocationError(
            "profile adjudication does not bind its funded full-market authority"
        )
    manager = _investment_manager_for_cohort(
        [queue_record],
        repository_root=repository_root,
    )
    research_agent = _text(completion.get("agent"), "profile completion agent")
    reviewer = str(submission["reviewer"])
    submitted_manager = str(submission["manager"])
    if len({submitted_manager, reviewer, research_agent}) != 3:
        raise ResearchAllocationError(
            "profile adjudication manager and QA reviewer must be independent of the researcher"
        )
    if manager is None or submitted_manager != manager:
        raise ResearchAllocationError(
            f"profile adjudication must be recorded by the original manager: expected {manager}"
        )
    completed_at = _datetime(completion.get("finished_at"), "profile completion finished_at")
    if adjudicated_at <= completed_at:
        raise ResearchAllocationError(
            "profile adjudication must be later than the sealed profile completion"
        )
    return {
        "research_agent": research_agent,
        "original_effective_outcome": original_outcome,
    }


def _expected_profile_adjudication_projection(
    *,
    payload: Mapping[str, Any],
    relative_path: str,
    sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    queue = dict(payload["prior_queue_row"])
    screen = dict(payload["prior_screening_row"])
    original_outcome = str(payload["original_effective_outcome"])
    outcome = str(payload["outcome"])
    effective_outcome = (
        "needs_manual_review"
        if outcome == "material_error_confirmed"
        else original_outcome
    )
    history = list(queue.get("stage_history") or [])
    if any(
        isinstance(item, Mapping) and item.get("stage") == "profile_adjudication"
        for item in history
    ):
        raise ResearchAllocationError("a second profile adjudication history event is forbidden")
    history.append(
        {
            "stage": "profile_adjudication",
            "status": "completed",
            "started_at": None,
            "finished_at": payload["adjudicated_at"],
            "agent": payload["manager"],
            "reviewer": payload["reviewer"],
            "research_agent": payload["research_agent"],
            "evaluated_stage": payload["stage"],
            "outcome": outcome,
            "next_stage": effective_outcome,
            "profile_path": payload["profile_path"],
            "profile_sha256": payload["profile_sha256"],
            "evaluation_path": payload["evaluation_path"],
            "evaluation_sha256": payload["evaluation_sha256"],
            "adjudication_path": relative_path,
            "adjudication_sha256": sha256,
            "additional_budget_hours": 0.0,
        }
    )
    next_action = _profile_adjudication_next_action(
        outcome=outcome,
        triggers=list(payload["restart_triggers"]),
    )
    common = {
        "reason": payload["reason"],
        "next_action": next_action,
        "revisit_triggers": list(payload["restart_triggers"]),
        "profile_adjudication_path": relative_path,
        "profile_adjudication_sha256": sha256,
        "profile_adjudication_outcome": outcome,
        "profile_adjudication_cycle_id": payload["profile_cycle_id"],
        "profile_adjudication_decisive_question": payload["corrected_decisive_question"],
        "profile_adjudication_evidence_ids": [
            item["evidence_id"] for item in payload["evidence"]
        ],
    }
    queue.update(common)
    queue["stage_history"] = history
    evidence = list(screen.get("evidence") or [])
    screen.update(common)
    screen["decision"] = effective_outcome
    screen["evidence"] = list(
        dict.fromkeys(
            evidence
            + [
                f"profile_adjudication:{relative_path}",
                f"profile_adjudication_sha256:{sha256}",
            ]
        )
    )
    return queue, screen, effective_outcome


def _verified_profile_adjudication_defer_selection(
    *,
    base: Path,
    repository_root: Path,
    payload: Mapping[str, Any],
    relative_path: str,
    sha256: str,
    effective_outcome: str,
) -> tuple[str, str]:
    cycle = str(payload["profile_cycle_id"])
    selection_path = (base / "profiles" / cycle / "quick-profile-selection.json").resolve()
    try:
        selection_path.relative_to(repository_root.resolve())
        sealed = verify_sealed(selection_path)
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError, ValueError) as exc:
        raise ResearchAllocationError(
            "profile adjudication projection drift: terminal defer selection is invalid"
        ) from exc
    _validate_profile_selection_payload(
        selection,
        artifact_type=sealed.artifact_type,
        cycle=cycle,
        stage="quick_profile",
        next_stage="scoped_research",
    )
    _validate_profile_stage_selection_semantics(
        selection,
        base=base,
        repository_root=repository_root,
        cycle=cycle,
        stage="quick_profile",
        next_stage="scoped_research",
        comparison_name="quick-profile-comparison.json",
    )
    symbol = str(payload["prior_queue_row"]["symbol"])
    rows = [row for row in selection["ranking"] if row.get("symbol") == symbol]
    expected_summary = _profile_adjudication_summary(
        payload,
        path=relative_path,
        sha256=sha256,
        effective_outcome=effective_outcome,
    )
    if (
        len(rows) != 1
        or rows[0].get("selected") is not False
        or rows[0].get("profile_adjudication") != expected_summary
        or _datetime(selection.get("finalized_at"), "selection.finalized_at")
        <= _datetime(payload.get("adjudicated_at"), "adjudicated_at")
    ):
        raise ResearchAllocationError(
            "profile adjudication is not terminally deferred by its sealed selection"
        )
    return selection_path.relative_to(repository_root).as_posix(), sealed.sha256


def _validate_profile_adjudication_live_projection(
    *,
    base: Path,
    repository_root: Path,
    payload: Mapping[str, Any],
    relative_path: str,
    sha256: str,
    current_queue: Mapping[str, Any] | None,
    current_screen: Mapping[str, Any] | None,
) -> str:
    """Accept only the immediate overlay or its sealed defer; later cycles fail closed."""

    expected_queue, expected_screen, effective_outcome = (
        _expected_profile_adjudication_projection(
            payload=payload,
            relative_path=relative_path,
            sha256=sha256,
        )
    )
    if current_queue == expected_queue and current_screen == expected_screen:
        return effective_outcome
    if not isinstance(current_queue, Mapping) or not isinstance(current_screen, Mapping):
        raise ResearchAllocationError("profile adjudication projection drift")
    selection_relative, selection_sha256 = _verified_profile_adjudication_defer_selection(
        base=base,
        repository_root=repository_root,
        payload=payload,
        relative_path=relative_path,
        sha256=sha256,
        effective_outcome=effective_outcome,
    )
    expected_binding = (relative_path, sha256, payload["outcome"])
    if current_queue.get("profile_cycle_id") != payload.get("profile_cycle_id"):
        raise ResearchAllocationError(
            "a later profile cycle requires a sealed adjudication successor workflow"
        )
    live_evidence = current_screen.get("evidence")
    selection_evidence = {
        f"stage_selection:{selection_relative}",
        f"stage_selection_sha256:{selection_sha256}",
    }
    if (
        tuple(current_queue.get(field) for field in PROFILE_ADJUDICATION_BINDING_FIELDS)
        != expected_binding
        or tuple(current_screen.get(field) for field in PROFILE_ADJUDICATION_BINDING_FIELDS)
        != expected_binding
        or current_queue.get("profile_quick_selection_path") != selection_relative
        or current_queue.get("profile_quick_selection_sha256") != selection_sha256
        or not isinstance(live_evidence, list)
        or not selection_evidence.issubset(set(live_evidence))
    ):
        raise ResearchAllocationError("profile adjudication projection drift")
    normalized_queue = dict(current_queue)
    normalized_queue.pop("profile_quick_selection_path", None)
    normalized_queue.pop("profile_quick_selection_sha256", None)
    normalized_screen = dict(current_screen)
    normalized_screen["evidence"] = [
        item for item in live_evidence if item not in selection_evidence
    ]
    if normalized_queue != expected_queue or normalized_screen != expected_screen:
        raise ResearchAllocationError("profile adjudication projection drift")
    return effective_outcome


def _materialize_profile_adjudication(
    *,
    base: Path,
    queue: list[dict[str, Any]],
    screening: list[dict[str, Any]],
    payload: Mapping[str, Any],
    path: Path,
    sha256: str,
    repository_root: Path,
    idempotent: bool,
) -> dict[str, Any]:
    symbol = str(payload["prior_queue_row"]["symbol"])
    relative = path.resolve().relative_to(repository_root).as_posix()
    expected_queue, expected_screen, effective_outcome = (
        _expected_profile_adjudication_projection(
            payload=payload,
            relative_path=relative,
            sha256=sha256,
        )
    )
    current_queue = _one_record(queue, symbol, "research queue")
    current_screen = _one_record(screening, symbol, "screening")
    prior_queue = dict(payload["prior_queue_row"])
    prior_screen = dict(payload["prior_screening_row"])
    queue_is_immediate = current_queue in (prior_queue, expected_queue)
    screen_is_immediate = current_screen in (prior_screen, expected_screen)
    if not queue_is_immediate or not screen_is_immediate:
        effective_outcome = _validate_profile_adjudication_live_projection(
            base=base,
            repository_root=repository_root,
            payload=payload,
            relative_path=relative,
            sha256=sha256,
            current_queue=current_queue,
            current_screen=current_screen,
        )
        return {
            "schema_version": 1,
            "symbol": symbol,
            "profile_cycle_id": payload["profile_cycle_id"],
            "stage": payload["stage"],
            "outcome": payload["outcome"],
            "effective_outcome": effective_outcome,
            "additional_budget_hours": 0.0,
            "adjudication_path": relative,
            "adjudication_sha256": sha256,
            "adjudicated_at": payload["adjudicated_at"],
            "idempotent": True,
            "portfolio_action": None,
        }
    if current_screen != expected_screen:
        write_jsonl(
            base / SCREENING_FILE,
            [expected_screen if item.get("symbol") == symbol else item for item in screening],
        )
    if current_queue != expected_queue:
        write_jsonl(
            base / RESEARCH_QUEUE_FILE,
            [expected_queue if item.get("symbol") == symbol else item for item in queue],
        )
    return {
        "schema_version": 1,
        "symbol": symbol,
        "profile_cycle_id": payload["profile_cycle_id"],
        "stage": payload["stage"],
        "outcome": payload["outcome"],
        "effective_outcome": effective_outcome,
        "additional_budget_hours": 0.0,
        "adjudication_path": relative,
        "adjudication_sha256": sha256,
        "adjudicated_at": payload["adjudicated_at"],
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def profile_adjudication_ledger_status(
    *,
    root: str | Path,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    """Verify every sealed profile adjudication and its live projection."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    cycle_filter = None
    if cycle_id is not None:
        cycle_filter = _text(cycle_id, "cycle_id")
        if not CYCLE_RE.fullmatch(cycle_filter):
            raise ResearchAllocationError("profile adjudication status cycle_id is invalid")
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    screening = read_jsonl(base / SCREENING_FILE)
    queue_by_symbol = {str(item.get("symbol")): item for item in queue}
    screen_by_symbol = {str(item.get("symbol")): item for item in screening}
    errors: dict[str, set[str]] = {}
    verified: list[dict[str, Any]] = []
    verified_paths: set[str] = set()
    identities: set[tuple[str, str, str, str]] = set()
    adjudication_root = base / "profiles"
    payload_paths: set[Path] = set()
    seal_payload_paths: set[Path] = set()
    if adjudication_root.is_dir():
        cycle_dirs = [
            path
            for path in adjudication_root.iterdir()
            if path.is_dir() and (cycle_filter is None or path.name == cycle_filter)
        ]
        for cycle_dir in cycle_dirs:
            root_dir = cycle_dir / "profile-adjudications"
            if not root_dir.exists():
                continue
            for path in root_dir.rglob("*.json"):
                if path.name.endswith(".seal.json"):
                    seal_payload_paths.add(
                        path.with_name(path.name[: -len(".seal.json")]).resolve()
                    )
                else:
                    payload_paths.add(path.resolve())
    for path in sorted(payload_paths | seal_payload_paths):
        symbol_hint = _profile_adjudication_symbol_hint(path)
        if path not in payload_paths:
            errors.setdefault(symbol_hint, set()).add("seal exists without payload")
            continue
        if path not in seal_payload_paths:
            errors.setdefault(symbol_hint, set()).add("payload exists without seal")
            continue
        try:
            payload, sealed = _verify_profile_adjudication_artifact(
                path,
                base=base,
            )
            symbol = str(payload["prior_queue_row"]["symbol"])
            identity = (
                str(payload["profile_cycle_id"]),
                str(payload["stage"]),
                symbol,
                str(payload["profile_sha256"]),
            )
            if identity in identities:
                raise ResearchAllocationError("duplicate profile adjudication identity")
            identities.add(identity)
            relative = path.relative_to(repository_root).as_posix()
            current_queue = queue_by_symbol.get(symbol)
            current_screen = screen_by_symbol.get(symbol)
            effective = _validate_profile_adjudication_live_projection(
                base=base,
                repository_root=repository_root,
                payload=payload,
                relative_path=relative,
                sha256=sealed.sha256,
                current_queue=current_queue,
                current_screen=current_screen,
            )
            verified_paths.add(relative)
            verified.append(
                _profile_adjudication_summary(
                    payload,
                    path=relative,
                    sha256=sealed.sha256,
                    effective_outcome=effective,
                )
            )
        except (OSError, SealingError, ValueError, ResearchAllocationError) as exc:
            errors.setdefault(symbol_hint, set()).add(str(exc))

    relevant_symbols = {
        str(item.get("symbol"))
        for item in queue
        if cycle_filter is None or item.get("profile_cycle_id") == cycle_filter
    } | {
        str(item.get("symbol"))
        for item in screening
        if cycle_filter is None or item.get("profile_cycle_id") == cycle_filter
    }
    for symbol in sorted(relevant_symbols):
        queued = queue_by_symbol.get(symbol, {})
        screen = screen_by_symbol.get(symbol, {})
        queue_values = tuple(queued.get(field) for field in PROFILE_ADJUDICATION_BINDING_FIELDS)
        screen_values = tuple(screen.get(field) for field in PROFILE_ADJUDICATION_BINDING_FIELDS)
        queue_present = any(value is not None for value in queue_values)
        screen_present = any(value is not None for value in screen_values)
        if not queue_present and not screen_present:
            continue
        if (
            not all(isinstance(value, str) and value for value in queue_values)
            or queue_values != screen_values
        ):
            errors.setdefault(symbol, set()).add(
                "profile adjudication queue/screen binding is incomplete or inconsistent"
            )
            continue
        if str(queue_values[0]) not in verified_paths:
            errors.setdefault(symbol, set()).add(
                "profile adjudication projection does not bind a verified artifact"
            )

    invalid = [
        {"symbol": symbol, "error": "; ".join(sorted(messages))}
        for symbol, messages in sorted(errors.items())
    ]
    verified.sort(
        key=lambda item: (
            str(item["profile_cycle_id"]),
            str(item["stage"]),
            str(item["symbol"]),
        )
    )
    quarantined = [
        item["symbol"]
        for item in verified
        if item["outcome"] == "material_error_confirmed"
    ]
    return {
        "schema_version": 1,
        "cycle_id": cycle_filter,
        "adjudication_count": len(verified),
        "material_error_confirmed_count": sum(
            item["outcome"] == "material_error_confirmed" for item in verified
        ),
        "manager_upheld_count": sum(
            item["outcome"] == "manager_upheld" for item in verified
        ),
        "quarantined_count": len(quarantined),
        "quarantined_symbols": sorted(quarantined),
        "profile_adjudications": verified,
        "invalid_artifact_count": len(invalid),
        "invalid_artifacts": invalid,
    }


def _profile_adjudication_symbol_hint(path: Path) -> str:
    try:
        ticker = path.parent.name
        if re.fullmatch(r"[0-9]{6}", ticker):
            return f"CN:{ticker}"
    except (AttributeError, ValueError):
        pass
    return "__profile_adjudication__"


def _verify_profile_adjudication_artifact(
    path: Path,
    *,
    base: Path,
) -> tuple[dict[str, Any], Any]:
    try:
        sealed = verify_sealed(path)
    except (OSError, SealingError, ValueError) as exc:
        raise ResearchAllocationError("profile adjudication seal is invalid") from exc
    if sealed.artifact_type != "profile_adjudication":
        raise ResearchAllocationError("profile adjudication artifact type is invalid")
    payload = _validate_profile_adjudication_payload(
        _read_profile_adjudication_payload(path),
        base=base,
        expected_path=path,
    )
    if sealed.sealed_at != _datetime(payload["adjudicated_at"], "adjudicated_at"):
        raise ResearchAllocationError("profile adjudication seal time does not match payload")
    return payload, sealed


def _profile_adjudication_summary(
    payload: Mapping[str, Any],
    *,
    path: str,
    sha256: str,
    effective_outcome: str,
) -> dict[str, Any]:
    return {
        "symbol": payload["prior_queue_row"]["symbol"],
        "profile_cycle_id": payload["profile_cycle_id"],
        "stage": payload["stage"],
        "profile_path": payload["profile_path"],
        "profile_sha256": payload["profile_sha256"],
        "outcome": payload["outcome"],
        "effective_outcome": effective_outcome,
        "reason": payload["reason"],
        "material_errors": list(payload["material_errors"]),
        "evidence": list(payload["evidence"]),
        "qa_sources": list(payload["qa_sources"]),
        "corrected_decisive_question": payload["corrected_decisive_question"],
        "corrected_decisive_answer": dict(payload["corrected_decisive_answer"]),
        "restart_triggers": list(payload["restart_triggers"]),
        "research_agent": payload["research_agent"],
        "reviewer": payload["reviewer"],
        "manager": payload["manager"],
        "additional_budget_hours": 0.0,
        "adjudicated_at": payload["adjudicated_at"],
        "adjudication_path": path,
        "adjudication_sha256": sha256,
        "portfolio_action": None,
    }


def _profile_adjudication_for_profile_row(
    item: Mapping[str, Any],
    *,
    symbol: str,
    repository_root: Path,
    base: Path,
) -> dict[str, Any] | None:
    """Return the authenticated latest QA view carried by a mutable row.

    The profile/evaluation package remains immutable, so every downstream
    consumer must explicitly prefer this append-only adjudication when the
    binding is present.  A partial or forged binding fails closed.
    """

    values = tuple(item.get(field) for field in PROFILE_ADJUDICATION_BINDING_FIELDS)
    if not any(value is not None for value in values):
        return None
    if not all(isinstance(value, str) and value for value in values):
        raise ResearchAllocationError(
            f"profile adjudication binding is incomplete: {symbol}"
        )
    relative_path, expected_sha256, expected_outcome = values
    path = (repository_root / str(relative_path)).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ResearchAllocationError(
            f"profile adjudication binding escapes repository root: {symbol}"
        ) from exc
    payload, sealed = _verify_profile_adjudication_artifact(path, base=base)
    bound_symbol = payload["prior_queue_row"].get("symbol")
    expected_brief = (
        payload["profile_cycle_id"],
        payload["corrected_decisive_question"],
        [entry["evidence_id"] for entry in payload["evidence"]],
    )
    if item.get("profile_cycle_id") != payload.get("profile_cycle_id"):
        raise ResearchAllocationError(
            "a later profile cycle requires a sealed adjudication successor workflow"
        )
    if (
        sealed.sha256 != expected_sha256
        or bound_symbol != symbol
        or payload.get("outcome") != expected_outcome
        or tuple(item.get(field) for field in PROFILE_ADJUDICATION_BRIEF_FIELDS)
        != expected_brief
    ):
        raise ResearchAllocationError(
            f"profile adjudication binding does not match its sealed artifact: {symbol}"
        )
    effective_outcome = (
        "needs_manual_review"
        if payload["outcome"] == "material_error_confirmed"
        else str(payload["original_effective_outcome"])
    )
    return _profile_adjudication_summary(
        payload,
        path=str(relative_path),
        sha256=sealed.sha256,
        effective_outcome=effective_outcome,
    )


def _require_profile_adjudication_package_binding(
    package: Mapping[str, Any],
    *,
    queue_record: Mapping[str, Any],
    symbol: str,
    base: Path,
    repository_root: Path,
) -> dict[str, Any] | None:
    adjudication = _profile_adjudication_for_profile_row(
        queue_record,
        symbol=symbol,
        repository_root=repository_root,
        base=base,
    )
    submitted = package.get("profile_adjudication_binding")
    if adjudication is None:
        if submitted is not None:
            raise ResearchAllocationError(
                "profile package supplied an adjudication binding without sealed authority"
            )
        return None
    expected = {
        "path": adjudication["adjudication_path"],
        "sha256": adjudication["adjudication_sha256"],
        "corrected_decisive_question": adjudication["corrected_decisive_question"],
        "evidence_ids": [item["evidence_id"] for item in adjudication["evidence"]],
    }
    if submitted != expected:
        raise ResearchAllocationError(
            "profile package must bind the sealed adjudication corrected research brief"
        )
    return adjudication
