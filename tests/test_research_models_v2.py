from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_domain_enums_are_closed_and_match_the_design():
    from trading_os.research_assets.models import (
        ClaimReviewStatus,
        PortfolioAction,
        PolicyKind,
        ReportType,
        ReviewRunStatus,
        SourceTier,
        UnderwritingStatus,
    )

    assert {item.value for item in ReportType} == {
        "initial_research",
        "monitoring_update",
        "underwriting_review",
        "challenger_review",
    }
    assert {item.value for item in UnderwritingStatus} == {
        "passed",
        "failed",
        "insufficient_evidence",
        "needs_challenger",
        "stale",
    }
    assert {item.value for item in PortfolioAction} == {
        "buy_now",
        "buy_on_weakness",
        "hold",
        "reduce",
        "exit",
        "watch",
        "reject",
    }
    assert {item.value for item in SourceTier} == {"S1", "S2", "S3", "S4"}
    assert {item.value for item in ClaimReviewStatus} == {
        "confirmed",
        "weakened",
        "disproven",
        "untested",
    }
    assert {item.value for item in PolicyKind} == {
        "underwriting",
        "portfolio",
        "industry",
        "research_allocation",
    }
    assert {item.value for item in ReviewRunStatus} == {
        "created",
        "candidates_frozen",
        "packets_ready",
        "blind_reviewing",
        "blind_sealed",
        "revealing",
        "challenging",
        "company_reviews_complete",
        "synthesizing",
        "completed",
        "blocked_missing_evidence",
        "failed_agent",
        "failed_validation",
        "stale_quotes",
        "cancelled",
    }


@pytest.mark.parametrize(
    "relative_path",
    [
        "templates/company-meta-v2.schema.json",
        "templates/review-run.schema.json",
        "templates/claim-packet.schema.json",
        "templates/blind-assessment.schema.json",
        "templates/portfolio.schema.json",
        "templates/quick-profile.schema.json",
        "templates/research-allocation.schema.json",
    ],
)
def test_v2_schemas_are_closed_json_objects(relative_path: str):
    payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))

    assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert payload["type"] == "object"
    assert payload["additionalProperties"] is False
    assert payload["required"]


@pytest.mark.parametrize(
    "relative_path",
    [
        "policies/underwriting.json",
        "policies/portfolio.json",
        "policies/research-allocation.json",
        "policies/industries/memory.json",
        "policies/industries/manufacturing.json",
        "policies/industries/software.json",
        "policies/industries/banking.json",
        "policies/industries/insurance.json",
        "policies/industries/resources.json",
    ],
)
def test_policy_files_have_versioned_closed_metadata(relative_path: str):
    from trading_os.research_assets.models import load_policy

    policy = load_policy(ROOT / relative_path)

    assert policy.schema_version == 2
    assert policy.policy_id
    assert policy.version
    if relative_path == "policies/research-allocation.json":
        expected_effective_at = "2026-07-25T00:00:00+08:00"
    elif relative_path in {"policies/underwriting.json", "policies/portfolio.json"}:
        expected_effective_at = "2026-07-23T00:00:00+08:00"
    else:
        expected_effective_at = "2026-07-21T00:00:00+08:00"
    assert policy.effective_at.isoformat() == expected_effective_at
    assert policy.payload


def test_portfolio_policy_matches_confirmed_default_limits():
    from trading_os.research_assets.models import load_policy

    policy = load_policy(ROOT / "policies" / "portfolio.json")

    assert policy.payload["max_single_name_weight"] == 0.05
    assert policy.payload["max_industry_weight"] == 0.20
    assert policy.payload["max_economic_risk_cluster_weight"] == 0.25
    assert policy.payload["max_top_five_weight"] == 0.25
    assert policy.payload["max_medium_confidence_weight"] == 0.03
    assert policy.payload["max_low_confidence_weight"] == 0.0
    assert policy.payload["initial_entry_fraction"] == pytest.approx(1 / 3)
    assert policy.payload["minimum_expected_annual_return"] == 0.12
    assert policy.payload["near_miss_expected_annual_return"] == 0.10


def test_underwriting_policy_uses_risk_tiers_without_repeated_charges():
    from trading_os.research_assets.models import load_policy

    policy = load_policy(ROOT / "policies" / "underwriting.json")

    assert policy.payload["minimum_safety_margin"] == {
        "high_confidence": 0.10,
        "medium_confidence": 0.15,
        "low_confidence": None,
    }
    assert policy.payload["risk_overlay_safety_margin"] == {
        "elevated": 0.20,
        "severe": 0.25,
    }
    assert "cannot be cured by a lower price" in policy.payload[
        "evidence_gap_principle"
    ]


def test_research_allocation_policy_reserves_capacity_before_deep_research():
    from trading_os.research_assets.models import load_policy

    policy = load_policy(ROOT / "policies" / "research-allocation.json")
    payload = policy.payload

    assert payload["quick_profile_capacity_per_cycle"] == 200
    assert sum(payload["selection_slots"].values()) == 200
    assert payload["selection_slots"]["crisis_mispricing"] == 30
    assert payload["selection_slots"]["false_negative_audit"] == 10
    assert payload["stage_capacity_per_cycle"] == {
        "scoped_research": 60,
        "deep_research": 24,
        "underwriting": 8,
    }


def test_policy_rejects_unknown_top_level_fields(tmp_path: Path):
    from trading_os.research_assets.models import PolicyValidationError, load_policy

    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "policy_id": "bad",
                "version": "1.0.0",
                "effective_at": "2026-07-21T00:00:00+08:00",
                "kind": "underwriting",
                "payload": {"enabled": True},
                "surprise": "must fail",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PolicyValidationError, match="unknown top-level"):
        load_policy(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 1),
        ("policy_id", ""),
        ("version", "latest"),
        ("effective_at", "2026-07-21"),
        ("kind", "unknown"),
        ("payload", {}),
    ],
)
def test_policy_rejects_invalid_required_values(
    tmp_path: Path, field: str, value: object
):
    from trading_os.research_assets.models import PolicyValidationError, load_policy

    payload = {
        "schema_version": 2,
        "policy_id": "underwriting.default",
        "version": "1.0.0",
        "effective_at": "2026-07-21T00:00:00+08:00",
        "kind": "underwriting",
        "payload": {"enabled": True},
    }
    payload[field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PolicyValidationError):
        load_policy(path)
