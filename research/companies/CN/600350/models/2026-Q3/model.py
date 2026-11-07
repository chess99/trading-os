"""600350 finite-concession design. Ordinary offline local invocation.
Money: CNY billion; shares: billion. No network, market prices, global state or imports of company code.
CLI: --inputs PATH --output PATH; --hand-cases uses the SAME run_case/build_plan/value_state chain.
"""
import argparse
import copy
import json
from pathlib import Path


def scheduled_amount(schedule, year, delay=0):
    """Only future construction instalments shift; the 2026 stub is never duplicated."""
    return sum(amount for original,amount in schedule.items()
               if year == int(original) + (delay if int(original) >= 2027 else 0))


def g220_funding(data, scenario, year):
    """Group construction cash is not the same as parent support or common ownership."""
    group_cash=data['other_capital']['g220_future_capex'].get(str(year),0.0)*scenario['capex_multiplier']
    return group_cash,group_cash*scenario['g220_parent_support_fraction']


def matched_interest_effects(data, group_delta, mother_delta, mother_operating_profit_delta):
    """Recognize only modeled current cash tax; no new deferred tax asset is booked."""
    e=data['initial_estimates'];rate=e['tax_rate']
    taxable_before=e['mother_taxable_income_proxy_2026']+mother_operating_profit_delta/(1-rate)
    taxable_after=taxable_before-mother_delta*e['mother_interest_tax_eligible_fraction']
    tax_before=max(0.0,taxable_before)*rate
    tax_after=max(0.0,taxable_after)*rate
    mother_tax_cash=tax_before-tax_after
    nonmother_delta=group_delta-mother_delta
    # No unverified cross-entity loss offset. For lower subsidiary interest, reserve extra tax conservatively.
    nonmother_tax_cash=min(0.0,nonmother_delta*rate)*e['nonmother_tax_on_interest_savings_fraction']
    base_group=e['group_debt']*e['group_interest_rate'];base_mother=e['mother_debt']*e['mother_interest_rate']
    nonmother_base=base_group-base_mother
    nonmother_common_fraction=min(1.0,max(0.0,(base_group*e['common_interest_fraction']-base_mother)/nonmother_base)) if nonmother_base>0 else 0.0
    mother_profit_change=-mother_delta+mother_tax_cash
    common_profit_change=mother_profit_change+nonmother_common_fraction*(-nonmother_delta+nonmother_tax_cash)
    return dict(group_interest_delta=group_delta,mother_interest_delta=mother_delta,
                mother_taxable_proxy_before=taxable_before,mother_current_tax_before=tax_before,mother_current_tax_after=tax_after,
                mother_cash_tax_adjustment=mother_tax_cash,group_cash_tax_adjustment=mother_tax_cash+nonmother_tax_cash,
                nonmother_cash_tax_adjustment=nonmother_tax_cash,nonmother_common_fraction=nonmother_common_fraction,
                mother_profit_change=mother_profit_change,common_profit_change=common_profit_change,
                unrecognized_mother_interest_tax_benefit=max(0.0,max(0.0,mother_delta)*rate-max(0.0,mother_tax_cash)),
                unrecognized_nonmother_interest_tax_benefit=max(0.0,nonmother_delta)*rate,new_deferred_tax_asset=0.0)


def annual_fraction(road, year):
    if year < road.get('opening_year', 2026) or year > road['end_year']:
        return 0.0
    if year == road.get('opening_year', -1):
        return road.get('opening_fraction', 1.0)
    return road.get('end_fraction', 1.0) if year == road['end_year'] else 1.0


def road_revenue(road, year, scenario, endpoint):
    fraction = annual_fraction(road, year)
    if not fraction:
        return 0.0
    n = year - 2026
    growth = road['growth'] + endpoint['road_growth_shift']
    if road.get('new_project'):
        full = road['opening_year'] + 1
        ramp = road['ramp_first_full'] if year <= full else 1.0
        return road['net_anchor'] * (1 + growth) ** max(0, year-full) * fraction * ramp * scenario['weilai_revenue_multiplier']
    recovery = scenario['jingtai_recovery'][min(max(n-1, 0), 4)] if road.get('jingtai') and year >= 2027 else 0.0
    traffic = 1.0 if year == 2026 else (scenario['traffic_multipliers'][n-1] if 1 <= n <= 5 else scenario['permanent_traffic_multiplier'])
    return road['net_anchor'] * (1+growth)**n * (1+recovery) * traffic * fraction


