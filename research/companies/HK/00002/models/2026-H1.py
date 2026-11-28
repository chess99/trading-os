"""以 Python 运行本文件，读取同目录输入并重建 2026-H1-output.json。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def present_value(dividends, terminal, rate):
    return sum(amount / (1 + rate) ** year for year, amount in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def project(opening_profit, shares, case):
    hk = case['annual_net_investment_hk'] * (1 - case['borrowed_fraction'])
    other = case['annual_net_investment_other'] * (1 - case['borrowed_fraction'])
    added_profit = hk * case['incremental_roe_hk'] + other * case['incremental_roe_other']
    rate, growth = case['required_return'], case['stable_growth']
    dividends = []
    for year, (shock, payment) in enumerate(zip(case['earnings_adjustments'], case['extra_cash_payments'], strict=True)):
        profit = opening_profit + year * added_profit + shock
        dividend = (profit - hk - other - payment) / shares
        assert dividend >= 0 and isclose(dividend * shares + hk + other + payment, profit)
        dividends.append(dividend)
    assert len(dividends) == 7 and 0 <= growth < min(rate, case['stable_roe'])
    profit8 = (opening_profit + 7 * added_profit + case['earnings_adjustments'][-1]) * case['post_2033_profit_factor']
    terminal7 = profit8 * (1 - growth / case['stable_roe']) / (rate - growth) / shares
    terminal5 = present_value(dividends[5:], terminal7, rate)
    equity = present_value(dividends[:5], terminal5, rate)
    assert isclose(equity, present_value(dividends, terminal7, rate))
    return {'dividends': [round(x, 4) for x in dividends[:5]], 'terminal5': round(terminal5, 4),
            'value': round(equity, 2), 'terminal_share_of_value': round(terminal5 / (1 + rate) ** 5 / equity, 4),
            'common_net_investment': round(hk + other, 4), 'annual_profit_added': round(added_profit, 4)}


def calculate(data):
    f = data['facts']
    for total, parts in [(f['total_equity'], [f['common_equity'], f['perpetual'], f['other_nci']]),
                         (f['gross_debt'], [f['net_debt'], f['liquid_assets']]),
                         (f['h1_profit'], [f['h1_common_profit'], f['h1_perpetual_profit'], f['h1_nci_profit']])]:
        assert isclose(total, sum(parts))
    # 无增长、无投入、每年一元且回报要求10%时，七年过渡与永续合计均值10元。
    flat = dict(data['scenario_parameters']['base_low'], annual_net_investment_hk=0,
                annual_net_investment_other=0, required_return=.1, stable_growth=0, post_2033_profit_factor=1)
    assert project(1, 1, flat)['value'] == 10
    profits = data['opening_normalized_profit']
    paths = {key: project(sum(profits.values()), f['shares'], case) for key, case in data['scenario_parameters'].items()}
    low, high = paths['base_low'], paths['base_high']
    values = {key: path['value'] for key, path in paths.items()}
    assert list(values.values()) == sorted(values.values()) and low['dividends'] == high['dividends']
    alternative = [round(sum(value * data['regional_multiples'][key][i] for key, value in profits.items()) / f['shares'], 2) for i in (0, 1)]
    return {'symbol': 'HK:00002', 'report_period': '2026-H1',
            'value_range': {'currency':'HKD','low':low['value'],'high':high['value']},
            'return_model': {'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'HKD',
                'model_as_of':data['cutoff'],'base_case_distributions_per_share':low['dividends'],
                'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':low['terminal5'],'high':high['terminal5']}}},
            'scenarios':dict(values, currency='HKD', horizon_note='各情景均折现至资料截止。前七年扣除普通股承担的净投资和额外付款，2033年协议到期后按续期回报、再投资率和资金成本收敛。'),
            'sotp_per_share':alternative,'scenario_calculations':paths,'common_equity_bn':f['common_equity'],'net_debt_bn':f['net_debt']}


if __name__ == '__main__':
    inputs = json.loads((HERE / '2026-H1-input.json').read_text())
    (HERE / '2026-H1-output.json').write_text(json.dumps(calculate(inputs), ensure_ascii=False, indent=2) + '\n')
