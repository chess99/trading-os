#!/usr/bin/env python3
"""Kedali 2026Q3 research budget. stdlib only. All amounts CNY billion, shares billion.
Legal-source budgets are estimates, NOT reported entity forecasts. No shared state.
"""
import json, math, copy
from pathlib import Path
SHARES=.286448468 # issued plus conservative unreported option exercise bound; no treasury cancellation
OPTION_SHARES=60126
OPTION_PROCEEDS=OPTION_SHARES*105.41/1e9
OWN={'P':1.,'H':1.,'J':1.,'D':.9902,'F':1.,'R':.444}
# H/J real legal entities with explicitly forecast balance budgets; D/F/R economic units.
# D: 98% wholly owned + 2% Sanli 51%; R: 60% Shenzhen 40% + 40% Thai 51%.
# These allocation weights are sensitivity-tested budgets, not legal ownership facts.
INITIAL={
 'P':dict(cash=.511524501,restricted=0.,retained=1.783852672,reserve=.137471634,capital=.286448468,debt=.016),
 'H':dict(cash=.30,restricted=0.,retained=0.,reserve=0.,capital=.5,debt=0.),
 'J':dict(cash=.20,restricted=0.,retained=0.,reserve=0.,capital=1.,debt=0.),
 'D':dict(cash=1.1669849113469388,restricted=1.10,retained=0.,reserve=0.,capital=3.,debt=.014444315),
 'F':dict(cash=.15,restricted=0.,retained=-.20,reserve=0.,capital=.5,debt=.038),
 'R':dict(cash=.1591271816530612,restricted=0.,retained=-.03,reserve=0.,capital=.2,debt=0.)}
CAP0={'P':1.7,'H':6.5,'J':5.5,'D':11.,'F':1.5,'R':.3}
REV0={'P':1.3,'H':5.5,'J':4.5,'D':8.7,'F':.75,'R':.05}
ADD={'P':[.05]*5,'H':[.8,.8,.7,.6,.5],'J':[.8,.8,.7,.6,.5],'D':[1.5,1.4,1.3,1.2,1.0],'F':[.25,.3,.3,.25,.2],'R':[.1,.1,.1,0,0]}
UTIL={'P':[.80,.82,.84,.85,.86],'H':[.87,.89,.90,.90,.90],'J':[.85,.87,.89,.90,.90],'D':[.82,.85,.87,.89,.90],'F':[.50,.55,.62,.68,.72],'R':[.20,.30,.40,.50,.55]}
# Operating cash contribution before fixed overhead and D&A; embeds materials, R&D, credit and supplier financing fees.
CONTR={'P':.24,'H':.215,'J':.18,'D':.18,'F':.25,'R':.30}
FIX={'P':.04,'H':.13,'J':.16,'D':.25,'F':.16,'R':.05}
DArate={'P':.025,'H':.035,'J':.04,'D':.04,'F':.055,'R':.06}
NWC={'P':.12,'H':.20,'J':.20,'D':.22,'F':.25,'R':.28}
LIMIT={'P':.8,'H':.3,'J':.5,'D':1.0,'F':.5,'R':.1}
SCENARIOS={
 'base':dict(util=0.,price=1.,contribution=0.,capmult=1.,nwc=0.,tax=.15,delay=0,rate=.04,payout=.38),
 'cyclical':dict(util=-.14,price=.96,contribution=-.015,capmult=.72,nwc=.04,tax=.15,delay=1,rate=.05,payout=.28),
 'structural':dict(util=-.16,price=.91,contribution=-.035,capmult=.50,nwc=.06,tax=.18,delay=2,rate=.055,payout=.20),
 'optimistic':dict(util=.04,price=1.01,contribution=.01,capmult=1.2,nwc=-.02,tax=.15,delay=0,rate=.04,payout=.42),
 'delay3':dict(util=0.,price=1.,contribution=0.,capmult=1.,nwc=0.,tax=.15,delay=3,rate=.04,payout=.38),
 'delay5':dict(util=0.,price=1.,contribution=0.,capmult=1.,nwc=0.,tax=.15,delay=5,rate=.04,payout=.38)}
for _a in ('D','F','R'): INITIAL[_a]['capital']=None

def operating_cash(revenue,capacity,contribution,fixed,da_rate,tax_rate,debt,rate,old_revenue,nwc_rate,growth,maintenance_factor=1):
 da=capacity*da_rate
 ebit=revenue*contribution-fixed-da
 interest=debt*rate
 tax=max(0.,ebit-interest)*tax_rate
 profit=ebit-interest-tax
 dnwc=(revenue-old_revenue)*nwc_rate
 maintenance=da*maintenance_factor
 cfo=profit+da-dnwc
 return dict(revenue=revenue,capacity=capacity,ebit=ebit,interest=interest,tax=tax,profit=profit,da=da,dnwc=dnwc,maintenance=maintenance,growth_capex=growth,cfo=cfo,fcfe=cfo-maintenance-growth)
def profit_legal(e,profit):
 if e.get('kind')=='economic':
  e['retained']+=profit
  return 0. # economic earnings capacity budget, NEVER statutory reserve

 old=e['retained']; e['retained']+=profit
 # prior losses must be made good before statutory reserve. Never truncate negative retained earnings.
 reserve=min(max(0.,profit+min(old,0.))*.10,max(0.,e['capital']*.5-e['reserve']))
 e['retained']-=reserve;e['reserve']+=reserve
 return reserve

def tax_budget(a,y,s):
 if s.get('old_tax',False):return .23 if a=='F' else .20 if a=='R' else s['tax']
 if a=='P':return .25
 if a=='F':return .23
 if a=='R':return .23
 if a=='D':return .20 if not s.get('nonrenewal') else .25
 return .25 if s.get('nonrenewal') and y>=2 else s['tax']

