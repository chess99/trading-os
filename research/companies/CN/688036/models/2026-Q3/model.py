"""Static-prepared Transsion model. Standard library only; import has no computation/I/O.
All amounts CNY billion, shares billion, ratios decimal. Not executed in preparation.
"""
from copy import deepcopy
import math


class EconomicInfeasible(Exception):
    """A bounded economic path failed; not a programming-error substitute."""

    def __init__(self, message, *, stage, period=None, open_state=None,
                 prescribed_inputs=None, last_computed_state=None, row=None,
                 threshold_and_actual=None, extra=None):
        super().__init__(message)
        self.evidence = deepcopy({'message':message, 'stage':stage, 'period':period,
            'open_state':open_state, 'prescribed_inputs':prescribed_inputs,
            'last_computed_state':last_computed_state, 'row':row,
            'threshold_and_actual':threshold_and_actual, 'extra':extra})


def nwc(s):
    return (s['inventory'] + s['ar'] + s['prepay'] + s['other_assets']
            - s['trade_pay'] - s['expense_pay'] - s['contract'] - s['other_liabilities']
            - s['income_tax_payable'] - s['accrual_pool'])


def capital(s):
    return nwc(s) + s['fixed'] - s['engineering_pay'] + s['required_cash'] + s['operating_deposit']


def annual_targets(a, p, common, accrued_income_tax):
    r = a['revenue']
    cogs = r * (1 - a['gross_margin'])
    tax_payable = accrued_income_tax*common['income_tax_lag_fraction']
    return {'inventory': r*a['inventory_ratio'], 'ar': r*a['ar_ratio'],
            'prepay': r*a['prepay_ratio'], 'other_assets': r*a['other_assets_ratio'],
            'trade_pay': cogs*a['ap_days']/365, 'expense_pay':r*a['fee_pay_ratio'], 'contract': r*a['contract_ratio'],
            'other_liabilities': r*a['other_liabilities_ratio']-tax_payable,
            'income_tax_payable':tax_payable,
            'accrual_pool': r*a['accrual_pool_ratio'], 'fixed': r*a['fixed_ratio'],
            'engineering_pay': r*a['engineering_ap_ratio'],
            'required_cash': r*p['cash_buffer_ratio'],
            'operating_deposit':r*a['operating_deposit_ratio']}


