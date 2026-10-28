"""Fresh independent literal rebuild. Does not import production or consume its parameters."""
from pathlib import Path
import json

def recalc(factor=1,stress=False,refinance=None,auth=0.,capacity=0.,mode='arrears',prorata=False,trigger=3):
 # Separate ledger, own literals. Currency 100m CNY.
 cost=30.175 if stress else 24.14;capital=7.242;start=5 if stress else 3;rate=.065 if stress else .05
 debt=money=earned=surplus=0.;project_rows=[];common=[];arrears=0.
 for year in range(1,37):
  cap=cost/2 if year<3 else 0.;equity=capital/2 if year<3 else 0.;extra=3.0175 if stress and year<3 else 0.;draw=8.449 if year<3 else 0.;debt+=draw
  running=start<=year<start+30
  rev=3000*365*.88*(260 if stress else 290)*.2*(24.14/3.5)/1e8 if running else 0.
  exp=3000*365*.88*(210 if stress else 170)/1e8+.15 if running else 0.;dep=cost/30 if running else 0.
  pre=rev-exp-dep-debt*rate;tax=max(0,pre+min(earned,0))*.22;profit=pre-tax;earned+=profit
  reserve_add=min(max(capital*.2-surplus,0),max(earned,0)*.1);earned-=reserve_add;surplus+=reserve_add
  repay=min(debt,16.898/15) if running else 0.;debt-=repay
  shutdown=.1 if year==start+30 else 0.
  money+=profit+dep-(.35 if running else 0)-repay+draw+equity+extra-cap-shutdown
  need=max(0,-money);money+=need
  dividend=max(0,min(money,earned)) if running else 0.
  minimum=.10863 if trigger<=year<start+30 else 0.;arrears+=minimum
  a=min(dividend,max(dividend*.3,arrears)) if dividend else 0.;arrears=max(0.,arrears-a)
  sponsor_payment=arrears if mode=='sponsor_topup' else 0.;arrears-=sponsor_payment
  flow=(dividend-a)*.79-equity*.553-(extra+need)*(.553 if prorata else 1.)-sponsor_payment
  money-=dividend;earned-=dividend
  liquidation=money if year==start+30 else 0.;money-=liquidation
  if year==start+30:
   senior=min(arrears,liquidation);arrears-=senior;flow+=(liquidation-senior)*.553
   flow-=arrears;arrears=0.
  common.append(flow);project_rows.append(dict(cash=money,debt=debt,common=flow,retained=earned,reserve=surplus,support=need,profit=profit,A_minimum_accrued=minimum,A_project_paid=a,A_sponsor_paid=sponsor_payment,A_arrears=arrears))
 foreign_tv=sum(common[i]/1.12**(i-4) for i in range(5,36));foreign_pv=sum(x/1.12**(i+1) for i,x in enumerate(common))
 cash=22.5139287324;parent=1.3436606882;profits=32.5323097698;reserve=7.8377144894;ar=.1;internal=25.5160562292;nci=20.5579804381;debt=84.8366774466;loss=0.;rows=[];divs=[];bond=15.2584365759
 growths=[]
 for i in range(5):
  domestic=([38,38.6,39.2,39.5,39.8][i]*(.9 if stress else factor)-[8.8,9.1,9.4,9.7,10][i]-(1 if stress else 0)-6-2.9)*.8+6-[3,3.1,3.2,3.3,3.4][i]-(.8 if stress else 0)-[3,2.5,2,1.5,1.5][i]-([2,1.5,1,.7,.5] if stress else [1,.8,.6,.4,.4])[i]
  equipment=((([12,12,13,13,13][i]*.27) if stress else [16,17,18,19,20][i]*.32)-1.5)*.8+.3-.35-[.6,.5,.4,.4,.4][i]-[.7,.5,.4,.4,.4][i]
  pre=[9,11,13,14,15][i]*([-.02,0,.02,.03,.03] if stress else [.06,.07,.08,.09,.1])[i]-.65
  net=pre-max(0,pre+loss)*.05;loss=min(0,loss+pre)
  material=net+1.3-[.9,1,1.1,1.2,1.3][i]-([3,2,1,.5,.5] if stress else [2,1.2,.6,.2,.1])[i]-[.6,.5,.4,.3,.2][i]
  np=.9717257385+.37*(net+.11);nd=max(0,np)*.3;nci+=np-nd
  coupon=14.76619*.018 if i==0 else 0.;new=((6 if stress else 10) if refinance is None else refinance) if i==1 else 0.;redeem=16.242809 if i==1 else 0.
  accretion=.9843724241*([.4,.6][i] if i<2 else 0.);bond+=accretion;debt+=accretion
  if i==1:debt+=new-bond;bond=0.
  interest=(3+((.042*((6 if stress else 10) if refinance is None else refinance)) if i>=2 else 0)+coupon)*.8
  guarantee=.6 if stress and i==1 else 0.;settlement=.5 if i<2 else 0.;income=cash*.015
  cash+=domestic+equipment+material-interest-nd+income+[0,.1,.2,.3,.3][i]+common[i]-settlement-guarantee+new-redeem
  declared=[10.5,10.5,11,11.5,12][i]*(.75 if stress else 1)*max(0,min(1.25,(domestic+equipment+material)/14))
  receipt=ar+.95*declared;ar=.05*declared;pi=.25+coupon if i<2 else .25+.042*((6 if stress else 10) if refinance is None else refinance)
  pp=declared+.2-pi-([2,1,0,0,0][i] if stress else 0)-accretion
  addition=min(max(17.04558119*.5-reserve,0),max(0,pp+min(profits,0))*.1);reserve+=addition;profits+=pp-addition
  parent+=receipt+.2-pi+common[i]+new-redeem-settlement-guarantee
  collect=min(max(.5-parent,0),max(cash-parent-3,0),internal,auth,capacity) if parent<.5 else 0.;parent+=collect;internal-=collect;auth-=collect;capacity-=collect
  if parent<0 or cash<0:return dict(status='payment_failure',failure_year=i+1,shortfall=max(0,-parent),value=None,terminal_per_share=None,auxiliary=None,rows=rows,overseas=project_rows,dividends=divs+[None]*(5-len(divs)))
  distribution=max(0,min([.3,.3,.4,.45,.5][i]*20.2934131,parent-.5,cash-3,profits));parent-=distribution;cash-=distribution;profits-=distribution
  divs.append(distribution/20.2934131)
  rows.append(dict(dom_fcff=domestic,eq_fcff=equipment,mat_fcff=material,cash=cash,parent_cash=parent,parent_retained=profits,parent_reserve=reserve,declared=declared,received=receipt,parent_ar=ar,nci=nci,debt=debt,conditional_collection=collect,dividend_per_share=divs[-1]))
  growths.append([3,2.5,2,1.5,1.5][i]+([2,1.5,1,.7,.5] if stress else [1,.8,.6,.4,.4])[i]+[.6,.5,.4,.4,.4][i]+[.7,.5,.4,.4,.4][i]+([3,2,1,.5,.5] if stress else [2,1.2,.6,.2,.1])[i]+[.6,.5,.4,.3,.2][i])
 dc=(39*(.9 if stress else factor)-10.3-(1 if stress else 0)-6-3)*.8+6-3.7-(.8 if stress else 0)-.4
 life=12 if stress else 15;dv=sum(dc*.99**i/1.085**(i+1) for i in range(life));release=22.1840854466/1.085**life
 ec=2.958*(.6 if stress else 1);ev=ec/.105
 mc=-.9 if stress else .046;mv=sum(-.9/1.125**j for j in range(1,21))-1/1.125**21 if stress else .046/.125
 av=7.8289003057*.85*(.6 if stress else 1)-.9;sale=1.1927039718*.8
 tv=(dv+release+ev+mv+foreign_tv+av+sale+cash-debt-nci)/20.2934131
 value=sum(x/1.11**(i+1) for i,x in enumerate(divs))+tv/1.11**5
 dt=sum(dc*.99**i/1.085**(i+1) for i in range(life+5))+22.1840854466/1.085**(life+5)
 mt=sum(mc/1.085**j for j in range(1,6))+mv/1.085**5 if stress else mv
 extra=sum((growths[i]+(.5 if i<2 else 0))/1.085**(i+1) for i in range(5))
 ramp=sum((dc+ec+mc-rows[i]['dom_fcff']-rows[i]['eq_fcff']-rows[i]['mat_fcff']-growths[i])/1.085**(i+1) for i in range(5))
 aux=(dt+ev+mt+foreign_pv+7.8289003057*.85*(.6 if stress else 1)+sale+22.5139287324-84.8366774466-20.5579804381-extra-ramp-(.6/1.085**2 if stress else 0)-(16.242809-15.2584365759)/1.085**2)/20.2934131
 return dict(status='conditional_5y_feasible',value=value,terminal_per_share=tv,auxiliary=aux,rows=rows,overseas=project_rows,dividends=divs)
