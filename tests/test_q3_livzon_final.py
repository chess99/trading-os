"""Literal independent rebuild. No production import/constants/row reuse in calculation."""
import json
from pathlib import Path

def literal(r,g,roic,structural=False,bio_gross=None,bio_creditors=.33158314088):
    own=[1,1,.51,.906443,.47425,.6787,.6752]
    c=[3.8,1.1,.45,.75,.2,7.14989826687-.65273064722-6.3,0.]
    b=[.6,.35,.12,.25,.08,.10,0.]
    weights=[.03,.45,.12,.27,.04,.09,0.]
    p=[[-.06,-.06,-.055,-.05,-.05],[1.05,1.10,1.16,1.22,1.28],[.6,.61,.625,.64,.66],[.52,.55,.575,.6,.63],[.09,.095,.10,.11,.12],[.04,.05,.06,.07,.08],[-.18,-.16,-.13,-.10,-.07]]
    debt=[0,1.7795019,0,.60,0,.18441458806,.8204981];initial=debt[:]
    cap=[6.73840844216,.25,.2,0,.2,.1,-3.]
    group=11.85092911057;reserve=.47711529203
    loan=2.;bio_loan=0.;fund=0.;asset=3.1
    bio_basis=2.45223079315;bio_exit=9 if structural else 10
    bio_gross=(.3 if structural else .45) if bio_gross is None else bio_gross
    f=[.70,.65,.62,.60,.60] if structural else [1]*5
    ex=[.12,.12,.08,.06,.04] if structural else [0]*5
    bills=[.45,.35,.20,.10,0] if structural else [.20,.15,.10,0,0]
    losses=[-.25,-.25,-.25,-.22,-.20] if structural else [-.18,-.16,-.13,-.10,-.07]
    releases={8:.65,9:.65,10:.65,11:.575,12:.575}
    delay=5 if structural else 0
    div=[];records=[]
    for y in range(1,241):
        scale=(1+g)**max(0,y-5);buf=[v*scale for v in b]
        if y<=5:
            op=[v[y-1]*f[y-1] if v[y-1]>0 else v[y-1] for v in p];op[6]=losses[y-1]
            inv=[.31,.33,.35,.38,.40][y-1]+ex[y-1]
        else:
            op=[v[-1]*f[-1]*scale if v[-1]>0 else v[-1]*scale for v in p]
            op[6]=(-.025 if y==6 else 0) if structural else (-.05 if y==6 else -.025 if y==7 else 0)
            inv=sum(own[i]*max(0,v) for i,v in enumerate(op))*g/roic/max(.8,sum(a*w for a,w in zip(own,weights)))
        op=[v+c[i]*.01 for i,v in enumerate(op)]
        c=[a+v-inv*w for a,v,w in zip(c,op,weights)]
        internal=loan*.02;c[0]-=internal;c[1]+=internal;op[0]-=internal;op[1]+=internal
        tax=internal*.25;c[1]-=tax;op[1]-=tax
        repayment=min(loan,max(0,c[0]-buf[0])) if y>=6 else 0
        c[0]-=repayment;c[1]+=repayment;loan-=repayment
        for i in range(7):
            if i==6:
                interest=debt[i]*.03;pay=min(debt[i],initial[i]/8)
                c[0]-=interest+pay;op[6]-=interest;bio_loan+=interest+pay;debt[i]-=pay
                continue
            interest=debt[i]*.03;c[i]-=interest;op[i]-=interest
            pay=min(debt[i],initial[i]/8,max(0,c[i]-buf[i]));c[i]-=pay;debt[i]-=pay
        carry=.005 if (6 if structural else 7)<y<bio_exit else 0
        c[0]-=carry;op[6]-=carry;bio_loan+=carry
        income=asset*.02;op[0]+=income;c[0]+=income
        proceeds=releases.get(y-delay,0);asset-=proceeds;c[0]+=proceeds
        op[0]+=proceeds-proceeds*3.391/3.1
        if y<=5:c[0]-=bills[y-1]
        if y==1:c[0]-=.1066958
        injection=max(.48 if y==1 else 0,max(0,-c[6]));fund+=injection
        assert fund<=1.2+1e-8
        c[0]-=injection;c[6]+=injection
        subscription=.48 if y==1 else 0
        bio_basis+=subscription;bio_loan+=injection-subscription
        bp=min(bio_loan,max(0,c[6])) if y>5 else 0;c[6]-=bp;c[0]+=bp;bio_loan-=bp
        impairment=0.
        if y==bio_exit:
            fee=bio_gross*.05
            gain=bio_gross-fee-.52860906544;tax=max(0,gain)*.25
            net=bio_gross-fee-tax-bio_creditors+c[6]
            rec=min(bio_loan,max(0,net));eq=max(0,net-rec)
            common=rec+eq*.6752-max(0,-net)
            impairment=bio_loan-rec+bio_basis-eq*.6752+max(0,-net)
            op[0]-=impairment;op[6]+=gain-tax
            c[0]+=common;c[6]=0.;bio_loan=0.;bio_basis=0.
        eligible=max(0,min(op[0],cap[0]+op[0]));add=min(eligible*.1,max(0,.887907171*.5-reserve));reserve+=add
        cap=[a+v for a,v in zip(cap,op)];cap[0]-=add
        gp=sum(a*v for a,v in zip(own,op))+impairment;fees=0;up=0
        for i in range(1,7):
            desired=max(0,op[i])*.8 if y<=5 else max(0,c[i]-buf[i])
            declared=min(desired,max(0,cap[i]))
            offset=min(.20,loan,declared) if i==1 and y<=5 else 0
            paid=min(max(0,declared-offset),max(0,c[i]-buf[i]));declared=paid+offset
            cap[i]-=declared;c[i]-=paid
            fee=paid*own[i]*.05 if i==5 else 0;fees+=fee
            received=paid*own[i]-fee;c[0]+=received;up+=received;cap[0]+=declared*own[i]-fee;loan-=offset
        post=min(loan,max(0,c[0]-buf[0])) if y>=6 else 0;c[0]-=post;c[1]+=post;loan-=post
        group+=gp-fees
        demand=.887907171*[2.1,1.5,1.6,1.7,1.8][y-1] if y<=5 else max(0,c[0]-buf[0])
        if min(c)<0:demand=0
        d=min(demand,max(0,cap[0]),max(0,group),max(0,c[0]-buf[0]));c[0]-=d;cap[0]-=d;group-=d;div.append(d)
        assert min(c)>-1e-8
        records.append({'year':y,'d':d,'cash':c[:],'parent_ret':cap[0],'group_ret':group,'capacity':cap[:],'debt':debt[:],'loan':loan,'up':up})
    residual=div[-1]*(1+g)/(r-g)
    pv=(sum(v/(1+r)**(i+1) for i,v in enumerate(div))+residual/(1+r)**240)/.887907171
    tv=(sum(div[y-1]/(1+r)**(y-5) for y in range(6,241))+residual/(1+r)**235)/.887907171
    return dict(pv=pv,tv=tv,rows=records)


