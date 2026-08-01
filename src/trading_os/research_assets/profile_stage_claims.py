from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed


class ProfileStageClaimError(ValueError):
    """Raised when an append-only profile-stage claim chain is invalid."""


CLAIM_ARTIFACT_TYPE = "profile_stage_claim_attempt"
RELEASE_ARTIFACT_TYPE = "profile_stage_claim_release"
SUCCESS_ARTIFACT_TYPE = "profile_stage_claim_success"
WORKFLOW = "profile_stage_claim_attempts"
WORKFLOW_VERSION = 1
SUPPORTED_STAGES = {
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
}

CLAIM_BINDING_PATH_FIELD = "profile_stage_claim_attempt_path"
CLAIM_BINDING_SHA_FIELD = "profile_stage_claim_attempt_sha256"
RELEASE_BINDING_PATH_FIELD = "profile_stage_claim_release_path"
RELEASE_BINDING_SHA_FIELD = "profile_stage_claim_release_sha256"

_SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ATTEMPT_DIR_RE = re.compile(r"^attempt-([0-9]{6})$")

_CLAIM_KEYS = {
    "schema_version",
    "workflow",
    "workflow_version",
    "stage",
    "manager_screen_run_id",
    "profile_cycle_id",
    "symbol",
    "attempt_number",
    "agent",
    "claimed_at",
    "stage_authorization",
    "previous_release",
    "prior_queue_row",
    "prior_queue_row_sha256",
    "portfolio_action",
}
_RELEASE_KEYS = {
    "schema_version",
    "workflow",
    "workflow_version",
    "stage",
    "manager_screen_run_id",
    "profile_cycle_id",
    "symbol",
    "attempt_number",
    "agent",
    "released_at",
    "failure_reason",
    "claim_path",
    "claim_sha256",
    "prior_running_row",
    "prior_running_row_sha256",
    "portfolio_action",
}
_SUCCESS_KEYS = {
    "schema_version",
    "workflow",
    "workflow_version",
    "stage",
    "manager_screen_run_id",
    "profile_cycle_id",
    "symbol",
    "attempt_number",
    "agent",
    "succeeded_at",
    "claim_path",
    "claim_sha256",
    "profile_path",
    "profile_sha256",
    "evaluation_path",
    "evaluation_sha256",
    "portfolio_action",
}
_AUTHORIZATION_KEYS = {"path", "sha256", "artifact_type", "sealed_at"}
_CLAIM_BINDING_KEYS = {
    "path",
    "sha256",
    "sealed_at",
    "attempt_number",
    "agent",
    "stage_authorization",
}
_PREVIOUS_RELEASE_KEYS = {"path", "sha256"}
_DISPLAY_MUTABLE_QUEUE_FIELDS = {
    "reason",
    "next_action",
    "revisit_triggers",
}
_PROFILE_PACKAGE_KEYS = {
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
_MANAGER_BOUND_PROFILE_PACKAGE_KEYS = _PROFILE_PACKAGE_KEYS | {
    "manager_screen_binding",
    "decisive_answer",
}
_PROFILE_EVALUATION_KEYS = {
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
    "claim_attempt",
}
_PROFILE_EVALUATION_RESULT_KEYS = {
    "schema_version",
    "symbol",
    "as_of",
    "evaluated_stage",
    "next_stage",
    "maximum_additional_effort_hours",
    "reason_codes",
    "base_expected_annual_return",
    "underwriting_return_threshold",
    "revisit_triggers",
    "portfolio_action",
}
_PROFILE_RESEARCH_STAGES = {"targeted_followup", "scoped_research", "deep_research"}


def claim_profile_stage_attempt(
    *,
    root: str | Path,
    queue_record: Mapping[str, Any],
    agent: str,
    claimed_at: dt.datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Seal a deep-stage claim before returning its deterministic queue projection."""

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    timestamp = _aware(claimed_at, "claimed_at")
    agent_name = _text(agent, "agent")
    stage = _stage(queue_record.get("task_type"))
    chain = _load_chain(base=base, repository=repository, queue_record=queue_record, stage=stage)

    if chain:
        last = chain[-1]
        claim = last["claim"]
        release = last["release"]
        if release is None:
            if claim["agent"] != agent_name:
                raise ProfileStageClaimError(
                    "the active sealed stage claim belongs to another agent"
                )
            if timestamp < _parse_datetime(claim["claimed_at"], "claim.claimed_at"):
                raise ProfileStageClaimError("claim replay timestamp predates the sealed attempt")
            if _matches_pending_projection(
                queue_record,
                claim=claim,
                repository=repository,
            ):
                repaired = _running_projection(
                    claim,
                    claim_path=last["claim_relative"],
                    claim_sha256=last["claim_sha256"],
                    base_row=queue_record,
                )
                return repaired, _claim_summary(last, idempotent=True, repaired=True)
            if _matches_running_projection(
                queue_record,
                claim=claim,
                claim_path=last["claim_relative"],
                claim_sha256=last["claim_sha256"],
                repository=repository,
            ):
                return dict(queue_record), _claim_summary(
                    last,
                    idempotent=True,
                    repaired=False,
                )
            raise ProfileStageClaimError(
                "active sealed stage claim matches neither its prior nor running projection"
            )

        if not _matches_released_projection(
            queue_record,
            claim=last["claim"],
            release=release,
            claim_path=last["claim_relative"],
            claim_sha256=last["claim_sha256"],
            release_path=last["release_relative"],
            release_sha256=last["release_sha256"],
            repository=repository,
        ):
            raise ProfileStageClaimError(
                "latest sealed stage release is not materialized before retry"
            )

    _validate_pending_prior(queue_record, stage=stage)
    authorization = _stage_authorization(
        queue_record,
        repository=repository,
        stage=stage,
    )
    attempt_number = len(chain) + 1
    previous_release = None
    previous_release_at = None
    if chain:
        latest = chain[-1]
        previous_release = {
            "path": latest["release_relative"],
            "sha256": latest["release_sha256"],
        }
        previous_release_at = _parse_datetime(
            latest["release"]["released_at"],
            "previous release.released_at",
        )
    if timestamp < _parse_datetime(authorization["sealed_at"], "authorization.sealed_at"):
        raise ProfileStageClaimError("claim timestamp predates its sealed stage authorization")
    if previous_release_at is not None and timestamp <= previous_release_at:
        raise ProfileStageClaimError("retry claim must be later than the prior sealed release")

    claim_path = (
        _attempt_dir(
            base=base,
            queue_record=queue_record,
            stage=stage,
            attempt_number=attempt_number,
        )
        / "claim.json"
    )
    _require_pair_or_absent(claim_path, "stage claim")
    if claim_path.exists():  # pragma: no cover - the chain loader must include it.
        raise ProfileStageClaimError("stage claim chain contains an unindexed attempt")
    payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "workflow_version": WORKFLOW_VERSION,
        "stage": stage,
        "manager_screen_run_id": _stage_run_id(
            queue_record.get("manager_screen_run_id"),
            stage=stage,
        ),
        "profile_cycle_id": _identifier(
            queue_record.get("profile_cycle_id"),
            "profile_cycle_id",
        ),
        "symbol": _symbol(queue_record.get("symbol")),
        "attempt_number": attempt_number,
        "agent": agent_name,
        "claimed_at": timestamp.isoformat(),
        "stage_authorization": authorization,
        "previous_release": previous_release,
        "prior_queue_row": dict(queue_record),
        "prior_queue_row_sha256": _payload_sha256(queue_record),
        "portfolio_action": None,
    }
    _validate_claim_payload(payload)
    try:
        sealed = seal_json(
            claim_path,
            payload,
            artifact_type=CLAIM_ARTIFACT_TYPE,
            sealed_at=timestamp,
        )
    except (OSError, SealingError) as exc:
        raise ProfileStageClaimError("stage claim attempt could not be sealed") from exc
    relative = _relative(claim_path, repository)
    entry = {
        "claim": payload,
        "claim_path": claim_path,
        "claim_relative": relative,
        "claim_sha256": sealed.sha256,
        "release": None,
        "release_path": claim_path.with_name("release.json"),
        "release_relative": None,
        "release_sha256": None,
    }
    return (
        _running_projection(
            payload,
            claim_path=relative,
            claim_sha256=sealed.sha256,
        ),
        _claim_summary(entry, idempotent=False, repaired=False),
    )


def release_profile_stage_attempt(
    *,
    root: str | Path,
    queue_record: Mapping[str, Any],
    agent: str,
    failure_reason: str,
    released_at: dt.datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Seal the terminal event for the current deep-stage claim before projection."""

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    timestamp = _aware(released_at, "released_at")
    agent_name = _text(agent, "agent")
    reason = _text(failure_reason, "failure_reason")
    stage = _stage(queue_record.get("task_type"))
    chain = _load_chain(base=base, repository=repository, queue_record=queue_record, stage=stage)
    if not chain:
        raise ProfileStageClaimError("profile stage has no sealed claim attempt to release")
    latest = chain[-1]
    claim = latest["claim"]
    if claim["agent"] != agent_name:
        raise ProfileStageClaimError("only the sealed claim agent can release the task")
    success_path = latest["claim_path"].with_name("success.json")
    _require_pair_or_absent(success_path, "profile stage success")
    if success_path.exists():
        raise ProfileStageClaimError(
            "sealed profile success must be replayed and cannot be released as failure"
        )
    release = latest["release"]
    if release is not None:
        if release["agent"] != agent_name or release["failure_reason"] != reason:
            raise ProfileStageClaimError("sealed stage release conflicts with replay")
        expected = _released_projection(
            claim,
            release,
            claim_path=latest["claim_relative"],
            claim_sha256=latest["claim_sha256"],
            release_path=latest["release_relative"],
            release_sha256=latest["release_sha256"],
        )
        if _matches_running_projection(
            queue_record,
            claim=claim,
            claim_path=latest["claim_relative"],
            claim_sha256=latest["claim_sha256"],
            repository=repository,
        ):
            return expected, _release_summary(latest, idempotent=True, repaired=True)
        if _matches_released_projection(
            queue_record,
            claim=claim,
            release=release,
            claim_path=latest["claim_relative"],
            claim_sha256=latest["claim_sha256"],
            release_path=latest["release_relative"],
            release_sha256=latest["release_sha256"],
            repository=repository,
        ):
            return dict(queue_record), _release_summary(
                latest,
                idempotent=True,
                repaired=False,
            )
        raise ProfileStageClaimError(
            "sealed stage release matches neither running nor released projection"
        )

    if not _matches_running_projection(
        queue_record,
        claim=claim,
        claim_path=latest["claim_relative"],
        claim_sha256=latest["claim_sha256"],
        repository=repository,
    ):
        raise ProfileStageClaimError("live queue does not match the active sealed stage claim")
    if timestamp <= _parse_datetime(claim["claimed_at"], "claim.claimed_at"):
        raise ProfileStageClaimError("release must be later than the sealed claim")
    release_path = latest["release_path"]
    _require_pair_or_absent(release_path, "stage claim release")
    payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "workflow_version": WORKFLOW_VERSION,
        "stage": stage,
        "manager_screen_run_id": claim["manager_screen_run_id"],
        "profile_cycle_id": claim["profile_cycle_id"],
        "symbol": claim["symbol"],
        "attempt_number": claim["attempt_number"],
        "agent": agent_name,
        "released_at": timestamp.isoformat(),
        "failure_reason": reason,
        "claim_path": latest["claim_relative"],
        "claim_sha256": latest["claim_sha256"],
        "prior_running_row": dict(queue_record),
        "prior_running_row_sha256": _payload_sha256(queue_record),
        "portfolio_action": None,
    }
    _validate_release_payload(payload)
    try:
        sealed = seal_json(
            release_path,
            payload,
            artifact_type=RELEASE_ARTIFACT_TYPE,
            sealed_at=timestamp,
        )
    except (OSError, SealingError) as exc:
        raise ProfileStageClaimError("stage claim release could not be sealed") from exc
    latest = {
        **latest,
        "release": payload,
        "release_relative": _relative(release_path, repository),
        "release_sha256": sealed.sha256,
    }
    return (
        _released_projection(
            claim,
            payload,
            claim_path=latest["claim_relative"],
            claim_sha256=latest["claim_sha256"],
            release_path=latest["release_relative"],
            release_sha256=sealed.sha256,
        ),
        _release_summary(latest, idempotent=False, repaired=False),
    )


def seal_profile_stage_success(
    *,
    root: str | Path,
    queue_record: Mapping[str, Any],
    agent: str,
    profile_path: str,
    profile_sha256: str,
    evaluation_path: str,
    evaluation_sha256: str,
    succeeded_at: dt.datetime,
) -> dict[str, Any]:
    """Seal the formal terminal receipt for one non-deep profile-stage attempt.

    The profile and evaluation seals are necessary evidence, but they are not
    by themselves proof that the formal workflow accepted the active claim.
    This canonical receipt is written after both complete artifacts and before
    their mutable queue/screening projection.
    """

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    timestamp = _aware(succeeded_at, "succeeded_at")
    agent_name = _text(agent, "agent")
    stage = _stage(queue_record.get("task_type"))
    if stage == "deep_research":
        raise ProfileStageClaimError(
            "deep research uses its dedicated sealed completion receipt"
        )
    chain = _load_chain(
        base=base,
        repository=repository,
        queue_record=queue_record,
        stage=stage,
    )
    if not chain or chain[-1]["release"] is not None:
        raise ProfileStageClaimError("profile stage has no active sealed claim to complete")
    latest = chain[-1]
    claim = latest["claim"]
    if claim["agent"] != agent_name:
        raise ProfileStageClaimError("profile success agent does not own the sealed claim")
    if not _matches_running_projection(
        queue_record,
        claim=claim,
        claim_path=latest["claim_relative"],
        claim_sha256=latest["claim_sha256"],
        repository=repository,
    ):
        raise ProfileStageClaimError(
            "profile success queue does not match the active sealed claim"
        )
    if timestamp <= _parse_datetime(claim["claimed_at"], "claim.claimed_at"):
        raise ProfileStageClaimError("profile success must be later than its sealed claim")

    payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "workflow_version": WORKFLOW_VERSION,
        "stage": stage,
        "manager_screen_run_id": claim["manager_screen_run_id"],
        "profile_cycle_id": claim["profile_cycle_id"],
        "symbol": claim["symbol"],
        "attempt_number": claim["attempt_number"],
        "agent": agent_name,
        "succeeded_at": timestamp.isoformat(),
        "claim_path": latest["claim_relative"],
        "claim_sha256": latest["claim_sha256"],
        "profile_path": _relative_text(profile_path, "profile_path"),
        "profile_sha256": _sha256(profile_sha256, "profile_sha256"),
        "evaluation_path": _relative_text(evaluation_path, "evaluation_path"),
        "evaluation_sha256": _sha256(evaluation_sha256, "evaluation_sha256"),
        "portfolio_action": None,
    }
    _validate_success_payload(payload)
    _validate_profile_success_artifacts(
        payload,
        claim=claim,
        claim_relative=latest["claim_relative"],
        claim_sha256=latest["claim_sha256"],
        repository=repository,
    )
    success_path = latest["claim_path"].with_name("success.json")
    _require_pair_or_absent(success_path, "profile stage success")
    if success_path.exists():
        existing, sealed = _sealed_object(success_path, SUCCESS_ARTIFACT_TYPE)
        _validate_success_payload(existing)
        if existing != payload or sealed.sealed_at != timestamp:
            raise ProfileStageClaimError("sealed profile stage success conflicts with replay")
        return {
            "path": _relative(success_path, repository),
            "sha256": sealed.sha256,
            "sealed_at": timestamp.isoformat(),
            "idempotent": True,
        }
    try:
        sealed = seal_json(
            success_path,
            payload,
            artifact_type=SUCCESS_ARTIFACT_TYPE,
            sealed_at=timestamp,
        )
    except (OSError, SealingError) as exc:
        raise ProfileStageClaimError("profile stage success could not be sealed") from exc
    return {
        "path": _relative(success_path, repository),
        "sha256": sealed.sha256,
        "sealed_at": timestamp.isoformat(),
        "idempotent": False,
    }


