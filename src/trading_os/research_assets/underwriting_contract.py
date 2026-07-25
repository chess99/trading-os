from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .evidence import EvidenceValidationResult, validate_evidence_ledger
from .portfolio import (
    PortfolioValidationError,
    expected_annual_return,
)
from .underwriting import UnderwritingEvaluation, evaluate_underwriting


class UnderwritingContractError(ValueError):
    """Raised when an independent assessment cannot enter machine underwriting."""


@dataclass(frozen=True, slots=True)
class MachineUnderwritingResult:
    evaluation: UnderwritingEvaluation
    evidence: EvidenceValidationResult
    prior_claims: Mapping[str, str]


ENVELOPE_KEYS = {
    "schema_version",
    "assessment_id",
    "review_id",
    "packet_sha256",
    "symbol",
    "information_cutoff",
    "assessment",
    "evidence",
    "portfolio_inputs",
}
EVIDENCE_INPUT_KEYS = {"ledger", "share_count_bridge"}
PORTFOLIO_INPUT_KEYS = {
    "current_price",
    "price_as_of",
    "reduce_zone",
    "industry",
    "economic_risk_clusters",
    "return_model",
}


def evaluate_assessment_envelope(
    envelope: Mapping[str, Any],
    *,
    expected_symbol: str,
    expected_review_id: str,
    expected_packet_sha256: str,
    claim_packet: Mapping[str, Any],
    underwriting_policy: Mapping[str, Any],
    evaluated_at: dt.datetime,
    prior_fair_value_range: list[float] | None,
    proposed_top_five: bool = False,
    challenger_completed: bool = False,
) -> MachineUnderwritingResult:
    _require_aware(evaluated_at, "evaluated_at")
    _validate_envelope_identity(
        envelope,
        expected_symbol=expected_symbol,
        expected_review_id=expected_review_id,
        expected_packet_sha256=expected_packet_sha256,
        evaluated_at=evaluated_at,
    )
    prior_claims, allowed_sources = _packet_authorities(
        claim_packet,
        expected_symbol=expected_symbol,
        expected_review_id=expected_review_id,
    )
    evidence = _evaluate_evidence(
        envelope,
        prior_claims=prior_claims,
        allowed_sources=allowed_sources,
        policy=underwriting_policy,
        evaluated_at=evaluated_at,
    )
    _validate_portfolio_inputs(envelope["portfolio_inputs"])
    evaluation = evaluate_underwriting(
        envelope["assessment"],
        evidence=evidence,
        prior_claims=prior_claims,
        policy=underwriting_policy,
        prior_fair_value_range=prior_fair_value_range,
        proposed_top_five=proposed_top_five,
        challenger_completed=challenger_completed,
    )
    return MachineUnderwritingResult(
        evaluation=evaluation,
        evidence=evidence,
        prior_claims=prior_claims,
    )


def _validate_envelope_identity(
    envelope: Mapping[str, Any],
    *,
    expected_symbol: str,
    expected_review_id: str,
    expected_packet_sha256: str,
    evaluated_at: dt.datetime,
) -> None:
    if not isinstance(envelope, Mapping) or set(envelope) != ENVELOPE_KEYS:
        actual = set(envelope) if isinstance(envelope, Mapping) else set()
        raise UnderwritingContractError(
            "assessment envelope fields do not match contract; "
            f"missing={sorted(ENVELOPE_KEYS - actual)}, "
            f"unknown={sorted(actual - ENVELOPE_KEYS)}"
        )
    if envelope.get("schema_version") != 3:
        raise UnderwritingContractError("assessment envelope schema_version must be 3")
    _require_text(envelope.get("assessment_id"), "assessment_id")
    if envelope.get("review_id") != expected_review_id:
        raise UnderwritingContractError("assessment review_id mismatch")
    if envelope.get("symbol") != expected_symbol:
        raise UnderwritingContractError("assessment symbol mismatch")
    if envelope.get("packet_sha256") != expected_packet_sha256:
        raise UnderwritingContractError("assessment packet_sha256 mismatch")
    cutoff = _parse_aware(envelope.get("information_cutoff"), "information_cutoff")
    if cutoff > evaluated_at:
        raise UnderwritingContractError("information_cutoff cannot be in the future")
    if not isinstance(envelope.get("assessment"), Mapping):
        raise UnderwritingContractError("assessment must be an object")
    evidence = envelope.get("evidence")
    if not isinstance(evidence, Mapping) or set(evidence) != EVIDENCE_INPUT_KEYS:
        raise UnderwritingContractError(
            "evidence fields must be ledger and share_count_bridge"
        )
    portfolio_inputs = envelope.get("portfolio_inputs")
    if (
        not isinstance(portfolio_inputs, Mapping)
        or set(portfolio_inputs) != PORTFOLIO_INPUT_KEYS
    ):
        raise UnderwritingContractError(
            "portfolio_inputs fields do not match contract"
        )


