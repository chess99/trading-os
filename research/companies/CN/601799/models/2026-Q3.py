#!/usr/bin/env python3
"""601799 independent cash/legal-capital model. All amounts CNY million; shares million.
No imports from production, files, environment, network, argv, or external packages.
Budgets are conditional estimates, not subsidiary statutory accounts or promises.
"""
import json, math, copy, hashlib
ASOF='2026-10-28T16:10:00+00:00'
FACTS={'q3_revenue':10493.78173223,'q3_parent_ni':931.72787212,'q3_equity':11479.98602406,'q3_nci':2.98502040,'q3_cash':3092.17215210,'q3_liquid_investment':466.82670520,'q3_strategic_investments':790.32425928,'q3_interest_lease_longpay':148.44249566,'oct_paid_dividend':56.64173080,'oct_buyback_cash':10.4155,'oct_buyback_shares':.151,'issued_shares':285.679419,'old_treasury_shares':2.470765,'mother_h1_re':7496.43256016,'mother_reserve':179.34606582,'mother_capital_premium':4129.40171388,'mother_investments':1758.72103835,'jilin_receivable':20.37896907}
# Id, registered capital, paid capital used for opening capital/RE split, reserve,
# cash, operating net capital, financial assets, external debt, mother cost, ownership.
# CN registered and mother costs are H1 actual. Subsidiary opening asset allocation,
# reserves and RE are explicit budgets constrained by group totals, not claimed actuals.
SPECS=[
 ('serbia',.80,856.62629929,0,100,560,0,30,856.62629929,1),
 ('foshan',195,195,0,55,113.2846,0,0,195,1),
 ('jilin',185,185,0,20,185,0,0,185,1),
 ('electronics',150,35.5,0,20,15.5,0,0,35.5,1),
 ('hongkong',56,475.761158,0,50,27.8021,290,0,425.98189657,1),
 ('japan',5.79924828,5.79924828,0,1,1.495,0,0,5.79924828,1),
 ('europe',.81359421,.81359421,0,.2,.0029,0,0,.81359421,1),
 ('shanghai',20,20,0,8,12.5938,0,0,20,1),
 ('trade',1,1,0,20,23.57,0,0,1,1),
 ('digital',5,1,0,1,.6113,0,0,1,1),
 ('chongqing',100,25,0,8,17,0,0,25,1),
 ('robot',100,10,0,7,2.950068,0,0,7,.7)]
# Hong Kong owns the immaterial Mexico/USA/Delaware/North Carolina chain; its
# consolidated operating budget is ring-fenced, not presumed directly parent-cash.
SCENARIOS={
 'core_low':dict(r=.10,g=.01,scale=.98,margin=-.004,capmult=1.10,nwc=.17,mode='base'),
 'base':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.,nwc=.15,mode='base'),
 'core_high':dict(r=.09,g=.02,scale=1.02,margin=.003,capmult=.95,nwc=.145,mode='base'),
 'cycle':dict(r=.10,g=.015,scale=1.,margin=0.,capmult=1.10,nwc=.19,mode='cycle'),
 'structural':dict(r=.105,g=0.,scale=.85,margin=-.028,capmult=1.2,nwc=.22,mode='structural'),
 'optimistic':dict(r=.09,g=.02,scale=1.12,margin=.012,capmult=1.,nwc=.145,mode='optimistic'),
 'margin_minus_1pct':dict(r=.095,g=.015,scale=1.,margin=-.01,capmult=1.,nwc=.15,mode='base'),
 'capex_plus_30pct':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.3,nwc=.15,mode='base'),
 'receivables_delay':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.,nwc=.23,mode='base'),
 'h_issue_conditional':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.,nwc=.15,mode='base',issue=True),
 'full_50yi_project':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.,nwc=.15,mode='base',full_project=True),
 'parent_legal_re_minus1000':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.,nwc=.15,mode='base',re_cut=1000),
 'internal_settlement_300':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.,nwc=.15,mode='base',settlement=300),
 'reserve_opening_high':dict(r=.095,g=.015,scale=1.,margin=0.,capmult=1.,nwc=.15,mode='base',reserve_high=True),
 'aux_competitive_replacement':dict(r=.10,g=.01,scale=1.,margin=0.,capmult=1.,nwc=.18,mode='aux')}

