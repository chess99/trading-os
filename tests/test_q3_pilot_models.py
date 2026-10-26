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


def test_catl_formal_distribution_and_capital_functions():
    model = load_model("300750")
    assert model.legal_step(0,5,20,10)[:3] == (9.,6.,1.)
    assert model.legal_step(-8,0,20,10)[:3] == (1.8,.2,.2)
    assert model.transfer(5,0,5) == (0,0,5)
    assert model.capital_reduce(10,20,20,6,3,1) == (3,17,17,6)
    sale=model.disposal(10,10,1,.25,.6)
    assert sale['cash'] == pytest.approx(5.4)
    assert sale['gain'] == pytest.approx(-.6)
    insolvent=model.run(parent_start=0,parent_earn=0,scale=0,extra=200)
    assert not insolvent['feasible']
    assert all(row['new_financing']==0 for row in insolvent['rows'])


def test_cti_formal_payer_profit_cash_and_principal():
    model = load_model("300012")
    # Same owner_cash_step used in every annual production calc: legal profit and cash cap.
    paid = model.owner_cash_step(0, 5, 20, 10, 100, 100, paid_capital=10)
    assert paid["reserve_add"] == pytest.approx(1)
    assert paid["paid"] == pytest.approx(9)
    old_receivable = model.owner_cash_step(0, 0, 20, 0, 10, 10)
    assert old_receivable["paid"] == 0
    assert old_receivable["cash"] == 10
    loss = model.owner_cash_step(-8, 0, 20, 10, 100, 100)
    assert loss["paid"] == pytest.approx(1.8)


def test_mobile_actual_payment_kernel_and_full_chain():
    model = load_model("600941")
    assert model.selftests().startswith("9 actual-kernel")
    cases = model.cases()
    for name, args in cases.items():
        actual = model.calculate(**args)
        assert actual["feasible"], name
        assert actual["value"] == pytest.approx(model.calculate(years=80, **args)["value"], abs=1e-9)
    with pytest.raises(ValueError, match="unresolved surplus"):
        model.calculate(upstream_scale=.1)


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
