#!/usr/bin/env python3
"""Desay SV 2026Q3. CNY billions; shares billions. Stdlib-only, self-contained.
Forecast budget is NOT legal-entity statutory accounts. Only payer P has an
observed legal retained-earnings anchor. S is a consolidated economic remainder;
NO statutory reserves or distributable profits are invented for S; NO S dividend
is assumed. Holder exit is a transfer of listed common shares, not liquidation.
"""
import json, math, pathlib, copy, argparse, gzip, base64, hashlib, sys
ASOF='2026-10-26T22:30:00+00:00'
OPEN={'revenue':34.64059929938,'cash':3.23394380126,'parent_cash':2.50,
      'debt':.74645066313,'parent_debt':.45,'earmark':2.0,
      'nwc':7.48700360644,'fixed':5.72315969547,
      'parent_retained':8.38350952378,'reserve':.298421317,'paid_share_capital':.596809294,'registered_capital':.596842634,
      'shares':.596809294,'minority_cash_reserve':0.,'nonoperating_assets':.93790284392,'parent_nonoperating_assets':.797217417332,'nci_book':.14208268524}
# cash = Q3 cash equivalents 1.82953142181 + trading assets 1.40441237945.
# Restricted cash 0.05019211427 is excluded, not written off: released in Y4.
BASE={'growth':[.08,.10,.10,.08,.07,.06,.05,.04,.03,.03]+[.02]*10,
      'margin':[.078,.080,.082,.083,.083,.082,.081,.080,.079,.078]+[.075]*10,
      'nwc_ratio':[.24,.23,.22]+[.215]*17,'fixed_ratio':.16,'mincash_ratio':.04,
      'depreciation':.025,'tax':.15,'deposit_rate':.02,'interest':.045,
      'parent_earnings_share':.95,'parent_working_share':.94,'parent_capex_share':.80,
      'parent_cash_share':.80,'payout':.35,'payout_late':.65,'special_start':6,'special_cash_buffer':1.5,'debt_limit':3.0,
      'discount':.095,'terminal_growth':.02,'exit_cost':.005,
      'minority_operating_fraction':.01,'minority_reinvestment_fraction':0.,'investment_exit_year':7,
      'investment_recovery':.85,'investment_tax':.25,'investment_cost':.02,
      'construction_floor':[1.8,1.6,1.4], 'eligible_project_spending':[1.1,.9,.6], 'loss_shock':{},'payment_shock':{},
      'option_exercise_year':2,'option_count':.0027424,'option_strike':84.85,
      'external_capital_call':.0511666,'us_internal_capital':.0056,'h_share_raise':0.,'opening':OPEN}

