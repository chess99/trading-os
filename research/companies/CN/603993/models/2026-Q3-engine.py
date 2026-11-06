#!/usr/bin/env python3
"""CMOC finite-life owner distributions. Units CNY billion; tonnes/oz; stdlib only."""
import json, math, sys
from pathlib import Path
from copy import deepcopy
SHARES=21.394310176
RATES=(.115,.10)
FX=6.9
N=32
# Initial allocations are research estimates, NOT undisclosed segment balance-sheet facts.
# Cash sums to 42.186334732; marketable investments 5.948578055 recovered Y1;
# restricted cash 2.871809985 recovered with closures. All operational working capital stays operational.
INIT={
 'TFM':dict(cash=14.,debt=.8,legal=30.,reserve=0.,own=.8,floor=3.,limit=4.),
 'KFM':dict(cash=7.,debt=.4,legal=10.,reserve=0.,own=.7125,floor=2.,limit=4.),
 'BR':dict(cash=1.5,debt=.5,legal=4.,reserve=0.,own=1.,floor=.7,limit=2.),
 'BG':dict(cash=1.5,debt=.5,legal=2.,reserve=0.,own=1.,floor=.7,limit=2.),
 'IXM':dict(cash=8.,debt=34.,legal=5.,reserve=0.,own=1.,floor=5.,limit=42.),
 'ODIN':dict(cash=0.,debt=0.,legal=0.,reserve=0.,own=1.,floor=.5,limit=0.)}
TF=[560000]*8+[500000,450000,400000,350000,300000,250000,200000]+[0]*15
KF=[260000,310000]+[340000]*6+[250000,200000,150000,120000,100000,80000,60000]+[0]*15
LIFE={'TFM':15,'KFM':15,'BR':20,'BG':15,'IXM':30,'ODIN':29}
# residual operating net working capital, after paying operating payables; no gross inventory add-back.
WC={'TFM':4.,'KFM':2.,'BR':1.,'BG':.6,'IXM':36.533455,'ODIN':.5}
# IXM: cash8+operating WC36.533455-debt34 = 10.533455 initial book equity.
def price(t,scenario):
 c=10500.;co=35000.;gold=3200.;tax=.35;cost=4600.;delay=0
 if scenario=='cycle' and t<=3: c=8500.;co=28000.;gold=2900.;cost=4900.
 if scenario=='structural': c=9500.;co=32000.;tax=.50;cost=5500.;delay=2
 if scenario=='upside': c=11500.;co=40000.;gold=3700.
 if scenario=='copper_minus_10': c*=.9
 if scenario=='copper_plus_10': c*=1.1
 if scenario=='tax_30': tax=.30
 if scenario=='tax_50': tax=.50
 if scenario=='cost_plus_15': cost*=1.15
 if scenario=='odin_delay': delay=2
 return c,co,gold,tax,cost,delay

