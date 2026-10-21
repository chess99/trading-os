import json
from pathlib import Path
S=2.213939223 # billion fully diluted ordinary shares
EARN=[4.6,4.85,5.1,5.35,5.6]
REINV=[.5,.6,.65,.7,.75]
DPS=[2,2.1,2.2,2.3,2.4]
# All monetary values CNY billion. No price/IRR.
LIQUID=7.653017811+5.173804854-.125741490+.20+.119222862+.85
DEBT=.12819+.048795750+.163529638+.020282517
MINORITY=.271520666
BUFFER=5.5
EQUITY_INV=.939243362+1.358293889
ASSOC=.807763804
COMMIT=.677
FUND_VALUE=.8*COMMIT
CLAIM=.269*7.7671
ASSETS=LIQUID+EQUITY_INV*.8+ASSOC-DEBT-MINORITY-BUFFER-COMMIT+FUND_VALUE
# Start liquidity assumes all commitment uncalled; if already called, reclass same
# amount from pre-existing investments to fund: total bridge is unchanged before
# uniform 20% investment haircut (max extra conservative haircut .1354).
def path(scale=1, first=None):
    p=[x*scale for x in EARN] if first is None else first
    cash=[p[i]-REINV[i] for i in range(5)]
    for g in [.045,.04,.035,.03,.025]:
        nxt=p[-1]*(1+g)
        cash.append(nxt-(nxt-p[-1])/.20)
        p.append(nxt)
    return p,cash

def dcf(r=.10,g=.02,scale=1,legal=0,first=None,terminal_roic=.15):
    p,c=path(scale,first)
    terminal=p[-1]*(1+g)*(1-g/terminal_roic)/(r-g)
    op=sum(x/(1+r)**(i+1) for i,x in enumerate(c))+terminal/(1+r)**10
    term5=sum(c[i]/(1+r)**(i-4) for i in range(5,10))+terminal/(1+r)**5
    return {'per_share':(op+ASSETS-legal)/S,'operating':op,'asset_bridge':ASSETS-legal,'terminal_pv_fraction':terminal/(1+r)**10/(op+ASSETS-legal),'operating_terminal_year5':term5,'earnings':p,'fcfe':c}
base=dcf()
low=dcf(r=.105,g=.015,scale=.95,legal=CLAIM)
high=dcf(r=.095,g=.025,scale=1.05,legal=0)
# Holder's actual five distributions. Residual liquidity excludes operating buffer.
liquid=LIQUID-DEBT-MINORITY-BUFFER-COMMIT
opening=liquid
rows=[]
for i,(earn,reinv,div) in enumerate(zip(EARN,REINV,DPS)):
    interest=liquid*.015
    end=liquid+earn-reinv+interest-div*S
    assert abs(end-(liquid+earn-reinv+interest-div*S))<1e-10
    rows.append(dict(year=i+1,earnings=earn,reinvestment=reinv,fcfe=earn-reinv,dps=div,distribution=div*S,opening_liquid=liquid,interest=interest,closing_liquid=end))
    liquid=end
illiquid=EQUITY_INV*.8+ASSOC+FUND_VALUE
holder={'rows':rows,'year5_liquid':liquid,'year5_other_assets':illiquid,'terminal_low':(dcf(.105,.015,1,CLAIM)['operating_terminal_year5']+liquid+illiquid-CLAIM)/S,'terminal_high':(dcf(.095,.025,1,0)['operating_terminal_year5']+liquid+illiquid)/S}
# auxiliary operating PE, strips all investment returns before addition of assets
def operating_multiple(r,g,n,steady_g=.02,early_roic=.20,steady_roic=.15):
    annual=sum((1+g)**(t-1)*(1-g/early_roic)/(1+r)**t for t in range(1,n+1))
    tail=(1+g)**(n-1)*(1+steady_g)*(1-steady_g/steady_roic)/(r-steady_g)/(1+r)**n
    return annual+tail
