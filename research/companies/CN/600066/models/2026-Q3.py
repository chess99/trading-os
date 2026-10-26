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
out=dict(shares=S,liquid_assets=LIQUID,debt=DEBT,minority=MINORITY,buffer=BUFFER,investment_assets=EQUITY_INV,associate=ASSOC,fund_commitment=COMMIT,fund_value=FUND_VALUE,claim=CLAIM,base=base,low=low,high=high,auxiliary=aux,holder=holder,cyclic=cyclic,structural=structural,upside=up,sensitivity_discount_up_1pct=dcf(.11)['per_share'],sensitivity_profit_down_10pct=dcf(scale=.9)['per_share'],sensitivity_buffer_plus_1bn=base['per_share']-1/S)

# Parent-only sources are not additional consolidated FCFE.
PARENT_PROFIT=[4,4.2,4.4,4.6,4.8]
PARENT_CASH=[3.8,4,4.2,4.4,4.6]
PARENT_OPENING=3.651901050+4.176504249-4
PARENT_RETAINED=5.107252998
HK_INVESTMENT=.02987976755
UPSTREAM=.55 # explicit annual budget within historical aggregate, not HK actual

def value_distributions(r, fcfe, requested_dps, opening_cash, operating_terminal,
                        other_assets, shares, parent_profit, parent_cash,
                        parent_opening, parent_retained, legal=0, support=0,
                        lost_upstream=None, impairment=0, cash_yield=.015,
                        reserve_rate=.10):
    """Actual valuation engine: legal/cash caps determine dividends before PV.
    Monetary inputs billions CNY; five end-year distributions, terminal at year 5.
    legal is external HK payment at opening of year 1; support is an internal
    parent-to-HK transfer at that same time, never a second group expense.
    Impairment only reduces parent legal profit, not consolidated cash again.
    """
    assert len(fcfe)==len(requested_dps)==len(parent_profit)==len(parent_cash)==5
    assert 0<=support<=legal and impairment>=0 and r>0
    lost_upstream=[0]*5 if lost_upstream is None else lost_upstream
    assert len(lost_upstream)==5
    cash=opening_cash-legal
    pc=parent_opening-support
    retained=parent_retained
    assert cash>=0 and pc>=0, 'Opening settlement requires financing outside this budget'
    rows=[]
    for i in range(5):
        start=cash; ps=pc; rs=retained
        # The separate-company investment loss is not the legal claim itself.
        loss=impairment if i==0 else 0
        profit=parent_profit[i]-lost_upstream[i]-loss
        reserve=max(profit,0)*reserve_rate
        cash_before=cash*(1+cash_yield)+fcfe[i]
        parent_before=pc+parent_cash[i]-lost_upstream[i]
        retained_before=retained+profit-reserve
        assert min(cash_before,parent_before,retained_before)>=-1e-10
        paid=min(requested_dps[i]*shares,cash_before,parent_before,retained_before)
        cash=cash_before-paid; pc=parent_before-paid; retained=retained_before-paid
        rows.append(dict(year=i+1,opening_liquid=start,fcfe=fcfe[i],interest=start*cash_yield,
            requested_dps=requested_dps[i],dps=paid/shares,distribution=paid,
            closing_liquid=cash,parent_opening_liquid=ps,parent_net_cash=parent_cash[i]-lost_upstream[i],
            parent_earnings=profit,parent_legal_reserve=reserve,parent_opening_retained=rs,
            parent_closing_liquid=pc,parent_closing_retained=retained,lost_upstream=lost_upstream[i],
            parent_investment_impairment=loss))
        assert abs(cash-start-(fcfe[i]+start*cash_yield-paid))<1e-9
        assert abs(pc-ps-(parent_cash[i]-lost_upstream[i]-paid))<1e-9
        assert abs(retained-rs-(profit-reserve-paid))<1e-9
    terminal=(operating_terminal+cash+other_assets)/shares
    pv_div=sum(row['dps']/(1+r)**row['year'] for row in rows)
    pv_terminal=terminal/(1+r)**5
    return dict(per_share=pv_div+pv_terminal,terminal=terminal,closing_liquid=cash,
                terminal_pv_fraction=pv_terminal/(pv_div+pv_terminal),rows=rows,
                parent_closing_liquid=pc,parent_closing_retained=retained,
                dps=[row['dps'] for row in rows],legal_external_payment=legal,
                internal_parent_support=support,opening_hk_own_cash_used=legal-support,
                parent_impairment=impairment)

def owner_value(r=.10,g=.02,scale=1,legal=0,first=None,support_fraction=1,
                upstream_years=1,impair_support=True,requested_dps=None):
    z=dcf(r,g,scale,legal,first)
    first5=[x*scale for x in EARN] if first is None else first
    # Same operating change reaches parent; hold parent's .2 annual net capital gap.
    parent_profit=[PARENT_PROFIT[i]*first5[i]/EARN[i] for i in range(5)]
    parent_cash=[PARENT_CASH[i]+parent_profit[i]-PARENT_PROFIT[i] for i in range(5)]
    support=legal*support_fraction
    upstream=[UPSTREAM*scale if legal and i<upstream_years else 0 for i in range(5)]
    impairment=(support+HK_INVESTMENT) if legal and impair_support else 0
    return value_distributions(r,z['fcfe'][:5],DPS if requested_dps is None else requested_dps,
        opening,z['operating_terminal_year5'],illiquid,S,parent_profit,parent_cash,
        PARENT_OPENING,PARENT_RETAINED,legal,support,upstream,impairment)

