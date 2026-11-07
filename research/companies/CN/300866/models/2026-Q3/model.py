'Anker ordinary offline economic research calculator. Standard library, no network. CNY billions/shares billions/CNY per share. Inert on import; no coordinator admission ticket.'
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time


def close(actual, expected, label):
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), (
        label, actual, expected
    )


def config_for(data, name):
    cfg = copy.deepcopy(data["base"])
    if name != "base":
        cfg.update(copy.deepcopy(data["cases"][name]))
    return cfg


def starting_state(f, c):
    revenue = f["fy25_revenue"] + f["nine_month_26_revenue"] - f["nine_month_25_revenue"]
    trade_wc = (f["inventory"] + f["receivables"] + f["prepayments"]
                - f["payables"] - f["notes_payable"] - f["contract_liabilities"])
    op_cash = revenue * c["operating_cash_ratio"]
    gross_liquid = (f["cash"] + f["trading_assets"] + c["other_current_deposits"]
                    + f["derivative_assets"] - f["derivative_liabilities"]
                    - f["trading_liabilities"] - c["trading_realization_tax"] - op_cash)
    # Parent equity proceeds already lie inside reported cash: this is attribution,
    # never a second cash addition. Residual asset ownership is a bounded estimate.
    nci_liquid = max(0.0, gross_liquid - f["parent_equity_cash_received"]) * c["nci_fraction"]
    carry_change = c["unobserved_month_parent_financial_change"]
    liquid = gross_liquid - nci_liquid - f["declared_dividend_payable"] + carry_change
    nonliquid = ((f["associate_investments"] + f["other_noncurrent_financial"])
                 * c["investment_realization_factor"] * (1 - c["nci_fraction"]))
    bank = f["short_bank_debt"] + f["long_bank_debt"] + c["current_bank_debt"]
    return {
        "revenue": revenue, "trade_wc": trade_wc, "operating_cash": op_cash,
        "total_operating_wc": trade_wc + op_cash,
        "gross_liquid_after_operating_cash": gross_liquid,
        "nci_liquid_estimate": nci_liquid, "liquid": liquid,
        "nonliquid": nonliquid, "bank": bank, "cb_face": f["cb_face"],
        "financial_assets_common": liquid + nonliquid,
        "nfa_before_extra_redemption_reserve": liquid + nonliquid - bank - f["cb_carrying"],
        "unobserved_month_parent_financial_change": carry_change,
        "shares": f["shares"], "parent_liquid": c["parent_available_financial_assets"] + carry_change,
        # Conservative legal-distribution budget, not asserted actual accounting.
        "parent_retained": c["parent_retained_earnings"] - c["legacy_social_parent_retained_debit"],
        "legacy_social_parent_retained_debit": c["legacy_social_parent_retained_debit"],
        "parent_reserve": f["parent_statutory_reserve"],
        "old_ic_receivable": f["parent_old_subsidiary_receivables_lower"],
        "old_ic_payable": f["parent_old_subsidiary_payables"]
    }


def operating_year(revenue_previous, wc_previous, growth, margin, wc_ratio, c):
    revenue = revenue_previous * (1 + growth)
    margin_before_social_cost = margin
    recurring_social_cost = revenue * c["ongoing_social_cost_ratio"]
    margin = margin_before_social_cost - c["ongoing_social_cost_ratio"]
    ebit = revenue * margin  # cash rent and recurring replacement compensation included
    nopat = ebit * (1 - c["tax_rate"])
    da = revenue * c["nonlease_da_ratio"]  # no ROU depreciation add-back
    capex = revenue * c["capex_ratio"]
    trade_wc = revenue * wc_ratio
    operating_cash = revenue * c["operating_cash_ratio"]
    total_wc = trade_wc + operating_cash
    delta_wc = total_wc - wc_previous
    group_fcff = nopat + da - capex - delta_wc
    common_nopat = nopat * (1 - c["nci_fraction"])
    common_fcff = group_fcff * (1 - c["nci_fraction"])
    close(group_fcff, nopat + da - capex - delta_wc, "operating cash identity")
    return dict(revenue=revenue, growth=growth, margin=margin, ebit=ebit,
                margin_before_social_cost=margin_before_social_cost,
                recurring_social_cost=recurring_social_cost,
                nopat=nopat, common_nopat=common_nopat, da=da, capex=capex,
                trade_wc=trade_wc, operating_cash=operating_cash,
                total_operating_wc=total_wc, delta_wc=delta_wc,
                group_fcff=group_fcff, common_fcff=common_fcff)


