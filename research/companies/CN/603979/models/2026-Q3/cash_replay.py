from pathlib import Path
import argparse,base64,gzip,hashlib,io,json,math,stat,sys
if sys.flags.optimize:raise RuntimeError('Assertions must be enabled; do not use -O')
def read_regular(path,limit):
 s=path.lstat();assert stat.S_ISREG(s.st_mode)and not path.is_symlink()and s.st_nlink==1 and s.st_size<=limit
 b=path.read_bytes();assert len(b)==s.st_size;return b
def load_json(raw):
 def unique(pairs):
  d={}
  for k,v in pairs:
   if k in d:raise ValueError('duplicate key')
   d[k]=v
  return d
 return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def encode(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
BASELINE_SHA='4c6e93afdeb56ffbf5963c4e0f97074cb9175f9b3520b07d7c51e4e75175ab6c'
EXPECTED_OUTPUT_SHA='21faaf755c4de34daa1ce91783782eab3eab1a7ef5293e0b14d2fc7e431a7c16'
OLD_CHECKS={'base': {'status': 'PASS', 'numeric_comparisons': 9091, 'max_abs': 0.0, 'relative_tolerance': 1e-11}, 'base_aux': {'status': 'PASS', 'numeric_comparisons': 5, 'max_abs': 0.0, 'relative_tolerance': 1e-11}, 'core_low': {'status': 'PASS', 'numeric_comparisons': 9091, 'max_abs': 0.0, 'relative_tolerance': 1e-11}, 'core_low_aux': {'status': 'PASS', 'numeric_comparisons': 5, 'max_abs': 0.0, 'relative_tolerance': 1e-11}, 'core_high': {'status': 'PASS', 'numeric_comparisons': 9091, 'max_abs': 0.0, 'relative_tolerance': 1e-11}, 'core_high_aux': {'status': 'PASS', 'numeric_comparisons': 5, 'max_abs': 0.0, 'relative_tolerance': 1e-11}, 'Y5_core_low': {'status': 'PASS', 'numeric_comparisons': 9091, 'max_abs': 0.0, 'relative_tolerance': 1e-11}, 'Y5_core_high': {'status': 'PASS', 'numeric_comparisons': 9091, 'max_abs': 0.0, 'relative_tolerance': 1e-11}}
SUMMARY_CONSTANTS={'status': 'CURRENT_CASH_BRIDGE_COMPLETE', 'all_unaffected_operating_rows_reused': True, 'shares_billion': 0.668381217647482, 'current_plan_paid_bCNY': 0.2186609, 'remaining_selected_budget_bCNY': 0.1313391, 'no_original_model_import_or_execution': True, 'no_financial_input_tuning': True, 'not_legal_or_forecast_certainty': True}
SUMMARY_KEYS=['status', 'old_replication', 'new_cases', 'conditional_Y5', 'base_D', 'all_unaffected_operating_rows_reused', 'shares_billion', 'current_plan_paid_bCNY', 'remaining_selected_budget_bCNY', 'no_original_model_import_or_execution', 'no_financial_input_tuning', 'not_legal_or_forecast_certainty']
SCOPE={'company': 'CN:603979', 'original_operating_information_cutoff': '2026-10-26T23:00:00Z', 'opening_group_cash_as_of': '2026-09-30', 'capital_fact_through': '2026-10-31', 'capital_announcement_read_on': '2026-11-02', 'current_cash_paths': 5, 'original_mine_service_generation': False, 'historical_other_diagnostics_not_updated': 25, 'paid_billion_CNY': 0.2186609, 'remaining_selected_budget_billion_CNY': 0.1313391, 'total_selected_budget_billion_CNY': 0.35, 'shares_unchanged': True, 'same_base_D_and_Y5': True}
"""Cash-only projection over immutable operating rows; no mine/service execution.
All amounts billion CNY. Five original cash functions are unchanged.
"""
import copy, math

OWN={'Dikulushi':.90,'Lonshi':.95,'Lubambe':.80,'Alacran':.975,'Phosphate':.90}
CASH_KEYS=('cash','debt','parent_cash','parent_re','parent_reserve','parent_loan',
           'parent_div_receivable','source_profit_budget')
PAID=.2186609
BUDGET=.35

def cash_step(old,p,opening,corrected):
    """One original annual cash waterfall; operating rows are read-only inputs."""
    t=old['year'];s=copy.deepcopy(opening);start=copy.deepcopy(s)
    rev=old['service']['revenue'];operation=old['common_operating_cash']
    buyback=(BUDGET-PAID if corrected else BUDGET) if t==1 else 0.
    contingency=old['emr_contingent_payment']
    bond=min(s['debt'],1.99977) if t<=5 else 0.
    coupon=[.003,.006,.010,.015,0.][t-1]*bond if t<=5 else 0.
    interest=max(0.,s['debt']-bond)*.052+coupon
    free=operation-interest-buyback-contingency-.08
    s['cash']+=free
    liquidity=1.20+rev*.08
    due=1.10 if t==1 else (.65 if t in (2,3) else (2.2397424 if t==5 else .30))
    floor=1.99977 if t<5 else 0.
    due=min(due,max(0.,s['debt']-floor))
    premium=.2399724 if t==5 else 0.
    s['cash']-=premium
    draw=max(0.,liquidity+due-s['cash']);capacity=max(0.,p['credit']-s['debt'])
    feasible=draw<=capacity+1e-9
    funded=min(draw,capacity);s['debt']+=funded;s['cash']+=funded
    pay=min(due,max(0.,s['cash']-liquidity));s['debt']-=pay;s['cash']-=pay
    if pay+1e-8<due:feasible=False
    extra=min(max(0.,s['debt']-floor),max(0.,s['cash']-liquidity)*(.50 if t<=5 else .80))
    s['debt']-=extra;s['cash']-=extra
    s['parent_cash']-=.08
    if corrected:s['parent_cash']-=buyback
    ordinary=max(0.,operation)*p['upstream']
    surplus=max(0.,start['cash']-start['parent_cash']-(1.20+start['service_revenue']*.08-.25))
    stored=surplus*p['stored_release'] if t>5 else 0.
    capacity=ordinary+stored
    upstream=min(capacity,max(0.,s['cash']-s['parent_cash']-(liquidity-.25)),s['parent_div_receivable']+s['parent_loan'])
    settle=min(upstream,s['parent_div_receivable']);s['parent_div_receivable']-=settle
    loan_return=min(upstream-settle,s['parent_loan']);s['parent_loan']-=loan_return
    source_profit=old['service']['ebit']*.75+sum((m['ebit']-m['tax_assessed'])*OWN[m['name']]for m in old['mines'])
    s['source_profit_budget']+=source_profit
    declared=min(max(0.,s['source_profit_budget']),capacity);s['source_profit_budget']-=declared
    s['parent_div_receivable']+=declared
    profit=declared-.08
    loss=min(max(0.,-s['parent_re']),max(0.,profit))
    reserve=min(max(0.,profit-loss)*.10,max(0.,.5*s['parent_registered']-s['parent_reserve']))
    s['parent_reserve']+=reserve;s['parent_re']+=profit-reserve;s['parent_cash']+=upstream
    desired=[.60,.70,.80,1.00,1.20][t-1]*p['_shares'] if t<=5 else max(0.,s['cash']-liquidity)*.90
    distribution=min(desired,max(0.,s['cash']-liquidity),max(0.,s['parent_cash']-.25),max(0.,s['parent_re'])) if feasible else 0.
    s['cash']-=distribution;s['parent_cash']-=distribution;s['parent_re']-=distribution
    if s['parent_cash']>s['cash']+1e-8 or s['parent_cash']<.25-1e-8 or s['cash']<liquidity-1e-8:feasible=False
    # Reuse all original physical operating state, replacing only cash-rights state.
    ending=copy.deepcopy(old['ending']);ending.update({k:s[k]for k in CASH_KEYS})
    row=copy.deepcopy(old)
    row.update(opening=start,ending=ending,interest=interest,bond_coupon=coupon,bank_interest=interest-coupon,buyback=buyback,
      borrow=funded,scheduled_debt_repayment=pay,extra_debt_repayment=extra,
      ordinary_upstream_capacity=ordinary,opening_foreign_surplus=surplus,stored_release_capacity=stored,
      upstream_cash=upstream,parent_receivable_cash=settle,parent_loan_principal_return=loan_return,
      parent_dividend_cash=settle,parent_dividend_declared=declared,parent_profit=profit,
      parent_reserve_allocation=reserve,parent_loss_makeup=loss,distribution=distribution,
      distribution_per_share=distribution/p['_shares'],feasible=feasible,
      cash_conservation_error=s['cash']-(start['cash']+free+funded-pay-extra-distribution-premium))
    assert abs(row['cash_conservation_error'])<1e-8
    assert abs(s['parent_cash']-(start['parent_cash']-.08-(buyback if corrected else 0.)+upstream-distribution))<1e-8
    assert row['mines']==old['mines'] and row['service']==old['service'] and row['common_operating_cash']==old['common_operating_cash']
    return row

def replay(path,shares,corrected=False,prefix=None):
    p=copy.deepcopy(path['parameters']);p['_shares']=shares
    rows=copy.deepcopy(prefix or [])
    start=copy.deepcopy(rows[-1]['ending'] if rows else path['years'][0]['opening'])
    if corrected and not rows:
        start['cash']-=PAID;start['parent_cash']-=PAID
        assert start['cash']>=start['parent_cash']>=.25
    for old in path['years'][len(rows):]:
        row=cash_step(old,p,start,corrected);rows.append(row);start=row['ending']
        if not row['feasible']:
            return {'status':'infeasible','failure':f"year_{row['year']}_finite_finance_or_parent_cash",'years':rows,
              'pv_per_share':None,'terminal_year5_per_share':None,'terminal_year30':None,'state':start}
    assert len(rows)==30,'Incomplete stored operating path; do not extrapolate or run producer'
    s=start;rev=s['service_revenue'];nr=rev*(1+p['g'])
    nextfcf=nr*p['service_margin']*.75-(nr-rev)*(.25+.40+.08)-.08*(1+p['g'])
    stock=p['stored_release']/(p['r']+p['stored_release']) if p['stored_release']>0 else 0.
    flow=(min(1.,p['upstream'])+(1-min(1.,p['upstream']))*stock)/(1+p['r'])**p['terminal_delay']
    op=nextfcf/(p['r']-p['g'])*flow
    excess=max(0.,s['cash']-(1.20+rev*.08))
    realizable=min(excess,max(0.,s['parent_re'])+max(0.,s['source_profit_budget'])+s['parent_div_receivable']+s['parent_loan'])
    obligations=s['debt']+s['zccm']+s['emr_contingent']+sum(x['tax_payable']for x in s['pools'].values())
    terminal=op+realizable*stock/(1+p['r'])**p['terminal_delay']-obligations
    pv=sum(y['distribution']/(1+p['r'])**y['year']for y in rows)+terminal/(1+p['r'])**30
    tv5=sum(y['distribution']/(1+p['r'])**(y['year']-5)for y in rows if y['year']>5)+terminal/(1+p['r'])**25
    tail={'operating_service':op,'undelayed_service_value':nextfcf/(p['r']-p['g']),'excess_cash':excess,
      'realizable_excess_cash':realizable,'realization_delay_years':p['terminal_delay'],'stock_release_rate':p['stored_release'],
      'stock_realization_factor':stock,'continuing_flow_factor':flow,'realized_cash_value':realizable*stock/(1+p['r'])**p['terminal_delay'],
      'retained_unrealizable_cash':excess-realizable,'obligations':obligations,'equity':terminal}
    return {'status':'feasible','failure':None,'years':rows,'pv_per_share':pv/shares,
      'terminal_year5_per_share':tv5/shares,'terminal_year30':tail,'state':s}


def auxiliary(path,result,shares,original_opening_cash,original_opening_debt,corrected):
    if result['status']!='feasible':return None
    r=path['parameters']['r']
    asset=sum((y['common_operating_cash']-.08-y['emr_contingent_payment']-y['buyback']-y['redemption_premium'])/(1+r)**y['year']for y in result['years'])
    operating_tail=result['terminal_year30']['undelayed_service_value']/(1+r)**30
    cash=original_opening_cash-(PAID if corrected else 0.)
    return {'operating_cash_pv':asset,'service_tail_pv':operating_tail,'opening_common_cash':cash,
      'financial_debt_excluding_project_zccm':original_opening_debt,
      'equity_per_share':(asset+operating_tail+cash-original_opening_debt)/shares,
      'meaning':'unlevered asset cash discounted at equity hurdle, debt settled now, no parent remittance lag; upper cross-check not final distributable-holder value'}

def formal_handcases():
    """Synthetic constants are independent of original company outputs."""
    state={'cash':5.,'parent_cash':2.,'debt':0.,'parent_re':10.,'parent_reserve':.5,'parent_registered':1.,
      'parent_loan':0.,'parent_div_receivable':0.,'source_profit_budget':0.,'service_revenue':0.,
      'zccm':0.,'emr_contingent':0.,'pools':{}}
    old={'year':1,'service':{'revenue':0.,'ebit':0.},'common_operating_cash':0.,'emr_contingent_payment':0.,
      'mines':[],'ending':copy.deepcopy(state)}
    p={'credit':0.,'upstream':0.,'stored_release':.25,'_shares':1.}
    a=cash_step(old,p,state,False)
    assert abs(a['ending']['cash']-3.97)<1e-12 and abs(a['ending']['parent_cash']-1.32)<1e-12
    # New total remains350m:218.6609m paid initially +131.3391m inyear1.
    s=copy.deepcopy(state);s['cash']-=PAID;s['parent_cash']-=PAID
    b=cash_step(old,p,s,True)
    assert abs(PAID+b['buyback']-.35)<1e-12
    assert abs(b['ending']['cash']-3.97)<1e-12 and abs(b['ending']['parent_cash']-.97)<1e-12
    assert b['distribution_per_share']==.6 and b['ending']['parent_re']==a['ending']['parent_re']
    # Low parent cash constrains D; equity repurchase is not an earnings expense.
    s=copy.deepcopy(state);s['parent_cash']=.8-PAID;s['cash']-=PAID
    c=cash_step(old,p,s,True)
    assert abs(c['distribution']-.12)<1e-12 and abs(c['ending']['parent_cash']-.25)<1e-12
    assert abs(c['ending']['parent_re']-(10.-.08-.12))<1e-12
    # Group insolvency flag is distinct from a merely lower discretionary D.
    s=copy.deepcopy(state);s['cash']=.1;s['parent_cash']=.05
    d=cash_step(old,p,s,False);assert not d['feasible'] and d['distribution']==0.
    # One-year isolated timing formula, not a substitute for company constraints.
    r=.1;assert abs((-PAID+PAID/(1+r))-(-PAID*r/(1+r)))<1e-14
    return {'status':'PASS','groups':6,'formal_cash_step_called':True,'company_inputs_used':False}
