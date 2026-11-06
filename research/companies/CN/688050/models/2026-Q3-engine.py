#!/usr/bin/env python3
"""CNY million, shares million. No network, dependency or production-state input.
Forecast years are rolling twelve-month periods after 2026-10-28.
Accounting lease basis: lease depreciation remains expense, maintenance includes
replacement right-of-use investment, and lease principal stays in debt bridge.
"""
import copy
import json
from pathlib import Path

ASOF='2026-10-28T00:06:00+00:00'
SHARES=193.437735
FACTS={
 'cash':570.57780016,'liquid_investments':48.14851849,
 'short_debt':113.65581756,'current_noncurrent_liabilities':191.56565807,
 'long_debt':836.44334849,'lease_debt':28.25775638,'other_long_payable':52.18226376,
 'deposit_maturity':42.97696372,'financial_principal':45.90555155+116.62929205,
 'common_book':2971.41136621,'minority_book':264.33971490,
 'parent_h1_cash':358.40323749,'parent_h1_retained':1319.13549610,
 'paid_dividend':61.85437920,
}
PRODUCTS=[['IOL',620,.85],['OK',255,.86],['soft_contacts',700,.35],['sports',410,.60],['other',215,.43]]
BASE={
 'nopat':(sum(r*m for _,r,m in PRODUCTS)-500-220-170-25)*.85,
 'g1':.06,'g2':.035,'g_terminal':.02,'roic':.14,'wacc':.10,'ke':.115,
 'cash_floor':300.,'cash_floor_growth':.02,'minority_value':280.,
 'minority_growth':.03,'financial_realization_year':8,'cash_release_years':5,'financial_recovery':.80,'interest_rate':.035,
 'parent_cash_adjustment':-50.,'parent_cfo':250.,'parent_profit':250.,
 'parent_growth':.04,'parent_capex':35.,'parent_support':80.,
 'parent_net_debt_repayment':60.,'parent_opening_debt_budget':810.27716245,'parent_min_cash':150.,
 'dividends':[60.,70.,80.,90.,100.], 'net_debt_repayments':[80.]*5,
 'nci_dividends':[6.,7.,8.,9.,10.], 'transient_working_capital':[40.,20.,0.,0.,0.],
 'project_fixed_budget':[60.,60.,54.594,0.,0.],
 'extra_maintenance':0.,'nopat_shocks':{},'parent_cfo_shocks':{},
 'cash_access_factor':1.,'notes':'核心：成熟眼科缓慢修复，制造增长快于渠道现金，德美有限增量。'}

def pv(flows,rate):
 return sum(v/(1+rate)**(i+1) for i,v in enumerate(flows))

def operating(p):
 rows=[];n=p['nopat'];floor=p['cash_floor']
 for year in range(1,12):
  if year>1:n*=1+(p['g1'] if year<=5 else p['g2'] if year<=10 else p['g_terminal'])
  next_g=p['g1'] if year<5 else p['g2'] if year<10 else p['g_terminal']
  # Investment at end of year funds NEXT year's incremental earnings.
  investment=n*next_g/p['roic']
  fixed=.70*investment;working=.30*investment
  project=p['project_fixed_budget'][year-1] if year<=5 else 0.
  project_extra=max(0.,project-fixed)
  floor_next=floor*(1+p['cash_floor_growth']);reserve_add=floor_next-floor
  temporary=p['transient_working_capital'][year-1] if year<=5 else 0.
  shock=p['nopat_shocks'].get(str(year),0.)
  economic_nopat=n+shock
  maintenance=160.*(1.03**(year-1))+p['extra_maintenance']
  depreciation=160.*(1.03**(year-1))
  fcf=economic_nopat+depreciation-maintenance-investment-project_extra-temporary-reserve_add
  rows.append({'year':year,'nopat':economic_nopat,'base_nopat':n,'depreciation':depreciation,
    'maintenance':maintenance,'growth_fixed':fixed,'growth_working':working,
    'project_budget':project,'project_extra':project_extra,'temporary_working':temporary,
    'reserve_add':reserve_add,'cash_floor':floor_next,'fcff':fcf})
  floor=floor_next
 return rows

