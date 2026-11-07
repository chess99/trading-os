#!/usr/bin/env python3
"""Orient Cable rolling annual common-holder model. CNY billion; shares billion.
Only stdlib; all inputs literal; no files read; deterministic full stdout.
Forecasts are budgets, not legal opinions or announced corporate actions.
"""
import copy,json,math
ASOF='2026-10-28T16:40:00+00:00'
P={
 'shares':.822558722,'issued':.824808488,'treasury':.002249766,
 'cash_p':1.65,'cash_s':.06291887586,'debt_p':.79071820392,'debt_s':.02,
 'group_equity':9.06193761806,'s_equity':.91009083278,'investment':.74858487228,'loan':.85282804308,
 'p_re':5.92387114978,'p_reserve':.41605095122,'p_capital':.824808488,
 'sub_reserve_rate':.1,'sub_reserve_cap':.5,'s_re':.17,'s_reserve':.02,'s_capital':.73,'s_registered_capital':.90,
 'ppe_p':2.4,'ppe_s':1.05,'other_p':.65,'other_s':.05,'wc_s':.62,
 'tax':.17,'loan_rate':.025,'debt_rate':.04,'cash_rate':.01,
 'grant_year':1,'grant_expense':[.017998128,.017998128,.017998128],
 'discount':.095,'max_debt':2.0,'issue_price':15.0,'sub_ownership':1.0,
 'contribution':[.139,0,0,0,0],'external_commitment':[.047,0,0,0,0],
 'payout':[.35,.4,.45,.5,.55,.62,.70,.78,.85,.9,.94,.97,1.0],
 'revenue':[[6.0,6.5,1.6],[6.4,7.2,1.8],[6.8,7.9,2.0],[7.2,8.6,2.1],[7.55,9.2,2.2]],
 'margin':[.10,.30,.28],'expense':.078,'wc_ratio':.29,'depr_rate':.08,
 'growth_capex':[.50,.50,.45,.40,.35,.28,.22,.16,.10,.05],
 'sub_profit_share':[.07,.09,.11,.13,.15,.17,.18,.19,.20],
 'growth_after5':.035,'fade_start':10,'steady_year':20,
 'aux_roic':[.175,.18,.185,.185,.18], 'aux_growth':[.07,.07,.06,.05,.04],
 'aux_steady_roic':.14,
 'exit':{'wc_recovery':.78,'ppe_recovery':.50,'other_recovery':.60,'employee':.16,'lease':.06,'cleanup':.05,'tax_rate':.17,'parent_extra_admin':.08},
}
SCENARIOS={
 'base':{},'holder_low':{'terminal_change_only':True,'margin_shift':-.006,'discount':.10},'holder_high':{'terminal_change_only':True,'margin_shift':.006,'discount':.09},'core_low':{'margin_shift':-.006,'discount':.10},'core_high':{'margin_shift':.006,'discount':.09},
 'cyclical':{'delay_years':3,'margin_shift_first':-.025,'wc_add_first':.07,'sales_factor_first':.85},
 'structural':{'margin_shift':-.045,'sales_factor':.85,'wc_add':.04,'growth_factor':.3,'long_margin_shift':-.025},
 'optimistic':{'margin_shift':.015,'sales_factor':1.06,'growth_factor':1.3},
 'capital_overrun':{'capex_multiplier':1.3,'margin_shift':-.003},'collections_stress':{'wc_add_first':.16,'delay_years':3},
 'sub_reserve_none':{'sub_reserve_rate':0},'sub_reserve_strict':{'sub_reserve_rate':.2,'sub_reserve_cap':1},'sub_re_zero':{'s_re':0},'sub_re_loss':{'s_re':-.30},
 'zero_grant_expense':{'grant_expense':[]},'double_grant_expense':{'grant_expense':[.035996256,.035996256,.035996256]},'no_treasury_grant':{'grant_year':999,'grant_expense':[]},'sub_registry_high':{'s_registered_capital':1.1},'parent_re_low':{'p_re':5.49511760014},'lower_sub_cash':{'cash_s':.02},
 'tax25':{'tax':.25},'no_upstream_3y':{'no_upstream':3},'no_upstream_12y':{'no_upstream':12},
 'issuance_stress':{'sales_factor_first':.55,'margin_shift_first':-.20,'wc_add_first':.20,'delay_years':3,'max_debt':.80},
 'exit_year3':{'exit_year':3,'sales_factor_first':.65,'margin_shift_first':-.14,'delay_years':3},
}
def near(a,b):
 assert abs(a-b)<2e-7*max(1,abs(a),abs(b)),(a,b)
