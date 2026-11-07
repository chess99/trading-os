#!/usr/bin/env python3
"""Reproducible economic model. Units: CNY bn, million shares, CNY/share.
No network, prices, hidden work files, or third-party dependencies.
Complete operating source; current valuation is the v5 bridge.
"""
import argparse
import copy
import json
from itertools import product
from pathlib import Path


def tax_adjusted_asset(gross, basis, tax_rate, fee_rate=0.0):
    tax = max(0.0, gross - basis) * tax_rate
    fee = max(0.0, gross) * fee_rate
    return {"gross": gross, "tax_basis": basis, "estimated_exit_tax": tax,
            "estimated_exit_fee": fee, "net": gross - tax - fee}


def value_stream(flows, terminal, rate):
    if rate <= -1:
        raise ValueError("invalid discount rate")
    pv_flows = sum(v / (1 + rate) ** (i + 1) for i, v in enumerate(flows))
    pv_terminal = terminal / (1 + rate) ** len(flows)
    return {"value": pv_flows + pv_terminal, "pv_flows": pv_flows,
            "pv_terminal": pv_terminal, "terminal_fraction":
            pv_terminal / (pv_flows + pv_terminal) if pv_flows + pv_terminal else None}


def capital_action(cash, external_m, issued_m, treasury_m, cancel_m=0.0,
                   new_m=0.0, subscription_price=0.0, buyback_cash=0.0,
                   buyback_price=None):
    if cancel_m > treasury_m + 1e-9:
        raise ValueError("cancel exceeds treasury shares")
    if buyback_cash and (buyback_price is None or buyback_price <= 0):
        raise ValueError("buyback needs explicit non-live budget price")
    bought_m = buyback_cash * 1000 / buyback_price if buyback_cash else 0.0
    return {"cash": cash + new_m * subscription_price / 1000 - buyback_cash,
            "external_m": external_m + new_m - bought_m,
            "issued_m": issued_m - cancel_m + new_m,
            "treasury_m": treasury_m - cancel_m + bought_m,
            "subscription_cash": new_m * subscription_price / 1000,
            "buyback_cash": buyback_cash}


def nwc_state(revenue, cogs, rd_cash, sga_cash, p, index=None, annual_tax=0.0):
    def item(key):
        value = p[key]
        return value[index] if isinstance(value, list) else value
    inv = cogs * item("inventory_days") / 365
    ar = revenue * item("ar_days") / 365
    pre = cogs * item("prepaid_cogs_fraction")
    ap = cogs * item("ap_days") / 365
    advance = revenue * item("customer_advance_fraction")
    necessary = (rd_cash + sga_cash) * p["necessary_cash_opex_fraction"]
    necessary += cogs * p.get("necessary_cash_cogs_fraction", 0)
    wages=(rd_cash+sga_cash)*p.get("wage_payable_opex_fraction",0)
    tax_due=max(0,annual_tax)*p.get("tax_payable_fraction_annual_tax",0)
    other_due=p.get("other_operating_liability_fixed",0)
    return {"inventory": inv, "receivables": ar, "prepaid": pre,
            "payables": ap, "customer_advances": advance,
            "wages_payable":wages,"taxes_payable":tax_due,"other_operating_liabilities":other_due,
            "necessary_cash": necessary, "nwc": inv + ar + pre - ap - advance + necessary-wages-tax_due-other_due}


def weighted_row(a, b, wa, wb, year):
    keys = ["revenue", "cogs", "ebit", "nopat", "fcff", "parent_nopat", "parent_fcff",
            "capex", "da", "normal_parent_profit", "known_sbc", "rd_total"]
    row = {k: a.get(k, 0.0) * wa + b.get(k, 0.0) * wb for k in keys}
    row.update({"holding_year": year, "end_date": f"{2026 + year}-10-31",
                "nwc": a["nwc"] / 6 + b["nwc"] * 5 / 6,
                "noncurrent_capital": a["noncurrent_capital"] / 6 + b["noncurrent_capital"] * 5 / 6,
                "necessary_cash": a["necessary_cash"] / 6 + b["necessary_cash"] * 5 / 6})
    row["invested_capital"] = row["nwc"] + row["noncurrent_capital"]
    return row


def holding_rows(fiscal, q4, years=10):
    # First two months are explicitly Q4, not 2/12 of a distorted peak fiscal year.
    result = []
    for i in range(1, years+1):
        a, b = fiscal[2025 + i], fiscal[2026 + i]
        row = weighted_row(q4 if i == 1 else a, b, 2/3 if i == 1 else 1/6, 5/6, i)
        # End states always interpolate consecutive fiscal closing states.
        for k in ("nwc", "noncurrent_capital", "necessary_cash"):
            row[k] = a[k] / 6 + b[k] * 5 / 6
        row["invested_capital"] = row["nwc"] + row["noncurrent_capital"]
        result.append(row)
    return result


def classify_cxmt_balance(data):
    """Every nonzero Q3 item appears once; necessary cash is a transfer, not an asset addition."""
    src=data["cxmt_balance_classification"]
    p=data["cxmt"]
    assets={k:v/1e9 for k,v in src["assets_yuan"].items()}
    liabilities={k:v/1e9 for k,v in src["liabilities_yuan"].items()}
    groups=src["buckets"]
    asset_names=[name for key,names in groups.items() if key.endswith("assets") for name in names]
    liability_names=[name for key,names in groups.items() if key.endswith("liabilities") for name in names]
    if sorted(asset_names)!=sorted(assets) or len(set(asset_names))!=len(asset_names):
        raise ValueError("CXMT assets missing or double classified")
    if sorted(liability_names)!=sorted(liabilities) or len(set(liability_names))!=len(liability_names):
        raise ValueError("CXMT liabilities missing or double classified")
    totals={k:sum((assets if k.endswith("assets") else liabilities)[n] for n in names)
            for k,names in groups.items()}
    parent=src["reported_parent_equity_yuan"]/1e9
    minority=src["reported_minority_equity_yuan"]/1e9
    if abs(sum(assets.values())-src["reported_total_assets_yuan"]/1e9)>1e-6:
        raise AssertionError("CXMT asset total")
    if abs(sum(liabilities.values())-src["reported_total_liabilities_yuan"]/1e9)>1e-6:
        raise AssertionError("CXMT liability total")
    necessary=p["q3_necessary_cash_estimate"]
    totals["operating_assets"]+=necessary
    totals["liquid_assets"]-=necessary
    totals["operating_net_capital"]=totals["operating_assets"]-totals["operating_liabilities"]
    total_net=(totals["operating_net_capital"]+totals["liquid_assets"]-totals["financing_liabilities"]
               +totals["noncash_assets"]-totals["noncash_liabilities"]
               +totals["unclassified_assets"]-totals["unclassified_liabilities"])
    if abs(total_net-parent-minority)>1e-6:
        raise AssertionError("CXMT four-bucket equity identity")
    return {"assets":assets,"liabilities":liabilities,"totals":totals,
            "parent_equity":parent,"minority_equity":minority,
            "necessary_cash_reclassified_once":necessary,"classified_total_equity":total_net}


