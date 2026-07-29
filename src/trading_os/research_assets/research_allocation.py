from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from .coverage_store import (
    COMPANIES_FILE,
    RESEARCH_QUEUE_FILE,
    SCREENING_FILE,
    read_jsonl,
    serialized_coverage_write,
    write_jsonl,
)
from .sealing import atomic_write_bytes


class ResearchAllocationError(ValueError):
    """Raised when research capacity or a quick profile is malformed."""


POLICY_KEYS = {
    "triage_administrative_batch_size",
    "candidate_pool_capacity_per_cycle",
    "quick_profile_capacity_per_cycle",
    "stage_capacity_per_cycle",
    "effort_budget_hours",
    "selection_slots",
    "risk_cluster_caps",
    "industry_evidence_requirements",
    "minimum_s1_sources_for_deep_research",
    "minimum_counterevidence_for_quick_profile",
    "minimum_base_expected_annual_return_for_deep_research",
    "minimum_base_expected_annual_return_for_underwriting",
    "structural_stop_reason_codes",
    "reactivation_trigger_types",
    "ranking_principle",
    "research_value_principle",
    "stop_principle",
    "comparison_principle",
}
STAGE_CAPACITY_KEYS = {"scoped_research", "deep_research", "underwriting"}
EFFORT_BUDGET_KEYS = {
    "rapid_triage",
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
    "underwriting",
}
SELECTION_LENSES = (
    "balanced",
    "value_income",
    "quality_compounder",
    "financial_specialist",
    "cyclical_specialist",
    "crisis_mispricing",
    "information_change",
    "false_negative_audit",
)
PROFILE_KEYS = {
    "research_stage",
    "symbol",
    "as_of",
    "information_cutoff",
    "s1_source_count",
    "circle_of_competence",
    "business_model_understood",
    "survival_status",
    "governance_status",
    "normalized_earnings_status",
    "valuation",
    "variant_perception",
    "decisive_unknowns",
    "counterevidence",
    "structural_stop_reasons",
    "revisit_triggers",
}
VALUATION_KEYS = {
    "current_price",
    "rough_fair_value_range",
    "base_expected_annual_return",
    "bull_expected_annual_return",
    "market_implied_assumptions_tested",
}
TRIGGER_KEYS = {"type", "condition", "reason"}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
CRISIS_REASON_CODES = {
    "extreme_low_pe_requires_one_off_verification",
    "negative_pe_requires_normalization",
    "negative_reported_roe",
    "reported_growth_under_pressure",
    "single_period_growth_outlier_requires_verification",
    "single_period_roe_outlier_requires_verification",
}


def allocate_research_capacity(
    ranking: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    policy_version: str,
) -> dict[str, Any]:
    limits = _validate_policy(policy)
    policy_ref = _require_text(policy_version, "policy_version")
    if not isinstance(ranking, Mapping):
        raise ResearchAllocationError("ranking must be an object")
    raw_items = ranking.get("items")
    if not isinstance(raw_items, list):
        raise ResearchAllocationError("ranking.items must be an array")
    items = [_normalize_ranking_item(item) for item in raw_items]
    symbols = [item["symbol"] for item in items]
    if len(symbols) != len(set(symbols)):
        raise ResearchAllocationError("ranking symbols must be unique")

    capacity = min(limits["candidate_pool_capacity_per_cycle"], len(items))
    selected_symbols: set[str] = set()
    selected_by: dict[str, list[str]] = {}
    selected_cluster_counts: dict[str, int] = {}
    lens_counts: dict[str, int] = {}
    generated_at = _require_text(ranking.get("generated_at"), "ranking.generated_at")
    retriage_completed = ranking.get("retriage_completed", False)
    if not isinstance(retriage_completed, bool):
        raise ResearchAllocationError("ranking.retriage_completed must be boolean")

    lens_pools = {
        lens: _lens_pool(lens, items, generated_at) for lens in SELECTION_LENSES
    }
    lens_shortlists = {
        lens: {
            item["symbol"]
            for item in pool[: limits["selection_slots"][lens]]
        }
        for lens, pool in lens_pools.items()
    }
    matched_lenses = {
        item["symbol"]: [
            lens for lens in SELECTION_LENSES if item["symbol"] in lens_shortlists[lens]
        ]
        for item in items
    }
    rapid_cap = limits["risk_cluster_caps"]["rapid_triage"]

    for lens in SELECTION_LENSES:
        quota = min(limits["selection_slots"][lens], capacity - len(selected_symbols))
        if quota <= 0:
            lens_counts[lens] = 0
            continue
        pool = lens_pools[lens]
        added = 0
        for item in pool:
            symbol = item["symbol"]
            if symbol in selected_symbols:
                continue
            if not _cluster_has_capacity(
                item["economic_risk_cluster"],
                counts=selected_cluster_counts,
                cap=rapid_cap,
            ):
                continue
            selected_symbols.add(symbol)
            selected_by.setdefault(symbol, []).append(lens)
            _increment_cluster(item["economic_risk_cluster"], selected_cluster_counts)
            added += 1
            if added >= quota:
                break
        lens_counts[lens] = added

    if len(selected_symbols) < capacity:
        for item in _lens_pool("balanced", items, generated_at):
            symbol = item["symbol"]
            if symbol in selected_symbols:
                continue
            if not _cluster_has_capacity(
                item["economic_risk_cluster"],
                counts=selected_cluster_counts,
                cap=rapid_cap,
            ):
                continue
            selected_symbols.add(symbol)
            selected_by.setdefault(symbol, []).append("capacity_fill")
            _increment_cluster(item["economic_risk_cluster"], selected_cluster_counts)
            if len(selected_symbols) >= capacity:
                break

    selected = []
    deferred = []
    for item in items:
        if item["symbol"] in selected_symbols:
            selected.append(
                {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "stage": "rapid_triage",
                    "effort_budget_hours": limits["effort_budget_hours"][
                        "rapid_triage"
                    ],
                    "selected_by": selected_by[item["symbol"]],
                    "matched_lenses": matched_lenses[item["symbol"]],
                    "economic_risk_cluster": item["economic_risk_cluster"],
                    "ranking_confidence": item["score_confidence"],
                    "reason_codes": [
                        "cheap_map_selected_for_rapid_triage",
                        "no_direct_formal_profile_from_public_score",
                    ],
                }
            )
        else:
            deferred.append(
                {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "stage": "catalog",
                    "reason_code": "research_capacity_allocated_to_higher_value_of_information",
                    "reactivation_trigger_types": list(
                        limits["reactivation_trigger_types"]
                    ),
                }
            )

    confidence_counts: dict[str, int] = {}
    for item in items:
        confidence = item["score_confidence"]
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
    warnings: list[str] = []
    reliable_count = confidence_counts.get("high", 0) + confidence_counts.get(
        "medium", 0
    )
    if items and reliable_count / len(items) < 0.25:
        warnings.append("ranking_confidence_too_low_for_score_led_promotion")

    raw_excluded = ranking.get("excluded", [])
    if not isinstance(raw_excluded, list):
        raise ResearchAllocationError("ranking.excluded must be an array")
    return {
        "schema_version": 2,
        "ranking_generated_at": generated_at,
        "retriage_completed": retriage_completed,
        "ranking_content_sha256": _mapping_sha256(ranking),
        "policy_version": policy_ref,
        "policy_payload_sha256": _mapping_sha256(policy),
        "principle": limits["ranking_principle"],
        "capacity": {
            "rapid_triage": capacity,
            "quick_profile": min(
                limits["quick_profile_capacity_per_cycle"],
                capacity,
            ),
            **limits["stage_capacity_per_cycle"],
        },
        "effort_budget_hours": limits["effort_budget_hours"],
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "warnings": warnings,
        "lens_counts": lens_counts,
        "risk_cluster_counts": dict(sorted(selected_cluster_counts.items())),
        "selected_count": len(selected),
        "deferred_count": len(deferred),
        "selected": selected,
        "deferred": deferred,
        "excluded": raw_excluded,
    }


