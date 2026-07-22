from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

CREATED_AT = dt.datetime(2026, 7, 21, 8, 0, tzinfo=dt.timezone.utc)
SOURCE_HASH = "a" * 64


def _research_claims() -> dict[str, object]:
    return {
        "schema_version": 2,
        "report_id": "CN-000021-2026-07-21-initial",
        "symbol": "CN:000021",
        "claims": [
            {
                "claim_id": "C1",
                "category": "business",
                "claim": "公司存储封测收入受益于客户需求恢复。",
                "verification_metrics": ["存储业务收入", "产能利用率"],
                "falsifiers": ["存储收入连续两个季度同比下降"],
                "source_ids": ["S1-annual"],
            },
            {
                "claim_id": "C2",
                "category": "fact",
                "claim": "最新年度经营现金流需要与扣非利润交叉核验。",
                "verification_metrics": ["经营现金流", "扣非归母净利润"],
                "falsifiers": ["现金流背离无法由营运资本解释"],
                "source_ids": ["S1-annual"],
            },
        ],
        "sources": [
            {
                "source_id": "S1-annual",
                "tier": "S1",
                "uri_or_path": "evidence/2025-annual-report.pdf",
            }
        ],
        "decision": {
            "rating": "buy",
            "fair_value_range": [31.5, 38.0],
            "buy_zone": [24.0, 27.0],
            "reduce_zone": [40.0, 45.0],
            "conclusion": "估值进入安全边际后可以买入。",
        },
    }


def _build(payload: dict[str, object] | None = None) -> dict[str, object]:
    from trading_os.research_assets.claims import build_claim_packet

    return build_claim_packet(
        payload or _research_claims(),
        review_id="review-memory-001",
        packet_id="packet-CN-000021",
        source_report_sha256=SOURCE_HASH,
        created_at=CREATED_AT,
    )


def test_claim_packet_is_a_deterministic_decision_free_projection():
    packet = _build()

    assert packet == _build()
    assert set(packet) == {
        "schema_version",
        "packet_id",
        "review_id",
        "symbol",
        "source_report_sha256",
        "claims",
        "allowed_sources",
        "created_at",
    }
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in [
        "decision",
        "rating",
        "fair_value_range",
        "buy_zone",
        "reduce_zone",
        "position_plan",
        "31.5",
        "38.0",
        "24.0",
        "27.0",
        "0.05",
    ]:
        assert forbidden not in serialized


def test_claim_packet_keeps_only_verifiable_claim_fields():
    packet = _build()

    assert packet["claims"][0] == {
        "claim_id": "C1",
        "category": "business",
        "claim": "公司存储封测收入受益于客户需求恢复。",
        "verification_metrics": ["存储业务收入", "产能利用率"],
        "falsifiers": ["存储收入连续两个季度同比下降"],
        "source_ids": ["S1-annual"],
    }
    assert packet["allowed_sources"] == [
        {
            "source_id": "S1-annual",
            "tier": "S1",
            "uri_or_path": "evidence/2025-annual-report.pdf",
        }
    ]


def test_operating_numbers_are_allowed_when_they_are_not_decision_answers():
    payload = _research_claims()
    payload["claims"][0]["claim"] = "公司规划新增12万片产能，需要核验投产节奏。"

    packet = _build(payload)

    assert "12万片" in packet["claims"][0]["claim"]


def test_source_uri_numeric_identifiers_do_not_count_as_decision_leaks():
    payload = _research_claims()
    payload["sources"][0]["uri_or_path"] = (
        "https://example.com/filings/31.5/report-38-24-27.pdf"
    )

    packet = _build(payload)

    assert packet["allowed_sources"][0]["uri_or_path"].endswith(
        "report-38-24-27.pdf"
    )


def test_workflow_metadata_numeric_identifiers_do_not_count_as_decision_leaks():
    from trading_os.research_assets.claims import build_claim_packet

    packet = build_claim_packet(
        _research_claims(),
        review_id="review-2026-07-31.5",
        packet_id="packet-2026-07-31.5",
        source_report_sha256=SOURCE_HASH,
        created_at=CREATED_AT,
    )

    assert packet["review_id"] == "review-2026-07-31.5"
    assert packet["packet_id"] == "packet-2026-07-31.5"


def test_credit_rating_language_is_not_treated_as_an_investment_rating():
    payload = _research_claims()
    payload["claims"][0]["falsifiers"] = ["发行人信用评级下调会提高融资成本"]

    packet = _build(payload)

    assert "信用评级" in packet["claims"][0]["falsifiers"][0]


@pytest.mark.parametrize(
    "leaking_claim",
    [
        "旧报告给出的合理价是31.5元。",
        "股价低于27元即可买入。",
        "建议仓位上限为5%。",
        "评级为buy。",
        "结论是强烈推荐。",
    ],
)
def test_free_text_decision_leakage_blocks_packet_creation(leaking_claim: str):
    from trading_os.research_assets.claims import ClaimPacketError

    payload = _research_claims()
    payload["claims"][0]["claim"] = leaking_claim

    with pytest.raises(ClaimPacketError, match="leak"):
        _build(payload)


def test_manual_packet_leak_scanner_detects_forbidden_fields_and_values():
    from trading_os.research_assets.claims import scan_claim_packet_for_leaks

    payload = _research_claims()
    packet = _build()
    packet["old_rating"] = "buy"
    packet["claims"][0]["claim"] = "目标价38元"

    findings = scan_claim_packet_for_leaks(packet, payload["decision"])

    assert {finding.kind for finding in findings} == {
        "forbidden_field",
        "decision_language",
        "decision_value",
    }


def test_unknown_research_claims_top_level_field_is_rejected():
    from trading_os.research_assets.claims import ClaimPacketError

    payload = _research_claims()
    payload["hidden_answer"] = "buy"

    with pytest.raises(ClaimPacketError, match="fields"):
        _build(payload)


@pytest.mark.parametrize("duplicate_kind", ["claim", "source"])
def test_duplicate_ids_are_rejected(duplicate_kind: str):
    from trading_os.research_assets.claims import ClaimPacketError

    payload = _research_claims()
    if duplicate_kind == "claim":
        payload["claims"].append(dict(payload["claims"][0]))
    else:
        payload["sources"].append(dict(payload["sources"][0]))

    with pytest.raises(ClaimPacketError, match="duplicate"):
        _build(payload)


def test_claim_source_reference_must_exist():
    from trading_os.research_assets.claims import ClaimPacketError

    payload = _research_claims()
    payload["claims"][0]["source_ids"] = ["missing-source"]

    with pytest.raises(ClaimPacketError, match="unknown source"):
        _build(payload)


def test_source_tier_must_be_known():
    from trading_os.research_assets.claims import ClaimPacketError

    payload = _research_claims()
    payload["sources"][0]["tier"] = "S5"

    with pytest.raises(ClaimPacketError, match="tier"):
        _build(payload)


def test_created_at_requires_timezone():
    from trading_os.research_assets.claims import ClaimPacketError, build_claim_packet

    with pytest.raises(ClaimPacketError, match="timezone"):
        build_claim_packet(
            _research_claims(),
            review_id="review-memory-001",
            packet_id="packet-CN-000021",
            source_report_sha256=SOURCE_HASH,
            created_at=dt.datetime(2026, 7, 21, 8, 0),
        )


def test_research_claims_schema_is_closed():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "templates" / "research-claims.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "report_id",
        "symbol",
        "claims",
        "sources",
        "decision",
    }
