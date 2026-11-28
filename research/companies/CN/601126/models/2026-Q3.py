"""运行 python 2026-Q3.py，由同目录输入生成简明结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def pv(cash, rate):
    return sum(amount / (1 + rate) ** year for year, amount in enumerate(cash, 1))


def settle(opening, legal, parent_cash, earnings, net_investment, parent_income, target, cash_rate):
    """当期税后利息只作用于未付出的合并余额。母子间已上划款不重复计入合并。"""
    available = opening * (1 + cash_rate) + earnings - net_investment
    assert available >= 0
    paid = max(0, min(target, available, legal + parent_income, parent_cash + parent_income))
    closing = available - paid
    assert isclose(closing + paid - opening, opening * cash_rate + earnings - net_investment, abs_tol=1e-8)
    return closing, legal + parent_income - paid, parent_cash + parent_income - paid, paid


def run(data, s):
    f, a = data['facts'], data['assumptions']
    shares = f['registered_shares']
    spend = f['repurchase_total'] - f['repurchase_to_sep'] + f['restricted_cancel_cash']
    cash = (f['cash_equivalents'] + f['marketable_assets'] - f['cash_debt']
            - spend - a['working_cash_floor'] - f['minority_equity'])
    opening_cash = cash
    parent_cash = f['parent_cash_equivalents'] + f['parent_marketable_assets'] - spend - a['parent_cash_floor']
    legal = f['parent_retained']
    sales = f['sales_2025'] - f['sales_9m25'] + f['sales_9m26']
    dividends, profits, capitals, reserves = [], [], [], []
    cumulative_investment = 0
    retained_subs = 0
    distributable_reserves = []
    for year in range(1, 11):
        blend = max(0, (year - 5) / 5)
        growth = s['growth'][year - 1] if year <= 5 else s['growth'][-1] * (1 - blend) + s['g'] * blend
        change = sales * growth
        sales += change
        margin = s['margin'] * (1 - blend) + s['margin_end'] * blend
        profit = sales * margin
        # 需求下行时不预设减员、设备变现或者收回逾期工程款。
        net_investment = max(0, change) * (s['wc'] + s['fixed']) + s['extra'] * (1 - blend)
        cumulative_investment += net_investment
        upstream = s['upstream'] * (1 - blend) + s['terminal_upstream'] * blend
        parent_share = a['parent_profit_share']
        income = profit * (parent_share + (1 - parent_share) * upstream)
        retained_subs += profit * (1 - parent_share) * (1 - upstream)
        payment = s['payout'] * profit
        cash, legal, parent_cash, paid = settle(cash, legal, parent_cash, profit, net_investment,
                                              income, payment, a['reserve_yield'])
        assert min(cash, legal, parent_cash) >= -1e-8
        dividends.append(paid / shares)
        profits.append(profit)
        capitals.append(cumulative_investment)
        reserves.append(cash)
        # 累积留存的上划受限；母公司储备和已上划部分只列一次。
        releasable = min(cash, legal + retained_subs * s['terminal_upstream'])
        distributable_reserves.append(releasable)
    rate, growth = s['r'], s['g']
    assert rate > growth
    year11_profit = sales * (1 + growth) * s['margin_end']
    investment = sales * growth * (s['wc'] + s['fixed'])
    # 长期可分配额同时服从再投资和稳定母公司上划能力；持续滞留款不另外估值。
    distributable = min(year11_profit - investment,
                        year11_profit * (parent_share + (1 - parent_share) * s['terminal_upstream']))
    release = a['cash_release_years']
    terminal = (distributable / (rate - growth) + pv([distributable_reserves[-1] / release] * release, rate)) / shares
    value5 = pv(dividends[5:], rate) + terminal / (1 + rate)**5
    value = pv(dividends[:5], rate) + value5 / (1 + rate)**5
    assert isclose(value, pv(dividends, rate) + terminal / (1 + rate)**10)
    def multiple_value(multiple):
        cash_at_five = pv([distributable_reserves[4] / release] * release, rate)
        return pv(dividends[:5], rate) + (profits[4] * multiple + cash_at_five) / shares / (1 + rate)**5
    return dict(value=value, value5=value5, dividends=dividends[:5], opening_cash=opening_cash,
                year5_cash=reserves[4], profit1=profits[0], profit5=profits[4],
                incremental_capital=capitals[4] - capitals[0], terminal5_fraction=value5 / (1 + rate)**5 / value,
                terminal10_fraction=terminal / (1 + rate)**10 / value,
                cross=[multiple_value(m) for m in data['crosscheck']['earnings_multiple']])


def main():
    assert settle(5, 1, 3, 4, 2, 2, 4, 0) == (4, 0, 2, 3)
    assert isclose(pv([1, 1.1], 0.1), 2/1.1)
    d = json.loads((ROOT / '2026-Q3-input.json').read_text())
    paths = {k:run(d,s) for k,s in d['scenarios'].items()}
    for end, settings in d['base_bounds'].items():
        paths['base_'+end] = run(d, {**d['scenarios']['base'], **settings})
    ordered = ['structural_bear','cyclical_bear','base_low','base_high','bull']
    scenarios = {k:round(paths[k]['value'],2) for k in ordered}
    assert list(scenarios.values()) == sorted(scenarios.values())
    base = paths['base']
    result = dict(symbol=d['symbol'],report_period=d['report_period'],value_range={
        'low':scenarios['base_low'],'high':scenarios['base_high'],'currency':'CNY'},
        scenarios={**scenarios,'currency':'CNY'},return_model={'schema_version':1,'method':'annual_common_equity_irr_v1',
        'currency':'CNY','model_as_of':d['as_of'],'base_case_distributions_per_share':[round(x,4) for x in base['dividends']],
        'base_case_terminal_equity_value_range_per_share':{'year_5':{
        end:round(paths['base_'+end]['value5'],4) for end in ('low','high')}}},
        base_diagnostics={k:v for k,v in base.items() if k!='dividends'})
    sensitivities={'净利率减1个百分点':{'margin':0.086,'margin_end':0.087},
                   '增量营运资本系数加10个百分点':{'wc':0.34},
                   '子公司常态上划60%':{'upstream':0.5,'terminal_upstream':0.6}}
    result['sensitivities']={k:round(run(d,{**d['scenarios']['base'],**v})['value'],2) for k,v in sensitivities.items()}
    (ROOT / '2026-Q3-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    main()
