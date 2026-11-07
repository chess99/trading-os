"""601827 compact research model r3. Money and shares are in millions.

This file is a STATIC DESIGN until the coordinator authorizes execution.
No top-level valuation, network, package installation, or repository mutation.
"""
from copy import deepcopy


def at(values, index, default=0.0):
    return values[index] if index < len(values) else default


def tax_rate(p, western_share, year, half_last=2025):
    western = (p["western_tax_until_2030"] if year <= 2030
               else p["western_tax_after_2030"])
    full = western_share * western + (1.0 - western_share) * p["other_domestic_tax"]
    return full * (0.5 if year <= half_last else 1.0)


def pv(flows, rate, origin=0):
    """Each pair is (annual end index, cash). No midyear convention."""
    return sum(cash / (1.0 + rate) ** (index - origin)
               for index, cash in flows if index > origin)


def case_parameters(data, case):
    p = deepcopy(data["parameters"])
    p.update(data.get("scenarios", {}).get(case, {}))
    return p


def validate_design(data, p):
    f = data["facts"]
    assert f["shares"] > 0
    assert 0 <= p["financial_common_share"] <= 1
    assert 0 <= p["macau_owner"] <= 1
    assert 0 <= p["refinancing_share"] <= 1
    assert (p["discount_rate"] > p["engineering_terminal_growth"]
            or p["engineering_revenue"] == 0 and p["discount_rate"] >= 0)
    assert p["last_year"] - p["first_year"] <= 40
    assert p["last_year"] > max(c["end_year"] for c in data["cohorts"])
    assert len(p["payout_ratios"]) == 5
    assert abs(sum(p["old_receivable_collection_weights"]) - 1.0) < 1e-9
    assert abs(sum(p["new_subsidy_collection_weights"]) - 1.0) < 1e-9
    assert abs(sum(p["restricted_cash_release_weights"]) - 1.0) < 1e-9
    assert all(0 <= c["owner"] <= 1 for c in data["cohorts"])
    assert 0 <= p["parent_nonincome_taxes"] <= p["parent_operating_cash_cost"]
    assert p["domestic_cash_sga"] >= p["parent_operating_cash_cost"]-p["parent_nonincome_taxes"]
    assert p["domestic_nonincome_taxes"] >= p["parent_nonincome_taxes"]
    assert 0 <= p["parent_opening_reserve_reclassification"] <= f["parent_retained_profit"]
    assert all(p[k] >= 0 for k in ("domestic_cash_sga", "engineering_cash_sga",
        "domestic_nonincome_taxes", "engineering_nonincome_taxes",
        "domestic_new_business_loss", "engineering_new_business_loss"))


def opening_balances(data, p):
    f = data["facts"]
    common = p["financial_common_share"]
    gross_financial_debt = (f["long_debt"] + f["bonds"] + f["lease_debt"]
                            + f["current_noncurrent_liabilities"]
                            - f["current_provision_proxy"])
    assert gross_financial_debt >= 0
    recurring_nwc = (f["net_receivables"] + f["contract_assets"] + f["inventory"]
                     - f["trade_payables"] - f["contract_liabilities"]
                     - f["old_subsidy_receivable_net_proxy"])
    result = {
        "cash": common * (f["cash_equivalents"] + f["trading_financial_assets"]),
        "debt": common * gross_financial_debt,
        "restricted": common * f["restricted_cash"],
        "recurring_nwc": recurring_nwc,
        "parent_cash": f["parent_cash"],
        "parent_debt": f["parent_external_debt"],
        "parent_dividend_receivable": f["parent_dividend_receivable"],
        "parent_retained": f["parent_retained_profit"]-p["parent_opening_reserve_reclassification"],
        "parent_reserve": f["parent_statutory_reserve"]+p["parent_opening_reserve_reclassification"],
        "parent_pool": f["parent_long_payable"],
        "associate_book": f["associate_book"],
        "associate_new_capital": 0.0,
        "common_book": f["common_book_equity"],
    }
    # Parent is identified directly; subsidiary location is the residual of the
    # SAME common-economic cash pool, not a second consolidated cash balance.
    result["subsidiary_cash"] = result["cash"] - result["parent_cash"]
    assert result["subsidiary_cash"] >= -1e-7
    assert result["debt"] >= result["parent_debt"] - 1e-7
    assert abs(result["parent_retained"]+result["parent_reserve"]
               -f["parent_retained_profit"]-f["parent_statutory_reserve"]) < 1e-7
    return result


