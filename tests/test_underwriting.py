from __future__ import annotations

from dataclasses import replace

import pytest

from trading_os.research_assets.evidence import EvidenceValidationResult

VALID_EVIDENCE = EvidenceValidationResult(True, False, (), ())


def _assessment() -> dict[str, object]:
    return {
        "confidence": "high",
        "cyclical_or_governance_risk": False,
        "normalization": {
            "method": "five_year_mid_cycle",
            "years_used": 5,
            "single_quarter_annualized": False,
            "peak_profit_used": False,
            "normalized_profit": 100.0,
        },
        "accounting_checks": {
            "nonrecurring_items_handled": True,
            "net_debt_handled": True,
            "minority_interests_handled": True,
            "dilution_handled": True,
            "cash_flow_divergence_explained": True,
            "working_capital_anomalies_explained": True,
        },
        "bridges": {
            "earnings_quality_complete": True,
            "cash_flow_complete": True,
            "normalized_earnings_complete": True,
        },
        "valuation": {
            "methods": [
                {"name": "dcf", "value": 100.0},
                {"name": "normalized_pe", "value": 105.0},
            ],
            "scenarios": {"bear": 70.0, "base": 100.0, "bull": 130.0},
            "fair_value_range": [95.0, 105.0],
            "buy_zone": [70.0, 80.0],
            "formulas_reproducible": True,
            "sensitivity_complete": True,
            "market_implied_assumptions_complete": True,
            "government_bond_yield": 0.03,
            "equity_cost": 0.11,
            "required_return_used": 0.12,
        },
        "counterevidence": ["需求下行", "成本上升", "竞争加剧"],
        "claim_reviews": [
            {"claim_id": "C1", "category": "investment", "result": "confirmed"},
            {"claim_id": "C2", "category": "fact", "result": "weakened"},
        ],
        "risk_flags": {
            "governance_material_doubt": False,
            "cycle_position_uncertain": False,
            "permanent_loss_risk": False,
        },
    }


def _evaluate(
    assessment: dict[str, object] | None = None,
    *,
    evidence: EvidenceValidationResult = VALID_EVIDENCE,
    prior_fair_value_range: list[float] | None = None,
    proposed_top_five: bool = False,
):
    from trading_os.research_assets.underwriting import evaluate_underwriting

    return evaluate_underwriting(
        assessment or _assessment(),
        evidence=evidence,
        prior_claim_ids={"C1", "C2"},
        prior_fair_value_range=prior_fair_value_range,
        proposed_top_five=proposed_top_five,
    )


def test_valid_assessment_passes_with_dynamic_required_return():
    result = _evaluate()

    assert result.status == "passed"
    assert result.required_return == pytest.approx(0.12)
    assert result.required_safety_margin == pytest.approx(0.20)
    assert result.blockers == ()
    assert result.challenger_triggers == ()


@pytest.mark.parametrize(
    ("bond_yield", "equity_cost", "expected"),
    [(0.05, 0.11, 0.13), (0.03, 0.15, 0.15)],
)
def test_required_return_uses_highest_hurdle(
    bond_yield: float, equity_cost: float, expected: float
):
    assessment = _assessment()
    assessment["valuation"]["government_bond_yield"] = bond_yield
    assessment["valuation"]["equity_cost"] = equity_cost
    assessment["valuation"]["required_return_used"] = expected

    result = _evaluate(assessment)

    assert result.required_return == pytest.approx(expected)