import runpy,subprocess,sys,shutil
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/000513/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():return model()['expand_output'](json.loads((D/'2026-Q3-output.json').read_text()))
def test_livzon_literal_seven_240year_paths():
 o=output()
 for k,args in {'core_low':(.102,.015,.12),'core_high':(.092,.02,.15),'base':(.0975,.0175,.135),'r_plus1pct':(.1075,.0175,.135),'structural':(.0975,0,.085,True),'bio_low_recovery':(.0975,.0175,.135,False,.30,.50),'bio_high_recovery':(.0975,.0175,.135,False,.65,.20)}.items():
  v=literal(*args);p=o[k];assert abs(v['pv']-p['value_per_share'])<1e-9;assert abs(v['tv']-p['tv5_per_share'])<1e-9
  for a,b in zip(v['rows'],p['rows']):assert abs(a['d']-b['parent_distribution'])<1e-8;assert abs(sum(a['cash'])-b['group_cash'])<1e-8

def test_livzon_actual_legal_and_asset_functions():
 m=model();f=m['statutory'];assert f(0,10,20,5)==(9,6,1,0);assert f(-6,10,20,0)==(3.6,.4,.4,0);assert f(0,10,20,10)==(10,10,0,0)
 assert m['settle_receivable'](0,0,10,6)==(6,0,4)
 z=m['capital_realization'](10,10,1,.25,.5,100,.1);assert z['cash']==4.5 and z['profit']==-.5 and z['tax']==0 and z['shares']==90
 z=m['bio_realize'](3,0,4,3,8,.5,10);assert z['shortfall_support']==1 and z['loan_repaid']==z['equity_parent']==0 and z['parent_legal_loss']==12

def test_livzon_all_cash_bio_priority_and_future_capital():
 m=model();o=output();m['tests']()
 assert len(o['case_inputs'])==27 and o['bio_unfunded_platform_creditor_stress']['feasible'] is False
 b=o['base']['bio_exit_record'];assert b['other_creditors']>0 and b['loan_repaid']>0 and b['equity_parent']==0
 assert abs(o['base']['bio_subscription_cumulative']-.48)<1e-9
 assert o['structural']['bio_exit_record']['shortfall_support']>0
 for name in o['case_inputs']:
  # Calls formal trajectory assertions over every original scenario, not output self-equality alone.
  x=m['run'](**o['case_inputs'][name]);assert x==o[name]

def test_livzon_single_file_lossless_fresh(tmp_path):
 m=model();o=output();assert m['expand_output'](m['pack_output'](o))==o
 shutil.copy2(D/'2026-Q3.py',tmp_path/'2026-Q3.py');subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py')],check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