def allocate_cxmt_ownership(classification,p,weights):
    """Conditional parent/minority allocation; unknown/noncash balances never become cash."""
    t=classification["totals"]
    if any(not 0<=v<=1 for v in weights.values()):return None
    op=t["operating_net_capital"]*weights["operating"]
    debt=t["financing_liabilities"]*weights["financing"]
    inv_book=(t["noncash_assets"]-t["noncash_liabilities"])*weights["noncash"]
    ua=t["unclassified_assets"]*weights["unknown_assets"]
    ul=t["unclassified_liabilities"]*weights["unknown_liabilities"]
    # The residual must land inside the actual classified liquid-asset bucket.
    cash=classification["parent_equity"]-op-inv_book-ua+ul+debt
    if cash < -1e-8 or cash > t["liquid_assets"]+1e-8:return None
    noncash_fair=sum(classification["assets"][k]*factor for k,factor in p["noncash_investment_fair_factors"].items())*weights["noncash"]
    noncash_fair-=t["noncash_liabilities"]*weights["noncash"]
    ua_fair=ua*p["unknown_asset_recovery_factor"]
    parent_book=cash-debt+op+inv_book+ua-ul
    minority_book=(t["liquid_assets"]-cash)-(t["financing_liabilities"]-debt)+(t["operating_net_capital"]-op)
    minority_book+=(t["noncash_assets"]-t["noncash_liabilities"]-inv_book)+(t["unclassified_assets"]-ua)-(t["unclassified_liabilities"]-ul)
    if abs(parent_book-classification["parent_equity"])>1e-7 or abs(minority_book-classification["minority_equity"])>1e-7:
        raise AssertionError("parent/minority book ownership conservation")
    return {"weights":weights,"operating_net_capital_parent":op,"liquid_assets_parent":cash,
            "financing_liabilities_parent":debt,"noncash_investments_book_parent":inv_book,
            "noncash_investments_fair_parent":noncash_fair,"unknown_assets_book_parent":ua,
            "unknown_assets_fair_parent":ua_fair,"unknown_liabilities_parent":ul,
            "parent_book_equity_check":parent_book,"minority_book_equity_check":minority_book,
            "minority_liquid_assets":t["liquid_assets"]-cash,
            "fair_nonoperating_rights":cash-debt+noncash_fair+ua_fair-ul}


def cxmt_ownership_cases(data,classification):
    p=data["cxmt"]
    neutral=classification["parent_equity"]/(classification["parent_equity"]+classification["minority_equity"])
    keys=("operating","financing","noncash","unknown_assets","unknown_liabilities")
    center=allocate_cxmt_ownership(classification,p,dict.fromkeys(keys,neutral))
    candidates=[]
    bounds=[p["parent_operating_net_capital_share_range"]]+[p["parent_other_bucket_share_range"]]*4
    # Vertices of the ownership box clipped by 0 <= parent liquid assets <= total liquid.
    # Include edge/slab intersections: feasible box corners alone need not attain the extrema.
    for values in product(*bounds):
        candidate=allocate_cxmt_ownership(classification,p,dict(zip(keys,values)))
        if candidate is not None:candidates.append(candidate)
    t=classification["totals"]
    coefficients=(-t["operating_net_capital"],t["financing_liabilities"],
                  -(t["noncash_assets"]-t["noncash_liabilities"]),
                  -t["unclassified_assets"],t["unclassified_liabilities"])
    for variable,key in enumerate(keys):
        if abs(coefficients[variable])<1e-12:continue
        fixed_indices=[j for j in range(len(keys)) if j!=variable]
        for fixed_values in product(*(bounds[j] for j in fixed_indices)):
            weights=dict(zip((keys[j] for j in fixed_indices),fixed_values))
            fixed_cash=classification["parent_equity"]+sum(coefficients[j]*weights[keys[j]] for j in fixed_indices)
            for cash_boundary in (0.0,t["liquid_assets"]):
                weight=(cash_boundary-fixed_cash)/coefficients[variable]
                if bounds[variable][0]<=weight<=bounds[variable][1]:
                    candidate=allocate_cxmt_ownership(classification,p,{**weights,key:weight})
                    if candidate is not None:candidates.append(candidate)
    if center is None or not candidates:raise ValueError("no feasible CXMT ownership allocation")
    lower=min(candidates,key=lambda x:(x["fair_nonoperating_rights"],-x["financing_liabilities_parent"]))
    upper=max(candidates,key=lambda x:(x["fair_nonoperating_rights"],-x["financing_liabilities_parent"]))
    return {"neutral_book_equity_prior":center,"lower_classified_assets":lower,"upper_classified_assets":upper,
            "feasible_vertex_count":len(candidates),"neutral_equity_ratio":neutral,
            "scope":"conditional accounting-feasible ownership envelope, not proven legal title"}


def manufacturing_capital_growth(quantity, equipment_price, productivity):
    return (1+quantity)*(1+equipment_price)/(1+productivity)-1


def manufacturing_capital_roll(productive_begin,cip_begin,productive_target,cip_target,
                               depreciation,commission_request):
    """Construction transfer is noncash; all direct/new-construction cash reconciles with net assets."""
    # Sunk idle plant/CIP is not sold for cash simply because desired capacity falls.
    productive_target=max(productive_begin,productive_target)
    additions_required=depreciation+productive_target-productive_begin
    commissioned=min(cip_begin,max(0,commission_request),max(0,additions_required))
    direct_cash=max(0,additions_required-commissioned)
    cip_after_transfer=cip_begin-commissioned
    cip_target=max(cip_after_transfer,cip_target)
    construction_cash=cip_target-cip_after_transfer
    productive_end=productive_begin-depreciation+commissioned+direct_cash
    capex=direct_cash+construction_cash
    change=productive_end+cip_target-productive_begin-cip_begin
    if abs(change-(capex-depreciation))>1e-8:raise AssertionError("manufacturing capital cash identity")
    return {"productive_begin":productive_begin,"cip_begin":cip_begin,"depreciation":depreciation,
            "noncash_cip_commission":commissioned,"direct_asset_cash":direct_cash,
            "new_construction_cash":construction_cash,"cash_capex":capex,
            "productive_end":productive_end,"cip_end":cip_target,"net_capital_change":change}


def cxmt_financial_bucket_roll(cash,debt,noncash,unknown_assets,unknown_liabilities,
                               operating_cash,dividend,p):
    reserve=unknown_liabilities*p["unknown_liability_cash_reserve_fraction"]
    eligible=max(0,cash-reserve)
    interest=eligible*p["financial_cash_net_yield"]
    financing_cost=debt*p["financial_liability_after_tax_cost"]
    cash_end=cash+operating_cash+interest-financing_cost-dividend
    noncash_end=noncash*(1+p["noncash_investment_value_growth"])
    unknown_assets_end=unknown_assets*(1+p["unknown_asset_value_growth"])
    return {"liquid_financial_assets_end":cash_end,"financing_liabilities_end":debt,
            "noncash_investments_fair_end":noncash_end,"unknown_assets_fair_end":unknown_assets_end,
            "unknown_liabilities_end":unknown_liabilities,
            "fair_nonoperating_rights_end":cash_end-debt+noncash_end+unknown_assets_end-unknown_liabilities,
            "cash_yield_eligible_begin":eligible,"unknown_settlement_cash_reserve":reserve,
            "cash_interest_income":interest,"financing_cash_cost":financing_cost,"cxmt_cash_dividend":dividend}


