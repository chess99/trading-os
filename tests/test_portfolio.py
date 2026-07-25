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
    "max_per_name_loss_weight": 0.01,
    "initial_entry_fraction": 1 / 3,
    "minimum_expected_annual_return": 0.12,
    "near_miss_expected_annual_return": 0.10,
    "allow_cash": True,
}
AS_OF = "2026-07-25T15:00:00+08:00"


def _return_model(
    *,
    terminal_value: float = 112.0,
    distributions: list[float] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "method": "annual_cashflow_irr_v1",
        "currency": "CNY",
        "model_as_of": AS_OF,
        "base_case_distributions_per_share": distributions or [0.0],
        "base_case_terminal_value_per_share": terminal_value,
    }


def _candidate(
    symbol: str = "CN:000021",
    *,
    industry: str = "半导体",
    clusters: list[str] | None = None,
    terminal_value: float = 112.0,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": symbol,
        "underwriting_status": "passed",
        "evidence_stale": False,
        "independent_challenger_completed": True,
        "source_machine_decision_sha256": "1" * 64,
        "policy_snapshot_sha256": "2" * 64,
        "current_price": 75.0,
        "price_as_of": AS_OF,
        "bear_value": 60.0,
        "fair_value_range": [95.0, 105.0],
        "buy_zone": [70.0, 80.0],
        "reduce_zone": [120.0, 130.0],
        "confidence": "high",
        "industry": industry,
        "economic_risk_clusters": clusters or ["memory_price_cycle"],
        "return_model": _return_model(terminal_value=terminal_value),
        "bear_case_loss_fraction": 0.20,
        "allowed_loss_weight": 0.01,
        "held": False,
        "reason_codes": ["underwriting_passed"],
    }


def _build(candidates: list[dict[str, object]]):
    from trading_os.research_assets.portfolio import build_model_portfolio

    return build_model_portfolio(candidates, policy=POLICY)


def test_buy_now_requires_machine_underwriting_return_and_challenger_gates():
    position = _build([_candidate()]).decisions[0]

    assert position.action == "buy_now"
    assert position.target_weight == pytest.approx(0.05)
    assert position.initial_entry_weight == pytest.approx(0.05 / 3)


@pytest.mark.parametrize(
    ("field", "value", "expected_action"),
    [
        ("underwriting_status", "failed", "reject"),
        ("evidence_stale", True, "watch"),
        ("current_price", 90.0, "buy_on_weakness"),
    ],
)
def test_missing_any_company_gate_prevents_buy_now(
    field: str, value: object, expected_action: str
):
    candidate = _candidate()
    candidate[field] = value

    decision = _build([candidate]).decisions[0]

    assert decision.action == expected_action
    assert decision.target_weight == 0


def test_return_metrics_are_recomputed_from_price_and_cash_flows():
    candidate = _candidate()
    candidate["current_price"] = 75.0
    candidate["buy_zone"] = [70.0, 100.0]
    candidate["return_model"] = _return_model(
        terminal_value=100.0,
        distributions=[2.0, 2.0, 2.0],
    )

    decision = _build([candidate]).decisions[0]

    assert decision.expected_annual_return == pytest.approx(0.12497894283079625)
    assert decision.minimum_expected_annual_return == pytest.approx(0.12)
    assert decision.expected_return_gap == pytest.approx(0.00497894283079625)
    assert decision.minimum_return_activation_price == pytest.approx(
        75.98168731778424
    )
    assert decision.buy_now_price_ceiling == pytest.approx(75.98168731778424)


def test_latest_price_can_cross_return_hurdle_without_changing_model():
    candidate = _candidate()
    candidate["buy_zone"] = [70.0, 110.0]
    candidate["current_price"] = 100.5

    before = _build([candidate]).decisions[0]
    candidate["current_price"] = 99.5
    after = _build([candidate]).decisions[0]

    assert before.action == "watch"
    assert "expected_return_near_miss" in before.reason_codes
    assert after.action == "buy_now"
    assert before.minimum_return_activation_price == pytest.approx(100.0)
    assert after.minimum_return_activation_price == pytest.approx(100.0)


def test_expected_return_below_near_miss_is_plain_watch():
    candidate = _candidate()
    candidate["buy_zone"] = [70.0, 110.0]
    candidate["current_price"] = 102.0

    decision = _build([candidate]).decisions[0]

    assert decision.action == "watch"
    assert "expected_return_below_minimum" in decision.reason_codes
    assert "expected_return_near_miss" not in decision.reason_codes


def test_price_at_minimum_return_activation_remains_buyable():
    candidate = _candidate()
    candidate["buy_zone"] = [70.0, 110.0]
    candidate["current_price"] = 100.0

    decision = _build([candidate]).decisions[0]

    assert decision.expected_annual_return == pytest.approx(0.12)
    assert decision.action == "buy_now"


def test_near_miss_threshold_cannot_exceed_buy_threshold():
    from trading_os.research_assets.portfolio import PortfolioValidationError

    policy = {**POLICY, "near_miss_expected_annual_return": 0.13}

    with pytest.raises(PortfolioValidationError, match="must not exceed"):
        from trading_os.research_assets.portfolio import build_model_portfolio

        build_model_portfolio([_candidate()], policy=policy)


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


