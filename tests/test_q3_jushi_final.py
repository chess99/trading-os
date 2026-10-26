import copy,json,math,runpy,subprocess,sys
from pathlib import Path
from functools import lru_cache
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN/600176/models"
def independently_rebuild(which,years=240):
    """Literal re-entry and ledger reconstruction; no production functions/data read."""
    specs=[('JJ','G',1,.16,.16,.2,.6,.85,.383241303),('CD','G',1,.10,.13,.15,.8,2,0),
      ('HA','G',1,.20,.34,.25,2.3,5.3,1.204223357),('EG','G',.7501,.08,.07,.25,.8,1,0),
      ('US','P',.70,.04,.04,.1,.15,.3,0),('W','Z',.80,.01,.01,.059480663,.128548324,.228548324,.361010719),
      ('L','Z',1,0,0,.03,0,1.5,0),('Z','P',1,0,0,0,0,.05,0),('G','P',1,.4,.25,.42,3.15,4,1.317516638),
      ('P',None,1,.01,0,.8,6.9,8.1,0)]
    # Independent scenario literals, deliberately not taken from SCENARIOS.
    cases={'base':(1,1.,0.,1.,1.,.03,.15,0.,.1,3,.05),
      'margin_minus_2pp':(2,1.,-.02,1.,1.,.03,.15,0.,.1,3,.05),
      'long_upstream_delay':(1,1.,0.,1.,1.,.03,.4,0.,.25,5,.05),
      'structural':(2,.9,-.075,1.,1.08,.045,.2,.3,.1,3,.05),
      'cycle':(1,1.,0.,1.,1.,.04,.25,.6,.1,3,.05),
      'upside':(2,1.08,.02,1.1,1.12,.03,.15,0.,.1,3,.05),
      'capex_plus_20pct':(1,1.,0.,1.,1.2,.03,.15,0.,.1,3,.05),
      'foreign_friction':(1,1.,0.,1.,1.,.03,.15,0.,.1,5,.15)}
    start,rf,ms,gf,cf,rate,lag,wc,hf,hy,wt=cases[which]
    z={n:dict(cash=c,debt=d,limit=l,loan=b,capital=4.003136728 if n=='P' else 0.,
      reserve=1.33955207603 if n=='P' else 0.,retained=.13953489229 if n=='P' else 0.,
      payable=.65 if n=='G' else 0.,dividend_receivable=.65 if n=='P' else 0.,held=[],surplus_age=0,
      shares=4.003136728 if n=='P' else 1.,excess_basis=0.,investment_cost=10.46536040559 if n=='P' else 0.)
      for n,u,f,p,cw,c,d,l,b in specs}
    records=[];distributions=[];last=24.
    for t in range(1,years+1):
        if t<=5:
            sales=(24.81,24.565,25.67,27.05,28.4)[t-1];mar=(.29,.26,.25,.25,.25)[t-1]
            depreciation=2.8+.15*(t-1);spend=(7.5,6.5,5.,4.2,4.3)[t-1]
        else:
            changes=(1.04,1.035,1.03,1.025,1.02)
            sales=28.4*math.prod(changes[:min(5,t-5)])*1.015**max(0,t-10)
            mar=.25-.004*min(5,t-5);depreciation=3.4*sales/28.4
            spend=depreciation+1.6*sales*(1-1/(changes[t-6] if t<=10 else 1.015))
        if t>=start:
            sales*=rf;mar+=ms;spend*=cf
            if t>5:sales*=gf**min(1,(t-5)/5)
        if which=='cycle' and t<=3:sales*=(.88,.92,.96)[t-1];mar-=(.09,.07,.04)[t-1]
        networking=(sales-last)/5+({1:1.,2:-.4,3:-.3}.get(t,0.));shock=wc*((t==start)-(t==start+2))
        accrued={n:0. for n in z};received=accrued.copy();capital_cash=accrued.copy()
        interinterest=sum(v['loan'] for v in z.values())/40;loanreturn=0.;earn=0.;row={};cashout=0.
        for idx,(n,u,share,pw,cw,*_) in enumerate(specs):
            old=z[n];rw=.41 if n=='G' else 0 if n=='P' else pw
            floor=(.45 if n=='P' else .02 if n in ('L','Z') else 1.35*rw)*sales/24
            grid={1:(.6,1.2,3.,.3,.2,.1,.9,0,1.2,0),2:(.55,1.,2.4,.3,.2,.1,.82449,0,1.12551,0),3:(.55,.8,1.65,.3,.2,.1,.1,0,1.3,0)}
            capitalspend=grid[t][idx]*spend/(7.5,6.5,5)[t-1] if t<4 else spend*(.025 if n=='L' else cw-(.025 if n=='G' else 0))
            wind=.13*sales/24-sales*mar*.01
            lp=(.02,.12,.22,.24,.25)[t-1] if t<6 else .25*sales/28.4
            ld=(.01,.05,.09,.1,.1)[t-1] if t<6 else .1*sales/28.4
            eb=sales*mar*pw+(wind if n=='W' else -wind if n=='G' else 0)+(lp if n=='L' else -lp if n=='G' else 0)
            dd=depreciation*cw+(ld if n=='L' else -ld if n=='G' else 0)
            pretax=eb+old['cash']*.012+(interinterest if n=='P' else 0)-old['debt']*(rate if t>=start else .03)-old['loan']*.025
            net=pretax-.18*max(pretax,0)+(.1*sales/24 if n=='P' else 0)
            capacity=net+accrued[n]+old['retained'];held=[(age-1,v) for age,v in old['held'] if age>1]
            if n=='P':
                provision=min(max(0.,old['capital']/2-old['reserve']),max(0.,net+accrued[n]+min(old['retained'],0))/10)
                capacity-=provision;usable=max(0,capacity)
            else:
                provision=0.;held.append((hy,hf*max(0,net+accrued[n]+min(old['retained'],0))))
                usable=max(0,capacity-sum(v for age,v in held))
            transfer=.3 if t==1 else .2 if t==2 else 0
            add=transfer if n in ('L','Z') else 0;deduct=transfer if n in ('P','Z') else 0
            money=old['cash']+net+dd-capitalspend-networking*rw-(shock if n=='P' else 0)+received[n]+(loanreturn if n=='P' else 0)-old['payable']+add-deduct+capital_cash[n]
            borrowing=min(max(0,floor-money),max(0,old['limit']-old['debt']));money+=borrowing
            if money<floor-1e-10:return dict(feasible=False,failed_year=t,failed_node=n)
            lpay=min(old['loan'],.1*max(0,money-floor));money-=lpay
            amort=min(old['debt']+borrowing,.25*max(0,money-floor));money-=amort
            target=max(0,earn)*(.45 if t<=5 else .7 if t<=10 else 1) if n=='P' else 1e9
            regular=min(usable,max(0,money-floor),target);extra=min(max(0,usable-regular),max(0,money-floor-regular)) if t>=6 else 0
            declared=regular+extra;deferred=0 if n=='P' else lag if t>=start else .15
            newpaid=declared*(1-deferred);payable=declared*deferred;money-=newpaid
            excess=max(0,money-floor-payable);age=old['surplus_age']+1 if excess>1e-9 else 0
            reduction=0.;fee=0.;capital=old['capital'];shares=old['shares'];basis=old['excess_basis']
            if age>=3 and excess>0 and (n=='P' or basis>0):
                blocked=max(0,excess-max(0,capacity-declared)) if n=='P' else min(excess,basis)
                reduction=min(blocked,capital*.95 if n=='P' else basis)/1.02;fee=.02*reduction
                money-=reduction+fee;capacity-=fee
                if n=='P' and reduction:shares*=1-reduction/capital;capital-=reduction
                if n!='P':basis-=reduction+fee
            if n=='P' and declared>max(0,capacity)+1e-10:
                undo=declared-max(0,capacity);declared-=undo;money+=undo*(1-deferred);payable=declared*deferred;newpaid=declared-payable
            z[n]=dict(cash=money,debt=old['debt']+borrowing-amort,limit=old['limit'],loan=old['loan']-lpay,
              capital=capital,reserve=old['reserve']+provision,retained=capacity-declared,
              payable=payable,dividend_receivable=old['dividend_receivable']+accrued[n]-received[n],held=held,
              surplus_age=age,shares=shares,excess_basis=basis,investment_cost=old['investment_cost']+deduct-capital_cash[n])
            earn+=(net-fee)*share;loanreturn+=lpay
            if u:
                factor=share*(1-wt if n in ('EG','US') else 1)
                accrued[u]+=declared*factor;received[u]+=(old['payable']+newpaid)*factor;capital_cash[u]+=reduction*share
            else:cashout=(old['payable']+newpaid+reduction)/4.003136728
            row[n]=copy.deepcopy(z[n])
        records.append(dict(year=t,states=row,distribution_per_share=cashout));distributions.append(cashout);last=sales
    return dict(feasible=True,trace=records,distributions=distributions,
      value_low=sum(v/1.1025**(t+1) for t,v in enumerate(distributions)),
      value_high=sum(v/1.09**(t+1) for t,v in enumerate(distributions)),
      terminal_y5_low=sum(v/1.1025**(t+1) for t,v in enumerate(distributions[5:])),
      terminal_y5_high=sum(v/1.09**(t+1) for t,v in enumerate(distributions[5:])))
