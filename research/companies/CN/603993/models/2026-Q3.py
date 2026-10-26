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
  # finite contractual stream reserve: 2026 H1 liability6.564 allocated over mining years as receipt haircut
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

RESERVE_CAP={'TFM':3.,'KFM':1.,'BR':.4,'BG':.2,'IXM':.5,'ODIN':.8}
def retained_profit(legal,reserve,ni,cap):
 """Bounded governance earmark, not a claim about local statutory reserve law.
 Only earnings left AFTER restoring accumulated losses can be earmarked."""
 eligible=max(0.,legal+ni)-max(0.,legal)
 addition=min(max(0.,cap-reserve),.05*max(0.,eligible))
 return legal+ni-addition,reserve+addition,addition

def cashpool(total,mother,balance,limit=10.):
 """Internal lender cash=total-mother; matched receivable/payable=balance.
 Repay from mother surplus first; transfer only existing lender cash. No income."""
 repayment=min(balance,max(0.,mother-1.))
 mother-=repayment;balance-=repayment
 loan=min(max(0.,1.-mother),max(0.,total-mother),max(0.,limit-balance))
 mother+=loan;balance+=loan
 if mother < -1e-8 or mother>total+1e-8:raise ValueError('mother liquidity fails')
 return mother,balance,loan,repayment

