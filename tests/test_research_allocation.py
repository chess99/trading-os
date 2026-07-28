from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _policy() -> dict[str, object]:
    return json.loads(
        (ROOT / "policies" / "research-allocation.json").read_text(encoding="utf-8")
    )["payload"]


def _small_policy() -> dict[str, object]:
    policy = copy.deepcopy(_policy())
    policy["candidate_pool_capacity_per_cycle"] = 4
    policy["quick_profile_capacity_per_cycle"] = 2
    policy["selection_slots"] = {
        "balanced": 1,
        "value_income": 1,
        "quality_compounder": 0,
        "magic_formula_nonfinancial": 0,
        "financial_specialist": 0,
        "cyclical_specialist": 0,
        "crisis_mispricing": 1,
        "information_change": 0,
        "false_negative_audit": 1,
    }
    return policy


def _ranking_item(
    index: int,
    *,
    total: float = 50.0,
    cluster: str = "consumer_demand",
    reasons: list[str] | None = None,
    value: float = 10.0,
) -> dict[str, object]:
    return {
        "symbol": f"CN:{index:06d}",
        "name": f"公司{index}",
        "total_score": total,
        "score_confidence": "low",
        "economic_risk_cluster": cluster,
        "dimensions": {
            "value_dislocation": value,
            "operating_capital_quality": 10.0,
            "permanent_loss_protection": 10.0,
            "information_update_urgency": 5.0,
            "verifiable_catalyst_odds": 5.0,
            "evidence_availability": 5.0,
        },
        "penalties": [],
        "reason_codes": reasons or ["public_prefilter_evidence_available"],
        "public_snapshot": {"dividend_yield_pct": 2.0},
    }


def _ranking() -> dict[str, object]:
    return {
        "generated_at": "2026-07-25T10:00:00+08:00",
        "items": [
            _ranking_item(1, total=90),
            _ranking_item(2, value=25),
            _ranking_item(
                3,
                total=20,
                reasons=["negative_pe_requires_normalization"],
            ),
            _ranking_item(4, cluster="credit_cycle"),
            _ranking_item(5, cluster="commodity_cycle"),
            _ranking_item(6, total=10),
        ],
        "excluded": [{"symbol": "CN:000007", "reason_code": "not_common_stock"}],
    }


def _profile(**changes) -> dict[str, object]:
    value: dict[str, object] = {
        "research_stage": "quick_profile",
        "symbol": "CN:600519",
        "as_of": "2026-07-25",
        "information_cutoff": "2026-07-25T10:00:00+08:00",
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
        "variant_perception": "市场低估了正常化现金流的持续性",
        "decisive_unknowns": ["下一份财报的自由现金流能否确认"],
        "counterevidence": ["行业需求可能恶化", "竞争可能压低利润率"],
        "structural_stop_reasons": [],
        "revisit_triggers": [
            {
                "type": "price",
                "condition": "预期年化回报达到12%",
                "reason": "重新评估是否值得承保",
            }
        ],
    }
    value.update(changes)
    return value


def test_multi_lens_allocation_is_capacity_bounded_and_never_promotes_to_deep():
    from trading_os.research_assets.research_allocation import (
        allocate_research_capacity,
    )

    result = allocate_research_capacity(
        _ranking(),
        policy=_small_policy(),
        policy_version="research-allocation.default@1.0.0",
    )

    assert result["selected_count"] == 4
    assert result["deferred_count"] == 2
    assert len(result["ranking_content_sha256"]) == 64
    assert len(result["policy_payload_sha256"]) == 64
    assert all(item["stage"] == "rapid_triage" for item in result["selected"])
    assert all("deep_research" not in item["stage"] for item in result["selected"])
    assert result["lens_counts"]["crisis_mispricing"] == 1
    assert any(item["symbol"] == "CN:000003" for item in result["selected"])
    assert result["excluded"] == [
        {"symbol": "CN:000007", "reason_code": "not_common_stock"}
    ]


def test_low_confidence_ranking_emits_warning_instead_of_false_precision():
    from trading_os.research_assets.research_allocation import (
        allocate_research_capacity,
    )

    result = allocate_research_capacity(
        _ranking(),
        policy=_small_policy(),
        policy_version="research-allocation.default@1.0.0",
    )

    assert result["confidence_counts"] == {"low": 6}
    assert result["warnings"] == [
        "ranking_confidence_too_low_for_score_led_promotion"
    ]


