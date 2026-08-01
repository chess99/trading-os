from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .claims import ClaimPacketError, build_claim_packet
from .company import REPORT_META_RE, AssetValidationError, validate_company_dir
from .coverage_store import (
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .profile_stage_claims import (
    ProfileStageClaimError,
    verify_active_profile_stage_claim,
)
from .profile_workflow import (
    _requires_funded_full_market_grant,
    _sealed_stage_commitment_ledger,
    _validate_profile_claim_stage_authorization,
    _verify_funded_full_market_profile_grant,
)
from .research_allocation import ResearchAllocationError
from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed


class DeepResearchCompletionError(ValueError):
    """Raised when a formal deep-research completion cannot be authenticated."""


ARTIFACT_TYPE = "deep_research_completion"
SUBMISSION_KEYS = {
    "schema_version",
    "symbol",
    "research_agent",
    "profile_cycle_id",
    "manager_screen_run_id",
    "scoped_selection_path",
    "scoped_selection_sha256",
    "report_path",
    "report_sha256",
    "claims_path",
    "claims_sha256",
}
RECEIPT_KEYS = {
    "schema_version",
    "artifact_type",
    "symbol",
    "research_agent",
    "profile_cycle_id",
    "manager_screen_run_id",
    "completed_at",
    "claim",
    "claim_attempt",
    "selection",
    "manager_predecessor",
    "effective_manager_authority",
    "report",
    "research_claims",
    "projection_base",
    "portfolio_action",
}
CLAIM_KEYS = {
    "task_type",
    "assigned_agent",
    "started_at",
    "effort_budget_hours",
    "preceding_stage",
}
CLAIM_ATTEMPT_KEYS = {
    "path",
    "sha256",
    "sealed_at",
    "attempt_number",
    "agent",
    "stage_authorization",
}
CLAIM_ATTEMPT_AUTHORIZATION_KEYS = {
    "path",
    "sha256",
    "artifact_type",
    "sealed_at",
}
EFFECTIVE_MANAGER_AUTHORITY_KEYS = {
    "agent",
    "source_path",
    "source_sha256",
    "source_type",
}
EFFECTIVE_MANAGER_AUTHORITY_SOURCE_TYPES = {
    "manager_screen_result",
    "manager_screen_quote_impact_result",
    "manager_screen_legacy_transition_result",
    "manager_screen_full_market_allocation_v3_result",
}
SELECTION_KEYS = {
    "path",
    "sha256",
    "sealed_at",
    "next_stage",
    "research_policy",
}
REPORT_KEYS = {
    "path",
    "sha256",
    "report_id",
    "report_type",
    "as_of",
    "information_cutoff",
    "agent_id",
    "predecessor_reports",
    "source_manifest_path",
    "source_manifest_sha256",
}
CLAIMS_KEYS = {
    "path",
    "sha256",
    "sealed_at",
    "report_id",
    "source_ids",
}
PROJECTION_BASE_KEYS = {"research_queue", "screening"}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@serialized_coverage_write
def record_deep_research_completion(
    *,
    root: str | Path,
    symbol: str,
    submission: Mapping[str, Any],
    completed_at: dt.datetime,
) -> dict[str, Any]:
    """Seal one formal deep-research receipt, then project coverage state.

    The receipt captures the exact running queue and screening rows.  Replay
    accepts only those sealed base rows or the deterministic completed rows,
    which makes a crash between the two JSONL writes recoverable without
    allowing unrelated mutable-state drift to be overwritten.
    """

    completed = _aware(completed_at, "completed_at")
    normalized = _normalize_submission(submission, expected_symbol=symbol)
    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    queue_path = base / RESEARCH_QUEUE_FILE
    screening_path = base / SCREENING_FILE
    queue_records = read_jsonl(queue_path)
    screening_records = read_jsonl(screening_path)
    current_queue = _one_record(queue_records, normalized["symbol"], "research queue")
    current_screen = _one_record(screening_records, normalized["symbol"], "screening")
    receipt_path = _receipt_path(
        base=base,
        cycle=normalized["profile_cycle_id"],
        symbol=normalized["symbol"],
    )
    receipt_relative = _relative(receipt_path, repository)
    presence = (receipt_path.exists(), _seal_path(receipt_path).exists())
    if presence[0] != presence[1]:
        raise DeepResearchCompletionError(
            f"deep-research completion is only partially sealed: {receipt_relative}"
        )

    if presence == (True, True):
        receipt, receipt_seal = _load_receipt(
            receipt_path,
            base=base,
            repository=repository,
        )
        receipt_completed = _parse_datetime(
            receipt.get("completed_at"),
            "receipt.completed_at",
        )
        if receipt_seal.sealed_at != receipt_completed:
            raise DeepResearchCompletionError(
                "deep-research receipt seal time conflicts with completed_at"
            )
        _require_submission_matches_receipt(normalized, receipt)
        base_queue, base_screen = _projection_base(receipt)
        expected_queue = _project_queue(
            receipt,
            receipt_path=receipt_relative,
            receipt_sha256=receipt_seal.sha256,
        )
        expected_screen = _project_screen(
            receipt,
            receipt_path=receipt_relative,
            receipt_sha256=receipt_seal.sha256,
        )
        queue_state = _projection_state(
            current_queue,
            before=base_queue,
            expected=expected_queue,
            label="research queue",
        )
        screen_state = _projection_state(
            current_screen,
            before=base_screen,
            expected=expected_screen,
            label="screening",
        )
        rebuilt = _build_receipt(
            normalized=normalized,
            queue_before=base_queue,
            screen_before=base_screen,
            base=base,
            repository=repository,
            completed_at=receipt_completed,
            allow_later_company_reports=True,
        )
        if rebuilt != receipt:
            raise DeepResearchCompletionError(
                "sealed deep-research completion no longer matches its source contracts"
            )
        queue_changed = queue_state == "before"
        screen_changed = screen_state == "before"
        if queue_changed:
            write_jsonl(
                queue_path,
                _replace_symbol(queue_records, normalized["symbol"], expected_queue),
            )
        if screen_changed:
            write_jsonl(
                screening_path,
                _replace_symbol(screening_records, normalized["symbol"], expected_screen),
            )
        return _summary(
            receipt,
            receipt_path=receipt_relative,
            receipt_sha256=receipt_seal.sha256,
            idempotent=not queue_changed and not screen_changed,
            queue_projected=True,
            screening_projected=True,
        )

    receipt = _build_receipt(
        normalized=normalized,
        queue_before=current_queue,
        screen_before=current_screen,
        base=base,
        repository=repository,
        completed_at=completed,
    )
    receipt_seal = seal_json(
        receipt_path,
        receipt,
        artifact_type=ARTIFACT_TYPE,
        sealed_at=completed,
    )
    expected_queue = _project_queue(
        receipt,
        receipt_path=receipt_relative,
        receipt_sha256=receipt_seal.sha256,
    )
    expected_screen = _project_screen(
        receipt,
        receipt_path=receipt_relative,
        receipt_sha256=receipt_seal.sha256,
    )
    # Every external dependency and both projection bases were validated before
    # the immutable receipt was created.  Only deterministic JSONL projection
    # remains after this point.
    write_jsonl(
        queue_path,
        _replace_symbol(queue_records, normalized["symbol"], expected_queue),
    )
    write_jsonl(
        screening_path,
        _replace_symbol(screening_records, normalized["symbol"], expected_screen),
    )
    return _summary(
        receipt,
        receipt_path=receipt_relative,
        receipt_sha256=receipt_seal.sha256,
        idempotent=False,
        queue_projected=True,
        screening_projected=True,
    )


def deep_research_completion_status(
    *,
    root: str | Path,
    symbol: str,
) -> dict[str, Any]:
    """Revalidate one receipt, every upstream seal, and its live projection."""

    normalized_symbol = _symbol(symbol, "symbol")
    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    current_queue = _one_record(
        read_jsonl(base / RESEARCH_QUEUE_FILE),
        normalized_symbol,
        "research queue",
    )
    current_screen = _one_record(
        read_jsonl(base / SCREENING_FILE),
        normalized_symbol,
        "screening",
    )
    cycle = _identifier(current_queue.get("profile_cycle_id"), "profile_cycle_id")
    receipt_path = _receipt_path(base=base, cycle=cycle, symbol=normalized_symbol)
    receipt_relative = _relative(receipt_path, repository)
    receipt, receipt_seal = _load_receipt(
        receipt_path,
        base=base,
        repository=repository,
    )
    base_queue, base_screen = _projection_base(receipt)
    expected_queue = _project_queue(
        receipt,
        receipt_path=receipt_relative,
        receipt_sha256=receipt_seal.sha256,
    )
    expected_screen = _project_screen(
        receipt,
        receipt_path=receipt_relative,
        receipt_sha256=receipt_seal.sha256,
    )
    queue_state = _projection_state(
        current_queue,
        before=base_queue,
        expected=expected_queue,
        label="research queue",
    )
    screen_state = _projection_state(
        current_screen,
        before=base_screen,
        expected=expected_screen,
        label="screening",
    )
    completed = _parse_datetime(receipt.get("completed_at"), "receipt.completed_at")
    if receipt_seal.sealed_at != completed:
        raise DeepResearchCompletionError(
            "deep-research receipt seal time conflicts with completed_at"
        )
    normalized = _submission_from_receipt(receipt)
    rebuilt = _build_receipt(
        normalized=normalized,
        queue_before=base_queue,
        screen_before=base_screen,
        base=base,
        repository=repository,
        completed_at=completed,
        allow_later_company_reports=True,
    )
    if rebuilt != receipt:
        raise DeepResearchCompletionError(
            "sealed deep-research completion no longer matches its source contracts"
        )
    return _summary(
        receipt,
        receipt_path=receipt_relative,
        receipt_sha256=receipt_seal.sha256,
        idempotent=True,
        queue_projected=queue_state == "expected",
        screening_projected=screen_state == "expected",
    )


def _build_receipt(
    *,
    normalized: Mapping[str, Any],
    queue_before: Mapping[str, Any],
    screen_before: Mapping[str, Any],
    base: Path,
    repository: Path,
    completed_at: dt.datetime,
    allow_later_company_reports: bool = False,
) -> dict[str, Any]:
    symbol = str(normalized["symbol"])
    _validate_claim_state(
        queue_before,
        screen_before=screen_before,
        normalized=normalized,
        completed_at=completed_at,
    )
    try:
        claim_attempt = verify_active_profile_stage_claim(
            root=base,
            queue_record=queue_before,
            stage="deep_research",
        )
    except ProfileStageClaimError as exc:
        raise DeepResearchCompletionError(
            f"deep-research active sealed claim is invalid: {symbol}: {exc}"
        ) from exc
    claim_authorization = claim_attempt.get("stage_authorization")
    if (
        claim_attempt.get("agent") != normalized["research_agent"]
        or not isinstance(claim_authorization, Mapping)
        or claim_authorization.get("path") != normalized["scoped_selection_path"]
        or claim_authorization.get("sha256") != normalized["scoped_selection_sha256"]
        or claim_authorization.get("artifact_type") != "scoped_research_cross_company_selection"
    ):
        raise DeepResearchCompletionError(
            f"deep-research submission does not match its sealed active claim: {symbol}"
        )
    try:
        _validate_profile_claim_stage_authorization(
            queue_before,
            base=base,
            repository_root=repository,
        )
    except (ResearchAllocationError, SealingError, ValueError) as exc:
        raise DeepResearchCompletionError(
            f"deep-research claim authorization is invalid: {symbol}: {exc}"
        ) from exc

    selection_path = _repository_file(
        repository,
        normalized["scoped_selection_path"],
        "scoped_selection_path",
    )
    try:
        selection_seal = verify_sealed(selection_path)
        selection = _read_object(selection_path, "scoped-research selection")
    except (OSError, SealingError, ValueError) as exc:
        raise DeepResearchCompletionError(
            f"scoped-research selection is invalid: {symbol}"
        ) from exc
    started_at = _parse_datetime(
        claim_attempt.get("sealed_at"),
        "claim_attempt.sealed_at",
    )
    if (
        selection_seal.artifact_type != "scoped_research_cross_company_selection"
        or selection_seal.sha256 != normalized["scoped_selection_sha256"]
        or selection.get("cycle_id") != normalized["profile_cycle_id"]
        or selection.get("manager_screen_run_id") != normalized["manager_screen_run_id"]
        or selection.get("next_stage") != "deep_research"
        or selection_seal.sealed_at > started_at
    ):
        raise DeepResearchCompletionError(
            f"scoped-research selection does not authorize this claimed deep task: {symbol}"
        )
    ranking = selection.get("ranking")
    matching = (
        [row for row in ranking if isinstance(row, Mapping) and row.get("symbol") == symbol]
        if isinstance(ranking, list)
        else []
    )
    if len(matching) != 1 or matching[0].get("selected") is not True:
        raise DeepResearchCompletionError(
            f"scoped-research selection did not fund deep research: {symbol}"
        )
    research_policy = selection.get("research_policy")
    if not isinstance(research_policy, Mapping):
        raise DeepResearchCompletionError(
            f"deep-research selection lacks its run policy binding: {symbol}"
        )
    try:
        ledger = _sealed_stage_commitment_ledger(
            base=base,
            repository_root=repository,
            manager_screen_run_id=str(normalized["manager_screen_run_id"]),
            next_stage="deep_research",
        )
    except (ResearchAllocationError, SealingError, ValueError) as exc:
        raise DeepResearchCompletionError(
            f"deep-research run budget ledger is invalid: {symbol}: {exc}"
        ) from exc
    commitment = ledger.get(symbol)
    expected_commitment = {
        "manager_screen_run_id": normalized["manager_screen_run_id"],
        "stage": "deep_research",
        "symbol": symbol,
        "profile_cycle_id": normalized["profile_cycle_id"],
        "selection_path": normalized["scoped_selection_path"],
        "selection_sha256": normalized["scoped_selection_sha256"],
    }
    if commitment != expected_commitment:
        raise DeepResearchCompletionError(
            f"deep-research selection is absent from the sealed run ledger: {symbol}"
        )

    manager_predecessor, effective_manager_authority = _manager_predecessor(
        queue_before,
        screen_before=screen_before,
        base=base,
        repository=repository,
        symbol=symbol,
        started_at=started_at,
    )
    report, claims = _formal_report_bindings(
        normalized=normalized,
        queue_before=queue_before,
        repository=repository,
        selection_sealed_at=selection_seal.sealed_at,
        started_at=started_at,
        completed_at=completed_at,
        allow_later_company_reports=allow_later_company_reports,
    )
    receipt = {
        "schema_version": 2,
        "artifact_type": ARTIFACT_TYPE,
        "symbol": symbol,
        "research_agent": normalized["research_agent"],
        "profile_cycle_id": normalized["profile_cycle_id"],
        "manager_screen_run_id": normalized["manager_screen_run_id"],
        "completed_at": completed_at.isoformat(),
        "claim": {
            "task_type": "deep_research",
            "assigned_agent": normalized["research_agent"],
            "started_at": started_at.isoformat(),
            "effort_budget_hours": queue_before.get("effort_budget_hours"),
            "preceding_stage": "scoped_research",
        },
        "claim_attempt": dict(claim_attempt),
        "selection": {
            "path": normalized["scoped_selection_path"],
            "sha256": selection_seal.sha256,
            "sealed_at": selection_seal.sealed_at.isoformat(),
            "next_stage": "deep_research",
            "research_policy": dict(research_policy),
        },
        "manager_predecessor": manager_predecessor,
        "effective_manager_authority": effective_manager_authority,
        "report": report,
        "research_claims": claims,
        "projection_base": {
            "research_queue": dict(queue_before),
            "screening": dict(screen_before),
        },
        "portfolio_action": None,
    }
    _validate_receipt_shape(receipt)
    return receipt


def _validate_claim_state(
    queue_before: Mapping[str, Any],
    *,
    screen_before: Mapping[str, Any],
    normalized: Mapping[str, Any],
    completed_at: dt.datetime,
) -> None:
    symbol = str(normalized["symbol"])
    required_queue = {
        "symbol": symbol,
        "task_type": "deep_research",
        "status": "running",
        "assigned_agent": normalized["research_agent"],
        "profile_cycle_id": normalized["profile_cycle_id"],
        "manager_screen_run_id": normalized["manager_screen_run_id"],
        "profile_scoped_selection_path": normalized["scoped_selection_path"],
        "profile_scoped_selection_sha256": normalized["scoped_selection_sha256"],
        "preceding_stage": "scoped_research",
    }
    mismatched = [
        key for key, expected in required_queue.items() if queue_before.get(key) != expected
    ]
    if mismatched:
        raise DeepResearchCompletionError(
            "deep-research completion does not match the running claim "
            f"({', '.join(mismatched)}): {symbol}"
        )
    if screen_before.get("symbol") != symbol:
        raise DeepResearchCompletionError(f"screening symbol does not match claim: {symbol}")
    started_at = _parse_datetime(queue_before.get("started_at"), "queue.started_at")
    if started_at >= completed_at:
        raise DeepResearchCompletionError(
            f"deep-research completion must be later than its claim: {symbol}"
        )
    history = queue_before.get("stage_history")
    if history is not None and not isinstance(history, list):
        raise DeepResearchCompletionError(f"queue stage_history is invalid: {symbol}")
    completed_history = [
        item
        for item in (history or [])
        if isinstance(item, Mapping)
        and item.get("stage") == "deep_research"
        and item.get("status") == "completed"
    ]
    if completed_history:
        raise DeepResearchCompletionError(
            f"deep-research claim already contains completed history: {symbol}"
        )


def _manager_predecessor(
    queue_before: Mapping[str, Any],
    *,
    screen_before: Mapping[str, Any],
    base: Path,
    repository: Path,
    symbol: str,
    started_at: dt.datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = _identifier(
        queue_before.get("manager_screen_run_id"),
        "manager_screen_run_id",
    )
    full_market_required = _requires_funded_full_market_grant(
        queue_before
    ) or _sealed_full_market_funded_symbol(
        base=base,
        run_id=run_id,
        symbol=symbol,
    )
    if full_market_required:
        try:
            grant = _verify_funded_full_market_profile_grant(
                queue_record=queue_before,
                screen_record=screen_before,
                root=base,
                repository_root=repository,
                symbol=symbol,
                expected_cycle_id=queue_before.get("profile_cycle_id"),
                required=True,
                context="deep-research completion",
            )
        except (ResearchAllocationError, SealingError, ValueError) as exc:
            raise DeepResearchCompletionError(
                f"full-market predecessor is invalid: {symbol}: {exc}"
            ) from exc
        if grant is None:  # pragma: no cover - required=True is fail closed.
            raise DeepResearchCompletionError(f"full-market predecessor is missing: {symbol}")
        result_path = _repository_file(
            repository,
            grant["result_path"],
            "full-market result path",
        )
        try:
            result_seal = verify_sealed(result_path)
            result_payload = _read_object(
                result_path,
                "full-market allocation result",
            )
        except (OSError, SealingError, ValueError) as exc:
            raise DeepResearchCompletionError(
                f"full-market authority source is invalid: {symbol}"
            ) from exc
        if (
            result_seal.artifact_type != "manager_screen_full_market_allocation_v3_result"
            or result_seal.sha256 != grant["result_sha256"]
            or result_seal.sealed_at > started_at
        ):
            raise DeepResearchCompletionError(
                f"full-market allocation authority does not precede the deep claim: {symbol}"
            )
        decision = grant["decision"]
        authority = _effective_manager_authority(
            payload=result_payload,
            source_path=grant["result_path"],
            source_sha256=result_seal.sha256,
            source_type=result_seal.artifact_type,
            expected_run_id=run_id,
        )
        return (
            {
                "kind": "manager_screen_full_market_allocation_v3_result",
                "path": grant["result_path"],
                "sha256": grant["result_sha256"],
                "candidate_sha256": decision["candidate_sha256"],
                "decision": "fund_quick_profile",
            },
            authority,
        )

    relative = _relative_text(
        queue_before.get("manager_screen_result_path"),
        "manager_screen_result_path",
    )
    expected_sha256 = _sha256(
        queue_before.get("manager_screen_result_sha256"),
        "manager_screen_result_sha256",
    )
    path = _repository_file(repository, relative, "manager-screen result")
    try:
        sealed = verify_sealed(path)
        payload = _read_object(path, "manager-screen result")
    except (OSError, SealingError, ValueError) as exc:
        raise DeepResearchCompletionError(
            f"manager-screen predecessor is invalid: {symbol}"
        ) from exc
    allowed_types = {
        "manager_screen_result",
        "manager_screen_quote_impact_result",
        "manager_screen_legacy_transition_result",
    }
    if sealed.artifact_type not in allowed_types or sealed.sha256 != expected_sha256:
        raise DeepResearchCompletionError(
            f"manager-screen predecessor seal does not match the claim: {symbol}"
        )
    run_id = queue_before.get("manager_screen_run_id")
    batch_id = queue_before.get("manager_screen_batch_id")
    if (
        payload.get("run_id") not in {None, run_id}
        or (isinstance(batch_id, str) and payload.get("batch_id") not in {None, batch_id})
        or sealed.sealed_at > started_at
    ):
        raise DeepResearchCompletionError(
            f"manager-screen predecessor identity/time does not match the claim: {symbol}"
        )
    decisions = payload.get("decisions")
    matching = (
        [item for item in decisions if isinstance(item, Mapping) and item.get("symbol") == symbol]
        if isinstance(decisions, list)
        else []
    )
    if len(matching) != 1:
        raise DeepResearchCompletionError(
            f"manager-screen predecessor must contain one company decision: {symbol}"
        )
    decision = matching[0]
    if (
        decision.get("route") != queue_before.get("manager_screen_route")
        or decision.get("decisive_question") != queue_before.get("decisive_question")
        or list(decision.get("evidence_ids") or []) != list(queue_before.get("evidence_ids") or [])
    ):
        raise DeepResearchCompletionError(
            f"manager-screen predecessor decision does not match the claim: {symbol}"
        )
    if sealed.artifact_type == "manager_screen_quote_impact_result":
        _verify_quote_impact_predecessor(
            base=base,
            payload=payload,
            relative=relative,
            sha256=sealed.sha256,
        )
    elif sealed.artifact_type == "manager_screen_legacy_transition_result":
        _verify_legacy_predecessor(
            base=base,
            run_id=str(run_id),
            relative=relative,
            sha256=sealed.sha256,
        )
    authority = _effective_manager_authority(
        payload=payload,
        source_path=relative,
        source_sha256=sealed.sha256,
        source_type=sealed.artifact_type,
        expected_run_id=str(run_id),
    )
    return (
        {
            "kind": sealed.artifact_type,
            "path": relative,
            "sha256": sealed.sha256,
            "decision_sha256": hashlib.sha256(canonical_json_bytes(dict(decision))).hexdigest(),
            "route": decision.get("route"),
        },
        authority,
    )


def _effective_manager_authority(
    *,
    payload: Mapping[str, Any],
    source_path: str,
    source_sha256: str,
    source_type: str,
    expected_run_id: str,
) -> dict[str, str]:
    manager = payload.get("manager")
    if payload.get("run_id") != expected_run_id or not isinstance(manager, Mapping):
        raise DeepResearchCompletionError("effective manager authority source identity is invalid")
    return {
        "agent": _relative_text(manager.get("agent"), "manager.agent"),
        "source_path": _repository_relative(source_path, "manager authority source_path"),
        "source_sha256": _sha256(source_sha256, "manager authority source_sha256"),
        "source_type": _relative_text(source_type, "manager authority source_type"),
    }


def _sealed_full_market_funded_symbol(
    *,
    base: Path,
    run_id: str,
    symbol: str,
) -> bool:
    """Detect a sealed v3 grant even if its mutable queue fields were deleted."""

    result_path = (
        base
        / "manager-screen"
        / run_id
        / "governance"
        / "allocation-v3"
        / "full-market"
        / "result.json"
    )
    presence = (result_path.exists(), _seal_path(result_path).exists())
    if presence == (False, False):
        return False
    if presence[0] != presence[1]:
        raise DeepResearchCompletionError(
            f"full-market allocation result is only partially sealed: {run_id}"
        )
    from .manager_screen_full_market_allocation_v3 import (
        ManagerScreenFullMarketAllocationV3Error,
        verify_manager_screen_full_market_allocation_v3_result,
    )

    try:
        result = verify_manager_screen_full_market_allocation_v3_result(
            root=base,
            run_id=run_id,
        )
    except ManagerScreenFullMarketAllocationV3Error as exc:
        raise DeepResearchCompletionError(
            f"sealed full-market allocation is invalid: {run_id}"
        ) from exc
    decisions = result.get("decisions")
    matching = (
        [item for item in decisions if isinstance(item, Mapping) and item.get("symbol") == symbol]
        if isinstance(decisions, list)
        else []
    )
    if len(matching) > 1:
        raise DeepResearchCompletionError(
            f"full-market allocation duplicates the deep-research symbol: {symbol}"
        )
    return bool(matching and matching[0].get("decision") == "fund_quick_profile")


def _verify_quote_impact_predecessor(
    *,
    base: Path,
    payload: Mapping[str, Any],
    relative: str,
    sha256: str,
) -> None:
    from .manager_screen_quote_impact import (
        ManagerScreenQuoteImpactError,
        manager_screen_quote_impact_status,
    )

    try:
        status = manager_screen_quote_impact_status(
            root=base,
            run_id=_identifier(payload.get("run_id"), "quote-impact run_id"),
            batch_id=_identifier(payload.get("batch_id"), "quote-impact batch_id"),
            review_id=_identifier(payload.get("review_id"), "quote-impact review_id"),
        )
    except (ManagerScreenQuoteImpactError, ValueError) as exc:
        raise DeepResearchCompletionError(
            "manager-screen quote-impact predecessor chain is invalid"
        ) from exc
    if (
        status.get("state") != "recorded"
        or status.get("result_path") != relative
        or status.get("result_sha256") != sha256
    ):
        raise DeepResearchCompletionError(
            "manager-screen quote-impact predecessor does not match its verified chain"
        )


def _verify_legacy_predecessor(
    *,
    base: Path,
    run_id: str,
    relative: str,
    sha256: str,
) -> None:
    from .legacy_transition import LegacyTransitionError, legacy_transition_status

    try:
        status = legacy_transition_status(root=base, run_id=run_id)
    except (LegacyTransitionError, ValueError) as exc:
        raise DeepResearchCompletionError(
            "manager-screen legacy predecessor chain is invalid"
        ) from exc
    if (
        status.get("state") != "recorded"
        or status.get("result_path") != relative
        or status.get("result_sha256") != sha256
    ):
        raise DeepResearchCompletionError(
            "manager-screen legacy predecessor does not match its verified chain"
        )


def _formal_report_bindings(
    *,
    normalized: Mapping[str, Any],
    queue_before: Mapping[str, Any],
    repository: Path,
    selection_sealed_at: dt.datetime,
    started_at: dt.datetime,
    completed_at: dt.datetime,
    allow_later_company_reports: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    symbol = str(normalized["symbol"])
    company_dir = _company_dir(queue_before, repository=repository)
    try:
        meta = validate_company_dir(company_dir)
    except AssetValidationError as exc:
        raise DeepResearchCompletionError(
            f"company research asset is invalid: {symbol}: {exc}"
        ) from exc
    if meta["identity"]["symbol"] != symbol:
        raise DeepResearchCompletionError(
            f"company research identity does not match completion: {symbol}"
        )
    report_path = _repository_file(repository, normalized["report_path"], "report_path")
    try:
        report_relative_to_company = report_path.relative_to(company_dir.resolve()).as_posix()
    except ValueError as exc:
        raise DeepResearchCompletionError(
            f"deep-research report is outside its company directory: {symbol}"
        ) from exc
    history = meta["reports"]["history"]
    matches = [
        (index, item)
        for index, item in enumerate(history)
        if item.get("path") == report_relative_to_company
    ]
    if len(matches) != 1:
        raise DeepResearchCompletionError(
            f"deep-research report is not uniquely recorded in company history: {symbol}"
        )
    report_index, report_record = matches[0]
    if (
        (not allow_later_company_reports and report_index != len(history) - 1)
        or (
            not allow_later_company_reports
            and meta["reports"].get("latest") != report_relative_to_company
        )
        or report_record.get("report_type") != "initial_research"
        or report_record.get("sha256") != normalized["report_sha256"]
        or hashlib.sha256(report_path.read_bytes()).hexdigest() != normalized["report_sha256"]
    ):
        raise DeepResearchCompletionError(
            f"deep completion must bind the latest formal initial_research report: {symbol}"
        )
    prior_result_path = queue_before.get("result_path")
    prior_result_sha256 = queue_before.get("result_sha256")
    if normalized["report_path"] == prior_result_path or (
        isinstance(prior_result_sha256, str) and normalized["report_sha256"] == prior_result_sha256
    ):
        raise DeepResearchCompletionError(
            f"deep completion cannot reuse the pre-claim queue result: {symbol}"
        )
    front = _report_front(report_path, symbol=symbol)
    if (
        front.get("report_id") != report_record.get("report_id")
        or front.get("report_type") != "initial_research"
        or front.get("symbol") != symbol
        or front.get("as_of") != report_record.get("as_of")
        or front.get("agent_id") != normalized["research_agent"]
    ):
        raise DeepResearchCompletionError(
            f"deep-research report metadata does not match the claim/history: {symbol}"
        )
    report_as_of = _parse_date(front.get("as_of"), "report.as_of")
    information_cutoff = _parse_datetime(
        front.get("information_cutoff"),
        "report.information_cutoff",
    )
    lower_bound = max(selection_sealed_at, started_at)
    if (
        report_as_of < lower_bound.date()
        or report_as_of > completed_at.date()
        or information_cutoff < lower_bound
        or information_cutoff > completed_at
    ):
        raise DeepResearchCompletionError(
            f"deep-research report predates its selection/claim or postdates completion: {symbol}"
        )
    predecessor_reports = front.get("predecessor_reports")
    if not isinstance(predecessor_reports, list) or not all(
        isinstance(item, str) and item for item in predecessor_reports
    ):
        raise DeepResearchCompletionError(f"deep-research predecessor_reports is invalid: {symbol}")
    if report_index > 0:
        prior = history[report_index - 1]
        if (
            prior.get("path") == report_record.get("path")
            or prior.get("sha256") == report_record.get("sha256")
            or prior.get("report_id") not in predecessor_reports
        ):
            raise DeepResearchCompletionError(
                f"deep-research report does not bind its prior latest report: {symbol}"
            )
    if allow_later_company_reports and report_index < len(history) - 1:
        previous = report_record
        for later in history[report_index + 1 :]:
            later_path = _company_file(
                company_dir,
                later.get("path"),
                "later company report",
            )
            later_front = _report_front(later_path, symbol=symbol)
            later_predecessors = later_front.get("predecessor_reports")
            if (
                not isinstance(later_predecessors, list)
                or previous.get("report_id") not in later_predecessors
            ):
                raise DeepResearchCompletionError(
                    f"later company timeline does not descend from deep research: {symbol}"
                )
            previous = later

    sealed_artifacts = front.get("sealed_artifacts")
    if not isinstance(sealed_artifacts, list):
        raise DeepResearchCompletionError(
            f"deep-research report sealed_artifacts is invalid: {symbol}"
        )
    research_claims: list[tuple[Path, Any]] = []
    for raw_path in sealed_artifacts:
        if not isinstance(raw_path, str) or not raw_path:
            raise DeepResearchCompletionError(
                f"deep-research sealed artifact path is invalid: {symbol}"
            )
        artifact_path = _company_file(company_dir, raw_path, "sealed report artifact")
        try:
            sealed = verify_sealed(artifact_path)
        except (OSError, SealingError, ValueError) as exc:
            raise DeepResearchCompletionError(
                f"deep-research report artifact is not validly sealed: {symbol}"
            ) from exc
        if sealed.artifact_type == "research_claims":
            research_claims.append((artifact_path, sealed))
    if len(research_claims) != 1:
        raise DeepResearchCompletionError(
            f"deep-research report must bind exactly one research_claims artifact: {symbol}"
        )
    claims_path, claims_seal = research_claims[0]
    claims_relative = _relative(claims_path, repository)
    if (
        claims_relative != normalized["claims_path"]
        or claims_seal.sha256 != normalized["claims_sha256"]
        or claims_seal.sealed_at < lower_bound
        or claims_seal.sealed_at > completed_at
    ):
        raise DeepResearchCompletionError(
            f"research claims do not match the claim/report time window: {symbol}"
        )
    claims_payload = _read_object(claims_path, "research claims")
    if claims_payload.get("symbol") != symbol or claims_payload.get(
        "report_id"
    ) != report_record.get("report_id"):
        raise DeepResearchCompletionError(
            f"research claims identity does not match the report: {symbol}"
        )
    try:
        packet = build_claim_packet(
            claims_payload,
            review_id=f"deep-completion-{normalized['profile_cycle_id']}",
            packet_id=f"deep-completion-{normalized['profile_cycle_id']}-{symbol[3:]}",
            source_report_sha256=str(report_record["sha256"]),
            created_at=completed_at,
        )
    except (ClaimPacketError, ValueError) as exc:
        raise DeepResearchCompletionError(
            f"structured research claims/sources are invalid: {symbol}: {exc}"
        ) from exc
    source_manifest = _company_file(
        company_dir,
        _relative_text(front.get("source_manifest"), "report.source_manifest"),
        "source manifest",
    )
    report_binding = {
        "path": normalized["report_path"],
        "sha256": normalized["report_sha256"],
        "report_id": report_record["report_id"],
        "report_type": "initial_research",
        "as_of": report_record["as_of"],
        "information_cutoff": information_cutoff.isoformat(),
        "agent_id": normalized["research_agent"],
        "predecessor_reports": list(predecessor_reports),
        "source_manifest_path": _relative(source_manifest, repository),
        "source_manifest_sha256": hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
    }
    claims_binding = {
        "path": claims_relative,
        "sha256": claims_seal.sha256,
        "sealed_at": claims_seal.sealed_at.isoformat(),
        "report_id": report_record["report_id"],
        "source_ids": sorted(str(item["source_id"]) for item in packet["allowed_sources"]),
    }
    return report_binding, claims_binding


def _project_queue(
    receipt: Mapping[str, Any],
    *,
    receipt_path: str,
    receipt_sha256: str,
) -> dict[str, Any]:
    base_queue, _ = _projection_base(receipt)
    report = receipt["report"]
    claims = receipt["research_claims"]
    selection = receipt["selection"]
    claim_attempt = receipt["claim_attempt"]
    history = list(base_queue.get("stage_history") or [])
    history.append(
        {
            "stage": "deep_research",
            "status": "completed",
            "started_at": receipt["claim"]["started_at"],
            "finished_at": receipt["completed_at"],
            "agent": receipt["research_agent"],
            "result_path": report["path"],
            "result_sha256": report["sha256"],
            "claims_path": claims["path"],
            "claims_sha256": claims["sha256"],
            "selection_path": selection["path"],
            "selection_sha256": selection["sha256"],
            "claim_path": claim_attempt["path"],
            "claim_sha256": claim_attempt["sha256"],
            "claim_attempt_number": claim_attempt["attempt_number"],
            "completion_path": receipt_path,
            "completion_sha256": receipt_sha256,
            "manager_screen_run_id": receipt["manager_screen_run_id"],
            "profile_cycle_id": receipt["profile_cycle_id"],
            "next_stage": "underwriting_candidate",
        }
    )
    updated = dict(base_queue)
    updated.update(
        {
            "task_type": "deep_research",
            "status": "completed",
            "reason": "正式深研已完成，等待投资经理显式批准独立承保预算。",
            "assigned_agent": receipt["research_agent"],
            "started_at": receipt["claim"]["started_at"],
            "finished_at": receipt["completed_at"],
            "result_path": report["path"],
            "result_sha256": report["sha256"],
            "failure_reason": None,
            "next_action": "由投资经理跨公司比较后显式决定是否购买独立承保预算；不得自动进入承保。",
            "stage_history": history,
            "deep_research_completion_path": receipt_path,
            "deep_research_completion_sha256": receipt_sha256,
            "deep_research_claims_path": claims["path"],
            "deep_research_claims_sha256": claims["sha256"],
        }
    )
    return updated


def _project_screen(
    receipt: Mapping[str, Any],
    *,
    receipt_path: str,
    receipt_sha256: str,
) -> dict[str, Any]:
    _, base_screen = _projection_base(receipt)
    report = receipt["report"]
    claims = receipt["research_claims"]
    evidence = list(base_screen.get("evidence") or [])
    evidence.extend(
        [
            f"deep_research_report:{report['path']}",
            f"deep_research_report_sha256:{report['sha256']}",
            f"research_claims:{claims['path']}",
            f"research_claims_sha256:{claims['sha256']}",
            f"deep_research_completion:{receipt_path}",
            f"deep_research_completion_sha256:{receipt_sha256}",
        ]
    )
    updated = dict(base_screen)
    updated.update(
        {
            "decision": "deep_research",
            "reason": "正式深研与结构化 claims 已完成并封存，尚未购买独立承保预算。",
            "evidence": list(dict.fromkeys(evidence)),
            "next_action": "等待投资经理显式批准独立承保；不得由研究员自动升级。",
            "profile_cycle_id": receipt["profile_cycle_id"],
            "deep_research_completed_at": receipt["completed_at"],
            "deep_research_completion_path": receipt_path,
            "deep_research_completion_sha256": receipt_sha256,
        }
    )
    return updated


def _load_receipt(
    path: Path,
    *,
    base: Path,
    repository: Path,
) -> tuple[dict[str, Any], Any]:
    relative = _relative(path, repository)
    try:
        sealed = verify_sealed(path)
        receipt = _read_object(path, "deep-research completion")
    except (OSError, SealingError, ValueError) as exc:
        raise DeepResearchCompletionError(
            f"deep-research completion is not validly sealed: {relative}"
        ) from exc
    if sealed.artifact_type != ARTIFACT_TYPE:
        raise DeepResearchCompletionError(
            f"deep-research completion artifact type is invalid: {relative}"
        )
    _validate_receipt_shape(receipt)
    expected_path = _receipt_path(
        base=base,
        cycle=str(receipt["profile_cycle_id"]),
        symbol=str(receipt["symbol"]),
    ).resolve()
    if path.resolve() != expected_path:
        raise DeepResearchCompletionError(
            f"deep-research completion path is not canonical: {relative}"
        )
    return receipt, sealed


def _validate_receipt_shape(receipt: Mapping[str, Any]) -> None:
    if not isinstance(receipt, Mapping) or set(receipt) != RECEIPT_KEYS:
        raise DeepResearchCompletionError("deep-research completion fields do not match contract")
    if (
        receipt.get("schema_version") != 2
        or receipt.get("artifact_type") != ARTIFACT_TYPE
        or receipt.get("portfolio_action") is not None
    ):
        raise DeepResearchCompletionError("deep-research completion schema/type is invalid")
    _symbol(receipt.get("symbol"), "receipt.symbol")
    _relative_text(receipt.get("research_agent"), "receipt.research_agent")
    _identifier(receipt.get("profile_cycle_id"), "receipt.profile_cycle_id")
    _identifier(receipt.get("manager_screen_run_id"), "receipt.manager_screen_run_id")
    _parse_datetime(receipt.get("completed_at"), "receipt.completed_at")
    claim = _exact_mapping(receipt.get("claim"), CLAIM_KEYS, "receipt.claim")
    claim_attempt = _exact_mapping(
        receipt.get("claim_attempt"),
        CLAIM_ATTEMPT_KEYS,
        "receipt.claim_attempt",
    )
    claim_authorization = _exact_mapping(
        claim_attempt.get("stage_authorization"),
        CLAIM_ATTEMPT_AUTHORIZATION_KEYS,
        "receipt.claim_attempt.stage_authorization",
    )
    _repository_relative(claim_attempt.get("path"), "receipt.claim_attempt.path")
    _sha256(claim_attempt.get("sha256"), "receipt.claim_attempt.sha256")
    claim_sealed_at = _parse_datetime(
        claim_attempt.get("sealed_at"),
        "receipt.claim_attempt.sealed_at",
    )
    attempt_number = claim_attempt.get("attempt_number")
    if (
        not isinstance(attempt_number, int)
        or isinstance(attempt_number, bool)
        or attempt_number < 1
    ):
        raise DeepResearchCompletionError("deep-research claim attempt number is invalid")
    claim_agent = _relative_text(
        claim_attempt.get("agent"),
        "receipt.claim_attempt.agent",
    )
    _repository_relative(
        claim_authorization.get("path"),
        "receipt.claim_attempt.stage_authorization.path",
    )
    _sha256(
        claim_authorization.get("sha256"),
        "receipt.claim_attempt.stage_authorization.sha256",
    )
    if claim_authorization.get("artifact_type") != ("scoped_research_cross_company_selection"):
        raise DeepResearchCompletionError("deep-research claim authorization type is invalid")
    _parse_datetime(
        claim_authorization.get("sealed_at"),
        "receipt.claim_attempt.stage_authorization.sealed_at",
    )
    _exact_mapping(receipt.get("selection"), SELECTION_KEYS, "receipt.selection")
    _exact_mapping(receipt.get("report"), REPORT_KEYS, "receipt.report")
    _exact_mapping(receipt.get("research_claims"), CLAIMS_KEYS, "receipt.research_claims")
    projection = _exact_mapping(
        receipt.get("projection_base"),
        PROJECTION_BASE_KEYS,
        "receipt.projection_base",
    )
    if not isinstance(projection.get("research_queue"), Mapping) or not isinstance(
        projection.get("screening"), Mapping
    ):
        raise DeepResearchCompletionError("deep-research projection base rows must be objects")
    predecessor = receipt.get("manager_predecessor")
    if not isinstance(predecessor, Mapping) or not predecessor:
        raise DeepResearchCompletionError("deep-research manager predecessor is invalid")
    authority = _exact_mapping(
        receipt.get("effective_manager_authority"),
        EFFECTIVE_MANAGER_AUTHORITY_KEYS,
        "receipt.effective_manager_authority",
    )
    authority_agent = _relative_text(
        authority.get("agent"),
        "receipt.effective_manager_authority.agent",
    )
    _repository_relative(
        authority.get("source_path"),
        "receipt.effective_manager_authority.source_path",
    )
    _sha256(
        authority.get("source_sha256"),
        "receipt.effective_manager_authority.source_sha256",
    )
    if authority.get("source_type") not in EFFECTIVE_MANAGER_AUTHORITY_SOURCE_TYPES:
        raise DeepResearchCompletionError(
            "deep-research effective manager authority source type is invalid"
        )
    if (
        receipt.get("research_agent") != claim_agent
        or claim.get("assigned_agent") != claim_agent
        or claim.get("started_at") != claim_attempt.get("sealed_at")
        or claim_sealed_at > _parse_datetime(receipt.get("completed_at"), "completed_at")
        or authority_agent == claim_agent
    ):
        raise DeepResearchCompletionError(
            "deep-research receipt authority/claim relationship is invalid"
        )
    selection = receipt["selection"]
    if claim_authorization.get("path") != selection.get("path") or claim_authorization.get(
        "sha256"
    ) != selection.get("sha256"):
        raise DeepResearchCompletionError(
            "deep-research claim authorization does not match selection"
        )


def _submission_from_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return _normalize_submission(
        {
            "schema_version": 1,
            "symbol": receipt["symbol"],
            "research_agent": receipt["research_agent"],
            "profile_cycle_id": receipt["profile_cycle_id"],
            "manager_screen_run_id": receipt["manager_screen_run_id"],
            "scoped_selection_path": receipt["selection"]["path"],
            "scoped_selection_sha256": receipt["selection"]["sha256"],
            "report_path": receipt["report"]["path"],
            "report_sha256": receipt["report"]["sha256"],
            "claims_path": receipt["research_claims"]["path"],
            "claims_sha256": receipt["research_claims"]["sha256"],
        },
        expected_symbol=str(receipt["symbol"]),
    )


def _require_submission_matches_receipt(
    normalized: Mapping[str, Any], receipt: Mapping[str, Any]
) -> None:
    if dict(normalized) != _submission_from_receipt(receipt):
        raise DeepResearchCompletionError(
            "submission conflicts with the sealed deep-research receipt"
        )


def _normalize_submission(
    submission: Mapping[str, Any],
    *,
    expected_symbol: str,
) -> dict[str, Any]:
    if not isinstance(submission, Mapping) or set(submission) != SUBMISSION_KEYS:
        raise DeepResearchCompletionError(
            "deep-research completion submission fields do not match contract"
        )
    if submission.get("schema_version") != 1:
        raise DeepResearchCompletionError(
            "deep-research completion submission schema_version must be 1"
        )
    symbol = _symbol(submission.get("symbol"), "submission.symbol")
    if symbol != _symbol(expected_symbol, "symbol"):
        raise DeepResearchCompletionError("submission symbol does not match command symbol")
    return {
        "schema_version": 1,
        "symbol": symbol,
        "research_agent": _relative_text(submission.get("research_agent"), "research_agent"),
        "profile_cycle_id": _identifier(submission.get("profile_cycle_id"), "profile_cycle_id"),
        "manager_screen_run_id": _identifier(
            submission.get("manager_screen_run_id"), "manager_screen_run_id"
        ),
        "scoped_selection_path": _repository_relative(
            submission.get("scoped_selection_path"), "scoped_selection_path"
        ),
        "scoped_selection_sha256": _sha256(
            submission.get("scoped_selection_sha256"),
            "scoped_selection_sha256",
        ),
        "report_path": _repository_relative(submission.get("report_path"), "report_path"),
        "report_sha256": _sha256(submission.get("report_sha256"), "report_sha256"),
        "claims_path": _repository_relative(submission.get("claims_path"), "claims_path"),
        "claims_sha256": _sha256(submission.get("claims_sha256"), "claims_sha256"),
    }


def _projection_base(receipt: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    projection = receipt.get("projection_base")
    if not isinstance(projection, Mapping):
        raise DeepResearchCompletionError("deep-research projection base is invalid")
    queue = projection.get("research_queue")
    screen = projection.get("screening")
    if not isinstance(queue, Mapping) or not isinstance(screen, Mapping):
        raise DeepResearchCompletionError("deep-research projection base rows are invalid")
    return dict(queue), dict(screen)


def _projection_state(
    current: Mapping[str, Any],
    *,
    before: Mapping[str, Any],
    expected: Mapping[str, Any],
    label: str,
) -> str:
    if dict(current) == dict(expected):
        return "expected"
    if dict(current) == dict(before):
        return "before"
    raise DeepResearchCompletionError(f"deep-research {label} projection has unrecognized drift")


def _summary(
    receipt: Mapping[str, Any],
    *,
    receipt_path: str,
    receipt_sha256: str,
    idempotent: bool,
    queue_projected: bool,
    screening_projected: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "symbol": receipt["symbol"],
        "profile_cycle_id": receipt["profile_cycle_id"],
        "manager_screen_run_id": receipt["manager_screen_run_id"],
        "research_agent": receipt["research_agent"],
        "completed_at": receipt["completed_at"],
        "receipt_path": receipt_path,
        "receipt_sha256": receipt_sha256,
        "report_path": receipt["report"]["path"],
        "report_sha256": receipt["report"]["sha256"],
        "claims_path": receipt["research_claims"]["path"],
        "claims_sha256": receipt["research_claims"]["sha256"],
        "claim_attempt_path": receipt["claim_attempt"]["path"],
        "claim_attempt_sha256": receipt["claim_attempt"]["sha256"],
        "effective_manager_authority": dict(receipt["effective_manager_authority"]),
        "queue_projected": queue_projected,
        "screening_projected": screening_projected,
        "finalized": queue_projected and screening_projected,
        "idempotent": idempotent,
        "underwriting_budget_purchased": False,
        "portfolio_action": None,
    }


def _report_front(path: Path, *, symbol: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise DeepResearchCompletionError(f"deep-research report cannot be read: {symbol}") from exc
    match = REPORT_META_RE.match(text)
    if match is None:
        raise DeepResearchCompletionError(f"deep-research report metadata is missing: {symbol}")
    try:
        payload = json.loads(match.group("meta"))
    except json.JSONDecodeError as exc:
        raise DeepResearchCompletionError(
            f"deep-research report metadata is invalid: {symbol}"
        ) from exc
    if not isinstance(payload, dict):
        raise DeepResearchCompletionError(
            f"deep-research report metadata must be an object: {symbol}"
        )
    return payload


def _company_dir(record: Mapping[str, Any], *, repository: Path) -> Path:
    raw = _repository_relative(record.get("target_company_dir"), "target_company_dir")
    path = (repository / raw).resolve()
    try:
        path.relative_to(repository)
    except ValueError as exc:
        raise DeepResearchCompletionError("target company directory escapes repository") from exc
    if not path.is_dir():
        raise DeepResearchCompletionError(f"target company directory is missing: {raw}")
    return path


def _company_file(company_dir: Path, value: Any, label: str) -> Path:
    relative = _repository_relative(value, label)
    path = (company_dir / relative).resolve()
    try:
        path.relative_to(company_dir.resolve())
    except ValueError as exc:
        raise DeepResearchCompletionError(f"{label} escapes company directory") from exc
    if not path.is_file():
        raise DeepResearchCompletionError(f"{label} is missing: {relative}")
    return path


def _repository_file(repository: Path, value: Any, label: str) -> Path:
    relative = _repository_relative(value, label)
    path = (repository / relative).resolve()
    try:
        path.relative_to(repository.resolve())
    except ValueError as exc:
        raise DeepResearchCompletionError(f"{label} escapes repository") from exc
    if not path.is_file():
        raise DeepResearchCompletionError(f"{label} is missing: {relative}")
    return path


def _repository_relative(value: Any, label: str) -> str:
    text = _relative_text(value, label).replace("\\", "/")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or text.startswith("/"):
        raise DeepResearchCompletionError(f"{label} must be repository-relative")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise DeepResearchCompletionError(f"{label} must be repository-relative")
    return normalized


def _receipt_path(*, base: Path, cycle: str, symbol: str) -> Path:
    return (
        base
        / "profiles"
        / _identifier(cycle, "profile_cycle_id")
        / "deep-research-completions"
        / f"{_symbol(symbol, 'symbol').split(':', 1)[1]}.json"
    )


def _seal_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.seal.json")


def _replace_symbol(
    records: list[dict[str, Any]],
    symbol: str,
    replacement: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [dict(replacement) if item.get("symbol") == symbol else item for item in records]


def _one_record(records: list[dict[str, Any]], symbol: str, label: str) -> dict[str, Any]:
    matching = [item for item in records if item.get("symbol") == symbol]
    if len(matching) != 1:
        raise DeepResearchCompletionError(f"expected exactly one {label} row: {symbol}")
    return dict(matching[0])


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeepResearchCompletionError(f"{label} is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise DeepResearchCompletionError(f"{label} must be an object: {path}")
    return payload


def _exact_mapping(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise DeepResearchCompletionError(f"{label} fields do not match contract")
    return value


def _symbol(value: Any, label: str) -> str:
    text = _relative_text(value, label)
    if not SYMBOL_RE.fullmatch(text):
        raise DeepResearchCompletionError(f"{label} must match CN:000000")
    return text


def _identifier(value: Any, label: str) -> str:
    text = _relative_text(value, label)
    if not IDENTIFIER_RE.fullmatch(text):
        raise DeepResearchCompletionError(f"{label} is invalid")
    return text


def _sha256(value: Any, label: str) -> str:
    text = _relative_text(value, label)
    if not SHA256_RE.fullmatch(text):
        raise DeepResearchCompletionError(f"{label} must be lowercase SHA-256")
    return text


def _relative_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeepResearchCompletionError(f"{label} must be a non-empty string")
    return value.strip()


def _aware(value: dt.datetime, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DeepResearchCompletionError(f"{label} must include timezone information")
    return value


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    text = _relative_text(value, label)
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise DeepResearchCompletionError(f"{label} must be an ISO datetime") from exc
    return _aware(parsed, label)


def _parse_date(value: Any, label: str) -> dt.date:
    text = _relative_text(value, label)
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise DeepResearchCompletionError(f"{label} must be an ISO date") from exc


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise DeepResearchCompletionError(f"path escapes repository root: {path}") from exc
