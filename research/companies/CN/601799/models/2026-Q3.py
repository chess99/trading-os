"""星宇普通股现金模型。单位：百万元、百万股、元/股。

python 2026-Q3.py                 只输出轻量正式字段
python 2026-Q3.py --details       十年表、情景和灵敏度
python 2026-Q3.py --check         正式函数手算例及现金守恒

输入：相邻2026-Q3-inputs.json；无下载缓存或历史Git依赖。
"""
from __future__ import annotations
import argparse, copy, json, math
from pathlib import Path

P = Path(__file__).parent
DATA = json.loads((P / '2026-Q3-inputs.json').read_text(encoding='utf-8'))
F = DATA['facts']


def discounted(cashflows, rate, terminal):
    """Formal valuation function, annual end-of-period convention."""
    n = len(cashflows)
    return sum(c / (1 + rate) ** (i + 1) for i, c in enumerate(cashflows)) + terminal / (1 + rate) ** n


def going_concern(capital, required_cash, nopat, growth, rate, cash_yield):
    """Next-year cash earnings less reinvestment in fixed/NWC/required cash.

    The return on existing capital follows from forecast NOPAT / actual modeled
    capital; growth does not arrive without funding. Required cash principal is
    not also added to the equity bridge.
    """
    assert rate > growth >= 0
    next_nopat = nopat * (1 + growth)
    next_cash_interest = required_cash * cash_yield
    reinvestment = growth * (capital + required_cash)
    fcf = next_nopat + next_cash_interest - reinvestment
    return fcf / (rate - growth), fcf, reinvestment


