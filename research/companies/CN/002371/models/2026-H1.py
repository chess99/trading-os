import json
from pathlib import Path
S=7.256892
CASH=179.5526
DEBT=164.7687
RESERVE=21.5021
MINORITY=61.7292
OPTIONS=[(6586649/1e8,116.23),(2465942/1e8,114.21),(12335355/1e8,139.63),(10403050/1e8,234.98)]
D=[.8,.9,1,1.1,1.2]
R=[500,576,659,742,831]
E=[478,551,631,711,797]
N=[62.19875,72.79825,84.58575,96.84525,108.40875]
PD=[5.3,6.2,7.2,8.3,9.5]
TD=[13.7,16.8,19.8,22.7,25.5]
CAP=[9.8,11.2,13.2,15.3,17.5]
def path(g=.10,margin_delta=0,wc=.45):
 p,t,w=84.0543,182.9157,233.4746
 prev=433.7298; rows=[]
 for i in range(5):
  np=N[i]+E[i]*margin_delta*.85; rd=E[i]*.074; dw=(R[i]-prev)*wc
  f=np+PD[i]+TD[i]-CAP[i]-rd-dw
  p+=CAP[i]-PD[i];t+=rd-TD[i];w+=dw
  rows.append(dict(year=i+1,revenue=R[i],equipment=E[i],nopat=np,pda=PD[i],tda=TD[i],capex=CAP[i],rd=rd,dwc=dw,fcf=f,p=p,t=t,w=w))
  prev=R[i]
 p5,t5=p,t
 eda=N[-1]/.85+PD[-1]+TD[-1]+E[-1]*margin_delta
 for y in range(6,11):
  old=rows[-1]; revenue=old['revenue']*(1+g); equip=old['equipment']*(1+g)
  da_p=p*9.5/p5;da_t=t*25.5/t5;ebitda=eda*(1+g)**(y-5)
  np=(ebitda-da_p-da_t)*.85;rd=equip*.074;cap=da_p+(revenue-prev)*8/89;dw=(revenue-prev)*wc
  f=np+da_p+da_t-cap-rd-dw
  p+=cap-da_p;t+=rd-da_t;w+=dw
  rows.append(dict(year=y,revenue=revenue,equipment=equip,nopat=np,pda=da_p,tda=da_t,capex=cap,rd=rd,dwc=dw,fcf=f,p=p,t=t,w=w));prev=revenue
 # Mature capital grows 2.5%, new development fully paid. Technical amortization closes stock.
 old=rows[-1]; gg=.025; rd=old['equipment']*(1+gg)*.074;dt=rd-old['t']*gg;dp=old['p']*9.5/p5
 ebitda=eda*(1+g)**5*(1+gg);np=(ebitda-dp-dt)*.85
 mature=np+dp+dt-(dp+old['p']*gg)-rd-old['w']*gg
 assert abs(mature-(np-(old['p']+old['t']+old['w'])*gg))<1e-8
 return rows,mature
def value(g,r,minority_multiple,margin_delta=0,wc=.45,exercise=False):
 rows,mature=path(g,margin_delta,wc);tv=mature/(r-.025)
 pv=sum(a['fcf']/(1+r)**a['year'] for a in rows)+tv/(1+r)**10
 proceeds=sum(n*(k-5) for n,k in OPTIONS) if exercise else 0
 shares=S+sum(n for n,k in OPTIONS) if exercise else S
 bridge=CASH-DEBT-RESERVE+10-MINORITY*minority_multiple+proceeds/(1+r)**3
 return dict(growth=g,rate=r,minority_multiple=minority_multiple,rows=rows,mature_fcf=mature,terminal=tv,ev=pv,net_adjustment=bridge,shares=shares,value=(pv+bridge)/shares,terminal_share=tv/(1+r)**10/pv,exercise=exercise)
