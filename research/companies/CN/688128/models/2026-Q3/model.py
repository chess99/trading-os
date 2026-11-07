# Pure economic functions; standard library only. See README.md for units and scope.
from copy import deepcopy
from datetime import datetime
from math import isfinite

def date_contract(meta):
    anchor = datetime.fromisoformat(meta['information_cutoff'])
    anniversaries = [anchor.replace(year=anchor.year + j).isoformat() for j in range(1, 9)]
    return {'anchor': meta['economic_anchor_timestamp'], 'model_as_of': meta['model_as_of'], 'information_cutoff': meta['information_cutoff'], 'display_delta_seconds': (datetime.fromisoformat(meta['valuation_display_timestamp']) - anchor).total_seconds(), 'first_five_ends': anniversaries[:5], 'terminal_year5': anniversaries[4], 'metadata_matches_anniversaries': meta['period_end_dates'] == anniversaries}

def opening_bridge(data, condition):
    s = data['snapshot']
    nwc = sum(s['nwc_assets'].values()) - sum(s['nwc_liabilities'].values())
    nwc += s['construction_payables_inside_other_payables_h1_proxy']
    investment_assets = s['other_equity_assets'] + s['associates']
    bank_assets = s['cash_equivalents'] + s['trading_assets'] + s['current_noncurrent_assets'] + s['other_noncurrent_assets'] - s['operating_items_in_combined_financial_lines_estimate']
    debt_at_open = s['short_debt']
    legacy_obligations = s['legacy_pension'] + s['unpaid_nci_purchase_proxy_upper']
    exposure = condition.get('exposure_override')
    if exposure is None:
        exposure = s['finance_company_exposure_h1_proxy']
    assert 0 <= exposure <= bank_assets
    recoverable_claim = exposure * condition['principal_recovery']
    liquid = bank_assets - exposure - s['operating_cash_open'] - debt_at_open + s['october_net_financial_change_assumption']
    if condition['release_year'] == 0:
        liquid += recoverable_claim
        outstanding_claim = 0.0
        claim_pv = 0.0
    else:
        outstanding_claim = recoverable_claim
        claim_pv = outstanding_claim / (1 + condition['claim_discount_rate']) ** condition['release_year']
    return {'operating_nwc_open': nwc + s['operating_cash_open'], 'fixed_operating_open': sum(s['fixed_operating_assets']), 'liquid_open': liquid, 'investment_assets': investment_assets, 'outstanding_claim': outstanding_claim, 'claim_pv': claim_pv, 'legacy_obligations': legacy_obligations, 'net_financial_value': liquid + investment_assets + claim_pv - legacy_obligations, 'nci_open': s['nci_value_proxy'], 'exposure_proxy': exposure}

