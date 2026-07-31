from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .coverage_store import serialized_coverage_write
from .manager_screening import ManagerScreeningError, manager_screen_status
from .models import PolicyKind, PolicyValidationError, load_policy
from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed


class ManagerScreenAllocationV3Error(ValueError):
    """Raised when the future-only manager-screen allocation contract is invalid."""


CONTRACT_ARTIFACT_TYPE = "manager_screen_allocation_v3_contract"
CONTRACT_RELATIVE_PATH = Path("governance") / "allocation-v3" / "contract.json"
PRIOR_SEND_TO_ANALYST_LIMIT = 200
PRIOR_PURCHASE_EFFORT_HOURS = 1.5
EXPECTED_ACTIVATION_COMPLETED_COMPANY_COUNT = 3_000
EXPECTED_ACTIVATION_REMAINING_COMPANY_COUNT = 2_445

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MANAGER_KEYS = {"agent", "model", "tools"}
_CONTRACT_KEYS = {
    "schema_version",
    "run_id",
    "frozen_at",
    "scope",
    "prior_policy",
    "future_policy",
    "rules",
    "capacity",
    "activation",
    "inherited_ledger",
    "inherited_ledger_sha256",
    "activation_queue",
    "commitment_classification",
    "commitment_classification_sha256",
    "manager",
    "reason",
    "portfolio_action",
}
_SCOPE_KEYS = {
    "manifest_path",
    "manifest_sha256",
    "baseline_intake_path",
    "baseline_intake_sha256",
    "information_cutoff",
}
_PRIOR_POLICY_KEYS = {
    "policy_id",
    "version",
    "path",
    "file_sha256",
    "payload_sha256",
    "decision_contract_version",
    "send_to_analyst_capacity_per_run",
    "quick_profile_effort_budget_hours",
}
_FUTURE_POLICY_KEYS = _PRIOR_POLICY_KEYS | {
    "research_candidate_requires_allocation",
    "routes",
}
_RULES = {
    "candidate_state": "candidate_unfunded",
    "deferred_state": "deferred_full_market",
    "direct_send_to_analyst": False,
    "full_scope_before_allocation": True,
    "historical_routes_immutable": True,
    "started_or_completed_budget_non_refundable": True,
    "unstarted_commitment_may_be_suspended": True,
}
_CAPACITY_KEYS = {
    "historical_purchase_count",
    "historical_effort_budget_hours",
    "absolute_funded_company_limit",
    "absolute_funded_effort_budget_hours",
    "irreversible_commitment_count",
    "irreversible_effort_budget_hours",
    "revocable_commitment_count",
    "revocable_effort_budget_hours",
    "post_scope_selection_capacity",
    "purchase_effort_budget_hours",
}
_ACTIVATION_KEYS = {
    "control_state",
    "control_event_path",
    "control_event_sha256",
    "completed_company_count",
    "remaining_unbatched_count",
    "open_batch_count",
    "open_company_count",
}
_LEDGER_KEYS = {
    "symbol",
    "purchase_kind",
    "effort_budget_hours",
    "source_kind",
    "source_path",
    "source_sha256",
    "source_id",
    "decision_contract_version",
    "purchased_at",
}
_QUEUE_SNAPSHOT_KEYS = {
    "path",
    "sha256",
    "size",
    "record_count",
    "purchased_state_count",
    "purchased_states",
    "purchased_states_sha256",
}
_PURCHASED_STATE_KEYS = {
    "symbol",
    "queue_record_sha256",
    "manager_screen_result_path",
    "manager_screen_result_sha256",
    "task_type",
    "status",
    "assigned_agent",
    "started_at",
    "finished_at",
    "failure_reason",
    "result_path",
    "preceding_stage",
    "attempt_history",
    "stage_history",
}
_CLASSIFICATION_KEYS = {
    "symbol",
    "commitment_class",
    "reason_codes",
    "queue_record_sha256",
    "sealed_progress",
}
_SEALED_PROGRESS_KEYS = {
    "path",
    "sha256",
    "artifact_type",
    "research_stage",
    "sealed_at",
}
_SOURCE_KINDS = {
    "manager_screen_result",
    "manager_screen_quote_impact_result",
    "manager_screen_legacy_transition_result",
}
_ROUTES = {"pass", "watch", "send_to_analyst"}


@serialized_coverage_write
def freeze_manager_screen_allocation_v3_contract(
    *,
    root: str | Path,
    run_id: str,
    manager: Mapping[str, Any],
    reason: str,
    frozen_at: dt.datetime,
    prior_policy_path: str | Path = "policies/manager-screening.json",
    future_policy_path: str | Path = ("policies/manager-screening-allocation-v3.json"),
    expected_completed_company_count: int = (EXPECTED_ACTIVATION_COMPLETED_COMPANY_COUNT),
    expected_remaining_unbatched_count: int = (EXPECTED_ACTIVATION_REMAINING_COMPANY_COUNT),
) -> dict[str, Any]:
    """Freeze the singleton v3 run contract without changing any legacy route.

    The contract is intentionally future-only.  It inventories purchases already
    made by immutable v1/v2 decisions, but does not cancel, refund, or materialize
    any analyst work.
    """

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    timestamp = _aware(frozen_at, "frozen_at")
    normalized_manager = _manager(manager)
    explanation = _text(reason, "reason")
    expected_completed = _non_negative_int(
        expected_completed_company_count,
        "expected_completed_company_count",
    )
    expected_remaining = _non_negative_int(
        expected_remaining_unbatched_count,
        "expected_remaining_unbatched_count",
    )
    contract_path = base / "manager-screen" / run / CONTRACT_RELATIVE_PATH
    seal_path = contract_path.with_name(f"{contract_path.name}.seal.json")
    if contract_path.exists() != seal_path.exists():
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 contract is only partially sealed"
        )
    if contract_path.exists():
        existing = verify_manager_screen_allocation_v3_contract(
            root=base,
            run_id=run,
        )
        requested_prior_policy = _prior_policy_binding(
            path=_repository_path(prior_policy_path, repository_root),
            repository_root=repository_root,
        )
        requested_future_policy = _future_policy_binding(
            path=_repository_path(future_policy_path, repository_root),
            repository_root=repository_root,
        )
        if (
            existing["frozen_at"] != timestamp.isoformat()
            or existing["manager"] != normalized_manager
            or existing["reason"] != explanation
            or existing["prior_policy"] != requested_prior_policy
            or existing["future_policy"] != requested_future_policy
            or existing["activation"]["completed_company_count"] != expected_completed
            or existing["activation"]["remaining_unbatched_count"] != expected_remaining
        ):
            raise ManagerScreenAllocationV3Error(
                "sealed manager-screen allocation v3 contract conflicts with request"
            )
        return _contract_summary(
            existing,
            contract_path=contract_path,
            contract_sha256=verify_sealed(contract_path).sha256,
            repository_root=repository_root,
            idempotent=True,
        )

    scope = _scope_binding(
        base=base,
        repository_root=repository_root,
        run_id=run,
    )
    if timestamp < _parse_datetime(scope["information_cutoff"], "information_cutoff"):
        raise ManagerScreenAllocationV3Error(
            "frozen_at cannot predate the sealed scope information cutoff"
        )
    prior_policy = _prior_policy_binding(
        path=_repository_path(prior_policy_path, repository_root),
        repository_root=repository_root,
    )
    future_policy = _future_policy_binding(
        path=_repository_path(future_policy_path, repository_root),
        repository_root=repository_root,
    )
    if future_policy["path"] == prior_policy["path"]:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 future policy must use a new immutable path"
        )
    ledger_state = rebuild_manager_screen_inherited_purchase_ledger(
        root=base,
        run_id=run,
        cutoff=timestamp,
    )
    if ledger_state["open_batch_count"]:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation requires zero open manager-screen batches"
        )
    if ledger_state["pending_precontract_quote_impact_count"]:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation requires all pre-contract quote-impact reviews "
            "to be sealed or absent"
        )
    if ledger_state["pending_precontract_legacy_transition"]:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation requires the pre-contract legacy transition "
            "to be sealed or absent"
        )
    _require_inherited_capacity(ledger_state)
    commitment_state = classify_manager_screen_inherited_commitments(
        root=base,
        run_id=run,
        inherited_ledger=ledger_state["ledger"],
        cutoff=timestamp,
    )
    activation = _activation_snapshot(
        base=base,
        repository_root=repository_root,
        run_id=run,
        frozen_at=timestamp,
        expected_completed_company_count=expected_completed,
        expected_remaining_unbatched_count=expected_remaining,
        ledger_state=ledger_state,
    )
    capacity = _capacity_contract(ledger_state, commitment_state)
    payload = {
        "schema_version": 1,
        "run_id": run,
        "frozen_at": timestamp.isoformat(),
        "scope": scope,
        "prior_policy": prior_policy,
        "future_policy": future_policy,
        "rules": dict(_RULES),
        "capacity": capacity,
        "activation": activation,
        "inherited_ledger": ledger_state["ledger"],
        "inherited_ledger_sha256": ledger_state["ledger_sha256"],
        "activation_queue": commitment_state["queue_snapshot"],
        "commitment_classification": commitment_state["classifications"],
        "commitment_classification_sha256": commitment_state["classifications_sha256"],
        "manager": normalized_manager,
        "reason": explanation,
        "portfolio_action": None,
    }
    _validate_contract_payload(payload)
    sealed = seal_json(
        contract_path,
        payload,
        artifact_type=CONTRACT_ARTIFACT_TYPE,
        sealed_at=timestamp,
    )
    return _contract_summary(
        payload,
        contract_path=contract_path,
        contract_sha256=sealed.sha256,
        repository_root=repository_root,
        idempotent=False,
    )


