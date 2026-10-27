#!/usr/bin/env python3
"""Independent 40-digit Decimal forward budget; never imports production functions."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json
getcontext().prec=40
R=Path(__file__).resolve().parent
x=json.loads((R/'2026-Q3-output.json').read_text(),parse_float=D)
def d(a):return a if isinstance(a,D) else D(str(a))
def pos(a):return max(a,D(0))
def recalc(case):
 p=case['inputs'];v=list(map(d,p['segments0']));n=sum(v)*p['capital_ratio'];c=p['cash0']-n;pc=p['parent_cash0'];pb=p['parent_profit_budget0'];pr=p['parent_reserve'];sb=sr=sc=ob=oc=D(0);shares=p['shares0'];pay=[];subs={};others={};receipts={};other=1-p['parent_own_share']-p['sub_share'];den=1-p['parent_own_share'];maxdiff=D(0)
 initial=pos(c-pc)*p['opening_sub_cash_access'];sc=initial*p['sub_share']/(p['sub_share']+other);oc=initial*other/(p['sub_share']+other)
 for t in range(1,p['horizon']+1):
  i=t-1;v=[a*(1+(d(p['growths'][j][i]) if t<=10 else p['g'])) for j,a in enumerate(v)];rev=sum(v);profit=rev*(p['margins'][i] if t<=10 else p['margins'][-1]);newn=rev*p['capital_ratio'];f=profit-rev*p['net_capex_ratio']-(newn-n)-(d(p['extra_cash_costs'][i]) if t<=10 else 0)
  interest=(c+n)*p['cash_yield'];pi=min(pos(pc),pos(c+n))*p['cash_yield'];si=interest-pi
  vest=d(p['vesting_counts'][i]) if t<=10 else D(0);shares+=vest
  subcash=p['exercise_proceeds_total']*vest/sum(map(d,p['vesting_counts'])) if vest else D(0)
  fund=p['fund0']*p['fund_recovery'] if t==p['fund_recovery_year'] else D(0)
  tax=p['tax_payment'] if t==p['fund_recovery_year'] else D(0);credit=p['tax_credit_recovery'] if t==2 else D(0)
  c+=f+interest+fund-tax+credit+subcash
  assert c>=0
  ramp=min(pos(D(t-p['maturity_year']+1)/5),D(1));up=p['upstream_rate']+(p['mature_upstream_rate']-p['upstream_rate'])*ramp;mature=t>=p['maturity_year']
  sp=profit*p['sub_share']+si*p['sub_share']/den-(d(p['fund_profit_budget_loss'][i]) if t<=10 else 0);opening_sb=sb;sb+=sp
  a=min(pos(sp+min(opening_sb,D(0)))/10,pos(p['sub_reserve_envelope']-sr),pos(sb));sr+=a;sb-=a
  sc+=f*p['sub_share']+si*p['sub_share']/den+(fund-tax+credit)*(1-p['parent_fund_fraction'])
  due=t+p['declaration_delay'];subs[due]=subs.get(due,D(0))+pos(sp)*up+(pos(sb)/p['release_years'] if mature else 0)
  sd=min(subs.pop(t,D(0)),pos(sb),pos(sc),pos(c));sb-=sd;sc-=sd
  op=profit*other+si*other/den;ob+=op;oc+=f*other+si*other/den
  others[due]=others.get(due,D(0))+pos(op)*up+(pos(ob)/p['release_years'] if mature else 0)
  od=min(others.pop(t,D(0)),pos(ob-pos(op)/10),pos(oc),pos(c-sd));ob-=od;oc-=od
  declaration=sd+od;friction=declaration*p['upstream_cash_friction'];c-=friction
  rt=t+p['receipt_delay'];receipts[rt]=receipts.get(rt,D(0))+declaration-friction;receipt=receipts.pop(t,D(0))
  own=profit*p['parent_own_share']-(d(p['parent_extra_losses'][i]) if t<=10 else 0);pp=own+pi+declaration-friction;opening_pb=pb;pb+=pp
  capital=p['parent_capital']+pos(shares-p['shares0']-p['treasury0']);reserve=min(pos(pp+min(opening_pb,D(0)))/10,pos(capital/2-pr),pos(pb));pr+=reserve;pb-=reserve
  pc+=f*p['parent_own_share']+pi+receipt+(fund-tax+credit)*p['parent_fund_fraction']+subcash
  demand=pos(f+interest)*(p['payout']+(p['mature_payout']-p['payout'])*ramp)+pos(c)/p['release_years'] if mature else pos(profit+interest)*p['payout']
  dividend=min(demand,pos(pb),pos(pc-p['parent_min_cash']),pos(c));pb-=dividend;pc-=dividend;c-=dividend;n=newn
  z=case['rows'][i]
  for a,k in [(c,'cash_excess_end'),(pb,'parent_legal_budget_end'),(pc,'parent_cash_end'),(sb,'sub_future_profit_budget_end'),(dividend,'dividend')]:maxdiff=max(maxdiff,abs(a-z[k]));assert abs(a-z[k])<D('1e-7'),(t,k,a,z[k])
  pay.append(dividend/shares)
 value=sum(a/(1+p['r'])**(i+1) for i,a in enumerate(pay));terminal5=sum(a/(1+p['r'])**(i-4) for i,a in enumerate(pay) if i>=5)
 assert abs(value-case['value_per_share'])<D('1e-9');assert abs(terminal5-case['terminal5_per_share'])<D('1e-8')
 return {'value_per_share':str(value),'terminal5_per_share':str(terminal5),'max_annual_state_difference_billion':str(maxdiff)}
res={k:recalc(x['scenarios'][k]) for k in ['base','core_low','core_high','r_plus_1ppt','permanent_low_upstream','normalized_earnings_low','normalized_earnings_high','structural_ai_substitution']}
res['discount_rate_plus_1ppt_impact']=str(D(res['r_plus_1ppt']['value_per_share'])-D(res['base']['value_per_share']))
res['permanent_low_upstream_impact']=str(D(res['permanent_low_upstream']['value_per_share'])-D(res['base']['value_per_share']))
for name,s in x['scenarios'].items():
 r=s['inputs']['r'];a=sum(z['dividend_per_share']/(1+r)**z['year'] for z in s['rows'][:5])+s['terminal5_per_share']/(1+r)**5;assert abs(a-s['value_per_share'])<D('1e-8'),name
assert D('20498260404.29')-D('5351255882.39')==D('15147004521.90')
assert D('5079649806.85')-D('3313262599.20')==D('1766387207.65')
assert D('2637040592.19')-D('2517594330.93')==D('119446261.26')
assert D('1109703395.98')-D('642693273.51')==D('467010122.47')
for name in ['normalized_earnings_low','normalized_earnings_high']:
 s=x['scenarios'][name];p=s['inputs'];e=s['rows'][4]['revenue']*p['normalized_profit_margin'];opv=D(0)
 for z in s['rows'][5:]:
  annual=z['operating_fcf']+s['rows'][z['year']-2]['required_cash']*p['cash_yield'];opv+=annual/(1+p['r'])**(z['year']-5)
 assert abs(opv/e-s['normalized_earning_power_bridge']['derived_capitalization_multiple'])<D('1e-10')
 res[name]['derived_earning_multiple']=str(opv/e)
res['source_reconciliations']='Assets-liabilities=common equity; 9M-H1=Q3 revenue/profit/CFO: passed'
res['holder_bridge']='All scenarios: years1-5 distributions plus discounted remaining distributions equals present value'
res['numeric_convergence_180_to240']=str(x['scenarios']['numeric_horizon_240']['value_per_share']-x['scenarios']['base']['value_per_share'])
res['status']='passed'
(R/'independent-check-output.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False,indent=2))
