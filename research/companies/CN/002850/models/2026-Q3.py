#!/usr/bin/env python3
"""Kedali 2026Q3 research budget. stdlib only. All amounts CNY billion, shares billion.
Legal-source budgets are estimates, NOT reported entity forecasts. No shared state.
"""
import json, math, copy
from pathlib import Path
SHARES=.286448468 # issued plus conservative unreported option exercise bound; no treasury cancellation
OPTION_SHARES=60126
OPTION_PROCEEDS=OPTION_SHARES*105.41/1e9
OWN={'P':1.,'H':1.,'J':1.,'D':1.,'F':1.,'R':.51}
# H Huizhou, J Jiangsu, D other domestic (ring fenced, no upstream), F foreign, R robot JV.
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
 old=e['retained']; e['retained']+=profit
 # prior losses must be made good before statutory reserve. Never truncate negative retained earnings.
 reserve=min(max(0.,profit+min(old,0.))*.10,max(0.,e['capital']*.5-e['reserve']))
 e['retained']-=reserve;e['reserve']+=reserve
 return reserve

def simulate(name='base',years=5,overrides=None):
 s=dict(SCENARIOS[name]);s.update(overrides or {})
 E=copy.deepcopy(INITIAL);E['P']['cash']+=OPTION_PROCEEDS;cap=CAP0.copy();prev=REV0.copy();queue=[];rows=[];maxres=0
 # Remaining historical options assumed exercised at 105.41; cash and dilution booked together.
 for y in range(1,years+1):
  opening=sum(x['cash'] for x in E.values()); olddebt=sum(x['debt'] for x in E.values())
  # Explicit shareholder contributions support construction; not earnings and not group cash.
  supportF=([.25,.25,.20,.10,.05][y-1] if y<=5 else .02)
  supportF+=s.get('extra_supportF',0.) if y>=4 else 0.
  supportR=([.08,.08,.06,.03,.02][y-1] if y<=5 else .01)
  E['P']['cash']-=supportF+supportR;E['F']['cash']+=supportF;E['R']['cash']+=supportR
  E['F']['capital']+=supportF;E['R']['capital']+=supportR
  # Other shareholders match robot funding at their legal 49% share.
  robot_other=supportR*49/51;E['R']['cash']+=robot_other;E['R']['capital']+=robot_other
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
   o=operating_cash(rev,cap[k],contribution,FIX[k]*(1.025**(y-1)),DArate[k],(.23 if k=='F' else .20 if k=='R' else s['tax']),e['debt'],s['rate'],prev[k],NWC[k]+s['nwc'],growth)
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
   ops[k].update(capital=e['capital'],cash=e['cash'],debt=e['debt'],retained=e['retained'],reserve=e['reserve'],restricted=e['restricted'],payable=payable)
  closing=sum(x['cash'] for x in E.values())
  expected=opening+sum(o['fcfe'] for o in ops.values())+newdebt-repay+equity_minor-div-buyback-minor_paid
  residual=closing-expected;maxres=max(maxres,abs(residual));assert abs(residual)<1e-7
  common_cash=sum(e['cash']*OWN[k] for k,e in E.items())
  common_debt=sum(e['debt']*OWN[k] for k,e in E.items())
  necessary=sum(ops[k]['revenue']*.025*OWN[k]+e['restricted']*OWN[k] for k,e in E.items())
  rows.append(dict(year=y,pending_dividends=copy.deepcopy(queue),rate=s['rate'],extra_supportF=s.get('extra_supportF',0),domestic_tax=s['tax'],scenario=name,upstream_delay=s['delay'],revenue=sum(o['revenue'] for o in ops.values()),ebit=sum(o['ebit']*OWN[k] for k,o in ops.items()),common_profit=earnings,dividend=div,dps=div/SHARES,upstream_declared=updecl,upstream_cash=upcash,parent_receivable=sum(q['amount'] for q in queue),cash=closing,common_cash=common_cash,common_debt=common_debt,excess_common_cash=common_cash-necessary,net_excess=common_cash-necessary-common_debt,borrowed=newdebt,repaid=repay,buyback=buyback,minor_equity=equity_minor,parent_support_foreign=supportF,parent_support_robot=supportR,entities=ops,residual=residual))
 return dict(feasible=True,rows=rows,max_cash_residual=maxres,opening_cash=sum(e['cash'] for e in INITIAL.values())+OPTION_PROCEEDS,option_proceeds=OPTION_PROCEEDS,shares=SHARES)