def scenario_inputs(data, name):
    d = deepcopy(data)
    b = d['base']
    if name == 'base':
        return d
    if name == 'cycle_delay':
        for key, first in [('electrical', [-0.05, 0.0, 0.12]), ('complete', [-0.08, 0.0, 0.08]), ('quality', [0.05, 0.05, 0.08]), ('materials', [0.0, 0.02, 0.05])]:
            b['segments'][key]['growth'][:3] = first
        for j in range(3):
            scale = 1.0 if j < 2 else 0.5
            b['segments']['electrical']['gm'][j] -= 0.03 * scale
            b['segments']['complete']['gm'][j] -= 0.02 * scale
            b['segments']['materials']['gm'][j] -= 0.01 * scale
            b['nwc_ratios']['receivables'][j] += 0.025 * scale
            b['nwc_ratios']['inventory'][j] += 0.06 * scale
            b['nwc_ratios']['customer_advances'][j] -= 0.04 * scale
        b['project_cash'][0] -= 60
        b['project_cash'][1] += 30
        b['project_cash'][2] += 30
        b['parent']['upstream_profit_ratio'][:2] = [0.45, 0.45]
        b['parent']['upstream_cash_collection'][:2] = [0.8, 0.8]
        return d
    if name == 'structural_competition':
        for key, arr in {'electrical': [-0.05, -0.03, 0, 0.01, 0.01, 0.01, 0.01, 0.01], 'quality': [0.03] * 8, 'complete': [-0.05, 0, 0, 0.01, 0.01, 0.01, 0.01, 0.01], 'materials': [0, 0, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01], 'other': [0.01] * 8}.items():
            b['segments'][key]['growth'] = arr
        b['segments']['quality']['growth'][-3:] = [0.02, 0.015, 0.01]
        for j in range(8):
            b['segments']['electrical']['gm'][j] -= 0.035
            b['segments']['quality']['gm'][j] -= 0.015
            b['segments']['complete']['gm'][j] -= 0.02
            b['segments']['materials']['gm'][j] -= 0.015
            b['nwc_ratios']['receivables'][j] += 0.025
            b['nwc_ratios']['inventory'][j] += 0.03
            b['nwc_ratios']['customer_advances'][j] -= 0.05
        b['parent']['upstream_profit_ratio'] = [0.4] * 8
        b['tax_rate'] = 0.17
        b['terminal_growth'] = 0.01
        return d
    if name == 'better_execution':
        for j in range(5):
            for key, extra in [('electrical', 0.03), ('quality', 0.02), ('materials', 0.01)]:
                b['segments'][key]['growth'][j] += extra
            b['segments']['electrical']['gm'][j] += 0.01
            b['segments']['quality']['gm'][j] += 0.005
        b['project_cash'] = [x * 1.15 for x in b['project_cash']]
        b['minimum_growth_fixed_intensity'] = 0.34
        return d
    if name == 'upstream_delay':
        b['parent']['upstream_cash_collection'][:2] = [0.5, 0.5]
        b['parent']['parent_deposit_access'][:2] = [0.0, 0.0]
        return d
    raise ValueError(name)

def fixed_capital_step(opening_fixed, cash_capex, nonlease_da, legacy_settlement):
    if not 0 <= legacy_settlement <= cash_capex:
        raise ValueError('Legacy settlement must be included in, not added to, cash capex')
    additions = cash_capex - legacy_settlement
    return {'capital_additions': additions, 'fixed_operating_capital': opening_fixed + additions - nonlease_da}

def operating_budget(data, checkpoint=None):
    b, s = (data['base'], data['snapshot'])
    initial = opening_bridge(data, data['financial_conditions']['par_available'])
    previous_revenue = sum((x['revenue0'] for x in b['segments'].values()))
    revenue_state = {k: v['revenue0'] for k, v in b['segments'].items()}
    rd_state = {k: v['revenue0'] * v['rd'][0] for k, v in b['segments'].items()}
    previous_nwc = initial['operating_nwc_open']
    fixed_capital = initial['fixed_operating_open']
    previous_invested = previous_nwc + fixed_capital
    rows = []
    for j in range(8):
        segment_rows = {}
        for key, p in b['segments'].items():
            revenue = revenue_state[key] * (1 + p['growth'][j])
            rd = max(revenue * p['rd'][j], rd_state[key] * 0.95)
            gross_profit = revenue * p['gm'][j]
            sga = revenue * p['sga'][j]
            segment_rows[key] = {'revenue': revenue, 'gross_profit': gross_profit, 'rd': rd, 'sga': sga, 'ebit_before_central': gross_profit - rd - sga}
            revenue_state[key], rd_state[key] = (revenue, rd)
        revenue = sum((x['revenue'] for x in segment_rows.values()))
        central_rd = b['central_rd0'] * (1 + b['central_inflation']) ** (j + 1)
        central_admin = b['central_admin0'] * (1 + b['central_inflation']) ** (j + 1)
        lease_cash_conversion = b['cash_rent_conversion0'] * (1 + b['central_inflation']) ** (j + 1)
        net_operating_other = revenue * (b['subsidy_rate'] - b['surcharge_rate'] - b['normal_credit_loss_rate'] - b['normal_inventory_asset_loss_rate'])
        ebit = sum((x['ebit_before_central'] for x in segment_rows.values())) - central_rd - central_admin - lease_cash_conversion + net_operating_other
        tax = max(ebit, 0.0) * b['tax_rate']
        nopat = ebit - tax
        ratios = {k: v[j] for k, v in b['nwc_ratios'].items()}
        nwc_components = {k: revenue * v for k, v in ratios.items()}
        nwc = sum((nwc_components[k] for k in ['receivables', 'inventory', 'prepayment', 'contract_assets', 'operating_cash'])) - sum((nwc_components[k] for k in ['trade_payables', 'customer_advances', 'ancillary_net_liabilities']))
        delta_nwc = nwc - previous_nwc
        da = b['nonlease_da'][j]
        maintenance_capex = da
        growth_floor = b['minimum_growth_fixed_intensity'] * max(0, revenue - previous_revenue)
        growth_capex = max(b['project_cash'][j], growth_floor)
        capex = maintenance_capex + growth_capex
        fcff = nopat + da - capex - delta_nwc
        legacy_settlement = b['legacy_construction_settlement'][j]
        capital = fixed_capital_step(fixed_capital, capex, da, legacy_settlement)
        fixed_capital = capital['fixed_operating_capital']
        invested = fixed_capital + nwc
        denominator = (previous_invested + invested) / 2
        rows.append({'year': j + 1, 'end_date': data['meta']['period_end_dates'][j], 'segments': segment_rows, 'revenue': revenue, 'ebit': ebit, 'tax': tax, 'nopat': nopat, 'central_rd': central_rd, 'central_admin': central_admin, 'rd_total': sum((x['rd'] for x in segment_rows.values())) + central_rd, 'net_operating_other': net_operating_other, 'lease_cash_conversion': lease_cash_conversion, 'nonlease_da': da, 'maintenance_capex': maintenance_capex, 'project_cash': b['project_cash'][j], 'growth_floor': growth_floor, 'growth_capex': growth_capex, 'capex': capex, 'legacy_construction_settlement': legacy_settlement, 'capital_additions': capital['capital_additions'], 'nwc_components': nwc_components, 'nwc': nwc, 'delta_nwc': delta_nwc, 'fcff': fcff, 'fixed_operating_capital': fixed_capital, 'invested_capital': invested, 'roic_diagnostic': nopat / denominator if denominator > 0 else None})
        if checkpoint:
            checkpoint('operating_row_' + str(j + 1), rows[-1])
        previous_revenue, previous_nwc, previous_invested = (revenue, nwc, invested)
    return rows

