#!/usr/bin/env python3
"""伟明环保2026Q3独立重建。标准库单文件；亿元/亿股；全部路径JSON stdout。"""
import json,copy
ASOF='2026-10-27T22:43:00+00:00'
F=dict(shares=(2048457418-19116108)/1e8,cash=2052820528.65/1e8,financial=448572344.59/1e8,
 restricted=(2221229073.31-2052820528.65)/1e8,other_assets=(39000000+3772285.57+76498111.61)/1e8,
 debt=(981546519.32+834651889.15+4352025532.63+1525843657.59+10068317.19+773219592.03+6312236.75)/1e8,
 bond_book=1525843657.59/1e8,bond_face=14.76619,nci=2055798043.81/1e8,associate=782890030.57/1e8,
 parent_cash=134366068.82/1e8,parent_retained=3253230976.98/1e8,parent_reserve=783771448.94/1e8,
 registered=1704558119/1e8,parent_ar=.1,internal_receivable=(1272861069.28-10000000+1288744553.64)/1e8)
B=dict(dom_revenue=[38,38.6,39.2,39.5,39.8],dom_cost=[8.8,9.1,9.4,9.7,10],dom_maint=[3,3.1,3.2,3.3,3.4],dom_growth=[3,2.5,2,1.5,1.5],dom_wc=[1,.8,.6,.4,.4],
 eq_revenue=[16,17,18,19,20],eq_margin=.32,eq_growth=[.6,.5,.4,.4,.4],eq_wc=[.7,.5,.4,.4,.4],
 mat_revenue=[9,11,13,14,15],mat_margin=[.06,.07,.08,.09,.1],mat_maint=[.9,1,1.1,1.2,1.3],mat_growth=[2,1.2,.6,.2,.1],mat_wc=[.6,.5,.4,.3,.2],
 upstream=1.,refinance=10.,parent_cash_shift=0.,registered=F['registered'],impair=[0]*5,guarantee=[0]*5,
 dom_tail_scale=1.,dom_tail_cost=0.,life_shift=0,eq_tail_scale=1.,mat_tail_scale=1.,assoc_scale=1.,nci_scale=1.,runoff_wc=18.,
 foreign_cost=24.14,foreign_overrun=1.,foreign_start=3,foreign_kwh=290,foreign_util=.88,foreign_toncost=170,foreign_rate=.05,
 material_runoff=False,support_years=20,closure=1.,internal_authorized=0.,internal_payable_capacity=0.,
 preference_mode='arrears',preference_start=3,extra_funding='listed_all',closure_pref_settlement=True)
def pv(xs,r):return sum(x/(1+r)**(i+1) for i,x in enumerate(xs))
def legal(retained,reserve,capital,profit):
 add=min(max(0.,capital*.5-reserve),max(0.,profit+min(retained,0.))*.1)
 return retained+profit-add,reserve+add,add

def preference(due_open,minimum,distributable,mode):
    due=due_open+minimum
    paid=min(distributable,max(.3*distributable,due)) if distributable>0 else 0.
    shortfall=max(0.,due-paid)
    topup=shortfall if mode=='sponsor_topup' else 0.
    return dict(accrued=minimum,project_paid=paid,sponsor_paid=topup,arrears=shortfall-topup,
                B_dividend=distributable-paid)

