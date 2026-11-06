#!/usr/bin/env python3
"""三瑞智能2026Q3；金额百万元，股数百万股；标准库、无文件输入。"""
import json, copy, math

def condition_ratio(growth,tranche):
    trigger=[.2,.4,.6][tranche]; full=[.5,1,1.5][tranche]
    return 0.0 if growth<trigger-1e-12 else min(1.0,.6+.4*(growth-trigger)/(full-trigger))

def grant_pools(include_reserve=False):
    pools=[]
    for kind,shares,cost,opening,enabled in [('first',.99,63.4273,7.34999118,True),('reserve',.2475,15.856825,0,include_reserve)]:
        for i,weight in enumerate([.33,.33,.34]):
            pools.append(dict(id=kind+'-'+str(i+1),max_shares=shares*weight,total_cost=cost*weight,opening_cost=opening*weight,grant_year=1,performance_year=i+1,issue_year=i+2,enabled=enabled,initial_expected_ratio=1))
    return pools

def assumptions():
    return dict(drone=[1640,1870,2080,2245,2400,2520,2620,2700,2750,2800],robot=[180,240,310,390,470,540,600,650,690,720],jv=[80,96,110,121,131,138,144,150,155,160],dm=[.33,.33,.325,.32,.315,.30,.285,.27,.26,.25],rm=[.25,.26,.27,.28,.28,.27,.26,.25,.24,.23],jm=[.15]*5+[.14,.135,.13,.125,.12],wc=[.12]*10,run=.08,project=[250,160,80]+[0]*7,capacity=2024.63587552,cap=.34,parent_share=.90,cash=[1550,269.86597613,30],debt=[0,3.17227943,4.47555138],wc0=[125.548648416,13.949849824,10],retained=[568.42422395,100,20],reserve=[118.75012332,10,5],capital=[400.01,50,20],shares=400.01,ownership=.55,other_minority=3.63757149,grants=grant_pools(),fy26_revenue=1700,fy26_gate_profit_bridge=dict(operating_common=593.4,recurring_financial=7,financing=.2,other_minorities=.2),recurring_financial_fraction=.25,other_minority_profit0=.363757149,issue_price=59.275,yield_rate=.015,debt_rate=.05,payout=.50,k=.105,g=.025,roic=.15,ipo_extra=121.4283,rd_ring=90.93,wc_ring=83.9647)

def legal(retained,reserve,profit,capital):
    after=retained+profit
    provision=min(max(profit-max(-retained,0),0)*.10,max(capital*.5-reserve,0))
    return after-provision,reserve+provision,provision

