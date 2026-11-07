"""SF v1 pure standard-library financial functions."""
from copy import deepcopy
from math import isfinite


class EconomicInfeasible(Exception):
    def __init__(self, reason, context=None):
        super().__init__(reason)
        self.reason = reason
        self.context = context or {}


def finite_tree(value, path="root"):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (float, int)):
        if not isfinite(value):
            raise ValueError("non-finite value at " + path)
    elif isinstance(value, dict):
        for key, item in value.items():
            finite_tree(item, path + "." + str(key))
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            finite_tree(item, path + "[" + str(index) + "]")
    else:
        raise TypeError("unsupported data at " + path)


def changed(inputs, overrides):
    result = deepcopy(inputs)
    for path, value in overrides.items():
        keys = path.split(".")
        target = result
        for key in keys[:-1]:
            target = target[key]
        if keys[-1] not in target:
            raise KeyError(path)
        target[keys[-1]] = deepcopy(value)
    return result


def validate_inputs(inputs):
    finite_tree(inputs)
    if inputs["forecast_months"] != 120:
        raise ValueError("contract requires exactly 120 forecast months")
    cap = inputs["capital"]
    if not (0 <= cap["terminal_growth"] < cap["enterprise_discount_rate"]):
        raise ValueError("terminal growth must be below enterprise discount rate")
    for name in ("incremental_roic", "normal_equity_roic_aux"):
        if cap[name] <= cap["terminal_growth"]:
            raise ValueError(name + " must exceed terminal growth")
    if inputs["nci"]["incremental_roic"] <= cap["terminal_growth"]:
        raise ValueError("NCI ROIC must exceed terminal growth")
    if cap["equity_discount_rate_aux"] <= cap["terminal_growth"]:
        raise ValueError("auxiliary discount rate must exceed terminal growth")
    if not 0 <= inputs["fiscal_base"]["tax_rate"] < 1:
        raise ValueError("invalid tax rate")
    for values in inputs["growth_2027_to_2037"].values():
        if len(values) != 11 or any(x <= -1 for x in values):
            raise ValueError("invalid annual growth vector")
    for values in inputs["gross_margin_gain_2027_to_2037"].values():
        if len(values) != 11:
            raise ValueError("invalid margin vector")
    if len(inputs["parent_policy"]["payout_fractions_holding_years"]) != 10:
        raise ValueError("ten payout fractions required")


def regime_changes(year, segment, regime):
    """Only changes named economic paths; no implicit recovery to lost revenue levels."""
    growth = None
    margin = 0.0
    if regime == "cyclical" and segment == "domestic":
        growth = {2027: -0.02, 2028: 0.0, 2029: 0.05, 2030: 0.05}.get(year)
        margin = {2027: -0.008, 2028: -0.004, 2029: -0.001}.get(year, 0.0)
    elif regime == "structural" and year >= 2027:
        if segment == "domestic":
            growth, margin = 0.01, -0.010
        elif segment == "international":
            growth, margin = (0.03 if year <= 2031 else 0.01), -0.005
        else:
            growth = 0.01
    elif regime == "optimistic" and year >= 2027:
        if segment == "domestic":
            growth = {2027: 0.06, 2028: 0.06, 2029: 0.055, 2030: 0.05,
                      2031: 0.045, 2032: 0.035, 2033: 0.03, 2034: 0.025}.get(year)
            margin = 0.004 * min((year - 2026) / 4.0, 1.0)
        elif segment == "international":
            growth = {2027: 0.08, 2028: 0.08, 2029: 0.075, 2030: 0.07,
                      2031: 0.06, 2032: 0.045, 2033: 0.035, 2034: 0.025}.get(year)
            margin = 0.006 * min((year - 2026) / 4.0, 1.0)
    return growth, margin


