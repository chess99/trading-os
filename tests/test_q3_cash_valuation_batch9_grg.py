#!/usr/bin/env python3
"""Independent raw-parameter reimplementation; imports no production model.
Compare all annual cash/NI/debt/dividends for base and dominant margin shock,
both current endpoints AND fixed-state TV5, and auxiliary PB. Stdlib only.
"""
import json,pathlib,math
HERE=pathlib.Path(__file__).parent

def recompute(margin_shock=0):
    # Raw disclosures / explicitly chosen forecasts, separately transcribed.
    w=[.45,.08,.06,.06,.32,.03,0];own=[1,1,1,1,1,.65,.8128]
    cash=[2050.,120.,60.,60.,260.,60.,26.06493146]
    retained=[666.89041865-92.5144512,0,0,0,0,0,-60.]
    reserve=[166.61911677,30,10,5,100,10,0]
    capital=[639.621152,250,100,50,1200,100,100]
    sales=4000.;debt=392.73004860+780.29275422+998.87765451+(160.72606274-75.06698696)
    shares=639.621152-22.858144
    growth=[.12,.11,.10,.09,.08,.07,.06,.05,.04,.03]
    margins=[.13,.133,.136,.138,.14,.137,.134,.13,.125,.12]
    rows=[];used=0.
    for year in range(1,141):
        own_start=list(own)
        last_sales=sales;sales*=1+(growth[year-1] if year<=10 else .02)
        margin=(margins[year-1] if year<=10 else .12)+(margin_shock if year>=2 else 0)
        operating=sales*margin;interest=debt*.035*.85
        ehs=[-25,-20,-12,-5,0][year-1] if year<=5 else 0
        invest=(sales*.085+[350,400,300,150,100][year-1]-sales*.09+(sales-last_sales)*.25) if year<=5 else (sales-last_sales)*margin/.11
        mature=min(debt,[847,100,1000,100,100][year-1] if year<=5 else 100)
        credit=500 if year==3 else 0;debt+=credit-mature;cash[0]+=credit-mature
        if year<=2:
            options=(8.02-.11-.18-2.5212-.02805)/2
            shares+=options;cash[0]+=options*(13.71 if year==1 else 13.40);capital[0]+=options
        if year<=5:shares+=22.858144/5
        profits=[];opprofits=[];floors=[]
        for i in range(7):
            floor=(sales*.15+max(0,1050-sum([350,400,300][:min(year,3)])))*w[i] if i<6 else 20;floors.append(floor)
            op=operating*w[i]-(interest if i==0 else 0)+(ehs if i==6 else 0)
            profit=op+max(0,cash[i]-floor)*.013*.85
            profits.append(profit);opprofits.append(op)
            cash[i]+=profit-invest*w[i]
            taxable=max(0,profit-min(max(profit,0),max(-retained[i],0)))
            addition=min(taxable*.1,max(0,capital[i]/2-reserve[i]))
            reserve[i]+=addition;retained[i]+=profit-addition
        upstream=0
        for i in range(1,7):
            contribution=max(0,floors[i]-cash[i]);cash[0]-=contribution;cash[i]+=contribution
            own[i]=(own[i]*capital[i]+contribution)/(capital[i]+contribution);capital[i]+=contribution
            demand=max(0,profits[i])*.7 if year<=5 else max(0,retained[i])
            dividend=max(0,min(demand,retained[i],cash[i]-floors[i]))
            cash[i]-=dividend;retained[i]-=dividend;upstream+=dividend*own[i]
        cash[0]+=upstream
        available=max(0,upstream-min(upstream,max(-retained[0],0)))
        reserve_add=min(available*.1,max(0,capital[0]/2-reserve[0]));reserve[0]+=reserve_add;retained[0]+=upstream-reserve_add
        draw=min(max(0,floors[0]-cash[0]),500-used);used+=draw;debt+=draw;credit+=draw;cash[0]+=draw
        assert cash[0]>=floors[0]-1e-8
        owner_operating=sum(opprofits[i]*own_start[i] for i in range(7))
        desired=max(0,owner_operating)*[.40,.40,.42,.45,.45][year-1] if year<=5 else max(0,owner_operating-invest*sum(w[i]*own_start[i] for i in range(7))-mature+credit)
        ordinary=max(0,min(desired,retained[0],cash[0]-floors[0]));cash[0]-=ordinary;retained[0]-=ordinary
        special=0
        if year>5:
            special=max(0,min(retained[0],cash[0]-floors[0]));cash[0]-=special;retained[0]-=special
        rows.append({'year':year,'revenue':sales,'net_reinvestment':invest,'owner_net_profit':sum(profits[i]*own_start[i] for i in range(7)),'ending_cash':sum(cash),'debt_end':debt,'ordinary':ordinary,'special':special,'shares':shares,'distribution_per_share':(ordinary+special)/shares,'entities':[{'cash':cash[i],'retained':retained[i],'reserve':reserve[i],'ownership':own[i],'capital':capital[i]} for i in range(7)]})
    endpoints={}
    for horizon in [60,100,140]:
        period=rows[:horizon];ends={}
        for r in [.1,.09]:
            continuation=period[-1]['distribution_per_share']*1.02/(r-.02)
            current=continuation/(1+r)**horizon
            terminal=continuation/(1+r)**(horizon-5)
            for row in period:
                current+=row['distribution_per_share']/(1+r)**row['year']
                if row['year']>5:terminal+=row['distribution_per_share']/(1+r)**(row['year']-5)
            ends[str(r)]={'value_per_share':current,'year5_terminal_per_share':terminal}
        endpoints[str(horizon)]=ends
    return rows,endpoints


import pytest,runpy
ROOT=pathlib.Path(__file__).resolve().parents[1]/'research/companies/CN/002967/models'
@pytest.mark.parametrize('case,shock',[('base',0),('margin_minus_1pp_y2',-.01)])
def test_grg_independent_140year_entity_cash(case,shock):
 expected=json.loads((ROOT/'2026-Q3-output.json').read_text());rows,values=recompute(shock)
 for a,b in zip(rows,expected['scenarios'][case]['rows']):
  for field in ['revenue','net_reinvestment','owner_net_profit','ending_cash','debt_end','ordinary','special','shares','distribution_per_share']:assert a[field]==pytest.approx(b[field],abs=1e-7)
  for ae,be in zip(a['entities'],b['entities']):
   for af,bf in [('cash','cash_end'),('retained','retained_end'),('reserve','reserve_end'),('ownership','ownership_end'),('capital','capital_end')]:assert ae[af]==pytest.approx(be[bf],abs=1e-7)
 for horizon,ends in values.items():
  for rate,v in ends.items():
   for field,value in v.items():assert value==pytest.approx(expected['horizon_checks'][case][horizon]['valuations'][rate][field],abs=1e-9)
 for rate,v in values['140'].items():
  for field,value in v.items():assert value==pytest.approx(expected['valuations'][case][rate][field],abs=1e-9)
def test_grg_formal_cash_and_ownership_functions():
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['selftests']()
 e={'capital':100.,'ownership':.6,'cash':0.};m['inject_at_par'](e,100.);assert e=={'capital':200.,'ownership':.8,'cash':100.}
 out=json.loads((ROOT/'2026-Q3-output.json').read_text())
 for case in out['scenarios'].values():
  if case['feasible']:
   assert len(case['rows'])==140
   m['horizon_check'](case)