def legal(re,res,cap,profit,rate=.1,ceiling=.5):
 # Profit first repairs accumulated losses; reserve only on remainder; cap at 50% capital.
 taxable_for_reserve=max(0,profit+min(0,re))
 transfer=min(max(0,ceiling*cap-res),rate*taxable_for_reserve)
 return re+profit-transfer,res+transfer,transfer

def initial(q):
 s={k:q[k] for k in ['shares','investment','loan']}
 s.update(cash_p=q['cash_p'],cash_s=q['cash_s'],debt_p=q['debt_p'],debt_s=q['debt_s'],
          re_p=q['p_re'],reserve_p=q['p_reserve'],capital_p=q['p_capital'],re_s=q['s_re'],reserve_s=q['s_reserve'],capital_s=q['s_capital'],
          ppe_p=q['ppe_p'],ppe_s=q['ppe_s'],other_p=q['other_p'],other_s=q['other_s'],wc_s=q['wc_s'],div_rec=0.0,div_pay=0.0)
 pe=q['group_equity']-q['s_equity']*q['sub_ownership']+q['investment']
 s['wc_p']=pe+q['debt_p']-q['cash_p']-q['investment']-q['loan']-q['ppe_p']-q['other_p']
 s['other_equity_p']=pe-s['re_p']-s['reserve_p']-s['capital_p']
 se=s['cash_s']+s['wc_s']+s['ppe_s']+s['other_s']-s['debt_s']-s['loan']
 s['treasury_remaining']=q['treasury']
 s['treasury_cost']=.10718588368
 s['capital_premium_p']=1.17063421689
 s['other_equity_residual_p']=s['other_equity_p']-s['capital_premium_p']+s['treasury_cost']
 s['other_equity_s']=se-s['re_s']-s['reserve_s']-s['capital_s']
 return s

def equity(s,sub=False):
 t='s' if sub else 'p'
 return s['re_'+t]+s['reserve_'+t]+s['capital_'+t]+s['other_equity_'+t]
def check(s):
 near(s['other_equity_p'],s['capital_premium_p']-s['treasury_cost']+s['other_equity_residual_p'])
 near(s['cash_p']+s['wc_p']+s['ppe_p']+s['other_p']+s['investment']+s['loan']+s['div_rec']-s['debt_p'],equity(s))
 near(s['cash_s']+s['wc_s']+s['ppe_s']+s['other_s']-s['debt_s']-s['loan']-s['div_pay'],equity(s,True))
 assert min(s['cash_p'],s['cash_s'],s['debt_p'],s['debt_s'],s['loan'],s['div_rec'],s['div_pay'])>-1e-8

def operations(y,prev,q,sc,method):
 rev=P['revenue'][min(y,5)-1][:]
 if y>5:
  rev=prev['revenues'][:]
  g=P['growth_after5']*sc.get('growth_factor',1)*max(0,(P['steady_year']-y)/(P['steady_year']-5))
  rev=[v*(1+g) for v in rev]
 else: rev=[v*sc.get('sales_factor',1) for v in rev]
 temporary=y<=sc.get('delay_years',0)
 if temporary and y<=5: rev=[v*sc.get('sales_factor_first',1) for v in rev]
 margins=[v+sc.get('margin_shift',0)+(sc.get('margin_shift_first',0) if temporary else 0) for v in P['margin']]
 fade=min(1,max(0,(y-P['fade_start'])/(P['steady_year']-P['fade_start'])))
 margins[1]-=.045*fade; margins[2]-=.03*fade
 margins=[v+sc.get('long_margin_shift',0)*fade for v in margins]
 gross=sum(r*m for r,m in zip(rev,margins))
 expenses=sum(rev)*q['expense']
 ebit=gross-expenses
 wc=sum(rev)*(q['wc_ratio']+sc.get('wc_add',0)+(sc.get('wc_add_first',0) if temporary else 0))
 growth=P['growth_capex'][y-1]*sc.get('growth_factor',1)*sc.get('capex_multiplier',1) if y<=len(P['growth_capex']) else 0
 ppe=prev['ppe']+growth
 if method=='capital_return':
  # Independent earning-capacity entrance: invested operating capital and return, no sales-margin earnings.
  old=prev['capital']
  g=P['aux_growth'][y-1] if y<=5 else .025*max(0,(20-y)/15)
  capital=old*(1+g)
  roic=P['aux_roic'][min(y,5)-1] if y<=5 else P['aux_roic'][-1]+(P['aux_steady_roic']-P['aux_roic'][-1])*min(1,(y-5)/15)
  nopat=old*roic
  ebit=nopat/(1-q['tax'])
  wc=capital*.53; ppe=capital*.47-.7
  growth=ppe-prev['ppe']
  rev=[capital/.60*.43,capital/.60*.45,capital/.60*.12]
  expenses=sum(rev)*q['expense'];gross=ebit+expenses
 sub_share=P['sub_profit_share'][min(y,len(P['sub_profit_share']))-1]
 return {'year':y,'revenues':rev,'gross_profit':gross,'operating_cost':expenses,'ebit':ebit,'wc':wc,'ppe':ppe,'growth_capex':growth,
         'capital':wc+ppe+.7,'sub_profit_share':sub_share,'method':method}

