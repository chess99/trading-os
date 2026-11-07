"""Static, never imported/executed during preparation. CNY bn internally.
Equity cash route: nonlease debt and NCI already in C; do not subtract again.
All case/amount assumptions are read from frozen INPUT-BUDGET.json.
"""
import copy
import math

BN = 1_000_000_000.0
BUSINESSES = ('rail', 'semi', 'auto', 'energy', 'marine', 'industrial', 'other')


def ratio(a, b):
    return a / b if abs(b) > 1e-12 else None


def fade(first5, year, terminal):
    if year <= 5:
        return first5[year - 1]
    return first5[-1] + (terminal - first5[-1]) * (year - 5) / 5.0


def cash_step(opening, op_cash, income, requested, payment_cap=math.inf):
    """Used by production and synthetic tests. No hidden borrowing/floor at zero."""
    available = opening + op_cash + income
    paid = max(0.0, min(requested, payment_cap))
    closing = available - paid
    return {'opening': opening, 'op_cash': op_cash, 'financial_income': income,
            'requested': requested, 'paid': paid, 'closing': closing,
            'funding_gap': max(-closing, 0.0)}


def pv(flows, rate, start=1):
    return sum(v / (1.0 + rate) ** (i + start) for i, v in enumerate(flows))


def policy_tail(cash, earnings, target, funds, payout, release, income_yield, ke, growth):
    """v3: ordinary payout includes financial income; no numerical long-horizon loop.
    E excludes financial income, y is after tax, C already common equity cash.
    Parent/RE conditions are checked separately; no unproven special distribution.
    """
    r = 1.0 + growth
    A = 1.0 + (1.0-payout)*income_yield
    a = (1.0-release)*A
    h = cash-payout*earnings
    b = (1.0-release)*h+release*target
    conditions = {'ke_above_g':ke>growth, 'discount_above_a':1+ke>a,
                  'nonnegative_initial_funds':funds>=0, 'valid_policy':0<=release<=1 and 0<=payout<=1}
    if not all(conditions.values()):
        return {'value':None,'conditions':conditions,'economic_status':'TAIL_UNRESOLVED'}
    sum_f = (funds+b*r/(ke-growth))/(1+ke-a)
    value = payout*earnings*r/(ke-growth)+(payout*income_yield+release*A)*sum_f
    value += release*(h-target)*r/(ke-growth)
    steady_f = None if abs(r-a)<1e-12 else b*r/(r-a)
    if release>0:
        excess_first=A*funds+(h-target)*r
        excess_limit=None if steady_f is None else A*steady_f/r+h-target
        conditions['stable_release_state']=0<=a/r<1
        conditions['release_branch_first']=excess_first>=-1e-10
        conditions['release_branch_limit']=excess_limit is not None and excess_limit>=-1e-10
    else:
        # Sufficient no-borrowing condition for all future ordinary-policy years.
        conditions['ordinary_cash_coverage']=h>=-1e-10
        excess_first=0.0;excess_limit=0.0
    d_next=payout*(earnings*r+income_yield*funds)+release*excess_first
    d_steady=None if steady_f is None or steady_f<0 else payout*earnings+(payout*income_yield+release*A)*steady_f/r+release*(h-target)
    return {'value':value if all(conditions.values()) else None,'unconstrained_value':value,
            'conditions':conditions,'A':A,'a':a,'b':b,'steady_financial_coefficient':steady_f,
            'next_dividend':d_next,'steady_dividend_coefficient':d_steady,
            'economic_status':'APPLICABLE' if all(conditions.values()) else 'TAIL_UNRESOLVED'}