def simulate(name='base',years=5,overrides=None):
 s=dict(SCENARIOS[name]);s.update(overrides or {})
 E=copy.deepcopy(INITIAL);
 for a,e in E.items(): e['kind']='domestic' if a in ('P','H','J') else 'economic'
 E['P']['capital']=.286388342
 E['P']['shares']=.286388342
 capital_action(E['P'],0,-OPTION_SHARES/1e9,OPTION_SHARES/1e9,OPTION_PROCEEDS) # conditional exercise and registration
 cap=CAP0.copy();prev=REV0.copy();queue=[];rows=[];maxres=0
 # Remaining historical options assumed exercised at 105.41; cash and dilution booked together.
 for y in range(1,years+1):
  opening=sum(x['cash'] for x in E.values()); olddebt=sum(x['debt'] for x in E.values())
  # Explicit shareholder contributions support construction; not earnings and not group cash.
  supportF=([.25,.25,.20,.10,.05][y-1] if y<=5 else .02)
  supportF+=s.get('extra_supportF',0.) if y>=4 else 0.
  supportR=([.08,.08,.06,.03,.02][y-1] if y<=5 else .01)
  E['P']['cash']-=supportF+supportR;E['F']['cash']+=supportF;E['R']['cash']+=supportR
  E['F']['investment_basis'] = E['F'].get('investment_basis',0)+supportF;E['R']['investment_basis'] = E['R'].get('investment_basis',0)+supportR
  # Other shareholders match robot funding at their legal 49% share.
  robot_other=supportR*(1-OWN['R'])/OWN['R'];E['R']['cash']+=robot_other;E['R']['investment_basis']+=robot_other
  # Net settlement of existing intercompany trade payable: cash transfer only, not new expense/profit.
  settlement=s.get('settlement',0.) if y==1 else 0.
  E['P']['cash']-=settlement;E['H']['cash']+=settlement*.6;E['J']['cash']+=settlement*.4
  ops={};earnings=0;updecl=0;upcash=0;minor_paid=0;newdebt=0;repay=0;equity_minor=robot_other
  for k,e in E.items():
   if y<=5:
    factor=s['capmult'] if y>1 else 1. # already committed first-year construction honored
    add=ADD[k][y-1]*factor
    shock=s['util']*(1 if name=='structural' else (max(0,4-y)/3))
    u=max(.10,min(.95,UTIL[k][y-1]+shock))
    price=s['price'] if name=='structural' else (1+(s['price']-1)*max(0,4-y)/3)
   else:
    # Optional diagnostic only; formal valuation/solvency after Y5 uses terminal()'s shared actual cash path.
    g=.025 if name!='structural' else .01
    add=cap[k]*g;u=min(.90,UTIL[k][-1])+(s['util'] if name=='structural' else 0)
    price=s['price'] if name=='structural' else 1.
   cap[k]+=add
   rev=cap[k]*u*price
   # Full gross robot capex, 49% investor matching equity only for approved expansion; all other entities wholly owned.
   growth=add*(.6 if k not in ('F','R') else .85)
   if k=='R':
    pass # total parent/partner contributions already booked above
   release=min(e['restricted'],growth if k=='D' else 0.)
   e['restricted']-=release # converts project cash to spendable for this capital payment only
   contribution=CONTR[k]+s['contribution']
   if name=='cyclical' and y>=4:contribution=CONTR[k]
   o=operating_cash(rev,cap[k],contribution,FIX[k]*(1.025**(y-1)),DArate[k],tax_budget(k,y,s),e['debt'],s['rate'],prev[k],NWC[k]+s['nwc'],growth)
   prev[k]=rev
   # Interest on intra-year financing included; solve cash deficit including half-year tax-adjusted interest.
   e['cash']+=o['fcfe'];floor=rev*.025+e['restricted']+sum(q['amount'] for q in queue if q['entity']==k)
   if e['cash']<floor:
    needed=(floor-e['cash'])/(1-s['rate']*.5)
    if needed>LIMIT[k]*s.get('credit_factor',1)-e['debt']+1e-8:
     return dict(feasible=False,year=y,entity=k,shortfall=needed-(LIMIT[k]*s.get('credit_factor',1)-e['debt']),rows=rows)
    e['cash']+=needed;e['debt']+=needed;newdebt+=needed
    extra=needed*s['rate']*.5;e['cash']-=extra;o['interest']+=extra;o['profit']-=extra;o['fcfe']-=extra;o['cfo']-=extra
   reserve=profit_legal(e,o['profit'])
   earnings+=o['profit']*OWN[k]
   o['reserve_added']=reserve;o['opening_restricted_release']=release
   # H/J are the only demonstrated major profits available for upstream; D/F/R cash remains entity-owned.
   if k in ('H','J'):
    free=max(0.,e['cash']-floor)
    declaration=min(max(0,e['retained']),max(0.,o['profit'])*.65,free)
    e['retained']-=declaration
    queue.append(dict(due=y+s['delay'],amount=declaration,entity=k))
    updecl+=declaration
   ops[k]=o
  # declaration creates parent earnings once; delayed receivable is never counted twice.
  profit_legal(E['P'],updecl)
  for q in queue[:]:
   if q['due']<=y:
    k=q['entity'];amt=q['amount']
    # ring-fence payable amounts in subsidiaries; no spending declared dividends
    if E[k]['cash']+1e-9<amt:return dict(feasible=False,year=y,entity=k,shortfall=amt-E[k]['cash'],rows=rows)
    E[k]['cash']-=amt;E['P']['cash']+=amt;upcash+=amt;queue.remove(q)
  # Remaining declared payable cash cannot fund new declarations or be spent: reserve it for subsequent periods.
  # cap annual H/J declarations above must include all old payables in floor (checked in next year cash floor below).
  buyback=.17521234211 if y==1 else 0 # midpoint 225m less already paid 49.78765789m
  E['P']['cash']-=buyback
  if E['P']['cash']<0:
   need=-E['P']['cash']+.04
   if E['P']['debt']+need>LIMIT['P']*s.get('credit_factor',1):return dict(feasible=False,year=y,entity='P',shortfall=need,rows=rows)
   E['P']['cash']+=need;E['P']['debt']+=need;newdebt+=need
  desired=max(0.,earnings)*s['payout']
  div=min(desired,max(0,E['P']['retained']),max(0,E['P']['cash']-ops['P']['revenue']*.025))
  E['P']['cash']-=div;E['P']['retained']-=div
  # Debt amortization from surplus only, preserves declared unpaid dividends and project cash.
  for k,e in E.items():
   payable=sum(q['amount'] for q in queue if q['entity']==k)
   excess=max(0,e['cash']-e['restricted']-ops[k]['revenue']*.025-payable)
   pay=min(e['debt'],excess*.5);e['cash']-=pay;e['debt']-=pay;repay+=pay
   assert e['cash']>=-1e-8
   ops[k].update(budget_kind=e['kind'],capital=(e['capital'] if k in ('P','H','J') else None),cash=e['cash'],debt=e['debt'],retained=(e['retained'] if k in ('P','H','J') else None),economic_cumulative_profit_budget=(e['retained'] if k not in ('P','H','J') else None),reserve=(e['reserve'] if k in ('P','H','J') else None),restricted=e['restricted'],payable=payable)
  closing=sum(x['cash'] for x in E.values())
  expected=opening+sum(o['fcfe'] for o in ops.values())+newdebt-repay+equity_minor-div-buyback-minor_paid
  residual=closing-expected;maxres=max(maxres,abs(residual));assert abs(residual)<1e-7
  common_cash=sum(e['cash']*OWN[k] for k,e in E.items())
  common_debt=sum(e['debt']*OWN[k] for k,e in E.items())
  necessary=sum(ops[k]['revenue']*.025*OWN[k]+e['restricted']*OWN[k] for k,e in E.items())
  rows.append(dict(year=y,tax_rates={a:tax_budget(a,y,s) for a in E},pending_dividends=copy.deepcopy(queue),rate=s['rate'],extra_supportF=s.get('extra_supportF',0),domestic_tax=s['tax'],scenario=name,upstream_delay=s['delay'],revenue=sum(o['revenue'] for o in ops.values()),ebit=sum(o['ebit']*OWN[k] for k,o in ops.items()),common_profit=earnings,dividend=div,dps=div/SHARES,upstream_declared=updecl,upstream_cash=upcash,parent_receivable=sum(q['amount'] for q in queue),cash=closing,common_cash=common_cash,common_debt=common_debt,excess_common_cash=common_cash-necessary,net_excess=common_cash-necessary-common_debt,borrowed=newdebt,repaid=repay,buyback=buyback,minor_equity=equity_minor,parent_support_foreign=supportF,parent_support_robot=supportR,entities=ops,residual=residual))
 return dict(feasible=True,rows=rows,max_cash_residual=maxres,opening_cash=sum(e['cash'] for e in INITIAL.values())+OPTION_PROCEEDS,option_proceeds=OPTION_PROCEEDS,shares=SHARES)


# Continuation is an economic realizability budget, NOT a synthetic legal entity ledger.
# Annual operating cash produces after-reinvestment profits. Surplus vintages have a
# finite 1-7 year realization period; haircuts are real economic leakage budgets.
# No aggregate foreign/robot registered capital or statutory reserve is inferred.
def realization(gross,basis,fee_rate,tax_rate,ownership):
 fee=max(0,gross)*fee_rate
 taxable_gain=max(0,gross-fee-basis)
 tax=taxable_gain*tax_rate
 return {'gross':gross,'fee':fee,'taxable_gain':taxable_gain,'tax':tax,
         'basis_recovered':min(max(0,gross-fee),basis),
         'net_all_owners':gross-fee-tax,'common':(gross-fee-tax)*ownership,
         'minority':(gross-fee-tax)*(1-ownership)}