def step(s,op,q,sc):
 s=copy.deepcopy(s);before=copy.deepcopy(s);y=op['year'];own=q['sub_ownership']
 grant_expense=q['grant_expense'][y-1] if y<=len(q['grant_expense']) else 0
 treasury_cost_transferred=0
 if y==q['grant_year']:
  s['shares']+=s['treasury_remaining'];s['treasury_remaining']=0
  treasury_cost_transferred=s['treasury_cost'];s['treasury_cost']=0;s['capital_premium_p']-=treasury_cost_transferred
 s['other_equity_p']+=grant_expense;s['capital_premium_p']+=grant_expense
 # Previously declared dividends settle, no second investment income.
 receipt=s['div_rec']; nci_old=s['div_pay']-receipt
 s['cash_s']-=s['div_pay'];s['cash_p']+=receipt;s['div_rec']=s['div_pay']=0
 # Fixed known equity commitment; no recurring capital return.
 contribution=q['contribution'][y-1] if y<=len(q['contribution']) else 0
 s['cash_p']-=contribution;s['investment']+=contribution;s['cash_s']+=contribution;s['capital_s']+=contribution
 # External uncalled investment: capitalized, maintained as non-operating asset, no double earnings.
 commitment=q['external_commitment'][y-1] if y<=len(q['external_commitment']) else 0
 s['cash_p']-=commitment;s['other_p']+=commitment
 dep_p=before['ppe_p']*q['depr_rate'];dep_s=before['ppe_s']*q['depr_rate']
 # Additional factory capital mainly belongs to subsidiaries; working capital mainly parent contracts.
 target_ppe_s=q['ppe_s']+.55*(op['ppe']-q['ppe_p']-q['ppe_s'])
 target_ppe_p=op['ppe']-target_ppe_s
 target_wc_s=op['wc']*.17;target_wc_p=op['wc']-target_wc_s
 capex_p=target_ppe_p-before['ppe_p']+dep_p;capex_s=target_ppe_s-before['ppe_s']+dep_s
 # No unexplained disposal: reduced target capital recovered via ordinary net renewal/disinvestment budget, separately shown.
 interest_loan=before['loan']*q['loan_rate'];ip=before['debt_p']*q['debt_rate'];isub=before['debt_s']*q['debt_rate']
 yieldp=before['cash_p']*q['cash_rate'];yields=before['cash_s']*q['cash_rate']
 pre_s=op['ebit']*op['sub_profit_share']-isub-interest_loan+yields
 pre_p=op['ebit']*(1-op['sub_profit_share'])-ip+interest_loan+yieldp
 tax_s=max(0,pre_s)*q['tax'];tax_p=max(0,pre_p)*q['tax']
 profit_s=pre_s-tax_s;own_profit_p=pre_p-tax_p-grant_expense
 cfp=own_profit_p+grant_expense+dep_p-capex_p-(target_wc_p-before['wc_p'])
 cfs=profit_s+dep_s-capex_s-(target_wc_s-before['wc_s'])
 s['cash_p']+=cfp;s['cash_s']+=cfs
 s.update(ppe_p=target_ppe_p,ppe_s=target_ppe_s,wc_p=target_wc_p,wc_s=target_wc_s)
 buffer_p=.085*sum(op['revenues']);buffer_s=.012*sum(op['revenues'])
 # Subsidiary funding is a loan; no fictitious consolidated external receipt.
 advance=max(0,buffer_s-s['cash_s']);s['cash_s']+=advance;s['cash_p']-=advance;s['loan']+=advance
 repay_loan=min(s['loan'],max(0,s['cash_s']-buffer_s));s['cash_s']-=repay_loan;s['cash_p']+=repay_loan;s['loan']-=repay_loan
 ds=min(s['debt_s'],max(0,s['cash_s']-buffer_s));s['cash_s']-=ds;s['debt_s']-=ds
 s['re_s'],s['reserve_s'],reserve_s=legal(s['re_s'],s['reserve_s'],q['s_registered_capital'],profit_s,q['sub_reserve_rate'],q['sub_reserve_cap'])
 decl=0 if y<=sc.get('no_upstream',0) else min(max(0,s['re_s']),max(0,s['cash_s']-buffer_s))
 s['re_s']-=decl;s['div_pay']=.5*decl;s['div_rec']=.5*decl*own
 s['cash_s']-=.5*decl;s['cash_p']+=.5*decl*own
 invest_income=decl*own
 profit_p=own_profit_p+invest_income
 s['re_p'],s['reserve_p'],reserve_p=legal(s['re_p'],s['reserve_p'],s['capital_p'],profit_p)
 # Funding first, equity only for uncovered operating requirement. Explicit issue budget not security price.
 need=max(0,buffer_p-s['cash_p']);new_debt=min(need,max(0,q['max_debt']-s['debt_p']))
 s['cash_p']+=new_debt;s['debt_p']+=new_debt
 issue=max(0,buffer_p-s['cash_p']);newshares=issue/q['issue_price'];s['cash_p']+=issue;s['shares']+=newshares
 s['capital_p']+=newshares;s['other_equity_p']+=issue-newshares;s['capital_premium_p']+=issue-newshares
 dp=min(s['debt_p'],max(0,s['cash_p']-buffer_p));s['cash_p']-=dp;s['debt_p']-=dp
 payout=q['payout'][min(y,len(q['payout']))-1]
 release=max(0,s['cash_p']-buffer_p)*min(1,max(0,(y-5)/8))
 desired=max(max(0,profit_p)*payout,release)
 dividend=min(desired,max(0,s['re_p']),max(0,s['cash_p']-buffer_p))
 s['cash_p']-=dividend;s['re_p']-=dividend
 check(s)
 nci=nci_old+.5*decl*(1-own)
 group_profit=own_profit_p+profit_s
 near(s['cash_p']+s['cash_s'],before['cash_p']+before['cash_s']+cfp+cfs-commitment-ds-dp+new_debt+issue-dividend-nci)
 # Consolidated earnings exclude investment income; minority interests change with subsidiary equity.
 old_group=equity(before)+own*equity(before,True)-before['investment']
 new_group=equity(s)+own*equity(s,True)-s['investment']
 near(new_group,old_group+own_profit_p+own*profit_s+grant_expense-dividend+issue-contribution*(1-own))
 return s,dict(op,opening=before,closing=copy.deepcopy(s),parent_own_profit=own_profit_p,sub_profit=profit_s,group_profit=group_profit,
  grant_expense=grant_expense,treasury_credit=treasury_cost_transferred,capital_premium_transfer_debit=treasury_cost_transferred,parent_total_profit=profit_p,parent_investment_income=invest_income,dividend_receipt_prior=receipt,sub_declared=decl,sub_paid_current=.5*decl,
  parent_dividend=dividend,holder_dps=dividend/s['shares'],nci_cash=nci,capex_p=capex_p,capex_s=capex_s,depreciation=dep_p+dep_s,
  parent_tax=tax_p,sub_tax=tax_s,parent_interest=ip,sub_interest=isub,intercompany_interest=interest_loan,
  parent_operating_cash=own_profit_p+grant_expense+dep_p-(target_wc_p-before['wc_p']),sub_operating_cash=profit_s+dep_s-(target_wc_s-before['wc_s']),
  parent_reserve_transfer=reserve_p,sub_reserve_transfer=reserve_s,loan_advance=advance,loan_repaid=repay_loan,sub_debt_repaid=ds,parent_debt_repaid=dp,
  equity_contribution=contribution,external_commitment=commitment,new_debt=new_debt,equity_issue_cash=issue,new_shares=newshares,buffer_p=buffer_p,buffer_s=buffer_s)

