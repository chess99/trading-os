from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .evidence import EvidenceValidationResult
from .models import ClaimReviewStatus, UnderwritingStatus


class UnderwritingValidationError(ValueError):
    """Raised when a blind assessment cannot be evaluated deterministically."""


@dataclass(frozen=True, slots=True)
class UnderwritingEvaluation:
    status: str
    required_return: float
    required_safety_margin: float | None
    blockers: tuple[str, ...]
    challenger_triggers: tuple[str, ...]


ASSESSMENT_KEYS = {
    "confidence",
    "safety_margin_tier",
    "normalization",
    "accounting_checks",
    "bridges",
    "valuation",
    "counterevidence",
    "claim_reviews",
    "risk_flags",
}
NORMALIZATION_KEYS = {
    "method",
    "years_used",
    "single_quarter_annualized",
    "peak_profit_used",
    "normalized_profit",
}
ACCOUNTING_CHECK_CODES = {
    "nonrecurring_items_handled": "nonrecurring_items_unhandled",
    "net_debt_handled": "net_debt_unhandled",
    "minority_interests_handled": "minority_interests_unhandled",
    "dilution_handled": "dilution_unhandled",
    "cash_flow_divergence_explained": "cash_flow_divergence_unexplained",
    "working_capital_anomalies_explained": "working_capital_unexplained",
}
BRIDGE_CODES = {
    "earnings_quality_complete": "earnings_quality_bridge_incomplete",
    "cash_flow_complete": "cash_flow_bridge_incomplete",
    "normalized_earnings_complete": "normalized_earnings_bridge_incomplete",
}
VALUATION_KEYS = {
    "methods",
    "scenarios",
    "fair_value_range",
    "buy_zone",
    "formulas_reproducible",
    "sensitivity_complete",
    "market_implied_assumptions_complete",
    "government_bond_yield",
    "equity_cost",
    "required_return_used",
}
RISK_FLAG_KEYS = {
    "governance_material_doubt",
    "cycle_position_uncertain",
    "permanent_loss_risk",
}
CLAIM_REVIEW_KEYS = {"claim_id", "result"}


