#!/usr/bin/env python3
"""宁波银行；金额百万元、股份百万股。纯stdlib、自足。预算不构成法律认证。"""
import json, math, sys
SHARES=6603.590792
CUT='2026-10-29T11:15:00+00:00'
def init():
 return dict(B=245136.,PB=222355.,M=1462.,RE=113170.,SR=19496.,GR=32171.,loan=1970690.,allow=56181.,fvallow=1159.,accrued=5333.,sec=1407161.,trading=367459.,liquid=339284.,other=62449.,deposit=2296217.,otherL=60863.,wholesale=1452851.,rwa=2532657.,prwa=2304409.,deduct=2959.,pdeduct=17277.,AT1=40825.,T2=84345.,pt2=81750.,cash=189505.,pcash=183529.,SRE=18000.,asset=4097354.,passets=3807189.,pwholesale=1209253.,priority_payable=0.)
def params(name):
 d=dict(k=.105,loan_yield=.0378,sec_yield=.023,trade_yield=.029,deposit_cost=.0125,wholesale_cost=.0175,cost=.305,fee_rate=.002,credit=.006,allow_ratio=.0285,roe=.132,roe_tail=.105,tail_growth=.03,early_growth=.10,parent_share=.83,sub_payout=.30,parent_cet=.09,group_cet=.095,tier1=.10,total=.13,legal_haircut=1.,refinance=True,wholesale_cap=.50)
 if name=='core_low': d.update(k=.11,loan_yield=.0373,cost=.315,credit=.0064,roe_tail=.10)
 if name=='core_high': d.update(k=.10,loan_yield=.0383,cost=.295,credit=.0056,roe_tail=.11)
 if name=='cycle': d.update(cycle=True)
 if name=='structural': d.update(loan_yield=.0343,deposit_cost=.014,wholesale_cost=.021,cost=.34,credit=.009,allow_ratio=.033,early_growth=.04,tail_growth=.02,structural_decline=True,roe=.09,roe_tail=.08)
 if name=='optimistic': d.update(loan_yield=.0393,cost=.29,credit=.005,early_growth=.11,roe=.14,roe_tail=.115)
 if name=='credit_plus_50bp': d['credit']+=.005
 if name=='parent_buffer_plus_100bp': d['parent_cet']+=.01
 if name=='sub_no_remit': d['sub_payout']=0.
 if name=='legal_pool_half': d['legal_haircut']=.5
 if name=='no_at1_refinance': d['refinance']=False
 if name=='wholesale_failure':d['wholesale_cap']=.25
 return d
def capital_need(rwa,p,at1,t2,group=True):
 return max(rwa*(p['group_cet'] if group else p['parent_cet']),rwa*p['tier1']-at1,rwa*p['total']-at1-t2)
def legal_budget(re,profit,sr,gr,required_gr,dt=1.):
 # Prior deficits are covered before any reserve appropriation; voluntary 10% continues as historical policy.
 eligible=max(0.,profit+min(re,0.))
 statutory=.10*eligible
 general=min(max(0.,required_gr-gr),max(0.,re+profit-statutory))
 return max(0.,re+profit-statutory-general),statutory,general

