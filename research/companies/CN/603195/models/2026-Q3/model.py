'Bull 603195 ordinary offline model. All money is CNY; fiscal-year cash is uniform within each year. No coordinator permission ticket is required.'
import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


def statutory_transfer(profit, reserve, capital, cfg):
    raw = max(0.0, profit) * cfg["reserve_rate"]
    if cfg["statutory_policy"] == "unlimited_10pct_stress":
        return raw
    gap = max(0.0, capital * cfg["registered_capital_fraction"] - reserve)
    return min(raw, gap)


def operating_nwc(facts, cfg):
    return (facts["receivables_sep"] + facts["inventory_sep"] + facts["prepayments_sep"]
            - (facts["total_ap_sep"] - cfg["capital_ap_sep_proxy"])
            - facts["contract_liability_sep"])


def financial_bridge(facts, cfg, redemption=0.0):
    bridge = dict(cash=facts["cash_sep"], trading_assets=facts["trading_assets_sep"],
                  diagnostic_asset_loss=facts["trading_assets_sep"]*cfg["trading_asset_loss_fraction"],
                  financial_debt=facts["short_debt_sep"]+facts["long_debt_sep"],
                  leases=facts["lease_liability_sep"], capital_ap_proxy=cfg["capital_ap_sep_proxy"],
                  minimum_operating_cash=cfg["minimum_group_cash"],
                  labelled_proforma_redemption=redemption)
    nfa = (bridge["cash"]+bridge["trading_assets"]-bridge["diagnostic_asset_loss"]
           -bridge["financial_debt"]-bridge["leases"]-bridge["capital_ap_proxy"]
           -bridge["minimum_operating_cash"]-redemption)
    return bridge, nfa


def settle_existing_capital_ap(facts, cfg, redemption=0.0):
    """Actual bridge/NWC chain: settlement changes gross cash, total AP and its capital part."""
    amount = cfg["capital_ap_sep_proxy"]
    paid_facts, paid_cfg = dict(facts), dict(cfg)
    paid_facts["cash_sep"] -= amount
    paid_facts["total_ap_sep"] -= amount
    paid_cfg["capital_ap_sep_proxy"] = 0.0
    _, before = financial_bridge(facts, cfg, redemption)
    _, after = financial_bridge(paid_facts, paid_cfg, redemption)
    nwc_before, nwc_after = operating_nwc(facts, cfg), operating_nwc(paid_facts, paid_cfg)
    return dict(assumed_year=2027, gross_cash_reduction=amount, liability_reduction=amount,
                before_net_wealth=before, after_net_wealth=after, net_wealth_change=after-before,
                before_operating_nwc=nwc_before, after_operating_nwc=nwc_after,
                operating_nwc_change=nwc_after-nwc_before,
                note="Historical snapshot settlement equivalence; 2027 net effect enters the actual cash step.")


def equity_from_state(operating_ev, nfa, common, shares):
    total = operating_ev+nfa
    return dict(group_equity_value=total, common_equity_value=common*total,
                minority_equity_value=(1-common)*total, per_share=common*total/shares)


