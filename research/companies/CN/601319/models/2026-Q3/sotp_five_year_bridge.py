"""Finite saved-state adapter. Import defines functions only; no original forecast import."""
import math
import traceback


class EconomicBridgeIncompatible(Exception):
    """Only the prewritten insurance-emergence versus carried-VIF constraint."""
    def __init__(self, message, *, entity, year, available, emergence, details):
        super().__init__(message)
        self.details = {'constraint': 'insurance_emergence_within_carried_vif',
            'entity': entity, 'year': year, 'available_carried_vif': available,
            'insurance_emergence': emergence, **details}
        self.partial_persistence_failed = False


def close(actual, expected, label, tol=1e-9):
    if not math.isfinite(actual) or not math.isfinite(expected):
        raise AssertionError(label+': nonfinite')
    if abs(actual-expected) > tol*max(1.0, abs(actual), abs(expected)):
        raise AssertionError(f'{label}: {actual!r} != {expected!r}')


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('nonfinite or nonnumeric input: '+label)
    return value


def emit(checkpoint, kind, payload):
    if checkpoint is not None:
        checkpoint(kind, payload)


def preserve(checkpoint, kind, payload, original):
    try:
        emit(checkpoint, kind, payload)
    except BaseException as cache_error:
        original.add_note('Partial persistence failure; original retained: '+repr(cache_error))
        original.partial_persistence_failed = True


def issue_terms(pre_book, old_shares, cash, new_shares, mother_re):
    for name, value in locals().copy().items():
        finite(value, name)
    if old_shares <= 0 or cash < 0 or new_shares < 0 or ((cash == 0) != (new_shares == 0)):
        raise ValueError('unlinked cash and shares')
    return {'book': pre_book+cash, 'shares': old_shares+new_shares,
            'mother_re': mother_re, 'capital_cash': cash}


def ownership(o):
    return {'pc': o['pc_direct'],
        'life': o['life_direct']+o['life_via_asset']+o['pc_direct']*o['life_via_pc'],
        'health': o['health_direct']+o['health_via_holdco']+o['pc_direct']*o['health_via_pc']}


def cohort_step(anav, cas, cohorts, profit, declaration, new_nbv, unwind, anav_yield,
                strategic_profit_x=0.0, entity='fixture', year=1):
    for name, value in {'anav': anav, 'cas': cas, 'profit': profit, 'declaration': declaration,
            'new_nbv': new_nbv, 'unwind': unwind, 'anav_yield': anav_yield,
            'strategic_profit_x': strategic_profit_x}.items():
        finite(value, name)
    if declaration < 0 or new_nbv < 0 or unwind < 0 or anav_yield < 0:
        raise ValueError('unreviewed negative bridge input')
    if str(year) in cohorts:
        raise ValueError('new cohort origin already exists')
    if any(finite(v, 'cohort') < 0 for v in cohorts.values()):
        raise ValueError('negative starting cohort')
    capital_income = anav*anav_yield
    emergence = profit-capital_income-strategic_profit_x
    carried = {q: v*(1.0+unwind) for q, v in cohorts.items()}
    available = sum(carried.values())
    if emergence < 0 or emergence > available:
        raise EconomicBridgeIncompatible('Normal ordinary profit is incompatible with the stated aggregate VIF bridge',
            entity=entity, year=year, available=available, emergence=emergence,
            details={'ordinary_profit': profit, 'capital_income': capital_income,
                     'strategic_profit_x': strategic_profit_x, 'anav_before': anav,
                     'cas_before': cas, 'cohorts_before': cohorts,
                     'unwind': unwind, 'anav_yield': anav_yield, 'new_nbv_not_yet_added': new_nbv})
    # Exact zero branch: no 0/0 and no invented existing-business realization.
    if available == 0:
        ending_old = {q: 0.0 for q in carried}
        realized = {q: 0.0 for q in carried}
    else:
        # Algebraically proportional deduction; nonnegative remainder is not a clamp.
        remaining_total = available-emergence
        ending_old = {q: remaining_total*(value/available) for q, value in carried.items()}
        realized = {q: carried[q]-ending_old[q] for q in carried}
    ending = dict(ending_old)
    ending[str(year)] = new_nbv
    anav_after, cas_after = anav+profit-declaration, cas+profit-declaration
    close(sum(realized.values()), emergence, 'cohort realization total')
    close(sum(ending.values()), available-emergence+new_nbv, 'aggregate VIF roll')
    close(anav_after-cas_after, anav-cas, 'ANAV minus CAS')
    close((anav_after+sum(ending.values()))-(anav+sum(cohorts.values())),
          capital_income+strategic_profit_x+unwind*sum(cohorts.values())+new_nbv-declaration,
          'economic EV change')
    return {'year': year, 'entity': entity, 'anav_before': anav, 'cas_before': cas,
        'cohorts_before': dict(cohorts), 'profit': profit, 'declaration': declaration,
        'capital_income': capital_income, 'strategic_profit_x': strategic_profit_x,
        'insurance_emergence': emergence, 'carried_cohorts': carried,
        'carried_total': available, 'realized_by_cohort': realized,
        'new_nbv_added_at_year_end': new_nbv, 'anav_after': anav_after, 'cas_after': cas_after,
        'cohorts_after': ending, 'vif_after': sum(ending.values())}


