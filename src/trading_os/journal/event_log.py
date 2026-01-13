from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EventLog:
    """Append-only JSONL event log.

    Default location should be under `artifacts/` (gitignored).
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, Any]) -> None:
        self._append_json(event)

    def write_obj(self, kind: str, obj: Any, *, ts: datetime | None = None, extra: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any]
        if is_dataclass(obj):
            payload = asdict(obj)
        elif isinstance(obj, dict):
            payload = dict(obj)
        else:
            payload = {"value": repr(obj)}

        event = {
            "ts": (ts or datetime.now(timezone.utc)).isoformat(),
            "kind": kind,
            "payload": payload,
        }
        if extra:
            event["extra"] = extra
        self._append_json(event)

    def _append_json(self, data: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

