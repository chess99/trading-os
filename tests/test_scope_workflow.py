from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

CUTOFF = dt.datetime.fromisoformat("2026-07-30T03:03:20+08:00")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _company(symbol: str, name: str) -> dict:
    ticker = symbol.split(":", 1)[1]
    return {
        "symbol": symbol,
        "ticker": ticker,
        "name": name,
        "market": "CN",
        "exchange": "SZSE",
        "security_type": "common_stock",
        "listing_status": "listed",
        "as_of": "2026-07-29",
        "source": "fixture universe",
    }


def _screen(symbol: str, name: str, decision: str) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "decision": decision,
        "priority": None,
        "reason": "fixture",
        "evidence": ["fixture"],
        "next_action": "fixture",
    }


def _queue(symbol: str, name: str, **updates) -> dict:
    row = {
        "symbol": symbol,
        "name": name,
        "task_type": "initial_research",
        "priority": 3,
        "status": "completed",
        "reason": "legacy completion",
        "target_company_dir": f"research/companies/CN/{symbol.split(':', 1)[1]}",
        "assigned_agent": None,
        "started_at": None,
        "finished_at": CUTOFF.isoformat(),
        "result_path": "reports/legacy.md",
        "failure_reason": None,
        "next_action": "legacy",
    }
    row.update(updates)
    return row


