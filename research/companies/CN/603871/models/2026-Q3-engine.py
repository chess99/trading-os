#!/usr/bin/env python3
"""嘉友国际；全自含条件预算；亿元、亿股。无网络/文件输入。"""
import json, math, copy
ASOF='2026-10-28T11:00:00+00:00'
SHARES=13.68008658
FACTS={'cash_and_wealth_q3':26.5230848982,'paid_oct23':3.8007442424,'restricted':.0998416526,'parent_cash_h1':6.811339629,'parent_RE_h1':4.419577389,'parent_investment_cost':9.8872411507,'associate_book':7.1677873957,'parent_loan_to_subs':17.4383346256,'sino_loan':16.1408703338,'parent_other_payables_h1':15.4652390672,'bank_q3':3.1967376032,'preferred_q3':1.3,'lease_q3':.2714028531,'q3_NCI':1.4635956894,'share_capital':13.68008658,'parent_statreserve':2.9108647964}
# Project figures are attributable common interests; NCI contributions/distributions separately shown gross.
PROJECTS=[{'name':'卡萨','own':1.,'end':2044,'start':2027,'base_revenue':6.7,'margin':.56,'opex':.65,'tax':.30,'amort':.75,'maint':.45,'wc':.6,'salvage':0.,'cost':16.,'newcost':0.,'share_cash':.85},
 {'name':'萨卡尼亚','own':.90,'end':2045,'start':2027,'base_revenue':1.3,'margin':.55,'opex':.15,'tax':.30,'amort':.24,'maint':.12,'wc':.25,'salvage':0.,'cost':1.9,'newcost':3.0,'share_cash':1.},
 {'name':'莫坎博','own':.90,'end':2046,'start':2029,'base_revenue':1.15,'margin':.54,'opex':.15,'tax':.30,'amort':.20,'maint':.10,'wc':.20,'salvage':0.,'cost':.5,'newcost':3.1,'share_cash':1.},
 {'name':'迪洛洛','own':.51,'end':2052,'start':2031,'base_revenue':7.0,'margin':.52,'opex':1.0,'tax':.30,'amort':.85,'maint':.55,'wc':1.,'salvage':0.,'cost':.7,'newcost':11.6,'share_cash':1.},
 {'name':'坦赞铁路5%','own':.05,'end':2056,'start':2031,'base_revenue':22.,'margin':.40,'opex':2.,'tax':.30,'amort':3.,'maint':2.5,'wc':4.,'salvage':.7,'cost':0.,'newcost':4.3,'share_cash':1.}]
# Newcost total 22.0亿元 attributable. Controlled projects grossed for asset stress; 5% rail remains equity investment.
BASE={'r':.115,'logrev':28.,'logmargin':.22,'traderev':48.,'trademargin':.135,'opex':2.10,'growth':.025,'growth_years':8,'tailgrowth':0.,'newcost_scale':1.,'project_scale':1.,'newproject_scale':1.,'kasa_share':.85,'project_delay':0,'mature_scale':1.,'weak_years':0,'weak_factor':1.,'structural':False,'remit_delay':0,'parent_net_payment':.2,'external_settlement':0.,'bank_renew':True,'bank_limit':6.,'extra_wc':0.,'end_shift':0,'preferred_rate':.045,'exit_if_insolvent':False,'exit_year':None,'exit_recovery':.55,'aux':False,'normalization_WC':3.1,'mine_exit_recovery':.8,'opening_NCI_cash_budget':.3,'reserve':8.5,'parent_reserve':1.0,'legal_haircut':.15,'payout':[.40,.40,.43,.46,.50]}
SCENARIOS={
 'base':{},'core_low':{'r':.12,'logmargin':.21,'trademargin':.125,'project_scale':.95,'newcost_scale':1.05},
 'core_high':{'r':.11,'logmargin':.23,'trademargin':.145,'project_scale':1.05,'newcost_scale':.95},
 'cyclical':{'weak_years':3,'weak_factor':.65,'project_delay':2,'extra_wc':2.,'payout':[.25,.25,.35,.40,.45]},
 'permanent_damage':{'mature_scale':.65,'project_scale':.55,'newcost_scale':1.25,'growth':0.,'structural':True,'extra_wc':3.,'payout':[0.,0.,.10,.15,.20]},
 'optimistic':{'logmargin':.245,'trademargin':.16,'growth':.04,'project_scale':1.25,'newcost_scale':.95},
 'new_project_EBIT_zero':{'newproject_scale':0.},'kasa_share_80':{'kasa_share':.80},'kasa_share_90':{'kasa_share':.90},
 'exit_low_recovery':{'bank_renew':False,'bank_limit':0.,'weak_years':5,'weak_factor':.45,'extra_wc':6.,'exit_if_insolvent':True,'exit_year':2029,'exit_recovery':.05,'payout':[0.,0.,0.,0.,0.]},
 'trade_margin_10':{'trademargin':.10},'capex_plus_6':{'newcost_scale':28/22},'overseas_remit_3yr':{'remit_delay':3},
 'no_renewal_exit':{'bank_renew':False,'bank_limit':0.,'weak_years':5,'weak_factor':.45,'extra_wc':6.,'exit_if_insolvent':True,'exit_year':2029,'exit_recovery':.45,'payout':[0.,0.,0.,0.,0.]},
 'mine_exit_zero':{'mine_exit_recovery':0.},'mine_exit_book':{'mine_exit_recovery':7.1677873957},
 'opening_NCI_cash_1_5':{'opening_NCI_cash_budget':1.5},
 'parent_extra_external_2':{'external_settlement':2.},
 'legal_capacity_half':{'legal_haircut':.50},'project_end_plus_3':{'end_shift':3},'priority_rate_8pct':{'preferred_rate':.08},
 'auxiliary':{'aux':True},'aux_low':{'aux':True,'r':.12,'mature_scale':.95,'project_scale':.95},'aux_high':{'aux':True,'r':.11,'mature_scale':1.05,'project_scale':1.05}}

