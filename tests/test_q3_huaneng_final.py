"""Literal operating/APV and minority reconstruction. No production import or parameter-file read.
Output only supplies financed debt balances and capitalized-interest amounts; financing itself is not independently regenerated.
"""
import json,gzip,math
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'research/companies/CN/600025/models'
S=18.631094257

def independent(b,low=False,rate=.05,high=False):
 scale=1.03 if low else .97 if high else 1.;loan=.03 if low else .026 if high else .028;maint=4.5 if low else 3.5 if high else 4.;end=2101
 pv=lambda a:math.fsum(v/(1+rate)**(y-2026) for y,v in a)
 fs=[(49.06,8.28299014527,.39785046984,2.6,2033,11.281,.40 if low else .45 if high else .425,'H'),(50.40133460819*.85,4.42357346965,.07648238126,2.2,2033,8.8 if low else 10.2 if high else 9.46,.28 if low else .32 if high else .30,'H'),(23.4922659*.85,3.44129553187,.11422327861,1.5,2032,6.149,.31 if low else .35 if high else .33,'H'),(31.7*.85,2.27377883062,.12294163552,2.1,2033,9.036,.31 if low else .35 if high else .33,'H'),(15.85*.85,.44507355036,0,.72,2036,3.096,.31 if low else .35 if high else .33,'H'),(4.95*.85,.82378837876,0,.195,2031,1.162,.25 if low else .27 if high else .26,'H'),(8.75*(1.2 if low else .92 if high else 1),6.25152322764,0,2.5,2028,3.5,.27 if low else .31 if high else .29,'S')]
 def calc(f,printed,q3=True,full=False,holiday=False,target=False):
  cost,cip,old,gw,first,gen,price,tech=f;cost*=scale;remain=cost-cip+old-(2.4*cip/28.59711873621 if q3 else 0);ci=0;out=[]
  for y in range(2027,end+1):
   age=y-first;life=45 if tech=='H' else 20;live=age>=0 and (tech=='H' or age<25);ramp=(1 if full else .5) if age==0 else int(live)
   generation=gen*ramp*((.995 if tech=='S' else .997)**max(0,age) if tech!='H' else 1)
   rev=generation*.992*price/1.13;op=gw*{'H':.2,'S':.05,'W':.08}[tech]*ramp
   maintenance=gw*{'H':.12,'S':.035,'W':.05}[tech]*ramp+(.004*cost*ramp if tech=='H' else 0)
   frac=(1 if full else .5) if age==0 else 1 if 0<age<life else (0 if full else .5) if age==life else 0
   frac=frac if live else 0;replacement=maintenance if tech=='H' and age>=45 else 0
   uda=(cost+old)/life*frac+replacement
   x=printed[y-2027];ci+=x['capitalized_interest'];da=(cost+old+ci)/life*frac+replacement
   expense=x['interest']-x['capitalized_interest'];pre=rev-op-da-expense
   normal=(.09 if y<=2027 else .15 if y<=2030 else .25) if target else .25
   tr=(0 if age<3 else .125 if age<6 else normal) if holiday else normal
   tax=max(0,pre)*tr;utax=max(0,rev-op-uda)*tr
   cap=remain/(first-2027) if y<first else remain if first<=2027 and y==2027 else 0
   out.append(dict(y=y,rev=rev,op=op,uda=uda,pre=pre,tr=tr,tax=tax,utax=utax,fcff=rev-op-utax-maintenance-cap,shield=utax-tax))
  return out
 keys=['RM','GS','BDa','GX','BDuo','GLB','PV_completion']
 pr={n:calc(f,b['projects'][n]['rows']) for n,f in zip(keys,fs)}
 tf=[(18.617*.85,3.91921463674,.11426267834,.6,2027,2.7,.35,'H'),(.810*.95,.01261966514,0,.1,2028,.26,.34,'W'),(.5331218*.95,.33226816921,.00358063057,.13,2026,.338,.34,'W')]
 tp={n:calc(f,b['target']['projects'][n]['rows'],False,n!='X',n=='N',n!='N') for n,f in zip(['X','W2','N'],tf)}
 # Rebuild the actual statutory liquidation tax on ND cash, independently from its project cash financing inputs.
 ncash=nret=nreserve=payable=0.;nbasis=.05179;ntax=0.
 for i,y in enumerate(range(2027,2052)):
  x=b['target']['projects']['N']['rows'][i];z=tp['N'][i];ncash-=payable
  # DA is reconstructed from tax base because holiday changes must not imply a tax refund.
  age=y-2026;da=(.5331218*.95*scale+.00358063057)/20 if age<20 else 0
  profit=z['pre']-z['tax'];flow=profit+da-.13*.05*(age<25)-x['repayment']-x['equity_call'];ncash+=flow
  support=max(0,-ncash);ncash+=support;nbasis+=support
  take=min(.1*max(0,profit+min(0,nret)),max(0,.05-nreserve));nreserve+=take;nret+=profit-take
  div=min(max(0,nret),max(0,ncash));nret-=div;ncash-=div
  if y==2051:ntax=max(0,ncash-nbasis)*.25
  payable=.2*div;ncash+=payable
 mature=[];target=[];shields=[];pool=[];pd=69.41272394423;sd=126.50412978373-pd;td=8.09361587276
 for i,y in enumerate(range(2027,end+1)):
  t=y-2027;infl=1.005**t;runoff=1 if t<15 else max(0,min(1,(24-t)/10));transition=max(0,min(1,(t-19)/20))
  rev=(25.6+1.6*runoff)*infl+(.594 if y>=2035 else 0);cost=6.2*infl;da=(7.5*(1-transition)+(maint+.4)*transition)*infl;mr=.15 if y<=2030 else .25;maintenance=maint*infl+(8*infl if (t+1)%20==0 else 0)
  mature.append((y,(rev-cost-da)*(1-mr)+da-maintenance))
  pe=(19.3-4.9)*infl+(.594 if y>=2035 else 0)-da*5.3/7.5;se=rev-cost-da-pe;pp=pe-pd*loan;sp=se-sd*loan
  direct=[pr[n][i] for n in ('GS','GLB')];upper=[pr[n][i] for n in ('RM','BDuo')]
  saving=lambda vals,r:sum(max(0,v)*r for v in vals)-max(0,sum(vals))*r
  dactual=saving([pp]+[x['pre'] for x in direct],mr);dun=saving([pe]+[x['rev']-x['op']-x['uda'] for x in direct],mr)
  uactual=saving([x['pre'] for x in upper],.25);uun=saving([x['rev']-x['op']-x['uda'] for x in upper],.25)
  ms=max(0,rev-cost-da)*mr-(max(0,pp)+max(0,sp))*mr
  factor=.7+(.3*.995**t if t<25 else 0);trev=1.15*factor*infl;top=.28*factor*infl;tda=(.4*(1-transition)+.14*transition)*factor*infl;tr=.09 if y<=2027 else .15 if y<=2030 else .25;tpre=trev-top-tda-td*(.016 if t<3 else loan)
  tax=max(0,tpre)*tr;utax=max(0,trev-top-tda)*tr;branch=[tp[n][i] for n in ('X','W2')]
  ta=saving([.9*tpre]+[x['pre'] for x in branch],tr);tu=saving([.9*(trev-top-tda)]+[x['rev']-x['op']-x['uda'] for x in branch],tr)
  cf=trev-top-utax-.14*factor*infl+tu
  if t<4:cf+=(.36794333648+.02426980978)/4
  if t<2:cf-=.21884897942/2
  if y==2051:cf-=ntax
  target.append((y,cf));pool.append((y,dun+uun))
  ps=sum(x[i]['shield'] for x in pr.values())-.11*(pr['BDa'][i]['shield']+pr['GX'][i]['shield'])
  shields.append((y,ms+ps+utax-tax+sum(x[i]['shield'] for x in tp.values())+dactual-dun+uactual-uun+ta-tu))
  pd=b['rows'][i]['parent_debt'];sd=b['rows'][i]['mature_sub_debt'];td=b['target']['rows'][i]['general_debt']
 last=mature[-1][1];normalized=last+(8*infl if (end-2026)%20==0 else 0)-.4*infl
 mev=pv(mature)+((normalized-.594*.75)/(rate-.005)+.594*.75/rate)/(1+rate)**75
 pvs={n:pv([(x['y'],x['fcff']) for x in z])+(z[-1]['fcff']/rate/(1+rate)**75 if n!='PV_completion' else 0) for n,z in pr.items()}
 acq=pv(target)+target[-1][1]/rate/(1+rate)**75+sum(pv([(x['y'],x['fcff']) for x in z])+(z[-1]['fcff']/rate/(1+rate)**75 if n=='X' else 0) for n,z in tp.items())+.04648791615-.1-8.09361587276-8.7012044/(1+rate)
 bases=[.3276975737,.22545125684,.01508410178,.10705748942,.02732937992,.09738019834];cash=[.4*v/.8 for v in bases];nseries=[]
 for y in range(2027,end+1):
  t=y-2027;runoff=1 if t<15 else max(0,min(1,(24-t)/10));profit=[v*1.005**t*(runoff if k<2 else 1) for k,v in enumerate(bases)];paid=[.5*v+(cash[k]*.2 if t>=9 else 0)+(cash[k]*.8 if k<2 and runoff==0 else 0) for k,v in enumerate(profit)];cash=[cash[k]+v-paid[k] for k,v in enumerate(profit)];nseries.append((y,sum(paid)))
 ntail=sum(cash)*.2/(rate+.2)+sum(profit)*1.005/(rate-.005)*(.5+.1/(rate+.2));nci=pv(nseries)+ntail/(1+rate)**75
 fiscal=(.2+.9*(3.66609092479-.2))/4*sum((1+rate)**-i for i in range(1,5))
 eq=mev+sum(pvs.values())-.11*(pvs['BDa']+pvs['GX'])+pv(pool)+pv(shields)+fiscal+acq-pv([(2027,2/3),(2028,2/3),(2029,2/3)])-126.50412978373-16.217-nci-7.68024741949+3.72253673088-2.0296755+5.41473511562
 return {'per_share':eq/S,'nci':nci,'shield':pv(shields),'liquidation_tax':ntax}