def nonoperating_recoveries(data, p):
    """Old already-recognized AR and restricted cash: cash only, never new NI."""
    f = data["facts"]
    common = p["financial_common_share"]
    last = p["last_year"] - p["first_year"] + 1
    return [(i + 1, common * (
        f["old_subsidy_receivable_net_proxy"] * p["old_receivable_collectible_fraction"]
        * at(p["old_receivable_collection_weights"], i)
        + f["restricted_cash"] * at(p["restricted_cash_release_weights"], i)))
        for i in range(last)]


def operating_path(data, p):
    """One production chain for full cases and closed-form fixtures.

    Economic ownership is applied to each operating cohort before the financial
    bridge. Engineering is capitalized at 2036; its post-2036 cash is NOT also in
    the explicit rows. BOT/BOO always terminate; only BOO may have a separately
    entered residual. New unlisted-subsidy catch-up is never included.
    """
    f = data["facts"]
    initial = opening_balances(data, p)
    cohorts = data["cohorts"]
    start = p["first_year"]
    total_cap = sum(c["capacity"] for c in cohorts)
    life_weights = sum(c["capacity"] * (c["end_year"] - start + 1) for c in cohorts)
    bot_cap = sum(c["capacity"] for c in cohorts if c["kind"] == "BOT")
    owner_average = sum(c["capacity"] * c["owner"] for c in cohorts) / total_cap
    books = {c["id"]: p["domestic_asset_book"] * c["capacity"]
             * (c["end_year"] - start + 1) / life_weights for c in cohorts}
    bot_provision = max(0.0, f["noncurrent_provisions"]
                        - f["warranty_provision_proxy"] - f["landfill_provision_proxy"])
    dom_initial_nwc = (initial["recurring_nwc"] - p["engineering_opening_nwc"]
                       - p["macau_nwc"])
    prev_dom_nwc = dom_initial_nwc * owner_average
    prev_eng_nwc = p["engineering_opening_nwc"]
    prev_mac_nwc = p["macau_nwc"] * p["macau_owner"]
    prev_eng_revenue = p["engineering_revenue"]
    eng_book = p["engineering_asset_book"]
    new_subsidy_history = []
    new_subsidy_ar = 0.0
    reference_central = sum(
        p["domestic_reference_throughput"] * c["capacity"] / total_cap
        * p["eligible_kwh_per_tonne"] * p["central_tariff_delta_including_vat"]
        / (1.0+p["electricity_vat_rate"]) / 1_000_000.0 * c["central_covered_fraction"]
        for c in cohorts if c["central_last_year"] >= start-1)
    reference_noncentral = p["domestic_reference_revenue"] - reference_central
    rows = []
    engineering_terminal = 0.0
    for year in range(start, p["last_year"] + 1):
        i = year - start
        n = i + 1
        volume = (1.0 + p["throughput_growth"]) ** min(n, p["throughput_growth_years"])
        inflation = (1.0 + p["price_cost_inflation"]) ** n
        cycle = at(p["cyclical_revenue_factors"], i, 1.0)
        totals = dict(revenue=0.0, ebitda=0.0, depreciation=0.0, tax=0.0,
                      nopat=0.0, capex=0.0, handover=0.0, subsidy_loss=0.0,
                      provision_unwind=0.0, end_book=0.0, central_recognition=0.0,
                      bot_handover=0.0, terminal_repair_overlap_credit=0.0,
                      cash_gross_profit=0.0, cash_sga=0.0, nonincome_taxes=0.0,
                      new_business_loss=0.0, recurring_cash_support=0.0)
        dom_full_revenue = 0.0
        dom_full_central = 0.0
        parent_operating_cost = 0.0
        parent_sga = 0.0
        parent_nonincome_taxes = 0.0
        details = []
        for c in cohorts:
            if year > c["end_year"]:
                continue
            weight = c["capacity"] / total_cap
            reference_revenue = p["domestic_reference_revenue"] * weight * volume * inflation * cycle
            price_loss = reference_revenue * (1.0 - p["structural_domestic_price_factor"])
            expiry = c["central_last_year"] + p["subsidy_expiry_shift"]
            loses_subsidy = c["central_last_year"] >= start - 1 and year > expiry
            tariff_loss = (p["central_tariff_delta_including_vat"]
                           + p["provincial_tariff_including_vat"]
                           * p["provincial_tariff_loss_after_central_expiry"])
            loss = (p["domestic_reference_throughput"] * weight * volume * cycle
                    * p["eligible_kwh_per_tonne"] * tariff_loss
                    / (1.0 + p["electricity_vat_rate"]) / 1_000_000.0
                    * c["central_covered_fraction"] if loses_subsidy else 0.0)
            central_recognition = (p["domestic_reference_throughput"] * weight * volume * cycle
                    * p["eligible_kwh_per_tonne"] * p["central_tariff_delta_including_vat"]
                    / (1.0+p["electricity_vat_rate"]) / 1_000_000.0
                    * c["central_covered_fraction"]
                    if c["central_last_year"] >= start-1 and year <= expiry else 0.0)
            revenue = reference_revenue - price_loss - loss
            parent_operating_cost += weight * inflation * p["parent_operating_cash_cost"]
            parent_sga_reference = p["parent_operating_cash_cost"]-p["parent_nonincome_taxes"]
            parent_sga += weight * inflation * parent_sga_reference
            parent_nonincome_taxes += weight * inflation * p["parent_nonincome_taxes"]
            cash_gross_profit = reference_revenue*p["domestic_cash_gross_margin"]-price_loss-loss
            cash_sga = weight*inflation*(p["domestic_cash_sga"]-parent_sga_reference)
            nonincome_taxes = weight*inflation*(p["domestic_nonincome_taxes"]-p["parent_nonincome_taxes"])
            # Future new-business economic losses only; annual cash-equivalent
            # charge, not another impairment of old NET AR or subsidy delay.
            new_business_loss = weight*volume*inflation*cycle*p["domestic_new_business_loss"]
            recurring_cash_support = weight*inflation*p["domestic_recurring_cash_support"]
            ebitda = (cash_gross_profit-cash_sga-nonincome_taxes-new_business_loss
                      +recurring_cash_support)
            remaining = c["end_year"] - year + 1
            depreciation = books[c["id"]] / remaining
            capex = (weight * inflation * (p["domestic_maintenance_capex"]
                      + at(p["domestic_growth_capex"], i)) if remaining > 1 else 0.0)
            reserve_share = bot_provision * c["capacity"] / bot_cap if c["kind"] == "BOT" and bot_cap else 0.0
            unwind = reserve_share * (1.0 + p["provision_unwind_rate"]) ** i * p["provision_unwind_rate"]
            handover = reserve_share * (1.0 + p["provision_unwind_rate"]) ** n if remaining == 1 else 0.0
            recovery = p["boo_end_recovery"] if remaining == 1 and c["kind"] == "BOO" else 0.0
            # IPO: the existing provision funds the final year's normal repair,
            # not an extra full restoration on top of identical operating repair.
            overlap = min(handover, reference_revenue*p["terminal_routine_repair_revenue_share"])
            ebitda += overlap
            ebit = ebitda - depreciation
            rate = tax_rate(p, c["western_share"], year, c["half_tax_last_year"])
            tax = max(ebit, 0.0) * rate
            books[c["id"]] += capex - depreciation
            raw = dict(revenue=revenue, ebitda=ebitda, depreciation=depreciation,
                       tax=tax, nopat=ebit-tax, capex=capex, handover=handover-recovery,
                       subsidy_loss=loss, provision_unwind=unwind, end_book=books[c["id"]],
                       central_recognition=central_recognition, bot_handover=handover,
                       terminal_repair_overlap_credit=overlap,
                       cash_gross_profit=cash_gross_profit, cash_sga=cash_sga,
                       nonincome_taxes=nonincome_taxes, new_business_loss=new_business_loss,
                       recurring_cash_support=recurring_cash_support)
            for key, value in raw.items():
                totals[key] += value * c["owner"]
            dom_full_revenue += revenue
            dom_full_central += central_recognition
            details.append({"id":c["id"], "owner":c["owner"], "tax_rate":rate,
                            "central_last_year_proxy":expiry, **raw})
        noncentral_revenue = dom_full_revenue - dom_full_central
        dom_nwc = (dom_initial_nwc * noncentral_revenue / reference_noncentral
                   + p["domestic_growth_nwc_ratio"]
                   * max(noncentral_revenue - reference_noncentral, 0.0)) * owner_average if reference_noncentral else 0.0
        eng_revenue = (p["engineering_revenue"] * (1.0+p["engineering_growth"]) ** min(n, 5)
                       * cycle)
        eng_active = year <= p["engineering_terminal_year"]
        if eng_active:
            eng_scale = eng_revenue/p["engineering_revenue"] if p["engineering_revenue"] else 0.0
            eng_cash_gross_profit = eng_revenue*p["engineering_cash_gross_margin"]
            eng_sga = p["engineering_cash_sga"]*eng_scale
            eng_nonincome_taxes = p["engineering_nonincome_taxes"]*eng_scale
            eng_new_business_loss = p["engineering_new_business_loss"]*eng_scale
            eng_ebitda = eng_cash_gross_profit-eng_sga-eng_nonincome_taxes-eng_new_business_loss
            eng_depr = p["engineering_depreciation"]
            eng_capex = eng_depr + max(eng_revenue-prev_eng_revenue, 0.0) * p["engineering_growth_capital_ratio"]
            eng_ebit = eng_ebitda - eng_depr
            eng_tax = max(eng_ebit, 0.0) * tax_rate(p, p["engineering_western_profit_share"], year)
            eng_nopat = eng_ebit - eng_tax
            eng_nwc = (p["engineering_opening_nwc"] * eng_revenue / p["engineering_revenue"]
                       + p["engineering_growth_nwc_ratio"] * max(eng_revenue-p["engineering_revenue"],0.0)) if p["engineering_revenue"] else 0.0
            eng_book += eng_capex - eng_depr
            eng_fcff = eng_nopat + eng_depr - eng_capex - (eng_nwc-prev_eng_nwc)
            if year == p["engineering_terminal_year"]:
                engineering_terminal = (eng_fcff * (1.0+p["engineering_terminal_growth"]) / (p["discount_rate"]-p["engineering_terminal_growth"]) if eng_fcff else 0.0)
        else:
            eng_revenue = eng_ebitda = eng_depr = eng_capex = eng_tax = eng_nopat = 0.0
            eng_cash_gross_profit = eng_sga = eng_nonincome_taxes = eng_new_business_loss = 0.0
            eng_nwc = prev_eng_nwc  # continuing franchise NWC already in terminal
        mac_fraction = (1.0 if year < p["macau_end_year"] else p["macau_final_year_fraction"] if year == p["macau_end_year"] else 0.0)
        mac_revenue = p["macau_revenue"] * mac_fraction
        mac_ebitda = mac_revenue * p["macau_cash_margin"]
        mac_depr = p["macau_depreciation"] * mac_fraction
        mac_tax = max(mac_ebitda-mac_depr,0.0) * p["macau_tax"]
        mac_nopat = mac_ebitda - mac_depr - mac_tax
        mac_capex = p["macau_capex"] * mac_fraction
        mac_nwc = p["macau_nwc"] * p["macau_owner"] if mac_fraction else 0.0
        mac_owner = p["macau_owner"]
        # Parent overhead is paid at parent, without a fictitious project-level
        # tax benefit. Its actual positive taxable net income is handled below.
        common_nopat = totals["nopat"] + eng_nopat + mac_owner * mac_nopat - parent_operating_cost
        common_depr = totals["depreciation"] + eng_depr + mac_owner * mac_depr
        common_cash_operating_income = totals["ebitda"]+eng_ebitda+mac_owner*mac_ebitda-parent_operating_cost
        common_income_taxes = totals["tax"]+eng_tax+mac_owner*mac_tax
        assert abs(common_nopat-(common_cash_operating_income-common_depr-common_income_taxes)) < 1e-7
        common_capex = totals["capex"] + eng_capex + mac_owner * mac_capex
        delta_nwc = dom_nwc + eng_nwc + mac_nwc - prev_dom_nwc - prev_eng_nwc - prev_mac_nwc
        new_subsidy_history.append(totals["central_recognition"])
        new_subsidy_collection = sum(
            new_subsidy_history[i-lag]*weight
            for lag,weight in enumerate(p["new_subsidy_collection_weights"]) if i >= lag)
        new_subsidy_delta = totals["central_recognition"] - new_subsidy_collection
        new_subsidy_ar += new_subsidy_delta
        old_other_claims = p["financial_common_share"] * (
            (f["current_provision_proxy"] if i == 0 else 0.0)
            + f["warranty_provision_proxy"] * at([0.4,0.35,0.25], i)
            + (f["landfill_provision_proxy"] if n == 10 else 0.0))
        fcff = common_nopat + common_depr - common_capex - delta_nwc - new_subsidy_delta - totals["handover"] - old_other_claims
        common_invested_capital = totals["end_book"] + eng_book + mac_owner * p["macau_depreciation"] * max(p["macau_end_year"]-year,0) + dom_nwc + eng_nwc + mac_nwc + new_subsidy_ar
        rows.append({"index":n,"year":year,"fcff":fcff,"nopat":common_nopat,
                     "cashflow_date_proxy":str(year)+"-10-31",
                     "common_cash_operating_income_before_income_tax":common_cash_operating_income,
                     "common_operating_income_taxes":common_income_taxes,
                     "depreciation":common_depr,"capex":common_capex,"delta_nwc":delta_nwc,
                     "handover_cash":totals["handover"],"old_other_claims_cash":old_other_claims,
                     "provision_unwind":totals["provision_unwind"],
                     "bot_handover_cash":totals["bot_handover"],
                     "terminal_repair_overlap_credit":totals["terminal_repair_overlap_credit"],
                     "parent_operating_cash_cost":parent_operating_cost,
                     "cash_cost_ledger":{
                         "domestic_common_cash_gross_profit":totals["cash_gross_profit"],
                         "domestic_common_cash_sga_including_parent":totals["cash_sga"]+parent_sga,
                         "domestic_common_nonincome_taxes_including_parent":totals["nonincome_taxes"]+parent_nonincome_taxes,
                         "domestic_common_new_business_loss":totals["new_business_loss"],
                         "domestic_common_recurring_cash_support":totals["recurring_cash_support"],
                         "parent_cash_sga_subset":parent_sga,
                         "parent_nonincome_taxes_subset":parent_nonincome_taxes,
                         "engineering_cash_gross_profit":eng_cash_gross_profit,
                         "engineering_cash_sga":eng_sga,
                         "engineering_nonincome_taxes":eng_nonincome_taxes,
                         "engineering_new_business_loss":eng_new_business_loss,
                         "engineering_ebitda_after_unique_costs":eng_ebitda},
                     "new_subsidy_recognition":totals["central_recognition"],
                     "new_subsidy_collection":new_subsidy_collection,
                     "new_subsidy_ar_change":new_subsidy_delta,
                     "new_subsidy_ar":new_subsidy_ar,
                     "subsidy_revenue_loss_common":totals["subsidy_loss"],
                     "common_operating_revenue":totals["revenue"]+eng_revenue+mac_owner*mac_revenue,
                     "common_invested_capital":common_invested_capital,
                     "macau_common_nopat":mac_owner*mac_nopat,
                     "macau_minority_nopat":(1-mac_owner)*mac_nopat,
                     "domestic":details if n <= 5 else [],
                     "engineering_capitalized_after_this_year":year == p["engineering_terminal_year"]})
        prev_dom_nwc, prev_eng_nwc, prev_mac_nwc = dom_nwc, eng_nwc, mac_nwc
        if eng_active:
            prev_eng_revenue = eng_revenue
    assert abs(new_subsidy_ar) < 1e-6, "Extend finite horizon to collect modeled new subsidy AR"
    return rows, engineering_terminal


