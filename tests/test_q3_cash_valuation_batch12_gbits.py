#!/usr/bin/env python3
"""Independent reconstruction; imports no production model functions.
All reconstruction inputs are literal re-entries; saved output is read only after reconstruction for comparison.
CNY billion. Explicit hand-derived legal ledger, scalar operations and terminal.
"""
import json,copy
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'research/companies/CN/603444/models'
N=.071756301
# Re-entered from source/budget bridge, NOT loaded from production model/output.
a={'interest_on_idle_cash':.01,'entities':{
'P':{'cash':.01946502401,'re':1.23207381943,'reserve':.0360205505,'capital':.072041101,'debt':0.,'inv':.2220215956},
'D':{'cash':2.62537073368,'re':1.17640884865,'reserve':.0260471665,'capital':.052094333,'debt':0.,'inv':1.08558347005},
'L':{'cash':1.0595825702,'re':1.7,'reserve':.015,'capital':.03,'debt':0.,'inv':0.},
'S':{'cash':2.5,'re':1.45,'reserve':.05,'capital':.1,'debt':0.,'inv':.33742553335}}}
q0={'cash_shift':0.,'revenue_components':{'legacy':[2.05,1.91,1.78,1.66,1.55],'domestic_2025':[2.35,1.98,1.70,1.49,1.34],'overseas':[1.65,1.60,1.48,1.40,1.34],'agency_and_new':[.65,.68,.72,1.20,1.77]},'gross':[.935,.933,.93,.925,.92],'selling':[.35,.345,.34,.34,.34],'rd':[.92,.94,.95,1.,1.04],'admin':[.35,.35,.35,.36,.37],'profit_split':{'P':.03,'D':.57,'S':.4},'cash_reserve_ratio':.18,'tail_growth':.01,'asset_realization':.8,'discount':.1,'residual_recovery':0.}
params={k:copy.deepcopy(q0) for k in ['base','core_low','core_high','sales_plus_3pp']}
params['core_low'].update(discount=.105,tail_growth=0.,asset_realization=.75)
params['core_high'].update(discount=.095,tail_growth=.02,asset_realization=.85)
params['sales_plus_3pp']['selling']=[.38,.375,.37,.37,.37]

def rebuild(q):
 st=copy.deepcopy(a['entities']);st['D']['cash']+=q['cash_shift'];st['S']['cash']-=q['cash_shift'];assets={k:v['inv'] for k,v in st.items()}; prev=7.1;old=.104787;trace=[]
 for n in range(1,12):
  j=min(n,5)-1
  scale=(1+q['tail_growth'])**max(0,min(n,10)-5)
  rev=sum(v[j] for v in q['revenue_components'].values())*scale
  margin=q['gross'][j]-q['selling'][j]-.005
  pretax=rev*margin-(q['rd'][j]+q['admin'][j])*scale
  net=pretax-max(pretax,0)*.17
  for k in ('P','D','L','S'):
   f=q['profit_split'].get(k,0); e=st[k]
   fi=max(0,e['cash'])*a['interest_on_idle_cash']
   cf=net*f+fi-(.015*f if n<=5 else 0)-(rev-prev)*.03*f
   e['cash']+=cf
   earned=net*f+fi
   if n in range(6,11):
    receipt=assets[k]*q['asset_realization']/5
    e['cash']+=receipt;earned+=receipt-assets[k]/5
   before=e['re']; e['re']+=earned
   reserve=min(max(0,.5*e['capital']-e['reserve']),.1*max(0,earned-max(0,-before)))
   e['re']-=reserve;e['reserve']+=reserve
  if n==1:st['D']['cash']-=old;st['P']['cash']+=old;old=0
  floor={'P':.04,'D':rev*q['cash_reserve_ratio']*.45,'S':rev*q['cash_reserve_ratio']*.55,'L':.03};paid={}
  for k,dest,w in [('S','L',1),('L','P',.6),('D','P',1)]:
   budget=(paid['S'] if k=='L' else net*q['profit_split'][k]*.9) if n<=5 else float('inf')
   pay=max(0,min(budget,st[k]['re'],st[k]['cash']-floor[k]));paid[k]=pay
   st[k]['cash']-=pay;st[k]['re']-=pay
   st[dest]['cash']+=pay*w
   # all tested receiving entities already have reserve at statutory cap
   assert st[dest]['reserve']>=.5*st[dest]['capital']-1e-12
   st[dest]['re']+=pay*w
  common=net*.84
  budget=max(6*N,.75*common) if n==1 else (.75*common if n<=5 else float('inf'))
  cash=max(0,min(budget,st['P']['re'],st['P']['cash']-.04))
  st['P']['cash']-=cash;st['P']['re']-=cash
  trace.append({'D':cash,'net':common,'st':copy.deepcopy(st),'floor':floor});prev=rev
 r=q['discount'];s=trace[10]
 perp=s['D']/r
 residual=sum((.6 if k in ('S','L') else 1)*max(0,e['cash']-s['floor'][k]-e['debt']) for k,e in s['st'].items())
 remaining=perp+residual*q['residual_recovery']/(1+r)**5
 t5=sum(trace[t-1]['D']/(1+r)**(t-5) for t in range(6,11))+remaining/(1+r)**5
 now=sum(trace[t-1]['D']/(1+r)**t for t in range(1,6))+t5/(1+r)**5
 return {'value':now/N,'TV5':t5/N,'D5':[x['D']/N for x in trace[:5]],'residual':residual,'P_cash5':trace[4]['st']['P']['cash'],'Y5_states':trace[4]['st']}

def test_gbits_literal_inputs_core_and_marketing_sensitivity():
    result={key:rebuild(q) for key,q in params.items()}
    
    # Only now read the official output; it supplies no reconstruction inputs.
    saved=json.loads((root/'2026-Q3-output.json').read_text())
    errors={}
    for key,r in result.items():
     s=saved['scenarios'][key]
     errors[key]={'PV_error_per_share':r['value']-s['value_per_share'],'TV5_error_per_share':r['TV5']-s['terminal_y5_per_share'],'D5_max_abs_error':max(abs(v-w) for v,w in zip(r['D5'],s['first5_dividends_ps']))}
     assert max(abs(x) for x in errors[key].values())<1e-8
    result['comparison_errors']=errors
    result['literal_inputs']=a
    result['literal_parameters']=params
    result['sales_3pp_impact']=result['sales_plus_3pp']['value']-result['base']['value']
    assert result['core_low']['Y5_states']==result['core_high']['Y5_states']==result['base']['Y5_states']
    result['same_base_Y5_pass']=True;result['no_production_import']=True

def test_gbits_production_gates_and_steady_cash():
 import runpy
 m=runpy.run_path(str(root/'2026-Q3.py'));m['tests']()
 o=json.loads((root/'2026-Q3-output.json').read_text())
 for v in o['scenarios'].values():
  if v['feasible']:
   assert v['steady_state_convergence']['cash_max_change']<1e-8
   assert abs(v['steady_state_convergence']['y11_dividend']-v['steady_state_convergence']['y21_dividend'])<1e-8
 assert not o['scenarios']['cash_delay']['feasible']
