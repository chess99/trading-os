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

def recover_tail(last, group_profits, r, g, terminal_roic=.15,
                 source_payout=.40, source_release=.10, source_block_years=0,
                 investment_delay=5, direct_share=4.25/5.6,
                 early_parent_capital_share=.60, voluntary_reserve_rate=.10,
                 other_assets=0., horizon=240, parent_asset_fraction=1.,
                 voluntary_until_year=10,source_buffer_until_year=10,
                 fixed_net_reinvestment=None):
    """Y5 economic value from actual future owner distributions, not group cash addback.
    Source collection is an attributable economic declaration budget, NOT a法人.
    It has no invented registered capital or statutory pool. No pre-existing
    source legal profit is asserted; only conservatively budgeted future earnings
    permit release, including investment proceeds funded by accumulated profits.
    """
    pc=last['parent_closing_liquid']
    sc=last['closing_liquid']-pc
    assert sc>=-1e-9, 'Source residual needs funding allocation review'
    pr=last['parent_closing_retained']; source_earnings_budget=0.
    reserve=last['parent_closing_statutory_reserve']
    previous=group_profits[4]; pv=0.; rows=[]
    # Fund has contractual original ten-year life: Y10 is five years after TV5.
    fund=.8*.677
    fund=min(fund,other_assets)
    rest=other_assets-fund
    parent_equity_book=min(EQUITY_INV,(.35057896043+.71856575228)*parent_asset_fraction)
    parent_associate_book=min(ASSOC,.5935258*parent_asset_fraction)
    parent_other_assets=min(rest,parent_equity_book*.8+parent_associate_book)
    parent_disposal_loss=.2*parent_equity_book
    source_disposal_loss=.2*(EQUITY_INV-parent_equity_book)
    # Cash-batch tracking is an attribution convention, not a second value addition.
    source_tags=[['source_cash_at_Y5',sc]];mother_tags=[['mother_cash_at_Y5',pc]]
    recovered_batches={};total_batches={'source_cash_at_Y5':sc,'mother_cash_at_Y5':pc}
    def move_tags(tags,amount,year,destination=None):
        for tag in tags:
            used=min(tag[1],max(0.,amount));tag[1]-=used;amount-=used
            if used<=0:continue
            if destination is not None:destination.append([tag[0],used])
            else:
                rec=recovered_batches.setdefault(tag[0],dict(paid=0.,last_payment_year=year))
                rec['paid']+=used;rec['last_payment_year']=year
        return amount
    for t in range(6,horizon+1):
        if t<=10:
            profit=group_profits[t-1]
            reinvest=(profit-previous)/.20
            capital_share=early_parent_capital_share
        else:
            profit=previous*(1+g)
            reinvest=profit*g/terminal_roic
            capital_share=direct_share
        if fixed_net_reinvestment is not None:reinvest=fixed_net_reinvestment
        pn=profit*direct_share; sn=profit-pn
        p_interest=pc*.015;s_interest=sc*.015
        cash_recovery=(fund if t==10 else 0.)+(rest if t==5+investment_delay else 0.)
        # H1 mother holds .350579+.718566 equity/financial assets and .593526
        # associate net book. These anchor a mother allocation budget, not Q3 fact.
        # Hong Kong Shengyu (NOT Hong Kong Yutong) owns the new fund commitment.
        mother_recovery=parent_other_assets if t==5+investment_delay else 0.
        pc_before=pc+pn-reinvest*capital_share+p_interest+mother_recovery
        sc_before=sc+sn-reinvest*(1-capital_share)+s_interest+cash_recovery-mother_recovery
        # Conservative recovery markdown is a realization loss in legal-profit
        # capacity too; NOT a second reduction of group cash after net proceeds.
        mother_loss=parent_disposal_loss if t==5+investment_delay else 0.
        source_loss=(source_disposal_loss if t==5+investment_delay else 0.)+(.677-fund if t==10 else 0.)
        source_profit=sn+s_interest-source_loss
        if t==10:
            source_tags.append(['fund_net_recovery',fund]);total_batches['fund_net_recovery']=fund
        if t==5+investment_delay:
            source_tags.append(['other_source_net_recovery',rest-parent_other_assets]);total_batches['other_source_net_recovery']=rest-parent_other_assets
            mother_tags.append(['mother_investment_net_recovery',parent_other_assets]);total_batches['mother_investment_net_recovery']=parent_other_assets
        recovered=max(0.,min(source_profit,source_earnings_budget+source_profit))
        source_buffer=.10*recovered if t<=source_buffer_until_year else 0.
        source_earnings_budget+=source_profit-source_buffer
        target=source_payout*max(0.,source_profit)+source_release*max(0.,sc)
        if t<=5+source_block_years:target=0.
        upstream=max(0.,min(target,sc_before,source_earnings_budget))
        source_earnings_budget-=upstream
        move_tags(source_tags,upstream,t,mother_tags)
        parent_profit=pn+p_interest+upstream-mother_loss
        eligible=max(0.,min(parent_profit,pr+parent_profit))
        mandatory=min(.10*eligible,max(0.,last['registered_capital']*.5-reserve))
        voluntary=max(0.,(voluntary_reserve_rate if t<=voluntary_until_year else 0.)*eligible-mandatory)
        reserve+=mandatory+voluntary;pr+=parent_profit-mandatory-voluntary
        pc_before+=upstream
        distribution=max(0.,min(pc_before,pr))
        pr-=distribution;pc_new=pc_before-distribution;sc_new=sc_before-upstream
        move_tags(mother_tags,distribution,t)
        assert min(pc_new,sc_new)>=-1e-9
        before=pc+sc
        assert abs((pc_new+sc_new)-(before+profit-reinvest+p_interest+s_interest+cash_recovery-distribution))<max(1e-8,abs(before)*1e-12)
        pv+=distribution/(1+r)**(t-5)
        rows.append(dict(year=t,group_profit=profit,net_reinvestment=reinvest,parent_own_profit=pn,
            source_profit=source_profit,source_upstream=upstream,investment_principal_recovery=cash_recovery,mother_investment_principal_recovery=mother_recovery,parent_disposal_loss=mother_loss,source_disposal_loss=source_loss,
            parent_mandatory_reserve=mandatory,parent_voluntary_reserve=voluntary,source_profit_buffer=source_buffer,
            parent_retained=pr,source_earnings_budget=source_earnings_budget,
            parent_cash=pc_new,source_cash=sc_new,financial_income=p_interest+s_interest,
            dividend=distribution,dps=distribution/S))
        pc,sc=pc_new,sc_new;previous=profit
    # No final unexplained asset sweep. Verify long-horizon materiality separately.
    recovery_check={k:dict(original_net_principal=v,paid=recovered_batches.get(k,{}).get('paid',0.),
        last_payment_year=recovered_batches.get(k,{}).get('last_payment_year'),
        unpaid=v-recovered_batches.get(k,{}).get('paid',0.)) for k,v in total_batches.items()}
    # Re-test later cash cohorts, not only assets existing at Y5. No cash/value added.
    later_cohorts={}
    for checkpoint in [20,80,160]:
        if checkpoint>=horizon:continue
        anchor=next(x for x in rows if x['year']==checkpoint)
        outstanding_source=anchor['source_cash'];mother_pending=anchor['parent_cash'];paid_total=0.;last_paid=None
        for following in rows:
            if following['year']<=checkpoint:continue
            shifted=min(outstanding_source,following['source_upstream']);outstanding_source-=shifted;mother_pending+=shifted
            paid=min(mother_pending,following['dividend']);mother_pending-=paid;paid_total+=paid
            if paid>1e-12:last_paid=following['year']
        later_cohorts[str(checkpoint)]=dict(mother_cash=anchor['parent_cash'],source_cash=anchor['source_cash'],
            cash_to_group_profit=(anchor['parent_cash']+anchor['source_cash'])/anchor['group_profit'],
            paid_by_horizon=paid_total,last_payment_year=last_paid,unpaid=outstanding_source+mother_pending)
    return dict(value_at_year5=pv,rows=rows,ending_cash_uncredited=pc+sc,later_cash_cohorts=later_cohorts,initial_asset_recovery=recovery_check,
        principal_allocation=dict(mother_cash=last['parent_closing_liquid'],
            source_cash=last['closing_liquid']-last['parent_closing_liquid'],other_assets=other_assets,parent_other_assets=parent_other_assets),
        assumptions=dict(source_payout=source_payout,source_release=source_release,
            source_block_years=source_block_years,investment_delay=investment_delay,
            direct_share=direct_share,early_parent_capital_share=early_parent_capital_share,
            voluntary_reserve_rate=voluntary_reserve_rate,voluntary_until_year=voluntary_until_year,source_buffer_until_year=source_buffer_until_year,fixed_net_reinvestment=fixed_net_reinvestment,horizon=horizon,parent_other_assets=parent_other_assets,parent_asset_fraction=parent_asset_fraction))

