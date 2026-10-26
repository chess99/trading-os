#!/usr/bin/env python3
"""Independent raw-parameter reimplementation; imports no production model.
Compare all annual cash/NI/debt/dividends for base and dominant margin shock,
both current endpoints AND fixed-state TV5, and auxiliary PB. Stdlib only.
"""
import json,pathlib,math
HERE=pathlib.Path(__file__).parent

def recompute(margin_shock=0,pool_rate=.15,fail_from=None):
    # Raw disclosures / explicitly chosen forecasts, separately transcribed.
    w=[.45,.08,.06,.06,.32,.03,0];own=[1,1,1,1,1,.65,.8128]
    cash=[2050.,120.,60.,60.,260.,60.,26.06493146]
    retained=[666.89041865-92.5144512,0,0,0,0,0,-60.]
    reserve=[166.61911677,30,10,5,100,10,0]
    capital=[639.621152,250,100,50,1200,100,50]
    sales=4000.;debt=392.73004860+780.29275422+998.87765451+(160.72606274-75.06698696)
    shares=639.621152-22.858144
    growth=[.12,.11,.10,.09,.08,.07,.06,.05,.04,.03]
    margins=[.13,.133,.136,.138,.14,.137,.134,.13,.125,.12]
    taxloss=[[] for _ in range(7)]
    rows=[];used=0.; zhong_investment_cost=235.85082384;closed=False
    for year in range(1,141):
        own_start=list(own)
        last_sales=sales;sales*=1+(growth[year-1] if year<=10 else .02)
        margin=(margins[year-1] if year<=10 else .12)+(margin_shock if year>=2 else 0)
        operating=sales*margin;grossinterest=debt*.035;interest=grossinterest*.85
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
            floor=(sales*.15+max(0,1050-sum([350,400,300][:min(year,3)])))*w[i] if i<6 else (0 if closed else 20);floors.append(floor)
            rate=pool_rate if i in [4,5] else (.25 if fail_from is not None and year>=fail_from else .15)
            grossop=operating*w[i]/.85 if operating*w[i]>0 else operating*w[i]
            grossop+=ehs if i==6 else 0
            gf=max(0,cash[i]-floor)*.013;gi=grossinterest if i==0 else 0
            taxloss[i]=[v for v in taxloss[i] if v[0]>=year];available=sum(v[1] for v in taxloss[i])
            t0=max(grossop-available,0)*rate;t1=max(grossop-gi-available,0)*rate;t2=max(grossop-gi+gf-available,0)*rate
            op=grossop-t0-gi+t0-t1;profit=op+gf-t2+t1
            usedloss=min(max(grossop-gi+gf,0),available)
            for v in taxloss[i]:take=min(v[1],usedloss);v[1]-=take;usedloss-=take
            taxloss[i]=[v for v in taxloss[i] if v[1]>1e-10]
            if grossop-gi+gf<0 and i not in [4,5]:taxloss[i].append([year+5,-grossop+gi-gf])
            profits.append(profit);opprofits.append(op)
            cash[i]+=profit-invest*w[i]
            taxable=max(0,profit-min(max(profit,0),max(-retained[i],0)))
            addition=min(taxable*.1,max(0,capital[i]/2-reserve[i]))
            reserve[i]+=addition;retained[i]+=profit-addition
        upstream=0
        for i in range(1,7):
            contribution=max(0,floors[i]-cash[i]);cash[0]-=contribution;cash[i]+=contribution
            if i==6:zhong_investment_cost+=contribution
            if capital[i]+contribution>0:own[i]=(own[i]*capital[i]+contribution)/(capital[i]+contribution)
            capital[i]+=contribution
            demand=max(0,profits[i])*.7 if year<=5 else max(0,retained[i])
            dividend=max(0,min(demand,retained[i],cash[i]-floors[i]))
            cash[i]-=dividend;retained[i]-=dividend;upstream+=dividend*own[i]
        if year==10:
            recovered=(201.25409215-26.06493146)*.80+45.57958246*.50
            costs=(cash[6]+recovered)*.03
            after_creditors=cash[6]+recovered-51.66769031-costs
            parent_receipt=(after_creditors-.75)*own[6]
            cash[0]+=parent_receipt
            retained[0]+=parent_receipt-zhong_investment_cost # disposal LOSS, no tax credit or fictitious dividend income
            cash[6]=0.;retained[6]=0.;reserve[6]=0.;capital[6]=0.;closed=True
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


import runpy,subprocess,sys,shutil,gzip,base64,copy
from pathlib import Path
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/002967/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():return model()['expand_output'](json.loads((D/'2026-Q3-output.json').read_text()))
def test_grg_four_literal_full_paths():
 computed={key:recompute(shock,pool,fail) for key,shock,pool,fail in [('base',0,.15,None),('margin_minus_1pp_y2',-.01,.15,None),('pool_tax25',0,.25,None),('named_qualification_fail_y3',0,.15,3)]}
 expected=output()
 for key,(rows,values) in computed.items():
  for a,b in zip(rows,expected['scenarios'][key]['rows']):
   for f in ['revenue','net_reinvestment','owner_net_profit','ending_cash','debt_end','ordinary','special','shares','distribution_per_share']:assert abs(a[f]-b[f])<1e-7
   for ae,be in zip(a['entities'],b['entities']):
    for af,bf in [('cash','cash_end'),('retained','retained_end'),('reserve','reserve_end'),('ownership','ownership_end'),('capital','capital_end')]:assert abs(ae[af]-be[bf])<1e-7
  for h,ends in values.items():
   for rate,vals in ends.items():
    for f,v in vals.items():assert abs(v-expected['horizon_checks'][key][h]['valuations'][rate][f])<1e-9

def test_grg_actual_legal_loss_tax_and_creditors():
 m=model();m['selftests']()
 w=m['liquidation_waterfall'](0,10,0,.5,0,.1,10,0,1,10)
 assert not w['feasible'] and w['creditor_shortfall']>0 and w['parent_total_cash']==0
 p=m['params']('zhong_creditor_shortfall');r=m['simulate'](p)
 assert not r['feasible'] and m['valuation'](r,.1)['value_per_share'] is None

def test_grg_all_paths_finite_capital_and_cash():
 d=output();m=model()
 for n,r in d['scenarios'].items():
  if not r['feasible']:continue
  m['horizon_check'](r)
  if n=='zhong_no_exit_extreme':continue
  for h in ['100','140']:
   assert d['horizon_checks'][n][h]['cash_above_operating_and_project_minima_owner']<1
  for z in r['rows']:
   assert z['ending_cash']>=-1e-8 and z['debt_end']>=-1e-8

def test_grg_fresh_single_file_output_expand(tmp_path):
 f=tmp_path/'2026-Q3.py';shutil.copy2(D/'2026-Q3.py',f)
 subprocess.run([sys.executable,str(f)],check=True,stdout=subprocess.DEVNULL)
 assert f.with_name('2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
 r=subprocess.run([sys.executable,str(f),'--expand'],check=True,capture_output=True,text=True)
 assert json.loads(r.stdout)==output()