def simulate(overrides=None):
    a = copy.deepcopy(DATA['base'])
    if overrides:
        a.update(overrides)
    group_cash = (F['cash_equivalents_q3'] + F['liquid_investments_q3']
                  - F['paid_october_dividend'] - F['new_buyback_paid_october']
                  - F['debt_and_leases_q3'] - F['minority_equity_q3'] + a['opening_common_cash_adjustment'])
    cash = [a['parent_opening_liquid_cash'], a['domestic_subs_opening_liquid_cash'], 0]
    cash[2] = group_cash - sum(cash)
    retained = [F['parent_h1_retained_earnings'] - F['paid_october_dividend'] + a['parent_retained_adjustment'],
                a['domestic_subs_opening_distributable_profit'], a['overseas_opening_retained_loss']]
    capital = a['opening_nwc'] + a['opening_net_fixed_operating_capital']
    nwc = a['opening_nwc']
    shares = F['issued_shares'] - F['new_buyback_shares_held']
    rows = []
    assets = F['strategic_financial_assets_q3']
    for i, (rev, margin, da, capex, abroad_profit) in enumerate(zip(
        a['revenues'], a['cash_operating_margin'], a['depreciation'], a['capex'], a['overseas_common_profit'])):
        year = i + 1
        before = sum(cash)
        opening_cash = cash[:]
        interest = [c * a['cash_yield_after_tax'] for c in cash]
        nopat = rev * margin * (1 - a['tax_rate'])
        domestic_profit = nopat * a['domestic_subs_profit_share']
        profit = [nopat - domestic_profit - abroad_profit, domestic_profit, abroad_profit]
        profit = [x + y for x, y in zip(profit, interest)]
        delta_nwc = rev * a['nwc_ratio'] - nwc
        nwc += delta_nwc
        net_reinvestment = capex - da + delta_nwc
        capital += net_reinvestment
        fcf = [profit[j] + da * a['depreciation_allocation'][j]
               - capex * a['capex_allocation'][j] - delta_nwc * a['nwc_change_allocation'][j]
               for j in range(3)]
        cash = [x + y for x, y in zip(cash, fcf)]
        # Domestic legal reserves are extra retained equity, not cash expense.
        reserves = max(profit[1], 0) * .10
        retained = [retained[0] + profit[0], retained[1] + profit[1] - reserves,
                    retained[2] + profit[2]]
        floors = [rev * a['minimum_cash_ratio'] * w for w in a['cash_floor_allocation']]
        floors[2] += a['overseas_floor_extra']
        injections = [0., 0., 0.]
        # Fund necessary operations/capital before discretionary parent dividends.
        # Contributions purchase subsidiary equity; no expense or group cash creation.
        for j in [1, 2]:
            injections[j] = max(floors[j] - cash[j], 0.)
            cash[j] += injections[j]
            cash[0] -= injections[j]
        upstream = [0., 0., 0.]
        tax_leakage = 0.
        if year >= a['subsidiary_upstream_start_year']:
            for j in [1, 2]:
                upstream[j] = max(min(cash[j] - floors[j], retained[j]), 0.)
                cash[j] -= upstream[j]
                retained[j] -= upstream[j]
                leakage = upstream[j] * (a['cross_border_dividend_friction'] if j == 2 else 0)
                tax_leakage += leakage
                cash[0] += upstream[j] - leakage
                retained[0] += upstream[j] - leakage
        recovery = 0.
        realised_loss = 0.
        if year == a['strategic_asset_recovery_year']:
            recovery = assets * a['strategic_asset_recovery_ratio']
            realised_loss = assets - recovery
            # H1 parent had 502m of group holdings; retain cash at actual funding
            # locations rather than treating all subsidiary disposal proceeds as
            # immediately available mother cash.
            parent_part = a['strategic_asset_parent_share']
            cash[0] += recovery * parent_part
            cash[2] += recovery * (1-parent_part)
            retained[0] -= realised_loss * parent_part
            retained[2] -= realised_loss * (1-parent_part)
            assets = 0.
        repurchase = 0.
        if year == 1:
            repurchase = F['remaining_minimum_buyback_cash'] + a['buyback_fees_budget']
            cash[0] -= repurchase
            shares -= F['remaining_minimum_buyback_cash'] / F['buyback_price_ceiling']
            # Existing employee-purpose shares stay in fully diluted shares.
        policy = a['first_five_distribution_profit_ratio'] if year <= 5 else a['later_distribution_profit_ratio']
        target = policy * max(nopat + sum(interest), 0)
        if year > 5:
            target += a['later_extra_parent_cash_release_ratio'] * max(cash[0] - 2 * floors[0], 0)
        available = max(min(cash[0] - floors[0], retained[0]), 0.)
        distribution = min(target, available)
        cash[0] -= distribution
        retained[0] -= distribution
        # Funding failure is an actual modeled shortfall; never rounded into pass.
        shortfall = max(floors[0] - cash[0], 0.)
        check = (sum(cash) - before - sum(fcf) + tax_leakage - recovery + repurchase + distribution)
        assert abs(check) < 1e-8, check
        assert abs(sum(fcf) - (nopat + sum(interest) - net_reinvestment)) < 1e-8
        rows.append(dict(year=year, revenue=rev, margin=margin, nopat=nopat,
            profit_including_liquid_interest=nopat+sum(interest), depreciation=da, capex=capex,
            delta_nwc=delta_nwc, capital=capital, operating_fcf=nopat-net_reinvestment,
            opening_entity_cash=opening_cash, entity_cash=cash[:], entity_retained=retained[:],
            floors=floors, injections=injections, upstream=upstream, foreign_tax_leakage=tax_leakage,
            strategic_recovery=recovery, strategic_realised_loss=realised_loss,
            buyback_cash=repurchase, shares=shares, distribution=distribution,
            distribution_per_share=distribution/shares, target_distribution=target,
            distribution_cut=target-distribution, funding_shortfall=shortfall,
            cash_conservation_residual=check))
    return dict(inputs=a, rows=rows, remaining_strategic_assets=assets,
                opening_common_liquid_cash=group_cash, closing_cash=cash, closing_retained=retained)


