"""创科实业估值。运行 python 2026-H1.py，在同目录重建简明结果。"""
from pathlib import Path
import json
import math

BASE = Path(__file__).resolve().parent
data = json.loads((BASE / "2026-H1-input.json").read_text())
facts = data["facts"]
settings = data["model"]
fx = data["fx_hkd_per_usd"]


def present_value(dividends, terminal, rate):
    return sum(d / (1 + rate) ** year for year, d in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def project(path):
    sales = facts["fy_sales"] + facts["h1_sales"] - facts["prior_h1_sales"]
    pro = sales * facts["professional_share"]
    consumer = sales - pro
    bridge = data["bridge"]
    reserve = (facts["cash"] - facts["current_borrowings"] - facts["long_borrowings"]
               - bridge["september_dividend_usd"]
               - bridge["post_june_buyback_cash_estimate"] - bridge["minimum_operating_cash"])
    shares = facts["issued"] - facts["pending_cancellation"] + facts["options_increment"] + facts["awards_increment"]
    start_shares = shares
    dividends = []
    track = []
    capital = 0
    for year, (pg, cg) in enumerate(zip(path["professional_growth"], path["consumer_growth"]), 1):
        pro *= 1 + pg
        consumer *= 1 + cg
        delta = pro + consumer - sales
        sales = pro + consumer
        # 正增长同步补充厂房、模具、开发支出及存货应收；销量下滑时固定资本无法变现。
        investment = (max(delta, 0) * path["net_growth_fixed_capital_share"]
                      + max(delta, delta * .25) * settings["net_growth_capital_working_share"])
        capital += investment
        pm = facts["professional_h1_margin"] + year / 5 * (path["professional_margin_y5"] - facts["professional_h1_margin"])
        cm = facts["consumer_h1_margin"] + year / 5 * (path["consumer_margin_y5"] - facts["consumer_h1_margin"])
        income = (pro * pm + consumer * cm - settings["lease_interest"]) * (1 - path["tax"])
        available = income - investment
        buy = 0
        if year == 1:
            # 工资预算已费用化，抵销新发奖励的购股视同现金薪酬；额外现金对应净注销。
            buy = max(0, path["first_year_gross_buybacks"] - settings["future_awards_million"] * settings["assumed_repurchase_hkd"] / fx)
            shares -= buy * fx / settings["assumed_repurchase_hkd"]
            annual_net = buy * fx / start_shares / 5
        assert reserve + available >= buy
        distributed = min(path["payout"] * income, reserve + available - buy)
        closing = reserve + available - distributed - buy
        assert min(distributed, closing) >= -1e-8
        assert math.isclose(reserve + available, closing + distributed + buy)
        reserve = closing
        dividends.append(distributed / shares * fx)
        track.append(dict(income=income,capital=capital,sales=sales,shares=shares))
    g, r = path["perpetuity_growth"], path["discount"]
    needed = sales * g * (settings["net_growth_capital_working_share"] + path["net_growth_fixed_capital_share"])
    next_income = ((pro * pm + consumer * cm) * (1 + g) - settings["lease_interest"]) * (1 - path["tax"])
    terminal = ((next_income - needed) / (r - g) + reserve) * fx / shares
    value = present_value(dividends, terminal, r)
    peer = [present_value(dividends, (income * multiple + reserve) * fx / shares, r)
            for multiple in settings["reference_exit_multiple"]]
    return dict(value=round(value,2),dividends=[round(d,4) for d in dividends],
                terminal=round(terminal,4),terminal_fraction=round(terminal / (1+r)**5 / value,4),
                multiple_crosscheck=[round(x,2) for x in peer],annual_net=round(annual_net,4),
                y1=track[0],y5=track[-1],closing_reserve=round(reserve,1))


assert math.isclose(present_value([5], 105, .10), 100)
runs = {key: project(path) for key, path in data["paths"].items()}
ordered = [run["value"] for run in runs.values()]
assert sorted(ordered) == ordered
low, high = runs["base_low"], runs["base_high"]
assert low["dividends"] == high["dividends"]
result = dict(symbol=data["symbol"],report_period=data["period"],
              value_range=dict(low=low["value"],high=high["value"],currency="HKD"),
              scenarios=dict(currency="HKD",**{k:v["value"] for k,v in runs.items()},
                             horizon_note="五年专业与消费工具分别预测，资本随收入变化，按稳态再投资后的可分配现金估计第五年末价值。"),
              return_model=dict(schema_version=1,method="annual_common_equity_irr_v1",currency="HKD",model_as_of=data["as_of"],
                                base_case_distributions_per_share=low["dividends"],
                                base_case_terminal_equity_value_range_per_share=dict(year_5=dict(low=low["terminal"],high=high["terminal"]))),
              annual_net_buyback_per_share=low["annual_net"],details=runs)
base_path = data["paths"]["base_low"]
lower_margin = dict(base_path, professional_margin_y5=base_path["professional_margin_y5"] - .01)
result["professional_margin_down_1pp"] = project(lower_margin)["value"]
(BASE / "2026-H1-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
