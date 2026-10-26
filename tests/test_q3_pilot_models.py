"""用独立手算结果检验 Q3 试点的正式估值入口，不认证商业假设。"""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_model(ticker: str):
    path = ROOT / "research" / "companies" / "CN" / ticker / "models" / "2026-Q3.py"
    spec = importlib.util.spec_from_file_location(f"q3_model_{ticker}", path)
    assert spec is not None and spec.loader is not None
    model = importlib.util.module_from_spec(spec)
    # Some existing models print their output on import; never write model artifacts here.
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(model)
    return model


def test_catl_formal_dcf_constant_cash_perpetuity(monkeypatch):
    model = load_model("300750")
    for name, value in {
        "fcf": [10.0] * 10,
        "profit": [10.0] * 10,
        "financial": 0.0,
        "other_financial": 0.0,
        "dps": [10.0] * 5,
    }.items():
        monkeypatch.setattr(model, name, value)
    result = model.dcf(r=0.1, g=0, buyback=0, shares=1)
    # All operating cash is paid; no retained financial assets or buybacks.
    assert result["per_share"] == pytest.approx(100.0)
    assert result["terminal5"] == pytest.approx(100.0)
    assert result["financial5"] == pytest.approx(0.0)


def test_cti_formal_calc_perpetuity_and_retained_cash(monkeypatch):
    model = load_model("300012")
    for name in ("DA", "CAPEX", "NWC", "ACQUISITIONS", "RENT_GAP"):
        monkeypatch.setattr(model, name, [0.0] * 5)
    for name, value in {
        "BASE_E": [1.0] * 5,
        "DPS": [1.0] * 5,
        "CASH": 1.0,
        "SHARES": 1.0,
    }.items():
        monkeypatch.setattr(model, name, value)
    result = model.calc(k=0.1, terminal_g=0, tail_g=[0.0] * 5)
    # Unit perpetuity plus initial cash earning 1.5%, released at year 5.
    expected_cash = 1.015**5
    assert result["value_per_share"] == pytest.approx(10.0 + expected_cash / 1.1**5)
    assert result["terminal_cash_y5_bn"] == pytest.approx(expected_cash)
    assert result["terminal_share_y5"] == pytest.approx(10.0 + expected_cash)
    assert result["immediate_fcfe_value_per_share"] == pytest.approx(11.0)


def test_mobile_formal_calculate_constant_cash_perpetuity(monkeypatch):
    model = load_model("600941")
    monkeypatch.setattr(model, "N", 1.0)
    monkeypatch.setattr(model, "ASSOC_CASH", [0.0] * 5)
    result = model.calculate(
        r=0.1, g=0, profit=[10.0] * 5, cf=[10.0] * 5,
        dps=[10.0] * 5, f0=0, assoc_terminal=0, yield_rate=0,
    )
    assert result["value"] == pytest.approx(100.0)
    assert result["terminal_per_share"] == pytest.approx(100.0)
    assert result["ending_financial_assets"] == pytest.approx(0.0)


@pytest.mark.parametrize("parent_cash", [1.0, 0.5])
def test_yutong_formal_valuation_recomputes_capped_distributions(parent_cash):
    model = load_model("600066")
    result = model.value_distributions(
        r=0.1, fcfe=[1.0] * 5, requested_dps=[1.0] * 5,
        opening_cash=0, operating_terminal=10, other_assets=0, shares=1,
        parent_profit=[2.0] * 5, parent_cash=[parent_cash] * 5,
        parent_opening=0, parent_retained=0, cash_yield=0, reserve_rate=0,
    )
    # Parent cannot spend group cash it has not received. Unpaid cash stays in terminal.
    retained_group_cash = (1.0 - parent_cash) * 5
    expected_terminal = 10.0 + retained_group_cash
    expected_value = parent_cash * (1 - 1.1**-5) / 0.1 + expected_terminal / 1.1**5
    assert result["dps"] == pytest.approx([parent_cash] * 5)
    assert result["closing_liquid"] == pytest.approx(retained_group_cash)
    assert result["terminal"] == pytest.approx(expected_terminal)
    assert result["per_share"] == pytest.approx(expected_value)
    assert result["parent_closing_liquid"] == pytest.approx(0.0)


@pytest.mark.parametrize("terminal_adjustment", [0.0, -2.0])
def test_chuantou_formal_ddm_perpetuity_and_terminal_bridge(terminal_adjustment):
    model = load_model("600674")
    result = model.ddm(
        0.1, 0, 0.1, earnings=[1.0] * 10, distributions=[1.0] * 10,
        financial_assets=0, fin_income=0, shares=1,
        terminal_equity_adjustment=terminal_adjustment,
    )
    assert result["value"] == pytest.approx(10.0 + terminal_adjustment / 1.1**10)
    assert result["terminal_year5"] == pytest.approx(10.0 + terminal_adjustment / 1.1**5)


def test_chuantou_binding_constraints_reach_financing_and_valuation():
    model = load_model("600674")
    path = model.mild_price_path()
    raw = path["unconstrained_operating"]
    constrained = path["operating"]
    assert raw[-1]["yl_retained_proxy"] < 0
    assert min(row["yl_retained_proxy"] for row in constrained) >= -1e-9
    assert constrained[-1]["yl_distribution"] < raw[-1]["yl_distribution"]
    assert constrained[-1]["yl_debt_end"] < raw[-1]["yl_debt_end"]
    parent = path["parent_cash_budget"]
    reproduced = model.ddm(
        earnings=[row["ct_common_profit"] for row in constrained],
        distributions=[row["dps"] for row in parent],
        terminal_equity_adjustment=parent[-1]["closing_cash"] - 1,
    )
    assert path["valuation"]["value"] == pytest.approx(reproduced["value"])
    capped = model.parent_budget(constrained, target_distributions=[10.0] * 10)
    assert any(row["dps"] < row["requested_dps"] for row in capped)
    assert all(row["closing_cash"] >= 1 - 1e-9 for row in capped)
