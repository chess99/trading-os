#!/usr/bin/env python3
"""Independent literal reconstruction: no production imports or INPUT/output-derived parameters.
Uses real cash accounts and an explicitly conditional economic transfer budget, NOT synthetic entities.
"""
import json,math,lzma,base64
from pathlib import Path
P=Path(__file__).parent
# Literal inputs read from Q3/H1 and stated forecast assumptions; monetary unit bn.
SEG=[(15.,18.5,[0,.01,.02,.02,.02,.02,.02,.015,.015,.01],[.145,.15,.155,.16,.16,.16,.1575,.155,.1525,.15],.10,.995,.06,1.,.35,.12,[.05,.05,.05,0,0,0,0,0,0,0]),(5.3,3.6,[.04,.04,.04,.03,.03,.025,.025,.02,.015,.01],[.08,.082,.085,.085,.085,.085,.083,.082,.081,.08],.15,.95,.022,1.05,.35,.45,[.1,.1,.05,.05,0,0,0,0,0,0]),(4.5,4.2,[.05,.05,.04,.04,.03,.03,.025,.02,.015,.01],[.08,.085,.09,.095,.095,.095,.0925,.09,.0875,.085],.15,.8,.04,1.,.4,.25,[.1,.1,.05,.05,0,0,0,0,0,0])]
SC={'base':{},'cyclical_weak':dict(gd=[-.08,-.03,.04,.03,.01,0,0,0,0,0],md=[-.025,-.015,-.005,0,0,0,0,0,0,0],wc=[.8,.3,-.5,-.3,-.3,0,0,0,0,0]),'structural_adverse':dict(gd=[-.06,-.05,-.04,-.03,-.02,-.02,-.02,-.015,-.015,-.01],md=[-.04]*10,wc=[.5,.3,.2,0,0,0,0,0,0,0],g=0,roic=.07),'optimistic':dict(gd=[.02]*5+[.01]*5,md=[.01]*10),'light_margin_minus_2pp':dict(light=-.02),'pool_cash_stress':dict(repay=1.5,collect=.1,oldyear=3),'full_dilution_diagnostic':dict(no_forfeit=True)}
SENS={'routing_70pct':dict(route=.7),'routing_delay3':dict(delay=3),'routing_cost3pct':dict(cost=.03),'early_half':dict(early=.5),'historic_budget_zero':dict(budget=0),'parent_tax15':dict(ptax=.15),'direct_assets_recovery70':dict(recovery=.7,salecost=.01),'foreign_routing_cost10pct':dict(cost=.003),'treasury_tax25':dict(stax=.25)}

def distribute(ret,stat,reg,earn,want,cash):
    profit=ret+earn
    charge=max(0,min(.5*reg-stat,.1*max(0,min(earn,profit))))
    paid=max(0,min(want,profit-charge,cash))
    return profit-charge-paid,stat+charge,paid,charge

