#!/usr/bin/env python3
"""CN:000902 新洋丰 2026-Q3. Standard library only. Amounts CNY billion.
Economic attribution pools are NOT legal entities or distributable-profit certification.
Run: python 2026-Q3.py. Default output is 2026-Q3-output.json beside this script. All forecasts are conditional research budgets.
"""
import argparse,copy,json,math
from pathlib import Path
SYMBOL='CN:000902'; NAME='新洋丰'; PERIOD='2026-Q3'; ASOF='2026-10-26T22:12:00+00:00'
SHARES=1.254734903
REGISTERED_CAPITAL=1.254733383 # H1 note III; registration date is not Q3 share register
BOND_BOOK=1.077891808; BOND_ACCRUED=.00500011696; BANK_ACCRUED=.00088690463
BOND_REDEMPTION=1.119891808
OPEN={'cash':1.36669537845,'restricted':.19069290298,'debt':3.29165317892,'wc':2.89649783646,'financial':.34581225994,'fixed':11.76932764466}
OPEN['wc']+=BOND_ACCRUED+BANK_ACCRUED
OPEN['debt']+=BOND_ACCRUED+BANK_ACCRUED
# H1 note27 carried as conditional Q3 accrued-interest split; not observed Q3 breakdown.
# debt includes current maturities and lease, not supplier/customer operating float.
# Redemption uplift over carrying amount is explicit, never additional principal.
BASE={'r':.10,'g':.01,'roic':.10,'attribution':.96,'margin_shift':0.,'volume_scale':[1]*10,
 'price_scale':[1]*10,'wc_ratio':[.14,.135,.13,.13,.13,.13,.13,.13,.13,.13],
 'capex':[2.4,2.1,1.8,1.4,1.20,1.22,1.24,1.26,1.28,1.30],
 'da':[.85,.90,.95,1.,1.05,1.07,1.09,1.11,1.13,1.15],
 'chem_sales':[1.5,1.85,2.2,2.55,2.8,2.9,3.,3.1,3.2,3.3],
 'chem_margin':[.06,.075,.085,.095,.10,.10,.10,.10,.10,.10],
 'mine_savings':[0,.04,.08,.12,.15,.12,.09,.06,.03,0],
 'parent_upstream_factor':1.,'parent_delay_years':0,'parent_extra_funding':[.2,.2,.1,0,0,0,0,0,0,0],
 'credit_limit':5.,'interest':.04,'tax':.25,'mincash':.8,
 'parent_opening_cash':.8,'parent_opening_retained':6.00465658864,'parent_opening_reserve':.54131279263,
 'dividend_ps':[.30,.35,.45,.60,.70,.80,.90,1.,1.05,1.10],
 'guarantee_loss':[0]*10,'extra_cost':[0]*10,'extra_wc':[0]*10,
 'financial_year':5,'financial_recovery':.90,'convert':False,'bond_premium':.042-BOND_ACCRUED,
 'terminal_margin_shift':0.,'terminal_cash_delay':0}
def operating(p,t):
 i=t-1
 # Tonnes in millions; prices in thousands CNY/tonne => billion CNY.
 growth=min(i,4); tail=max(i-4,0)
 vols=[3.15*1.025**growth*1.01**tail,1.70*1.07**growth*1.025**tail,1.30*1.01**i]
 prices=[2.50,3.15,3.30]
 revenues=[v*q*(1.01**max(i-1,0))*p['volume_scale'][i]*p['price_scale'][i] for v,q in zip(vols,prices)]
 margins=[.135,.25,.16]
 gross=sum(v*(m+p['margin_shift']) for v,m in zip(revenues,margins))
 fert=sum(revenues); chem=p['chem_sales'][i]; other=.5*1.01**i
 # Selling, administration, research, taxes and safety expenses retained in every scenario.
 opex=.06*fert+.05  # minimum corporate/safety cost; not switched off in loss paths.
 ebit=gross-opex+chem*p['chem_margin'][i]+other*.12+p['mine_savings'][i]-p['extra_cost'][i]
 return {'volumes_million_tonnes':vols,'fert_revenue':fert,'chem_revenue':chem,'other_revenue':other,'revenue':fert+chem+other,'gross_profit_fert':gross,'operating_expenses_fert':opex,'ebit':ebit}
