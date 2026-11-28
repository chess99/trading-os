"""在本目录运行 python 2026-Q3.py，生成同周期的港元每股结果。"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def cash_step(opening_cash, operating_cash, interest, dividend, repurchase):
    closing = opening_cash + operating_cash + interest - dividend - repurchase
    assert closing >= 0 and math.isclose(closing - opening_cash, operating_cash + interest - dividend - repurchase, abs_tol=1e-8)
    return closing


def fair_value(dividends, year_five, rate):
    return sum(dividend / (1 + rate) ** year for year, dividend in enumerate(dividends, 1)) + year_five / (1 + rate) ** len(dividends)


def forecast(case, facts, assumptions, revenue, shares, cash, portfolio):
    distributions = []
    initial_shares = shares
    initial_revenue = revenue
    for growth in case["growth"]:
        increment = revenue * growth
        revenue += increment
        operating = revenue * case["margin"] * (1 - assumptions["tax_rate"]) * assumptions["common_profit_share"]
        interest = cash * assumptions["nonoperating_cash_yield_after_tax"]
        # 营业利润已费用化研发、股份薪酬及维持性折旧；未来薪酬逐年发行权益结算。
        award_expense = revenue * assumptions["award_cost_ratio"]
        awards = initial_shares * assumptions["future_award_shares_ratio"]
        repurchase_cash = award_expense * case["buyback_to_awards"]
        repurchased_shares = awards * case["buyback_to_awards"]
        shares += awards - repurchased_shares
        reinvestment = max(increment, 0) * assumptions["incremental_capital_per_incremental_sale"] + case["extra_annual_investment"]
        free_cash = operating + award_expense - reinvestment
        dividend = min((operating + interest) * case["payout"], free_cash + interest - repurchase_cash)
        distributions.append(dividend / shares / facts["cny_per_hkd"])
        cash = cash_step(cash, free_cash, interest, dividend, repurchase_cash)

    # 稳态将新增股份薪酬等价现金结算，股数固定；经营权与期末金融资产分别计价。
    growth = case["terminal_growth"]
    steady_cash = operating * (1 + growth) * (1 - growth / case["terminal_roic"])
    terminal = [(steady_cash / (rate - growth) + cash + portfolio) / shares / facts["cny_per_hkd"] for rate in case["discount"]]
    values = [fair_value(distributions, tv, rate) for tv, rate in zip(terminal, case["discount"])]
    return {
        "current": [round(v, 2) for v in values], "terminal": [round(v, 2) for v in terminal],
        "dividends": [round(d, 4) for d in distributions],
        "terminal_pv_weight": [round(tv / (1 + r) ** 5 / v, 4) for tv, r, v in zip(terminal, case["discount"], values)],
        "end_cash_bn": round(cash, 3), "end_shares_bn": round(shares, 5), "end_revenue_bn": round(revenue, 3),
        "first_year_gross_repurchase_bn": round(initial_revenue * (1 + case["growth"][0]) * assumptions["award_cost_ratio"] * case["buyback_to_awards"], 3)
    }


def main():
    inputs = json.loads((ROOT / "2026-Q3-input.json").read_text())
    f, a = inputs["facts"], inputs["assumptions"]
    shares = f["ordinary_out_nov25"] + (f["q3_avg_diluted"] - f["q3_avg_basic"]) + f["nov27_grant"]
    revenue = f["revenue_fy25"] - f["revenue_9m25"] + f["revenue_9m26"]
    net_cash = f["cash"] + f["time_deposits"] + f["restricted_cash"] + f["short_investments"] - f["loans"]
    cash = net_cash - f["restricted_cash"] - f["noncontrolling"] - f["redeemable_noncontrolling"] - a["operating_and_remittance_reserve"] - a["post_q3_repurchase_cash_budget"]
    portfolio = f["long_investments_h1"] * a["long_investment_recovery"]
    results = {key: forecast(case, f, a, revenue, shares, cash, portfolio) for key, case in inputs["cases"].items()}
    secondary = [(revenue * a["secondary_margin"] * (1 - a["tax_rate"]) * a["common_profit_share"] * multiple + cash + portfolio) / shares / f["cny_per_hkd"] for multiple in a["secondary_earnings_multiples"]]
    base = results["base"]
    low, high = base["current"]
    structural, cyclical, bull = [results[key]["current"][0] for key in ("structural", "cyclical", "bull")]
    assert 0 <= structural <= cyclical <= low <= high <= bull
    assert cash_step(10, 5, 1, 2, 3) == 11 and math.isclose(fair_value([1], 10, 0.1), 10)
    out = {
        "symbol":inputs["symbol"], "report_period":"2026-Q3",
        "value_range":{"low":low, "high":high, "currency":"HKD"},
        "return_model":{"schema_version":1, "method":"annual_common_equity_irr_v1", "currency":"HKD", "model_as_of":inputs["as_of"], "base_case_distributions_per_share":base["dividends"],
            "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":base["terminal"][0], "high":base["terminal"][1]}}},
        "scenarios":{"currency":"HKD","structural_bear":structural, "cyclical_bear":cyclical, "base_low":low, "base_high":high, "bull":bull,
            "horizon_note":"长线产品老化程度决定经营利润率，前五年的研发、非现金奖励、回购支出和期末股数逐年衔接，稳态增长另扣再投资。"},
        "historical_bridge":{"group_net_cash_bn":round(net_cash,3),"common_surplus_cash_bn":round(cash,3),"recoverable_portfolio_bn":round(portfolio,3),"diluted_shares_bn":round(shares,6),
            "h1_net_shrinkage_bn":round(f["h1_gross_bought"]-f["h1_vested"],6),"declared_trailing_dps_usd":round(sum(f["declared_usd_dps_fy25q4_to_26q3"]),3)},
        "cases":results, "secondary_range_hkd":[round(x,2) for x in secondary]}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    main()
