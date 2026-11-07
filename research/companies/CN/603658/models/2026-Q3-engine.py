#!/usr/bin/env python3
"""CN:603658 安图生物 2026-Q3 economic budget; CNY billions except shares/per-share.
stdlib only. python model.py --out DIR; python model.py --test
No market price input. Fiscal annual forecasts 2027..2036 plus 2026Q4 bridge.
Subsidiary budgets are NOT stand-alone statutory accounts or distribution opinions.
"""
import argparse, copy, csv, hashlib, json, math, pathlib
SYMBOL='CN:603658'; NAME='安图生物'; PERIOD='2026-Q3'
SHARES=0.571424768 # billion issued ordinary shares; no treasury stock
ASOF='2026-10-26T21:30:00+00:00'
OPEN={
 'cash':.60216828778,'trading_financial':.93695095712,
 'other_current':1.97079678346,'nonfinancial_other_current_est':.0113,
 'financial_minorities_est':.028,
 'ar':1.22675660074,'notes_receivable':.00831578159,'receivable_financing':.01075774283,
 'inventory':1.07343509974,'prepayments':.05562692954,'other_receivable':.04480589354,
 'deferred_instrument_cost_est':1.14570212120,
 'deferred_instrument_revenue':.48380720395,
 'accounts_payable':.54080391059,'contract_liability':.12436585407,
 'payroll':.18811016538,'tax_payable':.13791034389,'other_payable':.41735767815,
 'other_current_liabilities':.05027651107,'warranty':.00891371680,
 'unrecognized_notes_debt_est':.01051082451,'notes_payable_financing':.92868402702,'short_debt':.02192511642,
 'current_debt_lease':.01027982079,'lease':.01080568554,'derivative_liability':.00147265135,
 'restricted_cash_deposits_est':.17223823135,
 'ppe':3.56646018279,'cip':.10633729696,'intangibles':.21379398039,
 'development':.24738208741,'long_term_prepaid':.09935761967,
 'deferred_tax_asset':.38965610456,'deferred_tax_liability':.22632508944,
 'goodwill':.16514426220,'invest_property':.05163853596,
 'equity_associates':.08717928683,'equity_other':.17331389480,
 'equity_deposit_est':.11425,
 'parent_cash_financial_est':2.80,'instrument_cash_est':.40,'tech_cash_est':.10,
 'parent_retained_h1_actual':2.99289569516,
 'parent_q3_profit_roll_est':.28,'parent_legal_reserve_actual':.293136128,
 'parent_registered_share_capital_actual':SHARES,
 'remaining_expansion_budget':.1250455,
 'expansion_accrued_payable_est':.080,
 'remaining_rd_project_budget':1.1434922,
}
OPEN['common_financial']=OPEN['cash']+OPEN['trading_financial']+OPEN['other_current']-OPEN['nonfinancial_other_current_est']-OPEN['financial_minorities_est']
OPEN['debt']=sum(OPEN[k] for k in ['unrecognized_notes_debt_est','notes_payable_financing','short_debt','current_debt_lease','lease','derivative_liability'])
OPEN['other_common_cash']=OPEN['common_financial']-OPEN['parent_cash_financial_est']-OPEN['instrument_cash_est']-OPEN['tech_cash_est']
OPEN['operating_nwc']=sum(OPEN[k] for k in ['ar','notes_receivable','receivable_financing','inventory','prepayments','other_receivable','nonfinancial_other_current_est','deferred_instrument_cost_est'])-sum(OPEN[k] for k in ['deferred_instrument_revenue','accounts_payable','contract_liability','payroll','tax_payable','other_payable','other_current_liabilities','warranty'])+OPEN['expansion_accrued_payable_est']+OPEN['unrecognized_notes_debt_est']
# Profit margins below expense ALL research cash, exclude all financial yields and non-recurring grants.
BASE={'domestic_growth':[.035,.04,.04,.035,.03,.03,.025,.025,.02,.02],
 'overseas_growth':[.18,.17,.15,.13,.11,.09,.08,.06,.05,.04],
 'economic_ebit_margin':[.23,.235,.24,.24,.24,.235,.23,.23,.23,.23],
 'rd_ratio':[.19,.19,.185,.18,.18,.18,.18,.18,.18,.18],
 'nwc_ratio':[.43,.43,.425,.42,.415,.41,.405,.40,.40,.40],
 'nonrd_capex_ratio':[.095,.095,.09,.09,.09,.095,.095,.095,.095,.095],
 'nonrd_da_ratio':[.10,.10,.095,.09,.09,.09,.09,.09,.09,.09],
 'tax':.12,'minority_profit_ratio':.008,'interest_rate':.03,'financial_yield':.02,'financial_tax':.25,
 'cost_equity':.095,'terminal_growth':.0175,'terminal_roic':.12,
 'normal_payout':.65,'special':[0,0,.25,.25,.25,0,0,0,0,0],
 'operating_cash_ratio':.12,'upstream_delay_years':0,'extra_parent_payment':0.,
 'no_rollover':False,'fund_exit_year':2034,'fund_net_recovery':.0891,
 'existing_invest_exit_year':2034,'existing_invest_recovery':.342,
 'financial_realization_lag':1,'financial_realization_cost':.005,
 'loss_carry_extra':0.,'rd_extra_ratio':0.,'failure':False}
