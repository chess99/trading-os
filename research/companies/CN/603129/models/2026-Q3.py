"""CFMOTO, CNY billion unless shares (billion) and per share CNY.
Independent operating budget; no price input. Run writes 2026-Q3-output.json.
"""
import json, math, copy
from pathlib import Path
ROOT=Path(__file__).resolve().parent
S0=.153482763
BOND=2.178763
CONVERSION=241.70
OLD_OPTIONS=.0023573
NEW_OPTIONS=.004151875 # approved total incl 20% reserved; forecast not actual grant
RESTRICTED=.0006
CASH0=14.18865953524-.34007697939 # cash equivalents less NCI ring-fence
PARENT_CASH0=7.65825519985 # H1 parent cash 8.15825519985 less 0.5 Q3 project/settlement buffer; no guessed Q3 addition
BASE_REV=[9.4,5.8,8.2,2.5,1.7]
GROWTH=[[.12,.10,.09,.07,.05],[.15,.12,.10,.08,.06],[.14,.12,.10,.08,.06],[.20,.18,.15,.10,.08],[.12,.10,.09,.07,.05]]

def present_value(flows, terminal, r):
    return sum(x/(1+r)**(i+1) for i,x in enumerate(flows))+terminal/(1+r)**len(flows)

def continuation(profit, r, growth, roic, stable_g=.03):
    flows=[]; records=[]
    for g in growth:
        old=profit; profit*=1+g; investment=(profit-old)/roic
        flows.append(profit-investment);records.append(dict(profit=profit,investment=investment,fcf=profit-investment))
    final_profit=profit*(1+stable_g)
    final_fcf=final_profit-(final_profit-profit)/roic
    terminal=final_fcf/(r-stable_g)
    return present_value(flows,terminal,r),records,terminal

def legally_available(opening_retained, profit, reserve, paidcapital):
    # Past losses are never erased; positive profit first covers cumulative deficit.
    surplus_after_loss=opening_retained+profit
    reserve_add=min(max(0.,.5*paidcapital-reserve),.1*max(0.,min(profit,surplus_after_loss)))
    closing=surplus_after_loss-reserve_add
    return closing,reserve+reserve_add

