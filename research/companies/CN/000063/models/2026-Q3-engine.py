#!/usr/bin/env python3
"""CN:000063 2026-Q3; CNY billion, billions of shares. stdlib only.
Default output is always beside this script. No external files or market quote.
python 2026-Q3.py --test ; python 2026-Q3.py --output /chosen/path.json
Budget source pools are economic allocations, NOT invented subsidiary legal ledgers.
"""
import argparse, copy, json, math
from pathlib import Path
AS_OF='2026-10-26T22:00:00+00:00'
FACTS={
 'issuer':'中兴通讯股份有限公司','symbol':'CN:000063','period':'2026-Q3',
 'issued_shares':4.783534887,'treasury_shares':.028659411,
 'derivative_net':.163075,'parent_derivative_net':.142426,
 'liquid_assets':80.485667, # cash+trading+current maturity+debt investments+other financial
 'parent_liquid_assets':56.685143, # same parent rows
 'gross_finance_claims':75.651608, # all borrowings, bonds, current noncurrent liabilities, leases, factoring
 'parent_finance_claims':50.946940,
 'escrow':3.304569, # latest detailed H1 disclosure; not in liquid assets
 'associates_book':3.038139,'new_investment_commitment':.561790,
 'parent_retained':30.845779,'parent_reserve':2.391767,'registered_capital':4.783534887,
 'group_retained':44.636861,'minority_equity':.142349,
 'wc':38.705485,'previous_revenue_budget':155.,'fixed_operating':23.346420,
 'convertible_carrying_estimate':3.44,'convertible_redemption':3.584,
 'convertible_incremental_shares':.132039936,'perpetual_principal':1.5,
 'other_equity_total':1.634353,'opening_trade_credit':71.559118,'other_operating_assets':20.505800,'other_operating_claims':21.106851,
 'quarter_revenue':38.813107,'ytd_revenue':116.838466,'ytd_net':4.060242,
 'ytd_recurring':2.813682,'ytd_ocf':.714970,'ytd_capex':2.650331,
 'ytd_parent_net':3.442694,'ytd_parent_investment_income':5.056758,
 'ytd_parent_ocf':-3.231185,
}
# Each group explicitly combines the three business budgets, NOT a legal entity.
BASE={
 'tax_shield_mode':'available_basis','other_operating_mode':'constant',
 'name':'base','discount':.10,'terminal_growth':.02,'years':15,
 'carrier_start':62.,'enterprise_start':67.,'consumer_start':39.,
 'carrier_growth':[.00,.01,.02,.02,.02], 'enterprise_growth':[.18,.16,.14,.12,.10],
 'consumer_growth':[.06,.05,.04,.04,.03],
 'carrier_margin':[.38,.38,.38,.38,.38], 'enterprise_margin':[.16,.165,.17,.17,.17],
 'consumer_margin':[.185,.185,.185,.185,.185],
 'rd_start':23.5,'rd_growth':.05,'sales_rate':.055,'admin_rate':.028,'levy_rate':.007,
 'software_rebate_rate':.012,'credit_loss_rate':.002,'tax':.18,'wc_ratio':[.25,.245,.24,.235,.23],
 'da_rate':.024,'maintenance_capital_ratio':.14,
 'cash_floor_rate':.08,'deposit_yield':.03,'debt_rate':.031,
 'minority_profit_share':.005,'ordinary_payout':.35,'special_start':3,
 'parent_own_profit_rate':-.009,'parent_fcfe_weight':.38,'upstream_rate':.70,'mature_upstream_rate':.90,
 'upstream_delay_years':0,'source_reserve_buffer':.10,'upstream_tax':.02,
 'parent_min_cash_rate':.035,'credit_cap':10.,'other_finance_repayments':[.7,1.490795,2.345451],'conversion':False,
 'escrow_release_year':2,'escrow_recovery':1.,'associate_recovery':.95,'associate_tax_basis_ratio':.8,
 'funding_shock':0.,'wc_shock':0.,'exit_year':None,'exit_recovery':.65,
 'exit_employee_cost':5.,'exit_fee':.03,'exit_tax':.25,
 'parent_opening_intercompany_net_payment':0.,'terminal_fee':.002,
}

def reserve_step(retained,reserve,profit,registered):
    """PRC parent reserve after carried losses; capital is not a dividend pool."""
    after=retained+profit
    repaired=max(0.,profit-max(0.,-retained))
    addition=min(max(0.,registered*.5-reserve),repaired*.1)
    return after-addition,reserve+addition,addition