def distribution_path(data, p, rows, recoveries, fixed_distributions=None):
    """Two cash locations on one common-economic basis; no legal netting assumed.

    First allocate external flows at the SAME date. Then actually transfer
    dividends/old receivables and parent pool repayment. Buffer warnings are
    distinct from negative cash after required payments. No unlimited financing.
    """
    state = opening_balances(data, p)
    records, violations, buffer_breaches = [], [], []
    for i, op in enumerate(rows[:5]):
        opening = deepcopy(state)
        year = op["year"]
        assert abs(opening["cash"]-opening["parent_cash"]-opening["subsidiary_cash"]) < 1e-7
        sub_tax = (p["financing_tax_rate_before_2031"] if year <= 2030
                   else p["financing_tax_rate_after_2030"])
        parent_interest = opening["parent_debt"]*p["debt_cash_interest_rate"]
        sub_interest = (opening["debt"]-opening["parent_debt"])*p["debt_cash_interest_rate"]
        parent_cash_income = opening["parent_cash"]*p["cash_yield"]
        sub_cash_income = opening["subsidiary_cash"]*p["cash_yield"]
        parent_opex = op["parent_operating_cash_cost"]
        # Dividends/equity-method income are not a pool of taxable operating
        # income against which parent automatically cash-monetizes deductions.
        parent_tax = max(parent_cash_income-parent_interest-parent_opex,0.0)*p["parent_tax_rate"]
        interest_after_tax = parent_interest+sub_interest*(1.0-sub_tax)
        cash_income_after_tax = parent_cash_income+sub_cash_income*(1.0-sub_tax)
        associate_income = (p["associate_normal_profit"]*(1.0+p["associate_profit_growth"])**i
                            + opening["associate_new_capital"]*p["associate_new_investment_return"])
        associate_dividend = max(associate_income,0.0)*p["associate_cash_payout"]
        associate_investment = at(p["associate_new_investments"],i)
        common_ni = (op["nopat"]-interest_after_tax+cash_income_after_tax-parent_tax
                     +associate_income-op["provision_unwind"])
        parent_own_profit = (parent_cash_income-parent_interest-parent_opex-parent_tax
                             +associate_income*p["parent_associate_share"])
        subsidiary_current_profit = common_ni-parent_own_profit
        new_declaration = max(subsidiary_current_profit,0.0)*p["parent_declaration_share"]
        inflow = (op["fcff"]+recoveries[i][1]+associate_dividend-associate_investment
                  -interest_after_tax+cash_income_after_tax-parent_tax)
        parent_mandatory = min(opening["parent_debt"],at(p["scheduled_parent_principal"],i))
        project_scheduled = max(0.0,at(p["scheduled_group_principal"],i)*p["financial_common_share"]-parent_mandatory)
        project_mandatory = min(max(0.0,opening["debt"]-opening["parent_debt"]),project_scheduled)
        mandatory = parent_mandatory+project_mandatory
        refinancing = mandatory*p["refinancing_share"]
        parent_refinancing = parent_mandatory*p["refinancing_share"]
        state["debt"] += refinancing-mandatory
        state["parent_debt"] += parent_refinancing-parent_mandatory
        group_external_flow = inflow+refinancing-mandatory
        parent_external_flow = (-parent_opex+parent_cash_income-parent_interest-parent_tax
                                +(associate_dividend-associate_investment)*p["parent_associate_share"]
                                +parent_refinancing-parent_mandatory)
        subsidiary_external_flow = group_external_flow-parent_external_flow
        parent_before_transfer = opening["parent_cash"]+parent_external_flow
        sub_before_transfer = opening["subsidiary_cash"]+subsidiary_external_flow
        group_before_transfer = opening["cash"]+group_external_flow
        assert abs(group_before_transfer-parent_before_transfer-sub_before_transfer) < 1e-7
        proposed_collection = (new_declaration*p["parent_same_year_collection_share"]
                               +min(opening["parent_dividend_receivable"],at(p["parent_old_receivable_collection"],i)))
        # Existing subsidiary money only. Parent's later repayment is not
        # instantly recycled into an assumed legally netted dividend receipt.
        collection = min(proposed_collection,opening["parent_dividend_receivable"]+new_declaration,
                         max(0.0,sub_before_transfer))
        pool_payment = min(opening["parent_pool"],at(p["parent_net_pool_repayment"],i))
        state["parent_pool"] -= pool_payment
        state["parent_dividend_receivable"] += new_declaration-collection
        parent_before_dividend = parent_before_transfer+collection-pool_payment
        sub_before_dividend = sub_before_transfer-collection+pool_payment
        parent_profit = parent_own_profit+new_declaration
        reserve_addition = max(parent_profit,0.0)*p["parent_statutory_accrual_rate"]
        state["parent_reserve"] += reserve_addition
        state["parent_retained"] += parent_profit-reserve_addition
        target = (fixed_distributions[i] if fixed_distributions is not None
                  else max(common_ni,0.0)*p["payout_ratios"][i])
        capacity = max(0.0,min(parent_before_dividend-p["parent_cash_floor"],
                              group_before_transfer-p["group_cash_floor"],state["parent_retained"]))
        dividend = min(target,capacity)
        state["parent_retained"] -= dividend
        state["parent_cash"] = parent_before_dividend-dividend
        state["subsidiary_cash"] = sub_before_dividend
        state["cash"] = state["parent_cash"]+state["subsidiary_cash"]
        project_debt = max(0.0,state["debt"]-state["parent_debt"])
        voluntary = (min(project_debt,max(0.0,state["subsidiary_cash"]-p["subsidiary_cash_floor"]),
                         max(0.0,state["cash"]-p["group_retained_cash_target"]))
                     if state["parent_cash"] >= 0 and state["subsidiary_cash"] >= 0 else 0.0)
        state["subsidiary_cash"] -= voluntary
        state["cash"] -= voluntary
        state["debt"] -= voluntary
        state["restricted"] -= data["facts"]["restricted_cash"]*p["financial_common_share"]*at(p["restricted_cash_release_weights"],i)
        state["associate_book"] += associate_income-associate_dividend+associate_investment
        state["associate_new_capital"] += associate_investment
        state["common_book"] += common_ni-dividend
        cash_residual = state["cash"]-(opening["cash"]+group_external_flow-dividend-voluntary)
        location_residual = state["cash"]-state["parent_cash"]-state["subsidiary_cash"]
        assert abs(cash_residual) < 1e-7
        assert abs(location_residual) < 1e-7
        for location,balance,floor in (("group",state["cash"],p["group_cash_floor"]),
                                        ("parent",state["parent_cash"],p["parent_cash_floor"]),
                                        ("subsidiary",state["subsidiary_cash"],p["subsidiary_cash_floor"])):
            if balance < -1e-7:
                violations.append({"year":year,"kind":location+" actual mandatory payment shortfall",
                                   "amount":-balance})
            elif balance < floor-1e-7:
                buffer_breaches.append({"year":year,"location":location,"kind":"research buffer breach only",
                                       "amount":floor-balance})
        if dividend < target-1e-7:
            violations.append({"year":year,"kind":"planned distribution clipped","amount":target-dividend})
        records.append({"year":year,"common_net_income":common_ni,"dividend":dividend,
                        "target_dividend":target,"parent_new_declaration":new_declaration,
                        "subsidiary_current_profit":subsidiary_current_profit,
                        "parent_own_profit_excluding_declaration":parent_own_profit,
                        "parent_collection":collection,"parent_profit":parent_profit,
                        "parent_cash_income":parent_cash_income,"parent_cash_tax":parent_tax,
                        "parent_reserve_addition":reserve_addition,"parent_pool_payment":pool_payment,
                        "interest_after_tax":interest_after_tax,"scheduled_principal":mandatory,
                        "refinancing":refinancing,"voluntary_principal":voluntary,
                        "opening_parent_cash":opening["parent_cash"],"opening_subsidiary_cash":opening["subsidiary_cash"],
                        "group_external_cash_flow":group_external_flow,"parent_external_cash_flow":parent_external_flow,
                        "subsidiary_external_cash_flow":subsidiary_external_flow,
                        "parent_cash_before_internal_transfers":parent_before_transfer,
                        "subsidiary_cash_before_internal_transfers":sub_before_transfer,
                        "cash_residual":cash_residual,"location_residual":location_residual, **deepcopy(state)})
        if any(v["year"]==year and v["kind"]!="planned distribution clipped" for v in violations):
            break
    return records,violations,buffer_breaches


