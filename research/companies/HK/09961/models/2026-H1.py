"""运行 python 2026-H1.py，在同目录重建输出。金额十亿元人民币，股数十亿股。"""
import json
from math import isclose
from pathlib import Path

folder = Path(__file__).resolve().parent
data = json.loads((folder / "2026-H1-input.json").read_text())
facts, assumptions = data["facts"], data["assumptions"]


def cash_and_investments(f, a, recovery):
    cash = f["cash_with_restricted"] + f["short_investments"] + f["term_deposits"]
    claims = sum(f[k] for k in ("prior_restricted_cash", "customer_advances", "current_debt",
                                 "long_debt", "fine", "confiscation", "hotel_refunds", "nci", "mezzanine"))
    investments = (f["investments_including_term"] - f["term_deposits"]) * recovery
    return cash - claims - a["acquisition_reserve"], investments


def equity_step(cash, shares, operating_cash, buyback, award_value, execution_price, dps, cash_yield):
    dividend = shares * dps
    end_cash = cash * (1 + cash_yield) + operating_cash - dividend - buyback
    end_shares = shares + (award_value - buyback) / execution_price
    assert isclose(end_cash + dividend + buyback, cash * (1 + cash_yield) + operating_cash)
    assert isclose((shares - end_shares) * execution_price, buyback - award_value, abs_tol=1e-10)
    assert end_shares > 0 and end_cash >= 0
    return end_cash, end_shares


def value(path, margin_shift=0):
    f, a = facts, assumptions
    fx, rate = f["cny_per_hkd"], path["rate"]
    cash, portfolio = cash_and_investments(f, a, path["portfolio_recovery"])
    opening_bridge = cash + portfolio
    shares = f["diluted_profit_basis"]
    sales = f["annual_sales"] + f["current_h1_sales"] - f["prior_h1_sales"]
    div_pv = 0
    snapshots = []
    for year, (growth, margin, dps) in enumerate(zip(path["growth"], path["margin"], path["dividend_hkd"]), 1):
        previous = sales
        sales *= 1 + growth
        earnings = sales * (margin + margin_shift) * (1 - a["tax_rate"])
        awards = sales * a["new_award_to_sales"]
        net_capex = sales * a["net_capex_to_sales"]
        wc = max(0, sales - previous) * a["working_capital_to_incremental_sales"]
        operating_cash = earnings + awards - net_capex - wc
        buyback = operating_cash * path["buyback"]
        execution = a["execution_price_cny"] * (1 + a["execution_price_growth"]) ** (year - 1)
        opening_shares = shares
        cash, shares = equity_step(cash, shares, operating_cash, buyback, awards, execution,
                                   dps * fx, a["treasury_yield"])
        div_pv += dps / (1 + rate) ** year
        snapshots.append(dict(sales=sales, earnings=earnings, cash=cash, shares=shares,
                              gross_buyback=buyback, award_value=awards, net_capex=net_capex, wc=wc,
                              net_shares=opening_shares-shares, net_buyback_hkd=(buyback-awards)/opening_shares/fx))
    g = path["g"]
    steady_cash = earnings * (1 + g) * (1 - g / path["roic"])
    # 稳态按含完整激励费用的利润估现金，视同现金补偿，未再增发或计增厚。
    terminal = (cash + portfolio + steady_cash / (rate - g)) / shares / fx
    multiple_terminal = (cash + portfolio + earnings * path["multiple"]) / shares / fx
    terminal_pv = terminal / (1 + rate) ** 5
    fair = div_pv + terminal_pv
    return dict(value=round(fair, 2), terminal=round(terminal, 2),
                secondary=round(div_pv + multiple_terminal / (1 + rate) ** 5, 2),
                terminal_pv_share=round(terminal_pv/fair, 4), opening_bridge=round(opening_bridge, 3),
                years=[{k:round(v, 5) for k,v in s.items()} for s in (snapshots[0],snapshots[-1])])


assert equity_step(10, 2, 4, 2, 1, 5, 0.5, 0) == (11, 1.8)
paths = data["paths"]
results = {k:value(p) for k,p in paths.items()}
anchors = {k:r["value"] for k,r in results.items()}
assert list(anchors.values()) == sorted(anchors.values())
assert paths["base_low"]["dividend_hkd"] == paths["base_high"]["dividend_hkd"]
output = dict(symbol=data["symbol"], report_period=data["report_period"],
              value_range=dict(low=anchors["base_low"], high=anchors["base_high"], currency="HKD"),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                                model_as_of=data["as_of"], base_case_distributions_per_share=paths["base_low"]["dividend_hkd"],
                                base_case_terminal_equity_value_range_per_share={"year_5":{
                                    "low":results["base_low"]["terminal"], "high":results["base_high"]["terminal"]}}),
              scenarios=anchors, details=results, sensitivity_margin_minus_2pp={
                  k:value(paths[k], -0.02)["value"] for k in ("base_low","base_high")})
(folder / "2026-H1-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
