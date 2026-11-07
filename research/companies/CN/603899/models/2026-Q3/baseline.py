#!/usr/bin/env python3
'603899 finite operating/capital model. Ordinary offline CLI, standard library only. All money is RMB 100 million; no coordinator admission ticket is required.'
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime, timezone

SEGMENTS = ("core", "colipu", "retail")
EPS = 1e-8
FUNDING_LABELS = {
    "PARENT_INTERNAL_SETTLEMENT_SHORTFALL":"母体内部结算资金不足",
    "PARENT_ASSUMED_BUFFER_SHORTFALL":"母体自定流动性缓冲不足",
    "GROUP_ASSUMED_BUFFER_SHORTFALL":"集团自定流动性缓冲不足",
    "GROUP_OPERATING_FINANCING_GAP":"经营投入存在实际融资缺口",
    "PARENT_OPERATING_OR_CAPITAL_ACTION_FUNDING_GAP":"母体经营或资本动作缺少已落实资金"
}


def merge(base, changes):
    result = copy.deepcopy(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def case_config(inputs, name):
    return merge(inputs["base"], inputs["cases"][name]["changes"])


def series_value(values, year):
    return values[min(year - 1, len(values) - 1)]


def faded(values, terminal, year):
    if year <= 5:
        return series_value(values, year)
    return values[-1] + (terminal - values[-1]) * min((year - 5) / 5, 1.0)


def step_segment(state, p, *, growth, margin, grant, tax_rate, nwc_ratio, extra_capex, recovery, replacement_payroll_ratio=0.0):
    """The formal operating engine, also used by independently hand-computable fixtures."""
    revenue = state["revenue"] * (1 + growth)
    assert revenue >= 0
    rd = revenue * p["rd_ratio"]
    rent = revenue * p["rent_ratio"]
    da = revenue * p["da_ratio"]
    replacement_payroll = revenue * replacement_payroll_ratio
    ebit = revenue * margin - rd - rent - da + grant - replacement_payroll
    tax = max(ebit, 0.0) * tax_rate  # no instantaneous refund on losses
    nopat = ebit - tax
    maintenance = da                # explicit physical/intangible maintenance, ROU excluded
    growth_fixed = max(revenue - state["revenue"], 0) / p["growth_fixed_turnover"]
    new_nwc = revenue * nwc_ratio
    delta_nwc = new_nwc - state["nwc"]
    cash_nwc = delta_nwc if delta_nwc >= 0 else delta_nwc * recovery
    new_cash = revenue * p["cash_ratio"]
    delta_cash = new_cash - state["cash"]
    investment_cash = maintenance - da + growth_fixed + extra_capex + cash_nwc + delta_cash
    fcff = nopat - investment_cash
    fixed = state["fixed"] + growth_fixed + extra_capex
    output = {
        "revenue": revenue, "growth": growth, "ebitdar_margin": margin,
        "research_expense_cash": rd, "cash_rent": rent,
        "post_plan_staff_compensation_cash": replacement_payroll, "non_rou_depreciation": da,
        "ebit_after_rent": ebit, "tax_rate": tax_rate, "tax": tax, "nopat": nopat,
        "common_grant_nopat": grant * (1 - tax_rate) * p["ownership"],
        "maintenance_capex": maintenance, "growth_fixed_capex": growth_fixed,
        "upgrade_capex": extra_capex, "nwc": new_nwc, "delta_nwc": delta_nwc,
        "nwc_cash_investment": cash_nwc,
        "nwc_release_unrecovered": max(-delta_nwc, 0) * (1 - recovery),
        "operating_cash": new_cash, "delta_operating_cash": delta_cash,
        "fixed_capital": fixed, "total_operating_capital": fixed + new_nwc + new_cash,
        "investment_cash_net_of_da": investment_cash, "fcff": fcff,
        "common_nopat": nopat * p["ownership"], "common_fcff": fcff * p["ownership"],
        "common_capital": (fixed + new_nwc + new_cash) * p["ownership"]
    }
    assert abs(fcff - (nopat + da - maintenance - growth_fixed - extra_capex - cash_nwc - delta_cash)) < EPS
    return {"revenue": revenue, "fixed": fixed, "nwc": new_nwc, "cash": new_cash}, output


def operating_path(inputs, config):
    states = {s: {"revenue": p["revenue"], "fixed": p["fixed_capital"],
                  "nwc": p["revenue"] * p["nwc_ratio"],
                  "cash": p["revenue"] * p["cash_ratio"]}
              for s, p in inputs["opening"]["segments"].items()}
    rows = []
    for year in range(1, 12):
        out = {"year": year, "segments": {}}
        for s in SEGMENTS:
            p = inputs["opening"]["segments"][s]
            g = faded(config["growth"][s], config["terminal_growth"][s], year)
            margin = faded(config["ebitdar_margin"][s], config["terminal_ebitdar_margin"][s], year)
            parent_tax = series_value(config["parent_tax"], year)
            tax = (inputs["opening"]["parent_core_pretax_fraction"] * parent_tax
                   + (1 - inputs["opening"]["parent_core_pretax_fraction"]) * config["subsidiary_tax"]) if s == "core" else config["subsidiary_tax"]
            states[s], out["segments"][s] = step_segment(
                states[s], p, growth=g, margin=margin,
                grant=series_value(config["core_grant"], year) if s == "core" else 0,
                tax_rate=tax, nwc_ratio=series_value(config["nwc_ratio"][s], year),
                extra_capex=series_value(config["retail_upgrade_capex"], year) if s == "retail" and year <= 5 else 0,
                recovery=config["working_capital_release_fraction"],
                replacement_payroll_ratio=(config["post_plan_replacement_payroll_base"] / p["revenue"]) if s == "core" and year > 5 else 0.0)
        out["common_fcff"] = sum(v["common_fcff"] for v in out["segments"].values())
        out["common_nopat"] = sum(v["common_nopat"] for v in out["segments"].values())
        out["external_revenue_proxy"] = sum(v["revenue"] for v in out["segments"].values())
        rows.append(out)
    return rows


def cash_ownership_bridge(inputs, config):
    """ONE asset classification for primary/auxiliary; no free-standing NCI haircut."""
    p = inputs["opening"]["segments"]["colipu"]
    common = p["ownership"]
    operating = p["revenue"] * p["cash_ratio"]
    seasonal_total = config["seasonal_cash_common"] / common
    excess = config["colipu_excess_cash"]
    gross = operating + seasonal_total + excess
    colipu_nci = gross * (1 - common)
    other_nci = config["other_nci_financial_assets"]
    group_assets = inputs["history"]["q3"]["cash"] + inputs["history"]["q3"]["trading_financial_assets"]
    assert excess >= 0 and other_nci >= 0
    assert gross + inputs["opening"]["parent_liquid_proxy"] <= group_assets + EPS
    assert abs(gross * common + colipu_nci - gross) < EPS
    assert abs(operating * common + config["seasonal_cash_common"] + excess * common - gross * common) < EPS
    return {"colipu_operating_cash_total": operating, "colipu_seasonal_cash_total": seasonal_total,
            "colipu_excess_cash_total": excess, "colipu_gross_financial_assets_total": gross,
            "colipu_common_financial_assets": gross * common,
            "colipu_nci_financial_assets": colipu_nci, "other_nci_financial_assets": other_nci,
            "group_nci_financial_assets": colipu_nci + other_nci,
            "remaining_group_assets_after_colipu_and_parent_proxy": group_assets - gross - inputs["opening"]["parent_liquid_proxy"],
            "classification": "Same gross cash, required operating/seasonal cash and excess cash in both methods; all seasonal buffer allocated to Colipu; other NCI rights nonnegative."}


def opening_bridge(inputs, config):
    h = inputs["history"]
    q = h["q3"]
    ownership = cash_ownership_bridge(inputs, config)
    group_assets = q["cash"] + q["trading_financial_assets"]
    known_after_q3_buyback = q["buyback_spend_oct15"] - q["buyback_spend_sep"]
    operating_cash = sum(p["revenue"] * p["cash_ratio"] * p["ownership"]
                         for p in inputs["opening"]["segments"].values())
    reserve = operating_cash + config["seasonal_cash_common"] + config["restricted_operating_cash"]
    free = group_assets - known_after_q3_buyback - ownership["group_nci_financial_assets"] - config["common_debt"] - reserve
    return {
        "group_financial_assets_q3": group_assets, "cash_ownership_classification": ownership,
        "known_post_q3_treasury_purchase": known_after_q3_buyback,
        "noncommon_financial_assets_estimate": ownership["group_nci_financial_assets"],
        "common_bank_debt_deducted": config["common_debt"],
        "operating_cash_already_capitalised": operating_cash,
        "seasonal_buffer_common": config["seasonal_cash_common"],
        "restricted_cash_in_operating_capital": config["restricted_operating_cash"],
        "total_required_common_cash": reserve,
        "group_buffer_mobilisation_upper_bound": reserve - config["restricted_operating_cash"],
        "opening_excess_net_financial_assets": free,
        "other_nonoperating_investments_value": q["other_investments_book"] * config["other_investments_recovery"],
        "lease_debt_deducted": 0.0,
        "lease_reason": "Full cash rent expensed in operating earnings every year, so no second lease principal deduction.",
        "remaining_employee_buyback": config["buyback_total_plan"] - q["buyback_spend_oct15"],
        "parent_free_liquidity_proxy": inputs["opening"]["parent_liquid_proxy"] - inputs["opening"]["parent_required_liquid"]
    }


def funding_state(parent_cash, group_cash, *, parent_buffer=0, group_buffer=0,
                  parent_before_internal_settlement=None):
    """Classify available EXTRA cash versus policy reserves; never create financing.
    Reserve amounts are an upper-bound diagnostic, not permission to spend them.
    Parent-only trouble does not prove consolidated operating EV is destroyed.
    """
    parent_before = parent_cash if parent_before_internal_settlement is None else parent_before_internal_settlement
    group_upper = group_cash + group_buffer
    parent_upper = parent_cash + parent_buffer
    issues = []
    if group_upper < -EPS:
        issues.append("GROUP_OPERATING_FINANCING_GAP")
    elif group_cash < -EPS:
        issues.append("GROUP_ASSUMED_BUFFER_SHORTFALL")
    if parent_cash < -EPS:
        if parent_before >= -EPS:
            issues.append("PARENT_INTERNAL_SETTLEMENT_SHORTFALL")
        elif parent_before + parent_buffer < -EPS:
            issues.append("PARENT_OPERATING_OR_CAPITAL_ACTION_FUNDING_GAP")
        else:
            issues.append("PARENT_ASSUMED_BUFFER_SHORTFALL")
    ready = not issues
    true_gap = any(x in issues for x in ("GROUP_OPERATING_FINANCING_GAP", "PARENT_OPERATING_OR_CAPITAL_ACTION_FUNDING_GAP"))
    if ready:
        operating_status = "SUPPORTED"
        reason = "普通分配前，经营投入、研究缓冲与计划结算均已具备资金。"
    elif true_gap:
        operating_status = "CONDITIONAL_UNFUNDED_OPERATING_OR_CAPITAL_ACTION_PATH"
        reason = "即使按可移动缓冲上界检验，现有经营投入或资本动作仍有资金缺口；融资或行动调整尚未落实，不假设免费资金。"
    elif "GROUP_ASSUMED_BUFFER_SHORTFALL" in issues:
        operating_status = "CONDITIONAL_ON_EXPLICIT_BUFFER_RELAXATION"
        reason = "未显示集团总资金必然不足，但既定运行及季节性缓冲未达到；需先明确缓冲调整与重建安排，不能把条件诊断直接当作已闭合价值。"
    else:
        operating_status = "GROUP_OPERATING_EV_NOT_INVALIDATED_BY_PARENT_LIQUIDITY"
        reason = "母体结算或自定流动性安排未具备资金。这本身不否定集团经营EV，但实际付款时点及可动用资产仍有条件。"
    return {"classification": issues[0] if issues else "FUNDED_BEFORE_D", "all_issues": issues,
            "payment_path_ready": ready, "true_operating_or_capital_action_financing_gap": true_gap,
            "operating_value_status": operating_status, "reason": reason,
            "group_extra_cash": group_cash, "group_cash_upper_bound_including_movable_buffer": group_upper,
            "group_gross_financing_shortfall": max(-group_upper,0),
            "group_policy_buffer_shortfall": max(-group_cash,0),
            "parent_extra_cash": parent_cash, "parent_cash_upper_bound_including_buffer": parent_upper,
            "parent_before_internal_settlement": parent_before,
            "parent_internal_settlement_shortfall": max(-parent_cash,0) if parent_before >= -EPS else 0,
            "buffer_draw_assumed": False, "new_financing_assumed": False}


def distribute(parent_cash, group_cash, retained, parent_profit, group_profit, payout,
               *, parent_buffer=0, group_buffer=0, parent_before_internal_settlement=None):
    """Formal payment gate. D limitation is distinct from an unresolved funding path."""
    requested = max(group_profit, 0) * payout
    legal = max(retained + parent_profit, 0)
    funding = funding_state(parent_cash, group_cash, parent_buffer=parent_buffer,
                            group_buffer=group_buffer, parent_before_internal_settlement=parent_before_internal_settlement)
    if not funding["payment_path_ready"]:
        return {"feasible": False, "requested": requested, "paid": None,
                "funding_state": funding, "reason": funding["reason"]}
    paid = min(requested, legal, max(parent_cash, 0), max(group_cash, 0))
    constrained = paid + EPS < requested
    return {"feasible": True, "requested": requested, "paid": paid,
            "classification": "ORDINARY_D_CONSTRAINED" if constrained else "ORDINARY_D_PAID_AS_BUDGETED",
            "funding_state": funding, "legal_capacity": legal, "parent_cash_capacity": parent_cash,
            "group_cash_capacity": group_cash, "constrained": constrained,
            "parent_cash_after": parent_cash - paid, "group_cash_after": group_cash - paid,
            "retained_after": retained + parent_profit - paid}


def valuation_acceptance(ledger, diagnostic_equity, future_equity, shares):
    """Formal contract != conditional business valuation. No parameter rescue or zero-cost finance."""
    supported = ledger["feasible"]
    issue = ledger.get("funding_state")
    return {"current_equity_contract_eligible": supported, "holder_contract_eligible": supported,
            "current_value_per_share": diagnostic_equity / shares if supported else None,
            "conditional_equity_diagnostic_per_share": diagnostic_equity / shares,
            "year5_equity_per_share": future_equity / shares if supported and future_equity is not None else None,
            "operating_value_status": "SUPPORTED" if supported else issue["operating_value_status"],
            "contract_status": "ACCEPTABLE_FUNDING_PATH" if supported else "CONDITIONAL_NOT_FORMAL_CONTRACT",
            "reason": "普通D下调已联动留存现金，不因此否定经营EV。" if supported else issue["reason"],
            "no_automatic_ev_writeoff": True}


def contract_readiness(low, high, base):
    return {"value_range":all(x["current_equity_contract_eligible"] for x in (low,base,high)),
            "return_model":base["holder_contract_eligible"]}


def holder_ledger(inputs, config, rows, bridge):
    o = inputs["opening"]
    free = bridge["opening_excess_net_financial_assets"]
    parent_free = bridge["parent_free_liquidity_proxy"]
    retained = o["parent_retained_earnings_floor"]
    ledger = []
    initial = funding_state(parent_free, free, parent_buffer=o["parent_required_liquid"],
                            group_buffer=bridge["group_buffer_mobilisation_upper_bound"])
    if not initial["payment_path_ready"]:
        return {"feasible":False,"ledger":ledger,"funding_state":initial,"reason":initial["reason"],"failure_year":0}
    grant = config["buyback_total_plan"] / config["employee_grant_years"]
    for year in range(1, 6):
        row = rows[year - 1]
        core = row["segments"]["core"]
        group_interest = max(free, 0) * o["financial_yield_after_tax"]
        parent_interest = max(parent_free, 0) * o["financial_yield_after_tax"]
        pbt = core["ebit_after_rent"] * o["parent_core_pretax_fraction"]
        parent_tax = max(pbt, 0) * series_value(config["parent_tax"], year)
        parent_op_profit = pbt - parent_tax
        parent_investment = core["investment_cash_net_of_da"] * o["parent_capital_fraction"]
        parent_fcf = parent_op_profit - parent_investment
        buyback = bridge["remaining_employee_buyback"] if year == 1 else 0.0
        extra_transfer = series_value(config["parent_extra_internal_payment"], year)
        upstream = series_value(config["parent_sub_dividend_receipt"], year)
        assert upstream == 0, "No unverified future upstream dividend admitted in this version"
        parent_pre_d = parent_free + parent_fcf + parent_interest + upstream - buyback - extra_transfer
        group_pre_d = free + row["common_fcff"] + group_interest - buyback
        # Stock delivery is not new share issuance. Treasury cash is counted once;
        # budget noncash grant amortisation reduces parent legal/accounting profit and payout target only.
        parent_profit = parent_op_profit + parent_interest - grant
        common_profit = row["common_nopat"] + group_interest - grant
        charge = max(parent_profit, 0) * o["statutory_reserve_charge_rate"]
        gate = distribute(parent_pre_d, group_pre_d, retained, parent_profit - charge,
                          common_profit, o["ordinary_payout_budget"],
                          parent_buffer=o["parent_required_liquid"] + o["parent_capital_fraction"] * (core["operating_cash"] - o["segments"]["core"]["revenue"] * o["segments"]["core"]["cash_ratio"]),
                          group_buffer=sum(v["operating_cash"] * o["segments"][k]["ownership"] for k,v in row["segments"].items()) + config["seasonal_cash_common"],
                          parent_before_internal_settlement=parent_pre_d + extra_transfer)
        item = {"year": year, "opening_group_free": free, "opening_parent_free": parent_free,
                "parent_operating_profit": parent_op_profit, "parent_cash_fcf": parent_fcf,
                "parent_financial_yield": parent_interest, "group_financial_yield": group_interest,
                "common_accounting_profit_budget": common_profit,
                "noncash_employee_grant_expense_budget": grant, "buyback_cash": buyback,
                "employee_cash_proceeds": 0, "extra_parent_to_subsidiary_settlement": extra_transfer,
                "subsidiary_upstream_dividend_cash": upstream,
                "parent_legal_profit_budget": parent_profit, "reserve_charge": charge,
                "group_fcff": row["common_fcff"], "payment_gate": gate}
        ledger.append(item)
        if not gate["feasible"]:
            return {"feasible": False, "ledger": ledger, "reason": gate["reason"], "funding_state":gate["funding_state"], "failure_year":year}
        free, parent_free, retained = gate["group_cash_after"], gate["parent_cash_after"], gate["retained_after"]
        assert abs(free - (item["opening_group_free"] + row["common_fcff"] + group_interest - buyback - gate["paid"])) < EPS
        assert abs(parent_free - (item["opening_parent_free"] + parent_fcf + parent_interest - buyback - extra_transfer - gate["paid"])) < EPS
        assert parent_free <= free + EPS, "Mother liquidity cannot exceed total common discretionary pool"
    return {"feasible": True, "ledger": ledger, "end_group_free": free,
            "end_parent_free": parent_free, "end_parent_retained": retained,
            "distributions_per_share": [x["payment_gate"]["paid"] / inputs["shares"] for x in ledger]}


def operating_value_at(rows, config, year):
    """Independent state date: Y0 or Y5; Y5 is not current value rolled forward."""
    assert year in (0, 5)
    values = {}
    for s in SEGMENTS:
        r = config["discount"][s]
        g = config["terminal_growth"][s]
        assert r > g
        interim = sum(rows[t - 1]["segments"][s]["common_fcff"] / (1 + r) ** (t - year)
                      for t in range(year + 1, 11))
        terminal_row = rows[10]["segments"][s]
        flat_grant = terminal_row.get("common_grant_nopat", 0.0)
        terminal = (terminal_row["common_fcff"] - flat_grant) / (r - g) + flat_grant / r
        terminal_pv = terminal / (1 + r) ** (10 - year)
        values[s] = {"explicit_period_pv": interim, "terminal_pv": terminal_pv,
                     "terminal_value_at_year10": terminal, "value": interim + terminal_pv}
    return {"segments": values, "total": sum(x["value"] for x in values.values()),
            "terminal_pv_total": sum(x["terminal_pv"] for x in values.values())}


def run_case(inputs, name):
    config = case_config(inputs, name)
    rows = operating_path(inputs, config)
    bridge = opening_bridge(inputs, config)
    ledger = holder_ledger(inputs, config, rows, bridge)
    current_op = operating_value_at(rows, config, 0)
    future_op = operating_value_at(rows, config, 5)
    # Repurchases are a real common-equity outflow; no share-count cancellation benefit.
    repurchase_pv = bridge["remaining_employee_buyback"] / (1 + config["discount"]["core"])
    equity = current_op["total"] + bridge["opening_excess_net_financial_assets"] + bridge["other_nonoperating_investments_value"] - repurchase_pv
    future = future_op["total"] + ledger["end_group_free"] + bridge["other_nonoperating_investments_value"] if ledger["feasible"] else None
    acceptance = valuation_acceptance(ledger, equity, future, inputs["shares"])
    capital_checks = {}
    for s in SEGMENTS:
        a, b = rows[0]["segments"][s], rows[4]["segments"][s]
        denominator = b["total_operating_capital"] - a["total_operating_capital"]
        capital_checks[s] = {"year1_revenue": a["revenue"], "year5_revenue": b["revenue"],
            "year1_nopat": a["nopat"], "year5_nopat": b["nopat"],
            "year1_capital": a["total_operating_capital"], "year5_capital": b["total_operating_capital"],
            "year1_to_year5_incremental_return": ((b["nopat"] - a["nopat"]) / denominator) if abs(denominator) > EPS else None,
            "five_year_maintenance": sum(x["segments"][s]["maintenance_capex"] for x in rows[:5]),
            "five_year_growth_and_upgrade": sum(x["segments"][s]["growth_fixed_capex"] + x["segments"][s]["upgrade_capex"] for x in rows[:5]),
            "five_year_cash_rent": sum(x["segments"][s]["cash_rent"] for x in rows[:5]),
            "five_year_research": sum(x["segments"][s]["research_expense_cash"] for x in rows[:5]),
            "capital_caveat": "Forecast not observed ROIC. Colipu needs additional common seasonal reserve outside segment table; fixed capital is not assumed liquid on decline."}
    return {"name": name, "scenario_definition": inputs["cases"][name], "config": config,
            "opening_bridge": bridge, "operating_rows": rows, "capital_checks": capital_checks,
            "current_operating_value": current_op, "current_equity": equity if acceptance["current_equity_contract_eligible"] else None,
            "diagnostic_equity_before_funding_acceptance": equity,
            "current_value_per_share": acceptance["current_value_per_share"],
            "conditional_equity_diagnostic_per_share": equity / inputs["shares"], "valuation_acceptance":acceptance,
            "future_operating_value_year5": future_op,
            "holder_ledger": ledger, "year5_equity": future,
            "year5_equity_per_share": future / inputs["shares"] if future is not None else None,
            "current_terminal_pv_fraction": current_op["terminal_pv_total"] / equity,
            "remaining_buyback_pv": repurchase_pv}


def auxiliary(inputs, cases):
    out = {}
    aux = inputs["auxiliary"]
    for side in ("low", "high"):
        p = aux[side]
        bridge_case = cases[p["financial_bridge_case"]]
        cash = bridge_case["opening_bridge"]["cash_ownership_classification"]
        excess_cash = cash["colipu_excess_cash_total"]
        book = inputs["history"]["colipu_h1"]["net_assets"] - excess_cash + p["colipu_debt_allocated"]
        earnings = (p["colipu_normal_total_profit"] - excess_cash * inputs["opening"]["financial_yield_after_tax"]
                    + p["colipu_debt_allocated"] * aux["bank_debt_after_tax_cost"])
        r = p["colipu_cost"]
        residual = earnings - book * r
        excess_pv = sum(residual * (1 - (t - 1) / aux["franchise_years"]) / (1 + r) ** t
                        for t in range(1, aux["franchise_years"] + 1))
        colipu_ev = book + excess_pv
        core = p["core_maintainable_common_cash_earnings"] / p["core_cost"]
        retail = p["retail_operating_value"] * inputs["opening"]["segments"]["retail"]["ownership"]
        equity = (core + colipu_ev * 0.7778 + retail
                  + bridge_case["opening_bridge"]["opening_excess_net_financial_assets"]
                  + bridge_case["opening_bridge"]["other_nonoperating_investments_value"]
                  - bridge_case["remaining_buyback_pv"])
        out[side] = {"cash_ownership_classification":cash, "core_earnings_power": core, "colipu_operating_book": book,
                     "colipu_normal_operating_earnings": earnings, "colipu_operating_roe": earnings / book,
                     "colipu_excess_roe_pv": excess_pv, "colipu_operating_value_total": colipu_ev,
                     "retail_operating_value_common": retail, "equity": equity,
                     "per_share": equity / inputs["shares"]}
    return out


def hand_cases():
    # 100 revenue, 20 EBIT, 25% tax, no growth: 15 NOPAT/FCFF.
    p = {"rd_ratio": 0, "rent_ratio": 0, "da_ratio": 0, "growth_fixed_turnover": 5,
         "cash_ratio": 0, "ownership": 1}
    state = {"revenue": 100, "fixed": 20, "nwc": 10, "cash": 0}
    _, flat = step_segment(state, p, growth=0, margin=0.2, grant=0, tax_rate=0.25,
                          nwc_ratio=0.1, extra_capex=0, recovery=1)
    assert abs(flat["fcff"] - 15) < EPS
    # 10 extra sales -> 2 fixed + 1 NWC; NOPAT 16.5; FCFF 13.5.
    _, grow = step_segment(state, p, growth=0.1, margin=0.2, grant=0, tax_rate=0.25,
                          nwc_ratio=0.1, extra_capex=0, recovery=1)
    assert abs(grow["fcff"] - 13.5) < EPS
    # D request 7 but only 3 mother cash -> D=3, terminal group cash=17, mother=0.
    gate = distribute(3, 20, 50, 5, 10, 0.7)
    assert gate["paid"] == 3 and gate["group_cash_after"] == 17 and gate["parent_cash_after"] == 0
    # Legal profit cap independently binds: retained 1 + legal profit 1 = 2.
    legal = distribute(10, 20, 1, 1, 10, 0.7)
    assert legal["paid"] == 2
    # Formal value chain: 15 constant FCFF, 10% rate, no growth -> 150 at t0 AND t5.
    row = {"segments": {s: {"common_fcff": 5.0} for s in SEGMENTS}}
    cfg = {"discount": {s: 0.1 for s in SEGMENTS}, "terminal_growth": {s: 0 for s in SEGMENTS}}
    v0 = operating_value_at([copy.deepcopy(row) for _ in range(11)], cfg, 0)
    v5 = operating_value_at([copy.deepcopy(row) for _ in range(11)], cfg, 5)
    assert abs(v0["total"] - 150) < EPS and abs(v5["total"] - 150) < EPS
    funded_acceptance = valuation_acceptance({"feasible":gate["feasible"]},200,210,10)
    assert funded_acceptance["current_value_per_share"] == 20 and gate["classification"] == "ORDINARY_D_CONSTRAINED"
    branch_specs = [
        (-1,20,5,10,None,"PARENT_ASSUMED_BUFFER_SHORTFALL",False),
        (-2,20,5,10,3,"PARENT_INTERNAL_SETTLEMENT_SHORTFALL",False),
        (10,-2,5,5,None,"GROUP_ASSUMED_BUFFER_SHORTFALL",False),
        (10,-7,5,5,None,"GROUP_OPERATING_FINANCING_GAP",True)]
    branches = []
    for pc,gc,pb,gb,before,label,true_gap in branch_specs:
        payment = distribute(pc,gc,50,5,10,0.7,parent_buffer=pb,group_buffer=gb,parent_before_internal_settlement=before)
        funding = payment["funding_state"]
        accepted = valuation_acceptance({"feasible":False,"funding_state":funding},200,None,10)
        assert funding["classification"] == label and funding["true_operating_or_capital_action_financing_gap"] is true_gap
        assert payment["paid"] is None and accepted["current_value_per_share"] is None
        assert accepted["conditional_equity_diagnostic_per_share"] == 20 and not accepted["holder_contract_eligible"]
        readiness = contract_readiness(funded_acceptance,funded_acceptance,accepted)
        assert readiness == {"value_range":False,"return_model":False}
        branches.append({"classification":label,"funding":funding,"valuation_acceptance":accepted,"formal_contract_readiness":readiness})
    # Shared asset bridge fixture: 10 running + 5 seasonal + 5 excess = 20;
    # 80% common=16, 20% minority=4, plus 1 other minority => group minority=5.
    ownership_fixture = {"opening":{"segments":{"colipu":{"ownership":0.8,"revenue":100,"cash_ratio":0.1}},"parent_liquid_proxy":20},"history":{"q3":{"cash":50,"trading_financial_assets":50}}}
    ownership = cash_ownership_bridge(ownership_fixture,{"seasonal_cash_common":4,"colipu_excess_cash":5,"other_nci_financial_assets":1})
    assert abs(ownership["colipu_gross_financial_assets_total"]-20)<EPS
    assert abs(ownership["group_nci_financial_assets"]-5)<EPS
    return {"flat_fcff": flat["fcff"], "growth_fcff": grow["fcff"], "cash_limited_D": gate["paid"],
            "legal_limited_D": legal["paid"], "flat_value_t0": v0["total"], "flat_value_t5": v5["total"],"funding_branch_transmission":branches,"ownership_nonoverlap_fixture":ownership}




def fmt(x):
    return f"{x:.2f}"