def evaluate_underwriting(
    assessment: Mapping[str, Any],
    *,
    evidence: EvidenceValidationResult,
    prior_claims: Mapping[str, str],
    policy: Mapping[str, Any],
    prior_fair_value_range: list[float] | None = None,
    proposed_top_five: bool = False,
    challenger_completed: bool = False,
) -> UnderwritingEvaluation:
    if not isinstance(assessment, Mapping):
        raise UnderwritingValidationError("assessment must be an object")
    _require_exact_keys(assessment, ASSESSMENT_KEYS, "assessment")
    if not isinstance(evidence, EvidenceValidationResult):
        raise UnderwritingValidationError("evidence must be EvidenceValidationResult")
    normalized_prior_claims = _validate_prior_claims(prior_claims)
    rules = _validate_policy(policy)
    if not isinstance(proposed_top_five, bool):
        raise UnderwritingValidationError("proposed_top_five must be boolean")
    if not isinstance(challenger_completed, bool):
        raise UnderwritingValidationError("challenger_completed must be boolean")

    blockers: set[str] = set()
    challenger: set[str] = set()
    confidence = _require_text(assessment.get("confidence"), "confidence")
    confidence_margin = {
        "high": rules["minimum_safety_margin"]["high_confidence"],
        "medium": rules["minimum_safety_margin"]["medium_confidence"],
        "low": rules["minimum_safety_margin"]["low_confidence"],
    }
    if confidence not in confidence_margin:
        raise UnderwritingValidationError(f"unsupported confidence: {confidence}")
    safety_margin_tier = _require_text(
        assessment.get("safety_margin_tier"),
        "safety_margin_tier",
    )
    risk_overlay_by_tier = {
        "standard": None,
        "elevated": rules["risk_overlay_safety_margin"]["elevated"],
        "severe": rules["risk_overlay_safety_margin"]["severe"],
    }
    if safety_margin_tier not in risk_overlay_by_tier:
        raise UnderwritingValidationError(
            f"unsupported safety_margin_tier: {safety_margin_tier}"
        )
    margin = confidence_margin[confidence]
    risk_overlay = risk_overlay_by_tier[safety_margin_tier]
    if margin is not None and risk_overlay is not None:
        margin = max(margin, risk_overlay)
    if confidence == "low":
        blockers.add("low_confidence")

    normalization = _require_object(assessment, "normalization")
    _require_exact_keys(normalization, NORMALIZATION_KEYS, "normalization")
    _require_text(normalization.get("method"), "normalization.method")
    _require_positive_int(normalization.get("years_used"), "normalization.years_used")
    _require_number(normalization.get("normalized_profit"), "normalized_profit")
    if _require_bool(
        normalization.get("single_quarter_annualized"), "single_quarter_annualized"
    ):
        blockers.add("single_quarter_annualized")
    if _require_bool(normalization.get("peak_profit_used"), "peak_profit_used"):
        blockers.add("peak_profit_used")

    accounting = _require_object(assessment, "accounting_checks")
    _require_exact_keys(accounting, set(ACCOUNTING_CHECK_CODES), "accounting_checks")
    for field, code in ACCOUNTING_CHECK_CODES.items():
        if not _require_bool(accounting.get(field), field):
            blockers.add(code)

    bridges = _require_object(assessment, "bridges")
    _require_exact_keys(bridges, set(BRIDGE_CODES), "bridges")
    for field, code in BRIDGE_CODES.items():
        if not _require_bool(bridges.get(field), field):
            blockers.add(code)

    valuation = _require_object(assessment, "valuation")
    _require_exact_keys(valuation, VALUATION_KEYS, "valuation")
    methods = _validate_methods(valuation.get("methods"))
    if len(methods) < rules["minimum_valuation_methods"]:
        blockers.add("insufficient_valuation_methods")
    scenarios = valuation.get("scenarios")
    if not isinstance(scenarios, Mapping):
        raise UnderwritingValidationError("valuation.scenarios must be an object")
    if set(scenarios) != set(rules["required_scenarios"]):
        blockers.add("missing_valuation_scenarios")
    else:
        for name, value in scenarios.items():
            _require_number(value, f"scenario {name}")
    fair_range = _require_range(valuation.get("fair_value_range"), "fair_value_range")
    buy_zone = _require_range(valuation.get("buy_zone"), "buy_zone")
    if not _require_bool(
        valuation.get("formulas_reproducible"), "formulas_reproducible"
    ):
        blockers.add("valuation_not_reproducible")
    if not _require_bool(
        valuation.get("sensitivity_complete"), "sensitivity_complete"
    ):
        blockers.add("valuation_sensitivity_incomplete")
    if not _require_bool(
        valuation.get("market_implied_assumptions_complete"),
        "market_implied_assumptions_complete",
    ):
        blockers.add("market_implied_assumptions_missing")

    bond_yield = _require_number(
        valuation.get("government_bond_yield"), "government_bond_yield"
    )
    equity_cost = _require_number(valuation.get("equity_cost"), "equity_cost")
    required_return = max(
        rules["minimum_valuation_discount_rate"],
        bond_yield + rules["government_bond_spread"],
        equity_cost,
    )
    required_used = _require_number(
        valuation.get("required_return_used"), "required_return_used"
    )
    if abs(required_used - required_return) > 1e-9:
        blockers.add("required_return_mismatch")
    if margin is not None:
        fair_midpoint = sum(fair_range) / 2
        max_buy_price = fair_midpoint * (1 - margin)
        if buy_zone[1] > max_buy_price + 1e-9:
            blockers.add("buy_zone_lacks_required_safety_margin")

    counterevidence = assessment.get("counterevidence")
    if not isinstance(counterevidence, list):
        raise UnderwritingValidationError("counterevidence must be an array")
    valid_counterevidence = [
        item for item in counterevidence if isinstance(item, str) and item.strip()
    ]
    if len(valid_counterevidence) != len(counterevidence):
        raise UnderwritingValidationError("counterevidence items must be non-empty strings")
    if len(set(valid_counterevidence)) < rules["minimum_counterevidence_items"]:
        blockers.add("insufficient_counterevidence")

    claim_reviews = _validate_claim_reviews(
        assessment.get("claim_reviews"), normalized_prior_claims
    )
    if any(
        item["category"] == "investment" and item["result"] == "disproven"
        for item in claim_reviews
    ):
        challenger.add("core_investment_claim_disproven")

    risk_flags = _require_object(assessment, "risk_flags")
    _require_exact_keys(risk_flags, RISK_FLAG_KEYS, "risk_flags")
    active_risk_flags: set[str] = set()
    for flag in RISK_FLAG_KEYS:
        if _require_bool(risk_flags.get(flag), flag):
            active_risk_flags.add(flag)
            challenger.add(flag)
    if (
        active_risk_flags & {"governance_material_doubt", "cycle_position_uncertain"}
        and safety_margin_tier == "standard"
    ):
        blockers.add("safety_margin_tier_below_material_risk")
    if (
        "permanent_loss_risk" in active_risk_flags
        and safety_margin_tier != "severe"
    ):
        blockers.add("safety_margin_tier_below_permanent_loss_risk")
    if proposed_top_five:
        challenger.add("proposed_top_five_position")
    if prior_fair_value_range is not None:
        prior = _require_range(prior_fair_value_range, "prior_fair_value_range")
        prior_midpoint = sum(prior) / 2
        new_midpoint = sum(fair_range) / 2
        if prior_midpoint <= 0:
            raise UnderwritingValidationError("prior fair value midpoint must be positive")
        if (
            abs(new_midpoint - prior_midpoint) / prior_midpoint
            > rules["challenger_thresholds"][
                "old_new_fair_value_midpoint_difference"
            ]
        ):
            challenger.add("old_new_fair_value_difference_over_30pct")
    if len(methods) >= 2:
        method_values = [value for _, value in methods]
        midpoint = (max(method_values) + min(method_values)) / 2
        if (
            midpoint > 0
            and (max(method_values) - min(method_values)) / midpoint
            > rules["challenger_thresholds"]["valuation_method_difference"]
        ):
            challenger.add("valuation_methods_diverge_over_40pct")

    if not evidence.is_valid:
        blockers.update(evidence.blockers)
        status = (
            UnderwritingStatus.STALE.value
            if evidence.is_stale
            else UnderwritingStatus.INSUFFICIENT_EVIDENCE.value
        )
    elif confidence == "low":
        status = UnderwritingStatus.INSUFFICIENT_EVIDENCE.value
    elif blockers:
        status = UnderwritingStatus.FAILED.value
    elif challenger and not challenger_completed:
        status = UnderwritingStatus.NEEDS_CHALLENGER.value
    else:
        status = UnderwritingStatus.PASSED.value
    return UnderwritingEvaluation(
        status=status,
        required_return=required_return,
        required_safety_margin=margin,
        blockers=tuple(sorted(blockers)),
        challenger_triggers=tuple(sorted(challenger)),
    )


