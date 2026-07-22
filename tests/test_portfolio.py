from __future__ import annotations

import copy

import pytest

POLICY = {
    "max_single_name_weight": 0.05,
    "max_industry_weight": 0.20,
    "max_economic_risk_cluster_weight": 0.25,
    "max_top_five_weight": 0.25,
    "max_medium_confidence_weight": 0.03,
    "max_low_confidence_weight": 0.0,
    "initial_entry_fraction": 1 / 3,
    "minimum_expected_annual_return": 0.12,
    "allow_cash": True,
}


def _candidate(
    symbol: str = "CN:000021",
    *,
    rank_score: float = 90.0,
    industry: str = "半导体",
    clusters: list[str] | None = None,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": symbol,
        "underwriting_status": "passed",
        "evidence_stale": False,
        "portfolio_eligible": True,
        "current_price": 75.0,
        "bear_value": 60.0,
        "fair_value_range": [95.0, 105.0],
        "buy_zone": [70.0, 80.0],
        "reduce_zone": [120.0, 130.0],
        "confidence": "high",
        "industry": industry,
        "economic_risk_clusters": clusters or ["memory_price_cycle"],
        "expected_annual_return": 0.18,
        "bear_case_loss_fraction": 0.20,
        "allowed_loss_weight": 0.01,
        "rank_score": rank_score,
        "held": False,
        "reason_codes": ["underwriting_passed"],
    }


def _build(candidates: list[dict[str, object]]):
    from trading_os.research_assets.portfolio import build_model_portfolio

    return build_model_portfolio(candidates, policy=POLICY)


def test_buy_now_requires_all_five_gates():
    result = _build([_candidate()])

    position = result.decisions[0]
    assert position.action == "buy_now"
    assert position.target_weight == pytest.approx(0.05)
    assert position.initial_entry_weight == pytest.approx(0.05 / 3)


@pytest.mark.parametrize(
    ("field", "value", "expected_action"),
    [
        ("underwriting_status", "failed", "reject"),
        ("evidence_stale", True, "watch"),
        ("current_price", 90.0, "buy_on_weakness"),
        ("portfolio_eligible", False, "watch"),
    ],
)
def test_missing_any_buy_gate_prevents_buy_now(
    field: str, value: object, expected_action: str
):
    candidate = _candidate()
    candidate[field] = value

    result = _build([candidate])

    assert result.decisions[0].action == expected_action
    assert result.decisions[0].target_weight == 0


def test_expected_return_below_policy_minimum_prevents_buy_now():
    candidate = _candidate()
    candidate["expected_annual_return"] = 0.119

    decision = _build([candidate]).decisions[0]

    assert decision.action == "watch"
    assert decision.target_weight == 0
    assert "expected_return_below_minimum" in decision.reason_codes


@pytest.mark.parametrize(
    ("status", "action"),
    [
        ("failed", "reject"),
        ("insufficient_evidence", "watch"),
        ("needs_challenger", "watch"),
        ("stale", "watch"),
    ],
)
def test_nonpassed_underwriting_has_deterministic_action(status: str, action: str):
    candidate = _candidate()
    candidate["underwriting_status"] = status

    assert _build([candidate]).decisions[0].action == action


def test_medium_confidence_is_capped_at_three_percent():
    candidate = _candidate()
    candidate["confidence"] = "medium"

    decision = _build([candidate]).decisions[0]

    assert decision.target_weight == pytest.approx(0.03)


def test_low_confidence_cannot_receive_weight():
    candidate = _candidate()
    candidate["confidence"] = "low"

    decision = _build([candidate]).decisions[0]

    assert decision.action == "watch"
    assert decision.target_weight == 0
    assert "low_confidence_zero_weight" in decision.reason_codes


def test_risk_budget_can_reduce_single_name_weight():
    candidate = _candidate()
    candidate["allowed_loss_weight"] = 0.004
    candidate["bear_case_loss_fraction"] = 0.20

    decision = _build([candidate]).decisions[0]

    assert decision.target_weight == pytest.approx(0.02)


def test_industry_limit_is_enforced_across_ranked_candidates():
    candidates = [
        _candidate(f"CN:{index:06d}", rank_score=100 - index, clusters=[f"cluster-{index}"])
        for index in range(1, 7)
    ]

    result = _build(candidates)

    assert sum(item.target_weight for item in result.decisions) == pytest.approx(0.20)
    assert sum(item.action == "buy_now" for item in result.decisions) == 4
    assert any("industry_limit_exhausted" in item.reason_codes for item in result.decisions)


def test_economic_risk_cluster_limit_crosses_industry_boundaries():
    candidates = [
        _candidate(
            f"CN:{index:06d}",
            rank_score=100 - index,
            industry=f"行业-{index}",
            clusters=["memory_price_cycle"],
        )
        for index in range(1, 8)
    ]

    result = _build(candidates)

    assert sum(item.target_weight for item in result.decisions) == pytest.approx(0.25)
    assert sum(item.action == "buy_now" for item in result.decisions) == 5
    assert any("risk_cluster_limit_exhausted" in item.reason_codes for item in result.decisions)


def test_cash_is_retained_instead_of_forcing_full_investment():
    result = _build([_candidate()])

    assert result.invested_weight == pytest.approx(0.05)
    assert result.cash_weight == pytest.approx(0.95)


def test_top_five_limit_is_enforced_independently_of_single_name_limit():
    from trading_os.research_assets.portfolio import build_model_portfolio

    policy = {**POLICY, "max_single_name_weight": 0.10}
    candidates = [
        _candidate(
            f"CN:{index:06d}",
            rank_score=100 - index,
            industry=f"industry-{index}",
            clusters=[f"cluster-{index}"],
        )
        for index in range(1, 8)
    ]
    for candidate in candidates:
        candidate["allowed_loss_weight"] = 0.02

    result = build_model_portfolio(candidates, policy=policy)
    ranked = sorted(
        (item.target_weight for item in result.decisions),
        reverse=True,
    )

    assert sum(ranked[:5]) == pytest.approx(0.25)
    assert any("top_five_limit_exhausted" in item.reason_codes for item in result.decisions)


def test_every_nonbuy_decision_has_structured_exclusion_reasons():
    expensive = _candidate("CN:000100")
    expensive["current_price"] = 90.0
    failed = _candidate("CN:000101")
    failed["underwriting_status"] = "failed"

    result = _build([expensive, failed])

    assert {item.symbol for item in result.exclusions} == {"CN:000100", "CN:000101"}
    assert all(item.reason_codes for item in result.exclusions)


@pytest.mark.parametrize(
    ("mutation", "action"),
    [
        ({}, "hold"),
        ({"current_price": 125.0}, "reduce"),
        ({"underwriting_status": "failed"}, "exit"),
    ],
)
def test_existing_holding_uses_hold_reduce_exit_actions(
    mutation: dict[str, object], action: str
):
    candidate = _candidate()
    candidate["held"] = True
    candidate.update(mutation)

    decision = _build([candidate]).decisions[0]

    assert decision.action == action


def test_input_order_does_not_change_ranked_allocation():
    candidates = [
        _candidate("CN:000001", rank_score=80, clusters=["a"]),
        _candidate("CN:000002", rank_score=90, clusters=["b"]),
    ]

    left = _build(candidates)
    right = _build(list(reversed(copy.deepcopy(candidates))))

    assert left == right
