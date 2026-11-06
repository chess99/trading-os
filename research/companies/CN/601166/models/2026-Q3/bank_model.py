"""Industrial Bank source-bound model. No top-level model execution.

Amounts CNY million, shares million, per-share outputs CNY.
All financial arithmetic is deferred until explicitly authorized execution.
"""
from copy import deepcopy
from datetime import date
from math import isclose


class EconomicInfeasible(Exception):
    """A bounded economic path failed, distinct from a programming error."""


def interpolate(x, knots):
    if x <= knots[0][0]:
        return knots[0][1]
    for (xa, ya), (xb, yb) in zip(knots, knots[1:]):
        if x <= xb:
            return ya + (yb - ya) * (x - xa) / (xb - xa)
    return knots[-1][1]


def next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def statutory_transfer(shares, statutory, profit):
    return min(max(0.0, 0.5 * shares - statutory), 0.1 * max(0.0, profit))


def annual_statutory_adjustment(start_statutory, budgeted_transfer, annual_profit, shares):
    desired = min(max(0.0, .5 * shares - start_statutory), .1 * max(0.0, annual_profit))
    return {"desired_annual_budget": desired, "adjustment_to_statutory": desired - budgeted_transfer,
            "adjustment_to_RE": budgeted_transfer - desired, "common_B_change": 0.0, "cash_change": 0.0}


def legal_capacity(prior_parent_profit, ordinary_paid, preferred_paid,
                   perpetual_paid, include_perpetual=False):
    return prior_parent_profit - ordinary_paid - preferred_paid - (
        perpetual_paid if include_perpetual else 0.0)


def distribution_capacity(request, re_available, calendar_capacity,
                          capital_capacity, cash_capacity):
    limits = {"RE": re_available, "calendar_principle": calendar_capacity,
              "capital": capital_capacity, "cash": cash_capacity}
    # A negative annual-principle room alone need not mean insolvency: pay zero.
    if min(re_available, capital_capacity, cash_capacity) < -1e-6:
        raise EconomicInfeasible("pre_distribution_constraint:" + str(limits))
    payment = max(0.0, min(request, *limits.values()))
    return payment, {"limits": limits,
                     "binding": [k for k, v in limits.items() if v < request - 1e-6]}


def credit_bridge(begin, target, charge, recovery_fraction):
    # No invented negative net charge-offs; at least half the charge covers
    # current loss realization while a higher allowance target is built.
    end = begin + min(target - begin, 0.5 * max(charge, 0.0))
    net_writeoff = charge - (end - begin)
    if net_writeoff < -1e-6:
        raise EconomicInfeasible("negative_net_writeoff")
    gross_writeoff = net_writeoff / (1.0 - recovery_fraction)
    recovery = gross_writeoff * recovery_fraction
    return {"end": end, "net_writeoff": net_writeoff,
            "gross_writeoff": gross_writeoff, "recovery": recovery,
            "target_shortfall": max(0.0, target - end)}


def convert_equity(book, shares, liability, face, price, original_option_equity):
    if price <= 0:
        raise EconomicInfeasible("nonpositive_conversion_price")
    return {"book": book + liability, "shares": shares + face / price,
            "liability": 0.0, "cash": 0.0,
            "option_reclassified_within_common": original_option_equity}


def redemption(face, liability, refinance):
    payment = 1.09 * face  # final 3% coupon is already included
    if abs(liability - payment) > 0.01:
        raise ArithmeticError("convertible amortized-cost redemption mismatch")
    return {"payment": payment, "refinancing": refinance,
            "cash_change": refinance - payment, "equity_change": 0.0,
            "final_coupon_paid_separately": 0.0}


def holder_windows(events):
    result = [0.0] * 5
    used = set()
    for ev in events:
        dt = date.fromisoformat(ev["date"])
        matches = [i for i in range(5)
                   if date(2026 + i, 11, 1) <= dt <= date(2027 + i, 10, 31)]
        if len(matches) > 1:
            raise ArithmeticError("overlapping holder windows")
        if matches:
            if ev["id"] in used:
                raise ArithmeticError("duplicate dividend event")
            used.add(ev["id"])
            result[matches[0]] += ev["per_share"]
    return result


