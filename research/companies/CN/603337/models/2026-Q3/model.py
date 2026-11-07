"""CN603337 source-derived static design. Ordinary offline local invocation.
All monetary values are CNY million; shares million. Standard library only.
"""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "jack_q3_static_v1"
ROOT = Path(__file__).resolve().parent
LIMIT_BYTES = 20 * 1024 * 1024


def time_coordinate(value: str) -> float:
    """Annual grid, calendar-month stub. Dec31 is exact fiscal end; not a monthly state model."""
    d = dt.date.fromisoformat(value)
    if d.month == 12 and d.day == 31:
        return float(d.year + 1)
    return d.year + (d.month - 1) / 12 + (d.day - 1) / 365.25


def discounted(value: float, rate: float, years: float) -> float:
    if rate <= -1 or years < -1e-9:
        raise ValueError("invalid discount rate or backward future flow")
    return value / ((1 + rate) ** max(0.0, years))


def validate(x: dict) -> None:
    if x.get("schema") != SCHEMA:
        raise ValueError("wrong schema")
    years = x["forecast_years"]
    if len(years) != 5 or years != list(range(years[0], years[0] + 5)):
        raise ValueError("exactly five consecutive forecast fiscal years required")
    if years[0] != dt.date.fromisoformat(x["q4_end"]).year + 1:
        raise ValueError("stub/fiscal boundary mismatch")
    if not 0 <= x["q4_elapsed_fraction"] <= 1:
        raise ValueError("invalid elapsed quarter fraction")
    if not x["balance_date"] < x["as_of"] <= x["q4_end"]:
        raise ValueError("valuation date must lie within the explicitly bridged quarter")
    if x["known_old_dividend"]["scheduled_payment_date"] > x["as_of"]:
        raise ValueError("this cutoff design requires the identified historical dividend date already passed")
    if not x["finance"]["ordinary_income_includes_net_finance_return"] or not x["finance"]["operating_dcf_excludes_finance_return"]:
        raise ValueError("financial-income and principal accounting convention mismatch")
    if not x["distribution"]["dates_are_research_assumptions"]:
        raise ValueError("future dividend dates are not company promises")
    b = x["balance"]
    if not 0 <= b["treasury_shares"] < b["registered_shares"]:
        raise ValueError("invalid shares")
    if not 0 < b["legacy_ordinary_ownership"] <= 1:
        raise ValueError("invalid ownership")
    if b["reserved_dilution_in_base"] > b["ungranted_reserved_shares"]:
        raise ValueError("dilution exceeds explicitly identified reserve")
    if x["known_old_dividend"]["future_holder_cash"] != 0:
        raise ValueError("past-record dividend cannot enter future holder D")
    p = x["parent_payment_budget"]
    if p["stop_appropriation_at_half_capital"]:
        raise ValueError("contradicts continuing observed reserve policy")
    tr = x["boke_transaction"]
    if abs(tr["initial_share"] + tr["remaining_share"] - 1) > 1e-9:
        raise ValueError("Boke ownership does not sum to one")
    if tr["assumed_close"] != x["q4_end"]:
        raise ValueError("this compact design requires the explicit fiscal-end initial close assumption")
    if tr["assumed_remaining_close"][-5:] != "12-31":
        raise ValueError("remaining-purchase timing must be explicit fiscal end")
    for name, unit in x["businesses"].items():
        for key, values in unit.items():
            if len(values) != 5:
                raise ValueError(f"{name}.{key} must have five values")
    for s in x["scenarios"]:
        for key in ("revenue_multipliers", "gross_margin_additions", "growth_capex_multipliers", "working_capital_additions", "upstream_cash_multipliers", "extra_parent_settlement"):
            if len(s[key]) != 5:
                raise ValueError("scenario horizon mismatch")
        for e in s["endpoints"]:
            if not e["discount_rate"] > e["terminal_growth"] >= 0:
                raise ValueError("terminal rate must exceed nonnegative growth")
            if not 0 <= e["financial_retention_haircut"] < 1:
                raise ValueError("invalid financial-claim adjustment")
    if x["fade"]["years"] != 5 or not x["fade"]["maintenance_equals_economic_da"] or not x["fade"]["no_special_dividend"] or x["fade"]["capital_recovery_release"] != 0:
        raise ValueError("five-year fade; no fabricated payout or capital recovery")


