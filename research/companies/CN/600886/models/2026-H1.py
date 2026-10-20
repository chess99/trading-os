import json
from pathlib import Path
S=80.04494262
D=[.52,.53,.55,.57,.59]
def funding():
 b=77.9836;c=11.5278;out=[];retained=202.0010444533
 for i in range(5):
  fresh=[64,68,70,72,76][i]*.52+[14,15,16,17,18][i]
  received=fresh+(12.48 if i==0 else 0)
  project=[13,15.6,13,7.8,3.12][i]-[13,15.6,11.9138,0,0][i]+[14,14,12,10,8][i]+[20,12.8152,0,0,0][i]
  expense=2.2*1.02**i; interest=b*.034; perp=[1.331,1.8,1.8,1.95,1.95][i]
  delta=project+expense+interest+perp+D[i]*S-received+5-c
  # No treasury interest income budget; statutory reserve stress at 10% of positive parent profit.
  legal=fresh-expense-interest-perp
  reserve=max(0,fresh-expense-interest)*.1
  retained+=legal-reserve-D[i]*S
  assert retained>=0
  out.append(dict(year=i+1,fresh_declared=fresh,cash_received=received,net_project_call=project,expense=expense,interest=interest,perpetual=perp,ordinary_distribution=D[i]*S,legal_profit_proxy=legal,reserve_allocation=reserve,ending_distributable_retained=retained,ending_debt=b+delta))
  assert abs(c+received+delta-project-expense-interest-perp-D[i]*S-5)<1e-9
  b+=delta;c=5
 return out
F=funding()
def operating(high=False,tax=.25,price_shift=0):
 q=925 if high else 900; price=(.290 if high else .282)+price_shift
 # Existing mature hydro only. No new dam output, no unapproved capacity.
 hydro=(q*price-21.6*1.02**5-75-8*1.02**5-q*price*.032-1.5-24.5)*(1-tax)*.52-.1
 other=5.14046*.75/.85
 cq=445 if high else 430;cp=.388 if high else .38;fuel=.249 if high else .255
 coal=(cq*(cp-fuel-.026*1.02**5)-9.5-6*1.02**5-1-8)*.75*.66
 nq=66 if high else 63
 newcoal=(nq*(cp-fuel-.026*1.02**5)-2-1.1*1.02**5-1.1)*.75*.9
 gas=(23*(.60-.50-.02*1.02**5)-1-.45*1.02**5-.5)*.75*.51
 # modest funded expansion; unit depreciation and cash costs retained, higher interest
 w,sol=(105,140) if high else (95,125)
 wp,sp=(.34,.30) if high else (.33,.29)
 ratio=(w+sol)/182
 renew=(w*wp+sol*sp-15*ratio-18*ratio-2*1.02**5-1.5*ratio-10.5-(2 if high else 1.5))*.75*(.35*.62464+.25*.52+.4*.9)-.4
 associates=7.2 if high else 6.5
 # Parent cash costs and treasury income aligned with financing budget.
 parent=-(F[-1]['expense']+F[-1]['interest'])
 parts=dict(yalong=hydro,other_hydro=other,coal=coal,new_coal=newcoal,gas=gas,renewables=renew,associates=associates,parent=parent,perpetual=-1.95)
 return parts
# Loan recovery scenarios begin after year five; no coupon cash in annual distributions.
def loan(high=False):
 face=32.8152; coupon=.06 if high else .04; recovery=.8 if high else .5; k=.08 if high else .10;n=18
 value=sum(face*coupon/(1+k)**t for t in range(1,n+1))+face*recovery/(1+k)**n
 # Old loan has uncertain different terms: separate 10-year principal recovery only.
 old=3.2014*recovery/(1+k)**10
 return dict(new_face=face,cash_coupon=coupon,principal_recovery=recovery,rate=k,years=n,new_value=value,old_value=old,total=value+old)
def new_hydro(high=False):
 # A separate asset pool: excludes all mature-hydro quantities and all wind/solar.
 cost=347.22+171.21; q=104.05+45.238
 price=.30 if high else .282; utilization=1.0 if high else .95
 completion=1.0 if high else .95; project_rate=(.085 if high else .10)*.30+.034*.75*.70
 debt=cost*completion*.70
 remaining=cost*(1-completion)
 depreciation=cost*.90/45
 maintenance=cost*.005
 rows=[];pv=0
 for t in range(1,46):
  ramp=(.9 if high else .5) if t==1 else ((1.0 if high else .85) if t==2 else 1.0)
  revenue=q*utilization*ramp*price
  cash_cost=q*utilization*ramp*.045+1.5
  nopat=(revenue*(1-.032)-cash_cost-depreciation)*.75
  cash=nopat+depreciation-maintenance-(remaining if t==1 else 0)
  pv+=cash/(1+project_rate)**t
  rows.append(dict(year_after_5=t,ramp=ramp,revenue=revenue,nopat=nopat,free_cash=cash))
 equity=(pv-debt)*.52
 return dict(cost=cost,design_volume=q,price=price,utilization=utilization,completion=completion,debt_at_5=debt,remaining_capex=remaining,discount=project_rate,maintenance=maintenance,depreciation=depreciation,enterprise_value=pv,ordinary_equity=equity,rows=rows)
def endpoint(high=False,price_shift=0,tax=.25):
 parts=operating(high,tax,price_shift);profit=sum(parts.values());roi=.08 if high else .05;k=.085 if high else .10;multiple=(1-.015/roi)/(k-.015)
 l=loan(high);project=new_hydro(high);tv=(profit*multiple+l['total']+project['ordinary_equity'])/S
 divpv=sum(d/(1+k)**t for t,d in enumerate(D,1));val=divpv+tv/(1+k)**5
 return dict(parts=parts,profit=profit,multiple=multiple,rate=k,loan=l,new_hydro=project,terminal=tv,value=val,terminal_share=(tv/(1+k)**5)/val)
def auxiliary(high=False):
 e=endpoint(high);pe=13 if high else 11.1
 tv=(e['profit']*pe+e['loan']['total']+e['new_hydro']['ordinary_equity'])/S
 return dict(multiple=pe,terminal=tv,value=sum(d/(1+e['rate'])**t for t,d in enumerate(D,1))+tv/(1+e['rate'])**5)
lo=endpoint();hi=endpoint(True)
o=dict(shares=S,distributions=D,funding=F,low=lo,high=hi,aux_low=auxiliary(),aux_high=auxiliary(True),price_down_low=endpoint(price_shift=-.01),tax17_low=endpoint(tax=.17),loan_zero_value_loss_low=lo['loan']['total']/S/1.1**5,batang_20pct_loss=102.7816*.2*.75/S,project_net_calls=sum(x['net_project_call'] for x in F))
assert len(D)==5 and all(x>0 for x in D)
assert abs(sum(x['ordinary_distribution'] for x in F)-sum(D)*S)<1e-9
assert abs(sum([1/(1+.1)**t for t in range(1,6)])-(1-1.1**-5)/.1)<1e-9
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(o,ensure_ascii=False,indent=2))
print(json.dumps({k:o[k] for k in ['low','high','aux_low','aux_high','funding']},ensure_ascii=False))
