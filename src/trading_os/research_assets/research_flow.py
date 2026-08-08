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
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

STATE_PATH = Path("coverage/cn-a/research_state.jsonl")
WATCHLIST_PATH = Path("research/watchlist.jsonl")
QUEUE_PATH = Path("coverage/cn-a/research_queue.jsonl")

_SYMBOL_RE = re.compile(r"^CN:\d{6}$")
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class ResearchFlowError(RuntimeError):
    """Base error for the compact research workflow."""


class ValidationError(ResearchFlowError, ValueError):
    """Raised before an invalid workflow mutation is written."""


class StateCorruptionError(ResearchFlowError):
    """Raised when a persisted JSONL file is malformed or internally inconsistent."""


class CompanyStatus(str, Enum):
    UNSEEN = "unseen"
    IGNORE = "ignore"
    WATCH = "watch"
    RESEARCHED = "researched"


class ScreenRoute(str, Enum):
    IGNORE = "ignore"
    WATCH = "watch"
    RESEARCH_NOW = "research_now"


class ScreenMode(str, Enum):
    BASELINE = "baseline"
    EVENT = "event"


class ResearchOutcome(str, Enum):
    DISCARD = "discard"
    WATCH = "watch"
    RESEARCHED = "researched"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    DISPATCHED = "dispatched"


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
class PriceLevel:
    id: str
    label: str
    threshold: float
    rearm_above: float | None = None


@dataclass(frozen=True)
class ScreenDecision:
    symbol: str
    route: ScreenRoute | str
    reason: str
    name: str | None = None
    buy_below: float | None = None
    rearm_above: float | None = None
    event_triggers: Sequence[str] = field(default_factory=tuple)
    source_urls: Sequence[str] = field(default_factory=tuple)
    price_levels: Sequence[PriceLevel] = field(default_factory=tuple)


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
    price_levels: Sequence[PriceLevel] = field(default_factory=tuple)
    buy_below: float | None = None
    rearm_above: float | None = None
    name: str | None = None
    report_markdown: str | None = None


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
    dispatched_at: str | None = None

    @property
    def trigger_key(self) -> str:
        return f"{self.trigger_kind}:{self.trigger_id}"


@dataclass(frozen=True)
class ScreeningUpdate:
    total: int
    ignored: int
    watched: int
    research_now: int
    enqueued_tasks: tuple[ResearchTask, ...]
    deduplicated: int


@dataclass(frozen=True)
class ResearchFlowStatus:
    companies: int
    unseen: int
    ignored: int
    watched: int
    researched: int
    watchlist: int
    queued: int
    dispatched: int


@dataclass(frozen=True)
class PriceHit:
    symbol: str
    trading_date: str
    close: float
    level_id: str
    label: str
    threshold: float

    @property
    def buy_below(self) -> float:
        """Compatibility name for callers that previously had one threshold."""

        return self.threshold


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


def _optional_number(value: float | int | None, label: str) -> float | None:
    return None if value is None else _number(value, label)


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


def _trading_date(value: str | date) -> str:
    if isinstance(value, datetime):
        raise ValidationError("trading_date must be a date, not a datetime")
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(_nonblank(value, "trading_date")).isoformat()
    except ValueError as exc:
        raise ValidationError(f"invalid trading_date: {value}") from exc


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


def _price_levels(
    values: Sequence[PriceLevel],
    *,
    buy_below: float | None,
    rearm_above: float | None,
) -> list[dict[str, Any]]:
    if isinstance(values, (str, bytes)):
        raise ValidationError("price_levels must be a sequence of PriceLevel objects")
    if values and (buy_below is not None or rearm_above is not None):
        raise ValidationError("use price_levels or buy_below, not both")
    if not values:
        threshold = _optional_number(buy_below, "buy_below")
        rearm = _optional_number(rearm_above, "rearm_above")
        if rearm is not None and threshold is None:
            raise ValidationError("rearm_above requires buy_below")
        if threshold is None:
            return []
        if rearm is not None and rearm < threshold:
            raise ValidationError("rearm_above must be greater than or equal to buy_below")
        return [
            {
                "id": "buy",
                "label": "买入触发",
                "threshold": threshold,
                "rearm_above": rearm if rearm is not None else threshold,
            }
        ]
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, PriceLevel):
            raise ValidationError("price_levels must contain PriceLevel objects")
        level_id = _nonblank(value.id, "price level id")
        if level_id in seen:
            raise ValidationError(f"duplicate price level id: {level_id}")
        seen.add(level_id)
        threshold = _number(value.threshold, "price level threshold")
        rearm = _optional_number(value.rearm_above, "price level rearm_above")
        if rearm is not None and rearm < threshold:
            raise ValidationError("price level rearm_above must not be below threshold")
        output.append(
            {
                "id": level_id,
                "label": _nonblank(value.label, "price level label"),
                "threshold": threshold,
                "rearm_above": rearm if rearm is not None else threshold,
            }
        )
    return output


