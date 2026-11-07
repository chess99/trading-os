#!/usr/bin/env python3
"""Kelun Q3 2026: CNY million, shareholder-before-personal-tax; stdlib only.
Run anywhere: python 2026-Q3.py > output.json. No reads, dates, or network.
All forward inputs are research budgets, NOT issuer guidance. Historical facts embedded.
"""
import json, math, copy
FACTS={'revenue_9m':13112.749782,'np_parent_9m':1467.027147,'core_np_9m':1061.166108,'cfo_9m':2736.559367,'cash_capex_9m':940.764767,'cash_q3':7031.707616,'liquid_investments_q3':3977.200767,'minority_financing_9m':2370.748466,'shares_m':1590.781208,'dividend_paid_oct21':200.394332208,'B_H1_cash_financial':4783.102,'B_H1_accum_loss':-4317.046,'B_H1_sales':657.041,'B_H1_rd':768.434,'B_H1_selling':390.598,'B_H1_settlement':702.72132578,'B_H1_tax_refund':140.052,'parent_H1_cash_financial':2209.764136,'parent_H1_retained':8676.325758,'parent_H1_cost_dividends':391.270561,'B_direct_shares':124547255,'B_post_placement_shares':239023969,'B_RSU':435064,'chuan_ownership':.7212,'C_H1_parent_retained':2387.12850378,'C_H1_parent_reserve':417.53123015,'C_H1_registered_capital':2232.293}
BASE={'k':.105,'mature_growth':.02,'incremental_return':.12,'mature_profit_factor':1.,'B_sales_factor':1.,'royalty_rate':.08,'overseas_factor':1.,'delay':0,'B_interest':.015,'S_ownership':.8861,'B_ownership':.5644*233185969/239459033,'B_cash':6800.,'parent_cash':2000.,'B_loss':-4617.046,'extra_parent_working':0.,'refinance_rate':.03,'debt_paydown':.10,'reserve_buffer_B':1500.,'remit_factor':1.,'upstream_delay':1,'rd_factor':1.,'exit_B_year':20,'extra_capex':0.,'S_capital_release_year':0,'S_capital_release_cost':0.,'S_retained':0.,'S_reserve':0.,'S_reserve_cap':500.,'S_loss_fraction':.10,'S_loss_retained':-500.,'dividend_target':[.55,.60,.66,.73,.80]}
# Starting cash by legal cluster: total equals Q3 cash+trading assets less already paid Oct21 dividend.
# Allocations are estimates because Q3 omits parent/sub balance sheets; sensitivity tests move cash,
# never manufacture cash. B has 3.5bn earmarked pool conservatively spent only on R&D/capex first.

def initial(p):
 total=FACTS['cash_q3']+FACTS['liquid_investments_q3']-FACTS['dividend_paid_oct21']
 # Total financing/leases 4459.377281: short 2071.233 + due 1157.828 + short bonds budget703.139 + leases527.177.
 state={'P':{'cash':p['parent_cash'],'restricted':12.,'debt':2250.,'retained':8475.931426,'reserve':1745.011993,'reserve_cap':795.390604,'book':18123.004823-200.394332208},
 'S':{'cash':total-p['B_cash']-p['parent_cash']-1200.,'restricted':20.,'debt':1128.023281,'retained':p['S_retained'],'reserve':p['S_reserve'],'reserve_cap':p['S_reserve_cap'],'book':10000.},
 'C':{'cash':1200.,'restricted':82.556288,'debt':1000.,'retained':2387.12850378,'reserve':417.53123015,'reserve_cap':2232.293*.5,'book':8344.75428268},
 'B':{'cash':p['B_cash'],'restricted':3500.,'debt':81.354,'retained':p['B_loss'],'reserve':0.,'reserve_cap':119.7295165,'book':5336.851+2370.748466-300.}}

 # S is an explicitly conservative two-bucket proxy, not an asserted legal consolidation.
 # Unknown loss pockets cannot consume profitable affiliates' legal retained earnings.
 f=p['S_loss_fraction']; state['SL']=copy.deepcopy(state['S'])
 for key in ['cash','restricted','debt','book','reserve','reserve_cap']:
  state['SL'][key]*=f; state['S'][key]*=1-f
 state['SL']['retained']=p['S_loss_retained'];state['S']['retained']*=1-f
 return state