def run(a):
    cash=a['cash'][:]; debt=a['debt'][:]; wc=a['wc0'][:]; retained=a['retained'][:]; reserve=a['reserve'][:]; capreg=a['capital'][:]
    surplus=[887.31127393,0,0]; shares=a['shares']
    pools=copy.deepcopy(a.get('grants',[])); achieved={}
    for pool in pools:
        pool['recognized']=pool['opening_cost']; pool['previous_ratio']=1.0
    bp=a['fy26_gate_profit_bridge']
    base_recurring=bp['operating_common']+bp['recurring_financial']-bp['financing']-bp['other_minorities']
    assert base_recurring>0
    last_core=a['capacity']; rows=[]; old_required=None; ipo_extra=a['ipo_extra']; cumulative_dps=0
    for t in range(10):
        core=a['drone'][t]+a['robot'][t]; jr=a['jv'][t]; p=a['parent_share']; own=[1,1,a['ownership']]
        rev=[p*core,(1-p)*core,jr]
        operating=a['drone'][t]*a['dm'][t]+a['robot'][t]*a['rm'][t]
        nopat=[p*operating,(1-p)*operating,jr*a['jm'][t]]
        nextwc=[r*a['wc'][t] for r in rev]; delta=[nextwc[i]-wc[i] for i in range(3)]; wc=nextwc
        growth=a['cap']*max(core-max(last_core,a['capacity']),0); last_core=max(last_core,core)
        jgrowth=a['cap']*max(jr-(a['jv'][t-1] if t else jr),0)
        investment=[a['project'][t]+p*growth,(1-p)*growth,jgrowth]
        required=[r*a['run'] for r in rev]
        required_common=sum(required[i]*own[i] for i in range(3))
        delta_required=0 if old_required is None else required_common-old_required; old_required=required_common
        opening=cash[:]; opening_debt=debt[:]; interest_income=[max(c,0)*a['yield_rate'] for c in cash]; interest_cost=[d*a['debt_rate'] for d in debt]
        other_minor_profit=a.get('other_minority_profit0',0)*1.1**(t+1)
        gate_bridge=dict(operating_common=sum(nopat[i]*own[i] for i in range(3)),recurring_financial=sum(interest_income[i]*own[i] for i in range(3))*a['recurring_financial_fraction'],financing=sum(interest_cost[i]*own[i] for i in range(3)),other_minorities=other_minor_profit)
        gate_profit=gate_bridge['operating_common']+gate_bridge['recurring_financial']-gate_bridge['financing']-gate_bridge['other_minorities']
        gate_ratio=None
        if t<3:
            revenue_growth=(core+jr)/a['fy26_revenue']-1
            profit_growth=gate_profit/base_recurring-1
            gate_ratio=condition_ratio(max(revenue_growth,profit_growth),t)
            achieved[t+1]=gate_ratio
        issued=0; sbc_expense=0; sbc_reversal=0; pool_rows=[]
        for pool in pools:
            previous=pool['recognized']; old_ratio=pool['previous_ratio']
            active=pool['enabled'] and t+1>=pool['grant_year']
            ratio=achieved.get(pool['performance_year'],pool.get('initial_expected_ratio',1)) if active else 0
            if not active:
                service=0
            else:
                elapsed=max(0,min(t+2-pool['grant_year'],pool['issue_year']-pool['grant_year']+1))
                future_fraction=elapsed/(pool['issue_year']-pool['grant_year']+1)
                service=pool['opening_cost']/pool['total_cost']+(1-pool['opening_cost']/pool['total_cost'])*future_fraction if pool['total_cost'] else 1
            target=pool['total_cost']*ratio*service
            remeasured=previous*ratio/old_ratio if old_ratio else 0
            remeasurement=remeasured-previous; service_cost=target-remeasured
            expense=max(remeasurement,0)+max(service_cost,0)
            reversal=max(-remeasurement,0)+max(-service_cost,0)
            shares_issued=pool['max_shares']*ratio if active and t+1==pool['issue_year'] else 0
            issued+=shares_issued; sbc_expense+=expense; sbc_reversal+=reversal
            assert abs(previous+expense-reversal-target)<1e-9
            pool_rows.append(dict(pool=pool['id'],active=active,ratio=ratio,service_fraction=service,previous_recognized=previous,expense=expense,reversal=reversal,cumulative_recognized=target,issued_shares=shares_issued,max_shares=pool['max_shares']))
            pool['recognized']=target; pool['previous_ratio']=ratio
        proceeds=issued*max(a['issue_price']-cumulative_dps,1.000001); shares+=issued; capreg[0]=shares
        accounting=[nopat[i]+interest_income[i]-interest_cost[i]-(sbc_expense-sbc_reversal if i==0 else 0) for i in range(3)]
        surplus[0]+=proceeds-issued+sbc_expense-sbc_reversal
        provisions=[]
        for i in range(3):
            retained[i],reserve[i],pr=legal(retained[i],reserve[i],accounting[i],capreg[i]); provisions.append(pr)
            cash[i]+=nopat[i]+interest_income[i]-interest_cost[i]-delta[i]-investment[i]
        cash[0]+=proceeds
        # IPO restrictions reserve future commitments. R&D already expensed in margin; WC already in delta.
        ipo_extra=max(ipo_extra-growth,0)
        ring=sum(a['project'][t+1:])+a['rd_ring']*max(2-t,0)/3+a['wc_ring']*max(2-t,0)/3+ipo_extra
        floors=[required[0]+ring,required[1],required[2]]
        repaid=[]; newdebt=[]
        for i in range(3):
            pay=min(debt[i],max(cash[i]-floors[i],0)); cash[i]-=pay; debt[i]-=pay; repaid.append(pay)
            borrow=max(floors[i]-cash[i],0); cash[i]+=borrow; debt[i]+=borrow; newdebt.append(borrow)
        earnings=sum((nopat[i]+interest_income[i]-interest_cost[i])*own[i] for i in range(3))-other_minor_profit
        distribution=min(max(earnings*a['payout'],0),max(retained[0],0),max(cash[0]-floors[0],0))
        cash[0]-=distribution; retained[0]-=distribution; dps=distribution/shares; cumulative_dps+=dps
        for i in range(3):
            expected=opening[i]+nopat[i]+interest_income[i]-interest_cost[i]-delta[i]-investment[i]+(proceeds-distribution if i==0 else 0)-repaid[i]+newdebt[i]
            assert math.isclose(cash[i],expected,abs_tol=1e-8)
            assert cash[i]>=floors[i]-1e-8
        fcf=sum((nopat[i]-delta[i]-investment[i])*own[i] for i in range(3))
        rows.append(dict(year=t+1,revenue=rev,nopat=nopat,noncash_wc=wc[:],delta_wc=delta,physical_investment=investment,depreciation=[r*.02 for r in rev],maintenance_capex=[r*.02 for r in rev],required_cash=required,delta_common_required_cash=delta_required,common_fcf=fcf,common_owner_fcfe=fcf-delta_required,opening_cash=opening,financial_income=interest_income,interest=interest_cost,opening_debt=opening_debt,repayment=repaid,new_debt=newdebt,debt=debt[:],cash=cash[:],accounting_profit=accounting,legal_retained=retained[:],legal_reserve=reserve[:],statutory_provision=provisions,registered_capital=capreg[:],capital_surplus=surplus[:],sbc_expense=sbc_expense,sbc_reversal=sbc_reversal,restricted_parent_cash=ring,issue_proceeds=proceeds,issued_shares=issued,vesting_ratio=achieved.get(t,0),performance_ratio=gate_ratio,contract_profit_bridge=gate_bridge,contract_recurring_profit_ex_sbc=gate_profit,sbc_pools=pool_rows,shares=shares,distribution=distribution,dps=dps))
    k,g,roic=a['k'],a['g'],a['roic']; own=a['ownership']; r5=rows[4]; r10=rows[9]
    cash5=sum(r5['cash'][i]*[1,1,own][i] for i in range(3)); required5=sum(r5['required_cash'][i]*[1,1,own][i] for i in range(3)); debt5=sum(r5['debt'][i]*[1,1,own][i] for i in range(3))
    tail_nopat=sum(r10['nopat'][i]*[1,1,own][i] for i in range(3))*(1+g)
    reinvest=tail_nopat*g/roic; cash_tail=sum(r10['required_cash'][i]*[1,1,own][i] for i in range(3))*g
    assert reinvest>=cash_tail-1e-8 and k>g
    gordon=(tail_nopat-reinvest)/(k-g)
    op5=sum(rows[t]['common_owner_fcfe']/(1+k)**(t-4) for t in range(5,10))+gordon/(1+k)**5
    other=a['other_minority']*1.1**5
    restricted5=r5['restricted_parent_cash']
    # Stranded earmarks: income capitalization, no hypothetical free principal release.
    restricted_value=restricted5*a['yield_rate']/k
    bridge=cash5-required5-debt5-other-restricted5+restricted_value
    tv=(op5+bridge)/r5['shares']; divpv=sum(rows[t]['dps']/(1+k)**(t+1) for t in range(5)); value=divpv+tv/(1+k)**5
    mature5=a['drone'][4]*a['dm'][-1]+a['robot'][4]*a['rm'][-1]+a['jv'][4]*a['jm'][-1]*own
    auxiliary_tv=(mature5*(1+g)*(1-g/roic)/(k-g)+bridge)/r5['shares']
    return dict(inputs=a,years=rows,value=value,terminal5=tv,dividend_pv=divpv,terminal_pv_share=(tv/(1+k)**5)/value,operating_value5=op5,financial_principal5=cash5,required_cash5=required5,debt5=debt5,other_minority5=other,equity_bridge5=bridge,restricted_principal5=restricted5,restricted_principal_income_value5=restricted_value,tail_nopat=tail_nopat,tail_total_reinvestment=reinvest,tail_running_cash_included=cash_tail,gordon10=gordon,auxiliary_value=divpv+auxiliary_tv/(1+k)**5)