def new_business_schedule(nbv_first, growth, long_growth, full_years=5, zero_year=15):
    if zero_year <= full_years or full_years < 1:
        raise ValueError('invalid absolute competitive calendar')
    scale, rows = 1.0, []
    for year in range(1, zero_year):
        if year > 1:
            scale *= 1.0+(growth if year <= full_years else long_growth)
        advantage = 1.0 if year <= full_years else (zero_year-year)/(zero_year-full_years)
        rows.append({'year': year, 'cohort_npv': nbv_first*scale*advantage,
                     'competitive_advantage': advantage})
    return rows


def future_franchise(schedule, anchor_year, ke):
    rows = [{'year': r['year'], 'cohort_npv': r['cohort_npv'],
             'pv_at_anchor': r['cohort_npv']/(1.0+ke)**(r['year']-anchor_year)}
            for r in schedule if r['year'] > anchor_year]
    return {'value': sum(r['pv_at_anchor'] for r in rows), 'rows': rows}


def segment_adjustment(anav, vif, franchise, cas, fraction):
    return fraction*(anav+vif+franchise-cas)


def pc_remaining(capital_at_zero, actual_scale5, actual_core_profit5, growth, ke, zero_year=15):
    rows = []
    for year in range(6, zero_year+1):
        scale = (1.0+growth)**(year-5)
        income = actual_core_profit5*scale
        capital = capital_at_zero*actual_scale5*scale
        advantage = max(0.0, (zero_year-year)/(zero_year-1))
        residual = (income-ke*capital)*advantage
        rows.append({'year': year, 'core_profit': income, 'necessary_capital': capital,
            'advantage_on_original_calendar': advantage, 'residual': residual,
            'pv_at_5': residual/(1.0+ke)**(year-5)})
    return {'value': sum(r['pv_at_5'] for r in rows), 'rows': rows,
            'surplus_financial_income_added': 0.0}


def terminal_rights(book5, adjustments, holding_cost_value, incremental_obligations,
                    shares5, declared_payable5, ke, payment_lag=1):
    if shares5 <= 0 or declared_payable5 < 0 or payment_lag <= 0:
        raise ValueError('invalid ordinary rights')
    ex_pending = book5+sum(adjustments.values())-holding_cost_value-incremental_obligations
    pending_pv = declared_payable5/(1.0+ke)**payment_lag
    return {'book5_after_all_declarations': book5, 'adjustments': adjustments,
        'holding_operating_cost_value5': holding_cost_value,
        'incremental_unbooked_obligation_value5': incremental_obligations,
        'ordinary_equity_ex_pending5': ex_pending, 'declared_payable5': declared_payable5,
        'pending_holder_claim_value5': pending_pv, 'shares5': shares5,
        'ordinary_share_ex_pending5': ex_pending/shares5,
        'holder_terminal_per_share5': (ex_pending+pending_pv)/shares5}