def terminal_cashflow(last, growth, fixed_intensity, tax_rate):
    revenue = last['revenue'] * (1 + growth)
    ebit = last['ebit'] * (1 + growth)
    nopat = ebit - max(0, ebit) * tax_rate
    da = last['nonlease_da'] * (1 + growth)
    growth_capex = fixed_intensity * max(0, revenue - last['revenue'])
    delta_nwc = last['nwc'] * growth
    return {'revenue': revenue, 'ebit': ebit, 'nopat': nopat, 'nonlease_da': da, 'maintenance_capex': da, 'growth_capex': growth_capex, 'delta_nwc': delta_nwc, 'fcff': nopat - growth_capex - delta_nwc}

def value_operations(rows, discount_rate, growth, fixed_intensity, tax_rate, from_year=0):
    assert len(rows) == 8 and 0 <= from_year <= 7 and (discount_rate > growth)
    terminal = terminal_cashflow(rows[-1], growth, fixed_intensity, tax_rate)
    terminal_value = terminal['fcff'] / (discount_rate - growth)
    visible = sum((row['fcff'] / (1 + discount_rate) ** (row['year'] - from_year) for row in rows if row['year'] > from_year))
    terminal_pv = terminal_value / (1 + discount_rate) ** (8 - from_year)
    return {'enterprise_value': visible + terminal_pv, 'visible_pv': visible, 'terminal_pv': terminal_pv, 'terminal_value_y8': terminal_value, 'terminal_cashflow_y9': terminal, 'terminal_pv_fraction': terminal_pv / (visible + terminal_pv) if visible + terminal_pv != 0 else None}

