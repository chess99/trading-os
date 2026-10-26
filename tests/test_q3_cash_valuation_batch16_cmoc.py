#!/usr/bin/env python3
"""Independent literal reconstruction. Does NOT import/read formal model or its parameters.
CNY bn; literals re-entered from financial source/assumption worksheet. Formal JSON read only after reconstruction."""
import json,sys
from pathlib import Path

def rebuild(case):
 names=['TFM','KFM','BR','BG','IXM','ODIN']
 cash=[14,7,1.5,1.5,8,0]; debt=[.8,.4,.5,.5,34,0]; legal=[30,10,4,2,5,0]
 ownership=[.8,.7125,1,1,1,1];buffers=[3,2,.7,.7,5,.5];limits=[4,4,2,2,42,0]
 end=[15,15,20,15,30,29];working=[4,2,1,.6,36.533455,.5]
 copper_tfm=[560000,560000,560000,560000,560000,560000,560000,560000,500000,450000,400000,350000,300000,250000,200000]
 copper_kfm=[260000,310000,340000,340000,340000,340000,340000,340000,250000,200000,150000,120000,100000,80000,60000]
 cosales=[30000,40000,60000,70000,70000,70000,70000,70000,70000,70000,60000,50000,40000,30000,20000]
 coprod=[80000,70000,60000,45000,45000,45000,45000,45000,45000,45000,35000,25000,15000,10000,0]
 stock=[107718.6,88133.4];tc=10.186334732;td=22.159167733;mc=4.186334732;lr=1.36615118
 cprice=10500;ctax=.35;ccost=4600
 if case=='copper_minus_10':cprice=9450
 if case=='copper_plus_10':cprice=11550
 if case=='tax_30':ctax=.30
 if case=='tax_50':ctax=.50
 if case=='cost_plus_15':ccost=5290
 reserve=[0.]*6; caps=[3,1,.4,.2,.5,.8]; pool=0
 if case=='reserve_double':caps=[v*2 for v in caps]
 if case=='legal_zero':legal=[0.]*6
 if case=='cash_shift':cash[0]-=6;cash[4]+=6
 delay=2 if case in ('structural','odin_delay') else 0
 end[5]+=delay
 annual=[]
 for y in range(1,33):
  scale=1.02**(y-1);p=0;remit=0;newincome=0
  coprice=35000;gold=3200
  if case=='cycle':
   cprice=8500 if y<=3 else 10500;coprice=28000 if y<=3 else 35000;gold=2900 if y<=3 else 3200;ccost=4900 if y<=3 else 4600
  if case=='structural':cprice=9500;coprice=32000;ctax=.5;ccost=5500
  if case=='upside':cprice=11500;coprice=40000;gold=3700
  for i in range(6):
   if y>end[i]:continue
   dep=0;wc=0;settlement=0;cu=0
   if i<2:
    cu=(copper_tfm if i==0 else copper_kfm)[y-1]
    if case=='structural':cu*=.9
    weight=.55 if i==0 else .45
    produced=(coprod[y-1] if case!='structural' else (25000 if y<=10 else 10000))*weight;sold=min((cosales[y-1] if case!='structural' else (30000 if y<=10 else 20000))*weight,stock[i]+produced)
    stock[i]+=produced-sold
    revenue=(cu*cprice*.965+sold*coprice*.9)*6.9/1e9*scale
    expense=(cu*ccost+sold*10000)*6.9/1e9*scale+.35*scale+6.563914669/15*scale*weight
    dep=cu*700*6.9/1e9*scale
    cap=(cu*650*6.9/1e9+((2 if i==0 else 1) if 7<=y<=10 else 0))*scale
    if i==0 and y<=3:cap+=1
    if i==1 and y==1:cap+=2.5
    tax=ctax;wc=(produced-sold)*10000*6.9/1e9*scale
    settlement=(.7 if y<=2 and i==0 else 0)+(10.540270406/5 if y<=5 and i==1 else 0)
   elif i==2:
    revenue=7.2*scale;expense=5.3*scale;dep=.5*scale;cap=.65*scale;tax=.34
   elif i==3:
    q=225000*(1 if y<=7 else max(.35,1-.07*(y-7)))
    revenue=q*gold*6.9/1e9*scale;expense=q*1900*6.9/1e9*scale;dep=.35*scale;cap=.55*scale;tax=.20
   elif i==4:
    revenue=240*scale;expense=(240-(1.3/.853+34*.045))*scale;dep=.06*scale;cap=.06*scale;tax=.147;wc=36.533455*.02*scale
    if case=='cycle' and y<=2:wc+=2.5;expense+=.8*scale
    if case=='structural':expense+=.7*scale
    if case=='ixm_wc_shock' and y==1:wc+=8
    if case=='ixm_wc_shock' and y==6:wc-=8
   else:
    age=y-delay
    q=0 if age<=3 else (180000 if age==4 else (280000 if age==5 else 371000))
    cu=0 if age<=3 else (10000 if age==4 else 18597)
    revenue=(q*gold*(1-.044*(.78 if case=='stream_payment_22' else .82))+cu*cprice)*6.9/1e9*scale
    expense=(q*1300*6.9/1e9+.15)*scale;dep=.45*scale if q else 0
    cap={1:2.5,2:3,3:2.5,6:2,9:2}.get(age,.5 if q else .1)*scale;tax=.30;wc=.5 if age==4 else 0
   pretax=revenue-expense-dep
   op=pretax*(1-tax) if pretax>=0 else pretax
   if i==1 and y<=5:op-=.05*10.540270406*(1-(y-1)/5)
   earn=op-debt[i]*.045+cash[i]*.015
   net=earn+dep-cap-wc-settlement+(1 if i==5 and y==1 and case!='no_future_stream_financing' else 0)
   p+=earn*ownership[i]
   surplus=max(0,legal[i]+earn)-max(0,legal[i])
   add=min(max(0,caps[i]-reserve[i]),.05*max(0,surplus))
   legal[i]+=earn-add;reserve[i]+=add
   pay=min(debt[i],.25) if i!=4 else 0
   if i==4 and case=='ixm_wc_shock' and y>=6:pay=max(debt[i]-34,0)
   cash[i]+=net-pay;debt[i]-=pay
   if i==5 and cash[i]<buffers[i]:
    injection=buffers[i]-cash[i];cash[i]+=injection;mc-=max(0,injection-(tc-mc));tc-=injection
   draw=max(0,buffers[i]-cash[i]);debt[i]+=draw;cash[i]+=draw
   assert debt[i]<=limits[i]+1e-8
   if i==0 and y==1:cash[i]-=1.802341533;remit+=1.802341533
   if y==end[i]:
    recovery=working[i]*(scale if i==4 else 1)
    if i<2:recovery+=stock[i]*10000*6.9/1e9*.75
    closure=cash[i]+recovery-debt[i]-[1,.6,.4,.3,0,.6][i]
    cash[i]=0;debt[i]=0
    remit+=closure*ownership[i]
   else:
    decl=min(max(0,legal[i]),max(0,cash[i]-buffers[i]),(.35 if y<=5 else .85)*max(earn,0)+(.05 if y<=5 else .5)*max(cash[i]-buffers[i],0))
    if case=='remit_delay' and y<=2:decl=0
    cash[i]-=decl;legal[i]-=decl
    receipt=decl*ownership[i]*(1 if i==4 else .95)
    remit+=receipt;newincome+=receipt
  dom=(3.2 if y<=8 else max(0,3.2-.64*(y-8)))*scale if y<=13 else 0
  if case=='cycle' and y<=3:dom*=.65
  if case=='structural':dom*=.75
  dom+=.45 if y<=10 else 0
  dom-=(.6 if y<=15 else .2)*scale
  cap=.45*scale if y<=13 else 0;dep=.3*scale if y<=13 else 0
  common=dom-td*.045+tc*.015;p+=common;lr+=common+newincome
  pf=common+dep-cap
  release=(5.948578055-.228973 if y==1 else (7.951387165+.228973 if y==10 else (2.871809985 if y==32 else 0)))
  tc+=pf+remit+release;mc+=pf+remit
  pay=min(td,8.28 if y==1 else (5 if y<=4 else 1));mc-=max(0,pay-(tc-mc));tc-=pay;td-=pay
  draw=max(0,(3 if y<32 else 0)-tc);tc+=draw;td+=draw
  repayment=min(pool,max(0,mc-1));pool-=repayment;mc-=repayment
  advance=min(max(0,1-mc),max(0,tc-mc),max(0,10-pool));mc+=advance;pool+=advance
  assert mc>=0 and mc<=tc+1e-8 and pool<=10 and td<=36+1e-8
  target=.3*max(p,0) if y<=(10 if case=='payout_delay' else 5) else max(.75*max(p,0),.9*max(tc-15,0))
  div=min(target,max(lr,0),max(mc-1,0),max(tc-3,0))
  if y==32:div=max(0,tc-td);tc-=td;td=0;lr=0
  else:lr-=div
  tc-=div;mc-=min(mc,div)
  if y==32:mc=0;pool=0
  annual.append({'year':y,'dividend':div/21.394310176,'common_profit':p,'treasury_cash':tc,'parent_legal_retained':lr,'parent_debt':td,'mother_cash':mc,'cashpool_payable':pool})
 vals=[]
 for r in [.115,.10]:
  pv=sum(a['dividend']/(1+r)**a['year'] for a in annual)
  tv=sum(a['dividend']/(1+r)**(a['year']-5) for a in annual[5:])
  vals.append({'pv':pv,'tv5':tv})
 return {'annual':annual,'valuation':vals}

ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/603993/models'
def test_cmoc_literal_finite_mines_stream_and_legal_chain():
 cases=['base','cycle','structural','upside','copper_minus_10','copper_plus_10','tax_30','tax_50','cost_plus_15','ixm_wc_shock','remit_delay','legal_zero','cash_shift','payout_delay','odin_delay','reserve_double','no_future_stream_financing','stream_payment_22']
 rebuilt={c:rebuild(c) for c in cases}
 formal=json.loads((ROOT/'2026-Q3-output.json').read_text())
 for c,d in rebuilt.items():
  target=formal['scenarios'][c]
  for a,b in zip(d['valuation'],target['valuation']):
   for k in ['pv','tv5']:assert abs(a[k]-b[k])<1e-9
  assert len(d['annual'])==len(target['annual'])==32
  for a,b in zip(d['annual'],target['annual']):
   assert abs(a['dividend']-b['distribution_per_share'])<1e-9
   for k in ['common_profit','parent_legal_retained','parent_debt','mother_cash','cashpool_payable']:assert abs(a[k]-b[k])<1e-8

def test_cmoc_actual_functions_loss_reserve_pool_and_project_delay():
 import runpy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']()
