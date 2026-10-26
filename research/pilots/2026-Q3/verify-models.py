import json, math
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'companies'/'CN'
def model(s): return P/s/'models'/'2026-Q3-output.json'
results={}
def check(name,a,b):
 assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),(name,a,b)
 results[name]=a
# Independent actual-distribution present values, no researcher imports.
y=json.load(open(model('600066')))
s=2.213939223
liq=7.653017811+5.173804854-.125741490+.2+.119222862+.85
opening=liq-(.12819+.048795750+.163529638+.020282517)-.271520666-5.5-.677
assets=(.939243362+1.358293889)*.8+.807763804+.677*.8
for key,r,g,scale,claim in [('owner_low',.105,.015,.95,.269*7.7671),('owner_high',.095,.025,1.05,0),('owner_sensitivity_r_up_1pct',.11,.02,1,0)]:
 profits=[x*scale for x in [4.6,4.85,5.1,5.35,5.6]]; cash=opening-claim
 parent_cash=3.651901050+4.176504249-4-claim
 retained=5.107252998; paid=[]
 for i in range(5):
  parent_profit=[4,4.2,4.4,4.6,4.8][i]*scale
  lost=.55*scale if claim and i==0 else 0
  legal_profit=parent_profit-lost-(claim+.02987976755 if claim and i==0 else 0)
  retained+=legal_profit-max(legal_profit,0)*.1
  parent_cash+=[3.8,4,4.2,4.4,4.6][i]+parent_profit-[4,4.2,4.4,4.6,4.8][i]-lost
  cash=cash*1.015+profits[i]-[.5,.6,.65,.7,.75][i]
  distribution=min([2,2.1,2.2,2.3,2.4][i]*s,cash,parent_cash,retained)
  cash-=distribution;parent_cash-=distribution;retained-=distribution;paid.append(distribution/s)
  assert min(cash,parent_cash,retained)>=-1e-9
 tail=0;last=profits[-1]
 for t,gr in enumerate([.045,.04,.035,.03,.025],1):
  nxt=last*(1+gr);tail+=(nxt-(nxt-last)/.2)/(1+r)**t;last=nxt
 tail+=last*(1+g)*(1-g/.15)/(r-g)/(1+r)**5
 v=sum(d/(1+r)**t for t,d in enumerate(paid,1))+(tail+cash+assets)/s/(1+r)**5
 check('600066_'+key,v,y[key]['per_share'])
c=json.load(open(model('300750')));s=4.65-.010945162-16.697/300
f=369.813786+62.779978+.629346-1.646355-sum([39.897579,16.8711,76.354823,52.737747,4.064886])-90-15-1.632147
p=[78,87.01,96.78,106.6,115.1]; cf=[p[i]-[42,44,45,46,47][i] for i in range(5)]
for gr,roi in zip([.06,.05,.04,.03,.03],[.16,.15,.14,.13,.12]):
 q=p[-1]*(1+gr);cf.append(q-(q-p[-1])/roi);p.append(q)
for key,r,g,extra in [('dcf_low',.10,.02,0),('dcf_high',.09,.03,0),('sensitivity_discount_plus1pp',.105,.025,0),('sensitivity_extra_reinvestment10',.095,.025,10)]:
 cash=f
 for i,d in enumerate([8.5,9.5,10.5,12,13]):cash=cash*1.02+cf[i]-extra-d*s-(16.697 if i==0 else 0)
 tail=sum(cf[i]/(1+r)**(i-4) for i in range(5,10))+p[-1]*(1+g)*(1-g/.12)/(r-g)/(1+r)**5
 val=sum(d/(1+r)**t for t,d in enumerate([8.5,9.5,10.5,12,13],1))+(tail+cash+(13.148849+11.824729)*.8)/s/(1+r)**5
 check('300750_'+key,val,c[key]['per_share'])
m=json.load(open(model('600941')));s=(20793122579+902767867+68013597+352207727)/1e9
proceeds=(68013597*55+352207727*51.6)*.8686/1e9
f=sum([196.293,132.237,248.473,6.934,19.043,29.5])+26.966+9.014-(85.542-73.910+55.797)-9.24-100-4.476+proceeds
for key,r,g,assoc in [('lower',.09,.005,190),('upper',.08,.01,220),('sensitivity_r_plus_1pp',.095,.0075,205)]:
 cash=f
 for cf,a,d in zip([90,96,102,106,110],[6,6.2,6.4,6.6,6.8],[4.66,4.80,4.97,5.11,5.29]):cash=cash*1.02+cf+a-d*s
 terminal=(110*(1+g)*(1-g/.1)/(r-g)+cash+assoc)/s
 val=sum(d/(1+r)**t for t,d in enumerate([4.66,4.80,4.97,5.11,5.29],1))+terminal/(1+r)**5
 check('600941_'+key,val,m[key]['value'])
print(json.dumps(results,indent=2))
# Hydropower: reconstruct last-year attributable profit from debt financing equation.
h=json.load(open(model('600674')))
debt=90;profits=[]
for i,(vol,price,other,cost,da,tax,cap,div,inj) in enumerate(zip([88,89,91,94,95,97,102,106,108,112],[.28,.279,.278,.277,.276,.275,.275,.275,.275,.275],[1.4,1.7,2.1,2.4,2.8,3.1,3.2,3.3,3.8,4.2],[5.1,5.2,5.3,5.4,5.5,5.6,5.8,6,6.2,6.4],[6.3,6.35,6.4,6.5,6.6,6.8,7.1,7.4,7.7,8.1],[.2]*4+[.25]*6,[15,16,16,15,14,13,12,11,10,9],[3.8,4,4.2,4.5,4.8,5.2,5.8,6.5,7,7.5],[1.5,1.4,1.2,1,.8,.6,.5,.4,.3,.2])):
 ebit=vol*price+other-cost-da
 borrow=(cap+div/.48-inj/.48-(ebit-.026*debt)*(1-tax)-da+.2)/(1-.026*(1-tax)/2)
 net=(ebit-.026*(debt+borrow/2))*(1-tax)-[.04,.045,.05,.055,.06,.07,.08,.09,.1,.11][i]
 profits.append(net*.48+[.45,.48,.51,.55,.60,.65,.7,.75,.8,.85][i]+[.22,.23,.25,.28,.30,.33,.36,.38,.4,.42][i]+.06-[.4,.41,.42,.43,.44,.46,.48,.5,.52,.54][i]);debt+=borrow
