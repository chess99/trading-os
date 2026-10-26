#!/usr/bin/env python3
"""Independent literal base reconstruction. No import/exec of production, no use of its inputs or rows as answers."""
import json,math
from pathlib import Path
S=401.702919
HB=[3250,3350,3350,3300,3200,3100,3000,2900,2800,2700]
GH=[800,1050,1300,1500,1650,1800,1930,2050,2150,2220]
OT=[320,350,380,400,420,440,455,465,470,470]
NW=[0,0,0,100,300,450,600,700,750,780]
RD=[500,540,580,620,650,680,700,710,710,710]
MI=[80,100,160,150,120,100,80,60,50,50]
CA=[520,470,400,330,300,300,300,300,300,300]
DA=[145,165,185,210,235,255,275,290,300,300]
GR=[.887,.883,.878,.873,.868,.863,.858,.853,.85,.85]
SE=[.355,.35,.345,.34,.335,.335,.335,.335,.335,.335]
RE=[90,100,110,120,130,135,140,140,140,140]
def literal(gh=1.):
 p,b,z=2005.2855085,195.,40.;pc,bc=1950.,500.;pres,bres=204.09474000,0.
 debt=795.74141896;bond=1533.266;nwc=1471.73526582;earmark=1400.;due={};rows=[];fixed=1396.94379801;bnew=0.;hnew=0.
 for year in range(1,41):
  t=min(year-1,9);f=.98**max(year-10,0)
  h,g,o,n=HB[t]*f,GH[t]*f*gh,OT[t]*f,NW[t]*f
  rev=h+g+o+n;ce,da=CA[t]*f,DA[t]*f;research=RE[t]*f
  retired=fixed*.02 if year>10 else 0.;sale=retired*.35;planned_da=da;da=min(da,max(0.,fixed+ce-retired))
  fixed=max(0.,fixed+ce-da-retired)
  eb=rev*(GR[t]-SE[t]-.085-.018)-RD[t]*f-MI[t]*f-.08*n+planned_da-da
  be=(h+g)*(.06 if year==1 else .045 if year==2 else .03)*.8
  coupon=bond*[.001,.003,.006,.01,.015][year-1] if year<6 else 0
  premium=bond*.08 if year==6 else 0;redemption=bond*1.08 if year==6 else 0
  pt=eb-be+research+.012*p-.035*debt-coupon-premium;bt=be+.012*b;zt=-research+.012*z
  pp=pt-.15*max(pt,0);bp=bt-.15*max(bt,0);zp=zt-.25*max(zt,0)
  pp-=.9*(retired-sale);bp-=.05*(retired-sale);zp-=.05*(retired-sale)
  change=rev*.34-nwc;nwc=rev*.34
  p+=pp+.9*(da-ce+retired)-change+premium;b+=bp+.05*(da-ce+retired);z+=zp+.05*(da-ce+retired)
  if year==1:p+=167.18274496
  rep=min(debt,150) if 2<=year<=7 else 0;debt-=rep;p-=rep+redemption
  if year==6:bond=0
  if year==2:b-=31.49177387
  if year==8:p+=161.65239399
  if year<=4:p-=80;b+=80
  receipt=due.pop(year,0);p+=receipt;b-=receipt
  support=max(0,20*f-z);z+=support;b-=support*.75;p-=support*.25;hnew+=support*.25
  reserve_pending=sum(due.values());topup=max(0,30*f+reserve_pending-b);p-=topup;b+=topup;bnew+=topup
  earmark=max(0,earmark-min(earmark,.65*ce+.2*RD[t]*f))
  floor=max(250*.98**max(0,year-20),rev*.1)+earmark
  draw=max(0,floor-p)
  assert draw<=1100-debt+1e-7
  debt+=draw;p+=draw;extra=draw*.035/2;p-=extra;pp-=extra
  consumption=max(0,-zp)
  bnet=bp-.75*consumption
  ba=min(max(0,21-bres),.1*max(0,bnet+min(0,bc)));bres+=ba;bc+=bnet-ba
  target=.6*max(0,bnet)
  if 5<year<=20:target+=.25*max(0,b-30*f-reserve_pending)
  if year>=15:target=max(0,b-30*f-reserve_pending)
  declaration=min(max(0,bc),max(0,b-30*f-reserve_pending),target);bc-=declaration;due[year+1]=declaration
  pnet=pp+declaration-.25*consumption-topup
  pa=min(max(0,206.262004-pres),.1*max(0,pnet+min(0,pc)));pres+=pa;pc+=pnet-pa
  gp=pp+bp+zp
  target=.3*max(0,gp) if year<=5 else .7*max(0,gp)+.25*max(0,p-floor)
  if 20<year<23:target=.7*max(0,gp)
  if year>=12:target=max(0,p-floor)
  div=min(target,max(0,p-floor),max(0,pc));p-=div;pc-=div
  # No capital reductions occur on these two paths; assert capacity never binds excess.
  assert not (pc<1e-6 and p>floor+1e-6)
  if year==40:
   liability=.11*rev;gross_wc=nwc+liability;realization=.85*gross_wc+.50*fixed
   before=p+b+z+realization-(.03*realization+25)-liability-debt-bond*1.08
   beq=min(before,max(0,b+.75*z+.0875*fixed*.5));heq=min(before-beq,max(0,.25*z+.0125*fixed*.5))
   investment_tax=.25*max(0,beq-47.56511718-bnew)+.25*max(0,heq-62.33956437-hnew)
   div+=(before-investment_tax)*.95
   p=b=z=0.
  rows.append({'year':year,'P':p,'B':b,'R':z,'pc':pc,'bc':bc,'dps':div/S})
 return rows