def verify_manager_screen_allocation_v3_contract(
    *,
    root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Verify the sealed contract and rebuild its pre-contract purchase ledger."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    contract_path = base / "manager-screen" / run / CONTRACT_RELATIVE_PATH
    payload, sealed = _sealed_object(
        contract_path,
        artifact_type=CONTRACT_ARTIFACT_TYPE,
    )
    if payload.get("run_id") != run:
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 contract run_id does not match its path"
        )
    if sealed.path.resolve() != contract_path.resolve():
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 contract escaped its canonical path"
        )
    _validate_contract_payload(payload)
    frozen_at = _parse_datetime(payload["frozen_at"], "frozen_at")
    if (
        _scope_binding(
            base=base,
            repository_root=repository_root,
            run_id=run,
        )
        != payload["scope"]
    ):
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 scope binding no longer matches"
        )
    prior_path = _repository_path(payload["prior_policy"]["path"], repository_root)
    if (
        _prior_policy_binding(
            path=prior_path,
            repository_root=repository_root,
        )
        != payload["prior_policy"]
    ):
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 prior-policy binding no longer matches"
        )
    future_path = _repository_path(payload["future_policy"]["path"], repository_root)
    if (
        _future_policy_binding(
            path=future_path,
            repository_root=repository_root,
        )
        != payload["future_policy"]
    ):
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 future-policy binding no longer matches"
        )
    _verify_activation_control(
        payload["activation"],
        repository_root=repository_root,
        run_id=run,
        frozen_at=frozen_at,
    )
    _verify_contract_sealed_progress(
        payload["commitment_classification"],
        repository_root=repository_root,
        frozen_at=frozen_at,
    )
    ledger_state = rebuild_manager_screen_inherited_purchase_ledger(
        root=base,
        run_id=run,
        cutoff=frozen_at,
    )
    _require_inherited_capacity(ledger_state)
    if ledger_state["open_batch_count"]:
        raise ManagerScreenAllocationV3Error(
            "sealed allocation v3 snapshot unexpectedly contains an open batch"
        )
    if ledger_state["pending_precontract_quote_impact_count"]:
        raise ManagerScreenAllocationV3Error(
            "sealed allocation v3 snapshot contains an unresolved quote-impact review"
        )
    if ledger_state["pending_precontract_legacy_transition"]:
        raise ManagerScreenAllocationV3Error(
            "sealed allocation v3 snapshot contains an unresolved legacy transition"
        )
    if (
        ledger_state["ledger"] != payload["inherited_ledger"]
        or ledger_state["ledger_sha256"] != payload["inherited_ledger_sha256"]
        or _capacity_contract(
            ledger_state,
            _classification_counts(payload["commitment_classification"]),
        )
        != payload["capacity"]
    ):
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 inherited ledger no longer matches"
        )
    return payload