def liquidate(s,q):
 # Solvent residual only; unpaid priority costs and creditors remain liabilities, not fictitious dissolution.
 x=q['exit'];b=copy.deepcopy(s)
 gross_s=s['cash_s']+s['wc_s']*x['wc_recovery']+s['ppe_s']*x['ppe_recovery']+s['other_s']*x['other_recovery']
 gross_p=s['cash_p']+s['wc_p']*x['wc_recovery']+s['ppe_p']*x['ppe_recovery']+s['other_p']*x['other_recovery']
 cost_s=x['employee']*.3+x['lease']*.3+x['cleanup']*.5
 parent_cost=x['employee']*.7+x['lease']*.7+x['cleanup']*.5+x['parent_extra_admin']
 support=min(x.get('parent_support_budget',0),max(0,gross_p-parent_cost-s['debt_p']),max(0,cost_s+s['debt_s']-gross_s))
 sub_cost_paid=min(gross_s+support,cost_s);sub_cost_unpaid=cost_s-sub_cost_paid
 bank_paid_s=min(max(0,gross_s+support-sub_cost_paid),s['debt_s'])
 declared_paid_s=min(max(0,gross_s+support-sub_cost_paid-bank_paid_s),s['div_pay'])
 available_s=max(0,gross_s+support-sub_cost_paid-bank_paid_s-declared_paid_s)
 loan_paid=min(s['loan'],available_s);available_s-=loan_paid
 sub_owner=available_s*q['sub_ownership'];nci=available_s*(1-q['sub_ownership'])
 parent_assets=gross_p-support+loan_paid+sub_owner+declared_paid_s*q['sub_ownership']
 parent_cost_paid=min(parent_assets,parent_cost);parent_cost_unpaid=parent_cost-parent_cost_paid
 parent_tax=max(0,sub_owner-s['investment'])*x['tax_rate']
 parent_tax_paid=min(max(0,parent_assets-parent_cost_paid),parent_tax)
 parent_bank_paid=min(max(0,parent_assets-parent_cost_paid-parent_tax_paid),s['debt_p'])
 common=max(0,parent_assets-parent_cost_paid-parent_tax_paid-parent_bank_paid)
 sub_income=gross_s+support-(s['cash_s']+s['wc_s']+s['ppe_s']+s['other_s'])-cost_s
 sub_creditor_unpaid=s['debt_s']-bank_paid_s+s['div_pay']-declared_paid_s+s['loan']-loan_paid
 near(equity(s,True)+sub_income+sub_creditor_unpaid+sub_cost_unpaid-available_s,0)
 parent_income=parent_assets-(s['cash_p']+s['wc_p']+s['ppe_p']+s['other_p']+s['loan']+s['investment']+s['div_rec'])-parent_cost-parent_tax
 parent_creditor_unpaid=s['debt_p']-parent_bank_paid
 near(equity(s)+parent_income+parent_creditor_unpaid+parent_cost_unpaid+parent_tax-parent_tax_paid-common,0)
 near(gross_s+support,sub_cost_paid+bank_paid_s+declared_paid_s+loan_paid+available_s)
 near(parent_assets,parent_cost_paid+parent_tax_paid+parent_bank_paid+common)
 outstanding={'sub_priority_cost':sub_cost_unpaid,'sub_external_debt':s['debt_s']-bank_paid_s,'sub_declared_dividend':s['div_pay']-declared_paid_s,'sub_intercompany_loan':s['loan']-loan_paid,'parent_priority_cost':parent_cost_unpaid,'parent_tax':parent_tax-parent_tax_paid,'parent_external_debt':parent_creditor_unpaid}
 solvent=sum(outstanding.values())<1e-9
 return {'opening':b,'sub_gross_assets':gross_s,'sub_employee_lease_cleanup':cost_s,'sub_external_and_declared_paid':bank_paid_s+declared_paid_s,
         'sub_priority_cost_paid':sub_cost_paid,'parent_priority_cost_paid':parent_cost_paid,'parent_support_cash':support,'unpaid_claims':outstanding,'solvent_dissolution':solvent,
         'intercompany_loan_recovery':loan_paid,'intercompany_loan_loss':s['loan']-loan_paid,'sub_equity_proceeds':available_s,'sub_parent_proceeds':sub_owner,'nci_proceeds':nci,
         'parent_assets_with_recoveries':parent_assets,'parent_employee_lease_cleanup_admin':parent_cost,'parent_debt_paid':parent_bank_paid,
         'parent_tax':parent_tax,'parent_tax_paid':parent_tax_paid,'common_cash':common,'holder_dps':common/s['shares'],'sub_liquidation_profit':sub_income,'sub_creditor_unpaid':sub_creditor_unpaid,'parent_liquidation_profit':parent_income,'parent_creditor_unpaid':parent_creditor_unpaid,
         'final_dissolved_balance':{k:0.0 for k in s} if solvent else None,
         'insolvent_estate_balance':None if solvent else {'remaining_assets':0,'unpaid_liabilities':sum(outstanding.values()),'negative_equity':-sum(outstanding.values()),'legal_release_assumed':False},'terminal':0.0}