def step(s, x):
 """Production cash/legal distribution chain. Interest, debt, reserve, cash conservation."""
 s=copy.deepcopy(s); old=copy.deepcopy(s)
 interest=s['debt']*x.get('interest_rate',.03)
 fin_income=s['cash']*x.get('cash_yield',.015)
 taxable=x['ebit']-interest+fin_income
 # Model taxes are current cash; loss relief deliberately not assumed; foreign WHT a minimum,
 # credit recognized against domestic tax, not 10%+25% stacked on same royalty.
 tax=max(max(taxable,0)*x.get('tax_rate',.25),x.get('foreign_wht',0))
 np=taxable-tax
 # A remittance is recognized in P profits when declared; actual cash one year later.
 np+=x.get('declared_in',0)
 prior_retained=s['retained']; s['retained']+=np
 appropr=min(max(s['retained'],0)*.10,max(s['reserve_cap']-s['reserve'],0)) if prior_retained<0 else min(max(np,0)*.10,max(s['reserve_cap']-s['reserve'],0))
 s['retained']-=appropr; s['reserve']+=appropr
 repayment=min(s['debt'],x.get('repayment',0)); s['debt']-=repayment
 fcfe=np-x.get('declared_in',0)+x['da']-x['capex']-x['dnwc']-repayment
 s['cash']+=fcfe+x.get('cash_in',0)
 s['restricted']=max(0,s['restricted']-max(x.get('restricted_use',0),0))
 # Reduce dividend, not borrow to maintain a proposed payout. Model reports shortfalls.
 available=max(0,s['cash']-max(s['restricted'],x['floor']))
 dividend=min(max(0,s['retained']),available,max(0,x['target']))
 s['cash']-=dividend;s['retained']-=dividend;s['book']+=np-dividend
 assert abs(s['cash']-(old['cash']+fcfe+x.get('cash_in',0)-dividend))<1e-7
 assert dividend<=max(0,old['retained']+np-appropr)+1e-7
 assert s['cash']>=-1e-7,('insolvent',x,s)
 return s,{'np':np,'tax':tax,'foreign_wht':x.get('foreign_wht',0),'interest':interest,'financial_income':fin_income,'da':x['da'],'capex':x['capex'],'dnwc':x['dnwc'],'debt_repaid':repayment,'fcfe':fcfe,'dividend_declared':dividend,'dividend_target':x['target'],'shortfall':max(0,x['target']-dividend),'reserve_transfer':appropr,'cash':s['cash'],'restricted':s['restricted'],'retained':s['retained'],'debt':s['debt'],'book':s['book'],'ebit':x['ebit']}

def b_budget(t,p):
 sales=p.get('drug_sales_curve',[1800,2300,2900,3450,4000,4400,4800,5200,5500,5800])
 d=sales[min(t,10)-1]*p['B_sales_factor']
 if t>10:d*=.90**(t-10)
 u=max(0,t-p['delay'])
 components=p.get('overseas_components',{'endometrial':[0,350,550,700,800,850,900,950,1000,1000],'breast':[0,0,200,400,650,900,1100,1200,1300,1500],'lung':[0,0,150,500,950,1250,1500,1750,1900,2000]})
 overseas=[sum(v[i] for v in components.values()) for i in range(10)] # USD million, conditional approvals
 foreign=overseas[min(u,10)-1] if u else 0
 if u>10:foreign*=.88**(u-10)
 if t>17:foreign=0. # no post-rights residual in base, despite patent later-of clause
 royalty=foreign*6.8*p['royalty_rate']*p['overseas_factor']
 # contract research receipts reimbursing work; no large upfront/milestone assumed recurring.
 services=250. if t<=5 else 150. if t<=10 else 0.
 service_cost=services*.85
 rd=(1600*1.04**(min(t,6)-1) if t<=10 else 1946.644644*.87**(t-10))*p['rd_factor']
 selling=max(550.,d*.30) if t<=10 else d*.30
 admin=180. if t<=10 else 180*.90**(t-10)
 da=100. if t<=10 else 100*.9**(t-10)
 capex=da+(100. if t<=5 else 50. if t<=10 else 0.)+p['extra_capex']
 ebit=d*.84+royalty+services-service_cost-selling-rd-admin-da
 return {'overseas_components_USDm':{key:((v[min(u,10)-1] if u else 0)*(.88**max(0,u-10)) if t<=17 else 0)*p['overseas_factor'] for key,v in components.items()},'drug_sales':d,'overseas_net_sales_USDm':foreign*p['overseas_factor'],'royalty':royalty,'research_services':services,'rd':rd,'selling':selling,'admin':admin,'da':da,'capex':capex,'ebit':ebit}

