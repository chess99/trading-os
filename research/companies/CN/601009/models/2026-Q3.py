#!/usr/bin/env python3
"""南京银行：bn CNY, shares bn; stdlib, no files/network inputs."""
import json, math
S=12.363567245
B0=217.884207-20-.664 # accrued 2026 perpetual distribution after Sept close
C0=199.144742-.664
R0=2098.856494
PC0=177.886377+.95*5.800495-.2035-.664
PR0=R0*(1987.457699/2074.829309)
U0=80.801804 # conservative last disclosed parent legal undistributed, no Q3 uplift
AT1=20.296702; T2=50.662722
PAT1=19.997811; PT2=48.890023

def path(roes,growth,target=.095,ptarget=.09,parent_share=.95,liquid_haircut=0,coupon=.664,book=B0,capital=C0,rwa=R0,pc=PC0,pr=PR0,legal=U0,announced=.33122*S,capital_funding=True,funding_growth=.10):
    rows=[]
    parent_book=211.181249-25+.95*5.800495-.2035-.664
    parent_assets=3095.748880*(3286.757658/3237.323805)
    parent_liabilities=parent_assets-parent_book-20
    cash_ratio=(38.456746-liquid_haircut)/3095.748880
    statutory=17.604798
    assert cash_ratio>0
    for i,(roe,g) in enumerate(zip(roes,growth),1):
        start=book; oldr=rwa; oldpr=pr
        # ROE after baseline coupon; independently higher refinancing coupon reduces ordinary income.
        profit=start*roe-(coupon-.664)
        at1=AT1*(oldr/R0 if capital_funding else 1); t2=T2*(oldr/R0 if capital_funding else 1)
        pat1=PAT1*(oldpr/PR0 if capital_funding else 1); pt2=PT2*(oldpr/PR0 if capital_funding else 1)
        incremental_coupon=.0332*max(at1-AT1,0)+.025*max(t2-T2,0)
        profit-=incremental_coupon
        pre_common=profit+coupon
        parent_profit=parent_share*pre_common-coupon
        # protect both legal entities and all capital tiers; if growth cannot be funded,
        # adjust asset growth before dividends (no assumed external ordinary injection).
        mandatory=announced if i==1 else 0
        desired_r=oldr*(1+g); ratio=oldpr/oldr
        profit_budget=profit
        asset_ratio=parent_assets/oldr
        rwa=desired_r
        for _ in range(100):
            profit=profit_budget*(oldr+rwa)/(oldr+desired_r)
            parent_profit=parent_share*(profit+coupon)-coupon
            upstream=max(profit-parent_profit-g*max(book-pc,0),0)*min(max((i-5)/5,0),1)
            parent_profit+=upstream
            fund_max=(parent_liabilities*(1+funding_growth)+parent_book+parent_profit-mandatory+20*(rwa/R0 if capital_funding else 1))/asset_ratio
            rmax=min((capital+profit-mandatory)/target,(capital+profit+at1-mandatory)/.10,(capital+profit+at1+t2-mandatory)/.125,
                     (pc+parent_profit-mandatory)/ptarget/ratio,(pc+parent_profit+pat1-mandatory)/.095/ratio,(pc+parent_profit+pat1+pt2-mandatory)/.12/ratio,fund_max)
            nr=min(desired_r,rmax)
            if abs(nr-rwa)<1e-10: break
            rwa=nr
        rwa=nr;pr=rwa*ratio
        # parent statutory 10% reserve and general reserve proxy 1.5% incremental parent RWA
        stat_add=min(.10*max(parent_profit,0),max(.5*S-statutory,0));statutory+=stat_add
        reserve=stat_add+.015*max(pr-oldpr,0)
        legal_before=legal+parent_profit-reserve
        available=min(capital+profit-target*rwa,capital+profit+at1-.10*rwa,capital+profit+at1+t2-.125*rwa,
                      pc+parent_profit-ptarget*pr,pc+parent_profit+pat1-.095*pr,pc+parent_profit+pat1+pt2-.12*pr)
        # no arbitrary trapped capital: amortise above-operating-buffer capital over 3 years.
        desired=.32*max(profit,0)+max(available-.32*max(profit,0),0)/3
        # Parent balance-sheet funding: cash-equivalent share of assets is maintained;
        # customer/wholesale liabilities can grow only at the scenario funding ceiling.
        new_parent_assets=asset_ratio*rwa
        new_parent_at1=20*(rwa/R0 if capital_funding else 1)
        funding_room=parent_liabilities*(1+funding_growth)+parent_book+parent_profit+new_parent_at1-new_parent_assets
        div=max(0,min(max(desired,mandatory),available,legal_before,funding_room))
        if i==1 and div+1e-7<announced: raise ValueError('announced dividend infeasible')
        book+=profit-div; capital+=profit-div;pc+=parent_profit-div;legal=legal_before-div
        parent_book+=parent_profit-div
        new_liabilities=new_parent_assets-parent_book-new_parent_at1
        actual_funding_growth=new_liabilities/parent_liabilities-1
        parent_assets=new_parent_assets;parent_liabilities=new_liabilities
        liquid=cash_ratio*parent_assets
        assert actual_funding_growth<=funding_growth+1e-8
        assert abs(book-start-profit+div)<1e-9
        assert min(legal,liquid,capital-target*rwa,pc-ptarget*pr)>-1e-7
        rows.append(dict(year=i,roe=roe,profit=profit,parent_profit=parent_profit,coupon=coupon,distribution=div,dps=div/S,
                         book=book,bvps=book/S,rwa=rwa,rwa_growth=rwa/oldr-1,needed_group=target*rwa,needed_parent=ptarget*pr,
                         cet1=capital/rwa,parent_cet1=pc/pr,tier1=(capital+at1)/rwa,total=(capital+at1+t2)/rwa,
                         parent_legal_reserve=reserve,parent_undistributed=legal,parent_cash_equivalents=liquid,parent_assets=parent_assets,parent_book=parent_book,parent_liabilities=parent_liabilities,parent_funding_growth=actual_funding_growth,subsidiary_upstream=upstream,parent_cet1_amount=pc,group_cet1_amount=capital,parent_rwa=pr,profit_per_average_rwa=profit/((oldr+rwa)/2),
                         external_common_equity=0,net_noncommon_financing=((AT1+T2)*(rwa-oldr)/R0 if capital_funding else 0),incremental_financing_cost=incremental_coupon,shares=S))
    return rows