def terminal(row,k,g,roic,horizon=300):
 """Same entity operating/capital path generates profits, financing and actual dividends.
 No separate automatic cash bridge. Opening principal remains on each cash ledger.
 """
 E={a:{q:e[q] for q in ['cash','debt','retained','reserve','capital','restricted']} for a,e in row['entities'].items()}
 prior={a:e['ebit'] for a,e in row['entities'].items()};rev={a:e['revenue'] for a,e in row['entities'].items()}
 pending=copy.deepcopy(row['pending_dividends']);history=[];pv=0.;openprincipal={}
 for a,e in E.items():openprincipal[a]=max(0,e['cash']-rev[a]*.025-e['restricted']-sum(q['amount'] for q in pending if q['entity']==a))
 principal=openprincipal.copy();unlocked={a:0 if v<1e-12 else None for a,v in principal.items()};rate=row['rate'];maxres=0.;ops_pv=0;principal_pv=0
 for t in range(1,horizon+1):
  opening=sum(e['cash'] for e in E.values());external_minority=0;minor_paid=0;taxwithheld=0;borrow=0;repaid=0;flows=0;up=0;details={}
  gr=([.01]*7 if row['scenario']=='structural' else [.065,.055,.045,.035,.03,.025,.025])[t-1] if t<=7 else g
  # Structural overseas losses continue to consume legal parent equity; matching partner capital is not profit.
  supportF=(.14 if row['scenario']=='structural' else 0.)*(1+g)**(t-1)
  if supportF:
   E['P']['cash']-=supportF;E['F']['cash']+=supportF;E['F']['capital']+=supportF
   supportR=.025*(1+g)**(t-1);partner=supportR*49/51
   E['P']['cash']-=supportR;E['R']['cash']+=supportR+partner;E['R']['capital']+=supportR+partner;external_minority+=partner
  for a,e in E.items():
   oldebit=prior[a];ebit=oldebit*(1+gr);taxrate=.23 if a=='F' else .20 if a=='R' else row['domestic_tax']
   oldnopat=oldebit-max(oldebit,0)*taxrate;nopat=ebit-max(ebit,0)*taxrate
   # Loss-making sites cannot finance negative reinvestment: retain maintenance and spend only on actual positive expansion.
   investment=max(0,nopat-oldnopat)/roic
   rev[a]*=1+gr;floor=rev[a]*.025+e['restricted']
   interest=e['debt']*rate;profit=ebit-interest-max(ebit-interest,0)*taxrate
   fcf=profit-investment;e['cash']+=fcf;flows+=fcf
   payable=sum(q['amount'] for q in pending if q['entity']==a)
   if e['cash']<floor+payable:
    need=(floor+payable-e['cash'])/(1-rate*.5)
    credit=LIMIT[a]*rev[a]/row['entities'][a]['revenue']
    if e['debt']+need>credit+1e-8:return dict(feasible=False,year_after_5=t,entity=a,shortfall=e['debt']+need-credit,rows=history)
    e['cash']+=need;e['debt']+=need;borrow+=need
    extra=need*rate*.5;e['cash']-=extra;profit-=extra;fcf-=extra;flows-=extra
   reserve=profit_legal(e,profit)
   debtpay=min(e['debt'],max(0,e['cash']-floor-payable));e['cash']-=debtpay;e['debt']-=debtpay;repaid+=debtpay
   # New operating cash consumes legal distributable profits BEFORE old financial principal.
   opdist=0;pd=0
   if a!='P':
    free=max(0,e['cash']-floor-payable)
    opdist=min(max(0,fcf-debtpay),max(0,e['retained']),free)
    e['retained']-=opdist;e['cash']-=opdist
    principal[a]=min(principal[a],max(0,e['cash']-floor-payable))
    unlock={'H':1,'J':1,'D':3,'F':5,'R':1}[a]
    if t>=unlock:
     pd=min(max(0,e['retained']),max(0,e['cash']-floor-payable))
     e['retained']-=pd;e['cash']-=pd;principal[a]-=min(principal[a],pd)
    gross=(opdist+pd)*OWN[a];withheld=gross*(.10 if a in ('F','R') else 0)
    minor_paid+=(opdist+pd)*(1-OWN[a]);taxwithheld+=withheld
    received=gross-withheld;E['P']['cash']+=received;profit_legal(E['P'],received);up+=received
   details[a]=dict(ebit=ebit,profit=profit,reinvestment=investment,fcf=fcf,reserve_added=reserve,debt_paid=debtpay,operating_dividend=opdist,principal_dividend=pd)
   prior[a]=ebit
  # Old receivables were recognized before year five; settlement never repeats profit.
  for q in pending[:]:
   if q['due']<=5+t:
    E[q['entity']]['cash']-=q['amount'];E['P']['cash']+=q['amount'];pending.remove(q)
  parent=E['P'];floor=rev['P']*.025
  latepay=min(parent['debt'],max(0,parent['cash']-floor));parent['debt']-=latepay;parent['cash']-=latepay;repaid+=latepay
  dividend=min(max(0,parent['retained']),max(0,parent['cash']-floor))
  parent['cash']-=dividend;parent['retained']-=dividend
  principal['P']=min(principal['P'],max(0,parent['cash']-floor))
  close=sum(e['cash'] for e in E.values())
  residual=close-(opening+flows+borrow-repaid+external_minority-minor_paid-taxwithheld-dividend)
  assert abs(residual)<1e-6;maxres=max(maxres,abs(residual))
  assert all(e['cash']>=-1e-8 for e in E.values())
  for a,e in E.items():
   details[a].update(e,principal_remaining=principal[a],revenue=rev[a])
   if principal[a]<1e-12 and unlocked[a] is None:unlocked[a]=t
  history.append(dict(year_after_5=t,operating_growth=gr,actual_holder_dividend=dividend,upstream_received=up,withholding=taxwithheld,minority_dividend=minor_paid,borrowing=borrow,debt_repayment=repaid,principal_remaining=principal.copy(),entities=details,residual=residual))
  pv+=dividend/(1+k)**t
 # Terminal closure only after legal unlock and debt recovery are established in actual path.
 # Beyond year300 settled businesses grow at g; actual cash distribution already incorporates reinvestment, reserves, withholding.
 tail=history[-1]['actual_holder_dividend']*(1+g)/(k-g)/(1+k)**horizon
 unresolved=sum(principal.values())
 # Unreleased original principal is retained (not confiscated); upper bound separately reported.
 return dict(feasible=True,per_share=(pv+tail)/SHARES,actual_distributions_pv=pv,steady_component=tail,unreleased_original_principal=unresolved,unreleased_principal_upper_bound_per_share=sum(principal[a]*OWN[a] for a in principal)/SHARES,last_dividend_growth=history[-1]['actual_holder_dividend']/history[-2]['actual_holder_dividend']-1,closure_growth=g,initial_principal=openprincipal,original_principal_fully_released_or_reinvested_year=unlocked,rows=history,simulated_years=horizon,max_cash_residual=maxres)