def build_plan(data, scenario, endpoint):
    est, obs = data['initial_estimates'], data['observed']
    roads = copy.deepcopy(data['roads'])
    net_ratio = obs['fy25_toll_revenue_net'] / obs['fy25_toll_revenue_gross']
    for r in roads:
        r['net_anchor'] = r.get('net_anchor_override', r['gross_2025'] * r['ytd_2026_wan'] / r['ytd_2025_wan'] * net_ratio)
        r['cash_cost_ratio'] = est['road_cash_cost_ratio']
        r['maintenance_ratio'] = est['road_capital_maintenance_ratio']
    new = data.get('weilai')
    new_book = obs.get('weilai_invested', 0.0) if new else 0.0
    stub_fraction = data['identity'].get('historical_stub_fraction', 0.25)
    weights = [r['net_anchor'] * sum(annual_fraction(r,year)*(stub_fraction if year==2026 else 1.0)
               for year in range(2026,r['end_year']+1)) * (endpoint['qilu_book_weight'] if r.get('qilu') else 1.0) for r in roads]
    total_weight = sum(weights)
    for r, weight in zip(roads, weights):
        r['initial_book'] = (endpoint['road_book_total']-new_book) * weight / total_weight
    if new:
        r = copy.deepcopy(new)
        r.update(new_project=True, opening_year=new['opening_year']+scenario['opening_delay'], initial_book=new_book,
                 net_anchor=new['mature_first_full_net_revenue'])
        r['end_year'] = r['opening_year'] + new['operating_years']
        r['end_fraction'] = 1.0-r['opening_fraction']
        r['growth'] = new['growth']
        roads.append(r)
    plan = {}
    for r in roads:
        revenues = {}
        for year in range(2026, r['end_year']+1):
            revenues[year] = road_revenue(r, year, scenario, endpoint)
            if year == 2026:
                revenues[year] *= stub_fraction
        depreciation_basis = r['initial_book']
        if r.get('new_project'):
            depreciation_basis += sum(r['future_capex'].values()) * scenario['capex_multiplier']
        # Traffic/revenue proxy allocation is an explicit estimate, NOT a disclosed individual tax schedule.
        total_revenue = sum(revenues.values())
        carrying = r['initial_book']
        maintenance_cohorts = []
        rows = {}
        for year, revenue in revenues.items():
            fraction = annual_fraction(r, year) * (stub_fraction if year == 2026 else 1.0)
            original_da = depreciation_basis * revenue / total_revenue if total_revenue else 0.0
            cost_ratio = r['cash_cost_ratio'] + scenario['cash_cost_add']
            inflation = (1+est['cash_cost_inflation']) ** max(0,year-2026)
            fixed_cost = r['net_anchor'] * cost_ratio * 0.70 * inflation * fraction
            variable_cost = revenue * cost_ratio * 0.30
            overhead = r['net_anchor'] * est['road_overhead_ratio'] * inflation * fraction
            maintenance = revenue * r['maintenance_ratio']
            if maintenance:
                maintenance_cohorts.append((year, maintenance, min(5, r['end_year']-year+1)))
            maintenance_da = sum(amount / life for start, amount, life in maintenance_cohorts if start <= year < start+life)
            da = original_da + maintenance_da
            large_maintenance = r.get('large_maintenance_cash',0.0) if year in r.get('large_maintenance_years',[]) else 0.0
            ebitda = revenue-fixed_cost-variable_cost-overhead-large_maintenance
            # No group-wide loss tax credit assumed for a loss-making individual road.
            tax = max(0.0, ebitda-da) * est['tax_rate']
            capex = scheduled_amount(r['future_capex'],year,scenario['opening_delay']) * scenario['capex_multiplier'] if r.get('new_project') else 0.0
            capitalized_interest = scheduled_amount(data['other_capital']['weilai_interest_in_project_budget'],year,scenario['opening_delay']) * scenario['capex_multiplier'] if r.get('new_project') else 0.0
            carrying += capex + maintenance - da
            rows[year] = dict(revenue=revenue, ebitda=ebitda, depreciation=da, tax=tax, nopat=ebitda-da-tax,
                              cash_before_capital=ebitda-tax, capital_maintenance=maintenance, growth_capex=capex,
                              capitalized_interest=capitalized_interest,
                              fcff=ebitda-tax-maintenance-capex+capitalized_interest, book=carrying)
        plan[r['id']] = dict(meta=r, years=rows)
    return plan


def aggregate_road(plan, year, field, basis='group'):
    total = 0.0
    for item in plan.values():
        meta = item['meta']
        weight = 1.0 if basis == 'group' else (float(meta['mother_direct']) if basis == 'mother' else meta['ownership'])
        total += item['years'].get(year,{}).get(field,0.0) * weight
    return total


def annual_asset_receipts(data, scenario, year):
    group_cash = mother_cash = common_loss = 0.0
    for a in data['recovery_assets']:
        if year == a['base_recovery_year'] + scenario['recovery_delay']:
            cash = a['book'] * a['base_recovery_fraction'] * scenario['recovery_fraction_multiplier']
            group_cash += cash
            mother_cash += cash * a['mother_cash_fraction']
            common_loss += (a['book']-cash) * a['ownership']
    return group_cash, mother_cash, common_loss


def initial_state(data, scenario, plan):
    o, e = data['observed'], data['initial_estimates']
    shares = o['shares_issued']-o['treasury_shares']
    common_book = o['parent_equity']-o['perpetual']-o['buyback_cash']+e['year0_common_profit']
    payment_fraction = e['old_dividend_payment_fraction_2026']
    g220_group,g220_mother=g220_funding(data,scenario,2026)
    capex = aggregate_road(plan,2026,'growth_capex') + g220_group + e['year0_nonroad_capex']
    legacy = data['other_capital']['old_construction_payables_settlement'].get('2026',0.0)
    gcash = o['group_cash']-o['buyback_cash']+e['year0_group_cfo']+e['year0_other_investment_receipts_net']-capex-legacy-e['year0_ordinary_interest_cash']-e['year0_perp_cash']-e['year0_minorities']-o['old_group_dividend_payable']*payment_fraction
    mcash = o['mother_cash']-o['buyback_cash']+e['year0_mother_cfo']+e['year0_mother_upstream_cash']-aggregate_road(plan,2026,'growth_capex','mother')-g220_mother-e['year0_mother_other_capex']-legacy-e['year0_mother_interest_cash']-e['year0_mother_perp_cash']-o['old_mother_dividend_payable']*payment_fraction
    gborrow = max(0.0,e['group_cash_floor']-gcash)
    mborrow = max(0.0,e['mother_cash_floor']-mcash)
    return dict(shares=shares, common_book=common_book, group_cash=gcash+gborrow, mother_cash=mcash+mborrow,
                group_debt=e['group_debt']+gborrow, mother_debt=e['mother_debt']+mborrow,
                mother_re=o['mother_retained_earnings']+e['year0_mother_profit']-e['year0_statutory_reserve']-e['year0_mother_perp_cash'],
                perpetual=o['perpetual'], old_group_payable=o['old_group_dividend_payable']*(1-payment_fraction),
                old_mother_payable=o['old_mother_dividend_payable']*(1-payment_fraction),
                prev_gaap_profit=e['gaap_parent_profit_2026'],g220_group_cost_proxy=o.get('g220_invested',0.0)+g220_group,
                g220_mother_support_cumulative=g220_mother,
                financial_cohorts=[],maintenance_overlap_common=e['maintenance_overlap_common'],maintenance_overlap_mother=e['maintenance_overlap_mother'],
                year=2026, year0_group_new_debt=gborrow, year0_mother_new_debt=mborrow)


