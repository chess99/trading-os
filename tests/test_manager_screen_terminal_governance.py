from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tests.test_legacy_transition import (
    FROZEN_AT as TRANSITION_FROZEN_AT,
)
from tests.test_legacy_transition import (
    RECORDED_AT as TRANSITION_RECORDED_AT,
)
from tests.test_legacy_transition import (
    RUN_ID as TRANSITION_RUN_ID,
)
from tests.test_legacy_transition import (
    _submission as transition_submission,
)
from tests.test_legacy_transition import (
    _transition_fixture,
)
from tests.test_manager_screen_governance import (
    SUPERSEDED_AT,
    _sealed_batch,
)
from tests.test_manager_screen_governance import (
    _manager as governance_manager,
)
from tests.test_manager_screening import (
    CUTOFF,
    RUN_ID,
    _calibration_submission,
    _root,
    _submission,
)


def _seal_terminal_packet(
    root: Path,
    *,
    run_id: str,
    sealed_at: dt.datetime,
) -> Path:
    from trading_os.research_assets.manager_screen_terminal_governance import (
        PACKET_ARTIFACT_TYPE,
        PACKET_RELATIVE_PATH,
        WORKFLOW,
        WORKFLOW_VERSION,
    )
    from trading_os.research_assets.sealing import seal_json

    path = root / "manager-screen" / run_id / PACKET_RELATIVE_PATH
    seal_json(
        path,
        {
            "schema_version": 1,
            "workflow": WORKFLOW,
            "workflow_version": WORKFLOW_VERSION,
            "run_id": run_id,
        },
        artifact_type=PACKET_ARTIFACT_TYPE,
        sealed_at=sealed_at,
    )
    return path


def _control_manager() -> dict:
    return {
        "agent": "/root",
        "model": "gpt-test",
        "tools": ["manager-screen status"],
    }


def test_terminal_governance_lock_state_is_read_only(tmp_path: Path) -> None:
    from trading_os.research_assets.manager_screen_terminal_governance import (
        manager_screen_terminal_governance_locked,
    )

    root = tmp_path / "coverage" / "cn-a"
    assert manager_screen_terminal_governance_locked(root=root, run_id=RUN_ID) is False
    packet_path = _seal_terminal_packet(root, run_id=RUN_ID, sealed_at=CUTOFF)
    packet_before = packet_path.read_bytes()
    seal_path = packet_path.with_name(f"{packet_path.name}.seal.json")
    seal_before = seal_path.read_bytes()

    assert manager_screen_terminal_governance_locked(root=root, run_id=RUN_ID) is True
    assert packet_path.read_bytes() == packet_before
    assert seal_path.read_bytes() == seal_before


def test_terminal_governance_lock_fails_closed_on_partial_packet(tmp_path: Path) -> None:
    from trading_os.research_assets.manager_screen_terminal_governance import (
        PACKET_RELATIVE_PATH,
        ManagerScreenTerminalGovernanceError,
        manager_screen_terminal_governance_locked,
    )

    root = tmp_path / "coverage" / "cn-a"
    packet_path = root / "manager-screen" / RUN_ID / PACKET_RELATIVE_PATH
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ManagerScreenTerminalGovernanceError, match="partially sealed"):
        manager_screen_terminal_governance_locked(root=root, run_id=RUN_ID)


def test_terminal_governance_lock_fails_closed_on_orphan_result(tmp_path: Path) -> None:
    from trading_os.research_assets.manager_screen_terminal_governance import (
        RESULT_RELATIVE_PATH,
        WORKFLOW,
        WORKFLOW_VERSION,
        ManagerScreenTerminalGovernanceError,
        manager_screen_terminal_governance_locked,
    )
    from trading_os.research_assets.sealing import seal_json

    root = tmp_path / "coverage" / "cn-a"
    result_path = root / "manager-screen" / RUN_ID / RESULT_RELATIVE_PATH
    seal_json(
        result_path,
        {
            "schema_version": 1,
            "workflow": WORKFLOW,
            "workflow_version": WORKFLOW_VERSION,
            "run_id": RUN_ID,
        },
        artifact_type="manager_screen_full_market_allocation_v3_result",
        sealed_at=CUTOFF,
    )

    with pytest.raises(ManagerScreenTerminalGovernanceError, match="without its singleton packet"):
        manager_screen_terminal_governance_locked(root=root, run_id=RUN_ID)


