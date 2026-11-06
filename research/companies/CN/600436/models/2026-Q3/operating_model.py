#!/usr/bin/env python3
"""Standard-library original formal chain; optional complete cache reproduction.

All money is CNY million internally. main() runs formal-chain closed-form fixtures
before any issuer calculation. Technical failures exit nonzero; available completed
path/auxiliary-stage partials are retained, not every interrupted simulation row.
"""
import argparse
import copy
import json
import math
import sys
import traceback
from pathlib import Path

EPS = 1e-7


class TechnicalFailure(Exception):
    def __init__(self, message, partial=None):
        super().__init__(message)
        self.partial = partial


def need(condition, message):
    if not condition:
        raise TechnicalFailure(message)


def close(a, b, label):
    need(abs(a - b) <= EPS * max(1.0, abs(a), abs(b)), label)


def finite_tree(value, path="input"):
    if isinstance(value, float):
        need(math.isfinite(value), "Nonfinite number at " + path)
    elif isinstance(value, dict):
        for key, item in value.items():
            finite_tree(item, path + "." + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            finite_tree(item, path + "[" + str(index) + "]")


def validate(c):
    finite_tree(c)
    need(c["unit"] == "CNY_million_except_shares_and_ratios", "Wrong units")
    n = c["horizon"]
    need(isinstance(n, int) and 5 <= n <= 30, "Horizon must be 5..30")
    need(c["shares"] > 0, "Shares must be positive")
    need(c["lease_convention"] == "CASH_RENT_EXPENSE_NO_LEASE_DEBT_DEDUCTION_NO_ROU_DEPRECIATION", "Lease convention mismatch")
    need(c["ownership_bridge"] == "FULL_GROUP_EV_MINUS_FULL_BANK_DEBT_MINUS_ECONOMIC_NCI_PLUS_LIMITED_RECOURSE_ADJUSTMENT_PLUS_OWNED_FINANCIAL_ASSETS", "Ownership convention mismatch")
    units = c["units"]
    ids = [u["id"] for u in units]
    need(len(ids) == len(set(ids)) and "manufacturing" in ids, "Duplicate/missing units")
    for u in units:
        need(0 <= u["owner"] <= 1, "Invalid ownership")
        need(u["equity_boundary"] in ("parent_direct_full_obligations", "limited_subgroup_zero_extra_parent_recourse_budget"), "Unspecified equity/recourse boundary")
        if u["equity_boundary"] == "parent_direct_full_obligations":
            need(u["owner"] == 1, "Direct parent bucket cannot have NCI")
        else:
            need(u["parent_recourse_budget"] == 0 and u["extra_parent_support_cash_budget"] == 0, "Nonzero parent recourse/support requires an explicit funded cash-plan revision; cannot silently release a known obligation")
        need(u["revenue_start"] >= 0 and u["initial_cost_index"] > 0, "Invalid opening unit")
        need(0 <= u["inventory_loss_rate"] < 1 and u["opening_ppe_remaining_life"] > 0, "Invalid physical assumptions")
        for key in ("growth", "new_cost_index", "coverage_years", "cash_opex_ratio"):
            need(len(u[key]) == n, "Wrong array length: " + u["id"] + "." + key)
        need(all(x > -1 for x in u["growth"]), "Revenue growth below -100%")
        need(all(x > 0 for x in u["new_cost_index"]), "Nonpositive purchase cost")
        need(all(x >= 0 for x in u["coverage_years"]), "Negative inventory coverage")
    for key in ("initial_ppe_share", "initial_other_nwc_share"):
        close(sum(u[key] for u in units), 1, "Unit allocations: " + key)
    if len(units) > 1:
        close(sum(u["nonparent_cash_share"] for u in units), 1, "Nonparent cash allocations")
    o = c["opening"]
    need(0 <= o["current_bank_portion_assumption"] <= o["reported_current_noncurrent_liabilities"], "Bank/lease current split outside reported total")
    need(o["group_cash"] >= o["group_cash_equivalents"], "Cash-equivalent restriction sign")
    need(o["other_current_deposits_assumption"] <= o["other_current_assets"], "Deposits exceed containing asset")
    for p in c["projects"]:
        need(len(p["payment_weights"]) == n, "Project schedule length")
        need(all(w >= 0 for w in p["payment_weights"]), "Negative payment weight")
        close(sum(p["payment_weights"]), 1, "Project schedule must exhaust selected future cash")
        need(p["future_cash"] >= p["included_prior_booked_payable"] >= 0, "Prior booked liability exceeds future cash")
        if p["type"] == "operating":
            need(p["unit"] in ids and p["asset_life"] > 0, "Invalid operating project")
            need(all(1 <= t <= n for t in p["commission_periods"]), "Commission outside horizon")
    close(sum(p["included_prior_booked_payable"] for p in c["projects"]), o["capex_payables_in_operating_lines_assumption"], "Capex payable must leave NWC exactly once")
    need(set(c["parent_cash_timing_policy"]["adjustable_new_capital_project_ids"]).issubset({p["id"] for p in c["projects"]}), "Timing policy names unknown projects")
    need(c["valuation"]["main_discount_rate"] > 0, "Discount rate invalid")
    if "capital_profile" in c:
        r, p = c["capital_revision"], c["capital_profile"]
        need(r["borrower"] in ids and r["beauty_unit"] in ids, "Capital profile units missing")
        loan = r["loan"]
        need(sum(r["h1_short_credit_principal"].values()) > 0 and all(v >= 0 for v in r["h1_short_credit_principal"].values()), "Invalid H1 short borrowing proxy weights")
        need(set(r["h1_short_credit_principal"]).issubset(ids), "Unknown borrowing-proxy entity")
        need(0 <= loan["cumulative_draw_cap"] and loan["contract_rate"] >= 0, "Invalid finite loan budget")
        need(all(1 <= t < loan["maturity_period"] <= n for t in loan["draw_periods"]), "Loan draw window must close before maturity within horizon")
        need(loan["credit_discount_rate"] > 0, "Credit discount must be explicit")
        for k in ("health_completion", "health_capital_release", "health_actual_cash_payments", "health_reduced_recovery", "beauty_payment_weights", "beauty_included_expense"):
            need(len(p[k]) == n, "Wrong capital profile length: " + k)
        for k in ("health_completion", "health_capital_release"):
            need(all(0 <= x <= 1 for x in p[k]), "Invalid restructure fraction")
            need(all(a <= b for a, b in zip(p[k], p[k][1:])), "Restructure fractions must not reverse")
        need(all(a <= b + EPS for a, b in zip(p["health_capital_release"], p["health_completion"])), "Capital cannot be released before its business block exits")
        need(all(v >= 0 for k in ("health_actual_cash_payments", "health_reduced_recovery", "beauty_included_expense") for v in p[k]), "Negative transition cost")
        for project in c["projects"]:
            expense = project.get("expense_cash_schedule", [0.0] * n)
            need(len(expense) == n, "Project expense schedule length")
            need(all(0 <= e <= project["future_cash"] * w + EPS for e, w in zip(expense, project["payment_weights"])), "Included project expense exceeds same-period total payment")


def period_labels(n):
    return [{"period": t, "from": str(2025 + t) + "-11-01", "to": str(2026 + t) + "-10-31"} for t in range(1, n + 1)]


def configure_path(config, path):
    c = copy.deepcopy(config)
    for u in c["units"]:
        if u["id"] == "manufacturing":
            for dest, source in (("revenue_start", "core_revenue_start"), ("growth", "core_growth"), ("new_cost_index", "core_new_cost"), ("coverage_years", "core_coverage"), ("cash_opex_ratio", "core_opex"), ("tax_rate", "core_tax_rate"), ("terminal_growth", "core_terminal_growth")):
                u[dest] = copy.deepcopy(path[source])
        else:
            u["revenue_start"] *= path["noncore_revenue_scale"]
            u["growth"] = [x + path["noncore_growth_add_first5"] if 0 < i < 5 else x for i, x in enumerate(u["growth"])]
    for p in c["projects"]:
        if p["type"] == "operating":
            p["future_cash"] *= path["project_cash_multiplier"]
    c["valuation"]["main_discount_rate"] = path["discount_rate"]
    c["active_path"] = copy.deepcopy(path)
    return c


def configure_capital_choice(c, name):
    """One pre-locked capital profile; never selected from model results."""
    revision = c["capital_revision"]
    profile = copy.deepcopy(revision["profiles"][name])
    c["capital_profile"] = profile
    c["capital_profile_name"] = name
    for u in c["units"]:
        if u["id"] in revision["h1_short_credit_principal"]:
            u["superseded_legacy_debt_perimeter"] = u["debt_perimeter"]
            u["debt_perimeter"] = "Q3 SHORT bank principal only is allocated by observed H1 borrower-credit proportions; this is a proxy, not September loan-level evidence. All long/current bank principal remains in the unallocated group reserve. Extra external recourse is separately bounded; finite parent loan, if selected, is explicit and not waived."
        if u["id"] == revision["borrower"]:
            # The old 5.2% -> 4.0% expense improvement could be this same cleanup.
            # Retire it completely; new savings are subtracted once from 5.2%.
            u["superseded_legacy_opex_path"] = copy.deepcopy(u["cash_opex_ratio"])
            u["cash_opex_ratio"] = [revision["unrestructured_cash_opex_ratio"]] * c["horizon"]
            u["health_restructure"] = True
            u["terminal_growth"] = 0.0
        if u["id"] == revision["beauty_unit"]:
            u["beauty_stage"] = True
            u["terminal_growth"] = 0.0
    for p in c["projects"]:
        if p["id"] == revision["beauty_project"]:
            p["future_cash"] = profile["beauty_future_cash"]
            p["payment_weights"] = copy.deepcopy(profile["beauty_payment_weights"])
            p["expense_cash_schedule"] = copy.deepcopy(profile["beauty_included_expense"])
            p["commission_periods"] = [profile["beauty_in_service_end"]]
            p["asset_life"] = 25
            p["purpose"] = "Current usable office/dorm/clean-fitout/logistics stage only; no unbuilt later expansion return"
    return c


def operating_budget(c, u, baseline_revenue, t, terminal=False):
    """Whole unrestructured baseline LESS one health block, never twice scaled."""
    i = min(t - 1, c["horizon"] - 1)
    revenue = baseline_revenue
    usage = baseline_revenue * u["usage_per_revenue"]
    opex = baseline_revenue * u["cash_opex_ratio"][i]
    nwc_revenue = baseline_revenue
    extra_cash = recovery_loss = site_cost = 0.0
    details = {}
    if u.get("health_restructure"):
        p, r = c["capital_profile"], c["capital_revision"]
        f = p["health_completion"][i]
        release = p["health_capital_release"][i]
        revenue -= r["health_revenue_removed"] * f
        usage -= (r["health_revenue_removed"] - r["health_gross_profit_removed"]) * f / r["health_reference_cost_index"]
        opex -= p["health_cash_opex_avoided"] * f
        nwc_revenue -= r["health_revenue_removed"] * release
        if not terminal:
            extra_cash = p["health_actual_cash_payments"][i]
            recovery_loss = p["health_reduced_recovery"][i]
        details = {"whole_baseline_revenue": baseline_revenue, "completion": f,
                   "removed_revenue": r["health_revenue_removed"] * f,
                   "removed_gross_profit_before_physical_losses": r["health_gross_profit_removed"] * f,
                   "avoided_cash_opex": p["health_cash_opex_avoided"] * f,
                   "capital_release_completion": release,
                   "actual_exit_cash_paid": extra_cash,
                   "reduced_receivable_realization_cash": recovery_loss,
                   "recovery_loss_is_not_an_additional_cash_payment": True,
                   "no_second_inventory_impairment_for_same_loss": True}
    if u.get("beauty_stage"):
        p, r = c["capital_profile"], c["capital_revision"]
        since = t - p["beauty_in_service_end"]
        increments = r["beauty_incremental_demand"]
        increment = 0 if since <= 0 else increments[min(since - 1, len(increments) - 1)]
        revenue = r["beauty_existing_demand"] + increment
        usage = revenue * u["usage_per_revenue"]
        opex = revenue * u["cash_opex_ratio"][i]
        nwc_revenue = revenue
        site_cost = p["beauty_site_cost"] if since > 0 else 0.0
        details = {"existing_demand_not_created_by_project": r["beauty_existing_demand"],
                   "incremental_demand_budget_not_physical_capacity": increment,
                   "in_service_end_period": p["beauty_in_service_end"], "site_cost": site_cost}
    need(revenue >= -EPS and usage >= -EPS and opex >= -EPS, "Selected health block exceeds whole business baseline")
    return {"revenue": revenue, "usage": usage, "cash_opex": opex,
            "nwc_revenue": nwc_revenue, "actual_exit_cash": extra_cash,
            "recovery_loss": recovery_loss, "site_cost": site_cost, "details": details}


def inventory_target(c, u, next_baseline, t):
    i = min(t - 1, c["horizon"] - 1)
    if u.get("health_restructure"):
        r, p = c["capital_revision"], c["capital_profile"]
        retained_usage = next_baseline * u["usage_per_revenue"] - (r["health_revenue_removed"] - r["health_gross_profit_removed"]) * p["health_capital_release"][i] / r["health_reference_cost_index"]
    else:
        retained_usage = operating_budget(c, u, next_baseline, t + 1, terminal=True)["usage"]
    need(retained_usage >= -EPS, "Negative inventory requirement")
    return max(0.0, retained_usage) * u["coverage_years"][i]


def support_cash_step(c, s, rows, t, maturity_allowance=None):
    """One non-revolving cash waterfall. Returns only external tax/bank outflows."""
    if "support_loan" not in s:
        return {"active": False, "draw": 0.0, "interest_paid": 0.0, "principal_paid": 0.0,
                "parent_interest_tax": 0.0, "bank_principal_paid": 0.0,
                "parent_profit_addition": 0.0, "borrower_profit_deduction": 0.0}
    policy = c["capital_revision"]["loan"]
    loan = s["support_loan"]
    sub = s["units"][c["capital_revision"]["borrower"]]
    parent = s["units"]["manufacturing"]
    opening = copy.deepcopy(loan)
    cash_before = sub["surplus_cash"]
    contractual_interest = loan["principal"] * policy["contract_rate"]
    loan["unpaid_interest"] += contractual_interest
    # No tax benefit for borrower interest is assumed; parent pays tax on receipt.
    # Thus no unproved incremental group tax shield is introduced.
    shortfall = max(0.0, -sub["surplus_cash"])
    draw = 0.0
    if t in policy["draw_periods"]:
        draw = min(shortfall, max(0.0, policy["cumulative_draw_cap"] - loan["cumulative_draws"]), max(0.0, parent["surplus_cash"]))
    parent["surplus_cash"] -= draw
    sub["surplus_cash"] += draw
    loan["principal"] += draw
    loan["carrying_principal"] += draw
    loan["cumulative_draws"] += draw
    interest_paid = min(max(0.0, sub["surplus_cash"]), loan["unpaid_interest"])
    sub["surplus_cash"] -= interest_paid
    loan["unpaid_interest"] -= interest_paid
    principal_paid = min(max(0.0, sub["surplus_cash"]), loan["principal"])
    sub["surplus_cash"] -= principal_paid
    loan["principal"] -= principal_paid
    carrying_removed = min(principal_paid, loan["carrying_principal"])
    recovery_gain = principal_paid - carrying_removed
    loan["carrying_principal"] -= carrying_removed
    parent_tax = interest_paid * c["units"][0]["tax_rate"]
    parent["surplus_cash"] += interest_paid + principal_paid - parent_tax
    bank_paid = 0.0
    # Suspends ordinary dividends until loan clearance, with no draw-to-bank loop.
    if draw <= EPS and loan["principal"] + loan["unpaid_interest"] <= EPS:
        bank_paid = min(max(0.0, sub["surplus_cash"]), sub["bank_debt"])
        sub["surplus_cash"] -= bank_paid
        sub["bank_debt"] -= bank_paid
    impairment = 0.0
    if t == policy["maturity_period"] and maturity_allowance is not None:
        impairment = min(loan["carrying_principal"], max(0.0, maturity_allowance))
        loan["carrying_principal"] -= impairment
        loan["maturity_impairment_booked"] += impairment
    loan["overdue"] = t >= policy["maturity_period"] and loan["principal"] + loan["unpaid_interest"] > EPS
    close(loan["principal"], opening["principal"] + draw - principal_paid, "Internal loan principal roll-forward")
    close(loan["cumulative_draws"], opening["cumulative_draws"] + draw, "Non-revolving cumulative draw cap")
    need(loan["cumulative_draws"] <= policy["cumulative_draw_cap"] + EPS, "Cumulative loan limit exceeded")
    if draw > EPS:
        close(bank_paid, 0, "No bank deleveraging funded by same-year parent draw")
    return {"active": True, "opening_contract": opening, "closing_contract": copy.deepcopy(loan),
            "borrower_cash_before_support": cash_before, "draw": draw,
            "contractual_interest_accrued": contractual_interest,
            "interest_paid": interest_paid, "principal_paid": principal_paid,
            "parent_interest_tax": parent_tax, "bank_principal_paid": bank_paid,
            "maturity_impairment_no_cash": impairment, "credit_recovery_gain_no_new_principal_profit": recovery_gain,
            "parent_profit_addition": interest_paid - parent_tax + recovery_gain - impairment,
            "borrower_profit_deduction": contractual_interest,
            "ordinary_distribution_blocked": draw > EPS or loan["principal"] + loan["unpaid_interest"] > EPS,
            "remaining_nonrevolving_draw_capacity": policy["cumulative_draw_cap"] - loan["cumulative_draws"],
            "annual_order_not_intra_year_liquidity_proof": True,
            "borrower_interest_tax_deduction_assumed": False}


def operating_other_nwc(o):
    assets = sum(o[k] for k in ("trade_receivables", "notes_receivable", "receivable_financing", "prepayments", "other_receivables", "contract_assets", "other_current_assets"))
    assets -= o["group_external_receivable_dividend"] + o["other_current_deposits_assumption"]
    liabilities = sum(o[k] for k in ("trade_payables", "notes_payable", "advance_receipts", "contract_liabilities", "staff_payable", "tax_payable", "other_payables", "other_current_liabilities"))
    liabilities -= o["already_declared_and_paid_dividend"] + o["capex_payables_in_operating_lines_assumption"]
    return assets - liabilities


def inventory_step(open_units, open_book, usage, desired_close, purchase_index, loss_rate):
    """Equivalent cost units, NOT undisclosed SKU counts; one periodic WA pool."""
    need(open_units >= -EPS and open_book >= -EPS and usage >= 0, "Invalid inventory opening")
    purchases = max(0.0, usage + desired_close / (1 - loss_rate) - open_units)
    available = open_units + purchases
    purchase_cash = purchases * purchase_index
    avg = (open_book + purchase_cash) / available if available > EPS else purchase_index
    need(available + EPS >= usage, "Insufficient inventory units")
    consumption = usage * avg
    loss_units = max(0.0, available - usage) * loss_rate
    loss_value = loss_units * avg
    end_units = max(0.0, available - usage - loss_units)
    end_book = end_units * avg
    close(open_book + purchase_cash - consumption - loss_value, end_book, "Weighted-average inventory roll-forward")
    close(consumption + loss_value + end_book - open_book, purchase_cash, "COGS plus inventory delta must equal purchases")
    return {"opening_units": open_units, "opening_book": open_book, "purchase_units": purchases, "purchase_cash": purchase_cash, "weighted_average_cost": avg, "usage_units": usage, "consumption_cost": consumption, "loss_units": loss_units, "loss_cost": loss_value, "closing_units": end_units, "closing_book": end_book, "desired_safety_units": desired_close}


def depreciation(cohorts, t):
    return sum(a["basis"] / a["life"] for a in cohorts if a["start"] <= t < a["start"] + a["life"])


def net_cohorts(cohorts, t):
    return sum(a["basis"] * max(0.0, 1 - min(a["life"], max(0, t - a["start"] + 1)) / a["life"]) for a in cohorts)


def revenue_schedule(u, n):
    revenue = u["revenue_start"]
    result = []
    for i in range(n):
        revenue *= 1 + u["growth"][i]
        result.append(revenue)
    return result


def initial_state(c):
    o = c["opening"]
    restricted = o["group_cash"] - o["group_cash_equivalents"]
    need(0 <= o["parent_restricted_cash_assumption"] <= restricted + EPS, "Parent restricted allocation")
    internal_receivable = o["parent_receivable_dividend"] - o["group_external_receivable_dividend"]
    need(internal_receivable >= -EPS, "Internal receivable sign")
    nonparent_cash = o["group_cash_equivalents"] - (o["parent_cash"] - o["parent_restricted_cash_assumption"]) - internal_receivable
    need(nonparent_cash >= -EPS, "Opening cash allocation exceeds group")
    parent_cash = o["parent_cash"] - o["parent_restricted_cash_assumption"] - o["already_declared_and_paid_dividend"] + o["october_unreported_net_operating_cash_assumption"]
    bank = o["short_bank_debt"] + o["long_bank_debt"] + o["current_bank_portion_assumption"]
    if bank > EPS and "capital_profile" not in c:
        close(sum(u["bank_debt_share"] for u in c["units"]), 1, "Bank debt attribution")
    nwc = operating_other_nwc(o)
    inv_assigned = sum(u["initial_inventory"] for u in c["units"] if isinstance(u["initial_inventory"], (int, float)))
    units = {}
    for u in c["units"]:
        inv = o["group_inventory"] - inv_assigned if u["initial_inventory"] == "RESIDUAL" else u["initial_inventory"]
        need(inv >= -EPS, "Negative residual inventory")
        cash = parent_cash if u["id"] == "manufacturing" else nonparent_cash * u["nonparent_cash_share"]
        ppe = (o["group_fixed_assets"] + o["group_intangibles"]) * u["initial_ppe_share"]
        assigned_bank = bank * u["bank_debt_share"]
        if "capital_profile" in c:
            weights = c["capital_revision"]["h1_short_credit_principal"]
            assigned_bank = o["short_bank_debt"] * weights.get(u["id"], 0.0) / sum(weights.values())
        units[u["id"]] = {"inventory_units": inv / u["initial_cost_index"], "inventory_book": inv, "other_nwc": nwc * u["initial_other_nwc_share"], "buffer": u["initial_cash_buffer"], "surplus_cash": cash - u["initial_cash_buffer"], "bank_debt": assigned_bank, "cohorts": [{"basis": ppe, "life": u["opening_ppe_remaining_life"], "start": 1}], "revenues": revenue_schedule(u, c["horizon"])}
    close(sum(s["inventory_book"] for s in units.values()), o["group_inventory"], "Inventory allocations")
    op = [p for p in c["projects"] if p["type"] == "operating"]
    h1_cip = sum(p["h1_book_cip"] for p in op)
    need(h1_cip > 0 or o["group_cip"] == 0, "CIP allocation needs anchor")
    projects = {}
    for p in c["projects"]:
        initial_cip = o["group_cip"] * p.get("h1_book_cip", 0) / h1_cip if h1_cip > 0 and p["type"] == "operating" else 0
        projects[p["id"]] = {"cip": initial_cip, "prior_payable_remaining": p["included_prior_booked_payable"], "cumulative_future_cash": 0}
    finance = []
    direct_equities = sum(a["opening_book"] for a in c["financial_assets"] if a["id"] == "other_equities_parent")
    for a in c["financial_assets"]:
        f = copy.deepcopy(a)
        f["book"] = c["group_other_equities_book"] - direct_equities if a["opening_book"] == "EQUITIES_RESIDUAL" else a["opening_book"]
        f["created_period"] = 0
        finance.append(f)
    state = {"units": units, "projects": projects, "finance": finance, "parent_locked_deposit": o["parent_term_deposits"], "treasury_cash": o["other_current_deposits_assumption"], "legacy_payer_cash": internal_receivable, "external_dividend_claim": o["group_external_receivable_dividend"], "restricted_claim": restricted, "parent_re": o["parent_retained_earnings"], "statutory_reserve": o["parent_statutory_reserve"], "other_reserve": 0}
    if "capital_profile" in c:
        state["unallocated_group_bank_debt"] = o["long_bank_debt"] + o["current_bank_portion_assumption"]
        state["support_loan"] = {"principal": 0.0, "carrying_principal": 0.0, "unpaid_interest": 0.0, "cumulative_draws": 0.0, "maturity_impairment_booked": 0.0, "overdue": False}
        close(sum(v["bank_debt"] for v in units.values()) + state["unallocated_group_bank_debt"], bank, "Reported bank debt preserved after H1 borrower proxy")
    return state


def total_liquid_state(s):
    return sum(u["surplus_cash"] + u["buffer"] for u in s["units"].values()) + s["parent_locked_deposit"] + s["treasury_cash"] + s["legacy_payer_cash"]


def financial_bridge(c, s):
    by_id = {u["id"]: u for u in c["units"]}
    cash_gross = sum(v["surplus_cash"] for v in s["units"].values()) + s["parent_locked_deposit"] + s["treasury_cash"] + s["legacy_payer_cash"]
    cash_nci = sum(v["surplus_cash"] * (1 - by_id[k]["owner"]) for k, v in s["units"].items())
    scale = c["active_path"]["financial_value_multiplier_scale"]
    assets = [{"id": a["id"], "book": a["book"], "gross_value": a["book"] * a["value_multiplier"] * scale, "owner": a["owner"]} for a in s["finance"]]
    asset_gross = sum(a["gross_value"] for a in assets)
    asset_nci = sum(a["gross_value"] * (1 - a["owner"]) for a in assets)
    restricted_value = s["restricted_claim"] * 0.95
    restricted_nci_fraction = sum(u["nonparent_cash_share"] * (1 - u["owner"]) for u in c["units"])
    restricted_nci = max(0, s["restricted_claim"] - c["opening"]["parent_restricted_cash_assumption"]) * restricted_nci_fraction * 0.95
    return {"surplus_cash_and_deposits_gross": cash_gross, "cash_nci": cash_nci, "financial_assets": assets, "financial_assets_gross": asset_gross, "financial_assets_nci": asset_nci, "restricted_value": restricted_value, "restricted_nci": restricted_nci, "external_dividend_claim": s["external_dividend_claim"], "attributable_net_assets": cash_gross - cash_nci + asset_gross - asset_nci + restricted_value - restricted_nci + s["external_dividend_claim"]}


def nci_allocation(c, state, u, ev, debt, loan_rights=None):
    """Explicit entity recourse applies to both parent and NCI equity.

    Financial bridge already deducts NCI on entity cash. The operating allocation
    is therefore signed when needed. Full bank debt remains visible; an identified
    subgroup-only conditional boundary has a separate limited-recourse adjustment.
    This is not liquidity, default, or a release of direct parent obligations.
    """
    cash = state["units"][u["id"]]["surplus_cash"]
    nonparent_restricted = max(0.0, state["restricted_claim"] - c["opening"]["parent_restricted_cash_assumption"])
    restricted = nonparent_restricted * u["nonparent_cash_share"] * 0.95
    financial_nci = (1 - u["owner"]) * (cash + restricted)
    joint_equity = ev - debt + cash + restricted
    loan_value = loan_rights["net_parent_contract_value_before_exclusive_tax"] if loan_rights else 0.0
    ordinary_pool = joint_equity - loan_value
    total_nci = (1 - u["owner"]) * max(0.0, ordinary_pool)
    if u["equity_boundary"] == "parent_direct_full_obligations":
        limited_adjustment = 0.0
        parent_equity = joint_equity
    elif u["equity_boundary"] == "limited_subgroup_zero_extra_parent_recourse_budget":
        need(u["parent_recourse_budget"] == 0 and u["extra_parent_support_cash_budget"] == 0, "Unsupported parent obligation cannot be waived")
        limited_adjustment = max(0.0, -ordinary_pool)
        parent_equity = loan_value + u["owner"] * max(0.0, ordinary_pool)
    else:
        raise TechnicalFailure("Unspecified equity boundary")
    close(joint_equity - total_nci + limited_adjustment, parent_equity, "Parent/NCI/recourse equity allocation")
    return {"entity_equity_before_nci": joint_equity, "entity_financial_nci_already_in_asset_bridge": financial_nci,
            "total_entity_economic_nci": total_nci, "operating_nci_allocation": total_nci - financial_nci,
            "limited_recourse_adjustment": limited_adjustment, "parent_entity_equity": parent_equity,
            "equity_boundary": u["equity_boundary"], "debt_perimeter": u["debt_perimeter"],
            "extra_parent_recourse_budget": u["parent_recourse_budget"], "extra_parent_support_cash_budget": u["extra_parent_support_cash_budget"],
            "ordinary_equity_pool_after_parent_loan_rights": ordinary_pool,
            "loan_rights": loan_rights,
            "conditional_subgroup_boundary_not_legal_certification": u["equity_boundary"] != "parent_direct_full_obligations",
            "ordinary_equity_floor_at_zero": ordinary_pool < 0}


def simulate_once(c, maturity_allowance=None):
    validate(c)
    s = initial_state(c)
    initial = copy.deepcopy(s)
    rows, states, constraints = [], [copy.deepcopy(s)], []
    path, n = c["active_path"], c["horizon"]
    for t in range(1, n + 1):
        i = t - 1
        opening_cash = total_liquid_state(s)
        parent = s["units"]["manufacturing"]
        interest_by_unit = {k: max(0, v["surplus_cash"]) * path["after_tax_cash_interest_rate"] for k, v in s["units"].items()}
        for k, interest in interest_by_unit.items():
            s["units"][k]["surplus_cash"] += interest
        locked_interest = s["parent_locked_deposit"] * path["after_tax_cash_interest_rate"]
        parent["surplus_cash"] += locked_interest
        treasury_interest = s["treasury_cash"] * path["after_tax_cash_interest_rate"]
        treasury_up = treasury_interest * c["distribution"]["treasury_interest_upstream_ratio"]
        s["treasury_cash"] += treasury_interest - treasury_up
        parent["surplus_cash"] += treasury_up
        finance_income_parent, finance_gross_cash, finance_nci_cash = 0.0, 0.0, 0.0
        for a in s["finance"]:
            dividend = a["book"] * a["after_tax_cash_yield"] if a["created_period"] < t else 0
            finance_gross_cash += dividend
            finance_nci_cash += dividend * (1 - a["owner"])
            finance_income_parent += dividend * a["owner"]
        parent["surplus_cash"] += finance_income_parent
        claim_release = 0.0
        internal_transfer = 0.0
        if t == c["distribution"]["parent_term_maturity_period"]:
            parent["surplus_cash"] += s["parent_locked_deposit"]
            s["parent_locked_deposit"] = 0
        if t == c["distribution"]["legacy_receivable_collection_period"]:
            internal_transfer = s["legacy_payer_cash"]
            parent["surplus_cash"] += internal_transfer + s["external_dividend_claim"]
            claim_release += s["external_dividend_claim"]
            s["legacy_payer_cash"] = 0
            s["external_dividend_claim"] = 0
        if t == c["distribution"]["restricted_cash_release_period"]:
            parent_part = min(s["restricted_claim"], c["opening"]["parent_restricted_cash_assumption"])
            parent["surplus_cash"] += parent_part
            for u in c["units"]:
                if u["id"] != "manufacturing":
                    s["units"][u["id"]]["surplus_cash"] += (s["restricted_claim"] - parent_part) * u["nonparent_cash_share"]
            claim_release += s["restricted_claim"]
            s["restricted_claim"] = 0
        project_cash = {u["id"]: 0.0 for u in c["units"]}
        project_expense = {u["id"]: 0.0 for u in c["units"]}
        financial_calls, project_rows = 0.0, []
        for p in c["projects"]:
            cash = p["future_cash"] * p["payment_weights"][i]
            ps = s["projects"][p["id"]]
            old_payable = min(cash, ps["prior_payable_remaining"])
            ps["prior_payable_remaining"] -= old_payable
            ps["cumulative_future_cash"] += cash
            expense = p.get("expense_cash_schedule", [0.0] * n)[i]
            if p["type"] == "operating":
                need(cash + EPS >= old_payable + expense, "Included payable/expense exceed project cash")
                project_cash[p["unit"]] += cash
                project_expense[p["unit"]] += expense
                ps["cip"] += cash - old_payable - expense
                commissioned = ps["cip"] if t in p["commission_periods"] else 0.0
                if commissioned > 0:
                    s["units"][p["unit"]]["cohorts"].append({"basis": commissioned, "life": p["asset_life"], "start": t + 1})
                    ps["cip"] = 0
            else:
                financial_calls += cash
                commissioned = 0.0
                if cash > 0:
                    s["finance"].append({"id": p["id"] + "_call_" + str(t), "book": cash, "owner": p["owner"], "value_multiplier": p["carrying_value_multiplier"], "after_tax_cash_yield": p["after_tax_cash_yield"], "created_period": t})
            project_rows.append({"id": p["id"], "payer": p["payer"], "type": p["type"], "cash_paid": cash, "settled_prior_booked_payable": old_payable, "included_expense_cash": expense, "new_asset_cost": cash - old_payable - expense, "commissioned": commissioned, "ending_cip": ps["cip"], "unpaid_selected_cash": p["future_cash"] - ps["cumulative_future_cash"]})
        parent["surplus_cash"] -= financial_calls
        park_purchase_cash = 0.0
        if c["park_real_estate"]["base_choice"] == "buy":
            park_purchase_cash = c["park_real_estate"]["property_purchase_sensitivity_cash"] * c["park_real_estate"]["purchase_payment_weights"][i]
            project_cash["manufacturing"] += park_purchase_cash
            if park_purchase_cash > 0:
                parent["cohorts"].append({"basis": park_purchase_cash, "life": c["park_real_estate"]["purchase_asset_life"], "start": t + 1})
        unit_rows, total_fcfe, total_buffer_delta = {}, 0.0, 0.0
        for u in c["units"]:
            us = s["units"][u["id"]]
            baseline_revenue = us["revenues"][i]
            budget = operating_budget(c, u, baseline_revenue, t)
            revenue = budget["revenue"]
            next_revenue = us["revenues"][i + 1] if t < n else baseline_revenue * (1 + u["terminal_growth"])
            usage = budget["usage"]
            target = inventory_target(c, u, next_revenue, t)
            pool = inventory_step(us["inventory_units"], us["inventory_book"], usage, target, u["new_cost_index"][i], u["inventory_loss_rate"])
            dep = depreciation(us["cohorts"], t)
            maintenance = dep
            if maintenance > 0:
                us["cohorts"].append({"basis": maintenance, "life": u["opening_ppe_remaining_life"], "start": t + 1})
            rent = u["legacy_annual_cash_rent"]
            if u["id"] == "manufacturing" and c["park_real_estate"]["base_choice"] == "rent" and t >= c["park_real_estate"]["starts_period"]:
                rent += c["park_real_estate"]["annual_cash_rent"]
            cogs = pool["consumption_cost"] + pool["loss_cost"] + revenue * u["conversion_cash_cost_ratio"]
            cash_opex = budget["cash_opex"] + budget["site_cost"]
            one_off = budget["actual_exit_cash"] + budget["recovery_loss"] + project_expense[u["id"]]
            # Foregone collection is a realized receivable loss, NOT another cash
            # payment or another subtraction from the closing NWC/pool balance.
            ebitda = revenue - cogs - cash_opex - rent - one_off
            ebit = ebitda - dep
            operating_tax = max(0.0, ebit) * u["tax_rate"]
            nopat = ebit - operating_tax
            interest = us["bank_debt"] * path["bank_interest_rate"]
            equity_tax = max(0.0, ebit - interest) * u["tax_rate"]
            profit = ebit - interest - equity_tax
            other_nwc = budget["nwc_revenue"] * u["other_nwc_ratio"]
            buffer = budget["nwc_revenue"] * u["cash_buffer_ratio"]
            delta_inventory = pool["closing_book"] - us["inventory_book"]
            delta_other = other_nwc - us["other_nwc"]
            delta_buffer = buffer - us["buffer"]
            capex = maintenance + project_cash[u["id"]] - project_expense[u["id"]]
            fcff = nopat + dep - capex - delta_inventory - delta_other - delta_buffer
            fcfe = profit + dep - capex - delta_inventory - delta_other - delta_buffer
            close(fcff - interest + operating_tax - equity_tax, fcfe, "FCFF/FCFE debt-tax bridge")
            us["inventory_units"], us["inventory_book"] = pool["closing_units"], pool["closing_book"]
            us["other_nwc"], us["buffer"] = other_nwc, buffer
            us["surplus_cash"] += fcfe
            total_fcfe += fcfe
            total_buffer_delta += delta_buffer
            unit_rows[u["id"]] = {"revenue": revenue, "unrestructured_baseline_revenue": baseline_revenue, "capital_choice_operating_bridge": budget, "one_off_ebit_cost": one_off, "project_included_expense": project_expense[u["id"]], "pool": pool, "cogs": cogs, "gross_margin": (revenue - cogs) / revenue if revenue else None, "cash_opex": cash_opex, "cash_rent": rent, "depreciation": dep, "ebitda": ebitda, "ebit": ebit, "operating_tax": operating_tax, "nopat": nopat, "bank_interest": interest, "equity_tax": equity_tax, "operating_equity_profit": profit, "financial_cash_interest": interest_by_unit[u["id"]], "maintenance_cash": maintenance, "project_cash": project_cash[u["id"]], "delta_inventory": delta_inventory, "delta_other_nwc": delta_other, "delta_cash_buffer": delta_buffer, "fcff": fcff, "fcfe_operating": fcfe, "surplus_cash_before_distribution": us["surplus_cash"], "bank_debt": us["bank_debt"]}
        unallocated_interest = s.get("unallocated_group_bank_debt", 0.0) * path["bank_interest_rate"]
        parent["surplus_cash"] -= unallocated_interest
        support = support_cash_step(c, s, unit_rows, t, maturity_allowance)
        parent_profit = unit_rows["manufacturing"]["operating_equity_profit"] + interest_by_unit["manufacturing"] + locked_interest + treasury_up + finance_income_parent - unallocated_interest + support["parent_profit_addition"]
        nci_cash = finance_nci_cash
        subsidiary_upstream = 0.0
        parent_cash_before_upstream = parent["surplus_cash"]
        for u in c["units"]:
            us = s["units"][u["id"]]
            if u["id"] != "manufacturing" and us["surplus_cash"] < -EPS:
                constraints.append({"period": t, "unit": u["id"], "code": "UNFUNDED_OPERATING_OR_COMMITTED_CASH", "shortfall": -us["surplus_cash"], "affects": ["main", "auxiliary", "distributions", "terminal"]})
            if u["id"] == "manufacturing":
                continue
            net_profit = unit_rows[u["id"]]["operating_equity_profit"] + interest_by_unit[u["id"]]
            is_borrower = support["active"] and u["id"] == c["capital_revision"]["borrower"]
            if is_borrower:
                net_profit -= support["borrower_profit_deduction"]
            future_project_cash_reserve = sum(max(0.0, p["future_cash"] - s["projects"][p["id"]]["cumulative_future_cash"]) for p in c["projects"] if p["type"] == "operating" and p["unit"] == u["id"])
            # A payout policy, not a second asset deduction or immediate cash expense.
            paid = min(max(0.0, us["surplus_cash"] - future_project_cash_reserve), max(0.0, net_profit) * u["subsidiary_payout_ratio"])
            if is_borrower and support["ordinary_distribution_blocked"]:
                paid = 0.0
            us["surplus_cash"] -= paid
            upstream = paid * u["owner"]
            parent["surplus_cash"] += upstream
            subsidiary_upstream += upstream
            parent_profit += upstream
            nci_cash += paid * (1 - u["owner"])
            unit_rows[u["id"]]["subsidiary_distribution"] = paid
            unit_rows[u["id"]]["parent_upstream"] = upstream
            unit_rows[u["id"]]["retained_for_remaining_project_cash"] = future_project_cash_reserve
        parent_cash_after_upstream = parent["surplus_cash"]
        timing_policy = c["parent_cash_timing_policy"]
        eligible_capital = sum(row["cash_paid"] - row["settled_prior_booked_payable"] for p, row in zip(c["projects"], project_rows) if p["id"] in timing_policy["adjustable_new_capital_project_ids"] and (p["unit"] == "manufacturing" or p["type"] == "financial"))
        if timing_policy["park_purchase_adjustable_after_upstream"]:
            eligible_capital += park_purchase_cash
        timing = {"parent_surplus_before_operating_subsidiary_upstream": parent_cash_before_upstream,
                  "adopted_operating_subsidiary_upstream": subsidiary_upstream,
                  "parent_surplus_after_upstream_before_holder_payment": parent_cash_after_upstream,
                  "eligible_adjustable_new_capital_payments": eligible_capital,
                  "timing_dependency": parent_cash_before_upstream < -EPS,
                  "annual_net_covered": parent_cash_after_upstream >= -EPS,
                  "adopted_payment_order_condition": False,
                  "condition": timing_policy["assumption"],
                  "does_not_certify_no_intra_year_shortfall": True}
        if parent_cash_after_upstream < -EPS:
            constraints.append({"period": t, "unit": "listed_parent", "code": "PARENT_ANNUAL_CASH_SHORTFALL_AFTER_ADOPTED_UPSTREAM", "shortfall": -parent_cash_after_upstream, "cash_before_upstream": parent_cash_before_upstream, "cash_after_upstream": parent_cash_after_upstream, "affects": ["main", "auxiliary", "distributions", "terminal"]})
        elif parent_cash_before_upstream < -EPS:
            timing["adopted_payment_order_condition"] = bool(timing_policy["adopt_adjustable_capital_payments_after_available_upstream"] and not timing_policy["observed_conflicting_fixed_future_dates_in_read_sources"] and -parent_cash_before_upstream <= eligible_capital + EPS)
            if not timing["adopted_payment_order_condition"]:
                constraints.append({"period": t, "unit": "listed_parent", "code": "PARENT_ANNUAL_NET_COVERED_BUT_TIMING_CONDITION_UNADOPTED", "not_an_annual_net_funding_failure": True, "cash_before_upstream": parent_cash_before_upstream, "cash_after_upstream": parent_cash_after_upstream, "eligible_adjustable_capital": eligible_capital, "affects": ["main", "auxiliary", "distributions", "terminal"]})
        current_reserve = max(0.0, parent_profit) * c["distribution"]["statutory_reserve_ratio"]
        pre_cutoff_reserve = max(0.0, c["opening"].get("pre_cutoff_parent_profit_pending_annual_reserve", 0)) * c["distribution"]["statutory_reserve_ratio"] if t == 1 else 0.0
        reserve = current_reserve + pre_cutoff_reserve
        optional_reserve = max(0.0, parent_profit) * c["distribution"]["discretionary_reserve_ratio"]
        available_re = s["parent_re"] + parent_profit - reserve - optional_reserve
        current_distributable_profit = max(0.0, parent_profit - current_reserve - optional_reserve)
        requested = max(0.0, parent_profit) * c["distribution"]["parent_payout_ratio"]
        actual = min(requested, max(0.0, parent["surplus_cash"]), max(0.0, available_re))
        floor = current_distributable_profit * c["distribution"]["policy_floor_ratio"]
        if actual + EPS < floor and not c["distribution"]["allow_policy_exception"]:
            constraints.append({"period": t, "unit": "listed_parent", "code": "PAYOUT_REQUIRES_UNADOPTED_POLICY_EXCEPTION", "shortfall": floor - actual, "affects": ["distributions", "terminal"]})
        parent["surplus_cash"] -= actual
        s["parent_re"] = available_re - actual
        s["statutory_reserve"] += reserve
        s["other_reserve"] += optional_reserve
        close(s["parent_re"], states[-1]["parent_re"] + parent_profit - reserve - optional_reserve - actual, "Parent RE roll-forward")
        closing_cash = total_liquid_state(s)
        expected_delta = total_fcfe + total_buffer_delta + sum(interest_by_unit.values()) + locked_interest + treasury_interest + finance_gross_cash + claim_release - financial_calls - nci_cash - actual - unallocated_interest - support["parent_interest_tax"] - support["bank_principal_paid"]
        close(closing_cash - opening_cash, expected_delta, "Group liquidity conservation; internal upstream/legacy transfer must cancel")
        rows.append({**period_labels(n)[i], "units": unit_rows, "support_loan_waterfall": support, "unallocated_bank_interest_parent_cash_cost": unallocated_interest, "projects": project_rows, "park_purchase_cash": park_purchase_cash, "financial_calls": financial_calls, "financial_income_parent": finance_income_parent, "financial_gross_cash_income": finance_gross_cash, "subsidiary_upstream": subsidiary_upstream, "parent_cash_timing": timing, "legacy_internal_cash_transfer_no_new_profit": internal_transfer, "old_external_claim_or_restricted_release_no_new_profit": claim_release, "nci_cash_distribution": nci_cash, "parent_profit": parent_profit, "statutory_reserve_addition": reserve, "statutory_reserve_on_pre_cutoff_profit": pre_cutoff_reserve, "optional_reserve_addition": optional_reserve, "parent_retained_earnings": s["parent_re"], "requested_parent_distribution": requested, "actual_parent_distribution": actual, "payout_reduced_for_capacity": requested - actual, "group_liquidity_open": opening_cash, "group_liquidity_close": closing_cash, "financial_bridge": financial_bridge(c, s)})
        states.append(copy.deepcopy(s))
    return {"initial_state": initial, "states": states, "periods": rows, "constraints": constraints}


def terminal_for_unit(c, sim, u):
    n = c["horizon"]
    row = sim["periods"][-1]["units"][u["id"]]
    s = sim["states"][-1]["units"][u["id"]]
    g = u["terminal_growth"]
    dep = depreciation(s["cohorts"], n + 1) * (1 + g)
    ebit = row["ebitda"] * (1 + g) - dep
    nopat = ebit - max(0.0, ebit) * u["tax_rate"]
    cip = sum(sim["states"][-1]["projects"][p["id"]]["cip"] for p in c["projects"] if p["type"] == "operating" and p["unit"] == u["id"])
    capital = net_cohorts(s["cohorts"], n) + cip + s["inventory_book"] + s["other_nwc"] + s["buffer"]
    growth_reinvestment = g * capital
    avg = row["pool"]["weighted_average_cost"]
    convergence = abs(avg - u["new_cost_index"][-1]) / u["new_cost_index"][-1]
    return {"first_terminal_nopat": nopat, "full_commissioned_depreciation": dep, "maintenance_equals_full_depreciation": dep, "capital_retained": capital, "growth": g, "growth_reinvestment": growth_reinvestment, "recurring_fcff": nopat - growth_reinvestment, "replacement_cost_convergence_gap": convergence, "remaining_cip": cip, "no_inventory_liquidation_or_capital_release": True}


def financial_commitment_npv(c, at, discount):
    """Only FUTURE calls after at; already paid financial assets live in asset bridge."""
    total, details = 0.0, []
    n = c["horizon"]
    scale = c["active_path"]["financial_value_multiplier_scale"]
    for p in c["projects"]:
        if p["type"] != "financial":
            continue
        for t, w in enumerate(p["payment_weights"], 1):
            if t <= at or w == 0:
                continue
            cash = p["future_cash"] * w
            pv_call = cash / (1 + discount) ** (t - at)
            pv_returns = sum(cash * p["after_tax_cash_yield"] / (1 + discount) ** (j - at) for j in range(t + 1, n + 1))
            pv_asset = cash * p["carrying_value_multiplier"] * scale / (1 + discount) ** (n - at)
            value = p["owner"] * (pv_returns + pv_asset - pv_call)
            total += value
            details.append({"project": p["id"], "call_period": t, "pv_cash_call": pv_call, "pv_cash_returns": pv_returns, "pv_acquired_asset": pv_asset, "attributable_net_value": value})
    return {"value": total, "details": details, "discount_rate": discount}


def loan_collection_value(principal, arrears, annual_cash, contract_rate, discount):
    """Closed-form cash-sweep recovery of existing claims, not a new forecast.

    Uses selected flat terminal cash AFTER external interest. No new funding,
    no EV-to-cash conversion, no arbitrary forgiveness after a chosen window.
    """
    p, a, f, r, d = principal, arrears, max(0.0, annual_cash), contract_rate, discount
    need(d > 0 and 0 <= r <= d, "Recovery discount must cover contract rate in this selected closed form")
    if p + a <= EPS or f <= EPS:
        return {"interest_pv": 0.0, "principal_pv": 0.0, "payoff_years": None if p + a > EPS else 0, "principal_never_repaid_under_flat_cash": p > EPS}
    discount_factor = lambda years: math.exp(-years * math.log1p(d))
    annuity = lambda years: (1 - discount_factor(years)) / d
    net = f - p * r
    if net <= EPS:
        # All available cash pays interest; principal/remaining legal claim persists.
        return {"interest_pv": f / d, "principal_pv": 0.0, "payoff_years": None, "principal_never_repaid_under_flat_cash": p > EPS}
    full_arrears_years = int(math.floor(a / net))
    remaining_arrears = max(0.0, a - full_arrears_years * net)
    first_interest = remaining_arrears + p * r
    first_principal = min(p, max(0.0, f - first_interest))
    remaining = max(0.0, p - first_principal)
    interest_pv = f * annuity(full_arrears_years) + first_interest * discount_factor(full_arrears_years + 1)
    principal_pv = first_principal * discount_factor(full_arrears_years + 1)
    extra_periods = 0
    if remaining > EPS:
        extra_periods = int(math.ceil(remaining / f)) if r <= EPS else int(math.ceil(math.log(f / (f - r * remaining)) / math.log1p(r)))
        extra_periods = max(1, extra_periods)
        before_last = max(0.0, remaining - f * (extra_periods - 1)) if r <= EPS else max(0.0, remaining * (1 + r) ** (extra_periods - 1) - f * math.expm1((extra_periods - 1) * math.log1p(r)) / r)
        final_cash = min(f, before_last * (1 + r))
        ratio = (1 + r) / (1 + d)
        geometric = extra_periods - 1 if abs(ratio - 1) <= EPS else (1 - ratio ** (extra_periods - 1)) / (1 - ratio)
        rest_principal_pv = (f - r * remaining) * geometric / (1 + d) + before_last * discount_factor(extra_periods)
        rest_cash_pv = f * annuity(extra_periods - 1) + final_cash * discount_factor(extra_periods)
        shift = discount_factor(full_arrears_years + 1)
        principal_pv += rest_principal_pv * shift
        interest_pv += max(0.0, rest_cash_pv - rest_principal_pv) * shift
    need(principal_pv <= p + EPS * max(1.0, p), "Discounted collection cannot exceed legal principal")
    return {"interest_pv": interest_pv, "principal_pv": principal_pv,
            "payoff_years": full_arrears_years + (1 if first_interest + first_principal > EPS else 0) + extra_periods,
            "principal_never_repaid_under_flat_cash": False,
            "unpaid_interest_noncapitalizing": True}


def loan_rights_projection(c, sim, at, joint_equity, terminal_capacity, terminal_annual_cash, discount):
    """Same entity value, parent cash priority; no external group loan asset.

    Future actual funding is a cost of the parent-only commitment. Terminal claim
    recovery is an economic value bound, never cash available for D or legal release.
    """
    if "support_loan" not in sim["states"][at]:
        return None
    n = c["horizon"]
    future = sim["periods"][at:]
    pv_draws = sum(r["support_loan_waterfall"]["draw"] / (1 + discount) ** (r["period"] - at) for r in future)
    pv_interest = sum(r["support_loan_waterfall"]["interest_paid"] / (1 + discount) ** (r["period"] - at) for r in future)
    pv_principal = sum(r["support_loan_waterfall"]["principal_paid"] / (1 + discount) ** (r["period"] - at) for r in future)
    end = sim["states"][-1]["support_loan"]
    policy = c["capital_revision"]["loan"]
    tail = loan_collection_value(end["principal"], end["unpaid_interest"], terminal_annual_cash, policy["contract_rate"], discount)
    gross_tail = tail["interest_pv"] + tail["principal_pv"]
    factor = min(1.0, max(0.0, terminal_capacity) / gross_tail) if gross_tail > EPS else 0.0
    terminal_interest = tail["interest_pv"] * factor
    terminal_principal = tail["principal_pv"] * factor
    terminal_recovery = terminal_interest + terminal_principal
    divisor = (1 + discount) ** (n - at)
    gross = pv_interest + pv_principal + terminal_recovery / divisor
    raw_net = gross - pv_draws
    # Positive priority cannot create value beyond the same entity equity pool.
    # Negative net funding subsidy survives a zero ordinary-equity floor.
    net = min(raw_net, max(0.0, joint_equity)) if raw_net > 0 else raw_net
    parent_tax = (pv_interest + terminal_interest / divisor) * c["units"][0]["tax_rate"]
    return {"at_period": at, "discount_rate": discount, "future_actual_draws_pv": pv_draws,
            "future_interest_receipts_pv": pv_interest, "future_principal_receipts_pv": pv_principal,
            "terminal_entity_equity_capacity": max(0.0, terminal_capacity),
            "terminal_annual_cash_after_external_interest": terminal_annual_cash,
            "closed_form_collection_tail": tail, "tail_value_cap_factor": factor,
            "legal_claim_not_extinguished_by_valuation": True,
            "terminal_interest_recovery_value": terminal_interest,
            "terminal_principal_recovery_value": terminal_principal,
            "expected_principal_recovery_pv": pv_principal + terminal_principal / divisor,
            "uncapped_net_contract_value": raw_net,
            "net_parent_contract_value_before_exclusive_tax": net,
            "parent_exclusive_interest_tax_pv": parent_tax,
            "principal_legal_at_terminal": end["principal"],
            "unpaid_interest_legal_at_terminal": end["unpaid_interest"],
            "not_group_external_asset_or_distributable_cash": True,
            "terminal_recovery_is_value_allocation_not_actual_repayment": True}


def joint_unit_equity(c, state, u, ev, debt):
    restricted = max(0.0, state["restricted_claim"] - c["opening"]["parent_restricted_cash_assumption"]) * u["nonparent_cash_share"] * 0.95
    return ev - debt + state["units"][u["id"]]["surplus_cash"] + restricted


def recourse_bound(c, sim, units, at):
    """Incidence sensitivity for recorded external principal, not new debt."""
    details = []
    for u in c["units"]:
        if u["equity_boundary"] == "parent_direct_full_obligations":
            continue
        state = sim["states"][at]["units"][u["id"]]
        unrecovered_bank_bound = max(0.0, state["bank_debt"] - max(0.0, state["surplus_cash"]))
        loss = min(units[u["id"]]["limited_recourse_adjustment"], unrecovered_bank_bound)
        details.append({"unit": u["id"], "additional_parent_loss_bound": loss,
                        "already_recorded_bank_principal": state["bank_debt"]})
    upper = sum(x["additional_parent_loss_bound"] for x in details)
    return {"base_additional_external_recourse": 0.0, "maximum_extra_parent_value_loss_bound": upper,
            "per_share_loss_bound": upper * 1000000 / c["shares"], "details": details,
            "not_additional_group_bank_debt": True,
            "not_an_assumption_of_legal_release": True}


def simulate(c):
    """Finite accounting replay, not an iterative liquidity or valuation solver."""
    pilot = simulate_once(c)
    if "capital_profile" not in c:
        return pilot
    policy = c["capital_revision"]["loan"]
    maturity = policy["maturity_period"]
    # Use the independently locked credit rate, not value-range endpoint rates.
    bridge = ev_bridge(c, pilot, maturity, policy["credit_discount_rate"])
    rights = bridge["units"][c["capital_revision"]["borrower"]]["nci_details"]["loan_rights"]
    book = pilot["states"][maturity]["support_loan"]["carrying_principal"]
    allowance = max(0.0, book - rights["expected_principal_recovery_pv"])
    final = simulate_once(c, allowance) if allowance > EPS else pilot
    # Draw window is closed before impairment: only parent RE/D may change.
    for before, after in zip(pilot["periods"], final["periods"]):
        for key in ("draw", "interest_paid", "principal_paid", "bank_principal_paid"):
            close(before["support_loan_waterfall"][key], after["support_loan_waterfall"][key], "Credit replay must not change legal loan cash waterfall")
        for u in c["units"]:
            for key in ("revenue", "fcff", "fcfe_operating"):
                close(before["units"][u["id"]][key], after["units"][u["id"]][key], "Credit replay must not change operating budget")
    final["credit_review"] = {"period": maturity, "credit_discount_rate": policy["credit_discount_rate"],
                              "carrying_principal_before_allowance": book,
                              "expected_principal_recovery_pv": rights["expected_principal_recovery_pv"],
                              "allowance_no_cash_or_group_EV_deduction": allowance,
                              "legal_claim_not_extinguished": True,
                              "finite_passes": 2 if allowance > EPS else 1}
    return final


def ev_bridge(c, sim, at=0, rate=None):
    rate = c["valuation"]["main_discount_rate"] if rate is None else rate
    need(rate > 0, "Nonpositive DCF rate")
    n = c["horizon"]
    units, terminal_constraints = {}, []
    for u in c["units"]:
        terminal = terminal_for_unit(c, sim, u)
        need(rate > terminal["growth"], "DCF rate must exceed terminal growth")
        tv = terminal["recurring_fcff"] / (rate - terminal["growth"])
        cash_pv = sum(sim["periods"][t - 1]["units"][u["id"]]["fcff"] / (1 + rate) ** (t - at) for t in range(at + 1, n + 1))
        tv_pv = tv / (1 + rate) ** (n - at)
        ev = cash_pv + tv_pv
        debt = sim["states"][at]["units"][u["id"]]["bank_debt"]
        rights = None
        if u.get("health_restructure"):
            capacity = joint_unit_equity(c, sim["states"][-1], u, tv, sim["states"][-1]["units"][u["id"]]["bank_debt"])
            rights = loan_rights_projection(c, sim, at, joint_unit_equity(c, sim["states"][at], u, ev, debt), capacity, terminal["recurring_fcff"] - sim["states"][-1]["units"][u["id"]]["bank_debt"] * c["active_path"]["bank_interest_rate"], rate)
        nci_parts = nci_allocation(c, sim["states"][at], u, ev, debt, rights)
        nci = nci_parts["operating_nci_allocation"]
        units[u["id"]] = {"full_group_unit_ev": ev, "explicit_fcff_pv": cash_pv, "terminal_pv": tv_pv, "bank_debt": debt, "operating_nci_economic_equity": nci, "limited_recourse_adjustment": nci_parts["limited_recourse_adjustment"], "nci_details": nci_parts, "terminal": terminal}
        if terminal["replacement_cost_convergence_gap"] > c["valuation"]["terminal_cost_convergence_tolerance"]:
            terminal_constraints.append({"period": n, "unit": u["id"], "code": "COST_POOL_NOT_READY_FOR_STABLE_TERMINAL", "affects": ["main", "terminal"]})
        if terminal["remaining_cip"] > EPS:
            terminal_constraints.append({"period": n, "unit": u["id"], "code": "UNFINISHED_PROJECT_AT_TERMINAL", "affects": ["main", "terminal"]})
    group_ev = sum(v["full_group_unit_ev"] for v in units.values())
    unallocated_debt = sim["states"][at].get("unallocated_group_bank_debt", 0.0)
    debt = sum(v["bank_debt"] for v in units.values()) + unallocated_debt
    nci = sum(v["operating_nci_economic_equity"] for v in units.values())
    limited_adjustment = sum(v["limited_recourse_adjustment"] for v in units.values())
    assets = financial_bridge(c, sim["states"][at])
    commitments = financial_commitment_npv(c, at, rate)
    loan_tax_pv = sum((v["nci_details"]["loan_rights"] or {}).get("parent_exclusive_interest_tax_pv", 0.0) for v in units.values())
    equity = group_ev - debt - nci + limited_adjustment + assets["attributable_net_assets"] + commitments["value"] - loan_tax_pv
    return {"at_period": at, "discount_rate": rate, "units": units, "unallocated_group_bank_debt_fully_retained": unallocated_debt, "parent_exclusive_loan_interest_tax_pv": loan_tax_pv, "recourse_sensitivity": recourse_bound(c, sim, units, at), "full_group_ev": group_ev, "full_external_bank_debt": debt, "operating_nci_economic_value": nci, "limited_recourse_adjustment": limited_adjustment, "limited_recourse_adjustment_is_valuation_only_not_cash": True, "nonoperating_assets": assets, "future_financial_commitment_net_value": commitments, "ordinary_equity_value": equity, "ordinary_equity_value_per_share": equity * 1000000 / c["shares"], "terminal_pv_share_of_ev": sum(x["terminal_pv"] for x in units.values()) / group_ev if abs(group_ev) > EPS else None, "constraints": terminal_constraints}


def auxiliary_value(c, sim):
    """No-growth earnings power at period-5 revenue, fully installed cost base.

    Not a recopy of the main terminal: no operating growth perpetuity, no stock
    release credit; deduct still-to-be-paid operating project cash at date zero.
    """
    rate = c["valuation"]["auxiliary_capitalization_rate"]
    need(rate > 0, "Auxiliary capitalization rate must be positive")
    units, reasons = {}, []
    n = c["horizon"]
    for u in c["units"]:
        revenue = sim["periods"][4]["units"][u["id"]]["revenue"]
        tail = sim["periods"][-1]["units"][u["id"]]
        cost_index = tail["pool"]["weighted_average_cost"]
        usage = revenue * u["usage_per_revenue"]
        opex = revenue * u["cash_opex_ratio"][-1]
        site_cost = 0.0
        if u.get("health_restructure"):
            normal = operating_budget(c, u, sim["periods"][4]["units"][u["id"]]["unrestructured_baseline_revenue"], n, terminal=True)
            revenue, usage, opex = normal["revenue"], normal["usage"], normal["cash_opex"]
        if u.get("beauty_stage"):
            # Auxiliary freezes actual period5 sales, but charges ALL installed costs.
            site_cost = c["capital_profile"]["beauty_site_cost"]
        steady_inventory = usage * u["coverage_years"][-1] * cost_index
        recurring_loss = steady_inventory * u["inventory_loss_rate"] / (1 - u["inventory_loss_rate"])
        material = usage * cost_index
        rent = tail["cash_rent"]
        dep = depreciation(sim["states"][-1]["units"][u["id"]]["cohorts"], n + 1)
        ebit = revenue - material - recurring_loss - revenue * u["conversion_cash_cost_ratio"] - opex - site_cost - rent - dep
        nopat = ebit - max(0.0, ebit) * u["tax_rate"]
        maintenance = dep
        owner_cash = nopat + dep - maintenance
        project_pv = sum(p["future_cash"] * w / (1 + rate) ** t for p in c["projects"] if p["type"] == "operating" and p["unit"] == u["id"] for t, w in enumerate(p["payment_weights"], 1))
        if u["id"] == "manufacturing" and c["park_real_estate"]["base_choice"] == "buy":
            project_pv += sum(c["park_real_estate"]["property_purchase_sensitivity_cash"] * w / (1 + rate) ** t for t, w in enumerate(c["park_real_estate"]["purchase_payment_weights"], 1))
        restructuring_pv = 0.0
        if u.get("health_restructure"):
            p = c["capital_profile"]
            restructuring_pv = sum((cash + loss) / (1 + rate) ** t for t, (cash, loss) in enumerate(zip(p["health_actual_cash_payments"], p["health_reduced_recovery"]), 1))
        ev = owner_cash / rate - project_pv - restructuring_pv
        debt = sim["states"][0]["units"][u["id"]]["bank_debt"]
        rights = None
        if u.get("health_restructure"):
            capacity = joint_unit_equity(c, sim["states"][-1], u, owner_cash / rate, sim["states"][-1]["units"][u["id"]]["bank_debt"])
            rights = loan_rights_projection(c, sim, 0, joint_unit_equity(c, sim["states"][0], u, ev, debt), capacity, owner_cash - sim["states"][-1]["units"][u["id"]]["bank_debt"] * c["active_path"]["bank_interest_rate"], rate)
        nci_parts = nci_allocation(c, sim["states"][0], u, ev, debt, rights)
        nci = nci_parts["operating_nci_allocation"]
        capital = net_cohorts(sim["states"][-1]["units"][u["id"]]["cohorts"], n) + steady_inventory + revenue * (u["other_nwc_ratio"] + u["cash_buffer_ratio"])
        units[u["id"]] = {"normal_revenue": revenue, "normal_nopat": nopat, "full_installed_maintenance": maintenance, "normal_owner_cash": owner_cash, "capitalization_factor": 1 / rate, "operating_project_cash_pv": project_pv, "restructuring_cash_and_foregone_recovery_pv": restructuring_pv, "normal_cash_opex": opex, "normal_site_cost": site_cost, "ev": ev, "bank_debt": debt, "operating_nci_economic_value": nci, "limited_recourse_adjustment": nci_parts["limited_recourse_adjustment"], "nci_details": nci_parts, "normal_required_capital": capital, "normal_roic": nopat / capital if capital > EPS else None}
        if owner_cash < 0:
            reasons.append({"unit": u["id"], "code": "NEGATIVE_NORMAL_EARNING_POWER_SIGNED_CONTRIBUTION_RETAINED", "normal_owner_cash": owner_cash, "affects": []})
    assets = financial_bridge(c, sim["states"][0])
    commitments = financial_commitment_npv(c, 0, c["valuation"]["main_discount_rate"])
    unallocated_debt = sim["states"][0].get("unallocated_group_bank_debt", 0.0)
    loan_tax_pv = sum((v["nci_details"]["loan_rights"] or {}).get("parent_exclusive_interest_tax_pv", 0.0) for v in units.values())
    equity = sum(v["ev"] - v["bank_debt"] - v["operating_nci_economic_value"] + v["limited_recourse_adjustment"] for v in units.values()) + assets["attributable_net_assets"] + commitments["value"] - unallocated_debt - loan_tax_pv
    return {"units": units, "unallocated_group_bank_debt_fully_retained": unallocated_debt, "parent_exclusive_loan_interest_tax_pv": loan_tax_pv, "recourse_sensitivity": recourse_bound(c, sim, units, 0), "limited_recourse_adjustment": sum(v["limited_recourse_adjustment"] for v in units.values()), "limited_recourse_adjustment_is_valuation_only_not_cash": True, "ordinary_equity_value": equity, "ordinary_equity_value_per_share": equity * 1000000 / c["shares"], "nonoperating_assets": assets, "future_financial_commitment_net_value": commitments, "constraints": reasons, "method_note": "No-growth earnings power with period5 sales and mature weighted-cost/installed-capital burden; no excess inventory release credit. Compare, never mechanically average with DCF."}


def affected(constraints, metric):
    return [x for x in constraints if metric in x["affects"]]


def evaluate_scenario(c, sim=None):
    sim = simulate(c) if sim is None else sim
    main = ev_bridge(c, sim, 0)
    y5 = ev_bridge(c, sim, 5)
    constraints = sim["constraints"] + main["constraints"]
    result = {"path": c["active_path"]["name"], "status": "CALCULATED", "raw_periods": sim["periods"], "raw_initial_state": sim["initial_state"], "raw_year5_state": sim["states"][5], "raw_main_method": main, "raw_year5_bridge": y5, "constraints": constraints}
    result["main_method"] = {"value_per_share": None if affected(constraints, "main") else main["ordinary_equity_value_per_share"], "null_reasons": affected(constraints, "main")}
    try:
        auxiliary = auxiliary_value(c, sim)
    except Exception as exc:
        raise TechnicalFailure("Auxiliary technical error; main/raw preserved: " + str(exc), result) from exc
    constraints.extend(auxiliary["constraints"])
    result["raw_auxiliary_method"] = auxiliary
    result["auxiliary_method"] = {"value_per_share": None if affected(constraints, "auxiliary") else auxiliary["ordinary_equity_value_per_share"], "null_reasons": affected(constraints, "auxiliary")}
    distributions, partial = [], []
    for row in sim["periods"][:5]:
        blocked = [x for x in affected(constraints, "distributions") if x.get("period", 0) <= row["period"]]
        value = row["actual_parent_distribution"] * 1000000 / c["shares"]
        distributions.append(None if blocked else value)
        partial.append({"period": row["period"], "from": row["from"], "to": row["to"], "raw_modeled_cash_per_share": value, "adopted_cash_per_share": None if blocked else value, "null_reasons": blocked})
    terminal_value = None if affected(constraints, "terminal") else y5["ordinary_equity_value_per_share"]
    result["partial_distribution_schedule"] = partial
    result["year5_value_per_share"] = terminal_value
    result["return_model"] = None if any(x is None for x in distributions) or terminal_value is None else {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": c["cutoff"], "base_case_distributions_per_share": distributions, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": terminal_value, "high": terminal_value}}}
    result["return_model_note"] = "Point-state diagnostic only. D=actual budgeted cash in five anniversary windows; Y5 uses identical state and remaining operating transition. No DDM equality asserted for current operating-DCF+net-assets value. Range endpoints require explicit parameter-combination diagnostics, not min/max across unrelated scenarios."
    a, b = result["main_method"]["value_per_share"], result["auxiliary_method"]["value_per_share"]
    result["method_gap_requires_explanation"] = None if a is None or b is None or abs(a) <= EPS else abs(a - b) / abs(a) > c["valuation"]["maximum_method_center_gap_for_explanation"]
    result["cash_buffer_is_operating_capital_not_added_again"] = True
    result["adopted_timing_dependencies"] = [{"period": row["period"], **row["parent_cash_timing"]} for row in sim["periods"] if row["parent_cash_timing"]["timing_dependency"]]
    result["recourse_boundaries_are_conditional_budgets_not_legal_certification"] = [{"unit": u["id"], "equity_boundary": u["equity_boundary"], "debt_perimeter": u["debt_perimeter"], "parent_recourse_budget": u["parent_recourse_budget"], "extra_parent_support_cash_budget": u["extra_parent_support_cash_budget"]} for u in c["units"]]
    result["return_model_note"] += " Subgroup equity retains a conditional zero-additional-external-recourse boundary; any separately adopted finite internal-loan commitment and priority is valued explicitly, not waived. Unallocated external principal is fully retained."
    result["credit_review"] = sim.get("credit_review")
    result["capital_profile"] = c.get("capital_profile_name")
    result["adopted_separate_nonrevolving_parent_loan_policy"] = copy.deepcopy(c.get("capital_revision", {}).get("loan"))
    result["recourse_sensitivity"] = main.get("recourse_sensitivity")
    if result["adopted_timing_dependencies"]:
        result["return_model_note"] += " Periods with before/after-upstream timing dependency: " + ",".join(str(x["period"]) for x in result["adopted_timing_dependencies"]) + ". Any adopted distribution is conditional on the tagged capital-payment/upstream order, not proof of no intra-year liquidity shortfall."
    result["status"] = "ECONOMIC_CONSTRAINTS_RETAINED" if any(x["affects"] for x in constraints) else ("CALCULATED_WITH_TIMING_DEPENDENCY" if result["adopted_timing_dependencies"] else "CALCULATED")
    return result


