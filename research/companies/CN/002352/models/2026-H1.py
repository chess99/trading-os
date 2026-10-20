# coding: utf-8
"""SF Holding: amounts CNY 100m, shares 100m. Standard library, offline."""
import json
from pathlib import Path
S=50.94207278
DPS=[.95,1.02,1.07,1.12,1.18]
CASH=458.97530-25.793325-1.199365-2.661376
DEBT=430.16160-25.674270
RESERVE=100.0
INVEST=125.61
CALLS=4.79506
ASSOC=69.54498
FAIR=67.96803
ASSET_LOW=(ASSOC*.7+FAIR*.8)/(ASSOC+FAIR)
ASSET_HIGH=(ASSOC*.9+FAIR)/(ASSOC+FAIR)
# H1 recurring group income: profit less group after-tax nonrecurring items.
H1_RECURRING=59.70017-(8.35002-1.86652)
# Non-lease financing removed; fund revaluation already excluded with nonrecurring items.
CORE=(H1_RECURRING+(5.47040-.06502)*.77-1.00132*.77+.50875)*2

def forecast(domestic_growth=.035,core=CORE,lease0=80.,growth_cap0=14.,wc0=17.35,loss=12.68):
    rows=[]; extra=CASH-RESERVE;reserve=RESERVE
    for t in range(1,6):
        f=(1+domestic_growth)**(t-1)
        op=(core+loss)*f-loss
        da=100*f;rou=68.01764*1.04**(t-1);li=4.8676*1.04**(t-1)
        rent=lease0*1.04**(t-1);growth=growth_cap0+t-1
        wc=wc0 if t==1 else 10.47*1.045**(t-2)
        reserve_add=reserve*domestic_growth
        necessary_yield=(reserve+13.83685)*.015*.77
        ufcf=op+da+rou+li-rent-da-growth-wc-reserve_add+necessary_yield
        interest=DEBT*.027*.77
        deposit_income=extra*.02*.77
        minority_profit=6.9*1.04**(t-1)
        minority_cash=(minority_profit-15*.02*.77)*(1-.04/.12)+15*.02*.77
        fcfe=ufcf-interest+deposit_income-minority_cash
        dividend=S*DPS[t-1]
        calls=CALLS if t==1 else 0
        closing_extra=extra+fcfe-dividend-calls
        row=dict(year=t,operating_profit_after_lease_interest=op,nonlease_depreciation=da,rou_depreciation=rou,lease_interest=li,lease_cash=rent,maintenance=da,growth_capex=growth,nwc_investment=wc,operating_cash_reserve_addition=reserve_add,necessary_cash_income=necessary_yield,unlevered_after_lease_cash=ufcf,nonlease_interest_after_tax=interest,deposit_income_after_tax=deposit_income,minority_core_profit=minority_profit,minority_cash=minority_cash,common_fcfe=fcfe,dividend=dividend,dps=DPS[t-1],new_investment_calls=calls,extra_cash_open=extra,extra_cash_close=closing_extra,operating_cash_reserve_close=reserve+reserve_add)
        assert abs(closing_extra-extra-fcfe+dividend+calls)<1e-9
        assert fcfe>dividend
        rows.append(row);extra=closing_extra;reserve+=reserve_add
    return rows

