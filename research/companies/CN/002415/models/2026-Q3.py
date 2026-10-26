#!/usr/bin/env python3
"""Hikvision 2026-Q3; amounts CNY bn, shares bn. No market-price input."""
import json, math
from pathlib import Path
S=9.16487155
CASH=36.60138445169-4.0 # unrestricted cash equivalents, less estimated minority-owned cash
DEBT=3.11165646664+1.09053677814+.86492007394+.31397661151
PARENT_CASH=26.60445168235-5.0406793525
LEGAL=45.89431922178-5.0406793525
NAV=(1.56698632401+.67280655052)*.9

def project(case='base', margin_delta=0.0, parent_payment_shock=0.0):
    main,innov=70.,33.
    cash,pcash,legal,debt=CASH,PARENT_CASH,LEGAL,DEBT
    sublegal=8.0 # conservative budget, not claim of Q3 disclosed reserve
    receivable=.1322042888
    settlement_balance=20.33773929925
    capital=84.27481359135-(CASH-DEBT-10.)
    rows=[]
    for t in range(1,11):
        gm=.04 if t<=5 else .03
        gi=.12 if t<=5 else [.08,.07,.06,.05,.04][t-6]
        mm,im=.175+margin_delta,.14+margin_delta
        release=1.5 if t<=2 else 0.
        working_shock,loss,extra_payment=0.,0.,0.
        extra_payment+=parent_payment_shock if t==1 else 0.
        upstream=.40
        if case=='cyclical':
            gm=[-.03,.02,.08][t-1] if t<=3 else gm
            gi=[.02,.05,.18][t-1] if t<=3 else gi
            if t<=2: mm-=.025; im-=.02
            release=1.5 if t in (3,4) else 0.
            working_shock=3. if t==1 else (-3. if t==3 else 0.)
            extra_payment=3. if t==1 else (-1.5 if t in (2,3) else 0.)
            if t<=2: upstream=.2
        if case=='structural':
            gm=-.03; gi=.03; mm=.125+margin_delta; im=.09+margin_delta
            release=0.; loss=3. if t==1 else 0.
            working_shock=3. if t==1 else 0.
            extra_payment=4. if t==1 else 0.; upstream=.2
        if case=='upside':
            gm=.06 if t<=5 else .035; gi=.18 if t<=5 else .08
            mm+=.005; im+=.01
        oldrev=main+innov
        main*=1+gm; innov*=1+gi; rev=main+innov
        profit=main*mm+innov*im-loss
        net_capex=[2.2,1.6,1.0][t-1] if t<=3 else .007*rev
        investment=.50*(rev-oldrev)+net_capex+working_shock-release
        # The impairment is noncash; subtract loss in profit, add back in FCF.
        operating_fcf=profit-investment+loss
        capital+=investment-loss+10.*(rev-oldrev)/103.
        interest=debt*.03
        cash_floor=10.*rev/103.
        parent_floor=.6*cash_floor
        finance_income=max(cash-10.*oldrev/103.,0)*.015
        fcf=operating_fcf-interest+finance_income
        netprofit=profit-interest+finance_income
        repay=min(debt,2.)
        subprofit=.25*profit
        ownprofit=.75*profit-interest+finance_income
        settlement=min(settlement_balance,1.) if t<=3 and case not in ('structural','cyclical') else 0.
        settlement_balance-=settlement
        subcash=cash-pcash
        ownflow=.70*operating_fcf-interest+finance_income+settlement-extra_payment
        subflow=.30*operating_fcf-settlement+extra_payment
        declared=max(0.,min(upstream*subprofit,sublegal+subprofit,max(0.,subcash+subflow-4.)))
        upstream_cash=.90*declared+receivable
        receivable=.10*declared
        sublegal+=subprofit-declared
        legal+=ownprofit+declared
        cash_before=cash+fcf-repay
        parent_before=pcash+ownflow+upstream_cash-repay
        # No assumed new borrowing for dividends. Funding follows cash constraints.
        new_debt=max(0.,cash_floor-cash_before,parent_floor-parent_before)
        if new_debt>5.: raise ValueError('operating funding exceeds authorized scenario capacity')
        cash_before+=new_debt; parent_before+=new_debt
        desired=.65*max(netprofit,0.)
        div=max(0.,min(desired,cash_before-cash_floor,parent_before-parent_floor,legal))
        cash_end=cash_before-div; parent_end=parent_before-div
        debt_end=debt-repay+new_debt
        legal-=div
        assert cash_end>=cash_floor-1e-8 and parent_end>=parent_floor-1e-8 and legal>=-1e-8
        assert abs(cash_end-(cash+fcf-repay+new_debt-div))<1e-8
        assert abs((cash_end-parent_end)-(subcash+subflow-upstream_cash))<1e-8
        rows.append(dict(year=2026+t,main_revenue=main,innovation_revenue=innov,revenue=rev,operating_profit_common=profit,netprofit_common=netprofit,investment=investment,net_capex=net_capex,operating_fcf=operating_fcf,fcf=fcf,interest=interest,finance_income=finance_income,dividend=div,dps=div/S,desired_dividend=desired,group_cash=cash_end,parent_cash=parent_end,parent_legal=legal,sub_legal=sublegal,sub_declared=declared,sub_cash_received=upstream_cash,sub_dividend_receivable=receivable,settlement=settlement,intercompany_extra_payment=extra_payment,internal_trade_receivable=settlement_balance,debt=debt_end,borrowed=new_debt,operating_capital=capital,cash_floor=cash_floor,nonoperating_nav=NAV))
        cash,pcash,debt=cash_end,parent_end,debt_end
    return rows