def operating_step(open_s, a, p, common, target=None, duration=1.0, period=None):
    """One accounting-consistent operating period, also used by stub and terminal."""
    rev = a['revenue']
    margin = a['gross_margin']-a['selling']-a['rd']-a['admin']-a['other_cost']
    ebit = rev*margin-a['inventory_loss']-a['incremental_accrual_cost']
    accrued_income_tax = max(ebit, 0.0)*p['tax']
    end = deepcopy(open_s)
    end.update(annual_targets(a, p, common, accrued_income_tax) if target is None else target)
    cash_income_tax = accrued_income_tax+open_s['income_tax_payable']-end['income_tax_payable']
    nopat = ebit-accrued_income_tax
    dep = open_s['fixed']*common['depreciation_rate']*duration
    growth_capex = end['fixed']-open_s['fixed']
    capex_asset = dep+growth_capex
    capex_cash = capex_asset-(end['engineering_pay']-open_s['engineering_pay'])
    delta_nwc = nwc(end)-nwc(open_s)
    ocf = nopat+dep-delta_nwc
    deposit_transfer=end['operating_deposit']-open_s['operating_deposit']
    fcff = ocf-capex_cash-(end['required_cash']-open_s['required_cash'])-deposit_transfer
    normal_charge = rev*common['normal_accrual_charge_ratio']
    accrual_paid = open_s['accrual_pool']+normal_charge+a['incremental_accrual_cost']-end['accrual_pool']
    cogs = rev*(1-a['gross_margin'])
    purchases = cogs+a['inventory_loss']+end['inventory']-open_s['inventory']
    cash_purchase = purchases+end['prepay']-open_s['prepay']-(end['trade_pay']-open_s['trade_pay'])
    average_capital = (capital(open_s)+capital(end))/2
    row = {'revenue':rev, 'normal_ebit_margin':margin, 'ebit':ebit,
           'accrued_operating_income_tax':accrued_income_tax,
           'cash_operating_income_tax_diagnostic_not_second_cash_deduction':cash_income_tax,
           'income_tax_payable_open':open_s['income_tax_payable'],
           'income_tax_payable_close':end['income_tax_payable'],
           'operating_deposit_open':open_s['operating_deposit'],
           'operating_deposit_close':end['operating_deposit'],
           'operating_deposit_transfer_from_available_cash':deposit_transfer,
           'nopat':nopat, 'economic_depreciation':dep,
           'maintenance_capex':dep, 'growth_capex':growth_capex, 'asset_capex':capex_asset,
           'cash_capex':capex_cash, 'nwc_open':nwc(open_s), 'nwc_close':nwc(end),
           'delta_nwc':delta_nwc, 'ocf':ocf, 'fcff':fcff,
           'capital_open':capital(open_s), 'capital_close':capital(end),
           'fcff_capital_identity_residual':fcff-(nopat-capital(end)+capital(open_s)),
           'accrual_open':open_s['accrual_pool'], 'accrual_charge_normal_embedded':normal_charge,
           'accrual_charge_incremental':a['incremental_accrual_cost'],
           'accrual_paid_diagnostic_not_second_cash_deduction':accrual_paid,
           'accrual_close':end['accrual_pool'], 'new_inventory_loss':a['inventory_loss'],
           'purchases':purchases, 'cash_purchase_diagnostic':cash_purchase,
           'roic_average_capital':nopat/average_capital if average_capital>0 else None}
    # These define economic feasibility, not ordinary software validation.
    quantities={'purchases':purchases,'cash_purchase':cash_purchase,'capex_asset':capex_asset,
                'capex_cash':capex_cash,'accrual_paid':accrual_paid,'cash_income_tax':cash_income_tax,
                'other_nonincome_tax_liabilities':end['other_liabilities'],
                'operating_deposit':end['operating_deposit']}
    if min(quantities.values()) < -1e-8:
        raise EconomicInfeasible('negative operating purchase/payment/balance under prescribed path',
            stage='operating_step',period=period,open_state=open_s,prescribed_inputs={'annual':a,'parameters':p,'target':target},
            last_computed_state=end,row=row,threshold_and_actual={'minimum_allowed':-1e-8,'actuals':quantities})
    return end, row