def test_value_income_excludes_credit_cycle_and_preserves_multi_lens_matches():
    from trading_os.research_assets.research_allocation import allocate_research_capacity

    policy = _small_policy()
    policy["candidate_pool_capacity_per_cycle"] = 2
    policy["quick_profile_capacity_per_cycle"] = 2
    policy["selection_slots"] = {
        lens: 0 for lens in policy["selection_slots"]
    }
    policy["selection_slots"].update({"balanced": 1, "value_income": 1})
    ranking = {
        "generated_at": "2026-07-28T10:00:00+08:00",
        "items": [
            _ranking_item(1, total=99, cluster="credit_cycle", value=99),
            _ranking_item(2, total=90, cluster="consumer_demand", value=50),
            _ranking_item(3, total=80, cluster="consumer_demand", value=40),
        ],
        "excluded": [],
    }

    result = allocate_research_capacity(
        ranking, policy=policy, policy_version="test@3.0.0"
    )
    selected = {item["symbol"]: item for item in result["selected"]}
    assert selected["CN:000001"]["selected_by"] == ["balanced"]
    assert "value_income" not in selected["CN:000001"]["matched_lenses"]
    assert selected["CN:000002"]["selected_by"] == ["value_income"]


def test_rapid_triage_allocation_respects_risk_cluster_cap_without_quota_fill():
    from trading_os.research_assets.research_allocation import allocate_research_capacity

    policy = _small_policy()
    policy["candidate_pool_capacity_per_cycle"] = 4
    policy["quick_profile_capacity_per_cycle"] = 4
    policy["risk_cluster_caps"]["rapid_triage"] = 2
    policy["selection_slots"] = {
        lens: 0 for lens in policy["selection_slots"]
    }
    policy["selection_slots"]["balanced"] = 4
    ranking = {
        "generated_at": "2026-07-28T10:00:00+08:00",
        "items": [
            _ranking_item(index, total=100 - index, cluster="credit_cycle")
            for index in range(1, 5)
        ]
        + [
            _ranking_item(5, total=50, cluster="consumer_demand"),
            _ranking_item(6, total=40, cluster="commodity_cycle"),
        ],
        "excluded": [],
    }

    result = allocate_research_capacity(
        ranking, policy=policy, policy_version="test@3.0.0"
    )
    assert result["selected_count"] == 4
    assert result["risk_cluster_counts"]["credit_cycle"] == 2
    assert {item["symbol"] for item in result["selected"]} == {
        "CN:000001",
        "CN:000002",
        "CN:000005",
        "CN:000006",
    }


def test_quick_profile_can_only_advance_to_scoped_research():
    from trading_os.research_assets.research_allocation import evaluate_quick_profile

    result = evaluate_quick_profile(_profile(), policy=_policy())

    assert result["next_stage"] == "scoped_research"
    assert result["maximum_additional_effort_hours"] == 4.0
    assert result["portfolio_action"] is None


def test_scoped_research_can_advance_to_full_deep_research():
    from trading_os.research_assets.research_allocation import evaluate_quick_profile

    profile = _profile(research_stage="scoped_research")

    result = evaluate_quick_profile(profile, policy=_policy())

    assert result["next_stage"] == "deep_research"
    assert result["maximum_additional_effort_hours"] == 24.0


def test_high_return_cannot_cure_scoped_research_evidence_gap():
    from trading_os.research_assets.research_allocation import evaluate_quick_profile

    profile = _profile(
        research_stage="scoped_research",
        s1_source_count=1,
    )
    profile["valuation"]["base_expected_annual_return"] = 0.30

    result = evaluate_quick_profile(profile, policy=_policy())

    assert result["next_stage"] == "targeted_followup"
    assert "scoped_research_not_ready_for_deep_research" in result["reason_codes"]


def test_primary_evidence_can_support_auditable_conditional_stop():
    from trading_os.research_assets.research_allocation import evaluate_quick_profile

    profile = _profile(
        structural_stop_reasons=[
            "financial_statements_unreliable_without_alternative_verification"
        ]
    )

    result = evaluate_quick_profile(profile, policy=_policy())

    assert result["next_stage"] == "conditional_stop"
    assert result["maximum_additional_effort_hours"] == 0


def test_structural_stop_without_primary_evidence_only_gets_targeted_followup():
    from trading_os.research_assets.research_allocation import evaluate_quick_profile

    profile = _profile(
        s1_source_count=0,
        structural_stop_reasons=[
            "financial_statements_unreliable_without_alternative_verification"
        ],
    )

    result = evaluate_quick_profile(profile, policy=_policy())

    assert result["next_stage"] == "targeted_followup"
    assert "structural_stop_requires_primary_evidence" in result["reason_codes"]


