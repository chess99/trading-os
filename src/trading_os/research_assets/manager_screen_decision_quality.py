from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .sealing import SealingError, canonical_json_bytes

DECISION_SUPPORT_KEYS = {
    "schema_version",
    "canonical_fact_line",
    "mandatory_risk_flags",
}
CANONICAL_FACT_LINE_KEYS = {
    "schema_version",
    "text",
    "source_evidence_id",
    "latest_annual_report_date",
    "latest_annual_report_type",
    "latest_interim_report_date",
    "latest_interim_report_type",
    "latest_annual_deducted_parent_net_profit_cny",
    "latest_annual_operating_cash_flow_cny",
    "latest_interim_deducted_parent_net_profit_cny",
    "market_cap_cny",
    "year_end_net_debt_cny",
    "sha256",
}
RISK_FLAG_KEYS = {
    "flag_id",
    "category",
    "summary",
    "evidence_ids",
    "signals",
}
RISK_ACKNOWLEDGEMENT_KEYS = {
    "flag_id",
    "assessment",
    "reason",
}

RISK_CATEGORIES = (
    "audit_or_listing",
    "capital_structure",
    "guarantee",
    "related_party_or_control",
    "pledge_or_freeze",
    "litigation_or_restructuring",
)
RISK_ASSESSMENTS = {"material", "not_material"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ST_NAME_RE = re.compile(r"^\*?ST", re.IGNORECASE)
_FORBIDDEN_REASON_SUFFIX_RE = re.compile(r"[0-9０-９%％倍]")
_TRIAGE_REASON_CODES_PREFIX = "triage_reason_codes:"
_STANDARD_AUDIT_OPINIONS = {
    "无保留意见",
    "标准无保留意见",
    "标准的无保留意见",
}
_CATEGORY_TITLES = {
    "audit_or_listing": "审计或上市状态风险",
    "capital_structure": "资本结构风险",
    "guarantee": "担保风险",
    "related_party_or_control": "关联方或控制权风险",
    "pledge_or_freeze": "质押或冻结风险",
    "litigation_or_restructuring": "诉讼或重整风险",
}
_CODE_PATTERNS = {
    "audit_or_listing": (
        "going_concern",
        "delist",
        "termination_of_listing",
        "non_standard_audit",
    ),
    "capital_structure": (
        "negative_net_assets",
        "insolven",
        "overdue",
        "default",
        "debt_crisis",
    ),
    "guarantee": ("guarantee", "guarant"),
    "related_party_or_control": (
        "related",
        "fund_occupation",
        "funds_occupation",
        "occupation_of_funds",
        "control_change",
    ),
    "pledge_or_freeze": ("pledge", "freeze", "frozen"),
    "litigation_or_restructuring": (
        "lawsuit",
        "litigation",
        "restructur",
        "bankrupt",
    ),
}
_TIMELINE_PATTERNS = {
    "audit_or_listing": (
        "持续经营",
        "退市",
        "终止上市",
        "非标审计",
        "going concern",
        "delist",
    ),
    "capital_structure": (
        "负资产",
        "净资产为负",
        "逾期",
        "违约",
        "债务危机",
        "insolven",
        "overdue",
        "default",
    ),
    "guarantee": ("担保", "guarantee"),
    "related_party_or_control": (
        "关联",
        "资金占用",
        "实控人",
        "控制权",
        "related",
        "fund occupation",
    ),
    "pledge_or_freeze": ("质押", "冻结", "pledge", "freeze", "frozen"),
    "litigation_or_restructuring": (
        "诉讼",
        "仲裁",
        "破产",
        "重整",
        "清算",
        "lawsuit",
        "litigation",
        "restructur",
        "bankrupt",
    ),
}
_EVIDENCE_ORDER = {
    "snapshot": 0,
    "screening": 1,
    "timeline": 2,
}

__all__ = [
    "CANONICAL_FACT_LINE_KEYS",
    "DECISION_SUPPORT_KEYS",
    "ManagerScreenDecisionQualityError",
    "RISK_ACKNOWLEDGEMENT_KEYS",
    "RISK_ASSESSMENTS",
    "RISK_CATEGORIES",
    "RISK_FLAG_KEYS",
    "build_decision_support",
    "validate_canonical_reason",
    "validate_decision_support",
    "validate_risk_acknowledgements",
]


class ManagerScreenDecisionQualityError(ValueError):
    """Raised when manager-screen decision-quality data violates its contract."""


def build_decision_support(
    *,
    symbol: str,
    name: str,
    market_snapshot: Mapping[str, Any],
    facts: Mapping[str, Any],
    prior_screening: Mapping[str, Any] | None,
    timeline: Mapping[str, Any] | None,
    high_liability_to_assets_pct: float,
    canonical_source_evidence_id: str | None = None,
) -> dict[str, Any]:
    """Build deterministic fact and risk support without making a route decision."""

    normalized_symbol = _text(symbol, "symbol")
    normalized_name = _text(name, "name")
    if not isinstance(market_snapshot, Mapping):
        raise ManagerScreenDecisionQualityError("market_snapshot must be an object")
    if not isinstance(facts, Mapping):
        raise ManagerScreenDecisionQualityError("facts must be an object")
    threshold = _required_number(
        high_liability_to_assets_pct,
        "high_liability_to_assets_pct",
    )
    if not 0 < threshold <= 100:
        raise ManagerScreenDecisionQualityError(
            "high_liability_to_assets_pct must be in (0, 100]"
        )

    latest_annual = _latest_annual(facts.get("annuals"))
    latest_interim = _period_or_none(facts.get("latest_interim"))
    source_evidence_id = (
        f"snapshot:{normalized_symbol}"
        if canonical_source_evidence_id is None
        else _text(
            canonical_source_evidence_id,
            "canonical_source_evidence_id",
        )
    )
    canonical_fact_line = _build_canonical_fact_line(
        symbol=normalized_symbol,
        name=normalized_name,
        market_snapshot=market_snapshot,
        latest_annual=latest_annual,
        latest_interim=latest_interim,
        source_evidence_id=source_evidence_id,
    )
    mandatory_risk_flags = _build_mandatory_risk_flags(
        symbol=normalized_symbol,
        name=normalized_name,
        market_snapshot=market_snapshot,
        latest_annual=latest_annual,
        prior_screening=prior_screening,
        timeline=timeline,
        high_liability_to_assets_pct=threshold,
    )
    return {
        "schema_version": 1,
        "canonical_fact_line": canonical_fact_line,
        "mandatory_risk_flags": mandatory_risk_flags,
    }


def validate_decision_support(
    value: Any,
    *,
    symbol: str,
    name: str,
    market_snapshot: Mapping[str, Any],
    facts: Mapping[str, Any],
    prior_screening: Mapping[str, Any] | None,
    timeline: Mapping[str, Any] | None,
    high_liability_to_assets_pct: float,
    canonical_source_evidence_id: str | None = None,
) -> dict[str, Any]:
    """Recompute decision support and require canonical-JSON exact equality."""

    expected = build_decision_support(
        symbol=symbol,
        name=name,
        market_snapshot=market_snapshot,
        facts=facts,
        prior_screening=prior_screening,
        timeline=timeline,
        high_liability_to_assets_pct=high_liability_to_assets_pct,
        canonical_source_evidence_id=canonical_source_evidence_id,
    )
    _validate_support_shape(value)
    try:
        actual_bytes = canonical_json_bytes(value)
        expected_bytes = canonical_json_bytes(expected)
    except SealingError as exc:
        raise ManagerScreenDecisionQualityError(
            f"decision support is not canonical JSON: {exc}"
        ) from exc
    if actual_bytes != expected_bytes:
        raise ManagerScreenDecisionQualityError(
            "decision support does not match deterministic recomputation"
        )
    return expected


def validate_canonical_reason(reason: Any, support: Any) -> str:
    """Require the immutable fact line followed by a qualitative-only suffix."""

    validated_support = _validate_support_shape(support)
    normalized_reason = _text(reason, "one_line_reason")
    if "\n" in normalized_reason or "\r" in normalized_reason:
        raise ManagerScreenDecisionQualityError("one_line_reason must be one line")
    fact_text = validated_support["canonical_fact_line"]["text"]
    prefix = f"{fact_text}；"
    if not normalized_reason.startswith(prefix):
        raise ManagerScreenDecisionQualityError(
            "one_line_reason must start with the canonical fact line"
        )
    suffix = normalized_reason[len(prefix) :].strip()
    if not suffix:
        raise ManagerScreenDecisionQualityError(
            "one_line_reason must include a qualitative suffix"
        )
    if _FORBIDDEN_REASON_SUFFIX_RE.search(suffix):
        raise ManagerScreenDecisionQualityError(
            "one_line_reason qualitative suffix must not contain digits, percentages, or 倍"
        )
    return normalized_reason


def validate_risk_acknowledgements(
    value: Any,
    *,
    support: Any,
    decision_evidence_ids: Any,
    one_line_reason: Any,
    decisive_question: Any,
) -> list[dict[str, str]]:
    """Validate exact, ordered acknowledgement of every mandatory risk flag."""

    validated_support = _validate_support_shape(support)
    normalized_one_line_reason = validate_canonical_reason(
        one_line_reason,
        validated_support,
    )
    question = _text(decisive_question, "decisive_question")
    if not isinstance(decision_evidence_ids, list) or not decision_evidence_ids:
        raise ManagerScreenDecisionQualityError(
            "decision_evidence_ids must be a non-empty string array"
        )
    if (
        not all(
            isinstance(item, str) and item.strip() == item and item
            for item in decision_evidence_ids
        )
        or len(decision_evidence_ids) != len(set(decision_evidence_ids))
    ):
        raise ManagerScreenDecisionQualityError(
            "decision_evidence_ids must be a non-empty unique string array"
        )
    if not isinstance(value, list):
        raise ManagerScreenDecisionQualityError("risk_acknowledgements must be an array")

    flags = validated_support["mandatory_risk_flags"]
    expected_ids = [flag["flag_id"] for flag in flags]
    actual_ids = [
        item.get("flag_id") if isinstance(item, Mapping) else None for item in value
    ]
    duplicate_ids = sorted(
        {
            flag_id
            for flag_id in actual_ids
            if isinstance(flag_id, str) and actual_ids.count(flag_id) > 1
        }
    )
    if duplicate_ids:
        raise ManagerScreenDecisionQualityError(
            f"duplicate risk acknowledgement flag_id: {duplicate_ids}"
        )
    unknown_ids = sorted(
        {
            flag_id
            for flag_id in actual_ids
            if isinstance(flag_id, str) and flag_id not in expected_ids
        }
    )
    if unknown_ids:
        raise ManagerScreenDecisionQualityError(
            f"unknown risk acknowledgement flag_id: {unknown_ids}"
        )
    missing_ids = [flag_id for flag_id in expected_ids if flag_id not in actual_ids]
    if missing_ids:
        raise ManagerScreenDecisionQualityError(
            f"missing risk acknowledgement flag_id: {missing_ids}"
        )
    if actual_ids != expected_ids or len(value) != len(expected_ids):
        raise ManagerScreenDecisionQualityError(
            "risk acknowledgements must appear exactly once in mandatory flag order"
        )

    fact_text = validated_support["canonical_fact_line"]["text"]
    qualitative_suffix = normalized_one_line_reason[len(f"{fact_text}；") :].strip()
    evidence_id_set = set(decision_evidence_ids)
    normalized: list[dict[str, str]] = []
    for index, (item, flag) in enumerate(zip(value, flags, strict=True)):
        if not isinstance(item, Mapping) or set(item) != RISK_ACKNOWLEDGEMENT_KEYS:
            raise ManagerScreenDecisionQualityError(
                f"risk_acknowledgements[{index}] fields do not match the contract"
            )
        assessment = item.get("assessment")
        if assessment not in RISK_ASSESSMENTS:
            raise ManagerScreenDecisionQualityError(
                f"risk_acknowledgements[{index}].assessment is invalid"
            )
        acknowledgement_reason = _text(
            item.get("reason"),
            f"risk_acknowledgements[{index}].reason",
        )
        if "\n" in acknowledgement_reason or "\r" in acknowledgement_reason:
            raise ManagerScreenDecisionQualityError(
                f"risk_acknowledgements[{index}].reason must be one line"
            )
        missing_evidence = [
            evidence_id
            for evidence_id in flag["evidence_ids"]
            if evidence_id not in evidence_id_set
        ]
        if missing_evidence:
            raise ManagerScreenDecisionQualityError(
                f"{flag['flag_id']} acknowledgement lacks decision evidence: "
                f"{missing_evidence}"
            )
        if (
            assessment == "material"
            and acknowledgement_reason not in qualitative_suffix
            and acknowledgement_reason not in question
        ):
            raise ManagerScreenDecisionQualityError(
                f"material acknowledgement reason for {flag['flag_id']} must appear "
                "verbatim in the qualitative suffix or decisive_question"
            )
        normalized.append(
            {
                "flag_id": flag["flag_id"],
                "assessment": assessment,
                "reason": acknowledgement_reason,
            }
        )
    return normalized


def _build_canonical_fact_line(
    *,
    symbol: str,
    name: str,
    market_snapshot: Mapping[str, Any],
    latest_annual: Mapping[str, Any] | None,
    latest_interim: Mapping[str, Any] | None,
    source_evidence_id: str,
) -> dict[str, Any]:
    annual_date = _report_date(latest_annual)
    annual_type = "年报" if latest_annual is not None else None
    interim_date = _report_date(latest_interim)
    interim_type = _interim_report_type(latest_interim)
    annual_deducted_profit = _period_number(
        latest_annual,
        "deducted_parent_net_profit_cny",
    )
    annual_operating_cash_flow = _period_number(
        latest_annual,
        "operating_cash_flow_cny",
    )
    interim_deducted_profit = _period_number(
        latest_interim,
        "deducted_parent_net_profit_cny",
    )
    market_cap = _number(market_snapshot.get("market_cap_cny"))
    balance_sheet = _balance_sheet(latest_annual)
    cash = _mapping_number(balance_sheet, "cash_cny")
    debt = _mapping_number(balance_sheet, "interest_bearing_debt_cny")
    year_end_net_debt = debt - cash if debt is not None and cash is not None else None

    annual_label = (
        f"{annual_date[:4]}年年报（{annual_date}）"
        if annual_date is not None
        else "年报（缺失）"
    )
    if interim_date is not None and interim_type is not None:
        interim_label = f"{interim_date[:4]}年{interim_type}（{interim_date}）"
    else:
        interim_label = "最新一季报/中报/三季报（缺失）"
    if year_end_net_debt is None:
        net_debt_text = "年末净债务/净现金缺失"
    elif year_end_net_debt < 0:
        net_debt_text = f"年末净现金{_format_cny(-year_end_net_debt)}"
    else:
        net_debt_text = f"年末净债务{_format_cny(year_end_net_debt)}"

    text = (
        f"{name}（{symbol}）：{annual_label}扣非归母净利润"
        f"{_format_cny(annual_deducted_profit)}、经营现金流"
        f"{_format_cny(annual_operating_cash_flow)}；{interim_label}扣非归母净利润"
        f"{_format_cny(interim_deducted_profit)}；市值{_format_cny(market_cap)}；"
        f"{annual_date[:4] + '年' if annual_date is not None else ''}{net_debt_text}"
    )
    unsigned = {
        "schema_version": 1,
        "text": text,
        "source_evidence_id": source_evidence_id,
        "latest_annual_report_date": annual_date,
        "latest_annual_report_type": annual_type,
        "latest_interim_report_date": interim_date,
        "latest_interim_report_type": interim_type,
        "latest_annual_deducted_parent_net_profit_cny": annual_deducted_profit,
        "latest_annual_operating_cash_flow_cny": annual_operating_cash_flow,
        "latest_interim_deducted_parent_net_profit_cny": interim_deducted_profit,
        "market_cap_cny": market_cap,
        "year_end_net_debt_cny": year_end_net_debt,
    }
    return {
        **unsigned,
        "sha256": hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest(),
    }


def _build_mandatory_risk_flags(
    *,
    symbol: str,
    name: str,
    market_snapshot: Mapping[str, Any],
    latest_annual: Mapping[str, Any] | None,
    prior_screening: Mapping[str, Any] | None,
    timeline: Mapping[str, Any] | None,
    high_liability_to_assets_pct: float,
) -> list[dict[str, Any]]:
    candidates = {
        category: {
            "signals": [],
            "descriptions": [],
            "evidence_ids": set(),
            "unstructured_count": 0,
        }
        for category in RISK_CATEGORIES
    }
    snapshot_evidence_id = f"snapshot:{symbol}"

    listing_status = market_snapshot.get("listing_status")
    if isinstance(listing_status, str) and listing_status.strip():
        normalized_listing_status = listing_status.strip()
        if normalized_listing_status != "listed":
            _add_candidate(
                candidates,
                category="audit_or_listing",
                signal=f"listing_status:{normalized_listing_status}",
                description=f"上市状态为{normalized_listing_status}",
                evidence_id=snapshot_evidence_id,
            )
    if _ST_NAME_RE.search(name):
        _add_candidate(
            candidates,
            category="audit_or_listing",
            signal="security_name:st",
            description="证券简称带ST标记",
            evidence_id=snapshot_evidence_id,
        )

    audit_opinion = (
        latest_annual.get("audit_opinion")
        if isinstance(latest_annual, Mapping)
        else None
    )
    if _is_non_standard_audit_opinion(audit_opinion):
        normalized_opinion = _single_line_text(audit_opinion)
        _add_candidate(
            candidates,
            category="audit_or_listing",
            signal=f"audit_opinion:non_standard:{normalized_opinion}",
            description=f"年报审计意见为{normalized_opinion}",
            evidence_id=snapshot_evidence_id,
        )

    balance_sheet = _balance_sheet(latest_annual)
    equity = _mapping_number(balance_sheet, "parent_equity_cny")
    assets = _mapping_number(balance_sheet, "total_assets_cny")
    liabilities = _mapping_number(balance_sheet, "total_liabilities_cny")
    cash = _mapping_number(balance_sheet, "cash_cny")
    debt = _mapping_number(balance_sheet, "interest_bearing_debt_cny")
    annual_ocf = _period_number(latest_annual, "operating_cash_flow_cny")
    if equity is not None and equity <= 0:
        _add_candidate(
            candidates,
            category="capital_structure",
            signal="parent_equity:non_positive",
            description=f"归母权益不大于零（{_format_cny(equity)}）",
            evidence_id=snapshot_evidence_id,
        )
    if assets is not None and assets > 0 and liabilities is not None:
        liability_to_assets_pct = liabilities / assets * 100
        if liability_to_assets_pct >= high_liability_to_assets_pct:
            _add_candidate(
                candidates,
                category="capital_structure",
                signal="liabilities_to_assets:above_policy_threshold",
                description=(
                    f"资产负债率{liability_to_assets_pct:.2f}%达到政策阈值"
                    f"{high_liability_to_assets_pct:g}%"
                ),
                evidence_id=snapshot_evidence_id,
            )
    if (
        debt is not None
        and equity is not None
        and cash is not None
        and annual_ocf is not None
        and debt >= 2 * equity
        and cash + max(annual_ocf, 0) < debt
    ):
        _add_candidate(
            candidates,
            category="capital_structure",
            signal="debt_vs_equity_and_liquidity:weak",
            description="有息债务至少为归母权益两倍且现金与正经营现金流不足覆盖债务",
            evidence_id=snapshot_evidence_id,
        )

    if isinstance(prior_screening, Mapping):
        for code in _triage_reason_codes(prior_screening.get("evidence")):
            for category in _matching_categories(code, _CODE_PATTERNS):
                _add_candidate(
                    candidates,
                    category=category,
                    signal=f"triage_reason_code:{code}",
                    description=f"历史初筛风险码{code}",
                    evidence_id=f"screening:{symbol}",
                    unstructured=True,
                )

    if isinstance(timeline, Mapping):
        active_triggers = timeline.get("active_triggers")
        if isinstance(active_triggers, list):
            for trigger in active_triggers:
                if not isinstance(trigger, Mapping) or trigger.get("active") is False:
                    continue
                reason = trigger.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    continue
                normalized_reason = _single_line_text(reason)
                for category in _matching_categories(
                    normalized_reason,
                    _TIMELINE_PATTERNS,
                ):
                    _add_candidate(
                        candidates,
                        category=category,
                        signal=f"timeline_reason:{normalized_reason}",
                        description=f"公司时间线提示{normalized_reason}",
                        evidence_id=f"timeline:{symbol}",
                        unstructured=True,
                    )

    flags: list[dict[str, Any]] = []
    for category in RISK_CATEGORIES:
        candidate = candidates[category]
        signals = candidate["signals"]
        if not signals:
            continue
        evidence_ids = sorted(
            candidate["evidence_ids"],
            key=lambda item: (
                _EVIDENCE_ORDER.get(item.split(":", 1)[0], len(_EVIDENCE_ORDER)),
                item,
            ),
        )
        flags.append(
            {
                "flag_id": category,
                "category": category,
                "summary": (
                    f"{_CATEGORY_TITLES[category]}候选："
                    + "；".join(candidate["descriptions"])
                ),
                "evidence_ids": evidence_ids,
                "signals": list(signals),
            }
        )
    return flags


def _add_candidate(
    candidates: dict[str, dict[str, Any]],
    *,
    category: str,
    signal: str,
    description: str,
    evidence_id: str,
    unstructured: bool = False,
) -> None:
    candidate = candidates[category]
    if signal in candidate["signals"]:
        return
    if unstructured and candidate["unstructured_count"] >= 3:
        return
    candidate["signals"].append(signal)
    candidate["descriptions"].append(description)
    candidate["evidence_ids"].add(evidence_id)
    if unstructured:
        candidate["unstructured_count"] += 1


def _triage_reason_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        prefix_index = entry.casefold().find(_TRIAGE_REASON_CODES_PREFIX)
        if prefix_index < 0:
            continue
        raw_codes = entry[prefix_index + len(_TRIAGE_REASON_CODES_PREFIX) :]
        for raw_code in raw_codes.split(","):
            code = raw_code.strip().casefold()
            if code and code not in result:
                result.append(code)
    return result


def _matching_categories(
    value: str,
    patterns_by_category: Mapping[str, tuple[str, ...]],
) -> list[str]:
    normalized = value.casefold()
    return [
        category
        for category in RISK_CATEGORIES
        if any(pattern.casefold() in normalized for pattern in patterns_by_category[category])
    ]


def _validate_support_shape(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != DECISION_SUPPORT_KEYS:
        raise ManagerScreenDecisionQualityError(
            "decision support fields do not match the v1 contract"
        )
    if value.get("schema_version") != 1:
        raise ManagerScreenDecisionQualityError(
            "decision support schema_version must be 1"
        )
    canonical = value.get("canonical_fact_line")
    if not isinstance(canonical, Mapping) or set(canonical) != CANONICAL_FACT_LINE_KEYS:
        raise ManagerScreenDecisionQualityError(
            "canonical fact line fields do not match the v1 contract"
        )
    if canonical.get("schema_version") != 1:
        raise ManagerScreenDecisionQualityError(
            "canonical fact line schema_version must be 1"
        )
    _text(canonical.get("text"), "canonical_fact_line.text")
    _text(
        canonical.get("source_evidence_id"),
        "canonical_fact_line.source_evidence_id",
    )
    digest = canonical.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ManagerScreenDecisionQualityError(
            "canonical_fact_line.sha256 must be a lowercase SHA-256"
        )
    unsigned = {key: canonical[key] for key in canonical if key != "sha256"}
    try:
        expected_digest = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    except SealingError as exc:
        raise ManagerScreenDecisionQualityError(
            f"canonical fact line is not canonical JSON: {exc}"
        ) from exc
    if digest != expected_digest:
        raise ManagerScreenDecisionQualityError(
            "canonical_fact_line.sha256 does not match its content"
        )

    flags = value.get("mandatory_risk_flags")
    if not isinstance(flags, list):
        raise ManagerScreenDecisionQualityError("mandatory_risk_flags must be an array")
    previous_category_index = -1
    seen_flag_ids: set[str] = set()
    for index, flag in enumerate(flags):
        if not isinstance(flag, Mapping) or set(flag) != RISK_FLAG_KEYS:
            raise ManagerScreenDecisionQualityError(
                f"mandatory_risk_flags[{index}] fields do not match the contract"
            )
        flag_id = _text(flag.get("flag_id"), f"mandatory_risk_flags[{index}].flag_id")
        category = flag.get("category")
        if category not in RISK_CATEGORIES or flag_id != category:
            raise ManagerScreenDecisionQualityError(
                f"mandatory_risk_flags[{index}] has an invalid category or flag_id"
            )
        category_index = RISK_CATEGORIES.index(category)
        if category_index <= previous_category_index or flag_id in seen_flag_ids:
            raise ManagerScreenDecisionQualityError(
                "mandatory_risk_flags must be unique and in canonical category order"
            )
        previous_category_index = category_index
        seen_flag_ids.add(flag_id)
        _text(flag.get("summary"), f"mandatory_risk_flags[{index}].summary")
        _validate_unique_string_array(
            flag.get("evidence_ids"),
            f"mandatory_risk_flags[{index}].evidence_ids",
        )
        _validate_unique_string_array(
            flag.get("signals"),
            f"mandatory_risk_flags[{index}].signals",
        )
    return {
        "schema_version": 1,
        "canonical_fact_line": dict(canonical),
        "mandatory_risk_flags": [dict(flag) for flag in flags],
    }


def _validate_unique_string_array(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() == item and item for item in value)
        or len(value) != len(set(value))
    ):
        raise ManagerScreenDecisionQualityError(
            f"{label} must be a non-empty unique string array"
        )
    return list(value)


def _latest_annual(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, list):
        return None
    periods = [
        item
        for item in value
        if isinstance(item, Mapping) and _report_date(item) is not None
    ]
    return max(periods, key=lambda item: str(item["report_date"])) if periods else None


def _period_or_none(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping) or _report_date(value) is None:
        return None
    return value


def _report_date(period: Mapping[str, Any] | None) -> str | None:
    if not isinstance(period, Mapping):
        return None
    value = period.get("report_date")
    if isinstance(value, str) and _DATE_RE.fullmatch(value):
        return value
    return None


def _interim_report_type(period: Mapping[str, Any] | None) -> str | None:
    if period is None:
        return None
    value = period.get("report_type")
    normalized = value.strip().casefold() if isinstance(value, str) else ""
    if any(token in normalized for token in ("一季", "1季", "第一季", "q1")):
        return "一季报"
    if any(token in normalized for token in ("中报", "半年", "半年度", "q2")):
        return "中报"
    if any(token in normalized for token in ("三季", "3季", "第三季", "q3")):
        return "三季报"
    report_date = _report_date(period)
    if report_date is not None:
        month_day = report_date[5:]
        if month_day == "03-31":
            return "一季报"
        if month_day == "06-30":
            return "中报"
        if month_day == "09-30":
            return "三季报"
    raise ManagerScreenDecisionQualityError(
        "latest_interim report_type must identify 一季报、中报或三季报"
    )


def _balance_sheet(period: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(period, Mapping):
        return None
    value = period.get("balance_sheet")
    return value if isinstance(value, Mapping) else None


def _period_number(period: Mapping[str, Any] | None, field: str) -> int | float | None:
    if not isinstance(period, Mapping):
        return None
    return _number(period.get(field))


def _mapping_number(value: Mapping[str, Any] | None, field: str) -> int | float | None:
    if not isinstance(value, Mapping):
        return None
    return _number(value.get(field))


def _number(value: Any) -> int | float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        return None
    return value


def _required_number(value: Any, label: str) -> int | float:
    normalized = _number(value)
    if normalized is None:
        raise ManagerScreenDecisionQualityError(f"{label} must be a finite number")
    return normalized


def _format_cny(value: int | float | None) -> str:
    if value is None:
        return "缺失"
    amount = (Decimal(str(value)) / Decimal("100000000")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return f"{amount:.2f}亿元"


def _is_non_standard_audit_opinion(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = re.sub(r"[\s，,。；;：:（）()]", "", value)
    return normalized not in _STANDARD_AUDIT_OPINIONS


def _single_line_text(value: Any) -> str:
    return " ".join(str(value).split())


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerScreenDecisionQualityError(f"{label} must be a non-empty string")
    normalized = value.strip()
    if normalized != value:
        raise ManagerScreenDecisionQualityError(
            f"{label} must not have leading or trailing whitespace"
        )
    return normalized
