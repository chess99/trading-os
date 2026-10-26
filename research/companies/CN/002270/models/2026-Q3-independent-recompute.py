#!/usr/bin/env python3
"""Literal independent recurrence. No importing production/AST/reading its parameters.
Only the final comparisons read published output. Monetary unit: billion CNY.
"""
import json,math,pathlib,base64,gzip

def independent(r=.0975,scale=1,margin_delta=0):
    e=2.36;c=.153;s=.187;p=.06;b=.67213186815;u=.21176170033;reserve=0;registered=.896225431;shares=registered;old=.39698138794;debt=.78858193369;values=[];rows=[]
    for y in range(1,601):
        g=([.09,.09,.08,.07,.06,.05,.04,.03,.025,.02]+[.02]*600)[y-1]
        e0=e;c0=c;e*=1+g;c*=1+(.03 if y<=5 else .02)
        margin=.34-.002*min(y,10)+margin_delta;earn=e*margin
        cap=(e-e0)*margin/(.25 if y<=5 else .18)+(c-c0)*.055/.12
        solar=.187 if y<=20 else 0;minor=earn*(.007+.000336+.0025)+c*.055*.03
        cross=earn*.004;profit=earn+(c+solar)*.055+b*.015-debt*.045-minor-cross
        hq=.02*1.02**(y-1);pfi=p*.015
        b+=profit-cap+(.01925-.004675 if y<=20 else 0)
        repay=min(debt,.78858193369/8 if y<=8 else 0);debt-=repay;b-=repay
        floor=.085*(e+c+solar);pfloor=.03*1.02**(y-1)
        paid_old=min(old,max(b-floor,0));old-=paid_old;b-=paid_old;p+=paid_old
        capacity=profit*(.65 if y<=5 else min(.95,.65+.06*(y-5)))*scale
        release=max(b-floor-capacity-old,0)*.20*scale if y>=6 else 0
        declare=min(capacity+release,max(b-floor,0))
        p+=declare;b-=declare
        recovery=.07 if y==2 else .02 if y==3 else 0
        disposal_loss=-.00695481108 if y==3 else 0
        if y==20:
            b+=.01875;extra=min(.01875*scale,max(b-floor,0));p+=extra;b-=extra;declare+=extra
        p+=recovery+pfi-hq
        legal_profit=declare+pfi-hq+disposal_loss
        add=min(max(registered/2-reserve,0),max(legal_profit-min(max(-u,0),max(legal_profit,0)),0)*.1)
        reserve+=add;u+=legal_profit-add
        if y==1:p-=.125001897
        support=min(max(floor-b,0),max(p-pfloor,0));p-=support;b+=support
        # On tested literal paths no external borrowing; failure would invalidate this independent engine.
        assert b>=floor-1e-9 and p>=pfloor-1e-9
        target=max(profit+pfi-hq,0)*.70 if y<=5 else max(p-pfloor,0)
        D=min(max(u,0),max(p-pfloor,0),target);u-=D;p-=D
        refund=fee=0
        if y>=12:
            request=.4 if y==12 else max(p-pfloor,0)/1.02
            refund=min(max(p-pfloor,0)/1.02,registered*.49,request);fee=refund*.02
            shares-=shares*refund/registered;registered-=refund;p-=refund+fee;u-=fee
        dps=(D+refund)/.896225431
        values.append(dps);rows.append(dict(year=y,dps=dps,parent_cash=p,budget_cash=b,statutory=reserve,retained=u,registered=registered,shares=shares,upstream=declare,old_receipt=paid_old,minority=minor))
    return dict(pv=sum(d/(1+r)**i for i,d in enumerate(values,1)),tv5=sum(d/(1+r)**(i-5) for i,d in enumerate(values,1) if i>5),first5=values[:5],rows=rows)

p=pathlib.Path(__file__).parent;prod=json.loads((p/'2026-Q3-output.json').read_text());trajectory=json.loads(gzip.decompress(base64.b64decode(prod['annual_data']['payload_base64'])))
checks={}
for name,r,scale,margin in [('base_low',.105,1,0),('base_high',.09,1,0),('upstream_80pct',.0975,.8,0),('margin_minus3',.0975,1,-.03)]:
    v=independent(r,scale,margin);expected=prod['paths'][name]
    err=max(abs(v[k]-expected[k]) for k in ['pv','tv5']);assert err<1e-9,(name,err)
    rowerror=0
    for a,b in zip(v['rows'],trajectory[name]):
        rowerror=max(rowerror,abs(a['dps']-b['dps'])/max(1,abs(a['dps'])))
        for key in ['parent_cash','budget_cash','statutory','retained','registered','shares']:
            rowerror=max(rowerror,abs(a[key]-b['end'][key])/max(1,abs(a[key])))
    assert rowerror<1e-8,(name,rowerror)
    checks[name]=dict(pv=v['pv'],tv5=v['tv5'],first5=v['first5'],max_value_error=err,max_all_year_state_relative_error=rowerror,years=600)
(p/'independent-output.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False,indent=2))
