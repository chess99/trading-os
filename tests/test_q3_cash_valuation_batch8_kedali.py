"""Separate original-parameter rebuild; never imports or calls formal model functions.
Written in scalar-array form to cross-check six accounts, five explicit years and actual tail dividends.
"""
import json,math
from pathlib import Path
# P,H,J,D,F,R. Amounts billions. Literal independently transcribed source/assumption parameters.
share=.286448468;ownership=[1,1,1,1,1,.51]
capacity0=[1.7,6.5,5.5,11,1.5,.3];sales0=[1.3,5.5,4.5,8.7,.75,.05]
addition=[[.05]*5,[.8,.8,.7,.6,.5],[.8,.8,.7,.6,.5],[1.5,1.4,1.3,1.2,1],[.25,.3,.3,.25,.2],[.1,.1,.1,0,0]]
use=[[.80,.82,.84,.85,.86],[.87,.89,.90,.90,.90],[.85,.87,.89,.90,.90],[.82,.85,.87,.89,.90],[.50,.55,.62,.68,.72],[.20,.30,.40,.50,.55]]
contrib=[.24,.215,.18,.18,.25,.30];fixed=[.04,.13,.16,.25,.16,.05];depreciation=[.025,.035,.04,.04,.055,.06];working=[.12,.20,.20,.22,.25,.28]
limits=[.8,.3,.5,1,.5,.1];tax=[.15,.15,.15,.15,.23,.20]
def legal_add(ret,res,paid,p):
 available=p+min(0,ret)
 transfer=min(.1*max(0,available),max(0,.5*paid-res))
 return ret+p-transfer,res+transfer

def reconstruct(margin=0):
 cash=[.511524501+60126*105.41/1e9,.30,.20,1.1669849113469388,.15,.1591271816530612]
 reserve=[.137471634,0,0,0,0,0];retained=[1.783852672,0,0,0,-.20,-.03];paid=[.286448468,.5,1,3,.5,.2]
 debt=[.016,0,0,.014444315,.038,0];restricted=[0,0,0,1.1,0,0]
 cap=capacity0[:];old=sales0[:];dividends=[];snapshots=[]
 for t in range(5):
  of=[.25,.25,.20,.10,.05][t];orb=[.08,.08,.06,.03,.02][t]
  cash[0]-=of+orb;cash[4]+=of;paid[4]+=of
  cash[5]+=orb/.51;paid[5]+=orb/.51
  profits=[];ebits=[];revenue=[];declared=0
  for i in range(6):
   cap[i]+=addition[i][t];r=cap[i]*use[i][t];revenue.append(r)
   amortization=cap[i]*depreciation[i]
   op=r*(contrib[i]+margin)-fixed[i]*(1.025**t)-amortization;ebits.append(op)
   interest=debt[i]*.04;p=op-interest-max(0,op-interest)*tax[i]
   investment=addition[i][t]*(.85 if i>=4 else .6)
   restricted[i]-=min(restricted[i],investment if i==3 else 0)
   cash[i]+=p-(r-old[i])*working[i]-investment
   buffer=.025*r+restricted[i]
   if cash[i]<buffer:
    needed=(buffer-cash[i])/.98
    assert debt[i]+needed<=limits[i]+1e-8
    debt[i]+=needed;cash[i]+=needed*.98;p-=needed*.02
   retained[i],reserve[i]=legal_add(retained[i],reserve[i],paid[i],p)
   profits.append(p);old[i]=r
   if i in (1,2):
    d=min(max(0,retained[i]),max(0,p)*.65,max(0,cash[i]-buffer))
    retained[i]-=d;cash[i]-=d;declared+=d
  retained[0],reserve[0]=legal_add(retained[0],reserve[0],paid[0],declared)
  cash[0]+=declared
  cash[0]-=.17521234211 if t==0 else 0
  if cash[0]<0:
   new=-cash[0]+.04;assert debt[0]+new<=.8;cash[0]+=new;debt[0]+=new
  payment=min(max(0,sum(p*o for p,o in zip(profits,ownership)))*.38,max(0,retained[0]),max(0,cash[0]-.025*revenue[0]))
  cash[0]-=payment;retained[0]-=payment;dividends.append(payment/share)
  for i in range(6):
   redemption=min(debt[i],max(0,cash[i]-restricted[i]-.025*revenue[i])*.5)
   cash[i]-=redemption;debt[i]-=redemption
  snapshots.append(dict(cash=cash[:],debt=debt[:],retained=retained[:],reserve=reserve[:],paid=paid[:],restricted=restricted[:],ebit=ebits[:],revenue=revenue[:]))
 return dividends,snapshots

