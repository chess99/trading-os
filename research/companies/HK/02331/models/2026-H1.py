"""在本目录运行 python3 2026-H1.py，重建每普通股税前港元结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def opening_position(f, a):
    repurchased = sum(units for units, _ in f["repurchases"])
    buyback_cost = sum(cost for _, cost in f["repurchases"]) * f["cny_per_hkd"]
    shares = f["issued"] - repurchased + f["converts"] + sum(f["options"])
    # 11月23日名册并未逐户披露，按发行股和可转换权益作付款预算上限。
    special = (f["issued"] + f["converts"]) * f["special_dividend_cny"]
    bank = f["cash"] + f["deposits_current"] + f["deposits_long"] - f["bank_debt"]
    uses = dict(interim=f["interim_dividend"], special=special, executed_buybacks=buyback_cost,
                liquidity=a["liquidity_buffer"], limited_partnership=f["lp_commitment_usd"] * f["cny_per_usd"],
                trustee_budget=f["trust_cap_hkd"] * f["cny_per_hkd"], outstanding_licence=f["licence_payable"])
    surplus = bank - sum(uses.values())
    assert isclose(surplus + sum(uses.values()), bank)
    return shares, surplus, uses


def present(dividends, terminal, rate):
    return sum(cash / (1 + rate)**year for year, cash in enumerate(dividends, 1)) + terminal / (1 + rate)**len(dividends)


def operating_path(revenue, p, surplus, committed, share_fx):
    cash = surplus
    dividends, profits, reinvestments, sales = [], [], [], []
    for year in range(5):
        growth = p["first_growth"] if year == 0 else p["following_growth"]
        old = revenue
        revenue *= 1 + growth
        profit = revenue * (p["initial_margin"] + year / 4 * (p["year5_margin"] - p["initial_margin"]))
        incremental = max(revenue - old, 0)
        net_investment = p["net_investment_floor"] + incremental * (p["growth_fixed_capital"] + p["growth_working_capital"])
        if year == 0:
            net_investment += committed + p["exceptional_cash_cost"]
        free = profit - net_investment
        dividend = min(profit * p["payout"], max(0, free))
        cash += free - dividend
        dividends.append(dividend)
        profits.append(profit)
        reinvestments.append(net_investment)
        sales.append(revenue)
    assert isclose(cash + sum(dividends), surplus + sum(profits) - sum(reinvestments))
    assert cash >= 0
    steady_g = p["perpetual_growth"]
    steady_cash = profits[-1] * (1 + steady_g) * (1 - steady_g / p["perpetual_roic"])
    distributions = [d / share_fx for d in dividends]
    endpoints = []
    for rate in p["discount_rates"]:
        assert rate > steady_g
        terminal = (cash + steady_cash / (rate - steady_g)) / share_fx
        value = present(distributions, terminal, rate)
        endpoints.append(dict(value=value, terminal=terminal, terminal_weight=terminal / (1 + rate)**5 / value))
    return dict(endpoints=endpoints, dividends=distributions, sales=sales, earnings=profits, invested=reinvestments, terminal_cash=cash)


def cross_check(f, a, cash, share_fx):
    series = f["years_fy25_fy24"]
    normalized = []
    for i in range(2):
        owner = series["operating_cash"][i] + series["equity_method_dividends"][i]
        for key in ("fixed_investment","investment_properties","intangibles","lease_cash","interest_paid"):
            owner -= series[key][i]
        normalized.append(owner)
    owner = sum(normalized) / 2 - a["secondary_working_capital_haircut"]
    return dict(historical=normalized, normalized=owner,
                values=[(cash + owner * multiple) / share_fx for multiple in a["owner_cash_multiple"]])


def main():
    d = json.loads((ROOT / "2026-H1-input.json").read_text())
    f, a = d["fact"], d["assumptions"]
    shares, cash, uses = opening_position(f, a)
    share_fx = shares * f["cny_per_hkd"]
    revenue = f["fy25_revenue"] + f["h126_revenue"] - f["h125_revenue"]
    paths = {k: operating_path(revenue, p, cash, f["committed_capex"], share_fx) for k, p in d["paths"].items()}
    def anchor(name, i=0):
        return round(paths[name]["endpoints"][i]["value"], 2)
    values = [anchor("structural_bear"), anchor("cyclical_bear"), anchor("base"), anchor("base", 1), anchor("bull")]
    assert sorted(values) == values
    base = paths["base"]
    terminal = {k: round(v["terminal"], 2) for k, v in zip(("low","high"),base["endpoints"])}
    holder = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD", model_as_of=d["as_of"],
                  base_case_distributions_per_share=[round(x,4) for x in base["dividends"]],
                  base_case_terminal_equity_value_range_per_share={"year_5":terminal})
    scenarios = dict(zip(("structural_bear","cyclical_bear","base_low","base_high","bull"), values))
    # 以经营利润率低一个百分点重估，其他条件不变。
    weaker = dict(d["paths"]["base"])
    weaker["initial_margin"] -= .01
    weaker["year5_margin"] -= .01
    lower_margin = operating_path(revenue, weaker, cash, f["committed_capex"], share_fx)
    out = dict(symbol=d["symbol"],report_period=d["report_period"],value_range=dict(low=values[2],high=values[3],currency="HKD"),
               return_model=holder, scenario_hkd=scenarios, opening_excess_cash=cash, cash_reservations=uses,
               fully_diluted_shares_bn=shares, paths=paths, secondary=cross_check(f,a,cash,share_fx),
               margin_minus_one_point=[round(x["value"],2) for x in lower_margin["endpoints"]])
    # 无增长、无留存、无起始现金，年收益1，资本成本10%，无论哪一年处置现值均为10。
    sample = dict(d["paths"]["base"], first_growth=0, following_growth=0, initial_margin=1, year5_margin=1,
                  net_investment_floor=0, exceptional_cash_cost=0, payout=1, perpetual_growth=0, discount_rates=[.1])
    assert isclose(operating_path(1, sample, 0, 0, 1)["endpoints"][0]["value"], 10)
    (ROOT/"2026-H1-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")

if __name__ == "__main__":
    main()
