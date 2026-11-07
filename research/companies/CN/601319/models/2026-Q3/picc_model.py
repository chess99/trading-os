"""PICC finite deterministic model. Import defines functions only; never runs a valuation."""
from datetime import date
import math
import traceback


class EconomicBudgetInfeasible(Exception):
    """Only a genuine stated budget constraint, never input/assert/program failure."""
    def __init__(self, message, *, constraint, available, obligations):
        super().__init__(message)
        self.details = {'constraint': constraint, 'available': available,
                        'obligations': obligations, 'year': None, 'phase': None}
        self.partial_persistence_failed = False


def emit_checkpoint(checkpoint, kind, payload):
    if checkpoint is not None:
        checkpoint(kind, payload)


def preserve_failure(checkpoint, kind, payload, original):
    """A secondary journal error must never replace the actual original exception."""
    try:
        emit_checkpoint(checkpoint, kind, payload)
    except BaseException as cache_error:
        original.add_note('Partial persistence also failed: '+repr(cache_error))
        original.partial_persistence_failed = True



def close(a, b, label, tol=1e-7):
    if not math.isfinite(a) or not math.isfinite(b) or abs(a-b) > tol*max(1.0, abs(a), abs(b)):
        raise AssertionError(f'{label}: {a!r} != {b!r}')


def declared_equity(book, profit, declaration, new_cash=0.0):
    return book + profit + new_cash - declaration


def pay_existing(cash, payable, amount):
    if amount < 0 or amount > payable + 1e-8:
        raise ValueError('payment exceeds existing payable')
    return cash-amount, payable-amount


def coupon_rate(year, first, step, step_date):
    start = date(2026+year-1, 11, 1)
    end = date(2026+year, 11, 1)
    change = date.fromisoformat(step_date)
    old_days = max(0, (min(end, max(start, change))-start).days)
    total = (end-start).days
    return (old_days*first + (total-old_days)*step)/total


def ownership(o):
    return {'pc': o['pc_direct'],
            'life': o['life_direct']+o['life_via_asset']+o['pc_direct']*o['life_via_pc'],
            'health': o['health_direct']+o['health_via_holdco']+o['pc_direct']*o['health_via_pc']}


def make_entity(o, name):
    return {'core': o[name+'_core_h126'], 'minimum': o[name+'_min_h126'],
            'surplus': 0.0, 'legal_pool': 0.0, 'scale': 1.0, 'previous_profit': 0.0}


def entity_step(state, core_profit_at_base, planned_growth, payout, target, recognition,
                legal_fraction, surplus_yield, holding_dividend=0.0):
    """Core is a forecast regulatory proxy, not ordinary book or cash. No external rescue."""
    old = dict(state)
    safe_profit = max(old['previous_profit'], core_profit_at_base*old['scale'], 0.0)
    affordable_growth = max(0.0, (old['core']+safe_profit*recognition)/(target*old['minimum'])-1.0)
    growth = min(planned_growth, affordable_growth)
    state['minimum'] = old['minimum']*(1.0+growth)
    state['scale'] = old['scale']*(1.0+growth)
    core_profit = core_profit_at_base*state['scale']
    surplus_income = old['surplus']*surplus_yield
    profit = core_profit+surplus_income+holding_dividend
    pool_before = max(0.0, old['legal_pool']+legal_fraction*max(profit, 0.0)+min(profit, 0.0))
    core_before = old['core']+recognition*profit
    capital_headroom = max(0.0, core_before-target*state['minimum'])
    dividend = min(max(0.0, payout*profit), pool_before, capital_headroom)
    state['core'] = core_before-dividend
    state['legal_pool'] = pool_before-dividend
    operating_retention = (state['minimum']-old['minimum'])*target/recognition
    state['surplus'] = max(0.0, old['surplus']+profit-dividend-operating_retention)
    state['previous_profit'] = profit
    close(state['core'], old['core']+recognition*profit-dividend, 'subsidiary capital')
    return {'profit': profit, 'core_profit': core_profit, 'dividend': dividend,
            'surplus_income': surplus_income, 'actual_growth': growth,
            'core_ratio_proxy': state['core']/state['minimum'],
            'target_shortfall': max(0.0, target*state['minimum']-state['core'])}


