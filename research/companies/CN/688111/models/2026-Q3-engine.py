#!/usr/bin/env python3
"""Kingsoft Office 2026-Q3. Standard library only; CNY billion/billion shares.
Run anywhere: python /path/2026-Q3.py [--output /path/output.json].
Economic forecast, not certification of legal distributable profits.
"""
from __future__ import annotations
from pathlib import Path
from copy import deepcopy
import argparse,json,math
ROOT=Path(__file__).resolve().parent
FACTS={
 'cash':.91043553866,'trading_assets':.69392951668,'maturing_deposits':5.78496608276,
 'other_current_assets':5.55443109387,'other_noncurrent_assets':2.791261506,
 'h1_non_deposit_current':.27920214229,'h1_non_deposit_noncurrent':.03947222930,
 'restricted_cash':.00087130,'fund_and_associates':2.73785943971,'deferred_tax':.206167132,
 'issued_shares':.464013435,'treasury_shares':.000486368,
 'parent_h1_retained':.41504754382,'parent_reserve':.23158964650,
 'parent_registered_capital':.464013435,'zhuhai_registered_capital':1.62326,
 'parent_h1_cash_finance':2.80757882719,'parent_dividend_payable_h1':.32959881913,
}
CASH=sum(FACTS[k] for k in ['cash','trading_assets','maturing_deposits','other_current_assets','other_noncurrent_assets'])-FACTS['h1_non_deposit_current']-FACTS['h1_non_deposit_noncurrent']-FACTS['restricted_cash']
BASE={
 'name':'base','segments0':[4.25,1.08,1.70,.15],
 'growths':[[.12,.11,.10,.09,.08,.07,.06,.05,.04,.03],
            [.30,.25,.22,.18,.15,.12,.10,.08,.06,.04],
            [.08,.08,.07,.06,.05,.04,.04,.03,.03,.025],[.03]*10],
 'margins':[.235,.24,.245,.25,.255,.255,.2525,.25,.25,.25],
 'r':.0975,'g':.0225,'cash_yield':.018,'capital_ratio':.22,'net_capex_ratio':.003,
 'cash0':CASH,'fund0':FACTS['fund_and_associates'],'fund_recovery':.85,'fund_recovery_year':3,
 'tax_payment':FACTS['deferred_tax'],'tax_credit_recovery':.19379199609,'shares':.467858371,
 'shares0':.463527067,'vesting_counts':[.0012,.0012,.0007,.0009,.000331304,0.,0.,0.,0.,0.],
 'exercise_proceeds_total':.6134,'treasury0':.000486368,
 'payout':.35,'parent_cash0':2.45,'parent_profit_budget0':.35,
 'parent_reserve':FACTS['parent_reserve'],'parent_capital':FACTS['parent_registered_capital'],
 'parent_own_share':.07,'sub_share':.75,'upstream_rate':.45,'receipt_delay':0,'declaration_delay':0,
 # Unknown historical subsidiary reserves are not invented. This envelope
 # bounds future precautionary appropriations by the actual registered capital.
 'sub_reserve_envelope':FACTS['zhuhai_registered_capital']*.5,
 'parent_min_cash':.25,'borrow_rate':.06,
 'extra_cash_costs':[0.]*10,'parent_extra_losses':[0.]*10,'fund_profit_budget_loss':[0.]*10,
 'horizon':180,'mature_upstream_rate':.95,'mature_payout':1.0,'maturity_year':11,
 'release_years':15,'upstream_cash_friction':0.,
 'parent_fund_fraction':.95226915232/3.46767005925,'opening_sub_cash_access':1.,
 'description':'Personal conversion and PC growth; 365 grows then decelerates; royalties mid-single-digit; AI costs retained.'
}

