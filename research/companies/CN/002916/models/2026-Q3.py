#!/usr/bin/env python3
"""CN:002916, 2026-Q3. Stdlib only. CNY billion, shares billion.
No current price. All distributions are legal and funded; terminal cash is released
through the very same annual function, never added as an untested excess-cash lump.
"""
import json, copy, pathlib, math
ROOT=pathlib.Path(__file__).resolve().parent
INPUTS={
 'symbol':'CN:002916','period':'2026-Q3','information_cutoff':'2026-10-26T09:00:00+00:00',
 'shares':.681166595,'opening_revenue':32.66683675642,'opening_nwc':10.564,
 'opening_fixed_operating_assets':23.859,'opening_engineering_payable':3.5,
 'opening_financial_asset':.08418882463,'financial_asset_cost':.0304783237,
 'opening_cash':[.4,.22,.17,.15,.16111696734],
 'opening_debt':[1.8,3.,1.6,1.,2.09499814993],
 'entities':['P_parent','W_wuxi','N_nantong','U_wuxi_guangxin','G_guangzhou'],
 'profit_weights':[.18,.32,.18,.22,.10], 'capital_weights':[.08,.40,.22,.12,.18],
 'wc_weights':[.20,.30,.20,.18,.12],
 'opening_legal_retained':[3.87016577999,0.,0.,0.,-.5],
 'opening_reserves':[.3333703975,0.,0.,0.,0.],
 'opening_registered_capital':[.681166595,.78,.78,.101,1.5],
 'revenue':[40,47,53,58,62], 'ebit_margin':[.20,.195,.19,.185,.18],
 'cash_capex':[8,6,5,4.8,4.8], 'engineering_payment':[2,1.5,0,0,0],
 'depreciation_ratio':.055, 'nwc_ratio':.32,'cash_floor_ratio':.035,
 'tax':.17,'cash_yield':.015,'borrowing_rate':.04,'debt_cap':18.,
 'minority_profit_fraction':.0013,'first5_payout':.30,
 'year6_10_growth':[.07,.06,.05,.04,.03],'terminal_growth':.02,
 'terminal_ebit_margin':.15,'net_fixed_capital_per_incremental_sales':.65,
 'core_discount_rates':[.105,.09], 'crosscheck_ev_ebit':[9.5,11.5],
 'tail_year':40,'ordinary_payout_end_year':5,'upstream_delay_years':0,'parent_settlement_to_guangzhou':0.,
 'source_fact_policy':'Opening legal cash/debt allocation and subsidiary reserve/loss balances are research budgets, not disclosed Q3 individual statements. Opening subsidiary positive reserves are not monetized. G loss cushion 0.5bn is deliberately adverse. Engineering payments are included in cash capex, not added twice.',
}
def accrue(e,profit):
    """Profit first repairs accumulated losses; 10% reserve capped at 50% capital."""
    available=max(0.,profit+min(0.,e['re']))
    reserve=min(max(0.,.5*e['capital']-e['reserve']),.1*available)
    e['re']+=profit-reserve;e['reserve']+=reserve
    return reserve