def present_from_distributions(distributions, opening_claim, opening_days, terminal5, ke):
    if len(distributions) != 5:
        raise ValueError('exactly five saved distributions required')
    other = list(distributions)
    other[0] -= opening_claim
    opening_pv = opening_claim/(1.0+ke)**(opening_days/365.0)
    annual_pv = sum(d/(1.0+ke)**(i+1) for i, d in enumerate(other))
    terminal_pv = terminal5/(1.0+ke)**5
    current = opening_pv+annual_pv+terminal_pv
    annual_convention = sum(d/(1.0+ke)**(i+1) for i, d in enumerate(distributions))
    known_date_correction = opening_pv-opening_claim/(1.0+ke)
    close(current, annual_convention+known_date_correction+terminal_pv,
          'same rights D and T5 current-time identity')
    return {'current_per_share': current, 'known_old_claim_pv': opening_pv,
        'other_D1_to_D5_pv': annual_pv, 'T5_present_value': terminal_pv,
        'known_claim_actual_date_correction': known_date_correction,
        'D1_to_D5': list(distributions), 'T5_per_share': terminal5,
        'terminal_present_value_fraction': terminal_pv/current if current != 0 else None}


def validate_scope(config, inputs, saved, states):
    if config['task_id'] != inputs['task_id'] or config['cutoff'] != inputs['cutoff']:
        raise ValueError('task or cutoff mismatch')
    if config['saved_case'] != 'central__not_completed' or config['years_reused'] != 5:
        raise ValueError('unreviewed saved scope')
    if saved['status'] != 'success' or saved['scenario'] != 'central' or saved['financing'] != 'not_completed':
        raise ValueError('saved case not successful reviewed base')
    initial = saved['A']['initial']
    if initial['issue_cash'] != 0 or initial['new_shares'] != 0:
        raise ValueError('only not-completed financing base authorized')
    linked = issue_terms(initial['book']-initial['issue_cash'], initial['old_shares'],
                         initial['issue_cash'], initial['new_shares'], initial['mother_re'])
    close(initial['book'], linked['book'], 'linked opening capital')
    close(initial['shares'], linked['shares'], 'linked ordinary shares')
    close(initial['mother_re'], linked['mother_re'], 'issue does not create RE')
    if [r['year'] for r in saved['A']['rows'][:5]] != [1, 2, 3, 4, 5]:
        raise ValueError('missing or unordered saved five years')
    if sorted(states) != [1, 2, 3, 4, 5]:
        raise ValueError('missing saved entity state')
    for row in saved['A']['rows'][:5]:
        if states[row['year']]['row'] != row:
            raise AssertionError('saved annual state and model result differ')
        close(states[row['year']]['state']['book'], row['group_book'], 'saved book consistency')
    combos = config['combinations']
    if len(combos) != 11 or len({x['id'] for x in combos}) != 11:
        raise ValueError('finite grid count or ids changed')
    corners = [x for x in combos if x['role'] == 'core_corner']
    expected = {(k, anchor, r) for k in (0.095, 0.115)
                for anchor, rates in [('original', (0.075, 0.085)), ('plus100bp', (0.085, 0.095))]
                for r in rates}
    if {(x['ke'], x['ev_anchor'], x['unwind']) for x in corners} != expected or len(corners) != 8:
        raise ValueError('prewritten core corners changed')
    for x in combos:
        anchor = config['ev_anchors'][x['ev_anchor']]
        if not anchor['unwind_low'] <= x['unwind'] <= anchor['unwind_high']:
            raise ValueError('EV anchor and unwind rate not synchronized')
        if x['role'] == 'core_corner' and x['anav_yield'] != 0.025:
            raise ValueError('ANAV diagnostic silently mixed into core')
    centers = [x for x in combos if x['role'] == 'center']
    diagnostics = [x for x in combos if x['role'] == 'anav_income_diagnostic']
    if len(centers) != 1 or len(diagnostics) != 2:
        raise ValueError('center/diagnostic count changed')
    for x in centers+diagnostics:
        if (x['ke'], x['ev_anchor'], x['unwind']) != (0.105, 'original', 0.08):
            raise ValueError('income diagnostics alter another parameter')
    if centers[0]['anav_yield'] != 0.025 or {x['anav_yield'] for x in diagnostics} != {0.02, 0.03}:
        raise ValueError('ANAV income split range changed')