def operation(name,t,scenario,inv):
 c,co,g,tax,cost,delay=price(t,scenario); infl=1.02**(t-1)
 end=LIFE[name]+(delay if name=='ODIN' else 0)
 if t>end:return dict(ni=0.,fcf=0.,capex=0.,ebitda=0.,cu=0.,co_sales=0.,co_prod=0.,inventory=inv),inv
 cu=0;cs=cp=0;cap=0;dep=0;rev=0;oper=0;rate=.25
 if name in ('TFM','KFM'):
  cu=(TF if name=='TFM' else KF)[t-1]
  if scenario=='structural':cu*=.9
  share=.55 if name=='TFM' else .45
  sales=([30000,40000,60000]+[70000]*7+[60000,50000,40000,30000,20000])[min(t-1,14)]
  prod=([80000,70000,60000]+[45000]*7+[35000,25000,15000,10000,0])[min(t-1,14)]
  if scenario=='structural': sales=30000 if t<=10 else 20000;prod=25000 if t<=10 else 10000
  cs=min(sales*share,inv+prod*share);cp=prod*share
  # product receipts after ad-valorem royalties and stream haircut. Separate cobalt costs, no byproduct credit.
  rev=(cu*c*(1-.035)+cs*co*(1-.10))*FX/1e9*infl
  oper=(cu*cost+cs*10000)*FX/1e9*infl+.35*infl
  dep=cu*700*FX/1e9*infl
  cap=(cu*650*FX/1e9+(2. if name=='TFM' and 7<=t<=10 else 0)+(1. if name=='KFM' and 7<=t<=10 else 0))*infl
  if name=='KFM' and t==1:cap+=2.5
  if name=='TFM' and t<=3:cap+=1.0 # power / acid / throughput, not prior acquisition
  rate=tax
  # net cash cost of additional cobalt stock; draws release exactly historical cost.
  dstock=(cp-cs)*10000*FX/1e9*infl
  # Economic delivery budget: H1 liability6.564 allocated over mine years; not verified exact contract delivery schedule.
  stream=(6.563914669/15)*infl
  oper+=stream*(.55 if name=='TFM' else .45)
  # final settlement payments for historic reserve royalty; no second opening debt deduction.
  settlement=(.7 if t<=2 and name=='TFM' else 0)+(10.540270406/5 if t<=5 and name=='KFM' else 0)
  inv+=cp-cs
 elif name=='BR':
  rev=7.2*infl;oper=5.3*infl;dep=.5*infl;cap=.65*infl;rate=.34;dstock=0;settlement=0
 elif name=='BG':
  oz=225000*(1 if t<=7 else max(.35,1-.07*(t-7)))
  rev=oz*g*FX/1e9*infl;oper=oz*1900*FX/1e9*infl;dep=.35*infl;cap=.55*infl;rate=.20;dstock=0;settlement=0
 elif name=='IXM':
  # normal after-tax earnings1.3bn, debt interest already below; gross margin net of hedges.
  rev=240.*infl;oper=(240.-(1.3/.853+34*.045)) *infl;dep=.06*infl;cap=.06*infl;rate=.147
  dstock=WC[name]*.02*infl
  if scenario=='cycle' and t<=2:dstock+=2.5;oper+=.8*infl
  if scenario=='structural':oper+=.7*infl
  if scenario=='ixm_wc_shock' and t==1:dstock+=8
  if scenario=='ixm_wc_shock' and t==6:dstock-=8
  settlement=0
 else:
  age=t-delay
  oz=0 if age<=3 else (180000 if age==4 else (280000 if age==5 else 371000))
  cu=0 if age<=3 else (10000 if age==4 else 18597)
  # Fixed18% is conservative versus contractual22% after advance credit exhaustion.
  delivery=.22 if scenario=='stream_payment_22' else .18
  rev=(oz*g*(1-.044*(1-delivery))+cu*c)*FX/1e9*infl
  oper=(oz*1300*FX/1e9+.15)*infl
  dep=.45*infl if oz else 0
  cap=({1:2.5,2:3.0,3:2.5,6:2.,9:2.}.get(age,.5 if oz else .1))*infl
  rate=.30;dstock=.5 if age==4 else 0;settlement=0
 ebitda=rev-oper;ni=(ebitda-dep)*(1-rate) if ebitda>=dep else ebitda-dep
 if name=='KFM' and t<=5:ni-=.05*10.540270406*(1-(t-1)/5)
 fcf=ni+dep-cap-dstock-settlement
 if name=='ODIN' and t==1 and scenario!='no_future_stream_financing':fcf+=1.0 # only remaining stream funding budget, not full original consideration
 return dict(ni=ni,fcf=fcf,capex=cap,ebitda=ebitda,cu=cu,co_sales=cs,co_prod=cp,inventory=inv),inv

def liquidity(cash,debt,need,floor,limit):
 """Real financing chain: cash deficit cannot be cured by negative dividends."""
 cash-=need
 draw=max(0.,floor-cash)
 if debt+draw>limit+1e-8:raise ValueError('finite financing exhausted even before dividends')
 return cash+draw,debt+draw,draw