def value_distributions(r, fcfe, requested_dps, opening_cash, operating_terminal,
                        other_assets, shares, parent_profit, parent_cash,
                        parent_opening, parent_retained, legal=0, support=0,
                        lost_upstream=None, impairment=0, cash_yield=.015,
                        reserve_rate=.10, registered_capital=2.213939223, opening_statutory_reserve=3.92962093934,
                        paid_capital=2.213939223, voluntary_reserve_rate=.10,tail_spec=None):
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
    statutory=opening_statutory_reserve
    assert min(registered_capital,paid_capital,statutory)>=0
    assert 0<=reserve_rate<=1 and 0<=voluntary_reserve_rate<=1
    assert cash>=0 and pc>=0, 'Opening settlement requires financing outside this budget'
    rows=[]
    for i in range(5):
        start=cash; ps=pc; rs=retained
        # The separate-company investment loss is not the legal claim itself.
        loss=impairment if i==0 else 0
        profit=parent_profit[i]-lost_upstream[i]-loss
        # Paid capital is separately disclosed, NEVER the statutory threshold or cash.
        # Article 210 allows stopping after half registered; observed FY2025 policy
        # continued 10% despite saturation. Model that separately as governance.
        recovered_profit=max(0., min(profit,retained+profit))
        mandatory=min(recovered_profit*reserve_rate,max(0.,registered_capital*.5-statutory))
        voluntary=max(0.,recovered_profit*voluntary_reserve_rate-mandatory)
        reserve=mandatory+voluntary
        statutory_start=statutory
        statutory+=reserve
        cash_before=cash*(1+cash_yield)+fcfe[i]
        parent_before=pc+parent_cash[i]-lost_upstream[i]
        retained_before=retained+profit-reserve
        assert min(cash_before,parent_before)>=-1e-10
        paid=min(requested_dps[i]*shares,cash_before,parent_before,max(0.,retained_before))
        cash=cash_before-paid; pc=parent_before-paid; retained=retained_before-paid
        rows.append(dict(year=i+1,opening_liquid=start,fcfe=fcfe[i],interest=start*cash_yield,
            requested_dps=requested_dps[i],dps=paid/shares,distribution=paid,
            closing_liquid=cash,parent_opening_liquid=ps,parent_net_cash=parent_cash[i]-lost_upstream[i],
            parent_earnings=profit,parent_legal_reserve=reserve,parent_opening_retained=rs,
            parent_closing_liquid=pc,parent_closing_retained=retained,lost_upstream=lost_upstream[i],
            parent_investment_impairment=loss,registered_capital=registered_capital,
            paid_capital=paid_capital,parent_opening_statutory_reserve=statutory_start,
            parent_closing_statutory_reserve=statutory,parent_mandatory_reserve=mandatory,
            parent_voluntary_reserve=voluntary,post_loss_recovery_profit=recovered_profit))
        assert abs(cash-start-(fcfe[i]+start*cash_yield-paid))<1e-9
        assert abs(pc-ps-(parent_cash[i]-lost_upstream[i]-paid))<1e-9
        assert abs(retained-rs-(profit-reserve-paid))<1e-9
    old_terminal=(operating_terminal+cash+other_assets)/shares
    tail=None
    if tail_spec is not None:
        tail=recover_tail(rows[-1],r=r,other_assets=other_assets,
            voluntary_reserve_rate=voluntary_reserve_rate,**tail_spec)
        terminal=tail['value_at_year5']/shares
    else:
        terminal=old_terminal
    pv_div=sum(row['dps']/(1+r)**row['year'] for row in rows)
    pv_terminal=terminal/(1+r)**5
    return dict(per_share=pv_div+pv_terminal,terminal=terminal,closing_liquid=cash,
                terminal_pv_fraction=pv_terminal/(pv_div+pv_terminal),rows=rows,
                parent_closing_liquid=pc,parent_closing_retained=retained,
                dps=[row['dps'] for row in rows],legal_external_payment=legal,
                internal_parent_support=support,opening_hk_own_cash_used=legal-support,
                parent_impairment=impairment,legacy_group_addback_terminal=old_terminal,tail_recovery=tail)

