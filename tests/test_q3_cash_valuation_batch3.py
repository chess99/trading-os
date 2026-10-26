"""第三批公司独立现金复算；读取假设数据，不调用正式估值函数。"""
import json
from decimal import Decimal as D, localcontext
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN"
S=D('.639826824')
def d(x):return D(str(x))
def check(p,rate,start=0):
 pc,sc,pr,sr=map(d,[p['parent_cash'],p['sub_cash'],p['parent_re'],p['sub_re']]);total=[]
 for j in range(10):
  owner=d(p['revenues'][j])*d(p['margins'][j])*(1-d(p['tax']))-d(p['minority'][j])
  frac=d(p['parent_share']);i1=pc*d(p['yield_net']);i2=sc*d(p['yield_net'])
  invest=d(p['maintenance'][j])+d(p['other_growth'][j])+d(p['nwc'][j])-d(p['da'][j])
  fcf=owner-invest-d(p['project'][j]);transfer=d(p['internal_repayment']) if j==0 else D(0)
  pre_sub=sc+(owner-invest)*(1-frac)+i2+transfer
  subprofit=owner*(1-frac)+i2
  sr+=subprofit-D('.1')*max(D(0),subprofit)
  u=max(D(0),min(d(p['sub_payout'])*(owner*(1-frac)+i2),sr,pre_sub-d(p['sub_floor'])))
  sr-=u;sc=pre_sub-u
  pr+=owner*frac+i1+u
  before=pc+(owner-invest)*frac-d(p['project'][j])+i1+u-transfer
  pay=max(D(0),min(d(p['payout'])*(owner+i1+i2),pr,before-d(p['parent_floor'])))
  pr-=pay;pc=before-pay
  total.append((pay,owner,pc+sc,pr,pc))
 r=d(rate);g=d(p['g']);term=total[-1][1]*(1+g)*(1-g/d(p['roic']))/(r-g)+total[-1][2]-d(p['parent_floor'])-d(p['sub_floor'])
 value=(sum(z[0]/(1+r)**(i+1-start) for i,z in enumerate(total) if i>=start)+term/(1+r)**(10-start))/S
 return float(value),[[float(a) for a in z] for z in total]

@pytest.mark.parametrize("margin_loss,rate,key", [(0,.095,"base_low"),(0,.085,"base_high"),(.02,.09,"margin_minus_2pp")])
def test_donge_independent_legal_cash_and_value(margin_loss,rate,key):
    out=json.loads((ROOT/"000423/models/2026-Q3-output.json").read_text())
    p=out["assumptions"]
    p["margins"]=[x-margin_loss for x in p["margins"]]
    with localcontext() as ctx:
        ctx.prec=35
        value,rows=check(p,rate)
    actual=out[key] if key in out else out["scenarios"][key]
    assert value == pytest.approx(actual["value"],abs=1e-9)
    for row,expected in zip(rows,actual["rows"],strict=True):
        for number,name in zip(row,["dividend","operating_profit_common","cash","parent_retained","parent_cash"],strict=True):
            assert number == pytest.approx(expected[name],abs=1e-9)


def hisense_independent(F,B,k,release):
    own=D('.492');cash=[D(B),D(F)-own*D(B)-D('1.5'),D('1.5')]
    law=[D('5.5'),D(6),D('6.03298055478')];hist=[]
    for t in range(1,201):
        b=[D('2.3'),D('2.4'),D('2.5'),D('2.6'),D('2.7')][min(t,5)-1]
        q=[D('.35'),D('.45'),D('.6'),D('.7'),D('.8')][min(t,5)-1]
        if t>5:b*=D('1.015')**(t-5);q*=D('1.015')**(t-5)
        inv=[D('.45'),[D('.5'),D('.45'),D('.4'),D('.35'),D('.35')][min(t,5)-1]] if t<=5 else [b*D('.015')/D('.14'),q*D('.015')/D('.14')]
        before=cash.copy();profits=[b+before[0]*D('.015'),q+before[1]*D('.015')];pays=[]
        for j in range(2):
            cash[j]+=profits[j]-inv[j];law[j]+=profits[j]-max(D(0),profits[j])*D(".10")
            desired=([D('.7')*b,D('.5')*q][j] if t<=5 else max(D(0),[b,q][j]-inv[j])*min(D(1),D('.6')+D('.08')*(t-5))+before[j]*D('.015')+D(release)*before[j]*min(D(1),D('.6')+D('.08')*(t-5)))
            pay=max(D(0),min(desired,cash[j],law[j]));cash[j]-=pay;law[j]-=pay;pays.append(pay)
        inc=pays[0]*own+pays[1]+before[2]*D('.015');cash[2]+=inc;law[2]+=inc-before[2]*D(".015")*D(".10")
        desired=[D('.65'),D('.75'),D('.85'),D('.95'),D('1.05')][t-1]*D("1.384861171") if t<=5 else inc+D(release)*before[2]*min(D(1),D('.6')+D('.08')*(t-5))
        d=max(D(0),min(desired,cash[2],law[2]));cash[2]-=d;law[2]-=d
        hist.append(d)
    val=sum(z/(1+D(k))**t for t,z in enumerate(hist,1))/D("1.384861171")
    tv=sum(hist[t-1]/(1+D(k))**(t-5) for t in range(6,201))/D("1.384861171")
    return val,tv

