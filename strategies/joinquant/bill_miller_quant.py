"""比尔·米勒风格的聚宽纯量化选股策略。

策略把主观价值判断压缩为三类可回测模型：普通企业、金融企业和亏损成长企业。
本文件保持单文件结构，便于直接复制到聚宽策略编辑器；不依赖 trading_os 包。
"""

from __future__ import annotations

import math

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
    if len(valid) < 4:
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


def classify_model(row):
    if bool(row.get("is_financial", False)):
        return MODEL_FINANCIAL
    latest_profit = _finite_number(row.get("latest_profit"))
    latest_fcf = _finite_number(row.get("latest_fcf"))
    if (
        np.isfinite(latest_profit)
        and latest_profit > 0
        and np.isfinite(latest_fcf)
        and latest_fcf > 0
    ):
        return MODEL_GENERAL

    revenue_cagr = _finite_number(row.get("revenue_cagr"))
    gross_margin = _finite_number(row.get("gross_margin"))
    gross_margin_change = _finite_number(row.get("gross_margin_change"))
    liability_ratio = _finite_number(row.get("liability_ratio"))
    try:
        cash_runway = float(row.get("cash_runway_years", np.nan))
    except (TypeError, ValueError):
        cash_runway = np.nan
    if (
        np.isfinite(revenue_cagr)
        and revenue_cagr > 0
        and np.isfinite(gross_margin)
        and gross_margin > 0
        and np.isfinite(gross_margin_change)
        and gross_margin_change >= -10.0
        and not np.isnan(cash_runway)
        and cash_runway >= 1.5
        and np.isfinite(liability_ratio)
        and liability_ratio < 0.70
    ):
        return MODEL_GROWTH
    return None


def risk_veto_reasons(row):
    reasons = []
    total_assets = _finite_number(row.get("total_assets"))
    total_liability = _finite_number(row.get("total_liability"))
    if (
        np.isfinite(total_assets)
        and np.isfinite(total_liability)
        and total_liability > total_assets
    ):
        reasons.append("insolvent")

    if (
        _finite_number(row.get("cfo_positive_ratio")) == 0
        and _finite_number(row.get("revenue_cagr")) <= 0
    ):
        reasons.append("persistent_negative_cfo")
    if _finite_number(row.get("deterioration_count")) >= 2:
        reasons.append("fundamental_deterioration")
    if _finite_number(row.get("accounting_gap_streak")) >= 2:
        reasons.append("accounting_gap")
    if _finite_number(row.get("feature_coverage")) < 0.5:
        reasons.append("insufficient_data")

    if not bool(row.get("is_financial", False)) and (
        _finite_number(row.get("latest_profit")) <= 0
        or _finite_number(row.get("latest_fcf")) <= 0
    ):
        try:
            cash_runway = float(row.get("cash_runway_years", np.nan))
        except (TypeError, ValueError):
            cash_runway = np.nan
        if np.isnan(cash_runway) or cash_runway < 1.5:
            reasons.append("cash_runway")
        liability_ratio = _finite_number(row.get("liability_ratio"))
        if not np.isfinite(liability_ratio) or liability_ratio >= 0.70:
            reasons.append("growth_leverage")
    return reasons