def auxiliary_capital_recovery(data, p):
    """Independent balance-sheet / finite capital-recovery entrance.

    No main-method revenue, EBITDA, annual NOPAT, or terminal multiple is read.
    Starting book already deducts recorded provisions. Principal returns once;
    assumed ROIC earns on declining unreturned capital, not on perpetual capital.
    """
    s = opening_balances(data,p)
    old_ar_net = data["facts"]["old_subsidy_receivable_net_proxy"]*p["financial_common_share"]
    book = data["facts"]["common_book_equity"]
    # Receipts from past sales do not manufacture future NOPAT. Remove the
    # entire allocated NET carrying asset, then value its recovery only once.
    capital = book+s["debt"]-s["cash"]-s["restricted"]-s["associate_book"]-old_ar_net
    life = p["auxiliary_remaining_years"]
    annual_recovery = capital/life
    flows = [(i+1,annual_recovery+(capital-i*annual_recovery)
              *(p["auxiliary_roic"] if p["first_year"]+i <= 2030 else p["auxiliary_roic_after_2030"]))
             for i in range(life)]
    operating_value = pv(flows,p["auxiliary_capital_cost"])
    recovery_value = pv(nonoperating_recoveries(data,p),p["auxiliary_capital_cost"])
    equity = operating_value+recovery_value+s["cash"]-s["debt"]+s["associate_book"]*p["associate_value_to_book"]
    return {"operating_capital":capital,"operating_value":operating_value,
            "old_receivable_net_removed_from_productive_capital":old_ar_net,
            "nonproductive_recovery_pv":recovery_value,
            "common_equity":equity,"per_share":equity/data["facts"]["shares"],
            "annual_capital_recovery":annual_recovery,"remaining_years":life}


