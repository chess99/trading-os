"""Pure-stdlib annual cash-rental model; importing does not calculate a case."""
import copy
import math


class EconomicInfeasible(Exception):
    """A fully specified economic path cannot satisfy a binding payment."""
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_tree(value):
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, (float, int)):
        return math.isfinite(value)
    return True


def validate_inputs(data):
    require(data["schema_version"] == 1, "INPUT_SCHEMA")
    require(data["information_cutoff"] == data["model_as_of"], "CUTOFF_MISMATCH")
    require(data["currency"] == "CNY" and data["shares"] > 0, "UNITS_OR_SHARES")
    require(data["base"]["years"] == 10, "EXPLICIT_HORIZON_MUST_BE_10")
    require(finite_tree(data), "NONFINITE_INPUT")
    for name in ("dutyfree_growth", "taxed_growth", "other_growth", "dutyfree_margin",
                 "nonrent_nondepreciation_accrual_opex_rate", "inventory_net_days",
                 "operating_income_cash_tax_rate", "growth_capex", "capital_floor_ramp",
                 "construction_payable_settlement", "old_restoration_settlement"):
        require(len(data["base"][name]) == 10, "YEAR_COUNT:" + name)
    source = data["source_facts"]
    require(abs(source["q3_group_profit"] - source["q3_common_profit"] -
                source["q3_nci_profit"]) < 0.02, "SOURCE_PROFIT_ATTRIBUTION")
    require(data["opening"]["debt_investment_estimate"] <
            source["q3_other_current_assets"], "OTHER_CURRENT_NOT_ALL_CASH")
    require(abs(sum(data["base"]["construction_payable_settlement"]) -
                data["opening"]["construction_payable_estimate"]) < 0.01,
            "CONSTRUCTION_SETTLEMENT_BRIDGE")
    require(abs(sum(data["base"]["old_restoration_settlement"]) -
                source["q3_restoration_provision"]) < 0.01, "RESTORATION_BRIDGE")


def val_path(scenario, path_name, index, default):
    return scenario[path_name][index] if path_name in scenario else default


def opening_state(data, scenario):
    source = data["source_facts"]
    opening = copy.deepcopy(data["opening"])
    for name in opening:
        if name in scenario:
            opening[name] = scenario[name]
    goods_ap = source["q3_ap"] - opening["construction_payable_estimate"]
    nwc = (source["q3_inventory_net"] + source["q3_ar"] + source["q3_prepayment"] +
           source["q3_other_ar"] + opening["operating_other_current_assets_estimate"] -
           goods_ap - source["q3_notes"] - source["q3_contract_liability"] -
           source["q3_payroll"] - (source["q3_other_payable"] - source["q3_dividend_payable"]) -
           (source["q3_tax_payable"] - opening["income_tax_payable_estimate"]))
    surplus = (source["q3_cash"] + opening["debt_investment_estimate"] +
               opening["october_net_financial_bridge"] - opening["minimum_operating_cash"] -
               opening["nci_surplus_financial_gross_estimate"] -
               opening["financial_asset_credit_loss"])
    debt = (source["q3_short_bank"] + source["q3_long_bank"] + opening["current_bank_estimate"] -
            opening["nci_financing_debt_estimate"])
    require(surplus >= 0 and debt >= 0, "OPENING_FINANCIAL_CLASSIFICATION")
    return {"nwc": nwc, "minimum_cash": opening["minimum_operating_cash"],
            "fixed_operating_capital": sum(source["q3_physical_components"].values()) -
            opening["physical_operating_asset_exclusions"],
            "surplus_financial": surplus, "ordinary_debt": debt, "emergency_debt": 0.0,
            "associate_value": source["q3_associate_book"] * opening["associate_value_to_book"],
            "other_external_claim": opening["noncommon_external_other_claim"],
            "opening_income_tax": opening["income_tax_payable_estimate"],
            "parent": {"liquid": opening["parent_liquid_financial_assets_estimate"],
                       "pool_liability": opening["parent_pool_liability_estimate"],
                       "pool_protected_floor": opening["parent_pool_protected_floor"],
                       "liquid_floor": opening["parent_liquid_floor"],
                       "locked": opening["parent_locked_liquidity"],
                       "retained": opening["parent_retained_before_pending_dividend_estimate"],
                       "dividend_receivable": opening["parent_old_dividend_receivable_estimate"]}}