_MODEL_COMPONENTS = {
    MODEL_GENERAL: {
        "expectation_score": (
            ("fcf_yield", True),
            ("earnings_yield", True),
            ("book_yield", True),
            ("sales_yield", True),
            ("roe_to_pb", True),
        ),
        "quality_score": (
            ("cash_conversion", True),
            ("fcf_positive_ratio", True),
            ("revenue_cagr", True),
            ("gross_margin", True),
            ("profit_stability", True),
        ),
        "capital_score": (
            ("roic_proxy", True),
            ("incremental_return", True),
            ("roe", True),
            ("roa", True),
        ),
        "accounting_score": (
            ("adjusted_profit_ratio", True),
            ("net_debt_ratio", False),
            ("ar_growth_gap", False),
            ("inventory_growth_gap", False),
            ("goodwill_ratio", False),
        ),
        "contrarian_score": (("contrarian_signal", True),),
    },
    MODEL_FINANCIAL: {
        "expectation_score": (
            ("roe_to_pb", True),
            ("book_yield", True),
            ("earnings_yield", True),
        ),
        "quality_score": (
            ("profit_stability", True),
            ("profit_growth", True),
            ("adjusted_profit_ratio", True),
        ),
        "capital_score": (("roe", True), ("roa", True)),
        "accounting_score": (
            ("adjusted_profit_ratio", True),
            ("profit_stability", True),
        ),
        "contrarian_score": (("contrarian_signal", True),),
    },
    MODEL_GROWTH: {
        "expectation_score": (
            ("sales_yield", True),
            ("revenue_cagr", True),
            ("cash_burn_improvement", True),
        ),
        "quality_score": (
            ("gross_margin", True),
            ("gross_margin_change", True),
            ("revenue_cagr", True),
        ),
        "capital_score": (("asset_turnover", True), ("revenue_cagr", True)),
        "accounting_score": (
            ("cash_runway_years", True),
            ("liability_ratio", False),
            ("share_capital_growth", False),
        ),
        "contrarian_score": (("contrarian_signal", True),),
    },
}

_COMPONENT_WEIGHTS = {
    "expectation_score": 0.35,
    "quality_score": 0.25,
    "capital_score": 0.15,
    "accounting_score": 0.15,
    "contrarian_score": 0.10,
}


def _score_group(frame, model, min_group_size):
    result = frame.copy()
    for component, feature_specs in _MODEL_COMPONENTS[model].items():
        component_parts = []
        original_valid = pd.DataFrame(index=result.index)
        for feature, higher_is_better in feature_specs:
            raw = pd.to_numeric(result.get(feature), errors="coerce").replace(
                [np.inf, -np.inf], np.nan
            )
            original_valid[feature] = raw.notna()
            if raw.notna().any():
                raw = raw.fillna(raw.median())
            component_parts.append(
                percentile_score(
                    raw,
                    higher_is_better=higher_is_better,
                    min_count=min_group_size,
                )
            )
        scores = pd.concat(component_parts, axis=1).mean(axis=1)
        enough_inputs = original_valid.sum(axis=1) >= math.ceil(len(feature_specs) / 2)
        result[component] = scores.where(enough_inputs)
    return result


def score_candidates(features, min_group_size=20):
    """按公司模型计算五类分数并返回稳定的降序排名。"""
    if features is None or len(features) == 0:
        return pd.DataFrame()
    frame = features.copy().reset_index(drop=True)
    frame["model"] = frame.apply(classify_model, axis=1)
    frame["veto_reasons"] = frame.apply(risk_veto_reasons, axis=1)

    scored_groups = []
    for model in (MODEL_GENERAL, MODEL_FINANCIAL, MODEL_GROWTH):
        model_frame = frame.loc[frame["model"] == model]
        if model_frame.empty:
            continue
        if model == MODEL_FINANCIAL:
            for _, industry_frame in model_frame.groupby("industry", dropna=False):
                scored_groups.append(_score_group(industry_frame, model, min_group_size))
        else:
            scored_groups.append(_score_group(model_frame, model, min_group_size))

    unclassified = frame.loc[frame["model"].isna()].copy()
    for component in _COMPONENT_WEIGHTS:
        unclassified[component] = np.nan
    if not unclassified.empty:
        scored_groups.append(unclassified)
    if not scored_groups:
        return frame.iloc[0:0]

    ranked = pd.concat(scored_groups, axis=0).sort_index()
    component_frame = ranked[list(_COMPONENT_WEIGHTS)]
    valid_components = component_frame.notna().sum(axis=1)
    ranked["score"] = sum(
        ranked[component] * weight for component, weight in _COMPONENT_WEIGHTS.items()
    )
    ranked["eligible"] = (
        ranked["model"].notna()
        & ranked["veto_reasons"].map(len).eq(0)
        & valid_components.ge(3)
        & ranked["score"].notna()
    )
    volatility = pd.to_numeric(ranked.get("volatility_12m"), errors="coerce").fillna(0.5)
    drawdown = pd.to_numeric(ranked.get("max_drawdown_12m"), errors="coerce").abs().fillna(0.5)
    balance_risk = pd.to_numeric(ranked.get("liability_ratio"), errors="coerce").clip(0, 1)
    ranked["downside_risk"] = (volatility + drawdown + balance_risk.fillna(0.5)) / 3.0
    return ranked.sort_values(
        ["eligible", "score", "code"], ascending=[False, False, True], na_position="last"
    ).reset_index(drop=True)


