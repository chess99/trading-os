from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import pytest

from tests.test_manager_screening import CUTOFF, RUN_ID, _root, _submission


def _manager() -> dict:
    return {
        "agent": "/root",
        "model": "gpt-test",
        "tools": ["manager-screen status", "control review"],
    }


def _require_run_control(policy_path: Path) -> None:
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    payload["payload"]["run_control_required"] = True
    policy_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_legacy_run_without_control_remains_active_unmanaged(tmp_path: Path) -> None:
    from trading_os.research_assets.manager_screen_control import (
        manager_screen_control_status,
    )
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        manager_screen_status,
    )

    root, policy_path = _root(tmp_path)
    control = manager_screen_control_status(root=root, run_id=RUN_ID)
    assert control == {
        "schema_version": 1,
        "run_id": RUN_ID,
        "state": "active_unmanaged",
        "managed": False,
        "event_count": 0,
        "latest_event_id": None,
        "latest_event_path": None,
        "latest_event_sha256": None,
        "recorded_at": None,
        "manager": None,
        "reason": None,
        "baseline_completed_company_count": None,
        "company_limit": None,
        "used_company_count": None,
        "remaining_company_count": None,
    }
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    assert manager_screen_status(root=root, run_id=RUN_ID)["control"]["state"] == (
        "active_unmanaged"
    )


def test_paused_blocks_new_freeze_and_first_record_but_allows_replays(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screen_control import (
        record_manager_screen_control,
    )
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    paused = record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="pause-001",
        state="paused",
        manager=_manager(),
        reason="Pause production for calibration review.",
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    assert paused["state"] == "paused"
    assert paused["event_count"] == 1
    with pytest.raises(ManagerScreeningError, match="paused"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=_submission(["CN:000001", "CN:000002"]),
            recorded_at=CUTOFF + dt.timedelta(minutes=3),
        )
    with pytest.raises(ManagerScreeningError, match="paused"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            frozen_at=CUTOFF + dt.timedelta(minutes=3),
            policy_path=policy_path,
        )
    replayed_freeze = freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    assert replayed_freeze["batch_id"] == "batch-001"

    record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="activate-001",
        state="active",
        manager=_manager(),
        reason="Permit the already frozen batch to record.",
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )
    submission = _submission(["CN:000001", "CN:000002"])
    recorded = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=5),
    )
    record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="pause-002",
        state="paused",
        manager=_manager(),
        reason="Pause after the controlled recording.",
        recorded_at=CUTOFF + dt.timedelta(minutes=6),
    )
    replayed_record = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=7),
    )
    assert replayed_record["result_sha256"] == recorded["result_sha256"]


def test_controlled_limit_uses_completed_baseline_and_open_batches_atomically(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screen_control import (
        manager_screen_control_status,
        record_manager_screen_control,
    )
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        manager_screen_status,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=1),
        policy_path=policy_path,
    )
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=_submission(["CN:000001", "CN:000002"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    controlled = record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="controlled-001",
        state="controlled",
        manager=_manager(),
        reason="Allow a one-company calibration continuation.",
        recorded_at=CUTOFF + dt.timedelta(minutes=3),
        company_limit=1,
    )
    assert controlled["baseline_completed_company_count"] == 2
    assert controlled["remaining_company_count"] == 1
    with pytest.raises(ManagerScreeningError, match="limit would be exceeded"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            batch_size=2,
            frozen_at=CUTOFF + dt.timedelta(minutes=4),
            policy_path=policy_path,
        )

    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        batch_size=1,
        frozen_at=CUTOFF + dt.timedelta(minutes=5),
        policy_path=policy_path,
    )
    after_open = manager_screen_control_status(root=root, run_id=RUN_ID)
    assert after_open["used_company_count"] == 1
    assert after_open["remaining_company_count"] == 0
    record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-002",
        submission=_submission(["CN:000003"]),
        recorded_at=CUTOFF + dt.timedelta(minutes=6),
    )
    status = manager_screen_status(root=root, run_id=RUN_ID)
    assert status["control"]["used_company_count"] == 1
    assert status["control"]["remaining_company_count"] == 0
    with pytest.raises(ManagerScreeningError, match="remaining 0"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-003",
            batch_size=1,
            frozen_at=CUTOFF + dt.timedelta(minutes=7),
            policy_path=policy_path,
        )


