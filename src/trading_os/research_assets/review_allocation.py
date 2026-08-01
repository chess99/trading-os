from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    read_jsonl,
    serialized_coverage_write,
)
from .deep_research_completion import (
    DeepResearchCompletionError,
    deep_research_completion_status,
)
from .sealing import (
    SealingError,
    canonical_json_bytes,
    seal_json,
    verify_sealed,
)


class ReviewAllocationError(ValueError):
    """Raised when manager-run review budget cannot be safely purchased."""


APPROVAL_ARTIFACT_TYPE = "manager_run_underwriting_approval"
APPROVAL_SCHEMA_VERSION = 1
APPROVAL_DIR = "review-allocations"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_CANDIDATE_INPUT_KEYS = {
    "symbol",
    "deep_selection_path",
    "deep_selection_sha256",
    "deep_completion_path",
    "deep_completion_sha256",
}
_APPROVAL_KEYS = {
    "schema_version",
    "approval_id",
    "manager_screen_run_id",
    "stage",
    "approved_by",
    "approved_at",
    "reason",
    "policy_binding",
    "capacity",
    "candidates",
}
_POLICY_BINDING_KEYS = {"path", "sha256", "policy_id", "version"}
_RUN_POLICY_REF_KEYS = {
    "policy_id",
    "version",
    "path",
    "file_sha256",
    "payload_sha256",
}
_RUN_POLICY_CONTRACT_ARTIFACT_TYPE = "manager_screen_research_policy_contract"
_RUN_POLICY_SNAPSHOT_ARTIFACT_TYPE = "manager_screen_research_policy_snapshot"
_RUN_POLICY_CANONICAL_PATH = "policies/research-allocation.json"
_CAPACITY_KEYS = {
    "limit",
    "committed_before",
    "approved_count",
    "committed_after",
    "effort_budget_hours_per_company",
}
_CANDIDATE_KEYS = {
    "symbol",
    "company_dir",
    "deep_selection",
    "deep_completion",
    "research_claims",
}
_PATH_BINDING_KEYS = {"path", "sha256"}
_CLAIMS_BINDING_KEYS = {"path", "sha256", "report_id", "source_ids"}
_EFFECTIVE_MANAGER_AUTHORITY_KEYS = {
    "agent",
    "source_path",
    "source_sha256",
    "source_type",
}
_EFFECTIVE_MANAGER_AUTHORITY_SOURCE_TYPES = {
    "manager_screen_result",
    "manager_screen_quote_impact_result",
    "manager_screen_legacy_transition_result",
    "manager_screen_full_market_allocation_v3_result",
}

_DOWNSTREAM_REQUEST_CONTRACTS = {
    "challenger": {
        "artifact_type": "manager_run_challenger_budget_request",
        "underwriting_approval_grants_budget": False,
        "required_fields": [
            "manager_screen_run_id",
            "underwriting_approval_path",
            "underwriting_approval_sha256",
            "trigger_artifact_path",
            "trigger_artifact_sha256",
            "requested_symbols",
            "requested_by",
            "requested_at",
            "reason",
        ],
    },
    "portfolio": {
        "artifact_type": "manager_run_portfolio_budget_request",
        "underwriting_approval_grants_budget": False,
        "required_fields": [
            "manager_screen_run_id",
            "underwriting_approval_paths",
            "underwriting_approval_sha256s",
            "completed_review_run_ids",
            "candidate_set_sha256",
            "requested_by",
            "requested_at",
            "reason",
        ],
    },
}
_BUDGET_STAGES = {"challenger", "portfolio_synthesis"}
_BUDGET_REQUEST_ARTIFACT_TYPES = {
    "challenger": "manager_run_challenger_request",
    "portfolio_synthesis": "manager_run_portfolio_synthesis_request",
}
_BUDGET_APPROVAL_ARTIFACT_TYPES = {
    "challenger": "manager_run_challenger_approval",
    "portfolio_synthesis": "manager_run_portfolio_synthesis_approval",
}
_BUDGET_REQUEST_KEYS = {
    "schema_version",
    "request_id",
    "manager_screen_run_id",
    "review_run_id",
    "budget_stage",
    "trigger",
    "requested_by",
    "requested_at",
    "underwriting_approval",
    "items",
}
_BUDGET_REQUEST_ITEM_KEYS = {"symbol", "evaluation", "candidate"}
_BUDGET_APPROVAL_KEYS = {
    "schema_version",
    "approval_id",
    "manager_screen_run_id",
    "review_run_id",
    "budget_stage",
    "approved_by",
    "approved_at",
    "reason",
    "executor",
    "request",
    "underwriting_approval",
    "policy_binding",
    "capacity",
    "items",
}