def annual(state, plan, p):
    """One year, including actual subsidiary declarations/cash and parent payment."""
    s=copy.deepcopy(state); before=copy.deepcopy(state); ents=s['entities']; n=len(ents)
    y=plan['year']; rev=plan['revenue']; margin=plan['margin']; capex=plan['capex']
    delta_wc=rev*p['nwc_ratio']-s['nwc']; s['nwc']+=delta_wc
    minimum=[rev*p['cash_floor_ratio']*w for w in p['wc_weights']]
    rows=[]; ni=0.; ops=0.; minor=0.; principal=0.; sale=0.; sale_tax=0.; capital_support=0.
    equity=plan.get('equity',0.);newshares=plan.get('new_shares',0.)
    s['shares']+=newshares; ents[0]['capital']+=newshares; ents[0]['cash']+=equity
    for i,e in enumerate(ents):
        cash_interest=e['cash']*p['cash_yield'] # includes necessary cash, separated from EBIT
        ebit=rev*margin*p['profit_weights'][i]
        interest=e['debt']*p['borrowing_rate'];pretax=ebit-interest+cash_interest
        tax=max(0.,pretax)*p['tax']; profit=pretax-tax
        # Minority cash/profit allocated to residual parent operating bucket, not added back.
        m=max(0,rev*margin*(1-p['tax']))*p['minority_profit_fraction'] if i==0 else 0.
        profit-=m;minor+=m;ni+=profit
        da=rev*p['depreciation_ratio']*p['capital_weights'][i]
        investment=capex*p['capital_weights'][i]; wc=delta_wc*p['wc_weights'][i]
        cf=profit+da-investment-wc
        e['cash']+=cf;ops+=cf
        reserved=accrue(e,profit)
        rows.append({'entity':p['entities'][i],'ebit':ebit,'interest':interest,'cash_interest':cash_interest,'tax':tax,'minority_paid':m,'operating_net_profit':profit,'depreciation':da,'cash_capex':investment,'delta_nwc':wc,'operating_fcfe_before_principal':cf,'reserve_added':reserved,'dividend_declared_paid':0.,'support_received':0.,'principal_repaid':0.})
    # Small noncore equity holding sold in year 3. Only gain creates legal profit.
    if y==3 and s['financial_asset']:
        sale=s['financial_asset'];gain=sale-p['financial_asset_cost'];sale_tax=max(0,gain)*.25
        ents[0]['cash']+=sale-sale_tax;accrue(ents[0],gain-sale_tax);s['financial_asset']=0.
    # Old intercompany settlement changes legal cash only, never group profit.
    settlement=p.get('parent_settlement_to_guangzhou',0.) if y==1 else 0.
    ents[0]['cash']-=settlement;ents[4]['cash']+=settlement
    # Entity debt service precedes remittance; later finite parent borrowing may bridge the stated dividend policy.
    for i,e in enumerate(ents):
        repayment=min(e['debt'],max(0,e['cash']-minimum[i])*(.25 if y<=5 else 1.))
        e['debt']-=repayment;e['cash']-=repayment;principal+=repayment;rows[i]['principal_repaid']=repayment
    # Two-tier U -> G -> P, other subsidiaries -> P. Current declarations are profits;
    # no opening receivable dividends exist, and old cash receipts are never new profit.
    for i,dest in [(3,4),(1,0),(2,0),(4,0)]:
        e=ents[i];payment=min(max(0,e['re']),max(0,e['cash']-minimum[i])) if y>p.get('upstream_delay_years',0) else 0.
        e['cash']-=payment;e['re']-=payment;ents[dest]['cash']+=payment
        added=accrue(ents[dest],payment)
        rows[dest]['reserve_added']+=added;rows[i]['dividend_declared_paid']=payment
    # Legally budgeted paid-in capital support, never profit. Nested U support routed via G.
    for i in [1,2,3,4]:
        gap=max(0,minimum[i]-ents[i]['cash'])
        if gap:
            ents[0]['cash']-=gap;ents[i]['cash']+=gap;ents[i]['capital']+=gap;capital_support+=gap;rows[i]['support_received']+=gap
            if i==3: ents[4]['capital']+=gap # P -> G -> U, G has no net cash gain
    # Finite financing may bridge the historically observed ordinary dividend policy.
    # Mandatory liquidity has first priority; dividend falls to zero before failure.
    desired=max(0,ni)*p['first5_payout'] if y<=p.get('ordinary_payout_end_year',5) else max(0,ents[0]['cash']-minimum[0])
    legal_target=min(desired,max(0,ents[0]['re']))
    need=max(0,minimum[0]+legal_target-ents[0]['cash']);headroom=max(0,p['debt_cap']-sum(e['debt'] for e in ents))
    borrow=min(need,headroom);ents[0]['debt']+=borrow;ents[0]['cash']+=borrow
    shortfall=max(0,minimum[0]-ents[0]['cash'])
    feasible=shortfall<1e-8
    desired=max(0,ni)*p['first5_payout'] if y<=p.get('ordinary_payout_end_year',5) else max(0,ents[0]['cash']-minimum[0])
    payment=min(desired,max(0,ents[0]['re']),max(0,ents[0]['cash']-minimum[0])) if feasible else 0.
    ents[0]['cash']-=payment;ents[0]['re']-=payment
    rows[0]['dividend_declared_paid']=payment
    # Fixed assets track additions excluding old construction payables already capitalized.
    engineering=min(s['engineering_payable'],plan.get('engineering_payment',0.))
    s['engineering_payable']-=engineering
    s['fixed_assets']+=capex-engineering-rev*p['depreciation_ratio']
    s['revenue']=rev;s['year']=y
    closing=sum(e['cash'] for e in ents)
    expected=sum(e['cash'] for e in before['entities'])+ops+sale-sale_tax+equity+borrow-principal-payment
    assert abs(closing-expected)<1e-8,(y,closing,expected)
    assert all(e['reserve']<=e['capital']*.5+1e-8 for e in ents)
    assert all(e['debt']>=-1e-8 for e in ents)
    assert payment<=max(0,ents[0]['re']+payment)+1e-9
    for i,e in enumerate(ents): rows[i].update({'closing_cash':e['cash'],'cash_floor':minimum[i],'closing_debt':e['debt'],'closing_legal_retained':e['re'],'closing_reserve':e['reserve'],'registered_capital':e['capital']})
    return s,{'year':y,'revenue':rev,'ebit_margin':margin,'ebit':rev*margin,'net_profit':ni,'cash_capex':capex,'engineering_payment_in_capex':engineering,'depreciation':rev*p['depreciation_ratio'],'delta_nwc':delta_wc,'nwc':s['nwc'],'fixed_assets':s['fixed_assets'],'operating_fcfe_before_principal':ops,'capital_support':capital_support,'new_external_debt':borrow,'principal_repaid':principal,'parent_old_trade_settlement':settlement,'equity_proceeds':equity,'new_shares':newshares,'shares':s['shares'],'financial_principal_sale':sale,'financial_sale_tax':sale_tax,'total_cash':closing,'total_debt':sum(e['debt'] for e in ents),'common_distribution':payment,'distribution_per_share':payment/s['shares'],'feasible':feasible,'funding_shortfall':shortfall,'entities':rows,'cash_conservation_error':closing-expected}

