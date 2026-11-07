"""Finite, homogeneous normalized bank cycle and cash-backed earnings method.

Economic conventions are frozen in REVISION-BUDGET-BEFORE-CODE.md. This module
does not import/run the issuer model at top level beyond shared definitions.
"""
from copy import deepcopy
from math import ceil, isclose
from bank_model import EconomicInfeasible, next_month, raw_nii, operating_parameters, legal_capacity


GROWING_STOCKS = ("bg", "bp", "cash", "loans", "allowance", "other_net_assets",
    "deposits", "funding", "refinancing", "at1", "t2", "rwag", "rwap",
    "dedg", "dedp", "offg", "offp", "general", "group_at1_extra", "group_t2_extra")
FIXED_STOCKS = ("stat", "arbitrary", "shares")


def verify_cycle_residuals(start, end, growth):
    residuals = {key: end[key] - start[key] * (1 + growth) for key in GROWING_STOCKS}
    residuals.update({key: end[key] - start[key] for key in FIXED_STOCKS})
    # Fixed non-RE classifications remain fixed; general reserve grows.
    residuals["RE_affine"] = end["re"] - (start["re"] + growth * (start["bp"] - start["general"]))
    failed = {k: v for k, v in residuals.items() if abs(v) > .01}
    if failed:
        raise ArithmeticError("normalized nonhomogeneous stock boundary: " + str(failed))
    return residuals


def normalized_capital(stocks, policy):
    cg = stocks["bg"] + stocks["offg"] - stocks["dedg"]
    cp = stocks["bp"] + stocks["offp"] - stocks["dedp"]
    ag, ap = stocks["at1"] + stocks["group_at1_extra"], stocks["at1"]
    tg, tp = stocks["t2"] + stocks["group_t2_extra"], stocks["t2"]
    head = {
        "group_cet1": cg - policy["group_cet1_floor"] * stocks["rwag"],
        "parent_cet1": cp - policy["parent_cet1_floor"] * stocks["rwap"],
        "group_tier1": cg + ag - policy["tier1_floor"] * stocks["rwag"],
        "parent_tier1": cp + ap - policy["tier1_floor"] * stocks["rwap"],
        "group_total": cg + ag + tg - policy["total_capital_floor"] * stocks["rwag"],
        "parent_total": cp + ap + tp - policy["total_capital_floor"] * stocks["rwap"],
    }
    return {"headrooms": head, "cet1_group": cg, "cet1_parent": cp,
            "cet1_ratio_group": cg / stocks["rwag"], "cet1_ratio_parent": cp / stocks["rwap"]}


