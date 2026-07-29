from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .company import validate_company_dir
from .coverage_store import CoverageValidationError, read_jsonl
from .sealing import atomic_write_bytes, verify_sealed

ALGORITHM_VERSION = "1.3.0"
PRIVATE_FIELD_FRAGMENTS = {
    "actual_weight",
    "cost_basis",
    "holding",
    "holdings",
    "portfolio_weight",
    "position",
    "private",
    "screenshot",
    "user",
}
CYCLICAL_KEYWORDS = (
    "煤炭",
    "石油",
    "天然气",
    "油气",
    "炼化",
    "有色",
    "工业金属",
    "贵金属",
    "小金属",
    "能源金属",
    "钢铁",
    "航运",
    "化工",
)
FINANCIAL_KEYWORDS = ("银行", "保险", "证券", "多元金融")
MANUAL_SCREENING_DECISIONS = {"needs_manual_review"}
HARD_SCREENING_DECISIONS = {
    "hard_exclusion",
    "skip_risk",
    "skip_too_small",
    "skip_not_in_scope",
}


class RebaselineRankingError(ValueError):
    """Raised when a public rebaseline ranking cannot be built safely."""


def build_rebaseline_ranking(
    *,
    companies_path: str | Path,
    queue_path: str | Path,
    screening_path: str | Path,
    research_root: str | Path,
    generated_at: dt.datetime,
    max_snapshot_age_days: int = 7,
    magic_formula_path: str | Path | None = None,
    include_completed: bool = False,
) -> dict[str, Any]:
    _require_aware_datetime(generated_at, "generated_at")
    if isinstance(max_snapshot_age_days, bool) or max_snapshot_age_days < 0:
        raise RebaselineRankingError("max_snapshot_age_days must be non-negative")

    companies_file = Path(companies_path)
    queue_file = Path(queue_path)
    screening_file = Path(screening_path)
    companies = read_jsonl(companies_file)
    queue = read_jsonl(queue_file)
    screening = read_jsonl(screening_file)
    _reject_private_fields(companies, "companies snapshot")
    _reject_private_fields(queue, "research queue")
    _reject_private_fields(screening, "screening snapshot")
    if not companies:
        raise RebaselineRankingError("companies snapshot is empty")

    by_symbol: dict[str, dict[str, Any]] = {}
    snapshot_dates: list[dt.date] = []
    for record in companies:
        symbol = _text(record.get("symbol"), "companies.symbol")
        if symbol in by_symbol:
            raise RebaselineRankingError(f"duplicate company symbol: {symbol}")
        snapshot_dates.append(_date(record.get("as_of"), f"{symbol} as_of"))
        _validate_public_numbers(record, symbol)
        by_symbol[symbol] = record
    snapshot_as_of = max(snapshot_dates)
    age = generated_at.date() - snapshot_as_of
    if age.days < 0:
        raise RebaselineRankingError("companies snapshot is dated in the future")
    if age.days > max_snapshot_age_days:
        raise RebaselineRankingError(
            f"companies snapshot is stale: {snapshot_as_of.isoformat()}"
        )

    magic_by_symbol, magic_input = _load_magic_formula(
        magic_formula_path,
        companies_file=companies_file,
        generated_at=generated_at,
    )
    items: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    screening_by_symbol: dict[str, dict[str, Any]] = {}
    for record in screening:
        symbol = _text(record.get("symbol"), "screening.symbol")
        if symbol in screening_by_symbol:
            raise RebaselineRankingError(f"duplicate screening symbol: {symbol}")
        screening_by_symbol[symbol] = record
    queue_by_symbol: dict[str, dict[str, Any]] = {}
    for task in queue:
        symbol = _text(task.get("symbol"), "queue.symbol")
        if symbol in queue_by_symbol:
            raise RebaselineRankingError(f"duplicate queue symbol: {symbol}")
        queue_by_symbol[symbol] = task

    accepted_statuses = (
        {"requires_rebaseline", "completed"}
        if include_completed
        else {"requires_rebaseline"}
    )
    for symbol, company in sorted(by_symbol.items()):
        task = queue_by_symbol.get(symbol)
        screening_record = screening_by_symbol.get(symbol)
        if screening_record is None:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "screening_missing",
                    "category": "data_error",
                }
            )
            continue
        screening_decision = _text(
            screening_record.get("decision"),
            f"{symbol} screening decision",
        )
        if screening_decision in MANUAL_SCREENING_DECISIONS:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "manual_review_required",
                    "category": "manual_review",
                }
            )
            continue
        if screening_decision in HARD_SCREENING_DECISIONS:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": f"screening_{screening_decision}",
                    "category": "hard_exclusion",
                }
            )
            continue
        hard_reason = _hard_exclusion(company)
        if hard_reason is not None:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": hard_reason,
                    "category": "hard_exclusion",
                }
            )
            continue

        if task is None:
            if not include_completed:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason_code": "research_queue_missing_not_reopened",
                        "category": "workflow_state",
                    }
                )
                continue
            ticker = symbol.split(":", 1)[1]
            task = {
                "symbol": symbol,
                "target_company_dir": f"research/companies/CN/{ticker}",
            }
        elif task.get("status") not in accepted_statuses:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": f"queue_status_{task.get('status')}_not_ranked",
                    "category": "workflow_state",
                }
            )
            continue

        company_dir = _resolve_company_dir(task, Path(research_root))
        try:
            meta = validate_company_dir(company_dir)
        except (OSError, ValueError) as exc:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "company_asset_missing_or_invalid",
                    "category": "data_error",
                }
            )
            continue
        if meta["identity"]["symbol"] != symbol:
            raise RebaselineRankingError(f"company meta symbol mismatch: {symbol}")
        items.append(
            _score_company(
                company,
                task,
                meta,
                generated_at,
                magic_formula=magic_by_symbol.get(symbol),
            )
        )

    for symbol in sorted(set(queue_by_symbol) - set(by_symbol)):
        excluded.append(
            {
                "symbol": symbol,
                "reason_code": "snapshot_missing",
                "category": "data_error",
            }
        )

    items.sort(
        key=lambda item: (
            -item["total_score"],
            -item["dimensions"]["information_update_urgency"],
            -item["dimensions"]["permanent_loss_protection"],
            item["symbol"],
        )
    )
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank

    if len(items) + len(excluded) != len(companies) + len(
        set(queue_by_symbol) - set(by_symbol)
    ):
        raise RebaselineRankingError("ranking universe partition is incomplete")

    return {
        "schema_version": 2,
        "algorithm_version": ALGORITHM_VERSION,
        "generated_at": generated_at.isoformat(),
        "retriage_completed": include_completed,
        "inputs": {
            "companies_path": companies_file.as_posix(),
            "companies_sha256": _sha256(companies_file),
            "queue_path": queue_file.as_posix(),
            "queue_sha256": _sha256(queue_file),
            "screening_path": screening_file.as_posix(),
            "screening_sha256": _sha256(screening_file),
            **magic_input,
        },
        "snapshot": {
            "as_of": snapshot_as_of.isoformat(),
            "record_count": len(companies),
            "source_count": len(
                {str(item.get("source")) for item in companies if item.get("source")}
            ),
        },
        "ranked_count": len(items),
        "excluded_count": len(excluded),
        "partition_count": len(items) + len(excluded),
        "items": items,
        "excluded": sorted(excluded, key=lambda item: item["symbol"]),
    }