def value_path(initial_bps, rows, terminal_ps, ke, periods_per_year=12):
    """Formal valuation chain; handcases use this very function.

    Per-share clean surplus includes dilution/equity transfer, not merely EPS.
    DDM is an algebraic audit, not the independent auxiliary valuation.
    """
    rate = (1.0 + ke) ** (1.0 / periods_per_year) - 1.0
    ri_pv = 0.0
    dividend_pv = 0.0
    previous = initial_bps
    for t, row in enumerate(rows, 1):
        if not isclose(row["bps_start"], previous, abs_tol=1e-8):
            raise ArithmeticError("broken per-share opening bridge")
        economic_earnings = row["bps_end"] - previous + row["dps"]
        ri_pv += (economic_earnings - rate * previous) / (1 + rate) ** t
        dividend_pv += row["dps"] / (1 + rate) ** t
        previous = row["bps_end"]
    discount = (1 + rate) ** len(rows)
    value = initial_bps + ri_pv + (terminal_ps - previous) / discount
    ddm = dividend_pv + terminal_ps / discount
    if not isclose(value, ddm, rel_tol=1e-9, abs_tol=1e-8):
        raise ArithmeticError("RI/DDM cash-equity mismatch")
    return {"value": value, "book_anchor": initial_bps,
            "residual_income_pv": ri_pv, "ddm_check": ddm,
            "terminal_pv": terminal_ps / discount,
            "terminal_pv_fraction": None if value == 0 else terminal_ps / discount / value}


def cb_monthly_rate(book, face):
    # Sept-2026 opening: Dec-2026 coupon in month 3, final cash in month 15.
    lo, hi = -0.01, 0.03
    for _ in range(80):
        mid = (lo + hi) / 2
        pv = face * .023 / (1 + mid) ** 3 + face * 1.09 / (1 + mid) ** 15
        if pv > book:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def raw_nii(source, loan_shift=0.0, investment_shift=0.0,
            deposit_shift=0.0, wholesale_shift=0.0):
    ar = list(source["asset_rates"])
    for j in (0, 1, 2):
        ar[j] += loan_shift
    ar[3] += investment_shift
    lr = list(source["liability_rates"])
    lr[0] += deposit_shift
    lr[1] += wholesale_shift
    return sum(a * r for a, r in zip(source["asset_balances"], ar)) - sum(
        a * r for a, r in zip(source["liability_balances"], lr))


def initial_state(config, diagnostic):
    q, p = config["source"], config["policy"]
    shares_integer = q["h1_exact_shares"] + q["q3_cumulative_conversion_shares"] - q["h1_cumulative_conversion_shares"]
    shares = shares_integer / 1_000_000
    parent_b = q["parent_equity"] - q["perpetual"]
    cb_book = q["cb_h1_book"] + q["cb_h1_accretion"] * 3 / 6 + diagnostic.get("cb_book_shift", 0.0)
    face = q["cb_face_cny"] / 1_000_000
    perp_paid = q["perpetual_paid_2026_h1"] + 20000 * .0224
    funding = sum(q["parent_funding_components"]) - cb_book
    out = {
        "year": 2026, "month": 9, "scale": 1.0, "fee_scale": 1.0, "expense_scale": 1.0,
        "bg": q["group_b"], "bp": parent_b, "re": q["parent_re"],
        "stat": q["statutory_rounded"] - .5, "arbitrary": q["arbitrary"],
        "general": q["general_reserve"], "shares": shares,
        "exact_start_shares": shares_integer, "cash": q["parent_cash"],
        "funding": funding, "initial_funding": funding, "refinancing": 0.0,
        "cb": cb_book, "cb_face": face, "cb_r": cb_monthly_rate(cb_book, face),
        "cb_price": q["cb_price"], "cb_option_equity": q["cb_equity"],
        "cb_status": "outstanding", "at1_new": 0.0, "t2_new": 0.0,
        "loan_allowance": q["loan_allowance"], "events": [], "plans": {},
        "fy_parent": {2025: q["parent_profit_fy25"], 2026: q["parent_profit_9m"]},
        "fy_common": {2026: q["group_parent_profit_9m"] - perp_paid},
        "h1_common": {2026: q["h1_common_profit"]},
        "fy_paid_common": {2026: q["ordinary_paid_2026"]},
        "fy_paid_preferred": {2026: 0.0}, "fy_paid_perpetual": {2026: perp_paid},
        "fy_statutory_budget": {2026: 0.0},
        "fy_statutory_start": {2026: q["statutory_rounded"] - .5},
        "fy_start_b": {2026: q["group_b"]},
        "group_reg_offset": q["group_cet1_gross"] - q["group_b"],
        "parent_reg_offset": q["parent_cet1_gross"] - parent_b,
    }
    out["starting_derivations"] = {
        "shares_integer": shares_integer,
        "statutory_source_interval": [q["statutory_rounded"] - .5, q["statutory_rounded"] + .5],
        "statutory_gap_upper_budget": max(0.0, .5 * shares - out["stat"]),
        "group_rwa_estimate": q["group_min_capital"] / .08,
        "group_rwa_rounding_interval": [(q["group_min_capital"] - .5) / .08, (q["group_min_capital"] + .5) / .08],
        "parent_rwa_estimate": q["parent_min_capital"] / .08,
        "parent_rwa_rounding_interval": [(q["parent_min_capital"] - .5) / .08, (q["parent_min_capital"] + .5) / .08],
        "fy25_loan_credit_cost": q["fy25_loan_charge"] / q["fy25_avg_loans"],
        "h1_loan_credit_cost_365_181": q["h1_loan_charge"] / q["h1_avg_loans"] * q["year_days"] / q["h1_days"],
        "cb_q3_estimated_book_not_disclosed": cb_book,
        "cb_q3_book_estimation_formula": "H126 book + H126 accretion/6*3 + explicit diagnostic",
        "RE_already_contains_9m_profit": True,
        "parent_loan_gross_proxy": q["group_loans"] * q["parent_net_loans"] / q["group_net_loans"],
        "general_risk_asset_proxy_not_RWA": q["general_reserve"] / p["general_rate"],
    }
    return out


