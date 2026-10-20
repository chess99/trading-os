"""中国人保2026-H1；亿元、亿股；标准库、无网络。"""
import json
from pathlib import Path
S=442.23990583
B0=3401.39
D=[.23,.25,.27,.29,.31]
COMMON=367.45/498.12

def operating_profit(cr,half_gain,covariance_pool=32.934):
    # Half-year realized/unrealized equity gains normalized, then underwriting seasonality.
    n=2*(367.45-(351.70-half_gain)*.8*COMMON)
    u=5100*(1-cr)
    n-=(2*140.10-u)*.8*.6898
    # Life/health financing costs partly co-move with policyholder participation.
    # 2026 net costs 230.56, prior H1 179.66; reserve 10% for volume/accretion.
    # Only proportional removal of the incremental equity-gain shock is reversed.
    ratio=min(1.,max(0.,(351.70-half_gain)/(351.70-86.81)))
    relief=covariance_pool*ratio
    return n-1.50+2*relief*.8*.80

def model(p,r,g,transition=15,y=.03,q=.10,cr=.97):
    k=B0;x=0.;rows=[]
    for t in range(1,transition+1):
        op=p*(1+g)**(t-1); income=op+y*x; need=g*k
        alpha=0 if t<=5 else min(1,(t-5)/(transition-5))
        baseline=D[t-1]*S if t<=5 else D[-1]*S*1.04**(t-5)
        distributable=op-need+y*x+q*x
        cash=baseline*(1-alpha)+distributable*alpha
        nx=x+income-need-cash;nk=k+need
        assert nx>-1e-8
        assert abs((nk+nx)-(k+x)-income+cash)<1e-8
        rows.append(dict(year=t,operating_profit=op,extra_asset_income=y*x,profit=income,necessary_capital_begin=k,extra_assets_begin=x,necessary_addition=need,distribution=cash,dps=cash/S,extra_assets_end=nx,book_end=nk+nx,payout=cash/income))
        k,x=nk,nx
    opnext=p*(1+g)**transition
    franchise_tv=(opnext-g*k)/(r-g)
    extra_tv=x*(y+q)/(r+q)
    tv=franchise_tv+extra_tv
    pv=sum(z['distribution']/(1+r)**z['year'] for z in rows)+tv/(1+r)**transition
    tv5=(sum(z['distribution']/(1+r)**(z['year']-5) for z in rows if z['year']>5)+tv/(1+r)**(transition-5))/S
    # At mature policy all extra principal is released over time, not written off.
    assert abs(sum(q*x*(1-q)**t for t in range(1000))-x)<1e-6
    assert abs((y+q)/(r+q)-1)<1e-10 if abs(y-r)<1e-10 else True
    return dict(p=p,r=r,g=g,transition_year=transition,rows=rows,value=pv/S,tv5=tv5,terminal_year_value=tv/S,terminal_franchise=franchise_tv/S,terminal_extra=extra_tv/S,terminal_pv_share=tv/(1+r)**transition/pv)
low=model(operating_profit(.97,120),.105,.025)
high=model(operating_profit(.965,150),.098,.03,cr=.965)
base=model((low['p']+high['p'])/2,.1015,.0275)
sens={
 'fixed_cost_growth_20pct_low':model(operating_profit(.97,120,14.968),.105,.025),
 'zero_covariance_low':model(operating_profit(.97,120,0),.105,.025),
 'zero_covariance_high':model(operating_profit(.965,150,0),.098,.03),
 'full_covariance_low':model(operating_profit(.97,120,50.90),.105,.025),
 'full_covariance_high':model(operating_profit(.965,150,50.90),.098,.03),
 'low_cost_ratio_plus_1pt':model(low['p']-5100*.01*.8*.6898,.105,.025),
 'low_release_delay_10years':model(low['p'],.105,.025,transition=25),
 'low_extra_return_2pct':model(low['p'],.105,.025,y=.02),
 'structural':model(operating_profit(.99,90),.115,.015,transition=25,y=.02),
 'upside':model(operating_profit(.955,160),.098,.035,transition=10),
}
# Permanent low-payout alternative: retained financial principal never directly released,
# but its future income and dividends are valued recursively (no arbitrary write-off).
def permanent_policy(z,payout=.25,y=.03):
    r,g=z['r'],z['g']; k=B0*(1+g)**5;x=z['rows'][4]['extra_assets_end']
    b=payout*y/(r-(1-payout)*y)
    a=(payout*z['p']/B0+b*((1-payout)*z['p']/B0-g))/(r-g)
    tv=a*k+b*x
    return sum(d/(1+r)**t for t,d in enumerate(D,1))+tv/S/(1+r)**5
permanent=permanent_policy(low)
# Separate parent payer bridge: direct holdings prevent assigning indirect holdings twice.
parent=[];cash=11.55;reserve=84.85
for t,d in enumerate(D,1):
 fac=1.03**(t-1)
 pc=(5100*.03*.8+240)*.35*.6898*fac
 life=135*.25*.7108*fac
 health=70*.25*.6932*fac
 other=8*fac; own=5*fac;cost=16*fac
 inflow=pc+life+health+other+own
 earnings=inflow-cost
 reserve+=earnings*.9-d*S
 cash+=earnings-d*S
 assert reserve>0 and cash>0
 parent.append(dict(year=t,pc_dividend=pc,life_direct_dividend=life,health_direct_dividend=health,other_upstream=other,own_income=own,cost=cost,net_cash=earnings,common_distribution=d*S,cash_end=cash,statutory_profit_after_reserve_end=reserve,twenty_pct_receipt_delay=.2*(pc+life+health+other)))
# Alternative immediate pass-through economic value (no extra trapped capital): cross-check.
aux={}
for name,z in [('low',low),('high',high)]:
 aux[name]=(z['p']-z['g']*B0)/(z['r']-z['g'])/S
# Self-contained PV recipes, not dependent on model function, for external recalculation.
recipes=[]
for name,z in [('core_low',low),('cost_ratio_plus_1pt',sens['low_cost_ratio_plus_1pt']),('core_high',high)]:
 recipes.append(dict(label=name,type='pv',cashflows=[dict(t=v['year'],amount=v['distribution']) for v in z['rows']],terminal=dict(t=z['transition_year'],amount=z['terminal_year_value']*S),rate=z['r'],net_adjustment=0,shares=S,expected_per_share=z['value']))
assert abs(sum(d/(1+low['r'])**t for t,d in enumerate(D,1))+low['tv5']/(1+low['r'])**5-low['value'])<1e-10
special=model(low['p'],.105,.025,y=.105)
assert abs(special['terminal_extra']*S-special['rows'][-1]['extra_assets_end'])<1e-6
out=dict(shares=S,book_initial=B0,common_profit_share=COMMON,low=low,high=high,base=base,sensitivities=sens,parent=parent,auxiliary=aux,permanent_low_payout_value=permanent,recipes=recipes)
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'normal_profit':[low['p'],high['p']],'value':[low['value'],high['value']],'tv5':[low['tv5'],high['tv5']],'sensitivity':{k:v['value'] for k,v in sens.items()},'auxiliary':aux,'parent_year5':parent[-1]},ensure_ascii=False,indent=2))
