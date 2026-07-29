from __future__ import annotations

import json
from pathlib import Path

DECISIONS = {
    "catalog",
    "quick_profile",
    "scoped_research",
    "targeted_followup",
    "deep_research",
    "price_watch",
    "reassign_or_stop",
    "watch_only",
    "conditional_stop",
    "hard_exclusion",
    "skip_risk",
    "skip_too_small",
    "skip_not_in_scope",
    "needs_manual_review",
}

QUEUE_STATUSES = {
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "needs_review",
}


def test_coverage_examples_are_valid_json():
    root = Path(__file__).resolve().parents[1]

    for path in (root / "coverage" / "cn-a").glob("*.example.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["market"] == "CN"


def test_coverage_jsonl_working_files_exist():
    root = Path(__file__).resolve().parents[1]

    for name in ["companies.jsonl", "screening.jsonl", "research_queue.jsonl", "runs.jsonl"]:
        assert (root / "coverage" / "cn-a" / name).exists()


def test_screening_example_uses_fixed_decision_protocol():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "coverage" / "cn-a" / "screening.example.json").read_text(
            encoding="utf-8"
        )
    )

    decisions = {item["decision"] for item in payload["results"]}
    assert decisions <= DECISIONS
    assert {"quick_profile", "skip_not_in_scope"} <= decisions
    for item in payload["results"]:
        assert item["reason"].strip()
        assert item["evidence"]
        assert item["next_action"].strip()


def test_research_queue_example_is_resumable():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "coverage" / "cn-a" / "research-queue.example.json").read_text(
            encoding="utf-8"
        )
    )

    for item in payload["items"]:
        assert item["status"] in QUEUE_STATUSES
        assert item["target_company_dir"].startswith("research/companies/CN/")
        assert item["next_action"].strip()
        if item["task_type"] == "quick_profile":
            assert item["effort_budget_hours"] > 0
            assert item["preceding_stage"]
            assert item["stop_conditions"]


def test_docs_route_full_market_work_through_coverage():
    root = Path(__file__).resolve().parents[1]
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    screening = (root / "playbooks" / "screening.md").read_text(encoding="utf-8")

    assert "coverage/" in agents
    assert "playbooks/screening.md" in agents
    assert "coverage/" in readme
    assert "AGENTS.md" in claude
    assert "coverage/" in claude
    assert "coverage status" in agents
    assert "coverage validate" in readme
    assert "全覆盖漏斗" in screening
    assert "每家公司独立 rapid triage" in screening
    assert "机器不得使用市场估值" in screening
    assert "deep_research" in screening
    assert "quick_profile" in screening
    assert "程序化选股、人工提名和外部清单" in screening
    assert "hard_exclusion" in screening
    assert "research_queue.jsonl" in screening
    assert "小市值、低流动性、暂时亏损" in screening
    assert "单公司研究或单公司复核 agent 一次只处理一家公司" in agents
    assert "跨公司 allocation、质量统计和组合综合是独立角色" in agents
    assert "组合层可给 `buy_now`" in agents