def _validate_methods(raw: Any) -> list[tuple[str, float]]:
    if not isinstance(raw, list):
        raise UnderwritingValidationError("valuation.methods must be an array")
    result: list[tuple[str, float]] = []
    names: set[str] = set()
    for index, method in enumerate(raw):
        if not isinstance(method, Mapping) or set(method) != {"name", "value"}:
            raise UnderwritingValidationError(
                f"valuation method {index} must contain name and value"
            )
        name = _require_text(method.get("name"), "valuation method name")
        if name in names:
            raise UnderwritingValidationError(f"duplicate valuation method: {name}")
        names.add(name)
        result.append((name, _require_number(method.get("value"), "method value")))
    return result


def _validate_claim_reviews(
    raw: Any,
    prior_claims: Mapping[str, str],
) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise UnderwritingValidationError("claim_reviews must be an array")
    allowed_results = {item.value for item in ClaimReviewStatus}
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, review in enumerate(raw):
        if not isinstance(review, Mapping):
            raise UnderwritingValidationError(f"claim review {index} must be an object")
        _require_exact_keys(review, CLAIM_REVIEW_KEYS, f"claim review {index}")
        claim_id = _require_text(review.get("claim_id"), "claim review claim_id")
        if claim_id in seen:
            raise UnderwritingValidationError(f"duplicate claim review: {claim_id}")
        seen.add(claim_id)
        review_result = _require_text(review.get("result"), "claim review result")
        if review_result not in allowed_results:
            raise UnderwritingValidationError(f"unsupported claim review result: {review_result}")
        result.append(
            {
                "claim_id": claim_id,
                "category": prior_claims[claim_id],
                "result": review_result,
            }
        )
    if seen != set(prior_claims):
        raise UnderwritingValidationError(
            "claim review coverage must exactly match all prior claim IDs"
        )
    return result


