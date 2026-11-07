"""Dated cash/anniversary bridge, using freshly calculated financial states.

The historical saved-output comparison/receipt fields are omitted; all valuation
and actual cash-date equations retain the adopted model's formulas.
"""
from datetime import date
import math

def year_fraction(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days / 365.0

def shift_value(value, annual_cost, source_horizon, target_horizon):
    """One fixed claim, no intervening distribution; negative values retain their sign."""
    return value * (1.0 + annual_cost) ** (source_horizon - target_horizon)

def anniversary(start, number):
    d = date.fromisoformat(start)
    return date(d.year + number, d.month, d.day).isoformat()

def cash_buckets(start, amounts, payment_dates):
    if len(amounts) != len(payment_dates):
        raise ValueError('Payment length mismatch')
    ends = [anniversary(start, n) for n in range(1, 6)]
    buckets = [0.0] * 5
    later = []
    table = []
    for amount, payment in zip(amounts, payment_dates):
        if amount < 0 or not math.isfinite(amount) or payment <= start:
            raise ValueError('Invalid future payment')
        bucket = next((i for i, end in enumerate(ends) if payment <= end), None)
        if bucket is None:
            later.append(dict(date=payment, amount=amount))
        else:
            buckets[bucket] += amount
        table.append(dict(payment_date=payment, amount=amount, year_fraction=year_fraction(start, payment), annual_bucket=None if bucket is None else bucket + 1))
    return dict(distributions=buckets, payments_after_five_years=later, payment_table=table)

def terminal_at_anniversary(fiscal_value, cost, fiscal_date, horizon_date, later_payments):
    result = shift_value(fiscal_value, cost, 0.0, year_fraction(horizon_date, fiscal_date))
    for payment in later_payments:
        if payment['date'] > fiscal_date:
            raise ValueError('Unmodeled post-fiscal dividend')
        result += shift_value(payment['amount'], cost, 0.0, year_fraction(horizon_date, payment['date']))
    return result

def date_bridge(settings, original, projection, inputs):
    cutoff = inputs['identity']['cutoff']
    start = settings['valuation_date']
    fiscal = settings['fiscal_terminal_date']
    if cutoff != settings['information_cutoff'] or original['identity'] != inputs['identity'] or projection['identity'] != inputs['identity']:
        raise ValueError('Identity/cutoff mismatch')
    if not original['base']['cash_path_feasible'] or projection['structural_terminal_adopted']:
        raise ValueError('No feasible fixed ordinary cash history')
    if settings['economic_adoption'] != 'normal_finite_rights_with_explicit_new_capital_loss':
        raise ValueError('No explicit economic adoption selection')
    if settings['day_count'] != 'ACT/365F':
        raise ValueError('Unsupported day count')
    if any((not original['cases'][name]['cash_path_feasible'] for name in ['core_low', 'core_high'])):
        raise ValueError('Core current valuation has an unresolved hard cash path')
    if projection['interfaces']['holder_blockers']:
        raise ValueError('Unresolved holder qualification')
    amounts = projection['fixed_distributions']
    if amounts != [r['distribution_per_share'] for r in original['base']['rows']]:
        raise ValueError('Historical D changed')
    horizon = anniversary(start, 5)
    if horizon != settings['fifth_anniversary_date']:
        raise ValueError('Wrong fifth anniversary')
    base = cash_buckets(start, amounts, settings['base_payment_dates'])
    delayed = cash_buckets(start, amounts, settings['delayed_payment_dates'])
    if base['payments_after_five_years']:
        raise ValueError('Base year-five rights need another design')
    if base['distributions'] != amounts:
        raise ValueError('Base distributions not in intended annual buckets')
    equity_costs = [inputs['initial_estimates']['aux_equity_cost_low'], inputs['initial_estimates']['aux_equity_cost_high']]
    shares = projection['fixed_state']['shares']
    stub = year_fraction(start, settings['estimated_current_state_date'])
    capital_horizon = year_fraction(start, fiscal)
    current_details = {}
    current = {}
    terminal = {}
    delayed_terminal = {}
    for name in ['low', 'high']:
        case_name = 'core_' + name
        source = original['cases'][case_name]['current']
        if abs(source['ordinary_equity'] / shares / (1 + inputs['endpoints'][case_name]['road_discount']) ** inputs['identity']['valuation_stub_years'] - source['per_share']) > 1e-08:
            raise ValueError('Original year-end ordinary value identity mismatch')
        delta = projection['cases'][case_name]['nonroad_new_capital']['adjustment']
        options = []
        for rate in equity_costs:
            ordinary_present = shift_value(source['ordinary_equity'] / shares, rate, 0.0, stub)
            capital_present = shift_value(delta / shares, rate, 0.0, capital_horizon)
            options.append(dict(equity_cost=rate, ordinary_present=ordinary_present, capital_increment_present=capital_present, total=ordinary_present + capital_present))
        choose = min if name == 'low' else max
        selected = choose(options, key=lambda x: x['total'])
        current[name] = selected['total']
        current_details[name] = dict(estimated_dec31_ordinary_value_per_share=source['ordinary_equity'] / shares, delta_terminal_common_bn=delta, by_equity_cost=options, selected=selected)
        fv = projection['cases'][case_name]['value']['per_share']
        terminal_options = [terminal_at_anniversary(fv, rate, fiscal, horizon, base['payments_after_five_years']) for rate in equity_costs]
        delayed_options = [terminal_at_anniversary(fv, rate, fiscal, horizon, delayed['payments_after_five_years']) for rate in equity_costs]
        terminal[name] = choose(terminal_options)
        delayed_terminal[name] = choose(delayed_options)
    for interval in [current, terminal, delayed_terminal]:
        if not (0 <= interval['low'] <= interval['high'] and all((math.isfinite(v) for v in interval.values()))):
            raise ValueError('Invalid value interval')
    return dict(current_value=current, current_bridge_details=current_details, terminal_value=terminal, delayed_terminal_value=delayed_terminal, base_timing=base, delayed_timing=delayed, stub_years=stub, capital_horizon_years=capital_horizon, fifth_anniversary_act365f=year_fraction(start, horizon), terminal_bridge_days=(date.fromisoformat(fiscal) - date.fromisoformat(horizon)).days, equity_costs=equity_costs, ordinary_state_date=settings['estimated_current_state_date'], fiscal_terminal_date=fiscal, fifth_anniversary_date=horizon, shares=shares, forecast_recomputed=False, monthly_funding_feasibility_verified=False, structural_terminal_adopted=False)