@pytest.mark.parametrize("F,B,r,release,key", [("19","12",".105",".02","low"),("23","4",".095",".04","high"),("21","8",".10","0","no_principal_release")])
def test_hisense_independent_long_cash(F,B,r,release,key):
    out=json.loads((ROOT/"000921/models/2026-Q3-output.json").read_text())
    got,tv=hisense_independent(F,B,r,release)
    actual=out["owner_model"].get(key,out["owner_sensitivity"].get(key))
    assert float(got)==pytest.approx(actual["value_per_share"],abs=1e-8)
    assert float(tv)==pytest.approx(actual["terminal_year5"],abs=1e-8)


def test_zijin_independent_resource_cash_and_raw_equity_bridge():
    import importlib.util
    spec=importlib.util.spec_from_file_location("zijin_inputs",ROOT/"601899/models/2026-Q3.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    x=json.loads((ROOT/"601899/models/2026-Q3-output.json").read_text())
    for name,prices,wacc in [('core_low',{'au':810,'cu':77000,'li':85000},.09),('base',{'au':850,'cu':80000,'li':90000},.085),('gold_minus_100',{'au':750,'cu':80000,'li':90000},.085)]:
     remaining=[a[4]*(.85 if a[1]=='li' else 1) for a in m.MINES];cash=[]
     for t in range(1,41):
      f=0.;infl=1.015**(t-1)
      for j,(label,metal,own,plan,res,life,cost,da,maint,cap) in enumerate(m.MINES):
       q=min(remaining[j],(plan[t-1] if t<=5 else plan[-1]*.995**(t-5)) if t<=life else 0);remaining[j]-=q;den=1000 if metal=='au' else 1e6
       rev=q*prices[metal]*infl/den;ebit=rev*.945-q*cost*infl*1.003**(t-1)/den;taxed=ebit*.76 if ebit>0 else ebit
       f+=own*(taxed+q*(da-maint)*infl/den-(cap[t-1] if t<=5 else 0)-(rev*.015 if t<=5 else 0))
      fade=1 if t<=5 else max(0,(26-t)/21)
      f+=(8+min(t-1,4)*.5)*infl*fade-(1.8 if t<=5 else .6)*infl*fade-7.5*infl*(1 if t<=5 else max(.15,(41-t)/36))
      cash.append(f);assert abs(f-x['cases'][name]['operations'][t-1]['fcf'])<1e-8
     pv=sum(c/(1+wacc)**(i+1) for i,c in enumerate(cash))-(8*1.015**39-18)/(1+wacc)**40-18
     p=x['cases'][name]['parameters'];cn=6.119465016+(76.776449446-6.119465016)*p['subcash_factor']-(10.006048855+.310902731*29.82*.88)+(6.033056952-.251781916-.535727062-.152391571)*.2585+.310902731*29.82*.88*.2585
     pd=96.586908041;debt=pd+(169.909564957-pd-21.5)*p['subdebt_factor']+24.4972+(.907076+.916897+.315435+.075532+.066728-.129481+2.744807)*.495*7-9.284632475
     assets=((13.141995727+15.006467342+2.694675079)*.8+3.242001754+1.175240077+(4.741664751+.440994803)*.262+.388460245+.288414821+.141983058-.7-(3.333987700-1.425577447))*p['assets_factor']
     value=(pv-debt+cn+assets+(.077474592*18.56+.0262*10.7)/(1+wacc))/26.616998241
     assert abs(value-x['cases'][name]['values']['current'])<1e-8;assert value>0


def calculate(rate,extra,coal):
 c=[D('45.426'),D('45.677')];b=[D('52.8'),D('109.752')];l=[D('165.353'),D(0)];ds=[]
 for t in range(1,41):
  scale=D(1) if t<=25 else D(40-t)/15;grow=1+D('.005')*min(t-1,5)
  tax=D('.22') if t<5 else D('.245') if t==5 else D('.25')
  floor=[10*scale+8*min(D(1),max(D(0),D(t-30)/5)),15*scale]
  cap=(D(57 if t<4 else 52 if t<6 else 46)+D(extra))*scale
  ni=[]
  for j,(eb,da,frac,minefrac,wcf,ir) in enumerate([(28,'5.6','.24','.15','.3','.025'),(64,'29.4','.76','.85','.7','.03')]):
   pr=(eb*scale*grow+D(coal)*D('.38')*D('.94')*scale*D(wcf)-b[j]*D(ir)+c[j]*D('.015'))*(1-tax);ni.append(pr)
   c[j]+=pr+D(da)*scale-cap*D(frac)-(D('7.0566')*D(minefrac)+scale*D(wcf) if t<=5 else 0)
  income=D('1.8') if t<=10 else D(0);c[0]+=income+(65 if t==10 else 0)
  for j in range(2):
   gap=max(D(0),floor[j]-c[j]);c[j]+=gap;b[j]+=gap
  reserves=[v/max(1,40-t) if t>25 else D(0) for v in b]
  l[1]+=ni[1]-max(D(0),ni[1])/10
  up=max(D(0),min(ni[1]*D('.75'),l[1],c[1]-floor[1]-reserves[1]))
  c[1]-=up;l[1]-=up;c[0]+=up*D('.72')
  legal=ni[0]+income+up*D('.72');l[0]+=legal-max(D(0),legal)/10
  net=ni[0]+D('.72')*ni[1]+(3 if t<=10 else 0)
  if t<=2:
   gap=min(max(D(0),D('.65')*net-max(D(0),c[0]-floor[0])),max(D(0),100-b[0]));b[0]+=gap;c[0]+=gap
  dividend=max(D(0),min(D('.7')*net,l[0],c[0]-floor[0]-reserves[0]));c[0]-=dividend;l[0]-=dividend
  for j in range(2):
   repay=min(b[j],max(D(0),c[j]-floor[j]));b[j]-=repay;c[j]-=repay
  u=min(max(D(0),c[1]-floor[1]),max(D(0),l[1])) if b[1]<D('1e-9') else D(0)
  c[1]-=u;l[1]-=u;c[0]+=u*D('.72');l[0]+=u*D('.648')
  special=min(max(D(0),c[0]-floor[0]),max(D(0),l[0])) if b[0]<D('1e-9') else D(0)
  c[0]-=special;l[0]-=special;dividend+=special
  if t==40:dividend+=c[0]-b[0]+D('.72')*(c[1]-b[1])-8
  ds.append(dividend/D('21.689434304'))
 return sum(v/(1+D(rate))**t for t,v in enumerate(ds,1)),ds

@pytest.mark.parametrize("name,r,cap,coal", [('core_low','.085','2','0'),('base','.08','0','0'),('coal_minus20','.08','0','-20')])
def test_shenhua_decimal_complete_life_cash(name,r,cap,coal):
    out=json.loads((ROOT/"601088/models/2026-Q3-output.json").read_text())
    value,flows=calculate(r,cap,coal)
    assert float(value)==pytest.approx(out['cases'][name]['value'],abs=1e-8)
    for a,b in zip(flows,out['cases'][name]['rows'],strict=True):
        assert float(a)==pytest.approx(b['dps'],abs=1e-8)


def test_sanjiu_independent_entity_cash_and_legal_profits():
    actual=json.loads((ROOT/"000999/models/2026-Q3-output.json").read_text())
    weights=[1,1,.28,.2908]; floors=[.4,.7,.6,.5]; sh=1.664217858
    results={}
    for label in ['base','core_low','core_high','capital_plus20','profit_minus10','discount_plus100bp','upstream_delay']:
     p=actual['cases'][label]['parameters']
     c=actual['opening_cash'][:];d=actual['opening_debt'][:];cap=[2.5,7,6,3.5];r=p['rev'][:]; n=p['nopat'][:];ret=p['legal_opening'][:];unpaid=[0]*4;old=1.1;dist=[]; checkpoints=[]
     for year in range(1,11):
      growth=p['growth'] if year<=5 else p['growth']+(p['g']-p['growth'])*(year-5)/5
      cash0=c[:];np=[];profits=[]
      for i in range(4):
       dr=r[i]*growth;r[i]+=dr;n[i]*=1+growth
       op=n[i]*p['margin'] if i!=3 else [-.25,-.1,0,.12,.2,.22,.24,.26,.28,.3][year-1]
       depreciation=cap[i]*p['da_rate'][i]
       investment=(depreciation*1.12+max(0,dr)*.15)*p['capex_mult']
       cap[i]+=investment-depreciation
       profit=op-d[i]*p['debt_rate']*(.8 if op>0 else 1.)+cash0[i]*.01
       c[i]+=profit+depreciation-investment-dr*.12;ret[i]+=profit-max(profit,0)*p['reserve_rates'][i];profits.append(profit);np.append(op)
      pay=min(old,p['old_receipt'][year-1] if year<=len(p['old_receipt']) else 0,max(0,c[1]-.7));old-=pay;c[1]-=pay;c[0]+=pay
      if year==1:c[0]-=p['pool_payment'];c[1]+=p['pool_payment']
      for i in range(1,4):
       receipt=min(unpaid[i],max(0,c[i]-floors[i]));c[i]-=receipt;unpaid[i]-=receipt
       new=min(max(0,profits[i])*(p['sub_payout'] if i==1 else .5),max(0,ret[i]),max(0,c[i]-floors[i]))
       paid=new*(1-p['delay']);c[i]-=paid;unpaid[i]+=new-paid;ret[i]-=new;c[0]+=(receipt+paid)*weights[i];ret[0]+=new*weights[i]
      for i in range(4):
       issue=max(0,floors[i]-c[i]);c[i]+=issue;d[i]+=issue
      distribution=min(max(0,sum(profits[i]*weights[i] for i in range(4)))*.5,max(0,ret[0]),max(0,c[0]-.4))
      c[0]-=distribution;ret[0]-=distribution;dist.append(distribution)
      for i in range(4):
       amort=min(d[i],max(0,c[i]-2*floors[i]));c[i]-=amort;d[i]-=amort
      checkpoints.append({'cash':c[:],'debt':d[:],'legal':ret[:]})
     terminal_op=sum(np[i]*weights[i] for i in range(4))*(1+p['g'])*(1-p['g']/p['roic'])/(p['r']-p['g'])
     terminal=terminal_op+sum((c[i]-d[i]-floors[i])*weights[i] for i in range(4))+p['nonop_asset']
     pv=(sum(v/(1+p['r'])**(j+1) for j,v in enumerate(dist))+terminal/(1+p['r'])**10)/sh
     term5=(sum(dist[j]/(1+p['r'])**(j-4) for j in range(5,10))+terminal/(1+p['r'])**5)/sh
     ref=actual['cases'][label]
     assert abs(pv-ref['value_per_share'])<1e-9
     assert abs(term5-ref['terminal5_per_share'])<1e-9
     for t,z in enumerate(checkpoints):
      for field,our in [('cash',z['cash']),('debt',z['debt']),('legal_retained',z['legal'])]:
       assert max(abs(a-b) for a,b in zip(our,ref['history'][t][field]))<1e-8
     results[label]={'independent_value':pv,'independent_terminal5':term5,'value_difference':pv-ref['value_per_share'],'five_distributions':[v/sh for v in dist[:5]],'all_cash_debt_legal_checks':True}
    balance=0.; accumulated=0.; dividends=[]; legal_path=[]
    for profit in [-1.,.5,1.]:
     reserve=max(0,profit)*.1;accumulated+=reserve;balance+=profit-reserve
     dividend=max(0,balance);balance-=dividend;dividends.append(dividend);legal_path.append(balance)
    expected=dividends[2]/1.1**3+(2.+sum([-1.,.5,1.])-sum(dividends))/1.1**10
    observed=actual['selftest']['loss_recovery_full_value_case']
    assert abs(observed['value']-expected)<1e-9
    assert abs(observed['year3_dividend']-dividends[2])<1e-9
    assert abs(observed['reserve_added']-accumulated)<1e-9
    results['loss_recovery_hand_check']={'legal_path':legal_path,'distributions':dividends,'reserve_added':accumulated,'expected_value':expected,'actual_value':observed['value'],'pass':True}