def fund_cash(cash, pool, minimum, sale_cost):
    """Redeem existing liquid assets, not a new asset or profit. Loss deducted separately."""
    required = max(0.0, minimum-cash)
    gross = required/(1.0-sale_cost)
    if gross > pool+1e-6:
        raise EconomicBudgetInfeasible(
            'Liquid mother assets cannot fund the stated cash floor/payment obligation',
            constraint='mother_liquid_asset_budget',
            available={'cash_before_funding': cash, 'liquid_pool_gross': pool,
                       'liquid_pool_net_at_sale_cost': pool*(1.0-sale_cost)},
            obligations={'required_cash_minimum': minimum, 'cash_shortfall_net': required,
                         'required_bond_sale_gross': gross, 'sale_cost_rate': sale_cost})
    return cash+gross*(1.0-sale_cost), pool-gross, gross*sale_cost, gross


def starting_state(inputs, s, financing):
    o, c = inputs['observed'], inputs['common_forecast']
    old_n = o['shares']
    opening_payable = old_n*o['opening_dividend_per_old_share']
    cash = o['mother_cash_equivalents']-s['new_litigation_loss']
    book = o['group_book']-s['new_litigation_loss']
    re = o['mother_re']-s['new_litigation_loss']
    cash, pool, sale_loss, sold = fund_cash(cash, c['mother_liquid_bond_pool'],
                                         opening_payable+c['mother_cash_floor'], s['liquid_bond_sale_cost'])
    book -= sale_loss
    re -= sale_loss
    cash, remaining = pay_existing(cash, opening_payable, opening_payable)
    close(remaining, 0.0, 'opening payable extinguished')
    # No book/RE reduction for the payment: the declaration was included in Q3 B and RE.
    new_shares = old_n*financing['new_shares_fraction']
    if financing['cash'] == 0:
        if new_shares != 0:
            raise ValueError('unfunded share issue')
        issue_price = None
    else:
        if new_shares <= 0 or financing['new_shares_fraction'] > 0.10:
            raise ValueError('funds and shares not linked or cap exceeded')
        issue_price = financing['cash']/new_shares
    book += financing['cash']
    pool += financing['cash']
    return {'book': book, 'mother_re': re, 'cash': cash, 'pool': pool,
            'shares': old_n+new_shares, 'old_shares': old_n, 'nominal_capital': old_n+new_shares,
            'group_core': o['group_core_h126']+financing['cash']-s['new_litigation_loss']-sale_loss,
            'group_minimum': o['group_min_h126'], 'payable': 0.0, 'upstream_receivable': 0.0,
            'legal_reserve_proxy': s['mother_legal_reserve_proxy'],
            'opening_claim': o['opening_dividend_per_old_share'],
            'opening_sale_loss': sale_loss, 'opening_bonds_sold': sold,
            'previous_group_profit': 0.0, 'issue_cash': financing['cash'], 'new_shares': new_shares, 'conditional_issue_price': issue_price}


