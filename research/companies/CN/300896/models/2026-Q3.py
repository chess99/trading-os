#!/usr/bin/env python3
"""IMEIK Q3 owner cash model. Stdlib only, no input files/network/quotes.
Amounts CNY 100m; shares 100m; rolling Y1 starts 2026-10-28.
All entity allocations after 2026H1 are ECONOMIC BUDGETS, not legal certifications.
"""
import json, math, copy
SHARES=3.02592061
LIQUID=(920008167.12+2692119303.62+759941769.46+155086805.52)/1e8
EQUITY_OTHER=(1078814486.65-872085052.54+305359949.84)/1e8
# Name, ownership, income tax, cash, retained profit budget, reserve, reserve cap,
# five year net-external revenue; five year EBIT after cash RD/marketing; net capex
DATA=[
 ['parent',1,.17,38.5,43.5,1.512960305,1.512960305,[16.8,16.8,17.3,17.8,18.3],[.54,.53,.525,.52,.51],[1.25,1.15,.95,.8,.75]],
 ['nobot',1,.15,3,-1.3,0,2.99155,[2.6,2.85,3.15,3.4,3.6],[.28,.29,.30,.30,.30],[.18,.2,.22,.22,.2]],
 ['beijing_sales',1,.25,.15,-.13,0,.005,[0,0,0,0,0],[-.20,-.15,-.08,0,0],[.01,.01,0,0,0]],
 ['regen',.7*.99447,.22,1.1,.1,.05,.2491625772,[2.8,3.1,3.4,3.65,3.9],[.36,.36,.35,.34,.33],[.20,.22,.25,.25,.25]],
 ['peiqilong',.575,.15,.7,.05,.02,.17,[.45,.5,.56,.62,.68],[.09,.12,.15,.18,.20],[.04,.05,.06,.06,.06]],
 ['aimeichuang',.52,.15,.5,-.25,0,.09177083,[.18,.23,.30,.38,.45],[-.4,-.2,0,.08,.12],[.06,.06,.06,.05,.05]],
 ['weimai',.8516,.25,.7,-.35,0,.23234812,[.2,.32,.48,.65,.8],[-.4,-.15,.05,.12,.16],[.10,.12,.12,.12,.10]],
 ['zhongxing',.75,.15,.2,-.08,0,.025,[.12,.15,.18,.21,.24],[-.1,0,.08,.12,.15],[.025,.025,.025,.025,.025]],
 # Residual non-operating CASH allocation proxy, not an identified legal entity.
 # 99.75% is disclosed Qingdao Borui Aimei interest (H1 p173); cash/basis
 # allocations and reserve are budgets, not that partnership's disclosed balances.
 ['other_treasury',.9975,.25,LIQUID-44.85,0,0,.30,[0]*5,[0]*5,[0]*5],
]
# base consolidated net external revenue includes sales-company commission losses,
# does not add related party turnover to parent revenue.
BASE={'r':.105,'g':.015,'yield':.015,'profit_scale':1.,'revenue_scale':1.,'recovery':.70,
 'release':.12,'capex_scale':1.,'lag_extra':0,'arbitration':0.,'parent_cash_shift':0.,
 'extra_receipt':0.,'tax_shift':0.,'structural':False,'cycle':False,'optimistic':False,
 'shares':SHARES,'nci_fund':True,'reserve_stress':False,'regen_share':.696129,'capacity_method':False,'treasury_exit':12,'treasury_ownership':.9975,'treasury_basis_factor':1.,'debt_payer':'parent','parent_ur_budget':43.5}