def simulate(p):
 p=copy.deepcopy(p); a=p['attribution'];cash=OPEN['cash']*a;debt=(OPEN['debt']-BOND_BOOK-BOND_ACCRUED)*a+BOND_BOOK+BOND_ACCRUED;wc=OPEN['wc']*a
 fixed=OPEN['fixed']*a;restricted=OPEN['restricted']*a;fin=OPEN['financial']*a;shares=SHARES
 # Parent only: latest observed H1 cash 1.6804, retained 6.0047, statutory reserve .5413.
 # Q3 cash/working-cap movement is not published parent-only: opening cash .80 is a conditional budget,
 # NOT observed Q3 balance. Parent used .80-.30= .50 free liquidity; group cap applies independently.
 pcash=p['parent_opening_cash'];pretained=p['parent_opening_retained'];reserve=p['parent_opening_reserve'];pcap=REGISTERED_CAPITAL*.5
 mcash=OPEN['cash']*(1-a);mdebt=(OPEN['debt']-BOND_BOOK-BOND_ACCRUED)*(1-a)
 parent_bank_debt=0.
 rows=[];failed=None;historic=0.;pending_receivable=0.
 for t in range(1,11):
  i=t-1;o=operating(p,t);omcash=mcash;omdebt=mdebt;ocash=cash;odebt=debt;owc=wc;ofixed=fixed;opc=pcash;opr=pretained
  bond_accretion=p['bond_premium'] if t==1 and not p['convert'] else 0.
  bank_accrued_payment=BANK_ACCRUED*a if t==1 else 0.
  interest=(debt-(BOND_BOOK+BOND_ACCRUED+bank_accrued_payment if t==1 else 0.))*p['interest']+bond_accretion
  cash_interest=cash*.015
  taxable=o['ebit']*a-interest+cash_interest
  tax=max(taxable,0)*p['tax'] # no instant monetization of tax losses
  earnings=taxable-tax
  wc=(o['revenue']*p['wc_ratio'][i]+p['extra_wc'][i])*a
  dwc=wc-owc;capex=p['capex'][i]*a;da=p['da'][i]*a;fixed+=capex-da
  guarantee=p['guarantee_loss'][i] # wholly common obligation, not multiplied by a
  fcfe=earnings+da+bond_accretion-capex-dwc-guarantee
  release=restricted if t==2 else 0.;restricted-=release
  realization=fin*p['financial_recovery'] if t==p['financial_year'] else 0.
  if t==p['financial_year']:fin=0.
  redemption=BOND_REDEMPTION if t==1 and not p['convert'] else 0.
  principal_repaid=(BOND_BOOK+BOND_ACCRUED if redemption else 0.)+bank_accrued_payment
  conversion_principal=0.
  if t==1 and p['convert']:
   conversion_principal=BOND_BOOK+BOND_ACCRUED;debt-=conversion_principal
   shares+=.9999034/16.79 # no cash inflow for conversion, original owners diluted
   pcap=(REGISTERED_CAPITAL+.9999034/16.79)*.5 # conditional registration of new conversion shares; existing 1520-share timing difference retained
  debt-=principal_repaid
  before=cash+fcfe+release+realization-redemption-bank_accrued_payment
  # Contractual obligations paid before distributions; credit line is an estimated capacity, not bank commitment.
  borrowed=min(max(p['mincash']*a-before,0),max(p['credit_limit']*a-debt,0))
  debt+=borrowed;before+=borrowed
  parent_interest=parent_bank_debt*p['interest']+bond_accretion
  parent_operating_aftertax=(.45*1.02**i + p['margin_shift']*6.0)*p['volume_scale'][i] -p['extra_cost'][i]*.30
  parent_pretax=parent_operating_aftertax/(1-p['tax'])-parent_interest
  parent_own_profit=parent_pretax-max(parent_pretax,0)*p['tax']
  # Declared upstream cash: Zhonglin + wholly owned mature fertilizer subsidiaries; not a fictitious reserve pool.
  zhonglin_declared=(.20+.015*min(i,4))*p['parent_upstream_factor']*p['volume_scale'][i]
  other_declared=(.20+.015*min(i,4))*p['parent_upstream_factor']*p['volume_scale'][i]
  declared=max(0.,zhonglin_declared+other_declared)
  receipt=declared
  if t<=p['parent_delay_years']:
   pending_receivable+=declared;receipt=0.
  elif pending_receivable:
   receipt+=pending_receivable;pending_receivable=0.
  parent_profit=parent_own_profit+declared # receipt of old declared dividend is not profit twice
  reserve_base=max(parent_profit-max(-pretained,0),0)
  reserve_add=min(max(pcap-reserve,0),reserve_base*.1)
  reserve+=reserve_add;pretained+=parent_profit-reserve_add
  # Standalone cash budget after own maintenance/working capital; debt is parent bond.
  parent_before=pcash+parent_own_profit+bond_accretion+.22-.30-.10 +receipt-p['parent_extra_funding'][i]-guarantee
  parent_bond=redemption if redemption else 0.
  # Location bridge: parent external CF + residual subsidiary common CF = total common CF.
  # All upstream receipts and downstream project funding are internal, never new group cash.
  parent_external_cf=parent_own_profit+bond_accretion+.22-.30-.10-guarantee
  subsidiary_opening=ocash-opc
  subsidiary_external_cf=fcfe-parent_external_cf
  parent_before-=parent_bond
  parent_refinance=min(borrowed,max(.30-parent_before,0)) if p['credit_limit']>=3.5 else 0.
  parent_before+=parent_refinance
  sub_before=before-parent_before
  sub_min=max(p['mincash']*a-.30,0.)
  downstream_topup=min(max(sub_min-sub_before,0.),max(parent_before-.30,0.))
  parent_before-=downstream_topup;sub_before+=downstream_topup
  # If an otherwise liquid group lacks cash at the payer, additional financing is explicit and bounded.
  location_borrow=min(max(.30-parent_before,0.)+max(sub_min-sub_before,0.),max(p['credit_limit']*a-debt,0.))
  parent_location_borrow=min(location_borrow,max(.30-parent_before,0.))
  parent_before+=parent_location_borrow;parent_refinance+=parent_location_borrow
  sub_before+=location_borrow-parent_location_borrow
  borrowed+=location_borrow;debt+=location_borrow;before+=location_borrow
  subsidiary_borrowing=borrowed-parent_refinance
  parent_bank_debt+=parent_refinance
  # Separate minority cash/credit budget: no minority cash pays the ordinary parent dividend.
  mtaxable=o['ebit']*(1-a)-(mdebt-(BANK_ACCRUED*(1-a) if t==1 else 0))*p['interest']+mcash*.015
  mprofit=mtaxable-max(mtaxable,0)*p['tax']
  mfcfe=mprofit+(p['da'][i]-p['capex'][i])*(1-a)-dwc*(1-a)/a
  mrelease=release*(1-a)/a;mrealization=realization*(1-a)/a
  mdistribution=receipt*(1-a)/a
  maccrued=BANK_ACCRUED*(1-a) if t==1 else 0.
  mdebt-=maccrued
  mbefore=mcash+mfcfe+mrelease+mrealization-mdistribution-maccrued
  mborrow=min(max(p['mincash']*(1-a)-mbefore,0.),max(p['credit_limit']*(1-a)-mdebt,0.))
  mdebt+=mborrow;mcash=mbefore+mborrow
  requested=p['dividend_ps'][i]*shares
  failed_now=before < -1e-9 or parent_before < -1e-9 or sub_before < -1e-9 or mcash < -1e-9 or debt>p['credit_limit']*a+1e-9
  if failed_now and failed is None:failed=t
  dividend=0. if failed is not None else min(requested,max(before-p['mincash']*a,0.),max(parent_before-.30,0.),max(pretained,0.))
  cash=before-dividend;pcash=parent_before-dividend;pretained-=dividend;historic+=dividend/shares
  # No subsequent rescue or distribution once an obligation fails. Keep negative amounts and costs visible.
  row={'year':t,'budget_year_label':2026+t,**o,'attribution':a,'shares_billion':shares,'opening_cash':ocash,'opening_debt':odebt,
   'bank_accrued_interest_payment':bank_accrued_payment,'interest':interest,'bond_accretion_addback':bond_accretion,'cash_interest':cash_interest,'tax':tax,'ordinary_earnings':earnings,'da_common':da,'capex_common':capex,
   'opening_wc':owc,'closing_wc':wc,'delta_wc':dwc,'opening_fixed':ofixed,'closing_fixed':fixed,'guarantee_loss_common':guarantee,
   'fcfe_pre_financing':fcfe,'restricted_release':release,'financial_realization':realization,'debt_redemption_cash':redemption,
   'principal_repaid':principal_repaid,'conversion_principal_removed':conversion_principal,'new_borrowing':borrowed,
   'dividend_common':dividend,'dividend_per_share':dividend/shares,'closing_cash':cash,'closing_debt':debt,
   'parent_opening_cash':opc,'parent_own_profit_budget':parent_own_profit,'zhonglin_dividend_declared_budget':zhonglin_declared,
   'other_mature_subs_dividend_declared_budget':other_declared,'parent_declared_dividend_income':declared,'parent_dividend_cash_receipt':receipt,
   'parent_dividend_receivable_closing':pending_receivable,'parent_statutory_reserve_add':reserve_add,'parent_retained_opening':opr,
   'parent_retained_closing':pretained,'parent_cash_closing':pcash,'parent_bond_refinancing_budget':parent_refinance,
   'parent_bank_debt_closing':parent_bank_debt,'parent_interest_expense':parent_interest,'parent_bond_accretion_addback':bond_accretion,'parent_external_cf':parent_external_cf,'subsidiary_common_opening_cash':subsidiary_opening,'subsidiary_common_external_cf':subsidiary_external_cf,
   'subsidiary_common_new_borrowing':subsidiary_borrowing,'parent_downstream_liquidity_topup':downstream_topup,'subsidiary_common_closing_cash':sub_before,
   'minority_opening_cash':omcash,'minority_opening_debt':omdebt,'minority_external_fcfe':mfcfe,'minority_distribution':mdistribution,
   'minority_restricted_release':mrelease,'minority_financial_realization':mrealization,'minority_accrued_payment':maccrued,'minority_new_borrowing':mborrow,
   'minority_closing_cash':mcash,'minority_closing_debt':mdebt,'full_group_budget_cash':cash+mcash,
   'parent_registered_capital_budget':pcap*2,'parent_reserve_profit_after_prior_loss':reserve_base,
   'parent_extra_project_funding':p['parent_extra_funding'][i],'priority_failure':failed is not None,'unpaid_priority_gap':max(-pcash,0)+max(-sub_before,0)+max(-mcash,0)}
  assert math.isclose(cash,ocash+fcfe+release+realization-redemption-bank_accrued_payment+borrowed-dividend,abs_tol=1e-8)
  assert math.isclose(debt,odebt-principal_repaid-conversion_principal+borrowed,abs_tol=1e-8)
  assert math.isclose(pretained,opr+parent_profit-reserve_add-dividend,abs_tol=1e-8)
  assert math.isclose(pcash,opc+parent_own_profit+bond_accretion+.22-.30-.10+receipt-p['parent_extra_funding'][i]-guarantee+parent_refinance-parent_bond-dividend-downstream_topup,abs_tol=1e-8)
  assert math.isclose(cash,pcash+sub_before,abs_tol=1e-8)
  assert math.isclose(sub_before,subsidiary_opening+subsidiary_external_cf+release+realization+subsidiary_borrowing-receipt+p['parent_extra_funding'][i]+downstream_topup-bank_accrued_payment,abs_tol=1e-8)
  if failed is None:assert min(pcash,sub_before,mcash)>=-1e-8
  if failed is not None:assert dividend==0
  rows.append(row)
 # Sustainable manufacturer after finite mine benefit has completely faded; maintenance already covered by EBIT depreciation.
 last=rows[-1];r=p['r'];g=p['g'];terminal_ebit=(last['ebit']+p['terminal_margin_shift']*last['revenue'])*(1+g)*a
 sustainable_nopat=terminal_ebit*(1-p['tax']);reinvestment=sustainable_nopat*g/p['roic']
 op_value=(sustainable_nopat-reinvestment)/(r-g)
 required_operating_cash=p['mincash']*a*(1+g)**10
 residual_cash=(cash-required_operating_cash+restricted+fin*p['financial_recovery'])/(1+r)**p['terminal_cash_delay']
 terminal10=op_value+residual_cash-debt
 if failed is not None or terminal10<0 or sustainable_nopat-reinvestment<=0:
  terminal10=None;pv=None;terminal5=None;tv_contribution=None
 else:
  terminal5=sum(z['dividend_per_share']/(1+r)**(z['year']-5) for z in rows[5:])+terminal10/shares/(1+r)**5
  pv=sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows)+terminal10/shares/(1+r)**10
  tv_contribution=(terminal10/shares/(1+r)**10)/pv
 # Alternative method: year 2 normalized EBIT capitalization, future committed growth expenditure deducted.
 m2=[]
 if failed is None:
  y2=rows[1];remaining_growth=sum(max(rows[j]['capex_common']-rows[j]['da_common'],0)/(1+r)**(j-1) for j in range(2,5))
  for multiple in [8.5,10.5]:
   v2=(y2['ebit']*a*multiple+y2['closing_cash']-p['mincash']*a+OPEN['financial']*a*p['financial_recovery']-y2['closing_debt']-remaining_growth)/y2['shares_billion']
   m2.append(sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows[:2])+v2/(1+r)**2)
 return {'inputs':p,'feasible':failed is None and pv is not None,'failure_year':failed,'historical_distributions_before_failure_ps':historic if failed else None,'total_modeled_paid_distributions_ps':historic,
 'rows':rows,'pv_per_share':pv,'terminal_year5_per_share':terminal5,'terminal_year10_common_billion':terminal10,
 'terminal_value_fraction':tv_contribution,'terminal_required_operating_cash':required_operating_cash if pv is not None else None,'terminal_surplus_cash_pv':residual_cash if pv is not None else None,'terminal_nopat':sustainable_nopat if pv is not None else None,'terminal_reinvestment':reinvestment if pv is not None else None,
 'method2_per_share':m2 if pv is not None else None}
