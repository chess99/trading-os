"""Literal-input rebuild, independent cash/capacity algorithm. Does not import production.
Reads production only AFTER own calculations, to compare each annual numeric field.
"""
import json,gzip,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'research/companies/CN/000921/models'
# Explicit literal core endpoints and dominant sensitivities; not loaded from production outputs.
P={'core_low':(17,10,.105,1,.15,4.5),'core_high':(19,6,.095,1,.15,4.5),
'base':(18,8,.1,1,.15,4.5),'operating_profit_minus20':(18,8,.1,.8,.15,4.5),
'bosch_tax_expiry':(18,8,.1,1,.25,4.5),'no_historical_capacity':(18,8,.1,1,.15,0),'japan_reorg_year25':(18,8,.1,1,.15,4.5),'japan_friction20pct':(18,8,.1,1,.15,4.5)}

def calculate(par,reorg=15,jfee=.1):
 F,B,discount,scale,b_tax,Rhead=par
 holdings=[[{'born':0,'cash':B,'last':35}], [{'born':0,'cash':F-.492*B-1.5,'last':35}],[{'born':0,'cash':1.5,'last':35}]]
 head=[0.,Rhead];buffer=[.5,.5];legal=6.03298055478;capital=[0,0];records=[];paid=[];necessary=3.
 jcashes=[];jfund=0.;jlegal=-.81068195;jcap=0.;jreorganized=False;jlimit=(21.899211610+14.196235)*.04205-.3;jbasis=1.24038777677*.7094/.7488
 def total(k):return math.fsum(a['cash'] for a in holdings[k])
 def subtract(k,amt):
  balance=total(k)
  for a in holdings[k]:a['cash']*=1-amt/balance if balance else 0
 def mature(k,t,limit):
  due=[(a,a['cash']/max(1,a['last']-t+1)) for a in holdings[k] if t>a['born']+5]
  wish=sum(v for _,v in due);fraction=min(1,max(0,limit)/wish) if wish else 0
  for a,v in due:a['cash']-=v*fraction
  return wish*fraction,wish
 for year in range(1,241):
  opening=[total(k) for k in range(3)];interest=[opening[0]*.015/.85*(1-b_tax),opening[1]*.015,opening[2]*.015]
  if year<=5:
   p=[(2.3,2.4,2.5,2.6,2.7)[year-1],(.35,.45,.6,.7,.8)[year-1]]
   invest=[.45,(.5,.45,.4,.35,.35)[year-1]]
  else:
   p=[2.7*1.015**(year-5),.8*1.015**(year-5)]
   invest=[v*.015/.14 for v in p]
  j_unscaled=(-.1,-.05,0,.025,.05)[year-1] if year<=5 else .05*1.015**(year-5)
  jn_unscaled=(j_unscaled-max(j_unscaled,0)*.305)*.7094
  pretax=[p[0]/.85*scale,(p[1]-jn_unscaled)/.77*scale]
  tax=[pretax[0]*b_tax,pretax[1]*.23]
  j=j_unscaled*scale;jt=max(j,0)*.305;jc=(j-jt)*.7094
  necessary_interest=necessary*.015
  earnings=[pretax[0]-tax[0],pretax[1]-tax[1]+jc+necessary_interest]
  if year>=4 and necessary>0:
   freed=min(1,necessary);necessary-=freed;holdings[1].append({'born':year,'cash':freed,'last':year+35});opening[1]+=freed
  if year>5:invest=[earnings[0]*.015/.14,(earnings[1]-necessary_interest)*.015/.14]
  # Independent literal Japanese incremental-cash ledger, separate from R.
  jbegin=sum(z['cash'] for z in jcashes)
  jint=jbegin*.0139
  jinv=max(j-jt,0)*.015/.14 if year>5 else 0.
  jlegal+=j-jt+jint
  jfree=j-jt+jint-jinv
  support=max(0,-jbegin-jfree)
  if jfree>=0:jcashes.append({'birth':year,'cash':jfree,'end':year+15})
  elif jbegin:
   fraction=max(0,1+jfree/jbegin)
   for z in jcashes:z['cash']*=fraction
  jclear=jconvert=0.
  if not jreorganized and year>=reorg:
   needclear=max(0,-jlegal);needconvert=max(0,sum(z['cash'] for z in jcashes)-max(0,jlegal))
   if needclear+needconvert<=jlimit+1e-10:
    jclear=needclear;jconvert=needconvert;jlegal+=jclear;jcap+=jconvert;jlimit-=jclear+jconvert;jreorganized=True
  due=[(z,z['cash']/max(1,z['end']-year+1)) for z in jcashes if year>z['birth']+10]
  wanted=sum(v for _,v in due);ratio=min(1,(max(0,jlegal)+jcap)/wanted) if wanted else 0.
  payment=wanted*ratio
  for z,v in due:z['cash']-=v*ratio
  jordinary=min(payment,max(0,jlegal));jcapital=payment-jordinary;jlegal-=jordinary;jcap-=jcapital
  jreturned=min(jbasis,jcapital*.7094);jbasis-=jreturned
  jgain=max(0,jcapital*.7094-jreturned)*.25
  jordnet=jordinary*.7094*(1-jfee);jcapnet=(jcapital*.7094-jgain)*(1-jfee)
  jcost=payment*.7094-jordnet-jcapnet
  jend=sum(z['cash'] for z in jcashes)
  # Investments remain the SAME total economic requirement, allocated away from R once paid in J.
  invest[1]-=jinv*.7094
  earnings[1]=pretax[1]-tax[1]+necessary_interest-support*.7094
  subrows=[];child_pay=[]
  for k in range(2):
   capital[k]+=invest[k]
   income=earnings[k]+interest[k]
   retained_for_availability=min(buffer[k],max(0,income-max(0,-head[k]))*.1)
   buffer[k]-=retained_for_availability;head[k]+=income-retained_for_availability
   free=earnings[k]-invest[k]
   ordinary_target=earnings[k]*(.7 if k==0 else .5) if year<=5 else max(0,free)*.9
   ordinary=max(0,min(ordinary_target+interest[k],head[k],opening[k]+free+interest[k]))
   delta=free+interest[k]-ordinary
   if delta>0:holdings[k].append({'born':year,'cash':delta,'last':year+35})
   elif delta<0:subtract(k,-delta)
   head[k]-=ordinary
   principal,due=mature(k,year,head[k]);head[k]-=principal
   distribution=ordinary+principal;child_pay.append(distribution)
   subrows.append(dict(np=earnings[k],interest=interest[k],investment=invest[k],cumulative_investment=capital[k],dividend=distribution,capacity_budget=head[k],remaining_buffer=buffer[k],cash=total(k),cohort_add=max(delta,0),principal_release=principal,principal_due=due))
  gross=.492*child_pay[0]+child_pay[1];fee=gross*.015;received=gross-fee+jordnet
  target=(.65,.75,.85,.95,1.05)[year-1]*1.384861171 if year<=5 else received+interest[2]+jcapnet
  pr,due=mature(2,year,max(0,legal+received+interest[2]+jcapnet-jreturned-target))
  if year>5:target+=pr
  div=max(0,min(target,opening[2]+received+interest[2]+jcapnet,legal+received+interest[2]+jcapnet-jreturned))
  legal+=received+interest[2]+jcapnet-jreturned-div
  closing=opening[2]+received+interest[2]+jcapnet-div
  difference=closing-total(2)
  if difference>0:holdings[2].append({'born':year,'cash':difference,'last':year+35})
  elif difference<0:subtract(2,-difference)
  subrows[0].update(pretax=pretax[0],tax=tax[0])
  subrows[1].update(pretax_equivalent=pretax[1],tax_budget=tax[1])
  record={'t':year,'B':subrows[0],'R':subrows[1],'J':dict(ownership=.7094,pretax=j,tax_rate=.305,tax=jt,common_profit=jc,dividend_budget=jordinary),'P':dict(new_dividend=received,transfer_cost=fee,interest=interest[2],profit=received+interest[2]+jcapnet-jreturned,capital_return=jreturned,capital_realization_pnl=jcapnet-jreturned,japan_ordinary_dividend=jordnet,japan_capital_cash=jcapnet,cash=closing,retained=legal,statutory_reserve=.694073685,reserve_add=0,dividend=div,cohort_release=pr),'common_cash':.492*total(0)+total(1)+closing+necessary+.7094*jend,'dividend_per_share':div/1.384861171}
  record['J_route']=dict(opening_cash=jbegin,interest=jint,investment=jinv,support=support,common_support=support*.7094,minority_support=support*.2906,cash=jend,profit_budget=jlegal,capital_headroom=jcap,capital_clearing=jclear,capital_conversion=jconvert,capital_reduction_remaining=jlimit,ordinary_distribution=jordinary,capital_distribution=jcapital,common_dividend_received=jordnet,common_capital_principal=jreturned,common_capital_pnl=jcapnet-jreturned,common_capital_cash=jcapnet,common_realization_leakage=jcost,remaining_basis_common=jbasis)
  records.append(record);paid.append(div/1.384861171)
 return {'value':sum(d/(1+discount)**(i+1) for i,d in enumerate(paid)), 'tv5':sum(paid[i]/(1+discount)**(i-4) for i in range(5,240)), 'rows':records}