CASES={
 'core_low':dict(r=.11,g=.01,yield_=.01,profit_scale=.97),
 'base':{},
 'core_high':dict(r=.10,g=.02,yield_=.02,profit_scale=1.03),
 'cyclical':dict(cycle=True,capex_scale=1.10,lag_extra=1),
 'structural':dict(structural=True,recovery=.45,release=.08),
 'optimistic':dict(optimistic=True,recovery=.85,release=.20),
 'r_plus_1pt':dict(r=.115), 'operating_profit_minus_12pct':dict(profit_scale=.88),
 'slow_cash_release':dict(release=.04), 'extra_capital_30pct':dict(capex_scale=1.3),
 'foreign_lag_4years':dict(lag_extra=2), 'cash_at_parent_minus_5':dict(parent_cash_shift=-5.),
 'arbitration_cash_16':dict(arbitration=16.,nci_fund=False),
 'tax_plus_5pt':dict(tax_shift=.05), 'all_employee_receipts_incremental':dict(extra_receipt=.56300055),
 'deficits_and_reserves':dict(reserve_stress=True),
 'regen_legal_85_only':dict(regen_share=.595),
 'no_nci_recapitalisation':dict(nci_fund=False),
 'treasury_exit_delayed_25':dict(treasury_exit=25),
 'debt_paid_by_52pct_sub':dict(debt_payer='aimeichuang'),
 'treasury_ownership_57_5pct':dict(treasury_ownership=.575),
 'treasury_ownership_100pct':dict(treasury_ownership=1.),
 'treasury_basis_50pct':dict(treasury_basis_factor=.5),
 'treasury_basis_150pct':dict(treasury_basis_factor=1.5),
 'parent_ur_41':dict(parent_ur_budget=41.),
 'parent_ur_46':dict(parent_ur_budget=46.),
}
def config(name):
 p=BASE.copy();p.update(CASES[name]);p['yield']=p.pop('yield_',p['yield']);return p

def legal_step(cash,ur,reserve,cap,profit,free_cash,floor,wanted,debt_due=0.):
 """Actual production waterfall: cover losses BEFORE reserve; cash after debt.
 profit includes accounting gain, free_cash includes the corresponding actual cash.
 No shareholder funding generated here; caller explicitly supplies it.
 """
 old=(cash,ur,reserve)
 eligible=max(0.,profit+min(ur,0.))
 appropriation=min(max(0.,cap-reserve),.10*eligible)
 ur+=profit-appropriation;reserve+=appropriation
 cash+=free_cash-debt_due
 dividend=min(max(0.,wanted),max(0.,ur),max(0.,cash-floor))
 cash-=dividend;ur-=dividend
 assert abs(cash-(old[0]+free_cash-debt_due-dividend))<1e-7
 assert abs(ur+reserve-(old[1]+old[2]+profit-dividend))<1e-7
 assert dividend<=max(0.,old[0]+free_cash-debt_due-floor)+1e-8
 return cash,ur,reserve,dividend,appropriation

def disposal(cost,proceeds,tax=.25):
 # Cost and proceeds are attributable to the parent. No cash subtraction of cost:
 # it was already invested. Conservative tax budget, no immediate loss tax credit.
 gain=proceeds-cost;cash_tax=max(0.,gain)*tax
 return gain,cash_tax,gain-cash_tax