def _normalized_cycle(basis, progress=None):
    """Same function for issuer terminal, auxiliary mature state and handcase.

    Stock growth is prescribed independently of dividend; the resulting cash
    bridge MUST close without a funding plug. Nonhomogeneity is an error.
    """
    start = deepcopy(basis["stocks"])
    st = deepcopy(start)
    growth, policy = basis["growth"], basis["policy"]
    ni_g, ni_p = basis["net_income_group"], basis["net_income_parent"]
    perpetual = basis["perpetual_cash_total"]
    eg, ep = sum(ni_g) - perpetual, sum(ni_p) - perpetual
    dividend = eg - growth * start["bg"]
    upstream = dividend + growth * start["bp"] - ep
    subsidiary_earnings = eg - ep
    cap = basis["upstream_fraction_max"] * max(0.0, subsidiary_earnings)
    if dividend < -1e-6:
        raise EconomicInfeasible("normalized earnings cannot fund required common-capital growth")
    if upstream < -1e-6 or upstream > cap + 1e-6:
        raise EconomicInfeasible("normalized parent/subsidiary retention budget:" + str({
            "upstream_needed": upstream, "cap": cap, "subsidiary_earnings": subsidiary_earnings}))
    upstream = max(0.0, upstream)
    if start["other_net_assets"] < 0 or start["funding"] < 0:
        raise EconomicInfeasible("normalized existing net operating asset/funding composition invalid")
    annual_funding = growth * (start["funding"] + start["refinancing"])
    funding_cap = policy["annual_net_funding_capacity"] * start["deposits"]
    if annual_funding > funding_cap + .01:
        raise EconomicInfeasible("normalized ordinary/replacement financing exceeds normal capacity")
    fy_ni = deepcopy(basis["fy_parent"])
    paid_c = deepcopy(basis["fy_paid_common"])
    paid_p = deepcopy(basis["fy_paid_perpetual"])
    year, month = basis["year"], basis["month"]
    rows = []
    for i in range(12):
        year, month = next_month(year, month)
        before = deepcopy(st)
        try:
            h = 1 + growth * (i + 1) / 12
            # Operating stocks and each separate finance category grow; common
            # B and cash are computed from earnings/flows, not assigned targets.
            for key in GROWING_STOCKS:
                if key not in ("bg", "bp", "cash"):
                    st[key] = start[key] * h
            perp = perpetual * basis["perpetual_weights"][i]
            div = dividend * basis["dividend_weights"][i]
            up = upstream * basis["upstream_weights"][i]
            common_g = ni_g[i] - perp
            common_p = ni_p[i] + up - perp
            st["bg"] += common_g - div
            st["bp"] += common_p - div
            reserve_move = st["general"] - before["general"]
            st["re"] += common_p - div - reserve_move
            loan_charge = basis["loan_charge_parent"][i]
            nonloan_charge = basis["nonloan_charge_parent"][i]
            net_writeoff = loan_charge - (st["allowance"] - before["allowance"])
            if net_writeoff < -1e-6:
                raise EconomicInfeasible("normalized allowance growth exceeds credit-loss charge")
            funding_flows = {key: st[key] - before[key]
                for key in ("deposits", "funding", "refinancing", "at1", "t2")}
            cash_operating = ni_p[i] + up + loan_charge + nonloan_charge
            loan_principal_cash = st["loans"] - before["loans"] + net_writeoff
            other_principal_cash = st["other_net_assets"] - before["other_net_assets"] + nonloan_charge
            st["cash"] += cash_operating - loan_principal_cash - other_principal_cash - perp - div + sum(funding_flows.values())
            prior = fy_ni.get(year - 1)
            if prior is None:
                raise ArithmeticError("normalized calendar missing previous parent NI")
            paid_p[year] = paid_p.get(year, 0.0) + perp
            room = legal_capacity(prior, paid_c.get(year, 0.0), 0.0, paid_p[year], basis["perpetual_in_law"])
            if div > room + .01:
                raise EconomicInfeasible("normalized first-cycle annual-principle limit")
            paid_c[year] = paid_c.get(year, 0.0) + div
            fy_ni[year] = fy_ni.get(year, 0.0) + ni_p[i] + up
            capital = normalized_capital(st, policy)
            floor = policy["cash_floor_ratio"] * st["deposits"]
            if min(capital["headrooms"].values()) < -.01 or st["cash"] < floor - .01 or st["re"] < -.01:
                raise EconomicInfeasible("normalized intra-cycle capital/cash/RE constraint")
            row = {"year": year, "month": month, "date": f"{year}-{month:02d}-28",
                "dps": div / st["shares"], "dividend": div, "perpetual_cash": perp,
                "common_earnings_group": common_g, "common_earnings_parent": common_p,
                "net_income_parent_including_upstream": ni_p[i] + up,
                "upstream_cash_and_income_once": up, "general_transfer": reserve_move,
                "loan_charge_parent": loan_charge, "net_writeoff_parent": net_writeoff,
                "cash_operating": cash_operating, "loan_principal_cash": loan_principal_cash,
                "other_principal_cash": other_principal_cash, "financing_cash": funding_flows,
                "cash_before": before["cash"], "cash_end": st["cash"], "cash_floor": floor,
                "parent_RE_end": st["re"], "calendar_previous_parent_NI": prior,
                "calendar_principle_room_before_payment": room, "capital": capital,
                "bps_start": before["bg"] / st["shares"], "bps_end": st["bg"] / st["shares"],
                "stocks_end": deepcopy(st)}
            rows.append(row)
            if progress is not None:
                progress({"phase": "normalized_cycle", "completed_months": len(rows),
                          "rows": rows, "last_complete_state": st})
        except Exception as exc:
            if progress is not None:
                try:
                    progress({"phase": "normalized_cycle", "rows": rows, "last_complete_state": before,
                              "failed_month": [year, month], "exception_type": type(exc).__name__, "exception": str(exc)})
                except Exception as recording_error:
                    exc.add_note("Failure snapshot also failed: " + repr(recording_error))
            raise
    residuals = verify_cycle_residuals(start, st, growth)
    # Two symbolically scaled adjoining cycles establish the full future
    # calendar NI/payment relationship, including Nov/Dec vs Jan/Oct.
    future_ni, future_pay = {}, {}
    for cycle_index in (0, 1):
        factor = (1 + growth) ** cycle_index
        for row in rows:
            yy = row["year"] + cycle_index
            future_ni[yy] = future_ni.get(yy, 0.0) + row["net_income_parent_including_upstream"] * factor
            amount = row["dividend"] + (row["perpetual_cash"] if basis["perpetual_in_law"] else 0.0)
            future_pay[yy] = future_pay.get(yy, 0.0) + amount * factor
    pay_years = [r["year"] for r in rows if r["dividend"] > 0]
    target_year = max(pay_years) + 1 if pay_years else max(r["year"] for r in rows) + 1
    perpetual_calendar_room = future_ni[target_year - 1] - future_pay[target_year]
    if perpetual_calendar_room < -.01:
        raise EconomicInfeasible("normalized long-run calendar principle fails despite first-cycle feasibility")
    return {"rows": rows, "growth": growth, "shares": start["shares"],
        "start_B": start["bg"], "end_B": st["bg"], "ordinary_distribution": dividend,
        "common_earnings": eg, "common_earnings_parent_before_upstream": ep,
        "upstream": upstream, "upstream_cap": cap, "ROE_on_opening_B": eg / start["bg"],
        "payout": dividend / eg if eg else None, "retention_growth_check": (eg - dividend) / start["bg"],
        "stocks_start": start, "stocks_end": st, "boundary_residuals": residuals,
        "long_run_calendar_principle_room": perpetual_calendar_room,
        "normal_financing_growth": annual_funding, "normal_financing_capacity": funding_cap,
        "normalization_notes": basis.get("normalization_notes", {})}


