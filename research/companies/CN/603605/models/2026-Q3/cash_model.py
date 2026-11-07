"""Cash-only derivative of published 188 primary. No operating forecast function is present.
Frozen operating rows are explicit arguments; no financial work at import."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

def merge(base, patch):
    out = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out

def at(path, year):
    return path[min(year, 5) - 1]

def calculate_cash(p, meta, frozen_operating_path, bridge_paid_cash=0.0, partial_state=None):
    """Single formal company/handcase chain. Results saved by runner BEFORE checks."""
    op = deepcopy(frozen_operating_path)
    if len(op) != 11 or [x["year"] for x in op] != list(range(1, 12)):
        raise ValueError("Exactly eleven frozen annual operations are required")
    f, parent, stock = p['finance'], p['parent'], p['shares']
    g_cash = f['reported_cash'] + f['reported_trading_assets'] - f['paid_october_dividend'] - f['minority_liquid_assets_estimate'] - p['capital']['opening_operating_cash']
    g_cash -= bridge_paid_cash
    opening_cash = g_cash
    p_cash = parent['opening_excess_cash']
    if bridge_paid_cash != 0.0:
        p_cash = parent['opening_excess_cash'] - bridge_paid_cash
    retained, statutory = parent['opening_legal_retained'], parent['opening_statutory_reserve']
    sub_retained = parent['opening_subsidiary_common_legal_retained']
    issued = stock['issued']
    treasury_cancel, treasury_incentive = stock['treasury_cancel_proposed'], stock['treasury_incentive']
    bond_book = f['bond_opening_book']
    loan = 0.0
    previous_conversion_div_adjustment = 0.0
    rows = []
    if partial_state is not None:
        partial_state["completed_rows"] = rows
    feasible = True
    for item in op[:5]:
        y = item['year']
        if partial_state is not None:
            partial_state['inflight_year'] = y
            partial_state['inflight_opening'] = {'group_cash':g_cash,'parent_cash':p_cash,'retained':retained,'statutory':statutory,'sub_retained':sub_retained,'issued':issued,'treasury_cancel':treasury_cancel,'treasury_incentive':treasury_incentive,'bond_book':bond_book,'loan':loan}
        g_open, p_open, loan_open = g_cash, p_cash, loan
        legal_open, reserve_open, sub_legal_open = retained, statutory, sub_retained
        issued_open = issued
        if stock['cancellation_year_budget'] == y:
            issued -= treasury_cancel
            treasury_cancel = 0.0  # outside shares unchanged by treasury cancellation
        incentive_cash = 0.0
        if stock['incentive_release_year_budget'] == y:
            treasury_incentive = 0.0
            incentive_cash = stock['incentive_cash_proceeds']
        bond_cash, bond_charge, conversion_shares = 0.0, 0.0, 0.0
        if y == 1:
            bond_cash = f['bond_coupon_y1']
            bond_charge = f['bond_book_charge_y1']
            bond_book += bond_charge - bond_cash
        elif y == 2:
            if f['bond_mode'] == 'repay':
                bond_cash = f['bond_redemption_y2']
                bond_charge = bond_cash - bond_book
            elif f['bond_mode'] == 'convert':
                conversion_price = f['bond_conversion_price'] - previous_conversion_div_adjustment
                if conversion_price <= 0:
                    raise ValueError('Nonpositive conditional conversion price; explicit redesign required')
                conversion_shares = f['bond_face'] / conversion_price
                issued += conversion_shares
            else:
                raise ValueError('Unknown bond branch; no automatic continuation')
            bond_book = 0.0
        outside = issued - treasury_cancel - treasury_incentive
        if outside <= 0:
            raise ValueError('Nonpositive ordinary participating share count')
        group_yield = max(g_open, 0) * f['after_tax_cash_yield']
        parent_yield = max(p_open, 0) * f['after_tax_cash_yield']
        loan_interest = loan_open * f['conditional_new_loan_rate']
        total_book_interest = bond_charge + loan_interest
        # Taxable profit must exist; an unsupported tax-loss refund is not financing.
        shield_capacity = max(item['parent_own_operating_profit'], 0) * f['parent_tax_rate'] / (1 - f['parent_tax_rate'])
        interest_tax_shield = min(max(total_book_interest, 0) * f['parent_tax_rate'], shield_capacity)
        common_profit = item['common_operating_accounting_profit'] + group_yield - total_book_interest + interest_tax_shield
        parent_own_profit = item['parent_own_operating_profit'] + parent_yield - total_book_interest + interest_tax_shield
        sub_profit = common_profit - parent_own_profit
        sub_retained += sub_profit
        settlement = at(parent['cash_settlement_delay'], y)
        # Settlement delay only relocates cash between parent and subsidiaries.
        g_pre = g_open + item['operating_common_fcf'] + group_yield + interest_tax_shield - bond_cash - loan_interest + incentive_cash
        p_pre = p_open + item['parent_own_operating_cash'] + parent_yield + interest_tax_shield - bond_cash - loan_interest + incentive_cash - settlement
        subs_cash_before_transfer = max(g_pre - p_pre, 0)
        upstream_request = at(parent['upstream_fraction'], y) * max(sub_profit, 0)
        upstream = min(upstream_request, max(sub_retained, 0), subs_cash_before_transfer)
        p_pre += upstream
        sub_retained -= upstream
        parent_profit = parent_own_profit + upstream  # newly declared and received same-year BUDGET
        profit_after_prior_losses = max(0.0, min(parent_profit, retained + parent_profit))
        statutory_add = min(0.1 * profit_after_prior_losses, max(0.5 * issued - statutory, 0))
        statutory += statutory_add
        retained += parent_profit - statutory_add
        funding_need = max(0.0, -g_pre, -p_pre)
        draw = min(funding_need, max(f['conditional_new_loan_limit'] - loan, 0))
        loan += draw
        g_pre += draw
        p_pre += draw
        # Financing support for a subsidiary cash deficit is a parent cash transfer,
        # not new consolidated profit/cash and not a legally automatic set-off.
        subsidiary_cash_support = min(max(p_pre - g_pre, 0), max(p_pre, 0))
        p_pre -= subsidiary_cash_support
        unfinanced_gap = max(0.0, -g_pre, -p_pre)
        if unfinanced_gap > 1e-7:
            feasible = False
        repayment = min(loan, max(min(g_pre, p_pre), 0))
        loan -= repayment
        g_pre -= repayment
        p_pre -= repayment
        target = max(common_profit, 0) * at(parent['payout_fraction'], y) + at(parent['distribution_target_addition'], y)
        dividend = max(0.0, min(target, max(g_pre, 0), max(p_pre, 0), max(retained, 0)))
        g_cash, p_cash = g_pre - dividend, p_pre - dividend
        retained -= dividend
        dps = dividend / outside
        # Differential dividend: adjustment uses total dividend / issued shares,
        # not dividend per non-treasury participating share (S10 p4 distinction).
        previous_conversion_div_adjustment = float(Decimal(str(dividend / issued)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        record = dict(item)
        record.update({'group_excess_cash_open': g_open, 'parent_excess_cash_open': p_open,
                       'group_net_finance_yield': group_yield, 'parent_net_finance_yield': parent_yield,
                       'bond_cash_paid': bond_cash, 'bond_book_expense': bond_charge, 'bond_book_end': bond_book,
                       'loan_open': loan_open, 'loan_interest': loan_interest, 'interest_tax_shield': interest_tax_shield,
                       'loan_draw': draw, 'loan_repayment': repayment, 'loan_end': loan,
                       'common_accounting_profit': common_profit, 'parent_own_profit': parent_own_profit,
                       'subsidiary_common_profit': sub_profit, 'upstream_declared_received': upstream,
                       'parent_profit_including_new_upstream': parent_profit, 'parent_cash_settlement_delay': settlement,
                       'subsidiary_cash_support': subsidiary_cash_support,
                       'legal_retained_open': legal_open, 'legal_retained_end': retained,
                       'subs_legal_open': sub_legal_open, 'subs_legal_end': sub_retained,
                       'statutory_reserve_open': reserve_open, 'statutory_addition': statutory_add,
                       'statutory_reserve_end': statutory, 'issued_open': issued_open, 'issued_end': issued,
                       'conversion_shares': conversion_shares, 'participating_shares': outside,
                       'conversion_dividend_adjustment': previous_conversion_div_adjustment,
                       'incentive_cash_proceeds': incentive_cash,
                       'distribution_target': target, 'distribution_total': dividend, 'distribution_per_share': dps,
                       'group_excess_cash_end': g_cash, 'parent_excess_cash_end': p_cash,
                       'unfinanced_gap': unfinanced_gap})
        rows.append(record)
    r, g = p['discount_rate'], p['steady_growth']
    if r <= g:
        raise ValueError('Discount rate must exceed steady growth')
    continuation_5 = sum(v['operating_common_fcf'] / (1 + r) ** (v['year'] - 5) for v in op[5:10])
    terminal_10 = op[10]['operating_common_fcf'] / (r - g)
    operating_value_5 = continuation_5 + terminal_10 / (1 + r) ** 5
    noncash_value_5 = f['noncash_investments_book'] * f['noncash_recovery_fraction'] * (1 + f['noncash_annual_return']) ** 5
    finance_bridge_5 = g_cash + noncash_value_5 - loan  # bond fully resolved in Y2; not subtracted again
    terminal_5 = operating_value_5 + finance_bridge_5
    terminal_shares = rows[-1]['participating_shares']
    dividend_pv = sum(row['distribution_per_share'] / (1 + r) ** row['year'] for row in rows)
    terminal_ps = terminal_5 / terminal_shares
    auxiliary_terminal_5 = op[4]['zero_growth_maintainable_common_cash_profit'] / r + finance_bridge_5
    current = dividend_pv + terminal_ps / (1 + r) ** 5
    auxiliary = dividend_pv + auxiliary_terminal_5 / terminal_shares / (1 + r) ** 5
    if terminal_5 < 0 or auxiliary_terminal_5 < 0:
        feasible = False  # no unsupported precise limited-liability/exit floor
    d0 = date.fromisoformat(meta['valuation_date'])
    anniversaries = [d0.replace(year=d0.year + k).isoformat() for k in range(1, 6)]
    return {'meta': deepcopy(meta), 'feasible': feasible, 'anniversary_dates': anniversaries,
            'opening_common_excess_financial_assets': opening_cash, 'opening_bond_deduction': 0.0,
            'operating_path': op, 'cash_legal_share_path': rows,
            'distributions_per_share': [x['distribution_per_share'] for x in rows],
            'year5_operating_value': operating_value_5, 'year5_finance_bridge': finance_bridge_5,
            'year5_noncash_investments': noncash_value_5, 'year5_terminal_equity_value_per_share': terminal_ps if feasible else None,
            'current_value_per_share': current if feasible else None,
            'auxiliary_zero_growth_value_per_share': auxiliary if feasible else None,
            'terminal_pv_share_of_current_value': (terminal_ps / (1 + r) ** 5 / current) if feasible and current else None,
            'two_method_gap_fraction': abs(current - auxiliary) / abs(current) if feasible and current else None,
            'requires_method_gap_explanation': bool(feasible and current and abs(current - auxiliary) / abs(current) > 0.25),
            'unchecked_numeric_diagnostic': {'current': current, 'auxiliary': auxiliary, 'terminal': terminal_ps}}

def validate_result(p, result):
    """Post-save invariants: never constrain value to a desired price/profit range."""
    def close(a, b, label):
        if abs(a - b) > 1e-7 * max(1.0, abs(a), abs(b)):
            raise AssertionError(f'{label}: {a} != {b}')
    if result['meta']['model_as_of'] != result['meta']['information_cutoff']:
        raise AssertionError('cutoff/model_as_of mismatch')
    if len(result['distributions_per_share']) != 5 or result['anniversary_dates'][-1] != result['meta']['year_5_date']:
        raise AssertionError('Five-year/date contract')
    for operating in result['operating_path']:
        close(operating['nopat_common_before_ppa'], sum(b['nopat_full'] * b['ownership'] for b in operating['brands'].values()), 'common operating attribution')
        close(operating['nopat_common_before_ppa'] + operating['nci_nopat'], sum(b['nopat_full'] for b in operating['brands'].values()), 'NCI scope')
        close(operating['operating_common_fcf'], operating['nopat_common_before_ppa'] + operating['depreciation_excluding_rou'] - operating['maintenance_capex'] - operating['ordinary_growth_capex'] - operating['factory_cash'] - operating['delta_nwc'] - operating['delta_operating_cash'], 'operating capital bridge')
    for row in result['cash_legal_share_path']:
        close(row['group_excess_cash_end'], row['group_excess_cash_open'] + row['operating_common_fcf'] + row['group_net_finance_yield'] + row['interest_tax_shield'] - row['bond_cash_paid'] - row['loan_interest'] + row['incentive_cash_proceeds'] + row['loan_draw'] - row['loan_repayment'] - row['distribution_total'], 'group cash')
        close(row['parent_excess_cash_end'], row['parent_excess_cash_open'] + row['parent_own_operating_cash'] + row['parent_net_finance_yield'] + row['interest_tax_shield'] - row['bond_cash_paid'] - row['loan_interest'] + row['incentive_cash_proceeds'] - row['parent_cash_settlement_delay'] + row['upstream_declared_received'] + row['loan_draw'] - row['subsidiary_cash_support'] - row['loan_repayment'] - row['distribution_total'], 'parent cash')
        close(row['legal_retained_end'], row['legal_retained_open'] + row['parent_profit_including_new_upstream'] - row['statutory_addition'] - row['distribution_total'], 'legal retained')
        close(row['subs_legal_end'], row['subs_legal_open'] + row['subsidiary_common_profit'] - row['upstream_declared_received'], 'subs legal')
        close(row['loan_end'], row['loan_open'] + row['loan_draw'] - row['loan_repayment'], 'loan')
        close(row['distribution_per_share'] * row['participating_shares'], row['distribution_total'], 'per-share dividend')
        if row['distribution_total'] < -1e-9 or row['distribution_total'] > row['distribution_target'] + 1e-7:
            raise AssertionError('Distribution target/cash bound')
        if row['distribution_total'] > 0 and min(row['parent_excess_cash_end'], row['group_excess_cash_end'], row['legal_retained_end']) < -1e-7:
            raise AssertionError('Paid dividend despite funding/legal deficit')
        if result['feasible'] and row['unfinanced_gap'] > 1e-7:
            raise AssertionError('Unfunded scenario labeled feasible')
        if result['feasible'] and row['parent_excess_cash_end'] > row['group_excess_cash_end'] + 1e-7:
            raise AssertionError('Parent cash counted without funding subsidiary cash deficit')
    if p['finance']['bond_mode'] == 'convert' and result['cash_legal_share_path'][1]['bond_cash_paid']:
        raise AssertionError('Conversion and redemption double counted')
    if p['finance']['bond_mode'] == 'repay' and any(x['conversion_shares'] for x in result['cash_legal_share_path']):
        raise AssertionError('Repayment and conversion dilution double counted')
    if p['finance']['bond_mode'] == 'repay':
        close(sum(x['bond_cash_paid'] for x in result['cash_legal_share_path']), p['finance']['bond_coupon_y1'] + p['finance']['bond_redemption_y2'], 'exact bond cash obligation once')
    close(result['cash_legal_share_path'][-1]['bond_book_end'], 0.0, 'bond resolved before TV5')
    last = result['cash_legal_share_path'][-1]
    close(result['year5_finance_bridge'], last['group_excess_cash_end'] + result['year5_noncash_investments'] - last['loan_end'], 'post-distribution terminal financial bridge')
    close(result['opening_bond_deduction'], 0.0, 'No duplicate initial debt bridge')
    return {'status': 'passed', 'checks': 'cash, parent legal/cash, NCI scope, debt branch, share/date, funding'}