def annual(state,p,y):
    """The production function used by every scenario and by hand cases."""
    a=copy.deepcopy(state); prior=copy.deepcopy(state)
    rev=prior['revenue']*(1+p['growth'][y-1]); margin=p['margin'][y-1]
    ebit=rev*margin-p.get('loss_shock',{}).get(y,0.)
    # No contemporaneous tax refund; unclaimed loss carryforwards receive no asset value.
    tax=max(ebit,0.)*p['tax']; nopat=ebit-tax
    nwc=rev*p['nwc_ratio'][y-1]; dnwc=nwc-prior['nwc']
    da=rev*p['depreciation']; target_fixed=rev*p['fixed_ratio']
    floor=p['construction_floor'][y-1] if y<=len(p['construction_floor']) else 0.
    capex=max(da+target_fixed-prior['fixed'],floor,0.)
    fixed=prior['fixed']+capex-da
    if y>len(p['construction_floor']) and fixed>target_fixed:
        # No free disposal proceeds. Overbuilt property depreciates, maintenance is retained.
        capex=max(da*.80,da+target_fixed-prior['fixed'])
        fixed=prior['fixed']+capex-da
    interest=prior['debt']*p['interest']; p_interest=prior['parent_debt']*p['interest']
    inc=prior['cash']*p['deposit_rate']*(1-p['investment_tax'])
    pinc=prior['parent_cash']*p['deposit_rate']*(1-p['investment_tax'])
    # Interest deduction not monetized: no modeled refund/tax shield.
    cash_flow=nopat+da-capex-dnwc-interest+inc
    parent_np=nopat*p['parent_earnings_share']-p_interest+pinc
    parent_cf=(nopat*p['parent_earnings_share']+da*p['parent_capex_share']
              -capex*p['parent_capex_share']-dnwc*p['parent_working_share']-p_interest+pinc)
    # Operating cash obligations are not netted against unrelated legal receivables.
    payment=p.get('payment_shock',{}).get(y,0.)
    parent_cf-=payment; cash_flow-=payment
    # Minority economics are reserved, not illegally paid only to minorities; no subsidiary dividend is assumed.
    minority_payment=0.
    # Economic attribution only: base common shareholders fund all reinvestment.
    reinvestment=capex-da+dnwc+(rev-prior['revenue'])*p['mincash_ratio']
    minority_reinvestment=min(max(nopat,0.),max(reinvestment,0.)*p.get('minority_reinvestment_fraction',0.))*p['minority_operating_fraction']
    minority_accrual=max(nopat,0.)*p['minority_operating_fraction']-minority_reinvestment
    a['minority_cash_reserve']=prior.get('minority_cash_reserve',0.)*(1+p['deposit_rate']*(1-p['investment_tax']))+minority_accrual
    # Non-operating investments sold once; capital basis and gains kept distinct.
    gross=cost=gain_tax=principal=realized_gain=investment_cash=0.
    if y==p['investment_exit_year']:
        gross=prior['nonoperating_assets']*p['investment_recovery'];cost=gross*p['investment_cost']
        netbefore=gross-cost;principal=min(netbefore,prior['nonoperating_assets'])
        realized_gain=netbefore-prior['nonoperating_assets'];gain_tax=max(realized_gain,0)*p['investment_tax']
        investment_cash=netbefore-gain_tax
        parent_cf+=investment_cash;cash_flow+=investment_cash
        parent_fraction=prior.get('parent_nonoperating_assets',prior['nonoperating_assets'])/prior['nonoperating_assets'] if prior['nonoperating_assets'] else 1.
        parent_cf-=investment_cash*(1-parent_fraction)
        parent_np+=(realized_gain-gain_tax)*parent_fraction;a['nonoperating_assets']=0.;a['parent_nonoperating_assets']=0.
    capital_call=p.get('external_capital_call',0.) if y==1 else 0.
    parent_cf-=capital_call;cash_flow-=capital_call;a['nonoperating_assets']+=capital_call
    a['parent_nonoperating_assets']=a.get('parent_nonoperating_assets',0.)+capital_call
    release=.05019211427 if y==4 and p.get('release_restricted',True) else 0.
    parent_cf+=release;cash_flow+=release
    issue_cash=0.
    if y==p['option_exercise_year']:
        issue_cash=p['option_count']*p['option_strike'];a['shares']+=p['option_count'];a['paid_share_capital']+=p['option_count'];a['registered_capital']+=p['option_count'] # conditional same-time registration budget
    parent_cf+=issue_cash;cash_flow+=issue_cash
    if y==1 and p['h_share_raise']:
        # Explicit non-core diagnostic issuance at assumed book capital per new share.
        n=p['h_share_raise']; cashraise=n*27.*.98
        a['shares']+=n;a['paid_share_capital']+=n;a['registered_capital']+=n;parent_cf+=cashraise;cash_flow+=cashraise;issue_cash+=cashraise
    # Earmarked funds pay eligible construction, they are not distributable balances.
    # Only project-specific eligible spend frees earmarks; ordinary maintenance is not presumed eligible.
    eligible=min(capex,p['eligible_project_spending'][y-1]) if y<=len(p['eligible_project_spending']) else 0.
    earmark_spent=min(prior['earmark'],eligible)
    a['earmark']=prior['earmark']-earmark_spent
    gmin=rev*p['mincash_ratio'];pmin=gmin*p['parent_cash_share'];smin=gmin-pmin
    pc=prior['parent_cash']+parent_cf; sc=prior['cash']-prior['parent_cash']+cash_flow-parent_cf
    # Forward intragroup support is a bilateral loan; no group income and no legal netting.
    support=max(0.,smin-sc)+(p.get('us_internal_capital',0.) if y==1 else 0.);pc-=support;sc+=support
    a['intercompany_loan']=prior.get('intercompany_loan',0.)+support
    need=max(0.,pmin+a['earmark']-pc)
    draw=min(need,max(0.,p['debt_limit']-prior['debt']))
    pc+=draw;a['debt']+=draw;a['parent_debt']+=draw
    # Restore liquidity first; surplus retires borrowings before discretionary dividends.
    repayment=min(a['parent_debt'],max(0.,pc-pmin-a['earmark']))
    pc-=repayment;a['debt']-=repayment;a['parent_debt']-=repayment
    legal_before=prior['parent_retained']+parent_np
    # Current earnings first repair carried deficit, then reserve; actual parent reserve is full.
    eligible_profit=max(0.,parent_np-max(0.,-prior['parent_retained']))
    reserve_add=min(max(0.,.5*a['registered_capital']-prior['reserve']),eligible_profit*.1)
    legal_before-=reserve_add;a['reserve']+=reserve_add
    desired=max(0.,parent_np)*(p['payout'] if y<=5 else p['payout_late'])
    special=max(0.,pc-pmin*p['special_cash_buffer']-a['earmark']-desired) if y>=p['special_start'] else 0.
    dividend=min(desired+special,max(0.,legal_before),max(0.,pc-pmin-a['earmark']))
    failed=pc+1e-9<pmin+a['earmark'] or sc+1e-9<smin
    if failed:dividend=0.
    pc-=dividend;a['parent_retained']=legal_before-dividend
    a.update(revenue=rev,nwc=nwc,fixed=fixed,parent_cash=pc,cash=pc+sc)
    row={'year':y,'revenue':rev,'ebit':ebit,'tax':tax,'nopat':nopat,'nwc':nwc,'delta_nwc':dnwc,
         'depreciation':da,'capex':capex,'fixed':fixed,'cash_minimum':gmin,'parent_minimum':pmin,
         'interest':interest,'deposit_income_after_tax':inc,'group_cash_flow':cash_flow,
         'parent_net_profit':parent_np,'parent_cash_flow':parent_cf,'subsidiary_economic_cash_flow':cash_flow-parent_cf,
         'parent_to_subs_loan':support,'subs_to_parent_dividend':0.,'new_borrowing':draw,'repaid_borrowing':repayment,
         'earmark_spent':earmark_spent,'earmark_remaining':a['earmark'],'parent_dividend':dividend,'regular_desired_dividend':desired,'special_budget_dividend':special,
         'dividend_per_share':dividend/a['shares'],'parent_retained':a['parent_retained'],'reserve_add':reserve_add,
         'investment_sale_gross':gross,'investment_sale_cost':cost,'investment_gain_tax':gain_tax,
         'investment_principal_return':principal,'investment_realized_gain':realized_gain,
         'external_capital_call':capital_call,'restricted_cash_release':release,'minority_payment':minority_payment,'minority_accrual':minority_accrual,'minority_reinvestment':minority_reinvestment,'minority_cash_reserve':a['minority_cash_reserve'],'issue_cash':issue_cash,
         'shares':a['shares'],'parent_cash':pc,'subs_economic_cash':sc,'cash':a['cash'],'debt':a['debt'],
         'parent_debt':a['parent_debt'],'invested_capital':nwc+fixed+gmin,
         'roic':nopat/(prior['nwc']+prior['fixed']+prior['revenue']*p['mincash_ratio']),
         'fcff':nopat+da-capex-dnwc-(gmin-prior['revenue']*p['mincash_ratio']),
         'feasible':not failed,'state':copy.deepcopy(a)}
    assert abs(a['cash']-(prior['cash']+cash_flow+draw-repayment-dividend))<1e-7
    assert abs(pc+sc-a['cash'])<1e-9
    assert abs(parent_cf+(cash_flow-parent_cf)-cash_flow)<1e-9
    assert abs(a['parent_retained']-(prior['parent_retained']+parent_np-reserve_add-dividend))<1e-8
    assert abs(a['debt']-(prior['debt']+draw-repayment))<1e-8
    return a,row

