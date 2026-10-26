"""Literal-input independent recomputation; imports no production model/config."""
import json, math, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN/002415/models"
import importlib.util
import pytest

def literal(case='base',delta=0,r=.1):
    a,b=70.,33.; c=32.60138445169;p=21.56377232985;l=40.85363986928
    debt=5.38108993023;ar=.1322042888;trade=20.33773929925;rows=[]
    for y in range(1,11):
        ga=.04 if y<=5 else .03;gb=.12 if y<=5 else [.08,.07,.06,.05,.04][y-6]
        ma=.175+delta;mb=.14+delta;rel=1.5 if y<=2 else 0.;wc=0.;imp=0.;support=0.;up=.4
        if case=='upside':ga=.06 if y<=5 else .035;gb=.18 if y<=5 else .08;ma+=.005;mb+=.01
        if case=='cyclical':
            ga=[-.03,.02,.08][y-1] if y<=3 else ga;gb=[.02,.05,.18][y-1] if y<=3 else gb
            if y<=2:ma-=.025;mb-=.02;up=.2
            rel=1.5 if y in (3,4) else 0.;wc=3. if y==1 else(-3. if y==3 else 0.)
            support=3. if y==1 else(-1.5 if y in (2,3) else 0.)
        if case=='structural':ga=-.03;gb=.03;ma=.125+delta;mb=.09+delta;rel=0.;wc=3. if y==1 else 0.;imp=3. if y==1 else 0.;support=4. if y==1 else 0.;up=.2
        prev=a+b;a*=1+ga;b*=1+gb;rev=a+b;op=a*ma+b*mb-imp
        cap=[2.2,1.6,1.][y-1] if y<=3 else rev*.007
        invest=.5*(rev-prev)+cap+wc-rel;flow=op-invest+imp
        interest=.03*debt;income=max(c-10*prev/103,0)*.015;floor=10*rev/103
        settle=min(trade,1.) if y<=3 and case not in ('cyclical','structural') else 0.;trade-=settle
        local=c-p+.3*flow-settle+support
        dec=max(0,min(.25*op*up,max(0,local-.4*floor)))
        pflow=.7*flow-interest+income+settle-support+.9*dec+ar;ar=.1*dec
        l+=.75*op-interest+income+dec
        pay=min(debt,2.);cb=c+flow-interest+income-pay;pb=p+pflow-pay
        new=max(0,floor-cb,.6*floor-pb);cb+=new;pb+=new
        d=max(0,min(.65*max(op-interest+income,0),cb-floor,pb-.6*floor,l))
        c=cb-d;p=pb-d;l-=d;debt=debt-pay+new
        rows.append(dict(dividend=d,group_cash=c,parent_cash=p,parent_legal=l,sub_declared=dec,operating_profit_common=op,revenue=rev,internal_trade_receivable=trade,cash_floor=floor,debt=debt))
    g=0 if case=='structural' else .02
    q,lag,loss=(.6,5,.1) if case=='structural' else (.8,3,.05)
    free=op*(1+g)*(1-g/.15)-rev*(1+g)*.007
    operating=free/(r-g)*(q+(1-q)*(1-loss)/(1+r)**lag)
    total=max(0,c-debt-floor);ps=min(total,max(0,p-.6*floor),l);cs=total-ps;settle=min(cs,trade)
    nav=(1.56698632401+.67280655052)*.9
    fin=ps/(1+r)+settle*.99/(1+r)+(cs-settle)*(1-loss)/(1+r)**lag+nav/(1+r)**lag-.00974956960*.48/(1+r)**lag
    pv=(sum(z['dividend']/(1+r)**(j+1) for j,z in enumerate(rows))+(operating+fin)/(1+r)**10)/9.16487155
    tv=(sum(z['dividend']/(1+r)**(j-4) for j,z in enumerate(rows) if j>=5)+(operating+fin)/(1+r)**5)/9.16487155
    return rows,pv,tv


@pytest.mark.parametrize("case,rate,endpoint",[(c,r,e) for c in ['base','cyclical','structural','upside'] for r,e in [(.10,'low'),(.09,'high')]])
def test_hikvision_literal_ten_year_balances_and_terminal(case,rate,endpoint):
    rows,pv,tv=literal(case,r=rate)
    out=json.loads((ROOT/'2026-Q3-output.json').read_text())['cases'][case]
    for a,b in zip(rows,out['rows'],strict=True):
        for k in a:assert a[k]==pytest.approx(b[k],abs=1e-10)
    assert pv==pytest.approx(out[endpoint]['value_per_share'],abs=1e-10)
    assert tv==pytest.approx(out[endpoint]['year5_per_share'],abs=1e-10)

@pytest.mark.parametrize("key,delta",[('margin_minus_1pp',-.01),('margin_plus_1pp',.01)])
def test_hikvision_literal_dominant_margin_sensitivity(key,delta):
    _,pv,tv=literal(delta=delta,r=.095)
    out=json.loads((ROOT/'2026-Q3-output.json').read_text())['sensitivities'][key]['mid']
    assert pv==pytest.approx(out['value_per_share'],abs=1e-10)
    assert tv==pytest.approx(out['year5_per_share'],abs=1e-10)

def test_hikvision_actual_functions_funding_old_receivable_and_all_future_cash():
    sp=importlib.util.spec_from_file_location('hikvision',ROOT/'2026-Q3.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
    assert m.hand_tests()['passed']
    out=json.loads((ROOT/'2026-Q3-output.json').read_text())
    for name,c in list(out['cases'].items())+list(out['sensitivities'].items()):
        for endpoint,rate in [('low',.10),('high',.09)]:
            t=c[endpoint]['tail'];g=0. if name=='structural' else .02;total=0
            for y in range(1,1201):
                free=t['next_annual_free_cash']*(1+g)**(y-1)
                total+=free*t['immediate_fraction']/(1+rate)**y
                total+=free*(1-t['immediate_fraction'])*(1-t['recovery_loss'])/(1+rate)**(y+t['delay_years'])
            assert total==pytest.approx(t['operating'],abs=1e-8)
            assert t['net_replacement']>0
            assert sum(t['financial_parts'].values())==pytest.approx(t['financial'],abs=1e-10)
            assert t['parent_stock']<=c['rows'][-1]['parent_legal']
        assert all(x['cumulative_borrowing']<=5 for x in c['rows'])
    assert out['cases']['structural']['low']['tail']['growth_capital']==0
