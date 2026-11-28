"""运行 python 2026-Q3.py，以同目录输入重算并写出两种估值及人民币现金桥。"""
from pathlib import Path
import json
from math import isclose

HERE = Path(__file__).resolve().parent


def operating_year(revenue, growth, margin, tax, capital_per_growth):
    next_revenue = revenue * (1 + growth)
    nopat = next_revenue * margin * (1 - tax)
    # 营收下降时不假设可以立即退出既有资本。
    investment = max(0, next_revenue - revenue) * capital_per_growth
    return next_revenue, nopat, investment


def case_value(revenue, cash, shares_in_hkd, case, tax, cash_yield):
    """shares_in_hkd 为十亿股×人民币/港元，人民币十亿元除之得到每股港元。"""
    retained = cash
    annual = []
    for growth, margin in zip(case["growth"], case["margin"]):
        revenue, nopat, capital = operating_year(revenue, growth, margin, tax, case["capital_per_growth"])
        free_cash = nopat - capital
        retained = retained * (1 + cash_yield) + free_cash
        annual.append((revenue, nopat, capital, free_cash))
    rate = case["discount"]
    year5_business = annual[-1][1] * case["exit_multiple"]
    terminal_equity = retained + year5_business
    factor = (1 + rate) ** 5
    primary = terminal_equity / factor / shares_in_hkd
    mature = case["perpetual_growth"]
    assert 0 <= mature < rate
    growth5, margin5 = case["growth"][-1], case["margin"][-1]
    business_dcf_at_5 = 0
    for step in range(1, 6):
        growth = growth5 + (mature - growth5) * step / 5
        revenue, nopat, capital = operating_year(revenue, growth, margin5, tax, case["capital_per_growth"])
        business_dcf_at_5 += (nopat - capital) / (1 + rate) ** step
    _, nopat11, capital11 = operating_year(revenue, mature, margin5, tax, case["capital_per_growth"])
    perpetuity_at_5 = (nopat11 - capital11) / (rate - mature) / (1 + rate) ** 5
    secondary = (retained + business_dcf_at_5 + perpetuity_at_5) / factor / shares_in_hkd
    assert isclose(retained, cash * (1 + cash_yield) ** 5 + sum(
        row[3] * (1 + cash_yield) ** (4 - t) for t, row in enumerate(annual)))
    assert isclose(terminal_equity / shares_in_hkd, primary * factor)
    return {
        "value_hkd": round(primary, 2), "year5_hkd": round(terminal_equity / shares_in_hkd, 2),
        "alternate_dcf_hkd": round(secondary, 2), "year5_revenue": round(annual[-1][0], 3),
        "year5_cash": round(retained, 3), "year5_nopat": round(annual[-1][1], 3),
        "year5_business_share": round(year5_business / terminal_equity, 3),
        "opening_excess_cash": round(cash, 3),
        "y1_to_y5_nopat_gain": round(annual[-1][1] - annual[0][1], 3),
        "y1_end_to_y5_end_capital": round(sum(row[2] for row in annual[1:]), 3),
    }


def main():
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    facts, assumptions = data["facts"], data["assumptions"]
    zero_growth = {"growth": [0]*5, "margin": [0.1]*5, "capital_per_growth": 0.15,
                   "discount": 0.10, "exit_multiple": 10, "perpetual_growth": 0}
    # 营收100、零增长、无税，五年留存50，加现金50及经营价值100，五年末200。
    simple = case_value(100, 50, 1, zero_growth, 0, 0)
    assert simple["year5_hkd"] == 200 and simple["value_hkd"] == round(200 / 1.1**5, 2)
    assert simple["alternate_dcf_hkd"] == simple["value_hkd"]

    start_revenue = (facts["fy25_revenue"] - facts["h1_revenue_2025"] - facts["q3_revenue_2025"]
                     + facts["h1_revenue_2026"] + facts["q3_revenue_2026"])
    fx = facts["cny_per_hkd"]
    shares = facts["issued"] + facts["possible_new_award_shares"]
    wealth = facts["wm_fair_value"] + facts["wm_amortized"]
    cash_pool = facts["cash"] + facts["deposits"] + wealth
    cash_before_reserves = cash_pool - facts["lease_liabilities"] - facts["award_purchases_hkd"] * fx

    def run(case):
        cash = (cash_before_reserves - assumptions["operating_liquidity_reserve"]
                - case["settlement_reserve_extra"] - wealth * case["wm_loss"])
        return case_value(start_revenue, cash, shares * fx, case,
                          assumptions["operating_tax"], assumptions["cash_yield_after_tax"])

    cases = {name: run(case) for name, case in data["cases"].items()}
    anchors = {name: row["value_hkd"] for name, row in cases.items()}
    assert list(anchors.values()) == sorted(anchors.values()) and min(anchors.values()) >= 0
    return_model = {
        "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
        "model_as_of": data["as_of"], "base_case_distributions_per_share": [0.0] * 5,
        "base_case_terminal_equity_value_range_per_share": {"year_5": {
            "low": cases["base_low"]["year5_hkd"], "high": cases["base_high"]["year5_hkd"]}}
    }
    low = data["cases"]["base_low"]
    sensitivity = run({**low, "margin": [m - 0.01 for m in low["margin"]]})
    result = {"symbol": data["symbol"], "report_period": data["report_period"],
              "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "HKD"},
              "scenarios": anchors, "return_model": return_model, "cash_resources_ex_restricted": round(cash_pool, 3),
              "diluted_billion_shares": round(shares, 6), "ttm_revenue": round(start_revenue, 3),
              "base_low_margin_minus_1pp_hkd": sensitivity["value_hkd"], "cases": cases}
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