def test_controlled_rejects_preexisting_open_over_limit_and_cannot_first_record(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screen_control import (
        ManagerScreenControlError,
        record_manager_screen_control,
        require_manager_screen_first_record_allowed,
    )
    from trading_os.research_assets.sealing import seal_json

    root = tmp_path / "coverage" / "cn-a"
    batch_dir = root / "manager-screen" / RUN_ID / "batch-001"
    batch = {
        "run_id": RUN_ID,
        "batch_id": "batch-001",
        "member_count": 150,
        "members": [
            {"symbol": f"CN:{ordinal:06d}"}
            for ordinal in range(1, 151)
        ],
    }
    batch_seal = seal_json(
        batch_dir / "batch.json",
        batch,
        artifact_type="manager_screen_batch",
        sealed_at=CUTOFF + dt.timedelta(minutes=1),
    )
    with pytest.raises(
        ManagerScreenControlError,
        match=r"existing open reservations exceed company_limit \(150 > 50\)",
    ):
        record_manager_screen_control(
            root=root,
            run_id=RUN_ID,
            event_id="controlled-rejected",
            state="controlled",
            manager=_manager(),
            reason="Attempt an undersized controlled allowance.",
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
            company_limit=50,
        )

    control_path = (
        root
        / "manager-screen"
        / RUN_ID
        / "control"
        / "controlled-invalid-existing-open.json"
    )
    seal_json(
        control_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "event_id": "controlled-invalid-existing-open",
            "state": "controlled",
            "recorded_at": (CUTOFF + dt.timedelta(minutes=2)).isoformat(),
            "manager": _manager(),
            "reason": "Adversarial pre-fix event with an undersized allowance.",
            "previous_event_sha256": None,
            "baseline_completed_company_count": 0,
            "company_limit": 50,
            "portfolio_action": None,
        },
        artifact_type="manager_screen_run_control_event",
        sealed_at=CUTOFF + dt.timedelta(minutes=2),
    )
    with pytest.raises(
        ManagerScreenControlError,
        match=r"controlled allowance is over capacity before first record \(150 > 50\)",
    ):
        require_manager_screen_first_record_allowed(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            batch_sha256=batch_seal.sha256,
            member_count=150,
            control_required=True,
        )


def test_control_events_are_sealed_chained_and_immutable(tmp_path: Path) -> None:
    from trading_os.research_assets.manager_screen_control import (
        ManagerScreenControlError,
        record_manager_screen_control,
    )
    from trading_os.research_assets.sealing import verify_sealed

    root, _ = _root(tmp_path)
    first = record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="pause-001",
        state="paused",
        manager=_manager(),
        reason="Pause.",
        recorded_at=CUTOFF + dt.timedelta(minutes=1),
    )
    second = record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="controlled-001",
        state="controlled",
        manager=_manager(),
        reason="Controlled continuation.",
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
        company_limit=3,
    )
    control_dir = root / "manager-screen" / RUN_ID / "control"
    second_payload = json.loads(
        (control_dir / "controlled-001.json").read_text(encoding="utf-8")
    )
    assert second_payload["previous_event_sha256"] == first["latest_event_sha256"]
    assert verify_sealed(control_dir / "controlled-001.json").sha256 == (
        second["latest_event_sha256"]
    )
    assert record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="controlled-001",
        state="controlled",
        manager=_manager(),
        reason="Controlled continuation.",
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
        company_limit=3,
    )["latest_event_sha256"] == second["latest_event_sha256"]
    with pytest.raises(ManagerScreenControlError, match="conflicts"):
        record_manager_screen_control(
            root=root,
            run_id=RUN_ID,
            event_id="controlled-001",
            state="controlled",
            manager=_manager(),
            reason="Changed reason.",
            recorded_at=CUTOFF + dt.timedelta(minutes=2),
            company_limit=3,
        )


def test_required_control_fails_closed_if_the_entire_timeline_is_deleted(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screen_control import (
        record_manager_screen_control,
    )
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        record_manager_screen_decisions,
    )

    root, policy_path = _root(tmp_path)
    from tests.test_manager_screening import _policy, _v2_submission

    _policy(policy_path, decision_contract_version=2)
    _require_run_control(policy_path)
    with pytest.raises(ManagerScreeningError, match="requires managed run control"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
            policy_path=policy_path,
        )
    record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="active-001",
        state="active",
        manager=_manager(),
        reason="Activate the managed run.",
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    freeze_manager_screen_batch(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        frozen_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    shutil.rmtree(root / "manager-screen" / RUN_ID / "control")
    with pytest.raises(ManagerScreeningError, match="requires managed run control"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            frozen_at=CUTOFF + dt.timedelta(minutes=4),
            policy_path=policy_path,
        )
    packet = json.loads(
        (root / "manager-screen" / RUN_ID / "batch-001" / "packet.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(ManagerScreeningError, match="requires managed run control"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=_v2_submission(packet),
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )


def test_manager_screen_control_cli_records_and_reports_status(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from trading_os.cli import main

    root, _ = _root(tmp_path)
    args = [
        "coverage",
        "manager-screen-control-record",
        RUN_ID,
        "pause-cli-001",
        "--root",
        str(root),
        "--state",
        "paused",
        "--manager-agent",
        "/root",
        "--manager-model",
        "gpt-test",
        "--manager-tool",
        "manager-screen status",
        "--reason",
        "Pause from CLI.",
        "--at",
        (CUTOFF + dt.timedelta(minutes=1)).isoformat(),
    ]
    assert main(args) == 0
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["ok"] is True
    assert recorded["state"] == "paused"

    assert main(
        [
            "coverage",
            "manager-screen-control-status",
            RUN_ID,
            "--root",
            str(root),
        ]
    ) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["ok"] is True
    assert status["state"] == "paused"
    assert status["event_count"] == 1
