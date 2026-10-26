#!/usr/bin/env python3
"""江苏金租 2026Q3. stdlib, CNY billion / billion shares. Run from any cwd.
Financial common-equity cash-flow model; liabilities are funding inputs, never EV deductions.
All projections and legal/treasury allocations are research budgets, not legal certification.
"""
import argparse, copy, json, math
from pathlib import Path
ASOF='2026-10-26T22:00:00+00:00'
L0=180.4090928
E0=26.74379803925
NCI0=.50266144761
A0=193.97122128183
F0=155.02680677592
NL0=166.72476179497-F0
C0=6.65087964110
SHARES=5.791866431
REGISTERED=5.793205763 # charter Dec2025 art6; NOT accounting paid-in shares
# Ordinary-attributable balance sheet: common assets deduct NCI, liabilities unchanged.
K_ASSET=(A0-NCI0-NL0)/L0
C_RATIO=C0/L0
RWA_RATIO=181.8919731/L0
PARENT_C0=2.4333936624 # last separately disclosed H1, no fabricated Q3 parent cash
PARENT_E0=25.27074990843+.925*(2.69561988815-1.70915956735)
INVESTMENT=.563
SUB_E0=E0-PARENT_E0+INVESTMENT
SUB_RATIO=SUB_E0/L0
INITIAL=dict(L=L0,E=E0,F=F0,C=C0,shares=SHARES,registered=REGISTERED,
 parent_E=PARENT_E0,parent_RE=8.25490944809+.925*(2.69561988815-1.70915956735),
 reserve=2.05970498092,risk_reserve=2.36947682244,parent_C=PARENT_C0,
 sub_E=SUB_E0,sub_RE=9.73337724145-(8.25490944809+.925*(2.69561988815-1.70915956735)),sub_reserve=0.,sub_risk=2.38216757461-2.36947682244,
 sub_receivable=0.0,sub_cash_pending=0.0,investment=INVESTMENT,sub_commitment=.55,minority_subscription=0.,approved_distribution_unpaid=.14*SHARES)
BASE=dict(growth=[.08,.08,.07,.06,.05],tail_growth=.03,loan_yield=.0600,
 tail_yield=.0565,funding=.0200,tail_funding=.0210,credit=.0090,tail_credit=.0090,
 fees=.0034,tail_fees=.0032,opex=.0041,tail_opex=.0040,cash_yield=.015,
 tax=.25,common_profit_share=.985,parent_profit_share=.925,
 capital_ratio=.14,rwa_ratio=RWA_RATIO,intangible_ratio=.1028591/L0,
 fund_cap=.15,payout=.50,parent_cash_ratio=PARENT_C0/L0,
 sub_cap_ratio=SUB_RATIO,sub_upstream=True,upstream_start=6,collection_delay=0,parent_capital_share=.90,
 equity_budget=0.0,issue_book_multiple=.80,discount=.0975,
 yield_shift=0.,funding_shift=0.,credit_shift=0.,rwa_shift=0.,
 cash_ratio=C_RATIO,asset_ratio=K_ASSET,allowance_ratio=.0358,
 parent_risk_ratio=.015*.88,sub_risk_ratio=.015*.12,
 stop_dividends=False,shock={},minimum_growth=-.30)

def params(case,t):
 p=copy.deepcopy(case)
 fade=max(0.,min(1.,(t-5)/5.))
 p['g']=case['growth'][t-1] if t<=5 else case['tail_growth']
 for a,b in [('loan_yield','tail_yield'),('funding','tail_funding'),('credit','tail_credit'),('fees','tail_fees'),('opex','tail_opex')]:
  p[a]=case[a]*(1-fade)+case[b]*fade
 p['loan_yield']+=case['yield_shift'];p['funding']+=case['funding_shift'];p['credit']+=case['credit_shift'];p['rwa_ratio']+=case['rwa_shift']
 p.update(case.get('shock',{}).get(str(t),{}))
 return p