def operating_period(p, prior):
    """Canonical operating function also used by the closed-form examples."""
    revenue = sum(p["revenue_by_product"].values())
    gross = sum(p["revenue_by_product"][key] * p["margin_by_product"][key]
                for key in p["revenue_by_product"])
    cost = revenue - gross
    opex = revenue * p["opex_rate"]
    depreciation = revenue * p["depreciation_rate"]
    fixed_service = p.get("fixed_rent_service", p["fixed_rent_cash"])
    rent = fixed_service + revenue * p["variable_rent_rate"]
    fixed_rent_adjustment = p["fixed_rent_cash"] - fixed_service
    operating_fees = revenue * p["operating_fee_rate"]
    inventory_loss = revenue * p["inventory_loss_rate"]
    exit_revenue = p.get("airport_exit_revenue", 0.0)
    avoided_cost = 0.0
    if exit_revenue:
        lost_gross = exit_revenue * p["margin_by_product"]["dutyfree"]
        avoided_cost = lost_gross - p["airport_exit_profit_loss"]
        rent_avoided = p["airport_exit_rent_avoided"]
        depreciation_avoided = p["airport_exit_depreciation_avoided"]
        # The residual includes all other avoided service/fees/loss costs.
        opex -= avoided_cost - rent_avoided - depreciation_avoided
        depreciation -= depreciation_avoided
        rent -= rent_avoided
        revenue -= exit_revenue
        gross -= lost_gross
        cost = revenue - gross
    require(min(revenue, gross, cost, depreciation, rent, opex) >= 0, "OPERATING_COMPONENT_NEGATIVE")
    ebit = gross - opex - depreciation - rent - operating_fees - inventory_loss
    cash_tax = max(ebit, 0.0) * p["income_tax_rate"]
    nopat = ebit - cash_tax
    components = {
        "inventory_net": cost * p["inventory_days"] / 365.0,
        "trade_ar": revenue * p["trade_receivable_rate"],
        "prepayment": revenue * p["prepayment_rate"],
        "other_operating_ar": revenue * p["other_operating_receivable_rate"],
        "operating_vat_other_assets": revenue * p["vat_other_asset_rate"],
        "goods_ap_notes": -cost * p["goods_payable_days"] / 365.0,
        "contract_liability": -revenue * p["contract_liability_rate"],
        "payroll_payable": -revenue * p["payroll_rate"],
        "other_operating_payable": -revenue * p["other_payable_rate"],
        "nonincome_tax_payable": -revenue * p["nonincome_tax_payable_rate"]}
    nwc = sum(components.values())
    min_cash = revenue * p["minimum_cash_rate"]
    delta_nwc = nwc - prior["nwc"]
    delta_min_cash = min_cash - prior["minimum_cash"]
    capital_floor = p["capital_floor_ramp"] * (
        p["terminal_growth"] / p["terminal_roic"] * max(nopat, 0.0) - delta_nwc - delta_min_cash)
    growth_capex = max(p["growth_capex"], capital_floor)
    maintenance = depreciation
    net_reinvestment = growth_capex + delta_nwc + delta_min_cash
    old_cash = p["old_construction"] + p["old_restoration"] + p["opening_income_tax"]
    restoration = p["ongoing_restoration"]
    fcff = (nopat + depreciation - maintenance - net_reinvestment - fixed_rent_adjustment - old_cash -
            restoration - p.get("airport_exit_cash_cost", 0.0))
    nci_claim = max(0.0, p["nci_nopat"] -
                    p["nci_capital_share"] * (net_reinvestment + restoration + fixed_rent_adjustment))
    common_fcff = fcff - nci_claim
    fixed_end = prior["fixed_operating_capital"] + growth_capex
    capital_begin = prior["fixed_operating_capital"] + prior["nwc"] + prior["minimum_cash"]
    capital_end = fixed_end + nwc + min_cash
    average_capital = (capital_begin + capital_end) / 2.0
    return {"revenue": revenue, "gross_profit": gross, "merchandise_cost": cost,
            "nonrent_accrual_opex": opex, "rent_service_cost": rent,
            "fixed_rent_cash_adjustment": fixed_rent_adjustment,
            "rent_cash_basis_before_variable_wc": rent + fixed_rent_adjustment,
            "economic_depreciation": depreciation, "maintenance_capex": maintenance,
            "operating_fees": operating_fees, "recurring_inventory_loss": inventory_loss,
            "ebit_cash_rent": ebit, "operating_cash_income_tax": cash_tax, "group_nopat": nopat,
            "nwc_components": components, "nwc": nwc, "delta_nwc": delta_nwc,
            "minimum_cash": min_cash, "delta_minimum_cash": delta_min_cash,
            "growth_capex": growth_capex, "net_reinvestment": net_reinvestment,
            "old_construction_cash": p["old_construction"], "old_restoration_cash": p["old_restoration"],
            "opening_income_tax_cash": p["opening_income_tax"], "ongoing_restoration_cash": restoration,
            "airport_exit_cash": p.get("airport_exit_cash_cost", 0.0),
            "airport_exit_revenue": exit_revenue, "airport_exit_avoided_cost": avoided_cost,
            "group_fcff": fcff, "nci_nopat": p["nci_nopat"], "nci_cash_claim": nci_claim,
            "common_fcff": common_fcff, "common_operating_nopat": nopat - p["nci_nopat"],
            "fixed_operating_capital": fixed_end, "operating_capital_begin": capital_begin,
            "operating_capital_end": capital_end, "average_operating_capital": average_capital,
            "effective_roic": nopat / average_capital if average_capital > 0 else None}


