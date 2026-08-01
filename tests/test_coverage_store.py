from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_jsonl_upsert_keeps_records_sorted_by_symbol(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, upsert_jsonl

    path = tmp_path / "screening.jsonl"

    upsert_jsonl(path, "symbol", {"symbol": "CN:600519", "decision": "deep_research"})
    upsert_jsonl(path, "symbol", {"symbol": "CN:000001", "decision": "watch_only"})
    upsert_jsonl(path, "symbol", {"symbol": "CN:600519", "decision": "watch_only"})

    assert read_jsonl(path) == [
        {"symbol": "CN:000001", "decision": "watch_only"},
        {"symbol": "CN:600519", "decision": "watch_only"},
    ]


def test_validate_coverage_root_rejects_duplicate_symbols(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        validate_coverage_root,
    )

    root = tmp_path / "coverage" / "cn-a"
    root.mkdir(parents=True)
    (root / "screening.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "symbol": "CN:600519",
                        "name": "贵州茅台",
                        "decision": "deep_research",
                        "priority": 1,
                        "reason": "高质量现金流资产。",
                        "evidence": ["高端白酒龙头"],
                        "next_action": "已有报告，等待复查。",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "symbol": "CN:600519",
                        "name": "贵州茅台",
                        "decision": "watch_only",
                        "priority": 2,
                        "reason": "重复记录示例。",
                        "evidence": ["重复 symbol"],
                        "next_action": "应被校验拦截。",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CoverageValidationError, match="duplicate symbol"):
        validate_coverage_root(root)


def test_validate_coverage_root_allows_multiple_runs_for_same_symbol(tmp_path: Path):
    from trading_os.research_assets.coverage_store import validate_coverage_root

    root = tmp_path / "coverage" / "cn-a"
    root.mkdir(parents=True)
    (root / "runs.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"symbol": "CN:600519", "run_id": "run-1"}),
                json.dumps({"symbol": "CN:600519", "run_id": "run-2"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert validate_coverage_root(root)["runs"]["total"] == 2


def test_coverage_status_counts_screening_and_queue(tmp_path: Path):
    from trading_os.research_assets.coverage_store import coverage_status

    root = tmp_path / "coverage" / "cn-a"
    root.mkdir(parents=True)
    (root / "screening.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"symbol": "CN:600519", "decision": "deep_research"}),
                json.dumps({"symbol": "CN:300750", "decision": "deep_research"}),
                json.dumps({"symbol": "CN:000001", "decision": "watch_only"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "research_queue.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"symbol": "CN:300750", "status": "pending"}),
                json.dumps({"symbol": "CN:600519", "status": "completed"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    status = coverage_status(root)

    assert status["screening"]["total"] == 3
    assert status["screening"]["by_decision"] == {
        "deep_research": 2,
        "watch_only": 1,
    }
    assert status["research_queue"]["by_status"] == {
        "completed": 1,
        "pending": 1,
    }


def test_set_screening_and_enqueue_write_agent_safe_jsonl(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        enqueue_research,
        read_jsonl,
        set_screening,
    )

    root = tmp_path / "coverage" / "cn-a"

    set_screening(
        root,
        symbol="CN:300750",
        name="宁德时代",
        decision="deep_research",
        priority=1,
        reason="动力电池龙头，值得完整研究。",
        evidence=["行业龙头", "全球竞争格局重要"],
        next_action="加入研究队列。",
    )
    enqueue_research(
        root,
        symbol="CN:300750",
        name="宁德时代",
        priority=1,
        reason="筛选结果为 deep_research。",
    )

    assert read_jsonl(root / "screening.jsonl")[0]["name"] == "宁德时代"
    assert read_jsonl(root / "research_queue.jsonl")[0] == {
        "symbol": "CN:300750",
        "name": "宁德时代",
        "task_type": "initial_research",
        "priority": 1,
        "status": "pending",
        "reason": "筛选结果为 deep_research。",
        "target_company_dir": "research/companies/CN/300750",
        "assigned_agent": None,
        "started_at": None,
        "finished_at": None,
        "result_path": None,
        "failure_reason": None,
        "next_action": "按 playbooks/company-research.md 写中文初始研究报告。",
    }


@pytest.mark.parametrize(
    ("owned_file", "ownership"),
    [
        ("screening.jsonl", {"manager_screen_run_id": "manager-run"}),
        (
            "screening.jsonl",
            {
                "manager_screen_allocation_result_path": (
                    "coverage/cn-a/manager-screen/manager-run/governance/"
                    "allocation-v3/full-market/result.json"
                )
            },
        ),
        ("research_queue.jsonl", {"scope_run_id": "scope-run"}),
        ("screening.jsonl", {"profile_cycle_id": "profile-cycle"}),
    ],
)
def test_set_screening_rejects_formal_workflow_owned_symbol_without_mutation(
    tmp_path: Path,
    owned_file: str,
    ownership: dict[str, str],
) -> None:
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        set_screening,
        write_jsonl,
    )

    root = tmp_path / "coverage" / "cn-a"
    screening_path = root / "screening.jsonl"
    queue_path = root / "research_queue.jsonl"
    screening = {
        "symbol": "CN:300750",
        "name": "宁德时代",
        "decision": "watch_only",
        "priority": 2,
        "reason": "正式 workflow 已拥有该投影。",
        "evidence": ["sealed:evidence"],
        "next_action": "走正式 workflow。",
    }
    queue = {
        "symbol": "CN:300750",
        "name": "宁德时代",
        "task_type": "initial_research",
        "priority": 2,
        "status": "completed",
        "reason": "已有正式状态。",
        "target_company_dir": "research/companies/CN/300750",
        "result_path": "reports/legacy.md",
    }
    if owned_file == "screening.jsonl":
        screening.update(ownership)
    else:
        queue.update(ownership)
    write_jsonl(screening_path, [screening])
    write_jsonl(queue_path, [queue])
    before_screening = screening_path.read_bytes()
    before_queue = queue_path.read_bytes()

    with pytest.raises(
        CoverageValidationError,
        match="formal workflow-owned",
    ):
        set_screening(
            root,
            symbol="CN:300750",
            name="宁德时代",
            decision="catalog",
            priority=None,
            reason="通用 setter 不得覆盖正式投影。",
            evidence=["generic:overwrite"],
            next_action="不应写入。",
        )

    assert screening_path.read_bytes() == before_screening
    assert queue_path.read_bytes() == before_queue


def test_generic_setters_allow_plain_legacy_rows(tmp_path: Path) -> None:
    from trading_os.research_assets.coverage_store import (
        enqueue_research,
        read_jsonl,
        set_screening,
        write_jsonl,
    )

    root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        root / "screening.jsonl",
        [
            {
                "symbol": "CN:300750",
                "name": "宁德时代",
                "decision": "watch_only",
                "priority": 2,
                "reason": "纯 legacy 非受管行。",
                "evidence": ["legacy:evidence"],
                "next_action": "允许显式迁移前的通用更新。",
            }
        ],
    )
    write_jsonl(
        root / "research_queue.jsonl",
        [
            {
                "symbol": "CN:300750",
                "name": "宁德时代",
                "task_type": "initial_research",
                "priority": 2,
                "status": "completed",
                "reason": "纯 legacy 非受管行。",
                "target_company_dir": "research/companies/CN/300750",
                "result_path": "reports/legacy.md",
                "result_sha256": "1" * 64,
            }
        ],
    )

    set_screening(
        root,
        symbol="CN:300750",
        name="宁德时代",
        decision="catalog",
        priority=None,
        reason="通用更新仍允许。",
        evidence=["legacy:updated"],
        next_action="等待后续触发。",
    )
    enqueue_research(
        root,
        symbol="CN:300750",
        name="宁德时代",
        priority=3,
        reason="通用 queue 更新仍允许。",
    )

    assert read_jsonl(root / "screening.jsonl")[0]["decision"] == "catalog"
    assert read_jsonl(root / "research_queue.jsonl")[0]["status"] == "pending"


def test_enqueue_rejects_formal_screening_ownership_without_mutation(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        enqueue_research,
        write_jsonl,
    )

    root = tmp_path / "coverage" / "cn-a"
    screening_path = root / "screening.jsonl"
    queue_path = root / "research_queue.jsonl"
    write_jsonl(
        screening_path,
        [
            {
                "symbol": "CN:300750",
                "name": "宁德时代",
                "decision": "deep_research",
                "priority": 1,
                "reason": "深研完成 workflow 已拥有该公司。",
                "evidence": ["deep:receipt"],
                "next_action": "只走正式完成 workflow。",
                "deep_research_completion_path": (
                    "research/companies/CN/300750/evidence/deep-completion.json"
                ),
            }
        ],
    )
    write_jsonl(
        queue_path,
        [
            {
                "symbol": "CN:300750",
                "name": "宁德时代",
                "task_type": "initial_research",
                "priority": 1,
                "status": "completed",
                "reason": "旧投影。",
                "target_company_dir": "research/companies/CN/300750",
                "result_path": "reports/legacy.md",
            }
        ],
    )
    before_screening = screening_path.read_bytes()
    before_queue = queue_path.read_bytes()

    with pytest.raises(CoverageValidationError, match="formal workflow-owned"):
        enqueue_research(
            root,
            symbol="CN:300750",
            name="宁德时代",
            priority=3,
            reason="通用 queue setter 不得覆盖正式 ownership。",
        )

    assert screening_path.read_bytes() == before_screening
    assert queue_path.read_bytes() == before_queue


def test_generic_setters_use_shared_coverage_write_lock(tmp_path: Path) -> None:
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        coverage_write_lock,
        enqueue_research,
        set_screening,
    )

    root = tmp_path / "coverage" / "cn-a"
    with coverage_write_lock(root):
        with pytest.raises(CoverageValidationError, match="coverage state is busy"):
            set_screening(
                root,
                symbol="CN:300750",
                name="宁德时代",
                decision="catalog",
                priority=None,
                reason="锁内不得重入。",
                evidence=["lock:test"],
                next_action="不应写入。",
            )
        with pytest.raises(CoverageValidationError, match="coverage state is busy"):
            enqueue_research(
                root,
                symbol="CN:300750",
                name="宁德时代",
                priority=3,
                reason="锁内不得重入。",
            )

    assert not (root / "screening.jsonl").exists()
    assert not (root / "research_queue.jsonl").exists()


def test_budgeted_quick_profile_queue_requires_budget_and_stop_conditions(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import (
        CoverageValidationError,
        enqueue_research,
        read_jsonl,
    )

    root = tmp_path / "coverage" / "cn-a"
    with pytest.raises(CoverageValidationError, match="effort_budget_hours"):
        enqueue_research(
            root,
            symbol="CN:300750",
            name="宁德时代",
            priority=1,
            reason="进入快速投资画像。",
            task_type="quick_profile",
        )

    enqueue_research(
        root,
        symbol="CN:300750",
        name="宁德时代",
        priority=1,
        reason="进入快速投资画像。",
        task_type="quick_profile",
        effort_budget_hours=1.0,
        preceding_stage="machine_triage",
        stop_conditions=["不存在可信投资路径"],
    )

    item = read_jsonl(root / "research_queue.jsonl")[0]
    assert item["task_type"] == "quick_profile"
    assert item["effort_budget_hours"] == 1.0
    assert item["preceding_stage"] == "machine_triage"
    assert item["stop_conditions"] == ["不存在可信投资路径"]


def test_reconcile_does_not_erase_pending_pre_report_stage(tmp_path: Path):
    from tests.test_company_assets import write_company
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["research"]["rebaseline_required"] = True
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        root / "research_queue.jsonl",
        [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "task_type": "quick_profile",
                "priority": 1,
                "status": "pending",
                "reason": "本周期快速画像",
                "target_company_dir": str(company_dir),
                "effort_budget_hours": 1.0,
                "preceding_stage": "machine_triage",
                "stop_conditions": ["不存在可信投资路径"],
            }
        ],
    )

    result = reconcile_research_queue(root, tmp_path, apply=False)

    assert result["change_count"] == 0
    assert read_jsonl(root / "research_queue.jsonl")[0]["status"] == "pending"


def test_reconcile_research_queue_finds_valid_completed_asset_without_writing(
    tmp_path: Path,
):
    from tests.test_company_assets import write_company
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    company_dir = write_company(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    queue_path = root / "research_queue.jsonl"
    original = {
        "symbol": "CN:600519",
        "name": "贵州茅台",
        "task_type": "initial_research",
        "priority": 1,
        "status": "pending",
        "reason": "进入研究队列。",
        "target_company_dir": str(company_dir),
        "assigned_agent": None,
        "started_at": None,
        "finished_at": None,
        "result_path": None,
        "failure_reason": None,
        "next_action": "完成初始研究。",
    }
    write_jsonl(queue_path, [original])

    result = reconcile_research_queue(root, tmp_path / "research")

    assert result["applied"] is False
    assert result["change_count"] == 1
    assert result["blocked_count"] == 0
    assert result["changes"] == [
        {
            "symbol": "CN:600519",
            "from_status": "pending",
            "to_status": "completed",
                "result_path": "reports/2026-07-21-initial-research.md",
        }
    ]
    assert read_jsonl(queue_path) == [original]


def test_reconcile_research_queue_applies_allowed_changes_and_is_idempotent(
    tmp_path: Path,
):
    from tests.test_company_assets import write_company
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    company_dir = write_company(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    queue_path = root / "research_queue.jsonl"
    records = [
        {
            "symbol": "CN:600519",
            "name": "贵州茅台",
            "task_type": "initial_research",
            "priority": 1,
            "status": "failed",
            "reason": "进入研究队列。",
            "target_company_dir": str(company_dir),
            "assigned_agent": "worker",
            "started_at": "2026-07-05T00:00:00+08:00",
            "finished_at": "2026-07-05T01:00:00+08:00",
            "result_path": None,
            "failure_reason": "timeout",
            "next_action": "重试。",
        },
        {
            "symbol": "CN:000001",
            "name": "平安银行",
            "task_type": "initial_research",
            "priority": 1,
            "status": "needs_review",
            "reason": "需要人工复核。",
            "target_company_dir": str(company_dir),
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "result_path": None,
            "failure_reason": None,
            "next_action": "人工复核。",
        },
    ]
    write_jsonl(queue_path, records)

    applied = reconcile_research_queue(root, tmp_path / "research", apply=True)
    second = reconcile_research_queue(root, tmp_path / "research")
    queue = read_jsonl(queue_path)

    assert applied["applied"] is True
    assert applied["change_count"] == 1
    assert second["change_count"] == 0
    assert queue[0]["status"] == "needs_review"
    assert queue[1]["status"] == "completed"
    assert queue[1]["result_path"] == "reports/2026-07-21-initial-research.md"
    assert queue[1]["failure_reason"] is None
    assert queue[1]["started_at"] == "2026-07-05T00:00:00+08:00"


def test_reconcile_research_queue_reports_invalid_asset_without_completing_it(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    root = tmp_path / "coverage" / "cn-a"
    queue_path = root / "research_queue.jsonl"
    company_dir = tmp_path / "research" / "companies" / "CN" / "600519"
    company_dir.mkdir(parents=True)
    (company_dir / "meta.json").write_text("{}\n", encoding="utf-8")
    record = {
        "symbol": "CN:600519",
        "name": "贵州茅台",
        "task_type": "initial_research",
        "priority": 1,
        "status": "pending",
        "reason": "进入研究队列。",
        "target_company_dir": str(company_dir),
        "assigned_agent": None,
        "started_at": None,
        "finished_at": None,
        "result_path": None,
        "failure_reason": None,
        "next_action": "完成初始研究。",
    }
    write_jsonl(queue_path, [record])

    result = reconcile_research_queue(root, tmp_path / "research", apply=True)

    assert result["change_count"] == 0
    assert result["blocked_count"] == 1
    assert result["blocked"][0]["symbol"] == "CN:600519"
    assert "schema_version 2" in result["blocked"][0]["error"]
    assert read_jsonl(queue_path) == [record]


def test_reconcile_resets_completed_legacy_asset_that_requires_rebaseline(
    tmp_path: Path,
):
    from tests.test_company_assets import write_company
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        reconcile_research_queue,
        write_jsonl,
    )

    company_dir = write_company(tmp_path)
    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["research"]["rebaseline_required"] = True
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    root = tmp_path / "coverage" / "cn-a"
    queue_path = root / "research_queue.jsonl"
    write_jsonl(
        queue_path,
        [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "task_type": "initial_research",
                "priority": 1,
                "status": "completed",
                "reason": "旧系统研究已完成。",
                "target_company_dir": str(company_dir),
                "assigned_agent": "legacy-worker",
                "started_at": "2026-07-05T00:00:00+08:00",
                "finished_at": "2026-07-05T01:00:00+08:00",
                "result_path": "reports/legacy.md",
                "failure_reason": None,
                "next_action": "查看旧报告。",
            }
        ],
    )

    result = reconcile_research_queue(root, tmp_path / "research", apply=True)
    queue_item = read_jsonl(queue_path)[0]

    assert result["change_count"] == 1
    assert result["changes"][0]["to_status"] == "requires_rebaseline"
    assert queue_item["status"] == "requires_rebaseline"
    assert queue_item["result_path"] is None
    assert queue_item["assigned_agent"] is None
    assert queue_item["started_at"] is None
    assert queue_item["finished_at"] is None
    assert reconcile_research_queue(root, tmp_path / "research")["change_count"] == 0