def manager_screen_allocation_v3_activation_drift_status(
    *,
    root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Compare live queue bytes with the activation snapshot without invalidating it."""

    base = Path(root)
    payload = verify_manager_screen_allocation_v3_contract(
        root=base,
        run_id=run_id,
    )
    queue_path = base.parent.parent.resolve() / payload["activation_queue"]["path"]
    try:
        current = queue_path.read_bytes()
    except OSError as exc:
        raise ManagerScreenAllocationV3Error(
            "research queue is unavailable for allocation v3 drift status"
        ) from exc
    current_sha256 = hashlib.sha256(current).hexdigest()
    activation_sha256 = payload["activation_queue"]["sha256"]
    return {
        "schema_version": 1,
        "run_id": payload["run_id"],
        "activation_queue_sha256": activation_sha256,
        "current_queue_sha256": current_sha256,
        "drifted": current_sha256 != activation_sha256,
        "contract_valid": True,
        "portfolio_action": None,
    }


def rebuild_manager_screen_inherited_purchase_ledger(
    *,
    root: str | Path,
    run_id: str,
    cutoff: dt.datetime | None = None,
) -> dict[str, Any]:
    """Rebuild non-recyclable purchases from sealed results, never from queue state."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    boundary = _aware(cutoff, "cutoff") if cutoff is not None else None
    run_dir = base / "manager-screen" / run
    ledger: list[dict[str, Any]] = []
    open_batch_count = 0
    pending_quote_impact_count = 0
    pending_legacy_transition = False
    source_counts = {
        "manager_screen_result": 0,
        "manager_screen_quote_impact_result": 0,
        "manager_screen_legacy_transition_result": 0,
    }
    if run_dir.exists() and not run_dir.is_dir():
        raise ManagerScreenAllocationV3Error("manager-screen run path is not a directory")
    if run_dir.is_dir():
        for batch_dir in _batch_dirs(run_dir):
            batch_path = batch_dir / "batch.json"
            batch, batch_seal = _sealed_object(
                batch_path,
                artifact_type="manager_screen_batch",
            )
            _validate_batch_identity(batch, batch_dir=batch_dir, run_id=run)
            if boundary is not None and batch_seal.sealed_at > boundary:
                _reject_post_contract_direct_purchases(
                    batch_dir=batch_dir,
                    repository_root=repository_root,
                    run_id=run,
                    cutoff=boundary,
                )
                continue
            result_presence = _artifact_presence(batch_dir / "result.json")
            supersession_presence = _artifact_presence(batch_dir / "supersession.json")
            if result_presence == "partial" or supersession_presence == "partial":
                raise ManagerScreenAllocationV3Error(
                    f"manager-screen batch contains a partially sealed terminal: {batch_dir.name}"
                )
            if result_presence == "complete" and supersession_presence == "complete":
                raise ManagerScreenAllocationV3Error(
                    "manager-screen batch cannot contain both result and supersession"
                )
            if supersession_presence == "complete":
                supersession, supersession_seal = _sealed_object(
                    batch_dir / "supersession.json",
                    artifact_type="manager_screen_batch_supersession",
                )
                _validate_supersession(
                    supersession,
                    supersession_sha256=supersession_seal.sha256,
                    batch=batch,
                    batch_sha256=batch_seal.sha256,
                    batch_dir=batch_dir,
                    run_id=run,
                    repository_root=repository_root,
                )
                if boundary is not None and supersession_seal.sealed_at > boundary:
                    open_batch_count += 1
                continue
            if result_presence == "absent":
                open_batch_count += 1
                continue
            result, result_seal = _sealed_object(
                batch_dir / "result.json",
                artifact_type="manager_screen_result",
            )
            if boundary is not None and result_seal.sealed_at > boundary:
                open_batch_count += 1
                continue
            decision_contract_version, effort = _validate_manager_result(
                batch=batch,
                batch_sha256=batch_seal.sha256,
                result=result,
                result_seal_sha256=result_seal.sha256,
                batch_dir=batch_dir,
                run_id=run,
                repository_root=repository_root,
            )
            result_path = batch_dir / "result.json"
            source_path = _relative(result_path, repository_root)
            for decision in result["decisions"]:
                if decision["route"] != "send_to_analyst":
                    continue
                ledger.append(
                    _ledger_entry(
                        symbol=decision["symbol"],
                        effort_budget_hours=effort,
                        source_kind="manager_screen_result",
                        source_path=source_path,
                        source_sha256=result_seal.sha256,
                        source_id=batch_dir.name,
                        decision_contract_version=decision_contract_version,
                        purchased_at=result["recorded_at"],
                    )
                )
                source_counts["manager_screen_result"] += 1
            quote_state = _quote_impact_purchases(
                batch_dir=batch_dir,
                repository_root=repository_root,
                run_id=run,
                batch_id=batch_dir.name,
                original_result_path=result_path,
                original_result_sha256=result_seal.sha256,
                cutoff=boundary,
            )
            ledger.extend(quote_state["ledger"])
            source_counts["manager_screen_quote_impact_result"] += len(quote_state["ledger"])
            pending_quote_impact_count += quote_state["pending_precontract_count"]

        legacy_state = _legacy_transition_purchases(
            run_dir=run_dir,
            repository_root=repository_root,
            run_id=run,
            cutoff=boundary,
        )
        ledger.extend(legacy_state["ledger"])
        source_counts["manager_screen_legacy_transition_result"] += len(legacy_state["ledger"])
        pending_legacy_transition = legacy_state["pending_precontract"]

    ledger.sort(key=lambda item: item["symbol"])
    symbols = [item["symbol"] for item in ledger]
    if len(symbols) != len(set(symbols)):
        duplicates = sorted(symbol for symbol in set(symbols) if symbols.count(symbol) > 1)
        raise ManagerScreenAllocationV3Error(
            f"one company has multiple inherited analyst purchases: {duplicates}"
        )
    effort_hours = round(
        sum(float(item["effort_budget_hours"]) for item in ledger),
        10,
    )
    return {
        "schema_version": 1,
        "run_id": run,
        "ledger": ledger,
        "ledger_sha256": _payload_sha256(ledger),
        "purchase_count": len(ledger),
        "effort_budget_hours": effort_hours,
        "source_counts": source_counts,
        "open_batch_count": open_batch_count,
        "pending_precontract_quote_impact_count": pending_quote_impact_count,
        "pending_precontract_legacy_transition": pending_legacy_transition,
        "queue_state_used": False,
        "historical_purchases_only": True,
    }


def classify_manager_screen_inherited_commitments(
    *,
    root: str | Path,
    run_id: str,
    inherited_ledger: list[Mapping[str, Any]],
    cutoff: dt.datetime,
) -> dict[str, Any]:
    """Classify inherited commitments using sealed progress plus a bound queue snapshot.

    Queue state is used only for facts that cannot yet be sealed (a live claim or an
    attempt).  Completed research must be corroborated by a sealed profile/evaluation;
    a bare mutable ``completed`` flag is never accepted as proof.
    """

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    boundary = _aware(cutoff, "cutoff")
    queue_path = base / "research_queue.jsonl"
    try:
        raw = queue_path.read_bytes()
        text = raw.decode("utf-8")
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManagerScreenAllocationV3Error(
            "research queue is invalid during allocation v3 activation"
        ) from exc
    if any(not isinstance(row, dict) for row in rows):
        raise ManagerScreenAllocationV3Error("research queue rows must be objects")
    queue_by_symbol: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = _symbol(row.get("symbol"))
        if symbol in queue_by_symbol:
            raise ManagerScreenAllocationV3Error(
                f"research queue contains a duplicate symbol: {symbol}"
            )
        queue_by_symbol[symbol] = row

    ledger = [_validate_ledger_entry(item) for item in inherited_ledger]
    if ledger != sorted(ledger, key=lambda item: item["symbol"]):
        raise ManagerScreenAllocationV3Error(
            "inherited ledger must be symbol-sorted before commitment classification"
        )
    purchased_states = []
    classifications = []
    for purchase in ledger:
        symbol = purchase["symbol"]
        queued = queue_by_symbol.get(symbol)
        if queued is None:
            raise ManagerScreenAllocationV3Error(
                f"research queue is missing an inherited purchase: {symbol}"
            )
        if (
            queued.get("manager_screen_run_id") != run
            or queued.get("manager_screen_route") != "send_to_analyst"
            or queued.get("manager_screen_result_path") != purchase["source_path"]
            or queued.get("manager_screen_result_sha256") != purchase["source_sha256"]
        ):
            raise ManagerScreenAllocationV3Error(
                f"research queue does not bind the inherited sealed purchase: {symbol}"
            )
        attempts = queued.get("attempt_history")
        history = queued.get("stage_history")
        if attempts is None:
            attempts = []
        if history is None:
            history = []
        if not isinstance(attempts, list) or not isinstance(history, list):
            raise ManagerScreenAllocationV3Error(
                f"research queue attempt/stage history is invalid: {symbol}"
            )
        queue_record_sha256 = _payload_sha256(queued)
        state = {
            "symbol": symbol,
            "queue_record_sha256": queue_record_sha256,
            "manager_screen_result_path": purchase["source_path"],
            "manager_screen_result_sha256": purchase["source_sha256"],
            "task_type": queued.get("task_type"),
            "status": queued.get("status"),
            "assigned_agent": queued.get("assigned_agent"),
            "started_at": queued.get("started_at"),
            "finished_at": queued.get("finished_at"),
            "failure_reason": queued.get("failure_reason"),
            "result_path": queued.get("result_path"),
            "preceding_stage": queued.get("preceding_stage"),
            "attempt_history": attempts,
            "stage_history": history,
        }
        _validate_purchased_state(state)
        purchased_states.append(state)
        purchased_at = _parse_datetime(purchase["purchased_at"], "purchased_at")
        if purchased_at > boundary:
            raise ManagerScreenAllocationV3Error(
                f"inherited purchase postdates activation cutoff: {symbol}"
            )
        sealed_progress = _sealed_progress_for_symbol(
            base=base,
            repository_root=repository_root,
            symbol=symbol,
            purchased_at=purchased_at,
            cutoff=boundary,
        )
        formal_history = _formal_history_after_purchase(
            history,
            purchased_at=purchased_at,
        )
        reason_codes = []
        if sealed_progress:
            reason_codes.append("sealed_formal_progress")
        if attempts:
            reason_codes.append("attempt_history_present")
        if formal_history:
            reason_codes.append("formal_stage_history_present")
        if queued.get("status") == "running":
            reason_codes.append("queue_running")
        if queued.get("status") in {"completed", "failed", "skipped"}:
            reason_codes.append("queue_terminal")
        if queued.get("assigned_agent") is not None:
            reason_codes.append("claim_identity_present")
        if queued.get("started_at") is not None or queued.get("finished_at") is not None:
            reason_codes.append("claim_timestamp_present")
        if queued.get("failure_reason") is not None:
            reason_codes.append("failure_trace_present")
        if queued.get("result_path") is not None:
            reason_codes.append("result_pointer_present")
        if queued.get("preceding_stage") != "manager_screen":
            reason_codes.append("preceding_stage_not_manager_screen")
        if (
            queued.get("status") == "completed"
            and queued.get("task_type")
            in {
                "quick_profile",
                "targeted_followup",
                "scoped_research",
                "deep_research",
            }
            and not sealed_progress
        ):
            raise ManagerScreenAllocationV3Error(
                f"completed queue state lacks sealed formal progress: {symbol}"
            )
        revocable = (
            queued.get("task_type") == "quick_profile"
            and queued.get("status") == "pending"
            and queued.get("assigned_agent") is None
            and queued.get("started_at") is None
            and queued.get("finished_at") is None
            and queued.get("failure_reason") is None
            and queued.get("result_path") is None
            and queued.get("preceding_stage") == "manager_screen"
            and not attempts
            and not formal_history
            and not sealed_progress
        )
        commitment_class = "revocable" if revocable else "irreversible"
        if revocable:
            reason_codes = ["pending_never_claimed_without_sealed_progress"]
        elif not reason_codes:
            reason_codes = ["not_strictly_revocable_fail_closed"]
        classifications.append(
            {
                "symbol": symbol,
                "commitment_class": commitment_class,
                "reason_codes": sorted(set(reason_codes)),
                "queue_record_sha256": queue_record_sha256,
                "sealed_progress": sealed_progress,
            }
        )

    purchased_states.sort(key=lambda item: item["symbol"])
    classifications.sort(key=lambda item: item["symbol"])
    queue_snapshot = {
        "path": _relative(queue_path, repository_root),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "record_count": len(rows),
        "purchased_state_count": len(purchased_states),
        "purchased_states": purchased_states,
        "purchased_states_sha256": _payload_sha256(purchased_states),
    }
    return {
        "schema_version": 1,
        "run_id": run,
        "queue_snapshot": queue_snapshot,
        "classifications": classifications,
        "classifications_sha256": _payload_sha256(classifications),
        "irreversible_count": sum(
            item["commitment_class"] == "irreversible" for item in classifications
        ),
        "revocable_count": sum(item["commitment_class"] == "revocable" for item in classifications),
    }


def _sealed_progress_for_symbol(
    *,
    base: Path,
    repository_root: Path,
    symbol: str,
    purchased_at: dt.datetime,
    cutoff: dt.datetime,
) -> list[dict[str, Any]]:
    ticker = symbol.split(":", 1)[1]
    profiles_root = base / "profiles"
    if not profiles_root.is_dir():
        return []
    candidates: set[Path] = set()
    for pattern in (f"*/{ticker}/*.profile.json", f"*/{ticker}/*.evaluation.json"):
        candidates.update(profiles_root.glob(pattern))
    progress = []
    for path in sorted(candidates):
        presence = _artifact_presence(path)
        if presence != "complete":
            raise ManagerScreenAllocationV3Error(
                f"formal progress is only partially sealed: {path}"
            )
        try:
            sealed = verify_sealed(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
            raise ManagerScreenAllocationV3Error(
                f"formal progress is not validly sealed: {path}"
            ) from exc
        if sealed.artifact_type not in {
            "quick_profile_package",
            "quick_profile_evaluation",
        }:
            continue
        if sealed.sealed_at < purchased_at or sealed.sealed_at > cutoff:
            continue
        profile = payload.get("profile")
        payload_symbol = (
            profile.get("symbol") if isinstance(profile, Mapping) else payload.get("symbol")
        )
        if payload_symbol != symbol:
            raise ManagerScreenAllocationV3Error(f"sealed formal progress symbol mismatch: {path}")
        research_stage = (
            profile.get("research_stage") if isinstance(profile, Mapping) else "evaluation"
        )
        progress.append(
            {
                "path": _relative(path, repository_root),
                "sha256": sealed.sha256,
                "artifact_type": sealed.artifact_type,
                "research_stage": (
                    research_stage
                    if isinstance(research_stage, str) and research_stage
                    else "quick_profile"
                ),
                "sealed_at": sealed.sealed_at.isoformat(),
            }
        )
    return progress


def _formal_history_after_purchase(
    history: list[Any],
    *,
    purchased_at: dt.datetime,
) -> list[Mapping[str, Any]]:
    formal_stages = {
        "quick_profile",
        "targeted_followup",
        "scoped_research",
        "deep_research",
        "underwriting",
    }
    result = []
    for item in history:
        if not isinstance(item, Mapping) or item.get("stage") not in formal_stages:
            continue
        timestamp = item.get("started_at") or item.get("finished_at")
        if timestamp is None:
            result.append(item)
            continue
        if _parse_datetime(timestamp, "stage_history timestamp") >= purchased_at:
            result.append(item)
    return result


def _activation_snapshot(
    *,
    base: Path,
    repository_root: Path,
    run_id: str,
    frozen_at: dt.datetime,
    expected_completed_company_count: int,
    expected_remaining_unbatched_count: int,
    ledger_state: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        status = manager_screen_status(root=base, run_id=run_id)
    except ManagerScreeningError as exc:
        raise ManagerScreenAllocationV3Error(
            "manager-screen status is invalid during allocation v3 activation"
        ) from exc
    control = status.get("control")
    if not isinstance(control, Mapping) or control.get("state") != "paused":
        raise ManagerScreenAllocationV3Error(
            "allocation v3 contract may only be frozen while the run is paused"
        )
    completed = _non_negative_int(
        status.get("completed_company_count"),
        "completed_company_count",
    )
    remaining = _non_negative_int(
        status.get("remaining_unbatched_count"),
        "remaining_unbatched_count",
    )
    open_batches = _non_negative_int(status.get("open_batches"), "open_batches")
    open_companies = _non_negative_int(
        status.get("open_company_count"),
        "open_company_count",
    )
    if completed != expected_completed_company_count:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation completed-company count is stale: "
            f"{completed} != {expected_completed_company_count}"
        )
    if remaining != expected_remaining_unbatched_count:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation remaining-company count is stale: "
            f"{remaining} != {expected_remaining_unbatched_count}"
        )
    if open_batches != 0 or open_companies != 0:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation requires zero open batches and companies"
        )
    if open_batches != ledger_state["open_batch_count"]:
        raise ManagerScreenAllocationV3Error(
            "manager-screen status and sealed-result scan disagree on open batches"
        )
    budget = status.get("analyst_budget")
    if not isinstance(budget, Mapping):
        raise ManagerScreenAllocationV3Error(
            "manager-screen status is missing analyst budget accounting"
        )
    if budget.get("purchased_company_count") != ledger_state["purchase_count"] or not _hours_equal(
        budget.get("purchased_effort_budget_hours"),
        ledger_state["effort_budget_hours"],
    ):
        raise ManagerScreenAllocationV3Error(
            "manager-screen status disagrees with the immutable inherited ledger"
        )
    event_path = _text(control.get("latest_event_path"), "control.latest_event_path")
    event_sha256 = _sha256(
        control.get("latest_event_sha256"),
        "control.latest_event_sha256",
    )
    activation = {
        "control_state": "paused",
        "control_event_path": event_path,
        "control_event_sha256": event_sha256,
        "completed_company_count": completed,
        "remaining_unbatched_count": remaining,
        "open_batch_count": open_batches,
        "open_company_count": open_companies,
    }
    _verify_activation_control(
        activation,
        repository_root=repository_root,
        run_id=run_id,
        frozen_at=frozen_at,
    )
    return activation