def cashpool(total,mother,balance,limit=10.):
 """Internal lender cash=total-mother; matched receivable/payable=balance.
 Repay from mother surplus first; transfer only existing lender cash. No income."""
 repayment=min(balance,max(0.,mother-1.))
 mother-=repayment;balance-=repayment
 loan=min(max(0.,1.-mother),max(0.,total-mother),max(0.,limit-balance))
 mother+=loan;balance+=loan
 if mother < -1e-8 or mother>total+1e-8:raise ValueError('mother liquidity fails')
 return mother,balance,loan,repayment

# The six units are ECONOMIC FORECAST SEGMENTS, not invented legal persons.
# No foreign registered-capital or statutory-reserve ledger is simulated.
PARENT_REGISTERED=4.2788620352
PARENT_STATUTORY=2.1599240583
# Returnable premium BUDGET bounded by parent total capital reserve26.69447508784;
# group disclosed share premium26.45911077155 is a corroborating bound, not a parent detail claim.
PARENT_CAPITAL_PREMIUM=26.45911077155
HK_COST=40.25373746363

def china_profit(retained, statutory, income, registered, paid_in=None):
    eligible=max(0.,retained+income)-max(0.,retained)
    appropriation=min(max(0.,registered*.5-statutory), max(0.,eligible)*.1)
    return retained+income-appropriation,statutory+appropriation,appropriation

def disposal(cash, noncash, external_debt, closure_cost, ownership, haircut=.15, tax_basis=None, tax=.25):
    realization=noncash*(1-haircut)
    gain=realization-(noncash if tax_basis is None else tax_basis)-closure_cost
    tax_paid=max(0.,gain)*tax # no immediate tax refund for losses
    equity=cash+realization-external_debt-closure_cost-tax_paid
    if equity< -1e-9: raise ValueError('exit cannot repay all external debt')
    return dict(total=equity,owner=equity*ownership,minority=equity*(1-ownership),
                gain=gain,tax=tax_paid,external=realization-external_debt-closure_cost-tax_paid)

def recover_basis(proceeds,basis,final=False):
    returned=min(proceeds,basis);remaining=basis-returned
    gain=max(0.,proceeds-basis)-(remaining if final else 0.)
    return (0. if final else remaining),returned,gain

def capital_reduce(payment,registered,premium,shares):
    base=registered+premium
    if payment>base+1e-9:raise ValueError('capital return exceeds actual paid capital and premium')
    ratio=1-payment/base if base else 1.
    return registered*ratio,premium*ratio,shares*ratio

def receipt(cash, income, amount, kind):
    return cash+amount,income+(amount if kind=='dividend' else 0.)

