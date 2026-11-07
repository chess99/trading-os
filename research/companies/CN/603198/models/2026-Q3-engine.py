#!/usr/bin/env python3
"""Standalone 603198 common-equity model. Monetary units: CNY bn; shares bn.
Annual periods are future 12-month economic approximations from information_cutoff.
No price-dependent return/IRR or trading outputs. Standard-library only.
"""
from __future__ import annotations
import math,json,gzip,pathlib,copy,sys
ROOT=pathlib.Path(__file__).resolve().parent
BASE={
 'name':'base','revenue':[6.65,6.95,7.25,7.55,7.85],
 'margin':[.315,.317,.320,.322,.322],
 'capex':[.85,.85,.75,.55,.45],'da':[.34,.36,.38,.40,.42],
 'dnwc':[.15,.15,.16,.16,.17],
 'shares':.8,'liquid0':(108466812.17+3829323294.15-28044176.95-9661965.57)/1e9,
 'illiquid0':290064588.90/1e9,'debt0':(529232678.70+684086.85)/1e9,
 'reserve':.60,'yield_aftertax':.02,'debt_cost_aftertax':.025*.75,
 'repayment':[.10,.10,.10,.10,.12991676555],
 'fund_calls':[.05,0,0,0,0], # prudently reserve H1 uncalled part; acquired fund asset credited
 'payout_requested':[1.2,1.28,1.36,1.44,1.52],
 'parent_liquid0':(619163841.05+2877724910.56-9661965.57)/1e9,
 'parent_retained0':6790162572.55/1e9,'sub_retained0':0.0,
 'parent_share_profit':.34,'parent_share_da':.65,'parent_share_capex':.90,'parent_share_nwc':.95,
 'upstream_payout':.80,'sub_legal_reserve_ratio':.10,'upstream_receipt_fraction':[1,1,1,1,1],
 'internal_payable0':(2486313498.43-140488142.84)/1e9,
 'internal_settlement':[.30,.30,.30,.30,.30],
 'parent_floor':.20,'sub_floor':.10,'parent_cash_opening_shift':0,
 'k':.09,'g':.0225,'terminal_roic':.20,
 'terminal_illiquid_recovery':1.0,'terminal_liquid_release_delay':2.0,'terminal_illiquid_release_delay':3.0,'liquid_loss0':0.0,
 'scope':'Group operations, listed parent dividend payer, mainly wholly-owned operating subsidiaries. Minor equity ring-fenced at opening book value; projected margins are common-attributable.'}

def finite(x):return isinstance(x,(int,float)) and math.isfinite(x)
def validate(p):
 for key in ['revenue','margin','capex','da','dnwc','repayment','fund_calls','payout_requested','upstream_receipt_fraction','internal_settlement']:
  a=p[key]
  if len(a)!=5 or not all(finite(x) for x in a): raise ValueError('five finite periods required: '+key)
 for key in ['shares','liquid0','illiquid0','debt0','reserve','yield_aftertax','debt_cost_aftertax','parent_liquid0','parent_retained0','sub_retained0','parent_share_profit','parent_share_da','parent_share_capex','parent_share_nwc','upstream_payout','sub_legal_reserve_ratio','internal_payable0','parent_floor','sub_floor','k','g','terminal_roic','terminal_illiquid_recovery','terminal_liquid_release_delay','terminal_illiquid_release_delay','liquid_loss0','parent_cash_opening_shift']:
  if not finite(p[key]):raise ValueError('finite scalar required: '+key)
 if not (p['shares']>0 and 0<p['k']<1 and -.1<p['g']<p['k'] and p['terminal_roic']>max(0,p['g'])):raise ValueError('invalid shares/discount/growth/reinvestment domain')
 for key in ['parent_share_profit','parent_share_da','parent_share_capex','parent_share_nwc','upstream_payout','sub_legal_reserve_ratio','terminal_illiquid_recovery']:
  if not 0<=p[key]<=1:raise ValueError('ratio domain: '+key)
 if not all(x>0 for x in p['revenue']) or not all(0<=x<=.7 for x in p['margin']):raise ValueError('operating domain')
 for key in ['capex','da','repayment','fund_calls','payout_requested','internal_settlement']:
  if any(x<0 for x in p[key]):raise ValueError('nonnegative: '+key)
 if any(not 0<=x<=1 for x in p['upstream_receipt_fraction']):raise ValueError('receipt fraction')
 if not(0<=p['terminal_liquid_release_delay']<=20 and 0<=p['terminal_illiquid_release_delay']<=20):raise ValueError('release delay domain')
 for key in ['liquid0','illiquid0','debt0','reserve','parent_liquid0','internal_payable0','parent_floor','sub_floor']:
  if p[key]<0:raise ValueError('nonnegative balance: '+key)
 if p['yield_aftertax']<0 or p['debt_cost_aftertax']<0:raise ValueError('negative funding rate')
 if sum(p['repayment'])>p['debt0']+1e-8:raise ValueError('over-repayment')
 if sum(p['internal_settlement'])>p['internal_payable0']+1e-8:raise ValueError('over-settlement')
 if p['liquid_loss0']<0 or p['liquid_loss0']>p['liquid0']:raise ValueError('financial loss domain')

