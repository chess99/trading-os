"""从同目录输入以标准库复算，每股单位为人民币元。"""
import json
from math import isclose
from pathlib import Path

here = Path(__file__).resolve().parent
data = json.loads((here / "2026-Q3-input.json").read_text())
cash = data["cash_bridge"]
equity = data["share_bridge"]
opening = (cash["cash"] + cash["liquid_investments"] + cash["certificates_h1_carried"]
           - cash["lease_and_current_debt"] - cash["repurchase_after_q3"] - cash["operating_reserve"])
shares = (equity["issued"] - equity["repurchased"] + equity["eligible_2023"]
          + equity["award_2026"] + equity["older_award_allowance"])


def holder_pv(dividends, terminal, discount):
    return (sum(d / (1 + discount) ** t for t, d in enumerate(dividends, 1))
            + terminal / (1 + discount) ** len(dividends))


def continuing_value(earnings, rate, growth, stable, reinvest_return, stable_return):
    """第六至十年利润增长逐步回落，持续经营段留足增量投资。"""
    value = 0
    for year in range(1, 6):
        next_growth = growth + (stable - growth) * (year - 1) / 4
        incremental_capital = earnings * next_growth / reinvest_return
        earnings *= 1 + next_growth
        value += (earnings - incremental_capital) / (1 + rate) ** year
    steady_flow = earnings * (1 + stable) * (1 - stable / stable_return)
    return value + steady_flow / (rate - stable) / (1 + rate) ** 5


def calculate(raw):
    p = dict(zip(data["path_fields"], raw, strict=True))
    start = data["start"]
    target = p["audio_volume"] * p["audio_asp"] + p["other_volume"] * p["other_asp"]
    balance = opening
    previous_revenue = start["revenue"]
    dividends = [d * p["dividend_scale"] for d in data["base_dividends"]]
    cumulative_flow = 0
    interest = 0
    for year, dividend in enumerate(dividends, 1):
        weight = year / 5
        def blend(initial, final):
            return initial + (final - initial) * weight
        revenue = blend(start["revenue"], target)
        margin = blend(start["gross_margin"], p["gross_margin"])
        rd = blend(start["cash_rd"], p["cash_rd"])
        overhead = revenue * blend(start["other_cost_rate"], p["other_cost_rate"])
        operating = revenue * margin - rd - overhead
        earnings = operating - max(operating, 0) * data["tax"]
        net_investment = (revenue - previous_revenue) * p["working_capital_rate"] + p["annual_net_capex"]
        cash_flow = earnings - net_investment - (p["first_year_writeoff"] if year == 1 else 0)
        cash_interest = balance * data["cash_yield"]
        balance += cash_interest + cash_flow - dividend * shares
        interest += cash_interest
        cumulative_flow += cash_flow
        previous_revenue = revenue
        assert balance >= 0
    assert isclose(opening + interest + cumulative_flow, balance + sum(dividends) * shares)
    business = max(0, earnings * p["exit_multiple"])
    terminal = (balance + business) / shares
    rate = p["discount_rate"]
    pv = holder_pv(dividends, terminal, rate)
    other = continuing_value(earnings, rate, p["transition_growth"], p["stable_growth"],
                             p["transition_ronic"], p["stable_ronic"])
    return {k:round(v, 2) for k,v in {
        "revenue_year5":target, "chip_earnings_year5":earnings, "cash_year5":balance,
        "terminal_per_share":terminal, "today_per_share":pv,
        "terminal_pv_pct":100 * terminal / (1 + rate) ** 5 / pv,
        "operating_terminal_pv_pct":100 * business / shares / (1 + rate) ** 5 / pv,
        "second_method_pv":holder_pv(dividends, (balance + max(0,other)) / shares, rate)
    }.items()}


assert isclose(holder_pv([1, 1], 10, 0.1), 10)
assert isclose(continuing_value(1, 0.1, 0, 0, 0.2, 0.2), 10)
results = {name:calculate(raw) for name,raw in data["paths"].items()}
values = {name:v["today_per_share"] for name,v in results.items()}
assert list(values.values()) == sorted(values.values())
low, high = results["base_low"], results["base_high"]
result = {
    "symbol":data["symbol"], "report_period":data["period"],
    "value_range":{"low":values["base_low"],"high":values["base_high"],"currency":"CNY"},
    "scenarios":{"currency":"CNY",**values,"horizon_note":"同一稀释股本、现金及五年折现期，联动终端颗数、单价、研发、营运资本和终态经营倍数。"},
    "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY",
        "model_as_of":data["cutoff"],"base_case_distributions_per_share":data["base_dividends"],
        "base_case_terminal_equity_value_range_per_share":{"year_5":
            {"low":low["terminal_per_share"],"high":high["terminal_per_share"]}}},
    "opening_surplus_cash_yi":round(opening,3),"diluted_shares_yi":round(shares,5),"calculations":results
}
(here / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