def step(s,p,year,method='balance',dt=1.,growth=None,stub=False):
 g=p['early_growth']-(p['early_growth']-.06)*min(max(year-1,0),4)/4 if year<=5 else .06-(.06-p['tail_growth'])*min(year-5,10)/10
 if p.get('structural_decline'):g=.04-.02*min(max(year-1,0),14)/14
 if growth is not None:g=growth
 factor=(1+g)**dt
 a=s.copy()
 for z in ['loan','fvallow','accrued','sec','trading','liquid','other','deposit','otherL','rwa','prwa','deduct','passets']:
  a[z]=s[z]*factor
 # RWA intensity initially improves more slowly than 9M2026, converging to fixed intensity in Y10.
 rf=(1+g*(.8+.2*min(max(year-1,0),9)/9))**dt
 a['rwa']=s['rwa']*rf; a['prwa']=s['prwa']*rf
 a['pdeduct']=15068.+(s['pdeduct']-15068.)*factor
 a['allow']=p['allow_ratio']*a['loan']
 # Transition allowance changes over a stub must be proportional, not an instantaneous annual reset.
 if stub:a['allow']=s['allow']+(p['allow_ratio']*a['loan']-s['allow'])*dt
 avgloan=(s['loan']+a['loan'])/2
 writeoff=avgloan*(p['credit']+.0013)*dt
 recovery=avgloan*.0013*dt
 if p.get('cycle') and year in [1,2]:writeoff+=avgloan*.003*dt
 provision=a['allow']-s['allow']+writeoff-recovery
 asset=a['loan']-a['allow']+a['fvallow']+a['accrued']+a['sec']+a['trading']+a['liquid']+a['other']
 a['asset']=asset
 avg=lambda z:(a[z]+s[z])/2
 # Existing priority capital is excluded from B. Calls are options, conditional on capital and replacement.
 coupon=(10000*(.0345 if year<2 else .033)+10000*(.023 if year<4 else .033)+16000*(.0197 if year<5 else .033)+4850*.0325)*dt
 economic_coupon=coupon
 # Equity-classified tools: only declared distributions reduce accounting ordinary equity.
 # Oct29 known preference declaration is unpaid until Nov16; later same-season declarations are budgets.
 closing_payable=157.625
 cash_coupon=0. if stub else coupon
 coupon=cash_coupon+closing_payable-s.get('priority_payable',0.)
 if 'coupon_override' in p:
  economic_coupon=coupon=cash_coupon=p['coupon_override'];closing_payable=s.get('priority_payable',0.)
 a['priority_payable']=closing_payable
 payable_change=closing_payable-s.get('priority_payable',0.)
 redeem=0.; issue=0.
 if not stub and year in [2,4,5]:
  scheduled={2:10000.,4:10000.,5:16000.}[year]
  if p['refinance']:redeem=scheduled;issue=scheduled
 # No replacement means no optional call, not fictional debt forgiveness.
 nw=s['wholesale']; div=0.; upstream=0.
 for iteration in range(100):
  credit=provision
  nii=(avgloan*p['loan_yield']+avg('sec')*p['sec_yield']+avg('liquid')*.013-avg('deposit')*p['deposit_cost']-(s['wholesale']+nw)/2*p['wholesale_cost'])*dt
  fee=(s['asset']+asset)/2*p['fee_rate']*dt
  trading=avg('trading')*p['trade_yield']*dt
  revenue=nii+fee+trading
  costs=revenue*p['cost']
  nonloan_provision=avg('sec')*.00025*dt
  pretax=revenue-costs-credit-nonloan_provision-revenue*.009
  tax=max(0.,pretax)*(.12+.03*min(max(year-1,0),14)/14)
  ni=pretax-tax
  if method=='roe':
   roe=p['roe']+(p['roe_tail']-p['roe'])*min(max(year-1,0),14)/14
   ni=(s['B']*roe*dt+economic_coupon)/.9904
   # This is an independent sustainable-return budget, not earnings copied from spread model.
   tax=max(0.,ni)*.15/.85; pretax=ni+tax
  minority=ni*.0096
  common_profit=ni-minority-coupon
  sub_attr=ni*(1-p['parent_share']-.0096)
  subbook=s['B']-s['PB']+15068.
  subrisk=max(0.,a['rwa']-a['prwa'])
  sub_legal=max(0.,s['SRE']+sub_attr-max(sub_attr,0.)*.20)
  sub_surplus=max(0.,subbook+sub_attr-subrisk*.12)
  sub_desire=max(sub_attr,0.)*p['sub_payout']+sub_surplus*(.1+.15*min(max(year-1,0),14)/14) if p['sub_payout'] else 0.
  upstream=min(sub_desire,sub_surplus,sub_legal)
  pprofit=ni*p['parent_share']+upstream
  plimit,sradd,gradd=legal_budget(s['RE'],pprofit,s['SR'],s['GR'],32171.*a['prwa']/2304409.)
  p_pre=s['PB']+pprofit-coupon
  b_pre=s['B']+common_profit
  gcap=capital_need(a['rwa'],p,a['AT1'],a['T2'])+a['deduct']
  pcap=capital_need(a['prwa'],p,a['AT1'],a['pt2'],False)+a['pdeduct']
  surplus=min(b_pre-gcap,p_pre-pcap)
  # Smooth cash-return policy, used from Y1 throughout; no magic Y5 release.
  desire=max(0.,common_profit)*.30+max(0.,surplus)*(.1+.15*min(max(year-1,0),14)/14)
  # Declared 0.4 is INCLUDED in Y1 ordinary distribution, not added a second time.
  if year==1 and not stub:desire=max(desire,.4*SHARES)
  div=0. if stub else max(0.,min(desire,surplus,plimit*p['legal_haircut']-coupon))
  b=b_pre-div; pb=p_pre-div; m=s['M']+minority-minority*.30
  nw2=asset-b-a['AT1']-m-a['deposit']-a['otherL']-a['priority_payable']
  if abs(nw2-nw)<1e-7*max(1.,abs(nw)):nw=nw2;break
  nw=nw2
 a.update(B=b,PB=pb,M=m,RE=s['RE']+pprofit-sradd-gradd-coupon-div,SR=s['SR']+sradd,GR=s['GR']+gradd,SRE=s['SRE']+sub_attr-max(sub_attr,0.)*.20-upstream,wholesale=nw)
 # Parent cash is a separately budgeted payout resource, not assumed equal to consolidated cash.
 a['cash']=s['cash']*factor;a['pcash']=s['pcash']*factor
 a['passets']=3807189.*asset/4097354.
 a['pwholesale']=a['passets']-pb-a['AT1']-a['deposit']-53.*a['asset']/4097354.-a['otherL']*(38486./60863.)-a['priority_payable']
 group_cet=(b-a['deduct'])/a['rwa']; parent_cet=(pb-a['pdeduct'])/a['prwa']
 capital_ok=(b>=gcap-1e-5 and pb>=pcap-1e-5 and (stub or year!=1 or div>=.4*SHARES-1e-5))
 funding_ok=nw>=0 and a['pwholesale']>=0 and nw/asset<p['wholesale_cap']
 # Cash identities use total noncash asset investment, not industrial CFO-capex.
 # Credit provision is noncash, while writeoff/recovery is already in net carrying-value change.
 noncash_asset_change=(asset-a['cash'])-(s['asset']-s['cash'])
 dliab=(a['deposit']-s['deposit'])+(nw-s['wholesale'])+(a['otherL']-s['otherL'])
 cash_change=ni+dliab-noncash_asset_change-cash_coupon-div-minority*.30
 parent_non_cash_change=(a['passets']-a['pcash'])-(s['passets']-s['pcash'])
 # Parent liabilities are disaggregated via an opening residual, so both cash and B reconcile.
 old_parent_L=s['passets']-s['PB']-s['AT1']; new_parent_L=a['passets']-pb-a['AT1']
 parent_cash_change=pprofit+(new_parent_L-old_parent_L-payable_change)-parent_non_cash_change-cash_coupon-div
 cash_err=cash_change-(a['cash']-s['cash'])
 pcash_err=parent_cash_change-(a['pcash']-s['pcash'])
 return a,dict(year=year,dt=dt,growth=g,method=method,opening=s,closing=a,nii=nii,fee=fee,trading_income=trading,revenue=revenue,costs=costs,loan_provision=credit,nonloan_provision=nonloan_provision,loan_writeoff=writeoff,loan_recovery=recovery,pretax=pretax,sustainable_earnings_adjustment=pretax-(revenue-costs-credit-nonloan_provision-revenue*.009),tax=tax,net_income=ni,minority_profit=minority,minority_distribution=minority*.30,priority_coupon=coupon,priority_cash_paid=cash_coupon,priority_economic_accrual=economic_coupon,priority_payable_change=payable_change,economic_common_profit=ni-minority-economic_coupon,priority_redemption=redeem,priority_replacement=issue,sub_attributable_profit=sub_attr,sub_remittance=upstream,parent_profit=pprofit,statutory_transfer=sradd,general_reserve_transfer=gradd,parent_legal_available=plimit,common_profit=common_profit,dividend=div,dividend_per_share=div/SHARES,group_required_B=gcap,parent_required_B=pcap,group_cet1=group_cet,parent_cet1=parent_cet,group_tier1=(b-a['deduct']+a['AT1'])/a['rwa'],group_total=(b-a['deduct']+a['AT1']+a['T2'])/a['rwa'],parent_tier1=(pb-a['pdeduct']+a['AT1'])/a['prwa'],parent_total=(pb-a['pdeduct']+a['AT1']+a['pt2'])/a['prwa'],capital_ok=capital_ok,funding_ok=funding_ok,cash_change=cash_change,parent_cash_change=parent_cash_change,cash_error=cash_err,parent_cash_error=pcash_err,net_new_funding=nw-s['wholesale'],loan_face_addition=a['loan']-s['loan']+writeoff-recovery,common_equity_error=b-s['B']-common_profit+div,parent_equity_error=pb-s['PB']-pprofit+coupon+div)

