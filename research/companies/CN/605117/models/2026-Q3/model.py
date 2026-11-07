#!/usr/bin/env python3
"""Deye annual ordinary-equity research model; standard library only.

This module alone is not evidence that any model or hand case has run.
Ordinary offline CLI; no market-price input.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback


EPS = 1e-7
MAX_OUTPUT_BYTES = 20 * 1024 * 1024


class EconomicInfeasible(Exception):
    """A genuine unbounded economic path, distinct from a coding failure."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def near(left, right, label, scale=1.0):
    tolerance = EPS * max(1.0, scale, abs(left), abs(right))
    if abs(left - right) > tolerance:
        raise AssertionError(f"{label}: {left!r} != {right!r}")
    return left - right


def merge(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def safe_relative(root, name):
    p = Path(name)
    require(not p.is_absolute(), "Paths must be relative to the model directory")
    result = (root / p).resolve()
    require(result.is_relative_to(root.resolve()), "Path escapes model directory")
    return result


def load_input(path, seen=None):
    seen = set() if seen is None else set(seen)
    resolved = path.resolve()
    require(resolved not in seen, "Input inheritance cycle")
    seen.add(resolved)
    raw = resolved.read_bytes()
    payload = json.loads(raw)
    identity = {"file": resolved.name, "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw)}
    if "inherits" not in payload:
        return payload, [identity]
    parent = safe_relative(resolved.parent, payload["inherits"])
    inherited, identities = load_input(parent, seen)
    return merge(inherited, payload["overrides"]), identities + [identity]


def validate_input(data):
    require(data["schema_version"] == 1, "Unsupported input schema")
    require(data.get("contract_revision") == 2, "Input contract revision must match v2 producer")
    require(data["currency"] == "CNY", "Currency mismatch")
    b = data["base"]
    n = b["years"]
    require(isinstance(b["maturity_transition"]["years"], int) and 0 <= b["maturity_transition"]["years"] <= 3, "Finite transition outside declared0..3 years")
    require(b["terminal"]["primary_cash_tail_mode"] == "physical_unit_capital_exact_two_component", "Unsupported primary mature mechanism")
    require(isinstance(n, int) and 5 <= n <= 30, "Invalid annual horizon")
    arrays = ["debt_principal_fraction_of_opening", "cash_rnd_ratio", "cash_sga_ratio",
              "noncash_known_share_plan_cost", "future_employee_buyback_cash",
              "future_employee_grant_cash_received", "future_employee_buyback_transaction_fees", "organic_growth_capex",
              "project_cash_guarantee_new", "project_cash_guarantee_release",
              "bank_guarantee_face"]
    for key in arrays:
        require(len(b[key]) == n, f"Wrong array length: {key}")
    for key in ["receivable_days", "inventory_days", "ap_purchase_days", "bill_purchase_days"]:
        require(len(b["working_capital"][key]) == n, f"Wrong WC length: {key}")
    for key in ["export_share", "china_origin_share_of_export", "eligible_customs_code_share",
                "incremental_rebate_loss_rate"]:
        require(len(b["battery_policy"][key]) == n, f"Wrong policy length: {key}")
    near(sum(s["anchor_share"] for s in b["segments"]), 1.0, "segment weights")
    for segment in b["segments"]:
        require(segment["id"] in b["capacity_proxy_existing"], "Missing capacity proxy")
        require(segment["id"] in b["auxiliary"]["gross_margin"], "Missing normalized margin")
        for key in ["volume_growth", "underlying_asp_change", "pre_incremental_policy_gross_margin"]:
            require(len(segment[key]) == n, f"Wrong segment length: {segment['id']}/{key}")
    for project in b["projects"]:
        for key in ["remaining_cash_weights", "new_book_weights"]:
            require(len(project[key]) == n, "Wrong project schedule")
            near(sum(project[key]), 1.0, f"project weights {project['id']}/{key}")
        for key in ["in_service_fraction_end", "in_service_capital_time_weight", "effective_sales_capacity_weight"]:
            require(len(project[key]) == n, "Wrong commissioning timing schedule")
            require(all(0 <= z <= 1 for z in project[key]), "Commissioning fraction outside0..1")
        require(all(project["in_service_fraction_end"][j] <= project["in_service_fraction_end"][j+1]
                    for j in range(n-1)), "Capital in-service end fractions must not decline")
        for j in range(n):
            require(project["effective_sales_capacity_weight"][j] <= project["in_service_capital_time_weight"][j] + EPS,
                    "Sales ramp exceeds time-weighted in-service capital proxy")
        for selector in ["fixed_capital_budget", "budget_low", "budget_high"]:
            require(project[selector] + EPS >= max(project["opening_cash_paid"],
                                                  project["opening_capital_book"]),
                    "Project budget below existing capital/payment")
    require(b["parent"]["upstream_declaration_ratio"] <=
            b["parent"]["subsidiary_profit_available_fraction"] + EPS,
            "Base upstream exceeds specified legal-profit allowance")
    require(0 <= b["parent"]["known_plan_sbc_parent_expense_fraction"] <= 1, "Invalid parent SBC allocation")
    require(b["cost_of_equity"] > b["terminal"]["growth"], "r must exceed g")
    ids = [s["id"] for s in data["scenarios"]]
    require(len(ids) == len(set(ids)) and "base" in ids, "Scenario identity error")
    for value in ids:
        require(value.replace("_", "").isalnum(), "Unsafe scenario id")



def mother_liquidity_buckets(total, excess, operating, collateral, minimum):
    """Ownership-location estimate only: preserve cash, no transfer or expense."""
    positive = max(0.0, total)
    operating_priority = min(positive, max(0.0, minimum), max(0.0, operating))
    financial = min(max(0.0, positive - operating_priority), max(0.0, excess))
    extra_operating = min(max(0.0, positive - operating_priority - financial),
                          max(0.0, operating - operating_priority))
    mother_operating = operating_priority + extra_operating
    mother_support = min(max(0.0, positive - financial - mother_operating), max(0.0, collateral))
    unlocated = max(0.0, positive - financial - mother_operating - mother_support)
    negative_gap = max(0.0, -total)
    residual_minimum = max(0.0, minimum - mother_operating)
    residual = near(total, financial + mother_operating + mother_support + unlocated - negative_gap,
                    "mother liquidity classification preserves principal")
    return {"total_liquid_cash": total, "financial_cash": financial,
            "operating_cash_in_group_B": mother_operating, "support_cash_in_group_C": mother_support,
            "unlocated_entity_bridge_amount": unlocated, "negative_cash_gap": negative_gap,
            "minimum_cash_not_already_in_B": residual_minimum,
            "ordinary_distribution_cash_capacity": max(0.0, financial - residual_minimum),
            "principal_classification_residual": residual}


def opening_state(data, changes):
    f, b = data["facts"], data["base"]
    q, h, rights, o, p = f["q3"], f["h1_parent"], f["rights"], b["opening_estimates"], b["parent"]
    anchor = q["revenue_9m"] + q["revenue_quarter"]
    financial_q3 = (q["cash"] + q["trading_financial_assets"] + q["one_year_noncurrent_assets"]
                    + o["other_current_financial_principal"]
                    + o["other_noncurrent_financial_principal"]
                    + changes.get("financial_principal_shift", 0.0))
    october_cfo = o["oct_operating_nopat"] + o["oct_depreciation"] - o["oct_core_wc_change"]
    financial_open = (financial_q3 + october_cfo - o["oct_cash_capex"]
                      + o["oct_financial_cash_income_after_tax"]
                      - o["oct_debt_cash_interest_after_tax"] - o["oct_debt_principal_repaid"]
                      + o["oct_other_external_cash"] - q["dividend_payable"]
                      - rights["buyback_cash_oct15_ex_fees"] - o["oct_share_transaction_fees"]
                      - q["trading_financial_liabilities"])
    collateral = q["cash"] - q["cash_equivalents"] + o["additional_pledged_deposits"]
    operating_cash = anchor * b["working_capital"]["minimum_operating_cash_ratio"]
    excess = financial_open - collateral - operating_cash
    minority_value = q["minority_equity"]
    debt = (q["short_debt"] + q["long_debt"] + q["current_noncurrent_liabilities"]
            + q["lease_liabilities"] - o["oct_debt_principal_repaid"])
    strategic = ((q["long_equity_investment"] + q["other_noncurrent_financial_assets"])
                 * o["strategic_asset_value_factor"])
    op_ap = q["trade_payables_reported"] - o["capital_payables_q3"]
    core_wc = (q["receivables"] + q["inventory"] + o["core_other_operating_net_q3"]
               - op_ap - q["bills_payable"] - q["contract_liabilities"]
               + o["oct_core_wc_change"])
    fixed_q3 = sum(q[k] for k in ["ppe", "cip", "intangibles", "rou_assets", "long_deferred_costs"])
    fixed = fixed_q3 + o["oct_capital_book_addition"] - o["oct_depreciation"]
    oct_rou_amortization = b["annual_rou_amortization"] / 12.0
    require(o["oct_depreciation"] + EPS >= oct_rou_amortization,
            "October total depreciation below budgeted ROU component")
    productive = (fixed_q3 - q["cip"] - q["rou_assets"]
                  - b["existing_project_non_cip_book_excluded_from_general_depreciation"]
                  - (o["oct_depreciation"] - oct_rou_amortization))
    mother_cash = (h["cash"] + h["trading_financial_assets"] + h["one_year_noncurrent_assets"]
                   + p["h2_to_oct_sub_dividends_received"] + p["h2_to_oct_own_operating_cash"]
                   + p["h2_to_oct_financial_income_cash"] - rights["h1_dividend_total_paid_by_oct14"]
                   - p["h2_to_oct_debt_cash_repayment"] - p["h2_to_oct_capital_contribution"]
                   - rights["buyback_cash_oct15_ex_fees"] - o["oct_share_transaction_fees"])
    mother_re = (h["retained_earnings"] + p["h2_to_oct_new_sub_dividends_declared"]
                 + p["h2_to_oct_own_profit_ex_dividends"] - rights["h1_dividend_total_paid_by_oct14"])
    mother_ar = (h["dividend_receivable"] + p["h2_to_oct_new_sub_dividends_declared"]
                 - p["h2_to_oct_sub_dividends_received"])
    mother_debt = h["short_debt"] + h["long_debt"] - p["h2_to_oct_debt_cash_repayment"]
    require(mother_ar >= -EPS and mother_debt >= -EPS, "Invalid explicit parent bridge")
    require(mother_debt <= debt + EPS, "Mother debt exceeds group debt")
    projects_unpaid = sum(x["opening_capital_book"] - x["opening_cash_paid"] for x in b["projects"])
    capital_payables_open = o["capital_payables_q3"] - (o["oct_cash_capex"] - o["oct_capital_book_addition"])
    near(projects_unpaid, capital_payables_open, "opening capital payable reconciliation")
    return {
        "anchor_revenue": anchor, "financial_q3": financial_q3, "october_cfo_estimate": october_cfo,
        "financial_pool_after_known_and_estimated_bridge": financial_open,
        "excess": excess, "collateral": collateral, "operating_cash": operating_cash,
        "core_wc": core_wc, "inventory": q["inventory"], "fixed": fixed,
        "productive": productive, "debt": debt, "strategic": strategic,
        "shares": q["issued_shares"], "mother_cash": mother_cash, "mother_re": mother_re,
        "minority_value_bridge": minority_value,
        "mother_liquidity": mother_liquidity_buckets(mother_cash, excess, operating_cash, collateral, p["minimum_cash"]),
        "mother_ar": mother_ar, "mother_reserve": h["statutory_reserve"],
        "mother_debt_share": mother_debt / debt if debt > EPS else 0.0,
        "subs_distributable": p["subsidiary_distributable_open"],
        "capital_payables": capital_payables_open,
        "issuer_opening_buyback_cash": rights["buyback_cash_oct15_ex_fees"],
        "issuer_opening_buyback_fees": o["oct_share_transaction_fees"],
        "issuer_cash_attribution_note": "Same external outflow once in group F0 and once in mother subset M0, never sum the ledgers. Principal/fees are equity cash, not additional parentRE expense.",
        "current_dividend_eligible_share_range": [q["issued_shares"] - rights["buyback_shares_header"],
                                                  q["issued_shares"] - rights["buyback_shares_body"]],
        "note": "Opening estimates, not observed Oct31 financial statements; mother balances are subset, not additional group value."
    }


def projects_for_case(base, changes):
    selector = changes.get("project_budget_selector", "fixed_capital_budget")
    require(selector in {"fixed_capital_budget", "budget_low", "budget_high"}, "Unknown project scope")
    result = copy.deepcopy(base["projects"])
    for item in result:
        item["selected_budget"] = item[selector]
    return result


def policy_segment(x, margin, exposure, loss_rate, pass_through, elasticity):
    require(0 <= margin <= 1, "Margin outside economic bounds")
    require(0 <= exposure <= 1 and 0 <= pass_through <= 1, "Policy parameter outside bounds")
    require(0 <= loss_rate < 1 and pass_through * loss_rate < 1, "Invalid price-tax circular base")
    multiplier = 1.0 / (1.0 - pass_through * loss_rate)
    retained_volume = max(0.0, 1.0 - elasticity * (multiplier - 1.0))
    exposed_base = x * exposure * retained_volume
    unexposed = x * (1.0 - exposure)
    taxed_fo_b = exposed_base * multiplier
    realized_base = unexposed + exposed_base
    revenue = unexposed + taxed_fo_b
    rebate_cost = taxed_fo_b * loss_rate
    cogs_reference = realized_base * (1.0 - margin) + rebate_cost
    return {
        "pre_policy_sales_after_capacity": x, "reference_accounting_margin": margin,
        "exposure_share": exposure, "incremental_rebate_loss_rate": loss_rate,
        "pass_through_fraction": pass_through, "price_multiplier": multiplier,
        "exposed_volume_retention": retained_volume, "affected_new_fob_tax_base": taxed_fo_b,
        "revenue": revenue, "realized_pre_policy_price_revenue": realized_base,
        "production_cogs_reference": realized_base * (1.0 - margin), "cogs_reference": cogs_reference,
        "incremental_nonrefundable_cost": rebate_cost,
        "price_recovery": exposed_base * (multiplier - 1.0),
        "net_policy_cost_before_income_tax": rebate_cost - exposed_base * (multiplier - 1.0)
    }


def business_rows(data, changes, mode, opening, projects):
    b = data["base"]
    n, aux = b["years"], b["auxiliary"]
    policy = b["battery_policy"]
    pass_through = changes.get("pass_through_fraction", policy["pass_through_fraction"])
    levels = changes.get("demand_level_multipliers", [1.0] * n)
    margin_years = changes.get("margin_shift_by_year", [0.0] * n)
    require(len(levels) == n and len(margin_years) == n, "Scenario annual length mismatch")
    volume_index = {s["id"]: 1.0 for s in b["segments"]}
    price_index = dict(volume_index)
    organic_prior = 0.0
    rows = []
    for i in range(n):
        segments = []
        for s in b["segments"]:
            sid = s["id"]
            seed = opening["anchor_revenue"] * s["anchor_share"]
            if mode == "primary":
                volume_index[sid] *= 1.0 + s["volume_growth"][i] * changes.get("volume_growth_multiplier", 1.0)
                price_index[sid] *= 1.0 + s["underlying_asp_change"][i]
                demand = seed * volume_index[sid] * price_index[sid] * levels[i]
                allocation = b["organic_capacity_battery_share"] if sid == "battery" else (
                    1.0 - b["organic_capacity_battery_share"] if sid == "inverters" else 0.0)
                installed = b["capacity_proxy_existing"][sid] + sum(
                    p["revenue_capacity_2026_prices"].get(sid, 0.0) * p["effective_sales_capacity_weight"][i]
                    for p in projects)
                installed *= changes.get("capacity_multiplier", 1.0)
                installed += organic_prior * b["organic_capacity_per_capital"] * allocation
                capacity = installed * price_index[sid] * b["capacity_proxy_max_utilization"]
                realized = min(demand, capacity)
                margin = s["pre_incremental_policy_gross_margin"][i]
            else:
                growth = changes.get("terminal_growth", aux["growth"])
                demand = seed * aux["anchor_utilization_factor"] * (1.0 + growth) ** (i + 1) * levels[i]
                realized, capacity = demand, None
                margin = aux["gross_margin"][sid]
            margin += changes.get("margin_shift", 0.0) + margin_years[i]
            margin += changes.get("segment_margin_shift", {}).get(sid, 0.0)
            if s["rebate_exposure"]:
                if mode == "primary":
                    exposure = policy["export_share"][i] * policy["china_origin_share_of_export"][i] * policy["eligible_customs_code_share"][i]
                    loss = policy["incremental_rebate_loss_rate"][i]
                else:
                    exposure, loss = aux["battery_export_share"], aux["incremental_rebate_loss_rate"]
            else:
                exposure, loss = 0.0, 0.0
            item = policy_segment(realized, margin, exposure, loss, pass_through, policy["price_elasticity"])
            item.update({"id": sid, "unconstrained_demand": demand, "sales_capacity_proxy": capacity,
                         "capacity_lost_sales": demand - realized, "volume_index": volume_index[sid] if mode == "primary" else None,
                         "underlying_price_index": price_index[sid] if mode == "primary" else None})
            segments.append(item)
        rows.append({"segments": segments, "revenue": sum(s["revenue"] for s in segments),
                     "cogs_reference": sum(s["cogs_reference"] for s in segments),
                     "realized_pre_policy_price_revenue": sum(s["realized_pre_policy_price_revenue"] for s in segments),
                     "production_cogs_reference": sum(s["production_cogs_reference"] for s in segments),
                     "incremental_nonrefundable_cost": sum(s["incremental_nonrefundable_cost"] for s in segments)})
        organic_prior += b["organic_growth_capex"][i]
    return rows


def annual(values, index):
    """Hold final annual assumption after the original explicit horizon."""
    return values[min(index, len(values) - 1)]


def aggregate_segments(segments):
    return {"segments": segments, "revenue": sum(s["revenue"] for s in segments),
            "cogs_reference": sum(s["cogs_reference"] for s in segments),
            "realized_pre_policy_price_revenue": sum(s["realized_pre_policy_price_revenue"] for s in segments),
            "production_cogs_reference": sum(s["production_cogs_reference"] for s in segments),
            "incremental_nonrefundable_cost": sum(s["incremental_nonrefundable_cost"] for s in segments)}


def installed_capacity_after_original_years(base, changes, projects):
    stock = {}
    for s in base["segments"]:
        sid = s["id"]
        allocation = base["organic_capacity_battery_share"] if sid == "battery" else (
            1.0 - base["organic_capacity_battery_share"] if sid == "inverters" else 0.0)
        stock[sid] = ((base["capacity_proxy_existing"][sid]
                       + sum(p["revenue_capacity_2026_prices"].get(sid, 0.0)
                             * p["effective_sales_capacity_weight"][-1] for p in projects))
                      * changes.get("capacity_multiplier", 1.0)
                      + sum(base["organic_growth_capex"]) * base["organic_capacity_per_capital"] * allocation)
    return stock


def transition_business(data, changes, previous_row, step, installed):
    b, transition = data["base"], data["base"]["maturity_transition"]
    length = transition["years"]
    target = changes.get("terminal_growth", b["terminal"]["growth"])
    alpha, next_alpha = step / length, min(1.0, (step + 1) / length)
    old = {s["id"]: s for s in b["segments"]}
    segments, capacity_addition, growth_capital = [], {}, {}
    productivity = transition["future_capacity_per_capital"]
    utilization = b["capacity_proxy_max_utilization"]
    require(productivity > 0 and 0 < utilization <= 1, "Invalid transition physical-capital assumptions")
    for previous in previous_row["segments"]:
        sid = previous["id"]
        v0 = old[sid]["volume_growth"][-1] * changes.get("volume_growth_multiplier", 1.0)
        growth = v0 * (1.0 - alpha) + target * alpha
        next_growth = v0 * (1.0 - next_alpha) + target * next_alpha
        asp_change = old[sid]["underlying_asp_change"][-1] * (1.0 - alpha)
        price_index = previous["underlying_price_index"] * (1.0 + asp_change)
        demand = previous["pre_policy_sales_after_capacity"] * (1.0 + growth) * (1.0 + asp_change)
        capacity = installed[sid] * price_index * utilization
        actual = min(demand, capacity)
        item = policy_segment(actual, previous["reference_accounting_margin"], previous["exposure_share"],
                              previous["incremental_rebate_loss_rate"], previous["pass_through_fraction"],
                              b["battery_policy"]["price_elasticity"])
        addition = actual / price_index * max(0.0, next_growth) / utilization
        capacity_addition[sid] = addition
        growth_capital[sid] = addition / productivity
        item.update({"id": sid, "unconstrained_demand": demand, "sales_capacity_proxy": capacity,
                     "capacity_lost_sales": demand - actual, "volume_index": None,
                     "underlying_price_index": price_index, "transition_volume_growth": growth,
                     "transition_asp_change": asp_change, "funded_next_volume_growth": next_growth,
                     "funded_capacity_addition_next_year": addition,
                     "growth_capital_for_next_year_capacity": growth_capital[sid]})
        segments.append(item)
    return aggregate_segments(segments), growth_capital, capacity_addition


def mature_physical_cash_tail(data, changes, result, r, g, return_override):
    """Five operating-only budget rows: two settlement transitions then exact affine growth.

    No distribution/legal machine and no second explicit-period run. A return
    override changes the cost of the SAME incremental physical capacity; it is
    a conditional capital-efficiency sensitivity, not extra unexplained capex.
    """
    b, last = data["base"], result["rows"][-1]
    wc = b["working_capital"]
    delta = b["depreciation_rate_on_productive_capital"]
    tax_rate = b["cash_tax_rate"]
    q = 1.0 + g
    require(r > g >= 0, "Invalid mature discount/growth")
    require(last["revenue"] > EPS, "Mature revenue is not positive")
    revenue0 = last["revenue"]
    cp = last["production_cash_cogs_for_supplier_credit"] / revenue0
    cash_margin = (revenue0 - last["production_cash_cogs_for_supplier_credit"]
                   - last["incremental_nonrefundable_cost"] - last["cash_opex"]) / revenue0
    inv_days = max(0.0, wc["inventory_days"][-1] + changes.get("inventory_days_shift", 0.0))
    ar_days = max(0.0, wc["receivable_days"][-1] + changes.get("receivable_days_shift", 0.0))
    ap_days = max(0.0, wc["ap_purchase_days"][-1] + changes.get("ap_days_shift", 0.0))
    bill_days = max(0.0, wc["bill_purchase_days"][-1] + changes.get("bill_days_shift", 0.0))
    collateral_rate = changes.get("bill_collateral_ratio", wc["bill_collateral_ratio"])
    vat_factor = 1.0 + wc["input_vat_rate"] * wc["input_vat_applicable_share"]
    credit = vat_factor * (ap_days + bill_days * (1.0 - collateral_rate)) / 365.0
    inventory_coefficient0 = inv_days / 365.0 * cp
    inventory_coefficient1 = inv_days / 365.0 * delta
    w0 = (ar_days / 365.0 + wc["other_operating_current_net_ratio"]
          - wc["contract_liability_ratio"] + wc["minimum_operating_cash_ratio"]
          + inventory_coefficient0
          - credit * (wc["raw_material_share_of_cash_cogs"] * cp + inventory_coefficient0 * g / q))
    w1 = inventory_coefficient1 * (1.0 - credit * g / q)
    utilization = b["capacity_proxy_max_utilization"]
    base_productivity = b["maturity_transition"]["future_capacity_per_capital"]
    base_kf = sum(s["pre_policy_sales_after_capacity"] / s["underlying_price_index"]
                  / utilization / base_productivity for s in last["segments"]) / revenue0
    kf = base_kf
    if return_override is not None:
        require(return_override > g, "Conditional mature return must exceed growth")
        numerator = cash_margin * (1.0 - tax_rate) - return_override * w0 / q
        denominator = delta * (1.0 - tax_rate) + return_override * (1.0 + w1 / q)
        if numerator <= 0 or denominator <= 0:
            raise EconomicInfeasible("Mature efficiency condition implies nonpositive physical capital cost")
        kf = numerator / denominator
    require(base_kf > 0 and kf > 0, "Mature fixed-capital intensity must be positive")
    productivity = base_productivity * base_kf / kf
    steady_cash_margin_after_da = cash_margin - delta * kf
    if steady_cash_margin_after_da <= 0:
        raise EconomicInfeasible("Physical mature replacement/expansion budget has no positive continuing operating margin")
    reinvestment_denominator = kf + (w0 + w1 * kf) / q
    implied_return = ((steady_cash_margin_after_da * (1.0 - tax_rate)) / reinvestment_denominator
                      if reinvestment_denominator > EPS else None)
    if return_override is not None and implied_return is not None:
        near(implied_return, return_override, "conditional mature physical-capital efficiency")
    prior_segments = copy.deepcopy(last["segments"])
    installed = copy.deepcopy(result["capacity_installed_at_horizon"])
    productive = last["productive_capital_next_year"]
    fixed = last["fixed_operating_capital_end"]
    inventory_prev, core_prev = last["inventory"], last["core_wc"]
    support_prev = last["required_collateral"] + last["minimum_operating_cash"]
    rows = []
    for step in range(1, 6):
        segments, additions = [], {}
        for s in prior_segments:
            sid, price_index = s["id"], s["underlying_price_index"]
            demand = s["pre_policy_sales_after_capacity"] * q
            capacity = installed[sid] * price_index * utilization
            if demand > capacity + EPS * max(1.0, demand):
                raise EconomicInfeasible("Mature initial capacity cannot support proposed growth from the saved state")
            item = policy_segment(demand, s["reference_accounting_margin"], s["exposure_share"],
                                  s["incremental_rebate_loss_rate"], s["pass_through_fraction"],
                                  b["battery_policy"]["price_elasticity"])
            addition = demand / price_index * g / utilization
            additions[sid] = addition
            item.update({"id": sid, "underlying_price_index": price_index,
                         "sales_capacity_proxy": capacity, "capacity_lost_sales": 0.0,
                         "growth_capacity_for_next_year": addition,
                         "growth_capital_for_next_year": addition / productivity})
            segments.append(item)
        income = aggregate_segments(segments)
        revenue = income["revenue"]
        depreciation = productive * delta + b["annual_rou_amortization"]
        reference_da = income["realized_pre_policy_price_revenue"] * b["reference_accounting_depreciation_ratio"]
        production_cash = income["production_cogs_reference"] - reference_da
        production_cogs = production_cash + depreciation
        policy_tax = income["incremental_nonrefundable_cost"]
        cogs = production_cogs + policy_tax
        cash_opex = revenue * (b["cash_rnd_ratio"][-1] + b["cash_sga_ratio"][-1]
                              + changes.get("cash_sga_ratio_shift", 0.0))
        ebit = revenue - cogs - cash_opex
        cash_tax = max(0.0, ebit) * tax_rate
        nopat = ebit - cash_tax
        inventory = production_cogs * inv_days / 365.0
        purchases = max(0.0, production_cash * wc["raw_material_share_of_cash_cogs"] + inventory - inventory_prev)
        vat_purchases = purchases * vat_factor
        ap, bills = vat_purchases * ap_days / 365.0, vat_purchases * bill_days / 365.0
        receivables = revenue * ar_days / 365.0
        core = (receivables + inventory + revenue * wc["other_operating_current_net_ratio"]
                - ap - bills - revenue * wc["contract_liability_ratio"])
        collateral = bills * collateral_rate
        operating_cash = revenue * wc["minimum_operating_cash_ratio"]
        support = collateral + operating_cash
        growth_capital = sum(additions.values()) / productivity
        net_reinvestment = growth_capital + core - core_prev + support - support_prev
        fcff = nopat - net_reinvestment
        fixed += growth_capital
        rows.append({"mature_step": step, "segments": segments, "revenue": revenue,
                     "production_cash_cogs": production_cash, "production_cogs": production_cogs,
                     "incremental_nonrefundable_cost": policy_tax, "depreciation": depreciation,
                     "maintenance_cash_capex": depreciation, "growth_cash_capex": growth_capital,
                     "cash_opex": cash_opex, "ebit": ebit, "cash_tax": cash_tax, "nopat": nopat,
                     "inventory": inventory, "materials_purchases_ex_vat": purchases,
                     "vat_inclusive_purchases": vat_purchases, "trade_payables": ap, "bills_payable": bills,
                     "core_wc": core, "required_collateral": collateral, "operating_cash": operating_cash,
                     "net_operating_reinvestment": net_reinvestment, "fcff": fcff,
                     "fixed_operating_capital_end": fixed, "productive_capital_begin": productive})
        productive += growth_capital
        for sid, addition in additions.items():
            installed[sid] += addition
        prior_segments = segments
        inventory_prev, core_prev, support_prev = inventory, core, support
    f1, f2, f3, f4, f5 = (row["fcff"] for row in rows)
    recurrence = near(f5 - f4, q * (f4 - f3), "mature operating cash affine-growth recurrence after inventory/AP transition")
    if g > EPS:
        growing = (f4 - f3) / g
        constant = f3 - growing
        if growing <= 0:
            raise EconomicInfeasible("Mature physical budget produces no positive growing operating cash component")
        operating_terminal = f1 / (1.0 + r) + f2 / (1.0 + r) ** 2 + (growing / (r - g) + constant / r) / (1.0 + r) ** 2
    else:
        near(f4, f3, "zero-growth mature cash stationarity")
        near(f5, f4, "zero-growth mature cash stationarity continued")
        growing, constant = 0.0, f3
        operating_terminal = f1 / (1.0 + r) + f2 / (1.0 + r) ** 2 + f3 / r / (1.0 + r) ** 2
    return {"operating_terminal": operating_terminal, "probe_rows": rows,
            "first_mature_nopat": rows[0]["nopat"], "first_mature_reinvestment": rows[0]["net_operating_reinvestment"],
            "growing_cash_component_from_step3": growing, "constant_cash_component_from_step3": constant,
            "affine_recurrence_residual": recurrence, "base_physical_capacity_per_capital": base_productivity,
            "applied_physical_capacity_per_capital": productivity, "fixed_capital_per_revenue_coefficient": kf,
            "working_support_coefficient_constant": w0, "working_support_coefficient_per_fixed": w1,
            "asymptotic_cash_reinvestment_implied_return": implied_return,
            "conditional_terminal_return_override": return_override,
            "capital_proxy_outside_disclosed_range": not (b["maturity_transition"]["capacity_cost_proxy_range"][0]
                                                           <= productivity <= b["maturity_transition"]["capacity_cost_proxy_range"][1]),
            "maintenance_note": "Every year maintenance cash equals full asset/ROU depreciation. Constant legacy DA is recurring replacement of existing capacity, not finite-lived assets depreciating forever without cash replacement; new owned growth capital begins DA next year. No second lease rent or debt deduction."}


def run_method(data, scenario, mode):
    changes, b = scenario["changes"], data["base"]
    p, wc, aux = b["parent"], b["working_capital"], b["auxiliary"]
    opening = opening_state(data, changes)
    projects = projects_for_case(b, changes)
    business = business_rows(data, changes, mode, opening, projects)
    state = copy.deepcopy(opening)
    initial_debt = opening["debt"]
    organic_prior = 0.0
    project_cash_margin = 0.0
    rows, failures, warnings = [], [], []
    if opening["excess"] < -EPS:
        failures.append({"year": 0, "reason": "opening_excess_finance_negative", "gap": -opening["excess"]})
    if opening["mother_liquidity"]["unlocated_entity_bridge_amount"] > EPS:
        warnings.append({"year": 0, "reason": "mother_entity_liquid_bridge_estimate_conflict",
                         "amount": opening["mother_liquidity"]["unlocated_entity_bridge_amount"],
                         "scope": "Unknown entity location; not a group financing gap or principal writeoff"})
    original_years = b["years"]
    transition_years = b["maturity_transition"]["years"] if mode == "primary" else 0
    capacity_stock = installed_capacity_after_original_years(b, changes, projects) if mode == "primary" else {}
    for i in range(original_years + transition_years):
        year = i + 1
        before = copy.deepcopy(state)
        transition_addition, transition_capital = {}, {}
        if i < original_years:
            income = copy.deepcopy(business[i])
        else:
            income, transition_capital, transition_addition = transition_business(
                data, changes, rows[-1], i - original_years + 1, capacity_stock)
        revenue = income["revenue"]
        project_cash = sum((z["selected_budget"] - z["opening_cash_paid"]) * (z["remaining_cash_weights"][i] if i < original_years else 0.0) for z in projects)
        project_book = sum((z["selected_budget"] - z["opening_capital_book"]) * (z["new_book_weights"][i] if i < original_years else 0.0) for z in projects)
        current_organic_for_da = b["organic_growth_capex"][i] if mode == "primary" and i < original_years else 0.0
        commissioned_average = sum(z["selected_budget"] * annual(z["in_service_capital_time_weight"], i) for z in projects)
        for z in projects:
            booked_to_date = z["opening_capital_book"] + (z["selected_budget"] - z["opening_capital_book"]) * sum(z["new_book_weights"][:min(i + 1, original_years)])
            require(z["selected_budget"] * annual(z["in_service_fraction_end"], i) <= booked_to_date + EPS,
                    "In-service capital exceeds cumulative recognized project capital")
        depreciation = ((opening["productive"] + commissioned_average + organic_prior
                         + 0.5 * current_organic_for_da) * b["depreciation_rate_on_productive_capital"]
                        + b["annual_rou_amortization"])
        reference_da = income["realized_pre_policy_price_revenue"] * b["reference_accounting_depreciation_ratio"]
        cogs = income["cogs_reference"] - reference_da + depreciation
        rebate_cost = income["incremental_nonrefundable_cost"]
        production_cogs = income["production_cogs_reference"] - reference_da + depreciation
        production_cash_cogs = production_cogs - depreciation
        require(production_cash_cogs >= -EPS and cogs >= 0, "Negative modeled production cash cost")
        production_cash_cogs = max(0.0, production_cash_cogs)
        near(cogs, production_cogs + rebate_cost, "production and tax COGS separation")
        for segment in income["segments"]:
            allocation = (segment["realized_pre_policy_price_revenue"] / income["realized_pre_policy_price_revenue"]
                          if income["realized_pre_policy_price_revenue"] > EPS else 0.0)
            segment["cogs_after_asset_depreciation"] = segment["cogs_reference"] + (depreciation - reference_da) * allocation
            segment["gross_margin_after_asset_depreciation"] = (
                1.0 - segment["cogs_after_asset_depreciation"] / segment["revenue"]
                if segment["revenue"] > EPS else None)
        loss = before["inventory"] * changes.get("inventory_writeoff_opening_fraction", 0.0) if i == 0 else 0.0
        rnd = annual(b["cash_rnd_ratio"], i) if mode == "primary" else aux["cash_rnd_ratio"]
        sga = annual(b["cash_sga_ratio"], i) if mode == "primary" else aux["cash_sga_ratio"]
        sga += changes.get("cash_sga_ratio_shift", 0.0)
        cash_opex = revenue * (rnd + sga)
        sbc = annual(b["noncash_known_share_plan_cost"], i)
        ebit = revenue - cogs - loss - cash_opex - sbc
        taxable_operating = max(0.0, ebit + sbc + loss)
        tax = taxable_operating * b["cash_tax_rate"]
        nopat = ebit - tax
        ar_days = max(0.0, annual(wc["receivable_days"], i) + changes.get("receivable_days_shift", 0.0))
        inventory_days = max(0.0, annual(wc["inventory_days"], i) + changes.get("inventory_days_shift", 0.0))
        ap_days = max(0.0, annual(wc["ap_purchase_days"], i) + changes.get("ap_days_shift", 0.0))
        bill_days = max(0.0, annual(wc["bill_purchase_days"], i) + changes.get("bill_days_shift", 0.0))
        ar = revenue / 365.0 * ar_days
        inventory = production_cogs / 365.0 * inventory_days
        purchases = max(0.0, production_cash_cogs * wc["raw_material_share_of_cash_cogs"] + inventory - before["inventory"] + loss)
        vat_purchases = purchases * (1.0 + wc["input_vat_rate"] * wc["input_vat_applicable_share"])
        ap = vat_purchases / 365.0 * ap_days
        bills = vat_purchases / 365.0 * bill_days
        other_net = revenue * wc["other_operating_current_net_ratio"]
        contract = revenue * wc["contract_liability_ratio"]
        core_wc = ar + inventory + other_net - ap - bills - contract
        delta_core = core_wc - before["core_wc"] + loss
        project_cash_margin += annual(b["project_cash_guarantee_new"], i) - annual(b["project_cash_guarantee_release"], i)
        require(project_cash_margin >= -EPS, "Guarantee release exceeds posted cash")
        collateral_rate = changes.get("bill_collateral_ratio", wc["bill_collateral_ratio"])
        bank_margin_rate = changes.get("bank_guarantee_collateral_rate", b["bank_guarantee_collateral_rate"])
        collateral = bills * collateral_rate + project_cash_margin + annual(b["bank_guarantee_face"], i) * bank_margin_rate
        operating_cash = revenue * wc["minimum_operating_cash_ratio"]
        delta_support = collateral + operating_cash - before["collateral"] - before["operating_cash"]
        if mode == "primary":
            organic = b["organic_growth_capex"][i] if i < original_years else sum(transition_capital.values())
            cash_capex = depreciation + project_cash + organic
            new_book = depreciation + project_book + organic
            normalized_growth_reinvestment = None
        else:
            ng = changes.get("terminal_growth", aux["growth"])
            nr = changes.get("aux_explicit_return", aux["aux_explicit_return"])
            require(nr > ng >= 0.0, "Auxiliary growth/return incompatible")
            normalized_growth_reinvestment = max(0.0, nopat) * ng / nr
            required = depreciation + normalized_growth_reinvestment - delta_core - delta_support
            cash_capex = max(depreciation + project_cash, depreciation, required)
            organic = cash_capex - depreciation - project_cash
            new_book = depreciation + project_book + organic
        employee_cash = annual(b["future_employee_buyback_cash"], i)
        grant_cash = annual(b["future_employee_grant_cash_received"], i)
        employee_fees = annual(b["future_employee_buyback_transaction_fees"], i)
        fcff = nopat + depreciation + sbc + loss - cash_capex - delta_core - delta_support - employee_cash - employee_fees + grant_cash
        net_financial_yield = b["financial_yield_before_tax"] * (1.0 - b["financial_tax_rate"])
        financial_income = max(0.0, before["excess"]) * net_financial_yield
        strategic_income = before["strategic"] * b["strategic_cash_yield_after_tax"]
        cash_interest = before["debt"] * b["debt_interest_rate"]
        interest_tax_rate = b["cash_tax_rate"] if taxable_operating > EPS else 0.0
        interest_after_tax = cash_interest * (1.0 - interest_tax_rate)
        principal = min(before["debt"], initial_debt * annual(b["debt_principal_fraction_of_opening"], i))
        options = data["facts"]["rights"]["remaining_valid_options"] if year == b["option_exercise_year"] else 0.0
        option_cash = options * data["facts"]["rights"]["option_strike_cny"]
        shares = before["shares"] + options
        group_profit = nopat + financial_income + strategic_income - interest_after_tax
        excess_before_div = before["excess"] + fcff + financial_income + strategic_income - interest_after_tax - principal + option_cash
        mother_liquidity_begin = mother_liquidity_buckets(before["mother_cash"], before["excess"],
            before["operating_cash"], before["collateral"], p["minimum_cash"])
        mother_fin_income = mother_liquidity_begin["financial_cash"] * b["financial_yield_before_tax"] * (1.0 - p["own_financial_tax_rate"])
        mother_interest = interest_after_tax * opening["mother_debt_share"]
        mother_principal = principal * opening["mother_debt_share"]
        mother_sbc_fraction = changes.get("parent_sbc_fraction", p["known_plan_sbc_parent_expense_fraction"])
        require(0 <= mother_sbc_fraction <= 1, "Invalid scenario parent SBC allocation")
        mother_sbc = sbc * mother_sbc_fraction
        mother_own_cash = p["own_operating_profit_and_cash"] + mother_fin_income - mother_interest
        mother_own_profit = mother_own_cash - mother_sbc
        downstream = project_cash * p["downstream_capital_share_of_project_cash"]
        mother_direct_flow = (mother_own_profit + mother_sbc - mother_principal - downstream
                              - employee_cash - employee_fees + grant_cash + option_cash)
        mother_cash_before_receipts = before["mother_cash"] + mother_direct_flow
        sub_profit = group_profit - mother_own_profit
        upstream_ratio = changes.get("upstream_declaration_ratio", p["upstream_declaration_ratio"])
        require(upstream_ratio <= p["subsidiary_profit_available_fraction"] + EPS, "Upstream ratio exceeds available-profit allowance")
        declared = max(0.0, sub_profit) * upstream_ratio
        old_rate = changes.get("old_collection_fraction", p["old_dividend_receivable_collection_fraction"])
        new_rate = changes.get("current_collection_fraction", p["current_declared_dividend_collection_fraction"])
        request_old, request_current = before["mother_ar"] * old_rate, declared * new_rate
        mother_before_receipts_buckets = mother_liquidity_buckets(mother_cash_before_receipts,
            excess_before_div, operating_cash, collateral, p["minimum_cash"])
        subsidiary_available_cash = max(0.0, excess_before_div - mother_before_receipts_buckets["financial_cash"])
        received = min(request_old + request_current, subsidiary_available_cash)
        received_old = min(request_old, received)
        received_current = received - received_old
        mother_ar = before["mother_ar"] + declared - received
        mother_profit = declared + mother_own_profit
        mode_reserve = changes.get("reserve_mode", p["reserve_mode"])
        ten_percent = max(0.0, mother_profit) * 0.10
        if mode_reserve == "gap_capped":
            reserve_add = min(ten_percent, max(0.0, shares * 0.50 - before["mother_reserve"]))
        elif mode_reserve == "full_ten_percent":
            reserve_add = ten_percent
        else:
            raise ValueError("Unknown parent reserve mode")
        legal_available = before["mother_re"] + mother_profit - reserve_add
        mother_after_receipts_buckets = mother_liquidity_buckets(mother_cash_before_receipts + received,
            excess_before_div, operating_cash, collateral, p["minimum_cash"])
        mother_available = mother_after_receipts_buckets["ordinary_distribution_cash_capacity"]
        desired_dividend = p["ordinary_payout_target"] * max(0.0, group_profit)
        dividend = max(0.0, min(desired_dividend, legal_available, mother_available, excess_before_div))
        excess = excess_before_div - dividend
        mother_cash = mother_cash_before_receipts + received - dividend
        mother_re = legal_available - dividend
        mother_liquidity_end = mother_liquidity_buckets(mother_cash, excess, operating_cash, collateral, p["minimum_cash"])
        if mother_liquidity_end["unlocated_entity_bridge_amount"] > EPS:
            warnings.append({"year": year, "reason": "mother_entity_liquid_bridge_estimate_conflict",
                             "amount": mother_liquidity_end["unlocated_entity_bridge_amount"],
                             "scope": "Conditional entity estimate, excluded from interest/distributable buckets; no fictitious cash transfer, loss or group financing null"})
        sub_available_profit = max(0.0, sub_profit) * p["subsidiary_profit_available_fraction"] + min(0.0, sub_profit)
        subs_distributable = before["subs_distributable"] + sub_available_profit - declared
        fixed_end = before["fixed"] + new_book - depreciation
        capital_payables = before["capital_payables"] + project_book - project_cash
        debt_end = before["debt"] - principal
        if excess_before_div < -EPS:
            failures.append({"year": year, "reason": "unfunded_group_capital_or_credit_requirement", "gap": -excess_before_div})
        if mother_cash < -EPS:
            failures.append({"year": year, "reason": "mother_cash_negative_after_budgeted_upstream", "gap": -mother_cash})
        if mother_re < -EPS:
            failures.append({"year": year, "reason": "mother_distributable_profit_deficit", "gap": -mother_re})
        if subs_distributable < -EPS:
            failures.append({"year": year, "reason": "subsidiary_available_profit_deficit", "gap": -subs_distributable})
        if any(s["capacity_lost_sales"] > EPS for s in income["segments"]):
            warnings.append({"year": year, "reason": "capacity_proxy_limits_demand", "lost_sales": sum(s["capacity_lost_sales"] for s in income["segments"])})
        capital_before = before["fixed"] + before["core_wc"] + before["collateral"] + before["operating_cash"]
        capital_end = fixed_end + core_wc + collateral + operating_cash
        delta_capital = capital_end - capital_before
        previous_nopat = rows[-1]["nopat"] if rows else None
        incremental_return = ((nopat - previous_nopat) / delta_capital
                              if previous_nopat is not None and delta_capital > EPS else None)
        residuals = {
            "group_cash": near(excess, before["excess"] + fcff + financial_income + strategic_income - interest_after_tax - principal + option_cash - dividend, "group cash"),
            "mother_cash": near(mother_cash, before["mother_cash"] + mother_own_profit + mother_sbc - mother_principal - downstream - employee_cash - employee_fees + grant_cash + option_cash + received - dividend, "mother cash"),
            "mother_profit": near(mother_re, before["mother_re"] + declared + mother_own_profit - reserve_add - dividend, "mother RE"),
            "mother_receivable": near(mother_ar, before["mother_ar"] + declared - received, "mother dividend AR"),
            "shares": near(shares, before["shares"] + options, "shares"),
            "capital_payables": near(capital_payables, before["capital_payables"] + project_book - project_cash, "capital payable")
        }
        row = {
            "year": year, "period_end": f"{2026 + year}-10-31", "mode": mode,
            "phase": "original_explicit" if i < original_years else "finite_physical_transition",
            "project_in_service_capital_time_weighted": commissioned_average,
            "productive_capital_next_year": (opening["productive"] + sum(z["selected_budget"] * annual(z["in_service_fraction_end"], i) for z in projects) + organic_prior + organic),
            "transition_capacity_addition_by_segment": transition_addition,
            "transition_growth_capital_by_segment": transition_capital,
            "segments": income["segments"], "revenue": revenue, "cogs": cogs,
            "gross_margin": 1.0 - cogs / revenue if revenue > EPS else None,
            "reference_depreciation": reference_da, "depreciation": depreciation,
            "rou_amortization_and_cash_replacement": b["annual_rou_amortization"],
            "cash_opex": cash_opex, "known_plan_noncash_expense": sbc,
            "inventory_loss": loss, "ebit": ebit, "cash_operating_tax": tax, "nopat": nopat,
            "realized_pre_policy_price_revenue": income["realized_pre_policy_price_revenue"],
            "incremental_nonrefundable_cost": rebate_cost,
            "production_cogs_ex_policy_tax": production_cogs,
            "production_cash_cogs_for_supplier_credit": production_cash_cogs,
            "materials_purchases_ex_vat": purchases, "vat_inclusive_credit_purchase_base": vat_purchases,
            "receivables": ar, "inventory": inventory, "trade_payables": ap, "bills_payable": bills,
            "contract_liabilities": contract, "other_operating_net_assets": other_net,
            "core_wc": core_wc, "delta_core_wc_cash": delta_core,
            "required_collateral": collateral, "minimum_operating_cash": operating_cash,
            "delta_cash_support": delta_support, "project_cash_guarantee_balance": project_cash_margin,
            "project_cash_capex": project_cash, "project_book_addition": project_book,
            "maintenance_capex": depreciation, "organic_growth_capex": organic,
            "cash_capex": cash_capex, "fixed_operating_capital_end": fixed_end,
            "capital_payables_end": capital_payables, "operating_capital_end": capital_end,
            "incremental_operating_return_same_period": incremental_return,
            "incremental_return_note": None if incremental_return is not None else "First year or nonpositive capital change; not a project return observation",
            "normalized_growth_reinvestment": normalized_growth_reinvestment,
            "employee_buyback_cash": employee_cash, "employee_buyback_transaction_fees": employee_fees,
            "employee_grant_cash_received": grant_cash,
            "fcff": fcff, "financial_income": financial_income, "strategic_income": strategic_income,
            "interest_before_tax": cash_interest, "interest_after_tax": interest_after_tax,
            "debt_principal_paid": principal, "debt_begin": before["debt"], "debt_end": debt_end,
            "excess_financial_begin": before["excess"], "excess_financial_before_dividend": excess_before_div,
            "excess_financial_end": excess, "strategic_assets": before["strategic"],
            "minority_value_bridge": before["minority_value_bridge"],
            "actual_group_liquid_pool_end": excess + operating_cash + collateral,
            "group_accounting_profit": group_profit, "option_cash": option_cash,
            "options_exercised": options, "shares_begin": before["shares"], "shares_end": shares,
            "desired_dividend": desired_dividend, "ordinary_cash_dividend": dividend,
            "dividend_per_share": dividend / shares,
            "mother_cash_begin": before["mother_cash"], "mother_cash_end": mother_cash,
            "mother_financial_income": mother_fin_income,
            "mother_liquidity_begin": mother_liquidity_begin,
            "mother_liquidity_before_receipts": mother_before_receipts_buckets,
            "mother_liquidity_after_receipts": mother_after_receipts_buckets,
            "mother_liquidity_end": mother_liquidity_end,
            "mother_own_accounting_profit": mother_own_profit, "mother_own_cash_before_share_plan": mother_own_cash,
            "mother_known_plan_noncash_expense": mother_sbc, "mother_known_plan_expense_fraction": mother_sbc_fraction,
            "mother_employee_buyback_cash": employee_cash, "mother_employee_buyback_transaction_fees": employee_fees,
            "mother_employee_grant_cash_received": grant_cash, "mother_direct_cash_flow": mother_direct_flow,
            "mother_cash_before_internal_receipts": mother_cash_before_receipts, "mother_debt_principal": mother_principal,
            "mother_downstream_capital": downstream, "subsidiary_profit": sub_profit,
            "subsidiary_dividend_declared": declared, "mother_old_dividend_received": received_old,
            "mother_current_dividend_received": received_current, "mother_dividend_cash_received": received,
            "mother_dividend_receivable_end": mother_ar, "mother_retained_earnings_end": mother_re,
            "mother_reserve_addition": reserve_add, "mother_reserve_end": before["mother_reserve"] + reserve_add,
            "mother_legal_available_before_dividend": legal_available,
            "mother_cash_available_before_dividend": mother_available,
            "subsidiary_distributable_reserves_end": subs_distributable,
            "distribution_constrained": dividend + EPS < desired_dividend,
            "residuals": residuals
        }
        rows.append(row)
        state.update({"excess": excess, "collateral": collateral, "operating_cash": operating_cash,
                      "core_wc": core_wc, "inventory": inventory, "fixed": fixed_end, "debt": debt_end,
                      "shares": shares, "mother_cash": mother_cash, "mother_re": mother_re,
                      "mother_ar": mother_ar, "mother_reserve": before["mother_reserve"] + reserve_add,
                      "subs_distributable": subs_distributable, "capital_payables": capital_payables})
        organic_prior += organic
        for sid, addition in transition_addition.items():
            capacity_stock[sid] += addition
    near(state["capital_payables"], 0.0, "all scheduled old capital payables settled")
    require(state["debt"] <= EPS, "Unmodeled financing debt survives forecast horizon")
    result = {"mode": mode, "opening": opening, "rows": rows, "state": state,
              "economic_feasible": not failures, "economic_failures": failures, "warnings": warnings,
              "parent_entity_cash_bridge_conditional": any(w["reason"] == "mother_entity_liquid_bridge_estimate_conflict" for w in warnings),
              "capacity_installed_at_horizon": capacity_stock,
              "original_explicit_years": original_years, "finite_transition_years": transition_years}
    if not failures:
        try:
            result["valuation"] = value_method(data, changes, result, mode)
        except EconomicInfeasible as exc:
            result["economic_feasible"] = False
            result["economic_failures"].append({"year": len(rows), "reason": str(exc)})
            result["valuation"] = {"equity_value": None, "value_per_share": None, "reason": str(exc)}
    else:
        result["valuation"] = {"equity_value": None, "value_per_share": None,
                               "reason": "Unfunded operating/parent path; no implicit borrowing or fictitious distributions"}
    return result


def terminal_components(data, changes, result, mode, override=None):
    b, last = data["base"], result["rows"][-1]
    terminal, norm = b["terminal"], b["auxiliary"]
    r = changes.get("cost_of_equity", b["cost_of_equity"])
    g = changes.get("terminal_growth", terminal["growth"] if mode == "primary" else norm["growth"])
    conditional_return = changes.get("terminal_return")
    normalized_return = changes.get("terminal_return", norm["incremental_operating_return"])
    if override:
        r, g = override["cost_of_equity"], override["terminal_growth"]
        conditional_return = override.get("terminal_return", conditional_return)
        normalized_return = override.get("terminal_return", normalized_return)
    require(r > g >= 0, "Incompatible mature growth/discount assumptions")
    physical_tail = None
    if mode == "primary":
        physical_tail = mature_physical_cash_tail(data, changes, result, r, g, conditional_return)
        mature_nopat = physical_tail["first_mature_nopat"]
        reinvestment = physical_tail["first_mature_reinvestment"]
        operating_terminal = physical_tail["operating_terminal"]
        roc = physical_tail["asymptotic_cash_reinvestment_implied_return"]
    else:
        roc = normalized_return
        require(roc > g, "Normalized mature return/growth incompatible")
        mature_nopat = last["nopat"] * (1.0 + g)
        if mature_nopat <= 0:
            raise EconomicInfeasible("Normalized mature operating losses need an explicit exit model")
        reinvestment = mature_nopat * g / roc
        operating_terminal = (mature_nopat - reinvestment) / (r - g)
    excess, strategic, debt = last["excess_financial_end"], last["strategic_assets"], last["debt_end"]
    minority_value = last["minority_value_bridge"]
    # This is only a declared budget partition, never a finding of legal lockup.
    proxy = max(0.0, last["mother_retained_earnings_end"]) + max(0.0, last["subsidiary_distributable_reserves_end"])
    e_fast = min(max(0.0, excess), proxy)
    a_fast = min(strategic, max(0.0, proxy - e_fast))
    e_slow, a_slow = excess - e_fast, strategic - a_fast
    y = b["financial_yield_before_tax"] * (1.0 - b["financial_tax_rate"])
    ya = b["strategic_cash_yield_after_tax"]
    lag_e, lag_a, lag_long = terminal["surplus_realization_lag_years"], terminal["strategic_asset_realization_lag_years"], terminal["long_realization_lag_years"]
    all_short = (excess * ((1.0 + y) / (1.0 + r)) ** lag_e
                 + strategic * ((1.0 + ya) / (1.0 + r)) ** lag_a - debt - minority_value)
    budget_split = (e_fast * ((1.0 + y) / (1.0 + r)) ** lag_e
                    + e_slow * ((1.0 + y) / (1.0 + r)) ** lag_long
                    + a_fast * ((1.0 + ya) / (1.0 + r)) ** lag_a
                    + a_slow * ((1.0 + ya) / (1.0 + r)) ** lag_long - debt - minority_value)
    return {"r": r, "growth": g, "incremental_operating_return": roc,
            "return_definition": "Primary: asymptotic NOPAT*g/net operating reinvestment from physical capital mechanism; normalized: separate declared mature return. Not observed annual project ROI.",
            "mature_nopat": mature_nopat, "mature_reinvestment": reinvestment,
            "operating_terminal": operating_terminal, "physical_cash_tail": physical_tail,
            "financial_book_value_at_horizon": excess + strategic - debt - minority_value,
            "minority_value_bridge": minority_value,
            "hypothetical_waiting_financial_terminal": all_short,
            "budget_split_waiting_financial_terminal": budget_split,
            "terminal_budget_profit_proxy_not_legal_capacity": proxy,
            "budget_partition": {"cash_short": e_fast, "cash_long": e_slow,
                                 "strategic_short": a_fast, "strategic_long": a_slow},
            "financial_surplus_long_lag_amount": e_slow + a_slow,
            "sensitivity_only_realization_lags": {"cash": lag_e, "strategic": lag_a, "budget_retained_not_legal": lag_long},
            "waiting_scope": "Two noncore hypothetical diagnostics: all-short and explicit budget-proxy split. No proof of statutory lock, actual liquidation date or principal impairment."}


def value_method(data, changes, result, mode, override=None, at_year=0):
    rows, initial = result["rows"], result["opening"]
    terminal = terminal_components(data, changes, result, mode, override)
    r, n = terminal["r"], len(rows)
    require(0 <= at_year < n, "Valuation date outside explicit horizon")
    dividends_pv = sum(x["ordinary_cash_dividend"] / (1.0 + r) ** (x["year"] - at_year)
                       for x in rows if x["year"] > at_year)
    terminal_discount = (1.0 + r) ** (n - at_year)
    future_rows = [x for x in rows if x["year"] > at_year]
    pv_fcff = sum(x["fcff"] / (1.0 + r) ** (x["year"] - at_year) for x in future_rows)
    pv_options = sum(x["option_cash"] / (1.0 + r) ** (x["year"] - at_year) for x in future_rows)
    if at_year == 0:
        financial_bridge = initial["excess"] + initial["strategic"] - initial["debt"] - initial["minority_value_bridge"]
    else:
        state_at_date = rows[at_year - 1]
        financial_bridge = (state_at_date["excess_financial_end"] + state_at_date["strategic_assets"]
                            - state_at_date["debt_end"] - state_at_date["minority_value_bridge"])
    equity = pv_fcff + terminal["operating_terminal"] / terminal_discount + financial_bridge + pv_options
    waiting_equity = dividends_pv + (terminal["operating_terminal"] + terminal["hypothetical_waiting_financial_terminal"]) / terminal_discount
    split_waiting_equity = dividends_pv + (terminal["operating_terminal"] + terminal["budget_split_waiting_financial_terminal"]) / terminal_discount
    shares = rows[-1]["shares_end"]
    result_value = {"equity_value": equity, "value_per_share": equity / shares,
                    "at_year": at_year, "dividend_present_value_diagnostic_not_core_component": dividends_pv,
                    "operating_fcff_present_value": pv_fcff,
                    "at_date_attributable_net_financial_bridge": financial_bridge,
                    "option_proceeds_present_value": pv_options,
                    "operating_terminal_present_value": terminal["operating_terminal"] / terminal_discount,
                    "terminal_present_value_fraction": (terminal["operating_terminal"]
                                                        / terminal_discount / equity) if abs(equity) > EPS else None,
                    "waiting_sensitivity": {"equity_value": waiting_equity, "value_per_share": waiting_equity / shares,
                                            "difference_from_core": waiting_equity - equity,
                                            "scope": "Explicit hypothetical future waiting; not default haircut of financial principal or actual capital destruction"},
                    "budget_split_waiting_sensitivity": {"equity_value": split_waiting_equity,
                        "value_per_share": split_waiting_equity / shares, "difference_from_core": split_waiting_equity - equity,
                        "scope": "Explicit budget-proxy two-bucket waiting, NOT legal delay; no effect on core/holder"},
                    "diluted_shares": shares, "terminal": terminal}
    if at_year == 0:
        discount = lambda x: (1.0 + r) ** (-x["year"])
        core = equity
        adjustment = sum((x["financial_income"] + x["strategic_income"] - x["interest_after_tax"]
                          - r * (x["excess_financial_begin"] + x["strategic_assets"] - x["debt_begin"] - x["minority_value_bridge"]))
                         * discount(x) for x in rows)
        last = rows[-1]
        adjustment += (terminal["hypothetical_waiting_financial_terminal"] - (last["excess_financial_end"] + last["strategic_assets"] - last["debt_end"] - last["minority_value_bridge"])) / terminal_discount
        residual = near(waiting_equity, core + adjustment, "hypothetical waiting sensitivity cash identity")
        split_adjustment = adjustment + (terminal["budget_split_waiting_financial_terminal"] - terminal["hypothetical_waiting_financial_terminal"]) / terminal_discount
        split_residual = near(split_waiting_equity, core + split_adjustment, "budget split waiting cash identity")
        last_investment = last["cash_capex"] - last["depreciation"] + last["delta_core_wc_cash"] + last["delta_cash_support"]
        reinvestment_step = ((terminal["mature_reinvestment"] - last_investment) / abs(last_investment)
                            if abs(last_investment) > EPS else None)
        result_value.update({"operating_fcff_present_value": pv_fcff,
                             "opening_attributable_net_financial_bridge": financial_bridge,
                             "option_proceeds_present_value": pv_options,
                             "core_operating_dcf_plus_financial_bridge": core,
                             "hypothetical_waiting_adjustment_not_core": adjustment,
                             "hypothetical_waiting_identity_residual": residual,
                             "budget_split_waiting_adjustment_not_core": split_adjustment,
                             "budget_split_waiting_identity_residual": split_residual,
                             "year_last_net_operating_investment": last_investment,
                             "mature_reinvestment_step_fraction": reinvestment_step,
                             "maturity_transition_requires_explanation": reinvestment_step is None or abs(reinvestment_step) > 0.25})
    return result_value


def run_scenario(data, scenario):
    primary = run_method(data, scenario, "primary")
    normalized = run_method(data, scenario, "normalized")
    main_value = primary["valuation"]["equity_value"]
    aux_value = normalized["valuation"]["equity_value"]
    gap = abs(main_value - aux_value) / abs(main_value) if main_value is not None and aux_value is not None and abs(main_value) > EPS else None
    return {"id": scenario["id"], "kind": scenario["kind"], "changes": scenario["changes"],
            "primary": primary, "normalized": normalized, "method_gap_fraction": gap,
            "method_gap_requires_economic_explanation": gap is None or gap > 0.25,
            "method_gap_note": "No averaging: primary forecasts product growth/capacity; auxiliary starts at90% normalized scale and independent margins, retains signed capital cash. Compare growth-stage value, recurrent margin, committed investment and idle-finance cost."}


def make_return_model(data, base_result):
    primary = base_result["primary"]
    if not primary["economic_feasible"]:
        return {"return_model": None, "return_model_note": "Base path funding/parent constraints not feasible: " + json.dumps(primary["economic_failures"], ensure_ascii=False)}
    bounds = {}
    for k in [3, 5]:
        low = value_method(data, {}, primary, "primary", data["terminal_value_bounds"]["lower"], k)["value_per_share"]
        high = value_method(data, {}, primary, "primary", data["terminal_value_bounds"]["upper"], k)["value_per_share"]
        require(low <= high + EPS, "Terminal endpoint order inverted; do not sort away economics")
        bounds[f"year_{k}"] = {"low": low, "high": high}
    model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
             "model_as_of": data["information_cutoff"],
             "base_case_distributions_per_share": [x["dividend_per_share"] for x in primary["rows"][:5]],
             "base_case_terminal_equity_value_range_per_share": bounds}
    require(len(model["base_case_distributions_per_share"]) == 5, "V1 needs exactly five cash distributions")
    return {"return_model": model,
            "parent_entity_cash_bridge_conditional": primary["parent_entity_cash_bridge_conditional"],
            "return_model_note": "Annual cash after cutoff, not accounting profit or market buybacks. Already paid1.60yuan excluded. Separate year3/year5 remaining original plus finite-transition operating FCFF/physical terminal DCF plus that year's post-distribution financial assets/net debt; no default operating-rate haircut or artificial horizon liquidation of cash. Reinvestment explicit. Fully restored employee-treasury rights and paired option proceeds/shares. Waiting cases are separate noncore sensitivities. No market-price IRR. Upstream, capital scope and pass-through are budgets, not declared commitments."}


def check_hand_case(data, result):
    oracle = data.get("closed_form_oracle")
    if oracle is None:
        return {"status": "NOT_REQUESTED", "note": "Formal hand case must be separately executed with hand-case.json in the same chain."}
    profit = oracle["R"] * (oracle["gross_margin"] - oracle["cash_rnd"] - oracle["cash_sga"])
    r, c, shares, n = oracle["r"], oracle["C"], oracle["S"], oracle["N"]
    expected = (profit / r + c) / shares
    expected_waiting = (profit / r + c / (1.0 + r) ** n) / shares
    residuals = {}
    for method in ["primary", "normalized"]:
        outcome = result[method]
        require(outcome["economic_feasible"], "Closed-form case became infeasible")
        residuals[method + "_current"] = near(outcome["valuation"]["value_per_share"], expected, "independent closed form current")
        residuals[method + "_waiting_only"] = near(outcome["valuation"]["waiting_sensitivity"]["value_per_share"], expected_waiting, "independent closed form noncore waiting")
        for row in outcome["rows"]:
            near(row["fcff"], profit, "closed-form formal FCFF")
            near(row["ordinary_cash_dividend"], profit, "closed-form formal dividend")
            near(row["excess_financial_end"], c, "closed-form financial balance")
        for k in [3, 5]:
            expected_k = (profit / r + c) / shares
            actual_k = value_method(data, {}, outcome, method, at_year=k)["value_per_share"]
            residuals[f"{method}_year{k}"] = near(actual_k, expected_k, "independent closed form future value")
    boundary = check_boundary_cases(data)
    combined_boundary = check_combined_v2_boundaries(data)
    return {"status": "EXECUTED_SAME_FORMAL_CHAIN_MATCHES_CLOSED_FORM", "expected_current_per_share": expected,
            "residuals": residuals, "policy_and_parent_boundary_cases": boundary,
            "combined_v2_boundaries": combined_boundary, "note": "Formula oracle uses only R,m,a,b,C,S,N,r; no company-model intermediate or output reused as expected result. This is producer self-check, not independent certification."}



def check_boundary_cases(data):
    """Authorized-run self-check only: variants use the identical formal chain."""
    contract = data.get("closed_form_boundary_contract")
    if contract is None:
        return {"status": "NOT_REQUESTED"}
    oracle = data["closed_form_oracle"]
    profit = oracle["R"] * (oracle["gross_margin"] - oracle["cash_rnd"] - oracle["cash_sga"])
    n, cases, residuals = data["base"]["years"], {}, {}
    r1 = contract["R1"]
    for pass_fraction in r1["pass_through_fractions"]:
        paired = []
        for rate in r1["loss_rates"]:
            d = copy.deepcopy(data)
            b = d["base"]
            b["segments"][0]["rebate_exposure"] = True
            b["battery_policy"].update({"export_share": [1.0] * n,
                "china_origin_share_of_export": [1.0] * n, "eligible_customs_code_share": [1.0] * n,
                "incremental_rebate_loss_rate": [rate] * n, "price_elasticity": r1["price_elasticity"],
                "pass_through_fraction": pass_fraction})
            b["working_capital"].update({"inventory_days": [r1["inventory_days"]] * n,
                "ap_purchase_days": [r1["ap_days"]] * n, "bill_purchase_days": [r1["bill_days"]] * n,
                "input_vat_rate": r1["input_vat_rate"], "input_vat_applicable_share": r1["input_vat_applicable_share"]})
            b["auxiliary"].update({"battery_export_share": 1.0, "incremental_rebate_loss_rate": rate})
            label = f"R1_pass_{pass_fraction}_loss_{rate}"
            outcome = run_scenario(d, {"id": label, "kind": "formal_boundary", "changes": {}})
            cases[label] = outcome
            paired.append(outcome)
        low, high = paired
        for mode in ["primary", "normalized"]:
            require(low[mode]["economic_feasible"] and high[mode]["economic_feasible"], "R1 boundary infeasible")
            for a, z in zip(low[mode]["rows"], high[mode]["rows"]):
                for field in ["reference_depreciation", "production_cogs_ex_policy_tax",
                              "production_cash_cogs_for_supplier_credit", "inventory",
                              "materials_purchases_ex_vat", "vat_inclusive_credit_purchase_base",
                              "trade_payables", "bills_payable"]:
                    near(a[field], z[field], "R1 policy tax cannot create procurement/credit: " + field)
                delta = ((z["revenue"] - a["revenue"]) * (1.0 - oracle["cash_rnd"] - oracle["cash_sga"])
                         - (z["incremental_nonrefundable_cost"] - a["incremental_nonrefundable_cost"]))
                near(z["ebit"] - a["ebit"], delta, "R1 real price/tax operating burden")
                near(z["fcff"] - a["fcff"], delta, "R1 cash burden not financed by fictitious AP")
        residuals[f"R1_pass_{pass_fraction}"] = "ALL_FORMAL_YEARLY_INVARIANTS_MATCH"
    r2 = contract["R2"]
    for fraction in r2["parent_expense_fractions"]:
        d = copy.deepcopy(data)
        b, rights = d["base"], d["facts"]["rights"]
        rights["buyback_cash_oct15_ex_fees"] = r2["opening_buyback_cash"]
        b["opening_estimates"]["oct_share_transaction_fees"] = r2["opening_fees"]
        for key, value in [("future_employee_buyback_cash", r2["first_year_buyback_cash"]),
                           ("future_employee_buyback_transaction_fees", r2["first_year_fees"]),
                           ("future_employee_grant_cash_received", r2["first_year_grant_cash"]),
                           ("noncash_known_share_plan_cost", r2["first_year_sbc"])]:
            b[key] = [value] + [0.0] * (n - 1)
        b["parent"]["known_plan_sbc_parent_expense_fraction"] = fraction
        label = f"R2_parent_expense_{fraction}"
        outcome = run_scenario(d, {"id": label, "kind": "formal_boundary", "changes": {}})
        cases[label] = outcome
        for mode in ["primary", "normalized"]:
            result = outcome[mode]
            require(result["economic_feasible"], "R2 boundary infeasible")
            opening, row = result["opening"], result["rows"][0]
            cash0 = oracle["C"] - r2["opening_buyback_cash"] - r2["opening_fees"]
            direct = -r2["first_year_buyback_cash"] - r2["first_year_fees"] + r2["first_year_grant_cash"]
            near(opening["excess"], cash0, "R2 group opening buyback once")
            near(opening["mother_cash"], cash0, "R2 mother opening same outflow subset")
            near(opening["mother_re"], d["facts"]["h1_parent"]["retained_earnings"], "R2 buyback principal/fee not RE expense")
            near(row["fcff"], profit + direct, "R2 group actual employee cash once")
            near(row["mother_direct_cash_flow"], direct, "R2 issuer direct cash subset")
            near(row["mother_own_accounting_profit"], -fraction * r2["first_year_sbc"], "R2 parent noncash allocation")
            near(row["subsidiary_profit"], profit - (1.0 - fraction) * r2["first_year_sbc"], "R2 subsidiary allocation")
            near(row["group_accounting_profit"], profit - r2["first_year_sbc"], "R2 group SBC once")
        residuals[label] = "GROUP_AND_MOTHER_SAME_OUTFLOW_NOT_ADDITIVE"
    q3 = contract.get("Q3")
    if q3 is not None:
        compared = []
        variants = [(q3["mother_total_cash"], nci) for nci in q3["nci_values"]]
        variants.append((q3["unknown_entity_mother_cash"], q3["nci_values"][0]))
        for mother_total, nci in variants:
            d = copy.deepcopy(data)
            d["facts"]["q3"].update({"cash": q3["group_cash"],
                "cash_equivalents": q3["group_cash_equivalents"], "minority_equity": nci})
            d["facts"]["h1_parent"]["cash"] = mother_total
            d["base"]["working_capital"]["minimum_operating_cash_ratio"] = q3["operating_cash_ratio"]
            d["base"].update({"financial_yield_before_tax": q3["financial_yield"],
                               "financial_tax_rate": q3["group_financial_tax"]})
            d["base"]["parent"].update({"minimum_cash": q3["mother_minimum_cash"],
                "own_financial_tax_rate": q3["mother_financial_tax"]})
            label = f"Q3_mother_{mother_total}_nci_{nci}"
            outcome = run_scenario(d, {"id": label, "kind": "formal_boundary", "changes": {}})
            cases[label] = outcome
            cash_support = q3["group_cash"] - q3["group_cash_equivalents"]
            operating_cash = oracle["R"] * q3["operating_cash_ratio"]
            excess = q3["group_cash"] - cash_support - operating_cash
            priority = min(mother_total, q3["mother_minimum_cash"], operating_cash)
            financial = min(mother_total - priority, excess)
            for mode in ["primary", "normalized"]:
                result = outcome[mode]
                opening, first = result["opening"], result["rows"][0]
                near(opening["excess"], excess, "Q3 NCI not actual cash deduction")
                near(opening["mother_cash"], mother_total, "Q3 classification preserves mother principal")
                near(opening["mother_liquidity"]["financial_cash"], financial, "Q3 correct financial bucket")
                near(opening["mother_liquidity"]["ordinary_distribution_cash_capacity"], financial,
                     "Q3 minimum already in B must not be reserved twice")
                near(first["mother_financial_income"], financial * q3["financial_yield"] * (1.0 - q3["mother_financial_tax"]),
                     "Q3 interest only on mother financial bucket")
                if mother_total == q3["unknown_entity_mother_cash"]:
                    require(result["parent_entity_cash_bridge_conditional"], "Q3 entity bridge conflict not flagged")
                    require(all(z["reason"] != "mother_entity_liquid_bridge_estimate_conflict"
                                for z in result["economic_failures"]), "Q3 estimate conflict mislabeled financing null")
                else:
                    require(result["economic_feasible"], "Q3 identified cash-boundary case infeasible")
            if mother_total == q3["mother_total_cash"]:
                compared.append((d, outcome, nci))
            residuals[label] = "PRINCIPAL_PRESERVED_AND_MINIMUM_NOT_DOUBLE_RESERVED"
        low_data, low, low_nci = compared[0]
        high_data, high, high_nci = compared[1]
        for mode in ["primary", "normalized"]:
            for a, z in zip(low[mode]["rows"], high[mode]["rows"]):
                for field in ["excess_financial_end", "mother_cash_end", "financial_income",
                              "mother_financial_income", "ordinary_cash_dividend"]:
                    near(a[field], z[field], "Q3 NCI cannot change actual cash: " + field)
            near(high[mode]["valuation"]["equity_value"] - low[mode]["valuation"]["equity_value"],
                 -(high_nci - low_nci), "Q3 current ordinary bridge NCI once")
            for k in [3, 5]:
                low_value = value_method(low_data, {}, low[mode], mode, at_year=k)["equity_value"]
                high_value = value_method(high_data, {}, high[mode], mode, at_year=k)["equity_value"]
                near(high_value - low_value, -(high_nci - low_nci), "Q3 future ordinary bridge NCI once")
    return {"status": "EXECUTED_FORMAL_BOUNDARIES_MATCH", "residuals": residuals,
            "complete_formal_case_results": cases,
            "note": "Author self-check only, not independent certification. No boundary runs occur during AST/compile."}



def share_plan_allocation_diagnostic(results):
    if not {"sbc_parent_zero", "sbc_parent_full"}.issubset(results):
        return {"status": "NOT_REQUESTED"}
    output = {}
    for mode in ["primary", "normalized"]:
        zero, full = results["sbc_parent_zero"][mode], results["sbc_parent_full"][mode]
        comparison = []
        for a, z in zip(zero["rows"], full["rows"]):
            fields = ["group_accounting_profit", "subsidiary_profit", "mother_own_accounting_profit",
                      "subsidiary_dividend_declared", "mother_retained_earnings_end",
                      "mother_cash_end", "ordinary_cash_dividend", "dividend_per_share"]
            comparison.append({"year": a["year"], "zero_parent_expense": {k: a[k] for k in fields},
                               "full_parent_expense": {k: z[k] for k in fields},
                               "full_minus_zero": {k: z[k] - a[k] for k in fields}})
        output[mode] = {"zero_path_economic_feasible": zero["economic_feasible"],
                        "full_path_economic_feasible": full["economic_feasible"], "years": comparison}
    return {"status": "EXECUTED_SAME_CHAIN_ENTITY_ALLOCATION_DIAGNOSTIC", "methods": output,
            "note": "No presumption that100% issuer expense is conservative. Future group financial income can differ if actual dividends differ; operating SBC is counted once in either allocation."}


def check_combined_v2_boundaries(data):
    contract = data.get("combined_v2_boundary_contract")
    if contract is None:
        return {"status": "NOT_REQUESTED"}
    n, cases, notes = data["base"]["years"], {}, {}
    fixture = contract["commissioning"]
    d = copy.deepcopy(data)
    d["facts"]["q3"]["ppe"] = fixture["total_fixed_book"] - fixture["project_book"]
    d["facts"]["q3"]["cip"] = fixture["project_book"]
    amount = fixture["project_book"]
    d["base"]["projects"] = [{"id": "timing_fixture", "fixed_capital_budget": amount,
        "budget_low": amount, "budget_high": amount, "opening_capital_book": amount,
        "opening_cash_paid": amount, "remaining_cash_weights": [1.0] + [0.0] * (n-1),
        "new_book_weights": [1.0] + [0.0] * (n-1), "in_service_fraction_end": [1.0] * n,
        "in_service_capital_time_weight": [fixture["first_year_capital_time"]] + [1.0] * (n-1),
        "effective_sales_capacity_weight": [fixture["first_year_effective_capacity"]] + [1.0] * (n-1),
        "revenue_capacity_2026_prices": {"test": fixture["project_capacity"]}}]
    outcome = run_scenario(d, {"id": "v2_commissioning", "kind": "formal_boundary", "changes": {}})
    cases["commissioning"] = outcome
    expected_da = ((fixture["total_fixed_book"] - amount + amount * fixture["first_year_capital_time"])
                   * d["base"]["depreciation_rate_on_productive_capital"])
    for mode in ["primary", "normalized"]:
        near(outcome[mode]["rows"][0]["depreciation"], expected_da, "v2 project capital-time DA, no second averaging")
    expected_capacity = ((d["base"]["capacity_proxy_existing"]["test"]
                          + fixture["project_capacity"] * fixture["first_year_effective_capacity"])
                         * d["base"]["capacity_proxy_max_utilization"])
    near(outcome["primary"]["rows"][0]["segments"][0]["sales_capacity_proxy"], expected_capacity,
         "v2 annual sales ramp distinct from capital time")
    notes["commissioning"] = "FORMAL_ROWS_MATCH_INPUT_ONLY_TIME_WEIGHT_ORACLES"
    d = copy.deepcopy(data)
    d["base"]["auxiliary"]["growth"] = contract["return_scope"]["aux_growth"]
    low = run_scenario(d, {"id": "v2_terminal_low", "kind": "formal_boundary",
                           "changes": {"terminal_return": contract["return_scope"]["terminal_low"]}})
    high = run_scenario(d, {"id": "v2_terminal_high", "kind": "formal_boundary",
                            "changes": {"terminal_return": contract["return_scope"]["terminal_high"]}})
    explicit = run_scenario(d, {"id": "v2_aux_explicit", "kind": "formal_boundary",
                                "changes": {"aux_explicit_return": contract["return_scope"]["aux_explicit_pressure"]}})
    cases.update({"terminal_low": low, "terminal_high": high, "aux_explicit_pressure": explicit})
    for mode in ["primary", "normalized"]:
        for a, z in zip(low[mode]["rows"], high[mode]["rows"]):
            for field in ["depreciation", "nopat", "cash_capex", "fcff", "ordinary_cash_dividend", "mother_retained_earnings_end"]:
                near(a[field], z[field], "v2 pure terminal return must not alter explicit state: " + field)
    require(abs(explicit["normalized"]["rows"][0]["normalized_growth_reinvestment"]
                - low["normalized"]["rows"][0]["normalized_growth_reinvestment"]) > EPS,
            "v2 explicit auxiliary pressure did not enter its own required investment")
    notes["return_scope"] = "PURE_TERMINAL_PRESERVES_EXPLICIT; EXPLICIT_AUXILIARY_OVERRIDE_DISTINCT"
    d = copy.deepcopy(data)
    oracle = contract["physical_growth"]
    d["facts"]["q3"].update({"ppe": 0.0, "cip": 0.0})
    d["base"].update({"depreciation_rate_on_productive_capital": 0.0,
                       "reference_accounting_depreciation_ratio": 0.0})
    d["base"]["maturity_transition"]["years"] = oracle["fade_years"]
    d["base"]["terminal"]["growth"] = oracle["growth"]
    growth_case = run_scenario(d, {"id": "v2_physical_growth", "kind": "formal_boundary", "changes": {}})
    efficient_case = run_scenario(d, {"id": "v2_mature_efficiency", "kind": "formal_boundary",
                                     "changes": {"terminal_return": oracle["conditional_return"]}})
    cases.update({"physical_growth": growth_case, "mature_efficiency": efficient_case})
    original = data["closed_form_oracle"]
    revenue = original["R"]
    for j in range(1, oracle["fade_years"] + 1):
        revenue *= 1.0 + oracle["growth"] * j / oracle["fade_years"]
    next_revenue = revenue * (1.0 + oracle["growth"])
    margin = original["gross_margin"] - original["cash_rnd"] - original["cash_sga"]
    productivity = d["base"]["maturity_transition"]["future_capacity_per_capital"]
    expected = next_revenue * (margin - oracle["growth"] / productivity) / (original["r"] - oracle["growth"])
    expected_condition = next_revenue * margin * (1.0 - oracle["growth"] / oracle["conditional_return"]) / (original["r"] - oracle["growth"])
    near(growth_case["primary"]["valuation"]["terminal"]["operating_terminal"], expected,
         "v2 input-only closed growing physical-capital terminal oracle")
    near(efficient_case["primary"]["valuation"]["terminal"]["operating_terminal"], expected_condition,
         "v2 conditional capital efficiency REPLACES same growth mechanism")
    require(len(growth_case["primary"]["rows"]) == n + oracle["fade_years"], "v2 finite fade length mismatch")
    for a, z in zip(growth_case["primary"]["rows"], efficient_case["primary"]["rows"]):
        near(a["fcff"], z["fcff"], "v2 conditional mature efficiency must preserve seven-year plus fade prefix")
        near(a["cash_capex"], z["cash_capex"], "v2 conditional mature efficiency must not rewrite funded prefix")
    notes["physical_growth"] = "FORMAL_CAPITAL_CASH_CHAIN_MATCHES_INPUT_ONLY_GROWING_PERPETUITY_ORACLE"
    d = copy.deepcopy(data)
    wait = contract["waiting_partition"]
    d["facts"]["h1_parent"]["retained_earnings"] = 0.0
    d["base"]["parent"]["subsidiary_distributable_open"] = 0.0
    d["facts"]["q3"]["other_noncurrent_financial_assets"] = wait["strategic_principal"]
    d["base"]["terminal"].update({"surplus_realization_lag_years": wait["short_lag"],
        "strategic_asset_realization_lag_years": wait["short_lag"], "long_realization_lag_years": wait["long_lag"]})
    outcome = run_scenario(d, {"id": "v2_waiting_partition", "kind": "formal_boundary", "changes": {}})
    cases["waiting_partition"] = outcome
    r = original["r"]
    delta = ((original["C"] + wait["strategic_principal"])
             * ((1.0 + r) ** (-wait["short_lag"]) - (1.0 + r) ** (-wait["long_lag"]))
             / (1.0 + r) ** n)
    for mode in ["primary", "normalized"]:
        val = outcome[mode]["valuation"]
        near(val["waiting_sensitivity"]["equity_value"] - val["budget_split_waiting_sensitivity"]["equity_value"],
             delta, "v2 saved-state waiting bucket closed oracle, not legal assertion")
        near(val["equity_value"], original["R"] * margin / r + original["C"] + wait["strategic_principal"],
             "v2 waiting buckets do not alter core cash/principal")
    notes["waiting_partition"] = "TWO_EXPLICIT_HYPOTHESES_DISTINCT_BUT_CORE_UNCHANGED"
    return {"status": "EXECUTED_COMBINED_V2_SAME_CHAIN_BOUNDARIES", "checks": notes,
            "complete_formal_case_results": cases, "independent_certification": False}


def write_json(path, payload):
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    encoded = content.encode("utf-8")
    require(len(encoded) <= MAX_OUTPUT_BYTES, "Single output exceeds declared20MiB budget")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def summarized(result):
    output = {k: v for k, v in result.items() if k not in {"primary", "normalized"}}
    for mode in ["primary", "normalized"]:
        output[mode] = {k: v for k, v in result[mode].items() if k not in {"rows", "state"}}
    return output
