from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


def canonical_company_name(value: str) -> str:
    """Normalize presentation-only whitespace without changing identity characters."""

    return " ".join(value.split())


class ReportType(str, Enum):
    RAPID_TRIAGE = "rapid_triage"
    INITIAL_RESEARCH = "initial_research"
    MONITORING_UPDATE = "monitoring_update"
    UNDERWRITING_REVIEW = "underwriting_review"
    CHALLENGER_REVIEW = "challenger_review"


class UnderwritingStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NEEDS_CHALLENGER = "needs_challenger"
    STALE = "stale"


class PortfolioAction(str, Enum):
    BUY_NOW = "buy_now"
    BUY_ON_WEAKNESS = "buy_on_weakness"
    HOLD = "hold"
    REDUCE = "reduce"
    EXIT = "exit"
    WATCH = "watch"
    REJECT = "reject"


class SourceTier(str, Enum):
    PRIMARY = "S1"
    AUTHORITATIVE_INDUSTRY = "S2"
    PROFESSIONAL_SECONDARY = "S3"
    LEAD_ONLY = "S4"


class ClaimReviewStatus(str, Enum):
    CONFIRMED = "confirmed"
    WEAKENED = "weakened"
    DISPROVEN = "disproven"
    UNTESTED = "untested"


class ReviewRunStatus(str, Enum):
    CREATED = "created"
    CANDIDATES_FROZEN = "candidates_frozen"
    PACKETS_READY = "packets_ready"
    BLIND_REVIEWING = "blind_reviewing"
    BLIND_SEALED = "blind_sealed"
    REVEALING = "revealing"
    CHALLENGING = "challenging"
    COMPANY_REVIEWS_COMPLETE = "company_reviews_complete"
    PORTFOLIO_CHALLENGING = "portfolio_challenging"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"
    FAILED_AGENT = "failed_agent"
    FAILED_VALIDATION = "failed_validation"
    STALE_QUOTES = "stale_quotes"
    CANCELLED = "cancelled"


class PolicyKind(str, Enum):
    UNDERWRITING = "underwriting"
    PORTFOLIO = "portfolio"
    INDUSTRY = "industry"
    RESEARCH_ALLOCATION = "research_allocation"
    TRIAGE_QUALITY_AUDIT = "triage_quality_audit"
    MANAGER_SCREENING = "manager_screening"


class PolicyValidationError(ValueError):
    """Raised when a versioned research policy is malformed."""


@dataclass(frozen=True, slots=True)
class Policy:
    schema_version: int
    policy_id: str
    version: str
    effective_at: dt.datetime
    kind: PolicyKind
    payload: Mapping[str, Any]


_POLICY_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "effective_at",
    "kind",
    "payload",
}
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def load_policy(path: str | Path) -> Policy:
    policy_path = Path(path)
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise PolicyValidationError(f"invalid JSON in policy {policy_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PolicyValidationError("policy must be a JSON object")
    return validate_policy(raw)


def validate_policy(raw: Mapping[str, Any]) -> Policy:
    keys = set(raw)
    unknown = sorted(keys - _POLICY_KEYS)
    if unknown:
        raise PolicyValidationError(f"unknown top-level policy fields: {unknown}")
    missing = sorted(_POLICY_KEYS - keys)
    if missing:
        raise PolicyValidationError(f"missing required policy fields: {missing}")

    schema_version = raw["schema_version"]
    if isinstance(schema_version, bool) or schema_version != 2:
        raise PolicyValidationError("schema_version must be integer 2")

    policy_id = _non_empty_string(raw["policy_id"], "policy_id")
    version = _non_empty_string(raw["version"], "version")
    if not _SEMVER_RE.fullmatch(version):
        raise PolicyValidationError("version must use MAJOR.MINOR.PATCH")

    effective_text = _non_empty_string(raw["effective_at"], "effective_at")
    try:
        effective_at = dt.datetime.fromisoformat(effective_text)
    except ValueError as exc:
        raise PolicyValidationError("effective_at must be an ISO 8601 datetime") from exc
    if effective_at.tzinfo is None or effective_at.utcoffset() is None:
        raise PolicyValidationError("effective_at must include a UTC offset")

    kind_text = _non_empty_string(raw["kind"], "kind")
    try:
        kind = PolicyKind(kind_text)
    except ValueError as exc:
        raise PolicyValidationError(f"unsupported policy kind: {kind_text}") from exc

    payload = raw["payload"]
    if not isinstance(payload, dict) or not payload:
        raise PolicyValidationError("payload must be a non-empty object")

    return Policy(
        schema_version=2,
        policy_id=policy_id,
        version=version,
        effective_at=effective_at,
        kind=kind,
        payload=MappingProxyType(dict(payload)),
    )


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyValidationError(f"{field} must be a non-empty string")
    return value.strip()
