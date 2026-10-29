#!/usr/bin/env python3
"""Independent SDIC common-equity research model. stdlib only; CNY bn, kWh bn.
Not legal budgets: named Yalong and parent plus ring-fenced economic pools.
All constants literal. No files, environment, network or market prices read.
"""
import json, math, copy, hashlib
SHARES=8.004494262
YEARS=400
# Pool ownership outside Yalong is an explicit economic allocation, not asserted legal title.
POOLS={
 'Yalong':dict(owner=.52,cash=1.5,debt=90.,capital=54.7,asset=145.,reserve=9.8,re=15.,q=88.,price=.274,variable=.035,fixed=2.25,da=5.9,tax=.18,book=79.3144343,roe=.118,oldpay=2.4,floor=1.2),
 'OtherHydro':dict(owner=.55,cash=.6,debt=.4,capital=3.0,asset=5.,reserve=.5,re=0.,q=10.8,price=.224,variable=.02,fixed=.22,da=.37,tax=.16,book=5.2,roe=.24,oldpay=0.,floor=.3),
 'Thermal':dict(owner=.65,cash=2.,debt=20.,capital=11.,asset=36.,reserve=1.,re=0.,q=48.,price=.412,variable=.258,fixed=1.45,da=2.5,tax=.25,book=14.8,roe=.125,oldpay=0.,floor=1.3),
 'Renewable':dict(owner=.75,cash=5.25240093,debt=30.,capital=9.,asset=41.,reserve=.7,re=0.,q=13.8,price=.35,variable=.035,fixed=.65,da=1.9,tax=.19,book=15.,roe=.055,oldpay=.457315877/.75,floor=1.),
}
# Total costs include prior spend. Spend schedules below ONLY future cash; old assets already paid.
# type, total, prior, first full operation year, quantity/revenue, capital cash schedule.
PROJECTS=[
 dict(name='Kara',pool='Yalong',owner=1.,kind='hydro',total=17.1210928,prior=7.,cod=2030,q=4.5238,price=.32,cost=.035,life=50,spend=[3.4,3.4,3.3210928]),
 dict(name='Mendigou',pool='Yalong',owner=1.,kind='hydro',total=34.721993739,prior=9.5,cod=2033,q=10.405,price=.32,cost=.035,life=50,spend=[3.5,4.,4.5,4.5,4.5,4.221993739]),
 dict(name='Yagen1',pool='Yalong',owner=1.,kind='hydro',total=5.8795716,prior=2.2,cod=2030,q=1.3,price=.31,cost=.035,life=50,spend=[1.2,1.3,1.1795716]),
 dict(name='LianghekouPump',pool='Yalong',owner=1.,kind='pump',total=8.9602831,prior=3.,cod=2030,q=0.,price=0.,cost=0.,life=40,spend=[2.,2.,1.9602831]),
 dict(name='DaofuPump',pool='Yalong',owner=1.,kind='pump',total=15.1,prior=2.,cod=2033,q=0.,price=0.,cost=0.,life=40,spend=[1.8,2.2,2.6,2.6,2.2,1.7]),
 dict(name='Yagen2',pool='Yalong',owner=.9,kind='hydro',total=33.394,prior=0.,cod=2036,q=8.645,price=.32,cost=.035,life=50,spend=[1.,2.,3.,4.,4.,5.,5.,5.,4.394]),
 dict(name='YalongWindSolar',pool='Yalong',owner=1.,kind='renew',total=12.,prior=4.5,cod=2029,q=4.,price=.29,cost=.04,life=25,spend=[3.5,4.]),
 dict(name='ThermalCompletion',pool='Thermal',owner=1.,kind='thermal',total=8.,prior=5.,cod=2029,q=5.,price=.40,cost=.28,life=30,spend=[2.,1.]),
 dict(name='OtherRenewCompletion',pool='Renewable',owner=1.,kind='renew',total=12.,prior=4.,cod=2029,q=3.5,price=.30,cost=.04,life=25,spend=[4.,4.]),
]
# Scenarios are complete annual reruns. Rate alone is only used for pure sensitivity.
CASES={
 'base':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=0.,maint=1.),
 'core_low':dict(rate=.085,water=.98,price=.99,renewprice=.98,coal=1.01,overrun=1.05,delay=0,collect=.8,spread=.002,maint=1.05),
 'core_high':dict(rate=.075,water=1.02,price=1.01,renewprice=1.02,coal=.99,overrun=1.,delay=0,collect=.9,spread=0.,maint=.95),
 'cyclical':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.08,delay=1,collect=.7,spread=.003,maint=1.,cycle=True),
 'structural':dict(exit_thermal=2036,rate=.09,water=.94,price=.94,renewprice=.85,coal=1.08,overrun=1.2,delay=2,collect=.65,spread=.007,maint=1.12,structural=True),
 'optimistic':dict(rate=.075,water=1.05,price=1.02,renewprice=1.06,coal=.96,overrun=1.,delay=0,collect=.95,spread=-.001,maint=.95),
 'water_minus10':dict(rate=.08,water=.9,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=0.,maint=1.),
 'new_project_return_down':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.15,delay=2,collect=.85,spread=0.,maint=1.,newprice=.85),
 'upstream_delay':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.25,spread=.003,maint=1.),
 'pool_ownership_low':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=0.,maint=1.,pool_owner_delta=-.05),
 'ppp_recovery_low':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=0.,maint=1.,ppp_exit_cost=.8),
 'uk_winddown_delay':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=0.,maint=1.,uk_winddown=2076,uk_exit_factor=.5),
 'fx_plus10':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=0.,maint=1.,fx=1.1),
 'perpetual_no_roll':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=.003,maint=1.,perpetual_redeem=2029),
 'reserve_zero':dict(rate=.08,water=1.,price=1.,renewprice=1.,coal=1.,overrun=1.,delay=0,collect=.85,spread=0.,maint=1.,reserve_zero=True),
}
def near(a,b,tol=1e-7):
 assert abs(a-b)<tol,(a,b)
