#!/usr/bin/env python3
"""万华化学2026Q3 ordinary-share cash model; self-contained standard library.
Units: CNY billion, shares billion. Output stdout is deterministic compact JSON.
No observed market price. 600 years is numeric convergence, not a forecasting claim.
Each budget unit is a named legal source or disclosed residual basket; see assumptions.
"""
import json,copy,math,sys,zlib,lzma,base64,hashlib
SHARES=3.130471626
# Independent re-entry of the literal-source budgets; never imported from reference.
BUDGET=[
 dict(id='P',parent=None,owner=1,cash=1.1526626269,debt=39.661237541,eng=3.3,cap=3.130471626,reserve=2.351465676,ret=64.006554120,ebit=7,da=4.6,weight=.25,floor=2,il=0,ia=0),
 dict(id='N',parent='P',owner=1,cash=6,debt=28,eng=1,ebit=6.5,da=2.2,weight=.08,floor=2,il=0,ia=0),
 dict(id='F',parent='P',owner=.8,cash=3,debt=23,eng=1,ebit=2,da=1.4,weight=.08,floor=1,il=2,ia=0),
 dict(id='I',parent='F',owner=.64,cash=2,debt=19,eng=.8,ebit=3.5,da=1.4,weight=.05,floor=1,il=0,ia=0),
 dict(id='B',parent='P',owner=1,cash=3,debt=10,eng=.5,ebit=1.7,da=1.5,weight=.03,floor=1.5,il=0,ia=0),
 dict(id='O',parent='P',owner=1,cash=5,debt=25,eng=1.4,ebit=4.8,da=2.6,weight=.12,floor=2,il=2.61080223,ia=0),
 dict(id='K',parent='P',owner=.75,cash=1,debt=0,eng=.2,ebit=1.1,da=.8,weight=.03,floor=.5,il=0,ia=0),
 dict(id='R',parent='P',owner=.8,cash=8,debt=35,eng=3.8,ebit=3,da=4.1,weight=.33,floor=2,il=9.5,ia=3.284196694),
 dict(id='T',parent='P',owner=1,cash=15.13325685014,debt=3.01320756845,eng=.54,ebit=.5,da=.2,weight=.03,floor=5,il=15.5,ia=8)]
SOURCE_BUDGET={'N':(2.5,3.8),'F':(.8,.9),'I':(1.2,1.8),'B':(.3,.8),'O':(1.,2.2),'K':(.35,.6),'R':(.3,.8),'T':(.1,.2)}
for _a in BUDGET:
 if _a['id']=='P':_a['registered_capital']=3.130471626
 else:
  _a['remit_target'],_a['remittable_income_budget']=SOURCE_BUDGET[_a['id']]
NAMES={'P':'上市母公司','N':'宁波','F':'福建母层','I':'福建异氰酸酯','B':'BC及海外生产','O':'烟台烯烃','K':'科化国际石化','R':'其余生产主体预算篮子','T':'新加坡及贸易预算篮子'}
SCENARIOS={'low':dict(rate=.11,tail=.95),'high':dict(rate=.095,tail=1.05),'base':{},'margin_minus10':dict(scenario='margin_minus10'),'cycle':dict(scenario='cycle'),'structural':dict(scenario='structural'),'upside':dict(scenario='upside'),'remit_delay':dict(lag=.75),'maintenance_plus10':dict(cost=1.1),'floor_double':dict(floorx=2),'no_credit':dict(credit=False),'structural_funded':dict(scenario='structural',support=True),'maintenance_funded':dict(cost=1.1,support=True),'floor_funded':dict(floorx=2,support=True),'rollover90':dict(renewal=.9),'rollover80':dict(renewal=.8),'release_delay':dict(release=21),'subpayout45':dict(subpayout=.45),'engplus20':dict(engfactor=1.2),'residual70':dict(residual_owner=.7),'rollover80_nobackup':dict(renewal=.8,credit=False),'capacity_half':dict(capacity_factor=.5),'no_capital_recovery':dict(recovery_year=1000),'capital_recovery_delay':dict(recovery_year=21),'capital_recovery_fee10':dict(recovery_fee=.10)}
# Additional fully recomputed economic sensitivities; original 25 scenarios unchanged.
SCENARIOS.update({'release_Y16': {'release': 16}, 'release_Y31': {'release': 31}, 'release_sweep20': {'sweep': 0.2}, 'release_sweep40': {'sweep': 0.4}, 'release_sweep60': {'sweep': 0.6}, 'rollover_loss10_continuous': {'annual_rollover_loss': 0.1}, 'rollover_loss10_Y6': {'rollover_event_year': 6, 'event_rollover_loss': 0.1}, 'rollover_loss20_Y6': {'rollover_event_year': 6, 'event_rollover_loss': 0.2}, 'interest4pct': {'interest_rate': 0.04}, 'interest5pct': {'interest_rate': 0.05}})

