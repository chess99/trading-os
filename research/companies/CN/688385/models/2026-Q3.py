"""复旦微电普通股终态矩阵与现金流校验。运行 python 2026-Q3.py。"""
import json
from pathlib import Path
from math import isclose

ROOT = Path(__file__).resolve().parent


def evaluate(revenue, shares, initial_cash, s):
    cash = initial_cash
    required_return = s["cost_equity"]
    pv_distributions = 0
    equity_cashflows = 0
    cumulative_investment = 0
    cumulative_earnings = 0
    for year, growth in enumerate(s["growth"], 1):
        prior_revenue = revenue
        revenue *= 1 + growth
        margin = s["margins"][0] + (s["margins"][1] - s["margins"][0]) * (year - 1) / 4
        profit = revenue * margin
        investment = max(0, revenue - prior_revenue) * (s["working_capital"] + s["net_fixed_dev"])
        investment += s["cash_stress"][year - 1]
        free_cash = profit - investment
        dividend = shares * s["dividend"]
        cash += free_cash - dividend
        cumulative_investment += investment
        cumulative_earnings += profit
        equity_cashflows += free_cash / (1 + required_return) ** year
        pv_distributions += dividend / (1 + required_return) ** year
        if year == 1:
            first_profit = profit
            first_investment = investment
    assert isclose(cash, initial_cash + cumulative_earnings - cumulative_investment - 5 * dividend, abs_tol=1e-8)
    terminal = profit * s["multiple"] + cash
    pv_terminal = terminal / (1 + required_return) ** 5
    primary = (pv_terminal + pv_distributions) / shares

    # 第二法假设各年剩余现金当年即可供普通股使用，免去对未来闲置现金的折价。
    mature_growth = s["perpetual_g"]
    assert mature_growth < required_return and mature_growth < s["mature_roic"]
    next_profit = profit
    for step in range(1, 6):
        growth = s["growth"][-1] + (mature_growth - s["growth"][-1]) * step / 5
        next_profit *= 1 + growth
        equity_cashflows += next_profit * (1 - growth / s["mature_roic"]) / (1 + required_return) ** (5 + step)
    continuing_cf = next_profit * (1 + mature_growth) * (1 - mature_growth / s["mature_roic"])
    second = (initial_cash + equity_cashflows + continuing_cf / (required_return - mature_growth) / (1 + required_return) ** 10) / shares
    delta_capital = cumulative_investment - first_investment
    return {
        "present_per_share": round(primary, 2), "year5_per_share": round(terminal / shares, 2),
        "secondary_per_share": round(second, 2), "year5_revenue": round(revenue, 2),
        "year5_core_profit": round(profit, 2), "year5_excess_cash": round(cash, 2),
        "five_year_investment": round(cumulative_investment, 2),
        "year1_to_5_incremental_profit": round(profit - first_profit, 2),
        "year1_to_5_incremental_capital": round(delta_capital, 2),
        "terminal_pv_fraction": round(pv_terminal / (pv_terminal + pv_distributions), 4),
    }


def main():
    inp = json.loads((ROOT / "2026-Q3-input.json").read_text())
    f, b = inp["financials"], inp["bridge_assumptions"]
    sales = f["fy2025_revenue"] + f["nine_months_2026_revenue"] - f["nine_months_2025_revenue"]
    shares = f["issued_shares"] + f["first_grant"] + f["reserve"]
    debt = sum(f[k] for k in ("short_debt", "due_in_one_year", "long_debt", "long_leases"))
    opening = f["cash"] + f["trading_assets"] * b["treasury_asset_realization"] - debt - b["cash_risk_reserve"]
    paths = inp["scenarios"]
    # 收入10，利润率10%，1股，零增长，每年利润全部派发；10%折现率和10倍终值给出10元现值。
    toy = dict(paths["base_low"], growth=[0]*5, margins=[0.1, 0.1], dividend=1, cost_equity=.1, multiple=10, perpetual_g=0)
    test = evaluate(10, 1, 0, toy)
    assert test["present_per_share"] == test["secondary_per_share"] == test["year5_per_share"] == 10
    detail = {name: evaluate(sales, shares, opening, s) for name, s in paths.items()}
    anchor = {k: v["present_per_share"] for k, v in detail.items()}
    assert list(anchor.values()) == sorted(anchor.values()) and min(anchor.values()) >= 0
    low, high = detail["base_low"], detail["base_high"]
    model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": inp["cutoff"],
             "base_case_distributions_per_share": [paths["base_low"]["dividend"]] * 5,
             "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low["year5_per_share"], "high": high["year5_per_share"]}}}
    out = {"symbol": inp["symbol"], "report_period": inp["report_period"],
           "value_range": {"low": anchor["base_low"], "high": anchor["base_high"], "currency": "CNY"},
           "scenarios": {"currency": "CNY", **anchor, "horizon_note": "同一稀释股数、留存现金与人民币口径。第五年持续经营估值和剩余现金随客户需求、利润率及资本占用联动。"},
           "return_model": model, "initial_bridge": {"revenue_ltm": round(sales, 2), "diluted_shares": shares, "debt_and_leases": round(debt, 2), "opening_surplus": round(opening, 2)},
           "detail": detail}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
