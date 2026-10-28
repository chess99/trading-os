#!/usr/bin/env python3
# Independent literal arithmetic. Reads frozen output only; never imports production.
from pathlib import Path
import json
root=Path(__file__).resolve().parent
actual=json.loads((root/'2026-Q3-output.json').read_text());errors=[];snap={}
face=13.89697;book0=13.963662443;shares=2.13998399
cp=[face*x for x in [.003,.006,.01,.015,1.1]];times=[6/365,371/365,736/365,1101/365,1466/365];y=.03
for _ in range(25):
 value=sum(c/(1+y)**t for c,t in zip(cp,times))-book0
 deriv=sum(-t*c/(1+y)**(t+1) for c,t in zip(cp,times));y-=value/deriv
own=1.353*(1-3.277976/6.8)+3.25*(1-1.731/2.75)
for name,gap,df,extra,remain,air,depr in [
 ('base',0,1,0,own,[29,34,40,46,49],[4.1,4.4,4.9,5.3,5.6]),
 ('suspension_margin_pressure',.01,.85,.15,own,[29,34,40,46,49],[4.1,4.4,4.9,5.3,5.6]),
 ('project_self_paid',0,1,0,0,[31,37,42,46,49],[4.2,4.6,5,5.3,5.6]),
 ('project_self_unpaid',0,1,0,4.87,[27,31,38,45,49],[4,4.3,4.8,5.2,5.6]),
 ('project_payable_overlap',0,1,0,own-.8957315724,[29,34,40,46,49],[4.1,4.4,4.9,5.3,5.6])]:
 bank=54.358898861;parent=6.7471555747;pc=.5659278207;ret=.3730465658;nci=2.5072208398;cb=book0;capital=84.6131157283;oldwc=36.9287744237;rows=[];project=4.540956+remain;dedicated=1.950955
 for i in range(5):
  ob,op=bank,parent;ebit=[6.3175,7.5583,8.9059,9.8492,10.482][i]+(air[i]-[31,37,42,46,49][i])*([.175,.185,.195,.2,.2][i]-[.147,.144,.141,.138,.136][i])-air[i]*gap;nop=ebit*.75
  cx=[8,7.8,7.3,6.8,6.4][i]+remain*[.6,.3,.1,0,0][i]
  dwc=[39,42,44.5,46.5,48][i]-oldwc;oldwc+=dwc;netinvest=cx-depr[i]+dwc-(.8957315724 if i==0 else 0);capital+=netinvest
  fcf=nop+depr[i]-cx-dwc-[.6,.1,0,0,0][i]
  oldcb=cb
  if i<4:cb=(cb-cp[i]*(1+y)**(-6/365))*(1+y);ce=cb-oldcb+cp[i]
  else:ce=cp[i]-cb;cb=0
  dill=[3.6,3.8,4,4.2,4.4][i]*.5;hk=[1.6,1.7,1.8,1.9,2][i]*.5;friction=(dill*.9+hk)*.08
  declaration=((dill*.9+hk)*.92-.35)*.9+[.25,.35,.45,.55,.65][i]*df
  bi=(bank+(cp[i] if i==4 else 0))*.03;pi=(parent+(cp[i] if i==4 else 0))*.032
  pp=declaration-[1,1.02,1.04,1.06,1.08][i]-pi-ce
  distribution=min(shares*[.2,.2,.25,.3,.35][i],max(0,ret+pp-.1));ret+=pp-distribution
  ncid=dill*.1+[.02,.02,.03,.03,.04][i];nci+=[.43,.46,.49,.52,.55][i]-ncid
  bank+=-fcf+(bi-.135)*.8+cp[i]+ncid+distribution+friction
  pre=pc+declaration+(.4039015 if i==0 else 0)+[.5,.4,.3,.2,.1][i]-[1,1.02,1.04,1.06,1.08][i]-pi-cp[i]-.25-[.6,.5,.4,.3,.2][i]-extra
  parent+=.5-(pre-distribution);pc=.5;pd=parent-op;sd=bank-ob-pd
  pm=min(op,3.7714124162 if i==0 else op*.6);sm=max(0,min(ob,48.1334362877 if i==0 else ob*.75)-pm);pr=max(pm,-pd);sr=max(sm,-sd)
  fund=[2.8,1.4,.340956,0,0][i];selfpay=remain*[.6,.3,.1,0,0][i];paid=fund+selfpay;project-=paid;topup=max(0,fund-dedicated);dedicated+=topup-fund
  r=dict(project_spend_included_in_capex=paid,project_remaining=project,dedicated_topup_from_existing_group_pool=topup,dedicated_ending=dedicated,project_self_payment=selfpay,ebit=ebit,nopat=nop,fcff=fcf,capital=capital,foreign_friction=friction,parent_declare=declaration,parent_profit=pp,parent_retained=ret,parent_bank=parent,bank=bank,nci_equity=nci,cb_expense=ce,cb_book=cb,distribution=distribution,dps=distribution/shares,parent_pre=pre,subsidiary_pre=12.7745958424-sd,subsidiary_cash=12.7745958424,parent_gross_repayment=pr,parent_gross_borrowing=pr+pd,subsidiary_gross_repayment=sr,subsidiary_gross_borrowing=sr+sd)
  for k,v in r.items():
   err=abs(v-actual['scenarios'][name]['repay']['rows'][i][k]);assert err<1e-8,(name,i,k,v);errors.append(err)
  rows.append(r)
 ends=[]
 for w,g,ke in [(.095,.015,.14),(.085,.02,.12)]:
  np6=rows[-1]['nopat']*(1+g);ev=(np6-np6*g/.11)/(w-g);n=nci+(.55*(1+g)-ke*nci)/(ke-g);leak=.2384*(1+g)/(ke-g);equity=ev+19.7745958424-bank-n-1.480273-leak;tv=equity/shares;value=sum(r['dps']/(1+ke)**(i+1) for i,r in enumerate(rows))+tv/(1+ke)**5
  ends.append(dict(ev=ev,nci=n,friction_value=leak,equity=equity,terminal_per_share=tv,current=value))
 for i,r in enumerate(ends):
  for k,v in r.items():
   e=abs(v-actual['scenarios'][name]['endpoints'][i]['repay'][k]);assert e<1e-8,(name,i,k);errors.append(e)
 aux=[]
 for endpoint,(w,ke,n) in enumerate([(.095,.14,10),(.085,.12,5)]):
  cap=capital;initial=nop/capital;value=0;trajectory=[]
  for j in range(1,n+1):
   roc=initial+(w-initial)*(j-1)/n;np=cap*roc;investment=cap*.01;cashflow=np-investment
   value+=cashflow/(1+w)**j;trajectory.append((cap,roc,np,investment,cashflow));cap+=investment
  value+=cap/(1+w)**n
  nc=nci+(.55*1.01-ke*nci)/(ke-.01);leak=.2384*1.01/(ke-.01);eq=value+19.7745958424-bank-nc-1.480273
  eq-=leak;tv=eq/shares;current=sum(r['dps']/(1+ke)**(i+1) for i,r in enumerate(rows))+tv/(1+ke)**5
  result_aux=dict(ev=value,nci=nc,friction_value=leak,equity=eq,terminal_per_share=tv,current=current)
  for key,v in result_aux.items():
   error=abs(v-actual['scenarios'][name]['auxiliary'][endpoint][key]);assert error<1e-8,(name,'aux',key);errors.append(error)
  aux.append(dict(values=result_aux,independent_cashflow_schedule=trajectory))
 for index,(w,ke) in enumerate([(.095,.14),(.085,.12)]):
  ev_stalled=(nop-.01*capital)/(w-.01)
  nc=nci+(.55*1.01-ke*nci)/(ke-.01);leak=.2384*1.01/(ke-.01)
  tv=(ev_stalled+19.7745958424-bank-nc-1.480273-leak)/shares
  cur=sum(t['dps']/(1+ke)**(i+1) for i,t in enumerate(rows))+tv/(1+ke)**5
  for key,value in [('ev',ev_stalled),('terminal_per_share',tv),('current',cur)]:
   err=abs(value-actual['scenarios'][name]['auxiliary_no_return_repair'][index][key]);assert err<1e-8;errors.append(err)
 snap[name]=dict(rows=rows,endpoints=ends,auxiliary=aux)