def project(p):
 """The same function computes every formal path and all hand-check special cases."""
 validate(p)
 cash=p['liquid0']-p['liquid_loss0'];illiquid=p['illiquid0'];debt=p['debt0']
 parent=p['parent_liquid0']+p['parent_cash_opening_shift']-p['liquid_loss0']
 par_ret=p['parent_retained0'];sub_ret=p['sub_retained0'];pending=0.;payable=p['internal_payable0'];rows=[]
 if not (p['parent_floor']<=parent<=cash-p['sub_floor']+1e-8):raise ValueError('infeasible initial entity liquidity')
 for i in range(5):
  start=cash;ps=parent;ds=debt;irs=illiquid;ars=pending;rets=par_ret;srets=sub_ret
  op=p['revenue'][i]*p['margin'][i]
  fi=max(cash-p['reserve'],0)*p['yield_aftertax'];interest=debt*p['debt_cost_aftertax']
  netprofit=op+fi-interest
  ocf=op+p['da'][i]-p['dnwc'][i]
  operating_fcf=ocf-p['capex'][i]
  fund=p['fund_calls'][i];repay=min(p['repayment'][i],debt);debt-=repay;illiquid+=fund
  cash_pre=cash+operating_fcf+fi-interest-fund-repay
  if cash_pre<p['reserve']-1e-8:raise ValueError('operational funding infeasible before any common payout')
  # Current sub earnings and legal reserve, not historical H1 dividend annualized.
  sub_op=op*(1-p['parent_share_profit'])
  available_sub_legal=max(sub_ret+sub_op*(1-p['sub_legal_reserve_ratio']),0)
  declared=min(max(sub_op*p['upstream_payout'],0),available_sub_legal)
  sub_ret+=sub_op*(1-p['sub_legal_reserve_ratio'])-declared
  # Legal declaration adds parent income once; collecting past AR does not.
  parent_fi=fi*(parent/cash if cash else 0)
  parent_own_profit=op*p['parent_share_profit']+parent_fi-interest
  par_ret+=parent_own_profit+declared
  settlement=min(p['internal_settlement'][i],payable);payable-=settlement
  own_parent_cash=parent_own_profit+p['da'][i]*p['parent_share_da']-p['capex'][i]*p['parent_share_capex']-p['dnwc'][i]*p['parent_share_nwc']-fund-repay-settlement
  parent_pre_receipt=parent+own_parent_cash
  # Internal settlement receives actual cash at subsidiary, and cancels actual payable only.
  sub_cash_pre_receipt=cash_pre-parent_pre_receipt
  receipt_wanted=ars+declared*p['upstream_receipt_fraction'][i]
  receipt=min(receipt_wanted,max(sub_cash_pre_receipt-p['sub_floor'],0))
  pending=ars+declared-receipt
  parent_pre=parent_pre_receipt+receipt
  # Dividend is always the least of budget, legal reserve, real parent cash and group liquidity.
  capacity=max(0,min(par_ret,parent_pre-p['parent_floor'],cash_pre-p['reserve']))
  paid=min(p['payout_requested'][i],capacity)
  parent=parent_pre-paid;cash=cash_pre-paid;par_ret-=paid
  subsidiary_cash=cash-parent
  if parent<p['parent_floor']-1e-8 or subsidiary_cash<p['sub_floor']-1e-8:raise ValueError('entity funding infeasible')
  assert abs(cash-(start+operating_fcf+fi-interest-fund-repay-paid))<1e-9
  assert abs(parent-(ps+own_parent_cash+receipt-paid))<1e-9
  assert abs(par_ret-(rets+parent_own_profit+declared-paid))<1e-9
  assert abs(pending-(ars+declared-receipt))<1e-9
  assert abs((cash+illiquid-debt)-(start+irs-ds+operating_fcf+fi-interest-paid))<1e-9
  rows.append(dict(year=i+1,revenue=p['revenue'][i],op_net_profit=op,net_profit=netprofit,da=p['da'][i],dnwc=p['dnwc'][i],capex=p['capex'][i],operating_cf=ocf,operating_fcf=operating_fcf,financial_income=fi,debt_interest=interest,repayment=repay,fund_call=fund,illiquid_asset=illiquid,debt=debt,liquid_before_dividend=cash_pre,requested_dividend=p['payout_requested'][i],actual_dividend=paid,dps=paid/p['shares'],cash_end=cash,parent_own_profit=parent_own_profit,parent_own_cash=own_parent_cash,sub_dividend_declared=declared,sub_dividend_received=receipt,dividend_receivable=pending,parent_retained=par_ret,subsidiary_retained=sub_ret,parent_cash_end=parent,subsidiary_cash_end=subsidiary_cash,internal_settlement=settlement,internal_payable=payable,dividend_capacity=capacity,dividend_cut=p['payout_requested'][i]-paid))
 # Operating going-concern value includes all necessary capital, including operating cash floor.
 end_op=rows[-1]['op_net_profit'];g=p['g'];k=p['k'];roi=p['terminal_roic']
 reinvest=max(g,0)/roi # shrinking operation does not mechanically release inventory/property
 terminal_cashflow=end_op*(1+g)*(1-reinvest)
 op_terminal=terminal_cashflow/(k-g)
 financial_terminal_raw=max(cash-p['reserve'],0)+illiquid*p['terminal_illiquid_recovery']-debt
 financial_terminal=max(cash-p['reserve'],0)*((1+p['yield_aftertax'])/(1+k))**p['terminal_liquid_release_delay']+illiquid*p['terminal_illiquid_recovery']/(1+k)**p['terminal_illiquid_release_delay']-debt
 terminal=op_terminal+financial_terminal
 pv_div=sum(r['actual_dividend']/(1+k)**r['year'] for r in rows)
 pv_terminal=terminal/(1+k)**5
 value=(pv_div+pv_terminal)/p['shares']
 # Auxiliary: earnings-power capitalization of first-three-year mean operating earnings,
 # with explicit transition cash-capital adjustment vs sustainable reinvestment.
 norm=sum(r['op_net_profit'] for r in rows[:3])/3
 multiple=(1+g)*(1-reinvest)/(k-g)
 capital_gap=sum((r['capex']+r['dnwc']-r['da']-r['op_net_profit']*reinvest)/(1+k)**r['year'] for r in rows)
 opening_financial=cash*0+p['liquid0']-p['liquid_loss0']-p['reserve']+p['illiquid0']-p['debt0']
 auxiliary=(norm*multiple+opening_financial-capital_gap)/p['shares']
 return dict(name=p['name'],inputs=p,years=rows,terminal_operating_cashflow=terminal_cashflow,terminal_operating_value=op_terminal,terminal_financial_value=financial_terminal,terminal_financial_value_raw=financial_terminal_raw,terminal_equity_value=terminal,terminal_per_share=terminal/p['shares'],pv_distributions=pv_div,pv_terminal=pv_terminal,value_per_share=value,terminal_pv_share=pv_terminal/(pv_div+pv_terminal),auxiliary_normalized_profit=norm,auxiliary_multiple=multiple,auxiliary_transition_capital_gap=capital_gap,auxiliary_value_per_share=auxiliary,terminal_reinvestment_ratio=reinvest,terminal_dividend_capacity_after_reinvestment=terminal_cashflow)