def parent_available(parent):
    protected = min(parent["pool_protected_floor"], parent["pool_liability"])
    return max(0.0, parent["liquid"] - protected - parent["liquid_floor"] - parent["locked"])


def parent_distribution(parent, p, ordinary_profit, group_budget):
    """Internal movements affect the payer, not consolidated wealth."""
    state = copy.deepcopy(parent)
    before_liquid = state["liquid"]
    before_retained = state["retained"]
    old_receipt = state["dividend_receivable"]
    state["liquid"] += old_receipt + p["other_cash"]
    state["dividend_receivable"] = 0.0
    state["retained"] += p["other_profit"]
    settlement = min(p["internal_settlement"], state["pool_liability"])
    state["liquid"] -= settlement
    state["pool_liability"] -= settlement
    target = max(0.0, ordinary_profit) * p["distribution_ratio"]
    pending = p["pending_distribution"]
    target = max(target, pending)
    interim_request = pending if pending else p.get("interim_target_fraction", 0.4) * target
    interim_capacity = min(parent_available(state), max(state["retained"], 0.0), max(group_budget, 0.0))
    if pending and interim_capacity + 0.01 < pending:
        raise EconomicInfeasible("APPROVED_PENDING_DIVIDEND_CANNOT_BE_PAID",
                                 {"pending": pending, "capacity": interim_capacity,
                                  "parent_at_payment": state, "group_budget": group_budget})
    interim = min(interim_request, interim_capacity)
    state["liquid"] -= interim
    state["retained"] -= interim
    declaration = max(ordinary_profit, 0.0) * p["upstream_declaration_ratio"]
    new_profit = declaration + p["other_profit"]
    reserve = max(new_profit, 0.0) * p["reserve_rate"]
    state["retained"] += declaration - reserve
    current_receipt = declaration * p["collection_rate"]
    state["liquid"] += current_receipt
    state["dividend_receivable"] = declaration - current_receipt
    final_capacity = min(parent_available(state), max(state["retained"], 0.0),
                         max(group_budget - interim, 0.0))
    final = min(max(target - interim, 0.0), final_capacity)
    state["liquid"] -= final
    state["retained"] -= final
    distribution = interim + final
    cash_residual = state["liquid"] - (before_liquid + old_receipt + current_receipt +
                                      p["other_cash"] - settlement - distribution)
    retained_residual = state["retained"] - (before_retained + declaration + p["other_profit"] -
                                            reserve - distribution)
    require(abs(cash_residual) < 0.0001 and abs(retained_residual) < 0.0001,
            "PARENT_CASH_OR_PROFIT_CONSERVATION")
    return state, {"desired_distribution": target, "actual_distribution": distribution,
                   "interim_distribution": interim, "final_distribution": final,
                   "parent_old_receivable_cash": old_receipt,
                   "parent_new_dividend_declared": declaration,
                   "parent_current_dividend_cash": current_receipt,
                   "parent_other_profit": p["other_profit"], "parent_other_cash": p["other_cash"],
                   "parent_reserve_assumption": reserve, "internal_settlement": settlement,
                   "parent_cash_residual": cash_residual, "parent_retained_residual": retained_residual,
                   "parent_end_available": parent_available(state), "parent_state_end": state}


def treasury_after_distribution(surplus, debt, fcff, interest_received, interest_paid,
                                repayment, distribution, borrowing):
    end_surplus = surplus + fcff + interest_received - interest_paid - repayment - distribution + borrowing
    end_debt = debt - repayment + borrowing
    return {"surplus_financial": end_surplus, "ordinary_debt": end_debt,
            "net_financial_change": (end_surplus - end_debt) - (surplus - debt),
            "expected_net_financial_change": fcff + interest_received - interest_paid - distribution}


def terminal_cash(group_nopat, nci_nopat, nci_capital_share, restoration, growth, roic,
                  advance=True):
    require(roic > 0 and growth >= 0, "TERMINAL_CAPITAL_PARAMETERS")
    scale = 1.0 + growth if advance else 1.0
    group_profit = group_nopat * scale
    nci_profit = nci_nopat * scale
    ongoing = restoration * scale
    reinvestment = max(group_profit, 0.0) * growth / roic
    nci_claim = max(0.0, nci_profit - nci_capital_share * (reinvestment + ongoing))
    return {"group_nopat": group_profit, "group_reinvestment": reinvestment,
            "ongoing_restoration": ongoing, "nci_cash_claim": nci_claim,
            "common_fcff": group_profit - reinvestment - ongoing - nci_claim}