def bridge(x: dict) -> dict:
    b = x["balance"]
    gross = b["cash"] + b["trading_assets"] + b["current_deposits_total"] + b["other_noncurrent_total"] - b["other_noncurrent_nonfinancial_estimate"]
    debt = b["short_debt"] + b["long_debt"] + b["current_long_liabilities"] + b["leases"]
    # Discounted intragroup bills are already within the bank debt; informational only.
    f = gross - b["restricted_cash"] - b["operating_cash_buffer"] - debt - b["minority_surplus_financial_claim_estimate"]
    dividend_payable_nonoperating = x["known_old_dividend"]["balance_payable_cash"]
    k_group = b["parent_equity"] + b["minority_equity"] + debt + dividend_payable_nonoperating + b["conditional_share_refund_liability_estimate"] - gross + b["restricted_cash"] + b["operating_cash_buffer"] - b["nonoperating_equity_investments_estimate"]
    k = (k_group - b["comelz_economic_capital_allocation"]) * b["legacy_ordinary_ownership"] + b["comelz_economic_capital_allocation"]
    shares = b["registered_shares"] - b["treasury_shares"] + b["reserved_dilution_in_base"]
    return {"gross_financial_assets": gross, "financial_principal_estimate": b["current_deposit_principal_estimate"] + b["long_deposit_principal_estimate"], "book_accrued_deposit_interest_estimate": b["current_deposits_total"] - b["current_deposit_principal_estimate"] + b["other_noncurrent_total"] - b["other_noncurrent_nonfinancial_estimate"] - b["long_deposit_principal_estimate"], "debt": debt, "declared_dividend_payable_reclassified_into_operating_capital": dividend_payable_nonoperating, "surplus_financial_ordinary_0930": f, "economic_operating_capital_group_0930": k_group, "economic_operating_capital_ordinary_0930": k, "shares": shares}


def unit_result(p: dict, ownership: float) -> dict:
    rev = p["revenue"]
    gross = rev * p["gross_margin"]
    selling = rev * p["selling"]
    admin = rev * p["administration"]
    rd = rev * p["research"]
    other = rev * p["other_operating"]
    ebit = gross - selling - admin - rd - other
    tax = max(0.0, ebit) * p["tax"]
    nopat = ebit - tax
    # Purchased-intangible amortization is disclosed separately; no unproven tax shield.
    gaap_nopat = nopat - p["ppa"]
    net_reinvestment = p["maintenance"] + p["growth_capex"] + p["working_capital"] - p["economic_da"]
    return {"revenue": rev, "revenue_ordinary_economic": rev * ownership, "research_ordinary_economic": rd * ownership, "gross_profit": gross, "selling": selling, "administration": admin, "research": rd, "other_operating": other, "economic_ebit_before_ppa": ebit, "ppa_amortization_estimate": p["ppa"], "gaap_ebit_estimate": ebit - p["ppa"], "normalized_cash_tax": tax, "nopat_ordinary": nopat * ownership, "gaap_operating_profit_after_tax_ordinary": gaap_nopat * ownership, "economic_da_ordinary": p["economic_da"] * ownership, "maintenance_ordinary": p["maintenance"] * ownership, "growth_capex_ordinary": p["growth_capex"] * ownership, "working_capital_ordinary": p["working_capital"] * ownership, "net_reinvestment_ordinary": net_reinvestment * ownership, "fcff_ordinary": (nopat - net_reinvestment) * ownership, "ownership": ownership}


def aggregate(units: dict) -> dict:
    keys = [k for k in next(iter(units.values())) if k != "ownership"]
    return {k: sum(u[k] for u in units.values()) for k in keys}


def transaction_amount(x: dict, year: int) -> float:
    t = x["boke_transaction"]
    return t["assumed_remaining_cost"] if t["purchase_remaining_in_base"] and year == int(t["assumed_remaining_close"][:4]) else 0.0


