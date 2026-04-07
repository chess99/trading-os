"""Append-only audit event log backed by SQLite.

Design:
- All events are written to a SQLite table with no UPDATE/DELETE interface.
- Each row has: id (autoincrement), ts (event time), event_type, payload (JSON), created_at.
- The log is the source of truth for all trading activity.

Event types:
    BAR           — a new bar was processed
    SIGNAL        — strategy generated a signal
    SIGNAL_EXPIRED — signal dropped because valid_until < trading_date
    ORDER         — an order was created
    FILL          — an order was filled
    RISK_REJECT   — risk manager rejected a signal or order
    STRATEGY_ERROR — strategy raised an exception
    SESSION_START  — trading session started
    SESSION_END    — trading session ended
"""
from __future__ import annotations

import importlib
import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

EventType = Literal[
    "BAR",
    "SIGNAL",
    "SIGNAL_EXPIRED",
    "ORDER",
    "FILL",
    "RISK_REJECT",
    "STRATEGY_ERROR",
    "SESSION_START",
    "SESSION_END",
]

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,   -- event timestamp (ISO 8601 UTC)
    event_type  TEXT    NOT NULL,
    payload     TEXT    NOT NULL,   -- JSON
    created_at  TEXT    NOT NULL    -- wall-clock write time (ISO 8601 UTC)
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
"""


class EventLog:
    """Append-only SQLite event log.

    Usage::

        log = EventLog(Path("artifacts/events.db"))
        log.write("FILL", {"symbol": "SSE:600000", "shares": 100, "price": 15.2})
        log.write("RISK_REJECT", {"symbol": "SSE:600000", "reason": "涨停无法买入"})

    Reading (for audit/replay)::

        rows = log.query(event_type="FILL", since=date(2024, 1, 1))
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as con:
            con.executescript(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def write(
        self,
        event_type: EventType,
        payload: Any,
        *,
        ts: datetime | None = None,
    ) -> int:
        """Append an event. Returns the row id."""
        now = datetime.now(timezone.utc)
        event_ts = ts or now

        if is_dataclass(payload):
            payload = asdict(payload)
        payload_json = json.dumps(_to_jsonable(payload), ensure_ascii=False)

        with self._connect() as con:
            cursor = con.execute(
                "INSERT INTO events (ts, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (event_ts.isoformat(), event_type, payload_json, now.isoformat()),
            )
            return cursor.lastrowid  # type: ignore

    def query(
        self,
        *,
        event_type: EventType | None = None,
        since: date | datetime | None = None,
        until: date | datetime | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query events from the log.

        Returns list of dicts with keys: id, ts, event_type, payload, created_at.
        """
        where: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            where.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            ts_str = since.isoformat() if isinstance(since, (date, datetime)) else since
            where.append("ts >= ?")
            params.append(ts_str)
        if until is not None:
            ts_str = until.isoformat() if isinstance(until, (date, datetime)) else until
            where.append("ts <= ?")
            params.append(ts_str)

        sql = "SELECT id, ts, event_type, payload, created_at FROM events"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        with self._connect() as con:
            rows = con.execute(sql, params).fetchall()

        return [
            {
                "id": row[0],
                "ts": row[1],
                "event_type": row[2],
                "payload": json.loads(row[3]),
                "created_at": row[4],
            }
            for row in rows
        ]

    def count(self, event_type: EventType | None = None) -> int:
        """Return total number of events (optionally filtered by type)."""
        if event_type is not None:
            with self._connect() as con:
                return con.execute(
                    "SELECT COUNT(*) FROM events WHERE event_type = ?", (event_type,)
                ).fetchone()[0]
        with self._connect() as con:
            return con.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    @classmethod
    def from_repo_root(cls, repo_root: Path, name: str = "trading") -> "EventLog":
        """Convenience constructor using the standard artifacts directory."""
        return cls(repo_root / "artifacts" / f"{name}.db")


def _to_jsonable(x: Any) -> Any:
    """Best-effort conversion to JSON-serializable types."""
    if is_dataclass(x):
        return _to_jsonable(asdict(x))
    if isinstance(x, datetime):
        return x.isoformat()
    if isinstance(x, date):
        return x.isoformat()

    # pandas Timestamp (optional)
    try:
        pd = importlib.import_module("pandas")
        ts_cls = getattr(pd, "Timestamp", None)
        if ts_cls is not None and isinstance(x, ts_cls):
            return x.to_pydatetime().isoformat()
    except ModuleNotFoundError:
        pass

    # numpy scalars (optional)
    try:
        np = importlib.import_module("numpy")
        for np_type in ["integer", "floating", "bool_"]:
            cls = getattr(np, np_type, None)
            if cls and isinstance(x, cls):
                return x.item()
    except ModuleNotFoundError:
        pass

    if isinstance(x, dict):
        return {str(k): _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]

    return x