def budget(e,t,p):
 name,own,tax,cash,ur,res,cap,revs,margins,capex=e
 if p['capacity_method']:
  # Independent sustainable earnings capacity, after income tax and cash RD.
  # Tuple: normalized external revenue, normalized after-tax operating earnings.
  independent={'parent':(18.,7.3),'nobot':(3.2,1.05),'beijing_sales':(0.,-.12),
   'regen':(3.,.90),'peiqilong':(.7,.05),'aimeichuang':(.3,0.),
   'weimai':(.5,.05),'zhongxing':(.25,.02),'other_treasury':(0.,0.)}
  revenue,earnings=independent[name]
  scale=1.01**min(t,8)*.975**min(max(t-8,0),12)*1.01**max(t-20,0)
  rev=revenue*scale;profit=earnings*scale
  if name=='beijing_sales' and t>3:profit=0.
  investment=max(0.,profit)*.18
  floor=.25*rev+3.5*(1.01**max(0,t-5)) if name=='parent' else .2*rev+.1
  if name in ('beijing_sales','other_treasury'):floor=.05
  if name=='other_treasury' and t>=p['treasury_exit']:floor=0.
  return rev,profit/(1-tax) if profit>0 else profit,profit,investment,floor
 j=min(t-1,4);rev=revs[j];margin=margins[j]
 if t>5:
  rev*= (1+p['g'])**(t-5)
  # five-year fade of mature core pricing advantage after explicit years
  if name=='parent':margin-=min(t-5,5)*.008
 if name=='beijing_sales':
  op=margins[j] if t<=5 else 0.
 else:op=rev*margin
 rev*=p['revenue_scale'];op*=p['profit_scale']*p['revenue_scale']
 if p['cycle']:
  factor=[.78,.85,.94][t-1] if t<=3 else 1.
  rev*=factor;op*=factor
  if t<=3:op-=.12 if name=='parent' else .015
 if p['structural']:
  factor=(.94**min(t,10)) if name in ('parent','nobot','regen') else .80
  rev*=factor;op*=factor
  if name=='parent':op-=rev*.10
  if name in ('aimeichuang','weimai'):op=-.03*(1+p['g'])**max(0,t-5) if t<=4 else .01*(1+p['g'])**max(0,t-5)
 if p['optimistic']:
  factor=1.08**min(t,5) if name in ('nobot','regen','weimai') else 1.025**min(t,5)
  rev*=factor;op*=factor
  if name=='parent':op+=rev*.025
 rate=min(.35,tax+p['tax_shift']);nopat=op-max(0.,op)*rate
 if t<=5:netinvest=capex[j]*p['capex_scale']
 else:
  # required incremental capital, not release of historical working capital:
  # two CNY incremental capital per CNY new revenue, including economic ramp needs.
  netinvest=rev*p['g']/(1+p['g'])*2*p['capex_scale']
 floor=(.20*rev+.10) if name!='parent' else .25*rev+3.5*(1+p['g'])**max(0,t-5)
 if name=='other_treasury':floor=.05 if t<p['treasury_exit'] else 0.
 if name=='beijing_sales':floor=.05
 # In the structural case no terminal negative-cash projects: redesign by year5
 # is budgeted above; capital still funded, no automatic capital release.
 return rev,op,nopat,netinvest,floor