def config(name):
 d=copy.deepcopy(BASE);d.update(SCENARIOS[name]);return d

def operate(c,y):
 t=y-2026; growth=(1+c['growth'])**min(t-1,c['growth_years']); weak=c['weak_factor'] if t<=c['weak_years'] else 1.
 # Core: segment margins. Auxiliary: independently specified replacement-capital returns.
 if c['aux']:
  pretax=(29.5*.26)*growth # net operating capital including 8.5 necessary cash; excludes PPP and parent investments
 else: pretax=(c['logrev']*c['logmargin']+c['traderev']*c['trademargin']-c['opex'])*growth
 pretax*=c['mature_scale']*weak
 # Cost allocation to actual payment-source groups is a budget, not segment financial disclosure.
 earnings={'parent':pretax*.25*.85,'domestic':pretax*.30*.75,'singapore':pretax*.45*.83,'africa':0.}
 legacy_nci=.05*growth*weak
 earnings['singapore']-=legacy_nci
 taxes=pretax*(.25*.15+.30*.25+.45*.17)
 mature_da=.55*growth; mature_maintenance=.55*growth; wc=.20*growth if t<=c['growth_years'] else 0.
 cf=sum(earnings.values())+mature_da-mature_maintenance-wc
 projects=[]; capex=0.; exit_cash=0.; nci_profit=legacy_nci; nci_capital=0.; amort=0.
 for p in PROJECTS:
  delay=c['project_delay'] if p['newcost'] else 0; start=p['start']+delay; end=p['end']+c['end_shift']; own=p['own']
  ramp=0. if y<start or y>end else min(1.,(y-start+1)/3.) if p['newcost'] else 1.
  project_factor=c['project_scale']*(c['newproject_scale'] if p['newcost'] else 1.)
  rev=p['base_revenue']*ramp*project_factor; gross_ebit=rev*p['margin']-p['opex']*ramp*project_factor
  if p['newcost'] and c['newproject_scale']==0.:
   rev=p['opex']*ramp/p['margin'];gross_ebit=0.
  if c['aux'] and p['newcost']:
   # Separate incremental-capital economics: 11% pretax project yield on total cost, before debt.
   gross_ebit=((p['cost']+p['newcost'])/own)*.11*ramp*project_factor
  tax=max(0.,gross_ebit)*p['tax']; ni=(gross_ebit-tax)*(c['kasa_share'] if p['name']=='卡萨' else p['share_cash']);
  da=p['amort']*ramp; maint=p['maint']*ramp; prior_ramp=0. if y-1<start or y-1>end else min(1.,(y-start)/3.) if p['newcost'] else 1.
  wc_increase=p['wc']*own*max(0.,ramp-prior_ramp) if p['newcost'] else 0.
  pcf=(ni+da-maint)*own-wc_increase
  allocation=[.27,.27,.23,.14,.09]; idx=t-1-delay
  invest=p['newcost']*c['newcost_scale']*allocation[idx] if 0<=idx<5 else 0.
  nci_capital+=invest/own*(1-own);nci_profit+=(ni+da-maint)*(1-own)
  salvage=0.
  if y==end+1:salvage=(p['wc']+p['salvage']-.10)*own # contract plant zero; WC/sale less closure cost
  earnings['africa']+=ni*own;cf+=pcf; taxes+=tax*own;capex+=invest;exit_cash+=salvage;amort+=da*own
  projects.append({'name':p['name'],'year':y,'legal_end_budget':end,'ownership':own,'revenue_gross':rev,'net_profit_gross':ni,'cash_common':pcf,'newcapital_common':invest,'newcapital_NCI':invest/own*(1-own),'cash_NCI':(ni+da-maint)*(1-own),'amort_common':da*own,'maintenance_common':maint*own,'new_working_capital_common':wc_increase,'working_capital_common':p['wc']*own*ramp,'recovery_common':salvage,'contract_asset_recovery':0.,'forecast_not_guaranteed':True})
 mine=.50 if y<=2038 else 0.; mine_exit=c['mine_exit_recovery'] if y==2039 else 0. # 20% interest; economic residual not book guarantee
 cf+=mine+exit_cash+mine_exit;earnings['parent']+=mine+(mine_exit-7.1677873957 if y==2039 else 0.)
 return {'earnings':earnings,'cash_before_growth':cf,'newcapital':capex,'tax':taxes,'NCI_profit_cash':nci_profit,'NCI_newcapital':nci_capital,'project_detail':projects,'amort':amort,'mine_cash':mine,'mine_exit':mine_exit,'exit_recovery':exit_cash}

