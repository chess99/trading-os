"""同行目录中运行 python 2026-Q3.py，生成普通股每股人民币估值。"""
import json
from math import isclose
from pathlib import Path

folder = Path(__file__).resolve().parent
data = json.loads((folder / "2026-Q3-input.json").read_text())
facts, common = data["facts"], data["common"]
shares = facts["issued_shares"] + common["potential_award_shares"]
ownership = facts["backplane_ownership"]
liabilities = sum(facts[k] for k in ("short_debt", "debt_due", "long_debt", "lease_debt"))
opening = (facts["cash"] + facts["liquid_assets"] - liabilities
           - facts["refundable_deposit_h1"] - facts["post_period_buyback_cash"]
           - common["operating_cash_buffer"])


def discounted(distributions, terminal, rate):
    return (sum(d / (1 + rate)**n for n, d in enumerate(distributions, 1))
            + terminal / (1 + rate)**len(distributions))


def operating_year(sales, growth, margin, intensity):
    increase = sales * growth
    revenue = sales + increase
    # 下行时须维持产线，不把销售下降自动换成资本回收。
    capital = max(increase, 0) * intensity
    return revenue, revenue * margin, capital


def estimate(s):
    xray, display = common["legacy_sales_start"], common["backplane_sales_start"]
    cash = opening
    distributions = []
    capital_total = 0
    for year, payout in enumerate(common["payout_base"]):
        xray, xprofit, xcap = operating_year(xray, s["legacy_growth"], s["legacy_margin"], s["legacy_capital"])
        display, dprofit, dcap = operating_year(display, s["backplane_growth"], s["backplane_margin"], s["backplane_capital"])
        earnings = xprofit + ownership * dprofit - common["normal_financing_spread_cost"]
        capital = xcap + ownership * dcap + s["ramp"][year]
        capital_total += capital
        holder_cash = payout * s["payout_scale"]
        carry = cash * (common["negative_cash_cost"] if cash < 0 else common["retained_cash_yield"])
        change = earnings + carry - capital - holder_cash * shares
        new_cash = cash + change
        assert isclose(new_cash + capital + holder_cash * shares, cash + carry + earnings, abs_tol=1e-9)
        cash = new_cash
        distributions.append(holder_cash)
    terminal = (earnings * s["multiple"] + cash) / shares
    value = discounted(distributions, terminal, s["rate"])
    return {
        "value":round(value, 2), "terminal":round(terminal, 4),
        "distributions":distributions,"earnings":round(earnings, 4),
        "xray_revenue":round(xray, 3),"display_revenue":round(display, 3),
        "retained_net_cash":round(cash, 3),"net_capital_5y":round(capital_total, 3),
        "terminal_pv_share":round(terminal / (1+s["rate"])**5 / value, 4)
    }


def transition_value(path, s, check):
    # 第六至十年增速线性收敛，每单位增量利润必须配备股东资本。
    earnings = path["earnings"]
    cashflows = []
    for year in range(5):
        growth = check["growth_after_y5"] + year/4 * (check["mature_growth"]-check["growth_after_y5"])
        incremental_profit = earnings * growth
        earnings += incremental_profit
        cashflows.append(earnings - incremental_profit / check["incremental_return"])
    maturity = check["mature_growth"]
    terminal = earnings * (1+maturity-maturity/check["incremental_return"]) / (s["rate"]-maturity)
    y5 = (discounted(cashflows, terminal, s["rate"])+path["retained_net_cash"]) / shares
    return round(discounted(path["distributions"], y5, s["rate"]), 2)


assert operating_year(100, .1, .2, .8) == (110, 22, 8)
assert isclose(discounted([1], 10, .1), 10)
cases = {name:estimate(s) for name, s in data["scenarios"].items()}
values = {name:p["value"] for name,p in cases.items()}
assert list(values.values()) == sorted(values.values()) and min(values.values()) >= 0
low, high = cases["base_low"], cases["base_high"]
assert low["distributions"] == high["distributions"]
out = {
    "symbol":data["symbol"],"report_period":data["report_period"],
    "value_range":{"low":low["value"],"high":high["value"],"currency":"CNY"},
    "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY",
        "model_as_of":data["cutoff"],"base_case_distributions_per_share":low["distributions"],
        "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["terminal"],"high":high["terminal"]}}},
    "scenarios":{"currency":"CNY",**values,"horizon_note":data["scenario_note"]},
    "scenarios_detail":cases,"diluted_shares_100m":shares,"net_cash_bridge_100m":round(opening,4),
    "transition_dcf":{key:transition_value(cases[key], data["scenarios"][key], check)
                      for key,check in data["crosscheck"].items()}
}
(folder / "2026-Q3-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")