def parent_step(state, *, own_profit, own_cfo, capex, lease_cash, internal_contribution, upstream_declared, collection_fraction, external_dividend, target_dividend, cash_buffer, deposit_draw_limit, deposit_access, reserve_rate, registered_capital, continue_reserve, group_dividend_capacity, legacy_payment=0.0, old_receivable_collection_fraction=1.0):
    old_received = state['dividend_receivable'] * old_receivable_collection_fraction
    current_received = upstream_declared * collection_fraction
    received = old_received + current_received
    new_receivable = state['dividend_receivable'] - old_received + upstream_declared - current_received
    profit = own_profit + upstream_declared + external_dividend
    profit_after_prior_loss = max(0, profit - max(0, -state['re']))
    appropriation = profit_after_prior_loss * reserve_rate if continue_reserve or state['reserve'] < registered_capital * 0.5 else 0.0
    re_before_dividend = state['re'] + profit - appropriation
    cash_before_draw = state['cash'] + received + own_cfo + external_dividend - capex - lease_cash - internal_contribution - legacy_payment
    legal_capacity = max(0, re_before_dividend)
    desired = min(max(0, target_dividend), legal_capacity, max(0, group_dividend_capacity))
    draw = min(state['deposits'] * deposit_access, deposit_draw_limit, max(0, cash_buffer + desired - cash_before_draw))
    cash_after_draw = cash_before_draw + draw
    dividend = min(desired, max(0, cash_after_draw - cash_buffer))
    cash = cash_after_draw - dividend
    next_state = {'cash': cash, 're': re_before_dividend - dividend, 'reserve': state['reserve'] + appropriation, 'deposits': state['deposits'] - draw, 'dividend_receivable': new_receivable}
    return (next_state, {'cash_open': state['cash'], 're_open': state['re'], 'reserve_open': state['reserve'], 'deposits_open': state['deposits'], 'dividend_receivable_open': state['dividend_receivable'], 'own_profit': own_profit, 'own_cfo': own_cfo, 'capex': capex, 'lease_cash': lease_cash, 'external_dividend': external_dividend, 'target_dividend': target_dividend, 'group_dividend_capacity': group_dividend_capacity, 'profit': profit, 'reserve_appropriation': appropriation, 'upstream_declared': upstream_declared, 'upstream_received': received, 'old_receivable_collected': old_received, 'current_dividend_collected': current_received, 'old_receivable_collection_fraction': old_receivable_collection_fraction, 'current_dividend_collection_fraction': collection_fraction, 'deposit_access_fraction': deposit_access, 'profit_after_prior_loss_for_reserve': profit_after_prior_loss, 'cash_before_draw': cash_before_draw, 'deposit_reclassification': draw, 'internal_contribution': internal_contribution, 'legacy_payment': legacy_payment, 'dividend': dividend, 'hard_funding_gap': max(0, -cash), 'buffer_shortfall': max(0, cash_buffer - cash), 'unpaid_target_dividend': max(0, target_dividend - dividend), **next_state})