def verify_profile_stage_success(
    *,
    root: str | Path,
    claim_attempt: Mapping[str, Any],
    history_event: Mapping[str, Any],
) -> dict[str, Any]:
    """Revalidate a completed history row against its canonical success receipt."""

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    if not isinstance(claim_attempt, Mapping) or set(claim_attempt) != _CLAIM_BINDING_KEYS:
        raise ProfileStageClaimError("profile success claim binding fields are invalid")
    claim_relative = _relative_text(claim_attempt.get("path"), "claim_attempt.path")
    claim_sha256 = _sha256(claim_attempt.get("sha256"), "claim_attempt.sha256")
    claim_path = (repository / claim_relative).resolve()
    try:
        claim_path.relative_to(repository)
        claim, claim_seal = _sealed_object(claim_path, CLAIM_ARTIFACT_TYPE)
    except (OSError, SealingError, ValueError) as exc:
        raise ProfileStageClaimError("profile success claim is not validly sealed") from exc
    _validate_claim_payload(claim)
    expected_binding = {
        "path": claim_relative,
        "sha256": claim_seal.sha256,
        "sealed_at": claim["claimed_at"],
        "attempt_number": claim["attempt_number"],
        "agent": claim["agent"],
        "stage_authorization": dict(claim["stage_authorization"]),
    }
    expected_claim_path = (
        _attempts_root(
            base=base,
            queue_record=claim["prior_queue_row"],
            stage=claim["stage"],
        )
        / f"attempt-{claim['attempt_number']:06d}"
        / "claim.json"
    ).resolve()
    if (
        dict(claim_attempt) != expected_binding
        or claim_sha256 != claim_seal.sha256
        or claim_path != expected_claim_path
        or claim_seal.sealed_at
        != _parse_datetime(claim["claimed_at"], "claim.claimed_at")
    ):
        raise ProfileStageClaimError("profile success claim binding is invalid")
    if not isinstance(history_event, Mapping) or not _sealed_success_closes_claim(
        {"stage_history": [history_event]},
        base=base,
        claim=claim,
        claim_relative=claim_relative,
        claim_sha256=claim_sha256,
        repository=repository,
    ):
        raise ProfileStageClaimError("profile success receipt/history binding is invalid")
    success_relative = _relative_text(
        history_event.get("success_path"),
        "profile success_path",
    )
    success_path = (repository / success_relative).resolve()
    sealed = verify_sealed(success_path)
    return {
        "path": success_relative,
        "sha256": sealed.sha256,
        "sealed_at": sealed.sealed_at.isoformat(),
    }