@serialized_coverage_write
def apply_research_allocation(
    allocation: Mapping[str, Any],
    *,
    ranking: Mapping[str, Any],
    root: str | Path,
    applied_at: dt.datetime,
) -> dict[str, Any]:
    """Materialize one finite-capacity cycle into screening and queue JSONL.

    The public ranking remains only a map. Selected companies receive a
    fifteen-minute rapid-triage budget; ordinary deferred companies remain in the
    auditable catalog, and manual/hard exclusions retain their separate gates.
    """

    if applied_at.tzinfo is None or applied_at.utcoffset() is None:
        raise ResearchAllocationError("applied_at must include a UTC offset")
    if not isinstance(allocation, Mapping) or not isinstance(ranking, Mapping):
        raise ResearchAllocationError("allocation and ranking must be objects")
    if allocation.get("ranking_content_sha256") != _mapping_sha256(ranking):
        raise ResearchAllocationError("allocation ranking SHA-256 mismatch")

    raw_items = ranking.get("items")
    selected = allocation.get("selected")
    deferred = allocation.get("deferred")
    excluded = allocation.get("excluded")
    if not all(isinstance(value, list) for value in (raw_items, selected, deferred, excluded)):
        raise ResearchAllocationError("allocation partitions must be arrays")

    ranking_items = {
        _symbol(item.get("symbol")): item
        for item in raw_items
        if isinstance(item, Mapping)
    }
    if len(ranking_items) != len(raw_items):
        raise ResearchAllocationError("ranking items must be unique objects")
    selected_items = _allocation_partition(selected, "rapid_triage")
    deferred_items = _allocation_partition(deferred, "catalog")
    if set(selected_items) & set(deferred_items):
        raise ResearchAllocationError("selected and deferred symbols overlap")
    if set(selected_items) | set(deferred_items) != set(ranking_items):
        raise ResearchAllocationError(
            "selected and deferred symbols must partition ranking items"
        )

    base = Path(root)
    companies = {
        _symbol(item.get("symbol")): item
        for item in read_jsonl(base / COMPANIES_FILE)
    }
    screening_records = read_jsonl(base / SCREENING_FILE)
    queue_records = read_jsonl(base / RESEARCH_QUEUE_FILE)
    screening_by_symbol = {
        _symbol(item.get("symbol")): dict(item) for item in screening_records
    }
    queue_by_symbol = {
        _symbol(item.get("symbol")): dict(item) for item in queue_records
    }
    allocation_sha = _mapping_sha256(allocation)
    retriage_completed = allocation.get("retriage_completed", False)
    if not isinstance(retriage_completed, bool):
        raise ResearchAllocationError("allocation.retriage_completed must be boolean")
    applied_iso = applied_at.isoformat()
    preserved_formal_symbols: set[str] = set()

    for symbol, allocation_item in selected_items.items():
        company = _required_company(companies, symbol)
        ranking_item = ranking_items[symbol]
        existing_queue = queue_by_symbol.get(symbol)
        if _has_formal_research_progress(existing_queue) and not retriage_completed:
            preserved_formal_symbols.add(symbol)
            continue
        if retriage_completed:
            existing_queue = _preserve_prior_queue_state(
                existing_queue,
                reallocated_at=applied_iso,
            )
        selected_by = _text_list(
            allocation_item.get("selected_by"),
            f"{symbol}.selected_by",
        )
        matched_lenses = _text_list(
            allocation_item.get("matched_lenses"),
            f"{symbol}.matched_lenses",
            allow_empty=True,
        )
        risk_cluster = _require_text(
            allocation_item.get("economic_risk_cluster"),
            f"{symbol}.economic_risk_cluster",
        )
        priority = _selected_priority(selected_by)
        screening_by_symbol[symbol] = _screening_record(
            screening_by_symbol.get(symbol),
            company=company,
            decision="rapid_triage",
            priority=priority,
            reason="多视角全市场分配获得本周期快速甄别预算。",
            evidence=[
                f"ranking_sha256:{allocation['ranking_content_sha256']}",
                f"allocation_sha256:{allocation_sha}",
                f"selected_by:{','.join(selected_by)}",
                f"ranking_confidence:{ranking_item['score_confidence']}",
            ],
            next_action=(
                "在15分钟预算内完成快速甄别并封存；待完整候选批次横向比较后，"
                "少数公司才能进入正式画像。"
            ),
            allocation_at=applied_iso,
        )
        queue_by_symbol[symbol] = _rapid_triage_queue_record(
            existing_queue,
            company=company,
            priority=priority,
            status="pending",
            reason="多视角全市场分配获得本周期快速甄别预算。",
            next_action="完成快速甄别并等待全批次横向比较。",
            allocation_sha=allocation_sha,
            selected_by=selected_by,
            matched_lenses=matched_lenses,
            economic_risk_cluster=risk_cluster,
            effort_budget_hours=allocation_item["effort_budget_hours"],
        )

    for symbol in deferred_items:
        company = _required_company(companies, symbol)
        existing_queue = queue_by_symbol.get(symbol)
        if _has_formal_research_progress(existing_queue):
            preserved_formal_symbols.add(symbol)
            continue
        screening_by_symbol[symbol] = _screening_record(
            screening_by_symbol.get(symbol),
            company=company,
            decision="catalog",
            priority=None,
            reason="本周期研究容量分配给信息价值更高的候选，保留在全市场目录。",
            evidence=[
                f"ranking_sha256:{allocation['ranking_content_sha256']}",
                f"allocation_sha256:{allocation_sha}",
                "reactivation:filing,price,event,thesis",
            ],
            next_action="等待下一研究周期或财报、价格、事件、论点触发后重新竞争预算。",
            allocation_at=applied_iso,
        )
        existing = existing_queue
        priority = (
            int(existing["priority"])
            if existing is not None and isinstance(existing.get("priority"), int)
            else 5
        )
        queue_by_symbol[symbol] = _rapid_triage_queue_record(
            existing,
            company=company,
            priority=priority,
            status="requires_rebaseline",
            reason="本周期未获得快速画像容量，保留可恢复候选状态。",
            next_action="等待下一研究周期或结构化重启触发器。",
            allocation_sha=allocation_sha,
            selected_by=[],
            matched_lenses=[],
            economic_risk_cluster=str(
                ranking_items[symbol].get("economic_risk_cluster") or "unclassified"
            ),
            effort_budget_hours=allocation["effort_budget_hours"]["rapid_triage"],
        )

    manual_count = 0
    hard_exclusion_count = 0
    for item in excluded:
        if not isinstance(item, Mapping):
            raise ResearchAllocationError("excluded items must be objects")
        symbol = _symbol(item.get("symbol"))
        category = _require_text(item.get("category"), f"{symbol}.category")
        reason_code = _require_text(
            item.get("reason_code"),
            f"{symbol}.reason_code",
        )
        company = _required_company(companies, symbol)
        existing = queue_by_symbol.get(symbol)
        priority = (
            int(existing["priority"])
            if existing is not None and isinstance(existing.get("priority"), int)
            else 3
        )
        if category in {"manual_review", "data_error"}:
            manual_count += 1
            screening_by_symbol[symbol] = _screening_record(
                screening_by_symbol.get(symbol),
                company=company,
                decision="needs_manual_review",
                priority=priority,
                reason=f"机器分配前必须人工解决：{reason_code}",
                evidence=[reason_code, f"allocation_sha256:{allocation_sha}"],
                next_action="主 agent 先确定证券状态、数据冲突或特殊风险的研究路径。",
                allocation_at=applied_iso,
            )
            queue_by_symbol[symbol] = _rapid_triage_queue_record(
                existing,
                company=company,
                priority=priority,
                status="needs_review",
                reason=f"机器分配前必须人工解决：{reason_code}",
                next_action="人工复核后再决定是否进入快速甄别。",
                allocation_sha=allocation_sha,
                selected_by=[],
                matched_lenses=[],
                economic_risk_cluster=str(
                    (existing or {}).get("economic_risk_cluster") or "unclassified"
                ),
                effort_budget_hours=allocation["effort_budget_hours"]["rapid_triage"],
            )
        elif category == "hard_exclusion":
            hard_exclusion_count += 1
            screening_by_symbol[symbol] = _screening_record(
                screening_by_symbol.get(symbol),
                company=company,
                decision="hard_exclusion",
                priority=None,
                reason=f"不构成当前普通A股投资对象：{reason_code}",
                evidence=[reason_code, f"allocation_sha256:{allocation_sha}"],
                next_action="仅在证券状态或法律投资属性改变时重新纳入。",
                allocation_at=applied_iso,
            )
            queue_by_symbol[symbol] = _rapid_triage_queue_record(
                existing,
                company=company,
                priority=priority,
                status="skipped",
                reason=f"不构成当前普通A股投资对象：{reason_code}",
                next_action="证券状态改变后重新筛选。",
                allocation_sha=allocation_sha,
                selected_by=[],
                matched_lenses=[],
                economic_risk_cluster=str(
                    (existing or {}).get("economic_risk_cluster") or "unclassified"
                ),
                effort_budget_hours=allocation["effort_budget_hours"]["rapid_triage"],
            )
        else:
            raise ResearchAllocationError(
                f"unsupported excluded category for {symbol}: {category}"
            )

    completed_count = 0
    for symbol, queue_item in queue_by_symbol.items():
        if queue_item.get("status") != "completed" or symbol not in companies:
            continue
        if queue_item.get("task_type") in {
            "rapid_triage",
            "quick_profile",
            "targeted_followup",
            "scoped_research",
        }:
            continue
        completed_count += 1
        company = companies[symbol]
        screening_by_symbol[symbol] = _screening_record(
            screening_by_symbol.get(symbol),
            company=company,
            decision="watch_only",
            priority=None,
            reason="已有结构化研究结果，不重复购买快速甄别预算。",
            evidence=[
                f"result_path:{queue_item.get('result_path')}",
                f"allocation_sha256:{allocation_sha}",
            ],
            next_action="按财报、价格和论点触发器复核。",
            allocation_at=applied_iso,
        )

    write_jsonl(base / SCREENING_FILE, list(screening_by_symbol.values()))
    write_jsonl(base / RESEARCH_QUEUE_FILE, list(queue_by_symbol.values()))
    return {
        "schema_version": 1,
        "allocation_sha256": allocation_sha,
        "applied_at": applied_iso,
        "selected_rapid_triage_count": len(selected_items),
        "deferred_catalog_count": len(deferred_items),
        "manual_review_count": manual_count,
        "hard_exclusion_count": hard_exclusion_count,
        "completed_watch_count": completed_count,
        "preserved_formal_research_count": len(preserved_formal_symbols),
    }


