from __future__ import annotations

import datetime as dt
import hashlib
import json
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
from .manager_screen_allocation_v3 import (
    CONTRACT_ARTIFACT_TYPE,
    CONTRACT_RELATIVE_PATH,
    ManagerScreenAllocationV3Error,
    verify_manager_screen_allocation_v3_contract,
)
from .manager_screen_terminal_governance import (
    ManagerScreenTerminalGovernanceError,
    manager_screen_terminal_governance_locked,
    require_manager_screen_terminal_governance_open,
)
from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed


class ManagerScreenAllocationV3SuspensionError(ValueError):
    """Raised when revocable v3 commitments cannot be suspended safely."""


def _terminal_governance_locked(*, base: Path, run_id: str) -> bool:
    try:
        return manager_screen_terminal_governance_locked(
            root=base,
            run_id=run_id,
        )
    except ManagerScreenTerminalGovernanceError as exc:
        raise ManagerScreenAllocationV3SuspensionError(str(exc)) from exc


SUSPENSION_ARTIFACT_TYPE = "manager_screen_allocation_v3_suspension"
SUSPENSION_RELATIVE_PATH = Path("governance") / "allocation-v3" / "suspension.json"
WORKFLOW = "manager_screen_allocation_v3_suspension"
WORKFLOW_VERSION = 1
CANDIDATE_STATE = "candidate_unfunded"

_SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MANAGER_KEYS = {"agent", "model", "tools"}
_PAYLOAD_KEYS = {
    "schema_version",
    "workflow",
    "workflow_version",
    "run_id",
    "suspended_at",
    "contract_path",
    "contract_sha256",
    "candidate_state",
    "manager",
    "reason",
    "members",
    "member_count",
    "members_sha256",
    "portfolio_action",
}
_MEMBER_KEYS = {
    "symbol",
    "manager_screen_route",
    "manager_screen_result_path",
    "manager_screen_result_sha256",
    "decisive_question",
    "evidence_ids",
    "prior_queue_row",
    "prior_queue_row_sha256",
    "prior_screening_row",
    "prior_screening_row_sha256",
}
_PURCHASE_FIELDS = {
    "allocation_sha256",
    "effort_budget_hours",
    "preceding_stage",
    "profile_cycle_id",
    "profile_evaluation_path",
    "profile_priority_score",
    "profile_quick_selection_path",
    "profile_recorded_at",
    "profile_scoped_selection_path",
    "selected_by",
    "stop_conditions",
}


