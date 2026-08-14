from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

STATE_PATH = Path("coverage/cn-a/research_state.jsonl")
WATCHLIST_PATH = Path("research/watchlist.jsonl")
QUEUE_PATH = Path("coverage/cn-a/research_queue.jsonl")

_SYMBOL_RE = re.compile(r"^CN:\d{6}$")
_DATED_MARKDOWN_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})(?:-(?P<sequence>\d{2}))?\.md$"
)
_FORMAL_REPORT_RE = _DATED_MARKDOWN_RE
_SECURITY_PRICE_TRIGGER_RE = re.compile(
    r"收盘价|股价|价格线|价格触发|重新武装|重装触发器|关注价|买入价|安全边际价格"
)
_REPORT_DEFERRAL_RE = re.compile(
    r"本次裁决不重复发明|完整业务分析可沿时间线回看|"
    r"(?:详见|参见|请回看).{0,20}(?:前序|上一版|历史|原)报告|"
    r"本报告不再重复.{0,20}(?:前序|上一版|历史|原)报告|"
    r"(?:前序|上一版|历史|原)报告.{0,30}(?:继续有效|共同部分)"
)
_REPORT_SECURITY_PRICE_LINE_RE = re.compile(
    r"关注价(?:格)?|买入价|重新武装|安全边际价格|"
    r"price_levels|price_monitor|deep_review|rearm_above"
)
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class ResearchFlowError(RuntimeError):
    """Base error for the compact research workflow."""


class ValidationError(ResearchFlowError, ValueError):
    """Raised before an invalid workflow mutation is written."""


class StateCorruptionError(ResearchFlowError):
    """Raised when a persisted JSONL file is malformed or internally inconsistent."""


STATE_SCHEMA_VERSION = 3


class UniverseStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CompanyStatus(str, Enum):
    UNSEEN = "unseen"
    IGNORE = "ignore"
    CANDIDATE = "candidate"
    COVERED = "covered"
    STALE = "stale"


class ScreenRoute(str, Enum):
    IGNORE = "ignore"
    RESEARCH_NOW = "research_now"


class ScreenMode(str, Enum):
    BASELINE = "baseline"
    EVENT = "event"


class ResearchOutcome(str, Enum):
    IGNORE = "ignore"
    COVERED = "covered"


class UpdateImpact(str, Enum):
    REAFFIRMED = "reaffirmed"
    MONITOR = "monitor"
    INVALIDATED = "invalidated"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"


@dataclass(frozen=True)
class CompanyRef:
    symbol: str
    name: str | None = None


@dataclass(frozen=True)
class ValueRange:
    low: float
    high: float
    currency: str = "CNY"


@dataclass(frozen=True)
class ScreenDecision:
    symbol: str
    route: ScreenRoute | str
    reason: str
    name: str | None = None
    event_triggers: Sequence[str] = field(default_factory=tuple)
    source_urls: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResearchResult:
    symbol: str
    outcome: ResearchOutcome | str
    summary: str
    key_logic: Sequence[str]
    risks: Sequence[str]
    value_range: ValueRange | None
    event_triggers: Sequence[str]
    source_urls: Sequence[str]
    information_cutoff: str
    name: str | None = None
    report_markdown: str | None = None
    valuation_note: str | None = None


@dataclass(frozen=True)
class ResearchUpdate:
    symbol: str
    title: str
    impact: UpdateImpact | str
    reviewed_at: str
    information_cutoff: str
    summary: str
    analysis: str
    conclusion: str
    source_urls: Sequence[str]
    event_ids: Sequence[str] = field(default_factory=tuple)
    invalidation_reason: str | None = None


@dataclass(frozen=True)
class ResearchUpdateRecord:
    symbol: str
    impact: UpdateImpact
    update_path: str
    status: CompanyStatus
    enqueued_task: ResearchTask | None


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    symbol: str
    trigger_kind: str
    trigger_id: str
    reason: str
    enqueued_at: str
    status: TaskStatus
    name: str | None = None
    started_at: str | None = None

    @property
    def trigger_key(self) -> str:
        return f"{self.trigger_kind}:{self.trigger_id}"


@dataclass(frozen=True)
class ScreeningUpdate:
    total: int
    ignored: int
    candidates: int
    enqueued_tasks: tuple[ResearchTask, ...]
    deduplicated: int


@dataclass(frozen=True)
class UniverseSyncUpdate:
    total: int
    added: int
    reactivated: int
    inactivated: int
    renamed: int
    enqueued_tasks: tuple[ResearchTask, ...]


@dataclass(frozen=True)
class ResearchFlowStatus:
    companies: int
    active: int
    inactive: int
    unseen: int
    ignored: int
    candidates: int
    covered: int
    stale: int
    watchlist: int
    queued: int
    running: int


