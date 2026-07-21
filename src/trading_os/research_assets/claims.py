from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .models import SourceTier


class ClaimPacketError(ValueError):
    """Raised when structured claims cannot be safely projected into a blind packet."""


@dataclass(frozen=True, slots=True)
class LeakFinding:
    kind: str
    location: str
    detail: str


RESEARCH_KEYS = {"schema_version", "report_id", "symbol", "claims", "sources", "decision"}
CLAIM_KEYS = {
    "claim_id",
    "category",
    "claim",
    "verification_metrics",
    "falsifiers",
    "source_ids",
}
SOURCE_KEYS = {"source_id", "tier", "uri_or_path"}
DECISION_KEYS = {
    "rating",
    "fair_value_range",
    "buy_zone",
    "reduce_zone",
    "conclusion",
}
CLAIM_CATEGORIES = {"fact", "business", "industry", "investment"}
SYMBOL_RE = re.compile(r"^(CN|HK|US):[A-Z0-9.]+$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.])(-?[0-9]+(?:\.[0-9]+)?)(\s*%)?")
DECISION_LANGUAGE_RE = re.compile(
    r"买入|卖出|减持|回避|强烈推荐|推荐|合理价|目标价|仓位|评级|"
    r"\b(?:buy|sell|avoid|rating|recommend(?:ation)?|position)\b|"
    r"\b(?:fair\s+value|target\s+price)\b",
    re.IGNORECASE,
)
FORBIDDEN_FIELD_FRAGMENTS = {
    "decision",
    "rating",
    "fair_value",
    "target_price",
    "buy_zone",
    "reduce_zone",
    "position_plan",
    "weight",
    "conclusion",
    "recommendation",
    "action",
}


def build_claim_packet(
    research_claims: Mapping[str, Any],
    *,
    review_id: str,
    packet_id: str,
    source_report_sha256: str,
    created_at: dt.datetime,
) -> dict[str, Any]:
    if not isinstance(research_claims, Mapping):
        raise ClaimPacketError("research claims must be an object")
    _require_exact_keys(research_claims, RESEARCH_KEYS, "research claims")
    if research_claims.get("schema_version") != 2:
        raise ClaimPacketError("research claims schema_version must be 2")
    review_id = _require_text(review_id, "review_id")
    packet_id = _require_text(packet_id, "packet_id")
    report_id = _require_text(research_claims.get("report_id"), "report_id")
    del report_id  # validated for traceability; source hash is the blind packet reference.
    symbol = _require_text(research_claims.get("symbol"), "symbol")
    if not SYMBOL_RE.fullmatch(symbol):
        raise ClaimPacketError(f"invalid symbol: {symbol}")
    if not isinstance(source_report_sha256, str) or not SHA256_RE.fullmatch(
        source_report_sha256
    ):
        raise ClaimPacketError("source_report_sha256 must be a lowercase SHA-256 digest")
    _require_aware(created_at, "created_at")

    sources = _normalize_sources(research_claims.get("sources"))
    source_ids = {source["source_id"] for source in sources}
    claims = _normalize_claims(research_claims.get("claims"), source_ids)
    decision = research_claims.get("decision")
    if not isinstance(decision, Mapping):
        raise ClaimPacketError("decision must be an object")
    _validate_decision(decision)

    packet = {
        "schema_version": 2,
        "packet_id": packet_id,
        "review_id": review_id,
        "symbol": symbol,
        "source_report_sha256": source_report_sha256,
        "claims": claims,
        "allowed_sources": sources,
        "created_at": created_at.isoformat(),
    }
    findings = scan_claim_packet_for_leaks(packet, decision)
    if findings:
        kinds = sorted({finding.kind for finding in findings})
        raise ClaimPacketError(f"claim packet decision leak detected: {kinds}")
    return packet


def scan_claim_packet_for_leaks(
    packet: Mapping[str, Any], decision: Mapping[str, Any]
) -> list[LeakFinding]:
    findings: list[LeakFinding] = []
    decision_values = _decision_numeric_values(decision)
    for location, key, value in _walk(packet):
        normalized_key = key.lower()
        if any(fragment in normalized_key for fragment in FORBIDDEN_FIELD_FRAGMENTS):
            findings.append(
                LeakFinding(
                    kind="forbidden_field",
                    location=location,
                    detail=f"field name leaks decision semantics: {key}",
                )
            )
        if isinstance(value, str):
            if DECISION_LANGUAGE_RE.search(value):
                findings.append(
                    LeakFinding(
                        kind="decision_language",
                        location=location,
                        detail="text contains rating, action, valuation, or position language",
                    )
                )
            if _text_contains_decision_value(value, decision_values):
                findings.append(
                    LeakFinding(
                        kind="decision_value",
                        location=location,
                        detail="text contains a numeric decision answer",
                    )
                )
        elif _is_number(value) and _matches_any(float(value), decision_values):
            findings.append(
                LeakFinding(
                    kind="decision_value",
                    location=location,
                    detail="numeric field contains a decision answer",
                )
            )
    return _deduplicate_findings(findings)


