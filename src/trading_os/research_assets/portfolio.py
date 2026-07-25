from __future__ import annotations

import datetime as dt
import hashlib
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .models import PortfolioAction, UnderwritingStatus
from .sealing import canonical_json_bytes


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
    price_as_of: str
    expected_annual_return: float
    minimum_expected_annual_return: float
    expected_return_gap: float
    minimum_return_activation_price: float
    near_miss_return_activation_price: float
    buy_now_price_ceiling: float
    bear_value: float
    fair_value_range: tuple[float, float]
    buy_zone: tuple[float, float]
    reduce_zone: tuple[float, float]
    return_model_method: str
    return_model_currency: str
    return_model_as_of: str
    holding_period_years: int
    terminal_value: float
    annual_cash_distributions: tuple[float, ...]
    target_weight: float
    initial_entry_weight: float
    industry: str
    economic_risk_clusters: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    decisions: tuple[PortfolioDecision, ...]
    exclusions: tuple[PortfolioDecision, ...]
    challenger_required_symbols: tuple[str, ...]
    invested_weight: float
    cash_weight: float


CANDIDATE_KEYS = {
    "symbol",
    "name",
    "underwriting_status",
    "evidence_stale",
    "independent_challenger_completed",
    "source_machine_decision_sha256",
    "policy_snapshot_sha256",
    "current_price",
    "price_as_of",
    "bear_value",
    "fair_value_range",
    "buy_zone",
    "reduce_zone",
    "confidence",
    "industry",
    "economic_risk_clusters",
    "return_model",
    "bear_case_loss_fraction",
    "allowed_loss_weight",
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
    "max_per_name_loss_weight",
    "initial_entry_fraction",
    "minimum_expected_annual_return",
    "near_miss_expected_annual_return",
    "allow_cash",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}


def portfolio_candidate_core_sha256(candidate: Mapping[str, Any]) -> str:
    """Hash every candidate field except its circular machine-decision link."""

    if not isinstance(candidate, Mapping) or set(candidate) != CANDIDATE_KEYS:
        raise PortfolioValidationError(
            "candidate fields do not match contract for core SHA-256"
        )
    core = dict(candidate)
    core.pop("source_machine_decision_sha256")
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def build_model_portfolio(
    candidates: list[Mapping[str, Any]], *, policy: Mapping[str, Any]
) -> PortfolioResult:
    limits = _validate_policy(policy)
    normalized = [
        _normalize_candidate(
            item,
            minimum_expected_annual_return=limits["minimum_expected_annual_return"],
            near_miss_expected_annual_return=limits[
                "near_miss_expected_annual_return"
            ],
        )
        for item in candidates
    ]
    symbols = [item["symbol"] for item in normalized]
    if len(symbols) != len(set(symbols)):
        raise PortfolioValidationError("candidate symbols must be unique")
    normalized.sort(
        key=lambda item: (
            -item["expected_annual_return"],
            item["bear_case_loss_fraction"],
            item["symbol"],
        )
    )
    challenger_by_symbol = {
        item["symbol"]: item["independent_challenger_completed"]
        for item in normalized
    }
    decisions = _allocate_candidates(
        normalized,
        limits,
        top_five_challenger_blocked=set(),
    )
    first_wave = _unchallenged_top_five(
        decisions,
        challenger_by_symbol=challenger_by_symbol,
    )
    blocked: set[str] = set()
    while True:
        required = _unchallenged_top_five(
            decisions,
            challenger_by_symbol=challenger_by_symbol,
        )
        new_required = required - blocked
        if not new_required:
            break
        blocked.update(new_required)
        decisions = _allocate_candidates(
            normalized,
            limits,
            top_five_challenger_blocked=blocked,
        )

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
        challenger_required_symbols=tuple(sorted(first_wave)),
        invested_weight=invested,
        cash_weight=cash,
    )


