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

def project(case='base', margin_delta=0.0, parent_payment_shock=0.0, upstream_factor=1., minority_cash=4., tax_delta=0., friction=0., mother_reserve_rate=0., opening_dividend_receivable=.1322042888):
    main,innov=70.,33.
    cash,pcash,legal,debt=36.60138445169-minority_cash,PARENT_CASH,LEGAL,DEBT
    mother_reserve=4.715460312
    cumulative_borrowing=0.0 # economic funding scenario, not disclosed bank commitment
    receivable=opening_dividend_receivable
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
        profit=(main*mm+innov*im)*(1-tax_delta/.85 if t>=2 else 1)-loss
        net_capex=[2.2,1.6,1.0][t-1] if t<=3 else .007*rev
        investment=.50*(rev-oldrev)+net_capex+working_shock-release
        # The impairment is noncash; subtract loss in profit, add back in FCF.
        operating_fcf=profit-investment+loss
        capital+=investment-loss+10.*(rev-oldrev)/103.
        interest=debt*.03
        cash_floor=10.*rev/103.
        parent_floor=.6*cash_floor
        finance_income=max(cash-10.*oldrev/103.,0)*.015
        fcf=operating_fcf-interest+finance_income-friction
        netprofit=profit-interest+finance_income-friction
        repay=min(debt,2.)
        subprofit=.25*profit
        ownprofit=.75*profit-interest+finance_income-friction
        settlement=min(settlement_balance,1.) if t<=3 and case not in ('structural','cyclical') else 0.
        settlement_balance-=settlement
        subcash=cash-pcash
        ownflow=.70*operating_fcf-interest+finance_income+settlement-extra_payment-friction
        subflow=.30*operating_fcf-settlement+extra_payment
        declared=max(0.,min(upstream*upstream_factor*subprofit,max(0.,subcash+subflow-.4*cash_floor))) # economic after-reserve/solvency/tax budget; NOT a fictional legal entity
        upstream_cash=.90*declared+receivable
        receivable=.10*declared
        reserve_add=reserve_step(ownprofit+declared,0.,9.16487155,mother_reserve,mother_reserve_rate)['actual']
        mother_reserve+=reserve_add
        legal+=ownprofit+declared-reserve_add
        cash_before=cash+fcf-repay
        parent_before=pcash+ownflow+upstream_cash-repay
        # No assumed new borrowing for dividends. Funding follows cash constraints.
        new_debt=max(0.,cash_floor-cash_before,parent_floor-parent_before)
        cumulative_borrowing+=new_debt
        if cumulative_borrowing>5.: raise ValueError('cumulative economic funding exceeds scenario capacity')
        cash_before+=new_debt; parent_before+=new_debt
        desired=.65*max(netprofit,0.)
        div=max(0.,min(desired,cash_before-cash_floor,parent_before-parent_floor,legal))
        cash_end=cash_before-div; parent_end=parent_before-div
        debt_end=debt-repay+new_debt
        legal-=div
        assert cash_end>=cash_floor-1e-8 and parent_end>=parent_floor-1e-8 and legal>=-1e-8
        assert abs(cash_end-(cash+fcf-repay+new_debt-div))<1e-8
        assert abs((cash_end-parent_end)-(subcash+subflow-upstream_cash))<1e-8
        rows.append(dict(year=2026+t,main_revenue=main,innovation_revenue=innov,revenue=rev,operating_profit_common=profit,netprofit_common=netprofit,investment=investment,net_capex=net_capex,operating_fcf=operating_fcf,fcf=fcf,interest=interest,finance_income=finance_income,dividend=div,dps=div/S,desired_dividend=desired,group_cash=cash_end,parent_cash=parent_end,parent_legal=legal,source_profit_economic=subprofit,upstream_budget=upstream*upstream_factor,sub_declared=declared,sub_cash_received=upstream_cash,sub_dividend_receivable=receivable,settlement=settlement,intercompany_extra_payment=extra_payment,internal_trade_receivable=settlement_balance,debt=debt_end,borrowed=new_debt,operating_capital=capital,cash_floor=cash_floor,nonoperating_nav=NAV,friction=friction,cumulative_borrowing=cumulative_borrowing,parent_own_profit=ownprofit,mother_reserve=mother_reserve,mother_reserve_add=reserve_add,tax_delta_effective=tax_delta if t>=2 else 0.))
        cash,pcash,debt=cash_end,parent_end,debt_end
    return rows


# All below are CNY bn. Funding fee is inside reported normalized profit;
# only the distinct entrusted net-asset principal payable is deducted here.
ENTRUSTED_PRINCIPAL_COMMON=.00974956960*.48

def reserve_step(profit, losses, registered, reserve, voluntary_rate=0.):
    """Chinese-law minimum; policy can continue above 50%. Paid capital not an input."""
    after_losses=max(0.,profit-max(0.,losses))
    mandatory=.10*after_losses if reserve<.50*registered else 0.
    actual=max(mandatory,after_losses*voluntary_rate)
    return dict(after_losses=after_losses,mandatory=mandatory,actual=actual,
                distributable=after_losses-actual)