def terminal(row,p,r=None):
    """Whole common-share economic transfer value. No asset liquidation/no subsidiary dividend.
    Operating minimum cash is embedded in IC and never added a second time.
    Entire continuing business buyer bears existing debt/NCI. Personal holder taxes excluded.
    """
    r=p['discount'] if r is None else r;g=p['terminal_growth'];s=row['state']
    rev=s['revenue']; ebit_next=rev*(1+g)*p['margin'][-1]
    nopat_next=ebit_next-max(0.,ebit_next)*p['tax']
    ic=rev*(p['nwc_ratio'][-1]+p['fixed_ratio']+p['mincash_ratio'])
    reinvest=ic*g; cash_next=nopat_next-reinvest
    if cash_next<=0 or r<=g:return None
    ev=cash_next/(r-g)
    minority_ev=ev*p['minority_operating_fraction']
    excess_cash=s['cash']-row['cash_minimum']
    # Minority operating value includes its productive capital; accumulated reserved cash is deducted separately.
    nci_claim=0. # No second subtraction of the capital already inside minority EV
    equity=ev-minority_ev+excess_cash-s['debt']-nci_claim-s.get('minority_cash_reserve',0.)+s['nonoperating_assets']
    cost=max(equity,0)*p['exit_cost'];equity-=cost
    return {'ev':ev,'minority_operating_value':minority_ev,'minority_reserved_cash':s.get('minority_cash_reserve',0.),'opening_nci_claim':nci_claim,
            'excess_cash':excess_cash,'necessary_cash':row['cash_minimum'],'debt':s['debt'],
            'nonoperating_assets':s['nonoperating_assets'],'next_nopat':nopat_next,'next_reinvestment':reinvest,
            'next_fcff':cash_next,'terminal_roic':nopat_next/(ic*(1+g)),
            'share_transfer_cost':cost,'corporate_asset_sale_tax':0.,
            'equity':equity,'per_share':equity/s['shares']}

