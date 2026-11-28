"""华润啤酒普通股税前股息及第五年剩余权益。运行后在同目录写出结果。"""
import json
from pathlib import Path
from math import isclose

directory = Path(__file__).resolve().parent
inputs = json.loads((directory / "2026-H1-input.json").read_text())


def discounted_value(dividends, terminal, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def calculate(case, discount):
    scale = inputs["shares"] * inputs["cny_per_hkd"]
    opening = sum(inputs["opening_bridge"].values())
    cash = opening
    units = inputs["beer_volume_fy25"]
    price = inputs["beer_revenue_fy25"] / units
    years = []
    for margin, spirits in zip(case["beer_margin"], case["spirits_ebit"], strict=True):
        prior_revenue = units * price
        units *= 1 + case["volume_growth"]
        price *= 1 + case["asp_growth"]
        revenue = units * price
        # 金沙亏损不给现金税盾，盈利时计所得税。白酒段落以金沙持股近似。
        profits = ((revenue * margin - case["head_office"]) * (1 - inputs["income_tax"])
                   + (spirits - max(spirits, 0) * inputs["income_tax"]) * inputs["jinsha_ownership"])
        reinvestment = case["annual_modernisation"] + max(0, revenue - prior_revenue) * case["growth_capital_per_revenue"]
        free_cash = profits - reinvestment
        dividends = min(profits * case["dividend_ratio"], max(free_cash, 0) * case["upstream_limit"])
        cash += free_cash - dividends
        years.append(dict(revenue=revenue, profits=profits, reinvestment=reinvestment,
                          free_cash=free_cash, dividend=dividends, remaining_cash=cash))
    assert isclose(cash, opening + sum(y["free_cash"] - y["dividend"] for y in years))
    growth = case["steady_growth"]
    forward_profit = years[-1]["profits"] * (1 + growth)
    sustainable_cash = forward_profit * (1 - growth / case["steady_roic"]) - case["annual_modernisation"]
    recovery = inputs["relocation_receivable"] * inputs["relocation_realisation"]
    terminal = (sustainable_cash / (discount - growth) + cash + recovery) / scale
    flows = [y["dividend"] / scale for y in years]
    value = discounted_value(flows, terminal, discount)
    return dict(value=round(value, 2), dividends=[round(v, 4) for v in flows],
                terminal=round(terminal, 2), terminal_pv_share=round(terminal / (1 + discount)**5 / value, 4),
                years=[{k: round(v, 2) for k, v in y.items()} for y in years])


assert isclose(discounted_value([10, 10], 100, 0.10), 100)
assert isclose(inputs["opening_bridge"]["cash_equivalents"] + 236 + 18 - 5208, 9022)
cases = inputs["cases"]
results = {name: calculate(case, case["discount"]) for name, case in cases.items()}
for end, rate in inputs["base_rates"].items():
    results["base_" + end] = calculate(cases["base"], rate)
ordered = ["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"]
values = [results[key]["value"] for key in ordered]
assert values == sorted(values) and values[0] > 0
lo, hi = results["base_low"], results["base_high"]
assert lo["dividends"] == hi["dividends"]
check = inputs["owner_cash_crosscheck"]
normal_cash = check["operating_cash_fy25"] - check["capex_fy25"] - check["lease_principal_fy25"] - check["other_owner_reserve"]
capital = sum(inputs["opening_bridge"].values())
comparison = [round((normal_cash / check[yield_key] + capital + inputs["relocation_receivable"] * inputs["relocation_realisation"] / (1.086**5)) / (inputs["shares"] * inputs["cny_per_hkd"]), 2)
              for yield_key in ("yield_high", "yield_low")]
result = dict(symbol="HK:00291", report_period="2026-H1",
              value_range=dict(currency="HKD", low=lo["value"], high=hi["value"]),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                                model_as_of=inputs["as_of"], base_case_distributions_per_share=lo["dividends"],
                                base_case_terminal_equity_value_range_per_share={"year_5":{"low":lo["terminal"],"high":hi["terminal"]}}),
              scenarios=dict(zip(ordered, values)), cash_crosscheck=comparison, opening_cash=capital, details=results)
(directory / "2026-H1-output.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
