"""Closed-form and limit fixtures."""
from copy import deepcopy
from math import isclose


def run_closed_form_fixtures(model):
    checked = []

    def close(name, actual, expected):
        if not isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8):
            raise AssertionError(f"{name}: {actual!r} != independently specified {expected!r}")
        checked.append({"check": name, "actual": actual, "expected": expected})

    # Independent annuity identity, not a second iteration of the production PV loop.
    rate = 0.12
    monthly_rate = (1 + rate) ** (1 / 12.0) - 1
    expected_annuity = 10 * (1 - (1 + monthly_rate) ** -12) / monthly_rate
    close("monthly PV closed geometric series", model.pv_monthly([(m, 10.0) for m in range(1, 13)], rate), expected_annuity)
    close("zero rate PV", model.pv_monthly([(1, 7.0), (2, 11.0)], 0.0), 18.0)
    close("valuation month excludes already paid flow", model.pv_monthly([(1, 7.0), (2, 11.0)], 0.0, 1), 11.0)

    policy = {"annual_upstream_fraction_of_positive_normal_common_profit": 0.5,
              "statutory_profit_allocation_rate": 0.1,
              "statutory_reserve_to_issued_capital_target": 0.5,
              "annual_intercompany_principal_collection_limit": 100.0, "cash_floor": 10.0}
    opening = {"cash": 100.0, "parent_cash": 10.0, "parent_re": 50.0,
               "parent_reserve": 5.0, "parent_dividend_receivable": 0.0,
               "parent_intercompany_principal": 0.0, "issued_shares": 10.0, "net_shares": 10.0}
    state = deepcopy(opening)
    result = model.parent_waterfall(state, 40.0, 0.0, policy, 0.5)
    # U=20; parent cash 10+20; D=20; RE=50+20-20; group cash 100-20.
    close("formal waterfall D", result["actual_distribution"], 20.0)
    close("formal waterfall parent cash", state["parent_cash"], 10.0)
    close("formal waterfall group cash", state["cash"], 80.0)
    close("formal waterfall RE", state["parent_re"], 50.0)
    state = deepcopy(opening)
    state["parent_dividend_receivable"] = 10.0
    model.parent_waterfall(state, 40.0, 0.0, policy, 0.5)
    close("old dividend collection does not create RE", state["parent_re"], 50.0)
    close("old dividend collection only relocates cash", state["parent_cash"], 20.0)
    state = deepcopy(opening)
    state.update({"parent_re": 0.0, "parent_reserve": 0.0, "issued_shares": 100.0})
    result = model.parent_waterfall(state, 40.0, 0.0, policy, 0.5)
    close("reserve allocation finite gap", result["statutory_reserve_addition"], 2.0)
    close("RE constrained D", result["actual_distribution"], 18.0)
    close("RE constrained cash retained", state["cash"], 82.0)
    state = deepcopy(opening)
    result = model.parent_waterfall(state, 0.0, 0.0, policy, 0.5)
    close("zero profit zero D", result["actual_distribution"], 0.0)
    close("zero D retains cash principal", state["cash"], 100.0)

    # Quarterly remaining NWC is 24, not spread over a fresh twelve-month year.
    miniature_inputs = {"september_2026": {"trade_nwc_positive": [12.0], "trade_nwc_negative": []},
                        "capital": {"operating_cash_ratio": 0.1,"operating_cash_revenue_anchor": 120.0}}
    miniature_budget = {2026: {"trade_nwc": 36.0,"operating_cash": 12.0,"nopat": 120.0,
                             "nonrou_da": 12.0,"maintenance": 12.0,"physical_growth_capex": 0.0,
                             "nci_fcff": 24.0,"nci_nopat": 24.0}}
    flow = model.monthly_operating_flow(miniature_inputs, miniature_budget, 2026, 10)
    close("remaining quarter NWC per month", flow["delta_wc"], 8.0)
    close("formal monthly group FCFF", flow["group_fcff"], 2.0)
    close("formal monthly NCI FCFF", flow["nci_fcff"], 2.0)
    close("formal monthly common FCFF", flow["common_unlevered_fcff"], 0.0)
    invalid_failed = False
    try:
        model.operating_value([], 10.0, 0.02, 0.02)
    except ValueError:
        invalid_failed = True
    if not invalid_failed:
        raise AssertionError("r == g must fail as input/program error, not economic null")
    checked.append({"check": "r == g is ValueError", "passed": True})
    cash_failed = False
    try:
        model.check_cash_state({"cash": -1.0, "parent_cash": 0.0}, "fixture")
    except model.EconomicInfeasible as exc:
        cash_failed = "exhausted" in exc.reason
    if not cash_failed:
        raise AssertionError("negative available cash requires a specific economic failure")
    checked.append({"check": "negative cash has explicit economic reason", "passed": True})
    return {"status": "passed", "checks": checked,
            "scope": "production functions versus independently written closed-form/limit expectations; not independent agent review"}