def simulate(p):
    state=copy.deepcopy(p['opening']);rows=[]
    for y in range(1,len(p['growth'])+1):
        state,row=annual(state,p,y);rows.append(row)
        if not row['feasible']:
            return {'status':'infeasible','failed_year':y,'reason':'bounded financing cannot meet required cash',
                    'pv':None,'tv5':None,'terminal':None,'unpaid_debt':state['debt'],
                    'distributions':[z['dividend_per_share'] for z in rows]+[0.]*(len(p['growth'])-y),
                    'rows':rows,'parameters':p}
    r=p['discount'];n=len(rows);t=terminal(rows[-1],p)
    if t is None:return {'status':'terminal_infeasible','pv':None,'tv5':None,'terminal':None,'unpaid_debt':state['debt'],'distributions':[z['dividend_per_share'] for z in rows],'rows':rows,'parameters':p}
    ds=[z['dividend_per_share'] for z in rows]
    tail=t['per_share']/(1+r)**n
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(ds))+tail
    tv5=sum(ds[i]/(1+r)**(i-4) for i in range(5,n))+t['per_share']/(1+r)**(n-5)
    # Auxiliary unlevered business DCF: instantaneous economic extraction rather than observed payout.
    aux_ev=sum((z['fcff']-z['minority_accrual'])/(1+r)**z['year'] for z in rows)
    aux_ev+=(t['ev']-t['minority_operating_value'])/(1+r)**n
    op=p['opening'];inv_exit=p['investment_exit_year']
    investment_basis=op['nonoperating_assets']+p.get('external_capital_call',0.)
    inv=investment_basis*p['investment_recovery']*(1-p['investment_cost'])
    auxiliary_gain_tax=max(0,inv-investment_basis)*p['investment_tax']
    inv-=auxiliary_gain_tax
    aux_equity=aux_ev+op['cash']-op['revenue']*p['mincash_ratio']-op['debt']
    aux_equity-=p.get('external_capital_call',0.)/(1+r)
    aux_equity-=sum(p.get('payment_shock',{}).get(y,0)/(1+r)**y for y in range(1,n+1))
    aux_equity+=inv/(1+r)**inv_exit+.05019211427/(1+r)**4
    # Compare fully diluted claims including time-discounted exercise proceeds.
    aux_equity+=p['option_count']*p['option_strike']/(1+r)**p['option_exercise_year'] if p['option_exercise_year'] else 0.
    aux=aux_equity/rows[-1]['shares']
    assert abs(pv-(sum(ds[i]/(1+r)**(i+1) for i in range(5))+tv5/(1+r)**5))<1e-8
    return {'status':'feasible','pv':pv,'tv5':tv5,'terminal':t,'terminal_pv_fraction':tail/pv,
            'distributions':ds,'aux_fcff_value_per_share':aux,'auxiliary_investment_bridge':{'basis':investment_basis,'gain_tax':auxiliary_gain_tax,'net_proceeds':inv,'exit_year':inv_exit},'rows':rows,'parameters':p}

