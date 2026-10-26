"""CN600750, cutoff2026-10-26. CNY million/shares million. Future economic budgets, not certified legal balances.
Real P/J/S/H/D/E separate. W and H_downstream are economic remittance budgets, no fictional registered/legal pools.
All operating flows, internal creditor cash, minority rights, taxes and finite recovery use ONE annual engine.
"""
import json,copy,math,gzip,base64,hashlib,sys
from pathlib import Path
S=635.588289
FIN=283.2669359+422.54048033+935.17586633-5.82521356+1283.83120596-52.4105701
NAMES=['listed_parent','wholly_owned_remittance_budget','Jisheng','Sanghai','Haisi','Yinpian','Jingcheng_Huiyao','Haisi_downstream_remittance_budget']
OWN=[1,1,.51,.51,.51,.51,.70,1]
RECV=[None,0,0,0,0,0,0,4]
REGISTER=[S,None,122.45,12.0155,148.5121,31.0204,51.,None]
BOOK=[0,0,217.02661589,51.30202294,223.44370736,86.11996148,70.78393,0]
BASE={'growth':[0,.025,.03,.03,.025],'margin':1.,'div':[.95,1,1.05,1.1,1.15],'g':.0175,'roic':.16,'r':.095,
 'aftertax_operating':[560.,20.,20.,0.,120.,70.,0.,30.], 'tax':[.15,.25,.25,.25,.25,.15,.25,.25],
 'cash':[FIN-170,100.,20.,1.,30.,10.,4.,5.], 'capacity':[2200.,100.,100.,0.,350.,140.,10.,50.],
 'reserve':[S/2,None,0.,0.,0.,0.,0.,None], 'registered':REGISTER,
 'parent_payable_settlement':[0.,0.,0.,0.,250.,140.,10.,0.],
 'p_capex':[120,120,110,105,105],'n_capex':[150,140,125,115,115],'wc':[15,15,16,17,17],
 'extra_wc':0.,'wc_recovery':True,'fund_call':24.,'fund_start':128.83038187,'fund_exit':8,'fund_realization':1.,
 'yield':.015,'loan_rate':.03,'j_loan_limit':450.,'j_funding':300.,'j_loan_maturity':20,'j_exit_realization':.70,
 'j_book_netassets':459.34,'weak_asset_exit_year':10,'weak_asset_realization':.70,'weak_asset_profit_hurdle':.05,'tax_basis_ratio':1.,'sub_dividend_start':3,'release_start':6,'sub_payout':.65,'capital_return_start':12,'capital_return_every':5,'capital_fee':.02,
 'parent_capital_start':12,'parent_capital_every':5,'parent_capital_fee':.02,'parent_premium':0.,
 'continue_reserve':False,'tax_renewal':True,'refund':False,'j_capex_stress':0.,'effective_year':1}

def reserve_roll(capacity,reserve,registered,profit,keep=False):
 if registered is None:return capacity+profit,None,0.
 eligible=max(profit-max(-capacity,0),0.)
 charge=.10*eligible if keep else min(.10*eligible,max(.5*registered-reserve,0.))
 return capacity+profit-charge,reserve+charge,charge