def test_terminal_packet_blocks_new_control_event_but_allows_exact_replay(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screen_control import (
        ManagerScreenControlError,
        record_manager_screen_control,
    )

    root, _ = _root(tmp_path)
    first = record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="pause-001",
        state="paused",
        manager=_control_manager(),
        reason="Pause for the terminal allocation.",
        recorded_at=CUTOFF + dt.timedelta(minutes=1),
    )
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=2),
    )

    replay = record_manager_screen_control(
        root=root,
        run_id=RUN_ID,
        event_id="pause-001",
        state="paused",
        manager=_control_manager(),
        reason="Pause for the terminal allocation.",
        recorded_at=CUTOFF + dt.timedelta(minutes=1),
    )
    assert replay["latest_event_sha256"] == first["latest_event_sha256"]
    with pytest.raises(ManagerScreenControlError, match="singleton packet is already sealed"):
        record_manager_screen_control(
            root=root,
            run_id=RUN_ID,
            event_id="active-001",
            state="active",
            manager=_control_manager(),
            reason="Attempt to reopen production.",
            recorded_at=CUTOFF + dt.timedelta(minutes=3),
        )


def test_terminal_packet_blocks_new_contract_and_suspension(tmp_path: Path) -> None:
    from trading_os.research_assets.manager_screen_allocation_v3 import (
        ManagerScreenAllocationV3Error,
        freeze_manager_screen_allocation_v3_contract,
    )
    from trading_os.research_assets.manager_screen_allocation_v3_suspension import (
        ManagerScreenAllocationV3SuspensionError,
        suspend_manager_screen_allocation_v3_revocable_commitments,
    )

    root = tmp_path / "coverage" / "cn-a"
    _seal_terminal_packet(root, run_id=RUN_ID, sealed_at=CUTOFF)
    with pytest.raises(ManagerScreenAllocationV3Error, match="new manager-screen allocation"):
        freeze_manager_screen_allocation_v3_contract(
            root=root,
            run_id=RUN_ID,
            manager=_control_manager(),
            reason="Too late to create the packet dependency.",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
        )
    with pytest.raises(
        ManagerScreenAllocationV3SuspensionError,
        match="new manager-screen allocation v3 suspension",
    ):
        suspend_manager_screen_allocation_v3_revocable_commitments(
            root=root,
            run_id=RUN_ID,
            manager=_control_manager(),
            reason="Too late to change the candidate baseline.",
            suspended_at=CUTOFF + dt.timedelta(minutes=1),
        )


def test_terminal_packet_blocks_new_batch_and_new_batch_result(
    tmp_path: Path,
) -> None:
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
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=2),
    )

    with pytest.raises(ManagerScreeningError, match="new manager-screen batch"):
        freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-002",
            frozen_at=CUTOFF + dt.timedelta(minutes=3),
            policy_path=policy_path,
        )
    with pytest.raises(ManagerScreeningError, match="new manager-screen result"):
        record_manager_screen_decisions(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            submission=_submission(["CN:000001", "CN:000002"]),
            recorded_at=CUTOFF + dt.timedelta(minutes=3),
        )


def test_terminal_packet_blocks_sealed_freeze_journal_recovery_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_os.research_assets.manager_screening as manager_screening

    root, policy_path = _root(tmp_path)
    original_repair = manager_screening._repair_manager_screen_freeze

    def interrupt_after_journal(*args, **kwargs):
        raise RuntimeError("simulated crash after the sealed freeze journal")

    monkeypatch.setattr(
        manager_screening,
        "_repair_manager_screen_freeze",
        interrupt_after_journal,
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        manager_screening.freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
            policy_path=policy_path,
        )
    batch_dir = root / "manager-screen" / RUN_ID / "batch-001"
    assert (batch_dir / "freeze-journal.json").exists()
    assert not (batch_dir / "batch.json").exists()

    monkeypatch.setattr(
        manager_screening,
        "_repair_manager_screen_freeze",
        original_repair,
    )
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=2),
    )
    journal_before = (batch_dir / "freeze-journal.json").read_bytes()
    seal_before = (batch_dir / "freeze-journal.json.seal.json").read_bytes()
    with pytest.raises(
        manager_screening.ManagerScreeningError,
        match="forbids freeze-journal repair",
    ):
        manager_screening.freeze_manager_screen_batch(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            frozen_at=CUTOFF + dt.timedelta(minutes=1),
            policy_path=policy_path,
        )
    assert (batch_dir / "freeze-journal.json").read_bytes() == journal_before
    assert (batch_dir / "freeze-journal.json.seal.json").read_bytes() == seal_before
    assert not (batch_dir / "batch.json").exists()
    assert not (batch_dir / "packet.json").exists()


