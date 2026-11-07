#!/usr/bin/env python3
"""CN:300910 / 新乡市瑞丰新材料股份有限公司 / 2026-Q3.
All economic balances in CNY million; annual end-period discounting.
Economic consolidation budget, NOT legal-entity distributability certification.
Standard library only. python 2026-Q3.py (output beside script: 2026-Q3-output.json)
"""
import json, argparse, copy, math, pathlib
IDENTITY={'symbol':'CN:300910','name':'新乡市瑞丰新材料股份有限公司','report_period':'2026-Q3','report_path':'research/companies/CN/300910/reports/2026-Q3.md'}
SHARES=383.042277 # million, full issued incl treasury: no free cancellation benefit
OPEN={'cash_equivalents':444.10001981,'liquid_financial':981.58540663,'restricted_cash_excluded':5.66342123,'debt_and_leases':951.45762823,'fund_nav':614.50539671,'fund_existing_tax':20.27095069,'working_capital':1063.72532828,'opening_capital_payable_budget':80.,'earmarked_project_cash':223.9541,'parent_retained':1670.62225417,'parent_statutory_reserve':147.967639,'parent_registered_capital':383.042277,'parent_book_share_capital':383.042277,'prior_registered_capital':295.935278,'capitalized_share_premium':87.106999,'capitalization_new_cash':0.0,'historical_paid_dividend':435.53499750}
# opening NWC uses every disclosed operating current asset/liability; see sources.md bridge.
BASE={'revenue':[3800,4150,4520,4890,5220,5480,5700,5870,6020,6140], 'margin':[.155,.165,.175,.18,.18,.1775,.175,.1725,.17,.17], 'depreciation':[130,145,160,170,180,185,190,195,200,205], 'capex':[550,550,500,440,400,240,230,225,220,220], 'wc_ratio':[.265,.26,.255,.25,.245,.24,.24,.24,.24,.24], 'saudi_revenue':[0,0,200,450,700,850,950,1000,1030,1060], 'saudi_ebit':[-8,-12,5,35,77,102,114,120,123.6,127.2], 'saudi_capex':[250,350,289,25,30,35,40,40,40,40], 'saudi_depreciation':[0,0,20,35,40,40,40,40,40,40], 'tax':[.15,.18,.18,.18,.18,.18,.18,.18,.18,.18], 'saudi_tax':.22, 'existing_common_factor':.995, 'saudi_owner':.6,'saudi_funding_share':.6,'saudi_extra_deficit_funding':0.,'saudi_wc_ratio':.22,'interest_rate':.035,'fund_recovery':.90,'fund_exit':[0,0,0,.2,.4,.4,0,0,0,0],'fund_calls':[90,90,0,0,0,0,0,0,0,0], 'fund_exit_cost':.02,'dividend_payout':.45,'discount':.105,'terminal_growth':.015,'terminal_roic':.14,'cash_yield_after_tax':.012,'cash_floor':180,'max_credit':250,'credit_rate':.065,'parent_profit_factor':.90,'parent_cash_haircut':.10,'trapped_release_year':5,'extra_claims':[0]*10,'extra_wc':[0]*10,'extra_funding':[0]*10,'debt_repay':[0]*10,'terminal_financial_recovery':1.0}