def financing_tax(positive_operating_basis,financial_income,interest,rate,mode='available_basis'):
    """Economic tax budget, not consolidated legal loss sharing.
    Interest uses only this pool's positive current operating/finance basis;
    no cash refund, negative base or unverified future loss tax asset.
    no_shield is a deliberately harsher sensitivity, not the central case.
    """
    base=max(0.,positive_operating_basis)
    tax_before=base*rate
    tax_after=(base+max(0.,financial_income))*rate if mode=='no_shield' else max(0.,base+financial_income-interest)*rate
    return tax_after-tax_before,tax_after

def operating(p):
    rows=[]; rev=[p['carrier_start'],p['enterprise_start'],p['consumer_start']]
    old_other=FACTS['other_operating_assets']-FACTS['other_operating_claims']; old_wc=FACTS['wc']; fixed=FACTS['fixed_operating']; old_sales=FACTS['previous_revenue_budget']
    for t in range(1,p['years']+1):
        if t>1:
            for j,k in enumerate(('carrier','enterprise','consumer')):
                gr=p[k+'_growth'][t-2] if t<=6 else .02+(p[k+'_growth'][-1]-.02)*max(0.,(11-t)/5)
                rev[j]*=1+gr
        margins=[p[k+'_margin'][min(t-1,4)] for k in ('carrier','enterprise','consumer')]
        if t>6: margins[1]=.16+(margins[1]-.16)*max(0.,(11-t)/5)
        sales=sum(rev); gross=sum(a*b for a,b in zip(rev,margins))
        rd=p['rd_start']*(1+p['rd_growth'])**min(t-1,5)*(1.02)**max(0,t-6)
        expense=rd+sales*(p['sales_rate']+p['admin_rate']+p['levy_rate'])
        ebit=gross-expense+sales*(p['software_rebate_rate']-p['credit_loss_rate'])
        tax=max(0.,ebit)*p['tax']; nopat=ebit-tax
        wc=sales*p['wc_ratio'][min(t-1,4)] + (p['wc_shock'] if t<=3 else 0)
        da=sales*p['da_rate']; capex=max(0.,da+(sales-old_sales)*p['maintenance_capital_ratio'])
        old_sales=sales
        delta=wc-old_wc; old_wc=wc;fixed+=capex-da
        other0=FACTS['other_operating_assets']-FACTS['other_operating_claims']
        other_scale=sales/FACTS['previous_revenue_budget'] if p['other_operating_mode']=='revenue_roll' else (max(0.,1-t/5) if p['other_operating_mode']=='settle_five_years' else 1.)
        other_net=other0*other_scale;delta_other=other_net-old_other;old_other=other_net
        rows.append(dict(year=t,carrier_revenue=rev[0],enterprise_revenue=rev[1],consumer_revenue=rev[2],revenue=sales,
          gross_profit=gross,rd=rd,ebit=ebit,tax=tax,nopat=nopat,working_capital=wc,delta_wc=delta,
          depreciation=da,capex=capex,fixed_operating=fixed,other_operating_net=other_net,delta_other_operating=delta_other,other_operating_scale=other_scale,fcff=nopat+da-capex-delta-delta_other))
    return rows