def run(name='base',method='sales_margin',horizon=60,extra=None):
 sc=copy.deepcopy(SCENARIOS[name]);sc.update(extra or {});q=copy.deepcopy(P)
 for k,v in sc.items():
  if k in q:q[k]=v
 s=initial(q);check(s);initial_state=copy.deepcopy(s)
 prev={'ppe':s['ppe_p']+s['ppe_s'],'capital':s['wc_p']+s['wc_s']+s['ppe_p']+s['ppe_s']+.7}
 rows=[];exit_detail=None
 for y in range(1,horizon+1):
  effective_sc={} if sc.get('terminal_change_only') and y<=5 else sc
  op=operations(y,prev,q,effective_sc,method);s,row=step(s,op,q,effective_sc)
  if y==sc.get('exit_year'):
   exit_detail=liquidate(s,q);row['holder_dps']+=exit_detail['holder_dps'];row['liquidation']=exit_detail;rows.append(row);break
  rows.append(row);prev=op
 r=q['discount'];tail=0
 if exit_detail is None:
  # Constant zero-growth state, not arbitrary end-year asset sale.
  for k in s:
   near(rows[-1]['closing'][k],rows[-2]['closing'][k])
  near(rows[-1]['holder_dps'],rows[-2]['holder_dps'])
  tail=rows[-1]['holder_dps']/r
 pv=sum(z['holder_dps']/(1+r)**z['year'] for z in rows)+tail/(1+r)**len(rows)
 tv5=sum(z['holder_dps']/(1+r)**(z['year']-5) for z in rows if z['year']>5)+tail/(1+r)**(len(rows)-5) if len(rows)>=5 else 0
 return {'name':name,'method':method,'information_cutoff':ASOF,'parameters':q,'scenario_changes':sc,'initial_state':initial_state,'annual':rows,'value_per_share':pv,
         'year5_terminal':tv5,'first5_distributions':[z['holder_dps'] for z in rows[:5]],'perpetuity_at_horizon':tail,
         'terminal_pv_share':tail/(1+r)**len(rows)/pv if pv else 0,'post_year5_pv_share':tv5/(1+r)**5/pv if pv else 0,'liquidation':exit_detail}

