"""独立literal先建年度现金与价值，保存后才读取正式输出。不导入正式模型。"""
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"research/companies/CN/600674/models"

def calc(rate,shift=0):
    volts=[88,89,91,94,95,97,102,106,108,112];prices=[.28,.279,.278,.277,.276,.275,.275,.275,.275,.275]
    others=[1.4,1.7,2.1,2.4,2.8,3.1,3.2,3.3,3.8,4.2];costs=[5.1,5.2,5.3,5.4,5.5,5.6,5.8,6,6.2,6.4]
    deps=[6.3,6.35,6.4,6.5,6.6,6.8,7.1,7.4,7.7,8.1];caps=[15,16,16,15,14,13,12,11,10,9]
    injections=[1.5,1.4,1.2,1,.8,.6,.5,.4,.3,.2];divs=[3.8,4,4.2,4.5,4.8,5.2,5.8,6.5,7,7.5]
    nci=[.04,.045,.05,.055,.06,.07,.08,.09,.1,.11];assoc=[.45,.48,.51,.55,.6,.65,.7,.75,.8,.85]
    ctl=[.22,.23,.25,.28,.3,.33,.36,.38,.4,.42];hc=[.4,.41,.42,.43,.44,.46,.48,.5,.52,.54]
    direct=[.4,.4,.4,.5,.7,.7,.7,.7,.7,.7];newdebt=[1,.6,.4,.1,0,0,0,0,0,0]
    targets=[.52,.54,.57,.6,.63,.7,.78,.86,.95,1.04];N=4.874606828
    yDebt=90.;yUP=15.;yStat=8.87038517457;yReg=50.7;yCash=0
    pDebt=14.185261;pCash=1.5;pUP=18.09076086388;pStat=.91234247476
    rec=1.104546825;rows=[]
    for year in range(1,161):
        j=min(year-1,9);tax=.2 if year<5 else .25
        ebit=volts[j]*(prices[j]+shift)+others[j]-costs[j]-deps[j]
        invest=injections[j] if year<=10 else 0;cap=caps[j] if year<=10 else deps[j]
        yReg+=invest/.48
        olddue=rec/.48 if year==1 else 0
        wish=divs[j]/.48 if year<=10 else 1e6
        def f(q):
            if year<=10:loan=max(-yDebt,(cap+q-invest/.48-(ebit-.026*yDebt)*(1-tax)-deps[j]+.2+nci[j])/(1-.026*(1-tax)/2))
            else:loan=-min(yDebt,.25*max(0,(ebit-.026*yDebt)*(1-tax)-nci[j])/(1-.25*.026*(1-tax)/2))
            interest=.026*(yDebt+loan/2);earn=(ebit-interest)*(1-tax)-nci[j]
            return loan,earn
        for _ in range(100):
            loan,earn=f(wish)
            sr=min(.1*max(0,earn+min(0,yUP)),max(0,.5*yReg-yStat))
            cash=yCash+earn+deps[j]-cap-(.2 if year<=10 else 0)+invest/.48+loan
            bound=min(wish,max(0,yUP+earn-sr)+olddue,max(0,cash))
            if abs(bound-wish)<1e-11:break
            wish=bound
        loan,earn=f(wish);yDebt+=loan
        sr=min(.1*max(0,earn+min(0,yUP)),max(0,.5*yReg-yStat))
        yCash+=earn+deps[j]-cap-(.2 if year<=10 else 0)+invest/.48+loan
        newdiv=min(max(0,wish-olddue),max(0,yCash-olddue),max(0,yUP+earn-sr))
        yCash-=newdiv+olddue;yUP+=earn-sr-newdiv;yStat+=sr
        fin=.06 if year<=12 else 0;gross=2.787239843 if year==12 else 0;friction=.147239843 if year==12 else 0
        othercash=.24 if year<=10 else (assoc[j]+ctl[j])*(.8 if year<=20 else 1)
        costdiv=min(ctl[j],.05+.005*j) if year<=10 else ctl[j]*(.8 if year<=20 else 1)
        b=newdebt[j] if year<=10 else 0;pDebt+=b
        overhead=hc[j] if year<=10 else .54-.026*(14.185261+2.1)+.026*pDebt
        income=.48*earn+assoc[j]+costdiv+fin-overhead-friction
        inflow=.48*newdiv+(rec if year==1 else 0)+othercash+fin
        pCash+=inflow-overhead-invest-(direct[j] if year<=10 else 0)+b+gross-friction
        repay=min(pDebt,max(0,(inflow-overhead)*.2),max(0,pCash-1)) if year>10 else 0
        pDebt-=repay;pCash-=repay
        requested=targets[j]*N if year<=10 else max(0,inflow-overhead-repay)
        if year>=15:requested=max(requested,pCash-1)
        eligible=max(0,income+min(0,pUP));s=min(.1*eligible,max(0,.5*N-pStat))
        if year<=10:s=max(s,.1*eligible)
        reserve=s+(.15*eligible if year<=10 else 0)
        paid=min(max(0,requested),max(0,pCash-1),max(0,pUP+income-reserve))
        pUP+=income-reserve-paid;pStat+=s;pCash-=paid
        rows.append({'year':year,'dps':paid/N,'yl_debt':yDebt,'parent_cash':pCash,'parent_profit':income})
    tv=rows[-1]['dps']/rate
    pv=sum(x['dps']/(1+rate)**x['year'] for x in rows)+tv/(1+rate)**160
    tv5=sum(x['dps']/(1+rate)**(x['year']-5) for x in rows[5:])+tv/(1+rate)**155
    return {'value':pv,'terminal_year5':tv5,'rows':rows}

answers={'core_low':calc(.075),'core_mid':calc(.07),'price_minus_001':calc(.07,-.01)}

import pytest
def test_chuantou_independent_literal_three_full_paths():
 actual=json.loads((P/'2026-Q3-output.json').read_text())
 for k,v in answers.items():
  for field in ['value','terminal_year5']:assert v[field]==pytest.approx(actual[k][field],abs=1e-9)
  for a,b in zip(v['rows'],actual[k]['rows']):
   for field in ['dps','yl_debt','parent_cash','parent_profit']:assert a[field]==pytest.approx(b[field],abs=1e-8)
def test_chuantou_all_paths_future_capital_and_no_idle_money():
 actual=json.loads((P/'2026-Q3-output.json').read_text())
 for k,c in actual.items():
  if not isinstance(c,dict) or 'rows' not in c:continue
  assert c['remaining_yl_cash']==pytest.approx(0,abs=1e-8)
  assert c['remaining_parent_cash']==pytest.approx(1,abs=1e-8)
  assert c['remaining_financial_assets']==0
  for row in c['rows']:
   assert row['yl_capital_return']['gross']==0
   assert row['yl_investment_book']>0
   if row['year']>10:assert row['yl_capex']>7
  assert c['value']==pytest.approx(sum(d/(1+c['params']['rate'])**(i+1) for i,d in enumerate(c['distributions_per_share']))+c['terminal_year5']/(1+c['params']['rate'])**5)
 assert max(actual['convergence'].values())-min(actual['convergence'].values())<1e-9