import runpy,shutil,sys,subprocess
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(R/'2026-Q3.py'))
@lru_cache(None)
def output():return model()['expand_output'](json.loads((R/'2026-Q3-output.json').read_text()))
def test_hisense_japan_literal_eight_complete_paths():
 prod=output()['cases']
 for name,par in P.items():
  a=calculate(par,reorg=25 if name=='japan_reorg_year25' else 15,jfee=.2 if name=='japan_friction20pct' else .1);b=prod[name]
  for f in ['value','tv5']:assert abs(a[f]-b[f])<1e-7
  for x,y in zip(a['rows'],b['rows']):
   for k in ['B','R','J','P']:
    for f,v in x[k].items():assert abs(v-y[k][f])<1e-7
   for f,v in x['J_route'].items():assert abs(v-y['J']['route'][f])<1e-7
   for f in ['common_cash','dividend_per_share']:assert abs(x[f]-y[f])<1e-7

def test_hisense_real_registered_principal_and_disposal_loss():
 m=model();f=m['statute'];assert f(10,0,20,5)==(9,6,1,0);assert f(10,-6,20,0)==(3.6,.4,.4,0);assert f(10,0,20,10)==(10,10,0,0)
 z=m['parent_step'](0,0,0,0,0,old_receivable=10,loan_repayment=10,capital_principal=10,registered=20)
 assert z['income']==z['distribution']==0 and z['cash']==30
 assert abs(m['exit_asset'](10,10,1,.25,.492,2,.1,100)['parent_profit']+.492)<1e-12
 j=m['japan_state']();a=m['japan_step'](j,-1,0,1);assert a['support']==1 and a['cash']==0 and a['common_support']==.7094

