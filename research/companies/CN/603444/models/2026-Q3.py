#!/usr/bin/env python3
"""603444 owner economics, not synthetic subsidiary statutory accounts.
stdlib only; python 2026-Q3.py [output.json]. CNY billion except shares/per-share.
Y1-5: parent actual legal ledger plus explicitly estimated incoming dividend capacity.
Y6+: economic equity cash realization with finite cohort lag, NOT asserted legal dividends.
"""
import copy,json,sys
from pathlib import Path
SHARES=.071756301
INPUTS={'as_of':'2026-10-26T09:00:00+00:00','group_financial_cash':6.20441832789,
 'owner_cash':4.78058529981,'owner_nonoperating_investments':1.51006038566,
 'owner_cash_attribution':'group cash less 40% of publishing-chain cash budget 3.5595825702; not published cash location',
 'investment_attribution':'group 1.65944712895 less fund outside claim .01441652995 less 40% publishing investment budget .33742553335',
 'parent':{'cash':.01946502401,'re':1.23207381943,'statutory_reserve':.0360205505,'registered':.072041101,'paid':.072041101,'debt':0.},
 'old_dividend_receivable':.104787,'initial_revenue':7.1,'tax':.17,
 'parent_own_profit_share':.03,'minority_publishing_stake':.4,'publishing_profit_share':.4,
 'parent_floor':.04,'holding_floor_owner':.018,'owner_floor_weight':.78,
 'debt_rate':.05,'owner_debt_limit':.2,'parent_debt_limit':.1,'idle_cash_yield':.01,
 'actual':{'YTD_revenue':5.49646849226,'Q3_revenue':1.76962619448,'YTD_common_net':1.58500744294,'Q3_common_net':.49347094755,'YTD_group_net':1.88896527756,'YTD_CFO':1.91521148827,'YTD_net_capex':-.04833308598,'shares_issued':72041101,'treasury':284800,'declared_Q3_dividend_ps':6.},
 'identity_boundary':'Only parent has a statutory ledger. Economic portfolio, cash attribution and realization cohorts are not legal entities. Foreign entities never receive Chinese reserve parameters.',
 'realization_boundary':'Tail cash is an equity valuation realization budget, not a forecast of legally declared dividends. Foreign taxation, solvency, procedures and governance are represented by finite delay and cash friction, not invented registered capital. Five-year holder cash remains parent-constrained.'}
BASE={'revenue_components':{'legacy':[2.05,1.91,1.78,1.66,1.55],'domestic_2025':[2.35,1.98,1.70,1.49,1.34],'overseas':[1.65,1.60,1.48,1.40,1.34],'agency_and_new':[.65,.68,.72,1.20,1.77]},'gross':[.935,.933,.93,.925,.92],'selling':[.35,.345,.34,.34,.34],'rd':[.92,.94,.95,1.,1.04],'admin':[.35,.35,.35,.36,.37],'other_cost':.005,'payout':.75,'upstream':.90,'cash_reserve_ratio':.18,'nwc_ratio':.03,'net_capex':.015,'maintenance_capex':.035,'asset_realization':.80,'discount':.10,'tail_growth':.01,'delay_years':0,'extra_wc':0.,'cash_attribution_shift':0.,'realization_lag':3,'realization_friction':.05,'routine_fraction':.90,'routine_friction':.01,'parent_loss':0.,'loss_year':1,'operating_shock_year':0,'operating_shock':0.,'debt_open':0.,'disposal_fee':0.,'tail_cash_injection_year':0,'tail_cash_injection':0.}
def params(**kw):
 p=copy.deepcopy(BASE);p.update(kw);return p

def cn_profit(e,profit):
 """Parent only. Registered threshold, loss first; paid never used as threshold."""
 old=e['re']; eligible=max(0.,profit-max(0.,-old))
 transfer=min(max(0.,.5*e['registered']-e['statutory_reserve']),.1*eligible)
 e['re']+=profit-transfer;e['statutory_reserve']+=transfer
 return transfer

