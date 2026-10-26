#!/usr/bin/env python3
"""CN:300595 / 2026-Q3. Standard-library, offline, deterministic; units CNY million.
Run: python 2026-Q3.py > 2026-Q3-output.json ; --expand is identical (plain JSON).
P is the actual listed PRC parent. S is an ECONOMIC common-interest budget,
NOT a legal entity or invented distributable reserve. R is the group restricted project cash budget, allocated to the parent-side
cash ledger only as a proxy: actual funds span parent/subsidiaries, legal location unverified. S remittance eligibility is a
transparent budget/haircut; no registration-capital-derived legal reserves.
"""
import json, math, sys, copy
SYMBOL='CN:300595'; PERIOD='2026-Q3'; ASOF='2026-10-26T21:00:00+00:00'
ISSUED=894.356608
POTENTIAL_SECOND_CLASS=1.385586 # 461862 remaining per tranche x 3, Apr-2026 notice
SHARES=ISSUED+POTENTIAL_SECOND_CLASS # conservative fully diluted upper bound, no unreceived subscription cash
FACTS={
 'cash':831.96104511,'trading_assets':1680.51305281,'other_current':916.29733608,
 'other_noncurrent':51.40426529,'other_current_nonfinancial_estimate':12.0,
 'noncurrent_prepayment_proxy_H1':24.23941753,'minority_financial_interest_budget':150.,
 'paid_october_dividend':46.50654362,'restricted_H1':766.8342,
 'parent_H1_financial_assets':244.07945732+807.48164893+992.99926744+50.19014629,
 'parent_H1_retained_profit':2480.10123130,'parent_H1_statutory_reserve':434.18777772,
 'parent_loan_to_ou_investment':886.30543753,'parent_dividend_receivable_H1':9.24,
 'bank_and_trading_financial_liabilities':13.01266653+10.005833+55.69651865,
 'legacy_acquisition_payable_budget':106.36733768,
 'remaining_community_project_budget':842.7389-173.4065,
 'new_deal_total':120.,'new_deal_common_ownership':.8,
 'associates_and_equity_book':460.50608511+63.91101746,
 'common_associate_book_budget':472.,'goodwill':875.07627271,'first_class_refund_obligation':22.89917864,'first_class_restricted_shares':1.693727,
 'consolidated_parent_equity':5198.75527324,'minority_equity':420.92408775,
 'lease_current_and_long':62.34914325+110.14484326,
}
BASE={
 'discount':.095,'g_terminal':.005,'finance_yield_aftertax':.017,
 'revenue0':[660.,230.,370.,470.,65.],
 'growth_1':[-.06,0.,.02,.07,0.], 'growth_2_5':[.01,.015,.04,.06,0.],
 'growth_6_10':[0.,.005,.025,.03,0.], 'growth_11_20':[-.01,0.,.015,.015,-.01],
 'gross_margin':[.875,.64,.53,.70,.20], 'opex_ratio':.39,'recurring_credit_cost':.008,
 'tax':.16,'parent_profit_share':.78,'subs_minority_profit_share':.40,
 'depreciation_ratio':.028,'maintenance_capex_ratio':.034,'working_capital_ratio':.12,
 'project_roi':.08,'project_net_margin':.15,'project_depreciation_ratio':.03,'project_maintenance_ratio':.04,'project_wc_ratio':.12,'project_cancellation_ratio':.20,'project_spend':[220.,220.,229.3324],
 'new_deal_profit':[12.,13.,14.,15.,15.],'new_deal_payments':[72.,12.,12.,12.,12.],
 'parent_min_cash':200.,'subs_min_cash':120.,
 'remittance_ratio':.8,'remittance_start':1,'loan_repay_start':1,
 'loan_repay_annual_first5':50.,'loan_repay_annual_later':100.,
 'parent_dividend_ratio_first5':.35,'surplus_release_start':6,'surplus_release_end':10,
 'surplus_release_annual':500.,'project_release_year':4,'subs_capital_realization_year':10,'subs_capital_realization_cap':600.,'realization_friction':.05,
 'asset_sale_year':8,'asset_sale_net':400.,'asset_sale_book':472.,
 'minority_financial_interest_budget':150.,'parent_cash_shift':0.,
 'profit_shock_year':99,'profit_shock_multiplier':1.,'extra_exit_cost':0.,
 'closure_year':None,'cash_freeze_year':None,'cash_freeze_amount':0.,
 'refund_years':3,'refund_fraction':1.,'description':'Base: hard-lens pricing pressure persists; mature business stabilizes; modest service recovery; project ROI 8%.'}