def rebuild(par,r,g,N=400,matched=False):
    c=[2.8,1.23972111738];d=[1.,.90539590619];init_d=d[:]
    loanpay,loanrec,old=(10. if matched else 9.4),2.8,.159
    ret,stat,shares=2.5585150299,.8704664345,1.697823974
    priorprofit=0.;b=par.get('budget',3.);acq=.81699029771
    rev=[15.,5.3,4.5];capital=[18.5,3.6,4.2];g=par.get('g',g)
    rows=[];last_ebit=[]
    for t in range(1,N+1):
        ops=[];inv=[];growthcap=[];ebits=[];nops=[]
        for j,z in enumerate(SEG):
            _,_,growth,margin,tax,own,da,maint,fix,wc,ma=z
            before=rev[j]
            if t<=10:
                rev[j]*=1+growth[t-1]+par.get('gd',[0]*10)[t-1]
                e=rev[j]*(margin[t-1]+par.get('md',[0]*10)[t-1]+(par.get('light',0) if j==0 else 0))
                reinvest=rev[j]*da*(maint-1)+max(0,rev[j]-before)*fix+(rev[j]-before)*wc+ma[t-1]
                gc=max(0,rev[j]-before)*fix
            else:
                rev[j]*=1+g;e=last_ebit[j]*(1+g)
                n=e-max(0,e)*tax
                reinvest=n*g/par.get('roic',.10)+rev[j]*da*(maint-1);gc=n*g/par.get('roic',.10)*.6
            np=e-max(e,0)*tax;ops.append(np*own);inv.append(reinvest*own);growthcap.append(gc*own);nops.append(np);ebits.append(e);capital[j]+=reinvest
        last_ebit=ebits
        invest=sum(inv)+(par.get('wc',[0]*10)[t-1] if t<=10 else 0)+max(0,([.55,.50,.25]+[0]*7)[t-1]-sum(growthcap) if t<=10 else 0)
        intp=min(d[0],1)*.03+max(0,d[0]-1)*.035
        ints=min(d[1],.90539590619)*.03+max(0,d[1]-.90539590619)*.035
        lend=loanrec*.02*(1 if matched else 1.7/2.8)
        pool=loanpay*.02
        pp=-.1+c[0]*.02+lend-pool-intp
        tp=max(pp,0)*par.get('ptax',.25);pn=pp-tp
        sf=c[1]*.02+pool-lend-ints
        ts=((max(0,ebits[0]+sf)-max(0,ebits[0]))*.1 if matched else max(sf,0)*par.get('stax',.15))
        sn=sum(ops)+sf-ts;common=pn+sn
        c[0]+=pn;c[1]+=sn-invest
        paid=min(loanpay,par.get('repay',.5));collected=min(loanrec,par.get('collect',.3));od=old if t==par.get('oldyear',1) else 0
        c[0]+=collected-paid+od;c[1]+=paid-collected-od;loanpay-=paid;loanrec-=collected;old-=od
        ap=min(acq,([.4,.41699029771]+[0]*8)[t-1] if t<=10 else 0);acq-=ap;c[0]-=ap
        refund=.071114680725 if t<=2 and not par.get('no_forfeit') else 0
        c[0]-=refund
        if refund: shares-=.004158066
        ramp=0 if t<6+par.get('delay',0) else min(1,(t-5-par.get('delay',0))*.2)
        debts=min(d[1],max(0,c[1]-.8)*ramp);c[1]-=debts;d[1]-=debts
        b+=sn
        desired=max(0,nops[0]*.595)*par.get('early',1) if t<6+par.get('delay',0) else max(0,b)*ramp*par.get('route',1)
        u=max(0,min(desired,b,max(0,c[1]-.8)));cost=u*par.get('cost',0);received=u-cost
        b-=u;c[1]-=u;c[0]+=received;common-=cost
        realization=gain=sale_tax=0
        if t==10:
            basis=.21028120459;gross=basis*par.get('recovery',1);fee=par.get('salecost',0)
            gain=gross-fee-basis;sale_tax=max(0,gross-fee-basis)*.25
            realization=gross-fee-sale_tax;c[0]+=realization;common+=gain-sale_tax
        debtp=min(d[0],max(0,c[0]-.3)*ramp);c[0]-=debtp;d[0]-=debtp
        wish=.9 if t==1 else max(0,priorprofit*.4)
        avail=max(0,min(c[0]-.3,c[0]+c[1]-1.1))
        ret,stat,div,charge=distribute(ret,stat,shares,pn+received+gain-sale_tax,wish,avail);c[0]-=div
        special=max(0,min(ret,max(0,c[0]-.3)))*ramp if ramp else 0
        ret-=special;c[0]-=special
        new=[max(0,.3-c[0]),max(0,.8-c[1])]
        if d[0]+new[0]-1>2.5+1e-9 or d[1]+new[1]-.90539590619>1+1e-9:return {'feasible':False,'year':t}
        for i in range(2):c[i]+=new[i];d[i]+=new[i]
        rows.append(dict(year=t,parent_cash=c[0],sub_common_cash=c[1],parent_debt=d[0],sub_common_debt=d[1],shares=shares,dps=(div+special)/shares,total_dividend=div+special,common_operating_profit=sum(ops),common_reinvestment=invest,parent_own_net_profit=pn,sub_economic_net_profit=sn,common_net_profit=common,parent_finance_tax=tp,sub_finance_tax=ts,upstream_cash=received,upstream_economic_budget_balance=b,old_dividend_collection=od,pool_parent_payable=loanpay,pool_parent_receivable=loanrec,nonoperating_realization=realization,asset_accounting_gain=gain,asset_sale_tax=sale_tax,parent_retained=ret,parent_reserve=stat))
        priorprofit=common
    pv=sum(row['dps']/(1+r)**row['year'] for row in rows)
    first=sum(row['dps']/(1+r)**row['year'] for row in rows[:5])
    return dict(feasible=True,pv=pv,tv5=(pv-first)*(1+r)**5,rows=rows)


