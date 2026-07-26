from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RECORDED_AT = dt.datetime.fromisoformat("2026-07-27T10:00:00+08:00")


def _policy() -> dict:
    return json.loads(
        (ROOT / "policies" / "research-allocation.json").read_text(encoding="utf-8")
    )["payload"]


def _package(
    symbol: str,
    name: str,
    agent: str,
    *,
    research_value: str = "medium",
    valuation_signal: str = "possible",
    triggers: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "cycle_id": "2026-07-27-triage-test",
        "symbol": symbol,
        "company_name": name,
        "as_of": "2026-07-27",
        "information_cutoff": "2026-07-27T09:30:00+08:00",
        "price_as_of": "2026-07-27T09:25:00+08:00",
        "price_source_id": "quote",
        "current_price": 10.0,
        "business_legibility": "clear",
        "survival_status": "pass",
        "governance_status": "acceptable",
        "earnings_legibility": "plausible",
        "valuation_signal": valuation_signal,
        "research_value": research_value,
        "decisive_question": "正常化所有者收益是否可持续",
        "reason_codes": ["latest_filing_and_price_checked"],
        "revisit_triggers": triggers or [],
        "sources": [
            {
                "source_id": "filing",
                "tier": "S1",
                "title": "最新定期报告",
                "accessed_at": "2026-07-27T09:00:00+08:00",
                "url": "https://example.com/filing",
                "local_path": None,
                "supports": ["生存", "治理", "盈利"],
            },
            {
                "source_id": "quote",
                "tier": "S2",
                "title": "最新行情",
                "accessed_at": "2026-07-27T09:25:00+08:00",
                "url": "https://example.com/quote",
                "local_path": None,
                "supports": ["价格"],
            },
        ],
        "provenance": {
            "agent": agent,
            "model": "test-model",
            "tools": ["repository", "browser"],
            "generated_at": "2026-07-27T09:45:00+08:00",
        },
    }


def _coverage(root: Path) -> None:
    from trading_os.research_assets.coverage_store import write_jsonl

    coverage_root = root / "coverage" / "cn-a"
    symbols = [
        ("CN:000001", "公司一", 2, ["balanced"]),
        ("CN:000002", "公司二", 1, ["value_income", "balanced"]),
        ("CN:000003", "公司三", 3, ["false_negative_audit"]),
    ]
    write_jsonl(
        coverage_root / "companies.jsonl",
        [{"symbol": symbol, "name": name} for symbol, name, _, _ in symbols],
    )
    write_jsonl(
        coverage_root / "screening.jsonl",
        [
            {
                "symbol": symbol,
                "name": name,
                "decision": "rapid_triage",
                "priority": priority,
                "reason": "测试快速甄别",
                "evidence": ["allocation:test"],
                "next_action": "完成快速甄别",
            }
            for symbol, name, priority, _ in symbols
        ],
    )
    write_jsonl(
        coverage_root / "research_queue.jsonl",
        [
            {
                "symbol": symbol,
                "name": name,
                "task_type": "rapid_triage",
                "priority": priority,
                "status": "pending",
                "reason": "测试快速甄别",
                "target_company_dir": f"research/companies/CN/{symbol[-6:]}",
                "assigned_agent": None,
                "started_at": None,
                "finished_at": None,
                "result_path": None,
                "failure_reason": None,
                "next_action": "完成快速甄别",
                "effort_budget_hours": 0.25,
                "preceding_stage": "machine_triage",
                "stop_conditions": ["没有继续研究价值"],
                "allocation_sha256": "a" * 64,
                "selected_by": lenses,
            }
            for symbol, name, priority, lenses in symbols
        ],
    )
    write_jsonl(coverage_root / "runs.jsonl", [], sort_key="run_id")


def test_triage_claim_binds_agent_and_release_preserves_attempt(tmp_path: Path):
    from trading_os.research_assets.triage_workflow import (
        claim_rapid_triage_task,
        release_rapid_triage_task,
    )

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    claimed = claim_rapid_triage_task(
        root=root,
        agent="/root/company-1",
        symbol="CN:000001",
        claimed_at=RECORDED_AT,
    )
    assert claimed["symbol"] == "CN:000001"
    assert claimed["effort_budget_hours"] == 0.25
    assert claim_rapid_triage_task(
        root=root,
        agent="/root/company-1",
        symbol="CN:000001",
        claimed_at=RECORDED_AT,
    )["idempotent"] is True

    released = release_rapid_triage_task(
        root=root,
        agent="/root/company-1",
        symbol="CN:000001",
        failure_reason="测试工具失败",
        released_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    assert released["status"] == "pending"
    assert released["attempt_count"] == 1


def test_completion_order_cannot_promote_before_full_cohort_comparison(
    tmp_path: Path,
):
    from trading_os.research_assets.research_allocation import (
        ResearchAllocationError,
    )
    from trading_os.research_assets.triage_workflow import (
        finalize_rapid_triage_cycle,
        record_rapid_triage_package,
    )

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    record_rapid_triage_package(
        _package("CN:000001", "公司一", "/root/company-1"),
        root=root,
        recorded_at=RECORDED_AT,
    )
    policy = copy.deepcopy(_policy())
    policy["quick_profile_capacity_per_cycle"] = 1
    with pytest.raises(ResearchAllocationError, match="cohort is incomplete"):
        finalize_rapid_triage_cycle(
            root=root,
            cycle_id="2026-07-27-triage-test",
            policy=policy,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
        )


def test_full_cohort_is_ranked_once_and_only_top_candidate_gets_profile_budget(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        validate_coverage_root,
    )
    from trading_os.research_assets.triage_workflow import (
        finalize_rapid_triage_cycle,
        rapid_triage_cycle_status,
        record_rapid_triage_package,
    )

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    packages = [
        _package("CN:000001", "公司一", "/root/company-1"),
        _package(
            "CN:000002",
            "公司二",
            "/root/company-2",
            research_value="high",
            valuation_signal="attractive",
        ),
        _package(
            "CN:000003",
            "公司三",
            "/root/company-3",
            valuation_signal="unattractive",
            triggers=[
                {
                    "type": "price",
                    "condition": "价格下跌20%",
                    "reason": "重新获得研究赔率",
                }
            ],
        ),
    ]
    for index, package in enumerate(packages):
        record_rapid_triage_package(
            package,
            root=root,
            recorded_at=RECORDED_AT + dt.timedelta(minutes=index),
        )

    policy = copy.deepcopy(_policy())
    policy["quick_profile_capacity_per_cycle"] = 1
    result = finalize_rapid_triage_cycle(
        root=root,
        cycle_id="2026-07-27-triage-test",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=10),
    )

    assert result["selected_symbols"] == ["CN:000002"]
    repeated = finalize_rapid_triage_cycle(
        root=root,
        cycle_id="2026-07-27-triage-test",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=11),
    )
    assert repeated["selected_symbols"] == ["CN:000002"]
    assert repeated["idempotent"] is True
    queue = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert queue["CN:000002"]["task_type"] == "quick_profile"
    assert queue["CN:000002"]["status"] == "pending"
    assert queue["CN:000002"]["preceding_stage"] == "rapid_triage"
    assert queue["CN:000001"]["task_type"] == "rapid_triage"
    assert queue["CN:000001"]["status"] == "completed"
    assert queue["CN:000003"]["triage_disposition"] == "price_watch"
    status = rapid_triage_cycle_status(
        root=root,
        cycle_id="2026-07-27-triage-test",
    )
    assert status["remaining_count"] == 0
    assert status["selection_finalized"] is True
    assert status["invalid_artifact_count"] == 0
    validate_coverage_root(root)