def legal_profit(re,profit,reserve,registered,risk,required_risk):
 # Current profits first repair accumulated losses. Reserve transfer is not cash expense.
 after_loss=max(0.,profit-max(0.,-re))
 statutory=min(.1*after_loss,max(0.,.5*registered-reserve))
 available=max(0.,re+profit-statutory)
 risk_transfer=min(available,max(0.,required_risk-risk))
 return dict(RE=re+profit-statutory-risk_transfer,reserve=reserve+statutory,
             risk=risk+risk_transfer,statutory_transfer=statutory,risk_transfer=risk_transfer)

def economics(s,p,g,D,issue=0.):
 L=s['L']*(1+g);avg=(s['L']+L)/2
 # Common profit allocation follows attributable earnings. NCI excluded, not deducted twice.
 taxfactor=(1-p['tax'])*p['common_profit_share']
 C=p['cash_ratio']*L
 gross=(p['loan_yield']-p['fees']-p['opex']-p['credit'])*avg+p['cash_yield']*(s['C']+C)/2
 funding_constant=(s['F']+p['asset_ratio']*L-s['E']+D-issue)/2
 P=taxfactor*(gross-p['funding']*funding_constant)/(1-taxfactor*p['funding']/2)
 if P<0: # no immediate cash monetisation of tax losses / deferred-tax assets
  taxfactor=p['common_profit_share']
  P=taxfactor*(gross-p['funding']*funding_constant)/(1-taxfactor*p['funding']/2)
 E=s['E']+P+issue-D
 F=p['asset_ratio']*L-E
 return dict(L=L,avgL=avg,C=C,P=P,E=E,F=F,credit_charge=p['credit']*avg,
             funding_cost=p['funding']*(s['F']+F)/2,
             loan_interest=p['loan_yield']*avg)