def simulate(p):
    p=copy.deepcopy(p); a=operating(p); liquid=FACTS['liquid_assets'];debt=FACTS['gross_finance_claims']
    parent=FACTS['parent_liquid_assets'];parent_debt=FACTS['parent_finance_claims']; retained=FACTS['parent_retained'];reserve=FACTS['parent_reserve']
    shares=FACTS['issued_shares']; registered=FACTS['registered_capital'] # inventory shares budgeted to return
    claim=FACTS['perpetual_principal']; escrow=FACTS['escrow']; pending=0.;sub_losses=0.;borrowed=0.; allrows=[];failed=False
    for row in a:
        t=row['year']; opening=liquid;parent_open=parent;debt_open=debt;share_open=shares
        floor=row['revenue']*p['cash_floor_rate'];pfloor=row['revenue']*p['parent_min_cash_rate']
        financial_income=liquid*(p['deposit_yield'] if t<=5 else .015)
        interest=debt*p['debt_rate']
        parent_financial_income=parent*(p['deposit_yield'] if t<=5 else .015)
        parent_interest=parent_debt*p['debt_rate']
        # Parent operating budget is loss-making: no positive current operating basis.
        # Source pool receives the existing effective operating tax budget, not parent losses.
        parent_finance_tax,parent_current_tax=financing_tax(0.,parent_financial_income,parent_interest,p['tax'],p['tax_shield_mode'])
        source_finance_tax,source_current_tax=financing_tax(max(0.,row['ebit']),financial_income-parent_financial_income,interest-parent_interest,p['tax'],p['tax_shield_mode'])
        financing_tax_delta=parent_finance_tax+source_finance_tax
        current_tax=parent_current_tax+source_current_tax
        parent_finance_aftertax=parent_financial_income-parent_interest-parent_finance_tax
        financing_aftertax=financial_income-interest-financing_tax_delta
        perpetual_coupon=claim*.025
        minority=max(0.,row['nopat']+financing_aftertax)*p['minority_profit_share']
        net=row['nopat']+financing_aftertax-minority-perpetual_coupon
        # Investment income is excluded from operating EBIT. No double counting of proceeds.
        investment=FACTS['new_investment_commitment'] if t==1 else 0.
        sale_book=FACTS['associates_book']+FACTS['new_investment_commitment'] if t==3 else 0.
        sale_proceeds=sale_book*p['associate_recovery']
        sale_profit=sale_proceeds-sale_book
        sale_tax_basis=FACTS['associates_book']*p['associate_tax_basis_ratio']+FACTS['new_investment_commitment'] if t==3 else 0.
        sale_tax=max(0.,sale_proceeds-sale_tax_basis)*.25
        release=escrow*p['escrow_recovery'] if t==p['escrow_release_year'] else 0.
        escrow_loss=escrow*(1-p['escrow_recovery']) if t==p['escrow_release_year'] else 0.
        if t==p['escrow_release_year']:escrow=0.
        net+=sale_profit-sale_tax-escrow_loss
        redeem=0.; conversion=0.; premium=0.
        if t==2:
            if p['conversion']:
                conversion=FACTS['convertible_carrying_estimate'];debt-=conversion;parent_debt-=conversion;shares+=FACTS['convertible_incremental_shares'];registered+=FACTS['convertible_incremental_shares']
            else:
                redeem=FACTS['convertible_redemption'];debt-=FACTS['convertible_carrying_estimate'];parent_debt-=FACTS['convertible_carrying_estimate']
                premium=redeem-FACTS['convertible_carrying_estimate'];net-=premium
        other_repay=p['other_finance_repayments'][t-1] if t<=3 else 0.
        debt-=other_repay
        parent_other_repay=[.7,1.490795,.678451][t-1] if t<=3 else 0.
        parent_other_repay=min(parent_other_repay,other_repay)
        parent_debt-=parent_other_repay
        perpetual_redeem=claim if t==3 else 0.
        claim-=perpetual_redeem
        # Cash at holding company is independent of consolidated profit; source budgets below.
        derivative_cash=FACTS['derivative_net'] if t==1 else 0.
        parent_derivative_cash=FACTS['parent_derivative_net'] if t==1 else 0.
        fcfe=row['fcff']+financing_aftertax-minority-perpetual_coupon-investment+sale_proceeds-sale_tax+release-redeem-perpetual_redeem-other_repay
        if t==1:fcfe+=derivative_cash-p['funding_shock']
        liquid+=fcfe
        own_profit=row['revenue']*p['parent_own_profit_rate']+parent_finance_aftertax-perpetual_coupon-premium
        if t==3:own_profit+=sale_profit-sale_tax
        own_profit-=escrow_loss
        source_profit=net-own_profit
        available_source=max(0.,source_profit-sub_losses)
        sub_losses=max(0.,sub_losses-source_profit)
        # Not a pooled statutory ledger: earnings-based capacity budget subject to actual entity approvals.
        new_upstream=available_source*(1-p['source_reserve_buffer'])*(p['upstream_rate'] if t<=5 else p['mature_upstream_rate'])
        p_external=own_profit-sale_profit+sale_tax+escrow_loss+premium+p['parent_fcfe_weight']*(row['depreciation']-row['capex']-row['delta_wc']-row['delta_other_operating'])
        parent_before_upstream=parent+parent_derivative_cash+p_external-investment+sale_proceeds-sale_tax+release-redeem-perpetual_redeem-parent_other_repay
        source_cash_capacity=max(0.,liquid-parent_before_upstream-max(0.,floor-pfloor))
        new_upstream=min(new_upstream,max(0.,source_cash_capacity-pending))
        upstream=min(pending+new_upstream,source_cash_capacity) if t>p['upstream_delay_years'] else 0.
        opening_receivable=pending;pending+=new_upstream-upstream
        withholding=upstream*p['upstream_tax']
        parent_profit=own_profit+new_upstream*(1-p['upstream_tax'])
        retained,reserve,reserve_add=reserve_step(retained,reserve,parent_profit,registered)
        parent=parent_before_upstream+upstream-withholding
        # New declaration recognized once; collections of old receivables never create profit.
        # Upstream is NOT added to group cash. Only taxes paid externally are deducted.
        liquid-=withholding
        interpay=p['parent_opening_intercompany_net_payment'] if t==1 else 0.
        parent-=interpay # other subsidiary receives this; group unchanged
        precaution=row['revenue']*.05 if p['special_start']<=t<=p['special_start']+4 else 0. # finite two-year cash timing headroom
        ordinary_target=max(0.,net)*p['ordinary_payout']
        repay=0.;parent_repay=0.;source_repay=0.
        if t>=p['special_start']:
            parent_repay=min(parent_debt,max(0.,liquid-floor-precaution-ordinary_target),max(0.,parent-pfloor-precaution-ordinary_target))
            source_repay=min(max(0.,debt-parent_debt),max(0.,liquid-parent-(floor-pfloor)))
            repay=parent_repay+source_repay
            debt-=repay;parent_debt-=parent_repay;liquid-=repay;parent-=parent_repay
        liquidity_gap=max(0.,floor-liquid,pfloor-parent)
        draw=min(liquidity_gap,max(0.,p['credit_cap']-borrowed));borrowed+=draw
        liquid+=draw;parent+=draw;debt+=draw;parent_debt+=draw
        funding_gap=max(0.,floor-liquid,pfloor-parent)
        unpaid=max(0.,-liquid,-parent)
        target=max(0.,net)*p['ordinary_payout']
        if t>=p['special_start'] and debt<1e-9:target=max(target,max(0.,liquid-floor))
        dividend=min(target,max(0.,retained),max(0.,liquid-floor),max(0.,parent-pfloor)) if funding_gap<1e-8 else 0.
        retained-=dividend; liquid-=dividend;parent-=dividend
        exit_value=None
        if p['exit_year']==t:
            trade_claims=FACTS['opening_trade_credit']*row['revenue']/FACTS['previous_revenue_budget']
            operating_book=row['working_capital']+trade_claims+row['fixed_operating']+FACTS['other_operating_assets']*row['other_operating_scale']
            recovery=operating_book*p['exit_recovery'];fee=recovery*p['exit_fee']
            tax_exit=max(0.,recovery-fee-operating_book)*p['exit_tax']
            estate=liquid+recovery-fee-tax_exit-p['exit_employee_cost']+escrow
            if t<3:estate+=(FACTS['associates_book']+FACTS['new_investment_commitment'])*p['exit_recovery']
            estate-=trade_claims+FACTS['other_operating_claims']*row['other_operating_scale']
            row.update(exit_gross_operating_assets=operating_book,exit_trade_claims=trade_claims,exit_other_operating_claims=FACTS['other_operating_claims']*row['other_operating_scale'],exit_sale_tax=tax_exit,exit_sale_fees=fee,exit_net_estate_before_finance=estate)
            obligations=debt+claim
            unpaid=max(unpaid,obligations-estate,0.)
            exit_value=max(0.,estate-obligations)*(1-p['minority_profit_share'])
        failed=failed or funding_gap>1e-8 or unpaid>1e-8
        row.update(opening_liquid=opening,opening_parent_liquid=parent_open,opening_debt=debt_open,
         parent_financial_income=parent_financial_income,parent_interest=parent_interest,parent_financing_tax=parent_finance_tax,source_financing_tax=source_finance_tax,financing_tax_delta=financing_tax_delta,parent_current_tax=parent_current_tax,source_current_tax=source_current_tax,current_tax=current_tax,
         parent_finance_aftertax=parent_finance_aftertax,financial_income=financial_income,interest=interest,financing_aftertax=financing_aftertax,
         net_common_profit=net,minority_distribution=minority,perpetual_coupon=perpetual_coupon,
         investment_cash=investment,investment_book_sold=sale_book,investment_sale=sale_proceeds,investment_profit=sale_profit,investment_tax_basis=sale_tax_basis,investment_tax=sale_tax,
         escrow_release=release,escrow_loss=escrow_loss,convertible_cash_redemption=redeem,convertible_debt_cancelled=conversion,
         other_finance_repayment=other_repay,parent_other_finance_repayment=parent_other_repay,convertible_redemption_premium=premium,perpetual_redemption=perpetual_redeem,
         derivative_settlement=derivative_cash,parent_derivative_settlement=parent_derivative_cash,fcfe_before_upstream_tax=fcfe,parent_own_profit_budget=own_profit,source_profit_budget=source_profit,
         source_loss_carryforward=sub_losses,upstream_declared=new_upstream,upstream_paid=upstream,opening_dividend_receivable=opening_receivable,closing_dividend_receivable=pending,upstream_tax=withholding,source_cash_capacity=source_cash_capacity,
         parent_profit=parent_profit,parent_reserve=reserve,parent_reserve_addition=reserve_add,parent_retained=retained,
         parent_external_cash_budget=p_external,parent_intercompany_payment=interpay,
         parent_debt_repayment=parent_repay,source_debt_repayment=source_repay,parent_closing_debt=parent_debt,precautionary_liquidity=precaution,optional_debt_repayment=repay,new_financing=draw,funding_gap=funding_gap,unpaid_claims=unpaid,
         dividend=dividend,dividend_entitled_shares=shares,opening_shares=share_open,distribution_per_share=dividend/shares,closing_liquid=liquid,parent_closing_liquid=parent,
         closing_debt=debt,perpetual_claim=claim,fully_diluted_shares=shares,registered_capital=registered,
         operating_cash_floor=floor,exit_equity=exit_value)
        row['cash_reconciliation_residual']=liquid-(opening+fcfe-withholding-repay+draw-dividend)
        allrows.append(row)
        if failed or exit_value is not None:break
    last=allrows[-1]; terminal=None;tv_operating=None;terminal_cash=0.
    if not failed:
        if p['exit_year']:
            terminal=last['exit_equity']
        else:
            g=p['terminal_growth'];r=p['discount']; sales=last['revenue']
            # Continuing operating assets and liquidity earn cash; reserve capital is NOT written off.
            reinvestment=g*(last['working_capital']+last['fixed_operating']+last['operating_cash_floor']+(last['other_operating_net'] if p['other_operating_mode']=='revenue_roll' else 0.))
            next_cash=(last['nopat']+last['operating_cash_floor']*.015*(1-p['tax']))*(1+g)-reinvestment
            tv_operating=next_cash/(r-g)
            terminal_cash=liquid-last['operating_cash_floor']
            terminal=(tv_operating+terminal_cash-debt-claim)*(1-p['minority_profit_share'])*(1-p['terminal_fee'])
            if terminal<0:failed=True;last['unpaid_claims']=max(last['unpaid_claims'],-terminal);terminal=None
    value=None;year5=None;tv_pv=None
    if not failed:
        r=p['discount'];n=len(allrows)
        tv_pv=terminal/(1+r)**n
        value=sum(x['dividend']/(1+r)**x['year'] for x in allrows)+tv_pv
        # Value of one continuing original share at year 5; post-conversion shares already enter cash entitlement.
        per_share=sum(x['distribution_per_share']/(1+r)**x['year'] for x in allrows)+tv_pv/shares
        if n>=5:year5=sum(x['distribution_per_share']/(1+r)**(x['year']-5) for x in allrows[5:])+terminal/shares/(1+r)**(n-5)
    else:per_share=None
    return dict(parameters=p,annual=allrows,feasible=not failed,pv_per_share=per_share,terminal_year5_per_share=year5,
      final_terminal_total=terminal,final_operating_value=tv_operating,final_terminal_surplus=terminal_cash,
      terminal_pv_fraction=(tv_pv/value if value and tv_pv is not None else None),unfunded_liquidity_requirement=last['funding_gap'],unpaid_claims=last['unpaid_claims'],outstanding_finance_claims=last['closing_debt']+last['perpetual_claim'])

