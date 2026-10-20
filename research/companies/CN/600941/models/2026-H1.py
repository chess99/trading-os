#!/usr/bin/env python3
"""CNY 100m units; shares in 100m. Standalone, standard library, no network."""
import json
from pathlib import Path
S0=216.87214173
S=221.72656240
FX=0.865436
OPTION=(0.69475775*55+4.15966292*51.60)*FX
C0=2495.3809
RESERVE=500.0
OTHER_FIN=6477.90-1878.57-1338.83
ASSOCIATES=2183.53
D=[5,5.05,5.10,5.15,5.20]
OCF=[2500,2530,2570,2600,2650]
CAPEX=[1400,1390,1400,1420,1450]
LEASE=[300,295,290,285,280]
PROFIT=[1230,1250,1280,1310,1350]
# Research budgets, not disclosed allocation: interest embedded in OCF 70;
# realized investing receipts 150. Investment accrual retained earnings 60.
INTEREST=70.0
INVEST_CASH=150.0
OTHER=30.0
DIST=[S0*2.51+S*2.49]+[S*d for d in D[1:]]

def run(ocf=OCF,capex=CAPEX,lease=LEASE,ds=D,interest=INTEREST,option=OPTION,shares=S):
    cash=C0
    rows=[]
    dist=[S0*2.51+shares*(ds[0]-2.51)]+[shares*d for d in ds[1:]]
    for i in range(5):
        op=ocf[i]-capex[i]-lease[i]-OTHER-interest
        pre=cash
        cash+=op+interest+INVEST_CASH-dist[i]+(option if i==0 else 0)
        assert abs(cash-(pre+ocf[i]-capex[i]-lease[i]-OTHER+INVEST_CASH-dist[i]+(option if i==0 else 0)))<1e-8
        rows.append(dict(year=i+1,profit=PROFIT[i],ocf=ocf[i],capex=capex[i],lease=lease[i],other=OTHER,interest_in_ocf=interest,investment_cash=INVEST_CASH,operating_cash=op,distribution=dist[i],option_cash=option if i==0 else 0,cash_end=cash))
    return rows

def pv(ds,tv,r):
    return sum(d/(1+r)**(i+1) for i,d in enumerate(ds))+tv/(1+r)**5

def endpoint(rows,r,g,liquid_factor,other_factor,associate_factor,ds=D):
    free=max(0,rows[-1]['cash_end']-RESERVE)
    liquid=free*liquid_factor
    financial=OTHER_FIN*other_factor
    associates=(ASSOCIATES+5*60)*associate_factor
    op=rows[-1]['operating_cash']*(1+g)/(r-g)
    assets=liquid+financial+associates
    terminal=(op+assets)/S
    current=pv(ds,terminal,r)
    return dict(rate=r,growth=g,liquid_factor=liquid_factor,other_financial_factor=other_factor,associate_factor=associate_factor,operating_terminal=op,liquid_terminal=liquid,other_financial_terminal=financial,associate_terminal=associates,assets_terminal=assets,terminal_per_share=terminal,current_per_share=current,terminal_pv_share=terminal/(1+r)**5/current,terminal_excess_liquid=free)

rows=run()
low=endpoint(rows,.09,.005,.98,.80,.70)
high=endpoint(rows,.08,.015,1,.95,.90)
# Alternative current operating-profit capitalization. Financial sleeve =
# its net cash benefits to shareholders during years 1-5 plus residual assets.
# Allocated operating cash is a valuation decomposition, not another dividend.
financial_sleeve={}
for label,e in [('low',low),('high',high)]:
    r=e['rate']
    sleeve=sum((D[i]-rows[i]['operating_cash']/S)/(1+r)**(i+1) for i in range(5))+e['assets_terminal']/S/(1+r)**5
    financial_sleeve[label]=sleeve
cross_low=920*10.5/S+financial_sleeve['low']
cross_high=1000*12.5/S+financial_sleeve['high']
# Meaningful one-factor and operating-path stresses.
cap_rows=run(capex=[x+100 for x in CAPEX])
cap_stress=endpoint(cap_rows,.085,.01,.99,.875,.80)
mid=endpoint(rows,.085,.01,.99,.875,.80)
interest_stress=endpoint(run(interest=120),.085,.01,.99,.875,.80)
asset_stress=endpoint(rows,.085,.01,.99,.775,.70)
cycle_rows=run(ocf=[2320,2430,2570,2600,2650],ds=[4.6,4.8,5.1,5.15,5.2])
cycle=endpoint(cycle_rows,.085,.01,.99,.875,.80,[4.6,4.8,5.1,5.15,5.2])
struct_rows=run(ocf=[2400,2325,2250,2175,2100],capex=[1450,1460,1475,1490,1500],lease=[305,310,315,320,325],ds=[4.8,4.5,4,3.6,3.3])
struct=endpoint(struct_rows,.10,0,.95,.70,.60,[4.8,4.5,4,3.6,3.3])
optimistic_rows=run(ocf=[2600,2730,2870,3010,3150],capex=[1390,1430,1470,1510,1550],ds=[5.1,5.25,5.45,5.65,5.9])
optimistic=endpoint(optimistic_rows,.08,.015,1,.95,.90,[5.1,5.25,5.45,5.65,5.9])
no_options=run(option=0,shares=S0)
parent_cash=0
parent_reserve=478.33
parent_rows=[]
for i,up in enumerate([1120,1140,1160,1180,1200]):
    parent_cash+=up-3-DIST[i]
    parent_reserve+=up-3-DIST[i]
    parent_rows.append(dict(year=i+1,upstream=up,cost=3,distribution=DIST[i],cash=parent_cash,profit_reserve=parent_reserve))
assert abs(S-S0-0.69475775-4.15966292)<1e-10
assert len(rows)==len(D)==5
assert abs(pv([1]*5,0,0)-5)<1e-10
assert abs(sum(DIST)-5641.842745318299)<1e-8
assert abs(rows[-1]['cash_end']-2012.3638921325837)<1e-8
assert abs(cap_rows[-1]['cash_end']-(rows[-1]['cash_end']-500))<1e-8
assert abs(run(interest=120)[-1]['cash_end']-rows[-1]['cash_end'])<1e-8
assert min(x['cash_end'] for x in rows)>RESERVE
assert parent_rows[0]['cash']>0
assert (550-S0*2.51-1.5)>0
out=dict(units='CNY 100m / shares 100m',shares=S,issued_shares=S0,option_cash=OPTION,other_financial_book=OTHER_FIN,rows=rows,low=low,high=high,mid=mid,core_range=dict(low=round(low['current_per_share']),high=round(high['current_per_share'])),terminal_range=dict(low=round(low['terminal_per_share']),high=round(high['terminal_per_share'])),financial_sleeve_pv=financial_sleeve,cross_check=dict(low=cross_low,high=cross_high),sensitivities=dict(annual_capex_plus100=cap_stress,interest_allocation_plus50=interest_stress,financial_and_associate_factor_minus10pp=asset_stress),scenarios=dict(cycle=cycle,structural=struct,optimistic=optimistic),no_options_cash_end=no_options[-1]['cash_end'],equity_end=14215.43+1.6009+sum(PROFIT)+OPTION-sum(DIST),parent_rows=parent_rows,tests='cash conservation, allocation invariance, capex stress, share bridge, zero-rate PV, dividend timing all passed')
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['core_range','terminal_range','cross_check','tests']},indent=2))
