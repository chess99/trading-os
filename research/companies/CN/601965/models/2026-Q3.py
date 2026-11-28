"""运行 python 2026-Q3.py，按同目录输入生成普通股现金、四情景及净资产检验。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def project(sales, profit, path):
    margin_start = profit / sales
    free_balance = 0.0
    years = []
    for index, growth in enumerate(path["sales_growth"]):
        next_sales = sales * (1 + growth)
        margin = margin_start + (path["end_margin"] - margin_start) * (index + 1) / 5
        earnings = next_sales * margin
        # 萎缩时不假定专用设备可变现，增长资本预算已扣常态折旧。
        capital = max(0, next_sales - sales) * path["growth_equity_per_sales"]
        capital += path["additional_build"][index]
        available = free_balance + earnings - capital
        assert available >= 0, "需要另行建立融资安排"
        distribution = min(earnings * path["payout"], available)
        free_balance = available - distribution
        years.append((earnings, capital, distribution, free_balance))
        sales = next_sales
    assert isclose(sum(e - c - d for e, c, d, _ in years), free_balance, abs_tol=1e-8)
    return years


def present(years, rate, growth, marginal_return, shares):
    assert rate > growth and marginal_return > growth
    next_earnings = years[-1][0] * (1 + growth)
    ongoing = next_earnings * (1 - growth / marginal_return) / (rate - growth)
    terminal = (ongoing + years[-1][3]) / shares
    terminal_pv = terminal / (1 + rate) ** 5
    payout_pv = sum(row[2] / shares / (1 + rate) ** i for i, row in enumerate(years, 1))
    total = payout_pv + terminal_pv
    return total, terminal, terminal_pv / total


def book_check(years, book, rate, growth, sustainable_roe, shares):
    # 清洁盈余桥。终态ROE作用于包括累计留存的完整归母净资产。
    present_payouts = 0
    for i, (earnings, _, payout, _) in enumerate(years, 1):
        book += earnings - payout
        present_payouts += payout / (1 + rate) ** i
    justified_pb = (sustainable_roe - growth) / (rate - growth)
    return (present_payouts + book * justified_pb / (1 + rate) ** 5) / shares


def main():
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    f = data["facts"]
    shares = f["common_shares"]
    assert isclose(f["group_book"], f["common_book"] + f["minority_book"], abs_tol=1e-7)
    assert isclose(f["group_net_income_9m"], f["common_net_income_9m"] + f["minority_net_income_9m"])
    # 手算：收入10，净利1，无增长、全分配，股本1；10%折现永续值为10。
    flat = {"sales_growth": [0] * 5, "end_margin": 0.1, "payout": 1,
            "growth_equity_per_sales": 0, "additional_build": [0] * 5}
    assert isclose(present(project(10, 1, flat), 0.10, 0, 0.15, 1)[0], 10)

    paths = data["scenarios"]
    sales = f["q4_2025_revenue"] + f["nine_month_revenue"]
    profit = f["q4_2025_core_common_profit"] + f["nine_month_core_common_profit"]
    projections = {name: project(sales, profit, case) for name, case in paths.items()}
    low_r, high_r = data["base_discount_low"], data["base_discount_high"]
    results = {}
    for label, name, rate in (
        ("structural_bear", "structural_bear", paths["structural_bear"]["r"]),
        ("cyclical_bear", "cyclical_bear", paths["cyclical_bear"]["r"]),
        ("base_low", "base", high_r), ("base_high", "base", low_r),
        ("bull", "bull", paths["bull"]["r"])
    ):
        case = paths[name]
        results[label] = present(projections[name], rate, case["steady_g"], case["steady_roic"], shares)
    anchors = {k: round(v[0], 2) for k, v in results.items()}
    assert sorted(anchors.values()) == list(anchors.values()) and min(anchors.values()) >= 0
    years = projections["base"]
    payout = [round(row[2] / shares, 4) for row in years]
    assert payout[0] >= f["announced_interim_dps"] and years[0][2] < f["parent_undistributed"]
    cross = data["book_crosscheck"]
    book_range = [book_check(years, f["common_book"], rate, cross["g"], cross[roe], shares)
                  for rate, roe in ((high_r, "terminal_roe_low"), (low_r, "terminal_roe_high"))]
    output = {
        "symbol": data["symbol"], "report_period": data["report_period"],
        "value_range": {"currency": "CNY", "low": anchors["base_low"], "high": anchors["base_high"]},
        "scenarios": anchors,
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1",
                         "currency": "CNY", "model_as_of": data["as_of"],
                         "base_case_distributions_per_share": payout,
                         "base_case_terminal_equity_value_range_per_share": {"year_5": {
                             "low": round(results["base_low"][1], 4),
                             "high": round(results["base_high"][1], 4)}}},
        "base_common_earnings_100m": [round(y[0], 3) for y in years],
        "base_reinvestment_100m": [round(y[1], 3) for y in years],
        "base_end_retained_cash_100m": round(years[-1][3], 3),
        "terminal_pv_share": [round(results[k][2], 4) for k in ("base_low", "base_high")],
        "incremental_return_year_1_to_5": round((years[-1][0]-years[0][0])/sum(y[1] for y in years[1:]), 4),
        "book_crosscheck_value": [round(v, 2) for v in book_range]
    }
    (HERE / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