def verify_active_profile_stage_claim(
    *,
    root: str | Path,
    queue_record: Mapping[str, Any],
    stage: str,
) -> dict[str, Any]:
    """Authenticate the unique unreleased attempt and its exact running projection."""

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    normalized_stage = _stage(stage)
    chain = _load_chain(
        base=base,
        repository=repository,
        queue_record=queue_record,
        stage=normalized_stage,
    )
    if not chain or chain[-1]["release"] is not None:
        raise ProfileStageClaimError("deep stage has no active sealed claim attempt")
    latest = chain[-1]
    if not _matches_running_projection(
        queue_record,
        claim=latest["claim"],
        claim_path=latest["claim_relative"],
        claim_sha256=latest["claim_sha256"],
        repository=repository,
    ):
        raise ProfileStageClaimError(
            "running queue projection does not match the active sealed claim attempt"
        )
    return {
        "path": latest["claim_relative"],
        "sha256": latest["claim_sha256"],
        "sealed_at": latest["claim"]["claimed_at"],
        "attempt_number": latest["claim"]["attempt_number"],
        "agent": latest["claim"]["agent"],
        "stage_authorization": dict(latest["claim"]["stage_authorization"]),
    }


def profile_stage_claim_reservation_agent(
    *,
    root: str | Path,
    queue_record: Mapping[str, Any],
) -> str | None:
    """Return the agent durably reserved by a receipt-only claim crash."""

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    stage = _stage(queue_record.get("task_type"))
    chain = _load_chain(
        base=base,
        repository=repository,
        queue_record=queue_record,
        stage=stage,
    )
    if not chain or chain[-1]["release"] is not None:
        return None
    latest = chain[-1]
    if not _matches_pending_projection(
        queue_record,
        claim=latest["claim"],
        repository=repository,
    ) and not _matches_running_projection(
        queue_record,
        claim=latest["claim"],
        claim_path=latest["claim_relative"],
        claim_sha256=latest["claim_sha256"],
        repository=repository,
    ):
        raise ProfileStageClaimError("sealed stage claim reservation has unrecognized queue drift")
    return str(latest["claim"]["agent"])


