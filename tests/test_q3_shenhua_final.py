"""Independent literal-input scalar reconstruction. No import/call of production model.
Reads output only AFTER constructing all annual values, for comparisons.
"""
import json,math
from pathlib import Path
P=Path(__file__).parent

def independently(r=.08,cap=0,coal=0,life=40,mode='base',up=.75,delay=3,interest=0,sale_year=10,own=.72,salvage=20,exit=8,leak=.5,friction=.004,loss_budget=18.5,oldlaw=False,voluntary=0,legacytax=False):
    cash=[45.426,45.677];debt=[52.8,109.752];retained=165.353;capacity=0.;paid=0.;asset=65.;remaining=35.283;rows=[]
    ebits=[1.252*2/.85,1.098*2/.75,3.714*2/.75,.172*2/.75,.979*2/.75,.815*2/.85,1.444*2/.85]
    taxrates=[.15,.25,.25,.25,.25,.15,.15]
    for year in range(1,life+1):
        size=1 if year<=life-15 else (life-year)/15
        level=size*(1+.005*min(year-1,5))
        if mode=='cycle' and year<=3:level*=.8
        if mode=='structural':
            if year>=2:level*=.72
            level*=max(.3,1-.025*max(year-5,0))
        if mode=='upside' and year>=3:level*=1.1
        price=coal*.38*.91*size
        earnings=[28*level+.3*price,64*level+.7*price]
        investment=((57 if year<=3 else 52 if year<=5 else 46)+cap)*size
        if mode=='cycle' and year<=3:investment-=4*size
        if mode=='structural':investment=max(34*size,investment*.9)
        if mode=='upside':investment+=(4 if year<=5 else 1)*size
        old=min(remaining,7.0566) if year<=5 else 0.;remaining-=old
        work=size if year<=5 else 0.
        pretax=[earnings[0]-debt[0]*(.025+interest)+cash[0]*.015,earnings[1]-debt[1]*(.03+interest)+cash[1]*.015]
        tax0=max(pretax[0],0)*.25;tax1=leak*size
        for eb,tr in zip(ebits,taxrates):
            rate=tr if year<=4 else tr*.2+.25*.8 if year==5 else .25
            tax1+=max(0,pretax[1]*eb/64)*rate
        tax1+=max(0,pretax[1]*(1-sum(ebits)/64))*.25
        if legacytax:
            tr=.22 if year<=4 else .245 if year==5 else .25
            tax0=pretax[0]*tr;tax1=pretax[1]*tr
        ni=[pretax[0]-tax0,pretax[1]-tax1]
        flow=[ni[0]+5.6*size-investment*.24-old*.15-work*.3,ni[1]+29.4*size-investment*.76-old*.85-work*.7]
        income=1.8 if asset else 0.;economic=3 if asset else 0.;sold=asset if year==sale_year else 0.;loss=-loss_budget if sold else 0.
        if sold:asset=0
        cash[0]+=flow[0]+income+sold;cash[1]+=flow[1]
        floors=[10*size+exit*min(1,max(0,(year-(life-10))/5)),15*size]
        for i in [0,1]:
            borrow=max(0,floors[i]-cash[i]);debt[i]+=borrow;cash[i]+=borrow
        capacity+=ni[1]-(max(0,ni[1])*.1 if oldlaw else 0)
        scheduled=[debt[i]/max(1,life-year) if year>life-15 else 0 for i in [0,1]]
        distribution=min(max(0,ni[1])*up,max(0,capacity-paid),max(0,cash[1]-floors[1]-scheduled[1]))
        paid+=distribution;cash[1]-=distribution;cash[0]+=distribution*own*(1-friction)
        lp=ni[0]+income+distribution*own*(1-friction)+loss
        retained+=lp-max(0,lp)*(.1 if oldlaw else voluntary)
        common=ni[0]+ni[1]*own+economic+loss
        dividend=min(max(0,common)*.7,max(0,retained),max(0,cash[0]-floors[0]-scheduled[0]))
        retained-=dividend;cash[0]-=dividend
        for i in [0,1]:
            repay=min(debt[i],max(0,cash[i]-floors[i]));debt[i]-=repay;cash[i]-=repay
        sweep=0
        if year%delay==0 or year==life:
            if debt[1]<1e-9:sweep=min(max(0,cash[1]-floors[1]),max(0,capacity-paid))
            paid+=sweep;cash[1]-=sweep;cash[0]+=sweep*own*(1-friction);retained+=sweep*own*(1-friction)*(1-(.1 if oldlaw else voluntary))
        if debt[0]<1e-9:
            special=min(max(0,cash[0]-floors[0]),max(0,retained));cash[0]-=special;retained-=special;dividend+=special
        if year==life:
            dividend+=cash[0]-debt[0]+own*(cash[1]-debt[1])+asset+salvage*.5*(.24+.76*own)-exit
            cash=[0,0];debt=[0,0]
        rows.append(dict(year=year,dividend=dividend,parent_cash=cash[0],sub_cash=cash[1],parent_debt=debt[0],sub_debt=debt[1],parent_ni=ni[0],sub_ni=ni[1],parent_legal_re=retained,upstream_received=(distribution+sweep)*own*(1-friction),capex=investment,parent_tax=tax0,sub_tax=tax1))
    total=sum(z['dividend']/21.689434304/(1+r)**z['year'] for z in rows)
    terminal=sum(z['dividend']/21.689434304/(1+r)**(z['year']-5) for z in rows[5:])
    return dict(value=total,year5_terminal=terminal,rows=rows)