def close(a,b,label='identity'):
 assert abs(a-b)<1e-6*max(1,abs(a),abs(b)),(label,a,b)
def entity(name,reg,paid,reserve,cash,k,fin,debt,investment,own):
 loan=FACTS['jilin_receivable'] if name=='jilin' else 0.
 eq=cash+k+fin-debt-loan
 return dict(name=name,reg=reg,paid=paid,reserve=reserve,re=eq-paid-reserve,cash=cash,ppe=k*.70,nwc=k*.30,fin=fin,debt=debt,loan=loan,investment=investment,own=own,payable=0.,active=True,receivable=0.)
def initial(cfg):
 es={x[0]:entity(*x) for x in SPECS}
 # Old inventory shares may be re-granted: fully diluted denominator includes them.
 # Only October cancellation-purpose shares excluded, never treats purchase as dividend.
 cash=FACTS['q3_cash']+FACTS['q3_liquid_investment']-FACTS['oct_paid_dividend']-FACTS['oct_buyback_cash']
 geq=FACTS['q3_equity']+FACTS['q3_nci']-FACTS['oct_buyback_cash']
 fin=FACTS['q3_strategic_investments']
 debt=FACTS['q3_interest_lease_longpay']
 k=geq-cash-fin+debt
 p=entity('parent',FACTS['issued_shares'],0,FACTS['mother_reserve'],cash-sum(e['cash'] for e in es.values()),k-sum(e['ppe']+e['nwc'] for e in es.values()),fin-sum(e['fin'] for e in es.values()),debt-sum(e['debt'] for e in es.values()),0,1)
 p['investment']=sum(e['investment'] for e in es.values());p['loanrec']=sum(e['loan'] for e in es.values())
 p['paid']=p['reg']+FACTS['mother_capital_premium']-294.97339946+35.71545467-FACTS['oct_buyback_cash']
 p['re']=p['cash']+p['ppe']+p['nwc']+p['fin']+p['investment']+p['loanrec']-p['debt']-p['paid']-p['reserve']
 p['re']-=cfg.get('re_cut',0);p['paid']+=cfg.get('re_cut',0)
 es['parent']=p
 # No unverified HK opening realised surplus is paid. This reserve is tested by
 # future realised operating profit and actual asset realisations.
 hk=es['hongkong'];locked=max(0,hk['re']);hk['re']-=locked;hk['paid']+=locked
 if cfg.get('reserve_high'):
  for n,e in es.items():
   if n not in ('parent','serbia','hongkong','japan','europe'):
    delta=max(0,.5*e['reg']-e['reserve']);e['reserve']+=delta;e['re']-=delta
 return es,FACTS['issued_shares']-.151

def legal_profit(e,profit):
 old=e['re'];e['re']+=profit
 # Losses are first made good; capital premium and cash never create distributable RE.
 base=max(0,profit+min(0,old))
 rate=0 if e['name'] in ('serbia','hongkong','japan','europe') else .10
 appropr=min(rate*base,max(0,.5*e['reg']-e['reserve']))
 e['re']-=appropr;e['reserve']+=appropr
 return appropr

def finance(e,need,kind='debt',price=40.):
 assert kind in ('debt','equity')
 need=max(0,need)
 if kind=='debt':e['cash']+=need;e['debt']+=need;return (need,0.)
 shares=need/price;e['cash']+=need;e['reg']+=shares;e['paid']+=need;return (0.,shares)

def declare(e,p,minimum_cash):
 dd=min(max(0,e['re']),max(0,e['cash']-e['payable']-minimum_cash)*.8)
 e['re']-=dd;e['payable']+=dd
 income=dd*e['own'];p['receivable']+=income
 return dd,income

def settle_dividend(e,p):
 paid=e['payable'];e['cash']-=paid;e['payable']=0
 receipt=paid*e['own'];p['cash']+=receipt;p['receivable']-=receipt
 return receipt,paid*(1-e['own'])