def write_rebaseline_ranking(output_path: str | Path, payload: Mapping[str, Any]) -> Path:
    target = Path(output_path)
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(target, content)


def _score_company(
    company: Mapping[str, Any],
    task: Mapping[str, Any],
    meta: Mapping[str, Any],
    generated_at: dt.datetime,
    magic_formula: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    symbol = str(company["symbol"])
    industry = _industry(company.get("industry"))
    missing: list[str] = []
    reasons: set[str] = set()

    value = _value_score(company, industry, missing, reasons)
    quality = _quality_score(company, industry, missing, reasons)
    protection = _protection_score(company, industry, missing, reasons)
    urgency = _urgency_score(company, meta, generated_at, missing, reasons)
    catalyst = _catalyst_score(company, missing, reasons)
    evidence = _evidence_score(company, missing, reasons)
    penalties = _penalties(company, industry)
    penalty_points = sum(item["points"] for item in penalties)
    total = max(
        0.0,
        min(100.0, value + quality + protection + urgency + catalyst + evidence - penalty_points),
    )

    if missing:
        reasons.add("public_data_gaps_recorded")
    confidence = "high" if len(missing) <= 1 else "medium" if len(missing) <= 4 else "low"
    result = {
        "rank": 0,
        "symbol": symbol,
        "name": _text(company.get("name"), f"{symbol} name"),
        "industry": industry,
        "economic_risk_cluster": _risk_cluster(industry),
        "target_company_dir": str(task["target_company_dir"]),
        "total_score": round(total, 4),
        "score_confidence": confidence,
        "dimensions": {
            "value_dislocation": round(value, 4),
            "operating_capital_quality": round(quality, 4),
            "permanent_loss_protection": round(protection, 4),
            "information_update_urgency": round(urgency, 4),
            "verifiable_catalyst_odds": round(catalyst, 4),
            "evidence_availability": round(evidence, 4),
        },
        "penalties": penalties,
        "reason_codes": sorted(reasons),
        "missing_fields": sorted(set(missing)),
        "public_snapshot": {
            key: company.get(key)
            for key in (
                "as_of",
                "price",
                "market_cap_cny",
                "pe_ttm",
                "pb",
                "roe",
                "revenue_growth_pct",
                "profit_growth_pct",
                "dividend_yield_pct",
                "latest_filing_date",
                "source",
            )
        },
    }
    result["magic_formula"] = (
        _normalize_magic_formula(magic_formula) if magic_formula is not None else None
    )
    if magic_formula is not None:
        reasons.add("auditable_magic_formula_available")
        result["reason_codes"] = sorted(reasons)
    return result


def _load_magic_formula(
    path: str | Path | None,
    *,
    companies_file: Path,
    generated_at: dt.datetime,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Any]]:
    if path is None:
        return {}, {
            "magic_formula_path": None,
            "magic_formula_sha256": None,
        }
    target = Path(path)
    sealed = verify_sealed(target)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RebaselineRankingError("magic formula snapshot is invalid JSON") from exc
    if payload.get("schema_version") != 1 or not isinstance(payload.get("items"), list):
        raise RebaselineRankingError("magic formula snapshot contract is invalid")
    market_sha = payload.get("market_snapshot_sha256")
    if market_sha != _sha256(companies_file):
        raise RebaselineRankingError("magic formula market snapshot SHA-256 mismatch")
    generated_text = payload.get("generated_at")
    if not isinstance(generated_text, str):
        raise RebaselineRankingError("magic formula generated_at is missing")
    magic_generated = dt.datetime.fromisoformat(generated_text)
    if magic_generated.tzinfo is None or magic_generated.utcoffset() is None:
        raise RebaselineRankingError("magic formula generated_at must include timezone")
    if magic_generated > generated_at:
        raise RebaselineRankingError("magic formula snapshot is dated in the future")
    result: dict[str, Mapping[str, Any]] = {}
    for item in payload["items"]:
        if not isinstance(item, Mapping):
            raise RebaselineRankingError("magic formula item must be an object")
        symbol = _text(item.get("symbol"), "magic_formula.symbol")
        if symbol in result:
            raise RebaselineRankingError(f"duplicate magic formula symbol: {symbol}")
        result[symbol] = item
    return result, {
        "magic_formula_path": target.as_posix(),
        "magic_formula_sha256": sealed.sha256,
    }