def annual_parameters(x: dict, name: str, index: int, s: dict) -> dict:
    p = {k: v[index] for k, v in x["businesses"][name].items()}
    p["revenue"] *= s["revenue_multipliers"][index]
    p["gross_margin"] += s["gross_margin_additions"][index]
    p["selling"] += s["selling_addition"]
    p["administration"] += s["administration_addition"]
    p["research"] = max(p["research"], s["research_floor"])
    p["other_operating"] += s["other_addition"]
    p["growth_capex"] *= s["growth_capex_multipliers"][index]
    if name == "legacy":
        p["working_capital"] += s["working_capital_additions"][index]
    return p


def operations_and_payments(x: dict, s: dict, b: dict) -> dict:
    own = x["balance"]["legacy_ordinary_ownership"]
    q_units = {name: unit_result(p, own if name == "legacy" else 1.0) for name, p in x["q4"].items()}
    q = aggregate(q_units)
    f0 = b["surplus_financial_ordinary_0930"]
    fin_rate = x["finance"]["net_aftertax_return_on_opening_surplus"]
    q_fin = f0 * fin_rate / 4
    d_old = x["known_old_dividend"]
    old_remaining = d_old["balance_payable_cash"] + d_old["baseline_additional_cash"]
    tr = x["boke_transaction"]
    initial_past = tr["assumed_close"] <= x["as_of"]
    old_past = d_old["scheduled_payment_date"] <= x["as_of"]
    elapsed = x["q4_elapsed_fraction"]
    f_asof = f0 + elapsed * (q["fcff_ordinary"] + q_fin) - (old_remaining if old_past else 0) - (tr["initial_cost"] if initial_past else 0)
    f = f0 + q["fcff_ordinary"] + q_fin - old_remaining - tr["initial_cost"]
    k = b["economic_operating_capital_ordinary_0930"] + q["net_reinvestment_ordinary"] + tr["initial_cost"]
    prev_profit = x["known_9m_parent_earnings"] + q["gaap_operating_profit_after_tax_ordinary"] + q_fin
    prev_interim = d_old["full_declared_cash"]
    pp = x["parent_payment_budget"]
    parent_cash = pp["opening_spendable_cash_estimate"]
    retained = pp["opening_retained_profit_conservative"]
    # Parent total surplus-reserve amount; statutory attribution follows group note/policy, not a standalone parent split.
    reserve = pp["opening_parent_statutory_reserve"]
    dist = x["distribution"]
    records = []
    all_payments = []
    for i, year in enumerate(x["forecast_years"]):
        bought = tr["purchase_remaining_in_base"] and year > int(tr["assumed_remaining_close"][:4])
        boke_own = 1.0 if bought else tr["initial_share"]
        units = {name: unit_result(annual_parameters(x, name, i, s), own if name == "legacy" else (boke_own if name == "boke" else 1.0)) for name in x["businesses"]}
        a = aggregate(units)
        fin_income = f * fin_rate
        ordinary_profit = a["gaap_operating_profit_after_tax_ordinary"] + fin_income
        parent_profit = ordinary_profit * pp["profit_share_of_group_ordinary_profit"]
        appropriation = max(0.0, parent_profit) * pp["statutory_appropriation_rate"]
        reserve += appropriation
        retained_before = retained + parent_profit - appropriation
        upstream = max(0.0, ordinary_profit) * pp["upstream_cash_share_of_group_ordinary_profit"] * s["upstream_cash_multipliers"][i]
        parent_cash_before = parent_cash + upstream + pp["standalone_cash_before_parent_capex"] - pp["parent_only_capex_cash_budget"] - s["extra_parent_settlement"][i]
        request_final = max(0.0, dist["full_fiscal_payout_ratio"] * max(0.0, prev_profit) - prev_interim)
        request_interim = dist["interim_ratio_of_fiscal_profit"] * max(0.0, ordinary_profit)
        capacity = max(0.0, min(retained_before, parent_cash_before - pp["minimum_cash"]))
        final_cash = min(request_final, capacity)
        interim_cash = min(request_interim, max(0.0, capacity - final_cash))
        paid = final_cash + interim_cash
        parent_cash = parent_cash_before - paid
        retained = retained_before - paid
        acquisition_cash = transaction_amount(x, year)
        f_open, k_open = f, k
        f = f + a["fcff_ordinary"] + fin_income - paid - acquisition_cash
        k = k + a["net_reinvestment_ordinary"] + acquisition_cash
        payments = [{"date": f"{year}-{dist['assumed_final_month_day']}", "type": "prior_fiscal_final", "cash": final_cash}, {"date": f"{year}-{dist['assumed_interim_month_day']}", "type": "current_fiscal_interim", "cash": interim_cash}]
        all_payments.extend(payments)
        records.append({"year": year, "units": units, **a, "economic_operating_margin": a["economic_ebit_before_ppa"] / a["revenue"] if a["revenue"] else 0, "ordinary_profit_estimate": ordinary_profit, "ordinary_net_margin": ordinary_profit / a["revenue"] if a["revenue"] else 0, "net_financial_income": fin_income, "capital_open": k_open, "capital_close": k, "roic_opening_economic_capital": a["nopat_ordinary"] / k_open if k_open else 0, "surplus_financial_open": f_open, "surplus_financial_close": f, "acquisition_cash": acquisition_cash, "parent_profit_budget": parent_profit, "parent_upstream_cash_budget": upstream, "parent_reserve_transfer": appropriation, "parent_reserve_close": reserve, "parent_retained_close": retained, "parent_cash_close": parent_cash, "parent_cash_shortfall_before_distribution": max(0.0, pp["minimum_cash"] - parent_cash_before), "requested_distribution": request_final + request_interim, "paid_distribution": paid, "payments": payments, "boke_ownership": boke_own})
        prev_profit, prev_interim = ordinary_profit, interim_cash
    return {"quarter": {"units": q_units, **q, "net_financial_income_estimate": q_fin}, "estimated_fy2026_ordinary_profit": x["known_9m_parent_earnings"] + q["gaap_operating_profit_after_tax_ordinary"] + q_fin, "financial_asof_estimate": f_asof, "financial_fy2026_close_estimate": f0 + q["fcff_ordinary"] + q_fin - old_remaining - tr["initial_cost"], "future_stub_operating_cash": (1 - elapsed) * q["fcff_ordinary"], "future_stub_initial_acquisition": 0.0 if initial_past else tr["initial_cost"], "future_stub_old_dividend": 0.0 if old_past else old_remaining, "quarter_elapsed_is_estimated_not_observed": True, "years": records, "payments": all_payments}


