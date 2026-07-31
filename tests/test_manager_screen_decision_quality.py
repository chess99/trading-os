from __future__ import annotations

import copy
import hashlib

import pytest

from trading_os.research_assets.manager_screen_decision_quality import (
    CANONICAL_FACT_LINE_KEYS,
    RISK_ACKNOWLEDGEMENT_KEYS,
    RISK_FLAG_KEYS,
    ManagerScreenDecisionQualityError,
    build_decision_support,
    validate_canonical_reason,
    validate_decision_support,
    validate_risk_acknowledgements,
)
from trading_os.research_assets.sealing import canonical_json_bytes

SYMBOL = "CN:000333"
NAME = "示例公司"
THRESHOLD = 90.0


def _market_snapshot(**overrides: object) -> dict:
    result = {
        "listing_status": "listed",
        "market_cap_cny": 50_000_000_000,
    }
    result.update(overrides)
    return result


def _annual(
    *,
    report_date: str = "2025-12-31",
    audit_opinion: str = "标准无保留意见",
    deducted_profit: int = 3_000_000_000,
    operating_cash_flow: int = 4_000_000_000,
    cash: int = 10_000_000_000,
    debt: int = 5_000_000_000,
    assets: int = 100_000_000_000,
    liabilities: int = 40_000_000_000,
    equity: int = 50_000_000_000,
) -> dict:
    return {
        "report_date": report_date,
        "report_type": "年报",
        "deducted_parent_net_profit_cny": deducted_profit,
        "operating_cash_flow_cny": operating_cash_flow,
        "audit_opinion": audit_opinion,
        "balance_sheet": {
            "cash_cny": cash,
            "interest_bearing_debt_cny": debt,
            "total_assets_cny": assets,
            "total_liabilities_cny": liabilities,
            "parent_equity_cny": equity,
        },
    }


def _facts(*, annual: dict | None = None, interim_type: str = "中报") -> dict:
    return {
        "annuals": [
            _annual(
                report_date="2024-12-31",
                deducted_profit=2_000_000_000,
            ),
            annual or _annual(),
        ],
        "latest_interim": {
            "report_date": "2026-06-30",
            "report_type": interim_type,
            "deducted_parent_net_profit_cny": 1_500_000_000,
            "operating_cash_flow_cny": 1_000_000_000,
            "balance_sheet": None,
            "audit_opinion": None,
        },
    }


def _build(
    *,
    name: str = NAME,
    market_snapshot: dict | None = None,
    facts: dict | None = None,
    prior_screening: dict | None = None,
    timeline: dict | None = None,
    canonical_source_evidence_id: str | None = None,
) -> dict:
    return build_decision_support(
        symbol=SYMBOL,
        name=name,
        market_snapshot=market_snapshot or _market_snapshot(),
        facts=facts or _facts(),
        prior_screening=prior_screening,
        timeline=timeline,
        high_liability_to_assets_pct=THRESHOLD,
        canonical_source_evidence_id=canonical_source_evidence_id,
    )


def _risk_support() -> tuple[dict, dict, dict, dict]:
    market_snapshot = _market_snapshot(listing_status="suspended")
    facts = _facts(
        annual=_annual(
            audit_opinion="保留意见",
            operating_cash_flow=-500_000_000,
            cash=1_000_000_000,
            debt=20_000_000_000,
            assets=100_000_000_000,
            liabilities=95_000_000_000,
            equity=2_000_000_000,
        )
    )
    prior_screening = {
        "evidence": [
            "fixture",
            (
                "triage_reason_codes:guarantee_exposure,related_party_funds,"
                "share_pledge,guarantee_chain,guarantee_overdue,guarantee_fourth"
            ),
        ]
    }
    timeline = {
        "active_triggers": [
            {"active": True, "reason": "重大诉讼进入审理阶段"},
            {"active": True, "reason": "法院已受理破产重整申请"},
            {"active": False, "reason": "冻结风险已解除"},
        ]
    }
    support = _build(
        name="*ST示例",
        market_snapshot=market_snapshot,
        facts=facts,
        prior_screening=prior_screening,
        timeline=timeline,
    )
    return support, market_snapshot, facts, prior_screening