def bridge_case(config, combination, inputs, saved, states, checkpoint=None):
    o, c, s = inputs['observed'], inputs['common_forecast'], inputs['scenarios']['central']
    anchor = config['ev_anchors'][combination['ev_anchor']]
    ke = combination['ke']
    weights = ownership(o)
    all_entity_results = {}
    rows5 = saved['A']['rows'][:5]
    try:
        for name in ('life', 'health'):
            anav, cas = o[name+'_anav_h126'], o[name+'_book_h126']
            cohorts = {'0': anchor[name]['vif']}
            first_nbv = anchor[name]['h1_nbv']*c['nbv_h1_to_forward_year_factor']*s['nbv_execution_factor']
            schedule = new_business_schedule(first_nbv, s[name+'_growth'], s['long_growth'],
                c['nbv_full_advantage_years'], c['nbv_zero_advantage_year'])
            if combination['ev_anchor'] == 'original':
                old_schedule = saved['B']['life_health'][name]['future_cohorts']
                if len(old_schedule) != len(schedule):
                    raise AssertionError('original future NBV schedule length differs')
                for old, new in zip(old_schedule, schedule):
                    if old['year'] != new['year']:
                        raise AssertionError('original NBV calendar differs')
                    close(old['cohort_npv_net_acquisition_and_capital'], new['cohort_npv'], 'original net NBV schedule')
            entity_rows = []
            for row in rows5:
                year = row['year']
                emit(checkpoint, 'entity_year_begin', {'entity': name, 'year': year,
                    'anav': anav, 'cas': cas, 'cohorts': dict(cohorts),
                    'saved_entity_row': row['entities'][name], 'parameters': combination,
                    'new_nbv': schedule[year-1]['cohort_npv']})
                step = cohort_step(anav, cas, cohorts, row['entities'][name]['profit'],
                    row['entities'][name]['dividend'], schedule[year-1]['cohort_npv'],
                    combination['unwind'], combination['anav_yield'],
                    config['separately_valued_strategic_profit_X'][name], name, year)
                entity_rows.append(step)
                anav, cas, cohorts = step['anav_after'], step['cas_after'], step['cohorts_after']
                emit(checkpoint, 'entity_year_completed', step)
            future = future_franchise(schedule, 5, ke)
            value_adjustment = segment_adjustment(anav, sum(cohorts.values()), future['value'], cas, weights[name])
            all_entity_results[name] = {'rows': entity_rows, 'anav5': anav, 'cas5': cas,
                'remaining_original_cohort_proxy5': cohorts['0'],
                'remaining_new_cohorts_proxy5': {q: v for q, v in cohorts.items() if q != '0'},
                'vif5': sum(cohorts.values()), 'future_new_business_after5': future,
                'ultimate_fraction': weights[name], 'value_minus_book_adjustment5': value_adjustment,
                'full_entity_economic_value5': anav+sum(cohorts.values())+future['value'],
                'capital_income_sum5': sum(r['capital_income'] for r in entity_rows),
                'insurance_emergence_sum5': sum(r['insurance_emergence'] for r in entity_rows)}
            emit(checkpoint, 'entity_completed', {'entity': name, 'result': all_entity_results[name]})
        capital0 = (o['pc_book_h126']-o['life_via_pc']*o['life_book_h126']
                    -o['health_via_pc']*o['health_book_h126']-o['re_via_pc']*o['re_book_h126'])
        close(capital0, saved['B']['pc_pure_capital_proxy'], 'pure PC capital original allocation')
        row5 = rows5[-1]
        pc = pc_remaining(capital0, states[5]['entities']['pc']['scale'],
                          row5['entities']['pc']['core_profit'], s['long_growth'], ke,
                          c['sotp_pc_competitive_fade_years'])
        adjustments = {'pc': weights['pc']*pc['value'],
            'life': all_entity_results['life']['value_minus_book_adjustment5'],
            'health': all_entity_results['health']['value_minus_book_adjustment5']}
        if ke <= c['sotp_parent_cost_growth']:
            raise ValueError('equity cost below holding cost growth')
        holding_cost = c['mother_operating_cost']*(1.0+c['sotp_parent_cost_growth'])**5/(ke-c['sotp_parent_cost_growth'])
        incremental_obligations = (config['debt_economic_value_minus_book_at_year5']+
                                    config['additional_unbooked_obligation_value_at_year5'])
        terminal = terminal_rights(row5['group_book'], adjustments, holding_cost, incremental_obligations,
            states[5]['state']['shares'], row5['closing_payable'], ke, config['pending_payment_lag_years'])
        current = present_from_distributions(saved['A']['D1_to_D5'], saved['A']['initial']['opening_claim'],
            o['opening_payment_days'], terminal['holder_terminal_per_share5'], ke)
        result = {'status': 'success', 'parameters': combination, 'life_health': all_entity_results,
            'pc_remaining': pc, 'terminal_bridge': terminal, 'current_bridge': current,
            'saved_group_book5': row5['group_book'], 'saved_mother_re5': row5['mother_re'],
            'saved_cash5': row5['mother_cash'], 'saved_liquid_pool5': row5['mother_liquid_pool'],
            'original_direct_B_current_central_anchor_only': saved['B']['method_B_current_per_share'],
            'original_A_policy_only': saved['A']['method_A_current'],
            'economic_acceptance': False}
        emit(checkpoint, 'combination_calculation_completed', {'result': result})
        return result
    except BaseException as original:
        scope = locals()
        preserve(checkpoint, 'combination_failure', {'exception_type': type(original).__name__,
            'message': str(original), 'traceback': traceback.format_exc(),
            'economic_details': getattr(original, 'details', None),
            'last_available': {n: scope[n] for n in ('name', 'year', 'anav', 'cas', 'cohorts', 'entity_rows',
                'all_entity_results', 'pc', 'terminal', 'current') if n in scope}}, original)
        raise


