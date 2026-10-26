#!/usr/bin/env python3
"""603444, CNY billion, stdlib, deterministic owner economics and legal cash waterfalls.
All undisclosed entity positions are research budgets, not reported legal balances.
Run: python 2026-Q3.py [output.json]
"""
import json,copy,sys,math
from pathlib import Path
SHARES=0.071756301 # billion shares, excludes treasury, not a cancellation
INPUTS={
 'as_of':'2026-10-26T09:00:00+00:00','units':'CNY billion unless per share',
 'actual':{'Q3_revenue':1.76962619448,'YTD_revenue':5.49646849226,'YTD_net':1.88896527756,'YTD_common_net':1.58500744294,'YTD_CFO':1.91521148827,'YTD_capex_net':-.04833308598,'cash_equivalents':4.88721662120,'trading_assets':.72822537253,'other_bonds':.143016878,'current_noncurrent_assets':.12058872248,'minority_equity':1.20568476784,'parent_cash':.01946502401,'parent_RE':1.23207381943,'parent_reserve':.0360205505,'parent_capital':.072041101,'parent_old_dividend_receivable':.104787,'shares_issued':72041101,'treasury_shares':284800,'declared_Q3_dividend_ps':6},
 'initial_revenue':7.1,'tax':.17,'interest_on_idle_cash':0.01,
 'entities':{
 'P':{'cash':.01946502401,'re':1.23207381943,'reserve':.0360205505,'capital':.072041101,'debt':0.,'inv':.2220215956},
 'D':{'cash':2.62537073368,'re':1.17640884865,'reserve':.0260471665,'capital':.052094333,'debt':0.,'inv':1.08558347005},
 'L':{'cash':1.0595825702,'re':1.70,'reserve':.015,'capital':.03,'debt':0.,'inv':0.},
 'S':{'cash':2.5,'re':1.45,'reserve':.05,'capital':.1,'debt':0.,'inv':.33742553335}},
 'old_dividend_receivable':.104787,'old_dividend_payer':'D',
 'debt_limit_per_entity':.10,'debt_rate':.05,'parent_cash_floor':.04,
 'initial_investment_book':1.645030599,'fund_other_holder_interest_excluded':.01441652995,'entrusted_customer_cash_excluded':.027484,'financial_asset_bridge_estimates':{'other_current_excluding_H1_tax_proxy':.21439075068,'other_noncurrent_CD_budget':.14227450039,'current_noncurrent_employee_loan_excluded':-.00381051739,'net_addition_to_D':.35285473368},
 'scope':'P listed parent; D wholly-owned development envelope; L 60%-owned Leiting legal holding; S publishing operating envelope wholly owned by L; D/S are legal-source budgeting envelopes, not reported consolidated distributable reserves',
 'timing':'Y1=2026-10-27 to 2027-10-26; opening 9/30 balances rolled unchanged to cutoff, a budget; all annual payouts year-end approximation; announced 6 yuan included in Y1 total',
 'terminal_policy':'After Y5 annual legal waterfall continues to Y10; Y11 operating distributions capitalize at g=0, maintenance capex=depreciation, all continuing R&D/marketing expensed. Residual non-distributable excess cash earns 1% net income already in steady dividends; no principal return is added in core. Conditional full-release increment removes the capitalized income on released principal and is outside core, not an executable distribution promise.'}
BASE={'revenue_components':{'legacy':[2.05,1.91,1.78,1.66,1.55],'domestic_2025':[2.35,1.98,1.70,1.49,1.34],'overseas':[1.65,1.60,1.48,1.40,1.34],'agency_and_new':[.65,.68,.72,1.20,1.77]},'gross':[.935,.933,.93,.925,.92],'selling':[.35,.345,.34,.34,.34],'rd':[.92,.94,.95,1.,1.04],'admin':[.35,.35,.35,.36,.37],'other_cost':.005,'profit_split':{'P':.03,'D':.57,'S':.40},'payout':.75,'upstream':.90,'cash_reserve_ratio':.18,'nwc_ratio':.03,'net_capex':.015,'maintenance_capex':.035,'asset_realization':.80,'discount':.10,'tail_growth':.01,'residual_recovery':0.,'residual_delay_after10':5,'delay_years':0,'extra_wc':0,'cash_shift':0,'legal_reserve_shift_D':0.,'legal_reserve_shift_S':0.}
def legal_profit(e,profit):
 old=e['re']; e['re']+=profit
 eligible=max(0.,max(0.,profit)-max(0.,-old))
 transfer=min(max(0.,.5*e['capital']-e['reserve']),.1*eligible)
 e['re']-=transfer;e['reserve']+=transfer
 return transfer