def _canonical_reason(support: dict, suffix: str) -> str:
    return f"{support['canonical_fact_line']['text']}；{suffix}"


def _acknowledgements(
    support: dict,
    *,
    material_flag_id: str | None = None,
    material_reason: str = "风险可能损害普通股剩余索取权",
) -> list[dict]:
    return [
        {
            "flag_id": flag["flag_id"],
            "assessment": (
                "material" if flag["flag_id"] == material_flag_id else "not_material"
            ),
            "reason": (
                material_reason
                if flag["flag_id"] == material_flag_id
                else "已核对证据且当前不构成路线阻断"
            ),
        }
        for flag in support["mandatory_risk_flags"]
    ]


def _all_evidence_ids(support: dict) -> list[str]:
    return list(
        dict.fromkeys(
            evidence_id
            for flag in support["mandatory_risk_flags"]
            for evidence_id in flag["evidence_ids"]
        )
    )


def test_builds_canonical_middle_report_without_mislabeling_it_as_q1() -> None:
    support = _build()
    canonical = support["canonical_fact_line"]

    assert set(canonical) == CANONICAL_FACT_LINE_KEYS
    assert canonical["latest_annual_report_date"] == "2025-12-31"
    assert canonical["latest_annual_report_type"] == "年报"
    assert canonical["latest_interim_report_date"] == "2026-06-30"
    assert canonical["latest_interim_report_type"] == "中报"
    assert "2025年年报" in canonical["text"]
    assert "2026年中报" in canonical["text"]
    assert "一季报" not in canonical["text"]
    assert "扣非归母净利润" in canonical["text"]
    assert "经营现金流" in canonical["text"]
    assert "市值500.00亿元" in canonical["text"]
    assert "2025年年末净现金50.00亿元" in canonical["text"]

    unsigned = {key: value for key, value in canonical.items() if key != "sha256"}
    assert canonical["sha256"] == hashlib.sha256(
        canonical_json_bytes(unsigned)
    ).hexdigest()


def test_explicit_canonical_source_is_bound_and_recomputed_fail_closed() -> None:
    market_snapshot = _market_snapshot()
    facts = _facts()
    source_evidence_id = f"quote-amendment:quotes-001:{SYMBOL}"
    support = _build(
        market_snapshot=market_snapshot,
        facts=facts,
        canonical_source_evidence_id=source_evidence_id,
    )

    assert (
        support["canonical_fact_line"]["source_evidence_id"]
        == source_evidence_id
    )
    validate_decision_support(
        support,
        symbol=SYMBOL,
        name=NAME,
        market_snapshot=market_snapshot,
        facts=facts,
        prior_screening=None,
        timeline=None,
        high_liability_to_assets_pct=THRESHOLD,
        canonical_source_evidence_id=source_evidence_id,
    )

    tampered = copy.deepcopy(support)
    tampered["canonical_fact_line"]["source_evidence_id"] = f"snapshot:{SYMBOL}"
    unsigned = {
        key: value
        for key, value in tampered["canonical_fact_line"].items()
        if key != "sha256"
    }
    tampered["canonical_fact_line"]["sha256"] = hashlib.sha256(
        canonical_json_bytes(unsigned)
    ).hexdigest()
    with pytest.raises(
        ManagerScreenDecisionQualityError,
        match="deterministic recomputation",
    ):
        validate_decision_support(
            tampered,
            symbol=SYMBOL,
            name=NAME,
            market_snapshot=market_snapshot,
            facts=facts,
            prior_screening=None,
            timeline=None,
            high_liability_to_assets_pct=THRESHOLD,
            canonical_source_evidence_id=source_evidence_id,
        )


