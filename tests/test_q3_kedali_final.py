"""Literal scalar-array rebuild; does NOT import production code/parameters/intermediates.
Reads its packed output only AFTER independently rebuilding for equality assertions.
"""
import json,gzip,base64,math
from pathlib import Path
shares=.286448468;own=[1.,1.,1.,.9902,1.,.444]
cap0=[1.7,6.5,5.5,11.,1.5,.3];rev0=[1.3,5.5,4.5,8.7,.75,.05]
adds=[[.05]*5,[.8,.8,.7,.6,.5],[.8,.8,.7,.6,.5],[1.5,1.4,1.3,1.2,1],[.25,.3,.3,.25,.2],[.1,.1,.1,0,0]]
utils=[[.8,.82,.84,.85,.86],[.87,.89,.9,.9,.9],[.85,.87,.89,.9,.9],[.82,.85,.87,.89,.9],[.5,.55,.62,.68,.72],[.2,.3,.4,.5,.55]]
margin=[.24,.215,.18,.18,.25,.30];fix=[.04,.13,.16,.25,.16,.05];da=[.025,.035,.04,.04,.055,.06];nw=[.12,.20,.20,.22,.25,.28];limit=[.8,.3,.5,1.,.5,.1]
def add_profit(ret,res,cap,p):
 z=min(.1*max(0,p+min(0,ret)),max(0,.5*cap-res));return ret+p-z,res+z

def build(name):
 # utility, price, contribution, expansion, NWC, domestic tax, delay, rate, payout
 sets={'base':(0,1,0,1,0,.15,0,.04,.38),'cyclical':(-.14,.96,-.015,.72,.04,.15,1,.05,.28),'structural':(-.16,.91,-.035,.5,.06,.18,2,.055,.20),'optimistic':(.04,1.01,.01,1.2,-.02,.15,0,.04,.42)}
 source='base' if name not in sets and name!='structural_supported' else ('structural' if name=='structural_supported' else name)
 shock,price,cm,exp,nwc,tx,delay,rate,pay=sets[source]
 if name=='structural_supported':exp=.3;pay=.1
 if name=='delay3':delay=3
 if name=='delay5':delay=5
 if name=='margin_minus_1pp':cm=-.01
 cash=[.511524501+60126*105.41/1e9,.30,.20,1.1669849113469388,.15,.1591271816530612]
 reserve=[.137471634,0,0,0,0,0];ret=[1.783852672,0,0,0,-.20,-.03];reg=[.286448468,.5,1.,0,0,0]
 
 if name=='HJ_open_loss_500m_each':ret[1]=ret[2]=-.5
 if name=='parent_statutory_zero':reserve[0]=0.
 debt=[.016,0,0,.014444315,.038,0];restricted=[0,0,0,1.1,0,0];capacity=cap0[:];prior=rev0[:];queue=[];states=[];divs=[]
 for t in range(5):
  of=[.25,.25,.20,.10,.05][t]+(.12 if name=='structural_supported' and t>=3 else 0)
  rb=[.08,.08,.06,.03,.02][t];cash[0]-=of+rb;cash[4]+=of;cash[5]+=rb/.444
  if name=='settlement' and t==0:cash[0]-=.5;cash[1]+=.3;cash[2]+=.2
  ebit=[];sales=[];profits=[];taxrates=[];declared=0
  for i in range(6):
   ad=adds[i][t]*(1 if t==0 else exp);capacity[i]+=ad
   fade=1 if source=='structural' else max(0,3-t)/3
   u=max(.1,min(.95,utils[i][t]+shock*fade));r=capacity[i]*u*(price if source=='structural' else 1+(price-1)*fade);sales.append(r)
   adjustment=0 if source=='cyclical' and t>=3 else cm
   op=r*(margin[i]+adjustment)-fix[i]*1.025**t-capacity[i]*da[i];ebit.append(op)
   tr=[.25,tx,tx,.20,.23,.23][i]
   if name=='nonrenewal' and ((i in (1,2) and t>=1) or i==3):tr=.25
   taxrates.append(tr)
   interest=debt[i]*rate;p=op-interest-max(0,op-interest)*tr
   growth=ad*(.85 if i>=4 else .6);restricted[i]-=min(restricted[i],growth if i==3 else 0)
   free=p-(r-prior[i])*(nw[i]+nwc)-growth;cash[i]+=free;prior[i]=r
   floor=r*.025+restricted[i]+sum(z[2] for z in queue if z[0]==i)
   if cash[i]<floor:
    loan=(floor-cash[i])/(1-rate*.5)
    if debt[i]+loan>limit[i]+1e-8:return {'feasible':False,'year':t+1,'entity':i,'states':states,'D':divs}
    debt[i]+=loan;cash[i]+=loan*(1-rate*.5);p-=loan*rate*.5
   if i<3:ret[i],reserve[i]=add_profit(ret[i],reserve[i],reg[i],p)
   else:ret[i]+=p
   profits.append(p)
   if i in (1,2):
    d=min(max(0,ret[i]),max(0,p)*.65,max(0,cash[i]-floor));ret[i]-=d;declared+=d;queue.append((i,t+1+delay,d))
  ret[0],reserve[0]=add_profit(ret[0],reserve[0],reg[0],declared)
  for z in queue[:]:
   if z[1]<=t+1:cash[z[0]]-=z[2];cash[0]+=z[2];queue.remove(z)
  if t==0:cash[0]-=.17521234211
  if cash[0]<0:
   loan=-cash[0]+.04
   if debt[0]+loan>.8:return {'feasible':False,'year':t+1,'entity':0,'states':states,'D':divs}
   debt[0]+=loan;cash[0]+=loan
  d=min(max(0,sum(x*y for x,y in zip(profits,own)))*pay,max(0,ret[0]),max(0,cash[0]-.025*sales[0]));cash[0]-=d;ret[0]-=d;divs.append(d/shares)
  for i in range(6):
   repay=min(debt[i],.5*max(0,cash[i]-restricted[i]-.025*sales[i]-sum(z[2] for z in queue if z[0]==i)));cash[i]-=repay;debt[i]-=repay
  states.append({'cash':cash[:],'debt':debt[:],'ret':ret[:],'reserve':reserve[:],'restricted':restricted[:],'revenue':sales[:],'ebit':ebit[:],'capacity':capacity[:],'pending':queue[:],'rate':rate,'tax':taxrates[:]})
 return {'feasible':True,'states':states,'D':divs,'source':source}