def opening_state(inputs, details):
    f, b = inputs['source_facts'], inputs['common_budget']
    cls = b['initial_financial_classification_bn']
    finance_components = {
        'reported_cash': f['q3_cash']/BN, 'trading':f['q3_trading']/BN,
        'near_noncurrent':f['q3_near_noncurrent']/BN, 'other_noncurrent':f['q3_other_noncurrent']/BN,
        'other_current_deposit_budget':cls['other_current_deposit'],
        'nonfinancial_near_excluded':-cls['nonfinancial_near'],
        'nonfinancial_long_excluded':-cls['nonfinancial_long'],
        'restricted_operating_cash_excluded':-cls['restricted_cash'],
        'operating_min_cash_excluded':-cls['operating_min_cash'],
        'known_october_dividend_paid':-f['october_dividend']/BN}
    group_financial = sum(finance_components.values())
    minority_financial = group_financial * b['nci_financial_share']
    common_financial = group_financial - minority_financial
    nwc = (f['q3_ar']+f['q3_notes']+f['q3_ar_financing']+f['q3_inventory']+
           f['q3_contract_assets']+f['q3_prepayment']-f['q3_ap']-
           f['q3_bill_payable']-f['q3_contract_liabilities'])/BN
    nwc += b['initial_long_contract_asset_bn'] + b['initial_other_operating_nwc_bn']
    # Operating minimum/restricted cash excluded from financial equity is retained
    # as operating capital, not written off or added independently to value.
    operating_cash = cls['operating_min_cash'] + cls['restricted_cash']
    revenue = {k: f['revenue_9m_bn'][k]/10.0 + b['q4_2026_revenue_bn'][k] for k in BUSINESSES}
    parent_re = f['h1_parent_re']/BN + b['parent_jul_oct_profit_bn'] - f['october_dividend']/BN
    return {'finance_components':finance_components, 'finance_group':group_financial,
            'finance_common':common_financial, 'finance_nci':minority_financial,
            'parent_finance':common_financial*b['parent_financial_share'],
            'subs_finance':common_financial*(1-b['parent_financial_share']),
            'parent_re':parent_re, 'subs_re':b['subs_opening_re_bn'],
            'parent_reserve':f['h1_parent_legal_reserve']/BN,
            'nwc':nwc, 'operating_cash':operating_cash, 'revenue':revenue,
            'ppe':f['q3_ppe']/BN, 'cip':f['q3_cip']/BN,
            'development':f['q3_development']/BN,
            'land':details['h1_land_book_yuan']/BN,
            'other_intangible':(details['h1_software_book_yuan']+details['h1_technology_book_yuan'])/BN,
            'lease_improvement':details['h1_lease_improvement_book_yuan']/BN,
            'rou':f['h1_rou_book']/BN, 'debt':b['initial_nonlease_debt_bn'],
            'net_dta':b['net_dta_open_bn']}


def pay_from_parent(state, parent_c, subs_c, parent_i, subs_i,
                    parent_ni_op, subs_ni_op, desired, target, budget, year):
    """Common-share subsidiaries only. Transfers are neutral to group F.
    Aggregate RE is a disclosed planning proxy, not legal permission to sweep each entity.
    """
    p_open, s_open = state['parent_finance'], state['subs_finance']
    settlement = budget['parent_intercompany_net_settlement_bn'][year-1]
    p_pre = p_open + parent_c + parent_i + settlement
    s_pre = s_open + subs_c + subs_i - settlement
    sub_profit = subs_ni_op + subs_i
    sub_reserve = max(sub_profit,0) * budget['subs_reserve_rate']
    s_re_pre = state['subs_re'] + sub_profit - sub_reserve
    sub_cash_floor = target * (1-budget['parent_financial_share'])
    sub_cash_capacity = max(s_pre-sub_cash_floor,0)
    regular = min(max(sub_profit,0)*budget['subs_regular_upstream_rate'],
                  max(s_re_pre,0), sub_cash_capacity)
    # Supplemental normal upstream when payment parent needs cash or RE, bounded by
    # common attributable subsidiary available cash and profit reserves.
    needed_cash = max(desired+budget['parent_cash_floor_bn']-(p_pre+regular),0)
    z = desired-state['parent_re']
    reserve_rate=budget['parent_reserve_rate']
    profit_required=z/(1-reserve_rate) if z>=0 else z
    profit_before_extra=parent_ni_op+parent_i+regular
    needed_re=max(profit_required-profit_before_extra,0)
    needed=max(needed_cash,needed_re)
    extra = min(needed,max(s_re_pre-regular,0),max(sub_cash_capacity-regular,0))
    upstream = regular + extra
    parent_profit = parent_ni_op + parent_i + upstream
    parent_reserve = max(parent_profit,0)*budget['parent_reserve_rate']
    p_re_pre = state['parent_re'] + parent_profit-parent_reserve
    p_available = p_pre+upstream
    pay_cap = min(max(p_re_pre,0),max(p_available-budget['parent_cash_floor_bn'],0))
    paid = min(max(desired,0),pay_cap)
    p_close, s_close = p_available-paid, s_pre-upstream
    return {'parent_opening_finance':p_open,'subs_opening_finance':s_open,
            'parent_operating_fcfe':parent_c,'subs_operating_fcfe':subs_c,
            'parent_financial_income':parent_i,'subs_financial_income':subs_i,
            'intercompany_net_payment_to_parent':settlement,
            'regular_subs_dividend_declared_paid':regular,'extra_subs_dividend_declared_paid':extra,
            'total_upstream':upstream,'extra_upstream_cash_need':needed_cash,'extra_upstream_re_need':needed_re,'parent_required_profit_for_D':profit_required,'parent_profit':parent_profit,'subs_profit':sub_profit,
            'parent_legal_reserve_added':parent_reserve,'subs_legal_reserve_added':sub_reserve,
            'parent_re_opening':state['parent_re'],'subs_re_opening':state['subs_re'],
            'parent_re_closing':p_re_pre-paid,'subs_re_closing':s_re_pre-upstream,
            'parent_finance_closing':p_close,'subs_finance_closing':s_close,
            'cash_payment_capacity':pay_cap,'dividend_requested':desired,'dividend_paid':paid,
            'payment_constraint_binding':paid+1e-9<desired,
            'parent_funding_gap':max(-p_close,0),'subs_funding_gap':max(-s_close,0)}


