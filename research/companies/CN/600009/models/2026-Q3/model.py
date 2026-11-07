#!/usr/bin/env python3
"""Source-led airport owner-cash valuation. Standard library only; all paths via CLI.
Amounts in RMB100m, shares in 100m. Lease costs are operating cash costs.
No lease debt is subtracted again. This is research, not a trading engine.
"""
import argparse
import copy
import json
import math
from pathlib import Path


def continuation(earnings, ke, growth, roic):
    if not (ke > growth >= 0 and roic > growth):
        raise ValueError('Invalid continuation parameters')
    reinvestment = earnings * (1 + growth) * growth / roic
    cash = earnings * (1 + growth) - reinvestment
    return {'earnings_next': earnings * (1 + growth), 'reinvestment_next': reinvestment,
            'cash_next': cash, 'value': cash / (ke - growth)}


def present_value(cashflows, terminal, ke, bridge):
    pv_flows = sum(x / (1 + ke) ** (i + 1) for i, x in enumerate(cashflows))
    pv_terminal = terminal / (1 + ke) ** len(cashflows)
    return {'cashflow_pv': pv_flows, 'terminal_pv': pv_terminal,
            'equity': bridge + pv_flows + pv_terminal}


def solve(data, overrides=None):
    f = data['source_facts']
    p = copy.deepcopy(data['base'])
    p.update(overrides or {})
    n = 5
    for k in ('t3_stage', 'new_owned_da', 'retail_equity_profit', 'growth_capex',
              'retail_jv_unpaid_budget', 'parent_extra_pool_settlement',
              'revenue_shock_factors', 'fuel_continuity_factors'):
        if len(p[k]) != n:
            raise ValueError('Expected five years: ' + k)
    current_shares = f['shares_issued'] - f['treasury_shares']
    shares = current_shares - f['planned_cancel_shares']
    # Expected cancellation is prospective: cash and shares both reflected.
    # Opening engineering debt is a payment for already recognised assets.
    # Future capex below excludes this settlement; it is deducted exactly once.
    liquid = (f['cash_equivalents'] + f['trading_assets'] + p['repo_estimate']
              - p['operating_cash_buffer'] - p['minority_financial_assets_estimate']
              - f['minority_dividend_due'] - f['nonlease_debt']
              - f['lease_bills_gross']
              - p['engineering_payable_estimate'] - f['planned_cancel_cash']
              - p['fund_unpaid_call_budget'])
    illiquid = (f['funds_equity_method_h1'] + f['other_noncurrent_financial']
                + p['fund_unpaid_call_budget']) * p['fund_realization_ratio']
    bridge = liquid + illiquid
    parent_cash = (f['parent_cash'] - p['engineering_payable_estimate'] * p['parent_capex_share']
                   - f['planned_cancel_cash'] - p['fund_unpaid_call_budget']
                   - f['parent_lease_bills_gross'])
    cancellation_principal = f['planned_cancel_shares'] * f['planned_cancel_price']
    parent_opening_engineering_settlement = p['engineering_payable_estimate'] * p['parent_capex_share']
    parent_pool_obligation = (f['parent_gross_other_payables']
                              - parent_opening_engineering_settlement - cancellation_principal)
    if parent_pool_obligation < 0:
        raise ValueError('Opening identified settlements exceed mother other payables')
    parent_floor = parent_pool_obligation + p['parent_operating_cash_floor']
    parent_retained = f['parent_retained_profit'] - (f['planned_cancel_cash']-cancellation_principal)
    prev_rev = sum(p['starting_revenue'])
    prev_profit = p['reported_2026_common_profit_estimate']
    rows = []
    for i in range(n):
        t = i + 1
        revenue_segments = [a * (1 + g) ** t * p['revenue_shock_factors'][i]
                            for a, g in zip(p['starting_revenue'], p['segment_growth'])]
        rev = sum(revenue_segments)
        variable = p['cash_opex_start'] * p['variable_cost_share'] * rev / sum(p['starting_revenue'])
        fixed = p['cash_opex_start'] * (1-p['variable_cost_share']) * (1+p['fixed_cost_growth']) ** t
        t3_other = p['t3_other_cash_cost_full'] * p['t3_stage'][i]
        opex = variable + fixed + t3_other
        rent_existing = p['existing_cash_rent_start'] * (1+p['existing_rent_growth']) ** t
        rent_new = (p['t3_rent_full'] + p['hotel_rent_full']) * p['t3_stage'][i]
        rent = rent_existing + rent_new
        da = p['own_da_start'] * (1+p['own_da_growth']) ** t + p['new_owned_da'][i]
        ebit = rev - opex - rent - da
        direct_aftertax = ebit * (1-p['tax_rate'])  # losses assume usable existing tax group/profit relief
        fuel = p['fuel_equity_profit_start'] * (1+p['fuel_profit_growth']) ** t * p['fuel_continuity_factors'][i]
        other_assoc = p['other_assoc_equity_profit_start'] * (1+p['other_assoc_profit_growth']) ** t
        assoc = fuel + other_assoc + p['retail_equity_profit'][i]
        assoc_cash = max(assoc,0) * p['assoc_cash_payout'] + min(assoc,0)
        nci = p['minority_operating_profit_start'] * (1+p['minority_profit_growth']) ** t
        common_profit = direct_aftertax + assoc - nci
        maintenance = da * p['maintenance_to_da']
        growth_capex = p['growth_capex'][i] + p['retail_jv_unpaid_budget'][i]
        nwc = (rev-prev_rev) * p['nwc_incremental_revenue']
        owner_cash = direct_aftertax - nci + da - maintenance - growth_capex - nwc + assoc_cash
        start_liquid = liquid
        financial_income = max(liquid,0) * p['cash_aftertax_yield']
        reportlike_profit = common_profit + financial_income
        if i == 0:
            target_distribution = max(0,p['dividend_payout'] * prev_profit
                                      - f['h1_dividend_already_paid_per_share'] * current_shares)
            target_distribution += p['dividend_payout'] * 0.5 * max(reportlike_profit,0)
        else:
            target_distribution = p['dividend_payout'] * 0.5 * max(prev_profit+reportlike_profit,0)
        parent_profit = p['parent_profit_share'] * common_profit + parent_cash * p['cash_aftertax_yield']
        parent_reserve = max(parent_profit,0) * p['parent_reserve_accrual']
        parent_cash_in = ((direct_aftertax - nci + da) * p['parent_operating_cash_share']
                          + assoc_cash * p['parent_assoc_cash_share']
                          + parent_cash * p['cash_aftertax_yield']
                          - (maintenance+growth_capex) * p['parent_capex_share']
                          - nwc * p['parent_operating_cash_share'])
        # An internal pool settlement changes mother payment capacity, not group value.
        pool_settlement = p['parent_extra_pool_settlement'][i]
        if not 0 <= pool_settlement <= parent_pool_obligation:
            raise ValueError('Pool settlement exceeds identified existing obligation')
        parent_cash += parent_cash_in - pool_settlement
        parent_pool_obligation -= pool_settlement
        parent_floor = parent_pool_obligation + p['parent_operating_cash_floor']
        parent_retained += parent_profit - parent_reserve
        available_group = max(0,liquid+owner_cash+financial_income)
        available_mother = max(0,parent_cash-parent_floor)
        distribution = min(target_distribution,available_group,available_mother,max(0,parent_retained))
        parent_cash -= distribution
        parent_retained -= distribution
        liquid += owner_cash + financial_income - distribution
        assert abs(liquid - (start_liquid+owner_cash+financial_income-distribution)) < 1e-8
        assert distribution >= 0
        rows.append({'year':t,'segments':revenue_segments,'revenue':rev,'cash_opex':opex,
                     'cash_rent':rent,'new_rent':rent_new,'own_da':da,'ebit_cash_rent':ebit,
                     'fuel_equity_profit':fuel,'other_assoc_equity_profit':other_assoc,
                     'retail_equity_profit':p['retail_equity_profit'][i], 'assoc_cash':assoc_cash,
                     'minority_operating_profit':nci,'common_operating_profit':common_profit,
                     'maintenance_capex':maintenance,'growth_capex':growth_capex,'nwc_increase':nwc,
                     'owner_cash':owner_cash,'liquid_start':start_liquid,'financial_income':financial_income,
                     'reportlike_common_profit':reportlike_profit,'target_distribution':target_distribution,
                     'actual_distribution':distribution,'distribution_per_share':distribution/shares,
                     'liquid_end':liquid,'illiquid_end':illiquid,'parent_cash_in':parent_cash_in,
                     'parent_profit':parent_profit,'parent_reserve_accrued':parent_reserve,
                     'parent_cash_end':parent_cash,'parent_cash_floor':parent_floor,
                     'parent_pool_obligation_end':parent_pool_obligation,
                     'parent_retained_end':parent_retained,'distribution_constrained':distribution+1e-8<target_distribution})
        prev_rev,prev_profit = rev,reportlike_profit
        if liquid < -1e-8 or parent_cash < -1e-8:
            return {'status':'economically_infeasible',
                    'reason':'Operating/capital payments exceed available liquidity; additional financing not substantiated',
                    'trigger_year':t,'parameters':p,'rows':rows,
                    'opening_financial_bridge':bridge,'valuation':None,'terminal':None}
    earn5 = rows[-1]['common_operating_profit']
    if earn5 <= 0:
        return {'status':'economically_unresolved','reason':'Year5 persistent operating loss; no substantiated exit/financing value',
                'parameters':p,'rows':rows,'valuation':None,'terminal':None}
    cont = continuation(earn5,p['cost_of_equity'],p['terminal_growth'],p['terminal_incremental_roic'])
    valuation = present_value([r['owner_cash'] for r in rows],cont['value'],p['cost_of_equity'],bridge)
    valuation['per_share'] = valuation['equity']/shares
    valuation['terminal_pv_share_of_equity'] = valuation['terminal_pv']/valuation['equity']
    operating_pv=valuation['cashflow_pv']+valuation['terminal_pv']
    timing_factor=(1+p['cost_of_equity'])**(2/12)
    valuation['timing_two_months_and_balance_one_month_bounds_per_share'] = {
        'low':(bridge-2+operating_pv/timing_factor)/shares,
        'high':(bridge+2+operating_pv*timing_factor)/shares}
    # Auxiliary mature earnings capitalisation: same 5-year transition, different terminal method.
    aux_terminal = earn5*p['normalized_earnings_multiple']
    aux = present_value([r['owner_cash'] for r in rows],aux_terminal,p['cost_of_equity'],bridge)
    aux['per_share'] = aux['equity']/shares
    terminal_equity = cont['value']+liquid+illiquid
    return {'status':'ok','parameters':p,'current_eligible_shares':current_shares,'future_shares':shares,
            'opening_liquid':bridge-illiquid,'opening_illiquid':illiquid,'opening_financial_bridge':bridge,
            'rows':rows,'continuation':cont,'valuation':valuation,'auxiliary':aux,
            'terminal':{'operation_value':cont['value'],'liquid':liquid,'illiquid':illiquid,
                        'equity':terminal_equity,'per_share':terminal_equity/shares}}


