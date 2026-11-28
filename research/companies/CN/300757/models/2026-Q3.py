"""在本文件所在目录运行 python 2026-Q3.py，读取同名周期输入并生成简明结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCALE = 100_000_000


def opening_bridge(capital):
    outstanding = capital["issued"] - capital["repurchased_pending_cancellation"]
    debt = sum(capital[k] for k in ("short_debt", "long_debt", "due_current", "leases"))
    available = (capital["cash_equivalents"] + capital["extra_issue_net_hkd"] * capital["cny_per_hkd_budget"]
                 + capital["short_term_investments"] - capital["repurchase_cost"] - debt
                 - capital["customer_advances"] - capital["operating_cash_buffer"])
    return outstanding, debt, available


def value_case(case, opening_cash, shares, last_sales):
    terminal_sales = case["market"] * case["share"] + case["other_sales"]
    retained_cash = opening_cash - case["capital_loss"]
    total_investment = 0
    for t, net_capex in enumerate(case["net_capex"]):
        weight = t / 4
        sales = (1 - weight) * case["y1_sales"] + weight * terminal_sales
        margin = (1 - weight) * case["start_margin"] + weight * case["end_margin"]
        profit = sales * margin
        # 历史预收款在期初剔除。增量营运资金只预算新增销售的净占款。
        investment = net_capex + max(0, sales - last_sales) * case["working_capital_ratio"]
        retained_cash += profit - investment
        total_investment += investment
        last_sales = sales
        assert retained_cash >= 0, "须增加融资或压减投资预算"
    business = profit * case["exit_multiple"]
    future_equity = (business + retained_cash) * SCALE / shares
    discount = (1 + case["rate"]) ** 5
    current = future_equity / discount
    # 方法二使用持续投资回报与永续增长决定可抽取的经营现金比例。
    growth = case["perpetual_growth"]
    next_cash = profit * (1 + growth) * (1 - growth / case["steady_roic"])
    stable_value = next_cash / (case["rate"] - growth)
    crosscheck = (stable_value + retained_cash) * SCALE / shares / discount
    assert isclose(current * discount * shares / SCALE, business + retained_cash)
    return {"current": round(current, 2), "terminal_equity": round(future_equity, 2),
            "terminal_sales": round(terminal_sales, 2), "terminal_nopat": round(profit, 3),
            "five_year_net_investment": round(total_investment, 2), "terminal_cash": round(retained_cash, 2),
            "ending_business_weight": round(business / (business + retained_cash), 3),
            "steady_cashflow_crosscheck": round(crosscheck, 2)}


def main():
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    capital = data["capital"]
    shares, debt, cash = opening_bridge(capital)
    # 手算：每年利润1亿元、资本投入为零，第五年经营价值10亿元及留存5亿元。
    example = dict(y1_sales=10, market=10, share=1, other_sales=0, start_margin=0.1, end_margin=0.1,
                   net_capex=[0]*5, working_capital_ratio=0, capital_loss=0, exit_multiple=10,
                   rate=0.1, perpetual_growth=0, steady_roic=0.1)
    assert value_case(example, 0, SCALE, 10)["current"] == round(15 / 1.1**5, 2)
    cases = {name: value_case(case, cash, shares, capital["reference_annual_revenue"])
             for name, case in data["cases"].items()}
    anchors = {name: result["current"] for name, result in cases.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
             "model_as_of": data["as_of"], "base_case_distributions_per_share": [0.0]*5,
             "base_case_terminal_equity_value_range_per_share": {"year_5": {
                 "low": cases["base_low"]["terminal_equity"], "high": cases["base_high"]["terminal_equity"]}}}
    output = {"symbol": data["symbol"], "report_period": data["report_period"],
              "value_range": {"currency": "CNY", "low": anchors["base_low"], "high": anchors["base_high"]},
              "return_model": model, "scenarios": anchors,
              "bridge": {"shares": shares, "debt_100m": round(debt, 3), "opening_cash_100m": round(cash, 3)},
              "cases": cases}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