@serialized_coverage_write
def suspend_manager_screen_allocation_v3_revocable_commitments(
    *,
    root: str | Path,
    run_id: str,
    manager: Mapping[str, Any],
    reason: str,
    suspended_at: dt.datetime,
) -> dict[str, Any]:
    """Seal and materialize suspension of every still-pristine revocable purchase.

    The sealed contract remains the authority for eligibility.  All eligible rows
    are preflighted before the suspension is sealed; after sealing, JSONL state is
    only a resumable projection and an identical replay repairs an interrupted
    queue/screening materialization.
    """

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    timestamp = _aware(suspended_at, "suspended_at")
    normalized_manager = _manager(manager)
    explanation = _text(reason, "reason")
    suspension_path = base / "manager-screen" / run / SUSPENSION_RELATIVE_PATH
    seal_path = suspension_path.with_name(f"{suspension_path.name}.seal.json")
    presence = (suspension_path.exists(), seal_path.exists())
    if presence[0] != presence[1]:
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 suspension is only partially sealed"
        )
    if presence == (False, False):
        try:
            require_manager_screen_terminal_governance_open(
                root=base,
                run_id=run,
                operation="new manager-screen allocation v3 suspension",
            )
        except ManagerScreenTerminalGovernanceError as exc:
            raise ManagerScreenAllocationV3SuspensionError(str(exc)) from exc

    contract, contract_path, contract_sha256 = _verified_contract(
        base=base,
        repository_root=repository_root,
        run_id=run,
    )
    if normalized_manager["agent"] != contract["manager"]["agent"]:
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension must be recorded by the contract manager"
        )
    if timestamp < _parse_datetime(contract["frozen_at"], "contract.frozen_at"):
        raise ManagerScreenAllocationV3SuspensionError(
            "suspended_at cannot predate the sealed allocation v3 contract"
        )

    if presence == (True, True):
        payload, suspension_sha256 = _verified_suspension(
            base=base,
            repository_root=repository_root,
            run_id=run,
            contract=contract,
            contract_path=contract_path,
            contract_sha256=contract_sha256,
        )
        if (
            payload["suspended_at"] != timestamp.isoformat()
            or payload["manager"] != normalized_manager
            or payload["reason"] != explanation
        ):
            raise ManagerScreenAllocationV3SuspensionError(
                "sealed allocation v3 suspension conflicts with request"
            )
        if _terminal_governance_locked(base=base, run_id=run):
            materialization = _projection_status(
                base=base,
                repository_root=repository_root,
                payload=payload,
                suspension_path=suspension_path,
                suspension_sha256=suspension_sha256,
            )
        else:
            materialization = _materialize(
                base=base,
                repository_root=repository_root,
                payload=payload,
                suspension_path=suspension_path,
                suspension_sha256=suspension_sha256,
            )
        return _summary(
            payload=payload,
            repository_root=repository_root,
            suspension_path=suspension_path,
            suspension_sha256=suspension_sha256,
            idempotent=True,
            materialization=materialization,
        )

    members = _preflight_new_suspension(
        base=base,
        contract=contract,
    )
    payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "workflow_version": WORKFLOW_VERSION,
        "run_id": run,
        "suspended_at": timestamp.isoformat(),
        "contract_path": _relative(contract_path, repository_root),
        "contract_sha256": contract_sha256,
        "candidate_state": CANDIDATE_STATE,
        "manager": normalized_manager,
        "reason": explanation,
        "members": members,
        "member_count": len(members),
        "members_sha256": _payload_sha256(members),
        "portfolio_action": None,
    }
    _validate_payload(payload)
    try:
        sealed = seal_json(
            suspension_path,
            payload,
            artifact_type=SUSPENSION_ARTIFACT_TYPE,
            sealed_at=timestamp,
        )
    except SealingError as exc:
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 suspension could not be sealed"
        ) from exc
    materialization = _materialize(
        base=base,
        repository_root=repository_root,
        payload=payload,
        suspension_path=suspension_path,
        suspension_sha256=sealed.sha256,
    )
    return _summary(
        payload=payload,
        repository_root=repository_root,
        suspension_path=suspension_path,
        suspension_sha256=sealed.sha256,
        idempotent=False,
        materialization=materialization,
    )


def verify_manager_screen_allocation_v3_suspension(
    *,
    root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Verify the suspension and report its crash-recoverable projection state."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    contract, contract_path, contract_sha256 = _verified_contract(
        base=base,
        repository_root=repository_root,
        run_id=run,
    )
    payload, suspension_sha256 = _verified_suspension(
        base=base,
        repository_root=repository_root,
        run_id=run,
        contract=contract,
        contract_path=contract_path,
        contract_sha256=contract_sha256,
    )
    suspension_path = base / "manager-screen" / run / SUSPENSION_RELATIVE_PATH
    projection = _projection_status(
        base=base,
        repository_root=repository_root,
        payload=payload,
        suspension_path=suspension_path,
        suspension_sha256=suspension_sha256,
    )
    return _summary(
        payload=payload,
        repository_root=repository_root,
        suspension_path=suspension_path,
        suspension_sha256=suspension_sha256,
        idempotent=True,
        materialization=projection,
    )


def _verified_contract(
    *,
    base: Path,
    repository_root: Path,
    run_id: str,
) -> tuple[dict[str, Any], Path, str]:
    try:
        contract = verify_manager_screen_allocation_v3_contract(
            root=base,
            run_id=run_id,
        )
    except ManagerScreenAllocationV3Error as exc:
        raise ManagerScreenAllocationV3SuspensionError(
            "sealed manager-screen allocation v3 contract is invalid"
        ) from exc
    contract_path = base / "manager-screen" / run_id / CONTRACT_RELATIVE_PATH
    try:
        sealed = verify_sealed(contract_path)
    except (OSError, SealingError) as exc:
        raise ManagerScreenAllocationV3SuspensionError(
            "sealed manager-screen allocation v3 contract is invalid"
        ) from exc
    if sealed.artifact_type != CONTRACT_ARTIFACT_TYPE:
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 contract artifact type is invalid"
        )
    if (
        contract_path.resolve()
        != (repository_root / _relative(contract_path, repository_root)).resolve()
    ):
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 contract escaped the repository"
        )
    return contract, contract_path, sealed.sha256