def scenarios():
 d={'base':copy.deepcopy(BASE)}
 def add(n,**kw):d[n]={**copy.deepcopy(BASE),**kw}
 add('core_low',r=.105,margin_shift=-.0025)
 add('core_high',r=.095,margin_shift=.0025)
 add('cyclical_weak',volume_scale=[.90,.93,.98,1,1,1,1,1,1,1],price_scale=[.94,.96,.99,1,1,1,1,1,1,1],
     wc_ratio=[.18,.17,.15,.13,.13,.13,.13,.13,.13,.13],chem_margin=[-.02,.02,.06,.09,.10,.10,.10,.10,.10,.10],parent_upstream_factor=.65)
 add('structural_damage',volume_scale=[.93,.90,.88,.87,.86,.85,.84,.83,.82,.81],margin_shift=-.025,
     chem_margin=[-.04,-.03,0,.02,.03,.03,.03,.03,.03,.03],mine_savings=[0]*10,
     wc_ratio=[.18]*10,capex=[2.4,2.1,1.9,1.6,1.5,1.5,1.5,1.5,1.5,1.5],
     parent_upstream_factor=.35,guarantee_loss=[0,.368,0,0,0,0,0,0,0,0],g=0.,roic=.07)
 add('optimistic',volume_scale=[1,1.03,1.06,1.09,1.12,1.12,1.12,1.12,1.12,1.12],margin_shift=.005,
     chem_margin=[.08,.10,.12,.13,.13,.13,.13,.13,.13,.13],capex=[2.5,2.2,1.9,1.5,1.3,1.32,1.34,1.36,1.38,1.4],
     parent_upstream_factor=1.2)
 add('float_and_receipt_delay',extra_wc=[.8,.8,.4,0,0,0,0,0,0,0],parent_delay_years=2,parent_extra_funding=[.5,.5,.1,0,0,0,0,0,0,0])
 add('full_conversion',convert=True)
 add('minority_capital_heavier',attribution=.92)
 add('capital_overrun',capex=[2.9,2.6,2.05,1.5,1.3,1.32,1.34,1.36,1.38,1.4])
 add('no_mine_increment',mine_savings=[0]*10)
 add('financial_exit_delay',financial_year=8,financial_recovery=.70)
 add('terminal_cash_release_delay',terminal_cash_delay=5)
 add('late_failure',extra_cost=[0,0,9,9,9,9,9,9,9,9])
 add('credit_failure',credit_limit=2.5,extra_wc=[2.]*10,extra_cost=[1.]*10,parent_upstream_factor=0.,parent_extra_funding=[1.]*10)
 return d

