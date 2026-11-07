#!/usr/bin/env python3
"""CN:300124 深圳市汇川技术股份有限公司; CNY bn, bn shares.
Economic common-interest budget, NOT subsidiary statutory statements.
stdlib only; python model.py --out output.json. No network, price, repo/state writes.
"""
import json,math,copy,argparse,pathlib
IDENTITY={'symbol':'CN:300124','name':'深圳市汇川技术股份有限公司','period':'2026-Q3'}
AUTO=2/2.441731160
SHARES=2.711067851
# 9/30 working capital incl accruals, endorsed receivables paired with obligations.
OPEN_ASSETS={'receivable_notes':5.32878475815,'receivable_accounts':13.33346580955,'receivable_financing':3.25065559237,'inventory':12.45814369716,'prepay':.70719286410,'contract':.07008380242,'other_current':.90764778674,'other_receivable':.08852489222}
OPEN_LIAB={'trade_notes':9.41703644482,'trade_payables':15.17031033890,'advance':.00143483149,'contract':1.05281979070,'payroll':1.11630211133,'tax':.69693922849,'other_payable':1.00772690972,'other_current':2.47789083639}
OPEN_AUTO_NWC=(1.10853852319+5.78253428177+.93022099260+5.06457024580+.035616613+.01644464513+.31345597922+.02413395069)-(4.91809942048+8.6431132467+.00077251835+.0900294145+.35163781694+.2031289526+.47232621392+.89426644675)
OPEN_NWC=sum(OPEN_ASSETS.values())-sum(OPEN_LIAB.values())-(1-AUTO)*OPEN_AUTO_NWC
# Long deposits estimated from Q3 other noncurrent minus H1 noncash components.
LIQ_GROSS=6.11774603506+2.88814033572+3.97137282189+(4.30421957769-.924)
AUTO_LIQ=2.40302543223+2.10500383562+.52220289039+.75
OPEN_CASH=LIQ_GROSS-(1-AUTO)*AUTO_LIQ-1.4 # pledged/operating restriction reserve retained, not worthless
OPEN_DEBT=.55047696978+1.34337002006+1.07762025839+.20428499029-(1-AUTO)*(.09341929328+.82999247317+.08964571596)
INVEST_BOOK=2.32681209910+3.48365106216-1.316-.17 # partnership debt claims distinct from NCI
BASE={'label':'Base','r':.10,'g':.025,'roic':.16,'auto_owner':AUTO,'margin_shift':0.,'growth_shift':0.,'nwc_extra':0.,'capex_extra':0.,'remit_factor':1.,'parent_runoff':.5,'claim':0.,'claim_year':1,'invest_recovery':.85,'invest_years':[5,9],'debt_limit':4.,'dividend_factor':1.,'tax':.15,'other_minority':.025,'special':False,'support_all_auto':False,'failure_cost':0.,'exercise':True,'capital_delay':3,'capital_leakage':.02}
def params(**kw):
 p=copy.deepcopy(BASE);p.update(kw);return p