def annual_budgets(inputs, regime="base", domestic_margin_shift=0.0,
                   lease_cash_multiplier=1.0, nci_profit_multiplier=1.0):
    validate_inputs(inputs)
    base, cap, nci = inputs["fiscal_base"], inputs["capital"], inputs["nci"]
    base_revenue = sum(x["revenue"] for x in base["segments"].values())
    rows = {}
    revenues = {key: value["revenue"] for key, value in base["segments"].items()}
    nci_levels = deepcopy(nci["normal_2026_nopat"])
    for year in range(2026, 2038):
        segment_rows = {}
        for name, spec in base["segments"].items():
            growth = 0.0
            margin_extra = domestic_margin_shift if name == "domestic" else 0.0
            if year > 2026:
                index = year - 2027
                growth = inputs["growth_2027_to_2037"][name][index]
                override_growth, regime_margin = regime_changes(year, name, regime)
                if override_growth is not None:
                    growth = override_growth
                revenues[name] *= 1 + growth
                margin_extra += inputs["gross_margin_gain_2027_to_2037"].get(name, [0.0] * 11)[index]
                margin_extra += regime_margin
            gross = revenues[name] * (spec["gross_margin"] + margin_extra)
            expense = (revenues[name] * spec["opex_ratio"] if "opex_ratio" in spec
                       else spec["opex_fixed"] * revenues[name] / spec["revenue"])
            segment_rows[name] = {"revenue": revenues[name], "growth": growth,
                                  "gross_profit": gross, "operating_expense": expense,
                                  "reported_core_ebit": gross - expense}
        revenue = sum(x["revenue"] for x in segment_rows.values())
        reported_ebit = sum(x["reported_core_ebit"] for x in segment_rows.values())
        scale = revenue / base_revenue
        da_elasticity = (cap["da_revenue_elasticity"]
                         + (1 - cap["da_revenue_elasticity"])
                         * min(max((year - 2031) / 4.0, 0.0), 1.0))
        da = (base["nonrou_da"] if year == 2026 else
              rows[year - 1]["nonrou_da"] * (revenue / rows[year - 1]["revenue"]) ** da_elasticity)
        maintenance = da * cap["maintenance_to_da"]
        rou_da = base["rou_da"] * scale
        lease_cash = base["capitalized_lease_cash"] * scale * lease_cash_multiplier
        cash_ebit = reported_ebit + rou_da - lease_cash
        cash_tax = max(cash_ebit, 0.0) * base["tax_rate"]
        nopat = cash_ebit - cash_tax
        trade_nwc = revenue * base["trade_nwc_ratio"]
        operating_cash = revenue * cap["operating_cash_ratio"]
        if year == 2026:
            revenue_growth = revenue / 308226.647 - 1.0
            delta_wc = None
            growth_capex = base["physical_growth_capex"]
            growth_requirement = None
            nci_growth = nci["normal_2027_2031_growth"]
        else:
            previous = rows[year - 1]
            revenue_growth = revenue / previous["revenue"] - 1.0
            delta_wc = trade_nwc + operating_cash - previous["trade_nwc"] - previous["operating_cash"]
            growth_requirement = max(nopat, 0.0) * max(revenue_growth, 0.0) / cap["incremental_roic"]
            growth_capex = max(0.0, growth_requirement - max(delta_wc, 0.0))
            if year <= 2031:
                nci_growth = nci["normal_2027_2031_growth"]
            else:
                weight = min((year - 2031) / 4.0, 1.0)
                nci_growth = ((1 - weight) * nci["normal_2027_2031_growth"]
                              + weight * cap["terminal_growth"])
            for key in nci_levels:
                nci_levels[key] *= 1 + nci_growth
        nci_layers = {
            "outside_kln_parent": nci_levels["kln_parent"] * nci["kln_top_outside_fraction"] * nci_profit_multiplier,
            "kln_lower": nci_levels["kln_lower"] * nci_profit_multiplier,
            "other": nci_levels["other"] * nci_profit_multiplier
        }
        nci_nopat = sum(nci_layers.values())
        nci_reinvestment = max(nci_nopat, 0.0) * max(nci_growth, 0.0) / nci["incremental_roic"]
        nci_ratio = nci_nopat / nopat if nopat > 0 else 0.0
        replacement_gap = da - maintenance
        nci_gap = replacement_gap * nci_ratio
        rows[year] = {
            "year": year, "segments": segment_rows, "revenue": revenue,
            "gross_margin": sum(x["gross_profit"] for x in segment_rows.values()) / revenue,
            "reported_core_ebit": reported_ebit, "rou_da_addback": rou_da,
            "capitalized_lease_cash": lease_cash, "cash_lease_ebit": cash_ebit,
            "cash_tax": cash_tax, "nopat": nopat, "nonrou_da": da,
            "nonrou_da_revenue_elasticity": da_elasticity,
            "maintenance": maintenance, "physical_growth_capex": growth_capex,
            "total_physical_capex": maintenance + growth_capex,
            "revenue_growth": revenue_growth, "trade_nwc": trade_nwc,
            "operating_cash": operating_cash, "delta_total_wc": delta_wc,
            "growth_capital_requirement": growth_requirement,
            "nci_layers_nopat": nci_layers, "nci_nopat": nci_nopat,
            "nci_growth": nci_growth, "nci_reinvestment": nci_reinvestment,
            "replacement_gap": replacement_gap, "nci_replacement_gap": nci_gap,
            "nci_fcff": nci_nopat - nci_reinvestment + nci_gap
        }
    finite_tree(rows)
    return rows


