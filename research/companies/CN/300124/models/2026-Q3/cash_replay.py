import hashlib,copy
from pathlib import Path
# NEW_RECONSTRUCTION: cached operating inputs; current cash recursion.
# No original main/build or full-company scenario generator is included.
CACHE_ROWS = None
TAIL_ROWS = None
EVENT_DELTA_CASH = 0.0
TREASURY_SHARES = .003566367

import json,math,copy,argparse,pathlib

IDENTITY={'symbol':'CN:300124','name':'深圳市汇川技术股份有限公司','period':'2026-Q3'}

AUTO=2/2.441731160

SHARES=2.711067851

OPEN_ASSETS={'receivable_notes':5.32878475815,'receivable_accounts':13.33346580955,'receivable_financing':3.25065559237,'inventory':12.45814369716,'prepay':.70719286410,'contract':.07008380242,'other_current':.90764778674,'other_receivable':.08852489222}

OPEN_LIAB={'trade_notes':9.41703644482,'trade_payables':15.17031033890,'advance':.00143483149,'contract':1.05281979070,'payroll':1.11630211133,'tax':.69693922849,'other_payable':1.00772690972,'other_current':2.47789083639}

OPEN_AUTO_NWC=(1.10853852319+5.78253428177+.93022099260+5.06457024580+.035616613+.01644464513+.31345597922+.02413395069)-(4.91809942048+8.6431132467+.00077251835+.0900294145+.35163781694+.2031289526+.47232621392+.89426644675)

OPEN_NWC=sum(OPEN_ASSETS.values())-sum(OPEN_LIAB.values())-(1-AUTO)*OPEN_AUTO_NWC

LIQ_GROSS=6.11774603506+2.88814033572+3.97137282189+(4.30421957769-.924)

AUTO_LIQ=2.40302543223+2.10500383562+.52220289039+.75

OPEN_CASH=LIQ_GROSS-(1-AUTO)*AUTO_LIQ-1.4

OPEN_DEBT=.55047696978+1.34337002006+1.07762025839+.20428499029-(1-AUTO)*(.09341929328+.82999247317+.08964571596)

INVEST_BOOK=2.32681209910+3.48365106216-1.316-.17

BASE={'label':'Base','r':.10,'g':.025,'roic':.16,'auto_owner':AUTO,'margin_shift':0.,'growth_shift':0.,'nwc_extra':0.,'capex_extra':0.,'remit_factor':1.,'parent_runoff':.5,'claim':0.,'claim_year':1,'invest_recovery':.85,'invest_years':[5,9],'debt_limit':4.,'dividend_factor':1.,'tax':.15,'other_minority':.025,'special':False,'support_all_auto':False,'failure_cost':0.,'exercise':True,'capital_delay':3,'capital_leakage':.02}

def reserve_profit(opening,profit,paid,reserve,capital):
 """Actual production legal parent gate: loss offsets first, reserve only positive profit after losses."""
 pre=opening+profit;loss_cure=min(max(-opening,0.),max(profit,0.))
 add=min(max(capital*.5-reserve,0.),max(profit-loss_cure,0.)*.1)
 available=pre-add
 dividend=min(max(available,0.),max(paid,0.))
 return available-dividend,reserve+add,dividend,add

def cash_step(cash,inflow,senior_due,min_cash,debt,limit,proposed,blocked=False):
 """Financing is actual draw; unpaid creditors persist; shareholder paid last."""
 gross=cash+inflow;draw=min(max(senior_due+min_cash-gross,0.),max(limit-debt,0.))
 gross+=draw;paid=min(max(gross,0.),senior_due);unpaid=senior_due-paid
 left=gross-paid;div=0. if blocked or unpaid>1e-9 else min(proposed,max(left-min_cash,0.))
 return {'cash':left-div,'draw':draw,'debt':debt+draw,'senior_paid':paid,'unpaid':unpaid,'distribution':div}

def investment_exit(book,recovery,tax_basis):
 gross=book*recovery;fees=gross*.02;tax=max(gross-tax_basis,0.)*.25
 cash=gross-fees-tax
 return {'gross':gross,'fees':fees,'tax':tax,'cash':cash,'book_removed':book,'after_tax_disposal_profit':cash-book}