def simulate(p):
 seg=list(p['segments0']);rev0=sum(seg);needed=rev0*p['capital_ratio'];cash=p['cash0']-needed
 debt=0.;fund=p['fund0'];pcash=p['parent_cash0'];legal=p['parent_profit_budget0'];pres=p['parent_reserve']
 sb=0.;sr=0.;sc=0.;ob=0.;oc=0.;pending={};proposed={};oproposed={};rows=[];shares=p.get('shares0',p['shares'])
 # The residual 18% is an economic forecast pool, NOT an invented legal entity.
 other_share=max(1-p['parent_own_share']-p['sub_share'],0.)
 # Initial subsidiary cash locations are forecast allocations, not certified.
 source_opening=max(cash-pcash,0.)*p.get('opening_sub_cash_access',1.)
 source_den=max(p['sub_share']+other_share,1e-12)
 sc=source_opening*p['sub_share']/source_den;oc=source_opening*other_share/source_den
 horizon=p.get('horizon',180)
 for i in range(horizon):
  t=i+1;growth=[p['growths'][j][i] if i<10 else p['g'] for j in range(4)]
  seg=[v*(1+growth[j]) for j,v in enumerate(seg)];rev=sum(seg)
  margin=p['margins'][i] if i<10 else p['margins'][-1]
  op=rev*margin;need_new=rev*p['capital_ratio'];dneed=need_new-needed
  netcap=rev*p['net_capex_ratio'];extra=p['extra_cash_costs'][i] if i<10 else 0.
  interest=(cash+needed)*p['cash_yield']-debt*p['borrow_rate']
  p_interest=min(max(pcash,0.),max(cash+needed,0.))*p['cash_yield']
  subsidiary_interest=interest-p_interest
  vested=p.get('vesting_counts',[0.]*10)[i] if i<10 else 0.;shares+=vested
  parent_cap_year=p['parent_capital']+max(shares-p.get('shares0',p['shares'])-p.get('treasury0',0.),0.)
  proceeds=p.get('exercise_proceeds_total',0.)*vested/sum(p.get('vesting_counts',[1.])) if vested else 0.
  fcf=op-netcap-dneed-extra
  tax=p['tax_payment'] if t==p['fund_recovery_year'] else 0.
  credit=p.get('tax_credit_recovery',0.) if t==2 else 0.;recovery=0.
  if t==p['fund_recovery_year']: recovery=fund*p['fund_recovery'];fund=0.
  openingcash=cash;openingdebt=debt
  cash+=fcf+interest+recovery-tax+proceeds+credit
  financing=max(-cash,0.);cash+=financing;debt+=financing
  mature=t>=p.get('maturity_year',11)
  ramp=min(max((t-p.get('maturity_year',11)+1)/5,0.),1.)
  upr=p['upstream_rate']+(p.get('mature_upstream_rate',.95)-p['upstream_rate'])*ramp
  den=max(1-p['parent_own_share'],1e-12)
  sp=op*p['sub_share']+subsidiary_interest*p['sub_share']/den-(p['fund_profit_budget_loss'][i] if i<10 else 0.)
  sb_open=sb;sb+=sp
  sub_after_loss_profit=max(sp+min(sb_open,0.),0.)
  appropriation=min(sub_after_loss_profit*.10,max(p['sub_reserve_envelope']-sr,0.),max(sb,0.))
  sb-=appropriation;sr+=appropriation
  sc+=fcf*p['sub_share']+subsidiary_interest*p['sub_share']/den+(recovery-tax+credit)*(1-p.get('parent_fund_fraction',0.))
  proposal=max(sp,0.)*upr+(max(sb,0.)/p.get('release_years',15) if mature else 0.)
  due=t+p.get('declaration_delay',0);proposed[due]=proposed.get(due,0.)+proposal
  declared=min(proposed.pop(t,0.),max(sb,0.),max(sc,0.),max(cash,0.))
  sc-=declared;sb-=declared
  # Other sources retain a current-profit economic buffer, not statutory reserve.
  otherprofit=op*other_share+subsidiary_interest*other_share/den;ob+=otherprofit
  oc+=fcf*other_share+subsidiary_interest*other_share/den
  oproposal=max(otherprofit,0.)*upr+(max(ob,0.)/p.get('release_years',15) if mature else 0.)
  oproposed[due]=oproposed.get(due,0.)+oproposal
  odeclared=min(oproposed.pop(t,0.),max(ob-.10*max(otherprofit,0.),0.),max(oc,0.),max(cash-declared,0.))
  oc-=odeclared;ob-=odeclared
  totaldeclared=declared+odeclared
  friction=totaldeclared*p.get('upstream_cash_friction',0.)
  cash-=friction
  pending[t+p['receipt_delay']]=pending.get(t+p['receipt_delay'],0.)+totaldeclared-friction
  receipt=pending.pop(t,0.)
  own=op*p['parent_own_share']-(p['parent_extra_losses'][i] if i<10 else 0.)
  pprofit=own+p_interest+totaldeclared-friction
  legal_open=legal;legal+=pprofit
  parent_after_loss_profit=max(pprofit+min(legal_open,0.),0.)
  pappro=min(parent_after_loss_profit*.10,max(parent_cap_year*.5-pres,0.),max(legal,0.))
  legal-=pappro;pres+=pappro
  # Cash uses FCF, not NOPAT; capital spending cannot vanish at parent level.
  pcash+=fcf*p['parent_own_share']+p_interest+receipt+(recovery-tax+credit)*p.get('parent_fund_fraction',0.)+proceeds
  if mature:
   payout=p['payout']+(p.get('mature_payout',1.)-p['payout'])*ramp
   requested=max(fcf+interest,0.)*payout+max(cash,0.)/p.get('release_years',15)
  else: requested=max(op+interest,0.)*p['payout']
  div=min(requested,max(legal,0.),max(pcash-p['parent_min_cash'],0.),max(cash,0.))
  if debt>0: div=0.
  pcash-=div;legal-=div;cash-=div
  repayment=min(cash,debt);cash-=repayment;debt-=repayment
  assert abs(cash-openingcash-(fcf+interest+recovery-tax+proceeds+credit+financing-div-repayment-friction))<1e-6
  assert cash>=-1e-8 and div>=0
  assert div<=requested+1e-8 and div<=max(legal+div,0.)+1e-8
  assert pres<=parent_cap_year*.5+1e-8
  rows.append(dict(year=t,segments=seg[:],revenue=rev,nopat=op,required_cash=need_new,
   delta_required_cash=dneed,net_capex=netcap,extra_cash_cost=extra,operating_fcf=fcf,
   financial_income=interest,fund_recovery=recovery,tax_payment=tax,tax_credit_recovery=credit,upstream_friction=friction,dividend=div,requested_dividend=requested,
   shares_outstanding=shares,vesting_count=vested,exercise_proceeds=proceeds,dividend_per_share=div/shares,cash_excess_end=cash,debt_end=debt,fund_end=fund,
   financing=financing,repayment=repayment,parent_own_profit=own,parent_dividend_declared=totaldeclared,zhuhai_declared=declared,other_economic_declared=odeclared,
   parent_dividend_receipt=receipt,parent_profit=pprofit,parent_legal_budget_end=legal,
   parent_cash_end=pcash,parent_profit_budget_open=legal_open,parent_profit_after_loss_absorption=parent_after_loss_profit,parent_statutory_appropriation=pappro,parent_reserve_end=pres,parent_registered_capital=parent_cap_year,
   sub_profit=sp,sub_profit_budget_open=sb_open,sub_profit_after_loss_absorption=sub_after_loss_profit,sub_cash_budget_end=sc,sub_future_profit_budget_end=sb,sub_precautionary_appropriation=appropriation,
   sub_cumulative_precautionary_reserve=sr,other_economic_profit_budget_end=ob,other_economic_cash_budget_end=oc,
   unreceived_declared_dividend=sum(pending.values()),mature_upstream_rate=upr))
  needed=need_new
 r=p['r'];divpv=sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows)
 # No Gordon or free terminal cash release: all payments face the same budgets.
 value=divpv
 terminal5=sum(z['dividend_per_share']/(1+r)**(z['year']-5) for z in rows[5:])
 terminal10=sum(z['dividend']/(1+r)**(z['year']-10) for z in rows[10:])
 latepv=sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows[10:])
 last=rows[-1]
 residual_bound=(last['cash_excess_end']+last['required_cash']+max(last['nopat']+last['financial_income'],0.)*(1+p['g'])/(r-p['g']))/shares/(1+r)**horizon
 end5=rows[4]
 normalized_profit=end5['revenue']*p.get('normalized_profit_margin',p['margins'][4])
 operating_value5=sum((z['operating_fcf']+rows[z['year']-2]['required_cash']*p['cash_yield'])/(1+r)**(z['year']-5) for z in rows[5:])
 derived_multiple=operating_value5/normalized_profit if normalized_profit else None
 extra_assets5=end5['cash_excess_end']+end5['fund_end']*p['fund_recovery']-end5['debt_end']
 actual_equity5=terminal5*shares
 realization_bridge5=operating_value5+extra_assets5-actual_equity5
 first5pv=sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows[:5])
 control_upper=first5pv+(operating_value5+extra_assets5)/shares/(1+r)**5
 earning_bridge=dict(normalized_profit_year5=normalized_profit,derived_capitalization_multiple=derived_multiple,
  operating_value_year5=operating_value5,extra_financial_assets_year5=extra_assets5,
  source_parent_timing_cost_year5=realization_bridge5,realizable_equity_year5=actual_equity5,
  present_holder_value=first5pv+(operating_value5+extra_assets5-realization_bridge5)/shares/(1+r)**5,
  control_asset_upper_value_per_share=control_upper)
 incremental_spend=sum((z['revenue']-rows[0]['revenue'])*.50 for z in rows[1:5])+sum(z['net_capex'] for z in rows[1:5])+rows[4]['required_cash']-rows[0]['required_cash']
 diagnostic=(rows[4]['nopat']-rows[0]['nopat'])/incremental_spend if incremental_spend>0 else None
 return dict(incremental_year1_to5_profit=rows[4]['nopat']-rows[0]['nopat'],incremental_year1_to5_investment_budget=incremental_spend,incremental_budget_return=diagnostic,name=p['name'],inputs=p,rows=rows,value_per_share=value,terminal5_per_share=terminal5,
  terminal10_equity=terminal10,terminal_pv_share=latepv/value if value else 0.,residual_upper_bound_per_share=residual_bound,
  normalized_earning_power_bridge=earning_bridge,control_asset_upper_value_per_share=control_upper,base_distributions=[z['dividend_per_share'] for z in rows[:5]])

