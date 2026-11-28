"""在任意目录运行 python3 /path/to/2026-Q3.py，读取同目录输入并重建结果。"""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def present_value(cash_flows, terminal, rate):
    years = len(cash_flows)
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(cash_flows, 1)) + terminal / (1 + rate) ** years


def operating_year(revenue, growth, margin, capex_rate, depreciation_rate, working_capital_rate):
    next_revenue = revenue * (1 + growth)
    profit = next_revenue * margin
    capex = next_revenue * capex_rate
    # 不预支衰退期的营运资本回收，包含支持业务所需的增量现金。
    working_capital = max(next_revenue - revenue, 0) * working_capital_rate
    net_investment = capex - next_revenue * depreciation_rate + working_capital
    cash_flow = profit - net_investment
    assert abs(cash_flow + net_investment - profit) < 1e-8
    return next_revenue, profit, capex, net_investment, cash_flow


def equity_bridge(facts, recovery):
    assets = facts['cash_equivalents'] + facts['liquid_investments'] - facts['operating_cash_reserve']
    assets += recovery * (facts['long_financial_assets'] + facts['equity_investments'])
    claims = sum(facts[key] for key in ('deferred_tax_liability', 'short_loans', 'current_maturities', 'long_loans', 'leases', 'minority_equity'))
    return assets - claims


def evaluate(facts, case):
    growth, margins, capex_rate, dep_rate, wc_rate, rate, multiple, recovery, transition, steady, steady_roic = case
    shares = facts['issued_shares'] + facts['incremental_award_shares_budget']
    bridge = equity_bridge(facts, recovery)
    revenue = facts['base_revenue']
    years = []
    assert len(growth) == len(margins) == 5
    for growth_rate, margin in zip(growth, margins):
        year = operating_year(revenue, growth_rate, margin, capex_rate, dep_rate, wc_rate)
        years.append(year)
        revenue = year[0]
    # H1合同未披露在Q3的未付余额，前两年付款预算保留H1的全部上限。
    assert sum(year[2] for year in years[:2]) >= facts['committed_h1']
    cash_flows = [year[4] for year in years]
    profit = years[-1][1]
    terminal = profit * multiple
    main = present_value(cash_flows, terminal, rate) + bridge
    # 辅助法独立以再投资回报与永续现金估算剩余经营权。
    # 过渡期每年利润增长所需的资本按期初投入，投资回报由第1至5年配对结果渐近稳态。
    invested = sum(year[3] for year in years[1:])
    incremental_return = (profit - years[0][1]) / invested
    transition_roic = max(incremental_return, steady_roic)
    next_growth = [transition + (steady - transition) * i / 5 for i in range(6)]
    for index in range(5):
        profit *= 1 + next_growth[index]
        earn_rate = transition_roic + (steady_roic - transition_roic) * (index + 1) / 5
        cash_flows.append(profit * (1 - next_growth[index + 1] / earn_rate))
    perpetual = profit * (1 + steady) * (1 - steady / steady_roic) / (rate - steady)
    auxiliary = (present_value(cash_flows, perpetual, rate) + bridge) / shares
    return {
        'main': round(main / shares, 2), 'auxiliary': round(auxiliary, 2),
        'bridge': round(bridge, 2), 'fully_diluted_shares': shares, 'year5_revenue': round(revenue, 2),
        'year5_profit': round(years[-1][1], 2), 'first_five_fcff': [round(cash, 2) for cash in cash_flows[:5]],
        'year5_terminal_operations': round(terminal, 2),
        'pv_terminal_share_of_equity': round(terminal / (1 + rate) ** 5 / main, 4),
        'years2_5_investment': round(invested, 2), 'years1_5_incremental_roic': round(incremental_return, 4)
    }


def main():
    assert abs(present_value([10], 100, 0.10) - 100) < 1e-10
    assert operating_year(100, 0, 0.20, 0.05, 0.05, 0.6) == (100, 20, 5, 0, 20)
    data = json.loads((ROOT / '2026-Q3-input.json').read_text())
    results = {key: evaluate(data['facts'], case) for key, case in data['cases'].items()}
    anchors = {key: result['main'] for key, result in results.items()}
    assert list(anchors.values()) == sorted(anchors.values()) and min(anchors.values()) >= 0
    output = {
        'symbol': data['symbol'], 'report_period': data['report_period'],
        'value_range': {'low': anchors['base_low'], 'high': anchors['base_high'], 'currency': 'CNY'},
        'scenarios': {**anchors, 'currency': 'CNY'}, 'return_model': None,
        'return_model_note': '新基地及备货占用现金，H股发行规模和五年派息政策尚未确定。按五年经营利润矩阵折现，以十年经营自由现金交叉估值。',
        'cases': results
    }
    (ROOT / '2026-Q3-output.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
