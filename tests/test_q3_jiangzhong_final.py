"""Literal independent cash ledger. No production module/parameters read until every calculation is finished."""
import json,math,gzip,base64,hashlib
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'research/companies/CN/600750/models'

def calculate(r=.095,g=.0175,roi=.16,struct=False,cyc=False,renew=True,maturity=20,jreal=.7,weak_year=10,weakreal=.7,basis=1.,keep=False,release=6,startdiv=3,all51=False,turn=False,refund=False,fin=-0.,capital=True,zero=False,pstart=12,pevery=5,pfee=.02,fundyear=8,keepuntil=10000,batches=False):
 cash=[2866.57870486-170+fin,100,20,1,30,10,4,5];u=[2200,100,100,0,350,140,10,50];k=[635.588289,None,122.45,12.0155,148.5121,31.0204,51,None];z=[635.588289/2,None,0,0,0,0,0,None]
 if zero:u=[2200,0,0,0,0,0,0,0]
 book=[0,0,217.02661589,51.30202294,223.44370736,86.11996148,70.78393,0];tb=[0,0,122.45*.51,12.0155*.51,148.5121*.51,31.0204*.51,51*.70,0]
 nb=[0,0,459.34,35.71,728.94,229.88,85.27,0];q=[1,1,.51,.51,.51,.51,.51 if all51 else .70,1];receiver=[0,0,0,0,0,0,0,4];alive=[True]*8
 debt=163.21408;fund=128.83038187;f=1.;shares=635.588289;units=1.;premium=0.;rows=[];ds=[]
 if struct:g=0.;roi=.095
 growth=[-.15,-.07,-.03,0,0] if struct else [-.12,0,.08,.06,.03] if cyc else [0,.025,.03,.03,.025]
 margin=.8 if struct else .95 if cyc else 1.;div=[.5,.5,.55,.6,.6] if struct else [.7,.8,.95,1.05,1.1] if cyc else [.95,1,1.05,1.1,1.15]
 for year in range(1,301):
  f*=1+(growth[year-1] if year<=5 else g)
  orig_rate=[.15,.25,.25,.25,.25,.15,.25,.25];rate=orig_rate[:] if renew else [.25,.25,.25,.25,.25,.25,.25,.25]
  source=[560,20,20,0,110 if turn else 120,70,10 if turn else 0,30]
  ebit=[source[i]/(1-orig_rate[i])*f*margin if alive[i] else 0 for i in range(8)]
  nopat=[ebit[i]-max(ebit[i],0)*rate[i] for i in range(8)]
  if year<=5:
   pc=[120,120,110,105,105][year-1];nc=[150,140,125,115,115][year-1];jcap=[40,35,30,25,20][year-1];rem=nc-jcap-3-13
   capex=[pc-10,10,jcap,.5,rem-5,13,2.5,5];da=[80,10,40,.5,20,8,1.5,5]
   extra=120 if struct and year==1 else 80 if cyc and year==1 else -40 if cyc and year in (3,4) else 0
   w=[a*([15,15,16,17,17][year-1]+extra) for a in [.58,.02,.08,0,.20,.08,0,.04]]
  else:
   da=[a*f for a in [80,10,40,.5,20,8,1.5,5]];capex=[da[i]+max(nopat[i],0)*g/roi for i in range(8)];w=[0]*8
  for i in range(8):
   if not alive[i]:da[i]=capex[i]=w[i]=0
  floor=[900 if year<=5 else 300,20,20,1,70,30,3,6]
  for i in range(8):
   if not alive[i]:floor[i]=0
  ext_interest=0
  if year==1:
   cash[0]-=400;cash[4]+=250;cash[5]+=140;cash[6]+=10
   cash[0]-=300;cash[2]+=300;debt+=300
   cash[2]-=163.21408;cash[0]+=163.21408;debt-=163.21408
   cash[2]-=156.78592;cash[0]-=10.04907838;cash[0]-=24;fund+=24;ext_interest=60.04907838*.03
  if year==2:cash[0]-=50;ext_interest=1.5
  interest=[a*.015 if alive[i] else 0 for i,a in enumerate(cash)]
  il=debt*.03 if alive[2] else 0;charges=[-il+ext_interest,0,il,0,0,0,0,0]
  d_tax=[(max(ebit[i]+interest[i]/(1-rate[i])-charges[i],0)-max(ebit[i]+interest[i]/(1-rate[i]),0))*rate[i] for i in range(8)]
  own=[nopat[i]+interest[i]-charges[i]-d_tax[i] for i in range(8)]
  for i in range(8):cash[i]+=own[i]+da[i]-capex[i]-w[i]
  for i in (2,3,4,5,6):nb[i]+=own[i]
  top=max(floor[2]-cash[2],0) if alive[2] else 0
  assert debt+top<=450+1e-8 and cash[0]-top>=floor[0]-1e-8
  debt+=top;cash[0]-=top;cash[2]+=top
  pay=min(debt,max(cash[2]-floor[2],0)) if year>=release else 0;debt-=pay;cash[2]-=pay;cash[0]+=pay
  if alive[2] and year==maturity and debt>1e-8:
   outside=227.43*f;noncash=max(nb[2]+debt+outside-cash[2],0);total=cash[2]+noncash*jreal-outside;credit=min(debt,total);equity=max(total-credit,0);receipt=q[2]*equity;loss=debt-credit
   tax=(max(ebit[0]+max(receipt-tb[2]*basis,0),0)-max(ebit[0],0))*rate[0]
   cash[0]+=credit+receipt-tax;own[0]+=receipt-book[2]-loss-tax;cash[2]=u[2]=z[2]=k[2]=book[2]=tb[2]=nb[2]=0;floor[2]=0;alive[2]=False;debt=0
  for i in (3,6):
   if alive[i] and year==weak_year and nopat[i]<nb[i]*.05:
    outside=({3:6.90,6:24.60}[i])*f;other=max(nb[i]+outside-cash[i],0);gross=cash[i]+other*weakreal-outside;recv=gross*q[i];tax=max(recv-tb[i]*basis,0)*rate[0]
    cash[0]+=recv-tax;own[0]+=recv-book[i]-tax;cash[i]=u[i]=z[i]=k[i]=book[i]=tb[i]=nb[i]=0;alive[i]=False;floor[i]=0
  if batches:
   releasecash=min(fund,152.83038187*{8:.3,40:.3,80:.4}.get(year,0));cash[0]+=releasecash;fund-=releasecash
  elif year==max(fundyear,release):cash[0]+=fund;fund=0
  totalprofit=own[:]
  def reserve(i):
   if k[i] is None:u[i]+=totalprofit[i];return
   eligible=max(totalprofit[i]-max(-u[i],0),0);a=eligible*.1 if keep and year<=keepuntil else min(eligible*.1,max(k[i]/2-z[i],0));z[i]+=a;u[i]+=totalprofit[i]-a
  for i in (7,1,2,3,4,5,6):
   if not alive[i]:continue
   if capital and i in (2,3,4,5,6) and (i!=2 or debt<1e-8) and year>=12 and (year-12)%5==0:
    original=[635.588289,None,122.45,12.0155,148.5121,31.0204,51,None]
    gross=min(max(cash[i]-floor[i]-max(u[i]+totalprofit[i],0),0),max(k[i]-original[i]*.1,0))
    if gross>=1:
     fee=.02*gross;fraction=gross/k[i];b=book[i]*fraction;rawt=tb[i]*fraction;t=rawt*basis;net=(gross-fee)*q[i];tax=max(net-t,0)*rate[0]
     cash[i]-=gross;cash[0]+=net-tax;totalprofit[i]-=fee;totalprofit[0]+=net-b-tax;k[i]-=gross;book[i]-=b;tb[i]-=rawt;nb[i]-=gross
   reserve(i);a=b=0
   if year>=startdiv and not (i==2 and debt>1e-8):
    free=max(cash[i]-floor[i],0);a=min(max(totalprofit[i],0)*.65,max(u[i],0),free);b=min(max(u[i]-a,0),max(free-a,0)) if year>=release else 0
   d=a+b;cash[i]-=d;u[i]-=d;cash[receiver[i]]+=d*q[i];totalprofit[receiver[i]]+=d*q[i]
   if i in (2,3,4,5,6):nb[i]-=d
  if refund and year==2:cash[0]-=92.6531;shares-=6.763;k[0]-=6.763
  oldshares=shares;oldunits=units;free=max(cash[0]-floor[0],0);target=div[year-1]*shares if year<=5 else free
  oldprofit=totalprofit[0];oldcap=u[0];oldres=z[0]
  def decide(net):
   expense=net*pfee/(1-pfee);profit=oldprofit-expense
   eligible=max(profit-max(-oldcap,0),0);charge=.1*eligible if keep and year<=keepuntil else min(.1*eligible,max(k[0]*.5-oldres,0))
   capacity=oldcap+profit-charge;ordinary=min(target,max(free-expense,0),max(capacity,0))
   return ordinary,capacity,charge,expense
  d,capacity,charge,expense=decide(0);net=0
  if year>=pstart and (year-pstart)%pevery==0 and free-d>1e-8:
   limit=min(free*(1-pfee),(k[0]+premium)*max(1-.1*635.588289/k[0],0))
   # Independent fixed-point cash budget, not production bisection.
   net=min(free-d,limit)
   for iteration in range(100):
    d,capacity,charge,expense=decide(net)
    following=max(0,min(free-d-expense,limit))
    if abs(following-net)<1e-12:net=following;break
    net=following
   d,capacity,charge,expense=decide(net)
   fraction=net/(k[0]+premium);k[0]*=1-fraction;premium*=1-fraction;shares*=1-fraction;units*=1-fraction
  u[0]=capacity-d;z[0]=oldres+charge;cash[0]-=d+net+expense;ds.append((d+net)/oldshares*oldunits)
  rows.append({'cash':cash[:],'capacity_budget':u[:],'reserve_budget':z[:],'registered_capital_budget':k[:],'J_loan':debt,'dividend':d,'shares':shares,'original_holder_units':units,'parent_premium_budget':premium,'active':alive[:]})
 return {'PV':math.fsum(x/(1+r)**(i+1) for i,x in enumerate(ds)),'TV5':math.fsum(ds[i]/(1+r)**(i-4) for i in range(5,300)),'DPS5':ds[:5],'rows':rows}