def make_cutoff(facts, scenario, common):
    """Reported September balance + one bounded unreported October bridge + completed H issue."""
    f = lambda k: facts[k]['value']/1_000_000_000
    p, a0, stub = scenario['parameters'], {k:v[0] for k,v in scenario['series'].items()}, scenario['october_bridge']
    non_ce=f('cash_funds')-f('cash_equivalents')
    income_tax_open=f('tax_payable')*common['q3_income_tax_share_budget']
    s = {'inventory':f('inventory'), 'ar':f('ar'), 'prepay':f('prepay'),
         'other_assets':f('other_ar')+f('other_current_assets'),
         'trade_pay':f('ap')+f('notes_payable')-p['q3_engineering_ap_budget']-p['q3_fee_ap_budget'],
         'expense_pay':p['q3_fee_ap_budget'],
         'contract':f('contract'),
         'other_liabilities':f('employee_payable')+f('tax_payable')+f('other_payable')-income_tax_open,
         'income_tax_payable':income_tax_open,
         'accrual_pool':f('accrual_pool'),
         'fixed':sum(f(k) for k in ['ppe','cip','rou','intangible','long_deferred','other_noncurrent']),
         'engineering_pay':p['q3_engineering_ap_budget'],
         'required_cash':f('nine_month_revenue')*4/3*p['cash_buffer_ratio'],
         'operating_deposit':non_ce*p['non_ce_necessary_fraction'],
         'nonce_release_receivable':non_ce*(1-p['non_ce_necessary_fraction']),
         'debt':sum(f(k) for k in ['short_debt','current_long_liabilities','long_debt','lease_debt']),
         'cash':f('cash_equivalents'), 'nci_book':f('nci_book')}
    q3 = deepcopy(s)
    target = {k:s[k]+stub[k] for k in ['inventory','ar','prepay','other_assets','trade_pay','expense_pay','contract','other_liabilities','accrual_pool','fixed','engineering_pay','operating_deposit']}
    target['income_tax_payable']=s['income_tax_payable']  # no unreported October tax-settlement fact invented
    target['required_cash'] = a0['revenue']*p['cash_buffer_ratio']
    a0.update({k:stub[k] for k in ['revenue','inventory_loss','incremental_accrual_cost']})
    end, op = operating_step(s, a0, p, common, target, 1/12, period='2026-10-unreported-bridge')
    debt_new = s['debt']+stub['debt_change']
    interest = (s['debt']+debt_new)/2*p['debt_rate']/12
    shield = min(max(op['ebit'],0),interest)*p['tax']
    nci_profit = op['nopat']*p['nci_profit_fraction']
    nci_div = max(nci_profit,0)*common['nci_payout']
    h_total = f('h_net_proceeds_estimate')*p['h_net_factor']*p['cny_per_hkd_budget']
    h_cash = h_total*p['h_received_fraction']
    wealth_sale = f('short_wealth')
    end.update({'cash':s['cash']+op['ocf']-op['cash_capex']-op['operating_deposit_transfer_from_available_cash']+stub['debt_change']-interest+shield-nci_div+wealth_sale+h_cash,
                'debt':debt_new, 'h_receivable':h_total-h_cash,
                'other_financial_value':f('other_financial')*p['other_fin_recovery']+f('equity_investments')*p['equity_invest_recovery'],
                'nci_book':s['nci_book']+nci_profit-nci_div,
                'shares_bn':f('shares_after_h'),
                'mother_cash':f('mother_cash')+f('mother_wealth')+p['mother_h2_cash_delta']-f('approved_interim_dividend')+h_cash,
                'mother_re':f('mother_re')+p['mother_h2_profit']-f('approved_interim_dividend'),
                'reserve':f('statutory_reserve'), 'mother_other_ar':f('mother_other_ar'),
                'mother_other_pay':f('mother_other_pay'), 'mother_dividend_receivable':0.0})
    bridge={'reported_q3_state':q3, 'october_operating_budget':op,
            'october_net_borrowing':stub['debt_change'], 'october_interest_aftertax':interest-shield,
            'october_nci_dividend':nci_div, 'short_wealth_assumed_conversion_not_reported_receipt':wealth_sale,
            'h_original_currency':'HKD', 'h_net_estimate_hkd_bn':f('h_net_proceeds_estimate'),
            'h_net_estimate_factor':p['h_net_factor'], 'h_fx_cny_per_hkd_budget_not_observed':p['cny_per_hkd_budget'],
            'h_net_economic_claim_cny_bn':h_total,'h_cash_budget':h_cash,'h_remaining_receivable':h_total-h_cash,
            'non_ce_cash_total':non_ce,'necessary_collateral_not_excess_asset':end['operating_deposit'],
            'non_ce_extra_release_claim':end['nonce_release_receivable'],
            'q3_income_tax_payable_budget_not_reported_split':income_tax_open,
            'h_shares_before':facts['shares_before_h']['value'],'h_new_issued':facts['h_issued']['value'],
            'h_total_shares':facts['shares_after_h']['value'], 'cutoff_state':deepcopy(end)}
    if end['cash'] < end['required_cash'] or end['mother_cash'] < 0 or end['mother_cash'] > end['cash']:
        raise EconomicInfeasible('cutoff liquidity/location budget infeasible before forecast',
            stage='cutoff_liquidity',period='2026-10-31',open_state=q3,
            prescribed_inputs={'scenario':scenario['id'],'october':stub,'parameters':p},
            last_computed_state=end,row=op,
            threshold_and_actual={'cash':end['cash'],'required_cash':end['required_cash'],
                                  'mother_cash':end['mother_cash'],'mother_cash_min':0,'mother_cash_max':end['cash']},
            extra={'cutoff_bridge':bridge})
    return end, bridge


