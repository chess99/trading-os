#!/usr/bin/env python3
"""Independent arithmetic: does not import/execute production code.
Only loads its JSON to compare independently reconstructed outputs.
Run alongside 2026-Q3-output.json; stdlib only; writes beside __file__.
"""
from pathlib import Path
import json, math
P=Path(__file__).resolve().parent
J=json.loads((P/'2026-Q3-output.json').read_text())
S=1.953888787
A0=8.459661726+3.305495382+.618454834+3.398620908-.8
CASH0=6.552840227+1.356233971+.8-.015815715
D0=4.177908575+4.725179250+.522261872
BRIDGE=CASH0-1.9-D0+.89

def independent(rev,margin,cap,k,g,roi,wc_ratio):
    assets=A0; working=8.2; op=1.9; cashflows=[]; details=[]
    y5ratio=None
    for y in range(10):
        if y>=5:
            ratio=y5ratio+(.6-y5ratio)*(y-4)/5
            target=max(ratio*rev[y],assets*.93)
            investment=max(0,(target-assets*.93)/.965)
        else:investment=cap[y]
        depreciation=.07*assets+.035*investment
        assets=assets+investment-depreciation
        if y==4:y5ratio=assets/rev[y]
        networking=rev[y]*wc_ratio[y]
        opnext=.05*rev[y]
        profit=rev[y]*margin[y]*.85*.998
        fcf=profit+depreciation-investment-(networking-working)-(opnext-op)-(1.1 if y<2 else 0)
        cashflows.append(fcf);details.append([profit,investment,depreciation,fcf,assets])
        working,op=networking,opnext
    perpetualprofit=profit*(1+g)
    tvalue=perpetualprofit*(1-g/roi)/(k-g)
    present=sum(x*math.exp(-(y+1)*math.log1p(k)) for y,x in enumerate(cashflows))+tvalue*math.exp(-10*math.log1p(k))
    option=19.22*(.010569965/(1+k)+.0147635/(1+k)**2)
    outside=CASH0-3.8-1.9*.4
    liquidity_discount=outside*(1-((1.015)/(1+k))**3)
    return (present+BRIDGE-liquidity_discount+option)/S, details,tvalue

low=independent([40,47,53.5,59,64,68.5,72.6,76.2,79.3,82],[.275,.275,.265,.255,.245,.235,.225,.22,.215,.21],[7.8,7.2,6.3,5.7,5.3],.115,.02,.14,[.25,.25,.245]+[.24]*7)
base_115=independent([41.5,50.5,59,66.5,73,78.8,84.3,89.4,93.9,97.7],[.285,.285,.28,.27,.26,.25,.24,.235,.23,.225],[7.8,7.2,6.3,5.7,5.3],.115,.025,.18,[.25,.25,.245]+[.24]*7)
base=independent([41.5,50.5,59,66.5,73,78.8,84.3,89.4,93.9,97.7],[.285,.285,.28,.27,.26,.25,.24,.235,.23,.225],[7.8,7.2,6.3,5.7,5.3],.105,.025,.18,[.25,.25,.245]+[.24]*7)
margin_stress=independent([41.5,50.5,59,66.5,73,78.8,84.3,89.4,93.9,97.7],[.255,.255,.25,.24,.23,.22,.21,.205,.20,.195],[7.8,7.2,6.3,5.7,5.3],.105,.025,.18,[.25,.25,.245]+[.24]*7)
checks={}
def check(n,a,b):
    err=abs(a-b);assert err<1e-8,(n,a,b,err);checks[n]={'independent':a,'production':b,'absolute_error':err}
check('core_low_endpoint',low[0],J['cases']['core_low']['valuation']['value_per_share'])
check('base',base[0],J['cases']['base']['valuation']['value_per_share'])
check('dominant_discount_sensitivity_11_5pct',base_115[0],J['sensitivity']['0.115']['value_per_share'])
check('dominant_operating_margin_minus3pct',margin_stress[0],J['single_parameter_sensitivity']['ebit_margin_-0.03']['valuation']['value_per_share'])
for i,row in enumerate(low[1]):check('core_low_fcf_Y'+str(i+1),row[3],J['cases']['core_low']['annual'][i]['fcff'])
# Separate payer budget, hand arithmetic, excluding any subsidiary upstream cash.
y1=J['cases']['base']['annual'][0]
pay_profit=41.5*.285*.85*.998*.6-5.2*.04*.85+3.8*.015
check('parent_profit_budget_Y1',pay_profit,y1['parent_profit_budget'])
check('parent_retained_Y1',10.146663766+pay_profit-2.2,y1['parent_retained_budget'])
check('reserve_does_not_need_addition',0.,y1['reserve_addition'])
assert 1.157990517>.5*S
# The first-year group excess-cash repayment is .146...; parent cash funds .60 share.
dep=.07*A0+.035*7.8
pcash_before=3.8+(41.5*.285*.85*.998+dep)*.6-(41.5*.25-8.2)*.65-7.8*.5-1.1*.5-5.2*.04*.85+3.8*.015+.010569965*19.22-2.2
repay=y1['debt_repayment']
check('parent_cash_Y1',pcash_before-.6*repay,y1['parent_cash'])
# Year5 terminal is valued from years6-10 plus their terminal, never grown from today's value.
x=J['cases']['base']['annual'][4]
future=sum(base[1][i][3]/1.105**(i-4) for i in range(5,10))+base[2]/1.105**5
outside5=x['closing_cash']-x['parent_cash']-x['operating_cash']*.4
liquidity_discount5=outside5*(1-(1.015/1.105)**3)
terminal5=(future+x['closing_cash']-x['operating_cash']-x['closing_debt']+.89-liquidity_discount5)/S
check('independent_year5_equity_bridge',terminal5,J['cases']['base']['valuation']['terminal_equity_per_share_year5'])
assert J['cases']['platform_failure']['valuation']['feasible'] is False
assert 'terminal_equity_per_share_year5' not in J['cases']['platform_failure']['valuation']
assert len(J['cases']['platform_failure']['annual'])==1
(P/'independent-verification.json').write_text(json.dumps({'status':'passed','checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'status':'passed','checks':len(checks),'max_error':max(x['absolute_error'] for x in checks.values())}))