def assert_agent_profile_stage_claim_capacity(
    *,
    root: str | Path,
    queue_records: list[Mapping[str, Any]],
    agent: str,
    requested_symbol: str | None,
) -> str | None:
    """Conserve one-task-per-agent from seals even when JSONL was tampered."""

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    agent_name = _text(agent, "agent")
    requested = _symbol(requested_symbol) if requested_symbol is not None else None
    rows: dict[str, Mapping[str, Any]] = {}
    for row in queue_records:
        symbol = row.get("symbol")
        if isinstance(symbol, str) and _SYMBOL_RE.fullmatch(symbol):
            if symbol in rows:
                raise ProfileStageClaimError(
                    f"research queue contains duplicate symbol during claim audit: {symbol}"
                )
            rows[symbol] = row

    active_for_agent: list[str] = []
    for chain in _all_stage_claim_chains(base=base, repository=repository):
        latest = chain[-1]
        if latest["release"] is not None:
            continue
        claim = latest["claim"]
        symbol = str(claim["symbol"])
        row = rows.get(symbol)
        if row is None:
            raise ProfileStageClaimError(
                f"sealed active stage claim lost its research queue row: {symbol}"
            )
        if _matches_pending_projection(
            row,
            claim=claim,
            repository=repository,
        ) or _matches_running_projection(
            row,
            claim=claim,
            claim_path=latest["claim_relative"],
            claim_sha256=latest["claim_sha256"],
            repository=repository,
        ):
            is_active = True
        elif _sealed_success_closes_claim(
            row,
            base=base,
            claim=claim,
            claim_relative=latest["claim_relative"],
            claim_sha256=latest["claim_sha256"],
            repository=repository,
        ):
            is_active = False
        else:
            raise ProfileStageClaimError(
                f"sealed active stage claim has unrecognized queue drift: {symbol}"
            )
        if is_active and claim["agent"] == agent_name:
            active_for_agent.append(symbol)
    if len(active_for_agent) > 1:
        raise ProfileStageClaimError(f"agent has multiple sealed active stage claims: {agent_name}")
    if requested is not None and active_for_agent and active_for_agent[0] != requested:
        raise ProfileStageClaimError(
            f"agent already has a different sealed active task: {active_for_agent[0]}"
        )
    return active_for_agent[0] if active_for_agent else None


def sealed_profile_stage_claim_authority_exists(
    *,
    root: str | Path,
    symbol: str,
    stage: str,
) -> bool:
    """Detect a validated claim chain without trusting mutable queue identity fields."""

    base = Path(root).resolve()
    repository = base.parent.parent.resolve()
    expected_symbol = _symbol(symbol)
    expected_stage = _stage(stage)
    return any(
        chain[-1]["claim"]["symbol"] == expected_symbol
        and chain[-1]["claim"]["stage"] == expected_stage
        for chain in _all_stage_claim_chains(base=base, repository=repository)
    )


def _all_stage_claim_chains(
    *,
    base: Path,
    repository: Path,
) -> list[list[dict[str, Any]]]:
    profiles = base / "profiles"
    if not profiles.is_dir():
        return []
    chains: list[list[dict[str, Any]]] = []
    roots = sorted(profiles.glob("*/stage-claim-attempts/*/*"))
    for attempts_root in roots:
        if not attempts_root.is_dir():
            continue
        stage = _stage(attempts_root.parent.name)
        attempt_dirs = sorted(path for path in attempts_root.iterdir() if path.is_dir())
        if not attempt_dirs:
            continue
        last_claim_path = attempt_dirs[-1] / "claim.json"
        _require_pair_complete(last_claim_path, "stage claim")
        last_claim, _ = _sealed_object(last_claim_path, CLAIM_ARTIFACT_TYPE)
        _validate_claim_payload(last_claim)
        pseudo_row = {
            "task_type": stage,
            "symbol": last_claim["symbol"],
            "profile_cycle_id": last_claim["profile_cycle_id"],
            "manager_screen_run_id": last_claim["manager_screen_run_id"],
        }
        chain = _load_chain(
            base=base,
            repository=repository,
            queue_record=pseudo_row,
            stage=stage,
        )
        if chain:
            chains.append(chain)
    return chains


def _sealed_success_closes_claim(
    row: Mapping[str, Any],
    *,
    base: Path,
    claim: Mapping[str, Any],
    claim_relative: str,
    claim_sha256: str,
    repository: Path,
) -> bool:
    history = row.get("stage_history")
    if not isinstance(history, list):
        return False
    events = [
        event
        for event in history
        if isinstance(event, Mapping)
        and event.get("stage") == claim["stage"]
        and event.get("status") == "completed"
        and event.get("agent") == claim["agent"]
        and event.get("started_at") == claim["claimed_at"]
        and event.get("claim_path") == claim_relative
        and event.get("claim_sha256") == claim_sha256
        and event.get("claim_attempt_number") == claim["attempt_number"]
    ]
    if len(events) != 1:
        return False
    event = events[0]
    expected_claim_binding = {
        "path": claim_relative,
        "sha256": claim_sha256,
        "sealed_at": claim["claimed_at"],
        "attempt_number": claim["attempt_number"],
        "agent": claim["agent"],
        "stage_authorization": dict(claim["stage_authorization"]),
    }
    claim_time = _parse_datetime(claim["claimed_at"], "claim.claimed_at")
    try:
        if claim["stage"] == "deep_research":
            completion_relative = _relative_text(
                event.get("completion_path"),
                "completion_path",
            )
            completion_sha256 = _sha256(
                event.get("completion_sha256"),
                "completion_sha256",
            )
            completion_path = (repository / completion_relative).resolve()
            completion_path.relative_to(repository)
            sealed = verify_sealed(completion_path)
            payload = json.loads(completion_path.read_text(encoding="utf-8"))
            claim_binding = payload.get("claim_attempt") if isinstance(payload, Mapping) else None
            from .deep_research_completion import deep_research_completion_status

            status = deep_research_completion_status(
                root=base,
                symbol=str(claim["symbol"]),
            )
            return bool(
                sealed.artifact_type == "deep_research_completion"
                and sealed.sha256 == completion_sha256
                and event.get("completion_sha256") == sealed.sha256
                and claim_binding == expected_claim_binding
                and payload.get("symbol") == claim["symbol"]
                and payload.get("research_agent") == claim["agent"]
                and _parse_datetime(payload.get("completed_at"), "completed_at") > claim_time
                and status.get("finalized") is True
                and status.get("receipt_path") == completion_relative
                and status.get("receipt_sha256") == completion_sha256
                and status.get("claim_attempt_path") == claim_relative
                and status.get("claim_attempt_sha256") == claim_sha256
                and status.get("research_agent") == claim["agent"]
            )

        success_relative = _relative_text(
            event.get("success_path"),
            "profile success_path",
        )
        success_sha256 = _sha256(
            event.get("success_sha256"),
            "profile success_sha256",
        )
        success_path = (repository / success_relative).resolve()
        success_path.relative_to(repository)
        expected_success_path = (
            (repository / claim_relative).resolve().with_name("success.json")
        )
        if success_path != expected_success_path:
            return False
        success_seal = verify_sealed(success_path)
        success = json.loads(success_path.read_text(encoding="utf-8"))
        _validate_success_payload(success)
        if (
            success_seal.artifact_type != SUCCESS_ARTIFACT_TYPE
            or success_seal.sha256 != success_sha256
            or success_seal.sealed_at
            != _parse_datetime(success["succeeded_at"], "success.succeeded_at")
            or success["stage"] != claim["stage"]
            or success["manager_screen_run_id"] != claim["manager_screen_run_id"]
            or success["profile_cycle_id"] != claim["profile_cycle_id"]
            or success["symbol"] != claim["symbol"]
            or success["attempt_number"] != claim["attempt_number"]
            or success["agent"] != claim["agent"]
            or success["claim_path"] != claim_relative
            or success["claim_sha256"] != claim_sha256
            or success["profile_path"] != event.get("result_path")
            or success["profile_sha256"] != event.get("result_sha256")
            or success["evaluation_path"] != event.get("evaluation_path")
            or success["evaluation_sha256"] != event.get("evaluation_sha256")
            or success["succeeded_at"] != event.get("finished_at")
            or success_seal.sealed_at <= claim_time
        ):
            return False
        _validate_profile_success_artifacts(
            success,
            claim=claim,
            claim_relative=claim_relative,
            claim_sha256=claim_sha256,
            repository=repository,
        )
        return True
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        SealingError,
        ValueError,
    ):
        return False


