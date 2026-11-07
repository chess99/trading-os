"""百亚股份；金额百万元，股数百万；仅标准库。运行写同目录output。"""
import json, pathlib, copy
SHARES=429.647790
# Real legal persons; units CNY million. Registered amounts are distinct from paid
# subscriptions, investment cost, external eligible shares and operating capital.
ENTITY_FACTS={
 'parent':{'name':'重庆百亚卫生用品股份有限公司','jurisdiction':'CN-mainland','share_capital_disclosed':429.647790,'registered_capital_independently_confirmed':None,'registered_capital_budget':429.647790,'paid_in_capital':None,'surplus_total_disclosed':171.647242,'statutory_exact_individual':None,'individual_retained_H1':583.177481},
 'subsidiary':{'name':'百亚（浙江）健康科技有限公司','disclosed_alias':'杭州百亚','jurisdiction':'CN-mainland','ownership':1.,'registered_capital':40.,'paid_in_capital':None,'actual_statutory_reserve':None,'actual_distributable_retained':None}}
def profit_capacity(retained,reserve,registered,profit,continue_above_threshold=False):
 # Article210 permits stopping at registered50%, not mandatorily stopping.
 # Losses first; continuation is an explicit policy scenario, not default legal law.
 eligible=max(0.,profit+min(retained,0.))
 charge=.1*eligible if continue_above_threshold else min(.1*eligible,max(registered*.5-reserve,0.))
 return retained+profit-charge,reserve+charge,charge

def capital_return_budget(available,registered,parent_investment_cost,requested,ownership=1.,friction=.02,parent_tax=.25,tax_basis_ratio=1.):
 # Partial proportional capital reduction of a named company, not an ordinary dividend.
 # Cost is parent's carrying cost of its interest; ownership unchanged when all owners reduce pro rata.
 gross=min(max(available,0.),max(requested,0.),max(registered,0.))
 allocated_cost=parent_investment_cost*gross/registered if registered else 0.
 parent_gross=gross*ownership;fee=parent_gross*friction;proceeds=parent_gross-fee
 disposal_profit=proceeds-allocated_cost
 # Tax basis is NOT the disclosed accounting carrying value. Core uses a conditional
 # paid-capital budget equal to registered capital; zero-basis sensitivity taxes all
 # net proceeds and assumes no dividend exemption. No loss produces an immediate refund.
 allocated_tax_basis=gross*ownership*tax_basis_ratio
 tax=max(proceeds-allocated_tax_basis,0.)*parent_tax
 return {'gross_capital_return':gross,'allocated_tax_basis_budget':allocated_tax_basis,'tax_basis_ratio_budget':tax_basis_ratio,'parent_cash':proceeds-tax,'parent_investment_cost_released':allocated_cost,'parent_profit':disposal_profit-tax,'parent_cash_tax':tax,'friction_cash':fee,'minority_cash':gross*(1-ownership),'registered_after':registered-gross,'parent_investment_cost_after':parent_investment_cost-allocated_cost,'ownership_after':ownership,'listed_shares_change':0.,'sub_capital_units_remaining_ratio':(registered-gross)/registered if registered else 0.}

PARAMS={'base': {'revenue':[3550,3760,4020,4260,4470,4649,4812,4956,5105,5258], 'ebit_margin':[.070,.080,.088,.094,.096,.096,.095,.094,.093,.092], 'capex':[140,145,150,155,160,164,168,172,177,182], 'wc_ratio':.10,'g':.02},
'cyclical':{'revenue':[3300,3510,3900,4170,4400,4576,4736,4878,5024,5175],'ebit_margin':[.025,.055,.080,.090,.096,.096,.095,.094,.093,.092],'capex':[125,130,145,150,158,162,166,170,175,180],'wc_ratio':.14,'g':.02},
'structural':{'capital_recovery_policy':'periodic','capital_recovery_start_year':13,'capital_recovery_interval':5,'capital_recovery_friction':.02,'revenue':[3200,3040,2950,2950,2970,2990,3010,3030,3050,3070],'ebit_margin':[-.025,-.01,.015,.025,.03,.03,.03,.03,.03,.03],'capex':[120]*10,'wc_ratio':.18,'g':0},
'optimistic':{'revenue':[3700,4070,4477,4870,5210,5523,5799,6031,6212,6398],'ebit_margin':[.085,.10,.112,.12,.122,.12,.118,.116,.114,.112],'capex':[155,165,180,195,205,215,225,230,235,240],'wc_ratio':.10,'g':.02}}
def discounted(flows,r,terminal=0):
 return sum(v/(1+r)**(i+1) for i,v in enumerate(flows))+terminal/(1+r)**len(flows)
