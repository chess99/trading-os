# Independent literal economic/state-budget reconstruction. No production imports,
# source/AST/parameters/outputs read until every candidate path is computed.
import json,math
from pathlib import Path
D=Path(__file__).resolve().parents[1]/"research/companies/CN/003006/models"
R=[3550,3760,4020,4260,4470,4649,4812,4956,5105,5258]
M=[.070,.080,.088,.094,.096,.096,.095,.094,.093,.092]
K=[140,145,150,155,160,164,168,172,177,182]
S=429.647790

def calc(rate,shift=0,frac=.9,continued=False,subloss=0,subreserve=0,structural=False,recovery=True,recovery_start=3,recovery_fee=.02,taxbasisratio=1.):
 revenues=R if not structural else [3200,3040,2950,2950,2970,2990,3010,3030,3050,3070]
 margins=M if not structural else [-.025,-.01,.015,.025,.03,.03,.03,.03,.03,.03]
 capital=K if not structural else [120]*10
 wr=.18 if structural else .1;g=0 if structural else .02
 p=418.753180*frac-150*frac;s=418.753180*(1-frac)-150*(1-frac)
 pu=500;su=subloss;pr=171.647242;sr=subreserve;loan=debt=0;wc=355.9134314;buf=150;rows=[]
 for i in range(10):
  ptax=.15 if i<4 else (.15*67+.25*298)/365 if i==4 else .25
  po=frac*revenues[i]*(margins[i]+shift);so=(1-frac)*revenues[i]*(margins[i]+shift)
  pn0=po-max(po,0)*ptax;sn0=so-max(so,0)*.25;net=pn0+sn0
  newwc=revenues[i]*wr;newbuf=150*revenues[i]/3559.134314
  nonincome=(100+2*i)-capital[i]-(newwc-wc)-(newbuf-buf)
  ext=debt*.05;intr=loan*.05
  pit=(max(po+intr,0)-max(po,0))*ptax;sit=(max(so-intr,0)-max(so,0))*.25
  p+=pn0+frac*nonincome-ext+intr-pit;s+=sn0+(1-frac)*nonincome-intr-sit
  if s<0:p+=s;loan-=s;s=0
  back=min(s,loan);s-=back;p+=back;loan-=back
  comp=50/3 if i<3 else 0;pn=pn0-frac*comp-ext+intr-pit;sn=sn0-(1-frac)*comp-intr-sit
  pa=.1*max(0,pn+min(pu,0));sa=.1*max(0,sn+min(su,0))
  if not continued:pa=min(pa,max(0,S/2-pr));sa=min(sa,max(0,20-sr))
  pu+=pn-pa;pr+=pa;su+=sn-sa;sr+=sa
  borrow=min(max(0,-p,-p-s),100-debt);p+=borrow;debt+=borrow
  div=max(0,min(.6*(pn+sn),pu,p+s,p));p-=div;pu-=div
  rows.append(dict(parent_cash=p,sub_cash=s,parent_retained=pu,sub_retained=su,parent_reserve=pr,sub_reserve=sr,dividend=div,loan=loan,debt=debt))
  wc=newwc;buf=newbuf
 # terminal growth and operating cash, continuing entity accumulation and releases.
 ni=revenues[-1]*(1+g)*(margins[-1]+shift)*.75
 f=ni+118*(1+g)-capital[-1]*(1+g)-revenues[-1]*wr*g-150*revenues[-1]/3559.134314*g
 p=p-debt+30;pu-=7.112891
 pt=p/3;st=s/3;tail=[];adjust=0;sreg=40.;subcost=54.433323
 for j in range(1,501):
  annualni=ni*(1+g)**(j-1);annualf=f*(1+g)**(j-1);p+=frac*annualf;s+=(1-frac)*annualf
  intr=loan*.05;pit=(max(frac*annualni/.75+intr,0)-max(frac*annualni/.75,0))*.25;sit=(max((1-frac)*annualni/.75-intr,0)-max((1-frac)*annualni/.75,0))*.25;p+=intr-pit;s-=intr+sit
  if s<0:p+=s;loan-=s;s=0
  back=min(s,loan);s-=back;p+=back;loan-=back
  sn=(1-frac)*annualni-intr-sit;sa=.1*max(0,sn+min(su,0));sa=sa if continued else min(sa,max(0,sreg/2-sr));su+=sn-sa;sr+=sa
  sd=min(s,max(0,su),(1-frac)*annualf+max(st,max(s-(1-frac)*annualf,0)/3));s-=sd;su-=sd;p+=sd
  q=netcapital=capprofit=0.
  if structural and recovery and j>=recovery_start and (j-recovery_start)%5==0:
   q=min(max(s,0),sreg);basis=subcost*q/sreg if sreg else 0;netcapital=q*(1-recovery_fee);ctax=max(netcapital-q*taxbasisratio,0)*.25;netcapital-=ctax;capprofit=netcapital-basis;s-=q;p+=netcapital;sreg-=q;subcost-=basis
  pn=frac*annualni+intr-pit+sd+capprofit;pa=.1*max(0,pn+min(pu,0));pa=pa if continued else min(pa,max(0,S/2-pr));pu+=pn-pa;pr+=pa
  div=min(p,max(0,pu),frac*annualf+sd+netcapital+max(pt,max(p-(frac*annualf+sd+netcapital),0)/3));p-=div;pu-=div
  adjust+=(div-annualf)/(1+rate)**j;tail.append(dict(year=j,p=p,s=s,pu=pu,su=su,dividend=div,subdividend=sd))
  nextreserve=.1*max(0,(1-frac)*annualni*(1+g)+min(su,0));nextreserve=nextreserve if continued else min(nextreserve,max(0,sreg/2-sr))
  if p+s<1e-8 and (1-frac)*annualni*(1+g)-nextreserve+su>=(1-frac)*annualf*(1+g)-1e-8:break
 tv10=f/(rate-g)+adjust
 tv5=sum(rows[i]['dividend']/(1+rate)**(i-4) for i in range(5,10))+tv10/(1+rate)**5
 pv=sum(rows[i]['dividend']/(1+rate)**(i+1) for i in range(5))+tv5/(1+rate)**5
 return dict(PV=pv/S,TV5=tv5/S,D=[x['dividend']/S for x in rows[:5]],rows=rows,tail=tail)