@pytest.mark.parametrize(
    ("section", "field", "code"),
    [
        ("normalization", "single_quarter_annualized", "single_quarter_annualized"),
        ("normalization", "peak_profit_used", "peak_profit_used"),
        ("accounting_checks", "nonrecurring_items_handled", "nonrecurring_items_unhandled"),
        ("accounting_checks", "net_debt_handled", "net_debt_unhandled"),
        ("accounting_checks", "minority_interests_handled", "minority_interests_unhandled"),
        ("accounting_checks", "dilution_handled", "dilution_unhandled"),
        ("accounting_checks", "cash_flow_divergence_explained", "cash_flow_divergence_unexplained"),
        ("accounting_checks", "working_capital_anomalies_explained", "working_capital_unexplained"),
        ("bridges", "earnings_quality_complete", "earnings_quality_bridge_incomplete"),
        ("bridges", "cash_flow_complete", "cash_flow_bridge_incomplete"),
        ("bridges", "normalized_earnings_complete", "normalized_earnings_bridge_incomplete"),
    ],
)
def test_hard_accounting_and_normalization_failures_block_underwriting(
    section: str, field: str, code: str
):
    assessment = _assessment()
    assessment[section][field] = section == "normalization"

    result = _evaluate(assessment)

    assert result.status == "failed"
    assert code in result.blockers


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda value: value["valuation"].update(methods=[{"name": "dcf", "value": 100}]),
            "insufficient_valuation_methods",
        ),
        (
            lambda value: value["valuation"].update(scenarios={"base": 100}),
            "missing_valuation_scenarios",
        ),
        (
            lambda value: value["valuation"].update(formulas_reproducible=False),
            "valuation_not_reproducible",
        ),
        (
            lambda value: value["valuation"].update(sensitivity_complete=False),
            "valuation_sensitivity_incomplete",
        ),
        (
            lambda value: value["valuation"].update(market_implied_assumptions_complete=False),
            "market_implied_assumptions_missing",
        ),
    ],
)
def test_valuation_quality_failures_block_underwriting(mutation, code: str):
    assessment = _assessment()
    mutation(assessment)

    result = _evaluate(assessment)

    assert result.status == "failed"
    assert code in result.blockers


def test_fewer_than_three_counterevidence_items_blocks_underwriting():
    assessment = _assessment()
    assessment["counterevidence"] = ["只有一条"]

    result = _evaluate(assessment)

    assert result.status == "failed"
    assert "insufficient_counterevidence" in result.blockers


def test_buy_zone_must_respect_confidence_safety_margin():
    assessment = _assessment()
    assessment["valuation"]["buy_zone"] = [80.0, 90.0]

    result = _evaluate(assessment)

    assert result.status == "failed"
    assert "buy_zone_lacks_required_safety_margin" in result.blockers


def test_low_confidence_cannot_pass_underwriting():
    assessment = _assessment()
    assessment["confidence"] = "low"

    result = _evaluate(assessment)

    assert result.status == "insufficient_evidence"
    assert "low_confidence" in result.blockers


def test_stale_evidence_makes_underwriting_stale():
    evidence = EvidenceValidationResult(False, True, ("stale_market_price",), ())

    result = _evaluate(evidence=evidence)

    assert result.status == "stale"


def test_missing_evidence_makes_underwriting_insufficient():
    evidence = EvidenceValidationResult(
        False,
        False,
        ("missing_required_filing:2026-q1",),
        (),
    )

    result = _evaluate(evidence=evidence)

    assert result.status == "insufficient_evidence"


@pytest.mark.parametrize(
    ("mutator", "trigger"),
    [
        (lambda value: None, "old_new_fair_value_difference_over_30pct"),
        (
            lambda value: value["valuation"].update(
                methods=[{"name": "a", "value": 70}, {"name": "b", "value": 130}]
            ),
            "valuation_methods_diverge_over_40pct",
        ),
        (
            lambda value: value["claim_reviews"][0].update(result="disproven"),
            "core_investment_claim_disproven",
        ),
        (
            lambda value: value["risk_flags"].update(governance_material_doubt=True),
            "governance_material_doubt",
        ),
        (
            lambda value: value["risk_flags"].update(cycle_position_uncertain=True),
            "cycle_position_uncertain",
        ),
        (lambda value: value["risk_flags"].update(permanent_loss_risk=True), "permanent_loss_risk"),
    ],
)
def test_material_disagreement_triggers_independent_challenger(mutator, trigger: str):
    assessment = _assessment()
    mutator(assessment)
    prior = [55.0, 65.0] if trigger.startswith("old_new") else None

    result = _evaluate(assessment, prior_fair_value_range=prior)

    assert result.status == "needs_challenger"
    assert trigger in result.challenger_triggers


def test_proposed_top_five_position_always_triggers_challenger():
    result = _evaluate(proposed_top_five=True)

    assert result.status == "needs_challenger"
    assert "proposed_top_five_position" in result.challenger_triggers


def test_every_prior_claim_requires_one_difference_result():
    from trading_os.research_assets.underwriting import UnderwritingValidationError

    assessment = _assessment()
    assessment["claim_reviews"] = [assessment["claim_reviews"][0]]

    with pytest.raises(UnderwritingValidationError, match="claim review coverage"):
        _evaluate(assessment)


def test_evidence_result_is_immutable_fixture():
    changed = replace(VALID_EVIDENCE, is_valid=False, blockers=("x",))

    assert VALID_EVIDENCE.is_valid is True
    assert changed.is_valid is False
