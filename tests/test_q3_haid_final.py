"""Literal independent reconstruction. Does not import/exec/parse production code or inputs.
Read production result only AFTER all independent computations finish.
"""
import json
from pathlib import Path

def calc(unit=1,capital_factor=1,lag=.2,capacity=.9,friction=.03,taxfade=.06):
    pc,sc,bank=3.,4.35,3.;ret,stat,reg=2.5,.831874985,1.663749970
    stock=1.657062365;loan=pending=0.;gret=19.1646404088
    d,o=27.2,4.3;prior=(27.2+4.3)/33.3;answers=[]
    for year in range(1,107):
        before_d,before_o=d,o
        if year==1:d,o=28.5,4.8
        else:
            fade=1 if year<=5 else max(0,(12-year)/7)
            d=d*(1+.02+.03*fade);o=o*(1+.02+.13*fade)
        scale=(d+o)/33.3
        overunit=220*unit*(1-taxfade*min(1,max(0,year-3)/7))
        operating=(105*unit*d+overunit*o)/1000+.5*scale
        own=.75*scale
        investment=((d-before_d)*(450 if year<=5 else 900)+(o-before_o)*(1200 if year<=5 else 1500))/1000*capital_factor+.5*max(0,scale-prior)/.15
        mother=own+.02*pc+loan*.03*(1-.15)
        source=operating-own+.02*sc-.035*bank-.03*loan
        pc+=mother-.05*investment;sc+=source-.95*investment
        if year==1:pc+=.002955818*26.91;stock+=.002955818;reg+=.002955818
        sc-=pending;pc+=pending*.95;pending=0
        repay=min(loan,max(0,sc-2.5*scale));sc-=repay;pc+=repay;loan-=repay
        principal=min(bank,.4 if year<=5 else .5*max(0,sc-2.5*scale),max(0,sc-2.5*scale));sc-=principal;bank-=principal
        advance=min(max(0,2.5*scale-sc),max(0,pc-.8*scale));pc-=advance;sc+=advance;loan+=advance
        borrow=max(0,2.5*scale-sc);assert bank+borrow<=5+1e-9;bank+=borrow;sc+=borrow
        spare=max(0,sc-2.5*scale)
        rate=[.35,.5,.65,.75,.85][year-1] if year<=5 else 1
        extra=.25*max(0,spare-max(source,0))
        remittance_rate=friction*min(1,max(0,o*overunit/max(operating*1000,1e-6)))
        decl=min(max(0,source)*rate+extra,capacity*max(0,source)+extra,spare/(1+remittance_rate))
        fee=decl*remittance_rate;paid=decl*(1-lag);pending=decl-paid
        sc-=paid+fee;pc+=paid*.95
        newearn=mother+decl*.95
        reserve=min(.1*max(0,newearn+min(ret,0)),max(0,.5*reg-stat));ret+=newearn-reserve;stat+=reserve
        common=mother+.95*(source-fee)
        legal=max(0,min(ret,gret+common));money=max(0,pc-.8*scale)
        ordinary=min(max(0,common)*(.5 if year<=5 else .7),legal,money)
        special=min(.25*max(0,money-ordinary),max(0,legal-ordinary)) if year>5 else 0
        distribution=ordinary+special;pc-=distribution;ret-=distribution;gret+=common-distribution
        answers.append(dict(distribution=distribution/stock,parent_cash=pc,source_cash=sc,legal_retained=ret,declared=decl,common_profit=common,investment=investment));prior=scale
    values={}
    for r in [.095,.105]:
        continuation=answers[-1]['distribution']/(r-.02)
        # Backward recursion, distinct from production forward discounted sum.
        backwards=continuation;tv5=None
        for j in range(104,-1,-1):
            backwards=(answers[j]['distribution']+backwards)/(1+r)
            if j==5:tv5=backwards
        values[str(r)]=dict(pv=backwards,tv5=tv5)
    return dict(rows=answers,values=values)


import runpy,subprocess,sys,shutil,copy
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/002311/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():return json.loads((D/'2026-Q3-output.json').read_text())
def test_haid_seven_literal_full_106years():
 computed={'base':calc(),'unit_minus10':calc(unit=.9),'capital_plus25':calc(capital_factor=1.25),'lag50':calc(lag=.5),'upstream_capacity40':calc(capacity=.4),'remittance_friction10':calc(friction=.1),'method_only_new':calc(capacity=1,friction=0,taxfade=0)}
 out=output()
 for name,res in computed.items():
  exp=out['scenarios']['base'] if name=='base' else out['method_only_new'] if name=='method_only_new' else out['sensitivities'][name]
  for rate,key in [('.095','high'),('.105','low')]:
   for metric in ['pv','tv5']:assert abs(res['values'][str(float(rate))][metric]-exp[key][metric])<1e-9
  for a,b in zip(res['rows'],exp['rows']):
   for x,y in [('distribution','distribution_per_share'),('parent_cash','parent_cash'),('source_cash','source_cash_budget'),('legal_retained','parent_legal_retained'),('declared','new_dividend_budget'),('common_profit','common_profit'),('investment','reinv')]:assert abs(a[x]-b[y])<1e-7

def test_haid_registered_receipt_loss_actual_and_exit_creditors():
 m=model();m['tests']();f=m['legal_profit'];assert f(0,10,20,5)['reserve_add']==1;assert f(0,10,20,10)['reserve_add']==0
 e=m['exit_waterfall'](100,.2,30,10,.6,20,5,4,.2,100);assert e['outside_shortfall']==14 and not e['feasible'] and e['units_close']==100 and e['units_cancelled']==0
 e=m['exit_waterfall'](100,0,0,10,.6,20,5,4,.2,100);assert not e['feasible'] and e['exit_fee_shortfall']==4 and e['units_close']==100
 e=m['exit_waterfall'](100,.8,30,10,.6,20,5,4,.2,100);assert e['feasible'] and abs(e['parent_receipt']-31.6)<1e-12 and e['units_close']==0

def test_haid_all_paths_actual_funding_capital():
 m=model();o=output();assert len(o['scenarios'])==4 and len(o['sensitivities'])==18
 for case in list(o['scenarios'].values())+list(o['sensitivities'].values()):
  for r in case['rows']:
   assert abs(r['cash_identity_error'])<1e-7 and abs(r['balance_error'])<1e-6
   assert r['parent_cash']>=r['pmin']-1e-8 and r['source_cash_budget']>=r['smin']-1e-8
   assert r['maintenance']>0 and r['source_interest_tax_credit']==0
 m['future_surplus_tests']()

def test_haid_fresh_single_file(tmp_path):
 shutil.copy2(D/'2026-Q3.py',tmp_path/'2026-Q3.py');subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py')],check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