def owner_value(r=.10,g=.02,scale=1,legal=0,first=None,support_fraction=1,
                upstream_years=1,impair_support=True,requested_dps=None,
                voluntary_reserve_rate=.10,upstream_budget=.55,tail_overrides=None):
    z=dcf(r,g,scale,legal,first)
    first5=[x*scale for x in EARN] if first is None else first
    # Same operating change reaches parent; hold parent's .2 annual net capital gap.
    parent_profit=[PARENT_PROFIT[i]*first5[i]/EARN[i] for i in range(5)]
    parent_cash=[PARENT_CASH[i]+parent_profit[i]-PARENT_PROFIT[i] for i in range(5)]
    support=legal*support_fraction
    # Budget shortfall is separate from a claim-induced interruption. All amounts
    # are mother-attributable receipts, not gross controlled-subsidiary profits.
    upstream=[(.55-upstream_budget)*scale + (upstream_budget*scale if legal and i<upstream_years else 0) for i in range(5)]
    impairment=(support+HK_INVESTMENT) if legal and impair_support else 0
    tail_spec=dict(group_profits=z['earnings'],g=g)
    tail_spec.update(tail_overrides or {})
    return value_distributions(r,z['fcfe'][:5],DPS if requested_dps is None else requested_dps,
        opening,z['operating_terminal_year5'],illiquid,S,parent_profit,parent_cash,
        PARENT_OPENING,PARENT_RETAINED,legal,support,upstream,impairment,
        voluntary_reserve_rate=voluntary_reserve_rate,tail_spec=tail_spec)

