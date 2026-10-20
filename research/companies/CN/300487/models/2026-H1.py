"""蓝晓科技：亿元、亿股；标准库、无网络。"""
import json
from pathlib import Path
R0=29.16439
W0=10.12783
C0=25.54705
S0=2.76751
E0=.25752
SHARES=5.09135722-.0055+5.458307/59.21
D=[.38,.42,.48,.55,.62]
DA=[1.8,2,2.4,2.7,2.85]
GROWTH_CAPEX=[4.5+2.72472*.6+.80407,4+2.72472*.4,1.5588,0,0]

def model(growth,margin,w_ratio,k,g,incremental_roic,distributions=D,shares=SHARES,debt=None):
    revenue=R0; w=W0; cash=C0; rows=[]
    for i in range(5):
        revenue*=1+growth[i]
        nopat=revenue*margin[i]
        w_new=revenue*w_ratio+1.5
        dw=w_new-w; w=w_new
        capex=DA[i]+GROWTH_CAPEX[i]
        fcf=nopat+DA[i]-capex-dw
        start=cash; interest=start*.015*(1-.15)
        release=E0 if i==0 else 0
        payment=debt[i] if debt else 0
        dividend=distributions[i]*shares
        cash=start+fcf+interest+release-dividend-payment
        assert abs((cash-start)-(fcf+interest+release-dividend-payment))<1e-9
        assert abs(fcf-(nopat-GROWTH_CAPEX[i]-dw))<1e-9
        rows.append(dict(year=i+1,revenue=revenue,nopat=nopat,da=DA[i],capex=capex,dw=dw,fcf=fcf,cash_start=start,interest=interest,restricted_release=release,distribution=dividend,debt=payment,cash_end=cash))
    # 存量利润不降档，永续新增利润以明确的新增资本回报约束。
    n6=rows[-1]['nopat']*(1+g)
    reinvest=n6*g/incremental_roic
    ev=(n6-reinvest)/(k-g)
    tv=(ev+cash+S0)/shares
    dpv=sum(d/(1+k)**t for t,d in enumerate(distributions,1))
    value=dpv+tv/(1+k)**5
    assert abs(sum(r['distribution'] for r in rows)-sum(distributions)*shares)<1e-9
    return dict(rows=rows,k=k,g=g,incremental_roic=incremental_roic,nopat6=n6,terminal_reinvestment=reinvest,operating_ev5=ev,cash5=cash,tv5=tv,dividend_pv=dpv,value=value,terminal_pv_share=(value-dpv)/value)

LOW=dict(growth=[.10,.09,.08,.07,.06],margin=[(.52-.08-.06-.017)*.85]*5,w_ratio=.325,k=.105,g=.025,incremental_roic=.18)
HIGH=dict(growth=[.13,.12,.11,.10,.09],margin=[.32555,.32555,.33235,.33235,.3383],w_ratio=.305,k=.095,g=.035,incremental_roic=.24)

def run():
    low=model(**LOW); high=model(**HIGH)
    sensitivity={}
    for name,params in [('low',LOW),('high',HIGH)]:
        for roic in [.12,.18,.24]:
            sensitivity[f'{name}_incremental_roic_{roic}']=model(**dict(params,incremental_roic=roic))['value']
        sensitivity[f'{name}_k_plus_1pct']=model(**dict(params,k=params['k']+.01))['value']
        sensitivity[f'{name}_cash5_haircut_20pct']=model(**params)['value']-.2*model(**params)['cash5']/SHARES/(1+params['k'])**5
    debt=[5.458307*.018,5.458307*.025,5.458307*1.15,0,0]
    noc={x:model(**p,shares=5.09135722-.0055,debt=debt) for x,p in [('low',LOW),('high',HIGH)]}
    weak=model(growth=[-.10,-.05,.08,.08,.06],margin=[(gm-.09-.065-.025)*.85 for gm in [.49,.48,.51,.52,.52]],w_ratio=.36,k=.115,g=.02,incremental_roic=.15,distributions=[.118,0,.2,.3,.38],shares=5.09135722-.0055,debt=debt)
    structural=model(growth=[-.15,-.10,0,.02,.02],margin=[(gm-.09-.065-.025)*.85 for gm in [.45,.42,.42,.43,.43]],w_ratio=.40,k=.125,g=0,incremental_roic=.10,distributions=[.118,0,0,0,0],shares=5.09135722-.0055,debt=debt)
    optimistic=model(**dict(HIGH,growth=[.15,.14,.13,.12,.10],g=.04,incremental_roic=.26))
    aux={}
    for name,n,k,g,r in [('low',8.8,.105,.025,.18),('high',10.73,.095,.035,.24)]:
        pv_cap=sum(x/(1+k)**(i+1) for i,x in enumerate(GROWTH_CAPEX))-E0/(1+k)
        mult=(1-g/r)/(k-g)
        aux[name]=dict(earnings=n,multiple=mult,net_adjustment=C0+S0-pv_cap,shares=SHARES,value=(n*mult+C0+S0-pv_cap)/SHARES,capital_pv=pv_cap)
    # 可手算特例：零增长终值不受新增回报影响；提高新增回报不能减少价值。
    z1=model(**dict(LOW,g=0,incremental_roic=.12));z2=model(**dict(LOW,g=0,incremental_roic=.24))
    assert abs(z1['operating_ev5']-z1['nopat6']/LOW['k'])<1e-9
    assert abs(z1['value']-z2['value'])<1e-9
    assert sensitivity['low_incremental_roic_0.24']>sensitivity['low_incremental_roic_0.12']
    assert low['cash5']>0 and high['cash5']>0
    out=dict(units='亿元/亿股/元每股',shares=SHARES,cash0=C0,other_investment=S0,distributions=D,low=low,high=high,sensitivities=sensitivity,no_conversion=noc,cyclical=weak,structural=structural,optimistic=optimistic,auxiliary=aux,self_checks='cash conservation, distributions, zero-growth terminal, monotonicity passed')
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({x:out[x] for x in ['shares','sensitivities','auxiliary']},ensure_ascii=False,indent=2))
    print({x:(out[x]['value'],out[x]['tv5'],out[x]['cash5']) for x in ['low','high','cyclical','structural','optimistic']})
if __name__=='__main__':run()