def forecast(inputs, s, financing, checkpoint=None):
    try:
        o, c = inputs['observed'], inputs['common_forecast']
        w = ownership(o)
        st = starting_state(inputs, s, financing)
        initial = dict(st)
        emit_checkpoint(checkpoint, 'initial_state', {'year': 0, 'state': dict(st)})
        entities = {name: make_entity(o, name) for name in ('pc', 'life', 'health')}
        # Life budget is ALREADY ordinary profit net of perpetual coupon; never subtract it again.
        base_profit = {'pc': o['pc_service_fy25']*(1.0-s['pc_cor'])*(1.0-c['pc_tax'])+s['pc_net_investment_budget'],
                       'life': s['life_ordinary_net_profit'], 'health': s['health_net_profit']}
        rows = []
        for year in range(1, c['horizon_years']+1):
            old = dict(st)
            emit_checkpoint(checkpoint, 'year_begin', {'year': year, 'state': dict(st),
                'entities': {name: dict(value) for name, value in entities.items()}, 'completed_rows': len(rows)})
            ramp = min(1.0, max(0.0, (year-5)/5.0))
            group_affordable_growth = max(0.0, (old['group_core']+c['capital_profit_recognition']*max(old['previous_group_profit'], 0.0))/(c['group_core_target']*old['group_minimum'])-1.0)
            growth = {name: min(s[name+'_growth'] if year <= 5 else s['long_growth'], group_affordable_growth) for name in entities}
            payout = {name: s[name+'_payout']+ramp*c[name+'_dividend_ramp_after_year5'] for name in entities}
            results = {}
            for name in ('life', 'health'):
                results[name] = entity_step(entities[name], base_profit[name], growth[name], payout[name],
                    c[name+'_core_target'], c['capital_profit_recognition'],
                    c['subsidiary_distributable_profit_fraction'], s['surplus_yield'])
            holding_dividend = (o['life_via_pc']*results['life']['dividend']
                                +o['health_via_pc']*results['health']['dividend'])
            results['pc'] = entity_step(entities['pc'], base_profit['pc'], growth['pc'], payout['pc'],
                c['pc_core_target'], c['capital_profit_recognition'],
                c['subsidiary_distributable_profit_fraction'], s['surplus_yield'], holding_dividend)
            # PC accounting/solvency budget recognizes received strategic dividends; consolidated ordinary
            # profit instead uses ultimate underlying insurer earnings, so those dividends are eliminated.
            pc_pure_profit = results['pc']['profit']-holding_dividend
            other_profit = c['other_group_ordinary_profit']*(1.0+s['long_growth'])**year
            upstream_declared = (o['pc_direct']*results['pc']['dividend']
                +(o['life_direct']+o['life_via_asset'])*results['life']['dividend']
                +(o['health_direct']+o['health_via_holdco'])*results['health']['dividend']
                +c['other_parent_payout']*other_profit)
            upstream_received = old['upstream_receivable']+(1.0-c['parent_receipt_lag_fraction'])*upstream_declared
            st['upstream_receivable'] = c['parent_receipt_lag_fraction']*upstream_declared
            own_income = c['mother_own_income_ex_buffer']+old['pool']*s['surplus_yield']
            operating_cost = c['mother_operating_cost']*(1.0+c['sotp_parent_cost_growth'])**(year-1)
            interest = o['mother_bond_face']*coupon_rate(year, o['mother_bond_coupon_first'],
                        o['mother_bond_coupon_step'], o['mother_bond_step_date'])
            mother_profit_before_sale = upstream_declared+own_income-operating_cost-interest
            group_profit_before_sale = (w['pc']*pc_pure_profit+w['life']*results['life']['profit']
                +w['health']*results['health']['profit']+other_profit+own_income-operating_cost-interest)
            cash_before_new = old['cash']+upstream_received+own_income-operating_cost-interest-old['payable']
            cash_before_new, pool, sale_loss, sold = fund_cash(cash_before_new, old['pool'],
                                                             c['mother_cash_floor'], s['liquid_bond_sale_cost'])
            mother_profit = mother_profit_before_sale-sale_loss
            group_profit = group_profit_before_sale-sale_loss
            legal_rate = 0.10 if (year <= c['minimum_statutory_policy_years'] or
                                 old['legal_reserve_proxy'] < 0.5*st['nominal_capital']) else 0.0
            legal_addition = legal_rate*max(0.0, mother_profit)
            legal_room = max(0.0, old['mother_re']+mother_profit-legal_addition)
            group_core_before = old['group_core']+c['capital_profit_recognition']*group_profit
            planned_group_growth = max(r['actual_growth'] for r in results.values())
            st['group_minimum'] = old['group_minimum']*(1.0+planned_group_growth)
            group_cap_room = max(0.0, group_core_before-c['group_core_target']*st['group_minimum'])
            planned_decl = max(0.0, group_profit)*(s['group_payout']+ramp*c['group_dividend_ramp_after_year5'])
            # Current cash plus an explicitly priced liquidation of existing liquid assets can fund
            # the declaration in full; reserve the deferred part rather than borrow against it.
            liquidity_room = max(0.0, cash_before_new-c['mother_cash_floor']+pool*(1.0-s['liquid_bond_sale_cost']))
            declaration = min(planned_decl, legal_room, group_cap_room, liquidity_room)
            cash_before_new, pool, declaration_sale_loss, declaration_sold = fund_cash(
                cash_before_new, pool, declaration+c['mother_cash_floor'], s['liquid_bond_sale_cost'])
            # Recompute legal/capital room after actual sale cost; no recursive retry.
            mother_profit -= declaration_sale_loss
            group_profit -= declaration_sale_loss
            legal_addition = legal_rate*max(0.0, mother_profit)
            declaration = min(declaration, max(0.0, old['mother_re']+mother_profit-legal_addition),
                max(0.0, old['group_core']+c['capital_profit_recognition']*group_profit
                    -c['group_core_target']*st['group_minimum']))
            new_cash_payment = c['same_window_payment_fraction']*declaration
            st['payable'] = (1.0-c['same_window_payment_fraction'])*declaration
            st['cash'] = cash_before_new-new_cash_payment
            st['pool'] = pool
            # Invest only unencumbered cash; pending declared dividends remain in cash.
            sweep = max(0.0, st['cash']-c['mother_cash_floor']-st['payable'])
            st['cash'] -= sweep
            st['pool'] += sweep
            st['book'] = declared_equity(old['book'], group_profit, declaration)
            st['mother_re'] = old['mother_re']+mother_profit-legal_addition-declaration
            st['legal_reserve_proxy'] = old['legal_reserve_proxy']+legal_addition
            st['group_core'] = old['group_core']+c['capital_profit_recognition']*group_profit-declaration
            st['previous_group_profit'] = group_profit
            cash_paid = old['payable']+new_cash_payment
            close(st['book'], old['book']+group_profit-declaration, 'group clean surplus by declaration')
            close(st['mother_re'], old['mother_re']+mother_profit-legal_addition-declaration, 'mother RE')
            close(st['payable'], old['payable']+declaration-cash_paid, 'dividend payable roll')
            total_sold = sold+declaration_sold
            total_sale_loss = sale_loss+declaration_sale_loss
            close(st['cash'], old['cash']+upstream_received+own_income-operating_cost-interest
                  +total_sold-total_sale_loss-cash_paid-sweep, 'mother cash conservation')
            close(st['pool'], old['pool']-total_sold+sweep, 'mother liquid asset conservation')
            if st['mother_re'] < -1e-6 or st['cash']+1e-6 < c['mother_cash_floor']+st['payable']:
                raise AssertionError('unfunded new declaration or negative mother distributable RE')
            gross_core_profit = (w['pc']*max(results['pc']['core_profit'], 0.0)
                +w['life']*max(results['life']['core_profit'], 0.0)
                +w['health']*max(results['health']['core_profit'], 0.0)+max(other_profit, 0.0)
                +max(c['mother_own_income_ex_buffer'], 0.0))
            rows.append({'year': year, 'group_profit': group_profit, 'group_book': st['book'],
                'group_core_proxy': st['group_core'], 'group_minimum_proxy': st['group_minimum'],
                'group_core_target_shortfall': max(0.0, c['group_core_target']*st['group_minimum']-st['group_core']),
                'mother_profit': mother_profit, 'mother_re': st['mother_re'], 'mother_cash': st['cash'],
                'mother_liquid_pool': st['pool'], 'upstream_declared': upstream_declared,
                'upstream_received': upstream_received, 'upstream_receivable': st['upstream_receivable'],
                'new_declaration': declaration, 'old_payable_paid': old['payable'],
                'cash_paid': cash_paid, 'closing_payable': st['payable'],
                'new_statutory_reserve': legal_addition, 'bond_interest': interest,
                'per_share_cash_ex_opening_claim': cash_paid/st['shares'],
                'gross_core_profit_for_tail_bound': gross_core_profit,
                'entities': results, 'sale_loss': total_sale_loss})
            emit_checkpoint(checkpoint, 'year_completed', {'year': year, 'state': dict(st),
                'entities': {name: dict(value) for name, value in entities.items()}, 'row': rows[-1]})
        k, n, horizon = s['k'], st['shares'], c['horizon_years']
        opening_pv = initial['opening_claim']/(1.0+k)**(o['opening_payment_days']/365.0)
        a_lower = opening_pv+sum(r['per_share_cash_ex_opening_claim']/(1.0+k)**r['year'] for r in rows)
        # An upper bound, not an extra central valuation: all positive equity and pending claim
        # available at T, plus future positive operating earnings with zero reinvestment/cost needs.
        tail_upper_at_horizon = (max(st['book'], 0.0)+st['payable']+
            rows[-1]['gross_core_profit_for_tail_bound']*(1.0+s['long_growth'])/(k-s['long_growth']))/n
        tail_pv = tail_upper_at_horizon/(1.0+k)**horizon
        y5_lower = sum(r['per_share_cash_ex_opening_claim']/(1.0+k)**(r['year']-5) for r in rows if r['year'] > 5)
        y5_tail = tail_upper_at_horizon/(1.0+k)**(horizon-5)
        d = [r['per_share_cash_ex_opening_claim'] for r in rows[:5]]
        d[0] += initial['opening_claim']
        # Exact identity uses the known six-day opening claim separately from the annual approximation.
        early_pv = opening_pv+sum(rows[i]['per_share_cash_ex_opening_claim']/(1.0+k)**(i+1) for i in range(5))
        close(a_lower, early_pv+y5_lower/(1.0+k)**5, 'D1-5 and Y5 lower time identity')
        return {'initial': initial, 'rows': rows, 'method_A_current': [a_lower, a_lower+tail_pv],
                'D1_to_D5': d, 'Y5': [y5_lower, y5_lower+y5_tail],
                'tail_current_width': tail_pv, 'tail_Y5_width': y5_tail,
                'known_opening_claim_present_value': opening_pv,
                'discounted_annual_other_D1_to_D5': early_pv-opening_pv,
                'tail_is_bound_not_added_twice': True}

    except BaseException as original:
        scope = locals()
        failure_year = scope.get('year', 0)
        phase = 'opening_funding' if 'initial' not in scope else 'forecast_or_tail'
        if isinstance(original, EconomicBudgetInfeasible):
            original.details['year'] = failure_year
            original.details['phase'] = phase
        names = ('st', 'old', 'initial', 'entities', 'rows', 'results', 'cash_before_new',
                 'pool', 'mother_profit', 'group_profit', 'declaration', 'legal_room',
                 'group_cap_room', 'liquidity_room', 'planned_decl', 'mother_profit_before_sale',
                 'group_profit_before_sale', 'upstream_declared', 'upstream_received')
        payload = {'year': failure_year, 'phase': phase,
                   'exception_type': type(original).__name__, 'message': str(original),
                   'original_traceback': traceback.format_exc(),
                   'economic_details': original.details if isinstance(original, EconomicBudgetInfeasible) else None,
                   'last_available_locals': {name: scope[name] for name in names if name in scope}}
        preserve_failure(checkpoint, 'forecast_failure', payload, original)
        raise