def parent_dividend(e,target,floor):
 d=min(max(0.,target),max(0.,e['re']),max(0.,e['cash']-floor))
 e['cash']-=d;e['re']-=d;return d

def collect_old(e,amount):
 e['cash']+=amount # no profit, no reserve

def dispose(book,gross,fee,external_debt,tax_rate=.25):
 """Used by every investment disposal. Failed settlement retains debt/asset; no zero-and-close."""
 gain=gross-fee-book;tax=max(0.,gain)*tax_rate;available=gross-fee-tax
 if available+1e-12<external_debt or available < -1e-12:
  return {'feasible':False,'cash_to_equity':None,'debt_remaining':external_debt,'book_remaining':book,'fee':fee,'tax':tax,'profit':gain-tax,'capital_basis_return':0.}
 net=available-external_debt
 return {'feasible':True,'cash_to_equity':net,'debt_remaining':0.,'book_remaining':0.,'fee':fee,'tax':tax,'profit':gain-tax,'capital_basis_return':min(book,max(0.,available)),'debt_repayment':external_debt}

def operate(p,y):
 i=min(y,5)-1;factor=(1+p['tail_growth'])**max(0,min(y,10)-5)
 rev=sum(v[i] for v in p['revenue_components'].values())*factor
 rd=p['rd'][i]*factor;admin=p['admin'][i]*factor
 ebit=rev*(p['gross'][i]-p['selling'][i]-p['other_cost'])-rd-admin
 tax=max(0.,ebit)*INPUTS['tax'];net=ebit-tax
 if y==p['operating_shock_year']:net-=p['operating_shock']
 return {'revenue':rev,'rd':rd,'admin':admin,'ebit':ebit,'tax':tax,'group_net':net}

def settle_cohort(gross,friction,available,debt=0.):
 """Valuation realization only; costs cannot be financed by clipping a shortfall."""
 fee=gross*friction
 if available+1e-12<gross+debt or gross<0 or not 0<=friction<=1:
  return {'feasible':False,'realized':None,'cash_used':0.,'fee':fee,'debt_remaining':debt}
 return {'feasible':True,'realized':gross-fee,'cash_used':gross+debt,'fee':fee,'debt_remaining':0.}