def project(p, opening_cash=418.753180, parent_cash=376.877862, legal=500, reserve=171.647242, limit=100, parent_fraction=.90, registered_parent=429.647790, registered_sub=40., paid_parent=None, paid_sub=None, sub_opening_capacity=0., sub_opening_reserve=0., continue_reserve=False):
 sublegal=sub_opening_capacity; subreserve=sub_opening_reserve; interloan=0.
 cash=opening_cash; pcash=parent_cash; prev_rev=3559.134314; debt=0.; rows=[]; feasible=True
 prev_wc=prev_rev*.10; minimum=150
 for i,(rev,m,capex) in enumerate(zip(p['revenue'],p['ebit_margin'],p['capex'])):
  parent_tax=.15 if i<4 else ((.15*67+.25*298)/365 if i==4 else .25)
  # Y5 [2030-10-26,2031-10-26):67 days15%,298 days25%; uniform pretax-profit timing budget, not actual monthly earnings.
  tax=parent_fraction*parent_tax+(1-parent_fraction)*.25
  op=rev*m; pop=parent_fraction*op;sop=(1-parent_fraction)*op
  pnet=pop-max(pop,0)*parent_tax;snet=sop-max(sop,0)*.25
  nopat=pnet+snet # entity losses produce no immediate group tax refund
  da=100+2*i; wc=rev*p['wc_ratio']; dwc=wc-prev_wc; buf=150*rev/3559.134314; dbuf=buf-minimum
  interest=debt*.05; fcf=nopat+da-capex-dwc-dbuf-interest
  # Cash balances below exclude committed minimum operating buffer.
  if i==0: cash-=150;pcash-=150*parent_fraction
  cash+=fcf; pcash+=pnet+parent_fraction*(fcf+interest-nopat)-interest
  internal_interest=interloan*.05
  # 5% is pretax contractual-budget interest. Incremental tax paid separately:
  pitax=(max(pop+internal_interest,0)-max(pop,0))*parent_tax
  sitax=(max(sop-internal_interest,0)-max(sop,0))*.25
  pcash+=internal_interest-pitax;cash-=pitax+sitax
  fcf-=pitax+sitax
  subcash=cash-pcash
  support=max(0,-subcash);pcash-=support;interloan+=support
  repayment=min(max(cash-pcash,0),interloan);pcash+=repayment;interloan-=repayment
  compensation=50/3 if i<3 else 0
  parent_profit=pnet-parent_fraction*compensation-interest+internal_interest-pitax
  subprofit=snet-(1-parent_fraction)*compensation-internal_interest-sitax
  sublegal,subreserve,sr=profit_capacity(sublegal,subreserve,registered_sub,subprofit,continue_reserve)
  legal,reserve,reserve_add=profit_capacity(legal,reserve,registered_parent,parent_profit,continue_reserve)
  need=max(0,-cash,-pcash)
  if need:
   available=max(0,limit-debt); borrowed=min(need,available); debt+=borrowed;cash+=borrowed;pcash+=borrowed
   if borrowed+1e-8<need: feasible=False
  target=max(0,.60*(parent_profit+subprofit))
  div=max(0,min(target,legal,cash,pcash)) if feasible else 0
  pre=cash;ppre=pcash; cash-=div;pcash-=div;legal-=div
  assert abs(pre-div-cash)<1e-8 and abs(ppre-div-pcash)<1e-8
  if feasible: assert min(cash,pcash,cash-pcash)>=-1e-8
  rows.append(dict(year=i+1,parent_fraction=parent_fraction,parent_tax_rate=parent_tax,subsidiary_tax_rate=.25,intercompany_parent_tax=pitax,intercompany_sub_tax=sitax,registered_parent_budget=registered_parent,registered_sub=registered_sub,paid_parent_disclosed=paid_parent,paid_sub_disclosed=paid_sub,continue_reserve=continue_reserve,revenue=rev,ebit=op,tax_rate=tax,nopat=nopat,da=da,capex=capex,delta_wc=dwc,delta_buffer=dbuf,fcfe=fcf,external_interest=interest,parent_profit=parent_profit,reserve_add=reserve_add,legal_retained=legal,sub_legal_retained=sublegal,sub_reserve=subreserve,parent_reserve=reserve,parent_surplus_cash=pcash,subsidiary_surplus_cash=cash-pcash,intercompany_loan=interloan,intercompany_interest=internal_interest,intercompany_support=support,intercompany_repayment=repayment,group_surplus_cash=cash,debt=debt,dividend=div,dps=div/SHARES,feasible=feasible))
  prev_rev=rev;prev_wc=wc;minimum=buf
 return rows