def _scope_binding(
    *,
    base: Path,
    repository_root: Path,
    run_id: str,
) -> dict[str, Any]:
    scope_dir = base / "scopes" / run_id
    manifest_path = scope_dir / "manifest.json"
    intake_path = scope_dir / "baseline-intake.json"
    manifest, manifest_seal = _sealed_object(
        manifest_path,
        artifact_type="all_a_scope_manifest",
    )
    intake, intake_seal = _sealed_object(
        intake_path,
        artifact_type="all_a_baseline_intake",
    )
    if manifest.get("run_id") != run_id or intake.get("run_id") != run_id:
        raise ManagerScreenAllocationV3Error(
            "sealed scope artifacts do not match allocation run_id"
        )
    manifest_relative = _relative(manifest_path, repository_root)
    if (
        intake.get("scope_manifest_path") != manifest_relative
        or intake.get("scope_manifest_sha256") != manifest_seal.sha256
    ):
        raise ManagerScreenAllocationV3Error(
            "baseline intake does not bind the sealed scope manifest"
        )
    cutoff = _parse_datetime(manifest.get("scope_cutoff"), "manifest.scope_cutoff")
    if _parse_datetime(intake.get("scope_cutoff"), "intake.scope_cutoff") != cutoff:
        raise ManagerScreenAllocationV3Error(
            "scope manifest and baseline intake information cutoffs differ"
        )
    return {
        "manifest_path": manifest_relative,
        "manifest_sha256": manifest_seal.sha256,
        "baseline_intake_path": _relative(intake_path, repository_root),
        "baseline_intake_sha256": intake_seal.sha256,
        "information_cutoff": cutoff.isoformat(),
    }


def _prior_policy_binding(*, path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        policy = load_policy(path)
        raw = path.read_bytes()
    except (OSError, PolicyValidationError) as exc:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 prior manager-screen policy is invalid"
        ) from exc
    if policy.kind != PolicyKind.MANAGER_SCREENING:
        raise ManagerScreenAllocationV3Error("allocation v3 prior policy must be manager_screening")
    payload = dict(policy.payload)
    if payload.get("decision_contract_version") != 2:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 must bind the current decision contract v2 policy"
        )
    capacity = _positive_int(
        payload.get("send_to_analyst_capacity_per_run"),
        "send_to_analyst_capacity_per_run",
    )
    effort = _positive_hours(
        payload.get("quick_profile_effort_budget_hours"),
        "quick_profile_effort_budget_hours",
    )
    if capacity != PRIOR_SEND_TO_ANALYST_LIMIT or not _hours_equal(
        effort,
        PRIOR_PURCHASE_EFFORT_HOURS,
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 prior policy must bind 200 purchases at 1.5 hours each"
        )
    return {
        "policy_id": policy.policy_id,
        "version": policy.version,
        "path": _relative(path, repository_root),
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_sha256": _payload_sha256(payload),
        "decision_contract_version": 2,
        "send_to_analyst_capacity_per_run": capacity,
        "quick_profile_effort_budget_hours": effort,
    }


def _future_policy_binding(*, path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        policy = load_policy(path)
        raw = path.read_bytes()
    except (OSError, PolicyValidationError) as exc:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 future manager-screen policy is invalid"
        ) from exc
    if policy.kind != PolicyKind.MANAGER_SCREENING:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 future policy must be manager_screening"
        )
    payload = dict(policy.payload)
    routes = payload.get("routes")
    if (
        payload.get("decision_contract_version") != 3
        or payload.get("research_candidate_requires_allocation") is not True
        or not isinstance(routes, list)
        or set(routes) != {"pass", "watch", "research_candidate"}
        or len(routes) != 3
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 future policy must nominate unfunded research candidates"
        )
    capacity = _positive_int(
        payload.get("send_to_analyst_capacity_per_run"),
        "future send_to_analyst_capacity_per_run",
    )
    effort = _positive_hours(
        payload.get("quick_profile_effort_budget_hours"),
        "future quick_profile_effort_budget_hours",
    )
    if capacity != PRIOR_SEND_TO_ANALYST_LIMIT or not _hours_equal(
        effort,
        PRIOR_PURCHASE_EFFORT_HOURS,
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 future policy cannot expand the 200-company/300-hour cap"
        )
    return {
        "policy_id": policy.policy_id,
        "version": policy.version,
        "path": _relative(path, repository_root),
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_sha256": _payload_sha256(payload),
        "decision_contract_version": 3,
        "send_to_analyst_capacity_per_run": capacity,
        "quick_profile_effort_budget_hours": effort,
        "research_candidate_requires_allocation": True,
        "routes": ["pass", "research_candidate", "watch"],
    }


def _validate_batch_identity(
    batch: Mapping[str, Any],
    *,
    batch_dir: Path,
    run_id: str,
) -> None:
    if (
        batch.get("schema_version") != 1
        or batch.get("run_id") != run_id
        or batch.get("batch_id") != batch_dir.name
    ):
        raise ManagerScreenAllocationV3Error(
            f"manager-screen batch identity is invalid: {batch_dir.name}"
        )
    members = batch.get("members")
    if not isinstance(members, list) or not members:
        raise ManagerScreenAllocationV3Error(
            f"manager-screen batch members are invalid: {batch_dir.name}"
        )
    symbols = [_symbol(item.get("symbol")) for item in members if isinstance(item, Mapping)]
    if len(symbols) != len(members) or len(symbols) != len(set(symbols)):
        raise ManagerScreenAllocationV3Error(
            f"manager-screen batch members are missing or duplicated: {batch_dir.name}"
        )