def _validate_success_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != _SUCCESS_KEYS:
        raise ProfileStageClaimError("profile stage success fields do not match contract")
    if (
        value.get("schema_version") != 1
        or value.get("workflow") != WORKFLOW
        or value.get("workflow_version") != WORKFLOW_VERSION
        or value.get("portfolio_action") is not None
    ):
        raise ProfileStageClaimError("profile stage success schema/workflow is invalid")
    stage = _stage(value.get("stage"))
    if stage == "deep_research":
        raise ProfileStageClaimError("deep research cannot use a profile success receipt")
    _stage_run_id(value.get("manager_screen_run_id"), stage=stage)
    _identifier(value.get("profile_cycle_id"), "profile_cycle_id")
    _symbol(value.get("symbol"))
    _positive_int(value.get("attempt_number"), "attempt_number")
    _text(value.get("agent"), "agent")
    _parse_datetime(value.get("succeeded_at"), "succeeded_at")
    _relative_text(value.get("claim_path"), "claim_path")
    _sha256(value.get("claim_sha256"), "claim_sha256")
    _relative_text(value.get("profile_path"), "profile_path")
    _sha256(value.get("profile_sha256"), "profile_sha256")
    _relative_text(value.get("evaluation_path"), "evaluation_path")
    _sha256(value.get("evaluation_sha256"), "evaluation_sha256")


def _validate_profile_success_artifacts(
    success: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    claim_relative: str,
    claim_sha256: str,
    repository: Path,
) -> None:
    expected_claim_binding = {
        "path": claim_relative,
        "sha256": claim_sha256,
        "sealed_at": claim["claimed_at"],
        "attempt_number": claim["attempt_number"],
        "agent": claim["agent"],
        "stage_authorization": dict(claim["stage_authorization"]),
    }
    profile_path = (repository / success["profile_path"]).resolve()
    evaluation_path = (repository / success["evaluation_path"]).resolve()
    try:
        profile_path.relative_to(repository)
        evaluation_path.relative_to(repository)
        profile_seal = verify_sealed(profile_path)
        evaluation_seal = verify_sealed(evaluation_path)
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError, ValueError) as exc:
        raise ProfileStageClaimError("profile success artifacts are not validly sealed") from exc
    succeeded_at = _parse_datetime(success["succeeded_at"], "success.succeeded_at")
    if (
        profile_seal.artifact_type != "quick_profile_package"
        or evaluation_seal.artifact_type != "quick_profile_evaluation"
        or profile_seal.sha256 != success["profile_sha256"]
        or evaluation_seal.sha256 != success["evaluation_sha256"]
        or profile_seal.sealed_at != succeeded_at
        or evaluation_seal.sealed_at != succeeded_at
        or not isinstance(profile, Mapping)
        or frozenset(profile)
        not in {
            frozenset(_PROFILE_PACKAGE_KEYS | {"claim_attempt"}),
            frozenset(_MANAGER_BOUND_PROFILE_PACKAGE_KEYS | {"claim_attempt"}),
        }
        or profile.get("schema_version") != 3
        or profile.get("claim_attempt") != expected_claim_binding
        or not isinstance(evaluation, Mapping)
        or set(evaluation) != _PROFILE_EVALUATION_KEYS
        or evaluation.get("schema_version") != 3
        or evaluation.get("claim_attempt") != expected_claim_binding
    ):
        raise ProfileStageClaimError("profile success artifact contract is invalid")

    profile_contract = dict(profile)
    profile_contract.pop("claim_attempt")
    profile_contract["schema_version"] = 2
    try:
        # Runtime import avoids a module-import cycle while reusing the exact
        # formal package validator that accepted the sealed profile.
        from .profile_workflow import _validate_package

        normalized = _validate_package(profile_contract, recorded_at=succeeded_at)
    except (ImportError, ValueError) as exc:
        raise ProfileStageClaimError("profile success package is not formally valid") from exc
    if normalized != profile_contract:
        raise ProfileStageClaimError("profile success package normalization drifted")
    _validate_profile_manager_contract(normalized, claim=claim)

    profile_body = normalized.get("profile")
    provenance = normalized.get("provenance")
    evaluated = evaluation.get("evaluation")
    if (
        not isinstance(profile_body, Mapping)
        or set(profile_body)
        != {
            "research_stage",
            "symbol",
            "as_of",
            "information_cutoff",
            "s1_source_count",
            "circle_of_competence",
            "business_model_understood",
            "survival_status",
            "governance_status",
            "normalized_earnings_status",
            "valuation",
            "variant_perception",
            "decisive_unknowns",
            "counterevidence",
            "structural_stop_reasons",
            "revisit_triggers",
        }
        or not isinstance(provenance, Mapping)
        or provenance.get("agent") != claim["agent"]
        or _parse_datetime(provenance.get("generated_at"), "provenance.generated_at")
        < _parse_datetime(claim["claimed_at"], "claim.claimed_at")
        or profile_body.get("symbol") != claim["symbol"]
        or evaluation.get("cycle_id") != claim["profile_cycle_id"]
        or evaluation.get("symbol") != claim["symbol"]
        or evaluation.get("company_name") != normalized.get("company_name")
        or evaluation.get("recorded_at") != success["succeeded_at"]
        or evaluation.get("profile_path") != success["profile_path"]
        or evaluation.get("profile_sha256") != success["profile_sha256"]
        or not isinstance(evaluation.get("policy_reference"), str)
        or not evaluation["policy_reference"].strip()
        or not _SHA256_RE.fullmatch(str(evaluation.get("policy_payload_sha256")))
        or (
            evaluation.get("allocation_sha256") is not None
            and not _SHA256_RE.fullmatch(str(evaluation.get("allocation_sha256")))
        )
        or evaluation.get("portfolio_action") is not None
        or not isinstance(evaluated, Mapping)
        or set(evaluated) != _PROFILE_EVALUATION_RESULT_KEYS
        or evaluated.get("schema_version") != 1
        or evaluated.get("symbol") != claim["symbol"]
        or evaluated.get("as_of") != profile_body.get("as_of")
        or evaluated.get("evaluated_stage") != profile_body.get("research_stage")
        or evaluated.get("portfolio_action") is not None
    ):
        raise ProfileStageClaimError("profile success package/evaluation identity is invalid")
    next_stage = evaluated.get("next_stage")
    queue_status = evaluation.get("queue_status")
    capacity_wait = evaluation.get("capacity_wait")
    if next_stage in _PROFILE_RESEARCH_STAGES:
        if queue_status not in {"pending", "requires_rebaseline"} or capacity_wait is not (
            queue_status == "requires_rebaseline"
        ):
            raise ProfileStageClaimError("profile success research-stage projection is invalid")
    elif queue_status != "completed" or capacity_wait is not False:
        raise ProfileStageClaimError("profile success terminal projection is invalid")