def cases():
    b=assumptions(); d={'base':b}
    for name,k,g,roic in [('low',.11,.02,.14),('high',.10,.025,.16)]:
        a=copy.deepcopy(b); a.update(k=k,g=g,roic=roic); d[name]=a
    c=copy.deepcopy(b)
    for field in ['drone','robot','jv']: c[field]=[v*[.8,.85,.95,1,1,1,1,1,1,1][t] for t,v in enumerate(c[field])]
    for field in ['dm','rm','jm']: c[field]=[v-[.05,.03,.01,0,0,0,0,0,0,0][t] for t,v in enumerate(c[field])]
    c.update(wc=[.16,.16,.14]+[.12]*7,project=[150,160,130,50]+[0]*6); d['cyclical']=c
    s=copy.deepcopy(b); s.update(drone=[1300,1350,1400,1400,1400,1400,1400,1400,1400,1400],robot=[140,160,180,200,210,220,230,230,230,230],dm=[.18]*10,rm=[.16]*10,jm=[.10]*10,wc=[.18]*10,g=.01,roic=.10); d['structural']=s
    u=copy.deepcopy(b)
    for f in ['drone','robot']: u[f]=[v*1.15 for v in u[f]]
    for f in ['dm','rm']: u[f]=[v+.02 for v in u[f]]
    d['upside']=u
    ur=copy.deepcopy(u); ur['grants']=grant_pools(True); d['upside_reserve_granted']=ur
    for label,which in [('sbc_opening_first_only',0),('sbc_opening_last_only',2)]:
        stress=copy.deepcopy(b)
        for i,pool in enumerate(stress['grants'][:3]):pool['opening_cost']=7.34999118 if i==which else 0
        d[label]=stress
    full=copy.deepcopy(b); full['grants']=grant_pools(True)
    for field in ['drone','robot','jv']:full[field]=[v*2 for v in full[field]]
    d['maximum_grant_business_stress']=full
    for name,field,delta in [('margin_minus_3pp','dm',-.03),('demand_minus_20pct','drone',.8)]:
        a=copy.deepcopy(b)
        for f in (['dm','rm'] if field=='dm' else ['drone','robot']): a[f]=[v+delta if field=='dm' else v*delta for v in a[f]]
        d[name]=a
    for name,patch in [('capital_50pct',{'cap':.5}),('parent_profit_60pct',{'parent_share':.6,'cash':[1250,569.86597613,30]}),('reserve_not_granted',{}),('reserve_conditional_grant',{'grants':grant_pools(True)}),('financial_gate_none',{'recurring_financial_fraction':0}),('financial_gate_all',{'recurring_financial_fraction':1}),('deposit_excluded',{'cash':[1390,269.86597613,30]}),('no_other_debt',{'debt':[0,0,4.47555138]}),('all_other_payables_debt',{'debt':[0,5.05557835,4.47555138]}),('cost_of_equity9',{'k':.09}),('cost_of_equity12',{'k':.12}),('payout25',{'payout':.25}),('roic_equals_cost',{'roic':.105}),('extra_project100',{'project':[350,160,80]+[0]*7})]:
        a=copy.deepcopy(b); a.update(patch); d[name]=a
    return d