def run_case(data, case="base", fixed_distributions=None):
    p = case_parameters(data,case)
    validate_design(data,p)
    op, engineering_terminal = operating_path(data,p)
    recoveries = nonoperating_recoveries(data,p)
    holder, violations, buffer_breaches = distribution_path(data,p,op,recoveries,fixed_distributions)
    s = opening_balances(data,p)
    operating_flows = [(r["index"],r["fcff"]) for r in op]
    tail_index = p["engineering_terminal_year"]-p["first_year"]+1
    tail = [(tail_index,engineering_terminal)]
    operating_value = pv(operating_flows+tail,p["discount_rate"])
    recovery_value = pv(recoveries,p["discount_rate"])
    equity = operating_value+recovery_value+s["cash"]-s["debt"]+s["associate_book"]*p["associate_value_to_book"]
    terminal_operating = pv(operating_flows+tail,p["discount_rate"],5)
    terminal_recoveries = pv(recoveries,p["discount_rate"],5)
    last = holder[-1]
    hard_funding_failure = any(v["kind"] != "planned distribution clipped" for v in violations)
    terminal_equity = ((terminal_operating+terminal_recoveries+last["cash"]-last["debt"]
                       +last["associate_book"]*p["associate_value_to_book"])
                      if len(holder)==5 and not hard_funding_failure else None)
    shares = data["facts"]["shares"]
    delta_capital = op[4]["common_invested_capital"]-op[0]["common_invested_capital"]
    delta_nopat = op[4]["nopat"]-op[0]["nopat"]
    roic = [{"year":r["year"],"end_capital_proxy":r["common_invested_capital"],
             "nopat":r["nopat"],"end_capital_roic_proxy":r["nopat"]/r["common_invested_capital"] if r["common_invested_capital"]>0 else None}
            for r in op[:5]]
    auxiliary = auxiliary_capital_recovery(data,p)
    bot_reserve = max(0.0,data["facts"]["noncurrent_provisions"]-data["facts"]["warranty_provision_proxy"]-data["facts"]["landfill_provision_proxy"])
    bot_capacity = sum(c["capacity"] for c in data["cohorts"] if c["kind"]=="BOT")
    bot_reserve_common = (bot_reserve*sum(c["capacity"]*c["owner"] for c in data["cohorts"] if c["kind"]=="BOT")/bot_capacity if bot_capacity else 0.0)
    handover_source_pv = pv([(r["index"],r["bot_handover_cash"]) for r in op],p["provision_unwind_rate"])
    assert abs(handover_source_pv-bot_reserve_common) < 1e-6
    return {"case":case,"parameters":p,"current_common_equity":equity,
            "time_basis":deepcopy(data["time_basis"]),
            "current_value_per_share":equity/shares,"operating_value":operating_value,
            "engineering_tail_pv":pv(tail,p["discount_rate"]),
            "engineering_tail_share_of_operating_value":pv(tail,p["discount_rate"])/operating_value if operating_value else None,
            "after_year5_operating_pv_share":terminal_operating/(1+p["discount_rate"])**5/operating_value if operating_value else None,
            "cash_recovery_pv":recovery_value,"opening_balances":s,
            "year5_common_equity":terminal_equity,"year5_value_per_share":terminal_equity/shares if terminal_equity is not None else None,
            "hard_funding_failure":hard_funding_failure,
            "current_asset_value_conditional_on_revised_funding":hard_funding_failure,
            "year5_operating_value":terminal_operating,"year5_remaining_recovery_value":terminal_recoveries,
            "future_cash_distributions_per_share":[r["dividend"]/shares for r in holder],
            "funding_and_distribution_violations":violations,"holder_path":holder,
            "liquidity_buffer_breaches":buffer_breaches,
            "provision_bridge":{"opening_bot_provision_common":bot_reserve_common,
                                "source_unwind_rate":p["provision_unwind_rate"],
                                "future_handover_cash_pv_at_source_rate":handover_source_pv},
            "five_year_operations":op[:5],"finite_dcf_schedule":op,
            "roic_diagnostics":roic,"matched_year1_to_year5_delta_capital":delta_capital,
            "matched_year1_to_year5_delta_nopat":delta_nopat,
            "incremental_roic":delta_nopat/delta_capital if delta_capital>0 else None,
            "incremental_roic_note":"Capital runoff denominator <=0 is not evidence of infinite incremental returns.",
            "auxiliary":auxiliary,
            "method_gap_relative_to_main":(auxiliary["common_equity"]-equity)/abs(equity) if equity else None}


