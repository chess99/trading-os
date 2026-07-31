from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

FROZEN_AT = dt.datetime.fromisoformat("2026-07-31T10:00:00+08:00")
SUPERSEDED_AT = FROZEN_AT + dt.timedelta(hours=1)


def _sealed_batch(tmp_path: Path) -> tuple[Path, Path]:
    from trading_os.research_assets.sealing import seal_json

    root = tmp_path / "coverage" / "cn-a"
    batch_dir = (
        root
        / "manager-screen"
        / "2026-07-31-run"
        / "batch-019"
    )
    batch_path = batch_dir / "batch.json"
    batch = {
        "schema_version": 1,
        "run_id": "2026-07-31-run",
        "batch_id": "batch-019",
        "frozen_at": FROZEN_AT.isoformat(),
        "member_count": 2,
        "members": [
            {"symbol": "CN:000001"},
            {"symbol": "CN:000002"},
        ],
    }
    batch_seal = seal_json(
        batch_path,
        batch,
        artifact_type="manager_screen_batch",
        sealed_at=FROZEN_AT,
    )
    seal_json(
        batch_dir / "packet.json",
        {
            "schema_version": 1,
            "run_id": "2026-07-31-run",
            "batch_id": "batch-019",
            "batch_sha256": batch_seal.sha256,
        },
        artifact_type="manager_screen_packet",
        sealed_at=FROZEN_AT,
    )
    return root, batch_dir


def _manager() -> dict:
    return {
        "agent": "/root",
        "model": "gpt-5",
        "tools": ["shell"],
    }


def test_supersede_unrecorded_batch_is_sealed_and_idempotent(tmp_path: Path):
    from trading_os.research_assets.manager_screen_governance import (
        load_manager_screen_supersession,
        supersede_manager_screen_batch,
    )

    root, batch_dir = _sealed_batch(tmp_path)
    first = supersede_manager_screen_batch(
        root=root,
        run_id="2026-07-31-run",
        batch_id="batch-019",
        manager=_manager(),
        reason="Policy changed before any manager decision was recorded.",
        superseded_at=SUPERSEDED_AT,
    )
    replay = supersede_manager_screen_batch(
        root=root,
        run_id="2026-07-31-run",
        batch_id="batch-019",
        manager=_manager(),
        reason="Policy changed before any manager decision was recorded.",
        superseded_at=SUPERSEDED_AT,
    )

    assert first == replay
    assert first["status"] == "superseded"
    assert first["released_member_count"] == 2
    payload = load_manager_screen_supersession(
        batch_dir=batch_dir,
        repository_root=tmp_path,
    )
    assert payload is not None
    assert payload["batch_sha256"]
    assert payload["packet_sha256"]
    assert not (batch_dir / "result.json").exists()


def test_recorded_batch_cannot_be_superseded(tmp_path: Path):
    from trading_os.research_assets.manager_screen_governance import (
        ManagerScreenGovernanceError,
        supersede_manager_screen_batch,
    )

    root, batch_dir = _sealed_batch(tmp_path)
    (batch_dir / "result.json").write_text("{}", encoding="utf-8")

    with pytest.raises(
        ManagerScreenGovernanceError,
        match="recorded manager-screen batch",
    ):
        supersede_manager_screen_batch(
            root=root,
            run_id="2026-07-31-run",
            batch_id="batch-019",
            manager=_manager(),
            reason="too late",
            superseded_at=SUPERSEDED_AT,
        )


def test_supersession_detects_changed_sealed_input(tmp_path: Path):
    from trading_os.research_assets.manager_screen_governance import (
        ManagerScreenGovernanceError,
        load_manager_screen_supersession,
        supersede_manager_screen_batch,
    )

    root, batch_dir = _sealed_batch(tmp_path)
    supersede_manager_screen_batch(
        root=root,
        run_id="2026-07-31-run",
        batch_id="batch-019",
        manager=_manager(),
        reason="Policy changed.",
        superseded_at=SUPERSEDED_AT,
    )
    packet = json.loads((batch_dir / "packet.json").read_text(encoding="utf-8"))
    packet["batch_id"] = "batch-tampered"
    (batch_dir / "packet.json").write_text(json.dumps(packet), encoding="utf-8")

    with pytest.raises(
        ManagerScreenGovernanceError,
        match="sealed manager-screen input is invalid",
    ):
        load_manager_screen_supersession(
            batch_dir=batch_dir,
            repository_root=tmp_path,
        )
