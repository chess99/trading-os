from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .coverage_store import serialized_coverage_write
from .manager_screen_governance import (
    ManagerScreenGovernanceError,
    load_manager_screen_supersession,
)
from .manager_screen_terminal_governance import (
    ManagerScreenTerminalGovernanceError,
    require_manager_screen_terminal_governance_open,
)
from .sealing import SealingError, seal_json, verify_sealed


class ManagerScreenControlError(ValueError):
    """Raised when manager-screen run control is invalid or blocks production."""


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTROL_STATES = {"paused", "controlled", "active"}
MANAGER_KEYS = {"agent", "model", "tools"}
CONTROL_EVENT_KEYS = {
    "schema_version",
    "run_id",
    "event_id",
    "state",
    "recorded_at",
    "manager",
    "reason",
    "previous_event_sha256",
    "baseline_completed_company_count",
    "company_limit",
    "portfolio_action",
}


@serialized_coverage_write
def record_manager_screen_control(
    *,
    root: str | Path,
    run_id: str,
    event_id: str,
    state: str,
    manager: Mapping[str, Any],
    reason: str,
    recorded_at: dt.datetime,
    company_limit: int | None = None,
) -> dict[str, Any]:
    """Append one immutable run-control event and return the effective state."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    event = _identifier(event_id, "event_id")
    normalized_state = _state(state)
    timestamp = _aware(recorded_at, "recorded_at")
    normalized_manager = _manager(manager)
    explanation = _text(reason, "reason")
    limit = _company_limit(company_limit, state=normalized_state)
    run_dir = base / "manager-screen" / run
    control_dir = run_dir / "control"
    event_path = control_dir / f"{event}.json"

    existing_events = _load_control_events(
        run_dir=run_dir,
        repository_root=repository_root,
        run_id=run,
    )
    existing = next(
        (item for item in existing_events if item["payload"]["event_id"] == event),
        None,
    )
    if existing is not None:
        payload = existing["payload"]
        if (
            payload["state"] != normalized_state
            or payload["recorded_at"] != timestamp.isoformat()
            or payload["manager"] != normalized_manager
            or payload["reason"] != explanation
            or payload["company_limit"] != limit
        ):
            raise ManagerScreenControlError(
                f"sealed manager-screen control event conflicts with request: {event}"
            )
        counts = _manager_screen_counts(
            run_dir=run_dir,
            repository_root=repository_root,
            run_id=run,
        )
        return _control_status(
            run_id=run,
            events=existing_events,
            completed_company_count=counts["completed_company_count"],
            open_company_count=counts["open_company_count"],
            repository_root=repository_root,
        )

    try:
        require_manager_screen_terminal_governance_open(
            root=base,
            run_id=run,
            operation="new manager-screen control event",
        )
    except ManagerScreenTerminalGovernanceError as exc:
        raise ManagerScreenControlError(str(exc)) from exc

    latest = existing_events[-1] if existing_events else None
    if latest is not None and timestamp <= latest["recorded_at"]:
        raise ManagerScreenControlError(
            "recorded_at must be later than the latest manager-screen control event"
        )
    counts = _manager_screen_counts(
        run_dir=run_dir,
        repository_root=repository_root,
        run_id=run,
    )
    if (
        normalized_state == "controlled"
        and counts["open_company_count"] > limit
    ):
        raise ManagerScreenControlError(
            "cannot enter controlled state: existing open reservations exceed "
            f"company_limit ({counts['open_company_count']} > {limit})"
        )
    payload = {
        "schema_version": 1,
        "run_id": run,
        "event_id": event,
        "state": normalized_state,
        "recorded_at": timestamp.isoformat(),
        "manager": normalized_manager,
        "reason": explanation,
        "previous_event_sha256": latest["seal"].sha256 if latest is not None else None,
        "baseline_completed_company_count": (
            counts["completed_company_count"]
            if normalized_state == "controlled"
            else None
        ),
        "company_limit": limit,
        "portfolio_action": None,
    }
    seal = seal_json(
        event_path,
        payload,
        artifact_type="manager_screen_run_control_event",
        sealed_at=timestamp,
    )
    existing_events.append(
        {
            "payload": payload,
            "path": event_path,
            "seal": seal,
            "recorded_at": timestamp,
        }
    )
    return _control_status(
        run_id=run,
        events=existing_events,
        completed_company_count=counts["completed_company_count"],
        open_company_count=counts["open_company_count"],
        repository_root=repository_root,
    )


def manager_screen_control_status(
    *,
    root: str | Path,
    run_id: str,
    completed_company_count: int | None = None,
    open_company_count: int | None = None,
) -> dict[str, Any]:
    """Verify the append-only control timeline and report remaining capacity."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    run_dir = base / "manager-screen" / run
    events = _load_control_events(
        run_dir=run_dir,
        repository_root=repository_root,
        run_id=run,
    )
    if completed_company_count is None or open_company_count is None:
        counts = _manager_screen_counts(
            run_dir=run_dir,
            repository_root=repository_root,
            run_id=run,
        )
        completed = counts["completed_company_count"]
        opened = counts["open_company_count"]
    else:
        completed = _non_negative_int(
            completed_company_count,
            "completed_company_count",
        )
        opened = _non_negative_int(open_company_count, "open_company_count")
    return _control_status(
        run_id=run,
        events=events,
        completed_company_count=completed,
        open_company_count=opened,
        repository_root=repository_root,
    )


