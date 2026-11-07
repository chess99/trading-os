"""600941: CNY billions; years are twelve months after 2026-10-21.
Economic upstream budgets are NOT statutory entity reserve ledgers.
All state is retained. Standard library only; print deterministic complete JSON.
"""
import json, math
ISSUED=21.695890446
OPTIONS=.420221324
N=ISSUED+OPTIONS
EXERCISE=(68013597*55+352207727*51.6)*.8686/1e9
F0=196.293+132.237+248.473+6.934+19.043+29.5+26.966+9.014-(85.542-(73.910-55.797))-9.240-100-4.476+EXERCISE

def legal_step(jurisdiction, registered, paid, statutory, voluntary, retained, profit,
               cash, old_receivable, old_collection, new_declared, new_collection,
               desired, capital_return=0, returned_cost=0, exit_cost=0,
               ownership=1., shares=1., cancelled=0., registration_increase=0.,
               continue_reserve=False, capital_reduction=0.):
    """Actual payment kernel. Inputs are one real entity or a labelled test fixture.
    Profit excludes new_declared. Capital proceeds do not create dividend profit.
    HK net-asset protection represented by retained excluding nondistributable reserves.
    No assumed financing; negative cash is explicit failure, not plugged.
    """
    registered+=registration_increase-capital_reduction
    paid-=capital_reduction
    realized_gain=capital_return-returned_cost-exit_cost
    income=profit+new_declared+realized_gain
    after_loss=retained+income
    eligible=max(0, after_loss)-max(0,retained)
    appropriation=0.
    if jurisdiction=='PRC':
        appropriation=.1*max(0,eligible) if (statutory<registered*.5 or continue_reserve) else 0.
        if not continue_reserve: appropriation=min(appropriation,max(0,registered*.5-statutory))
    statutory+=appropriation
    distributable=max(0,after_loss-appropriation)
    realized_gain=capital_return-returned_cost-exit_cost
    # A capital-return fixture is a separately approved exit; not dividend income.
    available=cash+old_collection+new_collection+capital_return-exit_cost
    div=min(max(0,desired),distributable,max(0,available-(capital_return-exit_cost)))
    capital_paid=max(0,capital_return-exit_cost)
    cash_end=available-div-capital_paid
    return dict(registered=registered,paid=paid,statutory=statutory,voluntary=voluntary,
        retained=after_loss-appropriation-div,cash=cash_end,
        receivable=old_receivable-old_collection+new_declared-new_collection,
        dividend=div,capital_distribution=capital_paid,exit_gain=realized_gain,
        owner_cash=(div+capital_paid)*ownership,shares=shares-cancelled,
        failed=cash_end < -1e-9,appropriation=appropriation)