def franchise_value(nbv, growth, discount, full_years, zero_year, long_growth=None):
    total = 0.0
    annual = []
    scale = 1.0
    if long_growth is None:
        long_growth = growth
    for year in range(1, zero_year):
        advantage = 1.0 if year <= full_years else (zero_year-year)/(zero_year-full_years)
        if year > 1:
            scale *= 1.0+(growth if year <= full_years else long_growth)
        cohort_value = nbv*scale*advantage
        pv = cohort_value/(1.0+discount)**year
        total += pv
        annual.append({'year': year, 'cohort_npv_net_acquisition_and_capital': cohort_value,
                       'competitive_advantage': advantage, 'present_value': pv})
    return total, annual


def sotp(inputs, s, initial):
    o, c = inputs['observed'], inputs['common_forecast']
    w, k = ownership(o), s['k']
    # Economic net-asset allocation, not an assertion about statutory carrying cost.
    pc_core_book = (o['pc_book_h126']-o['life_via_pc']*o['life_book_h126']
                   -o['health_via_pc']*o['health_book_h126']-o['re_via_pc']*o['re_book_h126'])
    pc_profit = o['pc_service_fy25']*(1.0-s['pc_cor'])*(1.0-c['pc_tax'])+s['pc_net_investment_budget']
    pc_premium = 0.0
    pc_rows = []
    fade_year = c['sotp_pc_competitive_fade_years']
    scale = 1.0
    for year in range(1, fade_year+1):
        growth = s['pc_growth'] if year <= 5 else s['long_growth']
        if year > 1:
            scale *= 1.0+growth
        income = pc_profit*scale
        capital = pc_core_book*scale
        advantage = max(0.0, (fade_year-year)/(fade_year-1))
        residual = (income-k*capital)*advantage
        pv = residual/(1.0+k)**year
        pc_premium += pv
        pc_rows.append({'year': year, 'ordinary_profit': income, 'capital': capital,
                        'residual': residual, 'competitive_advantage': advantage, 'pv': pv})
    life_health = {}
    adjustment = w['pc']*pc_premium
    for name in ('life', 'health'):
        case = s['ev_rate_case']
        vif_key = name+'_vif_'+case
        nbv_key = name+'_nbv_h126' if case == 'base' else name+'_nbv_'+case
        vif = o[vif_key]*s['vif_execution_factor']
        forward_nbv = o[nbv_key]*c['nbv_h1_to_forward_year_factor']*s['nbv_execution_factor']
        future, future_rows = franchise_value(forward_nbv, s[name+'_growth'], k,
            c['nbv_full_advantage_years'], c['nbv_zero_advantage_year'], s['long_growth'])
        value = o[name+'_anav_h126']+vif+future
        premium = value-o[name+'_book_h126']
        adjustment += w[name]*premium
        life_health[name] = {'anav': o[name+'_anav_h126'], 'vif': vif,
            'future_new_business_franchise': future, 'full_entity_value': value,
            'ordinary_book_removed_from_adjustment': o[name+'_book_h126'],
            'ultimate_parent_fraction': w[name], 'value_minus_book_adjustment': w[name]*premium,
            'future_cohorts': future_rows}
    # Book base already deducts parent debt. Only uncovered holding operating cost is capitalized.
    parent_cost_pv = c['mother_operating_cost']/(k-c['sotp_parent_cost_growth'])
    total_ordinary = initial['book']+adjustment-parent_cost_pv
    opening_pv = initial['opening_claim']/(1.0+k)**(o['opening_payment_days']/365.0)
    return {'method_B_current_per_share': total_ordinary/initial['shares']+opening_pv,
            'ordinary_book_base_after_issue_and_oneoff_losses': initial['book'],
            'pc_pure_capital_proxy': pc_core_book, 'pc_franchise_adjustment': w['pc']*pc_premium,
            'pc_residual_rows': pc_rows, 'life_health': life_health,
            'holding_operating_cost_value': parent_cost_pv,
            'opening_old_share_claim_present_value': opening_pv,
            'total_ordinary_ex_opening_claim': total_ordinary,
            'complete_future_new_business_method': True,
            'no_parent_bond_principal_or_interest_double_deduction': True}