def equity(e,parent=False):
 assets=e['cash']+e['ppe']+e['nwc']+e['fin']+e['receivable']
 if parent:assets+=e['investment']+e['loanrec']
 return assets-e['debt']-e['loan']-e['payable']
def audit(es):
 p=es['parent'];close(p['loanrec'],sum(e['loan'] for n,e in es.items() if n!='parent'),'internal principal')
 close(p['receivable'],sum(e['payable']*e['own'] for n,e in es.items() if n!='parent'),'declared dividend receivable')
 for n,e in es.items():
  close(equity(e,n=='parent'),e['paid']+e['reserve']+e['re'],n+' legal equity')
  assert e['cash']>=-1e-7 and e['payable']<=e['cash']+1e-7,(n,'cash backing')
 return sum(e['cash']+e['ppe']+e['nwc']+e['fin']-e['debt'] for e in es.values())-sum(e['payable']*(1-e['own']) for n,e in es.items() if n!='parent')

def interpolate(xs,t):
 if t<=len(xs):return xs[t-1]
 return xs[-1]
def group_revenue(t,c):
 if c['mode']=='aux':
  # Independent bottom-up mature headlamp/rear lamp units and net ASP, not primary
  # growth rates: 2025 actual 13.085m*614.5 and 19.043m*291.3, competitive mix haircut.
  front=interpolate([12.5,13.,13.5,14.,14.5,14.8,15.1,15.4,15.7,16.],t)
  rear=interpolate([18.,18.8,19.5,20.3,21.,21.4,21.8,22.2,22.6,23.],t)
  rev=front*interpolate([600,606,612,618,624,630,636,642,648,654],t)+rear*interpolate([280,283,286,289,292,295,298,301,304,307],t)+1100
  return rev*(1+c['g'])**max(0,t-10)
 xs=[14500,15400,16600,17900,19000,20000,20900,21700,22400,23000]
 rev=interpolate(xs,t)*c['scale']*(1+c['g'])**max(0,t-10)
 if c['mode']=='cycle':rev*=interpolate([.86,.89,.96,1.,1.],t)
 if c['mode']=='structural':rev*=interpolate([1,.98,.96,.94,.92],t)
 return rev