def budget_payment(cash, retained, profit, cash_in, mandatory, floor, desired,
                   reserve_gap=0., allocation=.1, principal_cap=0., principal_desired=0.):
 """Production settlement. Losses reduce accumulated profits before any payout.
 Mandatory deficits are explicit unpaid claims, never silently zeroed away.
 Principal return has its own capacity and does NOT consume profit reserves.
 """
 before=cash+cash_in-mandatory
 unpaid=max(0.,-before)
 available=max(0.,before-floor)
 reserve_add=min(max(0.,profit+min(0.,retained))*allocation,max(0.,reserve_gap))
 balance=retained+profit-reserve_add
 ordinary=min(max(0.,desired),max(0.,balance),available)
 principal=min(max(0.,principal_desired),max(0.,principal_cap),max(0.,available-ordinary))
 return dict(cash=before-ordinary-principal,retained=balance-ordinary,
             reserve_add=reserve_add,ordinary=ordinary,principal=principal,
             unpaid=unpaid,feasible=unpaid<1e-8)

def inputs_for(name):
 c=copy.deepcopy(BASE);c['name']=name
 if name=='parent_profit_share_50':c.update(parent_profit_share=.5)
 if name=='closure_year1':c.update(closure_year=1,extra_exit_cost=200.)
 if name=='closure_year1_full_project_settlement':c.update(closure_year=1,extra_exit_cost=200.,project_cancellation_ratio=1.)
 if name=='closure_year1_failed':c.update(closure_year=1,extra_exit_cost=10000.)
 if name=='closure_year4_failed':c.update(closure_year=4,extra_exit_cost=10000.)
 if name=='project_roi_zero':c.update(project_roi=0.)
 if name=='project_roi_4pct':c.update(project_roi=.04)
 if name=='subs_minority_20':c.update(subs_minority_profit_share=.20)
 if name=='subs_minority_60':c.update(subs_minority_profit_share=.60)
 if name=='maintenance_plus1pct':c.update(maintenance_capex_ratio=.044)
 if name=='zero_subs_remittance':c.update(remittance_ratio=0.)
 if name=='incentives_success':c.update(refund_fraction=0.,description='Capital-action diagnostic only: first-class shares remain, no refund; fully diluted second-class denominator still charged with zero assumed cash subscription.')
 if name=='core_low':c.update(discount=.105,g_terminal=0.,profit_shock_year=6,profit_shock_multiplier=.97)
 elif name=='core_high':c.update(discount=.09,g_terminal=.01,profit_shock_year=6,profit_shock_multiplier=1.03)
 elif name=='cyclical':c.update(growth_1=[-.16,-.08,-.04,-.03,-.1],growth_2_5=[.04,.04,.055,.08,.02],profit_shock_year=1,profit_shock_multiplier=.85,description='2027 demand slump; recovery 2028-2031, no permanent margin repair assumed beyond base.')
 elif name=='structural':c.update(growth_1=[-.15,-.05,0.,.03,-.1],growth_2_5=[-.08,-.03,.01,.025,-.03],growth_6_10=[-.05,-.02,.01,.01,-.02],growth_11_20=[-.03,-.01,0.,0.,-.02],gross_margin=[.80,.60,.49,.66,.18],opex_ratio=.39,project_roi=.035,g_terminal=-.01,remittance_ratio=.5,description='2027 onward persistent substitution, hard-lens price/volume erosion, weaker clinic returns; no automatic reversion.')
 elif name=='optimistic':c.update(growth_1=[0.,.04,.05,.09,.01],growth_2_5=[.05,.04,.06,.09,.01],gross_margin=[.89,.66,.57,.72,.22],project_roi=.12,g_terminal=.015,description='DK185 and specialty lenses stabilize volumes, clinic utilization improves; new-project after-tax equity return 12%.')
 elif name=='late_remittance':c.update(remittance_start=6,loan_repay_start=6,parent_cash_shift=-300.,description='2027-2031 subsidiaries cannot upstream cash; 300m less parent opening cash, unchanged total common cash.')
 elif name=='project_return_4pct_from_2029':c.update(project_roi=.04,project_roi_effective_year=3,description='Project ROI resets to 4% from 2029; budgets still paid, no free cancellation.')
 elif name=='release_delayed_to_2036':c.update(surplus_release_start=10,surplus_release_end=14,asset_sale_year=12,subs_capital_realization_year=14,description='Idle cash and associate monetization delayed four years; financial earnings retained explicitly.')
 elif name=='margin_loss_from_2032':c.update(profit_shock_year=6,profit_shock_multiplier=.75,description='Permanent 25% operating-profit loss starts 2032; first five years unchanged.')
 elif name=='minority_cash_250':c.update(minority_financial_interest_budget=250.,description='Opening financial assets owed to minorities rise 100m; no extra haircut to already common profit.')
 elif name=='financial_freeze_2028':c.update(cash_freeze_year=2,cash_freeze_amount=900.,description='900m parent money unavailable in 2028, returned without gain in 2029; payout must resize.')
 elif name=='closure_stress':c.update(closure_year=4,extra_exit_cost=200.,description='Counterfactual 2030 closure: realize assets, pay full debt/acquisition/rent/employee/tax costs; preserve unpaid claims if any.')
 return c

