"""CN300979 2026Q3. stdlib only. All amounts CNY billion except per-share.
Economic capacity budgets are NOT subsidiary statutory accounts. stdout is complete deterministic output.
"""
import json, math, copy
ASOF='2026-10-29T00:00:00+00:00'
S=1.167
OPEN={
 'cash_parent':.310, 'cash_operating':1.71032287886+.29172000669-.310,
 'deposit_parent':.739,'deposit_operating':5.54716376548-1.71032287886-.739,
 'investment':.44939719320,'debt':1.91794094165+.03073976799+.12165293961,
 'old_dividend_payable':2.070400500,'parent_receivable':3.75581419919,
 'parent_retained':1.18338795284-1.167,'parent_reserve':.5835,
 'registered_capital':1.167,'upstream_capacity_budget':4.,
 'loss_li_zhi':.30,'loss_prime':.20,'loss_xinyao':.20,
 'operating_capital':14.84503369017-5.54716376548-.29172000669-.44939719320+1.91794094165+.03073976799+.12165293961+2.070400500,
 'parent_intercompany_payable_budget':.84910342435,
 'parent_intercompany_receivable_budget':.37313154112,
 'parent_capital_support':0., 'earmarked_fund_budget':.799, 'earmarked_cash':.06, 'shares':S}
# The internal balances are paid/reinvested within the group, not deducted twice from group value.
def plan(kind='base', method='operations', horizon=160):
 rows=[];rev=21.924;capital=OPEN['operating_capital'];eps=2.95
 for y in range(1,horizon+1):
  if method=='operations':
   first=[22.5,23.6,24.8,26.0,27.2]
   if y<=5:rev=first[y-1]
   elif y<=10:rev*=1.03
   elif y<=20:rev*=1.03*(1-(y-10)/10)+1*(y-10)/10
   margin=([.14,.145,.15,.15,.15][y-1] if y<=5 else .15 if y<=10 else .15-(min(y,20)-10)*.003)
   if kind=='cyclical':
    if y<=3:rev*= [.88,.94,.98][y-1];margin-= [.025,.015,.005][y-1]
   elif kind=='structural':
    if y==1:rev=20.0
    elif y<=5:rev=20.0*(1.01**(y-1))
    margin=min(margin,.105)
   elif kind=='upside':margin+=.015;rev*=1.02 if y<=5 else 1.
   elif kind=='growth_without_value': margin-=.015;rev*=1.04 if y<=5 else 1.
   target=max(capital,rev*(.68 if kind=='growth_without_value' else .56))
   dk=max(target-capital,([1.1,.9,.7,.5,.5][y-1] if y<=5 else 0.))
   ebit=rev*margin
   local_net=ebit*.80*.996
  else:
   # Independent economic entry: cycle-normalised local after-tax operating earnings;
   # reinvestment priced at a separate 15% incremental return, not sales capital intensity.
   growth=.03 if y<=10 else max(0.,.03*(20-y)/10)
   old=eps;eps*=1+growth
   local_net=eps
   dk=(eps-old)/.15
   rev=local_net/.12  # solely for operational cash budget, not profit generation
   ebit=local_net/.80
  newloss=([.30,.20,.10][y-1] if y<=3 else 0.)
  if kind=='cyclical' and y<=3:newloss*=1.5
  if kind=='structural' and y<=5:newloss=.35 if y<=2 else .10
  newprof=0. if y<=3 else min(.25,.08*(y-3))
  # newprof is included in local_net, not incremental earnings.
  special=.265 if y==1 else .200 if y==2 else 0.
  project_profit=0 if y<=2 else .375*.08
  da=capital*.08
  capital+=dk+special
  rows.append(dict(year=y,revenue=rev,ebit_before_new_losses=ebit,local_aftertax_before_new_losses=local_net,new_losses=newloss,new_profit_included=newprof,project_profit=project_profit,capital_add=dk+special,maintenance_capex=da,depreciation=da,total_capex=da+dk+special,operating_capital=capital))
 return rows

