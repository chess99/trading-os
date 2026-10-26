#!/usr/bin/env python3
"""Literal independent cash/legal rebuild; no official functions or input imports."""
import json
from pathlib import Path

def rebuild(md=0.,years=61,mode="base"):
    structural=mode in ["structural","structural_zero_growth"]; terminal_g=(0. if mode=="structural_zero_growth" else .01) if structural else .02
    taxrate=.15 if structural else .12
    rev=[3500.,1300.,500.,600.,850.]; rates=[.05,.13,.03,.08,.15]; margins=[.42,.49,.25,.72,.72]
    if structural: rates=[z*.35 for z in rates];md=-.055
    pc=2313.59109369; sc=3968.35261672-pc; pr=397.18677070; sr=1000.; pres=173.85715231; sres=30.
    loan=1555.79576224; debt=21.; oldrev=6259.14558695; oldmin=.1*oldrev; bv=6091.70646697; ppe=2454.79436444; liability=493.40713005
    capital=787.5;premium=2000.;live_shares=787.5
    other=bv-3968.35261672+21.+12.46136551+liability-ppe; rows=[]
    for y in range(1,years+1):
        if y>1: rev=[v*(1+(g if y<=5 else terminal_g+(g-terminal_g)*max(0,(15-y)/10))) for v,g in zip(rev,rates)]
        sales=sum(rev); change=sales-oldrev; minimum=.1*sales
        op=(sum(v*(m+md) for v,m in zip(rev,margins))-sales*(.165+.145+.04+.01+.005+.004-.009))*(1-taxrate)
        da=190*sales/6750; capex=da+max(change,0)*(.15 if y<=5 else (.35 if structural else .25))+(9.121 if y==1 else 0)
        wc=(.42 if structural else .3)*change-([150,100][y-1] if y<=2 and not structural else 0)+([300,100][y-1] if structural and y<=2 else 0); pay=493.40713005*([.6,.4][y-1] if y<=2 else 0)
        fcf=op+da-capex-wc-pay; po=(66 if structural else 120)*sales/6750; so=op-po
        pi=pc*.01; si=sc*.01; interest=debt*.04; il=loan*.03; pinet=il*.75; sinet=il-min(il,max(so,0)/.85)*.15; wedge=sinet-pinet
        employee=3.58805770 if y==1 else (3.57833757/3 if y in [2,3,4] else 0.)
        derivative=1.665961 if y==1 else 0.;collection=employee+derivative;parent_collection=derivative+.2*employee
        pc+=po+pi+pinet+parent_collection+.25*(da-capex-pay)-.7*wc
        sc+=collection-parent_collection+so+si-interest-sinet+.75*(da-capex-pay)-.3*wc
        dedicated=max(0,526.4-(493.40713005-liability)-pay-9.121) if y<3 else 0
        dedicated+=59.70256532 if y<5 else 0.
        pm=.6*minimum+12.46136551; sm=.4*minimum+dedicated
        assert pc>=pm and sc>=sm  # This independent base/margin diagnostic requires no new funding.
        repayloan=min(200,loan,max(0,sc-sm)); pc+=repayloan;sc-=repayloan;loan-=repayloan
        sn=so+si-interest-sinet; sr+=sn
        a=min(.1*max(0,min(sn,sr)),max(0,65-sres));sr-=a;sres+=a
        up=min((max(sn,0)*.70 if y<=5 else max(sr,0)),max(sr,0),max(0,sc-sm))
        sr-=up;sc-=up;remit=up*.005;pc+=up-remit
        pn=po+pi+pinet+up-remit
        capitalpaid=fee=face=0.
        if y>=15 and loan<1e-8:
            blocked=max(0,pc-pm-max(0,pr+pn))
            capitalpaid=min(500,capital+premium,blocked/1.01)
            fee=capitalpaid*.01; frac=capitalpaid/(capital+premium)
            face=capital*frac;premium-=premium*frac;live_shares*=1-frac;capital-=face
            pc-=capitalpaid+fee;pn-=fee
        pr+=pn
        a=min(.1*max(0,min(pn,pr)),max(0,capital*.5-pres));pr-=a;pres+=a
        ni=op+pi+si-interest-wedge-remit-fee
        request=max(ni,0)*.55 if y<=5 else max(0,fcf-(minimum-oldmin)+pi+si-interest-wedge-remit)
        ordinary=min(request,max(pr,0),max(pc-pm,0));pr-=ordinary;pc-=ordinary
        extra=min(max(pr,0),max(pc-pm,0)) if y>=6 else 0;pr-=extra;pc-=extra
        paid=ordinary+extra+capitalpaid
        repay=min(debt,max(0,sc-sm));sc-=repay;debt-=repay
        bv+=ni-paid;ppe+=capex-da;other+=wc-collection;liability-=pay
        assert abs(pc+sc-debt-12.46136551-liability+ppe+other-bv)<1e-6
        rows.append(dict(capital_return=capitalpaid,capital_return_cost=fee,parent_registered_capital_remaining=capital,live_shares_after_proportional_cancellation=live_shares,remittance_tax_friction_paid=remit,year=y,revenue=sales,nopat=op,cash_dividend=paid,ordinary_dividend=ordinary,additional_principal_release_dividend=extra,parent_cash=pc,subs_cash=sc,parent_retained=pr,subs_retained_budget=sr,parent_reserve=pres,subs_reserve_budget=sres,internal_loan_balance=loan,internal_interest_tax_wedge=wedge,book_equity=bv,upstream_dividend_declared_and_collected=up,cash_min=minimum))
        oldrev=sales;oldmin=minimum
    values=[]
    for k in [.105,.095,.10]:
        constant=12.46136551*.01
        terminal=(rows[-1]['cash_dividend']-constant)/(k-terminal_g)+constant/k
        tv=sum(r['cash_dividend']/(1+k)**(r['year']-5) for r in rows[5:-1])+terminal/(1+k)**(years-1-5)
        pv=sum(r['cash_dividend']/(1+k)**r['year'] for r in rows[:5])+tv/(1+k)**5
        values.append(dict(k=k,value=pv/787.5,tv5=tv/787.5))
    return dict(values=values,annual_entity_states=rows)

