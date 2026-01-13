from __future__ import annotations

import importlib
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
            f.write(json.dumps(_to_jsonable(data), ensure_ascii=False) + "\n")


def _to_jsonable(x: Any) -> Any:
    """Best-effort conversion to JSON-serializable types."""
    if is_dataclass(x):
        return _to_jsonable(asdict(x))

    # datetime-like
    if isinstance(x, datetime):
        return x.isoformat()

    # pandas Timestamp (optional)
    try:  # pragma: no cover
        pd = importlib.import_module("pandas")
        ts_cls = getattr(pd, "Timestamp", None)
        if ts_cls is not None and isinstance(x, ts_cls):
            return x.to_pydatetime().isoformat()
    except ModuleNotFoundError:
        pass

    # numpy scalars (optional)
    try:  # pragma: no cover
        np = importlib.import_module("numpy")
        integer = getattr(np, "integer", None)
        floating = getattr(np, "floating", None)
        bool_ = getattr(np, "bool_", None)
        if integer and isinstance(x, integer):
            return x.item()
        if floating and isinstance(x, floating):
            return x.item()
        if bool_ and isinstance(x, bool_):
            return x.item()
    except ModuleNotFoundError:
        pass

    if isinstance(x, dict):
        return {str(k): _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]

    return x