def tests():
 # These hand cases enter the SAME production function, not a detached identity.
 p=copy.deepcopy(BASE);p.update(margin_shift=0,volume_scale=[0]*10,chem_sales=[0]*10,chem_margin=[0]*10,mine_savings=[0]*10,
  extra_cost=[0]*10,capex=[0]*10,da=[0]*10,wc_ratio=[0]*10,dividend_ps=[0]*10,tax=0.,interest=0.,bond_premium=.042)
 x=simulate(p)
 # Year1 EBIT=-.05+.5*.12=.01; cash interest=.01968041344968; common EBIT=.0096.
 assert abs(x['rows'][0]['ebit']-.01)<1e-12
 assert abs(x['rows'][0]['ordinary_earnings']+.01271958655032)<1e-11
 assert abs(x['rows'][0]['delta_wc']+OPEN['wc']*.96)<1e-11
 # Parent receipts delayed: no receipt first 2 years, year3 receives old 0.83 +new 0.46, only .46 new income.
 q=copy.deepcopy(BASE);q['parent_delay_years']=2;y=simulate(q)
 assert abs(y['rows'][2]['parent_dividend_cash_receipt']-1.29)<1e-12
 assert abs(y['rows'][2]['parent_declared_dividend_income']-.46)<1e-12
 z=simulate(scenarios()['credit_failure']);assert not z['feasible']
 assert z['pv_per_share'] is None and z['terminal_year5_per_share'] is None and z['terminal_year10_common_billion'] is None
 assert all(v['dividend_common']==0 for v in z['rows'][z['failure_year']-1:])
 late=simulate(scenarios()['late_failure']);assert late['failure_year']==3 and late['historical_distributions_before_failure_ps']>0
 assert late['pv_per_share'] is None and all(q['dividend_common']==0 for q in late['rows'][2:])
 loss=copy.deepcopy(BASE);loss['extra_cost']=[30]+[0]*9;v=simulate(loss)
 assert v['rows'][1]['parent_retained_opening']<0 and v['rows'][1]['parent_statutory_reserve_add']==0
 loss_case={'year2_opening_retained':v['rows'][1]['parent_retained_opening'],'year2_profit':v['rows'][1]['parent_own_profit_budget']+v['rows'][1]['parent_declared_dividend_income'],'year2_reserve_add':v['rows'][1]['parent_statutory_reserve_add']}
 loss=copy.deepcopy(BASE);loss.update(parent_opening_retained=-.5,parent_opening_reserve=.1,bond_premium=0);v=simulate(loss)
 assert abs(v['rows'][0]['parent_statutory_reserve_add']-.035)<1e-12
 return {'reserve_counterexample_large_loss':loss_case,'reserve_counterexample_partial_recovery':{'opening_retained':-.5,'profit':.85,'reserve_add':v['rows'][0]['parent_statutory_reserve_add']},'loss_absorption_before_reserve':True,'nested_cash_location_bridge':True,'late_failure_preserves_history':True,'production_hand_case':True,'receipt_not_new_profit':True,'failure_null_all_values':True,'cash_and_debt_all_years':True}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(Path(__file__).with_name('2026-Q3-output.json')));args=ap.parse_args()
 out={'symbol':SYMBOL,'name':NAME,'report_period':PERIOD,'asof':ASOF,'units':'CNY billion except per-share CNY and tonnes million','opening':OPEN,
 'scenarios':{n:simulate(p) for n,p in scenarios().items()},'tests':tests()}
 assert out['symbol']=='CN:000902' and out['name']=='新洋丰'
 with open(args.output,'w',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
if __name__=='__main__':main()