def one_year(s,p,t):
 """Production function; financing, cash, parent law and capital change dividends/scale."""
 s=copy.deepcopy(s)
 requested_g=p['g'];g=requested_g;issue=0.;issue_price=None
 min_g=p['minimum_growth']
 # Reduce new lending before breaching external net funding capacity, retaining scheduled collections.
 debt_limit=s['F']*(1+p['fund_cap'])
 def feasible_growth(x):
  z=economics(s,p,x,0)
  return z['F']<=debt_limit+1e-9
 if not feasible_growth(g):
  if not feasible_growth(min_g):
   return dict(status='infeasible_funding',year=t,opening=s,obligations_preserved=dict(debt=s['F'],parent_RE=s['parent_RE'],approved_distribution_unpaid=s['approved_distribution_unpaid'],subsidiary_commitment=s['sub_commitment']),distribution=0.,PV=None,TV=None),s
  lo,hi=min_g,g
  for _ in range(70):
   m=(lo+hi)/2
   if feasible_growth(m):lo=m
   else:hi=m
  g=lo
 z=economics(s,p,g,0)
 required=(p['capital_ratio']*p['rwa_ratio']+p['intangible_ratio'])*z['L']
 # If ordinary capital does not cover target, shrink lending again; only explicitly budgeted
 # equity subscriptions are available. An unresolved solvency/funding gap yields typed null.
 if z['E']<required:
  short=required-z['E']
  if p['equity_budget']>0:
   issue_price=p['issue_book_multiple']*s['E']/s['shares']
   tt=(1-p['tax'] if z['P']>=0 else 1)*p['common_profit_share']
   benefit=tt*p['funding']/2/(1-tt*p['funding']/2)
   # Approved 0.14/share remains an obligation even in a stress recapitalisation.
   declared=.14*s['shares'] if t==1 else 0.
   dilution_distribution=.14/issue_price if t==1 and issue_price>0 else 0.
   issue=min(p['equity_budget'],(short/(1+benefit)+declared)/(1-dilution_distribution))
   if issue_price<=0: return dict(status='infeasible_equity',year=t,opening=s,distribution=0.,PV=None,TV=None),s
   z=economics(s,p,g,0,issue)
  if z['E']<required-1e-7:
   lo,hi=min_g,g
   if economics(s,p,lo,0,issue)['E'] < (p['capital_ratio']*p['rwa_ratio']+p['intangible_ratio'])*s['L']*(1+lo):
    return dict(status='infeasible_capital',year=t,opening=s,obligations_preserved=dict(debt=s['F'],capital_requirement=required),distribution=0.,PV=None,TV=None),s
   for _ in range(70):
    m=(lo+hi)/2;q=economics(s,p,m,0,issue)
    if q['E']>=(p['capital_ratio']*p['rwa_ratio']+p['intangible_ratio'])*q['L']:lo=m
    else:hi=m
   g=lo;z=economics(s,p,g,0,issue)
   required=(p['capital_ratio']*p['rwa_ratio']+p['intangible_ratio'])*z['L']
 # Conditional approved-plan cash commitment: carry until funded, never silently delete.
 provisional_parent_need=max(0.,required-s['E'])
 available_parent=s['parent_C']+p['parent_profit_share']*z['P']+issue-provisional_parent_need-p['parent_cash_ratio']*z['L']
 contribution=s['sub_commitment'] if available_parent>=s['sub_commitment'] else 0.
 investment=s['investment']+contribution
 minority_subscription=contribution*45/55
 shares=s['shares']+(issue/issue_price if issue else 0)
 registered=s['registered']+(issue/issue_price if issue else 0) # RMB1 par per new share; same-year registration budget
 # Forecast sub-bucket includes only ordinary-attributable claims. Each actual subsidiary
 # still needs separate board/solvency checks. Conservative reserve envelope is a budget.
 def limits(D):
  q=economics(s,p,g,D,issue);P=q['P'];L=q['L']
  sub_profit=(1-p['parent_profit_share'])*P
  sub_law=legal_profit(s['sub_RE'],sub_profit,s['sub_reserve'],investment,s['sub_risk'],p['sub_risk_ratio']*L)
  sub_needed=max((p['sub_cap_ratio']+(investment-INVESTMENT)/L0)*L,investment+sub_law['reserve']+sub_law['risk'])
  declared=max(0.,min(sub_law['RE'],s['sub_E']+contribution+sub_profit-sub_needed)) if p['sub_upstream'] and t>=p['upstream_start'] else 0.
  # Optional one-year delayed collection: recognise this year's declared dividend once,
  # collect prior receivable without recognising income twice.
  upstream_cash=s['sub_receivable'] if p['collection_delay'] else declared
  receivable=declared if p['collection_delay'] else 0.
  parent_profit=p['parent_profit_share']*P+declared
  law=legal_profit(s['parent_RE'],parent_profit,s['reserve'],registered,s['risk_reserve'],p['parent_risk_ratio']*L)
  # Parent treasury budget: normal financing supports business net assets. All required
  # equity growth is earmarked first; sub funding retained locally is not parent cash.
  parent_need=max(0.,required-s['E'])-max(0.,sub_needed-s['sub_E'])
  parent_need=max(0.,parent_need)
  pc_floor=p['parent_cash_ratio']*L
  # Required capital finances cash as well as loans: avoid charging liquidity growth twice.
  parent_need=max(0.,parent_need-(pc_floor-s['parent_C']))
  pc_before=s['parent_C']+p['parent_profit_share']*P+upstream_cash+issue-parent_need-contribution
  cash_cap=max(0.,pc_before-pc_floor)
  common_cap=max(0.,q['E']+D-required)
  # Debt capacity is checked on the actual post-dividend balance sheet.
  financing_cap=max(0.,debt_limit-q['F']+D)
  desired=max(0.,p['payout']*P) if t<=5 else common_cap
  if t==1 and not p.get('test_ignore_declared',False):desired=max(desired,.14*shares)
  if p['stop_dividends']:desired=0.
  parent_cap=max(0.,s['parent_E']+parent_profit+issue-p['parent_capital_share']*required)
  cap=max(0.,min(desired,law['RE'],cash_cap,common_cap,financing_cap,parent_cap))
  return cap,q,law,sub_law,declared,upstream_cash,receivable,sub_needed,pc_before,parent_need
 D=0.
 for _ in range(120):
  cap,*_=limits(D)
  if abs(D-cap)<1e-11:break
  D=(D+cap)/2
 D=min(D,limits(D)[0]);cap,q,law,sl,decl,upcash,recv,subneed,pcbefore,parentneed=limits(D)
 if t==1 and s['approved_distribution_unpaid']>0 and D<.14*shares-1e-8:
  if g>min_g+1e-8:
   retry=copy.deepcopy(p);retry['g']=max(min_g,g-.02)
   rr,ss=one_year(s,retry,t);rr['requested_growth']=requested_g;rr['declared_dividend_scale_repair']=True
   return rr,ss
  return dict(status='infeasible_declared_distribution',year=t,opening=s,
   obligations_preserved=dict(debt=s['F'],declared_distribution=.14*shares,subsidiary_commitment=s['sub_commitment']),distribution=0.,PV=None,TV=None),s
 e=q['E'];sube=s['sub_E']+contribution+(1-p['parent_profit_share'])*q['P']-decl
 pe=s['parent_E']+p['parent_profit_share']*q['P']+decl+issue-D
 pc=pcbefore-D
 # Treasury surplus not paid is redeployed/reduces parent-level borrowing, not money
 # that can be added separately to group valuation. Record transfer explicitly.
 pc_floor=p['parent_cash_ratio']*q['L'];treasury_redeployment=max(0.,pc-pc_floor);pc-=treasury_redeployment
 state=dict(L=q['L'],E=e,F=q['F'],C=q['C'],shares=shares,registered=registered,parent_E=pe,
  parent_RE=law['RE']-D,reserve=law['reserve'],risk_reserve=law['risk'],parent_C=pc,
  sub_E=sube,sub_RE=sl['RE']-decl,sub_reserve=sl['reserve'],sub_risk=sl['risk'],
  sub_receivable=recv,sub_cash_pending=recv,investment=investment,sub_commitment=s['sub_commitment']-contribution,minority_subscription=s['minority_subscription']+minority_subscription,approved_distribution_unpaid=max(0.,s['approved_distribution_unpaid']-D) if t==1 else s['approved_distribution_unpaid'])
 # Cash conserved on ordinary-attributable financing balance sheet, including loan losses.
 net_asset_change=p['asset_ratio']*q['L']-s['E']-s['F']
 cash_residual=s['C']+q['P']+issue+(q['F']-s['F'])-D-(net_asset_change-(q['C']-s['C']))-q['C']
 equity_residual=s['E']+q['P']+issue-D-e
 parent_residual=s['parent_C']+p['parent_profit_share']*q['P']+upcash+issue-parentneed-contribution-D-treasury_redeployment-pc
 ownership_residual=pe+sube-investment-e
 legal_residual=s['parent_RE']+p['parent_profit_share']*q['P']+decl-law['statutory_transfer']-law['risk_transfer']-D-state['parent_RE']
 assert max(abs(cash_residual),abs(equity_residual),abs(parent_residual),abs(ownership_residual),abs(legal_residual))<1e-6
 assert D>=-1e-10 and state['parent_RE']>=-1e-8 if D>1e-9 else True
 assert q['F']<=debt_limit+1e-7
 assert e>=required-1e-6
 assert pe>=p['parent_capital_share']*required-1e-6
 if pc<pc_floor-1e-7:
  # Recoverable parent liquidity gap: reduce new production and recompute everything.
  if g>min_g+1e-8:
   retry=copy.deepcopy(p);retry['g']=max(min_g,g-.02)
   rr,ss=one_year(s,retry,t);rr['requested_growth']=requested_g;rr['parent_cash_scale_repair']=True
   return rr,ss
  return dict(status='infeasible_parent_cash',year=t,opening=s,obligations_preserved=dict(debt=s['F'],subsidiary_commitment=s['sub_commitment']),distribution=0.,PV=None,TV=None,parent_cash_result=pc,parent_cash_floor=pc_floor),s
 row=dict(status='ok',year=t,opening=s,closing=state,requested_growth=requested_g,actual_growth=g,
  ordinary_profit=q['P'],loan_interest=q['loan_interest'],funding_cost=q['funding_cost'],credit_charge=q['credit_charge'],
  required_common_capital=required,excess_common_capital=e-required,distribution=D,
  distribution_per_share=D/shares,equity_subscription=issue,issue_price=issue_price,
  parent_profit=p['parent_profit_share']*q['P']+decl,parent_standalone_profit=p['parent_profit_share']*q['P'],
  parent_statutory_transfer=law['statutory_transfer'],parent_risk_transfer=law['risk_transfer'],
  subsidiary_declared=decl,subsidiary_cash_received=upcash,subsidiary_required_capital=subneed,
  parent_cash_before_distribution=pcbefore,parent_earmarked_equity_investment=parentneed,
  parent_subsidiary_cash_subscription=contribution,minority_cash_subscription_excluded_from_common=minority_subscription,
  parent_treasury_redeployment=treasury_redeployment,
  ordinary_cash_conservation_residual=cash_residual,equity_conservation_residual=equity_residual,
  parent_cash_conservation_residual=parent_residual,ownership_residual=ownership_residual,
  parent_legal_profit_residual=legal_residual,parameters={k:v for k,v in p.items() if k not in ('growth','shock')})
 return row,state