@serialized_coverage_write
def freeze_underwriting_approval(
    *,
    root: str | Path,
    repository_root: str | Path,
    approval_id: str,
    manager_screen_run_id: str,
    policy_path: str,
    policy_sha256: str,
    approved_by: str,
    reason: str,
    approved_at: dt.datetime,
    candidates: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Freeze one explicit manager approval for underwriting budget.

    ``root`` is the CN-A coverage root. The coverage write lock serializes the
    ledger scan and seal so two approvals cannot independently consume the same
    remaining run capacity.
    """

    _require_aware(approved_at, "approved_at")
    approval = _identifier(approval_id, "approval_id")
    manager_run = _identifier(manager_screen_run_id, "manager_screen_run_id")
    manager = _text(approved_by, "approved_by")
    approval_reason = _text(reason, "reason")
    base = Path(root).resolve()
    repository = Path(repository_root).resolve()
    _require_within(base, repository, "coverage root")

    policy_binding, capacity, effort_budget = _ensure_run_policy_contract(
        base=base,
        repository=repository,
        run_id=manager_run,
        policy_path=policy_path,
        expected_sha256=policy_sha256,
        bound_at=approved_at,
    )
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    normalized_candidates = _validate_candidates(
        candidates,
        queue=queue,
        coverage_root=base,
        repository=repository,
        manager_screen_run_id=manager_run,
        approved_by=manager,
        approved_at=approved_at,
    )

    approval_dir = base / APPROVAL_DIR / manager_run
    target = approval_dir / f"{approval}.json"
    existing = _load_approval_ledger(approval_dir)
    target_existing = existing.pop(approval, None)
    ledger_symbols = _validate_ledger(existing, manager_screen_run_id=manager_run)
    if target_existing is None:
        _validate_complete_ledger(
            existing,
            manager_screen_run_id=manager_run,
            capacity=capacity,
            policy_binding=policy_binding,
        )
    requested_symbols = {item["symbol"] for item in normalized_candidates}
    duplicate = sorted(requested_symbols & ledger_symbols)
    if duplicate:
        raise ReviewAllocationError(
            f"underwriting budget is already approved in this manager run: {duplicate}"
        )

    core = {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "approval_id": approval,
        "manager_screen_run_id": manager_run,
        "stage": "underwriting",
        "approved_by": manager,
        "approved_at": approved_at.isoformat(),
        "reason": approval_reason,
        "policy_binding": policy_binding,
        "candidates": normalized_candidates,
    }
    if target_existing is not None:
        _validate_approval_payload(target_existing)
        expected_core = {key: target_existing[key] for key in _APPROVAL_KEYS if key != "capacity"}
        if expected_core != core:
            raise ReviewAllocationError(
                f"sealed underwriting approval conflicts with replay: {approval}"
            )
        _validate_complete_ledger(
            {**existing, approval: target_existing},
            manager_screen_run_id=manager_run,
            capacity=capacity,
            policy_binding=policy_binding,
        )
        sealed = verify_sealed(target)
        return _approval_result(
            target_existing,
            approval_path=_relative(target, repository),
            approval_sha256=sealed.sha256,
            idempotent=True,
        )

    if existing:
        latest_approval = max(
            _parse_datetime(item["approved_at"], "approval.approved_at")
            for item in existing.values()
        )
        if approved_at <= latest_approval:
            raise ReviewAllocationError(
                "new underwriting approval must be later than existing run approvals"
            )
    committed_before = len(ledger_symbols)
    committed_after = committed_before + len(normalized_candidates)
    if committed_after > capacity:
        raise ReviewAllocationError(
            "underwriting run capacity exceeded: "
            f"{committed_before} committed + {len(normalized_candidates)} requested "
            f"> {capacity}"
        )
    payload = {
        **core,
        "capacity": {
            "limit": capacity,
            "committed_before": committed_before,
            "approved_count": len(normalized_candidates),
            "committed_after": committed_after,
            "effort_budget_hours_per_company": effort_budget,
        },
    }
    sealed = seal_json(
        target,
        payload,
        artifact_type=APPROVAL_ARTIFACT_TYPE,
        sealed_at=approved_at,
    )
    return _approval_result(
        payload,
        approval_path=_relative(target, repository),
        approval_sha256=sealed.sha256,
        idempotent=False,
    )


def downstream_review_request_contracts() -> dict[str, Any]:
    """Return contracts deliberately not authorized by underwriting approval."""

    return {
        "contracts": copy.deepcopy(_DOWNSTREAM_REQUEST_CONTRACTS),
        "uncovered_items": [
            "challenger manager approval and manager-run capacity enforcement",
            "portfolio synthesis manager approval and manager-run capacity enforcement",
            "review_workflow consumption of frozen underwriting approvals",
        ],
    }


def verify_underwriting_approval(
    *,
    root: str | Path,
    repository_root: str | Path,
    approval_path: str,
    approval_sha256: str,
) -> dict[str, Any]:
    """Revalidate a frozen approval, its ledger, and every bound deep artifact."""

    base = Path(root).resolve()
    repository = Path(repository_root).resolve()
    _require_within(base, repository, "coverage root")
    path = _resolve_path(repository, approval_path, "underwriting approval")
    expected_sha256 = _sha256(approval_sha256, "approval_sha256")
    try:
        sealed = verify_sealed(path)
    except (SealingError, ValueError) as exc:
        raise ReviewAllocationError("underwriting approval is not validly sealed") from exc
    if sealed.artifact_type != APPROVAL_ARTIFACT_TYPE or sealed.sha256 != expected_sha256:
        raise ReviewAllocationError("underwriting approval seal binding is invalid")
    payload = _read_json(path, "underwriting approval")
    _validate_approval_payload(payload)
    manager_run = str(payload["manager_screen_run_id"])
    approval_id = str(payload["approval_id"])
    expected_path = base / APPROVAL_DIR / manager_run / f"{approval_id}.json"
    if path != expected_path.resolve():
        raise ReviewAllocationError(
            "underwriting approval path does not match its manager-run identity"
        )

    policy_binding, capacity, effort_budget = _load_run_policy_contract(
        base=base,
        repository=repository,
        run_id=manager_run,
        expected_binding=payload["policy_binding"],
    )
    if policy_binding != payload["policy_binding"]:
        raise ReviewAllocationError("underwriting approval policy binding drifted")
    if payload["capacity"]["effort_budget_hours_per_company"] != effort_budget:
        raise ReviewAllocationError("underwriting approval effort budget drifted")

    candidate_inputs = [
        {
            "symbol": item["symbol"],
            "deep_selection_path": item["deep_selection"]["path"],
            "deep_selection_sha256": item["deep_selection"]["sha256"],
            "deep_completion_path": item["deep_completion"]["path"],
            "deep_completion_sha256": item["deep_completion"]["sha256"],
        }
        for item in payload["candidates"]
    ]
    normalized_candidates = _validate_candidates(
        candidate_inputs,
        queue=read_jsonl(base / RESEARCH_QUEUE_FILE),
        coverage_root=base,
        repository=repository,
        manager_screen_run_id=manager_run,
        approved_by=str(payload["approved_by"]),
        approved_at=_parse_datetime(payload["approved_at"], "approved_at"),
    )
    if normalized_candidates != payload["candidates"]:
        raise ReviewAllocationError("underwriting approval candidate bindings drifted")

    ledger = _load_approval_ledger(base / APPROVAL_DIR / manager_run)
    if approval_id not in ledger:
        raise ReviewAllocationError("underwriting approval is absent from its run ledger")
    _validate_complete_ledger(
        ledger,
        manager_screen_run_id=manager_run,
        capacity=capacity,
        policy_binding=policy_binding,
    )
    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "approval_path": _relative(path, repository),
        "approval_sha256": sealed.sha256,
        "approval": copy.deepcopy(payload),
        **downstream_review_request_contracts(),
    }


@serialized_coverage_write
def freeze_challenger_approval(
    *,
    root: str | Path,
    repository_root: str | Path,
    approval_id: str,
    request_path: str,
    request_sha256: str,
    approved_by: str,
    executor: str,
    reason: str,
    approved_at: dt.datetime,
) -> dict[str, Any]:
    return _freeze_review_budget_approval(
        root=root,
        repository_root=repository_root,
        approval_id=approval_id,
        budget_stage="challenger",
        request_path=request_path,
        request_sha256=request_sha256,
        approved_by=approved_by,
        executor=executor,
        reason=reason,
        approved_at=approved_at,
    )


@serialized_coverage_write
def freeze_portfolio_synthesis_approval(
    *,
    root: str | Path,
    repository_root: str | Path,
    approval_id: str,
    request_path: str,
    request_sha256: str,
    approved_by: str,
    executor: str,
    reason: str,
    approved_at: dt.datetime,
) -> dict[str, Any]:
    return _freeze_review_budget_approval(
        root=root,
        repository_root=repository_root,
        approval_id=approval_id,
        budget_stage="portfolio_synthesis",
        request_path=request_path,
        request_sha256=request_sha256,
        approved_by=approved_by,
        executor=executor,
        reason=reason,
        approved_at=approved_at,
    )


def verify_review_budget_approval(
    *,
    root: str | Path,
    repository_root: str | Path,
    budget_stage: str,
    request_path: str,
    request_sha256: str,
    executor: str,
) -> dict[str, Any]:
    stage = _budget_stage(budget_stage)
    repository = Path(repository_root).resolve()
    base = Path(root).resolve()
    request, request_binding, underwriting = _verify_budget_request(
        root=base,
        repository=repository,
        budget_stage=stage,
        request_path=request_path,
        request_sha256=request_sha256,
    )
    approval_dir = base / APPROVAL_DIR / str(request["manager_screen_run_id"]) / stage
    matches: list[tuple[dict[str, Any], Any, Path]] = []
    for path in sorted(approval_dir.glob("*.json")) if approval_dir.exists() else []:
        if path.name.endswith(".seal.json"):
            continue
        sealed = verify_sealed(path)
        if sealed.artifact_type != _BUDGET_APPROVAL_ARTIFACT_TYPES[stage]:
            raise ReviewAllocationError("review budget approval artifact type is invalid")
        payload = _read_json(path, "review budget approval")
        _validate_budget_approval_payload(payload, budget_stage=stage)
        if payload["request"] == request_binding:
            matches.append((payload, sealed, path))
    if len(matches) != 1:
        raise ReviewAllocationError(f"explicit manager {stage} approval is required")
    payload, sealed, path = matches[0]
    _validate_budget_approval_binding(
        payload,
        sealed=sealed,
        path=path,
        request=request,
        request_binding=request_binding,
        underwriting=underwriting,
        budget_stage=stage,
        base=base,
        repository=repository,
    )
    if payload["executor"] != _text(executor, "executor"):
        raise ReviewAllocationError(f"{stage} approval executor does not match")
    if payload["underwriting_approval"] != {
        "path": underwriting["approval_path"],
        "sha256": underwriting["approval_sha256"],
    }:
        raise ReviewAllocationError("review budget underwriting binding drifted")
    return {
        "approval": payload,
        "approval_path": _relative(path, repository),
        "approval_sha256": sealed.sha256,
    }


def _freeze_review_budget_approval(
    *,
    root: str | Path,
    repository_root: str | Path,
    approval_id: str,
    budget_stage: str,
    request_path: str,
    request_sha256: str,
    approved_by: str,
    executor: str,
    reason: str,
    approved_at: dt.datetime,
) -> dict[str, Any]:
    _require_aware(approved_at, "approved_at")
    stage = _budget_stage(budget_stage)
    approval = _identifier(approval_id, "approval_id")
    manager = _text(approved_by, "approved_by")
    executor_name = _text(executor, "executor")
    if manager == executor_name:
        raise ReviewAllocationError(f"{stage} approver and executor must be independent")
    repository = Path(repository_root).resolve()
    base = Path(root).resolve()
    request, request_binding, underwriting = _verify_budget_request(
        root=base,
        repository=repository,
        budget_stage=stage,
        request_path=request_path,
        request_sha256=request_sha256,
    )
    underwriting_payload = underwriting["approval"]
    if manager != underwriting_payload["approved_by"]:
        raise ReviewAllocationError(f"{stage} approval must come from the bound investment manager")
    if manager == request["requested_by"]:
        raise ReviewAllocationError(f"{stage} approver must be independent of the requester")
    requested_at = _parse_datetime(request["requested_at"], "request.requested_at")
    if approved_at <= requested_at:
        raise ReviewAllocationError(f"{stage} approval must postdate its request")

    policy_binding = underwriting_payload["policy_binding"]
    _, underwriting_capacity, _ = _load_run_policy_contract(
        base=base,
        repository=repository,
        run_id=str(request["manager_screen_run_id"]),
        expected_binding=policy_binding,
    )
    capacity = underwriting_capacity if stage == "challenger" else 1
    capacity_source = (
        "stage_capacity_per_run.underwriting"
        if stage == "challenger"
        else "single_portfolio_synthesis_per_manager_run"
    )
    manager_run = str(request["manager_screen_run_id"])
    approval_dir = base / APPROVAL_DIR / manager_run / stage
    target = approval_dir / f"{approval}.json"
    existing_count = 0
    existing_symbols: set[str] = set()
    existing_requests: set[str] = set()
    existing_payloads: dict[str, dict[str, Any]] = {}
    if approval_dir.exists():
        for path in sorted(approval_dir.glob("*.json")):
            if path.name.endswith(".seal.json"):
                continue
            sealed = verify_sealed(path)
            if sealed.artifact_type != _BUDGET_APPROVAL_ARTIFACT_TYPES[stage]:
                raise ReviewAllocationError("review budget approval artifact type is invalid")
            payload = _read_json(path, "review budget approval")
            _validate_budget_approval_payload(payload, budget_stage=stage)
            existing_payloads[str(payload["approval_id"])] = payload
            existing_requests.add(str(payload["request"]["sha256"]))
            symbols = {str(item["symbol"]) for item in payload["items"]}
            if stage == "challenger":
                duplicate = existing_symbols & symbols
                if duplicate:
                    raise ReviewAllocationError(
                        f"challenger approval ledger has duplicate symbols: {sorted(duplicate)}"
                    )
                existing_symbols.update(symbols)
                existing_count += len(symbols)
            else:
                existing_count += 1

    core = {
        "schema_version": 1,
        "approval_id": approval,
        "manager_screen_run_id": manager_run,
        "review_run_id": request["review_run_id"],
        "budget_stage": stage,
        "approved_by": manager,
        "approved_at": approved_at.isoformat(),
        "reason": _text(reason, "reason"),
        "executor": executor_name,
        "request": request_binding,
        "underwriting_approval": {
            "path": underwriting["approval_path"],
            "sha256": underwriting["approval_sha256"],
        },
        "policy_binding": dict(policy_binding),
        "items": copy.deepcopy(request["items"]),
    }
    target_existing = existing_payloads.get(approval)
    if target_existing is not None:
        expected_core = {
            key: target_existing[key] for key in _BUDGET_APPROVAL_KEYS if key != "capacity"
        }
        if expected_core != core:
            raise ReviewAllocationError(f"sealed {stage} approval conflicts with replay")
        sealed = verify_sealed(target)
        return _budget_approval_result(
            target_existing,
            path=_relative(target, repository),
            sha256=sealed.sha256,
            idempotent=True,
        )
    if request_binding["sha256"] in existing_requests:
        raise ReviewAllocationError(f"{stage} request is already approved")
    requested_symbols = {str(item["symbol"]) for item in request["items"]}
    if stage == "challenger" and requested_symbols & existing_symbols:
        raise ReviewAllocationError("challenger budget is already approved for one or more symbols")
    purchase_count = len(requested_symbols) if stage == "challenger" else 1
    if existing_count + purchase_count > capacity:
        raise ReviewAllocationError(
            f"{stage} run capacity exceeded: "
            f"{existing_count} committed + {purchase_count} requested > {capacity}"
        )
    payload = {
        **core,
        "capacity": {
            "limit": capacity,
            "source": capacity_source,
            "committed_before": existing_count,
            "approved_count": purchase_count,
            "committed_after": existing_count + purchase_count,
        },
    }
    sealed = seal_json(
        target,
        payload,
        artifact_type=_BUDGET_APPROVAL_ARTIFACT_TYPES[stage],
        sealed_at=approved_at,
    )
    return _budget_approval_result(
        payload,
        path=_relative(target, repository),
        sha256=sealed.sha256,
        idempotent=False,
    )


def _verify_budget_request(
    *,
    root: Path,
    repository: Path,
    budget_stage: str,
    request_path: str,
    request_sha256: str,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    path = _resolve_path(repository, request_path, "review budget request")
    expected = _sha256(request_sha256, "request_sha256")
    try:
        sealed = verify_sealed(path)
    except (OSError, SealingError) as exc:
        raise ReviewAllocationError("review budget request seal binding is invalid") from exc
    if (
        sealed.artifact_type != _BUDGET_REQUEST_ARTIFACT_TYPES[budget_stage]
        or sealed.sha256 != expected
    ):
        raise ReviewAllocationError("review budget request seal binding is invalid")
    request = _read_json(path, "review budget request")
    _validate_budget_request_payload(request, budget_stage=budget_stage)
    if sealed.sealed_at != _parse_datetime(request["requested_at"], "request.requested_at"):
        raise ReviewAllocationError("review budget request timestamp drifted")
    underwriting_binding = request["underwriting_approval"]
    underwriting = verify_underwriting_approval(
        root=root,
        repository_root=repository,
        approval_path=str(underwriting_binding["path"]),
        approval_sha256=str(underwriting_binding["sha256"]),
    )
    if underwriting["approval"]["manager_screen_run_id"] != request["manager_screen_run_id"]:
        raise ReviewAllocationError("review budget request manager run drifted")
    requested_at = _parse_datetime(
        request["requested_at"],
        "request.requested_at",
    )
    if requested_at <= _parse_datetime(
        underwriting["approval"]["approved_at"],
        "underwriting approval approved_at",
    ):
        raise ReviewAllocationError("review budget request must postdate underwriting approval")
    approved_symbols = {str(item["symbol"]) for item in underwriting["approval"]["candidates"]}
    requested_symbols = {str(item["symbol"]) for item in request["items"]}
    if not requested_symbols <= approved_symbols:
        raise ReviewAllocationError(
            "review budget request contains symbols outside underwriting approval"
        )
    for item in request["items"]:
        artifacts: dict[str, tuple[dict[str, Any], Any]] = {}
        for key, artifact_type in (
            ("evaluation", "machine_underwriting_evaluation"),
            ("candidate", "portfolio_candidate"),
        ):
            binding = item[key]
            artifact = _resolve_path(repository, str(binding["path"]), f"request {key}")
            try:
                verified = verify_sealed(artifact)
            except SealingError as exc:
                raise ReviewAllocationError(
                    f"review budget request {key} binding is invalid"
                ) from exc
            if verified.sha256 != binding["sha256"] or verified.artifact_type != artifact_type:
                raise ReviewAllocationError(f"review budget request {key} binding is invalid")
            artifacts[key] = (
                _read_json(artifact, f"review budget request {key}"),
                verified,
            )
        evaluation, evaluation_seal = artifacts["evaluation"]
        candidate, _ = artifacts["candidate"]
        if (
            evaluation.get("symbol") != item["symbol"]
            or candidate.get("symbol") != item["symbol"]
            or evaluation.get("review_id") != request["review_run_id"]
            or candidate.get("source_machine_decision_sha256") != evaluation_seal.sha256
        ):
            raise ReviewAllocationError(
                "review budget request candidate/evaluation relationship is invalid"
            )
    return (
        request,
        {"path": _relative(path, repository), "sha256": sealed.sha256},
        underwriting,
    )


def _validate_budget_approval_binding(
    payload: Mapping[str, Any],
    *,
    sealed: Any,
    path: Path,
    request: Mapping[str, Any],
    request_binding: Mapping[str, str],
    underwriting: Mapping[str, Any],
    budget_stage: str,
    base: Path,
    repository: Path,
) -> None:
    underwriting_payload = underwriting["approval"]
    approved_at = _parse_datetime(payload["approved_at"], "approval.approved_at")
    requested_at = _parse_datetime(request["requested_at"], "request.requested_at")
    expected_underwriting = {
        "path": underwriting["approval_path"],
        "sha256": underwriting["approval_sha256"],
    }
    if path.name != f"{payload['approval_id']}.json":
        raise ReviewAllocationError("review budget approval path does not match approval_id")
    if sealed.sealed_at != approved_at or approved_at <= requested_at:
        raise ReviewAllocationError("review budget approval timestamp drifted")
    if (
        payload["manager_screen_run_id"] != request["manager_screen_run_id"]
        or payload["review_run_id"] != request["review_run_id"]
        or payload["request"] != request_binding
        or payload["underwriting_approval"] != expected_underwriting
        or payload["policy_binding"] != underwriting_payload["policy_binding"]
        or payload["items"] != request["items"]
    ):
        raise ReviewAllocationError("review budget approval binding drifted")
    manager = str(underwriting_payload["approved_by"])
    if (
        payload["approved_by"] != manager
        or manager == request["requested_by"]
        or payload["executor"] == manager
    ):
        raise ReviewAllocationError("review budget approval role binding drifted")
    _, underwriting_capacity, _ = _load_run_policy_contract(
        base=base,
        repository=repository,
        run_id=str(payload["manager_screen_run_id"]),
        expected_binding=payload["policy_binding"],
    )
    expected_limit = underwriting_capacity if budget_stage == "challenger" else 1
    expected_source = (
        "stage_capacity_per_run.underwriting"
        if budget_stage == "challenger"
        else "single_portfolio_synthesis_per_manager_run"
    )
    expected_count = len(request["items"]) if budget_stage == "challenger" else 1
    capacity = payload["capacity"]
    if (
        capacity["limit"] != expected_limit
        or capacity["source"] != expected_source
        or capacity["approved_count"] != expected_count
        or not isinstance(capacity["committed_before"], int)
        or isinstance(capacity["committed_before"], bool)
        or capacity["committed_before"] < 0
        or capacity["committed_after"] != capacity["committed_before"] + expected_count
        or capacity["committed_after"] > expected_limit
    ):
        raise ReviewAllocationError("review budget approval capacity drifted")


def _validate_budget_request_payload(payload: Any, *, budget_stage: str) -> None:
    if not isinstance(payload, Mapping) or set(payload) != _BUDGET_REQUEST_KEYS:
        raise ReviewAllocationError("review budget request fields do not match contract")
    if payload.get("schema_version") != 1 or payload.get("budget_stage") != budget_stage:
        raise ReviewAllocationError("review budget request schema/stage is invalid")
    _identifier(payload.get("request_id"), "request_id")
    _identifier(payload.get("manager_screen_run_id"), "manager_screen_run_id")
    _identifier(payload.get("review_run_id"), "review_run_id")
    _text(payload.get("trigger"), "trigger")
    _text(payload.get("requested_by"), "requested_by")
    _parse_datetime(payload.get("requested_at"), "requested_at")
    _validate_path_binding(payload.get("underwriting_approval"), "underwriting_approval")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ReviewAllocationError("review budget request items are invalid")
    symbols: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping) or set(item) != _BUDGET_REQUEST_ITEM_KEYS:
            raise ReviewAllocationError("review budget request item is invalid")
        symbol = _text(item.get("symbol"), "request item symbol")
        if symbol in symbols:
            raise ReviewAllocationError("review budget request symbols are duplicated")
        symbols.add(symbol)
        _validate_path_binding(item.get("evaluation"), "request evaluation")
        _validate_path_binding(item.get("candidate"), "request candidate")


def _validate_budget_approval_payload(payload: Any, *, budget_stage: str) -> None:
    if not isinstance(payload, Mapping) or set(payload) != _BUDGET_APPROVAL_KEYS:
        raise ReviewAllocationError("review budget approval fields do not match contract")
    if payload.get("schema_version") != 1 or payload.get("budget_stage") != budget_stage:
        raise ReviewAllocationError("review budget approval schema/stage is invalid")
    _identifier(payload.get("approval_id"), "approval_id")
    _identifier(payload.get("manager_screen_run_id"), "manager_screen_run_id")
    _identifier(payload.get("review_run_id"), "review_run_id")
    _text(payload.get("approved_by"), "approved_by")
    _parse_datetime(payload.get("approved_at"), "approved_at")
    _text(payload.get("reason"), "reason")
    _text(payload.get("executor"), "executor")
    _validate_path_binding(payload.get("request"), "approval request")
    _validate_path_binding(payload.get("underwriting_approval"), "approval underwriting")
    if not isinstance(payload.get("policy_binding"), Mapping):
        raise ReviewAllocationError("review budget approval policy binding is invalid")
    capacity = payload.get("capacity")
    if not isinstance(capacity, Mapping) or set(capacity) != {
        "limit",
        "source",
        "committed_before",
        "approved_count",
        "committed_after",
    }:
        raise ReviewAllocationError("review budget approval capacity is invalid")
    if not isinstance(payload.get("items"), list) or not payload["items"]:
        raise ReviewAllocationError("review budget approval items are invalid")


def _validate_path_binding(value: Any, label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != _PATH_BINDING_KEYS:
        raise ReviewAllocationError(f"{label} binding is invalid")
    _text(value.get("path"), f"{label}.path")
    _sha256(value.get("sha256"), f"{label}.sha256")


def _budget_stage(value: str) -> str:
    stage = _text(value, "budget_stage")
    if stage not in _BUDGET_STAGES:
        raise ReviewAllocationError(f"unsupported review budget stage: {stage}")
    return stage


def _budget_approval_result(
    payload: Mapping[str, Any],
    *,
    path: str,
    sha256: str,
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "approval_id": payload["approval_id"],
        "manager_screen_run_id": payload["manager_screen_run_id"],
        "review_run_id": payload["review_run_id"],
        "budget_stage": payload["budget_stage"],
        "approved_symbols": [item["symbol"] for item in payload["items"]],
        "approval_path": path,
        "approval_sha256": sha256,
        "capacity": dict(payload["capacity"]),
        "idempotent": idempotent,
    }


def _validate_candidates(
    candidates: list[Mapping[str, Any]],
    *,
    queue: list[Mapping[str, Any]],
    coverage_root: Path,
    repository: Path,
    manager_screen_run_id: str,
    approved_by: str,
    approved_at: dt.datetime,
) -> list[dict[str, Any]]:
    if not isinstance(candidates, list) or not candidates:
        raise ReviewAllocationError("underwriting approval candidates must not be empty")
    queue_by_symbol: dict[str, Mapping[str, Any]] = {}
    for item in queue:
        symbol = item.get("symbol")
        if isinstance(symbol, str):
            if symbol in queue_by_symbol:
                raise ReviewAllocationError(f"duplicate research queue symbol: {symbol}")
            queue_by_symbol[symbol] = item

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in candidates:
        if not isinstance(raw, Mapping) or set(raw) != _CANDIDATE_INPUT_KEYS:
            raise ReviewAllocationError("underwriting candidate fields do not match contract")
        symbol = _text(raw.get("symbol"), "candidate.symbol")
        if not SYMBOL_RE.fullmatch(symbol):
            raise ReviewAllocationError(f"invalid underwriting symbol: {symbol}")
        if symbol in seen:
            raise ReviewAllocationError(f"duplicate underwriting candidate: {symbol}")
        seen.add(symbol)
        queued = queue_by_symbol.get(symbol)
        if queued is None:
            raise ReviewAllocationError(f"research queue candidate is missing: {symbol}")
        if queued.get("manager_screen_run_id") != manager_screen_run_id:
            raise ReviewAllocationError(
                f"underwriting candidate belongs to a different manager run: {symbol}"
            )
        normalized.append(
            _validate_candidate(
                raw,
                queued=queued,
                coverage_root=coverage_root,
                repository=repository,
                approved_by=approved_by,
                approved_at=approved_at,
            )
        )
    return sorted(normalized, key=lambda item: item["symbol"])


def _validate_candidate(
    raw: Mapping[str, Any],
    *,
    queued: Mapping[str, Any],
    coverage_root: Path,
    repository: Path,
    approved_by: str,
    approved_at: dt.datetime,
) -> dict[str, Any]:
    symbol = str(raw["symbol"])
    selection = _binding(
        raw,
        path_key="deep_selection_path",
        sha_key="deep_selection_sha256",
        repository=repository,
        label=f"{symbol} deep selection",
        require_sealed=True,
    )
    if (
        queued.get("profile_scoped_selection_path") != selection["path"]
        or queued.get("profile_scoped_selection_sha256") != selection["sha256"]
    ):
        raise ReviewAllocationError(f"deep selection does not match research queue: {symbol}")
    selection_seal = verify_sealed(repository / selection["path"])
    if selection_seal.artifact_type != "scoped_research_cross_company_selection":
        raise ReviewAllocationError(f"deep selection artifact type is invalid: {symbol}")
    selection_payload = _read_json(repository / selection["path"], "deep selection")
    if selection_payload.get("next_stage") != "deep_research":
        raise ReviewAllocationError(f"deep selection does not grant deep research: {symbol}")
    ranking = selection_payload.get("ranking")
    if not isinstance(ranking, list) or not any(
        isinstance(item, Mapping) and item.get("symbol") == symbol and item.get("selected") is True
        for item in ranking
    ):
        raise ReviewAllocationError(f"candidate was not selected for deep research: {symbol}")
    if selection_seal.sealed_at > approved_at:
        raise ReviewAllocationError(f"deep selection postdates approval: {symbol}")

    completion = _binding(
        raw,
        path_key="deep_completion_path",
        sha_key="deep_completion_sha256",
        repository=repository,
        label=f"{symbol} deep completion",
        require_sealed=True,
    )
    try:
        completion_status = deep_research_completion_status(
            root=coverage_root,
            symbol=symbol,
        )
    except (DeepResearchCompletionError, OSError, ValueError) as exc:
        raise ReviewAllocationError(
            f"deep research completion chain is invalid: {symbol}: {exc}"
        ) from exc
    if (
        completion_status.get("finalized") is not True
        or completion_status.get("receipt_path") != completion["path"]
        or completion_status.get("receipt_sha256") != completion["sha256"]
    ):
        raise ReviewAllocationError(
            f"deep research completion receipt does not match live terminal projection: {symbol}"
        )

    completion_path = repository / completion["path"]
    completion_seal = verify_sealed(completion_path)
    receipt = _read_json(completion_path, "deep-research completion receipt")
    completed_at = _parse_datetime(receipt.get("completed_at"), "completion.completed_at")
    if completed_at > approved_at or completion_seal.sealed_at > approved_at:
        raise ReviewAllocationError(f"deep completion postdates approval: {symbol}")
    if (
        receipt.get("symbol") != symbol
        or receipt.get("manager_screen_run_id") != queued.get("manager_screen_run_id")
        or receipt.get("profile_cycle_id") != queued.get("profile_cycle_id")
        or completion_status.get("manager_screen_run_id")
        != queued.get("manager_screen_run_id")
        or completion_status.get("profile_cycle_id") != queued.get("profile_cycle_id")
    ):
        raise ReviewAllocationError(f"deep completion identity does not match queue: {symbol}")

    receipt_selection = receipt.get("selection")
    report = receipt.get("report")
    claims = receipt.get("research_claims")
    if not all(isinstance(item, Mapping) for item in (receipt_selection, report, claims)):
        raise ReviewAllocationError(f"deep completion receipt bindings are invalid: {symbol}")
    assert isinstance(receipt_selection, Mapping)
    assert isinstance(report, Mapping)
    assert isinstance(claims, Mapping)
    manager = _effective_manager_authority_from_completion(
        receipt,
        repository=repository,
        manager_screen_run_id=str(queued["manager_screen_run_id"]),
        approved_at=approved_at,
    )
    if approved_by != manager:
        raise ReviewAllocationError(
            "underwriting approved_by does not match sealed effective manager authority"
        )
    if (
        receipt_selection.get("path") != selection["path"]
        or receipt_selection.get("sha256") != selection["sha256"]
    ):
        raise ReviewAllocationError(f"deep completion selection binding drifted: {symbol}")

    completed_history = [
        item
        for item in (queued.get("stage_history") or [])
        if isinstance(item, Mapping)
        and item.get("stage") == "deep_research"
        and item.get("status") == "completed"
    ]
    if len(completed_history) != 1:
        raise ReviewAllocationError(
            f"deep research completion is not recorded exactly once: {symbol}"
        )
    history = completed_history[0]
    expected_history = {
        "agent": receipt.get("research_agent"),
        "result_path": report.get("path"),
        "result_sha256": report.get("sha256"),
        "claims_path": claims.get("path"),
        "claims_sha256": claims.get("sha256"),
        "selection_path": selection["path"],
        "selection_sha256": selection["sha256"],
        "completion_path": completion["path"],
        "completion_sha256": completion["sha256"],
        "manager_screen_run_id": receipt.get("manager_screen_run_id"),
        "profile_cycle_id": receipt.get("profile_cycle_id"),
    }
    if any(history.get(key) != value for key, value in expected_history.items()):
        raise ReviewAllocationError(
            f"deep research queue history does not match sealed completion: {symbol}"
        )
    if (
        queued.get("deep_research_completion_path") != completion["path"]
        or queued.get("deep_research_completion_sha256") != completion["sha256"]
        or queued.get("result_path") != report.get("path")
        or queued.get("result_sha256") != report.get("sha256")
        or queued.get("deep_research_claims_path") != claims.get("path")
        or queued.get("deep_research_claims_sha256") != claims.get("sha256")
    ):
        raise ReviewAllocationError(
            f"deep research live queue projection does not match receipt: {symbol}"
        )
    research_agent = _text(receipt.get("research_agent"), "completion.research_agent")
    if research_agent == approved_by:
        raise ReviewAllocationError(
            f"underwriting approver must be independent of deep researcher: {symbol}"
        )

    company_dir_text = _text(queued.get("target_company_dir"), f"{symbol} target_company_dir")
    company_dir = _resolve_path(repository, company_dir_text, f"{symbol} company dir")
    if not company_dir.is_dir():
        raise ReviewAllocationError(f"company directory is missing: {symbol}")
    source_ids = claims.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids or not all(
        isinstance(item, str) and item for item in source_ids
    ):
        raise ReviewAllocationError(f"deep completion research sources are invalid: {symbol}")
    return {
        "symbol": symbol,
        "company_dir": _relative(company_dir, repository),
        "deep_selection": selection,
        "deep_completion": completion,
        "research_claims": {
            "path": _text(claims.get("path"), "completion.research_claims.path"),
            "sha256": _sha256(
                claims.get("sha256"),
                "completion.research_claims.sha256",
            ),
            "report_id": _text(
                claims.get("report_id"),
                "completion.research_claims.report_id",
            ),
            "source_ids": sorted(source_ids),
        },
    }


def _effective_manager_authority_from_completion(
    receipt: Mapping[str, Any],
    *,
    repository: Path,
    manager_screen_run_id: str,
    approved_at: dt.datetime,
) -> str:
    """Revalidate the manager authority sealed by deep-research completion."""

    authority = receipt.get("effective_manager_authority")
    if not isinstance(authority, Mapping) or set(authority) != (
        _EFFECTIVE_MANAGER_AUTHORITY_KEYS
    ):
        raise ReviewAllocationError(
            "deep completion effective manager authority is invalid"
        )
    agent = _text(
        authority.get("agent"),
        "completion.effective_manager_authority.agent",
    )
    source_type = _text(
        authority.get("source_type"),
        "completion.effective_manager_authority.source_type",
    )
    if source_type not in _EFFECTIVE_MANAGER_AUTHORITY_SOURCE_TYPES:
        raise ReviewAllocationError(
            "deep completion effective manager authority source type is invalid"
        )
    source_path_text = _text(
        authority.get("source_path"),
        "completion.effective_manager_authority.source_path",
    )
    source_sha256 = _sha256(
        authority.get("source_sha256"),
        "completion.effective_manager_authority.source_sha256",
    )
    source_path = _resolve_path(
        repository,
        source_path_text,
        "completion effective manager authority source",
    )
    try:
        sealed = verify_sealed(source_path)
    except (OSError, SealingError, ValueError) as exc:
        raise ReviewAllocationError(
            "deep completion effective manager authority source is not validly sealed"
        ) from exc
    if sealed.artifact_type != source_type or sealed.sha256 != source_sha256:
        raise ReviewAllocationError(
            "deep completion effective manager authority source binding is invalid"
        )
    if sealed.sealed_at > approved_at:
        raise ReviewAllocationError(
            "deep completion effective manager authority postdates underwriting approval"
        )
    source = _read_json(source_path, "effective manager authority source")
    manager = source.get("manager")
    if (
        source.get("run_id") != manager_screen_run_id
        or not isinstance(manager, Mapping)
        or manager.get("agent") != agent
    ):
        raise ReviewAllocationError(
            "deep completion effective manager authority does not match its sealed source"
        )
    return agent


def _ensure_run_policy_contract(
    *,
    base: Path,
    repository: Path,
    run_id: str,
    policy_path: str,
    expected_sha256: str,
    bound_at: dt.datetime,
) -> tuple[dict[str, str], int, float]:
    expected = _sha256(expected_sha256, "policy_sha256")
    live_path = _resolve_path(
        repository,
        policy_path,
        "research-allocation policy",
    )
    if _relative(live_path, repository) != _RUN_POLICY_CANONICAL_PATH:
        raise ReviewAllocationError(
            f"manager-run research budget must use the canonical {_RUN_POLICY_CANONICAL_PATH}"
        )
    contract_path, snapshot_path = _run_policy_paths(
        base=base,
        run_id=run_id,
    )
    contract_exists = (
        contract_path.exists()
        or contract_path.with_name(f"{contract_path.name}.seal.json").exists()
    )
    if contract_exists:
        contract, _ = _read_run_policy_contract(
            contract_path,
            run_id=run_id,
        )
        policy_ref = _normalize_run_policy_ref(contract.get("policy"))
        if expected != policy_ref["file_sha256"]:
            raise ReviewAllocationError(
                "research-allocation policy differs from the sealed "
                "manager-run contract; start a new manager run"
            )
        if not snapshot_path.exists():
            policy_document, live_ref = _load_live_policy_document(
                repository=repository,
                path=live_path,
                expected_sha256=expected,
            )
            if live_ref != policy_ref:
                raise ReviewAllocationError(
                    "live policy cannot materialize the sealed run snapshot"
                )
            _seal_run_policy_snapshot(
                snapshot_path=snapshot_path,
                policy_document=policy_document,
                sealed_at=bound_at,
            )
        return _load_run_policy_contract(
            base=base,
            repository=repository,
            run_id=run_id,
            expected_binding=None,
        )

    policy_document, policy_ref = _load_live_policy_document(
        repository=repository,
        path=live_path,
        expected_sha256=expected,
    )
    contract = {
        "schema_version": 1,
        "run_id": run_id,
        "bound_at": bound_at.isoformat(),
        "policy": policy_ref,
        "portfolio_action": None,
    }
    seal_json(
        contract_path,
        contract,
        artifact_type=_RUN_POLICY_CONTRACT_ARTIFACT_TYPE,
        sealed_at=bound_at,
    )
    _seal_run_policy_snapshot(
        snapshot_path=snapshot_path,
        policy_document=policy_document,
        sealed_at=bound_at,
    )
    return _load_run_policy_contract(
        base=base,
        repository=repository,
        run_id=run_id,
        expected_binding=None,
    )


def _load_run_policy_contract(
    *,
    base: Path,
    repository: Path,
    run_id: str,
    expected_binding: Any,
) -> tuple[dict[str, str], int, float]:
    contract_path, snapshot_path = _run_policy_paths(
        base=base,
        run_id=run_id,
    )
    contract, _ = _read_run_policy_contract(
        contract_path,
        run_id=run_id,
    )
    policy_ref = _normalize_run_policy_ref(contract.get("policy"))
    try:
        snapshot_seal = verify_sealed(snapshot_path)
        policy_document = _read_json(
            snapshot_path,
            "manager-run research policy snapshot",
        )
    except (OSError, SealingError) as exc:
        raise ReviewAllocationError(
            "manager-run research policy snapshot is not validly sealed"
        ) from exc
    binding = {
        "path": _relative(snapshot_path, repository),
        "sha256": snapshot_seal.sha256,
        "policy_id": policy_ref["policy_id"],
        "version": policy_ref["version"],
    }
    if expected_binding is not None and dict(expected_binding) != binding:
        raise ReviewAllocationError("approval does not bind the sealed manager-run research policy")
    if snapshot_seal.artifact_type != _RUN_POLICY_SNAPSHOT_ARTIFACT_TYPE or not isinstance(
        policy_document, Mapping
    ):
        raise ReviewAllocationError("manager-run research policy snapshot binding is invalid")
    snapshot_ref = _policy_ref_from_document(
        policy_document,
        file_sha256=policy_ref["file_sha256"],
    )
    if snapshot_ref != policy_ref:
        raise ReviewAllocationError(
            "manager-run research policy snapshot drifted from its contract"
        )
    capacity, effort = _underwriting_policy_limits(policy_document)
    return binding, capacity, effort


def _run_policy_paths(*, base: Path, run_id: str) -> tuple[Path, Path]:
    run_dir = base / "manager-screen" / run_id
    return (
        run_dir / "research-policy.json",
        run_dir / "research-policy.snapshot.json",
    )


def _read_run_policy_contract(
    path: Path,
    *,
    run_id: str,
) -> tuple[dict[str, Any], Any]:
    try:
        sealed = verify_sealed(path)
        contract = _read_json(path, "manager-run research policy contract")
    except (OSError, SealingError) as exc:
        raise ReviewAllocationError(
            "manager-run research policy contract is not validly sealed"
        ) from exc
    if (
        sealed.artifact_type != _RUN_POLICY_CONTRACT_ARTIFACT_TYPE
        or set(contract)
        != {
            "schema_version",
            "run_id",
            "bound_at",
            "policy",
            "portfolio_action",
        }
        or contract.get("schema_version") != 1
        or contract.get("run_id") != run_id
        or contract.get("portfolio_action") is not None
    ):
        raise ReviewAllocationError("manager-run research policy contract is invalid")
    _parse_datetime(contract.get("bound_at"), "research policy bound_at")
    _normalize_run_policy_ref(contract.get("policy"))
    return contract, sealed


def _load_live_policy_document(
    *,
    repository: Path,
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    if not path.is_file():
        raise ReviewAllocationError("research-allocation policy is missing")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ReviewAllocationError("research-allocation policy SHA-256 mismatch")
    document = _read_json(path, "research-allocation policy")
    ref = _policy_ref_from_document(
        document,
        file_sha256=actual,
        path=_relative(path, repository),
    )
    _underwriting_policy_limits(document)
    return document, ref


def _policy_ref_from_document(
    document: Mapping[str, Any],
    *,
    file_sha256: str,
    path: str = _RUN_POLICY_CANONICAL_PATH,
) -> dict[str, str]:
    payload = document.get("payload")
    if document.get("kind") != "research_allocation" or not isinstance(payload, Mapping):
        raise ReviewAllocationError("research-allocation policy kind is invalid")
    return {
        "policy_id": _text(document.get("policy_id"), "policy_id"),
        "version": _text(document.get("version"), "policy version"),
        "path": path,
        "file_sha256": _sha256(file_sha256, "policy file_sha256"),
        "payload_sha256": hashlib.sha256(canonical_json_bytes(dict(payload))).hexdigest(),
    }


def _normalize_run_policy_ref(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _RUN_POLICY_REF_KEYS:
        raise ReviewAllocationError("manager-run research policy reference is invalid")
    normalized = {
        "policy_id": _text(value.get("policy_id"), "policy.policy_id"),
        "version": _text(value.get("version"), "policy.version"),
        "path": _text(value.get("path"), "policy.path"),
        "file_sha256": _sha256(
            value.get("file_sha256"),
            "policy.file_sha256",
        ),
        "payload_sha256": _sha256(
            value.get("payload_sha256"),
            "policy.payload_sha256",
        ),
    }
    if normalized["path"] != _RUN_POLICY_CANONICAL_PATH:
        raise ReviewAllocationError("manager-run research policy reference is not canonical")
    return normalized


def _seal_run_policy_snapshot(
    *,
    snapshot_path: Path,
    policy_document: Mapping[str, Any],
    sealed_at: dt.datetime,
) -> None:
    seal_json(
        snapshot_path,
        dict(policy_document),
        artifact_type=_RUN_POLICY_SNAPSHOT_ARTIFACT_TYPE,
        sealed_at=sealed_at,
    )


def _underwriting_policy_limits(
    policy_document: Mapping[str, Any],
) -> tuple[int, float]:
    policy_payload = policy_document.get("payload")
    if not isinstance(policy_payload, Mapping):
        raise ReviewAllocationError("research-allocation policy payload is invalid")
    capacities = policy_payload.get("stage_capacity_per_run")
    capacity = capacities.get("underwriting") if isinstance(capacities, Mapping) else None
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise ReviewAllocationError(
            "stage_capacity_per_run.underwriting must be a positive integer"
        )
    budgets = policy_payload.get("effort_budget_hours")
    effort = budgets.get("underwriting") if isinstance(budgets, Mapping) else None
    if isinstance(effort, bool) or not isinstance(effort, (int, float)) or effort <= 0:
        raise ReviewAllocationError("effort_budget_hours.underwriting must be positive")
    return capacity, float(effort)


def _load_approval_ledger(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for approval_path in sorted(path.glob("*.json")):
        if approval_path.name.endswith(".seal.json"):
            continue
        try:
            sealed = verify_sealed(approval_path)
        except (SealingError, ValueError) as exc:
            raise ReviewAllocationError(
                f"underwriting approval is not validly sealed: {approval_path}"
            ) from exc
        if sealed.artifact_type != APPROVAL_ARTIFACT_TYPE:
            raise ReviewAllocationError(
                f"underwriting approval artifact type is invalid: {approval_path}"
            )
        payload = _read_json(approval_path, "underwriting approval")
        _validate_approval_payload(payload)
        approval_id = str(payload["approval_id"])
        if approval_id in result:
            raise ReviewAllocationError(f"duplicate approval_id: {approval_id}")
        result[approval_id] = payload
    return result


def _validate_ledger(
    approvals: Mapping[str, Mapping[str, Any]], *, manager_screen_run_id: str
) -> set[str]:
    symbols: set[str] = set()
    for payload in approvals.values():
        if payload.get("manager_screen_run_id") != manager_screen_run_id:
            raise ReviewAllocationError("approval ledger spans multiple manager runs")
        for candidate in payload["candidates"]:
            symbol = str(candidate["symbol"])
            if symbol in symbols:
                raise ReviewAllocationError(
                    f"approval ledger contains duplicate underwriting budget: {symbol}"
                )
            symbols.add(symbol)
    return symbols


def _validate_complete_ledger(
    approvals: Mapping[str, Mapping[str, Any]],
    *,
    manager_screen_run_id: str,
    capacity: int,
    policy_binding: Mapping[str, Any],
) -> None:
    _validate_ledger(approvals, manager_screen_run_id=manager_screen_run_id)
    committed = 0
    ordered = sorted(
        approvals.values(),
        key=lambda item: (
            _parse_datetime(item["approved_at"], "approval.approved_at"),
            str(item["approval_id"]),
        ),
    )
    for payload in ordered:
        if payload.get("policy_binding") != policy_binding:
            raise ReviewAllocationError(
                "underwriting approval ledger spans multiple run policy contracts"
            )
        counts = payload["capacity"]
        approved_count = len(payload["candidates"])
        if (
            counts["limit"] != capacity
            or counts["committed_before"] != committed
            or counts["approved_count"] != approved_count
            or counts["committed_after"] != committed + approved_count
        ):
            raise ReviewAllocationError("underwriting approval capacity ledger is invalid")
        committed += approved_count
    if committed > capacity:
        raise ReviewAllocationError("underwriting approval ledger exceeds run capacity")


def _validate_approval_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping) or set(payload) != _APPROVAL_KEYS:
        raise ReviewAllocationError("underwriting approval fields do not match contract")
    if (
        payload.get("schema_version") != APPROVAL_SCHEMA_VERSION
        or payload.get("stage") != "underwriting"
    ):
        raise ReviewAllocationError("underwriting approval schema/stage is invalid")
    _identifier(payload.get("approval_id"), "approval_id")
    _identifier(payload.get("manager_screen_run_id"), "manager_screen_run_id")
    _text(payload.get("approved_by"), "approved_by")
    _parse_datetime(payload.get("approved_at"), "approved_at")
    _text(payload.get("reason"), "reason")
    policy = payload.get("policy_binding")
    if not isinstance(policy, Mapping) or set(policy) != _POLICY_BINDING_KEYS:
        raise ReviewAllocationError("underwriting approval policy binding is invalid")
    _text(policy.get("path"), "policy.path")
    _sha256(policy.get("sha256"), "policy.sha256")
    _text(policy.get("policy_id"), "policy.policy_id")
    _text(policy.get("version"), "policy.version")
    counts = payload.get("capacity")
    if not isinstance(counts, Mapping) or set(counts) != _CAPACITY_KEYS:
        raise ReviewAllocationError("underwriting approval capacity binding is invalid")
    for field in ("limit", "approved_count", "committed_after"):
        value = counts.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ReviewAllocationError(f"approval capacity {field} is invalid")
    committed_before = counts.get("committed_before")
    if (
        isinstance(committed_before, bool)
        or not isinstance(committed_before, int)
        or committed_before < 0
    ):
        raise ReviewAllocationError("approval capacity committed_before is invalid")
    effort = counts.get("effort_budget_hours_per_company")
    if isinstance(effort, bool) or not isinstance(effort, (int, float)) or effort <= 0:
        raise ReviewAllocationError("approval underwriting effort budget is invalid")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ReviewAllocationError("underwriting approval candidates are invalid")
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != _CANDIDATE_KEYS:
            raise ReviewAllocationError("approved candidate fields are invalid")
        symbol = candidate.get("symbol")
        if not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol):
            raise ReviewAllocationError("approved candidate symbol is invalid")
        _text(candidate.get("company_dir"), "candidate.company_dir")
        for key in ("deep_selection", "deep_completion"):
            binding = candidate.get(key)
            if not isinstance(binding, Mapping) or set(binding) != _PATH_BINDING_KEYS:
                raise ReviewAllocationError(f"candidate {key} binding is invalid")
            _text(binding.get("path"), f"candidate.{key}.path")
            _sha256(binding.get("sha256"), f"candidate.{key}.sha256")
        claims = candidate.get("research_claims")
        if not isinstance(claims, Mapping) or set(claims) != _CLAIMS_BINDING_KEYS:
            raise ReviewAllocationError("candidate research_claims binding is invalid")
        _text(claims.get("path"), "candidate.research_claims.path")
        _sha256(claims.get("sha256"), "candidate.research_claims.sha256")
        _text(claims.get("report_id"), "candidate.research_claims.report_id")
        source_ids = claims.get("source_ids")
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or not all(isinstance(item, str) and item for item in source_ids)
        ):
            raise ReviewAllocationError("candidate research source_ids are invalid")


def _binding(
    raw: Mapping[str, Any],
    *,
    path_key: str,
    sha_key: str,
    repository: Path,
    label: str,
    require_sealed: bool,
) -> dict[str, str]:
    path_text = _text(raw.get(path_key), path_key)
    expected = _sha256(raw.get(sha_key), sha_key)
    path = _resolve_path(repository, path_text, label)
    if not path.is_file():
        raise ReviewAllocationError(f"{label} is missing")
    if require_sealed:
        try:
            actual = verify_sealed(path).sha256
        except (SealingError, ValueError) as exc:
            raise ReviewAllocationError(f"{label} is not validly sealed") from exc
    else:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ReviewAllocationError(f"{label} SHA-256 mismatch")
    return {"path": _relative(path, repository), "sha256": actual}


def _approval_result(
    payload: Mapping[str, Any],
    *,
    approval_path: str,
    approval_sha256: str,
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "approval_id": payload["approval_id"],
        "manager_screen_run_id": payload["manager_screen_run_id"],
        "stage": "underwriting",
        "approved_symbols": [item["symbol"] for item in payload["candidates"]],
        "approval_path": approval_path,
        "approval_sha256": approval_sha256,
        "capacity": dict(payload["capacity"]),
        "idempotent": idempotent,
        **downstream_review_request_contracts(),
    }


def _resolve_path(root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    _require_within(resolved, root, label)
    return resolved


def _require_within(path: Path, root: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ReviewAllocationError(f"{label} escapes repository root") from exc


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ReviewAllocationError(f"path escapes repository root: {path}") from exc


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewAllocationError(f"{label} is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ReviewAllocationError(f"{label} must be an object")
    return payload


def _identifier(value: Any, label: str) -> str:
    text = _text(value, label)
    if not ID_RE.fullmatch(text):
        raise ReviewAllocationError(f"{label} is invalid")
    return text


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewAllocationError(f"{label} must be a non-empty string")
    return value.strip()


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ReviewAllocationError(f"{label} must be a lowercase SHA-256")
    return value


def _require_aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ReviewAllocationError(f"{label} must include timezone information")


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ReviewAllocationError(f"{label} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReviewAllocationError(f"{label} must be an ISO datetime") from exc
    _require_aware(parsed, label)
    return parsed
