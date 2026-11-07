"""Static author implementation. Do not import/run before separate authorization.

Money: CNY billion; shares: million; per share: CNY. No network or data discovery.
The production path and closed-form cases use the same simulate_path function.
"""
from __future__ import annotations

import copy
import math


class EconomicInfeasible(Exception):
    """Only a genuine cash/capital inability may make a scenario unavailable."""

    def __init__(self, stage, details):
        super().__init__(stage)
        self.stage, self.details = stage, details


def ensure(condition, message):
    if not condition:
        raise ValueError(message)


def near(a, b, label):
    if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-8):
        raise AssertionError(f"{label}: {a!r} != {b!r}")


def per_share(billions, millions):
    ensure(millions > 0, "nonpositive participating shares")
    return billions * 1000.0 / millions


def finite_tree(value, path="root"):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        ensure(math.isfinite(value), f"nonfinite input at {path}")
    elif isinstance(value, dict):
        for k, v in value.items():
            finite_tree(v, f"{path}/{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            finite_tree(v, f"{path}/{i}")
    else:
        raise TypeError(f"unsupported value at {path}")


def historical_bridges(data, scenario):
    """Two diagnostic bridges, never added to forecast FCF or to each other."""
    h = data["history"]
    ebit = (h["q3_pbt"] + h["q3_interest_expense"]
            - h["q3_interest_income"] - h["q3_investment_gain"]
            - h["q3_fair_value_gain"] - h["q3_tariff_pnl"]
            - h["q3_nonoperating_grant"] + scenario["normal_fx_adjustment"])
    taxes = scenario["tax_rate"]
    refund_tax_range = [h["q3_tariff_pnl"] * (1.0 - t)
                        for t in data["assumption_bounds"]["refund_tax_effect_rates"]]
    return {
        "reported_q3_pbt": h["q3_pbt"],
        "normalized_9m_operating_ebit_diagnostic": ebit,
        "normalized_9m_operating_profit_after_tax_diagnostic": ebit * (1 - taxes),
        "normal_fx_adjustment_is_estimate": scenario["normal_fx_adjustment"],
        "historical_software_income_tax_refund_removed_by_tax_replacement": h["software_income_tax_refund"],
        "no_second_tax_refund_deduction": True,
        "tariff_after_tax_adjustment_range_diagnostic_only": refund_tax_range,
        "h1_cfo_ex_actual_tariff_and_operating_interest_diagnostic": (
            h["h1_cfo"] - h["h1_cfo_tariff_and_interest"] - h["h1_operating_deposit_interest"]),
        "h1_investment_and_fv_gains_already_removed_in_reported_cfo": True,
        "refund_cash_tax_timing_unidentified_not_fabricated": True,
        "cash_bridge_not_combined_with_pnl_bridge": True,
        "diagnostics_not_forecast_cash_inputs": True,
    }


def validate(data, scenario):
    finite_tree(data)
    finite_tree(scenario)
    ensure(data["unit"] == "CNY_bn_shares_million", "unit mismatch")
    ensure(len(scenario["years"]) == 10, "exactly ten operating years required")
    ensure(scenario["equity_discount"] >= 0, "negative equity discount")
    ensure(scenario["wacc"] > scenario["terminal_growth"] >= 0, "invalid terminal rates")
    ensure(0 <= scenario["foreign_exposure_fraction"] <= 1, "risk bucket exceeds foreign revenue")
    ensure(0 <= scenario["foreign_share_anchor"] <= 1, "invalid geography share")
    ensure(0 <= scenario["tax_rate"] < 1, "invalid normal tax rate")
    ensure(0 <= scenario["financial_liquidity_fraction"] <= 1, "invalid liquidity fraction")
    ensure(scenario["method2_multiple"] > 0, "nonpositive method2 multiple")
    for i, y in enumerate(scenario["years"]):
        ensure(y["year"] == 2027 + i, "year ordering")
        for k in ["gross_margin", "selling_ratio", "rd_ratio", "admin_ratio", "other_operating_cost_ratio"]:
            ensure(0 <= y[k] < 1, f"invalid {k}")
        ensure(0 <= y["payout"] <= 1, "invalid payout")
        ensure(0 <= y["exposure_availability"] <= 1, "availability is conditional factor, not law")
        ensure(y["new_old_award_shares"] >= 0 and y["new_2026_award_shares"] >= 0, "negative new shares")
    ensure(sum(y["new_old_award_shares"] for y in scenario["years"]) <= data["award_envelope"]["old_gross_grants_million"], "old award gross envelope exceeded")
    ensure(sum(y["new_2026_award_shares"] for y in scenario["years"]) <= data["award_envelope"]["grant2026_shares_million"] + 1e-10, "2026 grant envelope exceeded")


def starting_state(data, s):
    a = data["opening"]
    other_bridge = data["opening_other_nwc_bridge"]
    signed_other = sum(x["signed_bn"] for x in other_bridge["components"])
    near(signed_other, other_bridge["net_other_operating_assets_bn"], "signed opening other NWC")
    near(s["repo_debt_estimate"], other_bridge["financial_debt_reclassified_bn"], "repo excluded from NWC then debt once")
    valued_financial = (a["cash"] + a["trading_financial"] * s["liquid_asset_recovery"]
                        + a["current_deposits"] + s["noncurrent_deposits_estimate"]
                        + (a["other_noncurrent_financial"] - s["private_equity_book_estimate"]) * s["liquid_asset_recovery"]
                        + s["private_equity_book_estimate"] * s["private_equity_recovery"]
                        + other_bridge["financial_asset_reclassified_bn"] * s["liquid_asset_recovery"])
    operating_nwc = (a["inventory"] + a["receivables"] + a["prepayments"]
                     - a["trade_payables"] + signed_other
                     + s["opening_operating_cash"])
    state = {
        "pool": valued_financial - s["opening_operating_cash"] - s["nci_claim_reserve"] + a["october_subscription_cash"],
        "parent_cash": s["parent_opening_liquidity"] + a["october_subscription_cash"],
        "parent_re": a["parent_h1_re"], "reserve": a["statutory_reserve"],
        "parent_internal_ar": a["parent_h1_internal_ar"],
        "issued": a["issued_at_cutoff_million"], "treasury": a["treasury_account_million"],
        "nwc": operating_nwc, "fixed": a["fixed_assets"],
        "operating_cash": s["opening_operating_cash"],
        "debt": a["short_debt"] + s["repo_debt_estimate"] + a["derivative_liability"],
    }
    ensure(state["issued"] > state["treasury"] >= 0, "invalid opening share ledger")
    ensure(state["parent_cash"] <= state["pool"] + state["operating_cash"], "parent cannot exceed group available assets")
    return state


def step(state, annual_revenue, operating_revenue, year_input, s, duration, time_from_cutoff, work=None):
    """The sole cash/share/parent transition used by production and analytical cases."""
    y, old = year_input, copy.deepcopy(state)
    if work is None:
        work = {}
    work.update(stage="operating_income", year=y["year"], state_before=copy.deepcopy(old),
                year_input=copy.deepcopy(y), annual_revenue=annual_revenue,
                operating_revenue=operating_revenue, duration=duration)
    gm = y["gross_margin"]
    cogs_annual = annual_revenue * (1 - gm)
    margin = gm - y["selling_ratio"] - y["rd_ratio"] - y["admin_ratio"] - y["other_operating_cost_ratio"]
    ebit = operating_revenue * margin
    operating_tax = max(ebit, 0) * s["tax_rate"]
    known_addback = y["known_new_share_expense_addback"] + y["already_transferred_employee_expense_addback"]
    work.update(ebit=ebit, normal_current_period_tax_accrual=operating_tax, known_expense_addback=known_addback)
    ensure(known_addback <= operating_revenue * s["total_sbc_cost_embedded_ratio"] + 1e-8,
           "matched award expense exceeds embedded total compensation budget")
    nopat = ebit - operating_tax
    matched_award_cash_adjustment = known_addback * (1 - s["tax_rate"])
    work.update(ebit=ebit, normal_current_period_tax_accrual=operating_tax,
                nopat=nopat, matched_award_cash_adjustment=matched_award_cash_adjustment,
                stage="working_and_fixed_capital")
    inventory = cogs_annual * y["inventory_days"] / 365
    receivables = annual_revenue * y["receivable_days"] / 365
    prepayments = cogs_annual * y["prepayment_days"] / 365
    payables = cogs_annual * y["payable_days"] / 365
    op_cash = annual_revenue * s["minimum_operating_cash_ratio"]
    nwc_target = inventory + receivables + prepayments - payables + annual_revenue * y["other_operating_net_ratio"] + op_cash
    balance_fraction = y.get("balance_transition_fraction", 1.0)
    ensure(0 < balance_fraction <= 1, "invalid partial-balance transition")
    nwc = old["nwc"] + (nwc_target - old["nwc"]) * balance_fraction
    op_cash = old["operating_cash"] + (op_cash - old["operating_cash"]) * balance_fraction
    depreciation = annual_revenue * s["depreciation_ratio"] * duration
    fixed_target = old["fixed"] + (annual_revenue * y["fixed_asset_target_ratio"] - old["fixed"]) * balance_fraction
    capex = max(depreciation * s["maintenance_floor_to_depreciation"],
                depreciation + fixed_target - old["fixed"])
    capex += y["extra_physical_capex"]
    work.update(nwc_target=nwc_target, nwc=nwc, op_cash=op_cash,
                depreciation=depreciation, fixed_target=fixed_target, capex=capex)
    ensure(capex >= y["capital_commitment_covered"] - 1e-9, "cash capex does not cover specified outstanding commitment")
    fixed = old["fixed"] + capex - depreciation
    interest_cash = old["debt"] * s["borrowing_cost"] * duration
    after_tax_interest = interest_cash * (1 - s["tax_rate"])
    fcff = nopat + matched_award_cash_adjustment + depreciation - capex - (nwc - old["nwc"]) - y["extra_cash_restructuring"]
    fcfe_before_financial_income = fcff - after_tax_interest
    fin_income = max(old["pool"], 0) * s["financial_after_tax_yield"] * duration
    work.update(fcff=fcff, fcfe_before_financial_income=fcfe_before_financial_income,
                financial_income=fin_income, stage="share_events")

    issued = old["issued"] + y["new_old_award_shares"] + y["new_2026_award_shares"]
    issuance_cash = (y["new_old_award_shares"] * s["old_award_subscription_price"]
                     + y["new_2026_award_shares"] * s["grant2026_subscription_price"]) / 1000
    treasury = old["treasury"]
    sale = y["treasury_sale_shares"]
    cancel = y["treasury_cancel_shares"]
    ensure(sale + cancel <= treasury + 1e-9, "cannot dispose more than held in treasury")
    treasury -= sale + cancel
    issued -= cancel
    treasury_sale_cash = sale * s["treasury_sale_price_assumption"] / 1000
    # Employee refunds return already-issued shares to treasury: no new issue/cancellation.
    refund_shares = y["employee_refund_shares"]
    employee_refund_cash = y["employee_refund_cash"]
    ensure((refund_shares == 0) == (employee_refund_cash == 0), "employee refund/participation rights must pair")
    treasury += refund_shares
    participating = issued - treasury
    ensure(participating > 0, "nonpositive participating shares")
    event_cash = issuance_cash + treasury_sale_cash - employee_refund_cash
    pool_before_div = old["pool"] + fcfe_before_financial_income + fin_income + event_cash
    work.update(issued=issued, treasury=treasury, participating=participating,
                event_cash=event_cash, pool_before_distribution=pool_before_div,
                stage="group_cash_feasibility_zero_D")
    if pool_before_div < -1e-9:
        raise EconomicInfeasible("group_cash_exhaustion_no_new_financing_authorized", {
            "year": y["year"], "pool_before_distribution": pool_before_div,
            "operating_cash_ringfenced": op_cash, "dividend_already_zero_for_test": True})

    # Parent is a subset/receiving account, not a second source of group value.
    parent_fin_income = min(fin_income, max(old["parent_cash"], 0) * s["financial_after_tax_yield"] * duration)
    parent_own_profit = operating_revenue * s["parent_own_profit_ratio"]
    parent_own_cf = operating_revenue * s["parent_own_cash_ratio"]
    support = max(-fcfe_before_financial_income, 0) * s["parent_funding_share"]
    parent_pre_transfer = old["parent_cash"] + parent_own_cf + parent_fin_income + event_cash - support
    desired_sub_dividend = max(nopat, 0) * s["domestic_profit_fraction"] * s["domestic_upstream_payout"]
    wanted_trade = min(y["parent_old_trade_collection"], old["parent_internal_ar"])
    other_liquid_capacity = max((pool_before_div + op_cash) * s["financial_liquidity_fraction"] - parent_pre_transfer, 0)
    actual_sub_dividend = min(desired_sub_dividend, other_liquid_capacity)
    actual_trade = min(wanted_trade, max(other_liquid_capacity - actual_sub_dividend, 0))
    parent_before_div = parent_pre_transfer + actual_sub_dividend + actual_trade
    work.update(stage="parent_payment_feasibility", parent_before_distribution=parent_before_div,
                actual_sub_dividend=actual_sub_dividend, actual_old_trade_collection=actual_trade)
    if parent_before_div < -1e-9:
        raise EconomicInfeasible("parent_payment_budget_exhaustion", {"year": y["year"], "parent_before_distribution": parent_before_div})
    parent_np = parent_own_profit + parent_fin_income + actual_sub_dividend
    statutory_gap = max(0.5 * issued / 1000 - old["reserve"], 0)
    # Current profit first absorbs accumulated parent loss; legal negative RE is not a code failure.
    profit_after_loss_absorption = min(max(parent_np, 0), max(old["parent_re"] + parent_np, 0))
    statutory_add = min(profit_after_loss_absorption * s["statutory_profit_rate"], statutory_gap)
    legal_capacity = max(old["parent_re"] + parent_np - statutory_add, 0)
    desired_distribution = max(nopat - after_tax_interest + fin_income, 0) * y["payout"]
    group_distribution_capacity = max(pool_before_div * s["financial_liquidity_fraction"] - y["purpose_cash_unavailable"], 0)
    parent_distribution_capacity = max(parent_before_div - s["parent_minimum_cash"], 0)
    distribution = min(desired_distribution, legal_capacity, group_distribution_capacity, parent_distribution_capacity)
    work.update(stage="distribution_and_rollforward", parent_np=parent_np,
                profit_after_loss_absorption=profit_after_loss_absorption,
                statutory_add=statutory_add, legal_capacity=legal_capacity,
                distribution=distribution)
    state.update(pool=pool_before_div - distribution, parent_cash=parent_before_div - distribution,
                 parent_re=old["parent_re"] + parent_np - statutory_add - distribution,
                 reserve=old["reserve"] + statutory_add, parent_internal_ar=old["parent_internal_ar"] - actual_trade,
                 issued=issued, treasury=treasury, nwc=nwc, fixed=fixed, operating_cash=op_cash)
    work["state_after_candidate"] = copy.deepcopy(state)
    near(state["pool"], old["pool"] + fcfe_before_financial_income + fin_income + event_cash - distribution, "group cash conservation")
    near(state["parent_cash"], old["parent_cash"] + parent_own_cf + parent_fin_income + event_cash - support + actual_sub_dividend + actual_trade - distribution, "parent cash conservation")
    ensure(state["parent_cash"] <= state["pool"] + op_cash + 1e-8, "parent liquidity exceeds group assets")
    ensure(state["parent_cash"] >= -1e-8, "distribution created parent cash deficit")
    ensure(distribution <= legal_capacity + 1e-8, "distribution exceeded lawful positive earnings capacity")
    near(issued - treasury, old["issued"] - old["treasury"] + y["new_old_award_shares"] + y["new_2026_award_shares"] + sale - refund_shares, "participating shares")
    return {
        "year": y["year"], "time_from_cutoff": time_from_cutoff, "duration": duration,
        "revenue": operating_revenue, "annual_revenue_runrate": annual_revenue,
        "gross_margin": gm, "ebit_margin_after_all_embedded_compensation": margin,
        "ebit": ebit, "operating_tax": operating_tax, "nopat": nopat,
        "tax_timing_convention": "normalized current-period tax accrual; opening/closing tax payable, VAT and prepayments enter aggregate NWC once",
        "matched_known_award_expense_cash_adjustment": matched_award_cash_adjustment,
        "embedded_total_sbc_budget": operating_revenue * s["total_sbc_cost_embedded_ratio"],
        "depreciation": depreciation, "capex": capex, "inventory": inventory,
        "receivables": receivables, "prepayments": prepayments, "trade_payables": payables,
        "nwc_full_target": nwc_target, "nwc": nwc, "delta_nwc": nwc - old["nwc"], "fixed_assets": fixed,
        "fcff": fcff, "cash_interest_after_tax": after_tax_interest,
        "fcfe_before_financial_income": fcfe_before_financial_income, "financial_income_after_tax": fin_income,
        "issuance_cash": issuance_cash, "treasury_sale_cash": treasury_sale_cash,
        "employee_refund_cash": employee_refund_cash, "parent_sub_dividends": actual_sub_dividend,
        "parent_profit_after_loss_absorption": profit_after_loss_absorption,
        "parent_legal_distribution_capacity": legal_capacity,
        "parent_old_trade_collections": actual_trade, "parent_statutory_add": statutory_add,
        "distribution_requested": desired_distribution, "distribution_actual": distribution,
        "distribution_shortfall_policy_adjusted": desired_distribution - distribution,
        "distribution_per_share": per_share(distribution, participating),
        "participating_shares_million": participating, "state_after_distribution": copy.deepcopy(state),
    }


def terminal(row, s):
    st, g = row["state_after_distribution"], s["terminal_growth"]
    sustainable_nopat = row["nopat"] * (1 + g)
    # Stable operating capital grows with sales: no zero-capital perpetual growth.
    growth_reinvestment = (st["nwc"] + st["fixed"]) * g
    sustainable_fcff = sustainable_nopat - growth_reinvestment
    operating_ev = sustainable_fcff / (s["wacc"] - g)
    equity = operating_ev + st["pool"] - st["debt"]
    valuation_status = ("NOT_ADOPTABLE_NEGATIVE_STEADY_CASH" if sustainable_fcff < 0
                        else "NOT_ADOPTABLE_NEGATIVE_RESIDUAL" if equity < 0 else "APPLICABLE_CONDITIONAL")
    return {"valuation_status":valuation_status, "negative_residual_is_not_shareholder_payment_obligation":True,
            "operating_ev": operating_ev, "financial_assets_ex_operating_cash": st["pool"],
            "financial_debt_deducted_once": st["debt"], "equity_value": equity,
            "per_share": per_share(equity, row["participating_shares_million"]),
            "next_nopat": sustainable_nopat, "growth_reinvestment": growth_reinvestment,
            "next_fcff": sustainable_fcff, "implied_operating_roic": (
                sustainable_nopat / (st["nwc"] + st["fixed"]) if st["nwc"] + st["fixed"] > 0 else None)}


def finite_award_adjustment_pv(future_rows, wacc, valuation_time):
    return sum(x["matched_known_award_expense_cash_adjustment"] /
               (1+wacc)**(x["time_from_cutoff"]-valuation_time) for x in future_rows)


def method2_at_year5(row, s, future_rows):
    st = row["state_after_distribution"]
    g = s["method2_normal_growth"]
    # Recurring compensation remains an expense. Finite already-claimed awards are not a perpetuity.
    owner_earnings = row["nopat"] * (1 + g) - (st["nwc"] + st["fixed"]) * g
    core_ev = owner_earnings * s["method2_multiple"]
    finite_awards = finite_award_adjustment_pv(future_rows, s["wacc"], row["time_from_cutoff"])
    equity = core_ev + st["pool"] - st["debt"] + finite_awards
    return {"normalized_operating_owner_earnings": owner_earnings, "multiple_assumption": s["method2_multiple"],
            "core_ev": core_ev, "financial_assets": st["pool"], "debt": st["debt"],
            "finite_matched_award_adjustment_present_value":finite_awards,
            "common_equity_residual":equity,
            "valuation_status":"NOT_ADOPTABLE_NEGATIVE_RESIDUAL" if equity < 0 else "APPLICABLE_CONDITIONAL",
            "per_share": per_share(equity, row["participating_shares_million"])}


def value_existing_rows(rows, s, cutoff_state):
    """Operating DCF plus financial principal once; same future base state for Y5.

    Known conditional claims use a conservative upfront fully-diluted claim count.
    This is not a statement that these shares are legally issued/participating now.
    Actual D uses each year's participation ledger. No payout-dependent discount
    is imposed on all currently liquid financial assets.
    """
    tv = terminal(rows[-1], s)
    w = s["wacc"]
    terminal_time = rows[-1]["time_from_cutoff"]
    full_claim_shares = rows[-1]["participating_shares_million"]
    op_ev = sum(x["fcff"] / (1+w)**x["time_from_cutoff"] for x in rows)
    op_ev += tv["operating_ev"] / (1+w)**terminal_time
    external_equity_funding_pv = sum((x["issuance_cash"] + x["treasury_sale_cash"] - x["employee_refund_cash"]) / (1+w)**x["time_from_cutoff"] for x in rows)
    equity0 = op_ev + cutoff_state["pool"] - cutoff_state["debt"] + external_equity_funding_pv
    value = per_share(equity0, full_claim_shares)
    year5_time = rows[4]["time_from_cutoff"]
    op_ev5 = sum(x["fcff"] / (1+w)**(x["time_from_cutoff"]-year5_time) for x in rows[5:])
    op_ev5 += tv["operating_ev"] / (1+w)**(terminal_time-year5_time)
    future_funding5 = sum((x["issuance_cash"] + x["treasury_sale_cash"] - x["employee_refund_cash"]) / (1+w)**(x["time_from_cutoff"]-year5_time) for x in rows[5:])
    state5 = rows[4]["state_after_distribution"]
    equity5 = op_ev5 + state5["pool"] - state5["debt"] + future_funding5
    y5 = per_share(equity5, full_claim_shares)
    tv["current_operating_ev"] = op_ev
    tv["current_financial_principal"] = cutoff_state["pool"]
    tv["current_debt_deducted_once"] = cutoff_state["debt"]
    tv["future_external_funding_present_value"] = external_equity_funding_pv
    tv["current_fully_diluted_claims_million_conservative"] = full_claim_shares
    tv["year5_operating_ev"] = op_ev5
    tv["year5_financial_principal_after_paid_D"] = state5["pool"]
    tv["current_common_equity_residual"] = equity0
    tv["year5_common_equity_residual"] = equity5
    tv["method1_current_status"] = ("NOT_ADOPTABLE_NEGATIVE_RESIDUAL" if equity0 < 0 else tv["valuation_status"])
    tv["method1_year5_status"] = ("NOT_ADOPTABLE_NEGATIVE_RESIDUAL" if equity5 < 0 else tv["valuation_status"])
    return value, y5, tv


def _simulate_path_impl(data, scenario, partial, emit):
    partial["stage"] = "validate_inputs"
    validate(data, scenario)
    s = copy.deepcopy(scenario)
    partial["stage"] = "opening_state"
    state = starting_state(data, s)
    initial_state = copy.deepcopy(state)
    partial["initial_state"] = copy.deepcopy(state)
    partial["opening_other_nwc_bridge"] = copy.deepcopy(data["opening_other_nwc_bridge"])
    if s["use_october_balance_bridge"]:
        q4_revenue = data["history"]["fy25_q4_revenue"] * (1 + s["q4_2026_revenue_growth"])
        annual_revenue = data["history"]["q3_revenue"] + q4_revenue
        partial.update(stage="october_stub", failing_year=2026, step_work={})
        q4 = step(state, annual_revenue, q4_revenue / 3, s["october_stub_input"], s, 1 / 12, 0.0, work=partial["step_work"])
        partial["october_balance_estimate"] = copy.deepcopy(q4)
        if emit is not None:
            emit({"event":"PATH_OCTOBER_BALANCE", "scenario_id":s["id"], "row":q4})
    else:
        annual_revenue, q4 = s["test_or_anchor_annual_revenue"], None
    cutoff_state = copy.deepcopy(state)
    partial["cutoff_state_estimate"] = copy.deepcopy(state)
    cn_underlying = annual_revenue * (1 - s["foreign_share_anchor"])
    foreign_underlying = annual_revenue * s["foreign_share_anchor"]
    rows = []
    for i, y in enumerate(s["years"]):
        cn_underlying *= 1 + y["cn_growth"]
        foreign_underlying *= 1 + y["foreign_underlying_growth"]
        foreign_actual = foreign_underlying * (1 - s["foreign_exposure_fraction"] + s["foreign_exposure_fraction"] * y["exposure_availability"])
        revenue = cn_underlying + foreign_actual
        partial.update(stage="annual_step", failing_year=y["year"], step_work={})
        if emit is not None:
            emit({"event":"PATH_STEP_STARTED", "scenario_id":s["id"], "year":y["year"], "state_before":copy.deepcopy(state), "year_input":copy.deepcopy(y)})
        row = step(state, revenue, revenue, y, s, 1.0, i + 1.0, work=partial["step_work"])
        row.update(period_end=f"{2027+i}-10-31", domestic_revenue=cn_underlying, foreign_revenue=foreign_actual,
                   foreign_underlying_before_conditional_risk=foreign_underlying,
                   conditional_exposed_foreign_bucket=foreign_underlying * s["foreign_exposure_fraction"])
        rows.append(row)
        partial["completed_rows"].append(copy.deepcopy(row))
        if emit is not None:
            emit({"event":"PATH_STEP_COMPLETED", "scenario_id":s["id"], "row":row})
    partial.update(stage="method1_valuation", failing_year=None, step_work={})
    value, y5, tv = value_existing_rows(rows, s, cutoff_state)
    partial["completed_valuation"] = {"method1_current":value, "method1_year5":y5, "terminal":copy.deepcopy(tv)}
    partial["stage"] = "method2_valuation"
    r = s["equity_discount"]
    year5_time = rows[4]["time_from_cutoff"]
    m2 = method2_at_year5(rows[4], s, rows[5:])
    m2_first = method2_at_year5(rows[0], s, rows[1:])
    finite_awards_current = finite_award_adjustment_pv(rows, s["wacc"], 0.0)
    explicit_extra_investments = sum((y["extra_physical_capex"] + y["extra_cash_restructuring"]) / (1+s["wacc"])**(i+1) for i, y in enumerate(s["years"]))
    m2_equity_current = (m2_first["core_ev"] + cutoff_state["pool"] - cutoff_state["debt"] + tv["future_external_funding_present_value"] - explicit_extra_investments + finite_awards_current)
    m2_current = per_share(m2_equity_current, tv["current_fully_diluted_claims_million_conservative"])
    partial["completed_valuation"].update(method2_current=m2_current, method2_year5=copy.deepcopy(m2))
    partial["stage"] = "final_diagnostics"
    # This is a genuine state continuity diagnostic, not a pass based on value size.
    terminal_cash_jump = tv["next_fcff"] - rows[-1]["fcff"]
    transition = {"year5_to_year6_revenue_change": rows[5]["revenue"] - rows[4]["revenue"],
                  "year5_to_year6_ebit_margin_change": rows[5]["ebit_margin_after_all_embedded_compensation"] - rows[4]["ebit_margin_after_all_embedded_compensation"],
                  "year5_to_year6_nwc_change": rows[5]["nwc"] - rows[4]["nwc"],
                  "year10_to_terminal_fcff_change": terminal_cash_jump,
                  "requires_economic_review_not_auto_pass": True}
    return {"scenario_id": s["id"], "role": s["role"], "status": "CALCULATED_NOT_RESEARCH_ACCEPTED",
            "initial_state": initial_state, "cutoff_state_estimate": cutoff_state, "october_balance_estimate": q4, "annual_rows": rows,
            "method1_operating_cash_state_dcf_per_share": value,
            "method2_owner_earnings_per_share": m2_current, "method2_year5": m2,
            "method2_first_forward_year_normalization": m2_first,
            "method2_explicit_extra_investments_present_value": explicit_extra_investments,
            "method2_finite_matched_award_present_value":finite_awards_current,
            "method2_current_common_equity_residual":m2_equity_current,
            "method_status":{"method1_current":tv["method1_current_status"], "method1_year5":tv["method1_year5_status"], "method2_current":"NOT_ADOPTABLE_NEGATIVE_RESIDUAL" if m2_equity_current < 0 else "APPLICABLE_CONDITIONAL", "method2_year5":m2["valuation_status"]},
            "operating_status":"COMPLETE",
            "holder_pv_first_five_D_and_method1_Y5_diagnostic": sum(x["distribution_per_share"]/(1+r)**x["time_from_cutoff"] for x in rows[:5]) + y5/(1+r)**year5_time,
            "five_year_distributions_per_share": [x["distribution_per_share"] for x in rows[:5]],
            "year5_equity_value_per_share_method1": y5, "year10_terminal": tv,
            "transition_diagnostics": transition, "historical_normalization": historical_bridges(data, s),
            "valuation_description": "Operating FCFF DCF plus current financial principal and discounted new subscription/treasury-sale proceeds, less financial debt once; known conditional shares included upfront as conservative fully-diluted claims. Actual D uses annual participation; Y5 uses the same base cash/share state with paid D removed.",
            "unknown_law_not_encoded_as_known_fact": True}


def simulate_path(data, scenario, emit=None):
    partial = {"scenario_id":scenario.get("id", "unidentified"), "scenario_input":copy.deepcopy(scenario),
               "initial_state":None, "cutoff_state_estimate":None, "october_balance_estimate":None,
               "completed_rows":[], "completed_valuation":{}, "stage":"entry", "step_work":{}}
    try:
        return _simulate_path_impl(data, scenario, partial, emit)
    except Exception as exc:
        partial["error_classification"] = "ECONOMIC_CASH_INFEASIBILITY" if isinstance(exc, EconomicInfeasible) else "PROGRAM_PARAMETER_ASSERTION_OR_IO_ERROR"
        partial["exception_type"] = type(exc).__name__
        partial["exception_message"] = str(exc)
        exc.scenario_partial = copy.deepcopy(partial)
        if emit is not None:
            try:
                emit({"event":"PATH_PARTIAL_FAILURE", "scenario_id":partial["scenario_id"], "partial":partial})
            except Exception as logging_error:
                logging_error.scenario_partial = copy.deepcopy(partial)
                logging_error.raw_failure_logging_error = repr(logging_error)
                logging_error.original_exception = {"type":type(exc).__name__, "message":str(exc),
                                                    "classification":partial["error_classification"]}
                raise logging_error from exc
        raise


def run_scenario(data, s, emit=None):
    try:
        return simulate_path(data, s, emit=emit)
    except EconomicInfeasible as exc:
        return {"scenario_id": s["id"], "role": s["role"], "status": "ECONOMICALLY_INFEASIBLE",
                "operating_status":"CASH_OR_PAYMENT_CAPACITY_EXHAUSTED",
                "valuation": None, "reason": exc.stage, "details": exc.details,
                "partial":getattr(exc, "scenario_partial", {})}


def scenario_set(data):
    # Only explicitly listed single-variable diagnostics; no Cartesian grid search.
    out = [copy.deepcopy(x) for x in data["scenarios"]]
    base = next(x for x in data["scenarios"] if x["id"] == "base")
    for z in data["isolated_sensitivities"]:
        s = copy.deepcopy(base)
        s["id"], s["role"] = z["id"], "isolated_diagnostic_not_core_endpoint"
        for k, v in z.get("scenario_overrides", {}).items():
            s[k] = copy.deepcopy(v)
        for event in z.get("year_overrides", []):
            index = event["year"] - 2027
            for k, v in event["changes"].items():
                s["years"][index][k] = v
        out.append(s)
    ensure(len(out) <= 16, "unexpected scenario expansion")
    return out