def project(p):
 cost=p['foreign_cost']*p['foreign_overrun'];borrowing=p['foreign_cost']*.7;original_equity=p['foreign_cost']*.3
 # Original equity is a financing budget. No original party undertakes automatic extra calls.
 overrun=max(0.,cost-p['foreign_cost']);a_paidin=original_equity*.3
 debt=cash=retained=reserve=arrears=0.;rows=[];flows=[]
 for y in range(1,37):
  opening=cash;cap=cost/2 if y<=2 else 0.;loan=borrowing/2 if y<=2 else 0.
  original_call=original_equity/2 if y<=2 else 0.;extra_cap=overrun/2 if y<=2 else 0.
  listed_original=original_call*.553;other_original=original_call*.447
  listed_extra=extra_cap*(.553 if p['extra_funding']=='pro_rata_confirmed' else 1.)
  other_extra=extra_cap-listed_extra;debt+=loan
  active=p['foreign_start']<=y<p['foreign_start']+30
  revenue=3000*365*p['foreign_util']*p['foreign_kwh']*.2*(24.14/3.5)/1e8 if active else 0.
  costs=3000*365*p['foreign_util']*p['foreign_toncost']/1e8+.15 if active else 0.
  da=cost/30 if active else 0.;interest=debt*p['foreign_rate'];pretax=revenue-costs-da-interest
  tax=max(0.,pretax+min(retained,0.))*.22;profit=pretax-tax;retained+=profit
  add=min(max(0.,original_equity*.2-reserve),max(0.,retained)*.1);retained-=add;reserve+=add
  principal=min(debt,borrowing/15) if active else 0.;debt-=principal;maintenance=.35 if active else 0.
  closing=y==p['foreign_start']+30;closure=.1 if closing else 0.
  cash+=profit+da-maintenance-principal+loan+original_call+extra_cap-cap-closure
  support=max(0.,-cash);cash+=support
  listed_support=support*(.553 if p['extra_funding']=='pro_rata_confirmed' else 1.);other_support=support-listed_support
  total_div=max(0.,min(cash,retained)) if active else 0.
  # The trigger is an explicit contract interpretation condition, never inferred from first actual cash.
  minimum=a_paidin*.05 if p['preference_start']<=y<p['foreign_start']+30 else 0.
  pref=preference(arrears,minimum,total_div,p['preference_mode']);arrears=pref['arrears']
  cash-=total_div;retained-=total_div
  listed_pref_topup=pref['sponsor_paid'] # separate sponsor obligation, not fake legal project profit
  liquidation=cash if closing else 0.;liquidation_A=liquidation_B=settlement=0.
  if closing:
   senior=min(liquidation,arrears);arrears-=senior;residue=liquidation-senior
   liquidation_A=senior+residue*.3;liquidation_B=residue*.7;cash-=liquidation
   if p['closure_pref_settlement']:settlement=arrears;arrears=0.
  common=.79*(pref['B_dividend']+liquidation_B)-listed_original-listed_extra-listed_support-listed_pref_topup-settlement
  assert abs(cash-(opening+profit+da-maintenance-principal+loan+original_call+extra_cap-cap-closure+support-total_div-liquidation))<1e-8
  assert abs((listed_original+other_original)-original_call)<1e-9
  assert abs(listed_support+other_support-support)<1e-9
  rows.append(dict(year=y,revenue=revenue,pretax=pretax,tax=tax,profit=profit,capex=cap,new_debt=loan,
   original_equity=original_call,extra_capital=extra_cap,listed_original=listed_original,other_original=other_original,
   listed_extra=listed_extra,other_extra=other_extra,interest=interest,principal=principal,debt=debt,maintenance=maintenance,closure=closure,
   support=support,listed_support=listed_support,other_support=other_support,dividend=total_div,
   A_minimum_accrued=minimum,A_project_paid=pref['project_paid'],A_sponsor_paid=listed_pref_topup,A_arrears=arrears,
   B_dividend=pref['B_dividend'],A_paidin_basis=a_paidin,retained=retained,reserve=reserve,cash=cash,
   liquidation=liquidation,liquidation_A=liquidation_A,liquidation_B=liquidation_B,A_closure_sponsor_settlement=settlement,common=common))
  flows.append(common)
 unresolved=arrears>1e-9
 return dict(rows=rows,flows=flows,pv=pv(flows,.12) if not unresolved else None,terminal=pv(flows[5:],.12) if not unresolved else None,
  unresolved_rights=unresolved,unpaid_A_claim=arrears,funding_condition=p['extra_funding'],preference_condition=p['preference_mode'],
  listed_extra_obligations=sum(x['listed_extra']+x['listed_support']+x['A_sponsor_paid']+x['A_closure_sponsor_settlement'] for x in rows),
  uncommitted_other_extra=sum(x['other_extra']+x['other_support'] for x in rows))