def run(scenario='base',zero_dividend=False,force_need=0.,horizon=32,budget_version='revised'):
    s=deepcopy(INIT)
    for z in s.values():
        z.pop('legal');z.pop('reserve');z['economic_earnings_budget']=0.
    inv={'TFM':107718.6,'KFM':88133.4};closed=set();rows=[];pending=[]
    cash=10.186334732;debt=22.159167733;legal=1.36615118;mothercash=4.186334732
    statutory=PARENT_STATUTORY;registered=PARENT_REGISTERED;premium=PARENT_CAPITAL_PREMIUM;shares=SHARES
    basis=HK_COST;recv=1.802341533;pool=0.;parent_limit=36.;finalized=False
    friction=.10 if scenario=='friction_10' else .05
    delay=2 if scenario=='upstream_delay_2' else 0
    exit_delay=(3 if scenario=='exit_delay_3' else 1) if budget_version=='revised' else 0
    haircut=(.35 if scenario=='exit_haircut_35' else .15) if budget_version=='revised' else 0.
    if scenario=='cash_shift':s['TFM']['cash']-=6;s['IXM']['cash']+=6
    for t in range(1,horizon+1):
        before=cash+sum(z['cash'] for z in s.values())+sum(x['amount'] for x in pending)
        profit=0.;external=0.;minor=0.;taxes=0.;capex=0.;finance=0.;subs={};inflow=0.;newincome=0.;capreceived=0.;injtotal=0.;gain=0.
        assetrelease=(5.948578055-.228973 if t==1 else (7.951387165+.228973 if t==10 else 0.))
        if budget_version=='legacy' and t==horizon:assetrelease+=2.871809985
        if budget_version=='revised' and t in (16,31):assetrelease+=2.0 if t==16 else .871809985
        for name,z in s.items():
            if name in closed:continue
            o,iv=operation(name,t,scenario,inv.get(name,0.));inv[name]=iv
            if budget_version=='revised' and name=='ODIN' and t==1 and scenario not in ('no_future_stream_financing','stream_funding_1'):o['fcf']-=1.
            ni=o['ni']-z['debt']*.045+z['cash']*.015
            fcf=o['fcf']-z['debt']*.045+z['cash']*.015
            profit+=ni*z['own'];external+=fcf;capex+=o['capex'];z['economic_earnings_budget']+=ni
            repay=min(z['debt'],.25) if name!='IXM' else 0.
            if name=='IXM' and scenario=='ixm_wc_shock' and t>=6:repay=max(z['debt']-34,0)
            z['cash']+=fcf-repay;z['debt']-=repay;external-=repay
            if name=='ODIN' and z['cash']<z['floor']:
                inj=z['floor']-z['cash'];cash-=inj;mothercash-=max(0.,inj-(cash+inj-mothercash));z['cash']+=inj;injtotal+=inj;basis+=inj
            z['cash'],z['debt'],draw=liquidity(z['cash'],z['debt'],0,z['floor'],z['limit']);finance+=draw;external+=draw
            old=recv if name=='TFM' and t==1 else 0.
            if old:z['cash']-=old;inflow,newincome=receipt(inflow,newincome,old,'old_receivable');recv=0.
            end=LIFE[name]+(price(t,scenario)[5] if name=='ODIN' else 0)
            cap=0.;decl=0.;ex={}
            if t==end:
                wc=WC[name]*(1.02**(t if budget_version=='revised' else t-1) if name=='IXM' else 1.)
                if name in ('TFM','KFM'):wc+=inv[name]*10000*FX/1e9*.75
                restoration={'TFM':1.,'KFM':.6,'BR':.4,'BG':.3,'ODIN':.6,'IXM':0}[name]*(1.02**(t-1) if budget_version=='revised' else 1.)
                ex=disposal(z['cash'],wc,z['debt'],restoration,z['own'],haircut)
                external+=ex['external'];minor+=ex['minority'];cap=ex['owner'];z['cash']=0.;z['debt']=0.;closed.add(name)
                # Exit cash is held in a settlement account. Cash itself is NOT haircut.
                fee=cap*(friction if budget_version=='revised' else 0.);taxes+=fee;pending.append(dict(due=t+exit_delay,amount=cap-fee,kind='capital'))
            else:
                budget=(.35 if t<=5 else .85)*max(ni,0)+(.05 if t<=5 else .5)*max(z['cash']-z['floor'],0)
                if scenario=='upstream_half':budget*=.5
                if scenario=='remit_delay' and t<=2:budget=0.
                decl=min(max(0.,z['economic_earnings_budget']),max(0.,z['cash']-z['floor']),budget)
                z['cash']-=decl;z['economic_earnings_budget']-=decl
                owner=decl*z['own'];minor+=decl*(1-z['own'])
                fee=(friction if name!='IXM' or budget_version=='revised' else 0.)*owner;taxes+=fee;pending.append(dict(due=t+delay,amount=owner-fee,kind='dividend'))
            subs[name]={**o,'net_profit':ni,'declaration_budget':decl,'economic_earnings_budget':z['economic_earnings_budget'],'cash':z['cash'],'debt':z['debt'],'draw':draw,'capital_gross_owner':cap,'exit':ex,'old_receivable_paid':old}
        due=[x for x in pending if x['due']<=t];pending=[x for x in pending if x['due']>t]
        for x in due:
            inflow,newincome=receipt(inflow,newincome,x['amount'],x['kind'])
            if x['kind']!='dividend':
                capreceived+=x['amount'];basis,returned,g=recover_basis(x['amount'],basis);gain+=g
        if len(closed)==len(s) and not pending and not finalized:
            basis,_,g=recover_basis(0.,basis,True);gain+=g;finalized=True
        domestic=(3.2 if t<=8 else max(0.,3.2-.64*(t-8)))*1.02**(t-1) if t<=13 else 0.
        if scenario=='cycle' and t<=3:domestic*=.65
        if scenario=='structural':domestic*=.75
        domcap=.45*1.02**(t-1) if t<=13 else 0.;domdep=.3*1.02**(t-1) if t<=13 else 0.
        domestic+=(.45 if t<=10 else 0.)-(.6 if t<=15 else .2)*1.02**(t-1)
        pi=debt*.045;ci=cash*.015;profit+=domestic-pi+ci
        gain_tax=max(0.,gain)*.25;taxes+=gain_tax
        parentprofit=domestic+newincome-pi+ci+gain-gain_tax
        legal,statutory,appropriation=china_profit(legal,statutory,parentprofit,registered)
        pf=domestic+domdep-domcap-pi+ci
        cash+=pf+inflow+assetrelease-gain_tax
        mothercash+=pf+inflow+assetrelease-gain_tax # financial principal routed under capital reduction budget, not profit
        repayment=min(debt,8.28 if t==1 else (5. if t<=4 else 1.))
        mothercash-=max(0.,repayment-(cash-mothercash));cash-=repayment;debt-=repayment
        need=force_need if t==1 else 0.
        cash,debt,draw=liquidity(cash,debt,need,3. if t<horizon else 0.,parent_limit);finance+=draw
        mothercash,pool,pl,pr=cashpool(cash,mothercash,pool)
        target=.30*max(profit,0) if t<=(10 if scenario=='payout_delay' else 5) else max(.75*max(profit,0),.90*max(cash-15.,0))
        dividend=min(target,max(legal,0),max(mothercash-1.,0),max(cash-3.,0))
        if zero_dividend:dividend=0.
        capital=0.;finaldebt=0.;exitfee=0.
        legal-=dividend
        # Legal capital return is proportional cancellation, not fabricated new profit.
        if t>=15 and t<horizon and not zero_dividend:
            capital=min(max(0.,target-dividend),max(0.,cash-15.-dividend),max(0.,mothercash-1.-dividend),max(0.,registered+premium-.5))
            registered,premium,shares=capital_reduce(capital,registered,premium,shares)
        if t==horizon:
            if pending or len(closed)!=len(s):raise ValueError('horizon truncates unsettled owner cash')
            exitfee=(.2*1.02**(t-1) if budget_version=='revised' else 0.);finaldebt=debt
            capital=cash-debt-exitfee-dividend
            if capital< -1e-8:raise ValueError('parent liquidation fails')
            debt=0.;registered=0.;premium=0.;shares=0.
        total=dividend+capital
        cash-=total+finaldebt+exitfee;mothercash-=min(mothercash,total)
        if t==horizon:mothercash=0.;pool=0.
        after=cash+sum(z['cash'] for z in s.values())+sum(x['amount'] for x in pending)
        expected=before+external+pf+assetrelease+draw-repayment-finaldebt-minor-taxes-total-need-exitfee
        assert abs(after-expected)<2e-7,(scenario,t,after,expected)
        assert -1e-7<=mothercash<=cash+1e-7 and cash>=-1e-7 and debt<=parent_limit+1e-7
        rows.append(dict(year=t,subs=subs,common_profit=profit,domestic_profit=domestic,parent_new_dividend_income=newincome,parent_old_receivable_collection=1.802341533 if t==1 else 0.,parent_legal_profit=parentprofit,parent_legal_retained=legal,parent_statutory=statutory,appropriation=appropriation,parent_cash=cash,mother_cash=mothercash,parent_debt=debt,draw=finance,capital_contribution=injtotal,minority_distribution=minor,withholding=taxes,capex=capex+domcap,settlement_cash=sum(x['amount'] for x in pending),hk_investment_basis=basis,hk_capital_received=capreceived,hk_disposal_gain=gain,registered=registered,shares_outstanding=shares,holder_share_fraction=shares/SHARES,ordinary_dividend=dividend,capital_return=capital,distribution=total,distribution_per_share=total/SHARES,cash_conservation_error=after-expected))
    return rows