def _normalize_claims(raw: Any, valid_source_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ClaimPacketError("claims must be a non-empty array")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, claim in enumerate(raw):
        if not isinstance(claim, Mapping):
            raise ClaimPacketError(f"claim {index} must be an object")
        _require_exact_keys(claim, CLAIM_KEYS, f"claim {index}")
        claim_id = _require_text(claim.get("claim_id"), f"claim {index} claim_id")
        if claim_id in seen:
            raise ClaimPacketError(f"duplicate claim_id: {claim_id}")
        seen.add(claim_id)
        category = _require_text(claim.get("category"), f"claim {index} category")
        if category not in CLAIM_CATEGORIES:
            raise ClaimPacketError(f"unsupported claim category: {category}")
        source_ids = _require_text_array(claim.get("source_ids"), "source_ids")
        for source_id in source_ids:
            if source_id not in valid_source_ids:
                raise ClaimPacketError(
                    f"claim {claim_id} references unknown source: {source_id}"
                )
        normalized.append(
            {
                "claim_id": claim_id,
                "category": category,
                "claim": _require_text(claim.get("claim"), f"claim {claim_id}"),
                "verification_metrics": _require_text_array(
                    claim.get("verification_metrics"), "verification_metrics"
                ),
                "falsifiers": _require_text_array(
                    claim.get("falsifiers"), "falsifiers"
                ),
                "source_ids": source_ids,
            }
        )
    return sorted(normalized, key=lambda item: item["claim_id"])


def _normalize_sources(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ClaimPacketError("sources must be a non-empty array")
    tiers = {tier.value for tier in SourceTier}
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, source in enumerate(raw):
        if not isinstance(source, Mapping):
            raise ClaimPacketError(f"source {index} must be an object")
        _require_exact_keys(source, SOURCE_KEYS, f"source {index}")
        source_id = _require_text(source.get("source_id"), f"source {index} source_id")
        if source_id in seen:
            raise ClaimPacketError(f"duplicate source_id: {source_id}")
        seen.add(source_id)
        tier = _require_text(source.get("tier"), f"source {source_id} tier")
        if tier not in tiers:
            raise ClaimPacketError(f"source {source_id} has unsupported tier: {tier}")
        normalized.append(
            {
                "source_id": source_id,
                "tier": tier,
                "uri_or_path": _require_text(
                    source.get("uri_or_path"), f"source {source_id} uri_or_path"
                ),
            }
        )
    return sorted(normalized, key=lambda item: item["source_id"])


def _validate_decision(decision: Mapping[str, Any]) -> None:
    _require_exact_keys(decision, DECISION_KEYS, "decision")
    _require_text(decision.get("rating"), "decision.rating")
    _require_text(decision.get("conclusion"), "decision.conclusion")
    for field in ("fair_value_range", "buy_zone", "reduce_zone"):
        value = decision.get(field)
        if not isinstance(value, list) or len(value) != 2:
            raise ClaimPacketError(f"decision.{field} must be a two-number range")
        lower = _require_number(value[0], f"decision.{field}[0]")
        upper = _require_number(value[1], f"decision.{field}[1]")
        if lower > upper:
            raise ClaimPacketError(f"decision.{field} must be ordered")
def _decision_numeric_values(decision: Mapping[str, Any]) -> set[float]:
    values: set[float] = set()

    def collect(value: Any) -> None:
        if _is_number(value):
            values.add(float(value))
        elif isinstance(value, Mapping):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    collect(decision)
    return values


def _walk(value: Any, location: str = "$"):
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            child = f"{location}.{key_text}"
            yield child, key_text, nested
            yield from _walk(nested, child)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            child = f"{location}[{index}]"
            yield child, str(index), nested
            yield from _walk(nested, child)


def _text_contains_decision_value(text: str, decision_values: set[float]) -> bool:
    for match in NUMBER_RE.finditer(text):
        value = float(match.group(1))
        if match.group(2):
            value /= 100.0
        if _matches_any(value, decision_values):
            return True
    return False


def _matches_any(value: float, candidates: set[float]) -> bool:
    return any(abs(value - candidate) <= 1e-9 for candidate in candidates)


def _deduplicate_findings(findings: list[LeakFinding]) -> list[LeakFinding]:
    unique: dict[tuple[str, str], LeakFinding] = {}
    for finding in findings:
        unique[(finding.kind, finding.location)] = finding
    return [unique[key] for key in sorted(unique)]


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    keys = set(value)
    if keys != expected:
        missing = sorted(expected - keys)
        unknown = sorted(keys - expected)
        raise ClaimPacketError(
            f"{label} fields do not match contract; missing={missing}, unknown={unknown}"
        )


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClaimPacketError(f"{label} must be a non-empty string")
    return value.strip()


def _require_text_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ClaimPacketError(f"{label} must be a non-empty string array")
    result = [_require_text(item, label) for item in value]
    if len(result) != len(set(result)):
        raise ClaimPacketError(f"{label} must not contain duplicates")
    return result


def _require_number(value: Any, label: str) -> float:
    if not _is_number(value):
        raise ClaimPacketError(f"{label} must be numeric")
    return float(value)


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _require_aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ClaimPacketError(f"{label} must include timezone information")