@lru_cache(None)
def model():return runpy.run_path(str(ROOT/'2026-Q3.py'))
@lru_cache(None)
def output():return model()['expand_output'](json.loads((ROOT/'2026-Q3-output.json').read_text()))
def test_jushi_independent_full_paths():
 m=model()
 for name in ['base','margin_minus_2pp','long_upstream_delay','cycle','structural','upside','capex_plus_20pct','foreign_friction']:
  q=independently_rebuild(name);p=m['run'](m['SCENARIOS'][name]);assert q['feasible']==p['feasible']
  for a,b in zip(q['trace'],p['trace']):
   assert abs(a['distribution_per_share']-b['distribution_per_share'])<1e-7
   for n,v in a['states'].items():
    for k,z in v.items():
     zz=b['nodes'][n]['end'][k]
     if isinstance(z,(float,int)):assert math.isclose(z,zz,rel_tol=1e-10,abs_tol=1e-7),(name,a['year'],n,k,z,zz)
  for k in ['value_low','value_high','terminal_y5_low','terminal_y5_high']:assert abs(q[k]-m['valuation'](p)[k])<1e-8

def test_jushi_actual_legal_capital_fee_and_creditors():
 m=model();m['tests']()
 for n in ['unfundable','capital_return_fee_shortfall']:
  p=m['run'](m['SCENARIOS'][n]);assert not p['feasible'] and p['value'] is None and p['shortfall']>0
 assert m['legal_step'](-3,5,20,10)==(6.3,5.7,.7000000000000001)