def run(p):
    # Rational option exercise diagnostic based on intrinsic Y2 continuation, never a quote.
    q=copy.deepcopy(p);maximum=q['option_count'];q['option_count']=0.
    first=simulate(q)
    if first['status']=='feasible' and maximum and q['option_exercise_year']:
        year=q['option_exercise_year'];r=q['discount'];n=len(first['rows'])
        fair=sum(first['distributions'][i]/(1+r)**(i+1-year) for i in range(year,n))+first['terminal']['per_share']/(1+r)**(n-year)
        if fair>q['option_strike']:
            q['option_count']=maximum;first=simulate(q)
        first['option_decision']={'pre_exercise_intrinsic_per_share':fair,'strike':q['option_strike'],'exercised':q['option_count'],'maximum_options':maximum}
    return first

def params(**kw):
    p=copy.deepcopy(BASE);p.update(kw);return p

def cases():
    p=copy.deepcopy(BASE)
    out={'base':run(p),'core_low':run(params(discount=.10)),'core_high':run(params(discount=.09))}
    cyc=params(growth=[-.06,.00,.13,.12,.09]+BASE['growth'][5:],margin=[.045,.055,.075,.080,.083]+BASE['margin'][5:],
               nwc_ratio=[.31,.29,.25,.23,.215]+[.215]*15)
    structural=params(growth=[-.12,-.05,.00,.02,.02]+[.01]*15,margin=[.035,.025]+[.04]*18,
                      nwc_ratio=[.30]*20,fixed_ratio=.18,terminal_growth=.01,loss_shock={1:.8})
    optimistic=params(growth=[.14,.16,.14,.12,.10,.08,.07,.06,.05,.04]+[.025]*10,
                      margin=[.085,.09,.095]+[.095]*7+[.085]*10,nwc_ratio=[.23,.21]+[.20]*18,terminal_growth=.025)
    out.update(cyclical=run(cyc),structural=run(structural),optimistic=run(optimistic))
    sens={'minority_proportional_reinvestment':params(minority_reinvestment_fraction=1.),
          'margin_minus_1pp':params(margin=[v-.01 for v in BASE['margin']]),
          'nwc_plus_5pp':params(nwc_ratio=[v+.05 for v in BASE['nwc_ratio']]),
          'parent_profit_share_80pct':params(parent_earnings_share=.8),
          'construction_extra_1bn':params(construction_floor=[2.8,1.6,1.4]),
          'cash_yield_zero':params(deposit_rate=0.),
          'tax_25pct':params(tax=.25),
          'investment_recovery_125pct':params(investment_recovery=1.25),
          'special_release_year_10':params(special_start=10),
          'special_release_year_15':params(special_start=15),
          'special_release_none':params(special_start=99),
          'funding_cap_1bn':params(debt_limit=1.),
          'parent_extra_payment_1bn':params(payment_shock={1:1.}),
          'investment_recovery_50pct':params(investment_recovery=.5),
          'no_options':params(option_count=0.),
          'funding_failure':params(growth=[-.35]*20,margin=[-.08]*20,nwc_ratio=[.45]*20,debt_limit=.75),
          'earmarked_2_5bn':params(opening=dict(OPEN,earmark=2.5)),
          'parent_opening_cash_2bn':params(opening=dict(OPEN,parent_cash=2.0))}
    out.update({k:run(v) for k,v in sens.items()})
    # Both endpoints extend the EXACT base Y5 state, not separate 5-year scenarios.
    tv={}
    base=out['base']; s5=copy.deepcopy(base['rows'][4]['state'])
    for name,rate in [('low',.10),('high',.09)]:
        par=copy.deepcopy(base['parameters']);par['discount']=rate
        tailrows=[];s=copy.deepcopy(s5)
        for y in range(6,21):s,z=annual(s,par,y);tailrows.append(z)
        t=terminal(tailrows[-1],par)
        tv[name]=sum(z['dividend_per_share']/(1+rate)**(z['year']-5) for z in tailrows)+t['per_share']/(1+rate)**15
        assert all(z['feasible'] for z in tailrows)
    return {'identity':{'symbol':'CN:002920','name':'惠州市德赛西威汽车电子股份有限公司','period':'2026-Q3',
                        'as_of':ASOF,'units':'CNY billion and billion shares'},
            'core_value_range':{'low':round(out['core_low']['pv'],2),'high':round(out['core_high']['pv'],2),'currency':'CNY'},
            'return_model':{'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,
                            'base_case_distributions_per_share':[round(x,6) for x in base['distributions'][:5]],
                            'base_case_terminal_equity_value_range_per_share':{'year_5':{k:round(v,6) for k,v in tv.items()}}},
            'cases':out,'tests':selftest()}

