"""思源：字面独立现金链与真实生产函数边界；不读取模型输入作为复算假设。"""
import copy, importlib.util, json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/002028/models'
@pytest.fixture(scope='module')
def production():
 spec=importlib.util.spec_from_file_location('sieyuan_unified',ROOT/'2026-Q3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 p=json.loads((ROOT/'2026-Q3-output.json').read_text());return m,m.expand_output(p)

def calculate(rate=.095,case='base',slow=False,delay=0,tax_extra=0.,net_recovery=.8,legal0=8.27410905342,statutory0=.38882131,permanent=False,mother_yield=.015,source_yield=.015):
    growth=[.17,.15,.12,.10,.08,.07,.06,.05,.04,.03]+[.03]*5
    margins=[.132,.134,.135,.135,.135,.134,.133,.132,.131,.13]+[.13]*5
    caprate=.45;roic=.18;g=.03;opt=True;shares=.795034532
    wc=[0.]*15;settle=[0.]*15;up=[.4]*5+[.5,.6,.7,.8,.9]+[1.]*5;arrival=[.8]*5+[.85,.9,.95,1.,1.]+[1.]*5
    payout=[.2]*5+[.25,.3,.4,.5,.6,.7,.8,1.,1.,1.]
    if case=='structural':
        growth=[.08,.06,.04,.03,.03,.03,.03,.03,.03,.03]+[.02]*5;margins=[.11,.10,.095]+[.09]*12
        caprate=.65;roic=.11;g=.02;wc=[2.5]+[0.]*14;settle=[1.5]+[0.]*14;up=[.25]*5+up[5:];arrival=[.5]*5+arrival[5:];opt=False;shares=.786762975
    if case=='cycle':
        growth=[.03,.07,.18,.14,.10,.07,.06,.05,.04,.03]+[.03]*5;margins=[.11,.12,.13,.135,.135,.134,.133,.132,.131,.13]+[.13]*5
        wc=[1.8,0.,-.9,-.9]+[0.]*11;settle=[.8]+[0.]*14;arrival=[.5,.5]+arrival[2:]
    if slow:up=[.4]*5+[.5]*10
    start=11+delay;end=15+delay
    if permanent:payout=[.2]*15;up=[.4]*15;arrival=[.8]*15;start=1000;end=1001
    liquid=3.76409683288+4.25769347219-.33799333991-2.5-.95979383065-.15
    m=2.4;s=liquid-m;ml=legal0;sl=0.;ar=0.;reserve=statutory0;debt=0.;loan=0.;rev=26.5;previousprofit=3.5;previouscore=rev*margins[0]
    deposit=.30507739726;acc=0.;earmark=.4;project=0.;out=[]
    for year in range(1,401):
        index=year-1;oldrev=rev;rev*=1+(growth[index] if year<=15 else g);margin=margins[index] if year<=15 else margins[-1]
        pretaxbudgetcore=rev*margin;core=rev*(margin-tax_extra)
        n=(.788772032 if year==1 else .795034532) if opt else shares
        cashsub=(.002009057*43.8 if year==1 else .0062625*(43.8-out[0]['dps']) if year==2 else 0.) if opt else 0.
        mi=m*mother_yield;si=s*source_yield-debt*.05;di=.3*.0175*.75 if deposit else 0.;acc+=di;profit=core+mi+si+di
        investment=(max(0.,rev-oldrev)*caprate if year<=10 else max(0.,pretaxbudgetcore-previouscore)/roic)+(wc[index] if year<=15 else 0.)
        direct=.2*(1+g)**max(0,year-15);cf=profit-investment
        mf=direct+mi-.1*investment;sf=core-direct+si-.9*investment
        payment=settle[index] if year<=15 else 0.;mc=m+mf+cashsub-payment;sc=s+sf+payment
        if year==1:mc-=.4;sc+=.4;project+=.4;earmark=0.
        spend=min(project,max(0.,.9*investment));project-=spend
        depo_cash=0.;mg=sg=0.;realize=0.
        if year==2:depo_cash=deposit+acc;mc+=depo_cash;deposit=0.;acc=0.
        if year==10:
            mb=.10261164646;sb=.12922305852-mb;mc+=mb*net_recovery;sc+=sb*net_recovery;realize=.12922305852*net_recovery;mg=mb*(1-net_recovery);sg=sb*(1-net_recovery)
        earning=core-direct+si-sg;eligible=max(0.,earning-max(0.,-sl));buffer=eligible*(.1 if year<=10 else 0.);sl+=earning-buffer
        old=min(ar,max(0.,sc-project));sc-=old;mc+=old;ar-=old
        shareup=up[index] if year<=15 else up[-1];receipt=arrival[index] if year<=15 else arrival[-1]
        special=start<=year<=end;release=1/max(1,end-year+1) if special else .1 if year>end else 0.
        ordinary=max(0.,sf)*shareup;additional=max(0.,sc-project-ar-ordinary)*release
        declared=min(ordinary+additional,max(0.,sl),max(0.,sc-project-ar));paid=declared*receipt;sc-=paid;mc+=paid;ar+=declared-paid;sl-=declared
        mp=direct+mi+di+declared-mg;eligible=max(0.,mp-max(0.,-ml));addition=min(.1*eligible,max(0.,n*.5-reserve));reserve+=addition;ml+=mp-addition
        transfer=0.
        if sc<project:
            transfer=min(project-sc,max(0.,mc-earmark),max(0.,1-loan));mc-=transfer;sc+=transfer;loan+=transfer
        loanpaid=min(loan,max(0.,sc-project-ar));sc-=loanpaid;mc+=loanpaid;loan-=loanpaid
        borrow=max(0.,project-sc)+max(0.,earmark-mc);assert debt+borrow<=2+1e-9
        motherpart=max(0.,earmark-mc);mc+=motherpart;sc+=borrow-motherpart;debt+=borrow
        repaid=min(debt,max(0.,mc-earmark)+max(0.,sc-project-ar));take=min(repaid,max(0.,mc-earmark));mc-=take;sc-=repaid-take;debt-=repaid
        payratio=payout[index] if year<=15 else payout[-1]
        request=max(0.,previousprofit*payratio) if payratio<1 else max(0.,cf)
        request+=max(0.,mc+sc-earmark-project-request-debt)*release
        distribution=min(request,max(0.,mc-earmark),max(0.,ml),max(0.,mc+sc-earmark-project-debt));m=mc-distribution;s=sc;ml-=distribution
        out.append(dict(year_index=year,profit=profit,economic_realization_book_loss=mg+sg,core_profit=core,reinvest=investment,dividend=distribution,dps=distribution/n,mother_cash=m,subsidiary_cash=s,mother_legal_profit_reserve=ml,source_earnings_budget=sl,source_profit_buffer=buffer,mother_statutory=reserve,mother_statutory_add=addition,option_subscription=cashsub,declared_upstream=declared,upstream_received=old+paid,upstream_receivable=ar,debt=debt,finance=borrow,internal_loan=loan,deposit_cash=depo_cash,illiquid_net_realization=realize))
        previousprofit=profit;previouscore=pretaxbudgetcore
    pv=sum(q['dps']/(1+rate)**q['year_index'] for q in out);tv=sum(q['dps']/(1+rate)**(q['year_index']-5) for q in out[5:])
    return dict(value_per_share=pv,terminal_per_share=tv,rows=out)

@pytest.mark.parametrize('path,kwargs',[
 ('core_low',{'rate':.10}),('core_high',{'rate':.09}),('base',{}),
 ('scenarios/structural_adverse/output',{'case':'structural'}),('scenarios/cyclical_weak/output',{'case':'cycle'}),
 ('scenarios/delayed_release/output',{'delay':5}),('capital_governance/source_50pct_forever',{'slow':True}),
 ('capital_governance/net_tax_plus_1pp',{'tax_extra':.01}),('capital_governance/noncore_net50pct',{'net_recovery':.5}),
 ('capital_governance/mother_legal_zero',{'legal0':0}),('permanent_20pct_payout_diagnostic',{'permanent':True}),
 ('capital_governance/source_net_financial_yield1pct',{'source_yield':.01}),('capital_governance/mother_net_financial_yield1pct',{'mother_yield':.01})])
def test_independent_full_cash(path,kwargs,production):
 _,out=production;expected=calculate(**kwargs);actual=out
 for part in path.split('/'):actual=actual[part]
 for k in ('value_per_share','terminal_per_share'):assert actual[k]==pytest.approx(expected[k],abs=1e-9)
 for a,b in zip(expected['rows'],actual['rows']+actual['tail_rows']):
  for k,v in a.items():assert b[k]==pytest.approx(v,abs=1e-7)

def test_formal_capital_loss_cash_and_failure(production):
 m,out=production;m.production_tests()
 p=copy.deepcopy(m.BASE);p.update(mother_legal0=0.,mother_direct_profit=0.,cash_yield=0.,deposit_net_yield=0.,upstream_rate=[0.]*15,special_release_start=1000,special_release_end=1001)
 assert all(x['dividend']==0 for x in m.operate(p,5))
 p=copy.deepcopy(m.BASE);p['wc_shocks']=[100.]+[0.]*14
 with pytest.raises(ValueError,match='unfunded'):m.operate(p)
 # Maintenance is embedded in after-depreciation net profit; zero growth removes only NET new investment.
 p=copy.deepcopy(m.BASE);p.update(g=0.,growth=[0.]*15,margins=[.13]*15)
 assert all(x['reinvest']==0 for x in m.operate(p,30))
 assert all(x['core_profit']>0 for x in m.operate(p,30))

def test_full_future_principal_and_serialization(production):
 m,out=production
 def walk(x):
  if isinstance(x,dict):
   if 'principal_realization' in x:
    for item in x['principal_realization']['later_cash_cohorts'].values():assert item['unpaid']<1e-7
    for row in x['rows']+x['tail_rows']:assert row['finance']==0 and row['internal_loan']==0
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(out);assert m.expand_output(m.pack_output(out))==out
 assert out['capital_governance']['horizon500']['value_per_share']==pytest.approx(out['base']['value_per_share'],abs=3e-9)