def run(p,high=False):
 overseas=project(p);cash=F['cash']+F['financial']-2.5;parent=F['parent_cash']+p['parent_cash_shift'];ar=F['parent_ar'];retained=F['parent_retained'];reserve=F['parent_reserve'];internal=F['internal_receivable'];nci=F['nci'];debt=F['debt'];taxloss=0.;rows=[];divs=[];authorized=p['internal_authorized'];payable_capacity=p['internal_payable_capacity'];bond_book=F['bond_book']
 for i in range(5):
  y=i+1;opening=cash;popening=parent;oldar=ar
  dn=(p['dom_revenue'][i]-p['dom_cost'][i]-6-2.9)*.8;dc=dn+6-p['dom_maint'][i]-p['dom_growth'][i]-p['dom_wc'][i]
  en=(p['eq_revenue'][i]*p['eq_margin']-1.5)*.8;ec=en+.3-.35-p['eq_growth'][i]-p['eq_wc'][i]
  mp=p['mat_revenue'][i]*p['mat_margin'][i]-.65;mt=max(0.,mp+taxloss)*.05;taxloss=min(0.,taxloss+mp);mn=mp-mt
  mc=mn+1.3-p['mat_maint'][i]-p['mat_growth'][i]-p['mat_wc'][i]
  nprofit=.9717257385+.37*(mn+.11);npay=max(0.,nprofit)*.3;nci+=nprofit-npay
  new=p['refinance'] if y==2 else 0.;redemption=F['bond_face']*1.1 if y==2 else 0.
  bond_accretion=(F['bond_face']*1.1-F['bond_book'])*([.4,.6][i] if i<2 else 0.)
  bond_open=bond_book;bond_book+=bond_accretion;debt+=bond_accretion
  if y==2:debt+=new-bond_book;bond_book=0.
  coupon=F['bond_face']*.018 if y==1 else 0.;interest=(3+(.042*p['refinance'] if y>=3 else 0)+coupon)*.8
  fi=opening*.015;assoc=[0,.1,.2,.3,.3][i];over=overseas['flows'][i];settle=[.5,.5,0,0,0][i]
  fcff=dc+ec+mc;flow=fcff-interest-npay+fi+assoc+over-settle-p['guarantee'][i];cash+=flow+new-redemption
  declared=[10.5,10.5,11,11.5,12][i]*p['upstream']*max(0.,min(1.25,fcff/14));receipt=oldar+.95*declared;ar=.05*declared
  pi=.25+coupon if y<=2 else .25+.042*p['refinance'];pp=declared+.2-pi-p['impair'][i]-bond_accretion
  retained,reserve,addition=legal(retained,reserve,p['registered'],pp)
  parent+=receipt+.2-pi+over+new-redemption-settle-p['guarantee'][i]
  collect=min(max(0.,.5-parent),max(0.,cash-parent-3),internal,authorized,payable_capacity) if parent<.5 else 0.;parent+=collect;internal-=collect;authorized-=collect;payable_capacity-=collect
  if parent < -1e-9 or cash < -1e-9:
   return dict(status='payment_failure',failure=dict(year=y,parent_required_payment_shortfall=max(0.,-parent),group_required_payment_shortfall=max(0.,-cash),internal_book_remaining=internal,authorized_remaining=authorized,debtor_payable_capacity_remaining=payable_capacity,conditional_principal_collected=collect,unpaid_obligations='no negative cash financing permitted; debt discharge and planned spending not certified'),value=None,terminal_per_share=None,auxiliary=None,dividends=divs+[None]*(5-len(divs)),rows=rows,overseas=overseas,material_tail=[],terminal=None,aux_bridge=None,conditional_collections=sum(x['conditional_collection'] for x in rows)+collect,stopped_before_normal_distribution=True)
  paid=max(0.,min([.3,.3,.4,.45,.5][i]*F['shares'],parent-.5,cash-3,retained));parent-=paid;cash-=paid;retained-=paid
  assert abs(cash-(opening+flow+new-redemption-paid))<1e-8
  assert abs(parent-(popening+receipt+.2-pi+over+new-redemption-settle-p['guarantee'][i]+collect-paid))<1e-8
  assert abs(ar-(oldar+declared-receipt))<1e-8 and paid<=retained+paid+1e-8
  divs.append(paid/F['shares'])
  rows.append(dict(year=y,dom_nopat=dn,dom_fcff=dc,eq_nopat=en,eq_fcff=ec,mat_nopat=mn,mat_fcff=mc,fcff=fcff,nci_profit=nprofit,nci_paid=npay,nci=nci,interest=interest,financial_income=fi,associate=assoc,overseas=over,settlement=settle,guarantee=p['guarantee'][i],new_debt=new,redemption=redemption,debt=debt,bond_book=bond_book,bond_opening=bond_open,bond_financing_accretion=bond_accretion,cash=cash,declared=declared,received=receipt,parent_ar=ar,parent_profit=pp,parent_reserve=reserve,parent_reserve_add=addition,parent_retained=retained,parent_cash=parent,conditional_collection=collect,internal_receivable=internal,dividend=paid,dividend_per_share=divs[-1],feasible=cash>=0 and parent>=0))
 if overseas['unresolved_rights']:
  return dict(status='unresolved_senior_rights',value=None,terminal_per_share=None,auxiliary=None,dividends=divs,rows=rows,overseas=overseas,material_tail=[],terminal=None,aux_bridge=None,conditional_collections=sum(x['conditional_collection'] for x in rows))
 w=.075 if high else .085;k=.10 if high else .11;life=(19 if high else 15)+p['life_shift'];decay=.995 if high else .99
 maintenance_bump=p['dom_maint'][-1]-3.4
 d=((41 if high else 39)*p['dom_tail_scale']-(10 if high else 10.3)-p['dom_tail_cost']-6-3)*.8+6-(3.4 if high else 3.7)-maintenance_bump-.4
 dv=pv([d*decay**i for i in range(life)],w);release=(p['runoff_wc']+2.5+F['restricted'])/(1+w)**life
 ec=((20 if high else 18)*.32-1.5)*.8-.45;ec*=p['eq_tail_scale'];ev=ec/(.09 if high else .105)
 mc=(((18 if high else 15)*(.11 if high else .09)-.65)*.78-.5)*p['mat_tail_scale'];mrows=[];mr=.11 if high else .125
 if p['material_runoff']:
  pre=p['mat_revenue'][-1]*p['mat_margin'][-1]-.65;mc=pre-max(0.,pre)*.22+1.3-p['mat_maint'][-1]-p['mat_growth'][-1]-p['mat_wc'][-1]
  for j in range(1,p['support_years']+2):
   op=mc if j<=p['support_years'] else 0.;close=p['closure'] if j==p['support_years']+1 else 0.;net=op-close
   mrows.append(dict(year=5+j,operating=op,closure=close,net=net,group_support=max(0.,-net),minority_contribution=0.,closing_cash=net+max(0.,-net)))
  mv=pv([x['net'] for x in mrows],mr)
 else:mv=mc/mr
 av=max(0.,F['associate']*(1.15 if high else .85)*p['assoc_scale']-.9);nv=nci*p['nci_scale'];sale=F['other_assets']*(1 if high else .8)
 terminal=dv+release+ev+mv+overseas['terminal']+av+sale+cash-debt-nv
 tv=terminal/F['shares'];value=pv(divs,k)+tv/(1+k)**5
 # Same economic obligations, normalized finite asset method at valuation date.
 dt=pv([d*decay**i for i in range(life+5)],w)+(p['runoff_wc']+2.5+F['restricted'])/(1+w)**(life+5)
 mt=pv([mc]*5,w)+mv/(1+w)**5 if mrows else mv
 investments=[p['dom_growth'][i]+p['dom_wc'][i]+p['eq_growth'][i]+p['eq_wc'][i]+p['mat_growth'][i]+p['mat_wc'][i] for i in range(5)]
 extra=pv([investments[i]+[.5,.5,0,0,0][i] for i in range(5)],w)
 ramp=pv([d+ec+mc-rows[i]['fcff']-investments[i] for i in range(5)],w)
 guarantee=pv(p['guarantee'],w);premium=(F['bond_face']*1.1-F['bond_book'])/(1+w)**2
 auxiliary=(dt+ev+mt+overseas['pv']+F['associate']*(1.15 if high else .85)*p['assoc_scale']+sale+F['cash']+F['financial']-2.5-F['debt']-F['nci']*p['nci_scale']-extra-ramp-guarantee-premium)/F['shares']
 return dict(status='conditional_5y_feasible',value=value,terminal_per_share=tv,dividends=divs,terminal_share=tv/(1+k)**5/value,auxiliary=auxiliary,rows=rows,overseas=overseas,material_tail=mrows,conditional_collections=sum(x['conditional_collection'] for x in rows),terminal=dict(domestic=dv,runoff=release,equipment=ev,materials=mv,overseas=overseas['terminal'],associate=av,other_assets=sale,cash=cash,debt=-debt,nci=-nv,total=terminal,dom_cash=d,eq_cash=ec,mat_cash=mc,life=life,wacc=w,cost_equity=k,permanent_maintenance_bump=maintenance_bump),aux_bridge=dict(domestic=dt,equipment=ev,materials=mt,overseas=overseas['pv'],growth_wc_settlement=extra,ramp=ramp,guarantee=guarantee,redemption_premium=premium))