def drivers(t,c):
 total=group_revenue(t,c);ratio=total/14500
 ser=interpolate([620,780,1050,1350,1600,1780,1930,2050,2150,2250],t)*c['scale']*(1+c['g'])**max(0,t-10)
 fos=total*.045;elect=interpolate([100,300,650,1050,1500,1800,2000,2200,2300,2400],t)*c['scale']*(1+c['g'])**max(0,t-10)
 hk=interpolate([0,40,120,200,260,300,340,370,390,400],t)*(1+c['g'])**max(0,t-10)
 ch=interpolate([100,250,400,550,650,700,750,800,830,850],t)*(1+c['g'])**max(0,t-10)
 robot=0 if t<4 else 20*ratio
 if c['mode']=='structural' and t>=4:ser=0
 revs={'serbia':ser,'foshan':fos,'electronics':elect,'hongkong':hk,'chongqing':ch,'robot':robot,'jilin':30*ratio,'japan':0,'europe':0,'shanghai':0,'trade':0,'digital':0}
 revs['parent']=total-sum(revs.values())
 out={}
 for n,rev in revs.items():
  if n=='parent':
   gross=interpolate([.185,.188,.193,.196,.198,.198,.197,.196,.195,.195],t)+c['margin']
   rd=interpolate([.069,.068,.065,.063,.062,.061,.061,.061,.061,.061],t)
   pretax=gross-rd-.030+.006 # admin/selling/taxes; recurring benefits normalized lower
   if c['mode']=='aux':pretax=.18-.065-.033+.004+c['margin']
   if c['mode']=='cycle':pretax-=interpolate([.025,.02,.005,0],t)
   margin=pretax*.85
  elif n=='serbia':
   margin=interpolate([-.035,-.01,.015,.035,.05,.055,.055,.055,.055,.055],t)+c['margin']*.7
   if c['mode']=='structural':margin=-.12
   if c['mode']=='optimistic':margin+=.02
  elif n in ('electronics','chongqing','hongkong'):
   margin=interpolate([-.04,-.01,.02,.05,.065,.07,.07,.07,.07,.07],t)+c['margin']
  elif n=='robot':margin=-.2
  else:margin=.04+c['margin']*.5
  ni=rev*margin
  # Non-revenue support entities are genuine cost centres, not magic dividend makers.
  if n in ('japan','europe','shanghai','digital'):ni=0. # services reimbursed at cost within parent R&D/admin expense
  if n=='robot':ni-=interpolate([10,12,15,15,10],t)*ratio
  nwcr=c['nwc'] if n=='parent' else .16
  if n=='parent' and t>10 and c['nwc']>.17:nwcr-=min(c['nwc']-.17,(t-10)*.01)
  # Existing assets remain until useful lives run off; pre-build is additional and
  # diminishes as utilisation rises, never deducted twice with the original asset cost.
  pper=.24 if n=='parent' else .32
  extra=0
  if n=='electronics':
   extra=interpolate([350,650,800,800,700,600,400,200,100,0],t)
   if c.get('full_project'):extra+=interpolate([800,1600,2400,3000,3500,3500,3300,3100,2900,2700],t)*(.9**max(0,t-10))
  if n=='serbia':extra=interpolate([250,450,500,450,350,250,150,80,40,0],t)
  if n=='hongkong':extra=interpolate([100,180,220,220,180,120,70,30,0,0],t)
  if n=='chongqing':extra=interpolate([40,80,100,100,80,60,40,20,0,0],t)
  out[n]=dict(revenue=rev,ni=ni,margin=margin,ppe_target=(rev*pper+extra)*c['capmult'],nwc_target=rev*nwcr,minimum_cash=max(0,rev*.06),extra_prebuild=extra)
 return out

def liquidate(e,p,recovery=.55,employee=20):
 # External liabilities senior; internal principal next; only actual residual goes to
 # equity holders. Loss on assets and exit cost hit subsidiary RE; not cash twice.
 oldcost=e['investment'];loan=e['loan'];ext=e['debt'];pp=e['ppe'];nw=e['nwc'];fi=e['fin']
 proceeds=pp*recovery+nw*.8+fi*.8
 loss=pp+nw+fi-proceeds+employee
 e['cash']+=proceeds-employee;e['ppe']=e['nwc']=e['fin']=0.;legal_profit(e,-loss)
 assert e['cash']>=ext
 e['cash']-=ext;e['debt']=0.
 repay=min(max(0,e['cash']),loan);e['cash']-=repay;e['loan']-=repay;p['cash']+=repay;p['loanrec']-=repay
 writeoff=e['loan'];e['loan']=0;p['loanrec']-=writeoff;legal_profit(p,-writeoff)
 # On dissolution all capital is returned in priority order, including minority share.
 residual=max(0,e['cash']);parent_recovery=residual*e['own'];nci=residual*(1-e['own'])
 e['cash']=0;e['paid']=e['reserve']=e['re']=0;e['active']=False
 p['cash']+=parent_recovery;p['investment']-=oldcost;legal_profit(p,parent_recovery-oldcost)
 e['investment']=0
 return dict(proceeds=proceeds,asset_loss_and_cost=loss,external_repayment=ext,loan_repayment=repay,loan_writeoff=writeoff,parent_historical_plus_new_cost=oldcost,parent_capital_recovery=parent_recovery,minority_recovery=nci,employee_and_lease_exit=employee)