def recovery(amount, r, lag, loss=0.):
    return max(0.,amount)*(1-loss)/(1+r)**lag

def tail(rows, r, g=.02, roic=.15, maintenance_rate=.007,
         immediate=.80, lag=3, loss=.05):
    """Economic common-equity realization budgets, not entity legal balances.
    All future cohorts are included. Necessary operating capital never released.
    Positive above-DA replacement remains when g=0; growth reinvestment separate.
    """
    z=rows[-1]
    next_profit=z['operating_profit_common']*(1+g)
    expansion=next_profit*g/roic
    maintenance=z['revenue']*(1+g)*maintenance_rate
    annual_free=next_profit-expansion-maintenance-z.get('friction',0.)*(1+g)
    factor=immediate+(1-immediate)*(1-loss)/(1+r)**lag
    continuing=annual_free/(r-g)*factor
    floor=z['cash_floor']; total=max(0.,z['group_cash']-z['debt']-floor)
    # No assertion that group debt is mother debt. All residual financial stock
    # waits >=1 year. Parent allocation is capped by its OWN profit capacity.
    parent_available=max(0.,z['parent_cash']-.6*floor)
    parent_now=min(total,parent_available,z['parent_legal'])
    child=total-parent_now
    # Internal trade collection is a relocation within existing cash; never an
    # addition to group value or new legal profit, and cannot exceed child cash.
    settlement=min(child,z['internal_trade_receivable'])
    residual=child-settlement
    principal=ENTRUSTED_PRINCIPAL_COMMON
    financial_parts={
      'parent_stock':recovery(parent_now,r,1,0.),
      'internal_trade_collection':recovery(settlement,r,1,.01),
      'other_child_stock':recovery(residual,r,lag,loss),
      'nonoperating_nav':recovery(z.get('nonoperating_nav',0.),r,lag,0.),
      'entrusted_principal_payable':-principal/(1+r)**lag}
    financial=sum(financial_parts.values())
    return dict(operating=continuing,financial=financial,total=continuing+financial,
      next_profit=next_profit,growth_capital=expansion,net_replacement=maintenance,
      next_annual_free_cash=annual_free,realization_factor=factor,
      immediate_fraction=immediate,delay_years=lag,recovery_loss=loss,
      gross_financial_stock=total,parent_stock=parent_now,
      child_stock=child,trade_relocation=settlement,other_child_stock=residual,
      financial_parts=financial_parts)

def value(rows,r=.095,g=.02,terminal_roic=.15,shares=S,**kw):
    t=tail(rows,r,g,terminal_roic,**kw)
    pvdiv=sum(row['dividend']/(1+r)**(i+1) for i,row in enumerate(rows))
    pvt=t['total']/(1+r)**len(rows)
    year5=sum(row['dividend']/(1+r)**(i-4) for i,row in enumerate(rows) if i>=5)+t['total']/(1+r)**5
    return dict(value_per_share=(pvdiv+pvt)/shares,year5_per_share=year5/shares,
      pv_distributions=pvdiv,pv_terminal=pvt,terminal_operating=t['operating'],
      terminal_financial=t['financial'],terminal_pv_fraction=pvt/(pvdiv+pvt),tail=t)

def hand_tests():
    a=reserve_step(10,0,20,5); assert a['mandatory']==1 # paid=10 would wrongly stop
    assert abs(reserve_step(10,4,20,5)['mandatory']-.6)<1e-12
    assert reserve_step(10,0,20,10)['mandatory']==0
    assert reserve_step(10,0,20,10,.1)['actual']==1
    assert abs(recovery(20,.1,2,.25)-15/1.1**2)<1e-12
    # Exact same production functions: profit10 less net replacement1, g=0.
    simple=[dict(dividend=9.,operating_profit_common=10.,revenue=100.,group_cash=10.,
       debt=0.,cash_floor=10.,parent_cash=6.,parent_legal=100.,
       internal_trade_receivable=0.,nonoperating_nav=ENTRUSTED_PRINCIPAL_COMMON) for _ in range(10)]
    got=value(simple,.1,0.,.15,1.,maintenance_rate=.01,immediate=1.,lag=0,loss=0.)
    assert abs(got['value_per_share']-90)<1e-10
    assert abs(got['year5_per_share']-90)<1e-10
    # Extra child cash20; no receivable, realized after2y with25% cost.
    simple[-1]['group_cash']=30.
    extra=value(simple,.1,0.,.15,1.,maintenance_rate=.01,immediate=1.,lag=2,loss=.25)
    assert abs(extra['value_per_share']-(90+15/1.1**12))<1e-10
    shock=project(parent_payment_shock=20.)
    assert shock[0]['dividend']<shock[0]['desired_dividend']
    normal=project(); extra_ar=project(opening_dividend_receivable=1.1322042888)
    assert abs(extra_ar[0]['parent_cash']-normal[0]['parent_cash']-1.)<1e-10
    assert extra_ar[0]['group_cash']==normal[0]['group_cash']
    assert extra_ar[0]['parent_legal']==normal[0]['parent_legal']
    assert project(mother_reserve_rate=.1)[0]['mother_reserve_add']>0
    try:
        project(parent_payment_shock=100.)
    except ValueError:
        funding_limit_rejects=True
    else:
        raise AssertionError('unfunded mother shortfall accepted')
    # Every future annual vintage receives same finite-delay treatment.
    rows=project(); z=tail(rows,.095); vals={}
    for n in (100,300,600,1200):
        vals[str(n)]=sum(z['next_annual_free_cash']*1.02**(j-1)/1.095**j*z['realization_factor'] for j in range(1,n+1))
    assert abs(vals['1200']-z['operating'])<1e-9
    return dict(reserve_cases_passed=True,production_perpetuity_net_maintenance=got,
      production_extra_child_cash=extra,parent_payment20_first_dividend=shock[0]['dividend'],
      old_receivable_not_new_profit=True,cumulative_funding_limit_rejects=funding_limit_rejects,
      all_future_vintages_convergence=vals,passed=True)

