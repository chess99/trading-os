"""在本目录运行 python3 2026-Q3.py。金额为百万港元，每股金额为港元。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "2026-Q3-input.json").read_text())
facts = data["observed"]


def operating_path(case):
    years = []
    hk_fees = facts["equity_trade"] + facts["equity_clear"]
    north_fees = facts["north_trade"] + facts["north_settle"]
    other_fees = facts["ytd_revenue"] - hk_fees - north_fees
    annual = 4 / 3
    for n, (hk, north) in enumerate(zip(case["cash_adt"], case["north_adt"])):
        growth = (1 + case["cost_growth"]) ** n
        fees = annual * (hk_fees * hk / facts["cash_adt"] * case["cash_fee_factor"]
                         + north_fees * north / facts["north_adt"]
                         + other_fees * case["other_start"] * (1 + case["other_growth"]) ** n)
        fund_income = (facts["fund_average"] * case["fund_balance_factor"] * case["fund_spread"]
                       * (1 + case["fund_growth"]) ** n)
        operating_cost = annual * (facts["ytd_opex"] - facts["ytd_charity_expense"]
                                   + facts["ytd_transaction_expense"]) * case["cost_factor"] * growth
        depreciation = annual * facts["ytd_da"] * growth
        profit = ((fees + fund_income + case["corporate_income"] - operating_cost
                   - depreciation - annual * facts["ytd_interest"]) * (1 - data["tax"])
                  - annual * facts["ytd_nci"])
        capex = case["capex"] * (1 + case["capex_growth"]) ** n
        headquarters = facts["headquarters_due"] if n == 0 else 0
        deployable = (profit + depreciation - capex - headquarters - data["lease_principal"] * growth
                      - case["reserve_addition"] * growth)
        dividend = max(0, min(profit * case["payout"], deployable))
        assert profit > 0 and 0 <= dividend <= deployable
        assert isclose(profit + depreciation, dividend + (deployable - dividend) + capex
                       + headquarters + (case["reserve_addition"] + data["lease_principal"]) * growth)
        years.append(dict(profit=profit, dividend=dividend, cash_limit=deployable, capex=capex,
                          headquarters=headquarters, eps=profit / facts["shares"],
                          dps=dividend / facts["shares"]))
    return years


def dividend_value(dividends, terminal_dividend, discount, growth):
    assert discount > growth
    terminal = terminal_dividend / (discount - growth)
    terminal_pv = terminal / (1 + discount) ** len(dividends)
    value = sum(d / (1 + discount) ** t for t, d in enumerate(dividends, 1)) + terminal_pv
    return value, terminal, terminal_pv / value


def price(case_name, path, discount, growth):
    case = data["cases"][case_name]
    last = path[-1]
    # 稳态派息同时满足增长留存、董事会分派惯例和现金上限。
    payout = min(case["payout"], 1 - growth / data["terminal_incremental_roe"],
                 last["cash_limit"] / last["profit"])
    return dividend_value([y["dps"] for y in path], last["eps"] * (1 + growth) * payout,
                          discount, growth)


def residual_income():
    p = data["cross_check"]
    book = facts["q3_equity"]
    normalized_ttm = (facts["prior_fy_profit"] - facts["prior_ytd_profit"] + facts["ytd_profit"]
                      - facts["unlisted_mark"] * (1 - data["tax"]))
    normalized_profit = (normalized_ttm + facts["prior_fy_profit"]) / 2
    starting_roe = normalized_profit / book
    value = book
    for year in range(1, p["years"] + 1):
        weight = (year - 1) / (p["years"] - 1)
        roe = starting_roe * (1 - weight) + p["steady_roe"] * weight
        value += book * (roe - p["discount"]) / (1 + p["discount"]) ** year
        book *= 1 + roe * (1 - p["payout"])
    terminal_excess = book * (p["steady_roe"] - p["discount"])
    value += terminal_excess / (p["discount"] - p["growth"]) / (1 + p["discount"]) ** p["years"]
    return round(value / facts["shares"], 2)


def run():
    # 每年派1元、永续零增长、资本成本10%，五年末仍值10元。
    simple = dividend_value([1] * 5, 1, 0.10, 0)
    assert isclose(simple[0], 10) and isclose(simple[1], 10)
    assert facts["q3_total_equity"] == facts["q3_equity"] + facts["q3_nci"]
    paths = {name: operating_path(case) for name, case in data["cases"].items()}
    for name, path in paths.items():
        assert path[0]["capex"] >= facts["total_capital_commitments"] - facts["headquarters_due"]
        assert sum(y["headquarters"] for y in path) == facts["headquarters_due"]
    base = paths["base"]
    endpoints = [price("base", base, *pair) for pair in data["base_discount_growth"]]
    anchors = {k: round(price(k, path, data["cases"][k]["discount"], data["cases"][k]["growth"])[0], 2)
               for k, path in paths.items() if k != "base"}
    low, high = (round(row[0], 2) for row in endpoints)
    assert anchors["structural_bear"] <= anchors["cyclical_bear"] <= low <= high <= anchors["bull"]
    sensitivity = {}
    for key, change in [("cash_adt", 0.9), ("fund_spread", 0.75), ("capex", 1.25)]:
        case = data["cases"]["base"].copy()
        case[key] = [x * change for x in case[key]] if key == "cash_adt" else case[key] * change
        path = operating_path(case)
        sensitivity[key] = round(price("base", path, .08125, .03)[0] / price("base", base, .08125, .03)[0] - 1, 4)
    return {
        "symbol": data["symbol"], "report_period": "2026-Q3",
        "value_range": {"currency": "HKD", "low": low, "high": high},
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
                         "model_as_of": data["as_of"], "base_case_distributions_per_share": [round(y["dps"], 2) for y in base],
                         "base_case_terminal_equity_value_range_per_share": {"year_5": {
                             "low": round(endpoints[0][1], 2), "high": round(endpoints[1][1], 2)}}},
        "scenarios": {"currency": "HKD", **anchors, "base_low": low, "base_high": high,
                      "horizon_note": "均为截至研究日的每股港元价值。成交、收费、资金净息差、技术投入与监管留存共同决定可派现金。"},
        "terminal_pv_shares": [round(row[2], 4) for row in endpoints],
        "base_common_profit_m": [round(y["profit"]) for y in base],
        "base_cash_ceiling_m": [round(y["cash_limit"]) for y in base],
        "residual_income_per_share": residual_income(), "sensitivity_fraction": sensitivity
    }


if __name__ == "__main__":
    result = run()
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