def initial(budget):
 out={}
 for a in budget:
  k=a['id'];out[k]={n:float(a[n]) for n in ['cash','debt','eng','il','ia']}
  out[k].update(pending=float(a.get('opening_pending',0)),loan=0.,taxloss=0.)
  if k=='P':out[k].update(cap=a['cap'],registered_capital=a.get('registered_capital',a['cap']),reserve=a['reserve'],ret=a['ret'],K_investment_book_cost_budget=2.979)
  else:out[k].update(remittable_balance_budget=0.,paid_equity_contributions=0.)
  if k=='K':out[k].update(returnable_capital_budget=1.986,capital_units_index=1.)
 return out
def legal_profit(state,profit,domestic=True):
 eligible=max(0.,profit+min(0.,state['ret']))
 addition=min(max(0.,state['registered_capital']*.5-state['reserve']),eligible*.1) if domestic else 0.
 state['reserve']+=addition;state['ret']+=profit-addition
 return addition

def run(scenario='base',rate=.10,horizon=600,tail=1.,lag=.25,cost=1.,floorx=1.,credit=True,budget=None,support=False,renewal=1.,release=11,subpayout=.70,engfactor=1.,residual_owner=.8,capacity_factor=1.,recovery_year=12,recovery_fee=.02,sweep=.80,annual_rollover_loss=0.,rollover_event_year=None,event_rollover_loss=0.,interest_rate=.028):
 b=copy.deepcopy(BUDGET if budget is None else budget)
 for a in b:
  a['eng']*=engfactor
  if a['id']=='R':a['owner']=residual_owner
 by={x['id']:x for x in b};s=initial(b)
 assets=[55.59,25,20,17,20,30,8.5,35,3.56];wc0=[8,5,3,2,2,3,1,5,6]
 for i,a in enumerate(b):s[a['id']].update(operating_assets=assets[i] if budget is None else 0.,working_capital=wc0[i] if budget is None else 0.,tax_vintages=[])
 # topological walk, children before paying investor
 order=[]
 def visit(k):
  for a in b:
   if a['parent']==k:visit(a['id'])
  order.append(k)
 visit('P')
 traces=[];ds=[];failure=None;max_residual=0.
 for y in range(1,horizon+1):
  start=copy.deepcopy(s)
  flows={k:{'cash_journal':[],'declared_in':0.,'received':0.,'internal_interest':0.,'capital_paid':0.,'capital_received':0.,'minority_capital':0.,'minority_cash':0.,'capital_cash':0.,'capital_returned':0.,'capital_return_fee':0.} for k in s}
  def post(k,label,amount):
   s[k]['cash']+=amount;flows[k]['cash_journal'].append([label,amount])
  scale=1.03**min(y-1,4)*1.02**max(0,min(y-5,5))*1.015**max(0,y-10)
  shock,grow,wc=1.,1.,1.
  if scenario=='cycle':shock=[.72,.82,.93][y-1] if y<=3 else 1.;grow=.8 if y<=3 else 1.;wc=1.5 if y<=2 else 1.
  if scenario.startswith('structural'):shock=.72 if y<=5 else .65;grow=1.25;wc=1.2
  if scenario=='upside':shock=1+min(y,5)*.035;grow=1.12
  if scenario=='margin_minus10':shock=.9
  if y>5:shock*=tail
  # Settle old dividends: cash only, never second profit recognition.
  for a in b:
   k=a['id'];par=a['parent'];f=a['owner'];friction=.95 if k=='B' else 1.
   if par:
    paid=s[k]['pending'];post(k,'old_declared_dividend_paid',-paid)
    flows[par]['received']+=paid*f*friction
    flows[k]['minority_cash']+=paid*(1-f);s[k]['pending']=0.
  # Gross bilateral legal balances; no legal netting is presumed.
  for a in b:
   k=a['id']
   if k=='P':continue
   liability,claim=s[k]['il'],s[k]['ia']
   pay=min(liability,a['il']/20);collect=min(claim,a['ia']/20)
   internal=(claim-liability)*.02
   flows[k]['internal_interest']+=internal;flows['P']['internal_interest']-=internal
   post(k,'intercompany_principal',collect-pay);post('P','intercompany_principal',pay-collect)
   s[k]['il']-=pay;s[k]['ia']-=collect
  # New equity: same-date capital, minority and parent cash ownership.
  for a in b:
   k,par,f=a['id'],a['parent'],a['owner']
   if not par:continue
   injection=((3 if y<=5 else 1.5) if k=='R' and y<=10 else (2 if y==1 else 1 if y==2 else 0)*a['weight'])
   injection += ((1 if k=='F' and scenario.startswith('structural') and 6<=y<=20 else .5 if k=='F' and y==6 else 3 if k=='R' and scenario.startswith('structural') and 11<=y<=20 else 1.5 if k=='R' and 11<=y<=15 else 1 if k=='T' and y==6 else 0) if support else 0)
   s[k]['paid_equity_contributions']+=injection;post(k,'paid_in_equity',injection)
   if k=='K':s[par]['K_investment_book_cost_budget']+=injection*f
   flows[k]['capital_received']=injection;flows[k]['minority_capital']=injection*(1-f)
   flows[par]['capital_paid']+=injection*f
  for k in s:post(k,'equity_into_children',-flows[k]['capital_paid'])
  for k in order:
   a=by[k];z=s[k];f=flows[k];par=a['parent'];fraction=a['owner'];friction=.95 if k=='B' else 1.
   ebit=a['ebit']*scale*shock*(1.11**min(y-1,4) if k=='R' else 1)
   da=a['da']*(1+.025*min(y-1,9))*1.015**max(0,y-10)
   growth=([8,7,6,5,4][y-1] if y<=5 else 3.5*1.015**max(0,y-10))*a['weight']*grow
   maintenance=da*cost;capex=maintenance+growth;working=(2 if y<=5 else 1.4)*a['weight']*scale*wc
   interest=z['debt']*interest_rate;deposit=max(0,z['cash'])*.012
   taxable=ebit-interest+f['internal_interest']+deposit
   z['tax_vintages']=[x for x in z['tax_vintages'] if k not in ('B','T') and y-x[0]<=5]
   used=min(sum(x[1] for x in z['tax_vintages']),max(0,taxable));todo=used
   for item in z['tax_vintages']:
    take=min(item[1],todo);item[1]-=take;todo-=take
   tax=max(0,taxable-used)*(.18 if k=='B' else .20)
   if taxable<0 and k not in ('B','T'):z['tax_vintages'].append([y,-taxable])
   z['taxloss']=sum(x[1] for x in z['tax_vintages'])
   z['operating_assets']+=capex-da;z['working_capital']+=working
   own=taxable-tax;external=.6*scale if k=='P' else 0.
   profit=own+external+f['declared_in']
   if k=='P':reserve=legal_profit(z,profit,True);capacity_addition=None
   else:
    # Explicit source budget is NOT legal retained earnings or a fictional statutory pool.
    # Bound by source-specific forecast own profit; losses reduce the carried budget.
    maturity=min(1.,max(0.,(y-10)/10))
    source_scale=scale*(1.11**min(y-1,4) if k=='R' else 1)
    observed_bound=a['remittable_income_budget']*source_scale*shock
    capacity_addition=(min(max(0,own),observed_bound)*(1-maturity)+max(0,own)*.95*maturity)*capacity_factor+min(0,own)+f['declared_in']
    z['remittable_balance_budget']+=capacity_addition;reserve=None
   engineer=min(z['eng'],a['eng']/3);z['eng']-=engineer
   repayment=min(z['debt'],(a['debt']+z['loan'])/25) if y>5 else (z['debt']*.65*(1-renewal) if y==1 else 0.);repayment=min(z['debt'],repayment+z['debt']*.65*(annual_rollover_loss+(event_rollover_loss if y==rollover_event_year else 0.)));z['debt']-=repayment
   post(k,'own_net_profit_cash',own+external);post(k,'depreciation',da);post(k,'new_capex',-capex)
   post(k,'working_capital',-working);post(k,'subsidiary_dividend_received',f['received']);post(k,'subsidiary_capital_received',f['capital_cash'])
   post(k,'old_engineering_settlement',-engineer);post(k,'external_principal',-repayment)
   floor=a['floor']*floorx*1.015**max(0,y-5)
   need=max(0,floor-z['cash']);limit=5 if k=='P' else 2
   borrowing=min(need,max(0,limit-z['loan'])) if credit and y<=5 else 0.
   z['loan']+=borrowing;z['debt']+=borrowing;post(k,'finite_revolver',borrowing)
   if z['cash']<floor-1e-9:failure={'year':y,'entity':k,'cash':z['cash'],'required_floor':floor}
   ordinary=max(0,profit)*(.25 if support and y<=20 else .35) if k=='P' else a['remit_target']*source_scale*shock*(subpayout/.70)*(.30/.70 if support and y<=20 else 1.)
   special=max(0,z['cash']-floor-ordinary)*sweep if y>=(21 if support else release) else 0.
   liquidity_reserve=z['debt']+max(0,z['il']-z['ia']) if k=='T' else 0.
   pool=z['ret'] if k=='P' else z['remittable_balance_budget']
   distribution=max(0,min(ordinary+special,pool,z['cash']-floor-liquidity_reserve))
   if k=='P':z['ret']-=distribution
   else:z['remittable_balance_budget']-=distribution
   if par:
    post(k,'new_dividend_paid',-distribution*(1-lag));z['pending']=distribution*lag
    flows[par]['declared_in']+=distribution*fraction*friction
    flows[par]['received']+=distribution*(1-lag)*fraction*friction
    f['minority_cash']+=distribution*(1-lag)*(1-fraction)
   else:post(k,'ordinary_share_distribution',-distribution);ds.append(distribution/SHARES)
   # Conditional K capital reorganisation: disclosed capital/cost bound, NOT a fake statutory balance.
   # Actual paid/tax basis and creditor clearance are forecast conditions; retain operating floor.
   # Pro-rata subsidiary units reduced; ultimate ownership and listed share count remain unchanged.
   if k=='K' and y>=recovery_year and z['remittable_balance_budget']<1e-9:
    excess=max(0,z['cash']-floor-z['pending']-z['debt']-z['eng'])
    principal=min(z['returnable_capital_budget'],excess/(1+recovery_fee))
    fee=principal*recovery_fee
    post(k,'proportional_capital_return',-principal);post(k,'capital_return_fee',-fee)
    z['returnable_capital_budget']-=principal;z['capital_units_index']=1-(1.986-z['returnable_capital_budget'])/3.972
    s[par]['K_investment_book_cost_budget']-=principal*fraction
    z['remittable_balance_budget']-=fee
    flows[par]['capital_cash']+=principal*fraction
    f['capital_returned']=principal;f['capital_return_fee']=fee;f['minority_cash']+=principal*(1-fraction)

   f.update(ebit=ebit,da=da,maintenance=maintenance,growth_capex=growth,wc=working,interest=interest,deposit_income=deposit,tax=tax,own_profit=own,external_dividend=external,economic_profit=profit,legal_profit=profit if k=='P' else None,remittable_capacity_added=capacity_addition,reserve_added=reserve,engineering_paid=engineer,principal_paid=repayment,gross_refinance_budget=max(0,start[k]['debt']*.65-repayment),cash_floor=floor,borrow=borrowing,ordinary_target=ordinary,special_target=special,liquidity_buffer=liquidity_reserve,declared=distribution)
   expected=start[k]['cash']+sum(t[1] for t in f['cash_journal'])
   err=abs(z['cash']-expected);max_residual=max(max_residual,err)
   assert err<1e-5*max(1,z['cash']), (y,k,'cash conservation',err)
   remaining=z['ret'] if k=='P' else z['remittable_balance_budget']
   assert remaining+f['capital_return_fee']>=-1e-8 or distribution==0
   assert distribution<=max(0,remaining+distribution+f['capital_return_fee'])+1e-7
   if k=='P':assert z['cap']>=start[k]['cap']
  traces.append(dict(year=y,opening=start,flows=flows,closing=copy.deepcopy(s),distribution_per_share=ds[-1]))
  if failure:break
 pv=None if failure else math.fsum(d/(1+rate)**(i+1) for i,d in enumerate(ds))
 tv=None if failure else math.fsum(d/(1+rate)**(i-4) for i,d in enumerate(ds) if i>=5)
 return dict(pv=pv,tv5=tv,d5=ds[:5],failure=failure,years=traces,max_cash_residual=max_residual,rate=rate,states5=[x['closing'] for x in traces[:5]],tv_pv_share=None if failure else tv/(1+rate)**5/pv)