def select_portfolio(
    ranked,
    current_codes,
    target_count=20,
    entry_rank=15,
    hold_rank=40,
):
    if ranked is None or len(ranked) == 0 or target_count <= 0:
        return []
    eligible = ranked.loc[ranked["eligible"].fillna(False)].copy()
    if "veto_reasons" in eligible:
        eligible = eligible.loc[eligible["veto_reasons"].map(len).eq(0)]
    eligible = eligible.reset_index(drop=True)
    eligible["rank"] = np.arange(1, len(eligible) + 1)
    if not current_codes:
        return list(eligible["code"].head(target_count))

    current = set(current_codes)
    retained = list(
        eligible.loc[
            eligible["code"].isin(current) & eligible["rank"].le(hold_rank), "code"
        ]
    )[:target_count]
    selected = list(retained)
    for code in eligible.loc[eligible["rank"].le(entry_rank), "code"]:
        if code not in selected:
            selected.append(code)
        if len(selected) >= target_count:
            break
    return selected


def _single_name_capped_weights(conviction, max_single):
    weights = pd.Series(0.0, index=conviction.index, dtype=float)
    active = list(conviction.index)
    remaining = 1.0
    while active and remaining > 1e-12:
        active_conviction = conviction.loc[active]
        total_conviction = active_conviction.sum()
        if not np.isfinite(total_conviction) or total_conviction <= 0:
            break
        proposed = active_conviction / total_conviction * remaining
        capped = proposed.loc[proposed > max_single + 1e-12]
        if capped.empty:
            weights.loc[active] = proposed
            break
        for index in capped.index:
            weights.loc[index] = max_single
            remaining -= max_single
            active.remove(index)
    return weights


def _apply_group_cap(frame, weights, column, group_value, cap):
    mask = frame[column].eq(group_value)
    group_total = weights.loc[mask].sum()
    if group_total > cap and group_total > 0:
        weights.loc[mask] *= cap / group_total


def allocate_weights(
    selected,
    max_single=0.08,
    min_single=0.02,
    max_industry=0.25,
    max_financial=0.30,
    max_growth=0.20,
):
    if selected is None or len(selected) == 0:
        return {}
    frame = selected.copy().drop_duplicates("code").reset_index(drop=True)
    scores = pd.to_numeric(frame["score"], errors="coerce")
    risks = pd.to_numeric(frame["downside_risk"], errors="coerce").clip(lower=0.05)
    valid = scores.notna() & risks.notna()
    frame = frame.loc[valid].reset_index(drop=True)
    if frame.empty:
        return {}
    scores = scores.loc[valid].reset_index(drop=True)
    risks = risks.loc[valid].reset_index(drop=True)
    conviction = (scores.sub(50.0).clip(lower=1.0) / risks).replace(
        [np.inf, -np.inf], np.nan
    )
    conviction = conviction.fillna(0.0)
    weights = _single_name_capped_weights(conviction, max_single)

    for industry in frame["industry"].dropna().unique():
        _apply_group_cap(frame, weights, "industry", industry, max_industry)
    _apply_group_cap(frame, weights, "model", MODEL_FINANCIAL, max_financial)
    _apply_group_cap(frame, weights, "model", MODEL_GROWTH, max_growth)

    weights = weights.where(weights >= min_single, 0.0)
    total = weights.sum()
    if total > 1.0:
        weights /= total
    return {
        frame.loc[index, "code"]: round(float(weight), 10)
        for index, weight in weights.items()
        if weight > 0
    }
