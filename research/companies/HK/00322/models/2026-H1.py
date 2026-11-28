"""康师傅股息折现。运行 python 2026-H1.py，在本目录重生成输出。"""
import json
from pathlib import Path
from math import isclose
from statistics import mean

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "2026-H1-input.json").read_text())


def year_cash(revenue, growth, margin, turnover, extra_capex):
    sales = revenue * (1 + growth)
    profit = sales * margin
    capacity_and_working_capital = max(0, sales - revenue) / turnover
    modernization = sales * extra_capex
    dividend = profit - capacity_and_working_capital - modernization
    assert dividend >= 0
    assert isclose(dividend + capacity_and_working_capital + modernization, profit)
    return sales, profit, dividend, capacity_and_working_capital


def present_value(distributions, terminal, discount):
    return sum(dividend / (1 + discount) ** year for year, dividend in enumerate(distributions, 1)) + terminal / (1 + discount) ** len(distributions)


def scenario(start_sales, units, p):
    sales = start_sales
    dividends, profit_path, incremental_capital = [], [], []
    for growth, margin in zip(p["sales_growth"], p["common_margin"], strict=True):
        sales, profit, dividend, capital = year_cash(sales, growth, margin, p["turnover"], p["extra_capex"])
        dividends.append(dividend / units)
        profit_path.append(profit)
        incremental_capital.append(capital)
    growth = p["terminal_growth"]
    discount = p["discount"]
    assert discount > growth
    _, _, next_dividend, _ = year_cash(sales, growth, p["common_margin"][-1], p["turnover"], p["extra_capex"])
    terminal = next_dividend / units / (discount - growth)
    value = present_value(dividends, terminal, discount)
    return dict(value=value, distributions=dividends, terminal=terminal, terminal_pv_ratio=terminal / (1 + discount)**5 / value,
                common_profit=profit_path, incremental_capital_y2_y5=sum(incremental_capital[1:]))


def run(data):
    assert isclose(present_value([1]*5, 10, 0.1), 10)
    assert isclose(year_cash(10, 0.1, 0.2, 2, 0)[2], 1.7)
    obs = data["observed"]
    assert isclose(obs["h1_common_profit"] + obs["h1_minority_profit"], obs["h1_group_profit"])
    diluted = obs["issued_shares_oct"] + sum(obs["outstanding_options"])
    assert obs["treasury_shares"] == 0
    units = diluted * data["cny_per_hkd"]
    sales = obs["annual_revenue"] + obs["h1_revenue"] - obs["prior_h1_revenue"]
    params = data["assumptions"]
    names = ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")
    cases = {name: scenario(sales, units, params[name]) for name in names}
    anchors = {name: round(case["value"], 2) for name, case in cases.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    base, high = cases["base_low"], cases["base_high"]
    assert base["distributions"] == high["distributions"]
    f = data["historic_cashflow"]
    historical = [f["cfo"][i] - f["equipment"][i] - f["land"][i] - f["leases"][i] - f["minority_dividends"][i]
                  + f["joint_dividends"][i] + f["associate_dividends"][i] + f["normalized_interest"] for i in range(2)]
    cash_method = [round(mean(historical) / rate / units, 2) for rate in f["capitalization_yields"]]
    stress = dict(params["base_low"])
    stress["common_margin"] = [m - 0.005 for m in stress["common_margin"]]
    return {
        "symbol": data["symbol"], "report_period": data["report_period"], "scenarios": anchors,
        "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "HKD"},
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD", "model_as_of": data["as_of"],
                         "base_case_distributions_per_share": [round(d, 4) for d in base["distributions"]],
                         "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(base["terminal"], 4), "high": round(high["terminal"], 4)}}},
        "terminal_pv_share": [round(case["terminal_pv_ratio"], 4) for case in [base, high]],
        "common_profit_y1_y5": [round(base["common_profit"][i], 4) for i in [0, -1]],
        "growth_capital_y2_y5": round(base["incremental_capital_y2_y5"], 4),
        "equity_bridge": {"diluted_billion_shares": diluted, "historical_net_cash_before_july_distribution": round(obs["cash_including_term_deposits"] - obs["borrowings"], 4),
                          "additive_cash_value": 0},
        "cashflow_cross_check": {"annual_cash_after_investment_and_minorities": [round(c, 4) for c in historical], "range_hkd": cash_method},
        "base_low_less_50bp_common_margin": round(scenario(sales, units, stress)["value"], 2)
    }


if __name__ == "__main__":
    result = run(DATA)
    (ROOT / "2026-H1-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
