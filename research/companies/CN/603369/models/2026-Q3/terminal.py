#!/usr/bin/env python3
"""Narrow Y5 sensitivity/display projection; ordinary offline invocation.

Never imports any producer or recomputes the 21-period cash path. Original results,
current valuations, dividends, legal-cash gates and warnings are read-only inputs.
"""
import argparse
import datetime as dt
import hashlib
import itertools
import json
import os
from pathlib import Path



def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': digest(data)}




def project(saved,x,facts,metadata):
    pre=metadata['inputs'];own=metadata['code']
    base = saved['results'][0]
    if base['case'] != 'base' or base['funding_infeasible']:
        raise SystemExit('Not the funded saved base case')
    m = x['maturity']
    shares = facts['q3_2026_consolidated']['equity']['ordinary_shares']
    if shares != 1246800037 or saved['terminal_date'] != '2031-10-31':
        raise SystemExit('Equity/time boundary mismatch')
    # Read four saved calendar slices. The fourth is one-third of Q4 (October).
    r31 = [r for r in base['periods'] if r['year'] == 2031]
    if [r['date'] for r in r31] != ['2031-03-31','2031-06-30','2031-09-30','2031-10-31']:
        raise SystemExit('Unexpected saved 2031 calendar slices')
    if [r['quarter_fraction'] for r in r31] != [1.0,1.0,1.0,1/3]:
        raise SystemExit('Unexpected saved partial-quarter fractions')
    q1, q2, q3, october = [r['NOPAT'] for r in r31]
    # Existing producer assumes unchanged product margins and expense ratios for
    # post-Y5 steady growth: all normal commodity P&L terms scale with revenue.
    # Nov-Dec2031 is still the prior calendar-year budget; Jan-Oct2032 grows by g.
    jan_oct_nopat = q1 + q2 + q3 + october
    nov_dec_nopat = october * 2
    calendar_2031_nopat = jan_oct_nopat + nov_dec_nopat
    forward_da = base['terminal_operating']['forward_da']
    calendar_2031_da = x['base']['nonlease_da'][4]
    tail_cash = base['terminal_operating']['tail_cash_after_Y5']
    nfa5 = base['conditional_holder_path']['Y5_remaining_NFA_total']
    terminal_t = base['periods'][-1]['t']

    def terminal(k, g, roic, maintenance_ratio, multiple):
        # Independent compact formula, not a call/import into model_candidate.
        nopat = nov_dec_nopat + jan_oct_nopat * (1+g)
        maintenance = forward_da * maintenance_ratio
        reinvestment = nopat * g / roic
        fcff = nopat + forward_da - maintenance - reinvestment
        tail_pv = sum(tail_cash*w/(1+k)**t for w,t in zip(
            x['capital_bridge']['tail_payment_weights'],
            x['capital_bridge']['tail_payment_years_after_Y5']))
        operating_ev = fcff/(k-g)-tail_pv
        normal_earning = calendar_2031_nopat + calendar_2031_da - maintenance
        normal_ev = normal_earning * multiple - tail_pv
        return {
            'k': k, 'g': g, 'incremental_roic': roic,
            'maintenance_to_da': maintenance_ratio, 'normal_NOPAT_multiple': multiple,
            'forward_NOPAT': nopat, 'forward_DA': forward_da,
            'forward_maintenance': maintenance, 'growth_reinvestment': reinvestment,
            'forward_FCFF': fcff, 'tail_PV_at_Y5': tail_pv,
            'operating_EV_Y5': operating_ev, 'normal_NOPAT_before_multiple': normal_earning,
            'normal_earnings_EV_Y5': normal_ev, 'same_path_NFA_Y5': nfa5,
            'main_Y5_per_share': (operating_ev+nfa5)/shares,
            'normal_earnings_Y5_per_share': (normal_ev+nfa5)/shares}

    central = terminal(m['required_return'], m['nominal_growth'], m['incremental_roic'],
                       m['maintenance_to_da'], m['normal_NOPAT_multiple'])
    # Central match verifies only the compact formula and units, not business truth.
    checks = []
    pairs = [('main_Y5_per_share',base['conditional_holder_path']['Y5_per_share']),
             ('operating_EV_Y5',base['terminal_operating']['operating_EV_Y5']),
             ('normal_earnings_EV_Y5',base['terminal_operating']['normal_earnings_EV_Y5']),
             ('forward_NOPAT',base['terminal_operating']['forward_nopat']),
             ('normal_NOPAT_before_multiple',base['terminal_operating']['normal_NOPAT_before_multiple'])]
    for key, original in pairs:
        error = central[key]-original
        ok = abs(error) <= max(1e-7,abs(original)*1e-12)
        checks.append({'field': key, 'saved': original, 'projected': central[key],
                       'difference': error, 'within_float_tolerance': ok})
        if not ok:
            raise SystemExit('Central formula mismatch: '+key)
    main_grid = [terminal(k,g,roi,mr,m['normal_NOPAT_multiple']) for k,g,roi,mr in itertools.product(
        m['required_return_range'], m['nominal_growth_range'],
        m['incremental_roic_range'], m['maintenance_to_da_range'])]
    # Normalized earnings is an auxiliary method, with its existing distinct
    # parameterization. Do not mix its endpoints into the selected primary band.
    normal_grid = [terminal(k,m['nominal_growth'],m['incremental_roic'],m['maintenance_to_da'],mult)
                   for k,mult in itertools.product(m['required_return_range'],m['normal_NOPAT_multiple_range'])]
    lower = min(main_grid, key=lambda r:r['main_Y5_per_share'])
    upper = max(main_grid, key=lambda r:r['main_Y5_per_share'])
    normal_lower = min(normal_grid, key=lambda r:r['normal_earnings_Y5_per_share'])
    normal_upper = max(normal_grid, key=lambda r:r['normal_earnings_Y5_per_share'])
    saved_ev = base['valuation']['current_operating_EV_total']
    current_nfa = base['valuation']['current_risk_tax_adjusted_NFA_total']
    saved_terminal_ev = base['terminal_operating']['operating_EV_Y5']
    pv_terminal = saved_terminal_ev/(1+m['required_return'])**terminal_t
    result = {
        'schema':'603369-same-base-cash-path-Y5-sensitivity-v1',
        'projection_completed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope':'Only Y5 endpoint sensitivity and saved-current-value display decomposition; no cash-path or current-valuation rerun',
        'same_five_distributions':[d['per_share'] for d in base['dividends']],
        'same_dividend_payment_dates':[d['payment_date'] for d in base['dividends']],
        'shares':shares,'terminal_date':saved['terminal_date'],'same_path_NFA_Y5':nfa5,
        'NFA_condition':'Fixed at the saved base financial-return/recovery/tax and cash-retention path; no extra loss or new cash receipt is invented. Separate original 85% recovery scenario is not spliced into these endpoints.',
        'economic_interpretation':'Conditional parameter sensitivity under one already adopted five-year operating/dividend path, not confidence/probability bounds or liquidation guarantee; k applies to ongoing operations at Y5, not to an artificial roll-forward of current value.',
        'raw_slices':[{'date':r['date'],'fraction':r['quarter_fraction'],'NOPAT':r['NOPAT']} for r in r31],
        'central':central,'central_match_checks':checks,
        'primary_Y5_grid':main_grid,'primary_Y5_low_endpoint':lower,'primary_Y5_high_endpoint':upper,
        'selected_same_path_Y5_range_per_share':{'low':lower['main_Y5_per_share'],'high':upper['main_Y5_per_share']},
        'normal_earnings_Y5_grid':normal_grid,
        'auxiliary_same_path_Y5_range_per_share':{'low':normal_lower['normal_earnings_Y5_per_share'],'high':normal_upper['normal_earnings_Y5_per_share']},
        'normal_earnings_low_endpoint':normal_lower,'normal_earnings_high_endpoint':normal_upper,
        'saved_current_value_display':{'saved_main_EV':saved_ev,'saved_current_NFA':current_nfa,
            'saved_main_per_share':base['valuation']['central_current_EV_plus_NFA_per_share'],
            'saved_cross_per_share':base['valuation']['central_current_normal_earnings_plus_NFA_per_share'],
            'formula':'saved operating_EV_Y5 / (1 + saved base k) ** saved terminal_t',
            't':terminal_t,'k':m['required_return'],'terminal_PV':pv_terminal,
            'explicit_period_PV':saved_ev-pv_terminal,'terminal_PV_fraction_of_EV':pv_terminal/saved_ev,
            'terminal_PV_fraction_of_equity':pv_terminal/(saved_ev+current_nfa)},
        'unchanged_copied_diagnostics':{'base_funding_infeasible':base['funding_infeasible'],'base_warnings':base['warnings'],
            'all_original_current_values_and_cash_paths_untouched':True,'delayed_policy_warning_not_in_scope_or_resolved':True,
            'negative_cash_null_branch_not_exercised':True},
        'pins':pre,'code':own,'admission':None,
    }
    return result
