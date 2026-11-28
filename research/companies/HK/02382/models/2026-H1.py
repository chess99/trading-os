"""运行 python 2026-H1.py，在同目录重建简明结果；输入金额均为人民币十亿元。"""
import json
from math import isclose
from pathlib import Path

DIR = Path(__file__).resolve().parent
data = json.loads((DIR / "2026-H1-input.json").read_text())
cost = data["costs"]
assets = data["assets"]
units = (data["shares_ex_treasury"] + data["treasury_for_awards"]) * data["cny_per_hkd"]

def asset_bridge(case):
    liquid = (assets["cash"] + assets["short_deposits"] + assets["time_deposits"]
              + assets["wealth_products"] * case["wm_recovery"])
    claims = sum(assets[key] for key in ("bank_debt", "bonds", "notes_payable", "equipment_payable",
                                         "operating_buffer", "post_h1_injection"))
    investment = (assets["associates_pre_injection"] + assets["post_h1_injection"]) * case["associate_recovery"]
    share = assets["parent_equity"] / assets["group_equity"]
    return (liquid - claims) * share, investment * share

def present_value(dividends, terminal, rate):
    discounted = [payment / (1 + rate) ** year for year, payment in enumerate(dividends, 1)]
    return sum(discounted) + terminal / (1 + rate) ** len(dividends)

def run(case):
    sales_h1 = data["sales_h1"]
    ltm = sum(sales_h1) + data["sales_fy25"] - data["sales_prior_h1"]
    sales = [amount * ltm / sum(sales_h1) for amount in sales_h1]
    surplus, associates = asset_bridge(case)
    opening = surplus
    dividends, profits, investments = [], [], []
    fcfs = []
    for year in range(5):
        growth = case["later_growth"] if year else case["first_growth"]
        next_sales = [amount * (1 + g) for amount, g in zip(sales, growth)]
        added_sales = sum(max(0, nxt - prev) for nxt, prev in zip(next_sales, sales))
        sales = next_sales
        gross = sum(s * m for s, m in zip(sales, case["gross_margins"]))
        op_profit = gross - sum(sales) * (cost["cash_opex_base_sales"] + case["opex_delta"])
        parent = cost["operating_parent_share"]
        profit = op_profit * (1 - cost["tax"]) * parent
        growth_capital = added_sales * (case["fixed_capital_per_added_sale"] + cost["working_capital_per_added_sale"]) * parent
        maintenance = sum(sales) * cost["maintenance_topup_sales"] * parent
        fcf = profit - maintenance - growth_capital
        dividend = min(max(fcf, 0), max(profit, 0) * case["payout"])
        surplus += fcf - dividend
        assert surplus >= 0
        dividends.append(dividend)
        fcfs.append(fcf)
        profits.append(profit)
        investments.append(growth_capital)
    assert isclose(surplus + sum(dividends), opening + sum(fcfs))
    # 成熟期现金盈利在支付折旧以上的设备更新之后，另按增量资本回报留足永久增长资本。
    rate, g = case["rate"], case["stable_growth"]
    assert rate > g and case["stable_roic"] > g
    recurring = (profits[-1] - maintenance) * (1 + g)
    continuing = recurring * (1 - g / case["stable_roic"]) / (rate - g)
    terminal = (continuing + surplus + associates) / units
    dps = [payment / units for payment in dividends]
    today = present_value(dps, terminal, rate)
    return dict(value=round(today, 2), dps=[round(x, 4) for x in dps], terminal=round(terminal, 2),
                terminal_pv_share=round(terminal / (1 + rate) ** 5 / today, 4),
                opening_surplus=round(opening, 3), associates=round(associates, 3),
                closing_surplus=round(surplus, 3), y5_sales=round(sum(sales), 3),
                y1_y5_profit=[round(profits[0], 3), round(profits[-1], 3)],
                y2_y5_added_capital=round(sum(investments[1:]), 3),
                y5_multiple=round(continuing / profits[-1], 2))

def alternative(rate):
    history = data["alternative"]
    totals = zip(*(history[key] for key in ("gross_profit", "research", "admin", "selling", "annual_sales")))
    profits = [((gross - rd - admin - selling) * (1 - cost["tax"]) - sales * cost["maintenance_topup_sales"])
               * cost["operating_parent_share"] for gross, rd, admin, selling, sales in totals]
    annual_cash = sum(profits) / len(profits)
    opening, associates = asset_bridge(data["base"])
    # 零增长资本化，保守假定净资金与联营权益同样到第五年才可回收。
    return round((annual_cash / rate + (opening + associates) / (1 + rate) ** 5) / units, 2)

assert isclose(present_value([1, 1], 10, 0.10), 10)
low, high = [run(dict(data["base"], rate=r)) for r in data["base_rates"]]
checks = {label: run(data[label]) for label in ("structural", "cyclical", "base", "bull")}
values = [checks["structural"]["value"], checks["cyclical"]["value"], low["value"], high["value"], checks["bull"]["value"]]
assert sorted(values) == values and low["dps"] == high["dps"] and min(values) > 0
scenarios = dict(zip(("structural_bear", "cyclical_bear", "base_low", "base_high", "bull"), values))
scenarios.update(currency="HKD", horizon_note="五年分部销售与毛利路径、设备和周转投入、联营权益回收及成熟期现金回报决定截止日每股港元价值。")
output = dict(symbol=data["symbol"], report_period=data["report_period"], value_range=dict(low=values[2], high=values[3], currency="HKD"),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", model_as_of=data["as_of"], currency="HKD",
                                base_case_distributions_per_share=low["dps"], base_case_terminal_equity_value_range_per_share=dict(
                                    year_5=dict(low=low["terminal"], high=high["terminal"]))), scenarios=scenarios,
              paths=dict(checks, base_low=low, base_high=high), alternative=[alternative(r) for r in data["base_rates"]])
for delta in (-0.02, 0.02):
    margins = list(data["base"]["gross_margins"])
    margins[-1] += delta
    output.setdefault("other_margin_sensitivity", []).append(run(dict(data["base"], gross_margins=margins))["value"])
(DIR / "2026-H1-output.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
