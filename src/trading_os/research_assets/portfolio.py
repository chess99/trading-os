from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .models import PortfolioAction, UnderwritingStatus


class PortfolioValidationError(ValueError):
    """Raised when portfolio candidates or constraints are malformed."""


@dataclass(frozen=True, slots=True)
class PortfolioDecision:
    symbol: str
    name: str
    underwriting_status: str
    evidence_stale: bool
    confidence: str
    action: str
    current_price: float
    bear_value: float
    fair_value_range: tuple[float, float]
    buy_zone: tuple[float, float]
    reduce_zone: tuple[float, float]
    target_weight: float
    initial_entry_weight: float
    industry: str
    economic_risk_clusters: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    decisions: tuple[PortfolioDecision, ...]
    exclusions: tuple[PortfolioDecision, ...]
    invested_weight: float
    cash_weight: float


CANDIDATE_KEYS = {
    "symbol",
    "name",
    "underwriting_status",
    "evidence_stale",
    "portfolio_eligible",
    "current_price",
    "bear_value",
    "fair_value_range",
    "buy_zone",
    "reduce_zone",
    "confidence",
    "industry",
    "economic_risk_clusters",
    "expected_annual_return",
    "bear_case_loss_fraction",
    "allowed_loss_weight",
    "rank_score",
    "held",
    "reason_codes",
}
POLICY_KEYS = {
    "max_single_name_weight",
    "max_industry_weight",
    "max_economic_risk_cluster_weight",
    "max_top_five_weight",
    "max_medium_confidence_weight",
    "max_low_confidence_weight",
    "initial_entry_fraction",
    "minimum_expected_annual_return",
    "near_miss_expected_annual_return",
    "allow_cash",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}


def build_model_portfolio(
    candidates: list[Mapping[str, Any]], *, policy: Mapping[str, Any]
) -> PortfolioResult:
    limits = _validate_policy(policy)
    normalized = [_normalize_candidate(item) for item in candidates]
    symbols = [item["symbol"] for item in normalized]
    if len(symbols) != len(set(symbols)):
        raise PortfolioValidationError("candidate symbols must be unique")
    normalized.sort(key=lambda item: (-item["rank_score"], item["symbol"]))

    industry_weights: dict[str, float] = {}
    cluster_weights: dict[str, float] = {}
    allocated_weights: list[float] = []
    decisions: list[PortfolioDecision] = []
    for item in normalized:
        action, gate_reasons = _preallocation_action(item, limits)
        reasons = set(item["reason_codes"])
        reasons.update(gate_reasons)
        target_weight = 0.0
        if action == PortfolioAction.BUY_NOW.value:
            confidence_cap = {
                "high": limits["max_single_name_weight"],
                "medium": limits["max_medium_confidence_weight"],
                "low": limits["max_low_confidence_weight"],
            }[item["confidence"]]
            if item["confidence"] == "low":
                reasons.add("low_confidence_zero_weight")
            bear_loss = item["bear_case_loss_fraction"]
            risk_cap = (
                limits["max_single_name_weight"]
                if bear_loss <= 0
                else item["allowed_loss_weight"] / bear_loss
            )
            industry_remaining = max(
                0.0,
                limits["max_industry_weight"]
                - industry_weights.get(item["industry"], 0.0),
            )
            cluster_remaining = min(
                (
                    max(
                        0.0,
                        limits["max_economic_risk_cluster_weight"]
                        - cluster_weights.get(cluster, 0.0),
                    )
                    for cluster in item["economic_risk_clusters"]
                ),
                default=limits["max_economic_risk_cluster_weight"],
            )
            top_five_remaining = _top_five_candidate_cap(
                allocated_weights,
                limits["max_top_five_weight"],
            )
            target_weight = max(
                0.0,
                min(
                    limits["max_single_name_weight"],
                    confidence_cap,
                    risk_cap,
                    industry_remaining,
                    cluster_remaining,
                    top_five_remaining,
                ),
            )
            if industry_remaining <= 1e-12:
                reasons.add("industry_limit_exhausted")
            if cluster_remaining <= 1e-12:
                reasons.add("risk_cluster_limit_exhausted")
            if top_five_remaining <= 1e-12:
                reasons.add("top_five_limit_exhausted")
            if target_weight <= 1e-12:
                action = PortfolioAction.WATCH.value
                target_weight = 0.0
            else:
                industry_weights[item["industry"]] = (
                    industry_weights.get(item["industry"], 0.0) + target_weight
                )
                for cluster in item["economic_risk_clusters"]:
                    cluster_weights[cluster] = (
                        cluster_weights.get(cluster, 0.0) + target_weight
                    )
                allocated_weights.append(target_weight)
        decision = PortfolioDecision(
            symbol=item["symbol"],
            name=item["name"],
            underwriting_status=item["underwriting_status"],
            evidence_stale=item["evidence_stale"],
            confidence=item["confidence"],
            action=action,
            current_price=item["current_price"],
            bear_value=item["bear_value"],
            fair_value_range=item["fair_value_range"],
            buy_zone=item["buy_zone"],
            reduce_zone=item["reduce_zone"],
            target_weight=target_weight,
            initial_entry_weight=(
                target_weight * limits["initial_entry_fraction"]
                if action == PortfolioAction.BUY_NOW.value
                else 0.0
            ),
            industry=item["industry"],
            economic_risk_clusters=item["economic_risk_clusters"],
            reason_codes=tuple(sorted(reasons)),
        )
        decisions.append(decision)

    invested = sum(item.target_weight for item in decisions)
    if invested > 1 + 1e-9:
        raise PortfolioValidationError("portfolio weights exceed 100%")
    cash = max(0.0, 1.0 - invested)
    if not limits["allow_cash"] and cash > 1e-9:
        raise PortfolioValidationError("portfolio policy disallows unallocated cash")
    exclusions = tuple(
        item for item in decisions if item.action != PortfolioAction.BUY_NOW.value
    )
    return PortfolioResult(
        decisions=tuple(decisions),
        exclusions=exclusions,
        invested_weight=invested,
        cash_weight=cash,
    )


