"""第四批独立现金复算：不调用正式估值函数。"""
import json
from decimal import Decimal as D
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN"

def aima_recalc(r,g,roic,shift='0'):
 r,g,roic,shift=map(D,(r,g,roic,shift));cash=D(2467+5970+1519+4400-5000-70);debt=D(2970);pc=D(1800);legal=D(1838);sl=D(5000);prev=D(22500);flows=[]
 for i,(rev,m,cap,da) in enumerate(zip([24000,26000,27500,28600,29700],['.055','.061','.065','.066','.066'],[2000,1500,1200,1100,1150],[850,900,950,1000,1050])):
  rev=D(rev);coupon=D([30,36,0,0,0][i]);cb=min(debt,D(2000)) if i<3 else D(0)
  ni=rev*(D(m)+shift)+cash*D('.015')-(debt-cb)*D('.035')-coupon-(200 if i==2 else 0)
  sc=cash-pc+ni+da-cap-(rev-prev)*D('.03')-(300 if i==0 else 0)+300
  principal=D(2000 if i==2 else 970 if i==4 else 0);pc-=300+principal;debt-=principal
  sl+=(ni+300)*D('.9');up=min(sl,(ni+300)*D('.8'),sc-1600);sc-=up;sl-=up;pc+=up;legal+=up-300
  div=min(ni/2,legal,pc-400,pc+sc-2000);pc-=div;legal-=div;cash=pc+sc;flows.append(div);prev=rev
  assert min(pc-400,sc-1600,legal,sl)>=0
 tv=rev*(1+g)*(D('.066')+shift)*(1-g/roic)/(r-g)+cash-2000-debt
 return float((sum(v/(1+r)**i for i,v in enumerate(flows,1))+tv/(1+r)**5)/D('863.320284'))

@pytest.mark.parametrize("rate,growth,roic,shift",[(".10",".015",".12","0"),(".095",".02",".15","0"),(".10",".015",".12","-.01")])
def test_aima_independent_legal_cash_and_debt_bridge(rate,growth,roic,shift):
 out=json.loads((ROOT/"603529/models/2026-Q3-output.json").read_text())
 expected=out['sensitivity']['margin_minus_1pp']['value']['value_per_share'] if shift!='0' else out['core_low' if rate=='.10' else 'core_high']['value_per_share']
 assert aima_recalc(rate,growth,roic,shift)==pytest.approx(expected,abs=1e-8)


def cfmoto_recalc(r,roi,stable,dm=0):
 rev=[9.4,5.8,8.2,2.5,1.7];gs=[[.12,.10,.09,.07,.05],[.15,.12,.10,.08,.06],[.14,.12,.10,.08,.06],[.2,.18,.15,.1,.08],[.12,.10,.09,.07,.05]]
 cash=14.18865953524-.34007697939;pc=8.15825519985-.5;shares=.153482763;re=4.15847860839;reserve=.083022672;wc=-5.9;lastrev=27.6;flows=[];cfp=other=0
 for t in range(5):
  rev=[v*(1+gs[i][t]) for i,v in enumerate(rev)];total=sum(rev);ms=[.09,.12,.08,[-.04,-.01,.01,.025,.03][t],.12];op=sum(v*(m+dm) for v,m in zip(rev,ms));zp=rev[3]*(ms[3]+dm)
  sbc=[.15,.08,.04,.02,.02][t];cap=[1.8,1.7,1.5,1.3,1.2][t];da=[.30,.38,.46,.53,.60][t];newwc=total*[-.19,-.17,-.15,-.15,-.15][t];dw=newwc-wc
  newshares=(.0023573+.0006+2.178763/241.7) if t==0 else .004151875*[0,.3,.3,.4,0][t]
  proceeds=(.0023573*97.95+.0006*145.91) if t==0 else newshares*(233.45-sum(flows))
  shares+=newshares;fin=max(cash-8*lastrev/27.6,0)*.015;pfin=max(pc-4*lastrev/27.6,0)*.015
  profit=.6*(op-zp)-.75*sbc+pfin;addition=min(max(shares/2-reserve,0),profit*.1);reserve+=addition;re+=profit-addition
  pc+=.6*(op-zp)+.45*da-.55*cap-.6*dw-.2+proceeds+pfin;cash+=op+da-cap-dw+fin+proceeds
  div=min(.4*(op-sbc+fin),re,cash-8*total/27.6,pc-4*total/27.6);cash-=div;pc-=div;re-=div;flows.append(div/shares);cfp+=rev[0]*.08;other+=op*.12
  assert pc>=4*total/27.6 and cash>=pc
  wc=newwc;lastrev=total
 parent=min(pc-4*total/27.6,re,cash-8*total/27.6);sub=cash-8*total/27.6-parent
 ca=parent+(min(.7*sub,cfp)*.9+min(.3*sub,other))*(1.015/(1+r))**3
 earnings=op;business=0
 for y,g in enumerate([.07,.06,.05,.04,.03],1):
  increase=earnings*g;earnings+=increase;business+=(earnings-increase/roi)/(1+r)**y
 business+=(earnings*(1+stable)-earnings*stable/roi)/(r-stable)/(1+r)**5
 tv=(business+ca+.1651183581)/shares
 return sum(v/(1+r)**y for y,v in enumerate(flows,1))+tv/(1+r)**5

@pytest.mark.parametrize("rate,roi,stable,shift",[(.115,.16,.025,0),(.105,.20,.03,0),(.11,.20,.03,-.01)])
def test_cfmoto_independent_legal_cash_growth_and_dilution(rate,roi,stable,shift):
 out=json.loads((ROOT/"603129/models/2026-Q3-output.json").read_text())
 expected=out['sensitivities']['margin_minus_1pp']['current'] if shift else out['core_low' if rate==.115 else 'core_high']['current']
 assert cfmoto_recalc(rate,roi,stable,shift)==pytest.approx(expected,abs=1e-8)