def calculate(r=.085,g=.0075,roi=.10,profit=None,cf=None,dps=None,
    upstream=None,assoc_terminal=205.,f0=F0,yield_rate=.02,tail_cash=None,
    first_collection=1.,upstream_scale=1.,realization_years=10,friction=.02,
    legacy_capacity=800.,tax_extra=0.,years=40):
    profit=profit or [100.,103.,106.,108.,110.]
    cf=cf or [90.,96.,102.,106.,110.]
    dps=dps or [4.66,4.80,4.97,5.11,5.29]
    upstream=upstream or [104.,107.,111.,114.,118.]
    # Zero starting parent available cash/profit avoids pretending FY25 is Oct26.
    f=f0; pc=pr=ar=0.; rows=[]; legacy=legacy_capacity; failed=False
    release_unit=None
    for t in range(1,years+1):
        opening=f; op=profit[t-1] if t<=5 else profit[-1]*(1+g)**(t-5)
        operating_cf=cf[t-1] if t<=5 else (tail_cash if tail_cash is not None else profit[-1]*(1+g)*(1-g/roi))*(1+g)**(t-6)
        ac=[6.,6.2,6.4,6.6,6.8][t-1] if t<=5 else 0.
        # Associates are sold after year 5 at explicit equity value, not both
        # perpetual dividends and sale price. 2% execution friction, gain tax
        # included in scenario-specific net value budget rather than invented basis.
        assoc_sale=assoc_terminal if t==6 else 0.
        interest=max(0,f)*yield_rate
        if t==6: release_unit=(f+assoc_sale)/realization_years
        release=min(max(0,f+assoc_sale),release_unit or 0.,legacy) if t>5 else 0.
        legacy-=release
        # Current legal-income headroom can distribute existing liquid principal.
        current_headroom=max(0,.95*op-operating_cf) if t>5 else 0.
        release+=min(max(0,f+assoc_sale-release),current_headroom)
        cost=(release*friction)
        legal_budget=(upstream[t-1] if t<=5 else .95*op+interest+max(0,release-current_headroom))*upstream_scale
        target=dps[t-1]*N if t<=5 else max(0,operating_cf+interest+release-cost)
        # Budget is a ceiling, not fictitious compulsory intercompany receivables.
        declared=min(max(0,legal_budget*(1-tax_extra)),max(0,target-pr),
          max(0,(f+operating_cf+interest+ac+assoc_sale-cost-pc-ar)*(1-tax_extra)))
        tax=declared*tax_extra/(1-tax_extra)
        collect=declared*(first_collection if t==1 else 1.)
        old_collect=ar
        # Group funding before transfer; no internal dividend added to group CF.
        group_available=f+operating_cf+interest+ac+assoc_sale-cost-tax
        liquidity_limit=max(0,group_available)
        parent=legal_step('HK',0,0,0,0,pr,0,pc,ar,old_collect,declared,collect,min(target,liquidity_limit))
        payout=parent['dividend'];pc=parent['cash'];pr=parent['retained'];ar=parent['receivable']
        f=group_available-payout
        failed=failed or group_available < -1e-9 or parent['failed']
        assert abs(f-(opening+operating_cf+interest+ac+assoc_sale-cost-tax-payout))<1e-7
        # Parent cash is a subset, never added separately to equity.
        assert f+1e-7>=pc
        rows.append(dict(year=t,shares=N,operating_profit=op,operating_cash=operating_cf,
          necessary_reinvestment=op-operating_cf,financial_open=opening,financial_income=interest,
          associate_cash=ac,associate_net_sale=assoc_sale,realization_principal=release,
          realization_cost=cost,extra_tax=tax,legacy_profit_remittance_budget_remaining=legacy,
          parent_new_income=declared,parent_new_collection=collect,parent_old_collection=old_collect,
          parent_receivable=ar,parent_available_profit=pr,parent_cash=pc,
          desired_distribution=target,distribution=payout,dps=payout/N,
          financial_close=f,funding_failure=group_available<0))
    # All financial principal must have a realizable path, no ignored stranded tail.
    # If constrained, extend rather than delete balances. Here disclosed tested
    # paths are exhausted by year40; necessary capital remains in operations.
    if f>1e-6 or ar>1e-6 or pc>1e-6:
        raise ValueError(('unresolved surplus at tail',f,ar,pc))
    terminal_cash_next=rows[-1]['operating_cash']*(1+g)*(1-tax_extra)
    assert terminal_cash_next <= .95*rows[-1]['operating_profit']*(1+g)*upstream_scale+pr+1e-7
    perpetuity=terminal_cash_next/(r-g)
    pv=sum(x['distribution']/(1+r)**x['year'] for x in rows)+perpetuity/(1+r)**years
    tv5=sum(x['distribution']/(1+r)**(x['year']-5) for x in rows[5:])+perpetuity/(1+r)**(years-5)
    pv5=sum(x['distribution']/(1+r)**x['year'] for x in rows[:5])
    return dict(value=pv/N,terminal_per_share=tv5/N,distributions=[x['dps'] for x in rows[:5]],
      terminal_pv_fraction=(pv-pv5)/pv,perpetuity_at_last_year=perpetuity,rows=rows,
      feasible=not failed,r=r,g=g,roi=roi,initial_financial_assets=f0)