def operating_parameters(scenario, year, month, diagnostic):
    t = year + (month - 1) / 12
    transition = interpolate(t, [(2031, 0.0), (2035, 1.0)])
    growth = (1 - transition) * scenario["growth_near"] + transition * scenario["growth_terminal"]
    cc = interpolate(t, [(2027, scenario["cc_2027"]), (2029, scenario["cc_2029"]), (2031, scenario["cc_2031"])])
    cc += diagnostic.get("cc_add", 0.0)
    if diagnostic.get("cycle_cc") and 2027 <= year <= 2029:
        cc += .0025
    return {
        "growth": growth, "terminal_weight": transition,
        "loan_shift": interpolate(t, [(2026.75, 0.0), (2027, scenario["loan_shift_2027"]), (2029, scenario["loan_shift_2029"])]),
        "invest_shift": interpolate(t, [(2026.75, 0.0), (2027, scenario["invest_shift_2027"]), (2029, scenario["invest_shift_2029"])]),
        "deposit_shift": interpolate(t, [(2026.75, 0.0), (2027, scenario["deposit_shift_2027"]), (2029, scenario["deposit_shift_2029"])]),
        "wholesale_shift": scenario["wholesale_shift"], "cc": cc,
        "fee_growth": (1 - transition) * scenario["fee_growth"] + transition * scenario["growth_terminal"],
        "expense_growth": (1 - transition) * scenario["expense_growth"] + transition * scenario["growth_terminal"],
    }


def capital_state(state, config, scenario):
    q, p = config["source"], config["policy"]
    scale = state["scale"]
    rg = q["group_min_capital"] / .08 * scale
    rp = q["parent_min_capital"] / .08 * scale
    cg = state["bg"] + state["group_reg_offset"] - q["group_deduction"] * scale
    cp = state["bp"] + state["parent_reg_offset"] - q["parent_deduction"] * scale
    ag = q["group_at1"] + state["at1_new"]
    ap = q["parent_at1"] + state["at1_new"]
    tg = q["group_t2"] + state["t2_new"]
    tp = q["parent_t2"] + state["t2_new"]
    add = scenario["capital_buffer_add"] if state["year"] >= 2027 else 0.0
    limits = {
        "group_CET1": cg - (p["group_cet1_floor"] + add) * rg,
        "parent_CET1": cp - (p["parent_cet1_floor"] + add) * rp,
        "group_Tier1": cg + ag - p["tier1_floor"] * rg,
        "parent_Tier1": cp + ap - p["tier1_floor"] * rp,
        "group_total": cg + ag + tg - p["total_capital_floor"] * rg,
        "parent_total": cp + ap + tp - p["total_capital_floor"] * rp,
    }
    return {"rwa_group": rg, "rwa_parent": rp, "cet1_group": cg,
            "cet1_parent": cp, "cet1_ratio_group": cg / rg,
            "cet1_ratio_parent": cp / rp, "group_deductions": q["group_deduction"] * scale,
            "parent_deductions": q["parent_deduction"] * scale,
            "group_gross_to_B_offset": state["group_reg_offset"],
            "parent_gross_to_B_offset": state["parent_reg_offset"],
            "tier1_ratio_group": (cg + ag) / rg, "tier1_ratio_parent": (cp + ap) / rp,
            "total_ratio_group": (cg + ag + tg) / rg,
            "total_ratio_parent": (cp + ap + tp) / rp,
            "headrooms": limits, "common_distribution_capacity": min(limits.values())}