def owner_cash_budget(data, rows, condition, checkpoint=None):
    b, s, p = (data['base'], data['snapshot'], data['base']['parent'])
    opening = opening_bridge(data, condition)

    def access(field, j):
        return min(p[field][j], condition.get(field, [1.0] * 8)[j])
    liquid, claim, nci = (opening['liquid_open'], opening['outstanding_claim'], opening['nci_open'])
    state = {'cash': s['parent_cash'], 're': s['parent_re'], 'reserve': s['parent_statutory_reserve'], 'deposits': s['parent_deposit_pool_estimate'], 'dividend_receivable': 0.0}
    outputs = []
    pension_remaining = s['legacy_pension']
    purchase_remaining = s['unpaid_nci_purchase_proxy_upper']
    for j, row in enumerate(rows):
        claim_open = claim
        financial_income = max(liquid, 0) * b['liquid_financial_yield_after_tax'] + b['equity_dividend_cash']
        release = claim if condition['release_year'] == j + 1 else 0.0
        claim -= release
        nci_profit = max(row['nopat'], 0) * b['nci_profit_fraction']
        nci_dividend = nci_profit * b['nci_payout']
        nci += nci_profit - nci_dividend
        pension_payment = min(pension_remaining, b['legacy_pension_cash_annual_budget'])
        purchase_payment = purchase_remaining if j == 0 else 0.0
        legacy_payment = pension_payment + purchase_payment
        pension_remaining -= pension_payment
        purchase_remaining -= purchase_payment
        legacy_remaining = pension_remaining + purchase_remaining
        available = liquid + row['fcff'] + financial_income + release - nci_dividend - legacy_payment
        scale = (1 + p['own_cash_cost_growth']) ** (j + 1)
        own_profit = p['own_profit_before_sub_dividends0'] * scale
        subs_profit_proxy = max(0, row['nopat'] - nci_profit - own_profit)
        upstream = subs_profit_proxy * p['upstream_profit_ratio'][j]
        target = max(0, row['nopat'] - nci_profit + financial_income) * p['target_common_payout']
        state, parent = parent_step(state, own_profit=own_profit, own_cfo=p['own_cfo0'] * scale, capex=p['own_capex0'] * scale, lease_cash=p['own_lease_cash0'] * scale, internal_contribution=p['internal_capital_contributions'][j], upstream_declared=upstream, collection_fraction=access('upstream_cash_collection', j), old_receivable_collection_fraction=access('old_dividend_receivable_collection', j), external_dividend=b['equity_dividend_cash'], target_dividend=target, cash_buffer=p['cash_buffer'], deposit_draw_limit=p['deposit_draw_limit_annual'], deposit_access=access('parent_deposit_access', j), reserve_rate=p['reserve_rate'], registered_capital=s['parent_registered_capital'], continue_reserve=p['continue_reserve_after_threshold'], group_dividend_capacity=max(0, available), legacy_payment=legacy_payment)
        next_liquid = available - parent['dividend']
        remaining_delay = max(0, condition['release_year'] - (j + 1))
        claim_pv = claim / (1 + condition['claim_discount_rate']) ** remaining_delay
        outputs.append({'year': j + 1, 'end_date': row['end_date'], 'financial_income': financial_income, 'liquid_open': liquid, 'fcff': row['fcff'], 'claim_open': claim_open, 'liquid_interest_income': max(liquid, 0) * b['liquid_financial_yield_after_tax'], 'equity_dividend_cash': b['equity_dividend_cash'], 'claim_interest_income': 0.0, 'claim_principal_release': release, 'claim_remaining': claim, 'claim_fair_value': claim_pv, 'liquid_assets': next_liquid, 'investment_assets': opening['investment_assets'], 'nci_dividend': nci_dividend, 'nci_value_proxy': nci, 'legacy_payment': legacy_payment, 'legacy_remaining': legacy_remaining, 'net_financial_value': next_liquid + opening['investment_assets'] + claim_pv - legacy_remaining, 'group_hard_funding_gap': max(0, -next_liquid), 'parent': parent, 'common_dividend_per_share': parent['dividend'] / data['meta']['shares_million']})
        if checkpoint:
            checkpoint('owner_row_' + str(j + 1), outputs[-1])
        liquid = next_liquid
    return outputs

def auxiliary_value(data, rows, opening, discount_rate):
    row = rows[2]
    central_cost = sum((v['ebit_before_central'] for v in row['segments'].values())) - row['ebit']
    first_three = sum((r['fcff'] / (1 + discount_rate) ** r['year'] for r in rows[:3]))
    remaining_projects = sum((max(0, r['project_cash'] - r['growth_floor']) / (1 + discount_rate) ** (r['year'] - 3) for r in rows[3:]))
    result = {}
    for label, m in data['auxiliary_multiples'].items():
        business = sum((v['ebit_before_central'] * m[k] for k, v in row['segments'].items())) - central_cost * m['central'] - remaining_projects
        ev = first_three + business / (1 + discount_rate) ** 3
        result[label] = {'enterprise_value': ev, 'equity_value_per_share': (ev + opening['net_financial_value'] - opening['nci_open']) / data['meta']['shares_million'], 'remaining_project_pv_at_y3': remaining_projects, 'normalized_operating_earnings_y3': row['ebit']}
    return result

