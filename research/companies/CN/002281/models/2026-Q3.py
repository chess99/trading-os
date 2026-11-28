"""光迅科技。以同目录输入复算五年经营、资本与普通股回报，金额单位亿元。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def discounted_hold(dividends, terminal, rate):
    return sum(v / (1 + rate) ** y for y, v in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def evaluate(basis, case):
    shares = basis["shares"]
    starting_cash = (basis["cash_equivalents"] - basis["borrowings_and_leases"]
                     - basis["paid_dividend"] - basis["minority_cash_reserve"])
    balance = starting_cash
    capital_cashflows = []
    for revenue, margin, fixed, working, dividend in zip(
        case["revenue"], case["common_operating_margin"], case["net_fixed"],
        case["working_capital"], case["dividends"], strict=True
    ):
        earnings = revenue * margin
        cashflow = earnings - fixed - working
        capital_cashflows.append(cashflow)
        balance += cashflow - dividend * shares
        assert balance >= basis["operating_cash_floor"]
    excess = balance - basis["operating_cash_floor"]
    assert isclose(starting_cash + sum(capital_cashflows), balance + shares * sum(case["dividends"]))
    rate = case["required_return"]
    terminal = (earnings * case["terminal_pe"] + excess) / shares
    value = discounted_hold(case["dividends"], terminal, rate)
    growth, incremental_return = case["perpetual_growth"], case["incremental_return"]
    recurring_cash = earnings * (1 + growth) * (1 - growth / incremental_return)
    steady_terminal = (recurring_cash / (rate - growth) + excess) / shares
    secondary = discounted_hold(case["dividends"], steady_terminal, rate)
    return {"value":round(value, 2), "year5":round(terminal, 2), "steady_value":round(secondary, 2),
            "terminal_pv_share":round(terminal / (1 + rate) ** 5 / value, 4),
            "net_cash_at_year5":round(balance, 2), "pre_distribution_cashflows":[round(v, 2) for v in capital_cashflows]}


def main():
    p = json.loads((ROOT / "2026-Q3-input.json").read_text())
    assert isclose(discounted_hold([1, 1], 10, .1), 10.0)
    results = {name:evaluate(p, case) for name, case in p["scenarios"].items()}
    anchors = {name:value["value"] for name, value in results.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    low, high = results["base_low"], results["base_high"]
    payouts = p["scenarios"]["base_low"]["dividends"]
    assert payouts == p["scenarios"]["base_high"]["dividends"]
    return_model = {"schema_version":1, "method":"annual_common_equity_irr_v1","currency":"CNY",
                    "model_as_of":p["cutoff"],"base_case_distributions_per_share":payouts,
                    "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["year5"], "high":high["year5"]}}}
    out = {"symbol":p["symbol"], "report_period":p["report_period"],
           "value_range":{"low":low["value"], "high":high["value"], "currency":"CNY"},
           "return_model":return_model, "scenarios":{"currency":"CNY",**anchors,
           "horizon_note":"五年后各速率产品的留存份额、归母盈利与净投资共同决定终值，折回资料截止日。"},
           "details":results}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
