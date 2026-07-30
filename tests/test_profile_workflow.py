from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECORDED_AT = dt.datetime.fromisoformat("2026-07-26T10:00:00+08:00")


def _policy() -> dict:
    return json.loads(
        (ROOT / "policies" / "research-allocation.json").read_text(encoding="utf-8")
    )["payload"]


def _profile(**changes) -> dict:
    profile = {
        "research_stage": "quick_profile",
        "symbol": "CN:600519",
        "as_of": "2026-07-26",
        "information_cutoff": "2026-07-26T09:00:00+08:00",
        "s1_source_count": 2,
        "circle_of_competence": "inside",
        "business_model_understood": True,
        "survival_status": "pass",
        "governance_status": "acceptable",
        "normalized_earnings_status": "plausible",
        "valuation": {
            "current_price": 80.0,
            "rough_fair_value_range": [95.0, 110.0],
            "base_expected_annual_return": 0.11,
            "bull_expected_annual_return": 0.16,
            "market_implied_assumptions_tested": True,
        },
        "variant_perception": "市场低估正常化现金流",
        "decisive_unknowns": ["下一期自由现金流能否确认"],
        "counterevidence": ["需求可能恶化", "竞争可能压低利润率"],
        "structural_stop_reasons": [],
        "revisit_triggers": [
            {
                "type": "price",
                "condition": "预期年化回报达到12%",
                "reason": "重新评估是否值得承保",
            }
        ],
    }
    profile.update(changes)
    return profile


def _package(**changes) -> dict:
    sections = {
        section: {"conclusion": f"{section}结论", "source_ids": ["annual", "quote"]}
        for section in (
            "business_summary",
            "owner_earnings_and_cycle",
            "survival",
            "governance",
            "valuation_basis",
            "market_mispricing",
            "decisive_unknowns",
        )
    }
    package = {
        "schema_version": 2,
        "cycle_id": "2026-07-26-test-cycle",
        "company_name": "贵州茅台",
        "profile": _profile(),
        "price_as_of": "2026-07-24T15:00:00+08:00",
        "price_source_id": "quote",
        "provenance": {
            "agent": "/root/test-company",
            "model": "test-model",
            "tools": ["repository", "browser"],
            "generated_at": "2026-07-26T09:30:00+08:00",
        },
        "analysis": sections,
        "sources": [
            {
                "source_id": "annual",
                "tier": "S1",
                "title": "2025年年度报告",
                "publisher": "贵州茅台",
                "published_at": "2026-03-31",
                "accessed_at": "2026-07-26T09:00:00+08:00",
                "url": "https://example.com/annual",
                "local_path": None,
                "supports": ["业务", "盈利", "治理"],
            },
            {
                "source_id": "q1",
                "tier": "S1",
                "title": "2026年一季度报告",
                "publisher": "贵州茅台",
                "published_at": "2026-04-30",
                "accessed_at": "2026-07-26T09:00:00+08:00",
                "url": "https://example.com/q1",
                "local_path": None,
                "supports": ["最新经营"],
            },
            {
                "source_id": "quote",
                "tier": "S2",
                "title": "收盘行情",
                "publisher": "交易所行情聚合",
                "published_at": "2026-07-24",
                "accessed_at": "2026-07-26T09:00:00+08:00",
                "url": "https://example.com/quote",
                "local_path": None,
                "supports": ["最新价格"],
            },
        ],
    }
    package.update(changes)
    return package


def _coverage(root: Path, *, extra_queue: list[dict] | None = None) -> None:
    from trading_os.research_assets.coverage_store import write_jsonl

    coverage_root = root / "coverage" / "cn-a"
    write_jsonl(
        coverage_root / "companies.jsonl",
        [{"symbol": "CN:600519", "name": "贵州茅台"}],
    )
    write_jsonl(
        coverage_root / "screening.jsonl",
        [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "decision": "quick_profile",
                "priority": 1,
                "reason": "测试画像",
                "evidence": ["allocation:test"],
                "next_action": "完成画像",
            }
        ],
    )
    queue = [
        {
            "symbol": "CN:600519",
            "name": "贵州茅台",
            "task_type": "quick_profile",
            "priority": 1,
            "status": "pending",
            "reason": "测试画像",
            "target_company_dir": "research/companies/CN/600519",
            "effort_budget_hours": 1.0,
            "preceding_stage": "machine_triage",
            "stop_conditions": ["不存在可信路径"],
            "allocation_sha256": "a" * 64,
            "selected_by": ["balanced"],
            "triage_selection_path": (
                "coverage/cn-a/triage/test/selection.json"
            ),
        }
    ]
    queue.extend(extra_queue or [])
    write_jsonl(coverage_root / "research_queue.jsonl", queue)
    write_jsonl(coverage_root / "runs.jsonl", [], sort_key="run_id")