def financing_close(cash_before_dividend, dividend, opening_debt, cash_floor, borrowing_cap):
    after = cash_before_dividend-dividend
    need = max(0.0,cash_floor-after)
    borrowed = min(need,borrowing_cap)
    after += borrowed
    repaid = min(opening_debt, max(0.0,after-cash_floor))
    return dict(cash=after-repaid, debt=opening_debt+borrowed-repaid, borrowed=borrowed, repaid=repaid, funding_gap=max(0.0,cash_floor-after))


def run_case(data, scenario, endpoint, forced_distributions=None):
    e, o = data['initial_estimates'], data['observed']
    plan = build_plan(data,scenario,endpoint)
    state = initial_state(data,scenario,plan)
    state0 = copy.deepcopy(state)
    rows=[]
    ref_nopat = aggregate_road(plan,2026,'nopat','common') / data['identity'].get('historical_stub_fraction',0.25) if data['identity'].get('historical_stub_fraction',0.25) else aggregate_road(plan,2027,'nopat','common')
    ref_cash = aggregate_road(plan,2026,'cash_before_capital') / data['identity'].get('historical_stub_fraction',0.25) if data['identity'].get('historical_stub_fraction',0.25) else aggregate_road(plan,2027,'cash_before_capital')
    ref_mother_nopat = aggregate_road(plan,2026,'nopat','mother') / data['identity'].get('historical_stub_fraction',0.25) if data['identity'].get('historical_stub_fraction',0.25) else aggregate_road(plan,2027,'nopat','mother')
    ref_mother_cash = aggregate_road(plan,2026,'cash_before_capital','mother') / data['identity'].get('historical_stub_fraction',0.25) if data['identity'].get('historical_stub_fraction',0.25) else aggregate_road(plan,2027,'cash_before_capital','mother')
    for index,year in enumerate(data['identity']['forecast_years']):
        n=index+1
        ginterest=state['group_debt']*(e['group_interest_rate']+scenario['debt_rate_add'])
        minterest=state['mother_debt']*(e['mother_interest_rate']+scenario['debt_rate_add'])
        capitalized=aggregate_road(plan,year,'capitalized_interest')
        ginterest_expensed=ginterest-capitalized
        minterest_expensed=minterest-capitalized
        proportion=state['perpetual']/o['perpetual'] if o['perpetual'] else 0.0
        pcoupon=(e['perpetual_cash_coupon']+scenario['perp_coupon_add'])*proportion
        mcoupon=(e['mother_perpetual_cash_coupon']+scenario['perp_coupon_add'])*proportion
        cash_recovery,mother_recovery,recovery_loss=annual_asset_receipts(data,scenario,year)
        matured=sum(amount for start,amount in state['financial_cohorts'] if year==start+3)
        financial_income=sum(amount*0.04 for start,amount in state['financial_cohorts'] if start<year<=start+3)
        retained=[(start,amount) for start,amount in state['financial_cohorts'] if year<start+3]
        traffic_delta=aggregate_road(plan,year,'nopat','common')-ref_nopat
        mother_operating_delta=aggregate_road(plan,year,'nopat','mother')-ref_mother_nopat-scenario['nonroad_profit_damage']*0.5
        interest=matched_interest_effects(data,ginterest_expensed-e['group_debt']*e['group_interest_rate'],
                                         minterest_expensed-e['mother_debt']*e['mother_interest_rate'],mother_operating_delta)
        common_profit=e['common_profit_2026']+traffic_delta+e['nonroad_profit_growth_per_year']*n-scenario['nonroad_profit_damage']+interest['common_profit_change']-(pcoupon-e['perpetual_cash_coupon'])+financial_income
        mother_profit=e['mother_profit_2026']+mother_operating_delta+interest['mother_profit_change']
        # Cash maintenance already appears in road costs. Settlement of its opening recognized provision is not a second expense.
        provision_common=min(state['maintenance_overlap_common'],e['maintenance_overlap_common']/5)
        provision_mother=min(state['maintenance_overlap_mother'],e['maintenance_overlap_mother']/5)
        common_profit+=provision_common
        mother_profit+=provision_mother
        # Investment receipts are NOT added to mother profit; collection of prior declared dividends is cash only.
        reserve=max(0.0,mother_profit)*e['statutory_reserve_rate']
        legal_available=max(0.0,state['mother_re']+mother_profit-reserve-mcoupon)
        wc=scenario['extra_wc_per_year'] * scenario.get('wc_cash_profile',[1,1,1,1,1])[index]
        gcfo=e['group_cfo_2026']+aggregate_road(plan,year,'cash_before_capital')-ref_cash+e['nonroad_cfo_growth_per_year']*n-scenario['nonroad_profit_damage']-wc+interest['group_cash_tax_adjustment']
        mcfo=e['mother_cfo_ex_pool_2026']+aggregate_road(plan,year,'cash_before_capital','mother')-ref_mother_cash+interest['mother_cash_tax_adjustment']
        road_growth=aggregate_road(plan,year,'growth_capex')
        road_maint=aggregate_road(plan,year,'capital_maintenance')
        g220,g220_mother=g220_funding(data,scenario,year)
        legacy=data['other_capital']['old_construction_payables_settlement'].get(str(year),0.0)
        nongrowth=e['nonroad_growth_capex_per_year']*scenario['capex_multiplier']
        nonmaint=e['nonroad_maintenance_capex_per_year']
        newinvestment=e['new_financial_investment_per_year']
        oldg=state['old_group_payable'] if n==1 else 0.0
        oldm=state['old_mother_payable'] if n==1 else 0.0
        before_g=state['group_cash']+gcfo+e['investment_cash_income']+financial_income+cash_recovery+matured-road_growth-road_maint-g220-nongrowth-nonmaint-legacy-newinvestment-ginterest_expensed-pcoupon-e['minority_cash_distribution']-oldg
        before_m=state['mother_cash']+mcfo+e['mother_upstream_and_investment_cash']*scenario['mother_upstream_multiplier']+mother_recovery-aggregate_road(plan,year,'growth_capex','mother')-aggregate_road(plan,year,'capital_maintenance','mother')-g220_mother-nongrowth*e['mother_nonroad_growth_share']-nonmaint*e['mother_maintenance_share']-legacy-minterest_expensed-mcoupon-oldm-e['mother_net_pool_outflow_per_year']-scenario['mother_extra_pool_outflow']
        desired=max(e['policy_payout']*max(0.0,state['prev_gaap_profit']),e['dividend_floor_per_share']*state['shares'] if scenario['dividend_floor_enabled'] else 0.0)
        if forced_distributions is not None:
            desired=forced_distributions[index]*state['shares']
        feasible=min(legal_available,max(0.0,before_g+scenario['group_new_debt_caps'][index]-e['group_cash_floor']),max(0.0,before_m+scenario['mother_new_debt_caps'][index]-e['mother_cash_floor']))
        dividend=min(desired,feasible)
        fg=financing_close(before_g,dividend,state['group_debt'],e['group_cash_floor'],scenario['group_new_debt_caps'][index])
        fm=financing_close(before_m,dividend,state['mother_debt'],e['mother_cash_floor'],scenario['mother_new_debt_caps'][index])
        group_cash_residual=fg['cash']-(before_g-dividend+fg['borrowed']-fg['repaid'])
        mother_cash_residual=fm['cash']-(before_m-dividend+fm['borrowed']-fm['repaid'])
        assert abs(group_cash_residual)<1e-8 and abs(mother_cash_residual)<1e-8
        redeemed=scenario['perp_redemption'] if year==scenario['perp_redemption_year'] else 0.0
        # Explicit debt-for-perpetual replacement is cash-neutral, not shareholder income or a second borrowing allowance.
        state.update(group_cash=fg['cash'],mother_cash=fm['cash'],group_debt=fg['debt']+redeemed,mother_debt=fm['debt']+redeemed,perpetual=state['perpetual']-redeemed,
                     common_book=state['common_book']+common_profit-dividend-recovery_loss,
                     mother_re=state['mother_re']+mother_profit-reserve-mcoupon-dividend,
                     old_group_payable=state['old_group_payable']-oldg,old_mother_payable=state['old_mother_payable']-oldm,
                     prev_gaap_profit=common_profit+pcoupon,year=year,g220_group_cost_proxy=state['g220_group_cost_proxy']+g220,
                     g220_mother_support_cumulative=state['g220_mother_support_cumulative']+g220_mother,
                     maintenance_overlap_common=state['maintenance_overlap_common']-provision_common,
                     maintenance_overlap_mother=state['maintenance_overlap_mother']-provision_mother,
                     financial_cohorts=retained+([(year,newinvestment)] if newinvestment else []))
        rows.append(dict(year=year,common_profit=common_profit,gaap_parent_profit=common_profit+pcoupon,mother_profit=mother_profit,statutory_reserve=reserve,
                         incremental_interest_tax=interest,
                         group_cfo=gcfo,mother_cfo_ex_pool=mcfo,road_growth_capex=road_growth,g220_capex=g220,g220_mother_support_cash=g220_mother,capital_maintenance=road_maint+nonmaint,nonroad_growth_capex=nongrowth,
                         old_liabilities_paid=legacy+oldg,old_mother_dividend_paid=oldm,investment_principal_received=cash_recovery+matured,investment_cash_income=e['investment_cash_income']+financial_income,
                         ordinary_interest_cash=ginterest_expensed,perpetual_cash=pcoupon,perpetual_redemption=redeemed,desired_common_dividend=desired,actual_common_dividend=dividend,distribution_per_share=dividend/state['shares'],
                         legal_profit_capacity=legal_available,mother_cash=state['mother_cash'],group_cash=state['group_cash'],mother_debt=state['mother_debt'],group_debt=state['group_debt'],
                         group_new_debt=fg['borrowed'],group_debt_repaid=fg['repaid'],mother_new_debt=fm['borrowed'],common_book=state['common_book'],mother_re=state['mother_re'],
                         funding_gap=max(fg['funding_gap'],fm['funding_gap']),forced_distribution_shortfall=max(0.0,desired-dividend) if forced_distributions is not None else 0.0,
                         group_cash_identity_residual=group_cash_residual,mother_cash_identity_residual=mother_cash_residual,
                         debt_consistency_gap=max(0.0,state['mother_debt']-state['group_debt'])))
    return dict(initial_state=state0,final_state=state,rows=rows,plan=plan,
                cash_path_feasible=not any(r['funding_gap']>1e-8 or r['debt_consistency_gap']>1e-8 for r in rows),
                current=value_state(data,scenario,endpoint,state0,plan),terminal=value_state(data,scenario,endpoint,state,plan))