def run(p,opening=None):
 o=copy.deepcopy(OPEN if opening is None else opening); own=p['existing_common_factor']; cash=(o['cash_equivalents']+o['liquid_financial'])*own
 # Opening liquid portfolio redeemed as needed; all existing debt/lease principal
 # is paid in year one, with half-year carry interest. This is a feasible funding
 # budget, not a claim that long loans legally accelerate. No legal acceleration is asserted.
 earmarked=o.get('earmarked_project_cash',0); cash-=earmarked; trapped=max(cash,0)*p['parent_cash_haircut']; cash-=trapped
 retained=o['parent_retained']; reserve=o['parent_statutory_reserve']; reserve_target=(p.get('registered_capital_override') or o['parent_registered_capital'])*.5
 wc=o['working_capital']; swc=0.; credit=0.; failed=False; hist=[]; rows=[]; fund_left=o['fund_nav']; parent_loss=0.
 for i in range(10):
  y=i+1; rev=p['revenue'][i]; ebit=rev*p['margin'][i]; tax=max(ebit,0)*p['tax'][i]; np=(ebit-tax)*own
  nwc=rev*p['wc_ratio'][i]+p['extra_wc'][i]; dwc=nwc-wc; wc=nwc
  core_cf=(ebit-tax+p['depreciation'][i]-p['capex'][i]-dwc)*own
  sr=p['saudi_revenue'][i]; se=p['saudi_ebit'][i]; st=max(se,0)*p['saudi_tax']; snp=(se-st)*p['saudi_owner']; nswc=sr*p['saudi_wc_ratio']; dswc=nswc-swc; swc=nswc
  saudi_all_cf=se-st+p['saudi_depreciation'][i]-dswc-p['saudi_capex'][i]; saudi_extra=max(-saudi_all_cf,0)*p['saudi_extra_deficit_funding']; scf=saudi_all_cf*p['saudi_owner']-saudi_extra
  fund_call=p['fund_calls'][i]; fund_left+=fund_call
  nav_slice=(o['fund_nav']+sum(p['fund_calls']))*p['fund_exit'][i]; fund_left-=nav_slice
  gross_recovery=nav_slice*p['fund_recovery']; fund_cost=gross_recovery*p['fund_exit_cost']; fund_tax=o['fund_existing_tax']*p['fund_exit'][i]
  fund_receipt=gross_recovery-fund_cost-fund_tax
  # Accounting mark-to-exit loss counts in distribution capacity; principal receipt is not profit.
  fund_accounting_result=gross_recovery-nav_slice-fund_cost
  earmarked_use=min(earmarked,p['capex'][i]*own); earmarked-=earmarked_use; start=cash; interest=max(cash,0)*p['cash_yield_after_tax']; old_debt_payment=o['debt_and_leases']*own if y==1 else 0.; old_debt_interest=o['debt_and_leases']*own*p['interest_rate']*.5 if y==1 else 0.; credit_interest=credit*p['credit_rate']; release=trapped if y==p['trapped_release_year'] else 0.; trapped-=release
  available=cash+core_cf+scf+fund_receipt+interest-credit_interest+release+earmarked_use-old_debt_payment-old_debt_interest-fund_call-p['extra_claims'][i]-p['extra_funding'][i]-p['debt_repay'][i]
  parent_profit=np*p['parent_profit_factor']+snp+interest-credit_interest-old_debt_interest+fund_accounting_result-p['extra_claims'][i]
  retained+=parent_profit
  # Losses reduce available accumulated earnings before reserve/dividend; no magic reset.
  reserve_add=min(max(reserve_target-reserve,0),max(min(parent_profit,retained),0)*.10); reserve+=reserve_add; retained-=reserve_add
  borrowed=0.
  if not failed and available<p['cash_floor']:
   borrowed=min(max(p['max_credit']-credit,0),p['cash_floor']-available); credit+=borrowed; available+=borrowed
  unpaid=max(-available,0)
  operating_liquidity_shortfall=max(p['cash_floor']-available,0)
  if operating_liquidity_shortfall>1e-8: failed=True
  ordinary=max(np+snp+interest-credit_interest-old_debt_interest,0)*p['dividend_payout']; proposed=ordinary+(max(available-ordinary-500,0) if y>=6 else 0)
  credit_repaid=min(credit,max(available-p['cash_floor']-proposed,0)) if y>=4 and not failed else 0.; credit-=credit_repaid; available-=credit_repaid
  paid=0. if failed else min(proposed,max(available-p['cash_floor'],0),max(retained,0))
  cash=available-paid; retained-=paid; hist.append(paid)
  r={'year':y,'period_end':str(2026+y)+'-10-26','existing_group_revenue':rev,'existing_group_ebit':ebit,'existing_group_tax':tax,'existing_common_profit':np,'existing_group_depreciation':p['depreciation'][i],'existing_group_capex':p['capex'][i],'existing_group_nwc':nwc,'existing_group_delta_nwc':dwc,'existing_common_cash':core_cf,'saudi_revenue':sr,'saudi_ebit':se,'saudi_tax':st,'saudi_common_profit':snp,'saudi_group_capex':p['saudi_capex'][i],'saudi_common_cash':scf,'saudi_partner_deficit_funded':saudi_extra,'earmarked_project_use':earmarked_use,'earmarked_project_remaining':earmarked,'saudi_nwc':swc,'saudi_common_capital_funded':p['saudi_capex'][i]*p['saudi_funding_share'],'fund_capital_call':fund_call,'fund_opening_and_new_nav_realized':nav_slice,'fund_gross_recovery':gross_recovery,'fund_cost':fund_cost,'fund_tax_paid':fund_tax,'fund_cash_receipt':fund_receipt,'fund_accounting_result':fund_accounting_result,'fund_remaining_nav':fund_left,'cash_start':start,'cash_interest':interest,'credit_interest':credit_interest,'existing_debt_repaid':old_debt_payment,'existing_debt_interest':old_debt_interest,'credit_draw':borrowed,'credit_repaid':credit_repaid,'credit_outstanding':credit,'trapped_released':release,'trapped_remaining':trapped,'extra_claims':p['extra_claims'][i],'extra_funding':p['extra_funding'][i],'debt_repay':p['debt_repay'][i],'parent_economic_profit_capacity':parent_profit,'parent_reserve_addition':reserve_add,'parent_reserve':reserve,'parent_retained':retained,'proposed_distribution':proposed,'paid_distribution':paid,'cash_end':cash,'unpaid_priority_claims':unpaid,'required_operating_cash':p['cash_floor'],'operating_liquidity_shortfall':operating_liquidity_shortfall,'feasible':not failed,'shares':SHARES,'distribution_per_share':paid/SHARES}
  assert math.isclose(start+core_cf+scf+fund_receipt+interest-credit_interest+release+earmarked_use+borrowed-old_debt_payment-old_debt_interest-fund_call-p['extra_claims'][i]-p['extra_funding'][i]-p['debt_repay'][i]-credit_repaid-paid,cash,abs_tol=1e-8)
  rows.append(r)
 r=p['discount']; g=p['terminal_growth']; terminal=None; pv=None; tv5=None; fraction=None
 if not failed:
  steady_np=(p['revenue'][-1]*p['margin'][-1]*(1-p['tax'][-1])*own + (p['saudi_ebit'][-1]-max(p['saudi_ebit'][-1],0)*p['saudi_tax'])*p['saudi_owner'])
  perpetual_cf=steady_np*(1+g)*(1-g/p['terminal_roic'])
  if perpetual_cf<=0 or r<=g: failed=True
  else:
   business=perpetual_cf/(r-g)
   terminal=business+cash-p['cash_floor']+trapped+fund_left*p['fund_recovery']*(1-p['fund_exit_cost'])-credit
   if terminal<0: failed=True
   else:
    pv=sum(v/(1+r)**(i+1) for i,v in enumerate(hist))+terminal/(1+r)**10
    tv5=sum(hist[i]/(1+r)**(i-4) for i in range(5,10))+terminal/(1+r)**5
    fraction=(terminal/(1+r)**10)/pv
 if failed: terminal=pv=tv5=fraction=None
 return {'identity':IDENTITY,'parameters':p,'opening':o,'annual':rows,'feasible':not failed,'forecast_cash_received_before_failure':hist,'historical_actual_distributions_excluded':o['historical_paid_dividend'],'terminal_10':terminal,'terminal_5_per_share':None if tv5 is None else tv5/SHARES,'pv_per_share':None if pv is None else pv/SHARES,'terminal_pv_share':fraction}