def _preflight_new_suspension(
    *,
    base: Path,
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    classifications = contract["commitment_classification"]
    revocable = {
        item["symbol"]: item for item in classifications if item["commitment_class"] == "revocable"
    }
    activation_states = {
        item["symbol"]: item for item in contract["activation_queue"]["purchased_states"]
    }
    queue = _unique_rows(base / RESEARCH_QUEUE_FILE, "research queue")
    screening = _unique_rows(base / SCREENING_FILE, "screening")
    members = []
    errors = []
    for symbol in sorted(revocable):
        classification = revocable[symbol]
        activation = activation_states.get(symbol)
        queue_row = queue.get(symbol)
        screen_row = screening.get(symbol)
        try:
            if activation is None:
                raise ManagerScreenAllocationV3SuspensionError(
                    "activation snapshot is missing the revocable commitment"
                )
            if queue_row is None:
                raise ManagerScreenAllocationV3SuspensionError(
                    "research queue is missing the revocable commitment"
                )
            queue_sha256 = _payload_sha256(queue_row)
            if queue_sha256 != classification["queue_record_sha256"]:
                raise ManagerScreenAllocationV3SuspensionError(
                    "live queue row drifted from the activation snapshot"
                )
            _require_still_revocable(
                queue_row,
                symbol=symbol,
                run_id=contract["run_id"],
                activation=activation,
            )
            if screen_row is None:
                raise ManagerScreenAllocationV3SuspensionError(
                    "screening is missing the revocable commitment"
                )
            _require_screen_binding(screen_row, queue_row=queue_row, symbol=symbol)
            member = {
                "symbol": symbol,
                "manager_screen_route": queue_row["manager_screen_route"],
                "manager_screen_result_path": queue_row["manager_screen_result_path"],
                "manager_screen_result_sha256": queue_row["manager_screen_result_sha256"],
                "decisive_question": queue_row["decisive_question"],
                "evidence_ids": list(queue_row["evidence_ids"]),
                "prior_queue_row": dict(queue_row),
                "prior_queue_row_sha256": queue_sha256,
                "prior_screening_row": dict(screen_row),
                "prior_screening_row_sha256": _payload_sha256(screen_row),
            }
            _validate_member(member)
            members.append(member)
        except ManagerScreenAllocationV3SuspensionError as exc:
            errors.append(f"{symbol}: {exc}")
    if errors:
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension preflight failed; no commitment was suspended: "
            + "; ".join(errors)
        )
    if {member["symbol"] for member in members} != set(revocable):
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension must include every revocable commitment"
        )
    return members


def _materialize(
    *,
    base: Path,
    repository_root: Path,
    payload: Mapping[str, Any],
    suspension_path: Path,
    suspension_sha256: str,
) -> dict[str, Any]:
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue = _unique_rows(queue_path, "research queue")
    screening = _unique_rows(screening_path, "screening")
    suspension_relative = _relative(suspension_path, repository_root)
    queue_updates: dict[str, dict[str, Any]] = {}
    screening_updates: dict[str, dict[str, Any]] = {}
    errors = []
    for member in payload["members"]:
        symbol = member["symbol"]
        expected_queue = _suspended_queue_row(
            member,
            payload=payload,
            suspension_path=suspension_relative,
            suspension_sha256=suspension_sha256,
        )
        expected_screen = _suspended_screening_row(
            member,
            payload=payload,
            suspension_path=suspension_relative,
            suspension_sha256=suspension_sha256,
        )
        current_queue = queue.get(symbol)
        current_screen = screening.get(symbol)
        try:
            queue_state = _projection_row_state(
                current_queue,
                prior_row=member["prior_queue_row"],
                prior_sha256=member["prior_queue_row_sha256"],
                expected_row=expected_queue,
                label="research queue",
                symbol=symbol,
            )
            screen_state = _projection_row_state(
                current_screen,
                prior_row=member["prior_screening_row"],
                prior_sha256=member["prior_screening_row_sha256"],
                expected_row=expected_screen,
                label="screening",
                symbol=symbol,
            )
            if queue_state == "prior":
                _require_still_revocable(
                    current_queue,
                    symbol=symbol,
                    run_id=payload["run_id"],
                    activation=None,
                )
                queue_updates[symbol] = expected_queue
            if screen_state == "prior":
                _require_screen_binding(
                    current_screen,
                    queue_row=member["prior_queue_row"],
                    symbol=symbol,
                )
                screening_updates[symbol] = expected_screen
        except ManagerScreenAllocationV3SuspensionError as exc:
            errors.append(f"{symbol}: {exc}")
    if errors:
        raise ManagerScreenAllocationV3SuspensionError(
            "sealed allocation v3 suspension materialization drifted; refusing all writes: "
            + "; ".join(errors)
        )

    if queue_updates:
        queue.update(queue_updates)
        write_jsonl(queue_path, list(queue.values()))
    if screening_updates:
        screening.update(screening_updates)
        write_jsonl(screening_path, list(screening.values()))
    return {
        "queue_materialized_count": len(payload["members"]),
        "screening_materialized_count": len(payload["members"]),
        "queue_repaired_count": len(queue_updates),
        "screening_repaired_count": len(screening_updates),
        "fully_materialized": True,
    }