def tests():
 out={}
 a=legal(-10,0,100,6);assert a==(-4,0,0);out['loss_carryforward']=a
 a=legal(-4,0,100,10);near(a[0],5.4);near(a[1],.6);out['loss_then_reserve']=a
 a=legal(0,49,100,20);assert a==(19,50,1);out['reserve_cap']=a
 q=copy.deepcopy(P);q.update(cash_p=1,cash_s=.1,p_re=0,s_re=0,p_reserve=.5,s_reserve=.5,p_capital=1,s_capital=1,loan=0,investment=1,
   debt_p=0,debt_s=0,cash_rate=0,tax=0,loan_rate=0,contribution=[],external_commitment=[],payout=[1],max_debt=0,grant_expense=[],grant_year=999,s_registered_capital=1)
 s=initial(q)
 op={'year':1,'revenues':[1,0,0],'ebit':1,'wc':s['wc_p']+s['wc_s'],'ppe':s['ppe_p']+s['ppe_s'],'sub_profit_share':0}
 # target sub split changes assets but group cash/profit remain one unit; legal distribution cannot exceed parent profit.
 z,row=step(s,op,q,{})
 near(row['group_profit'],1);assert row['parent_dividend']<=1+1e-8;out['production_one_unit_profit']=row
 # Same formal step with deficit, no debt capacity: positive equity funding and explicit dilution.
 op['ebit']=-10
 z,row=step(s,op,q,{})
 assert row['equity_issue_cash']>0 and z['shares']>s['shares'] and row['parent_dividend']==0
 out['production_funding_and_dilution']=row
 # Integrated legal counterexamples pass through the same operating/funding/distribution step.
 qloss=copy.deepcopy(q);qloss['p_re']=-.2;op['ebit']=.1;op['sub_profit_share']=0
 z,row=step(initial(qloss),op,qloss,{})
 near(z['re_p'],-.1);assert row['parent_reserve_transfer']==0 and row['parent_dividend']==0
 out['production_loss_repair']=row
 qcap=copy.deepcopy(q);qcap['p_re']=0;qcap['p_reserve']=.49;op['ebit']=.2
 z,row=step(initial(qcap),op,qcap,{})
 near(row['parent_reserve_transfer'],.01);near(z['reserve_p'],.5)
 out['production_reserve_cap']=row
 # NCI budget, dividends never treated as common holder cash.
 q['sub_ownership']=.6;op['ebit']=2;op['sub_profit_share']=.8
 s=initial(q);z,row=step(s,op,q,{})
 assert row['nci_cash']>0;near(row['parent_investment_income'],row['sub_declared']*.6);out['production_nci']=row
 out['production_exit']=liquidate(z,q)
 qhigh=copy.deepcopy(P);qhigh['exit'].update(employee=100,lease=40,cleanup=30,parent_support_budget=1)
 out['production_insolvent_exit']=liquidate(initial(qhigh),qhigh)
 bad=out['production_insolvent_exit'];assert bad['common_cash']==0 and bad['unpaid_claims']['sub_priority_cost']>0 and bad['final_dissolved_balance'] is None
 qsupport=copy.deepcopy(q);qsupport['exit'].update(employee=2,lease=.3,cleanup=.5,parent_support_budget=.5)
 qsupport.update(cash_s=.01,wc_s=.01,ppe_s=.01,other_s=.01,debt_s=.2,loan=.1)
 out['production_exit_parent_support']=liquidate(initial(qsupport),qsupport)
 assert out['production_exit_parent_support']['parent_support_cash']>0
 assert out['production_exit']['nci_proceeds']>=0
 return out