def run(c,N=360,start=None,start_t=0):
 if start is None:es,shares=initial(c)
 else:es,shares=copy.deepcopy(start)
 audit(es);rows=[];pv=0.;pv5=0.;state5=None
 for t in range(start_t+1,N+1):
  p=es['parent'];oldcash=sum(e['cash'] for e in es.values());oldgeq=audit(es)
  flows=dict(operating_ni=0.,capex=0.,depreciation=0.,delta_nwc=0.,financial_disposal=0.,financial_loss=0.,external_principal=0.,external_new=0.,external_equity=0.,minority_in=0.,minority_paid=0.,buyback=0.,holder_paid=0.)
  erows={};drv=drivers(t,c)
  # Pay prior declared, cash-backed dividends; no second parent investment income.
  paidup=0
  for n,e in es.items():
   if n=='parent':continue
   receipt,minority=settle_dividend(e,p);paidup+=receipt
   flows['minority_paid']+=minority
  # Optional H issue is mutually exclusive with borrowing the same amount. Amount and
  # 40 CNY budget issue proceeds are conditions, NOT a current price or completed action.
  if t==1 and c.get('issue'):
   amount=44.799650*40;_,newshares=finance(p,amount,'equity',40)
   shares+=newshares;flows['external_equity']+=amount
  if t==1:
   cost=100-FACTS['oct_buyback_cash'];retired=cost/148.31
   p['cash']-=cost;p['paid']-=cost;p['reg']-=retired+.151;shares-=retired;flows['buyback']=cost
  # Each legal entity earns and invests; repayments always separate from income.
  for n,e in es.items():
   if not e['active']:continue
   d=drv[n];prior=copy.deepcopy(e)
   interest=e['debt']*.045
   financial_income=e['fin']*.015+max(0,e['cash']-e['payable']-d['minimum_cash'])*.01
   if n in ('japan','europe','shanghai','digital','trade'):financial_income=0.
   ni=d['ni']+financial_income-interest
   dep=min(e['ppe'],max(e['ppe']*.1,d['revenue']*.028))
   target=max(e['ppe']-.35*dep,d['ppe_target'])
   capex=target-(e['ppe']-dep)
   # Services retain productive capital against costs; no forced fake asset release.
   if n in ('japan','europe','shanghai','digital','trade','jilin'):
    capex=dep;target=e['ppe']
   nw=d['nwc_target'] if n not in ('japan','europe','shanghai','digital','trade','jilin') else e['nwc']
   delta=nw-e['nwc'];e['ppe']=target;e['nwc']=nw
   disposal=e['fin']*.10 if t<=10 else e['fin']*.20
   disploss=disposal*.10 # deliberate conservative realization discount, not instant cash add
   e['fin']-=disposal;e['cash']+=disposal-disploss
   ni-=disploss
   e['cash']+=ni+dep-capex-delta+disploss
   debtpay=min(e['debt'],prior['debt']/(max(1,6-t))) if t<=5 else e['debt']*.20
   # No forced debt repayment when it would starve committed capex: repayment waits.
   debtpay=min(debtpay,max(0,e['cash']-d['minimum_cash']))
   e['cash']-=debtpay;e['debt']-=debtpay
   app=legal_profit(e,ni)
   for k,v in [('operating_ni',ni),('capex',capex),('depreciation',dep),('delta_nwc',delta),('financial_disposal',disposal-disploss),('financial_loss',disploss),('external_principal',debtpay)]:flows[k]+=v
   erows[n]=dict(revenue=d['revenue'],net_income=ni,margin=d['margin'],opening_cash=prior['cash'],opening_re=prior['re'],opening_ppe=prior['ppe'],opening_nwc=prior['nwc'],depreciation=dep,capex=capex,delta_nwc=delta,financial_income=financial_income,financial_disposal=disposal,financial_haircut=disploss,interest=interest,debt_paid=debtpay,reserve_appropriation=app,minimum_cash=d['minimum_cash'],capital_injection=0.,internal_loan_in=0.,internal_repayment=0.,dividend_declared=0.,exit=None)
  if t==1 and c.get('settlement'):
   settle=c['settlement'];p['cash']-=settle;p['nwc']+=settle
   es['foshan']['cash']+=settle;es['foshan']['nwc']-=settle
   erows['parent']['internal_trade_settlement']=-settle;erows['foshan']['internal_trade_settlement']=settle
  # Subsidiary deficits funded legally by parent equity. Robot minority co-funds
  # pro rata, preserving 70/30 rather than making parent pay for others for free.
  for n,e in es.items():
   if n=='parent' or not e['active']:continue
   need=max(0,drv[n]['minimum_cash']-e['cash'])
   if need:
    injection=need;e['cash']+=injection;e['paid']+=injection
    p['cash']-=injection*e['own'];p['investment']+=injection*e['own'];e['investment']+=injection*e['own']
    flows['minority_in']+=injection*(1-e['own']);erows[n]['capital_injection']=injection
   # Longstanding Jilin receivable settles over five years from available own cash,
   # not from a simultaneous round-trip parent funding or arbitrary legal netting.
   repay=min(e['loan'],max(0,e['cash']-drv[n]['minimum_cash'])*.20)
   e['cash']-=repay;e['loan']-=repay;p['cash']+=repay;p['loanrec']-=repay
   erows[n]['internal_repayment']=repay
  # Stop robot losses after three-year validation budget; exit pays all stakeholders.
  # Structural overseas failure at t4 has real recovery, severance and parent cost loss.
  for n in (['robot'] if t==4 else [])+(['serbia'] if t==4 and c['mode']=='structural' else [])+(['jilin'] if t==10 and c['mode']=='structural' else []):
   e=es[n]
   if e['active']:
    before=sum(x['cash'] for x in es.values());eqbefore=audit(es)
    ex=liquidate(e,p,.55,2 if n=='robot' else (10 if n=='jilin' else 35));erows[n]['exit']=ex
    flows['minority_paid']+=ex['minority_recovery'];flows['exit_cash_net']=flows.get('exit_cash_net',0)+sum(x['cash'] for x in es.values())-before+ex['minority_recovery']
    flows['exit_economic_loss']=flows.get('exit_economic_loss',0)+eqbefore-audit(es)-ex['minority_recovery']
  # Parent liquidity: no dividend before funded capital. Credit is conditional and
  # capped at 2bn (small versus equity); any exceeded path raises, not silently passes.
  need=max(0,drv['parent']['minimum_cash']-p['cash'])
  if need:
   assert p['debt']+need<2000,'unfunded path'
   d,_=finance(p,need,'debt');flows['external_new']+=d
  declared=0;crossborder_tax=0
  for n,e in es.items():
   if n=='parent' or not e['active']:continue
   surplus=max(0,e['cash']-drv[n]['minimum_cash'])
   # Dividend escrow backed at declaration. Distribution uses profits only,
   # subsidiary equity capital never silently becomes ordinary income.
   dd,income=declare(e,p,drv[n]['minimum_cash']);declared+=income;erows[n]['dividend_declared']=dd
   if n in ('serbia','hongkong','japan','europe'):crossborder_tax+=dd*e['own']*.05
  p['cash']-=crossborder_tax;flows['operating_ni']-=crossborder_tax
  parent_app=legal_profit(p,declared-crossborder_tax)
  # Mature release of genuinely surplus liquidity, retaining operating cash floor.
  target_payout=interpolate([.38,.40,.42,.45,.48,.55,.62,.70,.78,.85],t)
  normal=max(0,erows['parent']['net_income']+declared)*target_payout
  surplus=max(0,p['cash']-drv['parent']['minimum_cash'])
  extra=max(0,surplus-normal)*(.06 if t<=5 else .15)
  div=min(max(0,p['re']),surplus,normal+extra)
  p['cash']-=div;p['re']-=div;flows['holder_paid']=div
  dps=div/shares;pvpart=dps/(1+c['r'])**(t-start_t);pv+=pvpart
  if t<=5:pv5+=pvpart
  geq=audit(es)
  expectedcash=oldcash+flows['operating_ni']+flows['depreciation']-flows['capex']-flows['delta_nwc']+flows['financial_loss']+flows['financial_disposal']-flows['external_principal']+flows['external_new']+flows['external_equity']+flows['minority_in']-flows['minority_paid']-flows['buyback']-div+flows.get('exit_cash_net',0)
  close(sum(e['cash'] for e in es.values()),expectedcash,'group cash')
  # Ordinary equity profit bridge excludes internal declaration; minority obligations
  # are recognized at declaration and capital losses at liquidation.
  geqexpected=oldgeq+flows['operating_ni']+flows['external_equity']+flows['minority_in']-flows['buyback']-div-flows['minority_paid']-flows.get('exit_economic_loss',0)
  newminoritydecl=sum(e['payable']*(1-e['own']) for n,e in es.items() if n!='parent')
  # old minority payable was paid this year and is already excluded from oldgeq;
  # add its payment back to avoid counting twice in the economic equity definition.
  oldminoritypaid=flows['minority_paid']-sum((v['exit'] or {}).get('minority_recovery',0) for v in erows.values())
  geqexpected+=oldminoritypaid-newminoritydecl
  close(geq,geqexpected,'group economic equity')
  for n,e in es.items():
   if n in erows:erows[n]['closing']=copy.deepcopy(e)
  row=dict(year=t,calendar_label=2026+t,group_revenue=sum(v['revenue'] for v in erows.values()),group_cash=sum(e['cash'] for e in es.values()),group_equity=geq,flows=flows,shares=shares,distribution_per_share=dps,parent_dividend_declared_income=declared,parent_sub_dividend_received=paidup,parent_extra_reserve=parent_app,crossborder_tax_budget=crossborder_tax,entities=erows)
  rows.append(row)
  if t==5:state5=copy.deepcopy((es,shares))
 return dict(pv=pv,pv_first5=pv5,terminal5=(pv-pv5)*(1+c['r'])**5 if start_t==0 else None,rows=rows,state5=state5,end=copy.deepcopy((es,shares)))

