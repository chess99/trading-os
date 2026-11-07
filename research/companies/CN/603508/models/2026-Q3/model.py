"""Company-specific FCFF and legal payment budget; stdlib only.
No input is calibrated to market price. Money: CNY million; shares: million.
This file is not authorized to execute until the coordinator's exact admission.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path


def operating_step(revenues, margins, old_revenue, old_nwc, old_cash_reserve,
                   old_productive, ratios, tax, nwc_ratio, reserve_floor):
    revenue = sum(revenues)
    gross_profit = sum(r*m for r, m in zip(revenues, margins))
    sga = revenue * ratios['sga_ratio']
    rd = revenue * ratios['rd_ratio']
    surtax = revenue * ratios['surtax_ratio']
    rebate = revenue * ratios['vat_rebate_ratio']
    ebit = gross_profit - sga - rd - surtax + rebate
    nopat = ebit * (1-tax)
    nwc = revenue * nwc_ratio
    reserve = max(reserve_floor, revenue*ratios['operating_cash_ratio'])
    depreciation = old_productive*ratios['depreciation_rate_on_opening_productive_assets']
    growth_capex = max(revenue-old_revenue, 0)*ratios['incremental_fixed_capital_per_revenue']
    maintenance_capex = depreciation
    capex = maintenance_capex + growth_capex
    productive = old_productive + capex - depreciation
    fcff = nopat + depreciation - capex - (nwc-old_nwc) - (reserve-old_cash_reserve)
    return dict(revenue=revenue, gross_profit=gross_profit, sga=sga, rd=rd,
                surtax=surtax, vat_rebate=rebate, ebit=ebit, nopat=nopat,
                nwc=nwc, operating_cash=reserve, depreciation=depreciation,
                maintenance_capex=maintenance_capex, growth_capex=growth_capex,
                capex=capex, productive_assets=productive,
                delta_nwc=nwc-old_nwc, delta_operating_cash=reserve-old_cash_reserve,
                fcff=fcff, operating_capital=nwc+reserve+productive)


def fund_distribution(target, available_cash, legal_profit, min_cash):
    """Constrained budget, not fictional new financing. Negative balances are not erased."""
    capacity_cash = available_cash-min_cash
    feasible = max(0.0, min(target, capacity_cash, legal_profit))
    binding = []
    if feasible < target-1e-9:
        if capacity_cash < target: binding.append('parent_cash')
        if legal_profit < target: binding.append('parent_retained_earnings')
    return feasible, binding


def roll_financial_cash(opening, operating_cash, aftertax_yield, paid):
    income = opening*aftertax_yield
    return opening+operating_cash+income-paid, income


def operating_pv(rows, rate, growth, as_of_year=0):
    """Official FCFF valuation chain. rows 1..11; year11 is steady continuation."""
    if not rate > growth: raise ValueError('discount rate must exceed terminal growth')
    terminal = rows[10]['owner_fcff']/(rate-growth)
    explicit_pv = sum(r['owner_fcff']/(1+rate)**(r['year']-as_of_year)
                      for r in rows if as_of_year < r['year'] <= 10)
    terminal_pv = terminal/(1+rate)**(10-as_of_year)
    return dict(value=explicit_pv+terminal_pv, explicit_pv=explicit_pv,
                terminal_pv=terminal_pv, terminal_value_at_10=terminal,
                terminal_pv_share=terminal_pv/(explicit_pv+terminal_pv))


def zero_growth_epv(owner_nopat, rate, financial_bridge, shares):
    """Alternative mature earnings capitalization; no growth/released working capital."""
    if rate <= 0 or shares <= 0: raise ValueError('positive rate and shares required')
    return (owner_nopat/rate+financial_bridge)/shares


def scenario_spec(name):
    specs = {
      'base':{},
      'core_low':{'rate':0.10,'gm_delta':-0.005,'nwc':[0.72]*5,'minority_cash':80},
      'core_high':{'rate':0.09,'gm_delta':0.005,'nwc':[0.68]*5,'minority_cash':20},
      'cyclical':{'growth_all':[-0.08,0,0.08,0.06,0.04],
                  'gm_path':[-0.015,-0.01,-0.005,0,0],
                  'nwc':[0.80,0.80,0.77,0.74,0.70],
                  'upstream_delay_years':[1], 'parent_extra_payments':{'1':50,'2':25}},
      'structural':{'growth_all':[-0.08,-0.03,0,0.01,0.01],
                    'gm_delta':-0.055,'rd_delta':0.015,'sga_delta':0.005,
                    'nwc':[0.80,0.85,0.85,0.85,0.85],
                    'long_growth':0.005,'rate':0.105,
                    'upstream_delay_years':[1], 'parent_extra_payments':{'1':50,'2':50}},
      'upside':{'growth_all':[0.09,0.09,0.08,0.06,0.04],
                'rd_delta':0.008,'fixed_ratio':0.25,'nwc':[0.70]*5},
      'tax_25_diagnostic':{'tax':0.25},
      'minority_cash_0_diagnostic':{'minority_cash':0},
      'minority_cash_115_diagnostic':{'minority_cash':115},
      'parent_delay_and_extra_payment_diagnostic':{
          'upstream_delay_years':[1,2], 'parent_initial_cash_reduction':100,
          'parent_extra_payments':{'1':50,'2':50}}
    }
    if name not in specs: raise ValueError(name)
    return specs[name]


def forecast(config, name, overrides=None):
    f = config['facts']; a = copy.deepcopy(config['assumptions'])
    s = scenario_spec(name)
    if overrides: s.update(overrides)
    a['rd_ratio'] += s.get('rd_delta', 0)
    a['sga_ratio'] += s.get('sga_delta', 0)
    a['incremental_fixed_capital_per_revenue'] = s.get('fixed_ratio', a['incremental_fixed_capital_per_revenue'])
    g = s.get('long_growth', a['terminal_growth'])
    rate = s.get('rate', a['discount_rate'])
    tax = s.get('tax', a['tax_rate'])
    shares = f['shares']
    revs = list(a['normalized_start_revenue'])
    old_rev = sum(revs)
    initial_nwc = sum(f['nwc_assets'].values()) - sum(f['nwc_liabilities'].values()) - f['equipment_prepayment_proxy_from_h1']
    initial_productive = sum(f['productive_assets'].values()) + f['equipment_prepayment_proxy_from_h1']
    initial_reserve = old_rev*a['operating_cash_ratio']
    minor_cash = s.get('minority_cash', a['minority_excess_financial_assets'])
    liquid_finance = f['financial_assets']['cash_and_deposits']+f['financial_assets']['trading_financial']
    noninterest_finance = f['financial_assets']['other_equity']
    initial_owner_cash = liquid_finance-initial_reserve-minor_cash-f['external_interest_debt']
    owner_cash = initial_owner_cash
    parent_cash = f['parent_cash_h1']+f['parent_trading_h1']-s.get('parent_initial_cash_reduction',0)
    parent_re = f['parent_re_h1']
    old_nwc, old_reserve, old_productive = initial_nwc, initial_reserve, initial_productive
    rows=[]
    for year in range(1,12):
        if year <=5:
            growths=[s['growth_all'][year-1]]*3+[0] if 'growth_all' in s else [v[year-1] for v in a['growth_first5']]
            nwc_ratio=s.get('nwc',[a['nwc_ratio']]*5)[year-1]
            fade=0
        else:
            t=min((year-5)/5,1)
            last=[s['growth_all'][4]]*3+[0] if 'growth_all' in s else [v[4] for v in a['growth_first5']]
            growths=[x+(g-x)*t for x in last]
            nwc_ratio=s.get('nwc',[a['nwc_ratio']]*5)[-1]
            fade=a['post5_margin_fade_total']*t
        revs=[r*(1+h) for r,h in zip(revs,growths)]
        shock=s.get('gm_path',[0]*5)[year-1] if year<=5 else 0
        margins=[m+(s.get('gm_delta',0)+shock-fade if i<3 else 0) for i,m in enumerate(a['gross_margins'])]
        row=operating_step(revs,margins,old_rev,old_nwc,old_reserve,old_productive,
                           a,tax,nwc_ratio,initial_reserve)
        row.update(year=year,segment_revenues=list(revs),segment_growth=growths,
                   segment_margins=margins,nwc_ratio=nwc_ratio,tax_rate=tax)
        row['owner_nopat']=row['nopat']*(1-a['minority_operating_share'])
        row['minority_operating_profit']=row['nopat']*a['minority_operating_share']
        row['owner_fcff']=row['fcff']*(1-a['minority_operating_share'])
        # Only a budget for years 1–5; continuation operating value is not a legal maximum dividend.
        if year<=5:
            opening_owner=owner_cash; opening_parent=parent_cash; opening_re=parent_re
            finance_income=opening_owner*a['aftertax_financial_yield']
            owner_profit=row['owner_nopat']+finance_income
            target=max(0,owner_profit*a['payout'])
            lanxin_profit=max(0,row['nopat']*a['lanxin_profit_fraction_group_nopat'])
            lanxin_cash=max(0,row['fcff']*a['lanxin_cash_fraction_group_fcff'])
            upstream=min(f['last_actual_upstream']*(revs[2]/a['normalized_start_revenue'][2]),
                         lanxin_profit*a['upstream_profit_cap'],lanxin_cash*a['upstream_cash_cap'])
            if year in s.get('upstream_delay_years',[]): upstream=0
            parent_finance=max(opening_parent-a['parent_min_cash'],0)*a['aftertax_financial_yield']
            own_profit=row['nopat']*a['parent_own_profit_fraction_group_nopat'] + parent_finance-a['parent_annual_internal_interest']
            parent_ni=own_profit+upstream
            appropriation=max(0,parent_ni)*a['statutory_appropriation_rate']
            legal_available=opening_re+parent_ni-appropriation
            extra=s.get('parent_extra_payments',{}).get(str(year),0)
            own_cash=row['fcff']*a['parent_own_cash_fraction_group_fcff'] + parent_finance-a['parent_annual_internal_interest']-a['parent_annual_internal_lease_cash']
            funds_before=opening_parent+own_cash+upstream-extra
            paid,binding=fund_distribution(target,funds_before,legal_available,a['parent_min_cash'])
            owner_cash,income_check=roll_financial_cash(opening_owner,row['owner_fcff'],a['aftertax_financial_yield'],paid)
            parent_cash=funds_before-paid
            parent_re=legal_available-paid
            if min(owner_cash,parent_cash,parent_re)<-1e-8:
                raise ValueError(f'{name} Y{year}: infeasible finance/legal state; no free refinancing or cash erasure')
            assert abs(finance_income-income_check)<1e-8
            assert abs(owner_cash-opening_owner-row['owner_fcff']-finance_income+paid)<1e-8
            assert abs(parent_re-opening_re-parent_ni+appropriation+paid)<1e-8
            assert abs(parent_cash-opening_parent-own_cash-upstream+extra+paid)<1e-8
            row.update(owner_cash_open=opening_owner,owner_cash_close=owner_cash,
                       financial_income=finance_income,owner_profit=owner_profit,
                       payout_target=target,dividend_paid=paid,dividend_per_share=paid/shares,
                       payout_binding=binding,parent_cash_open=opening_parent,parent_cash_close=parent_cash,
                       parent_re_open=opening_re,parent_re_close=parent_re,parent_own_profit=own_profit,
                       parent_net_income=parent_ni,parent_appropriation=appropriation,
                       parent_own_cash=own_cash,upstream_cash=upstream,parent_extra_net_payment=extra,
                       parent_funds_before_dividend=funds_before,parent_legal_available=legal_available,
                       parent_cash_floor_shortfall=max(0,a['parent_min_cash']-parent_cash))
        old_rev,old_nwc,old_reserve,old_productive=row['revenue'],row['nwc'],row['operating_cash'],row['productive_assets']
        rows.append(row)
    ev0=operating_pv(rows,rate,g,0); ev5=operating_pv(rows,rate,g,5)
    current_financial_bridge=initial_owner_cash+noninterest_finance
    y5_financial_bridge=rows[4]['owner_cash_close']+noninterest_finance
    normalized0=operating_step(a['normalized_start_revenue'],
        [x+(s.get('gm_delta',0) if i<3 else 0) for i,x in enumerate(a['gross_margins'])],
        sum(a['normalized_start_revenue']),initial_nwc,initial_reserve,initial_productive,
        a,tax,a['nwc_ratio'],initial_reserve)
    # EPV is a zero-growth economic diagnostic: replacement capex=D&A, working capital held steady.
    epv_nopat=normalized0['nopat']*(1-a['minority_operating_share'])
    incremental_capital=rows[4]['operating_capital']-rows[0]['operating_capital']
    incremental_return=(rows[4]['nopat']-rows[0]['nopat'])/incremental_capital if abs(incremental_capital)>1e-8 else None
    return dict(name=name,rate=rate,terminal_growth=g,scenario=s,
        source_basis=dict(initial_nwc=initial_nwc,initial_productive=initial_productive,
          initial_operating_cash=initial_reserve,minority_excess_financial_assets=minor_cash,
          minority_current_asset_upper_reference=sum(x*y for x,y in f['minority_current_asset_bounds_h1']),
          financial_bridge_current=current_financial_bridge,financial_bridge_year5=y5_financial_bridge),
        rows=rows,operating_value_current=ev0,operating_value_year5=ev5,
        equity_value_current=ev0['value']+current_financial_bridge,
        value_per_share=(ev0['value']+current_financial_bridge)/shares,
        terminal_equity_year5_per_share=(ev5['value']+y5_financial_bridge)/shares,
        distributions_per_share=[x['dividend_per_share'] for x in rows[:5]],
        zero_growth_epv_per_share=zero_growth_epv(epv_nopat,rate,current_financial_bridge,shares),
        incremental_nopat_y1_to_y5=rows[4]['nopat']-rows[0]['nopat'],
        incremental_capital_y1_to_y5=incremental_capital,incremental_return_y1_to_y5=incremental_return,
        normalized_operating_roic_ex_goodwill=normalized0['nopat']/(initial_nwc+initial_reserve+initial_productive),
        normalized_operating_roic_incl_goodwill=normalized0['nopat']/(initial_nwc+initial_reserve+initial_productive+f['goodwill']),
        transition_y5_to_y6={k:rows[5][k]-rows[4][k] for k in ['revenue','nopat','fcff','capex','delta_nwc','delta_operating_cash']},
        continuation_y10_to_y11_fcff_growth=rows[10]['owner_fcff']/rows[9]['owner_fcff']-1)


def build_all(config):
    names=['base','core_low','core_high','cyclical','structural','upside',
           'tax_25_diagnostic','minority_cash_0_diagnostic','minority_cash_115_diagnostic',
           'parent_delay_and_extra_payment_diagnostic']
    cases={n:forecast(config,n) for n in names}
    # Return model is one operating Base, with only capital-cost endpoints varying at year5.
    base=cases['base']; bridge=base['source_basis']['financial_bridge_year5']
    future_low=(operating_pv(base['rows'],0.10,base['terminal_growth'],5)['value']+bridge)/config['facts']['shares']
    future_high=(operating_pv(base['rows'],0.09,base['terminal_growth'],5)['value']+bridge)/config['facts']['shares']
    return dict(company=config['company'],information_cutoff=config['information_cutoff'],
      units='CNY million and million shares, per-share values CNY',cases=cases,
      value_range_raw=[cases['core_low']['value_per_share'],cases['core_high']['value_per_share']],
      return_model_raw=dict(distributions=base['distributions_per_share'],year5_low=future_low,year5_high=future_high),
      historical_cash_diagnostics={period:dict(revenue=h['revenue'],parent_np=h['parent_np'],
          cfo=h['cfo'],cfo_to_parent_np=h['cfo']/h['parent_np'],
          capex=h.get('capex'),cfo_less_capex=h['cfo']-h['capex'] if 'capex' in h else None,
          expensed_rd_to_revenue=h['rd']/h['revenue'] if 'rd' in h else None)
          for period,h in config['facts']['historical'].items()},
      caveats=['NCI excess-cash allocation is an explicitly bounded estimate, not a disclosed subsidiary cash figure.',
               'Parent starting cash and RE are the latest disclosed H1 legal-body values, not falsely labeled Q3 values.',
               'Current FCFF+net-financial-assets economic value is not a legal maximum dividend or a promised payout.',
               'Rental income/property depreciation are inside operation; property book value is not added again.',
               'No external financing, buyback, dilution, negative-cash truncation or terminal capital liquidation is assumed.'])