def operations(facts, cfg):
    """Old capital AP is excluded from NWC and from new cash capex, exactly once."""
    n0 = operating_nwc(facts, cfg)
    annual_revenue = facts["revenue_9m_2026"] + cfg["q4_2026_revenue"]
    n1 = annual_revenue * cfg["q4_nwc_ratio"]
    ebit = cfg["q4_2026_revenue"] * (cfg["q4_proxy_ebit_margin"] - cfg["normal_loss_ratio"])
    nopat = ebit * (1.0 - cfg["tax_rate"])
    capex, da = cfg["capex_new_2027"] / 4.0, cfg["da_2027"] / 4.0
    reinv = capex - da + n1 - n0
    rows = {2026: dict(year=2026, start=2026.75, end=2027.0,
                       revenue=cfg["q4_2026_revenue"], annual_revenue=annual_revenue,
                       proxy_margin=cfg["q4_proxy_ebit_margin"], ebit=ebit, nopat=nopat,
                       da=da, capex_new=capex, nwc_start=n0, nwc_end=n1,
                       nwc_change=n1-n0, reinvestment=reinv, fcff=nopat-reinv,
                       required_operating_cash=cfg["minimum_group_cash"], operating_cash_increase=0.0,
                       transition_weight=0.0)}
    previous_revenue, previous_nwc = annual_revenue, n1
    previous_required_cash = cfg["minimum_group_cash"]
    for year in range(2027, 2038):
        if year <= 2031:
            idx, weight = year - 2027, 0.0
            growth = cfg["growth_2027_2031"][idx]
            margin = cfg["proxy_margin_2027_2031"][idx]
            nwc_ratio = cfg["nwc_ratio_2027_2031"][idx]
        else:
            weight = min(1.0, (year - 2031) / 5.0)
            growth = cfg["growth_2027_2031"][-1] * (1-weight) + cfg["terminal_growth"] * weight
            margin = cfg["proxy_margin_2027_2031"][-1] * (1-weight) + cfg["terminal_proxy_margin"] * weight
            nwc_ratio = cfg["nwc_ratio_2027_2031"][-1] * (1-weight) + cfg["terminal_nwc_ratio"] * weight
        revenue = previous_revenue * (1.0 + growth)
        ebit = revenue * (margin - cfg["normal_loss_ratio"])
        nopat = ebit * (1.0 - cfg["tax_rate"])
        da = cfg["da_2027"] * (1.0 + cfg["capital_cost_inflation"]) ** (year-2027)
        capex_raw = cfg["capex_new_2027"] * (1.0 + cfg["capital_cost_inflation"]) ** (year-2027)
        nwc_end = revenue * nwc_ratio
        dnwc = nwc_end - previous_nwc
        required_cash = cfg["minimum_group_cash"] * revenue / annual_revenue
        cash_increase = required_cash - previous_required_cash
        raw_reinvestment = capex_raw - da + dnwc + cash_increase
        target_reinvestment = nopat * max(0.0, growth) / cfg["terminal_incremental_roic"]
        reinvestment = raw_reinvestment * (1-weight) + target_reinvestment * weight
        capex = reinvestment + da - dnwc - cash_increase
        rows[year] = dict(year=year, start=float(year), end=float(year+1),
                          revenue=revenue, annual_revenue=revenue, growth=growth,
                          proxy_margin=margin, ebit=ebit, nopat=nopat, da=da,
                          capex_new=capex, capex_pre_transition=capex_raw,
                          nwc_start=previous_nwc, nwc_end=nwc_end, nwc_change=dnwc,
                          required_operating_cash=required_cash, operating_cash_increase=cash_increase,
                          reinvestment=reinvestment, fcff=nopat-reinvestment,
                          transition_weight=weight)
        previous_revenue, previous_nwc = revenue, nwc_end
        previous_required_cash = required_cash
    return rows


def operating_value(rows, asof, rate, terminal_growth):
    """Same date convention for current and independently dated Y3/Y5 values."""
    if rate <= terminal_growth:
        raise ValueError("Discount rate must exceed terminal growth")
    pv = 0.0
    for year in range(2026, 2037):
        row = rows[year]
        left, end = max(asof, row["start"]), row["end"]
        if left >= end:
            continue
        amount = row["fcff"] * (end-left) / (row["end"]-row["start"])
        midpoint = (left+end)/2.0
        pv += amount / (1.0+rate) ** (midpoint-asof)
    # Cash remains mid-year in perpetuity; sqrt term avoids a timing jump at terminal.
    terminal = rows[2037]["fcff"] * math.sqrt(1.0+rate) / (rate-terminal_growth)
    terminal_pv = terminal / (1.0+rate) ** (2037.0-asof)
    return dict(operating_ev=pv+terminal_pv, explicit_pv=pv,
                terminal_pv=terminal_pv, terminal_share=terminal_pv/(pv+terminal_pv))


def declaration(year, subs_profit, subs_cash, cfg):
    if cfg["subsidiary_declaration_policy"] == "historical":
        desired = cfg["historical_subsidiary_declaration"] * 1.02 ** (year-2026)
    else:
        desired = max(0.0, subs_profit) * cfg["subsidiary_profit_declaration_share"]
    # Prudential assumption on current cash, not a legal maximum on accumulated profits.
    return min(desired, max(0.0, subs_cash))