def simulate(initial, annual_rows, p, common, name='case'):
    """Formal path shared with all closed-form test cases. No validation assertions here."""
    state = deepcopy(initial)
    rows = []
    try:
        for i,a in enumerate(annual_rows):
            old=deepcopy(state)
            end,row=operating_step(old,a,p,common,period=i+1)
            h_collect=old['h_receivable'] if i==0 else 0.0
            nonce_collect=old['nonce_release_receivable'] if i==0 else 0.0
            deposit_transfer=row['operating_deposit_transfer_from_available_cash']
            target_debt=a['debt_target']
            interest=(old['debt']+target_debt)/2*p['debt_rate']
            tax_shield=min(max(row['ebit'],0),interest)*p['tax']
            interest_net=interest-tax_shield
            treasury_income=max(old['cash']-old['required_cash'],0)*p['treasury_aftertax_yield']
            nci_profit=row['nopat']*p['nci_profit_fraction']
            nci_div=max(nci_profit,0)*common['nci_payout']
            debt_change=target_debt-old['debt']
            cash_before_d=old['cash']+row['ocf']-row['cash_capex']-deposit_transfer+debt_change+h_collect+nonce_collect+treasury_income-interest_net-nci_div
            contingency=0.0
            if cash_before_d < end['required_cash']:
                # Bounded revolving financing; conservatively no incremental tax shield.
                contingency=(end['required_cash']-cash_before_d)/(1-0.5*p['debt_rate'])
                target_debt+=contingency
                debt_change+=contingency
                extra_interest=contingency*0.5*p['debt_rate']
                interest_net+=extra_interest
                cash_before_d+=contingency-extra_interest
            if target_debt>p['debt_cap']+1e-8:
                failed=deepcopy(end);failed.update({'cash_before_dividend':cash_before_d,'debt':target_debt})
                raise EconomicInfeasible('bounded financing cap exceeded',stage='financing_cap',period=i+1,
                    open_state=old,prescribed_inputs={'annual':a,'parameters':p},last_computed_state=failed,
                    row={**row,'interest_aftertax':interest_net,'net_borrowing':debt_change,'contingency_borrowing':contingency,
                         'cash_before_dividend':cash_before_d,'h_collection':h_collect,'non_ce_collection':nonce_collect,
                         'treasury_income':treasury_income,'nci_profit':nci_profit,'nci_dividend':nci_div,'tax_shield':tax_shield},
                    threshold_and_actual={'debt_cap':p['debt_cap'],'debt_actual':target_debt},
                    extra={'state_semantics':'operating end state plus provisional finance fields; not a committed closing state'})
            common_profit=row['nopat']-interest_net+treasury_income-nci_profit
            mother_payment=min(old['mother_other_pay'],a['mother_pay_settlement'])
            mother_cash_before_upstream=old['mother_cash']+h_collect-mother_payment+a['mother_local_cash_flow']
            declaration=max(common_profit,0)*p['declaration_fraction']
            div_receivable=old['mother_dividend_receivable']+declaration
            transfer_capacity=max(cash_before_d-mother_cash_before_upstream-end['required_cash'],0)*p['subsidiary_cash_mobility']
            dividend_received=min(div_receivable*p['dividend_receipt_fraction'],transfer_capacity)
            loan_received=min(old['mother_other_ar'],a['loan_collection'],max(transfer_capacity-dividend_received,0))
            mother_cash_before_d=mother_cash_before_upstream+dividend_received+loan_received
            reserve_cap=old['shares_bn']*common['statutory_cap_sharecapital_fraction']
            mother_profit=declaration+a['mother_own_net_profit']
            reserve_add=min(max(mother_profit,0)*common['statutory_reserve_rate'],max(reserve_cap-old['reserve'],0))
            legal_re_before_d=old['mother_re']+mother_profit-reserve_add
            desired_dividend=max(common_profit,0)*a['payout']
            actual_dividend=min(desired_dividend,max(cash_before_d-end['required_cash'],0),max(mother_cash_before_d-p['mother_cash_buffer'],0),max(legal_re_before_d,0))
            if mother_cash_before_d < -1e-8 or mother_cash_before_d>cash_before_d+1e-8:
                failed=deepcopy(end);failed.update({'cash':cash_before_d-actual_dividend,'debt':target_debt,
                    'mother_cash':mother_cash_before_d-actual_dividend,'mother_re':legal_re_before_d-actual_dividend})
                raise EconomicInfeasible('mother gross obligations / cash-location constraints infeasible',
                    stage='mother_cash_location',period=i+1,open_state=old,
                    prescribed_inputs={'annual':a,'parameters':p},last_computed_state=failed,
                    row={**row,'cash_before_dividend':cash_before_d,'mother_cash_before_upstream':mother_cash_before_upstream,
                         'mother_cash_before_dividend':mother_cash_before_d,'mother_payment':mother_payment,
                         'transfer_capacity':transfer_capacity,'dividend_received':dividend_received,
                         'loan_received':loan_received,'mother_profit':mother_profit,'legal_re_before_dividend':legal_re_before_d,
                         'ordinary_dividend_desired':desired_dividend,'ordinary_dividend_computed':actual_dividend,
                         'net_borrowing':debt_change,'h_collection':h_collect,'non_ce_collection':nonce_collect,
                         'interest_aftertax':interest_net,'nci_profit':nci_profit,'nci_dividend':nci_div},
                    threshold_and_actual={'mother_cash_min':0,'mother_cash_max':cash_before_d,'actual':mother_cash_before_d},
                    extra={'state_semantics':'provisional proposed payments and equity; full period not committed'})
            end.update({'cash':cash_before_d-actual_dividend,'debt':target_debt,
                        'h_receivable':old['h_receivable']-h_collect,
                        'nonce_release_receivable':old['nonce_release_receivable']-nonce_collect,
                        'mother_cash':mother_cash_before_d-actual_dividend,
                        'mother_re':legal_re_before_d-actual_dividend,
                        'reserve':old['reserve']+reserve_add,
                        'mother_other_ar':old['mother_other_ar']-loan_received,
                        'mother_other_pay':old['mother_other_pay']-mother_payment,
                        'mother_dividend_receivable':div_receivable-dividend_received,
                        'nci_book':old['nci_book']+nci_profit-nci_div})
            cash_formula=old['cash']+row['ocf']-row['cash_capex']-deposit_transfer+debt_change+h_collect+nonce_collect+treasury_income-interest_net-nci_div-actual_dividend
            funds_open=old['cash']+old['operating_deposit']+old['nonce_release_receivable']
            funds_close=end['cash']+end['operating_deposit']+end['nonce_release_receivable']
            funds_formula=funds_open+row['ocf']-row['cash_capex']+debt_change+h_collect+treasury_income-interest_net-nci_div-actual_dividend
            mother_formula=old['mother_cash']+h_collect-mother_payment+a['mother_local_cash_flow']+dividend_received+loan_received-actual_dividend
            row.update({'year_index':i+1,'cash_payment_date':common['cash_payment_dates'][i],
                        'cash_open':old['cash'],'cash_close':end['cash'],'required_cash_close':end['required_cash'],
                        'debt_open':old['debt'],'debt_close':target_debt,'net_borrowing':debt_change,
                        'contingency_borrowing':contingency,'h_collection':h_collect,
                        'non_ce_extra_collection':nonce_collect,'cash_funds_open':funds_open,'cash_funds_close':funds_close,
                        'treasury_income_aftertax':treasury_income,'interest_aftertax':interest_net,
                        'financing_tax_shield_assumed_current_cash':tax_shield,
                        'nci_profit':nci_profit,'nci_dividend':nci_div,
                        'nci_book_open':old['nci_book'],'nci_book_close':end['nci_book'],
                        'common_normalized_profit':common_profit,'ordinary_dividend_desired':desired_dividend,
                        'ordinary_dividend':actual_dividend,'ordinary_dividend_per_share':actual_dividend/old['shares_bn'],
                        'mother_cash_open':old['mother_cash'],'mother_cash_close':end['mother_cash'],
                        'mother_other_pay_settled_gross':mother_payment,'mother_loan_principal_collected':loan_received,
                        'subsidiary_dividend_declared':declaration,'subsidiary_dividend_received':dividend_received,
                        'mother_own_net_profit_already_in_group':a['mother_own_net_profit'],
                        'mother_local_cash_flow_already_in_group':a['mother_local_cash_flow'],
                        'mother_total_profit':mother_profit,
                        'mother_re_open':old['mother_re'],'mother_re_close':end['mother_re'],
                        'mother_re_available_before_dividend':legal_re_before_d,
                        'mother_reserve_added':reserve_add,'mother_dividend_receivable_close':end['mother_dividend_receivable'],
                        'cash_identity_residual':end['cash']-cash_formula,
                        'cash_funds_identity_residual':funds_close-funds_formula,
                        'mother_cash_identity_residual':end['mother_cash']-mother_formula,
                        'mother_re_identity_residual':end['mother_re']-(old['mother_re']+mother_profit-reserve_add-actual_dividend),
                        'closing_state':deepcopy(end)})
            rows.append(row)
            state=end
    except EconomicInfeasible as exc:
        return {'status':'ECONOMIC_INFEASIBLE_LOCAL_NULL','name':name,'reason':str(exc),
                'failed_year':len(rows)+1,'partial_rows':rows,'initial':deepcopy(initial),
                'failed_assumptions':deepcopy(annual_rows[len(rows)]),'parameters':deepcopy(p),
                'economic_failure':exc.evidence,
                'value':None,'return_model':None}
    return {'status':'CALCULATED_NOT_YET_ASSERTED','name':name,'initial':deepcopy(initial),'rows':rows,
            'final':deepcopy(state),'parameters':deepcopy(p),'last_annual_assumptions':deepcopy(annual_rows[-1])}