def project(f, c):
    for key in ("growth", "margin", "trade_wc_ratio", "legacy_award_shares",
                "old_receivable_collections", "old_payable_settlements",
                "additional_parent_net_outflow", "legacy_social_cash"):
        assert len(c[key]) == 10, key
    assert len(c["cb_coupon_rates"]) == 5
    assert c["discount_rate"] > c["terminal_growth"] >= 0
    assert 0 <= c["nci_fraction"] < 1 and 0 <= c["payout"] <= 1
    assert c["cb_mode"] in ("repay", "convert")
    assert sum(c["legacy_award_shares"][5:]) == 0, "five-year FD count must include all legacy awards"
    assert c["ongoing_social_cost_ratio"] >= 0
    assert c["legacy_social_parent_retained_debit"] >= 0
    assert all(x >= 0 for x in c["legacy_social_cash"])
    assert sum(c["legacy_social_cash"][5:]) == 0, "no hidden claim after Y5"
    s = starting_state(f, c)
    opening = copy.deepcopy(s)
    rows = []
    cumulative_dps = 0.0
    feasible = True
    for i in range(10):
        year = i + 1
        row = operating_year(s["revenue"], s["total_operating_wc"],
                             c["growth"][i], c["margin"][i], c["trade_wc_ratio"][i], c)
        row["year"] = year
        new_legacy_shares = c["legacy_award_shares"][i]
        subscription_cash = new_legacy_shares * c["legacy_award_subscription_price"]
        shares = s["shares"] + new_legacy_shares
        bank_interest = s["bank"] * c["bank_rate"] * (1 - c["tax_rate"])
        bank_principal = min(c["bank_amortization"],
                             max(0.0, s["bank"] - f["short_bank_debt"]))
        cb_coupon_gross = s["cb_face"] * c["cb_coupon_rates"][i] if i < 5 else 0.0
        cb_coupon_net = cb_coupon_gross * (1 - c["tax_rate"])
        cb_cash = 0.0
        cb_premium = 0.0
        converted_shares = 0.0
        conversion_price = max(1.0, f["cb_conversion_price"] - cumulative_dps)
        next_cb = s["cb_face"]
        if year == 5 and next_cb:
            if c["cb_mode"] == "repay":
                cb_premium = next_cb * c["cb_redemption_premium"]
                cb_cash = next_cb + cb_premium
            else:
                converted_shares = next_cb / conversion_price
                shares += converted_shares
            next_cb = 0.0
        interest_income = max(0.0, s["liquid"]) * c["financial_yield_after_tax"]
        legacy_social_cash = c["legacy_social_cash"][i]
        group_before_distribution = (s["liquid"] + row["common_fcff"] + interest_income
                                     + subscription_cash - bank_interest - cb_coupon_net
                                     - bank_principal - cb_cash - legacy_social_cash)

        # Mother legal-profit and liquidity memo: intra-group receipts do not
        # increase group cash or group profit a second time.
        own_profit = row["common_nopat"] * c["parent_own_profit_fraction"]
        own_cash = own_profit * c["parent_own_cash_conversion"]
        subsidiary_dividend = row["common_nopat"] * c["subsidiary_dividend_fraction"]
        mother_interest = max(0.0, s["parent_liquid"]) * c["financial_yield_after_tax"]
        mother_profit = own_profit + subsidiary_dividend + mother_interest - cb_coupon_net - cb_premium
        reserve_gap = max(0.0, shares * 0.5 - s["parent_reserve"])
        reserve_add = min(max(0.0, mother_profit) * 0.10, reserve_gap)
        legal_available = s["parent_retained"] + mother_profit - reserve_add
        collect = min(c["old_receivable_collections"][i], s["old_ic_receivable"])
        settle = min(c["old_payable_settlements"][i], s["old_ic_payable"])
        parent_capital = c["parent_capital_deployment"] * row["revenue"] / opening["revenue"]
        extra_outflow = c["additional_parent_net_outflow"][i]
        mother_before_distribution = (s["parent_liquid"] + own_cash + subsidiary_dividend
                                      + mother_interest + collect - settle - parent_capital
                                      - extra_outflow + subscription_cash - cb_coupon_net - cb_cash
                                      - legacy_social_cash)
        operating_net_profit_common = row["common_nopat"] - bank_interest - cb_coupon_net
        distribution_budget = max(0.0, operating_net_profit_common) * c["payout"]
        group_capacity = group_before_distribution - c["group_liquid_floor"]
        parent_capacity = mother_before_distribution - c["parent_cash_floor"]
        distribution = max(0.0, min(distribution_budget, legal_available,
                                     group_capacity, parent_capacity))
        group_shortfall = max(0.0, -group_capacity)
        parent_shortfall = max(0.0, -parent_capacity)
        legal_shortfall = max(0.0, -legal_available)
        feasible = feasible and max(group_shortfall, parent_shortfall, legal_shortfall) < 1e-9
        liquid = group_before_distribution - distribution
        mother_liquid = mother_before_distribution - distribution
        parent_pool_excess = max(0.0, mother_liquid - liquid
                                 - row["operating_cash"] * (1 - c["nci_fraction"]))
        feasible = feasible and parent_pool_excess < 1e-9
        mother_retained = legal_available - distribution
        bank = s["bank"] - bank_principal
        dps = distribution / shares
        nfa = liquid + s["nonliquid"] - bank - next_cb
        close(liquid - s["liquid"], row["common_fcff"] + interest_income + subscription_cash
              - bank_interest - cb_coupon_net - bank_principal - cb_cash - legacy_social_cash - distribution,
              "ordinary group cash conservation")
        close(mother_liquid - s["parent_liquid"], own_cash + subsidiary_dividend + mother_interest
              + collect - settle - parent_capital - extra_outflow + subscription_cash
              - cb_coupon_net - cb_cash - legacy_social_cash - distribution, "mother cash conservation")
        close(mother_retained - s["parent_retained"], mother_profit - reserve_add - distribution,
              "mother retained earnings")
        close(shares - s["shares"], new_legacy_shares + converted_shares, "share roll-forward")
        close(nfa, liquid + s["nonliquid"] - bank - next_cb, "ordinary NFA bridge")
        assert distribution <= distribution_budget + 1e-9
        assert reserve_add <= max(0.0, mother_profit) * 0.10 + 1e-9
        assert s["parent_reserve"] + reserve_add <= shares * 0.5 + 1e-9
        if converted_shares:
            assert cb_cash == 0.0 and next_cb == 0.0
        row.update(shares=shares, legacy_shares=new_legacy_shares,
                   subscription_cash=subscription_cash, converted_shares=converted_shares,
                   conversion_price=conversion_price, bank_interest_after_tax=bank_interest,
                   bank_principal=bank_principal, bank_debt=bank, cb_coupon_cash_gross=cb_coupon_gross,
                   cb_coupon_after_tax=cb_coupon_net, cb_cash_redemption=cb_cash,
                   cb_premium_expense=cb_premium, cb_remaining=next_cb,
                   interest_income_after_tax=interest_income,
                   legacy_social_cash=legacy_social_cash,
                   group_cash_before_distribution=group_before_distribution,
                   distribution_budget=distribution_budget, distribution=distribution, dps=dps,
                   distribution_clipped=distribution < distribution_budget - 1e-9,
                   liquid_financial_assets=liquid, nonliquid_financial_assets=s["nonliquid"], nfa=nfa,
                   parent_own_profit=own_profit, parent_own_operating_cash=own_cash,
                   subsidiary_dividend_cash_and_new_profit=subsidiary_dividend,
                   parent_financial_income=mother_interest, parent_profit=mother_profit,
                   reserve_add=reserve_add, parent_reserve=s["parent_reserve"] + reserve_add,
                   parent_legal_available_before_D=legal_available,
                   parent_old_collection=collect, parent_old_payment=settle,
                   parent_capital_deployment=parent_capital, extra_parent_outflow=extra_outflow,
                   parent_cash_before_distribution=mother_before_distribution,
                   parent_liquid=mother_liquid, parent_retained=mother_retained,
                   old_ic_receivable=s["old_ic_receivable"] - collect,
                   old_ic_payable=s["old_ic_payable"] - settle,
                   group_liquidity_shortfall=group_shortfall,
                   parent_liquidity_shortfall=parent_shortfall, legal_shortfall=legal_shortfall)
        row["parent_cash_exceeds_common_group_pool"] = parent_pool_excess
        rows.append(row)
        cumulative_dps += dps
        s.update(revenue=row["revenue"], total_operating_wc=row["total_operating_wc"],
                 liquid=liquid, bank=bank, cb_face=next_cb, shares=shares,
                 parent_liquid=mother_liquid, parent_retained=mother_retained,
                 parent_reserve=row["parent_reserve"], old_ic_receivable=row["old_ic_receivable"],
                 old_ic_payable=row["old_ic_payable"])
    assert len(rows) == 10 and all(r["year"] == i + 1 for i, r in enumerate(rows))
    return opening, rows, feasible