def annual_cash_step(year, state, flows, cfg, common, shares, capital, parent_required_cash):
    """The one production payment/state transition, also used by constrained hand cases."""
    opening = state["nfa"]
    parent_opening, retained_opening = state["parent_cash"], state["parent_retained"]
    reserve_opening = state["reserve"]
    internal = cfg["parent_internal_settlement_2027"] if year == 2027 else 0.0
    settlement = flows.get("capital_ap_net_effect", 0.0)
    generated = flows["fcff"]+flows["financial_income"]
    parent_pre = parent_opening+0.5*flows["parent_own_cash"]+flows["received"]-internal
    group_pre = opening+settlement+0.5*generated
    target = max(0.0, state["previous_common_ni"])*cfg["payout_target"]
    caps = dict(target=target, prior_parent_profit=max(0.0,retained_opening),
                parent_cash=max(0.0,parent_pre-parent_required_cash),
                group_cash=max(0.0,group_pre-cfg["financial_asset_liquidity_holdback"])*common)
    dividend = min(caps.values())
    total_distribution = dividend/common
    nfa = opening+settlement+generated-total_distribution
    parent_cash = parent_opening+flows["parent_own_cash"]+flows["received"]-internal-dividend
    parent_profit = flows["parent_own_profit"]+flows["declared"]
    transfer = statutory_transfer(parent_profit,reserve_opening,capital,cfg)
    reserve = reserve_opening+transfer
    retained = retained_opening-dividend+parent_profit-transfer
    october_nfa = opening+settlement+(10.0/12.0)*generated-total_distribution
    record = dict(year=year,opening_nfa=opening,financial_income=flows["financial_income"],
                  fcff=flows["fcff"],capital_ap_net_effect=settlement,
                  common_net_income=flows["common_ni"],common_dividend_target=target,
                  common_dividend=dividend,dividend_per_share=dividend/shares,
                  total_distribution=total_distribution,minority_distribution=total_distribution-dividend,
                  constraint_caps=caps,group_cash_pre_distribution=group_pre,
                  group_cash_post_distribution=group_pre-total_distribution,
                  end_nfa=nfa,october_nfa=october_nfa,parent_opening_cash=parent_opening,
                  parent_opening_retained=retained_opening,parent_own_profit=flows["parent_own_profit"],
                  new_subs_declared=flows["declared"],subs_cash_capacity=flows["subs_cash_capacity"],
                  new_subs_cash_received=flows["received"],parent_own_cash=flows["parent_own_cash"],
                  parent_internal_settlement=internal,parent_cash_pre_distribution=parent_pre,
                  parent_cash_post_distribution=parent_pre-dividend,parent_cash_end=parent_cash,
                  parent_retained_end=retained,parent_required_cash=parent_required_cash,
                  statutory_reserve_opening=reserve_opening,statutory_transfer=transfer,
                  statutory_reserve_end=reserve,group_buffer_gap=max(0.0,-nfa,-(group_pre-total_distribution)),
                  parent_buffer_gap=max(0.0,parent_required_cash-parent_cash,parent_required_cash-(parent_pre-dividend)))
    new_state = dict(nfa=nfa,parent_cash=parent_cash,parent_retained=retained,reserve=reserve,
                     previous_common_ni=flows["common_ni"])
    return new_state,record