def run(p,years=80):
 assert years>=30 and p['realization_lag']>=1
 owner_factor=1-INPUTS['minority_publishing_stake']*INPUTS['publishing_profit_share']
 cash=INPUTS['owner_cash']+p['cash_attribution_shift']; debt=p['debt_open']
 parent=copy.deepcopy(INPUTS['parent']);old=INPUTS['old_dividend_receivable']
 prev=INPUTS['initial_revenue'];inv=INPUTS['owner_nonoperating_investments'];initial_inv=inv
 rows=[];cohorts=[];feasible=True;reasons=[]
 for y in range(1,years+1):
  op=operate(p,y);opening=cash;opening_debt=debt
  fin_income=max(0.,cash)*INPUTS['idle_cash_yield'];interest=debt*INPUTS['debt_rate']
  loss=p['parent_loss'] if y==p['loss_year'] else 0.
  owner_net=op['group_net']*owner_factor-interest+fin_income-loss
  capex=(p['net_capex'] if y<=5 else 0.)*owner_factor
  wc=((op['revenue']-prev)*p['nwc_ratio']+(p['extra_wc'] if y==1 else 0.)-(p['extra_wc'] if y==3 else 0.))*owner_factor
  fcf=owner_net-capex-wc
  cash+=fcf; sale=None;proceeds=0.;sale_profit=0.
  if 6<=y<=10:
   book=initial_inv/5
   sale=dispose(book,book*p['asset_realization'],p['disposal_fee'],0.)
   if not sale['feasible']:feasible=False;reasons.append([y,'investment_disposal_fee_or_creditor_shortfall'])
   else:
    proceeds=sale['cash_to_equity'];sale_profit=sale['profit'];cash+=proceeds;inv-=book
  injection=p['tail_cash_injection'] if y==p['tail_cash_injection_year'] else 0.
  # diagnostic asset conversion is paired with loss of same off-model asset; not operating profit
  cash+=injection
  floor=INPUTS['parent_floor']+INPUTS['holding_floor_owner']+op['revenue']*p['cash_reserve_ratio']*INPUTS['owner_floor_weight']
  borrow=0.;repay=0.;dividend=0.;realized=0.;fee=0.;new_up=0.;collected=0.;transfer=0.;parent_profit=None;cancelled=0.
  if cash<floor:
   borrow=min(floor-cash,max(0.,INPUTS['owner_debt_limit']-debt));cash+=borrow;debt+=borrow
   if cash<floor-1e-10:feasible=False;reasons.append([y,'owner_liquidity_below_required_operations_even_with_zero_payout'])
  # Existing debt paid from available resources before any distribution; does not erase creditor claims.
  repay=min(max(0.,debt-(parent['debt'] if y<=5 else 0.)),max(0.,cash-floor));cash-=repay;debt-=repay
  if y<=5:
   p_own=op['group_net']*INPUTS['parent_own_profit_share']-loss
   p_fcf=p_own-(capex+wc)*INPUTS['parent_own_profit_share']/owner_factor-parent['debt']*INPUTS['debt_rate']
   parent['cash']+=p_fcf
   if y==p['delay_years']+1:
    collected=min(old,max(0.,cash-parent['cash']-(floor-INPUTS['parent_floor'])))
    collect_old(parent,collected);old-=collected
   source_profit=op['group_net']*(owner_factor-INPUTS['parent_own_profit_share'])
   # Explicit net-economic remittance budget; no fictitious foreign legal retained-earnings pool.
   new_up=min(max(0.,source_profit)*p['upstream'],max(0.,cash-parent['cash']-(floor-INPUTS['parent_floor']))) if y>p['delay_years'] else 0.
   parent['cash']+=new_up
   parent_profit=p_own-parent['debt']*INPUTS['debt_rate']+new_up
   transfer=cn_profit(parent,parent_profit) # same-year own loss offsets new dividends before parent payout
   if parent['cash']<INPUTS['parent_floor']:
    b=min(INPUTS['parent_floor']-parent['cash'],max(0.,INPUTS['parent_debt_limit']-parent['debt']),max(0.,INPUTS['owner_debt_limit']-debt))
    parent['cash']+=b;parent['debt']+=b;debt+=b;cash+=b;borrow+=b
    if parent['cash']<INPUTS['parent_floor']-1e-10:feasible=False;reasons.append([y,'parent_cash_shortfall'])
   # parent debt is part of owner debt; repay only from parent cash and owner excess simultaneously
   z=min(parent['debt'],debt,max(0.,parent['cash']-INPUTS['parent_floor']),max(0.,cash-floor))
   parent['debt']-=z;parent['cash']-=z;debt-=z;cash-=z;repay+=z
   target=p['payout']*max(0.,op['group_net']*owner_factor-loss)
   if y==1:target=max(6*SHARES,target)
   dividend=parent_dividend(parent,target,INPUTS['parent_floor']);cash-=dividend
   if y==1 and dividend<6*SHARES-1e-10:feasible=False;reasons.append([y,'declared_6_yuan_not_fundable'])
   if cash<floor-1e-10:feasible=False;reasons.append([y,'holder_payout_breaches_operating_funding'])
  else:
   routine_gross=min(max(0.,cash-floor),p['routine_fraction']*max(0.,min(fcf,owner_net+sale_profit)))
   routine=settle_cohort(routine_gross,p['routine_friction'],cash-floor,debt)
   if not routine['feasible']:
    feasible=False;reasons.append([y,'routine_economic_realization_shortfall'])
   else:
    cash-=routine['cash_used'];realized+=routine['realized'];fee+=routine['fee'];debt=0.
   # These are economic realization rights for TV, never statutory profit or literal parent dividends.
   # If later operations need cash, cancel newest still-pending realizations, preserving operating assets.
   excess=max(0.,cash-floor)
   shortage=max(0.,sum(c['gross'] for c in cohorts)-excess)
   for c in reversed(cohorts):
    cut=min(c['gross'],shortage);c['gross']-=cut;shortage-=cut;cancelled+=cut
   matured=[c for c in cohorts if c['due']<=y];cohorts=[c for c in cohorts if c['due']>y]
   for c in matured:
    s=settle_cohort(c['gross'],p['realization_friction'],cash-floor,debt)
    if not s['feasible']:
     feasible=False;reasons.append([y,'cohort_fee_or_creditor_shortfall']);cohorts.append(c)
    else:cash-=s['cash_used'];realized+=s['realized'];fee+=s['fee'];debt=0.
   unscheduled=max(0.,cash-floor-sum(c['gross'] for c in cohorts))
   if unscheduled>1e-12:cohorts.append({'born':y,'due':y+p['realization_lag'],'gross':unscheduled})
  outflow=dividend+realized
  residual=cash-(opening+fcf+proceeds+injection+borrow-repay-outflow-fee)
  assert abs(residual)<1e-8,(y,residual)
  assert abs(debt-opening_debt-borrow+repay)<1e-8
  rows.append({'year':y,**op,'owner_operating_net':op['group_net']*owner_factor,'owner_total_profit_before_disposals':owner_net,'financial_income':fin_income,'interest':interest,'incremental_capex':capex,'maintenance_capex':p['maintenance_capex']*owner_factor,'equal_depreciation':p['maintenance_capex']*owner_factor,'working_capital_change':wc,'FCFE_before_disposals':fcf,'investment_disposal':sale,'investment_cash':proceeds,'investment_profit':sale_profit,'investment_book_remaining':inv,'opening_cash':opening,'owner_cash':cash,'required_operating_cash':floor,'debt':debt,'new_borrowing':borrow,'repayment':repay,'parent_new_dividend_budget':new_up,'parent_profit_including_current_loss':parent_profit,'old_receivable_collection':collected,'old_receivable_remaining':old,'parent_reserve_transfer':transfer,'parent':copy.deepcopy(parent) if y<=5 else None,'holder_dividend':dividend,'economic_equity_realization_not_dividend':realized,'realization_cost':fee,'valuation_cash':outflow,'pending_cohorts':copy.deepcopy(cohorts),'cancelled_for_operations':cancelled,'asset_conversion_diagnostic':injection,'feasible':feasible,'cash_conservation_residual':residual})
  prev=op['revenue']
 r=p['discount'];last=rows[-1]
 # Fixed operating scale from Y11. Every future surplus cohort still settles after lag years.
 steady_fcf=last['owner_operating_net']
 steady_gross=(steady_fcf+INPUTS['idle_cash_yield']*last['required_operating_cash'])/(1-INPUTS['idle_cash_yield']*p['realization_lag']*(1-p['routine_fraction']))
 steady_realization=steady_gross*(p['routine_fraction']*(1-p['routine_friction'])+(1-p['routine_fraction'])*(1-p['realization_friction']))
 if steady_realization<0:feasible=False;reasons.append([years,'negative_permanent_operations_no_funded_terminal'])
 tail=steady_realization/r
 pv=sum(a['valuation_cash']/(1+r)**a['year'] for a in rows)+tail/(1+r)**years
 tv5=sum(a['valuation_cash']/(1+r)**(a['year']-5) for a in rows[5:])+tail/(1+r)**(years-5)
 # secondary: immediate equity FCFE + current excess liquid capital + discounted investment exit.
 floor0=INPUTS['parent_floor']+INPUTS['holding_floor_owner']+INPUTS['initial_revenue']*p['cash_reserve_ratio']*INPUTS['owner_floor_weight']
 secondary=sum((a['owner_operating_net']-a['incremental_capex']-a['working_capital_change']-(a['required_operating_cash']-(floor0 if a['year']==1 else rows[a['year']-2]['required_operating_cash'])))/(1+r)**a['year'] for a in rows[:10])+rows[10]['owner_operating_net']/r/(1+r)**10
 secondary-=p['parent_loss']/(1+r)**p['loss_year']
 secondary+=INPUTS['owner_cash']+p['cash_attribution_shift']-floor0-p['debt_open']
 secondary+=sum(initial_inv/5*p['asset_realization']/(1+r)**y for y in range(6,11))
 return {'parameters':p,'feasible':feasible,'failure_reasons':reasons,'value_per_share':pv/SHARES if feasible else None,'terminal_y5_per_share':tv5/SHARES if feasible else None,'first5_dividends_ps':[a['holder_dividend']/SHARES for a in rows[:5]],'terminal_share_of_PV':tv5/(1+r)**5/pv if feasible else None,'economic_FCFE_crosscheck_ps':secondary/SHARES if feasible else None,'years':rows,'terminal':{'year':years,'steady_gross_realization':steady_gross,'steady_net_realization':steady_realization,'perpetuity_at_last_year':tail,'last_year_realization':last['economic_equity_realization_not_dividend'],'convergence_error':last['economic_equity_realization_not_dividend']-steady_realization,'unpaid_debt':debt,'unrealized_investments':inv,'definition':'Equity economic realization, not promised statutory parent dividend; includes future cohort lag and friction, excludes any separate perpetual principal addition.'}}

