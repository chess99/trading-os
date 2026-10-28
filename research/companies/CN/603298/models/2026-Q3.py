#!/usr/bin/env python3
"""Hangcha Q3 research snapshot. Standard library, CNY100m / shares100m.
Future financing and legal balances are conditional economic budgets, not facts.
"""
from pathlib import Path
from copy import deepcopy
import json
S=13.09812049
BASE=dict(revenue0=195.,growth=[.08,.08,.07,.06,.05,.05,.04,.04,.03,.03],margin=[.105,.107,.109,.110,.110,.109,.108,.107,.106,.105],normal_reinvestment_rate=.03,project_capital=16.527918,project_rd=2.3218,project_wc=5.700282,project_schedule=[.4,.4,.2,0,0,0,0,0,0,0],cash0=37.6382402887-12-2.5,debt0=6.7946400004+3.97+.0098051077+.3325067986-.04578954,common_book0=127.2457586051,assoc_book0=32.5847711792,assoc_profit1=4.2,assoc_growth=.03,assoc_incremental_return=.12,assoc_cash_div=[.2,.3,.5,.8,1.2],assoc_payout_later=.4,cash_yield=.01,debt_rate=.025,bond=22.59,bond_fee=.2,bond_year=1,bond_repay_year=6,convert_year=0,conversion_price=30.,dps=[.65,.70,.75,.80,.85],payout_later=.45,parent_cash_budget0=17.,parent_cash_floor=8.,parent_cash_share=.75,parent_self_nwc_rate=.012,parent_maintenance_rate=.012,parent_sub_distribution_ratio=.25,parent_extra_settlement=[0.]*10,initial_parent_legal_reserve=75.5688992677,parent_registered_capital0=S,parent_statutory_reserve0=6.549060245,parent_capital_premium0=17.6109299678,parent_assoc_share=263187909.88/263212746.76,parent_reserved_debt_interest=4.973078389*.025,project_profit_embedded=[0.,.2,1.,2.,2.7,3.,3.1,3.2,3.3,3.4],project_profit_actual=[0.,.2,1.,2.,2.7,3.,3.1,3.2,3.3,3.4],terminal_g=.025,terminal_roic=.105,discount=.10,cash_release_years=10,extra_nwc=[0.]*10,loss=[0.]*10,label='base')
def pv_payments(values,r):return sum(v/(1+r)**(i+1) for i,v in enumerate(values))
def release_value(principal,r,y,n):
 if principal<0:return principal
 return sum((principal/n+principal*(1-(i-1)/n)*y)/(1+r)**i for i in range(1,n+1))
def deferred_cohorts(first,g,r,lag=2):
 balance=earned_total=paid_total=pv=0.;trace=[]
 for year in range(1,11+lag):
  earned=first*(1+g)**(year-1) if year<=10 else 0.
  paid=first*(1+g)**(year-lag-1) if lag<year<=10+lag else 0.
  balance+=earned-paid;earned_total+=earned;paid_total+=paid;pv+=paid/(1+r)**year
  assert abs(balance-earned_total+paid_total)<1e-8
  trace.append(dict(year=year,earned=earned,paid=paid,cohort_cash=balance))
 tail=first*(1+g)**10/(r-g)/(1+r)**(10+lag);closed=first/(r-g)/(1+r)**lag
 assert abs(balance)<1e-8 and abs(pv+tail-closed)<1e-8
 return dict(value=closed,first_ten_cohorts=trace,later_cohorts_pv=tail,first_ten_earned=earned_total,first_ten_paid=paid_total)