def perpetual_cash(state, config, year, month):
    p, q = config["policy"], config["source"]
    amount = state["at1_new"] * p["new_at1_rate"] / 12
    for tr in q["perpetual_tranches"]:
        if month == tr["month"]:
            coupon = tr["coupon"] if year < tr["reset_year"] else p["perpetual_reset_rate"]
            amount += tr["principal"] * coupon
    return amount


def step_once(previous, config, scenario, diagnostic, growth_fraction=1.0,
              override_growth=None, override_dividend=None, terminal_annual_dividend=None):
    q, p = config["source"], config["policy"]
    st = deepcopy(previous)
    year, month = next_month(st["year"], st["month"])
    st["year"], st["month"] = year, month
    if month == 1:
        st["fy_start_b"][year] = st["bg"]
        st["fy_statutory_start"][year] = st["stat"]
    op = operating_parameters(scenario, year, month, diagnostic)
    ga = op["growth"] if override_growth is None else override_growth
    gm = ((1 + ga) ** (1 / 12) - 1) * growth_fraction
    scale0 = st["scale"]
    st["scale"] *= 1 + gm
    avg_scale = (scale0 + st["scale"]) / 2
    st["fee_scale"] *= (1 + op["fee_growth"]) ** (1 / 12)
    st["expense_scale"] *= (1 + op["expense_growth"]) ** (1 / 12)
    # AT1 and Tier2 are external financing, never common equity/CET1.
    rp = q["parent_min_capital"] / .08 * st["scale"]
    at1_issue = max(0.0, p["at1_rwa_target"] * rp - q["parent_at1"] - st["at1_new"])
    t2_issue = max(0.0, p["t2_rwa_target"] * rp - q["parent_t2"] - st["t2_new"])
    st["at1_new"] += at1_issue
    st["t2_new"] += t2_issue
    perp = perpetual_cash(st, config, year, month)
    cb_expense = st["cb"] * st["cb_r"] if st["cb_status"] == "outstanding" else 0.0
    st["cb"] += cb_expense
    coupon_cash = 0.0
    if (year, month) == (2026, 12) and st["cb_status"] == "outstanding":
        coupon_cash = st["cb_face"] * .023
        st["cb"] -= coupon_cash
    # Remove reference convertible interest once, then insert actual schedule.
    reference_cb_annual = q["cb_h1_accretion"] * 2
    correction = q["nii_9m"] * 4 / 3 - raw_nii(q) + reference_cb_annual
    raw = raw_nii(q, op["loan_shift"], op["invest_shift"], op["deposit_shift"], op["wholesale_shift"])
    gross_nii = (raw + correction) * avg_scale / 12
    margin_shock = diagnostic.get("nii_margin_add", 0.0) * sum(q["asset_balances"]) * avg_scale / 12
    # Existing funding is already in raw NII; only deviation from scaled base
    # plus separate replacement CB/T2 financing incurs incremental charge.
    funding_deviation = previous["funding"] - previous["initial_funding"] * scale0
    funding_cost = (funding_deviation * (q["liability_rates"][1] + op["wholesale_shift"]) +
                    previous["refinancing"] * scenario["refinance_rate"] +
                    previous["t2_new"] * p["new_t2_rate"]) / 12
    nii = gross_nii + margin_shock - cb_expense - funding_cost
    parent_ratio_nii = q["parent_nii_9m"] / q["nii_9m"]
    parent_correction = reference_cb_annual * (1 - parent_ratio_nii) * avg_scale / 12
    nii_p = (gross_nii + margin_shock) * parent_ratio_nii + parent_correction - cb_expense - funding_cost
    fee = q["fee_9m"] * 4 / 3 * st["fee_scale"] / 12
    trade = q["fy25_trade"] * avg_scale / 12
    other = (q["fy25_revenue"] - q["fy25_nii"] - q["fy25_fee"] - q["fy25_trade"]) * avg_scale / 12
    expense = q["fy25_revenue"] * q["fy25_cost_income"] * st["expense_scale"] * p["month_expense_weights"][month - 1]
    taxes_other = 1705 * 4 / 3 * avg_scale / 12
    loan_charge = q["group_loans"] * avg_scale * op["cc"] / 12
    nonloan_charge = (sum(q["asset_balances"][3:])) * avg_scale * p["nonloan_credit_cost"] / 12
    pretax = nii + fee + trade + other - expense - taxes_other - loan_charge - nonloan_charge
    ni_total = pretax - max(pretax, 0.0) * p["group_tax"]
    ni_group = ni_total * q["group_parent_profit_9m"] / q["group_net_profit_9m"]
    fee_p = fee * q["parent_fee_9m"] / q["fee_9m"]
    trade_p = trade * sum(q["parent_trade_9m_components"]) / q["trade_9m"]
    expense_p = expense * q["parent_expense_9m"] / q["expense_9m"]
    credit_ratio = q["parent_credit_9m"] / q["credit_9m"]
    pretax_p = nii_p + fee_p + trade_p + other * .15 - expense_p - taxes_other * 1459 / 1705 - (loan_charge + nonloan_charge) * credit_ratio
    ni_parent = pretax_p - max(pretax_p, 0.0) * p["parent_tax"]
    common_group = ni_group - perp
    # Modest additional future upstreaming is bounded by subsidiary earnings,
    # recognized and paid once; consolidated profit is unchanged.
    common_parent_before = ni_parent - perp
    if terminal_annual_dividend is not None:
        need_upstream = max(0.0, scenario["growth_terminal"] * previous["bp"] / 12 + terminal_annual_dividend / 12 - common_parent_before)
        upstream_weight = 1.0
    else:
        far_policy = (1 - op["terminal_weight"]) * p["payout"] + op["terminal_weight"] * max(
            0.0, 1 - scenario["growth_terminal"] * previous["bg"] / max(common_group * 12, 1.0))
        need_upstream = max(0.0, ga * previous["bp"] / 12 + max(common_group, 0.0) * far_policy - common_parent_before)
        upstream_weight = op["terminal_weight"]
    upstream_cap = p["sub_remit_fraction_max"] * max(0.0, ni_group - ni_parent)
    upstream = min(need_upstream, upstream_cap) * upstream_weight
    ni_parent += upstream
    common_parent = ni_parent - perp
    # Common accounting equity, parent legal RE, and regulatory capital separate.
    st["bg"] += common_group
    st["bp"] += common_parent
    st["re"] += common_parent
    # Annual cumulative cap, not a second 10% charge on each profitable month
    # that would ignore losses elsewhere in the same calendar year.
    available_stat_profit = max(0.0, st["fy_parent"].get(year, 0.0) + ni_parent
        - 10 * st["fy_statutory_budget"].get(year, 0.0))
    stat_move = statutory_transfer(st["shares"], st["stat"], available_stat_profit)
    st["stat"] += stat_move
    general_target = q["general_reserve"] * st["scale"] * diagnostic.get("general_proxy_multiplier", 1.0)
    general_move = max(0.0, general_target - st["general"])
    st["general"] += general_move
    st["re"] -= stat_move + general_move
    bridge = credit_bridge(previous["loan_allowance"], q["group_loans"] * st["scale"] * scenario["allowance_ratio"], loan_charge, p["recovery_fraction"])
    st["loan_allowance"] = bridge["end"]
    parent_loan_ratio = q["parent_net_loans"] / q["group_net_loans"]
    delta_parent_loans = q["group_loans"] * parent_loan_ratio * (st["scale"] - scale0)
    parent_other_assets = q["parent_assets"] - q["parent_cash"] - q["parent_net_loans"]
    delta_other_assets = parent_other_assets * (st["scale"] - scale0)
    deposit_inflow = q["parent_deposits"] * (st["scale"] - scale0)
    # Accrual-to-cash adjustment for CB interest; ordinary funding interest is
    # assumed paid within the month. Loan principal loss uses NET charge-off.
    cash_operating = ni_parent + (loan_charge + nonloan_charge) * credit_ratio + cb_expense - coupon_cash
    loan_loss_cash = bridge["net_writeoff"] * credit_ratio
    nonloan_loss_cash = nonloan_charge * credit_ratio
    cash_before_dividend_and_funding = (previous["cash"] + deposit_inflow + cash_operating
        - delta_parent_loans - delta_other_assets - loan_loss_cash - nonloan_loss_cash
        - perp + at1_issue + t2_issue)
    cb_payment = cb_refinance = conversion_book = 0.0
    if (year, month) == (2027, 12) and st["cb_status"] == "outstanding":
        rd = redemption(st["cb_face"], st["cb"], 1.09 * st["cb_face"])
        cb_payment, cb_refinance = rd["payment"], rd["refinancing"]
        cash_before_dividend_and_funding += rd["cash_change"]
        st["refinancing"] += cb_refinance
        st["cb"] = 0.0
        st["cb_status"] = "redeemed"
        # Option equity remains inside total common B; internal relabel only.
        st["cb_option_equity"] = 0.0
    source_year = year - 1
    request = 0.0
    if override_dividend is not None:
        request = override_dividend
    elif month in (2, 6) and source_year in st["plans"]:
        request = st["plans"][source_year]["interim" if month == 2 else "final"]
    st["fy_paid_perpetual"][year] = st["fy_paid_perpetual"].get(year, 0.0) + perp
    prior_ni = st["fy_parent"].get(year - 1)
    if prior_ni is None:
        raise ArithmeticError("missing prior calendar parent net profit")
    law_room = legal_capacity(prior_ni, st["fy_paid_common"].get(year, 0.0),
                             st["fy_paid_preferred"].get(year, 0.0),
                             st["fy_paid_perpetual"][year], diagnostic.get("perpetual_in_law", False))
    cap = capital_state(st, config, scenario)
    deposits_end = q["parent_deposits"] * st["scale"]
    cash_floor = p["cash_floor_ratio"] * deposits_end
    cash_target = p["cash_target_ratio"] * deposits_end
    funding_limit = p["annual_net_funding_capacity"] * diagnostic.get("funding_capacity_multiplier", 1.0) * q["parent_deposits"] * scale0 / 12
    div, constraints = distribution_capacity(request, st["re"], law_room,
        cap["common_distribution_capacity"], cash_before_dividend_and_funding + funding_limit - cash_floor)
    funding_needed = cash_target - (cash_before_dividend_and_funding - div)
    funding_net = max(-st["funding"], min(funding_limit, funding_needed))
    st["funding"] += funding_net
    st["cash"] = cash_before_dividend_and_funding + funding_net - div
    st["bg"] -= div
    st["bp"] -= div
    st["re"] -= div
    st["fy_paid_common"][year] = st["fy_paid_common"].get(year, 0.0) + div
    dps = div / previous["shares"]
    if div:
        st["events"].append({"id": f"ordinary-{year}-{month:02d}", "date": f"{year}-{month:02d}-28",
            "profit_year": source_year, "amount": div, "shares": previous["shares"], "per_share": dps})
        if st["cb_status"] == "outstanding":
            st["cb_price"] -= dps
    if (year, month) == (2027, 6) and diagnostic.get("conversion") and st["cb_status"] == "outstanding":
        conversion_book = st["cb"]
        conv = convert_equity(st["bg"], st["shares"], st["cb"], st["cb_face"], st["cb_price"], st["cb_option_equity"])
        st["bg"], st["shares"], st["cb"] = conv["book"], conv["shares"], conv["liability"]
        st["bp"] += conversion_book
        st["cb_status"] = "converted"
        st["cb_option_equity"] = 0.0
        # New par capital can create a legal-reserve gap. Transfer within RE,
        # bounded by this month's available profit; following months continue.
        extra_stat = statutory_transfer(st["shares"], st["stat"], max(0.0, available_stat_profit - 10 * stat_move))
        st["stat"] += extra_stat
        st["re"] -= extra_stat
        stat_move += extra_stat
    st["fy_statutory_budget"][year] = st["fy_statutory_budget"].get(year, 0.0) + stat_move
    st["fy_parent"][year] = st["fy_parent"].get(year, 0.0) + ni_parent
    st["fy_common"][year] = st["fy_common"].get(year, 0.0) + common_group
    if month <= 6:
        st["h1_common"][year] = st["h1_common"].get(year, 0.0) + common_group
    statutory_year_end_check = None
    if month == 12:
        statutory_year_end_check = annual_statutory_adjustment(st["fy_statutory_start"][year],
            st["fy_statutory_budget"][year], st["fy_parent"][year], st["shares"])
        adjustment = statutory_year_end_check["adjustment_to_statutory"]
        st["stat"] += adjustment
        st["re"] -= adjustment
        stat_move += adjustment
        st["fy_statutory_budget"][year] = statutory_year_end_check["desired_annual_budget"]
        profit = max(0.0, st["fy_common"][year])
        weight = op["terminal_weight"]
        sustainable = max(0.0, profit - scenario["growth_terminal"] * st["fy_start_b"][year])
        annual_budget = (1 - weight) * p["payout"] * profit + weight * sustainable
        interim = min(p["interim_share"] * annual_budget, max(0.0, st["h1_common"].get(year, 0.0)) / 3)
        st["plans"][year] = {"total": annual_budget, "interim": interim,
                             "final": annual_budget - interim,
                             "source_profit": profit, "h1_common": st["h1_common"].get(year, 0.0)}
    cap_after = capital_state(st, config, scenario)
    if min(cap_after["headrooms"].values()) < -1e-5 or st["cash"] < cash_floor - 1e-5 or st["re"] < -1e-5:
        raise EconomicInfeasible("post_distribution_constraint")
    if not isclose(st["bg"], previous["bg"] + common_group - div + conversion_book, abs_tol=1e-6):
        raise ArithmeticError("group equity conservation")
    if not isclose(st["bp"], previous["bp"] + common_parent - div + conversion_book, abs_tol=1e-6):
        raise ArithmeticError("parent equity conservation")
    if not isclose(st["re"], previous["re"] + common_parent - stat_move - general_move - div, abs_tol=1e-6):
        raise ArithmeticError("parent legal RE conservation")
    row = {
        "date": f"{year}-{month:02d}-28", "year": year, "month": month,
        "profit_year_for_payment": source_year if div else None,
        "scale": st["scale"], "actual_monthly_growth": gm,
        "requested_annual_growth": ga, "growth_fraction": growth_fraction,
        "operating_parameters": op, "nii": nii, "nii_parent": nii_p,
        "nii_definition_reconciliation_annual_at_scale_one": correction,
        "fee": fee, "trade": trade, "other_income": other, "expense": expense,
        "loan_charge": loan_charge, "credit_cost_denominator_avg_loans": q["group_loans"] * avg_scale,
        "nonloan_charge": nonloan_charge, "net_parent_profit_group": ni_group,
        "net_profit_parent": ni_parent, "common_earnings_group": common_group,
        "common_earnings_parent": common_parent, "sub_upstream_received_once": upstream,
        "sub_upstream_cap": upstream_cap, "sub_upstream_requested": need_upstream,
        "perpetual_cash": perp, "dividend_requested": request, "dividend": div, "dps": dps,
        "bps_start": previous["bg"] / previous["shares"], "bps_end": st["bg"] / st["shares"],
        "group_B_start": previous["bg"], "group_B_end": st["bg"],
        "parent_B_start": previous["bp"], "parent_B_end": st["bp"],
        "parent_RE_start": previous["re"], "parent_RE_end": st["re"],
        "statutory_transfer": stat_move, "statutory_end": st["stat"],
        "statutory_year_end_check": statutory_year_end_check,
        "arbitrary_end": st["arbitrary"], "general_transfer": general_move,
        "general_end": st["general"], "credit_bridge": bridge,
        "calendar_previous_parent_profit": prior_ni,
        "calendar_ordinary_paid_ytd": st["fy_paid_common"][year],
        "calendar_preferred_paid_ytd": st["fy_paid_preferred"].get(year, 0.0),
        "calendar_perpetual_paid_ytd": st["fy_paid_perpetual"][year],
        "calendar_principle_room_before_payment": law_room,
        "cash_start": previous["cash"], "deposit_net_inflow": deposit_inflow,
        "cash_operating_after_tax_before_principal": cash_operating,
        "loan_principal_net_increase": delta_parent_loans,
        "loan_net_chargeoff_cash": loan_loss_cash, "other_asset_principal_increase": delta_other_assets,
        "nonloan_loss_cash": nonloan_loss_cash, "at1_issue_cash": at1_issue,
        "tier2_issue_cash": t2_issue, "normal_funding_net_cash": funding_net,
        "normal_funding_cap": funding_limit, "normal_funding_end": st["funding"],
        "incremental_funding_cost": funding_cost, "cash_end": st["cash"],
        "cash_floor": cash_floor, "cash_target": cash_target,
        "cb_interest_expense": cb_expense, "cb_coupon_cash": coupon_cash,
        "cb_redemption_cash": cb_payment, "cb_refinance_cash": cb_refinance,
        "cb_converted_book": conversion_book, "cb_book_end": st["cb"],
        "cb_status": st["cb_status"], "cb_conversion_price": st["cb_price"],
        "cb_original_option_equity_not_added_again": q["cb_equity"],
        "shares_start": previous["shares"], "shares_end": st["shares"],
        "constraints": constraints, "capital": cap_after,
    }
    expected_cash = (row["cash_start"] + deposit_inflow + cash_operating - delta_parent_loans
        - delta_other_assets - loan_loss_cash - nonloan_loss_cash - perp + at1_issue + t2_issue
        + cb_refinance - cb_payment + funding_net - div)
    if not isclose(expected_cash, st["cash"], abs_tol=1e-6):
        raise ArithmeticError("parent cash conservation")
    return st, row