def scenarios():
 sc={'base':params(),'core_low':params(discount=.105,asset_realization=.75,tail_growth=0.),'core_high':params(discount=.095,asset_realization=.85,tail_growth=.02)}
 cyc={k:[v[0]*.85,v[1]*.9,*v[2:]] for k,v in BASE['revenue_components'].items()}
 sc['cyclical']=params(revenue_components=cyc,extra_wc=.25,upstream=.60)
 structural={'legacy':[1.9,1.6,1.35,1.15,1.],'domestic_2025':[1.9,1.4,1.,.7,.5],'overseas':[1.3,1.,.8,.7,.6],'agency_and_new':[.5,.4,.4,.4,.4]}
 sc['structural']=params(revenue_components=structural,gross=[.92]*5,selling=[.38,.37,.35,.33,.32],rd=[.92,.88,.75,.6,.5],admin=[.35,.32,.28,.24,.22],payout=.5,tail_growth=0.,discount=.115,asset_realization=.6,realization_lag=5,realization_friction=.15)
 opt={'legacy':[2.1,2.,1.9,1.8,1.7],'domestic_2025':[2.5,2.3,2.1,2.,1.9],'overseas':[1.9,2.1,2.2,2.3,2.4],'agency_and_new':[.7,.8,1.1,1.8,2.6]}
 sc['optimistic']=params(revenue_components=opt,rd=[.96,1.02,1.12,1.25,1.4],admin=[.36,.38,.4,.42,.45],selling=[.35,.34,.34,.34,.34],tail_growth=.02,discount=.095)
 sc['cash_delay']=params(delay_years=2,extra_wc=.4)
 sc['sales_plus_3pp']=params(selling=[x+.03 for x in BASE['selling']])
 sc['new_projects_zero']=params(revenue_components={**copy.deepcopy(BASE['revenue_components']),'agency_and_new':[.65,.68,.72,.72,.72]},tail_growth=0.)
 sc['lower_cash_attribution']=params(cash_attribution_shift=-.28)
 sc['higher_operating_buffer']=params(cash_reserve_ratio=.23)
 sc['upstream_60pct']=params(upstream=.60)
 sc['slower_realization']=params(realization_lag=5,realization_friction=.15,routine_friction=.03)
 sc['faster_realization']=params(realization_lag=2,realization_friction=.02)
 sc['same_year_parent_loss']=params(parent_loss=1.)
 sc['late_surplus_40']=params(tail_cash_injection_year=40,tail_cash_injection=.5)
 sc['late_surplus_60']=params(tail_cash_injection_year=60,tail_cash_injection=.5)
 sc['tail_loss']=params(operating_shock_year=35,operating_shock=1.5)
 sc['zero_revenue_failure']=params(revenue_components={k:[0]*5 for k in BASE['revenue_components']},rd=[5]*5,admin=[2]*5)
 sc['disposal_fee_failure']=params(disposal_fee=1.)
 return sc

