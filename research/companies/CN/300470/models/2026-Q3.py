"""中密控股三季报。直接运行本文件，读取同目录输入并生成简明结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def forecast(revenue, shares, opening_cash, legal_capacity, parent_access, case):
    cash = opening_cash
    flows, profits, capital, distributions = [], [], [], []
    for year, growth in enumerate(case["growth"]):
        increment = revenue * growth
        revenue += increment
        profit = revenue * case["margin"][year]
        # 销售萎缩时，专用存货和应收款不假定可以按比例变现。
        working_capital = max(0, increment) * case["wc_intensity"] + case["extra_wc"][year]
        fixed_capital = max(max(0, increment) * case["fixed_intensity"], case["net_build"][year])
        investment = working_capital + fixed_capital
        available = profit - investment
        legal_capacity += profit * parent_access
        dividend = min(profit * case["payout"], cash + available, legal_capacity)
        assert dividend >= 0
        legal_capacity -= dividend
        cash += available - dividend
        profits.append(profit)
        flows.append(available)
        capital.append(investment)
        distributions.append(dividend / shares)
    assert isclose(cash, opening_cash + sum(flows) - sum(distributions) * shares)
    return dict(cash=cash, profits=profits, capital=capital, distributions=distributions, flows=flows)


def present_value(dividends, terminal, discount):
    return sum(d / (1 + discount)**t for t, d in enumerate(dividends, 1)) + terminal / (1 + discount)**len(dividends)


def evaluate(revenue, shares, cash, legal, access, case):
    flow = forecast(revenue, shares, cash, legal, access, case)
    g, rate, roic = (case[k] for k in ("terminal_growth", "discount", "terminal_roic"))
    assert rate > g and 0 <= g < roic
    last_profit = flow["profits"][-1]
    terminal_cash_flow = last_profit * (1 + g) * (1 - g / roic)
    terminal = (terminal_cash_flow / (rate - g) + flow["cash"]) / shares
    value = present_value(flow["distributions"], terminal, rate)
    return flow | dict(terminal=terminal, value=value, terminal_weight=terminal / (1 + rate)**5 / value)


def calculate(inputs):
    f, b = inputs["facts"], inputs["bridge_assumptions"]
    revenue = f["fy25_revenue"] + f["nine_month_26_revenue"] - f["nine_month_25_revenue"]
    shares = f["shares_sep"] - f["shares_cancelled"]
    assert 0 <= b["estimated_other_current_investments"] <= f["other_current_assets_total"]
    cash = (f["cash_equivalents"] + f["trading_assets"] + b["estimated_other_current_investments"]
            - f["dividend_already_paid"] - f["cash_for_cancellation"] - f["leases"]
            - f["fund_commitment"] + f["fund_called"]
            - b["operating_and_remittance_reserve"] - b["minority_cash_reserve"])
    legal = f["h1_parent_distributable"] - f["dividend_already_paid"]
    results = {k: evaluate(revenue, shares, cash, legal, inputs["parent_profit_access"], case)
               for k, case in inputs["cases"].items()}
    anchors = {k: round(r["value"], 2) for k, r in results.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    low, high = results["base_low"], results["base_high"]
    assert low["distributions"] == high["distributions"]
    terminal_pair = dict(low=round(low["terminal"], 4), high=round(high["terminal"], 4))
    check_values = []
    for case, multiple in zip(("base_low", "base_high"), inputs["base_terminal_multiple"]):
        flow = results[case]
        secondary_terminal = (flow["profits"][-1] * multiple + flow["cash"]) / shares
        check_values.append(round(present_value(flow["distributions"], secondary_terminal, inputs["cases"][case]["discount"]), 2))
    return {
        "symbol": inputs["symbol"], "report_period": inputs["report_period"],
        "value_range": dict(low=anchors["base_low"], high=anchors["base_high"], currency="CNY"),
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1",
                         "model_as_of": inputs["as_of"], "currency": "CNY",
                         "base_case_distributions_per_share": [round(d, 4) for d in low["distributions"]],
                         "base_case_terminal_equity_value_range_per_share": {"year_5": terminal_pair}},
        "anchors": anchors, "secondary_range": check_values,
        "shares_m": round(shares, 6), "opening_cash_m": round(cash, 3),
        "base_annual_distributable_cash_m": [round(x, 2) for x in low["flows"]],
        "base_investment_m": [round(x, 2) for x in low["capital"]],
        "base_profit_m": [round(x, 2) for x in low["profits"]],
        "base_y5_residual_cash_m": round(low["cash"], 2),
        "base_incremental_return_y1_to_y5": round((low["profits"][-1] - low["profits"][0]) / sum(low["capital"][1:]), 4),
        "terminal_pv_shares": [round(r["terminal_weight"], 4) for r in (low, high)],
    }


if __name__ == "__main__":
    # 每年赚10并全额派发，股数10、无增长、折现10%，终值及今日价值均为10元。
    flat = dict(growth=[0]*5, margin=[0.1]*5, wc_intensity=0, fixed_intensity=0,
                extra_wc=[0]*5, net_build=[0]*5, payout=1, discount=0.1, terminal_growth=0, terminal_roic=0.1)
    check = evaluate(100, 10, 0, 0, 1, flat)
    assert check["distributions"] == [1]*5 and isclose(check["terminal"], 10) and isclose(check["value"], 10)
    inputs = json.loads((ROOT / "2026-Q3-input.json").read_text())
    output = calculate(inputs)
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