def independent_economic_method():
 # Separate segment FCFF/ROIC budgeting; does not use legal-model output or arrays.
 # EBIT estimates after centrally allocated R&D/admin, mature D&A retained in EBIT.
 # Net investment = growth in NOPAT / independent incremental return, no EBITDA multiple.
 results=[]
 for wacc,pu,petro,fine in [(.09,17.,4.5,5.0),(.08,19.,5.8,6.5)]:
  pv=0.;rows=[];nci_pv=0.;ebits=[pu,petro,fine];g=[.018,.01,.035];roic=[.14,.085,.105];nci=[.11,.07,.13]
  for year in range(1,16):
   total=minor=0.
   for j in range(3):
    e=ebits[j]*(1+g[j])**(year-1);nopat=e*.8;netinvestment=nopat*g[j]/roic[j]
    cf=nopat-netinvestment;total+=cf;minor+=cf*nci[j]
   pv+=total/(1+wacc)**year;nci_pv+=minor/(1+wacc)**year;rows.append([year,total,minor])
  # From year16 the three businesses converge to 1% growth/10% incremental return.
  nopat16=sum(ebits[j]*(1+g[j])**14 for j in range(3))*.8*1.01
  terminal=nopat16*(1-.01/.10)/(wacc-.01)
  terminal_minority=sum(ebits[j]*(1+g[j])**14*nci[j] for j in range(3))*.8*1.01*.9/(wacc-.01)
  ev=pv+terminal/(1+wacc)**15;nci_value=nci_pv+terminal_minority/(1+wacc)**15
  # Opening debt includes financial bills & leases; unpaid old works separate.
  # Cash required to operate is inside enterprise capital, not free surplus.
  # Independently budgeted NCI financing: external20.872 + old works1.4004
  # - surplus cash2.213 + net internal claims1.6431606612.
  nci_operating_value=nci_value
  nci_net_financing=20.872+1.4004-2.213+1.6431606612
  nci_value=nci_operating_value-nci_net_financing
  equity=ev+(44.28591947704-17.)-182.67444510945-12.54+10.-nci_value
  results.append(dict(wacc=wacc,segment_ebit=[pu,petro,fine],growth=g,incremental_roic=roic,years=rows,enterprise_value=ev,minority_value=nci_value,minority_operating_value=nci_operating_value,minority_net_financing=nci_net_financing,operating_cash_floor=17.,investment_value=10,equity=equity,per_share=equity/SHARES))
 return results

