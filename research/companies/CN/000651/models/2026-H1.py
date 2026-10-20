# -*- coding: utf-8 -*-
"""Gree standalone owner-value model. Units: CNY 100m, shares 100m."""
import json
from pathlib import Path
D = [2.6, 2.65, 2.7, 2.75, 2.8]
NP = [245, 250, 255, 260, 265]
S = 56.01405741 - .7 * (.0174 + 49.31767703 / 40)
BUYBACK = 49.31767703
GRANT = (.0174 + BUYBACK / 40) * .3 * 40
B0 = 1485.0807655636 - .68232297 - .315428
Q = .01 * (1 - .165)

def pv(cash, terminal, rate):
    return sum(x / (1 + rate) ** t for t, x in enumerate(cash, 1)) + terminal / (1 + rate) ** len(cash)

def asset_factor(rate, years, yield_rate=Q):
    return sum(yield_rate / (1 + rate) ** t for t in range(1, years + 1)) + (1 + rate) ** (-years)

def run(initial_surplus=350, multiple=10, rate=.1025, release_years=4, profits=None, dividends=None, capex=None, wc=None):
    profits = list(NP if profits is None else profits)
    dividends = list(D if dividends is None else dividends)
    capex = [50] * 5 if capex is None else capex
    wc = [15] * 5 if wc is None else wc
    equity, surplus = B0, initial_surplus
    rows=[]
    for i, profit in enumerate(profits):
        expense=GRANT if i==0 else 0
        reported=profit-expense
        fcfe=reported+expense+50-capex[i]-wc[i]-1
        div=dividends[i]*S
        buy=BUYBACK if i==0 else 0
        retained=fcfe-div-buy
        equity+=reported+expense-div-buy
        surplus+=retained
        rows.append(dict(year=i+1,profit_before_new_grant=profit,grant_expense=expense,net_income=reported,grant_addback=expense,fcfe=fcfe,dividend_per_share=dividends[i],dividend=div,buyback=buy,retained_cash=retained,equity=equity,surplus=surplus))
        assert abs(fcfe-div-buy-retained)<1e-9
    financial_interest=surplus*Q
    continuing_profit=profits[-1]-financial_interest
    asset_value=surplus*asset_factor(rate,release_years)
    terminal=(continuing_profit*multiple+asset_value)/S
    current=pv(dividends,terminal,rate)
    assert abs(equity-B0-sum(r['retained_cash'] for r in rows)-sum(wc)-sum(x-49.45 for x in capex)-2.25)<1e-7
    return dict(initial_surplus=initial_surplus,multiple=multiple,rate=rate,release_years=release_years,rows=rows,terminal_financial_interest=financial_interest,terminal_continuing_profit=continuing_profit,terminal_financial_value=asset_value,terminal=terminal,current=current,terminal_pv_share=terminal/(1+rate)**5/current)

low=run(300,9,.11,5)
high=run(400,11,.095,3)
base=run()
# Cross-check current normalized earnings, matching buyback and future rights.
def capitalization(np,initial,multiple,rate,years):
    interest=initial*Q
    asset=initial*asset_factor(rate,years)
    return dict(profit=np,initial_surplus=initial,interest_removed=interest,multiple=multiple,asset_recovery_value=asset,buyback_pv=BUYBACK/(1+rate),shares=S,value=((np-interest)*multiple+asset-BUYBACK/(1+rate))/S)
second=[capitalization(240,300,9,.11,10),capitalization(270,400,11,.095,8)]
sens={
 'base_release_10_years':run(350,10,.1025,10),
 'base_permanent_interest_only':None,
 'base_margin_minus_1pct':run(350,10,.1025,4,profits=[p-r*.01*.835 for p,r in zip(NP,[1600,1625,1650,1675,1700])]),
 'base_surplus_zero':run(0,10,.1025,4),
 'base_multiple_9':run(350,9,.1025,4)
}
a=base['rows'][-1]['surplus']; op=base['terminal_continuing_profit']
permanent_tv=(op*10+a*Q/.1025)/S
sens['base_permanent_interest_only']=dict(terminal=permanent_tv,current=pv(D,permanent_tv,.1025))
cyc=run(350,9,.11,5,profits=[210,220,235,250,265],dividends=[2.2,2.35,2.5,2.65,2.8],wc=[30,20,10,15,15])
bear=run(180,7,.12,10,profits=[170,155,140,125,115],dividends=[1.5,1.2,1,.8,.7],capex=[85,55,55,55,55],wc=[35]*5)
bull=run(400,11,.095,3,profits=[260,280,300,315,330],dividends=[2.7,2.9,3.1,3.3,3.5],capex=[60]*5,wc=[20]*5)
assert abs(asset_factor(0,3)-1-3*Q)<1e-10
assert abs(asset_factor(.1,5,.1)-1)<1e-10
assert abs(pv([0]*5,100,.1)-100/1.1**5)<1e-10
assert abs(S-55.138818061975)<1e-9
assert len(D)==5
allocation_fixed=1516.6663935226
allocation=dict(financial_pool=2532.83,fixed_support=allocation_fixed,channel_claims=682.99,low_backing=.9,high_backing=.75,low_liquidity=101.4726064774,high_liquidity=103.9211064774)
assert abs(2532.83-allocation_fixed-682.99*.9-allocation['low_liquidity']-300)<1e-8
assert abs(2532.83-allocation_fixed-682.99*.75-allocation['high_liquidity']-400)<1e-8
out=dict(allocation=allocation,shares=S,grant=GRANT,opening_equity=B0,financial_pool=2532.83,all_liabilities=2468.1450904822,operating_current_assets=520.2274301302,residual_before_buffers=2532.83+520.2274301302-2468.1450904822,low=low,high=high,base=base,second_method=second,sensitivity=sens,scenarios=dict(cyclical=cyc,structural=bear,optimistic=bull),self_checks='passed')
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:out[k] for k in ['shares','residual_before_buffers','self_checks']}))
for k,v in [('low',low),('high',high),('base',base),('cyclical',cyc),('structural',bear),('optimistic',bull)]:print(k,v['current'],v['terminal'])
for k,v in sens.items():print(k,v['current'])
print('second',[x['value'] for x in second])