def simulate(schedule, discount=.10, remit_cap=1., deposit_delay=0, credit_limit=2.5, declaration_factor=1., hedge_lock=0., eligible_project_delay=0, initial=None):
 st=copy.deepcopy(OPEN if initial is None else initial);init=copy.deepcopy(st)
 history=[];totalpv=0.;feasible=True
 for p in schedule:
  y=p['year'];before=copy.deepcopy(st)
  # Deposits >3 months are liquidity timing, not permanent impairment.
  depfrac=(.60 if y==1+deposit_delay else 1. if y==2+deposit_delay else 0.)
  dep_p=st['deposit_parent']*depfrac;dep_o=st['deposit_operating']*depfrac
  st['deposit_parent']-=dep_p;st['deposit_operating']-=dep_o
  st['cash_parent']+=dep_p;st['cash_operating']+=dep_o
  # Identified IPO proceeds first fund eligible project capex, never ordinary dividends.
  # Opening dedicated funds earn 2% net yield budget grossed up at disclosed parent 25% tax.
  # Parent-owned profit stays dedicated until qualifying capex actually absorbs it.
  restricted_yield_gross=(.02/.75)*before['earmarked_fund_budget']
  restricted_yield_tax=.25*restricted_yield_gross
  restricted_yield_net=restricted_yield_gross-restricted_yield_tax
  st['cash_parent']+=restricted_yield_net
  st['earmarked_fund_budget']+=restricted_yield_net
  st['earmarked_cash']+=dep_p+restricted_yield_net
  earmarked_transfer=min(st['earmarked_fund_budget'],st['earmarked_cash'],p['capital_add'],max(0,st['cash_parent']-.05)) if y>eligible_project_delay else 0.
  st['cash_parent']-=earmarked_transfer;st['cash_operating']+=earmarked_transfer
  st['earmarked_fund_budget']-=earmarked_transfer;st['earmarked_cash']-=earmarked_transfer;st['parent_capital_support']+=earmarked_transfer
  # Financial investments recovered over ten years, with 20% valuation loss, not a year-5 plug.
  sold=min(st['investment'],init['investment']/10)
  exit_cash=sold*.8;exit_loss=sold*.2;st['investment']-=sold
  st['cash_operating']+=exit_cash
  cash_interest=.02*(before['cash_parent']+before['cash_operating']+before['deposit_parent']+before['deposit_operating'])
  interest=.04*before['debt']
  mature_net=p['local_aftertax_before_new_losses']-p['new_profit_included']
  eligible_new=0.;loss_recovery={}
  for key,weight in [('loss_li_zhi',3/7),('loss_prime',2/7),('loss_xinyao',2/7)]:
   loss_add=p['new_losses']*weight;profit=p['new_profit_included']*weight
   st[key]+=loss_add
   recover=min(st[key],profit);st[key]-=recover
   eligible_new+=profit-recover;loss_recovery[key]=recover
  group_op_net=p['local_aftertax_before_new_losses']-p['new_losses']+p['project_profit']
  st['cash_operating']+=group_op_net+cash_interest-restricted_yield_net-interest-p['capital_add']
  st['operating_capital']=p['operating_capital']
  # Do not pool legal loss balances: only profits after each pocket's loss recovery enter capacity.
  eligible=mature_net+eligible_new+p['project_profit']+cash_interest-restricted_yield_net-interest-exit_loss
  st['upstream_capacity_budget']+=eligible
  floor_o=p['revenue']*.05+(hedge_lock if y<=3 else 0.);floor_p=.05+st['earmarked_cash']
  # Finite internal receivable/payable settlement: no consolidated economic cash creation.
  inter_rec=min(st['parent_intercompany_receivable_budget'],init['parent_intercompany_receivable_budget']/5,max(0,st['cash_operating']-floor_o))
  st['cash_operating']-=inter_rec;st['cash_parent']+=inter_rec;st['parent_intercompany_receivable_budget']-=inter_rec
  inter_pay=min(st['parent_intercompany_payable_budget'],init['parent_intercompany_payable_budget']/5,max(0,st['cash_parent']-floor_p))
  st['cash_parent']-=inter_pay;st['cash_operating']+=inter_pay;st['parent_intercompany_payable_budget']-=inter_pay
  # Settle already recognised receivables first; current declaration has one full-year cash lag.
  upstream_cash=min(before['parent_receivable'],max(0,st['cash_operating']-floor_o),remit_cap*(3.2 if y<=2 else max(2.5,p['revenue']*.20)))
  st['cash_operating']-=upstream_cash;st['cash_parent']+=upstream_cash;st['parent_receivable']-=upstream_cash
  # budget combines current profitable operations and bounded historical capacity.
  release_extra=max(0,st['cash_operating']-floor_o-st['parent_receivable'])
  declare=min(max(0,st['upstream_capacity_budget']),max(0,eligible)+release_extra,(max(2.7,p['revenue']*.12)*declaration_factor if y<=5 else p['revenue']*.20))
  st['upstream_capacity_budget']-=declare;st['parent_receivable']+=declare
  parent_tax=.07*declare
  parent_cost=.03
  parent_profit=declare-parent_tax-parent_cost+restricted_yield_net
  st['parent_retained']+=parent_profit
  # Losses have first claim; only post-loss positive incremental profit is reserved.
  reserve_add=min(max(0,.5*st['registered_capital']-st['parent_reserve']),.1*min(max(0,parent_profit),max(0,st['parent_retained'])))
  st['parent_retained']-=reserve_add;st['parent_reserve']+=reserve_add
  st['cash_parent']-=parent_tax+parent_cost
  oldpaid=min(st['old_dividend_payable'],max(0,st['cash_parent']-floor_p))
  st['old_dividend_payable']-=oldpaid;st['cash_parent']-=oldpaid
  # No borrowing for distributions. Revolver only supports compulsory cash needs, finite capacity.
  need=max(0,floor_o-st['cash_operating'])+max(0,floor_p-st['cash_parent'])
  draw=min(need,max(0,credit_limit-st['debt']))
  st['debt']+=draw
  draw_p=min(draw,max(0,floor_p-st['cash_parent']));st['cash_parent']+=draw_p;st['cash_operating']+=draw-draw_p
  if need-draw>1e-8:
   # Fail closed before any shareholder cash or valuation can be manufactured.
   return dict(feasible=False,discount=discount,value_per_share=None,year5_value_per_share=None,first5=None,year5_state=None,horizon=len(history),history=history,failure=dict(year=y,unfunded_need=need-draw,reason='finite_credit_exhausted',pre_failure_state=before,provisional_unsettled_state=copy.deepcopy(st)))
  # Repay scheduled stock only from excess liquidity after obligations; no infinite refinancing.
  repayment_target=min(st['debt'],init['debt']/3)
  support=min(max(0,st['cash_parent']-floor_p),max(0,repayment_target-max(0,st['cash_operating']-floor_o)))
  st['cash_parent']-=support;st['cash_operating']+=support;st['parent_capital_support']+=support
  repay=min(st['debt'],init['debt']/3,max(0,st['cash_operating']-floor_o))
  st['cash_operating']-=repay;st['debt']-=repay
  desired=(.65*max(0,group_op_net-parent_tax-parent_cost) if y<=5 else max(0,st['cash_parent']-floor_p))
  dividend=min(desired,max(0,st['parent_retained']),max(0,st['cash_parent']-floor_p)) if st['old_dividend_payable']<1e-8 else 0.
  st['parent_retained']-=dividend;st['cash_parent']-=dividend
  # Consolidated cash conservation, including old owners (not new holder distributions).
  flow=group_op_net+cash_interest-interest-p['capital_add']+exit_cash-parent_tax-parent_cost-oldpaid+draw-repay-dividend
  cash_before=sum(before[k] for k in ['cash_parent','cash_operating','deposit_parent','deposit_operating'])
  cash_after=sum(st[k] for k in ['cash_parent','cash_operating','deposit_parent','deposit_operating'])
  assert abs(cash_after-cash_before-flow)<1e-8
  assert abs(st['parent_receivable']-before['parent_receivable']-declare+upstream_cash)<1e-8
  assert abs(st['parent_retained']-before['parent_retained']-parent_profit+reserve_add+dividend)<1e-8
  assert abs(st['earmarked_fund_budget']-before['earmarked_fund_budget']-restricted_yield_net+earmarked_transfer)<1e-8
  assert abs(st['earmarked_cash']-before['earmarked_cash']-dep_p-restricted_yield_net+earmarked_transfer)<1e-8
  assert abs(st['earmarked_fund_budget']-st['earmarked_cash']-st['deposit_parent'])<1e-8
  netincome=group_op_net+cash_interest-interest-parent_tax-parent_cost-exit_loss
  equity=lambda a:a['operating_capital']+a['investment']+sum(a[k] for k in ['cash_parent','cash_operating','deposit_parent','deposit_operating'])-a['debt']-a['old_dividend_payable']
  assert abs(equity(st)-equity(before)-netincome+dividend)<1e-8
  totalpv+=dividend/(1+discount)**y
  history.append(dict(**p,netincome=netincome,eligible_upstream=eligible,upstream_declaration=declare,upstream_cash=upstream_cash,parent_profit=parent_profit,parent_tax=parent_tax,reserve_add=reserve_add,old_dividend_paid=oldpaid,cash_interest=cash_interest,free_cash_interest=cash_interest-restricted_yield_net,restricted_yield_gross=restricted_yield_gross,restricted_yield_tax=restricted_yield_tax,restricted_yield_net=restricted_yield_net,debt_interest=interest,deposit_release_parent=dep_p,deposit_release_operating=dep_o,investment_exit_cash=exit_cash,investment_exit_loss=exit_loss,internal_receipt=inter_rec,internal_payment=inter_pay,parent_capital_support=support,earmarked_project_transfer=earmarked_transfer,borrowed=draw,repaid=repay,dividend=dividend,dividend_per_share=dividend/st['shares'],loss_recovery=loss_recovery,state=copy.deepcopy(st)))
 n=len(history)
 # A perpetuity is permitted only after ALL financial/legal-budget stocks and operating fields converge.
 if n>=5:
  last,prev=history[-1],history[-2]
  deltas={k:abs(v-prev['state'][k]) for k,v in last['state'].items()}
  flow_deltas={k:abs(last[k]-prev[k]) for k in ['revenue','netincome','dividend','upstream_declaration','upstream_cash','operating_capital','maintenance_capex','total_capex']}
  stable=max(list(deltas.values())+list(flow_deltas.values()))<1e-8
 else:stable=False;deltas={};flow_deltas={}
 if feasible and not stable:raise AssertionError(('nonconverged',deltas,flow_deltas))
 tail=history[-1]['dividend']/discount if stable else 0.
 totalpv+=tail/(1+discount)**n
 terminal5=(sum(r['dividend']/(1+discount)**(r['year']-5) for r in history[5:])+tail/(1+discount)**(n-5))/st['shares']
 value=totalpv/st['shares']
 return dict(feasible=feasible,discount=discount,value_per_share=value,year5_value_per_share=terminal5,first5=[r['dividend_per_share'] for r in history[:5]],year5_state=history[4]['state'],horizon=n,convergence=dict(stable=stable,all_stock_deltas=deltas,flow_deltas=flow_deltas),post_year5_pv_fraction=terminal5/(1+discount)**5/value if value else None,history=history)