def require_manager_screen_freeze_allowed(
    *,
    root: str | Path,
    run_id: str,
    requested_company_count: int,
    control_required: bool = False,
) -> dict[str, Any]:
    """Fail closed when a new batch would violate the effective run control."""

    requested = _positive_int(requested_company_count, "requested_company_count")
    status = manager_screen_control_status(root=root, run_id=run_id)
    if control_required and not status["managed"]:
        raise ManagerScreenControlError(
            "manager-screen policy requires managed run control; no control event exists"
        )
    if status["state"] == "paused":
        raise ManagerScreenControlError(
            "manager-screen run is paused; new production batches are forbidden"
        )
    if status["state"] == "controlled" and requested > status["remaining_company_count"]:
        raise ManagerScreenControlError(
            "manager-screen controlled company limit would be exceeded: "
            f"requested {requested}, remaining {status['remaining_company_count']}"
        )
    return status


def require_manager_screen_first_record_allowed(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    batch_sha256: str,
    member_count: int,
    control_required: bool = False,
) -> dict[str, Any]:
    """Block a first result while paused; sealed result replays bypass this call."""

    status = manager_screen_control_status(root=root, run_id=run_id)
    if control_required and not status["managed"]:
        raise ManagerScreenControlError(
            "manager-screen policy requires managed run control; no control event exists"
        )
    if status["state"] == "paused":
        raise ManagerScreenControlError(
            "manager-screen run is paused; first-time decision recording is forbidden"
        )
    if status["state"] == "controlled":
        base = Path(root)
        run = _identifier(run_id, "run_id")
        batch = _identifier(batch_id, "batch_id")
        expected_member_count = _positive_int(member_count, "member_count")
        if not isinstance(batch_sha256, str) or not SHA256_RE.fullmatch(batch_sha256):
            raise ManagerScreenControlError("batch_sha256 is invalid")
        counts = _manager_screen_counts(
            run_dir=base / "manager-screen" / run,
            repository_root=base.parent.parent.resolve(),
            run_id=run,
        )
        reservation = counts["open_reservations"].get(batch)
        if reservation != {
            "batch_sha256": batch_sha256,
            "member_count": expected_member_count,
        }:
            raise ManagerScreenControlError(
                "manager-screen batch is not an active open reservation in the "
                "controlled allowance"
            )
        used = status["used_company_count"]
        limit = status["company_limit"]
        if used > limit:
            raise ManagerScreenControlError(
                "manager-screen controlled allowance is over capacity before first "
                f"record ({used} > {limit})"
            )
    return status


def _load_control_events(
    *,
    run_dir: Path,
    repository_root: Path,
    run_id: str,
) -> list[dict[str, Any]]:
    control_dir = run_dir / "control"
    if not control_dir.exists():
        return []
    if not control_dir.is_dir():
        raise ManagerScreenControlError("manager-screen control path is not a directory")
    data_paths = sorted(
        path for path in control_dir.iterdir() if path.is_file() and path.suffix == ".json"
        and not path.name.endswith(".seal.json")
    )
    seal_paths = {
        path.name.removesuffix(".seal.json")
        for path in control_dir.iterdir()
        if path.is_file() and path.name.endswith(".json.seal.json")
    }
    if seal_paths != {path.name for path in data_paths}:
        raise ManagerScreenControlError(
            "manager-screen control timeline contains an orphan artifact or seal"
        )
    events = []
    event_ids: set[str] = set()
    for path in data_paths:
        payload, seal = _sealed_object(
            path,
            artifact_type="manager_screen_run_control_event",
        )
        _validate_control_event(payload, run_id=run_id, path=path)
        event_id = payload["event_id"]
        if event_id in event_ids or path.name != f"{event_id}.json":
            raise ManagerScreenControlError(
                "manager-screen control event identity does not match its path"
            )
        event_ids.add(event_id)
        events.append(
            {
                "payload": payload,
                "path": path,
                "seal": seal,
                "recorded_at": _parse_datetime(payload["recorded_at"], "recorded_at"),
            }
        )
        if seal.sealed_at != events[-1]["recorded_at"]:
            raise ManagerScreenControlError(
                "manager-screen control event seal time does not match recorded_at"
            )
    events.sort(key=lambda item: (item["recorded_at"], item["payload"]["event_id"]))
    previous = None
    for item in events:
        if previous is not None and item["recorded_at"] <= previous["recorded_at"]:
            raise ManagerScreenControlError(
                "manager-screen control event timestamps must be strictly increasing"
            )
        expected_previous = previous["seal"].sha256 if previous is not None else None
        if item["payload"]["previous_event_sha256"] != expected_previous:
            raise ManagerScreenControlError(
                "manager-screen control event chain is invalid"
            )
        previous = item
    return events