def scenarios():
 out={}
 for n in ['base','cyclical','structural','upside','domestic_minus10','life_minus3','upstream_minus20','refinance_zero','parent_cash_zero','nci_plus25','registered_sharecapital','runoff_zero','support30','closure3','internal_partial','internal_full','others_confirmed','preferred_topup','preferred_start11','unsettled_preference','structural_full']:
  p=copy.deepcopy(B)
  if n=='cyclical':p.update(eq_revenue=[12,13,16,19,20],mat_margin=[0,.02,.05,.09,.1],mat_wc=[1.2,.8,.2,-.2,-.2],foreign_start=4,foreign_overrun=1.1,upstream=.9)
  if n in ['structural','structural_full','support30','closure3']:
   p.update(dom_revenue=[x*.9 for x in p['dom_revenue']],dom_cost=[x+1 for x in p['dom_cost']],dom_maint=[x+.8 for x in p['dom_maint']],dom_wc=[2,1.5,1,.7,.5],eq_revenue=[12,12,13,13,13],eq_margin=.27,mat_margin=[-.02,0,.02,.03,.03],mat_growth=[3,2,1,.5,.5],upstream=.75,foreign_overrun=1.25,foreign_start=5,foreign_kwh=260,foreign_toncost=210,foreign_rate=.065,dom_tail_scale=.9,dom_tail_cost=1.,life_shift=-3,eq_tail_scale=.6,material_runoff=True,assoc_scale=.6,impair=[2,1,0,0,0],refinance=6.,guarantee=[0,.6,0,0,0])
  if n in ['structural_full','support30','closure3']:p.update(internal_authorized=25.,internal_payable_capacity=25.)
  if n=='support30':p['support_years']=30
  if n=='closure3':p['closure']=3
  if n=='upside':p.update(dom_revenue=[x*1.03 for x in p['dom_revenue']],eq_revenue=[18,20,22,23,24],eq_wc=[.9,.7,.6,.5,.5],mat_margin=[.08,.1,.12,.13,.13],mat_revenue=[10,13,16,18,20],mat_wc=[.8,.7,.6,.4,.4],foreign_kwh=320,foreign_util=.9,foreign_toncost=160,dom_tail_scale=1.03,eq_tail_scale=1.15,mat_tail_scale=1.3,assoc_scale=1.1)
  if n=='domestic_minus10':p.update(dom_revenue=[x*.9 for x in p['dom_revenue']],dom_tail_scale=.9)
  if n=='life_minus3':p['life_shift']=-3
  if n=='upstream_minus20':p['upstream']=.8
  if n in ['refinance_zero','internal_partial','internal_full']:p['refinance']=0
  if n=='internal_partial':p.update(internal_authorized=2.,internal_payable_capacity=1.)
  if n=='internal_full':p.update(internal_authorized=12.,internal_payable_capacity=12.)
  if n=='others_confirmed':p['extra_funding']='pro_rata_confirmed'
  if n=='preferred_topup':p['preference_mode']='sponsor_topup'
  if n=='preferred_start11':p['preference_start']=11
  if n=='unsettled_preference':p.update(foreign_overrun=1.25,foreign_start=5,foreign_kwh=0,foreign_toncost=210,foreign_rate=.065,closure_pref_settlement=False)
  if n=='parent_cash_zero':p['parent_cash_shift']=-F['parent_cash']
  if n=='nci_plus25':p['nci_scale']=1.25
  if n=='registered_sharecapital':p['registered']=20.48457418
  if n=='runoff_zero':p['runoff_wc']=0
  out[n]=dict(parameters=p,low=run(p),high=run(p,True))
 return out