def test_jiangzhong_literal_27_full_paths():
    results={'continued_reserves_first5':calculate(keep=True,keepuntil=5),'structural_continued_reserves_first5':calculate(struct=True,keep=True,keepuntil=5),'structural_fund_batches8_40_80':calculate(struct=True,batches=True),'structural_parent_return_disabled':calculate(struct=True,pstart=10000),'structural_parent_return30_fee5':calculate(struct=True,pstart=30,pevery=10,pfee=.05),'structural_late_fund40':calculate(struct=True,fundyear=40),'structural_continue_reserve':calculate(struct=True,keep=True),'zero_sub_opening_capacity':calculate(zero=True),'base':calculate(),'core_low':calculate(r=.1,g=.015,roi=.14),'core_high':calculate(r=.09,g=.02,roi=.18),'structural':calculate(struct=True),'cyclical':calculate(cyc=True),'tax_qualification_not_renewed':calculate(renew=False),'J_maturity10':calculate(maturity=10),'structural_J_maturity10':calculate(struct=True,maturity=10),'structural_J_recovery30':calculate(struct=True,jreal=.3),'no_weak_asset_exit':calculate(weak_year=10000),'weak_asset_realization30':calculate(weakreal=.3),'weak_asset_exit20':calculate(weak_year=20),'zero_capital_tax_basis':calculate(basis=0),'continued_reserves':calculate(keep=True),'release_8':calculate(startdiv=8,release=9),'legacy_all51_equity':calculate(all51=True),'Jingcheng_turnaround':calculate(turn=True),'refund_cancel':calculate(refund=True),'financial_minus100':calculate(fin=-100)}
    # Only after all independent paths, read the production output for comparison.
    o=json.loads((D/'2026-Q3-output.json').read_text());checks={}
    for n,res in results.items():
     c=o['cases'][n];raw=gzip.decompress(base64.b64decode(c['annual_trace_gzip_base64']));assert hashlib.sha256(raw).hexdigest()==c['annual_trace_sha256'];actual=json.loads(raw)
     pv=res['PV']-c['valuation']['value'];tv=res['TV5']-c['valuation']['tv5'];assert abs(pv)<1e-8 and abs(tv)<1e-8,(n,pv,tv)
     maximum=0.
     for a,b in zip(res['rows'],actual):
      for k in ['cash','capacity_budget','reserve_budget','registered_capital_budget']:
       for x,y in zip(a[k],b[k]):
        if x is None:assert y is None;continue
        e=abs(x-y);maximum=max(maximum,e);assert e<1e-7,(n,b['year'],k,x,y)
      for k in ['J_loan','dividend','shares','original_holder_units','parent_premium_budget']:assert abs(a[k]-b[k])<1e-7
      assert a['active']==b['active']
     checks[n]={'PV_error':pv,'TV5_error':tv,'max_state_error':maximum}

