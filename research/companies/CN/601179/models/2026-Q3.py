"""使用 Python 3 在任意目录运行本文件。读取同目录输入，覆盖同目录简明结果。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def discounted(distributions, terminal, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(distributions, 1)) + terminal / (1 + rate) ** len(distributions)

def forecast(facts, case):
    shares = facts["shares"] - facts["treasury_shares"] + facts["new_dilutive_shares"]
    parent_fraction = facts["last_nine_month_parent_profit"] / facts["last_nine_month_consolidated_profit"]
    previous_sales = facts["last_nine_month_revenue"] + facts["previous_q4_revenue"]
    rows = []
    opening_book = facts["parent_book"]
    cumulative_profit = 0.0
    cumulative_paid = 0.0
    for growth, margin, buffer in zip(case["growth"], case["net_margin"], case["supplier_and_receivable_buffer"], strict=True):
        sales = previous_sales * (1 + growth)
        profit = sales * margin
        net_fixed = sales * case["net_capex_ratio"]
        working = max(sales - previous_sales, 0) * case["working_capital_per_increment"]
        investment = (net_fixed + working) * parent_fraction
        cash_capacity = profit - investment - buffer
        paid = min(profit * case["payout_ceiling"], max(cash_capacity, 0))
        reserve = cash_capacity - paid
        assert 0 <= paid <= max(cash_capacity, 0)
        closing_book = opening_book + investment + buffer + reserve
        cumulative_profit += profit
        cumulative_paid += paid
        assert abs(closing_book - (facts["parent_book"] + cumulative_profit - cumulative_paid)) < 1e-8
        opening_book = closing_book
        rows.append({"sales": sales, "profit": profit, "net_investment": investment, "cash_capacity": cash_capacity, "payout": paid / shares})
        previous_sales = sales
    distributions = [r["payout"] for r in rows]
    terminal = [rows[-1]["profit"] * pe / shares for pe in case["exit_pe"]]
    values = [discounted(distributions, t, case["discount_rate"]) for t in terminal]
    return rows, terminal, values

def main():
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    assert abs(discounted([1, 1], 10, 0.1) - 10) < 1e-10
    facts = data["facts"]
    runs = {key: forecast(facts, case) for key, case in data["case_parameters"].items()}
    base, terminal, values = runs["base"]
    low, high = [round(v, 2) for v in values]
    anchors = [round(runs["structural_bear"][2][0], 2), round(runs["cyclical_bear"][2][0], 2), low, high, round(runs["bull"][2][0], 2)]
    assert 0 <= anchors[0] and anchors == sorted(anchors)
    scenarios = dict(zip(["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"], anchors, strict=True))
    check = data["book_check"]
    shares = facts["shares"] - facts["treasury_shares"] + facts["new_dilutive_shares"]
    book_per_share = facts["parent_book"] / shares
    book_value = [book_per_share * (roe - check["growth"]) / (check["discount_rate"] - check["growth"]) for roe in check["normalized_roe"]]
    rate = data["case_parameters"]["base"]["discount_rate"]
    capital = sum(row["net_investment"] for row in base[1:])
    result = {
        "symbol": data["symbol"], "report_period": data["report_period"],
        "value_range": {"low": low, "high": high, "currency": "CNY"},
        "scenarios": {"currency": "CNY", **scenarios, "horizon_note": data["horizon_note"]},
        "return_model": {
            "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["as_of"],
            "base_case_distributions_per_share": [round(row["payout"], 5) for row in base],
            "base_case_terminal_equity_value_range_per_share": {"year_5": dict(zip(("low", "high"), [round(x, 5) for x in terminal], strict=True))}
        },
        "terminal_pv_proportion": [round(t / ((1 + rate) ** 5) / v, 4) for t, v in zip(terminal, values, strict=True)],
        "book_crosscheck_per_share": [round(v, 2) for v in book_value],
        "base": [{k: round(v, 4) for k, v in row.items()} for row in base],
        "incremental_parent_profit_y1_to_y5": round(base[-1]["profit"] - base[0]["profit"], 4),
        "modeled_net_operating_capital_added_y2_to_y5": round(capital, 4),
        "one_percentage_point_lower_final_margin_value_effect": [round(-base[-1]["sales"] * 0.01 * pe / shares / ((1 + rate) ** 5), 2) for pe in data["case_parameters"]["base"]["exit_pe"]]
    }
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

if __name__ == "__main__":
    main()