def _projection_status(
    *,
    base: Path,
    repository_root: Path,
    payload: Mapping[str, Any],
    suspension_path: Path,
    suspension_sha256: str,
) -> dict[str, Any]:
    queue = _unique_rows(base / RESEARCH_QUEUE_FILE, "research queue")
    screening = _unique_rows(base / SCREENING_FILE, "screening")
    relative = _relative(suspension_path, repository_root)
    queue_count = 0
    screen_count = 0
    drift = []
    for member in payload["members"]:
        symbol = member["symbol"]
        expected_queue = _suspended_queue_row(
            member,
            payload=payload,
            suspension_path=relative,
            suspension_sha256=suspension_sha256,
        )
        expected_screen = _suspended_screening_row(
            member,
            payload=payload,
            suspension_path=relative,
            suspension_sha256=suspension_sha256,
        )
        if queue.get(symbol) == expected_queue:
            queue_count += 1
        else:
            drift.append({"symbol": symbol, "projection": "research_queue"})
        if screening.get(symbol) == expected_screen:
            screen_count += 1
        else:
            drift.append({"symbol": symbol, "projection": "screening"})
    return {
        "queue_materialized_count": queue_count,
        "screening_materialized_count": screen_count,
        "queue_repaired_count": 0,
        "screening_repaired_count": 0,
        "fully_materialized": not drift,
        "drift": drift,
    }


def _suspended_queue_row(
    member: Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
    suspension_path: str,
    suspension_sha256: str,
) -> dict[str, Any]:
    updated = dict(member["prior_queue_row"])
    history = list(updated.get("stage_history") or [])
    history.append(
        {
            "stage": WORKFLOW,
            "status": "completed",
            "action": "suspend_unclaimed_purchase",
            "finished_at": payload["suspended_at"],
            "run_id": payload["run_id"],
            "contract_path": payload["contract_path"],
            "contract_sha256": payload["contract_sha256"],
            "suspension_path": suspension_path,
            "suspension_sha256": suspension_sha256,
        }
    )
    updated.update(
        {
            "task_type": "manager_screen",
            "status": "completed",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": payload["suspended_at"],
            "failure_reason": None,
            "result_path": member["manager_screen_result_path"],
            "next_action": (
                "保留为未获资助候选；完整 scope 封存并由投资经理统一比较前，"
                "不得认领或购买单公司研究预算。"
            ),
            "research_budget_state": CANDIDATE_STATE,
            "research_budget_suspension_path": suspension_path,
            "research_budget_suspension_sha256": suspension_sha256,
            "stage_history": history,
        }
    )
    for field in _PURCHASE_FIELDS:
        updated.pop(field, None)
    return updated


def _suspended_screening_row(
    member: Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
    suspension_path: str,
    suspension_sha256: str,
) -> dict[str, Any]:
    updated = dict(member["prior_screening_row"])
    updated.update(
        {
            "decision": CANDIDATE_STATE,
            "state": CANDIDATE_STATE,
            "research_budget_state": CANDIDATE_STATE,
            "research_budget_suspension_path": suspension_path,
            "research_budget_suspension_sha256": suspension_sha256,
            "next_action": ("保留原研究理由与证据，待完整 scope 封存后统一比较是否获得研究预算。"),
        }
    )
    return updated