SCENARIOS={
 'base':params(),
 'core_low':params(label='核心下端',r=.105,g=.02,roic=.15),
 'core_high':params(label='核心上端',r=.095,g=.025,roic=.17),
 'cyclical':params(label='周期性弱',special='cycle',r=.105,capex_extra=.3),
 'structural':params(label='结构性不利',special='structural',r=.115,g=.01,roic=.10,invest_recovery=.65),
 'upside':params(label='兑现较好',special='upside',r=.095,g=.03,roic=.18),
 'collection_delay':params(label='额外30天回款占用',nwc_extra=30/365),
 'parent_remit_delay':params(label='母公司上划延后两年',special='remit_delay',parent_runoff=1.),
 'no_deposit_release':params(label='存款解除限制推迟',special='deposit_delay'),
 'auto_full_support':params(label='母公司独担汽车再投资',support_all_auto=True),
 'tax_normalization':params(label='经营税率25%',tax=.25),
 'investment_delay':params(label='投资退出延后',invest_years=[8,10],invest_recovery=.65),
 'capital_intensive':params(label='每年另增十亿元资本需求',capex_extra=1.),
 'margin_erosion':params(label='全期毛利率低2个百分点',margin_shift=-.02),
 'capital_delay':params(label='超额资本延后八年且损耗20%',capital_delay=8,capital_leakage=.20),
 'no_exercise':params(label='激励全部未行权',exercise=False),
 'buyer_guarantee':params(label='买方信贷20%损失',claim=.925765*.2),
 'no_financing_parent_stress':params(label='集团零新增融资且母公司内部偿付压力',parent_runoff=5.,debt_limit=0.),
 'failure':params(label='客户与担保系统性失败',claim=60.,claim_year=2,debt_limit=0.,failure_cost=2.,special='structural')}
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
 parent_cash=.332784296+3.0;parent_debt=1.225859188;parent_re=8.19165228829;parent_res=1.3549350945
 parent_old_div=.12;sub_losses={'苏州汇川技术有限公司':0.,'苏州汇川控制技术有限公司':0.}
 shares=SHARES;rows=[];failed=False;unpaid=0.;unpaid_parent=0.;invest=INVEST_BOOK;historical=0.;held=1.4
 for y in range(1,11):
  opening_cash=cash;opening_debt=debt;opening_nwc=nwc;opening_parent_cash=parent_cash;opening_shares=shares
  growth=[max(.035,.17-.014*(y-1)),max(.025,.10-.008*(y-1)),max(.04,.24-.022*(y-1)),.025]
  gm=[.405-.001*y,.13+min(y,5)*.006,.29,.30]
  rd=[.092,.065,.105,.08];sg=[.077,.033,.095,.11];imp=[.009,.020,.012,.01]
  if p['special']=='cycle' and y<=3:
   growth=[-.05,.00,.05,0.] if y==1 else [.05,.04,.08,.01];gm=[x-.025 for x in gm]
  if p['special']=='structural':growth=[.03,0.,.04,0.];gm=[.35,.105,.24,.26];imp=[.016,.04,.025,.02];rd=[.10,.07,.11,.08]
  if p['special']=='upside':growth=[x+.04 if y<=5 else x for x in growth];gm=[.42,.165,.32,.31]
  growth=[x+p['growth_shift'] for x in growth];gm=[x+p['margin_shift'] for x in gm]
  issue7=([.005996920,.007287125,.007287125][y-1] if y<=3 else 0.)
  issue8=(.0442164/4 if y<=4 else 0.)
  issue6=(.003091382 if y==1 else 0.)
  reserve7=([.001020160,.000769200,.000769200][y-1] if y<=3 else 0.)
  issue7+=reserve7
  if not p['exercise'] or p['special']=='structural' or (p['special']=='cycle' and y<=2):issue7=issue8=issue6=0.
  # Future receipt only when forecast issuance occurs; announced grant is not current cash.
  issue_cash=issue6*59.40+issue7*41.96+issue8*((.0127686*39.41+.0314478*56.30)/.0442164)
  shares+=issue7+issue8+issue6
  prevrev=rev[:];rev=[a*(1+b) for a,b in zip(rev,growth)]
  future_auto=(2/(2.441731160+.039603750) if p['exercise'] and p['special']!='structural' else p['auto_owner'])
  ownership_cash_bridge=0.
  if y==1 and future_auto!=AUTO:
   dilution=AUTO-future_auto
   ownership_cash_bridge=-dilution*AUTO_LIQ+future_auto*.039603750*2.857
   cash+=ownership_cash_bridge
   debt-=dilution*(.09341929328+.82999247317+.08964571596)
   opening_nwc-=dilution*OPEN_AUTO_NWC
  owner=[1.,future_auto,1.,1.];segments=[];earn=0.;fcf=0.;capex=0.;da=0.;gross_earn=0.
  for j in range(4):
   extra_depreciation=extra_assets[j]*.10
   ebit=rev[j]*(gm[j]-rd[j]-sg[j]-imp[j])-extra_depreciation;tax=max(ebit,0.)*p['tax'];np=ebit-tax
   dep=assets[j]*.10;growthcap=max(rev[j]-prevrev[j],0.)*[.16,.25,.25,.15][j]
   # existing CIP already paid; only future incremental capital, plus completion cash in first 2 years
   completion=([.30,.55,.10,.05][j] if y<=2 else 0.)
   cp=dep+growthcap+completion+p['capex_extra']/4
   assets[j]+=cp-dep;extra_assets[j]+=p['capex_extra']/4
   funding=1. if p['support_all_auto'] and j==1 else owner[j]
   earn+=np*owner[j];gross_earn+=np;capex+=cp*funding;da+=dep*owner[j]
   segments.append({'business':['自动化电梯','联合动力经济集团','机器人数字能源','其他'][j],'revenue':rev[j],'growth':growth[j],'gross_margin':gm[j],'rd':rev[j]*rd[j],'selling_admin':rev[j]*sg[j],'impairment':rev[j]*imp[j],'ebit':ebit,'cash_tax':tax,'nopat':np,'economic_interest':owner[j],'capital_funding_interest':funding,'depreciation':dep,'extra_depreciation':extra_depreciation,'extra_capital_stock':extra_assets[j],'future_cash_capex':cp,'closing_fixed_capital':assets[j]})
  earn-=p['other_minority'];effective_rev=sum(a*b for a,b in zip(rev,owner))
  # Long-run trade credit maintained, but positive common NWC; no guaranteed old inventory release.
  nwc_ratio=.13 if y<=2 else .12
  if p['special']=='structural':nwc_ratio=.20
  if p['special']=='cycle' and y<=2:nwc_ratio=.18
  nwc=effective_rev*(nwc_ratio+p['nwc_extra'])
  delta=nwc-opening_nwc;interest=debt*.045
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
  dist=step['distribution'];historical+=dist/(shares-.003566367)
  # All outstanding forecast awards are new issuance (no treasury share double benefit).
  assert abs(opening_cash+ownership_cash_bridge+fcf+fin_income+release+restricted_release+pc['draw']+step['draw']+issue_cash-step['senior_paid']-dist-cash)<1e-7
  rows.append({'year':y,'budget_year':2026+y,'segments':segments,'opening_cash':opening_cash,'opening_debt':opening_debt,'ownership_cash_bridge':ownership_cash_bridge,'auto_future_interest':future_auto,'effective_revenue':effective_rev,'owner_nopat':earn,'cash_interest':interest,'depreciation':da,'cash_capex':capex,'opening_nwc':opening_nwc,'closing_nwc':nwc,'delta_nwc':delta,'owner_fcf_before_finance':fcf,'financial_income_after_tax':fin_income,'investment_book_realized':inv_book,'investment_tax':inv_tax,'investment_fees':inv_fees,'investment_cash_realization':release,'remaining_investment_book':invest,'restricted_cash_release':restricted_release,'parent_subsidiary_budgets':subdata,'parent_opening_cash':opening_parent_cash,'parent_own_after_tax_profit':own_parent,'upstream_cash':upstream,'old_dividend_receipt_no_profit':oldreceipt,'parent_profit':parent_profit,'parent_exit_cash':parent_exit_cash,'parent_exit_book_removed':parent_exit_book,'parent_after_tax_disposal_profit':parent_disposal_profit,'parent_exit_tax':inv_tax*parent_exit_fraction,'parent_exit_fees':inv_fees*parent_exit_fraction,'group_borrowing_headroom_before_parent':group_headroom,'parent_reserve_addition':reserve_add,'parent_legal_re_budget':parent_re,'parent_cash':parent_cash,'parent_debt':parent_debt,'parent_internal_runoff':internal_runoff,'parent_new_borrowing':pc['draw'],'parent_unpaid':pc['unpaid'],'debt_amortization_due':amort,'existing_noncurrent_claims_payment_due':existing_claims,'senior_claim_due':due,'senior_claim_paid':step['senior_paid'],'unpaid_senior_claims':unpaid+unpaid_parent,'group_external_unpaid':unpaid,'parent_separate_unpaid':unpaid_parent,'new_borrowing':step['draw'],'closing_debt':debt,'closing_cash':cash,'proposed_dividend':proposed,'actual_distribution':dist,'shares':shares,'new_shares':issue7+issue8+issue6,'issue_cash':issue_cash,'dividend_eligible_shares':shares-.003566367,'distribution_per_share':dist/(shares-.003566367),'feasible':not failed})
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

