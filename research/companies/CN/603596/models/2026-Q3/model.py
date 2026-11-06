#!/usr/bin/env python3
"""Bethel minimal owner-attributable model. Public complete author computation.
Money: CNY billion. Shares: count. This file has no import-time model evaluation.
No network, subprocess, third-party packages, or repository state mutation.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback
from datetime import datetime, timezone


class EconomicInfeasibility(Exception):
    def __init__(self, message, snapshot, rows, category):
        super().__init__(message)
        self.snapshot = snapshot
        self.rows = rows
        self.category = category


def close(a, b, label, tol=1e-8):
    if not math.isclose(a, b, abs_tol=tol, rel_tol=tol):
        raise AssertionError(f"{label}: {a!r} != {b!r}")


def finite_tree(x, path="root"):
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError(f"nonfinite {path}")
    if isinstance(x, dict):
        for k, v in x.items():
            finite_tree(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            finite_tree(v, f"{path}[{i}]")


def dump(path, obj):
    finite_tree(obj)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def emit(trace, stage, payload):
    if trace is not None:
        trace(stage, payload)  #IO/program errors deliberately propagate.


def funding_gaps(parent_cash, sub_cash, parent_floor, sub_floor, purpose, payment):
    total=parent_cash+sub_cash
    floor=parent_floor+sub_floor
    return {"parent_payment_gap":max(0.0,parent_floor+purpose+payment-parent_cash),
            "sub_operating_gap":max(0.0,sub_floor-sub_cash),
            "group_usable_payment_gap":max(0.0,floor+purpose+payment-total),
            "group_total_cash_gap":max(0.0,floor+payment-total),
            "group_cash_before_payment":total,"group_operating_floor":floor,
            "purpose_restricted_balance":purpose,"payment_due":payment}


def classify_gap(gaps):
    if gaps["group_total_cash_gap"]>1e-8:
        return "GROUP_TOTAL_FUNDING_GAP"
    if gaps["group_usable_payment_gap"]>1e-8:
        return "GROUP_PURPOSE_RESTRICTED_PAYMENT_GAP"
    return "PARENT_OR_TIMING_ACCESS_GAP"


def validate(c):
    finite_tree(c)
    n = c["explicit_years"]
    if n != 10 or c["holder_years"] != 5:
        raise ValueError("This minimal implementation is pinned to10 explicit/5 holder years")
    if c["operating_discount_rate"] <= c["terminal_growth"]:
        raise ValueError("operating discount must exceed terminal growth")
    j = c["jv"]
    if j["equity_discount_rate"] <= j["terminal_growth"] or j["normalised_roe"] <= j["terminal_growth"]:
        raise ValueError("JV discount/ROE must support terminal retention")
    if c["opening_purpose_restricted_funds"] < 0:
        raise ValueError("negative purpose-restricted funds")
    if c["shares"] <= 0 or not 0 <= c["stub_year_fraction"] < 1:
        raise ValueError("shares/time")
    for key in ["pipeline_growth_capex_owned", "incremental_ppe_ratio", "upstream_payout_rates", "holder_payout_rates"]:
        if len(c[key]) != n:
            raise ValueError(f"bad horizon {key}")
    for b in c["blocks"]:
        if len(b["growth"]) != n or len(b["margin"]) != n:
            raise ValueError("block horizon")
        if not 0 <= b["ownership"] <= 1 or b["revenue_2026_normalized"] < 0:
            raise ValueError("block ownership/revenue")
    if c["bond"]["base_event"] not in {"maturity", "conversion", "put"}:
        raise ValueError("mutually exclusive bond branch required")


def discounted(value, rate, time):
    return value / ((1 + rate) ** time)


def bond_schedule(c):
    """Contractual future cash. Final110% includes final2%, no separate2031 coupon."""
    b = c["bond"]
    if b["face"] == 0 or b["base_event"] == "conversion":
        return []
    first = c["first_forecast_year"]
    stub = c["stub_year_fraction"]
    if b["base_event"] == "put":
        y = b["contingent_put_year"]
        return [{"year": y, "time": stub + y-first + 0.5,
                 "cash": b["face"] * b["contingent_put_factor_including_accrued_interest"],
                 "kind": "conditional_put_face_plus_accrued_included"}]
    out = [{"year": int(y), "time": stub + int(y)-first + 0.5,
            "cash": b["face"] * rate, "kind": "coupon"}
           for y, rate in b["coupon_cash_rates"].items() if int(y) >= first]
    y = b["maturity_year"]
    out.append({"year": y, "time": stub + y-first + 0.5,
                "cash": b["face"] * b["maturity_redemption_factor_including_final_coupon"],
                "kind": "maturity_final_coupon_included"})
    return sorted(out, key=lambda x: x["year"])


def bond_value(c, after_time=0.0):
    return sum(discounted(x["cash"], c["debt_discount_rate"], x["time"] - after_time)
               for x in bond_schedule(c) if x["time"] > after_time)


def projection(c, trace=None):
    """Same operating/capital function is used by production and closed-form fixtures."""
    rev = {b["name"]: b["revenue_2026_normalized"] for b in c["blocks"]}
    owned_rev0 = sum(rev[b["name"]] * b["ownership"] for b in c["blocks"])
    floor = owned_rev0 * c["minimum_cash_ratio"]
    restricted = c["opening_owned_restricted_cash"]
    nwc = c["opening_owned_nwc"]
    productive = c["opening_owned_productive_assets"]
    rows = []
    other = c["other_operating_profit_2026"]
    for idx in range(c["explicit_years"] + 1):
        emit(trace,"operating",{"phase":"period_begin","index":idx,"completed":rows,"revenue_state":rev,"nwc":nwc,"productive_assets":productive})
        stub = idx == 0
        fraction = c["stub_year_fraction"] if stub else 1.0
        year = c["first_forecast_year"] - 1 if stub else c["first_forecast_year"] + idx-1
        detail = []
        for b in c["blocks"]:
            old = rev[b["name"]]
            new = old if stub else old * (1 + b["growth"][idx-1])
            margin = b["stub_margin"] if stub else b["margin"][idx-1]
            detail.append({"name": b["name"], "revenue_100pct": new,
                           "ownership": b["ownership"], "owned_revenue": new*b["ownership"],
                           "owned_ebit": new*margin*b["ownership"]*fraction,
                           "delta_owned_revenue": (new-old)*b["ownership"],
                           "owned_nwc_target": new*b["nwc_ratio"]*b["ownership"]})
            rev[b["name"]] = new
        if not stub:
            other *= 1 + c["other_operating_growth"]
        annual_owned_revenue = sum(x["owned_revenue"] for x in detail)
        ebit = sum(x["owned_ebit"] for x in detail) + other*fraction
        nopat = ebit * (1-c["tax_rate"])
        da = annual_owned_revenue * c["da_rate"] * fraction
        maintenance = da*c["maintenance_da_multiple"]
        generic_growth_capex = 0.0 if stub else sum(max(0, x["delta_owned_revenue"]) for x in detail)*c["incremental_ppe_ratio"][idx-1]
        pipeline = c["stub_pipeline_growth_capex_owned"] if stub else c["pipeline_growth_capex_owned"][idx-1]
        growth_capex = max(generic_growth_capex, pipeline)
        new_nwc = sum(x["owned_nwc_target"] for x in detail)
        new_floor = annual_owned_revenue*c["minimum_cash_ratio"]
        new_restricted = annual_owned_revenue*c["restricted_operating_cash_ratio"]
        if stub and fraction == 0:
            new_nwc, new_floor, new_restricted, growth_capex = nwc, floor, restricted, 0.0
        delta_nwc, delta_floor, delta_restricted = new_nwc-nwc, new_floor-floor, new_restricted-restricted
        capex = maintenance + growth_capex
        # Raw cash excludes a fictitious cash-floor "payment". Restricted cash is an actual transfer out of available pool.
        cash_from_operations_after_capital = nopat + da - capex - delta_nwc - delta_restricted
        fcff = cash_from_operations_after_capital - delta_floor
        productive += capex - da
        row = {"index": idx, "year": year, "is_stub": stub, "year_fraction": fraction,
               "time": c["stub_year_fraction"] + max(0, idx), "blocks": detail,
               "owned_revenue_annual": annual_owned_revenue, "owned_ebit": ebit, "owned_nopat": nopat,
               "da": da, "maintenance_capex": maintenance, "growth_capex": growth_capex,
               "generic_growth_capex": generic_growth_capex, "identified_pipeline_coverage": pipeline,
               "total_capex": capex, "delta_nwc": delta_nwc, "ending_nwc": new_nwc,
               "delta_minimum_cash": delta_floor, "minimum_cash": new_floor,
               "delta_restricted_cash": delta_restricted, "restricted_cash": new_restricted,
               "cash_from_operations_after_capital": cash_from_operations_after_capital,
               "owned_fcff": fcff, "productive_assets": productive, "other_operating_profit": other*fraction}
        emit(trace,"operating",{"phase":"before_assertions","completed":rows,"current":row})
        if productive < -1e-8:
            raise ValueError("negative productive assets: invalid budget")
        rows.append(row)
        nwc, floor, restricted = new_nwc, new_floor, new_restricted
    # One mathematically explicit terminal step, carrying the same terminal costs/capital intensities.
    last = rows[-1]
    g = c["terminal_growth"]
    terminal_rev = last["owned_revenue_annual"]*(1+g)
    terminal_nopat = last["owned_nopat"]*(1+g)
    terminal_da = terminal_rev*c["da_rate"]
    terminal_maintenance = terminal_da*c["maintenance_da_multiple"]
    terminal_growth_capex = last["owned_revenue_annual"]*g*c["incremental_ppe_ratio"][-1]
    terminal_fcff = (terminal_nopat + terminal_da - terminal_maintenance - terminal_growth_capex
                     - last["ending_nwc"]*g - last["minimum_cash"]*g - last["restricted_cash"]*g)
    terminal = {"year": last["year"]+1, "growth": g, "owned_nopat": terminal_nopat,
                "da": terminal_da, "maintenance_capex": terminal_maintenance,
                "growth_capex": terminal_growth_capex, "delta_nwc": last["ending_nwc"]*g,
                "delta_minimum_cash": last["minimum_cash"]*g,
                "delta_restricted_cash": last["restricted_cash"]*g,
                "owned_fcff": terminal_fcff,
                "operating_value_at_end_explicit": terminal_fcff/(c["operating_discount_rate"]-g)}
    return rows, terminal, owned_rev0*c["minimum_cash_ratio"]


def operating_value(rows, terminal, c, after_time=0.0):
    k = c["operating_discount_rate"]
    return (sum(discounted(x["owned_fcff"], k, x["time"]-after_time) for x in rows if x["time"] > after_time)
            + discounted(terminal["operating_value_at_end_explicit"], k, rows[-1]["time"]-after_time))


def jv_projection(c, trace=None):
    j = c["jv"]
    book = j["opening_group_equity_investment"]
    rows = []
    for idx in range(c["explicit_years"]+1):
        emit(trace,"JV",{"phase":"period_begin","index":idx,"completed":rows,"book":book})
        f = c["stub_year_fraction"] if idx == 0 else 1.0
        profit = book*j["normalised_roe"]*f
        terminal_payout = 1-j["terminal_growth"]/j["normalised_roe"]
        payout = j["payout_rate"] if idx <= 5 else j["payout_rate"]+(terminal_payout-j["payout_rate"])*(idx-5)/5
        div = profit*payout
        book += profit-div
        rows.append({"index": idx, "time": c["stub_year_fraction"]+max(0,idx),
                     "group_investment_book":book, "payout_rate":payout, "owned_profit":profit*j["ownership"],
                     "owned_cash_distribution":div*j["ownership"]})
    # Next-year return on opening capital minus growth capital retention. No added book value.
    terminal_cash = book*(j["normalised_roe"]-j["terminal_growth"])*j["ownership"]
    terminal_value = terminal_cash/(j["equity_discount_rate"]-j["terminal_growth"])
    emit(trace,"JV",{"phase":"complete","rows":rows,"terminal_value":terminal_value})
    return rows, terminal_value


def jv_value(rows, terminal_value, c, after_time=0.0):
    k = c["jv"]["equity_discount_rate"]
    return (sum(discounted(x["owned_cash_distribution"], k, x["time"]-after_time) for x in rows if x["time"] > after_time)
            + discounted(terminal_value, k, rows[-1]["time"]-after_time))


def opening_finance(c):
    pre_oct = (c["group_cash"] + c["group_trading_financial"] + c["other_current_cd_estimate"]
               - c["nci_financial_principal_claim_estimate"] - c["opening_owned_restricted_cash"])
    #10月是独立预算桥；不在未来DCF中再出现。
    oct_interest = c["owned_ordinary_debt"]*c["ordinary_debt_cash_rate"]*(1-c["tax_rate"])/12
    oct_yield = pre_oct*c["cash_aftertax_yield"]/12
    pool = pre_oct+c["october_owned_fcf_bridge"]-oct_interest+oct_yield
    return {"available_owned_cash_pool":pool, "october_operating_bridge":c["october_owned_fcf_bridge"],
            "october_bank_interest_aftertax":oct_interest,"october_financial_yield_aftertax":oct_yield}


def holder_cash_ledger(c, policy, op, jv, opening, trace=None):
    cash = opening["available_owned_cash_pool"]
    parent = cash*c["parent_initial_cash_share"]
    sub = cash-parent
    cd = c["owned_term_cd"]
    purpose = c["opening_purpose_restricted_funds"]
    re = c["parent_re_disclosed_H126"]+c["parent_re_JulOct_budget"]
    reserve = c["parent_legal_reserve"]
    shares = float(c["shares"])
    conversion_price = c["bond"]["conversion_price_current_unit"]
    live_bond = c["bond"]["face"] > 0
    sched = {x["year"]:x for x in bond_schedule(c)}
    completed = []
    for row, jrow in zip(op[:c["holder_years"]+1], jv[:c["holder_years"]+1]):
        y, i, f = row["year"], row["index"], row["year_fraction"]
        begin_parent, begin_sub, begin_purpose = parent, sub, purpose
        emit(trace,"cash",{"phase":"period_begin","year":y,"completed":completed,
             "state":{"parent":parent,"sub":sub,"purpose":purpose,"RE":re,"reserve":reserve,"term_cd":cd,"shares":shares},
             "operating_row":row,"JV_row":jrow})
        is_conversion = (not row["is_stub"] and live_bond and c["bond"]["base_event"]=="conversion" and y==c["bond"]["conversion_year"])
        new_shares = 0.0
        if is_conversion:
            if conversion_price <= 0:
                raise ValueError("nonpositive adjusted conversion price")
            new_shares = c["bond"]["face"]*1e9/conversion_price
            shares += new_shares
            live_bond = False
        bank_interest = c["owned_ordinary_debt"]*c["ordinary_debt_cash_rate"]*(1-c["tax_rate"])*f
        cash_yield = (begin_parent+begin_sub+cd)*c["cash_aftertax_yield"]*f
        pyield = cash_yield*c["parent_initial_cash_share"]
        syield = cash_yield-pyield
        begin_cd = cd
        matured_cd = min(cd, c["term_cd_maturities"].get(str(y),0.0)) if not row["is_stub"] else 0.0
        cd -= matured_cd
        operating_cash = row["cash_from_operations_after_capital"]
        parent_operating_cash = operating_cash*c["parent_cashflow_share"]
        sub_operating_cash = operating_cash-parent_operating_cash
        parent += parent_operating_cash+pyield+matured_cd-bank_interest
        sub += sub_operating_cash+syield+jrow["owned_cash_distribution"]
        #Same project payment already reduced operating_cash. This only reduces a use restriction; never a new inflow.
        purpose_release = min(begin_purpose, row["identified_pipeline_coverage"])
        purpose -= purpose_release
        parent_floor = row["minimum_cash"]*c["parent_minimum_cash_share"]
        sub_floor = row["minimum_cash"]-parent_floor
        sub_profit = row["owned_nopat"]*(1-c["parent_operating_profit_share"])+jrow["owned_profit"]+syield
        upstream_rate = c["upstream_payout_rates"][max(0,i-1)]
        upstream_target = max(0.0,sub_profit)*upstream_rate
        upstream = min(upstream_target,max(0.0,sub-sub_floor))
        sub -= upstream
        parent += upstream
        parent_capital_injection = min(max(0.0,sub_floor-sub),max(0.0,parent-parent_floor-purpose))
        parent -= parent_capital_injection
        sub += parent_capital_injection
        payment = sched.get(y) if not row["is_stub"] and live_bond else None
        bond_cash = payment["cash"] if payment else 0.0
        parent_midyear_available = None
        mid_gaps = None
        if payment:
            purpose_mid = begin_purpose-0.5*purpose_release
            parent_mid_cash = (begin_parent+0.5*(parent_operating_cash+pyield-bank_interest)
                               +matured_cd+0.5*upstream-0.5*parent_capital_injection)
            sub_mid_cash = begin_sub+0.5*(sub_operating_cash+syield+jrow["owned_cash_distribution"]-upstream+parent_capital_injection)
            parent_midyear_available=parent_mid_cash-parent_floor-purpose_mid
            mid_gaps=funding_gaps(parent_mid_cash,sub_mid_cash,parent_floor,sub_floor,purpose_mid,bond_cash)
            if max(mid_gaps["parent_payment_gap"],mid_gaps["group_usable_payment_gap"],mid_gaps["sub_operating_gap"])>1e-8:
                snap={"year":y,"debt_kind":payment["kind"],"payment":bond_cash,
                      "parent_midyear_available":parent_midyear_available,"purpose_midyear":purpose_mid,
                      "parent_midyear_cash":parent_mid_cash,"sub_midyear_cash":sub_mid_cash,
                      "parent_full_year_before_payment":parent,"sub_full_year":sub,"gaps":mid_gaps,
                      "forecast_row":row,"project_use_release_full_year":purpose_release}
                emit(trace,"cash",{"phase":"economic_gap","completed":completed,"current":snap})
                raise EconomicInfeasibility("debt-node funding/access condition not established",snap,completed,classify_gap(mid_gaps))
        parent -= bond_cash
        ending_bond_event = bool(payment and payment["kind"]!="coupon")
        if live_bond:
            coupon_profit_cost = (c["bond"]["face"]*0.02 if ending_bond_event and payment["kind"].startswith("maturity") else
                                  c["bond"]["face"]*c["bond"]["coupon_cash_rates"].get(str(y),0.0))
            if row["is_stub"]:
                coupon_profit_cost = c["bond"]["face"]*0.003*f
            amort = c["bond"]["parent_non_cash_amortization_budget"]*f
        else:
            coupon_profit_cost, amort = 0.0, 0.0
        if ending_bond_event:
            live_bond=False
        parent_profit = (row["owned_nopat"]*c["parent_operating_profit_share"]-bank_interest
                         -coupon_profit_cost-amort+pyield+upstream)
        owner_net_profit = row["owned_nopat"]+jrow["owned_profit"]+cash_yield-bank_interest-coupon_profit_cost-amort
        statutory_capital = shares*c["pending_bonus_factor"]/1e9
        reserve_room=max(0.0,statutory_capital*c["legal_reserve_capital_threshold"]-reserve)
        beginning_re = re
        deficit_to_repair = max(0.0,-beginning_re)
        reserve_profit_base=max(0.0,parent_profit-deficit_to_repair)
        reserve_add=(min(reserve_room,c["stub_legal_reserve_budget"],reserve_profit_base) if row["is_stub"] else
                     min(reserve_room,reserve_profit_base*c["legal_reserve_profit_rate"]))
        reserve += reserve_add
        re += parent_profit-reserve_add
        future_bond_buffer = 0.0
        if live_bond:
            factor=min(1.0,max(0.0,(y-(c["first_forecast_year"]-1))/4))
            future_bond_buffer=c["bond"]["face"]*c["bond"]["maturity_redemption_factor_including_final_coupon"]*factor
        normal_replacement=policy["normal_annual_sbc_cash_replacement_2027"]*((1+policy["sbc_replacement_growth"])**max(0,i-1))*f
        plan_cash=c["discretionary_employee_buyback"].get(str(y),0.0) if not row["is_stub"] else 0.0
        extra_buyback_target=max(0.0,plan_cash-normal_replacement)
        extra_buyback=min(extra_buyback_target,max(0.0,parent-parent_floor-purpose-future_bond_buffer))
        parent-=extra_buyback
        dividend_target=0.0 if row["is_stub"] else max(0.0,owner_net_profit)*c["holder_payout_rates"][i-1]
        dividend=min(dividend_target,max(0.0,re),max(0.0,parent-parent_floor-purpose-future_bond_buffer))
        parent-=dividend
        re-=dividend
        dps=dividend*1e9/shares
        if live_bond:
            conversion_price-=dps
        expected_change=(operating_cash+cash_yield+matured_cd+jrow["owned_cash_distribution"]
                         -bank_interest-bond_cash-extra_buyback-dividend)
        end_gaps=funding_gaps(parent,sub,parent_floor,sub_floor,purpose,0.0)
        snap={"year":y,"is_stub":row["is_stub"],"time":row["time"],"parent_begin_cash":begin_parent,
              "sub_begin_cash":begin_sub,"parent_end_cash":parent,"sub_end_cash":sub,
              "owned_total_available_cash":parent+sub,"owned_minimum_cash":row["minimum_cash"],
              "purpose_balance_start":begin_purpose,"purpose_release_against_same_capex":purpose_release,
              "purpose_balance_end":purpose,"parent_cash_usable_after_purpose":parent-purpose,
              "parent_minimum_cash":parent_floor,"sub_minimum_cash":sub_floor,
              "upstream_dividend":upstream,"upstream_target":upstream_target,"parent_capital_injection":parent_capital_injection,
              "parent_profit_budget":parent_profit,"owner_net_profit_budget":owner_net_profit,
              "parent_beginning_RE":beginning_re,"loss_repair_before_reserve":min(max(0.0,parent_profit),deficit_to_repair),
              "reserve_profit_base_after_loss_repair":reserve_profit_base,
              "parent_ending_RE":re,"parent_statutory_reserve":reserve,"reserve_charge":reserve_add,
              "bond_cash_payment":bond_cash,"bond_kind":payment["kind"] if payment else None,
              "parent_midyear_available_for_bond":parent_midyear_available,"midyear_funding_gaps":mid_gaps,
              "bond_live":live_bond,"bond_buffer":future_bond_buffer,"ordinary_interest_aftertax":bank_interest,
              "financial_yield_aftertax":cash_yield,"term_cd_released":matured_cd,"term_cd_remaining":cd,
              "extra_employee_buyback":extra_buyback,"extra_employee_buyback_target":extra_buyback_target,
              "normal_sbc_replacement_in_operating_cost":normal_replacement,
              "dividend_target":dividend_target,"actual_dividend":dividend,"dividend_per_current_economic_unit":dps,
              "economic_shares":shares,"new_conversion_economic_shares":new_shares,
              "conversion_price_current_economic_unit":conversion_price,"end_funding_gaps":end_gaps,
              "cash_conservation_residual":parent+sub-begin_parent-begin_sub-expected_change}
        emit(trace,"cash",{"phase":"before_assertions","completed":completed,"current":snap})
        close(parent+sub-begin_parent-begin_sub,expected_change,"cash conservation")
        close(matured_cd+cd,begin_cd,"CD principal transfer")
        close(begin_purpose-purpose,purpose_release,"purpose release is not cash creation")
        if max(end_gaps["parent_payment_gap"],end_gaps["sub_operating_gap"],end_gaps["group_usable_payment_gap"])>1e-8:
            raise EconomicInfeasibility("end-period funds/access condition not established",snap,completed,classify_gap(end_gaps))
        completed.append(snap)
        emit(trace,"cash",{"phase":"period_complete","completed":completed})
    return completed


def method2(c, opening_min_cash):
    capital=(c["opening_owned_productive_assets"]+c["opening_owned_intangibles_and_goodwill"]
             +c["opening_owned_nwc"]+opening_min_cash+c["opening_owned_restricted_cash"])
    norm_ebit=sum(b["revenue_2026_normalized"]*b["normalised_margin_method2"]*b["ownership"] for b in c["blocks"])+c["other_operating_profit_2026"]
    norm_nopat=norm_ebit*(1-c["tax_rate"])
    r,g=c["operating_discount_rate"],c["terminal_growth"]
    normal_da=sum(b["revenue_2026_normalized"]*b["ownership"] for b in c["blocks"])*c["da_rate"]
    maintenance_excess=normal_da*(c["maintenance_da_multiple"]-1)
    normal_cash_earnings=norm_nopat-maintenance_excess
    economic_profit=normal_cash_earnings-r*capital
    before_pipeline=capital+economic_profit/(r-g)
    #Existing earnings support test: no separate credit for hoped-for future growth from these cash commitments.
    pipeline_pv=discounted(c["stub_pipeline_growth_capex_owned"],r,c["stub_year_fraction"])
    pipeline_pv+=sum(discounted(v,r,c["stub_year_fraction"]+i+1) for i,v in enumerate(c["pipeline_growth_capex_owned"]))
    return {"normalised_nopat":norm_nopat,"normalised_maintenance_excess":maintenance_excess,
            "normalised_cash_earnings":normal_cash_earnings,"owned_operating_capital":capital,
            "normalised_ROIC":norm_nopat/capital if capital else None,"economic_profit":economic_profit,
            "operating_value_before_remaining_pipeline":before_pipeline,
            "remaining_pipeline_cash_deduction_pv":pipeline_pv,"operating_value":before_pipeline-pipeline_pv,
            "interpretation":"current normalized earnings/capital support; does not independently credit long growth, no mechanical averaging"}


def extra_plan_pv(c,policy):
    total=0.0
    for y,amount in c["discretionary_employee_buyback"].items():
        i=int(y)-c["first_forecast_year"]
        normal=policy["normal_annual_sbc_cash_replacement_2027"]*(1+policy["sbc_replacement_growth"])**max(0,i)
        total+=discounted(max(0.0,amount-normal),c["operating_discount_rate"],c["stub_year_fraction"]+i+1)
    return total


def current_values(c,opening,opening_min,op_ev,jv_ev,m2,extra_pv,denominator):
    bridge=(opening["available_owned_cash_pool"]-opening_min+c["owned_term_cd"]+c["other_financial_assets"]
            -c["owned_ordinary_debt"]-bond_value(c)-extra_pv)
    eq1,eq2=op_ev+jv_ev+bridge,m2["operating_value"]+jv_ev+bridge
    gap=abs(eq1-eq2)/max(abs(eq1),abs(eq2),1e-12)
    return {"financial_bridge_owned":bridge,"future_extra_buyback_pv":extra_pv,
            "purpose_funds_in_asset_pool_not_written_off":c["opening_purpose_restricted_funds"],
            "bond_claim_value_current":bond_value(c),"value_denominator_economic_shares":denominator,
            "current_equity_method1":eq1,"current_equity_method2":eq2,
            "method1_per_current_economic_unit":eq1*1e9/denominator,
            "method2_per_current_economic_unit":eq2*1e9/denominator,
            "method_difference_fraction":gap,"explain_difference_over25pct":gap>0.25}


def run_path(c, policy, name, trace=None):
    emit(trace,"inputs",{"name":name,"inputs":c,"policy":policy})
    validate(c)
    emit(trace,"operating",{"phase":"begin"})
    op,terminal,opening_min=projection(c,trace)
    emit(trace,"operating",{"phase":"complete","rows":op,"terminal":terminal,"opening_min":opening_min})
    jr,jterminal=jv_projection(c,trace)
    opening=opening_finance(c)
    emit(trace,"valuation",{"phase":"begin","opening_finance":opening})
    op_ev=operating_value(op,terminal,c)
    jv_ev=jv_value(jr,jterminal,c)
    m2=method2(c,opening_min)
    denom=float(c["shares"])
    if c["bond"]["base_event"]=="conversion":
        denom+=c["bond"]["face"]*1e9/c["bond"]["conversion_price_current_unit"]
    result={"name":name,"status":"CONDITIONAL_BUDGET_NOT_RESEARCH_ACCEPTANCE","inputs":c,
            "operating_projection":op,"terminal_step":terminal,"jv_projection":jr,
            "jv_terminal_value":jterminal,"opening_finance":opening,"operating_value_method1":op_ev,
            "jv_current_equity_value_owned":jv_ev,"method2_operating":m2,
            "bond_contract_cash_schedule":bond_schedule(c),"models_do_not_include_current_market_price":True}
    result.update(current_values(c,opening,opening_min,op_ev,jv_ev,m2,extra_plan_pv(c,policy),denom))
    emit(trace,"valuation",{"phase":"conditional_values_before_cash_access_check","result":result})
    try:
        ledger=holder_cash_ledger(c,policy,op,jr,opening,trace)
    except EconomicInfeasibility as exc:
        result.update({"status":"PARTIAL_FUNDING_OR_ACCESS_CONDITION","funding_failure_category":exc.category,
                       "error":str(exc),"failure_snapshot":exc.snapshot,"completed_cash_ledger":exc.rows,
                       "holder_model":None,"current_values_are_conditional_not_accepted":True,
                       "current_value_conditions":"operating and asset values retained; payment/access/financing path not proven; no invented financing",
                       "conditional_operating_values_not_funded":exc.category=="GROUP_TOTAL_FUNDING_GAP"})
        emit(trace,"result",{"phase":"economic_partial","result":result})
        return result
    extra_buyback_pv=sum(discounted(x["extra_employee_buyback"],c["operating_discount_rate"],x["time"]) for x in ledger)
    denominator=ledger[-1]["economic_shares"] if c["bond"]["base_event"]=="conversion" else c["shares"]
    result.update(current_values(c,opening,opening_min,op_ev,jv_ev,m2,extra_buyback_pv,denominator))
    h=ledger[-1]
    t=h["time"]
    remaining_bond=bond_value(c,t) if h["bond_live"] else 0.0
    y5_operating=operating_value(op,terminal,c,t)
    y5_jv=jv_value(jr,jterminal,c,t)
    y5_financial=(h["owned_total_available_cash"]-h["owned_minimum_cash"]+h["term_cd_remaining"]
                  +c["other_financial_assets"]-c["owned_ordinary_debt"]-remaining_bond)
    y5_equity=y5_operating+y5_jv+y5_financial
    terminal_pv=discounted(terminal["operating_value_at_end_explicit"],c["operating_discount_rate"],op[-1]["time"])
    c1=op[1]["productive_assets"]+op[1]["ending_nwc"]+op[1]["minimum_cash"]+op[1]["restricted_cash"]+c["opening_owned_intangibles_and_goodwill"]
    c5=op[5]["productive_assets"]+op[5]["ending_nwc"]+op[5]["minimum_cash"]+op[5]["restricted_cash"]+c["opening_owned_intangibles_and_goodwill"]
    result.update({"status":"COMPLETE_CONDITIONAL_BUDGET_NOT_ACCEPTED","cash_ledger":ledger,
                   "current_values_are_conditional_not_accepted":True,
                   "method1_terminal_pv_fraction_of_operating_ev":terminal_pv/op_ev if op_ev else None,
                   "diagnostic_incremental_return_Y1_toY5":(op[5]["owned_nopat"]-op[1]["owned_nopat"])/(c5-c1) if abs(c5-c1)>1e-12 else None,
                   "holder_model":{"start":c["valuation_date"],"D_years":[x["year"] for x in ledger if not x["is_stub"]],
                                   "D_per_current_economic_unit":[x["dividend_per_current_economic_unit"] for x in ledger if not x["is_stub"]],
                                   "Y5_date":"2031-12-31","Y5_operating_value":y5_operating,"Y5_JV_value":y5_jv,
                                   "Y5_financial_bridge":y5_financial,"Y5_equity":y5_equity,
                                   "Y5_purpose_restricted_funds_not_ordinary_cash":h["purpose_balance_end"],
                                   "Y5_economic_shares":h["economic_shares"],
                                   "Y5_per_current_economic_unit":y5_equity*1e9/h["economic_shares"],
                                   "nominal_bonus_adjustment_is_wealth_neutral":True}})
    finite_tree(result)
    emit(trace,"result",{"phase":"complete_conditional","result":result})
    return result


def variant(base,name):
    c=copy.deepcopy(base)
    if name=="base_maturity":
        return c
    if name=="full_conversion_2027":
        c["bond"]["base_event"]="conversion"
    elif name=="contingent_full_put_2027":
        c["bond"]["base_event"]="put"
    elif name=="operating_stress":
        c["tax_rate"]=0.18
        c["terminal_growth"]=0.015
        c["other_operating_profit_2026"]=0.12
        c["other_operating_growth"]=0.015
        c["october_owned_fcf_bridge"]=-0.10
        c["maintenance_da_multiple"]=1.20
        c["jv"].update({"normalised_roe":0.045,"terminal_growth":0.015})
        for b in c["blocks"]:
            if b["name"]=="electric":
                b["growth"]=[0.08,0.06,0.04,0.03,0.02,0.02,0.015,0.015,0.015,0.015]
                b["margin"]=[0.09,0.085,0.085,0.087,0.09,0.087,0.084,0.081,0.078,0.075]
            elif b["name"]=="mechanical_lightweight":
                b["growth"]=[0,0,0.02,0.02,0.02,0.02,0.015,0.015,0.015,0.015]
                b["margin"]=[0.05,0.055,0.06,0.06,0.06,0.058,0.056,0.054,0.052,0.05]
            else:
                b["growth"]=[0.03,0.03,0.02,0.02,0.02,0.02,0.015,0.015,0.015,0.015]
                b["margin"]=[0.025,0.025,0.03,0.03,0.03,0.029,0.028,0.027,0.026,0.025]
            if b["name"] in {"electric","mechanical_lightweight"}:
                b["nwc_ratio"]+=0.03
            b["normalised_margin_method2"]=min(b["normalised_margin_method2"],b["margin"][0])
    elif name=="operating_discount_minus_100bp":
        c["operating_discount_rate"]-=0.01
    elif name=="operating_discount_plus_100bp":
        c["operating_discount_rate"]+=0.01
    elif name=="core_nwc_plus_3pt":
        for b in c["blocks"]:
            if b["name"] in {"electric","mechanical_lightweight"}:
                b["nwc_ratio"]+=0.03
    elif name=="jv_roe_4_5pct":
        c["jv"]["normalised_roe"]=0.045
    elif name=="jv_roe_8_5pct":
        c["jv"]["normalised_roe"]=0.085
    elif name=="other_current_cd_zero":
        c["other_current_cd_estimate"]=0.0
    else:
        raise ValueError(f"unknown named variant {name}")
    return c
