"""独立模型；单位：亿元、亿股、元/股。所有预测是研究预算。"""

import json
from pathlib import Path

P = Path(__file__).parent
shares = 12.50081601
assets = {
    "cash": 535.1879897908,
    "interbank": 1410.8415812401,
    "reverse_repo": 4.0649127208,
    "current_bonds": 17.9810644556,
    "loans": 4.1628717392,
    "bonds": 11.0670730424,
    "other_bonds": 24.1488526151,
    "funds": 39.1751057637,
}
opening = sum(assets.values()) - 254.2631666817 - 108.4275775486 - 2.4368486806 - 150
# June -> Oct18 110-day budget: operating earnings 225; net investment 20; finance 2.5.
# No post-June cash distribution was identified in the reviewed sources.
stub = 225 - 20 + 2.5
capital = opening + stub
fund = assets["funds"]
rows = []
mt, series = 1560.0, 240.0
capex = [75, 80, 80, 75, 65, 45, 40, 38, 38, 38]
da = [25, 27, 29, 31, 33, 35, 36, 37, 38, 39]
wc = [22, 24, 25, 26, 27, 26, 25, 24, 24, 24]
for y in range(1, 11):
    if y > 1:
        mt *= 1.04 if y <= 5 else 1.03
        series *= 1.03 if y <= 5 else 1.02
    op = mt * 0.50 + series * 0.30
    reinvest = capex[y - 1] - da[y - 1] + wc[y - 1]
    fin = (capital - fund) * 0.005
    earnings = op + fin
    div = (840 if y == 1 else rows[-1]["earnings"]) * 0.80
    call = 30 if y <= 2 else 0
    fund += call
    capital += op + fin - reinvest - div
    rows.append(
        dict(
            year=y,
            mt=mt,
            series=series,
            revenue=mt + series,
            op=op,
            financial_income=fin,
            earnings=earnings,
            capex=capex[y - 1],
            da=da[y - 1],
            wc=wc[y - 1],
            reinvestment=reinvest,
            fcf=op - reinvest,
            dividend=div,
            dps=div / shares,
            fund_call=call,
            fund=fund,
            financial_assets=capital,
            liquid_financial_assets=capital - fund,
        )
    )


# Primary: dividends received years1-5 + year5 value.
# Year5 business value: FCF years6-10 plus year10 continuing value.
# Terminal reinvestment = growth * operating earnings / incremental operating ROIC; maintenance=DA.
def value(r, g, opening_adjust=0, incremental_roic=0.35):
    # Capital adjustment changes terminal asset value while keeping operations fixed.
    terminal_cash = rows[9]["op"] * (1 + g) * (1 - g / incremental_roic)
    tail10 = terminal_cash / (r - g)
    business5 = sum(x["fcf"] / (1 + r) ** (x["year"] - 5) for x in rows[5:]) + tail10 / (1 + r) ** 5
    terminal5 = business5 + rows[4]["financial_assets"] + opening_adjust
    pv_div = sum(x["dividend"] / (1 + r) ** x["year"] for x in rows[:5])
    present = (pv_div + terminal5 / (1 + r) ** 5) / shares
    return dict(
        r=r,
        g=g,
        current_value=present,
        terminal5=terminal5 / shares,
        business5=business5 / shares,
        financial5=rows[4]["financial_assets"] / shares,
        year10_perpetuity_pv_share=tail10 / (1 + r) ** 10 / shares,
        terminal5_pv_share=terminal5 / (1 + r) ** 5 / shares,
        terminal_weight=(terminal5 / (1 + r) ** 5) / (present * shares),
    )


core = [value(0.095, 0.02), value(0.085, 0.025)]
# Secondary normalized operating PE + same net financial assets at valuation date.
secondary = [
    (rows[0]["op"] * k + capital0) / shares
    for k, capital0 in [(15, opening + stub), (18, opening + stub)]
]


# Distinct scenarios: full capital/distribution projection, not arbitrary valuation haircuts.
def scenario(kind, r, g):
    a = opening + stub
    f = assets["funds"]
    out = []
    op0 = rows[0]["op"]
    for i, b in enumerate(rows):
        y = i + 1
        if kind == "cycle":
            factors = [0.82, 0.85, 0.94, 1, 1, 1, 1, 1, 1, 1]
            op = b["op"] * factors[i]
            inv = b["reinvestment"] + (20 if y <= 2 else -10 if y in [3, 4] else 0)
        elif kind == "structural":
            op = op0 * 0.70 * (1.00 if y <= 3 else 1.01 ** (y - 3))
            inv = 50 if y <= 5 else 20
        else:
            op = op0 * 1.06**i
            inv = b["reinvestment"] + 15
        fi = (a - f) * 0.005
        d = 0.8 * (840 if y == 1 else out[-1]["earnings"])
        f += 30 if y <= 2 else 0
        a += op + fi - inv - d
        out.append(dict(year=y, op=op, earnings=op + fi, fcf=op - inv, div=d, assets=a))
    tv10 = out[-1]["op"] * (1 + g) * (1 - g / 0.35) / (r - g)
    b5 = sum(x["fcf"] / (1 + r) ** (x["year"] - 5) for x in out[5:]) + tv10 / (1 + r) ** 5
    return (
        sum(x["div"] / (1 + r) ** x["year"] for x in out[:5])
        + (b5 + out[4]["assets"]) / (1 + r) ** 5
    ) / shares