def release_cash(last, r, g, annual_ni, annual_fcf, years=3, verification_years=0):
 # All amounts are actual entity cash; internal dividends/loans cancel on consolidation.
 pcash=last['parent_surplus_cash']-last['debt']+30
 scash=last['group_surplus_cash']-last['parent_surplus_cash']
 loan=last.get('intercompany_loan',0)
 repay=min(scash,loan);scash-=repay;pcash+=repay;loan-=repay
 lp=last['legal_retained']-(37.112891-30);ls=last['sub_legal_retained'];rp=last['parent_reserve'];rs=last['sub_reserve']
 recovery_policy=last.get('capital_recovery_policy','none');recovery_start=last.get('capital_recovery_start_year',13)-10;recovery_interval=last.get('capital_recovery_interval',5);recovery_friction=last.get('capital_recovery_friction',.02);sub_investment_cost=54.433323;tax_basis_ratio=last.get('capital_recovery_tax_basis_ratio',1.)
 fraction=last.get('parent_fraction',.9);subfraction=1-fraction;preg=last.get('registered_parent_budget',429.647790);sreg=last.get('registered_sub',40.);continued=last.get('continue_reserve',False)
 ptarget=max(pcash,0)/years;starget=max(scash,0)/years;adjustment_pv=0.;schedule=[];first_ready=None
 assert pcash>=-1e-8 and scash>=-1e-8
 for t in range(1,501):
  opening=pcash+scash
  ni=annual_ni*(1+g)**(t-1);regular=annual_fcf*(1+g)**(t-1)
  pcash+=fraction*regular;scash+=subfraction*regular
  internal_interest=loan*.05
  pitax=(max(fraction*ni/.75+internal_interest,0)-max(fraction*ni/.75,0))*.25
  sitax=(max(subfraction*ni/.75-internal_interest,0)-max(subfraction*ni/.75,0))*.25
  pcash+=internal_interest-pitax;scash-=internal_interest+sitax
  support=max(0,-scash);pcash-=support;scash+=support;loan+=support
  repayment=min(scash,loan);scash-=repayment;pcash+=repayment;loan-=repayment
  sp=subfraction*ni-internal_interest-sitax; ls,rs,sr=profit_capacity(ls,rs,sreg,sp,continued)
  # Deferred ordinary dividends remain in subsidiary cash; the same distribution
  # capacity later releases them, rather than treating delay as permanent loss.
  sub_div=min(scash,max(ls,0),subfraction*regular+max(starget,max(scash-subfraction*regular,0)/years))
  scash-=sub_div;ls-=sub_div;pcash+=sub_div
  recovery=capital_return_budget(0,sreg,sub_investment_cost,0,friction=recovery_friction,tax_basis_ratio=tax_basis_ratio)
  if recovery_policy=='periodic' and t>=recovery_start and (t-recovery_start)%recovery_interval==0:
   # scash excludes the necessary operating buffer and all ordinary dividends just paid.
   recovery=capital_return_budget(scash,sreg,sub_investment_cost,scash,friction=recovery_friction,tax_basis_ratio=tax_basis_ratio)
   scash-=recovery['gross_capital_return'];pcash+=recovery['parent_cash'];sreg=recovery['registered_after'];sub_investment_cost=recovery['parent_investment_cost_after']
  parent_profit=fraction*ni+internal_interest-pitax+sub_div+recovery['parent_profit']
  lp,rp,pr=profit_capacity(lp,rp,preg,parent_profit,continued)
  holder_div=min(pcash,max(lp,0),fraction*regular+sub_div+recovery['parent_cash']+max(ptarget,max(pcash-(fraction*regular+sub_div+recovery['parent_cash']),0)/years))
  pcash-=holder_div;lp-=holder_div
  adjustment_pv+=(holder_div-regular)/(1+r)**t
  assert min(pcash,scash)>=-1e-8
  assert abs(opening+regular-pitax-sitax-recovery['friction_cash']-recovery['parent_cash_tax']-recovery['minority_cash']-holder_div-pcash-scash)<1e-7
  schedule.append(dict(year_after_10=t,capital_recovery=recovery,subsidiary_registered_budget=sreg,parent_sub_investment_cost_remaining=sub_investment_cost,opening_group_cash=opening,operating_fcfe=regular,subsidiary_new_declaration=sub_div,parent_holder_payment=holder_div,increment_vs_gordon_payment=holder_div-regular,parent_legal=lp,subsidiary_legal=ls,parent_cash=pcash,subsidiary_cash=scash,unreleased_cash=pcash+scash,intercompany_loan=loan,intercompany_parent_tax=pitax,intercompany_sub_tax=sitax,parent_reserve=rp,subsidiary_reserve=rs))
  sub_next_reserve=profit_capacity(ls,rs,sreg,subfraction*ni*(1+g),continued)[2]
  next_sub=subfraction*regular*(1+g)
  next_p_profit=fraction*ni*(1+g)+next_sub
  next_p_charge=profit_capacity(lp,rp,preg,next_p_profit,continued)[2]
  # Sufficient perpetual inequalities use worst-case ongoing10% even if caps stop.
  sub_keep=.9 if continued or rs<sreg*.5-1e-8 else 1.
  parent_keep=.9 if continued or rp<preg*.5-1e-8 else 1.
  perpetual_sub=sub_keep*subfraction*ni>=subfraction*regular-1e-8
  perpetual_parent=parent_keep*(fraction*ni+subfraction*regular)>=regular-1e-8
  ready=(loan<1e-8 and pcash+scash<1e-8 and subfraction*ni*(1+g)-sub_next_reserve+ls>=next_sub-1e-8 and lp+next_p_profit-next_p_charge>=regular*(1+g)-1e-8 and perpetual_sub and perpetual_parent)
  schedule[-1]['perpetual_parent_margin']=parent_keep*(fraction*ni+subfraction*regular)-regular
  schedule[-1]['perpetual_sub_margin']=sub_keep*subfraction*ni-subfraction*regular
  schedule[-1]['gordon_capacity_proven']=ready
  if ready and first_ready is None:first_ready=t
  if ready and t>=first_ready+verification_years:break
 assert pcash+scash<1e-7 and schedule[-1]['gordon_capacity_proven'], (pcash,scash,lp,ls)
 return adjustment_pv,schedule