def main():
 results={n:run(n) for n in SCENARIOS}
 results['auxiliary']=run(method='capital_return')
 for name in ['holder_low','holder_high']:
  for b,h in zip(results['base']['annual'][:5],results[name]['annual'][:5]):
   assert b==h
 convergence={str(n):run(horizon=n) for n in [40,80,120]}
 for v in convergence.values():near(v['value_per_share'],results['base']['value_per_share'])
 path_convergence={}
 for name,result in results.items():
  longer=run(name if name!='auxiliary' else 'base',method='capital_return' if name=='auxiliary' else 'sales_margin',horizon=120)
  near(longer['value_per_share'],result['value_per_share'])
  if result['liquidation'] is None:
   for k in result['annual'][-1]['closing']:near(result['annual'][-1]['closing'][k],longer['annual'][-1]['closing'][k])
  path_convergence[name]=longer
 sensitivities={}
 for k,vals in [('discount',[.085,.105]),('wc_ratio',[.25,.33]),('cash_rate',[0,.02]),('expense',[.071,.085])]:
  for v in vals:
   label=k+'_'+str(v);sensitivities[label]=run(extra={k:v});longer=run(horizon=120,extra={k:v})
   near(longer['value_per_share'],sensitivities[label]['value_per_share'])
   for state in longer['annual'][-1]['closing']:near(longer['annual'][-1]['closing'][state],sensitivities[label]['annual'][-1]['closing'][state])
   path_convergence[label]=longer
 obj={'information_cutoff':ASOF,'unit':'CNY billion; share count billion; per share CNY','all_parameters_literal':P,'scenarios':results,
      'convergence_full_runs':convergence,'all_paths_long_horizon_runs':path_convergence,'diagnostic_sensitivities_full_runs':sensitivities,'production_counterexamples':tests()}
 print(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()
