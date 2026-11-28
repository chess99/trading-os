"""运行 python 2026-H1.py，从同目录输入重新生成中报估值。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D = json.loads((ROOT / "2026-H1-input.json").read_text())


def present_value(dividends, terminal, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def opening_bridge(b):
    liquid = b["cash_equivalents"] + b["structured_deposits"] + b["time_deposits"] + b["reverse_repo"]
    deductions = sum(b[k] for k in ("borrowings", "settlement_payable", "dividends_payable", "unfunded_fund_call", "operating_liquidity_floor", "outside_equity_book"))
    return liquid - deductions, b["life_insurer_and_fund_fair_value"] * b["unlisted_recovery"]


def project(params):
    p = D["operating_assumptions"][params["path"]]
    f = D["facts"]
    revenue = f["revenue_fy25"] - f["revenue_h125"] + f["revenue_h126"]
    platform = f["platform_fy25"] - f["platform_h125"] + f["platform_h126"]
    other = revenue - platform
    cash, unlisted = opening_bridge(D["financial_bridge"])
    r, g = params["discount"], params["terminal_growth"]
    deposit_yield = D["net_cash_yield"]
    access = ((1 + deposit_yield) / (1 + r)) ** p["access_delay"]
    dividends, capital, earnings = [], [], []
    for i in range(5):
        platform *= 1 + p["platform_growth"][i]
        other *= 1 + p["other_growth"][i]
        next_revenue = platform + other
        op = next_revenue * p["after_tax_operating_margin"][i]
        reinvest = max(0, next_revenue - revenue) * p["capital_per_extra_sale"] + p["dual_running_net_spend"][i]
        available = op - reinvest + cash * deposit_yield
        dividend = min(available, (op + cash * deposit_yield) * p["parent_profit_share"] * p["payout"])
        next_cash = cash + available - dividend
        assert isclose(next_cash - cash + dividend + reinvest, op + cash * deposit_yield) and next_cash >= 0
        dividends.append(dividend)
        capital.append(reinvest)
        earnings.append(op)
        cash, revenue = next_cash, next_revenue
    # Mature annual earnings fund growth first. Each year's retained surplus is accessible only after a delay.
    future_op = earnings[-1] * (1 + g)
    future_free = future_op * (1 - g / params["terminal_roic"])
    steady_dividend = min(future_free, future_op * p["parent_profit_share"] * p["payout"])
    ongoing_value = (steady_dividend + (future_free - steady_dividend) * access) / (r - g)
    terminal = ongoing_value + cash * access + unlisted / (1 + r) ** p["access_delay"]
    pv = present_value(dividends, terminal, r)
    return {"value":pv / UNIT,"dividends":[round(x / UNIT, 5) for x in dividends],"terminal":terminal / UNIT,
            "terminal_pv_share":terminal / (1 + r) ** 5 / pv,"year_1_5_profit_change":earnings[-1] - earnings[0],
            "year_1_5_capital_change":sum(capital[1:]),"year_5_sales":revenue,"year_5_cash":cash}


s = D["shares"]
UNIT = (s["domestic"] + s["h"] - s["treasury"] + s["incremental_dilution"]) * D["cny_per_hkd"]
assert isclose(present_value([1, 1], 10, 0.1), 10)
all_paths = {k:project(v) for k,v in D["valuation_assumptions"].items()}
anchors = {k:round(row["value"], 2) for k,row in all_paths.items()}
assert sorted(anchors.values()) == list(anchors.values())
low, high = all_paths["base_low"], all_paths["base_high"]
assert low["dividends"] == high["dividends"]
cash, unlisted = opening_bridge(D["financial_bridge"])
facts = D["facts"]
normal_profit = facts["group_profit_fy25"] + facts["group_profit_h126"] - facts["group_profit_h125"] - facts["normalised_financial_profit_removed"]
rate = D["cross_check"]["delay_discount_rate"]
delay = D["operating_assumptions"]["base"]["access_delay"]
non_operating_pv = (cash * (1 + D["net_cash_yield"]) ** delay + unlisted) / (1 + rate) ** delay
cross = [(normal_profit * multiple + non_operating_pv) / UNIT for multiple in D["cross_check"]["normalised_ex_cash_pe"]]
output = {"symbol":D["symbol"],"report_period":D["report_period"],"value_range":{"currency":"HKD","low":anchors["base_low"],"high":anchors["base_high"]},
          "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD","model_as_of":D["model_as_of"],"base_case_distributions_per_share":low["dividends"],
                          "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(low["terminal"],2),"high":round(high["terminal"],2)}}},
          "scenarios":{"currency":"HKD",**anchors,"horizon_note":"五年客运处理量、项目利润和更新投入随情景变化。期末分别计入持续经营、延后使用的现金及非上市金融权益。"},
          "opening_free_cash_bn":cash,"unlisted_recoverable_bn":unlisted,"secondary_value_hkd":[round(x,2) for x in cross],"scenario_details":all_paths}
(ROOT / "2026-H1-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