def run_all(config, inputs, saved, states, recorder):
    validate_scope(config, inputs, saved, states)
    results = {}
    for combination in config['combinations']:
        key = combination['id']
        checkpoint = recorder.start(key, combination)
        try:
            result = bridge_case(config, combination, inputs, saved, states, checkpoint)
            recorder.finish(key, result)
            results[key] = result
        except EconomicBridgeIncompatible as original:
            if original.partial_persistence_failed:
                raise
            result = {'status': 'economic_bridge_incompatible', 'parameters': combination,
                'reason': str(original), 'constraint': original.details, 'current_bridge': None,
                'terminal_bridge': None, 'not_company_wide_null': True, 'retry_authorized': False}
            try:
                recorder.finish(key, result)
                results[key] = result
            except BaseException as cache_error:
                original.add_note('Economic failure persistence failed: '+repr(cache_error))
                raise original from None
        except BaseException as original:
            preserve(checkpoint, 'technical_failure', {'exception_type': type(original).__name__,
                'message': str(original), 'traceback': traceback.format_exc(),
                'previously_finished_ids': list(results)}, original)
            raise
    corner_ids = [x['id'] for x in config['combinations'] if x['role'] == 'core_corner']
    failed_corners = [key for key in corner_ids if results[key]['status'] != 'success']
    core = {'status': 'incomplete_grid_do_not_adopt' if failed_corners else 'complete_unaccepted_candidate_grid',
            'failed_corner_ids': failed_corners, 'current_range': None, 'year5_range': None}
    if not failed_corners:
        current_values = {key: results[key]['current_bridge']['current_per_share'] for key in corner_ids}
        terminal_values = {key: results[key]['terminal_bridge']['holder_terminal_per_share5'] for key in corner_ids}
        for label, values in [('current_range', current_values), ('year5_range', terminal_values)]:
            lo, hi = min(values, key=values.get), max(values, key=values.get)
            core[label] = {'low': values[lo], 'high': values[hi], 'low_combination': lo, 'high_combination': hi}
    return {'task_id': config['task_id'], 'symbol': config['symbol'], 'cutoff': config['cutoff'],
        'cases': results, 'core_grid': core, 'economic_acceptance': False,
        'D1_to_D5_unchanged_saved_base': saved['A']['D1_to_D5'],
        'ANAV_yield_is_new_whole_ANAV_proxy': True,
        'policy_A_not_core_and_no_ten_percent_release': True,
        'no_old_forecast_reexecution': True, 'failure_corner_not_silently_removed': True}