def terminal_operating(result, common, growth):
    a=deepcopy(result['last_annual_assumptions'])
    a['revenue']*=1+growth
    a['inventory_loss']=0.0
    a['incremental_accrual_cost']=0.0
    end,row=operating_step(result['final'],a,result['parameters'],common,period='terminal-year-9')
    ic=result['rows'][-1]['capital_close']
    row['terminal_growth']=growth
    row['forward_roic_on_opening_capital']=row['nopat']/ic if ic>0 else None
    row['steady_capital_growth_residual']=(capital(end)-ic)-growth*ic
    row['closing_operating_state']=end
    return row


def enterprise_value(result, common, rate, growth, start_year=0):
    if rate<=growth or rate<=0:
        raise EconomicInfeasible('terminal discount rate must exceed growth',stage='terminal_pricing',
            period=start_year,open_state=result['final'],prescribed_inputs={'rate':rate,'growth':growth},
            last_computed_state=result['final'],threshold_and_actual={'required':'rate > growth and rate > 0','rate':rate,'growth':growth})
    terminal=terminal_operating(result,common,growth)
    future=result['rows'][start_year:]
    pv_explicit=sum(row['fcff']/(1+rate)**(i+1) for i,row in enumerate(future))
    tv=terminal['fcff']/(rate-growth)
    terminal_pv=tv/(1+rate)**len(future)
    ev=pv_explicit+terminal_pv
    return {'enterprise_value':ev,'explicit_pv':pv_explicit,'terminal_value_at_year8':tv,
            'terminal_pv':terminal_pv,'terminal_pv_share':terminal_pv/ev if ev!=0 else None,
            'discount_rate':rate,'growth':growth,'start_year':start_year,'terminal_operating':terminal}