def tests(cases):
 assert legal(-2,1,10,3)==(.9,1.1,.1)
 assert legal(1,5,10,2)==(3,5,0)
 assert abs(pv([11,12.1],.1)-20)<1e-10
 # Actual preference waterfall: below-minimum cash, arrears subsequently paid, no fake legal income.
 a=preference(0,.1,.04,'arrears');assert abs(a['arrears']-.06)<1e-10 and a['B_dividend']==0
 b=preference(a['arrears'],.1,.2,'arrears');assert abs(b['project_paid']-.16)<1e-10 and abs(b['B_dividend']-.04)<1e-10
 a=preference(.2,.1,0,'sponsor_topup');assert abs(a['sponsor_paid']-.3)<1e-10 and a['arrears']==0
 p=copy.deepcopy(B);p.update(foreign_cost=10.,foreign_rate=.1)
 z=project(p);assert abs(z['rows'][0]['listed_original']-.8295)<1e-10 and abs(z['rows'][0]['listed_support']-.35)<1e-10
 assert abs(z['flows'][0]+1.1795)<1e-10
 p['extra_funding']='pro_rata_confirmed';z=project(p);assert abs(z['flows'][0]+1.02305)<1e-10
 # Production payment failure paths must have no resumed normal distributions or endpoint.
 for n in ['refinance_zero','internal_partial']:
  t=cases[n]['low'];assert t['status']=='payment_failure' and t['value'] is None and t['auxiliary'] is None
  fail=t['failure']['year'];assert all(x is None for x in t['dividends'][fail-1:])
 assert cases['internal_full']['low']['status']=='conditional_5y_feasible'
 assert cases['structural_full']['low']['status']=='conditional_5y_feasible'
 z=cases['unsettled_preference']['low']['overseas'];assert z['unresolved_rights'] and z['terminal'] is None and z['rows'][-1]['A_arrears']>0
 z=cases['structural_full']['low']['overseas'];assert z['uncommitted_other_extra']==0
 # Remaining bond carrying value + all future expense - cash coupons/redemption = zero.
 rows=cases['base']['low']['rows'];assert abs(F['bond_book']+sum(t['bond_financing_accretion'] for t in rows)-F['bond_face']*1.1)<1e-10
 checks=0
 for c in cases.values():
  for high in [False,True]:
   t=c['high' if high else 'low']
   if t['status']!='conditional_5y_feasible':continue
   q=copy.deepcopy(c['parameters']);q['guarantee'][1]+=.6;g=run(q,high);w=t['terminal']['wacc']
   if g['status']=='conditional_5y_feasible':assert abs(t['auxiliary']-g['auxiliary']-.6/(1+w)**2/F['shares'])<1e-9
   q=copy.deepcopy(c['parameters']);q['dom_maint']=[x+.2 for x in q['dom_maint']];g=run(q,high)
   if g['status']=='conditional_5y_feasible':assert abs(t['terminal']['domestic']-g['terminal']['domestic']-pv([.2*(.995 if high else .99)**i for i in range(t['terminal']['life'])],w))<1e-8
   checks+=2
 return dict(production_hand_cases=11,conditional_endpoint_regressions=checks,cash_conservation='Every executed project, consolidated and parent row; failed payments terminate',rights='A accrued, paid, arrears, sponsor topup and terminal settlement; no unproven waiver')
def output():
 c=scenarios();return dict(symbol='CN:603568',report_period='2026-Q3',information_cutoff=ASOF,units='亿元、亿股',facts=F,cases=c,tests=tests(c),published=dict(value_range=None,return_model=None,reason='海外支持担保上限、A类触发/累积/补足及追加出资主体未获充分约束；条件计算不可冒充核心普通股价值/实际分配承诺'))
if __name__=='__main__':print(json.dumps(output(),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
