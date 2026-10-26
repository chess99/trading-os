"""Independent literal-input calculator. Does not import/read production code or
production parameter/AST objects. Reads ONLY final PV/TV numbers for comparison
AFTER own computations. Units billion CNY. Authored from sources-assumptions.
"""
import json, math
from pathlib import Path
NAMES=['P','A','E','D','C','H','U']; S=.977170720
# cash, lock, debt, capital, reserve, U, fixed, WC, tax, limit, ownership
START=[[2.85,.428,1.85,.97717072,.48858536,4.06127034,2.7,2.25,.15,2.15,1],[.25,0,.4,.389198642,0,0,.82,.45,.15,.65,.685],[.28,0,.4,0,0,-.1,.5,.5,.30,.7,1],[.033,0,0,.030950195,0,0,.04,.04,.25,.03,1],[.02,0,.016,.0115,0,0,.035,.015,.25,.05,1],[0,0,0,0,0,0,0,0,0,0,1],[0,0,0,0,0,0,0,0,0,0,1]]
R=[[6.6,7.2,7.8,8.3,8.7],[1.4,1.48,1.56,1.63,1.7],[1.3,1.5,1.65,1.8,1.9],[.2,.21,.22,.23,.24],[1.3,1.36,1.42,1.48,1.54]]
M=[[.08,.09,.1,.105,.11],[.03,.035,.04,.045,.05],[0,.03,.05,.06,.07],[.01,.015,.02,.025,.03],[.003,.004,.005,.006,.007]]
K=[[5.05,5.15,5.35,5.55,5.75],[1.31,1.35,1.39,1.43,1.47],[1.08,1.12,1.16,1.2,1.24],[.082,.084,.086,.088,.09],[.052,.054,.056,.058,.06]]
FINISH=[.095,.045,.055,.025,.006];W=[.56,.65,.5,.5,.7];WEIGHT=[1,.5,1,.5,.1]
def calc(rate,shift=0,capital_factor=1,n=240,freeze=False,structure=False,recovery=True,start=13,fee=.02,taxbasis=1.):
    states=[a.copy()+[0.] for a in START];flows=[];checks=[];dcost=.04251307794
    for yr in range(1,n+1):
        declared=[0.]*7;receipts=[0.]*7;capgain=[0.]*7
        for j in [1,2,3,4,5,6,0]:
            cash,lock,debt,capital,reserve,loss,fix,wc,taxrate,limit,own,payable=states[j]
            if j<5:
                t=min(yr-1,4);r=R[j][t];m=M[j][t]+(0 if freeze and yr<=5 else shift)*WEIGHT[j];cap=K[j][t]*capital_factor
                if yr>5:
                    f=1. if structure else 1.03**min(yr-5,5)*1.02**max(yr-10,0);r*=f;cap*=f;m+=(FINISH[j]-M[j][4])*min((yr-5)/10,1)
                if structure:r*=.85;cap*=1.08;m-=.01 if j==2 else 0
                nf=cap*W[j];nw=cap*(1-W[j]);minimum=r*(.07 if j==0 else .01 if j==4 else .05)
            else:r=m=nf=nw=minimum=0
            ebit=r*m;pre=ebit+cash*.015-debt*.03;profit=pre-max(pre,0)*taxrate;awards=.165 if j==0 and yr<=3 else 0;profit-=awards
            earned=profit+declared[j]+capgain[j]
            replenish=0
            if j in (0,1,3,4):replenish=min(max(0,capital/2-reserve),max(0,earned-max(0,-loss))*.1)
            legal=loss+earned-replenish;reserve+=replenish
            # Separate balance movement rather than production CFO/capex formula.
            balance=cash+profit+awards-(nf-fix)-(nw-wc)+receipts[j]
            if yr==1 and j==0:balance-=.2215+.0701+.1+.113127127
            repayment=min(debt,max(0,balance-lock-minimum-payable)*.65);balance-=repayment;newdebt=debt-repayment
            if yr>=2 and START[j][2]-newdebt>=min(.428,lock):lock=0
            if newdebt<1e-8:lock=0
            raise_=min(max(0,minimum+lock+payable-balance),max(0,limit-newdebt));balance+=raise_;newdebt+=raise_
            oldsettle=min(payable,max(0,balance-lock-minimum));balance-=oldsettle
            usable=max(0,balance-lock-minimum)
            desire=([.25,.35,.45,.55,.6][yr-1]*S if yr<=5 else max(0,earned)) if j==0 else max(0,earned)*(.7 if j<5 else 1)
            if yr>=9:desire=usable
            distribution=min(desire,max(0,legal),usable)
            now=distribution*(.8 if 0<j<5 else 1)
            rem=payable-oldsettle+distribution-now;balance-=now
            if j==3 and recovery and yr>=start and (yr-start)%5==0:
                q=min(max(balance-minimum-lock-rem,0),capital)
                basis=dcost*q/capital if capital else 0
                proceeds=q*(1-fee);tax=max(proceeds-q*taxbasis,0)*.15
                receipts[0]+=proceeds-tax;capgain[0]+=proceeds-tax-basis
                balance-=q;capital-=q;dcost-=basis
            assert balance+1e-7>=minimum+lock+rem
            states[j]=[balance,lock,newdebt,capital,reserve,legal-distribution,nf,nw,taxrate,limit,own,rem]
            if j!=0:
                dest=5 if j==2 else 6 if j==5 else 0;factor=own*(.95 if j==6 else 1)
                declared[dest]+=distribution*factor;receipts[dest]+=(oldsettle+now)*factor
            else:flows.append(now/S)
        checks.append({'year':yr,'parent_cash':states[0][0],'parent_U':states[0][5],'group_cash':sum(a[0] for a in states),'debt':sum(a[2] for a in states)})
    return {'PV':math.fsum(x/(1+rate)**(i+1) for i,x in enumerate(flows)),'TV5':math.fsum(x/(1+rate)**(i-4) for i,x in enumerate(flows) if i>=5),'DPS5':flows[:5],'year5':checks[4],'all_checks':checks}
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/002318/models'