def _normalize_magic_formula(value: Mapping[str, Any]) -> dict[str, Any]:
    required_numbers = {
        "normalized_ebit_cny",
        "enterprise_value_cny",
        "earnings_yield",
        "return_on_tangible_capital",
        "combined_score",
        "combined_rank",
    }
    result: dict[str, Any] = {
        key: _optional_number(value.get(key), f"magic_formula.{key}")
        for key in required_numbers
    }
    if any(result[key] is None for key in required_numbers):
        raise RebaselineRankingError("magic formula numeric fields are incomplete")
    confidence = _text(value.get("confidence"), "magic_formula.confidence")
    if confidence not in {"high", "medium", "low"}:
        raise RebaselineRankingError("magic formula confidence is invalid")
    eligible = value.get("eligible_for_nonfinancial_lens")
    if not isinstance(eligible, bool):
        raise RebaselineRankingError("magic formula eligibility must be boolean")
    reasons = value.get("reason_codes")
    if not isinstance(reasons, list) or not all(
        isinstance(item, str) and item.strip() for item in reasons
    ):
        raise RebaselineRankingError("magic formula reason_codes are invalid")
    return {
        **result,
        "confidence": confidence,
        "eligible_for_nonfinancial_lens": eligible,
        "reason_codes": list(reasons),
    }


