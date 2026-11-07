#!/usr/bin/env python3
"""Narrow saved-state valuation bridge. No forecasts, original model imports, quotes or network.
Amounts CNY billion; shares million. Current valuation bridge over the complete operating states.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import sys
import traceback


def close(a,b,tolerance,label):
    if not math.isfinite(a) or not math.isfinite(b) or abs(a-b)>tolerance:
        raise AssertionError(f"{label}: {a!r} != {b!r}")


def transfer_fraction(p):
    return ((1-p["mother_own_operating_share"])*p["subsidiary_upstream_fraction"]
            *p["additional_upstream_tax_rate"])


def forward_cash_contract(state,p):
    years=p["forward_fiscal_years"]
    weights=p["forward_weights_numerator"]
    denominator=p["forward_weight_denominator"]
    rows=[state["giga_forward_fiscal"][str(y)] for y in years]
    def weighted(key):return sum(row[key]*w/denominator for row,w in zip(rows,weights))
    # The bridge relies on a mature no-SBC/no-one-off state already saved, not invented addbacks.
    for row in rows:
        if row["known_sbc"]!=0 or row["inventory_impairment"]!=0:
            raise ValueError("Forward exceptional expense requires an explicit revised cash contract")
    share=p["giga_parent_operating_share"]
    nopat=weighted("parent_nopat")
    capex=weighted("capex")
    da=weighted("da")
    noncurrent=capex-da
    nwc=weighted("nwc_change")
    parent_investment=(noncurrent+nwc)*share
    saved_parent_fcff=weighted("parent_fcff")
    close(nopat-parent_investment,saved_parent_fcff,p["comparison_roundoff_tolerance_bn"],"forward NOPAT/investment/FCFF")
    tax=nopat*transfer_fraction(p)
    g=p["mature_growth"]
    initial_capital=state["giga_holding"][-1]["invested_capital"]*share
    if parent_investment<=0 or initial_capital<=0:
        raise ValueError("This maturity contract needs positive necessary investment and initial capital")
    return {"source_fiscal_years":years,"weights_numerator":weights,"weight_denominator":denominator,
            "forward_parent_nopat":nopat,"forward_cash_capex_consolidated":capex,
            "forward_da_consolidated":da,"maintenance_proxy_historical_da_not_verified_replacement_cost":da,
            "forward_noncurrent_net_investment_consolidated":noncurrent,
            "forward_nwc_net_investment_consolidated":nwc,"forward_parent_net_investment":parent_investment,
            "forward_parent_fcff_before_upstream_tax":saved_parent_fcff,"forward_upstream_tax":tax,
            "forward_owner_fcff":saved_parent_fcff-tax,"mature_growth":g,
            "forward_expensed_rd_consolidated":weighted("rd_expense"),
            "forward_capitalized_rd_cash_consolidated":weighted("capitalized_rd_cash"),
            "initial_h10_parent_capital":initial_capital,
            "initial_forward_nopat_over_h10_capital":nopat/initial_capital,
            "asymptotic_nopat_over_prior_capital":g*nopat/parent_investment,
            "asymptotic_nopat_over_end_capital":g*nopat/((1+g)*parent_investment),
            "capital_roll_formula":"K_k=K_0+J_1*((1+g)^k-1)/g; no forced immediate K growth at g",
            "high_return_not_clamped":True,"not_a_proven_future_efficiency_fact":True}


def operating_values(flows,terminal_cash,rate,growth,horizon=5):
    if rate<=growth or rate<=-1:raise ValueError("operating rate must exceed growth")
    if len(flows)!=10 or horizon!=5:raise ValueError("saved contract is ten explicit years and year5")
    terminal=terminal_cash/(rate-growth)
    current_flows=sum(c/(1+rate)**(i+1) for i,c in enumerate(flows))
    remaining_flows=sum(c/(1+rate)**(i+1-horizon) for i,c in enumerate(flows) if i>=horizon)
    current_terminal=terminal/(1+rate)**len(flows)
    remaining_terminal=terminal/(1+rate)**(len(flows)-horizon)
    return {"rate":rate,"growth":growth,"terminal_at_h10":terminal,
            "current_explicit_pv":current_flows,"current_terminal_pv":current_terminal,
            "current_operating_value":current_flows+current_terminal,
            "year5_remaining_explicit_pv":remaining_flows,"year5_terminal_pv":remaining_terminal,
            "year5_remaining_operating_value":remaining_flows+remaining_terminal,
            "current_operating_terminal_fraction":current_terminal/(current_flows+current_terminal)}


def financing_pv(holder,p):
    rate=p["r_bridge"]
    if rate<=-1:raise ValueError("invalid bridge discount rate")
    rows=[]
    for h in holder:
        year=h["holding_year"]
        factor=(1+rate)**year
        rows.append({"holding_year":year,"discount_factor":factor,
                     "subscription_cash":h["subscription_cash"],
                     "fund_fair_value_shortfall_cash":h["fund_contribution_cash"]-h["new_fund_value"],
                     "extra_unmatched_capital_cash":h["extra_unmatched_capital_cash"],
                     "cash_award_delivery":h["H_cash_delivery"]})
    def pv(key):return sum(row[key]/row["discount_factor"] for row in rows)
    subscription=pv("subscription_cash");fund=pv("fund_fair_value_shortfall_cash")
    capital=pv("extra_unmatched_capital_cash");awards=pv("cash_award_delivery")
    return {"r_bridge":rate,"subscription_cash_pv":subscription,"fund_fair_value_shortfall_pv":fund,
            "extra_unmatched_capital_pv":capital,"cash_award_delivery_pv":awards,
            "net_financing_pv":subscription-fund-capital-awards,"cash_rows":rows,
            "same_for_all_operating_parameter_points":True}


def auxiliary_epv_contract(state,p):
    h5=state["giga_holding"][p["holder_horizon"]-1]
    fy=state["giga_normalization_fiscal_2031"]
    share=p["giga_parent_operating_share"]
    rent_loss=(fy["segment_revenue"]["memory"]
               *max(0,fy["segment_gross_margin"]["memory"]-p["auxiliary_normal_memory_margin"])
               *(1-p["giga_operating_tax_rate"])*share)
    normalized_nopat=h5["parent_nopat"]-rent_loss
    maintenance=h5["capex"]*share
    da=h5["da"]*share
    tax=normalized_nopat*transfer_fraction(p)
    cash=normalized_nopat+da-maintenance-tax
    return {"method":"zero_nominal_growth_normalized_earnings_power",
            "normalized_parent_nopat_no_growth_uplift":normalized_nopat,
            "memory_rent_normalization_taxed_parent_loss":rent_loss,
            "parent_da_addback":da,"parent_full_h5_cash_capex_maintenance_allowance":maintenance,
            "upstream_tax":tax,"annual_owner_maintenance_cash":cash,"growth":0.0,
            "working_capital_release":0.0,"expensed_rd_deducted_again":False,
            "sbc_addback":0.0,"not_a_liquidation_or_guaranteed_value_floor":True,
            "normalization_mechanism":"Price/rent normalization at frozen H5 physical scale; no working-capital release. Full saved capex remains a conservative recurring upkeep allowance, including any unseparated growth portion."}


def auxiliary_value(flows,epv,rate,current_nonoperating):
    if rate<=0:raise ValueError("zero-growth EPV requires positive return")
    first5=sum(c/(1+rate)**(i+1) for i,c in enumerate(flows[:5]))
    capitalized=epv["annual_owner_maintenance_cash"]/rate
    tail_pv=capitalized/(1+rate)**5
    return {"rate":rate,"first_five_operating_cash_pv":first5,"zero_growth_operating_epv_at_year5":capitalized,
            "zero_growth_epv_present_value":tail_pv,"current_operating_reference":first5+tail_pv,
            "current_equity_reference":first5+tail_pv+current_nonoperating,
            "same_financial_bridge_not_same_operating_tail":True}


def patch_state(state,p):
    tol=p["comparison_roundoff_tolerance_bn"]
    if len(state["holder"])!=5 or len(state["giga_holding"])!=10:raise ValueError("saved horizon")
    for row in state["giga_holding"]:
        if "normal_parent_profit" in row:raise ValueError("unused partial holding profit must not be labeled full-year normal profit")
    forward=forward_cash_contract(state,p)
    finance=financing_pv(state["holder"],p)
    bridge=state["financial_bridge"]
    close(finance["subscription_cash_pv"],state["source_subscription_cash_pv"],tol,"subscription bridge PV")
    close(finance["fund_fair_value_shortfall_pv"],bridge["future_commitment_fair_value_shortfall_pv"],tol,"fund PV")
    close(finance["extra_unmatched_capital_pv"],bridge["unmatched_capital_cost_pv"],tol,"capital PV")
    close(finance["cash_award_delivery_pv"],bridge["H_cash_delivery_cost_pv"],tol,"award PV")
    flows=[h["valuation_owner_fcff"] for h in state["giga_holding"]]
    old_terminal_cash=state["old_primary_operating_value"]["terminal_state"]["cash_flow"]
    old_g=state["old_primary_operating_value"]["terminal_state"]["growth"]
    close(old_g,p["mature_growth"],tol,"unchanged growth budget")
    h5=state["holder"][-1]
    shares=state["current_diluted_shares_m"]
    epv=auxiliary_epv_contract(state,p)
    definitions=[{"label":"center","op_required_return":p["central_operating_return"],
                  "cxmt_required_return":bridge["cxmt"]["operation_value_parent"]["discount_rate"],
                  "cxmt_tax_adjusted_stake_now":bridge["cxmt"]["stake"]["net"],
                  "current_equity":state["old_current_primary_equity"],
                  "initial_q3_witness":state["initial_q3_cxmt_ownership_witness"],
                  "cutoff_rights":state["cxmt_cutoff_financial_rights"]}]
    for old in state["source_parameter_points"]:
        definitions.append({"label":old["label"]+"_parameter_point","op_required_return":old["op_required_return"],
                            "cxmt_tax_adjusted_stake_now":old["cxmt_tax_adjusted_stake_now"],
                            "cxmt_tax_adjusted_stake_year5":old["cxmt_tax_adjusted_stake_year5"],
                            "current_equity":old["current_equity"],"year5_equity":old["year5_equity"],
                            "initial_q3_witness":old["cxmt_ownership_allocation"],
                            "cutoff_rights":old["cxmt_classified_rights_cutoff"],
                            "cxmt_required_return":old["cxmt_required_return"]})
    points=[]
    for point in definitions:
        rate=point["op_required_return"]
        old_op=operating_values(flows,old_terminal_cash,rate,old_g)
        new_op=operating_values(flows,forward["forward_owner_fcff"],rate,p["mature_growth"])
        current_nonoperating=(bridge["excess_group_liquid_economic_claims"]-bridge["existing_debt"]
                              +bridge["other_portfolio"]["net"]+point["cxmt_tax_adjusted_stake_now"]
                              -bridge["noninvestment_dtl"]+finance["net_financing_pv"])
        close(old_op["current_operating_value"]+current_nonoperating,point["current_equity"],tol,"saved current bridge reconstruction")
        current=new_op["current_operating_value"]+current_nonoperating
        close(current-point["current_equity"],
              (new_op["terminal_at_h10"]-old_op["terminal_at_h10"])/(1+rate)**10,tol,"current terminal-only delta")
        aux=auxiliary_value(flows,epv,rate,current_nonoperating)
        output={"label":point["label"],"point_scope":p["point_semantics"],"operating_return":rate,
                "cxmt_required_return":point["cxmt_required_return"],
                "current_equity":current,"current_per_diluted_share":current*1000/shares,
                "current_diluted_shares_m":shares,"saved_current_equity_reference":point["current_equity"],
                "current_equity_delta":current-point["current_equity"],"operating_value":new_op,
                "financial_pv":finance,"current_nonoperating_total_including_financing_pv":current_nonoperating,
                "initial_q3_cxmt_ownership_witness":copy.deepcopy(point["initial_q3_witness"]),
                "conditional_carry_cutoff_nonoperating_rights":point["cutoff_rights"],
                "unchanged_cxmt_tax_adjusted_stake_now":point["cxmt_tax_adjusted_stake_now"],
                "auxiliary_zero_growth_reference":aux,
                "auxiliary_zero_growth_per_diluted_share":aux["current_equity_reference"]*1000/shares}
        if "year5_equity" in point:
            financial5=(h5["group_excess_cash"]+h5["other_investments_net"]+point["cxmt_tax_adjusted_stake_year5"]
                        -bridge["existing_debt"]-bridge["noninvestment_dtl"])
            close(old_op["year5_remaining_operating_value"]+financial5,point["year5_equity"],tol,"saved year5 bridge reconstruction")
            year5=new_op["year5_remaining_operating_value"]+financial5
            close(year5-point["year5_equity"],
                  (new_op["terminal_at_h10"]-old_op["terminal_at_h10"])/(1+rate)**5,tol,"year5 terminal-only delta")
            output.update({"year5_equity":year5,"year5_per_share":year5*1000/h5["external_shares_m"],
                           "year5_external_shares_m":h5["external_shares_m"],
                           "saved_year5_equity_reference":point["year5_equity"],
                           "year5_equity_delta":year5-point["year5_equity"],
                           "year5_financial_bridge_after_same_dividends":financial5,
                           "unchanged_cxmt_tax_adjusted_stake_year5":point["cxmt_tax_adjusted_stake_year5"],
                           "cxmt_required_return":point["cxmt_required_return"]})
        points.append(output)
    parameter_points=points[1:]
    current_range=sorted(point["current_per_diluted_share"] for point in parameter_points)
    future_range=sorted(point["year5_per_share"] for point in parameter_points)
    return_model=copy.deepcopy(state["original_return_model"])
    if return_model is not None:
        return_model["base_case_terminal_equity_value_range_per_share"]["year_5"]={"low":future_range[0],"high":future_range[1]}
        if return_model["base_case_distributions_per_share"]!=[h["distribution_per_share"] for h in state["holder"]]:
            raise AssertionError("saved holder distributions changed")
    return {"name":state["name"],"group":state["group"],"status":"SAVED_STATE_BRIDGE_COMPLETE_ADOPTION_PENDING",
            "forward_cash_maturity_contract":forward,"old_terminal_cash_reference":old_terminal_cash,
            "old_terminal_net_investment_reference":state["old_primary_operating_value"]["terminal_state"]["net_reinvestment"],
            "current_primary_per_diluted_share":points[0]["current_per_diluted_share"],
            "conditional_current_parameter_interval_per_share":current_range,
            "conditional_year5_parameter_interval_per_share":future_range,"valuation_points":points,
            "auxiliary_zero_growth_contract":epv,
            "historical_auxiliary_reference_not_adopted_as_new_capital_validation":state["old_auxiliary_reference"],
            "holder":copy.deepcopy(state["holder"]),"return_model":return_model,
            "unchanged_funding_flags":copy.deepcopy(state["funding_flags"]),
            "unchanged_source_return_warnings":copy.deepcopy(state["source_warnings"]),
            "holding_normal_profit_field":"Unused partial normal_parent_profit omitted; fiscal policy profit and actual D unchanged",
            "financial_witness_scope":p["point_semantics"],
            "old_operating_cash_and_financial_states_not_reforecast":True,
            "auxiliary_is_distinct_growth_upkeep_counterfactual_not_independent_source_validation":True}