def _validate_manager_result(
    *,
    batch: Mapping[str, Any],
    batch_sha256: str,
    result: Mapping[str, Any],
    result_seal_sha256: str,
    batch_dir: Path,
    run_id: str,
    repository_root: Path,
) -> tuple[int, float]:
    del result_seal_sha256  # The caller records this verified digest in each ledger row.
    batch_path = batch_dir / "batch.json"
    packet_path = batch_dir / "packet.json"
    packet, packet_seal = _sealed_object(
        packet_path,
        artifact_type="manager_screen_packet",
    )
    if (
        result.get("schema_version") != 1
        or result.get("run_id") != run_id
        or result.get("batch_id") != batch_dir.name
        or result.get("batch_path") != _relative(batch_path, repository_root)
        or result.get("batch_sha256") != batch_sha256
        or result.get("packet_path") != _relative(packet_path, repository_root)
        or result.get("packet_sha256") != packet_seal.sha256
        or packet.get("batch_sha256") != batch_sha256
    ):
        raise ManagerScreenAllocationV3Error(
            f"manager-screen result binding is invalid: {batch_dir.name}"
        )
    _parse_datetime(result.get("recorded_at"), "result.recorded_at")
    policy = batch.get("policy")
    if not isinstance(policy, Mapping):
        raise ManagerScreenAllocationV3Error("manager-screen batch policy is invalid")
    version = policy.get("decision_contract_version", 1)
    if version not in {1, 2}:
        raise ManagerScreenAllocationV3Error(
            "pre-contract manager-screen result must use decision contract v1 or v2"
        )
    effort = _positive_hours(
        policy.get("quick_profile_effort_budget_hours"),
        "batch.policy.quick_profile_effort_budget_hours",
    )
    if not _hours_equal(effort, PRIOR_PURCHASE_EFFORT_HOURS):
        raise ManagerScreenAllocationV3Error(
            "inherited manager-screen purchase effort must be exactly 1.5 hours"
        )
    decisions = result.get("decisions")
    if not isinstance(decisions, list):
        raise ManagerScreenAllocationV3Error("manager-screen result decisions are invalid")
    member_symbols = [item["symbol"] for item in batch["members"]]
    decision_symbols = []
    for decision in decisions:
        if not isinstance(decision, Mapping):
            raise ManagerScreenAllocationV3Error("manager-screen result decision must be an object")
        decision_symbols.append(_symbol(decision.get("symbol")))
        if decision.get("route") not in _ROUTES:
            raise ManagerScreenAllocationV3Error(
                "manager-screen result contains an invalid inherited route"
            )
    if decision_symbols != member_symbols:
        raise ManagerScreenAllocationV3Error(
            "manager-screen result must cover its batch once and in member order"
        )
    return int(version), effort


def _quote_impact_purchases(
    *,
    batch_dir: Path,
    repository_root: Path,
    run_id: str,
    batch_id: str,
    original_result_path: Path,
    original_result_sha256: str,
    cutoff: dt.datetime | None,
) -> dict[str, Any]:
    reviews_root = batch_dir / "quote-impact-reviews"
    if not reviews_root.exists():
        return {"ledger": [], "pending_precontract_count": 0}
    if not reviews_root.is_dir():
        raise ManagerScreenAllocationV3Error("quote-impact reviews path is not a directory")
    entries = sorted(reviews_root.iterdir(), key=lambda path: path.name)
    if any(not entry.is_dir() for entry in entries) or len(entries) > 1:
        raise ManagerScreenAllocationV3Error(
            "each manager-screen batch may have at most one quote-impact review"
        )
    if not entries:
        return {"ledger": [], "pending_precontract_count": 0}
    review_dir = entries[0]
    plan, plan_seal = _sealed_object(
        review_dir / "plan.json",
        artifact_type="manager_screen_quote_impact_plan",
    )
    plan_before = cutoff is None or plan_seal.sealed_at <= cutoff
    result_presence = _artifact_presence(review_dir / "result.json")
    if result_presence == "partial":
        raise ManagerScreenAllocationV3Error("quote-impact result is only partially sealed")
    if result_presence == "absent":
        return {
            "ledger": [],
            "pending_precontract_count": int(plan_before),
        }
    packet, packet_seal = _sealed_object(
        review_dir / "packet.json",
        artifact_type="manager_screen_quote_impact_packet",
    )
    result, result_seal = _sealed_object(
        review_dir / "result.json",
        artifact_type="manager_screen_quote_impact_result",
    )
    common = (run_id, batch_id, review_dir.name)
    if (
        (plan.get("run_id"), plan.get("batch_id"), plan.get("review_id")) != common
        or (packet.get("run_id"), packet.get("batch_id"), packet.get("review_id")) != common
        or (result.get("run_id"), result.get("batch_id"), result.get("review_id")) != common
        or plan.get("original_result_path") != _relative(original_result_path, repository_root)
        or plan.get("original_result_sha256") != original_result_sha256
        or result.get("original_result_path") != _relative(original_result_path, repository_root)
        or result.get("original_result_sha256") != original_result_sha256
        or packet.get("plan_path") != _relative(review_dir / "plan.json", repository_root)
        or packet.get("plan_sha256") != plan_seal.sha256
        or result.get("plan_path") != _relative(review_dir / "plan.json", repository_root)
        or result.get("plan_sha256") != plan_seal.sha256
        or result.get("packet_path") != _relative(review_dir / "packet.json", repository_root)
        or result.get("packet_sha256") != packet_seal.sha256
    ):
        raise ManagerScreenAllocationV3Error(
            f"quote-impact result binding is invalid: {batch_id}/{review_dir.name}"
        )
    effort = _positive_hours(
        (plan.get("policy") or {}).get("quick_profile_effort_budget_hours")
        if isinstance(plan.get("policy"), Mapping)
        else None,
        "quote-impact quick_profile_effort_budget_hours",
    )
    if not _hours_equal(effort, PRIOR_PURCHASE_EFFORT_HOURS):
        raise ManagerScreenAllocationV3Error(
            "inherited quote-impact purchase effort must be exactly 1.5 hours"
        )
    purchased_at = _parse_datetime(result.get("recorded_at"), "quote result.recorded_at")
    reviews = result.get("reviews")
    if not isinstance(reviews, list):
        raise ManagerScreenAllocationV3Error("quote-impact reviews are invalid")
    ledger = []
    seen: set[str] = set()
    for review in reviews:
        if not isinstance(review, Mapping):
            raise ManagerScreenAllocationV3Error("quote-impact review must be an object")
        symbol = _symbol(review.get("symbol"))
        if symbol in seen:
            raise ManagerScreenAllocationV3Error("quote-impact review symbols are duplicated")
        seen.add(symbol)
        action = review.get("action")
        if action not in {"keep", "replacement"}:
            raise ManagerScreenAllocationV3Error("quote-impact review action is invalid")
        if action != "replacement":
            continue
        effective = review.get("effective_decision")
        if not isinstance(effective, Mapping) or effective.get("symbol") != symbol:
            raise ManagerScreenAllocationV3Error("quote-impact replacement decision is invalid")
        old_route = review.get("old_route")
        new_route = effective.get("route")
        if old_route not in _ROUTES or new_route not in _ROUTES:
            raise ManagerScreenAllocationV3Error("quote-impact replacement route is invalid")
        if old_route != "send_to_analyst" and new_route == "send_to_analyst":
            if cutoff is not None and result_seal.sealed_at > cutoff:
                raise ManagerScreenAllocationV3Error(
                    "post-contract quote-impact review cannot purchase analyst budget directly"
                )
            ledger.append(
                _ledger_entry(
                    symbol=symbol,
                    effort_budget_hours=effort,
                    source_kind="manager_screen_quote_impact_result",
                    source_path=_relative(review_dir / "result.json", repository_root),
                    source_sha256=result_seal.sha256,
                    source_id=f"{batch_id}/{review_dir.name}",
                    decision_contract_version=2,
                    purchased_at=purchased_at.isoformat(),
                )
            )
    summary = result.get("summary")
    if not isinstance(summary, Mapping) or summary.get("new_send_to_analyst_count") != len(ledger):
        raise ManagerScreenAllocationV3Error(
            "quote-impact new-send count does not match its sealed reviews"
        )
    return {
        "ledger": ledger,
        "pending_precontract_count": int(plan_before and result_seal.sealed_at > cutoff)
        if cutoff is not None
        else 0,
    }


def _legacy_transition_purchases(
    *,
    run_dir: Path,
    repository_root: Path,
    run_id: str,
    cutoff: dt.datetime | None,
) -> dict[str, Any]:
    transition_dir = run_dir / "legacy-transition-001"
    plan_presence = _artifact_presence(transition_dir / "plan.json")
    if plan_presence == "absent":
        return {"ledger": [], "pending_precontract": False}
    if plan_presence == "partial":
        raise ManagerScreenAllocationV3Error("legacy transition plan is only partially sealed")
    plan, plan_seal = _sealed_object(
        transition_dir / "plan.json",
        artifact_type="manager_screen_legacy_transition_plan",
    )
    plan_before = cutoff is None or plan_seal.sealed_at <= cutoff
    result_presence = _artifact_presence(transition_dir / "result.json")
    if result_presence == "partial":
        raise ManagerScreenAllocationV3Error("legacy transition result is only partially sealed")
    if result_presence == "absent":
        return {"ledger": [], "pending_precontract": plan_before}
    packet, packet_seal = _sealed_object(
        transition_dir / "packet.json",
        artifact_type="manager_screen_legacy_transition_packet",
    )
    result, result_seal = _sealed_object(
        transition_dir / "result.json",
        artifact_type="manager_screen_legacy_transition_result",
    )
    transition_id = "legacy-transition-001"
    if (
        plan.get("run_id") != run_id
        or plan.get("transition_id") != transition_id
        or packet.get("run_id") != run_id
        or packet.get("transition_id") != transition_id
        or result.get("run_id") != run_id
        or result.get("transition_id") != transition_id
        or packet.get("plan_path") != _relative(transition_dir / "plan.json", repository_root)
        or packet.get("plan_sha256") != plan_seal.sha256
        or result.get("plan_path") != _relative(transition_dir / "plan.json", repository_root)
        or result.get("plan_sha256") != plan_seal.sha256
        or result.get("packet_path") != _relative(transition_dir / "packet.json", repository_root)
        or result.get("packet_sha256") != packet_seal.sha256
    ):
        raise ManagerScreenAllocationV3Error("legacy transition result binding is invalid")
    adoption_symbols = [
        _symbol(member.get("symbol"))
        for member in plan.get("members", [])
        if isinstance(member, Mapping) and member.get("action") == "adoption"
    ]
    decisions = result.get("decisions")
    if not isinstance(decisions, list):
        raise ManagerScreenAllocationV3Error("legacy transition adoption decisions are invalid")
    if sorted(item.get("symbol") for item in decisions if isinstance(item, Mapping)) != sorted(
        adoption_symbols
    ):
        raise ManagerScreenAllocationV3Error(
            "legacy transition decisions do not cover the adoption population"
        )
    purchased_at = _parse_datetime(
        result.get("recorded_at"),
        "legacy transition recorded_at",
    )
    ledger = []
    for decision in decisions:
        symbol = _symbol(decision.get("symbol"))
        route = decision.get("route")
        if route not in _ROUTES:
            raise ManagerScreenAllocationV3Error("legacy transition contains an invalid route")
        if route != "send_to_analyst":
            continue
        if cutoff is not None and result_seal.sealed_at > cutoff:
            raise ManagerScreenAllocationV3Error(
                "post-contract legacy adoption cannot purchase analyst budget directly"
            )
        ledger.append(
            _ledger_entry(
                symbol=symbol,
                effort_budget_hours=PRIOR_PURCHASE_EFFORT_HOURS,
                source_kind="manager_screen_legacy_transition_result",
                source_path=_relative(transition_dir / "result.json", repository_root),
                source_sha256=result_seal.sha256,
                source_id=transition_id,
                decision_contract_version=1,
                purchased_at=purchased_at.isoformat(),
            )
        )
    return {
        "ledger": ledger,
        "pending_precontract": bool(
            cutoff is not None and plan_before and result_seal.sealed_at > cutoff
        ),
    }