def build_giga(data):
    r, p = data["raw_giga"], data["giga"]
    seg = [r["revenue_9m"] * w + q for w, q in
           zip(p["nine_month_segment_weights_estimate"], p["q4_revenue_by_segment"])]
    qrev = sum(p["q4_revenue_by_segment"])
    qgp = sum(v*m for v, m in zip(p["q4_revenue_by_segment"], p["q4_margin_by_segment"]))
    qrd_exp = p["fy2026_total_rd"] * (1-p["rd_capitalized_fraction"]) - r["rd_expense_9m"]
    qsga = p["fy2026_sga"] - r["sga_9m"]
    qebit = qgp - qrd_exp - qsga
    qnopat = qebit * (1-p["q4_operating_cash_tax"])
    initial_nwc = (r["inventory_q3"] + r["receivables_q3"] + r["prepaid_q3"]
                   - r["payables_q3"] - r["contract_liabilities_q3"] + p["q3_necessary_cash_estimate"]
                   -r["wages_payable_q3"]-r["taxes_payable_q3"]-r["other_payables_q3"]-r["other_current_liabilities_q3"])
    initial_nc = sum(r[k] for k in ("fixed_assets_q3", "cip_q3", "intangibles_q3",
                                   "development_q3", "goodwill_q3", "other_noncurrent_q3"))
    fyrev = sum(seg)
    fycogs = r["cogs_9m"] + qrev - qgp
    qparam = copy.deepcopy(p)
    qparam["inventory_days"] = p["q4_target_inventory_days"]
    qparam["customer_advance_fraction"] = 0.04
    st = nwc_state(fyrev, fycogs, p["fy2026_total_rd"]*(1-p["rd_non_cash_fraction"]),
                   p["fy2026_sga"], qparam,
                   annual_tax=max(0,fyrev-fycogs-p["fy2026_total_rd"]*(1-p["rd_capitalized_fraction"])-p["fy2026_sga"])*p["cash_tax_rate"])
    qfcff = qnopat + p["q4_da_expense"] + p["q4_known_sbc"] - p["q4_cash_capex"] - (st["nwc"]-initial_nwc)
    nc = initial_nc + p["q4_cash_capex"] - p["q4_da_expense"]
    # Economic cash and accounting profits are separate; total R&D is not called cash.
    q4 = {"revenue": qrev, "cogs": qrev-qgp, "ebit": qebit, "nopat": qnopat,
          "fcff": qfcff, "parent_nopat": qnopat*p["q4_parent_operating_share"],
          "parent_fcff": qfcff*p["q4_parent_operating_share"],
          "capex": p["q4_cash_capex"], "da": p["q4_da_expense"], "known_sbc": p["q4_known_sbc"],
          "rd_total": p["fy2026_total_rd"]/4, "noncurrent_capital": nc, **st}
    fyebit = fyrev - fycogs - p["fy2026_total_rd"]*(1-p["rd_capitalized_fraction"]) - p["fy2026_sga"]
    fyprofit = fyebit*(1-p["cash_tax_rate"])*p["parent_operating_share"]
    normal_gp = sum(v*min(m, p["normal_dividend_memory_margin_cap"]) if i == 0 else v*m
                    for i, (v,m) in enumerate(zip(seg,p["q4_margin_by_segment"])))
    normal_profit = max(0, normal_gp - p["fy2026_total_rd"]*(1-p["rd_capitalized_fraction"])-p["fy2026_sga"]) * (1-p["cash_tax_rate"])*p["parent_operating_share"]
    fiscal = {2026: {"year":2026,"revenue":fyrev,"cogs":fycogs,"ebit":fyebit,
                    "parent_nopat":fyprofit,"normal_parent_profit":normal_profit,
                    "nwc":st["nwc"],"noncurrent_capital":nc,"necessary_cash":st["necessary_cash"],
                    "segment_revenue_estimate":dict(zip(p["segment_names"],seg))}}
    rd, sga = p["fy2026_total_rd"], p["fy2026_sga"]
    other_da = p["other_expense_da_2026"]
    for i, year in enumerate(data["meta"]["fiscal_years"]):
        growth = [(1+p["memory_quantity_growth"][i])*(1+p["memory_price_mix_change"][i])-1,
                  p["mcu_growth"][i],p["sensor_growth"][i],p["analog_growth"][i]]
        seg = [v*(1+g) for v,g in zip(seg,growth)]
        margins = [p[k][i] for k in ("memory_margin","mcu_margin","sensor_margin","analog_margin")]
        rev, gp = sum(seg), sum(v*m for v,m in zip(seg,margins))
        cogs = rev-gp
        rd *= 1+p["rd_growth"][i]
        sga *= 1+p["sga_growth"][i]
        other_da *= 1+p["other_da_growth"]
        rd_expense = rd*(1-p["rd_capitalized_fraction"])
        rd_da_expense = rd*p["rd_non_cash_fraction"]*(1-p["rd_capitalized_fraction"])
        rd_cap_cash = rd*p["rd_capitalized_fraction"]*(1-p["rd_non_cash_fraction"])
        da = other_da + rd_da_expense
        known_sbc = p["known_sbc_expense_addback"][i]
        cash_rd = rd*(1-p["rd_non_cash_fraction"])
        impairment = p["inventory_oneoff_writeoff_2027"] if i == 0 else 0.0
        st_new = nwc_state(rev,cogs,cash_rd,max(0,sga-known_sbc),p,i,
                           annual_tax=max(0,gp-sga-rd_expense-impairment)*p["cash_tax_rate"])
        # Inventory write-down is noncash. Reduced opening carrying NWC must be reflected too.
        if impairment:
            st["nwc"] -= impairment
        ebit = gp-sga-rd_expense-impairment
        nopat = ebit - max(0,ebit)*p["cash_tax_rate"]
        capex = p["fixed_software_cash_capex"][i]+rd_cap_cash
        fcff = nopat+da+known_sbc+impairment-capex-(st_new["nwc"]-st["nwc"])
        nc_new = nc+capex-da
        if nc_new < 0:
            raise ValueError("negative operating capital book proxy")
        normal_gp = min(margins[0],p["normal_dividend_memory_margin_cap"])*seg[0] + sum(v*m for v,m in zip(seg[1:],margins[1:]))
        normal_np = max(0,normal_gp-sga-rd_expense)*(1-p["cash_tax_rate"])*p["parent_operating_share"]
        fiscal[year] = {"year":year,"revenue":rev,"segment_revenue":dict(zip(p["segment_names"],seg)),
                        "segment_gross_margin":dict(zip(p["segment_names"],margins)),"cogs":cogs,
                        "ebit":ebit,"nopat":nopat,"parent_nopat":nopat*p["parent_operating_share"],
                        "fcff":fcff,"parent_fcff":fcff*p["parent_operating_share"],"normal_parent_profit":normal_np,
                        "rd_total":rd,"rd_expense":rd_expense,"rd_cash_equivalent":cash_rd,
                        "capitalized_rd_cash":rd_cap_cash,"da":da,"known_sbc":known_sbc,"capex":capex,
                        "inventory_impairment":impairment,"noncurrent_capital":nc_new,
                        "nwc_change":st_new["nwc"]-st["nwc"],**st_new}
        nc,st = nc_new,st_new
    hold = holding_rows(fiscal,q4)
    return {"fiscal":fiscal,"q4_budget":q4,"holding":hold,"initial_q3_nwc":initial_nwc,
            "initial_q3_noncurrent":initial_nc,
            "cutoff_necessary_cash":p["q3_necessary_cash_estimate"]+(q4["necessary_cash"]-p["q3_necessary_cash_estimate"])/3}