def _validate_profile_manager_contract(
    profile: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
) -> None:
    prior = claim.get("prior_queue_row")
    if not isinstance(prior, Mapping):
        raise ProfileStageClaimError("profile success claim prior queue row is invalid")
    locked = prior.get("manager_screen_locked_calibration_remediation")
    if (
        claim.get("stage") == "targeted_followup"
        and isinstance(locked, Mapping)
        and locked.get("remediation") == "targeted_remediation_candidate"
    ):
        expected = {
            "result_path": locked.get("allocation_result_path"),
            "result_sha256": locked.get("allocation_result_sha256"),
            "decisive_question": locked.get("decisive_question"),
            "evidence_ids": list(locked.get("evidence_ids") or []),
        }
    elif prior.get("manager_screen_allocation_result_path") is not None:
        expected = {
            "result_path": prior.get("manager_screen_allocation_result_path"),
            "result_sha256": prior.get("manager_screen_allocation_result_sha256"),
            "decisive_question": prior.get("decisive_question"),
            "evidence_ids": list(prior.get("evidence_ids") or []),
        }
    elif prior.get("manager_screen_result_path") is not None:
        expected = {
            "result_path": prior.get("manager_screen_result_path"),
            "result_sha256": prior.get("manager_screen_result_sha256"),
            "decisive_question": prior.get("decisive_question"),
            "evidence_ids": list(prior.get("evidence_ids") or []),
        }
    else:
        return
    binding = profile.get("manager_screen_binding")
    answer = profile.get("decisive_answer")
    if (
        not isinstance(binding, Mapping)
        or dict(binding) != expected
        or not isinstance(answer, Mapping)
        or not isinstance(answer.get("conclusion"), str)
        or not answer["conclusion"].strip()
        or not isinstance(answer.get("source_ids"), list)
        or not answer["source_ids"]
    ):
        raise ProfileStageClaimError(
            "profile success package does not satisfy its manager decision contract"
        )


def _load_chain(
    *,
    base: Path,
    repository: Path,
    queue_record: Mapping[str, Any],
    stage: str,
) -> list[dict[str, Any]]:
    root = _attempts_root(base=base, queue_record=queue_record, stage=stage)
    if not root.exists():
        return []
    if not root.is_dir():
        raise ProfileStageClaimError("stage claim attempts path is not a directory")
    dirs = sorted(path for path in root.iterdir() if path.is_dir())
    unexpected = sorted(path.name for path in root.iterdir() if not path.is_dir())
    if unexpected:
        raise ProfileStageClaimError(
            f"stage claim attempts contain an unexpected file: {unexpected[0]}"
        )
    numbers = []
    for path in dirs:
        match = _ATTEMPT_DIR_RE.fullmatch(path.name)
        if match is None:
            raise ProfileStageClaimError(f"stage claim attempt directory is invalid: {path.name}")
        numbers.append(int(match.group(1)))
    if numbers != list(range(1, len(numbers) + 1)):
        raise ProfileStageClaimError("stage claim attempt numbers are not contiguous")

    chain: list[dict[str, Any]] = []
    previous_release: dict[str, Any] | None = None
    previous_release_relative: str | None = None
    previous_release_sha256: str | None = None
    for number, attempt_dir in enumerate(dirs, 1):
        claim_path = attempt_dir / "claim.json"
        release_path = attempt_dir / "release.json"
        _require_pair_complete(claim_path, "stage claim")
        _require_pair_or_absent(release_path, "stage claim release")
        claim, claim_seal = _sealed_object(claim_path, CLAIM_ARTIFACT_TYPE)
        _validate_claim_payload(claim)
        claim_relative = _relative(claim_path, repository)
        if (
            claim["stage"] != stage
            or claim["attempt_number"] != number
            or claim["symbol"] != queue_record.get("symbol")
            or claim["profile_cycle_id"] != queue_record.get("profile_cycle_id")
            or claim["manager_screen_run_id"] != queue_record.get("manager_screen_run_id")
            or claim_seal.sealed_at != _parse_datetime(claim["claimed_at"], "claim.claimed_at")
        ):
            raise ProfileStageClaimError("stage claim identity/time does not match its path")
        expected_previous = (
            None
            if previous_release is None
            else {
                "path": previous_release_relative,
                "sha256": previous_release_sha256,
            }
        )
        if claim["previous_release"] != expected_previous:
            raise ProfileStageClaimError("stage claim predecessor release binding is invalid")
        if number > 1:
            assert previous_release is not None
            prior_expected = _released_projection(
                chain[-1]["claim"],
                previous_release,
                claim_path=chain[-1]["claim_relative"],
                claim_sha256=chain[-1]["claim_sha256"],
                release_path=previous_release_relative,
                release_sha256=previous_release_sha256,
            )
            if claim["prior_queue_row"] != prior_expected:
                raise ProfileStageClaimError(
                    "retry claim prior row does not descend from the previous release"
                )
        authorization = _stage_authorization(
            claim["prior_queue_row"],
            repository=repository,
            stage=stage,
        )
        if authorization != claim["stage_authorization"]:
            raise ProfileStageClaimError("stage claim authorization binding drifted")
        release = None
        release_relative = None
        release_sha256 = None
        if release_path.exists():
            release, release_seal = _sealed_object(release_path, RELEASE_ARTIFACT_TYPE)
            _validate_release_payload(release)
            release_relative = _relative(release_path, repository)
            release_sha256 = release_seal.sha256
            if (
                release["stage"] != stage
                or release["attempt_number"] != number
                or release["symbol"] != claim["symbol"]
                or release["profile_cycle_id"] != claim["profile_cycle_id"]
                or release["manager_screen_run_id"] != claim["manager_screen_run_id"]
                or release["agent"] != claim["agent"]
                or release["claim_path"] != claim_relative
                or release["claim_sha256"] != claim_seal.sha256
                or release_seal.sealed_at
                != _parse_datetime(release["released_at"], "release.released_at")
                or release_seal.sealed_at <= claim_seal.sealed_at
                or not _matches_running_projection(
                    release["prior_running_row"],
                    claim=claim,
                    claim_path=claim_relative,
                    claim_sha256=claim_seal.sha256,
                    repository=repository,
                )
            ):
                raise ProfileStageClaimError("stage claim release binding/time is invalid")
        if release is None and number != len(dirs):
            raise ProfileStageClaimError("an unreleased stage claim has a later attempt")
        entry = {
            "claim": claim,
            "claim_path": claim_path,
            "claim_relative": claim_relative,
            "claim_sha256": claim_seal.sha256,
            "release": release,
            "release_path": release_path,
            "release_relative": release_relative,
            "release_sha256": release_sha256,
        }
        chain.append(entry)
        previous_release = release
        previous_release_relative = release_relative
        previous_release_sha256 = release_sha256
    return chain