def law(re,reserve,capital,profit,rate=.1,cap=.5):
 """Loss first, 10% of current profit remaining after prior losses, until 50% capital."""
 earned=max(0.,profit+min(0.,re))
 addition=min(max(0.,capital*cap-reserve),earned*rate)
 return re+profit-addition,reserve+addition,addition

def payment(s,profit,ocf,capex,equity,draw,repay,desired,collection,old_collection=1.):
 """One actual production payment chain; old payable paid without changing current profit."""
 b=copy.deepcopy(s)
 s['capital']+=equity
 s['re'],s['reserve'],transfer=law(s['re'],s['reserve'],s['capital'],profit,s.get('reserve_rate',.1),s.get('reserve_cap',.5))
 pre=s['cash']+ocf-capex+equity+draw-repay
 assert pre>=s['floor']+s.get('payable',0.)-1e-7,('unfunded old payable/minimum',pre,s)
 # First honor old declared obligations; declaration already reduced prior RE.
 oldpaid=min(s.get('payable',0.)*old_collection,max(0.,pre-s['floor']))
 pre-=oldpaid;s['payable']=s.get('payable',0.)-oldpaid
 declared=min(max(0.,s['re']),max(0.,desired),max(0.,pre-s['floor']-s['payable']))
 paid=declared*collection
 s['re']-=declared;s['payable']+=declared-paid;s['cash']=pre-paid
 s['debt']+=draw-repay
 near(s['cash'],b['cash']+ocf-capex+equity+draw-repay-oldpaid-paid)
 near(s['re']+s['reserve'],b['re']+b['reserve']+profit-declared)
 assert s['cash']>=-1e-7 and s['debt']>=-1e-7
 return dict(profit=profit,ocf=ocf,capex=capex,equity_in=equity,new_debt=draw,principal_paid=repay,
             reserve_transfer=transfer,declared=declared,current_cash_paid=paid,old_cash_paid=oldpaid,
             capital_close=s['capital'],capital_surplus_close=s.get('capital_surplus',0.),minimum_operating_cash=s['floor'],cash_open=b['cash'],cash_close=s['cash'],debt_close=s['debt'],re_close=s['re'],reserve_close=s['reserve'],payable_close=s['payable'])

def liquidation(s,sale,asset_book,exit_cost):
 old=copy.deepcopy(s);s['floor']=0.
 other=s.get('other_net_assets',0.);other_sale=max(0.,other)*.8;other_liability=max(0.,-other)
 gross=sale+other_sale
 equity=max(0.,s['debt']+s['payable']+other_liability+exit_cost-s['cash']-gross)
 profit=gross-asset_book-max(0.,other)-exit_cost
 r=payment(s,profit,gross-exit_cost-other_liability,0.,equity,0.,s['debt'],0.,1.)
 remaining=max(0.,s['cash'])
 # Final liquidation is an equity cancellation, not an expense or normal dividend.
 equity_before_cancel=s['capital']+s['reserve']+s['re']+s.get('capital_surplus',0.)
 near(equity_before_cancel,remaining)
 s.update(cash=0.,asset=0.,other_net_assets=0.,capital=0.,reserve=0.,re=0.,capital_surplus=0.,closed=True)
 r.update(capital_return=remaining,cash_close=0.,sale_proceeds=gross,exit_cost=exit_cost,old_nonfinancial_liability_paid=other_liability,other_asset_recovery=other_sale,book_asset_disposed=asset_book+max(0.,other),equity_cancelled=equity_before_cancel,capital_close=0.,reserve_close=0.,re_close=0.,closed=True)
 near(remaining,old['cash']+gross-exit_cost-other_liability+equity-old['debt']-old['payable'])
 return r

