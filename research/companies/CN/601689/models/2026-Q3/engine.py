"""Tuopu operating/capital/parent-cash model. Definitions only on import.

Amounts are CNY yuan. This module was written in a NO-EXECUTION phase.
The public complete entry point is run_model.py, never this module.
"""
from copy import deepcopy
from math import isfinite


class EconomicInfeasible(Exception):
    """A researched path has no supported financing/ownership continuation."""

    def __init__(self, reason, detail, partial_rows):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.partial_rows = deepcopy(partial_rows)


def close(actual, expected, label):
    """Technical conservation failure is not an economic zero/null valuation."""
    tolerance = max(0.02, abs(expected) * 1e-10)
    if not isfinite(actual) or not isfinite(expected) or abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: actual={actual!r}, expected={expected!r}")


def deep_update(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = deepcopy(value)
    return target


def make_case(inputs, path_name, diagnostic=None):
    case = deepcopy(inputs)
    case["budget"] = deepcopy(inputs["base"])
    deep_update(case["budget"], inputs["paths"][path_name]["overrides"])
    case["case_name"] = path_name
    if diagnostic is not None:
        if path_name != "base":
            raise ValueError("Diagnostics are isolated base perturbations, not combinations")
        deep_update(case, inputs["diagnostics"][diagnostic])
        case["case_name"] += "__" + diagnostic
    return case


def initial_state(case):
    z = case["initial"]
    noncash_assets = sum(z[k] for k in (
        "trade_receivables", "notes_receivable", "receivable_financing",
        "inventory_net", "operating_prepayments", "other_receivables",
        "other_current_assets_vat_led", "known_non_cash_equivalent_money_q3"))
    operating_liabilities = sum(z[k] for k in (
        "trade_payables", "notes_payable", "contract_liabilities",
        "payroll_payable", "taxes_payable", "other_payables",
        "other_current_liabilities")) - z["capital_payable_classification_budget"]
    fixed = sum(z[k] for k in (
        "ppe_net", "construction_in_progress", "right_of_use_assets",
        "intangibles", "long_term_prepaid_expenses", "investment_property_operating",
        "other_noncurrent_assets")) - z["equity_prepayment_classification_budget"]
    financial_value = (z["associate_book"] * z["associate_value_factor"]
                       + z["other_financial_book"] * z["other_financial_value_factor"]
                       + z["equity_prepayment_classification_budget"]
                       * z["equity_prepayment_value_factor"])
    bank = (z["bank_short_debt"] + z["bank_noncurrent_debt"]
            + z["current_noncurrent_liabilities_total"]
            - z["lease_current_split_budget_from_h1"])
    lease = z["lease_current_split_budget_from_h1"] + z["lease_noncurrent_debt"]
    close(bank + lease, z["bank_short_debt"] + z["bank_noncurrent_debt"]
          + z["current_noncurrent_liabilities_total"] + z["lease_noncurrent_debt"],
          "opening debt has one current lease component")
    state = {
        "cash": z["cash_and_equivalents_q3"] + z["trading_deposits_q3"],
        "minimum_cash": z["minimum_operating_cash_budget"],
        "earmarked": z["unused_fundraising_earmark_budget"],
        "noncash_nwc": noncash_assets - operating_liabilities,
        "fixed_operating_capital": fixed,
        "capital_payable": z["capital_payable_classification_budget"],
        "goodwill": z["goodwill_in_return_denominator"],
        "bank_debt": bank, "lease_debt": lease,
        "financial_value": financial_value,
        "nci_book": z["nci_book"],
        "parent_cash": z["parent_cash_h1"] + z["parent_trading_deposits_h1"],
        "parent_re": z["parent_re_h1"],
        "parent_statutory_reserve": z["parent_statutory_reserve_h1"],
        "parent_discretionary_reserve": z["parent_discretionary_reserve"],
        "parent_bank_debt": z["parent_bank_debt_budget"],
        "parent_dividend_receivable": z["parent_dividend_receivable"],
        "eligible_sub_re": z["domestic_subsidiary_distributable_re_budget"],
        "previous_common_profit": z["prior_year_common_profit_budget"],
        "segment_revenue": deepcopy(z["segment_revenue_fy26"]),
    }
    state["operating_capital"] = operating_capital(state)
    return state


def operating_capital(state):
    return (state["fixed_operating_capital"] + state["goodwill"]
            + state["noncash_nwc"] + state["minimum_cash"] - state["capital_payable"])


def parent_claim_step(opening_re, opening_ar, own_net_profit, declared_dividend,
                      actual_received, reserve_rate, cash_before_receipt):
    """Formal chain: old dividend collection is cash, not a second income event."""
    if actual_received < 0 or actual_received > opening_ar + declared_dividend + 0.01:
        raise ValueError("receipt exceeds parent dividend claim")
    income = own_net_profit + declared_dividend
    reserve = max(income, 0.0) * reserve_rate
    return {
        "recognized_income": income,
        "reserve_transfer": reserve,
        "legal_re_before_distribution": opening_re + income - reserve,
        "dividend_receivable_after_collection": opening_ar + declared_dividend - actual_received,
        "cash_after_collection": cash_before_receipt + actual_received,
    }


def project(case, on_row=None):
    """Full business + capital + group + parent chain; no price/IRR input."""
    s, b, z = case["shared"], case["budget"], case["initial"]
    state = initial_state(case)
    opening = deepcopy(state)
    rows = []
    for index in range(case["forecast_years"]):
        old = deepcopy(state)
        segments = {k: old["segment_revenue"][k] * (1 + b["growth"][k][index])
                    for k in old["segment_revenue"]}
        revenue = sum(segments.values())
        gp = sum(segments[k] * b["gross_margin"][k][index] for k in segments)
        rd, sga = revenue * b["rd_rate"][index], revenue * b["sga_rate"][index]
        business_tax = revenue * s["business_tax_rate"]
        normal_loss = revenue * s["normal_credit_inventory_loss_rate"]
        fx_loss = revenue * s["normal_transaction_fx_loss_rate"]
        support = revenue * s["recurring_operating_support_rate"]
        extra_cost = b["additional_operating_cost"][index]
        ebit = gp - rd - sga - business_tax - normal_loss - fx_loss + support - extra_cost
        operating_tax = max(ebit, 0.0) * s["tax_rate"]
        nopat = ebit - operating_tax
        da = revenue * b["da_rate"][index]
        maintenance = revenue * b["maintenance_including_leases_sales_rate"][index]
        lease_add = b["lease_asset_additions"][index]
        growth_capital = b["growth_capital_cash_budget"][index]
        if maintenance + 0.01 < lease_add:
            raise ValueError("Lease replacements exceed total maintenance budget")
        cash_capex = maintenance - lease_add + growth_capital
        economic_capital_additions = maintenance + growth_capital
        tail_paid = b["capital_payable_cash_settlement"][index]
        if tail_paid > old["capital_payable"] + 0.01:
            raise ValueError("Capital payable paid twice")
        funded_use = b["fundraising_eligible_cash_use"][index]
        if funded_use > min(old["earmarked"], growth_capital + tail_paid) + 0.01:
            raise ValueError("Earmark released without eligible actual capital payment")
        earmarked = old["earmarked"] - funded_use
        nwc = revenue * b["noncash_nwc_sales_ratio"][index]
        minimum_cash = revenue * s["minimum_operating_cash_sales_ratio"]
        delta_nwc = nwc - old["noncash_nwc"]
        delta_minimum_cash = minimum_cash - old["minimum_cash"]
        fcff = (nopat + da - economic_capital_additions - tail_paid
                - delta_nwc - delta_minimum_cash)
        fixed = old["fixed_operating_capital"] + economic_capital_additions - da
        capital_payable = old["capital_payable"] - tail_paid
        if fixed < -0.01:
            raise EconomicInfeasible("negative_operating_asset_state", {"year": index + 1}, rows)
        capital = fixed + old["goodwill"] + nwc + minimum_cash - capital_payable
        close(fcff, nopat - (capital - old["operating_capital"]), "FCFF/operating capital identity")

        # Net new debt is a year-end financing budget; opening balances earn/pay
        # the entire year's interest. Never an unmodelled midyear free cash plug.
        interest = (old["bank_debt"] * s["bank_interest_rate"]
                    + old["lease_debt"] * s["lease_interest_rate"])
        shield_rate = s["tax_rate"] if ebit > 0 else 0.0
        cash_interest_cost = interest * (1 - shield_rate)
        cash_income = old["cash"] * s["cash_yield_after_tax"]
        financial_income = old["financial_value"] * s["financial_asset_yield_after_tax"]
        total_profit = nopat - cash_interest_cost + cash_income + financial_income
        nci_profit = total_profit * s["nci_profit_share"]
        common_profit = total_profit - nci_profit
        nci_paid = max(nci_profit, 0.0) * s["nci_cash_payout_fraction"]
        lease_principal = min(old["lease_debt"], b["lease_principal_payments"][index])
        group_cash_pre_financing = (old["cash"] + fcff + delta_minimum_cash + lease_add
                                    - lease_principal - cash_interest_cost
                                    + cash_income + financial_income)
        lease_debt = old["lease_debt"] + lease_add - lease_principal

        scale = 1.0 + s["parent_budget_revenue_elasticity"] * (
            revenue / z["revenue_budget_fy26"] - 1.0)
        parent_interest = old["parent_bank_debt"] * s["bank_interest_rate"] * (1 - shield_rate)
        parent_cash_income = old["parent_cash"] * s["cash_yield_after_tax"]
        own_parent_profit = (s["parent_own_aftertax_preinterest_profit_anchor"] * scale
                             - parent_interest + parent_cash_income + financial_income)
        parent_own_operating_cash = s["parent_own_operating_cash_anchor"] * scale
        parent_pre_receipt = (old["parent_cash"] + parent_own_operating_cash
                              - parent_interest + parent_cash_income + financial_income
                              - b["parent_cash_capex"][index]
                              - b["parent_downstream_cash_investment"][index]
                              + b["parent_net_internal_settlement"][index])
        # If subsidiaries require more cash than the baseline internal budget,
        # the parent must fund that deficit before taking any remittance. This
        # is an internal transfer, not another consolidated cost or profit.
        additional_parent_support = max(parent_pre_receipt - group_cash_pre_financing
                                        + s["subsidiary_remittance_cash_buffer"], 0.0)
        parent_pre_receipt -= additional_parent_support
        eligible_sub_profit = max(common_profit - own_parent_profit, 0.0) * s["domestic_eligible_sub_profit_fraction"]
        eligible_sub_re_before = old["eligible_sub_re"] + eligible_sub_profit
        sub_declared = min(b["domestic_sub_dividend_declaration_budget"][index],
                           max(eligible_sub_re_before, 0.0))
        requested_receipt = (old["parent_dividend_receivable"]
                             + sub_declared * s["subsidiary_dividend_current_receipt_fraction"])
        sub_cash_capacity = max(group_cash_pre_financing - parent_pre_receipt
                                - s["subsidiary_remittance_cash_buffer"], 0.0)
        sub_received = min(requested_receipt, sub_cash_capacity)
        parent_claim = parent_claim_step(old["parent_re"], old["parent_dividend_receivable"],
                                         own_parent_profit, sub_declared, sub_received,
                                         s["statutory_reserve_policy_rate"], parent_pre_receipt)
        parent_pre_financing = parent_claim["cash_after_collection"]

        group_need = max(minimum_cash + earmarked + nci_paid - group_cash_pre_financing, 0.0)
        parent_need = max(s["parent_minimum_cash"] + earmarked - parent_pre_financing, 0.0)
        new_bank_debt = max(group_need, parent_need)
        debt_limit = min(revenue * s["maximum_bank_and_lease_debt_sales_ratio"],
                         max(ebit + da, 0.0) * s["maximum_bank_and_lease_debt_ebitda_multiple"])
        debt_headroom = max(debt_limit - old["bank_debt"] - lease_debt, 0.0)
        if new_bank_debt > debt_headroom + 0.02:
            detail = {"year": index + 1, "group_cash_need": group_need,
                      "parent_cash_need": parent_need, "required_new_debt": new_bank_debt,
                      "supported_debt_headroom": debt_headroom,
                      "parent_dividend_receivable": parent_claim["dividend_receivable_after_collection"],
                      "fcff": fcff, "nopat": nopat}
            raise EconomicInfeasible("unsupported_group_or_parent_funding_gap", detail, rows)
        if parent_pre_financing > group_cash_pre_financing + 0.02:
            raise EconomicInfeasible("parent_cash_budget_exceeds_consolidated_cash",
                                     {"year": index + 1, "parent": parent_pre_financing,
                                      "group": group_cash_pre_financing}, rows)
        group_before_distribution = group_cash_pre_financing + new_bank_debt
        parent_before_distribution = parent_pre_financing + new_bank_debt
        target = (max(old["previous_common_profit"], 0.0)
                  * s["payout_rate_prior_year_common_profit"] + s["special_distributions"][index])
        legal_capacity = max(parent_claim["legal_re_before_distribution"], 0.0)
        parent_cash_capacity = max(parent_before_distribution - s["parent_minimum_cash"] - earmarked, 0.0)
        group_cash_capacity = max(group_before_distribution - minimum_cash - earmarked - nci_paid, 0.0)
        paid = min(target, legal_capacity, parent_cash_capacity, group_cash_capacity)
        bank_debt = old["bank_debt"] + new_bank_debt
        state.update({
            "cash": group_before_distribution - nci_paid - paid,
            "minimum_cash": minimum_cash, "earmarked": earmarked,
            "noncash_nwc": nwc, "fixed_operating_capital": fixed,
            "capital_payable": capital_payable, "operating_capital": capital,
            "bank_debt": bank_debt, "lease_debt": lease_debt,
            "nci_book": old["nci_book"] + nci_profit - nci_paid,
            "parent_cash": parent_before_distribution - paid,
            "parent_re": parent_claim["legal_re_before_distribution"] - paid,
            "parent_statutory_reserve": old["parent_statutory_reserve"] + parent_claim["reserve_transfer"],
            "parent_bank_debt": old["parent_bank_debt"] + new_bank_debt,
            "parent_dividend_receivable": parent_claim["dividend_receivable_after_collection"],
            "eligible_sub_re": eligible_sub_re_before - sub_declared,
            "previous_common_profit": common_profit, "segment_revenue": segments,
        })
        close(state["cash"], old["cash"] + fcff + delta_minimum_cash + lease_add
              - lease_principal - cash_interest_cost + cash_income + financial_income
              + new_bank_debt - nci_paid - paid, "consolidated cash conservation")
        close(state["parent_re"] + state["parent_statutory_reserve"],
              old["parent_re"] + old["parent_statutory_reserve"] + own_parent_profit
              + sub_declared - paid, "parent RE/reserve transfer is not group cash expense")
        if state["cash"] < minimum_cash + earmarked - 0.02 or state["parent_cash"] < s["parent_minimum_cash"] + earmarked - 0.02:
            raise AssertionError("Distribution violated funded cash floor")
        row = {
            "year": index + 1, "calendar_budget_label": case["operating_budget_calendar_labels"][index],
            "revenue": revenue, "segment_revenue": segments, "gross_profit": gp,
            "gross_margin": gp / revenue if revenue else 0.0,
            "research_cost": rd, "sga_cost": sga, "extra_operating_cost": extra_cost,
            "ebit": ebit, "nopat": nopat, "da": da,
            "operating_return_on_average_capital": (nopat / ((old["operating_capital"] + capital) / 2)
                if old["operating_capital"] + capital > 0 else None),
            "maintenance_including_leases": maintenance,
            "growth_capital_cash": growth_capital, "cash_capex_excluding_tail": cash_capex,
            "capital_payable_paid": tail_paid, "lease_asset_added": lease_add,
            "economic_capital_additions": economic_capital_additions,
            "delta_noncash_nwc": delta_nwc, "delta_minimum_cash": delta_minimum_cash,
            "fcff": fcff, "fundraising_used_on_capital": funded_use,
            "group_interest_after_tax": cash_interest_cost, "new_bank_debt": new_bank_debt,
            "lease_principal_paid": lease_principal,
            "common_profit": common_profit, "nci_profit": nci_profit, "nci_cash_paid": nci_paid,
            "parent_own_operating_cash": parent_own_operating_cash,
            "parent_own_net_profit": own_parent_profit,
            "additional_parent_support_to_subsidiaries": additional_parent_support,
            "sub_dividend_declared": sub_declared, "sub_dividend_received": sub_received,
            "sub_cash_remittance_capacity": sub_cash_capacity,
            "parent_reserve_transfer": parent_claim["reserve_transfer"],
            "target_common_distribution": target, "actual_common_distribution": paid,
            "distribution_reduced": paid + 0.02 < target,
            "distribution_capacities": {"legal": legal_capacity, "parent_cash": parent_cash_capacity,
                                        "group_cash": group_cash_capacity},
            "end": deepcopy(state),
        }
        rows.append(row)
        if on_row is not None:
            on_row(deepcopy(row))
    return {"case_name": case["case_name"], "opening": opening, "rows": rows,
            "case": case, "terminal": terminal_state(case, rows)}


def terminal_state(case, rows):
    last = rows[-1]
    state, s = last["end"], case["shared"]
    g = s["terminal_growth"]
    if state["earmarked"] > 0.02 or state["capital_payable"] > 0.02:
        raise EconomicInfeasible("unsettled_capital_or_proceeds_at_terminal", state, rows)
    revenue = last["revenue"] * (1 + g)
    ebit = last["ebit"] * (1 + g)
    nopat = ebit - max(ebit, 0.0) * s["tax_rate"]
    da = last["da"] * (1 + g)
    fixed_growth = state["fixed_operating_capital"] * g
    nwc_growth = state["noncash_nwc"] * g
    min_cash_growth = state["minimum_cash"] * g
    economic_capex = da + fixed_growth
    fcff = nopat - fixed_growth - nwc_growth - min_cash_growth
    margin = ebit / revenue if revenue else 0.0
    previous_margin = last["ebit"] / last["revenue"] if last["revenue"] else 0.0
    if abs(margin - previous_margin) > s["maximum_terminal_margin_step"]:
        raise EconomicInfeasible("terminal_margin_jump", {"before": previous_margin, "after": margin}, rows)
    if abs(last["fcff"]) > 1.0:
        fcf_step = abs(fcff / last["fcff"] - 1)
    else:
        fcf_step = None
    last_intensity = last["economic_capital_additions"] / last["revenue"] if last["revenue"] else 0.0
    intensity = economic_capex / revenue if revenue else 0.0
    intensity_step = abs(intensity / last_intensity - 1) if last_intensity else 0.0
    # Diagnostic thresholds do not establish an economic funding failure.
    # Keep finite values and the cash/capital bridge; require an explanation
    # before adoption instead of discarding the entire calculated path.
    diagnostics = [
        {"metric": "terminal_fcf_relative_step", "value": fcf_step,
         "threshold": s["maximum_terminal_fcf_step_fraction"],
         "requires_explanation": fcf_step is not None and fcf_step > s["maximum_terminal_fcf_step_fraction"]},
        {"metric": "terminal_capital_intensity_step", "value": intensity_step,
         "threshold": s["maximum_terminal_capital_intensity_step"],
         "requires_explanation": intensity_step > s["maximum_terminal_capital_intensity_step"]},
    ]
    continuity_decomposition = {
        "last_explicit_period": {
            "nopat": last["nopat"], "da": last["da"],
            "economic_capital_additions": last["economic_capital_additions"],
            "capital_payable_paid": last["capital_payable_paid"],
            "delta_noncash_nwc": last["delta_noncash_nwc"],
            "delta_minimum_cash": last["delta_minimum_cash"], "fcff": last["fcff"],
            "economic_capital_intensity": last_intensity},
        "first_terminal_period": {
            "nopat": nopat, "da": da, "maintenance_including_leases": da,
            "fixed_growth_capital": fixed_growth, "economic_capex": economic_capex,
            "nwc_growth": nwc_growth, "minimum_cash_growth": min_cash_growth,
            "fcff": fcff, "economic_capital_intensity": intensity},
    }
    return {"revenue": revenue, "ebit": ebit, "nopat": nopat, "da": da,
            "maintenance_including_leases": da, "fixed_growth_capital": fixed_growth,
            "nwc_growth": nwc_growth, "minimum_cash_growth": min_cash_growth,
            "economic_capex": economic_capex, "fcff": fcff,
            "terminal_fcf_relative_step": fcf_step, "capital_intensity_step": intensity_step,
            "diagnostics": diagnostics,
            "requires_explanation": any(item["requires_explanation"] for item in diagnostics),
            "continuity_decomposition": continuity_decomposition}


def equity_bridge(state, nci_value_factor):
    # Earmarked cash is NOT deducted here: its matching future expenditure is
    # already deducted from enterprise CF. It IS withheld from dividend cash.
    return {"excess_cash": state["cash"] - state["minimum_cash"],
            "financial_assets": state["financial_value"],
            "bank_debt": -state["bank_debt"], "lease_debt": -state["lease_debt"],
            "nci_value": -max(state["nci_book"], 0.0) * nci_value_factor}


def value_projection(projection, discount_rate):
    case, rows = projection["case"], projection["rows"]
    g = case["shared"]["terminal_growth"]
    if discount_rate <= g:
        raise ValueError("Discount rate must exceed terminal growth")
    n = len(rows)
    terminal_ev = projection["terminal"]["fcff"] / (discount_rate - g)
    explicit_pv = sum(row["fcff"] / (1 + discount_rate) ** row["year"] for row in rows)
    terminal_pv = terminal_ev / (1 + discount_rate) ** n
    operating_ev = explicit_pv + terminal_pv
    bridge0 = equity_bridge(projection["opening"], case["initial"]["nci_value_factor"])
    equity = operating_ev + sum(bridge0.values())
    five = rows[4]["end"]
    ev5 = sum(row["fcff"] / (1 + discount_rate) ** (row["year"] - 5) for row in rows[5:])
    ev5 += terminal_ev / (1 + discount_rate) ** (n - 5)
    bridge5 = equity_bridge(five, case["initial"]["nci_value_factor"])
    equity5 = ev5 + sum(bridge5.values())
    if equity <= 0 or equity5 <= 0:
        raise EconomicInfeasible("nonpositive_common_equity_requires_restructuring_or_exit_design",
                                 {"equity_now": equity, "equity_year5": equity5}, rows)
    denom = rows[4]["end"]["operating_capital"] - rows[0]["end"]["operating_capital"]
    incremental_return = ((rows[4]["nopat"] - rows[0]["nopat"]) / denom) if denom > 0 else None
    return {"discount_rate": discount_rate, "terminal_growth": g,
            "terminal_diagnostics": projection["terminal"]["diagnostics"],
            "terminal_requires_explanation": projection["terminal"]["requires_explanation"],
            "adoption_status": ("PENDING_EXPLANATION_NOT_ADOPTED" if projection["terminal"]["requires_explanation"]
                                else "CALCULATED_NOT_ADOPTED"),
            "explicit_operating_cf_pv": explicit_pv, "terminal_operating_pv": terminal_pv,
            "terminal_share_of_operating_value": terminal_pv / operating_ev if operating_ev else None,
            "operating_enterprise_value": operating_ev, "equity_bridge_now": bridge0,
            "common_equity_value": equity, "value_per_share": equity / case["shares"],
            "year5_operating_value": ev5, "equity_bridge_after_D5": bridge5,
            "year5_common_equity_after_D5": equity5,
            "year5_value_per_share_after_D5": equity5 / case["shares"],
            "distributions_per_share": [row["actual_common_distribution"] / case["shares"] for row in rows[:5]],
            "incremental_nopat_return_Y1_end_to_Y5_end": incremental_return,
            "incremental_return_note": "Same Y1-to-Y5 endpoints; null if capital increment nonpositive; not proof of realized project return"}


def solve_one(inputs, path_name, discount_rate, diagnostic=None):
    """Formal complete chain also invoked by the checked-in hand examples."""
    case = make_case(inputs, path_name, diagnostic)
    projection = project(case)
    return {"projection": projection, "valuation": value_projection(projection, discount_rate)}


def normalized_owner_earnings(inputs):
    """Independent static earnings-power method: NEVER reads a DCF projection."""
    p = inputs["method_two"]
    opening = initial_state(make_case(inputs, "base"))
    required_capital = (p["required_productive_capital"]
                        + p["normalized_revenue"] * p["required_noncash_nwc_sales_ratio"]
                        + p["required_operating_cash"])
    results = []
    for margin in p["gross_margin_range"]:
        ebit = p["normalized_revenue"] * (margin - p["rd_rate"] - p["sga_rate"]
                - p["business_tax_rate"] - p["normal_loss_rate"]
                + p["recurring_support_rate"] - p["transaction_fx_rate"])
        nopat = ebit - max(ebit, 0.0) * p["cash_tax_rate"]
        owner_earnings = nopat + p["normal_da"] - p["maintenance_including_lease_replacement"]
        ev = owner_earnings / p["no_growth_capitalization_rate"]
        bridge = equity_bridge(opening, inputs["initial"]["nci_value_factor"])
        # Normalized required operating cash differs from latest current budget.
        bridge["excess_cash"] = opening["cash"] - p["required_operating_cash"]
        residual_capital_cost = (inputs["initial"]["capital_payable_classification_budget"]
                                + p["additional_uncompleted_expansion_obligation_budget"])
        equity = ev + sum(bridge.values()) - residual_capital_cost
        results.append({"normalized_gross_margin": margin, "normalized_ebit": ebit,
                        "normalized_nopat": nopat, "normalized_owner_earnings": owner_earnings,
                        "required_operating_capital": required_capital,
                        "normalized_nopat_return_on_required_capital": nopat / required_capital,
                        "no_growth_enterprise_value": ev, "equity_bridge": bridge,
                        "unpaid_and_completion_capital_deduction": residual_capital_cost,
                        "common_equity_value": equity if equity > 0 else None,
                        "value_per_share": equity / inputs["shares"] if equity > 0 else None,
                        "null_reason": None if equity > 0 else "Nonpositive earnings-power equity; not a certified zero liquidation floor"})
    return {"method": p["name"], "independent_operating_anchors": True,
            "shares_only_and_opening_claims_shared_with_method_one": True, "results": results}