def normalized_cycle(basis, progress=None):
    last = {"phase": "normalized_cycle_start", "rows": [], "last_complete_state": deepcopy(basis["stocks"])}
    def snapshot(item):
        last.clear()
        last.update(item)
        if progress is not None:
            progress(item)
    try:
        return _normalized_cycle(basis, snapshot)
    except Exception as exc:
        last.update({"exception_type": type(exc).__name__, "exception": str(exc),
                     "status": "economic_infeasible" if isinstance(exc, EconomicInfeasible) else "failed_nonzero"})
        if progress is not None:
            try:
                progress(last)
            except Exception as recording_error:
                exc.add_note("Failure snapshot also failed: " + repr(recording_error))
        raise


def terminal_dividend_weights(total_dividend, actual_prior_h1, normalized_current_h1,
                              growth, interim_share, months):
    """Previous-H1 timing budget, not a new statutory restriction.

    I is the first cycle's February payment. Next cycle pays I*(1+g),
    against THIS cycle's H1. June absorbs the timing change; annual D is fixed.
    """
    if 1 + growth <= 0:
        raise EconomicInfeasible("invalid normalized growth for previous-H1 budget")
    annual = max(0.0, total_dividend)
    actual_cap = max(0.0, actual_prior_h1) / 3
    next_cycle_cap = max(0.0, normalized_current_h1) / 3
    interim = min(interim_share * annual, actual_cap, next_cycle_cap / (1 + growth))
    weights = [0.0] * 12
    if annual > 0:
        weights[months.index(2)] = interim / annual
        weights[months.index(6)] = 1 - interim / annual
    next_interim = interim * (1 + growth)
    room = next_cycle_cap - next_interim
    if room < -1e-8:
        raise ArithmeticError("next-cycle February exceeds previous-H1 budget")
    return {"weights": weights, "annual_dividend_unchanged": annual,
        "first_interim": interim, "first_final": annual - interim,
        "actual_previous_H1_cap": actual_cap, "normalized_current_H1": normalized_current_h1,
        "next_cycle_interim": next_interim, "next_cycle_previous_H1_cap": next_cycle_cap,
        "next_cycle_previous_H1_budget_room": room}