def value(p,r,release_years=3,**project_settings):
 rows=project(p,**project_settings)
 if not all(x['feasible'] for x in rows): return {'feasible':False,'rows':rows}
 g=p['g']; last=rows[-1]
 for key in ['capital_recovery_policy','capital_recovery_start_year','capital_recovery_interval','capital_recovery_friction','capital_recovery_tax_basis_ratio']:
  if key in p:last[key]=p[key]
 rev=last['revenue']*(1+g)
 # Unlevered steady cash: debt settled at year ten from cash, no perpetual interest double count.
 terminal_ni=rev*p['ebit_margin'][-1]*.75
 terminal_fcf=terminal_ni+last['da']*(1+g)-p['capex'][-1]*(1+g)-last['revenue']*p['wc_ratio']*g-150*last['revenue']/3559.134314*g
 cash_pv,schedule=release_cash(last,r,g,terminal_ni,terminal_fcf,release_years)
 tv10=terminal_fcf/(r-g)+cash_pv
 equity5=discounted([x['dividend'] for x in rows[5:]],r,tv10)
 value0=discounted([x['dividend'] for x in rows[:5]],r,equity5)/SHARES
 return dict(feasible=True,current_value=value0,year5_terminal=equity5/SHARES,terminal_pv_share=(equity5/(1+r)**5/SHARES)/value0,tail_gordon_pv_share=(terminal_fcf/(r-g))/(1+r)**10/SHARES/value0,steady_fcfe=terminal_fcf,release_schedule=schedule,year10_release_pv=cash_pv,rows=rows)