def equity_bridge(state,p):
    excess=state['cash']-state['required_cash']
    nci_claim=max(state['nci_book'],0)*p['nci_book_multiple']
    h_value=state['h_receivable']/(1+p['ke'])
    nonce_value=state['nonce_release_receivable']/(1+p['ke'])
    delta=excess+state['other_financial_value']+h_value+nonce_value-state['debt']-nci_claim
    return {'total_available_cash':state['cash'],'necessary_available_operating_cash_excluded':state['required_cash'],
            'operating_deposit_in_capital_not_added_as_extra':state['operating_deposit'],
            'excess_cash_face':excess,'excess_cash_value':excess,
            'other_financial_recoverable_value':state['other_financial_value'],
            'h_receivable_face':state['h_receivable'],'h_receivable_value':h_value,
            'non_ce_release_claim_face':state['nonce_release_receivable'],'non_ce_release_claim_value':nonce_value,
            'financial_debt':state['debt'],'nci_economic_claim':nci_claim,
            'equity_bridge_delta':delta,'shares_bn':state['shares_bn']}


def price_at(result,common,rate,growth,start_year=0):
    ev=enterprise_value(result,common,rate,growth,start_year)
    state=result['initial'] if start_year==0 else result['rows'][start_year-1]['closing_state']
    bridge=equity_bridge(state,result['parameters'])
    equity=ev['enterprise_value']+bridge['equity_bridge_delta']
    if equity<0:
        raise EconomicInfeasible('negative common-equity residual; no zero clamp or canonical success',
            stage='common_equity_valuation',period=start_year,open_state=state,
            prescribed_inputs={'rate':rate,'growth':growth},last_computed_state=state,
            row={'operating':ev,'bridge':bridge,'common_equity_raw':equity},
            threshold_and_actual={'minimum_nonnegative_equity':0,'actual':equity})
    return {'operating':ev,'bridge':bridge,'common_equity':equity,'per_share':equity/state['shares_bn']}


