from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .coverage_store import serialized_coverage_write
from .manager_screen_terminal_governance import (
    ManagerScreenTerminalGovernanceError,
    require_manager_screen_terminal_governance_open,
)
from .sealing import SealingError, seal_json, verify_sealed


class ManagerScreenGovernanceError(ValueError):
    """Raised when a manager-screen governance transition is invalid."""


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MANAGER_KEYS = {"agent", "model", "tools"}
SUPERSESSION_KEYS = {
    "schema_version",
    "run_id",
    "batch_id",
    "superseded_at",
    "batch_path",
    "batch_sha256",
    "packet_path",
    "packet_sha256",
    "manager",
    "reason",
    "disposition",
    "released_member_count",
    "portfolio_action",
}


@serialized_coverage_write
def supersede_manager_screen_batch(
    *,
    root: str | Path,
    run_id: str,
    batch_id: str,
    manager: Mapping[str, Any],
    reason: str,
    superseded_at: dt.datetime,
) -> dict[str, Any]:
    """Seal the cancellation of an unrecorded batch without deleting it."""

    base = Path(root)
    repository_root = base.parent.parent.resolve()
    run = _identifier(run_id, "run_id")
    batch = _identifier(batch_id, "batch_id")
    timestamp = _aware(superseded_at, "superseded_at")
    normalized_manager = _manager(manager)
    explanation = _text(reason, "reason")
    batch_dir = base / "manager-screen" / run / batch
    batch_path = batch_dir / "batch.json"
    packet_path = batch_dir / "packet.json"
    result_path = batch_dir / "result.json"
    supersession_path = batch_dir / "supersession.json"
    if result_path.exists() or result_path.with_name("result.json.seal.json").exists():
        raise ManagerScreenGovernanceError(
            "a recorded manager-screen batch cannot be superseded"
        )
    batch_payload, batch_seal = _sealed_object(
        batch_path,
        artifact_type="manager_screen_batch",
    )
    packet_payload, packet_seal = _sealed_object(
        packet_path,
        artifact_type="manager_screen_packet",
    )
    if (
        batch_payload.get("run_id") != run
        or batch_payload.get("batch_id") != batch
        or packet_payload.get("run_id") != run
        or packet_payload.get("batch_id") != batch
        or packet_payload.get("batch_sha256") != batch_seal.sha256
    ):
        raise ManagerScreenGovernanceError(
            "manager-screen supersession inputs do not bind the requested batch"
        )
    frozen_at = _parse_datetime(batch_payload.get("frozen_at"), "batch frozen_at")
    if timestamp < frozen_at:
        raise ManagerScreenGovernanceError("superseded_at cannot predate batch freeze")
    member_count = batch_payload.get("member_count")
    if isinstance(member_count, bool) or not isinstance(member_count, int) or member_count <= 0:
        raise ManagerScreenGovernanceError("manager-screen member_count is invalid")
    payload = {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch,
        "superseded_at": timestamp.isoformat(),
        "batch_path": _relative(batch_path, repository_root),
        "batch_sha256": batch_seal.sha256,
        "packet_path": _relative(packet_path, repository_root),
        "packet_sha256": packet_seal.sha256,
        "manager": normalized_manager,
        "reason": explanation,
        "disposition": "superseded_before_decision",
        "released_member_count": member_count,
        "portfolio_action": None,
    }
    if supersession_path.exists():
        existing = load_manager_screen_supersession(
            batch_dir=batch_dir,
            repository_root=repository_root,
        )
        if existing != payload:
            raise ManagerScreenGovernanceError(
                "sealed manager-screen supersession conflicts with request"
            )
        seal = verify_sealed(supersession_path)
    else:
        try:
            require_manager_screen_terminal_governance_open(
                root=base,
                run_id=run,
                operation="new manager-screen batch supersession",
            )
        except ManagerScreenTerminalGovernanceError as exc:
            raise ManagerScreenGovernanceError(str(exc)) from exc
        seal = seal_json(
            supersession_path,
            payload,
            artifact_type="manager_screen_batch_supersession",
            sealed_at=timestamp,
        )
    return {
        "schema_version": 1,
        "run_id": run,
        "batch_id": batch,
        "status": "superseded",
        "released_member_count": member_count,
        "path": _relative(supersession_path, repository_root),
        "sha256": seal.sha256,
        "superseded_at": timestamp.isoformat(),
        "portfolio_action": None,
    }