def fixtures():
 e=entity('test',100,100,0,100,0,0,0,0,1);e['re']=-20;e['cash']=80
 assert legal_profit(e,10)==0 and e['re']==-10
 assert legal_profit(e,30)==2 and e['re']==18 and e['reserve']==2
 e['reserve']=49;e['re']=0;assert legal_profit(e,100)==1 and e['reserve']==50 and e['re']==99
 p=entity('parent',10,10,0,10,0,0,0,0,1);debt,sh=finance(p,80,'equity',40);assert debt==0 and sh==2 and p['debt']==0 and p['reg']==12
 q=entity('parent',10,10,0,10,0,0,0,0,1);debt,sh=finance(q,80,'debt');assert debt==80 and sh==0 and q['reg']==10
 p=entity('parent',1,1,0,100,0,0,0,0,1);p['loanrec']=20;p['investment']=70;p['re']=189
 e=entity('robot',100,100,0,50,100,0,30,70,.7);e['loan']=20;e['re']=0;e['ppe']=100;e['nwc']=0
 ex=liquidate(e,p,.5,10)
 close(ex['proceeds'],50);close(ex['loan_repayment'],20);close(ex['parent_capital_recovery'],28);close(ex['minority_recovery'],12);close(p['cash'],148);close(p['re'],147)
 # Actual production declaration and settlement helpers, with non-zero minority.
 p=entity('parent',10,10,0,10,0,0,0,0,1)
 e=entity('robot',10,10,0,110,0,0,0,7,.7)
 dd,inc=declare(e,p,10);close(dd,80);close(inc,56)
 legal_profit(p,inc);close(p['cash'],10);close(p['receivable'],56)
 r0=p['re'];res0=p['reserve'];receipt,mi=settle_dividend(e,p)
 close(receipt,56);close(mi,24);close(p['cash'],66);close(p['re'],r0);close(p['reserve'],res0);close(p['receivable'],0)
 # No unfunded perpetual declarations: pending escrow is unavailable for new ones.
 e=entity('robot',10,10,0,110,0,0,0,7,.7)
 dd,_=declare(e,p,10);dd2,_=declare(e,p,10)
 close(dd,80);close(dd2,16);assert e['payable']<=e['cash']
 return {'cash_backed_declaration_settlement_no_double_income':True,'loss_first_reserve_cap':True,'financing_exclusive':True,'exit_recovery_minority_cost':True}