def scenarios():
    out={}
    def add(name,**changes):
        p=copy.deepcopy(BASE);p.update(changes,name=name);out[name]=simulate(p)
    add('base')
    add('conversion',conversion=True)
    add('no_finance_tax_shield',tax_shield_mode='no_shield')
    add('other_operating_revenue_roll',other_operating_mode='revenue_roll')
    add('other_operating_settle',other_operating_mode='settle_five_years')
    add('core_low',discount=.105,enterprise_margin=[.155,.16,.165,.165,.165],wc_ratio=[.255,.25,.245,.24,.235])
    add('core_high',discount=.095,enterprise_margin=[.165,.17,.175,.175,.175],wc_ratio=[.245,.24,.235,.23,.225])
    add('cycle_weak',carrier_start=57.,enterprise_start=60.,consumer_start=36.,enterprise_growth=[.08,.20,.19,.15,.10],rd_start=23.,wc_shock=5.,upstream_delay_years=2)
    add('structural_weak',carrier_start=56.,enterprise_start=64.,consumer_start=36.,carrier_margin=[.34]*5,enterprise_margin=[.13]*5,
        carrier_growth=[-.03]*5,enterprise_growth=[.09,.08,.07,.06,.04],rd_start=22.5,rd_growth=.02,
        wc_ratio=[.28]*5,maintenance_capital_ratio=.19,terminal_growth=.01)
    add('upside',enterprise_start=74.,enterprise_growth=[.23,.20,.18,.15,.12],enterprise_margin=[.18,.185,.19,.19,.19],conversion=False)
    add('network_margin_minus_2pp',carrier_margin=[.36]*5)
    add('terminal_discount_low',discount=.105)
    add('terminal_discount_high',discount=.095)
    add('margin_minus_1pp',enterprise_margin=[x-.01 for x in BASE['enterprise_margin']])
    add('capital_light_execution',wc_ratio=[.25,.2375,.225,.2125,.20],maintenance_capital_ratio=.10)
    add('wc_plus_5pp',wc_ratio=[x+.05 for x in BASE['wc_ratio']])
    add('parent_delay',upstream_delay_years=3,parent_opening_intercompany_net_payment=8.)
    add('treasury_release_delayed',special_start=5)
    add('rate_plus_1pp',debt_rate=.041)
    add('no_new_credit',credit_cap=0.)
    add('escrow_forfeit',escrow_recovery=0.)
    add('funding_failure',funding_shock=100.,credit_cap=0.,exit_year=1,exit_recovery=.2)
    return out

