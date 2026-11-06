#!/usr/bin/env python3
"""FII common-holder cash ledger. CNY billion and billion shares; stdlib only.
gross margins mean cash contribution BEFORE depreciation and occupancy rentals;
not the reported accounting gross margin. Forecast pools are economic constraints, not legal-entity audited budgets.
No security quotes. Complete states, no omitted tail. stdout canonical JSON.
"""
import copy,json,math,sys
ASOF='2026-10-30T11:00:00Z'
OLD_DIVIDEND_DEBTORS={'天津富联':3.5,'深圳富桂':1.45,'郑州富联':1.,'河南裕展':.905,'晋城富晋':.8,'南宁富桂':.04}
ACTUAL={'cash':97.912418,'cash_equivalents':97.651199,'ar':224.822057,'inventory':188.940311,'ap':220.655866,'advance':2.914027,'ppe':46.353803,'rou':4.739994,'bank_debt':122.948350,'lease_and_current':5.441847,'equity':190.574981,'nci_equity':.326502,'opening_dtl':.140210,'parent_h1_cash':24.150647,'parent_h1_cash_equivalents':24.042892,'parent_h1_re':15.247727,'parent_reserve':8.453908,'paid_aug_dividend':12.8986599846,'paid_buyback':1.00000521768,'registered_shares':19.844092284,'treasury_shares':.015833353,'foreign_h1_cash':23.065560,'foreign_h1_unremitted_earnings':67.511922,'factored_h1_outstanding':48.564210,'factoring_h1_volume':161.344998,'factoring_h1_cost':.667295,'financial_assets':5.304683}
BASE={'method':'product','cloud':1100.,'network':370.,'cloud_margin':.071,'network_margin':.097,'opex_ratio':.018,'growth':[.18,.13,.09,.065,.045,.03,.02], 'mature_growth':.015,'k':.095,'tax':.17,'cash_yield':.012,'interest':.044,'factoring_share':.29,'factoring_cost':.00414,'ar_days':77.,'inventory_days':66.,'ap_days':78.,'advance_ratio':.003,'cap_ratio':.037,'depr_rate':.18,'lease_cost':.002,'foreign_profit_share':.72,'foreign_assets_share':.76,'foreign_cash':23.065560,'foreign_re':67.511922,'domestic_re':30.,'parent_cash_delta':0.,'parent_cash_min':2.,'parent_payout':.55,'foreign_delay':3,'remit_ratio':.8,'remit_tax':.07,'sub_payout':.9,'debt_cap_ratio':.12,'rollover':1.,'initial_extra_cash':0.,'factoring_active':1.,'sell_treasury_year':2,'sale_value_fraction':1.,'financial_recovery':1.,'financial_years':5,'financial_cost_fraction':.8,'secondary_gross':112.,'secondary_increment':[15.,12.,9.,6.,4.,3.,2.],'secondary_expense':27.,'secondary_capital_turnover':7.,'secondary_wc_to_gross':2.05,'stress_loss':0.,'legal_cost':0.,'parent_start_loss':0.,'policy_cash_factor':1.,'old_dividend_face':7.695,'old_dividend_paid_fraction':0.,'parent_shutdown_cost':.5}

def reserve(re,profit,res,cap,rate):
 # Losses are absorbed before statutory reserve; pre-existing deficits are not distributable.
 eligible=max(0.,profit+min(0.,re)); add=min(max(0.,cap*.5-res),eligible*rate)
 return re+profit-add,res+add,add

