"""中国巨石2026-H1；亿元、亿股、元/股。标准库，无网络。"""
import json
from pathlib import Path
S=40.03136728
D=[.55,.60,.65,.70,.75]
REVENUE=[225,238,250,264,277]
NOPAT=[54,55,54,56,58]
DA=[27,30,33,35,36]
CAPEX=[45,50,42,34,33]
WC=[5,5,4,4,4]
ND0=115.21
CASH_BUFFER=30.68

def model(nopat=NOPAT,capex=CAPEX,ds=D,k=.105,wacc=.095,g=.02,roic=.09,debt_rate=.03,minor_div=1.2,associate_div=.6,minor_value=18):
    nd=ND0; rows=[]
    for t,(n,a,c,w,d) in enumerate(zip(nopat,DA,capex,WC,ds),1):
        fcff=n+a-c-w
        interest=(max(nd,0)+CASH_BUFFER)*debt_rate
        end=nd-fcff+interest+d*S+minor_div-associate_div
        rows.append(dict(year=t,nopat=n,depreciation=a,capex=c,working_capital=w,fcff=fcff,net_debt_open=nd,after_tax_finance_cost=interest,common_distribution=d*S,minority_distribution=minor_div,associate_dividend=associate_div,net_debt_close=end))
        assert abs(nd+interest+d*S+minor_div-associate_div-fcff-end)<1e-9
        nd=end
    n6=nopat[-1]*(1+g)
    investment6=n6*g/roic
    fcff6=n6-investment6
    ev=fcff6/(wacc-g)
    eq=ev-nd+17-minor_value
    tv=eq/S
    dpv=sum(d/(1+k)**t for t,d in enumerate(ds,1))
    tpv=tv/(1+k)**5
    assert abs(fcff6+investment6-n6)<1e-9
    assert abs(investment6*roic-n6*g)<1e-9
    return dict(parameters=dict(k=k,wacc=wacc,g=g,incremental_roic=roic,debt_rate=debt_rate,minority_dividend=minor_div,associate_dividend=associate_div,minority_value=minor_value),years=rows,net_debt_year5=nd,nopat_year6=n6,reinvestment_year6=investment6,fcff_year6=fcff6,enterprise_value_year5=ev,equity_value_year5=eq,terminal_per_share=tv,distribution_pv=dpv,terminal_pv=tpv,current_value=dpv+tpv,terminal_weight=tpv/(dpv+tpv))

LOW=dict(k=.105,wacc=.095,g=.02,roic=.09,debt_rate=.03,minor_div=1.2,associate_div=.6,minor_value=18)
HIGH=dict(k=.095,wacc=.085,g=.025,roic=.11,debt_rate=.025,minor_div=.8,associate_div=.8,minor_value=22)
low=model(**LOW); high=model(**HIGH)
# 母公司：新宣派形成利润，旧应收到账只形成现金；集团内部流动不再加进FCFF。
def parent(declared=(24,27,30,33,36),cost=(3,3,2.8,2.5,2.3),receipt_delay=0):
    profit_reserve=14.60; statutory=13.3955207603; cash=19.11; rows=[]
    for t,(new,c,d) in enumerate(zip(declared,cost,D),1):
        profit=new-c
        reserve=min(profit*.1,max(S/2-statutory,0))
        statutory+=reserve
        end=profit_reserve+profit-reserve-d*S
        old_receipt=13.50 if t==1 else 0
        new_receipt=new-receipt_delay if t==1 else new+(receipt_delay if t==2 else 0)
        pre_treasury=cash+old_receipt+new_receipt-c-d*S
        repay=max(pre_treasury-10,0)
        close=pre_treasury-repay
        rows.append(dict(year=t,legal_open=profit_reserve,new_declared=new,parent_net_cost=c,net_profit=profit,statutory_appropriation=reserve,common_distribution=d*S,legal_close=end,old_receivable_collected=old_receipt,new_dividend_collected=new_receipt,cash_open=cash,cash_before_treasury=pre_treasury,available_for_treasury=repay,cash_close=close))
        assert abs(cash+old_receipt+new_receipt-c-d*S-repay-close)<1e-9
        profit_reserve=end;cash=close
    return rows