def value(p):
 rows=operating(p);w=p['wacc'];ke=p['ke'];g=p['g_terminal']
 assert w>g and ke>g and len(rows)==11
 terminal10=rows[10]['fcff']/(w-g)
 ev=pv([r['fcff'] for r in rows[:10]],w)+terminal10/(1+w)**10
 debt=sum(FACTS[k] for k in ['short_debt','current_noncurrent_liabilities','long_debt','lease_debt'])
 cash=FACTS['cash']+FACTS['liquid_investments'];other=FACTS['other_long_payable']
 financial_receipt=FACTS['financial_principal']*p['financial_recovery']/(1+ke)**(p['financial_realization_year']-5)
 cash_release_factor=sum(1/(1+ke)**j for j in range(1,p['cash_release_years']+1))/p['cash_release_years']
 # Operating cash excludes income on risk financial assets. Cash realization is
 # in year 8 by default; financial_receipt is its discounted economic value at year 5.
 opening_parent_excess=max(0.,FACTS['parent_h1_cash']+p['parent_cash_adjustment']-p['parent_min_cash'])
 opening_nonparent_excess=max(0.,cash-p['cash_floor']-opening_parent_excess)
 direct=(ev+opening_parent_excess+opening_nonparent_excess*cash_release_factor+FACTS['deposit_maturity']/(1+ke)+financial_receipt/(1+ke)**5-debt-other-p['minority_value'])/SHARES
 parent_cash=FACTS['parent_h1_cash']+p['parent_cash_adjustment']
 parent_reserve=96.70158750
 parent_legal=FACTS['parent_h1_retained'];parent_debt=p['parent_opening_debt_budget'];holders=[];funds=[]
 other_schedule=[12.,12.,12.,10.,FACTS['other_long_payable']-46.]
 for i,r in enumerate(rows[:5]):
  interest=debt*p['interest_rate']*.85
  repay=min(debt,p['net_debt_repayments'][i]);otherpay=other_schedule[i]
  # FCFF excludes reserve increments: add them back to actual cash pool.
  deposit_receipt=FACTS['deposit_maturity'] if i==0 else 0.
  cash_pre=cash+deposit_receipt+r['fcff']+r['reserve_add']-interest-repay-otherpay-p['nci_dividends'][i]
  pcfo=p['parent_cfo']*(1+p['parent_growth'])**i+p['parent_cfo_shocks'].get(str(i+1),0.)
  parent_interest=parent_debt*p['interest_rate']
  parent_pre=parent_cash+deposit_receipt+pcfo-parent_interest-p['parent_capex']*(1.03**i)-p['parent_support']-p['parent_net_debt_repayment']
  pp=p['parent_profit']*(1+p['parent_growth'])**i+min(0.,p['parent_cfo_shocks'].get(str(i+1),0.))
  # Parent has positive retained profits. First offset any prior loss; only
  # remaining current profit can fund the statutory reserve, capped at 50% capital.
  prior_loss=max(0.,-parent_legal)
  distributable_profit=max(0.,pp-prior_loss)
  reserve=min(distributable_profit*.10,max(0.,SHARES*.50-parent_reserve))
  parent_reserve+=reserve
  parent_legal+=pp-reserve
  capacity=max(0.,min(cash_pre-r['cash_floor'],parent_pre-p['parent_min_cash'],parent_legal))
  dividend=min(p['dividends'][i],capacity)
  cash=cash_pre-dividend;parent_cash=parent_pre-dividend;parent_legal-=dividend
  parent_debt-=p['parent_net_debt_repayment']
  debt-=repay;other-=otherpay;holders.append(dividend/SHARES)
  feasible=cash>=r['cash_floor']-1e-8 and parent_cash>=p['parent_min_cash']-1e-8 and parent_legal>=0
  funds.append({'year':i+1,'interest_after_tax':interest,'net_principal_repayment':repay,'other_payable_repayment':otherpay,
   'deposit_receipt':deposit_receipt,'minority_dividend':p['nci_dividends'][i],'common_dividend':dividend,'planned_common_dividend':p['dividends'][i],
   'group_cash':cash,'cash_floor':r['cash_floor'],'debt':debt,'other_payable':other,
   'parent_cash_budget':parent_cash,'parent_cfo_budget':pcfo,'parent_legal_profit_budget':pp,
   'parent_cash_interest_budget':parent_interest,'parent_debt_budget':parent_debt,'parent_statutory_reserve':reserve,'parent_statutory_reserve_balance':parent_reserve,'parent_legal_retained_budget':parent_legal,'feasible':feasible})
  assert abs(cash-(cash_pre-dividend))<1e-8
 ev5=pv([r['fcff'] for r in rows[5:10]],w)+terminal10/(1+w)**5
 minority5=p['minority_value']*(1+p['minority_growth'])**5
 excess=cash-rows[4]['cash_floor']
 parent_excess5=min(excess,max(0.,parent_cash-p['parent_min_cash']))
 nonparent_excess5=max(0.,excess-parent_excess5)
 cash_value5=(parent_excess5+nonparent_excess5*cash_release_factor)*p['cash_access_factor']
 tv5=(ev5+cash_value5+financial_receipt-debt-other-minority5)/SHARES
 primary=pv(holders,ke)+tv5/(1+ke)**5
 return {'parameters':p,'operating_rows':rows,'funding_rows':funds,'distributions_per_share':holders,
  'terminal_equity_per_share_year5':tv5,'primary_holder_dcf_per_share':primary,'auxiliary_fcff_per_share':direct,
  'initial_operating_value':ev,'year5_operating_value':ev5,'year5_excess_cash':excess,'year5_cash_economic_value':cash_value5,'year5_parent_excess':parent_excess5,'year5_nonparent_excess':nonparent_excess5,'cash_release_factor':cash_release_factor,'year5_financial_asset_value':financial_receipt,
  'year5_minority_value':minority5,'year10_terminal_pv_share_of_ev':terminal10/(1+w)**10/ev,
  'terminal5_pv_share_of_primary':tv5/(1+ke)**5/primary,'feasible':all(x['feasible'] for x in funds)}