def monthly_operating_flow(inputs, budgets, year, month):
    row = budgets[year]
    if year == 2026:
        if month not in (10, 11, 12):
            raise ValueError("2026 only supports October through December bridge")
        q3 = inputs["september_2026"]
        trade_at_q3 = sum(q3["trade_nwc_positive"]) - sum(q3["trade_nwc_negative"])
        opening_required_cash = (inputs["capital"]["operating_cash_ratio"]
                                 * inputs["capital"]["operating_cash_revenue_anchor"])
        delta_wc = ((row["trade_nwc"] - trade_at_q3) / 3.0
                    + (row["operating_cash"] - opening_required_cash) / 3.0)
    else:
        delta_wc = row["delta_total_wc"] / 12.0
    group_fcff = (row["nopat"] + row["nonrou_da"] - row["maintenance"]
                  - row["physical_growth_capex"]) / 12.0 - delta_wc
    nci_fcff = row["nci_fcff"] / 12.0
    return {"group_fcff": group_fcff, "nci_fcff": nci_fcff,
            "common_unlevered_fcff": group_fcff - nci_fcff,
            "delta_wc": delta_wc,
            "common_nopat": (row["nopat"] - row["nci_nopat"]) / 12.0}


def initial_state(inputs, budgets, exercise_all_options=False):
    q, nci, cap = inputs["september_2026"], inputs["nci"], inputs["capital"]
    effective = (nci["kln_lower_cash_debt_fraction"] + nci["kln_top_outside_fraction"]
                 * (1 - nci["kln_lower_cash_debt_fraction"]))
    nci_cash = nci["kln_cash_hkd"] * nci["hkd_to_cny_assumption"] * effective + nci["other_nci_cash_cny"]
    nci_opcash = nci["kln_required_operating_cash_cny"] * effective + nci["other_nci_operating_cash_cny"]
    nci_excess = max(nci_cash - nci_opcash, 0.0)
    nci_debt = (sum(nci["kln_nonlease_debt_hkd_components"]) * nci["hkd_to_cny_assumption"]
                * effective + nci["other_nci_debt_cny"])
    group_cash = q["cash_equivalents"] + q["trading_financial_assets"] * q["trading_assets_cashlike_fraction"]
    required_cash = cap["operating_cash_ratio"] * cap["operating_cash_revenue_anchor"]
    group_debt = (q["short_debt"] + q["long_debt"] + q["bonds"]
                  + q["current_noncurrent_liabilities"] - q["current_lease_estimate"]
                  + q["other_nci_loans_from_h1"] + q["supply_chain_finance_from_h1"])
    common_debt = group_debt - nci_debt
    cash_q3 = group_cash - required_cash - nci_excess
    tax = inputs["fiscal_base"]["tax_rate"] if budgets[2026]["nopat"] > 0 else 0.0
    october = monthly_operating_flow(inputs, budgets, 2026, 10)
    debt_interest = common_debt * cap["debt_interest_rate"] * (1 - tax) / 12.0
    cash_interest = max(cash_q3, 0.0) * cap["excess_cash_yield_before_tax"] * (1 - inputs["fiscal_base"]["tax_rate"]) / 12.0
    cash0 = (cash_q3 + october["common_unlevered_fcff"] - debt_interest + cash_interest
             - q["declared_dividend_liability_paid_october"])
    recoveries = q["investment_recovery"]
    investments = (q["longterm_investment_book"] * recoveries[0]
                   + q["fvoci_equity_book"] * recoveries[1]
                   + q["other_financial_book"] * recoveries[2]
                   - nci["other_nci_nonoperating_investment_book"] * recoveries[0])
    issued = (q["issued_a_before_cancellation"] - q["cancelled_a"]
              + q["original_h"] + q["new_h"])
    net_shares = issued - q["treasury_h"]
    pb, policy = inputs["parent_bridge_h1_to_october"], inputs["parent_policy"]
    interim = pb["a_interim_paid"] + pb["h_interim_cash_proxy"]
    parent_profit = pb["new_upstream_declared_and_received_assumption"] - pb["net_parent_expense_assumption"]
    reserve_topup = min(max(parent_profit, 0.0) * policy["statutory_profit_allocation_rate"],
                        max(0.0, issued * policy["statutory_reserve_to_issued_capital_target"] - pb["statutory_reserve_h1"]))
    parent_cash = (pb["cash_h1"] + pb["old_dividend_receivable_h1"]
                   + pb["new_upstream_declared_and_received_assumption"]
                   + pb["intercompany_principal_recovered_assumption"] - interim
                   - pb["residual_prior_dividend_cash_assumption"] - pb["july_a_buyback_cash_assumption"]
                   - pb["h_buyback_cash_proxy"] - pb["net_parent_expense_assumption"])
    parent_re = pb["retained_earnings_h1"] + parent_profit - interim - reserve_topup
    option_count = q["unexercised_options_h1"] if exercise_all_options else 0.0
    option_proceeds = option_count * q["option_exercise_price_assumption"]
    cash0 += option_proceeds
    parent_cash += option_proceeds
    state = {"cash": cash0, "parent_cash": parent_cash, "parent_re": parent_re,
             "parent_reserve": pb["statutory_reserve_h1"] + reserve_topup,
             "parent_dividend_receivable": 0.0,
             "parent_intercompany_principal": pb["intercompany_principal_h1"] - pb["intercompany_principal_recovered_assumption"],
             "debt": common_debt, "investments": investments,
             "issued_shares": issued + option_count, "net_shares": net_shares + option_count}
    bridge = {"group_liquid_financial_cash_q3": group_cash, "required_group_operating_cash": required_cash,
              "nci_effective_cash_debt_fraction": effective, "nci_total_cash": nci_cash,
              "nci_required_cash": nci_opcash, "nci_excess_cash": nci_excess,
              "group_nonlease_debt": group_debt, "nci_nonlease_debt": nci_debt,
              "common_nonlease_debt": common_debt, "common_excess_cash_q3": cash_q3,
              "october_operating_flow": october, "october_debt_interest_after_tax": debt_interest,
              "october_cash_interest_after_tax": cash_interest,
              "october_past_declared_dividend_paid": q["declared_dividend_liability_paid_october"],
              "common_nonoperating_investment_value": investments,
              "parent_h1_to_october_reserve_topup": reserve_topup,
              "options_exercised": option_count, "option_cash_proceeds": option_proceeds,
              "opening_state": deepcopy(state)}
    check_cash_state(state, "valuation date")
    return state, bridge


