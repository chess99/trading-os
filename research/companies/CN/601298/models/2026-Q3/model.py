'Qingdao ordinary offline model. CNY billion; shares billion; capacities million TEU/tonnes. Standard library only, no network/subprocess/implicit financing. No coordinator ticket required.'
import json
import sys
import hashlib


def require_finite(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not (-1e300 < x < 1e300):
        raise ValueError("non-finite numeric field: " + name)


def pv(cash, rate):
    return sum(x / ((1 + rate) ** (i + 1)) for i, x in enumerate(cash))


def release_value(principal, yield_rate, release_rate, discount_rate):
    """Remaining principal falls by release_rate each year; interest is paid annually."""
    if principal < 0:
        return principal
    if discount_rate + release_rate <= 0:
        raise ValueError("invalid financial-principal recovery denominator")
    return principal * (release_rate + yield_rate) / (discount_rate + release_rate)


def finite_runoff_pv(balance, annual_runoff, discount_rate):
    if balance <= 0:
        return 0.0
    if annual_runoff <= 0:
        raise ValueError("positive prepaid balance with no runoff")
    total = 0.0
    for t in range(1, 61):
        amount = min(balance, annual_runoff)
        total += amount / ((1 + discount_rate) ** t)
        balance -= amount
        if balance < 1e-10:
            return total
    raise ValueError("lease tail exceeds bounded 60-year diagnostic")


def validate_config(c):
    n = c["years"]
    if isinstance(n, bool) or not isinstance(n, int) or not 5 <= n <= 12:
        raise ValueError("years must be integer 5..12")
    for k, v in c.items():
        if k in ("name", "description", "provenance", "intervals"):
            continue
        if isinstance(v, list):
            if len(v) != n:
                raise ValueError("array length mismatch: " + k)
            for i, x in enumerate(v):
                require_finite(x, "%s[%s]" % (k, i))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            require_finite(v, k)
        else:
            raise ValueError("unexpected configuration type: " + k)
    if len(c["intervals"]) != n or any(not isinstance(x, str) for x in c["intervals"]):
        raise ValueError("intervals shape")
    if abs(sum(c["build_weights"]) - 1) > 1e-10 and c["future_project_cost"] != 0:
        raise ValueError("construction weights do not sum to one")
    if abs(sum(c["recognition_weights"]) - 1) > 1e-10 and c["future_project_cost"] != 0:
        raise ValueError("capital recognition weights do not sum to one")
    if c["equity_cost"] <= c["terminal_g"] or c["terminal_roic"] <= 0:
        raise ValueError("terminal rates")
    if c["subs_declared_ratio"] > c["subs_current_distributable_ratio"]:
        raise ValueError("subsidiary declared policy exceeds assumed current available profit")
    if not 0 <= c["nci_initial_financial_share"] <= 1:
        raise ValueError("initial NCI financial location share outside 0..1")


def simulate(c):
    validate_config(c)
    n, tax, ke = c["years"], c["tax"], c["equity_cost"]
    parent_cash = c["parent_cash0"]
    parent_term = c["parent_term0"]
    sub_cash = c["sub_cash0"]
    jv_cash = c["jv_cash0"]
    debt = c["debt0"]
    parent_debt = c["parent_debt0"]
    book = c["common_book0"]
    nci_book = c["nci_book0"]
    # Initial location estimate only: ordinary-owner withdrawals never reset it.
    nci_financial_claim = max(c["sub_cash0"] - c["sub_required_cash"], 0) * c["nci_initial_financial_share"]
    nci_initial_financial_income = nci_financial_claim * c["financial_yield_aftertax"]
    nci_legacy_asset_share = ((c["nci_profit0"] - nci_initial_financial_income) / c["old_nopat0"]) if c["old_nopat0"] > 0 else 0.0
    if not 0 <= nci_legacy_asset_share <= 1:
        raise ValueError("legacy NCI operating allocation proxy outside 0..1")
    parent_retained = c["parent_retained0"]
    sub_distributable = c["sub_distributable0"]
    sub_receivable = c["sub_dividend_receivable0"]
    jv_payment_backlog = c["jv_dividend_receivable0"]
    jv_new_invested = 0.0
    benefit = c["benefit_liability0"]
    benefit_settlement_due = c["benefit_related_payable0"]
    lease_prepaid = c["prepaid_lease_balance0"]
    lease_prepaid_tax = c["prepaid_lease_tax0"]
    project_gross = c["project_booked0"]
    project_ap = c["project_ap0"]
    old_project_ap_remaining = c["project_ap0"]
    project_prepay = c["project_prepay0"]
    legacy_ap = c["legacy_project_ap0"]
    project_net = c["project_booked0"]
    growth_factor = 1.0
    jv_growth_factor = 1.0
    prior_project_cash_contribution = 0.0
    rows = []
    group_cash0 = parent_cash + parent_term + sub_cash
    initial_project_state = project_gross
    cap_cash_total = 0.0
    accumulated_project_da = 0.0
    accumulated_project_maintenance = 0.0

    for t in range(n):
        opening_group = parent_cash + parent_term + sub_cash
        opening_parent = parent_cash + parent_term
        opening_sub = sub_cash
        opening_jv = jv_cash
        opening_book = book
        opening_benefit = benefit
        opening_nci_financial_claim = nci_financial_claim
        growth_factor *= 1 + c["old_growth"][t]
        jv_growth_factor *= 1 + c["jv_growth"][t]

        new_asset = c["future_project_cost"] * c["recognition_weights"][t]
        pay_ap = min(old_project_ap_remaining, c["project_ap_settlement"][t])
        use_prepay = min(project_prepay, c["project_prepay_use"][t], new_asset)
        pay_legacy = min(legacy_ap, c["legacy_project_settlement"][t])
        new_capital_cash = c["future_project_cost"] * c["build_weights"][t] - use_prepay
        project_ap += new_asset - use_prepay - new_capital_cash - pay_ap
        old_project_ap_remaining -= pay_ap
        if project_ap < -1e-8 or new_capital_cash < -1e-8:
            raise ValueError("capital payment precedes recognized/prepaid design; explicit new prepayment required")
        project_prepay -= use_prepay
        legacy_ap -= pay_legacy
        project_gross += new_asset
        construction_cash = new_capital_cash + pay_ap + pay_legacy
        cap_cash_total += construction_cash

        commissioned = c["commissioned"][t]
        util_c = c["container_util"][t]
        util_b = c["bulk_util"][t]
        if min(commissioned, util_c, util_b) < 0 or max(commissioned, util_c, util_b) > 1:
            raise ValueError("project fractions")
        if util_c > commissioned + 1e-10 or util_b > commissioned + 1e-10:
            raise ValueError("utilization exceeds commissioned capacity")
        volume_c = c["container_capacity_m"] * util_c
        volume_b = c["bulk_capacity_m"] * util_b
        contribution_c = volume_c * c["container_contribution_cny"] / 1000
        contribution_b = volume_b * c["bulk_contribution_cny"] / 1000
        project_cash_contribution = contribution_c + contribution_b
        original_project_cost = c["container_asset_cost"] + c["bulk_asset_cost"] + c["network_asset_cost"]
        cost_scale = ((c["project_booked0"] + c["future_project_cost"]) / original_project_cost) if original_project_cost else 1.0
        project_da = commissioned * cost_scale * (
            c["container_asset_cost"] * c["container_da_rate"]
            + c["bulk_asset_cost"] * c["bulk_da_rate"]
        )
        network_da = c["network_asset_cost"] * cost_scale * c["network_da_rate"] * c["network_commissioned"][t]
        inservice_gross = cost_scale * (
            commissioned * (c["container_asset_cost"] + c["bulk_asset_cost"])
            + c["network_commissioned"][t] * c["network_asset_cost"]
        )
        if inservice_gross > project_gross + 1e-8:
            raise ValueError("commissioned assets exceed recognized construction capital")
        fixed_cost = commissioned * (c["container_fixed_cash"] + c["bulk_fixed_cash"])
        project_ebit = project_cash_contribution - fixed_cost - project_da
        displaced_nopat = (
            volume_c * c["container_diversion_fraction"] * c["old_container_nopat_per_unit"]
            + volume_b * c["bulk_diversion_fraction"] * c["old_bulk_nopat_per_unit"]
        ) / 1000
        major_project_nopat = project_ebit * (1 - tax) - displaced_nopat
        project_nopat = major_project_nopat - network_da * (1 - tax)
        # Two main berths are assigned to the parent; only the network capital is
        # partly assigned to controlled subsidiaries. Match its depreciation to
        # the same location rather than adding back an expense never recorded.
        network_parent_share = 0.0
        if c["network_asset_cost"] > 0:
            network_parent_share = (
                c["parent_build_share"] * original_project_cost
                - c["container_asset_cost"] - c["bulk_asset_cost"]
            ) / c["network_asset_cost"]
            if not -1e-8 <= network_parent_share <= 1 + 1e-8:
                raise ValueError("network legal-entity capital allocation outside 0..1")
        parent_project_nopat = major_project_nopat - network_da * network_parent_share * (1 - tax)
        project_net += new_asset - project_da - network_da
        accumulated_project_da += project_da + network_da
        if project_net < -1e-9:
            raise ValueError("project capital depreciated below zero")

        pension_service = c["benefit_service0"] * ((1 + c["benefit_service_growth"]) ** t)
        pension_interest = benefit * c["benefit_discount_rate"]
        pension_accrual = pension_service + pension_interest
        pension_cash = c["benefit_cash"][t]
        benefit += pension_accrual - pension_cash
        if benefit < -1e-9:
            raise ValueError("negative remaining benefit liability")
        pension_conversion = (pension_accrual - pension_cash) * (1 - tax)
        existing_nopat = (
            c["old_nopat0"] * growth_factor * c["cycle_factor"][t]
            - (pension_accrual - c["benefit_base_expense"] * growth_factor) * (1 - tax)
        )
        nopat = existing_nopat + project_nopat

        lease_runoff = min(lease_prepaid, c["prepaid_lease_annual_runoff"])
        lease_prepaid -= lease_runoff
        prepaid_tax_runoff = min(lease_prepaid_tax, c["prepaid_lease_tax_runoff"])
        lease_prepaid_tax -= prepaid_tax_runoff
        jv_lease_addback = lease_runoff * c["prepaid_lease_direct_weight"] * c["qqct_share"]
        jv_lease_addback += lease_runoff * (1 - c["prepaid_lease_direct_weight"]) * c["other_lease_share"]
        lease_operating_adjustment = (
            c["rou_da0"] + c["lease_interest0"] - c["long_lease_cash0"]
        ) * growth_factor * (1 - tax)

        old_da = c["owned_da0"] * growth_factor
        own_da = old_da + project_da + network_da
        old_maintenance = c["maintenance0"] * ((1 + c["maintenance_inflation"]) ** t)
        new_maintenance = (project_da + network_da) * c["new_maintenance_fraction"][t]
        project_net += new_maintenance
        accumulated_project_maintenance += new_maintenance
        maintenance = old_maintenance + new_maintenance
        old_nwc = c["old_nwc_capital"] * c["old_growth"][t]
        nwc = old_nwc
        nwc += c["new_nwc_fraction"] * (project_cash_contribution - prior_project_cash_contribution)
        prior_project_cash_contribution = project_cash_contribution

        group_financial_income = opening_group * c["financial_yield_aftertax"]
        parent_financial_income = opening_parent * c["financial_yield_aftertax"]
        half_draw = 0.5 * c["parent_new_borrowing"][t]
        half_repayment = 0.5 * min(parent_debt, c["parent_debt_repayment"][t])
        bank_interest = (debt + half_draw - half_repayment) * c["debt_interest_rate"] * (1 - tax)
        parent_bank_interest = (parent_debt + half_draw - half_repayment) * c["debt_interest_rate"] * (1 - tax)
        jv_financial_income = opening_jv * c["financial_yield_aftertax"]
        jv_operating_profit = c["jv_operating_profit0"] * jv_growth_factor * c["jv_cycle_factor"][t]
        jv_operating_profit += jv_new_invested * c["new_jv_return"]
        jv_profit = jv_operating_profit + jv_financial_income
        jv_reinvestment = max(c["jv_growth"][t], 0) * jv_operating_profit / c["jv_incremental_return"]
        jv_fcfe = jv_profit + jv_lease_addback - jv_reinvestment
        jv_intended = max(jv_profit, 0) * c["jv_payout"][t]
        jv_intended += max(opening_jv - c["jv_required_cash"], 0) * c["jv_release"][t]
        jv_declared = min(jv_intended, max(opening_jv + jv_fcfe - c["jv_required_cash"], 0))
        jv_due = jv_payment_backlog + jv_declared
        jv_paid = jv_due * c["jv_payment_factor"][t]
        jv_paid = min(jv_paid, max(opening_jv + jv_fcfe - c["jv_required_cash"], 0))
        jv_payment_backlog = jv_due - jv_paid
        jv_cash += jv_fcfe - jv_paid

        nci_financial_current = opening_nci_financial_claim * c["financial_yield_aftertax"]
        nci_profit = (c["nci_profit0"] - nci_initial_financial_income) * growth_factor * c["cycle_factor"][t] + nci_financial_current
        nci_dividend = max(nci_profit, 0) * c["nci_payout"]
        # Attribution of already modeled old-asset net investment, NOT another
        # cash deduction or a uniform legal ownership ratio. New berth capital
        # is not silently charged to NCI merely because it lies in the group.
        nci_operating_reinvestment = (old_maintenance - old_da + old_nwc) * nci_legacy_asset_share
        nci_financial_claim += nci_profit - nci_dividend - nci_operating_reinvestment
        if nci_financial_claim < -1e-8:
            raise ValueError("NCI investment allocation needs unsupported additional funding")
        common_profit = nopat + jv_profit + group_financial_income - bank_interest - nci_profit
        group_operating_cash = (
            nopat + own_da + lease_operating_adjustment + pension_conversion
            - lease_runoff + prepaid_tax_runoff - nwc
            + group_financial_income - bank_interest
        )

        parent_operating_cash = c["parent_own_cash0"] * growth_factor * c["cycle_factor"][t]
        parent_operating_cash += parent_project_nopat + project_da + network_da * network_parent_share - c["new_nwc_fraction"] * (
            project_cash_contribution - (rows[-1]["project_cash_contribution"] if rows else 0)
        )
        parent_operating_cash += parent_financial_income - parent_bank_interest
        parent_own_profit = c["parent_own_profit0"] * growth_factor * c["cycle_factor"][t]
        parent_own_profit += parent_project_nopat + parent_financial_income - parent_bank_interest
        sub_common_profit = common_profit - parent_own_profit - jv_profit
        sub_distributable += max(sub_common_profit, 0) * c["subs_current_distributable_ratio"]
        sub_distributable += min(sub_common_profit, 0)

        parent_build = construction_cash * c["parent_build_share"]
        parent_maint = old_maintenance * c["parent_old_maintenance_share"] + new_maintenance * c["parent_build_share"]
        sub_build = construction_cash - parent_build
        sub_maint = maintenance - parent_maint
        benefit_related_paid = min(benefit_settlement_due, c["benefit_related_settlement"][t])
        benefit_settlement_due -= benefit_related_paid
        parent_benefit_related = benefit_related_paid * c["parent_benefit_share"]
        sub_benefit_related = benefit_related_paid - parent_benefit_related
        new_jv_investment = c["new_jv_investment"][t]
        jv_new_invested += new_jv_investment

        sub_prediv_cash = sub_cash + (group_operating_cash - parent_operating_cash)
        sub_prediv_cash -= sub_build + sub_maint + nci_dividend + sub_benefit_related + new_jv_investment
        sub_target = max(sub_common_profit, 0) * c["subs_declared_ratio"]
        sub_target += max(opening_sub - c["sub_required_cash"] - opening_nci_financial_claim, 0) * c["sub_release"][t]
        ordinary_sub_cash_capacity = max(sub_prediv_cash - c["sub_required_cash"] - nci_financial_claim, 0)
        sub_declared = min(sub_target, max(sub_distributable, 0), ordinary_sub_cash_capacity)
        sub_distributable -= sub_declared
        sub_due = sub_receivable + sub_declared
        sub_paid = min(sub_due * c["sub_payment_factor"][t], ordinary_sub_cash_capacity)
        sub_receivable = sub_due - sub_paid
        sub_cash = sub_prediv_cash - sub_paid

        redeemed = min(parent_term, c["parent_term_redemption"][t])
        parent_term -= redeemed
        financing = c["parent_new_borrowing"][t]
        repayment = min(parent_debt, c["parent_debt_repayment"][t])
        parent_debt += financing - repayment
        debt += financing - repayment
        parent_prediv_cash = parent_cash + redeemed + parent_operating_cash + sub_paid + jv_paid
        parent_prediv_cash += financing - repayment - parent_build - parent_maint - parent_benefit_related
        parent_profit = parent_own_profit + sub_declared + jv_profit
        parent_retained += parent_profit
        planned_d = max(common_profit, 0) * c["common_payout"][t]
        planned_d += max(parent_prediv_cash - c["parent_required_cash"], 0) * c["parent_release"][t]
        future_buffer = 0.0
        for k in range(t + 1, min(n, t + 3)):
            future_build = c["future_project_cost"] * c["build_weights"][k]
            future_build += c["project_ap_settlement"][k] + c["legacy_project_settlement"][k] - c["project_prepay_use"][k]
            future_parent_capital = future_build * c["parent_build_share"]
            future_parent_capital += c["maintenance0"] * ((1 + c["maintenance_inflation"]) ** k) * c["parent_old_maintenance_share"]
            future_buffer += max(future_parent_capital - c["parent_inflow_budget"], 0)
        parent_capacity = max(parent_prediv_cash - c["parent_required_cash"] - future_buffer, 0)
        group_capacity = max(parent_prediv_cash + parent_term + sub_cash - c["group_required_cash"], 0)
        d = min(planned_d, parent_capacity, group_capacity, max(parent_retained, 0))
        parent_cash = parent_prediv_cash - d
        parent_retained -= d
        book += common_profit - d
        nci_book += nci_profit - nci_dividend

        closing_group = parent_cash + parent_term + sub_cash
        expected_group = opening_group + group_operating_cash + jv_paid
        expected_group -= construction_cash + maintenance + nci_dividend + d + benefit_related_paid + new_jv_investment
        expected_group += financing - repayment
        closure = closing_group - expected_group
        if abs(closure) > 1e-8:
            raise AssertionError("group cash conservation failure")
        if abs(jv_cash - (opening_jv + jv_fcfe - jv_paid)) > 1e-8:
            raise AssertionError("JV cash conservation failure")
        if abs(benefit - (opening_benefit + pension_accrual - pension_cash)) > 1e-8:
            raise AssertionError("benefit liability failure")
        if d < -1e-10:
            raise AssertionError("negative common cash distribution")
        rows.append({
            "year": t + 1, "interval": c["intervals"][t], "existing_nopat": existing_nopat,
            "project_nopat": project_nopat, "parent_project_nopat": parent_project_nopat,
            "network_parent_share": network_parent_share, "project_cash_contribution": project_cash_contribution,
            "container_volume_m": volume_c, "bulk_volume_m": volume_b, "displaced_nopat": displaced_nopat,
            "project_da": project_da, "network_da": network_da, "owned_da": own_da,
            "new_capital_added": new_asset, "construction_cash": construction_cash,
            "project_gross": project_gross, "project_net": project_net,
            "project_inservice_gross": inservice_gross, "project_cip": project_gross - inservice_gross,
            "project_maintenance_capital": new_maintenance,
            "project_accumulated_da": accumulated_project_da,
            "project_accumulated_replacement_capital": accumulated_project_maintenance,
            "project_ap": project_ap, "project_prepay": project_prepay, "legacy_ap": legacy_ap,
            "maintenance": maintenance, "nwc_cash": nwc, "lease_runoff": lease_runoff,
            "lease_prepaid_remaining": lease_prepaid, "jv_lease_addback": jv_lease_addback,
            "lease_operating_adjustment": lease_operating_adjustment, "pension_service": pension_service,
            "pension_interest": pension_interest, "pension_cash": pension_cash, "benefit_remaining": benefit,
            "benefit_related_paid": benefit_related_paid, "benefit_related_remaining": benefit_settlement_due,
            "group_operating_cash": group_operating_cash, "jv_operating_profit": jv_operating_profit,
            "jv_profit": jv_profit, "jv_fcfe": jv_fcfe, "jv_declared": jv_declared, "jv_paid": jv_paid,
            "jv_payment_backlog": jv_payment_backlog, "jv_cash": jv_cash,
            "sub_common_profit": sub_common_profit, "sub_declared": sub_declared, "sub_paid": sub_paid,
            "sub_dividend_receivable": sub_receivable, "sub_distributable": sub_distributable,
            "sub_cash": sub_cash, "parent_operating_cash": parent_operating_cash,
            "parent_profit": parent_profit, "parent_cash": parent_cash, "parent_term": parent_term,
            "parent_retained": parent_retained, "parent_future_buffer": future_buffer,
            "parent_financing": financing, "parent_debt_repayment": repayment, "parent_debt": parent_debt,
            "group_debt": debt, "group_financial_assets": closing_group,
            "common_profit": common_profit, "common_dividend": d, "planned_dividend": planned_d,
            "policy_cash_floor": c["policy_cash_floor"][t],
            "policy_floor_shortfall": max(c["policy_cash_floor"][t] - d, 0),
            "parent_negative_cash_gap": max(-parent_cash, 0),
            "parent_liquidity_shortfall": max(c["parent_required_cash"] - parent_cash, 0),
            "sub_negative_cash_gap": max(-sub_cash, 0), "group_negative_cash_gap": max(-closing_group, 0),
            "common_book": book, "opening_common_book": opening_book,
            "nci_profit": nci_profit, "nci_dividend": nci_dividend, "nci_book": nci_book,
            "nci_opening_financial_claim": opening_nci_financial_claim,
            "nci_financial_income": nci_financial_current,
            "nci_operating_reinvestment": nci_operating_reinvestment,
            "nci_financial_claim": nci_financial_claim,
            "nci_claim_cash_backing_shortfall": max(nci_financial_claim - sub_cash, 0),
            "ordinary_sub_cash_capacity": ordinary_sub_cash_capacity,
            "nci_claim_closure_residual": nci_financial_claim - (opening_nci_financial_claim + nci_profit - nci_dividend - nci_operating_reinvestment),
            "cash_closure_residual": closure,
        })

    if abs(project_gross - initial_project_state - c["future_project_cost"]) > 1e-8:
        raise AssertionError("construction capital not preserved")
    if abs(project_net - project_gross - accumulated_project_maintenance + accumulated_project_da) > 1e-8:
        raise AssertionError("in-use construction/replacement/depreciation capital closure")
    expected_cap_cash = c["future_project_cost"] + c["project_ap0"] - project_ap
    expected_cap_cash -= c["project_prepay0"] - project_prepay
    expected_cap_cash += c["legacy_project_ap0"] - legacy_ap
    if abs(cap_cash_total - expected_cap_cash) > 1e-8:
        raise AssertionError("paid/accrued capital bridge failure")

    terminal = terminal_value(c, rows[-1], lease_prepaid_tax)
    dlist = [r["common_dividend"] for r in rows]
    value = pv(dlist, ke) + terminal["common_dcf"] / ((1 + ke) ** n)
    ri = [r["common_profit"] - ke * r["opening_common_book"] for r in rows]
    ri_value = c["common_book0"] + pv(ri, ke)
    ri_value += (terminal["common_ri"] - rows[-1]["common_book"]) / ((1 + ke) ** n)
    year5 = pv(dlist[5:], ke) + terminal["common_dcf"] / ((1 + ke) ** (n - 5))
    return {
        "name": c["name"], "rows": rows, "terminal": terminal,
        "current_common_value": value, "current_common_value_per_share": value / c["shares"],
        "auxiliary_ri_value": ri_value, "auxiliary_ri_value_per_share": ri_value / c["shares"],
        "year5_common_value": year5, "year5_common_value_per_share": year5 / c["shares"],
        "distributions_per_share": [r["common_dividend"] / c["shares"] for r in rows[:5]],
        "terminal_present_value_share": (terminal["common_dcf"] / ((1 + ke) ** n) / value) if value != 0 else None,
        "group_financial_assets0": group_cash0,
        "construction_cash_total": cap_cash_total,
        "negative_cash_preserved": any(r["parent_negative_cash_gap"] > 0 or r["sub_negative_cash_gap"] > 0 for r in rows),
        "policy_conflict_present": any(r["policy_floor_shortfall"] > 0 for r in rows),
        "year5_to_year6": [rows[4], rows[5]] if n > 5 else [rows[4]],
    }


def terminal_value(c, r, lease_tax_remaining):
    tax, ke, g = c["tax"], c["equity_cost"], c["terminal_g"]
    wacc = ke * (1 - c["terminal_debt_weight"]) + c["debt_interest_rate"] * (1 - tax) * c["terminal_debt_weight"]
    if wacc <= g:
        raise ValueError("WACC must exceed terminal growth")
    # All new berths must have approached the selected mature utilization at the explicit endpoint.
    end_nopat = r["existing_nopat"] + r["project_nopat"]
    # Legacy pension interest ceases in ongoing operating earnings because the outstanding
    # old liability is separately deducted below. New service remains an operating cost.
    end_nopat += r["pension_interest"] * (1 - tax)
    nopat_next = end_nopat * (1 + g)
    reinvestment = max(nopat_next, 0) * g / c["terminal_roic"]
    maintenance_gap = max(r["maintenance"] - r["owned_da"], 0) * (1 + g)
    lease_gap = r["lease_operating_adjustment"] * (1 + g)
    operating_fcff = nopat_next - reinvestment - maintenance_gap + lease_gap
    group_operations = operating_fcff / (wacc - g)
    jv_operating_next = r["jv_operating_profit"] * (1 + g)
    jv_reinvest = max(jv_operating_next, 0) * g / c["jv_incremental_return"]
    jv_operations = (jv_operating_next - jv_reinvest) / (ke - g)

    group_required = c["group_required_cash"]
    jv_required = c["jv_required_cash"]
    group_excess = r["group_financial_assets"] - group_required
    jv_excess = r["jv_cash"] - jv_required - r["jv_payment_backlog"]
    group_financial_value = release_value(group_excess, c["financial_yield_aftertax"], c["terminal_release_rate"], ke)
    jv_financial_value = release_value(jv_excess, c["financial_yield_aftertax"], c["terminal_release_rate"], ke)
    # Required working financial capital is not added as surplus principal; its return and
    # growth funding are included once as an ongoing net cash contribution.
    required_cash_net_value = (group_required + jv_required) * (c["financial_yield_aftertax"] - g) / (ke - g)
    pension_legacy = r["benefit_remaining"] * (1 - tax)
    pending_obligations = r["project_ap"] + r["legacy_ap"] + r["benefit_related_remaining"]
    pending_obligations -= r["project_prepay"]
    nci_excess_cash = r["nci_financial_claim"]
    nci_financial_value = release_value(nci_excess_cash, c["financial_yield_aftertax"], c["terminal_release_rate"], ke)
    nci_operating_book = r["nci_book"] - nci_excess_cash
    nci_operating_profit = r["nci_profit"] - r["nci_financial_income"]
    nci_next = nci_operating_profit * (1 + g)
    nci_value = nci_operating_book + (nci_next - ke * nci_operating_book) / (ke - g) + nci_financial_value
    # Runoff is finite. Group loses old prepaid-rent cash; matching JV gains its noncash addback.
    weighted_share = c["prepaid_lease_direct_weight"] * c["qqct_share"]
    weighted_share += (1 - c["prepaid_lease_direct_weight"]) * c["other_lease_share"]
    lease_group_loss = finite_runoff_pv(r["lease_prepaid_remaining"], c["prepaid_lease_annual_runoff"], wacc)
    lease_jv_addback = finite_runoff_pv(r["lease_prepaid_remaining"], c["prepaid_lease_annual_runoff"], ke) * weighted_share
    lease_tax_addback = finite_runoff_pv(lease_tax_remaining, c["prepaid_lease_tax_runoff"], wacc)
    common_dcf = group_operations + jv_operations + group_financial_value + jv_financial_value
    common_dcf += required_cash_net_value - r["group_debt"] - nci_value - pension_legacy - pending_obligations
    common_dcf += -lease_group_loss + lease_jv_addback + lease_tax_addback
    # Backlog is a JV-to-parent transfer, not lost principal or extra group earnings.
    common_dcf += r["jv_payment_backlog"]

    excess_sum = group_excess - nci_excess_cash + jv_excess
    # Same old-benefit obligation as DCF: remove it from operating book and
    # earnings together, retain new service, then deduct the claim exactly once.
    operating_common_book = r["common_book"] - excess_sum + pension_legacy
    operating_common_profit = r["common_profit"] - excess_sum * c["financial_yield_aftertax"]
    operating_common_profit += r["pension_interest"] * (1 - tax)
    ri_operating = operating_common_book + (
        operating_common_profit * (1 + g) - ke * operating_common_book
    ) / (ke - g)
    common_ri = ri_operating + group_financial_value - nci_financial_value + jv_financial_value + r["jv_payment_backlog"] - pension_legacy
    return {
        "wacc": wacc, "nopat_next": nopat_next, "growth_reinvestment": reinvestment,
        "operating_fcff": operating_fcff, "group_operations": group_operations,
        "jv_operations": jv_operations, "group_excess_financial_principal": group_excess,
        "jv_excess_financial_principal": jv_excess,
        "group_financial_value": group_financial_value, "jv_financial_value": jv_financial_value,
        "required_cash_net_value": required_cash_net_value, "debt": r["group_debt"],
        "nci_value": nci_value, "pension_legacy_aftertax": pension_legacy,
        "nci_excess_financial_principal": nci_excess_cash, "nci_financial_value": nci_financial_value,
        "pending_obligations": pending_obligations, "lease_group_loss": lease_group_loss,
        "lease_jv_addback": lease_jv_addback, "lease_tax_addback": lease_tax_addback,
        "common_dcf": common_dcf, "common_ri": common_ri,
        "ri_operating_common_book": operating_common_book,
        "ri_operating_common_profit": operating_common_profit,
        "project_net_capital_not_added_again": r["project_net"],
    }


def zero_fixture(base, name, years=5):
    x = {}
    for k, v in base.items():
        if isinstance(v, list):
            x[k] = [0.0] * years if k != "intervals" else ["fixture-%s" % (i + 1) for i in range(years)]
        elif isinstance(v, (float, int)) and not isinstance(v, bool):
            x[k] = 0.0
        else:
            x[k] = v
    x.update({"name": name, "years": years, "shares": 1.0, "equity_cost": 0.1,
              "terminal_roic": 0.1, "jv_incremental_return": 0.1,
              "terminal_release_rate": 0.2, "subs_current_distributable_ratio": 1.0,
              "subs_declared_ratio": 1.0, "cycle_factor": [1.0] * years,
              "jv_cycle_factor": [1.0] * years, "jv_payment_factor": [1.0] * years,
              "sub_payment_factor": [1.0] * years})
    return x


def formal_chain_tests(base):
    results = []
    x = zero_fixture(base, "hand_flat_business")
    x.update({"old_nopat0": 10.0, "parent_own_profit0": 10.0, "parent_own_cash0": 10.0,
              "parent_cash0": 1.0, "parent_required_cash": 1.0, "group_required_cash": 1.0,
              "common_book0": 100.0, "parent_retained0": 100.0,
              "common_payout": [1.0] * 5, "parent_inflow_budget": 10.0})
    a = simulate(x)
    if max(abs(v - 10.0) for v in a["distributions_per_share"]) > 1e-8:
        raise AssertionError("flat-chain dividends")
    if abs(a["current_common_value"] - 100.0) > 1e-8:
        raise AssertionError("flat-chain value: expected 100")
    results.append({"name": x["name"], "expected_value": 100.0, "actual_value": a["current_common_value"]})
    x = zero_fixture(base, "hand_negative_cash")
    x.update({"old_nopat0": -1.0, "parent_own_profit0": -1.0, "parent_own_cash0": -1.0,
              "future_project_cost": 2.0, "build_weights": [1.0, 0, 0, 0, 0],
              "recognition_weights": [1.0, 0, 0, 0, 0],
              "parent_build_share": 1.0, "common_book0": 0.0})
    a = simulate(x)
    if abs(a["rows"][0]["parent_cash"] + 3.0) > 1e-8 or a["rows"][0]["common_dividend"] != 0:
        raise AssertionError("negative cash was filled or dividend paid")
    results.append({"name": x["name"], "expected_first_cash": -3.0, "actual_first_cash": a["rows"][0]["parent_cash"]})
    x = zero_fixture(base, "hand_financial_principal")
    x.update({"parent_cash0": 10.0, "common_book0": 10.0, "parent_retained0": 10.0})
    a = simulate(x)
    expected_terminal = 20.0 / 3.0
    if abs(a["terminal"]["common_dcf"] - expected_terminal) > 1e-8:
        raise AssertionError("financial principal recovered incorrectly")
    results.append({"name": x["name"], "expected_terminal": expected_terminal,
                    "actual_terminal": a["terminal"]["common_dcf"]})
    x = zero_fixture(base, "hand_two_sided_prepaid_lease")
    x.update({"old_nopat0": 0.2, "jv_operating_profit0": -0.1,
              "parent_cash0": 2.0, "prepaid_lease_balance0": 1.0,
              "prepaid_lease_annual_runoff": 0.2, "prepaid_lease_direct_weight": 1.0,
              "qqct_share": 0.5})
    a = simulate(x)
    first = a["rows"][0]
    net_cash_change = first["group_financial_assets"] - 2.0 + first["jv_cash"]
    if abs(first["common_profit"] - 0.1) > 1e-8 or abs(net_cash_change) > 1e-8:
        raise AssertionError("prepaid landlord/JV cash asymmetry")
    results.append({"name": x["name"], "expected_accounting_profit": 0.1,
                    "actual_accounting_profit": first["common_profit"],
                    "expected_cash_change": 0.0, "actual_cash_change": net_cash_change})
    x = zero_fixture(base, "hand_nci_principal_protected")
    x.update({"sub_cash0": 10.0, "nci_book0": 1.5, "common_book0": 8.5,
              "nci_initial_financial_share": 0.15, "sub_distributable0": 100.0,
              "parent_retained0": 100.0, "sub_release": [1.0, 0, 0, 0, 0],
              "parent_release": [1.0, 0, 0, 0, 0]})
    a = simulate(x)
    first = a["rows"][0]
    if abs(first["sub_paid"] - 8.5) > 1e-8 or abs(first["common_dividend"] - 8.5) > 1e-8:
        raise AssertionError("ordinary withdrawal exceeded attributed cash")
    if any(abs(r["nci_financial_claim"] - 1.5) > 1e-8 for r in a["rows"]):
        raise AssertionError("unpaid NCI principal fell after ordinary withdrawal")
    results.append({"name": x["name"], "expected_ordinary_payment": 8.5,
                    "actual_ordinary_payment": first["common_dividend"],
                    "expected_unpaid_nci_principal": 1.5,
                    "actual_unpaid_nci_principal": a["rows"][-1]["nci_financial_claim"]})
    x = zero_fixture(base, "hand_nonzero_legacy_benefit")
    x.update({"tax": 0.25, "old_nopat0": 10.0, "parent_own_profit0": 10.0,
              "parent_own_cash0": 10.0, "parent_cash0": 1.0,
              "parent_required_cash": 1.0, "group_required_cash": 1.0,
              "common_book0": 99.25, "parent_retained0": 100.0,
              "common_payout": [1.0] * 5, "parent_inflow_budget": 10.0,
              "benefit_liability0": 1.0, "benefit_discount_rate": 0.02,
              "benefit_base_expense": 0.02, "benefit_cash": [0.02] * 5})
    a = simulate(x)
    # No new service; liability stays 1. Tax-adjusted interest .015 is removed
    # from earnings, then the same .75 old claim is deducted: 10.015/.10-.75.
    expected_terminal = 99.4
    if abs(a["terminal"]["pension_legacy_aftertax"] - 0.75) > 1e-8:
        raise AssertionError("wrong legacy benefit tax basis")
    if abs(a["terminal"]["common_dcf"] - expected_terminal) > 1e-8 or abs(a["terminal"]["common_ri"] - expected_terminal) > 1e-8:
        raise AssertionError("DCF/RI old benefit claim omitted or double-counted")
    results.append({"name": x["name"], "expected_terminal": expected_terminal,
                    "actual_dcf_terminal": a["terminal"]["common_dcf"],
                    "actual_ri_terminal": a["terminal"]["common_ri"],
                    "expected_old_benefit_claim_aftertax": 0.75})
    return results