def test_record_profile_waits_for_comparison_then_advances_to_scoped(tmp_path: Path):
    from trading_os.research_assets.coverage_store import (
        read_jsonl,
        validate_coverage_root,
    )
    from trading_os.research_assets.profile_workflow import (
        finalize_profile_stage,
        profile_cycle_status,
        record_profile_package,
    )
    from trading_os.research_assets.sealing import verify_sealed

    _coverage(tmp_path)
    result = record_profile_package(
        _package(),
        root=tmp_path / "coverage" / "cn-a",
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )

    assert result["next_stage"] == "profile_candidate"
    assert result["portfolio_action"] is None
    assert verify_sealed(tmp_path / result["profile_path"]).sha256 == result["profile_sha256"]
    assert verify_sealed(tmp_path / result["evaluation_path"]).sha256 == result["evaluation_sha256"]
    queue = read_jsonl(tmp_path / "coverage" / "cn-a" / "research_queue.jsonl")[0]
    assert queue["task_type"] == "quick_profile"
    assert queue["status"] == "completed"
    assert queue["stage_history"][0]["stage"] == "quick_profile"
    promoted = finalize_profile_stage(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    assert promoted["selected_symbols"] == ["CN:600519"]
    queue = read_jsonl(
        tmp_path / "coverage" / "cn-a" / "research_queue.jsonl"
    )[0]
    assert queue["task_type"] == "scoped_research"
    assert queue["status"] == "pending"
    assert queue["effort_budget_hours"] == 4.0
    repeated = finalize_profile_stage(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=2),
    )
    assert repeated["selected_symbols"] == ["CN:600519"]
    assert repeated["idempotent"] is True
    validate_coverage_root(tmp_path / "coverage" / "cn-a")
    status = profile_cycle_status(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
    )
    assert status["cohort_count"] == 1
    assert status["recorded_count"] == 1
    assert status["remaining_count"] == 0
    assert status["invalid_artifact_count"] == 0


def test_agent_profile_comparison_is_score_free_and_controls_budget(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        build_profile_comparison_packet,
        finalize_profile_stage_with_agent_decisions,
        record_profile_package,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.sealing import seal_json, verify_sealed

    _coverage(tmp_path)
    predecessor_path = (
        tmp_path / "coverage" / "cn-a" / "triage" / "test" / "selection.json"
    )
    seal_json(
        predecessor_path,
        {
            "schema_version": 1,
            "cycle_id": "test",
            "ranking": [
                {
                    "ordinal": 1,
                    "symbol": "CN:600519",
                    "selected_for_quick_profile": True,
                }
            ],
            "portfolio_action": None,
        },
        artifact_type="rapid_triage_cross_company_selection",
        sealed_at=RECORDED_AT - dt.timedelta(minutes=2),
    )
    record_profile_package(
        _package(),
        root=tmp_path / "coverage" / "cn-a",
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    comparison = build_profile_comparison_packet(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        created_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    packet_path = tmp_path / comparison["comparison_path"]
    assert verify_sealed(packet_path).artifact_type == "quick_profile_comparison_packet"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["cohort_count"] == 1
    assert packet["rows"][0]["symbol"] == "CN:600519"
    assert "rank" not in packet["rows"][0]
    assert "priority" not in packet["rows"][0]
    assert "profile_priority_score" not in packet["rows"][0]

    decisions = {
        "schema_version": 1,
        "cycle_id": "2026-07-26-test-cycle",
        "evaluated_stage": "quick_profile",
        "comparison_sha256": comparison["comparison_sha256"],
        "decisions": [
            {
                "symbol": "CN:600519",
                "decision": "select_scoped_research",
                "reason": "增量研究可解决现金收益归属并改变组合候选判断。",
                "decisive_question": "普通股正常化现金收益能否支撑目标回报？",
                "counterevidence_considered": ["需求恶化可能压低利润。"],
            }
        ],
        "provenance": {
            "agent": "/root/profile-allocation",
            "model": "test-model",
            "tools": ["sealed comparison packet"],
            "generated_at": (RECORDED_AT + dt.timedelta(minutes=2)).isoformat(),
        },
    }
    not_independent = copy.deepcopy(decisions)
    not_independent["provenance"]["agent"] = "/root/test-company"
    missing = copy.deepcopy(decisions)
    missing["decisions"] = []
    with pytest.raises(ResearchAllocationError, match="cover every comparison row"):
        finalize_profile_stage_with_agent_decisions(
            root=tmp_path / "coverage" / "cn-a",
            cycle_id="2026-07-26-test-cycle",
            stage="quick_profile",
            policy=_policy(),
            decisions=missing,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=3),
        )
    with pytest.raises(ResearchAllocationError, match="must be independent"):
        finalize_profile_stage_with_agent_decisions(
            root=tmp_path / "coverage" / "cn-a",
            cycle_id="2026-07-26-test-cycle",
            stage="quick_profile",
            policy=_policy(),
            decisions=not_independent,
            finalized_at=RECORDED_AT + dt.timedelta(minutes=3),
        )
    selected = finalize_profile_stage_with_agent_decisions(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=3),
    )
    assert selected["selected_symbols"] == ["CN:600519"]
    selection = json.loads(
        (tmp_path / selected["selection_path"]).read_text(encoding="utf-8")
    )
    assert selection["reviewed_count"] == 1
    assert selection["risk_cluster_mode"] == "conservative_unclassified"
    assert selection["agent_decision"] == decisions
    queue = read_jsonl(tmp_path / "coverage" / "cn-a" / "research_queue.jsonl")
    assert queue[0]["task_type"] == "scoped_research"
    assert queue[0]["status"] == "pending"
    assert queue[0]["effort_budget_hours"] == 4.0
    repeated = finalize_profile_stage_with_agent_decisions(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=4),
    )
    assert repeated["idempotent"] is True