def _allocate_candidates(
    normalized: list[dict[str, Any]],
    limits: Mapping[str, Any],
    *,
    top_five_challenger_blocked: set[str],
) -> list[PortfolioDecision]:
    industry_weights: dict[str, float] = {}
    cluster_weights: dict[str, float] = {}
    allocated_weights: list[float] = []
    decisions: list[PortfolioDecision] = []
    for item in normalized:
        action, gate_reasons = _preallocation_action(
            item,
            limits,
            top_five_challenger_required=(
                item["symbol"] in top_five_challenger_blocked
            ),
        )
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
            price_as_of=item["price_as_of"],
            expected_annual_return=item["expected_annual_return"],
            minimum_expected_annual_return=limits["minimum_expected_annual_return"],
            expected_return_gap=(
                item["expected_annual_return"]
                - limits["minimum_expected_annual_return"]
            ),
            minimum_return_activation_price=item[
                "minimum_return_activation_price"
            ],
            near_miss_return_activation_price=item[
                "near_miss_return_activation_price"
            ],
            buy_now_price_ceiling=min(
                item["buy_zone"][1],
                item["minimum_return_activation_price"],
            ),
            bear_value=item["bear_value"],
            fair_value_range=item["fair_value_range"],
            buy_zone=item["buy_zone"],
            reduce_zone=item["reduce_zone"],
            return_model_method=item["return_model"]["method"],
            return_model_currency=item["return_model"]["currency"],
            return_model_as_of=item["return_model"]["model_as_of"],
            holding_period_years=len(
                item["return_model"]["base_case_distributions_per_share"]
            ),
            terminal_value=item["return_model"][
                "base_case_terminal_value_per_share"
            ],
            annual_cash_distributions=item["return_model"][
                "base_case_distributions_per_share"
            ],
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
    return decisions


def _unchallenged_top_five(
    decisions: list[PortfolioDecision],
    *,
    challenger_by_symbol: Mapping[str, bool],
) -> set[str]:
    ranked = sorted(
        (item for item in decisions if item.target_weight > 1e-12),
        key=lambda item: (
            -item.target_weight,
            -item.expected_annual_return,
            item.symbol,
        ),
    )
    return {
        item.symbol
        for item in ranked[:5]
        if not challenger_by_symbol[item.symbol]
    }


def _top_five_candidate_cap(weights: list[float], limit: float) -> float:
    ranked = sorted(weights, reverse=True)
    if len(ranked) < 5:
        return max(0.0, limit - sum(ranked))
    return max(0.0, limit - sum(ranked[:4]))