def terminal_equity(sim, rate=None, growth=None, from_year=None):
    a = sim['inputs']
    rate = a['cost_of_equity'] if rate is None else rate
    growth = a['terminal_growth'] if growth is None else growth
    row = sim['rows'][(from_year or len(sim['rows'])) - 1]
    required = sum(row['floors'])
    enterprise, fcf, reinvestment = going_concern(row['capital'], required, row['nopat'], growth, rate, a['cash_yield_after_tax'])
    # Do not assume unknown opening legal reserves / capital can be paid out.
    eligible=range(1) if a['exclude_subsidiary_terminal_cash'] else range(3)
    available_cash = sum(max(min(row['entity_cash'][j]-row['floors'][j],row['entity_retained'][j]),0) for j in eligible)
    excluded_excess = sum(max(c-f, 0) for c,f in zip(row['entity_cash'],row['floors'])) - available_cash
    # An unsold financial holding is valued with recovery/time friction. Main
    # terminal is Y10, after Y6 recovery, so normally this item is zero.
    remaining = sim['remaining_strategic_assets']
    if row['year'] < a['strategic_asset_recovery_year']:
        remaining = F['strategic_financial_assets_q3']
    delay = max(a['strategic_asset_recovery_year'] - row['year'],0)
    financial_asset_value = remaining * a['strategic_asset_recovery_ratio']/(1+rate)**delay
    equity = enterprise + available_cash + financial_asset_value
    return dict(equity=equity, enterprise=enterprise, terminal_fcf=fcf, reinvestment=reinvestment,
        required_cash=required, available_excess_cash=available_cash,
        excluded_legal_excess_cash=excluded_excess, financial_asset_value=financial_asset_value,
        implied_roic_next=row['nopat']*(1+growth)/(row['capital']+required),
        equity_per_share=equity/row['shares'], rate=rate, growth=growth)


def value(sim, rate=None, growth=None):
    a = sim['inputs']
    rate = a['cost_of_equity'] if rate is None else rate
    terminal = terminal_equity(sim, rate, growth)
    divs = [r['distribution'] for r in sim['rows']]
    # Shares constant after Y1 cancellation; no interim equity issuance.
    shares = sim['rows'][-1]['shares']
    total = discounted(divs, rate, terminal['equity']) / shares
    terminal_share = terminal['equity']/(1+rate)**len(divs)/(total*shares)
    return dict(value_per_share=total, terminal_pv_share=terminal_share, terminal=terminal)


def continuation_at_five(sim, rate, growth):
    """Same real Y5 cash/retained/share state; only Y6+ discount/steady growth vary."""
    terminal = terminal_equity(sim, rate, growth)
    future = [r['distribution'] for r in sim['rows'][5:]]
    shares = sim['rows'][4]['shares']
    return discounted(future, rate, terminal['equity'])/shares


def auxiliary(sim, rate, growth):
    """Mature cash-earnings capitalisation at Y3, no further high-growth premium.

    This intentionally tests the commercial alternative that product engineering
    maintains share but cannot sustain the main path's growth beyond year 3.
    Its capitalisation multiple follows from required reinvestment, not peers.
    """
    t = terminal_equity(sim,rate,growth,from_year=3)
    shares = sim['rows'][2]['shares']
    result = discounted([r['distribution'] for r in sim['rows'][:3]],rate,t['equity'])/shares
    return dict(value_per_share=result, terminal=t,
        nopat_cash_multiple=t['enterprise']/sim['rows'][2]['nopat'])


