"""在任意目录运行 python 2026-Q3.py，可在本文件旁重建输出。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def present(distributions, terminal, rate):
    return sum(dividend / (1 + rate) ** year for year, dividend in enumerate(distributions, 1)) + terminal / (1 + rate) ** len(distributions)


def simulate(data, parameters):
    o = data["ownership"]
    b = data["operating_basis"]
    p = dict(zip(data["scenario_columns"], parameters, strict=True))
    shares = o["issued_shares"] + o["deal_shares"] + o["incremental_award_allowance"]
    revenue = b["revenue_2025"] + b["revenue_9m_2026"] - b["revenue_9m_2025"] + b["target_start_revenue"]
    start_margin = b["normalized_start_nopat_margin"]
    cash = o["cash_equivalents"] - sum(o[k] for k in ("cash_reserve", "debt_due_short", "debt_long", "lease_long", "other_long_payable", "interim_dividend_paid", "repurchase_paid", "cash_consideration_and_costs"))
    financial_bridge = sum(o["financial_assets_and_associates"]) * p["financial_asset_recovery"] - o["deferred_tax_liability"] - o["minorities_book"]
    start_cash = cash
    ds = [value * p["dividend_scale"] for value in data["base_dividends_per_share"]]
    flows, capital, nopats = [], [], []
    minimum_cash = cash
    for year, dividend in enumerate(ds, 1):
        increase = revenue * p["growth"]
        revenue += increase
        margin = start_margin + (p["end_nopat_margin"] - start_margin) * year / 5
        nopat = revenue * margin
        capital.append(increase * p["incremental_working_capital_per_revenue"] + max(p["growth_net_plant_capex_floor"], increase * p["incremental_net_plant_per_revenue"]))
        inventory_loss = b["inventory"] * p["inventory_loss_cash_equivalent"] if year == 1 else 0
        free_cash = nopat - capital[-1] - inventory_loss
        flows.append(free_cash)
        nopats.append(nopat)
        cash = cash * (1 + o["cash_yield_after_tax"]) + free_cash - dividend * shares
        minimum_cash = min(minimum_cash, cash)
    assert minimum_cash >= 0
    terminal = (nopat * p["terminal_operating_multiple"] + cash + financial_bridge) / shares
    required = p["equity_discount"]
    primary = present(ds, terminal, required)
    year5 = revenue
    year5_nopat = nopat
    for offset in range(1, 6):
        growth = p["growth"] + (p["year_10_growth"] - p["growth"]) * offset / 5
        increase = revenue * growth
        revenue += increase
        margin = p["end_nopat_margin"] + (p["year_10_margin"] - p["end_nopat_margin"]) * offset / 5
        nopat = revenue * margin
        investment = increase * (p["incremental_working_capital_per_revenue"] + p["incremental_net_plant_per_revenue"])
        flows.append(nopat - investment)
    g = p["year_10_growth"]
    assert g < required and g < p["mature_return_on_incremental_capital"]
    ongoing = nopat * (1 + g) * (1 - g / p["mature_return_on_incremental_capital"]) / (required - g)
    dcf = (present(flows, ongoing, required) + start_cash + financial_bridge) / shares
    return {k: round(v, 4) for k, v in {
        "value": primary, "fcff_dcf": dcf, "shares": shares, "year5_revenue": year5, "year5_nopat": year5_nopat,
        "year5_equity_per_share": terminal, "year5_excess_cash": cash, "opening_liquid_surplus": start_cash,
        "opening_equity_bridge": start_cash + financial_bridge, "year5_terminal_pv_weight": terminal / (1+required)**5 / primary,
        "year1_to_5_incremental_return": (nopats[-1] - nopats[0]) / sum(capital[1:]), "year1_to_5_capital": sum(capital),
        "minimum_liquid_surplus": minimum_cash
    }.items()}


def main():
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    assert isclose(present([1, 1], 100, 0), 102)
    assert isclose(present([0, 11], 110, 0.1), 100)
    rows = {name: simulate(data, p) for name, p in data["cases"].items()}
    anchors = {name: round(row["value"], 2) for name, row in rows.items()}
    assert list(anchors.values()) == sorted(anchors.values()) and all(v > 0 for v in anchors.values())
    result = {"symbol": data["symbol"], "report_period": data["report_period"],
              "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "CNY"},
              "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["cutoff"],
                               "base_case_distributions_per_share": data["base_dividends_per_share"],
                               "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(rows["base_low"]["year5_equity_per_share"], 2), "high": round(rows["base_high"]["year5_equity_per_share"], 2)}}},
              "anchors": anchors, "calculations": rows}
    for case in ("base_low", "base_high"):
        index = "low" if case == "base_low" else "high"
        model = result["return_model"]
        expected = present(model["base_case_distributions_per_share"], model["base_case_terminal_equity_value_range_per_share"]["year_5"][index], data["cases"][case][8])
        assert abs(expected - anchors[case]) < 0.011
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