def scenario(name):
 p=copy.deepcopy(BASE)
 if name=='core_low':p.update(cost_equity=.10,terminal_growth=.015,terminal_roic=.11)
 elif name=='core_high':p.update(cost_equity=.09,terminal_growth=.02,terminal_roic=.13)
 elif name=='cyclical':
  p['domestic_growth'][:3]=[-.05,.02,.10]; p['overseas_growth'][:3]=[.07,.12,.20]
  p['economic_ebit_margin'][:3]=[.19,.215,.235];p['nwc_ratio'][:4]=[.49,.49,.46,.43]
  p['nonrd_capex_ratio'][:3]=[.105,.105,.10];p['special']=[0]*10
 elif name=='structural':
  p.update(domestic_growth=[-.08,-.04,0,.01,.01,.01,.01,.01,.01,.01],overseas_growth=[.10,.08,.06,.05,.04,.03,.03,.03,.03,.03],economic_ebit_margin=[.17,.155,.15,.15,.15,.15,.15,.15,.15,.15],nwc_ratio=[.51,.56,.59,.60,.60,.60,.60,.60,.60,.60],nonrd_capex_ratio=[.105]*10,nonrd_da_ratio=[.09]*10,rd_ratio=[.20]*10,special=[0]*10,cost_equity=.105,terminal_growth=.005,terminal_roic=.08,fund_net_recovery=.0495,existing_invest_recovery=.22)
 elif name=='optimistic':
  p.update(domestic_growth=[.06,.065,.06,.055,.05,.04,.035,.03,.025,.02],overseas_growth=[.25,.23,.20,.18,.15,.12,.10,.08,.06,.05],economic_ebit_margin=[.245,.25,.255,.26,.26,.255,.25,.25,.245,.24],nwc_ratio=[.42,.415,.41,.40,.39,.385,.38,.38,.38,.38],nonrd_capex_ratio=[.105]*10,rd_ratio=[.19]*10,terminal_roic=.14,fund_net_recovery=.1188)
 elif name=='upstream_delay':p.update(upstream_delay_years=2,extra_parent_payment=.20)
 elif name=='no_rollover':p.update(no_rollover=True)
 elif name=='slow_asset_release':p.update(financial_realization_lag=4,existing_invest_exit_year=2036,fund_exit_year=2036)
 elif name=='rd_cost_up':p.update(rd_extra_ratio=.02)
 elif name=='tax_expiry':p.update(tax=.22)
 elif name=='working_capital_up':p['nwc_ratio']=[x+.10 for x in p['nwc_ratio']]
 elif name=='failure':p.update(economic_ebit_margin=[-.60]*10,domestic_growth=[-.15]*10,overseas_growth=[-.1]*10,special=[0]*10,failure=True)
 elif name!='base':raise ValueError(name)
 p['name']=name;return p