def liquidation_recovery(sales, opening_sales, common_factor, project_revenue, c):
 """Q3 gross-to-net recovery budget, not continuing-business value addition.
 Ordinary liabilities paid in full (incl. deposits/contract fulfillment); debt,
 old acquisition and incentive refund already paid/settled separately excluded.
 90m separate exit provision is incremental legal, employee severance and taxes,
 not the accrued wages/tax balance paid here. All discounts are economic estimates.
 """
 gross_wc=286.98703715*.85+1.016*.95+53.10031024*.50+84.10920963*.50+170.10704469*.60+12.*.50
 remaining_other_payable=181.71326971-106.36733768-22.89917864
 operating_liabilities=78.38905534+82.93037543+38.96684392+45.91155543+remaining_other_payable+6.94161990+.0635
 wc_open_net=gross_wc-operating_liabilities
 wc_growth_recovery=(sales-opening_sales)*c['working_capital_ratio']*.70
 project_wc_recovery=project_revenue*c['project_wc_ratio']*.70
 fixed_net=406.59292432*.30+108.37673124*.50
 return dict(receivables_inventory_other_gross=gross_wc,ordinary_liabilities_paid=operating_liabilities,other_payables_excluding_separately_settled=remaining_other_payable,opening_net_wc=wc_open_net,incremental_wc_net_recovery=wc_growth_recovery,project_wc_net_recovery_common=project_wc_recovery,fixed_investment_property_net=fixed_net,net_recovery_common=(wc_open_net+wc_growth_recovery+fixed_net)*common_factor+project_wc_recovery,excluded_separate=['bank_and_trading_financial_liabilities','legacy_acquisition','incentive_refund','lease','associates','incremental_exit_severance_legal_tax'],zero_recovery=['goodwill','capitalized_development','ROU_asset','remaining_project_fixed_investment'])