def _reject_post_contract_direct_purchases(
    *,
    batch_dir: Path,
    repository_root: Path,
    run_id: str,
    cutoff: dt.datetime,
) -> None:
    result_path = batch_dir / "result.json"
    if _artifact_presence(result_path) == "absent":
        return
    result, _ = _sealed_object(result_path, artifact_type="manager_screen_result")
    if result.get("run_id") != run_id or result.get("batch_id") != batch_dir.name:
        raise ManagerScreenAllocationV3Error("post-contract batch identity is invalid")
    decisions = result.get("decisions")
    if not isinstance(decisions, list):
        raise ManagerScreenAllocationV3Error("post-contract decisions are invalid")
    if any(
        isinstance(decision, Mapping) and decision.get("route") == "send_to_analyst"
        for decision in decisions
    ):
        raise ManagerScreenAllocationV3Error(
            "post-contract manager-screen result cannot purchase analyst budget directly"
        )
    del repository_root, cutoff


def _validate_supersession(
    supersession: Mapping[str, Any],
    *,
    supersession_sha256: str,
    batch: Mapping[str, Any],
    batch_sha256: str,
    batch_dir: Path,
    run_id: str,
    repository_root: Path,
) -> None:
    del supersession_sha256
    if (
        supersession.get("run_id") != run_id
        or supersession.get("batch_id") != batch_dir.name
        or supersession.get("batch_path") != _relative(batch_dir / "batch.json", repository_root)
        or supersession.get("batch_sha256") != batch_sha256
        or supersession.get("released_member_count") != len(batch["members"])
        or supersession.get("disposition") != "superseded_before_decision"
    ):
        raise ManagerScreenAllocationV3Error(
            f"manager-screen supersession binding is invalid: {batch_dir.name}"
        )


def _verify_activation_control(
    activation: Mapping[str, Any],
    *,
    repository_root: Path,
    run_id: str,
    frozen_at: dt.datetime,
) -> None:
    if not isinstance(activation, Mapping) or set(activation) != _ACTIVATION_KEYS:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation snapshot fields do not match v1"
        )
    if (
        activation.get("control_state") != "paused"
        or activation.get("open_batch_count") != 0
        or activation.get("open_company_count") != 0
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation snapshot must be paused with no open work"
        )
    _non_negative_int(
        activation.get("completed_company_count"),
        "activation.completed_company_count",
    )
    _non_negative_int(
        activation.get("remaining_unbatched_count"),
        "activation.remaining_unbatched_count",
    )
    control_path = _repository_path(
        activation.get("control_event_path"),
        repository_root,
    )
    control, sealed = _sealed_object(
        control_path,
        artifact_type="manager_screen_run_control_event",
    )
    expected_parent = repository_root / "coverage" / "cn-a" / "manager-screen" / run_id / "control"
    if control_path.parent.resolve() != expected_parent.resolve():
        raise ManagerScreenAllocationV3Error(
            "allocation v3 activation control event is outside the run"
        )
    if (
        sealed.sha256 != activation.get("control_event_sha256")
        or control.get("run_id") != run_id
        or control.get("state") != "paused"
        or _parse_datetime(control.get("recorded_at"), "control.recorded_at") > frozen_at
    ):
        raise ManagerScreenAllocationV3Error("allocation v3 activation control binding is invalid")


def _verify_contract_sealed_progress(
    classifications: list[Mapping[str, Any]],
    *,
    repository_root: Path,
    frozen_at: dt.datetime,
) -> None:
    for classification in classifications:
        symbol = classification["symbol"]
        for reference in classification["sealed_progress"]:
            path = _repository_path(reference["path"], repository_root)
            payload, sealed = _sealed_object(
                path,
                artifact_type=reference["artifact_type"],
            )
            profile = payload.get("profile")
            payload_symbol = (
                profile.get("symbol") if isinstance(profile, Mapping) else payload.get("symbol")
            )
            if (
                sealed.sha256 != reference["sha256"]
                or sealed.sealed_at.isoformat() != reference["sealed_at"]
                or sealed.sealed_at > frozen_at
                or payload_symbol != symbol
            ):
                raise ManagerScreenAllocationV3Error(
                    f"allocation v3 sealed formal-progress binding is invalid: {symbol}"
                )


def _validate_contract_payload(payload: Mapping[str, Any]) -> None:
    if (
        not isinstance(payload, Mapping)
        or set(payload) != _CONTRACT_KEYS
        or payload.get("schema_version") != 1
        or payload.get("portfolio_action") is not None
    ):
        raise ManagerScreenAllocationV3Error(
            "manager-screen allocation v3 contract fields do not match schema v1"
        )
    _identifier(payload.get("run_id"), "run_id")
    _parse_datetime(payload.get("frozen_at"), "frozen_at")
    _manager(payload.get("manager"))
    _text(payload.get("reason"), "reason")
    scope = payload.get("scope")
    if not isinstance(scope, Mapping) or set(scope) != _SCOPE_KEYS:
        raise ManagerScreenAllocationV3Error("allocation v3 scope fields are invalid")
    for key in ("manifest_path", "baseline_intake_path"):
        _relative_text(scope.get(key), f"scope.{key}")
    for key in ("manifest_sha256", "baseline_intake_sha256"):
        _sha256(scope.get(key), f"scope.{key}")
    _parse_datetime(scope.get("information_cutoff"), "scope.information_cutoff")
    prior = payload.get("prior_policy")
    if not isinstance(prior, Mapping) or set(prior) != _PRIOR_POLICY_KEYS:
        raise ManagerScreenAllocationV3Error("allocation v3 prior-policy fields are invalid")
    _relative_text(prior.get("path"), "prior_policy.path")
    _sha256(prior.get("file_sha256"), "prior_policy.file_sha256")
    _sha256(prior.get("payload_sha256"), "prior_policy.payload_sha256")
    if (
        prior.get("decision_contract_version") != 2
        or prior.get("send_to_analyst_capacity_per_run") != PRIOR_SEND_TO_ANALYST_LIMIT
        or not _hours_equal(
            prior.get("quick_profile_effort_budget_hours"),
            PRIOR_PURCHASE_EFFORT_HOURS,
        )
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 prior-policy capacity binding is invalid"
        )
    future = payload.get("future_policy")
    if not isinstance(future, Mapping) or set(future) != _FUTURE_POLICY_KEYS:
        raise ManagerScreenAllocationV3Error("allocation v3 future-policy fields are invalid")
    _relative_text(future.get("path"), "future_policy.path")
    _sha256(future.get("file_sha256"), "future_policy.file_sha256")
    _sha256(future.get("payload_sha256"), "future_policy.payload_sha256")
    if (
        future.get("decision_contract_version") != 3
        or future.get("send_to_analyst_capacity_per_run") != PRIOR_SEND_TO_ANALYST_LIMIT
        or not _hours_equal(
            future.get("quick_profile_effort_budget_hours"),
            PRIOR_PURCHASE_EFFORT_HOURS,
        )
        or future.get("research_candidate_requires_allocation") is not True
        or future.get("routes") != ["pass", "research_candidate", "watch"]
        or future.get("path") == prior.get("path")
    ):
        raise ManagerScreenAllocationV3Error("allocation v3 future-policy binding is invalid")
    if payload.get("rules") != _RULES:
        raise ManagerScreenAllocationV3Error("allocation v3 rules are invalid")
    capacity = payload.get("capacity")
    if not isinstance(capacity, Mapping) or set(capacity) != _CAPACITY_KEYS:
        raise ManagerScreenAllocationV3Error("allocation v3 capacity fields are invalid")
    _validate_capacity(capacity)
    activation = payload.get("activation")
    if not isinstance(activation, Mapping) or set(activation) != _ACTIVATION_KEYS:
        raise ManagerScreenAllocationV3Error("allocation v3 activation fields are invalid")
    ledger = payload.get("inherited_ledger")
    if not isinstance(ledger, list):
        raise ManagerScreenAllocationV3Error("allocation v3 inherited ledger is invalid")
    normalized = [_validate_ledger_entry(item) for item in ledger]
    if normalized != ledger or ledger != sorted(ledger, key=lambda item: item["symbol"]):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 inherited ledger must be normalized and symbol-sorted"
        )
    if len({item["symbol"] for item in ledger}) != len(ledger):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 inherited ledger contains duplicate symbols"
        )
    if _payload_sha256(ledger) != _sha256(
        payload.get("inherited_ledger_sha256"),
        "inherited_ledger_sha256",
    ):
        raise ManagerScreenAllocationV3Error("allocation v3 inherited ledger SHA does not match")
    if len(ledger) != capacity["historical_purchase_count"] or not _hours_equal(
        sum(float(item["effort_budget_hours"]) for item in ledger),
        capacity["historical_effort_budget_hours"],
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 inherited ledger totals do not match capacity"
        )
    queue_snapshot = _validate_queue_snapshot(payload.get("activation_queue"))
    classifications = payload.get("commitment_classification")
    if not isinstance(classifications, list):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 commitment classification must be an array"
        )
    normalized_classifications = [_validate_classification(item) for item in classifications]
    if (
        normalized_classifications != classifications
        or classifications != sorted(classifications, key=lambda item: item["symbol"])
        or [item["symbol"] for item in classifications] != [item["symbol"] for item in ledger]
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 commitment classification is not normalized or complete"
        )
    if queue_snapshot["purchased_state_count"] != len(ledger):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 queue snapshot does not cover the inherited ledger"
        )
    state_by_symbol = {item["symbol"]: item for item in queue_snapshot["purchased_states"]}
    if [item["symbol"] for item in queue_snapshot["purchased_states"]] != [
        item["symbol"] for item in ledger
    ] or any(
        state_by_symbol[item["symbol"]]["queue_record_sha256"] != item["queue_record_sha256"]
        for item in classifications
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 queue states do not bind the commitment classification"
        )
    if _payload_sha256(classifications) != _sha256(
        payload.get("commitment_classification_sha256"),
        "commitment_classification_sha256",
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 commitment classification SHA does not match"
        )
    irreversible = sum(item["commitment_class"] == "irreversible" for item in classifications)
    revocable = len(classifications) - irreversible
    if (
        capacity["irreversible_commitment_count"] != irreversible
        or capacity["revocable_commitment_count"] != revocable
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 classification counts do not match capacity"
        )