def changed(**kwargs):
 p=copy.deepcopy(BASE);p.update(kwargs);return p

def self_test():
 # Real production discount function is exercised by a literal annuity and
 # zero-growth perpetuity; neither expected result reads production rows.
 assert abs(pv([10.,10.],.10)-(10/1.1+10/1.21))<1e-12
 p=changed(nopat=100.,g1=0.,g2=0.,g_terminal=0.,cash_floor=0.,cash_floor_growth=0.,
   transient_working_capital=[0.]*5,project_fixed_budget=[0.]*5,extra_maintenance=0.)
 r=value(p)
 assert abs(r['initial_operating_value']-1000.)<1e-9
 assert abs(r['year5_operating_value']-1000.)<1e-9
 b=value(copy.deepcopy(BASE));q=value(changed(dividends=[0.]*5))
 assert abs(q['year5_excess_cash']-b['year5_excess_cash']-sum(BASE['dividends']))<1e-8
 assert q['terminal_equity_per_share_year5']>b['terminal_equity_per_share_year5']
 assert abs(b['funding_rows'][0]['parent_statutory_reserve']-.01728)<1e-10
 assert b['funding_rows'][1]['parent_statutory_reserve']==0
 return {'production_pv_annuity':'pass','production_zero_growth_1000':'pass','dividend_terminal_cash_conservation':'pass'}

def main():
 cases={
  'base':BASE,
  'core_low':changed(nopat=BASE['nopat']-15,roic=.13,wacc=.105,ke=.12,minority_value=300.,financial_recovery=.75),
  'core_high':changed(nopat=BASE['nopat']+15,roic=.15,wacc=.095,ke=.11,minority_value=260.,financial_recovery=.85),
  'cyclical_delay':changed(nopat_shocks={'1':-50.,'2':-35.},parent_cfo_shocks={'1':-40.,'2':-25.},notes='前两年采购/收款延迟，第三年恢复；已承诺资本不削减。'),
  'structural_failure':changed(nopat=BASE['nopat']*.75,g1=.03,g2=.02,roic=.09,minority_value=220.,nci_dividends=[3.]*5,parent_cfo=185.,parent_profit=190.,parent_support=95.,parent_net_debt_repayment=40.,net_debt_repayments=[60.]*5,interest_rate=.045,dividends=[40.,40.,45.,50.,55.],notes='IOL永久失价及零售亏损，弱现金和低资本回报；降分红并减少净偿债至集团60/母公司40，续作利率升至4.5%，不新增股本。'),
  'successful_scale':changed(nopat=BASE['nopat']*1.15,g1=.08,roic=.18,minority_value=340.,nci_dividends=[8.,10.,12.,14.,16.],parent_cfo=280.,parent_profit=280.,notes='高端复购、工厂良率和获客效率同时改善；并非核心上端。'),
  'roic_10pct':changed(roic=.10),
  'extra_maintenance_25':changed(extra_maintenance=25.),
  'parent_cash_minus100':changed(parent_cash_adjustment=-150.),
  'parent_transfer_stress':changed(parent_support=145.,cash_access_factor=.85,notes='每年额外内部支持65；不重复扣集团费用，母公司现金制约派息，尾期超额现金85%可实现。'),
  'financial_zero':changed(financial_recovery=0.),
  'financial_year12':changed(financial_realization_year=12),
  'subsidiary_release10years':changed(cash_release_years=10),
  'minority_plus100':changed(minority_value=380.),
  'wacc_plus1pt':changed(wacc=.11),
  'ke_plus1pt':changed(ke=.125),
  'growth_3pct':changed(g1=.03),
  'growth_8pct':changed(g1=.08),
 }
 output={'as_of':ASOF,'units':'CNY million except per share','shares_million':SHARES,'facts':FACTS,'products':PRODUCTS,
  'self_tests':self_test(),'scenarios':{k:value(copy.deepcopy(v)) for k,v in cases.items()}}
 Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