def run_suite(data):
    assert set(data["scenarios"]) == {"base", "core_low", "core_high"}, "r3 scope is three paths only"
    base = run_case(data,"base")
    fixed = ([x["dividend"] for x in base["holder_path"]]
             if len(base["holder_path"])==5 and not base["hard_funding_failure"] else None)
    cases = {"base":base}
    if fixed is None:
        # No invented replacement D schedule and no endpoint-specific budgets.
        # Retain the failed base evidence; a future funding redesign needs approval.
        return {"status":"computed_not_research_accepted",
                "information_cutoff":data["information_cutoff"],
                "time_basis":deepcopy(data["time_basis"]),"cases":cases,
                "core_value_range_per_share":None,"endpoint_order_inverted":None,
                "base_holder_interface_feasible":False,"return_model":None,
                "endpoints_not_run_reason":"No complete feasible new-base D schedule"}
    for name in ("core_low","core_high"):
        cases[name] = run_case(data,name,fixed)
    low, high = cases["core_low"],cases["core_high"]
    # A rejected extreme does not null the core valuation. The holder interface
    # needs the SAME five Ds and feasible mandatory financing at both TV ends.
    holder_valid = not any(cases[n]["funding_and_distribution_violations"] for n in ("base","core_low","core_high"))
    terminal_values = (sorted([low["year5_value_per_share"],high["year5_value_per_share"]])
                       if low["year5_value_per_share"] is not None and high["year5_value_per_share"] is not None else None)
    current_values = sorted([low["current_value_per_share"],high["current_value_per_share"]])
    return {"status":"computed_not_research_accepted","information_cutoff":data["information_cutoff"],
            "time_basis":deepcopy(data["time_basis"]),
            "cases":cases,"core_value_range_per_share":current_values,
            "endpoint_order_inverted":low["current_value_per_share"]>high["current_value_per_share"] or (terminal_values is not None and low["year5_value_per_share"]>high["year5_value_per_share"]),
            "base_holder_interface_feasible":holder_valid,
            "return_model":({"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY",
                             "model_as_of":data["information_cutoff"],
                             "base_case_distributions_per_share":base["future_cash_distributions_per_share"],
                             "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":terminal_values[0],"high":terminal_values[1]}}}
                            if holder_valid else None)}