def run(scenario='base',zero_dividend=False,force_need=0.):
 s=deepcopy(INIT); inv={'TFM':107718.6,'KFM':88133.4};closed=set();rows=[]
 cash=10.186334732;debt=22.159167733;legal=1.36615118;mothercash=4.186334732;recv=1.802341533
 # parent cash includes6 offshore treasury, not immediately available mother cash.
 parent_limit=36.;paid=0;old_paid=False;pool_balance=0.
 if scenario=='legal_zero':
  for z in s.values():z['legal']=0.
 if scenario=='cash_shift':s['TFM']['cash']-=6.;s['IXM']['cash']+=6.
 for t in range(1,N+1):
  before=sum(z['cash'] for z in s.values())+cash;profit=0.;inflow=0.;newlegal=0.;minor=0.;withtax=0.;capex=0.;finance=0.;subs={};external=0.;sub_injection=0.;closure_external=0.
  # financial investments sell once. No interest on these investments also capitalized.
  assetrelease=5.948578055 if t==1 else (7.951387165+.228973 if t==10 else 0.)
  if t==1:assetrelease-=.228973
  if t==N:assetrelease+=2.871809985
  for name,z in s.items():
   if name in closed:continue
   o,newinv=operation(name,t,scenario,inv.get(name,0.));inv[name]=newinv
   interest=z['debt']*.045;ni=o['ni']-interest;fcf=o['fcf']-interest
   interest_income=z['cash']*.015;ni+=interest_income;fcf+=interest_income
   profit+=ni*z['own'];capex+=o['capex'];external+=fcf
   z['legal'],z['reserve'],reserve=retained_profit(z['legal'],z['reserve'],ni,RESERVE_CAP[name]*(2 if scenario=='reserve_double' else 1))
   # Mature borrowers amortize bank debt, trade debt scales with nominal WC and remains matched.
   repay=min(z['debt'],.25) if name!='IXM' else 0.
   if name=='IXM' and scenario=='ixm_wc_shock' and t>=6:repay=max(z['debt']-34.,0.)
   z['cash']+=fcf-repay;z['debt']-=repay;external-=repay
   if name=='ODIN' and z['cash']<z['floor']:
    inj=z['floor']-z['cash'];mothercash-=max(0.,inj-(cash-mothercash));cash-=inj;z['cash']+=inj;sub_injection+=inj
   z['cash'],z['debt'],draw=liquidity(z['cash'],z['debt'],0,z['floor'],z['limit']);finance+=draw;external+=draw
   # Collection of pre-existing dividend receivable: debit subsidiary payable / parent receivable only.
   old=recv if name=='TFM' and t==1 else 0.
   if old:
    z['cash']-=old;inflow+=old;recv=0.;old_paid=True
   end=LIFE[name]+(price(t,scenario)[5] if name=='ODIN' else 0)
   if t==end or t==N:
    recovery=WC[name]*(1.02**(t-1) if name=='IXM' else 1.)
    if name in ('TFM','KFM'):recovery+=inv[name]*10000*FX/1e9*.75 # remaining inventory realization net recovery, no revenue duplication
    restoration={'TFM':1.,'KFM':.6,'BR':.4,'BG':.3,'ODIN':.6,'IXM':0}[name]
    closure_external+=recovery-z['debt']-restoration
    pot=z['cash']+recovery-z['debt']-restoration
    if pot<0:raise ValueError('negative closure equity')
    declaration=0.;capital=pot;z['cash']=0;z['debt']=0;closed.add(name)
    # closure financing and working-capital release are counted separately
   else:
    declaration=min(max(0,z['legal']),max(0,z['cash']-z['floor']),(.35 if t<=5 else .85)*max(ni,0)+(.05 if t<=5 else .5)*max(z['cash']-z['floor'],0))
    if scenario=='remit_delay' and t<=2:declaration=0.
    z['cash']-=declaration;z['legal']-=declaration;capital=0.
   owner_decl=declaration*z['own'];tax=.05*owner_decl if name in ('TFM','KFM','BR','BG','ODIN') else 0.
   received=owner_decl-tax+capital*z['own'];inflow+=received;newlegal+=owner_decl-tax
   minor+=(declaration+capital)*(1-z['own']);withtax+=tax
   subs[name]={**o,'net_profit':ni,'declaration':declaration,'old_receivable_paid':old,'capital_return':capital,'owner_receipt':received+old,'minority_distribution':(declaration+capital)*(1-z['own']),'cash':z['cash'],'debt':z['debt'],'legal_retained':z['legal'],'reserve':z['reserve'],'reserve_addition':reserve,'draw':draw}
  # Domestic normalized mining earnings, resource replacement included and ends Y13.
  domestic=(3.2 if t<=8 else max(0.,3.2-.64*(t-8))) *1.02**(t-1) if t<=13 else 0.
  if scenario=='cycle' and t<=3:domestic*=.65
  if scenario=='structural':domestic*=.75
  domcap=(.45*1.02**(t-1) if t<=13 else 0);domdep=(.3*1.02**(t-1) if t<=13 else 0)
  pi=debt*.045;ci=cash*.015
  investment_income=.45 if t<=10 else 0.
  domestic+=investment_income
  domestic-=(.6 if t<=15 else .2)*1.02**(t-1) # holding-company overhead beyond mine costs
  parentprofit=domestic+newlegal-pi+ci
  profit+=domestic-pi+ci
  legal+=parentprofit
  pf=domestic+domdep-domcap-pi+ci
  cash+=pf+inflow+assetrelease
  # collected old dividends do not enter legal profit; reserves have already exceeded 50% registered capital.
  mothercash+=pf+inflow # offshore asset proceeds require remittance/capital steps, not operating legal profit
  planned_repay=min(debt,8.28 if t==1 else (5. if t<=4 else 1.))
  mothercash-=max(0.,planned_repay-(cash-mothercash));cash-=planned_repay
  debt-=planned_repay
  cash,debt,draw=liquidity(cash,debt,force_need if t==1 else 0.,3. if t<N else 0.,parent_limit)
  finance+=draw
  parentdraw=draw
  mothercash,pool_balance,pool_draw,pool_repayment=cashpool(cash,mothercash,pool_balance)
  target=.30*max(profit,0) if t<=(10 if scenario=='payout_delay' else 5) else max(.75*max(profit,0),.90*max(cash-15.,0))
  dividend=min(target,max(legal,0),max(mothercash-1.,0),max(cash-3.,0))
  if zero_dividend:dividend=0.
  finaldebt=0.
  if t==N:
   finaldebt=debt
   dividend=max(0,cash-debt);debt=0.;legal=0. # orderly return of paid-in capital plus retained wealth
  else:legal-=dividend
  cash-=dividend+finaldebt;mothercash-=min(mothercash,dividend);paid+=dividend
  if t==N:mothercash=0.;pool_balance=0.
  after=cash+sum(z['cash'] for z in s.values())
  expected=before+external+closure_external+pf+assetrelease+parentdraw-planned_repay-finaldebt-minor-withtax-dividend-(force_need if t==1 else 0.)
  assert abs(after-expected)<1e-7, (t,after,expected)
  assert cash>=-1e-7 and debt<=parent_limit+1e-7
  assert all(z['cash']>=-1e-7 and z['debt']<=z['limit']+1e-7 for z in s.values())
  rows.append(dict(year=t,subs=subs,common_profit=profit,domestic_profit=domestic,domestic_capex=domcap,parent_new_dividend_income=newlegal,parent_old_receivable_collection=1.802341533 if t==1 else 0.,parent_legal_profit=parentprofit,parent_legal_retained=legal,parent_cash=cash,mother_cash=mothercash,treasury_cash=cash-mothercash,cashpool_receivable=pool_balance,cashpool_payable=pool_balance,cashpool_draw=pool_draw,cashpool_repayment=pool_repayment,parent_debt=debt,draw=finance,capital_contribution=sub_injection,minority_distribution=minor,withholding=withtax,capex=capex+domcap,cash_conservation_error=after-expected,distribution=dividend,distribution_per_share=dividend/SHARES))
 assert old_paid and recv==0
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