def build_cxmt(data):
    r,p=data["raw_cxmt"],data["cxmt"]
    classified=classify_cxmt_balance(data)
    cases=cxmt_ownership_cases(data,classified)
    owner=cases[p["ownership_mode"]]
    a=classified["assets"]
    prod0=sum(a[k] for k in ("fixed","right_of_use","intangibles","development","long_prepaid"))
    cip0=a["cip"]
    initial_nwc=classified["totals"]["operating_net_capital"]-prod0-cip0
    qrev=p["q4_revenue"]
    fyrev=r["revenue_9m"]+qrev
    qebit=qrev*p["q4_gross_margin"]-p["q4_opex"]
    qnp=qebit*(1-p["q4_cash_tax_rate"])
    qstate=nwc_state(qrev*4,qrev*(1-p["q4_gross_margin"])*4,p["opex_2026"],0,p,
                     annual_tax=max(0,qebit*4)*p["q4_cash_tax_rate"])
    qprod_target=prod0+p["q4_cash_capex"]-p["q4_new_cip_cash"]-p["q4_da"]
    qroll=manufacturing_capital_roll(prod0,cip0,qprod_target,cip0+p["q4_new_cip_cash"],p["q4_da"],0)
    if abs(qroll["cash_capex"]-p["q4_cash_capex"])>1e-8:raise AssertionError("Q4 capex split")
    nc=qroll["productive_end"]+qroll["cip_end"]
    qfcff=qnp+p["q4_da"]-qroll["cash_capex"]-(qstate["nwc"]-initial_nwc)
    q4={"revenue":qrev,"cogs":qrev*(1-p["q4_gross_margin"]),"ebit":qebit,"nopat":qnp,
        "fcff":qfcff,"parent_nopat":qnp*p["parent_operating_cash_share"],
        "parent_fcff":qfcff*p["parent_operating_cash_share"],"capex":qroll["cash_capex"],
        "da":p["q4_da"],"noncurrent_capital":nc,"capital_roll":qroll,**qstate}
    fiscal={2026:{"year":2026,"revenue":fyrev,"nwc":qstate["nwc"],
                  "noncurrent_capital":nc,"necessary_cash":qstate["necessary_cash"],"capital_roll":qroll}}
    rev,opex,st=fyrev,p["opex_2026"],qstate
    productive,cip=qroll["productive_end"],qroll["cip_end"]
    legacy_base,legacy_remaining=cip,cip
    capacity_target=productive
    quantity_index=1.0
    for i,year in enumerate(data["meta"]["fiscal_years"]):
        qg=p["quantity_growth"][i]
        quantity_index*=1+qg
        rev*=(1+qg)*(1+p["price_mix_change"][i])
        opex*=1+p["opex_growth"][i]
        cogs=rev*(1-p["gross_margin"][i])
        ebit=rev-cogs-opex
        nopat=ebit-max(0,ebit)*p["cash_tax_rate"]
        capital_growth=manufacturing_capital_growth(qg,p["productive_asset_price_inflation"],p["capital_productivity_gain"][i])
        capacity_target*=1+capital_growth
        productive_target=max(productive,capacity_target)
        da=(productive+productive_target)/2*p["depreciation_fraction_productive_assets"]
        request=legacy_base*p["cip_commission_fractions"][i] if i<2 else cip
        additions_required=da+productive_target-productive
        preliminary_commission=min(cip,request,max(0,additions_required))
        legacy_remaining=max(0,legacy_remaining-min(legacy_remaining,preliminary_commission))
        cip_target=max(legacy_remaining,p["steady_cip_fraction_productive"]*productive_target)
        roll=manufacturing_capital_roll(productive,cip,productive_target,cip_target,da,request)
        nc_new=roll["productive_end"]+roll["cip_end"]
        st_new=nwc_state(rev,cogs,opex,0,p,annual_tax=max(0,ebit)*p["cash_tax_rate"])
        fcff=nopat+da-roll["cash_capex"]-(st_new["nwc"]-st["nwc"])
        share=p["parent_operating_cash_share"]
        fiscal[year]={"year":year,"revenue":rev,"cogs":cogs,"gross_margin":p["gross_margin"][i],
                      "ebit":ebit,"nopat":nopat,"fcff":fcff,"parent_nopat":nopat*share,"parent_fcff":fcff*share,
                      "capex":roll["cash_capex"],"da":da,"opex":opex,"quantity_index":quantity_index,
                      "quantity_growth":qg,"price_mix_change":p["price_mix_change"][i],
                      "equipment_price_change":p["productive_asset_price_inflation"],
                      "capital_productivity_gain":p["capital_productivity_gain"][i],
                      "required_production_capital_growth":capital_growth,
                      "productive_assets":roll["productive_end"],"cip_uncommissioned":roll["cip_end"],
                      "capital_roll":roll,"noncurrent_capital":nc_new,"parent_operating_share_budget":share,
                      "nwc_change":st_new["nwc"]-st["nwc"],**st_new}
        productive,cip,nc,st=roll["productive_end"],roll["cip_end"],nc_new,st_new
    all_hold=holding_rows(fiscal,q4,years=11)
    hold,forward=all_hold[:10],all_hold[10]
    reserve=owner["unknown_liabilities_parent"]*p["unknown_liability_cash_reserve_fraction"]
    eligible_q3=max(0,owner["liquid_assets_parent"]-reserve)
    october_finance=eligible_q3*p["financial_cash_net_yield"]/12-owner["financing_liabilities_parent"]*p["financial_liability_after_tax_cost"]/12
    cash0=owner["liquid_assets_parent"]+q4["parent_fcff"]/3+october_finance
    cash=cash0
    debt=owner["financing_liabilities_parent"]
    noncash=owner["noncash_investments_fair_parent"]
    unknown_assets=owner["unknown_assets_fair_parent"]
    unknown_liabilities=owner["unknown_liabilities_parent"]
    rights0=cash0-debt+noncash+unknown_assets-unknown_liabilities
    for i,row in enumerate(hold):
        dividend=max(0,row["parent_fcff"])*p["payout_from_operating_cash"][i]
        finance=cxmt_financial_bucket_roll(cash,debt,noncash,unknown_assets,unknown_liabilities,
                                          row["parent_fcff"],dividend,p)
        cash=finance["liquid_financial_assets_end"]
        noncash=finance["noncash_investments_fair_end"]
        unknown_assets=finance["unknown_assets_fair_end"]
        row.update(finance)
    revenue_g=(1+p["terminal_quantity_growth"])*(1+p["terminal_price_mix_change"])-1
    capital_g=manufacturing_capital_growth(p["terminal_quantity_growth"],p["terminal_equipment_price_inflation"],p["terminal_capital_productivity_gain"])
    terminal=terminal_state(hold[-1],p,p["parent_operating_cash_share"])
    tol=p["terminal_transition_algebra_tolerance"]
    growth_aligned=abs(revenue_g-capital_g)<tol and abs(revenue_g-p["terminal_growth"])<tol
    capital_reinvest_forward=(forward["invested_capital"]-hold[-1]["invested_capital"])*p["parent_operating_cash_share"]
    cash_aligned=abs(forward["parent_fcff"]-terminal["cash_flow"])<tol
    capital_aligned=abs(capital_reinvest_forward-terminal["net_reinvestment"])<tol
    if not (growth_aligned and cash_aligned and capital_aligned):
        raise ValueError("CXMT explicit/forward/steady capital contract failed; cannot use Gordon terminal")
    return {"fiscal":fiscal,"q4_budget":q4,"holding":hold,"forward_holding_year11":forward,
            "classification":classified,"ownership_cases":cases,"adopted_ownership":owner,
            "cutoff_liquid_financial_assets":cash0,"cutoff_nonoperating_rights":rights0,
            "october_financial_income_net_budget":october_finance,
            "terminal_transition":{"revenue_growth":revenue_g,"productive_capital_growth":capital_g,
                "forward_parent_net_reinvestment":capital_reinvest_forward,
                "steady_parent_net_reinvestment":terminal["net_reinvestment"],
                "forward_owner_fcff":forward["parent_fcff"],"steady_owner_fcff":terminal["cash_flow"],
                "aligned":growth_aligned and cash_aligned and capital_aligned,
                "last_fiscal_years":[fiscal[y] for y in (2035,2036,2037)]},
            "ownership_note":"Classified conditional parent asset rights; noncash/unknown items do not earn cash yield; no claim of exact legal bank access"}