def scenarios():
 out={'base':copy.deepcopy(BASE)}
 lo=copy.deepcopy(BASE);lo.update(discount=.115,terminal_roic=.125);lo['margin']=[x-.005 for x in BASE['margin']];out['core_low']=lo
 hi=copy.deepcopy(BASE);hi.update(discount=.095,terminal_roic=.155);hi['margin']=[x+.005 for x in BASE['margin']];out['core_high']=hi
 cyc=copy.deepcopy(BASE);cyc['revenue']=[3400,3700,4200]+BASE['revenue'][3:];cyc['margin']=[.115,.135,.16]+BASE['margin'][3:];cyc['extra_wc']=[180,100,30]+[0]*7;cyc['capex']=[450,450,500,540,400]+BASE['capex'][5:];out['cyclical_weak']=cyc
 structural=copy.deepcopy(BASE);structural.update(discount=.12,terminal_growth=0,terminal_roic=.085,fund_recovery=.70);structural['revenue']=[3200,3250,3300,3350,3400,3400,3400,3400,3400,3400];structural['margin']=[.10,.10,.105,.11,.11,.11,.11,.11,.11,.11];structural['capex']=[380,350,260,200,180,180,180,180,180,180];structural['saudi_revenue']=[0,0,0,100,200,250,280,300,300,300];structural['saudi_ebit']=[-8,-12,-18,-5,4,10,16,20,20,20];structural['saudi_capex']=[100,150,250,389,20,20,20,20,20,20];structural['extra_wc']=[150]*10;out['structural_loss']=structural
 up=copy.deepcopy(BASE);up.update(discount=.10,terminal_growth=.02,terminal_roic=.17);up['revenue']=[4000,4500,5050,5650,6200,6650,7000,7250,7450,7600];up['margin']=[.17,.18,.19,.19,.19,.185,.18,.18,.18,.18];up['capex']=[600,650,600,450,350,300,280,260,250,250];up['saudi_ebit']=[-8,-10,15,55,100,140,165,180,190,200];out['upside']=up
 for name,changes in {'prior_registered_capital':{'registered_capital_override':295.935278},'fund_no_remaining_call':{'fund_calls':[0]*10},'fund_half':{'fund_recovery':.5},'fund_delay':{'fund_exit':[0,0,0,0,0,0,.3,.4,.3,0]},'working_capital_plus90days':{'extra_wc':[900]*10},'parent_upstream_delay':{'parent_cash_haircut':.30,'trapped_release_year':8},'tax25':{'tax':[.25]*10},'minority_attribution98':{'existing_common_factor':.98},'saudi_partner_no_funding':{'saudi_extra_deficit_funding':.4},'capex_overrun':{'capex':[v*1.3 for v in BASE['capex']]},'credit_unavailable':{'max_credit':0},'failed_priority_claim':{'extra_claims':[0,3000]+[0]*8,'max_credit':0}}.items():
  p=copy.deepcopy(BASE);p.update(changes);out[name]=p
 return out