out = {
    "units": "亿元、亿股、元/股",
    "shares": shares,
    "financial_assets_items": assets,
    "financial_asset_sum": sum(assets.values()),
    "june_net_financial_after_reserve": opening,
    "stub_net_addition": stub,
    "oct_opening_financial": opening + stub,
    "rows": rows,
    "core": core,
    "secondary": secondary,
    "sensitivity": [{**value(r, g)} for r in [0.085, 0.09, 0.095] for g in [0.015, 0.02, 0.025]],
    "scenarios": {
        "cycle": scenario("cycle", 0.09, 0.02),
        "structural": scenario("structural", 0.10, 0.01),
        "optimistic": scenario("optimistic", 0.085, 0.03),
    },
    "clean_cfo_h1": 706.9075011906 - 73.8300456378 - 218.9545228418 - 11.704248432 - 9,
    "incremental_roic_y1_y5": (rows[4]["op"] - rows[0]["op"])
    / sum(x["reinvestment"] for x in rows[1:5]),
}
assert all(x["dividend"] < x["fcf"] + x["financial_income"] for x in rows[:5])
assert (
    abs(
        rows[4]["financial_assets"]
        - (
            (opening + stub)
            + sum(x["fcf"] + x["financial_income"] - x["dividend"] for x in rows[:5])
        )
    )
    < 1e-8
)


# Independent operating sensitivities with all distributions and retained assets recomputed.
def alternative(mt_growth=0.04, mt_margin=0.50, initial_adjust=0):
    a = opening + stub + initial_adjust
    f = assets["funds"]
    q = 1560.0
    s = 240.0
    xx = []
    for i, b in enumerate(rows):
        y = i + 1
        if y > 1:
            q *= 1 + (mt_growth if y <= 5 else 0.03)
            s *= 1 + (0.03 if y <= 5 else 0.02)
        op = q * mt_margin + s * 0.30
        fi = (a - f) * 0.005
        d = 0.8 * (840 if y == 1 else xx[-1]["earnings"])
        f += 30 if y <= 2 else 0
        a += op + fi - b["reinvestment"] - d
        xx.append(dict(y=y, op=op, earnings=op + fi, fcf=op - b["reinvestment"], div=d, assets=a))
    r = 0.09
    g = 0.0225
    t10 = xx[-1]["op"] * (1 + g) * (1 - g / 0.35) / (r - g)
    t5 = (
        sum(z["fcf"] / (1 + r) ** (z["y"] - 5) for z in xx[5:])
        + t10 / (1 + r) ** 5
        + xx[4]["assets"]
    )
    return (sum(z["div"] / (1 + r) ** z["y"] for z in xx[:5]) + t5 / (1 + r) ** 5) / shares


out["operating_sensitivities"] = {
    "central": alternative(),
    "mt_growth_2_5pct": alternative(mt_growth=0.025),
    "mt_margin_48pct": alternative(mt_margin=0.48),
    "zero_stub": alternative(initial_adjust=-stub),
    "fund_writeoff_at5": value(0.09, 0.0225, opening_adjust=-rows[4]["fund"])["current_value"],
    "terminal_incremental_roic20pct": value(0.09, 0.0225, incremental_roic=0.20)["current_value"],
    "financial_extra5yr_lock": value(
        0.09, 0.0225, opening_adjust=rows[4]["financial_assets"] * ((1.005 / 1.09) ** 5 - 1)
    )["current_value"],
}
# Constant perpetuity identity: splitting out the first 5 cash flows preserves PV.
r = 0.09
c = 100
assert abs(sum(c / (1 + r) ** y for y in range(1, 6)) + (c / r) / (1 + r) ** 5 - c / r) < 1e-8

(P / "2026-H1-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(
    json.dumps(
        {k: v for k, v in out.items() if k not in ["rows", "sensitivity"]},
        ensure_ascii=False,
        indent=2,
    )
)
print(
    "rows",
    [
        (
            x["year"],
            round(x["revenue"], 2),
            round(x["op"], 2),
            round(x["dps"], 2),
            round(x["financial_assets"], 2),
        )
        for x in rows[:5]
    ],
)