import runpy,subprocess,sys,shutil,copy
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/688278/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():return json.loads((D/'2026-Q3-output.json').read_text())
def test_amoytop_literal_full_cash_path():
 computed={'base':literal(),'GH_minus20':literal(.8)}
 d=output()
 for name,rows in computed.items():
  actual=d['runs']['base'] if name=='base' else d['sensitivities'][name]['run']
  for x,y in zip(rows,actual['rows']):
   for k in ['P','B','R']:assert abs(x[k]-y['cash_close'][k])<1e-7
   for k,j in [('pc','P'),('bc','B')]:assert abs(x[k]-y['capacity_budget'][j])<1e-7
   assert abs(x['dps']-y['dps'])<1e-9
  for r in [.10,.115]:
   got=model()['value'](actual,r)
   assert abs(sum(x['dps']/(1+r)**x['year'] for x in rows)-got['value'])<1e-9
   assert abs(sum(x['dps']/(1+r)**(x['year']-5) for x in rows if x['year']>5)-got['tv5'])<1e-9

def test_amoytop_actual_losses_reserve_and_creditors():
 m=model(); m['checks']()
 assert m['legal_profit'](-10,0,20,6)==(-4,0,0)
 assert m['legal_profit'](-4,0,20,14)==(9,1,1)
 for fees,assets,debt in [(5,0,0),(0,50,60)]:
  r=m['liquidation'](assets,0,1,debt,10,1,20,fees=fees)
  assert not r['feasible'] and r['shares_cancelled_fraction']==0 and r['parent_cash']==0
 for name in ['base','cyclical','optimistic']:
  c=copy.deepcopy(m['VARIANTS'][name]);c.update(p_release_year=12,b_release_year=15,capital_release=True,retire_idle_assets=True,exit_year=40,working_recovery=0.,fixed_recovery=0.)
  r=m['simulate'](c)
  assert not r['feasible'] and m['value'](r,.1075)['value'] is None
  assert r['failure']['remaining_legal_shares']>0 and not r['failure']['shares_cancelled_by_exit']

def test_amoytop_all_actual_cash_and_original_holder():
 d=output()
 for r in list(d['runs'].values())+[x['run'] for x in d['sensitivities'].values()]:
  if not r['feasible']:continue
  for z in r['rows']:
   assert abs(z['cash_conservation_error'])<1e-6
   assert min(z['cash_close'].values())>=-1e-7
   assert abs(z['dps']*r['shares']-z['common_dividend']-z['capital_return']-z['exit_distribution'])<1e-6
   if z['remaining_legal_shares']:assert abs(z['holder_units']/z['remaining_legal_shares']-1/r['shares'])<1e-10
  z=r['rows'][-1];assert sum(z['cash_close'].values())==0 and z['holder_units']==0

def test_amoytop_single_file_fresh_reproduction(tmp_path):
 f=tmp_path/'2026-Q3.py';shutil.copy2(D/'2026-Q3.py',f)
 subprocess.run([sys.executable,str(f)],check=True,stdout=subprocess.DEVNULL)
 assert f.with_name('2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