def run(c):
 f=FACTS; gross=f['cash']+f['trading_assets']+f['other_current']-f['other_current_nonfinancial_estimate']+f['other_noncurrent']-f['noncurrent_prepayment_proxy_H1']
 common=gross-c['minority_financial_interest_budget']-f['paid_october_dividend']
 R=f['restricted_H1'];P=f['parent_H1_financial_assets']-R-f['paid_october_dividend']+c['parent_cash_shift'];S=common-P-R
 retained=f['parent_H1_retained_profit']-f['paid_october_dividend'];gap=max(0.,ISSUED*.5-f['parent_H1_statutory_reserve'])
 subs_eligible=0.;loan=f['parent_loan_to_ou_investment'];receivable=f['parent_dividend_receivable_H1'];reserved_invested=0.;locked=0.;unpaid_claim=0.;closed=False
 group_retained=2836.95784493-f['paid_october_dividend'];shares=SHARES
 rev=c['revenue0'][:];rows=[];previous_project_revenue=0.;parent_principal_capacity=0.;subs_principal_capacity=0.
 for y in range(1,21):
  opening=P+S+R+locked;group_retained_open=group_retained;P0,S0,R0=P,S,R;ret0=retained;eligible0=subs_eligible;loan0=loan
  rate=c['growth_1'] if y==1 else c['growth_2_5'] if y<=5 else c['growth_6_10'] if y<=10 else c['growth_11_20']
  oldrev=sum(rev);rev=[x*(1+g) for x,g in zip(rev,rate)]
  gp=sum(x*m for x,m in zip(rev,c['gross_margin']));sales=sum(rev)
  ebit=gp-sales*(c['opex_ratio']+c['recurring_credit_cost']);tax=max(0.,ebit)*c['tax'];net=ebit-tax
  shock=c['profit_shock_multiplier'] if y>=c['profit_shock_year'] else 1.
  net*=shock
  parent_op=net*c['parent_profit_share'];subs_gross_op=net*(1-c['parent_profit_share']);nci_op=subs_gross_op*c['subs_minority_profit_share'];subs_op=subs_gross_op-nci_op
  roi=c['project_roi'] if y>=c.get('project_roi_effective_year',1) else BASE['project_roi']
  project_profit=reserved_invested*roi
  deal_profit=c['new_deal_profit'][min(y-1,4)]*(1.005**max(0,y-5))*.8*shock
  subs_op+=project_profit+deal_profit
  depreciation=sales*c['depreciation_ratio'];maint=sales*c['maintenance_capex_ratio'];wc=(sales-oldrev)*c['working_capital_ratio']
  # Already-common cash adjustments: maintenance and WC first split by economic attribution.
  adj=depreciation-maint-wc
  project_revenue=project_profit/c['project_net_margin']
  project_depreciation=project_revenue*c['project_depreciation_ratio']
  project_maintenance=project_revenue*c['project_maintenance_ratio']
  project_delta_wc=(project_revenue-previous_project_revenue)*c['project_wc_ratio']
  previous_project_revenue=project_revenue
  project_cash_adjustment=project_depreciation-project_maintenance-project_delta_wc
  parent_cf=parent_op+adj*c['parent_profit_share'];subs_cf=subs_op+adj*(1-c['parent_profit_share'])*(1-c['subs_minority_profit_share'])+project_cash_adjustment
  interestP=P*c['finance_yield_aftertax'];interestS=S*c['finance_yield_aftertax'];interestR=R*c['finance_yield_aftertax']
  R+=interestR
  spend=c['project_spend'][y-1] if y<=len(c['project_spend']) else 0.
  # Project investment leaves group exactly once, whether paid directly or via an internal injection.
  R-=spend;reserved_invested+=spend
  release=R if y==c['project_release_year'] else 0.;R-=release;P+=release
  old_debt=f['bank_and_trading_financial_liabilities'] if y==1 else 0.
  old_acq=f['legacy_acquisition_payable_budget'] if y==1 else 0.
  deal_payment=(c['new_deal_payments'][y-1]*.8 if y<=5 else 0.)
  asset_sale=c['asset_sale_net'] if y==c['asset_sale_year'] else 0.
  sale_book=c['asset_sale_book'] if asset_sale else 0.
  # Net proceeds already contain taxes, costs and minority allocation; book losses affect profit budget once.
  sale_profit=asset_sale-sale_book
  S+=subs_cf+interestS+asset_sale*.5-old_debt-old_acq-deal_payment
  P+=parent_cf+interestP+asset_sale*.5
  sub_profit=subs_op+interestS+sale_profit*.5
  # Economic eligibility (not a legal statutory pool): accumulate after losses, apply remittance haircut.
  subs_eligible+=sub_profit
  collection=min(receivable,max(0.,S-c['subs_min_cash'])) if y==1 else 0.
  S-=collection;P+=collection;receivable-=collection
  loan_repay=min(loan,c['loan_repay_annual_first5'] if y<=5 else c['loan_repay_annual_later'],max(0.,S-c['subs_min_cash'])) if y>=c['loan_repay_start'] else 0.
  S-=loan_repay;P+=loan_repay;loan-=loan_repay
  desired_up=max(0.,subs_eligible)*c['remittance_ratio'] if y>=c['remittance_start'] else 0.
  up=min(desired_up,max(0.,S-c['subs_min_cash']))
  S-=up;P+=up;subs_eligible-=up
  capital_realized=0.;realization_cost=0.
  if y==c['subs_capital_realization_year']:
   # Economic partial capital extraction/asset-share sale budget, NOT a statutory paid-in-capital assertion.
   # The operations and minimum cash stay; minority interests were removed at the opening bridge.
   capital_realized=min(c['subs_capital_realization_cap'],max(0.,S-c['subs_min_cash']))
   realization_cost=capital_realized*c['realization_friction']
   S-=capital_realized;P+=capital_realized-realization_cost;subs_eligible-=realization_cost
  
  freeze=0.;thaw=0.
  if y==c['cash_freeze_year']:
   freeze=min(c['cash_freeze_amount'],max(0.,P));P-=freeze;locked+=freeze
  if c['cash_freeze_year'] is not None and y==c['cash_freeze_year']+1:
   thaw=locked;P+=locked;locked=0.
  refund=(f['first_class_refund_obligation']*c['refund_fraction']/c['refund_years'] if y<=c['refund_years'] else 0.)
  cancelled=(f['first_class_restricted_shares']*c['refund_fraction']/c['refund_years'] if y<=c['refund_years'] else 0.)
  P-=refund;shares-=cancelled;gap=max(0.,gap-cancelled*.5)
  parent_profit=parent_op+interestP+interestR+up+sale_profit*.5
  common_earnings=parent_op+subs_op+interestP+interestS+interestR
  desired=max(0.,common_earnings)*(.35 if y<=5 else .90)
  if c['surplus_release_start']<=y<=c['surplus_release_end']:desired+=c['surplus_release_annual']
  if y>c['surplus_release_end']:desired+=max(0.,P-c['parent_min_cash'])
  group_profit=parent_op+subs_op+interestP+interestS+interestR+sale_profit-realization_cost
  group_retained+=group_profit
  expected_reserve=min(max(0.,parent_profit+min(0.,retained))*.1,max(0.,gap))
  desired=min(desired,max(0.,group_retained-expected_reserve))
  exit_cost=0.;liquidation=0.;failed=False;exit_refund=0.;exit_cancelled=0.;project_cancel=0.;liquidation_bridge={}
  if c['closure_year'] is not None and y==c['closure_year']:
   # Never clip obligations out of existence. All remaining contracted purchase payments survive.
   remaining_deal=sum(c['new_deal_payments'][y:])*.8
   exit_refund=f['first_class_refund_obligation']*c['refund_fraction']*max(0.,c['refund_years']-y)/c['refund_years']
   exit_cancelled=f['first_class_restricted_shares']*c['refund_fraction']*max(0.,c['refund_years']-y)/c['refund_years']
   shares-=exit_cancelled;gap=max(0.,gap-exit_cancelled*.5)
   # Announced remaining project budget is not itself proven contracted debt.
   # Explicit 20% cancellation/settlement stress budget on unpaid capex, not free cancellation.
   project_cancel=sum(c['project_spend'][y:])*c['project_cancellation_ratio']
   exit_cost=FACTS['lease_current_and_long']+c['extra_exit_cost']+remaining_deal+90.+exit_refund+project_cancel
   liquidation_bridge=liquidation_recovery(sales,sum(c['revenue0']),c['parent_profit_share']+(1-c['parent_profit_share'])*(1-c['subs_minority_profit_share']),project_revenue,c)
   liquidation=liquidation_bridge['net_recovery_common']+(c['asset_sale_net'] if y<c['asset_sale_year'] else 0.)
   P+=S+R+locked+liquidation-exit_cost;S=R=locked=0.
   unpaid_claim=max(0.,-P);failed=unpaid_claim>1e-8
   # True capital realization route on liquidation: not a profit dividend.
   parent_principal_capacity=max(0.,P);principal_desired=max(0.,P)
   z=budget_payment(P,retained,parent_profit,0.,0.,0.,0.,gap,principal_cap=parent_principal_capacity,principal_desired=principal_desired)
   P=z['cash'];retained=z['retained'];closed=True
  else:
   z=budget_payment(P,retained,parent_profit,0.,0.,c['parent_min_cash'],desired,gap)
   P=z['cash'];retained=z['retained']
  gap-=z['reserve_add'];group_retained-=z['ordinary']+z['reserve_add'];paid=z['ordinary']+z['principal']
  external_in=parent_cf+subs_cf+interestP+interestS+interestR+asset_sale+liquidation
  external_out=spend+old_debt+old_acq+deal_payment+paid+exit_cost+realization_cost+refund
  closing=P+S+R+locked
  cash_error=closing-(opening+external_in-external_out)
  assert abs(cash_error)<1e-7,(c['name'],y,cash_error)
  assert abs(loan-(loan0-loan_repay))<1e-8
  assert retained>=-1e12 # signed loss balance retained; not floored to zero
  failed=failed or min(P,S,R)<-1e-7
  rows.append(dict(year=y,effective_year=2026+y,opening_common_financial=opening,revenue_by_business=rev[:],revenue=sales,gross_profit=gp,ebit=ebit,tax=tax,parent_operating_profit=parent_op,subs_operating_profit_common=subs_op,minority_operating_profit=nci_op,project_profit=project_profit,project_revenue=project_revenue,project_depreciation=project_depreciation,project_maintenance=project_maintenance,project_delta_working_capital=project_delta_wc,project_cash_adjustment=project_cash_adjustment,new_deal_profit_common=deal_profit,depreciation=depreciation,maintenance_capex=maint,delta_working_capital=wc,parent_operating_cash=parent_cf,subs_operating_cash_common=subs_cf,parent_finance_income=interestP,subs_finance_income=interestS,restricted_finance_income=interestR,project_paid=spend,project_invested=reserved_invested,project_cash_released=release,existing_debt_paid=old_debt,legacy_acquisition_paid=old_acq,new_deal_paid_common=deal_payment,new_deal_paid_group=deal_payment/.8,asset_sale_net=asset_sale,asset_sale_profit= sale_profit,subs_capital_return_gross=capital_realized,subs_capital_return_cost=realization_cost,subs_eligibility_open=eligible0,subs_profit_for_budget=sub_profit,subs_eligibility_close=subs_eligible,dividend_receivable_collected=collection,loan_open=loan0,loan_principal_repaid=loan_repay,loan_close=loan,subs_dividend_declared_and_received=up,parent_profit_for_distribution=parent_profit,parent_retained_open=ret0,parent_reserve_add=z['reserve_add'],parent_retained_close=retained,parent_profit_dividend=z['ordinary'],parent_capital_return=z['principal'],holder_cash=paid,holder_cash_per_share=paid/shares,fully_diluted_shares=shares,incentive_refund=refund,incentive_shares_cancelled=cancelled,group_retained_open=group_retained_open,group_retained_close=group_retained,parent_cash=P,subs_cash_common=S,restricted_cash=R,locked_cash=locked,parent_minimum_cash=c['parent_min_cash'],subs_minimum_cash=c['subs_min_cash'],unpaid_claim=unpaid_claim,failed=failed,exit_cost=exit_cost,exit_incentive_refund=exit_refund,exit_incentive_cancelled_shares=exit_cancelled,exit_project_cancellation_settlement=project_cancel,liquidation_bridge=liquidation_bridge,liquidation_net_recovery=liquidation,cash_conservation_error=cash_error))
  if closed:break
 # Sale of continuing equity, not forced liquidation. Capital needed for continued activity stays in operating value.
 r=c['discount'];g=c['g_terminal'];last=rows[-1];N=len(rows)
 if closed:operating_terminal=0.;excess_terminal=-unpaid_claim;terminal=excess_terminal
 else:
  necessary=c['parent_min_cash']+c['subs_min_cash']
  common_factor=c['parent_profit_share']+(1-c['parent_profit_share'])*(1-c['subs_minority_profit_share'])
  profit_next=(last['parent_operating_profit']+last['subs_operating_profit_common'])*(1+g)
  replacement_net=last['revenue']*(1+g)*(c['maintenance_capex_ratio']-c['depreciation_ratio'])*common_factor
  mature_wc_growth=last['revenue']*g*c['working_capital_ratio']*common_factor
  project_growth_equity=(last['project_profit']/max(.001,c['project_roi'])+last['new_deal_profit_common']/.08)*max(0.,g)
  project_terminal_net_replacement=last['project_revenue']*(1+g)*(c['project_maintenance_ratio']-c['project_depreciation_ratio'])
  project_terminal_wc=last['project_revenue']*g*c['project_wc_ratio']
  core_future=profit_next-replacement_net-mature_wc_growth-project_growth_equity-project_terminal_net_replacement-project_terminal_wc
  next_cash=core_future+necessary*c['finance_yield_aftertax']-necessary*max(0.,g)
  operating_terminal=next_cash/(r-g)
  excess=P+S+R+locked-necessary
  # Explicit realization friction 5% on surplus; negative balance remains a claim.
  excess_terminal=excess*.95 if excess>=0 else excess
  if c['asset_sale_year']>N:excess_terminal+=c['asset_sale_net']/(1+r)**(c['asset_sale_year']-N)
  terminal=operating_terminal+excess_terminal
 pv_distributions=sum(row['holder_cash']/(1+r)**row['year'] for row in rows)
 pv_terminal=terminal/(1+r)**N
 value=sum(row['holder_cash_per_share']/(1+r)**row['year'] for row in rows)+terminal/shares/(1+r)**N
 terminal5=sum(row['holder_cash_per_share']/(1+r)**(row['year']-5) for row in rows if row['year']>5)+terminal/shares/(1+r)**(N-5) if N>=5 else None
 # Forward value at year 5 is calculated only from year 6 onward, never current value copied.
 failed_path=any(x['failed'] for x in rows)
 return dict(name=c['name'],inputs=c,opening=dict(gross_financial_assets=gross,common_financial_assets=common,parent_cash=FACTS['parent_H1_financial_assets']-FACTS['restricted_H1']-FACTS['paid_october_dividend']+c['parent_cash_shift'],restricted_cash=FACTS['restricted_H1'],subs_cash_common=common-(FACTS['parent_H1_financial_assets']-FACTS['paid_october_dividend']+c['parent_cash_shift'])),annual=rows,value_per_share=None if failed_path else value,diagnostic_signed_value=value,holder_distributions=[x['holder_cash_per_share'] for x in rows[:5]],terminal_year5=None if failed_path else terminal5,pv_distributions=None if failed_path else pv_distributions,pv_terminal=None if failed_path else pv_terminal,terminal_contribution=None if failed_path else pv_terminal/(pv_terminal+pv_distributions),terminal_operating=operating_terminal,terminal_surplus=excess_terminal,terminal_total=None if failed_path else terminal,diagnostic_terminal_total=terminal,failed=failed_path,unpaid_claim=unpaid_claim)