def operating(p,t,prev):
 g=p['growth'][min(t-2,len(p['growth'])-1)] if t>1 and t<=len(p['growth'])+1 else p['mature_growth']
 if p['method']=='product':
  cloud=p['cloud'] if t==1 else prev['cloud']*(1+g)
  network=p['network'] if t==1 else prev['network']*(1+(g*.4 if t<=8 else p['mature_growth']))
  revenue=cloud+network; gross=cloud*p['cloud_margin']+network*p['network_margin']; expense=revenue*p['opex_ratio']
 else:
  gross=p['secondary_gross'] if t==1 else prev['gross']+(p['secondary_increment'][t-2] if t<=8 else prev['gross']*p['mature_growth'])
  expense=p['secondary_expense']*(1.035**min(t-1,7))*(1+p['mature_growth'])**max(0,t-8)
  # Auxiliary revenue only supports explicit procurement cost and fees; gross is an independent input.
  revenue=gross/.072;cloud=0.;network=0.
 cogs=revenue-gross; factor_volume=revenue*p['factoring_share']*p['factoring_active']; fee=factor_volume*p['factoring_cost']
 sold=factor_volume*55/365
 ar=revenue*p['ar_days']/365-sold
 inv=cogs*p['inventory_days']/365; ap=cogs*p['ap_days']/365; advance=revenue*p['advance_ratio']
 wc=ar+inv-ap-advance
 if p['method']=='value_added':
  # Net working-capital budget assumes normal factoring. Restore unsold receivables when volume falls, independently of fee rate.
  wc=gross*p['secondary_wc_to_gross']+revenue*p['factoring_share']*55/365*(1-p['factoring_active']); ar=wc-inv+ap+advance
 cap=revenue*p['cap_ratio'] if p['method']=='product' else gross/p['secondary_capital_turnover']*3.7
 if t<=2: gross-=p['stress_loss']*revenue
 lease=revenue*p['lease_cost']; legal=p['legal_cost'] if t<=3 else 0.
 return dict(cloud=cloud,network=network,revenue=revenue,gross=gross,expense=expense,factoring_volume=factor_volume,factoring_fee=fee,factored_outstanding=sold,ar=ar,inventory=inv,ap=ap,advance=advance,wc=wc,capital=cap,lease_cash=lease,legal_cost=legal)

