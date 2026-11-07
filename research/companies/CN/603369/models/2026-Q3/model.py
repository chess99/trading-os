#!/usr/bin/env python3
"""Ordinary offline frozen financial computation; no permission ticket.
No external packages/network. Outputs are accounting/valuation scenarios, not proof
of economic correctness. Source facts and bounded judgement remain distinguishable.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def year_fraction(start, end):
    years = end.year - start.year
    anniversary = start.replace(year=start.year + years)
    if anniversary > end:
        years -= 1
        anniversary = start.replace(year=start.year + years)
    following = anniversary.replace(year=anniversary.year + 1)
    return years + (end-anniversary).days / (following-anniversary).days


def quarter_end(year, quarter):
    month = quarter * 3
    day = 31 if month in (3, 12) else 30
    return dt.date(year, month, day)


def periods():
    result = [(2026, 4, 2/3, dt.date(2026, 12, 31))]
    for year in range(2027, 2031):
        result.extend((year, q, 1.0, quarter_end(year, q)) for q in range(1, 5))
    result.extend((2031, q, 1.0, quarter_end(2031, q)) for q in range(1, 4))
    result.append((2031, 4, 1/3, dt.date(2031, 10, 31)))
    return result


def case_input(original, name):
    x = copy.deepcopy(original)
    x['case_name'] = name
    if name in x['case_changes']:
        x['base'].update(copy.deepcopy(x['case_changes'][name]))
    if name == 'expense_recovery_slow':
        for i in range(5):
            extra_aftertax=(x['base']['selling_ratio'][i]-original['base']['selling_ratio'][i])*x['base']['revenue'][i]*(1-x['base']['income_tax_rate'])
            x['base']['sales_sub_legal_profit_proxy'][i]-=extra_aftertax*0.95
            x['base']['mother_own_posttax_operating_profit'][i]-=extra_aftertax*0.05
    if name == 'upstream_delayed_12m':
        x['liquidity']['upstream_delay_quarters'] = 4
    if name == 'capital_cash_60':
        # Cash-only diagnostic: additional work/payment with no assumed sales benefit.
        x['base']['completion_growth'] = [v + 200000000 for v in x['base']['completion_growth']]
    if name == 'financial_recovery_85':
        x['finance']['noncurrent_financial_recovery_factor'] = 0.85
        x['finance']['financial_DTA_utilization_factor'] = 0.0
    if name == 'zero_growth_maintenance':
        x['maturity']['nominal_growth'] = 0.0
        x['maturity']['maintenance_to_da'] = 1.10
        x['maturity']['nominal_growth_range'] = [0.0,0.0]
        x['maturity']['maintenance_to_da_range'] = [1.10,1.10]
    if name == 'structural_weak':
        x['maturity']['nominal_growth'] = 0.0
        x['capital_bridge']['post_2031_cash_tail'] = 570000000
        x['maturity']['nominal_growth_range'] = [0.0,0.0]
        # 970m less five-year growth cash: cancel 700m uncommitted work, defer 270m.
    if name == 'better_growth':
        x['maturity']['nominal_growth'] = 0.02
        x['maturity']['incremental_roic'] = 0.12
        x['maturity']['full_2032_nonlease_da'] = 650000000
        x['maturity']['nominal_growth_range'] = [0.01,0.02]
        x['maturity']['incremental_roic_range'] = [0.10,0.12]
    return x


def quarter_budget(x, year, q):
    b, s = x['base'], x['seasonality']
    i, j = year - 2027, q - 1
    revenue = b['revenue'][i] * s['revenue_weights'][j]
    gross_margin = (b['a_plus_share'][i]*b['a_plus_margin'][i]
                    + b['a_special_share'][i]*b['a_special_margin'][i]
                    + b['other_share'][i]*b['other_margin'][i])
    selling = b['revenue'][i]*b['selling_ratio'][i]*s['selling_accounting_expense_weights'][j]
    admin = b['revenue'][i]*b['admin_ratio'][i]*s['admin_rd_weights'][j]
    rd = b['revenue'][i]*b['rd_ratio']*s['admin_rd_weights'][j]
    ebit = revenue*gross_margin - selling - admin - rd - revenue*b['sales_tax_ratio']
    nopat = ebit*(1-b['income_tax_rate'])
    wc_parts = {k: values[i]*s['other_wc_category_weights'][k][j] for k, values in b['other_wc'].items()}
    wc_parts['external_contract_liability_change'] += s['external_contract_liability_seasonal_change'][j]
    # Liability increase is a source of cash; listed reductions are uses of cash.
    wc_use = (wc_parts['receivables_prepay_increase']
              + wc_parts['operating_supplier_payable_reduction']
              + wc_parts['employee_payable_reduction']
              + wc_parts['current_operating_tax_payable_reduction']
              - wc_parts['external_contract_liability_change']
              - wc_parts['preaccrued_expense_net_change'])
    return {
        'revenue': revenue, 'ebit': ebit, 'nopat': nopat,
        'maintenance': b['maintenance'][i]*s['capex_weights'][j],
        'growth_capex': b['completion_growth'][i]*s['capex_weights'][j],
        'da': b['nonlease_da'][i]*s['da_weights'][j],
        'inventory_cash_use': b['inventory_investment'][i]*s['inventory_weights'][j],
        'other_wc_cash_use': wc_use, 'wc_parts': wc_parts,
        'mother_own_profit': b['mother_own_posttax_operating_profit'][i]*s['mother_operating_profit_weights'][j],
        'sales_sub_legal_profit_proxy': b['sales_sub_legal_profit_proxy'][i]*s['sales_sub_legal_profit_weights'][j],
        'upstream_declaration': b['declared_cash_dividend_from_sales_sub'][i]*s['upstream_cash_dividend_declaration_weights'][j]
    }


def stub_budget(x):
    s = x['stub_2026']
    return {
        'revenue': None, 'ebit': s['full_q4_nopat']/(1-x['base']['income_tax_rate']),
        'nopat': s['full_q4_nopat'], 'maintenance': s['full_q4_maintenance_cash'],
        'growth_capex': s['full_q4_completion_cash'], 'da': s['full_q4_nonlease_da'],
        'inventory_cash_use': s['full_q4_inventory_investment'],
        'other_wc_cash_use': s['full_q4_other_wc_cash_use'],
        'wc_parts': {'external_contract_liability_change':300000000, 'receivables_prepay_increase':-50000000},
        'mother_own_profit':s['full_q4_mother_own_posttax_profit'],
        'sales_sub_legal_profit_proxy':s['full_q4_sales_sub_legal_profit_proxy'],
        'upstream_declaration':0.0
    }


def opening_states(x, obs):
    q = obs['q3_2026_consolidated']
    m = obs['h1_2026_mother']
    f = x['finance']
    a, l = q['assets'], q['liabilities']
    monetary_excess = a['monetary_funds'] - a['cash_and_cash_equivalents']
    finance_dtl = (f['PL_FV_DTL_proxy'] + f['OCI_FV_DTL_proxy']
                   + monetary_excess*f['noncash_monetary_excess_tax_rate_proxy'])
    haircut = a['other_noncurrent_financial_assets']*(1-f['noncurrent_financial_recovery_factor'])
    # Limited attribution to assets carrying earlier taxable gains; no new loss credit.
    relief = min(haircut*x['base']['income_tax_rate'], f['PL_FV_DTL_proxy'])*f['haircut_gains_attribution_fraction']
    finance_dtl = max(finance_dtl-relief, 0.0)
    # Operating cash-rent convention: explicit lease liabilities are not debt here.
    # Q3 undetailed current maturity is conservatively a nonlease-debt proxy.
    total_debt = l['short_debt']+l['long_debt']+l['current_noncurrent_liabilities']
    state = {
        'group_cash':a['cash_and_cash_equivalents']+x['opening']['group_cash_october_change'],
        'mother_cash':m['cash_equivalents']+x['opening']['mother_cash_june_to_october_change'],
        'debt':total_debt,
        'mother_debt':l['long_debt']+f['mother_current_principal_component'],
        'trading':a['trading_financial_assets'],
        'noncurrent_recovery':a['other_noncurrent_financial_assets']-haircut,
        'noncurrent_aftertax_retained_return':0.0,
        'other_financial':a['longterm_equity_investments']+a['other_equity_instruments']+monetary_excess,
        'finance_dta_value':f['financial_DTA_proxy']*f['financial_DTA_utilization_factor'],
        'finance_dtl':finance_dtl,
        'trading_dtl_reserve':f['PL_FV_DTL_proxy']*f['redemption_tax_share_of_PL_DTL_proxy'],
        'operating_net_dta':a['deferred_tax_assets']-f['financial_DTA_proxy']-(l['deferred_tax_liabilities']-(finance_dtl+relief)),
        'liability_basis_dta':x['operating_tax']['opening_liability_basis_DTA_proxy'],
        'inventory':a['inventory'],
        'preaccrued_expense':x['operating_tax']['preaccrued_expense_opening_proxy'],
        'operating_receivables_prepay':a['notes_receivable']+a['receivables']+a['receivables_financing']+a['prepayments']+a['other_receivables']+a['other_current_assets'],
        'operating_supplier_payables':l['trade_payables']+l['trade_notes_payable']-x['capital_bridge']['current_trade_payable_capital_proxy_excluded_from_wc'],
        'external_contract_liabilities':l['contract_liabilities'],
        'employee_payables':l['employee_payables'], 'current_operating_tax_payables':l['taxes_payable'],
        'mother_legal_retained_proxy':x['opening']['mother_legal_retained_earnings_t0_proxy'],
        'sales_sub_legal_retained_proxy':x['opening']['sales_sub_legal_retained_proxy'],
        'sales_sub_reserve_remaining':x['opening']['sales_sub_remaining_statutory_reserve']
    }
    return state


def nfa(state):
    return (state['group_cash']+state['trading']+state['noncurrent_recovery']+state['noncurrent_aftertax_retained_return']
            +state['other_financial']+state['finance_dta_value']-state['finance_dtl']-state['debt'])


def terminal_value(x, k, growth, roic, maintenance_ratio, multiple):
    # Next twelve months: Nov-Dec2031 + Jan-Oct2032, not all of FY2032 plus extra months.
    future = copy.deepcopy(x)
    for key in ('revenue','inside','outside','other_revenue'):
        future['base'][key][4] *= (1+growth)
    q31 = quarter_budget(x, 2031, 4)['nopat']
    q32 = [quarter_budget(future, 2031, q)['nopat'] for q in range(1, 5)]
    forward_nopat = q31*2/3 + sum(q32[:3]) + q32[3]/3
    da = x['base']['nonlease_da'][4]/6 + x['maturity']['full_2032_nonlease_da']*5/6
    maintenance = da*maintenance_ratio
    reinvestment = forward_nopat*growth/roic if growth else 0.0
    fcff = forward_nopat+da-maintenance-reinvestment
    planned_2031_last_two_months = x['base']['completion_growth'][4]*x['seasonality']['capex_weights'][3]*2/3
    tail = x['capital_bridge']['post_2031_cash_tail'] + planned_2031_last_two_months
    tail_pv_at_Y5 = sum(tail*w/(1+k)**t for w,t in zip(x['capital_bridge']['tail_payment_weights'],x['capital_bridge']['tail_payment_years_after_Y5']))
    ev = fcff/(k-growth)-tail_pv_at_Y5
    current_normal_nopat = sum(quarter_budget(x,2031,q)['nopat'] for q in range(1,5))
    normalized_earning_after_extra_maintenance = current_normal_nopat+x['base']['nonlease_da'][4]-maintenance
    alternative_ev = normalized_earning_after_extra_maintenance*multiple-tail_pv_at_Y5
    return {'forward_nopat':forward_nopat,'forward_da':da,'forward_maintenance':maintenance,
            'growth_reinvestment_includes_inventory_and_fixed_capital':reinvestment,
            'forward_fcff':fcff,'tail_cash_after_Y5':tail,'tail_pv_at_Y5':tail_pv_at_Y5,
            'operating_EV_Y5':ev,'normal_earnings_EV_Y5':alternative_ev,
            'normal_NOPAT_before_multiple':normalized_earning_after_extra_maintenance}


def evaluate_case(x, obs):
    b,f,s = x['base'],x['finance'],x['seasonality']
    start = dt.date.fromisoformat(x['valuation_date'])
    end = dt.date.fromisoformat(x['terminal_date'])
    shares = obs['q3_2026_consolidated']['equity']['ordinary_shares']
    state = opening_states(x,obs)
    initial_state = copy.deepcopy(state)
    initial_nfa = nfa(state)
    qcash = obs['q3_2026_consolidated']['assets']['cash_and_cash_equivalents']
    qtrade = obs['q3_2026_consolidated']['assets']['trading_financial_assets']
    q4_finance_net = (qcash*f['cash_aftertax_yield']+max(qtrade-f['trading_equity_nonfunding_proxy'],0)*f['trading_aftertax_yield']
                     -state['debt']*f['debt_interest_gross_rate']*(1-b['income_tax_rate']))/4
    annual_ni = {2026:obs['q3_2026_consolidated']['income_9m']['net_profit']+x['stub_2026']['full_q4_nopat']+q4_finance_net}
    mother_annual_profit = {2026:x['opening']['mother_2026_full_year_profit_for_policy_floor_proxy']}  # Not a reported FY2026 amount.
    queue, tax_queue, rows, dividends, warnings = [],[],[],[],[]
    total_fcff=0.0
    total_finance_returns=0.0
    total_dividends=0.0
    last_date=start
    for idx,(year,q,frac,date) in enumerate(periods()):
        qb = stub_budget(x) if year==2026 else quarter_budget(x,year,q)
        begin_nfa=nfa(state)
        begin_group=state['group_cash']
        begin_mother=state['mother_cash']
        begin_debt=state['debt']
        begin_mother_debt=state['mother_debt']
        budget_dt=frac/4
        cash_interest=begin_group*f['cash_aftertax_yield']*budget_dt
        mother_interest_income=begin_mother*f['cash_aftertax_yield']*budget_dt
        trading_income=max(state['trading']-f['trading_equity_nonfunding_proxy'],0)*f['trading_aftertax_yield']*budget_dt
        # Net economic return stays in the investment claim: not cash, legal profit
        # or a promise of redemption at Y5. The primary value uses current NFA.
        noncurrent_retained_return=(state['noncurrent_recovery']+state['noncurrent_aftertax_retained_return'])*f['noncurrent_aftertax_retained_total_return_proxy']*budget_dt
        state['noncurrent_aftertax_retained_return']+=noncurrent_retained_return
        debt_interest=begin_debt*f['debt_interest_gross_rate']*(1-b['income_tax_rate']*f['debt_interest_tax_deductible_fraction'])*budget_dt
        mother_debt_interest=begin_mother_debt*f['debt_interest_gross_rate']*(1-b['income_tax_rate']*f['debt_interest_tax_deductible_fraction'])*budget_dt
        inv=qb['inventory_cash_use']*frac
        other_wc=qb['other_wc_cash_use']*frac
        early_payment=0.0
        immediate_tax_release=0.0
        if (x['case_name']=='preaccrual_cash_early' and year==x['operating_tax']['stress_payment_year'] and q==x['operating_tax']['stress_payment_quarter']):
            early_payment=min(x['operating_tax']['stress_early_accrual_payment'],state['preaccrued_expense'])
            fraction=x['operating_tax']['immediately_deductible_fraction']
            immediate_tax_release=early_payment*b['income_tax_rate']*fraction
            tax_queue.append({'due':idx+x['operating_tax']['remaining_tax_release_lag_quarters'], 'amount':early_payment*b['income_tax_rate']*(1-fraction)})
            state['preaccrued_expense']-=early_payment
            other_wc+=early_payment
        due_tax=sum(item['amount'] for item in tax_queue if item['due']==idx)
        release=min(immediate_tax_release+due_tax,state['liability_basis_dta'])
        state['liability_basis_dta']-=release
        delta_operating_dta=-release
        state['operating_net_dta']+=delta_operating_dta
        capex=(qb['maintenance']+qb['growth_capex'])*frac
        nopat=qb['nopat']*frac
        da=qb['da']*frac
        fcff=nopat+da-capex-inv-other_wc-delta_operating_dta
        mother_other_wc=0.0
        for key,value in qb['wc_parts'].items():
            sign=-1.0 if key in ('external_contract_liability_change','preaccrued_expense_net_change') else 1.0
            mother_other_wc+=sign*value*frac*b['mother_wc_category_shares'][key]
        mother_other_wc+=early_payment*0.05
        mother_fcff=(qb['mother_own_profit']*frac+da*b['mother_da_share']-capex*b['mother_capex_share']
                     -inv*b['mother_inventory_share']-mother_other_wc
                     -delta_operating_dta*b['mother_operating_tax_adjustment_share'])
        state['group_cash']+=fcff+cash_interest+trading_income-debt_interest
        state['mother_cash']+=mother_fcff+mother_interest_income-mother_debt_interest
        state['inventory']+=inv
        parts={key:value*frac for key,value in qb['wc_parts'].items()}
        state['operating_receivables_prepay']+=parts.get('receivables_prepay_increase',0)
        state['operating_supplier_payables']-=parts.get('operating_supplier_payable_reduction',0)
        state['external_contract_liabilities']+=parts.get('external_contract_liability_change',0)
        state['employee_payables']-=parts.get('employee_payable_reduction',0)
        state['current_operating_tax_payables']-=parts.get('current_operating_tax_payable_reduction',0)
        redemption=tax_paid=fee=principal=mother_principal=0.0
        if year==2027 and q==1:
            redemption=min(f['trading_redemption_2027q1'],max(state['trading']-f['trading_equity_nonfunding_proxy'],0))
            redemption_fraction=redemption/state['trading'] if state['trading'] else 0
            tax_paid=min(state['trading_dtl_reserve']*redemption_fraction,state['finance_dtl'])
            fee=redemption*f['redemption_fee_rate']
            state['trading']-=redemption
            state['trading_dtl_reserve']-=tax_paid
            state['finance_dtl']-=tax_paid
            state['group_cash']+=redemption-tax_paid-fee
            principal+=f['short_principal_payment_2027q1']
        if year==2027 and q==2:
            principal+=f['other_current_nonlease_principal_paid_2027q2']
            mother_principal+=f['mother_current_principal_component']
        # Principal events are calendar year-end events; NOT pro-rated into October2031.
        if year>=2027 and q==f['long_principal_payment_quarter'] and frac==1.0:
            amount=f['long_principal_each_full_year'][year-2027]
            principal+=amount
            mother_principal+=amount
        principal=min(principal,state['debt'])
        mother_principal=min(mother_principal,state['mother_debt'])
        state['group_cash']-=principal
        state['mother_cash']-=mother_principal
        state['debt']-=principal
        state['mother_debt']-=mother_principal
        net_finance_cash=cash_interest+trading_income-debt_interest-fee
        net_finance=net_finance_cash+noncurrent_retained_return
        if year>=2027:
            # No unrealized investment markup is used to increase payout intent.
            annual_ni[year]=annual_ni.get(year,0)+nopat+net_finance_cash
        own_mother_profit=qb['mother_own_profit']*frac+mother_interest_income-mother_debt_interest
        state['mother_legal_retained_proxy']+=own_mother_profit
        if year>=2027:
            mother_annual_profit[year]=mother_annual_profit.get(year,0)+own_mother_profit
        child_earnings=qb['sales_sub_legal_profit_proxy']*frac
        reserve=min(state['sales_sub_reserve_remaining'],max(child_earnings,0)*0.10)
        state['sales_sub_reserve_remaining']-=reserve
        state['sales_sub_legal_retained_proxy']+=child_earnings-reserve
        declared=min(qb['upstream_declaration']*frac,max(state['sales_sub_legal_retained_proxy'],0))
        state['sales_sub_legal_retained_proxy']-=declared
        state['mother_legal_retained_proxy']+=declared
        if year>=2027:
            mother_annual_profit[year]=mother_annual_profit.get(year,0)+declared
        if declared:
            queue.append({'due':idx+x['liquidity']['upstream_delay_quarters'],'remaining':declared})
        upstream=0.0
        sub_cash_before_upstream=state['group_cash']-state['mother_cash']
        period_upstream_available=max(sub_cash_before_upstream-x['liquidity']['minimum_subpool_cash_before_upstream'],0)*x['liquidity']['subpool_eligible_cash_fraction_for_sales_sub_dividend_proxy']
        for item in queue:
            if item['due']<=idx and item['remaining']>0:
                payment=min(item['remaining'],period_upstream_available)
                period_upstream_available-=payment
                state['mother_cash']+=payment
                item['remaining']-=payment
                upstream+=payment
        ordinary=desired=policy_floor=0.0
        if year>=2027 and q==s['ordinary_dividend_quarter']:
            previous_profit=annual_ni[year-1]
            desired=max(previous_profit,0)*b['ordinary_payout_intention']
            policy_floor=max(mother_annual_profit.get(year-1,0),0)*0.30
            pre_mother_cash=state['mother_cash']
            pre_group_cash=state['group_cash']
            pre_legal_retained=state['mother_legal_retained_proxy']
            ordinary=max(0,min(desired,state['mother_legal_retained_proxy'],
                               state['mother_cash']-x['liquidity']['mother_cash_floor'],
                               state['group_cash']-x['liquidity']['group_cash_floor']))
            state['group_cash']-=ordinary
            state['mother_cash']-=ordinary
            state['mother_legal_retained_proxy']-=ordinary
            dividends.append({'payment_date':date.isoformat(),'profit_reference_year':year-1,
                              'reference_group_profit':previous_profit,'intended_total':desired,
                              'actual_cash_budget_total':ordinary,'per_share':ordinary/shares,
                              'mother_policy_floor_proxy':policy_floor,'policy_floor_shortfall':max(policy_floor-ordinary,0),
                              'mother_cash_before_payment':pre_mother_cash,'group_cash_before_payment':pre_group_cash,
                              'sub_cash_before_payment':pre_group_cash-pre_mother_cash,
                              'mother_legal_retained_before_payment':pre_legal_retained,
                              'mother_cash_headroom_before_payment':pre_mother_cash-x['liquidity']['mother_cash_floor'],
                              'group_cash_headroom_before_payment':pre_group_cash-x['liquidity']['group_cash_floor'],
                              'actual_upstream_cash_this_period':upstream,
                              'declared_upstream_not_yet_due':sum(z['remaining'] for z in queue if z['due']>idx),
                              'declared_upstream_due_but_unpaid':sum(z['remaining'] for z in queue if z['due']<=idx)})
            if ordinary+1<policy_floor:
                warnings.append(f'{year}: cash budget below mother policy-floor proxy; governance exception/adjustment required, not automatic permission')
        sub_cash=state['group_cash']-state['mother_cash']
        if state['mother_cash']<0 or sub_cash<0 or state['group_cash']<0:
            warnings.append(f'{date}: operating/financing cash deficit; not repaired with fictional borrowing')
        if state['group_cash']<x['liquidity']['group_cash_floor']:
            warnings.append(f'{date}: operating commitments draw group cash below precautionary buffer')
        if state['mother_cash']<x['liquidity']['mother_cash_floor']:
            warnings.append(f'{date}: mother buffer below budget outside ordinary payout')
        end_nfa=nfa(state)
        continuity=end_nfa-begin_nfa-fcff-net_finance+ordinary
        elapsed=year_fraction(start,date)
        interval=elapsed-year_fraction(start,last_date)
        row={'date':date.isoformat(),'year':year,'quarter':q,'quarter_fraction':frac,'t':elapsed,'dt':interval,
             'NOPAT':nopat,'nonlease_DA':da,'capital_cash':capex,'inventory_cash_use':inv,
             'other_WC_cash_use':other_wc,'operating_net_DTA_change':delta_operating_dta,'FCFF':fcff,
             'mother_FCFF_before_upstream':mother_fcff,'net_finance_return':net_finance,
             'net_finance_cash_return':net_finance_cash,'noncurrent_aftertax_retained_return':noncurrent_retained_return,
             'financial_redemption':redemption,'old_financial_DTL_cash_payment':tax_paid,'debt_principal_cash':principal,
             'declared_sub_dividend':declared,'actual_sub_dividend_cash':upstream,
             'ordinary_dividend':ordinary,'mother_cash':state['mother_cash'],'sub_cash':sub_cash,'group_cash':state['group_cash'],
             'NFA_begin':begin_nfa,'NFA_end':end_nfa,'debt_end':state['debt'],
             'mother_legal_retained_proxy':state['mother_legal_retained_proxy'],
             'sales_sub_legal_retained_proxy':state['sales_sub_legal_retained_proxy'],
             'gross_accrual_settlement_matched_by_new_accrual':x['operating_tax']['preaccrued_expense_opening_proxy']*x['operating_tax']['replacement_fraction_of_opening_accrual_per_full_year']*budget_dt,
             'early_extra_accrual_settlement':early_payment,'NFA_continuity_residual':continuity}
        rows.append(row)
        total_fcff+=fcff
        total_finance_returns+=net_finance
        total_dividends+=ordinary
        last_date=date
    k=x['maturity']['required_return']
    g=x['maturity']['nominal_growth']
    roi=x['maturity']['incremental_roic']
    mr=x['maturity']['maintenance_to_da']
    multiple=x['maturity']['normal_NOPAT_multiple']
    tv=terminal_value(x,k,g,roi,mr,multiple)
    terminal_t=year_fraction(start,end)
    final_nfa=nfa(state)
    pv_d=sum(row['ordinary_dividend']/(1+k)**row['t'] for row in rows)
    pv_fcff=sum(row['FCFF']/(1+k)**row['t'] for row in rows)
    # Primary EV + current assets is independent of the holder's distribution path.
    current_operating_ev=pv_fcff+tv['operating_EV_Y5']/(1+k)**terminal_t
    current_value=current_operating_ev+initial_nfa
    normal_operating_ev=pv_fcff+tv['normal_earnings_EV_Y5']/(1+k)**terminal_t
    normal_value=normal_operating_ev+initial_nfa
    y5=tv['operating_EV_Y5']+final_nfa
    holder_pv=pv_d+y5/(1+k)**terminal_t
    # This algebra describes the chosen path, NOT an economically required haircut.
    conditional_carry=sum((row['net_finance_return']-row['NFA_begin']*((1+k)**row['dt']-1))/(1+k)**row['t'] for row in rows)
    valuation_grid=[]
    for test_k in x['maturity']['required_return_range']:
        for test_g in sorted(set(x['maturity']['nominal_growth_range'])):
            for test_roi in x['maturity']['incremental_roic_range']:
                for test_mr in sorted(set(x['maturity']['maintenance_to_da_range'])):
                    tested=terminal_value(x,test_k,test_g,test_roi,test_mr,multiple)
                    explicit_ev=sum(row['FCFF']/(1+test_k)**row['t'] for row in rows)
                    val=explicit_ev+tested['operating_EV_Y5']/(1+test_k)**terminal_t+initial_nfa
                    valuation_grid.append({'k':test_k,'g':test_g,'incremental_roic':test_roi,'maintenance_to_da':test_mr,'current_EV_plus_NFA_per_share':val/shares})
    alternate_grid=[]
    for test_k in x['maturity']['required_return_range']:
        for mult in x['maturity']['normal_NOPAT_multiple_range']:
            tested=terminal_value(x,test_k,g,roi,mr,mult)
            explicit_ev=sum(row['FCFF']/(1+test_k)**row['t'] for row in rows)
            val=explicit_ev+tested['normal_earnings_EV_Y5']/(1+test_k)**terminal_t+initial_nfa
            alternate_grid.append({'k':test_k,'normal_NOPAT_multiple':mult,'current_normal_earnings_plus_NFA_per_share':val/shares})
    valuation={'current_operating_EV_total':current_operating_ev,
               'current_risk_tax_adjusted_NFA_total':initial_nfa,
               'central_current_EV_plus_NFA_per_share':current_value/shares,
               'current_normal_earnings_operating_EV_total':normal_operating_ev,
               'central_current_normal_earnings_plus_NFA_per_share':normal_value/shares,
               'valuation_parameter_grid':valuation_grid,'normal_earnings_parameter_grid':alternate_grid}
    holder_path={'conditional_not_primary_fair_value':True,
                 'five_year_cash_dividends_total':total_dividends,'PV_dividends_total_at_holder_hurdle':pv_d,
                 'Y5_total':y5,'Y5_per_share':y5/shares,'Y5_remaining_NFA_total':final_nfa,
                 'conditional_holder_PV_per_share':holder_pv/shares,
                 'difference_from_current_EV_plus_NFA_per_share':(holder_pv-current_value)/shares,
                 'chosen_policy_carry_identity_per_share':conditional_carry/shares,
                 'identity_residual_CNY_not_economic_validation':holder_pv-current_value-conditional_carry,
                 'noncurrent_return_proxy':f['noncurrent_aftertax_retained_total_return_proxy'],
                 'noncurrent_return_range_not_run':f['noncurrent_aftertax_retained_total_return_range_not_run'],
                 'not_promised_liquidation_or_asset_redemption_at_Y5':True,
                 'note':'Difference reflects the explicit distribution, retention and financial-return assumptions at a common holder hurdle; it is not a required discount to current assets or an identity proving fair value.'}
    deficit_dates=[{'date':row['date'],'mother_cash':row['mother_cash'],'sub_cash':row['sub_cash'],
                    'group_cash':row['group_cash']} for row in rows
                   if row['mother_cash'] < -0.01 or row['sub_cash'] < -0.01 or row['group_cash'] < -0.01]
    funding_infeasible=bool(deficit_dates)
    # A boolean beside a usable price is insufficient: remove all usable valuation
    # fields and grids. Mathematical numbers survive only in a diagnostic namespace.
    unfunded_diagnostic=None
    if funding_infeasible:
        unfunded_diagnostic={'not_executable_or_investable':True,'mathematical_valuation_only':valuation,
                             'mathematical_holder_path_only':holder_path,'mathematical_terminal_only':tv}
    return {'case':x['case_name'],'economic_uncertainty_not_resolved_by_arithmetic':True,
            'funding_infeasible':funding_infeasible,'funding_deficit_dates':deficit_dates,
            'dividend_budget_not_executable_if_funding_infeasible':True,
            'opening_state':initial_state,'ending_state':state,'dividends':dividends,'periods':rows,
            'annual_group_profit_reference_budget_excluding_noncurrent_markups':annual_ni,
            'future_declared_unpaid_sub_dividends':sum(z['remaining'] for z in queue),
            'valuation':None if funding_infeasible else valuation,
            'conditional_holder_path':None if funding_infeasible else holder_path,
            'terminal_operating':None if funding_infeasible else tv,
            'unfunded_diagnostic':unfunded_diagnostic,
            'mechanical_NFA_bridge_residual_CNY':final_nfa-initial_nfa-total_fcff-total_finance_returns+total_dividends,
            'largest_period_NFA_residual_CNY':max(abs(row['NFA_continuity_residual']) for row in rows),
            'warnings':warnings,
            'method_note':'Primary operating EV plus current risk/tax-adjusted NFA and normal commodity earnings cross-check use the same current ownership bridge, not a universal cash-retention discount. D+Y5 is a distinct conditional holder-return path; neither arithmetic nor agreement proves demand.'}