def run(p,N=600):
 es={e[0]:dict(c=e[3],u=e[4],z=e[5],cap=e[6]) for e in DATA}
 es['parent']['c']+=p['parent_cash_shift']+p['extra_receipt']
 es['other_treasury']['c']-=p['parent_cash_shift']
 es['parent']['u']=p['parent_ur_budget']
 if p['reserve_stress']:
  for n in es:
   if n!='parent':es[n]['u']-=.5;es[n]['cap']+=.5
 treasury_basis=max(0.,es['other_treasury']['c']-es['other_treasury']['u']-es['other_treasury']['z'])*p['treasury_ownership']*p['treasury_basis_factor']
 initial_treasury_basis=treasury_basis
 pending=[];rows=[];entity_rows=[];last_rev={e[0]:e[7][0] for e in DATA}
 # Group debt/current obligations .3186925739. Q3 says .06 short bank is at
 # a controlled subsidiary, but does not identify the payer of every balance.
 # Base assigns ALL economic burden to parent as a funding/settlement budget,
 # not a claim of legal parent debt; alternate controlled52% payer tests NCI.
 # Pay once Y1; future operating leases are cash costs inside margins.
 debt=.3186925739
 for t in range(1,N+1):
  start_cash=sum(s['c'] for s in es.values());start_receivable=sum(x[2] for x in pending)
  receipts=sum(x[2] for x in pending if x[0]==t)
  pending=[x for x in pending if x[0]!=t]
  parent_profit_add=0.;parent_dividend_declared=0.;injections=0.;nci_paid=0.;nci_injected=0.;wht=0.;external_fc=0.;sum_nopat=0.;sum_inv=0.;sum_rev=0.;interest_total=0.;disposal_gain=0.;disposal_tax=0.;basis_removed=0.;basis_added=0.
  for e in DATA[1:]:
   name,own,tax,_,_,_,cap,*_=e;s=es[name]
   if name=='regen':own=p['regen_share']
   if name=='other_treasury':own=p['treasury_ownership']
   opening=(s['c'],s['u'],s['z'])
   sub_due=debt if t==1 and name==p['debt_payer'] else 0.
   opening_basis=treasury_basis if name=='other_treasury' else None
   rev,op,profit,invest,floor=budget(e,t,p)
   loss=p['arbitration'] if name=='regen' and t==2 else 0.
   interest=s['c']*p['yield'];interest_total+=interest
   profit+=interest-loss;fc=profit-invest
   sum_nopat+=profit-interest+loss;sum_inv+=invest;sum_rev+=rev
   support=max(0.,floor-s['c']-fc+sub_due)
   if support:
    # pro-rata recapitalisation budget, or parent bears full stress financing
    parent_support=support*own if p['nci_fund'] else support
    injections+=parent_support;nci_injected+=support-parent_support;s['c']+=support
    if name=='other_treasury':treasury_basis+=parent_support;basis_added+=parent_support
   wanted=max(0.,profit)*(.60 if t<=5 else .90)+max(0.,s['c']-floor)*(.06 if t<=5 else p['release'])
   s['c'],s['u'],s['z'],d,z=legal_step(s['c'],s['u'],s['z'],s['cap'],profit,fc,floor,wanted,sub_due)
   capital_return=0.;closing_release_ur=0.;closing_release_reserve=0.
   if name=='other_treasury' and t==p['treasury_exit']:
    # Orderly authorized capital reduction/liquidation budget, no stranded
    # financial principal. Cash return minus tracked investment basis creates
    # disposal gain/loss in parent legal earnings, but basis is not paid twice.
    capital_return=s['c'];closing_release_ur=s['u'];closing_release_reserve=s['z']
    basis_removed=treasury_basis
    disposal_gain,disposal_tax,net_disposal_profit=disposal(treasury_basis,capital_return*own)
    parent_profit_add+=net_disposal_profit;treasury_basis=0.
    s['c']=0.;s['u']=0.;s['z']=0.;s['cap']=0.
   nci_paid+=(d+capital_return)*(1-own)
   taxloss=d*own*(.05 if name=='regen' else 0.);wht+=taxloss
   upstream=d*own-taxloss
   parent_profit_add+=upstream;parent_dividend_declared+=upstream
   lag=2+p['lag_extra'] if name=='regen' else 1
   pending.append((t+lag,name,upstream+capital_return*own))
   external_fc+=fc
   entity_rows.append(dict(year=t,entity=name,ownership=own,start_cash=opening[0],start_ur=opening[1],start_reserve=opening[2],debt_paid=sub_due,start_parent_cost_basis=opening_basis,end_parent_cost_basis=treasury_basis if name=='other_treasury' else None,exit_released_ur=closing_release_ur,exit_released_reserve=closing_release_reserve,rev=rev,nopat=profit-interest+loss,profit=profit,net_invest=invest,financial_income=interest,legal_reserve=z,dividend=d,capital_return=capital_return,owner_declared=upstream,nci_paid=(d+capital_return)*(1-own),support=support,parent_support=support*own if p['nci_fund'] else support,nci_support=support*(1-own) if p['nci_fund'] else 0.,loss=loss,end_cash=s['c'],end_ur=s['u'],end_reserve=s['z']))
  s=es['parent'];opening_parent=(s['c'],s['u'],s['z']);rev,op,profit,invest,floor=budget(DATA[0],t,p)
  sum_nopat+=profit;sum_inv+=invest;sum_rev+=rev
  interest=s['c']*p['yield'];interest_total+=interest
  # huons stake dividend: no capitalization of carrying amount in addition.
  huons=([.01,.02,.04,.06,.08][t-1] if t<=5 else .10*(1+p['g'])**(t-5))
  huons*=.6 if p['structural'] else 1.
  # remaining associates and funds run-off proceeds. Loss affects legal profit,
  # return of historical principal increases cash only. No separate asset add-on.
  recovery=EQUITY_OTHER*p['recovery']/5 if 6<=t<=10 else 0.
  book_removed=EQUITY_OTHER/5 if 6<=t<=10 else 0.
  # share compensation is noncash but reduces legal capacity; full share dilution
  # already counted. Remaining budget 0.50 split Y1/Y2, no second cash charge.
  sbc=[.35,.15][t-1] if t<=2 else 0.
  legal_profit=profit+interest+parent_profit_add+huons+recovery-book_removed-sbc
  fc=profit+interest-invest+receipts+huons+recovery-injections-disposal_tax
  due=debt if t==1 and p['debt_payer']=='parent' else 0.
  total_due=debt if t==1 else 0.
  wanted=max(0.,profit+receipts+interest+huons)*(.55 if t<=5 else .85)
  if t<=5:
   # Common budget across core endpoints; scenario-specific voluntary cuts.
   wanted=[1.4,1.45,1.6,1.75,1.8][t-1]*SHARES
   if p['cycle'] and t<=3:wanted*=[.78,.85,.94][t-1]
   if p['structural']:wanted*=.75
  else:wanted+=p['release']*max(0.,s['c']-floor)
  if s['c']+fc-due<floor-1e-9:raise ValueError('funding not feasible: '+str((t,p)))
  s['c'],s['u'],s['z'],d,z=legal_step(s['c'],s['u'],s['z'],s['cap'],legal_profit,fc,floor,wanted,due)
  external_fc+=profit+interest-invest+huons+recovery
  end_cash=sum(s['c'] for s in es.values());end_receivable=sum(x[2] for x in pending)
  # consolidation including declared cash in transit/receivable. A dividend
  # cannot vanish between declaration and collection or enter P&L twice.
  lhs=end_cash+end_receivable
  rhs=start_cash+start_receivable+external_fc+nci_injected-nci_paid-wht-d-total_due-disposal_tax
  assert abs(lhs-rhs)<1e-6,(t,lhs,rhs)
  rows.append(dict(year=t,revenue=sum_rev,nopat=sum_nopat,net_invest=sum_inv,financial_income=interest_total,group_cash=end_cash,upstream_receivable=end_receivable,parent_cash=s['c'],parent_ur=s['u'],parent_reserve=s['z'],group_reserve=sum(v['z'] for v in es.values()),group_ur=sum(v['u'] for v in es.values()),parent_legal_profit=legal_profit,parent_receipts=receipts,parent_declared=parent_dividend_declared,parent_investment_income=parent_profit_add,parent_support=injections,nci_paid=nci_paid,nci_injected=nci_injected,withholding=wht,debt_paid=total_due,parent_debt_paid=due,treasury_disposal_gain=disposal_gain,treasury_disposal_tax=disposal_tax,treasury_basis_removed=basis_removed,treasury_basis_added=basis_added,treasury_basis_end=treasury_basis,asset_recovery=recovery,huons=huons,dividend=d,dps=d/p['shares']))
  entity_rows.append(dict(year=t,entity='parent',ownership=1,start_cash=opening_parent[0],start_ur=opening_parent[1],start_reserve=opening_parent[2],capital_return=0,debt_paid=due,treasury_basis_end=treasury_basis,treasury_disposal_gain=disposal_gain,treasury_disposal_tax=disposal_tax,rev=rev,nopat=profit,profit=legal_profit,net_invest=invest,financial_income=interest,legal_reserve=z,dividend=d,owner_declared=d,nci_paid=0,support=-injections,loss=0,end_cash=s['c'],end_ur=s['u'],end_reserve=s['z']))
 # tail at N: verify actual future holder cash normalized to g has converged.
 ds=[x['dps'] for x in rows]
 r=p['r'];g=p['g']
 tail=ds[-1]*(1+g)/(r-g)
 pv=sum(d/(1+r)**(i+1) for i,d in enumerate(ds))+tail/(1+r)**N
 tv5=sum(ds[i]/(1+r)**(i-4) for i in range(5,N))+tail/(1+r)**(N-5)
 pv5=sum(ds[i]/(1+r)**(i+1) for i in range(5))
 assert abs(pv-pv5-tv5/(1+r)**5)<1e-8
 normalized=[ds[-j]/(1+g)**(N-j+1) for j in range(1,6)]
 convergence=max(normalized)/min(normalized)-1
 state_convergence={}
 for field in ('group_cash','upstream_receivable','parent_cash','parent_ur','group_ur'):
  ns=[rows[-j][field]/(1+g)**(N-j+1) for j in range(1,6)]
  state_convergence[field]=(max(ns)-min(ns))/max(abs(x) for x in ns)
 state_convergence['reserve_absolute_change']=abs(rows[-1]['group_reserve']-rows[-5]['group_reserve'])
 if N>=400:assert all(v<.001 for k,v in state_convergence.items() if k!='reserve_absolute_change'),state_convergence
 assert all(0<=v['z']<=v['cap']+1e-8 for v in es.values())
 assert len(entity_rows)==N*len(DATA)
 return dict(initial_treasury_cost_basis=initial_treasury_basis,value=pv,tv5=tv5,dps5=ds[:5],tv_pv_share=1-pv5/pv,tail_at_N=tail,terminal_convergence=convergence,state_convergence=state_convergence,tail_present_value=tail/(1+r)**N,rows=rows,entities=entity_rows,params=p)