def terminal_state(row, p, share):
    g=p["terminal_growth"]
    parent_capital=row["invested_capital"]*share
    # No arbitrary capitalization multiple: growth consumes capital already present in the state.
    next_nopat=row["parent_nopat"]*(1+g)
    reinvestment=parent_capital*g
    roic=row["parent_nopat"]/parent_capital if parent_capital>0 else None
    transfer_tax=next_nopat*p.get("owner_cash_transfer_tax_fraction",0.0)
    terminal_fcff=next_nopat-reinvestment-transfer_tax
    return {"next_parent_nopat":next_nopat,"parent_invested_capital":parent_capital,
            "growth":g,"net_reinvestment":reinvestment,"implied_roic":roic,
            "owner_cash_transfer_tax":transfer_tax,"cash_flow":terminal_fcff,
            "reinvestment_rate":reinvestment/next_nopat if next_nopat else None}


def operation_value(rows,p,share,start=0,rate=None):
    rate=p["required_operating_return"] if rate is None else rate
    term=terminal_state(rows[-1],p,share)
    if rate<=p["terminal_growth"]:
        raise ValueError("discount rate must exceed terminal growth")
    terminal=term["cash_flow"]/(rate-p["terminal_growth"])
    result=value_stream([r.get("valuation_owner_fcff",r["parent_fcff"]) for r in rows[start:]],terminal,rate)
    result.update({"terminal_state":term,"terminal_value_at_last_year":terminal,"discount_rate":rate})
    return result


def other_portfolio_value(data):
    p,r=data["portfolio"],data["raw_giga"]
    residual=tax_adjusted_asset(p["residual_other_equity_gross_estimate"]*p["residual_other_equity_fair_factor"],
                               p["residual_other_equity_tax_basis_estimate"],p["other_disposal_tax_rate"])
    other=tax_adjusted_asset(r["other_financial_q3"]*p["other_financial_fair_factor"],
                            p["other_financial_tax_basis_estimate"],p["other_disposal_tax_rate"])
    long_equity=r["long_equity_q3"]*p["long_equity_fair_factor"]
    return {"residual_other_equity":residual,"other_financial":other,
            "long_equity":long_equity,"net":residual["net"]+other["net"]+long_equity}


def cxmt_stake_value(data,cx,start=0,rate=None):
    p,r=data["portfolio"],data["raw_cxmt"]
    op=operation_value(cx["holding"],data["cxmt"],data["cxmt"]["parent_operating_cash_share"],start,rate)
    claims=cx["cutoff_nonoperating_rights"] if start==0 else cx["holding"][start-1]["fair_nonoperating_rights_end"]
    stake_fraction=r["giga_owned_m"]/r["shares_m"]
    gross=(op["value"]+claims)*stake_fraction
    net=tax_adjusted_asset(gross,r["giga_cost"],p["cxmt_disposal_tax_rate"],p["investment_disposal_fee_fraction"])
    net["net"]*=1-p["holding_liquidity_haircut"]
    return {"operation_value_parent":op,"classified_nonoperating_rights":claims,
            "stake_fraction":stake_fraction,"stake":net}


def bridge_at_cutoff(data,giga,cx):
    r,p=data["raw_giga"],data["portfolio"]
    # FCFF already contains the change in necessary cash. Deduct the Q3 reserve
    # once, then roll the excess balance by October FCFF; not the new reserve twice.
    liquid=(r["cash_q3"]+r["trading_assets_q3"]-data["giga"]["q3_necessary_cash_estimate"]
            +giga["q4_budget"]["parent_fcff"]/3-p["post_q3_buyback_cash_estimate"]
            -p["minority_claim_on_group_liquid_assets_estimate"])
    interest_bearing_debt=r["lease_q3"]+r["current_noncurrent_liability_q3"]
    debt=interest_bearing_debt+r["other_noncurrent_liability_q3"]
    other=other_portfolio_value(data)
    stake=cxmt_stake_value(data,cx)
    commitments_loss=sum(call*(1-p["new_commitment_asset_fair_fraction"])/(1+data["giga"]["required_operating_return"])**(i+1)
                         for i,call in enumerate(p["fund_call_cash_by_holding_year"]))
    extra_capital_pv=data.get("additional_unmatched_capital_cash",0.0)/(1+data["giga"]["required_operating_return"])
    cash_delivery_pv=sum(data.get("H_cash_delivery_budget",0.0)/4/(1+data["giga"]["required_operating_return"])**i for i in range(1,5))
    nav_reference=(r["parent_equity_q3"]-r["other_equity_q3"]-r["other_financial_q3"]-r["long_equity_q3"]
                   +other["net"]+stake["stake"]["net"]+r["dtl_q3"]-p["noninvestment_dtl_estimate"])
    # A reserve changes availability for distribution, not the existence of the asset.
    return {"excess_group_liquid_economic_claims":liquid,"existing_debt":debt,
            "interest_bearing_debt_budget":interest_bearing_debt,
            "other_portfolio":other,"cxmt":stake,"noninvestment_dtl":p["noninvestment_dtl_estimate"],
            "future_commitment_fair_value_shortfall_pv":commitments_loss,
            "unmatched_capital_cost_pv":extra_capital_pv,"H_cash_delivery_cost_pv":cash_delivery_pv,
            "investment_dtl_removed_from_book_bridge":r["dtl_q3"]-p["noninvestment_dtl_estimate"],
            "distribution_restricted_reserve":p["statutory_or_project_cash_not_yet_free_estimate"],
            "adjusted_reported_nav_reference":nav_reference,
            "nav_reference_scope":"9/30 reported parent NAV with modeled investment marks; not audited fair NAV, not liquidation floor, no unreported October operating profit inserted",
            "net_nonoperating_bridge":liquid-debt+other["net"]+stake["stake"]["net"]
                                      -p["noninvestment_dtl_estimate"]-commitments_loss-extra_capital_pv-cash_delivery_pv}


