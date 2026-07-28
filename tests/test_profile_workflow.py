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