def independent_tail(state,rate,steady,roi,horizon=300):
 bal={k:v[:] for k,v in state.items()};cash=bal['cash'];debt=bal['debt'];ret=bal['retained'];res=bal['reserve'];capital=bal['paid'];protected=bal['restricted'];profitbase=bal['ebit'];revenue=bal['revenue']
 original_revenue=revenue[:]
 legacy=[max(0,cash[i]-protected[i]-.025*revenue[i]) for i in range(6)]
 pv=0;allcash=[]
 for t in range(horizon):
  growth=[.065,.055,.045,.035,.03,.025,.025][t] if t<7 else steady
  for i in range(6):
   previous=profitbase[i];now=previous*(1+growth)
   previous_after=previous-max(0,previous)*tax[i];new_after=now-max(0,now)*tax[i]
   invest=max(0,new_after-previous_after)/roi
   revenue[i]*=1+growth;buffer=.025*revenue[i]+protected[i]
   p=now-debt[i]*.04-max(0,now-debt[i]*.04)*tax[i]
   free=p-invest;cash[i]+=free
   if cash[i]<buffer:
    loan=(buffer-cash[i])/.98
    assert debt[i]+loan<=limits[i]*revenue[i]/original_revenue[i]+1e-8
    cash[i]+=loan*.98;debt[i]+=loan;p-=loan*.02;free-=loan*.02
   ret[i],res[i]=legal_add(ret[i],res[i],capital[i],p)
   refund=min(debt[i],max(0,cash[i]-buffer));cash[i]-=refund;debt[i]-=refund
   if i:
    regular=min(max(0,free-refund),max(0,ret[i]),max(0,cash[i]-buffer))
    cash[i]-=regular;ret[i]-=regular
    legacy[i]=min(legacy[i],max(0,cash[i]-buffer))
    release=0
    if t+1>=[0,1,1,3,5,1][i]:
     release=min(max(0,ret[i]),max(0,cash[i]-buffer));ret[i]-=release;cash[i]-=release;legacy[i]-=min(legacy[i],release)
    parent_receipt=(regular+release)*ownership[i]*(.9 if i>=4 else 1)
    cash[0]+=parent_receipt
    ret[0],res[0]=legal_add(ret[0],res[0],capital[0],parent_receipt)
   profitbase[i]=now
  parent_buffer=.025*revenue[0]
  parent_repay=min(debt[0],max(0,cash[0]-parent_buffer));cash[0]-=parent_repay;debt[0]-=parent_repay
  actual=min(max(0,ret[0]),max(0,cash[0]-parent_buffer));cash[0]-=actual;ret[0]-=actual
  legacy[0]=min(legacy[0],max(0,cash[0]-parent_buffer))
  pv+=actual/(1+rate)**(t+1);allcash.append(actual)
 continuation=allcash[-1]*(1+steady)/(rate-steady)/(1+rate)**horizon
 assert max(legacy)<1e-8
 return (pv+continuation)/share,allcash


import pytest,runpy
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/002850/models'
@pytest.mark.parametrize('edge,k,g,r,m',[('low',.105,.02,.13,0),('high',.095,.025,.16,0),('minus_1pp',.10,.02,.14,-.01)])
def test_kedali_independent_raw_full_chain(edge,k,g,r,m):
 out=json.loads((ROOT/'2026-Q3-output.json').read_text());ds,states=reconstruct(m);tv,tail=independent_tail(states[-1],k,g,r)
 target=out['core'][edge] if not m else out['margin_sensitivity'];value=sum(a/(1+k)**(i+1) for i,a in enumerate(ds))+tv/(1+k)**5
 assert value==pytest.approx(target['value'],abs=1e-8);assert tv==pytest.approx(target['terminal']['per_share'],abs=1e-8)
 rows=out['scenarios']['base']['rows'] if not m else out['margin_sensitivity_path']['rows']
 for i in range(5):
  assert ds[i]==pytest.approx(rows[i]['dps'],abs=1e-9)
  for j,a in enumerate(['P','H','J','D','F','R']):
   assert states[i]['cash'][j]==pytest.approx(rows[i]['entities'][a]['cash'],abs=1e-9)
   assert states[i]['retained'][j]==pytest.approx(rows[i]['entities'][a]['retained'],abs=1e-9)
 label={'low':'core_low','high':'core_high','minus_1pp':'margin_minus_1pp'}[edge]
 ext=out['horizon_validation'][label]['extensions']
 for horizon in [400,500]:
  v,trace=independent_tail(states[-1],k,g,r,horizon);assert v==pytest.approx(ext[str(horizon)]['per_share'],abs=1e-8)
  recorded=ext['500']['rows'][:horizon];assert len(recorded)==horizon
  for a,b in zip(trace,recorded):assert a==pytest.approx(b['actual_holder_dividend'],rel=1e-12,abs=1e-9)
 assert ext['400']['rows']=={'rows_from_extension':'500','prefix_years':400}
def test_kedali_formal_function_handcases_and_lossless_rows():
 model=runpy.run_path(str(ROOT/'2026-Q3.py'));model['tests']()
 data=json.loads((ROOT/'2026-Q3-output.json').read_text());expanded=model['expand_output'](data)
 for case in expanded['horizon_validation'].values():assert case['extensions']['400']['rows']==case['extensions']['500']['rows'][:400]