def _top_five_candidate_cap(weights: list[float], limit: float) -> float:
    ranked = sorted(weights, reverse=True)
    if len(ranked) < 5:
        return max(0.0, limit - sum(ranked))
    return max(0.0, limit - sum(ranked[:4]))


def _preallocation_action(
    item: Mapping[str, Any], limits: Mapping[str, Any]
) -> tuple[str, set[str]]:
    reasons: set[str] = set()
    status = item["underwriting_status"]
    if item["held"]:
        if status == UnderwritingStatus.FAILED.value:
            return PortfolioAction.EXIT.value, {"underwriting_failed"}
        if item["current_price"] >= item["reduce_zone"][0]:
            return PortfolioAction.REDUCE.value, {"price_in_reduce_zone"}
        return PortfolioAction.HOLD.value, {"existing_holding"}
    if status == UnderwritingStatus.FAILED.value:
        return PortfolioAction.REJECT.value, {"underwriting_failed"}
    if status != UnderwritingStatus.PASSED.value:
        return PortfolioAction.WATCH.value, {f"underwriting_{status}"}
    if item["evidence_stale"]:
        return PortfolioAction.WATCH.value, {"evidence_stale"}
    if item["expected_annual_return"] < limits["minimum_expected_annual_return"]:
        reasons = {"expected_return_below_minimum"}
        if (
            item["expected_annual_return"]
            >= limits["near_miss_expected_annual_return"]
        ):
            reasons.add("expected_return_near_miss")
        return PortfolioAction.WATCH.value, reasons
    if item["current_price"] > item["buy_zone"][1]:
        return PortfolioAction.BUY_ON_WEAKNESS.value, {"price_above_buy_zone"}
    if not item["portfolio_eligible"]:
        return PortfolioAction.WATCH.value, {"not_selected_in_relative_ranking"}
    return PortfolioAction.BUY_NOW.value, reasons