def _stage_authorization(
    row: Mapping[str, Any],
    *,
    repository: Path,
    stage: str,
) -> dict[str, Any]:
    fields = {
        "targeted_followup": (
            "targeted_followup_approval_path",
            "targeted_followup_approval_sha256",
            {"targeted_followup_approval"},
        ),
        "scoped_research": (
            "profile_quick_selection_path",
            "profile_quick_selection_sha256",
            {"quick_profile_cross_company_selection"},
        ),
        "deep_research": (
            "profile_scoped_selection_path",
            "profile_scoped_selection_sha256",
            {"scoped_research_cross_company_selection"},
        ),
    }
    if stage == "quick_profile":
        if row.get("manager_screen_allocation_result_path") is not None:
            fields_for_stage = (
                "manager_screen_allocation_result_path",
                "manager_screen_allocation_result_sha256",
                {"manager_screen_full_market_allocation_v3_result"},
            )
        else:
            fields_for_stage = (
                "manager_screen_result_path",
                "manager_screen_result_sha256",
                {
                    "manager_screen_result",
                    "manager_screen_quote_impact_result",
                    "manager_screen_legacy_transition_result",
                },
            )
    else:
        fields_for_stage = fields[stage]
    path_field, sha_field, allowed_types = fields_for_stage
    relative = _relative_text(row.get(path_field), path_field)
    raw_expected_sha256 = row.get(sha_field)
    legacy_selection_without_queue_sha = bool(
        raw_expected_sha256 is None
        and stage in {"scoped_research", "deep_research"}
    )
    expected_sha256 = (
        None
        if legacy_selection_without_queue_sha
        else _sha256(raw_expected_sha256, sha_field)
    )
    path = (repository / relative).resolve()
    try:
        path.relative_to(repository)
        sealed = verify_sealed(path)
    except (OSError, SealingError, ValueError) as exc:
        raise ProfileStageClaimError("profile stage authorization is not validly sealed") from exc
    if sealed.artifact_type not in allowed_types or (
        expected_sha256 is not None and sealed.sha256 != expected_sha256
    ):
        raise ProfileStageClaimError("profile stage authorization binding is invalid")
    return {
        "path": relative,
        "sha256": sealed.sha256,
        "artifact_type": sealed.artifact_type,
        "sealed_at": sealed.sealed_at.isoformat(),
    }


def _validate_pending_prior(row: Mapping[str, Any], *, stage: str) -> None:
    if (
        row.get("task_type") != stage
        or row.get("status") != "pending"
        or row.get("assigned_agent") is not None
        or row.get("started_at") is not None
        or row.get("finished_at") is not None
        or row.get("failure_reason") is not None
    ):
        raise ProfileStageClaimError("new sealed stage claim requires a pristine pending row")
    _symbol(row.get("symbol"))
    _identifier(row.get("profile_cycle_id"), "profile_cycle_id")
    _stage_run_id(row.get("manager_screen_run_id"), stage=stage)


def _immutable_queue_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value for key, value in row.items() if key not in _DISPLAY_MUTABLE_QUEUE_FIELDS
    }


def _matches_pending_projection(
    row: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    repository: Path,
) -> bool:
    del repository
    return _immutable_queue_projection(row) == _immutable_queue_projection(claim["prior_queue_row"])


def _matches_running_projection(
    row: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    claim_path: str,
    claim_sha256: str,
    repository: Path,
) -> bool:
    del repository
    expected = _running_projection(
        claim,
        claim_path=claim_path,
        claim_sha256=claim_sha256,
    )
    return _immutable_queue_projection(row) == _immutable_queue_projection(expected)


def _matches_released_projection(
    row: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    release: Mapping[str, Any],
    claim_path: str,
    claim_sha256: str,
    release_path: str | None,
    release_sha256: str | None,
    repository: Path,
) -> bool:
    if release_path is None or release_sha256 is None:
        return False
    expected = _released_projection(
        claim,
        release,
        claim_path=claim_path,
        claim_sha256=claim_sha256,
        release_path=release_path,
        release_sha256=release_sha256,
    )
    del repository
    return _immutable_queue_projection(row) == _immutable_queue_projection(expected)