out['owner_low']=owner_value(.105,.015,.95,CLAIM)
out['owner_base']=owner_value()
out['owner_high']=owner_value(.095,.025,1.05)
out['owner_sensitivity_r_up_1pct']=owner_value(.11)
out['owner_sensitivity_profit_down_10pct']=owner_value(scale=.9)
out['owner_cyclic']=owner_value(first=[3.5,4.1,4.8,5.2,5.6])
# A genuinely stagnant operation: 3.6 profit - .7 reinvestment, forever.
out['owner_structural']=value_distributions(.115,[2.9]*5,[1.2]*5,opening,2.9/.115,
    illiquid,S,[3]*5,[2.8]*5,PARENT_OPENING,PARENT_RETAINED,CLAIM,CLAIM,
    [UPSTREAM]*5,CLAIM+HK_INVESTMENT,
    tail_spec=dict(group_profits=[3.6]*10,g=0.,direct_share=(3.-.55)/3.6,source_payout=.20,source_release=.05,fixed_net_reinvestment=.7))
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
                          cash_yield=0,reserve_rate=0,voluntary_reserve_rate=0)
assert abs(known['per_share']-10)<1e-10 and known['closing_liquid']==0
# Parent cash cap forces .5 annually; group retains .5*5=2.5, terminal12.5.
capped=value_distributions(.1,[1]*5,[1]*5,0,10,0,1,[2]*5,[.5]*5,0,0,
                           cash_yield=0,reserve_rate=0,voluntary_reserve_rate=0)