def holder_path(data,giga,cx,bridge):
    m,p,r=data["mother"],data["portfolio"],data["raw_giga"]
    common_cash=bridge["excess_group_liquid_economic_claims"]
    mother_cash=m["available_cash_at_cutoff_estimate"]
    retained=m["retained_earnings_at_cutoff_floor"]
    reserve=r["statutory_reserve_h1"]
    ext=r["issued_m"]-r["treasury_m_oct29"]
    issued,treasury=r["issued_m"],r["treasury_m_oct29"]
    subsidiary_retained=m["unconfirmed_prior_subsidiary_distributable_retained_earnings"]
    prior_parent_legal=m["fy2026_own_legal_profit_estimate"]
    other_assets=bridge["other_portfolio"]["net"]
    deferred_upstream=0.0
    result=[]
    for i,row in enumerate(giga["holding"][:5]):
        year=i+1
        prior_fiscal=giga["fiscal"][2026+i]
        own_fraction=m["own_fraction_of_group_operating_profit_and_cash"]
        owner_fcff=row["parent_fcff"]
        debt_cost=bridge["interest_bearing_debt_budget"]*p["after_tax_debt_cost"]
        mother_excess=max(0,mother_cash-m["minimum_operating_cash"])
        sub_cash_before=max(0,common_cash-mother_excess)
        sub_interest=sub_cash_before*p["financial_cash_net_yield"]
        sub_cash_capacity=max(0,sub_cash_before+owner_fcff*(1-own_fraction)+sub_interest-deferred_upstream)
        sub_profit=prior_fiscal["parent_nopat"]*(1-m["own_fraction_of_group_operating_profit_and_cash"])
        subsidiary_retained+=sub_profit
        scheduled_upstream=min(max(0,subsidiary_retained),max(0,sub_profit)*m["subsidiary_profit_cash_upstream_fraction"],sub_cash_capacity)
        subsidiary_retained-=scheduled_upstream
        upstream_cash=scheduled_upstream*(1-m["upstream_one_year_delay_fraction"])+deferred_upstream
        deferred_upstream=scheduled_upstream*m["upstream_one_year_delay_fraction"]
        # Declaration raises legal earnings now; later collection is cash only.
        upstream_tax=upstream_cash*m["additional_upstream_cash_tax_fraction"]
        interest=max(0,common_cash)*p["financial_cash_net_yield"]-debt_cost
        mother_interest=mother_excess*p["financial_cash_net_yield"]-debt_cost
        cxdiv=cx["holding"][i]["cxmt_cash_dividend"]*cx["raw_stake_fraction"]
        common_before=common_cash
        common_cash+=owner_fcff+interest+cxdiv-upstream_tax
        mother_cash+=owner_fcff*m["own_fraction_of_group_operating_profit_and_cash"]+upstream_cash+mother_interest+cxdiv-upstream_tax
        legal_profit=(row["parent_nopat"]*m["own_fraction_of_group_operating_profit_and_cash"]
                      +scheduled_upstream*(1-m["additional_upstream_cash_tax_fraction"])+mother_interest+cxdiv)
        fund_call=p["fund_call_cash_by_holding_year"][i]
        extra_capital=data.get("additional_unmatched_capital_cash",0.0) if i==0 else 0.0
        award_delivery_cash=data.get("H_cash_delivery_budget",0.0)/4 if i<4 else 0.0
        common_cash-=fund_call+extra_capital+award_delivery_cash
        mother_cash-=(fund_call+extra_capital+award_delivery_cash)*m["mother_funds_fraction"]
        added_investment_value=fund_call*p["new_commitment_asset_fair_fraction"]
        other_assets=other_assets*(1+p["other_assets_net_growth"])+added_investment_value
        cancel=treasury if year==m["cancel_existing_treasury_holding_year"] else 0.0
        before_capital=common_cash
        action_a=capital_action(common_cash,ext,issued,treasury,cancel,
                                m["new_A_options_m_by_holding_year"][i],m["A_option_strikes"][i])
        action_h=capital_action(action_a["cash"],action_a["external_m"],action_a["issued_m"],action_a["treasury_m"],
                                new_m=m["new_H_awards_m_by_holding_year"][i],subscription_price=m["H_award_subscription_price"])
        common_cash,ext,issued,treasury=[action_h[k] for k in ("cash","external_m","issued_m","treasury_m")]
        subscription_cash=common_cash-before_capital
        mother_cash+=subscription_cash
        target_reserve=issued/1000*0.50
        appropriation=min(max(0,target_reserve-reserve),max(0,legal_profit)*0.10)
        reserve+=appropriation
        retained+=legal_profit-appropriation
        floor=max(0,prior_parent_legal)*m["statutory_policy_floor"]
        intention=max(0,prior_fiscal["normal_parent_profit"])*m["normal_profit_cash_distribution_intent"]
        wanted=max(floor,intention)
        legal_cap=max(0,retained)
        restricted=p["project_restriction_by_holding_year"][i]
        mother_cap=max(0,mother_cash-m["minimum_operating_cash"]-restricted)
        group_cap=max(0,common_cash-restricted)
        allowed=min(legal_cap,mother_cap,group_cap)
        paid=min(wanted,allowed)
        floor_pass=allowed+1e-9>=floor
        funding_pass=common_cash>=-1e-9 and mother_cash>=-1e-9
        common_cash-=paid
        mother_cash-=paid
        retained-=paid
        identity_rhs=(common_before+owner_fcff+interest+cxdiv-upstream_tax-fund_call-extra_capital-award_delivery_cash+subscription_cash-paid)
        if abs(common_cash-identity_rhs)>1e-7:
            raise AssertionError("group cash conservation")
        result.append({"holding_year":year,"end_date":row["end_date"],"parent_fcff":owner_fcff,
                       "normal_dividend_intention":intention,"legal_policy_floor":floor,"dividend_budget":wanted,
                       "actual_model_dividend":paid,"distribution_per_share":paid*1000/ext,
                       "policy_floor_feasible":floor_pass,"financing_feasible_without_new_finance":funding_pass,
                       "mother_cash":mother_cash,"mother_retained":retained,"mother_legal_profit":legal_profit,
                       "statutory_reserve":reserve,"upstream_declared":scheduled_upstream,"upstream_received":upstream_cash,
                       "upstream_receivable":deferred_upstream,"upstream_tax":upstream_tax,
                       "subsidiary_cash_capacity":sub_cash_capacity,"funding_reserve":restricted,
                       "net_debt_cost":debt_cost,"H_cash_delivery":award_delivery_cash,
                       "group_excess_cash":common_cash,"other_investments_net":other_assets,
                       "fund_contribution_cash":fund_call,"new_fund_value":added_investment_value,
                       "extra_unmatched_capital_cash":extra_capital,"subscription_cash":subscription_cash,
                       "external_shares_m":ext,"issued_shares_m":issued,"treasury_shares_m":treasury,
                       "known_future_capital_actions_only":True})
        prior_parent_legal=legal_profit
    return result