def financing(need,mode,issue_price=1.,capacity=30.):
 assert need>=0
 if mode=='debt':
  assert need<=capacity+1e-8
  return need,0.,0.
 if mode=='equity':
  assert issue_price>0
  return 0.,need,need/issue_price
 assert need==0
 return 0.,0.,0.

def initial(c):
 subs={}
 for name,p in POOLS.items():
  subs[name]={k:p[k] for k in ['cash','debt','capital','asset','reserve','re','floor']}
  subs[name]['payable']=p['oldpay']
  subs[name]['other_net_assets']=p['capital']+p['reserve']+p['re']+p['debt']+p['oldpay']-p['cash']-p['asset']
  if c.get('reserve_zero'):
   subs[name]['capital_surplus']=subs[name]['reserve']+subs[name]['re'];subs[name]['reserve']=0.;subs[name]['re']=0.
 return dict(subs=subs,parent=dict(cash=5.293434771,debt=7.8,capital=SHARES,reserve=4.411821408,re=20.200104445,floor=1.,payable=0.),
             shares=SHARES,earmarked=4.05138,restricted=4.308706518,ppp_parent_basis=3.*.9333*.75,ppp=dict(capital_surplus=.7,other_net_assets=0.,reserve_rate=.1,reserve_cap=.2,receivable=11.5,cash=.2,debt=8.,capital=3.,reserve=0.,re=0.,floor=.15,payable=0.),
             loans=.320142394,old_other_loan=.187660108,loan_accrual=0.,investments=10.047435093,uk_equity_basis=1.454240439,uk_equity_legal_cost=1.454240439,uk_parent_cost=1.962042941,cost_basis=58.658336003,thermal_parent_basis=8.0,previous_common_profit=7.0,ar=1.705315877,ukhold=dict(reserve_rate=0.,reserve_cap=0.,cash=.0,debt=0.,capital=1.962042941,reserve=0.,re=0.,floor=0.,payable=0.))

def project_year(p,year,c,method):
 index=year-2027
 delay=c['delay']; j=index-delay
 spend=p['spend'][j]*c['overrun'] if 0<=j<len(p['spend']) else 0.
 cod=p['cod']+delay
 # Gradual first output then full-year capacity; not one jump from build to recovered capital.
 ramp=0 if year<cod-1 else (.35 if year==cod-1 else .85 if year==cod else 1.)
 # Full replacement starts 15y after commissioning; g=0. All prices/costs in constant nominal CNY.
 maturity=min(1.,max(0.,year-cod)/15)
 da=p['total']*c['overrun']/p['life']*ramp*(1+(c['maint']-1)*maturity)
 maintenance=da*(.35+.65*maturity)
 if p['kind']=='pump':
  # Revenue floor NOT asserted tariff: operating NOPAT 4.5% total capital, separate capacity remuneration budget.
  rev=p['total']*(.045/(1-.2)+1/p['life']+.015)*ramp
  opex=p['total']*.015*ramp
 else:
  q=p['q']*ramp*(c['water'] if p['kind']=='hydro' else 1.)
  pr=p['price']*c['price']*(c['renewprice'] if p['kind']=='renew' else 1.)*c.get('newprice',1.)
  rev=q*pr;opex=q*p['cost']*(c['coal'] if p['kind']=='thermal' else 1.)
  opex+=p['total']*.004*ramp
 if method=='capital':
  # Independent engineering-capital return anchor; not calculated from volume-price output.
  returns={'hydro':.048,'pump':.043,'renew':.055,'thermal':.05}
  ebit=p['total']*returns[p['kind']]*ramp/(1-.2)
  rev=opex+da+ebit
 else:ebit=rev-opex-da
 return dict(name=p['name'],spend=spend,full_cost=p['total']*c['overrun'],ramp=ramp,revenue=rev,opex=opex,da=da,maintenance=maintenance,ebit=ebit,inner_owner=p['owner'])