def holder_terminal_paths():
 # The holder interface fixes the actual BASE first five annual states and cash D.
 # Tail assumptions start at Y6; no terminal number is transplanted from core endpoints.
 result={}
 base_path=run(copy.deepcopy(BASE))
 for name,delta,rate,roic in [('low',-.005,.115,.125),('high',.005,.095,.155)]:
  p=copy.deepcopy(BASE)
  p['margin']=BASE['margin'][:5]+[x+delta for x in BASE['margin'][5:]]
  p['discount']=rate;p['terminal_roic']=roic
  path=run(p)
  assert path['annual'][:5]==base_path['annual'][:5]
  # Only a Y5 conditional valuation is exposed; applying the tail rate to Y1-Y5
  # would define a different current-value question, not this holder interface.
  path.pop('pv_per_share');path.pop('terminal_pv_share')
  path['valuation_scope']='conditional_at_year_5_from_fixed_base_state'
  result[name]=path
 return result

def method_two():
 # Independent normalized earnings (2023-25 history), not generated from DCF margin path.
 # Common operating earnings 540..650; effective multiple from finite franchise+capital needs.
 # All invested future domestic/Saudi projects included by explicitly subtracting remaining
 # growth spending NPV, then adding separately forecast incremental mature cash earnings.
 debt_net=(OPEN['cash_equivalents']+OPEN['liquid_financial']-OPEN['debt_and_leases'])*.995
 vals=[]
 for normal,multiple,project_np,project_multiple,capexpv,fundfactor in [(540,13,95,10,1450,.75),(650,15,145,12,1450,.9)]:
  fund=((OPEN['fund_nav']+180)*fundfactor*.98-OPEN['fund_existing_tax'])/(1.105**5)-90/1.105-90/1.105**2
  total=normal*multiple+project_np*project_multiple/(1.105**4)-capexpv+debt_net+fund
  vals.append({'normalized_common_operating_profit':normal,'multiple':multiple,'incremental_common_project_profit':project_np,'project_multiple':project_multiple,'growth_capex_pv':capexpv,'fund_net_pv':fund,'net_liquid_assets':debt_net,'value_per_share':total/SHARES})
 return vals

def main():
 a=argparse.ArgumentParser();a.add_argument('--out',default=str(pathlib.Path(__file__).resolve().with_name('2026-Q3-output.json')));args=a.parse_args()
 data={'identity':IDENTITY,'schema':'annual_common_economic_budget_v1','unit':'CNY million, per share CNY','scenarios':{n:run(p) for n,p in scenarios().items()},'method_two':method_two(),'holder_terminal_paths':holder_terminal_paths()}
 pathlib.Path(args.out).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