def step(previous, config, scenario, diagnostic, **kwargs):
    errors = []
    fractions = [1.0] if "override_growth" in kwargs else [1.0, .75, .5, .25, 0.0, -.25]
    for fraction in fractions:
        try:
            state, row = step_once(previous, config, scenario, diagnostic, fraction, **kwargs)
            row["growth_repair_attempts"] = errors
            return state, row
        except EconomicInfeasible as exc:
            errors.append({"growth_fraction": fraction, "reason": str(exc)})
    raise EconomicInfeasible("bounded_growth_and_distribution_repair_exhausted:" + str(errors))


def simulate(config, scenario_name="base", diagnostic=None, progress=None,
             stepper=None, initial_override=None, months=121):
    diagnostic = diagnostic or {}
    scenario = config["scenarios"][scenario_name]
    state = initial_state(config, diagnostic) if initial_override is None else deepcopy(initial_override)
    initial = deepcopy(state)
    rows = []
    asof = None
    stub = None
    completed = []
    auxiliary_anchor = None
    advance = step if stepper is None else stepper
    try:
        for i in range(months):
            state, row = advance(state, config, scenario, diagnostic)
            completed.append(row)
            if i == 0:
                asof, stub = deepcopy(state), row
            else:
                rows.append(row)
            if (state["year"], state["month"]) == (2027, 12):
                auxiliary_anchor = {"state": deepcopy(state), "row_count": len(rows)}
            if progress is not None:
                progress({"phase": "forecast", "last_complete_row": row,
                          "last_complete_state": state, "completed_months": len(completed)})
    except Exception as exc:
        if progress is not None:
            try:
                progress({"phase": "forecast_failure", "completed_rows_including_stub": completed,
                    "last_complete_state": state, "completed_months": len(completed),
                    "failed_month": list(next_month(state["year"], state["month"])),
                    "exception_type": type(exc).__name__, "exception": str(exc)})
            except Exception as recording_error:
                exc.add_note("Failure snapshot also failed: " + repr(recording_error))
        if not isinstance(exc, EconomicInfeasible):
            raise
        return {"status": "economic_infeasible", "reason": str(exc), "scenario": scenario_name,
                "diagnostic": diagnostic, "initial": initial, "asof": asof,
                "stub": stub, "rows": rows, "last_state": state,
                "auxiliary_anchor": auxiliary_anchor, "value_range": None, "return_model": None}
    return {"status": "forecast_ready", "scenario": scenario_name, "diagnostic": diagnostic,
            "initial": initial, "asof": asof, "stub": stub, "rows": rows,
            "last_state": state, "holder_D": holder_windows(state["events"]),
            "auxiliary_anchor": auxiliary_anchor}