def fade_value(x: dict, last: dict, endpoint: dict) -> dict:
    f = x["fade"]
    count = f["years"]
    k = last["capital_close"]
    initial_roic = last["roic_opening_economic_capital"]
    # Fade may reduce returns; it may not manufacture recovery from a worse year5.
    terminal_roic_used = min(endpoint["terminal_roic"], initial_roic)
    da = last["economic_da_ordinary"]
    economic_revenue = last["revenue_ordinary_economic"]
    persistent_rd_ratio = last["research_ordinary_economic"] / economic_revenue if economic_revenue else 0.0
    rows = []
    pv = 0.0
    for j in range(1, count + 1):
        weight = j / count
        growth = f["first_growth"] * (1 - weight) + endpoint["terminal_growth"] * weight
        roic = initial_roic * (1 - weight) + terminal_roic_used * weight
        nopat = k * roic
        reinvestment = k * growth
        da *= 1 + growth
        economic_revenue *= 1 + growth
        wc = reinvestment * f["working_capital_share_of_net_reinvestment"]
        growth_capex = reinvestment - wc
        fcff = nopat - reinvestment
        rows.append({"year": last["year"] + j, "ordinary_economic_revenue": economic_revenue, "persistent_research_ratio": persistent_rd_ratio, "persistent_research_cost": economic_revenue * persistent_rd_ratio, "implied_economic_aftertax_margin": nopat / economic_revenue if economic_revenue else 0.0, "capital_open": k, "nopat": nopat, "roic": roic, "growth": growth, "economic_da": da, "maintenance": da, "growth_capex": growth_capex, "working_capital": wc, "net_reinvestment": reinvestment, "fcff": fcff, "capital_close": k + reinvestment})
        k += reinvestment
        pv += discounted(fcff, endpoint["discount_rate"], j)
    terminal_nopat = k * terminal_roic_used
    terminal_reinvestment = k * endpoint["terminal_growth"]
    terminal_cash = terminal_nopat - terminal_reinvestment
    terminal_value = terminal_cash / (endpoint["discount_rate"] - endpoint["terminal_growth"])
    pv += discounted(terminal_value, endpoint["discount_rate"], count)
    return {"rows": rows, "terminal_roic_used_no_automatic_recovery": terminal_roic_used, "terminal_capital": k, "terminal_nopat": terminal_nopat, "terminal_reinvestment": terminal_reinvestment, "terminal_fcff": terminal_cash, "terminal_value_at_fade_end": terminal_value, "operating_value_at_fiscal_year5_end": pv, "no_special_dividend_or_capital_release": True}


