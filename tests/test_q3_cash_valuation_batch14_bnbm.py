#!/usr/bin/env python3
"""Independent literal-input reconstruction. Does not read/import/parse model code.
Inputs below independently re-keyed from source/assumption ledger. Formal output is
opened ONLY after all independent calculations, solely for comparison.
Units: billion CNY and billion shares. Separate state representation and loops.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/000786/models'
# revenue, margins, growth, tax, common ownership, DA, maintenance ratio, fixed intensity, WC intensity, acquisitions
BUSINESSES=[
 [15.,[.145,.15,.155,.16,.16,.16,.1575,.155,.1525,.15],[0,.01,.02,.02,.02,.02,.02,.015,.015,.01],.10,.995,.06,1.,.35,.12,[.05,.05,.05,0,0,0,0,0,0,0]],
 [5.3,[.08,.082,.085,.085,.085,.085,.083,.082,.081,.08],[.04,.04,.04,.03,.03,.025,.025,.02,.015,.01],.15,.95,.022,1.05,.35,.45,[.1,.1,.05,.05,0,0,0,0,0,0]],
 [4.5,[.08,.085,.09,.095,.095,.095,.0925,.09,.0875,.085],[.05,.05,.04,.04,.03,.03,.025,.02,.015,.01],.15,.8,.04,1.,.4,.25,[.1,.1,.05,.05,0,0,0,0,0,0]]]
DEBT=.41266416026+.15804510242+.08298035033+.13135629318+1.+.15035-.03
CASES={
 'base':([0]*10,[0]*10,[0]*10,0,.5,.3,1),
 'light_margin_minus_2pp':([0]*10,[0]*10,[0]*10,-.02,.5,.3,1),
 'cyclical_weak':([-.08,-.03,.04,.03,.01,0,0,0,0,0],[-.025,-.015,-.005,0,0,0,0,0,0,0],[.8,.3,-.5,-.3,-.3,0,0,0,0,0],0,.5,.3,1),
 'structural_adverse':([-.06,-.05,-.04,-.03,-.02,-.02,-.02,-.015,-.015,-.01],[-.04]*10,[.5,.3,.2,0,0,0,0,0,0,0],0,.5,.3,1),
 'optimistic':([.02]*5+[.01]*5,[.01]*10,[0]*10,0,.5,.3,1),
 'pool_cash_stress':([0]*10,[0]*10,[0]*10,0,1.5,.1,3)}

def source_budget(balance, profit, target, money, capital):
    retained,reserve=balance
    positive_after_loss=max(0,min(profit,retained+profit))
    transfer=min(max(0,capital/2-reserve),positive_after_loss/10)
    lawful=retained+profit-transfer
    dividend=max(0,min(target,money,lawful))
    return [lawful-dividend,reserve+transfer],dividend

def independent(case,r,g):
    dg,dm,stress,lightshift,payrate,collectionrate,oldyear=CASES[case]
    if case=='structural_adverse':g=0
    roic=.07 if case=='structural_adverse' else .10
    revenue=[15.,5.3,4.5]; previous_nopat=None
    cash=[2.8,4.13972111738-.1-2.8]; debt=[1.,DEBT-1.]
    pool=[10.,2.8];old=.159;acq=.81699029771;shares=1.697823974
    mother=[2.5585150299,.8704664345];taishan=[3.,0.];others=[[0.,0.] for _ in range(3)]
    lastprofit=0;trace=[];pv=0;first5=0
    for year in range(1,401):
        t=year-1; operating=[];reinvestment=0;growthcap=0
        for i,b in enumerate(BUSINESSES):
            last=revenue[i]
            if year<=10:
                revenue[i]=last*(1+b[2][t]+dg[t]); margin=b[1][t]+dm[t]+(lightshift if i==0 else 0)
                eb=revenue[i]*margin;np=eb-max(eb,0)*b[3]
                fix=max(revenue[i]-last,0)*b[7]
                inv=revenue[i]*b[5]*(b[6]-1)+fix+(revenue[i]-last)*b[8]+b[9][t]
                growthcap+=fix*b[4]
            else:
                revenue[i]=last*(1+g);np=previous_nopat[i]*(1+g);eb=np/(1-b[3]);inv=np*g/roic+revenue[i]*b[5]*(b[6]-1)
            operating.append((np,eb,np*b[4]));reinvestment+=inv*b[4]
        previous_nopat=[x[0] for x in operating]
        if year<=10:reinvestment+=stress[t]+max(0,([.55,.5,.25]+[0]*7)[t]-growthcap)
        mother_finance=-.1+.02*cash[0]+.02*(pool[1]-pool[0])-min(debt[0],1.)*.03-max(0,debt[0]-1.)*.035
        mother_np=mother_finance-max(mother_finance,0)*.25
        treasury=.02*cash[1]+.02*(pool[0]-pool[1])-min(debt[1],DEBT-1.)*.03-max(0,debt[1]-DEBT+1.)*.035
        tax_treasury=(max(operating[0][1]+treasury,0)-max(operating[0][1],0))*.1
        sub_np=sum(x[2] for x in operating)+treasury-tax_treasury
        profit=mother_np+sub_np;cash[0]+=mother_np;cash[1]+=sub_np-reinvestment
        payment=min(pool[0],payrate);collection=min(pool[1],collectionrate);oldcash=old if year==oldyear else 0
        pool[0]-=payment;pool[1]-=collection;old-=oldcash
        cash[0]+=collection-payment+oldcash;cash[1]+=payment-collection-oldcash
        acqpay=min(acq,([.4,.41699029771]+[0]*8)[t] if t<10 else 0);acq-=acqpay;cash[0]-=acqpay
        if year<=2:cash[0]-=.071114680725;shares-=.004158066
        ramp=0 if year<=5 else min(1,(year-5)/5)
        redeem=min(debt[1],max(0,cash[1]-.8)*ramp);cash[1]-=redeem;debt[1]-=redeem
        tnp=operating[0][0]*.85*.7
        taishan,up=source_budget(taishan,tnp,tnp+max(taishan[0],0)*ramp,max(0,cash[1]-.8)*.8,.155625)
        cash[0]+=up;cash[1]-=up
        for i in range(3):
            profit_i=operating[i][2]+(treasury-tax_treasury-tnp if i==0 else 0)
            target=max(others[i][0]+profit_i,0)*ramp
            others[i],d=source_budget(others[i],profit_i,target,max(0,cash[1]-.8),[2.,1.,1.][i])
            up+=d;cash[0]+=d;cash[1]-=d
        if year==10:cash[0]+=.06725058679+.14303061780
        redeem=min(debt[0],max(0,cash[0]-.3)*ramp);cash[0]-=redeem;debt[0]-=redeem
        want=.9 if year==1 else max(lastprofit*.4,0)
        mother,d=source_budget(mother,mother_np+up,want,max(0,min(cash[0]-.3,sum(cash)-1.1)),shares)
        cash[0]-=d
        extra=max(0,min(mother[0],max(0,cash[0]-.3)))*ramp
        mother[0]-=extra;cash[0]-=extra;d+=extra
        for i,minimum in enumerate([.3,.8]):
            shortfall=max(0,minimum-cash[i]);cash[i]+=shortfall;debt[i]+=shortfall
        assert debt[0]-1.<=2.5+1e-8 and debt[1]-(DEBT-1.)<=1+1e-8
        dps=d/shares;pv+=dps/(1+r)**year
        if year<=5:first5+=dps/(1+r)**year
        trace.append({'year':year,'dps':dps,'cash':cash[:],'debt':debt[:],'mother_retained':mother[0],'sub_retained':taishan[0]+sum(x[0] for x in others),'common_np':profit,'reinvestment':reinvestment})
        lastprofit=profit
    return {'value':pv,'tv5':(pv-first5)*(1+r)**5,'trace':trace}


def test_bnbm_literal_full_tail_endpoints_and_sensitivities():
    formal=json.loads((ROOT/'2026-Q3-output.json').read_text())
    for case in CASES:
        for ep,r,g in [('low',.10,.005),('high',.09,.01)]:
            mine=independent(case,r,g); actual=formal['scenarios'][case][ep]
            assert abs(mine['value']-actual['current_value_per_share'])<1e-9
            assert abs(mine['tv5']-actual['tv5_per_share'])<1e-9
            start=formal['scenarios'][case]; tail=actual['trajectory']['continuation']
            rows=[]
            for part in [start,tail]:
                for i,v in enumerate(part['annual_values']):
                    a=dict(zip(part['annual_columns'],v))
                    legal=part['legal']['parent_legal']
                    a['parent_legal']=dict(zip(legal['columns'],legal['values'][i]))
                    rows.append(a)
            assert len(rows)==len(mine['trace'])==400
            for a,b in zip(mine['trace'],rows):
                assert abs(a['dps']-b['dps'])<1e-9
                assert abs(a['cash'][0]-b['parent_cash'])<1e-8
                assert abs(a['cash'][1]-b['sub_common_cash'])<1e-8
                assert abs(a['mother_retained']-b['parent_legal']['retained'])<1e-8
                assert abs(a['sub_retained']-b['legal_source_retained_total'])<1e-7
                assert abs(a['common_np']-b['common_net_profit'])<1e-8
                assert abs(a['reinvestment']-b['common_reinvestment'])<1e-8

def test_bnbm_actual_functions_and_convergence():
    import runpy
    m=runpy.run_path(str(ROOT/'2026-Q3.py')); m['tests']()
    o=json.loads((ROOT/'2026-Q3-output.json').read_text())
    for ep in ['low','high']:
        c=o['convergence'][ep]; assert abs(c['400']-c['250'])<1e-6
        a=o['scenarios']['base'][ep]
        assert a['first_debt_free_year']==7
        assert a['first_cash_at_operating_floor_year']==10
        assert a['last_unpaid_historical_pool']==0
        assert a['omitted_cash_dividend_tail_upper_bound_per_share']<1e-10