def common_fixed_rent_adjustment(row, nci_capital_share):
    """The auxiliary method must retain the same NCI share of this cash gap."""
    if row["fixed_rent_cash_adjustment"] == 0.0:
        return 0.0
    without_gap = max(0.0, row["nci_nopat"] - nci_capital_share * (
        row["net_reinvestment"] + row["ongoing_restoration_cash"]))
    return row["fixed_rent_cash_adjustment"] - (without_gap - row["nci_cash_claim"])


def terminal_lease_boundary(schedule):
    """Narrow renewal-price diagnostic: no unexplained cash gap may vanish."""
    last = schedule["years"][-1]
    remaining = schedule["remaining_existing_contract_cash_after_explicit_horizon"]
    require(abs(last["fixed_cash_minus_service"]) <= 0.01 and abs(remaining) <= 0.01,
            "TERMINAL_LEASE_CASH_UNRECONCILED")
    return {"status": "CONSISTENT_UNDER_STATED_MATURITY_ASSUMPTION",
            "last_fixed_service": last["fixed_service"],
            "last_fixed_cash": last["fixed_cash"],
            "last_fixed_cash_minus_service": last["fixed_cash_minus_service"],
            "remaining_existing_contract_cash": remaining,
            "terminal_rental_cost_in_nopat": True}


def equity_bridge(state):
    return (state["surplus_financial"] - state["ordinary_debt"] +
            state["associate_value"] - state["other_external_claim"])


def operating_value(rows, start_year, rate, growth, roic, nci_capital_share):
    require(rate > growth and rate > 0, "DISCOUNT_NOT_ABOVE_GROWTH")
    tail = terminal_cash(rows[-1]["group_nopat"], rows[-1]["nci_nopat"], nci_capital_share,
                         rows[-1]["ongoing_restoration_cash"], growth, roic)
    tv = tail["common_fcff"] / (rate - growth)
    explicit_pv = sum(row["common_fcff"] / (1.0 + rate) ** (index + 1 - start_year)
                      for index, row in enumerate(rows) if index + 1 > start_year)
    tv_pv = tv / (1.0 + rate) ** (len(rows) - start_year)
    return {"operating_value": explicit_pv + tv_pv, "explicit_pv": explicit_pv,
            "terminal_pv": tv_pv, "terminal_year10_value": tv,
            "terminal_year11": tail,
            "terminal_share_of_operating_value": tv_pv / (explicit_pv + tv_pv)
            if abs(explicit_pv + tv_pv) > 1e-9 else None}


def lease_schedule(data, scenario):
    b = data["base"]
    bridge = b["lease_maturity_bridge"]
    replacement_multiplier = scenario.get("future_replacement_price_multiplier", 1.0)
    if "future_replacement_price_multiplier" in scenario:
        expected_multiplier = ((bridge["sustainable_fixed_cash_floor_first"] +
                                scenario.get("lease_floor_delta", 0.0)) /
                               bridge["sustainable_fixed_cash_floor_first"])
        require(replacement_multiplier > 0 and abs(replacement_multiplier - expected_multiplier) < 1e-12,
                "RENEWAL_PRICE_SCENARIO_INCONSISTENT")
    after_years = bridge["after5_spread_years_assumption"]
    monthly = ([bridge["cash_due_year1"] / 12.0] * 12 +
               [bridge["cash_due_year2"] / 12.0] * 12 +
               [bridge["cash_due_year3_to5_total"] / 36.0] * 36 +
               [bridge["cash_due_after5_total"] / (12.0 * after_years)] * (12 * after_years))
    elapsed = bridge["months_elapsed_to_model_date"]
    schedule = []
    for index in range(b["years"]):
        service = (bridge["sustainable_fixed_cash_floor_first"] + scenario.get("lease_floor_delta", 0.0)) * (
            1.0 + b["rental_fixed_growth"]) ** index
        start = elapsed + 12 * index
        existing = sum(monthly[start:start + 12])
        replacement = bridge["new_or_replacement_cash_additions"][index] * replacement_multiplier
        before_shift = max(existing + replacement, service)
        shift = scenario.get("lease_timing_shift_into_year1", 0.0)
        timing = shift if index == 0 else (-shift if index == 1 else 0.0)
        cash = before_shift + timing
        require(cash >= 0 and service > 0, "LEASE_CASH_OR_SERVICE_INVALID")
        schedule.append({"fixed_service": service, "mapped_existing_cash": existing,
                         "replacement_cash_budget": replacement, "cash_before_timing": before_shift,
                         "timing_shift": timing, "fixed_cash": cash,
                         "fixed_cash_minus_service": cash - service})
    return {"source_july_to_october_payment_proxy": sum(monthly[:elapsed]),
            "remaining_existing_contract_cash_after_explicit_horizon": sum(
                monthly[elapsed + 12 * b["years"]:]),
            "future_replacement_price_multiplier": replacement_multiplier,
            "not_reported_actual_payment": True, "years": schedule}