def claim_value(cash: float, haircut: float) -> float:
    return cash - max(0.0, cash) * haircut


def endpoint_value(x: dict, b: dict, path: dict, e: dict) -> dict:
    at = time_coordinate(x["as_of"])
    q_end = time_coordinate(x["q4_end"])
    rate = e["discount_rate"]
    stub_cash = path["future_stub_operating_cash"] - path["future_stub_initial_acquisition"] - path["future_stub_old_dividend"]
    operating_pv = discounted(stub_cash, rate, q_end - at)
    for row in path["years"]:
        operating_pv += discounted(row["fcff_ordinary"] - row["acquisition_cash"], rate, row["year"] + 1 - at)
    last = path["years"][-1]
    tail = fade_value(x, last, e)
    operating_pv += discounted(tail["operating_value_at_fiscal_year5_end"], rate, last["year"] + 1 - at)
    financial_claim = claim_value(path["financial_asof_estimate"], e["financial_retention_haircut"])
    raw_current = operating_pv + financial_claim
    d0 = dt.date.fromisoformat(x["as_of"])
    anniversary = d0.replace(year=d0.year + 5).isoformat()
    anniversary_t = time_coordinate(anniversary)
    fraction_last_year = min(1.0, max(0.0, anniversary_t - last["year"]))
    paid_before_anniversary = sum(p["cash"] for p in last["payments"] if p["date"] <= anniversary)
    acquisition_before_anniversary = last["acquisition_cash"] if x["boke_transaction"]["assumed_remaining_close"] <= anniversary else 0.0
    f_anniversary = last["surplus_financial_open"] + fraction_last_year * (last["fcff_ordinary"] + last["net_financial_income"]) - paid_before_anniversary - acquisition_before_anniversary
    remaining_last_cf = (1 - fraction_last_year) * last["fcff_ordinary"] - (last["acquisition_cash"] - acquisition_before_anniversary)
    op_anniversary = discounted(remaining_last_cf + tail["operating_value_at_fiscal_year5_end"], rate, last["year"] + 1 - anniversary_t)
    tv5_raw = op_anniversary + claim_value(f_anniversary, e["financial_retention_haircut"])
    ds = []
    previous_date = x["as_of"]
    for j in range(1, 6):
        end = d0.replace(year=d0.year + j).isoformat()
        cash = sum(p["cash"] for p in path["payments"] if previous_date < p["date"] <= end)
        ds.append({"anniversary": end, "cash_total": cash, "cash_per_share": cash / b["shares"]})
        previous_date = end
    realized_d_pv = sum(discounted(p["cash"], rate, time_coordinate(p["date"]) - at) for p in path["payments"] if x["as_of"] < p["date"] <= anniversary)
    holder_cash_and_residual_pv = realized_d_pv + discounted(tv5_raw, rate, anniversary_t - at)
    first_fade = tail["rows"][0]
    warnings = []
    for row in path["years"]:
        if row["parent_cash_shortfall_before_distribution"] > 0:
            warnings.append(f"parent liquidity budget shortfall in {row['year']}; dividends constrained, not assumed funded")
    if abs(first_fade["fcff"] - last["fcff_ordinary"]) > 0.40 * max(1.0, abs(last["fcff_ordinary"])):
        warnings.append("year5-to-fade FCFF change exceeds 40%; explain capital/margin transition before adoption")
    if abs(raw_current - holder_cash_and_residual_pv) > 0.20 * max(1.0, abs(raw_current)):
        warnings.append("cash retention/timing gap exceeds 20% of asset value; require explicit capital-allocation judgment, not automatic headline adoption")
    terminal_pv_now = discounted(tail["terminal_value_at_fade_end"], rate, last["year"] + 1 - at + x["fade"]["years"])
    return {"endpoint": e, "stub_net_future_cash": stub_cash, "post_fade_perpetuity_pv_now": terminal_pv_now, "year5_to_year6_fcff_delta": first_fade["fcff"] - last["fcff_ordinary"], "year5_to_year6_nopat_delta": first_fade["nopat"] - last["nopat_ordinary"], "current_operating_pv_after_future_acquisitions": operating_pv, "current_financial_claim": financial_claim, "current_equity_raw": raw_current, "current_equity_limited_liability": max(0.0, raw_current), "current_value_per_share": max(0.0, raw_current) / b["shares"], "fiscal_year5_end": f"{last['year']}-12-31", "true_five_year_anniversary": anniversary, "anniversary_last_fiscal_fraction": fraction_last_year, "financial_claim_balance_at_anniversary": f_anniversary, "operating_value_at_anniversary": op_anniversary, "tv5_per_share": max(0.0, tv5_raw) / b["shares"], "annual_holder_distributions": ds, "pv_of_actual_assumed_payment_dates_and_tv5": holder_cash_and_residual_pv, "cash_retention_timing_gap_vs_operating_asset_value": raw_current - holder_cash_and_residual_pv, "fade": tail, "warnings": warnings}