def run(p):
 # 2027-2036 = future twelve-month budgeting buckets, year 1 ends Oct 2027.
 rev=[27.5,22.,3.2,.8];assets=[6.,6.5,1.2,.3];extra_assets=[0.,0.,0.,0.];cash=OPEN_CASH;debt=OPEN_DEBT;nwc=OPEN_NWC
 parent_cash=.332784296+3.0-EVENT_DELTA_CASH;parent_debt=1.225859188;parent_re=8.19165228829;parent_res=1.3549350945
 parent_old_div=.12;sub_losses={'苏州汇川技术有限公司':0.,'苏州汇川控制技术有限公司':0.}
 shares=SHARES;rows=[];failed=False;unpaid=0.;unpaid_parent=0.;invest=INVEST_BOOK;historical=0.;held=1.4
 for y in range(1,11):
  opening_cash=cash;opening_debt=debt;opening_nwc=nwc;opening_parent_cash=parent_cash;opening_shares=shares
  saved=CACHE_ROWS[y-1]
  issue7=([.005996920,.007287125,.007287125][y-1] if y<=3 else 0.)
  issue8=(.0442164/4 if y<=4 else 0.)
  issue6=(.003091382 if y==1 else 0.)
  reserve7=([.001020160,.000769200,.000769200][y-1] if y<=3 else 0.)
  issue7+=reserve7
  if not p['exercise'] or p['special']=='structural' or (p['special']=='cycle' and y<=2):issue7=issue8=issue6=0.
  # Future receipt only when forecast issuance occurs; announced grant is not current cash.
  issue_cash=issue6*59.40+issue7*41.96+issue8*((.0127686*39.41+.0314478*56.30)/.0442164)
  shares+=issue7+issue8+issue6
  prevrev=rev[:];rev=[s['revenue'] for s in saved['segments']]
  future_auto=(2/(2.441731160+.039603750) if p['exercise'] and p['special']!='structural' else p['auto_owner'])
  ownership_cash_bridge=0.
  if y==1 and future_auto!=AUTO:
   dilution=AUTO-future_auto
   ownership_cash_bridge=-dilution*AUTO_LIQ+future_auto*.039603750*2.857
   cash+=ownership_cash_bridge
   debt-=dilution*(.09341929328+.82999247317+.08964571596)
   opening_nwc-=dilution*OPEN_AUTO_NWC
  segments=copy.deepcopy(saved['segments']);earn=saved['owner_nopat']
  capex=saved['cash_capex'];da=saved['depreciation'];effective_rev=saved['effective_revenue']
  nwc=saved['closing_nwc'];delta=nwc-opening_nwc;interest=debt*.045
  fcf=earn+da-capex-delta-interest
  release=0.;inv_tax=0.;inv_fees=0.;inv_book=0.
  if y in p['invest_years']:
   inv_book=INVEST_BOOK/2;exit_flow=investment_exit(inv_book,p['invest_recovery'],1.5)
   inv_fees=exit_flow['fees'];inv_tax=exit_flow['tax'];release=exit_flow['cash'];invest-=inv_book
  restricted_release=0.
  if y==(7 if p['special']=='deposit_delay' else 3):restricted_release=held;held=0.
  fin_income=max(cash,0.)*.012 # after 25% tax on ordinary financial income, no software exemption
  # Parent upstream estimates from two actual wholly owned firms; budgets not legal attestations.
  upstream=0.;subdata=[]
  for name,ratio in [('苏州汇川技术有限公司',.28),('苏州汇川控制技术有限公司',.23)]:
   profit=segments[0]['nopat']*ratio
   net=sub_losses[name]+profit;capacity=max(net,0.)*.9 # 10% prudential reserve, no invented opening reserve
   remit=capacity*.55*p['remit_factor']
   if p['special']=='remit_delay' and y<=2:remit=0.
   sub_losses[name]=min(net,0.)
   upstream+=remit;subdata.append({'legal_entity':name,'budget_after_tax_profit':profit,'loss_carry':sub_losses[name],'new_profit_distributable_proxy':capacity,'cash_remittance_budget':remit,'legal_single_entity_certified':False})
  own_parent=1.7*(rev[0]/27.5) # after-tax own licensing/services profit, part of group earnings
  parent_growth=.40 if y<=3 else .25 # internal transfer/investment, no second group cost
  parent_fin_income=max(parent_cash,0.)*.012
  # Only identified parent-held Qianhai Jingrui H1 carrying amount allocated to direct exits.
  # Q3 carrying amount/tax basis not disclosed: explicit proxy, not statutory certification.
  parent_exit_fraction=1.84300334653/INVEST_BOOK
  parent_exit_cash=release*parent_exit_fraction
  parent_exit_book=inv_book*parent_exit_fraction
  parent_disposal_profit=parent_exit_cash-parent_exit_book
  parent_profit=own_parent+upstream+parent_fin_income+parent_disposal_profit # old dividends and returned principal not profit
  oldreceipt=parent_old_div if y==1 else 0.;parent_old_div-=oldreceipt
  internal_runoff=p['parent_runoff'] if y<=3 else 0. # parent owes subsidiaries; group-neutral cash movement
  parent_external_due=(parent_debt*.4 if y<=3 else parent_debt)+(.187 if y==1 else 0.)
  parent_due=parent_external_due+internal_runoff+parent_growth+unpaid_parent
  parent_debt=max(0.,parent_debt-parent_external_due+(.187 if y==1 else 0.))
  proposed=max(earn-interest,0.)*(.30 if y<=3 else .45)*p['dividend_factor']
  pre_re,res,legal_paid,reserve_add=reserve_profit(parent_re,parent_profit,proposed,parent_res,shares)
  amort=min(debt,.45) if y<=7 else debt
  group_headroom=max(p['debt_limit']-(debt-amort),0.)
  parent_borrowing_limit=min(2.,parent_debt+group_headroom)
  pc=cash_step(parent_cash,own_parent+upstream+parent_fin_income+oldreceipt+parent_exit_cash+issue_cash,parent_due,.25,parent_debt,parent_borrowing_limit,legal_paid,blocked=failed)
  parent_debt=pc['debt'];parent_cash=pc['cash'];parent_res=res;unpaid_parent=pc['unpaid']
  parent_re=parent_re+parent_profit-reserve_add-pc['distribution']
  # External debt principal amortisation, normal finance facility capped, not infinite rescue.
  amort=min(debt,.45) if y<=7 else debt
  existing_claims=((.61577705120-(1-future_auto)*.59109205054)/3 if y<=3 else 0.)+((.01428997314+.000749936+.00291325871) if y==1 else 0.)
  due=amort+existing_claims+unpaid+(p['claim'] if y==p['claim_year'] else 0.)
  if failed:due+=p['failure_cost']
  # parent actual new borrowing must count at group, no separate source of value.
  step=cash_step(cash,fcf+fin_income+release+restricted_release+pc['draw']+issue_cash,due,effective_rev*.055,debt-amort+pc['draw'],p['debt_limit'],pc['distribution'],blocked=failed or pc['unpaid']>1e-9)
  cash=step['cash'];debt=step['debt'];unpaid=step['unpaid']
  if step['distribution']<pc['distribution']:
   # cancel parent proposal not actually paid; keep cash and legal earnings at parent
   restore=pc['distribution']-step['distribution'];parent_cash+=restore;parent_re+=restore
  if unpaid+unpaid_parent>1e-9:failed=True
  dist=step['distribution'];historical+=dist/(shares-TREASURY_SHARES)
  # All outstanding forecast awards are new issuance (no treasury share double benefit).
  assert abs(opening_cash+ownership_cash_bridge+fcf+fin_income+release+restricted_release+pc['draw']+step['draw']+issue_cash-step['senior_paid']-dist-cash)<1e-7
  rows.append({'year':y,'budget_year':2026+y,'segments':segments,'opening_cash':opening_cash,'opening_debt':opening_debt,'ownership_cash_bridge':ownership_cash_bridge,'auto_future_interest':future_auto,'effective_revenue':effective_rev,'owner_nopat':earn,'cash_interest':interest,'depreciation':da,'cash_capex':capex,'opening_nwc':opening_nwc,'closing_nwc':nwc,'delta_nwc':delta,'owner_fcf_before_finance':fcf,'financial_income_after_tax':fin_income,'investment_book_realized':inv_book,'investment_tax':inv_tax,'investment_fees':inv_fees,'investment_cash_realization':release,'remaining_investment_book':invest,'restricted_cash_release':restricted_release,'parent_subsidiary_budgets':subdata,'parent_opening_cash':opening_parent_cash,'parent_own_after_tax_profit':own_parent,'upstream_cash':upstream,'old_dividend_receipt_no_profit':oldreceipt,'parent_profit':parent_profit,'parent_exit_cash':parent_exit_cash,'parent_exit_book_removed':parent_exit_book,'parent_after_tax_disposal_profit':parent_disposal_profit,'parent_exit_tax':inv_tax*parent_exit_fraction,'parent_exit_fees':inv_fees*parent_exit_fraction,'group_borrowing_headroom_before_parent':group_headroom,'parent_reserve_addition':reserve_add,'parent_legal_re_budget':parent_re,'parent_cash':parent_cash,'parent_debt':parent_debt,'parent_internal_runoff':internal_runoff,'parent_new_borrowing':pc['draw'],'parent_unpaid':pc['unpaid'],'debt_amortization_due':amort,'existing_noncurrent_claims_payment_due':existing_claims,'senior_claim_due':due,'senior_claim_paid':step['senior_paid'],'unpaid_senior_claims':unpaid+unpaid_parent,'group_external_unpaid':unpaid,'parent_separate_unpaid':unpaid_parent,'new_borrowing':step['draw'],'closing_debt':debt,'closing_cash':cash,'proposed_dividend':proposed,'actual_distribution':dist,'shares':shares,'new_shares':issue7+issue8+issue6,'issue_cash':issue_cash,'dividend_eligible_shares':shares-TREASURY_SHARES,'distribution_per_share':dist/(shares-TREASURY_SHARES),'feasible':not failed})
 if failed:
  pv=tv=tv5=tvshare=None;tvcontrib=None
 else:
  # year11 normalized owner earnings, sustainable reinvestment g/ROIC, debt-free after amortization.
  terminal_cashflow=rows[-1]['owner_nopat']*(1+p['g'])*(1-p['g']/p['roic'])
  op=terminal_cashflow/(p['r']-p['g'])
  surplus=cash-rows[-1]['effective_revenue']*.055
  # Excess capital realized as lawful special dividends over years 11-13; 2% leakage and 3-year delay.
  capital_realization_pv=(surplus+held+invest*p['invest_recovery'])*(1-p['capital_leakage'])/(1+p['r'])**p['capital_delay']
  tv=op+capital_realization_pv-debt-unpaid
  pv=sum(x['distribution_per_share']/(1+p['r'])**x['year'] for x in rows)+tv/shares/(1+p['r'])**10
  tv5=sum(x['distribution_per_share']/(1+p['r'])**(x['year']-5) for x in rows[5:])+tv/shares/(1+p['r'])**5
  tvshare=tv/shares;tvcontrib=(tv/shares/(1+p['r'])**10)/pv
 return {'identity':IDENTITY,'parameters':p,'units':'CNY billion except per-share CNY; billion shares','opening':{'cash_economic_common_interest':OPEN_CASH,'restricted_cash_not_lost':1.4,'debt_economic_common_interest':OPEN_DEBT,'nwc_common_interest':OPEN_NWC,'investment_common_net_partner_claims':INVEST_BOOK},'years':rows,'feasible':not failed,'pv_per_share':pv,'terminal_equity_value':tv,'terminal_per_share':tvshare,'year5_terminal_per_share':tv5,'terminal_pv_share':tvcontrib,'historical_distributions_received_per_share':historical,'unpaid_senior_claims':unpaid+unpaid_parent,'group_external_unpaid':unpaid,'parent_separate_unpaid':unpaid_parent}