def year_parameters(data, scenario, index, revenues, opening, lease_row):
    b = data["base"]
    mult = val_path(scenario, "revenue_multiplier", index, 1.0)
    margin_delta = (scenario.get("dutyfree_margin_delta", 0.0) +
                    val_path(scenario, "margin_delta_path", index, 0.0))
    df_margin = b["dutyfree_margin"][index] + margin_delta
    n = b["nci"]
    aftertax_margin_delta = margin_delta * n["gross_margin_shock_aftertax_factor"]
    haimian = (n["haimian_first_net_profit"] * (1.0 + n["haimian_growth"]) ** index * mult *
               max(0.0, 1.0 + aftertax_margin_delta / n["haimian_reference_net_margin"]))
    shanghai = (n["shanghai_retail_first_revenue"] * (1.0 + n["shanghai_retail_growth"]) ** index *
                mult * max(0.0, n["shanghai_net_margin"] + aftertax_margin_delta) * n["shanghai_nci_ownership"])
    other = (n["other_first_net_profit"] * (1.0 + n["other_growth"]) ** index * mult *
             max(0.0, 1.0 + aftertax_margin_delta / n["other_reference_net_margin"]))
    exiting = index + 1 >= scenario.get("airport_exit_year", 1000)
    if exiting:
        shanghai = 0.0
    nci_net_profit = haimian + shanghai + other
    o = dict(data["opening"])
    o.update({key: value for key, value in scenario.items() if key in o})
    fin = b["financing"]
    nci_net_interest = (o["nci_surplus_financial_gross_estimate"] * fin["deposit_yield"] *
                        (1.0 - fin["deposit_income_tax"]) -
                        o["nci_financing_debt_estimate"] * fin["bank_rate"] *
                        (1.0 - fin["bank_tax_shield"])) * (1.0 + n["financial_principal_growth"]) ** index
    nci_net_interest *= scenario.get("nci_financial_income_subtraction_scale",
                                     n["financial_income_subtraction_scale"])
    nci_nopat = max(0.0, nci_net_profit - nci_net_interest)
    tax = b["operating_income_cash_tax_rate"][index] + scenario.get("tax_rate_delta", 0.0)
    if index >= 1:
        tax += scenario.get("tax_rate_delta_from_year2", 0.0)
    nci_tax_change_factor = (1.0 - tax) / (1.0 - b["operating_income_cash_tax_rate"][index])
    nci_nopat *= nci_tax_change_factor
    project_cash = val_path(scenario, "growth_capex_override", index, b["growth_capex"][index])
    project_cash *= scenario.get("growth_capex_multiplier", 1.0)
    if index < 5:
        project_cash += scenario.get("growth_capex_add_first_five", 0.0)
    overlap = scenario.get("old_engineering_within_project_cash_budget",
                            b["old_engineering_within_project_cash_budget"])
    overlap_this_year = (overlap / data["opening"]["construction_payable_estimate"] *
                         b["construction_payable_settlement"][index])
    require(project_cash + 0.01 >= overlap_this_year, "PROJECT_CASH_BELOW_INCLUDED_OLD_PAYABLE")
    p = {
        "revenue_by_product": {key: amount * mult for key, amount in revenues.items()},
        "margin_by_product": {"dutyfree": df_margin, "taxed": b["taxed_margin"], "other": b["other_margin"]},
        "opex_rate": b["nonrent_nondepreciation_accrual_opex_rate"][index] + scenario.get("opex_rate_delta", 0.0),
        "depreciation_rate": b["depreciation_and_maintenance_rate"],
        "fixed_rent_cash": lease_row["fixed_cash"], "fixed_rent_service": lease_row["fixed_service"],
        "variable_rent_rate": b["rental_variable_rate"] + scenario.get("rental_variable_delta", 0.0),
        "operating_fee_rate": b["operating_taxes_and_fees_rate"],
        "inventory_loss_rate": b["recurring_inventory_loss_rate"], "income_tax_rate": tax,
        "inventory_days": b["inventory_net_days"][index] + scenario.get("inventory_days_delta", 0.0) +
        val_path(scenario, "inventory_days_delta_path", index, 0.0),
        "trade_receivable_rate": b["trade_receivable_rate"], "prepayment_rate": b["prepayment_rate"],
        "other_operating_receivable_rate": b["other_operating_receivable_rate"],
        "vat_other_asset_rate": b["operating_vat_and_other_asset_rate"],
        "goods_payable_days": b["goods_payable_days"], "contract_liability_rate": b["contract_liability_rate"],
        "payroll_rate": b["payroll_payable_rate"], "other_payable_rate": b["other_operating_payable_rate"],
        "nonincome_tax_payable_rate": b["operating_nonincome_tax_payable_rate"],
        "minimum_cash_rate": scenario.get("minimum_cash_rate", b["minimum_cash_rate"]),
        "capital_floor_ramp": b["capital_floor_ramp"][index],
        "terminal_growth": scenario.get("terminal_growth", b["terminal_growth"]),
        "terminal_roic": scenario.get("terminal_incremental_roic", b["terminal_incremental_roic"]),
        "growth_capex": project_cash - overlap_this_year,
        "project_cash_envelope": project_cash, "old_engineering_overlap_credit": overlap_this_year,
        "old_construction": b["construction_payable_settlement"][index],
        "old_restoration": b["old_restoration_settlement"][index],
        "opening_income_tax": opening["opening_income_tax"] if index == 0 else 0.0,
        "ongoing_restoration": b["ongoing_restoration_cash"],
        "nci_nopat": nci_nopat, "nci_net_profit_anchor": nci_net_profit,
        "nci_financial_income_removed": nci_net_interest,
        "nci_scenario_tax_change_factor": nci_tax_change_factor,
        "nci_capital_share": scenario.get("nci_capital_consumption_share", n["capital_consumption_share"])}
    if exiting:
        factor = 1.02 ** (index + 1 - scenario["airport_exit_year"])
        for name in ("airport_exit_revenue", "airport_exit_profit_loss", "airport_exit_rent_avoided",
                     "airport_exit_depreciation_avoided"):
            p[name] = scenario[name] * factor
        p["airport_exit_cash_cost"] = scenario["airport_exit_cash_cost"] if index + 1 == scenario["airport_exit_year"] else 0.0
    return p


