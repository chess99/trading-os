from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Mapping

from .models import ClaimReviewStatus, SourceTier


class EvidenceValidationError(ValueError):
    """Raised when an evidence ledger or share-count bridge is malformed."""


@dataclass(frozen=True, slots=True)
class EvidenceValidationResult:
    is_valid: bool
    is_stale: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


EVIDENCE_KEYS = {
    "evidence_id",
    "claim_id",
    "source_id",
    "fact_type",
    "claim_role",
    "value",
    "period",
    "original_basis",
    "adjusted_basis",
    "source_tier",
    "source_uri_or_path",
    "source_locator",
    "observed_at",
    "retrieved_at",
    "cross_checked",
    "review_result",
}
FACT_TYPES = {
    "critical_financial",
    "market_price",
    "general_industry",
    "cyclical_price_inventory",
    "share_count",
    "governance",
    "other",
}
CLAIM_ROLES = {"fact", "purchase_reason", "risk", "context"}
SHARE_BRIDGE_KEYS = {"base_shares", "events", "diluted_shares"}
SHARE_EVENT_KEYS = {"event_id", "type", "share_delta", "handled"}
SHARE_EVENT_TYPES = {"issuance", "repurchase", "convertible", "split", "option"}


def validate_evidence_ledger(
    ledger: list[Mapping[str, Any]],
    *,
    as_of: dt.datetime,
    latest_completed_trading_day: dt.date,
    required_filing_ids: set[str],
    share_count_bridge: Mapping[str, Any] | None,
    cyclical_freshness_days: int = 30,
    industry_freshness_days: int = 90,
) -> EvidenceValidationResult:
    _require_aware(as_of, "as_of")
    if not isinstance(latest_completed_trading_day, dt.date):
        raise EvidenceValidationError("latest_completed_trading_day must be a date")
    if not isinstance(ledger, list) or not ledger:
        raise EvidenceValidationError("evidence ledger must be a non-empty array")
    if not isinstance(required_filing_ids, set):
        raise EvidenceValidationError("required_filing_ids must be a set")
    _require_nonnegative_int(cyclical_freshness_days, "cyclical_freshness_days")
    _require_nonnegative_int(industry_freshness_days, "industry_freshness_days")

    blockers: set[str] = set()
    warnings: set[str] = set()
    source_ids: set[str] = set()
    evidence_ids: set[str] = set()
    market_price_count = 0
    allowed_tiers = {item.value for item in SourceTier}
    review_results = {item.value for item in ClaimReviewStatus}

    for index, raw_entry in enumerate(ledger):
        if not isinstance(raw_entry, Mapping):
            raise EvidenceValidationError(f"evidence entry {index} must be an object")
        entry = raw_entry
        _require_exact_keys(entry, EVIDENCE_KEYS, f"evidence entry {index}")
        evidence_id = _require_text(entry.get("evidence_id"), "evidence_id")
        if evidence_id in evidence_ids:
            raise EvidenceValidationError(f"duplicate evidence_id: {evidence_id}")
        evidence_ids.add(evidence_id)
        _require_text(entry.get("claim_id"), "claim_id")
        source_id = _require_text(entry.get("source_id"), "source_id")
        source_ids.add(source_id)
        fact_type = _require_text(entry.get("fact_type"), "fact_type")
        if fact_type not in FACT_TYPES:
            raise EvidenceValidationError(f"unsupported fact_type: {fact_type}")
        claim_role = _require_text(entry.get("claim_role"), "claim_role")
        if claim_role not in CLAIM_ROLES:
            raise EvidenceValidationError(f"unsupported claim_role: {claim_role}")
        tier = _require_text(entry.get("source_tier"), "source_tier")
        if tier not in allowed_tiers:
            raise EvidenceValidationError(f"unsupported source_tier: {tier}")
        _require_text(entry.get("period"), "period")
        _require_text(entry.get("original_basis"), "original_basis")
        _require_text(entry.get("adjusted_basis"), "adjusted_basis")
        _require_text(entry.get("source_uri_or_path"), "source_uri_or_path")
        _require_text(entry.get("source_locator"), "source_locator")
        if not isinstance(entry.get("cross_checked"), bool):
            raise EvidenceValidationError("cross_checked must be boolean")
        review_result = _require_text(entry.get("review_result"), "review_result")
        if review_result not in review_results:
            raise EvidenceValidationError(f"unsupported review_result: {review_result}")
        observed_at = _parse_datetime(entry.get("observed_at"), "observed_at")
        retrieved_at = _parse_datetime(entry.get("retrieved_at"), "retrieved_at")
        if observed_at > as_of or retrieved_at > as_of:
            blockers.add("future_evidence_timestamp")
        if fact_type == "critical_financial" and tier != SourceTier.PRIMARY.value:
            blockers.add("critical_financial_not_s1")
        if claim_role == "purchase_reason" and tier == SourceTier.LEAD_ONLY.value:
            blockers.add("purchase_reason_relies_on_s4")
        if fact_type == "market_price":
            market_price_count += 1
            if observed_at.date() != latest_completed_trading_day:
                blockers.add("stale_market_price")
        age = as_of.astimezone(dt.timezone.utc) - observed_at.astimezone(dt.timezone.utc)
        if (
            fact_type == "cyclical_price_inventory"
            and age > dt.timedelta(days=cyclical_freshness_days)
        ):
            blockers.add("stale_cyclical_data")
        if (
            fact_type == "general_industry"
            and age > dt.timedelta(days=industry_freshness_days)
        ):
            blockers.add("stale_industry_data")
        if not entry["cross_checked"] and claim_role == "purchase_reason":
            warnings.add(f"purchase_reason_not_cross_checked:{evidence_id}")

    if market_price_count == 0:
        blockers.add("missing_market_price")
    for filing_id in sorted(required_filing_ids - source_ids):
        blockers.add(f"missing_required_filing:{filing_id}")
    _validate_share_count_bridge(share_count_bridge, blockers)
    ordered_blockers = tuple(sorted(blockers))
    stale_codes = {"stale_market_price", "stale_cyclical_data", "stale_industry_data"}
    return EvidenceValidationResult(
        is_valid=not ordered_blockers,
        is_stale=bool(stale_codes.intersection(blockers)),
        blockers=ordered_blockers,
        warnings=tuple(sorted(warnings)),
    )