def run(p, horizon=30):
 requested_horizon=horizon
 horizon=max(horizon+p['upstream_delay']+10,p['exit_B_year']+p['upstream_delay']+10,p['S_capital_release_year']+p['upstream_delay']+10)
 s=initial(p);opening=copy.deepcopy(s); shares=FACTS['shares_m']; weights={'S':p['S_ownership'],'SL':p['S_ownership'],'C':.7212,'B':p['B_ownership']}; pending=0.;due={};rows=[];last_drug=1500*p['B_sales_factor']; last_nwc=last_drug*.22
 # All financial forecasts use year 1=next 12 months, years 2...; no past Oct21 dividend in holder flows.
 for t in range(1,horizon+1):
  pending=due.get(t,0.);rr={'year':t,'entities':{}}; declared=0.; minority=0.; disposal_cost=0.
  for key in ['S','SL','C','B']:
   if key=='B' and t>p['exit_B_year']:
    rr['entities'][key]={'dividend_declared':0.,'np':0.,'cash':0.,'book':0.,'debt':0.,'closed':True};continue
   if key=='B':
    b=b_budget(t,p); nwc=b['drug_sales']*.22;dnwc=nwc-last_nwc;last_nwc=nwc
    x=dict(ebit=b['ebit'],da=b['da'],capex=b['capex'],dnwc=dnwc,foreign_wht=b['royalty']*.10,tax_rate=.25,floor=p['reserve_buffer_B'],target=1e9,repayment=81.354/5 if t<=5 else 0,restricted_use=b['rd']+b['capex'],interest_rate=p['refinance_rate'],cash_yield=p['B_interest'])
   else:
    g=p['mature_growth'] if t<=10 else p['mature_growth']*(20-t)/10 if t<=20 else 0.
    mult=math.prod(1+(p['mature_growth'] if i<=10 else p['mature_growth']*(20-i)/10 if i<=20 else 0.) for i in range(2,t+1))
    # normalized EBIT includes all platform R&D/selling and excludes financial/associate returns
    sf=(1-p['S_loss_fraction']) if key=='S' else p['S_loss_fraction'] if key=='SL' else 1.
    ebit=(1250 if key in ('S','SL') else 750)*mult*p['mature_profit_factor']*sf
    da=(650 if key in ('S','SL') else 400)*mult*sf
    growth_cap=max(0,ebit*.75*g/p['incremental_return'])
    x=dict(ebit=ebit,da=da,capex=da+growth_cap*.6+p['extra_capex'],dnwc=growth_cap*.4,tax_rate=.25,floor=500*sf if key in ('S','SL') else 450,target=1e9,repayment=opening[key]['debt']*p['debt_paydown'] if t<=5 else 0,restricted_use=da,interest_rate=p['refinance_rate'])
   x['year']=t; x['entity']=key
   before_step=copy.deepcopy(s[key])
   s[key],r=step(s[key],x)
   if key in ('S','SL') and t==p['S_capital_release_year']:
    # Conditional approved capital reduction. Budget tax basis covers returned principal;
    # not ordinary dividend income or automatic right to move cash between companies.
    gross_capital=max(0,s[key]['cash']-x['floor'])
    transaction_cost=gross_capital*p['S_capital_release_cost']
    if transaction_cost:
     x['ebit']-=transaction_cost
     s[key],r=step(before_step,x)
    capital_return=max(0,s[key]['cash']-x['floor'])
    r['capital_release_gross']=gross_capital;r['capital_release_cost']=transaction_cost
    s[key]['cash']-=capital_return;s[key]['book']-=capital_return
    r['capital_return']=capital_return;r['dividend_declared']+=capital_return
    r['cash']=s[key]['cash'];r['book']=s[key]['book']
    disposal_cost+=gross_capital*weights[key]*p['remit_factor']
   if key=='B':r.update(b)
   if key=='B' and t==p['exit_B_year']:
    # Budget orderly business disposal/runoff: collect remaining working capital, 150m plant net
    # disposal, pay 300m employee/regulatory/lease exit. Capital return is conditional corporate action.
    capital_return=max(0,s[key]['cash']+last_nwc+150-300-s[key]['debt'])
    r['capital_return']=capital_return;r['exit_nwc_recovery']=last_nwc;r['exit_fixed_net']=150;r['exit_cost']=300
    r['dividend_declared']+=capital_return;s[key]['cash']=0.;s[key]['debt']=0.;s[key]['book']=0.
    # closing gain/loss for clean surplus RI, not falsely labelled distributable earnings
    r['np']+=capital_return-r['book'];r['book']=0.
    disposal_cost+=3500. # 3342.575m direct parent carrying cost + estimated indirect ownership cost
    r['cash']=0.;r['debt']=0.
   rr['entities'][key]=r
   declared+=r['dividend_declared']*weights[key]*p['remit_factor']
   minority+=r['dividend_declared']*(1-weights[key])
  # remit_factor<1 means smaller economic ownership? No: unpaid upstream dividends remain receivable;
  # one-year timing applies in all scenarios; temporary restriction handled separate delay below.
  mult=math.prod(1+(p['mature_growth'] if i<=10 else p['mature_growth']*(20-i)/10 if i<=20 else 0.) for i in range(2,t+1))
  g=p['mature_growth'] if t<=10 else max(0,p['mature_growth']*(20-t)/10)
  pebit=500*mult*p['mature_profit_factor'] # H1 P pretax ex dividends ~256m supports ~500m annual operating EBIT
  pg=pebit*.75*g/p['incremental_return']
  # 180m annual associate economic income; 120m realized dividends until year5 then180; difference retained in investment value.
  assoc_income=180*mult;assoc_cash=(120 if t<=5 else 180)*mult
  if t==6:assoc_cash+=sum(z['associate_income']-z['associate_cash'] for z in rows)
  parent_declared=declared+assoc_income-disposal_cost
  parent_cash=pending+assoc_cash
  target=shares*p['dividend_target'][t-1] if t<=5 else 1e9
  x=dict(ebit=pebit,da=250*mult,capex=250*mult+pg*.6+p['extra_capex'],dnwc=pg*.4+(p['extra_parent_working'] if t==1 else 0),tax_rate=.25,floor=600,target=target,repayment=opening['P']['debt']*p['debt_paydown'] if t<=5 else 0,restricted_use=250,interest_rate=p['refinance_rate'],declared_in=parent_declared,cash_in=parent_cash)
  s['P'],r=step(s['P'],x);rr['entities']['P']=r
  rr.update(upstream_declared=declared,upstream_received=pending,associate_income=assoc_income,associate_cash=assoc_cash,minority_distributions=minority,holder_distribution=r['dividend_declared'],holder_per_share=r['dividend_declared']/shares)
  due[t+p['upstream_delay']]=declared;rows.append(rr)
 # All actual future due payments, including delayed capital returns, are processed in the
 # extension above. No already-received pending amount is added to value. Capitalize only
 # verified constant actual holder payments after every entity has reached legal steady state.
 future_due={str(t):v for t,v in due.items() if t>horizon}
 steady_up=rows[-1]['upstream_declared']
 assert len(future_due)==p['upstream_delay']
 assert all(abs(v-steady_up)<1e-7 for v in future_due.values()),('unsettled terminal receivable',future_due)
 schedule_audit={'declared_total':sum(z['upstream_declared'] for z in rows),'received_total':sum(z['upstream_received'] for z in rows),'future_due_total':sum(future_due.values())}
 assert abs(schedule_audit['declared_total']-schedule_audit['received_total']-schedule_audit['future_due_total'])<1e-6
 for row in rows:
  prior=row['year']-p['upstream_delay']
  expected=rows[prior-1]['upstream_declared'] if prior>0 else 0.
  assert abs(expected-row['upstream_received'])<1e-7
 annual=rows[-1]['holder_distribution']
 audit={}
 for key,floor in [('P',600.),('S',500*(1-p['S_loss_fraction'])),('SL',500*p['S_loss_fraction']),('C',450.)]:
  r=rows[-1]['entities'][key]
  # Verify each legal-source proxy's distribution capacity; disclose rather than silently
  # distribute cash trapped by the assumed retained balance. No automatic capital reduction.
  assert s[key]['cash']>=floor-1e-7
  for past in rows[-3:]: assert abs(past['entities'][key]['cash']-s[key]['cash'])<1e-7,('nonstationary cash',key)
  # Constant surplus is unavailable as ordinary dividends under the assumed RE balance;
  # this is not evidence of permanent legal prohibition on an approved capital reduction.
  assert s[key]['cash']<=floor+1e-7 or abs(s[key]['retained'])<1e-7,('unpaid legally available surplus',key)
  assert s[key]['reserve']>=s[key]['reserve_cap']-1e-7,('terminal unfinished reserve',key,s[key])
  assert s[key]['retained']>=-1e-7,('terminal accumulated loss',key,s[key])
  for past in rows[-3:]:
   assert abs(past['entities'][key]['dividend_declared']-r['dividend_declared'])<1e-7,('nonstationary payout',key)
  audit[key]={'cash':s[key]['cash'],'legally_locked_surplus':max(0,s[key]['cash']-floor),'floor':floor,'retained_after_distribution':s[key]['retained'],'reserve':s[key]['reserve'],'reserve_cap':s[key]['reserve_cap'],'next_year_legal_capacity':s[key]['retained']+r['np'],'steady_distribution':r['dividend_declared'],'capacity_margin':s[key]['retained']+r['np']-r['dividend_declared']}
  assert audit[key]['capacity_margin']>=-1e-7
 assert all(abs(z['holder_distribution']-annual)<1e-7 for z in rows[-3:])
 assert abs(sum(z['associate_income']-z['associate_cash'] for z in rows))<1e-7
 terminal=annual/p['k']
 pv_flows=sum(z['holder_distribution']/(1+p['k'])**z['year'] for z in rows)
 pv_terminal=terminal/(1+p['k'])**horizon
 value=pv_flows+pv_terminal
 # Auxiliary clean-surplus residual-income valuation on P legal equity. Equity includes subsidiary
 # book stakes, so no separate sub NAV/cash is appended; terminal deducts book capital before capitalizing.
 book0=opening['P']['book'];prev=book0;ri=0.
 for z in rows:
  e=z['entities']['P'];ri+=(e['np']-p['k']*prev)/(1+p['k'])**z['year'];prev=e['book']
 ri_value=book0+ri+(terminal-prev)/(1+p['k'])**horizon
 assert abs(ri_value-value)<1e-6
 assert all(z['entities']['P']['cash']>=600-1e-7 for z in rows)
 future5=(sum(z['holder_distribution']/(1+p['k'])**(z['year']-5) for z in rows if z['year']>5)+terminal/(1+p['k'])**(horizon-5))/shares
 return {'parameters':p,'opening':opening,'annual':rows,'current_value_m':value,'current_value_per_share':value/shares,'residual_income_identity_m':ri_value,'requested_horizon':requested_horizon,'actual_explicit_horizon':horizon,'upstream_schedule_audit':schedule_audit,'future_due_queue':future_due,'terminal_legal_capacity_audit':audit,'terminal_at_actual_horizon_m':terminal,'terminal_present_value_share':pv_terminal/value,'year5_value_per_share':future5,'year5_distributions':[z['holder_per_share'] for z in rows[:5]],'minimum_entity_cash':min(z['entities'][e]['cash'] for z in rows for e in z['entities']),'legal_B_first_dividend_year':next((z['year'] for z in rows if z['entities']['B']['dividend_declared']>0),None),'all_shortfalls_first5':{e:[z['entities'][e].get('shortfall',0) for z in rows[:5]] for e in ['P']}}

