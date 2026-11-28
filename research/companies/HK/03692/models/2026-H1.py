"""运行 python3 2026-H1.py，在本目录生成简明结果。"""
import json
from pathlib import Path
from math import isclose

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / '2026-H1-input.json').read_text())


def common_value(pool, shares, bond, conversion):
    """债权人选择收回本金或换股；现金退款与假设转换分别计算。"""
    return min((pool - bond) / shares, pool / (shares + conversion))


def run_case(f, bridge, c):
    fx = f['hkd_cny']
    shares = f['issued'] - f['trust_shares'] + f['outstanding_rsu']
    debt = f['bond_face_hkd'] * fx
    product = f['product_fy25'] - f['product_h125'] + f['product_h126']
    start_cash = (f['bank'] + bridge['illiquid_recovery'] * f['financial_assets']
                  - f['lease'] - f['fy_dividend_payable'] - f['issued'] * f['interim_dps_hkd'] * fx
                  - bridge['buffer'])
    cash = start_cash
    dividends, operating_cash, profits, investments = [], [], [], []
    for year, growth in enumerate(c['sales_growth'], start=1):
        old_product = product
        product *= 1 + growth
        profit = ((product * c['product_ebit_margin'] + c['other_license_bn'] * c['license_contribution'])
                  * (1 - c['tax']))
        investment = product * c['net_capex_on_sales'] + max(product - old_product, 0) * c['working_capital_on_growth']
        regular_fcf = profit - investment
        # 两份期后合同单列；研发履约预算与常态研发互不重叠。
        promised = {1: f['roche_upfront_usd'] + f['bayer_upfront_usd'], 2: f['roche_anniversary_usd']}.get(year, 0)
        special = promised * f['usd_cny'] * c['close_factor'] * (1 - c['obligation_cost']) * (1 - c['tax'])
        distribution = min(c['first_dps_hkd'] * (1 + bridge['dps_growth']) ** (year-1) * fx * shares,
                           bridge['max_distribute_fcf'] * max(regular_fcf, 0))
        cash += regular_fcf + special - distribution
        dividends.append(distribution)
        operating_cash.append(regular_fcf + special)
        profits.append(profit)
        investments.append(investment)
    assert isclose(cash + sum(dividends), start_cash + sum(operating_cash))
    assert cash > 0
    discount = 1 + c['discount']
    pv_dps = sum(d / shares / fx / discount**n for n, d in enumerate(dividends, start=1))
    def today(franchise):
        terminal = common_value(franchise + cash, shares, debt, f['conversion_shares']) / fx
        return pv_dps + terminal / discount**5, terminal
    primary, horizon = today(profits[-1] * c['terminal_multiple'])
    # 辅法逐年衰减至永续增长，以增量资本回报约束再投资。
    g, roic = c['mature_growth'], c['mature_roic']
    profit = profits[-1]
    franchise = 0
    for n in range(1, 6):
        step_growth = c['sales_growth'][-1] + (g - c['sales_growth'][-1]) * n / 5
        profit *= 1 + step_growth
        franchise += profit * (1 - max(step_growth, 0) / roic) / discount**n
    franchise += profit * (1 + g) * (1 - g / roic) / (c['discount'] - g) / discount**5
    secondary, _ = today(franchise)
    assert 0 < pv_dps < primary
    return dict(value=round(primary,2), dcf=round(secondary,2), terminal=round(horizon,2),
                dps=[round(x / shares / fx,4) for x in dividends], terminal_pv_fraction=round(1-pv_dps/primary,3),
                cash_bridge_before_bond=round(start_cash,3), year5_cash_before_bond=round(cash,3),
                year5_sales=round(product,3), year5_profit=round(profits[-1],3),
                year1_profit=round(profits[0],3), incremental_investment_y2_y5=round(sum(investments[1:]),3))


def main():
    assert common_value(120, 10, 20, 2) == 10   # 现金与转股无差异
    assert common_value(80, 10, 20, 2) == 6
    assert common_value(180, 10, 20, 2) == 15
    f, bridge = DATA['facts'], DATA['bridge_assumptions']
    paths = {k:run_case(f,bridge,v) for k,v in DATA['cases'].items()}
    ordered = [v['value'] for v in paths.values()]
    assert ordered == sorted(ordered)
    low, high = paths['base_low'], paths['base_high']
    assert low['dps'] == high['dps']
    output = dict(symbol=DATA['symbol'],report_period=DATA['report_period'],
                  value_range=dict(low=low['value'],high=high['value'],currency='HKD'),
                  return_model=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='HKD',
                                    model_as_of=DATA['information_cutoff'],base_case_distributions_per_share=low['dps'],
                                    base_case_terminal_equity_value_range_per_share={'year_5':dict(low=low['terminal'],high=high['terminal'])}),
                  paths=paths, sensitivity={})
    for label, diff in [('产品税前利润率下降3个百分点',{'product_ebit_margin':DATA['cases']['base_low']['product_ebit_margin']-.03}),
                        ('罗氏和拜耳约定款完全落空',{'close_factor':0}),
                        ('退出倍数少两倍',{'terminal_multiple':14})]:
        output['sensitivity'][label] = run_case(f,bridge,{**DATA['cases']['base_low'],**diff})['value']
    (ROOT/'2026-H1-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    main()