def selftest():
    # Literal one-step special case fed through production annual(), not a separate identity.
    s=dict(OPEN,revenue=100.,cash=20.,parent_cash=20.,debt=0.,parent_debt=0.,earmark=0.,nwc=20.,fixed=10.,
           parent_retained=0.,reserve=0.,paid_share_capital=10.,registered_capital=10.,shares=10.,nonoperating_assets=0.,nci_book=0.)
    p=params(growth=[0.],margin=[.1],nwc_ratio=[.2],fixed_ratio=.1,mincash_ratio=.05,depreciation=.02,tax=.2,
             deposit_rate=0.,parent_earnings_share=1.,parent_working_share=1.,parent_capex_share=1.,parent_cash_share=1.,
             payout=.5,construction_floor=[],option_exercise_year=0,minority_operating_fraction=0.,investment_exit_year=0,external_capital_call=0.,us_internal_capital=0.)
    a,z=annual(s,p,1)
    # EBIT10 tax2 NP8 D&A2 capex2 FC8 reserve0.8 D4 retained3.2 cash24, no debt.
    assert all(math.isclose(z[k],v,abs_tol=1e-9) for k,v in {'ebit':10.,'tax':2.,'capex':2.,'parent_dividend':4.,'reserve_add':.8,'parent_retained':3.2,'cash':24.}.items())
    # Actual production counterexample: registered 20 != paid 10, reserve 5.
    unequal=dict(s,registered_capital=20.,paid_share_capital=10.,reserve=5.)
    _,uz=annual(unequal,p,1);assert math.isclose(uz['reserve_add'],.8)
    # Loss repair: opening deficit -6, NP8 => reserve only on 2, dividend <=1.8.
    s['parent_retained']=-6.;a,z=annual(s,p,1)
    assert math.isclose(z['reserve_add'],.2) and math.isclose(z['parent_dividend'],1.8)
    # Negative earnings yield ZERO tax cash refund.
    p['margin']=[-.1];a,z=annual(s,p,1);assert z['tax']==0 and z['parent_dividend']==0
    # Capital principal is cash, not legal retained profit. Loss disposal creates no tax refund.
    s.update(parent_retained=0.,nonoperating_assets=1.,parent_nonoperating_assets=1.)
    p.update(margin=[0.],investment_exit_year=1)
    a,z=annual(s,p,1)
    assert math.isclose(z['investment_principal_return'],.833) and math.isclose(z['cash'],20.833)
    assert math.isclose(z['parent_retained'],-.167) and z['parent_dividend']==0 and z['investment_gain_tax']==0
    diagnostic=run(params(investment_recovery=1.25))
    ab=diagnostic['auxiliary_investment_bridge'];az=diagnostic['rows'][6]
    expected=(.93790284392+.0511666)*(1.25*.98-1)*.25
    assert math.isclose(ab['gain_tax'],expected,abs_tol=1e-12)
    assert math.isclose(ab['gain_tax'],az['investment_gain_tax'],abs_tol=1e-12)
    return {'registered_not_paid_production_counterexample':'pass','capital_call_tax_basis_auxiliary_regression':'pass','principal_not_distributable_profit':'pass','production_hand_case':'pass','loss_before_reserve':'pass','negative_ebit_no_refund':'pass',
            'every_year_cash_parent_debt_legal_conservation':'pass','fixed_y5_continuation':'pass'}