def enterprise_value_at(rows, c, at_year=0, discount=None, terminal_growth=None):
    r = c["discount_rate"] if discount is None else discount
    g = c["terminal_growth"] if terminal_growth is None else terminal_growth
    assert 0 <= at_year <= 5 and r > g
    last = rows[-1]
    year11 = operating_year(last["revenue"], last["total_operating_wc"], g,
                            c["terminal_margin"], c["trade_wc_ratio"][-1], c)
    tv10 = year11["common_fcff"] / (r - g)
    tv_pv = tv10 / (1 + r) ** (10 - at_year)
    explicit_pv = sum(row["common_fcff"] / (1 + r) ** (row["year"] - at_year)
                      for row in rows if row["year"] > at_year)
    return dict(value=explicit_pv + tv_pv, explicit_pv=explicit_pv,
                terminal_pv=tv_pv, terminal_share=tv_pv / (explicit_pv + tv_pv),
                year11=year11, tv_at_year10=tv10)


def evaluate(f, c):
    opening, rows, feasible = project(f, c)
    ev = enterprise_value_at(rows, c)
    r = c["discount_rate"]
    subscription_pv = sum(row["subscription_cash"] / (1 + r) ** row["year"] for row in rows)
    if c["cb_mode"] == "repay":
        cb_claim = f["cb_carrying"] + f["cb_face"] * c["cb_redemption_premium"] / (1 + r) ** 5
    else:
        # Fully-converted valuation convention: no principal debt deduction;
        # forward FD shares include conversion, but pre-conversion coupons remain.
        cb_claim = sum(row["cb_coupon_after_tax"] / (1 + r) ** row["year"] for row in rows)
    nfa_bridge = opening["financial_assets_common"] - opening["bank"] - cb_claim
    # One conditional historical cash PV in BOTH current methods, not a
    # second present reported-debt deduction. Y5 retains the actual cash loss.
    legacy_social_pv = sum(row["legacy_social_cash"] / (1 + r) ** row["year"] for row in rows)
    fd_shares = rows[4]["shares"]
    current_value = (ev["value"] + nfa_bridge + subscription_pv - legacy_social_pv) / fd_shares
    auxiliary = (rows[0]["common_nopat"] * c["auxiliary_multiple"] / (1 + r)
                 + nfa_bridge + subscription_pv - legacy_social_pv) / fd_shares
    t5 = enterprise_value_at(rows, c, at_year=5)
    terminal_equity = (t5["value"] + rows[4]["nfa"]) / rows[4]["shares"]
    value_gap = auxiliary / current_value - 1 if current_value else None
    increment_profit = rows[4]["common_nopat"] - rows[0]["common_nopat"]
    increment_capital = ((rows[4]["total_operating_wc"] - rows[0]["total_operating_wc"])
                         + sum(row["capex"] - row["da"] for row in rows[1:5])) * (1 - c["nci_fraction"])
    return {
        "feasible_without_new_unbudgeted_funding": feasible,
        "current_value_per_share": current_value if feasible else None,
        "auxiliary_value_per_share": auxiliary if feasible else None,
        "auxiliary_gap_fraction": value_gap,
        "gap_requires_economic_explanation": value_gap is not None and abs(value_gap) > 0.25,
        "current_nfa_bridge": nfa_bridge, "legacy_subscription_pv": subscription_pv,
        "historical_social_settlement_pv": legacy_social_pv,
        "current_cb_claim": cb_claim, "fully_diluted_shares": fd_shares,
        "current_operating_value": ev, "opening": opening, "rows": rows,
        "year5_operating_value": t5, "year5_equity_per_share": terminal_equity if feasible else None,
        "year1_to_year5_incremental_return_diagnostic": (
            increment_profit / increment_capital if increment_capital > 0 else None),
        "incremental_return_is_forecast_not_realized": True,
        "five_year_actual_cash_per_original_share": sum(row["dps"] for row in rows[:5]),
        "transition_y5_y6": {key: [rows[4][key], rows[5][key]] for key in (
            "revenue", "growth", "margin", "total_operating_wc", "delta_wc", "common_fcff",
            "distribution", "dps", "liquid_financial_assets", "nfa", "parent_liquid")}
    }