def annual(state,year,c,method='operating'):
 t=year-2026; records={};parent_in=0.;parent_declare=0.;parent_inject=0.;common_income=0.;nci_profit=0.
 projs=[project_year(p,year,c,method) for p in PROJECTS]
 # UK project equity/loan commitments not included in consolidated plant capex. Net extra cash modeled separately below.
 for name,p0 in POOLS.items():
  p=dict(p0)
  if name!='Yalong':p['owner']+=c.get('pool_owner_delta',0.)
  s=state['subs'][name];olddebt=s['debt']
  if s.get('closed'):
   r=payment(s,0.,0.,0.,0.,0.,0.,0.,1.)
   r.update(asset_close=0.,economic_owner=p['owner'],extra_equity=0.,parent_receipt=0.,minority_cash=0.,closed=True)
   records[name]=r;continue
  if name=='Thermal' and year==c.get('exit_thermal'):
   r=liquidation(s,s['asset']*.65,s['asset'],2.)
   parent_receipt=(r['capital_return']+r['old_cash_paid'])*p['owner']
   parent_in+=parent_receipt;parent_inject+=r['equity_in']*p['owner']
   legal_gain=r['capital_return']*p['owner']-state['thermal_parent_basis']-r['equity_in']*p['owner']
   parent_declare+=legal_gain;common_income+=r['profit']*p['owner'];nci_profit+=r['profit']*(1-p['owner'])
   state['thermal_parent_basis']=0.
   r.update(parent_legal_disposal_gain=legal_gain,asset_close=0.,economic_owner=p['owner'],extra_equity=r['equity_in'],parent_receipt=parent_receipt,minority_cash=(r['capital_return']+r['old_cash_paid'])*(1-p['owner']))
   records[name]=r;continue
  cyc=c.get('cycle') and t<=3
  w=c['water']*(.88 if cyc and name=='Yalong' else .94 if cyc and name=='OtherHydro' else 1.)
  q=p['q']*(w if name in ['Yalong','OtherHydro'] else 1.)
  if c.get('structural') and name=='Thermal':q*=max(.70,1-.03*t)
  price=p['price']*c['price']*(c['renewprice'] if name=='Renewable' else 1.)
  revenue=q*price
  if name=='Yalong':revenue=86.7*w*.274*c['price']+1.*.366*c['price']*c['renewprice']+1.8*.282*c['price']*c['renewprice']
  if name=='Renewable':revenue=(6.*.385+7.8*.323)*c['price']*c['renewprice']
  variable=p['variable']*(c['coal']*(1.1 if cyc else 1.) if name=='Thermal' else 1.)
  cost=q*variable+p['fixed']
  if name=='Yalong':cost=86.7*w*.035+2.8*.04+p['fixed']
  da=p['da']*(1+(c['maint']-1)*min(t,15)/15)
  # Tax holidays at Lianghekou/Yangfanggou lapse: pooled Yalong normal cash tax 18% versus 2026 lower rate.
  interest=olddebt*(.025+c['spread'])
  # Independent capital method uses observed equity return and opening debt interest to infer unlevered earnings.
  ebit=revenue-cost-da
  if method=='capital':
   ebit=p['book']*p['roe']/(1-p['tax'])+p['debt']*.025
   ebit*= (w*c['price'] if name in ['Yalong','OtherHydro'] else c['renewprice'] if name=='Renewable' else 1.)
  group=[x for x in projs if next(z['pool'] for z in PROJECTS if z['name']==x['name'])==name]
  spend=sum(x['spend']*x['inner_owner'] for x in group)
  ebit+=sum(x['ebit']*x['inner_owner'] for x in group)
  da+=sum(x['da']*x['inner_owner'] for x in group)
  # Construction debt draw (70%); equity contribution 30%. Yagen2 minority funded by CATL separately.
  draw=sum(x['spend']*x['inner_owner']*(.8 if x['name']=='Yagen2' else .7) for x in group)
  injection=([2.5,3.,2.5,1.5,.6][t-1] if t<=5 else 0.) if name=='Yalong' else .3*spend
  # Existing net debt retirement of 2.5% initial debt each year; gross rollover separate, not full early repayment.
  repayment=min(s['debt'],p['debt']*.025 + max(0.,t-8)*.025)
  tax_rate=p['tax'] if year<=2030 else .25
  tax=max(0.,ebit-interest)*tax_rate;profit=ebit-interest-tax
  # Inner minority losses/receipts not blindly multiplied: project 90% already removed above.
  maint=(p['da']*(1+(c['maint']-1)*min(t,15)/15))*(.6+.4*min(t,15)/15)+sum(x['maintenance']*x['inner_owner'] for x in group)
  wc=.08*(revenue-p['q']*p['price']) if t==1 else 0.
  restricted_release=min(state['restricted'],4.308706518/5) if name=='Renewable' and 3<=t<=7 else 0.
  if name=='Renewable':state['restricted']-=restricted_release
  ocf=profit+da-wc+restricted_release
  capex=maint+spend
  # Funding follows cash deficits only after committed project funding; extra parent capital, not free cash.
  extra=max(0.,s['floor']+s['payable']-(s['cash']+ocf-capex+injection+draw-repayment))
  injection+=extra
  # Desire is 75% early, then 95% after projects mature; constrained by law and cash.
  desired=max(0.,profit)*(.75 if spend>0 else .95)
  # Gradual distribution of excess cash, always limited by legal RE, never a magic year-5 release.
  desired+=.5*max(0.,s['cash']-s['floor']-s['payable'])
  r=payment(s,profit,ocf,capex,injection,draw,repayment,desired,c['collect'])
  s['asset']+=capex-da
  s['other_net_assets']+=wc-restricted_release
  # Continuing operations retain paid capital and reserves; no forecast capital reduction.
  capital_return=0.
  r.update(revenue=revenue,operating_cash_cost=cost,depreciation=da,interest=interest,tax=tax,maintenance=maint,growth_capex=spend,
           wc_change=wc,restricted_release=restricted_release,other_net_assets_close=s['other_net_assets'],asset_close=s['asset'],economic_owner=p['owner'],extra_equity=extra,
           parent_receipt=(r['current_cash_paid']+r['old_cash_paid']+capital_return)*p['owner'],minority_cash=(r['current_cash_paid']+r['old_cash_paid'])*(1-p['owner']),
           gross_debt_rollover=olddebt*.2)
  records[name]=r
  state['cost_basis']-=capital_return*p['owner']
  if name=='Thermal':state['thermal_parent_basis']+=(injection-capital_return)*p['owner']
  parent_in+=r['parent_receipt'];parent_declare+=r['declared']*p['owner'];parent_inject+=injection*p['owner']
  common_income+=profit*p['owner'];nci_profit+=profit*(1-p['owner'])
 # Batang: amortizing PPP concession, no terminal perpetuity/principal add-on. Economic share 93.33%*75%.
 s=state['ppp'];ppp_owner=.9333*.75;rec0=s['receivable']; debt0=s['debt']
 addition=.8 if t==1 else 0.
 principal=min(rec0,12.3/30) if 2<=t<=31 else 0.
 accrued=rec0*.065 if t<=31 else 0.
 income_tax=0. if t<=15 else (.11 if t<=17 else .22)
 interest=debt0*(.045+c['spread']);profit=accrued-interest
 tax=max(0.,profit)*income_tax;profit-=tax
 debtpay=min(debt0,8.56/20) if t>=2 else 0.
 draw=addition*.7;equity=addition*.3
 ocf=profit+principal # net operating fee equals operations & maintenance budget; no extra energy profit added
 extra=max(0.,s['floor']+s['payable']-(s['cash']+ocf-addition+draw+equity-debtpay));equity+=extra
 state['ppp_parent_basis']+=equity*ppp_owner
 if t==33:
  # Finite project liquidates after contractual operating term and handover; no expense truncation.
  r=liquidation(s,0.,s['receivable'],c.get('ppp_exit_cost',.2))
  profit=r['profit'];equity=r['equity_in'];state['ppp_parent_basis']+=equity*ppp_owner
  capital_return=r['capital_return']
  legal_gain=capital_return*ppp_owner-state['ppp_parent_basis']
  parent_declare+=legal_gain;state['ppp_parent_basis']=0.
  r['parent_legal_disposal_gain']=legal_gain
 else:
  r=payment(s,profit,ocf,addition,equity,draw,debtpay,max(0.,profit+principal-debtpay),c['collect'])
  capital_return=0.
 s['receivable']+=addition-principal
 r.update(receivable_open=rec0,receivable_close=s['receivable'],principal_collected=principal,finance_income=accrued,interest=interest,tax=tax,economic_owner=ppp_owner,minority_cash=(r['current_cash_paid']+r['old_cash_paid']+capital_return)*(1-ppp_owner))
 parent_in+=(r['current_cash_paid']+r['old_cash_paid']+capital_return)*ppp_owner
 parent_declare+=r['declared']*ppp_owner
 parent_inject+=equity*ppp_owner;common_income+=profit*ppp_owner;nci_profit+=profit*(1-ppp_owner)
 records['BatangPPP']=r
 # Associates excluding ICOHL: cash retention earns 4%, and surplus is gradually paid out.
 assoc_profit=.65*(.8 if c.get('structural') else 1.)+max(0.,state['investments']-10.047435093)*.04
 assoc_cash=assoc_profit*(.75 if t<=10 else .95 if t<=20 else 1.)
 state['investments']+=assoc_profit-assoc_cash
 # ICOHL loan: 364.613m GBP cap at budget 9 CNY/GBP, separate from old ICOL balance.
 # New drawing 2027/28 is 90% cap, remainder available but not assumed drawn. Historical old ICOL loan is separate.
 uk_equity=.25*c.get('fx',1.) if t<=2 else 0.
 uk_loan=(3.281517103*.9/2*c.get('fx',1.)) if t<=2 else 0.
 newloan0=state.get('uk_new_loan_balance',0.)
 contract_interest=newloan0*.08
 # Cash interest begins after operation/debt service: 60% of contractual cash, 40% accrues.
 loan_interest=contract_interest*(.4 if c.get('structural') else .6) if t>=4 and year<=2049 else 0.
 state['loan_accrual']+=(contract_interest-loan_interest)*.8 if year<=2049 else 0.
 loan_repay=0.;loan_loss=0.
 if year==2049:
  recovery=.5 if c.get('structural') else .8
  loan_repay=newloan0*recovery
  loan_loss=newloan0-loan_repay+state['loan_accrual']
  state['loan_accrual']=0.
  state['uk_new_loan_balance']=0.
 else:state['uk_new_loan_balance']=newloan0+uk_loan
 old_loan_receipt=state['loans']*.7 if t==10 else 0.
 old_loan_loss=state['loans']*.3 if t==10 else 0.
 if t==10:state['loans']=0.
 # Existing Lestari loan separately amortizes over 5 years, no repeated recognition of principal.
 other_loan_receipt=min(state['old_other_loan'],.187660108/5) if t<=5 else 0.
 state['old_other_loan']-=other_loan_receipt
 # UK equity budget: after lender service at project level, modest 0.12bn attributable distributable earnings.
 # No contract interest or principal counted in this equity earning stream.
 uk_profit=max(0.,min(1.,(t-2)/3))*.12*c.get('fx',1.)*(.5 if c.get('structural') else 1.) if year<=2057 else 0.
 uk_dividend=uk_profit*.6
 state['uk_equity_basis']+=uk_equity+uk_profit-uk_dividend
 state['uk_equity_legal_cost']+=uk_equity;state['uk_parent_cost']+=uk_equity+uk_loan
 # Controlled exit at lease/equipment renewal horizon; independent sale/recovery with old liabilities netted.
 uk_exit_cash=0.;uk_exit_gain=0.;uk_realized_exit_gain=0.
 if year==2058:
  uk_exit_cash=(1.5-.2-.35-.15)*c.get('uk_exit_factor',1.)*c.get('fx',1.)*(.5 if c.get('structural') else 1.) # attributable equipment/remaining-lease sale less bank, lease settlement and dismantling/staff; budgets, not legal date
  uk_exit_gain=uk_exit_cash-state['uk_equity_basis'];state['uk_equity_basis']=0.
  uk_realized_exit_gain=uk_exit_cash-state['uk_equity_legal_cost'];state['uk_equity_legal_cost']=0.
 # Loan cash taxed at 20%; accrued contract income recognized then losses reverse it, cash never double counted.
 net_cash_interest=loan_interest*.8
 new_loan_accrued_net=contract_interest*.8 if year<=2049 else 0.
 uk_hold_profit=uk_profit+new_loan_accrued_net-loan_loss-old_loan_loss+uk_exit_gain
 uk_hold_cash=uk_dividend+net_cash_interest+loan_repay+old_loan_receipt+other_loan_receipt+uk_exit_cash
 us=state['ukhold']
 uk_realized_profit=uk_dividend+net_cash_interest-(newloan0-loan_repay if year==2049 else 0.)-old_loan_loss+uk_realized_exit_gain
 ur=payment(us,uk_realized_profit,uk_hold_cash,uk_equity+uk_loan,uk_equity+uk_loan,0.,0.,uk_hold_cash,.9)
 # Repaid loan principal is an asset realization, not profit.
 # No invented UK capital reduction; residual cash is constrained by realized RE.
 uk_capital_return=0.
 if year==c.get('uk_winddown',2059):
  # Conditional wind-down of this finite asset ring, not shutdown of the entire UK platform.
  ur=liquidation(us,0.,0.,.05)
  uk_capital_return=ur['capital_return'];uk_hold_profit-=.05
  parent_declare+=uk_capital_return-state['uk_parent_cost']-ur['equity_in']
  state['uk_parent_cost']=0.;parent_inject+=ur['equity_in']
 ur.update(capital_return=uk_capital_return,cash_close=us['cash'],loan_assets=state['uk_new_loan_balance']+state['loans']+state['old_other_loan'],interest_receivable=state['loan_accrual'],equity_basis=state['uk_equity_basis'],equity_legal_cost=state['uk_equity_legal_cost'],parent_holding_cost=state['uk_parent_cost'])
 records['UKHolding']=ur
 parent_in+=assoc_cash+ur['current_cash_paid']+ur['old_cash_paid']+uk_capital_return
 parent_declare+=assoc_cash+ur['declared']
 common_income+=assoc_profit+uk_hold_profit
 # Parent interest and perpetual coupons deducted exactly once. Perpetual principal refinancing, not common-equity asset.
 p=state['parent'];interest=p['debt']*(.028+c['spread']);coupon=state.get('perpetual_balance',5.599433962)*(.026+c['spread'])
 perpetual_redemption=state.get('perpetual_balance',5.599433962) if year==c.get('perpetual_redeem') else 0.
 if perpetual_redemption:state['perpetual_balance']=0.
 overhead=.24
 pp=parent_declare-overhead-interest-coupon
 common_income-=overhead+interest+coupon
 mandatory=parent_inject+uk_equity+uk_loan+perpetual_redemption
 state['earmarked']=max(0.,state['earmarked']-records['Yalong']['equity_in']*.52)
  # Dedicated issue proceeds remain in the cash floor until actually applied to Yalong capital.
 p['floor']=1.+state['earmarked']
 amort=min(p['debt'],.20 if t<=10 else .40)
 netcash=parent_in-overhead-interest-coupon
 need=max(0.,p['floor']-(p['cash']+netcash-mandatory-amort))
 draw,issue,added_shares=financing(need,'debt',capacity=max(0.,30.-p['debt']+amort))
 assert issue==0 and added_shares==0
 # Financing is an explicit facility budget, not guaranteed state backing.
 if p['debt']+draw-amort>30.:raise ValueError(('parent facility exceeded',year,p['debt']+draw-amort))
 desired=max(0.,state['previous_common_profit'])*(.55 if mandatory>0 else .95)
 desired+=.5*max(0.,p['cash']-p['floor'])
 if draw>1e-9:desired=0. # don't borrow to pay common dividends
 pr=payment(p,pp,netcash,mandatory,0.,draw,amort,desired,1.)
 # cash parent investment purchases are capitalized, not parent P&L; dividends classified by declaration.
 prior_ar=state['ar'];new_ar=prior_ar+sum(records[n]['declared']*records[n]['economic_owner'] for n in POOLS)-sum((records[n]['current_cash_paid']+records[n]['old_cash_paid'])*records[n]['economic_owner'] for n in POOLS)
 state['ar']=new_ar
 pr.update(upstream_cash=parent_in,subsidiary_declarations=parent_declare,equity_to_subs=parent_inject,uk_equity=uk_equity,uk_new_loan=uk_loan,
           loan_principal_collected=loan_repay,uk_contract_interest=contract_interest,uk_cash_interest=loan_interest,uk_loan_loss=loan_loss,uk_old_loan_recovery=old_loan_receipt,uk_equity_profit=uk_profit,uk_equity_dividend=uk_dividend,uk_exit_cash=uk_exit_cash,uk_exit_gain=uk_exit_gain,earmarked_remaining=state['earmarked'],interest=interest,perpetual_coupon=coupon,perpetual_principal=state.get('perpetual_balance',5.599433962),perpetual_redemption=perpetual_redemption,
           perpetual_gross_refinance=state.get('perpetual_balance',5.599433962) if t in [1,3] or t>3 and t%5==3 else 0.,overhead=overhead,
           ordinary_profit=common_income,minority_profit=nci_profit,dividend_per_share=pr['current_cash_paid']/state['shares'],shares=state['shares'],
           dividend_ar_open=prior_ar,dividend_ar_close=new_ar)
 state['previous_common_profit']=common_income
 # Ring-fenced pool accounting closes: retained reserves are backed by actual modeled net assets.
 for pool_state in state['subs'].values():
  near(pool_state['capital']+pool_state['reserve']+pool_state['re']+pool_state.get('capital_surplus',0.),pool_state['cash']+pool_state['asset']+pool_state['other_net_assets']-pool_state['debt']-pool_state['payable'])
 # Shares unchanged in all live cases: authorized no new issue assumption; deficit financed by bounded facility.
 for z in records.values():
  near(z['cash_close'],z['cash_open']+z['ocf']-z['capex']+z['equity_in']+z['new_debt']-z['principal_paid']-z['current_cash_paid']-z['old_cash_paid']-z.get('capital_return',0.))
 return dict(year=year,subsidiaries=records,projects=projs,parent=pr)