def checks():
 # Same production function: a mature 1bn net profit with no capital need, no taxes in parent? Parent tax is 7%, costs .03.
 # For exact steady case, operation local net1, cash floor1+0.05 => interest.021, declaration1.021, parent NI .91953.
 z={k:0. for k in OPEN};z.update(cash_parent=.05,cash_operating=1.,parent_receivable=1.021,parent_retained=5.,upstream_capacity_budget=5.,shares=1.,operating_capital=10.)
 q=[dict(year=i,revenue=20.,ebit_before_new_losses=1.25,local_aftertax_before_new_losses=1.,new_losses=0.,new_profit_included=0.,project_profit=0.,capital_add=0.,maintenance_capex=.8,depreciation=.8,total_capex=.8,operating_capital=10.) for i in range(1,161)]
 # y1-5 desired65% creates temporary parent cash, interest; validate by independent one-period literal hand arithmetic.
 r=simulate(q,initial=z)
 first=r['history'][0]
 expected=.65*(1.-.07*1.021-.03)
 assert abs(first['dividend']-expected)<1e-12
 assert abs(first['state']['parent_receivable']-1.021)<1e-12
 # Negative retained earnings: profit fills loss first; no dividend or reserve before loss cured.
 neg=copy.deepcopy(z);neg['parent_retained']=-10.;neg['registered_capital']=1.;neg['parent_reserve']=0.
 rn=simulate(q,initial=neg)
 assert rn['history'][0]['dividend']==0 and rn['history'][0]['reserve_add']==0
 # Old receivable does not appear a second time in parent profit.
 a=first;assert abs(a['parent_profit']-(a['upstream_declaration']*.93-.03))<1e-12
 # Refused financing cannot become infinite free funding.
 bad=copy.deepcopy(z);bad['cash_operating']=0.;bad['cash_parent']=0.;bad['parent_receivable']=0.
 qb=copy.deepcopy(q);qb[0]['capital_add']=100.;qb[0]['operating_capital']=110.
 for row in qb[1:]:row['operating_capital']=110.
 rb=simulate(qb,credit_limit=0,initial=bad)
 assert not rb['feasible'] and rb['value_per_share'] is None and rb['first5'] is None and rb['failure']['unfunded_need']>0
 # Restricted principal AND reinvested yield remain dedicated in a real delayed-use path.
 locked=simulate(plan(),eligible_project_delay=3)
 for y,row in enumerate(locked['history'][:3],1):
  assert row['earmarked_project_transfer']==0
  assert abs(row['state']['earmarked_fund_budget']-.799*1.02**y)<1e-10
  assert abs(row['cash_interest']-row['free_cash_interest']-row['restricted_yield_net'])<1e-10
  assert row['state']['cash_parent']>=row['state']['earmarked_cash']+.05-1e-10
 assert locked['history'][4]['state']['earmarked_fund_budget']<1e-10
 return dict(restricted_yield_three_year_budget=.799*1.02**3,restricted_use_test_passed=True,steady_hand_first_dividend=expected,negative_retained_first_dividend=rn['history'][0]['dividend'],negative_retained_first_reserve=rn['history'][0]['reserve_add'],denied_credit_feasible=rb['feasible'],passed=True)