def run():
 out={'units':'CNY million; shares million','shares':SHARES,'entity_facts':ENTITY_FACTS,'state_scope':{'parent_legal_retained':'Forecast from conservative500m parent capacity budget; H1 individual583.177481m source, not Q3 actual','sub_legal_retained':'Economic remittance-capacity accumulator for named single subsidiary; actual opening retained unknown, no pooling across companies','sub_reserve':'Budget incremental retention allowance, not disclosed subsidiary statutory amount','parent_reserve':'Parent surplus171.647242m as statutory working assumption supported by same consolidated total classified entirely statutory; direct mother split not separately certified','registered_parent_budget':'Sharecapital429.647790m x par1 is registered-capital forecast proxy, not separately obtained registry extract','reserve_policy':'Core elects to stop at registered50%; continuation-after-threshold diagnostic explicitly allowed; past FY25 below threshold annual provision10% confirmed','capital_events':'No new injections; structural tail proportional capital reductions of named subsidiary start Y13 every five years only from excess cash. Equity percentage and listed shares unchanged; subsidiary nominal units/registration decline. Conditional on actual paid capital, creditor/solvency and registration process, not an announced plan','capital_recovery_basis':'Accounting cost54.433323m is disclosed mother investment cost. Tax basis is independently budgeted at registered40m, not certified; zero-basis25%cash-tax sensitivity. No immediate deduction of accounting losses. Historical subsidiary paid capital unknown.'},'parameters':PARAMS,'scenarios':{}}
 for name,p in PARAMS.items(): out['scenarios'][name]={str(r):value(p,r) for r in [.10,.11]}
 out['capital_recovery_sensitivities']={}
 for label,patch in [('dividend_only_reference',{'capital_recovery_policy':'none'}),('capital_recovery_start18',{'capital_recovery_start_year':18}),('capital_recovery_friction10',{'capital_recovery_friction':.10}),('zero_tax_basis',{'capital_recovery_tax_basis_ratio':0.})]:
  q=copy.deepcopy(PARAMS['structural']);q.update(patch);out['capital_recovery_sensitivities'][label]={str(r):value(q,r) for r in [.10,.11]}
 base=out['scenarios']['base'];out['value_range']={'low':round(base['0.11']['current_value'],2),'high':round(base['0.1']['current_value'],2)}
 out['dps']=[round(x['dps'],4) for x in base['0.1']['rows'][:5]]
 out['year5']={'low':round(base['0.11']['year5_terminal'],2),'high':round(base['0.1']['year5_terminal'],2)}
 # earnings-capitalization, normalized 25% taxation, same opening equity bridge
 out['method2']={'low':(3760*.08*.75*14+298.75318)/SHARES,'high':(4020*.088*.75*17+298.75318)/SHARES}
 s=copy.deepcopy(PARAMS['base']);s['ebit_margin']=[x-.01 for x in s['ebit_margin']];out['margin_minus_1pp']=value(s,.10)
 out['release_5years']=value(PARAMS['base'],.10,5)
 out['release_1year']=value(PARAMS['base'],.10,1)
 out['parent_fraction_70pct']=project(PARAMS['base'],parent_cash=418.753180*.7,parent_fraction=.7)

 out['entity_method_sensitivities']={}
 settings={'sub_old_loss20':{'sub_opening_capacity':-20.},'sub_reserve_already_full':{'sub_opening_reserve':20.},'continue_reserve_above_half':{'continue_reserve':True},'parent_fraction70_full_path':{'parent_cash':418.753180*.7,'parent_fraction':.7}}
 for label,kw in settings.items():
  out['entity_method_sensitivities'][label]={}
  for r in [.10,.11]:
   try: out['entity_method_sensitivities'][label][str(r)]={'settings':kw,**value(PARAMS['base'],r,**kw)}
   except (AssertionError,ValueError) as exc: out['entity_method_sensitivities'][label][str(r)]={'settings':kw,'feasible':False,'failure':str(exc),'note':'No value assigned to failed release or funding path'}
 # Same formal valuation function: constant no-reinvestment operating cash, zero cash bridge.
 assert abs(discounted([10]*5,.1,100)-100)<1e-9
 z={'revenue':[3559.134314]*10,'ebit_margin':[0]*10,'capex':[100+2*i for i in range(10)],'wc_ratio':.1,'g':0}
 zr=project(z,opening_cash=150,parent_cash=135,legal=500,limit=0)
 assert all(abs(x['fcfe'])<1e-9 and x['dividend']==0 and abs(x['group_surplus_cash'])<1e-9 for x in zr)
 p={'revenue':[100]*10,'ebit_margin':[.1]*10,'capex':[100+2*i for i in range(10)],'wc_ratio':.1,'g':0}
 rr=project(p,opening_cash=150,parent_cash=135,legal=-1000,limit=0)
 assert rr[0]['dividend']==0 and rr[0]['legal_retained'] < -1000
 assert all(x['dividend']==0 for x in project(PARAMS['structural'],opening_cash=0,parent_cash=0,legal=0,limit=0))
 assert not project(PARAMS['structural'],opening_cash=0,parent_cash=0,legal=0,limit=0)[0]['feasible']
 # Formal cash-release hand case: zero operations and 60 cash (30 parent plus
 # 30 modeled investment recovery), one-year release => PV 60/1.1.
 h={'parent_surplus_cash':30,'group_surplus_cash':30,'debt':0,'legal_retained':100,'sub_legal_retained':0,'parent_reserve':SHARES*.5,'sub_reserve':20}
 hp,hr=release_cash(h,.1,0,0,0,1)
 assert abs(hp-60/1.1)<1e-9 and abs(hr[-1]['unreleased_cash'])<1e-9
 h2=dict(h,parent_surplus_cash=0,group_surplus_cash=0,sub_legal_retained=-5)
 _,delayed=release_cash(h2,.1,0,20,10,1)
 assert abs(delayed[0]['subsidiary_cash']-1)<1e-9
 assert abs(delayed[0]['parent_holder_payment']-39)<1e-9
 assert delayed[-1]['unreleased_cash']<1e-8
 # Actual structural branch must fund subsidiary deficits via parent loans.
 assert out['scenarios']['structural']['0.1']['rows'][0]['intercompany_support']>0
 out['checks']=['formal discounted chain: five 10 cashflows plus 100 at 10%=100','negative statutory retained earnings carried','zero dividend does not cure unavailable financing','annual group parent subsidiary cash conservation', 'structural parent-to-subsidiary loan and interest tracked', 'formal release: 60 one-year cash at 10%=54.5454545', 'formal delayed legal dividend: subsidiary retains 1 in year1 then repays later']
 pathlib.Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 return out
if __name__=='__main__':
 o=run();print(json.dumps({k:o[k] for k in ['value_range','dps','year5','method2']},ensure_ascii=False,indent=2))
