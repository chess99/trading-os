"""Independent 240-year owner-receipt computation. Literal source/forecast inputs.
No production import, no output/input read until all independent calculations finish.
"""
import json
from pathlib import Path

def calc(rate=.10,growth=.02,scale=1,claim=False,upstream_budget=.55,
         elective=.10,source_payout=.4,release=.1,block=0,parent_assets=1.448841570168,structural=False,optional_end=10,source_end=10):
    shares=2.213939223
    profits=[4.6*scale,4.85*scale,5.1*scale,5.35*scale,5.6*scale]
    for g in [.045,.04,.035,.03,.025]:profits.append(profits[-1]*(1+g))
    if structural:profits=[3.6]*10;claim=True;growth=0.
    liquid=7.653017811+5.173804854-.125741490+.20+.119222862+.85
    debt=.12819+.048795750+.163529638+.020282517
    group=liquid-debt-.271520666-5.5-.677
    parent=3.651901050+4.176504249-4
    retained=5.107252998; reserve=3.92962093934
    legal=.269*7.7671 if claim else 0
    group-=legal;parent-=legal;first=[]
    for i in range(5):
        missing=(.55-upstream_budget)*scale+(upstream_budget*scale if claim and i==0 else 0)
        if structural:missing=.55
        pp=(3. if structural else [4,4.2,4.4,4.6,4.8][i]*scale)-missing-(legal+.02987976755 if claim and i==0 else 0)
        available=max(0,min(pp,retained+pp))
        mandatory=min(.1*available,max(0,shares/2-reserve))
        voluntary=max(0,elective*available-mandatory);reserve+=mandatory+voluntary
        retained+=pp-mandatory-voluntary
        parent += (2.8 if structural else [3.8,4,4.2,4.4,4.6][i]+[4,4.2,4.4,4.6,4.8][i]*(scale-1))-missing
        group=group*1.015+profits[i]-(.7 if structural else [.5,.6,.65,.7,.75][i])
        div=max(0,min((1.2 if structural else [2,2.1,2.2,2.3,2.4][i])*shares,parent,group,retained))
        group-=div;parent-=div;retained-=div
        first.append(dict(dps=div/shares,closing_liquid=group,parent_closing_liquid=parent,parent_closing_retained=retained,parent_closing_statutory_reserve=reserve))
    source=group-parent;allowance=0.;future=[];tv=0.;previous=profits[4]
    investments=(.939243362+1.358293889)*.8+.807763804+.677*.8
    direct=(3.-.55)/3.6 if structural else 4.25/5.6
    for year in range(6,241):
        if year<=10:
            profit=profits[year-1];investment=(profit-previous)/.2;parent_portion=.60
        else:
            profit=previous*(1+growth);investment=profit*growth/.15;parent_portion=direct
        if structural:investment=.7
        mother_profit=profit*direct;source_profit=profit-mother_profit
        mi=parent*.015;si=source*.015
        recovery=investments if year==10 else 0
        mother_recovery=parent_assets if year==10 else 0
        mothercash=parent+mother_profit-investment*parent_portion+mi+mother_recovery
        sourcecash=source+source_profit-investment*(1-parent_portion)+si+recovery-mother_recovery
        generated=source_profit+si-(.2*((.939243362+1.358293889)-(.35057896043+.71856575228))+.677*.2 if year==10 else 0)
        eligible=max(0,min(generated,allowance+generated));buffer=.1*eligible if year<=source_end else 0.;allowance+=generated-buffer
        ask=source_payout*max(0,generated)+release*max(0,source)
        if year<=5+block:ask=0
        received=max(0,min(ask,sourcecash,allowance));allowance-=received
        profit_at_mother=mother_profit+mi+received-(.2*(.35057896043+.71856575228) if year==10 else 0)
        legalprofit=max(0,min(profit_at_mother,retained+profit_at_mother))
        compulsory=min(.1*legalprofit,max(0,shares/2-reserve));elect=max(0,(elective if year<=optional_end else 0.)*legalprofit-compulsory)
        reserve+=compulsory+elect;retained+=profit_at_mother-compulsory-elect
        mothercash+=received
        payment=max(0,min(mothercash,retained));retained-=payment
        parent=mothercash-payment;source=sourcecash-received
        tv+=payment/(1+rate)**(year-5)
        future.append(dict(year=year,group_profit=profit,net_reinvestment=investment,parent_voluntary_reserve=elect,source_profit_buffer=buffer,parent_cash=parent,source_cash=source,parent_retained=retained,source_earnings_budget=allowance,dividend=payment,source_upstream=received))
        previous=profit
    tv/=shares
    pv=sum(row['dps']/(1+rate)**(i+1) for i,row in enumerate(first))+tv/(1+rate)**5
    return dict(per_share=pv,terminal=tv,rows=first,tail_rows=future)

computed={'owner_low':calc(.105,.015,.95,True),'owner_base':calc(),'owner_high':calc(.095,.025,1.05),
 'owner_sensitivity_profit_down_10pct':calc(scale=.9),'owner_sensitivity_r_up_1pct':calc(rate=.11),
 'tail_sensitivities/no_routine_profit_dividend_with_asset_recovery':calc(upstream_budget=0,source_payout=0,release=.10),
 'tail_sensitivities/source_half_and_slow':calc(source_payout=.2,release=.05),
 'capital_governance_sensitivities/normal_no_upstream_five_years':calc(upstream_budget=0,source_payout=.2,release=.05,block=5)}
computed['owner_structural']=calc(.115,structural=True,source_payout=.2,release=.05)
for label,stop in [('optional_stop_after_Y5',5),('optional_stop_after_Y20',20),('optional_perpetual_boundary',10000)]:
    computed['tail_policy_sensitivities/'+label]=calc(optional_end=stop,source_end=stop)
computed['tail_policy_sensitivities/structural_stop_Y20']=calc(.115,structural=True,source_payout=.2,release=.05,optional_end=20,source_end=20)

import pytest
P=Path(__file__).resolve().parents[1]/"research/companies/CN/600066/models"
def test_yutong_literal_13_full_cash_paths():
 production=json.loads((P/'2026-Q3-output.json').read_text())
 for key,a in computed.items():
  z=production
  for part in key.split('/'):z=z[part]
  for k in ['per_share','terminal']:assert a[k]==pytest.approx(z[k],abs=1e-9)
  for i,row in enumerate(a['rows']):
   for k,v in row.items():assert v==pytest.approx(z['rows'][i][k],abs=1e-8)
  for i,row in enumerate(a['tail_rows']):
   for k,v in row.items():assert v==pytest.approx(z['tail_recovery']['rows'][i][k],abs=1e-8)
def test_yutong_structural_maintenance_and_new_cash_realization():
 x=json.loads((P/'2026-Q3-output.json').read_text())
 s=x['owner_structural']['tail_recovery']
 for row in s['rows']:assert row['group_profit']-row['net_reinvestment']==pytest.approx(2.9)
 for c in s['later_cash_cohorts'].values():assert c['unpaid']<1e-8
 assert s['rows'][-1]['parent_cash']==pytest.approx(0,abs=1e-8)
 assert s['rows'][-1]['source_cash']==pytest.approx(18.326023,abs=.002)
 assert x['owner_base']['per_share']==pytest.approx(x['tail_sensitivities']['long_horizon_320']['per_share'],abs=1e-6)
 for key in ['owner_low','owner_base','owner_high','owner_cyclic','owner_structural','owner_upside']:
  for c in x[key]['tail_recovery']['later_cash_cohorts'].values():assert c['unpaid']<1e-8