def _validate_queue_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _QUEUE_SNAPSHOT_KEYS:
        raise ManagerScreenAllocationV3Error("allocation v3 queue snapshot fields are invalid")
    states = value.get("purchased_states")
    if not isinstance(states, list):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 purchased queue states must be an array"
        )
    normalized_states = [_validate_purchased_state(item) for item in states]
    if (
        normalized_states != states
        or states != sorted(states, key=lambda item: item["symbol"])
        or len({item["symbol"] for item in states}) != len(states)
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 purchased queue states are not normalized"
        )
    result = {
        "path": _relative_text(value.get("path"), "activation_queue.path"),
        "sha256": _sha256(value.get("sha256"), "activation_queue.sha256"),
        "size": _non_negative_int(value.get("size"), "activation_queue.size"),
        "record_count": _non_negative_int(
            value.get("record_count"),
            "activation_queue.record_count",
        ),
        "purchased_state_count": _non_negative_int(
            value.get("purchased_state_count"),
            "activation_queue.purchased_state_count",
        ),
        "purchased_states": normalized_states,
        "purchased_states_sha256": _sha256(
            value.get("purchased_states_sha256"),
            "activation_queue.purchased_states_sha256",
        ),
    }
    if result["purchased_state_count"] != len(states) or result[
        "purchased_states_sha256"
    ] != _payload_sha256(states):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 purchased queue state totals or SHA do not match"
        )
    return result


def _validate_purchased_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PURCHASED_STATE_KEYS:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 purchased queue state fields are invalid"
        )
    attempts = value.get("attempt_history")
    history = value.get("stage_history")
    if not isinstance(attempts, list) or not isinstance(history, list):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 purchased queue histories must be arrays"
        )
    for field in ("started_at", "finished_at"):
        timestamp = value.get(field)
        if timestamp is not None:
            _parse_datetime(timestamp, f"purchased_state.{field}")
    return {
        "symbol": _symbol(value.get("symbol")),
        "queue_record_sha256": _sha256(
            value.get("queue_record_sha256"),
            "purchased_state.queue_record_sha256",
        ),
        "manager_screen_result_path": _relative_text(
            value.get("manager_screen_result_path"),
            "purchased_state.manager_screen_result_path",
        ),
        "manager_screen_result_sha256": _sha256(
            value.get("manager_screen_result_sha256"),
            "purchased_state.manager_screen_result_sha256",
        ),
        "task_type": _text(value.get("task_type"), "purchased_state.task_type"),
        "status": _text(value.get("status"), "purchased_state.status"),
        "assigned_agent": _optional_text(
            value.get("assigned_agent"),
            "purchased_state.assigned_agent",
        ),
        "started_at": value.get("started_at"),
        "finished_at": value.get("finished_at"),
        "failure_reason": _optional_text(
            value.get("failure_reason"),
            "purchased_state.failure_reason",
        ),
        "result_path": _optional_relative_text(
            value.get("result_path"),
            "purchased_state.result_path",
        ),
        "preceding_stage": _optional_text(
            value.get("preceding_stage"),
            "purchased_state.preceding_stage",
        ),
        "attempt_history": attempts,
        "stage_history": history,
    }


def _validate_classification(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _CLASSIFICATION_KEYS:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 commitment classification fields are invalid"
        )
    commitment_class = value.get("commitment_class")
    if commitment_class not in {"irreversible", "revocable"}:
        raise ManagerScreenAllocationV3Error("allocation v3 commitment class is invalid")
    reasons = value.get("reason_codes")
    if (
        not isinstance(reasons, list)
        or not reasons
        or any(not isinstance(item, str) or not item.strip() for item in reasons)
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 classification reason codes are invalid"
        )
    normalized_reasons = sorted({item.strip() for item in reasons})
    progress = value.get("sealed_progress")
    if not isinstance(progress, list):
        raise ManagerScreenAllocationV3Error("allocation v3 sealed progress must be an array")
    normalized_progress = [_validate_sealed_progress(item) for item in progress]
    if normalized_progress != sorted(normalized_progress, key=lambda item: item["path"]):
        raise ManagerScreenAllocationV3Error("allocation v3 sealed progress must be path-sorted")
    return {
        "symbol": _symbol(value.get("symbol")),
        "commitment_class": commitment_class,
        "reason_codes": normalized_reasons,
        "queue_record_sha256": _sha256(
            value.get("queue_record_sha256"),
            "classification.queue_record_sha256",
        ),
        "sealed_progress": normalized_progress,
    }