def auxiliary(r=.105):
 """Normalized earnings capacity / finite franchise fade, using exactly the
 same ordinary-holder legal/cash/debt/NCI bridge as main. No spot cash add-on.
 Earnings grow1% for8yr, fade2.5% for12yr, then grow1%; renewal investment18%.
 This is not residual income and does not recycle main revenue/margin forecasts.
 """
 p=BASE.copy();p.update(r=r,g=.01,yield_=.012,recovery=.65,capacity_method=True)
 p['yield']=p.pop('yield_')
 return run(p)

def tests():
 # Loss first: opening -5, profit8 -> reserve0.3 not0.8; UR2.7.
 a=legal_step(20,-5,0,10,8,8,2,100);assert all(abs(x-y)<1e-10 for x,y in zip(a,(25.3,0,.3,2.7,.3)))
 # reserve cap: only .2 required; cash after debt2 and floor3 limits payout5.
 b=legal_step(7,9,.8,1,3,3,3,100,2);assert all(abs(x-y)<1e-10 for x,y in zip(b,(3,6.8,1,5,.2)))
 c=legal_step(1,100,0,0,0,0,2,100);assert c[3]==0
 # Full diluted-share arithmetic on same valuation engine.
 p=config('base');x=run(p,80);p['shares']*=2;y=run(p,80)
 assert abs(x['value']/2-y['value'])<1e-9
 assert max(abs(a/2-b) for a,b in zip(x['dps5'],y['dps5']))<1e-9
 assert disposal(4,5)==(1,.25,.75)
 assert disposal(5,4)==(-1,0,-1)
 return {'disposal_gain_case':disposal(4,5),'disposal_loss_case':disposal(5,4),'loss_first':a,'reserve_debt_cash':b,'cash_shortfall':c,'share_doubling':'passed'}

def main():
 outputs={n:run(config(n)) for n in CASES}
 conv={n:{str(k):run(config(n),k)['value'] for k in (400,600,800)} for n in CASES}
 for n,v in conv.items():assert abs(v['600']-v['800'])<.003
 for x in outputs.values():
  assert x['terminal_convergence']<.001
  for row in x['rows']:assert row['parent_cash']>=0 and row['group_cash']>=0 and row['dividend']>=0
 aux_conv={str(r):{str(k):run(dict(auxiliary(r)['params']),k)['value'] for k in (400,600,800)} for r in (.11,.10)}
 for v in aux_conv.values():assert abs(v['600']-v['800'])<.003
 print(json.dumps(dict(units='CNY 100m; shares100m',liquid=LIQUID,other_equity_book=EQUITY_OTHER,raw_budgets=DATA,scenarios=outputs,auxiliary=[auxiliary(.11),auxiliary(.10)],tests=tests(),convergence=conv,auxiliary_convergence=aux_conv),ensure_ascii=False,sort_keys=True,separators=(',',':')))
if __name__=='__main__':main()