def _packet_authorities(
    packet: Mapping[str, Any],
    *,
    expected_symbol: str,
    expected_review_id: str,
) -> tuple[dict[str, str], dict[str, str]]:
    if not isinstance(packet, Mapping):
        raise UnderwritingContractError("claim packet must be an object")
    if packet.get("symbol") != expected_symbol or packet.get("review_id") != expected_review_id:
        raise UnderwritingContractError("claim packet identity mismatch")
    claims = packet.get("claims")
    sources = packet.get("allowed_sources")
    if not isinstance(claims, list) or not claims:
        raise UnderwritingContractError("claim packet must contain claims")
    if not isinstance(sources, list) or not sources:
        raise UnderwritingContractError("claim packet must contain allowed_sources")
    prior_claims: dict[str, str] = {}
    for raw in claims:
        if not isinstance(raw, Mapping):
            raise UnderwritingContractError("claim packet claim must be an object")
        claim_id = _require_text(raw.get("claim_id"), "claim_id")
        category = _require_text(raw.get("category"), "claim category")
        if claim_id in prior_claims:
            raise UnderwritingContractError(f"duplicate packet claim: {claim_id}")
        prior_claims[claim_id] = category
    allowed_sources: dict[str, str] = {}
    for raw in sources:
        if not isinstance(raw, Mapping):
            raise UnderwritingContractError("allowed source must be an object")
        source_id = _require_text(raw.get("source_id"), "source_id")
        tier = _require_text(raw.get("tier"), "source tier")
        if source_id in allowed_sources:
            raise UnderwritingContractError(
                f"duplicate packet source: {source_id}"
            )
        allowed_sources[source_id] = tier
    return prior_claims, allowed_sources