def simulate(case,start=None,start_year=1,end_year=160):
 s=copy.deepcopy(INITIAL if start is None else start);rows=[]
 for t in range(start_year,end_year+1):
  row,s=one_year(s,params(case,t),t);rows.append(row)
  if row['status']!='ok':return dict(status=row['status'],rows=rows,PV=None,TV=None,terminal_state=s)
 return dict(status='ok',rows=rows,terminal_state=s)

def value_run(run,case,start_year=0):
 if run['status']!='ok':return dict(status=run['status'],PV=None,TV=None)
 r=case['discount'];rows=run['rows'];s=run['terminal_state'];last=rows[-1]['year'];g=case['tail_growth']
 nxt,ns=one_year(s,params(case,last+1),last+1)
 if nxt['status']!='ok' or r<=g:return dict(status='infeasible_tail',PV=None,TV=None)
 # Persistent ongoing capital and legal reserves remain in the production function.
 # At 160 years steady growth/payout and no share issuance are required, not presumed.
 dnext=nxt['distribution_per_share'];lastd=rows[-1]['distribution_per_share']
 steady_error=abs(dnext-lastd*(1+g))/max(1.,dnext)
 if steady_error>1e-6:return dict(status='nonsteady_tail',PV=None,TV=None,steady_error=steady_error)
 tv=dnext/(r-g)
 pv=sum(x['distribution_per_share']/(1+r)**(x['year']-start_year) for x in rows)+tv/(1+r)**(last-start_year)
 # Independent clean-surplus algebra on the same path checks full equity attribution;
 # issuance cases use per-share residual-income with actual dilution, not undiscounted B.
 b0=rows[0]['opening']['E']/rows[0]['opening']['shares'];ri=b0
 for x in rows:
  op=x['opening'];cl=x['closing']
  ri+=(cl['E']/cl['shares']-op['E']/op['shares']+x['distribution_per_share']-r*op['E']/op['shares'])/(1+r)**(x['year']-start_year)
 ri+=(tv-s['E']/s['shares'])/(1+r)**(last-start_year)
 assert abs(ri-pv)<1e-7
 return dict(status='ok',PV=pv,TV=tv,remaining_tail_PV=tv/(1+r)**(last-start_year),
  clean_surplus_value=ri,steady_error=steady_error,continuing_required_capital=nxt['required_common_capital'])