def initial(p):
    return {'year':0,'revenue':p['opening_revenue'],'shares':p['shares'],'nwc':p['opening_nwc'],'fixed_assets':p['opening_fixed_operating_assets'],'engineering_payable':p['opening_engineering_payable'],'financial_asset':p['opening_financial_asset'],'entities':[{'cash':p['opening_cash'][i],'debt':p['opening_debt'][i],'re':p['opening_legal_retained'][i],'reserve':p['opening_reserves'][i],'capital':p['opening_registered_capital'][i]} for i in range(5)]}

def run(p, label='base', equity=0., new_shares=0.):
    s=initial(p);rows=[];states=[]
    for y in range(1,p['tail_year']+2):
        previous=s['revenue']
        if y<=5:
            rev=p['revenue'][y-1];margin=p['ebit_margin'][y-1];capex=p['cash_capex'][y-1]
        else:
            growth=p['year6_10_growth'][y-6] if y<=10 else p['terminal_growth']
            rev=previous*(1+growth)
            margin=p['ebit_margin'][4]+(p['terminal_ebit_margin']-p['ebit_margin'][4])*min(1,(y-5)/5)
            capex=rev*p['depreciation_ratio']+max(0,rev-previous)*p['net_fixed_capital_per_incremental_sales']
        plan={'year':y,'revenue':rev,'margin':margin,'capex':capex,'engineering_payment':p['engineering_payment'][y-1] if y<=5 else 0.}
        if y==1:plan.update(equity=equity,new_shares=new_shares)
        s,row=annual(s,plan,p);rows.append(row);states.append(copy.deepcopy(s))
        if not row['feasible']:break
    return {'label':label,'inputs':p,'equity_budget':equity,'new_share_budget':new_shares,'feasible':all(x['feasible'] for x in rows),'years':rows,'states':states}