def run(p,years=300,initial=None,start=1):
 p=copy.deepcopy(p);ownership=p.get('ownership',OWN);n=8;rates=p['tax'][:];cash=p['cash'][:];cap=p['capacity'][:];res=p['reserve'][:];reg=p['registered'][:];book=BOOK[:];taxbasis=[0,0,122.45*.51,12.0155*.51,148.5121*.51,31.0204*.51,51*.70,0]
 loan=163.21408;old_j_external=156.78592;other_external=60.04907838;factor=1.;shares=S;holder_units=1.;premium=p['parent_premium'];active=[True]*n;Jnet=p['j_book_netassets'];netbook=[0,0,Jnet,35.71,728.94,229.88,85.27,0];fund=p['fund_start'];rows=[]
 if initial:
  cash=initial.get('cash',cash);cap=initial.get('capacity',cap);res=initial.get('reserve',res);reg=initial.get('registered',reg);loan=initial.get('loan',loan);old_j_external=initial.get('old_j_external',old_j_external);other_external=initial.get('other_external',other_external);fund=initial.get('fund',fund)
 for t in range(start,start+years):
  opening_cash=cash[:];opening_cap=cap[:];opening_loan=loan
  if t<=5:factor*=1+p['growth'][t-1]
  else:factor*=1+p['g']
  # Stable after-tax operating budgets converted to each real payer's pretax base.
  pretax=[p['aftertax_operating'][i]/(1-p['tax'][i])*factor*p['margin'] if active[i] else 0. for i in range(n)]
  yrates=rates[:]
  if not p['tax_renewal']:yrates[0]=.25;yrates[5]=.25
  tax=[max(x,0)*yrates[i] for i,x in enumerate(pretax)];op=[pretax[i]-tax[i] for i in range(n)]
  if t<=5:
   pc=p['p_capex'][t-1];nc=p['n_capex'][t-1];jc=[40,35,30,25,20][t-1]+(p['j_capex_stress'] if t==1 else 0.)
   # N aggregate budget allocated to actual asset operators; H includes lower remittance budget.
   remain=nc-[40,35,30,25,20][t-1]-.5-2.5-13.
   capex=[pc-10,10,jc,.5,remain-5.,13.,2.5,5.]
   da=[80,10,40,.5,20,8,1.5,5]
   extra=p['extra_wc'] if t==1 else (-p['extra_wc']/2 if t in (3,4) and p['wc_recovery'] else 0.)
   totalwc=p['wc'][t-1]+extra;wc=[.58*totalwc,.02*totalwc,.08*totalwc,0,.20*totalwc,.08*totalwc,0,.04*totalwc]
  else:
   da=[x*factor for x in [80,10,40,.5,20,8,1.5,5]]
   # g=0 still pays maintenance capex=depreciation; not a no-maintenance perpetuity.
   capex=[da[i]+max(op[i],0)*p['g']/p['roic'] for i in range(n)];wc=[0.]*n
  capex=[capex[i] if active[i] else 0. for i in range(n)];da=[da[i] if active[i] else 0. for i in range(n)];wc=[wc[i] if active[i] else 0. for i in range(n)]
  floors=[900. if t<=5 else 300.,20.,20.,1.,70.,30.,3.,6.]
  floors=[floors[i] if active[i] else 0. for i in range(n)]
  settle=[0.]*n;newloan=0.;oldrepay=0.;externalpay=0.;externint=0.
  if t==1:
   settle=p['parent_payable_settlement'][:];cash[0]-=sum(settle)
   for i in range(n):cash[i]+=settle[i]
   newloan=p['j_funding'];cash[0]-=newloan;cash[2]+=newloan;loan+=newloan
   oldrepay=163.21408;cash[2]-=oldrepay;cash[0]+=oldrepay;loan-=oldrepay
   externalpay=old_j_external;cash[2]-=externalpay;old_j_external=0.
   cash[0]-=other_external-50.;externalpay+=other_external-50.;other_external=50.
   fund+=p['fund_call'];cash[0]-=p['fund_call']
   externint=60.04907838*.03
  elif t==2:
   externalpay=other_external;cash[0]-=externalpay;other_external=0.;externint=1.5
  interest=[x*p['yield'] if active[i] else 0. for i,x in enumerate(cash)]
  loanint=loan*p['loan_rate'] if active[2] else 0.
  # Nominal loan3% is pretax. Tax changes use own taxable profits, not dividend exemptions/loss refunds.
  financing=[-loanint+externint,0,loanint,0,0,0,0,0]
  itax=[(max(pretax[i]+interest[i]/(1-yrates[i])-financing[i],0)-max(pretax[i]+interest[i]/(1-yrates[i]),0))*yrates[i] for i in range(n)]
  profit=[op[i]+interest[i]-financing[i]-itax[i] for i in range(n)]
  operatingcash=[profit[i]+da[i]-capex[i]-wc[i] for i in range(n)]
  cash=[cash[i]+operatingcash[i] for i in range(n)]
  Jnet+=profit[2]
  for i in [2,3,4,5,6]:netbook[i]+=profit[i]
  topup=max(floors[2]-cash[2],0) if active[2] else 0.
  if topup:
   if loan+topup>p['j_loan_limit']+1e-8 or cash[0]-topup<floors[0]-1e-8:return {'feasible':False,'year':t,'reason':'J cash cannot be funded within finite parent loan/cash limits','rows':rows,'failure_cash':cash,'zero_dividend_does_not_fix':True}
   loan+=topup;cash[0]-=topup;cash[2]+=topup;newloan+=topup
  # All loan principal recovery is actual J cash; no operation-plus-loan valuation overlay.
  amort=min(loan,max(cash[2]-floors[2],0)) if t>=p['release_start'] else 0.
  loan-=amort;cash[2]-=amort;cash[0]+=amort
  exit_event={'noncash_assets_realized':0.,'gross_cash':0.,'net_equity':0.,'parent_loan_received':0.,'parent_equity_received':0.,'minority_received':0.,'asset_realization_loss':0.,'parent_book_cost_released':0.,'parent_profit_effect':0.,'cash_tax':0.}
  minority=0.;exitloss=0.
  if active[2] and t==p['j_loan_maturity'] and loan>1e-8:
   # Conditional secured recovery/disposal of the REAL J company, not a nonexistent project.
   outside_creditors=227.43*factor;gross_noncash=max(Jnet+loan+outside_creditors-cash[2],0);net_realized=gross_noncash*p['j_exit_realization']-outside_creditors;proceeds=cash[2]+net_realized
   if proceeds<0:return {'feasible':False,'year':t,'reason':'J disposal cannot pay outside creditors in full','rows':rows}
   paidloan=min(loan,proceeds);equity=max(proceeds-paidloan,0.)
   preceipt=ownership[2]*equity;mi=(1-ownership[2])*equity;lossloan=loan-paidloan;gain=preceipt-book[2]-lossloan
   # Tax basis unknown: registered*actual ownership is a conditional budget, not book cost.
   taxable=max(preceipt-taxbasis[2]*p['tax_basis_ratio'],0);ctax=(max(pretax[0]+taxable,0)-max(pretax[0],0))*yrates[0]
   cash[0]+=paidloan+preceipt-ctax;cash[2]=0.;profit[0]+=gain-ctax
   exitloss=gross_noncash*(1-p['j_exit_realization']);minority+=mi;loan=0.;active[2]=False;floors[2]=0.
   exit_event=dict(noncash_assets_realized=net_realized,gross_noncash_book=gross_noncash,gross_asset_sale_cash=gross_noncash*p['j_exit_realization'],outside_creditors_paid=outside_creditors,gross_cash=proceeds,net_equity=equity,parent_loan_received=paidloan,parent_equity_received=preceipt,minority_received=mi,asset_realization_loss=exitloss,parent_book_cost_released=book[2],parent_profit_effect=gain-ctax,cash_tax=ctax)
   cap[2]=0.;res[2]=0.;reg[2]=0.;book[2]=0.;taxbasis[2]=0.;Jnet=0.;netbook[2]=0.
  weak_exits=[]
  for i in [3,6]:
   if active[i] and t==p['weak_asset_exit_year'] and op[i]<netbook[i]*p['weak_asset_profit_hurdle']:
    outside=({3:6.90,6:24.60}[i])*factor;noncash=max(netbook[i]+outside-cash[i],0);realized=noncash*p['weak_asset_realization']-outside;gross=cash[i]+realized
    if gross<0:return {'feasible':False,'year':t,'reason':'Weak asset disposal cannot pay outside creditors in full','rows':rows}
    parent=gross*ownership[i];mi=gross*(1-ownership[i]);gain=parent-book[i];ctax=max(parent-taxbasis[i]*p['tax_basis_ratio'],0)*yrates[0]
    cash[i]=0.;cash[0]+=parent-ctax;profit[0]+=gain-ctax;minority+=mi
    weak_exits.append(dict(entity=i,gross=gross,noncash_assets_realized=realized,outside_creditors_paid=outside,gross_asset_sale_cash=noncash*p['weak_asset_realization'],book_net_assets=netbook[i],book_non_cash_net_assets=noncash,parent_proceeds=parent-ctax,minority=mi,parent_book_cost=book[i],conditional_tax_basis=taxbasis[i]*p['tax_basis_ratio'],parent_profit=gain-ctax,tax=ctax,net_realizability=p['weak_asset_realization']))
    cap[i]=0.;res[i]=0.;reg[i]=0.;book[i]=0.;taxbasis[i]=0.;netbook[i]=0.;active[i]=False;floors[i]=0.
  fundevent={'gross':0.,'net':0.,'cost':0.,'profit_effect':0.,'tax':0.}
  exit_fraction=dict(p.get('fund_exit_schedule',[])).get(t,0.)
  if exit_fraction or (not p.get('fund_exit_schedule') and t==max(p['fund_exit'],p['release_start'])):
   fund_cost=min(fund,(p['fund_start']+p['fund_call'])*exit_fraction) if exit_fraction else fund
   gross=fund_cost*p['fund_realization'];gain=gross-fund_cost;ctax=max(gain,0)*yrates[0];cash[0]+=gross-ctax;profit[0]+=gain-ctax
   fundevent=dict(gross=gross,net=gross-ctax,cost=fund_cost,profit_effect=gain-ctax,tax=ctax);fund-=fund_cost
  charge=[0.]*n;declared=[0.]*n;receipt=[0.]*n;normal=[0.]*n;special=[0.]*n;capital_events=[];nodeprofit=profit[:]
  for i in [7,1,2,3,4,5,6]:
   if not active[i]:continue
   # Pro-rata nominal capital repayment only for real direct companies, never synthetic budgets.
   if i in [2,3,4,5,6] and (i!=2 or loan<1e-8) and t>=p['capital_return_start'] and (t-p['capital_return_start'])%p['capital_return_every']==0:
    gross=min(max(cash[i]-floors[i]-max(cap[i]+nodeprofit[i],0),0),max(reg[i]-.10*REGISTER[i],0));fee=gross*p['capital_fee'];net=gross-fee
    if gross>=1.:
     portion=gross/reg[i];b=book[i]*portion;raw_tb=taxbasis[i]*portion;tb=raw_tb*p['tax_basis_ratio'];pr=net*ownership[i];gain=pr-b;ctax=max(pr-tb,0)*yrates[0]
     cash[i]-=gross;cash[0]+=pr-ctax;nodeprofit[i]-=fee;nodeprofit[0]+=gain-ctax;minority+=net*(1-ownership[i]);reg[i]-=gross;book[i]-=b;taxbasis[i]-=raw_tb
     netbook[i]-=gross
     if i==2:Jnet-=gross
     capital_events.append(dict(entity=i,gross=gross,fee=fee,net=net,parent_cash=pr-ctax,minority_cash=net*(1-ownership[i]),book_cost_released=b,conditional_tax_basis_released=tb,parent_profit=gain-ctax,tax=ctax,registered_after=reg[i],ownership=ownership[i],listed_shares_unchanged=True))
   cap[i],res[i],charge[i]=reserve_roll(cap[i],res[i],reg[i],nodeprofit[i],(p['continue_reserve'] and t<=p.get('reserve_continue_until',10000)))
   free=max(cash[i]-floors[i],0.)
   if t>=p['sub_dividend_start'] and not (i==2 and loan>1e-8):
    normal[i]=min(max(nodeprofit[i],0)*p['sub_payout'],max(cap[i],0),free)
    special[i]=min(max(cap[i]-normal[i],0),max(free-normal[i],0)) if t>=p['release_start'] else 0.
   d=normal[i]+special[i];declared[i]=d;cash[i]-=d;cap[i]-=d;receipt[i]=d*ownership[i];cash[RECV[i]]+=receipt[i];nodeprofit[RECV[i]]+=receipt[i];minority+=d*(1-ownership[i])
   if i in [2,3,4,5,6]:netbook[i]-=d
   if i==2:Jnet-=d
  # Parent capital return is conditional pro-rata redemption, NOT profit/dividend.
  # H1 parent capital reserve521.26358415 is NOT certified distributable premium.
  # Baseline excludes it entirely: only genuine nominal capital returned, premium untouched.
  # A recurring five-year window handles future batches, preserving10% initial nominal.
  refund=0.
  if p['refund'] and t==2:refund=92.6531;cash[0]-=refund;shares-=6.763;reg[0]-=6.763
  before_shares=shares;before_units=holder_units;free=max(cash[0]-floors[0],0.)
  target=p['div'][t-1]*shares if t<=5 else free
  prior_capacity=cap[0];prior_reserve=res[0];gross_profit=nodeprofit[0]
  def parent_allocation(fee):
   cc,rr,aa=reserve_roll(prior_capacity,prior_reserve,reg[0],gross_profit-fee,(p['continue_reserve'] and t<=p.get('reserve_continue_until',10000)))
   ordinary=min(target,max(free-fee,0.),max(cc,0.))
   return ordinary,cc,rr,aa
  d,cc,rr,aa=parent_allocation(0.)
  blocked=max(free-d,0.);pe={'net_to_original_holders':0.,'fee':0.,'nominal_cancelled':0.,'premium_repaid':0.,'shares_cancelled':0.,'holder_units_before':before_units,'holder_units_after':before_units,'blocked_before':blocked,'profit_effect':0.,'cash_tax_refund':0.}
  scheduled=t>=p['parent_capital_start'] and (t-p['parent_capital_start'])%p['parent_capital_every']==0
  available=(reg[0]+premium)*max(1-.10*S/reg[0],0.) if reg[0]>0 else 0.
  net=fee=0.
  if scheduled and blocked>1e-8 and available>0:
   # Solve actual cash budget including fee and the reduced current legal profit.
   low=0.;high=min(free*(1-p['parent_capital_fee']),available)
   for _ in range(70):
    mid=(low+high)/2;cost=mid*p['parent_capital_fee']/(1-p['parent_capital_fee'])
    ordinary,*_=parent_allocation(cost)
    if mid+cost+ordinary<=free:low=mid
    else:high=mid
   net=low;fee=net*p['parent_capital_fee']/(1-p['parent_capital_fee'])
   d,cc,rr,aa=parent_allocation(fee);fraction=net/(reg[0]+premium)
   nominal=reg[0]*fraction;premium_return=premium*fraction;cancel=shares*fraction
   reg[0]-=nominal;premium-=premium_return;shares-=cancel;holder_units*=1-fraction
   nodeprofit[0]-=fee
   pe=dict(net_to_original_holders=net,fee=fee,nominal_cancelled=nominal,premium_repaid=premium_return,shares_cancelled=cancel,holder_units_before=before_units,holder_units_after=holder_units,blocked_before=blocked,profit_effect=-fee,cash_tax_refund=0.,equity_fraction_cancelled=fraction,registered_after=reg[0],premium_budget_after=premium,scope='conditional pro-rata capital repayment; no new profit; original holder units reduce with shares')
  cap[0]=cc-d;res[0]=rr;charge[0]=aa;cash[0]-=d+net+fee;normal[0]=d
  original_holder_cash=(d+net)/before_shares*before_units
  if any(cash[i]<floors[i]-1e-7 for i in range(n)):return {'feasible':False,'year':t,'reason':'Named entity below necessary cash; no anonymous support','rows':rows,'failure_cash':cash,'zero_dividend_does_not_fix':True}
  # Cash bridge includes physical noncash asset sale, taxes and externally paid capital, not investment book basis.
  expected=sum(opening_cash)+sum(operatingcash)-externalpay-(p['fund_call'] if t==1 else 0)+fundevent['net']-d-net-fee-minority-refund+exit_event['noncash_assets_realized']-exit_event['cash_tax']+sum(e['noncash_assets_realized']-e['tax'] for e in weak_exits)-sum(e['fee']+e['tax'] for e in capital_events)
  assert abs(sum(cash)-expected)<1e-7,(t,sum(cash),expected)
  cash_delta=sum(cash)-sum(opening_cash)
  rows.append(dict(year=t,period_end=f'{2026+t}-10-26',operating_pretax=pretax,operating_tax=tax,operating_aftertax=op,financial_income=interest,nominal_loan_interest=loanint,incremental_financing_cash_tax=itax,node_own_profit=profit,node_total_profit=nodeprofit,capex=capex,depreciation=da,working_increase=wc,cashflow_before_internal_principal=operatingcash,old_parent_payables_settled=settle,new_J_loan=newloan,old_J_parent_receivable_collected=oldrepay,J_principal_amortization=amort,external_principal_paid=externalpay,external_interest=externint,normal_distribution=normal,special_distribution=special,declared=declared,parent_or_intermediate_received=receipt,reserve_add=charge,minority_paid=minority,J_exit=exit_event,weak_asset_exits=weak_exits,net_assets_budget=netbook[:],capital_returns=capital_events,fund_exit=fundevent,fund_call=p['fund_call'] if t==1 else 0.,listed_refund=refund,dividend=d,dividend_per_share=original_holder_cash,ordinary_dividend_current_share=d/before_shares,parent_capital_return=pe,parent_premium_budget=premium,original_holder_units=holder_units,distribution_before_cancellation_shares=before_shares,shares=shares,cash=cash[:],cash_floor=floors,capacity_budget=cap[:],reserve_budget=res[:],registered_capital_budget=reg[:],parent_investment_book_budget=book[:],conditional_tax_basis_budget=taxbasis[:],J_loan=loan,J_net_assets_budget=Jnet,active=active[:],ownership_budget_state=[ownership[i] if active[i] else 0. for i in range(n)],fund_balance=fund,cash_delta=cash_delta))
 return {'feasible':True,'rows':rows}