def _running_projection(
    claim: Mapping[str, Any],
    *,
    claim_path: str,
    claim_sha256: str,
    base_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    updated = dict(claim["prior_queue_row"] if base_row is None else base_row)
    updated.update(
        {
            "status": "running",
            "assigned_agent": claim["agent"],
            "started_at": claim["claimed_at"],
            "finished_at": None,
            "failure_reason": None,
            CLAIM_BINDING_PATH_FIELD: claim_path,
            CLAIM_BINDING_SHA_FIELD: claim_sha256,
        }
    )
    updated.pop(RELEASE_BINDING_PATH_FIELD, None)
    updated.pop(RELEASE_BINDING_SHA_FIELD, None)
    return updated


def _released_projection(
    claim: Mapping[str, Any],
    release: Mapping[str, Any],
    *,
    claim_path: str,
    claim_sha256: str,
    release_path: str | None,
    release_sha256: str | None,
) -> dict[str, Any]:
    if release_path is None or release_sha256 is None:
        raise ProfileStageClaimError("sealed stage release path/SHA is missing")
    prior_running = release.get("prior_running_row")
    if not isinstance(prior_running, Mapping):
        raise ProfileStageClaimError("sealed stage release prior running row is invalid")
    running = dict(prior_running)
    attempts = list(running.get("attempt_history") or [])
    attempts.append(
        {
            "agent": claim["agent"],
            "started_at": claim["claimed_at"],
            "finished_at": release["released_at"],
            "status": "failed",
            "failure_reason": release["failure_reason"],
            "claim_path": claim_path,
            "claim_sha256": claim_sha256,
            "release_path": release_path,
            "release_sha256": release_sha256,
        }
    )
    running.update(
        {
            "status": "pending",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "failure_reason": None,
            "attempt_history": attempts,
            RELEASE_BINDING_PATH_FIELD: release_path,
            RELEASE_BINDING_SHA_FIELD: release_sha256,
        }
    )
    return running


def _validate_claim_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != _CLAIM_KEYS:
        raise ProfileStageClaimError("stage claim fields do not match contract")
    if (
        value.get("schema_version") != 1
        or value.get("workflow") != WORKFLOW
        or value.get("workflow_version") != WORKFLOW_VERSION
        or value.get("portfolio_action") is not None
    ):
        raise ProfileStageClaimError("stage claim schema/workflow is invalid")
    stage = _stage(value.get("stage"))
    _stage_run_id(value.get("manager_screen_run_id"), stage=stage)
    _identifier(value.get("profile_cycle_id"), "profile_cycle_id")
    symbol = _symbol(value.get("symbol"))
    attempt = _positive_int(value.get("attempt_number"), "attempt_number")
    _text(value.get("agent"), "agent")
    _parse_datetime(value.get("claimed_at"), "claimed_at")
    authorization = value.get("stage_authorization")
    if not isinstance(authorization, Mapping) or set(authorization) != _AUTHORIZATION_KEYS:
        raise ProfileStageClaimError("stage claim authorization fields are invalid")
    _relative_text(authorization.get("path"), "authorization.path")
    _sha256(authorization.get("sha256"), "authorization.sha256")
    _text(authorization.get("artifact_type"), "authorization.artifact_type")
    _parse_datetime(authorization.get("sealed_at"), "authorization.sealed_at")
    previous = value.get("previous_release")
    if previous is not None:
        if not isinstance(previous, Mapping) or set(previous) != _PREVIOUS_RELEASE_KEYS:
            raise ProfileStageClaimError("stage claim previous release fields are invalid")
        _relative_text(previous.get("path"), "previous_release.path")
        _sha256(previous.get("sha256"), "previous_release.sha256")
    if (attempt == 1) is not (previous is None):
        raise ProfileStageClaimError("stage claim predecessor release cardinality is invalid")
    prior = value.get("prior_queue_row")
    if not isinstance(prior, Mapping) or prior.get("symbol") != symbol:
        raise ProfileStageClaimError("stage claim prior queue row is invalid")
    if value.get("prior_queue_row_sha256") != _payload_sha256(prior):
        raise ProfileStageClaimError("stage claim prior queue SHA is invalid")
    if prior.get("task_type") != stage:
        raise ProfileStageClaimError("stage claim prior queue stage is invalid")


def _validate_release_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != _RELEASE_KEYS:
        raise ProfileStageClaimError("stage release fields do not match contract")
    if (
        value.get("schema_version") != 1
        or value.get("workflow") != WORKFLOW
        or value.get("workflow_version") != WORKFLOW_VERSION
        or value.get("portfolio_action") is not None
    ):
        raise ProfileStageClaimError("stage release schema/workflow is invalid")
    stage = _stage(value.get("stage"))
    _stage_run_id(value.get("manager_screen_run_id"), stage=stage)
    _identifier(value.get("profile_cycle_id"), "profile_cycle_id")
    _symbol(value.get("symbol"))
    _positive_int(value.get("attempt_number"), "attempt_number")
    _text(value.get("agent"), "agent")
    _parse_datetime(value.get("released_at"), "released_at")
    _text(value.get("failure_reason"), "failure_reason")
    _relative_text(value.get("claim_path"), "claim_path")
    _sha256(value.get("claim_sha256"), "claim_sha256")
    prior = value.get("prior_running_row")
    if not isinstance(prior, Mapping) or prior.get("symbol") != value.get("symbol"):
        raise ProfileStageClaimError("stage release prior running row is invalid")
    if value.get("prior_running_row_sha256") != _payload_sha256(prior):
        raise ProfileStageClaimError("stage release prior running row SHA is invalid")


def _claim_summary(
    entry: Mapping[str, Any],
    *,
    idempotent: bool,
    repaired: bool,
) -> dict[str, Any]:
    return {
        "path": entry["claim_relative"],
        "sha256": entry["claim_sha256"],
        "attempt_number": entry["claim"]["attempt_number"],
        "claimed_at": entry["claim"]["claimed_at"],
        "idempotent": idempotent,
        "projection_repaired": repaired,
    }


def _release_summary(
    entry: Mapping[str, Any],
    *,
    idempotent: bool,
    repaired: bool,
) -> dict[str, Any]:
    return {
        "path": entry["release_relative"],
        "sha256": entry["release_sha256"],
        "attempt_number": entry["claim"]["attempt_number"],
        "released_at": entry["release"]["released_at"],
        "idempotent": idempotent,
        "projection_repaired": repaired,
    }


def _attempts_root(
    *,
    base: Path,
    queue_record: Mapping[str, Any],
    stage: str,
) -> Path:
    cycle = _identifier(queue_record.get("profile_cycle_id"), "profile_cycle_id")
    ticker = _symbol(queue_record.get("symbol")).split(":", 1)[1]
    return base / "profiles" / cycle / "stage-claim-attempts" / stage / ticker


def _attempt_dir(
    *,
    base: Path,
    queue_record: Mapping[str, Any],
    stage: str,
    attempt_number: int,
) -> Path:
    return _attempts_root(base=base, queue_record=queue_record, stage=stage) / (
        f"attempt-{attempt_number:06d}"
    )


def _sealed_object(path: Path, artifact_type: str) -> tuple[dict[str, Any], Any]:
    try:
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SealingError) as exc:
        raise ProfileStageClaimError(f"sealed stage claim artifact is invalid: {path}") from exc
    if sealed.artifact_type != artifact_type or not isinstance(payload, dict):
        raise ProfileStageClaimError(f"stage claim artifact type is invalid: {path}")
    return payload, sealed


def _require_pair_complete(path: Path, label: str) -> None:
    pair = (path.exists(), _seal_path(path).exists())
    if pair != (True, True):
        raise ProfileStageClaimError(f"{label} is missing or only partially sealed")


def _require_pair_or_absent(path: Path, label: str) -> None:
    pair = (path.exists(), _seal_path(path).exists())
    if pair[0] != pair[1]:
        raise ProfileStageClaimError(f"{label} is only partially sealed")


def _seal_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.seal.json")


def _relative(path: Path, repository: Path) -> str:
    try:
        return path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError as exc:  # pragma: no cover - canonical paths stay in coverage.
        raise ProfileStageClaimError("stage claim path escapes repository root") from exc


def _payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _stage(value: Any) -> str:
    stage = _text(value, "stage")
    if stage not in SUPPORTED_STAGES:
        raise ProfileStageClaimError(f"sealed stage claims do not support: {stage}")
    return stage


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not _SYMBOL_RE.fullmatch(value):
        raise ProfileStageClaimError("symbol is invalid")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ProfileStageClaimError(f"{label} is invalid")
    return value


def _stage_run_id(value: Any, *, stage: str) -> str | None:
    """Validate run identity while preserving sealed pre-run stage work.

    Quick profile is always purchased by manager-screen and therefore must be
    run-bound. Historical rapid-triage profiles can have targeted/scoped
    selections that predate the run-level ledger contract; those stages still
    receive append-only claim receipts with an explicit null run identity.
    """

    if value is None and stage != "quick_profile":
        return None
    return _identifier(value, "manager_screen_run_id")


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ProfileStageClaimError(f"{label} is invalid")
    return value


def _relative_text(value: Any, label: str) -> str:
    text = _text(value, label).replace("\\", "/")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or text.startswith("/"):
        raise ProfileStageClaimError(f"{label} must be repository-relative")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise ProfileStageClaimError(f"{label} must be repository-relative")
    return normalized


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileStageClaimError(f"{label} is required")
    return value.strip()


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProfileStageClaimError(f"{label} must be a positive integer")
    return value


def _aware(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProfileStageClaimError(f"{label} must include a UTC offset")
    return value


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ProfileStageClaimError(f"{label} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProfileStageClaimError(f"{label} must be an ISO datetime") from exc
    return _aware(parsed, label)
