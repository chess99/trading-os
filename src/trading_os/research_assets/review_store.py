from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from .models import ReviewRunStatus
from .sealing import atomic_write_bytes, canonical_json_bytes


class ReviewStoreError(ValueError):
    """Raised when a review run, transition, or task lease is invalid."""


@dataclass(frozen=True, slots=True)
class TaskLease:
    run_id: str
    task_id: str
    owner: str
    status: str
    acquired_at: dt.datetime
    expires_at: dt.datetime
    attempt: int
    completed_at: dt.datetime | None
    result_path: str | None


RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]+$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]+$")
SYMBOL_RE = re.compile(r"^(CN|HK|US):[A-Z0-9.]+$")
SCOPE_KEYS = {"type", "market", "description"}
CANDIDATE_KEYS = {"symbol", "name", "target_company_dir"}
SCOPE_TYPES = {"industry", "theme", "full_market", "custom"}
SCOPE_MARKETS = {"CN", "HK", "US", "MULTI"}
FAILURE_STATUSES = {
    ReviewRunStatus.BLOCKED_MISSING_EVIDENCE.value,
    ReviewRunStatus.FAILED_AGENT.value,
    ReviewRunStatus.FAILED_VALIDATION.value,
    ReviewRunStatus.STALE_QUOTES.value,
    ReviewRunStatus.CANCELLED.value,
}
ALLOWED_TRANSITIONS = {
    ReviewRunStatus.CREATED.value: {ReviewRunStatus.CANDIDATES_FROZEN.value},
    ReviewRunStatus.CANDIDATES_FROZEN.value: {ReviewRunStatus.PACKETS_READY.value},
    ReviewRunStatus.PACKETS_READY.value: {ReviewRunStatus.BLIND_REVIEWING.value},
    ReviewRunStatus.BLIND_REVIEWING.value: {ReviewRunStatus.BLIND_SEALED.value},
    ReviewRunStatus.BLIND_SEALED.value: {ReviewRunStatus.REVEALING.value},
    ReviewRunStatus.REVEALING.value: {
        ReviewRunStatus.CHALLENGING.value,
        ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value,
    },
    ReviewRunStatus.CHALLENGING.value: {
        ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value
    },
    ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value: {
        ReviewRunStatus.SYNTHESIZING.value
    },
    ReviewRunStatus.SYNTHESIZING.value: {ReviewRunStatus.COMPLETED.value},
}


class ReviewRunStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def create_run(
        self,
        run_id: str,
        *,
        scope: Mapping[str, Any],
        policy_versions: Mapping[str, str],
        created_at: dt.datetime,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        _validate_run_id(run_id)
        _require_aware(created_at, "created_at")
        normalized_scope = _validate_scope(scope)
        normalized_policies = _validate_policy_versions(policy_versions)
        if parent_run_id is not None:
            _validate_run_id(parent_run_id)
        state = {
            "schema_version": 2,
            "run_id": run_id,
            "scope": normalized_scope,
            "status": ReviewRunStatus.CREATED.value,
            "created_at": created_at.isoformat(),
            "policy_versions": normalized_policies,
            "candidate_set": {
                "frozen": False,
                "frozen_at": None,
                "sha256": None,
                "count": 0,
            },
            "parent_run_id": parent_run_id,
        }
        run_dir = self._run_dir(run_id)
        state_path = run_dir / "state.json"
        if run_dir.exists():
            existing = self.load_run(run_id)
            if existing != state:
                raise ReviewStoreError(f"run already exists with a different manifest: {run_id}")
            return existing
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            existing = self.load_run(run_id)
            if existing != state:
                raise ReviewStoreError(
                    f"run already exists with a different manifest: {run_id}"
                ) from None
            return existing
        (run_dir / "agent_tasks").mkdir()
        atomic_write_bytes(state_path, canonical_json_bytes(state))
        initial_event = {
            "sequence": 1,
            "event": "run_created",
            "from_status": None,
            "to_status": ReviewRunStatus.CREATED.value,
            "actor": "system",
            "at": created_at.isoformat(),
            "reason": None,
        }
        atomic_write_bytes(
            run_dir / "events.jsonl", canonical_json_bytes(initial_event) + b"\n"
        )
        return state

    def load_run(self, run_id: str) -> dict[str, Any]:
        state = _read_json_object(self._run_dir(run_id) / "state.json", "review state")
        if state.get("run_id") != run_id:
            raise ReviewStoreError("review state run_id does not match its directory")
        return state

    def freeze_candidates(
        self,
        run_id: str,
        candidates: list[Mapping[str, Any]],
        *,
        actor: str,
        at: dt.datetime,
    ) -> dict[str, Any]:
        actor = _require_text(actor, "actor")
        _require_aware(at, "at")
        normalized = _normalize_candidates(candidates)
        content = b"".join(canonical_json_bytes(item) + b"\n" for item in normalized)
        digest = hashlib.sha256(content).hexdigest()
        run_dir = self._run_dir(run_id)
        with _exclusive_lock(run_dir / ".state.lock"):
            state = self.load_run(run_id)
            candidate_path = run_dir / "candidates.jsonl"
            if state["candidate_set"]["frozen"]:
                if (
                    state["candidate_set"]["sha256"] == digest
                    and candidate_path.is_file()
                    and candidate_path.read_bytes() == content
                ):
                    return state
                raise ReviewStoreError("candidate set is frozen and cannot change")
            if state.get("status") != ReviewRunStatus.CREATED.value:
                raise ReviewStoreError("candidates can only be frozen from created")
            atomic_write_bytes(candidate_path, content)
            updated = dict(state)
            updated["candidate_set"] = {
                "frozen": True,
                "frozen_at": at.isoformat(),
                "sha256": digest,
                "count": len(normalized),
            }
            updated["status"] = ReviewRunStatus.CANDIDATES_FROZEN.value
            self._write_state_and_event(
                run_dir,
                old_state=state,
                new_state=updated,
                event="candidates_frozen",
                actor=actor,
                at=at,
                reason=None,
            )
            return updated

    def read_candidates(self, run_id: str) -> list[dict[str, Any]]:
        state = self.load_run(run_id)
        if not state["candidate_set"]["frozen"]:
            raise ReviewStoreError("candidate set is not frozen")
        path = self._run_dir(run_id) / "candidates.jsonl"
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != state["candidate_set"]["sha256"]:
            raise ReviewStoreError("candidate snapshot sha256 mismatch")
        items: list[dict[str, Any]] = []
        for line_number, line in enumerate(content.decode("utf-8").splitlines(), start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReviewStoreError(
                    f"invalid candidate JSONL at line {line_number}"
                ) from exc
            if not isinstance(item, dict):
                raise ReviewStoreError(f"candidate line {line_number} must be an object")
            items.append(item)
        if len(items) != state["candidate_set"]["count"]:
            raise ReviewStoreError("candidate snapshot count mismatch")
        return items

    def transition(
        self,
        run_id: str,
        to_status: str,
        *,
        actor: str,
        at: dt.datetime,
        reason: str | None = None,
    ) -> dict[str, Any]:
        actor = _require_text(actor, "actor")
        _require_aware(at, "at")
        known_statuses = {item.value for item in ReviewRunStatus}
        if to_status not in known_statuses:
            raise ReviewStoreError(f"unknown review status: {to_status}")
        if reason is not None:
            reason = _require_text(reason, "reason")
        run_dir = self._run_dir(run_id)
        with _exclusive_lock(run_dir / ".state.lock"):
            state = self.load_run(run_id)
            from_status = str(state["status"])
            if from_status == to_status:
                return state
            allowed = set(ALLOWED_TRANSITIONS.get(from_status, set()))
            if from_status not in FAILURE_STATUSES and from_status != "completed":
                allowed.update(FAILURE_STATUSES)
            if to_status not in allowed:
                raise ReviewStoreError(
                    f"illegal review state transition: {from_status} -> {to_status}"
                )
            updated = dict(state)
            updated["status"] = to_status
            self._write_state_and_event(
                run_dir,
                old_state=state,
                new_state=updated,
                event="state_transition",
                actor=actor,
                at=at,
                reason=reason,
            )
            return updated

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        path = self._run_dir(run_id) / "events.jsonl"
        if not path.is_file():
            raise ReviewStoreError(f"event log is missing for run: {run_id}")
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReviewStoreError(f"invalid event JSON at line {line_number}") from exc
            if not isinstance(event, dict):
                raise ReviewStoreError(f"event line {line_number} must be an object")
            if event.get("sequence") != line_number:
                raise ReviewStoreError(
                    f"event sequence mismatch at line {line_number}: {event.get('sequence')}"
                )
            events.append(event)
        return events

    def acquire_lease(
        self,
        run_id: str,
        task_id: str,
        *,
        owner: str,
        now: dt.datetime,
        ttl_seconds: int,
    ) -> TaskLease:
        self.load_run(run_id)
        _validate_task_id(task_id)
        owner = _require_text(owner, "owner")
        _require_aware(now, "now")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ReviewStoreError("ttl_seconds must be a positive integer")
        task_path = self._task_path(run_id, task_id)
        with _exclusive_lock(task_path.with_name(task_path.name + ".lock")):
            if task_path.exists():
                existing = _read_lease(task_path)
                if existing.status == "completed":
                    if existing.owner == owner:
                        return existing
                    raise ReviewStoreError(f"task is already completed: {task_id}")
                if existing.owner == owner and now <= existing.expires_at:
                    return existing
                if now <= existing.expires_at:
                    raise ReviewStoreError(
                        "task is leased by "
                        f"{existing.owner} until {existing.expires_at.isoformat()}"
                    )
                attempt = existing.attempt + 1
            else:
                attempt = 1
            lease = TaskLease(
                run_id=run_id,
                task_id=task_id,
                owner=owner,
                status="leased",
                acquired_at=now,
                expires_at=now + dt.timedelta(seconds=ttl_seconds),
                attempt=attempt,
                completed_at=None,
                result_path=None,
            )
            _write_lease(task_path, lease)
            return lease

    def complete_lease(
        self,
        run_id: str,
        task_id: str,
        *,
        owner: str,
        completed_at: dt.datetime,
        result_path: str,
    ) -> TaskLease:
        self.load_run(run_id)
        _validate_task_id(task_id)
        owner = _require_text(owner, "owner")
        result_path = _require_text(result_path, "result_path")
        _require_aware(completed_at, "completed_at")
        task_path = self._task_path(run_id, task_id)
        with _exclusive_lock(task_path.with_name(task_path.name + ".lock")):
            if not task_path.is_file():
                raise ReviewStoreError(f"task has no active lease: {task_id}")
            existing = _read_lease(task_path)
            if existing.owner != owner:
                raise ReviewStoreError(
                    f"only lease owner {existing.owner} can complete task {task_id}"
                )
            if existing.status == "completed":
                if (
                    existing.completed_at == completed_at
                    and existing.result_path == result_path
                ):
                    return existing
                raise ReviewStoreError("completed task result is immutable")
            completed = TaskLease(
                run_id=run_id,
                task_id=task_id,
                owner=owner,
                status="completed",
                acquired_at=existing.acquired_at,
                expires_at=existing.expires_at,
                attempt=existing.attempt,
                completed_at=completed_at,
                result_path=result_path,
            )
            _write_lease(task_path, completed)
            return completed

    def release_lease(
        self, run_id: str, task_id: str, *, owner: str
    ) -> None:
        self.load_run(run_id)
        _validate_task_id(task_id)
        owner = _require_text(owner, "owner")
        task_path = self._task_path(run_id, task_id)
        with _exclusive_lock(task_path.with_name(task_path.name + ".lock")):
            if not task_path.is_file():
                return
            existing = _read_lease(task_path)
            if existing.owner != owner:
                raise ReviewStoreError(
                    f"only lease owner {existing.owner} can release task {task_id}"
                )
            if existing.status == "completed":
                raise ReviewStoreError("completed task lease cannot be released")
            task_path.unlink()

    def _write_state_and_event(
        self,
        run_dir: Path,
        *,
        old_state: Mapping[str, Any],
        new_state: Mapping[str, Any],
        event: str,
        actor: str,
        at: dt.datetime,
        reason: str | None,
    ) -> None:
        events = self.read_events(str(old_state["run_id"]))
        entry = {
            "sequence": len(events) + 1,
            "event": event,
            "from_status": old_state["status"],
            "to_status": new_state["status"],
            "actor": actor,
            "at": at.isoformat(),
            "reason": reason,
        }
        atomic_write_bytes(run_dir / "state.json", canonical_json_bytes(new_state))
        with (run_dir / "events.jsonl").open("ab") as handle:
            handle.write(canonical_json_bytes(entry) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _run_dir(self, run_id: str) -> Path:
        _validate_run_id(run_id)
        return self.root / run_id

    def _task_path(self, run_id: str, task_id: str) -> Path:
        return self._run_dir(run_id) / "agent_tasks" / f"{task_id}.json"


def _normalize_candidates(candidates: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(candidates, list) or not candidates:
        raise ReviewStoreError("candidate set must be a non-empty array")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise ReviewStoreError(f"candidate {index} must be an object")
        if set(candidate) != CANDIDATE_KEYS:
            raise ReviewStoreError(
                f"candidate {index} fields must be {sorted(CANDIDATE_KEYS)}"
            )
        symbol = _require_text(candidate.get("symbol"), f"candidate {index} symbol")
        if not SYMBOL_RE.fullmatch(symbol):
            raise ReviewStoreError(f"candidate {index} symbol is invalid: {symbol}")
        if symbol in seen:
            raise ReviewStoreError(f"duplicate candidate symbol: {symbol}")
        seen.add(symbol)
        normalized.append(
            {
                "symbol": symbol,
                "name": _require_text(candidate.get("name"), f"candidate {index} name"),
                "target_company_dir": _require_text(
                    candidate.get("target_company_dir"),
                    f"candidate {index} target_company_dir",
                ),
            }
        )
    return sorted(normalized, key=lambda item: item["symbol"])


def _validate_scope(scope: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(scope, Mapping) or set(scope) != SCOPE_KEYS:
        raise ReviewStoreError(f"scope fields must be {sorted(SCOPE_KEYS)}")
    scope_type = _require_text(scope.get("type"), "scope.type")
    market = _require_text(scope.get("market"), "scope.market")
    if scope_type not in SCOPE_TYPES:
        raise ReviewStoreError(f"unsupported scope type: {scope_type}")
    if market not in SCOPE_MARKETS:
        raise ReviewStoreError(f"unsupported scope market: {market}")
    return {
        "type": scope_type,
        "market": market,
        "description": _require_text(scope.get("description"), "scope.description"),
    }


def _validate_policy_versions(policy_versions: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(policy_versions, Mapping) or not policy_versions:
        raise ReviewStoreError("policy_versions must be a non-empty object")
    normalized: dict[str, str] = {}
    for policy_id, version in policy_versions.items():
        normalized[_require_text(policy_id, "policy_id")] = _require_text(
            version, "policy version"
        )
    return dict(sorted(normalized.items()))


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ReviewStoreError(f"{label} is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewStoreError(f"invalid {label} JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ReviewStoreError(f"{label} must be an object")
    return payload


def _write_lease(path: Path, lease: TaskLease) -> None:
    payload = {
        "schema_version": 2,
        "run_id": lease.run_id,
        "task_id": lease.task_id,
        "owner": lease.owner,
        "status": lease.status,
        "acquired_at": lease.acquired_at.isoformat(),
        "expires_at": lease.expires_at.isoformat(),
        "attempt": lease.attempt,
        "completed_at": (
            lease.completed_at.isoformat() if lease.completed_at is not None else None
        ),
        "result_path": lease.result_path,
    }
    atomic_write_bytes(path, canonical_json_bytes(payload))


def _read_lease(path: Path) -> TaskLease:
    payload = _read_json_object(path, "task lease")
    return TaskLease(
        run_id=_require_text(payload.get("run_id"), "lease.run_id"),
        task_id=_require_text(payload.get("task_id"), "lease.task_id"),
        owner=_require_text(payload.get("owner"), "lease.owner"),
        status=_require_text(payload.get("status"), "lease.status"),
        acquired_at=_parse_datetime(payload.get("acquired_at"), "lease.acquired_at"),
        expires_at=_parse_datetime(payload.get("expires_at"), "lease.expires_at"),
        attempt=_require_positive_int(payload.get("attempt"), "lease.attempt"),
        completed_at=(
            None
            if payload.get("completed_at") is None
            else _parse_datetime(payload.get("completed_at"), "lease.completed_at")
        ),
        result_path=(
            None
            if payload.get("result_path") is None
            else _require_text(payload.get("result_path"), "lease.result_path")
        ),
    )


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ReviewStoreError(f"review store is busy: {path}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise ReviewStoreError(f"invalid run_id: {run_id!r}")


def _validate_task_id(task_id: str) -> None:
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise ReviewStoreError(f"invalid task_id: {task_id!r}")


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewStoreError(f"{label} must be a non-empty string")
    return value.strip()


def _require_aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ReviewStoreError(f"{label} must include timezone information")


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ReviewStoreError(f"{label} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReviewStoreError(f"{label} must be an ISO datetime") from exc
    _require_aware(parsed, label)
    return parsed


def _require_positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ReviewStoreError(f"{label} must be a positive integer")
    return value