def _manager_screen_counts(
    *,
    run_dir: Path,
    repository_root: Path,
    run_id: str,
) -> dict[str, Any]:
    completed = 0
    opened = 0
    open_reservations: dict[str, dict[str, Any]] = {}
    if not run_dir.is_dir():
        return {
            "completed_company_count": 0,
            "open_company_count": 0,
            "open_reservations": {},
        }
    for batch_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        batch_path = batch_dir / "batch.json"
        journal_path = batch_dir / "freeze-journal.json"
        if batch_path.exists() or batch_path.with_name("batch.json.seal.json").exists():
            batch, batch_seal = _sealed_object(
                batch_path,
                artifact_type="manager_screen_batch",
            )
            reservation_sha256 = batch_seal.sha256
        elif journal_path.exists() or journal_path.with_name(
            "freeze-journal.json.seal.json"
        ).exists():
            journal, _ = _sealed_object(
                journal_path,
                artifact_type="manager_screen_freeze_journal",
            )
            batch = journal.get("batch")
            if not isinstance(batch, dict):
                raise ManagerScreenControlError(
                    "manager-screen freeze journal batch is invalid"
                )
            batch_sha256 = journal.get("batch_sha256")
            if not isinstance(batch_sha256, str) or not SHA256_RE.fullmatch(
                batch_sha256
            ):
                raise ManagerScreenControlError(
                    "manager-screen freeze journal batch SHA is invalid"
                )
            reservation_sha256 = batch_sha256
        else:
            continue
        if batch.get("run_id") != run_id or batch.get("batch_id") != batch_dir.name:
            raise ManagerScreenControlError(
                "manager-screen batch identity is invalid while evaluating control"
            )
        members = batch.get("members")
        member_count = batch.get("member_count")
        if (
            not isinstance(members, list)
            or isinstance(member_count, bool)
            or not isinstance(member_count, int)
            or member_count <= 0
            or len(members) != member_count
        ):
            raise ManagerScreenControlError(
                "manager-screen batch member count is invalid while evaluating control"
            )
        try:
            supersession = load_manager_screen_supersession(
                batch_dir=batch_dir,
                repository_root=repository_root,
            )
        except ManagerScreenGovernanceError as exc:
            raise ManagerScreenControlError(
                "manager-screen supersession is invalid while evaluating control"
            ) from exc
        if supersession is not None:
            continue
        result_path = batch_dir / "result.json"
        result_exists = result_path.exists() or result_path.with_name(
            "result.json.seal.json"
        ).exists()
        if result_exists:
            result, _ = _sealed_object(
                result_path,
                artifact_type="manager_screen_result",
            )
            if result.get("run_id") != run_id or result.get("batch_id") != batch_dir.name:
                raise ManagerScreenControlError(
                    "manager-screen result identity is invalid while evaluating control"
                )
            completed += member_count
        else:
            opened += member_count
            open_reservations[batch_dir.name] = {
                "batch_sha256": reservation_sha256,
                "member_count": member_count,
            }
    return {
        "completed_company_count": completed,
        "open_company_count": opened,
        "open_reservations": open_reservations,
    }