def build_basis(state, config, scenario_name, diagnostic, mode="terminal"):
    q, policy0 = config["source"], config["policy"]
    scenario = config["scenarios"][scenario_name]
    p = deepcopy(policy0)
    p["group_cet1_floor"] += scenario["capital_buffer_add"]
    p["parent_cet1_floor"] += scenario["capital_buffer_add"]
    p["annual_net_funding_capacity"] *= diagnostic.get("funding_capacity_multiplier", 1.0)
    growth = scenario["growth_terminal"] if mode == "terminal" else 0.0
    credit_ratio = q["parent_credit_9m"] / q["credit_9m"]
    target_allowance = q["group_loans"] * state["scale"] * scenario["allowance_ratio"]
    catchup = max(0.0, target_allowance - state["loan_allowance"])
    group_loss = catchup * (1 - p["group_tax"]) * q["group_parent_profit_9m"] / q["group_net_profit_9m"]
    parent_loss = catchup * credit_ratio * (1 - p["parent_tax"])
    stat_topup = max(0.0, state["shares"] * .5 - state["stat"])
    remaining_stat_budget = max(0.0, .1 * max(0.0, state["fy_parent"].get(state["year"], 0.0) - parent_loss)
        - state["fy_statutory_budget"].get(state["year"], 0.0))
    if stat_topup > remaining_stat_budget + .01:
        raise EconomicInfeasible("normalization statutory gap exceeds available annual profit budget")
    stocks = {"bg": state["bg"] - group_loss, "bp": state["bp"] - parent_loss,
        "cash": state["cash"], "loans": q["group_loans"] * q["parent_net_loans"] / q["group_net_loans"] * state["scale"],
        "allowance": (state["loan_allowance"] + catchup) * credit_ratio,
        "deposits": q["parent_deposits"] * state["scale"],
        "funding": state["funding"] - q["parent_t2"], "refinancing": state["refinancing"],
        "at1": q["parent_at1"] + state["at1_new"], "t2": q["parent_t2"] + state["t2_new"],
        "group_at1_extra": q["group_at1"] - q["parent_at1"],
        "group_t2_extra": q["group_t2"] - q["parent_t2"],
        "rwag": q["group_min_capital"] / .08 * state["scale"],
        "rwap": q["parent_min_capital"] / .08 * state["scale"],
        "dedg": q["group_deduction"] * state["scale"], "dedp": q["parent_deduction"] * state["scale"],
        "offg": state["group_reg_offset"], "offp": state["parent_reg_offset"],
        "general": state["general"], "stat": state["stat"] + stat_topup,
        "arbitrary": state["arbitrary"], "shares": state["shares"],
        "re": state["re"] - parent_loss - stat_topup}
    stocks["other_net_assets"] = (stocks["bp"] + stocks["deposits"] + stocks["funding"] + stocks["refinancing"]
        + stocks["at1"] + stocks["t2"] - stocks["cash"] - stocks["loans"] + stocks["allowance"])
    op = operating_parameters(scenario, state["year"], state["month"], diagnostic)
    reference_cb = q["cb_h1_accretion"] * 2
    parent_nii_ratio = q["parent_nii_9m"] / q["nii_9m"]
    if mode == "terminal":
        correction = q["nii_9m"] * 4 / 3 - raw_nii(q) + reference_cb
        unit_nii = raw_nii(q, op["loan_shift"], op["invest_shift"], op["deposit_shift"], op["wholesale_shift"]) + correction
        unit_nii += diagnostic.get("nii_margin_add", 0.0) * sum(q["asset_balances"])
        wholesale_rate = q["liability_rates"][1] + op["wholesale_shift"]
        fee_scale, expense_scale = state["fee_scale"], state["expense_scale"]
        cc = op["cc"]
    else:
        # Independent normalized NII; no Q3 reconciliation/correction.
        unit_nii = raw_nii(q) + reference_cb
        wholesale_rate = q["liability_rates"][1]
        fee_scale = expense_scale = state["scale"]
        cc = .0095
    funding_cost = ((state["funding"] - state["initial_funding"] * state["scale"]) * wholesale_rate
        + state["refinancing"] * scenario["refinance_rate"] + state["t2_new"] * p["new_t2_rate"]
        + q["parent_t2"] * (p["new_t2_rate"] - q["liability_rates"][3]))
    nii0 = unit_nii * state["scale"] - funding_cost
    nii_parent0 = (unit_nii * parent_nii_ratio + reference_cb * (1 - parent_nii_ratio)) * state["scale"] - funding_cost
    arrays = {key: [] for key in ("net_income_group", "net_income_parent", "loan_charge_parent", "nonloan_charge_parent")}
    months, years = [], []
    yy, mm = state["year"], state["month"]
    for i in range(12):
        yy, mm = next_month(yy, mm)
        months.append(mm); years.append(yy)
        h = 1 + growth * (i + .5) / 12
        fee = q["fee_9m"] * 4 / 3 * fee_scale * h / 12
        trade = q["fy25_trade"] * state["scale"] * h / 12
        other = (q["fy25_revenue"] - q["fy25_nii"] - q["fy25_fee"] - q["fy25_trade"]) * state["scale"] * h / 12
        expense = q["fy25_revenue"] * q["fy25_cost_income"] * expense_scale * h * p["month_expense_weights"][mm - 1]
        taxes_other = 1705 * 4 / 3 * state["scale"] * h / 12
        loan_charge = q["group_loans"] * state["scale"] * h * cc / 12
        nonloan = sum(q["asset_balances"][3:]) * state["scale"] * h * p["nonloan_credit_cost"] / 12
        pretax = nii0 * h / 12 + fee + trade + other - expense - taxes_other - loan_charge - nonloan
        ni_g = (pretax - max(0.0, pretax) * p["group_tax"]) * q["group_parent_profit_9m"] / q["group_net_profit_9m"]
        pretax_p = (nii_parent0 * h / 12 + fee * q["parent_fee_9m"] / q["fee_9m"]
            + trade * sum(q["parent_trade_9m_components"]) / q["trade_9m"] + other * .15
            - expense * q["parent_expense_9m"] / q["expense_9m"] - taxes_other * 1459 / 1705
            - (loan_charge + nonloan) * credit_ratio)
        arrays["net_income_group"].append(ni_g)
        arrays["net_income_parent"].append(pretax_p - max(0.0, pretax_p) * p["parent_tax"])
        arrays["loan_charge_parent"].append(loan_charge * credit_ratio)
        arrays["nonloan_charge_parent"].append(nonloan * credit_ratio)
    perp = stocks["at1"] * p["perpetual_reset_rate"] * (1 + growth / 2)
    eg = sum(arrays["net_income_group"]) - perp
    expected_div = eg - growth * stocks["bg"]
    normalized_h1_common = sum(arrays["net_income_group"][i] for i, m in enumerate(months) if m <= 6) - perp * 9 / 11
    dweights = [0.0] * 12
    interim_budget = None
    if mode == "terminal":
        interim_budget = terminal_dividend_weights(expected_div,
            state["h1_common"].get(state["year"], 0.0), normalized_h1_common,
            growth, p["interim_share"], months)
        dweights = interim_budget["weights"]
    else:
        dweights[-1] = 1.0  # auxiliary annual cash convention, not V1 D
    pweights = [9 / 11 if m == 4 else 2 / 11 if m == 9 else 0.0 for m in months]
    uweights = [1.0 if m == 9 else 0.0 for m in months]
    fy_parent = deepcopy(state["fy_parent"])
    fy_parent[state["year"]] -= parent_loss
    if mode != "terminal":
        # Mature feasibility only. Actual initial prior NI is separately used
        # in the finite auxiliary cash-release bridge; it is not overwritten there.
        fy_parent[state["year"]] = sum(arrays["net_income_group"])
    return {"stocks": stocks, "growth": growth, "policy": p,
        **arrays, "perpetual_cash_total": perp, "dividend_weights": dweights,
        "perpetual_weights": pweights, "upstream_weights": uweights,
        "upstream_fraction_max": p["sub_remit_fraction_max"] if mode == "terminal" else 1.0,
        "perpetual_in_law": diagnostic.get("perpetual_in_law", False),
        "year": state["year"], "month": state["month"], "fy_parent": fy_parent,
        "fy_paid_common": deepcopy(state["fy_paid_common"]),
        "fy_paid_perpetual": deepcopy(state["fy_paid_perpetual"]),
        "normalization_notes": {"mode": mode, "entry_allowance_catchup": catchup,
            "terminal_previous_H1_payment_budget": interim_budget,
            "entry_group_common_loss": group_loss, "entry_parent_common_loss": parent_loss,
            "statutory_topup_internal_only": stat_topup,
            "other_net_assets_is_existing_nonloan_assets_net_nonfinancing_liabilities": True,
            "future_refinancing_is_generic_replacement_debt_not_original_CB": True,
            "annual_normalized_NII": nii0, "annual_normalized_parent_NII": nii_parent0,
            "future_all_capital_funding_growth_is_costed": True}}