def test_jushi_total_tail_and_incremental():
 m=model();checks=[]
 for name in ['base','structural','long_upstream_delay','foreign_friction']:
  p=m['run'](m['SCENARIOS'][name],years=320)
  assert p['feasible']
  for y in [80,160,320]:
   row=p['trace'][y-1]
   for n,x in row['nodes'].items():
    # Current declarations in transit and explicit finite held-capacity are not idle unpriced cash.
    extra=max(0,x['end']['cash']-x['minimum']-x['end']['payable'])
    checks.append((name,y,n,extra,sum(v for _,v in x['end']['held'])))
  for y in [40,120]:
   state=copy.deepcopy(p['trace'][y-1]['nodes']);states={n:x['end'] for n,x in state.items()}
   for n in ['P','G','EG']:
    changed=copy.deepcopy(states);changed[n]['cash']+=.1
    a=m['run'](m['SCENARIOS'][name],years=y+30,start_state=states,start_y=y+1,prior_revenue=p['trace'][y-1]['operating']['revenue'])
    b=m['run'](m['SCENARIOS'][name],years=y+30,start_state=changed,start_y=y+1,prior_revenue=p['trace'][y-1]['operating']['revenue'])
    assert a['feasible'] and b['feasible']
    residual=sum(b['closing_state'][k]['cash']-a['closing_state'][k]['cash'] for k in states)
    assert abs(residual)<.001,(name,y,n,residual)
 return checks

def test_jushi_standalone_regeneration(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((ROOT/'2026-Q3.py').read_bytes())
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(ROOT/'2026-Q3-output.json').read_bytes()
 p=subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py'),'--expand',str(tmp_path/'2026-Q3-output.json')],capture_output=True,check=True)
 assert json.loads(p.stdout)==output()