def diagnostic_config(base, diagnostic):
    c = copy.deepcopy(base)
    k, value = diagnostic["kind"], diagnostic["value"]
    if k == "core_tax_rate":
        c["units"][0]["tax_rate"] = value
    elif k == "park_buy":
        c["park_real_estate"]["base_choice"] = "buy" if value else "rent"
    elif k == "other_current_deposits":
        c["opening"]["other_current_deposits_assumption"] = value
    elif k == "current_bank_portion":
        c["opening"]["current_bank_portion_assumption"] = value
    else:
        raise TechnicalFailure("Unknown diagnostic " + k)
    c["active_path"]["name"] = diagnostic["name"]
    return c


def calculate_company(config):
    results = []
    cached_base_sim = None
    revision = config.get("capital_revision")
    selected = config["paths"] if revision is None else [next(p for p in config["paths"] if p["name"] == "base")]
    if revision is not None:
        selected = [{**selected[0], "name": name} for name in config["execution_plan"]["capital_profiles"]]
    for path in selected:
        try:
            c = configure_path(config, path)
            if revision is not None:
                c = configure_capital_choice(c, path["name"])
                sim = simulate(c)
                if path["name"] == "base":
                    cached_base_sim = sim
                results.append(evaluate_scenario(c, sim))
            else:
                results.append(evaluate_scenario(c))
        except Exception as exc:
            if not results:
                raise
            raise TechnicalFailure("Path technical failure after completed paths: " + str(exc), {"completed_paths": results, "failing_path": path["name"], "current_partial": getattr(exc, "partial", None)}) from exc
    base_path = next(p for p in config["paths"] if p["name"] == "base")
    base = configure_path(config, base_path)
    if revision is not None:
        base = configure_capital_choice(base, "base")
    diagnostics = []
    for d in ([] if revision is not None else config["diagnostics"]):
        try:
            diagnostics.append({"diagnostic": d, "result": evaluate_scenario(diagnostic_config(base, d))})
        except Exception as exc:
            raise TechnicalFailure("Diagnostic technical failure: " + str(exc), {"completed_paths": results, "completed_diagnostics": diagnostics, "failing_diagnostic": d, "current_partial": getattr(exc, "partial", None)}) from exc
    rate_results = []
    for rate in config["valuation"]["rate_sensitivities"]:
        c = copy.deepcopy(base)
        c["valuation"]["main_discount_rate"] = rate
        c["active_path"]["name"] = "base_discount_" + str(rate)
        try:
            rate_results.append(evaluate_scenario(c, cached_base_sim))
        except Exception as exc:
            raise TechnicalFailure("Rate diagnostic technical failure: " + str(exc), {"completed_paths": results, "completed_diagnostics": diagnostics, "completed_rate_diagnostics": rate_results, "current_partial": getattr(exc, "partial", None)}) from exc
    base_result = next(x for x in results if x["path"] == "base")
    range_members = rate_results if rate_results else [base_result]
    main_values = [x["main_method"]["value_per_share"] for x in range_members]
    terminal_values = [x["year5_value_per_share"] for x in range_members]
    value_range = None if any(x is None for x in main_values) else {"low": min(main_values), "high": max(main_values), "currency": "CNY"}
    interface = copy.deepcopy(base_result["return_model"])
    if interface is not None:
        if any(x is None for x in terminal_values):
            interface = None
        else:
            interface["base_case_terminal_equity_value_range_per_share"]["year_5"] = {"low": min(terminal_values), "high": max(terminal_values)}
            for member in range_members:
                for actual_d, base_d in zip(member["partial_distribution_schedule"], base_result["partial_distribution_schedule"]):
                    close(actual_d["raw_modeled_cash_per_share"], base_d["raw_modeled_cash_per_share"], "Discount-only range cannot alter base D")
    preview = {"value_range": value_range, "return_model": interface, "return_model_note": base_result["return_model_note"], "range_definition": "Same base operating/capital/payment state; only declared DCF discount endpoints change. Not mixed scenario min/max, not a submitted candidate."}
    return {"execution_plan": config.get("execution_plan", {"legacy_all_paths": True}), "incompatible_legacy_outputs_reused": False, "symbol": config["symbol"], "information_cutoff": config["cutoff"], "economic_date": config["economic_date"], "currency": "CNY", "internal_money_unit": "million", "paths": results, "diagnostics": diagnostics, "discount_rate_diagnostics": rate_results, "base_interface_preview": preview, "no_current_price_or_irr": True, "not_formal_research_registration": True}
