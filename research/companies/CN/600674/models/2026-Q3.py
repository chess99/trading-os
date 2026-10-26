"""Independent operating estimates; billion CNY/kWh; not company guidance."""
YL_HYDRO_KWH=[88,89,91,94,95,97,102,106,108,112]
YL_PRICE=[.28,.279,.278,.277,.276,.275,.275,.275,.275,.275]
YL_OTHER_REVENUE=[1.4,1.7,2.1,2.4,2.8,3.1,3.2,3.3,3.8,4.2]
YL_CASH_COST=[5.1,5.2,5.3,5.4,5.5,5.6,5.8,6,6.2,6.4]
YL_DA=[6.3,6.35,6.4,6.5,6.6,6.8,7.1,7.4,7.7,8.1]
YL_INTEREST=[2.6,2.7,2.8,2.9,2.8,2.8,2.8,2.8,2.8,2.8]
YL_TAX=[.20,.20,.20,.20,.25,.25,.25,.25,.25,.25]
YL_NCI=[.04,.045,.05,.055,.06,.07,.08,.09,.1,.11]
DADU_AND_OTHER_ASSOC=[.45,.48,.51,.55,.60,.65,.7,.75,.8,.85]
CONTROLLED_COMMON=[.22,.23,.25,.28,.30,.33,.36,.38,.4,.42]
HOLDING_COST=[.40,.41,.42,.43,.44,.46,.48,.50,.52,.54]
FIN_INCOME=.06

YL_CAPEX=[15,16,16,15,14,13,12,11,10,9] # excludes interest; includes maintenance
YL_CT_DIVIDENDS=[3.8,4.0,4.2,4.5,4.8,5.2,5.8,6.5,7.0,7.5]
YL_CT_INJECTIONS=[1.5,1.4,1.2,1.0,.8,.6,.5,.4,.3,.2]

def operating_rows(price_shift=0.0, constrain_distribution=False, reserve_haircut=.10):
    out=[];debt=90.0; retained=15.0; equity=77.492584704
    # Opening debt/retained balances are estimates, not reported Q3 parent balances.
    for i in range(10):
        revenue=YL_HYDRO_KWH[i]*(YL_PRICE[i]+price_shift)+YL_OTHER_REVENUE[i]
        tax=YL_TAX[i]; rate=.026
        ebit=revenue-YL_CASH_COST[i]-YL_DA[i]
        upstream=YL_CT_DIVIDENDS[i]/.48
        injections=YL_CT_INJECTIONS[i]/.48
        # CF after all financing costs = total NI + D&A - working-capital needs.
        # Use full cash financing burden, rather than benefiting from capitalization.
        # Average debt convention solved algebraically; cash kept constant.
        def solve(distribution):
            borrowing=(YL_CAPEX[i]+distribution-injections-(ebit-rate*debt)*(1-tax)-YL_DA[i]+.2)/(1-rate*(1-tax)/2)
            interest=rate*(debt+borrowing/2)
            total_ni=(ebit-interest)*(1-tax)
            return borrowing,interest,total_ni,total_ni-YL_NCI[i]
        borrowing,interest,total_ni,yl_common=solve(upstream)
        requested=upstream
        # Research budget cap, NOT a finding about legally distributable parent profits.
        if constrain_distribution and retained+(1-reserve_haircut)*yl_common-upstream < 0:
            lo,hi=0.,upstream
            assert retained+(1-reserve_haircut)*solve(0)[3]>=0
            for _ in range(80):
                mid=(lo+hi)/2
                if retained+(1-reserve_haircut)*solve(mid)[3]-mid>=0: lo=mid
                else: hi=mid
            upstream=lo
            borrowing,interest,total_ni,yl_common=solve(upstream)
        retained+=(1-reserve_haircut)*yl_common-upstream
        equity+=yl_common+injections-upstream
        profit=yl_common*.48+DADU_AND_OTHER_ASSOC[i]+CONTROLLED_COMMON[i]+FIN_INCOME-HOLDING_COST[i]
        cf=total_ni+YL_DA[i]-.2
        assert abs(cf+injections+borrowing-YL_CAPEX[i]-upstream)<1e-8
        debt+=borrowing
        out.append(dict(year=i+1,hydro_kwh=YL_HYDRO_KWH[i],net_price=YL_PRICE[i]+price_shift,other_revenue=YL_OTHER_REVENUE[i],revenue=revenue,cash_cost=YL_CASH_COST[i],da=YL_DA[i],interest=interest,tax=tax,minority_profit=YL_NCI[i],yl_common_profit=yl_common,ct_common_profit=profit,yl_cash_after_interest=cf,yl_capex=YL_CAPEX[i],yl_distribution=upstream,yl_equity_injection=injections,yl_net_borrowing=borrowing,yl_debt_end=debt,yl_requested_distribution=requested,yl_retained_proxy=retained,yl_equity_end=equity,yl_reserve_haircut=reserve_haircut*yl_common))
    return out