def run(p):
 rev=p['revenue0'];cash=p['cash0'];debt=p['debt0'];shares=S;book=p['common_book0'];abook=p['assoc_book0'];afin=0.;acapital=abook;opcapital=book-abook-cash+debt
 parent=p['parent_cash_budget0'];legal=p['initial_parent_legal_reserve'];registered=p['parent_registered_capital0'];statutory=p['parent_statutory_reserve0'];premium=p['parent_capital_premium0'];earmarked=0.;rows=[];aprior=p['assoc_profit1']/(1+p['assoc_growth'])
 for i in range(10):
  y=i+1;rev*=1+p['growth'][i];w=p['project_schedule'][i];rd=p['project_rd']*w;pc=p['project_capital']*w;pw=p['project_wc']*w
  mature=rev*p['margin'][i]-p['project_profit_embedded'][i];base_profit=mature+p['project_profit_actual'][i];profit=base_profit-rd-p['loss'][i]
  normal=rev*p['normal_reinvestment_rate'];nw=p['extra_nwc'][i];fcf=profit-normal-pc-pw-nw
  apr=p['assoc_profit1']*(1+p['assoc_growth'])**i;areinvest=(apr-aprior)/p['assoc_incremental_return'];acapital+=areinvest;ayield=afin*p['cash_yield'];adiv=p['assoc_cash_div'][i] if i<5 else apr*p['assoc_payout_later'];afin_next=afin+apr+ayield-areinvest-adiv;abook_next=abook+apr+ayield-adiv
  assert afin_next>=-1e-9 and abs(abook_next-acapital-afin_next)<1e-7
  cash_start=cash;debt_start=debt;borrow=p['bond'] if y==p['bond_year'] else 0.;fee=p['bond_fee'] if borrow else 0.;earmarked=max(0.,earmarked+borrow-p['bond']*w)
  repay=p['bond'] if y==p['bond_repay_year'] and not p['convert_year'] else 0.;conversion=p['bond'] if y==p['convert_year'] else 0.
  if conversion:
   issued=conversion/p['conversion_price'];shares+=issued;registered+=issued;premium+=conversion-issued
  debt+=borrow-repay-conversion
  interest=(debt_start+borrow-conversion)*p['debt_rate'];cash_interest=cash_start*p['cash_yield']
  self_cfo=base_profit*p['parent_cash_share']+rev*.010-p['parent_self_nwc_rate']*rev-rd-p['loss'][i];self_capex=rev*p['parent_maintenance_rate']+pc
  subprofit=max(0.,base_profit*(1-p['parent_cash_share']));sub_cash=max(0.,fcf-(self_cfo-self_capex-pw));upstream=min(subprofit*p['parent_sub_distribution_ratio'],sub_cash)
  bond_interest=max(0.,debt_start+borrow-conversion-p['debt0'])*p['debt_rate'];parent_interest=p['parent_reserved_debt_interest']+bond_interest
  parent_pre=parent+self_cfo-self_capex-pw+upstream+adiv+borrow-repay-fee-parent_interest-p['parent_extra_settlement'][i]
  pp=base_profit*p['parent_cash_share']-rd-p['loss'][i]+upstream+(apr+ayield)*p['parent_assoc_share']-parent_interest-fee
  retained_start=legal;statutory_start=statutory;post_loss=max(0.,pp+min(0.,legal));reserve_add=.1*post_loss if statutory<.5*registered else 0.;statutory+=reserve_add;available=legal+pp-reserve_add
  planned=p['dps'][i]*shares if i<5 else p['payout_later']*(profit+apr);group_pre=cash+fcf+adiv+cash_interest-interest+borrow-repay-fee
  sinking=p['bond']*y/p['bond_repay_year'] if y<p['bond_repay_year'] and not p['convert_year'] else 0.
  distribution=max(0.,min(planned,max(0.,group_pre-sinking-earmarked),max(0.,parent_pre-p['parent_cash_floor']-sinking-earmarked),available))
  cash=group_pre-distribution;parent=parent_pre-distribution;legal=available-distribution
  assert abs(legal+statutory-retained_start-statutory_start-pp+distribution)<1e-8
  assert cash>=-1e-8 and parent>=p['parent_cash_floor']-1e-8
  earnings=profit+apr+ayield+cash_interest-interest-fee;book_next=book+earnings-distribution+conversion;opcapital+=normal+pc+pw+nw
  assert abs(book_next-opcapital-abook_next-cash+debt)<1e-7
  assert abs(cash-cash_start-fcf-adiv-cash_interest+interest-borrow+repay+fee+distribution)<1e-8
  assert abs(book_next-book-earnings+distribution-conversion)<1e-8
  rows.append(dict(year=y,revenue=rev,mature_operating_profit=mature,project_operating_profit=p['project_profit_actual'][i],base_operating_profit=base_profit,project_rd=rd,operating_profit=profit,normal_net_reinvestment=normal,operating_required_capital=opcapital,project_capital=pc,project_working_capital=pw,extra_nwc=nw,fcf=fcf,associate_profit=apr,associate_reinvestment=areinvest,associate_distribution=adiv,associate_financial_income=ayield,associate_required_capital=acapital,associate_financial_assets=afin_next,associate_book=abook_next,cash_start=cash_start,cash_income=cash_interest,interest=interest,borrow=borrow,repay=repay,conversion=conversion,fee=fee,earmarked_project_cash=earmarked,bond_interest=bond_interest,cash=cash,debt=debt,shares=shares,planned_distribution=planned,distribution=distribution,dps=distribution/shares,parent_self_cfo_budget=self_cfo,parent_capex_budget=self_capex,parent_sub_upstream_budget=upstream,parent_cash_before_distribution=parent_pre,parent_cash_budget=parent,parent_profit_budget=pp,parent_legal_reserve_budget=legal,parent_registered_capital=registered,parent_capital_premium=premium,parent_statutory_reserve=statutory,parent_reserve_add=reserve_add,parent_post_loss_profit=post_loss,common_earnings=earnings,common_book=book_next))
  book=book_next;abook=abook_next;afin=afin_next;aprior=apr
 r=p['discount'];g=p['terminal_g'];p11=base_profit*(1+g);reinvest11=p11*g/p['terminal_roic'];ov=(p11-reinvest11)/(r-g);a11=apr*(1+g);ari=a11*g/p['assoc_incremental_return'];av=(a11-ari)/(r-g);af=release_value(afin,r,p['cash_yield'],p['cash_release_years']);fv=release_value(cash-debt,r,p['cash_yield'],p['cash_release_years']);terminal=(ov+av+af+fv)/shares;ds=[x['dps'] for x in rows];value=pv_payments(ds,r)+terminal/(1+r)**10;year5=pv_payments(ds[5:],r)+terminal/(1+r)**5
 assert abs(value-pv_payments(ds[:5],r)-year5/(1+r)**5)<1e-9
 denominator=sum(x['normal_net_reinvestment']+x['project_capital']+x['project_working_capital']+x['extra_nwc'] for x in rows[1:5])
 return dict(parameters=p,rows=rows,current_value_per_share=value,year5_value_per_share=year5,terminal10_per_share=terminal,terminal_pv_share=terminal/(1+r)**10/value,terminal_bridge=dict(operating_profit11=p11,operating_reinvestment11=reinvest11,operating_value=ov,associate_profit11=a11,associate_reinvestment11=ari,associate_operating_value=av,associate_financial_value=af,financial_value=fv,cash=cash,debt=debt,shares=shares),capital_return_year1_to5=(rows[4]['base_operating_profit']-rows[0]['base_operating_profit'])/denominator if denominator else None)