def capital_realization(cash,asset_sale,asset_tax_basis,transaction_cost,employee_restoration,other_tax,debt,engineering,other_senior,owner,investment_cost,investor_tax_rate=.25,asset_tax_rate=.25,delay=2.,rate=.10,shares=1.):
 """Finite realization economic budget, not a legal liquidation certificate.
 All creditors are settled before equity; failure cannot yield a continuing value.
 Unknown worker/environment/tax obligations are explicit budgets, never zero by default.
 Investor capital recovery is not new distributable profit. No double-count of asset/book basis.
 """
 assert 0<=owner<=1 and 0<=transaction_cost and 0<=employee_restoration and shares>0
 asset_tax=max(0,asset_sale-asset_tax_basis-transaction_cost)*asset_tax_rate
 available=cash+asset_sale-transaction_cost-employee_restoration-other_tax-asset_tax
 claims=debt+engineering+other_senior
 residual=available-claims
 gross=max(0,residual)*owner
 investor_gain=gross-investment_cost
 investor_tax=max(0,investor_gain)*investor_tax_rate
 net=gross-investor_tax
 return dict(asset_tax=asset_tax,claims=claims,unfunded_claims=max(0,-residual),equity_before_ownership=max(0,residual),owner=owner,gross_receipt=gross,investment_basis=investment_cost,capital_recovery=min(gross,investment_cost),investment_gain=investor_gain,investor_tax=investor_tax,net_receipt=net,delay_years=delay,discounted_per_share=net/(1+rate)**delay/shares,continuing_value=0.,fee=transaction_cost,employee_restoration=employee_restoration,other_tax=other_tax)

