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

def operating_rows():
    out=[];debt=90.0 # modeling proxy, not reported Q3 debt; total H1 liabilities 105.31
    for i in range(10):
        revenue=YL_HYDRO_KWH[i]*YL_PRICE[i]+YL_OTHER_REVENUE[i]
        tax=YL_TAX[i]; rate=.026
        ebit=revenue-YL_CASH_COST[i]-YL_DA[i]
        upstream=YL_CT_DIVIDENDS[i]/.48
        injections=YL_CT_INJECTIONS[i]/.48
        # CF after all financing costs = total NI + D&A - working-capital needs.
        # Use full cash financing burden, rather than benefiting from capitalization.
        # Average debt convention solved algebraically; cash kept constant.
        borrowing=(YL_CAPEX[i]+upstream-injections-(ebit-rate*debt)*(1-tax)-YL_DA[i]+.2)/(1-rate*(1-tax)/2)
        interest=rate*(debt+borrowing/2)
        total_ni=(ebit-interest)*(1-tax)
        yl_common=total_ni-YL_NCI[i]
        profit=yl_common*.48+DADU_AND_OTHER_ASSOC[i]+CONTROLLED_COMMON[i]+FIN_INCOME-HOLDING_COST[i]
        cf=total_ni+YL_DA[i]-.2
        assert abs(cf+injections+borrowing-YL_CAPEX[i]-upstream)<1e-8
        debt+=borrowing
        out.append(dict(year=i+1,hydro_kwh=YL_HYDRO_KWH[i],net_price=YL_PRICE[i],other_revenue=YL_OTHER_REVENUE[i],revenue=revenue,cash_cost=YL_CASH_COST[i],da=YL_DA[i],interest=interest,tax=tax,minority_profit=YL_NCI[i],yl_common_profit=yl_common,ct_common_profit=profit,yl_cash_after_interest=cf,yl_capex=YL_CAPEX[i],yl_distribution=upstream,yl_equity_injection=injections,yl_net_borrowing=borrowing,yl_debt_end=debt))
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

def ddm(rate=.07,g=.02,incremental_roe=.10,earnings_scale=1,dividend_scale=1):
    ds=[x*dividend_scale for x in DPS]
    # Financial stakes held at book through year 10; income included in earnings.
    # Year-10 remaining stake value is separate; no mandated sale. Operating TV excludes its income.
    terminal_operating=(EARNINGS[-1]*earnings_scale-FIN_INCOME)*(1+g)*(1-g/incremental_roe)/(rate-g)/SHARES
    terminal_assets=FINANCIAL_ASSETS/SHARES
    terminal=terminal_operating+terminal_assets
    pvdiv=sum(x/(1+rate)**i for i,x in enumerate(ds,1))
    pvt=terminal/(1+rate)**10
    year5=sum(ds[i-1]/(1+rate)**(i-5) for i in range(6,11))+terminal/(1+rate)**5
    return dict(value=pvdiv+pvt,terminal_year5=year5,terminal_year10=terminal,terminal_pv_share=pvt/(pvdiv+pvt),pv_dividends=pvdiv,pv_terminal=pvt)

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


def yl_legal_bridge():
    # 2024 parent retained earnings 16.873bn; start15 as a haircut, NOT Q3 reported figure.
    retained=15.;equity=77.492584704;out=[]
    for x in operating_rows():
        profit=x['yl_common_profit']; reserve=.1*profit
        retained+=profit-reserve-x['yl_distribution']
        equity+=profit+x['yl_equity_injection']-x['yl_distribution']
        assert retained>0
        out.append(dict(year=x['year'],proxy_parent_profit=profit,statutory_reserve=reserve,distribution=x['yl_distribution'],retained_profit=retained,equity=equity))
    return out


if __name__=='__main__':
    base=ddm(); low=ddm(.075);high=ddm(.065)
    assert abs(base['value']-(sum(x/(1.07)**i for i,x in enumerate(DPS[:5],1))+base['terminal_year5']/1.07**5))<1e-10
    assert len(DPS[:5])==5 and all(x>=0 for x in DPS)
    # Gordon known case: r=.1, g=0, annual payout 1 -> 10.
    assert abs(sum(1/1.1**i for i in range(1,11))+10/1.1**10-10)<1e-10
    output=dict(operating=operating_rows(),core_low=low,core_mid=base,core_high=high,auxiliary=[earnings_asset_method(15),earnings_asset_method(17)],capital_bridge=capital_bridge(),parent_cash_budget=liquidity(),cyclical_weak=None,structural_weak=structural_path(),yl_legal_bridge=yl_legal_bridge(),optimistic=ddm(.065,.025,.11,1.10,1.10),sensitivity_rate_plus_100bp=ddm(.08))
    # Cyclical drought: two years NI -20%, dividend -20%; un-distributed loss
    # is extra debt, deducted at year 2; no automatic recovery of lost cash.
    dividend_loss=.2*sum(x/1.07**i for i,x in enumerate(DPS[:2],1))
    extra_debt=.2*sum(EARNINGS[:2])-.2*SHARES*sum(DPS[:2])
    output['cyclical_weak']=base['value']-dividend_loss-extra_debt/SHARES/1.07**2
    output['sensitivity_rate_9pct']=ddm(.09)
    output['parent_stress_first_year_cash']=liquidity()[0]['closing_cash']-.8-.5-.5
    # Parallel permanent realized-price shock; operating interest adjusts with borrowing.
    old_price=YL_PRICE[:]
    YL_PRICE[:]=[p-.01 for p in old_price]
    shocked=[r['ct_common_profit'] for r in operating_rows()]
    original=EARNINGS[:]
    EARNINGS[:]=shocked
    output['price_minus_001_terminal_only_value']=ddm()['value']
    output['price_minus_001_profit']=shocked
    EARNINGS[:]=original
    YL_PRICE[:]=old_price
    print(json.dumps(output,ensure_ascii=False,indent=2))