def value(rows,k,termroe,g,initial=B0,shares=S):
    n=len(rows); tv=rows[-1]['book']*(termroe-g)/(k-g)
    pv=sum(r['distribution']/(1+k)**r['year'] for r in rows)+tv/(1+k)**n
    ri=initial+sum((r['profit']-k*(initial if j==0 else rows[j-1]['book']))/(1+k)**r['year'] for j,r in enumerate(rows))+(tv-rows[-1]['book'])/(1+k)**n
    assert abs(pv-ri)<1e-8
    y5=sum(r['distribution']/(1+k)**(r['year']-5) for r in rows if r['year']>5)+tv/(1+k)**(n-5)
    return dict(current=pv/shares,terminal_y5=y5/shares,terminal_y10=tv/shares,terminal_pv_share=tv/(1+k)**n/pv,residual_income=ri/shares,k=k,terminal_roe=termroe,g=g,terminal_payout=1-g/termroe)

def tail_check(last,k,roe,g,years=100,parent_share=.95,capital_funding=True,funding_growth=.10):
    # Explicit parent/group long-run legal/funding bridge. Conservative retained
    # capital outside parent CET1 = common book minus parent regulatory capital.
    b=last['book'];c=last['group_cet1_amount'];pc=last['parent_cet1_amount'];r=last['rwa'];pr=last['parent_rwa']
    pb=last['parent_book'];pa=last['parent_assets'];pl=last['parent_liabilities'];u=last['parent_undistributed']
    rows=[];pv=0;initial=b
    for n in range(1,years+1):
        profit=roe*b;coupon=.664*r/R0
        own=parent_share*(profit+coupon)-coupon
        outside_profit=profit-own
        outside_retained=g*max(b-pc,0)
        upstream=outside_profit-outside_retained
        assert upstream>=-1e-7 and upstream<=outside_profit+1e-7
        div=(roe-g)*b
        parent_profit=own+upstream
        reserve=.015*g*pr
        u+=parent_profit-reserve-div
        pb+=parent_profit-div;pc+=parent_profit-div;c+=profit-div;b+=profit-div
        r*=1+g;pr*=1+g;pa*=1+g
        oldpl=pl;pl=pa-pb-20*(r/R0 if capital_funding else 1)
        assert min(u,c/r-.095,pc/pr-.09,(c+AT1*(r/R0 if capital_funding else 1))/r-.10,(c+(AT1+T2)*(r/R0 if capital_funding else 1))/r-.125, (pc+PAT1*(pr/PR0 if capital_funding else 1))/pr-.095,(pc+(PAT1+PT2)*(pr/PR0 if capital_funding else 1))/pr-.12)>-1e-7
        assert pl/oldpl-1<=funding_growth+1e-7
        pv+=div/(1+k)**n
        rows.append(dict(year=10+n,ordinary_profit=profit,dividend=div,subsidiary_attributable_profit=outside_profit,subsidiary_capital_retention=outside_retained,subsidiary_upstream=upstream,parent_profit=parent_profit,parent_legal_profit=u,group_cet1=c/r,parent_cet1=pc/pr,parent_funding_growth=pl/oldpl-1,common_book=b))
    pv+=b*(roe-g)/(k-g)/(1+k)**years
    closed=initial*(roe-g)/(k-g)
    assert abs(pv-closed)<1e-7
    return dict(first_year=rows[0],last_year=rows[-1],all_years=rows,terminal_value=pv/S,formula_value=closed/S)