def value(result,r):
 if not result['feasible']:return None
 rows=result['rows'];pv=math.fsum(x['dividend_per_share']/(1+r)**x['year'] for x in rows);pv5=math.fsum(x['dividend_per_share']/(1+r)**x['year'] for x in rows[:5]);tv=math.fsum(x['dividend_per_share']/(1+r)**(x['year']-5) for x in rows if x['year']>5)
 return {'value':pv,'tv5':tv,'pv_first5':pv5,'tv_pv_fraction':1-pv5/pv,'DPS5':[x['dividend_per_share'] for x in rows[:5]]}

def cases():
 specs={'base':{},'core_low':{'r':.10,'g':.015,'roic':.14},'core_high':{'r':.09,'g':.02,'roic':.18},
 'cyclical':{'growth':[-.12,0,.08,.06,.03],'margin':.95,'extra_wc':80.,'div':[.7,.8,.95,1.05,1.1]},
 'structural':{'growth':[-.15,-.07,-.03,0,0],'margin':.8,'extra_wc':120.,'wc_recovery':False,'div':[.5,.5,.55,.6,.6],'g':0.,'roic':.095},
 'upside':{'growth':[.03,.05,.05,.04,.035],'margin':1.04,'extra_wc':10.,'div':[1,1.1,1.2,1.3,1.4],'g':.0225,'roic':.18},
 'r_105':{'r':.105},'terminal_roic_10':{'roic':.10},'j_capex_stress':{'j_capex_stress':50.},'refund_cancel':{'refund':True},
 'tax_qualification_not_renewed':{'tax_renewal':False},'continued_reserves':{'continue_reserve':True},'fund_realization50':{'fund_realization':.5},'fund_delay15':{'fund_exit':15},
 'legacy_all51_equity':{'ownership':[1,1,.51,.51,.51,.51,.51,1]},'Jingcheng_turnaround':{'aftertax_operating':[560,20,20,0,110,70,10,30]},'exclude_associate_principal':{'fund_start':94.77226667},'no_weak_asset_exit':{'weak_asset_exit_year':10000},'weak_asset_realization30':{'weak_asset_realization':.30},'weak_asset_exit20':{'weak_asset_exit_year':20},'zero_capital_tax_basis':{'tax_basis_ratio':0.},'J_maturity10':{'j_loan_maturity':10},'J_recovery30':{'j_exit_realization':.30},'capital_return_disabled':{'capital_return_start':10000},'zero_financial_yield':{'yield':0.},
 'zero_sub_opening_capacity':{'capacity':[2200,0,0,0,0,0,0,0]},'real_sub_reserves_full':{'reserve':[S/2,None,122.45/2,12.0155/2,148.5121/2,31.0204/2,51/2,None]},'no_new_J_funding':{'j_funding':0.,'j_loan_limit':163.21408},'financial_minus100':{'cash':[BASE['cash'][0]-100]+BASE['cash'][1:]},
 'minority_internal_plus300':{'parent_payable_settlement':[0,0,0,0,437.5,245,17.5,0]},'all_internal_minority_1000':{'parent_payable_settlement':[0,0,0,0,625,350,25,0]},
 'n_cash_plus100':{'cash':[BASE['cash'][0]-100,100,20,1,90,45,9,5]}}
 for delay in [3,5,8,10]:specs['release_'+str(delay)]={'sub_dividend_start':delay,'release_start':6+max(0,delay-5)}
 for name in ['structural_J_recovery30','structural_J_maturity10','structural_no_capital_return']:
  specs[name]=dict(specs['structural'],**({'j_exit_realization':.3} if 'recovery' in name else {'j_loan_maturity':10} if 'maturity' in name else {'capital_return_start':10000}))
 specs['structural_parent_return_disabled']=dict(specs['structural'],parent_capital_start=10000)
 specs['structural_parent_return30_fee5']=dict(specs['structural'],parent_capital_start=30,parent_capital_every=10,parent_capital_fee=.05)
 specs['structural_late_fund40']=dict(specs['structural'],fund_exit=40)
 specs['structural_continue_reserve']=dict(specs['structural'],continue_reserve=True)
 specs['structural_fund_batches8_40_80']=dict(specs['structural'],fund_exit_schedule=[(8,.3),(40,.3),(80,.4)])
 specs['continued_reserves_first5']=dict(continue_reserve=True,reserve_continue_until=5)
 specs['structural_continued_reserves_first5']=dict(specs['structural'],continue_reserve=True,reserve_continue_until=5)
 out={}
 for name,patch in specs.items():p=copy.deepcopy(BASE);p.update(patch);out[name]=p
 return out