def valuation(rows,r):
 d=[x['distribution_per_share'] for x in rows]
 pv=sum(v/(1+r)**(i+1) for i,v in enumerate(d))
 tv=sum(d[i]/(1+r)**(i-4) for i in range(5,len(d)))
 assert abs(pv-sum(d[i]/(1+r)**(i+1) for i in range(5))-tv/(1+r)**5)<1e-9
 return dict(pv=pv,tv5=tv,tv_pv_share=tv/(1+r)**5/pv)

def residual_income(roe):
 b=94.747813362;value=b;r=.105
 # separate normal sustainable return model: existing book capital earns18-22%, spread halves over Y6-10, vanishes Y15.
 for t in range(1,16):
  spread=(roe-r)*(1 if t<=5 else max(0,(15-t)/10))
  income=b*(r+spread);value+=b*spread/(1+r)**t
  retention=.35 if t<=5 else -.04 # mature resource capital shrinks after Y5, not perpetual excess returns
  b+=income*retention
 return value/SHARES

SCENARIOS=['base','cycle','structural','upside','copper_minus_10','copper_plus_10','tax_30','tax_50','cost_plus_15','ixm_wc_shock','remit_delay','legal_zero','cash_shift','payout_delay','odin_delay','reserve_double','no_future_stream_financing','stream_payment_22','friction_10','upstream_delay_2','exit_delay_3','exit_haircut_35','upstream_half','stream_funding_1']

