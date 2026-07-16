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