parent_cash=1.5
for up,cost,invest,borrow,div in zip([4.1,4.3,4.5,4.8,5.1,5.5,6.1,6.8,7.3,7.8],[.4,.41,.42,.43,.44,.46,.48,.5,.52,.54],[1.9,1.8,1.6,1.5,1.5,1.3,1.2,1.1,1,.9],[1,.6,.4,.1,0,0,0,0,0,0],[.52,.54,.57,.6,.63,.7,.78,.86,.95,1.04]):
 parent_cash+=up-cost-invest+borrow-div*4.874606828
for k,r in [('core_low',.075),('core_high',.065),('sensitivity_rate_plus_100bp',.08)]:
 terminal=((profits[-1]-.06)*1.02*.8/(r-.02)+2.64+parent_cash-1)/4.874606828
 value=sum(d/(1+r)**t for t,d in enumerate([.52,.54,.57,.6,.63,.7,.78,.86,.95,1.04],1))+terminal/(1+r)**10
 check('600674_'+k,value,h[k]['value'])
print('ALL CHECKS',json.dumps(results,indent=2))
z=json.load(open(model('300012')))
for key,r,g,roi in [('core_low',.095,.025,.14),('core_high',.085,.03,.16),('sensitivity_roi12',.09,.03,.12)]:
 cash=.61314537045+.36761189194+.28+.01011858241-.45-.03-.067-.06524846766
 for cf,d in zip([.54,.66,.78,.95,1.07],[.23,.26,.29,.32,.35]): cash=cash*1.015+cf-d*1.682828214
 last=1.75;tail=0
 for t,gr in enumerate([.05,.045,.04,.035,.03],1):
  nxt=last*(1+gr);tail+=(nxt-(nxt-last)/roi)/(1+r)**t;last=nxt
 tail+=last*(1+g)*(1-g/roi)/(r-g)/(1+r)**5
 value=sum(d/(1+r)**t for t,d in enumerate([.23,.26,.29,.32,.35],1))+(tail+cash)/1.682828214/(1+r)**5
 check('300012_'+key,value,z[key]['value_per_share'])
# Independent mild-price funding loop: solve the cap analytically, not by production bisection.
debt=90.;retained=15.;pc=1.5;ps=[]
for i in range(10):
 vol=[88,89,91,94,95,97,102,106,108,112][i]
 price=[.28,.279,.278,.277,.276,.275,.275,.275,.275,.275][i]-.01
 da=[6.3,6.35,6.4,6.5,6.6,6.8,7.1,7.4,7.7,8.1][i]
 ebit=vol*price+[1.4,1.7,2.1,2.4,2.8,3.1,3.2,3.3,3.8,4.2][i]-[5.1,5.2,5.3,5.4,5.5,5.6,5.8,6,6.2,6.4][i]-da
 tax=.2 if i<4 else .25; nci=[.04,.045,.05,.055,.06,.07,.08,.09,.1,.11][i]
 cap=[15,16,16,15,14,13,12,11,10,9][i];inj=[1.5,1.4,1.2,1,.8,.6,.5,.4,.3,.2][i]
 requested=[3.8,4,4.2,4.5,4.8,5.2,5.8,6.5,7,7.5][i]/.48
 den=1-.026*(1-tax)/2
 const=(cap-inj/.48-(ebit-.026*debt)*(1-tax)-da+.2)/den
 # NI(div)=intercept-slope*div.
 intercept=(ebit-.026*(debt+const/2))*(1-tax)-nci
 slope=.026*(1-tax)/2/den
 actual=min(requested,(retained+.9*intercept)/(1+.9*slope))
 borrowing=const+actual/den
 common=intercept-slope*actual
 retained+=.9*common-actual;debt+=borrowing
 profit=common*.48+[.45,.48,.51,.55,.60,.65,.7,.75,.8,.85][i]+[.22,.23,.25,.28,.30,.33,.36,.38,.4,.42][i]+.06-[.4,.41,.42,.43,.44,.46,.48,.5,.52,.54][i]
 before=pc+actual*.48+.3-[.4,.41,.42,.43,.44,.46,.48,.5,.52,.54][i]-inj-[.4,.4,.4,.5,.7,.7,.7,.7,.7,.7][i]+[1,.6,.4,.1,0,0,0,0,0,0][i]
 paid=min([.52,.54,.57,.6,.63,.7,.78,.86,.95,1.04][i]*4.874606828,max(0,before-1));pc=before-paid;ps.append(paid/4.874606828)
 assert retained>=-1e-8 and pc>=1-1e-8
terminal=((profit-.06)*1.02*.8/.05+2.64+pc-1)/4.874606828
mild=sum(d/1.07**t for t,d in enumerate(ps,1))+terminal/1.07**10
check('600674_mild_value',mild,h['mild_price_full_path']['valuation']['value'])
check('600674_mild_debt',debt,h['mild_price_full_path']['operating'][-1]['yl_debt_end'])
check('600674_mild_parent_cash',pc,h['mild_price_full_path']['parent_cash_budget'][-1]['closing_cash'])
print('FINAL PASS',len(results))