def assess(case):
 run=simulate(case);v=value_run(run,case)
 if run['status']=='ok':
  y5=run['rows'][4]['closing'];tail=simulate(case,y5,6);future=value_run(tail,case,5)
 else:future=dict(PV=None,TV=None,status=run['status'])
 return dict(parameters=case,valuation=v,year5_terminal=future,annual_rows=run['rows'])

def manual_tests():
 # Actual production legal function: profit 10 repairs RE -6, only 4 subject to 10%.
 z=legal_profit(-6,10,0,100,0,0);assert z==dict(RE=3.6,reserve=.4,risk=0,statutory_transfer=.4,risk_transfer=0)
 z=legal_profit(0,10,49.8,100,0,0);assert abs(z['statutory_transfer']-.2)<1e-12
 # Same economics function, debt financing: L100 ->110, E20, F80, asset=1,
 # yield10%, debt cost2%, tax0; D4 => P=(10.5-.01*(80+110-20+4))/.99=8.8484848.
 s=copy.deepcopy(INITIAL);s.update(L=100,E=20,F=80,C=0)
 p=copy.deepcopy(BASE);p.update(asset_ratio=1,cash_ratio=0,loan_yield=.1,funding=.02,fees=0,opex=0,credit=0,tax=0,common_profit_share=1,cash_yield=0)
 z=economics(s,p,.1,4)
 assert abs(z['P']-8.848484848484848)<1e-12
 assert abs(z['F']-85.15151515151516)<1e-12
 # Complete production one_year with independent literal answer, not an external identity.
 ss=copy.deepcopy(INITIAL);ss.update(L=100,E=100,F=90,C=10,shares=10,registered=10,
  parent_E=100,parent_RE=0,reserve=0,risk_reserve=0,parent_C=10,
  sub_E=.563,sub_RE=0,sub_reserve=0,sub_risk=0,sub_commitment=0)
 pp=copy.deepcopy(BASE);pp.update(g=0,asset_ratio=1.9,cash_ratio=.1,loan_yield=.1,funding=0,fees=0,opex=0,credit=0,
  tax=0,common_profit_share=1,parent_profit_share=1,cash_yield=0,capital_ratio=.5,rwa_ratio=1,
  intangible_ratio=0,parent_cash_ratio=.1,sub_cap_ratio=.00563,parent_risk_ratio=0,sub_risk_ratio=0)
 rr,cc=one_year(ss,pp,1)
 for actual,expected in [(rr['ordinary_profit'],10),(rr['distribution'],5),(cc['E'],105),(cc['F'],85),
  (cc['reserve'],1),(cc['parent_RE'],4),(cc['parent_C'],10)]:assert abs(actual-expected)<1e-8
 # Stress input must preserve debt and return null, never price a failed continuation.
 p=params(BASE,1);p.update(fund_cap=-.99,minimum_growth=0)
 failed,_=one_year(INITIAL,p,1)
 assert failed['PV'] is None and failed['TV'] is None and failed['distribution']==0 and failed['opening']['F']==F0
 # Whole production payment chain on deliberately high legal profit/high capital reserve:
 # stop dividend flag feeds cash/equity, rather than setting output D to zero after calculation.
 p=params(BASE,1);p['stop_dividends']=True
 no_declared=copy.deepcopy(INITIAL);no_declared['approved_distribution_unpaid']=0.
 row,cl=one_year(no_declared,p,1)
 assert row['distribution']==0 and abs(cl['E']-E0-row['ordinary_profit'])<1e-9
 # Same Y5 state, changed permanent tail credit must lower valuation, not only Y1 profit.
 b=simulate(BASE,end_year=5);y5=b['terminal_state']
 lo=copy.deepcopy(BASE);lo['credit_shift']=.003
 a=value_run(simulate(BASE,y5,6),BASE,5);c=value_run(simulate(lo,y5,6),lo,5)
 assert c['PV']<a['PV']
 return dict(loss_before_reserve=True,registered_cap_ceiling=True,production_economics_literal=True,production_full_payment_literal=True,
  failed_path_typed_null=True,production_stop_distribution=True,permanent_tail_sensitivity=True)