def cases():
 d={'base':deepcopy(BASE)}
 low=deepcopy(BASE);low.update(name='core_low',r=.105,g=.02,fund_recovery=.75)
 low['growths']=[[max(-.05,x-.02) for x in z] for z in low['growths']];low['margins']=[x-.01 for x in low['margins']];d['core_low']=low
 high=deepcopy(BASE);high.update(name='core_high',r=.09,g=.025,fund_recovery=.95)
 high['growths']=[[x+.015 for x in z] for z in high['growths']];high['margins']=[x+.01 for x in high['margins']];d['core_high']=high
 weak=deepcopy(BASE);weak.update(name='cyclical_delay',receipt_delay=1,fund_recovery_year=5)
 weak['growths'][0][:3]=[.03,.06,.16];weak['growths'][1][:3]=[.05,.10,.38];weak['growths'][2][:3]=[-.15,0.,.20]
 weak['margins'][:3]=[.19,.21,.235];weak['extra_cash_costs'][:3]=[.30,.10,-.25]
 weak['description']='Years 1-2 procurement and collections delay; partial working-capital recovery in year 3, not full lost sales catch-up; same long-run moat.';d[weak['name']]=weak
 bad=deepcopy(BASE);bad.update(name='structural_ai_substitution',r=.105,g=.01,fund_recovery=.55,capital_ratio=.28,net_capex_ratio=.01,upstream_rate=.25,receipt_delay=0,declaration_delay=2,payout=.25)
 bad.update(vesting_counts=[0.]*10,exercise_proceeds_total=0.,shares=bad['shares0'])
 bad['growths']=[[.03,0.,-.03,-.03,-.02,0.,.01,.01,.01,.01],[.15,.10,.06,.04,.03,.02,.01,.01,.01,.01],[-.10,-.05,0.,0.,0.,.01,.01,.01,.01,.01],[0.]*10]
 bad['margins']=[.13,.10,.08,.08,.09,.10,.10,.10,.10,.10]
 bad['extra_cash_costs']=[.5,.35,.15,0.,0.,0.,0.,0.,0.,0.];bad['parent_extra_losses']=[.25,.15,.10,0.,0.,0.,0.,0.,0.,0.];bad['fund_profit_budget_loss']=[.80,0.,0.,0.,0.,0.,0.,0.,0.,0.]
 bad['description']='From year 1 AI agents erode paid personal conversion, 365 implementation burden increases, authorization shrinks; permanent low margin, parent own losses, fund drawdown and two-year declaration deferral. No automatic base terminal.';d[bad['name']]=bad
 bull=deepcopy(BASE);bull.update(name='paid_ai_success',r=.095,g=.025,fund_recovery=1.0)
 bull['growths']=[[x+.04 for x in z] for z in bull['growths']];bull['margins']=[x+.025 for x in bull['margins']];bull['capital_ratio']=.24;bull['net_capex_ratio']=.005
 bull['description']='Paid conversion, overseas PC and enterprise retention outperform; higher implementation capacity and cash reserve required, not free upside.';d[bull['name']]=bull
 for name,change in [('margin_minus_2ppt',{'margins':[x-.02 for x in BASE['margins']]}),('r_plus_1ppt',{'r':BASE['r']+.01}),('cash_release_30yrs',{'release_years':30}),('permanent_low_upstream',{'mature_upstream_rate':.25,'upstream_rate':.25,'release_years':1000000000}),('never_raise_payout',{'mature_payout':.35,'release_years':1000000000}),('upstream_friction_10pct',{'upstream_cash_friction':.10}),('maturity_delayed_10yrs',{'maturity_year':21}),('numeric_horizon_120',{'horizon':120}),('numeric_horizon_240',{'horizon':240}),('upstream_delay_2yrs',{'declaration_delay':2}),('financial_non_deposit_plus_02bn',{'cash0':BASE['cash0']-.2}),('opening_sub_cash_inaccessible',{'opening_sub_cash_access':0.}),('financial_principal_not_present',{'cash0':sum(BASE['segments0'])*BASE['capital_ratio'],'parent_cash0':.25}),('no_award_vesting',{'vesting_counts':[0.]*10,'exercise_proceeds_total':0.,'shares':BASE['shares0']})]:
  p=deepcopy(BASE);p.update(change,name=name);d[name]=p
 for nm,r,g,adj in [('base_terminal_low',.105,.02,-.01),('base_terminal_high',.09,.025,.01)]:
  p=deepcopy(BASE);p.update(name=nm,r=r,g=g);p['margins'][5:]=[x+adj for x in p['margins'][5:]]
  for a in p['growths']:a[5:]=[x+adj for x in a[5:]]
  d[nm]=p
 for nm,margin in [('normalized_earnings_low',.24),('normalized_earnings_high',.26)]:
  p=deepcopy(BASE);p.update(name=nm,normalized_profit_margin=margin);p['margins'][5:]=[margin]*5
  for a in p['growths']:a[5:]=[.08,.06,.04,.03,.0225]
  p['description']='Aggregate normalized earning-power alternative after year5; 24-26% margin, growth 8/6/4/3/2.25%; SAME realized ordinary-holder source/parent/cash constraints.';d[nm]=p
 return d