def test_terminal_packet_allows_exact_manager_result_replay(tmp_path: Path) -> None:
    from trading_os.research_assets.manager_screening import (
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
    submission = _submission(["CN:000001", "CN:000002"])
    first = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=3),
    )
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

    screening_path = root / "screening.jsonl"
    screens = read_jsonl(screening_path)
    for row in screens:
        if row.get("symbol") == "CN:000001":
            row["downstream_projection_marker"] = "full-market-allocation"
    write_jsonl(screening_path, screens)
    queue_path = root / "research_queue.jsonl"
    queue_before = queue_path.read_bytes()
    screening_before = screening_path.read_bytes()
    replay = record_manager_screen_decisions(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=2),
    )
    assert replay["result_sha256"] == first["result_sha256"]
    assert queue_path.read_bytes() == queue_before
    assert screening_path.read_bytes() == screening_before


def test_terminal_packet_blocks_new_calibration_packet_and_result(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screening import (
        ManagerScreeningError,
        freeze_manager_screen_batch,
        prepare_manager_screen_calibration,
        record_manager_screen_calibration,
        record_manager_screen_decisions,
    )

    packet_root = tmp_path / "packet-case"
    root, policy_path = _root(packet_root)
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
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=3),
    )
    with pytest.raises(ManagerScreeningError, match="new manager-screen calibration packet"):
        prepare_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-001",
            prepared_at=CUTOFF + dt.timedelta(minutes=4),
            policy_path=policy_path,
        )

    result_root = tmp_path / "result-case"
    root, policy_path = _root(result_root)
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
    prepared = prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    packet = json.loads((result_root / prepared["packet_path"]).read_text(encoding="utf-8"))
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=4),
    )
    with pytest.raises(ManagerScreeningError, match="new manager-screen calibration result"):
        record_manager_screen_calibration(
            root=root,
            run_id=RUN_ID,
            batch_id="batch-001",
            calibration_id="calibration-001",
            submission=_calibration_submission(packet),
            recorded_at=CUTOFF + dt.timedelta(minutes=5),
        )


def test_terminal_packet_allows_exact_calibration_packet_and_result_replays(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screening import (
        freeze_manager_screen_batch,
        prepare_manager_screen_calibration,
        record_manager_screen_calibration,
        record_manager_screen_decisions,
    )

    packet_root = tmp_path / "packet-replay"
    root, policy_path = _root(packet_root)
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
    prepared = prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=4),
    )
    replayed_packet = prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    assert replayed_packet["packet_sha256"] == prepared["packet_sha256"]

    result_root = tmp_path / "result-replay"
    root, policy_path = _root(result_root)
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
    prepared = prepare_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        prepared_at=CUTOFF + dt.timedelta(minutes=3),
        policy_path=policy_path,
    )
    packet = json.loads((result_root / prepared["packet_path"]).read_text(encoding="utf-8"))
    submission = _calibration_submission(packet)
    recorded = record_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )
    _seal_terminal_packet(
        root,
        run_id=RUN_ID,
        sealed_at=CUTOFF + dt.timedelta(minutes=5),
    )
    replayed_result = record_manager_screen_calibration(
        root=root,
        run_id=RUN_ID,
        batch_id="batch-001",
        calibration_id="calibration-001",
        submission=submission,
        recorded_at=CUTOFF + dt.timedelta(minutes=4),
    )
    assert replayed_result["result_sha256"] == recorded["result_sha256"]


