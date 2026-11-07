"""Small deterministic valuation engine. No network, imports with side effects or I/O.

All currency amounts are CNY. This is not an independently audited calculator.
Source inputs and economic assumptions live outside this module.
"""
from __future__ import annotations
import math


class ModelError(ValueError):
    pass


def snapshot(sink, stage, payload):
    """Synchronous raw checkpoint; an I/O failure is a program failure, not economics."""
    if sink is not None:
        sink(stage, payload)


def require(condition, message):
    if not condition:
        raise ModelError(message)


def close(a, b, label, absolute=0.01, relative=1e-10):
    require(math.isfinite(a) and math.isfinite(b), label + ": nonfinite")
    require(abs(a-b) <= max(absolute, relative*max(abs(a), abs(b))),
            f"{label}: {a!r} != {b!r}")


def finite_tree(value, path="root"):
    if isinstance(value, dict):
        for key, item in value.items():
            finite_tree(item, path+"."+str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            finite_tree(item, f"{path}[{index}]")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        require(math.isfinite(value), path+": nonfinite numeric input")


def validate(data, s):
    finite_tree(data)
    n = data["periods"]
    require(isinstance(n, int) and 1 <= n <= 10, "bounded horizon required")
    require(data["unit"] == "CNY", "currency/unit must be CNY")
    require(s["discount_rate"] > s["terminal_growth"] >= 0, "r must exceed g")
    require(0 < s["terminal_incremental_roic"] <= 1, "terminal ROIC")
    require(0 < s["nci_terminal_incremental_roic"] <= 1, "NCI terminal ROIC")
    require(s["terminal_growth"] < min(s["terminal_incremental_roic"],
            s["nci_terminal_incremental_roic"]), "terminal retention must be below one")
    for name in ["domestic_price_factors", "domestic_volume_factors", "overseas_growth",
                 "domestic_ebit_margins", "overseas_ebit_margins", "nwc_ratios",
                 "parent_cash_access"]:
        require(len(s[name]) == n, name+": horizon mismatch")
    for name in ["tax_rate", "da_ratio", "maintenance_capex_ratio", "operating_cash_ratio"]:
        require(0 <= s[name] <= 1, name+": ratio out of range")
    require(s["maintenance_capex_ratio"] >= s["da_ratio"],
            "maintenance cannot be permanently below non-ROU D&A in this design")
    for name in ["nwc_ratios", "parent_cash_access"]:
        require(all(0 <= x <= 1 for x in s[name]), name+": ratio out of range")
    require(all(x > 0 for x in s["domestic_price_factors"]+s["domestic_volume_factors"]),
            "positive domestic price and volume factors required")
    require(all(x > -1 for x in s["overseas_growth"]), "invalid foreign growth")
    require(1 <= s["aux_normalization_year"] <= n, "aux normalization year")
    b = data["balance"]
    require(b["issued_shares"] > b["treasury_shares"] >= 0, "invalid shares")
    require(0 <= b["fund_future_asset_recovery"] <= 1, "fund recovery")
    for e in data["nci_entities"]:
        require(0 <= e["minority_fraction"] <= 1, "NCI ownership")
        require(0 <= e["reinvestment_rate"] < 1, "NCI reinvestment")
        require(e["growth_axis"] in ("domestic", "overseas"), "NCI axis")


def asset_bridge(data, s, sink=None):
    b, a = data["balance"], data["anchor"]
    eligible = {k: b[k]*v for k, v in b["financial_eligibility"].items()}
    operating_cash = (a["domestic_revenue"]+a["overseas_revenue"])*a["operating_cash_ratio"]
    debt = b["short_borrowings"]+b["long_borrowings"]
    unpaid = max(0.0, b["fund_committed"]-b["fund_paid_at_h1"])
    fund_df = (1+s["discount_rate"])**b["fund_call_year"]
    call_pv = unpaid/fund_df
    future_asset_pv = unpaid*b["fund_future_asset_recovery"]/fund_df
    extra = (b["cash_equivalents"]+sum(eligible.values())-operating_cash-debt
             -b["dividend_paid_after_q3_before_cutoff"]-b["nci_nonoperating_cash_claim"]
             +b["nci_borrowing_share"]-call_pv+future_asset_pv
             +b["bridge_october_unknown_operating_cashflow"])
    liquid_owner = (b["cash_equivalents"]+eligible.get("trading_financial", 0)
                   +eligible.get("other_current_assets", 0)
                   +eligible.get("current_noncurrent_assets", 0)-operating_cash-debt
                   -b["dividend_paid_after_q3_before_cutoff"]
                   -b["nci_nonoperating_cash_claim"]+b["nci_borrowing_share"])
    nonliquid=sum(value for key,value in eligible.items() if key not in
                  ("trading_financial","other_current_assets","current_noncurrent_assets"))
    result={"eligible_financial_assets": eligible, "cash_equivalents": b["cash_equivalents"],
            "operating_cash_retained": operating_cash, "borrowings_settled": debt,
            "known_prevaluation_dividend_deducted_once": b["dividend_paid_after_q3_before_cutoff"],
            "nci_nonoperating_cash_deducted": b["nci_nonoperating_cash_claim"],
            "nci_share_of_borrowings_added_back": b["nci_borrowing_share"],
            "fund_unpaid_proxy": unpaid, "fund_call_pv": call_pv,
            "future_fund_asset_pv": future_asset_pv, "net_nonoperating_owner_value": extra,
            "initial_owner_liquid_pool_before_future_fund_call": liquid_owner,
            "initial_nonliquid_financial_assets": nonliquid,
            "future_fund_reservation_headroom_not_current_payment": liquid_owner-unpaid,
            "initial_owner_liquid_pool_shortfall": min(0.0, liquid_owner),
            "eligible_shares": b["issued_shares"]-b["treasury_shares"],
            "issued_shares": b["issued_shares"], "lease_treatment": "operating cash rent; no lease debt deduction",
            "financial_income_assumed":0,
            "negative_initial_liquidity_is_not_filled_by_implicit_financing":True}
    snapshot(sink,"asset_bridge_candidate",result)
    close(extra,liquid_owner+nonliquid-call_pv+future_asset_pv
          +b["bridge_october_unknown_operating_cashflow"],"F0 decomposition")
    return result


def operating_forecast(data, s, sink=None):
    a, n = data["anchor"], data["periods"]
    domestic, overseas = a["domestic_revenue"], a["overseas_revenue"]
    revenue = domestic+overseas
    nwc = revenue*a["operating_nwc_ratio"]
    cash = revenue*a["operating_cash_ratio"]
    fixed = sum(a["fixed_operating_assets"])
    ic = nwc+cash+fixed
    anchor_ebit=domestic*a["domestic_ebit_margin"]+overseas*a["overseas_ebit_margin"]
    last_nopat=anchor_ebit-max(0.0,anchor_ebit)*a["tax_rate"]
    entity_nopat = {e["name"]: e["anchor_normalized_nopat"]*s["nci_profit_multipliers"][e["name"]]
                    for e in data["nci_entities"]}
    rows = []
    for i in range(n):
        snapshot(sink,"operating_year_start",{"year":i+1,"completed_rows":rows,
                 "opening_state":{"domestic":domestic,"overseas":overseas,"revenue":revenue,
                 "nwc":nwc,"operating_cash":cash,"fixed":fixed,"invested_capital":ic,
                 "last_nopat":last_nopat,"entity_nopat":dict(entity_nopat)},"parameters":s})
        d_factor = s["domestic_price_factors"][i]*s["domestic_volume_factors"][i]
        o_factor = 1+s["overseas_growth"][i]
        d_new, o_new = domestic*d_factor, overseas*o_factor
        sales = d_new+o_new
        ebit = d_new*s["domestic_ebit_margins"][i]+o_new*s["overseas_ebit_margins"][i]
        cash_tax=max(0.0,ebit)*s["tax_rate"]
        nopat=ebit-cash_tax
        da = sales*s["da_ratio"]
        maintenance = sales*s["maintenance_capex_ratio"]
        growth_capex = max(0.0, sales-revenue)*s["growth_fixed_capex_per_incremental_revenue"]
        capex = maintenance+growth_capex
        commitment_floor_extra = 0.0
        if i == 0:
            commitment_floor_extra = max(0.0, data["balance"]["signed_capex_commitment"]-capex)
            capex += commitment_floor_extra
        nwc_new, cash_new = sales*s["nwc_ratios"][i], sales*s["operating_cash_ratio"]
        delta_nwc, delta_cash = nwc_new-nwc, cash_new-cash
        reinvestment = capex-da+delta_nwc+delta_cash
        fcff = nopat+da-capex-delta_nwc-delta_cash
        fixed_new = fixed+capex-da
        ic_new = fixed_new+nwc_new+cash_new
        entities, nci_cf, nci_profit = [], 0.0, 0.0
        for e in data["nci_entities"]:
            growth = d_factor if e["growth_axis"] == "domestic" else o_factor
            enp = entity_nopat[e["name"]]*growth
            claim_np = enp*e["minority_fraction"]
            claim_cf = claim_np*(1-e["reinvestment_rate"])
            entities.append({"name":e["name"], "entity_nopat":enp,
                             "minority_fraction":e["minority_fraction"], "nci_nopat":claim_np,
                             "nci_cashflow":claim_cf, "reinvestment_rate":e["reinvestment_rate"],
                             "growth_to_retention_return_proxy":(growth-1)/e["reinvestment_rate"]
                             if e["reinvestment_rate"] else None})
            nci_profit += claim_np
            nci_cf += claim_cf
            entity_nopat[e["name"]] = enp
        snapshot(sink,"operating_raw_components",{"year":i+1,"revenue":sales,"nopat":nopat,
                 "da":da,"capex":capex,"delta_nwc":delta_nwc,"delta_cash":delta_cash,
                 "fcff":fcff,"net_reinvestment":reinvestment,"opening_ic":ic,"closing_ic":ic_new,
                 "nci_entities":entities,"completed_rows":rows})
        row = {"year":i+1, "phase":"explicit" if i < data["explicit_years"] else "transition",
               "domestic_revenue":d_new, "overseas_revenue":o_new, "revenue":sales,
               "ebit":ebit, "cash_operating_tax":cash_tax,"nopat":nopat,
               "negative_ebit_has_no_assumed_immediate_tax_refund":True,
               "embedded_rd_not_deducted_again":sales*s.get("embedded_rd_ratio",0),
               "da_excluding_rou":da, "maintenance_capex":maintenance, "growth_capex":growth_capex,
               "commitment_floor_extra_capex":commitment_floor_extra, "total_capex":capex,
               "operating_nwc":nwc_new, "operating_cash":cash_new, "delta_nwc":delta_nwc,
               "delta_operating_cash":delta_cash, "net_reinvestment":reinvestment, "fcff":fcff,
               "fixed_operating_assets":fixed_new, "opening_invested_capital":ic,
               "closing_invested_capital":ic_new, "nopat_to_average_ic":nopat/((ic+ic_new)/2),
               "incremental_roic":(nopat-last_nopat)/reinvestment if reinvestment > 0 else None,
               "incremental_roic_denominator_note": "positive net reinvestment" if reinvestment > 0 else "nonpositive denominator; not meaningful",
               "nci_entities":entities, "nci_nopat":nci_profit, "nci_cashflow":nci_cf,
               "owner_nopat":nopat-nci_profit, "owner_operating_cashflow":fcff-nci_cf,
               "discount_factor":(1+s["discount_rate"])**(i+1)}
        snapshot(sink,"operating_row_before_checks",{"completed_rows":rows,"candidate_row":row})
        close(fcff, nopat-reinvestment, f"Y{i+1} FCFF identity")
        close(ic_new-ic, reinvestment, f"Y{i+1} capital roll-forward")
        require(fixed_new >= 0 and nwc_new >= 0 and cash_new >= 0, "negative operating asset")
        rows.append(row)
        domestic, overseas, revenue, nwc, cash, fixed, ic, last_nopat = d_new, o_new, sales, nwc_new, cash_new, fixed_new, ic_new, nopat
    return rows


def terminal_budget(data, s, last, sink=None):
    snapshot(sink,"terminal_start",{"last_operating_row":last,"parameters":s})
    g, roc = s["terminal_growth"], s["terminal_incremental_roic"]
    sales = last["revenue"]*(1+g)
    nopat = last["nopat"]*(1+g)
    net_reinvestment = nopat*g/roc
    delta_nwc = last["operating_nwc"]*g
    delta_cash = last["operating_cash"]*g
    da = sales*s["da_ratio"]
    capex = da+net_reinvestment-delta_nwc-delta_cash
    maintenance = sales*s["maintenance_capex_ratio"]
    fcff = nopat-net_reinvestment
    entities = []
    for e in last["nci_entities"]:
        np = e["entity_nopat"]*(1+g)
        claim = np*e["minority_fraction"]
        cash = claim*(1-g/s["nci_terminal_incremental_roic"])
        entities.append({"name":e["name"], "entity_nopat":np, "nci_nopat":claim,
                         "nci_cashflow":cash, "incremental_roic":s["nci_terminal_incremental_roic"]})
    nci_nopat, nci_cf = sum(x["nci_nopat"] for x in entities), sum(x["nci_cashflow"] for x in entities)
    implied = nopat*g/net_reinvestment if net_reinvestment else None
    snapshot(sink,"terminal_raw_components",{"revenue":sales,"nopat":nopat,"net_reinvestment":net_reinvestment,
             "delta_nwc":delta_nwc,"delta_cash":delta_cash,"da":da,"capex":capex,
             "maintenance":maintenance,"fcff":fcff,"nci_entities":entities,
             "capital_return_denominator":last["closing_invested_capital"]+net_reinvestment/2})
    result={"year":data["periods"]+1, "revenue":sales, "nopat":nopat, "growth":g,
            "incremental_roic_input":roc, "forward_incremental_roic_from_reinvestment":implied,
            "net_reinvestment":net_reinvestment, "reinvestment_fraction":g/roc,
            "delta_nwc":delta_nwc, "delta_operating_cash":delta_cash,
            "da_excluding_rou":da, "total_capex":capex, "maintenance_capex_floor":maintenance,
            "maintenance_headroom":capex-maintenance, "fcff":fcff, "nci_entities":entities,
            "nci_nopat":nci_nopat, "nci_cashflow":nci_cf, "owner_nopat":nopat-nci_nopat,
            "owner_operating_cashflow":fcff-nci_cf,
            "existing_capital_return":nopat/(last["closing_invested_capital"]+net_reinvestment/2)}
    economic_issues=[]
    if capex+0.01 < maintenance:
        economic_issues.append({"year":data["periods"]+1,
              "classification":"TERMINAL_MAINTENANCE_BUDGET_UNCOVERED",
              "raw_capex":capex,"required_maintenance":maintenance,
              "shortfall":maintenance-capex,
              "note":"Economic reinvestment/growth budget inconsistent; not a program arithmetic error"})
    if capex < 0:
        economic_issues.append({"year":data["periods"]+1,
              "classification":"TERMINAL_NEGATIVE_FIXED_CAPEX_BUDGET",
              "raw_capex":capex,"note":"No automatic liquidation or financing assumed"})
    result["economic_budget_executable"]=not economic_issues
    result["economic_budget_issues"]=economic_issues
    result["formal_fcff"]=fcff if not economic_issues else None
    snapshot(sink,"terminal_before_checks",result)
    close(fcff, nopat+da-capex-delta_nwc-delta_cash, "terminal FCFF identity")
    if implied is not None:
        close(implied, roc, "forward incremental ROIC", absolute=1e-12)
    return result


def dividends(data, s, rows, terminal, bridge, sink=None):
    p,b=data["distribution"],data["balance"]
    unpaid=bridge["fund_unpaid_proxy"]
    parent_raw=(p["parent_cash_h1"]*p["parent_cash_availability_haircut"]
                -b["dividend_paid_after_q3_before_cutoff"]-p["parent_borrowing_settlement_proxy"]
                -p["parent_operating_cash_floor"])
    parent_cash=parent_raw
    group_cash=bridge["initial_owner_liquid_pool_before_future_fund_call"]
    re=p["parent_re_h1"]-b["dividend_paid_after_q3_before_cutoff"]
    reserve=p["statutory_reserve"]
    result,issues=[],[]

    def record_gaps(year,group,parent):
        found=[]
        if group < 0:
            found.append({"year":year,"classification":"GROUP_NECESSARY_FUNDING_UNCOVERED",
                          "group_balance":group,"group_gap":-group,
                          "note":"Model funding/required operating-cash deficit; not a claim of observed issuer default"})
        if parent < 0:
            found.append({"year":year,"classification":"PARENT_POLICY_OR_ACCESS_TIMING_GAP",
                          "parent_balance":parent,"parent_gap":-parent,
                          "group_balance":group,"group_itself_negative":group<0,
                          "note":"Under assumed parent funding of all negative owner FCF / limited access; not a proven legal obligation or group-wide insolvency"})
        return found

    issues.extend(record_gaps(0,group_cash,parent_cash))
    feasible=not issues
    initial={"initial_parent_free_cash_raw":parent_raw,"initial_owner_liquid_pool_raw":group_cash,
             "initial_parent_re":re,"initial_statutory_reserve":reserve,
             "future_fund_call_amount":unpaid,"fund_call_year":b["fund_call_year"],
             "future_reservation_headroom_parent":parent_raw-unpaid,
             "future_reservation_headroom_group":group_cash-unpaid,
             "reservation_is_not_yet_a_hard_payment":True,"issues":list(issues)}
    snapshot(sink,"distribution_initial_state",initial)
    for i,row in enumerate(rows+[terminal]):
        snapshot(sink,"distribution_year_start",{"year":row["year"],"completed_rows":result,
                 "signed_opening_parent_cash":parent_cash,"signed_opening_group_cash":group_cash,
                 "opening_re":re,"opening_reserve":reserve,"path_feasible_so_far":feasible,
                 "operating_row":row,"issues":list(issues)})
        access_ratio=s["parent_cash_access"][min(i,len(s["parent_cash_access"])-1)]
        owner_cf,owner_np=row["owner_operating_cashflow"],row["owner_nopat"]
        parent_income=owner_np*p["parent_income_fraction_of_owner_nopat"]
        profit_after_loss_absorption=max(0.0,parent_income-max(0.0,-re))
        transfer=min(profit_after_loss_absorption*p["statutory_ratio"],
                     max(0.0,p["registered_capital"]*p["statutory_capital_threshold"]-reserve))
        accessible_cash=owner_cf*access_ratio if owner_cf>=0 else owner_cf
        call=unpaid if row["year"]==b["fund_call_year"] else 0.0
        before_parent,before_group,before_re=parent_cash,group_cash,re
        parent_available=before_parent+accessible_cash-call
        group_available=before_group+owner_cf-call
        re_available=before_re+parent_income-transfer
        new_issues=record_gaps(row["year"],group_available,parent_available)
        if i==len(rows):
            new_issues.extend(terminal.get("economic_budget_issues",[]))
        issues.extend(new_issues)
        feasible=feasible and not new_issues
        target=max(0.0,owner_np*p["target_payout_of_owner_nopat"])
        paid=max(0.0,min(target,parent_available,group_available,max(0.0,re_available))) if feasible else None
        shadow_paid=paid if paid is not None else 0.0
        parent_cash=parent_available-shadow_paid
        group_cash=group_available-shadow_paid
        re=re_available-shadow_paid
        reserve+=transfer
        candidate={"year":row["year"],"phase":"terminal_first_year" if i==len(rows) else row["phase"],
             "path_executable":feasible,"opening_parent_free_cash":before_parent,
             "opening_owner_group_liquid_pool":before_group,"owner_external_operating_cashflow":owner_cf,
             "cash_access_fraction":access_ratio,"cash_available_to_parent":accessible_cash,
             "negative_FCF_parent_support_is_policy_not_legal_fact":True,
             "fund_cash_call_once":call,"parent_before_D":parent_available,"group_before_D":group_available,
             "internal_cash_relocation_not_new_group_cash":True,
             "parent_normalized_income_proxy":parent_income,
             "profit_after_prior_loss_absorption":profit_after_loss_absorption,"statutory_transfer":transfer,
             "statutory_reserve_close":reserve,"discretionary_reserve":p["discretionary_reserve"],
             "opening_parent_re":before_re,"re_available_before_distribution":re_available,
             "target_D":target,"actual_D":paid,
             "D_per_eligible_share":paid/bridge["eligible_shares"] if paid is not None else None,
             "closing_parent_free_cash":parent_cash if feasible else None,
             "closing_owner_group_liquid_pool":group_cash if feasible else None,
             "closing_parent_re":re if feasible else None,
             "signed_shadow_closing_parent_free_cash":parent_cash,
             "signed_shadow_closing_owner_group_liquid_pool":group_cash,
             "signed_shadow_closing_parent_re":re,"shadow_D_without_funding":shadow_paid,
             "shadow_policy":"After an unresolved gap, continue frozen operating budget with no financing and no dividends; later positive balance does not cure past missing funding",
             "unremitted_operating_cash_in_group":owner_cf-accessible_cash,
             "constraint_binding":paid+0.01<target if paid is not None else None,
             "new_economic_issues":new_issues,"all_unresolved_issues":list(issues)}
        snapshot(sink,"distribution_row_before_checks",{"completed_rows":result,"candidate_row":candidate})
        close(before_parent+accessible_cash-call-shadow_paid,parent_cash,"parent signed cash roll-forward")
        close(before_group+owner_cf-call-shadow_paid,group_cash,"owner group signed cash roll-forward")
        close(before_re+parent_income-transfer-shadow_paid,re,"parent RE roll-forward")
        if paid is not None:
            require(paid>=0 and paid<=max(0.0,re_available)+0.01,"distribution exceeds available RE")
            require(parent_cash>=-0.01 and group_cash>=-0.01,"inconsistent executable liquidity state")
        require(transfer<=profit_after_loss_absorption*p["statutory_ratio"]+0.01,
                "reserve transfer made before loss absorption")
        result.append(candidate)
    output={**initial,"initial_parent_cash_shortfall":min(0.0,parent_raw),
            "purpose":"same-policy executable D and signed no-financing shadow; not another valuation addend",
            "economic_path_executable_through_terminal_first_year":feasible,
            "economic_issues":issues,"first_gap_year":min((x["year"] for x in issues),default=None),
            "group_funding_deficit_present":any(x["classification"]=="GROUP_NECESSARY_FUNDING_UNCOVERED" for x in issues),
            "parent_policy_or_timing_gap_present":any(x["classification"]=="PARENT_POLICY_OR_ACCESS_TIMING_GAP" for x in issues),
            "rows":result}
    snapshot(sink,"distribution_complete",output)
    return output


def year_five_equity(data,s,rows,terminal,bridge,distributions,current_equity,sink=None):
    y=data["explicit_years"]
    require(y==5,"This interface is explicitly the post-D Y5 state")
    r,g=s["discount_rate"],s["terminal_growth"]
    tail=[x for x in rows if x["year"]>y]
    leaves=[{"year":x["year"],"consolidated_fcff":x["fcff"],"nci_cashflow":x["nci_cashflow"],
             "discount_to_Y5":(1+r)**(x["year"]-y),
             "consolidated_pv_at_Y5":x["fcff"]/(1+r)**(x["year"]-y),
             "nci_pv_at_Y5":x["nci_cashflow"]/(1+r)**(x["year"]-y)} for x in tail]
    terminal_full=terminal["fcff"]/(r-g)/(1+r)**(data["periods"]-y)
    terminal_nci=terminal["nci_cashflow"]/(r-g)/(1+r)**(data["periods"]-y)
    ev5=sum(x["consolidated_pv_at_Y5"] for x in leaves)+terminal_full
    nci5=sum(x["nci_pv_at_Y5"] for x in leaves)+terminal_nci
    op5=ev5-nci5
    d5=distributions["rows"][y-1]
    state_valid=d5["path_executable"]
    future_gaps=[x for x in distributions["economic_issues"] if x["year"]>y]
    u=bridge["fund_unpaid_proxy"]
    call_year=data["balance"]["fund_call_year"]
    h=data["balance"]["fund_future_asset_recovery"]
    called=u if call_year<=y else 0.0
    fund_asset=h*called
    future_net=(h*u-u)/(1+r)**(call_year-y) if call_year>y else 0.0
    nonliquid=bridge["initial_nonliquid_financial_assets"]
    shadow_g5=d5["signed_shadow_closing_owner_group_liquid_pool"]
    financial_shadow=shadow_g5+nonliquid+fund_asset+future_net
    actual_financial=(d5["closing_owner_group_liquid_pool"]+nonliquid+fund_asset+future_net) if state_valid else None
    actual_equity=op5+actual_financial if actual_financial is not None else None
    formal_executable=(state_valid and distributions["economic_path_executable_through_terminal_first_year"]
                       and terminal["economic_budget_executable"])
    formal_equity=actual_equity if formal_executable else None
    paid_rows=distributions["rows"][:y]
    observed_D_all=all(x["actual_D"] is not None for x in paid_rows)
    paid_sum=sum(x["actual_D"] for x in paid_rows) if observed_D_all else None
    shadow_D_sum=sum(x["shadow_D_without_funding"] for x in paid_rows)
    d_pv=sum(x["actual_D"]/(1+r)**x["year"] for x in paid_rows) if observed_D_all else None
    five_year_wealth_pv=d_pv+actual_equity/(1+r)**y if d_pv is not None and actual_equity is not None else None
    status=("NOT_EXECUTABLE_PRE_Y5_FUNDING_OR_PARENT_POLICY_GAP" if not state_valid else
            ("Y5_STATE_VALID_VALUE_CONDITIONAL_ON_POST_Y5_FUNDS_OR_ECONOMIC_BUDGET" if future_gaps else
             "Y5_POST_D_STATE_VALID_THROUGH_TERMINAL_FIRST_YEAR_CHECK"))
    result={"date":"2031-10-31 after Y5 dividend","year":y,"status":status,
            "state_executable_through_Y5":state_valid,"post_Y5_economic_issues":future_gaps,
            "post_Y5_new_funding_gaps_absent":not future_gaps,
            "full_policy_path_executable_through_terminal_first_year":distributions["economic_path_executable_through_terminal_first_year"],
            "remaining_operating_value_always_conditional_on_frozen_operating_budget":True,
            "remaining_cashflow_leaves":leaves,"terminal_consolidated_pv_at_Y5":terminal_full,
            "terminal_nci_pv_at_Y5":terminal_nci,"remaining_consolidated_operating_value":ev5,
            "remaining_nci_operating_value":nci5,"remaining_owner_operating_value":op5,
            "initial_owner_liquid_pool_L0":bridge["initial_owner_liquid_pool_before_future_fund_call"],
            "first_five_owner_FCF":sum(x["owner_operating_cashflow"] for x in rows[:y]),
            "first_five_actual_D":paid_sum,"known_D_before_gap_partial_sum":sum(x["actual_D"] for x in paid_rows if x["actual_D"] is not None),
            "fund_call_paid_by_Y5":called,"fund_asset_at_Y5":fund_asset,
            "fund_net_future_value_if_not_called":future_net,"nonliquid_financial_assets_I0":nonliquid,
            "financial_income_cumulative":0,"group_liquid_pool_after_Y5_D":d5["closing_owner_group_liquid_pool"],
            "signed_shadow_group_liquid_pool_after_Y5":shadow_g5,
            "financial_bridge_after_Y5_D":actual_financial,"signed_shadow_financial_bridge":financial_shadow,
            "equity_after_Y5_D":actual_equity,
            "formal_equity_after_Y5_D":formal_equity,
            "formal_per_eligible_share":formal_equity/bridge["eligible_shares"] if formal_equity is not None else None,
            "conditional_equity_after_Y5_D":actual_equity if actual_equity is not None else op5+financial_shadow,
            "terminal_economic_budget_executable":terminal["economic_budget_executable"],
            "independent_field_mapping":"independent actual Y5 -> formal_equity_after_Y5_D; independent conditional -> conditional_equity_after_Y5_D plus matching real/shadow financial-state status",
            "per_eligible_share":actual_equity/bridge["eligible_shares"] if actual_equity is not None else None,
            "per_fully_issued_share":actual_equity/bridge["issued_shares"] if actual_equity is not None else None,
            "conditional_shadow_equity_if_frozen_operations_continue_without_recorded_funding_resolution":op5+financial_shadow,
            "shadow_equity_is_not_an_executable_funded_path":not state_valid,
            "D1_to_D5_pv":d_pv,"D_plus_Y5_wealth_pv":five_year_wealth_pv,
            "current_DCF_minus_D_and_Y5_wealth_pv":current_equity-five_year_wealth_pv if five_year_wealth_pv is not None else None,
            "wealth_pv_difference_note":"Zero financial return on retained cash produces timing/capital-allocation drag; not forced to zero or funded at discount rate",
            "no_second_deduction_of_operating_cash_borrowings_NCI_cash_paid_dividend_or_called_fund":True}
    snapshot(sink,"Y5_before_identity_checks",result)
    shadow_expected=(bridge["initial_owner_liquid_pool_before_future_fund_call"]
                     +result["first_five_owner_FCF"]-called-shadow_D_sum)
    close(shadow_g5,shadow_expected,"Y5 signed liquid-pool identity")
    close(financial_shadow,shadow_g5+nonliquid+fund_asset+future_net,"Y5 financial bridge")
    if actual_equity is not None:
        close(actual_equity,op5+actual_financial,"Y5 equity bridge")
    return result


def auxiliary_income_capitalization(data, s, bridge, sink=None):
    """Independent scalar earnings build; does not consume primary forecast rows."""
    a, k = data["anchor"], s["aux_normalization_year"]
    dom, foreign = a["domestic_revenue"], a["overseas_revenue"]
    old_rev = dom+foreign
    old_nwc, old_cash = old_rev*a["operating_nwc_ratio"], old_rev*a["operating_cash_ratio"]
    np_entities = {e["name"]:e["anchor_normalized_nopat"]*s["nci_profit_multipliers"][e["name"]]
                   for e in data["nci_entities"]}
    prefix, prefix_nci, prefix_rows = 0.0, 0.0, []
    for j in range(k):
        snapshot(sink,"aux_year_start",{"year":j+1,"prefix_rows":prefix_rows,
                 "domestic":dom,"foreign":foreign,"old_revenue":old_rev,
                 "old_nwc":old_nwc,"old_operating_cash":old_cash,"entities":dict(np_entities)})
        dfactor = s["domestic_price_factors"][j]*s["domestic_volume_factors"][j]
        ofactor = 1+s["overseas_growth"][j]
        dom, foreign = dom*dfactor, foreign*ofactor
        rev = dom+foreign
        operating_profit=dom*s["domestic_ebit_margins"][j]+foreign*s["overseas_ebit_margins"][j]
        operating_cash_tax=max(0.0,operating_profit)*s["tax_rate"]
        np=operating_profit-operating_cash_tax
        depreciation = rev*s["da_ratio"]
        maintenance = rev*s["maintenance_capex_ratio"]
        new_nwc, new_cash = rev*s["nwc_ratios"][j], rev*s["operating_cash_ratio"]
        investment = maintenance+max(0,rev-old_rev)*s["growth_fixed_capex_per_incremental_revenue"]
        if j==0:
            investment=max(investment,data["balance"]["signed_capex_commitment"])
        full_cf=np+depreciation-investment-(new_nwc-old_nwc)-(new_cash-old_cash)
        minority_np, minority_cf=0.0,0.0
        for e in data["nci_entities"]:
            np_entities[e["name"]] *= dfactor if e["growth_axis"]=="domestic" else ofactor
            claim=np_entities[e["name"]]*e["minority_fraction"]
            minority_np+=claim
            minority_cf+=claim*(1-e["reinvestment_rate"])
        snapshot(sink,"aux_row_before_capitalization",{"year":j+1,"domestic":dom,"overseas":foreign,
                 "revenue":rev,"ebit":operating_profit,"cash_tax":operating_cash_tax,
                 "nopat":np,"depreciation":depreciation,"maintenance":maintenance,
                 "capex":investment,"nwc":new_nwc,"operating_cash":new_cash,"full_cf":full_cf,
                 "minority_nopat":minority_np,"minority_cf":minority_cf,"prefix_rows":prefix_rows})
        if j<k-1:
            discount=(1+s["discount_rate"])**(j+1)
            prefix+=full_cf/discount
            prefix_nci+=minority_cf/discount
            prefix_rows.append({"year":j+1,"consolidated_fcff":full_cf,"nci_cashflow":minority_cf,
                                "consolidated_pv":full_cf/discount,"nci_pv":minority_cf/discount})
        old_rev,old_nwc,old_cash=rev,new_nwc,new_cash
    net_maintenance=maintenance-depreciation
    total_growth_reinvestment=np*s["terminal_growth"]/s["terminal_incremental_roic"]
    additional_growth=max(0.0,total_growth_reinvestment-net_maintenance)
    normal_cash=np+depreciation-maintenance-additional_growth
    minority_normal_cash=minority_np*(1-s["terminal_growth"]/s["nci_terminal_incremental_roic"])
    normal_owner_cash=normal_cash-minority_normal_cash
    normal_net_reinvestment=net_maintenance+additional_growth
    normal_delta_working_and_cash=(new_nwc+new_cash)*s["terminal_growth"]/(1+s["terminal_growth"])
    normal_implied_fixed_capex=depreciation+normal_net_reinvestment-normal_delta_working_and_cash
    normalization_issues=[]
    if normal_implied_fixed_capex+0.01 < maintenance:
        normalization_issues.append({"classification":"AUX_NORMALIZATION_MAINTENANCE_OR_WORKING_CAPITAL_UNDERFUNDED",
             "implied_fixed_capex":normal_implied_fixed_capex,"maintenance":maintenance,
             "normal_growth_working_and_cash_need":normal_delta_working_and_cash})
    if normal_owner_cash < 0:
        normalization_issues.append({"classification":"AUX_NORMALIZATION_NEGATIVE_OWNER_CASH_REQUIRES_ONGOING_SUPPORT",
                                    "normal_owner_cash":normal_owner_cash})
    capitalized_full=normal_cash/(s["discount_rate"]-s["terminal_growth"])
    capitalized_nci=minority_normal_cash/(s["discount_rate"]-s["terminal_growth"])
    discount=(1+s["discount_rate"])**(k-1)
    operating_owner_value=prefix-prefix_nci+(capitalized_full-capitalized_nci)/discount
    equity=operating_owner_value+bridge["net_nonoperating_owner_value"]
    result={"method":"方法二：正常化普通股经营收益与资本回报约束的收益资本化（辅助方法）",
            "normalization_year":k,"normalized_domestic_revenue":dom,"normalized_overseas_revenue":foreign,
            "normalized_consolidated_nopat":np,"normalized_nci_nopat":minority_np,
            "normalized_operating_cash_tax":operating_cash_tax,
            "negative_ebit_has_no_assumed_immediate_tax_refund":True,
            "D_and_A_addback":depreciation,"cash_maintenance_deduction":maintenance,
            "net_maintenance_already_counted_as_reinvestment":net_maintenance,
            "growth_total_net_reinvestment_requirement":total_growth_reinvestment,
            "additional_growth_deduction_after_net_maintenance":additional_growth,
            "normalized_consolidated_owner_cash":normal_cash,"normalized_minority_cash":minority_normal_cash,
            "normalized_parent_owner_cash":normal_owner_cash,"prefix_rows":prefix_rows,
            "normalization_budget_executable":not normalization_issues,
            "normalization_economic_issues":normalization_issues,
            "normalization_total_net_reinvestment":normal_net_reinvestment,
            "normalization_growth_working_and_operating_cash_need":normal_delta_working_and_cash,
            "normalization_implied_fixed_capex":normal_implied_fixed_capex,
            "capitalized_value_at_end_year":k-1,"capitalized_consolidated_value":capitalized_full,
            "capitalized_nci_value":capitalized_nci,"operating_owner_value":operating_owner_value,
            "nonoperating_owner_bridge":bridge["net_nonoperating_owner_value"],"equity_value":equity,
            "per_eligible_share":equity/bridge["eligible_shares"],
            "per_fully_issued_share":equity/bridge["issued_shares"],
            "limitation":"Y3 normalized earnings capitalization does not credit the full primary Y3-Y8 growth path; shared economics, distinct timing/growth representation; not independent numerical verification"}
    snapshot(sink,"aux_complete_before_final_checks",result)
    return result


def evaluate(data, scenario_name, override=None, sink=None):
    s=dict(data["scenarios"][scenario_name])
    if override:
        s.update(override)
    snapshot(sink,"evaluate_input_before_validation",{"scenario":scenario_name,"inputs":data,
             "override":override,"effective_scenario":s})
    validate(data,s)
    bridge=asset_bridge(data,s,sink)
    rows=operating_forecast(data,s,sink)
    terminal=terminal_budget(data,s,rows[-1],sink)
    rate,g=s["discount_rate"],s["terminal_growth"]
    cf_pv=sum(x["fcff"]/x["discount_factor"] for x in rows)
    nci_pv=sum(x["nci_cashflow"]/x["discount_factor"] for x in rows)
    terminal_ev=terminal["fcff"]/(rate-g)
    terminal_nci=terminal["nci_cashflow"]/(rate-g)
    terminal_df=(1+rate)**data["periods"]
    enterprise=cf_pv+terminal_ev/terminal_df
    nci_value=nci_pv+terminal_nci/terminal_df
    owner_operating=enterprise-nci_value
    equity=owner_operating+bridge["net_nonoperating_owner_value"]
    snapshot(sink,"primary_valuation_before_distribution",{"consolidated_cashflow_pv":cf_pv,
             "nci_cashflow_pv":nci_pv,"terminal_ev":terminal_ev,"terminal_nci":terminal_nci,
             "enterprise_value":enterprise,"nci_value":nci_value,"owner_operating_value":owner_operating,
             "financial_bridge":bridge,"conditional_current_equity":equity})
    distributions=dividends(data,s,rows,terminal,bridge,sink)
    auxiliary=auxiliary_income_capitalization(data,s,bridge,sink)
    y5=year_five_equity(data,s,rows,terminal,bridge,distributions,equity,sink)
    warnings=[]
    threshold=data["diagnostic_limits"]["year_on_year_jump_warning"]
    jumps=[]
    drows=distributions["rows"]
    for previous,current in zip(drows,drows[1:]):
        ratio=(current["actual_D"]/previous["actual_D"]-1
               if previous["actual_D"] is not None and previous["actual_D"]!=0
               and current["actual_D"] is not None else None)
        jumps.append({"from_year":previous["year"],"to_year":current["year"],"D_change_fraction":ratio})
        if ratio is not None and abs(ratio)>threshold:
            warnings.append(f"D jump {previous['year']}->{current['year']}; inspect cash/RE constraint and transition, do not auto-tune")
    for row in rows:
        if row["incremental_roic"] is not None and row["incremental_roic"]>data["diagnostic_limits"]["incremental_roic_warning"]:
            warnings.append(f"Y{row['year']} high incremental ROIC; inspect margin recovery / spare capacity / capital needs")
        for e in row["nci_entities"]:
            q=e["growth_to_retention_return_proxy"]
            if q is not None and q>data["diagnostic_limits"]["incremental_roic_warning"] and e["entity_nopat"]:
                warnings.append(f"Y{row['year']} {e['name']} high growth/retention proxy; entity simplification risk")
    tv_share=(terminal_ev-terminal_nci)/terminal_df/owner_operating if owner_operating else None
    if tv_share is not None and tv_share>data["diagnostic_limits"]["terminal_value_share_warning"]:
        warnings.append("High terminal-value dependence")
    terminal_change=terminal["owner_operating_cashflow"]/rows[-1]["owner_operating_cashflow"]-1 if rows[-1]["owner_operating_cashflow"] else None
    if terminal_change is not None and abs(terminal_change)>threshold:
        warnings.append("Y8->terminal owner FCF jump; review reinvestment and growth fade")
    if distributions["economic_issues"]:
        warnings.append("Unresolved group funding, parent-policy/access timing gap, or terminal economic-budget condition; inspect classified issues; actual D/Y5 state may be null; no implicit financing")
    condition=("FROZEN_OPERATING_BUDGET_AND_D_PATH_EXECUTABLE_THROUGH_TERMINAL_FIRST_YEAR_CHECK"
               if distributions["economic_path_executable_through_terminal_first_year"] else
               "CONDITIONAL_CURRENT_ASSET_VALUE_FROZEN_OPERATIONS_WITH_UNRESOLVED_FUNDING_OR_PARENT_POLICY_PATH")
    if not terminal["economic_budget_executable"]:
        condition="CONDITIONAL_ONLY_TERMINAL_REINVESTMENT_OR_MAINTENANCE_BUDGET_INCONSISTENT"
        warnings.append("Terminal maintenance/capital budget inconsistent: formal current valuation is null; raw conditional arithmetic retained without retuning")
    auxiliary["economic_condition"]=("AUX_NORMALIZATION_EXECUTABLE_WITH_PRIMARY_TERMINAL_PATH_CONDITION"
               if auxiliary["normalization_budget_executable"] and not terminal["economic_budget_executable"] else condition)
    auxiliary["conditional_equity_value"]=auxiliary["equity_value"]
    auxiliary["conditional_per_eligible_share"]=auxiliary["per_eligible_share"]
    auxiliary["conditional_per_fully_issued_share"]=auxiliary["per_fully_issued_share"]
    method_difference=auxiliary["equity_value"]-equity
    if not auxiliary["normalization_budget_executable"]:
        warnings.append("Auxiliary normalization has its own reinvestment/owner-cash inconsistency: auxiliary formal value null, conditional value and own constraints retained")
        auxiliary["economic_condition"]="CONDITIONAL_ONLY_AUXILIARY_NORMALIZATION_BUDGET_INCONSISTENT"
        auxiliary["equity_value"]=None
        auxiliary["per_eligible_share"]=None
        auxiliary["per_fully_issued_share"]=None
    result={"scenario":scenario_name,"effective_scenario_parameters":s,
            "economic_condition":condition,
            "method_one":{"method":"方法一：经营现金流DCF（主方法）","explicit_and_transition_rows":rows,
                          "terminal":terminal,"consolidated_cashflow_pv":cf_pv,"nci_cashflow_pv":nci_pv,
                          "terminal_enterprise_value_at_Y8":terminal_ev,"terminal_nci_value_at_Y8":terminal_nci,
                          "enterprise_value":enterprise,"nci_operating_economic_value":nci_value,
                          "owner_operating_value":owner_operating,"asset_bridge":bridge,
                          "conditional_equity_value":equity,
                          "equity_value":equity if terminal["economic_budget_executable"] else None,
                          "equity_value_is_conditional_on_frozen_operating_budget":True,
                          "conditional_per_eligible_share":equity/bridge["eligible_shares"],
                          "per_eligible_share":equity/bridge["eligible_shares"] if terminal["economic_budget_executable"] else None,
                          "per_fully_issued_share":equity/bridge["issued_shares"] if terminal["economic_budget_executable"] else None},
            "method_two":auxiliary,"same_base_D_path":distributions,"same_base_Y5_equity_after_D":y5,
            "diagnostics":{"warnings":warnings,"D_year_changes":jumps,
                           "terminal_share_of_owner_operating_value":tv_share,
                           "Y8_to_terminal_owner_FCF_change":terminal_change,
                           "Y5_D":drows[data["explicit_years"]-1],
                           "conditional_methods_difference_not_averaged":method_difference,
                           "all_hard_identity_checks_passed":True}}
    snapshot(sink,"full_result_before_final_checks",result)
    finite_tree(result)
    return result