def test_jiuli_twelve_literal_value_and_annual_states():
 res={}
 for name,rate,margin,k in [('core_low',.105,-.005,1),('base',.10,0,1),('core_high',.095,.005,1),('margin_minus_1pct',.10,-.01,1),('capital_plus_15pct',.10,0,1.15)]:
     res[name]=calc(rate,margin,k)
 for name,r,m in [('holder_low',.105,-.005),('holder_high',.095,.005)]:res[name]=calc(r,m,freeze=True)
 for label,options in [('structural',{}),('structural_dividend_only',{'recovery':False}),('structural_recovery_delay20',{'start':20}),('structural_recovery_fee10',{'fee':.1}),('structural_zero_tax_basis',{'taxbasis':0})]:
     res[label]=calc(.11,-.025,structure=True,**options)
 res['convergence']={s:{str(n):calc(r,m,1,n) for n in [160,240,320]} for s,r,m in [('core_low',.105,-.005),('core_high',.095,.005)]}
 res['holder_convergence']={s:{str(n):calc(r,m,1,n,True) for n in [160,240,320]} for s,r,m in [('holder_low',.105,-.005),('holder_high',.095,.005)]}
 # Only at this point read production outputs, and only compare result fields.
 p=json.loads((ROOT/'2026-Q3-output.json').read_text());differences={}
 for name in ['core_low','base','core_high','margin_minus_1pct','capital_plus_15pct','holder_low','holder_high','structural','structural_dividend_only','structural_recovery_delay20','structural_recovery_fee10','structural_zero_tax_basis']:
     differences[name]={key:res[name][key]-p['scenarios'][name][key] for key in ['PV','TV5']}
     assert max(abs(x) for x in differences[name].values())<1e-10
     assert all(abs(a-b)<1e-10 for a,b in zip(res[name]['DPS5'],p['scenarios'][name]['DPS5']))
 res['differences']=differences;res['pass']=True
 
 import gzip,base64
 for name,z in res.items():
  if not isinstance(z,dict) or 'all_checks' not in z:continue
  rows=json.loads(gzip.decompress(base64.b64decode(p['scenarios'][name]['annual_trace_gzip_base64'])))
  for a,b in zip(z['all_checks'],rows):
   parent=b['entities']['P']
   assert abs(a['parent_cash']-parent['cash_end'])<1e-7
   assert abs(a['parent_U']-parent['retained'])<1e-7
   assert abs(a['group_cash']-b['cash_bn'])<1e-7
   assert abs(a['debt']-b['debt_bn'])<1e-7