import copy,runpy,subprocess,sys
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def expanded():return model()['expand'](json.loads((D/'2026-Q3-output.json').read_text()))

def test_jiangzhong_actual_registered_gate_and_loss():
 m=model();f=m['reserve_roll'];assert f(0,5,20,10)[2]==1
 assert abs(f(-6,0,20,10)[2]-.4)<1e-12
 assert f(0,10,20,10)[2]==0
 assert f(0,10,20,10,True)[2]==1
 p=copy.deepcopy(m['BASE']);p['aftertax_operating'][0]=-1000;p['cash'][0]+=5000
 z=m['run'](p,1);assert z['feasible'];assert z['rows'][0]['incremental_financing_cash_tax'][0]==0

def test_jiangzhong_capital_realization_original_holder_and_future_batches():
 m=model();out=expanded()
 for name in ['structural','structural_parent_return30_fee5','structural_fund_batches8_40_80']:
  c=out['cases'][name];assert c['feasible'];events=[]
  for row in c['rows']:
   e=row['parent_capital_return'];net=e['net_to_original_holders'];cash=(row['dividend']+net)/635.588289
   assert abs(cash-row['dividend_per_share'])<1e-10
   assert abs(row['original_holder_units']/row['shares']-1/635.588289)<1e-12
   assert row['parent_premium_budget']==0 and e['premium_repaid']==0
   if net>1e-8:
    assert abs(net-e['nominal_cancelled'])<1e-8
    assert e['profit_effect']==-e['fee'] and e['cash_tax_refund']==0
    events.append(row['year'])
   if row['year']>5:assert row['capex']==row['depreciation']
  last=m['run'](c['parameters'],400)['rows'][-1]
  assert abs(last['cash'][0]-last['cash_floor'][0])<1e-6
  if name.endswith('8_40_80'):assert len(events)>=2
 assert not out['cases']['no_new_J_funding']['feasible']