def run_case(data, name):
    scenario = data["scenarios"][name]
    b = data["base"]
    first = opening_state(data, scenario)
    state = copy.deepcopy(first)
    lease = lease_schedule(data, scenario)
    revenues = dict(b["first_revenue"])
    rows = []
    states = []
    for index in range(b["years"]):
        if index:
            for key in revenues:
                revenues[key] *= 1.0 + b[key + "_growth"][index]
        p = year_parameters(data, scenario, index, revenues, first, lease["years"][index])
        row = operating_period(p, state)
        incremental_capital = row["operating_capital_end"] - row["operating_capital_begin"]
        incremental_profit = row["group_nopat"] - rows[-1]["group_nopat"] if rows else None
        row["incremental_nopat"] = incremental_profit
        row["incremental_operating_capital"] = incremental_capital
        row["incremental_roic_diagnostic"] = (incremental_profit / incremental_capital
                                               if rows and incremental_capital > 100000000.0 else None)
        row["incremental_roic_note"] = ("Year-on-year diagnostic, not project causality; ramp timing matters."
                                        if rows and incremental_capital > 100000000.0 else
                                        "No comparable full-year starting NOPAT or denominator<=0.1bn; ratio omitted, not infinite.")
        financing = b["financing"]
        received_interest = max(state["surplus_financial"], 0.0) * financing["deposit_yield"] * (
            1.0 - financing["deposit_income_tax"])
        paid_interest = (state["ordinary_debt"] * financing["bank_rate"] +
                         state["emergency_debt"] * (financing["emergency_credit_rate"] - financing["bank_rate"])) * (
                             1.0 - financing["bank_tax_shield"])
        ordinary_profit = row["common_operating_nopat"] + received_interest - paid_interest
        pending = data["shares"] * b["parent"]["pending_distribution_per_share"] if index == 0 else 0.0
        before_principal = state["surplus_financial"] + row["common_fcff"] + received_interest - paid_interest
        planned_repayment = min(financing["ordinary_debt_repayment"][index], state["ordinary_debt"])
        repayment = min(planned_repayment, max(before_principal - pending, 0.0))
        before_distribution = before_principal - repayment
        borrowing = max(0.0, pending - before_distribution)
        if borrowing > financing["emergency_credit_limit"] - state["emergency_debt"] + 0.01:
            raise EconomicInfeasible("OPERATING_OR_PENDING_CASH_EXCEEDS_EMERGENCY_CREDIT:Y%d" % (index + 1),
                                     {"rows_completed": rows, "current_operating_row": row,
                                      "current_parameters": p, "state_before": state,
                                      "borrowing_needed": borrowing, "opening": first})
        group_budget = before_distribution + borrowing
        pp = b["parent"]
        parent_p = {
            "other_cash": pp["other_cash"], "other_profit": pp["other_profit"],
            "internal_settlement": pp["net_internal_settlement"][index] +
            (scenario.get("parent_settlement_add_first", 0.0) if index == 0 else 0.0),
            "distribution_ratio": pp["common_distribution_ratio"], "pending_distribution": pending,
            "interim_target_fraction": pp["interim_target_fraction_after_first"],
            "upstream_declaration_ratio": pp["new_dividend_declaration_ratio"],
            "reserve_rate": scenario.get("parent_reserve_assumption", pp["reserve_provision_assumption_rate"]),
            "collection_rate": val_path(scenario, "parent_collection_path", index, pp["new_declaration_cash_collection_rate"])}
        try:
            parent_end, parent_detail = parent_distribution(state["parent"], parent_p, ordinary_profit, group_budget)
        except EconomicInfeasible as exc:
            exc.details.update({"rows_completed": rows, "current_operating_row": row,
                                "current_parameters": p, "state_before": state, "opening": first})
            raise
        actual_d = parent_detail["actual_distribution"]
        treasury = treasury_after_distribution(state["surplus_financial"], state["ordinary_debt"],
                                               row["common_fcff"], received_interest, paid_interest,
                                               repayment, actual_d, borrowing)
        require(abs(treasury["net_financial_change"] - treasury["expected_net_financial_change"]) < 0.0001,
                "GROUP_FINANCIAL_CONSERVATION")
        if treasury["surplus_financial"] < -0.01:
            raise EconomicInfeasible("OPERATING_MINIMUM_CASH_NOT_FUNDED:Y%d" % (index + 1),
                                     {"rows_completed": rows, "current_operating_row": row,
                                      "treasury": treasury, "opening": first})
        end = {"nwc": row["nwc"], "minimum_cash": row["minimum_cash"],
               "fixed_operating_capital": row["fixed_operating_capital"],
               "surplus_financial": treasury["surplus_financial"], "ordinary_debt": treasury["ordinary_debt"],
               "emergency_debt": max(0.0, state["emergency_debt"] - max(
                   0.0, repayment - (state["ordinary_debt"] - state["emergency_debt"]))) + borrowing,
               "associate_value": state["associate_value"] * (1.0 + data["opening"]["associate_value_growth"]),
               "other_external_claim": state["other_external_claim"], "parent": parent_end}
        year_end = b["first_holding_year"] + index
        row.update({"holding_year": index + 1, "period_start": "%d-11-01" % (year_end - 1),
                    "period_end": "%d-10-31" % year_end, "parameters": p, "lease_bridge": lease["years"][index],
                    "ordinary_normal_profit": ordinary_profit, "financial_interest_received": received_interest,
                    "bank_interest_paid": paid_interest, "bank_principal_repayment": repayment,
                    "planned_repayment_deferred": planned_repayment - repayment, "emergency_borrowing": borrowing,
                    "dividend_cash": actual_d, "dividend_per_share": actual_d / data["shares"],
                    "dividend_to_normal_profit": actual_d / ordinary_profit if ordinary_profit > 0 else None,
                    "distribution_events": [
                        {"estimated_date": "%d-12-15" % (year_end - 1),
                         "cash": parent_detail["interim_distribution"], "date_is_disclosed": False,
                         "known_amount_pending": index == 0},
                        {"estimated_date": "%d-07-15" % year_end,
                         "cash": parent_detail["final_distribution"], "date_is_disclosed": False}],
                    "parent_bridge": parent_detail, "financial_state_end": end})
        rows.append(row)
        states.append(end)
        state = end
    rate = scenario.get("discount_rate", b["discount_rate"])
    growth = scenario.get("terminal_growth", b["terminal_growth"])
    roic = scenario.get("terminal_incremental_roic", b["terminal_incremental_roic"])
    nci_share = scenario.get("nci_capital_consumption_share", b["nci"]["capital_consumption_share"])
    lease_boundary = (terminal_lease_boundary(lease)
                      if "future_replacement_price_multiplier" in scenario else None)
    valuation = operating_value(rows, 0, rate, growth, roic, nci_share)
    bridge = equity_bridge(first)
    current_equity = valuation["operating_value"] + bridge
    normalized = terminal_cash(rows[2]["group_nopat"], rows[2]["nci_nopat"], nci_share,
                               rows[2]["ongoing_restoration_cash"], growth, roic, advance=False)
    auxiliary_op = (rows[0]["common_fcff"] / (1.0 + rate) + rows[1]["common_fcff"] / (1.0 + rate) ** 2 +
                    normalized["common_fcff"] / (rate - growth) / (1.0 + rate) ** 2)
    auxiliary_unsettled_obligations_pv = sum(
        (row["old_construction_cash"] + row["old_restoration_cash"] + row["opening_income_tax_cash"] +
         row["airport_exit_cash"] + common_fixed_rent_adjustment(row, nci_share)) / (1.0 + rate) ** (index + 1)
        for index, row in enumerate(rows) if index >= 2)
    auxiliary_op -= auxiliary_unsettled_obligations_pv
    auxiliary_equity = auxiliary_op + bridge
    divergence = abs(auxiliary_equity - current_equity) / max(abs(current_equity), 1.0)
    valuation.update({"current_equity": current_equity, "current_per_share": current_equity / data["shares"],
                      "ordinary_financial_bridge": bridge, "auxiliary_normalized_equity": auxiliary_equity,
                      "auxiliary_unsettled_obligations_pv": auxiliary_unsettled_obligations_pv,
                      "auxiliary_per_share": auxiliary_equity / data["shares"],
                      "method_divergence_ratio": divergence, "explain_if_divergence_above_25pct": divergence > 0.25,
                      "discount_rate": rate, "terminal_growth": growth, "terminal_incremental_roic": roic})
    result = {"status": "NUMERIC", "scenario": name, "scenario_definition": scenario,
              "terminal_lease_boundary": lease_boundary,
              "opening": first, "lease_schedule": lease, "rows": rows, "valuation": valuation,
              "same_case_year5_financial_bridge": equity_bridge(states[4]),
              "resource_note": "Numeric candidate only; independent comparison/editorial acceptance required"}
    require(finite_tree(result), "NONFINITE_RESULT")
    return result