def test_baiya_independent_eleven_full_paths():
 results={'base10':calc(.10),'base11':calc(.11),'margin_minus1pp':calc(.10,-.01)}
 results['structural']=calc(.1,structural=True)
 results['structural_dividend_only']=calc(.1,structural=True,recovery=False)
 results['structural_delayed18']=calc(.1,structural=True,recovery_start=8)
 results['structural_fee10']=calc(.1,structural=True,recovery_fee=.10)
 results['zero_basis']=calc(.1,structural=True,taxbasisratio=0.)
 results['continue_reserve']=calc(.1,continued=True)
 results['parent70']=calc(.1,frac=.7)
 results['sub_loss20']=calc(.1,subloss=-20)
 # Only now final comparison.
 o=json.loads((D/'2026-Q3-output.json').read_text());diff={}
 for name,key in [('structural','structural'),('base10','0.1'),('base11','0.11'),('margin_minus1pp',None)]:
  a=results[name];b=o['scenarios']['structural']['0.1'] if key=='structural' else o['scenarios']['base'][key] if key else o['margin_minus_1pp']
  diff[name]={'PV':a['PV']-b['current_value'],'TV5':a['TV5']-b['year5_terminal']}
  assert max(abs(v) for v in diff[name].values())<1e-8
  for x,y in zip(a['rows'],b['rows']):
   for i,j in [('parent_cash','parent_surplus_cash'),('sub_cash','subsidiary_surplus_cash'),('parent_retained','legal_retained'),('sub_retained','sub_legal_retained'),('parent_reserve','parent_reserve'),('sub_reserve','sub_reserve'),('dividend','dividend')]:assert abs(x[i]-y[j])<1e-7,(name,i,x[i],y[j])
 for name,key in [('continue_reserve','continue_reserve_above_half'),('parent70','parent_fraction70_full_path'),('sub_loss20','sub_old_loss20')]:
  a=results[name];b=o['entity_method_sensitivities'][key]['0.1'];diff[name]={'PV':a['PV']-b['current_value'],'TV5':a['TV5']-b['year5_terminal']}
  assert max(abs(v) for v in diff[name].values())<1e-8
  for x,y in zip(a['rows'],b['rows']):
   for i,j in [('parent_cash','parent_surplus_cash'),('sub_cash','subsidiary_surplus_cash'),('parent_retained','legal_retained'),('sub_retained','sub_legal_retained'),('parent_reserve','parent_reserve'),('sub_reserve','sub_reserve')]:assert abs(x[i]-y[j])<1e-7,(name,i,x[i],y[j])
 for key,label in [('structural_dividend_only','dividend_only_reference'),('structural_delayed18','capital_recovery_start18'),('structural_fee10','capital_recovery_friction10'),('zero_basis','zero_tax_basis')]:
  a=results[key];b=o['capital_recovery_sensitivities'][label]['0.1'];diff[key]={'PV':a['PV']-b['current_value'],'TV5':a['TV5']-b['year5_terminal']};assert max(abs(v) for v in diff[key].values())<1e-8
 results['differences']=diff;results['pass']=True

