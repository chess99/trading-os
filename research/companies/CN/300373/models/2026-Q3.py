"""运行 python 2026-Q3.py，在源码目录生成简明 JSON。金额单位为亿元。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def present(distributions, terminal, rate):
    return sum(c / (1 + rate) ** i for i, c in enumerate(distributions, 1)) + terminal / (1 + rate) ** len(distributions)


def opening(facts, policy):
    borrowings = sum(facts[k] for k in ("short_debt", "current_long_debt", "long_debt", "lease_debt"))
    private_debt = facts["h1_private_debt"] + facts["other_payables"] - facts["h1_other_payables"]
    paid = facts["shares"] * facts["dividend_paid_per_share"]
    cash = facts["cash_equivalents"] + facts["trading_assets"] - policy["operating_cash_buffer"]
    liquid = cash - borrowings - private_debt - facts["minority_book"] - paid - facts["fund_commitment"]
    return liquid, paid


def project(facts, policy, case):
    balance, paid = opening(facts, policy)
    credit_limit = max(0, -balance)
    parent_retained = facts["parent_h1_retained"] - paid
    sales = facts["nine_month_revenue"] + facts["q4_revenue_estimate"]
    years = []
    for growth, margin, capex_rate, wc_drain in zip(case["sales_growth"], case["operating_after_tax_margin"], case["capex_ratio"], case["wc_drain"], strict=True):
        previous_sales = sales
        sales *= 1 + growth
        nopat = sales * margin
        fixed = sales * (capex_rate - case["depreciation_ratio"])
        # 下行情景不预收库存变现款，应收滞后回款在单独资金占用中预算。
        working = max(0, sales - previous_sales) * case["wc_ratio"] + wc_drain
        free = nopat - fixed - working
        interest = balance * (case["financing_rate"] if balance < 0 else policy["cash_yield"])
        available = balance + interest + free
        parent_retained += nopat * policy["parent_profit_share"]
        cash_budget = max(0, free + interest) * case["cash_payout_limit"]
        payout = max(0, min(nopat * case["payout"], cash_budget, available + credit_limit, parent_retained))
        new_balance = available - payout
        assert isclose(new_balance - balance, free + interest - payout, abs_tol=1e-9)
        assert payout <= max(0, free + interest) + 1e-9
        parent_retained -= payout
        balance = new_balance
        years.append(dict(revenue=sales, nopat=nopat, gross_capex=sales * capex_rate, net_fixed=fixed,
                          working=working, free=free, dividend=payout, balance=balance))
    return years


def value(years, shares, late_assets, rate, multiple):
    terminal = (years[-1]["nopat"] * multiple + late_assets + years[-1]["balance"]) / shares
    distributions = [y["dividend"] / shares for y in years]
    price = present(distributions, terminal, rate)
    return price, terminal, terminal / (1 + rate) ** len(years) / price


def calculate(data):
    f, p, cases = data["facts"], data["assumptions"], data["cases"]
    late_assets = f["other_financial_assets"] * p["fair_asset_recovery"]
    anchors, checks = {}, {}
    for name, case in cases.items():
        projection = project(f, p, case)
        for i, multiple in enumerate(case.get("terminal_multiples", [case.get("terminal_multiple")])):
            key = ("base_low", "base_high")[i] if name == "base" else name
            v, terminal, share = value(projection, f["shares"], late_assets, case["discount"], multiple)
            anchors[key] = round(v, 2)
            checks[key] = dict(terminal_per_share=round(terminal, 2), terminal_present_share=round(share, 4),
                               minimum_net_cash=round(min(opening(f, p)[0], *(y["balance"] for y in projection)), 3),
                               revenue_y5=round(projection[-1]["revenue"], 2), nopat_y5=round(projection[-1]["nopat"], 2))
    base = cases["base"]
    years = project(f, p, base)
    steady_multiple = (1 + base["steady_growth"]) * (1 - base["steady_growth"] / base["steady_roic"]) / (base["discount"] - base["steady_growth"])
    # 第六至十年增量利润由过渡期资本回报率约束，再计稳态再投资。
    future_cash = [year["free"] for year in years]
    sales, nopat = years[-1]["revenue"], years[-1]["nopat"]
    for growth, margin, roic in zip(base["transition_growth"], base["transition_margin"], base["transition_roic"], strict=True):
        sales *= 1 + growth
        next_nopat = sales * margin
        reinvestment = max(0, next_nopat - nopat) / roic
        future_cash.append(next_nopat - reinvestment)
        nopat = next_nopat
    alt_ev = present(future_cash, nopat * steady_multiple, base["discount"])
    alt = (alt_ev + opening(f, p)[0] + late_assets / (1 + base["discount"]) ** 5) / f["shares"]
    paired_capital = sum(y["net_fixed"] + y["working"] for y in years[1:])
    assert paired_capital > 0
    ordered = [anchors[k] for k in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")]
    assert min(ordered) >= 0 and ordered == sorted(ordered)
    returns = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="CNY", model_as_of=data["cutoff"],
                   base_case_distributions_per_share=[round(y["dividend"] / f["shares"], 4) for y in years],
                   base_case_terminal_equity_value_range_per_share={"year_5": {k: checks["base_"+k]["terminal_per_share"] for k in ("low","high")}})
    sensitivity = {}
    for move in (-0.01, 0.01):
        varied = dict(base, operating_after_tax_margin=[x + move for x in base["operating_after_tax_margin"]])
        v = value(project(f, p, varied), f["shares"], late_assets, base["discount"], sum(base["terminal_multiples"])/2)[0]
        sensitivity[str(move)] = round(v, 2)
    return dict(symbol=data["symbol"], report_period=data["period"], value_range=dict(low=anchors["base_low"], high=anchors["base_high"], currency="CNY"),
                return_model=returns, scenarios=dict(currency="CNY", **anchors,
                  horizon_note="五年经营路径与第五年末经营价值按各情景现金、再投资和融资成本折现，均为除息后每股现值。"),
                alternate_dcf_per_share=round(alt,2), alternate_operating_multiple=round(steady_multiple,2),
                initial_net_financial_claim=round(opening(f,p)[0],3), terminal_other_assets=round(late_assets,3),
                margin_sensitivity=sensitivity, scenarios_detail=checks,
                incremental_return_y1_to_y5=round((years[-1]["nopat"]-years[0]["nopat"])/paired_capital,4),
                base_five_years=[{k:round(v,3) for k,v in y.items()} for y in years])


if __name__ == "__main__":
    # 一年、零利率，2亿股分红2亿元、期末经营利润2亿元乘10倍加4亿元现金，每股1+12=13元。
    simple = [{"nopat": 2, "balance": 4, "dividend": 2}]
    assert value(simple, 2, 0, 0, 10)[:2] == (13, 12)
    inputs = json.loads((ROOT / "2026-Q3-input.json").read_text())
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(calculate(inputs), ensure_ascii=False, indent=2) + "\n")
