"""标准库复算。将同名输入与源码放在一起，直接运行后生成输出。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def present(cash, rate):
    return sum(value / (1 + rate) ** year for year, value in enumerate(cash, 1))


def one_year(revenue, growth, path, tax):
    new_revenue = revenue * (1 + growth)
    profit = new_revenue * (path["gross"] - path["rd"] - path["other"]) * (1 - tax)
    # 需求收缩时不给积压库存或存量固定资产假设变现收益。
    increase = max(0, new_revenue - revenue)
    capital = increase * (path["wc_per_growth"] + path["fixed_per_growth"]) + new_revenue * path["net_renewal"]
    return new_revenue, profit, capital


def bridge(facts):
    liquid = (facts["cash_equivalent"] + facts["trading_assets"] + facts["term_deposits_noncurrent"]
              + facts["paid_exercise_proceeds"] - facts["current_lease"] - facts["noncurrent_lease"]
              - facts["minority_cash_allowance"] - facts["operating_liquidity"])
    outside = facts["issued"] - facts["treasury_sep"] + facts["transferred_nov"]
    awards = sum(facts[k] for k in ("award_2022", "award_2024", "award_2025", "award_2026_initial",
                                    "award_2026_reserved_granted")) - facts["cancelled_nov"] - facts["transferred_nov"]
    earmarked = sum(amount * (1 - used) for amount, used in zip(facts["project_budgets"], facts["project_progress"]))
    return liquid, outside + awards, earmarked


def model(path, inputs):
    facts = inputs["opening"]
    cash, shares, restricted = bridge(facts)
    opening_cash = cash
    revenue = facts["q4_2025_revenue"] + facts["nine_month_revenue"]
    unspent = restricted
    distributions, profits, capital, revenues = [], [], [], []
    for growth, release in zip(path["growth"], inputs["project_release"]):
        revenue, profit, investment = one_year(revenue, growth, path, inputs["tax"])
        assert restricted * release <= revenue * path["rd"] + investment
        unspent = max(0, unspent - restricted * release)
        cash += profit - investment
        distribution = min(profit * path["payout"], max(0, cash - unspent))
        cash -= distribution
        assert cash >= unspent - 1e-8
        distributions.append(distribution)
        profits.append(profit)
        capital.append(investment)
        revenues.append(revenue)
    assert abs(cash - opening_cash - sum(profits) + sum(capital) + sum(distributions)) < 1e-8
    assert unspent < 1e-7
    terminals = [(profits[-1] * multiple + cash) / shares for multiple in path["pe"]]
    dividends = [amount / shares for amount in distributions]
    terminal_pv = [value / (1 + path["discount"]) ** 5 for value in terminals]
    values = [value + present(dividends, path["discount"]) for value in terminal_pv]
    return {"values": values, "terminals": terminals, "dividends": dividends, "year5_revenue": revenue,
            "year5_profit": profits[-1], "year5_net_cash": cash, "net_invested_y2_y5": sum(capital[1:]),
            "profit_increase_y1_y5": profits[-1] - profits[0], "terminal_pv_share": [v / p for v, p in zip(terminal_pv, values)]}


def cashflow_check(inputs):
    path = inputs["paths"]["base"]
    check = inputs["cashflow_check"]
    cash, shares, _ = bridge(inputs["opening"])
    revenue = inputs["opening"]["q4_2025_revenue"] + inputs["opening"]["nine_month_revenue"]
    cashflows = []
    for growth in path["growth"] + check["growth_y6_y10"] + [check["perpetual_growth"]]:
        revenue, profit, investment = one_year(revenue, growth, path, inputs["tax"])
        cashflows.append(profit - investment)
    return [round((cash + present(cashflows[:10], r)
                   + cashflows[10] / (r - check["perpetual_growth"]) / (1 + r) ** 10) / shares, 2)
            for r in check["discounts"]]


def main():
    i = json.loads((ROOT / "2026-Q3-input.json").read_text())
    assert present([11], 0.10) == 10
    sample = dict(i["paths"]["base"], gross=0.5, rd=0.2, other=0.1, wc_per_growth=0.3,
                  fixed_per_growth=0.2, net_renewal=0)
    rev, earning, cap = one_year(100, 0.1, sample, 0)
    assert all(abs(a-b) < 1e-9 for a,b in zip([rev, earning, cap], [110, 22, 5]))
    runs = {key: model(path, i) for key, path in i["paths"].items()}
    base = runs["base"]
    values = [round(x, 2) for x in base["values"]]
    anchors = [round(runs[k]["values"][0], 2) for k in ("structural_bear","cyclical_bear")] + values + [round(runs["bull"]["values"][0], 2)]
    assert sorted(anchors) == anchors and anchors[0] >= 0
    terms = dict(zip(("low","high"), (round(x, 2) for x in base["terminals"])))
    payouts = [round(v, 3) for v in base["dividends"]]
    for v, tv in zip(values, terms.values()):
        assert abs(v - present(payouts, i["paths"]["base"]["discount"]) - tv / 1.1 ** 5) < 0.01
    result = {
        "symbol": i["symbol"], "report_period": i["report_period"],
        "value_range": {"low": values[0], "high": values[1], "currency": "CNY"},
        "return_model": {"schema_version": 1, "method":"annual_common_equity_irr_v1",
                         "currency":"CNY", "model_as_of":i["as_of"], "base_case_distributions_per_share":payouts,
                         "base_case_terminal_equity_value_range_per_share":{"year_5":terms}},
        "scenarios": {"currency":"CNY", **dict(zip(("structural_bear","cyclical_bear","base_low","base_high","bull"),anchors)),
                      "horizon_note":"人民币普通股现值。连接芯片替代、库存周期、已有平台扩量、新平台跨代采用分别改变研发后的盈利、资金占用、派息及第五年经营倍数。"},
        "opening_cash_shares_earmarked": bridge(i["opening"]), "ten_year_fcfe_per_share":cashflow_check(i),
        "scenarios_detail":runs,
        "base_gross_margin_minus_two_points":model(dict(i["paths"]["base"],gross=i["paths"]["base"]["gross"]-0.02),i)["values"]
    }
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    main()
