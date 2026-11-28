"""北矿检测普通股现金回报，金额与股数分别使用百万元和百万股。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def value(distributions, terminal, rate):
    dividends_pv = sum(d / (1 + rate) ** t for t, d in enumerate(distributions, 1))
    terminal_pv = terminal / (1 + rate) ** len(distributions)
    return dividends_pv + terminal_pv, terminal_pv


def steady_business(profit, growth, roic, rate):
    assert rate > growth and 0 <= growth < roic
    next_profit = profit * (1 + growth)
    return next_profit * (1 - growth / roic) / (rate - growth)


def forecast(data, case, rate):
    shares = data["shares"]
    excess = data["cash_and_deposits"] + data["noncurrent_deposit_estimate"] - data["operating_cash_floor"]
    legal = data["opening_legal_profit"]
    revenue = data["sales_ttm"]
    records = []
    assert len(case["sales_growth"]) == len(case["owner_margins"]) == len(case["net_project_spend"]) == 5
    for year, (growth, margin, project) in enumerate(zip(
        case["sales_growth"], case["owner_margins"], case["net_project_spend"]
    ), 1):
        previous_revenue, beginning_cash = revenue, excess
        revenue *= 1 + growth
        operating_profit = revenue * margin
        finance_income = beginning_cash * data["after_tax_deposit_yield"]
        profit = operating_profit + finance_income
        legal += profit * (1 - data["reserve_rate"])
        growth_capital = project + max(0, revenue - previous_revenue) * case["other_capital_per_incremental_sales"]
        available_cash = beginning_cash + profit - growth_capital
        # 当期预算按普通利润分配，三季度已表决的款项在第一年另行结算。
        distribution = profit * case["payout"]
        if year == 1:
            distribution += shares * data["approved_dividend_per_share"]
        distribution = min(distribution, legal, available_cash)
        legal -= distribution
        excess = available_cash - distribution
        assert min(excess, legal, distribution) >= 0
        assert isclose(beginning_cash + profit, excess + growth_capital + distribution)
        records.append(dict(revenue=revenue, profit=operating_profit, growth_capital=growth_capital,
                            dividend=distribution / shares, ending_excess=excess))
    terminal_business = steady_business(operating_profit, case["perpetual_growth"], case["terminal_roic"], rate)
    terminal = (terminal_business + excess) / shares
    dividends = [record["dividend"] for record in records]
    price, terminal_pv = value(dividends, terminal, rate)
    paired_capital = sum(row["growth_capital"] for row in records[1:])
    return dict(present=price, terminal=terminal, distributions=dividends,
                terminal_share=terminal_pv / price, y1_sales=records[0]["revenue"],
                y5_sales=revenue, y5_profit=operating_profit, y5_excess=excess,
                y1_to_y5_profit_change=operating_profit-records[0]["profit"],
                y1_to_y5_growth_capital=paired_capital)


def main():
    # 一年后领取 1 元、终值 10 元，折现 10%，现值 10 元。零增长盈利 1 元值 10 元。
    assert isclose(value([1], 10, 0.1)[0], 10)
    assert isclose(steady_business(1, 0, 0.2, 0.1), 10)
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    cases = data["cases"]
    base = cases["base"]
    paths = {
        "structural_bear": (cases["structural_bear"], cases["structural_bear"]["rate"]),
        "cyclical_bear": (cases["cyclical_bear"], cases["cyclical_bear"]["rate"]),
        "base_low": (base, base["rate_low_value"]),
        "base_high": (base, base["rate_high_value"]),
        "bull": (cases["bull"], cases["bull"]["rate"])
    }
    results = {name: forecast(data, case, rate) for name, (case, rate) in paths.items()}
    values = [r["present"] for r in results.values()]
    assert values == sorted(values) and values[0] >= 0
    base_result = results["base_low"]
    assert base_result["distributions"] == results["base_high"]["distributions"]
    crosscheck = []
    rate = (base["rate_low_value"] + base["rate_high_value"]) / 2
    for pe in data["base_crosscheck_pe"]:
        terminal = (base_result["y5_profit"] * pe + base_result["y5_excess"]) / data["shares"]
        crosscheck.append(round(value(base_result["distributions"], terminal, rate)[0], 2))
    rounded = {name: {k: ([round(n, 4) for n in v] if isinstance(v, list) else round(v, 4))
                      for k, v in result.items()} for name, result in results.items()}
    high = results["base_high"]
    output = {
        "symbol": "CN:920160",
        "report_period": "2026-Q3",
        "value_range": {
            "currency": "CNY",
            "low": round(base_result["present"], 2),
            "high": round(high["present"], 2),
        },
        "return_model": {
            "schema_version": 1,
            "method": "annual_common_equity_irr_v1",
            "currency": "CNY",
            "model_as_of": data["as_of"],
            "base_case_distributions_per_share": rounded["base_low"]["distributions"],
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": {"low": round(base_result["terminal"], 2), "high": round(high["terminal"], 2)}
            },
        },
        "cases": rounded,
        "terminal_pe_crosscheck": crosscheck,
    }
    (HERE / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
