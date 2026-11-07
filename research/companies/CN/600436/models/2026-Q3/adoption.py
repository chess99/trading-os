#!/usr/bin/env python3
"""Public, relative-path, standard-library adoption overlay. Explicit saved-cache reuse.

Reuses pinned healthy operating states/valuations; never replays the issuer's
inventory, project, or operating forecasts. Recomputes only parent/risk cash,
bounded RE capacity, and complete entity attribution. No private recorder shell.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

EPS = 1e-7


class TechnicalFailure(Exception):
    def __init__(self, message, partial=None):
        super().__init__(message)
        self.partial = partial


def need(condition, message):
    if not condition:
        raise TechnicalFailure(message)


def close(a, b, label):
    need(abs(a - b) <= EPS * max(1.0, abs(a), abs(b)), label)


def finite_tree(x):
    if isinstance(x, float):
        need(math.isfinite(x), 'Nonfinite financial input/output')
    elif isinstance(x, dict):
        for y in x.values():
            finite_tree(y)
    elif isinstance(x, list):
        for y in x:
            finite_tree(y)


def paths_by_name(cache):
    result = cache['result']
    paths = result['paths'] + result['discount_rate_diagnostics']
    mapping = {p['path']: p for p in paths}
    need(len(mapping) == len(paths), 'Duplicate cache path')
    return mapping


def risk_initial(config, cached, recourse_fraction):
    need(recourse_fraction in (0, 1), 'Selected recourse is zero or full same-principal bound')
    bank = cached['raw_initial_state']['units'][config['problem_unit']]['bank_debt']
    budget = config['support_loss_budget']
    need(bank >= 0 and budget >= 0, 'Negative principal or budget')
    return {'original_support_budget': budget, 'remaining_support_reserve': budget,
            'support_paid_total': 0.0, 'support_used_for_bank_principal': 0.0,
            'support_used_for_operating_or_integration': 0.0,
            'original_problem_bank_principal': bank, 'remaining_problem_bank_principal': bank,
            'creditor_realized_principal_recoveries': 0.0, 'extra_parent_bank_paid': 0.0,
            'recourse_fraction': recourse_fraction, 'remaining_extra_recourse_reserve': recourse_fraction * bank}


def risk_settle(risk, cash, event):
    """Only actual designated same-principal payments reduce external principal."""
    before = copy.deepcopy(risk)
    r = copy.deepcopy(risk)
    op, bank, recovery, direct = [event[k] for k in ('support_operating', 'support_bank_principal', 'creditor_bank_recovery', 'extra_parent_bank_payment')]
    need(all(x >= 0 for x in (op, bank, recovery, direct)), 'Negative settlement')
    support = op + bank
    need(support <= r['remaining_support_reserve'] + EPS, 'Support budget exceeded: no automatic replenishment')
    need(bank + recovery <= r['remaining_problem_bank_principal'] + EPS, 'Same bank principal over-repaid')
    r['remaining_support_reserve'] -= support
    r['support_paid_total'] += support
    r['support_used_for_bank_principal'] += bank
    r['support_used_for_operating_or_integration'] += op
    r['creditor_realized_principal_recoveries'] += recovery
    r['remaining_problem_bank_principal'] -= bank + recovery
    q_before_direct = r['recourse_fraction'] * r['remaining_problem_bank_principal']
    need(direct <= q_before_direct + EPS, 'Direct recourse payment exceeds same outstanding assumed claim')
    r['extra_parent_bank_paid'] += direct
    r['remaining_problem_bank_principal'] -= direct
    r['remaining_extra_recourse_reserve'] = r['recourse_fraction'] * r['remaining_problem_bank_principal']
    after_cash = cash - support - direct
    close(r['support_paid_total'] + r['remaining_support_reserve'], r['original_support_budget'], 'One support budget paid + remaining')
    close(r['remaining_problem_bank_principal'] + r['support_used_for_bank_principal'] + r['creditor_realized_principal_recoveries'] + r['extra_parent_bank_paid'], r['original_problem_bank_principal'], 'Same external principal roll-forward; no legal writeoff')
    before_net = cash - before['remaining_support_reserve'] - before['remaining_extra_recourse_reserve']
    after_net = after_cash - r['remaining_support_reserve'] - r['remaining_extra_recourse_reserve']
    # Operating support never frees bank recourse. Same-bank payment/recovery can.
    close(after_net - before_net, r['recourse_fraction'] * (bank + recovery), 'Cash/reserve/recourse deduplication')
    if bank == 0 and recovery == 0 and direct == 0:
        close(r['remaining_problem_bank_principal'], before['remaining_problem_bank_principal'], 'Operating support is not bank repayment')
    return r, after_cash, {'event': copy.deepcopy(event), 'cash_before_settlement': cash,
                          'cash_after_settlement': after_cash, 'risk_before': before,
                          'risk_after': copy.deepcopy(r), 'net_cash_before': before_net, 'net_cash_after': after_net,
                          'support_is_not_a_second_deduction_from_reserved_net_cash': True}


def maximum_total_parent_loss(risk):
    # Actual parent recourse payments + the remaining same-principal claim;
    # support-bank payments reduce only remaining recourse, not the 200 budget.
    return risk['original_support_budget'] + risk['extra_parent_bank_paid'] + risk['remaining_extra_recourse_reserve']


def validate_profile(config, operating, cached, profile):
    n = operating['horizon']
    need(len(cached['raw_periods']) == n, 'Cached horizon mismatch')
    need(len(profile['settlements']) == n, 'Settlement schedule length')
    need(config['parent_unit'] == 'manufacturing', 'Unexpected parent operating bucket')
    need(config['problem_unit'] in cached['raw_initial_state']['units'], 'Problem unit absent')
    need(profile['recourse_fraction'] in (0, 1), 'Unapproved fractional recourse policy')
    finite_tree(config)
    for i, row in enumerate(cached['raw_periods'], 1):
        need(row['period'] == i, 'Nonsequential cached periods')
        need(config['parent_unit'] in row['units'] and config['problem_unit'] in row['units'], 'Cached unit missing')
    need(operating['shares'] > 0, 'Shares must be positive')


def parent_replay(config, operating, cached, profile):
    """Only parent cash/distribution/risk ledger changes; healthy budgets are inputs.

    C is projected parent surplus cash, excluding its already retained operating
    buffer. R is the remaining fixed support budget; Q is the distinct same-bank
    recourse reserve. C-R-Q is used by both D and equity bridges. Reserved cash has
    zero adopted yield; no interest or loan recovery is created by the reserve.
    """
    states, rows, constraints = [], [], []
    completed_constraint_count = 0
    failure_stage, failure_period = 'parent_initialization', None
    try:
        validate_profile(config, operating, cached, profile)
        parent, problem = config['parent_unit'], config['problem_unit']
        initial = cached['raw_initial_state']
        cash = initial['units'][parent]['surplus_cash']
        risk = risk_initial(config, cached, profile['recourse_fraction'])
        re_reference = initial['parent_re']
        statutory = initial['statutory_reserve']
        discretionary = initial.get('other_reserve', 0.0)
        state = {'parent_cash_C': cash, 'risk': copy.deepcopy(risk),
                 'parent_disposable_cash_C_minus_R_minus_Q': cash - risk['remaining_support_reserve'] - risk['remaining_extra_recourse_reserve'],
                 'parent_RE_reference_before_support_recognition': re_reference,
                 'parent_RE_lower_bound_after_all_budget_losses': re_reference - maximum_total_parent_loss(risk),
                 'statutory_reserve_reference': statutory, 'discretionary_reserve_reference': discretionary}
        states, rows, constraints = [copy.deepcopy(state)], [], []
        dist = operating['distribution']
        path = next(p for p in operating['paths'] if p['name'] == 'base')
        cash_yield = path['after_tax_cash_interest_rate']
        old_cash_open = cash
        for i, old in enumerate(cached['raw_periods']):
            t = i + 1
            failure_stage, failure_period = 'parent_period', t
            cash_open = cash
            risk_open = copy.deepcopy(risk)
            old_interest = old['units'][parent]['financial_cash_interest']
            old_loan = old['support_loan_waterfall']
            old_loan_cash = old_loan['interest_paid'] + old_loan['principal_paid'] - old_loan['parent_interest_tax'] - old_loan['draw']
            old_problem_up = old['units'][problem]['parent_upstream']
            old_after_up = old['parent_cash_timing']['parent_surplus_after_upstream_before_holder_payment']
            # This reuses all unaffected parent operating/project/financial-commitment
            # cash flows, restricted/term maturities and healthy subsidiary upstreams.
            # It explicitly strips every old problem-loan cash movement/upstream.
            independent_cash_flow = old_after_up - old_cash_open - old_interest - old_loan_cash - old_problem_up
            independent_profit = old['parent_profit'] - old_interest - old_loan['parent_profit_addition'] - old_problem_up
            healthy_upstream = old['subsidiary_upstream'] - old_problem_up
            disposable_open = cash - risk['remaining_support_reserve'] - risk['remaining_extra_recourse_reserve']
            adopted_interest = max(0.0, disposable_open) * cash_yield
            cash += independent_cash_flow + adopted_interest
            risk, cash, settlement = risk_settle(risk, cash, profile['settlements'][i])
            profit_reference = independent_profit + adopted_interest
            before_up_cash = cash - healthy_upstream
            r, q = risk['remaining_support_reserve'], risk['remaining_extra_recourse_reserve']
            net_before, net_after = before_up_cash - r - q, cash - r - q
            eligible = old['parent_cash_timing']['eligible_adjustable_new_capital_payments']
            timing_policy = operating['parent_cash_timing_policy']
            adopted_timing = bool(net_before < -EPS <= net_after and timing_policy['adopt_adjustable_capital_payments_after_available_upstream'] and not timing_policy['observed_conflicting_fixed_future_dates_in_read_sources'] and -net_before <= eligible + EPS)
            if cash < -EPS:
                constraints.append({'period': t, 'unit': parent, 'code': 'PARENT_ACTUAL_ANNUAL_CASH_SHORTFALL', 'shortfall': -cash, 'affects': ['main', 'auxiliary', 'distributions', 'terminal']})
            elif net_after < -EPS:
                constraints.append({'period': t, 'unit': parent, 'code': 'FINITE_RISK_RESERVE_NOT_FULLY_FUNDED_FOR_D', 'shortfall': -net_after, 'not_group_insolvency': True, 'affects': ['distributions', 'terminal']})
            elif net_before < -EPS and not adopted_timing:
                constraints.append({'period': t, 'unit': parent, 'code': 'RISK_NET_CASH_TIMING_CONDITION_UNADOPTED', 'affects': ['distributions', 'terminal']})
            current_reserve = max(0.0, profit_reference) * dist['statutory_reserve_ratio']
            pre_cutoff = max(0.0, operating['opening'].get('pre_cutoff_parent_profit_pending_annual_reserve', 0.0)) * dist['statutory_reserve_ratio'] if t == 1 else 0.0
            optional = max(0.0, profit_reference) * dist['discretionary_reserve_ratio']
            re_before_payment = re_reference + profit_reference - current_reserve - pre_cutoff - optional
            loss_bound = maximum_total_parent_loss(risk)
            re_lower_before_payment = re_before_payment - loss_bound
            # Stable normal-profit payout target; actual loss-recognition timing is
            # not claimed known. Its entire bounded RE impact is tested separately.
            requested = max(0.0, profit_reference) * dist['parent_payout_ratio']
            actual = min(requested, max(0.0, net_after), max(0.0, re_lower_before_payment))
            floor = max(0.0, profit_reference - current_reserve - optional) * dist['policy_floor_ratio']
            if actual + EPS < floor and not dist['allow_policy_exception']:
                constraints.append({'period': t, 'unit': parent, 'code': 'NORMAL_PROFIT_POLICY_FLOOR_REQUIRES_EXCEPTION', 'shortfall': floor - actual, 'affects': ['distributions', 'terminal']})
            cash_after_up_before_D = cash
            cash -= actual
            re_reference = re_before_payment - actual
            statutory += current_reserve + pre_cutoff
            discretionary += optional
            close(cash - cash_open, independent_cash_flow + adopted_interest - profile['settlements'][i]['support_operating'] - profile['settlements'][i]['support_bank_principal'] - profile['settlements'][i]['extra_parent_bank_payment'] - actual, 'Actual parent cash conservation')
            close(re_reference, states[-1]['parent_RE_reference_before_support_recognition'] + profit_reference - current_reserve - pre_cutoff - optional - actual, 'Reference RE roll-forward, not fictitious reserve expense')
            state = {'parent_cash_C': cash, 'risk': copy.deepcopy(risk),
                     'parent_disposable_cash_C_minus_R_minus_Q': cash - r - q,
                     'parent_RE_reference_before_support_recognition': re_reference,
                     'parent_RE_lower_bound_after_all_budget_losses': re_reference - loss_bound,
                     'statutory_reserve_reference': statutory, 'discretionary_reserve_reference': discretionary}
            close(old_after_up - old['parent_cash_timing']['parent_surplus_before_operating_subsidiary_upstream'], old['subsidiary_upstream'], 'Cached upstream identity')
            old_cash_open = old_after_up - old['actual_parent_distribution']
            if t == 5:
                close(old_cash_open, cached['raw_year5_state']['units'][parent]['surplus_cash'], 'Reconstructed old parent cash matches cached Y5 post-distribution state')
            rows.append({'period': t, 'from': old['from'], 'to': old['to'],
                         'reused_independent_parent_cash_flow': independent_cash_flow,
                         'reused_independent_parent_profit_before_parent_cash_interest': independent_profit,
                         'retired_problem_loan_cash_flow': old_loan_cash,
                         'retired_problem_loan_profit': old_loan['parent_profit_addition'],
                         'retired_problem_upstream': old_problem_up,
                         'healthy_subsidiary_upstream': healthy_upstream,
                         'adopted_parent_unreserved_cash_interest': adopted_interest,
                         'normal_profit_payout_reference_not_reported_GAAP_profit': profit_reference,
                         'settlement': settlement, 'cash_before_healthy_upstream': before_up_cash,
                         'cash_after_upstream_before_holder_payment': cash_after_up_before_D,
                         'disposable_before_upstream': net_before, 'disposable_after_upstream_before_payment': net_after,
                         'timing_dependency': net_before < -EPS, 'adopted_timing_condition': adopted_timing,
                         'does_not_certify_daily_liquidity': True, 'eligible_adjustable_capital': eligible,
                         'statutory_reserve_reference_addition': current_reserve + pre_cutoff,
                         'pre_cutoff_profit_reserve': pre_cutoff, 'optional_reserve_reference_addition': optional,
                         'maximum_same_budget_RE_loss_bound': loss_bound,
                         'RE_lower_bound_before_holder_payment': re_lower_before_payment,
                         'RE_loss_bound_binds_payout': re_lower_before_payment + EPS < min(requested, max(0.0, net_after)),
                         'requested_distribution': requested, 'actual_distribution': actual,
                         'post_distribution_state': copy.deepcopy(state)})
            states.append(copy.deepcopy(state))
            completed_constraint_count = len(constraints)
        failure_stage, failure_period = 'parent_final_consistency', None
        close(old_cash_open, cached['raw_periods'][-1]['parent_cash_timing']['parent_surplus_after_upstream_before_holder_payment'] - cached['raw_periods'][-1]['actual_parent_distribution'], 'Old policy cash reconstruction')
        return {'initial_state': states[0], 'states': states, 'periods': rows, 'constraints': constraints,
                'RE_method': 'Reference no-support-loss RE minus entire bounded same-budget losses; not a claim about booked impairment date. Higher reference statutory reserves are conservative; no loss-timing tax benefit.'}

    except Exception as exc:
        partial = {'failure_stage': failure_stage, 'failure_period': failure_period,
                   'completed_period_count': len(rows),
                   'last_completed_period': rows[-1]['period'] if rows else 0,
                   'initial_state': copy.deepcopy(states[0]) if states else None,
                   'last_completed_state': copy.deepcopy(states[-1]) if states else None,
                   'states': copy.deepcopy(states), 'periods': copy.deepcopy(rows),
                   'constraints': copy.deepcopy(constraints[:completed_constraint_count]),
                   'incomplete_period_constraints': copy.deepcopy(constraints[completed_constraint_count:]),
                   'incomplete_period_not_committed': failure_stage == 'parent_period'}
        raise TechnicalFailure('Parent ledger failed at ' + failure_stage + ' period=' + str(failure_period) + ': ' + str(exc), partial) from exc


RECOMPUTED_OLD_PARENT_POLICY_CODES = frozenset({
    'PARENT_ANNUAL_CASH_SHORTFALL_AFTER_ADOPTED_UPSTREAM',
    'PARENT_ANNUAL_NET_COVERED_BUT_TIMING_CONDITION_UNADOPTED',
    'PAYOUT_REQUIRES_UNADOPTED_POLICY_EXCEPTION',
})


def retired_parent_policy_constraint(constraint):
    return (constraint.get('unit') == 'listed_parent'
            and constraint.get('code') in RECOMPUTED_OLD_PARENT_POLICY_CODES)


def adopt_bridge(config, operating, cached, parent_state, method_name, at):
    """Rebuild from 100% components; retire the COMPLETE problem entity bucket."""
    method = cached[method_name]
    old_state = cached['raw_initial_state'] if at == 0 else cached['raw_year5_state']
    problem, parent = config['problem_unit'], config['parent_unit']
    unit_cfg = next(u for u in operating['units'] if u['id'] == problem)
    ev_key = 'ev' if method_name == 'raw_auxiliary_method' else 'full_group_unit_ev'
    nci_key = 'operating_nci_economic_value' if method_name == 'raw_auxiliary_method' else 'operating_nci_economic_equity'
    entity = method['units'][problem]
    problem_cash = old_state['units'][problem]['surplus_cash']
    problem_restricted = max(0.0, old_state['restricted_claim'] - operating['opening']['parent_restricted_cash_assumption']) * unit_cfg['nonparent_cash_share'] * 0.95
    problem_cash_nci = (problem_cash + problem_restricted) * (1 - unit_cfg['owner'])
    problem_owned_financial = problem_cash + problem_restricted - problem_cash_nci
    close(problem_cash_nci, entity['nci_details']['entity_financial_nci_already_in_asset_bridge'], 'Problem financial NCI matches same cash/restricted pool')
    old_bucket = entity[ev_key] - entity['bank_debt'] - entity[nci_key] + entity['limited_recourse_adjustment'] + problem_owned_financial
    close(old_bucket, entity['nci_details']['parent_entity_equity'], 'Complete old problem bucket identity')
    healthy = {k: copy.deepcopy(v) for k, v in method['units'].items() if k != problem}
    ev = sum(v[ev_key] for v in healthy.values())
    unallocated = method['unallocated_group_bank_debt_fully_retained']
    debt = sum(v['bank_debt'] for v in healthy.values()) + unallocated
    nci = sum(v[nci_key] for v in healthy.values())
    adjustments = sum(v['limited_recourse_adjustment'] for v in healthy.values())
    assets = copy.deepcopy(method['nonoperating_assets'])
    old_parent_cash = old_state['units'][parent]['surplus_cash']
    parent_delta = parent_state['parent_cash_C'] - old_parent_cash
    healthy_assets_before_risk = assets['attributable_net_assets'] - problem_owned_financial + parent_delta
    risk = parent_state['risk']
    r, q = risk['remaining_support_reserve'], risk['remaining_extra_recourse_reserve']
    healthy_assets_after_risk = healthy_assets_before_risk - r - q
    commitments = method['future_financial_commitment_net_value']
    value = ev - debt - nci + adjustments + healthy_assets_after_risk + commitments['value']
    # Counterfactual subtraction is only a check, not the construction algorithm.
    removed_loan_tax = method.get('parent_exclusive_loan_interest_tax_pv', 0.0)
    check = method['ordinary_equity_value'] - old_bucket + removed_loan_tax + parent_delta - r - q
    close(value, check, 'Whole-bucket replacement equals 100% rebuilt bridge; no leftover NCI/recourse gain')
    close(healthy_assets_before_risk - healthy_assets_after_risk, r + q, 'Risk preparation deducted once at this state')
    retained_constraints = [copy.deepcopy(x) for x in method.get('constraints', []) if x.get('unit') != problem and not retired_parent_policy_constraint(x)]
    retired_parent_constraints = [copy.deepcopy(x) for x in method.get('constraints', []) if retired_parent_policy_constraint(x)]
    return {'at_period': at, 'source_method': method_name, 'healthy_units': healthy,
            'healthy_EV': ev, 'healthy_external_bank_debt_including_unallocated': debt,
            'unallocated_group_bank_debt_fully_retained': unallocated,
            'healthy_operating_NCI': nci, 'healthy_limited_recourse_adjustments': adjustments,
            'financial_assets_bridge': {'source_attributable_assets': assets['attributable_net_assets'],
                'removed_problem_surplus_cash_gross': problem_cash,
                'removed_problem_restricted_value_gross': problem_restricted,
                'removed_problem_financial_NCI': problem_cash_nci,
                'removed_problem_owned_financial_cash': problem_owned_financial,
                'old_parent_surplus_cash': old_parent_cash, 'new_parent_cash_C': parent_state['parent_cash_C'],
                'parent_cash_replacement_delta': parent_delta,
                'healthy_attributable_assets_before_risk': healthy_assets_before_risk,
                'remaining_support_reserve_R': r, 'remaining_same_bank_recourse_Q': q,
                'healthy_attributable_assets_after_risk': healthy_assets_after_risk,
                'retained_external_financial_assets': assets['financial_assets']},
            'future_financial_commitments_preserved': commitments,
            'retired_problem_bucket': {'operating_EV_100percent': entity[ev_key], 'old_policy_bank_debt': entity['bank_debt'],
                'surplus_cash_gross': problem_cash, 'restricted_cash_value_gross': problem_restricted,
                'operating_NCI': entity[nci_key], 'financial_cash_NCI': problem_cash_nci,
                'old_limited_recourse_adjustment': entity['limited_recourse_adjustment'],
                'old_parent_loan_rights': entity['nci_details'].get('loan_rights'),
                'old_parent_loan_interest_tax_PV': removed_loan_tax,
                'whole_old_parent_contribution_before_exclusive_tax': old_bucket,
                'new_problem_ordinary_equity_recovery': 0.0, 'new_support_rights_recovery': 0.0,
                'no_legal_sale_or_debt_cancellation_claimed': True},
            'external_bank_disclosure_ledger': {'healthy_and_unallocated_principal': debt,
                'problem_original_proxy_principal': risk['original_problem_bank_principal'],
                'problem_remaining_same_principal': risk['remaining_problem_bank_principal'],
                'total_external_principal_under_new_adoption': debt + risk['remaining_problem_bank_principal'],
                'problem_principal_outside_healthy_equity_bridge_is_not_extinguished': True,
                'recourse_Q_is_incidence_of_same_principal_not_new_debt': True},
            'additional_bank_recourse_incidence_bound': {'remaining_recorded_principal': risk['remaining_problem_bank_principal'],
                'additional_loss_beyond_already_reserved_Q': risk['remaining_problem_bank_principal'] - q,
                'conditional_equity_after_full_same_principal_reserve': value - (risk['remaining_problem_bank_principal'] - q),
                'additional_loss_per_share_bound': (risk['remaining_problem_bank_principal'] - q) * 1000000 / operating['shares'],
                'not_a_total_liability_or_accrued_interest_cap': True,
                'not_an_adopted_payment_timeline_or_D_Y5_return_model': True,
                'no_premature_credit_for_unspent_support_budget': True},
            'ordinary_equity_value': value, 'ordinary_equity_value_per_share': value * 1000000 / operating['shares'],
            'retired_parent_policy_constraints': retired_parent_constraints,
            'constraints': retained_constraints}


def blocked(constraints, metric):
    return [x for x in constraints if metric in x['affects']]


def evaluate(config, operating, cached, profile, ledger=None):
    result = {}
    failure_stage, failure_period = 'evaluation_context', None
    try:
        result.update({'path': profile['name'], 'profile': profile['name'],
                       'cached_operating_profile': cached['path']})
        failure_stage = 'parent_replay'
        ledger = parent_replay(config, operating, cached, profile) if ledger is None else ledger
        result['parent_risk_ledger'] = ledger
        failure_stage, failure_period = 'current_main_bridge', 0
        main = adopt_bridge(config, operating, cached, ledger['states'][0], 'raw_main_method', 0)
        result['raw_main_method'] = main
        failure_stage, failure_period = 'year5_bridge', 5
        y5 = adopt_bridge(config, operating, cached, ledger['states'][5], 'raw_year5_bridge', 5)
        result['raw_year5_bridge'] = y5
        failure_stage, failure_period = 'constraint_attribution', None
        inherited = [copy.deepcopy(x) for x in cached['constraints'] if x.get('unit') != config['problem_unit'] and not retired_parent_policy_constraint(x)]
        constraints = inherited + ledger['constraints'] + main['constraints'] + y5['constraints']
        result['retired_problem_policy_constraints_not_global_insolvency'] = [copy.deepcopy(x) for x in cached['constraints'] if x.get('unit') == config['problem_unit']]
        result['retired_parent_policy_constraints'] = [copy.deepcopy(x) for x in cached['constraints'] if retired_parent_policy_constraint(x)] + main['retired_parent_policy_constraints'] + y5['retired_parent_policy_constraints']
        result['constraints'] = constraints
        result['main_method'] = {'value_per_share': None if blocked(constraints, 'main') else main['ordinary_equity_value_per_share'], 'null_reasons': blocked(constraints, 'main')}
        failure_stage, failure_period = 'current_auxiliary_bridge', 0
        aux = adopt_bridge(config, operating, cached, ledger['states'][0], 'raw_auxiliary_method', 0)
        result['raw_auxiliary_method'] = aux
        result['retired_parent_policy_constraints'].extend(aux['retired_parent_policy_constraints'])
        failure_stage, failure_period = 'distribution_and_interface', None
        constraints.extend(aux['constraints'])
        result['auxiliary_method'] = {'value_per_share': None if blocked(constraints, 'auxiliary') else aux['ordinary_equity_value_per_share'], 'null_reasons': blocked(constraints, 'auxiliary')}
        schedule = []
        result['partial_distribution_schedule'] = schedule
        for row in ledger['periods'][:5]:
            failure_period = row['period']
            reasons = [x for x in blocked(constraints, 'distributions') if x.get('period', 0) <= row['period']]
            raw_d = row['actual_distribution'] * 1000000 / operating['shares']
            schedule.append({'period': row['period'], 'from': row['from'], 'to': row['to'], 'raw_modeled_cash_per_share': raw_d,
                             'adopted_cash_per_share': None if reasons else raw_d, 'null_reasons': reasons})
        failure_period = 5
        tv = None if blocked(constraints, 'terminal') else y5['ordinary_equity_value_per_share']
        ds = [x['adopted_cash_per_share'] for x in schedule]
        result['partial_distribution_schedule'] = schedule
        result['year5_value_per_share'] = tv
        result['return_model'] = None if tv is None or any(d is None for d in ds) else {'schema_version': 1, 'method': 'annual_common_equity_irr_v1', 'currency': 'CNY', 'model_as_of': operating['cutoff'], 'base_case_distributions_per_share': ds, 'base_case_terminal_equity_value_range_per_share': {'year_5': {'low': tv, 'high': tv}}}
        result['return_model_note'] = 'Conditional separated-entity adoption. D and Y5 use identical post-distribution C,R,Q; 200 is one pre-locked budget valued at full loss, not a second safety haircut or claimed booked GAAP loss. No automatic reserve release, no problem-entity cash/upstream/loan recovery, no DCF=DDM assertion. Normal-profit payout target is bounded by cash and worst bounded RE loss.'
        a, b = result['main_method']['value_per_share'], result['auxiliary_method']['value_per_share']
        result['method_gap_requires_explanation'] = None if a is None or b is None or abs(a) <= EPS else abs(a - b) / abs(a) > operating.get('valuation', {}).get('maximum_method_center_gap_for_explanation', 0.25)
        result['methods_not_mechanically_averaged'] = True
        result['status'] = 'ECONOMIC_CONSTRAINTS_RETAINED' if any(x['affects'] for x in constraints) else 'CONDITIONAL_ADOPTION_CALCULATED'
        return result, ledger

    except Exception as exc:
        result['failure_stage'] = failure_stage
        result['failure_period'] = failure_period
        if getattr(exc, 'partial', None) is not None:
            result['current_stage_partial'] = exc.partial
        raise TechnicalFailure('Adoption evaluation failed at ' + failure_stage + ' period=' + str(failure_period) + ': ' + str(exc), result) from exc


def calculate_adoption(config, operating, cache):
    results, ledgers, rates = [], {}, []
    failure_stage, failure_period = 'cache_validation', None
    failing_profile, failing_rate_key = None, None
    try:
        need(cache['execution_status'] == 'COMPLETED', 'Operating cache is not a completed formal result')
        mapping = paths_by_name(cache)
        for profile in config['profiles']:
            failure_stage, failing_profile = 'profile_evaluation', profile['name']
            result, ledger = evaluate(config, operating, mapping[profile['cache_key']], profile)
            results.append(result)
            ledgers[profile['name']] = ledger
        failure_stage, failing_profile = 'base_lookup', None
        base_profile = next(p for p in config['profiles'] if p['name'] == 'base')
        base_cached = mapping[base_profile['cache_key']]
        for key in config['rate_cache_keys']:
            failure_stage, failing_rate_key = 'rate_cache_lookup', key
            member = mapping[key]
            failure_stage = 'rate_cache_consistency'
            need(member['raw_initial_state'] == base_cached['raw_initial_state'] and member['raw_year5_state'] == base_cached['raw_year5_state'] and member['raw_periods'] == base_cached['raw_periods'], 'Discount cache does not share exact operating/cash state')
            profile = copy.deepcopy(base_profile)
            profile['name'] = key
            failure_stage = 'rate_evaluation'
            result, _ = evaluate(config, operating, member, profile, ledgers['base'])
            rates.append(result)
        failure_stage, failing_rate_key = 'interface_aggregation', None
        base = next(p for p in results if p['profile'] == 'base')
        members = rates if rates else [base]
        values = [p['main_method']['value_per_share'] for p in members]
        terminals = [p['year5_value_per_share'] for p in members]
        value_range = None if any(v is None for v in values) else {'low': min(values), 'high': max(values), 'currency': 'CNY'}
        interface = copy.deepcopy(base['return_model'])
        if interface is not None:
            if any(v is None for v in terminals):
                interface = None
            else:
                interface['base_case_terminal_equity_value_range_per_share']['year_5'] = {'low': min(terminals), 'high': max(terminals)}
        for member in members:
            failure_stage, failing_rate_key, failure_period = 'rate_final_state_consistency', member['profile'], 5
            need(member['parent_risk_ledger']['states'][5] == base['parent_risk_ledger']['states'][5], 'Y5 range reused a different risk/distribution state')
            for a, b in zip(member['partial_distribution_schedule'], base['partial_distribution_schedule']):
                failure_period = a['period']
                close(a['raw_modeled_cash_per_share'], b['raw_modeled_cash_per_share'], 'Discount endpoints cannot alter actual D')
        failure_stage, failing_rate_key, failure_period = 'final_result', None, None
        return {'symbol': operating['symbol'], 'information_cutoff': operating['cutoff'], 'currency': 'CNY', 'internal_money_unit': 'million', 'paths': results, 'discount_rate_diagnostics': rates,
                'base_interface_preview': {'value_range': value_range, 'return_model': interface, 'return_model_note': base['return_model_note'],
                                           'range_definition': 'Same base risk-prepared state; original8%-10% valuation endpoints only. Capital execution and bank-recourse conditions are separate views, not mixed endpoints.'},
                'healthy_operating_forecasts_replayed': False, 'old_policy_outputs_preserved_as_cache': True,
                'no_market_price_or_IRR': True, 'not_formal_research_registration': True}

    except Exception as exc:
        partial = {'completed_profiles': results, 'completed_parent_ledgers': ledgers,
                   'completed_rate_views': rates, 'failure_stage': failure_stage,
                   'failure_period': failure_period, 'failing_profile': failing_profile,
                   'failing_rate_key': failing_rate_key,
                   'current_partial': getattr(exc, 'partial', None)}
        raise TechnicalFailure('Adoption calculation failed at ' + failure_stage + ': ' + str(exc), partial) from exc


def load_pinned(base, item):
    p = (base / item['path']).resolve()
    need(base.resolve() in p.parents, 'Input dependency must be within relative input closure')
    data = p.read_bytes()
    need(hashlib.sha256(data).hexdigest() == item['sha256'], 'Pinned input mismatch: ' + item['path'])
    return json.loads(data)