def _control_status(
    *,
    run_id: str,
    events: list[dict[str, Any]],
    completed_company_count: int,
    open_company_count: int,
    repository_root: Path,
) -> dict[str, Any]:
    if not events:
        return {
            "schema_version": 1,
            "run_id": run_id,
            "state": "active_unmanaged",
            "managed": False,
            "event_count": 0,
            "latest_event_id": None,
            "latest_event_path": None,
            "latest_event_sha256": None,
            "recorded_at": None,
            "manager": None,
            "reason": None,
            "baseline_completed_company_count": None,
            "company_limit": None,
            "used_company_count": None,
            "remaining_company_count": None,
        }
    latest = events[-1]
    payload = latest["payload"]
    baseline = payload["baseline_completed_company_count"]
    limit = payload["company_limit"]
    used = None
    remaining = None
    if payload["state"] == "controlled":
        used = max(0, completed_company_count + open_company_count - baseline)
        remaining = max(0, limit - used)
    return {
        "schema_version": 1,
        "run_id": run_id,
        "state": payload["state"],
        "managed": True,
        "event_count": len(events),
        "latest_event_id": payload["event_id"],
        "latest_event_path": _relative(latest["path"], repository_root),
        "latest_event_sha256": latest["seal"].sha256,
        "recorded_at": payload["recorded_at"],
        "manager": payload["manager"],
        "reason": payload["reason"],
        "baseline_completed_company_count": baseline,
        "company_limit": limit,
        "used_company_count": used,
        "remaining_company_count": remaining,
    }


def _validate_control_event(payload: Any, *, run_id: str, path: Path) -> None:
    if not isinstance(payload, dict) or set(payload) != CONTROL_EVENT_KEYS:
        raise ManagerScreenControlError(
            "manager-screen control event fields do not match v1"
        )
    if payload.get("schema_version") != 1 or payload.get("run_id") != run_id:
        raise ManagerScreenControlError("manager-screen control event run binding is invalid")
    event_id = _identifier(payload.get("event_id"), "event_id")
    state = _state(payload.get("state"))
    _parse_datetime(payload.get("recorded_at"), "recorded_at")
    _manager(payload.get("manager"))
    _text(payload.get("reason"), "reason")
    previous = payload.get("previous_event_sha256")
    if previous is not None and (
        not isinstance(previous, str) or not SHA256_RE.fullmatch(previous)
    ):
        raise ManagerScreenControlError("previous_event_sha256 is invalid")
    baseline = payload.get("baseline_completed_company_count")
    limit = payload.get("company_limit")
    if state == "controlled":
        _non_negative_int(baseline, "baseline_completed_company_count")
        _positive_int(limit, "company_limit")
    elif baseline is not None or limit is not None:
        raise ManagerScreenControlError(
            "only controlled events may carry a baseline and company limit"
        )
    if payload.get("portfolio_action") is not None:
        raise ManagerScreenControlError("manager-screen control cannot take portfolio action")
    if path.name != f"{event_id}.json":
        raise ManagerScreenControlError("manager-screen control event path is invalid")


def _sealed_object(path: Path, *, artifact_type: str) -> tuple[dict[str, Any], Any]:
    try:
        seal = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenControlError(
            f"sealed manager-screen control input is invalid: {path}"
        ) from exc
    if seal.artifact_type != artifact_type or not isinstance(payload, dict):
        raise ManagerScreenControlError(
            f"sealed manager-screen control input has unexpected type: {path}"
        )
    return payload, seal


def _manager(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != MANAGER_KEYS:
        raise ManagerScreenControlError("manager fields do not match contract")
    tools = value.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or any(not isinstance(item, str) or not item.strip() for item in tools)
    ):
        raise ManagerScreenControlError("manager.tools must be non-empty strings")
    return {
        "agent": _text(value.get("agent"), "manager.agent"),
        "model": _text(value.get("model"), "manager.model"),
        "tools": [item.strip() for item in tools],
    }


def _company_limit(value: Any, *, state: str) -> int | None:
    if state == "controlled":
        return _positive_int(value, "company_limit")
    if value is not None:
        raise ManagerScreenControlError(
            "company_limit is only valid for controlled state"
        )
    return None


def _state(value: Any) -> str:
    result = _text(value, "state")
    if result not in CONTROL_STATES:
        raise ManagerScreenControlError(
            "state must be one of active, controlled, or paused"
        )
    return result


def _identifier(value: Any, field: str) -> str:
    result = _text(value, field)
    if not ID_RE.fullmatch(result):
        raise ManagerScreenControlError(f"{field} is invalid")
    return result


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenControlError(f"{field} must be non-empty text")
    return value.strip()


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManagerScreenControlError(f"{field} must be a positive integer")
    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManagerScreenControlError(f"{field} must be a non-negative integer")
    return value


def _aware(value: dt.datetime, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreenControlError(f"{field} must include a UTC offset")
    return value


def _parse_datetime(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ManagerScreenControlError(f"{field} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManagerScreenControlError(f"{field} must be an ISO timestamp") from exc
    return _aware(parsed, field)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreenControlError(
            "manager-screen control asset escaped the repository"
        ) from exc