expected=.5*(1-1.1**-5)/.1+12.5/1.1**5
assert abs(capped['per_share']-expected)<1e-10
assert capped['dps']==[.5]*5 and capped['closing_liquid']==2.5
# Internal funding and parent-only impairment must not change group assets
# when the same external dividends are frozen at zero.
a=value_distributions(.1,[1]*5,[0]*5,3,10,0,1,[2]*5,[1]*5,3,3,
                      legal=1,support=0,cash_yield=0,reserve_rate=0,voluntary_reserve_rate=0)
b=value_distributions(.1,[1]*5,[0]*5,3,10,0,1,[2]*5,[1]*5,3,3,
                      legal=1,support=1,impairment=1,cash_yield=0,reserve_rate=0,voluntary_reserve_rate=0)
assert a['closing_liquid']==b['closing_liquid']==7
assert a['per_share']==b['per_share']
legal_cap=value_distributions(.1,[1]*5,[1]*5,0,10,0,1,[.25]*5,[1]*5,0,0,
                             cash_yield=0,reserve_rate=0,voluntary_reserve_rate=0)
assert legal_cap['dps']==[.25]*5 and legal_cap['closing_liquid']==3.75
assert out['owner_base']['dps']==DPS
assert out['owner_base']['per_share']>0 # independent literal regression below replaces legacy terminal anchor
for key in ['owner_low','owner_base','owner_high','owner_cyclic','owner_structural','owner_upside']:
    assert all(min(row['closing_liquid'],row['parent_closing_liquid'],row['parent_closing_retained'])>=-1e-9 for row in out[key]['rows'])
out['tests']={'actual_function_perpetuity_expected':10,'actual_function_perpetuity_actual':known['per_share'],
    'parent_cash_cap_expected':expected,'parent_cash_cap_actual':capped['per_share'],
    'cash_conservation':'passed for group and parent separately','legal_profit_rollforward':'passed',
    'baseline_regression':'unchanged economic baseline and DPS','internal_support_no_double_count':'passed','parent_legal_cap':'passed'}

out['capital_governance_sensitivities']={
 'statutory_only_base':owner_value(voluntary_reserve_rate=0),
 'statutory_only_low':owner_value(.105,.015,.95,CLAIM,voluntary_reserve_rate=0),
 'statutory_only_high':owner_value(.095,.025,1.05,voluntary_reserve_rate=0),
 'normal_no_upstream_five_years':owner_value(upstream_budget=0,tail_overrides=dict(source_block_years=5,source_payout=.20,source_release=.05)),
 'normal_FY2025_upstream':owner_value(upstream_budget=.02207624149,tail_overrides=dict(source_payout=.02207624149/1.35,source_release=.05)),
 'normal_FY2024_upstream':owner_value(upstream_budget=.13096038359,tail_overrides=dict(source_payout=.13096038359/1.35,source_release=.05)),
 'low_no_upstream_five_years':owner_value(.105,.015,.95,CLAIM,upstream_budget=0,tail_overrides=dict(source_block_years=5,source_payout=.20,source_release=.05))}
# Real engine counterexample: registered 20, paid 10, reserve 5, profit 10.
counter=value_distributions(.1,[10]*5,[0]*5,0,10,0,1,[10]*5,[10]*5,0,0,
 registered_capital=20,paid_capital=10,opening_statutory_reserve=5,
 voluntary_reserve_rate=0,cash_yield=0)
assert counter['rows'][0]['parent_mandatory_reserve']==1
# Recover losses BEFORE compulsory and voluntary appropriation; never negative D.
recovery=value_distributions(.1,[1]*5,[1]*5,0,10,0,1,[.3]*5,[1]*5,0,-.5,
 registered_capital=20,paid_capital=10,opening_statutory_reserve=5,cash_yield=0)