def tail(state,k,g,roi,source,horizon,extra_lag=0,extra_fee=0,recovery=.35):
 cash=state['cash'][:];debt=state['debt'][:];rev=state['revenue'][:];ebit=state['ebit'][:];restricted=state['restricted'][:];r=state['rate'];tax=state['tax'];pending=[];closed=set();records=[];pv=0
 for i,due,money in state['pending']:cash[i]-=money;pending.append((i,max(1,due-5),money))
 for year in range(1,horizon+1):
  change=([.01]*7 if source=='structural' else [.065,.055,.045,.035,.03,.025,.025])[year-1] if year<=7 else g
  states=[]
  for i in range(6):
   if i in closed:states.append(None);continue
   before=ebit[i];ebit[i]*=1+change;rev[i]*=1+change
   invest=max(0,(ebit[i]-max(0,ebit[i])*tax[i])-(before-max(0,before)*tax[i]))/roi
   p=ebit[i]-debt[i]*r-max(0,ebit[i]-debt[i]*r)*tax[i]
   cash[i]+=p-invest;floor=rev[i]*.025+restricted[i];exitnow=ebit[i]<0 and year==3
   if exitnow:
    asset=state['capacity'][i]*(.85 if i>=4 else .6)
    proceeds=asset*recovery+state['revenue'][i]*nw[i]*.5
    net=proceeds*.9-max(0,proceeds*.9-asset)*.25;cash[i]+=net;floor=0
   if cash[i]<floor:
    debt_needed=(floor-cash[i])/(1-r*.5)
    if debt[i]+debt_needed>limit[i]*rev[i]/state['revenue'][i]+1e-9:return {'feasible':False,'year':year,'entity':i}
    debt[i]+=debt_needed;cash[i]+=debt_needed*(1-r*.5)
   repay=min(debt[i],max(0,cash[i]-floor));debt[i]-=repay;cash[i]-=repay
   if exitnow and debt[i]>1e-9:return {'feasible':False,'year':year,'entity':i}
   free=max(0,cash[i]-floor)
   if free:pending.append((i,year+[1,1,1,3,5,5][i]-1+extra_lag,free));cash[i]-=free
   if exitnow:closed.add(i);ebit[i]=0;rev[i]=0;restricted[i]=0
   states.append({'cash':cash[i],'debt':debt[i],'profit':p,'reinvestment':invest,'surplus':free})
  paid=0
  for z in pending[:]:
   if z[1]<=year:paid+=z[2]*(1-[0,.02,.02,.05,.15,.15][z[0]]-extra_fee)*own[z[0]];pending.remove(z)
  pv+=paid/(1+k)**year;records.append({'year':year,'cash_to_common_budget':paid,'states':states})
 tv=(pv+records[-1]['cash_to_common_budget']*(1+g)/(k-g)/(1+k)**horizon)/shares
 return {'feasible':True,'tv5':tv,'rows':records}

