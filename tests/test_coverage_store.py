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