def validate_inputs(inputs):
    c = inputs['common_forecast']
    if c['horizon_years'] != 80 or c['reported_years'] != 5:
        raise ValueError('unreviewed horizon')
    for s in inputs['scenarios'].values():
        if not s['k'] > max(s['long_growth'], c['sotp_parent_cost_growth'], s['surplus_yield']):
            raise ValueError('discount does not exceed growth/yield')
    if c['nbv_zero_advantage_year'] <= c['nbv_full_advantage_years']:
        raise ValueError('franchise fade invalid')


def run_all(inputs, recorder=None):
    validate_inputs(inputs)
    cases = {}
    for scenario_name, scenario in inputs['scenarios'].items():
        for financing_name, financing in inputs['financing_branches'].items():
            key = scenario_name+'__'+financing_name
            a = None
            b = None
            checkpoint = None
            try:
                if recorder is not None:
                    recorder.case_started(key, {'scenario': scenario_name, 'financing': financing_name})
                    checkpoint = recorder.checkpoint_for(key)
                a = forecast(inputs, scenario, financing, checkpoint=checkpoint)
                emit_checkpoint(checkpoint, 'method_A_completed', {'A': a})
                b = sotp(inputs, scenario, a['initial'])
                cases[key] = {'scenario': scenario_name, 'financing': financing_name,
                              'status': 'success', 'A': a, 'B': b, 'current_method_gap':
                              [b['method_B_current_per_share']-v for v in a['method_A_current']]}
                if recorder is not None:
                    recorder.case_finished(key, cases[key])
            except EconomicBudgetInfeasible as original:
                # A failed persistence operation makes even an economic failure a failed run.
                # The original economic exception remains primary, with the secondary I/O note.
                if original.partial_persistence_failed:
                    raise
                failed_case = {'scenario': scenario_name, 'financing': financing_name,
                    'status': 'economic_infeasible', 'A': None, 'B': None,
                    'current_method_gap': None, 'constraint': original.details,
                    'reason': str(original), 'source_gap': False,
                    'not_company_wide_null': True, 'retry_authorized': False}
                try:
                    if recorder is not None:
                        recorder.case_finished(key, failed_case)
                    cases[key] = failed_case
                except BaseException as cache_error:
                    original.add_note('Economic-case persistence failed: '+repr(cache_error))
                    original.partial_persistence_failed = True
                    raise original from None
            except BaseException as original:
                payload = {'exception_type': type(original).__name__, 'message': str(original),
                           'original_traceback': traceback.format_exc(),
                           'already_completed_case_names': list(cases),
                           'A_if_completed': a, 'B_if_completed': b}
                preserve_failure(checkpoint, 'case_technical_failure', payload, original)
                raise
    return {'symbol': inputs['symbol'], 'cutoff': inputs['cutoff'], 'cases': cases,
            'not_an_accepted_report': True, 'no_current_market_price': True,
            'no_probability_weighting_or_trade_authorization': True}