def _task_id(symbol: str, trigger_key: str) -> str:
    digest = hashlib.sha256(f"{symbol}\0{trigger_key}".encode()).hexdigest()
    return digest[:24]


def _empty_state(symbol: str, name: str | None, at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "symbol": symbol,
        "name": name,
        "status": CompanyStatus.UNSEEN.value,
        "updated_at": at,
        "summary": None,
        "key_logic": [],
        "risks": [],
        "value_range": None,
        "price_levels": [],
        "event_triggers": [],
        "source_urls": [],
        "last_screening": None,
        "last_research_at": None,
        "report_path": None,
        "processed_triggers": [],
        "price_monitor": None,
    }


def _monitor(
    existing: Mapping[str, Any] | None, levels: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    if not levels:
        return None
    previous = existing.get("levels", {}) if existing else {}
    monitored: dict[str, dict[str, Any]] = {}
    for level in levels:
        level_id = level["id"]
        old = previous.get(level_id)
        if (
            isinstance(old, dict)
            and old.get("threshold") == level["threshold"]
            and old.get("rearm_above") == level["rearm_above"]
        ):
            item = dict(old)
            item["label"] = level["label"]
        else:
            item = {
                **level,
                "armed": True,
                "last_close": None,
                "last_scan_date": None,
                "last_hit_date": None,
            }
        monitored[level_id] = item
    return {"levels": monitored}


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
            dispatched_at=(_timestamp(row["dispatched_at"]) if row.get("dispatched_at") else None),
        )
    except KeyError as exc:
        raise StateCorruptionError(f"queue row is missing {exc.args[0]}") from exc


def _task_row(task: ResearchTask) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": task.task_id,
        "symbol": task.symbol,
        "name": task.name,
        "trigger_kind": task.trigger_kind,
        "trigger_id": task.trigger_id,
        "reason": task.reason,
        "enqueued_at": task.enqueued_at,
        "status": task.status.value,
        "dispatched_at": task.dispatched_at,
    }