def _validate_share_count_bridge(
    bridge: Mapping[str, Any] | None, blockers: set[str]
) -> None:
    if bridge is None:
        blockers.add("missing_share_count_bridge")
        return
    if not isinstance(bridge, Mapping):
        raise EvidenceValidationError("share_count_bridge must be an object")
    _require_exact_keys(bridge, SHARE_BRIDGE_KEYS, "share_count_bridge")
    base = _require_number(bridge.get("base_shares"), "base_shares")
    diluted = _require_number(bridge.get("diluted_shares"), "diluted_shares")
    if base <= 0 or diluted <= 0:
        raise EvidenceValidationError("share counts must be positive")
    events = bridge.get("events")
    if not isinstance(events, list):
        raise EvidenceValidationError("share_count_bridge.events must be an array")
    expected = base
    seen: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise EvidenceValidationError(f"share event {index} must be an object")
        _require_exact_keys(event, SHARE_EVENT_KEYS, f"share event {index}")
        event_id = _require_text(event.get("event_id"), "share event_id")
        if event_id in seen:
            raise EvidenceValidationError(f"duplicate share event_id: {event_id}")
        seen.add(event_id)
        event_type = _require_text(event.get("type"), "share event type")
        if event_type not in SHARE_EVENT_TYPES:
            raise EvidenceValidationError(f"unsupported share event type: {event_type}")
        delta = _require_number(event.get("share_delta"), "share_delta")
        handled = event.get("handled")
        if not isinstance(handled, bool):
            raise EvidenceValidationError("share event handled must be boolean")
        if not handled:
            blockers.add(f"unhandled_share_event:{event_id}")
        expected += delta
    tolerance = max(1e-9, abs(expected) * 1e-9)
    if abs(expected - diluted) > tolerance:
        blockers.add("share_count_bridge_does_not_reconcile")


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    keys = set(value)
    if keys != expected:
        raise EvidenceValidationError(
            f"{label} fields do not match contract; "
            f"missing={sorted(expected - keys)}, unknown={sorted(keys - expected)}"
        )


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _require_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceValidationError(f"{label} must be numeric")
    return float(value)


def _require_nonnegative_int(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceValidationError(f"{label} must be a non-negative integer")


def _require_aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceValidationError(f"{label} must include timezone information")


def _parse_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise EvidenceValidationError(f"{label} must be an ISO datetime")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise EvidenceValidationError(f"{label} must be an ISO datetime") from exc
    _require_aware(parsed, label)
    return parsed