def evaluate(name, facts, cfg, event_sink=None):
    rows = operations(facts, cfg)
    common = 1.0-cfg["minority_economic_share"]
    shares = facts["shares_sep"]
    redemption = 0.0
    if cfg["proposed_cancellation_proforma"]:
        shares -= facts["proposed_cancellation_shares"]
        redemption = facts["proposed_cancellation_cash"]
    capital = float(shares)  # RMB1 nominal; only implemented or labelled proforma changes.
    bridge,nfa_sep = financial_bridge(facts,cfg,redemption)
    capital_settlement = settle_existing_capital_ap(facts,cfg,redemption)
    q4_finance = max(0.0, nfa_sep)*cfg["net_financial_return_after_tax"]/4.0
    q4_total_cash = rows[2026]["fcff"]+q4_finance
    nfa_asof = nfa_sep+q4_total_cash/3.0  # October forecast only; remaining 2/3 is after cutoff.
    nfa = nfa_sep+q4_total_cash
    common_ni_2026 = facts["common_net_income_9m_2026"] + common*(rows[2026]["nopat"]+q4_finance)
    own_2026 = cfg["parent_own_income_share"]*common_ni_2026
    subs_2026 = common_ni_2026-own_2026
    declared = {2026: declaration(2026, subs_2026, subs_2026*cfg["parent_seed_subs_cash_conversion"], cfg)}
    parent_full_profit = own_2026+declared[2026]
    reserve = facts["statutory_reserve"]
    transfer = statutory_transfer(parent_full_profit, reserve, capital, cfg)
    reserve += transfer
    h2_own = own_2026-facts["parent_own_net_income_h1"]
    parent_retained = facts["parent_retained_h1"]+h2_own+declared[2026]-transfer
    parent_cash = (facts["parent_cash_and_trading_h1"] + cfg["parent_opening_cash_adjustment"]
                   +h2_own*cfg["parent_h2_cash_conversion"]
                   +facts["parent_old_dividend_receivable_h1"]-redemption)
    seed = dict(common_ni_2026=common_ni_2026, parent_own_full_2026=own_2026,
                parent_own_h2_2026=h2_own, new_subs_declared_2026=declared[2026],
                old_dividend_cash_not_profit=facts["parent_old_dividend_receivable_h1"],
                statutory_transfer_2026=transfer, parent_retained_end_2026=parent_retained,
                parent_cash_end_2026=parent_cash, statutory_reserve_end_2026=reserve,
                q4_financial_income=q4_finance, q4_fcff=rows[2026]["fcff"],nfa_end_2026=nfa)
    state = dict(nfa=nfa,parent_cash=parent_cash,parent_retained=parent_retained,reserve=reserve,
                 previous_common_ni=common_ni_2026)
    cash_rows = []
    for year in range(2027, 2038):
        row, opening = rows[year], state["nfa"]
        financial_income = max(0.0, opening)*cfg["net_financial_return_after_tax"]
        common_ni = (row["nopat"]+financial_income)*common
        common_cash_generated = (row["fcff"]+financial_income)*common
        own_profit = cfg["parent_own_income_share"]*common_ni
        own_cash = cfg["parent_own_income_share"]*common_cash_generated
        subs_profit = common_ni-own_profit
        subs_cash = common_cash_generated-own_cash
        declared[year] = declaration(year, subs_profit, subs_cash, cfg)
        receipt_year = year-cfg["subsidiary_cash_receipt_lag_years"]
        received = declared.get(receipt_year, 0.0)
        parent_required_cash = cfg["parent_minimum_cash"] * row["annual_revenue"] / rows[2026]["annual_revenue"]
        flows = dict(fcff=row["fcff"],financial_income=financial_income,common_ni=common_ni,
                     parent_own_profit=own_profit,parent_own_cash=own_cash,declared=declared[year],
                     received=received,subs_cash_capacity=max(0.0,subs_cash),
                     capital_ap_net_effect=capital_settlement["net_wealth_change"] if year==2027 else 0.0)
        state,record = annual_cash_step(year,state,flows,cfg,common,shares,capital,parent_required_cash)
        cash_rows.append(record)
        if event_sink:
            event_sink(dict(event="annual_cash_record",scenario=name,record=record))
    current = operating_value(rows, 2026.0+10.0/12.0, cfg["discount_rate"], cfg["terminal_growth"])
    current.update(equity_from_state(current["operating_ev"],nfa_asof,common,shares))
    # Auxiliary method: a separate normal-profit/maintenance calculation, no DCF output reuse.
    norm_ebit = rows[2026]["annual_revenue"]*(cfg["cross_normal_proxy_margin"]-cfg["normal_loss_ratio"])
    norm_nopat = norm_ebit*(1-cfg["tax_rate"])
    owner_earnings = norm_nopat+cfg["da_2027"]-cfg["cross_maintenance_cash"]
    cross_g = cfg["cross_growth"]
    cross_fcf = owner_earnings*(1+cross_g)*(1-cross_g/cfg["cross_incremental_roic"])
    cross_ev = cross_fcf*math.sqrt(1+cfg["discount_rate"])/(cfg["discount_rate"]-cross_g)
    cross = dict(normal_nopat=norm_nopat, maintenance_cash=cfg["cross_maintenance_cash"],
                 owner_earnings=owner_earnings, sustainable_next_cash=cross_fcf, operating_ev=cross_ev,
                 **equity_from_state(cross_ev,nfa_asof,common,shares))
    endpoints = {}
    for horizon, year in ((3,2029),(5,2031)):
        state = next(x for x in cash_rows if x["year"] == year)
        values = []
        for rate in cfg["terminal_return_rates"]:
            ev = operating_value(rows, year+10.0/12.0, rate, cfg["terminal_growth"])["operating_ev"]
            values.append(equity_from_state(ev,state["october_nfa"],common,shares)["per_share"])
        endpoints[f"year_{horizon}"] = dict(date=f"{year}-10-31", net_financial_wealth=state["october_nfa"],
                                           low=min(values), high=max(values))
    first_five = cash_rows[:5]
    jumps = dict(y5_y6_fcff_ratio=rows[2032]["fcff"]/rows[2031]["fcff"],
                 y5_y6_capex_ratio=rows[2032]["capex_new"]/rows[2031]["capex_new"],
                 y5_y6_dividend_ratio=(cash_rows[5]["common_dividend"]/cash_rows[4]["common_dividend"]
                                        if cash_rows[4]["common_dividend"] else None),
                 terminal_reinvestment_ratio=rows[2037]["reinvestment"]/rows[2037]["nopat"])
    return dict(name=name, assumptions=cfg, shares=shares, equity_bridge=bridge,
                opening_nfa_sep=nfa_sep, estimated_nfa_asof=nfa_asof,
                source_capex_inconsistency_isolated=True,
                capital_ap_settlement=capital_settlement,
                parent_seed=seed, operations=list(rows.values()), cash= cash_rows,
                main=current, cross=cross, method_midpoint_gap_fraction=cross["per_share"]/current["per_share"]-1,
                forward_distributions_per_share=[x["dividend_per_share"] for x in first_five],
                terminal_equity_ranges=endpoints, transition_diagnostics=jumps,
                distribution_shortfall_years=[x["year"] for x in cash_rows if x["common_dividend"]+0.01<x["common_dividend_target"]],
                research_cash_gap_years=[x["year"] for x in cash_rows if x["group_buffer_gap"]>0.01 or x["parent_buffer_gap"]>0.01],
                return_path_feasible=not any(x["group_buffer_gap"]>0.01 or x["parent_buffer_gap"]>0.01 for x in cash_rows),
                negative_funding_note="If a buffer gap occurs, subsequent arithmetic is diagnostic only: no financing terms are supplied and no zero-cost credit is assumed.",
                diagnostic_scope_notes=["The constant 2bn holdback is persistent modeled unavailability, not a dated maturity/release forecast.",
                                        "5%/10% financial losses are asset-bridge diagnostics, not complete parent/subsidiary legal-profit credit-event tests.",
                                        "Capital AP range changes both debt classification and opening operating NWC, not debt alone.",
                                        "Reported 8,916,080 CNY derivative liability is treated as operating hedge settlement within the net-input-cost budget; its opening cash timing is not separately resolved and is a small precision limit, not a zero liability."],
                below_maintenance_reference_years=[y for y in range(2027,2038) if rows[y]["capex_new"] < cfg["cross_maintenance_cash"]*(1+cfg["capital_cost_inflation"])**(y-2027)])