def legal_payment(cash, reserve_cash, requested, retained, net_profit, registered, statutory):
 """Real parent only. Losses reduce retained; reserve proxy applies after losses made good.
 No dividends are legally certified; this implements explicitly budgeted stand-alone income.
 """
 loss_offset=min(max(-retained,0.),max(net_profit,0.))
 positive=max(net_profit-loss_offset,0.)
 reserve_add=min(.10*positive,max(.50*registered-statutory,0.))
 available_profit=retained+net_profit-reserve_add
 available_cash=cash-reserve_cash
 paid=min(max(requested,0.),max(available_profit,0.),max(available_cash,0.))
 return {'paid':paid,'retained':available_profit-paid,'statutory':statutory+reserve_add,'reserve_add':reserve_add,'cash':cash-paid,'unmet_request':max(requested-paid,0.)}

def compute(p):
 # Q4 bridge is a forecast, not reported; nine-month balances are the actual opening.
 # All cash proceeds and costs remain attributable to the same ordinary holders.
 cash={k:OPEN[v] for k,v in [('parent','parent_cash_financial_est'),('instrument','instrument_cash_est'),('tech','tech_cash_est'),('other','other_common_cash')]}
 debt=OPEN['debt'];nw=OPEN['operating_nwc'];r=p['cost_equity'];minority_cash=OPEN['financial_minorities_est']
 retained=OPEN['parent_retained_h1_actual']+OPEN['parent_q3_profit_roll_est'];stat=OPEN['parent_legal_reserve_actual']
 rd_project_left=OPEN['remaining_rd_project_budget'];fund_paid=0.;fund_asset=0.;existing_asset=OPEN['equity_associates']+OPEN['equity_other']+OPEN['equity_deposit_est']
 rd_project_plan={2026:.0878177,2027:.3522672,2028:.4204759,2029:.2829314}
 # latest project balance remaining 1.1434922 includes legacy budget; spending allocations
 # are WITHIN total R&D cash, not a second expense or second capex line.
 assert abs(sum(rd_project_plan.values())-rd_project_left)<1e-8
 domestic=3.96;overseas=.49 # 2026E 4.45bn, bounded by H1 and Q3 consolidated actual
 fixed=OPEN['ppe']+OPEN['cip']+OPEN['intangibles']+OPEN['long_term_prepaid']
 rows=[];feasible=True; failure_reason=None; first_failure_year=None
 for i,year in enumerate(range(2026,2037)):
  stub=year==2026;j=i-1
  if stub:
   sales=4.45-3.23952511120; margin=.235;rd=sales*.19;da=.112;cap=.145
   # Q4 operating settlements release only .06bn net, not all receivables or liabilities.
   end_nw=nw-.06;tax=.12;special=0.;request=0.;repay=0.;legacy=.03
  else:
   domestic*=1+p['domestic_growth'][j];overseas*=1+p['overseas_growth'][j];sales=domestic+overseas
   margin=p['economic_ebit_margin'][j]-p['rd_extra_ratio'];rd=sales*(p['rd_ratio'][j]+p['rd_extra_ratio'])
   da=sales*p['nonrd_da_ratio'][j];cap=sales*p['nonrd_capex_ratio'][j]
   end_nw=sales*p['nwc_ratio'][j];tax=p['tax'];special=p['special'][j];legacy=.05 if year==2027 else 0.
   repay=debt if p['no_rollover'] and year==2027 else min(.30,debt-.40) if year==2029 and debt>.40 else min(debt-.40,.30) if year==2031 and debt>.40 else 0.
  if not feasible:
   repay=0.;request=0.;special=0.
  # Future .0450455bn final expansion work resides inside non-R&D capex; already accrued
  # .080bn carved out of opening operating payables and settled .03/.05 once here.
  if year==2027:assert cap>=OPEN['remaining_expansion_budget']-OPEN['expansion_accrued_payable_est']
  opening_total=sum(cash.values());opening_cash=dict(cash);opening_debt=debt;opening_nw=nw
  ebit=sales*margin
  # No negative tax refund: losses are not converted into cash rebates.
  cash_tax=max(ebit,0.)*tax
  nopat=ebit-cash_tax
  minprofit=nopat*p['minority_profit_ratio'] if nopat>0 else nopat*p['minority_profit_ratio']
  common_nopat=nopat-minprofit
  # Full group capital expenditures and working capital, less explicit minority share.
  group_fcf=nopat+da-cap-(end_nw-nw)
  minority_capital_share=(da-cap-(end_nw-nw))*p['minority_profit_ratio']
  minority_cf=minprofit+minority_capital_share
  common_fcf=group_fcf-minority_cf
  interest=debt*p['interest_rate']*(.25 if stub else 1.)
  interest_tax_shield=min(cash_tax,interest*tax) if ebit>0 else 0.
  financing_cost=interest-interest_tax_shield
  yields={k:max(v,0.)*p['financial_yield']*(1-p['financial_tax'])*(.25 if stub else 1.) for k,v in cash.items()}
  financial_income=sum(yields.values());yield_tax=sum(max(v,0.) for v in cash.values())*p['financial_yield']*p['financial_tax']*(.25 if stub else 1.)
  operating_cash_flow=nopat+da-(end_nw-nw)
  # Annual allocation is economic, after intercompany eliminations. Not legal segment profit.
  proportions={'parent':.65,'instrument':.25,'tech':.03,'other':.07}
  for k,a in proportions.items():cash[k]+=common_fcf*a+yields[k]
  cash['parent']-=financing_cost+repay+legacy
  debt-=repay
  call=0. if stub else {2027:.0198,2028:.0198,2029:.0396,2030:.0198}.get(year,0.)
  cash['parent']-=call;fund_paid+=call;fund_asset+=call
  fund_recovery=0.;existing_recovery=0.;fund_gain=0.;fund_return_capital=0.;fund_loss=0.
  if year==p['fund_exit_year']:
   fund_recovery=p['fund_net_recovery'];fund_return_capital=min(fund_recovery,fund_paid);fund_gain=max(fund_recovery-fund_paid,0.);fund_loss=max(fund_paid-fund_recovery,0.);cash['parent']+=fund_recovery;fund_asset=0.
  if year==p['existing_invest_exit_year']:
   existing_recovery=p['existing_invest_recovery'];cash['parent']+=existing_recovery;existing_asset=0.
  # Dividend budgets from actual entities, current-year positive profit only. 10% retention
  # is a budget allowance when full individual legal reserve details are unavailable.
  upstream={};upstream_profit={}
  for k in ['instrument','tech']:
   profit=common_nopat*proportions[k]+yields[k]
   floor=(.08 if k=='instrument' else .02)*(sales/4.45)
   allowed=0. if not stub and j<p['upstream_delay_years'] else min(max(profit,0.)*.90,max(cash[k]-floor,0.))
   desired=max(profit,0.)*(.80 if k=='instrument' else .70)
   pay=min(allowed,desired);cash[k]-=pay;cash['parent']+=pay;upstream[k]=pay;upstream_profit[k]=profit
  # Other subsidiary economic funds remain within enterprise, no invented legal pool.
  other_transfer=0.
  if year>=2030:
   other_transfer=min(max(common_nopat*.07,0.)*.60,max(cash['other']-.08*sales/4.45,0.))
   cash['other']-=other_transfer;cash['parent']+=other_transfer
  # Existing parent intercompany receivables settle at face in stress only: no new income.
  extra_parent= p['extra_parent_payment'] if not stub and j<2 else 0.
  cash['parent']-=extra_parent;cash['other']+=extra_parent
  # Economic R&D fully expensed conservatively in parent budget; no capitalization uplift.
  parent_profit=common_nopat*.65+yields['parent']-financing_cost+sum(upstream.values())+other_transfer+fund_gain-fund_loss
  if existing_recovery:parent_profit+=existing_recovery-(OPEN['equity_associates']+OPEN['equity_other']+OPEN['equity_deposit_est'])
  # Model shareholder distributions use prior-year earnings anchor, no already-paid 2026 dividend.
  common_earnings=common_nopat-financing_cost+financial_income
  if not stub:
   request=max(prior_common_earnings,0.)*p['normal_payout']+special
   # mature residual cash release is budgeted at parent and leaves operating/approved project buffer.
   if year>=2032:request+=max(cash['parent']-sales*.12-1.0,0.)*.50
  required_group_cash=sales*p['operating_cash_ratio'] if not stub else .55
  parent_floor=required_group_cash*.70
  # Reserve still-unspent approved R&D project only to extent not funded from the following year
  # available operating inflows: full remaining reserve until expenditure, no double cash cost.
  rd_project_spend=rd_project_plan.get(year,0.);assert rd_project_spend<=rd+1e-9
  rd_project_left-=rd_project_spend
  reserve_project=max(rd_project_left,0.)
  parent_floor+=reserve_project*.70
  request=min(request,max(sum(cash.values())-required_group_cash,0.))
  if not feasible or min(cash.values())<0:request=0.
  legal=legal_payment(cash['parent'],parent_floor,request,retained,parent_profit,SHARES,stat)
  dist=legal['paid'];cash['parent']=legal['cash'];retained=legal['retained'];stat=legal['statutory']
  # Parent support bounded by existing group cash only, no new capital invented.
  support=0.
  if cash['parent']<0:
   for k in ['instrument','tech','other']:
    x=min(max(cash[k]-.05,0.),-cash['parent']);cash[k]-=x;cash['parent']+=x;support+=x
  ending_total=sum(cash.values())
  cash_residual=ending_total-(opening_total+common_fcf+financial_income-financing_cost-repay-legacy-call+fund_recovery+existing_recovery-dist)
  assert abs(cash_residual)<1e-9
  if min(cash.values())<-.0000001 or ending_total<required_group_cash-.0000001:
   feasible=False
   if failure_reason is None:
    first_failure_year=year
    failure_reason=f'{year}: liquid resources below operating minimum; no unlimited rescue or floor-zero terminal permitted'
  fixed+=cap-da
  tax_reversal_allowance=.02 if year<=2030 else 0.
  # Deferred-tax realization uncertainty is already included in cash tax rate. Diagnostic only.
  gross_margin=(.70 if stub else .685 if year<=2029 else .68 if year<=2031 else .675)
  if p['name']=='cyclical' and year in (2027,2028):gross_margin=.65
  if p['name']=='structural' and not stub:gross_margin=.615
  if p['name']=='optimistic' and not stub:gross_margin=.70
  if p['name']=='failure' and not stub:gross_margin=.35
  selling=sales*.19;operating_taxes=sales*.015;administration=sales*gross_margin-selling-operating_taxes-rd-ebit
  row={'economic_gross_margin_budget':gross_margin,'cogs_budget':sales*(1-gross_margin),'selling_cash_and_da_budget':selling,'operating_taxes_budget':operating_taxes,'administration_residual_budget':administration,'year':year,'is_stub':stub,'sales':sales,'domestic_sales':None if stub else domestic,'overseas_sales':None if stub else overseas,'economic_ebit_margin':margin,'cash_rd_total_in_ebit':rd,'project_rd_within_total':rd_project_spend,'project_rd_unspent_reserve':max(rd_project_left,0.),'ebit_after_all_rd':ebit,'operating_cash_tax':cash_tax,'group_nopat':nopat,'minority_profit':minprofit,'common_nopat':common_nopat,'nonrd_da':da,'nonrd_capex':cap,'opening_nwc':opening_nw,'ending_nwc':end_nw,'nwc_investment':end_nw-opening_nw,'operating_cash_flow':operating_cash_flow,'group_fcf':group_fcf,'minority_capital_cash_share':minority_capital_share,'minority_cashflow':minority_cf,'common_fcf_before_financing':common_fcf,'opening_debt':opening_debt,'gross_interest':interest,'interest_tax_shield':interest_tax_shield,'net_financing_cost':financing_cost,'debt_repayment':repay,'ending_debt':debt,'legacy_accrued_settlement':legacy,'opening_common_financial':opening_total,'financial_yield_net':financial_income,'financial_income_tax':yield_tax,'fund_call':call,'fund_paid_to_date':fund_paid,'fund_asset_cost_remaining':fund_asset,'fund_exit_net_cash':fund_recovery,'fund_capital_return':fund_return_capital,'fund_gain_after_cost_tax':fund_gain,'fund_loss_no_tax_refund':fund_loss,'existing_invest_exit_net_cash':existing_recovery,'existing_asset_cost_remaining':existing_asset,'instrument_profit_budget':upstream_profit['instrument'],'instrument_upstream':upstream['instrument'],'tech_profit_budget':upstream_profit['tech'],'tech_upstream':upstream['tech'],'other_subsidiary_economic_upstream_budget':other_transfer,'extra_intercompany_settlement_no_profit':extra_parent,'parent_profit_budget_not_legal_certificate':parent_profit,'parent_retained_profit_budget':retained,'parent_statutory_reserve':stat,'parent_reserve_add':legal['reserve_add'],'parent_cash_floor_including_unspent_project':parent_floor,'common_earnings_budget':common_earnings,'requested_dividend':request,'common_cash_distribution':dist,'distribution_per_share':dist/SHARES,'unmet_distribution_request':legal['unmet_request'],'ending_parent_financial':cash['parent'],'ending_instrument_financial':cash['instrument'],'ending_tech_financial':cash['tech'],'ending_other_common_financial':cash['other'],'ending_common_financial':ending_total,'required_operating_cash':required_group_cash,'nonrd_fixed_assets_model':fixed,'capital_employed_common':(fixed+end_nw+required_group_cash)*(1-p['minority_profit_ratio']),'feasible_to_date':feasible,'bounded_internal_support':support,'cash_conservation_residual':cash_residual,'first_failure_year':first_failure_year,'unfunded_operating_minimum':max(required_group_cash-ending_total,0.),'unpaid_senior_cash_claims_budget':max(-ending_total,0.),'financial_debt_claim_preserved':debt,'failure_cash_is_unfunded_budget_not_bank_balance':not feasible,'shares_billion':SHARES}
  rows.append(row);nw=end_nw
  prior_common_earnings=(common_earnings+(.84709104128-.15)) if stub else common_earnings
 def terminal_at(index,r_override=None,g_override=None,roic_override=None):
  row=rows[index];rate=p['cost_equity'] if r_override is None else r_override;g=p['terminal_growth'] if g_override is None else g_override;roic=p['terminal_roic'] if roic_override is None else roic_override
  if not feasible:return {'equity_value':None,'reason':failure_reason}
  if index<10:
   # Exact tail forecast with remaining operating allocations/dividends, not copying today's value.
   tail=sum(rows[k]['common_cash_distribution']/(1+rate)**(k-index) for k in range(index+1,11))
   end=terminal_at(10,rate,g,roic)
   eq=tail+end['equity_value']/(1+rate)**(10-index)
   return {'equity_value':eq,'per_share':eq/SHARES,'explicit_tail_distribution_pv':tail,'remaining_terminal_pv':end['equity_value']/(1+rate)**(10-index)}
  steady_nopat=row['common_nopat']*(1+g)
  reinvestment=steady_nopat*g/roic
  steady_fcf=steady_nopat-reinvestment
  operating=steady_fcf/(rate-g)
  extra_financial=row['ending_common_financial']-row['required_operating_cash']
  # Extra principal is realized under approvals at stated delay, not capitalized interest only.
  financial_net=extra_financial*(1-p['financial_realization_cost'])/(1+rate)**p['financial_realization_lag']
  net_assets=financial_net-row['ending_debt']
  # Only still unexited assets are included; cost is not automatically fair value.
  still_assets=(row['fund_asset_cost_remaining']*.90+row['existing_asset_cost_remaining']*.90)
  equity=operating+net_assets+still_assets
  return {'steady_common_nopat':steady_nopat,'steady_reinvestment_including_operating_cash':reinvestment,'steady_common_fcf':steady_fcf,'operating_value':operating,'excess_financial_principal':extra_financial,'financial_realization_pv':financial_net,'debt':row['ending_debt'],'remaining_investment_value':still_assets,'equity_value':equity,'per_share':equity/SHARES}
 final=terminal_at(10) if feasible else None
 roll=(1+r)**(26/365.)
 if feasible:
  dpv=sum(row['common_cash_distribution']/(1+r)**(row['year']-2026+.25) for row in rows if not row['is_stub'])
  tpv=final['equity_value']/(1+r)**10.25
  current=(dpv+tpv)*roll/SHARES
  tv5lo=terminal_at(5,.10,.015,.11);tv5hi=terminal_at(5,.09,.02,.13)
 else:dpv=tpv=current=None;tv5lo=tv5hi={'per_share':None}
 # Secondary method: normalized recurring distributable operating cash from 2028; asset
 # realization and debt timing explicit. No peer market multiple, no double yield.
 normal=rows[2]
 normal_cash=(normal['common_nopat']*(1-.0175/.12))
 auxiliary_operating=normal_cash/(r-.0175)
 financial_pv=(OPEN['common_financial']-.55)*(1-p['financial_realization_cost'])/(1+r)**3
 # initial debt and legacy are paid/valued once in this stock bridge; future fund net outflow priced separately.
 fund_npv=sum(-rows[k]['fund_call']/(1+r)**(rows[k]['year']-2026+.25) for k in range(1,11))+sum(rows[k]['fund_exit_net_cash']/(1+r)**(rows[k]['year']-2026+.25) for k in range(1,11))
 existing_npv=sum(rows[k]['existing_invest_exit_net_cash']/(1+r)**(rows[k]['year']-2026+.25) for k in range(1,11))
 auxiliary=(auxiliary_operating+financial_pv-OPEN['debt']-OPEN['expansion_accrued_payable_est']+fund_npv+existing_npv)*roll/SHARES if feasible else None
 return {'identity':{'symbol':SYMBOL,'name':NAME,'period':PERIOD,'information_cutoff':ASOF},'parameters':p,'opening':OPEN,'years':rows,'feasible':feasible,'failure_reason':failure_reason,'first_failure_year':first_failure_year,'historical_distributions_before_failure':[{'year':z['year'],'cash':z['common_cash_distribution']} for z in rows if first_failure_year and z['year']<first_failure_year], 'unpaid_claims_at_end':None if feasible else {'unfunded_senior_cash_claims':rows[-1]['unpaid_senior_cash_claims_budget'],'outstanding_financial_principal':debt,'operating_accounts_payable_not_legally_extinguished':OPEN['accounts_payable'],'payroll_opening_not_waived':OPEN['payroll'],'tax_opening_not_waived':OPEN['tax_payable'],'warranty_opening_not_waived':OPEN['warranty'],'scope':'Gross claim categories are NOT additive to projected deficit: continuing settlements and new accruals are embedded in NWC/costs; no liquidation value asserted.'},'current_value_per_share':current,'dividend_pv_bn_from_sep30':dpv,'terminal_pv_bn_from_sep30':tpv,'terminal_pv_share':None if not feasible else tpv/(dpv+tpv),'terminal_2036':final,'five_year_distributions':[x['distribution_per_share'] for x in rows[1:6]],'terminal_2031_range_per_share':{'low':tv5lo['per_share'],'high':tv5hi['per_share']} if feasible else None,'terminal_2031_detail':{'low':tv5lo,'high':tv5hi} if feasible else None,'auxiliary':{'normal_cash_2028':normal_cash,'operating_value':auxiliary_operating,'initial_financial_realization_pv':financial_pv,'debt_deduction':OPEN['debt'],'legacy_accrued_deduction':OPEN['expansion_accrued_payable_est'],'fund_npv':fund_npv,'existing_investment_npv':existing_npv,'value_per_share':auxiliary}}