def run(params=None,years=240,actual=None):
 p=copy.deepcopy(BASE);p.update(params or {});a=copy.deepcopy(ACTUAL if actual is None else actual)
 pc=a['parent_h1_cash_equivalents']-a['paid_aug_dividend']-a['paid_buyback']+p['parent_cash_delta']
 # Known H1 statutory RE already includes declared annual dividend; payment is not another earnings deduction.
 pr=a['parent_h1_re']-p['parent_start_loss']; ps=a['parent_reserve']; cost=[35.,24.421977]
 totaldebt=a['bank_debt']+a['lease_and_current']; initialwc=a['ar']+a['inventory']-a['ap']-a['advance']
 other_liabilities=a['cash_equivalents']+initialwc+a['ppe']+a['rou']+a['financial_assets']-totaldebt-a['equity']-a['nci_equity']
 # Residual is reconciled net operating/tax/provision and other-asset bridge, not another debt face.
 assert other_liabilities>0
 pools=[]
 for j,name in enumerate(['domestic_manufacturing','overseas_CNT_Ingrasys_and_other']):
  q=p['foreign_assets_share'] if j else 1-p['foreign_assets_share']; profitshare=p['foreign_profit_share'] if j else 1-p['foreign_profit_share']
  cash=p['foreign_cash'] if j else a['cash_equivalents']-pc-p['foreign_cash']
  pools.append(dict(name=name,cash=cash,wc=initialwc*q,capital=a['ppe']*q,debt=a['bank_debt']*(.985 if j else .015)+a['lease_and_current']*q,rou=a['rou']*q,re=p['foreign_re'] if j else p['domestic_re'],reserve=0. if j else 5.,legal_capital=15. if j else 30.,share=q,profitshare=profitshare,other_liabilities=other_liabilities*q,alive=True))
 # H1 old dividend is already in parent's retained earnings and subsidiaries' declared payable.
 # Paid fraction is a conditional redistribution WITHIN group cash, never extra consolidated assets or new profit.
 old_paid=p['old_dividend_face']*p['old_dividend_paid_fraction'];pc+=old_paid;pools[0]['cash']-=old_paid
 old_face=p['old_dividend_face']-old_paid;pools[0]['old_dividend_payable']=old_face;pools[1]['old_dividend_payable']=0.
 parent_active=True;parent_unpaid_claim=0.;old_impaired=0.
 pc+=p['initial_extra_cash']; registered=a['registered_shares']; shares=registered-a['treasury_shares']; rows=[]; pv=0.; prev={}; financial=a['financial_assets']; financialcost=financial*p['financial_cost_fraction']; nci_share=.002
 for t in range(1,years+1):
  op=operating(p,t,prev); prev=op
  opening_parent=pc; opening_pr=pr; opening_ps=ps; parent_interest=pc*p['cash_yield'] if parent_active else 0.; pc+=parent_interest*.75
  admin_due=.08*(1+p['mature_growth'])**(t-1) if parent_active else 0.
  admin_paid=min(pc,admin_due);pc-=admin_paid;parent_unpaid_claim+=admin_due-admin_paid
  parent_profit=parent_interest*.75-admin_due;old_receipt=0.;old_writeoff=0.;shutdown_cost=0.;shutdown_paid=0.;capital_return=0.;parent_financial_exit=0.;parent_exit_gain=0.;parent_arrears_paid=0.
  financial_receipt=0.; financial_gain=0.
  if parent_active and t<=p['financial_years']:
   face=3.709172/p['financial_years']; basis=face*p['financial_cost_fraction']; proceeds=face*p['financial_recovery']; gain=proceeds-basis; tax=max(0.,gain)*.25
   financial_receipt=proceeds-tax; financial_gain=proceeds-face-tax;pc+=financial_receipt;parent_profit+=financial_gain
  subrows=[]; upstream=0.; injections=0.; totalminority=0.
  for j,s in enumerate(pools):
   opening=copy.deepcopy(s)
   if not s['alive']:
    subrows.append({'opening':opening,'closing':copy.deepcopy(s),'inactive':True});continue
   q=s['share']; b=s['profitshare']; targetwc=op['wc']*q; targetcapital=op['capital']*q
   depreciation=s['capital']*p['depr_rate']; capex=max(0.,targetcapital-s['capital']+depreciation)
   # Original lease liabilities paid over five years; new recurring rentals are charged in EBIT, no new free lease financing.
   rou_depreciation=min(s['rou'],a['rou']*q/5) if t<=5 else 0.
   lease_principal=(a['lease_and_current']/5)*q if t<=5 else 0.
   interest=s['debt']*p['interest']; finance_income=s['cash']*p['cash_yield']
   # Existing lease principal and imputed interest are included in aggregate occupancy cash; charge only the residual as new rental expense.
   old_lease_face=max(0.,a['lease_and_current']*(1-(t-1)/5))*q if t<=5 else 0.
   new_rent=max(0.,op['lease_cash']*b-lease_principal-old_lease_face*p['interest'])
   ebit=(op['gross']-op['expense']-op['factoring_fee']-op['legal_cost'])*b-new_rent-depreciation-rou_depreciation
   pretax=ebit-interest+finance_income; tax=max(0.,pretax)*p['tax']; profit=pretax-tax
   newre,newreserve,reserve_add=reserve(s['re'],profit,s['reserve'],s['legal_capital'],0. if j else .1)
   delta_wc=targetwc-s['wc']; other_payment=min(s['other_liabilities'],((other_liabilities-a['opening_dtl'])*q/5 if t<=5 else 0.)+(a['opening_dtl']*q/p['financial_years'] if t<=p['financial_years'] else 0.))
   sub_financial_face=(financial-3.709172)*q/p['financial_years'] if t<=p['financial_years'] else 0.
   sub_financial_basis=sub_financial_face*p['financial_cost_fraction']; sub_financial_proceeds=sub_financial_face*p['financial_recovery']; sub_financial_gain=sub_financial_proceeds-sub_financial_face; sub_financial_tax=max(0.,sub_financial_proceeds-sub_financial_basis)*.25
   dtl_reversal=a['opening_dtl']*q/p['financial_years'] if t<=p['financial_years'] else 0.
   # Old DTL is in the residual opening liability bridge. Its reversal is noncash; offset its scheduled bridge settlement, never pay the same tax twice.
   profit+=sub_financial_gain-sub_financial_tax+dtl_reversal
   newre,newreserve,reserve_add=reserve(s['re'],profit,s['reserve'],s['legal_capital'],0. if j else .1)
   before=s['cash']+profit+depreciation+rou_depreciation-capex-delta_wc-lease_principal-other_payment+sub_financial_face
   lease_closing=max(0.,old_lease_face-lease_principal)
   mandatory=max(0.,s['debt']-old_lease_face)*(1-p['rollover'])
   debt_after_due=max(0.,s['debt']-lease_principal-mandatory);before-=mandatory
   needcash=op['revenue']*.014*q*p['policy_cash_factor']
   creditcap=op['revenue']*p['debt_cap_ratio']*(.985 if j else .015)
   draw=min(max(0.,needcash-before),max(0.,creditcap-(debt_after_due-lease_closing))) if p['rollover']>0 else 0.
   before+=draw; debt_after_due+=draw
   injection=0.
   if before<needcash:
    injection=min(max(0.,pc-p['parent_cash_min']),needcash-before);pc-=injection;before+=injection;injections+=injection;cost[j]+=injection;s['legal_capital']+=injection
   failed=before < -1e-8
   if failed:
    # Real inability to settle mandatory obligations: economic recovery, not a negative-cash going concern.
    recover_wc=(op['ar']*.85+op['inventory']*.60-op['ap']-op['advance'])*q
    remaining_financial=(financial-3.709172)*q*max(0.,1-t/p['financial_years'])
    financial_exit=remaining_financial*p['financial_recovery']-max(0.,remaining_financial*(p['financial_recovery']-p['financial_cost_fraction']))*.25
    trade_claim=(op['ap']+op['advance'])*q
    gross_recovery=max(0.,before+mandatory+recover_wc+trade_claim+targetcapital*.4+financial_exit)
    expenses=.08*gross_recovery; distributable=max(0.,gross_recovery-expenses)
    bank_claim=debt_after_due+mandatory; other_claim=max(0.,s['other_liabilities']-other_payment); old_claim=s['old_dividend_payable'];claims=bank_claim+other_claim+trade_claim+old_claim
    creditor_payment=min(distributable,claims); unpaid=max(0.,claims-creditor_payment)
    unpaid_bank=unpaid*bank_claim/claims if claims else 0.;unpaid_trade=unpaid*trade_claim/claims if claims else 0.;unpaid_old=unpaid*old_claim/claims if claims else 0.;unpaid_other=unpaid-unpaid_bank-unpaid_old
    old_recovered=old_claim-unpaid_old;pc+=old_recovered;old_receipt+=old_recovered;old_face-=old_recovered;old_impaired+=unpaid_old;old_writeoff+=unpaid_old;parent_profit-=unpaid_old
    net=max(0.,distributable-claims)
    minority=net*nci_share if j==0 else 0.; owned=net-minority
    exitgain=owned-cost[j]; exittax=max(0.,exitgain)*.25; receipt=owned-exittax
    parent_profit+=exitgain-exittax;pc+=receipt;upstream+=receipt;totalminority+=minority;cost[j]=0.
    # Inactive economic shutdown is not legal discharge: unpaid creditor face persists in every later state.
    s.update(old_dividend_payable=unpaid_old,cash=0.,wc=0.,capital=0.,rou=0.,debt=unpaid_bank,re=-unpaid,reserve=0.,other_liabilities=unpaid_other,unpaid_creditor_claim=unpaid,unpaid_trade_claim=unpaid_trade,claims_not_legally_extinguished=True,alive=False)
    subrows.append(dict(opening=opening,failed=True,operating_profit=profit,cash_before_finance=before,mandatory_repayment=mandatory,draw=draw,injection=injection,liquidation_wc=recover_wc,liquidation_gross=gross_recovery,liquidation_expense=expenses,old_dividend_claim=old_claim,old_dividend_received=old_recovered,old_dividend_impaired=unpaid_old,creditor_claims=claims,trade_claim=trade_claim,creditor_payment=creditor_payment,unpaid_claim=unpaid,exit_gain=exitgain,exit_tax=exittax,upstream=receipt,minority=minority,closing=copy.deepcopy(s)));continue
   repay=min(max(0.,before-needcash),max(0.,debt_after_due-lease_closing));before-=repay;debt_after_due-=repay
   # Old declared dividends are a settlement, not a new dividend and not new parent earnings.
   old_payment=min(s['old_dividend_payable'],max(0.,before-needcash));before-=old_payment;s['old_dividend_payable']-=old_payment;pc+=old_payment;old_receipt+=old_payment;old_face-=old_payment
   ratio=p['sub_payout'] if j==0 else (0. if t<=p['foreign_delay'] else p['remit_ratio'])
   dividend=min(max(0.,newre),max(0.,before-needcash))*ratio
   before-=dividend;newre-=dividend;minority=dividend*nci_share if j==0 else 0.
   withholding=(dividend-minority)*p['remit_tax'] if j else 0.;receipt=dividend-minority-withholding
   parent_profit+=receipt;pc+=receipt;upstream+=receipt;totalminority+=minority
   s.update(cash=before,wc=targetwc,rou=max(0.,s['rou']-rou_depreciation),capital=opening['capital']+capex-depreciation,debt=debt_after_due,re=newre,reserve=newreserve,other_liabilities=max(0.,s['other_liabilities']-other_payment))
   subrows.append(dict(opening=opening,old_dividend_payment=old_payment,new_rent=new_rent,old_lease_face=old_lease_face,ebit=ebit,interest=interest,finance_income=finance_income,tax=tax,profit=profit,depreciation=depreciation,rou_depreciation=rou_depreciation,capex=capex,delta_wc=delta_wc,other_payment=other_payment,financial_face=sub_financial_face,financial_basis=sub_financial_basis,financial_gain=sub_financial_gain,financial_tax=sub_financial_tax,dtl_reversal=dtl_reversal,lease_principal=lease_principal,mandatory_repayment=mandatory,draw=draw,injection=injection,voluntary_repayment=repay,reserve_add=reserve_add,dividend=dividend,withholding=withholding,minority=minority,upstream=receipt,cash_minimum=needcash,failed=False,closing=copy.deepcopy(s)))
  # Economic cessation after ALL operating pools fail. No assertion about a court liquidation date.
  # Realize remaining parent investments once, pay finite wind-down costs, retain unpaid creditor faces.
  shutdown=parent_active and not any(z['alive'] for z in pools)
  if shutdown:
   remaining=3.709172*max(0.,1-t/p['financial_years']);proceeds=remaining*p['financial_recovery'];exit_tax=max(0.,proceeds-remaining*p['financial_cost_fraction'])*.25
   parent_financial_exit=proceeds-exit_tax;parent_exit_gain=proceeds-remaining-exit_tax;pc+=parent_financial_exit;parent_profit+=parent_exit_gain
   shutdown_cost=p['parent_shutdown_cost'];parent_profit-=shutdown_cost;parent_unpaid_claim+=shutdown_cost
   shutdown_paid=min(pc,parent_unpaid_claim);pc-=shutdown_paid;parent_unpaid_claim-=shutdown_paid
   # Residual common-holder proceeds are capital realization, not distributable current earnings.
   capital_return=pc if parent_unpaid_claim==0 else 0.;pc-=capital_return;parent_active=False
  if parent_active:
   parent_arrears_paid=min(pc,parent_unpaid_claim);pc-=parent_arrears_paid;parent_unpaid_claim-=parent_arrears_paid
  cancelled=0.
  if t==3 and p['sell_treasury_year']>3:
   cancelled=a['treasury_shares'];registered-=cancelled
  pr,ps,pres=reserve(pr,parent_profit,ps,registered,.1)
  # Treasury issuance consideration is capital not income: evaluated at a fixed non-quote conditional accounting amount.
  sale=0.
  if parent_active and t==p['sell_treasury_year']:
   sale=a['paid_buyback']*p['sale_value_fraction'];pc+=sale;shares+=a['treasury_shares']
  pd=min(max(0.,pr),max(0.,pc-p['parent_cash_min']))*p['parent_payout'];pc-=pd;pr-=pd
  dps=(pd+capital_return)/shares; discounted=dps/(1+p['k'])**t;pv+=discounted
  for z in subrows:
   for endpoint in ['opening','closing']:
    state=z[endpoint];state['old_dividend_debtors']={name:amount/7.695*state['old_dividend_payable'] for name,amount in OLD_DIVIDEND_DEBTORS.items()} if state['name']=='domestic_manufacturing' else {}
  row=dict(year=t,operating=op,subsidiaries=subrows,parent=dict(opening_cash=opening_parent,active=parent_active,economic_equity_realized=not parent_active,legal_dissolution_not_assumed=True,arrears_paid=parent_arrears_paid,admin_due=admin_due,admin_paid=admin_paid,unpaid_creditor_claim=parent_unpaid_claim,old_dividend_gross_claim=old_face,old_dividend_impairment=old_impaired,old_dividend_receipt=old_receipt,old_dividend_writeoff=old_writeoff,shutdown=shutdown,shutdown_cost=shutdown_cost,shutdown_creditor_payment=shutdown_paid,financial_exit_cash=parent_financial_exit,financial_exit_gain=parent_exit_gain,capital_return=capital_return,opening_re=opening_pr,opening_reserve=opening_ps,interest=parent_interest,profit=parent_profit,financial_cash=financial_receipt,financial_gain=financial_gain,upstream=upstream,injections=injections,investment_cost=list(cost),reserve_add=pres,registered_shares=registered,treasury_cancelled=cancelled,treasury_sale_cash=sale,closing_cash=pc,closing_re=pr,closing_reserve=ps,dividend=pd,shares=shares,dps=dps,minority_paid=totalminority),discounted_dividend=discounted,cumulative_pv=pv)
  assert pc>=-1e-8 and all(z['cash']>=-1e-8 for z in pools),('negative cash',t)
  rows.append(row)
 first5=sum(r['discounted_dividend'] for r in rows[:5]); terminal=(pv-first5)*(1+p['k'])**5
 return {'parameters':p,'years':years,'value_per_share':pv,'year5_continuation_same_path':terminal,'dps_first5':[r['parent']['dps'] for r in rows[:5]],'rows':rows,'last_state':rows[-1]}