def holder(g,r,minority_multiple,cash_yield=.004):
 rows,mature=path(g);cash=CASH;mother=59.4586;legal=.1688;reserve=2.5601;ledger=[]
 for i,row in enumerate(rows[:5]):
  old=cash;div=D[i]*S;interest=DEBT*.03;cash_income=old*cash_yield*.85;cash+=row['fcf']+cash_income-interest-div
  upstream=10+i;mother_income=mother*cash_yield*.85;motherprofit=upstream+mother_income-90.8096*.03-.8
  appropriation=min(max(S*.5-reserve,0),max(motherprofit,0)*.1);reserve+=appropriation;legal+=motherprofit-appropriation-div
  mother+=upstream+mother_income-90.8096*.03-.8-div
  assert abs(cash-old-row['fcf']-cash_income+interest+div)<1e-8
  assert legal>=0 and mother>=0 and cash>=RESERVE
  ledger.append(dict(year=i+1,distribution=D[i],total_dividend=div,cash_income=cash_income,interest=interest,group_cash=cash,mother_cash=mother,mother_retained=legal,upstream=upstream))
 future=sum(row['fcf']/(1+r)**(row['year']-5) for row in rows[5:])+mature/(r-.025)/(1+r)**5
 minor=MINORITY*minority_multiple*(1+r)**5
 assert abs(minor/(1+r)**5-MINORITY*minority_multiple)<1e-9
 undiluted=(future+cash-DEBT-RESERVE+10-minor)/S
 # End-year exercise only where intrinsic value exceeds dividend-adjusted strike.
 exercise=[(n,k-sum(D)) for n,k in OPTIONS if undiluted>k-sum(D)]
 proceeds=sum(n*k for n,k in exercise);shares=S+sum(n for n,k in exercise)
 tv=(future+cash+proceeds-DEBT-RESERVE+10-minor)/shares
 return dict(year5_undiluted_terminal=undiluted,year5_shares=shares,year5_option_proceeds=proceeds,ledger=ledger,year5_ev=future,year5_cash=cash,year5_debt=DEBT,year5_minority=minor,year5_terminal_per_share=tv)

def bridge_diagnostic(current,h):
 r=current['rate'];discount=(1+r)**-5
 pieces={
 'operating_cash_retention':sum(v['fcf']*(discount-(1+r)**-v['year']) for v in current['rows'][:5])/S,
 'dividend_timing':sum(v['total_dividend']*((1+r)**-v['year']-discount) for v in h['ledger'])/S,
 'opening_financial_bridge_carry':(CASH-DEBT-RESERVE+10)*(discount-1)/S,
 'net_interest_carry':sum(v['cash_income']-v['interest'] for v in h['ledger'])*discount/S,
 'minority_timing':(MINORITY*current['minority_multiple']-h['year5_minority']*discount)/S,
 'option_dilution':(h['year5_terminal_per_share']-h['year5_undiluted_terminal'])*discount}
 mechanical_pv=sum(d/(1+r)**i for i,d in enumerate(D,1))+h['year5_terminal_per_share']*discount
 assert abs(mechanical_pv-current['value']-sum(pieces.values()))<1e-8
 return dict(current_fcff_value=current['value'],same_rate_d_plus_tv_pv=mechanical_pv,difference=mechanical_pv-current['value'],components=pieces,equity_cost=(r-.2*.03)/.8)

low=value(.08,.115,1.75);high=value(.12,.095,1)
mid=value(.10,.105,1.375)
sens={k:value(**v) for k,v in {'growth6':dict(g=.06,r=.105,minority_multiple=1.375),'growth14':dict(g=.14,r=.105,minority_multiple=1.375),'margin_minus2pp':dict(g=.10,r=.105,minority_multiple=1.375,margin_delta=-.02),'wc55':dict(g=.10,r=.105,minority_multiple=1.375,wc=.55),'structural':dict(g=.06,r=.105,minority_multiple=1.375,margin_delta=-.02,wc=.55),'exercise':dict(g=.10,r=.105,minority_multiple=1.375,exercise=True)}.items()}
hlow=holder(.08,.115,1.75);hhigh=holder(.12,.095,1)
epv=[(58.2128/r+CASH-DEBT-RESERVE+10-MINORITY*m)/S for r,m in [(.115,1.75),(.095,1)]]
# Basic independent identities, including no future cash and simple single payment.
assert sum([0/(1.1)**t for t in range(1,6)])==0
assert abs(110/1.1-100)<1e-10
for row in mid['rows']:
 assert abs(row['fcf']-(row['nopat']+row['pda']+row['tda']-row['capex']-row['rd']-row['dwc']))<1e-8
cycle_loss=sum(row['fcf']*((1.105)**(-row['year'])-(1.105)**(-row['year']-1)) for row in mid['rows'][:3])/S
result=dict(bridge_low=bridge_diagnostic(low,hlow),bridge_high=bridge_diagnostic(high,hhigh),cash_yield_zero_low=holder(.08,.115,1.75,0)['year5_terminal_per_share'],cash_yield_zero_high=holder(.12,.095,1,0)['year5_terminal_per_share'],cycle_delayed_value=mid['value']-cycle_loss,core_low=low,core_high=high,mid=mid,sensitivity=sens,holder_low=hlow,holder_high=hhigh,epv=epv,distributions=D,option_reference_shares=sum(n for n,k in OPTIONS))
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'core':[low['value'],high['value']],'mid':mid['value'],'sens':{k:v['value'] for k,v in sens.items()},'holder':[hlow['year5_terminal_per_share'],hhigh['year5_terminal_per_share']],'epv':epv}))
