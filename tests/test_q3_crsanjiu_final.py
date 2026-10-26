"""Independent literal rebuild: does not import production or read its parameters.
Production output is read ONLY after own annual arrays and PV are built.
"""
import json,gzip,pathlib
P=pathlib.Path(__file__).parent

def rebuild(rate=.095,growth=.025,roic=.14,capmult=1.,margin=1.,cycle=5):
    weights=(1,1,.28,.2908);shares=1.664217858
    money=[1.00934958893,1.10909007747,2.84184543927,1.2];loans=[2,.2,.5,1.2925144079]
    revenue=[3,17.5,8.3,3.8];fixed=[2.5,7,6,3.5];earnings=[.4,2.45,1.6,0];rates=[.04,.075,.065,.06]
    payable=[0]*4;old_debt=1.1;retained=8.77745218836;rows=[];PV=0;T5=0;past_nop=None
    for year in range(1,241):
        salesgrowth=growth if year<=5 else growth+(.015-growth)*(year-5)/5 if year<=10 else .015
        cashstart=money[:];floor=[a*1.015**max(0,year-10) for a in [.4,.7,.6,.5]]
        np=[];op=[];declarations=[0]*4;remittances=[0]*4
        for i in range(4):
            inc=revenue[i]*salesgrowth;revenue[i]+=inc
            if year<=10:
                if i<3:earnings[i]*=1+salesgrowth;operating=earnings[i]*margin
                else:operating=[-.25,-.1,0,.12,.2,.22,.24,.26,.28,.3][year-1]
                depreciation=fixed[i]*rates[i];invest=(depreciation*1.12+max(inc,0)*.15)*capmult;wc=inc*.12
            else:
                operating=past_nop[i]*1.015;depreciation=fixed[i]*rates[i];invest=(depreciation+(operating-past_nop[i])/roic)*capmult;wc=0
            fixed[i]+=invest-depreciation if year<=10 else (operating-past_nop[i])/roic*capmult
            interest=loans[i]*.035*(.85 if i==0 and operating>0 else 1)
            np.append(operating-interest+cashstart[i]*.01)
            money[i]+=operating+depreciation-invest-wc-interest+cashstart[i]*.01
            op.append(operating)
        past_nop=op
        old=min(old_debt,.55 if year<=2 else 0,max(0,money[1]-floor[1]));money[1]-=old;money[0]+=old;old_debt-=old
        for i in [1,2,3]:
            paid=min(payable[i],max(0,money[i]-floor[i]));payable[i]-=paid;money[i]-=paid
            declared=min(max(0,np[i])*(.45 if i==1 else .5),max(0,money[i]-floor[i]-payable[i]));money[i]-=declared*.75;payable[i]+=declared*.25
            paid+=declared*.75
            repay=min(loans[i],max(0,money[i]-floor[i]*2-payable[i]));money[i]-=repay;loans[i]-=repay
            if year%cycle==0:
                extra=max(0,money[i]-floor[i]*2-payable[i]);money[i]-=extra;declared+=extra*.97;paid+=extra*.97
            declarations[i]=declared;remittances[i]=paid;money[0]+=paid*weights[i]
        if year==4:money[0]+=.65*.97
        retained+=np[0]+sum(declarations[i]*weights[i] for i in [1,2,3])-(.65*.03 if year==4 else 0)
        for i in range(4):
            credit=min(max(0,floor[i]-money[i]),max(0,[2.8,.5,.8,3.5][i]-loans[i]));money[i]+=credit;loans[i]+=credit
        div=min(max(0,sum(np[i]*weights[i] for i in range(4)))*.5,max(0,retained),max(0,money[0]-floor[0]));money[0]-=div;retained-=div
        repay=min(loans[0],max(0,money[0]-2*floor[0]));money[0]-=repay;loans[0]-=repay
        if year%cycle==0:
            special=min(max(0,retained),max(0,money[0]-2*floor[0]));money[0]-=special;retained-=special;div+=special
        PV+=div/(1+rate)**year/shares
        if year>5:T5+=div/(1+rate)**(year-5)/shares
        rows.append(dict(cash=money[:],debt=loans[:],parent_retained=retained,dividend=div,declarations_budget=declarations,receipts=remittances))
    return PV,T5,rows

checks={}
settings={'base':{},'core_low':dict(rate=.10,growth=.02,roic=.12),'core_high':dict(rate=.09,growth=.03,roic=.15),'capital_plus20':dict(capmult=1.2),'profit_minus10':dict(margin=.9),'discount_plus100bp':dict(rate=.105),'release8':dict(cycle=8)}

import runpy,subprocess,sys,shutil,base64,hashlib,copy
from pathlib import Path
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/000999/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():
 w=json.loads((D/'2026-Q3-output.json').read_text());raw=gzip.decompress(base64.b64decode(w['payload']));assert hashlib.sha256(raw).hexdigest()==w['full_payload_sha256'];return json.loads(raw)
def test_crsanjiu_seven_literal_240year_paths():
 rebuilt={k:rebuild(**v) for k,v in settings.items()};actual=output()
 for n,(pv,tv,rows) in rebuilt.items():
  target=actual['cases'][n]
  assert abs(pv-target['value_per_share'])<1e-9 and abs(tv-target['terminal5_per_share'])<1e-9
  for a,b in zip(rows,target['history']):
   for k in ['cash','debt','declarations_budget','receipts']:
    assert max(abs(x-y) for x,y in zip(a[k],b[k]))<1e-8
   for k in ['parent_retained','dividend']:assert abs(a[k]-b[k])<1e-8

def test_crsanjiu_real_production_tax_loss_and_funding():
 m=model();m['selftest']()
 assert abs(m['net_financing_cost'](.07,.01,.15)-(.07-.01/.85*.15))<1e-12
 assert m['net_financing_cost'](.07,-.01,.15)==.07
 p=copy.deepcopy(m['BASE']);p.update(m['CHANGES']['structural_unfunded'])
 x=m['value'](p);assert not x['feasible'] and x['value_per_share'] is None
 # The entire actual simulator gets a positive operating profit too small for its interest.
 p=copy.deepcopy(m['BASE']);p.update(years=1,payout=0,nonop_asset=0,old_receipt=[])
 p['literal_ops']=[[dict(revenue=0,nopat=.01,da=0,maintenance=0,capex=0,delta_wc=0,capital_end=0,fcff=.01) for _ in range(4)]]
 row=m['simulate'](p)[0]
 assert abs(row['interest'][0]-(.07-.01/.85*.15))<1e-12

def test_crsanjiu_all_cash_and_capital_return_identity():
 for c in output()['cases'].values():
  for r in c['history']:
   assert abs(r['cash_error'])<1e-6
   assert abs(r['dividend']/r['shares']-r['dps'])<1e-12
   assert abs(r['parent_retained']-r['parent_retained_begin']-r['parent_profit']+r['reserve_add']+r['voluntary_add']+r['dividend'])<1e-7
  if c['feasible']:assert all(min(r['cash'])>=-1e-9 for r in c['history'])

def test_crsanjiu_single_file_lossless_reproduction(tmp_path):
 f=tmp_path/'2026-Q3.py';shutil.copy2(D/'2026-Q3.py',f)
 subprocess.run([sys.executable,str(f)],check=True,stdout=subprocess.DEVNULL)
 assert f.with_name('2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
 r=subprocess.run([sys.executable,str(f),'--expand'],check=True,capture_output=True,text=True)
 assert json.loads(r.stdout)==output()