def finite_and_capital_diagnostics(results):
 # N maps to real Wanhua Chemical (Ningbo) Co., Ltd.; no forced closure in core.
 # Hypothetical Y30 whole-N-budget termination, not a disclosed plan or certified liquidation floor.
 z=results['base']['years'][29]['closing']['N']
 rows=[]
 for recovery,fee,restoration,delay in [(.4,.03,1.,2),(.65,.02,.5,1)]:
  sale=z['operating_assets']*recovery+z['working_capital']*.8
  out=capital_realization(z['cash'],sale,z['operating_assets']+z['working_capital'],sale*fee,restoration,.2,z['debt'],z['eng'],z['il']+z['pending'],1.,4.61575569057+z['paid_equity_contributions'],.25,.25,delay,.1,SHARES)
  out.update(year=30,entity='万华化学（宁波）有限公司',basis_kind='economic_source_budget_not_single_entity_audited_balance',assets_recovery=recovery,working_capital_recovery=.8,classification='finite_exit_diagnostic_not_whole_company_fair_value')
  rows.append(out)
 # Monitor whether low payouts actually strand money in the continuing base path.
 snapshots={}
 for name in ['low','base','high','capacity_half']:
  snapshots[name]=[]
  for y in [20,30,60,100]:
   t=results[name]['years'][y-1]
   snapshots[name].append(dict(year=y,units={k:dict(cash=v['cash'],necessary_cash=t['flows'][k]['cash_floor'],budget_capacity=v.get('ret',v.get('remittable_balance_budget')),distribution=t['flows'][k]['declared']) for k,v in t['closing'].items()}))
 return dict(finite_exit=rows,continuing_capital=snapshots,capacity_half_classification='distribution_only_stress; omitted capital-restructuring rights mean not a complete fair value',core_no_forced_liquidation=True)

def paid_capital_reduction(state,amount,fee,holder_units):
 """Conditional authorised proportional reduction; caller supplies proven allowable amount.
 Not invoked as an assumed issuer action in core. Models no profit from principal return.
 """
 assert 0<=amount<=state['paid_capital'] and 0<=fee and holder_units<=state['units']
 assert state['cash']-amount-fee>=state['necessary_cash']
 old_units=state['units'];fraction=holder_units/old_units
 reduction=old_units*amount/state['paid_capital']
 state['cash']-=amount+fee;state['paid_capital']-=amount
 state['units']-=reduction;state['retained']-=fee
 return dict(receipt=amount*fraction,holder_units=holder_units*(state['units']/old_units),fee=fee)

