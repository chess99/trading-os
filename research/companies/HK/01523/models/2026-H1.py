"""用同目录输入重算珩湾科技普通股估值，金额百万美元，股价港元。"""
import json
from math import isclose
from pathlib import Path

folder = Path(__file__).resolve().parent


def operating_path(opening_sales, opening_cash, hkd_per_million, path):
    sales = opening_sales
    cash = opening_cash
    rate = path["discount"]
    dividends = []
    invested = []
    earnings = []
    assert len(path["growth"]) == len(path["margins"]) == len(path["exceptional_cash"]) == 5
    for growth, margin, expense in zip(path["growth"], path["margins"], path["exceptional_cash"]):
        new_sales = sales * (1 + growth)
        profit = new_sales * margin
        investment = max(0, new_sales - sales) * path["capital_intensity"]
        free_cash = profit - investment - expense
        dividend = min(profit * path["payout"], max(free_cash, 0))
        next_cash = cash + free_cash - dividend
        assert next_cash >= 0 and isclose(next_cash + dividend + investment + expense, cash + profit)
        cash, sales = next_cash, new_sales
        dividends.append(dividend * hkd_per_million)
        earnings.append(profit)
        invested.append(investment)
    g = path["steady_growth"]
    assert rate > g
    mature_cash = sales * (1 + g) * path["margins"][-1] - sales * g * path["capital_intensity"]
    terminal = (mature_cash / (rate - g) + cash) * hkd_per_million
    dividend_pv = sum(d / (1 + rate)**t for t, d in enumerate(dividends, start=1))
    pv_terminal = terminal / (1 + rate)**len(dividends)
    return dict(value=dividend_pv + pv_terminal, terminal=terminal, dividends=dividends,
                terminal_pv_share=pv_terminal / (dividend_pv + pv_terminal), dividend_pv=dividend_pv,
                retained_cash=cash, earnings=earnings, invested=invested)


def calculate(data):
    facts = data["facts"]
    opening_sales = facts["fy25_revenue"] + facts["h126_revenue"] - facts["h125_revenue"]
    diluted = facts["issued"] + facts["options"]
    exchange = facts["usd_hkd"]
    per_share = exchange / diluted
    opening_cash = (facts["cash"] + facts["term_deposit"] - facts["borrowings"] - facts["tax_payable"]
                    - facts["interim_hkd"] * facts["dividend_record_shares"] / exchange - facts["working_liquidity"])
    paths = data["paths"]
    cases = {key: operating_path(opening_sales, opening_cash, per_share, path) for key, path in paths.items()}
    anchors = {key: round(item["value"], 2) for key, item in cases.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    lower, upper = cases["base_low"], cases["base_high"]
    assert lower["dividends"] == upper["dividends"]
    value_range = dict(currency="HKD", low=anchors["base_low"], high=anchors["base_high"])
    model = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD", model_as_of=data["as_of"],
                 base_case_distributions_per_share=[round(item, 4) for item in lower["dividends"]],
                 base_case_terminal_equity_value_range_per_share={"year_5":dict(low=round(lower["terminal"], 2), high=round(upper["terminal"], 2))})
    cross_check = {}
    for key, multiple in zip(("base_low","base_high"), data["normalized_profit_multiples"]):
        case = cases[key]
        end = multiple * case["earnings"][-1] + case["retained_cash"]
        cross_check[key] = round(case["dividend_pv"] + per_share * end / (1 + paths[key]["discount"])**5, 2)
    return dict(symbol=data["symbol"],report_period=data["period"],value_range=value_range,return_model=model,
                scenarios=anchors, cross_check=cross_check, opening_excess_cash_usdm=round(opening_cash, 3),
                share_count_million=diluted, opening_revenue_usdm=round(opening_sales,3),
                base_annual_profit_usdm=[round(x, 2) for x in lower["earnings"]],
                base_growth_investment_usdm=[round(x,2) for x in lower["invested"]],
                base_year5_surplus_usdm=round(lower["retained_cash"],2),
                terminal_pv_share=[round(x["terminal_pv_share"],3) for x in (lower,upper)])


if __name__ == "__main__":
    flat = dict(growth=[0]*5, margins=[0.1]*5, exceptional_cash=[0]*5, payout=1,
                capital_intensity=0.3, discount=0.10, steady_growth=0)
    # 10 美元永续分配，以 10% 折现等于 100 美元，独立检查正式函数。
    assert isclose(operating_path(100, 0, 1, flat)["value"], 100)
    inputs = json.loads((folder / "2026-H1-input.json").read_text())
    output = calculate(inputs)
    (folder / "2026-H1-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
