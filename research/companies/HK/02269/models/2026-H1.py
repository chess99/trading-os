"""从本目录运行 python3 2026-H1.py，生成港元/普通股的报告结果。"""
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "2026-H1-input.json").read_text())


def equity_bridge(x):
    net = x["cash"] + x["deposits"] + x["wealth_products"] - x["debt"] - x["xdc_payable"]
    xdc_net = x["xdc_cash"] + x["xdc_deposits"] + x["xdc_products"] - x["xdc_debt"] - x["xdc_payable"]
    minority_cash = xdc_net * x["xdc_outside_share"]
    surplus = net - minority_cash - x["cash_buffer"] - x["july_repurchase_hkd"] * x["fx"]
    nonoperating = x["portfolio_recovery"] * x["investment_portfolio"] - x["investment_commitment"] + x["bestchrom_common_recovery"]
    return surplus + nonoperating, minority_cash


def evaluate(start, opening, shares, fx, depreciation_rate, case):
    cash, sales = opening, start
    rows = []
    assert len(case["growth"]) == len(case["margin"]) == len(case["capex"])
    for growth, margin, capex in zip(case["growth"], case["margin"], case["capex"]):
        previous = sales
        sales *= 1 + growth
        profit = sales * margin
        working = max(case["working_capital_floor"], (sales - previous) * case["wc"])
        net_investment = capex - sales * depreciation_rate + working
        cash_flow = (profit - net_investment) * case["parent"]
        cash += cash_flow
        assert cash >= 0
        rows.append((sales, profit, net_investment, cash_flow))
    operating = rows[-1][1] * case["parent"] * case["multiple"]
    terminal = (cash + operating) / (shares * fx)
    discount = (1 + case["rate"]) ** len(rows)
    assert abs((terminal * fx * shares) - (opening + sum(r[3] for r in rows) + operating)) < 1e-8
    return dict(value=terminal / discount, terminal=terminal, cash=cash, rows=rows,
                operating_share=operating / (cash + operating))


def continuation_value(case, cash, last_group_profit, shares, fx):
    """独立的第6年至稳态经营现金折现；资本回报控制成长的资金消耗。"""
    rate = case["rate"]
    profit = last_group_profit * case["parent"]
    pv = 0.
    for year in range(1, data["transition_years"] + 1):
        profit *= 1 + case["transition_growth"]
        reinvested_fraction = case["transition_growth"] / case["transition_roic"]
        pv += profit * (1 - reinvested_fraction) / (1 + rate)**year
    g = case["perpetual_growth"]
    steady_cf = profit * (1 + g) * (1 - g / case["perpetual_roic"])
    pv += steady_cf / (rate - g) / (1 + rate)**data["transition_years"]
    return (pv + cash) / (1 + rate)**5 / (shares * fx)


def run():
    mini = dict(growth=[0], margin=[0.2], capex=[1], wc=0, working_capital_floor=0, parent=1, rate=0.1, multiple=10)
    # 收入10、税后利润2、折旧与购建均为1。结存2、经营终值20，以10%折现得20。
    assert abs(evaluate(10, 0, 1, 1, .1, mini)["value"] - 20) < 1e-9
    x = data
    opening, nci = equity_bridge(x)
    start = x["revenue_fy25"] - x["revenue_h125"] + x["revenue_h126"] - x["held_for_sale_revenue_budget"]
    shares = x["issued"] + sum(x["options"]) + sum(x["future_issue_awards"])
    args = (start, opening, shares, x["fx"], x["depreciation_to_sales"])
    scenarios, detail, check, end = {}, {}, {}, {}
    for name, case in x["cases"].items():
        r = evaluate(*args, case)
        scenarios[name] = round(r["value"], 2)
        rows = r["rows"]
        detail[name] = dict(year_1_and_5_revenue=[round(i[0], 3) for i in (rows[0], rows[-1])],
                            year_1_and_5_nopat=[round(i[1], 3) for i in (rows[0], rows[-1])],
                            year_2_to_5_net_investment=round(sum(i[2] for i in rows[1:]), 3),
                            year_5_retained_assets=round(r["cash"], 3),
                            year_5_operating_share=round(r["operating_share"], 3),
                            minimum_cash=round(min(opening + sum(i[3] for i in rows[:j]) for j in range(1, 6)), 3))
        if name.startswith("base"):
            check[name] = round(continuation_value(case, r["cash"], rows[-1][1], shares, x["fx"]), 2)
            end[name] = round(r["terminal"], 2)
    assert list(scenarios.values()) == sorted(scenarios.values())
    c = deepcopy(x["cases"]["base_low"])
    c["capex"] = [s * 1.20 for s in c["capex"]]
    stress_capex = evaluate(*args, c)["value"]
    c = deepcopy(x["cases"]["base_low"])
    c["margin"] = [s - .03 for s in c["margin"]]
    stress_margin = evaluate(*args, c)["value"]
    return dict(symbol=x["symbol"], report_period=x["report_period"],
                value_range=dict(low=scenarios["base_low"], high=scenarios["base_high"], currency="HKD"),
                return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                    model_as_of=x["as_of"], base_case_distributions_per_share=[0]*5,
                    base_case_terminal_equity_value_range_per_share=dict(year_5=dict(low=end["base_low"], high=end["base_high"]))),
                scenarios=scenarios, secondary_dcf=check, starting_common_assets_cny_bn=round(opening,3),
                xdc_minority_cash_cny_bn=round(nci,3), diluted_shares_bn=round(shares,6),
                matched_operating_inputs=detail, lower_case_capex_plus_20pct=round(stress_capex,2),
                lower_case_margin_minus_3pp=round(stress_margin,2))


if __name__ == "__main__":
    (ROOT / "2026-H1-output.json").write_text(json.dumps(run(), ensure_ascii=False, indent=2) + "\n")