def tests():
 # Same production run with one legal parent: 10 EBIT, no debt/capex, 20% tax,
 # cash interest0 initial, 35% distribution =>2.8 /SHARES, cash5.2, reserve capped.
 one=[dict(id='P',parent=None,owner=1,cash=0,debt=0,eng=0,cap=2,reserve=1,ret=0,ebit=10,da=0,weight=0,floor=0,il=0,ia=0)]
 z=run(horizon=1,budget=one);expected=(10*.8+.6)*.35
 assert abs(z['d5'][0]*SHARES-expected)<1e-12
 assert abs(z['years'][0]['closing']['P']['cash']-(8.6-expected))<1e-12
 failed=copy.deepcopy(one);failed[0].update(ebit=0,floor=10)
 q=run(horizon=1,budget=failed,credit=False)
 assert q['failure'] and q['pv'] is None and q['tv5'] is None and q['d5']==[0.]
 # Deficit covered before reserve: prior -4 +6 =>eligible2, reserve .2, retained1.8.
 x=dict(cap=10,registered_capital=10,reserve=0,ret=-4);r=legal_profit(x,6);assert abs(r-.2)<1e-12 and abs(x['ret']-1.8)<1e-12
 # Reserve ceiling uses registered capital, while cash follows paid capital.
 x=dict(cap=2,registered_capital=2,reserve=.95,ret=0);assert abs(legal_profit(x,10)-.05)<1e-12
 uncalled=copy.deepcopy(one);uncalled[0].update(cap=0,registered_capital=10,reserve=0)
 u=run(horizon=1,budget=uncalled)
 assert abs(u['years'][0]['closing']['P']['reserve']-.86)<1e-12
 assert abs(u['years'][0]['closing']['P']['cash']-5.59)<1e-12
 # Collection of previously declared dividend adds cash, not a second statutory profit.
 parent=copy.deepcopy(one[0]);parent.update(ebit=0,cap=2,reserve=1)
 child=dict(id='N',parent='P',owner=1,cash=1,debt=0,eng=0,ebit=0,da=0,weight=0,floor=0,il=0,ia=0,remit_target=0,remittable_income_budget=0,opening_pending=1)
 pending=run(horizon=1,budget=[parent,child]);pf=pending['years'][0]['flows']['P']
 assert abs(pf['legal_profit']-.6)<1e-12 and pf['received']==1
 assert abs(pending['years'][0]['closing']['P']['cash']-1.39)<1e-12
 red=dict(cash=10.,necessary_cash=1.,paid_capital=10.,units=100.,retained=0.)
 rr=paid_capital_reduction(red,4.,.1,60.)
 assert rr['receipt']==2.4 and rr['holder_units']==36 and red['units']==60 and red['retained']==-.1
 # Actual core K return: cash and investor book basis move, not parent legal profit.
 kr=run(horizon=12);kn=run(horizon=12,recovery_year=1000)
 flow=kr['years'][-1]['flows']['K'];amount=flow['capital_returned'];assert amount>0
 assert abs(kr['years'][-1]['closing']['P']['K_investment_book_cost_budget']-(2.979+.09*.75-amount*.75))<1e-10
 assert abs(kr['years'][-1]['flows']['P']['legal_profit']-kn['years'][-1]['flows']['P']['legal_profit'])<1e-10
 assert kr['years'][-1]['closing']['K']['capital_units_index']>=.5
 # Required registered-vs-paid example and already-full reserve.
 x=dict(cap=10,registered_capital=20,reserve=5,ret=0);assert legal_profit(x,10)==1
 x=dict(cap=10,registered_capital=20,reserve=10,ret=0);assert legal_profit(x,10)==0
 x['registered_capital']=24;assert legal_profit(x,10)==1
 # Profit-constrained but solvent owner can recover capital with costs and minority respected.
 cr=capital_realization(10,0,0,1,0,0,0,0,0,.6,6,delay=0,shares=2)
 assert abs(cr['capital_recovery']-5.4)<1e-12 and cr['investor_tax']==0 and cr['continuing_value']==0
 assert abs(cr['discounted_per_share']-2.7)<1e-12
 insolvent=capital_realization(1,2,2,.1,.5,.2,3,1,0,.6,6)
 assert insolvent['unfunded_claims']>0 and insolvent['net_receipt']==0
 # Pro-rata paid reduction changes holder units as well as total units; no artificial per-share gain.
 original_units=100;reduced=20;holder=60
 assert (holder*(1-reduced/original_units))/(original_units-reduced)==.6
 return dict(actual_K_capital_return_cash_not_profit=True,old_pending_cash_not_profit=True,production_capital_reduction=True,capital_realization_fees_priority_basis_minority=True,registered20_paid10_reserve5=True,registered_conversion_reserve=True,paid_reduction_units=True,uncalled_registered_does_not_create_cash=True,actual_run_hand_dividend=expected,actual_run_hand_cash=8.6-expected,funding_failure=q['failure'],loss_before_reserve=True,registered_capital_cap=True)