def run_case(inputs, details, case_name, case_override=None, aux=False, policy=None, sink=None, path_id=None):
    path_id=path_id or ('standalone/'+case_name+('/aux' if aux else '/main'))
    def emit(stage,payload):
        if sink is not None:sink.event(path_id,stage,payload)
    emit('path_start',{'case_name':case_name,'auxiliary':aux,'case_override_used':case_override is not None})
    case = copy.deepcopy(case_override or inputs['cases'][case_name])
    b = inputs['common_budget']; f=inputs['source_facts']
    policy = policy or {'ordinary_payout_all_operating_paths':0.40,'release_fraction_all_operating_paths':0.0,'boundary_jump_review_threshold':0.20}
    if case_override is None or not case_override.get('_isolated_release_diagnostic',False):
        case['ordinary_payout']=policy['ordinary_payout_all_operating_paths']
        case['release_fraction']=policy['release_fraction_all_operating_paths']
    initial=opening_state(inputs,details); s=copy.deepcopy(initial)
    emit('opening',initial)
    rows=[]; issues=[]; last_rev=sum(s['revenue'].values())
    prior_tax_payable=None; previous_ppe_da=b['ppe_da_annual_bn']
    new_asset_depreciation=0.0
    for year in range(1,b['horizon_years']+1):
        emit('year_start',{'year':year,'state':s})
        old_rev=s['revenue'].copy(); rev={}
        for k in BUSINESSES:
            growth=0.0 if aux else fade(case['growth_first5'][k],year,case['terminal_growth'])
            rev[k]=old_rev[k]*(1+growth)
        total=sum(rev.values()); scale=total/sum(initial['revenue'].values())
        weights={k:rev[k]/total for k in BUSINESSES}
        gm={k:(case['aux_gm'][k] if aux else fade(case['gm_first5'][k],year,case['gm_first5'][k][-1])) for k in BUSINESSES}
        gross={k:rev[k]*gm[k] for k in BUSINESSES}
        rd_total={k:rev[k]*case['rd_fraction'] for k in BUSINESSES}
        rd_cap={k:rd_total[k]*b['rd_capitalization_rate'] for k in BUSINESSES}
        rd_exp={k:rd_total[k]-rd_cap[k] for k in BUSINESSES}
        sga={k:rev[k]*case['sga_fraction'] for k in BUSINESSES}
        credit={k:rev[k]*b['credit_loss_fraction'] for k in BUSINESSES}
        ppe_da=b['ppe_da_annual_bn']+new_asset_depreciation
        rou_da=b['rou_da_annual_bn']*scale
        rent=b['cash_rent_annual_bn']*scale
        land_amort=b['land_amort_annual_bn']
        intangible_amort=b['other_intangible_amort_annual_bn']*scale
        improve_amort=b['lease_improvement_amort_annual_bn']*scale
        eligible_da=ppe_da+land_amort+intangible_amort+improve_amort
        debt_interest=s['debt']*b['debt_rate']
        software_refund=b['software_vat_refund_bn']*scale
        temporary_vat=0.0 if aux or year>1 else b['temporary_vat_credit_2027_bn']
        grant_amort=0.0 if aux else b['capital_grant_amort_bn'][year-1]
        other_income=software_refund+temporary_vat+grant_amort
        # Margins include financial-report DA allocation. Replace only ROU DA with rent.
        pre_tax={k:gross[k]-rd_exp[k]-sga[k]-credit[k]+weights[k]*(rou_da-rent+other_income-debt_interest) for k in BUSINESSES}
        rd_extra={k:(case['rd_extra_after_2027'] if aux or year>1 else (b['rd_extra_semi_through_2027'] if k=='semi' else b['rd_extra_general'])) for k in BUSINESSES}
        book_tax={k:max(0.0,(pre_tax[k]+max(pre_tax[k],0)*b['tax_permanent_addback_fraction']-rd_exp[k]*b['rd_eligible_fraction']*rd_extra[k])*b['normal_tax_rate']) for k in BUSINESSES}
        book_tax_total=sum(book_tax.values())
        wanted_dta_change=0.0 if aux else b['net_dta_changes_bn'][year-1]
        dta_change=max(wanted_dta_change,-s['net_dta'])
        current_tax=max(book_tax_total+dta_change,0.0)
        dta_change=current_tax-book_tax_total
        tax_payable=current_tax*b['tax_payable_fraction']
        if prior_tax_payable is None:
            # No standalone source income-tax payable at cutoff: neutral opening
            # estimate, explicitly output, not all-tax balance sheet payable.
            prior_tax_payable=tax_payable
        cash_tax=current_tax+prior_tax_payable-tax_payable
        deferred_tax=book_tax_total-current_tax
        ni={k:pre_tax[k]-book_tax[k] for k in BUSINESSES}
        ni_total=sum(ni.values())
        emit('tax_component',{'year':year,'revenue':rev,'pretax_profit':pre_tax,'book_tax':book_tax,'current_tax':current_tax,'cash_tax':cash_tax,'deferred_tax':deferred_tax,'dta_change':dta_change})
        cash_tax_adjustment=book_tax_total-cash_tax
        nr=fade(case['nwc_ratio_first5'],year,case['nwc_terminal_ratio'])
        nwc_end=total*nr
        delta_nwc=nwc_end-s['nwc']
        min_cash_end=initial['operating_cash']*scale
        delta_op_cash=min_cash_end-s['operating_cash']
        maintenance_ppe=ppe_da*case['maintenance_ppe_factor']
        land_cash=b['land_reinvestment_annual_bn']*scale
        software_cash=b['purchased_software_maintenance_bn']*scale
        tech_cash=b['technology_maintenance_bn']*scale
        improvement_cash=b['lease_improvement_maintenance_bn']*scale
        development_cash=sum(rd_cap.values())
        commitment=b['remaining_unrecognized_capital_commitment_bn']*b['commitment_payment_fraction'][year-1]
        capital_payable=b['capital_equipment_payable_bn']*b['capital_payable_fraction'][year-1]
        equity_commitment=b['equity_commitment_bn'] if year==1 else 0.0
        capacity_need={k:max(rev[k]-old_rev[k],0)*b['growth_capital_per_incremental_sales'][k] for k in BUSINESSES}
        if year<=2 and not aux:
            for k in ('semi','auto'):
                capacity_need[k]*=case['growth_existing_capacity_factor_first2']
        if aux:
            capacity_need={k:0.0 for k in BUSINESSES}
        # Existing committed capacity first satisfies growth requirements. Remainder
        # not assumed optional. Do not add the same new capacity cash twice.
        capacity_linked=sum(capacity_need.values())
        new_capacity_cash=max(capacity_linked,commitment)
        extra_uncommitted=max(capacity_linked-commitment,0)
        repayment=b['net_debt_repayment_bn'][year-1]
        all_capital=maintenance_ppe+land_cash+software_cash+tech_cash+improvement_cash+development_cash+new_capacity_cash+capital_payable+equity_commitment
        cip_transfer=min(s['cip'],initial['cip']*b['commitment_payment_fraction'][year-1])
        ppe_new_book=maintenance_ppe+new_capacity_cash+cip_transfer
        # Settlement of existing equipment payable creates no new book asset.
        ppe_end=s['ppe']+ppe_new_book-ppe_da
        cip_end=s['cip']-cip_transfer
        # Aggregate completed project payments represented in PPE; separate CIP
        # stock bridge shown, but never counted twice in invested capital changes.
        dev_transfer=s['development']*(details['development_transfer_fraction_first_year'] if year==1 else details['development_transfer_fraction_later'])
        development_end=s['development']+development_cash-dev_transfer
        other_int_end=s['other_intangible']+software_cash+tech_cash+dev_transfer-intangible_amort
        land_end=s['land']+land_cash-land_amort
        improve_end=s['lease_improvement']+improvement_cash-improve_amort
        emit('capital_component',{'year':year,'ppe_da':ppe_da,'eligible_da':eligible_da,'maintenance_ppe':maintenance_ppe,'development_cash':development_cash,'new_capacity_cash':new_capacity_cash,'capital_payable_settlement':capital_payable,'equity_commitment':equity_commitment,'all_capital_cash':all_capital,'ppe_closing':ppe_end,'cip_closing':cip_end,'nwc_closing':nwc_end})
        depreciation_allocation={k:ppe_da*b['ppe_da_allocation'][k]+weights[k]*(land_amort+intangible_amort+improve_amort) for k in BUSINESSES}
        cap_alloc={k:maintenance_ppe*b['ppe_da_allocation'][k]+weights[k]*(all_capital-maintenance_ppe) for k in BUSINESSES}
        c={k:ni[k]+depreciation_allocation[k]+weights[k]*(cash_tax_adjustment-grant_amort+b['new_capital_grant_cash_bn']-delta_nwc-delta_op_cash-repayment)-cap_alloc[k] for k in BUSINESSES}
        common_ni={k:ni[k]*b['ownership'][k] for k in BUSINESSES}
        common_c={k:c[k]*b['ownership'][k] for k in BUSINESSES}
        group_c=sum(c.values()); attr_c=sum(common_c.values()); nci_c=group_c-attr_c
        attr_ni=sum(common_ni.values()); nci_ni=ni_total-attr_ni
        common_finance=s['parent_finance']+s['subs_finance']
        y=b['financial_pretax_yield']*(1-b['financial_income_tax_rate'])
        parent_i=max(s['parent_finance'],0)*y; subs_i=max(s['subs_finance'],0)*y
        financial_i=parent_i+subs_i
        attr_revenue=sum(rev[k]*b['ownership'][k] for k in BUSINESSES)
        target=attr_revenue*case['financial_target_revenue_ratio']
        ordinary=max(attr_ni+financial_i,0)*case['ordinary_payout']
        excess=max(common_finance+attr_c+financial_i-ordinary-target,0)
        special=case['release_fraction']*excess
        desired=ordinary+special
        parent_c=sum(common_c[k]*b['parent_direct_fraction'][k] for k in BUSINESSES)
        parent_ni=sum(common_ni[k]*b['parent_direct_fraction'][k] for k in BUSINESSES)
        distribution=pay_from_parent(s,parent_c,attr_c-parent_c,parent_i,subs_i,parent_ni,attr_ni-parent_ni,desired,target,b,year)
        paid=distribution['dividend_paid']; ordinary_paid=min(paid,ordinary); special_paid=max(paid-ordinary_paid,0)
        cash=cash_step(common_finance,attr_c,financial_i,desired,distribution['cash_payment_capacity'])
        # NCI has its own financial pool. No assumed free minority capital injection.
        nci_i=max(s['finance_nci'],0)*y
        nci_div=min(max(nci_ni+nci_i,0)*case['ordinary_payout'],max(s['finance_nci']+nci_c+nci_i,0))
        nci_finance_end=s['finance_nci']+nci_c+nci_i-nci_div
        invested_open=s['ppe']+s['nwc']+s['operating_cash']+s['land']+s['other_intangible']+s['development']+s['lease_improvement']+s['cip']
        invested_end=ppe_end+nwc_end+min_cash_end+land_end+other_int_end+development_end+improve_end+cip_end
        unlevered_ni=ni_total+debt_interest*(1-b['normal_tax_rate'])
        own_revenue=sum(weights[k]*b['ownership'][k] for k in BUSINESSES)
        own_ppe=sum(b['ppe_da_allocation'][k]*b['ownership'][k] for k in BUSINESSES)
        common_da=sum(depreciation_allocation[k]*b['ownership'][k] for k in BUSINESSES)
        maintenance_other=land_cash+software_cash+tech_cash+improvement_cash+development_cash
        maintenance_common=maintenance_ppe*own_ppe+maintenance_other*own_revenue
        invested_common=(ppe_end+cip_end)*own_ppe+(invested_end-ppe_end-cip_end)*own_revenue
        row={'year':year,'holder_year_end':f'{2026+year}-10-31','operating_label':2026+year,'method':'aux_zero_growth' if aux else 'main_growth',
             'business':{k:{'revenue':rev[k],'gross_margin':gm[k],'gross_profit':gross[k],'rd_total':rd_total[k],'rd_expensed':rd_exp[k],'rd_capitalized':rd_cap[k],'sga':sga[k],'credit_loss':credit[k],'pretax_profit':pre_tax[k],'book_tax':book_tax[k],'net_income':ni[k],'fcfe_group':c[k],'common_ownership_budget_or_fact':b['ownership'][k],'ni_common':common_ni[k],'fcfe_common':common_c[k],'eligible_da_common':depreciation_allocation[k]*b['ownership'][k],'maintenance_cash_common':(maintenance_ppe*b['ppe_da_allocation'][k]+maintenance_other*weights[k])*b['ownership'][k],'invested_capital_common':((ppe_end+cip_end)*b['ppe_da_allocation'][k]+(invested_end-ppe_end-cip_end)*weights[k])*b['ownership'][k],'eligible_da_group':depreciation_allocation[k],'maintenance_cash_group':maintenance_ppe*b['ppe_da_allocation'][k]+maintenance_other*weights[k],'invested_capital_group':(ppe_end+cip_end)*b['ppe_da_allocation'][k]+(invested_end-ppe_end-cip_end)*weights[k]} for k in BUSINESSES},
             'revenue':total,'revenue_common_weighted':attr_revenue,'gross_profit':sum(gross.values()),'net_income_group':ni_total,'ni_operating_common':attr_ni,'ni_nci':nci_ni,
             'eligible_da':eligible_da,'eligible_da_common':common_da,'maintenance_cash_common':maintenance_common,'invested_capital_common':invested_common,'ppe_da':ppe_da,'rou_da_replaced':rou_da,'cash_rent':rent,'land_amortization':land_amort,'other_intangible_amortization':intangible_amort,'lease_improvement_amortization':improve_amort,
             'tax_book':book_tax_total,'tax_current':current_tax,'tax_deferred':deferred_tax,'tax_cash':cash_tax,'tax_payable_opening':prior_tax_payable,'tax_payable_closing':tax_payable,'net_dta_opening':s['net_dta'],'net_dta_change':dta_change,'net_dta_closing':s['net_dta']+dta_change,'rd_extra_semi':rd_extra['semi'],'rd_extra_other':rd_extra['rail'],'vat_software_refund':software_refund,'temporary_vat_credit':temporary_vat,'noncash_capital_grant_amort':grant_amort,
             'nwc_opening':s['nwc'],'nwc_closing':nwc_end,'delta_nwc':delta_nwc,'operating_cash_opening':s['operating_cash'],'operating_cash_closing':min_cash_end,
             'maintenance_ppe':maintenance_ppe,'land_maintenance_cash':land_cash,'purchased_software_maintenance':software_cash,'technology_maintenance':tech_cash,'lease_improvement_maintenance':improvement_cash,'capitalized_rd_cash':development_cash,
             'unrecognized_commitment_cash':commitment,'existing_equipment_payable_settlement':capital_payable,'capacity_linked_cash_need':capacity_linked,'extra_uncommitted_capacity_cash':extra_uncommitted,'total_new_capacity_cash':new_capacity_cash,'equity_commitment_cash':equity_commitment,'all_capital_cash':all_capital,
             'ppe_opening':s['ppe'],'ppe_new_book':ppe_new_book,'ppe_closing':ppe_end,'cip_opening':s['cip'],'cip_closing':cip_end,'cip_transfer_to_ppe':cip_transfer,'development_transfer_to_intangible':dev_transfer,'development_closing':development_end,'other_intangible_closing':other_int_end,'land_closing':land_end,'lease_improvement_closing':improve_end,
             'debt_opening':s['debt'],'nonlease_interest':debt_interest,'net_debt_repayment':repayment,'debt_closing':s['debt']-repayment,
             'fcfe_group':group_c,'fcfe_common':attr_c,'fcfe_nci':nci_c,'financial_income_common':financial_i,'financial_target':target,'financial_opening_common':common_finance,'financial_closing_common':cash['closing'],'financial_opening_nci':s['finance_nci'],'financial_closing_nci':nci_finance_end,'nci_financial_income':nci_i,'nci_dividend':nci_div,
             'ordinary_dividend_requested':ordinary,'extra_dividend_requested':special,'ordinary_dividend_paid':ordinary_paid,'extra_dividend_paid':special_paid,'dividend_paid':paid,'dividend_per_share':paid*BN/f['shares'],'parent_sub_bridge':distribution,
             'invested_capital_opening':invested_open,'invested_capital_closing':invested_end,'unlevered_normal_income':unlevered_ni,'model_return_on_operating_capital':ratio(unlevered_ni,(invested_open+invested_end)/2),
             'funding_gap_common':cash['funding_gap'],'funding_gap_nci':max(-nci_finance_end,0)}
        if any(row[k]>1e-8 for k in ('funding_gap_common','funding_gap_nci')) or distribution['parent_funding_gap']>1e-8 or distribution['subs_funding_gap']>1e-8:
            issues.append({'year':year,'type':'ECONOMIC_FUNDING_GAP','common':row['funding_gap_common'],'nci':row['funding_gap_nci'],'parent':distribution['parent_funding_gap'],'subs':distribution['subs_funding_gap']})
        if min(ppe_end,development_end,other_int_end,land_end,improve_end)<-1e-8:
            issues.append({'year':year,'type':'ASSET_REPLACEMENT_BUDGET_INCONSISTENT'})
        emit('year_complete',row)
        rows.append(row)
        s.update({'revenue':rev,'nwc':nwc_end,'operating_cash':min_cash_end,'ppe':ppe_end,'cip':cip_end,'development':development_end,'other_intangible':other_int_end,'land':land_end,'lease_improvement':improve_end,'debt':s['debt']-repayment,'net_dta':s['net_dta']+dta_change,'finance_nci':nci_finance_end,'parent_finance':distribution['parent_finance_closing'],'subs_finance':distribution['subs_finance_closing'],'parent_re':distribution['parent_re_closing'],'subs_re':distribution['subs_re_closing'],'parent_reserve':s['parent_reserve']+distribution['parent_legal_reserve_added']})
        # Incremental capacity depreciation enters next year. Maintenance replaces
        # existing machinery and is not added as a second depreciation generation.
        new_asset_depreciation += (new_capacity_cash+cip_transfer) / b['new_ppe_life_years']
        prior_tax_payable=tax_payable;last_rev=total;previous_ppe_da=ppe_da
    last=rows[-1]; g=0.0 if aux else case['terminal_growth'];ke=case['ke'];y=b['financial_pretax_yield']*(1-b['financial_income_tax_rate'])
    # Terminal normal cash uses current NI + DA - maintenance - g*capital,
    # not the last temporary tax reversal/working-capital release.
    terminal_growth_investment=g*last['invested_capital_common']
    terminal_c=last['ni_operating_common']+last['eligible_da_common']-last['maintenance_cash_common']-terminal_growth_investment
    tail=policy_tail(terminal_c,last['ni_operating_common'],last['financial_target'],last['financial_closing_common'],case['ordinary_payout'],case['release_fraction'],y,ke,g)
    emit('terminal_before_payability',{'year':10,'terminal_normal_C':terminal_c,'tail':tail})
    tail['normal_fcfe_common']=terminal_c
    tail['required_growth_reinvestment_common']=terminal_growth_investment
    tail['normal_fcfe_vs_year10_change']=ratio(terminal_c,last['fcfe_common'])
    # Whole-tail aggregate payability sufficient proof, not just a Y10 snapshot.
    terminal_c_by={k:(v['ni_common']+v['eligible_da_common']-v['maintenance_cash_common']-g*v['invested_capital_common']) for k,v in last['business'].items()}
    terminal_group_c=sum(v['net_income']+v['eligible_da_group']-v['maintenance_cash_group']-g*v['invested_capital_group'] for v in last['business'].values())
    cp=sum(terminal_c_by[k]*b['parent_direct_fraction'][k] for k in BUSINESSES)
    cs=terminal_c-cp
    ep=sum(last['business'][k]['ni_common']*b['parent_direct_fraction'][k] for k in BUSINESSES)
    es=last['ni_operating_common']-ep
    ks=last['financial_target']*(1-b['parent_financial_share'])
    rp=b['parent_reserve_rate'];rs=b['subs_reserve_rate'];payout=case['ordinary_payout']
    ordinary_operating=payout*last['ni_operating_common']
    lower=max(ordinary_operating-cp,ordinary_operating/(1-rp)-ep,0)
    upper=min((1-rs)*es,cs-g*ks)
    tail['whole_tail_upstream_interval']={'lower':lower,'upper':upper,'parent_C':cp,'subs_C':cs,'parent_E':ep,'subs_E':es,'subs_financial_buffer':ks}
    tail['whole_tail_operating_upstream_feasible']=lower<=upper+1e-8
    tail['financial_income_two_reserve_coverage']=payout<=(1-rp)*(1-rs)
    tail['terminal_parent_position']=s['parent_finance']>=b['parent_cash_floor_bn']-1e-8 and s['subs_finance']>=ks-1e-8
    tail['terminal_parent_re_nonnegative']=s['parent_re']>=0 and s['subs_re']>=0
    tail['nci_tail_cash_coverage']=terminal_group_c-terminal_c>=payout*last['ni_nci']-1e-8 and s['finance_nci']>=0
    tail['proof_scope']='Aggregate common-share major sources with frozen ownership/location budgets; no claim of unlimited legal cash sweep among all subsidiaries.'
    if case['release_fraction']>0:
        sf=tail.get('steady_financial_coefficient')
        a=tail.get('a',1.0);A=tail.get('A',1.0)
        coeff=payout*y+case['release_fraction']*A
        transient=coeff*max(last['financial_closing_common']-(sf or 0),0)/(1-a) if a<1 else None
        legal_steady=(max(ep,0)+(1-rs)*max(es,0))*(1-rp)
        legal_steady += max(sf or 0,0)*y/(1+g)*(1-rp)*(1-rs)
        ds=tail.get('steady_dividend_coefficient')
        tail['transient_extra_distribution_bound']=transient
        tail['steady_legal_common_capacity']=legal_steady
        tail['release_steady_legal_coverage']=ds is not None and ds<=legal_steady+1e-8
        tail['transient_re_coverage']=transient is not None and s['parent_re']>=transient and s['subs_re']>=transient*(1-b['parent_financial_share'])
    required=['whole_tail_operating_upstream_feasible','financial_income_two_reserve_coverage','terminal_parent_position','terminal_parent_re_nonnegative','nci_tail_cash_coverage']
    if case['release_fraction']>0:required+=['release_steady_legal_coverage','transient_re_coverage']
    if not all(tail[k] for k in required):
        tail['value']=None;tail['economic_status']='TAIL_LEGAL_OR_POLICY_UNRESOLVED'
    if tail['value'] is None:issues.append({'type':tail['economic_status']})
    free_tail=terminal_c*(1+g)/(ke-g) if ke>g else None
    free_value=pv([r['fcfe_common'] for r in rows],ke)+free_tail/(1+ke)**10+initial['finance_common'] if free_tail is not None else None
    policy_value=pv([r['dividend_paid'] for r in rows],ke)+tail['value']/(1+ke)**10 if tail['value'] is not None and not issues else None
    y5=(pv([r['dividend_paid'] for r in rows[5:]],ke)+tail['value']/(1+ke)**5)*BN/f['shares'] if policy_value is not None else None
    holder=pv([r['dividend_per_share'] for r in rows[:5]],ke)+y5/(1+ke)**5 if y5 is not None else None
    incr=ratio(rows[4]['unlevered_normal_income']-rows[0]['unlevered_normal_income'],rows[4]['invested_capital_closing']-rows[0]['invested_capital_closing'])
    result={'case':case_name,'method':'aux' if aux else 'main','parameters':case,'opening':initial,'annual':rows,'terminal':tail,'free_operating_equity_value_bn':free_value,'policy_equity_value_bn':policy_value,'conditional_unconstrained_policy_value_bn':(pv([r['dividend_paid'] for r in rows],ke)+tail['unconstrained_value']/(1+ke)**10) if tail.get('unconstrained_value') is not None else None,'capital_allocation_value_difference_bn':None if policy_value is None else free_value-policy_value,'policy_per_share':None if policy_value is None else policy_value*BN/f['shares'],'D1_D5':[r['dividend_per_share'] for r in rows[:5]],'Y5_policy_per_share':y5,'holder_present_value_per_share':holder,'terminal_present_value_share':None if policy_value is None or abs(policy_value)<1e-12 else (tail['value']/(1+ke)**10)/policy_value,'incremental_return_year1_to_year5':incr,'year5_to_year6_dividend_change':ratio(rows[5]['dividend_paid'],rows[4]['dividend_paid']),'year10_to_year11_dividend_change':ratio(tail.get('next_dividend',0),rows[-1]['dividend_paid']),'aux_owner_earnings_normal_bn':terminal_c if aux else None,'aux_finite_cash_bridge_adjustments_bn':[r['fcfe_common']-terminal_c for r in rows] if aux else None,'aux_capitalization_formula_value_bn':(terminal_c/ke+initial['finance_common']+pv([r['fcfe_common']-terminal_c for r in rows],ke)) if aux else None,'economic_issues':issues,'economic_status':'FEASIBLE_WITH_BUDGETS' if not issues else 'INCONCLUSIVE_OR_INFEASIBLE'}

    emit('path_complete',result)
    return result


