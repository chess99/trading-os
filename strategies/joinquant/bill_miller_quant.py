"""比尔·米勒风格的聚宽纯量化选股策略。

策略把主观价值判断压缩为三类可回测模型：普通企业、金融企业和亏损成长企业。
本文件保持单文件结构，便于直接复制到聚宽策略编辑器；不依赖 trading_os 包。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MODEL_GENERAL = "general"
MODEL_FINANCIAL = "financial"
MODEL_GROWTH = "growth"


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if np.isfinite(number) else np.nan


def safe_divide(numerator, denominator):
    numerator = _finite_number(numerator)
    denominator = _finite_number(denominator)
    if (
        not np.isfinite(numerator)
        or not np.isfinite(denominator)
        or abs(denominator) < 1e-12
    ):
        return np.nan
    return numerator / denominator


def simple_growth(latest, previous):
    previous = _finite_number(previous)
    if not np.isfinite(previous) or previous <= 0:
        return np.nan
    return safe_divide(_finite_number(latest) - previous, previous)


def compound_growth(latest, oldest, periods):
    latest = _finite_number(latest)
    oldest = _finite_number(oldest)
    if (
        not np.isfinite(latest)
        or not np.isfinite(oldest)
        or latest <= 0
        or oldest <= 0
        or periods <= 0
    ):
        return np.nan
    return (latest / oldest) ** (1.0 / periods) - 1.0


def winsorize_series(series, lower=0.05, upper=0.95):
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = clean.dropna()
    if valid.empty:
        return clean
    lower_bound = valid.quantile(lower, interpolation="lower")
    upper_bound = valid.quantile(upper, interpolation="lower")
    return clean.clip(lower_bound, upper_bound)


def percentile_score(series, higher_is_better=True, min_count=20):
    clean = winsorize_series(series)
    if clean.notna().sum() < min_count:
        return pd.Series(np.nan, index=clean.index, dtype=float)
    scores = clean.rank(method="average", pct=True) * 100.0
    return scores if higher_is_better else 100.0 - scores


def _value(row, key):
    if row is None:
        return np.nan
    if hasattr(row, "get"):
        return _finite_number(row.get(key, np.nan))
    return np.nan


def _row_debt(row):
    values = [_value(row, key) for key in ("shortterm_loan", "longterm_loan", "bonds_payable")]
    finite = [value for value in values if np.isfinite(value)]
    return sum(finite) if finite else np.nan


def _free_cash_flow(row):
    cash_flow = _value(row, "net_operate_cash_flow")
    capital_expenditure = _value(row, "fix_intan_other_asset_acqui_cash")
    if not np.isfinite(cash_flow) or not np.isfinite(capital_expenditure):
        return np.nan
    return cash_flow - capital_expenditure


def _positive_ratio(values):
    finite = [value for value in values if np.isfinite(value)]
    if not finite:
        return np.nan
    return sum(value > 0 for value in finite) / len(finite)


def _growth_gap(latest, previous, latest_revenue, previous_revenue):
    item_growth = simple_growth(latest, previous)
    revenue_growth = simple_growth(latest_revenue, previous_revenue)
    if not np.isfinite(item_growth) or not np.isfinite(revenue_growth):
        return np.nan
    return item_growth - revenue_growth


def build_company_features(
    history_rows,
    valuation_row,
    price_row,
    industry,
    is_financial,
    latest_row=None,
):
    """把三年可见年报转换为横截面可比较的经济特征。"""
    if history_rows is None or len(history_rows) < 2:
        return None

    history = history_rows.copy()
    if "statDate" in history:
        history = history.sort_values("statDate")
    rows = [row for _, row in history.iterrows()]
    oldest = rows[0]
    previous = rows[-2]
    latest = rows[-1]
    periods = len(rows) - 1

    latest_revenue = _value(latest, "total_operating_revenue")
    previous_revenue = _value(previous, "total_operating_revenue")
    oldest_revenue = _value(oldest, "total_operating_revenue")
    latest_profit = _value(latest, "np_parent_company_owners")
    previous_profit = _value(previous, "np_parent_company_owners")
    latest_cfo = _value(latest, "net_operate_cash_flow")
    previous_cfo = _value(previous, "net_operate_cash_flow")
    annual_fcf = [_free_cash_flow(row) for row in rows]
    latest_fcf = annual_fcf[-1]
    previous_fcf = annual_fcf[-2]

    cash = _value(latest, "cash_equivalents")
    total_assets = _value(latest, "total_assets")
    total_liability = _value(latest, "total_liability")
    equity = _value(latest, "total_owner_equities")
    debt = _row_debt(latest)
    oldest_debt = _row_debt(oldest)
    invested_capital = equity + debt - cash if all(
        np.isfinite(value) for value in (equity, debt, cash)
    ) else np.nan
    oldest_capital_parts = (
        _value(oldest, "total_owner_equities"),
        oldest_debt,
        _value(oldest, "cash_equivalents"),
    )
    oldest_invested_capital = (
        oldest_capital_parts[0] + oldest_capital_parts[1] - oldest_capital_parts[2]
        if all(np.isfinite(value) for value in oldest_capital_parts)
        else np.nan
    )

    market_cap_yuan = _value(valuation_row, "market_cap") * 1e8
    pe_ratio = _value(valuation_row, "pe_ratio")
    pb_ratio = _value(valuation_row, "pb_ratio")
    ps_ratio = _value(valuation_row, "ps_ratio")

    revenue_cagr = compound_growth(latest_revenue, oldest_revenue, periods)
    gross_margin = _value(latest, "gross_profit_margin")
    gross_margin_change = gross_margin - _value(previous, "gross_profit_margin")
    return_12m = _value(price_row, "return_12m")
    contrarian_signal = (
        -return_12m
        + (max(revenue_cagr, 0.0) if np.isfinite(revenue_cagr) else 0.0)
        + (max(gross_margin_change, 0.0) / 100.0 if np.isfinite(gross_margin_change) else 0.0)
        if np.isfinite(return_12m)
        else np.nan
    )

    deterioration_count = 0
    if latest_row is not None:
        quarterly_revenue_growth = _value(latest_row, "inc_total_revenue_year_on_year")
        quarterly_margin = _value(latest_row, "gross_profit_margin")
        quarterly_cfo = _value(latest_row, "net_operate_cash_flow")
        deterioration_count += bool(
            np.isfinite(quarterly_revenue_growth) and quarterly_revenue_growth < -15.0
        )
        deterioration_count += bool(
            np.isfinite(quarterly_margin)
            and np.isfinite(gross_margin)
            and quarterly_margin < gross_margin - 5.0
        )
        deterioration_count += bool(
            np.isfinite(quarterly_cfo)
            and quarterly_cfo < 0
            and np.isfinite(latest_cfo)
            and latest_cfo > 0
        )
    else:
        deterioration_count += bool(
            np.isfinite(simple_growth(latest_revenue, previous_revenue))
            and simple_growth(latest_revenue, previous_revenue) < -0.15
        )
        deterioration_count += bool(
            np.isfinite(gross_margin_change) and gross_margin_change < -5.0
        )
        deterioration_count += bool(
            np.isfinite(latest_cfo)
            and latest_cfo < 0
            and np.isfinite(previous_cfo)
            and previous_cfo > 0
        )

    ar_gaps = []
    inventory_gaps = []
    for prior, current in zip(rows[:-1], rows[1:], strict=True):
        ar_gaps.append(
            _growth_gap(
                _value(current, "account_receivable"),
                _value(prior, "account_receivable"),
                _value(current, "total_operating_revenue"),
                _value(prior, "total_operating_revenue"),
            )
        )
        inventory_gaps.append(
            _growth_gap(
                _value(current, "inventories"),
                _value(prior, "inventories"),
                _value(current, "total_operating_revenue"),
                _value(prior, "total_operating_revenue"),
            )
        )
    accounting_gap_streak = 0
    for ar_gap, inventory_gap in zip(
        reversed(ar_gaps), reversed(inventory_gaps), strict=True
    ):
        if (np.isfinite(ar_gap) and ar_gap > 0.25) or (
            np.isfinite(inventory_gap) and inventory_gap > 0.25
        ):
            accounting_gap_streak += 1
        else:
            break

    features = {
        "code": valuation_row.get("code"),
        "industry": industry or "未知行业",
        "is_financial": bool(is_financial),
        "latest_revenue": latest_revenue,
        "latest_profit": latest_profit,
        "latest_cfo": latest_cfo,
        "latest_fcf": latest_fcf,
        "fcf_yield": safe_divide(latest_fcf, market_cap_yuan),
        "cash_conversion": safe_divide(latest_cfo, latest_profit),
        "fcf_positive_ratio": _positive_ratio(annual_fcf),
        "cfo_positive_ratio": _positive_ratio(
            [_value(row, "net_operate_cash_flow") for row in rows]
        ),
        "revenue_cagr": revenue_cagr,
        "profit_growth": simple_growth(latest_profit, previous_profit),
        "profit_stability": _positive_ratio(
            [_value(row, "np_parent_company_owners") for row in rows]
        ),
        "gross_margin": gross_margin,
        "gross_margin_change": gross_margin_change,
        "roic_proxy": safe_divide(_value(latest, "operating_profit") * 0.75, invested_capital),
        "incremental_return": safe_divide(
            (_value(latest, "operating_profit") - _value(oldest, "operating_profit")) * 0.75,
            invested_capital - oldest_invested_capital,
        ),
        "roe": _value(latest, "roe"),
        "roa": _value(latest, "roa"),
        "asset_turnover": safe_divide(latest_revenue, total_assets),
        "net_debt_ratio": safe_divide(debt - cash, equity),
        "liability_ratio": safe_divide(total_liability, total_assets),
        "share_capital_growth": simple_growth(
            _value(latest, "paidin_capital"), _value(oldest, "paidin_capital")
        ),
        "ar_growth_gap": ar_gaps[-1] if ar_gaps else np.nan,
        "inventory_growth_gap": inventory_gaps[-1] if inventory_gaps else np.nan,
        "adjusted_profit_ratio": safe_divide(
            _value(latest, "adjusted_profit"), latest_profit
        ),
        "goodwill_ratio": safe_divide(_value(latest, "good_will"), total_assets),
        "cash_runway_years": (
            safe_divide(cash, -latest_fcf) if np.isfinite(latest_fcf) and latest_fcf < 0 else np.inf
        ),
        "cash_burn_improvement": safe_divide(latest_fcf - previous_fcf, total_assets),
        "earnings_yield": safe_divide(1.0, pe_ratio) if pe_ratio > 0 else np.nan,
        "book_yield": safe_divide(1.0, pb_ratio) if pb_ratio > 0 else np.nan,
        "sales_yield": safe_divide(1.0, ps_ratio) if ps_ratio > 0 else np.nan,
        "roe_to_pb": safe_divide(_value(latest, "roe"), pb_ratio) if pb_ratio > 0 else np.nan,
        "return_12m": return_12m,
        "volatility_12m": _value(price_row, "volatility_12m"),
        "max_drawdown_12m": _value(price_row, "max_drawdown_12m"),
        "average_money_20d": _value(price_row, "average_money_20d"),
        "contrarian_signal": contrarian_signal,
        "total_assets": total_assets,
        "total_liability": total_liability,
        "deterioration_count": int(deterioration_count),
        "accounting_gap_streak": accounting_gap_streak,
    }
    coverage_keys = (
        "latest_revenue",
        "latest_profit",
        "latest_cfo",
        "latest_fcf",
        "revenue_cagr",
        "gross_margin",
        "roe",
        "roa",
        "total_assets",
        "total_liability",
        "return_12m",
        "share_capital_growth",
    )
    features["feature_coverage"] = sum(
        np.isfinite(_finite_number(features[key])) for key in coverage_keys
    ) / len(coverage_keys)
    return features