def simulate(c,method='operating',state=None,start=2027,end=2426):
 s=initial(c) if state is None else copy.deepcopy(state);out=[];state5=None
 for yr in range(start,end+1):
  row=annual(s,yr,c,method);out.append(row)
  if yr==2031:state5=copy.deepcopy(s)
 return out,s,state5

def value(rows,rate,origin=2026):return sum(r['parent']['dividend_per_share']/(1+rate)**(r['year']-origin) for r in rows)

def fixtures():
 out={}
 # negative prior RE is made good before statutory appropriation.
 near(law(-4.,0.,10.,3.)[0],-1.);near(law(-4.,0.,10.,3.)[1],0.)
 near(law(-4.,0.,10.,6.)[0],1.8);near(law(-4.,0.,10.,6.)[1],.2)
 near(law(0.,4.9,10.,4.)[1],5.)
 s=dict(cash=10.,debt=2.,capital=10.,reserve=0.,re=-4.,floor=1.,payable=3.)
 a=payment(s,6.,6.,2.,0.,0.,1.,9.,.5)
 near(a['declared'],1.8);near(a['current_cash_paid'],.9);near(a['old_cash_paid'],3.);near(s['cash'],9.1)
 out['loss_first_old_payable']=a
 # Equity financing changes capital/reserve threshold and contributes cash, not earnings.
 s=dict(cash=1.,debt=0.,capital=2.,reserve=1.,re=0.,floor=1.,payable=0.)
 a=payment(s,2.,2.,4.,4.,0.,0.,2.,1.)
 near(a['reserve_transfer'],.2);near(a['declared'],1.8);near(s['capital'],6.)
 out['capital_contribution']=a
 # Explicit share issuance fixture through a separate primitive: no buyback or dividend on same financing deficit.
 cash,shares=1.,2.
 draw,raised,added=financing(3.,'equity',1.5)
 ss=dict(cash=cash,debt=0.,capital=2.,reserve=1.,re=0.,floor=1.,payable=0.)
 rr=payment(ss,0.,0.,0.,raised,draw,0.,0.,1.)
 shares+=added
 near(ss['cash'],4.);near(shares,4.);near(raised/shares,.75);near(draw,0.)
 out['dilution_fixture']=dict(payment=rr,shares=shares)
 ss=dict(cash=2.,debt=5.,capital=5.,reserve=0.,re=1.,floor=0.,payable=1.,asset=10.)
 ll=liquidation(ss,7.,10.,1.)
 near(ll['capital_return'],2.);near(ll['profit'],-4.);near(ll['equity_in'],0.)
 out['liquidation_fixture']=ll
 ss=dict(cash=.1,debt=2.,capital=1.,reserve=.2,re=-3.6,floor=0.,payable=.5,asset=0.,other_net_assets=0.)
 ll=liquidation(ss,0.,0.,1.)
 near(ll['equity_in'],3.4);near(ll['profit'],-1.);near(ll['capital_return'],0.)
 out['cash_deficient_exit']=ll
 returned=out['liquidation_fixture']['capital_return']
 near(returned,2.);near(returned*.699975+returned*(1-.699975),returned)
 out['minority_principal_return']=dict(total=returned,ordinary=returned*.699975,minority=returned*(1-.699975))
 # Inner economic ownership 90% x52%, minority 10% +90%x48% =53.2%.
 near(.9*.52,.468);near(.1+.9*.48,.532)
 out['ownership_fixture']=dict(common=.468,minority=.532)
 near(law(0.,0.,10.,2.,0.,0.)[0],2.)
 near(law(0.,1.9,10.,2.,.1,.2)[1],2.)
 out['jurisdiction_fixture']=dict(UK_no_CN_reserve=True,Indonesia_cap=.2)
 return out