def actual_tests():
    assert china_profit(0,5,10,20,10)==(9,6,1)
    assert china_profit(-12,0,10,20,10)==(-2,0,0)
    assert china_profit(-2,0,10,20,10)==(7.2,.8,.8)
    assert china_profit(0,10,10,20,10)==(10,10,0)
    assert china_profit(0,10,10,24,12)==(9,11,1)
    assert receipt(2,3,5,'old_receivable')==(7,3)
    assert receipt(2,3,5,'capital')==(7,3)
    assert receipt(2,3,5,'dividend')==(7,8)
    assert recover_basis(8,10)==(2,8,0)
    assert recover_basis(8,10,True)==(0,8,-2)
    assert recover_basis(12,10,True)==(0,10,2)
    x=disposal(10,20,12,3,.8,.25);assert abs(x['owner']-8)<1e-9 and x['tax']==0
    x=disposal(10,20,12,3,.5,.25);assert x['owner']==5
    assert capital_reduce(5,4,16,20)==(3,12,15)
    assert operation('ODIN',1,'base',0)[0]['ni']==-.15
    try:disposal(1,10,15,1,1,.1)
    except ValueError:pass
    else:raise AssertionError('unpaid debt hidden by haircut')
    try:run('base',True,500)
    except ValueError:pass
    else:raise AssertionError('infinite financing')
    rr=[{'distribution_per_share':v} for v in [10,0,0,0,0,20]]
    assert abs(valuation(rr,.1)['pv']-10/1.1-20/1.771561)<1e-9
    br=run();assert br[0]['parent_old_receivable_collection']==1.802341533
    assert br[-1]['parent_cash']<1e-8 and br[-1]['settlement_cash']==0
    return {'registered_not_paid':True,'loss_first':True,'reserve_cap_and_conversion':True,'real_basis_gain_loss':True,'noncash_only_haircut_full_debt':True,'proportional_cancel':True,'no_negative_tax_refund':True,'no_infinite_finance':True,'terminal_cash_zero':True}
