#!/usr/bin/env python3
"""Independent literal reconstruction; no production import, source parsing, or output-derived inputs.
Different implementation: scalar parent ledger, due-year buckets, closed-form terminal.
Only reads production output after all independent paths have been computed.
"""
import json,copy
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"research/companies/CN/603444/models"
L={'shares':.071756301,'cash':4.78058529981,'investments':1.51006038566,'Pcash':.01946502401,'Pre':1.23207381943,'Preg':.072041101,'Pres':.0360205505,'receivable':.104787,'rev0':7.1,'owner':.84,'pown':.03,'yield':.01,'tax':.17}
B={'components':[[2.05,1.91,1.78,1.66,1.55],[2.35,1.98,1.70,1.49,1.34],[1.65,1.60,1.48,1.40,1.34],[.65,.68,.72,1.2,1.77]],'gm':[.935,.933,.93,.925,.92],'sell':[.35,.345,.34,.34,.34],'rd':[.92,.94,.95,1.,1.04],'admin':[.35,.35,.35,.36,.37],'r':.10,'growth':.01,'asset':.8,'buffer':.18,'payout':.75,'up':.9,'wcstress':0.,'lag':3,'haircut':.05,'routinefee':.01,'routine':.9,'cashshift':0.,'loss':0.,'injectyear':0,'inject':0.,'shockyear':0,'shock':0.}
def alt(**kw):
 d=copy.deepcopy(B);d.update(kw);return d
C={'base':alt(),'core_low':alt(r=.105,growth=0.,asset=.75),'core_high':alt(r=.095,growth=.02,asset=.85),
 'sales_plus_3pp':alt(sell=[.38,.375,.37,.37,.37]),'slower_realization':alt(lag=5,haircut=.15,routinefee=.03),
 'faster_realization':alt(lag=2,haircut=.02),'upstream_60pct':alt(up=.6),'higher_operating_buffer':alt(buffer=.23),
 'lower_cash_attribution':alt(cashshift=-.28),'same_year_parent_loss':alt(loss=1.),
 'new_projects_zero':alt(components=[[2.05,1.91,1.78,1.66,1.55],[2.35,1.98,1.70,1.49,1.34],[1.65,1.6,1.48,1.4,1.34],[.65,.68,.72,.72,.72]],growth=0.),
 'cyclical':alt(components=[[1.7425,1.719,1.78,1.66,1.55],[1.9975,1.782,1.7,1.49,1.34],[1.4025,1.44,1.48,1.4,1.34],[.5525,.612,.72,1.2,1.77]],wcstress=.25,up=.6),
 'structural':alt(components=[[1.9,1.6,1.35,1.15,1.],[1.9,1.4,1.,.7,.5],[1.3,1.,.8,.7,.6],[.5,.4,.4,.4,.4]],gm=[.92]*5,sell=[.38,.37,.35,.33,.32],rd=[.92,.88,.75,.6,.5],admin=[.35,.32,.28,.24,.22],payout=.5,growth=0.,r=.115,asset=.6,lag=5,haircut=.15),
 'optimistic':alt(components=[[2.1,2.,1.9,1.8,1.7],[2.5,2.3,2.1,2.,1.9],[1.9,2.1,2.2,2.3,2.4],[.7,.8,1.1,1.8,2.6]],rd=[.96,1.02,1.12,1.25,1.4],admin=[.36,.38,.4,.42,.45],sell=[.35,.34,.34,.34,.34],growth=.02,r=.095),
 'late_surplus_40':alt(injectyear=40,inject=.5),'late_surplus_60':alt(injectyear=60,inject=.5),'tail_loss':alt(shockyear=35,shock=1.5)}