def variant(label,**kw):
 p=deepcopy(BASE);p.update(kw);p['label']=label;return run(p)
def outputs():
 d={k:variant(k,**v) for k,v in {'base':{},'core_low':dict(discount=.105,terminal_roic=.095),'core_high':dict(discount=.095,terminal_roic=.115),'cyclical_weak':dict(growth=[-.05,0,.10,.10,.07,.05,.04,.04,.03,.03],margin=[.08,.085,.10,.105,.11,.109,.108,.107,.106,.105],project_schedule=[.25,.25,.3,.2,0,0,0,0,0,0],extra_nwc=[3,1,-1,-1,0,0,0,0,0,0],assoc_profit1=3.6,assoc_growth=.03,discount=.105,terminal_roic=.095),'structural_adverse':dict(growth=[-.06,-.03,0,.01,.01,.01,.01,.01,.01,.01],margin=[.08]+[.075]*9,normal_reinvestment_rate=.033,extra_nwc=[3,2,1,0,0,0,0,0,0,0],loss=[1,1,.5,0,0,0,0,0,0,0],assoc_profit1=3.,assoc_growth=.01,discount=.11,terminal_g=.01,terminal_roic=.08,parent_extra_settlement=[2,2,0,0,0,0,0,0,0,0]),'strong_execution':dict(growth=[.10,.10,.09,.08,.07,.06,.05,.04,.03,.03],margin=[.108,.112,.115,.115,.115,.114,.113,.112,.111,.110],normal_reinvestment_rate=.029,assoc_profit1=4.5,assoc_growth=.04,discount=.095,terminal_roic=.16),'parent_collection_delay':dict(parent_extra_settlement=[5,5,5,-5,-5,-5,0,0,0,0]),'project_delay_low_return':dict(project_schedule=[.2,.2,.3,.3,0,0,0,0,0,0],project_profit_actual=[0.,0.,0.,.1,.5,1.,1.35,1.5,1.55,1.6],terminal_roic=.095),'no_bond_self_funding':dict(bond=0.,bond_fee=0.),'sensitivity_discount_plus_1pct':dict(discount=.11),'sensitivity_margin_minus_1pct':dict(margin=[x-.01 for x in BASE['margin']]),'sensitivity_slow_cash_release':dict(cash_release_years=20)}.items()}
 d['conversion_sensitivity']=[variant('conversion_'+str(x),convert_year=3,conversion_price=x) for x in [20,30,40]];d['method2']={};d['method2_inputs']={}
 for key,r,roi,ar in [('low',.105,.105,.115),('high',.095,.115,.105)]:
  g=.025;mc=deferred_cohorts(21.5*(1-g/roi),g,r);ac=deferred_cohorts(4.2*(1-g/.12),g,ar);net=release_value(BASE['cash0']-BASE['debt0'],r,.01,10);project=sum(24.55*w/(1+r)**(j+1) for j,w in enumerate([.4,.4,.2]));d['method2'][key]=(mc['value']+ac['value']+net-project-.2)/S;d['method2_inputs'][key]=dict(discount=r,growth=g,incremental_return=roi,associate_discount=ar,manufacturing_cohorts=mc,associate_cohorts=ac,initial_financial_value=net,project_obligation=project,distribution_delay=2)
 simple=deepcopy(BASE);simple.update(revenue0=S,growth=[0.]*10,margin=[1.]*10,normal_reinvestment_rate=0,project_capital=0,project_rd=0,project_wc=0,cash0=0,debt0=0,assoc_book0=0,assoc_profit1=0,assoc_growth=0,assoc_cash_div=[0.]*5,bond=0,bond_fee=0,dps=[1.]*5,payout_later=1.,parent_cash_budget0=1000,parent_cash_floor=0,parent_cash_share=1,parent_self_nwc_rate=.01,parent_maintenance_rate=0,parent_reserved_debt_interest=0,terminal_g=0,discount=.10,project_profit_embedded=[0.]*10,project_profit_actual=[0.]*10)
 hand=run(simple);assert abs(hand['current_value_per_share']-10)<1e-8
 cash_case=deepcopy(simple);cash_case.update(margin=[0.]*10,cash0=50,dps=[0.]*5,payout_later=0,cash_yield=0);ch=run(cash_case);expected=50/S*(1-1.1**-10)/(10*.1)/1.1**10;assert abs(ch['current_value_per_share']-expected)<1e-9
 lc=deepcopy(simple);lc.update(revenue0=0,margin=[0.]*10,cash0=100,parent_cash_budget0=100,initial_parent_legal_reserve=2,loss=[3.]+[0.]*9,dps=[.1]*5);lh=run(lc)['rows'][0];assert lh['distribution']==0 and abs(lh['parent_legal_reserve_budget']+1)<1e-9
 rc=deepcopy(simple);rc.update(revenue0=3.,initial_parent_legal_reserve=-2.,parent_statutory_reserve0=0,cash0=100,parent_cash_budget0=100);rr=run(rc)['rows'][0];assert abs(rr['distribution']-.9)<1e-9 and abs(rr['parent_reserve_add']-.1)<1e-9
 cv=d['conversion_sensitivity'][1]['rows'][2];assert cv['parent_reserve_add']>0 and abs(cv['parent_registered_capital']+cv['parent_capital_premium']-BASE['parent_registered_capital0']-BASE['parent_capital_premium0']-22.59)<1e-8
 coupons=sum(x['bond_interest'] for x in d['base']['rows']);assert abs(coupons-22.59*.025*6)<1e-9;assert abs(sum(x['bond_interest'] for x in d['conversion_sensitivity'][1]['rows'])-22.59*.025*2)<1e-9
 d['tests']=dict(production_perpetuity_value=hand['current_value_per_share'],production_finite_cash_value=ch['current_value_per_share'],finite_cash_expected=expected,signed_loss_first_year_retained=lh['parent_legal_reserve_budget'],signed_loss_first_year_dividend=lh['distribution'],loss_recovery_dividend=rr['distribution'],loss_recovery_reserve=rr['parent_reserve_add'],six_coupon_total=coupons,conversion_reserve_add=cv['parent_reserve_add'],cash_and_equity_identities='passed');d['unit']='CNY 100m; shares 100m; per-share CNY';return d
if __name__=='__main__':
 out=Path(__file__).resolve().with_name('2026-Q3-output.json');out.write_text(json.dumps(outputs(),ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8');print(out.name)