def independent_crosscheck(x: dict, b: dict, path: dict) -> dict:
    c = x["independent_crosscheck"]
    sales = c["industrial_units"] * c["industrial_asp_cny"] / 1_000_000 + c["cutting_units"] * c["cutting_asp_cny"] / 1_000_000 + c["special_machines_revenue"] + c["other_revenue"]
    margin = c["legacy_gross_margin"] - c["legacy_selling"] - c["legacy_administration"] - c["legacy_research"] - c["legacy_other"]
    ebit = sales * margin
    nopat = ebit - max(0.0, ebit) * c["legacy_tax"]
    legacy_owner = (nopat + c["legacy_economic_da"] - c["legacy_maintenance"] - c["legacy_steady_working_capital_investment"]) * x["balance"]["legacy_ordinary_ownership"]
    tr = x["boke_transaction"]
    existing_owner = legacy_owner + c["comelz_normalized_owner_earnings"] + c["boke_normalized_owner_earnings_100pct"] * tr["initial_share"]
    at = time_coordinate(x["as_of"])
    bridge_rate = c["bridge_discount_rate"]
    known_initial_cost_pv = discounted(path["future_stub_initial_acquisition"], bridge_rate, time_coordinate(x["q4_end"]) - at)
    old_remaining_pv = discounted(path["future_stub_old_dividend"], bridge_rate, time_coordinate(x["q4_end"]) - at)
    project_reserve_pv = discounted(c["remaining_growth_projects_cash_reserve"], bridge_rate, c["project_reserve_years"])
    outputs = []
    for label, yield_rate in (("low", c["owner_earnings_yield_low_value"]), ("high", c["owner_earnings_yield_high_value"])):
        if yield_rate <= 0:
            raise ValueError("crosscheck capitalization yield must be positive")
        incremental_30pct_pv = 0.0
        if tr["purchase_remaining_in_base"]:
            incremental_30pct_pv = discounted(c["boke_normalized_owner_earnings_100pct"] * tr["remaining_share"] / yield_rate - tr["assumed_remaining_cost"], bridge_rate, time_coordinate(tr["assumed_remaining_close"]) - at)
        business_value = existing_owner / yield_rate + incremental_30pct_pv - known_initial_cost_pv - old_remaining_pv - project_reserve_pv
        equity = business_value + claim_value(path["financial_asof_estimate"], c["financial_retention_haircut"])
        outputs.append({"name": label, "owner_earnings_yield": yield_rate, "existing_owner_earnings": existing_owner, "incremental_remaining_30pct_value_pv": incremental_30pct_pv, "project_cash_reserve_pv": project_reserve_pv, "business_value": business_value, "equity_raw": equity, "value_per_share": max(0.0, equity) / b["shares"]})
    return {"independent_unit_based_legacy_sales": sales, "independent_legacy_ebit": ebit, "independent_legacy_owner_earnings": legacy_owner, "source_capital_coverage_owner_yield": existing_owner / b["economic_operating_capital_ordinary_0930"] if b["economic_operating_capital_ordinary_0930"] else None, "outputs": outputs, "not_derived_from_main_dcf_or_year5_earnings": True}