def self_test():
    assert financing_tax(0.,1.,2.,.18)==(0.,0.)
    assert financing_tax(5.,1.,2.,.18)==(-.17999999999999994,.72)
    assert financing_tax(0.,2.,1.,.18)==(.18,.18)
    assert abs(financing_tax(5.,1.,2.,.18,'no_shield')[0]-.18)<1e-12
    assert reserve_step(-5.,0.,4.,10.)==(-1.,0.,0.)
    assert reserve_step(-5.,0.,10.,10.)==(4.5,.5,.5)
    p=copy.deepcopy(BASE);p.update(years=1,carrier_start=100.,enterprise_start=0.,consumer_start=0.,carrier_margin=[.20]*5,
      rd_start=0.,sales_rate=0.,admin_rate=0.,levy_rate=0.,software_rebate_rate=0.,credit_loss_rate=0.,tax=.25,
      wc_ratio=[FACTS['wc']/100]*5,da_rate=.02,maintenance_capital_ratio=0.)
    q=operating(p)[0];assert abs(q['fcff']-15.)<1e-12 # official operating function, literal tax/capital case
    saved=copy.deepcopy(FACTS)
    try:
        for key in FACTS:
            if isinstance(FACTS[key],(int,float)):FACTS[key]=0.
        FACTS.update(liquid_assets=100.,parent_liquid_assets=100.,parent_retained=100.,parent_reserve=1.,registered_capital=2.,issued_shares=2.,previous_revenue_budget=1.)
        z=copy.deepcopy(BASE);z.update(years=1,carrier_start=0.,enterprise_start=0.,consumer_start=0.,rd_start=0.,exit_year=1,exit_recovery=0.,exit_employee_cost=0.,exit_fee=0.,minority_profit_share=0.,deposit_yield=0.,other_finance_repayments=[0.,0.,0.])
        assert abs(simulate(z)['pv_per_share']-50/1.1)<1e-12
    finally:
        FACTS.clear();FACTS.update(saved)
    all_s=scenarios()
    for s in all_s.values():
        for x in s['annual']:
            assert abs(x['cash_reconciliation_residual'])<1e-9
            expected_net=x['ebit']+x['financial_income']-x['interest']-x['current_tax']-x['minority_distribution']-x['perpetual_coupon']+x['investment_profit']-x['investment_tax']-x['escrow_loss']-x['convertible_redemption_premium']
            assert abs(x['net_common_profit']-expected_net)<1e-9
            assert abs(x['parent_finance_aftertax']-(x['parent_financial_income']-x['parent_interest']-x['parent_financing_tax']))<1e-9
            assert abs(x['distribution_per_share']*x['dividend_entitled_shares']-x['dividend'])<1e-9
            assert x['dividend']>=0
            assert x['parent_reserve_addition']>=0
            assert abs(x['closing_dividend_receivable']-(x['opening_dividend_receivable']+x['upstream_declared']-x['upstream_paid']))<1e-9
            if s['feasible']:assert x['parent_closing_liquid']<=x['closing_liquid']+1e-9
            if x['dividend']>0:assert x['parent_retained']>=-1e-9
        if not s['feasible']:assert s['pv_per_share'] is None and s['final_terminal_total'] is None and s['terminal_year5_per_share'] is None
    assert not all_s['funding_failure']['feasible'] and all_s['funding_failure']['unpaid_claims']>0
    cp=copy.deepcopy(BASE);cp['conversion']=True;cr=simulate(cp)['annual'][1]
    assert cr['convertible_cash_redemption']==0 and cr['convertible_debt_cancelled']==3.44
    assert abs(cr['fully_diluted_shares']-4.915574823)<1e-12
    assert abs(cr['distribution_per_share']-cr['dividend']/4.915574823)<1e-12
    assert cr['distribution_per_share']<cr['dividend']/cr['opening_shares']
    for row in all_s['structural_weak']['annual']:
        assert row['current_tax']>=0
        if row['ebit']<0: assert row['financing_tax_delta']>=0
    for sc in all_s.values():
        for row in sc['annual']:
            assert abs(row['current_tax']-row['tax']-row['financing_tax_delta'])<1e-10
            assert abs(row['current_tax']-row['parent_current_tax']-row['source_current_tax'])<1e-10
    assert all_s['margin_minus_1pp']['pv_per_share']<all_s['base']['pv_per_share']
    return {'passed':True,'tests':['loss-before-reserve','post-loss-reserve','literal-operating-fcff','literal-full-simulation-cash-exit','all-year-cash-conservation','no-profit-dividend-breach','failure-nulls-whole-value','dominant-margin-direction','conversion-current-year-entitlement','current-tax-no-loss-refund','tax-positive-basis-interest-deduction','other-operating-net-roll']}