def test_hisense_japan_separate_cash_and_finite_future_batches():
 o=output()
 for c in o['cases'].values():
  for r in c['rows']:
   j=r['J']['route'];p=r['P'];assert abs(r['cash_residual'])<1e-8;assert abs(j['cash_residual'])<1e-8
   assert abs(p['profit']-p['new_dividend']-p['interest']-p['capital_realization_pnl'])<1e-9
   assert abs(j['support']-j['common_support']-j['minority_support'])<1e-10
   assert r['shares']==1.384861171 and j['capital_reduction_remaining']>=-1e-8
   if r['t']<=10:assert p['japan_capital_cash']+p['japan_ordinary_dividend']==0
   expected=r['R']['pretax_equivalent']-r['R']['tax_budget']+r['necessary_gross_interest']-r['necessary_finance_tax']-j['common_support']
   assert abs(r['R']['np']-expected)<1e-9
  for b in c['japan_cohorts']:
   if b['origin']<=160:assert abs(b['balance'])<1e-8
 m=model()
 for year in [20,80,160]:
  z=m['run'](shock_year=year,shock_amount=1.)
  for b in z['cohorts'][1]:
   if b['origin']==year:assert b['balance']<1e-8

def test_hisense_single_file_fresh_pack(tmp_path):
 m=model();o=output();assert m['expand_output'](m['pack_output'](o))==o
 shutil.copy2(R/'2026-Q3.py',tmp_path/'2026-Q3.py');subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py')],check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(R/'2026-Q3-output.json').read_bytes()