def test_validate_decision_support_rejects_any_canonical_tampering() -> None:
    market_snapshot = _market_snapshot()
    facts = _facts()
    support = _build(market_snapshot=market_snapshot, facts=facts)
    tampered = copy.deepcopy(support)
    tampered["canonical_fact_line"]["text"] = tampered["canonical_fact_line"][
        "text"
    ].replace("2026年中报", "2026年一季报")

    with pytest.raises(
        ManagerScreenDecisionQualityError,
        match="sha256 does not match",
    ):
        validate_decision_support(
            tampered,
            symbol=SYMBOL,
            name=NAME,
            market_snapshot=market_snapshot,
            facts=facts,
            prior_screening=None,
            timeline=None,
            high_liability_to_assets_pct=THRESHOLD,
        )

    rehashed = copy.deepcopy(tampered)
    unsigned = {
        key: value
        for key, value in rehashed["canonical_fact_line"].items()
        if key != "sha256"
    }
    rehashed["canonical_fact_line"]["sha256"] = hashlib.sha256(
        canonical_json_bytes(unsigned)
    ).hexdigest()
    with pytest.raises(
        ManagerScreenDecisionQualityError,
        match="deterministic recomputation",
    ):
        validate_decision_support(
            rehashed,
            symbol=SYMBOL,
            name=NAME,
            market_snapshot=market_snapshot,
            facts=facts,
            prior_screening=None,
            timeline=None,
            high_liability_to_assets_pct=THRESHOLD,
        )


@pytest.mark.parametrize(
    "suffix",
    [
        "利润增长2倍但兑现度不足",
        "利润增长２倍但兑现度不足",
        "收益率达到百分之十%",
        "收益率达到百分之十％",
        "估值翻倍风险较高",
    ],
)
def test_validate_canonical_reason_rejects_numeric_suffix(suffix: str) -> None:
    support = _build()

    with pytest.raises(
        ManagerScreenDecisionQualityError,
        match="must not contain digits",
    ):
        validate_canonical_reason(_canonical_reason(support, suffix), support)


def test_build_aggregates_structured_and_unstructured_risk_candidates() -> None:
    support, _, _, _ = _risk_support()
    flags = support["mandatory_risk_flags"]
    by_category = {flag["category"]: flag for flag in flags}

    assert [flag["category"] for flag in flags] == [
        "audit_or_listing",
        "capital_structure",
        "guarantee",
        "related_party_or_control",
        "pledge_or_freeze",
        "litigation_or_restructuring",
    ]
    assert all(set(flag) == RISK_FLAG_KEYS for flag in flags)
    assert {
        "listing_status:suspended",
        "security_name:st",
    }.issubset(by_category["audit_or_listing"]["signals"])
    assert any(
        signal.startswith("audit_opinion:non_standard:")
        for signal in by_category["audit_or_listing"]["signals"]
    )
    assert {
        "liabilities_to_assets:above_policy_threshold",
        "debt_vs_equity_and_liquidity:weak",
    }.issubset(by_category["capital_structure"]["signals"])
    assert by_category["guarantee"]["evidence_ids"] == [f"screening:{SYMBOL}"]
    assert by_category["related_party_or_control"]["evidence_ids"] == [
        f"screening:{SYMBOL}"
    ]
    assert by_category["pledge_or_freeze"]["evidence_ids"] == [
        f"screening:{SYMBOL}"
    ]
    assert by_category["litigation_or_restructuring"]["evidence_ids"] == [
        f"timeline:{SYMBOL}"
    ]
    guarantee_unstructured = [
        signal
        for signal in by_category["guarantee"]["signals"]
        if signal.startswith("triage_reason_code:")
    ]
    assert len(guarantee_unstructured) == 3


def test_non_positive_parent_equity_is_a_capital_structure_candidate() -> None:
    facts = _facts(
        annual=_annual(
            cash=1_000_000_000,
            debt=2_000_000_000,
            equity=0,
        )
    )

    support = _build(facts=facts)

    capital_flag = next(
        flag
        for flag in support["mandatory_risk_flags"]
        if flag["category"] == "capital_structure"
    )
    assert "parent_equity:non_positive" in capital_flag["signals"]


