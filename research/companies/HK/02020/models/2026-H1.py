"""在任意目录执行 python 2026-H1.py，将同目录输入复算为简明结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "2026-H1-input.json").read_text())
FX = DATA["foreign_exchange"]
SHARES = DATA["shares"]
DILUTED = SHARES["issued"] + SHARES["convertible"]
UNITS = DILUTED * FX["rmb_per_hkd"]
CAP = DATA["capital"]


def trailing(annual, prior_half, current_half):
    return [a - b + c for a, b, c in zip(annual, prior_half, current_half)]


def present_value(dividends, terminal, discount):
    return sum(d / (1 + discount) ** t for t, d in enumerate(dividends, 1)) + terminal / (1 + discount) ** len(dividends)


def terminal_per_share(total_before_bond):
    # 比较转换和偿付本金对普通股的影响。债券持有人经济上选择较高索偿。
    redemption = SHARES["bond_principal_eur"] * FX["rmb_per_eur"]
    converted = total_before_bond / DILUTED
    redeemed = (total_before_bond - redemption) / SHARES["issued"]
    return min(converted, redeemed) / FX["rmb_per_hkd"]


def opening_cash():
    cash = DATA["cash"]
    hq = cash["group_deposits"] - sum(cash["segment_cash_reserved"])
    return hq - sum(cash[k] for k in ("pledged_exclusion", "bank_loans", "financial_bills",
                                      "puma_consideration", "interim_dividend_paid", "headquarters_buffer"))


def forecast(s):
    sales = trailing(DATA["fy25_sales"], DATA["h125_sales"], DATA["h126_sales"])
    ebit = trailing(DATA["fy25_segment_ebit"], DATA["h125_segment_ebit"], DATA["h126_segment_ebit"])
    initial_margins = [e / r for e, r in zip(ebit, sales)]
    cash = opening_cash()
    dividends, earnings, invested, revenues = [], [], [], []
    for year in range(1, 6):
        rates = s["first_growth"] if year == 1 else s["following_growth"]
        updated = [r * (1 + g) for r, g in zip(sales, rates)]
        # 每个品牌扩张都要占用资本，衰退门店不预设可按账面撤出。
        added_sales = sum(max(new - old, 0) for old, new in zip(sales, updated))
        margins = [start + (end - start) * year / 5 for start, end in zip(initial_margins, s["margin_y5"])]
        revenue = sum(updated)
        op_profit = sum(r * m for r, m in zip(updated, margins)) - revenue * DATA["headquarters_cost_ratio"]
        parent_profit = (op_profit - revenue * CAP["lease_interest_ratio"]) * (1 - CAP["tax"]) * CAP["parent_share"]
        depreciation = revenue * CAP["depreciation_ratio"]
        gross_capex = max(depreciation + max(s["net_capex_floor"], added_sales * s["net_capex_per_growth"]),
                          CAP["committed_fixed_capex"] if year == 1 else 0)
        net_reinvestment = (gross_capex - depreciation + added_sales * s["working_capital_per_growth"]) * CAP["parent_share"]
        cash_cost = s["clearance_cash_cost_y1"] if year == 1 else 0
        available = parent_profit - net_reinvestment - cash_cost
        dividend = max(0, min(parent_profit * s["payout"], available))
        old_cash = cash
        cash += available - dividend
        assert isclose(old_cash + parent_profit, cash + dividend + net_reinvestment + cash_cost)
        dividends.append(dividend / UNITS)
        earnings.append(parent_profit)
        invested.append(net_reinvestment)
        revenues.append(revenue)
        sales = updated
    a = DATA["associate"]
    amer = a["amer_start_profit_usd"] * (1 + s["amer_growth"])**5 * s["amer_exit_pe"] * a["amer_stake"] * FX["rmb_per_usd"]
    puma = s["puma_y5_sales"] * s["puma_net_margin"] * s["puma_exit_pe"] * a["puma_stake"] * FX["rmb_per_eur"]
    return dividends, earnings, invested, revenues, cash, amer, puma


def evaluate(s, discount, multiple=None):
    dividends, profits, invested, revenues, cash, amer, puma = forecast(s)
    growth = s["steady_growth"]
    distributable = profits[-1] * (1 + growth) * (1 - growth / s["steady_roic"])
    core_value = profits[-1] * multiple if multiple else distributable / (discount - growth)
    terminal = terminal_per_share(core_value + cash + amer + puma)
    value = present_value(dividends, terminal, discount)
    return dict(value=round(value, 2), terminal=round(terminal, 2), dividends=[round(x, 3) for x in dividends],
                terminal_pv_weight=round(terminal / (1 + discount)**5 / value, 3),
                y1_y5_parent_profit=[round(profits[i], 3) for i in (0, 4)],
                y1_y5_sales=[round(revenues[i], 3) for i in (0, 4)],
                y2_y5_reinvestment=round(sum(invested[1:]), 3),
                year5_cash=round(cash, 3), amer_year5=round(amer, 3), puma_year5=round(puma, 3))


if __name__ == "__main__":
    assert isclose(present_value([1], 10, 0.1), 10)
    assert isclose(opening_cash(), 12.316)
    cases = {name: [evaluate(s, r) for r in s["discount"]] for name, s in DATA["scenarios"].items()}
    low, high = cases["base"]
    levels = [cases["structural_bear"][0]["value"], cases["cyclical_bear"][0]["value"], low["value"], high["value"], cases["bull"][0]["value"]]
    assert levels == sorted(levels) and min(levels) > 0
    assert low["dividends"] == high["dividends"]
    base = DATA["scenarios"]["base"]
    aux = [evaluate(base, rate, multiple)["value"] for rate, multiple in zip(base["discount"], DATA["secondary_pe"])]
    result = dict(symbol=DATA["symbol"], report_period=DATA["report_period"],
                  value_range=dict(low=low["value"], high=high["value"], currency="HKD"),
                  return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                                    model_as_of=DATA["as_of"], base_case_distributions_per_share=low["dividends"],
                                    base_case_terminal_equity_value_range_per_share={"year_5": {"low": low["terminal"], "high": high["terminal"]}}),
                  scenario_values=dict(zip(("structural_bear","cyclical_bear","base_low","base_high","bull"), levels)),
                  secondary_value_range=aux, opening_cash_rmb_bn=round(opening_cash(), 3), case_details=cases)
    (ROOT / "2026-H1-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