def check_cash_state(state, label):
    finite_tree(state)
    if state["cash"] < -1e-7:
        raise EconomicInfeasible("ordinary excess cash exhausted with no new net borrowing at " + label,
                                 {"state": deepcopy(state)})
    if state["parent_cash"] < -1e-7 or state["parent_cash"] > state["cash"] + 1e-7:
        raise EconomicInfeasible("parent cash subset inconsistent or negative at " + label,
                                 {"state": deepcopy(state)})


def parent_waterfall(state, normal_common_profit, parent_profit_ex_upstream,
                     policy, payout_fraction):
    """Mutates state. Internal transfers preserve consolidated ordinary cash."""
    cash_before = state["cash"]
    old_receipt = min(state["parent_dividend_receivable"], max(state["cash"] - state["parent_cash"], 0.0))
    state["parent_dividend_receivable"] -= old_receipt
    state["parent_cash"] += old_receipt
    declared = max(normal_common_profit, 0.0) * policy["annual_upstream_fraction_of_positive_normal_common_profit"]
    receipt = min(declared, max(state["cash"] - state["parent_cash"], 0.0))
    state["parent_cash"] += receipt
    state["parent_dividend_receivable"] += declared - receipt
    parent_profit = declared + parent_profit_ex_upstream
    state["parent_re"] += parent_profit
    reserve = min(max(parent_profit, 0.0) * policy["statutory_profit_allocation_rate"],
                  max(0.0, state["issued_shares"] * policy["statutory_reserve_to_issued_capital_target"] - state["parent_reserve"]))
    state["parent_reserve"] += reserve
    state["parent_re"] -= reserve
    target = payout_fraction * max(normal_common_profit, 0.0)
    permissible_target = min(target, max(state["parent_re"], 0.0))
    principal_collection = min(max(permissible_target + policy["cash_floor"] - state["parent_cash"], 0.0),
                               policy["annual_intercompany_principal_collection_limit"],
                               max(state["parent_intercompany_principal"], 0.0),
                               max(state["cash"] - state["parent_cash"], 0.0))
    state["parent_intercompany_principal"] -= principal_collection
    state["parent_cash"] += principal_collection
    paid = min(target, max(state["parent_re"], 0.0),
               max(state["parent_cash"] - policy["cash_floor"], 0.0), max(state["cash"], 0.0))
    state["cash"] -= paid
    state["parent_cash"] -= paid
    state["parent_re"] -= paid
    if abs((cash_before - paid) - state["cash"]) > 1e-7:
        raise ArithmeticError("internal transfers changed consolidated cash")
    return {"normal_common_profit": normal_common_profit,
            "old_dividend_receivable_collected": old_receipt,
            "upstream_declared": declared, "new_upstream_cash_collected": receipt,
            "parent_profit_ex_upstream": parent_profit_ex_upstream,
            "statutory_reserve_addition": reserve,
            "intercompany_principal_collected": principal_collection,
            "target_distribution": target, "actual_distribution": paid,
            "distribution_shortfall": target - paid,
            "distribution_per_share": paid / state["net_shares"],
            "ending_state": deepcopy(state)}


