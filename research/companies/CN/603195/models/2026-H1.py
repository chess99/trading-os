import json
from pathlib import Path
S=18.03446009
C=149.168673
DEBT=9.220090
CASH=15.
NET=C-DEBT-CASH
D=[1.7,1.8,1.9,2.,2.1]
R=[168,173,178,184,190]
GM=[.42,.422,.423,.424,.425]

LEGACY=.43571206+.202309934-.071874

def cap(e,r,g,roc,net=NET-LEGACY,s=S):
    return (e*(1-g/roc)/(r-g)+net)/s

def run(margin_shift=0,cap_extra=0,revenues=R,margins=GM,dividends=D):
    c=C;s=S;parent=55.094884;ret=9.1003;reserve=8.7031;rows=[];run_cash=CASH
    for i,(rev,gm,d) in enumerate(zip(revenues,margins,dividends)):
        opening=c; opening_s=s
        nopat=(rev*(gm+margin_shift-.07-.009)-(7.15+.15*i)-(6.55+.2875*i)-(.25+.0125*i)-.10)*.83-(.08+.005*i)
        da=3.1+.2*i;cx=5.2+.2*i+cap_extra;wc=.5
        fc=nopat+da-cx-wc
        interest=(c-run_cash)*.02-DEBT*.02*.83
        payout=s*d
        cancelled=[.02185530,.01097124,0,0,0][i]
        refund=[.43571206,.202309934,0,0,0][i]
        recovery=.071874 if i==0 else 0
        c+=fc+interest-payout-refund+recovery;s-=cancelled
        next_cash=CASH*rev/168
        opfc=fc-(next_cash-run_cash)
        parent_interest=(parent-5)*.02-2.25*.02*.83
        sub=[20,22,24,26,28][i]
        parent_fc=7.8+.3*i
        parent_profit=8.5+.3*i+sub+parent_interest
        add_reserve=min(max(0,S*.5-reserve),parent_profit*.1)
        reserve+=add_reserve;ret+=parent_profit-add_reserve-payout
        parent+=parent_fc+sub+parent_interest-payout-refund+recovery
        assert abs(c-(opening+fc+interest-payout-refund+recovery))<1e-9
        assert abs(s-(opening_s-cancelled))<1e-10
        assert parent>0 and ret>0 and c>=parent
        rows.append(dict(year=i+1,revenue=rev,margin=gm+margin_shift,nopat=nopat,da=da,capex=cx,wc=wc,operating_fcf=opfc,finance_net=interest,dividend_per_share=d,dividend_total=payout,refund=refund,shares=s,cash=c,required_cash=next_cash,net_financial=c-DEBT-next_cash,parent_cash=parent,parent_retained=ret,sub_dividend=sub))
        run_cash=next_cash
    return rows

def dcf(rows,r,g,roc):
    tv=rows[-1]['nopat']*(1+g)*(1-g/roc)/(r-g)
    present=sum(x['operating_fcf']/(1+r)**x['year'] for x in rows)
    # Repurchase refunds less recovered historical plan cash are equity cash costs, paired with initial shares.
    equity_cost=sum((x['refund']-(.071874 if x['year']==1 else 0))/(1+r)**x['year'] for x in rows)
    value=(present+tv/(1+r)**5+NET-equity_cost)/S
    return dict(value=value,terminal=tv,terminal_pv_share=tv/(1+r)**5/(value*S))
base=run();lo=cap(35.5,.09,.02,.20);hi=cap(37.5,.085,.03,.25)
last=base[-1]
tlo=cap(last['nopat']*1.02,.09,.02,.20,last['net_financial'],last['shares'])
thi=cap(last['nopat']*1.03,.085,.03,.25,last['net_financial'],last['shares'])
scenarios={}
for name,revs,mars in [('cycle',[155,160,168,178,186],[.40,.405,.415,.422,.425]),('structural',[145,145,145,146,147],[.37]*5),('upside',[172,180,189,200,212],[.425,.43,.435,.44,.442])]:
    # Operating valuation isolates operating scenario; distributions are not asserted for these alternatives.
    rows=run(revenues=revs,margins=mars,dividends=[1.0]*5)
    params=(.10,.01,.15) if name=='structural' else (.09,.02,.20)
    scenarios[name]=dict(nopat5=rows[-1]['nopat'],dcf=dcf(rows,*params)['value'])
out=dict(inputs=dict(shares=S,cash=C,debt=DEBT,required_cash=CASH,net_financial=NET),core=dict(low=lo,high=hi),base=base,terminal=dict(low=tlo,high=thi),dcf=dict(low=dcf(base,.09,.02,.20),high=dcf(base,.085,.03,.25)),sensitivity=dict(margin_minus_2pp=dcf(run(margin_shift=-.02),.09,.02,.20)['value'],capex_plus_2=dcf(run(cap_extra=2),.09,.02,.20)['value'],capitalization_g1=cap(35.5,.09,.01,.20),capitalization_roc15=cap(35.5,.09,.02,.15),financial_loss10=(102.25*.1)/S),scenarios=scenarios)
assert abs(cap(10,.1,0,.2,0,1)-100)<1e-9
assert len(base)==5 and all(x['net_financial']>0 for x in base)
assert abs(S-base[-1]['shares']-.03282654)<1e-10
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='base'},ensure_ascii=False,indent=2))