def auxiliary_value(data,giga,bridge,exercise_pv):
    # Earnings-power cross-check: same base state at year 5, normalized cost/margin
    # immediately mature thereafter rather than allowing another five years of transition.
    row=giga["holding"][4]
    p=data["giga"]
    term=terminal_state(row,p,p["parent_operating_share"])
    mature_memory=p["memory_margin"][-1]
    fy=giga["fiscal"][2031]
    margin_excess=max(0,fy["segment_gross_margin"]["memory"]-mature_memory)
    steady_profit=term["next_parent_nopat"]-fy["segment_revenue"]["memory"]*margin_excess*(1-p["cash_tax_rate"])*p["parent_operating_share"]
    normalized_cash=steady_profit-term["net_reinvestment"]-steady_profit*p.get("owner_cash_transfer_tax_fraction",0.0)
    terminal=normalized_cash/(p["required_operating_return"]-p["terminal_growth"])
    value=value_stream([x.get("valuation_owner_fcff",x["parent_fcff"]) for x in giga["holding"][:5]],terminal,p["required_operating_return"])
    return {"method":"normalized_earnings_power_at_base_year5_plus_explicit_bridge",
            "normalized_parent_nopat":steady_profit,"normalized_owner_cash":normalized_cash,
            "normalization_year":5,"operating_value":value,
            "equity_value":value["value"]+bridge["net_nonoperating_bridge"]+exercise_pv,
            "limitations":"same base facts/capital assumptions; not independent corroboration"}


def scenario_input(data,name):
    d=copy.deepcopy(data)
    if name=="base": return d
    s=d["scenarios"][name]
    if name in ("cycle_stress","long_shortage"):
        mapping={"giga_memory_price_first_two":("giga","memory_price_mix_change"),
                 "giga_memory_quantity_first_two":("giga","memory_quantity_growth"),
                 "giga_memory_margin_first_three":("giga","memory_margin"),
                 "giga_inventory_days_first_two":("giga","inventory_days"),
                 "giga_customer_advance_first_two":("giga","customer_advance_fraction"),
                 "cxmt_price_first_two":("cxmt","price_mix_change"),
                 "cxmt_margin_first_three":("cxmt","gross_margin"),
                 "cxmt_quantity_first_two":("cxmt","quantity_growth")}
        for key,(section,field) in mapping.items():
            if key in s: d[section][field][:len(s[key])]=s[key]
        if "giga_inventory_writeoff" in s:d["giga"]["inventory_oneoff_writeoff_2027"]=s["giga_inventory_writeoff"]
        if "cxmt_parent_cash_share" in s:d["cxmt"]["parent_operating_cash_share"]=s["cxmt_parent_cash_share"]
    elif name in ("upstream_delay","maximum_funding_pressure"):
        d["mother"]["available_cash_at_cutoff_estimate"]=s["mother_initial_cash"]
        if "upstream_delay_fraction" in s:d["mother"]["upstream_one_year_delay_fraction"]=s["upstream_delay_fraction"]
        if "additional_unmatched_capital_cash" in s:d["additional_unmatched_capital_cash"]=s["additional_unmatched_capital_cash"]
    elif name=="commitments_already_paid":
        d["portfolio"]["fund_call_cash_by_holding_year"]=[0,0,0,0,0]
        d["portfolio"]["remaining_investment_commit_cash"]=0
        d["portfolio"]["yunfeng_unpaid_usd_million_estimate"]=0
    elif name=="awards_cash_delivery":
        d["H_cash_delivery_budget"]=s["total_H_purchase_cash_budget"]
        d["mother"]["new_H_awards_m_by_holding_year"]=[0,0,0,0,0]
    elif name=="cxmt_no_efficiency_price_pass":
        d["cxmt"]["capital_productivity_gain"]=[0]*11
        d["cxmt"]["quantity_growth"][7:]=[0.01]*4
        d["cxmt"]["price_mix_change"][7:]=[0.015]*4
        d["cxmt"]["opex_growth"][7:]=[0.02515]*4
        d["cxmt"]["terminal_quantity_growth"]=0.01
        d["cxmt"]["terminal_price_mix_change"]=0.015
        d["cxmt"]["terminal_capital_productivity_gain"]=0.0
        d["cxmt"]["terminal_growth"]=0.02515
    return d


def diagnostic_band(data,giga,cx,bridge,holder,exercise_pv):
    points=[]
    for label,idx,ownership_mode in (("lower",1,"lower_classified_assets"),("upper",0,"upper_classified_assets")):
        d=copy.deepcopy(data)
        rg=d["giga"]["required_operating_return_range"][idx]
        rc=d["cxmt"]["required_operating_return_range"][idx]
        # Base operating/cash distribution paths unchanged; asset-attribution uncertainty only.
        d["cxmt"]["ownership_mode"]=ownership_mode
        cx_band=build_cxmt(d)
        stake0=cxmt_stake_value(d,cx_band,0,rc)["stake"]["net"]
        stake5=cxmt_stake_value(d,cx_band,5,rc)["stake"]["net"]
        current_op=operation_value(giga["holding"],d["giga"],d["giga"]["parent_operating_share"],0,rg)["value"]
        terminal_op=operation_value(giga["holding"],d["giga"],d["giga"]["parent_operating_share"],5,rg)["value"]
        current=current_op+bridge["net_nonoperating_bridge"]-bridge["cxmt"]["stake"]["net"]+stake0+exercise_pv
        h5=holder[-1]
        terminal=(terminal_op+h5["group_excess_cash"]+h5["other_investments_net"]+stake5
                  -bridge["existing_debt"]-bridge["noninvestment_dtl"])
        points.append({"label":label,"current_equity":current,"year5_equity":terminal,
                       "op_required_return":rg,"cxmt_required_return":rc,
                       "cxmt_classified_rights_cutoff":cx_band["cutoff_nonoperating_rights"],
                       "cxmt_ownership_allocation":cx_band["adopted_ownership"],
                       "cxmt_tax_adjusted_stake_now":stake0,"cxmt_tax_adjusted_stake_year5":stake5,
                       "base_distributions_and_giga_cash_unchanged":True})
    return points