def terminal(row,k,g,roic,horizon=300,lag_extra=0,friction_extra=0,exit_year=3,exit_recovery=.35):
 E={a:dict(cash=e['cash'],debt=e['debt'],restricted=e['restricted'],revenue=e['revenue'],ebit=e['ebit']) for a,e in row['entities'].items()}
 # Pending dividends are internally eliminated: source cash is included once, parent's
 # receivable is NOT another asset. Settlement cannot create group/common earnings.
 # all H/J wholly owned; pending cash valuation keeps original due date lower bound.
 queue=[];history=[];pv=0;exited=set();initial={};maxres=0
 for q in row['pending_dividends']:
  E[q['entity']]['cash']-=q['amount']
  queue.append({'source':q['entity'],'born':0,'due':max(1,q['due']-5),'amount':q['amount'],'capital_fraction':0.,'exit':False})
 for a,e in E.items():
  initial[a]=max(0,e['cash']-e['restricted']-e['revenue']*.025-e['debt'])
 for t in range(1,horizon+1):
  start=sum(e['cash'] for e in E.values())+sum(q['amount'] for q in queue)
  operating=0;interest=0;borrowing=0;debtpay=0;exitgross=0;exitcost=0;holder=0;minority=0;friction=0;details={}
  growth=(([.01]*7 if row['scenario']=='structural' else [.065,.055,.045,.035,.03,.025,.025])[t-1] if t<=7 else g)
  for a,e in E.items():
   if a in exited:continue
   old=e['ebit'];e['ebit']*=1+growth;e['revenue']*=1+growth
   tr=row['tax_rates'][a]
   nopat=e['ebit']-max(0,e['ebit'])*tr;oldnopat=old-max(0,old)*tr
   inv=max(0,nopat-oldnopat)/roic
   intcash=e['debt']*row['rate'];interest+=intcash
   # positive taxable profits obtain interest shield; losses have no instant refund.
   tax=max(0,e['ebit']-intcash)*tr
   profit=e['ebit']-intcash-tax
   fcfe=profit-inv;e['cash']+=fcfe;operating+=fcfe
   floor=e['revenue']*.025+e['restricted']
   # stop permanent negative-EBIT businesses after finite restructuring budget.
   exitinfo=None
   if e['ebit']<0 and t==exit_year:
    # disposed operating assets = Y5 capacity x original cost intensity; only 35%
    # recovery, 10% closure cost, NWC recovered 50%. Forecast, not an appraisal.
    assets=row['entities'][a]['capacity']*(.85 if a in ('F','R') else .6)
    gross=assets*exit_recovery+row['entities'][a]['revenue']*NWC[a]*.5
    ex=realization(gross,assets,.10,.25,1.)
    e['cash']+=ex['net_all_owners'];exitgross+=gross;exitcost+=ex['fee']+ex['tax']
    floor=0;exitinfo=ex
   if e['cash']<floor:
    need=(floor-e['cash'])/(1-row['rate']*.5)
    limit=LIMIT[a]*e['revenue']/row['entities'][a]['revenue']
    if e['debt']+need>limit+1e-9:return {'feasible':False,'year_after_5':t,'entity':a,'shortfall':e['debt']+need-limit,'rows':history,'reason':'finite credit exhausted before realization'}
    e['cash']+=need;e['debt']+=need;borrowing+=need
    extra=need*row['rate']*.5;e['cash']-=extra;operating-=extra
   repay=min(e['debt'],max(0,e['cash']-floor));e['debt']-=repay;e['cash']-=repay;debtpay+=repay
   if exitinfo and e['debt']>1e-9:return {'feasible':False,'year_after_5':t,'entity':a,'shortfall':e['debt'],'reason':'exit does not repay all external debt','rows':history}
   surplus=max(0,e['cash']-floor)
   # Economic realization: profits can be dividends, capital may be returned through
   # approved reduction/disposal. Not an assertion all surplus is accounting income.
   if surplus:
    lag=({'P':1,'H':1,'J':1,'D':3,'F':5,'R':5}[a]+lag_extra)
    # Initial and every future surplus vintage gets a finite deadline. Cash parked in
    # pending realization is separately owned; no interest counted in either value.
    queue.append({'source':a,'born':t,'due':t+lag-1,'amount':surplus,'capital_fraction':min(1.,max(0,surplus-max(0,profit))/surplus),'exit':bool(exitinfo)})
    e['cash']-=surplus
   if exitinfo:exited.add(a);e['ebit']=0;e['revenue']=0;e['restricted']=0
   details[a]={'profit':profit,'tax':tax,'reinvestment':inv,'fcfe':fcfe,'interest':intcash,'surplus_earmarked':surplus,'cash':e['cash'],'debt':e['debt'],'floor':floor,'exit':exitinfo,'registered_capital':None,'statutory_reserve':None}
  for q in queue[:]:
   if q['due']<=t:
    a=q['source'];haircut=min(.9,{'P':0,'H':.02,'J':.02,'D':.05,'F':.15,'R':.15}[a]+friction_extra)
    # haircut includes all incremental cross-layer realization tax/fee and governance
    # friction; not a second corporation tax or claimed domestic withholding tax.
    realized=realization(q['amount'],q['amount']*q['capital_fraction'],haircut,0.,OWN[a])
    friction+=realized['fee'];holder+=realized['common'];minority+=realized['minority'];queue.remove(q)
  end=sum(e['cash'] for e in E.values())+sum(q['amount'] for q in queue)
  residual=end-(start+operating+borrowing-debtpay+exitgross-exitcost-holder-minority-friction)
  assert abs(residual)<1e-5
  maxres=max(maxres,abs(residual));pv+=holder/(1+k)**t
  history.append({'year_after_5':t,'growth':growth,'economic_common_realization':holder,'minority_realization':minority,'realization_friction':friction,'operating_fcfe':operating,'debt_raised':borrowing,'debt_repaid':debtpay,'exit_gross':exitgross,'exit_cost_tax':exitcost,'cash_and_pending':end,'pending':copy.deepcopy(queue),'entities':details,'residual':residual})
 tail=history[-1]['economic_common_realization']*(1+g)/(k-g)/(1+k)**horizon
 return {'feasible':True,'per_share':(pv+tail)/SHARES,'economic_realization_pv':pv,'steady_component':tail,'rows':history,'max_cash_residual':maxres,'initial_excess':initial,'exited':sorted(exited),'horizon':horizon,'terminal_cash_double_add':0,'interpretation':'conditional economic realizability budget, NOT forecast legal dividends','last_growth':history[-1]['economic_common_realization']/history[-2]['economic_common_realization']-1}

def valuation(sim,k=.10,g=.02,roic=.14,**kw):
 if not sim['feasible']:return {'feasible':False,'reason':'explicit period funding failure'}
 tv=terminal(sim['rows'][4],k,g,roic,**kw)
 if not tv['feasible']:return {'feasible':False,'terminal':tv}
 d=sum(r['dps']/(1+k)**r['year'] for r in sim['rows'])
 return {'feasible':True,'value':d+tv['per_share']/(1+k)**5,'distribution_pv':d,'terminal_pv':tv['per_share']/(1+k)**5,'terminal':tv}

def capital_action(state,cash_paid,shares_retired,registration_change,cash_received=0):
 # Production capital-event primitive, including no-cash conversion and paid reductions.
 if cash_paid>state['cash']+1e-10:raise ValueError('unfunded reduction')
 state['cash']+=cash_received-cash_paid;state['shares']-=shares_retired;state['capital']+=registration_change
 assert state['shares']>=0 and state['capital']>=0
 return state