def tests():
 p=deepcopy(BASE);p.update(name='hand_constant',segments0=[100.,0,0,0],growths=[[0.]*10 for _ in range(4)],margins=[.1]*10,r=.1,g=0.,cash_yield=0.,capital_ratio=0.,net_capex_ratio=0.,cash0=0.,fund0=0.,tax_payment=0.,tax_credit_recovery=0.,horizon=240,shares=1.,shares0=1.,vesting_counts=[0.]*10,exercise_proceeds_total=0.,payout=1.,parent_cash0=0.,parent_profit_budget0=0.,parent_reserve=0.,parent_capital=0.,parent_own_share=1.,sub_share=0.,sub_reserve_envelope=0.,parent_min_cash=0.)
 z=simulate(p);assert abs(z['value_per_share']-100)<1e-5;assert z['base_distributions']==[10.]*5
 p.update(name='hand_loss',margins=[-.1,.1]+[0.]*8,cash0=100.,parent_cash0=100.,parent_profit_budget0=5.)
 z=simulate(p);assert z['rows'][0]['dividend']==0.;assert z['rows'][0]['parent_legal_budget_end']==-5.;assert abs(z['rows'][1]['dividend']-5.)<1e-9
 # Same production loop, actual NONZERO capital and unfilled reserve threshold.
 reserve_hand_checks={}
 for entity in ['parent','zhuhai']:
  for path,ms,budget_year in [('loss2_then_profit5',[-.002,.005]+[0.]*8,2),('unrecovered_then_partial_current_profit',[-.002,.001,.004]+[0.]*7,3)]:
   h=deepcopy(BASE);h.update(name='hand_reserve_'+entity+'_'+path,segments0=[1.,0.,0.,0.],growths=[[0.]*10 for _ in range(4)],margins=ms,horizon=10,cash_yield=0.,capital_ratio=0.,net_capex_ratio=0.,cash0=5.,fund0=0.,tax_payment=0.,tax_credit_recovery=0.,vesting_counts=[0.]*10,exercise_proceeds_total=0.,payout=0.,maturity_year=999,parent_profit_budget0=0.,parent_min_cash=0.,upstream_rate=0.,mature_upstream_rate=0.,parent_own_share=1. if entity=='parent' else 0.,sub_share=0. if entity=='parent' else 1.,parent_cash0=5. if entity=='parent' else 0.)
   hz=simulate(h);rk='parent_statutory_appropriation' if entity=='parent' else 'sub_precautionary_appropriation';bk='parent_legal_budget_end' if entity=='parent' else 'sub_future_profit_budget_end'
   assert hz['rows'][0][rk]==0. and abs(hz['rows'][0][bk]+.002)<1e-12
   if budget_year==3:assert hz['rows'][1][rk]==0. and abs(hz['rows'][1][bk]+.001)<1e-12
   assert abs(hz['rows'][budget_year-1][rk]-.0003)<1e-12;assert abs(hz['rows'][budget_year-1][bk]-.0027)<1e-12
   reserve_hand_checks[entity+'_'+path]={'appropriation_billion':hz['rows'][budget_year-1][rk],'profit_budget_after_appropriation_billion':hz['rows'][budget_year-1][bk],'nonzero_registered_capital_billion':h['parent_capital'] if entity=='parent' else FACTS['zhuhai_registered_capital']}
 p=deepcopy(BASE);p.update(receipt_delay=1);z=simulate(p)
 assert z['rows'][0]['parent_dividend_receipt']==0;assert abs(z['rows'][1]['parent_dividend_receipt']-z['rows'][0]['parent_dividend_declared'])<1e-12
 return {'production_constant_profit':'constant 10 annual dividend discounted at 10% converges to 100 through actual 240-year production loop; no terminal formula','production_loss_budget':'opening 5 - loss 10 + profit 10 permits only dividend 5 in year2','reserve_after_loss_hand_checks':reserve_hand_checks,'declaration_receipt':'one-year receipt lag does not recognize dividend income twice','status':'passed'}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'2026-Q3-output.json');args=ap.parse_args()
 out={'units':'CNY billion, shares billion; per-share CNY','facts':FACTS,'financial_cash_estimate':CASH,'tests':tests(),'scenarios':{n:simulate(p) for n,p in cases().items()}}
 args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'output':str(args.output),'tests':out['tests'],'summary':{n:{k:v[k] for k in ['value_per_share','terminal5_per_share','base_distributions','terminal_pv_share','control_asset_upper_value_per_share']} for n,v in out['scenarios'].items()}},ensure_ascii=False,indent=2))
