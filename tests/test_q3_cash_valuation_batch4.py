"""第四批独立现金复算：不调用正式估值函数。"""
import json
from decimal import Decimal as D
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN"

def baiya_recalc(rate,margin_delta='0'):
 revenue=list(map(D,['3550','3760','4020','4260','4470','4649','4812','4956','5105','5258']))
 margin=list(map(D,['.070','.080','.088','.094','.096','.096','.095','.094','.093','.092']))
 cap=list(map(D,['140','145','150','155','160','164','168','172','177','182']))
 cash=D('342.469072')+D('140.541525')-D('34.700')-D('3.544871')-D('26.012546')-150
 lastwc=D('355.9134314');lastbuffer=D(150);flows=[];r=D(rate)
 for t,(rev,m,investment) in enumerate(zip(revenue,margin,cap)):
  tax=D('.16') if t<4 else D('.23') if t==4 else D('.25')
  profit=rev*(m+D(margin_delta))*(1-tax)
  wc=rev/10;buffer=150*rev/D('3559.134314')
  cashflow=profit+100+2*t-investment-(wc-lastwc)-(buffer-lastbuffer)
  dividend=(profit-(D(50)/3 if t<3 else 0))*D('.60')
  cash+=cashflow-dividend;flows.append(dividend);lastwc=wc;lastbuffer=buffer
 steady=revenue[-1]*D('1.02')*(margin[-1]+D(margin_delta))*D('.75')+(118-cap[-1])*D('1.02')-lastwc*D('.02')-lastbuffer*D('.02')
 release=(cash+30)*sum((1+r)**(-t) for t in (1,2,3))/3
 terminal=steady/(r-D('.02'))+release
 current=(sum(v/(1+r)**t for t,v in enumerate(flows,1))+terminal/(1+r)**10)/D('429.647790')
 return float(current)

@pytest.mark.parametrize("rate,dm",[(".11","0"),(".10","0"),(".10","-.01")])
def test_baiya_independent_full_period_value(rate,dm):
    out=json.loads((ROOT/"003006/models/2026-Q3-output.json").read_text())
    expected=out['margin_minus_1pp']['current_value'] if dm!='0' else out['scenarios']['base'][str(float(rate))]['current_value']
    assert baiya_recalc(rate,dm)==pytest.approx(expected,abs=1e-8)

def test_baiya_independent_entity_cash_conservation():
    o=json.loads((ROOT/"003006/models/2026-Q3-output.json").read_text())
    for case in o['scenarios'].values():
     for result in case.values():
      pc=376.877862-135;sc=418.753180-376.877862-15;debt=0
      for row in result['rows']:
       pc+=.9*(row['fcfe']+row['external_interest'])-row['external_interest']+row['intercompany_interest']-row['intercompany_support']+row['intercompany_repayment']+(row['debt']-debt)-row['dividend']
       sc+=.1*(row['fcfe']+row['external_interest'])-row['intercompany_interest']+row['intercompany_support']-row['intercompany_repayment']
       assert abs(pc-row['parent_surplus_cash'])<1e-7 and abs(sc-row['subsidiary_surplus_cash'])<1e-7
       assert min(pc,sc)>=-1e-7;debt=row['debt']
      pc=pc-debt+30
      for rr in result['release_schedule']:
       pc+=.9*rr['operating_fcfe']+rr['subsidiary_new_declaration']-rr['parent_holder_payment']
       sc+=.1*rr['operating_fcfe']-rr['subsidiary_new_declaration']
       assert abs(pc-rr['parent_cash'])<1e-7 and abs(sc-rr['subsidiary_cash'])<1e-7
       assert min(pc,sc)>=-1e-7


def qiaqia_recalc(rate,shift='0'):
 c=sum(map(D,['3.11039224728','1.23308011310','.38220270827','.35562269185']))-sum(map(D,['.9895','1.54880849806','.00364909872','.03593239247','.001477064','.015','.008']))
 shares=D('.505856969')-D('.009460417');treasury=D('.009460417');flows=[]
 for i,(rev,margin,cap,wc) in enumerate(zip(['7.7','8.1','8.5','8.9','9.3'],['.093','.096','.097','.097','.097'],['.13','.10','.08','.08','.08'],['.1','.072','.072','.072','.072'])):
  profit=D(rev)*(D(margin)+D(shift))*D('.75')-D('.005');buy=D('.048522936') if i==0 else D(0);shares-=buy/20;treasury+=buy/20
  issuance=treasury*20 if i==1 else D(0)
  if i==1:shares+=treasury;treasury=D(0)
  dividend=profit*D('.7');c=c*D('1.015')+profit-D(cap)-D(wc)-buy+issuance-dividend;flows.append(dividend/shares)
 r=D(rate);terminal=(D('9.3')*D('1.02')*(D('.097')+D(shift))*D('.75')-D('.0051')-D('9.3')*D('.02')*(D('.5')+D('.8')/D('7.4')))/(r-D('.02'))+c-D('9.3')*D('.8')/D('7.4')
 return float(sum(v/(1+r)**i for i,v in enumerate(flows,1))+terminal/shares/(1+r)**5)

@pytest.mark.parametrize("rate,shift",[(".105","0"),(".095","0"),(".10","-.01")])
def test_qiaqia_independent_opening_bridge_and_cash(rate,shift):
    out=json.loads((ROOT/"002557/models/2026-Q3-output.json").read_text())
    expected=out['sensitivity']['margin_minus_1pp']['value'] if shift!='0' else out['core'][str(float(rate))]['value']
    assert qiaqia_recalc(rate,shift)==pytest.approx(expected,abs=1e-9)


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