BASE_ROE=[.12,.12,.118,.116,.114,.112,.11,.11,.11,.11]
BASE_G=[.07,.07,.065,.06,.055,.05,.045,.04,.035,.03]
def main():
    base=path(BASE_ROE,BASE_G)
    paths={'base':base,
      'cyclical':path([.09,.095,.11,.115,.114,.112,.11,.11,.11,.11],[.04,.04,.05,.06,.055,.05,.045,.04,.035,.03]),
      'structural':path([.065,.065,.07,.075,.08,.08,.08,.08,.08,.08],[.02]*10,parent_share=.90,liquid_haircut=20,coupon=.9),
      'optimistic':path([.13]*5+[.125]*5,[.08,.08,.075,.07,.065,.06,.05,.04,.035,.03]),
      'parent_stress':path(BASE_ROE,BASE_G,parent_share=.85,liquid_haircut=20,coupon=.9,funding_growth=.04),
      'no_incremental_capital_issuance':path(BASE_ROE,BASE_G,capital_funding=False),
      'slower_release':path(BASE_ROE,[.09]*5+[.07,.06,.05,.04,.03])}
    vals={n:value(p,.105,{'structural':.08,'optimistic':.12,'no_incremental_capital_issuance':.095}.get(n,.11),0 if n=='no_incremental_capital_issuance' else .03) for n,p in paths.items()}
    core={'low':value(base,.11,.105,.025),'high':value(base,.10,.115,.03)}
    # Simplified input through the exact formal value chain: 100 capital, 10 annual profit,
    # all 10 distributed, no growth, k=10%; one-share total value=100.
    simple=[dict(year=i,book=100,profit=10,distribution=10) for i in range(1,11)]
    check=value(simple,.10,.10,0,initial=100,shares=1)
    assert math.isclose(check['current'],100,abs_tol=1e-9)
    out=dict(units='CNY bn / shares bn',starting=dict(common_book=B0,group_cet1=C0,rwa=R0,parent_cet1_estimate=PC0,parent_rwa_estimate=PR0,shares=S),paths=paths,values=vals,core=core,
             sensitivity={'discount_plus_100bp':value(base,.115,.11,.03),'terminal_roe_minus_100bp':value(base,.105,.10,.03)},
             terminal_feasibility={name:tail_check(base[-1],k,roe,g) for name,k,roe,g in [('low',.11,.105,.025),('high',.10,.115,.03)]},
             scenario_terminal_feasibility={n:tail_check(rows[-1],.105,vals[n]['terminal_roe'],vals[n]['g'],parent_share={'structural':.90,'parent_stress':.85}.get(n,.95),capital_funding=n!='no_incremental_capital_issuance',funding_growth=.04 if n=='parent_stress' else .10) for n,rows in paths.items()},
             auxiliary_no_growth=dict(eps_low=22/S,eps_high=25/S,low=(22/S)/.11,high=(25/S)/.10),hand_case=check)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