def selftest():
 a=cash_step(10,2,3,2,0,0,4);assert a['cash']==5 and a['distribution']==4
 b=cash_step(1,0,3,0,0,0,1);assert b['unpaid']==2 and b['distribution']==0
 c=reserve_profit(-5,3,9,0,10);assert c==(-2,0,0,0)
 d=reserve_profit(-5,7,9,0,10);assert d==(0.,.2,1.8,.2)
 e=run(SCENARIOS['failure']);assert e['pv_per_share'] is None and e['year5_terminal_per_share'] is None and e['terminal_equity_value'] is None
 failure=next(x['year'] for x in e['years'] if not x['feasible']);assert all(x['actual_distribution']==0 for x in e['years'][failure-1:]);assert e['unpaid_senior_claims']>0
 f=run(SCENARIOS['base']);assert f['feasible'];assert all(x['parent_cash']>=.25-1e-8 for x in f['years']);assert len(f['years'])==10
 h=run(params(parent_runoff=5.,debt_limit=0.));assert all(z['parent_new_borrowing']==0 and z['new_borrowing']==0 for z in h['years']);assert not h['feasible'] and h['pv_per_share'] is None
 i=investment_exit(2.,.8,1.);assert abs(i['cash']-1.418)<1e-12 and abs(i['after_tax_disposal_profit']+.582)<1e-12
 j=run(SCENARIOS['capital_intensive']);assert abs(sum(z['extra_depreciation'] for z in j['years'][-1]['segments'])-.9)<1e-12
 return {'no_financing_parent_gate':True,'investment_disposal_profit_not_principal':True,'maintained_extra_capital_stock':True,'cash_step_handcases':True,'loss_and_reserve_handcases':True,'production_failure_null_all_PV_TV':True,'no_distribution_after_first_unpaid':True,'all_year_cash_conservation':True}
def build():return {'identity':IDENTITY,'opening_assets':OPEN_ASSETS,'opening_liabilities':OPEN_LIAB,'auto_interest_latest':AUTO,'scenarios':{k:run(v) for k,v in SCENARIOS.items()},'method2':method2(),'selftests':selftest()}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',default=str(pathlib.Path(__file__).with_name('2026-Q3-output.json')));a=ap.parse_args();pathlib.Path(a.out).write_text(json.dumps(build(),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