def value_state(data, scenario, endpoint, state, plan):
    date=state['year']; discount=endpoint['road_discount']+scenario.get('road_discount_add',0.0)
    road_pv=road_book=remaining_capex_pv=tail_pv=0.0
    for item in plan.values():
        weight=item['meta']['ownership']
        road_book += item['years'].get(date,{}).get('book',0.0)*weight
        for year,row in item['years'].items():
            if year > date:
                term=row['fcff']*weight/(1+discount)**(year-date)
                road_pv += term
                remaining_capex_pv += row['growth_capex']*weight/(1+discount)**(year-date)
                if year>date+5: tail_pv += term
    recovery_adjust=0.0
    for a in data['recovery_assets']:
        recovery_year=a['base_recovery_year']+scenario['recovery_delay']
        if date<recovery_year:
            cash=a['book']*a['base_recovery_fraction']*scenario['recovery_fraction_multiplier']
            recovery_adjust += (cash/(1+a['discount'])**(recovery_year-date)-a['book'])*a['ownership']
    nonroad_adjust=data['initial_estimates']['extra_nonroad_common_value_adjustment']
    unit_detail=[]
    for unit in data['nonroad_units']:
        common_capital=unit['assets']-unit['liabilities']-unit['minority_book']
        factor=max(0.0,unit['base_value_factor']+endpoint['nonroad_factor_shift']+scenario['nonroad_value_factor_add'])
        adjust=common_capital*(factor-1.0)
        nonroad_adjust += adjust
        unit_detail.append(dict(id=unit['id'],common_capital=common_capital,value_factor=factor,adjustment=adjust))
    # A concession agreement exists, but its cash-economics terms are unavailable: no invented toll DCF or near-term collection.
    g220_factor=max(0.0,endpoint.get('g220_value_factor',data['initial_estimates']['g220_value_factor'])+scenario['nonroad_value_factor_add'])
    g220_group_adjust=state['g220_group_cost_proxy']*(g220_factor-1.0)
    g220_group_adjust += sum(amount*scenario['capex_multiplier']*(g220_factor-1.0)/(1+discount)**(int(year)-date)
                       for year,amount in data['other_capital']['g220_future_capex'].items() if int(year)>date)
    ownership=data['observed']['g220_common_ownership']
    parent_loan_exposure=state['g220_mother_support_cumulative']+sum(
        g220_funding(data,scenario,int(year))[1]/(1+discount)**(int(year)-date)
        for year in data['other_capital']['g220_future_capex'] if int(year)>date)
    # A bounded economic exposure test, not an assertion of contractual recourse.
    # Ordinary project equity bears its share first; unverified financing support is a separate 0..1 range.
    if g220_group_adjust<0:
        group_loss=-g220_group_adjust
        equity_layer=min(group_loss,data['observed']['g220_group_registered_capital'])
        parent_equity_loss=min(equity_layer*ownership,data['observed']['g220_parent_equity_cost'])
        financing_shortfall=max(0.0,group_loss-data['observed']['g220_group_registered_capital'])
        # Risk-bearing shareholder advances absorb creditor loss before any optional rescue of outsiders.
        # This is an economic conservatism, not a claimed contractual liquidation ranking.
        parent_loan_loss=min(parent_loan_exposure,financing_shortfall)
        outside_financing_shortfall=financing_shortfall-parent_loan_loss
        g220_adjust=-parent_equity_loss-parent_loan_loss-outside_financing_shortfall*scenario['g220_parent_financing_loss_share']
    else:
        financing_shortfall=parent_loan_loss=outside_financing_shortfall=0.0
        g220_adjust=g220_group_adjust*ownership
    rolling_adjust=0.0
    for start,principal in state['financial_cohorts']:
        remaining=start+3-date
        if remaining>0:
            rolling_adjust += principal/(1.05)**remaining+sum(principal*0.04/(1.05)**k for k in range(1,remaining+1))-principal
    total=state['common_book']+road_pv-road_book+recovery_adjust+nonroad_adjust+g220_adjust+rolling_adjust+state['maintenance_overlap_common']
    # The opening common book already excludes all perpetual principal, NCI, and the old declared dividend liability.
    stub=data['identity']['valuation_stub_years'] if date==2026 else 0.0
    per_share=total/(1+discount)**stub/state['shares']
    return dict(ordinary_equity=total,per_share=per_share,common_book=state['common_book'],attributable_road_pv=road_pv,
                attributable_road_book=road_book,road_revaluation=road_pv-road_book,recovery_adjustment=recovery_adjust,
                nonroad_adjustment=nonroad_adjust,g220_adjustment=g220_adjust,rolling_financial_adjustment=rolling_adjust,
                g220_group_value_adjustment=g220_group_adjust,g220_common_ownership=data['observed']['g220_common_ownership'],
                g220_financing_shortfall_proxy=financing_shortfall,g220_parent_financing_loss_share=scenario['g220_parent_financing_loss_share'],
                g220_parent_loan_exposure=parent_loan_exposure,g220_parent_loan_loss=parent_loan_loss,g220_outside_financing_shortfall=outside_financing_shortfall,
                g220_parent_support_cumulative=state['g220_mother_support_cumulative'],
                maintenance_liability_overlap_adjustment=state['maintenance_overlap_common'],
                remaining_road_capex_pv=remaining_capex_pv,road_value_beyond_five_years=tail_pv,unit_details=unit_detail)


