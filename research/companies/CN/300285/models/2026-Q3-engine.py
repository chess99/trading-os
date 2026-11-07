#!/usr/bin/env python3
"""CN:300285 国瓷材料; economic budgets, NOT legal-entity financial statements.
Units CNY billion, shares billion. Standard library only. Default writes next to script.
"""
import json, math, copy, pathlib, argparse
IDENTITY={'symbol':'CN:300285','name':'国瓷材料','period':'2026-Q3'}
# The 94% common economic weight is a bounded portfolio allocation, not an ownership claim.
# It applies to earnings, working capital, capital expenditure, and cash consistently; debt is charged in full because recourse is not allocated away.
OPEN={'cash':.43144809091,'restricted_cash':.07592967710,
 'debt':1.28558476085,'wc':2.56591072716,'financial_principal':.02116227261,'associate_value':.15257329820,'current_debt_due':.54490335346,
 'shares':.988021599,'registered_shares':.997048299,'award_total':.0057606,'parent_cash_budget':.15,'parent_profit_available':2.90,
 'parent_reserve':.41099427948,'paid_in_parent_capital':.997048299,'registered_parent_capital':.997048299}
SEGS=['电子','催化','牙科医疗','新能源','精密陶瓷','打印及其他']
BASE={'revenue':[.88,1.08,1.60,.78,.46,1.20],
 'growth_floor':.025,'growth':[.10,.06,.09,.12,.12,.04], 'margin':[.23,.23,.18,.18,.14,.10],
 'common_weight':.94,'tax':.17,'wc_ratio':.45,'da_ratio':.060,
 'maintenance_ratio':.057,'capex_ratio':.105,'rate':.045,'reserve_cash':.055,
 'parent_own_share':.55,'upstream_leakage':.03,'upstream_rate':.70,'finance_limit':.40,
 'parent_settlement_extra':0., 'collection_delay':0., 'maintenance_extra':0.,
 'awards_allowed':True,'exceptional_cost':0.,'exceptional_year':1,'release_year':3,'associate_release_year':5,'surplus_payout_start':6,'rollover':True,'name':'Base'}

def reserve_transfer(profit, retained, reserve, registered_capital):
 # Company Law uses registered capital, not paid-in capital or investment cost.
 return min(max(0.,profit+min(0.,retained))*.10,max(0.,registered_capital*.50-reserve))

def continuous_tail(last, p, ke, g, roic, legal_reserve):
 """Same parent/subsidiary remittance strategy continues, no year-11 forced exit.
 Reinvestment includes growth in required operating cash; use EXCESS cash states
 so the operating-cash floor is retained and never distributed twice.
 1000 years numerically approximates an infinite stream, with a disclosed bound.
 """
 own=p['parent_own_share']; w=p['common_weight']; shares=last['shares_end']
 parent=last['parent_cash_end']-last['parent_cash_floor']
 sub=last['cash_end']-last['cash_floor']-parent
 retained=last['parent_legal_profit_budget']; debt=last['debt_end']
 pv=0.; sampled=[]; last_nopat=last['common_ebit']*(1-p['tax'])
 debt_installment=debt/max(1,10-last['year'])
 for n in range(1,1001):
  nopat=last_nopat*(1+g)**n
  reinvest=nopat*g/roic
  maintenance=p['maintenance_extra']*w*(1+g)**n
  interest=debt*p['rate']; debt_paid=min(debt,debt_installment)
  # Interest reduces earnings and cash; remaining debt is paid BEFORE common payouts.
  profit=nopat-interest*(1-p['tax'])
  fcf=profit-reinvest-maintenance
  pb,sb=parent,sub
  principal=0.
  if last['year']+n==p['release_year']:principal+=(OPEN['financial_principal']*.95+OPEN['restricted_cash'])*w
  if last['year']+n==p['associate_release_year']:principal+=OPEN['associate_value']*.85*w
  parent+=(fcf-debt_paid)*own+principal;sub+=(fcf-debt_paid)*(1-own);debt-=debt_paid
  gross=max(0.,sub)*p['upstream_rate'];cost=gross*p['upstream_leakage']
  sub-=gross;parent+=gross-cost
  pp=profit*own+gross-cost
  add=reserve_transfer(pp,retained,legal_reserve,OPEN['registered_parent_capital'])
  legal_reserve+=add;retained+=pp-add
  if parent < -1e-9 or sub < -1e-9:
   return {'feasible':False,'pv_at_anchor':None,'unpaid_creditor_claim':max(0.,-parent,-sub)}
  absolute_year=last['year']+n
  desired=shares*[.15,.18,.22,.26,.30][absolute_year-1] if absolute_year<=5 else (shares*.30 if absolute_year<p['surplus_payout_start'] else max(0.,parent+sub))
  dividend=min(desired,max(0.,parent),max(0.,parent+sub),max(0.,retained))
  parent-=dividend;retained-=dividend;pv+=dividend/(1+ke)**n
  if n<=10 or n in (50,100,1000):
   sampled.append({'tail_year':n,'nopat':nopat,'reinvestment':reinvest,'extra_maintenance':maintenance,
    'fcf_before_remittance':fcf,'parent_excess_begin':pb,'subsidiary_excess_begin':sb,
    'debt_paid':debt_paid,'debt_end':debt,'principal_realized':principal,'upstream_gross':gross,'remittance_cost':cost,
    'parent_profit_budget':pp,'reserve_add':add,'parent_retained':retained,
    'dividend':dividend,'parent_excess_end':parent,'subsidiary_excess_end':sub})
 # Conservative numerical remainder includes ALL residual excess, even inaccessible sub cash.
 bound=(abs(parent)+abs(sub)+abs(nopat)*(1+g)/(ke-g))/(1+ke)**1000
 return {'feasible':True,'pv_at_anchor':pv,'policy':'continuous_parent_cash_profit_and_subsidiary_remittance',
  'anchor_year':last['year'],'years_computed':1000,'remaining_pv_upper_bound':bound,
  'opening_parent_excess':last['parent_cash_end']-last['parent_cash_floor'],
  'opening_subsidiary_excess':last['cash_end']-last['cash_floor']-(last['parent_cash_end']-last['parent_cash_floor']),
  'fcf_before_remittance_year1':sampled[0]['fcf_before_remittance'],
  'year1_dividend':sampled[0]['dividend'],'sampled_rows':sampled}