def pv_monthly(cashflows, annual_rate, start_month=0):
    if annual_rate <= -1:
        raise ValueError("invalid discount rate")
    return sum(flow / (1 + annual_rate) ** ((month - start_month) / 12.0)
               for month, flow in cashflows if month > start_month)


def terminal_cashflow(inputs, budgets):
    cap, nci = inputs["capital"], inputs["nci"]
    left, right = budgets[2036], budgets[2037]
    weighted = lambda key: (2 * left[key] + 10 * right[key]) / 12.0
    group_nopat, nci_nopat = weighted("nopat"), weighted("nci_nopat")
    gap, nci_gap = weighted("replacement_gap"), weighted("nci_replacement_gap")
    g = cap["terminal_growth"]
    group = group_nopat * (1 - g / cap["incremental_roic"]) + gap
    outside = nci_nopat * (1 - g / nci["incremental_roic"]) + nci_gap
    return {"next_12m_group_nopat": group_nopat, "next_12m_nci_nopat": nci_nopat,
            "group_growth_reinvestment": group_nopat * g / cap["incremental_roic"],
            "nci_growth_reinvestment": nci_nopat * g / nci["incremental_roic"],
            "group_replacement_gap": gap, "nci_replacement_gap": nci_gap,
            "group_fcff": group, "nci_fcff": outside, "common_fcff": group - outside}