def valuation(sim,k=.10,g=.02,roic=.14):
 if not sim['feasible']:return None
 row=sim['rows'][4];tv=terminal(row,k,g,roic)
 if not tv['feasible']:return dict(feasible=False,terminal=tv)
 d=sum(r['dps']/(1+k)**r['year'] for r in sim['rows'][:5]);tpv=tv['per_share']/(1+k)**5
 return dict(value=d+tpv,distributions_pv=d,terminal_pv=tpv,terminal_share=tpv/(d+tpv),terminal=tv)

def tests():
 # Formal operating function manual fixture: EBIT=100*.3-5-10=15; interest=2; tax=2.6; NI10.4;
 # NWC growth=(100-80)*.2=4; CFO16.4; maintenance10 and growth7 => FCFE -0.6.
 z=operating_cash(100,100,.3,5,.1,.2,20,.1,80,.2,7)
 assert abs(z['fcfe']-(-.6))<1e-10
 e=dict(retained=-5,reserve=0,capital=10)
 profit_legal(e,3);assert e['retained']==-2 and e['reserve']==0
 profit_legal(e,4);assert abs(e['retained']-1.8)<1e-10 and abs(e['reserve']-.2)<1e-10
 f=simulate('structural',overrides=dict(credit_factor=0,payout=0,util=-.65))
 assert not f['feasible'] # zero dividends cannot cure missing project/operating funds
 base=simulate('base'); delayed=simulate('delay5')
 # Declaration earnings, not cash receipt, drive legal retained earnings: same declarations and own operations.
 for i in range(5):
  b=base['rows'][i];d=delayed['rows'][i]
  blegal=b['entities']['P']['retained']+sum(a['dividend'] for a in base['rows'][:i+1])
  dlegal=d['entities']['P']['retained']+sum(a['dividend'] for a in delayed['rows'][:i+1])
  assert abs(blegal-dlegal)<1e-8
 assert delayed['rows'][4]['parent_receivable']>0
 assert delayed['rows'][4]['entities']['R']['retained']<0
 return dict(no_double_profit_on_old_receivable=True,delayed_principal_preserved=delayed['rows'][4]['parent_receivable'],operating_manual_fcfe=z['fcfe'],loss_carry_forward=e,finite_credit_zero_dividend_fail={k:v for k,v in f.items() if k!='rows'})

