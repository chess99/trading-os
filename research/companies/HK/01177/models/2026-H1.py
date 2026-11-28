"""python 2026-H1.py：以同目录输入复算每股港元估值并写出简明结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def present_value(distributions, terminal, discount):
    return sum(value / (1 + discount) ** year
               for year, value in enumerate(distributions, start=1)) + terminal / (1 + discount) ** len(distributions)


def ownership_bridge(facts, profile):
    liquid = (facts['net_cash_including_wmp'] - profile['liquidity_reserve']) * profile['financial_owner_share']
    cash_obligations = (facts['ct_cost'] + sum(facts['paid_dividends']) + facts['other_consideration']
                        + facts['lease'] + facts['post_h1_buyback_hkd'] * facts['cny_per_hkd'])
    investments = sum(facts['nonoperating_assets']) * profile['financial_owner_share'] * profile['investment_realisation']
    return liquid - cash_obligations + investments


def forecast(data, p, fixed_dividends=None):
    facts, a = data['facts'], data['assumptions']
    shares = facts['issued'] - facts['pending_cancel'] + facts['acquisition_shares']
    conversion = shares * facts['cny_per_hkd']
    bridge = ownership_bridge(facts, p)
    innovative, other = a['initial_innovative_sales'], a['initial_other_sales']
    retained = 0
    dividends, cash_flows, reinvestment, profits = [], [], [], []
    for year in range(5):
        previous_sales = innovative + other
        innovative *= 1 + p['innov_growth']
        other *= 1 + p['other_growth']
        sales = innovative + other
        operating_profit = sales * p['product_ebit_margin'] + p['licence_annual'] * p['licence_ebit_margin']
        common = operating_profit * (1 - a['tax_rate']) * p['owner_share']
        new_capital = (max(0, sales - previous_sales) * p['incremental_capital_sales']
                       + sales * p['recurring_net_investment_sales']) * p['owner_share']
        cash = common - new_capital
        dividend = (min(max(0, cash), common * p['payout']) if fixed_dividends is None
                    else fixed_dividends[year] * conversion)
        assert 0 <= dividend <= cash
        retained += cash - dividend
        profits.append(common)
        reinvestment.append(new_capital)
        dividends.append(dividend / conversion)
        cash_flows.append(cash / conversion)
    assert isclose(sum(profits) - sum(reinvestment), retained + sum(dividends) * conversion)
    terminal = (profits[-1] * p['exit_multiple'] + retained + bridge) / conversion
    primary = present_value(dividends, terminal, p['discount'])
    growth, roic = p['terminal_growth'], p['terminal_roic']
    # 方法二于现金可支配时确认，用稳态投资回报率约束增长所需的投资。
    steady_cash = profits[-1] * (1 + growth) * (1 - growth / roic)
    alternative = present_value(cash_flows, (steady_cash / (p['discount'] - growth) + bridge) / conversion, p['discount'])
    return dict(primary=round(primary,2),alternative=round(alternative,2),terminal=round(terminal,4),
                dividends=[round(v,4) for v in dividends],final_common=round(profits[-1],3),
                first_common=round(profits[0],3),year2_to_year5_capital=round(sum(reinvestment[1:]),3),
                final_innovative=round(innovative,3),final_other=round(other,3),retained=round(retained,3),
                bridge=round(bridge,3),terminal_pv_share=round(terminal / (1+p['discount'])**5 / primary,3))


def run(data):
    assert present_value([1,1],10,0)==12
    assert isclose(present_value([1,1],10,.1),10)
    f=data['facts']
    assert isclose(f['noncontrolling_income']+f['attributable_income'],f['total_income'])
    results={k:forecast(data,p) for k,p in data['profiles'].items()}
    lower, upper = results['base_low'], results['base_high']
    distributions = [round((low + high) / 2, 4) for low, high in zip(lower['dividends'], upper['dividends'])]
    for key in ['base_low', 'base_high']:
        results[key] = forecast(data, data['profiles'][key], distributions)
    order=['structural_bear','cyclical_bear','base_low','base_high','bull']
    values=[results[k]['primary'] for k in order]
    assert values==sorted(values) and min(values)>0
    lower,upper=results['base_low'],results['base_high']
    return dict(symbol=data['symbol'],report_period=data['period'],value_range=dict(low=lower['primary'],high=upper['primary'],currency='HKD'),
                return_model=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='HKD',model_as_of=data['cutoff'],
                base_case_distributions_per_share=distributions,base_case_terminal_equity_value_range_per_share={'year_5':dict(low=lower['terminal'],high=upper['terminal'])}),
                diluted_shares_bn=f['issued']-f['pending_cancel']+f['acquisition_shares'],profiles=results)


if __name__=='__main__':
    data=json.loads((ROOT/'2026-H1-input.json').read_text())
    (ROOT/'2026-H1-output.json').write_text(json.dumps(run(data),ensure_ascii=False,indent=2)+'\n')
