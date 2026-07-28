from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

ALGORITHM_VERSION = "1.0.0"

FINANCIAL_KEYWORDS = ("银行", "保险", "证券", "多元金融")
INCOMPATIBLE_KEYWORDS = FINANCIAL_KEYWORDS + ("房地产", "公用事业", "电力", "燃气", "水务")
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


class MagicFormulaError(ValueError):
    """Raised when an auditable Magic Formula snapshot cannot be built."""


def build_magic_formula_snapshot(
    *,
    companies: Sequence[Mapping[str, Any]],
    income_records_by_year: Mapping[int, Sequence[Mapping[str, Any]]],
    balance_records_by_year: Mapping[int, Sequence[Mapping[str, Any]]],
    latest_balance_records: Sequence[Mapping[str, Any]] | None = None,
    latest_balance_date: str | None = None,
    generated_at: dt.datetime,
    market_snapshot_sha256: str,
    source: str,
    max_market_age_days: int = 7,
) -> dict[str, Any]:
    """Build a non-financial, cycle-aware Magic Formula research lens.

    Earnings yield uses median three-year EBIT divided by current enterprise
    value. Return on capital divides median annual EBIT by median annual
    non-cash, non-interest-bearing working capital plus net fixed assets and
    construction in progress. The output remains a research-budget map; it
    is never an investment recommendation.
    """

    _aware(generated_at, "generated_at")
    if isinstance(max_market_age_days, bool) or max_market_age_days < 0:
        raise MagicFormulaError("max_market_age_days must be non-negative")
    if not _sha256_text(market_snapshot_sha256):
        raise MagicFormulaError("market_snapshot_sha256 must be lowercase SHA-256")
    years = sorted(set(income_records_by_year) & set(balance_records_by_year))
    if len(years) < 2:
        raise MagicFormulaError("at least two matched annual periods are required")

    company_by_ticker: dict[str, Mapping[str, Any]] = {}
    for company in companies:
        symbol = _text(company.get("symbol"), "company.symbol")
        market_as_of = _date(company.get("as_of"), f"{symbol}.as_of")
        age_days = (generated_at.date() - market_as_of).days
        if age_days < 0 or age_days > max_market_age_days:
            raise MagicFormulaError(
                f"market snapshot date is outside freshness window: {symbol}"
            )
        ticker = symbol.split(":", 1)[-1]
        if ticker in company_by_ticker:
            raise MagicFormulaError(f"duplicate company ticker: {ticker}")
        company_by_ticker[ticker] = company

    incomes = {
        year: _latest_by_ticker(records, generated_at)
        for year, records in income_records_by_year.items()
    }
    balances = {
        year: _latest_by_ticker(records, generated_at)
        for year, records in balance_records_by_year.items()
    }

    items: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    latest_year = max(years)
    latest_balances = (
        _latest_by_ticker(latest_balance_records, generated_at)
        if latest_balance_records is not None
        else balances.get(latest_year, {})
    )
    for ticker, company in sorted(company_by_ticker.items()):
        symbol = _text(company.get("symbol"), "company.symbol")
        industry = str(company.get("industry") or "未知行业").strip() or "未知行业"
        incompatible = next(
            (keyword for keyword in INCOMPATIBLE_KEYWORDS if keyword in industry),
            None,
        )
        if incompatible is not None:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "magic_formula_incompatible_business_model",
                    "detail": incompatible,
                }
            )
            continue

        market_cap = _number_or_none(company.get("market_cap_cny"))
        if market_cap is None or market_cap <= 0:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "market_cap_missing_or_nonpositive",
                    "detail": "market_cap_cny",
                }
            )
            continue

        yearly: list[dict[str, Any]] = []
        fallback_interest_years = 0
        for year in years:
            income = incomes.get(year, {}).get(ticker)
            balance = balances.get(year, {}).get(ticker)
            if income is None or balance is None:
                continue
            ebit, used_fallback = _ebit(income)
            capital = _tangible_operating_capital(balance)
            if ebit is None or capital is None or ebit <= 0 or capital <= 0:
                continue
            fallback_interest_years += int(used_fallback)
            yearly.append(
                {
                    "year": year,
                    "ebit": ebit,
                    "tangible_operating_capital": capital,
                    "return_on_capital": ebit / capital,
                }
            )
        if len(yearly) < 2:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "insufficient_positive_normalized_history",
                    "detail": f"usable_years={len(yearly)}",
                }
            )
            continue

        latest_balance = latest_balances.get(ticker)
        if latest_balance is None:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "latest_balance_missing",
                    "detail": latest_balance_date or str(latest_year),
                }
            )
            continue
        enterprise_value = _enterprise_value(market_cap, latest_balance)
        if enterprise_value is None or enterprise_value <= 0:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "enterprise_value_nonpositive_or_incomplete",
                    "detail": latest_balance_date or str(latest_year),
                }
            )
            continue

        normalized_ebit = statistics.median(row["ebit"] for row in yearly)
        normalized_capital = statistics.median(
            row["tangible_operating_capital"] for row in yearly
        )
        normalized_roc = normalized_ebit / normalized_capital
        capital_to_market_cap = normalized_capital / market_cap
        earnings_yield = normalized_ebit / enterprise_value
        if not all(
            math.isfinite(value) and value > 0
            for value in (normalized_ebit, normalized_roc, earnings_yield)
        ):
            excluded.append(
                {
                    "symbol": symbol,
                    "reason_code": "nonpositive_magic_formula_metric",
                    "detail": "normalized_ebit_or_roc_or_yield",
                }
            )
            continue

        is_cyclical = any(keyword in industry for keyword in CYCLICAL_KEYWORDS)
        near_zero_capital = capital_to_market_cap < 0.02
        confidence = (
            "high"
            if len(yearly) >= 3 and fallback_interest_years == 0
            else "medium"
        )
        items.append(
            {
                "symbol": symbol,
                "name": _text(company.get("name"), f"{symbol}.name"),
                "industry": industry,
                "market_as_of": _text(company.get("as_of"), f"{symbol}.as_of"),
                "report_years": [row["year"] for row in yearly],
                "normalized_ebit_cny": round(normalized_ebit, 2),
                "enterprise_value_cny": round(enterprise_value, 2),
                "earnings_yield": round(earnings_yield, 8),
                "return_on_tangible_capital": round(normalized_roc, 8),
                "ranking_return_on_tangible_capital": round(
                    min(normalized_roc, 2.0), 8
                ),
                "normalized_tangible_operating_capital_cny": round(
                    normalized_capital, 2
                ),
                "capital_to_market_cap": round(capital_to_market_cap, 8),
                "confidence": confidence,
                "eligible_for_nonfinancial_lens": not is_cyclical
                and not near_zero_capital,
                "reason_codes": (
                    [
                        "three_year_median_core_operating_ebit",
                        "tangible_operating_capital",
                        "cash_deduction_requires_company_level_restriction_check",
                    ]
                    + (["finance_expense_interest_proxy"] if fallback_interest_years else [])
                    + (["cyclical_requires_specialist"] if is_cyclical else [])
                    + (
                        ["near_zero_operating_capital_requires_quality_lens"]
                        if near_zero_capital
                        else []
                    )
                ),
            }
        )

    _attach_ranks(items)
    items.sort(key=lambda item: (item["combined_rank"], item["symbol"]))
    return {
        "schema_version": 1,
        "algorithm_version": ALGORITHM_VERSION,
        "generated_at": generated_at.isoformat(),
        "market_snapshot_sha256": market_snapshot_sha256,
        "report_years": years,
        "latest_balance_date": latest_balance_date or f"{latest_year}-12-31",
        "source": _text(source, "source"),
        "method": {
            "earnings_yield": "median_annual_ebit/current_enterprise_value",
            "return_on_capital": (
                "median_annual_ebit/median_annual_"
                "(noncash_noninterest_working_capital+net_fixed_assets+cip)"
            ),
            "rank_blend": "70% global percentile + 30% exact-industry percentile",
            "classic_rank": "global earnings-yield rank + global return-on-capital rank",
            "financials_and_incompatible_businesses": "excluded",
            "cyclicals": "measured_but_routed_to_specialist_lens",
            "near_zero_operating_capital": (
                "capital_below_2%_of_market_cap_routed_to_quality_lens"
            ),
            "roc_ranking_winsorization": "raw_roc_capped_at_200%_for_ranking_only",
        },
        "eligible_count": sum(
            bool(item["eligible_for_nonfinancial_lens"]) for item in items
        ),
        "item_count": len(items),
        "excluded_count": len(excluded),
        "items": items,
        "excluded": excluded,
    }