def _projection_row_state(
    current: Mapping[str, Any] | None,
    *,
    prior_row: Mapping[str, Any],
    prior_sha256: str,
    expected_row: Mapping[str, Any],
    label: str,
    symbol: str,
) -> str:
    if current is None:
        raise ManagerScreenAllocationV3SuspensionError(f"{label} row is missing: {symbol}")
    current_sha256 = _payload_sha256(current)
    if current_sha256 == prior_sha256 and dict(current) == dict(prior_row):
        return "prior"
    if dict(current) == dict(expected_row):
        return "materialized"
    raise ManagerScreenAllocationV3SuspensionError(
        f"{label} row matches neither sealed prior nor suspension projection"
    )


def _require_still_revocable(
    row: Mapping[str, Any],
    *,
    symbol: str,
    run_id: str,
    activation: Mapping[str, Any] | None,
) -> None:
    history = row.get("stage_history")
    attempts = row.get("attempt_history")
    if history is None:
        history = []
    if attempts is None:
        attempts = []
    result_path = row.get("manager_screen_result_path")
    result_sha256 = row.get("manager_screen_result_sha256")
    decisive_question = row.get("decisive_question")
    evidence_ids = row.get("evidence_ids")
    if (
        row.get("symbol") != symbol
        or row.get("manager_screen_run_id") != run_id
        or row.get("manager_screen_route") != "send_to_analyst"
        or row.get("task_type") != "quick_profile"
        or row.get("status") != "pending"
        or row.get("assigned_agent") is not None
        or row.get("started_at") is not None
        or row.get("finished_at") is not None
        or row.get("failure_reason") is not None
        or row.get("result_path") is not None
        or row.get("preceding_stage") != "manager_screen"
        or not isinstance(attempts, list)
        or attempts
        or not isinstance(history, list)
        or not isinstance(result_path, str)
        or not result_path.strip()
        or not isinstance(result_sha256, str)
        or not _SHA256_RE.fullmatch(result_sha256)
        or not isinstance(decisive_question, str)
        or not decisive_question.strip()
        or not isinstance(evidence_ids, list)
        or not evidence_ids
        or any(not isinstance(item, str) or not item.strip() for item in evidence_ids)
    ):
        raise ManagerScreenAllocationV3SuspensionError(
            "commitment is no longer pending, never claimed, and never attempted"
        )
    # The sealed contract already classifies formal progress relative to each
    # purchase timestamp.  Legacy research completed before the current run's
    # purchase is therefore compatible with revocation and must not be treated
    # as work performed against this commitment.  Exact activation-row binding
    # below prevents any post-contract history from being ignored.
    if activation is not None:
        for field in (
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
        ):
            if row.get(field) != activation.get(field):
                raise ManagerScreenAllocationV3SuspensionError(
                    f"live queue field drifted from activation snapshot: {field}"
                )
        if attempts != activation.get("attempt_history"):
            raise ManagerScreenAllocationV3SuspensionError(
                "live queue attempt_history drifted from activation snapshot"
            )
        if history != activation.get("stage_history"):
            raise ManagerScreenAllocationV3SuspensionError(
                "live queue stage_history drifted from activation snapshot"
            )


def _require_screen_binding(
    screen: Mapping[str, Any],
    *,
    queue_row: Mapping[str, Any],
    symbol: str,
) -> None:
    evidence_ids = queue_row.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise ManagerScreenAllocationV3SuspensionError(
            "queue manager-screen evidence binding is invalid"
        )
    if (
        screen.get("symbol") != symbol
        or screen.get("manager_screen_run_id") != queue_row.get("manager_screen_run_id")
        or screen.get("manager_screen_route") != queue_row.get("manager_screen_route")
        or screen.get("manager_screen_result_path") != queue_row.get("manager_screen_result_path")
        or screen.get("manager_screen_result_sha256")
        != queue_row.get("manager_screen_result_sha256")
        or screen.get("decisive_question") != queue_row.get("decisive_question")
        or screen.get("evidence") != evidence_ids
    ):
        raise ManagerScreenAllocationV3SuspensionError(
            "screening manager result/route/question/evidence binding drifted"
        )