def terminal_cycle(forecast, config, progress=None):
    basis = build_basis(forecast["last_state"], config, forecast["scenario"], forecast["diagnostic"])
    cycle = normalized_cycle(basis, progress)
    old_div = sum(r["dividend"] for r in forecast["rows"][-12:])
    gap = None if old_div == 0 else cycle["ordinary_distribution"] / old_div - 1
    cycle["distribution_transition_gap"] = gap
    if gap is None or abs(gap) > config["policy"]["terminal_distribution_gap_max"]:
        raise EconomicInfeasible("normalized terminal transition requires economic review:" + str(gap))
    return cycle


def repayment_annuity(backlog, annual_capacity, ke):
    """PV at just before the first repayment; principal is not valued twice."""
    if backlog <= 0:
        return {"pv": 0.0, "years": 0, "last_payment": 0.0}
    if annual_capacity <= 0:
        raise EconomicInfeasible("no bounded legal route for retained-cash release")
    years = ceil(backlog / annual_capacity)
    last = backlog - annual_capacity * (years - 1)
    full_pv = annual_capacity * (1 - (1 + ke) ** (-(years - 1))) / ke
    return {"pv": full_pv + last / (1 + ke) ** years, "years": years, "last_payment": last}


def auxiliary_release_bridge(common_profit, normalized_perpetual, initial_prior_parent_ni,
                             gross_coupon_savings, ke):
    """Calendar annual bridge; retained earnings become cash, then are released.

    Each year's actual ordinary payment is limited by previous parent NI.
    Zero growth keeps operating capital intact. Extra retained cash earns zero
    incremental income and is fully valued through finite principal repayments.
    """
    if common_profit <= 0:
        raise EconomicInfeasible("nonpositive normalized auxiliary earnings")
    n = max([0, *gross_coupon_savings.keys()]) + 1
    prior = initial_prior_parent_ni
    retained = 0.0
    pv = 0.0
    rows = []
    for year in range(1, n + 1):
        gross_saving = gross_coupon_savings.get(year, 0.0)
        # Source statutory tax rate 25%; lower actual perpetual cost reduces
        # its tax deduction. This finite item does not alter operating inputs.
        cash_profit = common_profit + .75 * gross_saving
        parent_ni = common_profit + normalized_perpetual - .25 * gross_saving
        available = retained + cash_profit
        payment = max(0.0, min(available, prior))
        retained_end = available - payment
        rows.append({"year": year, "prior_parent_NI": prior, "parent_NI": parent_ni,
            "common_cash_profit": cash_profit, "dividend": payment,
            "cash_and_RE_retained_before": retained, "cash_and_RE_retained_end": retained_end,
            "ordinary_capital_below_operating_floor": False})
        pv += payment / (1 + ke) ** year
        retained, prior = retained_end, parent_ni
    # From here NI is stable: ordinary profit plus perpetual priority expense.
    # The principle permits that expense-sized headroom to return old cash.
    release = repayment_annuity(retained, normalized_perpetual, ke)
    tail = common_profit / ke + release["pv"]
    value = pv + tail / (1 + ke) ** n
    return {"value_total_at_anchor": value, "annual_rows": rows,
        "tail_regular_profit_value": common_profit / ke,
        "retained_cash_principal": retained, "retained_cash_release": release,
        "retained_cash_extra_yield": 0.0, "retained_cash_counted_once": True,
        "release_horizon_requires_review": release["years"] > 10}