def tests():
 # Literal counterexamples enter exactly the settlement used by production paths.
 aa=budget_payment(100.,-20.,10.,0.,0.,0.,0.,reserve_gap=10.);assert aa['reserve_add']==0 and aa['retained']==-10
 a=budget_payment(100.,20.,-30.,0.,0.,0.,50.);assert a['ordinary']==0 and a['retained']==-10 and a['cash']==100
 b=budget_payment(5.,100.,0.,0.,12.,0.,30.);assert b['unpaid']==7 and not b['feasible'] and b['cash']==-7
 c=budget_payment(5.,0.,0.,10.,0.,0.,20.);assert c['ordinary']==0 and c['cash']==15 # receivable recovery isn't profit
 d=budget_payment(100.,0.,-10.,0.,0.,20.,0.,principal_cap=50.,principal_desired=80.);assert d['principal']==50 and d['retained']==-10 and d['cash']==50
 e=budget_payment(40.,100.,10.,0.,0.,20.,80.);assert e['ordinary']==20 and e['cash']==20
 # Forced production-path failure preserves claims after all fees, not max(0, liquidation).
 cc=inputs_for('closure_stress');cc['extra_exit_cost']=10000.;rr=run(cc);assert rr['failed'] and rr['unpaid_claim']>0 and rr['terminal_surplus']<0 and rr['value_per_share'] is None and rr['terminal_total'] is None and rr['pv_terminal'] is None
 # Real production parameter chain and early-closure obligations.
 half=inputs_for('base');half['parent_profit_share']=.5;hh=run(half);row=hh['annual'][0]
 assert abs(row['parent_operating_cash']-row['parent_operating_profit']-(-5.4291))<1e-7
 early=inputs_for('closure_stress');early['closure_year']=1;ee=run(early);er=ee['annual'][0]
 assert abs(er['exit_incentive_refund']-15.266119093333333)<1e-8
 assert abs(er['fully_diluted_shares']-(SHARES-FACTS['first_class_restricted_shares']))<1e-8
 assert abs(er['exit_project_cancellation_settlement']-89.86648)<1e-8
 early['extra_exit_cost']=10000.;ef=run(early);assert ef['failed'] and ef['unpaid_claim']>0 and ef['value_per_share'] is None and ef['terminal_total'] is None and ef['pv_distributions'] is None and ef['pv_terminal'] is None and ef['terminal_year5'] is None
 assert ef['annual'][0]['exit_incentive_refund']==er['exit_incentive_refund'] and ef['annual'][0]['exit_project_cancellation_settlement']==er['exit_project_cancellation_settlement']
 assert abs(ef['annual'][0]['parent_cash']+ef['unpaid_claim'])<1e-8
 return {'losses_before_reserve':True,'parent_share_complete_cash_chain':True,'early_exit_refund_share_settlement':True,'unpaid_project_cancellation_budget':True,'failed_pv_terminal_null':True,'losses_before_dividend':True,'mandatory_shortfall_preserved':True,'receivable_not_profit':True,'principal_separate':True,'cash_floor_binds':True,'real_production_exit_failure_preserves_claim':True,'failure_claim':rr['unpaid_claim']}