def run_case(data, scenario='base', financial_condition='par_available', discount_rate=None, checkpoint=None):
    d = scenario_inputs(data, scenario)
    b = d['base']
    r = b['discount_rate'] if discount_rate is None else discount_rate
    condition = d['financial_conditions'][financial_condition]
    opening = opening_bridge(d, condition)
    if checkpoint:
        checkpoint('opening_bridge', opening)
    rows = operating_budget(d, checkpoint)
    owners = owner_cash_budget(d, rows, condition, checkpoint)
    operations = value_operations(rows, r, b['terminal_growth'], b['minimum_growth_fixed_intensity'], b['tax_rate'])
    terminal_y5 = value_operations(rows, r, b['terminal_growth'], b['minimum_growth_fixed_intensity'], b['tax_rate'], from_year=5)
    shares = d['meta']['shares_million']
    equity = (operations['enterprise_value'] + opening['net_financial_value'] - opening['nci_open']) / shares
    terminal_equity = (terminal_y5['enterprise_value'] + owners[4]['net_financial_value'] - owners[4]['nci_value_proxy']) / shares
    feasible = all((x['group_hard_funding_gap'] < 1e-07 and x['parent']['hard_funding_gap'] < 1e-07 for x in owners))
    distributions_usable = feasible and condition['principal_recovery'] == 1.0
    jump = []
    for a, c in [(rows[4], rows[5]), (rows[7], operations['terminal_cashflow_y9'])]:
        jump.append({'from_year': a['year'], 'revenue_change': c['revenue'] / a['revenue'] - 1, 'nopat_change': c['nopat'] / a['nopat'] - 1 if a['nopat'] else None, 'fcff_change': c['fcff'] - a['fcff'], 'fcff_from': a['fcff'], 'fcff_to': c['fcff']})
    return {'scenario': scenario, 'financial_condition': financial_condition, 'discount_rate': r, 'opening_bridge': opening, 'operating_rows': rows, 'owner_rows': owners, 'operations': operations, 'equity_value_per_share': equity, 'terminal_equity_y5_per_share': terminal_equity, 'diagnostic_distributions_per_share': [x['common_dividend_per_share'] for x in owners[:5]], 'base_distributions_per_share': [x['common_dividend_per_share'] for x in owners[:5]] if distributions_usable else None, 'adoption_status': 'CONDITIONAL_CANDIDATE_NOT_REVIEWED' if distributions_usable else 'NOT_ADOPTABLE_HARD_GAP_OR_UNALLOCATED_LOSS', 'condition_assumptions': condition, 'feasible_without_new_external_finance': feasible, 'distributions_usable': distributions_usable, 'transition_review': jump, 'incremental_roic_y1_to_y5_diagnostic': (rows[4]['nopat'] - rows[0]['nopat']) / (rows[4]['invested_capital'] - rows[0]['invested_capital']) if abs(rows[4]['invested_capital'] - rows[0]['invested_capital']) > 1e-07 else None, 'auxiliary': auxiliary_value(d, rows, opening, r)}