def assert_close(label, actual, expected):
    if not (math.isfinite(actual) and math.isfinite(expected)):
        raise AssertionError(f"{label}: nonfinite {actual}, {expected}")
    if not math.isclose(actual,expected,rel_tol=1e-12,abs_tol=0.005):
        raise AssertionError(f"{label}: actual={actual!r} expected={expected!r}")
    return abs(actual-expected)


def verify_production_result(result, facts, cfg):
    """Independent cumulative balance reconciliation of the actually returned records."""
    errors=[]
    def check(label,a,b):
        errors.append(assert_close(result["name"]+":"+label,a,b))
    common=1-cfg["minority_economic_share"]
    shares=result["shares"]
    seed=result["parent_seed"]
    operations_by_year={row["year"]:row for row in result["operations"]}
    q4_flow=seed["q4_fcff"]+seed["q4_financial_income"]
    check("October stub",result["estimated_nfa_asof"],result["opening_nfa_sep"]+q4_flow/3)
    check("December stub",seed["nfa_end_2026"],result["estimated_nfa_asof"]+2*q4_flow/3)
    redemption=result["equity_bridge"]["labelled_proforma_redemption"]
    check("mother seed cash",seed["parent_cash_end_2026"],facts["parent_cash_and_trading_h1"]
          +cfg["parent_opening_cash_adjustment"]+seed["parent_own_h2_2026"]*cfg["parent_h2_cash_conversion"]
          +facts["parent_old_dividend_receivable_h1"]-redemption)
    check("mother seed retained",seed["parent_retained_end_2026"],facts["parent_retained_h1"]
          +seed["parent_own_h2_2026"]+seed["new_subs_declared_2026"]-seed["statutory_transfer_2026"])
    check("mother seed reserve",seed["statutory_reserve_end_2026"],facts["statutory_reserve"]+seed["statutory_transfer_2026"])
    check("capital AP net settlement",result["capital_ap_settlement"]["net_wealth_change"],0.0)
    check("capital AP not operating release",result["capital_ap_settlement"]["operating_nwc_change"],0.0)
    group=seed["nfa_end_2026"]
    mother_cash=seed["parent_cash_end_2026"]
    retained=seed["parent_retained_end_2026"]
    reserve=seed["statutory_reserve_end_2026"]
    prior_income=seed["common_ni_2026"]
    cumulative_group_cash=cumulative_dividends=cumulative_capital=0.0
    cumulative_parent_cash=cumulative_parent_profit=cumulative_common_d=cumulative_reserve=0.0
    cumulative_nopat_fin=0.0
    declarations={2026:seed["new_subs_declared_2026"]}
    for record in result["cash"]:
        year=record["year"]
        op=operations_by_year[year]
        reinvest=op["capex_new"]-op["da"]+op["nwc_change"]+op["operating_cash_increase"]
        check(f"{year} operating investment",op["reinvestment"],reinvest)
        check(f"{year} FCFF",record["fcff"],op["nopat"]-reinvest)
        check(f"{year} opening group",record["opening_nfa"],group)
        check(f"{year} opening mother cash",record["parent_opening_cash"],mother_cash)
        check(f"{year} opening retained",record["parent_opening_retained"],retained)
        check(f"{year} opening reserve",record["statutory_reserve_opening"],reserve)
        check(f"{year} ordinary/minority sum",record["total_distribution"],record["common_dividend"]+record["minority_distribution"])
        check(f"{year} ordinary share",record["common_dividend"],record["total_distribution"]*common)
        check(f"{year} per-share D",record["dividend_per_share"]*shares,record["common_dividend"])
        check(f"{year} dividend target",record["common_dividend_target"],max(0,prior_income)*cfg["payout_target"])
        expected_receipt=declarations.get(year-cfg["subsidiary_cash_receipt_lag_years"],0.0)
        check(f"{year} declaration receipt lag",record["new_subs_cash_received"],expected_receipt)
        declarations[year]=record["new_subs_declared"]
        generated=op["nopat"]-reinvest+record["financial_income"]
        effect=record["capital_ap_net_effect"]
        mother_pre=mother_cash+0.5*record["parent_own_cash"]+expected_receipt-record["parent_internal_settlement"]
        group_pre=group+effect+0.5*generated
        independent_caps=[max(0,prior_income)*cfg["payout_target"],max(0,retained),
                          max(0,mother_pre-record["parent_required_cash"]),
                          max(0,group_pre-cfg["financial_asset_liquidity_holdback"])*common]
        if record["common_dividend"] < -0.005:
            raise AssertionError(f"{year}: negative distribution")
        check(f"{year} payment constraint",record["common_dividend"],min(independent_caps))
        check(f"{year} mother pre payment",record["parent_cash_pre_distribution"],mother_pre)
        check(f"{year} mother post payment",record["parent_cash_post_distribution"],mother_pre-record["common_dividend"])
        check(f"{year} group post payment",record["group_cash_post_distribution"],group_pre-record["total_distribution"])
        parent_profit=record["parent_own_profit"]+record["new_subs_declared"]
        expected_reserve=max(0,parent_profit)*cfg["reserve_rate"]
        if cfg["statutory_policy"]!="unlimited_10pct_stress":
            expected_reserve=min(expected_reserve,max(0,shares*cfg["registered_capital_fraction"]-reserve))
        check(f"{year} reserve rule",record["statutory_transfer"],expected_reserve)
        cumulative_group_cash+=generated+effect
        cumulative_dividends+=record["common_dividend"]+record["minority_distribution"]
        cumulative_capital+=reinvest
        cumulative_nopat_fin+=op["nopat"]+record["financial_income"]+effect
        cumulative_parent_cash+=record["parent_own_cash"]+expected_receipt-record["parent_internal_settlement"]
        cumulative_parent_profit+=parent_profit
        cumulative_common_d+=record["common_dividend"]
        cumulative_reserve+=record["statutory_transfer"]
        group=seed["nfa_end_2026"]+cumulative_group_cash-cumulative_dividends
        mother_cash=seed["parent_cash_end_2026"]+cumulative_parent_cash-cumulative_common_d
        retained=seed["parent_retained_end_2026"]+cumulative_parent_profit-cumulative_reserve-cumulative_common_d
        reserve=seed["statutory_reserve_end_2026"]+cumulative_reserve
        check(f"{year} cumulative group wealth",record["end_nfa"],group)
        check(f"{year} profit-capital-cash conservation",record["end_nfa"]+cumulative_capital,
              seed["nfa_end_2026"]+cumulative_nopat_fin-cumulative_dividends)
        check(f"{year} cumulative mother cash",record["parent_cash_end"],mother_cash)
        check(f"{year} cumulative mother retained",record["parent_retained_end"],retained)
        check(f"{year} cumulative reserve",record["statutory_reserve_end"],reserve)
        check(f"{year} group buffer flag",record["group_buffer_gap"],max(0,-group,-record["group_cash_post_distribution"]))
        check(f"{year} mother buffer flag",record["parent_buffer_gap"],max(0,record["parent_required_cash"]-mother_cash,
              record["parent_required_cash"]-record["parent_cash_post_distribution"]))
        check(f"{year} mother retained plus reserve",record["parent_retained_end"]+record["statutory_reserve_end"],
              seed["parent_retained_end_2026"]+seed["statutory_reserve_end_2026"]+cumulative_parent_profit-cumulative_common_d)
        check(f"{year} October to December",record["end_nfa"]-record["october_nfa"],generated*2/12)
        prior_income=record["common_net_income"]
    for method in ("main","cross"):
        value=result[method]
        check(method+" group equity",value["group_equity_value"],value["operating_ev"]+result["estimated_nfa_asof"])
        check(method+" ownership conservation",value["common_equity_value"]+value["minority_equity_value"],value["group_equity_value"])
        check(method+" per share",value["per_share"]*shares,value["common_equity_value"])
    if [row["year"] for row in result["cash"][:5]]!=[2027,2028,2029,2030,2031]:
        raise AssertionError("Wrong five distribution periods")
    for horizon,year in ((3,2029),(5,2031)):
        endpoint=result["terminal_equity_ranges"][f"year_{horizon}"]
        row=next(x for x in result["cash"] if x["year"]==year)
        check(f"Y{horizon} paid-D endpoint wealth",endpoint["net_financial_wealth"],row["october_nfa"])
    return dict(status="PRODUCTION_BALANCES_RECONCILED",comparison_count=len(errors),
                max_absolute_roundoff=max(errors),meaning="Arithmetic/state consistency only, not economic forecast accuracy")