def formal_chain_hand_cases(data):
    f = {key: 0.0 for key in data["facts"]}
    f.update(fy25_revenue=100.0, shares=10.0, cash=20.0, short_bank_debt=5.0,
             cb_face=10.0, cb_carrying=10.0, cb_conversion_price=5.0,
             parent_statutory_reserve=5.0)
    c = copy.deepcopy(data["base"])
    c.update(growth=[0.0]*10, margin=[0.1]*10, trade_wc_ratio=[0.0]*10,
             tax_rate=0.0, nci_fraction=0.0, operating_cash_ratio=0.0,
             capex_ratio=0.0, nonlease_da_ratio=0.0, discount_rate=0.1,
             terminal_growth=0.0, terminal_margin=0.1, auxiliary_multiple=10,
             other_current_deposits=0.0, investment_realization_factor=1.0,
             trading_realization_tax=0.0, current_bank_debt=0.0, bank_rate=0.0,
             bank_amortization=0.0, financial_yield_after_tax=0.0,
             cb_mode="repay", cb_coupon_rates=[0.0]*5, cb_redemption_premium=0.0,
             legacy_award_shares=[0.0]*10, legacy_award_subscription_price=0.0,
             payout=0.5, group_liquid_floor=0.0, parent_available_financial_assets=20.0,
             parent_retained_earnings=100.0, parent_own_profit_fraction=1.0,
             parent_own_cash_conversion=1.0, subsidiary_dividend_fraction=0.0,
             parent_capital_deployment=0.0, parent_cash_floor=0.0,
             old_receivable_collections=[0.0]*10, old_payable_settlements=[0.0]*10,
             additional_parent_net_outflow=[0.0]*10,
             ongoing_social_cost_ratio=0.0, legacy_social_cash=[0.0]*10,
             legacy_social_parent_retained_debit=0.0)
    result = evaluate(f, c)
    close(result["current_operating_value"]["value"], 100.0, "perpetuity 10 / 10%")
    close(result["current_value_per_share"], 10.5, "(100 + 20 - 5 - 10) / 10")
    close(result["rows"][4]["liquid_financial_assets"], 35.0, "20 + 5*10 - 5*5 - 10")
    close(result["year5_equity_per_share"], 13.0, "(100 + 35 - 5) / 10")
    assert [row["dps"] for row in result["rows"][:5]] == [0.5]*5
    assert all(row["reserve_add"] == 0.0 for row in result["rows"])
    c_rate = copy.deepcopy(c)
    c_rate["discount_rate"] = 0.2
    close(evaluate(f, c_rate)["current_value_per_share"], 5.5, "(10/20% + 5) / 10")

    f_wc = copy.deepcopy(f)
    f_wc["inventory"] = 20.0
    c_wc = copy.deepcopy(c)
    c_wc.update(growth=[0.1]*10, trade_wc_ratio=[0.2]*10, tax_rate=0.2,
                capex_ratio=0.03, nonlease_da_ratio=0.01)
    wc = evaluate(f_wc, c_wc)
    close(wc["rows"][0]["group_fcff"], 4.6, "8.8 + 1.1 - 3.3 - 2")
    c_wc["nci_fraction"] = 0.5
    close(evaluate(f_wc, c_wc)["rows"][0]["common_fcff"], 2.3, "4.6 * 50% common")

    c_convert = copy.deepcopy(c)
    c_convert.update(cb_mode="convert", payout=0.0)
    converted = evaluate(f, c_convert)
    close(converted["rows"][4]["shares"], 12.0, "10 + 10/5 conversion")
    close(converted["rows"][4]["liquid_financial_assets"], 70.0, "20 + 5*10; no principal payment")
    assert converted["rows"][4]["cb_cash_redemption"] == 0.0
    assert converted["rows"][4]["cb_remaining"] == 0.0

    c_award = copy.deepcopy(c)
    c_award.update(legacy_award_shares=[1.0]+[0.0]*9, legacy_award_subscription_price=2.0)
    award = evaluate(f, c_award)
    close(award["rows"][0]["shares"], 11.0, "legacy award shares")
    close(award["rows"][0]["subscription_cash"], 2.0, "legacy subscription cash")
    close(award["rows"][0]["reserve_add"], 0.5, "reserve catch-up only")
    c_clamp = copy.deepcopy(c)
    c_clamp.update(parent_available_financial_assets=0.0, parent_own_cash_conversion=0.0,
                   cb_mode="convert")
    clamped = evaluate(f, c_clamp)
    assert clamped["rows"][0]["distribution"] == 0.0
    assert clamped["rows"][0]["distribution_clipped"]

    # A real funding gap must survive into the next year. No zero-clamping,
    # retrospective rescue from future profits, or invented loan is allowed.
    f_unfunded = copy.deepcopy(f)
    f_unfunded.update(cash=0.0, short_bank_debt=0.0, cb_face=0.0, cb_carrying=0.0)
    c_unfunded = copy.deepcopy(c)
    c_unfunded.update(trade_wc_ratio=[0.2]*10,
                      parent_available_financial_assets=0.0,
                      parent_own_cash_conversion=0.0)
    unfunded = evaluate(f_unfunded, c_unfunded)
    close(unfunded["rows"][0]["common_fcff"], -10.0, "10 NOPAT minus 20 new WC")
    close(unfunded["rows"][0]["liquid_financial_assets"], -10.0, "negative cash retained")
    close(unfunded["rows"][0]["group_liquidity_shortfall"], 10.0, "unfunded year1 gap")
    close(unfunded["rows"][1]["common_fcff"], 10.0, "year2 no new WC")
    close(unfunded["rows"][1]["liquid_financial_assets"], 0.0, "negative10 carried plus10, not plus20")
    assert all(row["distribution"] == 0.0 for row in unfunded["rows"])
    assert all(row["bank_debt"] == 0.0 and row["cb_remaining"] == 0.0 for row in unfunded["rows"])
    assert not unfunded["feasible_without_new_unbudgeted_funding"]
    assert all(unfunded[key] is None for key in (
        "current_value_per_share", "auxiliary_value_per_share", "year5_equity_per_share"))

    # The same negative FCFF, when covered by existing resources, is allowed.
    # A negative operating year alone is not insolvency and must not force null.
    f_funded = copy.deepcopy(f_unfunded)
    f_funded["cash"] = 20.0
    funded = evaluate(f_funded, c_unfunded)
    close(funded["rows"][0]["common_fcff"], -10.0, "identical negative FCFF with funding")
    close(funded["rows"][0]["liquid_financial_assets"], 10.0, "20 existing cash minus10")
    close(funded["rows"][1]["liquid_financial_assets"], 20.0, "10 carried plus10")
    assert funded["feasible_without_new_unbudgeted_funding"]
    assert all(funded[key] is not None for key in (
        "current_value_per_share", "auxiliary_value_per_share", "year5_equity_per_share"))

    # These new same-chain tests are defined, not executed, until admission.
    c_social_cost = copy.deepcopy(c)
    c_social_cost["ongoing_social_cost_ratio"] = 0.01
    social_cost = evaluate(f, c_social_cost)
    close(social_cost["rows"][0]["recurring_social_cost"], 1.0, "100 revenue * 1% cost")
    close(social_cost["rows"][0]["common_fcff"], 9.0, "10 profit less1 recurring cost")
    close(social_cost["current_operating_value"]["value"], 90.0, "9 / 10%, including terminal cost")
    close(social_cost["current_value_per_share"], 9.5, "(90 + 20 - 5 - 10) / 10")
    c_social_legacy = copy.deepcopy(c)
    c_social_legacy.update(legacy_social_cash=[2.0]+[0.0]*9,
                           legacy_social_parent_retained_debit=2.0)
    social_legacy = evaluate(f, c_social_legacy)
    close(social_legacy["current_operating_value"]["value"], 100.0, "legacy cash leaves recurring EBIT intact")
    close(social_legacy["historical_social_settlement_pv"], 2.0/1.1, "single Y1 settlement PV")
    close(social_legacy["current_value_per_share"], 10.5-2.0/1.1/10.0, "one historical PV, not two")
    close(social_legacy["auxiliary_value_per_share"], result["auxiliary_value_per_share"]-2.0/1.1/10.0,
          "same historical PV in auxiliary")
    close(social_legacy["rows"][0]["liquid_financial_assets"], 23.0, "20+10-5-2 group cash")
    close(social_legacy["rows"][0]["parent_liquid"], 23.0, "same mother payment, not group twice")
    close(social_legacy["opening"]["parent_retained"], 98.0, "100 less2 legal budget reserve")
    close(social_legacy["rows"][0]["parent_retained"], 103.0, "98+10-5, no second expense")
    close(social_legacy["rows"][4]["liquid_financial_assets"], 33.0, "35 less2 settled cash")
    close(social_legacy["year5_equity_per_share"], 12.8, "(100+33-5)/10, no residual settled claim")
    assert all(row["legacy_social_cash"] == 0.0 for row in social_legacy["rows"][1:])
    c_social_unfunded = copy.deepcopy(c)
    c_social_unfunded.update(legacy_social_cash=[40.0]+[0.0]*9,
                             legacy_social_parent_retained_debit=40.0)
    social_unfunded = evaluate(f, c_social_unfunded)
    close(social_unfunded["rows"][0]["liquid_financial_assets"], -10.0, "20+10-40, no rescue loan")
    close(social_unfunded["rows"][1]["liquid_financial_assets"], 0.0, "legacy gap persists into Y2")
    assert not social_unfunded["feasible_without_new_unbudgeted_funding"]
    assert all(social_unfunded[key] is None for key in (
        "current_value_per_share", "auxiliary_value_per_share", "year5_equity_per_share"))
    return {"status":"passed", "same_chain":"evaluate -> project -> operating_year / enterprise_value_at",
            "hand_cases":["constant perpetuity", "rate change", "working capital and NCI",
                          "conversion", "legacy award and reserve", "mother cash distribution clamp",
                          "negative cash carried with infeasible/null", "funded negative FCFF permitted",
                          "recurring social cost includes terminal", "historical social cash no double charge",
                          "unfunded historical cash remains negative and null"]}