def run(kind='base', margin_delta=0, parent_delay=0, capital_extra=0, convert=True, hand_case=False):
    rev=BASE_REV[:]; prevtotal=sum(rev); nwc=-5.9
    cash=CASH0; pc=PARENT_CASH0-parent_delay
    # Parent delay parks receivables/settlements in other consolidated entities, not a group loss.
    shares=S0; retained=4.15847860839; reserve=.083022672
    zloss=-.50; zreserve=0; debt=0 if convert else BOND
    cfp_legal=0.;other_legal=0.
    rows=[]; failed=False
    if hand_case:
        cash=10.;pc=6.;shares=.1;retained=2.;reserve=.05;debt=0.;nwc=0.
    opcap=4.0+nwc+8.0
    for t in range(1 if hand_case else 5):
        oldtotal=prevtotal
        for i in range(5):rev[i]*=1+GROWTH[i][t]
        # Scenario shocks apply to post-baseline segment revenue; annual path computed independently.
        observed=rev[:]; margins=[.09,.12,.08,[-.04,-.01,.01,.025,.03][t],.12]
        if kind=='cyclical':
            factors=[.82,.9,.98,1,1]; observed[0]*=factors[t];observed[1]*=factors[t]
            margins[0]-=[.025,.015,.005,0,0][t]; margins[1]-=[.015,.008,.003,0,0][t]
        elif kind=='structural':
            # From year 1 permanent US access loss, replacement designs and price concessions.
            observed[0]*=.50; observed[1]*=.88; observed[2]*=.92
            margins=[.015,.085,.065,-.08,.09]
        elif kind=='upside':
            observed=[v*(1+.025*(t+1)) for v in observed]
            margins=[.105,.13,.09,[0,.02,.04,.05,.05][t],.13]
        total=sum(observed)
        margins=[m+margin_delta for m in margins]
        op=sum(v*m for v,m in zip(observed,margins)) # after tax/NCI, before noncash award expense; leases are cash expenses
        zprofit=observed[3]*margins[3]
        sbc=[.15,.08,.04,.02,.02][t]
        profit=op-sbc
        depreciation=[.30,.38,.46,.53,.60][t] # nonlease only, H1 0.127bn anchor
        capex=[1.8,1.7,1.5,1.3,1.2][t]+(capital_extra if t==0 else 0)
        if kind=='cyclical':capex*=.95
        if kind=='structural':capex=[1.8,1.5,1.2,1.0,1.0][t]
        if kind=='upside':capex*=1.2
        # Supplier-credit normalization from -5.9bn to -15% sales, not all liabilities deducted again.
        ratio=[-.19,-.17,-.15,-.15,-.15][t]
        if kind=='cyclical':ratio=[-.14,-.14,-.15,-.15,-.15][t]
        if kind=='structural':ratio=-.10
        nextnwc=total*ratio; delta_nwc=nextnwc-nwc
        floor=8.*total/27.6
        parentfloor=4.*total/27.6
        if kind=='structural':floor=max(6.,floor)
        # New funds and fully diluted shares are both recorded, never a free denominator change.
        additions=0.;proceeds=0.
        if t==0:
            additions+=OLD_OPTIONS+RESTRICTED
            proceeds+=OLD_OPTIONS*97.95+RESTRICTED*145.91
            if convert:additions+=BOND/CONVERSION
        if 1<=t<=3 and kind!='structural':
            q=NEW_OPTIONS*[.3,.3,.4][t-1]
            # Future dividends adjust exercise strike; budget reduces strike by cumulated per-share dividends.
            strike=233.45-sum(x['distribution_per_share'] for x in rows)
            additions+=q;proceeds+=q*max(0,strike)
        shares+=additions
        interest=debt*[.001,.003,.006,.015,.018][t]
        fin=max(0,cash-8.*oldtotal/27.6)*.015
        fcf=op+depreciation-capex-delta_nwc-interest
        if hand_case:
            # Passed through same cash -> statutory earnings -> actual payout chain.
            op=1.;zprofit=0.;sbc=0.;profit=1.;depreciation=.2;capex=.3;delta_nwc=.1
            shares=.1;proceeds=0.;interest=0.;fin=0.;floor=4.;parentfloor=2.
        fcf=op+depreciation-capex-delta_nwc-interest
        before=cash+fcf+fin+proceeds
        # No subsidiary dividend is assumed. Parent cash generation reflects own operations and project funding.
        parent_fin=.015*max(0,pc-4.*oldtotal/27.6)
        if hand_case:parent_fin=0.
        parentprofit=.60*(op-zprofit)-.75*sbc-interest+parent_fin
        retained,reserve=legally_available(retained,parentprofit,reserve,shares)
        # Zhejiang Hexin is not identical to the electric business. Standalone legal-profit budget,
        # separate from consolidated electric product profit (intragroup pricing/eliminations differ).
        hexin_profit=([-.15,-.10,0,.05,.10] if kind!='structural' else [-.25]*5)[t]
        zloss,zreserve=legally_available(zloss,hexin_profit,zreserve,.01)
        # Parent operational cash conversion 55%; remaining earnings settle through receivables; yearly extra funding .2bn.
        parentfcf=.60*(op-zprofit)+.45*depreciation-.55*capex-.60*delta_nwc-.20-interest
        if kind=='structural':parentfcf-=.25 # additional intercompany cash support, not a consolidated expense
        pbefore=pc+parentfcf+proceeds+parent_fin
        target=.40*max(0,profit+fin-interest)
        distribution=max(0,min(target,retained,before-floor,pbefore-parentfloor))
        # Financing cap 0: no new external loan is budgeted; conversion isn't cash financing.
        shortfall=max(0,floor-before,parentfloor-pbefore)
        if shortfall>1e-9:failed=True
        retained-=distribution;cash=before-distribution;pc=pbefore-distribution
        cfp_margin=(-.01 if kind=='structural' else (.08-[.025,.015,.005,0,0][t] if kind=='cyclical' else .08))
        cfp_legal+=observed[0]*cfp_margin # CFP standalone net margin budget below H1 9.47%; no upstream before Y5
        other_legal+=op*.12 # profitable wholly-owned subsidiaries only; excludes loss-making Hexin
        assert cash+1e-9>=pc>=-1e-9 or shortfall>1e-9
        assert cash-pc>=-1e-9
        assert distribution<=max(0,retained+distribution)+1e-9
        assert distribution<=max(0,pbefore-parentfloor)+1e-9
        opcap+=capex-depreciation+delta_nwc+(floor-8.*oldtotal/27.6)
        assert abs(cash-(rows[-1]['cash'] if rows else (10. if hand_case else CASH0))-fcf-fin-proceeds+distribution)<1e-8
        rows.append(dict(year=t+1,revenue=total,segment_revenue=observed,cash_operating_profit=op,accounting_profit=profit,
            depreciation=depreciation,capex=capex,delta_nwc=delta_nwc,nwc=nextnwc,fcf=fcf,financial_income=fin,
            exercise_cash=proceeds,shares=shares,distribution=distribution,distribution_per_share=distribution/shares,
            cash=cash,operating_cash_floor=floor,surplus_cash=cash-floor,parent_cash=pc,parent_floor=parentfloor,
            parent_own_profit=parentprofit,parent_fcf=parentfcf,parent_financial_income=parent_fin,parent_retained=retained,parent_reserve=reserve,hexin_profit=hexin_profit,hexin_retained=zloss,
            cfp_legal=cfp_legal,other_sub_legal=other_legal,upstream_declared=0.,upstream_received=0.,financing_shortfall=shortfall,debt=debt,operating_capital=opcap))
        nwc=nextnwc;prevtotal=total
    return dict(kind=kind,feasible=not failed,rows=rows)