def _value_score(
    company: Mapping[str, Any],
    industry: str,
    missing: list[str],
    reasons: set[str],
) -> float:
    pe = _optional_number(company.get("pe_ttm"), "pe_ttm")
    pb = _optional_number(company.get("pb"), "pb")
    dividend = _optional_number(company.get("dividend_yield_pct"), "dividend_yield_pct")
    score = 8.0
    if _is_financial(industry):
        reasons.add("financial_sector_pb_valuation")
        if pb is None:
            missing.append("pb")
        elif pb <= 0.6:
            score = 22.0
        elif pb <= 0.8:
            score = 19.0
        elif pb <= 1.0:
            score = 15.0
        elif pb <= 1.5:
            score = 9.0
        else:
            score = 4.0
    else:
        if pe is None:
            missing.append("pe_ttm")
        elif pe <= 0:
            reasons.add("negative_pe_requires_normalization")
            score = 6.0
        elif pe < 2:
            reasons.add("extreme_low_pe_requires_one_off_verification")
            score = 10.0
        elif pe <= 8:
            score = 19.0
        elif pe <= 15:
            score = 16.0
        elif pe <= 25:
            score = 12.0
        elif pe <= 40:
            score = 7.0
        else:
            score = 3.0
        if pb is None:
            missing.append("pb")
        elif 0 < pb <= 1:
            score += 3.0
        elif pb <= 2:
            score += 1.5
    if dividend is None:
        missing.append("dividend_yield_pct")
    elif dividend >= 5:
        score += 3.0
        reasons.add("high_public_dividend_yield")
    elif dividend >= 3:
        score += 1.5
    return min(25.0, score)


def _quality_score(
    company: Mapping[str, Any],
    industry: str,
    missing: list[str],
    reasons: set[str],
) -> float:
    roe = _optional_number(company.get("roe"), "roe")
    if roe is None:
        missing.append("roe")
        return 8.0
    reasons.add("latest_period_roe_requires_normalization")
    if roe > 50:
        score = 10.0
        reasons.add("single_period_roe_outlier_requires_verification")
    elif roe >= 8:
        score = 19.0
    elif roe >= 5:
        score = 17.0
    elif roe >= 3:
        score = 14.0
    elif roe >= 1:
        score = 9.0
    elif roe >= 0:
        score = 5.0
    else:
        score = 2.0
        reasons.add("negative_reported_roe")
    if _is_financial(industry):
        reasons.add("financial_quality_requires_capital_and_asset_review")
    return score