root=Path(__file__).parent;expected=json.loads((root/'2026-Q3-output.json').read_text());result={}
inputs={'base':{},'domestic_minus10':{'factor':.9},'structural':{'stress':True},'structural_full':{'stress':True,'auth':25,'capacity':25},'refinance_zero':{'refinance':0},'internal_partial':{'refinance':0,'auth':2,'capacity':1},'internal_full':{'refinance':0,'auth':12,'capacity':12},'others_confirmed':{'prorata':True},'preferred_topup':{'mode':'sponsor_topup'},'preferred_start11':{'trigger':11}}
for name,kw in inputs.items():
 actual=recalc(**kw);prod=expected['cases'][name]['low'];deltas=[]
 assert actual['status']==prod['status'],name
 if actual['status']=='payment_failure':
  assert actual['failure_year']==prod['failure']['year']
  assert actual['value'] is None and prod['value'] is None and actual['dividends']==prod['dividends']
  deltas.append(abs(actual['shortfall']-prod['failure']['parent_required_payment_shortfall']))
 else:
  for k in ['value','terminal_per_share','auxiliary']:deltas.append(abs(actual[k]-prod[k]))
 for a,b in zip(actual['rows'],prod['rows']):
  for k in a:deltas.append(abs(a[k]-b[k]))
 for a,b in zip(actual['overseas'],prod['overseas']['rows']):
  for k in a:deltas.append(abs(a[k]-b[k]))
 assert max(deltas)<1e-8,(name,max(deltas),actual['value'],prod['value'])
 result[name]=dict(status=actual['status'],comparisons=len(deltas),max_error=max(deltas),value=actual['value'],terminal=actual['terminal_per_share'],auxiliary=actual['auxiliary'])
print(json.dumps(result,ensure_ascii=False,indent=2))