def test_price_watch_requires_an_explicit_reactivation_trigger():
    from trading_os.research_assets.research_allocation import (
        ResearchAllocationError,
        evaluate_quick_profile,
    )

    profile = _profile(revisit_triggers=[])
    profile["valuation"]["base_expected_annual_return"] = 0.08
    profile["valuation"]["bull_expected_annual_return"] = 0.09

    with pytest.raises(ResearchAllocationError, match="revisit trigger"):
        evaluate_quick_profile(profile, policy=_policy())


def test_outside_circle_is_reassigned_not_declared_a_bad_company():
    from trading_os.research_assets.research_allocation import evaluate_quick_profile

    result = evaluate_quick_profile(
        _profile(circle_of_competence="outside"),
        policy=_policy(),
    )

    assert result["next_stage"] == "reassign_or_stop"
    assert result["portfolio_action"] is None


def test_selection_slots_must_equal_cycle_capacity():
    from trading_os.research_assets.research_allocation import (
        ResearchAllocationError,
        allocate_research_capacity,
    )

    policy = _small_policy()
    policy["candidate_pool_capacity_per_cycle"] = 5

    with pytest.raises(ResearchAllocationError, match="must sum"):
        allocate_research_capacity(
            _ranking(),
            policy=policy,
            policy_version="research-allocation.default@1.0.0",
        )


def test_apply_allocation_replaces_legacy_deep_queue_with_bounded_funnel(
    tmp_path: Path,
):
    import datetime as dt

    from trading_os.research_assets.coverage_store import (
        coverage_status,
        read_jsonl,
        validate_coverage_root,
        write_jsonl,
    )
    from trading_os.research_assets.research_allocation import (
        allocate_research_capacity,
        apply_research_allocation,
    )

    ranking = _ranking()
    ranking["excluded"] = []
    allocation = allocate_research_capacity(
        ranking,
        policy=_small_policy(),
        policy_version="research-allocation.default@1.0.0",
    )
    root = tmp_path / "coverage" / "cn-a"
    companies = []
    screening = []
    queue = []
    for item in ranking["items"]:
        symbol = item["symbol"]
        ticker = symbol.split(":", 1)[1]
        companies.append({"symbol": symbol, "name": item["name"]})
        screening.append(
            {
                "symbol": symbol,
                "name": item["name"],
                "decision": "deep_research",
                "priority": 1,
                "reason": "legacy blanket promotion",
                "evidence": ["legacy"],
                "next_action": "legacy",
            }
        )
        queue.append(
            {
                "symbol": symbol,
                "name": item["name"],
                "task_type": "initial_research",
                "priority": 1,
                "status": "requires_rebaseline",
                "reason": "legacy blanket promotion",
                "target_company_dir": f"research/companies/CN/{ticker}",
            }
        )
    write_jsonl(root / "companies.jsonl", companies)
    write_jsonl(root / "screening.jsonl", screening)
    write_jsonl(root / "research_queue.jsonl", queue)
    write_jsonl(root / "runs.jsonl", [], sort_key="run_id")

    result = apply_research_allocation(
        allocation,
        ranking=ranking,
        root=root,
        applied_at=dt.datetime.fromisoformat("2026-07-26T20:30:00+08:00"),
    )

    assert result["selected_rapid_triage_count"] == 4
    assert result["deferred_catalog_count"] == 2
    status = coverage_status(root)
    assert status["screening"]["by_decision"] == {
        "catalog": 2,
        "rapid_triage": 4,
    }
    assert status["research_queue"]["by_status"] == {
        "pending": 4,
        "requires_rebaseline": 2,
    }
    queue_records = read_jsonl(root / "research_queue.jsonl")
    assert all(item["task_type"] == "rapid_triage" for item in queue_records)
    assert all(item["effort_budget_hours"] == 0.25 for item in queue_records)
    validate_coverage_root(root)