def distribute(e,target,floor):
 d=min(max(0.,target),max(0.,e['re']),max(0.,e['cash']-floor))
 e['cash']-=d;e['re']-=d
 return d

def operate(rev,gross,sell,rd,admin,tax,other):
 ebit=rev*(gross-sell-other)-rd-admin
 return {'revenue':rev,'gross_profit':rev*gross,'selling':rev*sell,'rd':rd,'admin':admin,'ebit':ebit,'tax':max(0.,ebit)*tax,'net':ebit-max(0.,ebit)*tax}

def run(p):
 E=copy.deepcopy(INPUTS['entities']);E['D']['cash']+=p['cash_shift'];E['S']['cash']-=p['cash_shift']
 E['D']['re']+=p['legal_reserve_shift_D'];E['S']['re']+=p['legal_reserve_shift_S']
 rows=[];prev=INPUTS['initial_revenue'];fail=False;old=INPUTS['old_dividend_receivable']; inv0={k:v['inv'] for k,v in E.items()}
 group_open=sum(e['cash'] for e in E.values());own_open=E['P']['cash']+E['D']['cash']+.6*(E['L']['cash']+E['S']['cash'])
 for y in range(1,22):
  if y<=5:
   rev=sum(v[y-1] for v in p['revenue_components'].values());gross=p['gross'][y-1];sell=p['selling'][y-1];rd=p['rd'][y-1];admin=p['admin'][y-1]
  else:
   factor=(1+p['tail_growth'])**(min(y,10)-5);rev=sum(v[4] for v in p['revenue_components'].values())*factor;gross=p['gross'][4];sell=p['selling'][4];rd=p['rd'][4]*factor;admin=p['admin'][4]*factor
  op=operate(rev,gross,sell,rd,admin,INPUTS['tax'],p['other_cost'])
  open_cash=sum(e['cash'] for e in E.values());open_debt=sum(e['debt'] for e in E.values());interest=0.;borrow=0.;repay=0.;reserves={};cashflow=0.;realized=0.;loss=0.;entity_flow={}
  # operating funding cost, external financing capped at legal entity envelope; never free parental subsidy
  for k,e in E.items():
   opening=copy.deepcopy(e)
   s=p['profit_split'].get(k,0);intr=e['debt']*INPUTS['debt_rate'];interest+=intr
   financial_income=max(0.,e['cash'])*INPUTS['interest_on_idle_cash']
   profit=op['net']*s-intr+financial_income
   capex=p['net_capex']*s if y<=5 else 0.
   wc=(rev-prev)*p['nwc_ratio']*s+(p['extra_wc']*s if y==1 else 0.)-(p['extra_wc']*s if y==3 else 0.)
   fcf=profit-capex-wc
   e['cash']+=fcf;cashflow+=fcf
   if 6<=y<=10:
    book=inv0[k]/5;proceeds=book*p['asset_realization'];e['inv']-=book;e['cash']+=proceeds;profit+=proceeds-book;realized+=proceeds;loss+=book-proceeds
   entity_flow[k]={'opening':opening,'own_statutory_profit':profit,'own_operating_FCFE':fcf,'incremental_capex':capex,'change_non_cash_working_capital':wc,'maintenance_capex_and_depreciation_each':p['maintenance_capex']*s,'interest':intr,'financial_income':financial_income}
   reserves[k]=legal_profit(e,profit)
   if e['cash']<0:
    need=-e['cash'];b=min(need,max(0.,INPUTS['debt_limit_per_entity']-e['debt']));e['debt']+=b;e['cash']+=b;borrow+=b
    if e['cash'] < -1e-9:fail=True
  # collect pre-existing D payable, recognized in P RE before opening date: no new income
  collected=old if y==max(1,p['delay_years']+1) else 0.
  if collected:
   collected=min(collected,max(0.,E['D']['cash']));E['D']['cash']-=collected;E['P']['cash']+=collected;old-=collected
  floors={'P':INPUTS['parent_cash_floor'],'D':rev*p['cash_reserve_ratio']*.45,'S':rev*p['cash_reserve_ratio']*.55,'L':.03}
  # repay external debt before dividends
  for k,e in E.items():
   z=min(e['debt'],max(0,e['cash']-floors[k]));e['debt']-=z;e['cash']-=z;repay+=z
  allow=y>p['delay_years'];up={};minority=0.
  for src,dst,stake in [('S','L',1.),('L','P',.6),('D','P',1.)]:
   e=E[src]
   target=(up.get('S',0.) if src=='L' else max(0.,op['net']*p['profit_split'].get(src,0))*p['upstream']) if y<=5 else 1e6
   d=distribute(e,target if allow else 0.,floors[src]);up[src]=d
   E[dst]['cash']+=d*stake;legal_profit(E[dst],d*stake);minority+=d*(1-stake)
  common_net=op['net']*(1-.4*p['profit_split']['S'])-sum(entity_flow[k]['interest']*(.6 if k in ('L','S') else 1.) for k in E)
  target=max(6*SHARES,p['payout']*max(0.,common_net)) if y==1 else p['payout']*max(0.,common_net)
  if y>5:target=1e6
  dividend=distribute(E['P'],target,floors['P'])
  if y==1 and dividend+1e-9<6*SHARES: fail=True # declared cash obligation cannot silently disappear
  end=sum(e['cash'] for e in E.values())
  assert abs(end-(open_cash+cashflow+realized+borrow-repay-minority-dividend))<1e-7
  assert all(e['reserve']<=.5*e['capital']+1e-8 for e in E.values())
  assert abs(sum(e['debt'] for e in E.values())-open_debt-borrow+repay)<1e-8
  if fail: # report, but never provide a feasible valuation for this run
   pass
  rows.append({'year':y,'calendar_end':2026+y,**op,'common_operating_net':common_net,'group_operating_FCFE':cashflow,'investment_sale':realized,'investment_loss':loss,'external_borrow':borrow,'external_repay':repay,'interest':interest,'old_receivable_collected':collected,'upstream_dividend':up,'minority_dividend':minority,'holder_dividend':dividend,'dividend_ps':dividend/SHARES,'requested_dividend':target if y<=5 else None,'cash_floors':floors,'statutory_transfers':reserves,'entity_flows':entity_flow,'entities':copy.deepcopy(E),'group_cash':end,'old_receivable_remaining':old,'feasible':not fail})
  prev=rev
 # Tail operating dividend and residual capital use the SAME y11 legal/cash state. No second legal profit budget.
 r=p['discount'];y10=rows[9];y11=rows[10]
 # exclude transitory releases: only owner net recurring operations, capped by actual legal waterfall payout
 sustainable=y11['holder_dividend'] # includes cash interest: residual principal is NOT added to core value
 operation_tv10=sustainable/r
 assert p['residual_recovery']==0., 'Core paths do not assume undocumented capital return'
 # Undistributed cash after the y11 operating dividend; keep permanent operating liquidity and all debts.
 excess=0.
 for k,e in y11['entities'].items():
  weight=.6 if k in ('L','S') else 1.
  excess+=weight*max(0,e['cash']-y11['cash_floors'][k]-e['debt'])
 # Cash claim is not called distributable profit. Core principal release is zero; conditional full release is outside core.
 residual_pv10=excess*p['residual_recovery']/(1+r)**p['residual_delay_after10']
 tv10=operation_tv10+residual_pv10
 tv5=sum(rows[t-1]['holder_dividend']/(1+r)**(t-5) for t in range(6,11))+tv10/(1+r)**5
 pv5=sum(rows[t-1]['holder_dividend']/(1+r)**t for t in range(1,6))
 value=(pv5+tv5/(1+r)**5)/SHARES
 # Independent economic FCFE cross-check: attributable free cash flow and attributable surplus ownership,
 # same continuing operating costs, maintenance and minority claims, no interest income repeated.
 own_liquid=own_open;floor0=.04+.03*.6+INPUTS['initial_revenue']*p['cash_reserve_ratio']*(.45+.55*.6)
 own_inv=INPUTS['entities']['P']['inv']+INPUTS['entities']['D']['inv']+.6*INPUTS['entities']['S']['inv']
 econ_pv=sum((row['common_operating_net']-(p['net_capex']+(row['revenue']-(INPUTS['initial_revenue'] if row['year']==1 else rows[row['year']-2]['revenue']))*p['nwc_ratio'])*(1-.4*p['profit_split']['S']) if row['year']<=5 else row['common_operating_net']-(row['revenue']-rows[row['year']-2]['revenue'])*p['nwc_ratio']*(1-.4*p['profit_split']['S']))/(1+r)**row['year'] for row in rows[:10])
 econ_pv+=rows[10]['common_operating_net']/r/(1+r)**10+max(0,own_liquid-floor0)+own_inv*p['asset_realization']/(1+r)**8
 return {'parameters':p,'years':rows,'value_per_share':None if fail else value,'terminal_y5_per_share':None if fail else tv5/SHARES,'first5_dividends_ps':[a['dividend_ps'] for a in rows[:5]],'terminal_share_of_PV':None if fail or abs(pv5+tv5/(1+r)**5)<1e-12 else tv5/(1+r)**5/(pv5+tv5/(1+r)**5),'terminal_detail':{'steady_dividend':sustainable,'operating_value_y10':operation_tv10,'residual_excess_cash_y11':excess,'residual_value_y10':residual_pv10,'conditional_full_release_increment_today_ps':max(0,excess*(1-INPUTS['interest_on_idle_cash']/r))/(1+r)**10/SHARES,'capitalized_residual_interest_today_ps':excess*INPUTS['interest_on_idle_cash']/r/(1+r)**10/SHARES,'steady_financial_income_in_dividend':sustainable-y11['common_operating_net'],'legal_re_after_operating_y11':{k:e['re'] for k,e in y11['entities'].items()},'cash_after_operating_y11':{k:e['cash'] for k,e in y11['entities'].items()}},'economic_FCFE_crosscheck_ps':econ_pv/SHARES,'feasible':not fail,'cash_conservation_pass':True,'steady_state_convergence':{'y11_dividend':rows[10]['holder_dividend'],'y21_dividend':rows[20]['holder_dividend'],'cash_max_change':max(abs(rows[20]['entities'][k]['cash']-rows[10]['entities'][k]['cash']) for k in E),'Y11_to_Y21_NI_change':rows[20]['common_operating_net']-rows[10]['common_operating_net']}}

