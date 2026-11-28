"""在本文件旁提供 2026-Q3-input.json，运行 python 2026-Q3.py 生成结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def present(distributions, terminal, rate):
    return sum(amount / (1 + rate) ** year for year, amount in enumerate(distributions, 1)) + terminal / (1 + rate) ** len(distributions)


def evaluate(f, a, case):
    shares = f["issued"]
    deposits = f["other_current_assets"] * f["h1_deposit"] / f["h1_other_current"]
    debts = f["short_debt"] + f["current_maturities"] + f["leases"] + f["deferred_tax_liabilities"]
    opening = (f["cash_equivalents"] + f["trading_assets"] * case["liquid_recovery"]
               + deposits + f["associate_book"] * case["associate_recovery"]
               - debts - a["operating_cash_buffer"])
    sales_before = f["revenue_2025"] - f["revenue_2025_9m"] + f["revenue_2026_9m"]
    end_sales = case["mcu_units"] * case["mcu_asp"] + case["other_sales"] + case["own_flash"]
    distributions = case.get("payout", a["base_payout"])
    cash = opening
    rows = []
    for ix, dps in enumerate(distributions):
        sales = case["y1_sales"] + (end_sales - case["y1_sales"]) * ix / 4
        gross_margin = case["gm1"] + (case["gm5"] - case["gm1"]) * ix / 4
        pretax = sales * (gross_margin - case["rd"] - case["other_costs"])
        profit = pretax - max(pretax, 0) * a["tax"]
        working = max(sales - sales_before, 0) * case["wc"]
        fixed = sales * case["net_fixed"] + case["ipm"] * a["annual_ipm_split"][ix]
        reinvestment = working + fixed
        free = profit - reinvestment
        cash += free - dps * shares
        assert cash >= 0, "现有资金不足，需重新设计融资或支出"
        rows.append({"sales": sales, "profit": profit, "reinvestment": reinvestment,
                     "working_capital": working, "net_fixed_capital": fixed, "free": free})
        sales_before = sales
    assert isclose(cash + sum(distributions) * shares, opening + sum(row["free"] for row in rows))
    operations = rows[-1]["profit"] * case["multiple"]
    terminal = (cash + operations) / shares
    value = present(distributions, terminal, case["rate"])
    growth = case["perpetual_growth"]
    alternative_operations = rows[-1]["profit"] * (1 + growth) * (1 - growth / case["incremental_roc"]) / (case["rate"] - growth)
    alternative = present(distributions, (cash + alternative_operations) / shares, case["rate"])
    incremental = sum(row["reinvestment"] for row in rows[1:])
    return {"value": round(value, 2), "year_5_terminal": round(terminal, 2),
            "year_5_sales": round(end_sales, 2), "year_5_after_tax_operating_profit": round(rows[-1]["profit"], 3),
            "year_1_after_tax_operating_profit": round(rows[0]["profit"], 3),
            "opening_financial_value_net": round(opening, 3), "end_retained_financial_value": round(cash, 3),
            "five_year_free_cash": round(sum(row["free"] for row in rows), 3),
            "year_2_to_5_incremental_capital": round(incremental, 3),
            "incremental_operating_return": round((rows[-1]["profit"] - rows[0]["profit"]) / incremental, 4),
            "terminal_pv_fraction": round(terminal / (1 + case["rate"]) ** 5 / value, 4),
            "capitalized_free_cash_value": round(alternative, 2)}


def calculate(inputs):
    assert isclose(present([1, 1], 8, 0), 10)
    assert isclose(present([0], 11, 0.1), 10)
    facts, assumptions = inputs["facts"], inputs["assumptions"]
    assert isclose(sum(assumptions["annual_ipm_split"]), 1)
    assert 0 < facts["issued"] - facts["treasury"] <= facts["issued"]
    cases = {k: evaluate(facts, assumptions, v) for k, v in inputs["cases"].items()}
    anchors = {k: v["value"] for k, v in cases.items()}
    ordered = [anchors[k] for k in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")]
    assert ordered == sorted(ordered) and min(ordered) >= 0
    horizon = "未来五年的MCU销量、单价与研发负担决定终态盈利。各情景逐年支付分红、负担 IPM 与营运资本后再折现，第五年仅较乐观路径纳入自主闪存实质收入。"
    terminal = {k: cases["base_" + k]["year_5_terminal"] for k in ("low", "high")}
    distribution = assumptions["base_payout"]
    for endpoint in ("low", "high"):
        rate = inputs["cases"]["base_" + endpoint]["rate"]
        assert abs(present(distribution, terminal[endpoint], rate) - anchors["base_" + endpoint]) < 0.01
    return {"symbol": inputs["symbol"], "report_period": inputs["report_period"],
            "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "CNY"},
            "scenarios": {"currency": "CNY", **anchors, "horizon_note": horizon},
            "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1",
                             "currency": "CNY", "model_as_of": inputs["cutoff"],
                             "base_case_distributions_per_share": distribution,
                             "base_case_terminal_equity_value_range_per_share": {"year_5": terminal}},
            "case_details": cases}


if __name__ == "__main__":
    result = calculate(json.loads((ROOT / "2026-Q3-input.json").read_text()))
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
