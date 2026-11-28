"""在任意目录执行本文件。模型仅使用同目录输入，生成同目录结果。"""
import json
from math import isclose
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent


def value_per_share(distributions, terminal, discount):
    return sum(cash / (1 + discount) ** year for year, cash in enumerate(distributions, 1)) + terminal / (1 + discount) ** len(distributions)


def forecast(data, case, convert, perpetuity=False):
    assets = data["cash"] + data["securities"] - data["cash_consideration_after_first"]
    available = assets - data["operating_cash_floor"] - data["lease_liabilities"]
    associate = data["associate_book"] * data["associate_share_of_book_value"]
    previous_sales = data["opening_sales"]
    starting_shares = shares = data["basic_shares"]
    capital_y1_to_y5 = 0
    project_total = data["project_budget"] - data["project_spent"]
    extra_projects = 0
    for year, (sales, margin, dividend) in enumerate(zip(case["sales"], case["margins"], case["dps"]), 1):
        earnings = sales * margin
        # 下行时不靠存货与固定产能按原价变现支持分红。
        sales_added = max(sales - previous_sales, 0)
        working = sales_added * case["working_capital"]
        fixed = sales_added * case["growth_capital"]
        project_credit = data["project_eligible_share"] * (sales * (data["recurring_rd_sales"] + data["maintenance_capex_sales"]) + fixed)
        additional = max(project_total * data["project_year_weights"][year - 1] - project_credit, 0)
        extra_projects += additional
        if year > 1:
            capital_y1_to_y5 += working + fixed + additional
        opening = available
        available += available * data["cash_return_after_tax"] + earnings - working - fixed - additional - dividend * shares
        if year <= 4:
            available -= data["bond_face"] * data["bond_coupon"]
        if year == 4:
            if convert:
                adjusted_price = data["bond_price"] - sum(case["dps"][:4])
                shares += data["bond_face"] / adjusted_price
            else:
                available -= data["bond_face"]
        assert available >= 0 and starting_shares <= shares
        if year == 5:
            assert isclose(available + dividend * shares, opening * (1 + data["cash_return_after_tax"]) + earnings - working - fixed - additional)
        previous_sales = sales
    if perpetuity:
        multiple = (1 + case["g"]) * (1 - case["g"] / case["roic"]) / (case["discount"] - case["g"])
    else:
        multiple = case["earnings_multiple"]
    terminal = (earnings * multiple + available + associate) / shares
    value = value_per_share(case["dps"], terminal, case["discount"])
    return {
        "current": round(value, 2), "terminal": round(terminal, 2),
        "settlement": "转股" if convert else "偿还本金", "shares_m": round(shares, 4),
        "year5_earnings_m": round(earnings, 2), "year5_cash_m": round(available, 2),
        "additional_project_expense_m": round(extra_projects, 2),
        "y1_to_y5_new_capital_m": round(capital_y1_to_y5, 2),
        "terminal_pv_share": round(terminal / (1 + case["discount"]) ** 5 / value, 4)
    }


def calculate(data):
    assert value_per_share([1, 1, 1, 1, 1], 10, 0) == 15
    assert isclose(value_per_share([1], 10, 0.1), 10)
    primary, secondary = {}, {}
    for name, case in data["cases"].items():
        for target, perpetuity in ((primary, False), (secondary, True)):
            paths = [forecast(data, case, conversion, perpetuity) for conversion in (False, True)]
            target[name] = min(paths, key=lambda result: result["current"])
    anchors = {name: row["current"] for name, row in primary.items()}
    assert list(anchors.values()) == sorted(anchors.values()) and anchors["structural_bear"] >= 0
    for endpoint in ("base_low", "base_high"):
        case = data["cases"][endpoint]
        assert abs(value_per_share(case["dps"], primary[endpoint]["terminal"], case["discount"]) - anchors[endpoint]) < 0.01
    return {
        "symbol": data["symbol"], "report_period": data["report_period"],
        "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "CNY"},
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
            "model_as_of": data["as_of"], "base_case_distributions_per_share": data["cases"]["base_low"]["dps"],
            "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": primary["base_low"]["terminal"], "high": primary["base_high"]["terminal"]}}},
        "scenarios": {"currency": "CNY", **anchors, "horizon_note": data["horizon_note"]},
        "base_share_count_m": data["basic_shares"], "diluted_at_current_terms_m": round(data["basic_shares"] + data["bond_face"] / data["bond_price"], 4),
        "primary_paths": primary, "perpetuity_check": secondary
    }


if __name__ == "__main__":
    source = json.loads((DIRECTORY / "2026-Q3-input.json").read_text())
    result = calculate(source)
    (DIRECTORY / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
