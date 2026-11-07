"""Wasion source-bounded research model. Offline public command-line edition.
Units: CNY million; shares in million; per-share outputs CNY. Standard library only.
No network, external package, import-time computation, or hidden financing.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math


class InputBoundaryError(ValueError):
    """Invalid input contract, before any financial calculation."""


class EconomicBoundaryError(ValueError):
    """This path needs an explained economic mechanism, not a zero company value."""


def require(condition, message):
    if not condition:
        raise InputBoundaryError(message)


def ensure_finite(value, location="root"):
    if isinstance(value, float) and not math.isfinite(value):
        raise InputBoundaryError(f"{location}: non-finite number")
    if isinstance(value, dict):
        for key, item in value.items():
            ensure_finite(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            ensure_finite(item, f"{location}[{index}]")


def numeric(value, location, lower=None, upper=None, strict_lower=False):
    require(type(value) in (int, float) and math.isfinite(value), f"{location}: finite number required")
    if lower is not None:
        require(value > lower if strict_lower else value >= lower, f"{location}: invalid lower bound")
    if upper is not None:
        require(value <= upper, f"{location}: invalid upper bound")


def require_keys(value, names, location):
    require(isinstance(value, dict), f"{location}: object required")
    for name in names.split():
        require(name in value, f"{location}.{name}: missing required field")


def numeric_array(value, length, location, lower=None, upper=None):
    require(isinstance(value, list) and len(value) == length, f"{location}: exactly {length} entries required")
    for index, item in enumerate(value):
        numeric(item, f"{location}[{index}]", lower, upper)


def validate_dates(data):
    require_keys(data, "units model_as_of balance_date period_end_dates snapshot_convention", "input")
    require(data["units"] == "CNY_million_except_ratios_and_shares_million", "units: unsupported contract")
    try:
        asof = datetime.fromisoformat(data["model_as_of"].replace("Z", "+00:00"))
        balance = datetime.strptime(data["balance_date"], "%Y-%m-%d").date()
    except (ValueError, TypeError, AttributeError) as exc:
        raise InputBoundaryError(f"dates: invalid ISO date/time: {exc}") from exc
    require(asof.utcoffset() is not None and asof.utcoffset().total_seconds() == 0,
            "model_as_of: UTC timezone required")
    require((asof.month, asof.day, asof.hour, asof.minute, asof.second, asof.microsecond) == (11, 1, 0, 0, 0, 0),
            "dates: this annual approximation supports November 1 midnight UTC only")
    require(balance == asof.date().replace(month=9, day=30),
            "balance_date: this snapshot contract requires September 30 of the same year")
    require(data["snapshot_convention"] == "September balances proxy November opening; explicit gap_cash and gap_nwc conditions, not verified October activity",
            "snapshot_convention: unsupported annual/snapshot approximation")
    expected = [asof.date().replace(year=asof.year + i).isoformat() for i in range(1, 6)]
    require(data["period_end_dates"] == expected, "period_end_dates: five exact anniversaries required; calendar year-end is not year five")


def resolve_path(data, name, seen=()):
    require(isinstance(name, str) and name in data["paths"], f"path {name!r}: unknown")
    require(name not in seen, f"path {name}: inheritance cycle {seen}")
    own = deepcopy(data["paths"][name])
    require(isinstance(own, dict), f"path {name}: object required")
    parent = own.pop("inherits", None)
    return {**(resolve_path(data, parent, seen + (name,)) if parent is not None else {}), **own}


def validate_case_inputs(data, name, share, overrides=None):
    ensure_finite(data)
    validate_dates(data)
    require_keys(data, "facts common paths", "input")
    require(isinstance(data["paths"], dict) and bool(data["paths"]), "paths: nonempty object required")
    require(isinstance(overrides, (dict, type(None))), "overrides: object required")
    require_keys(data["facts"], "shares_million treasury_shares_million cash_equivalents cash_difference trading_financial unknown_current unknown_noncurrent noncurrent_financial investment_property bank_debt receivables receivable_notes receivable_financing contract_assets inventory prepayments payables payable_notes contract_liabilities other_current_assets other_receivables interest_receivable wages_payable taxes_payable other_payables other_current_liabilities ppe cip intangibles long_deferred mother_fy25_distributable fy25_final_declared statutory_gap_conditional_max", "facts")
    require_keys(data["common"], "opening_operating_cash_buffer reference_revenue cash_buffer_revenue_ratio cash_yield_after_tax deposit_yield_after_tax property_net_cash_yield other_financial_cash_yield tax_rate tax_surcharge_ratio prepayment_revenue_ratio notes_revenue_ratio contract_asset_revenue_ratio contract_liability_revenue_ratio dividend_payout seed_profit_for_first_dividend cash_before_dividend_fraction mother_cash_buffer mother_cash_before_dividend_fraction mother_initial_cash mother_initial_distributable mother_upstream_cash mother_upstream_new_profit reserve_policy reserve_gap unknown_financial_share_conditions cash_difference_financial_share unknown_noncurrent_maturity_year gap_cash gap_nwc extra_commitment_payments extra_growth_capex future_buybacks transition_growth terminal_fixed_capital_revenue_ratio terminal_maintenance_revenue_ratio terminal_other_operating_income_ratio terminal_net_working_other_ratio receivable_ratio_shift", "common")
    for key in overrides or {}:
        require(key in data["common"], f"override.{key}: unknown key")
    f, c, p = deepcopy(data["facts"]), {**deepcopy(data["common"]), **(overrides or {})}, resolve_path(data, name)
    ensure_finite(c, "effective_common")
    for key, value in f.items():
        numeric(value, f"facts.{key}", 0)
    numeric(f["shares_million"], "facts.shares_million", 0, strict_lower=True)
    require(f["treasury_shares_million"] <= f["shares_million"], "facts: treasury exceeds issued shares")
    require(f["interest_receivable"] <= f["other_receivables"], "facts: interest receivable exceeds its containing balance")
    numeric(share, "financial_share_condition", 0, 1)
    for key in "tax_rate cash_before_dividend_fraction mother_cash_before_dividend_fraction dividend_payout cash_difference_financial_share".split():
        numeric(c[key], f"common.{key}", 0, 1)
    for key in "opening_operating_cash_buffer cash_buffer_revenue_ratio tax_surcharge_ratio prepayment_revenue_ratio notes_revenue_ratio contract_asset_revenue_ratio contract_liability_revenue_ratio mother_cash_buffer reserve_gap terminal_fixed_capital_revenue_ratio terminal_maintenance_revenue_ratio".split():
        numeric(c[key], f"common.{key}", 0)
    numeric(c["reference_revenue"], "common.reference_revenue", 0, strict_lower=True)
    for key in "seed_profit_for_first_dividend gap_cash gap_nwc terminal_other_operating_income_ratio terminal_net_working_other_ratio receivable_ratio_shift".split():
        numeric(c[key], f"common.{key}")
    numeric(f["cash_equivalents"] + c["gap_cash"], "opening cash snapshot after gap_cash", 0)
    for key in "cash_yield_after_tax deposit_yield_after_tax property_net_cash_yield other_financial_cash_yield".split():
        numeric(c[key], f"common.{key}", -1, strict_lower=True)
    for key in "mother_initial_cash mother_initial_distributable".split():
        if c[key] is not None:
            numeric(c[key], f"common.{key}", 0 if key == "mother_initial_cash" else None)
    for key in "mother_upstream_cash mother_upstream_new_profit extra_commitment_payments extra_growth_capex future_buybacks".split():
        numeric_array(c[key], 5, f"common.{key}", 0)
    require(c["reserve_policy"] in ("cap_conditional", "continue10pct"), "reserve_policy: unsupported policy")
    if c["reserve_policy"] == "cap_conditional":
        require(c["reserve_gap"] <= f["statutory_gap_conditional_max"], "reserve_gap exceeds documented conditional bound")
    require(type(c["unknown_noncurrent_maturity_year"]) is int and c["unknown_noncurrent_maturity_year"] >= 1,
            "unknown_noncurrent_maturity_year: positive integer required")
    require(isinstance(c["unknown_financial_share_conditions"], list) and bool(c["unknown_financial_share_conditions"]), "financial shares: nonempty list required")
    for value in c["unknown_financial_share_conditions"]:
        numeric(value, "unknown_financial_share_conditions[]", 0, 1)
    numeric_array(c["transition_growth"], 3, "common.transition_growth")
    array_fields = "domestic_revenue international_revenue domestic_gross_margin international_gross_margin rd_ratio sales_ratio admin_ratio credit_inventory_loss_ratio other_operating_income receivable_revenue_ratio inventory_cost_ratio payables_cost_ratio maintenance_capex growth_capex depreciation mother_operating_cash mother_capex mother_subsidiary_funding mother_profit"
    scalar_fields = "discount_rate terminal_growth terminal_domestic_gross_margin terminal_international_gross_margin terminal_rd_ratio terminal_sales_ratio terminal_admin_ratio terminal_loss_ratio terminal_receivable_ratio terminal_inventory_ratio terminal_payables_ratio aux_normal_owner_cash aux_growth"
    require_keys(p, array_fields + " " + scalar_fields + " role", f"path.{name}")
    signed_arrays = {"domestic_gross_margin", "international_gross_margin", "other_operating_income", "mother_operating_cash", "mother_profit"}
    for key in array_fields.split():
        numeric_array(p[key], 5, f"path.{name}.{key}", None if key in signed_arrays else 0)
    for key in scalar_fields.split():
        numeric(p[key], f"path.{name}.{key}")
    for key in "domestic_gross_margin international_gross_margin".split():
        require(all(v <= 1 for v in p[key]), f"path.{name}.{key}: gross margin above 1 implies negative cost")
    for key in "terminal_domestic_gross_margin terminal_international_gross_margin".split():
        numeric(p[key], f"path.{name}.{key}", upper=1)
    for key in "terminal_rd_ratio terminal_sales_ratio terminal_admin_ratio terminal_loss_ratio terminal_receivable_ratio terminal_inventory_ratio terminal_payables_ratio".split():
        numeric(p[key], f"path.{name}.{key}", 0)
    for index, (a, b) in enumerate(zip(p["domestic_revenue"], p["international_revenue"])):
        numeric(a + b, f"path.{name}.total_revenue[{index}]", 0, strict_lower=True)
    require(all(v + c["receivable_ratio_shift"] >= 0 for v in p["receivable_revenue_ratio"] + [p["terminal_receivable_ratio"]]), "effective receivable ratio must be nonnegative (no upper cap)")
    numeric(p["discount_rate"], f"path.{name}.discount_rate", 0, strict_lower=True)
    require(p["discount_rate"] > p["terminal_growth"], f"path.{name}: discount rate must exceed terminal growth")
    transition = p.get("transition_growth_override", c["transition_growth"])
    numeric_array(transition, 3, f"path.{name}.transition_growth")
    require(all(v > -1 for v in transition + [p["terminal_growth"], p["aux_growth"]]), "growth: > -1 required")
    # AR/revenue, inventory/cost, AP/cost and signed NWC are NOT capped at one.
    return f, c, p


def validate_document(data):
    ensure_finite(data)
    validate_dates(data)
    require_keys(data, "paths common diagnostics", "input")
    require(isinstance(data["diagnostics"], list), "diagnostics: list required")
    require(isinstance(data["paths"], dict) and bool(data["paths"]), "paths: nonempty object required")
    for name in data["paths"]:
        validate_case_inputs(data, name, 0.0)
    for diag in data["diagnostics"]:
        require_keys(diag, "name path financial_share common_overrides", "diagnostic")
        validate_case_inputs(data, diag["path"], diag["financial_share"], diag["common_overrides"])


def write_complete_json(path, value):
    # Build complete finite JSON before touching the final filename.
    ensure_finite(value, "output")
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("x") as stream:
        stream.write(encoded + "\n")
        stream.flush()
    temporary.rename(path)


def reject_json_constant(token):
    raise InputBoundaryError(f"JSON: forbidden non-finite literal {token}")


def opening_state(f, c, financial_share):
    trade = (f["receivables"] + f["receivable_notes"] + f["receivable_financing"]
             + f["contract_assets"] + f["inventory"] + f["prepayments"]
             - f["payables"] - f["payable_notes"] - f["contract_liabilities"])
    residual = (f["other_current_assets"] + f["other_receivables"]
                - f["interest_receivable"] - f["wages_payable"] - f["taxes_payable"]
                - f["other_payables"] - f["other_current_liabilities"])
    current_operating = f["unknown_current"] * (1 - financial_share)
    noncurrent_operating = f["unknown_noncurrent"] * (1 - financial_share)
    fixed = f["ppe"] + f["cip"] + f["intangibles"] + f["long_deferred"]
    collateral = f["cash_difference"] * (1 - c["cash_difference_financial_share"])
    return {"nwc": trade + residual + current_operating + c["gap_nwc"], "residual": residual,
            "fixed": fixed + noncurrent_operating,
            "collateral": collateral, "buffer": c["opening_operating_cash_buffer"],
            "cash": f["cash_equivalents"] + c["gap_cash"]}


def financial_assets(f, c, share):
    # Principal is an owned asset, not a second operating-profit capitalization.
    # Maturity is a liquidity condition, not an arbitrary principal impairment.
    return [
        {"name": "trading", "principal": f["trading_financial"], "maturity": 1,
         "yield": c["deposit_yield_after_tax"]},
        {"name": "accrued_interest", "principal": f["interest_receivable"],
         "maturity": 1, "yield": 0.0},
        {"name": "unclassified_current_financial", "principal": f["unknown_current"] * share,
         "maturity": 1, "yield": c["deposit_yield_after_tax"]},
        {"name": "unclassified_noncurrent_financial", "principal": f["unknown_noncurrent"] * share,
         "maturity": c["unknown_noncurrent_maturity_year"], "yield": c["deposit_yield_after_tax"]},
        {"name": "cash_difference_financial", "principal": f["cash_difference"] * c["cash_difference_financial_share"],
         "maturity": 1, "yield": c["deposit_yield_after_tax"]},
        {"name": "noncurrent_financial", "principal": f["noncurrent_financial"],
         "maturity": None, "yield": c["other_financial_cash_yield"]},
        {"name": "investment_property", "principal": f["investment_property"],
         "maturity": None, "yield": c["property_net_cash_yield"]},
    ]


def mix(a, b, weight):
    return a + (b - a) * weight


def forecast_operations(f, c, p, share):
    start = opening_state(f, c, share)
    prev = deepcopy(start)
    rows = []
    residual_ratio = start["residual"] / c["reference_revenue"]
    collateral_ratio = start["collateral"] / c["reference_revenue"]
    last_dom, last_int = p["domestic_revenue"][-1], p["international_revenue"][-1]
    transition = p.get("transition_growth_override", c["transition_growth"])[:]
    transition[-1] = p["terminal_growth"]
    keys = [("domestic_gross_margin", "terminal_domestic_gross_margin"),
            ("international_gross_margin", "terminal_international_gross_margin"),
            ("rd_ratio", "terminal_rd_ratio"), ("sales_ratio", "terminal_sales_ratio"),
            ("admin_ratio", "terminal_admin_ratio"),
            ("credit_inventory_loss_ratio", "terminal_loss_ratio"),
            ("receivable_revenue_ratio", "terminal_receivable_ratio"),
            ("inventory_cost_ratio", "terminal_inventory_ratio"),
            ("payables_cost_ratio", "terminal_payables_ratio")]
    for i in range(8):
        if i < 5:
            dom, intl = p["domestic_revenue"][i], p["international_revenue"][i]
            q = {key: p[key][i] for key, _ in keys}
            other = p["other_operating_income"][i]
            dep = p["depreciation"][i]
            maintenance = p["maintenance_capex"][i]
            growth_capex = p["growth_capex"][i] + c["extra_growth_capex"][i]
            capex = maintenance + growth_capex
            extra_payment = c["extra_commitment_payments"][i]
            residual = residual_ratio * (dom + intl)
        else:
            w = (i - 4) / 3
            last_dom *= 1 + transition[i - 5]
            last_int *= 1 + transition[i - 5]
            dom, intl = last_dom, last_int
            q = {key: mix(p[key][-1], p[target], w) for key, target in keys}
            other = (dom + intl) * mix(p["other_operating_income"][-1] /
                        (p["domestic_revenue"][-1] + p["international_revenue"][-1]),
                        c["terminal_other_operating_income_ratio"], w)
            dep = p["depreciation"][-1] * (dom + intl) / (p["domestic_revenue"][-1] + p["international_revenue"][-1])
            maintenance = (dom + intl) * c["terminal_maintenance_revenue_ratio"]
            # No asset sale or terminal release is invented when fixed capital exceeds target.
            capex = max(maintenance, (dom + intl) * c["terminal_fixed_capital_revenue_ratio"] - prev["fixed"] + dep)
            growth_capex = capex - maintenance
            extra_payment = 0.0
            residual = (dom + intl) * mix(residual_ratio, c["terminal_net_working_other_ratio"], w)
        revenue = dom + intl
        gross_profit = dom * q["domestic_gross_margin"] + intl * q["international_gross_margin"]
        cost = revenue - gross_profit
        rd = revenue * q["rd_ratio"]
        losses = revenue * q["credit_inventory_loss_ratio"]
        ebit = gross_profit - rd - revenue * (q["sales_ratio"] + q["admin_ratio"] + c["tax_surcharge_ratio"]) - losses + other
        nopat = ebit - max(ebit, 0.0) * c["tax_rate"]
        ar = revenue * (q["receivable_revenue_ratio"] + c["receivable_ratio_shift"])
        inventory = cost * q["inventory_cost_ratio"]
        ap_notes = cost * q["payables_cost_ratio"]
        contract_assets = revenue * c["contract_asset_revenue_ratio"]
        other_trade = revenue * (c["notes_revenue_ratio"] + c["prepayment_revenue_ratio"] - c["contract_liability_revenue_ratio"])
        nwc = ar + inventory + contract_assets + other_trade - ap_notes + residual
        fixed = prev["fixed"] + capex - dep
        if fixed < 0:
            raise EconomicBoundaryError(f"{p['role']} year {i + 1}: negative physical/long-term operating capital; review depreciation and investment budget")
        collateral = revenue * collateral_ratio
        buffer = revenue * c["cash_buffer_revenue_ratio"]
        raw_fcf = nopat + dep - capex - (nwc - prev["nwc"]) - (collateral - prev["collateral"]) - extra_payment
        fcff = raw_fcf - (buffer - prev["buffer"])
        capital = nwc + fixed + collateral + buffer
        row = {"year": i + 1, "domestic_revenue": dom, "international_revenue": intl,
               "revenue": revenue, "gross_profit": gross_profit, "cost": cost, "rd": rd,
               "credit_inventory_losses": losses, "other_operating_income": other,
               "ebit": ebit, "nopat": nopat, "receivables_net": ar, "inventory_net": inventory,
               "trade_payables_notes": ap_notes, "contract_assets": contract_assets,
               "residual_operating_nwc": residual, "nwc": nwc, "fixed": fixed,
               "maintenance_capex": maintenance, "growth_capex": growth_capex,
               "capex": capex, "depreciation": dep, "separate_commitment_payment": extra_payment,
               "collateral": collateral, "buffer": buffer, "operating_capital": capital,
               "raw_fcf": raw_fcf, "fcff": fcff}
        rows.append(row)
        prev = row
    return start, rows


def operating_value(rows, rate, growth):
    # Terminal profit is generated by the operating budget, never investment * target ROIC.
    last = rows[-1]
    capital_status = "POSITIVE_CAPITAL_SUPPORTED"
    if last["operating_capital"] <= 0:
        if growth != 0:
            raise EconomicBoundaryError("Nonpositive aggregate operating capital with nonzero terminal growth needs an explicit company-specific funding/float mechanism. Negative NWC itself is allowed; no company value of zero is inferred.")
        capital_status = "NONPOSITIVE_CAPITAL_ZERO_GROWTH_NO_PERPETUAL_RELEASE"
    forward_nopat = last["nopat"] * (1 + growth)
    reinvestment = last["operating_capital"] * growth
    terminal_fcf = forward_nopat - reinvestment
    terminal_value = terminal_fcf / (rate - growth)
    value = sum(r["fcff"] / (1 + rate) ** r["year"] for r in rows)
    terminal_pv = terminal_value / (1 + rate) ** len(rows)
    return {"value": value + terminal_pv, "terminal_pv": terminal_pv,
            "capital_support_status": capital_status,
            "steady_terminal_value_at_year8": terminal_value,
            "terminal_forward_nopat": forward_nopat, "terminal_reinvestment": reinvestment,
            "terminal_fcf": terminal_fcf,
            "implied_steady_incremental_roic": (last["nopat"] / last["operating_capital"]
                                                if last["operating_capital"] > 0 else None)}


def cash_before_payment(net_flow, fraction):
    # Negative cash needs occur first; only part of positive annual inflow funds April-like dividend.
    return min(net_flow, 0.0) + max(net_flow, 0.0) * fraction


def shareholder_path(f, c, p, start, rows, assets):
    cash = start["cash"]
    prior_profit = c["seed_profit_for_first_dividend"]
    mother_cash = c["mother_initial_cash"]
    mother_legal = c["mother_initial_distributable"]
    gap = c["reserve_gap"]
    cum_mother_cash, cum_legal_profit, cum_d = 0.0, 0.0, 0.0
    minimum_cash = c["mother_cash_buffer"]
    minimum_legal = 0.0
    out = []
    for i, r in enumerate(rows[:5]):
        cash_start = cash
        fin_income = max(cash_start, 0.0) * c["cash_yield_after_tax"]
        fin_income += sum(a["principal"] * a["yield"] for a in assets)
        redemptions = sum(a["principal"] for a in assets if a["maturity"] == i + 1)
        proposed = max(0.0, prior_profit * c["dividend_payout"])
        buyback = c["future_buybacks"][i]
        group_pre_d = cash_start + cash_before_payment(r["raw_fcf"], c["cash_before_dividend_fraction"]) + fin_income * c["cash_before_dividend_fraction"] - buyback
        group_capacity = max(group_pre_d - r["buffer"], 0.0)
        group_limited = min(proposed, group_capacity)
        mother_net = (p["mother_operating_cash"][i] - p["mother_capex"][i]
                      - p["mother_subsidiary_funding"][i] + c["mother_upstream_cash"][i])
        mother_pre_flow = cash_before_payment(mother_net, c["mother_cash_before_dividend_fraction"])
        paid = group_limited
        # If M0/U0 supplied, they are explicit hypothetical conditions, not inferred facts.
        mother_pre_d = None if mother_cash is None else mother_cash + mother_pre_flow
        if mother_cash is not None:
            paid = min(paid, max(mother_pre_d - c["mother_cash_buffer"], 0.0))
        if mother_legal is not None:
            paid = min(paid, max(mother_legal, 0.0))
        minimum_cash = max(minimum_cash, c["mother_cash_buffer"] + cum_d + paid - cum_mother_cash - mother_pre_flow)
        minimum_legal = max(minimum_legal, cum_d + paid - cum_legal_profit)
        parent_profit = p["mother_profit"][i] + c["mother_upstream_new_profit"][i]
        reserve = max(parent_profit, 0.0) * 0.10
        if c["reserve_policy"] == "cap_conditional":
            reserve = min(reserve, gap)
            gap -= reserve
        cum_d += paid
        cum_mother_cash += mother_net
        cum_legal_profit += parent_profit - reserve
        if mother_cash is not None:
            mother_cash += mother_net - paid
        if mother_legal is not None:
            mother_legal += parent_profit - reserve - paid
        cash = cash_start + r["raw_fcf"] + fin_income + redemptions - paid - buyback
        for a in assets:
            if a["maturity"] == i + 1:
                a["principal"] = 0.0
        out.append({"year": i + 1, "cash_start": cash_start, "raw_operating_fcf": r["raw_fcf"],
                    "financial_income": fin_income, "asset_redemptions": redemptions,
                    "dividend_proposed": proposed, "dividend_after_group_limit": group_limited,
                    "dividend_paid": paid, "distribution_per_share": paid / f["shares_million"],
                    "buybacks": buyback, "cash_end": cash, "operating_cash_buffer": r["buffer"],
                    "midperiod_group_buffer_shortfall": max(r["buffer"] - group_pre_d, 0.0),
                    "unfunded_operating_cash_need": max(-min(group_pre_d, cash), 0.0),
                    "mother_pre_dividend_cash_if_supplied": mother_pre_d,
                    "mother_pre_dividend_unfunded_cash_need": (None if mother_pre_d is None else max(-mother_pre_d, 0.0)),
                    "mother_period_end_unfunded_cash_need": (None if mother_cash is None else max(-mother_cash, 0.0)),
                    "mother_unfunded_cash_need": (None if mother_pre_d is None else max(-mother_pre_d, -mother_cash, 0.0)),
                    "mother_period_end_buffer_shortfall_if_supplied": (None if mother_cash is None else max(c["mother_cash_buffer"] - mother_cash, 0.0)),
                    "mother_buffer_shortfall_if_supplied": (None if mother_pre_d is None else max(c["mother_cash_buffer"] - mother_pre_d, 0.0)),
                    "mother_net_cash_budget": mother_net, "mother_profit_budget": parent_profit,
                    "mother_statutory_retention": reserve,
                    "minimum_M0_for_paid_path_to_date": max(minimum_cash, 0.0),
                    "minimum_U0_for_paid_path_to_date": max(minimum_legal, 0.0),
                    "upfront_upstream_needed_if_M0_0": max(minimum_cash, 0.0),
                    "upfront_upstream_needed_if_M0_200": max(minimum_cash - 200.0, 0.0),
                    "dividend_reduced_for_mother_condition": group_limited - paid,
                    "mother_end_cash_if_supplied": mother_cash,
                    "mother_end_legal_profit_if_supplied": mother_legal,
                    "financial_assets_remaining": sum(a["principal"] for a in assets)})
        prior_profit = r["nopat"] + fin_income
    return out


def evaluate_case(data, path, financial_share, overrides=None):
    # All effective inputs, including diagnostic overrides and fixtures, are checked first.
    f, c, p = validate_case_inputs(data, path, financial_share, overrides)
    start, operations = forecast_operations(f, c, p, financial_share)
    assets = financial_assets(f, c, financial_share)
    asset_principal = sum(a["principal"] for a in assets)
    equity_bridge = start["cash"] - start["buffer"] + asset_principal - f["bank_debt"]
    try:
        value = operating_value(operations, p["discount_rate"], p["terminal_growth"])
    except EconomicBoundaryError as exc:
        raise EconomicBoundaryError(f"{path}, financial_share={financial_share}: {exc}") from exc
    holder = shareholder_path(f, c, p, start, operations, deepcopy(assets))
    # Genuine year-five value from the remaining operating path, not today's equity copied forward.
    value_at_five = sum(r["fcff"] / (1 + p["discount_rate"]) ** (r["year"] - 5) for r in operations[5:])
    value_at_five += value["steady_terminal_value_at_year8"] / (1 + p["discount_rate"]) ** 3
    mother_gaps = [h["mother_unfunded_cash_need"] for h in holder if h["mother_unfunded_cash_need"] is not None]
    mother_gap = max(mother_gaps) if mother_gaps else None
    group_gap = max(h["unfunded_operating_cash_need"] for h in holder)
    has_unfunded_gap = group_gap > 1e-7 or (mother_gap is not None and mother_gap > 1e-7)
    h5 = holder[-1]
    bridge5 = h5["cash_end"] - h5["operating_cash_buffer"] + h5["financial_assets_remaining"] - f["bank_debt"]
    aux_flows = [p["aux_normal_owner_cash"] * (1 + p["aux_growth"]) ** i for i in range(1, 11)]
    aux_ev = sum(v / (1 + p["discount_rate"]) ** i for i, v in enumerate(aux_flows, 1))
    aux_ev += aux_flows[-1] / p["discount_rate"] / (1 + p["discount_rate"]) ** 10
    dc = operations[4]["operating_capital"] - operations[0]["operating_capital"]
    incremental = ((operations[4]["nopat"] - operations[0]["nopat"]) / dc if dc > 0 else None)
    return {"path": path, "role": p["role"], "financial_share_condition": financial_share,
            "overrides": overrides or {}, "opening": start, "financial_assets_opening": assets,
            "operations": operations, "holder": holder, "operating_value": value,
            "current_asset_equity_bridge": equity_bridge,
            "current_equity_value_per_share": (value["value"] + equity_bridge) / f["shares_million"],
            "aux_current_equity_value_per_share": (aux_ev + equity_bridge) / f["shares_million"],
            "terminal_operating_value_at_year5": value_at_five,
            "terminal_asset_equity_bridge_at_year5": bridge5,
            "year5_equity_value_per_share": (value_at_five + bridge5) / f["shares_million"],
            "terminal_pv_contribution_to_current_operating_value": value["terminal_pv"] / value["value"] if value["value"] else None,
            "incremental_roic_year1_to_year5": incremental,
            "minimum_M0_for_paid_path": holder[-1]["minimum_M0_for_paid_path_to_date"],
            "minimum_U0_for_paid_path": holder[-1]["minimum_U0_for_paid_path_to_date"],
            "extra_upfront_upstream_needed_if_M0_is_zero": holder[-1]["minimum_M0_for_paid_path_to_date"],
            "extra_upfront_upstream_needed_if_M0_is_200": max(holder[-1]["minimum_M0_for_paid_path_to_date"] - 200.0, 0.0),
            "method_difference_fraction": abs(aux_ev - value["value"]) / abs(value["value"] + equity_bridge) if value["value"] + equity_bridge else None,
            "historical_mother_profit_anchor_after_fy25_final_only": f["mother_fy25_distributable"] - f["fy25_final_declared"],
            "actual_mother_funding_verified": False,
            "mother_condition_status": "unknown_M0_U0_threshold_only" if c["mother_initial_cash"] is None else "explicit_hypothetical_M0_not_verified_actual",
            "economic_status": ("UNFUNDED_GROUP_OR_MOTHER_NEEDS_REDESIGN" if has_unfunded_gap
                                else "CONDITIONAL_ON_MOTHER_AND_ASSET_ASSUMPTIONS"),
            "mother_unfunded_operating_cash_need": mother_gap,
            "holder_path_has_unmodelled_financing_need": has_unfunded_gap,
            "holder_path_adoptable_as_already_funded": False,
            "funding_note": ("Affected D/TV path is not funded; explicit financing or budget revision is required. Conditional operating/asset values are not automatically zero or null." if has_unfunded_gap
                             else "No modelled negative-cash gap; actual mother cash/assets still require the stated conditions."),
            "unfunded_operating_cash_need": group_gap}


def closed_form_cases(data):
    # The same full evaluate_case -> operating/holder chains as the real company are used.
    test = deepcopy(data)
    test["facts"] = {k: 0.0 for k in data["facts"]}
    test["facts"]["shares_million"] = 10.0
    c = test["common"]
    zero_keys = ["opening_operating_cash_buffer", "cash_buffer_revenue_ratio", "cash_yield_after_tax",
                 "deposit_yield_after_tax", "property_net_cash_yield", "tax_rate", "tax_surcharge_ratio",
                 "prepayment_revenue_ratio", "notes_revenue_ratio", "contract_asset_revenue_ratio",
                 "contract_liability_revenue_ratio", "mother_cash_buffer", "reserve_gap",
                 "terminal_fixed_capital_revenue_ratio", "terminal_maintenance_revenue_ratio",
                 "terminal_other_operating_income_ratio"]
    for k in zero_keys:
        c[k] = 0.0
    c.update({"dividend_payout": 1.0, "seed_profit_for_first_dividend": 10.0,
              "cash_before_dividend_fraction": 1.0, "mother_cash_before_dividend_fraction": 1.0,
              "transition_growth": [0.0, 0.0, 0.0]})
    p = resolve_path(data, "base_cautious")
    for k, v in p.items():
        if isinstance(v, list):
            p[k] = [0.0] * 5
    p.update({"role": "synthetic_closed_form", "domestic_revenue": [100.0] * 5,
              "domestic_gross_margin": [0.20] * 5, "rd_ratio": [0.10] * 5,
              "mother_profit": [10.0] * 5, "mother_operating_cash": [10.0] * 5,
              "discount_rate": 0.10, "terminal_growth": 0.0,
              "terminal_domestic_gross_margin": 0.20, "terminal_international_gross_margin": 0.0,
              "terminal_rd_ratio": 0.10, "terminal_sales_ratio": 0.0, "terminal_admin_ratio": 0.0,
              "terminal_loss_ratio": 0.0, "terminal_receivable_ratio": 0.0,
              "terminal_inventory_ratio": 0.0, "terminal_payables_ratio": 0.0,
              "aux_normal_owner_cash": 10.0, "aux_growth": 0.0})
    test["paths"] = {"steady": p}
    first = evaluate_case(test, "steady", 0.0)
    test["facts"]["cash_equivalents"] = 20.0
    second = evaluate_case(test, "steady", 0.0)
    test["facts"]["cash_equivalents"] = 0.0
    test["common"]["mother_initial_cash"] = 0.0
    test["paths"]["steady"]["mother_operating_cash"] = [0.0] * 5
    third = evaluate_case(test, "steady", 0.0)
    return [{"name": "constant_10_perpetuity", "expected_current_per_share": 10.0,
             "expected_tv5_per_share": 10.0, "expected_D": [1.0] * 5, "actual": first},
            {"name": "owned_nonpaying_cash20_retained", "expected_current_per_share": 12.0,
             "expected_tv5_per_share": 12.0, "expected_D": [1.0] * 5, "actual": second},
            {"name": "mother_cash_zero_no_invented_transfer", "expected_current_per_share": 10.0,
             "expected_tv5_per_share": 15.0, "expected_D": [0.0] * 5, "actual": third}]




def validate_saved_results(results):
    failures = []
    for case in results["cases"] + [d["result"] for d in results["diagnostics"]]:
        if len(case["holder"]) != 5:
            failures.append([case["path"], "five_distribution_periods"])
        for h in case["holder"]:
            expected = (h["cash_start"] + h["raw_operating_fcf"] + h["financial_income"]
                        + h["asset_redemptions"] - h["dividend_paid"] - h["buybacks"])
            if not math.isclose(expected, h["cash_end"], abs_tol=1e-7):
                failures.append([case["path"], h["year"], "cash_conservation"])
            if h["dividend_paid"] < -1e-8 or h["dividend_paid"] > h["dividend_after_group_limit"] + 1e-8:
                failures.append([case["path"], h["year"], "payment_cap"])
    for test in results["closed_form_cases"]:
        a = test["actual"]
        for actual, expected in [(a["current_equity_value_per_share"], test["expected_current_per_share"]),
                                 (a["year5_equity_value_per_share"], test["expected_tv5_per_share"])]:
            if not math.isclose(actual, expected, abs_tol=1e-7):
                failures.append([test["name"], actual, expected])
        if any(not math.isclose(h["distribution_per_share"], expected, abs_tol=1e-7)
               for h, expected in zip(a["holder"], test["expected_D"])):
            failures.append([test["name"], "D_mismatch"])
    return {"failures": failures, "passed": not failures,
            "note": "Arithmetic checks only; source/economic/mother-condition acceptance is separate."}