specs={'base':{},'sale_profit_capacity_no_loss':dict(loss_budget=0),'sale_profit_capacity_full_book_loss':dict(loss_budget=83.5),'same_economy_old_law':dict(oldlaw=True),'same_economy_old_tax':dict(legacytax=True),'voluntary10':dict(voluntary=.1),'core_low':dict(r=.085,cap=2),'core_high':dict(r=.075,cap=-2),'holder_low':dict(r=.085),'holder_high':dict(r=.075),'cycle':dict(mode='cycle'),'structural':dict(mode='structural',life=30),'upside':dict(mode='upside'),'coal_minus20':dict(coal=-20),'capex_plus5':dict(cap=5),'life30':dict(life=30),'rate9':dict(r=.09),'upstream50_delay5':dict(up=.5,delay=5),'interest_plus1pct':dict(interest=.01),'financial_recovery40':dict(sale_year=40),'sub_ownership68':dict(own=.68),'sub_ownership76':dict(own=.76),'no_salvage':dict(salvage=0),'exit_double':dict(exit=16),'crossborder_friction2pct':dict(friction=.02),'tax_leakage2':dict(leak=2)}

import runpy,subprocess,sys,shutil,copy
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/601088/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():return json.loads((D/'2026-Q3-output.json').read_text())
def test_shenhua_26_literal_annual_paths():
 rebuilt={name:independently(**kwargs) for name,kwargs in specs.items()};o=output()
 for name,a in rebuilt.items():
  b=o['cases'][name]
  for ar,br in zip(a['rows'],b['rows']):
   for k,v in ar.items():assert abs(v-br[k])<1e-8
  assert abs(a['value']-b['value'])<1e-10 and abs(a['year5_terminal']-b['year5_terminal'])<1e-10

def test_shenhua_actual_hand_functions():
 m=model();m['fixtures']()
 assert m['tax_due'](-10,.25)==0
 assert m['parent_payment'](12,10,2,100)==(2,0,10)
 try:m['run'](exitcost=1000)
 except ValueError:pass
 else:raise AssertionError('unfunded exit costs should fail')

def test_shenhua_every_future_cash_batch_and_holders():
 m=model();base=m['run']()
 for year in range(20,40):
  for kind in ['parent_cash','sub_cash']:
   q=m['run'](shock={'year':year,kind:.1,'new_profit':0})
   entitlement=.1 if kind=='parent_cash' else .1*.72*(1-.004)
   paid=0;when=None
   for a,b in zip(q['rows'],base['rows']):
    paid+=a['dividend']-b['dividend']
    if paid+1e-8>=entitlement and when is None:when=a['year']
   assert when is not None and when<=min(year+3,40)
 for case in output()['cases'].values():
  assert case['rows'][-1]['shares_outstanding']==0
  assert case['rows'][-1]['parent_debt']==case['rows'][-1]['sub_debt']==0
  assert all(x['parent_cash']>=0 and x['sub_cash']>=0 for x in case['rows'])

def test_shenhua_fresh_single_file_output(tmp_path):
 f=tmp_path/'2026-Q3.py';shutil.copy2(D/'2026-Q3.py',f)
 subprocess.run([sys.executable,str(f)],check=True,stdout=subprocess.DEVNULL)
 assert f.with_name('2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