"""CN600674 independent Q3 pilot model. Units: CNY billion unless per share.
No market price or investor IRR; all estimates are research assumptions.
"""
import json

SHARES=4.874606828
BOOK0=46.70917936221
FINANCIAL_ASSETS=2.64 # parent-only net realization estimate, after tax/fees; excludes subsidiary stakes
EARNINGS=[r["ct_common_profit"] for r in operating_rows()]
DPS=[.52,.54,.57,.60,.63,.70,.78,.86,.95,1.04]
FIN_INCOME=.06

def ddm(rate=.07,g=.02,incremental_roe=.10,earnings_scale=1,dividend_scale=1,
        *, earnings=None, distributions=None, financial_assets=None, fin_income=None,
        shares=None, terminal_equity_adjustment=None):
    """Actual valuation API. All aggregate amounts are billion CNY.
    terminal_equity_adjustment is year-10 aggregate excess parent cash.
    None uses base closing cash less 1bn operating buffer; pass 0 for pure DDM.
    """
    es=EARNINGS if earnings is None else earnings
    ds=[x*dividend_scale for x in (DPS if distributions is None else distributions)]
    assets=FINANCIAL_ASSETS if financial_assets is None else financial_assets
    income=FIN_INCOME if fin_income is None else fin_income
    n=SHARES if shares is None else shares
    assert len(es)==len(ds)==10 and rate>g and incremental_roe>0 and n>0
    assert 0<=g/incremental_roe<=1 and all(x>=0 for x in ds)
    # Financial stakes held at book through year 10; income included in earnings.
    # Year-10 remaining stake value is separate; no mandated sale. Operating TV excludes its income.
    terminal_operating=(es[-1]*earnings_scale-income)*(1+g)*(1-g/incremental_roe)/(rate-g)/n
    if terminal_equity_adjustment is None:
        if earnings is not None or distributions is not None or earnings_scale!=1 or dividend_scale!=1:
            raise ValueError('Custom earnings/dividends require an explicit terminal cash bridge')
        terminal_equity_adjustment=parent_budget(operating_rows())[-1]['closing_cash']-1.0
    terminal_assets=(assets+terminal_equity_adjustment)/n
    terminal=terminal_operating+terminal_assets
    pvdiv=sum(x/(1+rate)**i for i,x in enumerate(ds,1))
    pvt=terminal/(1+rate)**10
    year5=sum(ds[i-1]/(1+rate)**(i-5) for i in range(6,11))+terminal/(1+rate)**5
    return dict(value=pvdiv+pvt,terminal_year5=year5,terminal_year10=terminal,terminal_pv_share=pvt/(pvdiv+pvt),pv_dividends=pvdiv,pv_terminal=pvt,terminal_operating_per_share=terminal_operating,terminal_assets_per_share=terminal_assets,terminal_equity_adjustment=terminal_equity_adjustment)

def capital_bridge():
    book=BOOK0; rows=[]
    for i,(profit,div) in enumerate(zip(EARNINGS,DPS),1):
        distribution=div*SHARES
        retained=profit-distribution
        old=book; book+=retained
        rows.append(dict(year=i,profit=profit,dividend=distribution,retained=retained,book_end=book,roe=profit/old))
    assert abs(book-BOOK0-sum(EARNINGS)+SHARES*sum(DPS))<1e-10
    return rows

def earnings_asset_method(pe):
    # Normalized total common profit 5.1; remove nonoperating financial income.
    # All financing interest and NCI are already deducted, so no second debt/NCI deduction.
    return ((5.1-FIN_INCOME)*pe+FINANCIAL_ASSETS)/SHARES

def liquidity():
    # Planning budget: cash to listed parent, less debt interest/admin,
    # total new equity contributions including controlled investments, then dividends.
    # Project borrowing stays at project level, no unfinanced full consolidated capex assumed.
    cash=1.50; rows=[]
    inflow=[4.1,4.3,4.5,4.8,5.1]; costs=[.40,.41,.42,.43,.44]
    equity_capex=[1.9,1.8,1.6,1.5,1.5]; financing=[1.0,.6,.4,.1,0]
    for i in range(5):
        opening=cash; dist=DPS[i]*SHARES
        cash+=inflow[i]-costs[i]-equity_capex[i]-dist+financing[i]
        assert abs(cash-opening-inflow[i]+costs[i]+equity_capex[i]+dist-financing[i])<1e-10
        rows.append(dict(year=i+1,opening_cash=opening,upstream_cash=inflow[i],holding_costs=costs[i],new_equity_outflow=equity_capex[i],dividends=dist,net_financing=financing[i],closing_cash=cash))
    return rows

