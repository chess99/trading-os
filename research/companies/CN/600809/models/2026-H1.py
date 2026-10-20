import json, math
from pathlib import Path
S=12.19964222
C0=354.4121-80.0297-.3686-25.6907-.4951-50-5.3372-.1162
P=[90,96,103,110,117]
REV=[340,352,366,382,398]
CAP=[20,20,19,18,18]; DA=[3,4,4,4,5]; WC=[1]*5
NET=[a-b+c for a,b,c in zip(CAP,DA,WC)]
def run(profits=P, rate=.105,g=.0225,roic=.18,extra=0,cash=C0):
    rows=[];start=cash
    for i,p in enumerate(profits):
        interest=cash*.01
        d=math.ceil(.65*(p+interest)/S*100)/100
        reinvest=NET[i]+(extra if i==0 else 0)
        fcfe=p-reinvest+interest
        end=cash+fcfe-d*S
        rows.append(dict(year=i+1,revenue=REV[i],profit=p,capex=CAP[i]+(extra if i==0 else 0),depreciation=DA[i],working_capital=WC[i],net_reinvestment=reinvest,interest=interest,fcfe=fcfe,distribution=d,cash_end=end))
        assert abs(end-cash-fcfe+d*S)<1e-9
        assert d*S>=.65*(p+interest)-1e-9
        cash=end
    p6=profits[-1]*(1+g); ni6=p6*g/roic; f6=p6-ni6
    bv=f6/(rate-g);terminal=(bv+cash)/S
    divpv=sum(x['distribution']/(1+rate)**x['year'] for x in rows)
    tvpv=terminal/(1+rate)**5
    assert abs(cash-(start+sum(x['fcfe']-x['distribution']*S for x in rows)))<1e-8
    return dict(rate=rate,g=g,roic=roic,rows=rows,profit6=p6,net_investment6=ni6,fcfe6=f6,business_terminal=bv,cash5=cash,terminal_per_share=terminal,value=divpv+tvpv,terminal_pv_share=tvpv/(divpv+tvpv))
low=run(rate=.11,g=.02);high=run(rate=.10,g=.025);base=run()
sens={"rate_9_5":run(rate=.095),"rate_11_5":run(rate=.115),"roic_12":run(roic=.12),"extra_capex_15":run(extra=15),"profit5_minus_10":run(profits=[90,96,103,110,107])}
scenarios={"cycle":run(profits=[75,78,90,103,112],rate=.11,g=.02),"structural":run(profits=[75,68,62,60,60],rate=.12,g=0,roic=.10),"upside":run(profits=[95,107,119,130,140],rate=.10,g=.025,roic=.22)}
# Zero-growth terminal identity and capital conservation.
assert abs(run(g=0)['business_terminal']-117/.105)<1e-8
assert sum(NET)==sum(CAP)-sum(DA)+sum(WC)==80
assert abs(C0-192.3746)<.001
out=dict(shares=S,initial_cash=C0,base=base,low=low,high=high,sensitivity=sens,scenarios=scenarios,method2=dict(low=(80*12+C0)/S,high=(90*14+C0)/S),checks='passed')
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:out[k] for k in ['initial_cash','method2','checks']},ensure_ascii=False))
for k,v in dict(low=low,high=high,base=base,**sens,**scenarios).items(): print(k,round(v['value'],4),round(v['terminal_per_share'],4),round(v['cash5'],4))
print([x['distribution'] for x in base['rows']])