def _protection_score(
    company: Mapping[str, Any],
    industry: str,
    missing: list[str],
    reasons: set[str],
) -> float:
    debt = _optional_number(company.get("debt_to_asset_pct"), "debt_to_asset_pct")
    score = 10.0
    if _is_financial(industry):
        missing.append("financial_capital_and_asset_quality")
        reasons.add("financial_balance_sheet_requires_specialized_review")
        return score
    if debt is None:
        missing.append("debt_to_asset_pct")
    elif debt <= 30:
        score = 18.0
    elif debt <= 50:
        score = 15.0
    elif debt <= 70:
        score = 10.0
    else:
        score = 5.0
        reasons.add("high_reported_leverage")
    return score


def _urgency_score(
    company: Mapping[str, Any],
    meta: Mapping[str, Any],
    generated_at: dt.datetime,
    missing: list[str],
    reasons: set[str],
) -> float:
    cutoff = meta["research"].get("information_cutoff")
    if cutoff is None:
        score = 12.0
        reasons.add("no_valid_information_cutoff")
    else:
        cutoff_dt = dt.datetime.fromisoformat(str(cutoff))
        days = max(0, (generated_at - cutoff_dt).days)
        score = min(12.0, 3.0 + days / 30.0)
    filing = company.get("latest_filing_date")
    if filing is None:
        missing.append("latest_filing_date")
    else:
        filing_date = _date(filing, "latest_filing_date")
        if cutoff is None or filing_date > dt.datetime.fromisoformat(str(cutoff)).date():
            score = min(15.0, score + 3.0)
            reasons.add("new_filing_after_research_cutoff")
    return score


def _catalyst_score(
    company: Mapping[str, Any], missing: list[str], reasons: set[str]
) -> float:
    revenue = _optional_number(company.get("revenue_growth_pct"), "revenue_growth_pct")
    profit = _optional_number(company.get("profit_growth_pct"), "profit_growth_pct")
    if revenue is None:
        missing.append("revenue_growth_pct")
    if profit is None:
        missing.append("profit_growth_pct")
    if revenue is None and profit is None:
        return 4.0
    values = [value for value in (revenue, profit) if value is not None]
    if any(abs(value) > 200 for value in values):
        reasons.add("single_period_growth_outlier_requires_verification")
        return 4.0
    average = sum(values) / len(values)
    if average >= 20:
        reasons.add("strong_reported_growth_requires_verification")
        return 9.0
    if average >= 5:
        return 7.0
    if average >= -5:
        return 5.0
    reasons.add("reported_growth_under_pressure")
    return 3.0


def _evidence_score(
    company: Mapping[str, Any], missing: list[str], reasons: set[str]
) -> float:
    present = sum(
        company.get(field) is not None
        for field in ("industry", "pe_ttm", "pb", "roe", "latest_filing_date", "source")
    )
    score = min(10.0, 3.0 + present)
    if present >= 5:
        reasons.add("public_prefilter_evidence_available")
    return score


def _penalties(company: Mapping[str, Any], industry: str) -> list[dict[str, Any]]:
    penalties: list[dict[str, Any]] = []
    if any(keyword in industry for keyword in CYCLICAL_KEYWORDS):
        penalties.append(
            {"code": "cyclical_normalization_required", "points": 0.0}
        )
    name = str(company.get("name") or "").replace(" ", "").upper()
    if name.startswith("*ST") or name.startswith("ST"):
        penalties.append({"code": "special_treatment_risk", "points": 12.0})
    market_cap = _optional_number(company.get("market_cap_cny"), "market_cap_cny")
    turnover = _optional_number(company.get("turnover_cny"), "turnover_cny")
    if market_cap is not None and market_cap < 1_000_000_000:
        penalties.append({"code": "very_small_public_float_evidence", "points": 3.0})
    if turnover is not None and turnover < 5_000_000:
        penalties.append({"code": "thin_trading_evidence", "points": 2.0})
    flags = company.get("risk_flags")
    if flags is not None:
        if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
            raise RebaselineRankingError("risk_flags must be an array of strings")
        mapping = {
            "governance_doubt": 8.0,
            "related_party_transaction": 5.0,
            "cash_flow_divergence": 5.0,
            "material_dilution": 5.0,
            "modified_audit_opinion": 10.0,
        }
        for flag in sorted(set(flags)):
            penalties.append({"code": flag, "points": mapping.get(flag, 2.0)})
    return penalties


