"""在本目录运行 python3 2026-Q3.py，生成同周期结果。仅依赖标准库。"""
import json
from math import isclose
from pathlib import Path

directory = Path(__file__).resolve().parent
data = json.loads((directory / "2026-Q3-input.json").read_text())
facts = data["observed"]
# 月末可发行股数以公告的可行权数量计算，剔除 11 月已行权转为普通股的部分。
nov_exercises = facts["issued_ex_treasury_nov27"] - facts["issued_oct31_ex_treasury"]
shares = (facts["issued_ex_treasury_nov27"] + sum(facts["october_potential_under_options"])
          + facts["october_granted_awards"] - nov_exercises)
denominator = shares * data["fx_cny_per_hkd"]
revenue_start = facts["nine_month_revenue"] * 4 / 3


def project(case, prior_revenue, conversion):
    reserve = 0
    cash_distributions = []
    reinvestment = []
    profits = []
    for volume, selling_price, margin, cash_buffer in zip(
        case["volume"], case["revenue_per_vehicle"], case["common_margin"], case["payment_reserve"], strict=True
    ):
        revenue = volume * selling_price
        profit = revenue * margin
        # 负增长时宁可维持周转预算，不假定渠道和供应商立即返还资金。
        invested = revenue * case["fixed_net_rate"] + max(revenue - prior_revenue, 0) * case["incremental_working_capital_rate"]
        available = profit - invested - cash_buffer
        dividend = max(0, min(profit * case["payout"], available))
        new_reserve = reserve + available - dividend
        assert new_reserve >= 0 and isclose(profit + reserve, new_reserve + invested + cash_buffer + dividend)
        profits.append(profit)
        reinvestment.append(invested)
        cash_distributions.append(dividend / conversion)
        reserve, prior_revenue = new_reserve, revenue

    years = len(profits)
    rate = case["discount"]
    pv_dividends = sum(payment / (1 + rate) ** year for year, payment in enumerate(cash_distributions, 1))
    terminals = [(profits[-1] * multiple + reserve) / conversion for multiple in case["exit_pe"]]
    pv_terminals = [terminal / (1 + rate) ** years for terminal in terminals]
    return {"dividends":cash_distributions, "terminal":terminals, "values":[v + pv_dividends for v in pv_terminals],
            "terminal_weight":[v / (v + pv_dividends) for v in pv_terminals], "reserve":reserve,
            "pv_dividends":pv_dividends, "invested":reinvestment, "profits":profits}


# 手算：一年的收入100、利润10、净投资1、分红2、余留7；8倍终值加余留为87，零贴现合计89。
toy = dict(volume=[1],revenue_per_vehicle=[100],common_margin=[0.1],payment_reserve=[0],
           fixed_net_rate=.01,incremental_working_capital_rate=.16,payout=.2,discount=0,exit_pe=[8])
assert project(toy, 100, 1)["values"] == [89]
cases = {name:project(data[name],revenue_start,denominator) for name in ("structural_bear","cyclical_bear","base","bull")}
base = cases["base"]
r = data["base"]["discount"]
stable = data["steady_state"]
g, capital_return = stable["growth"], stable["incremental_common_return"]
year6_profit = base["profits"][-1] * (1 + g)
steady_value = year6_profit * (1 - g/capital_return) / (r - g)
alternative = base["pv_dividends"] + (steady_value + base["reserve"]) / denominator / (1+r)**5
low, high = [round(v,2) for v in base["values"]]
anchors = dict(structural_bear=round(cases["structural_bear"]["values"][0],2),
               cyclical_bear=round(cases["cyclical_bear"]["values"][0],2),
               base_low=low,base_high=high,bull=round(cases["bull"]["values"][0],2))
assert sorted(anchors.values()) == list(anchors.values())
stress = dict(data["base"], common_margin=[v-.005 for v in data["base"]["common_margin"]])
terminal_low, terminal_high = [round(v,2) for v in base["terminal"]]
result = {
    "symbol":data["symbol"], "report_period":data["period"],"value_range":{"currency":"HKD","low":low,"high":high},
    "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD","model_as_of":data["as_of"],
                    "base_case_distributions_per_share":[round(v,4) for v in base["dividends"]],
                    "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":terminal_low,"high":terminal_high}}},
    "scenarios":anchors,"steady_cash_flow_value_hkd":round(alternative,2),
    "half_point_margin_stress_values":[round(v,2) for v in project(stress,revenue_start,denominator)["values"]],
    "fully_diluted_billion_shares":round(shares,6),"terminal_pv_share":[round(v,4) for v in base["terminal_weight"]],
    "cumulative_new_unearmarked_cash_cny_bn":round(base["reserve"],3),
    "net_reinvestment_cny_bn":[round(v,3) for v in base["invested"]],
    "year1_to_year5_profit_change_cny_bn":round(base["profits"][-1]-base["profits"][0],3),
    "year1_end_to_year5_end_net_investment_cny_bn":round(sum(base["invested"][1:]),3),
}
(directory / "2026-Q3-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