def params(**kw):
 p=copy.deepcopy(BASE);p.update(kw);return p

def tests():
 # These invoke production functions, with independent hand amounts.
 e={'cash':100.,'re':-20.,'reserve':2.,'capital':20.}
 assert legal_profit(e,30.)==1. and e['re']==9.
 assert distribute(e,20.,10.)==9. and e['cash']==91. and e['re']==0.
 e={'cash':30.,'re':5.,'reserve':9.5,'capital':20.};assert legal_profit(e,20.)==.5
 assert distribute(e,100.,12.)==18. and e['re']==6.5
 z=operate(100,.9,.2,10,5,.2,.01);assert abs(z['net']-43.2)<1e-9
 e={'cash':3.,'re':5.,'reserve':10.,'capital':20.};assert distribute(e,4.,2.)==1.
 return {'negative_RE_then_reserve_cap':True,'cash_limited_dividend':True,'operating_function_handcase':True}
def main():
 sc={'base':params(),'core_low':params(discount=.105,asset_realization=.75,residual_recovery=0.,tail_growth=0.),'core_high':params(discount=.095,asset_realization=.85,residual_recovery=0.,tail_growth=.02)}
 cyc=copy.deepcopy(BASE['revenue_components']);cyc={k:[v[0]*.85,v[1]*.9,*v[2:]] for k,v in cyc.items()}
 sc['cyclical']=params(revenue_components=cyc,extra_wc=.25,upstream=.60)
 structural={'legacy':[1.9,1.6,1.35,1.15,1.],'domestic_2025':[1.9,1.4,1.,.7,.5],'overseas':[1.3,1.,.8,.7,.6],'agency_and_new':[.5,.4,.4,.4,.4]}
 sc['structural']=params(revenue_components=structural,gross=[.92]*5,selling=[.38,.37,.35,.33,.32],rd=[.92,.88,.75,.6,.5],admin=[.35,.32,.28,.24,.22],payout=.5,tail_growth=0.,discount=.115,asset_realization=.6,residual_recovery=0.)
 opt={'legacy':[2.1,2.,1.9,1.8,1.7],'domestic_2025':[2.5,2.3,2.1,2.,1.9],'overseas':[1.9,2.1,2.2,2.3,2.4],'agency_and_new':[.7,.8,1.1,1.8,2.6]}
 sc['optimistic']=params(revenue_components=opt,rd=[.96,1.02,1.12,1.25,1.4],admin=[.36,.38,.4,.42,.45],selling=[.35,.34,.34,.34,.34],tail_growth=.02,discount=.095)
 sc['cash_delay']=params(delay_years=2,extra_wc=.4)
 # Diagnostics, not complete business alternatives.
 sc['sales_plus_3pp']=params(selling=[x+.03 for x in BASE['selling']])
 sc['new_projects_zero']=params(revenue_components={**copy.deepcopy(BASE['revenue_components']),'agency_and_new':[.65,.68,.72,.72,.72]},tail_growth=0.)
 sc['cash_position_shift']=params(cash_shift=-.7)
 sc['reserve_plus_5pp']=params(cash_reserve_ratio=.23)
 sc['lower_legal_reserve']=params(legal_reserve_shift_D=-.37640884865,legal_reserve_shift_S=-.8)
 sc['higher_legal_reserve']=params(legal_reserve_shift_D=.2,legal_reserve_shift_S=.2)
 stress=run(params(revenue_components={k:[0]*5 for k in BASE['revenue_components']},rd=[5]*5,admin=[2]*5))
 assert not stress['feasible'] and stress['value_per_share'] is None
 out={'inputs':INPUTS,'tests':{**tests(),'zero_dividend_insolvency_fails':True},'scenarios':{k:run(v) for k,v in sc.items()}}
 # Two TV marks from exactly the same base Y5 entity state: keep first five years/base budgets unchanged;
 # endpoint r/tail only changes post-Y5 capitalization (all future entity paths rerun, Y5 identical).
 for name,result in out['scenarios'].items():
  if result['feasible']:
   convergence=result['steady_state_convergence']
   assert abs(convergence['y11_dividend']-convergence['y21_dividend'])<1e-8, name
   assert convergence['cash_max_change']<1e-8 and abs(convergence['Y11_to_Y21_NI_change'])<1e-8, name
 assert out['scenarios']['base']['years'][4]['entities']==out['scenarios']['core_low']['years'][4]['entities']==out['scenarios']['core_high']['years'][4]['entities']
 out['tests']['all_feasible_steady_state_convergence']=True
 out['tests']['same_core_Y5_entity_state']=True
 out['same_base_Y5_terminal_range']=[out['scenarios'][k]['terminal_y5_per_share'] for k in ('core_low','core_high')]
 out['core_range_rounded']=[round(out['scenarios']['core_low']['value_per_share']),round(out['scenarios']['core_high']['value_per_share'])]
 path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('2026-Q3-output.json')
 path.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'),sort_keys=True)+'\n')
 print(json.dumps({k:{'value':v['value_per_share'],'tv5':v['terminal_y5_per_share'],'D':v['first5_dividends_ps'],'feasible':v['feasible']} for k,v in out['scenarios'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