def tests():
 e={'cash':100.,'re':0.,'statutory_reserve':5.,'registered':20.,'paid':10.}
 assert cn_profit(e,10.)==1. and e['re']==9.
 e.update(re=-20.,statutory_reserve=2.);assert cn_profit(e,30.)==1. and e['re']==9.
 e.update(re=0.,statutory_reserve=10.);assert cn_profit(e,10.)==0.
 e['registered']=40.;assert cn_profit(e,10.)==1.
 before=e['re'];collect_old(e,5.);assert e['re']==before
 e.update(re=5.,cash=3.);assert parent_dividend(e,20.,2.)==1.
 e.update(re=2.,statutory_reserve=20.,registered=40.);cn_profit(e,-4.);assert parent_dividend(e,20.,0.)==0.
 s=dispose(10.,10.,1.,2.);assert s['feasible'] and s['cash_to_equity']==7. and s['profit']==-1. and s['capital_basis_return']==9.
 assert not dispose(10.,1.,2.,0.)['feasible']
 q=dispose(10.,3.,1.,5.);assert not q['feasible'] and q['debt_remaining']==5. and q['book_remaining']==10.
 q=settle_cohort(10.,.1,8.,1.);assert not q['feasible'] and q['debt_remaining']==1.
 q=settle_cohort(10.,.1,10.);assert q['feasible'] and q['realized']==9. and q['cash_used']==10.
 return {'registered_not_paid':True,'loss_before_reserve':True,'capped_reserve_and_registered_change':True,'old_receivable_no_new_profit':True,'same_year_loss_caps_dividend':True,'capital_basis_vs_gain':True,'disposal_cost_shortfall_fails':True,'creditor_claim_retained_on_failure':True,'cohort_cost_shortfall_fails':True}