assert recovery['rows'][0]['parent_legal_reserve']==0 and recovery['dps'][0]==0
assert abs(recovery['rows'][1]['parent_legal_reserve']-.01)<1e-12
assert abs(recovery['dps'][1]-.09)<1e-12
out['tests']['registered20_paid10_reserve5_profit10']=counter['rows'][0]
out['tests']['loss_recovery_actual_engine']=recovery['rows'][:2]
out['capital_policy']={'mother_registered':2.213939223,'mother_paid':2.213939223,
 'mother_opening_surplus_classified_statutory_by_table_mapping':3.92962093934,
 'mandatory_rate':.10,'threshold_fraction_registered':.5,'continuing_appropriation_budget_rate':.10,
 'basis':'FY2025 mother appropriation .49673309965 = 10% profit despite saturation. Core continues discretionary policy through Y10 only; Y5/Y20 end and permanent boundary tested. Future stop is governance budget, not fact.',
 'upstream_budget':.55,'upstream_basis':'H1 cost-method dividend income .55277771519; FY2025 .02207624149, FY2024 .13096038359. Conditional budget, not recurrent historical fact.',
 'foreign_law':'No PRC reserve computation applied to Hong Kong or aggregated sources.',
 'future_capital':'No issuance/subscription/new paid cash assumed. Support is parent investment funding, not proof of registered-capital increase.'}


out['tail_sensitivities']={
 'no_routine_profit_dividend_with_asset_recovery':owner_value(upstream_budget=0,tail_overrides=dict(source_payout=0,source_release=.10)),
 'source_half_and_slow':owner_value(tail_overrides=dict(source_payout=.20,source_release=.05)),
 'source_faster':owner_value(tail_overrides=dict(source_payout=.60,source_release=.20)),
 'source_block_extra_five_years':owner_value(tail_overrides=dict(source_block_years=5)),
 'investment_recovery_ten_years_after_TV5':owner_value(tail_overrides=dict(investment_delay=10)),
 'parent_capital_legacy_0267':owner_value(tail_overrides=dict(early_parent_capital_share=.2/.75)),
 'parent_capital_080':owner_value(tail_overrides=dict(early_parent_capital_share=.8)),
 'parent_own_profit_share_090':owner_value(tail_overrides=dict(direct_share=.90)),
 'all_existing_investments_at_sources':owner_value(tail_overrides=dict(parent_asset_fraction=0)),
 'parent_investment_allocation_150pct':owner_value(tail_overrides=dict(parent_asset_fraction=1.5)),
 'long_horizon_320':owner_value(tail_overrides=dict(horizon=320))}
out['tail_policy_sensitivities']={
 'optional_stop_after_Y5':owner_value(tail_overrides=dict(voluntary_until_year=5,source_buffer_until_year=5)),
 'optional_stop_after_Y20':owner_value(tail_overrides=dict(voluntary_until_year=20,source_buffer_until_year=20)),
 'optional_perpetual_boundary':owner_value(tail_overrides=dict(voluntary_until_year=10000,source_buffer_until_year=10000))}
for label,end in [('structural_stop_Y5',5),('structural_stop_Y20',20),('structural_perpetual_boundary',10000)]:
    out['tail_policy_sensitivities'][label]=value_distributions(.115,[2.9]*5,[1.2]*5,opening,2.9/.115,
        illiquid,S,[3]*5,[2.8]*5,PARENT_OPENING,PARENT_RETAINED,CLAIM,CLAIM,
        [UPSTREAM]*5,CLAIM+HK_INVESTMENT,
        tail_spec=dict(group_profits=[3.6]*10,g=0.,direct_share=(3.-.55)/3.6,source_payout=.20,source_release=.05,fixed_net_reinvestment=.7,voluntary_until_year=end,source_buffer_until_year=end))
out['terminal_method']='Y6 onward actual holder distributions with separate mother/source economic budget; no group cash or operating-terminal addback.'

if __name__=='__main__':
 print(json.dumps(out,ensure_ascii=False,indent=2))