def payload_sha256(payload: Mapping[str, Any]) -> str:
    content = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _latest_by_ticker(
    records: Sequence[Mapping[str, Any]], cutoff: dt.datetime
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        ticker = str(record.get("SECURITY_CODE") or "").strip()
        if len(ticker) != 6 or not ticker.isdigit():
            continue
        notice = _source_datetime(record.get("NOTICE_DATE"))
        update = _source_datetime(record.get("UPDATE_DATE"))
        effective = update or notice
        if effective is not None and effective > cutoff:
            continue
        previous = result.get(ticker)
        if previous is None or _record_sort_key(record) > _record_sort_key(previous):
            result[ticker] = record
    return result


def _record_sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record.get("UPDATE_DATE") or ""), str(record.get("NOTICE_DATE") or ""))


def _source_datetime(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = dt.datetime.fromisoformat(value.strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
    return parsed


def _ebit(record: Mapping[str, Any]) -> tuple[float | None, bool]:
    operating_profit = _number_or_none(record.get("OPERATE_PROFIT"))
    if operating_profit is None:
        return None, False
    nonoperating_income = sum(
        _zero(record.get(key))
        for key in (
            "INVEST_INCOME",
            "FAIRVALUE_CHANGE_INCOME",
            "ASSET_DISPOSAL_INCOME",
            "OTHER_INCOME",
        )
    )
    interest = _number_or_none(record.get("FE_INTEREST_EXPENSE"))
    used_fallback = False
    if interest is None:
        finance_expense = _number_or_none(record.get("FINANCE_EXPENSE"))
        interest = max(0.0, finance_expense or 0.0)
        used_fallback = True
    core_operating_profit = operating_profit - nonoperating_income
    return core_operating_profit + max(0.0, interest), used_fallback


def _tangible_operating_capital(record: Mapping[str, Any]) -> float | None:
    current_assets = _number_or_none(record.get("TOTAL_CURRENT_ASSETS"))
    current_liabilities = _number_or_none(record.get("TOTAL_CURRENT_LIAB"))
    fixed_assets = _number_or_none(record.get("FIXED_ASSET"))
    if current_assets is None or current_liabilities is None or fixed_assets is None:
        return None
    cash = _zero(record.get("MONETARYFUNDS"))
    interest_bearing_current = sum(
        _zero(record.get(key))
        for key in ("SHORT_LOAN", "SHORT_BOND_PAYABLE", "NONCURRENT_LIAB_1YEAR")
    )
    noncash_current_assets = current_assets - cash
    noninterest_current_liabilities = current_liabilities - interest_bearing_current
    net_working_capital = noncash_current_assets - noninterest_current_liabilities
    return net_working_capital + fixed_assets + _zero(record.get("CIP"))


def _enterprise_value(
    market_cap: float, record: Mapping[str, Any]
) -> float | None:
    cash = _number_or_none(record.get("MONETARYFUNDS"))
    if cash is None:
        return None
    debt = sum(
        _zero(record.get(key))
        for key in (
            "SHORT_LOAN",
            "SHORT_BOND_PAYABLE",
            "NONCURRENT_LIAB_1YEAR",
            "LONG_LOAN",
            "BOND_PAYABLE",
            "LEASE_LIAB",
        )
    )
    reported_other_equity = _number_or_none(record.get("OTHER_EQUITY_TOOL"))
    if reported_other_equity is None:
        other_equity = _zero(record.get("PREFERRED_SHARES")) + _zero(
            record.get("PERPETUAL_BOND_PAYBALE")
        )
    else:
        other_equity = reported_other_equity
    senior_equity = _zero(record.get("MINORITY_EQUITY")) + other_equity
    return market_cap + debt + senior_equity - cash


def _attach_ranks(items: list[dict[str, Any]]) -> None:
    if not items:
        return
    yield_rank = _rank(items, "earnings_yield")
    roc_rank = _rank(items, "ranking_return_on_tangible_capital")
    industry_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        industry_groups[item["industry"]].append(item)
    for item in items:
        item["earnings_yield_rank"] = yield_rank[item["symbol"]]
        item["return_on_capital_rank"] = roc_rank[item["symbol"]]
        global_percentile = _rank_percentile(
            yield_rank[item["symbol"]] + roc_rank[item["symbol"]],
            2,
            max(2, 2 * len(items)),
        )
        peers = industry_groups[item["industry"]]
        peer_yield = _rank(peers, "earnings_yield")
        peer_roc = _rank(peers, "ranking_return_on_tangible_capital")
        industry_percentile = _rank_percentile(
            peer_yield[item["symbol"]] + peer_roc[item["symbol"]],
            2,
            max(2, 2 * len(peers)),
        )
        item["global_percentile_score"] = round(global_percentile, 6)
        item["industry_percentile_score"] = round(industry_percentile, 6)
        item["combined_score"] = round(
            0.7 * global_percentile + 0.3 * industry_percentile,
            6,
        )
    ordered = sorted(items, key=lambda item: (-item["combined_score"], item["symbol"]))
    for rank, item in enumerate(ordered, 1):
        item["combined_rank"] = rank
    classic = sorted(
        items,
        key=lambda item: (
            item["earnings_yield_rank"] + item["return_on_capital_rank"],
            item["symbol"],
        ),
    )
    for rank, item in enumerate(classic, 1):
        item["classic_rank_sum"] = (
            item["earnings_yield_rank"] + item["return_on_capital_rank"]
        )
        item["classic_combined_rank"] = rank


def _rank(items: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    ordered = sorted(items, key=lambda item: (-float(item[field]), str(item["symbol"])))
    return {str(item["symbol"]): rank for rank, item in enumerate(ordered, 1)}


def _rank_percentile(value: int, minimum: int, maximum: int) -> float:
    if maximum <= minimum:
        return 100.0
    return 100.0 * (maximum - value) / (maximum - minimum)


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _zero(value: Any) -> float:
    return _number_or_none(value) or 0.0


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MagicFormulaError(f"{label} must be non-empty text")
    return value.strip()


def _aware(value: dt.datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MagicFormulaError(f"{label} must include timezone")


def _date(value: Any, label: str) -> dt.date:
    text = _text(value, label)
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise MagicFormulaError(f"{label} must be an ISO date") from exc


def _sha256_text(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)
