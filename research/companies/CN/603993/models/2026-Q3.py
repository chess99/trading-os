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

LEGACY_SOURCE_GZIP_BASE64='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'

def main():
    out={'units':'CNY billion; billion shares; original-share holder cash','tests':actual_tests(),'scenarios':{},'method_only_same_economics':{},'auxiliary_residual_income':[residual_income(.18),residual_income(.22)]}
    for scenario in SCENARIOS:
        for key,budget in [('scenarios','revised'),('method_only_same_economics','legacy')]:
            try:
                rows=run(scenario,budget_version=budget,horizon=34 if scenario=='exit_delay_3' else 32)
                out[key][scenario]={'feasible':True,'valuation':[valuation(rows,r) for r in RATES],'annual':rows}
            except ValueError as e:out[key][scenario]={'feasible':False,'reason':str(e)}
    import base64,gzip
    legacy={'__name__':'legacy_snapshot'}
    exec(gzip.decompress(base64.b64decode(LEGACY_SOURCE_GZIP_BASE64)),legacy)
    out['old_same_economic_budget']={}
    out['old_new_comparison']={}
    for scenario in SCENARIOS[:18]:
        try:
            oldrows=legacy['run'](scenario)
            oldval=[legacy['valuation'](oldrows,r) for r in RATES]
            out['old_same_economic_budget'][scenario]={'annual':oldrows,'valuation':oldval}
            new=out['method_only_same_economics'][scenario];core=out['scenarios'][scenario]
            out['old_new_comparison'][scenario]={'old':oldval,'method_only':new.get('valuation'),'revised_budget':core.get('valuation'),'d_old':[a['distribution_per_share'] for a in oldrows[:5]],'d_new':[a['distribution_per_share'] for a in new.get('annual',[])[:5]],'d_core':[a['distribution_per_share'] for a in core.get('annual',[])[:5]]}
        except ValueError as e:out['old_same_economic_budget'][scenario]={'feasible':False,'reason':str(e)}
    text=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'
    Path(__file__).with_name('2026-Q3-output.json').write_text(text)
    print(json.dumps({k:{n:q.get('valuation',q.get('reason')) for n,q in out[k].items()} for k in ['scenarios','method_only_same_economics']},indent=2))
if __name__=='__main__':main()