def expand_output(data):
 """Resolve the four explicit 400-year prefix references; no numeric conversion."""
 import copy
 full=copy.deepcopy(data)
 for case in full.get('horizon_validation',{}).values():
  ext=case['extensions']
  if isinstance(ext['400']['rows'],dict):
   assert ext['400']['rows']=={'rows_from_extension':'500','prefix_years':400}
   ext['400']['rows']=copy.deepcopy(ext['500']['rows'][:400])
 return full

def main():
 result={'unit':'CNY billion except per share','shares':SHARES,'definitions':{'P':'listed parent economic operations and legal payer','H':'Huizhou wholly-owned manufacturing','J':'Jiangsu wholly-owned manufacturing','D':'other domestic ring-fenced budget, no upstream in explicit years','F':'overseas wholly-owned aggregate, no upstream','R':'robot project 51% parent ownership'},'initial':INITIAL,'scenarios':{k:simulate(k) for k in SCENARIOS},'tests':tests()}
 result['scenarios']['structural_supported']=simulate('structural',overrides={'extra_supportF':.12,'capmult':.3,'payout':.1})
 base=result['scenarios']['base'];result['core']={'low':valuation(base,.105,.02,.13),'high':valuation(base,.095,.025,.16)}
 result['scenario_values']={k:valuation(v,.10,.01 if k.startswith('structural') else .02,.10 if k.startswith('structural') else .14) for k,v in result['scenarios'].items()}
 sensitivity_path=simulate('base',overrides={'contribution':-.01})
 result['settlement_pressure']=simulate('base',overrides={'settlement':.5})
 result['margin_sensitivity_path']=sensitivity_path
 result['margin_sensitivity']=valuation(sensitivity_path,.10,.02,.14)
 # Auxiliary EV/EBIT current normalized next-year operations; no use of market price.
 r=base['rows'][0];netcash=sum(e['cash']*OWN[k] for k,e in INITIAL.items())-sum(e['restricted']*OWN[k] for k,e in INITIAL.items())-sum(REV0[k]*.025*OWN[k] for k in INITIAL)-sum(e['debt']*OWN[k] for k,e in INITIAL.items())-.17521234211+OPTION_PROCEEDS
 result['auxiliary']={'ebit1':r['ebit'],'net_cash_after_restricted_operating_buyback':netcash,'low':(r['ebit']*12+netcash)/SHARES,'high':(r['ebit']*15+netcash)/SHARES}
 result['horizon_validation']={}
 for label,path,k,g,rr in [('core_low',base,.105,.02,.13),('core_high',base,.095,.025,.16),('margin_minus_1pp',sensitivity_path,.10,.02,.14),('structural_supported',result['scenarios']['structural_supported'],.10,.01,.10)]:
  standard=terminal(path['rows'][4],k,g,rr,300)
  full={}
  for h in [400,500]:
   extended=terminal(path['rows'][4],k,g,rr,h)
   assert extended['feasible']
   extended['tv5_error_against_300']=extended['per_share']-standard['per_share']
   extended['current_value_error_against_300']=extended['tv5_error_against_300']/(1+k)**5
   assert abs(extended['current_value_error_against_300'])<1e-6
   assert abs(extended['last_dividend_growth']-g)<1e-8
   full[str(h)]=extended
  result['horizon_validation'][label]={'scope':'full 400/500-year legal-cash paths, compared with 300; all years retained','300_tv5':standard['per_share'],'300_final_dividend_growth':standard['last_dividend_growth'],'300_unreleased_original_principal':standard['unreleased_original_principal'],'extensions':full}
 result['independent_endpoint_recalculation']='See independent-check.json: separately coded full operating and legal-cash chain.'
 # Lossless prefix reuse: 400-year path is exactly the first 400 rows of 500.
 # All 500 rows remain inline; expand_output reconstructs the original full object.
 original=__import__('copy').deepcopy(result)
 for case in result['horizon_validation'].values():
  ext=case['extensions']
  assert ext['400']['rows']==ext['500']['rows'][:400]
  ext['400']['rows']={'rows_from_extension':'500','prefix_years':400}
 assert expand_output(result)==original
 Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
 print(json.dumps({'core':{k:v['value'] for k,v in result['core'].items()},'dps':[x['dps'] for x in base['rows'][:5]],'tv':{k:v['terminal']['per_share'] for k,v in result['core'].items()},'feasibility':{k:v['feasible'] for k,v in result['scenarios'].items()}},indent=2))
if __name__=='__main__':main()
