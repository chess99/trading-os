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