def test_manager_screen_profile_cohort_supersedes_legacy_allocation(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_workflow import (
        build_profile_comparison_packet,
        record_profile_package,
    )
    from trading_os.research_assets.sealing import seal_json

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    predecessor_path = (
        coverage_root / "manager-screen" / "current" / "batch-001" / "result.json"
    )
    sealed = seal_json(
        predecessor_path,
        {
            "schema_version": 1,
            "decisions": [
                {"symbol": "CN:600519", "route": "send_to_analyst"},
                {"symbol": "CN:000001", "route": "pass"},
            ],
            "portfolio_action": None,
        },
        artifact_type="manager_screen_result",
        sealed_at=RECORDED_AT - dt.timedelta(minutes=2),
    )
    queue_path = coverage_root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0].update(
        {
            "preceding_stage": "manager_screen",
            "manager_screen_result_path": predecessor_path.relative_to(
                tmp_path
            ).as_posix(),
            "manager_screen_result_sha256": sealed.sha256,
            "triage_selection_path": "coverage/cn-a/triage/legacy/selection.json",
        }
    )
    queue.append(
        {
            "symbol": "CN:000001",
            "name": "legacy",
            "task_type": "quick_profile",
            "status": "completed",
            "allocation_sha256": "a" * 64,
            "profile_cycle_id": "2026-07-25-legacy-cycle",
        }
    )
    write_jsonl(queue_path, queue)

    recorded = record_profile_package(
        _package(),
        root=coverage_root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    assert recorded["next_stage"] == "profile_candidate"
    evaluation = json.loads(
        (tmp_path / recorded["evaluation_path"]).read_text(encoding="utf-8")
    )
    assert evaluation["allocation_sha256"] is None
    current = read_jsonl(queue_path)[1]
    assert current["symbol"] == "CN:600519"
    assert "allocation_sha256" not in current
    assert "triage_selection_path" not in current

    comparison = build_profile_comparison_packet(
        root=coverage_root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        created_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    packet = json.loads(
        (tmp_path / comparison["comparison_path"]).read_text(encoding="utf-8")
    )
    assert [row["symbol"] for row in packet["rows"]] == ["CN:600519"]


def test_profile_package_rejects_probable_gbk_latin1_mojibake(tmp_path: Path):
    from trading_os.research_assets.profile_workflow import record_profile_package
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    _coverage(tmp_path)
    package = _package()
    package["profile"]["variant_perception"] = (
        "市场可能低估正常化现金流".encode("gbk").decode("latin-1")
    )
    with pytest.raises(ResearchAllocationError, match="probable GBK/Latin-1 mojibake"):
        record_profile_package(
            package,
            root=tmp_path / "coverage" / "cn-a",
            policy=_policy(),
            policy_reference="research-allocation.default@1.0.0",
            recorded_at=RECORDED_AT,
        )


def test_current_triage_selection_excludes_old_unselected_profile_history(
    tmp_path: Path,
):
    from trading_os.research_assets.profile_workflow import (
        finalize_profile_stage,
        profile_cycle_status,
        record_profile_package,
    )
    from trading_os.research_assets.sealing import seal_json

    binding = "coverage/cn-a/triage/test/selection.json"
    old_unselected = {
        "symbol": "CN:000002",
        "name": "万科A",
        "task_type": "rapid_triage",
        "priority": 1,
        "status": "completed",
        "reason": "本轮快速甄别未获得正式画像预算",
        "target_company_dir": "research/companies/CN/000002",
        "effort_budget_hours": 0.25,
        "preceding_stage": "machine_triage",
        "stop_conditions": ["不存在可信路径"],
        "allocation_sha256": "b" * 64,
        "selected_by": ["crisis_mispricing"],
        "triage_selection_path": binding,
        "profile_cycle_id": "2026-07-25-old-cycle",
        "stage_history": [
            {
                "stage": "quick_profile",
                "status": "completed",
                "result_path": "legacy/000002.profile.json",
                "evaluation_path": "legacy/000002.evaluation.json",
            }
        ],
    }
    _coverage(tmp_path, extra_queue=[old_unselected])
    selection_path = tmp_path / binding
    seal_json(
        selection_path,
        {
            "schema_version": 1,
            "cycle_id": "2026-07-26-test-cycle",
            "ranking": [
                {
                    "symbol": "CN:600519",
                    "selected_for_quick_profile": True,
                },
                {
                    "symbol": "CN:000002",
                    "selected_for_quick_profile": False,
                },
            ],
        },
        artifact_type="rapid_triage_cross_company_selection",
        sealed_at=RECORDED_AT,
    )
    record_profile_package(
        _package(),
        root=tmp_path / "coverage" / "cn-a",
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )

    status = profile_cycle_status(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
    )
    assert status["cohort_count"] == 1
    assert status["recorded_count"] == 1
    assert status["remaining_count"] == 0

    promoted = finalize_profile_stage(
        root=tmp_path / "coverage" / "cn-a",
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    assert promoted["cohort_count"] == 1
    assert promoted["selected_symbols"] == ["CN:600519"]


def test_profile_status_uses_stage_history_after_deep_research_reconcile(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_workflow import (
        profile_cycle_status,
        record_profile_package,
    )

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    record_profile_package(
        _package(),
        root=coverage_root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )

    queue = read_jsonl(coverage_root / "research_queue.jsonl")
    queue[0]["status"] = "completed"
    queue[0]["result_path"] = "reports/2026-07-26-initial-research-v2.md"
    write_jsonl(coverage_root / "research_queue.jsonl", queue)

    status = profile_cycle_status(
        root=coverage_root,
        cycle_id="2026-07-26-test-cycle",
    )
    assert status["recorded_count"] == 1
    assert status["invalid_artifact_count"] == 0


def test_scoped_research_also_waits_for_peer_comparison_before_deep_research(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        finalize_profile_stage,
        record_profile_package,
    )

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    policy = _policy()
    record_profile_package(
        _package(),
        root=root,
        policy=policy,
        policy_reference="research-allocation.default@2.0.0",
        recorded_at=RECORDED_AT,
    )
    finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
    )

    scoped_package = _package()
    scoped_package["profile"]["research_stage"] = "scoped_research"
    scoped_package["provenance"]["generated_at"] = (
        RECORDED_AT + dt.timedelta(minutes=2)
    ).isoformat()
    result = record_profile_package(
        scoped_package,
        root=root,
        policy=policy,
        policy_reference="research-allocation.default@2.0.0",
        recorded_at=RECORDED_AT + dt.timedelta(minutes=3),
    )
    assert result["next_stage"] == "deep_candidate"
    queued = read_jsonl(root / "research_queue.jsonl")[0]
    assert queued["task_type"] == "scoped_research"
    assert queued["status"] == "completed"

    promoted = finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="scoped_research",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=4),
    )
    assert promoted["selected_symbols"] == ["CN:600519"]
    queued = read_jsonl(root / "research_queue.jsonl")[0]
    assert queued["task_type"] == "deep_research"
    assert queued["status"] == "pending"
    assert queued["preceding_stage"] == "scoped_research"
    assert queued["effort_budget_hours"] == 24.0


def test_record_profile_rejects_self_asserted_s1_count(tmp_path: Path):
    from trading_os.research_assets.profile_workflow import record_profile_package
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    _coverage(tmp_path)
    package = _package()
    package["profile"]["s1_source_count"] = 3

    with pytest.raises(ResearchAllocationError, match="s1_source_count"):
        record_profile_package(
            package,
            root=tmp_path / "coverage" / "cn-a",
            policy=_policy(),
            policy_reference="research-allocation.default@1.0.0",
            recorded_at=RECORDED_AT,
        )
    assert not (tmp_path / "coverage" / "cn-a" / "profiles").exists()


def test_price_watch_is_completed_with_a_reactivation_path(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import record_profile_package

    _coverage(tmp_path)
    package = _package()
    package["profile"]["valuation"]["base_expected_annual_return"] = 0.04
    package["profile"]["valuation"]["bull_expected_annual_return"] = 0.08

    result = record_profile_package(
        package,
        root=tmp_path / "coverage" / "cn-a",
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )

    assert result["next_stage"] == "price_watch"
    queue = read_jsonl(tmp_path / "coverage" / "cn-a" / "research_queue.jsonl")[0]
    assert queue["status"] == "completed"
    screening = read_jsonl(tmp_path / "coverage" / "cn-a" / "screening.jsonl")[0]
    assert screening["decision"] == "price_watch"
    assert "价格" in screening["next_action"]


def test_profile_completion_does_not_consume_scoped_capacity_before_comparison(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import record_profile_package

    other = {
        "symbol": "CN:000001",
        "name": "其他银行",
        "task_type": "scoped_research",
        "priority": 1,
        "status": "pending",
        "reason": "已占用容量",
        "target_company_dir": "research/companies/CN/000001",
        "effort_budget_hours": 4.0,
        "preceding_stage": "quick_profile",
        "stop_conditions": ["投资路径不成立"],
    }
    _coverage(tmp_path, extra_queue=[other])
    policy = copy.deepcopy(_policy())
    policy["stage_capacity_per_cycle"]["scoped_research"] = 1

    result = record_profile_package(
        _package(),
        root=tmp_path / "coverage" / "cn-a",
        policy=policy,
        policy_reference="research-allocation.default@test",
        recorded_at=RECORDED_AT,
    )

    assert result["capacity_wait"] is False
    assert result["queue_status"] == "completed"
    queue = {
        item["symbol"]: item
        for item in read_jsonl(tmp_path / "coverage" / "cn-a" / "research_queue.jsonl")
    }
    assert queue["CN:600519"]["task_type"] == "quick_profile"
    assert "横向比较" in queue["CN:600519"]["reason"]


def test_cli_record_profile_is_the_production_entrypoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    from trading_os.cli import main

    _coverage(tmp_path)
    input_path = tmp_path / "profile-package.json"
    input_path.write_text(
        json.dumps(_package(), ensure_ascii=False),
        encoding="utf-8",
    )

    code = main(
        [
            "coverage",
            "record-profile",
            "--root",
            str(tmp_path / "coverage" / "cn-a"),
            "--input",
            str(input_path),
            "--policy",
            str(ROOT / "policies" / "research-allocation.json"),
            "--at",
            RECORDED_AT.isoformat(),
        ]
    )

    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["next_stage"] == "profile_candidate"


def test_claim_profile_task_prevents_duplicate_company_assignment(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import claim_profile_task
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    first = claim_profile_task(
        root=coverage_root,
        agent="/root/qp_600519",
        claimed_at=RECORDED_AT,
        symbol="CN:600519",
    )

    assert first["symbol"] == "CN:600519"
    assert first["idempotent"] is False
    again = claim_profile_task(
        root=coverage_root,
        agent="/root/qp_600519",
        claimed_at=RECORDED_AT,
        symbol="CN:600519",
    )
    assert again["idempotent"] is True
    with pytest.raises(ResearchAllocationError, match="no eligible"):
        claim_profile_task(
            root=coverage_root,
            agent="/root/another",
            claimed_at=RECORDED_AT,
            symbol="CN:600519",
        )
    queue = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    assert queue["status"] == "running"
    assert queue["assigned_agent"] == "/root/qp_600519"


def test_deep_research_task_can_be_claimed_and_released(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        release_profile_task,
    )

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    queue_path = coverage_root / "research_queue.jsonl"
    queue = read_jsonl(queue_path)
    queue[0].update(
        {
            "task_type": "deep_research",
            "preceding_stage": "scoped_research",
            "effort_budget_hours": 24.0,
        }
    )
    write_jsonl(queue_path, queue)

    claimed = claim_profile_task(
        root=coverage_root,
        agent="/root/deep_600519",
        claimed_at=RECORDED_AT,
        symbol="CN:600519",
    )
    assert claimed["task_type"] == "deep_research"
    assert claimed["assigned_agent"] == "/root/deep_600519"

    released = release_profile_task(
        root=coverage_root,
        agent="/root/deep_600519",
        symbol="CN:600519",
        failure_reason="issuer filing unavailable",
        released_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    assert released["status"] == "pending"
    queue = read_jsonl(queue_path)[0]
    assert queue["task_type"] == "deep_research"
    assert queue["assigned_agent"] is None
    assert queue["attempt_history"][0]["status"] == "failed"


def test_release_profile_task_preserves_failure_and_allows_reassignment(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        release_profile_task,
    )

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    claim_profile_task(
        root=coverage_root,
        agent="/root/first",
        claimed_at=RECORDED_AT,
        symbol="CN:600519",
    )
    released_at = dt.datetime.fromisoformat("2026-07-26T10:05:00+08:00")
    released = release_profile_task(
        root=coverage_root,
        agent="/root/first",
        symbol="CN:600519",
        failure_reason="official PDF extraction timed out",
        released_at=released_at,
    )

    assert released["attempt_count"] == 1
    queue = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    assert queue["status"] == "pending"
    assert queue["assigned_agent"] is None
    assert queue["attempt_history"] == [
        {
            "agent": "/root/first",
            "started_at": RECORDED_AT.isoformat(),
            "finished_at": released_at.isoformat(),
            "status": "failed",
            "failure_reason": "official PDF extraction timed out",
        }
    ]

    reassigned = claim_profile_task(
        root=coverage_root,
        agent="/root/retry",
        claimed_at=dt.datetime.fromisoformat("2026-07-26T10:06:00+08:00"),
        symbol="CN:600519",
    )
    assert reassigned["assigned_agent"] == "/root/retry"
    queue = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    assert len(queue["attempt_history"]) == 1


def test_release_profile_task_rejects_non_owner(tmp_path: Path):
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        release_profile_task,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    claim_profile_task(
        root=coverage_root,
        agent="/root/owner",
        claimed_at=RECORDED_AT,
        symbol="CN:600519",
    )
    with pytest.raises(ResearchAllocationError, match="only the assigned agent"):
        release_profile_task(
            root=coverage_root,
            agent="/root/other",
            symbol="CN:600519",
            failure_reason="not mine",
            released_at=dt.datetime.fromisoformat("2026-07-26T10:05:00+08:00"),
        )


def test_record_profile_rejects_wrong_assigned_agent(tmp_path: Path):
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        record_profile_package,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    claim_profile_task(
        root=coverage_root,
        agent="/root/assigned",
        claimed_at=RECORDED_AT,
        symbol="CN:600519",
    )

    with pytest.raises(ResearchAllocationError, match="does not match queue assignment"):
        record_profile_package(
            _package(),
            root=coverage_root,
            policy=_policy(),
            policy_reference="research-allocation.default@1.0.0",
            recorded_at=RECORDED_AT,
        )


def test_targeted_followup_reuses_preceding_profile_stage_and_can_resolve_gap(
    tmp_path: Path,
):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        record_profile_package,
    )

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    first_package = _package()
    first_package["profile"]["governance_status"] = "uncertain"
    first_package["profile"]["normalized_earnings_status"] = "uncertain"
    first_package["profile"]["valuation"]["base_expected_annual_return"] = 0.06
    first_package["profile"]["valuation"]["bull_expected_annual_return"] = 0.12
    first = record_profile_package(
        first_package,
        root=coverage_root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    assert first["next_stage"] == "targeted_followup"

    claimed_at = dt.datetime.fromisoformat("2026-07-26T10:01:00+08:00")
    claim = claim_profile_task(
        root=coverage_root,
        agent="/root/followup_600519",
        claimed_at=claimed_at,
        symbol="CN:600519",
    )
    assert claim["task_type"] == "targeted_followup"

    resolved = _package()
    resolved["profile"]["information_cutoff"] = "2026-07-26T10:03:00+08:00"
    resolved["profile"]["valuation"]["base_expected_annual_return"] = 0.06
    resolved["profile"]["valuation"]["bull_expected_annual_return"] = 0.12
    resolved["provenance"]["agent"] = "/root/followup_600519"
    resolved["provenance"]["generated_at"] = "2026-07-26T10:04:00+08:00"
    second = record_profile_package(
        resolved,
        root=coverage_root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=dt.datetime.fromisoformat("2026-07-26T10:05:00+08:00"),
    )

    assert second["next_stage"] == "price_watch"
    queue = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    assert queue["status"] == "completed"
    assert [item["stage"] for item in queue["stage_history"]] == [
        "quick_profile",
        "targeted_followup",
    ]


def test_agent_defer_preserves_completed_targeted_followup_state(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        build_profile_comparison_packet,
        claim_profile_task,
        finalize_profile_stage_with_agent_decisions,
        record_profile_package,
    )
    from trading_os.research_assets.sealing import seal_json

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    predecessor_path = coverage_root / "triage" / "test" / "selection.json"
    seal_json(
        predecessor_path,
        {
            "schema_version": 1,
            "cycle_id": "test",
            "ranking": [
                {
                    "ordinal": 1,
                    "symbol": "CN:600519",
                    "selected_for_quick_profile": True,
                }
            ],
            "portfolio_action": None,
        },
        artifact_type="rapid_triage_cross_company_selection",
        sealed_at=RECORDED_AT - dt.timedelta(minutes=2),
    )
    first_package = _package()
    first_package["profile"]["governance_status"] = "uncertain"
    first_package["profile"]["normalized_earnings_status"] = "uncertain"
    first_package["profile"]["valuation"]["base_expected_annual_return"] = 0.06
    first_package["profile"]["valuation"]["bull_expected_annual_return"] = 0.12
    first = record_profile_package(
        first_package,
        root=coverage_root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    assert first["next_stage"] == "targeted_followup"
    claim_profile_task(
        root=coverage_root,
        agent="/root/followup_600519",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=1),
        symbol="CN:600519",
    )
    resolved = _package()
    resolved["profile"]["information_cutoff"] = "2026-07-26T10:03:00+08:00"
    resolved["profile"]["valuation"]["base_expected_annual_return"] = 0.06
    resolved["profile"]["valuation"]["bull_expected_annual_return"] = 0.12
    resolved["provenance"]["agent"] = "/root/followup_600519"
    resolved["provenance"]["generated_at"] = "2026-07-26T10:04:00+08:00"
    second = record_profile_package(
        resolved,
        root=coverage_root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    assert second["next_stage"] == "price_watch"
    queue_before = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    screening_before = read_jsonl(coverage_root / "screening.jsonl")[0]

    comparison = build_profile_comparison_packet(
        root=coverage_root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        created_at=RECORDED_AT + dt.timedelta(minutes=6),
    )
    decisions = {
        "schema_version": 1,
        "cycle_id": "2026-07-26-test-cycle",
        "evaluated_stage": "quick_profile",
        "comparison_sha256": comparison["comparison_sha256"],
        "decisions": [
            {
                "symbol": "CN:600519",
                "decision": "defer",
                "reason": "补证已经收口，新增信息必须等待结构化触发器。",
                "decisive_question": "下一份正式披露能否改变现有现金收益判断？",
                "counterevidence_considered": ["现有业务仍具备生存能力。"],
            }
        ],
        "provenance": {
            "agent": "/root/profile-allocation",
            "model": "test-model",
            "tools": ["sealed comparison packet"],
            "generated_at": (RECORDED_AT + dt.timedelta(minutes=7)).isoformat(),
        },
    }
    finalized = finalize_profile_stage_with_agent_decisions(
        root=coverage_root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=8),
    )

    assert finalized["selected_symbols"] == []
    queue_after = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    screening_after = read_jsonl(coverage_root / "screening.jsonl")[0]
    assert queue_after["task_type"] == "targeted_followup"
    assert queue_after["status"] == "completed"
    assert queue_after["result_path"] == queue_before["result_path"]
    assert queue_after["next_action"] == queue_before["next_action"]
    assert queue_after["profile_quick_selection_path"] == finalized["selection_path"]
    assert screening_after["decision"] == screening_before["decision"]
    assert screening_after["reason"] == screening_before["reason"]
    assert screening_after["next_action"] == screening_before["next_action"]
    assert set(screening_before["evidence"]).issubset(screening_after["evidence"])
    assert f"stage_selection:{finalized['selection_path']}" in screening_after[
        "evidence"
    ]


def test_agent_defer_preserves_direct_terminal_profile_state(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        build_profile_comparison_packet,
        finalize_profile_stage_with_agent_decisions,
        record_profile_package,
    )
    from trading_os.research_assets.sealing import seal_json

    _coverage(tmp_path)
    coverage_root = tmp_path / "coverage" / "cn-a"
    seal_json(
        coverage_root / "triage" / "test" / "selection.json",
        {
            "schema_version": 1,
            "cycle_id": "test",
            "ranking": [
                {
                    "ordinal": 1,
                    "symbol": "CN:600519",
                    "selected_for_quick_profile": True,
                }
            ],
            "portfolio_action": None,
        },
        artifact_type="rapid_triage_cross_company_selection",
        sealed_at=RECORDED_AT - dt.timedelta(minutes=2),
    )
    package = _package()
    package["profile"]["valuation"]["base_expected_annual_return"] = 0.06
    package["profile"]["valuation"]["bull_expected_annual_return"] = 0.12
    recorded = record_profile_package(
        package,
        root=coverage_root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    assert recorded["next_stage"] == "price_watch"
    queue_before = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    screening_before = read_jsonl(coverage_root / "screening.jsonl")[0]
    comparison = build_profile_comparison_packet(
        root=coverage_root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        created_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    decisions = {
        "schema_version": 1,
        "cycle_id": "2026-07-26-test-cycle",
        "evaluated_stage": "quick_profile",
        "comparison_sha256": comparison["comparison_sha256"],
        "decisions": [
            {
                "symbol": "CN:600519",
                "decision": "defer",
                "reason": "当前价格不支持继续购买研究预算。",
                "decisive_question": "价格或现金收益何时形成足够安全边际？",
                "counterevidence_considered": ["正常化盈利仍为正。"],
            }
        ],
        "provenance": {
            "agent": "/root/profile-allocation",
            "model": "test-model",
            "tools": ["sealed comparison packet"],
            "generated_at": (RECORDED_AT + dt.timedelta(minutes=2)).isoformat(),
        },
    }
    finalized = finalize_profile_stage_with_agent_decisions(
        root=coverage_root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        decisions=decisions,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=3),
    )

    assert finalized["selected_symbols"] == []
    queue_after = read_jsonl(coverage_root / "research_queue.jsonl")[0]
    screening_after = read_jsonl(coverage_root / "screening.jsonl")[0]
    assert queue_after["task_type"] == "quick_profile"
    assert queue_after["status"] == "completed"
    assert queue_after["result_path"] == queue_before["result_path"]
    assert queue_after["next_action"] == queue_before["next_action"]
    assert queue_after["profile_quick_selection_path"] == finalized["selection_path"]
    assert screening_after["decision"] == screening_before["decision"]
    assert screening_after["reason"] == screening_before["reason"]
    assert screening_after["next_action"] == screening_before["next_action"]
    assert set(screening_before["evidence"]).issubset(screening_after["evidence"])


def test_credit_cycle_profile_requires_stage_specific_s1_evidence():
    from trading_os.research_assets.profile_workflow import (
        _validate_industry_evidence,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    package = {
        "profile": {"research_stage": "quick_profile"},
        "sources": [
            {
                "tier": "S1",
                "supports": ["bank_latest_s1_filing", "bank_capital_adequacy"],
            }
        ],
    }
    with pytest.raises(ResearchAllocationError, match="bank_asset_quality_migration"):
        _validate_industry_evidence(
            package,
            queue_record={"economic_risk_cluster": "credit_cycle"},
            policy=_policy(),
        )

    package["sources"][0]["supports"].append("bank_asset_quality_migration")
    _validate_industry_evidence(
        package,
        queue_record={"economic_risk_cluster": "credit_cycle"},
        policy=_policy(),
    )


def test_nonfinancial_profile_is_not_subject_to_bank_evidence_gate():
    from trading_os.research_assets.profile_workflow import (
        _validate_industry_evidence,
    )

    _validate_industry_evidence(
        {"profile": {"research_stage": "quick_profile"}, "sources": []},
        queue_record={"economic_risk_cluster": "consumer_demand"},
        policy=_policy(),
    )


def test_record_profile_replay_is_read_only_and_conflicts_fail(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import record_profile_package
    from trading_os.research_assets.research_allocation import ResearchAllocationError

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    package = _package()
    first = record_profile_package(
        package,
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    assert first["idempotent"] is False
    queue_before = read_jsonl(root / "research_queue.jsonl")
    screening_before = read_jsonl(root / "screening.jsonl")

    replayed = record_profile_package(
        package,
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    assert replayed == {**first, "idempotent": True}
    assert read_jsonl(root / "research_queue.jsonl") == queue_before
    assert read_jsonl(root / "screening.jsonl") == screening_before

    conflicting = copy.deepcopy(package)
    conflicting["analysis"]["business_summary"]["conclusion"] += "但内容被修改。"
    with pytest.raises(ResearchAllocationError, match="conflicts with the sealed package"):
        record_profile_package(
            conflicting,
            root=root,
            policy=_policy(),
            policy_reference="research-allocation.default@1.0.0",
            recorded_at=RECORDED_AT,
        )

    changed_policy = copy.deepcopy(_policy())
    changed_policy["minimum_base_expected_annual_return_for_deep_research"] = 0.105
    with pytest.raises(ResearchAllocationError, match="sealed evaluation"):
        record_profile_package(
            package,
            root=root,
            policy=changed_policy,
            policy_reference="research-allocation.default@changed",
            recorded_at=RECORDED_AT,
        )


def test_record_profile_replay_after_promotion_preserves_running_queue(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        finalize_profile_stage,
        record_profile_package,
    )

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    package = _package()
    first = record_profile_package(
        package,
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    finalize_profile_stage(
        root=root,
        cycle_id=package["cycle_id"],
        stage="quick_profile",
        policy=_policy(),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    claim_profile_task(
        root=root,
        agent="/root/scoped-agent",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
        symbol="CN:600519",
    )
    queue_before = read_jsonl(root / "research_queue.jsonl")
    screening_before = read_jsonl(root / "screening.jsonl")
    assert queue_before[0]["task_type"] == "scoped_research"
    assert queue_before[0]["status"] == "running"

    replayed = record_profile_package(
        package,
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    assert replayed == {**first, "idempotent": True}
    assert read_jsonl(root / "research_queue.jsonl") == queue_before
    assert read_jsonl(root / "screening.jsonl") == screening_before


@pytest.mark.parametrize("failed_write", [1, 2])
def test_finalize_profile_repairs_zero_or_half_written_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_write: int
):
    import trading_os.research_assets.profile_workflow as workflow
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.sealing import verify_sealed

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    record_profile_package = workflow.record_profile_package
    record_profile_package(
        _package(),
        root=root,
        policy=_policy(),
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    original_write = workflow.write_jsonl
    write_count = 0

    def fail_selected_write(path, records, sort_key="symbol"):
        nonlocal write_count
        write_count += 1
        if write_count == failed_write:
            raise RuntimeError("simulated profile materialization crash")
        return original_write(path, records, sort_key)

    monkeypatch.setattr(workflow, "write_jsonl", fail_selected_write)
    with pytest.raises(RuntimeError, match="simulated profile materialization crash"):
        workflow.finalize_profile_stage(
            root=root,
            cycle_id="2026-07-26-test-cycle",
            stage="quick_profile",
            policy=_policy(),
            finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
        )
    selection_path = (
        root / "profiles" / "2026-07-26-test-cycle" / "quick-profile-selection.json"
    )
    assert verify_sealed(selection_path).artifact_type == (
        "quick_profile_cross_company_selection"
    )

    monkeypatch.setattr(workflow, "write_jsonl", original_write)
    recovered = workflow.finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=_policy(),
        finalized_at=RECORDED_AT + dt.timedelta(minutes=2),
    )
    assert recovered["idempotent"] is True
    queue = read_jsonl(root / "research_queue.jsonl")[0]
    screening = read_jsonl(root / "screening.jsonl")[0]
    assert queue["task_type"] == "scoped_research"
    assert queue["status"] == "pending"
    assert queue["profile_quick_selection_path"] == recovered["selection_path"]
    assert queue["effort_budget_hours"] == 4.0
    assert screening["decision"] == "scoped_research"
    assert f"stage_selection:{recovered['selection_path']}" in screening["evidence"]


def test_finalize_profile_replay_never_regresses_later_progress(tmp_path: Path):
    from trading_os.research_assets.coverage_store import read_jsonl
    from trading_os.research_assets.profile_workflow import (
        claim_profile_task,
        finalize_profile_stage,
        record_profile_package,
    )

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    policy = _policy()
    record_profile_package(
        _package(),
        root=root,
        policy=policy,
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT,
    )
    finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    claim_profile_task(
        root=root,
        agent="/root/scoped-agent",
        claimed_at=RECORDED_AT + dt.timedelta(minutes=2),
        symbol="CN:600519",
    )
    running_queue = read_jsonl(root / "research_queue.jsonl")
    running_screening = read_jsonl(root / "screening.jsonl")
    finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=3),
    )
    assert read_jsonl(root / "research_queue.jsonl") == running_queue
    assert read_jsonl(root / "screening.jsonl") == running_screening

    scoped_package = _package()
    scoped_package["profile"]["research_stage"] = "scoped_research"
    scoped_package["provenance"]["agent"] = "/root/scoped-agent"
    scoped_package["provenance"]["generated_at"] = (
        RECORDED_AT + dt.timedelta(minutes=4)
    ).isoformat()
    record_profile_package(
        scoped_package,
        root=root,
        policy=policy,
        policy_reference="research-allocation.default@1.0.0",
        recorded_at=RECORDED_AT + dt.timedelta(minutes=5),
    )
    completed_queue = read_jsonl(root / "research_queue.jsonl")
    completed_screening = read_jsonl(root / "screening.jsonl")
    finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=6),
    )
    assert read_jsonl(root / "research_queue.jsonl") == completed_queue
    assert read_jsonl(root / "screening.jsonl") == completed_screening

    finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="scoped_research",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=7),
    )
    deeper_queue = read_jsonl(root / "research_queue.jsonl")
    deeper_screening = read_jsonl(root / "screening.jsonl")
    assert deeper_queue[0]["task_type"] == "deep_research"
    finalize_profile_stage(
        root=root,
        cycle_id="2026-07-26-test-cycle",
        stage="quick_profile",
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=8),
    )
    assert read_jsonl(root / "research_queue.jsonl") == deeper_queue
    assert read_jsonl(root / "screening.jsonl") == deeper_screening


@pytest.mark.parametrize(
    ("stage", "candidate_decision", "next_stage", "binding_field", "binding_path"),
    [
        (
            "quick_profile",
            "profile_candidate",
            "scoped_research",
            "triage_selection_path",
            "coverage/cn-a/triage/risk-cap/selection.json",
        ),
        (
            "scoped_research",
            "deep_candidate",
            "deep_research",
            "profile_quick_selection_path",
            "coverage/cn-a/profiles/risk-cap/quick-profile-selection.json",
        ),
    ],
)
def test_profile_selection_caps_missing_risk_cluster_as_unclassified(
    tmp_path: Path,
    stage: str,
    candidate_decision: str,
    next_stage: str,
    binding_field: str,
    binding_path: str,
):
    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.profile_workflow import finalize_profile_stage
    from trading_os.research_assets.sealing import seal_json

    _coverage(tmp_path)
    root = tmp_path / "coverage" / "cn-a"
    symbols = [("CN:600519", "贵州茅台"), ("CN:000001", "平安银行")]
    queue = []
    screening = []
    for rank, (symbol, name) in enumerate(symbols, 1):
        queue.append(
            {
                "symbol": symbol,
                "name": name,
                "task_type": stage,
                "priority": rank,
                "status": "completed",
                "reason": "等待同层比较",
                "target_company_dir": f"research/companies/CN/{symbol[-6:]}",
                "effort_budget_hours": 1.0 if stage == "quick_profile" else 4.0,
                "preceding_stage": "rapid_triage" if stage == "quick_profile" else "quick_profile",
                "stop_conditions": ["投资路径不成立"],
                "profile_cycle_id": "risk-cap-cycle",
                "profile_priority_score": 300 - rank,
                binding_field: binding_path,
                "stage_history": [{"stage": stage, "status": "completed"}],
            }
        )
        screening.append(
            {
                "symbol": symbol,
                "name": name,
                "decision": candidate_decision,
                "priority": rank,
                "reason": "等待同层比较",
                "evidence": ["profile:test"],
                "next_action": "等待比较",
            }
        )
    write_jsonl(root / "research_queue.jsonl", queue)
    write_jsonl(root / "screening.jsonl", screening)
    predecessor_path = tmp_path / binding_path
    if stage == "quick_profile":
        predecessor_payload = {
            "schema_version": 1,
            "cycle_id": "risk-cap-cycle",
            "ranking": [
                {"symbol": symbol, "selected_for_quick_profile": True}
                for symbol, _ in symbols
            ],
        }
        artifact_type = "rapid_triage_cross_company_selection"
    else:
        predecessor_payload = {
            "schema_version": 1,
            "cycle_id": "risk-cap-cycle",
            "ranking": [
                {"symbol": symbol, "selected": True} for symbol, _ in symbols
            ],
        }
        artifact_type = "quick_profile_cross_company_selection"
    seal_json(
        predecessor_path,
        predecessor_payload,
        artifact_type=artifact_type,
        sealed_at=RECORDED_AT,
    )
    policy = copy.deepcopy(_policy())
    policy["stage_capacity_per_cycle"][next_stage] = 2
    policy["risk_cluster_caps"][next_stage] = 1

    result = finalize_profile_stage(
        root=root,
        cycle_id="risk-cap-cycle",
        stage=stage,
        policy=policy,
        finalized_at=RECORDED_AT + dt.timedelta(minutes=1),
    )
    assert result["selected_count"] == 1
    assert result["selected_symbols"] == ["CN:600519"]
    stored = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    assert stored["CN:600519"]["task_type"] == next_stage
    assert stored["CN:000001"]["task_type"] == stage


def test_diversified_risk_cluster_is_also_capped():
    from trading_os.research_assets.profile_workflow import (
        _select_with_risk_cluster_cap,
    )

    ranked = [
        {"symbol": "CN:000001", "economic_risk_cluster": "diversified"},
        {"symbol": "CN:000002", "economic_risk_cluster": "diversified"},
    ]
    selected, capped = _select_with_risk_cluster_cap(ranked, capacity=2, cap=1)
    assert [item["symbol"] for item in selected] == ["CN:000001"]
    assert capped == {"CN:000002"}