def tests():
 checks={}
 e={'retained':0.,'reserve':5.,'capital':20.,'paid':10.};assert profit_legal(e,10)==1;checks['registered20_paid10_reserve5_profit10']=e
 e={'retained':-5.,'reserve':0.,'capital':20.};assert profit_legal(e,3)==0 and e['retained']==-2;assert abs(profit_legal(e,4)-.2)<1e-12;checks['loss_before_reserve']=e
 e={'retained':0.,'reserve':10.,'capital':20.};assert profit_legal(e,10)==0
 capital_action(e|{'cash':0,'shares':20},0,0,4)
 z=capital_action({'cash':10.,'shares':100.,'capital':20.},2.,10.,-2.)
 assert z=={'cash':8.,'shares':90.,'capital':18.};checks['paid_reduction_shares_and_cash']=z
 c={'cash':0,'shares':100,'capital':20};capital_action(c,0,0,4);assert c['cash']==0 and c['capital']==24
 e={'retained':0.,'reserve':10.,'capital':24.};assert profit_legal(e,10)==1;checks['conversion_registration_after_effective']=e
 # Principal recovery can be positive even with accounting loss; basis is not income.
 r=realization(10,10,.1,.25,.4);assert r['tax']==0 and abs(r['common']-3.6)<1e-12 and abs(r['minority']-5.4)<1e-12
 checks['principal_realization_without_profit']=r
 r=realization(15,10,.1,.25,.51);assert r['tax']==.875 and abs(r['common']-6.43875)<1e-12
 checks['fees_gain_tax_and_minority_once']=r
 b=simulate('base');d=simulate('delay5')
 for i in range(5):
  x=b['rows'][i]['entities']['P']['retained']+sum(v['dividend'] for v in b['rows'][:i+1])
  y=d['rows'][i]['entities']['P']['retained']+sum(v['dividend'] for v in d['rows'][:i+1])
  assert abs(x-y)<1e-8
 checks['old_receivable_no_second_profit']=True
 fail=simulate('structural',overrides={'credit_factor':0,'payout':0,'util':-.65});assert not fail['feasible'];checks['zero_dividend_no_invented_funding']={k:v for k,v in fail.items() if k!='rows'}
 x=operating_cash(100,100,.3,5,.1,.2,20,.1,80,.2,7);assert abs(x['fcfe']+.6)<1e-10
 checks['operating_manual_fcfe']=x
 # same production terminal function: raising only starting surplus by1 gives only
 # discounted realized principal, not capitalized interest or second cash add.
 row=copy.deepcopy(b['rows'][4]);v=terminal(row,.1,.02,.14)
 row['entities']['D']['cash']+=1.;w=terminal(row,.1,.02,.14)
 delta=w['per_share']-v['per_share'];expected=.95*OWN['D']/SHARES/(1.1)**3
 assert abs(delta-expected)<1e-8;(checks.update(principal_single_count_delta=delta,principal_single_count_expected=expected))
 # Failure counterexample: negative exit recovery cannot discharge debt.
 bad=copy.deepcopy(b['rows'][4]);bad['entities']['F'].update(cash=0.,debt=.49,ebit=-.01)
 q=terminal(bad,.1,.02,.14,exit_year=1,exit_recovery=0)
 assert not q['feasible'];checks['exit_failure_external_debt']=q.get('reason')
 return checks

def _brief(v):
 if not v.get('feasible'):return {'feasible':False,'reason':v.get('reason') or v.get('terminal',{}).get('reason')}
 return {'feasible':True,'value':v['value'],'distribution_pv':v['distribution_pv'],'tv5':v['terminal']['per_share'],'terminal_pv_share':v['terminal_pv']/v['value']}

def main():
 import gzip,base64,hashlib,sys
 p=Path(__file__).parent
 if '--expand' in sys.argv:
  packet=json.loads((p/'2026-Q3-output.json').read_text());raw=gzip.decompress(base64.b64decode(packet['payload_gzip_base64']))
  assert hashlib.sha256(raw).hexdigest()==packet['expanded_sha256']
  (p/'2026-Q3-expanded.json').write_bytes(raw);return
 paths={n:simulate(n) for n in SCENARIOS}
 paths['structural_supported']=simulate('structural',overrides={'extra_supportF':.12,'capmult':.3,'payout':.1})
 paths['nonrenewal']=simulate('base',overrides={'nonrenewal':True})
 paths['margin_minus_1pp']=simulate('base',overrides={'contribution':-.01})
 paths['settlement']=simulate('base',overrides={'settlement':.5})
 saved_losses={a:INITIAL[a]['retained'] for a in ('H','J')}
 for a in ('H','J'):INITIAL[a]['retained']=-.5
 paths['HJ_open_loss_500m_each']=simulate('base')
 for a in ('H','J'):INITIAL[a]['retained']=saved_losses[a]
 saved_reserve=INITIAL['P']['reserve'];INITIAL['P']['reserve']=0.
 paths['parent_statutory_zero']=simulate('base');INITIAL['P']['reserve']=saved_reserve
 core={'low':valuation(paths['base'],.105,.02,.13),'high':valuation(paths['base'],.095,.025,.16)}
 values={n:valuation(s,.10,.01 if n.startswith('structural') else .02,.10 if n.startswith('structural') else .14) for n,s in paths.items()}
 values['lag_plus2']=valuation(paths['base'],lag_extra=2)
 values['friction_plus5pp']=valuation(paths['base'],friction_extra=.05)
 ownership_sensitivity={}
 saved_own=OWN.copy()
 for label,r,d in [('R40_D9755',.40,.9755),('R51_D100',.51,1.)]:
  OWN.update({'R':r,'D':d});z=simulate('base');ownership_sensitivity[label]={'path':z,'valuation':valuation(z)}
 OWN.update(saved_own)
 values['exit_recovery15pct']=valuation(paths['structural_supported'],g=.01,roic=.10,exit_recovery=.15)
 # Frozen old economic budgets -> remove pseudo statutory law -> change realization
 # method only -> separately change ownership, tax and matching minority contributions.
 old={};exec(OLD_SOURCE,old)
 oldpaths={n:old['simulate'](n) for n in SCENARIOS}
 oldpaths['structural_supported']=old['simulate']('structural',overrides={'extra_supportF':.12,'capmult':.3,'payout':.1})
 oldvalues={n:old['valuation'](v,.10,.01 if n.startswith('structural') else .02,.10 if n.startswith('structural') else .14) for n,v in oldpaths.items()}
 # Pure legal-accounting diagnostic: same operating, cash-release and tax budgets.
 # This stage alone retains old delayed-principal flaws and is NOT the final candidate.
 law_source=OLD_SOURCE.replace(" prior={a:e['ebit']", " for a,e in E.items():e['kind']='domestic' if a in ('P','H','J') else 'economic'\n prior={a:e['ebit']")
 law={};exec(law_source,law);law['profit_legal']=profit_legal
 for a in ('D','F','R'):law['INITIAL'][a]['kind']='economic'
 lawpaths={n:law['simulate'](n) for n in SCENARIOS}
 lawpaths['structural_supported']=law['simulate']('structural',overrides={'extra_supportF':.12,'capmult':.3,'payout':.1})
 lawvalues={n:law['valuation'](v,.10,.01 if n.startswith('structural') else .02,.10 if n.startswith('structural') else .14) for n,v in lawpaths.items()}
 saved=OWN.copy();OWN.update({'D':1.,'R':.51})
 bridgepaths={n:simulate(n,overrides={'old_tax':True}) for n in SCENARIOS}
 bridgepaths['structural_supported']=simulate('structural',overrides={'old_tax':True,'extra_supportF':.12,'capmult':.3,'payout':.1})
 bridgevalues={n:valuation(s,.10,.01 if n.startswith('structural') else .02,.10 if n.startswith('structural') else .14) for n,s in bridgepaths.items()}
 bridge=[]
 for n in oldpaths:
  ov=oldvalues[n];nv=bridgevalues[n];fv=values[n]
  bridge.append({'scenario':n,'old_value':None if not ov or not ov.get('terminal',{}).get('feasible') else ov['value'],'law_only_same_economics_value':None if not lawvalues[n] or not lawvalues[n].get('terminal',{}).get('feasible') else lawvalues[n]['value'],'finite_realization_frozen_operating_value':nv.get('value'),'new_economic_value':fv.get('value'),'old_D':[r['dps'] for r in oldpaths[n]['rows']],'finite_realization_frozen_operating_D':[r['dps'] for r in bridgepaths[n]['rows']],'new_D':[r['dps'] for r in paths[n]['rows']]})
 OWN.update(saved)
 convergence={}
 for label,case,k,g,roi in [('low',paths['base'],.105,.02,.13),('high',paths['base'],.095,.025,.16),('margin',paths['margin_minus_1pp'],.10,.02,.14),('structural',paths['structural_supported'],.10,.01,.10)]:
  convergence[label]={str(h):valuation(case,k,g,roi,horizon=h) for h in (200,300,400,500)}
  vals=[v['value'] for v in convergence[label].values() if v['feasible']];assert max(vals)-min(vals)<1e-5
  assert all(abs(v['terminal']['last_growth']-g)<1e-8 for v in convergence[label].values() if v['feasible'])
 r=paths['base']['rows'][0]
 netcash=sum(e['cash']*OWN[a] for a,e in INITIAL.items())-sum(e['restricted']*OWN[a] for a,e in INITIAL.items())-sum(REV0[a]*.025*OWN[a] for a in INITIAL)-sum(e['debt']*OWN[a] for a,e in INITIAL.items())-.17521234211+OPTION_PROCEEDS
 aux={'ebit1':r['ebit'],'net_cash':netcash,'low':(r['ebit']*8+netcash)/SHARES,'high':(r['ebit']*10+netcash)/SHARES}
 full={'units':'CNY billion; shares billion; per-share CNY','economic_ownership_weights':OWN,'scenarios':paths,'core':core,'values':values,'method_bridge':bridge,'law_only_paths':lawpaths,'law_only_values':lawvalues,'finite_realization_frozen_operating_paths':bridgepaths,'finite_realization_frozen_operating_values':bridgevalues,'old_paths':oldpaths,'old_values':oldvalues,'convergence':convergence,'tests':tests(),'auxiliary':aux,'ownership_sensitivity':ownership_sensitivity,'terminal_type':'economic realization capacity budget; not legal entity dividends'}
 raw=(json.dumps(full,ensure_ascii=False,separators=(',',':'))+'\n').encode()
 summary={'core':{a:_brief(v) for a,v in core.items()},'D':[r['dps'] for r in paths['base']['rows']],'values':{a:_brief(v) for a,v in values.items()},'bridge':bridge,'auxiliary':aux,'ownership_sensitivity':{a:_brief(v['valuation']) for a,v in ownership_sensitivity.items()}}
 packet={'schema':'kedali-economic-budget-v2','compression':'gzip+base64 lossless full annual records','expanded_sha256':hashlib.sha256(raw).hexdigest(),'expanded_bytes':len(raw),'summary':summary,'payload_gzip_base64':base64.b64encode(gzip.compress(raw,mtime=0)).decode()}
 data=(json.dumps(packet,ensure_ascii=False,separators=(',',':'))+'\n').encode();assert len(data)<16*1024*1024
 (p/'2026-Q3-output.json').write_bytes(data);(p/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(summary['core'],ensure_ascii=False))

