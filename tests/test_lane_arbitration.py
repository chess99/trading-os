from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

NOW = dt.datetime(2026, 7, 30, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _hit(symbol: str, suffix: str, *, target: str = "company_research") -> dict:
    return {
        "hit_id": _hash(f"hit:{suffix}"),
        "dedupe_key": _hash(f"dedupe:{suffix}"),
        "symbol": symbol,
        "workflow_target": target,
        "trigger_id": f"trigger-{suffix}",
        "trigger_type": "filing",
        "definition_sha256": _hash(f"definition:{suffix}"),
        "effective_at": (NOW - dt.timedelta(hours=2)).isoformat(),
        "observed_at": (NOW - dt.timedelta(hours=1)).isoformat(),
        "occurrence_key": f"occurrence-{suffix}",
        "observed_event_id": _hash(f"event:{suffix}"),
        "score": 999,
        "investment_rank": 1,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _setup_artifacts(
    tmp_path: Path,
    *,
    run_id: str = "run-1",
    symbols: tuple[str, ...] = ("CN:000001",),
    baseline_symbols: tuple[str, ...] = (),
    hits: list[dict] | None = None,
) -> tuple[Path, Path]:
    from trading_os.research_assets.sealing import seal_json

    root = tmp_path / "coverage" / "cn-a"
    scope_dir = root / "scopes" / run_id
    scope_path = scope_dir / "manifest.json"
    frozen_at = NOW + dt.timedelta(minutes=1)
    scope = {
        "schema_version": 1,
        "run_id": run_id,
        "scope_cutoff": NOW.isoformat(),
        "frozen_at": frozen_at.isoformat(),
        "members": [
            {
                "ordinal": index,
                "symbol": symbol,
                "name": f"Company {symbol[-1]}",
                "partition": "eligible",
            }
            for index, symbol in enumerate(symbols, 1)
        ],
    }
    scope_seal = seal_json(
        scope_path,
        scope,
        artifact_type="all_a_scope_manifest",
        sealed_at=frozen_at,
    )
    baseline_path = scope_dir / "baseline-intake.json"
    baseline = {
        "schema_version": 1,
        "run_id": run_id,
        "lane": "baseline",
        "scope_cutoff": NOW.isoformat(),
        "scope_manifest_path": scope_path.relative_to(tmp_path).as_posix(),
        "scope_manifest_sha256": scope_seal.sha256,
        "members": [
            {
                "ordinal": index,
                "symbol": symbol,
                "name": f"Company {symbol[-1]}",
                "materialization_action": "normalize_queue",
            }
            for index, symbol in enumerate(baseline_symbols, 1)
        ],
    }
    seal_json(
        baseline_path,
        baseline,
        artifact_type="all_a_baseline_intake",
        sealed_at=frozen_at,
    )
    checkpoint_path = scope_dir / "trigger-hit-checkpoint.json"
    checkpoint = {
        "schema_version": 1,
        "run_id": run_id,
        "scope_cutoff": NOW.isoformat(),
        "checkpointed_at": (NOW + dt.timedelta(minutes=2)).isoformat(),
        "scope_manifest_path": scope_path.relative_to(tmp_path).as_posix(),
        "scope_manifest_sha256": scope_seal.sha256,
        "counts": {},
        "hits": hits or [],
    }
    seal_json(
        checkpoint_path,
        checkpoint,
        artifact_type="trigger_hit_checkpoint",
        sealed_at=NOW + dt.timedelta(minutes=2),
    )
    return root, scope_dir


def _freeze(root: Path, **kwargs):
    from trading_os.research_assets.lane_arbitration import freeze_lane_arbitration

    return freeze_lane_arbitration(
        root=root,
        run_id="run-1",
        frozen_at=NOW + dt.timedelta(minutes=3),
        **kwargs,
    )


def test_empty_checkpoint_seals_incremental_and_baseline_arbitration(tmp_path: Path):
    from trading_os.research_assets.sealing import verify_sealed

    root, scope_dir = _setup_artifacts(
        tmp_path,
        symbols=("CN:000001",),
        baseline_symbols=("CN:000001",),
        hits=[],
    )
    result = _freeze(root, apply_coverage=False, baseline_minimum_slots=2)

    assert result["incremental_counts"]["hit_count"] == 0
    assert result["arbitration_counts"]["baseline_symbol_count"] == 1
    incremental = json.loads((scope_dir / "incremental-intake.json").read_text())
    arbitration = json.loads((scope_dir / "lane-arbitration.json").read_text())
    assert incremental["members"] == []
    assert arbitration["contract"]["baseline_minimum_slots"] == 2
    assert arbitration["decisions"][0]["materialization_action"] == "baseline_only"
    assert verify_sealed(scope_dir / "incremental-intake.json").artifact_type == (
        "all_a_incremental_intake"
    )
    assert verify_sealed(scope_dir / "lane-arbitration.json").artifact_type == (
        "all_a_lane_arbitration"
    )


def test_multiple_hits_merge_by_symbol_and_create_one_incremental_task(tmp_path: Path):
    root, scope_dir = _setup_artifacts(
        tmp_path,
        hits=[_hit("CN:000001", "a"), _hit("CN:000001", "b")],
    )
    _write_jsonl(
        root / "research_queue.jsonl",
        [
            {
                "symbol": "CN:000001",
                "name": "Old",
                "task_type": "initial_research",
                "status": "completed",
                "result_path": "research/old.md",
                "priority": 1,
            }
        ],
    )

    result = _freeze(root)
    incremental = json.loads((scope_dir / "incremental-intake.json").read_text())
    assert incremental["counts"]["hit_count"] == 2
    assert incremental["counts"]["symbol_count"] == 1
    assert incremental["members"][0]["hit_count"] == 2
    serialized = json.dumps(incremental)
    assert '"score"' not in serialized
    assert '"investment_rank"' not in serialized
    queue = [json.loads(line) for line in (root / "research_queue.jsonl").read_text().splitlines()]
    assert len(queue) == 1
    assert queue[0]["task_type"] == "rapid_triage"
    assert queue[0]["status"] == "pending"
    assert queue[0]["bound_trigger_hit_ids"] == sorted(
        [_hash("hit:a"), _hash("hit:b")]
    )
    assert queue[0]["stage_history"][-1]["prior_result_path"] == "research/old.md"
    assert result["materialization"]["changed_count"] == 1


@pytest.mark.parametrize(
    "queue_row",
    [
        {
            "symbol": "CN:000001",
            "name": "Running",
            "task_type": "rapid_triage",
            "status": "running",
            "assigned_agent": "agent-1",
            "started_at": NOW.isoformat(),
            "lease_id": "lease-1",
            "lease_expires_at": (NOW + dt.timedelta(hours=1)).isoformat(),
            "result_path": None,
            "priority": 4,
        },
        {
            "symbol": "CN:000001",
            "name": "Deep",
            "task_type": "quick_profile",
            "status": "completed",
            "assigned_agent": None,
            "started_at": None,
            "lease_id": None,
            "lease_expires_at": None,
            "result_path": "coverage/profile.json",
            "priority": 5,
        },
    ],
)
def test_running_or_deeper_task_is_never_overwritten(tmp_path: Path, queue_row: dict):
    root, _ = _setup_artifacts(tmp_path, hits=[_hit("CN:000001", "active")])
    _write_jsonl(root / "research_queue.jsonl", [queue_row])
    protected = dict(queue_row)

    result = _freeze(root)
    queued = json.loads((root / "research_queue.jsonl").read_text())
    for key, value in protected.items():
        assert queued[key] == value
    assert queued["incremental_contexts"][0]["hit_ids"] == [_hash("hit:active")]
    assert result["materialization"]["protected_count"] == 1


def test_materialization_is_idempotent_and_repairs_missing_queue_context(tmp_path: Path):
    from trading_os.research_assets.lane_arbitration import verify_lane_arbitration

    root, _ = _setup_artifacts(tmp_path, hits=[_hit("CN:000001", "repair")])
    first = _freeze(root)
    second = _freeze(root)
    assert second["incremental_intake_sha256"] == first["incremental_intake_sha256"]
    assert second["lane_arbitration_sha256"] == first["lane_arbitration_sha256"]
    assert second["materialization"]["changed_count"] == 0

    row = json.loads((root / "research_queue.jsonl").read_text())
    row.pop("incremental_contexts")
    row.pop("bound_trigger_hit_ids")
    _write_jsonl(root / "research_queue.jsonl", [row])
    repaired = _freeze(root)
    assert repaired["materialization"]["repaired_count"] == 1
    assert verify_lane_arbitration(root=root, run_id="run-1")["ok"] is True


def test_seals_survive_materialization_failure_and_retry_repairs_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from trading_os.research_assets import lane_arbitration
    from trading_os.research_assets.sealing import verify_sealed

    root, scope_dir = _setup_artifacts(tmp_path, hits=[_hit("CN:000001", "fault")])
    real_write = lane_arbitration.write_jsonl

    def fail_write(*args, **kwargs):
        raise OSError("injected queue write failure")

    monkeypatch.setattr(lane_arbitration, "write_jsonl", fail_write)
    with pytest.raises(OSError, match="injected"):
        _freeze(root)
    verify_sealed(scope_dir / "incremental-intake.json")
    verify_sealed(scope_dir / "lane-arbitration.json")
    assert not (root / "research_queue.jsonl").exists()

    monkeypatch.setattr(lane_arbitration, "write_jsonl", real_write)
    repaired = _freeze(root)
    assert repaired["materialization"]["created_count"] == 1
    assert (root / "research_queue.jsonl").is_file()