def main():
 f=fixtures();paths={};summaries={};states={}
 for name,c in CASES.items():
  rows,end,s5=simulate(c);paths[name]=rows;states[name]=s5
  v=value(rows,c['rate']);pv5=value(rows[:5],c['rate'])
  summaries[name]=dict(value_per_share=v,first5=[r['parent']['dividend_per_share'] for r in rows[:5]],tail_pv_share=(v-pv5)/v,
                       terminal5_ownpath=value(rows[5:],c['rate'],2031),last_common_cash=rows[-1]['parent']['current_cash_paid'],
                       numerical_omitted_pv_bound=100/(1+c['rate'])**YEARS/c['rate'],end_state=end)
 # Independently anchored capital/earnings method shares actual payment conditions and rights, not main earnings.
 rows,end,_=simulate(CASES['base'],'capital');paths['capital_crosscheck']=rows
 summaries['capital_crosscheck']=dict(value_per_share=value(rows,.08),first5=[r['parent']['dividend_per_share'] for r in rows[:5]])
 # TV branching starts from complete post-distribution base Y5, never a low/high historical path.
 terminal={};branch_states={}
 for label in ['core_low','core_high']:
  branch_states[label]=copy.deepcopy(states['base'])
  assert branch_states[label]==states['base']
  rows,end,_=simulate(CASES[label],state=branch_states[label],start=2032)
  paths['base5_then_'+label]=rows
  terminal[label]=value(rows,CASES[label]['rate'],2031)
  # simulate deep-copies the complete year-5 state; first branch opening cash is verified.
  near(rows[0]['parent']['cash_open'],states['base']['parent']['cash'])
  for pool in POOLS:near(rows[0]['subsidiaries'][pool]['cash_open'],states['base']['subs'][pool]['cash'])
 # Deterministic whole state identity printed for independent inspection.
 state5_bytes=json.dumps(states['base'],sort_keys=True,separators=(',',':')).encode()
 result=dict(units='CNY billion except per-share CNY; power billion kWh',share_count_billion=SHARES,
             source_facts=dict(Q3_common_net_assets=(74.47797378515-5.59943396227),Q3_CFO=19.98990901773,Q3_capex=11.46529339405,
                               H1_Yalong_assets=183.70286743304,H1_Yalong_liabilities=105.33579491691,H1_Yalong_netassets=78.36707251613,
                               H1_Yalong_parent_profit=2.19337306113/.48,H1_Yalong_common_profit=2.19337306113/.48*.52,
                               H1_Yalong_parent_equity=38.07092847011/.48,H1_Yalong_dividend_declared_to_parent=3.552/.48*.52,
                               H1_Yalong_dividend_received=3.552/.48*.52-1.248),
             assumptions=dict(pools=POOLS,projects=PROJECTS,cases=CASES),fixtures=f,summaries=summaries,
             terminal5_same_base=terminal,branch_opening_full_states=branch_states,base_year5_full_state=states['base'],base_year5_state_sha256=hashlib.sha256(state5_bytes).hexdigest(),
             annual_paths=paths)
 print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