def auxiliary_value(data):
    e,o=data['initial_estimates'],data['observed']
    common_book=o['parent_equity']-o['perpetual']-o['buyback_cash']
    shares=o['shares_issued']-o['treasury_shares']
    values=[]
    for earnings,cost,recovery in [(e['aux_common_earnings_low'],e['aux_equity_cost_high'],e['aux_book_recovery_low']),
                                   (e['aux_common_earnings_high'],e['aux_equity_cost_low'],e['aux_book_recovery_high'])]:
        years=e['aux_life_years']
        profit_pv=sum(earnings/(1+cost)**t for t in range(1,years+1))
        capital_pv=common_book*recovery/(1+cost)**years
        values.append(dict(per_share=(profit_pv+capital_pv)/shares,profit_pv=profit_pv,capital_recovery_pv=capital_pv))
    return dict(method='normal_common_earnings_annuity_plus_net_capital_recovery',low=values[0],high=values[1])


def diagnostic_sensitivities(data):
    """One input at a time; diagnostic bounds are not fitted to obtain a desired range."""
    configurations=[
        ('road_book_78','endpoint','road_book_total',78.0),
        ('road_book_82_5','endpoint','road_book_total',82.5),
        ('qilu_book_weight_1','endpoint','qilu_book_weight',1.0),
        ('qilu_book_weight_1_5','endpoint','qilu_book_weight',1.5),
        ('road_discount_4_5pct','endpoint','road_discount',0.045),
        ('road_discount_6_5pct','endpoint','road_discount',0.065),
        ('g220_no_recovery','estimate','g220_value_factor',0.0),
        ('g220_at_cost','estimate','g220_value_factor',1.0),
        ('g220_no_additional_parent_support','scenario','g220_parent_support_fraction',0.0),
        ('g220_full_parent_support','scenario','g220_parent_support_fraction',1.0),
        ('g220_no_parent_financing_recourse','scenario','g220_parent_financing_loss_share',0.0),
        ('g220_full_parent_financing_recourse','scenario','g220_parent_financing_loss_share',1.0),
        ('perp_coupon_0_5','estimate','perpetual_cash_coupon',0.50),
        ('perp_coupon_0_85','estimate','perpetual_cash_coupon',0.85),
        ('nonroad_growth_0_3','estimate','nonroad_growth_capex_per_year',0.30),
        ('nonroad_growth_0_9','estimate','nonroad_growth_capex_per_year',0.90),
        ('investment_cash_0_4','estimate','investment_cash_income',0.40),
        ('investment_cash_1_2','estimate','investment_cash_income',1.20),
        ('mother_no_current_interest_tax_benefit','estimate','mother_interest_tax_eligible_fraction',0.0),
        ('mother_zero_starting_taxable_proxy','estimate','mother_taxable_income_proxy_2026',0.0),
        ('nonmother_no_extra_tax_on_interest_saving','estimate','nonmother_tax_on_interest_savings_fraction',0.0),
        ('maintenance_overlap_zero','estimate','maintenance_overlap_common',0.0),
        ('maintenance_overlap_gross_upper','estimate','maintenance_overlap_common',0.3781389),
        ('no_early_claim_collection','scenario','recovery_delay',5),
        ('weilai_20_years','weilai','operating_years',20),
        ('weilai_revenue_0_44','weilai','mature_first_full_net_revenue',0.44),
        ('weilai_revenue_0_66','weilai','mature_first_full_net_revenue',0.66),
    ]
    out={}
    for name,kind,key,value in configurations:
        x=copy.deepcopy(data); endpoint=copy.deepcopy(x['endpoints']['central']); scenario=x['scenarios']['base']
        target={'endpoint':endpoint,'estimate':x['initial_estimates'],'scenario':scenario,'weilai':x['weilai']}[kind]
        target[key]=value
        if key=='perpetual_cash_coupon':
            # Keep the normalized ordinary-profit baseline and total GAAP earnings consistent.
            delta=value-data['initial_estimates']['perpetual_cash_coupon']
            x['initial_estimates']['common_profit_2026']-=delta
            x['initial_estimates']['mother_perpetual_cash_coupon']+=delta
        c=run_case(x,scenario,endpoint)
        out[name]=dict(current=c['current'],terminal=c['terminal'],distributions=[r['distribution_per_share'] for r in c['rows']],
                       max_funding_gap=max(r['funding_gap'] for r in c['rows']),final_group_debt=c['final_state']['group_debt'])
    # Joint endpoint of the specific unresolved project contract, not an all-company worst-case mixture.
    for name,loss_share in [('g220_total_asset_loss_no_financing_support',0.0),('g220_total_asset_loss_full_financing_support',1.0)]:
        x=copy.deepcopy(data)
        x['initial_estimates']['g220_value_factor']=0.0
        x['scenarios']['base']['g220_parent_financing_loss_share']=loss_share
        c=run_case(x,x['scenarios']['base'],x['endpoints']['central'])
        out[name]=dict(current=c['current'],terminal=c['terminal'],distributions=[r['distribution_per_share'] for r in c['rows']],
                       max_funding_gap=max(r['funding_gap'] for r in c['rows']),final_group_debt=c['final_state']['group_debt'])
    return out