def test_kedali_independent_allpaths():
 rebuilt={n:build(n) for n in ['base','cyclical','structural','optimistic','delay3','delay5','structural_supported','nonrenewal','margin_minus_1pp','settlement','HJ_open_loss_500m_each','parent_statutory_zero']}
 calculated={}
 for n,s in rebuilt.items():
  if not s['feasible']:continue
  k=.10;g=.01 if n.startswith('structural') else .02;roi=.10 if n.startswith('structural') else .14
  q=tail(s['states'][-1],k,g,roi,s['source'],300);calculated[n]=q
 for label,source,lag,fee,rec in [('lag_plus2','base',2,0,.35),('friction_plus5pp','base',0,.05,.35),('exit_recovery15pct','structural_supported',0,0,.15)]:
  z=rebuilt[source];calculated[label]=tail(z['states'][-1],.1,.01 if source.startswith('structural') else .02,.10 if source.startswith('structural') else .14,z['source'],300,lag,fee,rec)
 endpoints={}
 for label,k,g,roi,name in [('low',.105,.02,.13,'base'),('high',.095,.025,.16,'base'),('margin',.10,.02,.14,'margin_minus_1pp'),('structural',.10,.01,.10,'structural_supported')]:
  s=rebuilt[name];endpoints[label]={}
  for h in [200,300,400,500]:
   q=tail(s['states'][-1],k,g,roi,s['source'],h);q['value']=sum(d/(1+k)**(i+1) for i,d in enumerate(s['D']))+q['tv5']/(1+k)**5;endpoints[label][str(h)]=q
 # Only now read production outputs; no output participates in reconstruction.
 packet=json.loads((D/'2026-Q3-output.json').read_text());actual=json.loads(gzip.decompress(base64.b64decode(packet['payload_gzip_base64'])))
 names=['P','H','J','D','F','R'];maxerr=0
 for n,s in rebuilt.items():
  a=actual['scenarios'][n];assert a['feasible']==s['feasible'],n
  for year,(d,row,state) in enumerate(zip(s['D'],a['rows'],s['states'])):
   assert abs(d-row['dps'])<1e-9
   for i,key in enumerate(names):
    for independent,production in [('cash','cash'),('debt','debt'),('ret','retained'),('reserve','reserve')]:
     
     if i>=3 and production=='reserve':
      assert row['entities'][key][production] is None;continue
     if i>=3 and production=='retained':production='economic_cumulative_profit_budget'
     err=abs(state[independent][i]-row['entities'][key][production]);maxerr=max(maxerr,err);assert err<1e-8,(n,year,key,independent,err)
 for n,q in calculated.items():
  target=actual['values'][n];assert q['feasible']==target['feasible']
  if not q['feasible']:continue
  assert abs(q['tv5']-target['terminal']['per_share'])<1e-8
  for one,two in zip(q['rows'],target['terminal']['rows']):
   assert math.isclose(one['cash_to_common_budget'],two['economic_common_realization'],rel_tol=1e-12,abs_tol=1e-8)
   for i,key in enumerate(names):
    if one['states'][i] is None:continue
    for f in ['cash','debt','profit','reinvestment']:
     assert math.isclose(one['states'][i][f],two['entities'][key][f],rel_tol=1e-12,abs_tol=1e-8),(n,one['year'],key,f)
 for label,hs in endpoints.items():
  for h,q in hs.items():
   target=actual['convergence'][label][h];assert abs(q['value']-target['value'])<1e-8
 result={'scope':'all 12 explicit scenarios; all feasible 300-year paths plus 3 realization/exit sensitivities; four endpoints 200/300/400/500 years','max_explicit_ledger_error':maxerr,'rebuilt':rebuilt,'tail':calculated,'endpoints':endpoints}
 assert maxerr<1e-8

import runpy,subprocess,sys,copy,hashlib
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/"research/companies/CN/002850/models"
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():
 w=json.loads((D/'2026-Q3-output.json').read_text());raw=gzip.decompress(base64.b64decode(w['payload_gzip_base64']));assert hashlib.sha256(raw).hexdigest()==w['expanded_sha256'];return json.loads(raw)
def test_kedali_actual_profit_capital_and_creditor():
 m=model();m['tests']()
 e=dict(retained=-5,reserve=0,capital=20);assert m['profit_legal'](e,3)==0 and e['retained']==-2
 q=m['realization'](3,8,.02,.25,.4);assert q['tax']==0 and abs(q['common']-1.176)<1e-12
 st=dict(cash=1,shares=10,capital=10)
 try:m['capital_action'](st,2,2,-2)
 except ValueError:pass
 else:raise AssertionError('unfunded capitalreturn succeeds')
 assert st==dict(cash=1,shares=10,capital=10)
 base=output()['scenarios']['structural_supported']
 z=m['terminal'](base['rows'][4],.1,.01,.1,exit_recovery=.15)
 assert not z['feasible']
def test_kedali_future_cohorts_and_no_excess_cash():
 out=output()
 for name,v in out['values'].items():
  if not v['feasible']:continue
  for row in v['terminal']['rows']:
   assert abs(row['residual'])<1e-5
   for e in row['entities'].values():assert abs(e['cash']-e['floor'])<1e-7
   for q in row['pending']:assert q['due']-q['born']<=6 and q['due']>row['year_after_5']
def test_kedali_singlefile_complete_roundtrip(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((D/'2026-Q3.py').read_bytes());subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py'),'--expand'],cwd=tmp_path,check=True);assert json.loads((tmp_path/'2026-Q3-expanded.json').read_text())==output()