def structural_path():
    """Price/volume impairment; defer optional projects, complete committed construction.
    Dividend equals 50% of listed common profit unless liquidity forces explicit cut.
    Positive financing is an additional loan assumption, not existing commitment.
    """
    vols=[84,84,85,86,87,88,90,92,94,96]
    prices=[.26,.258,.256,.254,.252,.25,.25,.25,.25,.25]
    other=[1.3,1.4,1.5,1.6,1.7,1.8,2,2.2,2.4,2.5]
    costs=[5.2,5.3,5.4,5.5,5.6,5.7,5.8,5.9,6,6.1]
    da=[6.3,6.35,6.4,6.5,6.6,6.7,6.9,7.1,7.3,7.4]
    capex=[13,13,12,11,10,9,8,7,7,7]
    injections=[.9,.8,.6,.5,.4,.3,.2,.1,0,0]
    direct=[.3,.3,.2,.2,.1,0,0,0,0,0]
    parent_borrow=[.8,.6,.4,.2,0,0,0,0,0,0]
    debt=90;cash=1.5;reserve=15;eq=77.492584704;rows=[]
    for i in range(10):
        ebit=vols[i]*prices[i]+other[i]-costs[i]-da[i]
        rate=.03;tax=.25;payout=.60;nci=.04+.006*i
        inj=injections[i]/.48
        borrowing=(capex[i]-inj-(1-payout)*(ebit-rate*debt)*(1-tax)-payout*nci-da[i]+.2)/(1-(1-payout)*rate*(1-tax)/2)
        interest=rate*(debt+borrowing/2);ni=(ebit-interest)*(1-tax);common=ni-nci
        div=common*payout;cf=ni+da[i]-.2
        assert abs(cf+inj+borrowing-capex[i]-div)<1e-8
        debt+=borrowing;reserve+=common*.9-div;eq+=common+inj-div
        ctprofit=common*.48+.25-(.42+.01*i)
        upstream=div*.48+.25
        holding=.42+.01*i; equity=injections[i]+direct[i]
        prediv=cash+upstream-holding-equity+parent_borrow[i]
        distribution=min(ctprofit*.5,max(0,prediv-1.0))
        cash=prediv-distribution
        assert cash>=1-1e-9 and reserve>0
        rows.append(dict(year=i+1,hydro_kwh=vols[i],price=prices[i],yl_profit=common,yl_capex=capex[i],yl_interest=interest,yl_net_borrowing=borrowing,yl_debt_end=debt,yl_dividend=div,yl_reserve=reserve,yl_equity=eq,ct_profit=ctprofit,parent_inflow=upstream,parent_cost=holding,parent_investment=equity,parent_net_borrowing=parent_borrow[i],dividend=distribution,dps=distribution/SHARES,parent_cash=cash))
    # Years 11 onward: no growth; maintenance=DA, no fresh equity.
    # All cash not paid as 60% YL dividends repays debt. Once debt is extinguished,
    # the entire steady profit is distributed, so retained value is not lost.
    future=[];d=debt
    fixed_ebit=vols[-1]*prices[-1]+other[-1]-costs[-1]-da[-1]
    for year in range(11,61):
        ni=(fixed_ebit-.03*d)*.75-.094
        repay=min(d,.4*ni)
        ydiv=ni-repay
        d-=repay
        distribution=ydiv*.48+.25-.51
        future.append(dict(year=year,yl_debt=d,dps=distribution/SHARES))
        if d<=1e-10:break
    assert d<=1e-10
    terminal_dps=(fixed_ebit*.75-.094)*.48+.25-.51-FIN_INCOME
    tail=terminal_dps/.08/SHARES+FINANCIAL_ASSETS/SHARES
    tv=sum(z['dps']/1.08**(z['year']-10) for z in future)+tail/1.08**(future[-1]['year']-10)+(cash-1.0)/SHARES
    value=sum(x['dps']/1.08**(i+1) for i,x in enumerate(rows))+tv/1.08**10
    return dict(value=value,terminal_year10=tv,rows=rows,deleveraging_tail=future)


