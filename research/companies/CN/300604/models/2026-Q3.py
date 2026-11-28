"""以本模型及同目录输入离线运行，输出普通股折现价值。金额以亿元计。"""
import json
from pathlib import Path
from math import isclose

root = Path(__file__).resolve().parent
inputs = json.loads((root / "2026-Q3-input.json").read_text())
b = inputs["basis"]


def ordinary_value(free_cash, terminal_operations, opening_bridge, shares, discount):
    periods = len(free_cash)
    present_operations = terminal_operations / (1 + discount)**periods
    present_flows = sum(cash / (1 + discount)**year for year, cash in enumerate(free_cash, 1))
    return (opening_bridge + present_operations + present_flows) / shares, present_operations


def transition_value(profit, case):
    """第6至10年持续再投资，随后按稳态资本回报、增速和资本成本计价。"""
    flows = []
    for year in range(5):
        growth = case["g6"] + year * (case["g10"] - case["g6"]) / 4
        reinvest = profit * growth / case["roic"]
        profit *= 1 + growth
        flows.append(profit - reinvest)
    steady_cash = profit * (1 + case["gt"]) * (1 - case["gt"] / case["roic"])
    terminal = steady_cash / (case["discount"] - case["gt"])
    return ordinary_value(flows, terminal, 0, 1, case["discount"])[0]


def evaluate(case):
    starting_sales = b["sales_9m26"] + b["sales_fy25"] - b["sales_9m25"]
    sales = starting_sales
    first_sales = sales * (1 + case["first_growth"])
    growth_after_y1 = (sum(case["y5_product_sales"]) / first_sales)**0.25 - 1
    free_cash, investment, profits = [], [], []
    for year in range(5):
        prior_sales = sales
        sales *= 1 + (case["first_growth"] if year == 0 else growth_after_y1)
        margin = case["margin1"] + year * (case["margin5"] - case["margin1"]) / 4
        earnings = sales * margin * (1 - b["tax"])
        # 验收延期时未收回的营运资本保持占用，缩量不自动释放现金。
        invested = max(0, sales - prior_sales) * case["wc"] + sales * case["fixed"]
        investment.append(invested)
        profits.append(earnings)
        free_cash.append(earnings - invested)
        assert isclose(earnings, free_cash[-1] + invested)
    assert isclose(sales, sum(case["y5_product_sales"]))
    primary, pv_terminal = ordinary_value(free_cash, profits[-1] * case["multiple"], bridge, shares, case["discount"])
    secondary, _ = ordinary_value(free_cash, transition_value(profits[-1], case), bridge, shares, case["discount"])
    return {
        "today": round(primary, 2), "cashflow_check": round(secondary, 2),
        "year5_operating_terminal_per_share": round(profits[-1] * case["multiple"] / shares, 2),
        "year5_nopat": round(profits[-1], 2), "terminal_pv_share": round(pv_terminal / (primary * shares), 4),
        "year1_to_5_incremental_nopat": round(profits[-1] - profits[0], 2),
        "year1_end_to_5_end_investment": round(sum(investment[1:]), 2),
        "five_year_required_investment": round(sum(investment), 2),
        "five_year_cash_after_reinvestment": round(sum(free_cash), 2)
    }


assert isclose(ordinary_value([1], 11, 0, 2, 0.2)[0], 5)
debt = sum(b[k] for k in ("short_debt", "debt_due", "long_debt", "lease_noncurrent"))
bridge = b["cash_equivalents"] - b["operating_cash"] - debt - b["minority_claim"] - b["post_dividend"] - b["first_repurchase"]
shares = b["registered_shares"] + (b["opening_awards_millions"] - b["registered_awards_oct_millions"]) / 100
results = {name: evaluate(case) for name, case in inputs["scenarios"].items()}
anchors = {name: v["today"] for name, v in results.items()}
assert list(anchors.values()) == sorted(anchors.values()) and min(anchors.values()) >= 0
low = inputs["scenarios"]["base_low"]
sensitivities = {
    "base_low_margin5_minus_2pp": evaluate(low | {"margin5": low["margin5"] - 0.02})["today"],
    "base_low_multiple_minus_2": evaluate(low | {"multiple": low["multiple"] - 2})["today"]
}
output = {
    "symbol": "CN:300604", "report_period": "2026-Q3",
    "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency":"CNY"},
    "return_model": None, "scenarios": anchors, "diluted_shares_yi": round(shares, 6),
    "ordinary_equity_bridge_yi": round(bridge, 3), "interest_bearing_debt_yi": round(debt, 3),
    "low_endpoint_sensitivity": sensitivities, "operating_forecast": results
}
(root / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