def build_output(data):
    central=run_case(data,data['scenarios']['base'],data['endpoints']['central'])
    d=[row['distribution_per_share'] for row in central['rows']]
    cases={}
    for name in ['core_low','core_high']:
        cases[name]=run_case(data,data['scenarios']['base'],data['endpoints'][name],d)
    for name in ['cycle','structural']:
        cases[name]=run_case(data,data['scenarios'][name],data['endpoints']['central'])
    issues=[]
    for name,case in [('base',central)]+list(cases.items()):
        for row in case['rows']:
            for key in ['funding_gap','forced_distribution_shortfall','debt_consistency_gap']:
                if row[key]>1e-8: issues.append(dict(case=name,year=row['year'],issue=key,amount=row[key]))
    low,high=cases['core_low'],cases['core_high']
    base_issue=any(x['case'] in ['base','core_low','core_high'] for x in issues)
    current_range={'low':low['current']['per_share'],'high':high['current']['per_share'],'currency':'CNY'}
    terminal_range={'low':low['terminal']['per_share'],'high':high['terminal']['per_share']}
    if current_range['low']<0 or current_range['low']>current_range['high'] or terminal_range['low']<0 or terminal_range['low']>terminal_range['high']:
        base_issue=True
        issues.append(dict(issue='range_order_or_negative_value'))
    interface={'value_range':None if base_issue else current_range,
               'return_model':None if base_issue else {'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY',
               'model_as_of':data['identity']['cutoff'],'base_case_distributions_per_share':d,
               'base_case_terminal_equity_value_range_per_share':{'year_5':terminal_range}}}
    def compact(c): return {k:v for k,v in c.items() if k!='plan'}
    stub=data['identity'].get('historical_stub_fraction',0.25)
    normalization=dict(estimated_2026_road_da=aggregate_road(central['plan'],2026,'depreciation')/stub,
                       fy25_actual_road_da=data['observed']['fy25_toll_depreciation'],
                       estimated_2026_road_cash=aggregate_road(central['plan'],2026,'cash_before_capital')/stub,
                       maintenance_provision_gross_overlap_bound=0.3781389,
                       annual_period_alignment='Fiscal 2027-2031 are annual proxies; terminal at fiscal 2031, not an exact October anniversary.')
    return dict(identity=data['identity'],status='calculation_only_not_research_acceptance',interfaces=interface,
                base=compact(central),cases={name:compact(case) for name,case in cases.items()},auxiliary=auxiliary_value(data),
                diagnostics=diagnostic_sensitivities(data),normalization=normalization,issues=issues)