def test_apply_allocation_preserves_completed_formal_profile_progress(
    tmp_path: Path,
):
    import datetime as dt

    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.research_allocation import (
        allocate_research_capacity,
        apply_research_allocation,
    )

    ranking = _ranking()
    ranking["excluded"] = []
    allocation = allocate_research_capacity(
        ranking,
        policy=_small_policy(),
        policy_version="research-allocation.default@2.0.0",
    )
    root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        root / "companies.jsonl",
        [
            {"symbol": item["symbol"], "name": item["name"]}
            for item in ranking["items"]
        ],
    )
    write_jsonl(
        root / "screening.jsonl",
        [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "decision": "catalog",
                "priority": 3,
                "reason": "测试",
                "evidence": ["test"],
                "next_action": "测试",
            }
            for item in ranking["items"]
        ],
    )
    queue = []
    for item in ranking["items"]:
        record = {
            "symbol": item["symbol"],
            "name": item["name"],
            "task_type": "rapid_triage",
            "priority": 3,
            "status": "requires_rebaseline",
            "reason": "测试",
            "target_company_dir": f"research/companies/CN/{item['symbol'][-6:]}",
            "effort_budget_hours": 0.25,
            "preceding_stage": "machine_triage",
            "stop_conditions": ["测试停止"],
        }
        queue.append(record)
    preserved_symbol = ranking["items"][0]["symbol"]
    queue[0].update(
        {
            "task_type": "scoped_research",
            "status": "pending",
            "effort_budget_hours": 4.0,
            "preceding_stage": "quick_profile",
            "reason": "已有正式画像进度",
        }
    )
    write_jsonl(root / "research_queue.jsonl", queue)
    write_jsonl(root / "runs.jsonl", [], sort_key="run_id")

    result = apply_research_allocation(
        allocation,
        ranking=ranking,
        root=root,
        applied_at=dt.datetime.fromisoformat("2026-07-27T10:00:00+08:00"),
    )

    assert result["preserved_formal_research_count"] == 1
    stored = {
        item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")
    }
    assert stored[preserved_symbol]["task_type"] == "scoped_research"
    assert stored[preserved_symbol]["status"] == "pending"


def test_explicit_retriage_mode_reopens_completed_work_and_preserves_history(
    tmp_path: Path,
):
    import datetime as dt

    from trading_os.research_assets.coverage_store import read_jsonl, write_jsonl
    from trading_os.research_assets.research_allocation import (
        allocate_research_capacity,
        apply_research_allocation,
    )

    ranking = _ranking()
    ranking["excluded"] = []
    ranking["retriage_completed"] = True
    allocation = allocate_research_capacity(
        ranking,
        policy=_small_policy(),
        policy_version="research-allocation.default@3.0.0",
    )
    root = tmp_path / "coverage" / "cn-a"
    write_jsonl(
        root / "companies.jsonl",
        [
            {"symbol": item["symbol"], "name": item["name"]}
            for item in ranking["items"]
        ],
    )
    write_jsonl(
        root / "screening.jsonl",
        [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "decision": "price_watch",
                "priority": 3,
                "reason": "旧结论",
                "evidence": ["legacy"],
                "next_action": "等待",
            }
            for item in ranking["items"]
        ],
    )
    queue = []
    for item in ranking["items"]:
        queue.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "task_type": "quick_profile",
                "priority": 3,
                "status": "completed",
                "reason": "旧画像",
                "target_company_dir": f"research/companies/CN/{item['symbol'][-6:]}",
                "assigned_agent": "legacy-agent",
                "finished_at": "2026-07-27T12:00:00+08:00",
                "result_path": f"legacy/{item['symbol'][-6:]}.json",
                "triage_cycle_id": "legacy-cycle",
                "triage_disposition": "price_watch",
                "triage_selection_path": "legacy/selection.json",
                "profile_cycle_id": "legacy-profile-cycle",
            }
        )
    write_jsonl(root / "research_queue.jsonl", queue)
    write_jsonl(root / "runs.jsonl", [], sort_key="run_id")

    result = apply_research_allocation(
        allocation,
        ranking=ranking,
        root=root,
        applied_at=dt.datetime.fromisoformat("2026-07-28T19:00:00+08:00"),
    )

    assert result["preserved_formal_research_count"] == 0
    stored = {item["symbol"]: item for item in read_jsonl(root / "research_queue.jsonl")}
    selected = allocation["selected"][0]["symbol"]
    assert stored[selected]["task_type"] == "rapid_triage"
    assert stored[selected]["status"] == "pending"
    assert stored[selected]["stage_history"][-1]["result_path"].startswith("legacy/")
    assert stored[selected]["triage_cycle_id"] is None
    assert stored[selected]["triage_disposition"] is None
    assert stored[selected]["triage_selection_path"] is None
    assert stored[selected]["profile_cycle_id"] is None