def build():
 tests=manual_tests();base=assess(BASE)
 # Core endpoints have identical five-year distributions AND identical full Y5 state.
 y5=base['annual_rows'][4]['closing'];core={}
 for name,r,ys,fs in [('low',.1025,-.0010,.0005),('high',.0925,.0010,-.0005)]:
  p=copy.deepcopy(BASE);p.update(discount=r,yield_shift=ys,funding_shift=fs)
  run=simulate(p,y5,6);v=value_run(run,p,5)
  d=[x['distribution_per_share'] for x in base['annual_rows'][:5]]
  pv=sum(x/(1+r)**(i+1) for i,x in enumerate(d))+v['PV']/(1+r)**5
  core[name]=dict(current_value=pv,year5_terminal=v['PV'],discount=r,terminal_pv_share=(v['PV']/(1+r)**5)/pv,
   y5_state=y5,tail_parameters=p,tail_rows=run['rows'],valuation=v)
 scenarios={'base':base}
 cyc=copy.deepcopy(BASE);cyc.update(growth=[.02,.02,.05,.06,.05],shock={'1':dict(credit=.018,funding=.025),'2':dict(credit=.015,funding=.023),'3':dict(credit=.011)})
 scenarios['cyclical_weak']=assess(cyc)
 structural=copy.deepcopy(BASE);structural.update(growth=[.02,.02,.02,.02,.02],tail_growth=.015,loan_yield=.054,tail_yield=.051,funding=.024,tail_funding=.024,credit=.014,tail_credit=.014,fees=.004,tail_fees=.004,opex=.0045,tail_opex=.0045,capital_ratio=.16,discount=.11)
 scenarios['structural_adverse']=assess(structural)
 bull=copy.deepcopy(BASE);bull.update(growth=[.11,.10,.09,.08,.06],loan_yield=.061,tail_yield=.058,credit=.0075,tail_credit=.008,fees=.0032,tail_fees=.003,discount=.0925)
 scenarios['optimistic']=assess(bull)
 tight=copy.deepcopy(BASE);tight.update(shock={'1':dict(fund_cap=-.05,funding=.03),'2':dict(fund_cap=0,funding=.026)},discount=.105)
 scenarios['funding_contraction']=assess(tight)
 delay=copy.deepcopy(BASE);delay['collection_delay']=1;scenarios['subsidiary_one_year_cash_delay']=assess(delay)
 defer=copy.deepcopy(BASE);defer['upstream_start']=11;scenarios['subsidiary_upstream_deferred_to_year11']=assess(defer)
 issuance=copy.deepcopy(BASE);issuance.update(shock={'1':dict(credit=.045,capital_ratio=.17,equity_budget=12.),'2':dict(credit=.02,capital_ratio=.17)},discount=.11)
 scenarios['conditional_equity_recapitalisation']=assess(issuance)
 failure=copy.deepcopy(BASE);failure['shock']={'1':dict(fund_cap=-.99,minimum_growth=0)};scenarios['funding_failure_no_recovery_value']=assess(failure)
 sensitivities={}
 for field,delta in [('credit_shift',.001),('funding_shift',.001),('yield_shift',-.001),('rwa_shift',.1)]:
  p=copy.deepcopy(BASE);p[field]+=delta;sensitivities[field]=assess(p)
 # Auxiliary steady ROE/PB capitalisation is a separate normalisation, not market PB.
 # Same ordinary book (already net of all funding debt/NCI), zero additional cash add-on.
 auxiliary={}
 for label,roe,r,g in [('low',.115,.1025,.03),('high',.125,.0925,.03)]:
  pb=(roe-g)/(r-g);auxiliary[label]=dict(roe=roe,discount=r,growth=g,payout=1-g/roe,justified_PB=pb,value=E0/SHARES*pb)
 return dict(company='CN:600901',period='2026-Q3',as_of=ASOF,units='CNY billion; billion shares; CNY/share',
  opening_state=INITIAL,opening_state_classification=dict(reported=['L','E','F','C','shares','registered','reserve'],last_H1_reported=['parent_C','risk_reserve','investment'],estimated_or_budget=['parent_E','parent_RE','sub_E','sub_RE','sub_reserve','sub_risk','sub_commitment'],approved_not_yet_paid=['approved_distribution_unpaid']),model_parameters=BASE,tests=tests,
  core=core,return_model=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=ASOF,
  base_case_distributions_per_share=[round(x['distribution_per_share'],6) for x in base['annual_rows'][:5]],
  base_case_terminal_equity_value_range_per_share=dict(year_5={k:round(core[k]['year5_terminal'],6) for k in ['low','high']})),
  value_range=dict(low=round(core['low']['current_value'],2),high=round(core['high']['current_value'],2),currency='CNY'),
  auxiliary_PB_ROE=auxiliary,scenarios=scenarios,sensitivities=sensitivities)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('2026-Q3-output.json'));ap.add_argument('--expand',action='store_true',help='already expanded plain stdlib source; accepted for portable interface')
 args=ap.parse_args();out=build();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 print(json.dumps(dict(value_range=out['value_range'],return_model=out['return_model'],tests=out['tests']),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
