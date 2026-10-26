# Independent original-input reconstruction. Does not import production model.
import json
from pathlib import Path
D=Path(__file__).parent

def rebuild(release=10,margin_end=.145):
    c=[1800.,200.,200.];d=[105.006481,17.225,17.225];olddebt=d[:];u=[1700.,0.,0.];a=[370.058427,0.,0.];cap=[793.970662,50.,200.];loans=[137.30797819,354.63494228]
    wc=1430.;f=686.;r=0.;out=[];eq=4445.085799;shares=793.970662
    for t in range(1,351):
        if t<6:r=[3600,4000,4400,4800,5200][t-1];m=[.13,.15,.16,.165,.17][t-1]
        else:
            q=min((t-5)/10,1);r*=1+(5200/4800-1)*(1-q)+.02*q;m=.17*(1-q)+margin_end*q
        nw=r*.39;nf=r*.20;da=f*.12;cx=da+nf-f
        if cx<0:cx=0.;nf=f-da
        rein=cx-da+nw-wc;op=r*m*.85-rein
        interest=[x*.035*.85 for x in d];fin=[x*.018*.85 for x in c];mi=r*m*.85*.002
        np=[r*m*.85*w+fin[i]-interest[i] for i,w in enumerate([.85,.075,.075])];np[0]-=mi
        n=sum(np)
        issue=.60312 if t==1 else 0;proceeds=issue*16.8;shares+=issue;cap[0]+=issue
        for i,w in enumerate([.85,.075,.075]):
            c[i]+=op*w+fin[i]-interest[i]
            reserve=min(.1*max(np[i]-max(-u[i],0),0),max(cap[i]/2-a[i],0));a[i]+=reserve;u[i]+=np[i]-reserve
        c[0]-=mi+(62.5 if t==1 else 0)
        c[0]+=proceeds
        floors=[r*.12*w for w in [.75,.10,.15]]
        if t==1:floors[0]+=450
        p=[min(x,olddebt[i]/3) if t<=3 else 0 for i,x in enumerate(d)]
        for i in [1,2]:
            z=min(max(floors[i]+p[i]-c[i],0),max(c[0]-floors[0]-p[0],0));c[0]-=z;c[i]+=z;loans[i-1]+=z
        for i in range(3):
            z=min(max(floors[i]+p[i]-c[i],0),max([200,50,50][i]-d[i],0));c[i]+=z;d[i]+=z-p[i];c[i]-=p[i];assert c[i]+1e-7>=floors[i]
        for i in [1,2]:
            z=min(loans[i-1],max(c[i]-floors[i],0));loans[i-1]-=z;c[i]-=z;c[0]+=z
            z=min(max(u[i],0),max(c[i]-floors[i],0)) if t>=2 else 0
            u[i]-=z;c[i]-=z;c[0]+=z
            alloc=min(.1*max(z-max(-u[0],0),0),max(cap[0]/2-a[0],0));a[0]+=alloc;u[0]+=z-alloc
        target=max(n,0)*.5 if t<6 else max(n-max(rein,0),0)
        div=min(target,max(c[0]-floors[0],0),max(u[0],0));c[0]-=div;u[0]-=div
        z=min(max(c[0]-floors[0],0),max(u[0],0)) if t>=release else 0;c[0]-=z;u[0]-=z;div+=z;eq+=n+proceeds-div
        out.append({'year':t,'dps':div/shares,'cash':c[:],'legal':u[:],'equity':eq,'net_profit':n,'sales':r,'capex':cx,'working_capital':nw})
        wc=nw;f=nf
    return out

def pv(x,rate,start=0):return sum(z['dps']/(1+rate)**(z['year']-start) for z in x if z['year']>start)

import pytest,runpy
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/300627/models'
@pytest.mark.parametrize('name,release,marg',[('base',10,.145),('retained_principal_release_year15',15,.145),('terminal_margin_minus2pt_from_year6',10,.125)])
def test_huace_navigation_independent_raw_chain(name,release,marg):
 ref=json.loads((ROOT/'2026-Q3-output.json').read_text());rows=rebuild(release,marg);actual=ref['cases'][name]['rows'];assert len(rows)==len(actual)==350
 for x,y in zip(rows,actual):
  for k in ['dps','equity','net_profit','sales','capex','working_capital']:assert x[k]==pytest.approx(y[k],abs=1e-6)
  for k in ['cash','legal']:
   for l,r in zip(x[k],y[k]):assert l==pytest.approx(r,abs=1e-6)
 for rate in [.105,.1,.095]:
  assert pv(rows,rate)==pytest.approx(ref['cases'][name]['valuations'][str(rate)]['value'],abs=1e-8)
  assert pv(rows,rate,5)==pytest.approx(ref['cases'][name]['valuations'][str(rate)]['tv5'],abs=1e-8)
def test_huace_navigation_formal_functions_and_granted_awards():
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['test']()
 o=json.loads((ROOT/'2026-Q3-output.json').read_text())
 for c in ['base','structural']:
  y=o['cases'][c]['rows'][0];assert y['issued_shares']==.60312;assert y['issue_proceeds']==pytest.approx(.60312*16.8)
 a=o['cases']['base']['rows'][4];b=o['cases']['retained_principal_release_year15']['rows'][4]
 for key in ['sales','net_profit','cash','debt','legal','reserve','shares','working_capital','fixed_assets','capital']:assert a[key]==b[key]