def _validate_prior_claims(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise UnderwritingValidationError("prior_claims must be a non-empty object")
    allowed_categories = {"fact", "business", "industry", "investment"}
    result: dict[str, str] = {}
    for claim_id, category in value.items():
        normalized_id = _require_text(claim_id, "prior claim_id")
        normalized_category = _require_text(category, "prior claim category")
        if normalized_category not in allowed_categories:
            raise UnderwritingValidationError(
                f"unsupported prior claim category: {normalized_category}"
            )
        result[normalized_id] = normalized_category
    return result


def _validate_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnderwritingValidationError("policy must be an object")
    required = {
        "minimum_valuation_discount_rate",
        "government_bond_spread",
        "minimum_safety_margin",
        "risk_overlay_safety_margin",
        "minimum_counterevidence_items",
        "minimum_valuation_methods",
        "required_scenarios",
        "challenger_thresholds",
    }
    missing = required - set(value)
    if missing:
        raise UnderwritingValidationError(
            f"underwriting policy is missing fields: {sorted(missing)}"
        )
    minimum_margin = value["minimum_safety_margin"]
    if not isinstance(minimum_margin, Mapping) or set(minimum_margin) != {
        "high_confidence",
        "medium_confidence",
        "low_confidence",
    }:
        raise UnderwritingValidationError(
            "policy.minimum_safety_margin fields do not match contract"
        )
    normalized_margin: dict[str, float | None] = {}
    for key, raw in minimum_margin.items():
        if raw is None:
            normalized_margin[key] = None
        else:
            margin = _require_number(raw, f"minimum_safety_margin.{key}")
            if not 0 <= margin <= 1:
                raise UnderwritingValidationError(
                    f"minimum_safety_margin.{key} must be between 0 and 1"
                )
            normalized_margin[key] = margin
    overlay = value["risk_overlay_safety_margin"]
    if not isinstance(overlay, Mapping) or set(overlay) != {"elevated", "severe"}:
        raise UnderwritingValidationError(
            "policy.risk_overlay_safety_margin fields do not match contract"
        )
    normalized_overlay = {
        key: _require_number(raw, f"risk_overlay_safety_margin.{key}")
        for key, raw in overlay.items()
    }
    thresholds = value["challenger_thresholds"]
    if not isinstance(thresholds, Mapping) or set(thresholds) != {
        "old_new_fair_value_midpoint_difference",
        "valuation_method_difference",
    }:
        raise UnderwritingValidationError(
            "policy.challenger_thresholds fields do not match contract"
        )
    normalized_thresholds = {
        key: _require_number(raw, f"challenger_thresholds.{key}")
        for key, raw in thresholds.items()
    }
    scenarios = value["required_scenarios"]
    if (
        not isinstance(scenarios, list)
        or len(scenarios) != 3
        or len(set(scenarios)) != 3
        or any(not isinstance(item, str) or not item.strip() for item in scenarios)
    ):
        raise UnderwritingValidationError(
            "policy.required_scenarios must contain three unique names"
        )
    counters = _require_positive_int(
        value["minimum_counterevidence_items"],
        "minimum_counterevidence_items",
    )
    methods = _require_positive_int(
        value["minimum_valuation_methods"],
        "minimum_valuation_methods",
    )
    return {
        "minimum_valuation_discount_rate": _require_number(
            value["minimum_valuation_discount_rate"],
            "minimum_valuation_discount_rate",
        ),
        "government_bond_spread": _require_number(
            value["government_bond_spread"],
            "government_bond_spread",
        ),
        "minimum_safety_margin": normalized_margin,
        "risk_overlay_safety_margin": normalized_overlay,
        "minimum_counterevidence_items": counters,
        "minimum_valuation_methods": methods,
        "required_scenarios": list(scenarios),
        "challenger_thresholds": normalized_thresholds,
    }


def _require_object(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    result = value.get(key)
    if not isinstance(result, Mapping):
        raise UnderwritingValidationError(f"{key} must be an object")
    return result


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise UnderwritingValidationError(
            f"{label} fields do not match contract; "
            f"missing={sorted(expected - set(value))}, unknown={sorted(set(value) - expected)}"
        )


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnderwritingValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise UnderwritingValidationError(f"{label} must be boolean")
    return value


def _require_positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise UnderwritingValidationError(f"{label} must be a positive integer")
    return value


def _require_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnderwritingValidationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise UnderwritingValidationError(f"{label} must be finite")
    return result


def _require_range(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise UnderwritingValidationError(f"{label} must be a two-number range")
    lower = _require_number(value[0], f"{label}[0]")
    upper = _require_number(value[1], f"{label}[1]")
    if lower > upper:
        raise UnderwritingValidationError(f"{label} must be ordered")
    return lower, upper