def tests():
 assert liquidity(10,0,3,2,5)==(7,0,0)
 assert liquidity(1,0,3,2,5)==(2,4,4)
 try:liquidity(1,0,9,2,5)
 except ValueError:pass
 else:raise AssertionError('financing fail test did not fail')
 assert retained_profit(-2.,0.,1.,.8)==(-1.,0.,0.)
 assert retained_profit(-1.,0.,2.,.8)==(.95,.05,.05)
 assert retained_profit(1.,.79,2.,.8)==(2.99,.8,.010000000000000009)
 assert cashpool(20.,0.,9.5)==(.5,10.,.5,0.)
 m,b,_,_=cashpool(20.,0.,9.5)
 assert m+(20.-m)==20. and b==10.
 assert cashpool(20.,0.,10.)==(0.,10.,0.,0.)
 assert cashpool(20.,4.,10.)==(1.,7.,0.,3.)
 try:cashpool(20.,-1.,10.)
 except ValueError:pass
 else:raise AssertionError('cumulative pool limit must fail')
 br=run('base');delayed=run('odin_delay')
 assert abs(br[2]['subs']['ODIN']['legal_retained']+.44406)<1e-10
 assert br[2]['subs']['ODIN']['reserve']==0.
 assert abs(br[3]['subs']['ODIN']['reserve_addition']-.06511849874703744)<1e-10
 assert sum(row['subs'].get('ODIN',{}).get('cu',0)>0 for row in br)==26
 assert sum(row['subs'].get('ODIN',{}).get('cu',0)>0 for row in delayed)==26
 assert (180000+280000+24*371000)*.044==412016. and 412016.<469000.
 assert abs(operation('ODIN',1,'base',0)[0]['fcf']-operation('ODIN',1,'no_future_stream_financing',0)[0]['fcf']-1.)<1e-10
 assert 'ODIN' in delayed[30]['subs'] and 'ODIN' not in delayed[31]['subs']
 # simplified genuine valuation chain: year1 payout10, year6 payout20 at10%; independently hand computed.
 op,_=operation('BR',1,'base',0.)
 assert abs(op['ni']-.924)<1e-10 and abs(op['fcf']-.774)<1e-10
 rr=[{'distribution_per_share':v} for v in [10,0,0,0,0,20]]
 q=valuation(rr,.1)
 assert abs(q['pv']-(10/1.1+20/1.771561))<1e-10
 assert abs(q['tv5']-20/1.1)<1e-10
 try:run('base',True,500.)
 except ValueError:pass
 else:raise AssertionError('zero-dividend insolvency must fail')
 return {'liquidity_hand_cases':True,'formal_pv_hand_case':True,'operating_hand_case':True,'loss_recovery_and_reserve_cap':True,'cashpool_cumulative_and_repayment':True,'zero_dividend_funding_failure':True}

def main():
 out={'units':'CNY billion; shares billion; price CNY/share','base_parameters':{'copper_usd_t':10500,'cobalt_usd_t':35000,'gold_usd_oz':3200,'fx':FX,'rates':RATES,'shares':SHARES,'finite_horizon':N},'tests':tests(),'scenarios':{}}
 for name in ['base','cycle','structural','upside','copper_minus_10','copper_plus_10','tax_30','tax_50','cost_plus_15','ixm_wc_shock','remit_delay','legal_zero','cash_shift','payout_delay','odin_delay','reserve_double','no_future_stream_financing','stream_payment_22']:
  try:
   rows=run(name);out['scenarios'][name]={'valuation':[valuation(rows,r) for r in RATES],'annual':rows}
  except ValueError as e:out['scenarios'][name]={'feasible':False,'reason':str(e)}
 out['auxiliary_residual_income']=[residual_income(.18),residual_income(.22)]
 payload=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'
 Path(__file__).with_name('2026-Q3-output.json').write_text(payload,encoding='utf-8')
 sys.stdout.write(payload)
if __name__=='__main__':main()
