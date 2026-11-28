"""运行 python 2026-H1.py，读取同目录输入，输出同目录估值结果。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def terminal_value(nopat, renewal, cash, investment, growth, roic, discount, recovery):
    assert 0 <= growth < min(roic, discount)
    year_six_cash = (nopat * (1 - growth / roic) - renewal) * (1 + growth)
    return year_six_cash / (discount - growth) + (cash + investment) * recovery


def value_path(facts, policy, case):
    shares_in_hkd = facts["shares"] * facts["cny_per_hkd"]
    start_sales = facts["fy25_revenue"] - facts["h1_25_revenue"] + facts["h1_26_revenue"]
    opening = (facts["bank_cash_ex_interest"] - facts["restricted_cash"] + facts["financial_assets"]
               - facts["debt_including_leases"] - facts["july_dividend"] - policy["liquidity_reserve"])
    reserve = facts["fy25_parent_distributable"] - facts["july_dividend"]
    remittable = min(reserve, opening * policy["remittable_opening_share"])
    sales, cash = start_sales, opening
    distributions, trace = [], []
    for growth, margin in zip(case["growth"], case["ebit_margin"], strict=True):
        new_sales = sales * (1 + growth)
        nopat = new_sales * margin * (1 - policy["tax"])
        renewal = new_sales * case["extra_renewal"]
        # 销售下跌时保留厂线及铺货能力，不假设按比例自动变现。
        expansion = max(0, new_sales - sales) * case["growth_capital"]
        profit = nopat + cash * policy["after_tax_financial_yield"]
        free_cash = profit - renewal - expansion
        new_reserve = reserve + max(0, free_cash) * case["upstream"]
        available_for_remittance = remittable + max(0, free_cash) * case["upstream"]
        dividend = min(profit * case["payout"], cash + free_cash, new_reserve, available_for_remittance)
        remittable = available_for_remittance - dividend
        ending_cash = cash + free_cash - dividend
        assert isclose(ending_cash + dividend + expansion + renewal, cash + profit)
        assert min(ending_cash, new_reserve - dividend, dividend) >= 0
        distributions.append(dividend / shares_in_hkd)
        trace.append((nopat, expansion, new_sales))
        sales, cash, reserve = new_sales, ending_cash, new_reserve - dividend

    discount = case["discount"]
    terminal = terminal_value(nopat, renewal, cash, facts["associates_book"], case["terminal_growth"],
                              case["terminal_roic"], discount, case["cash_recovery"]) / shares_in_hkd
    terminal_pv = terminal / (1 + discount) ** len(distributions)
    pv = sum(value / (1 + discount) ** i for i, value in enumerate(distributions, 1)) + terminal_pv
    paired_capital = sum(row[1] for row in trace[1:])
    return dict(value=pv, terminal=terminal, terminal_weight=terminal_pv / pv, dividends=distributions,
                opening_cash=opening, ending_cash=cash, nopat_first=trace[0][0], nopat_last=nopat,
                incremental_capital_y1_to_y5=paired_capital, initial_sales=start_sales,
                remittable_after_five_years=remittable, legal_reserve_after_five_years=reserve)


def calculate(data):
    facts, policy = data["facts"], data["policy"]
    cases = dict(data["cases"])
    cases.update({key: {**cases["base"], **changes} for key, changes in data["core_endpoints"].items()})
    paths = {name: value_path(facts, policy, case) for name, case in cases.items()}
    order = ["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"]
    values = [round(paths[name]["value"], 2) for name in order]
    assert values == sorted(values) and min(values) >= 0
    low, high = values[2:4]
    base = paths["base"]
    crosscheck = [(base["nopat_first"] * multiple
                   + cases["base"]["cash_recovery"] * (base["opening_cash"] + facts["associates_book"]))
                  / (facts["shares"] * facts["cny_per_hkd"]) for multiple in policy["earning_multiple_range"]]
    sensitivity = value_path(facts, policy, {**cases["base"], "ebit_margin": [m - 0.01 for m in cases["base"]["ebit_margin"]]})
    return {
        "symbol": data["symbol"], "report_period": data["period"],
        "value_range": {"currency": "HKD", "low": low, "high": high},
        "scenarios": {"currency": "HKD", **dict(zip(order, values))},
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1",
                         "currency": "HKD", "model_as_of": data["as_of"],
                         "base_case_distributions_per_share": [round(v, 4) for v in base["dividends"]],
                         "base_case_terminal_equity_value_range_per_share": {"year_5": {
                             key: round(paths["base_" + key]["terminal"], 4) for key in ("low", "high")}}},
        "crosscheck_hkd": [round(v, 2) for v in crosscheck],
        "margin_minus_one_point_hkd": round(sensitivity["value"], 2),
        "base_bridge_cny_m": {k: round(v, 2) for k, v in base.items() if k not in ("dividends", "value", "terminal", "terminal_weight")},
        "base_value_hkd": round(base["value"], 2),
        "terminal_pv_share": [round(paths[k]["terminal_weight"], 4) for k in ("base_low", "base_high")]
    }


if __name__ == "__main__":
    # 无增长的100元持续现金按10%资本化，外加50元富余现金。
    assert isclose(terminal_value(100, 0, 50, 0, 0, 0.2, 0.1, 1), 1050)
    data = json.loads((HERE / "2026-H1-input.json").read_text())
    result = calculate(data)
    (HERE / "2026-H1-output.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