class ResearchFlow:
    """Small, single-writer coordinator for screening, research and price alerts.

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
            if state.get("status") not in {
                CompanyStatus.WATCH.value,
                CompanyStatus.RESEARCHED.value,
            }:
                continue
            monitor = state.get("price_monitor") or {}
            monitored_levels = monitor.get("levels", {})
            price_levels = []
            for level in state.get("price_levels") or []:
                runtime = monitored_levels.get(level["id"], {})
                price_levels.append(
                    {
                        **level,
                        "armed": runtime.get("armed", True),
                        "last_close": runtime.get("last_close"),
                        "last_scan_date": runtime.get("last_scan_date"),
                        "last_hit_date": runtime.get("last_hit_date"),
                    }
                )
            rows.append(
                {
                    "schema_version": 1,
                    "symbol": symbol,
                    "name": state.get("name"),
                    "status": state["status"],
                    "summary": state.get("summary"),
                    "key_logic": list(state.get("key_logic") or []),
                    "risks": list(state.get("risks") or []),
                    "value_range": state.get("value_range"),
                    "price_levels": price_levels,
                    "event_triggers": list(state.get("event_triggers") or []),
                    "source_urls": list(state.get("source_urls") or []),
                    "last_research_at": state.get("last_research_at"),
                    "report_path": state.get("report_path"),
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

    def apply_screening(
        self,
        decisions: Iterable[ScreenDecision],
        *,
        screen_id: str,
        mode: ScreenMode | str = ScreenMode.BASELINE,
        at: str | datetime | None = None,
    ) -> ScreeningUpdate:
        """Apply one manager batch; only ``research_now`` creates worker tasks."""

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
            price_levels = _price_levels(
                decision.price_levels,
                buy_below=decision.buy_below,
                rearm_above=decision.rearm_above,
            )
            event_triggers = _strings(decision.event_triggers, "event trigger")
            if route == ScreenRoute.WATCH.value and not price_levels and not event_triggers:
                raise ValidationError("watch screening requires a price or event trigger")
            normalized.append(
                {
                    "symbol": symbol,
                    "name": _optional_name(decision.name),
                    "route": route,
                    "reason": reason,
                    "price_levels": price_levels,
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
                        states[item["symbol"]].get("status")
                        != CompanyStatus.UNSEEN.value
                        or states[item["symbol"]].get("last_screening") is not None
                    )
                )
                if already_screened:
                    raise ValidationError(
                        "baseline screening only accepts unseen companies: "
                        + ", ".join(already_screened)
                    )
            enqueued: list[ResearchTask] = []
            deduplicated = 0
            invalidated_reports: set[Path] = set()
            for item in normalized:
                symbol = item["symbol"]
                state = states.setdefault(symbol, _empty_state(symbol, item["name"], timestamp))
                if item["name"]:
                    state["name"] = item["name"]
                state["updated_at"] = timestamp
                state["last_screening"] = {
                    "screen_id": batch_id,
                    "mode": screen_mode,
                    "route": item["route"],
                    "reason": item["reason"],
                    "price_levels": item["price_levels"],
                    "event_triggers": item["event_triggers"],
                    "source_urls": item["source_urls"],
                    "at": timestamp,
                }
                if item["route"] == ScreenRoute.IGNORE.value:
                    if state.get("status") == CompanyStatus.RESEARCHED.value:
                        invalidated_reports.add(self._company_report_path(symbol))
                    state["status"] = CompanyStatus.IGNORE.value
                    state["summary"] = item["reason"]
                    state["price_levels"] = []
                    state["event_triggers"] = item["event_triggers"]
                    state["price_monitor"] = None
                    state["report_path"] = None
                    tasks = [task for task in tasks if task.symbol != symbol]
                elif item["route"] == ScreenRoute.WATCH.value:
                    if state.get("status") == CompanyStatus.RESEARCHED.value:
                        invalidated_reports.add(self._company_report_path(symbol))
                    state["status"] = CompanyStatus.WATCH.value
                    state["summary"] = item["reason"]
                    state["price_levels"] = item["price_levels"]
                    state["event_triggers"] = item["event_triggers"]
                    state["price_monitor"] = _monitor(
                        state.get("price_monitor"), item["price_levels"]
                    )
                    state["report_path"] = None
                    tasks = [task for task in tasks if task.symbol != symbol]
                elif item["route"] == ScreenRoute.RESEARCH_NOW.value:
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
            for report_path in invalidated_reports:
                report_path.unlink(missing_ok=True)

        return ScreeningUpdate(
            total=len(normalized),
            ignored=counts[ScreenRoute.IGNORE.value],
            watched=counts[ScreenRoute.WATCH.value],
            research_now=counts[ScreenRoute.RESEARCH_NOW.value],
            enqueued_tasks=tuple(enqueued),
            deduplicated=deduplicated,
        )

    def list_tasks(self, *, status: TaskStatus | str | None = None) -> tuple[ResearchTask, ...]:
        wanted = None if status is None else _enum_value(status, TaskStatus, "task status")
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
        return tuple(task for task in tasks if wanted is None or task.status.value == wanted)

    def dispatch_tasks(
        self, *, limit: int, at: str | datetime | None = None
    ) -> tuple[ResearchTask, ...]:
        """Dispatch at most ``limit`` companies; the caller owns the concurrency policy."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")
        timestamp = _timestamp(at)
        with _exclusive_lock(self.lock_path):
            tasks = self._tasks()
            active_symbols = {task.symbol for task in tasks if task.status is TaskStatus.DISPATCHED}
            selected_ids: set[str] = set()
            for task in tasks:
                if len(selected_ids) >= limit:
                    break
                if task.status is not TaskStatus.QUEUED or task.symbol in active_symbols:
                    continue
                selected_ids.add(task.task_id)
                active_symbols.add(task.symbol)
            updated: list[ResearchTask] = []
            dispatched: list[ResearchTask] = []
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
                        status=TaskStatus.DISPATCHED,
                        dispatched_at=timestamp,
                    )
                    dispatched.append(task)
                updated.append(task)
            if dispatched:
                self._write_tasks(updated)
        return tuple(dispatched)

    def requeue_task(self, task_id: str) -> ResearchTask:
        """Explicitly return an interrupted dispatched task to the queue."""

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
                dispatched_at=None,
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
        price_levels = _price_levels(
            result.price_levels,
            buy_below=result.buy_below,
            rearm_above=result.rearm_above,
        )
        event_triggers = _strings(result.event_triggers, "event trigger")
        source_urls = _urls(result.source_urls)
        report_markdown = (
            _nonblank(result.report_markdown, "report_markdown")
            if result.report_markdown is not None
            else None
        )
        if outcome != ResearchOutcome.DISCARD.value and not key_logic:
            raise ValidationError("research result requires at least one key logic item")
        if outcome != ResearchOutcome.DISCARD.value and not source_urls:
            raise ValidationError("research result requires at least one source URL")
        if outcome == ResearchOutcome.WATCH.value and not price_levels and not event_triggers:
            raise ValidationError("watch result requires a price or event trigger")
        if outcome == ResearchOutcome.RESEARCHED.value:
            if value_range is None or not price_levels:
                raise ValidationError("researched result requires value_range and price_levels")
            if not risks or not event_triggers:
                raise ValidationError("researched result requires risks and event_triggers")
            if report_markdown is None:
                raise ValidationError("researched result requires report_markdown")
        return {
            "symbol": symbol,
            "name": _optional_name(result.name),
            "outcome": outcome,
            "summary": summary,
            "key_logic": key_logic,
            "risks": risks,
            "value_range": value_range,
            "price_levels": price_levels,
            "event_triggers": event_triggers,
            "source_urls": source_urls,
            "report_markdown": report_markdown,
        }

    def _company_report_path(self, symbol: str) -> Path:
        ticker = _symbol(symbol).split(":", 1)[1]
        return self.root / "research" / "companies" / "CN" / ticker / "current.md"

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
            if task.status is not TaskStatus.DISPATCHED:
                raise ValidationError("research task must be dispatched before completion")
            if task.symbol != normalized["symbol"]:
                raise ValidationError("research result symbol does not match task symbol")
            state = states.setdefault(
                normalized["symbol"],
                _empty_state(normalized["symbol"], normalized["name"], timestamp),
            )
            previous_monitor = state.get("price_monitor")
            status = {
                ResearchOutcome.DISCARD.value: CompanyStatus.IGNORE.value,
                ResearchOutcome.WATCH.value: CompanyStatus.WATCH.value,
                ResearchOutcome.RESEARCHED.value: CompanyStatus.RESEARCHED.value,
            }[normalized["outcome"]]
            report_path = self._company_report_path(normalized["symbol"])
            report_relative = report_path.relative_to(self.root).as_posix()
            if status == CompanyStatus.RESEARCHED.value:
                report_content = normalized["report_markdown"].rstrip() + "\n"
                _atomic_write_text(report_path, report_content)
            state.update(
                {
                    "schema_version": 1,
                    "symbol": normalized["symbol"],
                    "name": normalized["name"] or state.get("name"),
                    "status": status,
                    "updated_at": timestamp,
                    "summary": normalized["summary"],
                    "key_logic": normalized["key_logic"],
                    "risks": normalized["risks"],
                    "value_range": normalized["value_range"],
                    "price_levels": normalized["price_levels"],
                    "event_triggers": normalized["event_triggers"],
                    "source_urls": normalized["source_urls"],
                    "last_research_at": timestamp,
                    "report_path": (
                        report_relative if status == CompanyStatus.RESEARCHED.value else None
                    ),
                }
            )
            if normalized["price_levels"] and status in {
                CompanyStatus.WATCH.value,
                CompanyStatus.RESEARCHED.value,
            }:
                state["price_monitor"] = _monitor(previous_monitor, normalized["price_levels"])
            else:
                state["price_monitor"] = None
            processed = list(state.get("processed_triggers") or [])
            if task.trigger_key not in processed:
                processed.append(task.trigger_key)
            state["processed_triggers"] = processed
            tasks = [item for item in tasks if item.task_id != task.task_id]
            self._write_states(states)
            self._write_tasks(tasks)
            if status != CompanyStatus.RESEARCHED.value:
                report_path.unlink(missing_ok=True)
            return dict(state)

    def scan_daily_close(
        self,
        closes: Mapping[str, float],
        *,
        trading_date: str | date,
        at: str | datetime | None = None,
    ) -> tuple[PriceHit, ...]:
        """Return close-price edge hits; a later close above rearm re-arms the trigger."""

        scan_date = _trading_date(trading_date)
        timestamp = _timestamp(at)
        normalized_closes = {
            _symbol(symbol): _number(close, "close") for symbol, close in closes.items()
        }
        with _exclusive_lock(self.lock_path):
            states = self._states()
            monitored_symbols = {
                symbol
                for symbol, state in states.items()
                if state.get("status")
                in {CompanyStatus.WATCH.value, CompanyStatus.RESEARCHED.value}
                and state.get("price_monitor") is not None
            }
            missing_quotes = sorted(monitored_symbols - normalized_closes.keys())
            if missing_quotes:
                raise ValidationError(
                    "daily close input is missing monitored companies: "
                    + ", ".join(missing_quotes)
                )
            for symbol, state in states.items():
                if symbol not in monitored_symbols:
                    continue
                for runtime in state["price_monitor"].get("levels", {}).values():
                    previous_date = runtime.get("last_scan_date")
                    if previous_date is not None and previous_date > scan_date:
                        raise ValidationError(
                            f"cannot scan {symbol} at {scan_date}; latest scan is {previous_date}"
                        )
            hits: list[PriceHit] = []
            changed = False
            for symbol in sorted(states):
                state = states[symbol]
                if state.get("status") not in {
                    CompanyStatus.WATCH.value,
                    CompanyStatus.RESEARCHED.value,
                }:
                    continue
                if symbol not in normalized_closes or state.get("price_monitor") is None:
                    continue
                monitor = {
                    "levels": {
                        level_id: dict(runtime)
                        for level_id, runtime in state["price_monitor"].get("levels", {}).items()
                    }
                }
                close = normalized_closes[symbol]
                symbol_changed = False
                for level_id, runtime in monitor["levels"].items():
                    if runtime.get("last_scan_date") == scan_date:
                        continue
                    label = _nonblank(runtime["label"], "price level label")
                    threshold = _number(runtime["threshold"], "price level threshold")
                    rearm_above = _number(
                        runtime.get("rearm_above", threshold), "price level rearm_above"
                    )
                    armed = bool(runtime.get("armed", True))
                    hit = armed and close <= threshold
                    if hit:
                        runtime["armed"] = False
                        runtime["last_hit_date"] = scan_date
                    elif not armed and close > rearm_above:
                        runtime["armed"] = True
                    runtime["last_close"] = close
                    runtime["last_scan_date"] = scan_date
                    symbol_changed = True
                    if hit:
                        hits.append(
                            PriceHit(
                                symbol=symbol,
                                trading_date=scan_date,
                                close=close,
                                level_id=level_id,
                                label=label,
                                threshold=threshold,
                            )
                        )
                if not symbol_changed:
                    continue
                state["price_monitor"] = monitor
                state["updated_at"] = timestamp
                changed = True
            if changed:
                self._write_states(states)
            return tuple(hits)

    def validate(self) -> ResearchFlowStatus:
        """Validate all compact facts and projections without writing any file."""

        # A process-local read lock avoids creating or touching the on-disk writer lock.
        with _thread_lock(self.lock_path):
            states = self._states()
            tasks = self._tasks()
            counts = {status.value: 0 for status in CompanyStatus}
            try:
                for symbol, state in states.items():
                    if state.get("schema_version") != 1:
                        raise StateCorruptionError(f"state for {symbol} has unsupported schema")
                    status = _enum_value(state.get("status"), CompanyStatus, "company status")
                    counts[status] += 1
                    if not state.get("updated_at"):
                        raise StateCorruptionError(f"state for {symbol} has no updated_at")
                    _timestamp(state["updated_at"])
                    _strings(state.get("key_logic") or [], "key logic")
                    _strings(state.get("risks") or [], "risk")
                    _strings(state.get("event_triggers") or [], "event trigger")
                    _urls(state.get("source_urls") or [])
                    raw_levels = state.get("price_levels")
                    if not isinstance(raw_levels, list):
                        raise StateCorruptionError(f"price_levels for {symbol} must be a list")
                    levels = _price_levels(
                        tuple(
                            PriceLevel(
                                id=level["id"],
                                label=level["label"],
                                threshold=level["threshold"],
                                rearm_above=level.get("rearm_above"),
                            )
                            for level in raw_levels
                        ),
                        buy_below=None,
                        rearm_above=None,
                    )
                    if levels != raw_levels:
                        raise StateCorruptionError(f"price_levels for {symbol} are not canonical")
                    monitor = state.get("price_monitor")
                    if monitor is not None:
                        if not isinstance(monitor, dict) or not isinstance(
                            monitor.get("levels"), dict
                        ):
                            raise StateCorruptionError(
                                f"price_monitor for {symbol} must contain levels"
                            )
                        expected = {level["id"]: level for level in levels}
                        if set(monitor["levels"]) != set(expected):
                            raise StateCorruptionError(
                                f"price_monitor levels do not match {symbol} price_levels"
                            )
                        for level_id, runtime in monitor["levels"].items():
                            if runtime.get("threshold") != expected[level_id]["threshold"]:
                                raise StateCorruptionError(
                                    f"price_monitor threshold mismatch for {symbol}:{level_id}"
                                )
                            if runtime.get("rearm_above") != expected[level_id]["rearm_above"]:
                                raise StateCorruptionError(
                                    f"price_monitor rearm mismatch for {symbol}:{level_id}"
                                )
                    processed = state.get("processed_triggers") or []
                    if not isinstance(processed, list) or len(processed) != len(set(processed)):
                        raise StateCorruptionError(
                            f"processed_triggers for {symbol} must be a unique list"
                        )
                    expected_report = self._company_report_path(symbol)
                    expected_relative = expected_report.relative_to(self.root).as_posix()
                    if status == CompanyStatus.RESEARCHED.value:
                        if state.get("report_path") != expected_relative:
                            raise StateCorruptionError(f"report_path mismatch for {symbol}")
                        if not expected_report.is_file():
                            raise StateCorruptionError(f"current report is missing for {symbol}")
                        if not expected_report.read_text(encoding="utf-8").strip():
                            raise StateCorruptionError(f"current report is blank for {symbol}")
                    elif state.get("report_path") is not None:
                        raise StateCorruptionError(
                            f"non-researched company {symbol} must not have report_path"
                        )
                    elif expected_report.exists():
                        raise StateCorruptionError(
                            f"non-researched company {symbol} still has current.md"
                        )
            except (KeyError, TypeError, ValidationError) as exc:
                if isinstance(exc, StateCorruptionError):
                    raise
                raise StateCorruptionError(f"invalid research state: {exc}") from exc

            queued_symbols: set[str] = set()
            for task in tasks:
                if task.symbol not in states:
                    raise StateCorruptionError(f"queue task has no company state: {task.symbol}")
                if task.symbol in queued_symbols:
                    raise StateCorruptionError(
                        f"company has more than one current task: {task.symbol}"
                    )
                queued_symbols.add(task.symbol)
                if task.status is TaskStatus.DISPATCHED:
                    if task.dispatched_at is None:
                        raise StateCorruptionError(
                            f"dispatched task has no dispatched_at: {task.task_id}"
                        )
                elif task.dispatched_at is not None:
                    raise StateCorruptionError(
                        f"queued task unexpectedly has dispatched_at: {task.task_id}"
                    )

            expected_watchlist = self._watch_rows(states)
            actual_watchlist = _read_jsonl(self.watchlist_path)
            if actual_watchlist != expected_watchlist:
                raise StateCorruptionError(
                    "watchlist is not the exact projection of research state"
                )

            return ResearchFlowStatus(
                companies=len(states),
                unseen=counts[CompanyStatus.UNSEEN.value],
                ignored=counts[CompanyStatus.IGNORE.value],
                watched=counts[CompanyStatus.WATCH.value],
                researched=counts[CompanyStatus.RESEARCHED.value],
                watchlist=len(expected_watchlist),
                queued=sum(task.status is TaskStatus.QUEUED for task in tasks),
                dispatched=sum(task.status is TaskStatus.DISPATCHED for task in tasks),
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
    "PriceHit",
    "PriceLevel",
    "QUEUE_PATH",
    "ResearchFlow",
    "ResearchFlowError",
    "ResearchFlowStatus",
    "ResearchOutcome",
    "ResearchResult",
    "ResearchTask",
    "STATE_PATH",
    "ScreenDecision",
    "ScreenMode",
    "ScreenRoute",
    "ScreeningUpdate",
    "StateCorruptionError",
    "TaskStatus",
    "ValidationError",
    "ValueRange",
    "WATCHLIST_PATH",
]