def scenarios():
 return {'base':{},'core_low':{'cloud':980.,'network':345.,'cloud_margin':.066,'network_margin':.093,'growth':[.14,.10,.075,.055,.04,.025,.018],'k':.105,'ar_days':80.,'inventory_days':69.,'foreign_delay':5,'remit_tax':.10},'core_high':{'cloud':1250.,'network':400.,'cloud_margin':.076,'network_margin':.101,'growth':[.22,.16,.11,.075,.05,.03,.02],'k':.09,'ar_days':75.,'inventory_days':64.,'foreign_delay':2},'secondary_low':{'method':'value_added','secondary_gross':98.,'secondary_increment':[10.,8.,6.,5.,3.,2.,1.5],'secondary_expense':27.,'k':.105,'secondary_wc_to_gross':2.2},'secondary_base':{'method':'value_added'},'secondary_high':{'method':'value_added','secondary_gross':127.,'secondary_increment':[19.,15.,10.,7.,5.,3.,2.],'secondary_expense':28.,'k':.09,'secondary_wc_to_gross':1.9},'cyclical':{'cloud':800.,'network':320.,'cloud_margin':.057,'network_margin':.087,'growth':[.0,.08,.08,.06,.04,.025,.02],'ar_days':95.,'inventory_days':90.,'k':.115},'structural':{'cloud':720.,'network':300.,'cloud_margin':.048,'network_margin':.075,'growth':[-.08,-.04,0.,.01,.015,.015,.015],'ar_days':105.,'inventory_days':95.,'k':.125,'debt_cap_ratio':.08},'optimistic':{'cloud':1400.,'network':420.,'cloud_margin':.083,'network_margin':.105,'growth':[.28,.20,.14,.09,.055,.03,.02],'k':.09},'k_plus_100bp':{'k':.105},'margin_minus_1pp':{'cloud_margin':.061,'network_margin':.087},'no_factoring':{'factoring_active':0.},'ar_plus_15days':{'ar_days':92.},'inventory_plus_20days':{'inventory_days':86.},'rollover_failure':{'rollover':0.,'debt_cap_ratio':0.},'foreign_delay_8':{'foreign_delay':8},'foreign_delay_15':{'foreign_delay':15},'foreign_low_upstream':{'remit_ratio':.25},'foreign_tax_20pct':{'remit_tax':.20},'parent_cash_minus_5':{'parent_cash_delta':-5.},'parent_cash_plus_5':{'parent_cash_delta':5.},'domestic_re_zero':{'domestic_re':0.},'foreign_re_zero':{'foreign_re':0.},'337_adverse':{'cloud_margin':.066,'legal_cost':1.,'growth':[.08,.1,.09,.065,.045,.03,.02]},'treasury_sale_half':{'sale_value_fraction':.5},'no_treasury_sale':{'sell_treasury_year':999},'financial_half_recovery':{'financial_recovery':.5},'financial_cost_zero':{'financial_cost_fraction':0.},'cash_yield_zero':{'cash_yield':0.},'interest_plus_200bp':{'interest':.064},'parent_loss_absorption':{'parent_start_loss':25.},'cash_buffer_double':{'policy_cash_factor':2.},'foreign_profit_90pct':{'foreign_profit_share':.90},'foreign_profit_55pct':{'foreign_profit_share':.55},'foreign_cash_plus_15':{'foreign_cash':38.065560},'foreign_cash_minus_15':{'foreign_cash':8.065560},'credit_cap_8pct':{'debt_cap_ratio':.08},'parent_fast_payout':{'parent_payout':.85},'parent_slow_payout':{'parent_payout':.25},'financial_release_20years':{'financial_years':20}}

def extended_scenarios():
 cases=scenarios()
 for name in ['base','core_low','core_high']:
  for paid in [0.5,1.]:cases[name+'_old_paid_'+str(paid)]={**cases[name],'old_dividend_paid_fraction':paid}
 for name in ['secondary_low','secondary_base','secondary_high']:
  for active in [0.,.5]:cases[name+'_factoring_'+str(active)]={**cases[name],'factoring_active':active}
 cases['severe_double_failure']={'rollover':0.,'debt_cap_ratio':0.,'stress_loss':.25,'ar_days':200.,'inventory_days':180.}
 cases['severe_unfunded_parent_exit']={**cases['severe_double_failure'],'parent_shutdown_cost':50.}
 return cases