parent_rows=parent()
assert all(r['legal_close']>=0 and r['cash_close']>=0 for r in parent_rows)
# 18亿元年度新宣派不能支撑既定分配；既有应收到账不修复法定利润缺口。
parent_weak=parent(declared=(18,18,18,18,18))
assert parent_weak[-1]['legal_close']<0
# 独立特例：零增长时无需成长净留存，终态FCFF=NOPAT。
zero=model(**{**LOW,'g':0})
assert zero['reinvestment_year6']==0 and zero['fcff_year6']==58
assert abs(sum([1/(1+0)**t for t in range(1,6)])-5)<1e-12
sensitivity={
 'low_roic_8pct':model(**{**LOW,'roic':.08}),
 'low_roic_11pct':model(**{**LOW,'roic':.11}),
 'low_wacc_plus_1pct':model(**{**LOW,'wacc':.105}),
 'extra_capex_10_year2':model(capex=[45,60,42,34,33],**LOW),
 'no_growth':zero,
}
scenarios={
 'cyclical_weak_low':model(nopat=[40,42,48,54,58],ds=[.4,.45,.5,.6,.7],**LOW),
 'cyclical_weak_high':model(nopat=[40,42,48,54,58],ds=[.4,.45,.5,.6,.7],**HIGH),
 'structural_low':model(nopat=[40,38,37,36,36],ds=[.35,.3,.3,.3,.3],k=.115,wacc=.10,g=0,roic=.07,debt_rate=.035,minor_div=.7,associate_div=.4,minor_value=14),
 'structural_high':model(nopat=[42,42,43,44,45],ds=[.35,.35,.4,.4,.45],k=.105,wacc=.095,g=.01,roic=.08,debt_rate=.03,minor_div=.8,associate_div=.6,minor_value=16),
 'optimistic_low':model(nopat=[58,62,65,68,72],capex=[45,50,45,40,40],ds=[.6,.7,.8,.9,1],k=.095,wacc=.085,g=.025,roic=.12,debt_rate=.025,minor_div=1.2,associate_div=.8,minor_value=24),
 'optimistic_high':model(nopat=[58,62,65,68,72],capex=[45,50,45,40,40],ds=[.6,.7,.8,.9,1],k=.09,wacc=.08,g=.03,roic=.14,debt_rate=.025,minor_div=1.2,associate_div=.8,minor_value=24),
}
aux=[]
for earnings,k,g,roe in [(42,.105,.02,.125),(52,.095,.025,.14)]:
    multiple=(1-g/roe)/(k-g)
    aux.append(dict(earnings=earnings,k=k,g=g,roe=roe,multiple=multiple,current_value=earnings*multiple/S))
output=dict(units='CNY亿元及亿股，每股CNY元',shares=S,distributions=D,revenue=REVENUE,core=dict(low=low,high=high),parent=parent_rows,parent_18_declarations=parent_weak,parent_delayed_10=parent(receipt_delay=10),sensitivities=sensitivity,scenarios=scenarios,auxiliary=aux,self_checks='现金守恒、利润与资本守恒、零增长特例、母公司法定利润和现金、18亿元上划不足均已通过')
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(core={k:{f:v[f] for f in ['current_value','terminal_per_share','net_debt_year5','reinvestment_year6','fcff_year6']} for k,v in output['core'].items()},sensitivity={k:v['current_value'] for k,v in sensitivity.items()},scenarios={k:v['current_value'] for k,v in scenarios.items()},auxiliary=aux,parent_legal=[r['legal_close'] for r in parent_rows]),ensure_ascii=False,indent=2))
