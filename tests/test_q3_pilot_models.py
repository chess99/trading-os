"""用独立手算结果检验 Q3 试点的正式估值入口，不认证商业假设。"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
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


def test_catl_formal_distribution_and_capital_functions(tmp_path):
    model = load_model("300750")

    def retained_run(name, **kwargs):
        result = model.run(**kwargs)
        (tmp_path / ("catl-handcase-" + name + ".json")).write_text(
            json.dumps(result, allow_nan=False)
        )
        return result

    assert model.law(0, 5, 20, 10)[:3] == (9.0, 6.0, 1.0)
    assert model.law(-8, 0, 20, 10)[:3] == (1.8, 0.2, 0.2)
    assert model.law(0, 10, 20, 10) == (10.0, 10.0, 0.0, 0.0)
    assert model.law(0, 5, 8, 10) == (10.0, 5.0, 0.0, 0.0)
    # The old60%-owned disposal maps to the already-common-owned6-unit basis.
    cash, gain, fee, tax = model.sale(6, 1, 0.1, 0.25)
    assert (cash, gain, fee, tax) == pytest.approx((5.4, -0.6, 0.6, 0.0))
    assert model.sale(10, 1.2, 0.1, 0.25) == pytest.approx((10.6, 0.6, 1.2, 0.2))
    # Collection of an opening receivable is cash transfer, not new legal profit.
    transfer = retained_run(
        "receivable",
        scale=0,
        cutday=0,
        n_years=12,
        employee_transfer=False,
        exercise=False,
    )
    first = transfer["rows"][0]
    assert first["parent_cash"] == pytest.approx(63.00829442)
    assert first["source_cash"] == pytest.approx(35.71267146)
    assert first["new_dividend_declaration"] == 0
    assert first["dividend_receivable"] == pytest.approx(0.008228 * 0.25)
    assert first["parent_legal_profit"] == pytest.approx(2.0)
    # Actual cancellation removes treasury quantity and capital reserve, not profit.
    base = retained_run("base", n_years=12)
    first = base["rows"][0]
    assert first["cancelled"] == pytest.approx(0.019605919)
    assert first["registered"] == pytest.approx(4.627249686 - 0.019605919 + 0.000519738)
    assert first["issued"] == pytest.approx(first["registered"])
    assert first["repurchased_uncancelled"] == 0
    assert first["cancellation_retained_charge"] == 0
    assert first["parent_capital_reserve"] < 166.987461
    # Identical actual purchases must not pay again on early/late cancellation.
    common = dict(
        buyback=6.0,
        buy_price=300.0,
        employee_transfer=False,
        exercise=False,
        n_years=12,
    )
    early = retained_run("cancel-early", cancel_year=1, **common)
    late = retained_run("cancel-late", cancel_year=3, **common)
    cancelled_quantity = 0.019605919 + 0.02
    treasury_cost = (
        3.30315513838
        + sum(
            [
                0.19997683436,
                0.19237993188,
                0.061019185,
                0.0499936164,
                0.7999985385,
                0.4999467487,
                0.19998299442,
                0.053672625,
            ]
        )
        * 1.001
        + 6.006
    )
    premium = treasury_cost - cancelled_quantity
    for result, year in [(early, 1), (late, 3)]:
        row = result["rows"][year - 1]
        assert row["cancelled"] == pytest.approx(cancelled_quantity)
        assert row["registered"] == pytest.approx(4.627249686 - cancelled_quantity)
        assert row["parent_capital_reserve"] == pytest.approx(166.987461 - premium)
        assert row["cancellation_retained_charge"] == 0
        assert sum(r["repurchase_cash"] for r in result["rows"]) == pytest.approx(6.0)
        assert sum(r["repurchase_fee"] for r in result["rows"]) == pytest.approx(0.006)
    assert late["rows"][2]["repurchase_cash"] == late["rows"][2]["repurchase_fee"] == 0
    for a, b in zip(early["rows"], late["rows"], strict=True):
        assert a["effective_dividend_budget_shares"] == pytest.approx(
            b["effective_dividend_budget_shares"]
        )
    assert early["rows"][0]["parent_cash"] == pytest.approx(
        late["rows"][0]["parent_cash"]
    )
    assert early["rows"][0]["source_cash"] == pytest.approx(
        late["rows"][0]["source_cash"]
    )
    gain_case = retained_run(
        "positive-gain", refinance=0, matched_recovery=1.2, matched_fee=0.1, n_years=12
    )
    gain_row = gain_case["rows"][0]
    basis = 56.768679
    expense = basis * 1.2 * 0.1
    tax = (basis * 1.2 - expense - basis) * 0.25
    assert gain_row["matched_disposed_basis"] == pytest.approx(basis)
    assert gain_row["matched_realisation_expense"] == pytest.approx(expense)
    assert gain_row["matched_realisation_tax"] == pytest.approx(tax)
    assert gain_row["matched_realised_gain_after_tax"] == pytest.approx(
        basis * 1.2 - expense - basis - tax
    )
    operating_shortfall = retained_run(
        "operating-shortfall",
        parent_start=0,
        parent_earn=0,
        scale=0,
        extra=200,
        n_years=12,
    )
    assert not operating_shortfall["feasible"]
    assert (
        operating_shortfall["failure"] == "negative cash without authorised financing"
    )
    assert operating_shortfall["PV"] is None and operating_shortfall["TV5"] is None
    assert operating_shortfall["tail_PV_upper_bound"] is None
    # No new borrowing rescues an unpaid maturity; nominal assets earn no PV.
    insolvent = retained_run(
        "debt-failure",
        refinance=0,
        matched_locked=1,
        matched_unlock_year=6,
        first_maturity=189.926135,
        n_years=12,
    )
    assert not insolvent["feasible"]
    assert insolvent["PV"] is None and insolvent["TV5"] is None
    assert insolvent["tail_PV_upper_bound"] is None
    failure = insolvent["failure_state"]
    assert failure["new_borrowing"] == 0 and failure["unpaid_principal"] > 0
    assert failure["debt_face"] == pytest.approx(
        189.926135
        - failure["actual_parent_principal_paid"]
        - failure["actual_source_principal_paid"]
    )
    assert failure["dividend"] == 0
    assert (
        failure["matched_disposed_basis"]
        == failure["matched_realised_gain_after_tax"]
        == 0
    )
    assert failure["matched_remaining_cost"] == pytest.approx(189.926135)
    assert failure["common_equity"] == pytest.approx(
        failure["parent_cash"]
        + failure["source_cash"]
        + failure["remaining_parent_financial_cost"]
        + failure["remaining_source_financial_cost"]
        + failure["fund_cost"]
        + failure["common_operating_capital"]
        + failure["matched_remaining_cost"]
        - failure["debt_face"]
    )
    (tmp_path / "catl-actual-handcases.json").write_text(
        json.dumps(
            {
                "receivable": transfer,
                "base": base,
                "cancel_early": early,
                "cancel_late": late,
                "positive_gain": gain_case,
                "operating_shortfall": operating_shortfall,
                "failure": insolvent,
            },
            allow_nan=False,
        )
    )

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
        assert actual["value"] == pytest.approx(
            model.calculate(years=80, **args)["value"], abs=1e-9
        )
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


def test_chuantou_actual_entity_functions_and_full_chain():
    model = load_model("600674")
    assert model.tests().startswith("passed:")
    base = model.run()
    stressed = model.run(extra_equity=.5)
    assert stressed["distributions_per_share"][1] < base["distributions_per_share"][1]
    assert stressed["value"] < base["value"]
    lower = model.run(price_shift=-.01)
    assert lower["value"] < base["value"]
    assert lower["rows"][-1]["dps"] < base["rows"][-1]["dps"]
    with pytest.raises(ValueError, match="funding fails"):
        model.run(initial_cash=-100)