def tests():
 # Known cases pass through the very same legal-payment function used in all production paths.
 q=legal_payment(10,2,8,3,2,10,5);assert q['paid']==5 and q['cash']==5 and q['retained']==0
 q=legal_payment(10,2,8,-3,2,10,0);assert q['paid']==0 and q['retained']==-1 and q['reserve_add']==0
 q=legal_payment(10,2,8,-3,5,10,0);assert abs(q['paid']-1.8)<1e-10 and abs(q['reserve_add']-.2)<1e-10
 q=legal_payment(1,2,8,100,-10,10,5);assert q['paid']==0 and q['cash']==1 and q['retained']==90
 b=compute(scenario('base'));assert b['feasible'];assert len(b['years'])==11 and len(b['five_year_distributions'])==5
 assert abs(sum(x['fund_call'] for x in b['years'])-.099)<1e-9
 assert abs(sum(x['legacy_accrued_settlement'] for x in b['years'])-.08)<1e-9
 assert b['years'][0]['common_cash_distribution']==0
 assert b['years'][-1]['fund_asset_cost_remaining']==0
 assert not compute(scenario('failure'))['feasible']
 f=compute(scenario('failure'));assert f['current_value_per_share'] is None and f['terminal_2036'] is None and f['terminal_2031_range_per_share'] is None
 assert all(x['common_cash_distribution']==0 for x in f['years'] if x['year']>=f['first_failure_year'])
 assert f['unpaid_claims_at_end']['unfunded_senior_cash_claims']>0 and f['unpaid_claims_at_end']['outstanding_financial_principal']>0
 # Production parameter counterexamples: no yield removes yield everywhere; all principal remains.
 p=scenario('base');p['financial_yield']=0.;z=compute(p)
 assert all(x['financial_yield_net']==0 for x in z['years'])
 assert z['current_value_per_share']<b['current_value_per_share']
 p=scenario('base');p['normal_payout']=0;p['special']=[0]*10
 z=compute(p);assert all(x['common_cash_distribution']==0 for x in z['years'][1:6]);assert z['years'][5]['ending_common_financial']>b['years'][5]['ending_common_financial']
 return {'same_function_hand_cases':4,'production_full_path_counterexamples':['zero_financial_yield','no_first_five_dividends','insolvent_failure_no_terminal'],'pass':True}