def yl_retained_proxy_bridge():
    # 2024 parent retained earnings 16.873bn; start15 as a haircut, NOT Q3 reported figure.
    retained=15.;equity=77.492584704;out=[]
    for x in operating_rows():
        profit=x['yl_common_profit']; reserve=.1*profit
        retained+=profit-reserve-x['yl_distribution']
        equity+=profit+x['yl_equity_injection']-x['yl_distribution']
        assert retained>0
        out.append(dict(year=x['year'],proxy_parent_profit=profit,research_reserve_haircut=reserve,distribution=x['yl_distribution'],retained_profit=retained,equity=equity))
    return out


def parent_budget(yl_rows, target_distributions=None, initial_cash=1.5, cash_floor=1.0):
    """Ten-year parent cash budget. No newly granted credit is presumed.
    Years 1-5 reproduce the published budget; years 6-10 retain 0.7bn/year
    direct-project equity budget (year-5 level), with no additional net borrowing.
    HOLDING_COST includes base financing cost; no incremental parent debt added.
    Common cash dividends are automatically capped by available cash.
    """
    target=DPS if target_distributions is None else target_distributions
    other_inflow=[.3]*10
    direct_equity=[.4,.4,.4,.5,.7]+[.7]*5
    financing=[1.,.6,.4,.1,0]+[0]*5
    cash=initial_cash; retained_proxy=18.091; rows=[]
    for i,x in enumerate(yl_rows):
        upstream=x['yl_distribution']*.48+other_inflow[i]
        investment=YL_CT_INJECTIONS[i]+direct_equity[i]
        before=cash+upstream-HOLDING_COST[i]-investment+financing[i]
        if before < cash_floor-1e-9:
            raise ValueError('Parent cannot finance investment even with zero dividend')
        distribution=min(target[i]*SHARES,max(0,before-cash_floor),max(0,retained_proxy+(upstream-HOLDING_COST[i])*.9))
        opening=cash;cash=before-distribution
        retained_proxy+=(upstream-HOLDING_COST[i])*.9-distribution
        assert abs(cash-opening-upstream+HOLDING_COST[i]+investment-financing[i]+distribution)<1e-9
        rows.append(dict(year=i+1,opening_cash=opening,upstream_cash=upstream,
            holding_costs=HOLDING_COST[i],new_equity_outflow=investment,
            net_financing=financing[i],dividends=distribution,dps=distribution/SHARES,
            requested_dps=target[i],closing_cash=cash,parent_retained_proxy=retained_proxy))
    return rows


def mild_price_path(reserve_haircut=.10, initial_cash=1.5, cash_floor=1.0):
    """Permanent 0.01 CNY/kWh shock from year 1; physical projects unchanged.
    Re-solve YL distributions, debt and interest under a retained-profit proxy cap;
    parent cannot borrow more than base and cuts dividends if liquidity binds.
    Terminal includes year-10 parent cash above its 1bn operating buffer.
    Cash earns no modeled income and is separate from financial stakes.
    """
    raw=operating_rows(-.01,False,reserve_haircut)
    constrained=operating_rows(-.01,True,reserve_haircut)
    parent=parent_budget(constrained,initial_cash=initial_cash,cash_floor=cash_floor)
    reference_parent=parent_budget(operating_rows())
    funding_delta=parent[-1]['closing_cash']-reference_parent[-1]['closing_cash']
    earnings=[x['ct_common_profit'] for x in constrained]
    distributions=[x['dps'] for x in parent]
    valuation=ddm(earnings=earnings,distributions=distributions,
                  terminal_equity_adjustment=parent[-1]['closing_cash']-cash_floor)
    assert min(x['yl_retained_proxy'] for x in constrained)>=-1e-9
    assert min(x['closing_cash'] for x in parent)>=cash_floor-1e-9
    return dict(unconstrained_operating=raw,operating=constrained,parent_cash_budget=parent,
        terminal_cash_difference_vs_base=funding_delta,terminal_parent_cash_release=parent[-1]['closing_cash']-cash_floor,valuation=valuation,
        distributions_per_share=distributions,reserve_haircut=reserve_haircut,
        metadata=dict(start_year=2027,year_1='first forward annual bucket',
          changed='YL price minus 0.01 permanently; dividend cap; borrowing; interest; CT cash; funding-adjusted terminal',
          frozen='water volume, project capex, injections, tax, financing rates, other businesses, g=2%, incremental ROE=10%, shares',
          constraint='retained-profit proxy >=0; parent cash >=1bn; no extra parent net financing',
          legal_status='research proxy only, not an audited parent distributable-profit test'))