def operating_value(flows, terminal_flow, rate, growth, at_month=0):
    if rate <= growth:
        raise ValueError("discount rate must exceed growth")
    explicit = pv_monthly(flows, rate, at_month)
    terminal_at_120 = terminal_flow / (rate - growth)
    tail = terminal_at_120 / (1 + rate) ** ((120 - at_month) / 12.0)
    return {"explicit_pv": explicit, "terminal_pv": tail,
            "operating_value": explicit + tail,
            "terminal_contribution": tail / (explicit + tail) if explicit + tail else None}


def project(inputs, label="base", regime="base", exercise_all_options=False,
            domestic_margin_shift=0.0, lease_cash_multiplier=1.0,
            nci_profit_multiplier=1.0):
    budgets = annual_budgets(inputs, regime, domestic_margin_shift, lease_cash_multiplier, nci_profit_multiplier)
    state, bridge = initial_state(inputs, budgets, exercise_all_options)
    opening = deepcopy(state)
    monthly, annual = [], []
    flow_pairs = []
    cap, policy = inputs["capital"], inputs["parent_policy"]
    tax = inputs["fiscal_base"]["tax_rate"]
    income_accum, parent_income_accum = 0.0, 0.0
    try:
        for m in range(1, 121):
            absolute_month = 2026 * 12 + 9 + m
            year, month_zero = divmod(absolute_month, 12)
            month = month_zero + 1
            flow = monthly_operating_flow(inputs, budgets, year, month)
            cash_begin, parent_begin = state["cash"], state["parent_cash"]
            tax_shield = tax if budgets[year]["nopat"] > 0 else 0.0
            debt_interest = state["debt"] * cap["debt_interest_rate"] * (1 - tax_shield) / 12.0
            cash_interest = max(cash_begin, 0.0) * cap["excess_cash_yield_before_tax"] * (1 - tax) / 12.0
            parent_interest = max(parent_begin, 0.0) * cap["excess_cash_yield_before_tax"] * (1 - tax) / 12.0
            parent_net = parent_interest - policy["annual_net_expense"] / 12.0
            ordinary_profit = flow["common_nopat"] - debt_interest + cash_interest
            state["cash"] += flow["common_unlevered_fcff"] - debt_interest + cash_interest
            state["parent_cash"] += parent_net
            state["investments"] = opening["investments"] * (1 + cap["investment_value_growth"]) ** (m / 12.0)
            income_accum += ordinary_profit
            parent_income_accum += parent_net
            check_cash_state(state, f"month {m} before distribution")
            distribution = 0.0
            if m % 12 == 0:
                y = m // 12
                waterfall = parent_waterfall(state, income_accum, parent_income_accum, policy,
                                             policy["payout_fractions_holding_years"][y - 1])
                waterfall.update({"holding_year": y, "month": m, "date": f"{year:04d}-{month:02d}-31"})
                annual.append(waterfall)
                distribution = waterfall["actual_distribution"]
                income_accum, parent_income_accum = 0.0, 0.0
            check_cash_state(state, f"month {m} after distribution")
            monthly.append({"month": m, "year": year, "calendar_month": month,
                            **flow, "cash_begin": cash_begin, "parent_cash_begin": parent_begin,
                            "debt_interest_after_tax": debt_interest,
                            "cash_interest_after_tax": cash_interest,
                            "normal_common_profit": ordinary_profit,
                            "parent_net_income_ex_upstream": parent_net,
                            "common_distribution": distribution,
                            "cash_end": state["cash"], "parent_cash_end": state["parent_cash"]})
            flow_pairs.append((m, flow["common_unlevered_fcff"]))
    except EconomicInfeasible as exc:
        exc.context.update({"label": label, "initial_bridge": bridge,
                            "monthly_completed": monthly, "annual_completed": annual})
        raise
    terminal = terminal_cashflow(inputs, budgets)
    main = operating_value(flow_pairs, terminal["common_fcff"], cap["enterprise_discount_rate"], cap["terminal_growth"])
    common_equity = main["operating_value"] + opening["cash"] + opening["investments"] - opening["debt"]
    at_five = annual[4]["ending_state"]
    year5_values = []
    for rate in cap["enterprise_discount_range"]:
        op5 = operating_value(flow_pairs, terminal["common_fcff"], rate, cap["terminal_growth"], 60)
        equity5 = op5["operating_value"] + at_five["cash"] + at_five["investments"] - at_five["debt"]
        year5_values.append({"rate": rate, **op5, "equity_value": equity5,
                             "per_share": max(0.0, equity5) / at_five["net_shares"]})
    anchor = budgets[2027]
    debt_after_tax = opening["debt"] * cap["debt_interest_rate"] * (1 - tax)
    normal_income = (anchor["nopat"] - anchor["nci_nopat"] - debt_after_tax
                     + anchor["replacement_gap"] - anchor["nci_replacement_gap"])
    aux_earning_value = (normal_income * (1 - cap["terminal_growth"] / cap["normal_equity_roic_aux"])
                         / (cap["equity_discount_rate_aux"] - cap["terminal_growth"]))
    aux_equity = aux_earning_value + opening["cash"] + opening["investments"]
    result = {"label": label, "status": "calculated", "regime": regime,
              "exercise_all_options": exercise_all_options,
              "initial_bridge": bridge, "annual_operating_budgets": list(budgets.values()),
              "monthly_cash_trace": monthly, "annual_distribution_trace": annual,
              "terminal_economic_bridge": terminal, "current_main": {**main,
                  "common_equity": common_equity,
                  "per_share": max(0.0, common_equity) / opening["net_shares"]},
              "auxiliary": {"normal_2027_common_economic_income": normal_income,
                  "capitalized_earnings_value": aux_earning_value,
                  "common_equity": aux_equity, "per_share": max(0.0, aux_equity) / opening["net_shares"],
                  "relative_difference_to_main": (aux_equity / common_equity - 1) if common_equity else None,
                  "difference_over_25_percent": abs(aux_equity / common_equity - 1) > 0.25 if common_equity else True},
              "base_five_year_distributions_per_share": [x["distribution_per_share"] for x in annual[:5]],
              "year5_same_path_equity_endpoints": year5_values,
              "year5_terminal_range_per_share": {"low": min(x["per_share"] for x in year5_values),
                                                 "high": max(x["per_share"] for x in year5_values)},
              "continuity_diagnostics": {
                  "last_holding_year_common_fcff": sum(x[1] for x in flow_pairs[-12:]),
                  "next_stable_year_common_fcff": terminal["common_fcff"],
                  "year5_debt_unchanged": at_five["debt"] == opening["debt"],
                  "retained_cash_not_added_to_current_dcf": True,
                  "full_lease_cash_and_lease_debt_not_double_deducted": True}}
    finite_tree(result)
    return result


