from __future__ import annotations

import datetime as dt

import pytest

AS_OF = dt.datetime(2026, 7, 21, 8, 0, tzinfo=dt.timezone.utc)
LATEST_TRADING_DAY = dt.date(2026, 7, 20)


def _entry(
    source_id: str,
    *,
    fact_type: str,
    tier: str = "S1",
    observed_at: str = "2026-07-20T15:00:00+08:00",
    claim_role: str = "fact",
) -> dict[str, object]:
    return {
        "evidence_id": f"E-{source_id}",
        "claim_id": "C1",
        "source_id": source_id,
        "fact_type": fact_type,
        "claim_role": claim_role,
        "value": 100,
        "period": "2026-Q1",
        "original_basis": "法定披露口径",
        "adjusted_basis": "未调整",
        "source_tier": tier,
        "source_uri_or_path": f"evidence/{source_id}.pdf",
        "source_locator": "第10页",
        "observed_at": observed_at,
        "retrieved_at": "2026-07-21T07:00:00+00:00",
        "cross_checked": True,
        "review_result": "confirmed",
    }


def _valid_ledger() -> list[dict[str, object]]:
    return [
        _entry("2025-annual", fact_type="critical_financial"),
        _entry("2026-q1", fact_type="critical_financial"),
        _entry("quote", fact_type="market_price", tier="S3"),
        _entry("industry", fact_type="general_industry", tier="S2"),
        _entry("inventory", fact_type="cyclical_price_inventory", tier="S2"),
        _entry("shares", fact_type="share_count"),
    ]


def _share_bridge(*, handled: bool = True, diluted_shares: float = 105.0):
    return {
        "base_shares": 100.0,
        "events": [
            {
                "event_id": "convertible-dilution",
                "type": "convertible",
                "share_delta": 5.0,
                "handled": handled,
            }
        ],
        "diluted_shares": diluted_shares,
    }


def _validate(
    ledger: list[dict[str, object]] | None = None,
    *,
    share_bridge: dict[str, object] | None = None,
):
    from trading_os.research_assets.evidence import validate_evidence_ledger

    return validate_evidence_ledger(
        ledger or _valid_ledger(),
        as_of=AS_OF,
        latest_completed_trading_day=LATEST_TRADING_DAY,
        required_filing_ids={"2025-annual", "2026-q1"},
        share_count_bridge=share_bridge or _share_bridge(),
        cyclical_freshness_days=30,
        industry_freshness_days=90,
    )


def test_valid_evidence_ledger_passes_all_gates():
    result = _validate()

    assert result.is_valid is True
    assert result.is_stale is False
    assert result.blockers == ()


def test_critical_financial_fact_requires_s1_source():
    ledger = _valid_ledger()
    ledger[0]["source_tier"] = "S3"

    result = _validate(ledger)

    assert "critical_financial_not_s1" in result.blockers


def test_s4_cannot_support_a_purchase_reason():
    ledger = _valid_ledger()
    ledger.append(
        _entry(
            "rumour",
            fact_type="other",
            tier="S4",
            claim_role="purchase_reason",
        )
    )

    result = _validate(ledger)

    assert "purchase_reason_relies_on_s4" in result.blockers


def test_quote_must_match_latest_completed_trading_day():
    ledger = _valid_ledger()
    ledger[2]["observed_at"] = "2026-07-17T15:00:00+08:00"

    result = _validate(ledger)

    assert result.is_stale is True
    assert "stale_market_price" in result.blockers


@pytest.mark.parametrize(
    ("fact_type", "observed_at", "code"),
    [
        ("cyclical_price_inventory", "2026-06-01T00:00:00+08:00", "stale_cyclical_data"),
        ("general_industry", "2026-03-01T00:00:00+08:00", "stale_industry_data"),
    ],
)
def test_industry_freshness_windows_are_enforced(
    fact_type: str, observed_at: str, code: str
):
    ledger = _valid_ledger()
    target = next(item for item in ledger if item["fact_type"] == fact_type)
    target["observed_at"] = observed_at

    result = _validate(ledger)

    assert result.is_stale is True
    assert code in result.blockers


def test_all_required_filings_must_be_present():
    ledger = [item for item in _valid_ledger() if item["source_id"] != "2026-q1"]

    result = _validate(ledger)

    assert "missing_required_filing:2026-q1" in result.blockers


def test_unhandled_share_event_blocks_per_share_valuation():
    result = _validate(share_bridge=_share_bridge(handled=False))

    assert "unhandled_share_event:convertible-dilution" in result.blockers


def test_diluted_share_count_must_reconcile_to_event_bridge():
    result = _validate(share_bridge=_share_bridge(diluted_shares=100.0))

    assert "share_count_bridge_does_not_reconcile" in result.blockers


def test_missing_share_count_bridge_is_blocking():
    from trading_os.research_assets.evidence import validate_evidence_ledger

    result = validate_evidence_ledger(
        _valid_ledger(),
        as_of=AS_OF,
        latest_completed_trading_day=LATEST_TRADING_DAY,
        required_filing_ids={"2025-annual", "2026-q1"},
        share_count_bridge=None,
    )

    assert "missing_share_count_bridge" in result.blockers


def test_observed_and_retrieved_times_cannot_be_in_the_future():
    ledger = _valid_ledger()
    ledger[0]["retrieved_at"] = "2026-07-22T00:00:00+00:00"

    result = _validate(ledger)

    assert "future_evidence_timestamp" in result.blockers


def test_invalid_evidence_shape_raises_instead_of_silently_dropping():
    from trading_os.research_assets.evidence import EvidenceValidationError

    ledger = _valid_ledger()
    del ledger[0]["source_locator"]

    with pytest.raises(EvidenceValidationError, match="fields"):
        _validate(ledger)