def method2():
 # Independently specified normalized earning power; no five-year high growth, no historic-price multiples.
 # 2028 sustainable revenue bn [33,24,4,1], EBIT after R&D, bad debt and overhead [23%,3%,7%,6%].
 out=[]
 for r,tax,maint in [(.105,.18,.55),(.095,.15,.35)]:
  earning=(33*.23+24*.03*AUTO+4*.07+1*.06)*(1-tax)-.025
  cashpower=earning-maint # maintenance above accounting depreciation, constant real scale
  necessary_cash=(33+24*AUTO+4+1)*.055
  v=(cashpower/r+OPEN_CASH+1.4-necessary_cash-OPEN_DEBT+INVEST_BOOK*.80-(.61577705120-(1-AUTO)*.59109205054+.01428997314+.000749936+.00291325871))/(SHARES)
  out.append({'r':r,'tax':tax,'normalized_owner_profit':earning,'maintenance_above_da':maint,'cash_earning_power':cashpower,'necessary_operating_cash':necessary_cash,'value_per_share':v})
 return out


import importlib.util,sys,stat,os
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
CODE='300124'
CHECKER_NAME='2026-Q3-capital-20261102-check.py'
CHECKER_SHA='e658cbf439dcfbc95cdb3478fd47bb6461e1a4d2dee080c1dbae4c3ae307ce81'
EVENT={'deduction': 'Full listed-parent payment; not multiplied by automotive minority interest', 'fees': 'Source transaction amount does not state inclusion of fees', 'full_treasury_after': '3985992', 'full_treasury_before': '3566367', 'holder_policy': 'Annual distribution excludes treasury; terminal uses original conservative fully reissued shares; registered shares not cancelled', 'paid_transaction_oct30': '179221269.54', 'paid_transaction_q3': '161868304.60', 'post_q3_cash': '17352964.94', 'source_ids': ['1225596797', '1225652002'], 'treasury_increment': '419625'}
OUTPUT_META={'classification': 'NEW_RECONSTRUCTION_NOT_OLD189_BYTE_RECOVERY', 'event': {'deduction': 'Full listed-parent payment; not multiplied by automotive minority interest', 'fees': 'Source transaction amount does not state inclusion of fees', 'full_treasury_after': '3985992', 'full_treasury_before': '3566367', 'holder_policy': 'Annual distribution excludes treasury; terminal uses original conservative fully reissued shares; registered shares not cancelled', 'paid_transaction_oct30': '179221269.54', 'paid_transaction_q3': '161868304.60', 'post_q3_cash': '17352964.94', 'source_ids': ['1225596797', '1225652002'], 'treasury_increment': '419625'}, 'event_asof': '2026-11-02', 'event_input_sha256': '7a51b2b67020b43752ee6627bf58ab829e3be8f24f141f752323cfd3bb2a2565', 'historical_field_roles': {}, 'old_diagnostics_are_historical_not_updated': True, 'operating_forecast_recomputed': False, 'original_baseline_sha256': '45610705440e047c92dd1d23a4d18b2a3292a23a4bd4f080c46ae3da2ab31cf3', 'period': '2026-Q3', 'scope': '3 core x10 cash +2 original auxiliary endpoints; other16 historical', 'scope_note': 'Original full company forecast dispatcher not executed; operating rows reused. Original finite terminal/NOPAT and normalized earning-power formulas are evaluated where required for selected cash valuation, not called new researched forecasts.', 'symbol': 'CN:300124', 'public_delivery_note': 'New reconstruction of selected current cash from exact published operating budgets. Old unselected diagnostics remain historical. This is not recovery of the lost original189 bytes.'}

def selected_cash(old,event,changed):
    m=sys.modules[__name__]
    delta = float(event['post_q3_cash'])/1e9 if changed else 0.
    m.EVENT_DELTA_CASH = delta
    m.OPEN_CASH -= delta
    if changed:
        m.TREASURY_SHARES = float(event['full_treasury_after'])/1e9
    result = {'cases': {}, 'auxiliary': None}
    for name in ('base', 'core_low', 'core_high'):
        saved = old['scenarios'][name]
        m.CACHE_ROWS = saved['years']
        result['cases'][name] = m.run(copy.deepcopy(saved['parameters']))
    result['auxiliary'] = m.method2()
    oracle = {'cases': {k: old['scenarios'][k] for k in result['cases']}, 'auxiliary': old['method2']}
    projection = result
    scope = '3 core x10 cash +2 original auxiliary endpoints; other16 historical'

    return result,projection,oracle,scope