def main():
 a=argparse.ArgumentParser();a.add_argument('--out',default=None,help='Explicit output directory (relative to invocation cwd), using model-output.json/model-summary.json/model-years.csv. Without --out, write 2026-Q3-* beside this script.');a.add_argument('--test',action='store_true');args=a.parse_args()
 test=tests()
 if args.test:print(json.dumps(test,ensure_ascii=False));return
 out=pathlib.Path(args.out) if args.out is not None else pathlib.Path(__file__).resolve().parent;out.mkdir(parents=True,exist_ok=True)
 prefix='model' if args.out is not None else PERIOD
 names=['base','core_low','core_high','cyclical','structural','optimistic','upstream_delay','no_rollover','slow_asset_release','rd_cost_up','tax_expiry','working_capital_up','failure']
 full={n:compute(scenario(n)) for n in names}
 summary={'identity':{'symbol':SYMBOL,'name':NAME,'period':PERIOD},'units':'CNY billion; per share CNY','core_value_range':{'low':round(full['core_low']['current_value_per_share'],2),'high':round(full['core_high']['current_value_per_share'],2)},'five_year_distributions':full['base']['five_year_distributions'],'terminal_2031_range_per_share':full['base']['terminal_2031_range_per_share'],'scenarios':{n:{k:v for k,v in z.items() if k in ['feasible','failure_reason','current_value_per_share','terminal_pv_share','five_year_distributions','terminal_2031_range_per_share','auxiliary']} for n,z in full.items()},'tests':test}
 for filename,obj in [(prefix+'-output.json',full),(prefix+'-summary.json',summary)]:
  (out/filename).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
 with (out/(prefix+'-years.csv')).open('w',encoding='utf8',newline='') as f:
  fields=['scenario']+list(full['base']['years'][0]);w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for n,z in full.items():
   for row in z['years']:w.writerow({'scenario':n,**row})
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
