"""Standalone bank common-equity research model. Standard library only.
No network, repository, private source paths, market price or dynamic IRR.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import traceback
from pathlib import Path


MATURITY = dt.date(2028, 9, 14)
COUPON_2027 = dt.date(2027, 9, 15)


def years(a, b):
    return (b - a).days / 365.25


def rwa_interval(capital, ratio):
    """Ratios disclosed to 0.01 percentage point; not official exact RWA."""
    return capital / (ratio + 0.00005), capital / (ratio - 0.00005)


def intersect_rwa(cet, cet_ratio, total, total_ratio):
    a, b = rwa_interval(cet, cet_ratio), rwa_interval(total, total_ratio)
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    if lo > hi:
        raise ValueError("Inconsistent rounded capital ratios")
    return {"low": lo, "high": hi, "proxy_midpoint": (lo + hi) / 2}


def forward_rate(carry, date, flows):
    """Economic forward carrying-cost proxy, NOT disclosed accounting EIR."""
    lo, hi = -0.05, 0.30
    for _ in range(90):
        r = (lo + hi) / 2
        pv = sum(cash / (1 + r) ** years(date, day) for day, cash in flows)
        if pv > carry:
            lo = r
        else:
            hi = r
    return (lo + hi) / 2


def debt_step(balance, rate, begin, end, face, path, active):
    """Coupon dates and maturity explicit; no second deduction of principal."""
    if not active:
        return {"balance": 0.0, "expense": 0.0, "cash": 0.0,
                "conversion_liability": 0.0, "refinance_principal": 0.0,
                "active": False, "post_event_fraction": 0.0}
    stop = min(end, MATURITY)
    current, expense, cash = begin, 0.0, 0.0
    for day, amount in [(COUPON_2027, face * 0.013)]:
        if begin < day <= stop:
            charge = balance * ((1 + rate) ** years(current, day) - 1)
            expense += charge
            balance += charge - amount
            cash += amount
            current = day
    charge = balance * ((1 + rate) ** years(current, stop) - 1)
    expense += charge
    balance += charge
    converted, refinance, post = 0.0, 0.0, 0.0
    if begin < MATURITY <= end:
        post = years(MATURITY, end)
        if path == "convert":
            converted = balance
        else:
            redemption = face * 1.07  # includes final 1.8% coupon
            expense += redemption - balance
            cash += redemption
            refinance = redemption
        balance, active = 0.0, False
    return {"balance": balance, "expense": expense, "cash": cash,
            "conversion_liability": converted, "refinance_principal": refinance,
            "active": active, "post_event_fraction": post}


def equity_bridge(book, profit, cash, liability_transferred=0.0,
                  option_transferred=0.0, oci=0.0):
    return book + profit - cash + liability_transferred + option_transferred + oci


def capital_room(cet, at1, other_capital, rwa, p):
    return min(cet - p["working_cet1_floor"] * rwa,
               cet + at1 - p["working_tier1_floor"] * rwa,
               cet + other_capital - p["working_total_floor"] * rwa)


def present_value(initial_bps, rows, tv, ke):
    """Actual-holder DCF plus equivalent book-residual identity.
    Residual includes the separately disclosed per-share capital transfer;
    this identity is not a second independent business valuation method.
    """
    cash_pv, residual_pv, previous = 0.0, 0.0, initial_bps
    for row in rows:
        n = row["year"]
        d, closing = row["dps"], row["book_end"] / row["shares_end"]
        cash_pv += d / (1 + ke) ** n
        holder_residual = closing - previous + d - ke * previous
        residual_pv += holder_residual / (1 + ke) ** n
        previous = closing
    value = cash_pv + tv / (1 + ke) ** len(rows)
    ri_value = initial_bps + residual_pv + (tv - previous) / (1 + ke) ** len(rows)
    return {"value": value, "ri_identity": ri_value,
            "dividend_pv": cash_pv, "terminal_pv": tv / (1 + ke) ** len(rows)}


def initialize(data, asof, dividend_state):
    o, p = data["observed"], data["base"]
    financial = dt.date.fromisoformat(data["financial_date"])
    if not financial <= asof <= financial + dt.timedelta(days=92):
        raise ValueError("Cutoff outside bounded Q3-to-cutoff bridge")
    gr = intersect_rwa(o["group_cet1"], o["group_cet1_ratio"],
                       o["group_total_capital"], o["group_total_capital_ratio"])
    mr = intersect_rwa(o["mother_cet1"], o["mother_cet1_ratio"],
                       o["mother_total_capital"], o["mother_total_capital_ratio"])
    mother_book = o["h1_mother_equity"] + o["mother_cet1"] - o["h1_mother_cet1"]
    mother_retained = o["h1_mother_retained"] + o["mother_cet1"] - o["h1_mother_cet1"]
    # H1 disclosed amortization extrapolated only to Q3. Accrued coupon proxy
    # is separate. Future r solves remaining contractual cash from this proxy.
    h1 = dt.date(2026, 6, 30)
    carry = (o["h1_convertible_liability_ex_accrual"]
             + o["h1_convertible_amortization"] * (financial - h1).days / 181)
    carry *= o["convertible_face"] / o["h1_convertible_face"]
    carry += o["convertible_face"] * 0.013 * (financial - dt.date(2026, 9, 15)).days / 365.25
    r = forward_rate(carry, financial, [(COUPON_2027, o["convertible_face"] * 0.013),
                                       (MATURITY, o["convertible_face"] * 1.07)])
    earning = o["h1_average_earning_assets"] * o["total_assets"] / o["h1_group_assets"]
    # Annualized normalized short stub, not an invented disclosed Q4 result.
    dt_stub = years(financial, asof)
    gross = (earning * p["nim"][0] + p["fee_base"] + p["trading_base"]
             + p["other_recurring_base"])
    stub_ni = ((gross * (1 - p["cost_income_ratio"][0])
                - o["gross_loans"] * p["loan_credit_cost"][0]
                - p["other_credit_loss_base"] - p["tax_surcharge_base"])
               * (1 - p["effective_business_tax"])
               - 2 * (o["h1_village_total_profit"]
                      - o["village_direct_ownership"] * o["h1_village_parent_profit"])) * dt_stub
    village_attr = 2 * o["h1_village_parent_profit"] * o["village_direct_ownership"] * dt_stub
    paid = o["declared_interim_dps"] * o["shares"] if dividend_state == "paid" else 0.0
    state = {
        "book": o["parent_attributable_equity"] - o["convertible_equity"] + stub_ni - paid,
        "mother_book": mother_book - o["convertible_equity"] + stub_ni - village_attr - paid,
        "mother_retained": mother_retained + stub_ni - village_attr - paid,
        "cet": o["group_cet1"] + stub_ni - paid,
        "mother_cet": o["mother_cet1"] + stub_ni - village_attr - paid,
        "rwa": gr["proxy_midpoint"], "mother_rwa": mr["proxy_midpoint"],
        "core_earning_assets": earning, "loans": o["gross_loans"],
        "allowance": o["gross_loans"] * o["loan_allowance_ratio"],
        "shares": o["shares"], "option": o["convertible_equity"],
        "conversion_price": o["conversion_price"] - (o["declared_interim_dps"] if paid else 0),
        "debt_balance": carry * (1 + r) ** dt_stub, "debt_active": True,
        "noncash_capital_transfers": 0.0,
        "refinancing_principal": 0.0, "statutory": o["statutory_reserve"],
        "general": o["general_reserve"], "mother_assets": o["h1_mother_assets"],
        "village_assets": o["h1_village_assets"],
        "village_rwa": o["h1_village_rwa"],
        "village_cet": o["h1_village_cet1"]
    }
    state["operating_book_anchor"] = state["book"]
    state["mother_operating_anchor"] = state["mother_book"]
    return state, {"group_rwa_interval": gr, "mother_rwa_interval": mr,
                   "economic_debt_rate_proxy": r, "stub_profit": stub_ni,
                   "stub_village_attributable_profit": village_attr,
                   "interim_assumed_pre_cutoff_paid": paid,
                   "mother_q3_book_is_h1_deduction_bridge": True,
                   "q3_earning_assets_is_scale_proxy": True,
                   "village_capital_latest_h1_carried_forward_no_invented_q3": True}


def parameters(data, case, i):
    p, c = data["base"], data["cases"][case]
    early = i < 2
    growth = p["growth"][i] + c.get("growth_shift", 0) + (c.get("growth_shift_first_two", 0) if early else 0)
    growth = min(growth, c.get("growth_cap", growth))
    return {"growth": growth,
            "nim": p["nim"][i] + c.get("nim_shift", 0) + (c.get("nim_shift_first_two", 0) if early else 0),
            "cc": p["loan_credit_cost"][i] + c.get("credit_cost_shift", 0) + (c.get("credit_cost_shift_first_two", 0) if early else 0),
            "net_co": p["net_chargeoff_rate"][i] + (c.get("credit_cost_shift", 0) if case == "structural_weak" else 0) + (c.get("credit_cost_shift_first_two", 0) if early else 0),
            "cir": p["cost_income_ratio"][i] + c.get("cir_shift", 0)}


def evaluate_year(data, state, anchor, meta, case, i, begin, end, growth):
    o, p, c = data["observed"], data["base"], data["cases"][case]
    q = parameters(data, case, i)
    factor = 1 + growth
    debt = debt_step(state["debt_balance"], meta["economic_debt_rate_proxy"],
                     begin, end, o["convertible_face"], c["path"], state["debt_active"])
    funding = debt["expense"] + state["refinancing_principal"] * p["refinancing_rate"] * years(begin, end)
    funding += debt["refinance_principal"] * p["refinancing_rate"] * debt["post_event_fraction"]
    average_ea = state["core_earning_assets"] * (1 + factor) / 2
    average_loans = state["loans"] * (1 + factor) / 2
    required_begin = anchor["operating_book_anchor"] * state["rwa"] / anchor["rwa"]
    excess_begin = max(0.0, state["book"] - required_begin)
    # Incremental equity retained from earnings can replace normal funding.
    # Conversion/option reclassification brings NO cash and is excluded here.
    # If that event-created capital is later returned, normal funding must be
    # added; the signed adjustment then becomes a recurring financing cost.
    retained_funding_variance = state["book"] - required_begin - state["noncash_capital_transfers"]
    surplus_income = retained_funding_variance * p["surplus_after_tax_return"]
    fixed_funding_addback = 2 * o["h1_convertible_amortization"] + o["h1_convertible_face"] * 0.01
    nii_before_funding = average_ea * q["nim"] + fixed_funding_addback
    fee = p["fee_base"] * (1 + p["fee_growth"]) ** (i + 1)
    trading = p["trading_base"] * (1 + p["trading_growth"]) ** (i + 1)
    other = p["other_recurring_base"] * (1 + p["terminal_g"]) ** (i + 1)
    revenue = nii_before_funding + fee + trading + other
    costs = revenue * q["cir"]
    net_co = average_loans * q["net_co"]
    floor = state["loans"] * factor * p["allowance_floor_ratio"]
    provision = max(average_loans * q["cc"], net_co + floor - state["allowance"])
    allowance = state["allowance"] + provision - net_co
    other_loss = p["other_credit_loss_base"] * (state["rwa"] * factor / anchor["rwa"])
    surcharge = p["tax_surcharge_base"] * (state["rwa"] * factor / anchor["rwa"])
    pre_funding_profit = revenue - costs - provision - other_loss - surcharge
    # Subsidiary profits are a compact source-calibrated allocation, not a second
    # income stream. They are already inside group operations above.
    village_assets_end = state["village_assets"] * (1 + min(growth, p["village_growth"]))
    village_assets_proxy = (state["village_assets"] + village_assets_end) / 2
    village_shock = ((q["nim"] - p["nim"][i]) * 0.95
                     - (q["cc"] - p["loan_credit_cost"][i])
                     * o["h1_village_loans"] / o["h1_village_assets"]) * village_assets_proxy * (1 - p["effective_business_tax"])
    village_total = 2 * o["h1_village_total_profit"] * village_assets_proxy / o["h1_village_assets"] + village_shock
    attribution_fraction = o["village_direct_ownership"] * o["h1_village_parent_profit"] / o["h1_village_total_profit"]
    village_attr = village_total * attribution_fraction
    minority = village_total - village_attr
    group_profit = pre_funding_profit * (1 - p["effective_business_tax"]) - funding * (1 - p["funding_tax_shield"]) - minority + surplus_income
    village_rwa_end = state["village_rwa"] * (1 + min(growth, p["village_growth"]))
    # Only the holding-bank attributable portion is credited as fresh village
    # regulatory capital; no automatic recognition of all lower-tier minority.
    village_cet_pre = state["village_cet"] + village_attr / o["village_direct_ownership"]
    village_at1_proxy = o["h1_village_rwa"] * o["h1_village_tier1_ratio"] - o["h1_village_cet1"]
    village_other = o["h1_village_total_capital"] - o["h1_village_cet1"]
    village_room = min(village_cet_pre - p["village_working_floor"] * village_rwa_end,
                       village_cet_pre + village_at1_proxy - p["working_tier1_floor"] * village_rwa_end,
                       village_cet_pre + village_other - p["working_total_floor"] * village_rwa_end)
    upstream_blend = max(0.0, (i - 4) / 5)
    village_retention_need = max(0.0, village_rwa_end - state["village_rwa"]) * 0.11 * attribution_fraction
    upstream = upstream_blend * min(max(0.0, village_attr - village_retention_need),
                                   max(0.0, village_room) * o["village_direct_ownership"])
    mother_profit = group_profit - village_attr + upstream
    village_cet_end = village_cet_pre - upstream / o["village_direct_ownership"]
    rwa = state["rwa"] * factor
    mother_rwa = state["mother_rwa"] * factor
    # Do not assume new eligible Tier 2. Existing eligibility is capped if loss
    # reserves contract; this is a conservative proxy, not a regulatory ECL model.
    cap_scale = min(1.0, allowance / anchor["allowance"])
    other_cap = (o["group_total_capital"] - o["group_cet1"]) * cap_scale
    mother_other_cap = (o["mother_total_capital"] - o["mother_cet1"]) * cap_scale
    cet_pre = state["cet"] + group_profit + debt["conversion_liability"]
    mother_cet_pre = state["mother_cet"] + mother_profit + debt["conversion_liability"]
    group_room = capital_room(cet_pre, (o["group_tier1"] - o["group_cet1"]), other_cap, rwa, p)
    mother_room = capital_room(mother_cet_pre, 0.0, mother_other_cap, mother_rwa, p)
    # Before-conversion capital is also tested using proportional annual income.
    before_fraction = min(1.0, max(0.0, years(begin, MATURITY) / years(begin, end)))
    if debt["conversion_liability"]:
        pre_event_group = capital_room(state["cet"] + group_profit * before_fraction,
                                      (o["group_tier1"] - o["group_cet1"]), other_cap,
                                      state["rwa"] * (1 + growth * before_fraction), p)
        pre_event_mother = capital_room(state["mother_cet"] + mother_profit * before_fraction,
                                       0.0, mother_other_cap,
                                       state["mother_rwa"] * (1 + growth * before_fraction), p)
    else:
        pre_event_group, pre_event_mother = group_room, mother_room
    return locals()


def project(data, asof, dividend_state, case):
    p, o = data["base"], data["observed"]
    state, meta = initialize(data, asof, dividend_state)
    anchor = copy.deepcopy(state)
    rows, issues = [], []
    for i in range(10):
        begin = asof.replace(year=asof.year + i)
        end = asof.replace(year=asof.year + i + 1)
        target_g = parameters(data, case, i)["growth"]
        calc = evaluate_year(data, state, anchor, meta, case, i, begin, end, target_g)
        # Growth first adjusts if retaining all profits still cannot meet buffers.
        if min(calc["group_room"], calc["mother_room"], calc["pre_event_group"], calc["pre_event_mother"], calc["village_room"]) < 0:
            low, high = -0.10, target_g
            feasible = evaluate_year(data, state, anchor, meta, case, i, begin, end, low)
            if min(feasible["group_room"], feasible["mother_room"], feasible["pre_event_group"], feasible["pre_event_mother"], feasible["village_room"]) < 0:
                issues.append({"year": i + 1, "type": "capital-infeasible-even-with-10-percent-contraction"})
                return {"case": case, "feasible": False, "rows": rows, "issues": issues, "meta": meta}
            for _ in range(50):
                mid = (low + high) / 2
                trial = evaluate_year(data, state, anchor, meta, case, i, begin, end, mid)
                if min(trial["group_room"], trial["mother_room"], trial["pre_event_group"], trial["pre_event_mother"], trial["village_room"]) >= 0:
                    low = mid
                else:
                    high = mid
            calc = evaluate_year(data, state, anchor, meta, case, i, begin, end, low)
        x = calc
        required_end = anchor["operating_book_anchor"] * x["rwa"] / anchor["rwa"]
        required_increase = required_end - x["required_begin"]
        target = max(0.0, x["group_profit"]) * p["payout"][min(i, 4)]
        if i >= 5:
            blend = (i - 4) / 5
            sustainable_cash = max(0.0, x["group_profit"] - required_increase
                                   + p["terminal_excess_release_fraction"] * x["excess_begin"])
            target = (1 - blend) * target + blend * sustainable_cash
        # Full 10% budget, not just a threshold top-up. Registered/issued mismatch
        # is handled as a stricter budget, not asserted as current legal fact.
        stat = 0.1 * max(0.0, x["mother_profit"]) if state["statutory"] < 0.5 * state["shares"] else 0.0
        mother_assets = state["mother_assets"] * (1 + x["growth"])
        general = max(0.0, 0.015 * mother_assets * p["general_reserve_stress_asset_fraction"] - state["general"])
        legal_room = max(0.0, state["mother_retained"] + x["mother_profit"] - stat - general)
        available = max(0.0, min(x["group_room"], x["mother_room"],
                                 x["pre_event_group"], x["pre_event_mother"], legal_room))
        committed = o["declared_interim_dps"] * o["shares"] if i == 0 and dividend_state == "unpaid" else 0.0
        if committed > available + 1e-7:
            issues.append({"year": i + 1, "type": "declared-dividend-not-funded"})
            return {"case": case, "feasible": False, "rows": rows, "issues": issues, "meta": meta}
        cash = min(max(target, committed), available)
        old_shares = state["shares"]
        dps = cash / old_shares
        price_after_dividend = state["conversion_price"] - dps if state["debt_active"] else state["conversion_price"]
        transfer = state["option"] if state["debt_active"] and not x["debt"]["active"] else 0.0
        conversion = x["debt"]["conversion_liability"]
        new_shares = 0.0
        if conversion:
            if price_after_dividend <= 0:
                raise ValueError("Nonpositive conversion price")
            new_shares = o["convertible_face"] / price_after_dividend
        ending_book = equity_bridge(state["book"], x["group_profit"], cash, conversion, transfer)
        ending_mother = equity_bridge(state["mother_book"], x["mother_profit"], cash, conversion, transfer)
        shares = old_shares + new_shares
        village_rwa = x["village_rwa_end"]
        village_cet = x["village_cet_end"]
        row = {"year": i + 1, "period_start": begin.isoformat(), "period_end": end.isoformat(),
               "growth_target": target_g, "growth_actual": x["growth"],
               "nim": x["q"]["nim"], "credit_cost_assumption": x["q"]["cc"], "cir": x["q"]["cir"],
               "average_earning_assets": x["average_ea"], "average_loans": x["average_loans"],
               "nii_before_funding": x["nii_before_funding"], "funding_expense": x["funding"],
               "fixed_funding_addback": x["fixed_funding_addback"],
               "fee": x["fee"], "trading": x["trading"], "other_income": x["other"],
               "revenue_before_funding": x["revenue"], "costs": x["costs"],
               "provision": x["provision"], "net_chargeoff": x["net_co"],
               "allowance_begin": state["allowance"], "allowance_end": x["allowance"],
               "other_credit_loss": x["other_loss"], "tax_surcharge": x["surcharge"],
               "minority_profit": x["minority"], "village_total_profit": x["village_total"],
               "village_attributable_profit": x["village_attr"],
               "village_upstream_budget": x["upstream"],
               "surplus_income": x["surplus_income"], "surplus_begin": x["excess_begin"],
               "retained_funding_variance": x["retained_funding_variance"],
               "group_profit": x["group_profit"], "mother_profit": x["mother_profit"],
               "book_begin": state["book"], "book_end": ending_book,
               "mother_book_begin": state["mother_book"], "mother_book_end": ending_mother,
               "cash_target": target, "cash_paid": cash, "dps": dps,
               "declared_interim_included": committed, "shares_begin": old_shares, "shares_end": shares,
               "conversion_liability": conversion, "option_transfer": transfer,
               "noncash_capital_transfers_end": state["noncash_capital_transfers"] + conversion + transfer,
               "conversion_price": price_after_dividend, "conversion_new_shares": new_shares,
               "capital_transaction_per_old_share": ending_book / shares - (ending_book - conversion - transfer) / old_shares,
               "debt_balance_begin": state["debt_balance"], "debt": x["debt"],
               "refinancing_principal": state["refinancing_principal"] + x["debt"]["refinance_principal"],
               "cet1_end": x["cet_pre"] - cash, "mother_cet1_end": x["mother_cet_pre"] - cash,
               "group_rwa_end": x["rwa"], "mother_rwa_end": x["mother_rwa"],
               "other_capital": x["other_cap"], "mother_other_capital": x["mother_other_cap"],
               "group_capital_room_after_cash": x["group_room"] - cash,
               "mother_capital_room_after_cash": x["mother_room"] - cash,
               "pre_event_capital_room_after_cash": min(x["pre_event_group"], x["pre_event_mother"]) - cash,
               "statutory_appropriation_budget": stat, "general_appropriation_stress": general,
               "mother_retained_end": state["mother_retained"] + x["mother_profit"] - cash - stat - general,
               "required_operating_book": required_end,
               "village_capital_room_after_upstream": x["village_room"] - x["upstream"] / o["village_direct_ownership"],
               "village_cet1_ratio_proxy": village_cet / village_rwa}
        rows.append(row)
        state.update(book=ending_book, mother_book=ending_mother,
                     mother_retained=row["mother_retained_end"], cet=row["cet1_end"],
                     mother_cet=row["mother_cet1_end"], rwa=x["rwa"], mother_rwa=x["mother_rwa"],
                     core_earning_assets=state["core_earning_assets"] * (1 + x["growth"]),
                     loans=state["loans"] * (1 + x["growth"]), allowance=x["allowance"], shares=shares,
                     option=state["option"] - transfer, conversion_price=price_after_dividend,
                     debt_balance=x["debt"]["balance"], debt_active=x["debt"]["active"],
                     refinancing_principal=row["refinancing_principal"],
                     noncash_capital_transfers=row["noncash_capital_transfers_end"],
                     statutory=state["statutory"] + stat, general=state["general"] + general,
                     mother_assets=mother_assets, village_assets=x["village_assets_end"], village_rwa=village_rwa, village_cet=village_cet)
    return {"case": case, "feasible": True, "rows": rows, "issues": issues,
            "meta": meta, "initial": anchor, "ending": state}


def value_case(data, result):
    if not result["feasible"]:
        return []
    p, rows, final = data["base"], result["rows"], result["ending"]
    last = rows[-1]
    g = data["cases"][result["case"]].get("terminal_g", p["terminal_g"])
    # Excess return is limited to demonstrably modeled parent/group headroom.
    theoretical_excess = max(0.0, final["book"] - last["required_operating_book"])
    eligible_excess = min(theoretical_excess,
                          max(0.0, last["group_capital_room_after_cash"]),
                          max(0.0, last["mother_capital_room_after_cash"]),
                          max(0.0, last["mother_retained_end"]))
    k = final["book"] - eligible_excess
    # Fixed financing addback/refinancing is not made to grow perpetually.
    scalable_profit = ((last["revenue_before_funding"] - last["fixed_funding_addback"])
                       * (1 - last["cir"]) - last["provision"]
                       - last["other_credit_loss"] - last["tax_surcharge"])
    scalable_profit = scalable_profit * (1 - p["effective_business_tax"]) - last["minority_profit"]
    scalable_profit += (theoretical_excess - eligible_excess) * p["surplus_after_tax_return"]
    fixed_profit = (last["fixed_funding_addback"] * (1 - last["cir"])
                    * (1 - p["effective_business_tax"])
                    - final["refinancing_principal"] * p["refinancing_rate"]
                    * (1 - p["funding_tax_shield"]))
    fixed_profit -= final["noncash_capital_transfers"] * p["surplus_after_tax_return"]
    normalized_profit_next = scalable_profit * (1 + g) + fixed_profit
    # Existing non-CET capital is fixed, not magically scaled forever. Growth
    # must therefore fund the gross capital requirement, not merely g*net K.
    growth_capital_base = max(k, p["working_total_floor"] * final["rwa"])
    values = []
    for ke in p["equity_cost_endpoints"]:
        if ke <= g:
            raise ValueError("Discount rate must exceed terminal growth")
        operating_value = (scalable_profit * (1 + g) - g * growth_capital_base) / (ke - g) + fixed_profit / ke
        lam, y = p["terminal_excess_release_fraction"], p["surplus_after_tax_return"]
        excess_value = eligible_excess * (y + lam) / (ke + lam)
        terminal_10 = (operating_value + excess_value) / final["shares"]
        terminal_5 = sum(r["dps"] / (1 + ke) ** (r["year"] - 5) for r in rows[5:]) + terminal_10 / (1 + ke) ** 5
        five = present_value(result["initial"]["book"] / result["initial"]["shares"], rows[:5], terminal_5, ke)
        # Auxiliary earnings/necessary-capital anchor at Y5, without the five-
        # year payout transition: distinct maturation assumption, not averaged.
        r5 = rows[4]
        e5 = max(0.0, r5["book_end"] - r5["required_operating_book"])
        e5 = min(e5, max(0.0, r5["group_capital_room_after_cash"]), max(0.0, r5["mother_capital_room_after_cash"]))
        k5 = r5["book_end"] - e5
        scalable5 = (((r5["revenue_before_funding"] - r5["fixed_funding_addback"]) * (1 - r5["cir"])
                      - r5["provision"] - r5["other_credit_loss"] - r5["tax_surcharge"])
                     * (1 - p["effective_business_tax"]) - r5["minority_profit"])
        scalable5 += max(0.0, r5["book_end"] - r5["required_operating_book"] - e5) * p["surplus_after_tax_return"]
        fixed5 = (r5["fixed_funding_addback"] * (1 - r5["cir"]) * (1 - p["effective_business_tax"])
                  - r5["refinancing_principal"] * p["refinancing_rate"] * (1 - p["funding_tax_shield"]))
        fixed5 -= r5["noncash_capital_transfers_end"] * p["surplus_after_tax_return"]
        growth_k5 = max(k5, p["working_total_floor"] * r5["group_rwa_end"])
        auxiliary_tv5 = ((scalable5 * (1 + g) - g * growth_k5) / (ke - g) + fixed5 / ke
                         + e5 * (y + lam) / (ke + lam)) / r5["shares_end"]
        auxiliary_current = present_value(result["initial"]["book"] / result["initial"]["shares"], rows[:5], auxiliary_tv5, ke)["value"]
        values.append({"equity_cost": ke, "terminal_g": g,
                       "terminal_10_per_share": terminal_10, "terminal_5_per_share": terminal_5,
                       "terminal_operating_capital": k, "terminal_operating_profit_next": normalized_profit_next,
                       "terminal_growth_capital_base": growth_capital_base,
                       "terminal_scalable_profit_base": scalable_profit, "terminal_fixed_profit": fixed_profit,
                       "terminal_implied_operating_roe": normalized_profit_next / k,
                       "terminal_eligible_excess": eligible_excess,
                       "terminal_excess_value": excess_value,
                       "terminal_excess_release_fraction": lam,
                       "terminal_operating_value": operating_value,
                       "current_value_per_share": five["value"], "ri_identity": five["ri_identity"],
                       "five_year_dividend_pv": five["dividend_pv"],
                       "terminal_pv_contribution": five["terminal_pv"] / five["value"] if five["value"] else None,
                       "auxiliary_current_value": auxiliary_current,
                       "auxiliary_terminal_5": auxiliary_tv5})
    return values


def audit(result):
    failures = []
    if not result["feasible"]:
        return result["issues"]
    for r in result["rows"]:
        expected = equity_bridge(r["book_begin"], r["group_profit"], r["cash_paid"], r["conversion_liability"], r["option_transfer"])
        if abs(expected - r["book_end"]) > 1e-7:
            failures.append({"year": r["year"], "check": "common-equity-roll"})
        if abs(r["allowance_begin"] + r["provision"] - r["net_chargeoff"] - r["allowance_end"]) > 1e-7:
            failures.append({"year": r["year"], "check": "allowance-roll"})
        if min(r["group_capital_room_after_cash"], r["mother_capital_room_after_cash"], r["pre_event_capital_room_after_cash"], r["mother_retained_end"], r["village_capital_room_after_upstream"]) < -1e-6:
            failures.append({"year": r["year"], "check": "distribution-capacity"})
    for v in result.get("values", []):
        if abs(v["current_value_per_share"] - v["ri_identity"]) > 1e-7:
            failures.append({"check": "holder-ri-ddm-identity"})
    return failures
