"""Independently rebuild every scenario before reading any production output."""
import json, math
from pathlib import Path
n=22.116111770
start=sum((196.293,132.237,248.473,6.934,19.043,29.500,26.966,9.014,-67.429,-9.240,-100,-4.476))+(68013597*55+352207727*51.60)*.8686/1e9
specs={
'base':{},'lower':{'r':.09,'g':.005,'a':190},'upper':{'r':.08,'g':.01,'a':220},
'cyclical':{'p':[90,95,101,106,110],'c':[65,80,95,104,110],'d':[4.3,4.5,4.8,5,5.29],'u':[94,99,107,112,118],'collect':.8},
'structural':{'r':.095,'g':0,'roi':.08,'p':[95,90,85,82,80],'c':[80,70,65,60,60],'d':[4,3.8,3.5,3.3,3.2],'u':[92,86,80,76,73],'a':165,'tail':60,'realize':15,'cost':.05},
'upside':{'r':.08,'g':.015,'roi':.12,'p':[110,116,122,128,135],'c':[110,116,122,128,135],'d':[4.8,5.1,5.4,5.7,6],'u':[110,116,123,130,137],'a':225},
'sensitivity_r_plus_1pp':{'r':.095},'sensitivity_profit_minus_10pct':{'p':[90,92.7,95.4,97.2,99],'c':[80,85.7,91.4,95.2,99],'u':[93.6,96.3,99.9,102.6,106.2]},
'sensitivity_f0_minus_20':{'f':start-20},'sensitivity_delay_half_year':{'collect':.5},
'sensitivity_realization_20years':{'realize':20},'sensitivity_extra_tax_5pct':{'tax':.05},'sensitivity_legacy_capacity_650':{'legacy':650}}
computed={}
for name,s in specs.items():
 r=s.get('r',.085);g=s.get('g',.0075);roi=s.get('roi',.10)
 p=s.get('p',[100,103,106,108,110]);c=s.get('c',[90,96,102,106,110]);d=s.get('d',[4.66,4.8,4.97,5.11,5.29]);u=s.get('u',[104,107,111,114,118])
 funds=s.get('f',start);legal=liquid=owed=0.;quota=s.get('legacy',800);tax=s.get('tax',0.);vals=[];states=[]
 for j in range(40):
  op=p[j] if j<5 else p[4]*(1+g)**(j-4)
  flow=c[j] if j<5 else s.get('tail',p[4]*(1+g)*(1-g/roi))*(1+g)**(j-5)
  coupon=funds*.02;affiliate=6+j*.2 if j<5 else 0; sale=s.get('a',205) if j==5 else 0
  if j==5:fixed=(funds+sale)/s.get('realize',10)
  historical=min(max(0,funds+sale),fixed,quota) if j>4 else 0
  quota-=historical;head=max(0,.95*op-flow) if j>4 else 0
  principal=historical+min(max(0,funds+sale-historical),head)
  costs=principal*s.get('cost',.02)
  capacity=u[j] if j<5 else .95*op+coupon+max(0,principal-head)
  desire=d[j]*n if j<5 else max(0,flow+coupon+principal-costs)
  declaration=min(capacity*(1-tax),max(0,desire-legal),max(0,(funds+flow+coupon+affiliate+sale-costs-liquid-owed)*(1-tax)))
  taxes=declaration*tax/(1-tax)
  receipt=declaration*(s.get('collect',1) if j==0 else 1)
  available=funds+flow+coupon+affiliate+sale-costs-taxes
  paid=min(desire,max(0,available),max(0,legal+declaration),max(0,liquid+owed+receipt))
  liquid+=owed+receipt-paid;owed=declaration-receipt;legal+=declaration-paid
  funds=available-paid;vals.append(paid)
  states.append([funds,legal,liquid,owed,quota])
 tail=flow*(1+g)*(1-tax)/(r-g)
 value=(sum(v/(1+r)**(i+1) for i,v in enumerate(vals))+tail/(1+r)**40)/n
 tv=(sum(v/(1+r)**(i-4) for i,v in enumerate(vals[5:],5))+tail/(1+r)**35)/n
 computed[name]={'value':value,'terminal_per_share':tv,'distributions':[v/n for v in vals[:5]],'states':states}

import pytest
P=Path(__file__).resolve().parents[1]/"research/companies/CN/600941/models"
def test_mobile_independent_literal_all_states():
 production=json.loads((P/'2026-Q3-output.json').read_text())['cases']
 for name,x in computed.items():
  y=production[name]
  for key in ('value','terminal_per_share','distributions'):assert x[key]==pytest.approx(y[key],abs=1e-9)
  for s,row in zip(x['states'],y['rows']):
   assert s==pytest.approx([row[k] for k in ['financial_close','parent_available_profit','parent_cash','parent_receivable','legacy_profit_remittance_budget_remaining']],abs=1e-8)
def test_mobile_future_cash_and_necessary_capital():
 production=json.loads((P/'2026-Q3-output.json').read_text())['cases']
 for c in production.values():
  assert c['feasible']
  for k in ['financial_close','parent_cash','parent_receivable']:assert c['rows'][-1][k]==pytest.approx(0,abs=1e-8)
  assert c['value']==pytest.approx(sum(d/(1+c['r'])**(i+1) for i,d in enumerate(c['distributions']))+c['terminal_per_share']/(1+c['r'])**5)
 for row in production['structural']['rows'][5:]:assert row['necessary_reinvestment']==20
 assert production['sensitivity_delay_half_year']['distributions'][0]==pytest.approx(2.33)