def pack(o):
 q=copy.deepcopy(o)
 for c in q['cases'].values():
  raw=json.dumps(c.pop('rows'),ensure_ascii=False,separators=(',',':')).encode();c['annual_trace_sha256']=hashlib.sha256(raw).hexdigest();c['annual_trace_gzip_base64']=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
 return q

def expand(o):
 q=copy.deepcopy(o)
 for c in q['cases'].values():
  raw=gzip.decompress(base64.b64decode(c.pop('annual_trace_gzip_base64')));assert hashlib.sha256(raw).hexdigest()==c.pop('annual_trace_sha256');c['rows']=json.loads(raw)
 return q

def main():
 out={'unit':'CNY million except per share','model_as_of':'2026-10-26T08:12:00+00:00','shares':S,'nodes':NAMES,'schema':{'cash':'forecast allocation, NOT actual entity Q3 balance','capacity_budget':'constrained economic remittance / dividend capacity, NOT audited legal retained','reserve_budget':'P full equivalent register/2 supported by P surplus356.393488m; subsidiaries incremental zero start not actual balances; W/downstream null','registered_capital_budget':'real mainland registered facts with forecast proportional reductions; W/downstream no fictitious capital','tax_basis':'conditional registered*ownership basis separate from actual parent investment book cost, actual tax basis unknown','J_exit':'only if parent loan outstanding at finite maturity, conditional asset realization, creditor first/equity51%; future operation removed','parent_capital_return':'conditional recurring pro-rata cancellation, only nominal capital used; H1 parent capital reserve521.26358415 unchanged, distributable share-premium component unknown; fees reduce own profit without tax refund; dividend_per_share includes capital cash per ORIGINAL held share and retained holder units, no cancellation windfall', 'foreign':'HK businesses identified in audit, no invented PRC law or standalone cash allocated in W domestic remittance budget'},'cases':{}}
 for name,p in cases().items():
  z=run(p);z['parameters']=p;z['valuation']=value(z,p['r']);z['acceptance_scope']='permanent_discretionary_retention_counterfactual_NOT_full_realization' if name in ['continued_reserves','structural_continue_reserve'] else 'capital_return_disabled_counterfactual_NOT_adopted' if name=='structural_parent_return_disabled' else 'conditional_economic_policy';out['cases'][name]=z
  if z['feasible']:z['convergence']={str(n):value(run(p,n),p['r'])['value'] for n in [200,300,400]}
 low=out['cases']['core_low'];high=out['cases']['core_high'];assert low['feasible'] and high['feasible'];assert low['rows'][:5]==high['rows'][:5]
 out['core']={'value_range':{'low':low['valuation']['value'],'high':high['valuation']['value'],'currency':'CNY'},'distributions':low['valuation']['DPS5'],'tv5':{'low':low['valuation']['tv5'],'high':high['valuation']['tv5']}}
 out['auxiliary']={}
 for label in ['low','high']:
  p=copy.deepcopy(out['cases']['core_'+label]['parameters']);primary=out['cases']['core_'+label]['valuation']['value']
  # Conservative controlled subtraction retains all year1 entity buffers, old external debt and committed call.
  keep_cash=sum([900,20,20,1,70,30,3,6])+216.83499838+24
  p['cash'][0]-=FIN-keep_cash;p['fund_start']=0.;p['weak_asset_exit_year']=10000
  shadow=run(p);assert shadow['feasible'];shadow['parameters']=p;shadow['valuation']=value(shadow,p['r']);out['cases']['auxiliary_cash_shadow_'+label]=shadow
  increment=primary-shadow['valuation']['value'];op=702.4*(1+p['g'])*(1-p['g']/p['roic'])/(p['r']-p['g'])/S
  out['auxiliary'][label]={'normalized_operating_profit':702.4,'operating_value_per_share':op,'incremental_existing_financial_and_weak_asset_realization_value':increment,'value':op+increment,'retained_opening_cash_budget':keep_cash,'scope':'conservative auxiliary retaining initial temporary buffers and obligations; not added on top of main DCF'}
 q=pack(out);assert expand(q)==out;Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(q,ensure_ascii=False,separators=(',',':'))+'\n');print(json.dumps({'core':out['core'],'cases':{n:{'feasible':c['feasible'],'value':c['valuation'],'failure':c.get('reason')} for n,c in out['cases'].items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--expand':print(json.dumps(expand(json.loads(Path(sys.argv[2]).read_text())),ensure_ascii=False,separators=(',',':')))
 else:main()