import runpy,subprocess,sys,shutil,hashlib,copy
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/000786/models'
@lru_cache(None)
def model():
 m=runpy.run_path(str(D/'2026-Q3.py'));m['INPUT']['interest_bearing_receivable_fraction']=1.7/2.8;m['INPUT']['pool_parent_payable']=9.4;return m
@lru_cache(None)
def output():
 w=json.loads((D/'2026-Q3-output.json').read_text());raw=lzma.decompress(base64.b64decode(w['payload_xz_base64']));assert hashlib.sha256(raw).hexdigest()==w['payload_sha256'];return json.loads(raw)
def test_bnbm_all_literal_400year_paths():
 own={(sec,n,ep):rebuild(par,r,g,matched=sec=='matched_budget') for sec,pars in [('scenarios',SC),('sensitivities',SENS),('matched_budget',SC)] for n,par in pars.items() for ep,r,g in [('low',.10,.005),('high',.09,.01)]}
 out=output()
 for (sec,n,ep),a in own.items():
  b=out[sec][n][ep] if sec=='scenarios' else out[sec][n]['endpoints'][ep] if sec=='sensitivities' else out[sec][n][ep]['new']
  assert a['feasible']==b['feasible']
  if a['feasible']:
   for x,y in zip(a['rows'],b['rows']):
    for k,v in x.items():
     expected=y['parent_legal']['retained'] if k=='parent_retained' else y['parent_legal']['reserve'] if k=='parent_reserve' else y[k]
     assert abs(v-expected)<1e-7*max(1,abs(expected))
   assert abs(a['pv']-b['pv'])<1e-9 and abs(a['tv5']-b['tv5'])<1e-9

def test_bnbm_actual_production_funding_loss_and_equity():
 m=model();m['actual_tests']()
 assert not m['exit_waterfall'](0,1,.5,1,2,1,.8)['feasible']
 stress=copy.deepcopy(m['INPUT']['scenarios']['base']);stress.update(pool_repayment=10,loan_collection=0)
 assert not m['simulation'](stress)['feasible']
 assert m['capital_refund'](10,10,3,3)=={'shares':7,'cash':7,'profit':0}

def test_bnbm_all_cash_cohorts_and_valuation_bridge():
 o=output()
 for v in o['scenarios'].values():
  for a in v.values():
   assert a['feasible']
   assert max(abs(z['cash_conservation_error']) for z in a['rows'])<1e-8
   assert abs(a['d5']+a['tv5']/(1+a['r'])**5-a['pv'])<1e-10
   active=[q for q in a['financial_cohorts'] if q['remaining']>1e-7]
   assert all(q['origin']>=399 for q in active)
   assert abs(sum(q['remaining'] for q in active)-1.1)<1e-6

def test_bnbm_fresh_singlefile_lossless_output(tmp_path):
 f=tmp_path/'2026-Q3.py';shutil.copy2(D/'2026-Q3.py',f)
 subprocess.run([sys.executable,str(f)],check=True,stdout=subprocess.DEVNULL)
 assert f.with_name('2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
 subprocess.run([sys.executable,str(f),'--expand'],check=True,stdout=subprocess.DEVNULL)
 assert json.loads(f.with_name('expanded-output.json').read_text())==output()