def value(rows,r=.095,g=.02,terminal_roic=.15,shares=S):
    last=rows[-1]
    terminal_op=last['operating_profit_common']*(1+g)*(1-g/terminal_roic)/(r-g)
    terminal_cash=last['group_cash']-last['debt']-last.get('cash_floor',10.)+last.get('nonoperating_nav',0.)
    terminal=terminal_op+terminal_cash
    pvdiv=sum(row['dividend']/(1+r)**(i+1) for i,row in enumerate(rows))
    pvt=terminal/(1+r)**len(rows)
    # t=5 valuation independently rolls forward dividends 6..10 and year10 remainder.
    year5=sum(row['dividend']/(1+r)**(i-4) for i,row in enumerate(rows) if i>=5)+terminal/(1+r)**5
    return dict(value_per_share=(pvdiv+pvt)/shares,year5_per_share=year5/shares,terminal_operating=terminal_op,terminal_financial=terminal_cash,terminal_pv_fraction=pvt/(pvdiv+pvt))

def hand_tests():
    # Exact input through the production value() chain: 10 annual dividends of 10,
    # perpetual profit=10, growth=0, r=10%, cash floor=10, debt=0 => 100.
    simple=[dict(dividend=10.,operating_profit_common=10.,group_cash=10.,debt=0.) for _ in range(10)]
    got=value(simple,.10,0.,.15,1.)
    assert abs(got['value_per_share']-100)<1e-10
    assert abs(got['year5_per_share']-100)<1e-10
    simple[-1]['group_cash']=30.
    got2=value(simple,.10,0.,.15,1.)
    assert abs(got2['value_per_share']-(100+20/1.1**10))<1e-10
    stress=project(parent_payment_shock=20.)
    assert stress[0]['dividend'] < stress[0]['desired_dividend']
    assert stress[0]['parent_cash'] >= .6*stress[0]['cash_floor']-1e-8
    return {'perpetuity_100':got,'extra_cash20':got2,'parent_payment_shock_20_first_dividend':stress[0]['dividend'],'parent_payment_shock_20_desired_dividend':stress[0]['desired_dividend'],'passed':True}

def run():
    cases={}
    for name in ['base','cyclical','structural','upside']:
        rows=project(name)
        g=.0 if name=='structural' else .02
        cases[name]={'rows':rows,'low':value(rows,.10,g),'high':value(rows,.09,g)}
    # Auxiliary steady-state capitalization: operating common profit only;
    # keep current financial assets separate, do not capitalize their interest.
    p=cases['base']['rows'][0]['operating_profit_common']
    netextra=CASH-DEBT-10.+NAV
    aux=[]
    for r,g,roic in [(.10,.025,.15),(.09,.03,.18)]:
        multiple=(1-g/roic)/(r-g)
        aux.append((p*multiple/(1+r)+netextra)/S)
    sensitivity={str(d):value(project(margin_delta=d),.095)['value_per_share'] for d in [-.01,0.,.01]}
    return {'units':'CNY billion except per-share','shares_billion':S,'opening_cash_common_estimate':CASH,'opening_debt_including_leases':DEBT,'opening_parent_cash_floor_estimate':PARENT_CASH,'opening_parent_legal_floor':LEGAL,'cash_floor':10.,'cases':cases,'auxiliary_normalized_earnings_range':aux,'margin_sensitivity':sensitivity,'hand_tests':hand_tests()}
if __name__=='__main__':
    out=run(); path=Path(__file__).with_name('2026-Q3-output.json'); path.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps({k:v for k,v in out.items() if k!='cases'},ensure_ascii=False,indent=2)); print({n:(x['low']['value_per_share'],x['high']['value_per_share']) for n,x in out['cases'].items()})