def value(path,rate):
    if not path['feasible']:return {'value_per_share':None,'terminal_year5_per_share':None,'reason':'mandatory funding fails even with zero common dividend'}
    p=path['inputs'];r=path['years'];n=p['tail_year'];g=p['terminal_growth']
    terminal=r[n]['distribution_per_share']/(rate-g)
    pv=sum(x['distribution_per_share']/(1+rate)**x['year'] for x in r[:n])+terminal/(1+rate)**n
    tv5=sum(x['distribution_per_share']/(1+rate)**(x['year']-5) for x in r[5:n])+terminal/(1+rate)**(n-5)
    first5=sum(x['distribution_per_share']/(1+rate)**x['year'] for x in r[:5])
    assert abs(pv-first5-tv5/(1+rate)**5)<1e-7
    # By stable period no unmodeled old financial cash remains and all debts cleared.
    assert sum(e['debt'] for e in path['states'][-1]['entities'])<1e-7
    assert abs(r[n]['distribution_per_share']/r[n-1]['distribution_per_share']-(1+g))<1e-7
    return {'discount_rate':rate,'value_per_share':pv,'terminal_year5_per_share':tv5,'pv_first5':first5,'pv_terminal_year5':tv5/(1+rate)**5,'terminal_pv_share':(pv-first5)/pv,'terminal_year40_per_share':terminal}

def hand_tests():
    p=copy.deepcopy(INPUTS);p.update(tax=0,cash_yield=0,borrowing_rate=0,nwc_ratio=0,cash_floor_ratio=0,depreciation_ratio=0,minority_profit_fraction=0,first5_payout=1,debt_cap=0,profit_weights=[1,0,0,0,0],capital_weights=[1,0,0,0,0],wc_weights=[1,0,0,0,0])
    s=initial(p);s.update(nwc=0,financial_asset=0,engineering_payable=0)
    for e in s['entities']:e.update(cash=0,debt=0,re=0,reserve=.5,capital=1)
    # 10 revenue x 20% margin - 0.5 capex = 1.5 cash, reserve at cap, profit 2.
    s1,a=annual(s,{'year':1,'revenue':10,'margin':.2,'capex':.5},p)
    assert abs(a['common_distribution']-1.5)<1e-10 and abs(s1['entities'][0]['re']-.5)<1e-10
    # Same function: accumulated loss 3 and 2 profit, cash present but no legal payout.
    t=copy.deepcopy(s);t['entities'][0]['re']=-3
    t1,b=annual(t,{'year':1,'revenue':10,'margin':.2,'capex':0},p)
    assert b['common_distribution']==0 and t1['entities'][0]['re']==-1
    # 0-profit 1 capex, no cash/no credit: zero dividends still fails.
    _,c=annual(s,{'year':1,'revenue':0,'margin':0,'capex':1},p)
    assert not c['feasible'] and c['common_distribution']==0 and abs(c['funding_shortfall']-1)<1e-10
    # reserve shortfall: profit2, opening reserves0, capital1 -> reserve.2 payout1.8.
    t=copy.deepcopy(s);t['entities'][0]['reserve']=0
    _,d=annual(t,{'year':1,'revenue':10,'margin':.2,'capex':0},p)
    assert abs(d['common_distribution']-1.8)<1e-10
    # Two-tier legal test: U earns 2, G has loss 3. Its cash receipt does not
    # create fresh group earnings or permit dividend before loss recovery.
    q=copy.deepcopy(p);q['profit_weights']=[0,0,0,1,0]
    t=copy.deepcopy(s);t['entities'][4]['re']=-3
    t1,e=annual(t,{'year':1,'revenue':10,'margin':.2,'capex':0},q)
    assert e['common_distribution']==0 and abs(t1['entities'][4]['cash']-2)<1e-10
    assert t1['entities'][4]['re']==-1
    t2,f=annual(t1,{'year':2,'revenue':10,'margin':.2,'capex':0},q)
    assert abs(f['common_distribution']-1)<1e-10
    assert abs(t2['entities'][4]['cash']-3)<1e-10 and t2['entities'][4]['re']==0
    return {'formal_annual_function_cash_1_5':'pass','loss_carryforward_blocks_cash':'pass','zero_dividend_insolvency_fails':'pass','reserve_cap_and_accrual':'pass','two_tier_loss_cash_release_no_double_profit':'pass'}