def terminal_cycle(forecast, config, progress=None):
    from normalized import terminal_cycle as normalized_terminal_cycle
    return normalized_terminal_cycle(forecast, config, progress)


def terminal_value(cycle, ke):
    g = cycle["growth"]
    if ke <= g:
        raise EconomicInfeasible("discount_rate_not_above_growth")
    rm = (1 + ke) ** (1 / 12) - 1
    one_cycle_pv = sum(row["dps"] / (1 + rm) ** (i + 1) for i, row in enumerate(cycle["rows"]))
    return one_cycle_pv / (1 - (1 + g) / (1 + ke))


def price_forecast(forecast, cycle, config, ke):
    current = value_path(forecast["asof"]["bg"] / forecast["asof"]["shares"],
                         forecast["rows"], terminal_value(cycle, ke), ke)
    y5_bps = forecast["rows"][59]["bps_end"]
    year5 = value_path(y5_bps, forecast["rows"][60:], terminal_value(cycle, ke), ke)
    return {"ke": ke, "current": current, "year5": year5,
            "year5_state": forecast["rows"][59], "D": forecast["holder_D"]}


def auxiliary_normalized(config, forecast, ke, progress=None):
    from normalized import auxiliary_normalized as cash_backed_auxiliary
    return cash_backed_auxiliary(config, forecast, ke, progress)