def _coverage(tmp_path: Path) -> Path:
    root = tmp_path / "coverage" / "cn-a"
    companies = [
        _company("CN:000001", "甲公司"),
        _company("CN:000002", "乙公司"),
        _company("CN:000003", "退市公司"),
        _company("CN:000004", "异常公司"),
    ]
    screening = [
        _screen("CN:000001", "甲公司", "catalog"),
        _screen("CN:000002", "乙公司", "price_watch"),
        _screen("CN:000003", "退市公司", "skip_risk"),
        _screen("CN:000004", "异常公司", "needs_manual_review"),
    ]
    triage_path = root / "triage" / "prior-cycle" / "000002" / "20260729T200000+0800.triage.json"
    from tests.test_triage_workflow import _package
    from trading_os.research_assets.sealing import seal_json

    package = _package("CN:000002", "乙公司", "/root/test-agent")
    seal_json(
        triage_path,
        package,
        artifact_type="rapid_triage_package",
        sealed_at=dt.datetime.fromisoformat("2026-07-27T10:00:00+08:00"),
    )
    relative = triage_path.relative_to(tmp_path).as_posix()
    company_dir = tmp_path / "research" / "companies" / "CN" / "000002"
    report_path = company_dir / "reports" / "2026-07-27-rapid-triage-test.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# rapid triage\n", encoding="utf-8")
    source_sha256 = __import__("hashlib").sha256(triage_path.read_bytes()).hexdigest()
    meta = {
        "schema_version": 2,
        "identity": {"symbol": "CN:000002"},
        "research": {
            "latest_rapid_triage": {
                "source_package_path": relative,
                "source_package_sha256": source_sha256,
                "report_path": "reports/2026-07-27-rapid-triage-test.md",
            }
        },
        "reports": {"latest_by_type": {"rapid_triage": "reports/2026-07-27-rapid-triage-test.md"}},
    }
    (company_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    queue = [
        _queue("CN:000001", "甲公司"),
        _queue(
            "CN:000002",
            "乙公司",
            task_type="quick_profile",
            stage_history=[
                {
                    "stage": "rapid_triage",
                    "status": "completed",
                    "result_path": relative,
                }
            ],
        ),
    ]
    _write_jsonl(root / "companies.jsonl", companies)
    _write_jsonl(root / "screening.jsonl", screening)
    _write_jsonl(root / "research_queue.jsonl", queue)
    _write_jsonl(root / "runs.jsonl", [])
    return root


def test_scope_freeze_conserves_universe_and_materializes_missing_baseline(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.scope_workflow import (
        all_a_scope_status,
        freeze_all_a_scope,
    )

    root = _coverage(tmp_path)
    queue_path = root / "research_queue.jsonl"
    queue_before = read_jsonl(queue_path)
    stale = next(item for item in queue_before if item["symbol"] == "CN:000001")
    stale.update(
        {
            "allocation_sha256": "a" * 64,
            "selected_by": ["legacy_lens"],
            "profile_cycle_id": "2026-07-28-legacy-cycle",
            "profile_evaluation_path": "legacy/evaluation.json",
            "profile_quick_selection_path": "legacy/selection.json",
            "triage_priority_score": 99,
        }
    )
    write_jsonl(queue_path, queue_before)
    result = freeze_all_a_scope(
        root=root,
        run_id="2026-07-30-cn-all-a-auto-001",
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
        mode="auto",
    )

    assert result["counts"] == {
        "universe": 4,
        "eligible": 2,
        "hard_excluded": 1,
        "exception": 1,
        "current_protocol_terminal": 1,
        "baseline_backlog": 2,
    }
    assert result["intake_counts"] == {
        "total": 2,
        "normalize_queue": 1,
        "manual_identity_review": 1,
        "defer_active_or_deeper_stage": 0,
    }
    queue = {row["symbol"]: row for row in read_jsonl(root / "research_queue.jsonl")}
    assert queue["CN:000001"]["status"] == "requires_rebaseline"
    assert queue["CN:000001"]["task_type"] == "manager_screen"
    assert queue["CN:000001"]["scope_run_id"] == result["run_id"]
    for stale_field in (
        "allocation_sha256",
        "selected_by",
        "profile_cycle_id",
        "profile_evaluation_path",
        "profile_quick_selection_path",
        "triage_priority_score",
    ):
        assert stale_field not in queue["CN:000001"]
    assert queue["CN:000002"]["task_type"] == "quick_profile"
    assert "CN:000004" not in queue

    status = all_a_scope_status(root=root, run_id=result["run_id"])
    assert status["ok"] is True
    assert status["queue_materialization_drift_count"] == 0
    assert status["queue_materialization_drift_sample"] == []


def test_scope_freeze_is_idempotent_and_repairs_queue_materialization(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root = _coverage(tmp_path)
    first = freeze_all_a_scope(
        root=root,
        run_id="2026-07-30-cn-all-a-auto-001",
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )
    assert first["materialized_count"] == 1
    queue = read_jsonl(root / "research_queue.jsonl")
    queue[0].pop("baseline_intake_sha256", None)
    write_jsonl(root / "research_queue.jsonl", queue)

    replay = freeze_all_a_scope(
        root=root,
        run_id="2026-07-30-cn-all-a-auto-001",
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )

    assert replay["scope_manifest_sha256"] == first["scope_manifest_sha256"]
    assert replay["baseline_intake_sha256"] == first["baseline_intake_sha256"]
    assert replay["materialized_count"] == 1


def test_scope_replay_rejects_a_different_cutoff(tmp_path: Path) -> None:
    import pytest

    from trading_os.research_assets.scope_workflow import (
        ScopeWorkflowError,
        freeze_all_a_scope,
    )

    root = _coverage(tmp_path)
    run_id = "2026-07-30-cn-all-a-auto-001"
    freeze_all_a_scope(
        root=root,
        run_id=run_id,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )
    with pytest.raises(ScopeWorkflowError, match="conflicts with freeze request"):
        freeze_all_a_scope(
            root=root,
            run_id=run_id,
            scope_cutoff=CUTOFF + dt.timedelta(seconds=1),
            frozen_at=CUTOFF + dt.timedelta(seconds=1),
        )


def test_sealed_package_without_company_timeline_is_not_a_current_terminal(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root = _coverage(tmp_path)
    (tmp_path / "research" / "companies" / "CN" / "000002" / "meta.json").unlink()
    result = freeze_all_a_scope(
        root=root,
        run_id="2026-07-30-cn-all-a-auto-001",
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )

    assert result["counts"]["current_protocol_terminal"] == 0
    assert result["counts"]["baseline_backlog"] == 3


def test_run_ledger_append_preserves_existing_lines(tmp_path: Path) -> None:
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope

    root = _coverage(tmp_path)
    legacy = '{"status": "completed", "run_id": "legacy-run", "custom": 1}'
    (root / "runs.jsonl").write_text(legacy + "\n", encoding="utf-8")
    freeze_all_a_scope(
        root=root,
        run_id="2026-07-30-cn-all-a-auto-001",
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )

    assert (root / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0] == legacy


def test_cli_scope_freeze_and_status(tmp_path: Path, capsys) -> None:
    from trading_os.cli import main

    root = _coverage(tmp_path)
    args = [
        "coverage",
        "scope-freeze",
        "2026-07-30-cn-all-a-auto-001",
        "--root",
        str(root),
        "--scope-cutoff",
        CUTOFF.isoformat(),
        "--at",
        CUTOFF.isoformat(),
    ]
    assert main(args) == 0
    frozen = json.loads(capsys.readouterr().out)
    assert frozen["ok"] is True
    assert frozen["counts"]["universe"] == 4

    assert (
        main(
            [
                "coverage",
                "scope-status",
                "2026-07-30-cn-all-a-auto-001",
                "--root",
                str(root),
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["ok"] is True


def test_triage_cohort_binds_parent_scope_and_rejects_non_intake_symbol(
    tmp_path: Path,
) -> None:
    import pytest

    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.scope_workflow import freeze_all_a_scope
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    root = _coverage(tmp_path)
    run_id = "2026-07-30-cn-all-a-auto-001"
    frozen = freeze_all_a_scope(
        root=root,
        run_id=run_id,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
    )
    # Legacy rapid-triage compatibility is tested with an explicit legacy
    # intake row. New scope freezes intentionally materialize manager_screen.
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl

    queue_path = root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    legacy = next(item for item in queue if item["symbol"] == "CN:000001")
    legacy.update(
        {
            "task_type": "rapid_triage",
            "effort_budget_hours": 0.25,
            "preceding_stage": "scope_to_queue_intake",
            "stop_conditions": ["legacy compatibility fixture"],
        }
    )
    write_jsonl(queue_path, queue)
    cohort = freeze_rapid_triage_cohort(
        root=root,
        cycle_id="2026-07-30-baseline-001",
        frozen_at=CUTOFF,
        queue_status="requires_rebaseline",
        symbols=["CN:000001"],
        scope_run_id=run_id,
    )
    payload = json.loads((tmp_path / cohort["cohort_path"]).read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["parent_scope"]["run_id"] == run_id
    assert payload["parent_scope"]["manifest_sha256"] == frozen["scope_manifest_sha256"]

    queue = read_jsonl(queue_path)
    queue.append(
        {
            "symbol": "CN:000004",
            "name": "异常公司",
            "task_type": "initial_research",
            "priority": 3,
            "status": "requires_rebaseline",
            "reason": "manual test row",
            "target_company_dir": "research/companies/CN/000004",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "result_path": None,
            "failure_reason": None,
            "next_action": "manual review",
        }
    )
    write_jsonl(queue_path, queue)

    with pytest.raises(ResearchAllocationError, match="outside the sealed baseline intake"):
        freeze_rapid_triage_cohort(
            root=root,
            cycle_id="2026-07-30-invalid-001",
            frozen_at=CUTOFF,
            queue_status="requires_rebaseline",
            symbols=["CN:000004"],
            scope_run_id=run_id,
        )