def self_tests(data):
    # Both formal valuation functions, not a detached arithmetic assertion.
    c = continuation(10,0.10,0,0.10)
    v = present_value([10]*5,c['value'],0.10,20)
    assert abs(v['equity']-120) < 1e-9
    z = copy.deepcopy(data)
    z['base'].update({'starting_revenue':[100,0,0,0],'segment_growth':[0,0,0,0],
      'cash_opex_start':60,'fixed_cost_growth':0,'existing_cash_rent_start':10,'existing_rent_growth':0,
      't3_rent_full':0,'t3_other_cash_cost_full':0,'hotel_rent_full':0,'own_da_start':10,'own_da_growth':0,
      'new_owned_da':[0]*5,'fuel_equity_profit_start':0,'other_assoc_equity_profit_start':0,
      'retail_equity_profit':[0]*5,'minority_operating_profit_start':0,'growth_capex':[0]*5,
      'retail_jv_unpaid_budget':[0]*5,'tax_rate':0.5,'terminal_growth':0,'cost_of_equity':0.1,
      'cash_aftertax_yield':0,'parent_operating_cash_floor':0})
    r = solve(z)
    assert all(abs(a['owner_cash']-10)<1e-9 for a in r['rows'])
    assert abs(r['valuation']['equity']-r['opening_financial_bridge']-100)<1e-8
    # Known binding mother-cash case through solve: group earns 10 each year,
    # mother cash cannot exceed its 20 cash floor, so D=0 and group keeps all 50.
    m=copy.deepcopy(z)
    m['source_facts'].update({'cash_equivalents':50,'trading_assets':0,
      'funds_equity_method_h1':0,'other_noncurrent_financial':0,'nonlease_debt':0,
      'minority_dividend_due':0,'parent_cash':20,'parent_retained_profit':5,
      'lease_bills_gross':0,'parent_lease_bills_gross':0,
      'parent_gross_other_payables':0,'planned_cancel_cash':0,'planned_cancel_shares':0})
    m['base'].update({'repo_estimate':0,'operating_cash_buffer':0,
      'minority_financial_assets_estimate':0,'engineering_payable_estimate':0,
      'fund_unpaid_call_budget':0,'parent_operating_cash_share':0,'parent_assoc_cash_share':0,
      'parent_capex_share':0,'parent_operating_cash_floor':20})
    constrained=solve(m)
    assert all(a['actual_distribution']==0 for a in constrained['rows'])
    assert abs(constrained['rows'][-1]['liquid_end']-100)<1e-9
    assert abs(constrained['rows'][-1]['parent_cash_end']-20)<1e-9
    assert abs(constrained['rows'][-1]['parent_retained_end']-41)<1e-9
    assert abs(constrained['terminal']['equity']-200)<1e-9
    return {'formal_continuation_and_pv_equity':v['equity'],'hand_expected':120,
            'formal_operating_chain_cash_per_year':10,'formal_operating_chain_value':100,
            'constrained_mother_distributions':[a['actual_distribution'] for a in constrained['rows']],
            'constrained_group_cash_end':100,'constrained_mother_cash_end':20,
            'constrained_retained_profit_end':41,'constrained_terminal_equity':200,'passed':True}