def run_case(data,name="base"):
    d=scenario_input(data,name)
    giga,cx=build_giga(d),build_cxmt(d)
    cx["raw_stake_fraction"]=d["raw_cxmt"]["giga_owned_m"]/d["raw_cxmt"]["shares_m"]
    bridge=bridge_at_cutoff(d,giga,cx)
    holder=holder_path(d,giga,cx,bridge)
    transfer_tax_fraction=((1-d["mother"]["own_fraction_of_group_operating_profit_and_cash"])
                           *d["mother"]["subsidiary_profit_cash_upstream_fraction"]
                           *d["mother"]["additional_upstream_cash_tax_fraction"])
    d["giga"]["owner_cash_transfer_tax_fraction"]=transfer_tax_fraction
    for i,row in enumerate(giga["holding"]):
        tax=holder[i]["upstream_tax"] if i<5 else max(0,row["parent_nopat"])*transfer_tax_fraction
        row["valuation_owner_transfer_tax"]=tax
        row["valuation_owner_fcff"]=row["parent_fcff"]-tax
    op=operation_value(giga["holding"],d["giga"],d["giga"]["parent_operating_share"])
    exercise_pv=sum(h["subscription_cash"]/(1+d["giga"]["required_operating_return"])**h["holding_year"] for h in holder)
    diluted_shares=holder[-1]["external_shares_m"]
    current=op["value"]+bridge["net_nonoperating_bridge"]+exercise_pv
    aux=auxiliary_value(d,giga,bridge,exercise_pv)
    band=diagnostic_band(d,giga,cx,bridge,holder,exercise_pv)
    warnings=[]
    if abs(giga["fiscal"][2037]["revenue"]/giga["fiscal"][2036]["revenue"]-1-d["giga"]["terminal_growth"])>0.02:
        warnings.append("forward fiscal growth does not converge to terminal growth")
    for who,rows,p,share in (("giga",giga["holding"],d["giga"],d["giga"]["parent_operating_share"]),
                              ("cxmt",cx["holding"],d["cxmt"],d["cxmt"]["parent_operating_cash_share"])):
        t=terminal_state(rows[-1],p,share)
        lo,hi=p["terminal_roic_diagnostic_band"]
        if t["implied_roic"] is None or not lo<=t["implied_roic"]<=hi:
            warnings.append(f"{who}: terminal ROIC outside evidence diagnostic band; review not automatic clamp")
        flow_margin_jump=(t["cash_flow"]/(1+p["terminal_growth"])-rows[-1]["parent_fcff"])/rows[-1]["revenue"]
        if who=="giga" and abs(flow_margin_jump)>p["terminal_cash_margin_jump_tolerance"]:
            warnings.append(f"{who}: last-explicit/terminal cash margin jump requires review")
        if who=="cxmt" and not cx["terminal_transition"]["aligned"]:
            raise AssertionError("CXMT terminal identity must hold, not merely fit a tolerance band")
    if abs(aux["equity_value"]/current-1)>0.25:
        warnings.append("primary/auxiliary differ >25%; explain normalization/transition, do not average")
    if current*1000/diluted_shares < max(d["mother"]["A_option_strikes"]):
        warnings.append("intrinsic diluted value below an option strike; exercise assumption requires conditional revision")
    issuer_feasible=all(h["policy_floor_feasible"] and h["financing_feasible_without_new_finance"] for h in holder)
    cxmt_feasible=all(h["liquid_financial_assets_end"]>=h["unknown_settlement_cash_reserve"] for h in cx["holding"])
    feasible=issuer_feasible and cxmt_feasible
    if not issuer_feasible:warnings.append("issuer distribution/funding infeasible: no clean holder model may be adopted")
    if not cxmt_feasible:warnings.append("CXMT operating-capital path requires unfunded financing; investment valuation conditional, not issuer insolvency")
    value_range=sorted(x["current_equity"]*1000/diluted_shares for x in band)
    term_range=sorted(x["year5_equity"]*1000/holder[-1]["external_shares_m"] for x in band)
    return_model={"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY",
                  "model_as_of":d["meta"]["information_cutoff"],
                  "base_case_distributions_per_share":[h["distribution_per_share"] for h in holder],
                  "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":term_range[0],"high":term_range[1]}}}
    return {"scenario":name,"numeric_adoption":"PENDING_INDEPENDENT_REVIEW",
            "business_stress":name in ("cycle_stress","long_shortage","cxmt_no_efficiency_price_pass"),"funding_distribution_feasible":feasible,
            "issuer_funding_distribution_feasible":issuer_feasible,"cxmt_financing_budget_feasible":cxmt_feasible,
            "current_primary_equity":current,"current_primary_per_diluted_share":current*1000/diluted_shares,
            "current_value_range_per_diluted_share":value_range,"current_diluted_shares_m":diluted_shares,
            "future_subscription_cash_pv":exercise_pv,"primary_operating_value":op,"auxiliary":aux,
            "bridge":bridge,"giga":giga,"cxmt":cx,"holder":holder,"base_path_valuation_band":band,
            "return_model":return_model if feasible else None,
            "return_model_note":"Five Nov-Oct cash buckets; year5 is 2031-10-31. Same base operating state and after-dividend cash in both terminal endpoints; only valuation discount rates and CXMT classified asset-ownership bounds differ. Noncash/unknown rights are not cash-interest buckets. No quote or IRR. Conditional forecasts, not promised distributions.",
            "warnings":warnings}


def validate_inputs(data):
    if data["meta"]["money_unit"]!="CNY_billion": raise ValueError("units")
    if abs(sum(data["giga"]["nine_month_segment_weights_estimate"])-1)>1e-10: raise ValueError("segment weights")
    if len(data["meta"]["fiscal_years"])!=11: raise ValueError("fiscal horizon")
    if len(data["portfolio"]["fund_call_cash_by_holding_year"])!=5: raise ValueError("holder horizon")
    if abs(sum(data["portfolio"]["fund_call_cash_by_holding_year"])-data["portfolio"]["remaining_investment_commit_cash"]
           -data["portfolio"]["yunfeng_unpaid_usd_million_estimate"]*data["portfolio"]["usd_cny_budget"]/1000)>1e-8:
        raise ValueError("fund contributions and obligation budget must reconcile")
    for s in ("giga","cxmt"):
        if data[s]["required_operating_return"]<=data[s]["terminal_growth"]:raise ValueError("r<=g")


def run_sensitivities(data):
    # Isolated diagnostic changes, not complete business scenarios or probability weights.
    specs={
        "cxmt_parent_flow_share_55":{"cxmt.parent_operating_cash_share":0.55},
        "cxmt_parent_flow_share_75":{"cxmt.parent_operating_cash_share":0.75},
        "cxmt_disposal_tax_15":{"portfolio.cxmt_disposal_tax_rate":0.15},
        "cxmt_disposal_tax_25":{"portfolio.cxmt_disposal_tax_rate":0.25},
        "cxmt_unknown_asset_recovery_50":{"cxmt.unknown_asset_recovery_factor":0.50},
        "cxmt_unknown_asset_recovery_100":{"cxmt.unknown_asset_recovery_factor":1.0},
        "cxmt_noncash_investment_recovery_50":{"cxmt.noncash_investment_fair_factors":
            {"long_equity":0.5,"other_equity":0.5,"other_noncurrent_financial":0.5,"derivative_asset":1.0}},
        "cxmt_noncash_investment_recovery_100":{"cxmt.noncash_investment_fair_factors":
            {"long_equity":1.0,"other_equity":1.0,"other_noncurrent_financial":1.0,"derivative_asset":1.0}},
        "A_options_zero":{"mother.new_A_options_m_by_holding_year":[0,0,0,0,0]},
        "A_options_8m":{"mother.new_A_options_m_by_holding_year":[4.4,3.6,0,0,0]},
        "other_portfolio_low":{"portfolio.residual_other_equity_fair_factor":0.70,
                               "portfolio.other_financial_fair_factor":0.65,"portfolio.long_equity_fair_factor":0.85},
        "other_portfolio_high":{"portfolio.residual_other_equity_fair_factor":1.10,
                                "portfolio.other_financial_fair_factor":1.05,"portfolio.long_equity_fair_factor":1.15}}
    results={}
    for label,overrides in specs.items():
        d=copy.deepcopy(data)
        for path,value in overrides.items():
            section,field=path.split(".")
            d[section][field]=value
        result=run_case(d)
        result["sensitivity"]={"label":label,"overrides":overrides,"not_a_complete_business_scenario":True}
        results[label]=result
    return results