def _verified_suspension(
    *,
    base: Path,
    repository_root: Path,
    run_id: str,
    contract: Mapping[str, Any],
    contract_path: Path,
    contract_sha256: str,
) -> tuple[dict[str, Any], str]:
    suspension_path = base / "manager-screen" / run_id / SUSPENSION_RELATIVE_PATH
    try:
        sealed = verify_sealed(suspension_path)
        payload = json.loads(suspension_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenAllocationV3SuspensionError(
            "sealed manager-screen allocation v3 suspension is invalid"
        ) from exc
    if sealed.artifact_type != SUSPENSION_ARTIFACT_TYPE:
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 suspension artifact type is invalid"
        )
    _validate_payload(payload)
    if payload["run_id"] != run_id:
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 suspension run_id does not match its path"
        )
    if (
        payload["contract_path"] != _relative(contract_path, repository_root)
        or payload["contract_sha256"] != contract_sha256
    ):
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 suspension contract binding is invalid"
        )
    suspended_at = _parse_datetime(payload["suspended_at"], "suspended_at")
    if sealed.sealed_at != suspended_at:
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 suspension seal time does not match"
        )
    if suspended_at < _parse_datetime(contract["frozen_at"], "contract.frozen_at"):
        raise ManagerScreenAllocationV3SuspensionError(
            "manager-screen allocation v3 suspension predates the contract"
        )
    revocable = {
        item["symbol"]: item
        for item in contract["commitment_classification"]
        if item["commitment_class"] == "revocable"
    }
    members = {member["symbol"]: member for member in payload["members"]}
    if set(members) != set(revocable):
        raise ManagerScreenAllocationV3SuspensionError(
            "sealed suspension does not cover every revocable commitment exactly once"
        )
    for symbol, member in members.items():
        if member["prior_queue_row_sha256"] != revocable[symbol]["queue_record_sha256"]:
            raise ManagerScreenAllocationV3SuspensionError(
                f"sealed suspension prior queue hash is not contract-bound: {symbol}"
            )
    return payload, sealed.sha256


def _validate_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != _PAYLOAD_KEYS:
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension fields do not match the contract"
        )
    if (
        value.get("schema_version") != 1
        or value.get("workflow") != WORKFLOW
        or value.get("workflow_version") != WORKFLOW_VERSION
        or value.get("candidate_state") != CANDIDATE_STATE
        or value.get("portfolio_action") is not None
    ):
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension protocol constants are invalid"
        )
    _identifier(value.get("run_id"), "run_id")
    _parse_datetime(value.get("suspended_at"), "suspended_at")
    _text(value.get("contract_path"), "contract_path")
    _sha256(value.get("contract_sha256"), "contract_sha256")
    _manager(value.get("manager"))
    _text(value.get("reason"), "reason")
    members = value.get("members")
    if not isinstance(members, list):
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension members must be an array"
        )
    normalized = []
    for member in members:
        _validate_member(member)
        normalized.append(dict(member))
    symbols = [member["symbol"] for member in normalized]
    if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension members must be uniquely symbol-sorted"
        )
    if value.get("member_count") != len(normalized):
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension member_count does not match"
        )
    if value.get("members_sha256") != _payload_sha256(normalized):
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension members_sha256 does not match"
        )


