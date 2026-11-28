"""在模型目录执行 python 2026-Q3.py，输入与输出位于本文件旁。"""
import json
from pathlib import Path
from math import isclose

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "2026-Q3-input.json").read_text())


def opening_bridge(a):
    gross = sum(a[k] for k in ("cash", "trading", "within_year", "other_current", "other_long_term"))
    deductions = sum(a[k] for k in ("nondeposit_and_restricted_allowance", "operating_cash_reserve",
                                     "lease_principal", "committed_construction"))
    return gross - deductions + a["portfolio_books"] * a["portfolio_recovery"]


def settle_claims(equity, ordinary, awards):
    """以五年末为统一结算日。仅在价值超过缴款价时计入股数和缴款。"""
    shares, proceeds = ordinary, 0.0
    for award in sorted(awards, key=lambda a: a["strike"]):
        if (equity + proceeds) / shares <= award["strike"]:
            break
        shares += award["shares"]
        proceeds += award["shares"] * award["strike"]
    price = (equity + proceeds) / shares
    assert isclose(price * shares, equity + proceeds)
    return price, shares, proceeds


def alternative_operations(revenue, p, intensity):
    """以第6至10年经营现金和第11年永续现金，计算第5年末经营资产。"""
    discount, stable_growth = p["discount"], p["perpetual_growth"]
    assert discount > stable_growth
    value = 0.0
    for year in range(1, 6):
        growth = p["transition_growth"] + (stable_growth - p["transition_growth"]) * (year - 1) / 4
        increment = revenue * growth
        revenue += increment
        cash = revenue * p["margin"] - increment * intensity
        value += cash / (1 + discount) ** year
    next_cash = revenue * (1 + stable_growth) * p["margin"] - revenue * stable_growth * intensity
    return value + next_cash / (discount - stable_growth) / (1 + discount) ** 5


def value_case(data, p):
    opening = opening_bridge(data["financial_assets"])
    shares = data["shares"]
    ordinary = shares["issued"] - shares["treasury"]
    revenue = data["base_revenue_2026e"]
    start_margin = data["initial_aftertax_operating_margin"]
    cash = opening
    dividend_pv = 0.0
    net_capital = 0.0
    intensity = p["net_fixed_per_added_sale"] + p["working_per_added_sale"]
    for year, payout in enumerate(data["base_dividends_per_share"], 1):
        change = revenue * p["growth"]
        revenue += change
        margin = start_margin + (p["margin"] - start_margin) * year / 5
        profit = revenue * margin
        # 萎缩期不假定应收与在役设备可以按原账面价值退出。
        investment = max(change, 0) * intensity
        net_capital += investment
        fcf = profit - investment - (p["restructuring"] if year <= 2 else 0)
        dividend = payout * p["dividend_fraction"]
        cash = cash * (1 + data["cash_yield_after_tax"]) + fcf - ordinary * dividend
        assert cash >= 0
        dividend_pv += dividend / (1 + p["discount"]) ** year
    terminal_operations = revenue * margin * p["multiple"]
    end, diluted, contributed = settle_claims(terminal_operations + cash, ordinary, shares["awards"])
    factor = (1 + p["discount"]) ** 5
    today = dividend_pv + end / factor
    alt_ev = alternative_operations(revenue, p, intensity)
    alt_end, _, _ = settle_claims(alt_ev + cash, ordinary, shares["awards"])
    return {"value": round(today, 2), "alternative": round(dividend_pv + alt_end / factor, 2),
            "terminal_per_share": round(end, 2), "operating_terminal_pv_share": round(terminal_operations / diluted / factor / today, 4),
            "holder_terminal_pv_share": round(end / factor / today, 4),
            "revenue_y5": round(revenue, 2), "profit_y5": round(profit, 2), "cash_y5_pre_exercise": round(cash, 2),
            "net_investment_5y": round(net_capital, 2), "exercise_cash": round(contributed, 2),
            "effective_shares_y5": round(diluted, 5)}


def main():
    # 独立手算：权益100元/10股，2股以4元认购后108/12=9元；12元奖励不归属。
    assert settle_claims(100, 10, [{"shares": 2, "strike": 4}, {"shares": 1, "strike": 12}]) == (9, 12, 8)
    # 营收10、净利率10%、无成长和外部资本，五年盈利留存5，主业终值10，每股15。
    flat = dict(D, base_revenue_2026e=10, initial_aftertax_operating_margin=0.1,
                cash_yield_after_tax=0, base_dividends_per_share=[0] * 5,
                financial_assets=dict.fromkeys(D["financial_assets"], 0),
                shares={"issued": 1, "treasury": 0, "awards": []})
    flat_case = dict(D["cases"]["base_low"], growth=0, margin=0.1, multiple=10,
                     discount=0.1, transition_growth=0, perpetual_growth=0)
    hand = value_case(flat, flat_case)
    assert hand["terminal_per_share"] == 15
    assert hand["value"] == hand["alternative"] == round(15 / 1.1**5, 2)
    cases = {key: value_case(D, p) for key, p in D["cases"].items()}
    anchors = {key: item["value"] for key, item in cases.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    note = "同一权益桥与授予池。情景同步调整需求、税后主营利润率、增量资本占用、终态倍数与折现率，五年末扣除已派现金后折回资料截止日。"
    output = {"symbol": D["symbol"], "report_period": D["report_period"],
              "opening_excess_assets": round(opening_bridge(D["financial_assets"]), 2),
              "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "CNY"},
              "scenarios": {"currency": "CNY", **anchors, "horizon_note": note},
              "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1",
                               "currency": "CNY", "model_as_of": D["cutoff"],
                               "base_case_distributions_per_share": D["base_dividends_per_share"],
                               "base_case_terminal_equity_value_range_per_share": {"year_5": {
                                   "low": cases["base_low"]["terminal_per_share"], "high": cases["base_high"]["terminal_per_share"]}}},
              "case_details": cases}
    (HERE / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