def make_paths():
 d={}
 for name,mod in [
 ('base',{}),
 ('core_low',{'k':.095,'g':.02,'terminal_roic':.18,'terminal_liquid_release_delay':3.0,'terminal_illiquid_release_delay':5.0,'margin':[.310,.312,.315,.317,.317]}),
 ('core_high',{'k':.085,'g':.025,'terminal_roic':.22,'terminal_liquid_release_delay':1.0,'terminal_illiquid_release_delay':3.0,'margin':[.320,.322,.325,.327,.327]}),
 ('cyclical_weak',{'revenue':[5.90,6.0,6.45,7.05,7.50],'margin':[.285,.29,.305,.315,.317],'dnwc':[.35,.25,.10,.12,.15],'capex':[.85,.85,.75,.55,.45],'payout_requested':[.96,.96,1.12,1.20,1.28],'k':.095,'g':.02,'terminal_roic':.18}),
 ('structural_adverse',{'revenue':[5.85,5.65,5.5,5.4,5.30],'margin':[.28,.27,.26,.255,.25],'dnwc':[.35,.30,.10,0,0],'capex':[1.1,1.1,.8,.5,.45],'da':[.34,.38,.42,.43,.43],'payout_requested':[.8,.64,.56,.48,.48],'k':.105,'g':0,'terminal_roic':.12,'yield_aftertax':.015,'terminal_illiquid_recovery':.7,'liquid_loss0':.15}),
 ('optimistic',{'revenue':[6.85,7.35,7.90,8.45,9.0],'margin':[.32,.33,.335,.34,.34],'capex':[.95,.95,.85,.65,.55],'da':[.34,.38,.42,.44,.45],'dnwc':[.22,.24,.25,.25,.25],'payout_requested':[1.2,1.36,1.52,1.68,1.84],'k':.085,'g':.025,'terminal_roic':.22}),
 ('capital_stress',{'capex':[1.3,1.3,1.1,.75,.55],'da':[.34,.39,.44,.47,.50],'margin':[.31,.31,.315,.315,.315],'terminal_roic':.15,'k':.095,'g':.02}),
 ('full_plan_execution',{'capex':[1.4,1.4,1.2,.85,.65],'da':[.34,.40,.46,.50,.54],'margin':[.31,.31,.315,.315,.315],'terminal_roic':.15,'k':.095,'g':.02}),
 ('upstream_delay',{'upstream_receipt_fraction':[0,0,1,1,1],'parent_cash_opening_shift':-.75,'internal_settlement':[.9,.5,.3,.3,.3]}),
 ('immediate_financial_release',{'terminal_liquid_release_delay':0.0,'terminal_illiquid_release_delay':0.0}),
 ('five_year_financial_wait',{'terminal_liquid_release_delay':5.0,'terminal_illiquid_release_delay':5.0}),
 ('margin_minus_2pp',{'margin':[x-.02 for x in BASE['margin']]}),
 ('discount_plus_1pp',{'k':.10}),
 ('no_unverified_fund_call',{'fund_calls':[0,0,0,0,0]}),
 ]:
  p=copy.deepcopy(BASE);p.update(mod);p['name']=name;d[name]=project(p)
 return d