def method_two(result,common,multiple):
    rows=result['rows']; p=result['parameters']; rate=p['operating_discount_rate']
    normalized=rows[2]['nopat']
    ramp=sum((rows[i]['nopat']-normalized)/(1+rate)**(i+1) for i in (0,1))
    capital_change=rows[2]['capital_close']-capital(result['initial'])
    capital_adjustment=-capital_change/(1+rate)**3
    ev=normalized*multiple+ramp+capital_adjustment
    bridge=equity_bridge(result['initial'],p)
    equity=ev+bridge['equity_bridge_delta']
    if equity<0:
        raise EconomicInfeasible('negative auxiliary common-equity residual; method-local null',
            stage='auxiliary_equity_valuation',period=0,open_state=result['initial'],
            prescribed_inputs={'multiple':multiple},last_computed_state=result['initial'],
            row={'normalized_nopat':normalized,'ramp':ramp,'capital_adjustment':capital_adjustment,
                 'enterprise_value':ev,'bridge':bridge,'common_equity_raw':equity},
            threshold_and_actual={'minimum_nonnegative_equity':0,'actual':equity})
    return {'normalized_nopat':normalized,'capitalization_multiple':multiple,
            'ramp_adjustment':ramp,'one_time_capital_adjustment':capital_adjustment,
            'enterprise_value':ev,'bridge':bridge,'common_equity':ev+bridge['equity_bridge_delta'],
            'per_share':(ev+bridge['equity_bridge_delta'])/result['initial']['shares_bn']}


def attach_valuations(result,common):
    if result['status']=='ECONOMIC_INFEASIBLE_LOCAL_NULL':
        return result
    p=result['parameters']
    result['method_one']=price_at(result,common,p['operating_discount_rate'],p['terminal_growth'])
    ev=result['method_one']['operating']['enterprise_value']
    result['capital_cost_diagnostic']={'equity_required_return_budget':p['ke'],
        'operating_discount_rate_budget':p['operating_discount_rate'],
        'debt_to_operating_enterprise_value':result['initial']['debt']/ev if ev>0 else None,
        'note':'diagnostic of modest leverage approximation, not observed-market CAPM/WACC'}
    result['method_two']={}
    for k in ['low','center','high']:
        try:
            result['method_two'][k]=method_two(result,common,p['method2_multiple_'+k])
        except EconomicInfeasible as exc:
            result['method_two'][k]={'status':'ECONOMIC_INFEASIBLE_METHOD_LOCAL_NULL',
                'per_share':None,'reason':str(exc),'economic_failure':exc.evidence}
    m1=result['method_one']['per_share']; m2=result['method_two']['center']['per_share']
    result['method_midpoint_gap_fraction']=abs(m1-m2)/abs(m1) if m1 and m2 is not None else None
    result['method_gap_requires_explanation']=result['method_midpoint_gap_fraction'] is not None and result['method_midpoint_gap_fraction']>.25
    first,last=result['rows'][0],result['rows'][4]
    dc=last['capital_close']-first['capital_close']
    result['year1_to_year5_incremental_roic']={'profit_change':last['nopat']-first['nopat'],'capital_change':dc,
        'ratio':(last['nopat']-first['nopat'])/dc if dc>0 else None,
        'note':'forecast diagnostic, not observed project return; nonpositive investment denominator is not infinite ROIC'}
    if result['name']=='base':
        result['core_value_range']={side:price_at(result,common,v['operating_discount_rate'],v['terminal_growth']) for side,v in common['year5_endpoints'].items()}
        y5={side:price_at(result,common,v['operating_discount_rate'],v['terminal_growth'],5) for side,v in common['year5_endpoints'].items()}
        result['year5_base_state_range']=y5
        result['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY',
            'model_as_of':common['information_cutoff'],
            'base_case_distributions_per_share':[r['ordinary_dividend_per_share'] for r in result['rows'][:5]],
            'base_case_terminal_equity_value_range_per_share':{'year_5':{side:v['per_share'] for side,v in y5.items()}}}
        result['return_model_note']='Annual cash dates October 31, 2027–2031; budget ordinary dividends after consolidated liquidity and mother RE/cash/gross obligations. Year5 value is remaining years6–8 operating DCF plus capital-consistent terminal and actual year5 financial/debt/NCI bridge. Fixed completed H share count; no unverified over-allotment; distributions removed from cash. No market price or IRR.'
        payload=result['return_model']
        ds=payload['base_case_distributions_per_share']
        ts=payload['base_case_terminal_equity_value_range_per_share']['year_5']
        if any(x<0 for x in ds) or min(ts.values())<0 or sum(ds)+ts['high']<=0:
            result['invalid_holder_candidate_raw']=payload
            result['return_model']=None
            result['holder_domain_status']='ECONOMIC_INFEASIBLE_INTERFACE_LOCAL_NULL'
            result['return_model_note']='Holder interface locally unavailable: negative component or nonpositive total future payoff. Raw economic values preserved; no clamp to zero. Operating/other method outputs remain separately available.'
    return result