def tests():
    a=assumptions()
    a.update(drone=[100]*5+[200]*5,robot=[0]*10,jv=[0]*10,dm=[.2]*10,rm=[0]*10,jm=[0]*10,wc=[0]*10,run=.08,project=[0]*10,cap=0,parent_share=1,cash=[50,0,0],debt=[0]*3,wc0=[0]*3,retained=[0]*3,reserve=[5,0,0],capital=[10,0,0],shares=10,yield_rate=0,payout=0,k=.1,g=0,roic=.1,ipo_extra=0,rd_ring=0,wc_ring=0,other_minority=0,grants=[],other_minority_profit0=0)
    r=run(a)
    expected=(142+32/1.1+sum(40/1.1**j for j in range(2,6))+400/1.1**5)/(10*1.1**5)
    assert abs(r['value']-expected)<1e-10
    assert r['years'][5]['cash'][0]==190 and r['years'][5]['common_owner_fcfe']==32
    assert legal(-10,0,20,100)==(9,1,1)
    a.update(drone=[100]*10,payout=.5,retained=[-10,0,0],reserve=[0,0,0]); loss=run(a)
    assert loss['years'][0]['distribution']==9 and loss['years'][0]['legal_reserve'][0]==1
    a.update(cash=[0,0,0],project=[100]+[0]*9); funding=run(a)
    assert funding['years'][0]['new_debt'][0]==88 and funding['years'][0]['distribution']==0
    mixed=copy.deepcopy(a)
    mixed.update(drone=[100,200]+[250]*8,dm=[.1]*10,project=[0]*10,cash=[100,0,0],debt=[0]*3,retained=[0]*3,reserve=[5,0,0],payout=0,fy26_revenue=100,fy26_gate_profit_bridge=dict(operating_common=10,recurring_financial=0,financing=0,other_minorities=0),recurring_financial_fraction=0)
    mixed['grants']=[dict(id='test-'+str(i),max_shares=.1,total_cost=3,opening_cost=1,grant_year=1,performance_year=i+1,issue_year=i+2,enabled=True,initial_expected_ratio=1) for i in range(3)]
    mr=run(mixed); first=mr['years'][0]
    assert [r['performance_ratio'] for r in mr['years'][:3]]==[0,1,1]
    assert abs(first['sbc_reversal']-1)<1e-10 and abs(first['sbc_expense']-7/6)<1e-10
    assert abs(first['accounting_profit'][0]-(10-1/6))<1e-10 and first['cash'][0]==110
    assert abs(first['capital_surplus'][0]-(887.31127393+1/6))<1e-10
    assert mr['years'][1]['issued_shares']==0 and mr['years'][2]['issued_shares']==.1
    partial=copy.deepcopy(mixed); partial['drone'][0]=135; pr=run(partial); pool=pr['years'][0]['sbc_pools'][0]
    assert abs(pool['ratio']-.8)<1e-10 and abs(pool['expense']-.8)<1e-10 and abs(pool['reversal']-.2)<1e-10 and abs(pool['cumulative_recognized']-1.6)<1e-10
    # Revenue flat but recurring bank income triggers the profit test; nonrecurring income excluded.
    profit=copy.deepcopy(mixed); profit.update(drone=[100]*10,cash=[40,0,0],yield_rate=.1,recurring_financial_fraction=1)
    gr=run(profit); gp=gr['years'][0]
    assert gp['contract_recurring_profit_ex_sbc']==14 and abs(gp['performance_ratio']-13/15)<1e-10
    profit['recurring_financial_fraction']=0; excluded=run(profit)
    assert excluded['years'][0]['performance_ratio']==0 and excluded['years'][0]['contract_recurring_profit_ex_sbc']==10
    ceiling=assumptions();ceiling['grants']=grant_pools(True)
    for field in ['drone','robot','jv']:ceiling[field]=[v*2 for v in ceiling[field]]
    cr=run(ceiling);pool_cost=sum(p['cumulative_recognized'] for p in cr['years'][4]['sbc_pools'])
    assert abs(cr['years'][4]['shares']-401.2475)<1e-9 and abs(pool_cost-79.284125)<1e-9
    return dict(nonzero_cash_growth={'production':r['value'],'literal':expected,'year6_cash':190,'year6_owner_fcfe':32},legal_loss_makeup={'year1_distribution':loss['years'][0]['distribution'],'reserve':1},funding_constraint={'year1_new_debt':88,'dividend':0},mixed_vesting={'ratios':[0,1,1],'expense':first['sbc_expense'],'reversal':first['sbc_reversal'],'cash':first['cash'][0],'accounting_profit':first['accounting_profit'][0]},partial_vesting=pool,profit_only_trigger={'recurring_profit':14,'ratio':gp['performance_ratio'],'excluded_nonrecurring_ratio':0},reserve_full_cost={'fully_issued_shares':cr['years'][4]['shares'],'recognized_first_and_reserve_cost':pool_cost})

if __name__=='__main__':
    output={'company':'CN:301696','period':'2026-Q3','unit':'CNY million and million shares','scenarios':{n:run(a) for n,a in cases().items()},'production_tests':tests()}
    print(json.dumps(output,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False))
