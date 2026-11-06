"""当前数学计算组件；输入由必要事实、预算及同次经营计算生成。"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import copy
import json
import traceback
from release_math import EconomicUnproved, ReleaseBudgetExceeded, first_hit


class PendingSourceError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ValueError(message)


def q(value):
    if value is None:
        raise PendingSourceError('A required numeric input is pending')
    if isinstance(value, bool):
        raise TypeError('Boolean is not a numeric amount')
    if isinstance(value, dict):
        need(set(value) == {'amount', 'divisor'}, 'Unknown amount wrapper')
        return q(value['amount']) / q(value['divisor'])
    return value if isinstance(value, F) else F(str(value))


def encode(x):
    if isinstance(x, F):
        return {'exact': str(x), 'decimal': float(x)}
    if isinstance(x, dict):
        return {k: encode(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [encode(v) for v in x]
    return x


def save(path, obj):
    path.write_text(json.dumps(encode(obj), ensure_ascii=False, indent=2) + '\n')


def append(path, obj):
    with path.open('a') as stream:
        stream.write(json.dumps(encode(obj), ensure_ascii=False) + '\n')


def annual(series, year):
    """Explicit lists or new linear interpolation between declared anchors."""
    if isinstance(series, list):
        need(len(series) == 11, 'Annual list must contain exactly Y1..Y11')
        return q(series[year - 1])
    if isinstance(series, dict) and 'anchors' in series:
        points = sorted((int(k), q(v)) for k, v in series['anchors'].items())
        need(points[0][0] == 1 and points[-1][0] == 11, 'Anchor range must cover Y1..Y11')
        for a, b in zip(points, points[1:]):
            if a[0] <= year <= b[0]:
                return a[1] + (b[1] - a[1]) * F(year - a[0], b[0] - a[0])
        raise ValueError('Uncovered forecast year')
    return q(series)


def validate_source_gate(doc):
    need(doc['reconstruction'] == 'NEW_RECONSTRUCTION', 'New code must retain new identity')
    need(doc['common']['horizon'] == 10, 'This design uses ten explicit years and Y11 steady state')
    need(doc['common']['as_of'] == '2026-10-31T23:59:59+08:00', 'Wrong economic cutoff')
    if doc['data_kind'] == 'company':
        pending = [k for k, v in doc['source_verification'].items() if v['status'] != 'VERIFIED_LOCAL']
        pending += doc['pending_fields']
        if pending:
            raise PendingSourceError('Company source completion pending: ' + ', '.join(pending))
    else:
        need(doc['data_kind'] == 'synthetic_fixture', 'Unsupported input kind')
        need(not doc['pending_fields'], 'Toy must be completely specified')
    for label, endpoint in doc['common']['endpoints'].items():
        r, g, roc = q(endpoint['discount']), q(endpoint['growth']), q(endpoint['reinvestment_return'])
        need(r > g >= 0 and roc > g, 'Invalid terminal parameters: ' + label)
    need(q(doc['opening']['shares_final']) > 0, 'Non-positive shares')
    need(q(doc['opening']['shares_final']) == q(doc['opening']['shares_Q3']) + q(doc['opening']['october_new_shares']), 'Share bridge must equal Q3 plus October increment')
    need(doc['opening']['lease_treatment'] == 'cash_rent_in_operating_cost_no_second_debt_deduction', 'Lease treatment not specified')
    for label in ('bank_debt', 'minority_equity', 'preferred_claims'):
        need(q(doc['opening'][label]) == 0, 'This unlevered ordinary-equity design needs explicit extension for ' + label)


def opening_state(doc, paid_after_Q3):
    o, p, c = doc['opening'], doc['project'], doc['common']
    x = q(paid_after_Q3)
    paid = q(p['preinvestment_total'])
    need(0 <= x <= paid, 'Preinvestment timing correction outside source-bounded interval')
    fee_max = q(o['Q3_IPO_cash_receipt']) - q(o['initial_IPO_final_net'])
    need(fee_max >= 0, 'Negative fee uncertainty proxy requires source review')
    fee_hold = fee_max * q(c['fee_reserve_fraction'])
    need(0 <= q(c['fee_reserve_fraction']) <= 1, 'Invalid issue-fee assumption')
    incremental_fee = q(o['final_issue_fees']) - q(o['initial_issue_fees'])
    need(incremental_fee >= 0, 'Final fee total below initial fee total requires separate treatment')
    delta_cash = q(o['october_new_cash']) - incremental_fee - fee_hold
    group = q(o['group_cash']) + q(o['group_financial_assets']) + delta_cash - x
    parent = q(o['parent_cash']) + q(o['parent_financial_assets']) + delta_cash - x
    reclass = min(fee_hold, q(o['other_payables']))
    nwc = sum(q(v) for v in o['operating_current_assets'].values()) - sum(q(v) for v in o['operating_current_liabilities'].values()) + reclass
    fixed_pool = sum(q(v) for v in o['physical_asset_pool'].values())
    fixed_paid = paid * q(p['preinvestment_assumed_fixed_fraction'])
    # Unknown payment month changes the assets actually present at the cutoff,
    # not remaining project construction or the operating earnings forecast.
    legacy_fixed = fixed_pool - (fixed_paid - x)
    need(legacy_fixed >= 0, 'Project reclassification exceeds observed asset pool')
    need(q(p['preinvestment_assumed_fixed_fraction']) == 1, 'Any mixed prior-expense/working-capital preinvestment needs explicit new source allocation')
    need(0 <= parent <= group, 'Parent not a valid subset of group financial assets')
    restricted = q(o['restricted_project_cash'])
    need(0 <= restricted <= parent, 'Restricted project cash exceeds parent funds')
    return {'group_cash': group, 'parent_cash': parent, 'restricted_cash': restricted,
            'legacy_NWC': nwc, 'legacy_fixed': legacy_fixed, 'project_fixed': fixed_paid,
            'parent_RE': q(o['parent_RE']), 'statutory_reserve': q(o['statutory_reserve']),
            'operating_cash': q(c['opening_operating_cash']), 'fee_reserve': fee_hold,
            'fee_uncertainty_proxy': fee_max, 'fee_payable_reclassification': reclass,
            'october_only_net_cash_increment': delta_cash, 'preinvestment_post_Q3': x,
            'shares': q(o['shares_final'])}


def build_operating(doc, sink, checkpoint):
    """Operating rows are built once; the x upper bound only replays treasury."""
    validate_source_gate(doc)
    s = opening_state(doc, 0)
    p, c, path = doc['project'], doc['common'], doc['path']
    assets = p['capital_components']
    need(assets, 'Project asset breakdown is required')
    base_cost = sum(q(a['amount']) for a in assets)
    contingency = sum(q(v) for v in p['contingency_components'])
    need(base_cost > 0 and contingency >= 0, 'Invalid project capital budget')
    full_fixed = base_cost + contingency
    rd_expense = sum(q(v) for v in p['research_startup_components'])
    need(full_fixed + rd_expense + q(p['budget_working_capital_not_double_counted']) == q(p['total_budget']), 'Source project budget does not reconcile')
    remaining = full_fixed - q(p['preinvestment_total'])
    need(remaining >= 0, 'Negative remaining project capital')
    need(sum(q(v) for v in path['construction_fractions']) == 1, 'Construction schedule must spend remaining budget once')
    need(len(path['construction_fractions']) == 11, 'Construction needs Y1..Y11')
    commission = path['commission_year']
    need(1 <= commission <= 10, 'Invalid commission year')
    need(all(q(v) == 0 for v in path['construction_fractions'][commission:]), 'Construction after full commissioning requires another asset schedule')
    project_DA = sum(q(a['amount']) * (1 + contingency/base_cost) * (1-q(a['residual'])) / q(a['life']) for a in assets)
    lf, pf = s['legacy_fixed'], s['project_fixed']
    ln, pn, oc = s['legacy_NWC'], F(0), s['operating_cash']
    installed_legacy_capacity = q(c['opening_legacy_revenue_capacity'])
    last_extra_revenue = F(0)
    extra_cohorts = []
    parent_share = q(c['legacy_parent_fraction'])
    tax_rate = q(c['tax_rate'])
    need(0 <= parent_share <= 1 and 0 <= tax_rate < 1, 'Invalid tax/parent attribution')
    rows = []
    for year in range(1, 12):
        checkpoint({'stage':'operating_year_open','year':year,'legacy_fixed':lf,'project_fixed':pf,'legacy_NWC':ln,'project_NWC':pn,'operating_cash':oc,'installed_legacy_capacity':installed_legacy_capacity,'path_inputs':path})
        lr, pr = annual(path['legacy_revenue'], year), annual(path['project_revenue'], year)
        checkpoint({'stage':'operating_revenue_before_assert','year':year,'legacy_revenue':lr,'project_revenue':pr})
        need(lr >= 0 and pr >= 0, 'Negative revenue not supported')
        active = year >= commission
        need(active or pr == 0, 'Revenue before usable project capacity')
        lDA = annual(path['legacy_DA'], year)
        extra_revenue = max(pr-q(p['design_capacity_revenue']), F(0))
        pgrowth = max(extra_revenue-last_extra_revenue, F(0))*q(c['extra_project_fixed_capital_per_revenue'])
        if pgrowth:
            extra_cohorts.append((year, pgrowth))
        extra_DA = sum(amount*(1-q(c['extra_project_asset_residual']))/q(c['extra_project_asset_life']) for start,amount in extra_cohorts if year-start < q(c['extra_project_asset_life']))
        pDA = (project_DA if active else F(0)) + extra_DA
        lmargin = annual(path['legacy_cash_margin'], year)
        fixed_opex = q(path['project_fixed_cash_cost_at_commission']) * (1+q(path['project_fixed_cost_escalation']))**(year-commission) if active else F(0)
        research = rd_expense * q(path['construction_fractions'][year-1])
        legacy_EBIT = lr*lmargin - lDA
        project_EBIT = pr*q(path['project_contribution_margin']) - fixed_opex - pDA - research
        legacy_tax = max(legacy_EBIT, F(0))*tax_rate
        # The project and 85% legacy share are in the same legal parent. Loss
        # relief is limited to that parent's contemporaneous taxable profit.
        parent_tax = max(parent_share*legacy_EBIT + project_EBIT, F(0))*tax_rate
        project_tax = parent_tax - max(parent_share*legacy_EBIT, F(0))*tax_rate
        lNOPAT, pNOPAT = legacy_EBIT-legacy_tax, project_EBIT-project_tax
        nopat = lNOPAT+pNOPAT
        build = remaining*q(path['construction_fractions'][year-1])
        lmaint = lDA*q(c['legacy_maintenance_DA_multiple'])
        capacity_add = max(lr-installed_legacy_capacity, F(0))
        lgr = capacity_add*q(c['legacy_growth_fixed_capital_per_revenue'])
        age = year-commission
        pmaint_factor = q(path['initial_project_maintenance_DA_fraction']) if active and age < path['early_maintenance_years'] else F(1)
        pmaint = pDA*pmaint_factor if active else F(0)
        new_ln = lr*annual(path['legacy_NWC_ratio'], year)
        new_pn = pr*q(path['project_NWC_ratio'])
        new_oc = (lr+pr)*q(c['operating_cash_ratio'])
        dl, dp, dc = new_ln-ln, new_pn-pn, new_oc-oc
        lc = lNOPAT+lDA-lmaint-lgr-dl
        pc = pNOPAT+pDA-build-pmaint-pgrowth-dp
        fcff = lc+pc-dc
        before_ic = lf+pf+ln+pn+oc
        new_lf, new_pf = lf+lmaint+lgr-lDA, pf+build+pmaint+pgrowth-pDA
        checkpoint({'stage':'operating_year_calculated_before_assertions','year':year,'NOPAT':nopat,'FCFF':fcff,'new_legacy_fixed':new_lf,'new_project_fixed':new_pf,'old_capital':before_ic,'new_NWC':[new_ln,new_pn],'new_operating_cash':new_oc,'capacity_before':installed_legacy_capacity,'capacity_add':capacity_add})
        need(new_lf >= 0 and new_pf >= 0, 'Asset stock exhausted without a replacement/exit budget')
        after_ic = new_lf+new_pf+new_ln+new_pn+new_oc
        need(fcff == nopat-(after_ic-before_ic), 'NOPAT versus change in invested capital identity failed')
        # Split operating cash requirements proportionally by revenue; this is
        # an explicit NEW allocation convention for project NPV, not a cash use.
        new_project_oc = pr*q(c['operating_cash_ratio'])
        old_project_oc = rows[-1]['project_operating_cash'] if rows else F(0)
        project_fcff = pc-(new_project_oc-old_project_oc)
        row={'year':year,'legacy_revenue':lr,'project_revenue':pr,'legacy_cash_margin':lmargin,
             'legacy_EBIT':legacy_EBIT,'project_EBIT':project_EBIT,'project_tax':project_tax,
             'legacy_NOPAT':lNOPAT,'project_NOPAT':pNOPAT,'NOPAT':nopat,
             'installed_legacy_capacity_open':installed_legacy_capacity,'installed_legacy_capacity_close':installed_legacy_capacity+capacity_add,'legacy_capacity_add':capacity_add,
             'legacy_DA':lDA,'project_DA':pDA,'legacy_maintenance':lmaint,'legacy_growth_capex':lgr,
             'project_build_capex':build,'project_research_startup_expense':research,
             'project_maintenance':pmaint,'extra_project_growth_capex':pgrowth,
             'legacy_NWC':new_ln,'project_NWC':new_pn,'change_legacy_NWC':dl,'change_project_NWC':dp,
             'operating_cash_floor':new_oc,'change_operating_cash_floor':dc,'project_operating_cash':new_project_oc,
             'legacy_business_cash':lc,'project_business_cash':pc,'FCFF':fcff,'project_FCFF':project_fcff,
             'legacy_fixed_close':new_lf,'project_fixed_close':new_pf,
             'operating_capital_open':before_ic,'operating_capital_close':after_ic,
             'group_ROIC_average_capital':nopat/((before_ic+after_ic)/2) if before_ic+after_ic else 'UNDEFINED_ZERO_CAPITAL',
             'parent_operating_profit':parent_share*lNOPAT+pNOPAT,
             'parent_business_cash':parent_share*lc+pc,
             'restricted_eligible_project_use':build+research+max(dp,F(0))}
        rows.append(row);sink(row)
        lf,pf,ln,pn,oc,last_extra_revenue=new_lf,new_pf,new_ln,new_pn,new_oc,extra_revenue
        installed_legacy_capacity += capacity_add
    return {'rows':rows,'project_budget':{'full_fixed':full_fixed,'remaining_fixed':remaining,
             'research_startup_expense':rd_expense,'full_annual_project_DA':project_DA},'x0_opening':s}


def normalized_row(doc, operating, endpoint, year, previous_ic, checkpoint):
    """Fixed-growth release segment, not an additional operating scenario/grid.
    Net investment earns the endpoint incremental return in the following year;
    actual existing capital is carried, never reset to NOPAT/ROIC.
    """
    c=doc['common'];e=c['endpoints'][endpoint];g=q(e['growth']);roc=q(e['reinvestment_return'])
    anchor=operating['rows'][10];at10=operating['rows'][9]
    scale=(1+g)**(year-11)
    ln=anchor['legacy_NOPAT']*scale;pn=anchor['project_NOPAT']*scale;n=ln+pn
    reinvest=n*g/roc
    old_core=at10['operating_cash_floor']*(1+g)**(year-11)
    core=old_core*(1+g);delta=core-old_core
    legacy_weight=anchor['legacy_revenue']/(anchor['legacy_revenue']+anchor['project_revenue'])
    parent_weight=q(c['legacy_parent_fraction'])*legacy_weight+(1-legacy_weight)
    parent_profit=q(c['legacy_parent_fraction'])*ln+pn
    business=n-reinvest+delta;parent_business=parent_profit-parent_weight*(reinvest-delta)
    checkpoint({'stage':'normalized_growth_before_assert','year':year,'endpoint':endpoint,'NOPAT':n,'net_reinvestment':reinvest,'operating_cash_change':delta,'parent_business_cash':parent_business,'previous_operating_capital':previous_ic})
    if not(n>0 and reinvest>=delta>=0):
        raise EconomicUnproved('NORMALIZED_REINVESTMENT_REQUIRES_NEW_BUDGET',{'year':year,'NOPAT':n,'reinvestment':reinvest,'operating_cash_change':delta})
    return {'year':year,'normalized_release_segment':True,'legacy_NOPAT':ln,'project_NOPAT':pn,'NOPAT':n,
        'parent_operating_profit':parent_profit,'parent_business_cash':parent_business,
        'legacy_business_cash':business,'project_business_cash':F(0),'FCFF':n-reinvest,
        'terminal_net_reinvestment':reinvest,'terminal_parent_reinvestment_weight':parent_weight,
        'operating_cash_floor':core,'change_operating_cash_floor':delta,
        'operating_capital_open':previous_ic,'operating_capital_close':previous_ic+reinvest,
        'project_build_capex':F(0),'project_research_startup_expense':F(0),
        'restricted_eligible_project_use':F(0)}


def required_cash(doc, operating, op, endpoint):
    c=doc['common'];share=q(c['legacy_parent_fraction'])
    if op['year']<=10:
        parent=max(q(c['parent_cash_buffer']),share*op['legacy_revenue']*q(c['operating_cash_ratio'])+op['project_operating_cash'])
        sub=max(q(c['subsidiary_cash_buffer']),(1-share)*op['legacy_revenue']*q(c['operating_cash_ratio']))
    else:
        ten=operating['rows'][9];scale=(1+q(c['endpoints'][endpoint]['growth']))**(op['year']-10)
        parent=max(q(c['parent_cash_buffer']),share*ten['legacy_revenue']*q(c['operating_cash_ratio'])+ten['project_operating_cash'])*scale
        sub=max(q(c['subsidiary_cash_buffer']),(1-share)*ten['legacy_revenue']*q(c['operating_cash_ratio']))*scale
    return parent,sub


def cash_step(doc, operating, state, op, endpoint, checkpoint):
    c,path=doc['common'],doc['path'];year=op['year']
    cash,parent,restricted,RE,reserve,sub_pool=(state[k] for k in ('group_cash','parent_cash','restricted_cash','parent_RE','reserve','subsidiary_profit_pool'))
    checkpoint({'stage':'cash_year_open','year':year,'endpoint':endpoint,'state':state,'operating_row':op})
    yield_rate=q(c['cash_yield_after_tax']);withholding=q(c['subsidiary_dividend_withholding_budget'])
    need(0<=withholding<1,'Invalid conditional dividend tax budget')
    interest,p_interest,r_interest=cash*yield_rate,parent*yield_rate,restricted*yield_rate
    G=cash+op['legacy_business_cash']+op['project_business_cash']+interest
    P=parent+op['parent_business_cash']+p_interest
    restricted_with_interest=restricted+r_interest
    restricted_used=min(restricted_with_interest,op['restricted_eligible_project_use'])
    R=restricted_with_interest-restricted_used
    if year<=10:
        next_op=operating['rows'][year]
        major=next_op['project_build_capex']+next_op['project_research_startup_expense']>0 or path['additional_major_spend'][year]
        audit=path['standard_audit'][year-1]
    else:
        major=False;audit=c['normalized_future_standard_audit_assumed']
    # Project closeout/unused-fund transfer is a conditional authorized budget.
    # It changes classification, never total bank cash, and cannot bypass works.
    released=F(0)
    if year>=c['unused_project_funds_release_year'] and not major and audit:
        need(c['unused_project_funds_closeout_approval_assumed'],'Unused purpose funds need explicit closeout authority')
        released=R;R=F(0)
    parent_floor,sub_floor=required_cash(doc,operating,op,endpoint)
    sub_cash=G-P
    wanted=annual(c['old_intercompany_receivable_collection'],year) if year<=11 else F(0)
    remit=min(wanted,state['old_receivable_remaining'],max(sub_cash-sub_floor,F(0)))
    P+=remit;sub_cash-=remit
    # Only future actual subsidiary earnings establish the budgeted pool.
    # Opening unknown subsidiary legal RE is not silently converted to cash.
    sub_profit=op['NOPAT']-op['parent_operating_profit']+interest-p_interest
    pool_before=sub_pool+sub_profit
    fraction=F(1,max(c['normal_release_end_year']-year+1,1))
    sub_div=F(0)
    if year>=c['subsidiary_dividend_start_year'] and audit and not major:
        sub_div=min(max(pool_before,F(0)),max(sub_cash-sub_floor,F(0))*fraction)
    tax=sub_div*withholding;net_div=sub_div-tax
    P+=net_div;G-=tax;sub_cash-=sub_div
    parent_profit=op['parent_operating_profit']+p_interest+net_div
    target=q(doc['opening']['registered_capital_final'])*q(c['reserve_limit_capital_fraction'])
    reserve_add=min(max(parent_profit+min(RE,F(0)),F(0))*q(c['reserve_rate']),max(target-reserve,F(0)))
    legal=RE+parent_profit-reserve_add
    pfree=P-R-parent_floor;gfree=G-R-parent_floor-sub_floor
    gate=(not major) and audit and parent_profit>0 and legal>0
    intent=(max(op['NOPAT'],F(0))*q(c['profit_cash_distribution_intent'])+max(pfree,F(0))*q(c['excess_parent_cash_release_fraction'])) if year<c['normal_release_start_year'] else max(pfree,F(0))*fraction
    D=min(intent,pfree,gfree,legal) if gate else F(0)
    interim={'stage':'cash_year_before_assertions','year':year,'endpoint':endpoint,'group_before_D':G,'parent_before_D':P,'subsidiary_cash':sub_cash,'restricted_close':R,'parent_free':pfree,'group_free':gfree,'sub_pool_before_dividend':pool_before,'sub_dividend_gross':sub_div,'withholding':tax,'parent_profit':parent_profit,'legal_pool':legal,'desired_D':intent,'D':D,'parent_floor':parent_floor,'subsidiary_floor':sub_floor}
    checkpoint(interim)
    need(G>=0 and P>=0 and sub_cash>=0,'Unfunded group/parent/subsidiary cash in Y'+str(year))
    need(pfree>=0 and gfree>=0,'Required normal cash/purpose buffers unfunded in Y'+str(year))
    need(D>=0 and D<=max(legal,F(0)),'Illegal parent distribution')
    G-=D;P-=D
    need(G-P==sub_cash,'Intercompany transfer duplicated group cash')
    need(G==cash+op['FCFF']+op['change_operating_cash_floor']+interest-tax-D,'Group cash conservation failed')
    next_state={'group_cash':G,'parent_cash':P,'restricted_cash':R,'parent_RE':legal-D,'reserve':reserve+reserve_add,
        'subsidiary_profit_pool':pool_before-sub_div,'old_receivable_remaining':state['old_receivable_remaining']-remit,
        'operating_capital':op['operating_capital_close']}
    row={**op,**interim,'group_financial_income_after_tax':interest,'parent_financial_income_after_tax':p_interest,
        'subsidiary_profit':sub_profit,'subsidiary_profit_pool_close':pool_before-sub_div,'subsidiary_dividend_net_to_parent':net_div,
        'restricted_interest':r_interest,'restricted_use':restricted_used,'restricted_reclassified_on_closeout':released,'restricted_cash_close':R,
        'old_intercompany_collection':remit,'remaining_collection_budget':next_state['old_receivable_remaining'],
        'reserve_add':reserve_add,'reserve_close':reserve+reserve_add,'parent_RE_before_D':legal,'parent_RE_close':legal-D,
        'future12m_major_spend_gate':major,'audit_condition_assumed':audit,'dividend_policy_gate_open':gate,
        'D_per_share':D/q(doc['opening']['shares_final']),'group_cash_before_D':G+D,'parent_cash_before_D':P+D,
        'group_cash_close':G,'parent_cash_close':P,'group_ROIC_average_capital_corrected':op['NOPAT']/((op['operating_capital_open']+op['operating_capital_close'])/2) if op['operating_capital_open']+op['operating_capital_close'] else 'UNDEFINED_ZERO_CAPITAL','parent_unrestricted_after_buffer':pfree-D,'group_unrestricted_after_operating_floor':gfree-D}
    return next_state,row


def cash_chain(doc, operating, paid_after_Q3, endpoint, sink, checkpoint):
    c=doc['common'];opening=opening_state(doc,paid_after_Q3)
    state={'group_cash':opening['group_cash'],'parent_cash':opening['parent_cash'],'restricted_cash':opening['restricted_cash'],
        'parent_RE':opening['parent_RE'],'reserve':opening['statutory_reserve'],'subsidiary_profit_pool':q(c['opening_subsidiary_distributable_profit_budget']),
        'old_receivable_remaining':q(c['old_intercompany_receivable_budget_cap']),
        'operating_capital':operating['rows'][0]['operating_capital_open']+q(paid_after_Q3)}
    rows=[];g=q(c['endpoints'][endpoint]['growth']);target=q(doc['opening']['registered_capital_final'])*q(c['reserve_limit_capital_fraction'])
    last_normal=None;normal_streak=0
    # Normalization is event-driven. This bound is an engineering failure stop,
    # never an economic truncation, forced liquidation, or income-only remainder.
    for year in range(1,11+c['maximum_normalized_release_years']):
        if year<=10:
            op=copy.deepcopy(operating['rows'][year-1]);op['operating_capital_open']+=q(paid_after_Q3);op['operating_capital_close']+=q(paid_after_Q3)
        else:op=normalized_row(doc,operating,endpoint,year,state['operating_capital'],checkpoint)
        state,row=cash_step(doc,operating,state,op,endpoint,checkpoint)
        rows.append(row);sink(row)
        if year<=10:continue
        normal=(state['restricted_cash']==0 and state['parent_cash']==row['parent_floor'] and state['group_cash']==row['parent_floor']+row['subsidiary_floor'] and state['reserve']==target and state['parent_RE']>=0 and state['subsidiary_profit_pool']>=0 and row['dividend_policy_gate_open'])
        if normal:
            # A growing normal payout must not eat either profit pool. Once
            # these homogeneous inequalities hold, no later principal sweep is
            # hidden in the growing perpetuity.
            legal_stable=row['parent_profit']>=row['D'] and row['subsidiary_profit']>=row['sub_dividend_gross']
            if last_normal is not None and legal_stable and row['D']==last_normal['D']*(1+g):normal_streak+=1
            else:normal_streak=0
            last_normal=row
            if normal_streak>=1:
                need(row['D']>0,'Normal dividend must be positive for terminal capitalization')
                return {'opening':opening,'rows':rows,'terminal_year':year,'terminal_next_D':row['D']*(1+g),
                    'terminal_state':state,'certificate':{'cash_at_required_floors':True,'purpose_balance_zero':True,'parent_and_subsidiary_profit_pools_nonnegative':True,'reserve_target_met':True,'two_consecutive_normal_D_grow_by_g_exact':True,'future_profit_exceeds_normal_D':True,'no_residual_principal_added':True}}
        else:last_normal=None;normal_streak=0
    checkpoint({'stage':'normal_release_not_certified_at_budget_limit','endpoint':endpoint,'last_state':state,'last_row':rows[-1]})
    return continue_release_event(doc,operating,state,rows,endpoint,sink,checkpoint,opening)


def continue_saved_normal_one(doc,operating,state,rows,endpoint,sink,checkpoint,opening):
    """A saved full normal row needs one next original cash step, not zero pool.
    Certify its independent closed normal D coefficient before continuation.
    """
    c=doc['common'];last=rows[-1];previous=rows[-2];t=last['year'];g=q(c['endpoints'][endpoint]['growth']);Q=1+g
    checkpoint({'stage':'saved_normal_one_input','endpoint':endpoint,'state':state,'last_row':last,'previous_row':previous})
    if g<0:raise EconomicUnproved('NORMAL_ONE_NEGATIVE_GROWTH_UNAUTHORIZED',{'growth':g})
    target=q(doc['opening']['registered_capital_final'])*q(c['reserve_limit_capital_fraction'])
    eligible=(t>10 and previous['year']==t-1 and last.get('normalized_release_segment',False) and state['restricted_cash']==0 and state['parent_cash']==last['parent_floor'] and state['group_cash']==last['parent_floor']+last['subsidiary_floor'] and state['parent_RE']>=0 and state['subsidiary_profit_pool']>=0 and state['reserve']==target and state['old_receivable_remaining']==0 and last['dividend_policy_gate_open'] and c['normalized_future_standard_audit_assumed'] and t>=max(c['normal_release_end_year'],c['subsidiary_dividend_start_year'],c['unused_project_funds_release_year']))
    if not eligible:raise EconomicUnproved('SAVED_FULL_NORMAL_STATE_NOT_PROVED',{'state':state,'last_row':last})
    for key,stored in [('group_cash','group_cash_close'),('parent_cash','parent_cash_close'),('parent_RE','parent_RE_close'),('reserve','reserve_close'),('subsidiary_profit_pool','subsidiary_profit_pool_close'),('operating_capital','operating_capital_close')]:
        need(state[key]==last[stored],'Saved state/last row mismatch: '+key)
    Pprev=last['parent_floor']/Q;Fprev=last['subsidiary_floor']/Q
    start_normal=(previous['parent_cash_close']==Pprev and previous['group_cash_close']==Pprev+Fprev and previous['parent_floor']==Pprev and previous['subsidiary_floor']==Fprev and previous['restricted_cash_close']==0)
    if not start_normal:raise EconomicUnproved('LAST_SAVED_D_STILL_TRANSITIONAL',{'previous_row':previous,'last_row':last})
    W=last['terminal_parent_reinvestment_weight'];J=last['terminal_net_reinvestment']-last['change_operating_cash_floor'];y=q(c['cash_yield_after_tax']);tax=q(c['subsidiary_dividend_withholding_budget'])
    A=(1-W)*J;Ns=last['NOPAT']-last['parent_operating_profit']
    normal_sub=Ns+y*Fprev-A-g*Fprev
    normal_D=last['parent_business_cash']+y*Pprev+(1-tax)*normal_sub-g*Pprev
    sub_headroom=A+g*Fprev;parent_headroom=W*J+g*Pprev
    coefficient={'saved_year':t,'Q':Q,'subsidiary_normal_dividend':normal_sub,'ordinary_normal_D':normal_D,'subsidiary_profit_headroom':sub_headroom,'parent_profit_headroom':parent_headroom,'parent_prior_required_cash':Pprev,'subsidiary_prior_required_cash':Fprev,'existing_subsidiary_profit_pool_is_not_a_blocker':state['subsidiary_profit_pool']}
    checkpoint({'stage':'independent_normal_coefficient_before_assertions','endpoint':endpoint,**coefficient})
    if not(0<=W<=1 and J>=0 and normal_sub>=0 and normal_D>0 and sub_headroom>=0 and parent_headroom>=0):raise EconomicUnproved('NORMAL_ONE_FUTURE_CAPACITY_NOT_PROVED',coefficient)
    expected={'sub_dividend_gross':normal_sub,'withholding':tax*normal_sub,'subsidiary_dividend_net_to_parent':(1-tax)*normal_sub,'parent_profit':last['parent_operating_profit']+y*Pprev+(1-tax)*normal_sub,'subsidiary_profit':Ns+y*Fprev,'D':normal_D,'parent_financial_income_after_tax':y*Pprev,'group_financial_income_after_tax':y*(Pprev+Fprev)}
    for key,value in expected.items():need(last[key]==value,'Saved normal coefficient mismatch: '+key)
    need(last['parent_profit']-last['D']==parent_headroom,'Parent law-capacity coefficient mismatch')
    need(last['subsidiary_profit']-last['sub_dividend_gross']==sub_headroom,'Subsidiary law-capacity coefficient mismatch')
    # Exactly one new row. No build_operating, prior cash_step or low-end replay.
    op=normalized_row(doc,operating,endpoint,t+1,state['operating_capital'],checkpoint)
    new_state,row=cash_step(doc,operating,state,op,endpoint,checkpoint)
    sink(row)
    checkpoint({'stage':'one_new_normal_row_before_certificate','endpoint':endpoint,'state':new_state,'row':row,'coefficient':coefficient})
    normal=(new_state['restricted_cash']==0 and new_state['parent_cash']==row['parent_floor'] and new_state['group_cash']==row['parent_floor']+row['subsidiary_floor'] and new_state['reserve']==target and new_state['parent_RE']>=0 and new_state['subsidiary_profit_pool']>=0 and row['dividend_policy_gate_open'] and row['parent_profit']>=row['D'] and row['subsidiary_profit']>=row['sub_dividend_gross'])
    need(normal,'One-step original complete normal certificate failed')
    for key in ['D','sub_dividend_gross','withholding','subsidiary_dividend_net_to_parent','parent_profit','subsidiary_profit','parent_floor','subsidiary_floor']:
        need(row[key]==last[key]*Q,'Normal homogeneous coefficient failed: '+key)
    need(new_state['parent_RE']>=state['parent_RE'] and new_state['subsidiary_profit_pool']>=state['subsidiary_profit_pool'],'Profit pools are consumed instead of accumulating')
    return {'opening':opening,'rows':rows+[row],'terminal_year':t+1,'terminal_next_D':row['D']*Q,'terminal_state':new_state,
      'certificate':{'cash_at_required_floors':True,'purpose_balance_zero':True,'parent_and_subsidiary_profit_pools_nonnegative':True,'reserve_target_met':True,'two_consecutive_normal_D_grow_by_g_exact':True,'future_profit_exceeds_normal_D':True,'no_residual_principal_added':True,'saved_row_closed_coefficient':coefficient,'prior_rows_reused_without_recalculation':len(rows),'new_cash_steps':1}}


def continue_release_event(doc,operating,state,rows,endpoint,sink,checkpoint,opening):
    """Resume only an observed profit-limited subsidiary branch, no operations rebuild.
    Prove finite first hit, replay exactly that event plus two normal rows.
    All original cash_step fields/constraints/taxes remain authoritative.
    """
    c=doc['common'];last=rows[-1];t0=last['year'];g=q(c['endpoints'][endpoint]['growth']);Q=1+g
    checkpoint({'stage':'event_resume_input','endpoint':endpoint,'state':state,'last_row':last})
    if g<=-1:raise EconomicUnproved('INVALID_NORMAL_GROWTH_DOMAIN',{'growth':g})
    if g<0:raise EconomicUnproved('NEGATIVE_GROWTH_NEEDS_ASSET_EXIT_BUDGET',{'growth':g,'geometry_handles_negative_growth':True,'full_original_reinvestment_rules_do_not_authorize_asset_realizations':True})
    if state['parent_cash']==last['parent_floor'] and state['group_cash']==last['parent_floor']+last['subsidiary_floor'] and state['subsidiary_profit_pool']>=0:
        return continue_saved_normal_one(doc,operating,state,rows,endpoint,sink,checkpoint,opening)
    target=q(doc['opening']['registered_capital_final'])*q(c['reserve_limit_capital_fraction'])
    eligible=(t0>=10 and state['restricted_cash']==0 and state['parent_cash']==last['parent_floor'] and state['parent_RE']>=0 and state['reserve']==target and state['subsidiary_profit_pool']==0 and state['old_receivable_remaining']==0 and last['dividend_policy_gate_open'] and c['normalized_future_standard_audit_assumed'] and t0>=max(c['normal_release_end_year'],c['subsidiary_dividend_start_year'],c['unused_project_funds_release_year']))
    if not eligible:raise EconomicUnproved('OBSERVED_BRANCH_NOT_PROVED',{'state':state,'last_row':last})
    nxt=normalized_row(doc,operating,endpoint,t0+1,state['operating_capital'],checkpoint)
    W=nxt['terminal_parent_reinvestment_weight'];IminusOC=nxt['terminal_net_reinvestment']-nxt['change_operating_cash_floor']
    A=(1-W)*IminusOC;S=state['group_cash']-state['parent_cash'];F0=last['subsidiary_floor'];P0=last['parent_floor']
    geometry=first_hit(S,F0,A,g)
    checkpoint({'stage':'exact_first_hit_geometry','endpoint':endpoint,'geometry':geometry,'net_investment_minus_operating_cash':IminusOC})
    if geometry['kind']!='FINITE':raise EconomicUnproved('NO_FINITE_FIRST_HIT',geometry)
    if IminusOC<0 or not(0<=W<=1):raise EconomicUnproved('NET_CAPITAL_RELEASE_REQUIRES_NEW_BUDGET',{'net_investment_minus_operating_cash':IminusOC,'parent_weight':W,'geometry':geometry})
    y=q(c['cash_yield_after_tax']);tax=q(c['subsidiary_dividend_withholding_budget'])
    subsidiary_normal_div=nxt['NOPAT']-nxt['parent_operating_profit']+y*F0-A-g*F0
    parent_normal_D=nxt['parent_business_cash']+y*P0+(1-tax)*subsidiary_normal_div-g*P0
    proof={'geometry':geometry,'start_year':t0,'A1':A,'growth':g,'subsidiary_normal_dividend_next':subsidiary_normal_div,'parent_normal_D_next':parent_normal_D,'parent_profit_headroom_next':W*IminusOC+g*P0,'subsidiary_profit_headroom_next':A+g*F0,'economic_parameters_changed':False}
    checkpoint({'stage':'event_branch_and_future_capacity_proof','endpoint':endpoint,**proof})
    if subsidiary_normal_div<0 or parent_normal_D<=0 or W*IminusOC+g*P0<0 or A+g*F0<0:
        raise EconomicUnproved('NORMAL_DIVIDEND_OR_LEGAL_CAPACITY_NOT_PROVED',proof)
    n=geometry['n'];exact_rows=n+2
    if exact_rows>c['maximum_normalized_release_years']:
        raise ReleaseBudgetExceeded('Finite event proved but exact row replay exceeds unchanged per-continuation budget')
    additions=[];normal_rows=[]
    for k in range(1,exact_rows+1):
        year=t0+k
        op=normalized_row(doc,operating,endpoint,year,state['operating_capital'],checkpoint)
        state,row=cash_step(doc,operating,state,op,endpoint,checkpoint)
        additions.append(row);sink(row)
        predicted=S-A*(Q**k-1)/g-F0*Q**k if g!=0 else S-F0-k*A
        checkpoint({'stage':'event_row_exact_branch_check','endpoint':endpoint,'k':k,'predicted_uncapped_excess':predicted,'state':state,'row':row})
        if k<n:
            need(predicted>0 and state['subsidiary_profit_pool']==0,'Pre-boundary profit-limited branch differs from proof')
            need(state['group_cash']-state['parent_cash']-row['subsidiary_floor']==predicted,'Subsidiary closed-form balance mismatch')
            need(row['sub_dividend_gross']==row['subsidiary_profit'],'Pre-boundary dividend is not full contemporaneous subsidiary profit')
        elif k==n and n>0:
            need(predicted<=0 and state['group_cash']-state['parent_cash']==row['subsidiary_floor'],'First boundary actual cash floor mismatch')
            need(row['sub_dividend_gross']==row['subsidiary_profit']+predicted,'Boundary cash-limited dividend mismatch')
            need(state['subsidiary_profit_pool']==-predicted,'Boundary retained profit pool mismatch')
        normal=(state['restricted_cash']==0 and state['parent_cash']==row['parent_floor'] and state['group_cash']==row['parent_floor']+row['subsidiary_floor'] and state['reserve']==target and state['parent_RE']>=0 and state['subsidiary_profit_pool']>=0 and row['dividend_policy_gate_open'] and row['parent_profit']>=row['D'] and row['subsidiary_profit']>=row['sub_dividend_gross'])
        if k>n:
            need(normal,'Post-hit original full normal certificate failed')
            normal_rows.append(row)
    need(len(normal_rows)==2 and normal_rows[1]['D']==normal_rows[0]['D']*Q,'Two exact normal growing dividends not established')
    full=rows+additions;N=full[-1]['year']
    cumulative={key:sum(z[key] for z in additions) for key in ['D','sub_dividend_gross','withholding','subsidiary_dividend_net_to_parent','parent_profit','reserve_add','group_financial_income_after_tax','parent_financial_income_after_tax','terminal_net_reinvestment']}
    checkpoint({'stage':'event_cumulative_reconciliation','endpoint':endpoint,'added_rows':exact_rows,'cumulative':cumulative,'terminal_state':state})
    return {'opening':opening,'rows':full,'terminal_year':N,'terminal_next_D':full[-1]['D']*Q,'terminal_state':state,
        'certificate':{'cash_at_required_floors':True,'purpose_balance_zero':True,'parent_and_subsidiary_profit_pools_nonnegative':True,'reserve_target_met':True,'two_consecutive_normal_D_grow_by_g_exact':True,'future_profit_exceeds_normal_D':True,'no_residual_principal_added':True,'exact_finite_first_hit':proof,'continuation_cumulative':cumulative,'prior_rows_reused_without_recalculation':len(rows)}}


def valuation(doc, operating, chains):
    rows=operating['rows'];c=doc['common'];answers={};shares=q(doc['opening']['shares_final'])
    first5=None
    for name,e in c['endpoints'].items():
        chain=chains[name];funds=chain['rows'];opening=chain['opening'];N=chain['terminal_year']
        r,g,roc=q(e['discount']),q(e['growth']),q(e['reinvestment_return']);factor=(1-g/roc)/(r-g)
        d5=[z['D_per_share'] for z in funds[:5]]
        need(first5 is None or first5==d5,'Endpoint growth assumptions changed the same-base first-five D')
        first5=d5
        tv=chain['terminal_next_D']/(r-g)
        holder=sum(z['D']/(1+r)**z['year'] for z in funds)+tv/(1+r)**N
        y5=sum(z['D']/(1+r)**(z['year']-5) for z in funds if z['year']>5)+tv/(1+r)**(N-5)
        need(holder==sum(z['D']/(1+r)**z['year'] for z in funds[:5])+y5/(1+r)**5,'Same-state D/Y5 identity failed')
        operating_value=sum(rows[i]['FCFF']/(1+r)**(i+1) for i in range(10))+rows[10]['NOPAT']*factor/(1+r)**10
        project_value=sum(rows[i]['project_FCFF']/(1+r)**(i+1) for i in range(10))+rows[10]['project_NOPAT']*factor/(1+r)**10
        bridge=opening['group_cash']-opening['operating_cash'];resource=operating_value+bridge
        normal=q(doc['path']['aux_normalized_legacy_NOPAT'][name]);aux=normal*factor+project_value+bridge
        answers[name]={'discount':r,'growth':g,'terminal_incremental_ROIC':roc,'holder_current_equity':holder,'holder_current_per_share':holder/shares,
            'Y5_equity':y5,'Y5_per_share':y5/shares,'Y5_definition':'Only subsequent actual constrained D plus certified normal dividend continuation; no full cash5 or FCFF substitution',
            'normalized_terminal_year':N,'terminal_next_D':chain['terminal_next_D'],'terminal_value_at_N':tv,'terminal_certificate':chain['certificate'],
            'conditional_resource_current_equity':resource,'conditional_resource_current_per_share':resource/shares,'conditional_resource_operating_current':operating_value,
            'conditional_financial_bridge_current':bridge,'holder_minus_conditional_resource':holder-resource,'project_NPV_resource_basis':project_value,
            'aux_resource_equity':aux,'aux_resource_per_share':aux/shares,'aux_normalized_legacy_NOPAT':normal,
            'method_gap_same_conditional_resource':(aux-resource)/resource if resource else 'UNDEFINED_ZERO_RESOURCE',
            'resource_conditions':'Immediate ordinary access or equivalent frictionless ownership realization; excludes payout delays and dividend transfer taxes; auxiliary only, not adopted holder value'}
    need(answers['low']['holder_current_equity']<=answers['high']['holder_current_equity'],'Endpoint order reversal requires economic review, not sorting')
    need(answers['low']['Y5_per_share']<=answers['high']['Y5_per_share'],'Y5 endpoint order reversal requires review')
    return {'opening':chains['low']['opening'],'project_budget':operating['project_budget'],'operating_rows':rows,'endpoint_cash_chains':chains,'endpoints':answers,
        'return_model':{'as_of':c['as_of'],'terminal_date':'2031-10-31','same_base':True,'distributions_per_share':first5,
            'terminal_per_share_low':answers['low']['Y5_per_share'],'terminal_per_share_high':answers['high']['Y5_per_share']},
        'definition':'REVISION2 actual ordinary D throughout; finite normal-release certification, never automatic liquidation or permanent interest-only residual'}




def set_field(obj,dotted,value):
    parts=dotted.split('.');target=obj
    for part in parts[:-1]:target=target[part]
    need(parts[-1] in target,'Patch field not present: '+dotted);target[parts[-1]]=value