class FundingFailure(RuntimeError):
 pass

def run(c,years=100,freeze_first5=False):
 original=copy.deepcopy(c);project_books={p['name']:p['cost'] for p in PROJECTS};mature_wc_book=6.9578068072
 gross_wc_open=23.2033589927;trade_liabilities_open=gross_wc_open-6.9578068072
 project_wc={p['name']:(p['wc']*p['own'] if not p['newcost'] else 0.) for p in PROJECTS}
 fixed_open=sum(p['cost']/(p['own'] if p['own']>=.5 else 1.) for p in PROJECTS);pwc_open=sum(project_wc[p['name']]/(p['own'] if p['own']>=.5 else 1.) for p in PROJECTS)
 residual_open=68.774558805-gross_wc_open-11.-7.1677873957-fixed_open-pwc_open
 residual_book=residual_open;associate_book=7.1677873957;stress_wc_book=0.;external_unpaid={};closure_unpaid=0.;liquidation_paid_by_entity={};asset_ledger={};pending_liability={};dividend_impairment=0.
 cash=FACTS['cash_and_wealth_q3']-FACTS['paid_oct23']-c['opening_NCI_cash_budget']; pc=FACTS['parent_cash_h1']-FACTS['paid_oct23'];pre=FACTS['parent_RE_h1']-FACTS['paid_oct23']; pres=FACTS['parent_statreserve']
 source_statreserve=0.;subre={'domestic':4.,'singapore':8.,'africa':2.}; subcash=cash-pc; sourcecash={'domestic':6.,'singapore':8.,'africa':subcash-14.}; loans={'domestic':1.1094787773,'singapore':.1879855145,'africa':16.1408703338}; olddiv=2.; receivable=0.; bank=FACTS['bank_q3']; pref=1.3; lease=FACTS['lease_q3']; loan=FACTS['parent_loan_to_subs'];loan_impaired=0.; cost=FACTS['parent_investment_cost']+FACTS['associate_book']; paidin=cost; impair=0.;rows=[];arrears=0.;exited=False; pv=0.;pending=[]
 for t in range(1,years+1):
  c=copy.deepcopy(BASE) if freeze_first5 and t<=5 else original
  c['r']=original['r']
  y=2026+t;op=operate(c,y);project_writeoff=0.
  for detail in ([] if exited else op['project_detail']):
   nm=detail['name'];project_wc[nm]=detail['working_capital_common'];project_books[nm]+=detail['newcapital_common']+detail['maintenance_common']-detail['amort_common']
   if y==detail['legal_end_budget']+1:
    project_writeoff+=max(0.,project_books[nm]);detail['carrying_value_written_off']=max(0.,project_books[nm]);project_books[nm]=0.
   detail['asset_book_budget_close']=project_books[nm]
  op['earnings']['africa']-=project_writeoff
  mature_wc_book+=.20*(1+c['growth'])**min(t-1,c['growth_years']) if t<=c['growth_years'] and not exited else 0.
  startcash=cash; startpc=pc;startpre=pre;startsub=subcash;loan_open=loan
  interest=bank*.045+pref*c['preferred_rate']+lease*.04
  repaybank=bank if (not c['bank_renew'] and t==1) or t==5 else 0.;repaypref=pref if t==5 else 0.;repaylease=lease/ max(1,6-t) if t<=5 else 0.
  bank-=repaybank;pref-=repaypref;lease-=repaylease
  normalization_out=c['normalization_WC'] if t==1 else 0.
  if not exited:mature_wc_book+=normalization_out
  obligation=1.5+.2102855503+.1605295137 if t==1 else 0. # customer refund, employee obligation, NCI loan, not dividends
  wcstress=c['extra_wc'] if t==1 else -c['extra_wc']*.5 if t in (4,5) and not c['structural'] else 0.
  if exited:
   c=copy.deepcopy(c);c['parent_net_payment']=0.;obligation=0.;wcstress=0.
  else:stress_wc_book+=wcstress
  if exited:
   op={**op,'earnings':dict.fromkeys(op['earnings'],0.),'cash_before_growth':0.,'newcapital':0.,'tax':0.,'project_detail':[],'NCI_profit_cash':0.,'NCI_newcapital':0.}
  profit=sum(op['earnings'].values())-interest;capex=op['newcapital']; extra_external=c['external_settlement'] if t==1 else 0.; cash+=op['cash_before_growth']-capex-interest-repaybank-repaypref-repaylease-obligation-wcstress-extra_external-normalization_out
  # Parent supply is an internal transfer, and is never deducted again from consolidated cash.
  parent_supply=capex*.55; new_equity=parent_supply*.5;newloan=parent_supply*.5;cost+=new_equity;paidin+=new_equity;loan+=newloan
  parent_earn=op['earnings']['parent']-interest*.85;pc+=parent_earn-extra_external-parent_supply-c['parent_net_payment']*(t<=5)-repaybank-repaylease
  pre+=parent_earn
  associate_basis_release=7.1677873957 if y==2039 and not exited else 0.
  pc+=associate_basis_release;cost-=associate_basis_release;associate_book-=associate_basis_release
  adjustment=op['cash_before_growth']-sum(op['earnings'].values())-associate_basis_release
  mature_wc=-.20*(1+c['growth'])**min(t-1,c['growth_years']) if t<=c['growth_years'] and not exited else 0.
  sourcecash['domestic']+=op['earnings']['domestic']+mature_wc*.4-obligation-wcstress-normalization_out
  sourcecash['singapore']+=op['earnings']['singapore']+mature_wc*.6
  sourcecash['africa']+=op['earnings']['africa']+adjustment-mature_wc-capex+parent_supply-interest*.15-repaypref+c['parent_net_payment']*(t<=5)
  loans['africa']+=newloan
  subcash=sum(sourcecash.values())
  # Old dividend is already in parent RE; no second investment income on collection.
  collect_old=min(olddiv,max(0.,sourcecash['domestic']-1.)) if t>c['remit_delay'] else 0.;olddiv-=collect_old;pc+=collect_old;sourcecash['domestic']-=collect_old;subcash-=collect_old
  # Each fresh declaration is bounded by both source profit capacity and actual pooled available cash.
  declarations={};totaldecl=0.
  for unit in ('domestic','singapore','africa'):
   ni=op['earnings'][unit];subre[unit]+=ni
   legal_hold=min(min(max(0.,ni),max(0.,subre[unit]))*.10,max(0.,3.78-source_statreserve)) if unit=='domestic' else 0.
   source_statreserve+=legal_hold;subre[unit]-=legal_hold
   availability=max(0.,subre[unit])
   want=max(0.,ni)*(.80 if t<=5 else 1.)*(1-c['legal_haircut'] if unit=='africa' else 1.)
   decl=min(availability,want,max(0.,sourcecash[unit]-1.-sum(x[1] for x in pending if x[2]==unit)))
   subre[unit]-=decl;declarations[unit]=decl;totaldecl+=decl
  pre+=totaldecl;receivable+=totaldecl;pending.extend([t,a,u] for u,a in declarations.items())
  collect=0.
  for item in pending:
   if t-item[0]>=c['remit_delay']:
    a=min(item[1],max(0.,sourcecash[item[2]]-1.));item[1]-=a;collect+=a;sourcecash[item[2]]-=a;subcash-=a
  receivable-=collect;pc+=collect
  # Loan repayment creates cash, not profit. Keep unpaid claim outstanding.
  lr=0.;loan_repayments={}
  for u in loans:
   a=min(loans[u],max(0.,sourcecash[u]-1.5),.8 if t<=5 else 1.5);loans[u]-=a;sourcecash[u]-=a;lr+=a;loan_repayments[u]=a
  loan-=lr;pc+=lr;subcash-=lr
  support_total=0.;support_by_entity={}
  for u in sourcecash:
   support=min(max(0.,1.-sourcecash[u]) if not exited and not (u=='africa' and y>=2057+c['end_shift']) else 0.,max(0.,pc-c['parent_reserve']))
   sourcecash[u]+=support;subcash+=support;pc-=support;loans[u]+=support;loan+=support;support_total+=support;support_by_entity[u]=support
  newloan+=support_total
  statutory=min(min(max(0.,parent_earn+totaldecl),max(0.,pre))*.10,max(0.,FACTS['share_capital']*.5-pres));pres+=statutory;pre-=statutory
  draw=0.
  if not exited and (cash<c['reserve'] or pc<c['parent_reserve']):
   draw=min(max(0.,c['bank_limit']-bank),max(c['reserve']-cash,c['parent_reserve']-pc,0.)) if c['bank_renew'] else 0.;cash+=draw;pc+=draw;bank+=draw
  liquidation={}
  # Reconcile the disclosed opening gross noncash assets to budget components, then roll each component.
  asset_ledger={'mature_gross_working_assets':mature_wc_book+trade_liabilities_open+stress_wc_book if not exited else 0.,'mature_fixed_assets':11. if not exited else 0.,'project_operating_and_equity_assets':sum(project_books[p['name']]/(p['own'] if p['own']>=.5 else 1.) for p in PROJECTS),'project_working_assets_budget':sum(project_wc[p['name']]/(p['own'] if p['own']>=.5 else 1.) for p in PROJECTS),'associate_investment':associate_book,'other_opening_noncash_residual':residual_book}
  asset_total_before_liquidation=sum(asset_ledger.values())
  prior_asset_ledger=rows[-1]['asset_ledger_close'] if rows else {'project_working_assets_budget':pwc_open}
  asset_movements={'project_newcapital_gross':sum(d['newcapital_common']/(d['ownership'] if d['ownership']>=.5 else 1.) for d in op['project_detail']),'project_maintenance_gross':sum(d['maintenance_common']/(d['ownership'] if d['ownership']>=.5 else 1.) for d in op['project_detail']),'project_amortization_gross':sum(d['amort_common']/(d['ownership'] if d['ownership']>=.5 else 1.) for d in op['project_detail']),'project_retirement_gross':sum(d.get('carrying_value_written_off',0.)/(d['ownership'] if d['ownership']>=.5 else 1.) for d in op['project_detail']),'mature_maintenance':.55*(1+c['growth'])**min(t-1,c['growth_years']) if not exited else 0.,'mature_depreciation':.55*(1+c['growth'])**min(t-1,c['growth_years']) if not exited else 0.,'normalization_WC':normalization_out,'stress_WC_change':wcstress,'associate_cost_retired':associate_basis_release,'mature_growth_WC':.20*(1+c['growth'])**min(t-1,c['growth_years']) if t<=c['growth_years'] and not exited else 0.,'project_gross_WC_change':asset_ledger['project_working_assets_budget']-prior_asset_ledger['project_working_assets_budget']}
  asset_open=sum(prior_asset_ledger.values()) if rows else 68.774558805
  asset_change=asset_movements['project_newcapital_gross']+asset_movements['project_maintenance_gross']-asset_movements['project_amortization_gross']-asset_movements['project_retirement_gross']+normalization_out+wcstress-associate_basis_release+asset_movements['mature_growth_WC']+asset_movements['project_gross_WC_change']
  assert abs(asset_total_before_liquidation-asset_open-asset_change)<1e-7
  if (c['exit_year']==y or (c['exit_if_insolvent'] and min(pc,cash,*sourcecash.values())<0)) and not exited:
   # Aggregate economic stress pool, NOT a legal consolidation of separate entities or legal ranking opinion.
   noncash_assets=sum(asset_ledger.values());recovery=noncash_assets*c['exit_recovery'];closure=3.
   claims={'bank':bank,'preferred':pref,'lease':lease,'other_external':23.3441833074-(1.5+.2102855503+.1605295137)}
   cash_before_liquidation=cash;mother_cash_before_liquidation=pc;gross_pool=max(0.,cash+recovery);closure_paid=min(gross_pool,closure);closure_unpaid=closure-closure_paid;pool=gross_pool-closure_paid
   external_claim=sum(claims.values());external_paid=min(pool,external_claim);pool-=external_paid
   external_unpaid={k:v*(1-external_paid/external_claim) for k,v in claims.items()}
   declared_claim=olddiv+receivable;declared_paid=min(declared_claim,pool);pool-=declared_paid
   old_paid=min(olddiv,declared_paid);olddiv-=old_paid;remaining_declared_payment=declared_paid-old_paid;declared_entity_paid={'domestic':old_paid,'singapore':0.,'africa':0.}
   for item in pending:
    paid=min(item[1],remaining_declared_payment);item[1]-=paid;remaining_declared_payment-=paid;receivable-=paid;declared_entity_paid[item[2]]+=paid
   pending=[x for x in pending if x[1]>1e-12]
   loan_paid=min(loan,pool);pool-=loan_paid
   liquidation_paid_by_entity={u:(v*loan_paid/loan if loan else 0.) for u,v in loans.items()}
   for u,a in liquidation_paid_by_entity.items():loans[u]-=a
   loan=sum(loans.values())
   # Budget minority net capital changes at actual gross asset participation, not only original NCI.
   nci_capital_budget=max(0.,FACTS['q3_NCI']-c['opening_NCI_cash_budget']+sum((project_books[p['name']]-p['cost'])/p['own']*(1-p['own']) for p in PROJECTS if p['own']>=.5)+sum((project_wc[p['name']]-(p['wc']*p['own'] if not p['newcost'] else 0.))/p['own']*(1-p['own']) for p in PROJECTS if p['own']>=.5))
   equity_recovery=pool;minority=min(equity_recovery,nci_capital_budget*c['exit_recovery']);parent_share=equity_recovery-minority
   cash=declared_paid+loan_paid+parent_share;subcash=0.;sourcecash=dict.fromkeys(sourcecash,0.);pc=cash;bank=pref=lease=0.;arrears=sum(external_unpaid.values())+closure_unpaid
   impair=max(0.,cost-parent_share);loan_impaired=loan;dividend_impairment=olddiv+receivable;pre+=parent_share-cost-loan_impaired-dividend_impairment;cost=0.;paidin=0.
   liquidation={'cash_before_liquidation':cash_before_liquidation,'mother_cash_before_liquidation':mother_cash_before_liquidation,'unpaid_dividend_face_impaired_not_cancelled':dividend_impairment,'pool_is_economic_budget_not_entity_legal_waterfall':True,'noncash_asset_components':dict(asset_ledger),'noncash_asset_book_budget':noncash_assets,'restricted_cash_in_pool':FACTS['restricted'],'restricted_cash_release_assumed_on_closure_not_dividend':True,'gross_recovery':recovery,'closure_cost':closure,'closure_paid':closure_paid,'closure_unpaid':closure_unpaid,'external_claims':external_claim,'external_paid':external_paid,'unpaid_external_claims':sum(external_unpaid.values()),'unpaid_external_by_class':dict(external_unpaid),'already_declared_claim':declared_claim,'already_declared_paid':declared_paid,'declared_paid_by_entity':declared_entity_paid,'parent_loan_paid':loan_paid,'loan_paid_by_entity':dict(liquidation_paid_by_entity),'unpaid_parent_loan_claim':loan,'equity_recovery_gross':equity_recovery,'NCI_capital_budget':nci_capital_budget,'NCI_equity_payment':minority,'parent_equity_recovery':parent_share,'parent_investment_writeoff':impair,'parent_old_declared_unpaid':olddiv,'parent_new_declared_unpaid':receivable}
   exited=True;project_books=dict.fromkeys(project_books,0.);project_wc=dict.fromkeys(project_wc,0.);mature_wc_book=0.;associate_book=0.;residual_book=0.;stress_wc_book=0.;asset_ledger=dict.fromkeys(asset_ledger,0.)
  natural_exit={}
  if y==2057+c['end_shift'] and not exited:
   retired_cost=.133112+sum(z['parent_new_equity_cost'] for z in rows)+new_equity
   available=max(0.,sourcecash['africa']-.1);natural_declared_paid=0.;left=available
   for item in pending:
    if item[2]=='africa':
     paid=min(left,item[1]);item[1]-=paid;left-=paid;receivable-=paid;natural_declared_paid+=paid
   dividend_impairment=sum(x[1] for x in pending if x[2]=='africa');pre-=dividend_impairment
   debt_recovery=min(left,loans['africa']);equity_recovery=max(0.,left-debt_recovery)
   sourcecash['africa']-=available;subcash-=available;pc+=available;loans['africa']-=debt_recovery;loan-=debt_recovery
   loan_impaired=loans['africa'];pre+=equity_recovery-retired_cost-loan_impaired;cost-=retired_cost
   closing_cost=min(.1,max(0.,sourcecash['africa']));sourcecash['africa']-=closing_cost;subcash-=closing_cost;cash-=closing_cost
   natural_exit={'declared_dividend_paid':natural_declared_paid,'unpaid_declared_face':dividend_impairment,'declared_dividend_impairment':dividend_impairment,'entity':'中非国际有限期项目预算关闭','equity_cost_retired':retired_cost,'available_after_costs':available,'parent_loan_cash_recovery':debt_recovery,'equity_recovery':equity_recovery,'unpaid_parent_loan_claim':loans['africa'],'loan_carrying_value_impaired':loan_impaired,'claim_not_cancelled':True,'contract_asset_recovery':0.,'mother_realized_gain_loss':equity_recovery-retired_cost-loan_impaired,'closure_cash_cost':closing_cost}
  # Cash insolvency is recorded as arrears, never silently funded with unlimited debt.
  if min(cash,pc,*sourcecash.values()) < -1e-8:
   raise FundingFailure('Unfunded actual payment-source cash; no clipping: year=%s parent=%s group=%s sources=%s'%(y,pc,cash,sourcecash))
  desired=c['payout'][t-1]*SHARES if t<=5 else max(0.,cash-c['reserve'])
  if exited: desired=max(0.,cash-arrears)
  distributable=max(0.,pre)
  payout=min(desired,distributable,max(0.,pc-(0. if exited else c['parent_reserve'])),max(0.,cash-(0. if exited else c['reserve'])-arrears))
  capital_return=max(0.,payout-max(0.,pre)) if exited else 0.
  if exited: payout=min(desired,max(0.,pc),max(0.,cash-arrears));capital_return=max(0.,payout-max(0.,pre))
  pre-=payout-capital_return;pc-=payout;cash-=payout
  # Operating pool cash identity; any unresolved intercompany timing remains explicitly identified.
  bridge=cash-(pc+subcash)
  pending_liability={u:sum(x[1] for x in pending if x[2]==u)+(olddiv if u=='domestic' else 0.) for u in sourcecash}
  if exited and not liquidation:assert draw==0. and newloan==0. and new_equity==0.
  assert abs(sum(loans.values())-loan)<1e-8
  assert abs(sum(pending_liability.values())-olddiv-receivable)<1e-8
  row={'external_unpaid_by_class':dict(external_unpaid),'closure_cost_unpaid':closure_unpaid,'declared_payables_by_source':pending_liability,'pending_dividend_original_records':[x[:] for x in pending if x[1]>1e-12],'dividend_receivable_impairment':dividend_impairment,'pending_dividend_records':[[min(t-x[0],c['remit_delay']),x[1],x[2]] for x in pending if x[1]>1e-12],'asset_book_open':asset_open,'asset_book_before_liquidation':asset_total_before_liquidation,'asset_book_change':asset_change,'asset_ledger_close':dict(asset_ledger),'asset_movements':asset_movements,'project_WC_book_budget':dict(project_wc),'stress_WC_book_budget':stress_wc_book,'restricted_cash_budget':min(FACTS['restricted'],cash) if not exited else 0.,'exited':exited,'year':y,'index':t,'opening_group_cash':startcash,'ending_group_cash':cash,'opening_parent_cash':startpc,'ending_parent_cash':pc,'parent_RE_open':startpre,'parent_RE_close':pre,'parent_statreserve':pres,'source_retained_profit_budget':dict(subre),'domestic_statreserve_budget':source_statreserve,'source_cash':subcash,'source_cash_by_entity_budget':dict(sourcecash),'loans_by_entity':dict(loans),'loan_repaid_by_entity':loan_repayments,'source_declared':declarations,'source_declared_total':totaldecl,'new_dividend_cash_collected':collect,'old_dividend_cash_collected':collect_old,'old_dividend_receivable':olddiv,'new_dividend_receivable':receivable,'parent_loan_open':loan_open,'parent_loan_close':loan,'parent_loan_impairment':loan_impaired,'parent_loan_carrying_value':loan-loan_impaired,'parent_loan_repaid':lr,'parent_new_loan':newloan,'additional_source_support':support_by_entity,'parent_new_equity_cost':new_equity,'parent_investment_cost_close':cost,'parent_paid_in_cost_cumulative':paidin,'parent_investment_impairment':impair,'parent_supply':parent_supply,'parent_subsidiary_net_settlement_budget':c['parent_net_payment']*(t<=5),'cash_timing_reconciliation':bridge,'operating_cash':op['cash_before_growth'],'net_profit_budget':profit,'newcapital':capex,'cash_tax':op['tax'],'interest':interest,'bank_repaid':repaybank,'priority_repaid':repaypref,'lease_repaid':repaylease,'bank_draw':draw,'bank_end':bank,'priority_end':pref,'lease_end':lease,'other_external_obligation_paid':obligation,'wc_stress_change':wcstress,'extra_external_settlement':extra_external,'normalization_WC_payment':normalization_out,'NCI_cash':op['NCI_profit_cash'],'NCI_capital':op['NCI_newcapital'],'ordinary_payout':payout,'liquidation_capital_return':capital_return,'distribution_per_share':payout/SHARES,'arrears':arrears,'liquidation':liquidation,'natural_exit':natural_exit,'projects':op['project_detail'],'associate_cost_basis_retired':associate_basis_release,'associate_recovery':op['mine_exit'] if not exited else 0.,'project_asset_book_budget':dict(project_books),'project_asset_retirement_loss':project_writeoff,'mature_WC_book_budget':mature_wc_book,'mature_fixed_operating_asset_budget':11. if not exited else 0.,'annual_legal_budgets_not_undisclosed_actuals':True}
  if not liquidation and not exited:
   expected=startcash+op['cash_before_growth']-capex-interest-repaybank-repaypref-repaylease-obligation-wcstress-extra_external-normalization_out+draw-payout-natural_exit.get('closure_cash_cost',0.)
   assert abs(expected-cash)<1e-7
  assert min(sourcecash.values())>=-1e-8
  assert (exited or payout<=distributable+1e-8) and payout>=0 and op['tax']>=0
  assert abs(loan-(loan_open+newloan-lr-(liquidation.get('parent_loan_paid',0))-natural_exit.get('parent_loan_cash_recovery',0.)))<1e-7
  pv+=payout/(1+c['r'])**t;rows.append(row)
 # Tail: fully explicit horizon, then normalized affine state proof against a longer run, not prefix equality.
 last=rows[-1];tail=0. if exited else last['ordinary_payout']/c['r']
 pv+=tail/(1+c['r'])**years
 terminal5=(pv-sum(rows[i]['ordinary_payout']/(1+c['r'])**(i+1) for i in range(5)))*(1+c['r'])**5/SHARES
 return {'configuration':original,'freeze_first5':freeze_first5,'value_per_share':pv/SHARES,'distribution_5':[r['distribution_per_share'] for r in rows[:5]],'terminal_y5':terminal5,'terminal_PV_share':(terminal5/(1+c['r'])**5)/(pv/SHARES) if pv else 0.,'rows':rows,'tail':{'year':2026+years,'annual_distribution':last['ordinary_payout'],'terminal_value':tail,'PV':tail/(1+c['r'])**years,'affine_state':{'cash':last['ending_group_cash'],'parent_cash':last['ending_parent_cash'],'RE':last['parent_RE_close'],'loan':last['parent_loan_close'],'debt':last['bank_end']+last['priority_end']+last['lease_end'],'cost':last['parent_investment_cost_close'],'receivables':last['old_dividend_receivable']+last['new_dividend_receivable'],'domestic_RE':last['source_retained_profit_budget']['domestic'],'singapore_RE':last['source_retained_profit_budget']['singapore'],'africa_RE':last['source_retained_profit_budget']['africa'],'parent_statreserve':last['parent_statreserve'],'source_cash':last['source_cash'],'domestic_statreserve':last['domestic_statreserve_budget'],'loan_impairment':last['parent_loan_impairment'],'mature_fixed_operating_assets':last['mature_fixed_operating_asset_budget'],'mature_WC':last['mature_WC_book_budget'],'paidin_cost':last['parent_paid_in_cost_cumulative'],**{'cash_'+k:v for k,v in last['source_cash_by_entity_budget'].items()},**{'loan_'+k:v for k,v in last['loans_by_entity'].items()},**{'project_'+k:v for k,v in last['project_asset_book_budget'].items()}}}}