def literal(rate,margin_delta=0,minority_reinvest=0):
    growth=[.08,.10,.10,.08,.07,.06,.05,.04,.03,.03]+[.02]*10
    margins=[.078,.080,.082,.083,.083,.082,.081,.080,.079,.078]+[.075]*10
    nwcs=[.24,.23,.22]+[.215]*17
    revenue=34.64059929938;working=7.48700360644;plant=5.72315969547
    cash=3.23394380126;parent=2.5;debt=.74645066313;pdebt=.45
    earmark=2.;retained=8.38350952378;reserve=.298421317;capital=.596842634
    assets=.93790284392;passets=.797217417332;shares=.596809294;loan=0;minority_reserve=0.
    rows=[];ds=[]
    for i in range(20):
        year=i+1;oldcash=cash;oldparent=parent;oldrevenue=revenue
        revenue*=1+growth[i]
        profit=revenue*(margins[i]+margin_delta);tax=max(profit,0)*.15;net=profit-tax
        newworking=revenue*nwcs[i];workingchange=newworking-working
        depreciation=revenue*.025;desiredplant=revenue*.16
        capex=max(depreciation+desiredplant-plant,[1.8,1.6,1.4][i] if i<3 else 0,0)
        newplant=plant+capex-depreciation
        if i>=3 and newplant>desiredplant:
            capex=max(depreciation*.8,depreciation+desiredplant-plant);newplant=plant+capex-depreciation
        cost=debt*.045;pcost=pdebt*.045
        income=oldcash*.015;pincome=oldparent*.015
        flow=net+depreciation-capex-workingchange-cost+income
        minority_charge=min(max(net,0),max(0,capex-depreciation+workingchange+(revenue-oldrevenue)*.04)*minority_reinvest)*.01
        minority_reserve=minority_reserve*1.015+max(net,0)*.01-minority_charge
        pflow=net*.95+(depreciation-capex)*.8-workingchange*.94-pcost+pincome
        pprofit=net*.95-pcost+pincome
        salegross=salecharges=saletax=principal=gain=0
        if year==7:
            salegross=assets*.85;salecharges=salegross*.02;gain=salegross-salecharges-assets
            saletax=max(gain,0)*.25;proceeds=salegross-salecharges-saletax
            principal=min(assets,salegross-salecharges)
            pflow+=proceeds*passets/assets;pprofit+=(gain-saletax)*passets/assets
            flow+=proceeds;assets=0;passets=0
        if year==1:
            flow-=.0511666;pflow-=.0511666;assets+=.0511666;passets+=.0511666
        if year==4:flow+=.05019211427;pflow+=.05019211427
        eligible=[1.1,.9,.6][i] if i<3 else 0
        spend=min(earmark,capex,eligible);earmark-=spend
        minimum=.04*revenue;pminimum=minimum*.8
        pc=oldparent+pflow;sc=oldcash-oldparent+flow-pflow
        support=max(0,minimum-pminimum-sc)+(.0056 if year==1 else 0)
        pc-=support;sc+=support;loan+=support
        borrowing=min(max(0,pminimum+earmark-pc),max(0,3.-debt));pc+=borrowing;debt+=borrowing;pdebt+=borrowing
        repayment=min(pdebt,max(0,pc-pminimum-earmark));pc-=repayment;debt-=repayment;pdebt-=repayment
        replenishment=min(max(0,capital*.5-reserve),max(0,pprofit-max(0,-retained))*.1)
        reserve+=replenishment;legal=retained+pprofit-replenishment
        regular=max(0,pprofit)*(.35 if year<=5 else .65)
        extra=max(0,pc-pminimum*1.5-earmark-regular) if year>=6 else 0
        div=min(regular+extra,max(0,legal),max(0,pc-pminimum-earmark))
        assert pc>=pminimum+earmark-1e-9 and sc>=minimum-pminimum-1e-9
        pc-=div;retained=legal-div;cash=pc+sc;parent=pc;working=newworking;plant=newplant
        d=div/shares;ds.append(d)
        rows.append({'year':year,'revenue':revenue,'ebit':profit,'tax':tax,'nopat':net,'nwc':working,
                     'delta_nwc':workingchange,'depreciation':depreciation,'capex':capex,'fixed':plant,
                     'cash_minimum':minimum,'parent_minimum':pminimum,'interest':cost,'deposit_income_after_tax':income,
                     'group_cash_flow':flow,'parent_net_profit':pprofit,'parent_cash_flow':pflow,
                     'parent_to_subs_loan':support,'new_borrowing':borrowing,'repaid_borrowing':repayment,
                     'earmark_spent':spend,'earmark_remaining':earmark,'parent_dividend':div,'dividend_per_share':d,
                     'parent_retained':retained,'reserve_add':replenishment,'cash':cash,'parent_cash':parent,
                     'subs_economic_cash':sc,'debt':debt,'parent_debt':pdebt,'shares':shares,
                     'investment_sale_gross':salegross,'investment_sale_cost':salecharges,'investment_gain_tax':saletax,
                     'investment_principal_return':principal,'investment_realized_gain':gain,
                     'fcff':net+depreciation-capex-workingchange-(minimum-oldrevenue*.04)})
    nextnet=revenue*1.02*(.075+margin_delta)*.85;reinvest=revenue*(.215+.16+.04)*.02
    ev=(nextnet-reinvest)/(rate-.02)
    tequity=(ev*.99+cash-revenue*.04-debt-minority_reserve)*.995
    t=tequity/shares
    pv=sum(d/(1+rate)**(i+1) for i,d in enumerate(ds))+t/(1+rate)**20
    tv5=sum(ds[i]/(1+rate)**(i-4) for i in range(5,20))+t/(1+rate)**15
    return {'rows':rows,'pv':pv,'tv5':tv5,'terminal_per_share':t}