import copy,runpy,subprocess,sys,shutil
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/688475/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
def test_ezviz_independent_literal_ten_paths():
 m=model()
 cases=[(md,years,'base') for md in [0.,-.01] for years in [61,81,101]]+[(0.,years,mode) for mode in ['structural','structural_zero_growth'] for years in [61,101]]
 for md,years,mode in cases:
  own=rebuild(md,years,mode);s={'permanent_gm_shock':md} if mode=='base' else m['SCENARIOS'][mode];prod=m['trajectory'](m['INPUT'],s,years)
  for a,b in zip(own['annual_entity_states'],prod['rows']):
   for k,v in a.items():assert abs(v-b[k])<2e-7
  for a in own['values']:
   z=m['value'](m['INPUT'],prod,a['k'],s);assert abs(a['value']-z['value_per_share'])<1e-8;assert abs(a['tv5']-z['terminal_year5_per_share'])<1e-8

def test_ezviz_registered_tax_and_original_capital_actual_functions():
 m=model();f=m['statutory'];assert f(0,5,20,10)==(9,6,1);assert f(-6,0,20,10)==(3.6,.4,.4);assert f(0,10,20,10)==(10,10,0)
 assert f(0,10,40,10)==(9,11,1)
 assert m['operating_tax_bridge'](-100,120,.12)==(-20,-80,0,0)
 assert m['proportional_capital_return'](101,0,100,100,500,.01)==(100,1,50,50)
 assert m['proportional_capital_return'](0,0,100,100,500,.01)==(0,0,0,0)
 for name in ['base','structural','structural_zero_growth']:
  z=m['trajectory'](m['INPUT'],m['SCENARIOS'][name],241)
  for r in z['rows']:
   assert abs(r['distribution_per_share']*787.5-r['cash_dividend'])<1e-8
   assert abs(r['live_shares_after_proportional_cancellation']/r['parent_registered_capital_remaining']-1)<1e-12
   if name=='structural_zero_growth' and r['year']>15:assert r['maintenance']>0
  assert abs(z['rows'][-1]['group_cash']-z['rows'][-1]['cash_min']-12.46136551)<1e-6

def test_ezviz_all_scenarios_funding_and_cash():
 m=model();o=json.loads((D/'2026-Q3-output.json').read_text());assert len(o['scenarios'])==35
 for name,c in o['scenarios'].items():
  if not c['trajectory']['feasible']:continue
  for r in c['trajectory']['rows']:
   assert abs(r['cash_reconciliation_error'])<1e-6 and abs(r['equity_reconciliation_error'])<1e-6
   assert r['parent_operating_tax_budget']>=0 and r['nonparent_operating_tax_budget']>=0
 assert not o['scenarios']['funding_failure']['trajectory']['feasible']
 # Perpetual discretionary blocking is not silently called a complete value.
 for c in o['scenarios'].values():
  if c['trajectory']['feasible'] and isinstance(c['central'],dict) and c['central'].get('unresolved_terminal_constraint'):
   assert 'value_per_share' not in c['central']

def test_ezviz_isolated_fresh_exact(tmp_path):
 shutil.copy2(D/'2026-Q3.py',tmp_path/'2026-Q3.py');subprocess.run([sys.executable,str(tmp_path/'2026-Q3.py')],check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