def _normalize_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, Mapping) or set(candidate) != CANDIDATE_KEYS:
        raise PortfolioValidationError(
            "candidate fields do not match contract; "
            f"missing={sorted(CANDIDATE_KEYS - set(candidate))}, "
            f"unknown={sorted(set(candidate) - CANDIDATE_KEYS)}"
        )
    status = _require_text(candidate.get("underwriting_status"), "underwriting_status")
    allowed_statuses = {item.value for item in UnderwritingStatus}
    if status not in allowed_statuses:
        raise PortfolioValidationError(f"unsupported underwriting_status: {status}")
    confidence = _require_text(candidate.get("confidence"), "confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise PortfolioValidationError(f"unsupported confidence: {confidence}")
    clusters = candidate.get("economic_risk_clusters")
    if not isinstance(clusters, list) or not clusters:
        raise PortfolioValidationError("economic_risk_clusters must be non-empty")
    normalized_clusters = tuple(
        _require_text(cluster, "economic_risk_cluster") for cluster in clusters
    )
    if len(normalized_clusters) != len(set(normalized_clusters)):
        raise PortfolioValidationError("economic_risk_clusters must be unique")
    reasons = candidate.get("reason_codes")
    if not isinstance(reasons, list) or not reasons:
        raise PortfolioValidationError("reason_codes must be non-empty")
    normalized_reasons = tuple(_require_text(reason, "reason_code") for reason in reasons)
    result = dict(candidate)
    for field in (
        "current_price",
        "bear_value",
        "expected_annual_return",
        "bear_case_loss_fraction",
        "allowed_loss_weight",
        "rank_score",
    ):
        result[field] = _require_number(candidate.get(field), field)
    if result["current_price"] <= 0:
        raise PortfolioValidationError("current_price must be positive")
    result["fair_value_range"] = _require_range(
        candidate.get("fair_value_range"), "fair_value_range"
    )
    result["buy_zone"] = _require_range(candidate.get("buy_zone"), "buy_zone")
    result["reduce_zone"] = _require_range(candidate.get("reduce_zone"), "reduce_zone")
    result["symbol"] = _require_text(candidate.get("symbol"), "symbol")
    result["name"] = _require_text(candidate.get("name"), "name")
    result["industry"] = _require_text(candidate.get("industry"), "industry")
    result["underwriting_status"] = status
    result["confidence"] = confidence
    result["economic_risk_clusters"] = normalized_clusters
    result["reason_codes"] = normalized_reasons
    for field in ("evidence_stale", "portfolio_eligible", "held"):
        if not isinstance(candidate.get(field), bool):
            raise PortfolioValidationError(f"{field} must be boolean")
    return result


def _validate_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, Mapping) or set(policy) != POLICY_KEYS:
        raise PortfolioValidationError("portfolio policy fields do not match contract")
    result = dict(policy)
    for field in POLICY_KEYS - {"allow_cash"}:
        result[field] = _require_number(policy.get(field), f"policy.{field}")
        if not 0 <= result[field] <= 1:
            raise PortfolioValidationError(f"policy.{field} must be between 0 and 1")
    if not isinstance(policy.get("allow_cash"), bool):
        raise PortfolioValidationError("policy.allow_cash must be boolean")
    if (
        result["near_miss_expected_annual_return"]
        > result["minimum_expected_annual_return"]
    ):
        raise PortfolioValidationError(
            "policy.near_miss_expected_annual_return must not exceed "
            "policy.minimum_expected_annual_return"
        )
    return result


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PortfolioValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _require_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PortfolioValidationError(f"{label} must be numeric")
    return float(value)


def _require_range(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise PortfolioValidationError(f"{label} must be a two-number range")
    lower = _require_number(value[0], f"{label}[0]")
    upper = _require_number(value[1], f"{label}[1]")
    if lower > upper:
        raise PortfolioValidationError(f"{label} must be ordered")
    return lower, upper
