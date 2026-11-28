"""京东普通股五年现金分配与剩余索取权。运行 python 2026-Q3.py 重建相邻输出。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "2026-Q3-input.json").read_text())
F = DATA["facts"]
A = DATA["shared_assumptions"]
FX = F["hkd_cny"]
PARENT = 1 - F["noncontrolling_equity"] / F["total_equity"]


def present(dividends, terminal, rate):
    return sum(cash / (1 + rate) ** n for n, cash in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def equity_bridge(path, convert=True):
    # Converted note is already in diluted units. Leases run through operating expense.
    debt = F["short_debt"] + F["senior_current"] + F["senior_long"] + F["other_long_debt"]
    if convert:
        debt -= F["convertible_usd"] * F["usd_cny_at_quarter"]
    consideration = F["acquisition_eur"] * F["eur_cny"]
    liquidity = F["cash"] + F["short_investments"] - debt - A["operating_cash_reserve"]
    parent_cash = liquidity * PARENT - consideration
    realizable_assets = (F["long_investments"] + F["associates"]) * PARENT * path["asset_recovery"]
    realizable_assets += consideration * path["ceconomy_recovery"]
    return parent_cash, realizable_assets


def price(path, terminal_multiple=None, convert=True):
    opening_cash, assets = equity_bridge(path, convert)
    cash = opening_cash
    shares = F["fully_diluted"]
    if not convert:
        shares -= F["convertible_usd"] / 1000 * F["initial_ads_per_1000"] * 2
    revenue = F["retail_sales_fy25"] - F["retail_sales_9m25"] + F["retail_sales_9m26"]
    dividends, free_flows, net_cancellations, budgets, parent_earnings = [], [], [], [], []
    for yr, growth in enumerate(path["retail_growth"]):
        revenue *= 1 + growth
        ebit = revenue * path["retail_margin"][yr] + path["logistics"][yr] + path["new"][yr]
        pre_award_profit = (ebit - A["other_corporate_cash_cost"]) * (1 - A["tax"])
        pre_award_profit -= A["initial_minority_operating_earnings"] * (1 + A["minority_growth"]) ** yr
        award = F["equity_awards_9m"] * 4 / 3 * (1 + A["noncash_awards_growth"]) ** yr
        flow = pre_award_profit - path["net_capital"][yr]
        opening_shares = shares
        settlement = A["award_settlement_cny_start"] * (1 + A["annual_award_price_growth"]) ** yr
        available = cash + flow
        dividend = min(A["annual_ordinary_dividends"][yr] * path["owner_dividend_factor"], max(0., available))
        repurchase = min(path["repurchases"][yr], max(0., available - dividend))
        cash = available - dividend - repurchase
        shares += (award - repurchase) / settlement
        assert cash >= 0 and shares > 0
        assert isclose(cash + dividend + repurchase, available)
        assert isclose(shares - opening_shares, (award - repurchase) / settlement, abs_tol=1e-12)
        # Dividend record precedes current-year grant/repurchase settlement.
        dividends.append(dividend / opening_shares / FX)
        free_flows.append(flow)
        net_cancellations.append((repurchase - award) / settlement)
        budgets.append(repurchase)
        parent_earnings.append(pre_award_profit - award)

    rate, growth = path["discount"], path["terminal_growth"]
    assert path["terminal_roic"] > growth and rate > growth
    if terminal_multiple is None:
        normalized_flow = parent_earnings[-1] * (1 + growth) * (1 - growth / path["terminal_roic"])
        operating_value = normalized_flow / (rate - growth)
    else:
        operating_value = parent_earnings[-1] * terminal_multiple
    terminal = (operating_value + cash + assets) / shares / FX
    value = present(dividends, terminal, rate)
    return dict(value=value, terminal=terminal, dividends=dividends, terminal_share=terminal / (1+rate)**5 / value,
                cash_open=opening_cash, cash_close=cash, nonoperating_assets=assets, shares_y5=shares,
                cash_after_growth_capital=free_flows, normalized_profit=parent_earnings,
                net_cancellations=net_cancellations, repurchases=budgets)


def calculate():
    paths = {name: price(path) for name, path in DATA["paths"].items()}
    base = DATA["paths"]["base"]
    edges = {k: price(base | overrides) for k, overrides in DATA["base_edges"].items()}
    low, high = (round(edges[k]["value"], 2) for k in ("low","high"))
    value_range = dict(currency="HKD", low=low, high=high)
    scenario = dict(structural_bear=round(paths["structural_bear"]["value"], 2),
                    cyclical_bear=round(paths["cyclical_bear"]["value"], 2), base_low=low, base_high=high,
                    bull=round(paths["bull"]["value"], 2))
    assert list(scenario.values()) == sorted(scenario.values()) and scenario["structural_bear"] >= 0
    single = paths["base"]
    returns = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD", model_as_of=DATA["as_of"],
                   base_case_distributions_per_share=[round(x, 4) for x in single["dividends"]],
                   base_case_terminal_equity_value_range_per_share={"year_5": {k: round(v["terminal"], 4) for k,v in edges.items()}})
    # 100 today -> 10 at year one and 110 at year two at 10%.
    assert isclose(present([10, 10], 100, .10), 100)
    check = [round(price(base, m)["value"], 2) for m in A["terminal_multiple_check"]]
    # Year-one cash-equivalent net cancellation per opening fully diluted share; no subsequent unapproved budget assumed.
    net_per_share = single["net_cancellations"][0] * A["award_settlement_cny_start"] / F["fully_diluted"] / FX
    return dict(symbol=DATA["symbol"], report_period=DATA["report_period"], value_range=value_range, return_model=returns,
                scenarios=scenario, normalized_multiple_check=check, net_buyback_y1_per_share=round(net_per_share, 4),
                base={k: [round(i, 4) for i in v] if isinstance(v,list) else round(v,4) for k,v in single.items()},
                terminal_weight={k:round(v["terminal_share"],4) for k,v in edges.items()},
                sensitivity={ "margin_minus_one_point":round(price(base | {"retail_margin":[x-.01 for x in base["retail_margin"]]})["value"],2),
                              "put_settlement":round(price(base, convert=False)["value"],2),
                              "no_buyback":round(price(base | {"repurchases":[0]*5})["value"],2),
                              "extra_annual_capital_4":round(price(base | {"net_capital":[n+4 for n in base["net_capital"]]})["value"],2),
                              "loss_persists_at_20":round(price(base | {"new":[min(-20,n) for n in base["new"]]})["value"],2)})


if __name__ == "__main__":
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(calculate(), ensure_ascii=False, indent=2) + "\n")