pe_low=operating_multiple(.105,.03,5)
pe_high=operating_multiple(.095,.045,10)
aux={'multiple_low':pe_low,'multiple_high':pe_high,'low':(EARN[0]*.95*pe_low+ASSETS-CLAIM)/S,'high':(EARN[0]*1.05*pe_high+ASSETS)/S}
cyclic=dcf(first=[3.5,4.1,4.8,5.2,5.6])
structural=dcf(r=.115,g=0,first=[3.6,3.6,3.6,3.6,3.6],legal=CLAIM)
up=dcf(r=.095,g=.025,scale=1.2)
assert len(rows)==5 and all(x['closing_liquid']>0 for x in rows)
assert abs(sum(x['distribution'] for x in rows)-sum(DPS)*S)<1e-10
assert abs(liquid-opening-sum(x['fcfe']+x['interest']-x['distribution'] for x in rows))<1e-10
assert abs(sum(1/1.1**i for i in range(1,6))-(1-1.1**-5)/.1)<1e-10
out=dict(shares=S,liquid_assets=LIQUID,debt=DEBT,minority=MINORITY,buffer=BUFFER,investment_assets=EQUITY_INV,associate=ASSOC,fund_commitment=COMMIT,fund_value=FUND_VALUE,claim=CLAIM,base=base,low=low,high=high,auxiliary=aux,holder=holder,cyclic=cyclic,structural=structural,upside=up,sensitivity_discount_up_1pct=dcf(.11)['per_share'],sensitivity_profit_down_10pct=dcf(scale=.9)['per_share'],sensitivity_buffer_plus_1bn=base['per_share']-1/S)

def owner_value(r=.10,g=.02,scale=1,legal=0,first=None):
    z=dcf(r,g,scale,legal,first)
    cash=opening-legal
    first5=[x*scale for x in EARN] if first is None else first
    for i in range(5):
        cash=cash*1.015+first5[i]-REINV[i]-DPS[i]*S
    terminal=(z['operating_terminal_year5']+cash+illiquid)/S
    value=sum(DPS[i]/(1+r)**(i+1) for i in range(5))+terminal/(1+r)**5
    return dict(per_share=value,terminal=terminal,closing_liquid=cash,terminal_pv_fraction=terminal/(1+r)**5/value)
holder['terminal_low']=owner_value(.105,.015,1,CLAIM)['terminal']
holder['terminal_high']=owner_value(.095,.025,1,0)['terminal']
out['owner_low']=owner_value(.105,.015,.95,CLAIM)
out['owner_base']=owner_value()
out['owner_high']=owner_value(.095,.025,1.05,0)
out['owner_sensitivity_r_up_1pct']=owner_value(.11)
out['owner_sensitivity_profit_down_10pct']=owner_value(scale=.9)

out['owner_cyclic']=owner_value(first=[3.5,4.1,4.8,5.2,5.6])
sc=opening-CLAIM
for _ in range(5): sc=sc*1.015+2.9-1.2*S
st=(2.9/.115+sc+illiquid)/S
out['owner_structural']={'per_share':sum(1.2/1.115**i for i in range(1,6))+st/1.115**5,'terminal':st,'closing_liquid':sc,'dps':[1.2]*5}
assert sc>0
out['owner_upside']=owner_value(.095,.025,1.2)
# Parent dividend capacity scenario; earnings already include estimated lawful upstreaming.
parent_profit=[4,4.2,4.4,4.6,4.8]
parent_cash=[3.8,4,4.2,4.4,4.6]
parent_retained=5.107252998
parent_liquid=3.651901050+4.176504249-4
pr=[]
for i in range(5):
 parent_retained+=.9*parent_profit[i]-DPS[i]*S
 parent_liquid+=parent_cash[i]-DPS[i]*S
 pr.append(dict(year=i+1,earnings=parent_profit[i],legal_reserve=.1*parent_profit[i],retained=parent_retained,available_liquid=parent_liquid))
assert min(x['retained'] for x in pr)>0 and min(x['available_liquid'] for x in pr)>0
out['parent_capacity']=pr
out['maturity_financial_budget']=.20
out['maturity_total']=.398073523
out['maturity_zero_financial_sensitivity_per_share']=.20*1.015**5/1.10**5/S
if __name__=='__main__':
 print(json.dumps(out,ensure_ascii=False,indent=2))