def load_manager_screen_supersession(
    *,
    batch_dir: str | Path,
    repository_root: str | Path,
) -> dict[str, Any] | None:
    directory = Path(batch_dir)
    root = Path(repository_root).resolve()
    path = directory / "supersession.json"
    seal_path = path.with_name("supersession.json.seal.json")
    if not path.exists() and not seal_path.exists():
        return None
    payload, seal = _sealed_object(
        path,
        artifact_type="manager_screen_batch_supersession",
    )
    if set(payload) != SUPERSESSION_KEYS or payload.get("schema_version") != 1:
        raise ManagerScreenGovernanceError(
            "manager-screen supersession fields do not match v1"
        )
    run_id = _identifier(payload.get("run_id"), "run_id")
    batch_id = _identifier(payload.get("batch_id"), "batch_id")
    _parse_datetime(payload.get("superseded_at"), "superseded_at")
    _manager(payload.get("manager"))
    _text(payload.get("reason"), "reason")
    if (
        payload.get("disposition") != "superseded_before_decision"
        or payload.get("portfolio_action") is not None
    ):
        raise ManagerScreenGovernanceError(
            "manager-screen supersession disposition is invalid"
        )
    member_count = payload.get("released_member_count")
    if isinstance(member_count, bool) or not isinstance(member_count, int) or member_count <= 0:
        raise ManagerScreenGovernanceError(
            "manager-screen supersession member count is invalid"
        )
    batch_path = root / str(payload.get("batch_path"))
    packet_path = root / str(payload.get("packet_path"))
    batch_payload, batch_seal = _sealed_object(
        batch_path,
        artifact_type="manager_screen_batch",
    )
    packet_payload, packet_seal = _sealed_object(
        packet_path,
        artifact_type="manager_screen_packet",
    )
    if (
        batch_payload.get("run_id") != run_id
        or batch_payload.get("batch_id") != batch_id
        or packet_payload.get("run_id") != run_id
        or packet_payload.get("batch_id") != batch_id
        or payload.get("batch_sha256") != batch_seal.sha256
        or payload.get("packet_sha256") != packet_seal.sha256
        or packet_payload.get("batch_sha256") != batch_seal.sha256
    ):
        raise ManagerScreenGovernanceError(
            "manager-screen supersession no longer binds its sealed inputs"
        )
    if path.resolve().parent != directory.resolve():
        raise ManagerScreenGovernanceError(
            "manager-screen supersession is outside its batch directory"
        )
    if seal.artifact_type != "manager_screen_batch_supersession":
        raise ManagerScreenGovernanceError(
            "manager-screen supersession artifact type is invalid"
        )
    return payload


def _sealed_object(path: Path, *, artifact_type: str) -> tuple[dict[str, Any], Any]:
    try:
        seal = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenGovernanceError(
            f"sealed manager-screen input is invalid: {path}"
        ) from exc
    if seal.artifact_type != artifact_type or not isinstance(payload, dict):
        raise ManagerScreenGovernanceError(
            f"sealed manager-screen input has unexpected type: {path}"
        )
    return payload, seal


def _manager(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != MANAGER_KEYS:
        raise ManagerScreenGovernanceError("manager fields do not match contract")
    tools = value.get("tools")
    if (
        not isinstance(tools, list)
        or not tools
        or any(not isinstance(item, str) or not item.strip() for item in tools)
    ):
        raise ManagerScreenGovernanceError("manager.tools must be non-empty strings")
    return {
        "agent": _text(value.get("agent"), "manager.agent"),
        "model": _text(value.get("model"), "manager.model"),
        "tools": [item.strip() for item in tools],
    }


def _identifier(value: Any, field: str) -> str:
    result = _text(value, field)
    if not ID_RE.fullmatch(result):
        raise ManagerScreenGovernanceError(f"{field} is invalid")
    return result


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenGovernanceError(f"{field} must be non-empty text")
    return value.strip()


def _aware(value: dt.datetime, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ManagerScreenGovernanceError(f"{field} must include a UTC offset")
    return value


def _parse_datetime(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ManagerScreenGovernanceError(f"{field} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManagerScreenGovernanceError(f"{field} must be an ISO timestamp") from exc
    return _aware(parsed, field)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ManagerScreenGovernanceError(
            "manager-screen governance asset escaped the repository"
        ) from exc