def tests():
 # Known perpetuity: cash earned and received=1 annually, k=10%, zero growth =>10.
 p=copy.deepcopy(BASE)
 p.update(name='hand_perpetuity',revenue=[2]*5,margin=[.5]*5,capex=[0]*5,da=[0]*5,dnwc=[0]*5,shares=1,liquid0=0,illiquid0=0,debt0=0,reserve=0,yield_aftertax=0,debt_cost_aftertax=0,repayment=[0]*5,fund_calls=[0]*5,payout_requested=[1]*5,parent_liquid0=0,parent_retained0=0,sub_retained0=0,parent_share_profit=1,parent_share_da=1,parent_share_capex=1,parent_share_nwc=1,upstream_payout=0,sub_legal_reserve_ratio=0,internal_payable0=0,internal_settlement=[0]*5,parent_floor=0,sub_floor=0,k=.1,g=0,terminal_roic=.2)
 z=project(p);assert abs(z['value_per_share']-10)<1e-10
 # Budget2 cannot manufacture dividends: formal chain caps at1 and value remains10.
 p['payout_requested']=[2]*5;z2=project(p);assert [r['actual_dividend'] for r in z2['years']]==[1]*5;assert abs(z2['value_per_share']-10)<1e-10
 # 0.2 capex with no depreciation leaves .8 cash, terminal requires zero growth no reinvestment.
 p['payout_requested']=[.8]*5;p['capex']=[.2]*5
 z3=project(p);hand=sum(.8/(1.1)**t for t in range(1,6))+10/(1.1)**5
 assert abs(z3['value_per_share']-hand)<1e-10
 # Explicit delayed financial-principal hand case, using the same production chain.
 q=copy.deepcopy(p);q.update(capex=[0]*5,payout_requested=[1]*5,liquid0=1,parent_liquid0=1,terminal_liquid_release_delay=2)
 z4=project(q);hand_delay=10+1/(1.1)**7
 assert abs(z4['value_per_share']-hand_delay)<1e-10
 rejected=[]
 for key,bad in [('shares',0),('k',.0),('g',.11),('terminal_roic',.0),('revenue',[1]*4),('margin',[float('nan')]*5),('capex',[-1]*5),('upstream_receipt_fraction',[2]*5),('repayment',[1]*5),('illiquid0',-1),('terminal_liquid_release_delay',-1),('internal_settlement',[1]*5)]:
  q=copy.deepcopy(p);q[key]=bad
  try:project(q)
  except ValueError:rejected.append(key)
  else:raise AssertionError('domain accepted '+key)
 # Formal counterexample: an overnight full repayment of all entity liquidity without
 # replacement funding may be infeasible and must not retain a dividend schedule.
 q=copy.deepcopy(BASE);q.update(parent_cash_opening_shift=-3.0,upstream_receipt_fraction=[0]*5,internal_settlement=[2.0,0,0,0,0])
 try:project(q)
 except ValueError:rejected.append('infeasible_entity_funding')
 else:raise AssertionError('funding-infeasible path silently accepted')
 return {'status':'PASS','formal_function':'project','perpetuity_actual':z['value_per_share'],'perpetuity_independent_hand':10,'overdistribution_cap_actual':[r['actual_dividend'] for r in z2['years']],'capex_case_actual':z3['value_per_share'],'capex_case_independent_hand':hand,'delayed_principal_actual':z4['value_per_share'],'delayed_principal_independent_hand':hand_delay,'rejected_inputs':rejected}

if __name__=='__main__':
 payload={'model_units':'CNY billion; shares billion','tests':tests(),'paths':make_paths()}
 sys.stdout.write(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))