def calc(**kw):
 p=copy.deepcopy(BASE);p.update(kw);return run(p)

def hand_tests():
 # literal expected values derived independently: 100cash+80 EBIT-20tax+10DA-15capex-5WC-20debt-30div=100.
 s={'cash':100.,'restricted':0.,'debt':20.,'retained':50.,'reserve':0.,'reserve_cap':0.,'book':200.}
 x={'ebit':80.,'da':10.,'capex':15.,'dnwc':5.,'tax_rate':.25,'floor':0.,'target':30.,'repayment':20.,'interest_rate':0.,'cash_yield':0.}
 a,r=step(s,x)
 assert a['cash']==100. and a['retained']==80. and a['debt']==0. and r['np']==60. and a['book']==230.
 # Loss barrier: -100 retained +60 earnings still negative, dividend zero though cash available.
 s['retained']=-100.;a,r=step(s,x);assert r['dividend_declared']==0. and a['retained']==-40. and a['cash']==130.
 # prior-period receivable collected: cash_in=40, no declared_in => legal income unaffected.
 x.update(cash_in=40.);a,r=step(s,x);assert r['np']==60. and a['retained']==-40. and a['cash']==170.
 return {'production_step_literal_cash':100,'production_step_literal_retained':80,'loss_block_dividend':0,'old_receivable_no_new_profit':60}