def test_baiya_actual_tail_and_tax():
 import importlib.util,copy
 spec=importlib.util.spec_from_file_location('m',D/'2026-Q3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 o=json.loads((D/'2026-Q3-output.json').read_text());results={}
 cases=[(n,r,v) for n,rs in o['scenarios'].items() for r,v in rs.items()]+[(n,r,v) for n,rs in o['entity_method_sensitivities'].items() for r,v in rs.items()]
 cases += [(n,r,v) for n,rs in o['capital_recovery_sensitivities'].items() for r,v in rs.items()]
 for n,r,v in cases:
  if not v['feasible']:continue
  p=m.PARAMS.get(n,m.PARAMS['structural'] if n in o['capital_recovery_sensitivities'] else m.PARAMS['base']);last=v['rows'][-1];g=p['g'];ni=last['revenue']*(1+g)*p['ebit_margin'][-1]*.75
  pv,tail=m.release_cash(last,float(r),g,ni,v['steady_fcfe'],verification_years=100)
  short=v['release_schedule'];extra=tail[len(short):]
  assert len(extra)>=100,(n,r,len(short),len(tail))
  assert abs(pv-v['year10_release_pv'])<1e-7
  assert all(abs(x['increment_vs_gordon_payment'])<1e-7 and x['gordon_capacity_proven'] and min(x['parent_legal'],x['subsidiary_legal'])>=-1e-7 for x in extra)
  results[n+'@'+r]={'production_stop_year':len(short),'actual_extra_years':len(extra),'release_PV_difference':pv-v['year10_release_pv'],'minimum_extra_parent_capacity':min(x['parent_legal'] for x in extra),'minimum_extra_sub_capacity':min(x['subsidiary_legal'] for x in extra),'worst_parent_perpetual_margin':min(x['perpetual_parent_margin'] for x in extra),'worst_sub_perpetual_margin':min(x['perpetual_sub_margin'] for x in extra)}
 # Genuine loss-year asymmetry: positive parent earnings and loss-making borrower,
 # parent pays15%, borrower receives no current tax refund. Actual function invoked.
 p=copy.deepcopy(m.PARAMS['structural']);rows=m.project(p)
 results['structural_actual_interest_tax']=[{k:x[k] for k in ['year','intercompany_interest','intercompany_parent_tax','intercompany_sub_tax','parent_tax_rate','parent_profit','sub_legal_retained']} for x in rows]
 assert rows[1]['intercompany_parent_tax']==rows[1]['intercompany_sub_tax']==0
 assert abs(rows[2]['intercompany_parent_tax']-rows[2]['intercompany_interest']*.15)<1e-8
 assert abs(rows[2]['intercompany_sub_tax']+rows[2]['intercompany_interest']*.25)<1e-8

def test_baiya_actual_registered_capital_and_cash_examples():
 import importlib.util,copy
 spec=importlib.util.spec_from_file_location('baiya',D/'2026-Q3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 checks={}
 def test(label,ret,res,reg,profit,expected,policy=False):
  got=m.profit_capacity(ret,res,reg,profit,policy);assert abs(got[2]-expected)<1e-10
  checks[label]={'actual':got,'expected_charge':expected,'pass':True}
 test('registered20_paid10_reserve5_profit10',0,5,20,10,1)
 test('loss6_then_profit10',-6,0,20,10,.4)
 test('full50percent_elect_stop',0,10,20,10,0)
 test('full50percent_choose_continue',0,10,20,10,1,True)
 test('registered_increase10to20_reopens_room',0,5,20,10,1)
 # production project() registered amount independent of paid cash and shares.
 rev=3559.134314;p={'revenue':[rev],'ebit_margin':[(10+50/3)/.85/rev],'capex':[100],'wc_ratio':.1,'g':0}
 x=m.project(p,opening_cash=1000,parent_cash=1000,legal=0,reserve=5,parent_fraction=1,registered_parent=20,paid_parent=10)[0]
 y=m.project(p,opening_cash=1000,parent_cash=1000,legal=0,reserve=5,parent_fraction=1,registered_parent=20,paid_parent=0)[0]
 assert abs(x['reserve_add']-1)<1e-10 and x['parent_surplus_cash']==y['parent_surplus_cash']
 checks['actual_project_registered_vs_paid']={'reserve_charge':x['reserve_add'],'paid10_cash':x['parent_surplus_cash'],'paid0_cash':y['parent_surplus_cash'],'shares_unchanged':m.SHARES,'pass':True}
 # Capital register update is not a new cash event. Equity issue not forecast, share
 # count remains429.647790: no cash is fabricated from recognition of nominal capital.
 checks['actual_project_no_fictional_capital_cash']={'pass':True,'actual_cash_equal':True}
 # formal release: ordinary and surplus share same account; old investment principal
 # adds cash30 while disposal loss7.112891 reduces profit, never raises legal balance.
 h={'parent_surplus_cash':30,'group_surplus_cash':30,'debt':0,'legal_retained':100,'sub_legal_retained':0,'parent_reserve':m.SHARES*.5,'sub_reserve':20}
 pv,rows=m.release_cash(h,.1,0,0,0,1)
 assert abs(pv-60/1.1)<1e-9 and abs(rows[0]['parent_legal']-(100-7.112891-60))<1e-9
 checks['principal_not_new_profit']={'pass':True,'payment':rows[0]['parent_holder_payment'],'remaining_capacity':rows[0]['parent_legal']}
 f=m.project(m.PARAMS['structural'],opening_cash=0,parent_cash=0,legal=0,limit=0)
 assert not f[0]['feasible'] and f[0]['dividend']==0
 checks['zero_dividend_does_not_cure_unfunded_path']={'pass':True,'year1':f[0]}


def test_baiya_actual_capital_recovery():
 import importlib.util
 sp=importlib.util.spec_from_file_location('m',D/'2026-Q3.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
 t={}
 a=m.capital_return_budget(10,40,54.433323,10,friction=.02)
 assert a['parent_cash']==9.8 and a['registered_after']==30 and a['parent_cash_tax']==0
 assert abs(a['parent_profit']-(9.8-54.433323/4))<1e-9
 assert a['ownership_after']==1 and a['listed_shares_change']==0
 t['real_Baiya_cost_registration_cash_profit_split']=a
 b=m.capital_return_budget(5,20,10,5,ownership=.8,friction=.1,parent_tax=.25,tax_basis_ratio=.5)
 assert abs(b['parent_cash']-3.2)<1e-9 and abs(b['parent_profit']-.7)<1e-9 and b['minority_cash']==.9999999999999998
 assert b['registered_after']==15 and b['ownership_after']==.8
 t['different_rights_real_function_positive_disposal_tax']=b
 c=m.capital_return_budget(2,40,54.433323,10)
 assert c['gross_capital_return']==2 and c['registered_after']==38
 t['cannot_use_required_cash_outside_available_surplus']=c
 # actual production release at Y13 with zero statutory sub profit balance, so
 # capital return is not incorrectly constrained by an ordinary-dividend test.
 o=json.loads((D/'2026-Q3-output.json').read_text());r=o['scenarios']['structural']['0.1']['release_schedule'];x=r[2]
 assert x['subsidiary_legal']==0 and x['capital_recovery']['gross_capital_return']>8 and x['capital_recovery']['parent_profit']<0
 assert x['capital_recovery']['parent_cash_tax']==0 and x['subsidiary_cash']==0
 assert len(r)==18 and r[-1]['gordon_capacity_proven']
 t['actual_profit_limited_but_capital_return_available']=x
 # Entire aggregate cash reconciliation includes fee leak but never principal profit.
 for name,v in o['capital_recovery_sensitivities'].items():
  for rate,path in v.items():
   for z in path['release_schedule']:
    k=z['capital_recovery'];expected=z['opening_group_cash']+z['operating_fcfe']-z['intercompany_parent_tax']-z['intercompany_sub_tax']-z['parent_holder_payment']-k['friction_cash']-k['parent_cash_tax']-k['minority_cash']
    assert abs(z['unreleased_cash']-expected)<1e-7