def build():
 names=['base','core_low','core_high','cyclical','structural','optimistic','late_remittance','project_return_4pct_from_2029','release_delayed_to_2036','margin_loss_from_2032','minority_cash_250','financial_freeze_2028','closure_stress','incentives_success','parent_profit_share_50','closure_year1','project_roi_zero','project_roi_4pct','subs_minority_20','subs_minority_60','maintenance_plus1pct','zero_subs_remittance','closure_year1_full_project_settlement','closure_year1_failed','closure_year4_failed']
 out={n:run(inputs_for(n)) for n in names}
 # Independent economic anchor: normalized no-growth owner operating profit and replacement capital,
 # not year-five DCF output or peer/current stock multiples. Capital balances use same obligations.
 normalized_owner_profit=420.;replacement_net=25.;owner_cash=normalized_owner_profit-replacement_net
 excess_financial=out['base']['opening']['common_financial_assets']-320.-FACTS['remaining_community_project_budget']-FACTS['bank_and_trading_financial_liabilities']-FACTS['legacy_acquisition_payable_budget']-96.-FACTS['first_class_refund_obligation']
 asset_pv=400./1.095**8
 secondary={'method':'normalised_owner_cash_earnings_power_plus_assets','normalized_owner_profit':420.,'depreciation_minus_replacement_capex':-25.,'owner_cash':owner_cash,'capitalization_factors':[12.,16.],'excess_financial_after_all_spending':excess_financial,'associate_net_recovery_present_value':asset_pv,'values':[(owner_cash*k+excess_financial+asset_pv)/SHARES for k in [12.,16.]],'incentive_refund_deducted_upfront':FACTS['first_class_refund_obligation'],'share_basis':'Initial fully diluted shares maintained, refund charged upfront without cancellation benefit: conservative independent bound.','boundary':'No new-project earnings credited despite full earmarked spend deducted: conservative independent mature franchise anchor; no financial interest in operating numerator.'}
 lo=round(out['core_low']['value_per_share'],2);hi=round(out['core_high']['value_per_share'],2)
 summary={'symbol':SYMBOL,'report_period':PERIOD,'information_cutoff':ASOF,'value_range':{'low':lo,'high':hi,'currency':'CNY'},'holder_distributions':out['base']['holder_distributions'],'holder_terminal_year5':{'low':out['core_low']['terminal_year5'],'high':out['core_high']['terminal_year5']},'scenario_values':{n:round(z['value_per_share'],6) if z['value_per_share'] is not None else None for n,z in out.items()},'secondary':secondary,'base_terminal_contribution':out['base']['terminal_contribution']}
 return {'schema':'CN300595_Q3_2026_full_annual_plain_json_v1','summary':summary,'unit':'CNY million except per-share and ratios','diluted_shares_initial':SHARES,'issued_shares_at_cutoff':ISSUED,'potential_second_class_shares':POTENTIAL_SECOND_CLASS,'financial_forecast_period':'20 rolling annual budgets after 2026-10-26; years 1-5 end October 2027-2031','facts':FACTS,'legal_scope':'Parent is actual listed PRC entity. R is a group restricted-cash budget allocated to parent-side funds/interest only as an economic proxy, not verified legal ownership. S is only a common-interest economic budget of actual subsidiaries; exact local statutory reserves/tax bases unknown. No consolidated reserve is treated as legal. Upstream eligibility and realization times are scenario assumptions, not legal opinions.','scenarios':out,'production_tests':tests()}
if __name__=='__main__':
 assert SYMBOL=='CN:300595' and PERIOD=='2026-Q3'
 print(json.dumps(build(),ensure_ascii=True,sort_keys=True,indent=2,allow_nan=False))
