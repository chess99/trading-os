"""用 Python 3 运行本文件，在同目录生成简明估值结果。"""
import json
from pathlib import Path
from math import isclose

root = Path(__file__).resolve().parent
data = json.loads((root / '2026-H1-input.json').read_text())
f = data['facts']
bridge = data['bridge']
sales = f['fy25_sales'] - f['prior_h1_sales'] + f['h1_sales']
unit = f['shares'] * f['cny_per_hkd']
cash = (f['bank_cash'] + (f['other_financial_assets'] + f['fvtpl_assets']) * bridge['financial_asset_recovery']
        - f['bank_debt'] - f['minority_equity'] - f['paid_interim_hkd'] * f['cny_per_hkd']
        - bridge['operating_reserve'])
upstream = bridge['remittance_net']


def operating_year(prior, growth, margin, cash_gap, capital_per_sales):
    revenue = prior * (1 + growth)
    investment = max(0, revenue - prior) * capital_per_sales
    earnings = revenue * margin
    cash_flow = earnings - revenue * cash_gap - investment
    return revenue, earnings, investment, cash_flow


def value(path, starting_sales, opening_cash, remittance, per_share_unit):
    revenue = starting_sales
    retained = opening_cash
    dividends = []
    investment = []
    profits = []
    for growth, margin in zip(path['growth'], path['margin']):
        revenue, profit, reinvestment, free = operating_year(
            revenue, growth, margin, path['cash_gap'], path['capital_per_sales'])
        distribution = max(0, free) * path['payout']
        prior_cash = retained
        retained += free - distribution
        assert retained >= 0 and isclose(prior_cash + free, retained + distribution)
        dividends.append(distribution * remittance / per_share_unit)
        investment.append(reinvestment)
        profits.append(profit)
    rate = path['discount']
    g = path['steady_growth']
    assert rate > g
    steady_free = operating_year(revenue, g, margin, path['cash_gap'], path['capital_per_sales'])[3]
    terminal = (steady_free / (rate - g) + retained) * remittance / per_share_unit
    terminal_pv = terminal / (1 + rate) ** len(dividends)
    present = terminal_pv + sum(d / (1 + rate) ** t for t, d in enumerate(dividends, 1))
    return dict(present=present, terminal=terminal, dividends=dividends, terminal_share=terminal_pv / present,
                profits=profits, investment=investment, retained=retained)


# 无增长、100%派发，每期利润1元，10%折现，永续每股即为10元。
flat = dict(growth=[0]*5, margin=[0.1]*5, cash_gap=0, capital_per_sales=0, payout=1,
            discount=0.1, steady_growth=0)
assert isclose(value(flat, 10, 0, 1, 1)['present'], 10)
paths = data['paths']
estimated = {name:value(path, sales, cash, upstream, unit) for name,path in paths.items()}
anchors = {k:round(x['present'], 2) for k,x in estimated.items()}
assert list(anchors.values()) == sorted(anchors.values())
lo, hi = estimated['base_low'], estimated['base_high']
assert lo['dividends'] == hi['dividends']
terminal = dict(low=round(lo['terminal'], 4), high=round(hi['terminal'], 4))
# 独立盈利检验直接将未来一年的租后经营利润资本化，加回一次可用金融净资产。
first_profit = lo['profits'][0]
aux = {k:round((first_profit * m + cash) * upstream / unit, 2)
       for k,m in data['earnings_check'].items()}
margin_shock = dict(paths['base_low'])
margin_shock['margin'] = [m - 0.01 for m in margin_shock['margin']]
value_shock = value(margin_shock, sales, cash, upstream, unit)['present'] / lo['present'] - 1
output = {
    'symbol':data['symbol'], 'report_period':data['report_period'],
    'value_range':dict(low=anchors['base_low'], high=anchors['base_high'], currency='HKD'),
    'return_model':dict(schema_version=1, method='annual_common_equity_irr_v1', currency='HKD',
                        model_as_of=data['as_of'], base_case_distributions_per_share=[round(d,4) for d in lo['dividends']],
                        base_case_terminal_equity_value_range_per_share={'year_5':terminal}),
    'scenarios':anchors, 'earnings_check_hkd':aux, 'excess_net_assets_cny_bn':round(cash,4),
    'base_terminal_pv_share':[round(x['terminal_share'],4) for x in (lo,hi)],
    'base_y1_to_y5_profit_gain':round(lo['profits'][4]-lo['profits'][0],4),
    'base_y1_end_to_y5_end_incremental_capital':round(sum(lo['investment'][1:]),4),
    'one_point_margin_shock_low_change':round(value_shock,4)
}
(root / '2026-H1-output.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
