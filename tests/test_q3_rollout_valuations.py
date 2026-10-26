"""独立复算新一批Q3核心端点和支配性敏感性，不导入正式模型。"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "research/companies/CN"


def result(ticker):
    return json.loads((ROOT / ticker / "models/2026-Q3-output.json").read_text())


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