def _preallocation_action(
    item: Mapping[str, Any],
    limits: Mapping[str, Any],
    *,
    top_five_challenger_required: bool,
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
    if (
        item["current_price"]
        > item["minimum_return_activation_price"] + 1e-9
    ):
        reasons = {"expected_return_below_minimum"}
        if item["current_price"] <= item["near_miss_return_activation_price"] + 1e-9:
            reasons.add("expected_return_near_miss")
        return PortfolioAction.WATCH.value, reasons
    if item["current_price"] > item["buy_zone"][1]:
        return PortfolioAction.BUY_ON_WEAKNESS.value, {"price_above_buy_zone"}
    if top_five_challenger_required:
        return PortfolioAction.WATCH.value, {"top_five_challenger_required"}
    return PortfolioAction.BUY_NOW.value, reasons


def _normalize_candidate(
    candidate: Mapping[str, Any],
    *,
    minimum_expected_annual_return: float,
    near_miss_expected_annual_return: float,
) -> dict[str, Any]:
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
        "bear_case_loss_fraction",
        "allowed_loss_weight",
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
    result["price_as_of"] = _require_aware_datetime_text(
        candidate.get("price_as_of"), "price_as_of"
    )
    result["underwriting_status"] = status
    result["confidence"] = confidence
    result["economic_risk_clusters"] = normalized_clusters
    result["reason_codes"] = normalized_reasons
    result["return_model"] = _normalize_return_model(
        candidate.get("return_model")
    )
    result["expected_annual_return"] = expected_annual_return(
        result["current_price"],
        result["return_model"],
    )
    result["minimum_return_activation_price"] = activation_price(
        result["return_model"],
        minimum_expected_annual_return=minimum_expected_annual_return,
    )
    result["near_miss_return_activation_price"] = activation_price(
        result["return_model"],
        minimum_expected_annual_return=near_miss_expected_annual_return,
    )
    for field in ("evidence_stale", "independent_challenger_completed", "held"):
        if not isinstance(candidate.get(field), bool):
            raise PortfolioValidationError(f"{field} must be boolean")
    for field in (
        "source_machine_decision_sha256",
        "policy_snapshot_sha256",
    ):
        value = candidate.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise PortfolioValidationError(
                f"{field} must be a lowercase SHA-256 digest"
            )
    return result


def expected_annual_return(
    current_price: float,
    return_model: Mapping[str, Any],
) -> float:
    """Solve the annual IRR implied by price and sealed base-case cash flows."""

    price = _require_number(current_price, "current_price")
    if price <= 0:
        raise PortfolioValidationError("current_price must be positive")
    model = _normalize_return_model(return_model)

    def present_value(rate: float) -> float:
        distributions = model["base_case_distributions_per_share"]
        terminal = model["base_case_terminal_value_per_share"]
        value = sum(
            distribution / ((1 + rate) ** year)
            for year, distribution in enumerate(distributions, start=1)
        )
        return value + terminal / ((1 + rate) ** len(distributions))

    lower = -0.999999
    upper = 1.0
    while present_value(upper) > price and upper < 1_000_000:
        upper = upper * 2 + 1
    if present_value(upper) > price:
        raise PortfolioValidationError(
            "return_model implies an annual return above the supported range"
        )
    for _ in range(200):
        midpoint = (lower + upper) / 2
        if present_value(midpoint) > price:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2


def activation_price(
    return_model: Mapping[str, Any],
    *,
    minimum_expected_annual_return: float,
) -> float:
    """Return the maximum price whose base-case cash flows meet the hurdle."""

    hurdle = _require_number(
        minimum_expected_annual_return,
        "minimum_expected_annual_return",
    )
    if hurdle <= -1:
        raise PortfolioValidationError(
            "minimum_expected_annual_return must be greater than -1"
        )
    model = _normalize_return_model(return_model)
    distributions = model["base_case_distributions_per_share"]
    terminal = model["base_case_terminal_value_per_share"]
    value = sum(
        distribution / ((1 + hurdle) ** year)
        for year, distribution in enumerate(distributions, start=1)
    )
    result = _require_number(
        value + terminal / ((1 + hurdle) ** len(distributions)),
        "minimum_return_activation_price",
    )
    if result <= 0:
        raise PortfolioValidationError(
            "minimum_return_activation_price must be positive"
        )
    return result


def _normalize_return_model(value: Any) -> dict[str, Any]:
    expected = {
        "schema_version",
        "method",
        "currency",
        "model_as_of",
        "base_case_distributions_per_share",
        "base_case_terminal_value_per_share",
    }
    if not isinstance(value, Mapping):
        raise PortfolioValidationError("return_model must be an object")
    if set(value) != expected:
        raise PortfolioValidationError(
            "return_model fields do not match contract; "
            f"missing={sorted(expected - set(value))}, "
            f"unknown={sorted(set(value) - expected)}"
        )
    if value.get("schema_version") != 1:
        raise PortfolioValidationError("return_model.schema_version must be 1")
    method = _require_text(value.get("method"), "return_model.method")
    if method != "annual_cashflow_irr_v1":
        raise PortfolioValidationError(f"unsupported return_model.method: {method}")
    currency = _require_text(value.get("currency"), "return_model.currency")
    model_as_of = _require_aware_datetime_text(
        value.get("model_as_of"),
        "return_model.model_as_of",
    )
    raw_distributions = value.get("base_case_distributions_per_share")
    if not isinstance(raw_distributions, (list, tuple)) or not 1 <= len(
        raw_distributions
    ) <= 30:
        raise PortfolioValidationError(
            "return_model.base_case_distributions_per_share must contain 1 to 30 years"
        )
    distributions = tuple(
        _require_number(item, "base_case_distribution")
        for item in raw_distributions
    )
    if any(item < 0 for item in distributions):
        raise PortfolioValidationError(
            "return_model base-case distributions must be non-negative"
        )
    terminal = _require_number(
        value.get("base_case_terminal_value_per_share"),
        "return_model.base_case_terminal_value_per_share",
    )
    if terminal <= 0:
        raise PortfolioValidationError(
            "return_model base-case terminal value must be positive"
        )
    return {
        "schema_version": 1,
        "method": method,
        "currency": currency,
        "model_as_of": model_as_of,
        "base_case_distributions_per_share": distributions,
        "base_case_terminal_value_per_share": terminal,
    }


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
    result = float(value)
    if not math.isfinite(result):
        raise PortfolioValidationError(f"{label} must be finite")
    return result


def _require_aware_datetime_text(value: Any, label: str) -> str:
    text = _require_text(value, label)
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise PortfolioValidationError(f"{label} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortfolioValidationError(f"{label} must include a UTC offset")
    return parsed.isoformat()


def _require_range(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise PortfolioValidationError(f"{label} must be a two-number range")
    lower = _require_number(value[0], f"{label}[0]")
    upper = _require_number(value[1], f"{label}[1]")
    if lower > upper:
        raise PortfolioValidationError(f"{label} must be ordered")
    return lower, upper