def _thread_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    """Serialize writers in this process and across local coordinator processes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    local_lock = _thread_lock(path)
    with local_lock:
        handle = path.open("a+b")
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            acquired = True
            yield
        finally:
            try:
                if acquired:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def _atomic_write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for record in records
    ]
    content = (("\n".join(lines) + "\n") if lines else "").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def _atomic_write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise StateCorruptionError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise StateCorruptionError(f"{path}:{line_number}: each JSONL row must be an object")
        records.append(item)
    return records


def _enum_value(value: Enum | str, enum_type: type[Enum], label: str) -> str:
    raw = value.value if isinstance(value, Enum) else value
    try:
        return str(enum_type(raw).value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValidationError(f"{label} must be one of: {allowed}") from exc


def _symbol(value: str) -> str:
    normalized = str(value).strip().upper()
    if not _SYMBOL_RE.fullmatch(normalized):
        raise ValidationError("symbol must use the CN:000000 form")
    return normalized


def _nonblank(value: str, label: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{label} must not be blank")
    return normalized


def _optional_name(value: str | None) -> str | None:
    if value is None:
        return None
    return _nonblank(value, "name")


def _number(value: float | int, label: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{label} must be a finite non-negative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValidationError(f"{label} must be a finite non-negative number")
    return result


def _strings(values: Sequence[str], label: str) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise ValidationError(f"{label} must be a sequence of strings")
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _nonblank(value, label)
        if normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _urls(values: Sequence[str]) -> list[str]:
    output = _strings(values, "source URL")
    for value in output:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError(f"source URL must be an absolute http(s) URL: {value}")
    return output


def _event_triggers(values: Sequence[str]) -> list[str]:
    output = _strings(values, "event trigger")
    security_price_triggers = [
        value for value in output if _SECURITY_PRICE_TRIGGER_RE.search(value)
    ]
    if security_price_triggers:
        raise ValidationError(
            "event triggers must be business, financial, governance, or industry facts; "
            "security-price triggers are not research triggers"
        )
    return output


def _without_security_price_triggers(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        value
        for value in values
        if isinstance(value, str) and not _SECURITY_PRICE_TRIGGER_RE.search(value)
    ]


def _migrated_screening(value: object) -> object:
    if not isinstance(value, dict):
        return value
    screening = dict(value)
    for field_name in ("price_levels", "price_monitor", "buy_below", "rearm_above"):
        screening.pop(field_name, None)
    screening["event_triggers"] = _without_security_price_triggers(
        screening.get("event_triggers")
    )
    return screening


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    else:
        raw = _nonblank(value, "timestamp")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(f"invalid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError("timestamp must include a timezone")
    return parsed.isoformat()


def _value_range(value: ValueRange | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, ValueRange):
        raise ValidationError("value_range must be a ValueRange or None")
    low = _number(value.low, "value_range.low")
    high = _number(value.high, "value_range.high")
    if low > high:
        raise ValidationError("value_range.low must not exceed value_range.high")
    return {"low": low, "high": high, "currency": _nonblank(value.currency, "currency")}


def _task_id(symbol: str, trigger_key: str) -> str:
    digest = hashlib.sha256(f"{symbol}\0{trigger_key}".encode()).hexdigest()
    return digest[:24]


def _empty_state(symbol: str, name: str | None, at: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "symbol": symbol,
        "name": name,
        "universe_status": UniverseStatus.ACTIVE.value,
        "status": CompanyStatus.UNSEEN.value,
        "updated_at": at,
        "summary": None,
        "key_logic": [],
        "risks": [],
        "value_range": None,
        "event_triggers": [],
        "source_urls": [],
        "last_screening": None,
        "last_research_at": None,
        "information_cutoff": None,
        "report_path": None,
        "valuation_note": None,
        "candidate_since": None,
        "invalidation": None,
        "last_update": None,
        "processed_triggers": [],
    }


def _task_from_row(row: Mapping[str, Any]) -> ResearchTask:
    try:
        return ResearchTask(
            task_id=_nonblank(row["task_id"], "task_id"),
            symbol=_symbol(row["symbol"]),
            trigger_kind=_nonblank(row["trigger_kind"], "trigger_kind"),
            trigger_id=_nonblank(row["trigger_id"], "trigger_id"),
            reason=_nonblank(row["reason"], "reason"),
            enqueued_at=_timestamp(row["enqueued_at"]),
            status=TaskStatus(_enum_value(row["status"], TaskStatus, "task status")),
            name=_optional_name(row.get("name")),
            started_at=(_timestamp(row["started_at"]) if row.get("started_at") else None),
        )
    except KeyError as exc:
        raise StateCorruptionError(f"queue row is missing {exc.args[0]}") from exc


def _task_row(task: ResearchTask) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "task_id": task.task_id,
        "symbol": task.symbol,
        "name": task.name,
        "trigger_kind": task.trigger_kind,
        "trigger_id": task.trigger_id,
        "reason": task.reason,
        "enqueued_at": task.enqueued_at,
        "status": task.status.value,
        "started_at": task.started_at,
    }


class ResearchFlow:
    """Small, single-writer coordinator for screening and company research.

    Worker agents receive :class:`ResearchTask` objects and return one
    :class:`ResearchResult`. They do not need to mutate any shared file. The
    caller decides how many tasks to dispatch concurrently.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        state_path: str | Path = STATE_PATH,
        watchlist_path: str | Path = WATCHLIST_PATH,
        queue_path: str | Path = QUEUE_PATH,
    ) -> None:
        self.root = Path(root)
        self.state_path = self._resolve(state_path)
        self.watchlist_path = self._resolve(watchlist_path)
        self.queue_path = self._resolve(queue_path)
        self.lock_path = self.state_path.with_suffix(self.state_path.suffix + ".lock")

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _states(self) -> dict[str, dict[str, Any]]:
        rows = _read_jsonl(self.state_path)
        states: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                symbol = _symbol(row["symbol"])
                _enum_value(row["universe_status"], UniverseStatus, "universe status")
                _enum_value(row["status"], CompanyStatus, "company status")
            except KeyError as exc:
                raise StateCorruptionError(f"state row is missing {exc.args[0]}") from exc
            if symbol in states:
                raise StateCorruptionError(f"duplicate state row for {symbol}")
            states[symbol] = dict(row)
        return states

    def _tasks(self) -> list[ResearchTask]:
        tasks = [_task_from_row(row) for row in _read_jsonl(self.queue_path)]
        seen: set[str] = set()
        for task in tasks:
            expected_id = _task_id(task.symbol, task.trigger_key)
            if task.task_id != expected_id:
                raise StateCorruptionError(
                    f"task ID does not match symbol and trigger: {task.task_id}"
                )
            if task.task_id in seen:
                raise StateCorruptionError(f"duplicate queue task: {task.task_id}")
            seen.add(task.task_id)
        return tasks

    def _write_tasks(self, tasks: Sequence[ResearchTask]) -> None:
        ordered = sorted(tasks, key=lambda task: (task.enqueued_at, task.task_id))
        _atomic_write_jsonl(self.queue_path, (_task_row(task) for task in ordered))

    @staticmethod
    def _watch_rows(states: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for symbol in sorted(states):
            state = states[symbol]
            if (
                state.get("universe_status") != UniverseStatus.ACTIVE.value
                or state.get("status") != CompanyStatus.COVERED.value
            ):
                continue
            rows.append(
                {
                    "schema_version": STATE_SCHEMA_VERSION,
                    "symbol": symbol,
                    "name": state.get("name"),
                    "status": state["status"],
                    "summary": state.get("summary"),
                    "key_logic": list(state.get("key_logic") or []),
                    "risks": list(state.get("risks") or []),
                    "value_range": state.get("value_range"),
                    "event_triggers": list(state.get("event_triggers") or []),
                    "source_urls": list(state.get("source_urls") or []),
                    "last_research_at": state.get("last_research_at"),
                    "information_cutoff": state.get("information_cutoff"),
                    "report_path": state.get("report_path"),
                    "valuation_note": state.get("valuation_note"),
                    "updated_at": state.get("updated_at"),
                }
            )
        return rows

    def _write_states(self, states: Mapping[str, Mapping[str, Any]]) -> None:
        _atomic_write_jsonl(self.state_path, (states[symbol] for symbol in sorted(states)))
        _atomic_write_jsonl(self.watchlist_path, self._watch_rows(states))

    @staticmethod
    def _enqueue(
        tasks: list[ResearchTask],
        state: Mapping[str, Any],
        *,
        symbol: str,
        name: str | None,
        trigger_kind: str,
        trigger_id: str,
        reason: str,
        at: str,
    ) -> ResearchTask | None:
        kind = _nonblank(trigger_kind, "trigger_kind")
        identifier = _nonblank(trigger_id, "trigger_id")
        trigger_key = f"{kind}:{identifier}"
        identifier_hash = _task_id(symbol, trigger_key)
        processed = set(state.get("processed_triggers") or [])
        if (
            trigger_key in processed
            or any(task.task_id == identifier_hash for task in tasks)
            or any(task.symbol == symbol for task in tasks)
        ):
            return None
        task = ResearchTask(
            task_id=identifier_hash,
            symbol=symbol,
            name=name,
            trigger_kind=kind,
            trigger_id=identifier,
            reason=_nonblank(reason, "reason"),
            enqueued_at=at,
            status=TaskStatus.QUEUED,
        )
        tasks.append(task)
        return task

    def migrate_state_v3(self, *, at: str | datetime | None = None) -> int:
        """Migrate legacy state into the event-driven schema.

        A legacy ``watch`` without a formal report becomes ``candidate`` and
        a legacy ``researched`` row becomes ``covered``. Version 2 rows lose
        all security-price alert state and security-price event text. The
        migration does not create research tasks.
        """

        timestamp = _timestamp(at)
        with _exclusive_lock(self.lock_path):
            rows = _read_jsonl(self.state_path)
            if not rows:
                return 0
            versions = {row.get("schema_version") for row in rows}
            if versions == {STATE_SCHEMA_VERSION}:
                states: dict[str, dict[str, Any]] = {}
                changed = 0
                for row in rows:
                    symbol = _symbol(row.get("symbol"))
                    state = dict(row)
                    migrated_screening = _migrated_screening(state.get("last_screening"))
                    if migrated_screening != state.get("last_screening"):
                        state["last_screening"] = migrated_screening
                        changed += 1
                    states[symbol] = state
                if changed:
                    self._write_states(states)
                return changed
            if versions == {2}:
                states: dict[str, dict[str, Any]] = {}
                for row in rows:
                    symbol = _symbol(row.get("symbol"))
                    state = dict(row)
                    state["schema_version"] = STATE_SCHEMA_VERSION
                    state.pop("price_levels", None)
                    state.pop("price_monitor", None)
                    state["event_triggers"] = _without_security_price_triggers(
                        state.get("event_triggers")
                    )
                    state["last_screening"] = _migrated_screening(
                        state.get("last_screening")
                    )
                    states[symbol] = state
                tasks = self._tasks()
                self._write_tasks(tasks)
                self._write_states(states)
                return len(rows)
            if versions != {1}:
                raise StateCorruptionError(
                    f"cannot migrate mixed or unsupported state schemas: {versions}"
                )

            states: dict[str, dict[str, Any]] = {}
            migrated_candidates: set[str] = set()
            for row in rows:
                symbol = _symbol(row.get("symbol"))
                legacy_status = _nonblank(row.get("status"), "legacy status")
                if legacy_status not in {"unseen", "ignore", "watch", "researched"}:
                    raise StateCorruptionError(
                        f"unsupported legacy company status for {symbol}: {legacy_status}"
                    )
                state = dict(row)
                state.update(
                    {
                        "schema_version": STATE_SCHEMA_VERSION,
                        "universe_status": UniverseStatus.ACTIVE.value,
                        "information_cutoff": row.get("last_research_at"),
                        "valuation_note": None,
                        "candidate_since": None,
                        "invalidation": None,
                    }
                )
                state.pop("price_levels", None)
                state.pop("price_monitor", None)
                state["event_triggers"] = _without_security_price_triggers(
                    state.get("event_triggers")
                )
                state["last_screening"] = _migrated_screening(
                    state.get("last_screening")
                )
                if legacy_status == "watch":
                    state["status"] = CompanyStatus.CANDIDATE.value
                    state["candidate_since"] = timestamp
                    state["value_range"] = None
                    state["report_path"] = None
                    state["last_research_at"] = None
                    state["information_cutoff"] = None
                    migrated_candidates.add(symbol)
                elif legacy_status == "researched":
                    state["status"] = CompanyStatus.COVERED.value
                elif legacy_status == "ignore":
                    state["status"] = CompanyStatus.IGNORE.value
                else:
                    state["status"] = CompanyStatus.UNSEEN.value
                states[symbol] = state

            legacy_tasks = _read_jsonl(self.queue_path)
            tasks: list[ResearchTask] = []
            for row in legacy_tasks:
                task_status = _nonblank(row.get("status"), "legacy task status")
                if task_status not in {"queued", "dispatched"}:
                    raise StateCorruptionError(f"unsupported legacy task status: {task_status}")
                task = ResearchTask(
                    task_id=_nonblank(row.get("task_id"), "task_id"),
                    symbol=_symbol(row.get("symbol")),
                    name=_optional_name(row.get("name")),
                    trigger_kind=_nonblank(row.get("trigger_kind"), "trigger_kind"),
                    trigger_id=_nonblank(row.get("trigger_id"), "trigger_id"),
                    reason=_nonblank(row.get("reason"), "reason"),
                    enqueued_at=_timestamp(row.get("enqueued_at")),
                    status=(
                        TaskStatus.RUNNING if task_status == "dispatched" else TaskStatus.QUEUED
                    ),
                    started_at=(
                        _timestamp(row.get("dispatched_at")) if row.get("dispatched_at") else None
                    ),
                )
                tasks.append(task)
                state = states[task.symbol]
                if state.get("report_path") is not None:
                    state["status"] = CompanyStatus.STALE.value
                    state["invalidation"] = {
                        "at": timestamp,
                        "reason": task.reason,
                        "screen_id": task.trigger_id,
                    }
                else:
                    state["status"] = CompanyStatus.CANDIDATE.value
                    state["candidate_since"] = state.get("candidate_since") or timestamp

            self._write_tasks(tasks)
            self._write_states(states)
        self.migrate_current_reports()
        return len(rows)

    def migrate_current_reports(self) -> int:
        """Move legacy ``current.md`` files into the immutable dated timeline."""

        created_targets: list[Path] = []
        current_paths: list[Path] = []
        with _exclusive_lock(self.lock_path):
            states = self._states()
            migrations: list[tuple[dict[str, Any], Path, Path]] = []
            for symbol, state in states.items():
                current = self._company_directory(symbol) / "current.md"
                current_relative = current.relative_to(self.root).as_posix()
                if state.get("report_path") != current_relative:
                    continue
                research_at = state.get("last_research_at")
                if not research_at:
                    raise StateCorruptionError(
                        f"cannot date legacy current report without last_research_at: {symbol}"
                    )
                if not current.is_file():
                    raise StateCorruptionError(f"legacy current report is missing for {symbol}")
                report_date = _timestamp(research_at)[:10]
                target = self._company_directory(symbol) / "reports" / f"{report_date}.md"
                if target.exists() and target.read_bytes() != current.read_bytes():
                    raise StateCorruptionError(
                        f"dated report already exists with different content: {symbol}"
                    )
                migrations.append((state, current, target))

            if not migrations:
                return 0
            try:
                for state, current, target in migrations:
                    if not target.exists():
                        _atomic_write_text(target, current.read_text(encoding="utf-8"))
                        created_targets.append(target)
                    state["report_path"] = target.relative_to(self.root).as_posix()
                    current_paths.append(current)
                self._write_states(states)
            except BaseException:
                for target in created_targets:
                    target.unlink(missing_ok=True)
                raise
        for current in current_paths:
            current.unlink(missing_ok=True)
        return len(current_paths)

    def prepare_rebaseline(self, *, at: str | datetime | None = None) -> int:
        """Reset active non-covered companies to unseen for a full manager pass."""

        timestamp = _timestamp(at)
        with _exclusive_lock(self.lock_path):
            states = self._states()
            reset_symbols: set[str] = set()
            for symbol, state in states.items():
                if state.get("universe_status") != UniverseStatus.ACTIVE.value:
                    continue
                if state.get("status") == CompanyStatus.COVERED.value:
                    continue
                reset_symbols.add(symbol)
                state.update(
                    {
                        "status": CompanyStatus.UNSEEN.value,
                        "updated_at": timestamp,
                        "summary": None,
                        "key_logic": [],
                        "risks": [],
                        "value_range": None,
                        "event_triggers": [],
                        "source_urls": [],
                        "last_screening": None,
                        "last_research_at": None,
                        "information_cutoff": None,
                        "report_path": None,
                        "valuation_note": None,
                        "candidate_since": None,
                        "invalidation": None,
                        "processed_triggers": [],
                    }
                )
            tasks = [task for task in self._tasks() if task.symbol not in reset_symbols]
            self._write_tasks(tasks)
            self._write_states(states)
        return len(reset_symbols)

    def register_universe(
        self, companies: Iterable[CompanyRef], *, at: str | datetime | None = None
    ) -> int:
        """Add previously unseen companies without changing existing decisions."""

        timestamp = _timestamp(at)
        normalized: list[tuple[str, str | None]] = []
        seen: set[str] = set()
        for company in companies:
            symbol = _symbol(company.symbol)
            if symbol in seen:
                raise ValidationError(f"duplicate company in input: {symbol}")
            seen.add(symbol)
            normalized.append((symbol, _optional_name(company.name)))
        with _exclusive_lock(self.lock_path):
            states = self._states()
            added = 0
            for symbol, name in normalized:
                if symbol not in states:
                    states[symbol] = _empty_state(symbol, name, timestamp)
                    added += 1
                elif name and not states[symbol].get("name"):
                    states[symbol]["name"] = name
                    states[symbol]["updated_at"] = timestamp
            self._write_states(states)
        return added

    def sync_universe(
        self, companies: Iterable[CompanyRef], *, at: str | datetime | None = None
    ) -> UniverseSyncUpdate:
        """Synchronize a complete active-security snapshot without losing research history."""

        timestamp = _timestamp(at)
        snapshot: dict[str, str | None] = {}
        for company in companies:
            symbol = _symbol(company.symbol)
            if symbol in snapshot:
                raise ValidationError(f"duplicate company in input: {symbol}")
            snapshot[symbol] = _optional_name(company.name)

        with _exclusive_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            added = 0
            reactivated = 0
            inactivated = 0
            renamed = 0
            enqueued: list[ResearchTask] = []

            for symbol, state in states.items():
                if (
                    symbol not in snapshot
                    and state.get("universe_status") == UniverseStatus.ACTIVE.value
                ):
                    state["universe_status"] = UniverseStatus.INACTIVE.value
                    state["updated_at"] = timestamp
                    tasks = [task for task in tasks if task.symbol != symbol]
                    inactivated += 1

            for symbol, name in snapshot.items():
                state = states.get(symbol)
                if state is None:
                    states[symbol] = _empty_state(symbol, name, timestamp)
                    added += 1
                    continue
                changed = False
                if name and name != state.get("name"):
                    state["name"] = name
                    renamed += 1
                    changed = True
                if state.get("universe_status") == UniverseStatus.INACTIVE.value:
                    state["universe_status"] = UniverseStatus.ACTIVE.value
                    reactivated += 1
                    changed = True
                    if state.get("status") in {
                        CompanyStatus.CANDIDATE.value,
                        CompanyStatus.STALE.value,
                    }:
                        reason = (
                            (state.get("invalidation") or {}).get("reason")
                            or (state.get("last_screening") or {}).get("reason")
                            or "security re-entered the active research universe"
                        )
                        task = self._enqueue(
                            tasks,
                            state,
                            symbol=symbol,
                            name=state.get("name"),
                            trigger_kind="universe",
                            trigger_id=f"reactivated:{timestamp}",
                            reason=reason,
                            at=timestamp,
                        )
                        if task is not None:
                            enqueued.append(task)
                if changed:
                    state["updated_at"] = timestamp

            self._write_tasks(tasks)
            self._write_states(states)
        return UniverseSyncUpdate(
            total=len(snapshot),
            added=added,
            reactivated=reactivated,
            inactivated=inactivated,
            renamed=renamed,
            enqueued_tasks=tuple(enqueued),
        )

    def apply_screening(
        self,
        decisions: Iterable[ScreenDecision],
        *,
        screen_id: str,
        mode: ScreenMode | str = ScreenMode.BASELINE,
        at: str | datetime | None = None,
    ) -> ScreeningUpdate:
        """Apply one manager batch; ``research_now`` selects a research candidate."""

        timestamp = _timestamp(at)
        batch_id = _nonblank(screen_id, "screen_id")
        screen_mode = _enum_value(mode, ScreenMode, "screen mode")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        counts = {route.value: 0 for route in ScreenRoute}
        for decision in decisions:
            symbol = _symbol(decision.symbol)
            if symbol in seen:
                raise ValidationError(f"duplicate screening decision for {symbol}")
            seen.add(symbol)
            route = _enum_value(decision.route, ScreenRoute, "screen route")
            reason = _nonblank(decision.reason, "reason")
            event_triggers = _event_triggers(decision.event_triggers)
            normalized.append(
                {
                    "symbol": symbol,
                    "name": _optional_name(decision.name),
                    "route": route,
                    "reason": reason,
                    "event_triggers": event_triggers,
                    "source_urls": _urls(decision.source_urls),
                }
            )
            counts[route] += 1

        with _exclusive_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            if screen_mode == ScreenMode.BASELINE.value:
                already_screened = sorted(
                    item["symbol"]
                    for item in normalized
                    if item["symbol"] in states
                    and (
                        states[item["symbol"]].get("status") != CompanyStatus.UNSEEN.value
                        or states[item["symbol"]].get("last_screening") is not None
                    )
                )
                if already_screened:
                    raise ValidationError(
                        "baseline screening only accepts unseen companies: "
                        + ", ".join(already_screened)
                    )
            direct_outcome_changes = sorted(
                item["symbol"]
                for item in normalized
                if item["route"] == ScreenRoute.IGNORE.value
                and isinstance(states.get(item["symbol"], {}).get("report_path"), str)
            )
            if direct_outcome_changes:
                raise ValidationError(
                    "screening cannot replace a formal research outcome with ignore; "
                    "complete a full research task instead: "
                    + ", ".join(direct_outcome_changes)
                )
            enqueued: list[ResearchTask] = []
            deduplicated = 0
            for item in normalized:
                symbol = item["symbol"]
                state = states.setdefault(symbol, _empty_state(symbol, item["name"], timestamp))
                if state.get("universe_status") != UniverseStatus.ACTIVE.value:
                    raise ValidationError(f"cannot screen inactive security: {symbol}")
                if item["name"]:
                    state["name"] = item["name"]
                state["updated_at"] = timestamp
                state["last_screening"] = {
                    "screen_id": batch_id,
                    "mode": screen_mode,
                    "route": item["route"],
                    "reason": item["reason"],
                    "event_triggers": item["event_triggers"],
                    "source_urls": item["source_urls"],
                    "at": timestamp,
                }
                if item["route"] == ScreenRoute.IGNORE.value:
                    state["status"] = CompanyStatus.IGNORE.value
                    state["summary"] = item["reason"]
                    state["key_logic"] = []
                    state["risks"] = []
                    state["value_range"] = None
                    state["event_triggers"] = item["event_triggers"]
                    state["source_urls"] = item["source_urls"]
                    state["last_research_at"] = None
                    state["information_cutoff"] = None
                    state["report_path"] = None
                    state["valuation_note"] = None
                    state["candidate_since"] = None
                    state["invalidation"] = None
                    tasks = [task for task in tasks if task.symbol != symbol]
                elif item["route"] == ScreenRoute.RESEARCH_NOW.value:
                    if state.get("report_path") is not None:
                        state["status"] = CompanyStatus.STALE.value
                        state["invalidation"] = {
                            "at": timestamp,
                            "reason": item["reason"],
                            "screen_id": batch_id,
                        }
                    else:
                        state["status"] = CompanyStatus.CANDIDATE.value
                        state["candidate_since"] = state.get("candidate_since") or timestamp
                        state["invalidation"] = None
                    state["summary"] = item["reason"]
                    if item["event_triggers"]:
                        state["event_triggers"] = item["event_triggers"]
                    if item["source_urls"]:
                        state["source_urls"] = item["source_urls"]
                    task = self._enqueue(
                        tasks,
                        state,
                        symbol=symbol,
                        name=state.get("name"),
                        trigger_kind="screen",
                        trigger_id=batch_id,
                        reason=item["reason"],
                        at=timestamp,
                    )
                    if task is None:
                        deduplicated += 1
                    else:
                        enqueued.append(task)
            self._write_tasks(tasks)
            self._write_states(states)

        return ScreeningUpdate(
            total=len(normalized),
            ignored=counts[ScreenRoute.IGNORE.value],
            candidates=counts[ScreenRoute.RESEARCH_NOW.value],
            enqueued_tasks=tuple(enqueued),
            deduplicated=deduplicated,
        )

    def list_tasks(self, *, status: TaskStatus | str | None = None) -> tuple[ResearchTask, ...]:
        wanted = None if status is None else _enum_value(status, TaskStatus, "task status")
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
        return tuple(task for task in tasks if wanted is None or task.status.value == wanted)

    def dispatch_tasks(
        self,
        *,
        limit: int,
        at: str | datetime | None = None,
        from_end: bool = False,
    ) -> tuple[ResearchTask, ...]:
        """Dispatch at most ``limit`` companies; the caller owns the concurrency policy."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")
        timestamp = _timestamp(at)
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
            active_symbols = {task.symbol for task in tasks if task.status is TaskStatus.RUNNING}
            selected_ids: set[str] = set()
            candidates = reversed(tasks) if from_end else iter(tasks)
            for task in candidates:
                if len(selected_ids) >= limit:
                    break
                if task.status is not TaskStatus.QUEUED or task.symbol in active_symbols:
                    continue
                selected_ids.add(task.task_id)
                active_symbols.add(task.symbol)
            updated: list[ResearchTask] = []
            running: list[ResearchTask] = []
            for task in tasks:
                if task.task_id in selected_ids:
                    task = ResearchTask(
                        task_id=task.task_id,
                        symbol=task.symbol,
                        name=task.name,
                        trigger_kind=task.trigger_kind,
                        trigger_id=task.trigger_id,
                        reason=task.reason,
                        enqueued_at=task.enqueued_at,
                        status=TaskStatus.RUNNING,
                        started_at=timestamp,
                    )
                    running.append(task)
                updated.append(task)
            if running:
                self._write_tasks(updated)
        return tuple(running)

    def requeue_task(self, task_id: str) -> ResearchTask:
        """Explicitly return an interrupted running task to the queue."""

        wanted = _nonblank(task_id, "task_id")
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
            current = next((task for task in tasks if task.task_id == wanted), None)
            if current is None:
                raise ValidationError(f"task is not current: {wanted}")
            if current.status is TaskStatus.QUEUED:
                return current
            restored = ResearchTask(
                task_id=current.task_id,
                symbol=current.symbol,
                name=current.name,
                trigger_kind=current.trigger_kind,
                trigger_id=current.trigger_id,
                reason=current.reason,
                enqueued_at=current.enqueued_at,
                status=TaskStatus.QUEUED,
                started_at=None,
            )
            self._write_tasks([restored if task.task_id == wanted else task for task in tasks])
            return restored

    @staticmethod
    def _normalized_result(result: ResearchResult) -> dict[str, Any]:
        symbol = _symbol(result.symbol)
        outcome = _enum_value(result.outcome, ResearchOutcome, "research outcome")
        summary = _nonblank(result.summary, "summary")
        key_logic = _strings(result.key_logic, "key logic")
        risks = _strings(result.risks, "risk")
        value_range = _value_range(result.value_range)
        event_triggers = _event_triggers(result.event_triggers)
        source_urls = _urls(result.source_urls)
        information_cutoff = _timestamp(result.information_cutoff)
        valuation_note = (
            _nonblank(result.valuation_note, "valuation_note")
            if result.valuation_note is not None
            else None
        )
        report_markdown = (
            _nonblank(result.report_markdown, "report_markdown")
            if result.report_markdown is not None
            else None
        )
        if not key_logic:
            raise ValidationError("research result requires at least one key logic item")
        if not risks:
            raise ValidationError("research result requires at least one risk")
        if not source_urls:
            raise ValidationError("research result requires at least one source URL")
        if report_markdown is None:
            raise ValidationError("research result requires report_markdown")
        if _REPORT_DEFERRAL_RE.search(report_markdown):
            raise ValidationError(
                "formal report must be self-contained and must not defer core analysis "
                "to prior reports"
            )
        if _REPORT_SECURITY_PRICE_LINE_RE.search(report_markdown):
            raise ValidationError(
                "formal report must not define a security-price trigger or review line"
            )
        if value_range is None and valuation_note is None:
            raise ValidationError("research result requires value_range or valuation_note")
        return {
            "symbol": symbol,
            "name": _optional_name(result.name),
            "outcome": outcome,
            "summary": summary,
            "key_logic": key_logic,
            "risks": risks,
            "value_range": value_range,
            "event_triggers": event_triggers,
            "source_urls": source_urls,
            "information_cutoff": information_cutoff,
            "report_markdown": report_markdown,
            "valuation_note": valuation_note,
        }

    def _company_directory(self, symbol: str) -> Path:
        ticker = _symbol(symbol).split(":", 1)[1]
        return self.root / "research" / "companies" / "CN" / ticker

    def _formal_reports(self, symbol: str) -> tuple[Path, ...]:
        reports_directory = self._company_directory(symbol) / "reports"
        if not reports_directory.is_dir():
            return ()

        def order(path: Path) -> tuple[str, int]:
            match = _FORMAL_REPORT_RE.fullmatch(path.name)
            assert match is not None
            return match.group("date"), int(match.group("sequence") or "1")

        reports = [
            path
            for path in reports_directory.iterdir()
            if path.is_file() and _FORMAL_REPORT_RE.fullmatch(path.name)
        ]
        return tuple(sorted(reports, key=order))

    def _next_report_path(self, symbol: str, timestamp: str) -> Path:
        report_date = _timestamp(timestamp)[:10]
        reports = self._formal_reports(symbol)
        if reports:
            newest_match = _FORMAL_REPORT_RE.fullmatch(reports[-1].name)
            assert newest_match is not None
            if report_date < newest_match.group("date"):
                raise ValidationError(
                    f"research completion for {symbol} predates its newest formal report"
                )
        reports_directory = self._company_directory(symbol) / "reports"
        first = reports_directory / f"{report_date}.md"
        if not first.exists():
            return first
        for sequence in range(2, 100):
            candidate = reports_directory / f"{report_date}-{sequence:02d}.md"
            if not candidate.exists():
                return candidate
        raise ValidationError(f"too many formal reports for {symbol} on {report_date}")

    def _updates(self, symbol: str) -> tuple[Path, ...]:
        updates_directory = self._company_directory(symbol) / "updates"
        if not updates_directory.is_dir():
            return ()

        def order(path: Path) -> tuple[str, int]:
            match = _DATED_MARKDOWN_RE.fullmatch(path.name)
            assert match is not None
            return match.group("date"), int(match.group("sequence") or "1")

        updates = [
            path
            for path in updates_directory.iterdir()
            if path.is_file() and _DATED_MARKDOWN_RE.fullmatch(path.name)
        ]
        return tuple(sorted(updates, key=order))

    def _next_update_path(self, symbol: str, timestamp: str) -> Path:
        update_date = _timestamp(timestamp)[:10]
        updates = self._updates(symbol)
        if updates:
            newest_match = _DATED_MARKDOWN_RE.fullmatch(updates[-1].name)
            assert newest_match is not None
            if update_date < newest_match.group("date"):
                raise ValidationError(
                    f"research update for {symbol} predates its newest update record"
                )
        updates_directory = self._company_directory(symbol) / "updates"
        first = updates_directory / f"{update_date}.md"
        if not first.exists():
            return first
        for sequence in range(2, 100):
            candidate = updates_directory / f"{update_date}-{sequence:02d}.md"
            if not candidate.exists():
                return candidate
        raise ValidationError(f"too many research updates for {symbol} on {update_date}")

    @staticmethod
    def _normalized_update(update: ResearchUpdate) -> dict[str, Any]:
        impact = UpdateImpact(
            _enum_value(update.impact, UpdateImpact, "research update impact")
        )
        reviewed_at = _timestamp(update.reviewed_at)
        information_cutoff = _timestamp(update.information_cutoff)
        if datetime.fromisoformat(information_cutoff) > datetime.fromisoformat(reviewed_at):
            raise ValidationError("research update information_cutoff must not follow reviewed_at")
        source_urls = _urls(update.source_urls)
        if not source_urls:
            raise ValidationError("research update requires at least one source URL")
        event_ids = _strings(update.event_ids, "event ID")
        if len(event_ids) != len(set(event_ids)):
            raise ValidationError("research update event IDs must be unique")
        if any("`" in event_id or "\n" in event_id or "\r" in event_id for event_id in event_ids):
            raise ValidationError("research update event IDs must be single-line plain text")
        invalidation_reason = (
            _nonblank(update.invalidation_reason, "invalidation reason")
            if update.invalidation_reason is not None
            else None
        )
        if impact is UpdateImpact.INVALIDATED and invalidation_reason is None:
            raise ValidationError("invalidated update requires invalidation_reason")
        if impact is not UpdateImpact.INVALIDATED and invalidation_reason is not None:
            raise ValidationError("only invalidated update may have invalidation_reason")
        return {
            "symbol": _symbol(update.symbol),
            "title": _nonblank(update.title, "research update title"),
            "impact": impact,
            "reviewed_at": reviewed_at,
            "information_cutoff": information_cutoff,
            "summary": _nonblank(update.summary, "research update summary"),
            "analysis": _nonblank(update.analysis, "research update analysis"),
            "conclusion": _nonblank(update.conclusion, "research update conclusion"),
            "source_urls": source_urls,
            "event_ids": event_ids,
            "invalidation_reason": invalidation_reason,
        }

    @staticmethod
    def _update_markdown(
        normalized: Mapping[str, Any], *, base_report: str
    ) -> str:
        impact_labels = {
            UpdateImpact.REAFFIRMED: "确认原报告",
            UpdateImpact.MONITOR: "继续观察",
            UpdateImpact.INVALIDATED: "原报告失效",
        }
        event_lines = (
            "\n".join(f"- `{event_id}`" for event_id in normalized["event_ids"])
            or "- 无外部事件 ID"
        )
        source_lines = "\n".join(f"- {url}" for url in normalized["source_urls"])
        invalidation = ""
        if normalized["impact"] is UpdateImpact.INVALIDATED:
            invalidation = (
                "\n## 失效原因\n\n"
                f"{normalized['invalidation_reason']}\n"
            )
        return (
            f"# {normalized['title']}\n\n"
            f"- 公司：`{normalized['symbol']}`\n"
            f"- 类型：`event_review`\n"
            f"- 影响：`{normalized['impact'].value}`（{impact_labels[normalized['impact']]}）\n"
            f"- 审阅时间：{normalized['reviewed_at']}\n"
            f"- 信息截止：{normalized['information_cutoff']}\n"
            f"- 基础报告：`{base_report}`\n\n"
            "## 事件 ID\n\n"
            f"{event_lines}\n\n"
            "## 事件摘要\n\n"
            f"{normalized['summary']}\n\n"
            "## 与当前报告的关系\n\n"
            f"{normalized['analysis']}\n\n"
            "## 结论\n\n"
            f"{normalized['conclusion']}\n"
            f"{invalidation}\n"
            "## 来源\n\n"
            f"{source_lines}\n"
        )

    def record_update(self, update: ResearchUpdate) -> ResearchUpdateRecord:
        """Append a reviewed event without silently patching the formal report.

        ``reaffirmed`` and ``monitor`` leave current research state untouched.
        ``invalidated`` marks the formal report stale and enqueues exactly one
        full-research task. Any valuation or conclusion change belongs in a new
        self-contained formal report, not in this record type.
        """

        normalized = self._normalized_update(update)
        with _exclusive_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            state = states.get(normalized["symbol"])
            if state is None:
                raise ValidationError("research update company is not registered")
            if state.get("universe_status") != UniverseStatus.ACTIVE.value:
                raise ValidationError("research update requires an active security")
            if state.get("status") not in {
                CompanyStatus.COVERED.value,
                CompanyStatus.STALE.value,
            }:
                raise ValidationError("research update requires a covered or stale company")
            base_report = state.get("report_path")
            if not isinstance(base_report, str):
                raise ValidationError("research update requires a current formal report")
            report_cutoff = _timestamp(state.get("information_cutoff"))
            if datetime.fromisoformat(normalized["information_cutoff"]) < datetime.fromisoformat(
                report_cutoff
            ):
                raise ValidationError(
                    "research update information_cutoff predates the current formal report"
                )
            if datetime.fromisoformat(normalized["reviewed_at"]) < datetime.fromisoformat(
                _timestamp(state.get("updated_at"))
            ):
                raise ValidationError("research update predates the current company state")
            impact = normalized["impact"]
            if (
                state.get("status") == CompanyStatus.STALE.value
                and impact is not UpdateImpact.INVALIDATED
            ):
                raise ValidationError("stale company only accepts another invalidation record")

            existing_updates = self._updates(normalized["symbol"])
            duplicate_event_ids = sorted(
                event_id
                for event_id in normalized["event_ids"]
                if any(
                    f"- `{event_id}`" in update_file.read_text(encoding="utf-8")
                    for update_file in existing_updates
                )
            )
            if duplicate_event_ids:
                raise ValidationError(
                    "research update event IDs were already recorded: "
                    + ", ".join(duplicate_event_ids)
                )

            update_path = self._next_update_path(
                normalized["symbol"], normalized["reviewed_at"]
            )
            update_relative = update_path.relative_to(self.root).as_posix()
            _atomic_write_text(
                update_path,
                self._update_markdown(normalized, base_report=base_report),
            )

            state["updated_at"] = normalized["reviewed_at"]
            state["last_update"] = {
                "path": update_relative,
                "impact": impact.value,
                "reviewed_at": normalized["reviewed_at"],
                "information_cutoff": normalized["information_cutoff"],
                "event_ids": normalized["event_ids"],
                "summary": normalized["summary"],
                "source_urls": normalized["source_urls"],
                "base_report": base_report,
            }

            enqueued: ResearchTask | None = None
            if impact is UpdateImpact.INVALIDATED:
                state["status"] = CompanyStatus.STALE.value
                state["invalidation"] = {
                    "at": normalized["reviewed_at"],
                    "reason": normalized["invalidation_reason"],
                    "update_path": update_relative,
                }
                trigger_id = (
                    ",".join(normalized["event_ids"])
                    if normalized["event_ids"]
                    else hashlib.sha256(update_relative.encode()).hexdigest()[:24]
                )
                enqueued = self._enqueue(
                    tasks,
                    state,
                    symbol=normalized["symbol"],
                    name=state.get("name"),
                    trigger_kind="update",
                    trigger_id=trigger_id,
                    reason=normalized["invalidation_reason"],
                    at=normalized["reviewed_at"],
                )
                self._write_tasks(tasks)
            self._write_states(states)

            return ResearchUpdateRecord(
                symbol=normalized["symbol"],
                impact=impact,
                update_path=update_relative,
                status=CompanyStatus(state["status"]),
                enqueued_task=enqueued,
            )

    def apply_result(
        self,
        result: ResearchResult,
        *,
        task_id: str,
        at: str | datetime | None = None,
    ) -> dict[str, Any]:
        """Apply the worker's single final answer and remove its current task."""

        normalized = self._normalized_result(result)
        wanted = _nonblank(task_id, "task_id")
        timestamp = _timestamp(at)
        with _exclusive_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            task = next((item for item in tasks if item.task_id == wanted), None)
            if task is None:
                raise ValidationError(f"task is not current: {wanted}")
            if task.status is not TaskStatus.RUNNING:
                raise ValidationError("research task must be running before completion")
            if task.symbol != normalized["symbol"]:
                raise ValidationError("research result symbol does not match task symbol")
            state = states.setdefault(
                normalized["symbol"],
                _empty_state(normalized["symbol"], normalized["name"], timestamp),
            )
            status = {
                ResearchOutcome.IGNORE.value: CompanyStatus.IGNORE.value,
                ResearchOutcome.COVERED.value: CompanyStatus.COVERED.value,
            }[normalized["outcome"]]
            report_path = self._next_report_path(normalized["symbol"], timestamp)
            report_relative = report_path.relative_to(self.root).as_posix()
            report_content = normalized["report_markdown"].rstrip() + "\n"
            _atomic_write_text(report_path, report_content)
            state.update(
                {
                    "schema_version": STATE_SCHEMA_VERSION,
                    "symbol": normalized["symbol"],
                    "name": normalized["name"] or state.get("name"),
                    "universe_status": UniverseStatus.ACTIVE.value,
                    "status": status,
                    "updated_at": timestamp,
                    "summary": normalized["summary"],
                    "key_logic": normalized["key_logic"],
                    "risks": normalized["risks"],
                    "value_range": normalized["value_range"],
                    "event_triggers": normalized["event_triggers"],
                    "source_urls": normalized["source_urls"],
                    "last_research_at": timestamp,
                    "information_cutoff": normalized["information_cutoff"],
                    "report_path": report_relative,
                    "valuation_note": normalized["valuation_note"],
                    "candidate_since": None,
                    "invalidation": None,
                }
            )
            processed = list(state.get("processed_triggers") or [])
            if task.trigger_key not in processed:
                processed.append(task.trigger_key)
            state["processed_triggers"] = processed
            tasks = [item for item in tasks if item.task_id != task.task_id]
            self._write_states(states)
            self._write_tasks(tasks)
            return dict(state)

    def validate(self) -> ResearchFlowStatus:
        """Validate all compact facts and projections without writing any file."""

        # A process-local read lock avoids creating or touching the on-disk writer lock.
        with _thread_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            counts = {status.value: 0 for status in CompanyStatus}
            universe_counts = {status.value: 0 for status in UniverseStatus}
            try:
                for symbol, state in states.items():
                    if state.get("schema_version") != STATE_SCHEMA_VERSION:
                        raise StateCorruptionError(f"state for {symbol} has unsupported schema")
                    universe_status = _enum_value(
                        state.get("universe_status"), UniverseStatus, "universe status"
                    )
                    status = _enum_value(state.get("status"), CompanyStatus, "company status")
                    universe_counts[universe_status] += 1
                    counts[status] += 1
                    if not state.get("updated_at"):
                        raise StateCorruptionError(f"state for {symbol} has no updated_at")
                    _timestamp(state["updated_at"])
                    _strings(state.get("key_logic") or [], "key logic")
                    _strings(state.get("risks") or [], "risk")
                    _event_triggers(state.get("event_triggers") or [])
                    _urls(state.get("source_urls") or [])
                    if "price_levels" in state or "price_monitor" in state:
                        raise StateCorruptionError(
                            f"retired security-price fields remain in state for {symbol}"
                        )
                    last_screening = state.get("last_screening")
                    if isinstance(last_screening, dict):
                        retired = {
                            "price_levels",
                            "price_monitor",
                            "buy_below",
                            "rearm_above",
                        }.intersection(last_screening)
                        if retired:
                            raise StateCorruptionError(
                                f"retired security-price fields remain in last_screening "
                                f"for {symbol}: {', '.join(sorted(retired))}"
                            )
                        _event_triggers(last_screening.get("event_triggers") or [])
                    processed = state.get("processed_triggers") or []
                    if not isinstance(processed, list) or len(processed) != len(set(processed)):
                        raise StateCorruptionError(
                            f"processed_triggers for {symbol} must be a unique list"
                        )
                    report_path = state.get("report_path")
                    if report_path is not None:
                        expected_prefix = (self._company_directory(symbol) / "reports").relative_to(
                            self.root
                        ).as_posix() + "/"
                        if not isinstance(report_path, str) or not report_path.startswith(
                            expected_prefix
                        ):
                            raise StateCorruptionError(f"report_path mismatch for {symbol}")
                        report_name = report_path.removeprefix(expected_prefix)
                        if not _FORMAL_REPORT_RE.fullmatch(report_name):
                            raise StateCorruptionError(
                                f"report_path is not a dated formal report for {symbol}"
                            )
                        expected_report = self.root / report_path
                        if not expected_report.is_file():
                            raise StateCorruptionError(f"current report is missing for {symbol}")
                        if not expected_report.read_text(encoding="utf-8").strip():
                            raise StateCorruptionError(f"current report is blank for {symbol}")
                        if _REPORT_DEFERRAL_RE.search(
                            expected_report.read_text(encoding="utf-8")
                        ):
                            raise StateCorruptionError(
                                f"current report defers core analysis to prior reports: {symbol}"
                            )
                        reports = self._formal_reports(symbol)
                        if not reports or expected_report != reports[-1]:
                            raise StateCorruptionError(
                                f"report_path is not the latest formal report for {symbol}"
                            )

                    updates_directory = self._company_directory(symbol) / "updates"
                    if updates_directory.is_dir():
                        for update_file in updates_directory.iterdir():
                            if (
                                not update_file.is_file()
                                or not _DATED_MARKDOWN_RE.fullmatch(update_file.name)
                            ):
                                raise StateCorruptionError(
                                    f"research update path is not dated Markdown for {symbol}: "
                                    f"{update_file.name}"
                                )
                            if not update_file.read_text(encoding="utf-8").strip():
                                raise StateCorruptionError(
                                    f"research update is blank for {symbol}: {update_file.name}"
                                )

                    last_update = state.get("last_update")
                    if last_update is not None:
                        if not isinstance(last_update, dict):
                            raise StateCorruptionError(
                                f"last_update for {symbol} must be an object"
                            )
                        expected_last_update_fields = {
                            "path",
                            "impact",
                            "reviewed_at",
                            "information_cutoff",
                            "event_ids",
                            "summary",
                            "source_urls",
                            "base_report",
                        }
                        if set(last_update) != expected_last_update_fields:
                            raise StateCorruptionError(
                                f"last_update fields mismatch for {symbol}"
                            )
                        UpdateImpact(
                            _enum_value(
                                last_update.get("impact"),
                                UpdateImpact,
                                "research update impact",
                            )
                        )
                        reviewed_at = _timestamp(last_update.get("reviewed_at"))
                        information_cutoff = _timestamp(
                            last_update.get("information_cutoff")
                        )
                        if datetime.fromisoformat(information_cutoff) > datetime.fromisoformat(
                            reviewed_at
                        ):
                            raise StateCorruptionError(
                                f"last_update information_cutoff follows review for {symbol}"
                            )
                        if datetime.fromisoformat(reviewed_at) > datetime.fromisoformat(
                            _timestamp(state["updated_at"])
                        ):
                            raise StateCorruptionError(
                                f"last_update follows state updated_at for {symbol}"
                            )
                        event_ids = _strings(
                            last_update.get("event_ids") or [], "event ID"
                        )
                        if len(event_ids) != len(set(event_ids)):
                            raise StateCorruptionError(
                                f"last_update event IDs must be unique for {symbol}"
                            )
                        _nonblank(last_update.get("summary"), "research update summary")
                        if not _urls(last_update.get("source_urls") or []):
                            raise StateCorruptionError(
                                f"last_update requires source URLs for {symbol}"
                            )
                        update_path = last_update.get("path")
                        expected_update_prefix = updates_directory.relative_to(
                            self.root
                        ).as_posix() + "/"
                        if not isinstance(update_path, str) or not update_path.startswith(
                            expected_update_prefix
                        ):
                            raise StateCorruptionError(
                                f"last_update path mismatch for {symbol}"
                            )
                        update_name = update_path.removeprefix(expected_update_prefix)
                        if not _DATED_MARKDOWN_RE.fullmatch(update_name):
                            raise StateCorruptionError(
                                f"last_update path is not dated for {symbol}"
                            )
                        updates = self._updates(symbol)
                        if not updates or self.root / update_path != updates[-1]:
                            raise StateCorruptionError(
                                f"last_update is not the latest update for {symbol}"
                            )
                        base_report = last_update.get("base_report")
                        expected_report_prefix = (
                            self._company_directory(symbol) / "reports"
                        ).relative_to(self.root).as_posix() + "/"
                        if not isinstance(base_report, str) or not base_report.startswith(
                            expected_report_prefix
                        ):
                            raise StateCorruptionError(
                                f"last_update base_report mismatch for {symbol}"
                            )
                        base_report_name = base_report.removeprefix(expected_report_prefix)
                        if not _FORMAL_REPORT_RE.fullmatch(base_report_name):
                            raise StateCorruptionError(
                                f"last_update base_report is not dated for {symbol}"
                            )
                        base_report_file = self.root / base_report
                        if not base_report_file.is_file() or not base_report_file.read_text(
                            encoding="utf-8"
                        ).strip():
                            raise StateCorruptionError(
                                f"last_update base report is missing or blank for {symbol}"
                            )

                    if status in {CompanyStatus.COVERED.value, CompanyStatus.STALE.value}:
                        if report_path is None:
                            raise StateCorruptionError(f"{status} company has no report: {symbol}")
                        if not state.get("last_research_at") or not state.get("information_cutoff"):
                            raise StateCorruptionError(
                                f"{status} company lacks research timestamps: {symbol}"
                            )
                        _timestamp(state["last_research_at"])
                        _timestamp(state["information_cutoff"])
                        if not state.get("key_logic") or not state.get("risks"):
                            raise StateCorruptionError(
                                f"{status} company lacks research logic or risks: {symbol}"
                            )
                        if not state.get("source_urls"):
                            raise StateCorruptionError(
                                f"{status} company lacks source URLs: {symbol}"
                            )
                    if status == CompanyStatus.COVERED.value:
                        if state.get("value_range") is None and not state.get("valuation_note"):
                            raise StateCorruptionError(f"covered company lacks valuation: {symbol}")
                        if state.get("invalidation") is not None:
                            raise StateCorruptionError(
                                f"covered company unexpectedly has invalidation: {symbol}"
                            )
                    elif status == CompanyStatus.STALE.value:
                        invalidation = state.get("invalidation")
                        if not isinstance(invalidation, dict):
                            raise StateCorruptionError(
                                f"stale company lacks invalidation details: {symbol}"
                            )
                        _timestamp(invalidation.get("at"))
                        _nonblank(invalidation.get("reason"), "invalidation reason")
                        update_path = invalidation.get("update_path")
                        if update_path is not None:
                            expected_prefix = (
                                self._company_directory(symbol) / "updates"
                            ).relative_to(self.root).as_posix() + "/"
                            if not isinstance(update_path, str) or not update_path.startswith(
                                expected_prefix
                            ):
                                raise StateCorruptionError(
                                    f"invalidation update_path mismatch for {symbol}"
                                )
                            update_name = update_path.removeprefix(expected_prefix)
                            if not _DATED_MARKDOWN_RE.fullmatch(update_name):
                                raise StateCorruptionError(
                                    f"invalidation update_path is not dated for {symbol}"
                                )
                            update_file = self.root / update_path
                            if not update_file.is_file() or not update_file.read_text(
                                encoding="utf-8"
                            ).strip():
                                raise StateCorruptionError(
                                    f"invalidation update is missing or blank for {symbol}"
                                )
                    elif status == CompanyStatus.CANDIDATE.value:
                        if report_path is not None:
                            raise StateCorruptionError(
                                f"candidate cannot have a current report: {symbol}"
                            )
                        _timestamp(state.get("candidate_since"))
                    elif status == CompanyStatus.UNSEEN.value:
                        if state.get("last_screening") is not None or report_path is not None:
                            raise StateCorruptionError(
                                f"unseen company already has screening or report: {symbol}"
                            )
            except (KeyError, TypeError, ValidationError) as exc:
                if isinstance(exc, StateCorruptionError):
                    raise
                raise StateCorruptionError(f"invalid research state: {exc}") from exc

            queued_symbols: set[str] = set()
            for task in tasks:
                if task.symbol not in states:
                    raise StateCorruptionError(f"queue task has no company state: {task.symbol}")
                company = states[task.symbol]
                if company.get("universe_status") != UniverseStatus.ACTIVE.value:
                    raise StateCorruptionError(
                        f"inactive company has a research task: {task.symbol}"
                    )
                if company.get("status") not in {
                    CompanyStatus.CANDIDATE.value,
                    CompanyStatus.STALE.value,
                }:
                    raise StateCorruptionError(
                        f"task company is neither candidate nor stale: {task.symbol}"
                    )
                if task.symbol in queued_symbols:
                    raise StateCorruptionError(
                        f"company has more than one current task: {task.symbol}"
                    )
                queued_symbols.add(task.symbol)
                if task.status is TaskStatus.RUNNING:
                    if task.started_at is None:
                        raise StateCorruptionError(
                            f"running task has no started_at: {task.task_id}"
                        )
                elif task.started_at is not None:
                    raise StateCorruptionError(
                        f"queued task unexpectedly has started_at: {task.task_id}"
                    )

            expected_watchlist = self._watch_rows(states)
            actual_watchlist = _read_jsonl(self.watchlist_path)
            if actual_watchlist != expected_watchlist:
                raise StateCorruptionError(
                    "watchlist is not the exact projection of research state"
                )

            return ResearchFlowStatus(
                companies=len(states),
                active=universe_counts[UniverseStatus.ACTIVE.value],
                inactive=universe_counts[UniverseStatus.INACTIVE.value],
                unseen=counts[CompanyStatus.UNSEEN.value],
                ignored=counts[CompanyStatus.IGNORE.value],
                candidates=counts[CompanyStatus.CANDIDATE.value],
                covered=counts[CompanyStatus.COVERED.value],
                stale=counts[CompanyStatus.STALE.value],
                watchlist=len(expected_watchlist),
                queued=sum(task.status is TaskStatus.QUEUED for task in tasks),
                running=sum(task.status is TaskStatus.RUNNING for task in tasks),
            )

    def status(self) -> ResearchFlowStatus:
        """Return validated compact counts for CLI/status consumers."""

        return self.validate()

    def rebuild_watchlist(self) -> Path:
        """Recreate the disposable watchlist projection from the sole company state."""

        with _exclusive_lock(self.lock_path):
            states = self._states()
            _atomic_write_jsonl(self.watchlist_path, self._watch_rows(states))
        return self.watchlist_path

    def read_states(self) -> tuple[dict[str, Any], ...]:
        with _exclusive_lock(self.lock_path):
            states = self._states()
        return tuple(dict(states[symbol]) for symbol in sorted(states))

    def read_watchlist(self) -> tuple[dict[str, Any], ...]:
        with _exclusive_lock(self.lock_path):
            rows = _read_jsonl(self.watchlist_path)
        return tuple(rows)


__all__ = [
    "CompanyRef",
    "CompanyStatus",
    "QUEUE_PATH",
    "ResearchFlow",
    "ResearchFlowError",
    "ResearchFlowStatus",
    "ResearchOutcome",
    "ResearchResult",
    "ResearchTask",
    "ResearchUpdate",
    "ResearchUpdateRecord",
    "STATE_PATH",
    "ScreenDecision",
    "ScreenMode",
    "ScreenRoute",
    "ScreeningUpdate",
    "StateCorruptionError",
    "TaskStatus",
    "UniverseStatus",
    "UpdateImpact",
    "ValidationError",
    "ValueRange",
    "WATCHLIST_PATH",
]