def main():
 results={n:run(config(n)) for n in SCENARIOS}
 results['terminal_low_same_y5']=run(config('core_low'),freeze_first5=True)
 results['terminal_high_same_y5']=run(config('core_high'),freeze_first5=True)
 for n in ('terminal_low_same_y5','terminal_high_same_y5'):
  assert results[n]['rows'][4]==results['base']['rows'][4]
  for k in ('ending_group_cash','ending_parent_cash','parent_RE_close','parent_loan_close','parent_investment_cost_close','bank_end','priority_end','lease_end','old_dividend_receivable','new_dividend_receivable'):
   assert abs(results[n]['rows'][4][k]-results['base']['rows'][4][k])<1e-8
 checks={}
 for name in results:
  a=results[name];b=run(config('core_low' if name=='terminal_low_same_y5' else 'core_high' if name=='terminal_high_same_y5' else name),140,freeze_first5=name.startswith('terminal_'))
  dif={k:b['tail']['affine_state'][k]-v for k,v in a['tail']['affine_state'].items()}
  extra_keys=['external_unpaid_by_class','closure_cost_unpaid','declared_payables_by_source','pending_dividend_records','asset_ledger_close','project_WC_book_budget','stress_WC_book_budget','restricted_cash_budget','exited','dividend_receivable_impairment','source_retained_profit_budget','source_cash_by_entity_budget','loans_by_entity','old_dividend_receivable','new_dividend_receivable','parent_investment_impairment','arrears']
  state_equal=all(a['rows'][-1][k]==b['rows'][-1][k] for k in extra_keys)
  assert state_equal and max(abs(v) for v in dif.values())<1e-8 and abs(b['value_per_share']-a['value_per_share'])<1e-8,(name,{k:(a['rows'][-1][k],b['rows'][-1][k]) for k in extra_keys if a['rows'][-1][k]!=b['rows'][-1][k]},dif)
  checks[name]={'complete_additional_state_equal':state_equal,'additional_state_100':{k:a['rows'][-1][k] for k in extra_keys},'additional_state_140':{k:b['rows'][-1][k] for k in extra_keys},'100_vs_140_PV_diff':b['value_per_share']-a['value_per_share'],'state_deltas':dif,'distribution_delta':b['tail']['annual_distribution']-a['tail']['annual_distribution']}
 # Hand-computable test is sent through the same operating chain.
 c=copy.deepcopy(BASE);c.update(logrev=10,logmargin=.2,traderev=0,opex=0,growth=0,project_scale=0)
 z=operate(c,2027); expected=2*(.25*.85+.30*.75+.45*.83)-.05
 assert abs(sum(z['earnings'].values())-.5-expected)<1e-9
 fixture=copy.deepcopy(BASE);fixture.update(exit_year=2029,exit_recovery=0.,remit_delay=3)
 audit_exit=run(fixture);audit_exit_long=run(fixture,140)
 event=next(row for row in audit_exit['rows'] if row['liquidation'])
 assert event['new_dividend_receivable']>0 and event['old_dividend_receivable']>0
 assert abs(sum(event['declared_payables_by_source'].values())-event['old_dividend_receivable']-event['new_dividend_receivable'])<1e-8
 assert abs(audit_exit['value_per_share']-audit_exit_long['value_per_share'])<1e-8
 assert audit_exit['tail']['affine_state']==audit_exit_long['tail']['affine_state']
 assert all(audit_exit['rows'][-1][k]==audit_exit_long['rows'][-1][k] for k in extra_keys)
 bad=copy.deepcopy(BASE);bad.update(external_settlement=100.,bank_limit=0.)
 try:run(bad,1)
 except FundingFailure as exc:failure_test={'passed':True,'actual_error':str(exc)}
 else:raise AssertionError('funding counterexample silently accepted')
 print(json.dumps({'declared_claim_exit_fixture':audit_exit,'funding_fail_closed_counterexample':failure_test,'opening_asset_allocation':{'disclosed_Q3_gross_noncash':68.774558805,'gross_mature_WC':23.2033589927,'mature_fixed':11.,'associate':7.1677873957,'project_fixed_gross':sum(p['cost']/(p['own'] if p['own']>=.5 else 1.) for p in PROJECTS),'project_WC_gross':.6,'residual_reconciles_not_precision_project_actuals':68.774558805-23.2033589927-11.-7.1677873957-sum(p['cost']/(p['own'] if p['own']>=.5 else 1.) for p in PROJECTS)-.6},'information_cutoff':ASOF,'model_as_of':ASOF,'units':'CNY 100 million, shares 100 million','facts':FACTS,'projects':PROJECTS,'results':results,'tail_validation':checks,'hand_operating_chain':{'pretax':2,'after_tax_excluding_mine':expected,'actual':sum(z['earnings'].values())-.5}},ensure_ascii=False,sort_keys=True,indent=2))
if __name__=='__main__':main()