def conditional_property_cases(inputs, net_shares):
    prop, fx = inputs["property_conditional"], inputs["nci"]["hkd_to_cny_assumption"]
    output = {}
    for name, case in prop["cases"].items():
        if case["rate"] <= case["growth"]:
            raise ValueError("invalid property capitalization assumptions")
        tax = max(prop["annual_property_noi_hkd"] - prop["annual_depreciation_hkd_assumption"], 0.0) * prop["tax_rate"]
        cash_flow = prop["annual_property_noi_hkd"] - tax - case["annual_maintenance_hkd"]
        ev_hkd = cash_flow * (1 + case["growth"]) / (case["rate"] - case["growth"])
        old_asset = prop["old_reit_book_cny_proxy"] * prop["old_reit_recovery"]
        delta = (ev_hkd - case["external_debt_hkd"] - prop["net_cash_price_hkd"]) * fx - old_asset
        output[name] = {"annual_fcff_hkd": cash_flow, "enterprise_value_hkd": ev_hkd,
                        "external_debt_hkd_assumption": case["external_debt_hkd"],
                        "net_cash_price_hkd": prop["net_cash_price_hkd"],
                        "old_investment_removed_cny": old_asset,
                        "conditional_equity_delta_cny": delta,
                        "conditional_delta_per_share": delta / net_shares,
                        "base_assumes_not_closed": True}
    return output