import importlib.util,base64,hashlib,copy
import pytest
@pytest.fixture(scope="module")
def model():
 spec=importlib.util.spec_from_file_location("huaneng_final",P/"2026-Q3.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
@pytest.fixture(scope="module")
def output():
 packed=json.loads((P/'2026-Q3-output.json').read_text());meta=packed['_complete_output'];raw=gzip.decompress(base64.b64decode(meta['data']));assert len(raw)==meta['expanded_bytes'];assert hashlib.sha256(raw).hexdigest()==meta['sha256'];return json.loads(raw)
@pytest.mark.parametrize('label,low,high,r',[('central',False,False,.05),('core_low',True,False,.055),('core_high',False,True,.045),('ku6',False,False,.06)])
def test_literal_operating_apv(output,label,low,high,r):
 b=output['cases'][label];v=independent(b,low,r,high);assert v['per_share']==pytest.approx(b['current']['per_share'],abs=1e-10);assert v['nci']==pytest.approx(b['current']['nci'],abs=1e-10)
def test_fresh_all_fields_and_pack(model,output):
 fresh=model.make();assert fresh==output;assert model.expand_output(model.pack_output(fresh))==output
 assert model.pack_output(fresh)==json.loads((P/'2026-Q3-output.json').read_text())
def test_actual_legal_and_capital_functions(model):
 assert all(model.tests().values())
 assert model.reserve(10,0,5,20,paid=10)==1
 assert model.reserve(10,-12,0,20)==0
 assert model.reserve(10,0,10,20)==0
 assert model.reserve(10,0,10,22)==1
 assert model.capital_action(20,10,10,5,4,2,'reduction')==(16,8,8,4)
 assert model.realized_capital(10,12,fee=1,ownership=.65)==pytest.approx((5.85,-1.95))
def test_negative_ebit_tax_and_real_taxpayer(model):
 q=copy.deepcopy(model.SC['central']);q['mature_price']=0;x=model.mature(q,2027)
 assert x['ebit']<0 and x['fcff']==pytest.approx(-10.2)
 assert model.pooled_tax_saving([10,-8],.25)==2
 assert model.pooled_tax_saving([10],.25)+model.pooled_tax_saving([-8],.25)==0
 assert sum(model.depreciation_fraction(i,45,.5) for i in range(47))==45
 c=copy.deepcopy(model.SC['central']);c.update(first=[2027],gen=[10.],price=[1.])
 x=model.engineering({'engineering':1.,'dynamic':1.,'cip':0.,'old_interest':0.,'gw':1.,'target_tax':True,'first_ramp':1.},c,0,end=2027)['rows'][0]
 assert x['engineering']>0 and x['revenue']>0
 assert x['tax']==pytest.approx(max(0,x['pretax'])*.09)
def test_funding_boundary_not_infinite(model,output):
 assert model.fund(1,3,2,1,4,0)==(2,-1,1)
 with pytest.raises(ValueError):model.fund(1,-5,0,0,10,2)
 assert not output['cases']['structural']['feasible']
 assert 'zero-distribution funding gap' in output['cases']['structural']['reason']
def test_every_scenario_annual_cash_and_capital(output):
 assert len(output['cases'])==39
 for b in output['cases'].values():
  if not b['feasible']:continue
  for z in b['rows']:
   assert abs(z['consolidated_cash_check'])<1e-7
   assert z['parent_cash']>=.6-1e-8 and z['parent_distribution']>=0
   assert z['mature_sub_cash']>=2.5+z['mature_nci_restricted_cash']-1e-8
   assert z['parent_statutory_reserve']<=z['parent_registered']/2+1e-8
   if b['target']:assert z['target']['registered']>=1-1e-8

def test_minority_runoff_and_continuing_claim(model):
 states={n:.4*v/.8 for n,v in model.NCI_BASE.items()};z=model.minority_step(states,{},2027)
 assert sum(x['gross_cash_payment'] for x in z.values())==pytest.approx(.4)
 assert sum(states.values())==pytest.approx(.8)
 z=model.minority_step({n:1. for n in model.NCI_BASE},{},2051)
 assert z['云南联合电力']['closing_restricted_cash']==0 and z['桑河二级水电']['gross_cash_payment']==1
 assert model.minority_step({n:0. for n in model.NCI_BASE},{},2060)['龙开口']['gross_cash_payment']>0

def test_fixed_year5_interface_and_finite_horizon(model,output):
 assert output['return_model']['base_case_distributions_per_share']==[x['dps'] for x in output['cases']['central']['rows'][:5]]
 assert output['return_model']['base_case_terminal_equity_value_range_per_share']['year_5']=={k:output['terminal_base_rate_range'][k]['per_share'] for k in ('low','high')}
 values=[model.run('central',end=y)['current']['per_share'] for y in [2086,2101,2126,2151]]
 assert max(values)-min(values)<.022
 for b in output['cases'].values():
  if b['feasible']:assert b['rows'][-1]['mature']['maintenance']>0