def _validate_sealed_progress(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _SEALED_PROGRESS_KEYS:
        raise ManagerScreenAllocationV3Error("allocation v3 sealed progress fields are invalid")
    return {
        "path": _relative_text(value.get("path"), "sealed_progress.path"),
        "sha256": _sha256(value.get("sha256"), "sealed_progress.sha256"),
        "artifact_type": _text(
            value.get("artifact_type"),
            "sealed_progress.artifact_type",
        ),
        "research_stage": _text(
            value.get("research_stage"),
            "sealed_progress.research_stage",
        ),
        "sealed_at": _parse_datetime(
            value.get("sealed_at"),
            "sealed_progress.sealed_at",
        ).isoformat(),
    }


def _validate_capacity(capacity: Mapping[str, Any]) -> None:
    integer_fields = (
        "historical_purchase_count",
        "absolute_funded_company_limit",
        "irreversible_commitment_count",
        "revocable_commitment_count",
        "post_scope_selection_capacity",
    )
    for field in integer_fields:
        _non_negative_int(capacity.get(field), f"capacity.{field}")
    for field in (
        "historical_effort_budget_hours",
        "absolute_funded_effort_budget_hours",
        "purchase_effort_budget_hours",
    ):
        _positive_hours(capacity.get(field), f"capacity.{field}")
    for field in (
        "irreversible_effort_budget_hours",
        "revocable_effort_budget_hours",
    ):
        _non_negative_hours(capacity.get(field), f"capacity.{field}")
    if (
        capacity["historical_purchase_count"] != PRIOR_SEND_TO_ANALYST_LIMIT
        or capacity["absolute_funded_company_limit"] != PRIOR_SEND_TO_ANALYST_LIMIT
        or not _hours_equal(
            capacity["historical_effort_budget_hours"],
            PRIOR_SEND_TO_ANALYST_LIMIT * PRIOR_PURCHASE_EFFORT_HOURS,
        )
        or not _hours_equal(
            capacity["absolute_funded_effort_budget_hours"],
            PRIOR_SEND_TO_ANALYST_LIMIT * PRIOR_PURCHASE_EFFORT_HOURS,
        )
        or not _hours_equal(
            capacity["purchase_effort_budget_hours"],
            PRIOR_PURCHASE_EFFORT_HOURS,
        )
        or capacity["irreversible_commitment_count"] + capacity["revocable_commitment_count"]
        != PRIOR_SEND_TO_ANALYST_LIMIT
        or capacity["post_scope_selection_capacity"]
        != PRIOR_SEND_TO_ANALYST_LIMIT - capacity["irreversible_commitment_count"]
        or not _hours_equal(
            capacity["irreversible_effort_budget_hours"],
            capacity["irreversible_commitment_count"] * PRIOR_PURCHASE_EFFORT_HOURS,
        )
        or not _hours_equal(
            capacity["revocable_effort_budget_hours"],
            capacity["revocable_commitment_count"] * PRIOR_PURCHASE_EFFORT_HOURS,
        )
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 capacity must preserve the absolute 200-company/300-hour cap"
        )


def _validate_ledger_entry(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _LEDGER_KEYS:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 inherited ledger entry fields are invalid"
        )
    result = {
        "symbol": _symbol(value.get("symbol")),
        "purchase_kind": value.get("purchase_kind"),
        "effort_budget_hours": _positive_hours(
            value.get("effort_budget_hours"),
            "ledger.effort_budget_hours",
        ),
        "source_kind": value.get("source_kind"),
        "source_path": _relative_text(value.get("source_path"), "ledger.source_path"),
        "source_sha256": _sha256(value.get("source_sha256"), "ledger.source_sha256"),
        "source_id": _text(value.get("source_id"), "ledger.source_id"),
        "decision_contract_version": value.get("decision_contract_version"),
        "purchased_at": _parse_datetime(
            value.get("purchased_at"),
            "ledger.purchased_at",
        ).isoformat(),
    }
    if (
        result["purchase_kind"] != "inherited"
        or result["source_kind"] not in _SOURCE_KINDS
        or result["decision_contract_version"] not in {1, 2}
        or not _hours_equal(
            result["effort_budget_hours"],
            PRIOR_PURCHASE_EFFORT_HOURS,
        )
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 inherited ledger entry semantics are invalid"
        )
    return result


def _capacity_contract(
    ledger_state: Mapping[str, Any],
    commitment_state: Mapping[str, Any],
) -> dict[str, Any]:
    irreversible = int(commitment_state["irreversible_count"])
    revocable = int(commitment_state["revocable_count"])
    return {
        "historical_purchase_count": ledger_state["purchase_count"],
        "historical_effort_budget_hours": ledger_state["effort_budget_hours"],
        "absolute_funded_company_limit": PRIOR_SEND_TO_ANALYST_LIMIT,
        "absolute_funded_effort_budget_hours": (
            PRIOR_SEND_TO_ANALYST_LIMIT * PRIOR_PURCHASE_EFFORT_HOURS
        ),
        "irreversible_commitment_count": irreversible,
        "irreversible_effort_budget_hours": (irreversible * PRIOR_PURCHASE_EFFORT_HOURS),
        "revocable_commitment_count": revocable,
        "revocable_effort_budget_hours": revocable * PRIOR_PURCHASE_EFFORT_HOURS,
        "post_scope_selection_capacity": PRIOR_SEND_TO_ANALYST_LIMIT - irreversible,
        "purchase_effort_budget_hours": PRIOR_PURCHASE_EFFORT_HOURS,
    }


def _classification_counts(
    classifications: list[Mapping[str, Any]],
) -> dict[str, int]:
    irreversible = sum(item.get("commitment_class") == "irreversible" for item in classifications)
    return {
        "irreversible_count": irreversible,
        "revocable_count": len(classifications) - irreversible,
    }


def _require_inherited_capacity(ledger_state: Mapping[str, Any]) -> None:
    if ledger_state.get("purchase_count") != PRIOR_SEND_TO_ANALYST_LIMIT or not _hours_equal(
        ledger_state.get("effort_budget_hours"),
        PRIOR_SEND_TO_ANALYST_LIMIT * PRIOR_PURCHASE_EFFORT_HOURS,
    ):
        raise ManagerScreenAllocationV3Error(
            "allocation v3 requires exactly 200 inherited purchases / 300 hours; "
            f"rebuilt {ledger_state.get('purchase_count')} purchases / "
            f"{ledger_state.get('effort_budget_hours')} hours"
        )


def _ledger_entry(
    *,
    symbol: str,
    effort_budget_hours: float,
    source_kind: str,
    source_path: str,
    source_sha256: str,
    source_id: str,
    decision_contract_version: int,
    purchased_at: str,
) -> dict[str, Any]:
    return {
        "symbol": _symbol(symbol),
        "purchase_kind": "inherited",
        "effort_budget_hours": float(effort_budget_hours),
        "source_kind": source_kind,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "source_id": source_id,
        "decision_contract_version": decision_contract_version,
        "purchased_at": _parse_datetime(purchased_at, "purchased_at").isoformat(),
    }


def _contract_summary(
    payload: Mapping[str, Any],
    *,
    contract_path: Path,
    contract_sha256: str,
    repository_root: Path,
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": payload["run_id"],
        "state": "frozen",
        "contract_path": _relative(contract_path, repository_root),
        "contract_sha256": contract_sha256,
        "historical_purchase_count": payload["capacity"]["historical_purchase_count"],
        "historical_effort_budget_hours": payload["capacity"]["historical_effort_budget_hours"],
        "irreversible_commitment_count": payload["capacity"]["irreversible_commitment_count"],
        "revocable_commitment_count": payload["capacity"]["revocable_commitment_count"],
        "post_scope_selection_capacity": payload["capacity"]["post_scope_selection_capacity"],
        "idempotent": idempotent,
        "portfolio_action": None,
    }


def _batch_dirs(run_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in run_dir.iterdir()
        if path.is_dir()
        and ((path / "batch.json").exists() or (path / "batch.json.seal.json").exists())
    )


def _artifact_presence(path: Path) -> str:
    artifact = path.exists()
    manifest = path.with_name(f"{path.name}.seal.json").exists()
    if artifact and manifest:
        return "complete"
    if artifact or manifest:
        return "partial"
    return "absent"


def _sealed_object(
    path: Path,
    *,
    artifact_type: str,
) -> tuple[dict[str, Any], Any]:
    if _artifact_presence(path) != "complete":
        raise ManagerScreenAllocationV3Error(
            f"sealed allocation input is missing or partial: {path}"
        )
    try:
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenAllocationV3Error(f"sealed allocation input is invalid: {path}") from exc
    if sealed.artifact_type != artifact_type or not isinstance(payload, dict):
        raise ManagerScreenAllocationV3Error(f"sealed allocation input has unexpected type: {path}")
    return payload, sealed


def _manager(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _MANAGER_KEYS:
        raise ManagerScreenAllocationV3Error("manager fields do not match contract")
    tools = value.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or any(not isinstance(item, str) or not item.strip() for item in tools)
    ):
        raise ManagerScreenAllocationV3Error("manager.tools must be non-empty strings")
    return {
        "agent": _text(value.get("agent"), "manager.agent"),
        "model": _text(value.get("model"), "manager.model"),
        "tools": [item.strip() for item in tools],
    }


def _repository_path(value: Any, repository_root: Path) -> Path:
    text = _text(str(value) if isinstance(value, Path) else value, "repository path")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = repository_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ManagerScreenAllocationV3Error(
            "allocation v3 reference escaped the repository"
        ) from exc
    return resolved


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreenAllocationV3Error("allocation v3 asset escaped the repository") from exc


def _relative_text(value: Any, field: str) -> str:
    text = _text(value, field)
    if Path(text).is_absolute() or ".." in Path(text).parts:
        raise ManagerScreenAllocationV3Error(f"{field} must be repository-relative")
    return Path(text).as_posix()


def _optional_relative_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _relative_text(value, field)


def _identifier(value: Any, field: str) -> str:
    result = _text(value, field)
    if not _ID_RE.fullmatch(result):
        raise ManagerScreenAllocationV3Error(f"{field} is invalid")
    return result


def _symbol(value: Any) -> str:
    result = _text(value, "symbol")
    if not _SYMBOL_RE.fullmatch(result):
        raise ManagerScreenAllocationV3Error(f"invalid CN-A symbol: {result}")
    return result


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ManagerScreenAllocationV3Error(f"{field} must be a lowercase SHA-256")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenAllocationV3Error(f"{field} must be non-empty text")
    return value.strip()


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _aware(value: dt.datetime | None, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreenAllocationV3Error(f"{field} must include a UTC offset")
    return value


def _parse_datetime(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ManagerScreenAllocationV3Error(f"{field} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManagerScreenAllocationV3Error(f"{field} must be an ISO timestamp") from exc
    return _aware(parsed, field)


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManagerScreenAllocationV3Error(f"{field} must be a non-negative integer")
    return value


def _positive_int(value: Any, field: str) -> int:
    result = _non_negative_int(value, field)
    if result <= 0:
        raise ManagerScreenAllocationV3Error(f"{field} must be positive")
    return result


def _positive_hours(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise ManagerScreenAllocationV3Error(f"{field} must be positive finite hours")
    return float(value)


def _non_negative_hours(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise ManagerScreenAllocationV3Error(f"{field} must be non-negative finite hours")
    return float(value)


def _hours_equal(left: Any, right: Any) -> bool:
    if (
        isinstance(left, bool)
        or isinstance(right, bool)
        or not isinstance(left, (int, float))
        or not isinstance(right, (int, float))
    ):
        return False
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)


def _payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