def budget(p, rates=(.115,.105), gs=(.02,.025), terminal_roics=(.12,.14)):
 p=copy.deepcopy(p); w=p['common_weight']; shares=OPEN['shares']
 cash=OPEN['cash']*w; debt=OPEN['debt']; wc=OPEN['wc']*w
 parent_cash=OPEN['parent_cash_budget']; parent_retained=OPEN['parent_profit_available']
 legal_reserve=OPEN['parent_reserve']; drawn=0.; unpaid=0.; failed=False; rows=[]; rev=p['revenue'][:]
 fixed_repayment=debt/10
 for t in range(1,11):
  begin_cash=cash; begin_shares=shares; begin_debt=debt; begin_parent_cash=parent_cash; begin_unpaid=unpaid
  if t>1:
   rev=[r*(1+max(p['growth_floor'],g*(1 if t<=5 else (11-t)/6))) for r,g in zip(rev,p['growth'])]
  scale=1.; margin_shift=0.; extra_wc=0.; extra_cost=0.
  if p['name']=='Cycle' and t<=3:
   scale=[.88,.93,.98][t-1]; margin_shift=[-.04,-.025,-.01][t-1]; extra_wc=[.15,.10,0][t-1]
  if p['name']=='Structural':
   # permanently weaker MLCC/dental pricing, catalyst ICE substitution and lower capital returns
   scale=.96**(t-1); margin_shift=-.055
  if p['name']=='Upside': scale=1.04**min(t,5); margin_shift=.015
  sales=[r*scale for r in rev]; revenue=sum(sales)
  ebit_by=[r*(m+margin_shift) for r,m in zip(sales,p['margin'])]
  ebit=sum(ebit_by)*w
  # Historical acquisition price is already in opening cash/debt; never paid a second time.
  exceptional=p['exceptional_cost'] if t==p['exceptional_year'] else 0.
  interest=begin_debt*p['rate']; pretax=ebit-interest-exceptional
  tax=max(0.,pretax)*p['tax']; profit=pretax-tax
  award=(OPEN['award_total']/2 if t<=2 and p['awards_allowed'] and p['name'] not in ('Cycle','Structural') and profit>0 and not failed else 0.)
  issue_price=15.08-(.15 if t==2 else 0.)
  issue_proceeds=award*issue_price
  shares+=award
  da=revenue*p['da_ratio']*w
  maintenance=(revenue*p['maintenance_ratio']+p['maintenance_extra'])*w
  growth_capex=revenue*(p['capex_ratio']-p['maintenance_ratio'])*w*(1 if t<=5 else (11-t)/6)
  if p['name']=='Structural': growth_capex*=.45
  capex=maintenance+growth_capex
  # Opening includes full taxes, payroll, contract floats and other operating claims (bridge in report).
  next_wc=(revenue*p['wc_ratio']+extra_wc+p['collection_delay']*(1 if t<=2 else 0))*w
  delta_wc=next_wc-wc; wc=next_wc
  financial_release=(OPEN['financial_principal']*.95+OPEN['restricted_cash'])*w if t==p['release_year'] else 0.
  financial_release+=OPEN['associate_value']*.85*w if t==p['associate_release_year'] else 0.
  # Principal sale is not income. 5% haircut includes tax/transaction-cost economic allowance.
  fcfe_before_debt=profit+da-capex-delta_wc+financial_release
  scheduled=fixed_repayment+(drawn/5 if t>=6 else 0.)
  if not p['rollover']:
   scheduled=OPEN['current_debt_due'] if t==1 else (OPEN['debt']-OPEN['current_debt_due'])/9
  gross_refinancing=max(0.,OPEN['current_debt_due']-scheduled) if t==1 and p['rollover'] else 0.
  repayment=min(begin_debt,scheduled)
  cash_before_finance=begin_cash+fcfe_before_debt-repayment+issue_proceeds
  floor=revenue*p['reserve_cash']*w
  financing=min(max(0.,floor-cash_before_finance),max(0.,p['finance_limit']*w-drawn)) if not failed else 0.
  drawn+=financing; debt=begin_debt+financing-repayment
  cash=cash_before_finance+financing
  # Parent income/cash budget: own economic activity plus actual forecast remittance.
  # This proxy never creates additional consolidated earnings.
  own_cf=(fcfe_before_debt-financial_release)*p['parent_own_share']+financial_release
  parent_payment=repayment*p['parent_own_share']+p['parent_settlement_extra']*(1 if t==1 else 0.)
  parent_cash+=own_cf-parent_payment+financing*p['parent_own_share']+issue_proceeds
  subsidiary_cash=cash-parent_cash
  subsidiary_floor=floor*(1-p['parent_own_share'])
  upstream_capacity=max(0.,subsidiary_cash-subsidiary_floor)
  upstream_gross=upstream_capacity*p['upstream_rate'] if not failed else 0.
  remittance_cost=upstream_gross*p['upstream_leakage']
  upstream=upstream_gross-remittance_cost
  cash-=remittance_cost
  parent_cash+=upstream
  own_profit=profit*p['parent_own_share']
  parent_profit=own_profit+upstream
  profit_after_prior_losses=max(0.,parent_profit+min(0.,parent_retained))
  reserve_add=reserve_transfer(parent_profit,parent_retained,legal_reserve,OPEN['registered_parent_capital'])
  legal_reserve+=reserve_add; parent_retained+=parent_profit-reserve_add
  # Group-to-parent settlement: external-to-parent but internal-to-group payable remains below.
  parent_cash_floor=floor*p['parent_own_share']
  creditor_shortfall=max(0.,-cash,-parent_cash)
  liquidity_shortfall=max(0.,floor-cash)
  if creditor_shortfall>1e-10 or liquidity_shortfall>1e-10 or failed:
   failed=True
   # No fictitious zero-value recovery and no dividends after first unpayable obligation.
   unpaid=max(begin_unpaid,creditor_shortfall)
  desired=(shares*[.15,.18,.22,.26,.30][t-1] if t<=5 else (shares*.30 if t<p['surplus_payout_start'] else max(0.,cash-floor)))
  dividend=0. if failed else min(desired,max(0.,cash-floor),max(0.,parent_cash-parent_cash_floor),max(0.,parent_retained))
  cash-=dividend; parent_cash-=dividend; parent_retained-=dividend
  row={'year':t,'end_date':f'{2026+t}-10-26','segment_revenue':dict(zip(SEGS,sales)),
   'revenue':revenue,'common_weight':w,'common_ebit':ebit,'interest':interest,'tax':tax,
   'profit':profit,'depreciation':da,'maintenance_capex':maintenance,'growth_capex':growth_capex,
   'capex':capex,'working_capital':wc,'delta_wc':delta_wc,'financial_principal_realized':financial_release,
   'exceptional_cost':exceptional,'fcfe_before_debt':fcfe_before_debt,
   'cash_begin':begin_cash,'debt_begin':begin_debt,'debt_repaid':repayment,'financing_received':financing,'gross_rollover_received':gross_refinancing,'gross_debt_paid':repayment+gross_refinancing,
   'shares_begin':begin_shares,'shares_end':shares,'issue_proceeds':issue_proceeds,'awards_delivered':award,'award_cash_price':issue_price,'cash_floor':floor,
   'parent_cash_begin':begin_parent_cash,'parent_own_profit_budget':own_profit,
   'parent_own_cash_budget':own_cf,'parent_payments_budget':parent_payment,
   'upstream_gross':upstream_gross,'remittance_tax_cost':remittance_cost,'subsidiary_remittance_budget':upstream,'parent_profit_budget':parent_profit,
   'parent_profit_after_prior_losses':profit_after_prior_losses,'parent_reserve_add':reserve_add,'parent_legal_reserve':legal_reserve,'parent_legal_profit_budget':parent_retained,
   'parent_cash_end':parent_cash,'parent_cash_floor':parent_cash_floor,
   'desired_dividend':desired,'actual_dividend':dividend,'dps':dividend/shares,
   'cash_end':cash,'debt_end':debt,'unpaid_creditor_claim':unpaid,
   'liquidity_shortfall':liquidity_shortfall,'failed':failed}
  assert abs(cash-(begin_cash+profit+da-capex-delta_wc+financial_release-repayment+financing+issue_proceeds-dividend-remittance_cost))<1e-9
  assert abs(parent_cash-(begin_parent_cash+own_cf-parent_payment+financing*p['parent_own_share']+upstream+issue_proceeds-dividend))<1e-9
  assert abs(debt-(begin_debt+financing-repayment))<1e-9
  if failed: assert dividend==0
  rows.append(row)
 results=[]
 for ke,g,roic in zip(rates,gs,terminal_roics):
  if failed:
   results.append({'discount_rate':ke,'terminal_growth':g,'terminal_roic':roic,'pv':None,'tv10':None,'tv5':None,'terminal':None})
   continue
  tail=continuous_tail(rows[-1],p,ke,g,roic,rows[-1]['parent_legal_reserve'])
  if not tail['feasible']:
   results.append({'discount_rate':ke,'terminal_growth':g,'terminal_roic':roic,'pv':None,'tv10':None,'tv5':None,'terminal':None,'tail_failure':tail});continue
  terminal=tail['pv_at_anchor']
  pv=sum(r['dps']/(1+ke)**r['year'] for r in rows)+terminal/shares/(1+ke)**10
  tv5=sum(r['dps']/(1+ke)**(r['year']-5) for r in rows[5:])+terminal/shares/(1+ke)**5
  results.append({'discount_rate':ke,'terminal_growth':g,'terminal_roic':roic,'pv':pv,
   'tv10':terminal/shares,'tv5':tv5,'terminal':tail,
   'terminal_pv_fraction':terminal/shares/(1+ke)**10/pv})
 # Auxiliary: from year3 steady capital economics, same attainable remittance strategy.
 # No year3 forced liquidation and no presumption of cash immediately distributable.
 aux=[];aux_details=[]
 for ke,rr in ((.115,.10),(.105,.12)):
  if failed:aux.append(None);aux_details.append(None);continue
  r=rows[2]
  tail=continuous_tail(r,p,ke,.02,rr,r['parent_legal_reserve'])
  aux_details.append(tail)
  aux.append(None if not tail['feasible'] else sum(z['dps']/(1+ke)**z['year'] for z in rows[:3])+tail['pv_at_anchor']/r['shares_end']/(1+ke)**3)
 return {'identity':IDENTITY,'assumptions':p,'feasible':not failed,'rows':rows,'valuation':results,
 'auxiliary_value':aux,'auxiliary_detail':aux_details,'historical_forecast_distributions_received':sum(r['actual_dividend'] for r in rows),
 'unpaid_creditor_claim':unpaid,'base5D':[r['dps'] for r in rows[:5]]}

