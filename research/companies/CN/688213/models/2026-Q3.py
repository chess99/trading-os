"""Run python 2026-Q3.py beside 2026-Q3-input.json. Amounts in CNY 100mn."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def discounted(cash_flows, exit_value, rate):
    factors = [(1 + rate) ** year for year in range(1, len(cash_flows) + 1)]
    return sum(flow / factor for flow, factor in zip(cash_flows, factors)) + exit_value / factors[-1]


def bridge(balance, book_factor):
    issued = balance["registered_after_november_vest"] - balance["treasury_shares"]
    count = (issued + balance["unvested_budget"]) / 1e8
    cash = balance["cash"] + balance["vested_cash"] + balance["unvested_budget"] / 1e8 * balance["remaining_strike"]
    debts = sum(balance[k] for k in ("short_debt", "current_maturities", "long_debt", "lease", "short_bond_estimate"))
    cost = balance["wuhan_bank_financed_purchase"]
    associate = (balance["wuhan_equity_before_investment"] + cost) * balance["wuhan_ownership"] * book_factor
    nonoperating = cash + balance["investments_marked_to_market_net_of_derivative"] + balance["other_equity_financial_assets"]
    adjustment = nonoperating - debts - balance["operating_cash_reserve"] - balance["october_associate_investment"] + associate - cost
    return count, adjustment


def value(data, case):
    sales = data["sales_2026_9m"] + data["sales_2025_q4"]
    rate = case["cost_of_capital"]
    count, adjustment = bridge(data["balance"], case["wuhan_book_factor"])
    flows, investments, profits = [], [], []
    for year, growth in enumerate(case["growth"], 1):
        change = sales * growth
        sales += change
        margin = data["starting_nopat_margin"] + (case["margin"] - data["starting_nopat_margin"]) * year / 5
        nopat = sales * margin
        wc = change * case["working_capital"]
        if wc < 0:
            wc *= case["wc_release_fraction"]
        capital = sales * case["net_capex"] + wc
        # Additional cash shortfall on old receivables or stock, above ordinary operating losses.
        loss = case["initial_writeoff"] if year == 1 else 0
        cashflow = nopat - capital - loss
        assert math.isclose(cashflow + capital + loss, nopat)
        flows.append(cashflow)
        investments.append(capital)
        profits.append(nopat)
    exit_value = profits[-1] * case["terminal_multiple"]
    enterprise = discounted(flows, exit_value, rate)
    # Cross-check year 6–10 with explicit growth and incremental investment; steady state at Y11.
    fade_flows = []
    earnings = profits[-1]
    perpetual = case["perpetual_growth"]
    for step in range(5):
        growth = case["fade_growth"] + (perpetual - case["fade_growth"]) * step / 4
        next_earnings = earnings * (1 + growth)
        fade_flows.append(next_earnings - (next_earnings - earnings) / case["steady_roic"])
        earnings = next_earnings
    terminal = (earnings * (1 + perpetual) - earnings * perpetual / case["steady_roic"]) / (rate - perpetual)
    dcf = discounted(flows + fade_flows, terminal, rate)
    return {
        "today_per_share": round((enterprise + adjustment) / count, 2),
        "alternate_dcf_per_share": round((dcf + adjustment) / count, 2),
        "exit_pv_over_equity": round(exit_value / (1 + rate)**5 / (enterprise + adjustment), 3),
        "year5_sales": round(sales, 2), "year5_nopat": round(profits[-1], 2),
        "years1to5_operating_cash_after_reinvestment": [round(x, 2) for x in flows],
        "years1to5_net_investment": round(sum(investments), 2),
        "year1to5_incremental_return": round((profits[-1] - profits[0]) / sum(investments[1:]), 3),
        "equity_bridge": round(adjustment, 2), "diluted_shares_100mn": count
    }


def main():
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    assert math.isclose(discounted([1, 1], 10, .1), 10)
    results = {name: value(data, case) for name, case in data["cases"].items()}
    anchors = {name: result["today_per_share"] for name, result in results.items()}
    values = list(anchors.values())
    assert 0 <= values[0] and values == sorted(values)
    for name, result in results.items():
        assert result["diluted_shares_100mn"] == results["base_low"]["diluted_shares_100mn"]
    out = {"symbol": data["symbol"], "report_period": data["report_period"],
           "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "CNY"},
           "return_model": None, "scenarios": anchors, "case_results": results}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