def test_terminal_packet_blocks_new_supersession_but_allows_exact_replay(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.manager_screen_governance import (
        ManagerScreenGovernanceError,
        supersede_manager_screen_batch,
    )

    replay_root = tmp_path / "replay"
    root, _ = _sealed_batch(replay_root)
    first = supersede_manager_screen_batch(
        root=root,
        run_id="2026-07-31-run",
        batch_id="batch-019",
        manager=governance_manager(),
        reason="Cancel before terminal allocation.",
        superseded_at=SUPERSEDED_AT,
    )
    _seal_terminal_packet(
        root,
        run_id="2026-07-31-run",
        sealed_at=SUPERSEDED_AT + dt.timedelta(minutes=1),
    )
    replay = supersede_manager_screen_batch(
        root=root,
        run_id="2026-07-31-run",
        batch_id="batch-019",
        manager=governance_manager(),
        reason="Cancel before terminal allocation.",
        superseded_at=SUPERSEDED_AT,
    )
    assert replay == first

    blocked_root = tmp_path / "blocked"
    root, _ = _sealed_batch(blocked_root)
    _seal_terminal_packet(
        root,
        run_id="2026-07-31-run",
        sealed_at=SUPERSEDED_AT + dt.timedelta(minutes=1),
    )
    with pytest.raises(ManagerScreenGovernanceError, match="new manager-screen batch supersession"):
        supersede_manager_screen_batch(
            root=root,
            run_id="2026-07-31-run",
            batch_id="batch-019",
            manager=governance_manager(),
            reason="Too late to change the candidate universe.",
            superseded_at=SUPERSEDED_AT,
        )


def test_terminal_packet_blocks_legacy_mutations_but_allows_exact_replays(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.legacy_transition import (
        LegacyTransitionError,
        freeze_legacy_transition,
        record_legacy_transition,
    )

    freeze_case = _transition_fixture(tmp_path / "freeze-case")
    _seal_terminal_packet(
        freeze_case["coverage_root"],
        run_id=TRANSITION_RUN_ID,
        sealed_at=TRANSITION_FROZEN_AT + dt.timedelta(minutes=1),
    )
    with pytest.raises(LegacyTransitionError, match="new legacy transition plan or packet"):
        freeze_legacy_transition(
            root=freeze_case["coverage_root"],
            run_id=TRANSITION_RUN_ID,
            classification=freeze_case["classification"],
            frozen_at=TRANSITION_FROZEN_AT,
        )

    record_case = _transition_fixture(tmp_path / "record-case")
    frozen = freeze_legacy_transition(
        root=record_case["coverage_root"],
        run_id=TRANSITION_RUN_ID,
        classification=record_case["classification"],
        frozen_at=TRANSITION_FROZEN_AT,
    )
    _seal_terminal_packet(
        record_case["coverage_root"],
        run_id=TRANSITION_RUN_ID,
        sealed_at=TRANSITION_FROZEN_AT + dt.timedelta(minutes=1),
    )
    assert (
        freeze_legacy_transition(
            root=record_case["coverage_root"],
            run_id=TRANSITION_RUN_ID,
            classification=record_case["classification"],
            frozen_at=TRANSITION_FROZEN_AT,
        )
        == frozen
    )
    with pytest.raises(LegacyTransitionError, match="new legacy transition result"):
        record_legacy_transition(
            root=record_case["coverage_root"],
            run_id=TRANSITION_RUN_ID,
            submission=transition_submission(record_case["symbols"]),
            recorded_at=TRANSITION_RECORDED_AT,
        )

    replay_case = _transition_fixture(tmp_path / "replay-case")
    freeze_legacy_transition(
        root=replay_case["coverage_root"],
        run_id=TRANSITION_RUN_ID,
        classification=replay_case["classification"],
        frozen_at=TRANSITION_FROZEN_AT,
    )
    first = record_legacy_transition(
        root=replay_case["coverage_root"],
        run_id=TRANSITION_RUN_ID,
        submission=transition_submission(replay_case["symbols"]),
        recorded_at=TRANSITION_RECORDED_AT,
    )
    _seal_terminal_packet(
        replay_case["coverage_root"],
        run_id=TRANSITION_RUN_ID,
        sealed_at=TRANSITION_RECORDED_AT + dt.timedelta(minutes=1),
    )
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

    screening_path = replay_case["coverage_root"] / "screening.jsonl"
    screens = read_jsonl(screening_path)
    for row in screens:
        if row.get("symbol") == replay_case["symbols"]["direct"]:
            row["downstream_projection_marker"] = "full-market-allocation"
    write_jsonl(screening_path, screens)
    queue_path = replay_case["coverage_root"] / "research_queue.jsonl"
    queue_before = queue_path.read_bytes()
    screening_before = screening_path.read_bytes()
    replay = record_legacy_transition(
        root=replay_case["coverage_root"],
        run_id=TRANSITION_RUN_ID,
        submission=transition_submission(replay_case["symbols"]),
        recorded_at=TRANSITION_RECORDED_AT,
    )
    assert replay == first
    assert queue_path.read_bytes() == queue_before
    assert screening_path.read_bytes() == screening_before


def test_terminal_packet_makes_suspension_replay_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_manager_screen_allocation_v3 import RUN_ID as ALLOCATION_RUN_ID
    from tests.test_manager_screen_allocation_v3_suspension import (
        SUSPENDED_AT,
        _ready_repository,
        _suspend,
    )
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

    root = _ready_repository(tmp_path, monkeypatch)
    first = _suspend(root)
    _seal_terminal_packet(
        root,
        run_id=ALLOCATION_RUN_ID,
        sealed_at=SUSPENDED_AT + dt.timedelta(minutes=1),
    )
    queue_path = root / "research_queue.jsonl"
    screening_path = root / "screening.jsonl"
    queue = read_jsonl(queue_path)
    screens = read_jsonl(screening_path)
    queue[0]["downstream_projection_marker"] = "full-market-allocation"
    screens[0]["downstream_projection_marker"] = "full-market-allocation"
    write_jsonl(queue_path, queue)
    write_jsonl(screening_path, screens)
    queue_before = queue_path.read_bytes()
    screening_before = screening_path.read_bytes()

    replay = _suspend(root)

    assert replay["suspension_sha256"] == first["suspension_sha256"]
    assert replay["idempotent"] is True
    assert queue_path.read_bytes() == queue_before
    assert screening_path.read_bytes() == screening_before