out['owner_low']=owner_value(.105,.015,.95,CLAIM)
out['owner_base']=owner_value()
out['owner_high']=owner_value(.095,.025,1.05)
out['owner_sensitivity_r_up_1pct']=owner_value(.11)
out['owner_sensitivity_profit_down_10pct']=owner_value(scale=.9)
out['owner_cyclic']=owner_value(first=[3.5,4.1,4.8,5.2,5.6])
# A genuinely stagnant operation: 3.6 profit - .7 reinvestment, forever.
out['owner_structural']=value_distributions(.115,[2.9]*5,[1.2]*5,opening,2.9/.115,
    illiquid,S,[3]*5,[2.8]*5,PARENT_OPENING,PARENT_RETAINED,CLAIM,CLAIM,
    [UPSTREAM]*5,CLAIM+HK_INVESTMENT)
out['owner_upside']=owner_value(.095,.025,1.2)
out['parent_capacity']=out['owner_base']['rows']
out['legal_funding_boundaries']={
    'hk_self_funded':owner_value(.105,.015,.95,CLAIM,support_fraction=0),
    'parent_half_funded':owner_value(.105,.015,.95,CLAIM,support_fraction=.5),
    'parent_all_funded':out['owner_low'],
    'parent_all_funded_no_impairment':owner_value(.105,.015,.95,CLAIM,impair_support=False),
    'parent_all_funded_five_year_upstream_block':owner_value(.105,.015,.95,CLAIM,upstream_years=5),
    'profit_down_only':owner_value(.105,.015,.95),
    'legal_only':owner_value(.105,.015,1,CLAIM)}
# Fixed baseline interface uses baseline earnings, no legal settlement; uncertain
# settlement belongs to the separately constrained actual-distribution scenario.
holder['terminal_low']=owner_value(.105,.015)['terminal']
holder['terminal_high']=owner_value(.095,.025)['terminal']
out['maturity_financial_budget']=.20
out['maturity_total']=.398073523
out['maturity_zero_financial_sensitivity_per_share']=.20*1.015**5/1.10**5/S
out['scenario_scope']={
 'units':'CNY billion; shares billion; DPS CNY',
 'year_1':'2026-10-21 to 2027-10-21; five consecutive 12-month forecast intervals',
 'parent_start':'H1 latest separate-company balances; Q3 parent bridge unavailable, no additional H2 cash assumed',
 'core_low_changes':'profit -5% reaches both entities; parent net cash falls by same amount as parent profit; full external claim at year-1 start; parent support funding boundary; first-year upstream .5225 withheld; full new support plus existing HK investment impaired for parent legal-capacity stress; dividend capped annually',
 'core_high_changes':'profit +5% reaches both entities; r .095, g .025; no legal settlement',
 'frozen':'share count, reinvestment, opening group assets, parent 4bn and group 5.5bn operating buffers, target dividend schedule, 1.5% group cash yield; no new debt or asset sale',
 'baseline':'profit scale 1, no claim, r .10/g .02; interface terminal range changes only r/g',
 'upstream':'aggregate .55bn budget; no identified HK component, first-year total blockade is an upper bound, not reported HK dividend',
 'impairment':'funding creates parent investment; full impairment is legal-profit capacity boundary, not a second consolidated cost or legal liability finding'}

# Known closed-form case calls the SAME engine used for published core values.
# Five 1-unit distributions, zero residual cash, 10 terminal, r=10% => 10 exactly.
known=value_distributions(.1,[1]*5,[1]*5,0,10,0,1,[2]*5,[1]*5,0,0,
                          cash_yield=0,reserve_rate=0)
assert abs(known['per_share']-10)<1e-10 and known['closing_liquid']==0
# Parent cash cap forces .5 annually; group retains .5*5=2.5, terminal12.5.
capped=value_distributions(.1,[1]*5,[1]*5,0,10,0,1,[2]*5,[.5]*5,0,0,
                           cash_yield=0,reserve_rate=0)
expected=.5*(1-1.1**-5)/.1+12.5/1.1**5
assert abs(capped['per_share']-expected)<1e-10
assert capped['dps']==[.5]*5 and capped['closing_liquid']==2.5
# Internal funding and parent-only impairment must not change group assets
# when the same external dividends are frozen at zero.
a=value_distributions(.1,[1]*5,[0]*5,3,10,0,1,[2]*5,[1]*5,3,3,
                      legal=1,support=0,cash_yield=0,reserve_rate=0)
b=value_distributions(.1,[1]*5,[0]*5,3,10,0,1,[2]*5,[1]*5,3,3,
                      legal=1,support=1,impairment=1,cash_yield=0,reserve_rate=0)
assert a['closing_liquid']==b['closing_liquid']==7
assert a['per_share']==b['per_share']
legal_cap=value_distributions(.1,[1]*5,[1]*5,0,10,0,1,[.25]*5,[1]*5,0,0,
                             cash_yield=0,reserve_rate=0)
assert legal_cap['dps']==[.25]*5 and legal_cap['closing_liquid']==3.75
assert out['owner_base']['dps']==DPS
assert abs(out['owner_base']['per_share']-28.991789373665966)<1e-10
for key in ['owner_low','owner_base','owner_high','owner_cyclic','owner_structural','owner_upside']:
    assert all(min(row['closing_liquid'],row['parent_closing_liquid'],row['parent_closing_retained'])>=-1e-9 for row in out[key]['rows'])
out['tests']={'actual_function_perpetuity_expected':10,'actual_function_perpetuity_actual':known['per_share'],
    'parent_cash_cap_expected':expected,'parent_cash_cap_actual':capped['per_share'],
    'cash_conservation':'passed for group and parent separately','legal_profit_rollforward':'passed',
    'baseline_regression':'unchanged economic baseline and DPS','internal_support_no_double_count':'passed','parent_legal_cap':'passed'}
if __name__=='__main__':
 print(json.dumps(out,ensure_ascii=False,indent=2))