def test_jiuli_actual_chain_handcases_failure_and_common_y5():
 import runpy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));assert m['boundary']()['pass']
 f=json.loads((ROOT/'2026-Q3-output.json').read_text());base=m['expand']({k:v for k,v in f['scenarios']['base'].items() if k!='assumptions'})
 for name in ['holder_low','holder_high']:
  z=m['expand']({k:v for k,v in f['scenarios'][name].items() if k!='assumptions'})
  assert z['years'][:5]==base['years'][:5]
  conv=f['convergence'][name]
  for k in ['PV','TV5']:assert abs(conv['240'][k]-conv['320'][k])<1e-6
 z=f['scenarios']['no_refinance_zero_D'];assert not z['feasible'] and z['PV'] is None and z['TV5'] is None

def test_jiuli_registered_threshold_and_budget_identity():
 import runpy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'))
 # Paid-in can be 10 while registered is 20. Threshold uses registered, not paid-in.
 assert m['legal_step'](0,5,20,10,True)==(9.,6.,1.)
 assert abs(m['legal_step'](-6,0,20,10,True)[2]-.4)<1e-12
 assert m['legal_step'](0,0,None,10,False)==(10,0,0)
 assert m['OPEN']['P']['reserve']==m['OPEN']['P']['capital']/2
 for e in ['A','D','C']:
  assert m['OPEN'][e]['retained']==0 and m['OPEN'][e]['reserve']==0
 for e in ['E','H','U']: assert m['OPEN'][e]['capital'] is None
 row=m['run'](m['SCENARIOS']['base'],1)['years'][0]
 for e in ['A','D','C','E','H','U']:
  x=row['entities'][e]
  assert x['actual_individual_statutory_reserve'] is None
  assert x['actual_individual_legal_retained'] is None
  assert x['declared_D']<=max(0,x['distribution_capacity_budget_before_D'])+1e-10

def test_jiuli_complete_annual_trace_is_lossless():
 import runpy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'))
 for c in m['SCENARIOS'].values():
  full=m['run'](c)
  assert m['expand'](m['pack'](full))==full


def test_jiuli_all_scenario_capital_recovery_and_real_functions():
 import importlib.util,copy
 D=ROOT;sp=importlib.util.spec_from_file_location('m',D/'2026-Q3.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
 tests={};scenarios={}
 for key,args,expected in [('registered20_paid10_reserve5_profit10',(0,5,20,10,True),1),('prior_loss',(-6,0,20,10,True),.4),('full',(0,10,20,10,True),0),('registration_increase',(0,5,20,10,True),1),('foreign',(0,0,None,10,False),0)]:
  v=m.legal_step(*args);assert abs(v[2]-expected)<1e-12;tests[key]=v
 for key,args in [('real_cost',(10,30.950195,42.51307794,10)),('minority',(5,20,10,5))]:
  v=m.capital_return_budget(*args,ownership=1 if key=='real_cost' else .8,friction=.02,tax_basis_ratio=0);assert v['parent_profit']!=v['parent_cash'];assert v['registered_after']==args[1]-args[3];assert v['listed_shares_change']==0;tests[key]=v
 for name,c in m.SCENARIOS.items():
  a=m.run(c);b=m.run(c,n=320);assert m.expand(m.pack(a))==a
  selected={};events=[]
  for z in a['years']:
   for e,x in z['entities'].items():
    assert abs(x['legal_income']-x['net_income']-x['upstream_declared']-x['capital_disposal_profit'])<1e-8
    assert x['declared_D']<=max(x['distribution_capacity_budget_before_D'],0)+1e-8
    assert abs(z['shares_bn']-m.SHARES)<1e-12
    if x['capital_recovery']['gross_capital_return']>1e-10:events.append({'year':z['year'],'entity':e,**x['capital_recovery']})
   if z['year'] in [5,9,13,20,43,50,100,240]:selected[z['year']]={e:{'cash':x['cash_end'],'required':x['required_cash'],'locked':x['locked_end'],'payable':x['D_payable'],'excess':x['cash_end']-x['required_cash']-x['locked_end']-x['D_payable'],'registered':x['registered_capital'],'deposit_income':x['deposit_income'],'capital_received':x['capital_return_received']} for e,x in z['entities'].items()}
  scenarios[name]={'feasible':a['feasible'],'failure':a['failure'],'PV240':a['PV'],'PV320':b['PV'],'TV240':a['TV5'],'TV320':b['TV5'],'capital_events':events,'selected_years':selected}
  if a['feasible'] and name!='structural_dividend_only':
   # All excess released; growing necessary productive capital and normal dividend float remain.
   assert max(abs(v['excess']) for v in selected[240].values())<1e-6,(name,selected[240])
 assert not scenarios['no_refinance_zero_D']['feasible'];tests['original_no_refinance_failure_preserved']=scenarios['no_refinance_zero_D']['failure']