@pytest.mark.parametrize("route", ["pass", "watch", "send_to_analyst"])
def test_acknowledgement_gate_is_independent_of_route(route: str) -> None:
    support, _, _, _ = _risk_support()
    material_reason = "高杠杆削弱普通股安全边际"
    decision = {
        "route": route,
        "one_line_reason": _canonical_reason(
            support,
            f"{material_reason}，仍需由投资经理统一判断",
        ),
        "decisive_question": "现有证据是否足以排除永久损失风险？",
        "evidence_ids": _all_evidence_ids(support),
        "risk_acknowledgements": _acknowledgements(
            support,
            material_flag_id="capital_structure",
            material_reason=material_reason,
        ),
    }

    validated = validate_risk_acknowledgements(
        decision["risk_acknowledgements"],
        support=support,
        decision_evidence_ids=decision["evidence_ids"],
        one_line_reason=decision["one_line_reason"],
        decisive_question=decision["decisive_question"],
    )

    assert validated == decision["risk_acknowledgements"]
    assert all(set(item) == RISK_ACKNOWLEDGEMENT_KEYS for item in validated)


def test_material_acknowledgement_may_be_bound_to_decisive_question() -> None:
    support, _, _, _ = _risk_support()
    material_reason = "诉讼可能改变普通股剩余价值"

    validated = validate_risk_acknowledgements(
        _acknowledgements(
            support,
            material_flag_id="litigation_or_restructuring",
            material_reason=material_reason,
        ),
        support=support,
        decision_evidence_ids=_all_evidence_ids(support),
        one_line_reason=_canonical_reason(support, "风险候选均已回应并保留审慎判断"),
        decisive_question=f"{material_reason}，是否存在可核验的反证？",
    )

    assert validated[-1]["assessment"] == "material"


def test_acknowledgements_reject_missing_duplicate_and_unknown_flags() -> None:
    support, _, _, _ = _risk_support()
    acknowledgements = _acknowledgements(support)
    kwargs = {
        "support": support,
        "decision_evidence_ids": _all_evidence_ids(support),
        "one_line_reason": _canonical_reason(support, "风险候选均已逐项审阅"),
        "decisive_question": "是否仍有未被当前证据覆盖的重大风险？",
    }

    with pytest.raises(ManagerScreenDecisionQualityError, match="missing"):
        validate_risk_acknowledgements(acknowledgements[:-1], **kwargs)

    duplicate = copy.deepcopy(acknowledgements)
    duplicate[-1]["flag_id"] = duplicate[0]["flag_id"]
    with pytest.raises(ManagerScreenDecisionQualityError, match="duplicate"):
        validate_risk_acknowledgements(duplicate, **kwargs)

    unknown = copy.deepcopy(acknowledgements)
    unknown[-1]["flag_id"] = "unknown"
    with pytest.raises(ManagerScreenDecisionQualityError, match="unknown"):
        validate_risk_acknowledgements(unknown, **kwargs)


def test_acknowledgement_requires_flag_evidence_and_material_reason_binding() -> None:
    support, _, _, _ = _risk_support()
    material_reason = "担保链可能导致不可逆损失"
    acknowledgements = _acknowledgements(
        support,
        material_flag_id="guarantee",
        material_reason=material_reason,
    )

    with pytest.raises(ManagerScreenDecisionQualityError, match="lacks decision evidence"):
        validate_risk_acknowledgements(
            acknowledgements,
            support=support,
            decision_evidence_ids=[f"snapshot:{SYMBOL}", f"timeline:{SYMBOL}"],
            one_line_reason=_canonical_reason(support, material_reason),
            decisive_question="担保风险是否已经充分计入判断？",
        )

    with pytest.raises(ManagerScreenDecisionQualityError, match="must appear verbatim"):
        validate_risk_acknowledgements(
            acknowledgements,
            support=support,
            decision_evidence_ids=_all_evidence_ids(support),
            one_line_reason=_canonical_reason(support, "担保风险需要继续审阅"),
            decisive_question="是否存在其他重大风险？",
        )