def self_tests():
    # Exercise the production valuation function with a fully specified analytical case.
    known=ddm(.1,0,.1,earnings=[1.]*10,distributions=[1.]*10,
              financial_assets=0.,fin_income=0.,shares=1.,terminal_equity_adjustment=0.)
    assert abs(known['value']-10)<1e-10
    assert abs(known['terminal_year5']-10)<1e-10
    bridge=ddm(.1,0,.1,earnings=[1.]*10,distributions=[1.]*10,
              financial_assets=0.,fin_income=0.,shares=1.,terminal_equity_adjustment=-2.)
    assert abs(known['value']-bridge['value']-2/1.1**10)<1e-10
    base=ddm()
    assert abs(base['value']-(sum(x/(1.07)**i for i,x in enumerate(DPS[:5],1))+base['terminal_year5']/1.07**5))<1e-10
    assert len(DPS[:5])==5 and all(x>=0 for x in DPS)
    mild=mild_price_path()
    assert mild['unconstrained_operating'][-1]['yl_retained_proxy']<0
    assert mild['operating'][-1]['yl_distribution']<mild['unconstrained_operating'][-1]['yl_distribution']
    # The cap actually changes the financing and valuation path.
    assert mild['operating'][-1]['yl_debt_end']<mild['unconstrained_operating'][-1]['yl_debt_end']
    binding=parent_budget(mild['operating'],target_distributions=[10.]*10)
    assert any(x['dps']<x['requested_dps'] for x in binding)
    assert all(x['closing_cash']>=1-1e-9 for x in binding)
    for path in (parent_budget(operating_rows()),mild['parent_cash_budget']):
        assert path[-1]['parent_retained_proxy']>=path[-1]['closing_cash']-1
    for base_row,old in zip(parent_budget(operating_rows()),liquidity()):
        assert abs(base_row['closing_cash']-old['closing_cash'])<1e-10


if __name__=='__main__':
    self_tests()
    base=ddm(); low=ddm(.075);high=ddm(.065)
    output=dict(operating=operating_rows(),core_low=low,core_mid=base,core_high=high,
        auxiliary=[earnings_asset_method(15),earnings_asset_method(17)],
        capital_bridge=capital_bridge(),parent_cash_budget=parent_budget(operating_rows()),
        cyclical_weak=None,structural_weak=structural_path(),
        yl_retained_proxy_bridge=yl_retained_proxy_bridge(),optimistic=ddm(.065,.025,.11,1.10,1.10,terminal_equity_adjustment=parent_budget(operating_rows(),[x*1.1 for x in DPS])[-1]['closing_cash']-1),
        sensitivity_rate_plus_100bp=ddm(.08))
    dividend_loss=.2*sum(x/1.07**i for i,x in enumerate(DPS[:2],1))
    extra_debt=.2*sum(EARNINGS[:2])-.2*SHARES*sum(DPS[:2])
    output['cyclical_weak']=base['value']-dividend_loss-extra_debt/SHARES/1.07**2
    output['sensitivity_rate_9pct']=ddm(.09)
    output['parent_stress_first_year_cash']=liquidity()[0]['closing_cash']-.8-.5-.5
    shocked=[r['ct_common_profit'] for r in operating_rows(-.01)]
    output['price_minus_001_terminal_only_value']=ddm(earnings=shocked,terminal_equity_adjustment=parent_budget(operating_rows())[-1]['closing_cash']-1)['value']
    output['price_minus_001_profit']=shocked
    output['core_excluding_parent_excess_cash']={str(r):ddm(r,terminal_equity_adjustment=0) for r in [.075,.07,.065]}
    output['mild_price_full_path']=mild_price_path()
    output['mild_price_no_reserve_haircut']=mild_price_path(reserve_haircut=0)
    output['scenario_metadata']={
      'base': {'start_year':2027,'entities':['Yalong consolidated and parent proxy','Chuantou parent','ordinary holder'],'cash_release_year':10},
      'cyclical_weak': {'start_year':2027,'changed':'CT profits and dividends -20% for years 1-2; uncovered loss valued as extra debt at year 2','frozen':'year 3+ operations; base cash asset; loss financed through the separate debt bridge','boundary':'two-year loss diagnostic, not a rebuilt project-level borrowing path'},
      'structural_weak': {'start_year':2027,'changed':'volumes, prices, financing rate, tax, delayed capex, upstream payout, parent financing, debt repayment tail','frozen':'committed construction and maintenance; existing share count'},
      'optimistic': {'start_year':2027,'changed':'profit and distributions +10%; g=.025; incremental ROE=.11; r=.065; larger distributions reduce actual parent terminal cash','frozen':'upstream dividend budget, construction funding and share count; conditional operating upside'}}
    output['self_tests']='production ddm analytical case; cash conservation; cap and dividend-cut paths passed'
    print(json.dumps(output,ensure_ascii=False,indent=2))