def _validate_member(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != _MEMBER_KEYS:
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension member fields do not match the contract"
        )
    symbol = _symbol(value.get("symbol"))
    if value.get("manager_screen_route") != "send_to_analyst":
        raise ManagerScreenAllocationV3SuspensionError(
            f"suspension member is not an inherited analyst purchase: {symbol}"
        )
    _text(value.get("manager_screen_result_path"), "manager_screen_result_path")
    _sha256(value.get("manager_screen_result_sha256"), "manager_screen_result_sha256")
    _text(value.get("decisive_question"), "decisive_question")
    evidence = value.get("evidence_ids")
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(item, str) or not item.strip() for item in evidence)
    ):
        raise ManagerScreenAllocationV3SuspensionError(
            f"suspension member evidence_ids are invalid: {symbol}"
        )
    queue_row = value.get("prior_queue_row")
    screen_row = value.get("prior_screening_row")
    if not isinstance(queue_row, Mapping) or not isinstance(screen_row, Mapping):
        raise ManagerScreenAllocationV3SuspensionError(
            f"suspension member prior rows must be objects: {symbol}"
        )
    if queue_row.get("symbol") != symbol or screen_row.get("symbol") != symbol:
        raise ManagerScreenAllocationV3SuspensionError(
            f"suspension member prior row symbol mismatch: {symbol}"
        )
    if value.get("prior_queue_row_sha256") != _payload_sha256(queue_row):
        raise ManagerScreenAllocationV3SuspensionError(
            f"suspension member prior queue hash does not match: {symbol}"
        )
    if value.get("prior_screening_row_sha256") != _payload_sha256(screen_row):
        raise ManagerScreenAllocationV3SuspensionError(
            f"suspension member prior screening hash does not match: {symbol}"
        )
    for field in (
        "manager_screen_route",
        "manager_screen_result_path",
        "manager_screen_result_sha256",
        "decisive_question",
    ):
        if queue_row.get(field) != value.get(field):
            raise ManagerScreenAllocationV3SuspensionError(
                f"suspension member prior queue binding mismatch: {symbol}.{field}"
            )
    if queue_row.get("evidence_ids") != evidence:
        raise ManagerScreenAllocationV3SuspensionError(
            f"suspension member prior queue evidence mismatch: {symbol}"
        )
    _require_screen_binding(screen_row, queue_row=queue_row, symbol=symbol)


def _unique_rows(path: Path, label: str) -> dict[str, dict[str, Any]]:
    try:
        rows = read_jsonl(path)
    except (OSError, ValueError) as exc:
        raise ManagerScreenAllocationV3SuspensionError(f"{label} is invalid") from exc
    result = {}
    for row in rows:
        symbol = _symbol(row.get("symbol"))
        if symbol in result:
            raise ManagerScreenAllocationV3SuspensionError(
                f"{label} contains a duplicate symbol: {symbol}"
            )
        result[symbol] = dict(row)
    return result


def _summary(
    *,
    payload: Mapping[str, Any],
    repository_root: Path,
    suspension_path: Path,
    suspension_sha256: str,
    idempotent: bool,
    materialization: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": payload["run_id"],
        "suspension_path": _relative(suspension_path, repository_root),
        "suspension_sha256": suspension_sha256,
        "suspended_at": payload["suspended_at"],
        "suspended_commitment_count": payload["member_count"],
        "candidate_state": payload["candidate_state"],
        "idempotent": idempotent,
        "materialization": dict(materialization),
        "portfolio_action": None,
    }


def _manager(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _MANAGER_KEYS:
        raise ManagerScreenAllocationV3SuspensionError(
            "manager fields do not match the suspension contract"
        )
    tools = value.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or any(not isinstance(item, str) or not item.strip() for item in tools)
    ):
        raise ManagerScreenAllocationV3SuspensionError("manager.tools must be non-empty strings")
    normalized_tools = [item.strip() for item in tools]
    if len(normalized_tools) != len(set(normalized_tools)):
        raise ManagerScreenAllocationV3SuspensionError("manager.tools must be unique")
    return {
        "agent": _text(value.get("agent"), "manager.agent"),
        "model": _text(value.get("model"), "manager.model"),
        "tools": normalized_tools,
    }


def _relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreenAllocationV3SuspensionError(
            f"path is outside the repository: {path}"
        ) from exc


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", text):
        raise ManagerScreenAllocationV3SuspensionError(f"{field} is invalid")
    return text


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not _SYMBOL_RE.fullmatch(value):
        raise ManagerScreenAllocationV3SuspensionError(f"invalid CN symbol: {value}")
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ManagerScreenAllocationV3SuspensionError(f"{field} must be sha256")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenAllocationV3SuspensionError(f"{field} must be non-empty text")
    return value.strip()


def _aware(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreenAllocationV3SuspensionError(f"{field} must be timezone-aware")
    return value


def _parse_datetime(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ManagerScreenAllocationV3SuspensionError(f"{field} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManagerScreenAllocationV3SuspensionError(f"{field} must be an ISO datetime") from exc
    return _aware(parsed, field)


def _payload_sha256(value: Any) -> str:
    try:
        return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    except SealingError as exc:
        raise ManagerScreenAllocationV3SuspensionError(
            "allocation v3 suspension row is not canonical JSON"
        ) from exc
