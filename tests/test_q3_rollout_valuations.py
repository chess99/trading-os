"""独立复算新一批Q3核心端点和支配性敏感性，不导入正式模型。"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "research/companies/CN"


def result(ticker):
    return json.loads((ROOT / ticker / "models/2026-Q3-output.json").read_text())


@pytest.mark.parametrize("margin,rate,key", [(0, .10, "core"), (.01, .095, "margin")])
def test_hikvision_independent_cash_and_value(margin, rate, key):
    actual = result("002415")
    main, innovation = 70., 33.
    cash = 36.60138445169 - 4.
    debt = 3.11165646664 + 1.09053677814 + .86492007394 + .31397661151
    dividends = []
    for year in range(1, 11):
        previous = main + innovation
        main *= 1 + (.04 if year <= 5 else .03)
        innovation *= 1 + (.12 if year <= 5 else [.08, .07, .06, .05, .04][year - 6])
        revenue = main + innovation
        profit = main * (.175 + margin) + innovation * (.14 + margin)
        capex = [2.2, 1.6, 1.][year - 1] if year <= 3 else .007 * revenue
        investment = .5 * (revenue - previous) + capex - (1.5 if year <= 2 else 0)
        financial = max(cash - 10 * previous / 103, 0) * .015 - debt * .03
        dividend = .65 * (profit + financial)
        repayment = min(debt, 2.)
        debt -= repayment
        cash += profit - investment + financial - dividend - repayment
        dividends.append(dividend)
    terminal = profit * 1.02 * (1 - .02 / .15) / (rate - .02)
    terminal += cash - debt - 10 * revenue / 103 + (1.56698632401 + .67280655052) * .9
    value = (sum(d / (1 + rate) ** t for t, d in enumerate(dividends, 1))
             + terminal / (1 + rate) ** 10) / 9.16487155
    expected = (actual["cases"]["base"]["low"]["value_per_share"] if key == "core"
                else actual["margin_sensitivity"]["0.01"])
    assert value == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("loss", [0, .01])
def test_supor_independent_cash_value(loss):
 out=result("002032")
 p=.5;s=1.60142209873-.01786188461+.0004462727-p;u=1.093300754;reserve=.330789524;sh=.796964626;rec=0;ds=[]
 for t in range(5):
  op=16*1.025**t*(.095-loss)+7*1.02**t*.047;profit=op+(p+s)*.02;own=op*.022+p*.02;declare=(profit-own)*.81;received=rec+declare*.9;rec=declare*.1
  iss=[.00102317,.0010115,.0010345,.0005215,0][t];fund=[.000480780*36.49+.000542390*37.89,.000498500*37.89+.000513000*38.82,.000513000*38.82+.000521500*31.21,.000521500*31.21,0][t];sh+=iss
  p+=own-.14*.022+received+fund-.15;s+=profit-.14-(own-.14*.022)-received+.15
  r=min((own+declare)*.1,max(0,sh*.5-reserve));reserve+=r;u+=own+declare-r;d=min(profit*.85,u,p,p+s);u-=d;p-=d;ds.append(d/sh)
 k=.095;g=.015;tv=(op*(1+g)*(1-g/.25)/(k-g)+p+s)/sh;v=sum(d/(1+k)**(i+1) for i,d in enumerate(ds))+tv/(1+k)**5
 target=(out['cases']['base']['valuations'] if not loss else out['sensitivity_domestic_margin_minus_1pp'])[0]['current_per_share'];assert abs(v-target)<1e-10;assert v == pytest.approx(target, abs=1e-10)


from decimal import Decimal as D

def _sieyuan_independent(out, rate, capital):
 p=out["inputs"];d=lambda x:D(str(x))
 r=d(rate);rev=d(p['revenue0']);coreprev=rev*d(p['margins'][0]);profitprev=d(p['profit0'])
 mc=d(p['mother_cash0']);sc=d(out['excess0'])-mc;ml=d(p['mother_legal0']);sl=d(0);receivable=d(0);divs=[];dps=[];profit0=None
 for i in range(15):
  nextrev=rev*(1+d(p['growth'][i]));core=nextrev*d(p['margins'][i]);mi=mc*d(.015);si=sc*d(.015)
  profit=core+mi+si;investment=(nextrev-rev)*d(capital) if i<10 else (core-coreprev)/d(.18)
  subcap=d(.002009057)*d(43.8) if i==0 else (d(.0062625)*(d(43.8)-dps[0]) if i==1 else d(0))
  mc+=d(.2)+mi-investment*d(.1)+subcap;sc+=core-d(.2)+si-investment*d(.9)
  ml+=d(.9)*(d(.2)+mi);sl+=d(.9)*(core-d(.2)+si)
  sc-=receivable;mc+=receivable;receivable=d(0)
  ordinary=(core-d(.2)+si-investment*d(.9))*d(p['upstream_rate'][i]);special=(max(d(0),sc-ordinary)/d(15-i)) if i>=10 else d(0)
  declaration=min(ordinary+special,sl,sc);paid=declaration*d(p['arrival'][i]);sl-=declaration;ml+=declaration;sc-=paid;mc+=paid;receivable=declaration-paid
  normal=profitprev*d(p['payout'][i]) if p['payout'][i]<1 else profit-investment
  request=normal+(max(d(0),mc+sc-normal)/d(15-i) if i>=10 else d(0));dividend=min(request,mc,ml,mc+sc)
  mc-=dividend;ml-=dividend;divs.append(dividend);dps.append(dividend/(d(.788772032) if i==0 else d(p['shares'])));profitprev=profit;coreprev=core;rev=nextrev
 assert abs(mc+sc)<d('1e-20')
 terminal=core*d(1.03)*(1-d(.03)/d(.18))/(r-d(.03))
 return float(sum(v/(1+r)**(i+1) for i,v in enumerate(dps))+terminal/(1+r)**15/d(p['shares']))


@pytest.mark.parametrize("rate,capital,key", [(.10,.45,"core_low"),(.095,.60,"sensitivity_capital_060")])
def test_sieyuan_independent_cash_value(rate, capital, key):
 out=result("002028")
 actual=_sieyuan_independent(out,rate,capital)
 expected=out[key]["value_per_share"] if key=="core_low" else out[key]
 assert actual == pytest.approx(expected,abs=1e-9)


def test_sieyuan_formal_value_and_actual_payment_hand_cases():
    import copy
    import importlib.util
    path = ROOT / "002028/models/2026-Q3.py"
    spec = importlib.util.spec_from_file_location("sieyuan_q3", path)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    p = copy.deepcopy(model.BASE)
    p.update(revenue0=10., profit0=1., growth=[0.] * 15, margins=[.1] * 15,
             capital_intensity=0., g=0., r=.1, payout=[1.] * 15,
             cash_yield=0., mother_direct_profit=1., upstream_rate=[0.] * 15,
             arrival=[1.] * 15, mother_cash0=0., mother_legal0=100.,
             sub_legal0=0., receivable0=0., excess0=0., shares=1., option_exercise=False)
    assert model.value(p)["value_per_share"] == pytest.approx(10., abs=1e-10)
    p.update(mother_direct_profit=0., mother_legal0=0.,
             special_release_start=1000, special_release_end=1001)
    rows = model.operate(p)
    assert [r["dividend"] for r in rows[:5]] == [0.] * 5
    assert rows[4]["cash"] == pytest.approx(5.)


def test_huaneng_conditional_asset_and_financing_limits():
    import importlib.util
    actual = result("600025")
    # Preserve the original 40-year operating-asset diagnostic inside the now-complete model.
    ev = 0.
    for year in range(1, 41):
        inflation = 1.005 ** (year - 1)
        runoff = max(0., min(1., (25 - year) / 10)) if year > 15 else 1.
        revenue = (25.6 + 1.6 * runoff) * inflation
        tax = .15 if year <= 4 else .25
        fcf = (revenue - 6.2 * inflation - 7.5 * inflation) * (1 - tax)
        fcf += (7.5 - 4.5) * inflation
        if year in (20, 40):
            fcf -= 8 * inflation
        ev += fcf / 1.06 ** year
    assert ev == pytest.approx(actual["scenarios"]["engineering_low"]["mature"]["ev"], abs=1e-9)
    assert actual["value_range"] is not None and actual["return_model"] is not None
    spec = importlib.util.spec_from_file_location("huaneng_q3", ROOT / "600025/models/2026-Q3.py")
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    assert model.funding_step(1, 3, 2, 6, 4, 0, 2) == (2, 2, 0)
    with pytest.raises(ValueError):
        model.funding_step(1, 3, 2, 9, 0, 0, 2)