def verify(output):
    results={}
    for name,r,m,f in [('base',.095,0,0),('core_low',.1,0,0),('core_high',.09,0,0),('margin_minus_1pp',.095,-.01,0),('minority_proportional_reinvestment',.095,0,1)]:
        independent=literal(r,m,f);published=output['cases'][name];count=0;maxerror=0
        for x,y in zip(independent['rows'],published['rows']):
            for k,v in x.items():
                err=abs(v-y[k]);maxerror=max(maxerror,err);assert math.isclose(v,y[k],rel_tol=1e-10,abs_tol=1e-9),(name,x['year'],k,v,y[k]);count+=1
        for k in ['pv','tv5']:assert math.isclose(independent[k],published[k],rel_tol=1e-10)
        assert math.isclose(independent['terminal_per_share'],published['terminal']['per_share'],rel_tol=1e-10)
        results[name]={'rows':20,'matched_fields':count+3,'maximum_absolute_error':maxerror,'pv':independent['pv'],'tv5':independent['tv5'],'status':'pass'}
    return results

def pack_output(full):
    packed=copy.deepcopy(full)
    for case in packed['cases'].values():
        raw=json.dumps(case.pop('rows'),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        case['annual_rows_encoding']='gzip+base64; UTF-8 JSON; deterministic mtime=0; all fields retained'
        case['annual_rows_bytes']=len(raw)
        case['annual_rows_sha256']=hashlib.sha256(raw).hexdigest()
        case['annual_rows_gzip_base64']=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode()
    packed['artifact_encoding']='full case scalars and parameters; annual rows losslessly compressed in each case; --expand decodes without data loss'
    return packed

def expand_output(packed):
    full=copy.deepcopy(packed);full.pop('artifact_encoding',None)
    for case in full['cases'].values():
        if 'annual_rows_gzip_base64' in case:
            raw=gzip.decompress(base64.b64decode(case.pop('annual_rows_gzip_base64')))
            assert len(raw)==case.pop('annual_rows_bytes')
            assert hashlib.sha256(raw).hexdigest()==case.pop('annual_rows_sha256')
            case.pop('annual_rows_encoding');case['rows']=json.loads(raw)
    return full

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--expand',nargs='?',const='',help='Decode optional packed path to stdout; missing file is regenerated from this standalone script')
    ap.add_argument('--output');args=ap.parse_args()
    target=pathlib.Path(args.output) if args.output else pathlib.Path(__file__).resolve().with_name('2026-Q3-output.json')
    if args.expand is not None:
        source=pathlib.Path(args.expand) if args.expand else target
        if source.exists():result=expand_output(json.loads(source.read_text(encoding='utf-8')))
        else:
            result=cases();result['independent_literal_verification']=verify(result)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False));sys.exit(0)
    result=cases();result['independent_literal_verification']=verify(result)
    packed=pack_output(result);assert expand_output(packed)==result
    target.write_text(json.dumps(packed,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(target),'core':result['core_value_range'],'return_model':result['return_model'],'tests':result['tests'],'lossless_roundtrip':'pass'},ensure_ascii=False))
