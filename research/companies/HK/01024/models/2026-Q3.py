"""运行 python3 2026-Q3.py，生成同目录简明结果。金额十亿元人民币，价值每股港元。"""
from pathlib import Path
import json
from math import isclose


def bridge(inputs):
    fx = inputs['fx_cny_per_hkd']
    executed = inputs['post_period_repurchases']
    cash = sum(inputs['liquid_assets'].values()) - sum(inputs['capital_claims'].values())
    cash -= sum(number * price * fx for number, price in executed)
    shares = sum(inputs['shares_bn'].values()) - sum(number for number, _ in executed)
    return cash, shares


def value(inputs, case):
    cash, shares = bridge(inputs)
    fx, tax = inputs['fx_cny_per_hkd'], inputs['tax']
    discount = case['discount_rate']
    previous_sales = inputs['starting_revenue_bn']
    distribution_pv, investment_total = 0, 0
    assert all(len(case[key]) == 5 for key in ('revenue_bn', 'cash_operating_margin', 'net_fixed_investment_bn', 'dividend_hkd'))
    for year, (sales, margin, equipment, dividend) in enumerate(zip(
        case['revenue_bn'], case['cash_operating_margin'], case['net_fixed_investment_bn'],
        case['dividend_hkd']
    ), start=1):
        profit = sales * margin * (1 - tax)
        investment = equipment + max(0, sales - previous_sales) * inputs['working_capital_ratio']
        free_cash = profit - investment
        awards = shares * case['award_share_fraction']
        repurchased = shares * case['buyback_share_fraction']
        payment = repurchased * case['execution_cny']
        shares_after = shares + awards - repurchased
        dividend_total = shares_after * dividend * fx
        redemption_interest = 0
        if year == 5:
            redemption_interest = (inputs['kling_completed_subscription_bn'] *
                                   inputs['kling_simple_annual_return'] * year *
                                   case['redemption_interest_fraction'])
        cash_after = cash + free_cash - dividend_total - payment - redemption_interest
        assert isclose(cash + free_cash, cash_after + dividend_total + payment + redemption_interest)
        assert cash_after >= 0 and shares_after > 0
        cash, shares, previous_sales = cash_after, shares_after, sales
        distribution_pv += dividend / (1 + discount) ** year
        if year > 1:
            investment_total += investment
        if year == 1:
            first_profit = profit
    growth = case['terminal_growth']
    reinvestment_rate = growth / case['terminal_incremental_roic']
    assert 0 <= reinvestment_rate < 1 and growth < discount
    # 到稳态后以替代现金薪酬覆盖持续激励，持股分母固定。现金薪酬不另计税盾。
    replacement_cost = shares * case['award_share_fraction'] * case['execution_cny']
    sustainable_cash = (profit * (1 + growth) * (1 - reinvestment_rate) - replacement_cost)
    terminal = (cash + sustainable_cash / (discount - growth)) / (shares * fx)
    multiple_terminal = (cash + (profit - replacement_cost) * case['check_nopat_multiple']) / (shares * fx)
    present = distribution_pv + terminal / (1 + discount) ** 5
    cross = distribution_pv + multiple_terminal / (1 + discount) ** 5
    return dict(present=round(present,2), terminal=round(terminal,2), cross=round(cross,2),
                terminal_pv_share=round(1-distribution_pv/present,3), end_cash_bn=round(cash,3),
                end_shares_bn=round(shares,4), incremental_profit_bn=round(profit-first_profit,2),
                incremental_investment_bn=round(investment_total,2), ending_nopat_bn=round(profit,2))


def self_check(inputs, reference):
    # 10股、每年10元经营利润、全分配、零增长、10%资本成本。第五年末业务价值100元。
    test = dict(inputs, liquid_assets={},capital_claims={},post_period_repurchases=[],
                shares_bn={'test':10},fx_cny_per_hkd=1,tax=0,working_capital_ratio=0)
    case = dict(reference,revenue_bn=[100]*5,cash_operating_margin=[.1]*5,
                net_fixed_investment_bn=[0]*5,dividend_hkd=[1]*5,discount_rate=.1,
                buyback_share_fraction=0,award_share_fraction=0,terminal_growth=0,
                redemption_interest_fraction=0,check_nopat_multiple=10)
    result = value(test, case)
    assert (result['present'],result['terminal'],result['cross']) == (10,10,10)


def main():
    directory = Path(__file__).resolve().parent
    inputs = json.loads((directory/'2026-Q3-input.json').read_text())
    cases = inputs['scenarios']
    self_check(inputs,cases['base_low'])
    details = {key:value(inputs,case) for key,case in cases.items()}
    anchors = {key:row['present'] for key,row in details.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    base = cases['base_low']
    assert base['dividend_hkd'] == cases['base_high']['dividend_hkd']
    net_buyback = (base['buyback_share_fraction'] - base['award_share_fraction']) * base['execution_cny'] / inputs['fx_cny_per_hkd']
    sensitivity = {}
    for key in ('base_low','base_high'):
        reduced = dict(cases[key],cash_operating_margin=[m - .01 for m in cases[key]['cash_operating_margin']])
        sensitivity[key] = value(inputs,reduced)['present']
    outputs = dict(sensitivity_all_margins_minus_one_point_hkd=sensitivity,symbol=inputs['symbol'],report_period=inputs['report_period'],
        value_range=dict(currency='HKD',low=anchors['base_low'],high=anchors['base_high']),
        return_model=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='HKD',
            model_as_of=inputs['as_of'],base_case_distributions_per_share=base['dividend_hkd'],
            base_case_terminal_equity_value_range_per_share={'year_5':{
                'low':details['base_low']['terminal'],'high':details['base_high']['terminal']}}),
        scenario_values_hkd=anchors,details=details,initial_excess_cash_bn=round(bridge(inputs)[0],3),
        diluted_shares_bn=round(bridge(inputs)[1],5),annual_net_buyback_hkd_per_share=round(net_buyback,3))
    (directory/'2026-Q3-output.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    main()