def run_all(inputs, details, policy, sink=None):
    paths={}
    for name in ('conservative','base','improvement'):
        main=run_case(inputs,details,name,policy=policy,sink=sink,path_id='operating/'+name+'/main')
        aux=run_case(inputs,details,name,aux=True,policy=policy,sink=sink,path_id='operating/'+name+'/aux')
        comparison=None
        if main['policy_equity_value_bn'] is not None and aux['policy_equity_value_bn'] is not None:
            comparison=ratio(main['policy_equity_value_bn']-aux['policy_equity_value_bn'],aux['policy_equity_value_bn'])
        paths[name]={'main':main,'aux':aux,'same_policy_method_difference_ratio':comparison,'difference_above_25pct':comparison is not None and abs(comparison)>.25}
    sensitivities=[]
    for spec in inputs['sensitivities']:
        if spec['path']=='case.release_fraction':
            continue
        case=copy.deepcopy(inputs['cases']['base']);field=spec['path'].split('.')[-1]
        case[field]=case[field]+spec['delta'] if 'delta' in spec else spec['value']
        result=run_case(inputs,details,'base',case_override=case,policy=policy,sink=sink,path_id='sensitivity/'+spec['name'])
        # One complete annual result per sensitivity, no repeated source/input snapshots.
        sensitivities.append({'name':spec['name'],'changed_parameter':field,'value':case[field],'result':result})
    release_diagnostics=[]
    for release in policy['same_operating_base_release_diagnostics']:
        case=copy.deepcopy(inputs['cases']['base'])
        case.update({'ordinary_payout':policy['ordinary_payout_all_operating_paths'],'release_fraction':release,'_isolated_release_diagnostic':True})
        result=run_case(inputs,details,'base',case_override=case,policy=policy,sink=sink,path_id='conditional-release/'+str(release))
        release_diagnostics.append({'conditional_release_fraction':release,'not_company_commitment':True,'result':result})
    return {'schema_version':3,'policy_adoption':policy['core_value_adoption'],'conditional_release_diagnostics':release_diagnostics,'symbol':inputs['symbol'],'information_cutoff':inputs['cutoff'],'currency':'CNY','internal_amount_unit':'CNY billion','source_vs_budget':'Every forward input is analyst budget, not disclosed forecast','no_market_price_or_irr':True,'paths':paths,'isolated_sensitivities':sensitivities}