def run(name='base',method='balance',years=300,start=None,startyear=1,stub=True):
 p=params(name);s=init() if start is None else dict(start);rows=[]
 stubrow=None
 if stub:
  s,stubrow=step(s,p,1,method,dt=29/365,stub=True)
 b0=s['B'];pv=0.;ri=b0; discount=1.
 for year in range(startyear,startyear+years):
  a,row=step(s,p,year,method)
  if not row['capital_ok'] or not row['funding_ok']:
   # Shrink growth until feasible; if even zero growth fails, no fictitious negative-cash continuation.
   low=-.05; high=row['growth'];best=None
   aa,rr=step(s,p,year,method,growth=low)
   if rr['capital_ok'] and rr['funding_ok']:best=(aa,rr)
   if best is None:return dict(name=name,method=method,status='infeasible',failure_year=year,failed_state=row,years=rows,stub=stubrow)
   for _ in range(48):
    mid=(low+high)/2;aa,rr=step(s,p,year,method,growth=mid)
    if rr['capital_ok'] and rr['funding_ok']:low=mid;best=(aa,rr)
    else:high=mid
   a,row=best;row['growth_adjusted']=True
  discount*=1+p['k'];row['discount']=discount;row['pv_dividend']=row['dividend']/discount
  pv+=row['pv_dividend'];ri+=(row['common_profit']-p['k']*s['B'])/discount
  # all annual accounting and ownership tests, scale-aware
  for key in ['cash_error','parent_cash_error','common_equity_error','parent_equity_error']:
   assert abs(row[key])<1e-7*max(1,a['asset']),(name,year,key,row[key])
  assert a['RE']>=-1e-4 and a['cash']>=0 and a['pcash']>=0
  rows.append(row);s=a
 # No perpetuity plug. 300/500-year explicit tails and discounted remaining book compare convergence.
 residual=s['B']/discount
 timing=.4*((1+p['k'])**(-7/365)-1/(1+p['k'])) if stub else 0.
 pv+=timing*SHARES;ri+=timing*SHARES
 return dict(name=name,method=method,status='feasible',parameters=p,initial_common_B=b0,known_dividend_timing_correction_per_share=timing,stub=stubrow,years=rows,value_per_share=pv/SHARES,ri_per_share=(ri-residual)/SHARES,discounted_remaining_book_per_share=residual/SHARES,terminal5_from_same_state_per_share=sum(r['pv_dividend'] for r in rows[5:])*(1+p['k'])**5/SHARES,terminal_pv_share=sum(r['pv_dividend'] for r in rows[5:])/pv,distributions=[r['dividend_per_share'] for r in rows[:5]])

