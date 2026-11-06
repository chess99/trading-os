"""CN603338 deterministic research producer. Requires coordinated run permission.

Money is CNY million, shares are million shares, per-share values are CNY.
This file has no network, repository, queue, trade, or Library side effects.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ARRAY_KEYS = (
    "growth", "gross_margin", "operating_cost_ratio", "nwc_revenue_ratio",
    "da_ex_rou", "maintenance_capex", "expansion_capex", "dividends_per_share",
)


def validate_inputs(data: dict) -> None:
    def finite_tree(value):
        if type(value) in (int, float):
            assert math.isfinite(value), "Non-finite numeric input"
        elif isinstance(value, dict):
            for child in value.values():
                finite_tree(child)
        elif isinstance(value, list):
            for child in value:
                finite_tree(child)
    def number(value, low=0.0, high=None):
        assert type(value) in (int, float) and math.isfinite(value)
        assert value >= low
        assert high is None or value <= high
    finite_tree(data)
    assert data["symbol"] == "CN:603338"
    assert data["report_period"] == "2026-Q3"
    assert data["amount_unit"] == "CNY_million"
    assert data["share_unit"] == "million_shares"
    assert data["rate_unit"] == "decimal"
    assert 500 < data["shares"] < 510
    assert 0 < data["common_ownership_proxy"] <= 1
    number(data["shares"], 500, 510)
    number(data["common_ownership_proxy"], 0.000001, 1)
    assert set(data["scenarios"]) == {"structural_pressure", "base", "strong_execution", "cyclical_weak"}
    number(data["discount_rate"], 0.001, 0.5)
    number(data["cash_yield_pretax"], 0, 0.20)
    number(data["bank_interest_pretax"], 0, 0.30)
    number(data["terminal_da_revenue_ratio"], 0.001, 0.20)
    for value in data["historical"].values():
        number(value)
    for key, value in data["anchor"].items():
        if key == "balance_date":
            continue
        if isinstance(value, dict):
            for amount in value.values():
                number(amount)
        else:
            number(value)
    for key, value in data["parent"].items():
        if key != "balance_date":
            number(value)
        if key.endswith("fraction"):
            number(value, 0, 1.5)
    number(data["parent"]["further_statutory_transfer_rate"], 0, 1)
    for scenario in data["scenarios"].values():
        for key in ARRAY_KEYS:
            value = scenario[key]
            assert isinstance(value, list) and len(value) == 5, key
            assert all(type(x) in (int, float) and math.isfinite(x) for x in value), key
        assert all(-0.25 < x < 0.30 for x in scenario["growth"])
        assert all(0 < x < 0.60 for x in scenario["gross_margin"])
        assert all(0 < x < 0.25 for x in scenario["operating_cost_ratio"])
        assert all(0.25 < x < 0.80 for x in scenario["nwc_revenue_ratio"])
        assert all(x >= 0 for key in ARRAY_KEYS[4:] for x in scenario[key])
        assert data["discount_rate"] > scenario["terminal_growth"] >= 0
        assert 0 < scenario["terminal_incremental_roic"] < 0.50
        number(scenario["transition_start_incremental_roic"], 0.001, 0.50)
        number(scenario["terminal_incremental_roic"], 0.001, 0.50)
        number(scenario["terminal_growth"], 0, 0.10)
        assert all(x > 0 for x in scenario["da_ex_rou"])
        for key in ("tax_rate", "terminal_tax_rate", "terminal_ebit_margin", "terminal_nwc_ratio", "epv_ebit_margin"):
            number(scenario[key], 0, 0.99)
        number(scenario["additional_historical_net_loss"])
        number(scenario["parent_settlement_delay"])
        number(scenario["terminal_maintenance_multiple"], 1, 2)


def opening_bridge(data: dict, scenario: dict) -> dict:
    anchor = data["anchor"]
    history = data["historical"]
    revenue = history["revenue_fy2025"] + history["revenue_9m2026"] - history["revenue_9m2025"]
    current_bank = (anchor["current_noncurrent_liabilities"]
                    - anchor["current_lease_proxy"] - anchor["current_warranty_proxy"])
    assert current_bank >= 0
    bank_debt = anchor["short_bank_debt"] + anchor["long_bank_debt"] + current_bank
    financial_assets = sum(anchor["financial_assets"].values())
    operating_assets = sum(anchor["operating_assets"].values()) + anchor["operating_cash"]
    operating_liabilities = (sum(anchor["operating_liabilities"].values())
                             - anchor["capex_payable_proxy_included_in_future_capex"]
                             + anchor["current_warranty_proxy"] + anchor["noncurrent_warranty"])
    nwc = operating_assets - operating_liabilities
    pre_loss_nfa = (financial_assets - bank_debt - anchor["operating_cash"]
                    - anchor["tax_payables_excluded_from_nwc"])
    group_nfa = pre_loss_nfa - scenario["additional_historical_net_loss"]
    factor = data["common_ownership_proxy"]
    return {
        "revenue_ltm": revenue,
        "financial_assets": financial_assets,
        "bank_debt": bank_debt,
        "current_bank_debt_proxy": current_bank,
        "nwc": nwc,
        "nwc_revenue_ratio": nwc / revenue,
        "pre_additional_loss_group_nfa": pre_loss_nfa,
        "group_nfa": group_nfa,
        "common_nfa": group_nfa * factor,
        "common_bank_debt": bank_debt * factor,
        "ownership_factor": factor,
    }


def interpolate(start: float, end: float, weight: float) -> float:
    return start + (end - start) * weight


def capital_plan(data: dict, reference: dict) -> dict:
    """Normal capacity budget; never recomputed from a cash-collection/margin shock.

    Reference ROIC constrains a normal capital plan only. A replacement floor
    protects productive assets. Actual NWC and actual profitability are separate.
    """
    opening = opening_bridge(data, reference)
    revenue = opening["revenue_ltm"]
    for growth in reference["growth"]:
        revenue *= 1 + growth
    y5_revenue = revenue
    nwc = revenue * reference["nwc_revenue_ratio"][-1]
    y5_margin = reference["gross_margin"][-1] - reference["operating_cost_ratio"][-1]
    initial_maintenance_multiple = max(1.0, reference["maintenance_capex"][-1] / reference["da_ex_rou"][-1])
    result = {}
    for year in range(6, 12):
        weight = min((year - 5) / 5, 1.0)
        roic_weight = min((year - 6) / 4, 1.0)
        growth = interpolate(reference["growth"][-1], reference["terminal_growth"], weight)
        margin = interpolate(y5_margin, reference["terminal_ebit_margin"], weight)
        tax = interpolate(reference["tax_rate"], reference["terminal_tax_rate"], weight)
        ratio = interpolate(reference["nwc_revenue_ratio"][-1], reference["terminal_nwc_ratio"], weight)
        roic = interpolate(reference["transition_start_incremental_roic"], reference["terminal_incremental_roic"], roic_weight)
        revenue *= 1 + growth
        nopat = revenue * margin * (1 - tax)
        next_nwc = revenue * ratio
        depreciation = revenue * interpolate(reference["da_ex_rou"][-1] / y5_revenue, data["terminal_da_revenue_ratio"], weight)
        normal_total_reinvestment = nopat * growth / roic
        unconstrained_capex = depreciation + normal_total_reinvestment - (next_nwc - nwc)
        maintenance_multiple = interpolate(initial_maintenance_multiple, reference["terminal_maintenance_multiple"], weight)
        maintenance_floor = depreciation * maintenance_multiple
        cash_capex = max(unconstrained_capex, maintenance_floor)
        result[year] = {"cash_capex": cash_capex, "maintenance_floor": maintenance_floor,
                        "unconstrained_capex": unconstrained_capex,
                        "maintenance_floor_binding": unconstrained_capex < maintenance_floor,
                        "reference_normal_nwc": next_nwc, "reference_roic": roic}
        nwc = next_nwc
    return result


def project(data: dict, scenario: dict, discount_rate: float | None = None,
            capital_reference: dict | None = None) -> dict:
    rate = data["discount_rate"] if discount_rate is None else discount_rate
    assert rate > scenario["terminal_growth"]
    opening = opening_bridge(data, scenario)
    reference = scenario if capital_reference is None else capital_reference
    fixed_capital_plan = capital_plan(data, reference)
    revenue, nwc = opening["revenue_ltm"], opening["nwc"]
    rows = []
    for index in range(5):
        revenue *= 1 + scenario["growth"][index]
        margin = scenario["gross_margin"][index] - scenario["operating_cost_ratio"][index]
        tax = scenario["tax_rate"]
        nopat = revenue * margin * (1 - tax)
        closing_nwc = revenue * scenario["nwc_revenue_ratio"][index]
        change_nwc = closing_nwc - nwc
        depreciation = scenario["da_ex_rou"][index]
        capex = scenario["maintenance_capex"][index] + scenario["expansion_capex"][index]
        net_reinvestment = capex - depreciation + change_nwc
        fcff = nopat - net_reinvestment
        rows.append({
            "year": index + 1, "revenue": revenue,
            "growth": scenario["growth"][index], "ebit_margin": margin,
            "tax_rate": tax, "nopat": nopat, "da_ex_rou": depreciation,
            "cash_capex": capex, "nwc": closing_nwc, "change_nwc": change_nwc,
            "net_reinvestment": net_reinvestment, "fcff": fcff,
            "dividend_per_share": scenario["dividends_per_share"][index],
        })
        nwc = closing_nwc
    y5 = rows[-1]
    for year in range(6, 12):
        weight = min((year - 5) / 5, 1.0)
        roic_weight = min((year - 6) / 4, 1.0)
        growth = interpolate(y5["growth"], scenario["terminal_growth"], weight)
        margin = interpolate(y5["ebit_margin"], scenario["terminal_ebit_margin"], weight)
        tax = interpolate(scenario["tax_rate"], scenario["terminal_tax_rate"], weight)
        nwc_ratio = interpolate(scenario["nwc_revenue_ratio"][-1], scenario["terminal_nwc_ratio"], weight)
        roic = interpolate(scenario["transition_start_incremental_roic"],
                           scenario["terminal_incremental_roic"], roic_weight)
        revenue *= 1 + growth
        nopat = revenue * margin * (1 - tax)
        closing_nwc = revenue * nwc_ratio
        change_nwc = closing_nwc - nwc
        depreciation_ratio = interpolate(y5["da_ex_rou"] / y5["revenue"],
                                         data["terminal_da_revenue_ratio"], weight)
        depreciation = depreciation_ratio * revenue
        capex = fixed_capital_plan[year]["cash_capex"]
        net_reinvestment = capex - depreciation + change_nwc
        assert capex >= 0, "Transition implies negative cash capex; reconsider economics"
        rows.append({
            "year": year, "revenue": revenue, "growth": growth,
            "ebit_margin": margin, "tax_rate": tax, "nopat": nopat,
            "da_ex_rou": depreciation, "cash_capex": capex,
            "nwc": closing_nwc, "change_nwc": change_nwc,
            "net_reinvestment": net_reinvestment,
            "reference_incremental_roic": roic,
            "growth_equivalent_capital_return": nopat * growth / net_reinvestment if net_reinvestment > 0 else None,
            "fixed_capital_plan": fixed_capital_plan[year],
            "fcff": nopat - net_reinvestment,
        })
        nwc = closing_nwc
    terminal_value_y10 = rows[10]["fcff"] / (rate - scenario["terminal_growth"])
    enterprise_value = sum(row["fcff"] / (1 + rate) ** row["year"] for row in rows[:10])
    enterprise_value += terminal_value_y10 / (1 + rate) ** 10
    enterprise_value_y5 = sum(row["fcff"] / (1 + rate) ** (row["year"] - 5) for row in rows[5:10])
    enterprise_value_y5 += terminal_value_y10 / (1 + rate) ** 5
    factor = opening["ownership_factor"]
    common_nfa = opening["common_nfa"]
    parent = data["parent"]
    parent_cash = (parent["cash"] - data["anchor"]["tax_payables_excluded_from_nwc"]
                   - scenario["additional_historical_net_loss"] - scenario["parent_settlement_delay"])
    parent_re = parent["retained_earnings"] - scenario["additional_historical_net_loss"]
    initial_parent_cash = parent_cash
    minimum_parent_cash = parent_cash
    minimum_parent_re = parent_re
    funding_feasible = True
    funding_gap = 0.0
    for row in rows[:5]:
        opening_nfa = common_nfa
        interest_earning_assets = common_nfa + opening["common_bank_debt"]
        if interest_earning_assets < 0:
            funding_feasible = False
            funding_gap = max(funding_gap, -interest_earning_assets)
            break
        net_financial_return = (
            interest_earning_assets * data["cash_yield_pretax"]
            - opening["common_bank_debt"] * data["bank_interest_pretax"]
        ) * (1 - row["tax_rate"])
        common_dividend = row["dividend_per_share"] * data["shares"]
        common_fcff = row["fcff"] * factor
        common_nfa += common_fcff + net_financial_return - common_dividend
        closing_financial_assets = common_nfa + opening["common_bank_debt"]
        if closing_financial_assets < 0:
            funding_feasible = False
            funding_gap = max(funding_gap, -closing_financial_assets)
        parent_cash_before_dividend = (
            parent_cash + row["nopat"] * parent["nopat_fraction"]
            + row["da_ex_rou"] * parent["da_fraction"]
            - row["cash_capex"] * parent["capex_fraction"]
            - row["change_nwc"] * parent["working_capital_fraction"]
            + net_financial_return * parent["financial_return_fraction"]
        )
        parent_net_profit = (row["nopat"] * parent["nopat_fraction"]
                            + net_financial_return * parent["financial_return_fraction"])
        parent_statutory_transfer = max(parent_net_profit, 0) * parent["further_statutory_transfer_rate"]
        parent_re += parent_net_profit - parent_statutory_transfer - common_dividend
        parent_cash = parent_cash_before_dividend - common_dividend
        minimum_parent_cash = min(minimum_parent_cash, parent_cash)
        minimum_parent_re = min(minimum_parent_re, parent_re)
        common_profit = row["nopat"] * factor + net_financial_return
        row.update({
            "common_fcff": common_fcff, "common_profit": common_profit,
            "common_dividend": common_dividend,
            "dividend_payout_ratio": common_dividend / common_profit,
            "opening_common_nfa": opening_nfa, "common_nfa": common_nfa,
            "net_financial_return": net_financial_return,
            "parent_cash_before_dividend": parent_cash_before_dividend,
            "parent_cash_budget": parent_cash, "parent_net_profit_budget": parent_net_profit,
            "parent_retained_earnings_budget": parent_re,
            "parent_statutory_transfer": parent_statutory_transfer,
            "closing_interest_earning_assets": closing_financial_assets,
            "cash_conservation_residual": common_nfa - opening_nfa - common_fcff
                                          - net_financial_return + common_dividend,
        })
        if not funding_feasible:
            break
    equity_value = enterprise_value * factor + opening["common_nfa"]
    terminal_equity_y5 = enterprise_value_y5 * factor + common_nfa
    price_y5 = terminal_equity_y5 / data["shares"]
    holder_pv = sum(row["dividend_per_share"] / (1 + rate) ** row["year"] for row in rows[:5])
    holder_pv += price_y5 / (1 + rate) ** 5
    distribution_feasible = (funding_feasible and minimum_parent_cash >= parent["minimum_cash"]
                             and minimum_parent_re >= 0 and len([x for x in rows[:5] if "common_nfa" in x]) == 5)
    valuation_usable = distribution_feasible and equity_value > 0 and terminal_equity_y5 > 0
    epv_nopat = opening["revenue_ltm"] * scenario["epv_ebit_margin"] * (1 - scenario["tax_rate"])
    epv_operating_value = (epv_nopat - 50.0) / rate
    epv_per_share = (epv_operating_value * factor + opening["common_nfa"]) / data["shares"]
    q3_revenue = data["historical"]["revenue_9m2026"] - data["historical"]["revenue_h12026"]
    q3_cogs = data["historical"]["cogs_9m2026"] - data["historical"]["cogs_h12026"]
    return {
        "label": scenario["label"], "discount_rate": rate, "opening": opening,
        "rows": rows, "enterprise_value": enterprise_value,
        "equity_value": equity_value, "value_per_share": equity_value / data["shares"],
        "enterprise_value_y5": enterprise_value_y5, "terminal_value_y10": terminal_value_y10,
        "terminal_equity_y5": terminal_equity_y5 if distribution_feasible else None,
        "terminal_price_y5": price_y5 if distribution_feasible else None,
        "common_nfa_y5": common_nfa if funding_feasible else None,
        "holder_cash_flow_pv_per_share": holder_pv if distribution_feasible else None,
        "retention_time_cost_per_share": equity_value / data["shares"] - holder_pv if distribution_feasible else None,
        "valuation_usable": valuation_usable, "distribution_feasible": distribution_feasible,
        "funding_feasible": funding_feasible, "funding_gap": funding_gap,
        "epv_per_share": epv_per_share, "epv_nopat": epv_nopat,
        "q3_gross_margin": 1 - q3_cogs / q3_revenue,
        "parent_initial_available_cash_budget": initial_parent_cash,
        "minimum_parent_cash_budget": minimum_parent_cash,
        "minimum_parent_re_budget": minimum_parent_re,
        "parent_cash_feasible": minimum_parent_cash >= parent["minimum_cash"],
        "parent_re_feasible": minimum_parent_re >= 0,
        "terminal_pv_fraction_of_operating_value": terminal_value_y10 / (1 + rate) ** 10 / enterprise_value,
    }


def build_results(data: dict) -> dict:
    validate_inputs(data)
    main = {name: project(data, scenario) for name, scenario in data["scenarios"].items()}
    base = data["scenarios"]["base"]
    sensitivities = []
    for rate in (0.09, 0.115):
        result = project(data, base, rate)
        sensitivities.append({"variable": "discount_rate", "input": rate,
                              "value_per_share": result["value_per_share"]})
    for loss in (0, 500, 1500, 3000):
        scenario = copy.deepcopy(base)
        scenario["additional_historical_net_loss"] = loss
        result = project(data, scenario)
        sensitivities.append({"variable": "additional_historical_net_loss", "input": loss,
                              "value_per_share": result["value_per_share"],
                              "parent_cash_feasible": result["parent_cash_feasible"]})
    for change in (-500, 500):
        scenario = copy.deepcopy(base)
        scenario["expansion_capex"][0] += change / 2
        scenario["expansion_capex"][1] += change / 2
        assert min(scenario["expansion_capex"]) >= 0
        result = project(data, scenario)
        sensitivities.append({"variable": "remaining_project_capex", "input_change": change,
                              "value_per_share": result["value_per_share"]})
    scenario = copy.deepcopy(base)
    scenario["gross_margin"] = [x - 0.02 for x in scenario["gross_margin"]]
    scenario["terminal_ebit_margin"] -= 0.02
    result = project(data, scenario, capital_reference=base)
    sensitivities.append({"variable": "persistent_operating_margin", "input_change": -0.02,
                          "value_per_share": result["value_per_share"],
                          "capital_plan_held_at_base": True})
    scenario = copy.deepcopy(base)
    scenario["nwc_revenue_ratio"] = [x + 0.05 for x in scenario["nwc_revenue_ratio"]]
    scenario["terminal_nwc_ratio"] += 0.05
    result = project(data, scenario, capital_reference=base)
    sensitivities.append({"variable": "nwc_revenue_ratio", "input_change": 0.05,
                          "value_per_share": result["value_per_share"],
                          "capital_plan_held_at_base": True,
                          "transition_rows": [{k: row[k] for k in ("year", "cash_capex", "change_nwc", "net_reinvestment", "fcff")} for row in result["rows"][5:]]})
    for current_lease, current_warranty in ((20, 60), (26, 100)):
        changed = copy.deepcopy(data)
        changed["anchor"]["current_lease_proxy"] = current_lease
        changed["anchor"]["current_warranty_proxy"] = current_warranty
        result = project(changed, base)
        sensitivities.append({"variable": "current_debt_split", "lease": current_lease,
                              "warranty": current_warranty,
                              "value_per_share": result["value_per_share"]})
    values = [x["value_per_share"] for x in main.values()]
    core_specs = {
        "lower": {"label": "采纳路径合理下端", "growth": [0.07, 0.07, 0.06, 0.05, 0.04],
                  "gross_margin": [0.285, 0.29, 0.295, 0.295, 0.295],
                  "nwc_revenue_ratio": [0.555, 0.55, 0.545, 0.54, 0.535],
                  "expansion_capex": [450, 350, 100, 0, 0],
                  "terminal_growth": 0.02, "terminal_ebit_margin": 0.175,
                  "terminal_nwc_ratio": 0.52, "additional_historical_net_loss": 500.0,
                  "parent_settlement_delay": 500.0},
        "upper": {"label": "采纳路径合理上端", "growth": [0.09, 0.09, 0.08, 0.07, 0.06],
                  "gross_margin": [0.305, 0.31, 0.315, 0.315, 0.315],
                  "nwc_revenue_ratio": [0.525, 0.52, 0.515, 0.51, 0.505],
                  "expansion_capex": [450, 350, 100, 0, 0],
                  "terminal_growth": 0.025, "terminal_ebit_margin": 0.195,
                  "terminal_nwc_ratio": 0.49, "additional_historical_net_loss": 0.0},
    }
    core_results = {}
    for name, changes in core_specs.items():
        scenario = copy.deepcopy(base)
        scenario.update(changes)
        reference = copy.deepcopy(base)
        reference["growth"] = copy.deepcopy(scenario["growth"])
        reference["terminal_growth"] = scenario["terminal_growth"]
        reference["expansion_capex"] = copy.deepcopy(scenario["expansion_capex"])
        core_results[name] = project(data, scenario, capital_reference=reference)
    terminal_results = {}
    for name, target_margin, target_nwc, target_growth in (("lower", 0.175, 0.52, 0.02), ("upper", 0.195, 0.49, 0.025)):
        scenario = copy.deepcopy(base)
        scenario["terminal_ebit_margin"] = target_margin
        scenario["terminal_nwc_ratio"] = target_nwc
        scenario["terminal_growth"] = target_growth
        reference = copy.deepcopy(base)
        reference["terminal_growth"] = target_growth
        terminal_results[name] = project(data, scenario, capital_reference=reference)
    core_valid = all(x["valuation_usable"] for x in core_results.values()) and main["base"]["valuation_usable"]
    terminal_valid = all(x["distribution_feasible"] for x in terminal_results.values())
    core_range = [core_results["lower"]["value_per_share"], core_results["upper"]["value_per_share"]] if core_valid else None
    terminal_range = [terminal_results["lower"]["terminal_price_y5"], terminal_results["upper"]["terminal_price_y5"]] if terminal_valid else None
    if core_valid:
        assert core_range[0] <= main["base"]["value_per_share"] <= core_range[1], "Core endpoint semantics failed"
    if terminal_valid:
        assert terminal_range[0] <= main["base"]["terminal_price_y5"] <= terminal_range[1]
    return {"symbol": data["symbol"], "report_period": data["report_period"],
            "units": {"money": "CNY_million", "per_share": "CNY", "rates": "decimal"},
            "scenarios": main, "sensitivities": sensitivities,
            "diagnostic_scenario_span_not_core": [min(values), max(values)],
            "core_endpoint_specs": core_specs, "core_endpoints": core_results,
            "core_value_range": core_range, "core_usable": core_valid,
            "base_terminal_endpoint_paths": terminal_results,
            "base_y5_terminal_value_range": terminal_range,
            "no_market_price_or_irr_used": True}


def render_bridge(results: dict) -> str:
    lines = ["# 经营、现金与期末权益计算", "", "金额：百万元人民币；每股：元。", ""]
    for result in results["scenarios"].values():
        lines += ["## " + result["label"], "",
                  "| 年 | 收入 | EBIT率 | NOPAT | 折旧 | capex | ΔNWC | FCFF | D/股 | 普通股NFA | 母体现金预算 | 母体RE预算 |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for row in result["rows"]:
            fields = [str(row["year"]), f'{row["revenue"]:.2f}', f'{row["ebit_margin"]:.2%}',
                      f'{row["nopat"]:.2f}', f'{row["da_ex_rou"]:.2f}', f'{row["cash_capex"]:.2f}',
                      f'{row["change_nwc"]:.2f}', f'{row["fcff"]:.2f}']
            for key in ("dividend_per_share", "common_nfa", "parent_cash_budget", "parent_retained_earnings_budget"):
                fields.append(f'{row[key]:.2f}' if key in row else "—")
            lines.append("| " + " | ".join(fields) + " |")
        def fmt(value):
            return "不可采用：资金或分配约束未满足" if value is None else f"{value:.4f}"
        lines += ["", f'经营资产主法当前每股 {result["value_per_share"]:.4f}；无增长收益价值 {result["epv_per_share"]:.4f}；',
                  f'Y5独立每股权益 {fmt(result["terminal_price_y5"])}；普通分红持有路径折现值 {fmt(result["holder_cash_flow_pv_per_share"])}。',
                  f'资金可行 {result["funding_feasible"]}；实际分配可行 {result["distribution_feasible"]}；可采用 {result["valuation_usable"]}。', ""]
    return "\n".join(lines) + "\n"