def run_all():
    base = simulate()
    # Core endpoints describe the SAME finite recovery path with reasonable
    # margin, capital, collection and capital-cost variation, not bear/bull bounds.
    lo = simulate({'cash_operating_margin':[x-.003 for x in DATA['base']['cash_operating_margin']],
        'capex':[x*1.05 for x in DATA['base']['capex']], 'nwc_ratio':.185})
    hi = simulate({'cash_operating_margin':[x+.003 for x in DATA['base']['cash_operating_margin']],
        'capex':[x*.97 for x in DATA['base']['capex']], 'nwc_ratio':.175})
    low = value(lo,.1025,.015)
    high = value(hi,.0925,.02)
    y5lo = continuation_at_five(base,.1025,.015)
    y5hi = continuation_at_five(base,.0925,.02)
    vr = {'low':round(low['value_per_share'],2),'high':round(high['value_per_share'],2),'currency':'CNY'}
    rm = dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=DATA['information_cutoff'],
        base_case_distributions_per_share=[round(r['distribution_per_share'],6) for r in base['rows'][:5]],
        base_case_terminal_equity_value_range_per_share={'year_5':{'low':round(y5lo,6),'high':round(y5hi,6)}})
    valuation_note = ('主方法为十年经营、必要资本与母子现金联动的普通股现金折现；国内有限恢复、海外缓慢贡献，'
        '研发持续费用化，收入152至234亿元、正常正常化税前经营利润率9.2%至10%，资本成本9.25%-10.25%，'
        '十年后增长1.5%-2%且按经营资本配套再投资。核心端点同时改变利润空间、资本支出和占款。'
        '辅助为第三年成熟现金收益资本化，检验较短成长持续期，未机械平均。已付股息和回购扣除，'
        '专项应付款按政府补助而非借款处理。子公司法定储备与现金地点用注明的预算和敏感性约束。')
    return_note = ('五项为同一基准下未来五个十二个月持续持有人实际现金分红预算，首五年不依赖子公司上划；'
        '先投入、补资并保留营运现金，再按正常利润38%且受母现金/法定利润约束分配。'
        'Y5终值从同一Y5现金、资本和股本状态继续研究Y6-Y10，随后按相容增长与资本回报资本化。'
        '已付2026中期0.20元及公开市场回购不计D；剩余回购及费用扣现金、按148.31元上限预算股份注销，'
        '未来完全稀释股数约284.790106百万股，旧员工库存假设全部转授且不收款；未发生H股发行未计入。'
        '已分红现金不再留在终值，必要现金不在权益桥重复相加。')
    formal = dict(schema='trading_os_research_result_v1',symbol=DATA['symbol'],report_period=DATA['report_period'],
        information_cutoff=DATA['information_cutoff'],value_range=vr,return_model=rm,
        valuation_note=valuation_note,return_model_note=return_note)
    details = dict(formal=formal,base=base,core_low=dict(simulation=lo,valuation=low),core_high=dict(simulation=hi,valuation=high),
        base_valuation=value(base),auxiliary_low=auxiliary(base,.1025,.015),auxiliary_high=auxiliary(base,.0925,.02))
    cases = {}
    # Complete alternative business paths: timing, profits, capex and collections
    # change together. All use the same actual payment constraints.
    cases['cyclical_weak'] = simulate({
        'revenues':[13200,13700,15100,17000,18500,19610,20590.5,21517.0725,22377.7554,23160.976839],
        'cash_operating_margin':[.070,.074,.085,.095,.10,.10,.10,.10,.10,.10],
        'capex':[1250,1150,1200,1250,1250,1200,1200,1200,1220,1240],
        'nwc_ratio':.20,'overseas_common_profit':[-45,-30,0,25,45,65,80,90,100,110]})
    cases['structural_adverse'] = simulate({
        'revenues':[14500,14300,14100,13900,13700,13837,13975.37,14115.1237,14256.274937,14398.83768637],
        'cash_operating_margin':[.072,.065,.060,.060,.060,.060,.060,.060,.060,.060],
        'capex':[1200,1000,900,900,900,950,990,1030,1070,1110],
        'nwc_ratio':.21,'overseas_common_profit':[-45,-35,-15,0,5,10,15,20,25,30],
        'first_five_distribution_profit_ratio':.30,'later_distribution_profit_ratio':.50})
    cases['optimistic'] = simulate({
        'revenues':[16200,18000,20000,22000,24000,25800,27477,29125.62,30581.901,31805.17704],
        'cash_operating_margin':[.098,.105,.11,.112,.115,.115,.115,.115,.115,.115],
        'capex':[1650,1700,1600,1550,1500,1500,1500,1500,1550,1600],
        'nwc_ratio':.175,'overseas_common_profit':[-10,20,60,100,140,160,180,200,220,240]})
    details['scenarios']={k:dict(valuation=value(v,.105 if k=='structural_adverse' else .0975,
        .01 if k=='structural_adverse' else .02),simulation=v) for k,v in cases.items()}
    sensitivities={
        'margin_minus_1pp': {'cash_operating_margin':[x-.01 for x in DATA['base']['cash_operating_margin']]},
        'capex_plus_30pct':{'capex':[x*1.30 for x in DATA['base']['capex']]},
        'nwc_plus_3pp':{'nwc_ratio':.21},
        'parent_cash_minus_300':{'parent_opening_liquid_cash':2550},
        'group_opening_cash_minus_300':{'opening_common_cash_adjustment':-300,'parent_opening_liquid_cash':2550},
        'parent_legal_profit_minus_1000':{'parent_retained_adjustment':-1000},
        'financial_assets_zero_recovery':{'strategic_asset_recovery_ratio':0},
        'overseas_opening_loss_600':{'overseas_opening_retained_loss':-600},
        'extra_1000_capex_first_three':{'capex':[x+(1000/3 if i<3 else 0) for i,x in enumerate(DATA['base']['capex'])]},
        'accelerated_extra_2500_capex_first_three':{'capex':[x+(2500/3 if i<3 else 0) for i,x in enumerate(DATA['base']['capex'])]},
        'no_subsidiary_upstream_ten_years':{'subsidiary_upstream_start_year':11},
        'no_subsidiary_upstream_and_no_terminal_cash':{'subsidiary_upstream_start_year':11,'exclude_subsidiary_terminal_cash':True},
        'overseas_cash_350_ring_fenced':{'overseas_floor_extra':350}}
    result={}
    for k,o in sensitivities.items():
        s=simulate(o)
        v=value(s)
        result[k]=dict(value_per_share=v['value_per_share'],change=v['value_per_share']-value(base)['value_per_share'],
            min_parent_cash=min(x['entity_cash'][0] for x in s['rows']),
            max_funding_shortfall=max(x['funding_shortfall'] for x in s['rows']),
            distribution_cuts=sum(x['distribution_cut'] for x in s['rows']),
            first_five_dps=[x['distribution_per_share'] for x in s['rows'][:5]])
    details['sensitivities']=result
    return formal, details