def main():
    scenarios={};base=run(copy.deepcopy(INPUTS));scenarios['base']=base
    settings={
      'cyclical':{'revenue':[34,37,44,51,56],'ebit_margin':[.14,.15,.17,.18,.18],'cash_capex':[7,4.5,4.8,4.8,4.8],'nwc_ratio':.37},
      'structural':{'revenue':[34,35,37,39,41],'ebit_margin':[.12,.115,.11,.105,.10],'cash_capex':[7,4,3.5,3.2,3.2],'nwc_ratio':.38,'terminal_ebit_margin':.10,'terminal_growth':.01,'year6_10_growth':[.02]*5,'net_fixed_capital_per_incremental_sales':.8},
      'upside':{'revenue':[43,53,62,70,77],'ebit_margin':[.21,.21,.205,.20,.195],'cash_capex':[9,7,6.5,6.2,6],'terminal_ebit_margin':.16,'nwc_ratio':.32},
      'margin_minus_2pp_from_year1':{'ebit_margin':[x-.02 for x in INPUTS['ebit_margin']],'terminal_ebit_margin':.13},
      'wc_plus_5pp_from_year1':{'nwc_ratio':.37},
      'borrowing_plus_2pp_from_year1':{'borrowing_rate':.06},
      'guangzhou_loss_2bn':{'opening_legal_retained':[3.87016577999,0,0,0,-2.]},
      'upstream_delay_one_year_parent_pays_1bn':{'upstream_delay_years':1,'parent_settlement_to_guangzhou':1.},
      'financial_release_delayed_to_year11':{'ordinary_payout_end_year':10},
      'debt_cap_11bn':{'debt_cap':11.},
      'cash_capex_plus_20pct_first5':{'cash_capex':[x*1.2 for x in INPUTS['cash_capex']]},
    }
    for name,over in settings.items():
        p=copy.deepcopy(INPUTS);p.update(over);scenarios[name]=run(p,name)
    scenarios['incentive_refund_cancel']=run(copy.deepcopy(INPUTS),'incentive_refund_cancel',-1.624123968,-.0144258)
    for dilution in [.03,.06]:
        name='equity_4_30bn_newshares_'+str(dilution);scenarios[name]=run(copy.deepcopy(INPUTS),name,4.3,dilution)
    valuations={name:{'low':value(path,.105),'high':value(path,.09)} for name,path in scenarios.items()}
    # Auxiliary mature year-10 EBIT capitalization. All legacy financial cash
    # and first-five-year surplus run through actual legal distributions first.
    yr10=base['years'][9]
    assert abs(yr10['total_cash']-yr10['revenue']*INPUTS['cash_floor_ratio'])<1e-7
    assert yr10['total_debt']<1e-7
    auxiliary=[]
    for multiple,rate in zip(INPUTS['crosscheck_ev_ebit'],INPUTS['core_discount_rates']):
        equity_tv=(yr10['ebit']*multiple-yr10['total_debt'])/yr10['shares']
        pv=sum(x['distribution_per_share']/(1+rate)**x['year'] for x in base['years'][:10])+equity_tv/(1+rate)**10
        auxiliary.append({'ev_ebit_multiple':multiple,'rate':rate,'year10_ebit':yr10['ebit'],'year10_debt':yr10['total_debt'],'year10_cash_all_necessary':yr10['total_cash'],'year10_equity_per_share':equity_tv,'current_value_per_share':pv,'limitation':'Mature year10 capitalization after actual years1-10 legal cash releases. Necessary operating cash included in enterprise economics, no separately added principal. Shares/operating forecasts shared with primary method.'})
    out={'identity':{'symbol':'CN:002916','period':'2026-Q3'},'units':'CNY billion except per-share CNY','inputs':INPUTS,'scenarios':scenarios,'valuations':valuations,'auxiliary':auxiliary,'hand_tests':hand_tests(),'core_value_range':{'low':round(valuations['base']['low']['value_per_share'],1),'high':round(valuations['base']['high']['value_per_share'],1)},'base_distributions_per_share':[round(x['distribution_per_share'],6) for x in base['years'][:5]],'base_terminal_year5':{'low':round(valuations['base']['low']['terminal_year5_per_share'],6),'high':round(valuations['base']['high']['terminal_year5_per_share'],6)}}
    (ROOT/'2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({k:out[k] for k in ['core_value_range','base_distributions_per_share','base_terminal_year5','hand_tests']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