def main():
 f=fixtures();out={'schema':'601799-legal-cash-v1','as_of':ASOF,'units':'CNY million, million shares, per-share CNY','facts':FACTS,'opening_budget_specs':SPECS,'fixtures':f,'scenario_inputs':SCENARIOS,'scenarios':{},'continuations':{}}
 for name,c in SCENARIOS.items():
  a=run(c,600);mid=run(c,780);b=run(c,960)
  # The extension re-evaluates every year and the actual balance sheet; no hardcoded TV.
  assert abs(a['pv']-b['pv'])<.00001,(name,'PV nonconvergence')
  ea,eb=a['end'][0],b['end'][0];growth=((1+c['g'])**360)
  checks={}
  for n in ea:
   checks[n]={}
   for k in ('cash','ppe','nwc','debt','payable','receivable','loan','reserve','reg','paid','re'):
    # Fixed nominal registered capital and paid capital are distinguished from growth
    # assets. RE has an additive fixed-capital offset, tested in total legal equity.
    v1,v2=ea[n][k],eb[n][k]
    if k in ('reg','paid','reserve'):err=abs(v2-v1)/max(1,abs(v1),abs(v2))
    elif k=='re':
     v1+=ea[n]['paid']+ea[n]['reserve'];v2+=eb[n]['paid']+eb[n]['reserve'];err=abs(v2/growth-v1)/max(1,abs(v1))
    else:err=abs(v2/growth-v1)/max(1,abs(v1))
    checks[n][k]=err
   # service entities and fixed parent historic investment create additive constants;
   # test absolute PV of residuals as well as normalized economic scale.
  affine={}
  for n in ea:
   affine[n]={}
   for k in ('cash','ppe','nwc','debt','payable','receivable','loan','reserve','reg','paid','re'):
    v0=ea[n][k];v1=mid['end'][0][n][k];v2=eb[n][k]
    q=(1+c['g'])**180
    # A growing component plus a fixed nominal capital component; g=0 must be flat.
    pred=v1+(v1-v0)*q if c['g'] else v1
    err=abs(v2-pred)/max(1,abs(v2));affine[n][k]=err
    assert err<.001,(name,n,k,'state nonconvergence',v0,v1,v2,err)
  b['convergence']={'N600_pv':a['pv'],'N780_pv':mid['pv'],'N960_pv':b['pv'],'difference':b['pv']-a['pv'],'raw_growth_normalized_errors':checks,'affine_fixed_and_growth_state_errors':affine}
  b.pop('end');out['scenarios'][name]=b
 # V1 terminal range shares one actual base Y5 cash/legal/capital state.
 base=out['scenarios']['base'];s5=base['state5']
 for label,r,g,margin in [('low',.10,.01,-.004),('high',.09,.02,.003)]:
  c=copy.deepcopy(SCENARIOS['base']);c.update(r=r,g=g,margin=margin)
  x=run(c,960,start=s5,start_t=5)
  xs=run(c,600,start=s5,start_t=5);xm=run(c,780,start=s5,start_t=5)
  errors={};q=(1+c['g'])**180
  for en in x['end'][0]:
   errors[en]={}
   for key in ('cash','ppe','nwc','debt','payable','receivable','loan','reserve','reg','paid','re'):
    v0=xs['end'][0][en][key];v1=xm['end'][0][en][key];v2=x['end'][0][en][key]
    pred=v1+(v1-v0)*q;err=abs(v2-pred)/max(1,abs(v2));errors[en][key]=err
    assert err<.001,('continuation',label,en,key,err)
  assert abs(xs['pv']-x['pv'])<.00001
  x['convergence']={'N600_pv':xs['pv'],'N780_pv':xm['pv'],'N960_pv':x['pv'],'state_errors':errors}
  x['start_state_sha256']=hashlib.sha256(json.dumps(s5,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  x.pop('end');out['continuations'][label]=x
 out['value_range']={'low':round(out['scenarios']['core_low']['pv'],1),'high':round(out['scenarios']['core_high']['pv'],1),'currency':'CNY'}
 out['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':[x['distribution_per_share'] for x in base['rows'][:5]],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':out['continuations']['low']['pv'],'high':out['continuations']['high']['pv']}}}
 print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
