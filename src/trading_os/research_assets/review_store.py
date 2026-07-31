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
INTAKE_KEYS = {
    "mode",
    "manager_screen_run_id",
    "coverage_root",
    "underwriting_approval_path",
    "underwriting_approval_sha256",
}
INTAKE_MODES = {"legacy_unbound", "underwriting_approval"}
SCOPE_TYPES = {"industry", "theme", "full_market", "custom"}
SCOPE_MARKETS = {"CN", "HK", "US", "MULTI"}
FAILURE_STATUSES = {
    ReviewRunStatus.BLOCKED_MISSING_EVIDENCE.value,
    ReviewRunStatus.FAILED_AGENT.value,
    ReviewRunStatus.FAILED_VALIDATION.value,
    ReviewRunStatus.STALE_QUOTES.value,
    ReviewRunStatus.CANCELLED.value,
}
STATE_TRANSACTION_FILE = ".state-transaction.json"
STATE_TRANSACTION_KEYS = {
    "schema_version",
    "run_id",
    "old_state",
    "new_state",
    "event",
    "prior_event_count",
    "prior_events_sha256",
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
        ReviewRunStatus.PORTFOLIO_CHALLENGING.value,
        ReviewRunStatus.SYNTHESIZING.value,
    },
    ReviewRunStatus.PORTFOLIO_CHALLENGING.value: {
        ReviewRunStatus.COMPANY_REVIEWS_COMPLETE.value
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
        policy_snapshot_sha256: str,
        created_at: dt.datetime,
        parent_run_id: str | None = None,
        intake: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        _validate_run_id(run_id)
        _require_aware(created_at, "created_at")
        normalized_scope = _validate_scope(scope)
        normalized_policies = _validate_policy_versions(policy_versions)
        policy_snapshot_sha256 = _validate_sha256(
            policy_snapshot_sha256,
            "policy_snapshot_sha256",
        )
        if parent_run_id is not None:
            _validate_run_id(parent_run_id)
        normalized_intake = _validate_intake(intake)
        state = {
            "schema_version": 2,
            "run_id": run_id,
            "scope": normalized_scope,
            "status": ReviewRunStatus.CREATED.value,
            "created_at": created_at.isoformat(),
            "policy_versions": normalized_policies,
            "policy_snapshot_sha256": policy_snapshot_sha256,
            "candidate_set": {
                "frozen": False,
                "frozen_at": None,
                "sha256": None,
                "count": 0,
                "source_binding": _candidate_source_binding(normalized_intake),
            },
            "parent_run_id": parent_run_id,
            "intake": normalized_intake,
        }
        run_dir = self._run_dir(run_id)
        initial_event = {
            "sequence": 1,
            "event": "run_created",
            "from_status": None,
            "to_status": ReviewRunStatus.CREATED.value,
            "actor": "system",
            "at": created_at.isoformat(),
            "reason": None,
        }
        run_dir.mkdir(parents=True, exist_ok=True)
        _crash_failpoint("create_directory_ready")
        with _exclusive_lock(run_dir / ".state.lock"):
            self._recover_state_transaction(run_dir)
            tasks_path = run_dir / "agent_tasks"
            if tasks_path.exists() and not tasks_path.is_dir():
                raise ReviewStoreError(
                    f"review agent_tasks path is not a directory: {tasks_path}"
                )
            tasks_path.mkdir(exist_ok=True)
            _crash_failpoint("create_tasks_ready")
            state_path = run_dir / "state.json"
            event_path = run_dir / "events.jsonl"
            if state_path.exists() and event_path.exists():
                existing = self._load_run_unlocked(run_id)
                events = self._read_events_unlocked(run_id)
                if existing != state or events != [initial_event]:
                    raise ReviewStoreError(
                        f"run already exists with a different manifest: {run_id}"
                    )
                return existing
            if state_path.exists() and self._load_run_unlocked(run_id) != state:
                raise ReviewStoreError(
                    f"run already exists with a different manifest: {run_id}"
                )
            if event_path.exists():
                events = self._read_events_unlocked(run_id)
                if events != [initial_event]:
                    raise ReviewStoreError(
                        f"run already exists with a different manifest: {run_id}"
                    )
            self._commit_state_and_event(
                run_dir,
                old_state=None,
                new_state=state,
                entry=initial_event,
            )
            return state

    def load_run(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        if not run_dir.is_dir():
            return self._load_run_unlocked(run_id)
        with _exclusive_lock(run_dir / ".state.lock"):
            self._recover_state_transaction(run_dir)
            return self._load_run_unlocked(run_id)

    def _load_run_unlocked(self, run_id: str) -> dict[str, Any]:
        state = _read_json_object(self._run_dir(run_id) / "state.json", "review state")
        return _normalize_review_state(state, run_id=run_id)

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
            self._recover_state_transaction(run_dir)
            state = self._load_run_unlocked(run_id)
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
                "source_binding": _candidate_source_binding(state["intake"]),
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
            self._recover_state_transaction(run_dir)
            state = self._load_run_unlocked(run_id)
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
        run_dir = self._run_dir(run_id)
        if not run_dir.is_dir():
            return self._read_events_unlocked(run_id)
        with _exclusive_lock(run_dir / ".state.lock"):
            self._recover_state_transaction(run_dir)
            return self._read_events_unlocked(run_id)

    def _read_events_unlocked(self, run_id: str) -> list[dict[str, Any]]:
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

    def resume(
        self,
        run_id: str,
        *,
        actor: str,
        at: dt.datetime,
    ) -> dict[str, Any]:
        actor = _require_text(actor, "actor")
        _require_aware(at, "at")
        run_dir = self._run_dir(run_id)
        with _exclusive_lock(run_dir / ".state.lock"):
            self._recover_state_transaction(run_dir)
            state = self._load_run_unlocked(run_id)
            if state["status"] not in FAILURE_STATUSES:
                raise ReviewStoreError(
                    f"only a failed review run can resume, got {state['status']}"
                )
            events = self._read_events_unlocked(run_id)
            failure_event = events[-1]
            if failure_event["to_status"] != state["status"]:
                raise ReviewStoreError("failure event does not match current state")
            resume_status = failure_event["from_status"]
            if resume_status is None or resume_status in FAILURE_STATUSES:
                raise ReviewStoreError("review run has no safe pre-failure state")
            updated = dict(state)
            updated["status"] = resume_status
            self._write_state_and_event(
                run_dir,
                old_state=state,
                new_state=updated,
                event="run_resumed",
                actor=actor,
                at=at,
                reason=f"resume from {state['status']}",
            )
            return updated

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
        events = self._read_events_unlocked(str(old_state["run_id"]))
        entry = {
            "sequence": len(events) + 1,
            "event": event,
            "from_status": old_state["status"],
            "to_status": new_state["status"],
            "actor": actor,
            "at": at.isoformat(),
            "reason": reason,
        }
        self._commit_state_and_event(
            run_dir,
            old_state=old_state,
            new_state=new_state,
            entry=entry,
        )

    def _commit_state_and_event(
        self,
        run_dir: Path,
        *,
        old_state: Mapping[str, Any] | None,
        new_state: Mapping[str, Any],
        entry: Mapping[str, Any],
    ) -> None:
        event_path = run_dir / "events.jsonl"
        if old_state is None:
            prior_bytes = b""
            prior_events: list[dict[str, Any]] = []
        else:
            prior_bytes = event_path.read_bytes() if event_path.exists() else b""
            prior_events = (
                self._read_events_unlocked(str(new_state["run_id"]))
                if event_path.exists()
                else []
            )
            if prior_bytes and not prior_bytes.endswith(b"\n"):
                raise ReviewStoreError(
                    "review event log must end with a newline"
                )
        if entry.get("sequence") != len(prior_events) + 1:
            raise ReviewStoreError("review event sequence does not follow current log")
        transaction = {
            "schema_version": 1,
            "run_id": str(new_state["run_id"]),
            "old_state": dict(old_state) if old_state is not None else None,
            "new_state": dict(new_state),
            "event": dict(entry),
            "prior_event_count": len(prior_events),
            "prior_events_sha256": hashlib.sha256(prior_bytes).hexdigest(),
        }
        atomic_write_bytes(
            run_dir / STATE_TRANSACTION_FILE,
            canonical_json_bytes(transaction),
        )
        _crash_failpoint("transaction_prepared")
        self._apply_state_transaction(
            run_dir,
            transaction,
            failpoints=True,
        )

    def _recover_state_transaction(self, run_dir: Path) -> None:
        transaction_path = run_dir / STATE_TRANSACTION_FILE
        if not transaction_path.exists():
            return
        transaction = _read_json_object(
            transaction_path,
            "review state transaction",
        )
        self._apply_state_transaction(
            run_dir,
            transaction,
            failpoints=False,
        )

    def _apply_state_transaction(
        self,
        run_dir: Path,
        transaction: Mapping[str, Any],
        *,
        failpoints: bool,
    ) -> None:
        normalized = _validate_state_transaction(transaction, run_dir=run_dir)
        run_id = normalized["run_id"]
        old_state = normalized["old_state"]
        new_state = normalized["new_state"]
        state_path = run_dir / "state.json"
        if state_path.exists():
            current_state = self._load_run_unlocked(run_id)
            if current_state not in tuple(
                item for item in (old_state, new_state) if item is not None
            ):
                raise ReviewStoreError(
                    "review state conflicts with pending transaction"
                )
        elif old_state is not None:
            raise ReviewStoreError(
                "review state disappeared during pending transaction"
            )

        event_path = run_dir / "events.jsonl"
        current_bytes = event_path.read_bytes() if event_path.exists() else b""
        current_events = (
            self._read_events_unlocked(run_id)
            if event_path.exists()
            else []
        )
        prior_count = normalized["prior_event_count"]
        prior_sha256 = normalized["prior_events_sha256"]
        if len(current_events) == prior_count:
            if hashlib.sha256(current_bytes).hexdigest() != prior_sha256:
                raise ReviewStoreError(
                    "review event log conflicts with pending transaction"
                )
            if current_bytes and not current_bytes.endswith(b"\n"):
                raise ReviewStoreError(
                    "review event log must end with a newline"
                )
            updated_bytes = (
                current_bytes
                + canonical_json_bytes(normalized["event"])
                + b"\n"
            )
            event_needs_write = True
        elif len(current_events) == prior_count + 1:
            lines = current_bytes.splitlines(keepends=True)
            prefix = b"".join(lines[:prior_count])
            if (
                hashlib.sha256(prefix).hexdigest() != prior_sha256
                or current_events[-1] != normalized["event"]
            ):
                raise ReviewStoreError(
                    "review event log conflicts with pending transaction"
                )
            updated_bytes = current_bytes
            event_needs_write = False
        else:
            raise ReviewStoreError(
                "review event count conflicts with pending transaction"
            )

        atomic_write_bytes(state_path, canonical_json_bytes(new_state))
        if failpoints:
            _crash_failpoint("state_written")
        if event_needs_write:
            atomic_write_bytes(event_path, updated_bytes)
        if failpoints:
            _crash_failpoint("events_written")

        (run_dir / STATE_TRANSACTION_FILE).unlink(missing_ok=True)
        if failpoints:
            _crash_failpoint("transaction_cleared")

    def _run_dir(self, run_id: str) -> Path:
        _validate_run_id(run_id)
        return self.root / run_id

    def _task_path(self, run_id: str, task_id: str) -> Path:
        return self._run_dir(run_id) / "agent_tasks" / f"{task_id}.json"


def _validate_state_transaction(
    transaction: Mapping[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    if not isinstance(transaction, Mapping) or set(transaction) != STATE_TRANSACTION_KEYS:
        raise ReviewStoreError(
            "review state transaction fields do not match the v1 contract"
        )
    if transaction.get("schema_version") != 1:
        raise ReviewStoreError("review state transaction schema_version is invalid")
    run_id = _require_text(transaction.get("run_id"), "transaction.run_id")
    _validate_run_id(run_id)
    if run_dir.name != run_id:
        raise ReviewStoreError(
            "review state transaction run_id does not match its directory"
        )
    old_raw = transaction.get("old_state")
    if old_raw is not None and not isinstance(old_raw, Mapping):
        raise ReviewStoreError("transaction.old_state must be an object or null")
    new_raw = transaction.get("new_state")
    if not isinstance(new_raw, Mapping):
        raise ReviewStoreError("transaction.new_state must be an object")
    old_state = (
        _normalize_review_state(dict(old_raw), run_id=run_id)
        if old_raw is not None
        else None
    )
    new_state = _normalize_review_state(dict(new_raw), run_id=run_id)
    event = transaction.get("event")
    event_keys = {
        "sequence",
        "event",
        "from_status",
        "to_status",
        "actor",
        "at",
        "reason",
    }
    if not isinstance(event, Mapping) or set(event) != event_keys:
        raise ReviewStoreError("review state transaction event is invalid")
    prior_count = transaction.get("prior_event_count")
    if (
        isinstance(prior_count, bool)
        or not isinstance(prior_count, int)
        or prior_count < 0
    ):
        raise ReviewStoreError(
            "review state transaction prior_event_count is invalid"
        )
    prior_sha256 = _validate_sha256(
        transaction.get("prior_events_sha256"),
        "transaction.prior_events_sha256",
    )
    if (
        event.get("sequence") != prior_count + 1
        or event.get("from_status")
        != (old_state["status"] if old_state is not None else None)
        or event.get("to_status") != new_state["status"]
    ):
        raise ReviewStoreError(
            "review state transaction event binding is invalid"
        )
    if old_state is None and (
        prior_count != 0
        or prior_sha256 != hashlib.sha256(b"").hexdigest()
    ):
        raise ReviewStoreError(
            "review create transaction must start from an empty event log"
        )
    normalized_event = {
        "sequence": prior_count + 1,
        "event": _require_text(event.get("event"), "transaction.event"),
        "from_status": event.get("from_status"),
        "to_status": _require_text(
            event.get("to_status"),
            "transaction.event.to_status",
        ),
        "actor": _require_text(event.get("actor"), "transaction.event.actor"),
        "at": _parse_datetime(
            event.get("at"),
            "transaction.event.at",
        ).isoformat(),
        "reason": (
            None
            if event.get("reason") is None
            else _require_text(event.get("reason"), "transaction.event.reason")
        ),
    }
    if dict(event) != normalized_event:
        raise ReviewStoreError(
            "review state transaction event is not normalized"
        )
    return {
        "run_id": run_id,
        "old_state": old_state,
        "new_state": new_state,
        "event": normalized_event,
        "prior_event_count": prior_count,
        "prior_events_sha256": prior_sha256,
    }


def _normalize_review_state(
    value: Mapping[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    state = dict(value)
    if state.get("run_id") != run_id:
        raise ReviewStoreError("review state run_id does not match its directory")
    if "intake" not in state:
        state["intake"] = _validate_intake(None)
    else:
        state["intake"] = _validate_intake(state["intake"])
    candidate_set = state.get("candidate_set")
    if not isinstance(candidate_set, dict):
        raise ReviewStoreError("review candidate_set is invalid")
    candidate_set = dict(candidate_set)
    state["candidate_set"] = candidate_set
    expected_source = _candidate_source_binding(state["intake"])
    if "source_binding" not in candidate_set and expected_source is None:
        candidate_set["source_binding"] = None
    elif candidate_set.get("source_binding") != expected_source:
        raise ReviewStoreError(
            "review candidate_set source binding does not match intake"
        )
    return state


def _crash_failpoint(name: str) -> None:
    """Test hook for simulating a process crash at durable write boundaries."""

    del name


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


def _validate_intake(value: Mapping[str, Any] | None) -> dict[str, str | None]:
    if value is None:
        return {
            "mode": "legacy_unbound",
            "manager_screen_run_id": None,
            "coverage_root": None,
            "underwriting_approval_path": None,
            "underwriting_approval_sha256": None,
        }
    if not isinstance(value, Mapping) or set(value) != INTAKE_KEYS:
        raise ReviewStoreError(f"intake fields must be {sorted(INTAKE_KEYS)}")
    mode = _require_text(value.get("mode"), "intake.mode")
    if mode not in INTAKE_MODES:
        raise ReviewStoreError(f"unsupported review intake mode: {mode}")
    if mode == "legacy_unbound":
        approval_keys = {
            "manager_screen_run_id",
            "underwriting_approval_path",
            "underwriting_approval_sha256",
        }
        if any(value.get(key) is not None for key in approval_keys):
            raise ReviewStoreError("legacy_unbound intake cannot carry approval bindings")
        coverage_root = value.get("coverage_root")
        if coverage_root is not None:
            coverage_root = _require_text(
                coverage_root,
                "intake.coverage_root",
            )
        return {
            "mode": mode,
            "manager_screen_run_id": None,
            "coverage_root": coverage_root,
            "underwriting_approval_path": None,
            "underwriting_approval_sha256": None,
        }
    manager_run = _require_text(
        value.get("manager_screen_run_id"),
        "intake.manager_screen_run_id",
    )
    if not RUN_ID_RE.fullmatch(manager_run):
        raise ReviewStoreError("intake.manager_screen_run_id is invalid")
    return {
        "mode": mode,
        "manager_screen_run_id": manager_run,
        "coverage_root": _require_text(
            value.get("coverage_root"), "intake.coverage_root"
        ),
        "underwriting_approval_path": _require_text(
            value.get("underwriting_approval_path"),
            "intake.underwriting_approval_path",
        ),
        "underwriting_approval_sha256": _validate_sha256(
            value.get("underwriting_approval_sha256"),
            "intake.underwriting_approval_sha256",
        ),
    }


def _candidate_source_binding(
    intake: Mapping[str, Any],
) -> dict[str, str] | None:
    if intake.get("mode") != "underwriting_approval":
        return None
    return {
        "type": "underwriting_approval",
        "path": str(intake["underwriting_approval_path"]),
        "sha256": str(intake["underwriting_approval_sha256"]),
    }


def _validate_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ReviewStoreError(f"{label} must be a lowercase SHA-256 digest")
    return value


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
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
        os.fsync(handle.fileno())
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise ReviewStoreError(f"review store is busy: {path}") from exc
    try:
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


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