def assemble(data, results):
    base = results["base"]
    core_valid = all(results[key]["status"] == "NUMERIC" for key in ("base", "core_low", "core_high"))
    if base["status"] != "NUMERIC":
        return {"status": "ECONOMICALLY_INFEASIBLE_BASE", "value_range": None, "return_model": None,
                "valuation_note": base["reason"], "return_model_note": base["reason"],
                "case_statuses": {key: result["status"] for key, result in results.items()}}
    rows = base["rows"]
    shares = data["shares"]
    b = data["base"]
    year5_state = rows[4]["financial_state_end"]
    bridge5 = equity_bridge(year5_state)
    terminal_values = []
    terminal_detail = {}
    for endpoint in ("core_low", "core_high"):
        ep = data["scenarios"][endpoint]
        op = operating_value(rows, 5, ep["discount_rate"], ep["terminal_growth"],
                             ep["terminal_incremental_roic"], b["nci"]["capital_consumption_share"])
        value = (op["operating_value"] + bridge5) / shares
        terminal_values.append(value)
        terminal_detail[endpoint] = {"base_state_only": True, "operating": op,
                                     "financial_bridge_same_base": bridge5, "per_share": value}
    rate = b["discount_rate"]
    base_t5_op = operating_value(rows, 5, rate, b["terminal_growth"], b["terminal_incremental_roic"],
                                 b["nci"]["capital_consumption_share"])["operating_value"]
    base_t5 = base_t5_op + bridge5
    policy_pv = sum(row["dividend_cash"] / (1.0 + rate) ** row["holding_year"] for row in rows[:5]) + (
        base_t5 / (1.0 + rate) ** 5)
    financial_rate = b["financing"]["deposit_yield"] * (1.0 - b["financing"]["deposit_income_tax"])
    financial_rate_difference = year5_state["surplus_financial"] * (
        (1.0 + financial_rate) ** -5 - (1.0 + rate) ** -5)
    core_values = [results[key]["valuation"]["current_per_share"] for key in ("core_low", "core_high")
                   if results[key]["status"] == "NUMERIC"]
    value_range = {"low": min(core_values), "high": max(core_values), "currency": "CNY"} if core_valid else None
    return_model = {
        "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
        "model_as_of": data["model_as_of"],
        "base_case_distributions_per_share": [row["dividend_per_share"] for row in rows[:5]],
        "base_case_terminal_equity_value_range_per_share": {
            "year_5": {"low": min(terminal_values), "high": max(terminal_values)}}}
    return {"status": "NUMERIC_CANDIDATE" if core_valid else "ECONOMIC_CORE_ENDPOINT_INCOMPLETE",
            "value_range": value_range, "base_current_per_share": base["valuation"]["current_per_share"],
            "valuation_note": "Cash-rental operating DCF plus attributable financial assets/debt and separately valued associates; not price-calibrated.",
            "return_model": return_model,
            "return_model_note": "Same Base actual constrained D1–D5 and year5 financial state. T5 revalues future Base operations with stated terminal parameter range.2077796644 fully diluted ordinary shares; no unannounced capital action.0.40 pending included once, no year5 liquidation or special capital return.",
            "year5_terminal_details": terminal_detail,
            "diagnostics": {"base_policy_pv_at_operating_discount": policy_pv,
                            "base_policy_pv_per_share": policy_pv / shares,
                            "difference_from_standard_operating_dcf": policy_pv - base["valuation"]["current_equity"],
                            "year5_financial_balance_discount_rate_only_difference": financial_rate_difference,
                            "financial_discount_rate_for_diagnostic": financial_rate,
                            "not_automatic_principal_impairment": True,
                            "year5": rows[4], "year6": rows[5],
                            "year10": rows[9], "year11": base["valuation"]["terminal_year11"]},
            "case_value_per_share": {key: result["valuation"]["current_per_share"]
                                     if result["status"] == "NUMERIC" else None for key, result in results.items()},
            "case_statuses": {key: result["status"] for key, result in results.items()},
            "not_independently_verified": True}