def validate_case_result(result):

    def finite_tree(value):
        if isinstance(value, dict):
            for v in value.values():
                finite_tree(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                finite_tree(v)
        elif isinstance(value, (float, int)):
            assert isfinite(value), value
    finite_tree(result)
    for row in result['owner_rows']:
        p = row['parent']
        assert abs(p['re'] - (p['re_open'] + p['profit'] - p['reserve_appropriation'] - p['dividend'])) < 1e-07
        assert abs(p['reserve'] - (p['reserve_open'] + p['reserve_appropriation'])) < 1e-07
        assert abs(p['cash'] - (p['cash_before_draw'] + p['deposit_reclassification'] - p['dividend'])) < 1e-07
        assert abs(row['liquid_assets'] - (row['liquid_open'] + row['fcff'] + row['financial_income'] + row['claim_principal_release'] - row['nci_dividend'] - row['legacy_payment'] - p['dividend'])) < 1e-07
        assert abs(row['claim_remaining'] - (row['claim_open'] - row['claim_principal_release'])) < 1e-07
        assert p['dividend'] >= 0 and p['deposit_reclassification'] >= 0 and (p['deposits'] >= -1e-07)
        assert p['dividend_receivable'] >= -1e-07
    assert result['distributions_usable'] == (result['feasible_without_new_external_finance'] and result['condition_assumptions']['principal_recovery'] == 1.0)
    assert (result['base_distributions_per_share'] is not None) == result['distributions_usable']

def full_run(data, recorder):
    outputs = {'meta': data['meta']}

    def execute(label, d, scenario='base', condition='par_available', rate=None):
        return recorder.capture(label, {'data': d, 'scenario': scenario, 'condition': condition, 'discount_rate': rate}, {'invariants': 'see validate_case_result; economic adoption requires manual review'}, lambda: run_case(d, scenario, condition, rate, checkpoint=lambda stage, value: recorder.record(label + '__' + stage, value)), validate_case_result)
    cases = {}
    for scenario in ['base', 'cycle_delay', 'structural_competition', 'better_execution', 'upstream_delay']:
        cases[scenario] = execute('case_' + scenario, data, scenario)
    outputs['cases'] = cases
    conditional = {}
    for condition in ['par_available', 'par_two_year_delay_parent_pool_independent', 'par_two_year_delay_joint_parent_lock']:
        ends = {}
        for k, v in data['core_endpoints'].items():
            ends[k] = execute('condition_' + condition + '_' + k, data, 'base', condition, v['discount_rate'])
        conditional[condition] = {'role': 'CORE_CONDITION' if condition == 'par_available' else 'DIAGNOSTIC_NOT_CORE', 'endpoints': ends, 'distributions_usable': all((v['distributions_usable'] for v in ends.values())), 'distributions': ends['low']['base_distributions_per_share'], 'diagnostic_distributions': ends['low']['diagnostic_distributions_per_share'], 'adoption_status': ends['low']['adoption_status']}

        def same_distributions(values):
            assert all((abs(a - b) < 1e-08 for a, b in zip(values['low'], values['high'])))
        recorder.capture('condition_' + condition + '_distribution_alignment', {'condition': condition}, {'same_path_at_both_discount_rates': True}, lambda: {k: v['diagnostic_distributions_per_share'] for k, v in ends.items()}, same_distributions)
    outputs['conditional_core_ranges'] = conditional
    if conditional['par_available']['distributions_usable']:
        cr = conditional['par_available']
        outputs['conditional_interface_draft'] = {'schema_version': 1, 'method': 'annual_common_equity_irr_v1', 'currency': 'CNY', 'model_as_of': data['meta']['information_cutoff'], 'base_case_distributions_per_share': cr['distributions'], 'base_case_terminal_equity_value_range_per_share': {'year_5': {'low': cr['endpoints']['low']['terminal_equity_y5_per_share'], 'high': cr['endpoints']['high']['terminal_equity_y5_per_share']}}}
    else:
        outputs['conditional_interface_draft'] = None
    aux_mid = (cases['base']['auxiliary']['low']['equity_value_per_share'] + cases['base']['auxiliary']['high']['equity_value_per_share']) / 2
    core = conditional['par_available']['endpoints']
    main_mid = (core['low']['equity_value_per_share'] + core['high']['equity_value_per_share']) / 2
    outputs['cross_method_midpoint_gap_fraction'] = abs(aux_mid - main_mid) / abs(main_mid) if main_mid else None
    outputs['cross_method_action'] = 'If gap >25%, explain capital/margin/terminal assumptions; do not average or automatically take the lower method.'
    outputs['isolated_financial_diagnostics'] = {}
    for condition in ['principal_loss_10pct', 'zero_recovery_tail']:
        outputs['isolated_financial_diagnostics'][condition] = execute('isolated_' + condition, data, condition=condition)
    diagnostics = {}
    for label, kind, value in [('tax18', 'tax', 0.18), ('electrical_gm_down1pp', 'gm', -0.01), ('october_minus50', 'october', -50), ('parent_reserve_stop_eligible', 'reserve', False), ('parent_internal60', 'internal', 60), ('project_plus150', 'project', 150)]:
        d = deepcopy(data)
        if kind == 'tax':
            d['base']['tax_rate'] = value
        elif kind == 'gm':
            d['base']['segments']['electrical']['gm'] = [x + value for x in d['base']['segments']['electrical']['gm']]
        elif kind == 'october':
            d['snapshot']['october_net_financial_change_assumption'] = value
        elif kind == 'reserve':
            d['base']['parent']['continue_reserve_after_threshold'] = value
        elif kind == 'internal':
            d['base']['parent']['internal_capital_contributions'][:2] = [35, 25]
        elif kind == 'project':
            d['base']['project_cash'][:3] = [350, 290, 220]
        diagnostics[label] = execute('parameter_' + label, d)
    outputs['isolated_parameter_diagnostics'] = diagnostics
    return outputs