def main():
 results={}
 for kind in ['base','cyclical','structural','upside','growth_without_value']:
  results[kind]=simulate(plan(kind))
 for label,r in [('core_low',.105),('core_high',.095),('discount_up_100bp',.11)]:results[label]=simulate(plan(),discount=r)
 results['auxiliary']=simulate(plan(method='earnings'))
 results['remittance_70pct']=simulate(plan(),remit_cap=.7)
 zero_capacity=copy.deepcopy(OPEN);zero_capacity['upstream_capacity_budget']=0.
 results['zero_opening_upstream_capacity']=simulate(plan(),initial=zero_capacity)
 double_loss=copy.deepcopy(OPEN)
 for key in ['loss_li_zhi','loss_prime','loss_xinyao']:double_loss[key]*=2
 results['double_unverified_loss_budget']=simulate(plan(),initial=double_loss)
 results['refused_new_credit']=simulate(plan(),credit_limit=OPEN['debt'])
 results['hedge_margin_1_6bn_3y']=simulate(plan(),hedge_lock=1.6)
 results['declaration_70pct_5y']=simulate(plan(),declaration_factor=.7)
 results['eligible_project_delayed_3y']=simulate(plan(),eligible_project_delay=3)
 results['deposits_delayed_2y']=simulate(plan(),deposit_delay=2)
 # All formal paths receive a complete, actual 320-year re-run.
 configs={k:dict(kind=k) for k in ['base','cyclical','structural','upside','growth_without_value']}
 configs.update(core_low=dict(discount=.105),core_high=dict(discount=.095),discount_up_100bp=dict(discount=.11),auxiliary=dict(method='earnings'),remittance_70pct=dict(remit_cap=.7),zero_opening_upstream_capacity=dict(initial=zero_capacity),double_unverified_loss_budget=dict(initial=double_loss),refused_new_credit=dict(credit_limit=OPEN['debt']),hedge_margin_1_6bn_3y=dict(hedge_lock=1.6),declaration_70pct_5y=dict(declaration_factor=.7),deposits_delayed_2y=dict(deposit_delay=2),eligible_project_delayed_3y=dict(eligible_project_delay=3))
 longs={}
 for name,config in configs.items():
  c=config.copy();kind=c.pop('kind','base');method=c.pop('method','operations')
  long=simulate(plan(kind,method,320),**c);short=results[name]
  assert long['feasible'] and abs(long['value_per_share']-short['value_per_share'])<1e-9
  assert long['history'][:160]==short['history']
  for k in OPEN:assert abs(long['history'][-1]['state'][k]-short['history'][-1]['state'][k])<1e-8
  for k in short['convergence']['flow_deltas']:assert abs(long['history'][-1][k]-short['history'][-1][k])<1e-8
  longs[name]=long
 result=dict(information_cutoff=ASOF,units='CNY billion; shares billion; per-share CNY',opening=OPEN,checks=checks(),horizon_extension={'years':320,'all_paths_all_fields_match':True},paths=results,long_horizon_paths=longs)
 print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()