def checks():
    # The production valuation and terminal functions receive hand-solvable inputs.
    assert abs(discounted([10,10],.10,100)-100) < 1e-12
    # K=100, required cash=0, NOPAT=12, g=2%, r=10%:
    # next earnings 12.24, reinvestment 2, cash 10.24, EV=128.
    ev,cf,re=going_concern(100,0,12,.02,.10,0)
    assert abs(ev-128)<1e-12 and abs(cf-10.24)<1e-12 and abs(re-2)<1e-12
    formal,d=run_all()
    for sim in [d['base'],d['core_low']['simulation'],d['core_high']['simulation']]+[x['simulation'] for x in d['scenarios'].values()]:
        for row in sim['rows']:
            assert row['funding_shortfall'] < 1e-8
            assert row['distribution'] >= 0
            assert row['entity_retained'][0] >= -1e-8
            assert abs(row['cash_conservation_residual'])<1e-8
    return {'formal_function_hand_cases':'passed','cash_and_owner_reconciliation':'passed',
        'scope':'base, two core endpoints and three complete business scenarios; isolated capex/collection sensitivities can force dividend cuts',
        'first_five_years_no_subsidiary_dividend':all(sum(x['upstream'])==0 for x in d['base']['rows'][:5])}


if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('--details',action='store_true');p.add_argument('--check',action='store_true');args=p.parse_args()
    formal,details=run_all()
    print(json.dumps(checks() if args.check else details if args.details else formal,ensure_ascii=False,indent=2))