def compute_original_bytes():
 test=tests();result={k:run(**v) for k,v in SCENARIOS.items()}
 # Same economic initial and complete five-year states, not just equal D.
 assert result['low']['states5']==result['base']['states5']==result['high']['states5']
 for name,z in result.items():
  if z['failure'] is None:
   cashpv=math.fsum(d/(1+z['rate'])**(i+1) for i,d in enumerate(z['d5']))
   assert abs(z['pv']-cashpv-z['tv5']/(1+z['rate'])**5)<1e-9
 out=dict(schema_version=2,symbol='CN:600309',name='万华化学',diagnostics=finite_and_capital_diagnostics(result),as_of='2026-10-26',unit='CNY billion; shares billion',shares=SHARES,budget=BUDGET,entity_names=NAMES,scenarios=result,economic_method=independent_economic_method(),tests=test)
 if True: # Original nested format retained byte-for-byte before reversible transport.
  for val in out['scenarios'].values():
   annual=val.pop('years');raw=json.dumps(annual,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
   encoded=base64.b64encode(lzma.compress(raw,preset=6)).decode()
   assert json.loads(lzma.decompress(base64.b64decode(encoded)))==annual
   val['annual_trace']={'encoding':'lzma-base64-utf8-json','count':len(annual),'sha256_uncompressed':hashlib.sha256(raw).hexdigest(),'data':encoded}
  out['readable_summary']={'core_value_per_share':[result['low']['pv'],result['high']['pv']],'distributions':result['base']['d5'],'tv5':[result['low']['tv5'],result['high']['tv5']],'classification':'core plus explicitly labelled stress/exit diagnostics','annual_record_schema':{'year':'rolling year integer','opening':'each budget unit beginning balances','flows':'cash journal and income/capital/debt/distribution calculations','closing':'each budget unit ending balances','distribution_per_share':'actual budget ordinary-share receipt'}}
  out['lossless_expansion']='base64 decode annual_trace.data; lzma decompress; UTF8 JSON parse. No recomputation, interpolation or scenario reuse.'
 return (json.dumps(out,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')


# TRANSPORT ONLY: no financial function or parameter above this section is changed.
TRANSPORT_SCHEMA='deterministic-xz-reversible-json-envelope-v2'
ORIGINAL_SHA256='61a4c36a3179cb8ee0d51f3fc836db36ec249f765c593762ffa81a0a8e3b952f'
ORIGINAL_BYTES=45375702

def canonical(value):
 return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')

def pack_original(raw):
 assert len(raw)==ORIGINAL_BYTES and hashlib.sha256(raw).hexdigest()==ORIGINAL_SHA256
 original=json.loads(raw);metadata=copy.deepcopy(original);series=[]
 for name,scenario in metadata['scenarios'].items():
  trace=scenario['annual_trace'];decoded=lzma.decompress(base64.b64decode(trace.pop('data'),validate=True))
  assert hashlib.sha256(decoded).hexdigest()==trace['sha256_uncompressed']
  annual=json.loads(decoded);assert len(annual)==trace['count'];series.append(annual)
 # Plain rectangular record order, no deltas, reference table, interpolation or omitted field.
 # None means the scenario already ended; exact counts are retained in original metadata.
 annual_by_year=[[rows[y] if y<len(rows) else None for rows in series] for y in range(max(map(len,series)))]
 # Stream canonical UTF8 into xz; avoid allocating 327MB text and bytes simultaneously.
 encoder=json.JSONEncoder(ensure_ascii=False,separators=(',',':'),allow_nan=False)
 compressor=lzma.LZMACompressor(format=lzma.FORMAT_XZ,preset=6)
 buffer=bytearray();chunks=[];transport_hash=hashlib.sha256();transport_size=0
 for fragment in encoder.iterencode({'original_metadata':metadata,'scenario_order':list(metadata['scenarios']),'annual_by_year':annual_by_year}):
  buffer.extend(fragment.encode('utf-8'))
  if len(buffer)>=1048576:
   block=bytes(buffer);buffer.clear();transport_hash.update(block);transport_size+=len(block);chunks.append(compressor.compress(block))
 if buffer:
  block=bytes(buffer);transport_hash.update(block);transport_size+=len(block);chunks.append(compressor.compress(block))
 chunks.append(compressor.flush());compressed=b''.join(chunks)
 wrapper={'schema':TRANSPORT_SCHEMA,'symbol':'CN:600309','name':'万华化学','payload_schema_version':original['schema_version'],
 'original_bytes':len(raw),'original_sha256':hashlib.sha256(raw).hexdigest(),
 'transport_bytes':transport_size,'transport_sha256':transport_hash.hexdigest(),
 'compression':{'format':'xz','preset':6,'library':'Python standard library lzma'},
 'compressed_bytes':len(compressed),'compressed_sha256':hashlib.sha256(compressed).hexdigest(),
 'reversible_transform':{'steps':['decode each annual_trace.data using lzma and base64','place complete annual records by year, then scenario_order','preserve all other original metadata and JSON key order'],
 'restore':['transpose using each annual_trace.count','canonical UTF8 JSON each annual array; check its SHA256','lzma.compress(array,preset=6) and base64 restores each original data string','canonical original JSON plus one LF; check original_bytes and original_sha256']},
 'expand':'python 2026-Q3.py --expand [target]; default expanded-output.json; restores original bytes exactly, without economic recomputation',
 'expand_years':'python 2026-Q3.py --expand-years [target]; default expanded-years.json; original parsed fields plus every scenario.years as readable records',
 'value_range':{'low':36.49,'high':52.43,'currency':'CNY'},'summary':original['readable_summary'],
 'scenario_names':list(original['scenarios']),'scenario_annual_counts':{k:v['annual_trace']['count'] for k,v in original['scenarios'].items()},
 'tests':original['tests'],'annual_record_schema':original['readable_summary']['annual_record_schema'],
 'payload_xz_base64':base64.b64encode(compressed).decode('ascii')}
 return wrapper

def decode_transport(wrapper):
 assert wrapper['schema']==TRANSPORT_SCHEMA
 compressed=base64.b64decode(wrapper['payload_xz_base64'],validate=True)
 assert len(compressed)==wrapper['compressed_bytes'] and hashlib.sha256(compressed).hexdigest()==wrapper['compressed_sha256']
 import io
 digest=hashlib.sha256();size=0
 with lzma.LZMAFile(io.BytesIO(compressed),'rb') as stream:
  while True:
   block=stream.read(1048576)
   if not block:break
   digest.update(block);size+=len(block)
 assert size==wrapper['transport_bytes'] and digest.hexdigest()==wrapper['transport_sha256']
 with lzma.open(io.BytesIO(compressed),'rt',encoding='utf-8') as stream:payload=json.load(stream)
 metadata=payload['original_metadata'];order=payload['scenario_order'];blocks=payload['annual_by_year']
 assert order==list(metadata['scenarios'])==wrapper['scenario_names']
 all_years={}
 for index,name in enumerate(order):
  trace=metadata['scenarios'][name]['annual_trace'];count=trace['count']
  rows=[blocks[y][index] for y in range(count)]
  assert all(row is not None for row in rows) and all(block[index] is None for block in blocks[count:])
  data=canonical(rows);assert hashlib.sha256(data).hexdigest()==trace['sha256_uncompressed']
  trace['data']=base64.b64encode(lzma.compress(data,preset=6)).decode('ascii')
  all_years[name]=rows
 raw=canonical(metadata)+b'\n'
 assert len(raw)==wrapper['original_bytes']==ORIGINAL_BYTES
 assert hashlib.sha256(raw).hexdigest()==wrapper['original_sha256']==ORIGINAL_SHA256
 return raw,all_years

def main():
 from pathlib import Path
 here=Path(__file__).resolve().parent;output=here/'2026-Q3-output.json'
 if len(sys.argv)>1 and sys.argv[1] in ('--expand','--expand-years'):
  years_mode=sys.argv[1]=='--expand-years'
  target=Path(sys.argv[2]) if len(sys.argv)>2 else here/('expanded-years.json' if years_mode else 'expanded-output.json')
  if target.resolve() in {output.resolve(),Path(__file__).resolve()}:raise ValueError('Expansion must not overwrite model or envelope')
  raw,years=decode_transport(json.loads(output.read_bytes()))
  if years_mode:
   readable=json.loads(raw)
   for name,rows in years.items():readable['scenarios'][name]['years']=rows
   # Stream the large human-readable JSON instead of allocating a second full UTF8 copy.
   with target.open('w',encoding='utf-8') as handle:
    json.dump(readable,handle,ensure_ascii=False,separators=(',',':'),allow_nan=False);handle.write('\n')
   return
  target.write_bytes(raw);return
 original=compute_original_bytes();wrapper=pack_original(original)
 output.write_bytes(canonical(wrapper)+b'\n')
 (here/'summary.json').write_text(json.dumps({k:v for k,v in wrapper.items() if k!='payload_xz_base64'},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(wrapper['value_range'],ensure_ascii=False))
if __name__=='__main__':main()
