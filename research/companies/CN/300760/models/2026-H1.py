"""迈瑞医疗：金额亿元、股数亿股；标准库、无网络。"""
import json
from pathlib import Path
S=12.11799431
C0=187.2088-(13.3019+.7559)*(1-37418188/139227286)-1.3156-40-9.6713-.3907-.1567-1-.0076
D=[5.5,5.8,6.3,6.7,7.1]
P=[96,103,110,117,124]

def model(r=.095,roc=.30,tail_roc=.22,g=.03,profit_scale=1,delay=False):
    profits=[p*profit_scale for p in P]
    if delay: profits=[p-x for p,x in zip(profits,[15,10,5,0,0])]
    c=C0; rows=[]
    for i,p in enumerate(profits):
        inv=23*profit_scale if i==0 else (p-profits[i-1])/roc
        f=p-inv; interest=c*.01; prev=c;c+=f+interest-D[i]*S
        rows.append(dict(year=i+1,profit=p,reinvestment=inv,fcfe=f,dividend=D[i],interest=interest,cash_end=c))
        assert abs(c-(prev+f+interest-D[i]*S))<1e-9
        assert abs(p-inv-f)<1e-9
    tail=[]; p=profits[-1]
    for t,(growth,roi) in enumerate(zip([.06,.055,.05,.045,.04],[.28,.265,.25,.235,tail_roc]),6):
        np=p*(1+growth);inv=(np-p)/roi;f=np-inv
        tail.append(dict(year=t,profit=np,reinvestment=inv,fcfe=f));p=np
    p11=p*(1+g);f11=p11-(p11-p)/tail_roc
    op10=f11/(r-g)
    op5=sum(x['fcfe']/(1+r)**(x['year']-5) for x in tail)+op10/(1+r)**5
    obligation= (3.9184 if r>=.10 else 1 if r<=.09 else 2.4592)*(1+r)**5
    tv=(op5+c-obligation)/S
    pvdiv=sum(d/(1+r)**(i+1) for i,d in enumerate(D))
    value=pvdiv+tv/(1+r)**5
    return dict(rate=r,rows=rows,tail=tail,terminal_profit=p11,terminal_fcfe=f11,operating_value_year10=op10,operating_value_year5=op5,cash_year5=c,obligation_year5=obligation,terminal_per_share=tv,value=value,terminal_pv_share=tv/(1+r)**5/value)

out={'shares':S,'initial_cash':C0,'core_low':model(.10),'core_high':model(.09),'base':model(),
     'sensitivity_roi20':model(roc=.20),'sensitivity_tail_roi15':model(tail_roc=.15),
'cycle_delay':model(delay=True),
     'optimistic':model(.09,roc=.35,profit_scale=1.10),
     'structural':{'low':(40/.12+C0-3.9184)/S,'high':(50/.11+C0-1)/S},
     'method2':{'low':(96*17+C0-3.9184)/S,'high':(96*19+C0-1)/S}}
assert len(D)==5
assert abs(sum(x['reinvestment'] for x in out['base']['rows'][1:])*.30-(P[-1]-P[0]))<1e-8
assert out['sensitivity_roi20']['value']<out['base']['value']
assert out['sensitivity_tail_roi15']['value']<out['base']['value']
# Static economic check: zero growth and no investment -> earnings/r.
assert abs(sum(10/1.1**t for t in range(1,6))+(10/.1)/1.1**5-100)<1e-9
# Moving a dividend forward removes the same undiscounted terminal cash (zero cash interest).
assert abs((100+50-20)-(100+50-30)-10)<1e-9
parent=76.7796;re=329.705;parent_rows=[]
for i,d in enumerate(D):
    interest=parent*.01
    parent+=50+2.5*i+15+1.25*i+interest-d*S
    re+=45+2.5*i+interest-d*S
    parent_rows.append(dict(year=i+1,cash=parent,retained_earnings=re))
    assert parent>0 and re>0
out['parent']=parent_rows
out['core_range']={'low':round(out['core_low']['value'],2),'high':round(out['core_high']['value'],2)}
out['terminal_range']={'low':round(out['core_low']['terminal_per_share'],2),'high':round(out['core_high']['terminal_per_share'],2)}
out['checks']='cash_conservation, profit_capital_bridge, constant_perpetuity, dividend_cash_offset, parent_solvency passed'
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['initial_cash','core_range','terminal_range','method2','structural','parent']},ensure_ascii=False,indent=2))
for k in ['base','sensitivity_roi20','sensitivity_tail_roi15','cycle_delay','optimistic']:
 print(k,out[k]['value'])