def evaluate_quick_profile(
    profile: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    limits = _validate_policy(policy)
    normalized = _normalize_profile(profile, limits)
    reasons: set[str] = set()
    stop_reasons = set(normalized["structural_stop_reasons"])
    valuation = normalized["valuation"]
    base_return = valuation["base_expected_annual_return"]
    bull_return = valuation["bull_expected_annual_return"]
    deep_threshold = limits["minimum_base_expected_annual_return_for_deep_research"]

    if stop_reasons:
        if normalized["s1_source_count"] < 1:
            stage = "targeted_followup"
            reasons.add("structural_stop_requires_primary_evidence")
        else:
            stage = "conditional_stop"
            reasons.update(stop_reasons)
    elif normalized["survival_status"] == "fail":
        if normalized["s1_source_count"] < 1:
            stage = "targeted_followup"
            reasons.add("survival_failure_requires_primary_evidence")
        else:
            stage = "conditional_stop"
            reasons.add("survival_test_failed")
    elif normalized["governance_status"] == "uninvestable":
        if normalized["s1_source_count"] < 1:
            stage = "targeted_followup"
            reasons.add("governance_failure_requires_primary_evidence")
        else:
            stage = "conditional_stop"
            reasons.add("governance_uninvestable")
    elif normalized["circle_of_competence"] == "outside":
        stage = "reassign_or_stop"
        reasons.add("outside_current_agent_circle_of_competence")
    elif bull_return < deep_threshold:
        stage = "price_watch"
        reasons.add("no_plausible_current_return_path")
    elif _profile_has_basic_gaps(normalized):
        stage = "targeted_followup"
        reasons.add("decisive_evidence_gap")
    elif base_return < deep_threshold:
        stage = "price_watch"
        reasons.add("base_return_below_deep_research_threshold")
    elif normalized["research_stage"] == "quick_profile":
        stage = "scoped_research"
        reasons.add("credible_path_requires_scoped_research")
    elif _scoped_research_has_gaps(normalized, limits):
        stage = "targeted_followup"
        reasons.add("scoped_research_not_ready_for_deep_research")
    else:
        stage = "deep_research"
        reasons.add("credible_investment_path_requires_full_research")

    if stage in {"price_watch", "conditional_stop"} and not normalized[
        "revisit_triggers"
    ]:
        raise ResearchAllocationError(
            f"{stage} quick profile must contain at least one revisit trigger"
        )
    effort_key = {
        "targeted_followup": "targeted_followup",
        "scoped_research": "scoped_research",
        "deep_research": "deep_research",
    }.get(stage)
    return {
        "schema_version": 1,
        "symbol": normalized["symbol"],
        "as_of": normalized["as_of"],
        "evaluated_stage": normalized["research_stage"],
        "next_stage": stage,
        "maximum_additional_effort_hours": (
            limits["effort_budget_hours"][effort_key] if effort_key else 0.0
        ),
        "reason_codes": sorted(reasons),
        "base_expected_annual_return": base_return,
        "underwriting_return_threshold": limits[
            "minimum_base_expected_annual_return_for_underwriting"
        ],
        "revisit_triggers": normalized["revisit_triggers"],
        "portfolio_action": None,
    }


def write_research_allocation(
    output_path: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    target = Path(output_path)
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(target, content)


def _allocation_partition(
    items: list[Any],
    expected_stage: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise ResearchAllocationError("allocation items must be objects")
        symbol = _symbol(item.get("symbol"))
        if item.get("stage") != expected_stage:
            raise ResearchAllocationError(
                f"{symbol} allocation stage must be {expected_stage}"
            )
        if symbol in result:
            raise ResearchAllocationError(f"duplicate allocation symbol: {symbol}")
        result[symbol] = item
    return result


def _required_company(
    companies: Mapping[str, Mapping[str, Any]],
    symbol: str,
) -> Mapping[str, Any]:
    company = companies.get(symbol)
    if company is None:
        raise ResearchAllocationError(f"company snapshot missing: {symbol}")
    return company


def _selected_priority(selected_by: list[str]) -> int:
    lenses = set(selected_by)
    if "balanced" in lenses:
        return 1
    if lenses & {
        "value_income",
        "quality_compounder",
        "financial_specialist",
        "cyclical_specialist",
    }:
        return 2
    if lenses & {"crisis_mispricing", "information_change"}:
        return 3
    return 4


def _has_formal_research_progress(
    record: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(record, Mapping):
        return False
    if (
        record.get("task_type") == "quick_profile"
        and record.get("status") == "running"
    ):
        return True
    if record.get("task_type") in {"scoped_research", "deep_research"}:
        return True
    if (
        record.get("task_type") in {"initial_research", "followup_review"}
        and record.get("status") in {"running", "completed"}
    ):
        return True
    return any(
        isinstance(item, Mapping)
        and item.get("stage") in {"quick_profile", "scoped_research"}
        and item.get("status") == "completed"
        for item in (record.get("stage_history") or [])
    )


def _preserve_prior_queue_state(
    existing: Mapping[str, Any] | None, *, reallocated_at: str
) -> dict[str, Any] | None:
    if existing is None or existing.get("status") != "completed":
        return dict(existing) if existing is not None else None
    history = list(existing.get("stage_history") or [])
    snapshot = {
        "stage": str(existing.get("task_type") or "legacy_research"),
        "status": "completed",
        "finished_at": existing.get("finished_at") or reallocated_at,
        "agent": existing.get("assigned_agent"),
        "result_path": existing.get("result_path"),
        "evaluation_path": existing.get("profile_evaluation_path"),
        "next_stage": "rapid_triage_recheck",
    }
    if not history or history[-1] != snapshot:
        history.append(snapshot)
    result = dict(existing)
    result["stage_history"] = history
    return result


def _screening_record(
    existing: Mapping[str, Any] | None,
    *,
    company: Mapping[str, Any],
    decision: str,
    priority: int | None,
    reason: str,
    evidence: list[str],
    next_action: str,
    allocation_at: str,
) -> dict[str, Any]:
    record = dict(existing or {})
    record.update(
        {
            "symbol": _symbol(company.get("symbol")),
            "name": _require_text(company.get("name"), "company.name"),
            "decision": decision,
            "priority": priority,
            "reason": reason,
            "evidence": evidence,
            "next_action": next_action,
            "allocation_at": allocation_at,
        }
    )
    return record


def _rapid_triage_queue_record(
    existing: Mapping[str, Any] | None,
    *,
    company: Mapping[str, Any],
    priority: int,
    status: str,
    reason: str,
    next_action: str,
    allocation_sha: str,
    selected_by: list[str],
    matched_lenses: list[str],
    economic_risk_cluster: str,
    effort_budget_hours: float,
) -> dict[str, Any]:
    symbol = _symbol(company.get("symbol"))
    ticker = symbol.split(":", 1)[1]
    record = dict(existing or {})
    record.update(
        {
            "symbol": symbol,
            "name": _require_text(company.get("name"), f"{symbol}.name"),
            "task_type": "rapid_triage",
            "priority": priority,
            "status": status,
            "reason": reason,
            "target_company_dir": f"research/companies/CN/{ticker}",
            "assigned_agent": None,
            "started_at": None,
            "finished_at": None,
            "result_path": None,
            "failure_reason": None,
            "next_action": next_action,
            "effort_budget_hours": float(effort_budget_hours),
            "preceding_stage": "machine_triage",
            "stop_conditions": [
                "快速甄别发现明确生存、治理或财务可信度阻断项",
                "当前价格明显不具备进一步研究赔率",
                "继续研究不太可能改变组合决策",
            ],
            "allocation_sha256": allocation_sha,
            "selected_by": selected_by,
            "matched_lenses": matched_lenses,
            "economic_risk_cluster": economic_risk_cluster,
            "triage_cycle_id": None,
            "triage_disposition": None,
            "triage_priority_score": None,
            "triage_selection_path": None,
            "profile_cycle_id": None,
            "profile_evaluation_path": None,
            "profile_recorded_at": None,
            "profile_quick_selection_path": None,
            "profile_scoped_selection_path": None,
        }
    )
    return record


def _validate_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        raise ResearchAllocationError("research allocation policy must be an object")
    if set(policy) != POLICY_KEYS:
        raise ResearchAllocationError(
            "research allocation policy fields do not match contract"
        )
    result = dict(policy)
    result["triage_administrative_batch_size"] = _positive_int(
        policy.get("triage_administrative_batch_size"),
        "triage_administrative_batch_size",
    )
    result["candidate_pool_capacity_per_cycle"] = _positive_int(
        policy.get("candidate_pool_capacity_per_cycle"),
        "candidate_pool_capacity_per_cycle",
    )
    result["quick_profile_capacity_per_cycle"] = _positive_int(
        policy.get("quick_profile_capacity_per_cycle"),
        "quick_profile_capacity_per_cycle",
    )
    result["stage_capacity_per_cycle"] = _exact_numeric_mapping(
        policy.get("stage_capacity_per_cycle"),
        STAGE_CAPACITY_KEYS,
        "stage_capacity_per_cycle",
        integer=True,
    )
    result["effort_budget_hours"] = _exact_numeric_mapping(
        policy.get("effort_budget_hours"),
        EFFORT_BUDGET_KEYS,
        "effort_budget_hours",
    )
    result["selection_slots"] = _exact_numeric_mapping(
        policy.get("selection_slots"),
        set(SELECTION_LENSES),
        "selection_slots",
        integer=True,
    )
    result["risk_cluster_caps"] = _exact_numeric_mapping(
        policy.get("risk_cluster_caps"),
        {
            "rapid_triage",
            "quick_profile",
            "scoped_research",
            "deep_research",
            "underwriting",
        },
        "risk_cluster_caps",
        integer=True,
    )
    raw_requirements = policy.get("industry_evidence_requirements")
    if not isinstance(raw_requirements, Mapping):
        raise ResearchAllocationError("industry_evidence_requirements must be an object")
    result["industry_evidence_requirements"] = dict(raw_requirements)
    if sum(result["selection_slots"].values()) != result[
        "candidate_pool_capacity_per_cycle"
    ]:
        raise ResearchAllocationError(
            "selection_slots must sum to candidate_pool_capacity_per_cycle"
        )
    if (
        result["quick_profile_capacity_per_cycle"]
        > result["candidate_pool_capacity_per_cycle"]
    ):
        raise ResearchAllocationError(
            "quick_profile_capacity_per_cycle must not exceed "
            "candidate_pool_capacity_per_cycle"
        )
    result["minimum_s1_sources_for_deep_research"] = _positive_int(
        policy.get("minimum_s1_sources_for_deep_research"),
        "minimum_s1_sources_for_deep_research",
    )
    result["minimum_counterevidence_for_quick_profile"] = _positive_int(
        policy.get("minimum_counterevidence_for_quick_profile"),
        "minimum_counterevidence_for_quick_profile",
    )
    for field in (
        "minimum_base_expected_annual_return_for_deep_research",
        "minimum_base_expected_annual_return_for_underwriting",
    ):
        result[field] = _number(policy.get(field), field)
        if not 0 <= result[field] <= 1:
            raise ResearchAllocationError(f"{field} must be between 0 and 1")
    if (
        result["minimum_base_expected_annual_return_for_deep_research"]
        > result["minimum_base_expected_annual_return_for_underwriting"]
    ):
        raise ResearchAllocationError(
            "deep research return threshold must not exceed underwriting threshold"
        )
    result["structural_stop_reason_codes"] = _text_list(
        policy.get("structural_stop_reason_codes"),
        "structural_stop_reason_codes",
    )
    result["reactivation_trigger_types"] = _text_list(
        policy.get("reactivation_trigger_types"),
        "reactivation_trigger_types",
    )
    for field in (
        "ranking_principle",
        "research_value_principle",
        "stop_principle",
        "comparison_principle",
    ):
        result[field] = _require_text(policy.get(field), field)
    return result


def _normalize_ranking_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise ResearchAllocationError("ranking item must be an object")
    symbol = _symbol(item.get("symbol"))
    dimensions = item.get("dimensions")
    if not isinstance(dimensions, Mapping):
        raise ResearchAllocationError(f"{symbol} dimensions must be an object")
    required_dimensions = {
        "value_dislocation",
        "operating_capital_quality",
        "permanent_loss_protection",
        "information_update_urgency",
        "verifiable_catalyst_odds",
        "evidence_availability",
    }
    if not required_dimensions <= set(dimensions):
        raise ResearchAllocationError(f"{symbol} ranking dimensions are incomplete")
    public = item.get("public_snapshot")
    if not isinstance(public, Mapping):
        raise ResearchAllocationError(f"{symbol} public_snapshot must be an object")
    penalties = item.get("penalties")
    if not isinstance(penalties, list):
        raise ResearchAllocationError(f"{symbol} penalties must be an array")
    reasons = _text_list(item.get("reason_codes"), f"{symbol}.reason_codes")
    confidence = _require_text(item.get("score_confidence"), "score_confidence")
    if confidence not in {"high", "medium", "low"}:
        raise ResearchAllocationError(f"unsupported score_confidence: {confidence}")
    return {
        "symbol": symbol,
        "name": _require_text(item.get("name"), f"{symbol}.name"),
        "total_score": _number(item.get("total_score"), f"{symbol}.total_score"),
        "score_confidence": confidence,
        "economic_risk_cluster": _require_text(
            item.get("economic_risk_cluster"),
            f"{symbol}.economic_risk_cluster",
        ),
        "dimensions": {
            key: _number(dimensions.get(key), f"{symbol}.dimensions.{key}")
            for key in required_dimensions
        },
        "reason_codes": reasons,
        "public_snapshot": dict(public),
    }


def _lens_pool(
    lens: str,
    items: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    if lens == "false_negative_audit":
        return sorted(
            items,
            key=lambda item: (
                _stable_hash(generated_at, item["symbol"]),
                item["symbol"],
            ),
        )

    def eligible(item: dict[str, Any]) -> bool:
        if lens == "financial_specialist":
            return item["economic_risk_cluster"] in {
                "credit_cycle",
                "insurance_rates",
                "capital_markets",
            }
        if lens == "cyclical_specialist":
            return item["economic_risk_cluster"] == "commodity_cycle"
        if lens == "value_income":
            return item["economic_risk_cluster"] not in {
                "credit_cycle",
                "insurance_rates",
                "capital_markets",
                "property_credit_cycle",
            }
        if lens == "crisis_mispricing":
            return bool(set(item["reason_codes"]) & CRISIS_REASON_CODES)
        return True

    score_functions: dict[str, Callable[[dict[str, Any]], float]] = {
        "balanced": lambda item: item["total_score"],
        "value_income": lambda item: (
            item["dimensions"]["value_dislocation"]
            + item["dimensions"]["permanent_loss_protection"]
            + _optional_public_number(item, "dividend_yield_pct")
        ),
        "quality_compounder": lambda item: (
            item["dimensions"]["operating_capital_quality"]
            + item["dimensions"]["permanent_loss_protection"]
            + item["dimensions"]["verifiable_catalyst_odds"]
        ),
        "financial_specialist": lambda item: (
            item["dimensions"]["value_dislocation"]
            + item["dimensions"]["operating_capital_quality"]
        ),
        "cyclical_specialist": lambda item: (
            item["dimensions"]["permanent_loss_protection"]
            + item["dimensions"]["value_dislocation"]
        ),
        "crisis_mispricing": lambda item: (
            item["dimensions"]["permanent_loss_protection"]
            + item["dimensions"]["information_update_urgency"]
            + item["dimensions"]["value_dislocation"]
        ),
        "information_change": lambda item: (
            item["dimensions"]["information_update_urgency"]
            + item["dimensions"]["verifiable_catalyst_odds"]
        ),
    }
    score = score_functions[lens]
    return sorted(
        (item for item in items if eligible(item)),
        key=lambda item: (-score(item), item["symbol"]),
    )


def _cluster_has_capacity(cluster: str, *, counts: Mapping[str, int], cap: int) -> bool:
    return cluster == "diversified" or counts.get(cluster, 0) < cap


def _increment_cluster(cluster: str, counts: dict[str, int]) -> None:
    counts[cluster] = counts.get(cluster, 0) + 1


def _normalize_profile(
    profile: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(profile, Mapping) or set(profile) != PROFILE_KEYS:
        raise ResearchAllocationError(
            "quick profile fields do not match contract"
        )
    result = dict(profile)
    result["research_stage"] = _enum(
        profile.get("research_stage"),
        {"quick_profile", "scoped_research"},
        "research_stage",
    )
    result["symbol"] = _symbol(profile.get("symbol"))
    result["as_of"] = _iso_date(profile.get("as_of"), "as_of")
    result["information_cutoff"] = _iso_datetime(
        profile.get("information_cutoff"),
        "information_cutoff",
    )
    result["s1_source_count"] = _nonnegative_int(
        profile.get("s1_source_count"),
        "s1_source_count",
    )
    result["circle_of_competence"] = _enum(
        profile.get("circle_of_competence"),
        {"inside", "outside", "uncertain"},
        "circle_of_competence",
    )
    if not isinstance(profile.get("business_model_understood"), bool):
        raise ResearchAllocationError("business_model_understood must be boolean")
    result["survival_status"] = _enum(
        profile.get("survival_status"),
        {"pass", "uncertain", "fail"},
        "survival_status",
    )
    result["governance_status"] = _enum(
        profile.get("governance_status"),
        {"acceptable", "uncertain", "uninvestable"},
        "governance_status",
    )
    result["normalized_earnings_status"] = _enum(
        profile.get("normalized_earnings_status"),
        {"plausible", "uncertain", "unavailable"},
        "normalized_earnings_status",
    )
    valuation = profile.get("valuation")
    if not isinstance(valuation, Mapping) or set(valuation) != VALUATION_KEYS:
        raise ResearchAllocationError(
            "quick profile valuation fields do not match contract"
        )
    current_price = _number(valuation.get("current_price"), "current_price")
    if current_price <= 0:
        raise ResearchAllocationError("current_price must be positive")
    fair_range = _range(
        valuation.get("rough_fair_value_range"),
        "rough_fair_value_range",
    )
    if not isinstance(valuation.get("market_implied_assumptions_tested"), bool):
        raise ResearchAllocationError(
            "market_implied_assumptions_tested must be boolean"
        )
    result["valuation"] = {
        "current_price": current_price,
        "rough_fair_value_range": fair_range,
        "base_expected_annual_return": _number(
            valuation.get("base_expected_annual_return"),
            "base_expected_annual_return",
        ),
        "bull_expected_annual_return": _number(
            valuation.get("bull_expected_annual_return"),
            "bull_expected_annual_return",
        ),
        "market_implied_assumptions_tested": valuation[
            "market_implied_assumptions_tested"
        ],
    }
    variant = profile.get("variant_perception")
    if variant is not None:
        variant = _require_text(variant, "variant_perception")
    result["variant_perception"] = variant
    result["decisive_unknowns"] = _text_list(
        profile.get("decisive_unknowns"),
        "decisive_unknowns",
        allow_empty=True,
    )
    result["counterevidence"] = _text_list(
        profile.get("counterevidence"),
        "counterevidence",
        allow_empty=True,
    )
    if len(set(result["counterevidence"])) < policy[
        "minimum_counterevidence_for_quick_profile"
    ]:
        raise ResearchAllocationError(
            "quick profile has insufficient counterevidence"
        )
    result["structural_stop_reasons"] = _text_list(
        profile.get("structural_stop_reasons"),
        "structural_stop_reasons",
        allow_empty=True,
    )
    unknown_stops = set(result["structural_stop_reasons"]) - set(
        policy["structural_stop_reason_codes"]
    )
    if unknown_stops:
        raise ResearchAllocationError(
            f"unsupported structural stop reasons: {sorted(unknown_stops)}"
        )
    triggers = profile.get("revisit_triggers")
    if not isinstance(triggers, list):
        raise ResearchAllocationError("revisit_triggers must be an array")
    normalized_triggers = []
    for trigger in triggers:
        if not isinstance(trigger, Mapping) or set(trigger) != TRIGGER_KEYS:
            raise ResearchAllocationError(
                "revisit trigger fields do not match contract"
            )
        trigger_type = _enum(
            trigger.get("type"),
            set(policy["reactivation_trigger_types"]),
            "revisit trigger type",
        )
        normalized_triggers.append(
            {
                "type": trigger_type,
                "condition": _require_text(
                    trigger.get("condition"),
                    "revisit trigger condition",
                ),
                "reason": _require_text(
                    trigger.get("reason"),
                    "revisit trigger reason",
                ),
            }
        )
    result["revisit_triggers"] = normalized_triggers
    return result


def _profile_has_basic_gaps(profile: Mapping[str, Any]) -> bool:
    return any(
        (
            profile["s1_source_count"] < 1,
            profile["circle_of_competence"] == "uncertain",
            not profile["business_model_understood"],
            profile["survival_status"] == "uncertain",
            profile["governance_status"] == "uncertain",
            profile["normalized_earnings_status"] != "plausible",
            len(profile["decisive_unknowns"]) > 3,
            not profile["valuation"]["market_implied_assumptions_tested"],
            profile["variant_perception"] is None,
        )
    )


def _scoped_research_has_gaps(
    profile: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> bool:
    return any(
        (
            profile["s1_source_count"]
            < policy["minimum_s1_sources_for_deep_research"],
            profile["normalized_earnings_status"] != "plausible",
            not profile["decisive_unknowns"],
        )
    )


def _exact_numeric_mapping(
    value: Any,
    expected: set[str],
    label: str,
    *,
    integer: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ResearchAllocationError(f"{label} fields do not match contract")
    result: dict[str, Any] = {}
    for key in expected:
        result[key] = (
            _nonnegative_int(value.get(key), f"{label}.{key}")
            if integer
            else _positive_number(value.get(key), f"{label}.{key}")
        )
    return result


def _text_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        suffix = "an array" if allow_empty else "a non-empty array"
        raise ResearchAllocationError(f"{label} must be {suffix}")
    result = [_require_text(item, label) for item in value]
    if len(result) != len(set(result)):
        raise ResearchAllocationError(f"{label} items must be unique")
    return result


def _symbol(value: Any) -> str:
    result = _require_text(value, "symbol")
    if not SYMBOL_RE.fullmatch(result):
        raise ResearchAllocationError("symbol must match CN:000000")
    return result


def _enum(value: Any, allowed: set[str], label: str) -> str:
    result = _require_text(value, label)
    if result not in allowed:
        raise ResearchAllocationError(f"unsupported {label}: {result}")
    return result


def _optional_public_number(item: Mapping[str, Any], field: str) -> float:
    value = item["public_snapshot"].get(field)
    return 0.0 if value is None else _number(value, field)


def _stable_hash(seed: str, symbol: str) -> str:
    return hashlib.sha256(f"{seed}:{symbol}".encode("utf-8")).hexdigest()


def _mapping_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _iso_date(value: Any, label: str) -> str:
    result = _require_text(value, label)
    try:
        dt.date.fromisoformat(result)
    except ValueError as exc:
        raise ResearchAllocationError(f"{label} must be an ISO date") from exc
    return result


def _iso_datetime(value: Any, label: str) -> str:
    result = _require_text(value, label)
    try:
        parsed = dt.datetime.fromisoformat(result)
    except ValueError as exc:
        raise ResearchAllocationError(f"{label} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchAllocationError(f"{label} must include a UTC offset")
    return result


def _range(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ResearchAllocationError(f"{label} must be a two-number range")
    lower = _number(value[0], f"{label}[0]")
    upper = _number(value[1], f"{label}[1]")
    if lower > upper:
        raise ResearchAllocationError(f"{label} must be ordered")
    return lower, upper


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchAllocationError(f"{label} must be a non-empty string")
    return value.strip()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResearchAllocationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ResearchAllocationError(f"{label} must be finite")
    return result


def _positive_number(value: Any, label: str) -> float:
    result = _number(value, label)
    if result <= 0:
        raise ResearchAllocationError(f"{label} must be positive")
    return result


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResearchAllocationError(f"{label} must be a non-negative integer")
    return value


def _positive_int(value: Any, label: str) -> int:
    result = _nonnegative_int(value, label)
    if result == 0:
        raise ResearchAllocationError(f"{label} must be positive")
    return result