def run():
    cases={}
    for name in ['base','cyclical','structural','upside']:
        rows=project(name);g=0. if name=='structural' else .02
        kw=dict(immediate=.6,lag=5,loss=.10) if name=='structural' else {}
        cases[name]={'rows':rows,'low':value(rows,.10,g,**kw),'high':value(rows,.09,g,**kw)}
    settings={
      'margin_minus_1pp':({'margin_delta':-.01},{}),
      'margin_plus_1pp':({'margin_delta':.01},{}),
      'no_new_upstream_10y':({'upstream_factor':0.},{'immediate':.6,'lag':5,'loss':.10}),
      'half_upstream':({'upstream_factor':.5},{'immediate':.7,'lag':5,'loss':.10}),
      'parent_payment20':({'parent_payment_shock':20.},{}),
      'minority_cash2':({'minority_cash':2.},{}),
      'minority_cash6':({'minority_cash':6.},{}),
      'tax_plus5pp_Y2':({'tax_delta':.05},{}),
      'tax_fee_friction10m':({'friction':.01},{'lag':5,'loss':.10}),
      'net_maintenance_half':({}, {'maintenance_rate':.0035}),
      'mother_voluntary_reserve10pct':({'mother_reserve_rate':.10},{}),
      'tail_delay5_loss10':({}, {'immediate':.6,'lag':5,'loss':.1})}
    sensitivities={}
    for name,(project_kw,tail_kw) in settings.items():
        rows=project(**project_kw)
        sensitivities[name]=dict(project_parameters=project_kw,tail_parameters=tail_kw,rows=rows,
           low=value(rows,.10,**tail_kw),mid=value(rows,.095,**tail_kw),high=value(rows,.09,**tail_kw))
    # Independent economic lens: immediate steady state, same finite realization
    # and net replacement. No current financial-income capitalization.
    p=cases['base']['rows'][0]['operating_profit_common'];rev=cases['base']['rows'][0]['revenue']
    current_extra=CASH-DEBT-10.
    aux=[]
    for r,g,roic in [(.10,.025,.15),(.09,.03,.18)]:
        op=(p*(1-g/roic)-.007*rev)/(r-g)*(.8+.2*.95/(1+r)**3)/(1+r)
        fin=(current_extra*.95+NAV-ENTRUSTED_PRINCIPAL_COMMON)/(1+r)**3
        aux.append((op+fin)/S)
    for c in list(cases.values())+list(sensitivities.values()):
        g=0. if c is cases['structural'] else .02
        t=c['low']['tail']; first=c['rows'][-1]['year']+1
        c['future_cash_vintages']=[dict(origin_year=first+j,free_cash=t['next_annual_free_cash']*(1+g)**j,
          immediate_cash=t['next_annual_free_cash']*(1+g)**j*t['immediate_fraction'],
          delayed_payment_year=first+j+t['delay_years'],
          delayed_cash=t['next_annual_free_cash']*(1+g)**j*(1-t['immediate_fraction'])*(1-t['recovery_loss'])) for j in range(120)]
        c['future_vintages_after_120']='Same finite-lag rule forever; exact growing-perpetuity remainder included in tail, not set to zero.'
    return dict(units='CNY billion except per-share',information_cutoff='2026-10-26T06:21:46+00:00',
      shares_billion=S,opening_cash_common_estimate=CASH,opening_debt_including_leases=DEBT,
      opening_parent_cash_estimate=PARENT_CASH,opening_parent_legal_estimate=LEGAL,
      entrusted_principal_common=ENTRUSTED_PRINCIPAL_COMMON,cases=cases,sensitivities=sensitivities,
      auxiliary_normalized_earnings_range=aux,hand_tests=hand_tests())

if __name__=='__main__':
    out=run();Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print({n:(v['low']['value_per_share'],v['high']['value_per_share']) for n,v in out['cases'].items()})