def endpoint(rows,re,g,asset_factor,roic=.12,recurring_cash_shock=0,debt_weight=.2):
    rd=.027*.77;wacc=(1-debt_weight)*re+debt_weight*rd
    assert wacc>g and re>g and roic>g
    last=rows[-1]
    # Cash earnings after replacing recurring leased capacity; negative international residual fixed.
    cash_earnings=last['operating_profit_after_lease_interest']+last['rou_depreciation']+last['lease_interest']-last['lease_cash']+(last['operating_cash_reserve_close']+13.83685)*.015*.77
    grow6=(cash_earnings+12.68)*(1+g)*(1-g/roic)+recurring_cash_shock
    fixed=-12.68
    ev=grow6/(wacc-g)+fixed/wacc
    minority6=(last['minority_core_profit']-15*.02*.77)*(1+g)
    minority_eq=minority6*(1-g/.12)/(re-g)+15
    jt=3.5*(1+g)*(1-g/.12)/(re-g)
    other=INVEST*asset_factor+CALLS
    terminal=ev+last['extra_cash_close']-DEBT-minority_eq+jt+other
    pvdiv=sum(row['dividend']/(1+re)**row['year'] for row in rows)
    pvterminal=terminal/(1+re)**5
    # Enterprise DCF cross check, same economic terminal, full cash ownership bridge.
    # Current equity value: UFCF discounted + EV terminal, net financing and assets.
    ev_today=sum(row['unlevered_after_lease_cash']/(1+wacc)**row['year'] for row in rows)+ev/(1+wacc)**5
    minority_today=sum(row['minority_cash']/(1+re)**row['year'] for row in rows)+minority_eq/(1+re)**5
    aux=(ev_today+(CASH-RESERVE)-DEBT-minority_today+(jt+other)/(1+re)**5-CALLS/(1+re))/S
    assert abs((terminal-ev-last['extra_cash_close']+DEBT+minority_eq-jt-other))<1e-8
    return dict(equity_cost=re,wacc=wacc,growth=g,incremental_return=roic,nonoperating_asset_factor=asset_factor,year6_growing_cash=grow6,year6_fixed_cash=fixed,year6_total_cash=grow6+fixed,terminal_operating_ev=ev,terminal_minority_equity=minority_eq,terminal_jt_equity=jt,terminal_other_investments=other,terminal_extra_cash=last['extra_cash_close'],terminal_nonlease_debt=DEBT,terminal_equity=terminal,terminal_per_share=terminal/S,current_per_share=(pvdiv+pvterminal)/S,terminal_pv_weight=pvterminal/(pvdiv+pvterminal),enterprise_dcf_crosscheck_per_share=aux)

def main():
    rows=forecast();lo=endpoint(rows,.103,.015,ASSET_LOW);hi=endpoint(rows,.096,.02,ASSET_HIGH)
    sensitivities={'high_recurring_cash_minus10':endpoint(rows,.096,.02,ASSET_HIGH,recurring_cash_shock=-10),'low_roic_equal_wacc':endpoint(rows,.103,.015,ASSET_LOW,roic=lo['wacc']),'high_zero_growth':endpoint(rows,.096,0,ASSET_HIGH),'high_other_assets_zero':endpoint(rows,.096,.02,0.),'high_debt_weight15':endpoint(rows,.096,.02,ASSET_HIGH,debt_weight=.15),'high_debt_weight25':endpoint(rows,.096,.02,ASSET_HIGH,debt_weight=.25)}
    # Known elementary cases and share / cash conservation.
    assert abs(sum(10/1.1**t for t in range(1,6))+100/1.1**5-100)<1e-8
    assert abs(52.65308078-1.6016-.109408-S)<1e-8
    assert abs(CASH-DEBT-(458.9753-430.1616-(25.793325-25.67427)-1.199365-2.661376))<1e-9
    structural_cash=69+68.01764+4.8676-86-5
    structural_wacc=.8*.115+.2*.027*.77
    structural_value=(structural_cash/structural_wacc+(CASH-RESERVE)-DEBT-4/.115+3.5/.115+INVEST*.6)/S
    cycle_cash_loss=30*1.0154**4+20*1.0154**3
    scenarios=dict(structural=dict(operating_profit=69,rou_depreciation=68.01764,lease_interest=4.8676,lease_cash=86,maintenance_above_depreciation=5,zero_growth_cash=structural_cash,wacc=structural_wacc,minority_earnings=4,other_asset_factor=.6,current_per_share=structural_value),cyclical=dict(year1_profit_loss=30,year2_profit_loss=20,terminal_extra_cash_loss=cycle_cash_loss,low_value=lo['current_per_share']-cycle_cash_loss/S/1.103**5,high_value=hi['current_per_share']-cycle_cash_loss/S/1.096**5))
    out=dict(scenarios=scenarios,inputs=dict(shares=S,initial_available_financial_assets=CASH,initial_nonlease_debt=DEBT,operating_cash_reserve=RESERVE,initial_extra_cash=CASH-RESERVE,restricted_cash_not_added=13.83685,normalized_core_profit=CORE,non_jt_common_investment_book=INVEST,investment_calls=CALLS),annual=rows,low=lo,high=hi,sensitivities=sensitivities,self_checks='passed')
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['inputs','low','high','self_checks']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
