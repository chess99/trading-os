"""在任意目录执行 python 2026-Q3.py 以重算同目录的结果。金额为百万港元。"""
from pathlib import Path
import json
import math

HERE = Path(__file__).resolve().parent


def run_path(data, scenario):
    facts, common = data['actual'], data['common']
    shares = common['shares_fully_diluted']
    rate, tax = scenario['discount'], common['tax']
    semi_q4 = common['semi_q4_assumed']
    smt_q4 = facts['q4_usd_guidance_mid'] * facts['usd_hkd_assumption'] - semi_q4
    semi = facts['semi_h1'] + facts['semi_q3'] + semi_q4
    smt = facts['smt_h1'] + facts['smt_q3'] + smt_q4
    wc, fixed = scenario['incremental_working_capital'], scenario['incremental_fixed_capital']
    opening_cash = (facts['cash_equivalents'] + facts['time_deposit'] - facts['bank_debt']
                    - facts['committed_investment'] - facts['pension_deficit'] - facts['paid_interim']
                    - common['liquidity_floor'] - scenario['extra_liquidity_floor'])
    funds = opening_cash
    dividends, cash_flows, profits, invested = [], [], [], []
    for y in range(5):
        prior_sales = semi + smt
        semi *= 1 + scenario['semi_growth'][y]
        smt *= 1 + scenario['smt_growth'][y]
        sales = semi + smt
        profit = sales * scenario['operating_margin'][y] * (1 - tax)
        # 需求下行不预支库存释放；正常折旧与维持性资本开支相抵。
        investment = max(sales - prior_sales, 0) * (wc + fixed)
        free_cash = profit - investment - scenario['exceptional_cash'][y]
        dividend = min(common['base_dividend_cap'][y] * scenario['dividend_scale'] * shares,
                       profit * .5, max(0, free_cash + funds))
        funds += free_cash - dividend
        assert funds >= -1e-8
        dividends.append(dividend / shares)
        cash_flows.append(free_cash)
        profits.append(profit)
        invested.append(investment)
    assert math.isclose(funds, opening_cash + sum(cash_flows) - shares * sum(dividends), abs_tol=1e-8)
    associate = facts['associate_book'] * scenario['associate_recovery']
    bridge = funds + associate
    terminal = (profit * scenario['multiple'] + bridge) / shares
    dividend_pv = sum(value / (1 + rate)**year for year, value in enumerate(dividends, 1))
    terminal_pv = terminal / (1 + rate)**5
    value = dividend_pv + terminal_pv
    # 方法二从第六年起显性过渡，持续经营税后利润扣新增资本后折现。
    tail_sales, tail_value = sales, 0
    for year in range(1, 6):
        fraction = year / 5
        growth = scenario['transition_growth'] + (common['terminal_growth'] - scenario['transition_growth']) * fraction
        margin = scenario['operating_margin'][-1] + (scenario['mature_margin'] - scenario['operating_margin'][-1]) * fraction
        increment = tail_sales * growth
        tail_sales += increment
        tail_cash = tail_sales * margin * (1 - tax) - increment * (wc + fixed)
        tail_value += tail_cash / (1 + rate)**year
    growth = common['terminal_growth']
    perpetual_cash = tail_sales * (1 + growth) * margin * (1 - tax) - tail_sales * growth * (wc + fixed)
    tail_value += perpetual_cash / (rate - growth) / (1 + rate)**5
    alternate = dividend_pv + (tail_value + bridge) / shares / (1 + rate)**5
    return {'current':round(value,2),'dividends':[round(d,2) for d in dividends],
            'terminal':round(terminal,2),'cash_dcf':round(alternate,2),
            'terminal_pv_share':round(terminal_pv / value,4),'y5_semi':round(semi,1),
            'y5_smt':round(smt,1),'after_tax_operating_profit_y1_y5':[round(profits[0],1),round(profits[-1],1)],
            'y2_to_y5_incremental_capital':round(sum(invested[1:]),1),'opening_free_cash':round(opening_cash,1),
            'year5_retained_cash':round(funds,1),'year5_associate':round(associate,1)}


def calculate(data):
    paths = {name:run_path(data, assumptions) for name, assumptions in data['scenarios'].items()}
    values = [p['current'] for p in paths.values()]
    assert values == sorted(values) and min(values) >= 0
    low, high = paths['base_low'], paths['base_high']
    assert low['dividends'] == high['dividends']
    holder = {'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'HKD','model_as_of':data['as_of'],
              'base_case_distributions_per_share':low['dividends'],
              'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':low['terminal'],'high':high['terminal']}}}
    return {'symbol':data['symbol'],'report_period':data['period'],
            'value_range':{'low':low['current'],'high':high['current'],'currency':'HKD'},
            'return_model':holder,'paths':paths}


def check_flat_business(data):
    import copy
    sample = copy.deepcopy(data)
    # 收入100，税后利润10，股数10，派息为零，五年后现金50，经营价值100，零折现的结果为15。
    for key in sample['actual']:
        sample['actual'][key] = 0
    sample['actual']['semi_h1'] = 100
    sample['common'].update(shares_fully_diluted=10, semi_q4_assumed=0, liquidity_floor=0,
                            base_dividend_cap=[0]*5, tax=0, terminal_growth=-.01)
    case = dict(sample['scenarios']['base_low'],semi_growth=[0]*5,smt_growth=[0]*5,operating_margin=[.1]*5,
                multiple=10,discount=0,extra_liquidity_floor=0)
    result = run_path(sample, case)
    assert result['current'] == result['terminal'] == 15


if __name__ == '__main__':
    inputs = json.loads((HERE/'2026-Q3-input.json').read_text())
    check_flat_business(inputs)
    (HERE/'2026-Q3-output.json').write_text(json.dumps(calculate(inputs),ensure_ascii=False,indent=2)+'\n')