def validate_return_model(payload,cutoff):
    """Pure local mirror of the canonical v1 field/domain contract; no consumer import."""
    assert isinstance(payload,dict)
    assert set(payload)=={'schema_version','method','currency','model_as_of',
        'base_case_distributions_per_share','base_case_terminal_equity_value_range_per_share'}
    assert type(payload['schema_version']) is int and payload['schema_version']==1
    assert payload['method']=='annual_common_equity_irr_v1' and payload['currency']=='CNY'
    assert payload['model_as_of']==cutoff
    ds=payload['base_case_distributions_per_share']
    assert isinstance(ds,list) and len(ds)==5
    ranges=payload['base_case_terminal_equity_value_range_per_share']
    assert isinstance(ranges,dict) and set(ranges)=={'year_5'}  # no unresearched year_3
    pair=ranges['year_5']
    assert isinstance(pair,dict) and set(pair)=={'low','high'}
    for x in ds+[pair['low'],pair['high']]:
        assert type(x) in (int,float) and math.isfinite(x) and x>=0
    assert pair['low']<=pair['high']
    assert sum(ds)+pair['high']>0
    return {'status':'LOCAL_CANONICAL_V1_FIELD_AND_NUMERIC_DOMAIN_PASS'}


def validate_result(result,common):
    """Called only after unmodified raw results have been saved by runner."""
    if result['status']=='ECONOMIC_INFEASIBLE_LOCAL_NULL':
        return {'status':'LOCAL_NULL_RECORDED_NOT_NUMERIC_PASS','reason':result['reason']}
    tol=1e-7
    assert len(result['rows'])==8
    for row in result['rows']:
        for key in ['cash_identity_residual','cash_funds_identity_residual','mother_cash_identity_residual','mother_re_identity_residual','fcff_capital_identity_residual']:
            assert abs(row[key])<tol,(result['name'],row['year_index'],key,row[key])
        assert row['ordinary_dividend']>=0
        assert row['cash_close']+tol>=row['required_cash_close']
        assert row['mother_cash_close']>=-tol
        assert row['mother_cash_close']<=row['cash_close']+tol
        assert row['debt_close']<=result['parameters']['debt_cap']+tol
        assert row['accrual_paid_diagnostic_not_second_cash_deduction']>=-tol
        assert abs(row['accrual_open']+row['accrual_charge_normal_embedded']+row['accrual_charge_incremental']-row['accrual_paid_diagnostic_not_second_cash_deduction']-row['accrual_close'])<tol
        assert abs(row['nci_book_open']+row['nci_profit']-row['nci_dividend']-row['nci_book_close'])<tol
        assert row['closing_state']['mother_other_ar']>=-tol
        assert row['closing_state']['mother_other_pay']>=-tol
        assert row['ordinary_dividend']<=max(row['mother_re_available_before_dividend'],0)+tol
        # Accumulated mother losses are economically possible; they prohibit dividends, not computation.
        assert abs(row['income_tax_payable_open']+row['accrued_operating_income_tax']
                   -row['cash_operating_income_tax_diagnostic_not_second_cash_deduction']-row['income_tax_payable_close'])<tol
    term=terminal_operating(result,common,result['parameters']['terminal_growth'])
    assert abs(term['steady_capital_growth_residual'])<tol
    if result['name']=='base':
        if result['return_model'] is not None:
            validate_return_model(result['return_model'],common['information_cutoff'])
        else:
            assert result['return_model_note'] and 'invalid_holder_candidate_raw' in result
        assert result['core_value_range']['low']['per_share']<=result['core_value_range']['high']['per_share']
        assert result['year5_base_state_range']['low']['per_share']<=result['year5_base_state_range']['high']['per_share']
        for pair in [result['core_value_range'],result['year5_base_state_range']]:
            assert pair['low']['per_share']>=0 and pair['high']['per_share']>=0
    def finite(x):
        if isinstance(x,float): assert math.isfinite(x)
        elif isinstance(x,dict):
            for v in x.values():finite(v)
        elif isinstance(x,list):
            for v in x:finite(v)
    finite(result)
    return {'status':'INTERNAL_ACCOUNTING_ASSERTIONS_PASS_NOT_INDEPENDENT_AUDIT'}