def test_jiangzhong_no_double_loans_exit_and_all_cash():
 m=model();out=expanded();y=out['cases']['base']['rows'][0]
 assert abs(y['old_J_parent_receivable_collected']-163.21408)<1e-9
 assert abs(y['node_total_profit'][0]-y['node_own_profit'][0]-sum(y['parent_or_intermediate_received'][i] for i in [1,2,3,4,5,6]))<1e-9
 assert abs(y['nominal_loan_interest']-9)<1e-9
 for c in out['cases'].values():
  if not c['feasible']:continue
  previous=c['parameters']['cash']
  for r in c['rows']:
   ex=r['J_exit'];other=r['weak_asset_exits'];returns=r['capital_returns'];expected=sum(previous)+sum(r['cashflow_before_internal_principal'])-r['external_principal_paid']-r['fund_call']+r['fund_exit']['net']-r['dividend']-r['parent_capital_return']['net_to_original_holders']-r['parent_capital_return']['fee']-r['minority_paid']-r['listed_refund']+ex['noncash_assets_realized']-ex['cash_tax']+sum(a['noncash_assets_realized']-a['tax'] for a in other)-sum(a['fee']+a['tax'] for a in returns)
   assert abs(sum(r['cash'])-expected)<1e-7
   assert all(a>=b-1e-7 for a,b in zip(r['cash'],r['cash_floor']))
   if ex['gross_cash']:
    assert abs(ex['gross_asset_sale_cash']-ex['outside_creditors_paid']-ex['noncash_assets_realized'])<1e-7
    assert abs(ex['parent_equity_received']+ex['minority_received']-ex['net_equity'])<1e-7
   if r['year']>20:
    for i in range(8):
     if not r['active'][i]:assert r['operating_aftertax'][i]==r['capex'][i]==r['financial_income'][i]==0
   previous=r['cash']

def test_jiangzhong_isolated_regeneration_and_pack(tmp_path):
 import shutil
 m=model();out=expanded();assert m['expand'](m['pack'](out))==out
 shutil.copy2(D/'2026-Q3.py',tmp_path/'2026-Q3.py')
 subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py')],check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
 assert all(abs(a-b)<1e-14 for a,b in zip(out['core']['distributions'],[.95,1.,1.05,1.1,1.15]))