def value(path,r=.11,roic=.20,stable_g=.03,growth=None,multiple=None,release_delay=3):
    if not path['feasible']:return dict(feasible=False,reason='zero distributions still cannot meet cash floor within zero new financing limit')
    rows=path['rows'];last=rows[-1]
    growth=growth or [.07,.06,.05,.04,.03]
    ev,tail,tv=continuation(last['cash_operating_profit'],r,growth,roic,stable_g)
    if multiple is not None:ev=last['cash_operating_profit']*multiple
    # Restrained terminal liquidity excludes necessary cash; debt retained if unconverted (face plus 8% maturity premium).
    debt=last['debt']*1.08
    parent_release=min(max(0,last['parent_cash']-last['parent_floor']),max(0,last['parent_retained']),last['surplus_cash'])
    subcash=max(0,last['surplus_cash']-parent_release)
    # Non-parent location allocation is a forecast, not a claim of cash freely legally nettable.
    cfp_release=min(subcash*.70,max(0,last['cfp_legal']))
    other_release=min(subcash*.30,max(0,last['other_sub_legal']))
    eligible=cfp_release+other_release
    unreleasable=subcash-eligible
    # 10% cross-border/friction allowance on CFP, three-year release delay, 1.5% net deposit carry.
    cash_asset=parent_release+(cfp_release*.90+other_release)*((1.015)/(1+r))**release_delay
    terminal=(ev+cash_asset-debt+.1651183581)/last['shares']
    flows=[x['distribution_per_share'] for x in rows]
    current=present_value(flows,terminal,r)
    return dict(feasible=True,current=current,terminal=terminal,business_value=ev,terminal_pv_share=(terminal/(1+r)**5)/current,
                tail=tail,perpetuity_terminal=tv,terminal_surplus=last['surplus_cash'],terminal_cash_asset=cash_asset,
                parent_release=parent_release,cfp_release=cfp_release,other_release=other_release,unreleased_excluded=unreleasable,
                release_delay=release_delay,shares=last['shares'],r=r,roic=roic,g=stable_g)

def all_results():
    base=run();out={'inputs':dict(initial_cash=CASH0,parent_cash=PARENT_CASH0,bond=BOND,shares=S0,base_revenue=BASE_REV), 'base':base}
    out['core_low']=value(base,.115,.16,.025)
    out['core_high']=value(base,.105,.20,.03)
    out['central']=value(base)
    out['method2_low']=value(base,.115,multiple=12)
    out['method2_high']=value(base,.105,multiple=15)
    for kind in ['cyclical','structural','upside']:
        p=run(kind,convert=kind!='structural')
        v=value(p,.12 if kind=='structural' else .11,.12 if kind=='structural' else .20,.02 if kind=='structural' else .03,
                 [.02]*5 if kind=='structural' else None)
        out[kind]=dict(path=p,value=v)
    out['sensitivities']={
      'margin_minus_1pp':value(run(margin_delta=-.01)),
      'roic_12pct':value(base,roic=.12),
      'cash_release_delay_0':value(base,release_delay=0),
      'cash_release_delay_5':value(base,release_delay=5),
      'parent_delay_2bn':dict(path=run(parent_delay=2),value=value(run(parent_delay=2))),
      'extra_capex_2bn':dict(path=run(capital_extra=2),value=value(run(capital_extra=2))),
      'no_conversion':dict(path=run(convert=False),value=value(run(convert=False))),
      'financing_failure':run(parent_delay=10)}
    # Same formal valuation functions, independently hand-computable special cases.
    assert abs(present_value([10]*5,100,.1)-100)<1e-10
    ev,_,_=continuation(10,.1,[0]*5,.2,0)
    assert abs(ev-100)<1e-10
    loss,res=legally_available(-10,4,0,100);assert loss==-6 and res==0
    loss,res=legally_available(-6,10,0,100);assert abs(loss-3.6)<1e-10 and abs(res-.4)<1e-10
    assert not out['sensitivities']['financing_failure']['feasible']
    hand=run(hand_case=True)['rows'][0]
    # Opening group 10, op1 + dep.2 - capex.3 - WC.1 = .8, dividend .4 -> cash10.4.
    # Parent6 + .6 + .09 -.165 -.06 -.2 -.4 = 5.865; retained2+.6-.4=2.2.
    assert abs(hand['cash']-10.4)<1e-9 and abs(hand['parent_cash']-5.865)<1e-9
    assert abs(hand['distribution_per_share']-4)<1e-9 and abs(hand['parent_retained']-2.2)<1e-9
    out['tests']={'full_run_hand_case':hand,'formal_PV_hand_case':100,'formal_continuation_hand_case':100,'loss_carryforward':[-6,3.6], 'all_assertions_pass':True}
    return out
if __name__=='__main__':
    out=all_results();(ROOT/'2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:{i:v for i,v in x.items() if i in ['current','terminal','feasible']} for k,x in out.items() if isinstance(x,dict)},indent=2))