def test_potential_top_five_cannot_buy_without_independent_challenger():
    candidate = _candidate()
    candidate["independent_challenger_completed"] = False

    result = _build([candidate])
    decision = result.decisions[0]

    assert decision.action == "watch"
    assert "top_five_challenger_required" in decision.reason_codes
    assert result.challenger_required_symbols == (candidate["symbol"],)


def test_actual_largest_weight_cannot_hide_behind_five_smaller_positions():
    candidates = []
    for index in range(1, 6):
        candidate = _candidate(
            f"CN:{index:06d}",
            industry=f"industry-{index}",
            clusters=[f"cluster-{index}"],
            terminal_value=131.0 - index,
        )
        candidate["allowed_loss_weight"] = 0.001
        candidates.append(candidate)
    largest = _candidate(
        "CN:000006",
        industry="industry-6",
        clusters=["cluster-6"],
        terminal_value=112.0,
    )
    largest["independent_challenger_completed"] = False
    candidates.append(largest)

    result = _build(candidates)
    decisions = {item.symbol: item for item in result.decisions}

    assert result.challenger_required_symbols == ("CN:000006",)
    assert decisions["CN:000006"].action == "watch"
    assert decisions["CN:000006"].target_weight == 0
    assert "top_five_challenger_required" in decisions[
        "CN:000006"
    ].reason_codes


def test_medium_confidence_is_capped_at_three_percent():
    candidate = _candidate()
    candidate["confidence"] = "medium"

    assert _build([candidate]).decisions[0].target_weight == pytest.approx(0.03)


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

    assert _build([candidate]).decisions[0].target_weight == pytest.approx(0.02)


def test_industry_limit_is_enforced_across_machine_ranked_candidates():
    candidates = [
        _candidate(
            f"CN:{index:06d}",
            clusters=[f"cluster-{index}"],
            terminal_value=120.0 - index,
        )
        for index in range(1, 7)
    ]

    result = _build(candidates)

    assert sum(item.target_weight for item in result.decisions) == pytest.approx(0.20)
    assert sum(item.action == "buy_now" for item in result.decisions) == 4


def test_economic_risk_cluster_limit_crosses_industry_boundaries():
    candidates = [
        _candidate(
            f"CN:{index:06d}",
            industry=f"行业-{index}",
            clusters=["memory_price_cycle"],
            terminal_value=120.0 - index,
        )
        for index in range(1, 8)
    ]

    result = _build(candidates)

    assert sum(item.target_weight for item in result.decisions) == pytest.approx(0.25)
    assert sum(item.action == "buy_now" for item in result.decisions) == 5


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
            industry=f"industry-{index}",
            clusters=[f"cluster-{index}"],
            terminal_value=120.0 - index,
        )
        for index in range(1, 8)
    ]
    for candidate in candidates:
        candidate["allowed_loss_weight"] = 0.02

    result = build_model_portfolio(candidates, policy=policy)
    ranked = sorted((item.target_weight for item in result.decisions), reverse=True)

    assert sum(ranked[:5]) == pytest.approx(0.25)


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

    assert _build([candidate]).decisions[0].action == action


def test_input_order_does_not_change_machine_ranked_allocation():
    candidates = [
        _candidate("CN:000001", clusters=["a"], terminal_value=110.0),
        _candidate("CN:000002", clusters=["b"], terminal_value=120.0),
    ]

    left = _build(candidates)
    right = _build(list(reversed(copy.deepcopy(candidates))))

    assert left == right


@pytest.mark.parametrize("forbidden", ["portfolio_eligible", "rank_score", "expected_annual_return"])
def test_company_candidate_cannot_supply_cross_company_or_derived_conclusions(
    forbidden: str,
):
    from trading_os.research_assets.portfolio import PortfolioValidationError

    candidate = _candidate()
    candidate[forbidden] = 1

    with pytest.raises(PortfolioValidationError, match="unknown"):
        _build([candidate])


def test_invalid_return_model_is_rejected():
    from trading_os.research_assets.portfolio import PortfolioValidationError

    candidate = _candidate()
    candidate["return_model"]["base_case_distributions_per_share"] = [-1.0]

    with pytest.raises(PortfolioValidationError, match="non-negative"):
        _build([candidate])


def test_activation_price_rejects_overflowed_discounted_value():
    from trading_os.research_assets.portfolio import (
        PortfolioValidationError,
        activation_price,
    )

    model = _return_model(
        terminal_value=1.7976931348623157e308,
        distributions=[
            1.7976931348623157e308,
            1.7976931348623157e308,
        ],
    )

    with pytest.raises(PortfolioValidationError, match="must be finite"):
        activation_price(
            model,
            minimum_expected_annual_return=0.12,
        )


def test_activation_price_rejects_underflowed_discounted_value():
    from trading_os.research_assets.portfolio import (
        PortfolioValidationError,
        activation_price,
    )

    model = _return_model(
        terminal_value=5e-324,
        distributions=[0.0] * 30,
    )

    with pytest.raises(PortfolioValidationError, match="must be positive"):
        activation_price(
            model,
            minimum_expected_annual_return=1.0,
        )