def _evaluate_evidence(
    envelope: Mapping[str, Any],
    *,
    prior_claims: Mapping[str, str],
    allowed_sources: Mapping[str, str],
    policy: Mapping[str, Any],
    evaluated_at: dt.datetime,
) -> EvidenceValidationResult:
    evidence = envelope["evidence"]
    ledger = evidence["ledger"]
    if not isinstance(ledger, list) or not ledger:
        raise UnderwritingContractError("evidence.ledger must be a non-empty array")
    market_entries = [
        item
        for item in ledger
        if isinstance(item, Mapping) and item.get("fact_type") == "market_price"
    ]
    if len(market_entries) != 1:
        raise UnderwritingContractError(
            "evidence ledger must contain exactly one market_price entry"
        )
    market_entry = market_entries[0]
    market_observed = _parse_aware(
        market_entry.get("observed_at"),
        "market price observed_at",
    )
    portfolio_inputs = envelope["portfolio_inputs"]
    price_as_of = _parse_aware(
        portfolio_inputs.get("price_as_of"),
        "portfolio_inputs.price_as_of",
    )
    if price_as_of != market_observed:
        raise UnderwritingContractError(
            "portfolio price_as_of must match market evidence observed_at"
        )
    price = _number(portfolio_inputs.get("current_price"), "current_price")
    market_value = _number(market_entry.get("value"), "market evidence value")
    if price <= 0 or abs(price - market_value) > max(1e-9, price * 1e-9):
        raise UnderwritingContractError(
            "portfolio current_price must match positive market evidence"
        )

    custom_blockers: set[str] = set()
    for raw in ledger:
        if not isinstance(raw, Mapping):
            continue
        source_id = raw.get("source_id")
        fact_type = raw.get("fact_type")
        claim_id = raw.get("claim_id")
        tier = raw.get("source_tier")
        if source_id in allowed_sources:
            if tier != allowed_sources[source_id]:
                custom_blockers.add(f"source_tier_mismatch:{source_id}")
        elif fact_type != "market_price":
            custom_blockers.add(f"evidence_source_not_allowed:{source_id}")
        if claim_id not in prior_claims and fact_type not in {
            "market_price",
            "share_count",
        }:
            custom_blockers.add(f"evidence_claim_not_frozen:{claim_id}")

    required_primary_sources = {
        source_id for source_id, tier in allowed_sources.items() if tier == "S1"
    }
    freshness = policy.get("freshness_days")
    if not isinstance(freshness, Mapping):
        raise UnderwritingContractError("underwriting policy freshness_days is missing")
    try:
        result = validate_evidence_ledger(
            ledger,
            as_of=evaluated_at,
            latest_completed_trading_day=market_observed.date(),
            required_filing_ids=required_primary_sources,
            share_count_bridge=evidence["share_count_bridge"],
            cyclical_freshness_days=int(freshness["cyclical_price_and_inventory"]),
            industry_freshness_days=int(freshness["general_industry_operating_data"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise UnderwritingContractError(f"invalid evidence ledger: {exc}") from exc

    max_price_age_days = policy.get("market_price_freshness_days")
    if (
        isinstance(max_price_age_days, bool)
        or not isinstance(max_price_age_days, int)
        or max_price_age_days < 0
    ):
        raise UnderwritingContractError(
            "underwriting policy market_price_freshness_days is invalid"
        )
    if evaluated_at - market_observed > dt.timedelta(days=max_price_age_days):
        custom_blockers.add("stale_market_price")
    blockers = tuple(sorted(set(result.blockers) | custom_blockers))
    stale_codes = {"stale_market_price", "stale_cyclical_data", "stale_industry_data"}
    return EvidenceValidationResult(
        is_valid=not blockers,
        is_stale=bool(stale_codes.intersection(blockers)),
        blockers=blockers,
        warnings=result.warnings,
    )


def _validate_portfolio_inputs(value: Mapping[str, Any]) -> None:
    _require_text(value.get("industry"), "portfolio_inputs.industry")
    clusters = value.get("economic_risk_clusters")
    if (
        not isinstance(clusters, list)
        or not clusters
        or any(not isinstance(item, str) or not item.strip() for item in clusters)
        or len(clusters) != len(set(clusters))
    ):
        raise UnderwritingContractError(
            "portfolio_inputs.economic_risk_clusters must be unique non-empty strings"
        )
    _range(value.get("reduce_zone"), "portfolio_inputs.reduce_zone")
    try:
        expected_annual_return(value.get("current_price"), value.get("return_model"))
    except PortfolioValidationError as exc:
        raise UnderwritingContractError(str(exc)) from exc
    model_as_of = _parse_aware(
        value["return_model"].get("model_as_of"),
        "return_model.model_as_of",
    )
    price_as_of = _parse_aware(value.get("price_as_of"), "price_as_of")
    if model_as_of > price_as_of:
        raise UnderwritingContractError(
            "return_model.model_as_of cannot be later than price_as_of"
        )


def _range(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise UnderwritingContractError(f"{label} must be a two-number range")
    lower = _number(value[0], f"{label}[0]")
    upper = _number(value[1], f"{label}[1]")
    if lower > upper:
        raise UnderwritingContractError(f"{label} must be ordered")
    return lower, upper


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnderwritingContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise UnderwritingContractError(f"{label} must be finite")
    return result


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnderwritingContractError(f"{label} must be a non-empty string")
    return value.strip()


def _parse_aware(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise UnderwritingContractError(f"{label} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise UnderwritingContractError(f"{label} must be an ISO datetime") from exc
    _require_aware(parsed, label)
    return parsed


def _require_aware(value: dt.datetime, label: str) -> None:
    if (
        not isinstance(value, dt.datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise UnderwritingContractError(f"{label} must include a UTC offset")