def build():
 cases={}
 for name in ('Base','Cycle','Structural','Upside'):
  p=copy.deepcopy(BASE);p['name']=name
  cases[name]=budget(p,terminal_roics=(.08,.09) if name=='Structural' else (.12,.14),gs=(.00,.005) if name=='Structural' else (.02,.025))
 for label,change in {'collection_delay_300m':{'collection_delay':.30},'maintenance_plus100m':{'maintenance_extra':.10},
  'parent_extra_payment300m':{'parent_settlement_extra':.30},'upstream_half':{'upstream_rate':.35},'upstream_zero':{'upstream_rate':0.},
  'ownership90':{'common_weight':.90},'no_refinancing':{'finance_limit':0.,'rollover':False},'no_refinancing_no_awards':{'finance_limit':0.,'rollover':False,'awards_allowed':False},'no_awards':{'awards_allowed':False},'tax25':{'tax':.25},'associate_realization_year10':{'associate_release_year':10},'surplus_distribution_year8':{'surplus_payout_start':8},'restricted_release_year5':{'release_year':5},
  'failure_cost3000m':{'exceptional_cost':3.,'finance_limit':0.},'failure_year3':{'exceptional_cost':3.,'exceptional_year':3,'finance_limit':0.}}.items():
  p=copy.deepcopy(BASE);p.update(change);cases[label]=budget(p)
 return {'schema':'CN300285-economic-budget-v2','identity':IDENTITY,'units':'CNY billion, shares billion',
 'as_of':'2026-10-26T22:00:00+00:00','opening':OPEN,'scenarios':cases}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=pathlib.Path)
 args=parser.parse_args();target=args.output or pathlib.Path(__file__).resolve().with_name('2026-Q3-output.json')
 target.write_text(json.dumps(build(),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf8')
 print(target)
if __name__=='__main__':main()