def _hard_exclusion(company: Mapping[str, Any]) -> str | None:
    if company.get("security_type") not in {None, "common_stock"}:
        return "not_common_stock"
    if company.get("listing_status") not in {None, "listed"}:
        return "not_listed"
    name = str(company.get("name") or "")
    if "退" in name:
        return "delisting_name_signal"
    return None


def _risk_cluster(industry: str) -> str:
    if "银行" in industry:
        return "credit_cycle"
    if "保险" in industry:
        return "insurance_rates"
    if any(keyword in industry for keyword in ("证券", "多元金融")):
        return "capital_markets"
    if "房地产" in industry:
        return "property_credit_cycle"
    if any(keyword in industry for keyword in CYCLICAL_KEYWORDS):
        return "commodity_cycle"
    if any(keyword in industry for keyword in ("半导体", "电子", "通信", "计算机")):
        return "technology_capex"
    if any(keyword in industry for keyword in ("医药", "医疗", "制药", "中药")):
        return "healthcare_policy"
    if any(keyword in industry for keyword in ("食品", "白酒", "饮料", "家电", "零售", "消费")):
        return "consumer_demand"
    if any(keyword in industry for keyword in ("电力", "公用", "交通", "建筑")):
        return "infrastructure"
    if any(keyword in industry for keyword in ("汽车", "机械", "制造")):
        return "industrial_export"
    return "diversified"


def _industry(value: Any) -> str:
    if value is None or not str(value).strip():
        return "未知行业"
    return str(value).strip()


def _is_financial(industry: str) -> bool:
    return any(keyword in industry for keyword in FINANCIAL_KEYWORDS)


def _resolve_company_dir(task: Mapping[str, Any], research_root: Path) -> Path:
    target = Path(_text(task.get("target_company_dir"), "target_company_dir"))
    if target.is_absolute():
        return target
    if target.parts and target.parts[0] == research_root.name:
        return research_root.parent / target
    if target.parts and target.parts[0] == "companies":
        return research_root / target
    return research_root.parent / target


def _reject_private_fields(value: Any, label: str, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if any(
                re.search(rf"(^|_){re.escape(fragment)}(_|$)", normalized)
                for fragment in PRIVATE_FIELD_FRAGMENTS
            ):
                raise RebaselineRankingError(
                    f"private field is forbidden in {label}: {path}.{key}"
                )
            _reject_private_fields(nested, label, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_private_fields(nested, label, f"{path}[{index}]")


def _validate_public_numbers(record: Mapping[str, Any], symbol: str) -> None:
    for field in (
        "price",
        "market_cap_cny",
        "pe_ttm",
        "pb",
        "roe",
        "revenue_growth_pct",
        "profit_growth_pct",
        "dividend_yield_pct",
        "debt_to_asset_pct",
    ):
        _optional_number(record.get(field), f"{symbol}.{field}")


def _optional_number(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RebaselineRankingError(f"{label} must be numeric or null")
    result = float(value)
    if not math.isfinite(result):
        raise RebaselineRankingError(f"{label} must be finite")
    return result


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RebaselineRankingError(f"{label} must be a non-empty string")
    return value.strip()


def _date(value: Any, label: str) -> dt.date:
    if not isinstance(value, str):
        raise RebaselineRankingError(f"{label} must be an ISO date")
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError as exc:
        raise RebaselineRankingError(f"{label} must be an ISO date") from exc


def _require_aware_datetime(value: dt.datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RebaselineRankingError(f"{label} must include a UTC offset")


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise CoverageValidationError(f"input file is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()