def cases():
    return {'base':{},'lower':dict(r=.09,g=.005,assoc_terminal=190.),'upper':dict(r=.08,g=.01,assoc_terminal=220.),
      'cyclical':dict(profit=[90,95,101,106,110],cf=[65,80,95,104,110],dps=[4.3,4.5,4.8,5,5.29],upstream=[94,99,107,112,118],first_collection=.8),
      'structural':dict(r=.095,g=0,roi=.08,profit=[95,90,85,82,80],cf=[80,70,65,60,60],dps=[4,3.8,3.5,3.3,3.2],upstream=[92,86,80,76,73],assoc_terminal=165,tail_cash=60.,realization_years=15,friction=.05),
      'upside':dict(r=.08,g=.015,roi=.12,profit=[110,116,122,128,135],cf=[110,116,122,128,135],dps=[4.8,5.1,5.4,5.7,6],upstream=[110,116,123,130,137],assoc_terminal=225.),
      'sensitivity_r_plus_1pp':dict(r=.095),'sensitivity_profit_minus_10pct':dict(profit=[90,92.7,95.4,97.2,99],cf=[80,85.7,91.4,95.2,99],upstream=[93.6,96.3,99.9,102.6,106.2]),
      'sensitivity_f0_minus_20':dict(f0=F0-20), 'sensitivity_delay_half_year':dict(first_collection=.5),
      'sensitivity_realization_20years':dict(realization_years=20),
      'sensitivity_extra_tax_5pct':dict(tax_extra=.05),
      'sensitivity_legacy_capacity_650':dict(legacy_capacity=650.)}

def selftests():
    def k(**kw):
        d=dict(jurisdiction='PRC',registered=20,paid=10,statutory=5,voluntary=0,retained=0,profit=10,cash=10,old_receivable=0,old_collection=0,new_declared=0,new_collection=0,desired=10)
        d.update(kw);return legal_step(**d)
    assert k()['appropriation']==1
    assert abs(k(retained=-6)['appropriation']-.4)<1e-12
    assert k(statutory=10)['appropriation']==0
    assert k(statutory=10,continue_reserve=True)['appropriation']==1
    assert k(statutory=10,registration_increase=20)['appropriation']==1
    z=k(profit=0,cash=0,old_receivable=10,old_collection=10)
    assert z['retained']==0 and z['dividend']==0 and z['cash']==10
    z=k(profit=0,cash=-2,desired=0); assert z['failed']
    z=k(registered=50,paid=50,statutory=25,profit=0,cash=0,capital_return=10,returned_cost=10,exit_cost=1,ownership=.6,shares=10,cancelled=2,capital_reduction=10)
    assert z['dividend']==0 and z['capital_distribution']==9 and abs(z['owner_cash']-5.4)<1e-12 and z['exit_gain']==-1 and z['shares']==8 and z['paid']==40 and z['registered']==40 and z['retained']==-1
    z=k(jurisdiction='HK');assert z['appropriation']==0 and z['dividend']==10
    return '9 actual-kernel hand-computable checks passed'

def output():
    out={k:calculate(**v) for k,v in cases().items()}
    # Auxiliary independent earnings capitalization, same net financial bridge.
    aux=[]
    for key,multiple in [('lower',11.5),('upper',13.5)]:
        x=out[key];r=x['r'];g=x['g']
        op=sum(row['operating_cash']/(1+r)**row['year'] for row in x['rows'])+x['perpetuity_at_last_year']/(1+r)**40
        bridge=x['value']*N-op
        aux.append((100*multiple+bridge)/N)
    return dict(schema='600941-economic-upstream-v2',units='CNY billion except per-share',shares=N,exercise_cash=EXERCISE,
        initial_financial_assets=F0,selftests=selftests(),auxiliary_value=aux,cases=out)
if __name__=='__main__':print(json.dumps(output(),ensure_ascii=False,indent=2,allow_nan=False))