def auxiliary_normalized(config, forecast, ke, progress=None):
    anchor = forecast.get("auxiliary_anchor")
    if anchor is None or anchor["state"]["cb_status"] != "redeemed":
        raise EconomicInfeasible("auxiliary requires same base no-conversion maturity anchor")
    state = anchor["state"]
    if progress is not None:
        progress({"phase": "auxiliary_anchor", "state": state, "ke": ke})
    basis = build_basis(state, config, "base", {}, mode="auxiliary")
    cycle = normalized_cycle(basis, progress)
    savings = {}
    for tr in config["source"]["perpetual_tranches"]:
        for year in range(state["year"] + 1, tr["reset_year"]):
            n = year - state["year"]
            savings[n] = savings.get(n, 0.0) + tr["principal"] * (config["policy"]["perpetual_reset_rate"] - tr["coupon"])
    bridge = auxiliary_release_bridge(cycle["common_earnings"], basis["perpetual_cash_total"],
        state["fy_parent"][state["year"]] - basis["normalization_notes"]["entry_parent_common_loss"], savings, ke)
    # Same finite obligations before debt maturity; independent earnings after.
    prefix = forecast["rows"][:anchor["row_count"]]
    rm = (1 + ke) ** (1 / 12) - 1
    prefix_pv = sum(r["dps"] / (1 + rm) ** (i + 1) for i, r in enumerate(prefix))
    anchor_ps = bridge["value_total_at_anchor"] / state["shares"]
    present = prefix_pv + anchor_ps / (1 + rm) ** len(prefix)
    return {"method": "independent_normalized_earnings_with_parent_cash_release",
        "anchor_date": "2027-12-31", "same_no_conversion_obligations_prefix_months": len(prefix),
        "normalized_mature_cycle": cycle, "parent_cash_release_bridge": bridge,
        "normal_ROE": cycle["common_earnings"] / cycle["start_B"],
        "growth": 0.0, "required_return": ke, "mature_subsidiary_upstream_fraction_max": 1.0,
        "prefix_dividend_pv": prefix_pv, "anchor_per_share_value": anchor_ps,
        "per_share_value": present, "extra_cash_added_separately": 0.0,
        "basis": "Independent H1 gross-yield profitability; actual branch capital obligations through 2027 maturity; zero-expansion mature upstreaming and bounded retained-cash recovery."}