def priority_bridge():
 return dict(unit='CNY million',accounting='equity-classified distributions recognized on declaration; economic accrual is memorandum only, not duplicate expense',opening_20260930_declared_unpaid=0.,stub_cash=0.,stub_declared=157.625,closing_20261029_declared_unpaid=157.625,annual_future_preference_declaration='157.625 at each model year end is a continuation policy budget, not known approval',ordinary_known_cash=dict(date='2026-11-05',amount=.4*SHARES,included_in_year1=True,opening_equity_deduction=False),instruments=[dict(name='2023 perpetual',principal=10000.,annual_cash=345.,opening_state='2026 July coupon already paid and in Q3 equity',stub_cash=0.,year1_payment_budget_date='2027-07-11',year1_cash=345.),dict(name='2025 perpetual',principal=10000.,annual_cash=230.,opening_state='2026 September coupon already paid and in Q3 equity',stub_cash=0.,year1_payment_budget_date='2027-09-16',year1_cash=230.),dict(name='2026 perpetual',principal=16000.,annual_cash=315.2,opening_state='May2026 issued; no first annual coupon paid by Q3',stub_cash=0.,year1_payment_budget_date='2027-05-28',year1_cash=315.2),dict(name='preference',principal=4850.,annual_cash=157.625,opening_state='2026 distribution not declared in Sep30 equity; Oct29 board declaration',stub_cash=0.,stub_declared=157.625,year1_payment_known_date='2026-11-16',year1_cash=157.625)])

def main():
 names=['base','core_low','core_high','cycle','structural','optimistic','credit_plus_50bp','parent_buffer_plus_100bp','sub_no_remit','legal_pool_half','no_at1_refinance','wholesale_failure']
 out={n:run(n) for n in names}
 out['auxiliary_roe']=run('base','roe')
 # Extend actual same states with continuing operations, not a terminal multiplier.
 out['tail500']=run('base',years=500)
 base=out['base']
 out['holder_terminal_low']=run('core_low',start=base['years'][4]['closing'],startyear=6,years=300,stub=False)
 out['holder_terminal_high']=run('core_high',start=base['years'][4]['closing'],startyear=6,years=300,stub=False)
 print(json.dumps({'as_of':CUT,'units':'CNY million / shares million','shares':SHARES,'priority_distribution_bridge':priority_bridge(),'models':out},sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
