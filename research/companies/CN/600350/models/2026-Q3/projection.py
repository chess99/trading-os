"""Read-only center-state terminal projection. No five-year cash simulation.
Only the pinned producer's build_plan/value_state functions may be called.
Company output is deliberately not embedded; independent review can use this source blind.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def pinned_bytes(path, expected):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Pinned file changed: ' + str(path))
    return raw


def checked_json(raw):
    return json.loads(raw)


def load_producer(path, expected):
    pinned_bytes(path, expected)
    spec = importlib.util.spec_from_file_location('frozen_source_producer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def future_plan(data, central, endpoint, date, options):
    """Accounting composition uncertainty at a FIXED common-equity snapshot.
    Reallocate remaining book inside that same total; never rewrite past profit/tax/cash.
    """
    e = data['initial_estimates']; center_ep = data['endpoints']['central']
    new_initial = data['observed'].get('weilai_invested', 0.0) if data.get('weilai') else 0.0
    weights = {}
    for name, item in central.items():
        r = item['meta']
        if not r.get('new_project'):
            weights[name] = r['initial_book'] * (endpoint['qilu_book_weight']/center_ep['qilu_book_weight'] if r.get('qilu') else 1.0)
    denominator = sum(weights.values())
    out = {}; book_bridge = []
    for name, item in central.items():
        r = copy.deepcopy(item['meta']); history = item['years']
        original_end = r['end_year']
        if r.get('new_project') and options.get('weilai_operating_years') is not None:
            r['end_year'] = r['opening_year'] + options['weilai_operating_years']
        if r['end_year'] > original_end:
            raise ValueError('No extension beyond frozen rights')
        if any(row['growth_capex'] > 1e-10 for year, row in history.items() if year > date):
            raise ValueError('Remaining construction needs a separate funded design')
        original_basis = r['initial_book']
        if r.get('new_project'):
            original_basis += sum(r['future_capex'].values()) * data['scenarios']['base']['capex_multiplier']
            alternative_basis = original_basis
        else:
            alternative_basis = (endpoint['road_book_total']-new_initial)*weights[name]/denominator if denominator else 0.0
        total_revenue = sum(row['revenue'] for row in history.values())
        consumed = sum(row['revenue'] for year,row in history.items() if year <= date)/total_revenue if total_revenue else 1.0
        original_left = original_basis * max(0.0, 1.0-consumed)
        alternative_left = alternative_basis * max(0.0, 1.0-consumed)
        cohorts = []
        for year, row in history.items():
            if year <= date and row['capital_maintenance']:
                life = min(5, original_end-year+1)
                if year+life-1 > date:
                    cohorts.append((year, row['capital_maintenance'], life))
        maintenance_left = sum(amount*(start+life-1-date)/life for start,amount,life in cohorts)
        center_book = history.get(date, {}).get('book', 0.0)
        if abs(center_book-original_left-maintenance_left) > 1e-7:
            raise ValueError('Historical road carrying bridge does not close: '+name)
        carrying = alternative_left + maintenance_left
        rows = {date: {'book':carrying}}
        future_revenues = {}
        for year in range(date+1, r['end_year']+1):
            center_revenue = history[year]['revenue']
            # Existing physical rights are frozen; only FUTURE growth/revenue expectations vary.
            if r['end_year'] != original_end and year == r['end_year']:
                center_revenue *= r.get('end_fraction', 1.0)
            revenue = center_revenue*((1+r['growth']+endpoint['road_growth_shift'])/(1+r['growth']))**(year-date)
            if r.get('new_project'):
                revenue *= options.get('weilai_revenue_multiplier', 1.0)
            future_revenues[year] = revenue
        remaining_revenue = sum(future_revenues.values())
        for year, revenue in future_revenues.items():
            fraction = r.get('end_fraction',1.0) if year == r['end_year'] else 1.0
            inflation = (1+e['cash_cost_inflation'])**max(0,year-2026)
            cost_ratio = r['cash_cost_ratio'] + data['scenarios']['base']['cash_cost_add']
            fixed = r['net_anchor']*cost_ratio*0.70*inflation*fraction
            variable = revenue*cost_ratio*0.30
            overhead = r['net_anchor']*e['road_overhead_ratio']*inflation*fraction
            large = r.get('large_maintenance_cash',0.0) if year in r.get('large_maintenance_years',[]) else 0.0
            maintenance = revenue*r['maintenance_ratio']
            if maintenance:
                cohorts.append((year,maintenance,min(5,r['end_year']-year+1)))
            original_da = alternative_left*revenue/remaining_revenue if remaining_revenue else 0.0
            maintenance_da = sum(amount/life for start,amount,life in cohorts if start<=year<start+life)
            da = original_da+maintenance_da
            ebitda = revenue-fixed-variable-overhead-large
            tax_da = original_da*options.get('tax_depreciation_factor',1.0)+maintenance_da
            tax = max(0.0,ebitda-tax_da)*e['tax_rate']
            carrying += maintenance-da
            rows[year] = dict(revenue=revenue,ebitda=ebitda,depreciation=da,tax_depreciation=tax_da,tax=tax,
                              capital_maintenance=maintenance,growth_capex=0.0,fcff=ebitda-tax-maintenance,book=carrying)
        if abs(carrying)>1e-7:
            raise ValueError('Finite right retains unexplained book at expiry: '+name)
        out[name] = dict(meta=r,years=rows)
        common_delta = (rows[date]['book']-center_book)*r['ownership']
        book_bridge.append(dict(road=name,center_book=center_book,conditional_book=rows[date]['book'],ownership=r['ownership'],
                               common_road_reclassification=common_delta,residual_common_net_assets_reclassification=-common_delta,
                               historical_original_cost_consumed_fraction=consumed,unamortized_historical_maintenance=maintenance_left))
    return out, book_bridge


def new_nonroad_adjustment(data, endpoint, spent, mode='existing_mix'):
    """Cost has ALREADY left cash. This is ONLY the value correction to retained assets.
    Existing units' original capital and later growth spending are separate cohorts.
    """
    if mode == 'at_cost':
        return dict(adjustment=0.0,group_cost=spent,mode=mode)
    if mode == 'all_common_total_loss':
        return dict(adjustment=-spent,group_cost=spent,common_cost_proxy=spent,recovery_factor=0.0,mode=mode)
    if mode != 'existing_mix':
        raise ValueError('Unknown nonroad mode')
    net = common = weighted_value = 0.0
    for unit in data['nonroad_units']:
        group_net = unit['assets']-unit['liabilities']
        common_net = group_net-unit['minority_book']
        if group_net <= 0 or common_net < 0 or common_net > group_net:
            raise ValueError('Invalid nonroad ownership proxy')
        factor = min(1.0,max(0.0,unit['base_value_factor']+endpoint['nonroad_factor_shift']))
        net += group_net; common += common_net; weighted_value += common_net*factor
    fraction = common/net if net else 0.0
    recovery = weighted_value/common if common else 1.0
    return dict(adjustment=spent*fraction*(recovery-1.0),group_cost=spent,common_cost_proxy=spent*fraction,
                common_fraction_proxy=fraction,recovery_factor=recovery,mode=mode)


def project_snapshot(producer, data, central_plan, state, endpoint, spent, options):
    before = copy.deepcopy(state)
    plan, bridge = future_plan(data,central_plan,endpoint,state['year'],options)
    scenario = copy.deepcopy(data['scenarios']['base'])
    if 'g220_parent_financing_loss_share' in options:
        scenario['g220_parent_financing_loss_share'] = options['g220_parent_financing_loss_share']
    result = producer.value_state(data,scenario,endpoint,state,plan)
    adjustment = new_nonroad_adjustment(data,endpoint,spent,options.get('new_nonroad_mode','existing_mix'))
    result['ordinary_equity'] += adjustment['adjustment']
    result['per_share'] = result['ordinary_equity']/state['shares']
    if state != before:
        raise ValueError('The fixed historical state was mutated')
    return dict(value=result,nonroad_new_capital=adjustment,book_composition_bridge=bridge,
                fixed_state_unchanged=True,road_cashflows=plan)


def hard_issues(case, tolerance):
    issues=[]
    if not case['cash_path_feasible']:
        issues.append('cash_path_infeasible')
    for row in case['rows']:
        for key in ['funding_gap','debt_consistency_gap']:
            if row[key]>tolerance:
                issues.append(str(row['year'])+':'+key)
    return issues


def valid_range(low, high):
    return math.isfinite(low) and math.isfinite(high) and 0<=low<=high


def interface_projection(data, calculation, low_terminal, high_terminal, tolerance):
    current_issues=[]
    for name,case in [('base',calculation['base']),('core_low',calculation['cases']['core_low']),('core_high',calculation['cases']['core_high'])]:
        current_issues += [name+':'+x for x in hard_issues(case,tolerance)]
    lo=calculation['cases']['core_low']['current']['per_share'];hi=calculation['cases']['core_high']['current']['per_share']
    if not valid_range(lo,hi):current_issues.append('current_range_invalid')
    d=[r['distribution_per_share'] for r in calculation['base']['rows']]
    holder_issues=hard_issues(calculation['base'],tolerance)
    if not valid_range(low_terminal,high_terminal):holder_issues.append('conditional_terminal_range_invalid')
    if len(d)!=5 or not all(math.isfinite(x) and x>=0 for x in d):holder_issues.append('distribution_vector_invalid')
    return dict(value_range=None,
                diagnostic_unadopted_current_range=dict(low=lo,high=hi,currency='CNY') if valid_range(lo,hi) else None,
                current_adoption_status='pending_new_capital_npv_bridge_materiality',
                return_model=None if holder_issues else dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',
                    model_as_of=data['identity']['cutoff'],base_case_distributions_per_share=d,
                    base_case_terminal_equity_value_range_per_share={'year_5':{'low':low_terminal,'high':high_terminal}}),
                current_blockers=current_issues+['pending_new_capital_npv_bridge_materiality'],holder_blockers=holder_issues)


def conditional_output(producer, data, calculation, settings):
    if data['identity']!=calculation['identity']:raise ValueError('Input/result identity mismatch')
    state=copy.deepcopy(calculation['base']['final_state'])
    if state['year']!=settings['terminal_year']:raise ValueError('Wrong terminal date')
    if settings['first_uncertain_operating_year']!=state['year']+1:raise ValueError('Wrong uncertainty start')
    if hard_issues(calculation['base'],settings['numerical_tolerance']):raise ValueError('Cannot project from an infeasible cash state')
    if any(int(y)>state['year'] and amount for y,amount in data['other_capital']['g220_future_capex'].items()):
        raise ValueError('Unfunded post-terminal G220 capital outside scope')
    plan=producer.build_plan(data,data['scenarios']['base'],data['endpoints']['central'])
    spent=sum(row['nonroad_growth_capex'] for row in calculation['base']['rows'])
    central=project_snapshot(producer,data,plan,state,data['endpoints']['central'],spent,{'new_nonroad_mode':'at_cost'})
    reproduction={}
    for key in ['ordinary_equity','per_share','attributable_road_pv','attributable_road_book','nonroad_adjustment','g220_adjustment','rolling_financial_adjustment']:
        difference=central['value'][key]-calculation['base']['terminal'][key]
        reproduction[key]=difference
        if abs(difference)>settings['reproduction_tolerance']:raise ValueError('Center reproduction failed: '+key)
    cases={}
    for name in ['core_low','core_high']:
        endpoint=data['endpoints'][settings[name+'_source_endpoint']]
        cases[name]=project_snapshot(producer,data,plan,state,endpoint,spent,{'tax_depreciation_factor':settings['tax_depreciation_factor']})
    diagnostics={}
    configurations=[('road_book_78','road_book_total',78.0),('road_book_82_5','road_book_total',82.5),
                    ('qilu_weight_1','qilu_book_weight',1.0),('qilu_weight_1_5','qilu_book_weight',1.5),
                    ('discount_4_5pct','road_discount',0.045),('discount_6_5pct','road_discount',0.065),
                    ('future_growth_minus_25bp','road_growth_shift',-0.0025),('future_growth_plus_25bp','road_growth_shift',0.0025),
                    ('nonroad_minus_005','nonroad_factor_shift',-0.05),('nonroad_plus_005','nonroad_factor_shift',0.05),
                    ('g220_zero_recovery','g220_value_factor',0.0),('g220_at_cost','g220_value_factor',1.0)]
    for name,key,value in configurations:
        ep=copy.deepcopy(data['endpoints']['central']);ep[key]=value
        diagnostics[name]=project_snapshot(producer,data,plan,state,ep,spent,{})
    options=[('weilai_20_years',{'weilai_operating_years':20}),('weilai_revenue_0_44',{'weilai_revenue_multiplier':0.8}),
             ('weilai_revenue_0_66',{'weilai_revenue_multiplier':1.2}),('zero_remaining_original_tax_basis',{'tax_depreciation_factor':0.0}),
             ('new_nonroad_at_cost',{'new_nonroad_mode':'at_cost'}),('new_nonroad_all_common_total_loss',{'new_nonroad_mode':'all_common_total_loss'})]
    for name,option in options:
        diagnostics[name]=project_snapshot(producer,data,plan,state,data['endpoints']['central'],spent,option)
    for label,share in [('none',0.0),('full',1.0)]:
        ep=copy.deepcopy(data['endpoints']['central']);ep['g220_value_factor']=0.0
        diagnostics['g220_zero_recovery_external_rescue_'+label]=project_snapshot(producer,data,plan,state,ep,spent,{'g220_parent_financing_loss_share':share})
    for name in ['core_low','core_high']:
        diagnostics[name+'_new_nonroad_at_cost']=project_snapshot(producer,data,plan,state,data['endpoints'][name],spent,{'new_nonroad_mode':'at_cost'})
    interfaces=interface_projection(data,calculation,cases['core_low']['value']['per_share'],cases['core_high']['value']['per_share'],settings['numerical_tolerance'])
    return dict(status='conditional_projection_only_not_research_acceptance',identity=data['identity'],interfaces=interfaces,
                center_reproduction_differences=reproduction,fixed_state=state,
                fixed_distributions=[r['distribution_per_share'] for r in calculation['base']['rows']],
                cases=cases,diagnostics=diagnostics,original_issues_retained=calculation['issues'],
                structural_terminal_adopted=False,full_five_year_simulation_rerun=False)


def hand_cases(producer, production):
    x=copy.deepcopy(production);e=x['initial_estimates'];o=x['observed']
    e.update(tax_rate=0.25,road_cash_cost_ratio=0.0,road_overhead_ratio=0.0,road_capital_maintenance_ratio=0.0,
             cash_cost_inflation=0.0,extra_nonroad_common_value_adjustment=0.0,g220_value_factor=1.0)
    o.update(fy25_toll_revenue_net=1.0,fy25_toll_revenue_gross=1.0,weilai_invested=0.0,g220_common_ownership=0.5219,
             g220_group_registered_capital=0.778,g220_parent_equity_cost=0.406)
    x['identity'].update(historical_stub_fraction=0.0,valuation_stub_years=0.0)
    x['weilai']=None;x['recovery_assets']=[];x['nonroad_units']=[];x['other_capital']['g220_future_capex']={}
    x['roads']=[dict(id='closed',net_anchor_override=40.0,gross_2025=40.0,ytd_2026_wan=1.0,ytd_2025_wan=1.0,
                    ownership=1.0,mother_direct=True,end_year=2033,end_fraction=1.0,growth=0.0)]
    ep=dict(road_discount=0.0,road_growth_shift=0.0,road_book_total=210.0,qilu_book_weight=1.0,nonroad_factor_shift=0.0)
    x['endpoints']['central']=ep
    state=dict(year=2031,common_book=100.0,shares=1.0,g220_group_cost_proxy=0.0,g220_mother_support_cumulative=0.0,
               financial_cohorts=[],maintenance_overlap_common=0.0,group_cash=5.0,mother_cash=2.0,group_debt=10.0,mother_debt=4.0,perpetual=0.0)
    plan=producer.build_plan(x,x['scenarios']['base'],ep)
    a=project_snapshot(producer,x,plan,state,ep,0.0,{})
    assert abs(a['value']['ordinary_equity']-115.0)<1e-8
    changed=dict(ep,road_book_total=280.0)
    b=project_snapshot(producer,x,plan,state,changed,0.0,{})
    assert abs(b['value']['ordinary_equity']-100.0)<1e-8
    assert abs(b['book_composition_bridge'][0]['common_road_reclassification']-20.0)<1e-8
    assert abs(b['book_composition_bridge'][0]['residual_common_net_assets_reclassification']+20.0)<1e-8
    assert a['fixed_state_unchanged'] and b['fixed_state_unchanged']
    c=project_snapshot(producer,x,plan,state,ep,0.0,{'tax_depreciation_factor':0.0})
    assert abs(c['value']['ordinary_equity']-100.0)<1e-8
    for r in b['road_cashflows']['closed']['years'].values():
        if 'tax' in r:assert r['tax']==0.0
    x['nonroad_units']=[dict(id='closed',assets=20.0,liabilities=10.0,minority_book=4.0,base_value_factor=0.75)]
    d=project_snapshot(producer,x,plan,state,ep,10.0,{})
    assert abs(d['nonroad_new_capital']['adjustment']+1.5)<1e-8
    assert abs(d['value']['ordinary_equity']-112.0)<1e-8
    row=dict(year=2027,funding_gap=0.0,debt_consistency_gap=0.0,forced_distribution_shortfall=1.0,distribution_per_share=1.0)
    case=dict(cash_path_feasible=True,rows=[dict(row,year=y) for y in range(2027,2032)],current={'per_share':10.0})
    calc=dict(base=copy.deepcopy(case),cases={'core_low':copy.deepcopy(case),'core_high':copy.deepcopy(case)})
    i=interface_projection(x,calc,10.0,12.0,1e-8)
    assert i['value_range'] is None and i['return_model'] is not None
    assert i['diagnostic_unadopted_current_range']==dict(low=10.0,high=10.0,currency='CNY')
    assert i['current_blockers']==['pending_new_capital_npv_bridge_materiality']
    calc['cases']['core_low']['rows'][0]['funding_gap']=1.0
    j=interface_projection(x,calc,10.0,12.0,1e-8)
    assert j['value_range'] is None and j['return_model'] is not None
    assert any('funding_gap' in issue for issue in j['current_blockers'])
    calc['base']['rows'][0]['funding_gap']=1.0
    k=interface_projection(x,calc,10.0,12.0,1e-8)
    assert k['value_range'] is None and k['return_model'] is None
    return dict(closed_cases=7,executed=True,scope='four closed terminal-value examples plus three interface eligibility cases')