OLD_SOURCE='#!/usr/bin/env python3\n"""Kedali 2026Q3 research budget. stdlib only. All amounts CNY billion, shares billion.\nLegal-source budgets are estimates, NOT reported entity forecasts. No shared state.\n"""\nimport json, math, copy\nfrom pathlib import Path\nSHARES=.286448468 # issued plus conservative unreported option exercise bound; no treasury cancellation\nOPTION_SHARES=60126\nOPTION_PROCEEDS=OPTION_SHARES*105.41/1e9\nOWN={\'P\':1.,\'H\':1.,\'J\':1.,\'D\':1.,\'F\':1.,\'R\':.51}\n# H Huizhou, J Jiangsu, D other domestic (ring fenced, no upstream), F foreign, R robot JV.\nINITIAL={\n \'P\':dict(cash=.511524501,restricted=0.,retained=1.783852672,reserve=.137471634,capital=.286448468,debt=.016),\n \'H\':dict(cash=.30,restricted=0.,retained=0.,reserve=0.,capital=.5,debt=0.),\n \'J\':dict(cash=.20,restricted=0.,retained=0.,reserve=0.,capital=1.,debt=0.),\n \'D\':dict(cash=1.1669849113469388,restricted=1.10,retained=0.,reserve=0.,capital=3.,debt=.014444315),\n \'F\':dict(cash=.15,restricted=0.,retained=-.20,reserve=0.,capital=.5,debt=.038),\n \'R\':dict(cash=.1591271816530612,restricted=0.,retained=-.03,reserve=0.,capital=.2,debt=0.)}\nCAP0={\'P\':1.7,\'H\':6.5,\'J\':5.5,\'D\':11.,\'F\':1.5,\'R\':.3}\nREV0={\'P\':1.3,\'H\':5.5,\'J\':4.5,\'D\':8.7,\'F\':.75,\'R\':.05}\nADD={\'P\':[.05]*5,\'H\':[.8,.8,.7,.6,.5],\'J\':[.8,.8,.7,.6,.5],\'D\':[1.5,1.4,1.3,1.2,1.0],\'F\':[.25,.3,.3,.25,.2],\'R\':[.1,.1,.1,0,0]}\nUTIL={\'P\':[.80,.82,.84,.85,.86],\'H\':[.87,.89,.90,.90,.90],\'J\':[.85,.87,.89,.90,.90],\'D\':[.82,.85,.87,.89,.90],\'F\':[.50,.55,.62,.68,.72],\'R\':[.20,.30,.40,.50,.55]}\n# Operating cash contribution before fixed overhead and D&A; embeds materials, R&D, credit and supplier financing fees.\nCONTR={\'P\':.24,\'H\':.215,\'J\':.18,\'D\':.18,\'F\':.25,\'R\':.30}\nFIX={\'P\':.04,\'H\':.13,\'J\':.16,\'D\':.25,\'F\':.16,\'R\':.05}\nDArate={\'P\':.025,\'H\':.035,\'J\':.04,\'D\':.04,\'F\':.055,\'R\':.06}\nNWC={\'P\':.12,\'H\':.20,\'J\':.20,\'D\':.22,\'F\':.25,\'R\':.28}\nLIMIT={\'P\':.8,\'H\':.3,\'J\':.5,\'D\':1.0,\'F\':.5,\'R\':.1}\nSCENARIOS={\n \'base\':dict(util=0.,price=1.,contribution=0.,capmult=1.,nwc=0.,tax=.15,delay=0,rate=.04,payout=.38),\n \'cyclical\':dict(util=-.14,price=.96,contribution=-.015,capmult=.72,nwc=.04,tax=.15,delay=1,rate=.05,payout=.28),\n \'structural\':dict(util=-.16,price=.91,contribution=-.035,capmult=.50,nwc=.06,tax=.18,delay=2,rate=.055,payout=.20),\n \'optimistic\':dict(util=.04,price=1.01,contribution=.01,capmult=1.2,nwc=-.02,tax=.15,delay=0,rate=.04,payout=.42),\n \'delay3\':dict(util=0.,price=1.,contribution=0.,capmult=1.,nwc=0.,tax=.15,delay=3,rate=.04,payout=.38),\n \'delay5\':dict(util=0.,price=1.,contribution=0.,capmult=1.,nwc=0.,tax=.15,delay=5,rate=.04,payout=.38)}\ndef operating_cash(revenue,capacity,contribution,fixed,da_rate,tax_rate,debt,rate,old_revenue,nwc_rate,growth,maintenance_factor=1):\n da=capacity*da_rate\n ebit=revenue*contribution-fixed-da\n interest=debt*rate\n tax=max(0.,ebit-interest)*tax_rate\n profit=ebit-interest-tax\n dnwc=(revenue-old_revenue)*nwc_rate\n maintenance=da*maintenance_factor\n cfo=profit+da-dnwc\n return dict(revenue=revenue,capacity=capacity,ebit=ebit,interest=interest,tax=tax,profit=profit,da=da,dnwc=dnwc,maintenance=maintenance,growth_capex=growth,cfo=cfo,fcfe=cfo-maintenance-growth)\ndef profit_legal(e,profit):\n old=e[\'retained\']; e[\'retained\']+=profit\n # prior losses must be made good before statutory reserve. Never truncate negative retained earnings.\n reserve=min(max(0.,profit+min(old,0.))*.10,max(0.,e[\'capital\']*.5-e[\'reserve\']))\n e[\'retained\']-=reserve;e[\'reserve\']+=reserve\n return reserve\n\ndef simulate(name=\'base\',years=5,overrides=None):\n s=dict(SCENARIOS[name]);s.update(overrides or {})\n E=copy.deepcopy(INITIAL);E[\'P\'][\'cash\']+=OPTION_PROCEEDS;cap=CAP0.copy();prev=REV0.copy();queue=[];rows=[];maxres=0\n # Remaining historical options assumed exercised at 105.41; cash and dilution booked together.\n for y in range(1,years+1):\n  opening=sum(x[\'cash\'] for x in E.values()); olddebt=sum(x[\'debt\'] for x in E.values())\n  # Explicit shareholder contributions support construction; not earnings and not group cash.\n  supportF=([.25,.25,.20,.10,.05][y-1] if y<=5 else .02)\n  supportF+=s.get(\'extra_supportF\',0.) if y>=4 else 0.\n  supportR=([.08,.08,.06,.03,.02][y-1] if y<=5 else .01)\n  E[\'P\'][\'cash\']-=supportF+supportR;E[\'F\'][\'cash\']+=supportF;E[\'R\'][\'cash\']+=supportR\n  E[\'F\'][\'capital\']+=supportF;E[\'R\'][\'capital\']+=supportR\n  # Other shareholders match robot funding at their legal 49% share.\n  robot_other=supportR*49/51;E[\'R\'][\'cash\']+=robot_other;E[\'R\'][\'capital\']+=robot_other\n  # Net settlement of existing intercompany trade payable: cash transfer only, not new expense/profit.\n  settlement=s.get(\'settlement\',0.) if y==1 else 0.\n  E[\'P\'][\'cash\']-=settlement;E[\'H\'][\'cash\']+=settlement*.6;E[\'J\'][\'cash\']+=settlement*.4\n  ops={};earnings=0;updecl=0;upcash=0;minor_paid=0;newdebt=0;repay=0;equity_minor=robot_other\n  for k,e in E.items():\n   if y<=5:\n    factor=s[\'capmult\'] if y>1 else 1. # already committed first-year construction honored\n    add=ADD[k][y-1]*factor\n    shock=s[\'util\']*(1 if name==\'structural\' else (max(0,4-y)/3))\n    u=max(.10,min(.95,UTIL[k][y-1]+shock))\n    price=s[\'price\'] if name==\'structural\' else (1+(s[\'price\']-1)*max(0,4-y)/3)\n   else:\n    # Optional diagnostic only; formal valuation/solvency after Y5 uses terminal()\'s shared actual cash path.\n    g=.025 if name!=\'structural\' else .01\n    add=cap[k]*g;u=min(.90,UTIL[k][-1])+(s[\'util\'] if name==\'structural\' else 0)\n    price=s[\'price\'] if name==\'structural\' else 1.\n   cap[k]+=add\n   rev=cap[k]*u*price\n   # Full gross robot capex, 49% investor matching equity only for approved expansion; all other entities wholly owned.\n   growth=add*(.6 if k not in (\'F\',\'R\') else .85)\n   if k==\'R\':\n    pass # total parent/partner contributions already booked above\n   release=min(e[\'restricted\'],growth if k==\'D\' else 0.)\n   e[\'restricted\']-=release # converts project cash to spendable for this capital payment only\n   contribution=CONTR[k]+s[\'contribution\']\n   if name==\'cyclical\' and y>=4:contribution=CONTR[k]\n   o=operating_cash(rev,cap[k],contribution,FIX[k]*(1.025**(y-1)),DArate[k],(.23 if k==\'F\' else .20 if k==\'R\' else s[\'tax\']),e[\'debt\'],s[\'rate\'],prev[k],NWC[k]+s[\'nwc\'],growth)\n   prev[k]=rev\n   # Interest on intra-year financing included; solve cash deficit including half-year tax-adjusted interest.\n   e[\'cash\']+=o[\'fcfe\'];floor=rev*.025+e[\'restricted\']+sum(q[\'amount\'] for q in queue if q[\'entity\']==k)\n   if e[\'cash\']<floor:\n    needed=(floor-e[\'cash\'])/(1-s[\'rate\']*.5)\n    if needed>LIMIT[k]*s.get(\'credit_factor\',1)-e[\'debt\']+1e-8:\n     return dict(feasible=False,year=y,entity=k,shortfall=needed-(LIMIT[k]*s.get(\'credit_factor\',1)-e[\'debt\']),rows=rows)\n    e[\'cash\']+=needed;e[\'debt\']+=needed;newdebt+=needed\n    extra=needed*s[\'rate\']*.5;e[\'cash\']-=extra;o[\'interest\']+=extra;o[\'profit\']-=extra;o[\'fcfe\']-=extra;o[\'cfo\']-=extra\n   reserve=profit_legal(e,o[\'profit\'])\n   earnings+=o[\'profit\']*OWN[k]\n   o[\'reserve_added\']=reserve;o[\'opening_restricted_release\']=release\n   # H/J are the only demonstrated major profits available for upstream; D/F/R cash remains entity-owned.\n   if k in (\'H\',\'J\'):\n    free=max(0.,e[\'cash\']-floor)\n    declaration=min(max(0,e[\'retained\']),max(0.,o[\'profit\'])*.65,free)\n    e[\'retained\']-=declaration\n    queue.append(dict(due=y+s[\'delay\'],amount=declaration,entity=k))\n    updecl+=declaration\n   ops[k]=o\n  # declaration creates parent earnings once; delayed receivable is never counted twice.\n  profit_legal(E[\'P\'],updecl)\n  for q in queue[:]:\n   if q[\'due\']<=y:\n    k=q[\'entity\'];amt=q[\'amount\']\n    # ring-fence payable amounts in subsidiaries; no spending declared dividends\n    if E[k][\'cash\']+1e-9<amt:return dict(feasible=False,year=y,entity=k,shortfall=amt-E[k][\'cash\'],rows=rows)\n    E[k][\'cash\']-=amt;E[\'P\'][\'cash\']+=amt;upcash+=amt;queue.remove(q)\n  # Remaining declared payable cash cannot fund new declarations or be spent: reserve it for subsequent periods.\n  # cap annual H/J declarations above must include all old payables in floor (checked in next year cash floor below).\n  buyback=.17521234211 if y==1 else 0 # midpoint 225m less already paid 49.78765789m\n  E[\'P\'][\'cash\']-=buyback\n  if E[\'P\'][\'cash\']<0:\n   need=-E[\'P\'][\'cash\']+.04\n   if E[\'P\'][\'debt\']+need>LIMIT[\'P\']*s.get(\'credit_factor\',1):return dict(feasible=False,year=y,entity=\'P\',shortfall=need,rows=rows)\n   E[\'P\'][\'cash\']+=need;E[\'P\'][\'debt\']+=need;newdebt+=need\n  desired=max(0.,earnings)*s[\'payout\']\n  div=min(desired,max(0,E[\'P\'][\'retained\']),max(0,E[\'P\'][\'cash\']-ops[\'P\'][\'revenue\']*.025))\n  E[\'P\'][\'cash\']-=div;E[\'P\'][\'retained\']-=div\n  # Debt amortization from surplus only, preserves declared unpaid dividends and project cash.\n  for k,e in E.items():\n   payable=sum(q[\'amount\'] for q in queue if q[\'entity\']==k)\n   excess=max(0,e[\'cash\']-e[\'restricted\']-ops[k][\'revenue\']*.025-payable)\n   pay=min(e[\'debt\'],excess*.5);e[\'cash\']-=pay;e[\'debt\']-=pay;repay+=pay\n   assert e[\'cash\']>=-1e-8\n   ops[k].update(capital=e[\'capital\'],cash=e[\'cash\'],debt=e[\'debt\'],retained=e[\'retained\'],reserve=e[\'reserve\'],restricted=e[\'restricted\'],payable=payable)\n  closing=sum(x[\'cash\'] for x in E.values())\n  expected=opening+sum(o[\'fcfe\'] for o in ops.values())+newdebt-repay+equity_minor-div-buyback-minor_paid\n  residual=closing-expected;maxres=max(maxres,abs(residual));assert abs(residual)<1e-7\n  common_cash=sum(e[\'cash\']*OWN[k] for k,e in E.items())\n  common_debt=sum(e[\'debt\']*OWN[k] for k,e in E.items())\n  necessary=sum(ops[k][\'revenue\']*.025*OWN[k]+e[\'restricted\']*OWN[k] for k,e in E.items())\n  rows.append(dict(year=y,pending_dividends=copy.deepcopy(queue),rate=s[\'rate\'],extra_supportF=s.get(\'extra_supportF\',0),domestic_tax=s[\'tax\'],scenario=name,upstream_delay=s[\'delay\'],revenue=sum(o[\'revenue\'] for o in ops.values()),ebit=sum(o[\'ebit\']*OWN[k] for k,o in ops.items()),common_profit=earnings,dividend=div,dps=div/SHARES,upstream_declared=updecl,upstream_cash=upcash,parent_receivable=sum(q[\'amount\'] for q in queue),cash=closing,common_cash=common_cash,common_debt=common_debt,excess_common_cash=common_cash-necessary,net_excess=common_cash-necessary-common_debt,borrowed=newdebt,repaid=repay,buyback=buyback,minor_equity=equity_minor,parent_support_foreign=supportF,parent_support_robot=supportR,entities=ops,residual=residual))\n return dict(feasible=True,rows=rows,max_cash_residual=maxres,opening_cash=sum(e[\'cash\'] for e in INITIAL.values())+OPTION_PROCEEDS,option_proceeds=OPTION_PROCEEDS,shares=SHARES)\n\ndef terminal(row,k,g,roic,horizon=300):\n """Same entity operating/capital path generates profits, financing and actual dividends.\n No separate automatic cash bridge. Opening principal remains on each cash ledger.\n """\n E={a:{q:e[q] for q in [\'cash\',\'debt\',\'retained\',\'reserve\',\'capital\',\'restricted\']} for a,e in row[\'entities\'].items()}\n prior={a:e[\'ebit\'] for a,e in row[\'entities\'].items()};rev={a:e[\'revenue\'] for a,e in row[\'entities\'].items()}\n pending=copy.deepcopy(row[\'pending_dividends\']);history=[];pv=0.;openprincipal={}\n for a,e in E.items():openprincipal[a]=max(0,e[\'cash\']-rev[a]*.025-e[\'restricted\']-sum(q[\'amount\'] for q in pending if q[\'entity\']==a))\n principal=openprincipal.copy();unlocked={a:0 if v<1e-12 else None for a,v in principal.items()};rate=row[\'rate\'];maxres=0.;ops_pv=0;principal_pv=0\n for t in range(1,horizon+1):\n  opening=sum(e[\'cash\'] for e in E.values());external_minority=0;minor_paid=0;taxwithheld=0;borrow=0;repaid=0;flows=0;up=0;details={}\n  gr=([.01]*7 if row[\'scenario\']==\'structural\' else [.065,.055,.045,.035,.03,.025,.025])[t-1] if t<=7 else g\n  # Structural overseas losses continue to consume legal parent equity; matching partner capital is not profit.\n  supportF=(.14 if row[\'scenario\']==\'structural\' else 0.)*(1+g)**(t-1)\n  if supportF:\n   E[\'P\'][\'cash\']-=supportF;E[\'F\'][\'cash\']+=supportF;E[\'F\'][\'capital\']+=supportF\n   supportR=.025*(1+g)**(t-1);partner=supportR*49/51\n   E[\'P\'][\'cash\']-=supportR;E[\'R\'][\'cash\']+=supportR+partner;E[\'R\'][\'capital\']+=supportR+partner;external_minority+=partner\n  for a,e in E.items():\n   oldebit=prior[a];ebit=oldebit*(1+gr);taxrate=.23 if a==\'F\' else .20 if a==\'R\' else row[\'domestic_tax\']\n   oldnopat=oldebit-max(oldebit,0)*taxrate;nopat=ebit-max(ebit,0)*taxrate\n   # Loss-making sites cannot finance negative reinvestment: retain maintenance and spend only on actual positive expansion.\n   investment=max(0,nopat-oldnopat)/roic\n   rev[a]*=1+gr;floor=rev[a]*.025+e[\'restricted\']\n   interest=e[\'debt\']*rate;profit=ebit-interest-max(ebit-interest,0)*taxrate\n   fcf=profit-investment;e[\'cash\']+=fcf;flows+=fcf\n   payable=sum(q[\'amount\'] for q in pending if q[\'entity\']==a)\n   if e[\'cash\']<floor+payable:\n    need=(floor+payable-e[\'cash\'])/(1-rate*.5)\n    credit=LIMIT[a]*rev[a]/row[\'entities\'][a][\'revenue\']\n    if e[\'debt\']+need>credit+1e-8:return dict(feasible=False,year_after_5=t,entity=a,shortfall=e[\'debt\']+need-credit,rows=history)\n    e[\'cash\']+=need;e[\'debt\']+=need;borrow+=need\n    extra=need*rate*.5;e[\'cash\']-=extra;profit-=extra;fcf-=extra;flows-=extra\n   reserve=profit_legal(e,profit)\n   debtpay=min(e[\'debt\'],max(0,e[\'cash\']-floor-payable));e[\'cash\']-=debtpay;e[\'debt\']-=debtpay;repaid+=debtpay\n   # New operating cash consumes legal distributable profits BEFORE old financial principal.\n   opdist=0;pd=0\n   if a!=\'P\':\n    free=max(0,e[\'cash\']-floor-payable)\n    opdist=min(max(0,fcf-debtpay),max(0,e[\'retained\']),free)\n    e[\'retained\']-=opdist;e[\'cash\']-=opdist\n    principal[a]=min(principal[a],max(0,e[\'cash\']-floor-payable))\n    unlock={\'H\':1,\'J\':1,\'D\':3,\'F\':5,\'R\':1}[a]\n    if t>=unlock:\n     pd=min(max(0,e[\'retained\']),max(0,e[\'cash\']-floor-payable))\n     e[\'retained\']-=pd;e[\'cash\']-=pd;principal[a]-=min(principal[a],pd)\n    gross=(opdist+pd)*OWN[a];withheld=gross*(.10 if a in (\'F\',\'R\') else 0)\n    minor_paid+=(opdist+pd)*(1-OWN[a]);taxwithheld+=withheld\n    received=gross-withheld;E[\'P\'][\'cash\']+=received;profit_legal(E[\'P\'],received);up+=received\n   details[a]=dict(ebit=ebit,profit=profit,reinvestment=investment,fcf=fcf,reserve_added=reserve,debt_paid=debtpay,operating_dividend=opdist,principal_dividend=pd)\n   prior[a]=ebit\n  # Old receivables were recognized before year five; settlement never repeats profit.\n  for q in pending[:]:\n   if q[\'due\']<=5+t:\n    E[q[\'entity\']][\'cash\']-=q[\'amount\'];E[\'P\'][\'cash\']+=q[\'amount\'];pending.remove(q)\n  parent=E[\'P\'];floor=rev[\'P\']*.025\n  latepay=min(parent[\'debt\'],max(0,parent[\'cash\']-floor));parent[\'debt\']-=latepay;parent[\'cash\']-=latepay;repaid+=latepay\n  dividend=min(max(0,parent[\'retained\']),max(0,parent[\'cash\']-floor))\n  parent[\'cash\']-=dividend;parent[\'retained\']-=dividend\n  principal[\'P\']=min(principal[\'P\'],max(0,parent[\'cash\']-floor))\n  close=sum(e[\'cash\'] for e in E.values())\n  residual=close-(opening+flows+borrow-repaid+external_minority-minor_paid-taxwithheld-dividend)\n  assert abs(residual)<1e-6;maxres=max(maxres,abs(residual))\n  assert all(e[\'cash\']>=-1e-8 for e in E.values())\n  for a,e in E.items():\n   details[a].update(e,principal_remaining=principal[a],revenue=rev[a])\n   if principal[a]<1e-12 and unlocked[a] is None:unlocked[a]=t\n  history.append(dict(year_after_5=t,operating_growth=gr,actual_holder_dividend=dividend,upstream_received=up,withholding=taxwithheld,minority_dividend=minor_paid,borrowing=borrow,debt_repayment=repaid,principal_remaining=principal.copy(),entities=details,residual=residual))\n  pv+=dividend/(1+k)**t\n # Terminal closure only after legal unlock and debt recovery are established in actual path.\n # Beyond year300 settled businesses grow at g; actual cash distribution already incorporates reinvestment, reserves, withholding.\n tail=history[-1][\'actual_holder_dividend\']*(1+g)/(k-g)/(1+k)**horizon\n unresolved=sum(principal.values())\n # Unreleased original principal is retained (not confiscated); upper bound separately reported.\n return dict(feasible=True,per_share=(pv+tail)/SHARES,actual_distributions_pv=pv,steady_component=tail,unreleased_original_principal=unresolved,unreleased_principal_upper_bound_per_share=sum(principal[a]*OWN[a] for a in principal)/SHARES,last_dividend_growth=history[-1][\'actual_holder_dividend\']/history[-2][\'actual_holder_dividend\']-1,closure_growth=g,initial_principal=openprincipal,original_principal_fully_released_or_reinvested_year=unlocked,rows=history,simulated_years=horizon,max_cash_residual=maxres)\n\ndef valuation(sim,k=.10,g=.02,roic=.14):\n if not sim[\'feasible\']:return None\n row=sim[\'rows\'][4];tv=terminal(row,k,g,roic)\n if not tv[\'feasible\']:return dict(feasible=False,terminal=tv)\n d=sum(r[\'dps\']/(1+k)**r[\'year\'] for r in sim[\'rows\'][:5]);tpv=tv[\'per_share\']/(1+k)**5\n return dict(value=d+tpv,distributions_pv=d,terminal_pv=tpv,terminal_share=tpv/(d+tpv),terminal=tv)\n\ndef tests():\n # Formal operating function manual fixture: EBIT=100*.3-5-10=15; interest=2; tax=2.6; NI10.4;\n # NWC growth=(100-80)*.2=4; CFO16.4; maintenance10 and growth7 => FCFE -0.6.\n z=operating_cash(100,100,.3,5,.1,.2,20,.1,80,.2,7)\n assert abs(z[\'fcfe\']-(-.6))<1e-10\n e=dict(retained=-5,reserve=0,capital=10)\n profit_legal(e,3);assert e[\'retained\']==-2 and e[\'reserve\']==0\n profit_legal(e,4);assert abs(e[\'retained\']-1.8)<1e-10 and abs(e[\'reserve\']-.2)<1e-10\n f=simulate(\'structural\',overrides=dict(credit_factor=0,payout=0,util=-.65))\n assert not f[\'feasible\'] # zero dividends cannot cure missing project/operating funds\n base=simulate(\'base\'); delayed=simulate(\'delay5\')\n # Declaration earnings, not cash receipt, drive legal retained earnings: same declarations and own operations.\n for i in range(5):\n  b=base[\'rows\'][i];d=delayed[\'rows\'][i]\n  blegal=b[\'entities\'][\'P\'][\'retained\']+sum(a[\'dividend\'] for a in base[\'rows\'][:i+1])\n  dlegal=d[\'entities\'][\'P\'][\'retained\']+sum(a[\'dividend\'] for a in delayed[\'rows\'][:i+1])\n  assert abs(blegal-dlegal)<1e-8\n assert delayed[\'rows\'][4][\'parent_receivable\']>0\n assert delayed[\'rows\'][4][\'entities\'][\'R\'][\'retained\']<0\n return dict(no_double_profit_on_old_receivable=True,delayed_principal_preserved=delayed[\'rows\'][4][\'parent_receivable\'],operating_manual_fcfe=z[\'fcfe\'],loss_carry_forward=e,finite_credit_zero_dividend_fail={k:v for k,v in f.items() if k!=\'rows\'})\n\ndef expand_output(data):\n """Resolve the four explicit 400-year prefix references; no numeric conversion."""\n import copy\n full=copy.deepcopy(data)\n for case in full.get(\'horizon_validation\',{}).values():\n  ext=case[\'extensions\']\n  if isinstance(ext[\'400\'][\'rows\'],dict):\n   assert ext[\'400\'][\'rows\']=={\'rows_from_extension\':\'500\',\'prefix_years\':400}\n   ext[\'400\'][\'rows\']=copy.deepcopy(ext[\'500\'][\'rows\'][:400])\n return full\n\ndef main():\n result={\'unit\':\'CNY billion except per share\',\'shares\':SHARES,\'definitions\':{\'P\':\'listed parent economic operations and legal payer\',\'H\':\'Huizhou wholly-owned manufacturing\',\'J\':\'Jiangsu wholly-owned manufacturing\',\'D\':\'other domestic ring-fenced budget, no upstream in explicit years\',\'F\':\'overseas wholly-owned aggregate, no upstream\',\'R\':\'robot project 51% parent ownership\'},\'initial\':INITIAL,\'scenarios\':{k:simulate(k) for k in SCENARIOS},\'tests\':tests()}\n result[\'scenarios\'][\'structural_supported\']=simulate(\'structural\',overrides={\'extra_supportF\':.12,\'capmult\':.3,\'payout\':.1})\n base=result[\'scenarios\'][\'base\'];result[\'core\']={\'low\':valuation(base,.105,.02,.13),\'high\':valuation(base,.095,.025,.16)}\n result[\'scenario_values\']={k:valuation(v,.10,.01 if k.startswith(\'structural\') else .02,.10 if k.startswith(\'structural\') else .14) for k,v in result[\'scenarios\'].items()}\n sensitivity_path=simulate(\'base\',overrides={\'contribution\':-.01})\n result[\'settlement_pressure\']=simulate(\'base\',overrides={\'settlement\':.5})\n result[\'margin_sensitivity_path\']=sensitivity_path\n result[\'margin_sensitivity\']=valuation(sensitivity_path,.10,.02,.14)\n # Auxiliary EV/EBIT current normalized next-year operations; no use of market price.\n r=base[\'rows\'][0];netcash=sum(e[\'cash\']*OWN[k] for k,e in INITIAL.items())-sum(e[\'restricted\']*OWN[k] for k,e in INITIAL.items())-sum(REV0[k]*.025*OWN[k] for k in INITIAL)-sum(e[\'debt\']*OWN[k] for k,e in INITIAL.items())-.17521234211+OPTION_PROCEEDS\n result[\'auxiliary\']={\'ebit1\':r[\'ebit\'],\'net_cash_after_restricted_operating_buyback\':netcash,\'low\':(r[\'ebit\']*12+netcash)/SHARES,\'high\':(r[\'ebit\']*15+netcash)/SHARES}\n result[\'horizon_validation\']={}\n for label,path,k,g,rr in [(\'core_low\',base,.105,.02,.13),(\'core_high\',base,.095,.025,.16),(\'margin_minus_1pp\',sensitivity_path,.10,.02,.14),(\'structural_supported\',result[\'scenarios\'][\'structural_supported\'],.10,.01,.10)]:\n  standard=terminal(path[\'rows\'][4],k,g,rr,300)\n  full={}\n  for h in [400,500]:\n   extended=terminal(path[\'rows\'][4],k,g,rr,h)\n   assert extended[\'feasible\']\n   extended[\'tv5_error_against_300\']=extended[\'per_share\']-standard[\'per_share\']\n   extended[\'current_value_error_against_300\']=extended[\'tv5_error_against_300\']/(1+k)**5\n   assert abs(extended[\'current_value_error_against_300\'])<1e-6\n   assert abs(extended[\'last_dividend_growth\']-g)<1e-8\n   full[str(h)]=extended\n  result[\'horizon_validation\'][label]={\'scope\':\'full 400/500-year legal-cash paths, compared with 300; all years retained\',\'300_tv5\':standard[\'per_share\'],\'300_final_dividend_growth\':standard[\'last_dividend_growth\'],\'300_unreleased_original_principal\':standard[\'unreleased_original_principal\'],\'extensions\':full}\n result[\'independent_endpoint_recalculation\']=\'See independent-check.json: separately coded full operating and legal-cash chain.\'\n # Lossless prefix reuse: 400-year path is exactly the first 400 rows of 500.\n # All 500 rows remain inline; expand_output reconstructs the original full object.\n original=__import__(\'copy\').deepcopy(result)\n for case in result[\'horizon_validation\'].values():\n  ext=case[\'extensions\']\n  assert ext[\'400\'][\'rows\']==ext[\'500\'][\'rows\'][:400]\n  ext[\'400\'][\'rows\']={\'rows_from_extension\':\'500\',\'prefix_years\':400}\n assert expand_output(result)==original\n Path(__file__).with_name(\'2026-Q3-output.json\').write_text(json.dumps(result,ensure_ascii=False,separators=(\',\',\':\'))+\'\\n\')\n print(json.dumps({\'core\':{k:v[\'value\'] for k,v in result[\'core\'].items()},\'dps\':[x[\'dps\'] for x in base[\'rows\'][:5]],\'tv\':{k:v[\'terminal\'][\'per_share\'] for k,v in result[\'core\'].items()},\'feasibility\':{k:v[\'feasible\'] for k,v in result[\'scenarios\'].items()}},indent=2))\nif __name__==\'__main__\':main()\n'

if __name__=="__main__":main()