def rebuild(a,N=80):
 cash=L['cash']+a['cashshift'];pc=L['Pcash'];re=L['Pre'];reserve=L['Pres'];due={};prior=L['rev0'];out=[]
 for year in range(1,N+1):
  col=year-1 if year<6 else 4
  factor=(1+a['growth'])**(max(0,min(10,year)-5))
  revenue=sum(comp[col] for comp in a['components'])*factor
  pretax=revenue*(a['gm'][col]-a['sell'][col]-.005)-(a['rd'][col]+a['admin'][col])*factor
  profit=pretax-max(pretax,0)*.17-(a['shock'] if year==a['shockyear'] else 0.)
  loss=a['loss'] if year==1 else 0.
  ownprofit=.84*profit+.01*cash-loss
  extra=(.015*.84 if year<6 else 0.)
  working=.84*(.03*(revenue-prior)+(a['wcstress'] if year==1 else -a['wcstress'] if year==3 else 0.))
  flow=ownprofit-extra-working; cash+=flow
  saleprofit=0.;sale=0.
  if 6<=year<=10:
   book=1.51006038566/5
   gain=book*(a['asset']-1);tax=max(0,gain)*.25
   sale=book*a['asset']-tax;saleprofit=gain-tax;cash+=sale
  if year==a['injectyear']:cash+=a['inject']
  floor=.058+.78*a['buffer']*revenue
  assert cash>=floor-1e-10,'Independent selected feasible paths require no owner borrowing'
  dividend=0.;economic=0.;fee=0.;up=0.;parentprofit=None
  if year<6:
   pc+=.03*profit-loss-(extra+working)*(.03/.84)
   if year==1:pc+=.104787
   up=min(max(0,profit*.81)*a['up'],max(0,cash-pc-(floor-.04)))
   pc+=up;parentprofit=.03*profit-loss+up
   eligible=max(0,parentprofit-max(0,-re))
   moved=min(max(0,.5*.072041101-reserve),.1*eligible)
   re+=parentprofit-moved;reserve+=moved
   want=a['payout']*max(0,profit*.84-loss)
   if year==1:want=max(want,6*.071756301)
   dividend=min(want,max(0,re),max(0,pc-.04));pc-=dividend;re-=dividend;cash-=dividend
  else:
   ordinary=min(max(0,cash-floor),a['routine']*max(0,min(flow,ownprofit+saleprofit)))
   cash-=ordinary;economic=ordinary*(1-a['routinefee']);fee=ordinary*a['routinefee']
   short=max(0,sum(due.values())-max(0,cash-floor))
   for key in sorted(due,reverse=True):
    take=min(short,due[key]);due[key]-=take;short-=take
   gross=due.pop(year,0.)
   assert cash-floor>=gross-1e-9
   cash-=gross;economic+=gross*(1-a['haircut']);fee+=gross*a['haircut']
   available=max(0,cash-floor-sum(due.values()))
   if available>1e-12:due[year+a['lag']]=due.get(year+a['lag'],0.)+available
  out.append({'year':year,'revenue':revenue,'group_net':profit,'owner_cash':cash,'required_operating_cash':floor,'holder_dividend':dividend,'economic_equity_realization_not_dividend':economic,'realization_cost':fee,'parent_new_dividend_budget':up,'parent_profit_including_current_loss':parentprofit,'parent_cash':pc if year<6 else None,'parent_re':re if year<6 else None,'valuation_cash':dividend+economic,'pending_total':sum(due.values())})
  prior=revenue
 annual=(.84*profit+.01*floor)/(1-.01*a['lag']*(1-a['routine']))
 terminal=annual*(a['routine']*(1-a['routinefee'])+(1-a['routine'])*(1-a['haircut']))/a['r']
 current=sum(x['valuation_cash']/(1+a['r'])**x['year'] for x in out)+terminal/(1+a['r'])**N
 fifth=sum(x['valuation_cash']/(1+a['r'])**(x['year']-5) for x in out[5:])+terminal/(1+a['r'])**(N-5)
 return {'value_per_share':current/.071756301,'terminal_y5_per_share':fifth/.071756301,'first5_dividends_ps':[x['holder_dividend']/.071756301 for x in out[:5]],'years':out}

def test_gbits_independent_full_paths():
 independent={name:rebuild(param) for name,param in C.items()}
 # Production output is opened only here, after reconstruction is complete.
 actual=json.loads((HERE/'2026-Q3-output.json').read_text())['scenarios'];errors={}
 for name,x in independent.items():
  y=actual[name];diff=[]
  for field in ['value_per_share','terminal_y5_per_share']:diff.append(abs(x[field]-y[field]))
  for a,b in zip(x['years'],y['years']):
   for field in ['revenue','group_net','owner_cash','required_operating_cash','holder_dividend','economic_equity_realization_not_dividend','realization_cost','parent_new_dividend_budget','valuation_cash']:
    diff.append(abs(a[field]-b[field]))
   if a['year']<=5:
    diff.extend([abs(a['parent_cash']-b['parent']['cash']),abs(a['parent_re']-b['parent']['re'])])
   diff.append(abs(a['pending_total']-sum(c['gross'] for c in b['pending_cohorts'])))
  errors[name]=max(diff);assert errors[name]<1e-8,(name,errors[name])
 long={name:{'N80':independent[name]['value_per_share'],'N260':rebuild(C[name],260)['value_per_share']} for name in ['base','core_low','core_high','structural','slower_realization']}
 for v in long.values():assert abs(v['N80']-v['N260'])<1e-8

import runpy,subprocess,sys
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(HERE/'2026-Q3.py'))
@lru_cache(None)
def output():return json.loads((HERE/'2026-Q3-output.json').read_text())
def test_gbits_actual_law_loss_fee_creditor():
 m=model();m['tests']()
 for name,p in m['scenarios']().items():
  assert m['run'](p)==output()['scenarios'][name]
 for n in ['zero_revenue_failure','disposal_fee_failure','cash_delay']:assert not output()['scenarios'][n]['feasible'] and output()['scenarios'][n]['value_per_share'] is None
 q=m['dispose'](10,1,2,0);assert not q['feasible'] and q['book_remaining']==10
 q=m['run'](m['params'](debt_open=.5));assert q['years'][0]['repayment']==.5 and q['years'][0]['interest']==.025 and q['years'][0]['debt']==0

def test_gbits_total_and_all_future_cash():
 m=model()
 for name in ['base','core_low','core_high','structural','slower_realization']:
  p=m['scenarios']()[name];a=m['run'](p,260);assert a['feasible']
  for row in a['years'][5:]:
   extra=max(0,row['owner_cash']-row['required_operating_cash']);pending=sum(c['gross'] for c in row['pending_cohorts'])
   assert abs(extra-pending)<1e-8
   assert all(0<c['due']-row['year']<=p['realization_lag'] for c in row['pending_cohorts'])
  for year in [17,40,100,200]:
   q=m['run'](dict(p,tail_cash_injection_year=year,tail_cash_injection=.5),260)
   # Existing financial-asset conversion; adds no operating income or fabricated legal earnings.
   assert q['years'][year-1]['owner_operating_net']==a['years'][year-1]['owner_operating_net']
   after=year+p['realization_lag']+15
   assert abs(q['years'][after]['owner_cash']-a['years'][after]['owner_cash'])<1e-5
   assert q['value_per_share']>=a['value_per_share']

def test_gbits_standalone_regeneration(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((HERE/'2026-Q3.py').read_bytes())
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(HERE/'2026-Q3-output.json').read_bytes()