def formal_kernel_cases():
    """Only evaluated by an authorized run; small hand-solvable cases, not a forecast confidence claim."""
    rate, cash = 0.10, 100.0
    flat = {y:dict(start=float(y),end=float(y+1),fcff=cash) for y in range(2026,2038)}
    observed = operating_value(flat,2027.0,rate,0.0)["operating_ev"]
    expected = cash*math.sqrt(1+rate)/rate
    if abs(observed-expected)>1e-8:
        raise AssertionError("Flat perpetuity/midyear timing mismatch")
    cfg = dict(reserve_rate=0.10, statutory_policy="cap_at_half_registered_capital", registered_capital_fraction=0.50)
    transfer = statutory_transfer(100.0,49.0,100.0,cfg)
    if transfer != 1.0 or statutory_transfer(100.0,50.0,100.0,cfg) != 0.0:
        raise AssertionError("Statutory cap logic")
    ap_facts=dict(cash_sep=100.0,trading_assets_sep=0.0,short_debt_sep=0.0,long_debt_sep=0.0,
                  lease_liability_sep=0.0,receivables_sep=0.0,inventory_sep=0.0,prepayments_sep=0.0,
                  total_ap_sep=30.0,contract_liability_sep=0.0)
    ap_cfg=dict(capital_ap_sep_proxy=20.0,minimum_group_cash=0.0,trading_asset_loss_fraction=0.0)
    settlement=settle_existing_capital_ap(ap_facts,ap_cfg)
    assert_close("formal AP before wealth",settlement["before_net_wealth"],80.0)
    assert_close("formal AP after wealth",settlement["after_net_wealth"],80.0)
    assert_close("formal AP before operating NWC",settlement["before_operating_nwc"],-10.0)
    assert_close("formal AP after operating NWC",settlement["after_operating_nwc"],-10.0)
    cfg.update(parent_internal_settlement_2027=0.0,payout_target=0.8,financial_asset_liquidity_holdback=0.0)
    state=dict(nfa=settlement["after_net_wealth"],parent_cash=10.0,parent_retained=5.0,reserve=50.0,previous_common_ni=20.0)
    flows=dict(fcff=20.0,financial_income=0.0,common_ni=20.0,parent_own_profit=4.0,
               parent_own_cash=4.0,declared=4.0,received=4.0,subs_cash_capacity=14.0,
               capital_ap_net_effect=settlement["net_wealth_change"])
    constrained,record=annual_cash_step(2027,state,flows,cfg,0.9,100.0,100.0,8.0)
    equity=equity_from_state(0.0,constrained["nfa"],0.9,100.0)
    assert_close("constrained D",record["common_dividend"],5.0)
    assert_close("constrained mother cash",constrained["parent_cash"],13.0)
    assert_close("constrained retained",constrained["parent_retained"],8.0)
    assert_close("unpaid assets remain common equity",equity["common_equity_value"],85.0)
    negative_state=dict(state,nfa=-10.0)
    negative_flows=dict(flows,fcff=-2.0,common_ni=-2.0,parent_own_profit=-0.5,
                        parent_own_cash=0.0,declared=0.0,received=0.0,subs_cash_capacity=0.0)
    negative,negative_record=annual_cash_step(2027,negative_state,negative_flows,cfg,0.9,100.0,100.0,8.0)
    negative_equity=equity_from_state(0.0,negative["nfa"],0.9,100.0)
    assert_close("negative wealth not clipped",negative["nfa"],-12.0)
    assert_close("negative equity not clipped",negative_equity["common_equity_value"],-10.8)
    assert_close("funding gap retained",negative_record["group_buffer_gap"],12.0)
    return dict(flat_perpetuity=dict(actual=observed,hand_formula=expected),
                statutory_cap_transfer=transfer,capital_ap_formal_chain=settlement,
                constrained_production_cash=record,constrained_equity=equity,
                negative_production_cash=negative_record,negative_equity=negative_equity)


def validate_inputs(data):
    if data["identity"]["symbol"] != "CN:603195":
        raise ValueError("Wrong company")
    base = data["base"]
    for key in ("growth_2027_2031","proxy_margin_2027_2031","nwc_ratio_2027_2031"):
        if len(base[key]) != 5:
            raise ValueError(key)
    if not 0.0 <= base["minority_economic_share"] < 1.0:
        raise ValueError("Invalid common equity fraction")