def hand_cases(production):
    # Closed inputs, not calculations checked against themselves. Expected results are independently handwritten.
    x=copy.deepcopy(production); e=x['initial_estimates']; o=x['observed']
    for key in e: e[key]=0.0
    e.update(group_cash_floor=0.0,mother_cash_floor=0.0,road_cash_cost_ratio=1/3,dividend_floor_per_share=20.0,common_profit_2026=0.0,
             group_cfo_2026=20.0,mother_cfo_ex_pool_2026=20.0,statutory_reserve_rate=0.0)
    for key in o: o[key]=0.0
    o.update(parent_equity=100.0,shares_issued=1.0,mother_retained_earnings=100.0,fy25_toll_revenue_net=1.0,fy25_toll_revenue_gross=1.0)
    x['identity'].update(historical_stub_fraction=0.0,valuation_stub_years=0.0)
    x['weilai']=None;x['recovery_assets']=[];x['nonroad_units']=[]
    x['other_capital']={key:{} for key in x['other_capital']}
    x['roads']=[dict(id='test',gross_2025=30.0,ytd_2026_wan=1.0,ytd_2025_wan=1.0,net_anchor_override=30.0,ownership=1.0,mother_direct=True,end_year=2031,end_fraction=1.0,growth=0.0)]
    scenario=copy.deepcopy(production['scenarios']['base'])
    for key in ['debt_rate_add','perp_coupon_add','nonroad_profit_damage','extra_wc_per_year','mother_extra_pool_outflow','perp_redemption']:scenario[key]=0.0
    scenario.update(description='closed hand case',group_new_debt_caps=[0]*5,mother_new_debt_caps=[0]*5,dividend_floor_enabled=True,jingtai_recovery=[0]*5)
    endpoint=dict(road_discount=0.0,road_growth_shift=0.0,road_book_total=100.0,qilu_book_weight=1.0,nonroad_factor_shift=0.0)
    one=run_case(x,scenario,endpoint)
    assert abs(one['current']['ordinary_equity']-100.0)<1e-8
    assert all(abs(r['actual_common_dividend']-20.0)<1e-8 for r in one['rows'])
    assert abs(one['terminal']['ordinary_equity'])<1e-8
    y=copy.deepcopy(x);y['roads']=[];y['observed'].update(parent_equity=30.0,group_cash=50.0,mother_cash=50.0,old_group_dividend_payable=20.0,old_mother_dividend_payable=20.0,mother_retained_earnings=30.0)
    y['initial_estimates'].update(dividend_floor_per_share=10.0,group_cfo_2026=0.0,mother_cfo_ex_pool_2026=0.0)
    endpoint2=dict(endpoint,road_book_total=0.0)
    two=run_case(y,scenario,endpoint2)
    assert abs(two['current']['ordinary_equity']-30.0)<1e-8
    assert [r['actual_common_dividend'] for r in two['rows']]==[10.0,10.0,10.0,0.0,0.0]
    assert abs(two['terminal']['ordinary_equity'])<1e-8
    z=copy.deepcopy(y)
    z['observed'].update(parent_equity=20.438,group_cash=20.0,mother_cash=10.0,mother_retained_earnings=20.438,
                         old_group_dividend_payable=0.0,old_mother_dividend_payable=0.0,g220_invested=10.0,g220_common_ownership=0.5219,
                         g220_group_registered_capital=20.0,g220_parent_equity_cost=10.438)
    z['initial_estimates'].update(dividend_floor_per_share=0.0,g220_value_factor=0.5)
    z['other_capital']['g220_future_capex']={'2027':2.0}
    scenario3=copy.deepcopy(scenario);scenario3['g220_parent_support_fraction']=0.5219
    three=run_case(z,scenario3,endpoint2)
    assert abs(three['current']['ordinary_equity']-17.3066)<1e-8
    assert abs(three['rows'][0]['group_cash']-18.0)<1e-8
    assert abs(three['rows'][0]['mother_cash']-8.9562)<1e-8
    assert abs(three['rows'][0]['g220_mother_support_cash']-1.0438)<1e-8
    assert abs(three['terminal']['ordinary_equity']-17.3066)<1e-8
    t=copy.deepcopy(y)
    t['observed'].update(parent_equity=100.0,group_cash=0.0,mother_cash=0.0,mother_retained_earnings=100.0,
                         old_group_dividend_payable=0.0,old_mother_dividend_payable=0.0)
    t['initial_estimates'].update(dividend_floor_per_share=0.0,group_debt=20.0,mother_debt=20.0,
                                 group_interest_rate=0.10,mother_interest_rate=0.10,common_interest_fraction=1.0,
                                 group_cfo_2026=10.0,mother_cfo_ex_pool_2026=10.0,common_profit_2026=5.0,mother_profit_2026=5.0,
                                 tax_rate=0.25,mother_taxable_income_proxy_2026=4.0,mother_interest_tax_eligible_fraction=1.0)
    tax_scenario=copy.deepcopy(scenario);tax_scenario['debt_rate_add']=0.05
    four=run_case(t,tax_scenario,endpoint2)
    r=four['rows'][0]
    assert abs(r['incremental_interest_tax']['mother_current_tax_before']-1.0)<1e-8
    assert abs(r['incremental_interest_tax']['mother_current_tax_after']-0.75)<1e-8
    assert abs(r['common_profit']-4.25)<1e-8 and abs(r['mother_profit']-4.25)<1e-8
    assert abs(r['group_cfo']-10.25)<1e-8 and abs(r['group_debt']-12.75)<1e-8
    assert abs(r['common_book']-104.25)<1e-8
    t0=copy.deepcopy(t);t0['initial_estimates']['mother_taxable_income_proxy_2026']=0.0
    five=run_case(t0,tax_scenario,endpoint2);r=five['rows'][0]
    assert r['incremental_interest_tax']['mother_current_tax_before']==0.0
    assert r['incremental_interest_tax']['mother_current_tax_after']==0.0
    assert r['incremental_interest_tax']['new_deferred_tax_asset']==0.0
    assert abs(r['incremental_interest_tax']['unrecognized_mother_interest_tax_benefit']-0.25)<1e-8
    assert abs(r['common_profit']-4.0)<1e-8 and abs(r['mother_profit']-4.0)<1e-8
    assert abs(r['group_cfo']-10.0)<1e-8 and abs(r['group_debt']-13.0)<1e-8
    assert abs(r['common_book']-104.0)<1e-8
    u=copy.deepcopy(z)
    u['observed'].update(parent_equity=11.0438,mother_retained_earnings=11.0438,g220_group_registered_capital=2.0,g220_parent_equity_cost=1.0438)
    u['initial_estimates'].update(group_debt=18.0,group_cash_floor=18.0,g220_value_factor=0.0)
    s0=copy.deepcopy(scenario3);s0['g220_parent_financing_loss_share']=0.0
    six=run_case(u,s0,endpoint2)
    assert abs(six['current']['ordinary_equity']-8.9562)<1e-8
    assert abs(six['terminal']['ordinary_equity']-8.9562)<1e-8
    assert abs(six['current']['g220_parent_loan_loss']-1.0438)<1e-8
    assert abs(six['terminal']['g220_parent_loan_loss']-1.0438)<1e-8
    assert abs(six['rows'][0]['mother_cash']-8.9562)<1e-8
    sn=copy.deepcopy(s0);sn['g220_parent_support_fraction']=0.0
    six_no_new=run_case(u,sn,endpoint2)
    assert abs(six_no_new['terminal']['ordinary_equity']-10.0)<1e-8
    assert six_no_new['terminal']['g220_parent_loan_loss']==0.0
    sf=copy.deepcopy(s0);sf['g220_parent_financing_loss_share']=1.0
    six_full=run_case(u,sf,endpoint2)
    assert abs(six_full['terminal']['ordinary_equity'])<1e-8
    return {'case_1':'finite five-year asset capital recovery','case_2':'old dividend remains a liability but is not new-holder cash',
            'case_3':'group project spending, common ownership and parent support are distinct',
            'case_4':'matched current tax cash realization','case_5':'no tax base, no refund, no deferred tax asset',
            'case_6':'new parent principal remains at risk without rescue of outside financing; two companion boundaries',
            'closed_case_runs':8,'executed':True}