def build():
    ss=scenarios();b=ss['base'];lo=ss['core_low'];hi=ss['core_high']
    tl=copy.deepcopy(BASE);tl['discount']=.105;th=copy.deepcopy(BASE);th['discount']=.095
    # Auxiliary normalized profit: fifth-year operating aftertax profit, excludes treasury earnings;
    # justified 11-14x at that future state, net liquid/debt bridge, discounted to same current date.
    y=b['annual'][4]; aux=[]
    for mult in (11.,14.):
        future=(y['nopat']*mult+y['closing_liquid']-y['operating_cash_floor']-y['closing_debt']-y['perpetual_claim'])*.995
        aux.append(sum(x['distribution_per_share']/1.1**x['year'] for x in b['annual'][:5])+future/y['fully_diluted_shares']/1.1**5)
    return {'identity':{k:FACTS[k] for k in ('issuer','symbol','period')},'as_of':AS_OF,'units':'CNY billion except per-share CNY; shares billion',
      'facts':FACTS,'scenarios':ss,'summary':{'core_value_range':[round(lo['pv_per_share'],2),round(hi['pv_per_share'],2)],
      'base_distributions':[round(x['distribution_per_share'],6) for x in b['annual'][:5]],
      'year5_terminal_range':[round(simulate(tl)['terminal_year5_per_share'],6),round(simulate(th)['terminal_year5_per_share'],6)],
      'auxiliary_normalized_profit_range':aux},'tests':self_test()}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output');ap.add_argument('--test',action='store_true');args=ap.parse_args()
    if args.test:print(json.dumps(self_test(),ensure_ascii=False));raise SystemExit()
    out=build();path=Path(args.output) if args.output else Path(__file__).resolve().with_name('2026-Q3-output.json')
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(out['summary'],ensure_ascii=False));print(str(path))
