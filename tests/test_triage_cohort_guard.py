from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tests.test_triage_workflow import CYCLE, RECORDED_AT, _coverage


def test_freeze_rejects_running_queue_without_clearing_assignment(tmp_path: Path) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    root = _coverage(tmp_path)
    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update(
        {
            "status": "running",
            "assigned_agent": "/root/existing-agent",
            "started_at": RECORDED_AT.isoformat(),
        }
    )
    write_jsonl(root / "research_queue.jsonl", queue)
    queue_before = read_jsonl(root / "research_queue.jsonl")
    screening_before = read_jsonl(root / "screening.jsonl")

    with pytest.raises(ResearchAllocationError, match="not eligible"):
        freeze_rapid_triage_cohort(
            root=root,
            cycle_id=CYCLE,
            frozen_at=RECORDED_AT,
            queue_status="running",
            symbols=[queue[0]["symbol"]],
        )

    assert read_jsonl(root / "research_queue.jsonl") == queue_before
    assert read_jsonl(root / "screening.jsonl") == screening_before
    assert not (root / "triage" / CYCLE / "cohort.json").exists()


@pytest.mark.parametrize("task_type", ["quick_profile", "deep_research", "underwriting"])
def test_freeze_rejects_pending_deeper_research_stage(
    tmp_path: Path, task_type: str
) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    root = _coverage(tmp_path)
    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update(
        {
            "task_type": task_type,
            "status": "pending",
            "assigned_agent": "/root/deeper-stage-agent",
            "started_at": None,
        }
    )
    write_jsonl(root / "research_queue.jsonl", queue)
    queue_before = read_jsonl(root / "research_queue.jsonl")
    screening_before = read_jsonl(root / "screening.jsonl")

    with pytest.raises(ResearchAllocationError, match="protected research stage"):
        freeze_rapid_triage_cohort(
            root=root,
            cycle_id=CYCLE,
            frozen_at=RECORDED_AT,
            queue_status="pending",
            symbols=[queue[0]["symbol"]],
        )

    assert read_jsonl(root / "research_queue.jsonl") == queue_before
    assert read_jsonl(root / "screening.jsonl") == screening_before
    assert not (root / "triage" / CYCLE / "cohort.json").exists()


def test_freeze_rejects_active_assignment_on_pending_intake_task(tmp_path: Path) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    root = _coverage(tmp_path)
    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update(
        {
            "status": "pending",
            "assigned_agent": "/root/existing-agent",
            "started_at": RECORDED_AT.isoformat(),
        }
    )
    write_jsonl(root / "research_queue.jsonl", queue)
    queue_before = read_jsonl(root / "research_queue.jsonl")

    with pytest.raises(ResearchAllocationError, match="active assignment metadata"):
        freeze_rapid_triage_cohort(
            root=root,
            cycle_id=CYCLE,
            frozen_at=RECORDED_AT,
            queue_status="pending",
            symbols=[queue[0]["symbol"]],
        )

    assert read_jsonl(root / "research_queue.jsonl") == queue_before


def test_status_slice_skips_deeper_pending_rows_and_keeps_them_unchanged(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    root = _coverage(tmp_path)
    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].update({"task_type": "quick_profile", "status": "pending"})
    queue[1].update({"task_type": "initial_research", "status": "pending"})
    write_jsonl(root / "research_queue.jsonl", queue)
    protected_before = copy.deepcopy(queue[0])

    result = freeze_rapid_triage_cohort(
        root=root,
        cycle_id=CYCLE,
        frozen_at=RECORDED_AT,
        queue_status="pending",
        limit=1,
    )

    assert result["symbols"] == [queue[1]["symbol"]]
    stored = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert stored[queue[0]["symbol"]] == protected_before
    assert stored[queue[1]["symbol"]]["task_type"] == "rapid_triage"


def test_completed_status_cannot_be_bulk_frozen(tmp_path: Path) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    root = _coverage(tmp_path)
    queue_before = read_jsonl(root / "research_queue.jsonl")

    with pytest.raises(ResearchAllocationError, match="requires explicit symbols"):
        freeze_rapid_triage_cohort(
            root=root,
            cycle_id=CYCLE,
            frozen_at=RECORDED_AT,
            queue_status="completed",
            limit=1,
        )

    assert read_jsonl(root / "research_queue.jsonl") == queue_before
    assert not (root / "triage" / CYCLE / "cohort.json").exists()