def evaluate(x: dict, include_crosscheck: bool = True) -> dict:
    validate(x)
    b = bridge(x)
    scenarios = []
    for s in x["scenarios"]:
        path = operations_and_payments(x, s, b)
        scenarios.append({"name": s["name"], "path": path, "valuations": [endpoint_value(x, b, path, e) for e in s["endpoints"]]})
    out = {"schema": SCHEMA, "as_of": x["as_of"], "balance_date": x["balance_date"], "timing_convention": "annual fiscal cash at Dec31; month-weighted stubs; dated distributions separate; no actual October measurement", "bridge": b, "scenarios": scenarios}
    if include_crosscheck:
        out["independent_crosscheck"] = independent_crosscheck(x, b, scenarios[0]["path"])
        main_values = [v["current_value_per_share"] for v in scenarios[0]["valuations"]]
        cross_values = [v["value_per_share"] for v in out["independent_crosscheck"]["outputs"]]
        main_middle = sum(main_values) / len(main_values)
        cross_middle = sum(cross_values) / len(cross_values)
        out["method_comparison_not_averaged"] = {"main_midpoint_for_diagnostic_only": main_middle, "crosscheck_midpoint_for_diagnostic_only": cross_middle, "fractional_difference": abs(cross_middle - main_middle) / max(1e-9, abs(main_middle)), "require_explanation_if_over_25pct": abs(cross_middle - main_middle) > 0.25 * max(1e-9, abs(main_middle))}
    assert_finite(out)
    return out


def assert_finite(value) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite financial result")
    if isinstance(value, dict):
        for v in value.values():
            assert_finite(v)
    if isinstance(value, list):
        for v in value:
            assert_finite(v)


def sensitivity_input(x: dict, spec: dict) -> dict:
    z = copy.deepcopy(x)
    z["scenarios"] = [z["scenarios"][0]]
    a, kind = spec["amount"], spec["kind"]
    if kind == "research_add":
        for u in z["businesses"].values():
            u["research"] = [v + a for v in u["research"]]
    elif kind == "maintenance_add":
        z["businesses"]["legacy"]["maintenance"] = [v + a for v in z["businesses"]["legacy"]["maintenance"]]
    elif kind == "old_dividend_extra":
        z["known_old_dividend"]["baseline_additional_cash"] = a
    elif kind == "remaining_cost":
        z["boke_transaction"]["assumed_remaining_cost"] = a
    elif kind == "no_remaining_purchase":
        z["boke_transaction"]["purchase_remaining_in_base"] = False
    elif kind == "reserved_shares":
        z["balance"]["reserved_dilution_in_base"] = a
    elif kind == "parent_stress":
        z["scenarios"][0]["upstream_cash_multipliers"] = [0,0,1,1,1]
        z["scenarios"][0]["extra_parent_settlement"] = [a,0,0,0,0]
    elif kind == "finance_return":
        z["finance"]["net_aftertax_return_on_opening_surplus"] = a
    elif kind == "nonfinancial_assets":
        z["balance"]["other_noncurrent_nonfinancial_estimate"] = a
    elif kind == "terminal_roic_reduction":
        for e in z["scenarios"][0]["endpoints"]:
            e["terminal_roic"] = max(0.0, e["terminal_roic"] - a)
    elif kind == "comelz_profit_scale":
        u = z["businesses"]["comelz"]
        for i in range(5):
            expense = u["selling"][i] + u["administration"][i] + u["research"][i] + u["other_operating"][i]
            u["gross_margin"][i] = expense + (u["gross_margin"][i] - expense) * a
    else:
        raise ValueError("unknown sensitivity")
    return z
