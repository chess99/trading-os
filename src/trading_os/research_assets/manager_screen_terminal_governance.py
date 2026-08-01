from __future__ import annotations

import json
import re
from pathlib import Path

from .sealing import SealingError, verify_sealed


class ManagerScreenTerminalGovernanceError(ValueError):
    """Raised when a sealed full-market packet closes candidate governance."""


WORKFLOW = "manager_screen_full_market_allocation_v3"
WORKFLOW_VERSION = 1
PACKET_ARTIFACT_TYPE = "manager_screen_full_market_allocation_v3_packet"
FULL_MARKET_RELATIVE_DIR = Path("governance") / "allocation-v3" / "full-market"
PACKET_RELATIVE_PATH = FULL_MARKET_RELATIVE_DIR / "packet.json"
RESULT_RELATIVE_PATH = FULL_MARKET_RELATIVE_DIR / "result.json"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def require_manager_screen_terminal_governance_open(
    *,
    root: str | Path,
    run_id: str,
    operation: str,
) -> None:
    """Fail closed once the run's singleton full-market packet is sealed.

    Production callers must invoke this while holding the shared coverage write
    lock, after any exact replay of an already sealed caller-owned artifact.  The
    check is deliberately read-only: sealing the singleton packet is the lock.
    """

    run = _identifier(run_id, "run_id")
    action = _text(operation, "operation")
    if not manager_screen_terminal_governance_locked(root=root, run_id=run):
        return
    raise ManagerScreenTerminalGovernanceError(
        "full-market allocation singleton packet is already sealed; "
        f"{action} is forbidden"
    )


def manager_screen_terminal_governance_locked(
    *,
    root: str | Path,
    run_id: str,
) -> bool:
    """Return whether one valid singleton packet has closed upstream writes.

    Callers use this read-only state while holding the shared coverage write
    lock.  An absent packet leaves governance open; every partial, orphaned, or
    invalid singleton fails closed instead of being treated as an open run.
    """

    base = Path(root)
    run = _identifier(run_id, "run_id")
    run_dir = base / "manager-screen" / run
    packet_path = run_dir / PACKET_RELATIVE_PATH
    result_path = run_dir / RESULT_RELATIVE_PATH
    packet_presence = _pair_presence(packet_path)
    result_presence = _pair_presence(result_path)

    if packet_presence == "absent":
        if result_presence != "absent":
            raise ManagerScreenTerminalGovernanceError(
                "full-market allocation result exists without its singleton packet; "
                "upstream governance is locked"
            )
        return False
    if packet_presence != "complete":
        raise ManagerScreenTerminalGovernanceError(
            "full-market allocation singleton packet is only partially sealed; "
            "upstream governance is locked"
        )

    try:
        sealed = verify_sealed(packet_path)
        payload = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, SealingError) as exc:
        raise ManagerScreenTerminalGovernanceError(
            "full-market allocation singleton packet is invalid; "
            "upstream governance is locked"
        ) from exc
    if (
        sealed.artifact_type != PACKET_ARTIFACT_TYPE
        or not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("workflow") != WORKFLOW
        or payload.get("workflow_version") != WORKFLOW_VERSION
        or payload.get("run_id") != run
    ):
        raise ManagerScreenTerminalGovernanceError(
            "full-market allocation singleton packet identity is invalid; "
            "upstream governance is locked"
        )
    return True


def _pair_presence(path: Path) -> str:
    artifact_exists = path.exists()
    seal_exists = path.with_name(f"{path.name}.seal.json").exists()
    if artifact_exists and seal_exists:
        return "complete"
    if artifact_exists or seal_exists:
        return "partial"
    return "absent"


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ManagerScreenTerminalGovernanceError(f"{label} is invalid")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenTerminalGovernanceError(f"{label} is required")
    return value.strip()