assert actual['scenarios']['temporary_draw_and_return']['temporary_funds']['mandatory_return']==1.8
assert actual['scenarios']['temporary_draw_and_return']['temporary_funds']['group_cash_created']==0
assert actual['scenarios']['temporary_draw_and_return']['repay']['rows']==[dict(r,temporary_fund_draw_budget=1.8 if i==0 else 0,temporary_fund_mandatory_return=1.8 if i==0 else 0) for i,r in enumerate(actual['scenarios']['base']['repay']['rows'])]
# Failure paths must stop before asserting unfunded financing or terminal value.
for name,s in actual['scenarios'].items():
 for branch in ['repay','convert']:
  z=s[branch]
  if not z['feasible']:
   assert z['rows'][-1]['feasible'] is False
   assert all(e[branch] is None for e in s['endpoints'])
 for r in s['repay']['rows']:
  if not r['feasible']:continue
  assert abs(r['parent_bank']+r['subsidiary_bank']-r['bank'])<1e-8
  assert abs(r['parent_cash']+r['subsidiary_cash']-r['cash'])<1e-8
result=dict(passed=True,comparisons=len(errors),max_error=max(errors),independent_newton_rate=y,method='literal inputs; no production import; independent financing and legal-profit chain',recalculations=snap)
(root/'independent-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n');print({k:v for k,v in result.items() if k!='recalculations'})