def main():
 scenarios={
 'base':{},'core_low':{'k':.11,'mature_profit_factor':.95,'mature_growth':.01,'B_ownership':124547255/239459033,'B_sales_factor':.95,'royalty_rate':.07},
 'core_high':{'k':.10,'mature_profit_factor':1.05,'mature_growth':.025,'B_sales_factor':1.05,'royalty_rate':.09},
 'structural_pressure':{'mature_profit_factor':.72,'mature_growth':0.,'B_sales_factor':.7,'overseas_factor':.45,'rd_factor':.85,'k':.12},
 'clinical_delay_2y':{'delay':2,'B_sales_factor':.90,'rd_factor':1.10},
 'royalty_zero':{'overseas_factor':0.,'rd_factor':.70,'B_sales_factor':.90},
 'royalty_zero_fixed_spend':{'overseas_factor':0.},
 'no_B_clinical_success':{'B_sales_factor':.6,'overseas_factor':0.,'rd_factor':1.0},
 'growth_without_returns':{'mature_growth':.04,'incremental_return':.06},
 'strong_commercial':{'B_sales_factor':1.25,'overseas_factor':1.25,'mature_growth':.03,'rd_factor':1.10},
 'S_retained_old_budget':{'S_retained':6000.,'S_reserve':500.,'S_loss_retained':0.},
 'S_capital_release_20':{'S_capital_release_year':20},
 'S_capital_release_30':{'S_capital_release_year':30},
 'S_capital_release_40':{'S_capital_release_year':40},
 'S_capital_release_20_cost10pct':{'S_capital_release_year':20,'S_capital_release_cost':.10},
 'S_capital_release_30_cost10pct':{'S_capital_release_year':30,'S_capital_release_cost':.10},
 'S_capital_release_40_cost10pct':{'S_capital_release_year':40,'S_capital_release_cost':.10},
 'S_loss_1000':{'S_loss_retained':-1000.},
 'S_reserve_cap_1000':{'S_reserve_cap':1000.},
 'S_loss_pool_20pct':{'S_loss_fraction':.20,'S_loss_retained':-1000.},
 'other_subs_attribution_85pct':{'S_ownership':.85},
 'other_subs_attribution_92pct':{'S_ownership':.92},
 'upstream_delay_3y':{'upstream_delay':3},
 'parent_cash_reallocated':{'parent_cash':1500.},
 'working_payment_500':{'extra_parent_working':500.},
 'debt_cost_6pct':{'refinance_rate':.06},
 'no_net_refinancing_5y':{'debt_paydown':.20},
 'B_cash_lower_500':{'B_cash':6300.},
 'B_exit_delayed_30':{'exit_B_year':30},
 'B_exit30_lag3':{'exit_B_year':30,'upstream_delay':3},
 'B_legal_loss_extra_1000':{'B_loss':-5617.046},
 'discount_plus_1pct':{'k':.115}}
 out={'currency':'CNY','unit':'million except per_share','information_cutoff':'2026-10-28T11:45:00+00:00','facts':FACTS,'hand_tests':hand_tests(),'scenarios':{}}
 for n,kw in scenarios.items():
  try:out['scenarios'][n]=calc(**kw)
  except AssertionError as e:out['scenarios'][n]={'infeasible':True,'reason':str(e)}
 # Independent economic cross-check: no mature growth; smaller marketed-drug footprint and
 # endometrial-led rights, rather than recycling main forecast profit or a market PE. Same legal cash chain.
 aux_components={'endometrial':[0,250,400,550,650,700,750,800,800,800],'breast':[0,0,0,200,350,500,650,750,800,800],'lung':[0,0,0,150,300,450,600,700,800,900]}
 out['auxiliary_earnings_power']={}
 for name,m in [('low',.95),('high',1.05)]:
  out['auxiliary_earnings_power'][name]=calc(mature_growth=0.,mature_profit_factor=m,drug_sales_curve=[1700,2100,2500,2850,3200,3500,3750,4000,4200,4400],overseas_components=aux_components,rd_factor=.90,k=.105)
 out['auxiliary_earnings_power']['normalized_mature_aftertax_equity_income_m']=(500+1250*.8861+750*.7212)*.75+180
 out['auxiliary_earnings_power']['capitalization_factor_derived_not_market']=1/.105
 # Convergence check uses same stable policy after y30; no growing terminal B claim.
 b=copy.deepcopy(BASE);con={}
 for h in (30,40,60):con[str(h)]=run(b,h)['current_value_per_share']
 out['tail_convergence']=con
 out['tail_convergence_all_scenarios']={}
 for name,kw in scenarios.items():
  pp=copy.deepcopy(BASE);pp.update(kw);vals={}
  for h in (30,40,60):
   try: vals[str(h)]=run(pp,h)['current_value_per_share']
   except AssertionError as e: vals[str(h)]={'infeasible':True,'reason':str(e)}
  out['tail_convergence_all_scenarios'][name]=vals
  if all(isinstance(v,float) for v in vals.values()): assert max(vals.values())-min(vals.values())<1e-8,(name,vals)
 out['conditional_capital_recovery']={}
 for name,result in out['scenarios'].items():
  if name.startswith('S_capital_release_') and not result.get('infeasible'):
   pp=result['parameters'];payments=[]
   for row in result['annual']:
    for entity in ('S','SL'):
     r=row['entities'][entity]
     if 'capital_return' in r:
      parent_principal=r['capital_return']*pp['S_ownership']
      payments.append({'entity':entity,'declaration_year':row['year'],'parent_receipt_year':row['year']+pp['upstream_delay'],'gross_capital':r['capital_release_gross'],'cash_transaction_cost':r['capital_release_cost'],'net_capital_return':r['capital_return'],'parent_principal':parent_principal,'parent_receipt_PV_per_share':parent_principal/(1+pp['k'])**(row['year']+pp['upstream_delay'])/FACTS['shares_m']})
   out['conditional_capital_recovery'][name]={'payments':payments,'holder_value_per_share':result['current_value_per_share'],'net_value_change_vs_no_capital_return':result['current_value_per_share']-out['scenarios']['base']['current_value_per_share'],'interpretation':'gross receipt PV is NOT net shareholder uplift: future interest falls and costs/taxes/legal payout timing are fully rerun; capital basis deducted from parent declared income'}
 out['published_summary']={'method_1':'legal_holder_distribution_DCF','method_2':'zero_growth_earnings_power_plus_limited_drug_rights','value_range_per_share':{'low':round(out['scenarios']['core_low']['current_value_per_share'],2),'high':round(out['scenarios']['core_high']['current_value_per_share'],2)},'year_5_equity_value_range_per_share':{'low':round(out['scenarios']['core_low']['year5_value_per_share'],2),'high':round(out['scenarios']['core_high']['year5_value_per_share'],2)},'distributions_per_share':out['scenarios']['base']['year5_distributions']}
 print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False))
if __name__=='__main__':main()
