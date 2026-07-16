from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "joinquant" / "bill_miller_quant.py"


def load_strategy():
    spec = importlib.util.spec_from_file_location("bill_miller_quant", STRATEGY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_ratios_and_growth_reject_economically_invalid_denominators():
    strategy = load_strategy()

    assert strategy.safe_divide(10.0, 2.0) == 5.0
    assert math.isnan(strategy.safe_divide(10.0, 0.0))
    assert math.isnan(strategy.safe_divide(10.0, np.nan))
    assert strategy.simple_growth(120.0, 100.0) == 0.2
    assert math.isnan(strategy.simple_growth(120.0, -100.0))
    assert round(strategy.compound_growth(121.0, 100.0, 2), 6) == 0.1


def test_percentile_score_handles_outliers_ties_and_small_samples():
    strategy = load_strategy()
    values = pd.Series([1.0, 2.0, 3.0, 1000.0, np.nan], index=list("abcde"))

    clipped = strategy.winsorize_series(values, lower=0.0, upper=0.75)
    assert clipped.loc["d"] == 3.0
    scores = strategy.percentile_score(clipped, min_count=3)
    assert scores.loc["c"] == scores.loc["d"]
    assert scores.loc["a"] < scores.loc["b"] < scores.loc["c"]
    assert math.isnan(scores.loc["e"])
    assert strategy.percentile_score(pd.Series([1.0, 2.0]), min_count=3).isna().all()


def test_build_company_features_derives_cash_flow_returns_and_balance_sheet_risk():
    strategy = load_strategy()
    unit = 1e8
    history = pd.DataFrame(
        [
            {
                "statDate": "2022-12-31",
                "cash_equivalents": 20.0 * unit,
                "total_assets": 200.0 * unit,
                "total_liability": 100.0 * unit,
                "total_owner_equities": 100.0 * unit,
                "paidin_capital": 10.0 * unit,
                "account_receivable": 20.0 * unit,
                "inventories": 10.0 * unit,
                "shortterm_loan": 20.0 * unit,
                "longterm_loan": 20.0 * unit,
                "bonds_payable": 0.0,
                "good_will": 4.0 * unit,
                "net_operate_cash_flow": 16.0 * unit,
                "fix_intan_other_asset_acqui_cash": 6.0 * unit,
                "total_operating_revenue": 100.0 * unit,
                "operating_profit": 12.0 * unit,
                "np_parent_company_owners": 10.0 * unit,
                "adjusted_profit": 9.0 * unit,
                "roe": 10.0,
                "roa": 5.0,
                "gross_profit_margin": 30.0,
            },
            {
                "statDate": "2023-12-31",
                "cash_equivalents": 23.0 * unit,
                "total_assets": 220.0 * unit,
                "total_liability": 108.0 * unit,
                "total_owner_equities": 112.0 * unit,
                "paidin_capital": 10.0 * unit,
                "account_receivable": 21.0 * unit,
                "inventories": 10.5 * unit,
                "shortterm_loan": 18.0 * unit,
                "longterm_loan": 18.0 * unit,
                "bonds_payable": 0.0,
                "good_will": 4.0 * unit,
                "net_operate_cash_flow": 18.0 * unit,
                "fix_intan_other_asset_acqui_cash": 6.0 * unit,
                "total_operating_revenue": 110.0 * unit,
                "operating_profit": 14.0 * unit,
                "np_parent_company_owners": 11.0 * unit,
                "adjusted_profit": 10.5 * unit,
                "roe": 10.4,
                "roa": 5.1,
                "gross_profit_margin": 31.0,
            },
            {
                "statDate": "2024-12-31",
                "cash_equivalents": 28.0 * unit,
                "total_assets": 245.0 * unit,
                "total_liability": 115.0 * unit,
                "total_owner_equities": 130.0 * unit,
                "paidin_capital": 10.0 * unit,
                "account_receivable": 22.0 * unit,
                "inventories": 11.0 * unit,
                "shortterm_loan": 16.0 * unit,
                "longterm_loan": 16.0 * unit,
                "bonds_payable": 0.0,
                "good_will": 4.0 * unit,
                "net_operate_cash_flow": 22.0 * unit,
                "fix_intan_other_asset_acqui_cash": 7.0 * unit,
                "total_operating_revenue": 121.0 * unit,
                "operating_profit": 17.0 * unit,
                "np_parent_company_owners": 13.0 * unit,
                "adjusted_profit": 12.5 * unit,
                "roe": 11.0,
                "roa": 5.5,
                "gross_profit_margin": 32.0,
            },
        ]
    )
    features = strategy.build_company_features(
        history,
        {
            "code": "000001.XSHE",
            "market_cap": 150.0,
            "pe_ratio": 12.0,
            "pb_ratio": 1.2,
            "ps_ratio": 1.0,
            "pcf_ratio": 8.0,
        },
        {
            "return_12m": -0.2,
            "volatility_12m": 0.25,
            "max_drawdown_12m": -0.35,
            "average_money_20d": 5e7,
        },
        industry="制造业",
        is_financial=False,
    )

    assert features is not None
    assert features["code"] == "000001.XSHE"
    assert features["latest_fcf"] == 15.0 * unit
    assert round(features["fcf_yield"], 4) == 0.1
    assert round(features["revenue_cagr"], 4) == 0.1
    assert features["fcf_positive_ratio"] == 1.0
    assert round(features["net_debt_ratio"], 4) == round((32.0 - 28.0) / 130.0, 4)
    assert features["contrarian_signal"] > 0


def test_classification_and_vetoes_distinguish_three_company_models():
    strategy = load_strategy()
    base = {
        "latest_revenue": 100.0,
        "latest_profit": 10.0,
        "latest_fcf": 8.0,
        "revenue_cagr": 0.1,
        "gross_margin": 30.0,
        "gross_margin_change": 1.0,
        "cash_runway_years": np.inf,
        "liability_ratio": 0.45,
        "fcf_positive_ratio": 1.0,
        "latest_cfo": 12.0,
        "cfo_positive_ratio": 1.0,
        "deterioration_count": 0,
        "accounting_gap_streak": 0,
        "feature_coverage": 1.0,
        "total_assets": 200.0,
        "total_liability": 90.0,
    }

    assert strategy.classify_model({**base, "is_financial": True}) == strategy.MODEL_FINANCIAL
    assert strategy.classify_model({**base, "is_financial": False}) == strategy.MODEL_GENERAL
    growth = {
        **base,
        "is_financial": False,
        "latest_profit": -5.0,
        "latest_fcf": -6.0,
        "cash_runway_years": 2.0,
    }
    assert strategy.classify_model(growth) == strategy.MODEL_GROWTH
    assert strategy.risk_veto_reasons(growth) == []
    assert "cash_runway" in strategy.risk_veto_reasons(
        {**growth, "cash_runway_years": 1.0}
    )
    assert "insolvent" in strategy.risk_veto_reasons(
        {**base, "total_assets": 100.0, "total_liability": 101.0}
    )


def make_scoring_fixture():
    base = {
        "industry": "制造业",
        "is_financial": False,
        "latest_revenue": 100.0,
        "latest_profit": 10.0,
        "latest_fcf": 8.0,
        "latest_cfo": 12.0,
        "revenue_cagr": 0.10,
        "profit_growth": 0.10,
        "profit_stability": 1.0,
        "gross_margin": 30.0,
        "gross_margin_change": 1.0,
        "cash_conversion": 1.2,
        "fcf_positive_ratio": 1.0,
        "cfo_positive_ratio": 1.0,
        "roic_proxy": 0.12,
        "incremental_return": 0.15,
        "roe": 12.0,
        "roa": 6.0,
        "asset_turnover": 0.8,
        "share_capital_growth": 0.0,
        "net_debt_ratio": 0.1,
        "liability_ratio": 0.45,
        "ar_growth_gap": 0.0,
        "inventory_growth_gap": 0.0,
        "adjusted_profit_ratio": 0.95,
        "goodwill_ratio": 0.02,
        "cash_runway_years": 5.0,
        "cash_burn_improvement": 0.02,
        "earnings_yield": 0.08,
        "book_yield": 0.80,
        "sales_yield": 1.0,
        "roe_to_pb": 10.0,
        "contrarian_signal": 0.20,
        "total_assets": 200.0,
        "total_liability": 90.0,
        "deterioration_count": 0,
        "accounting_gap_streak": 0,
        "feature_coverage": 1.0,
        "volatility_12m": 0.25,
        "max_drawdown_12m": -0.30,
    }

    def row(code, **changes):
        return {**base, "code": code, **changes}

    return pd.DataFrame(
        [
            row(
                "GENERAL_GOOD",
                fcf_yield=0.10,
                roic_proxy=0.18,
                contrarian_signal=0.35,
            ),
            row(
                "GENERAL_WEAK",
                fcf_yield=0.02,
                roic_proxy=0.06,
                net_debt_ratio=0.8,
            ),
            row(
                "FINANCIAL_GOOD",
                is_financial=True,
                industry="银行I",
                roe_to_pb=14.0,
                roe=14.0,
            ),
            row(
                "FINANCIAL_WEAK",
                is_financial=True,
                industry="银行I",
                roe_to_pb=5.0,
                roe=6.0,
            ),
            row(
                "GROWTH_GOOD",
                latest_profit=-3.0,
                latest_fcf=-4.0,
                revenue_cagr=0.30,
                gross_margin=55.0,
                cash_runway_years=3.0,
                sales_yield=0.8,
            ),
            row(
                "GROWTH_WEAK",
                latest_profit=-5.0,
                latest_fcf=-7.0,
                revenue_cagr=0.05,
                gross_margin=20.0,
                cash_runway_years=1.6,
                sales_yield=0.2,
            ),
        ]
    )


def test_score_candidates_rewards_expectation_gap_without_making_low_pe_a_hard_filter():
    strategy = load_strategy()
    ranked = strategy.score_candidates(make_scoring_fixture(), min_group_size=2)

    assert set(ranked["model"]) == {
        strategy.MODEL_GENERAL,
        strategy.MODEL_FINANCIAL,
        strategy.MODEL_GROWTH,
    }
    good_score = ranked.loc[ranked["code"] == "GENERAL_GOOD", "score"].iloc[0]
    weak_score = ranked.loc[ranked["code"] == "GENERAL_WEAK", "score"].iloc[0]
    assert good_score > weak_score
    assert ranked.loc[ranked["code"] == "GROWTH_GOOD", "eligible"].iloc[0]
    assert ranked["score"].dropna().between(0.0, 100.0).all()