def main():
 out={'inputs':INPUTS,'tests':tests(),'method':'Parent-constrained five-year distributions plus economic equity realization tail; no synthetic legal subsidiary pools','scenarios':{k:run(v) for k,v in scenarios().items()}}
 for k,v in out['scenarios'].items():
  if v['feasible']:
   assert abs(v['terminal']['convergence_error'])<1e-7,(k,v['terminal'])
   assert abs(v['terminal']['unpaid_debt'])<1e-9
 assert not out['scenarios']['zero_revenue_failure']['feasible']
 assert not out['scenarios']['disposal_fee_failure']['feasible']
 assert not out['scenarios']['cash_delay']['feasible']
 assert out['scenarios']['base']['years'][4]==out['scenarios']['core_low']['years'][4]==out['scenarios']['core_high']['years'][4]
 out['core_range_rounded']=[round(out['scenarios'][k]['value_per_share']) for k in ['core_low','core_high']]
 out['same_base_Y5_terminal_range']=[out['scenarios'][k]['terminal_y5_per_share'] for k in ['core_low','core_high']]
 path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('2026-Q3-output.json')
 path.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'),sort_keys=True)+'\n')
 print(json.dumps({k:{a:v[a] for a in ['feasible','value_per_share','terminal_y5_per_share','first5_dividends_ps']} for k,v in out['scenarios'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
