"""在输入文件所在目录运行，结果写入同目录。金额和股数分别以百万元、百万股计。"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def equity_bridge(items):
    residual = items["relocation_proceeds"] - items["relocation_costs_in_receivables"]
    return (
        items["cash_equivalents"] - items["operating_cash"] - items["short_debt"]
        - items["current_maturities"] - items["long_debt"] - items["lease_debt"]
        - items["noncontrolling_interest"] - residual
    )


def value(data, case):
    revenue = data["revenue_ttm"]
    bridge = equity_bridge(data["bridge"])
    cash_pv = 0.0
    capex_sum = 0.0
    cumulative_fcf = 0.0
    max_funding = 0.0
    for year, floor in enumerate(data["construction_budget_floor_years_1_to_5"], 1):
        change = revenue * case["growth"]
        revenue += change
        margin = data["starting_ebit_margin"] + year / 5 * (case["ending_ebit_margin"] - data["starting_ebit_margin"])
        nopat = revenue * margin * (1 - data["tax"])
        capex = max(floor, revenue * case["capex_ratio"])
        depreciation = revenue * data["da_to_revenue"]
        reinvestment = capex - depreciation + change * case["working_capital_ratio"]
        fcf = nopat - reinvestment
        cumulative_fcf += fcf
        max_funding = max(max_funding, -cumulative_fcf)
        capex_sum += capex
        discount = (1 + case["wacc"]) ** year
        cash_pv += fcf / discount
        assert math.isclose(fcf + reinvestment, nopat, abs_tol=1e-10)
    assert capex_sum >= data["contracted_construction_h1"]
    operating_terminal = nopat * case["exit_nopat_multiple"]
    growth = case["perpetual_growth"]
    cash_terminal = nopat * (1 + growth) * (1 - growth / case["mature_roic"]) / (case["wacc"] - growth)
    primary = (cash_pv + operating_terminal / discount + bridge) / data["shares"]
    secondary = (cash_pv + cash_terminal / discount + bridge) / data["shares"]
    return {
        "value": round(primary, 2), "fcf_value": round(secondary, 2),
        "terminal_pv_share_of_operating_value": round(operating_terminal / discount / (cash_pv + operating_terminal / discount), 4),
        "y5_revenue_m": round(revenue, 1), "y5_nopat_m": round(nopat, 1),
        "capex_y1_to_y5_m": round(capex_sum, 1), "peak_cumulative_funding_m": round(max_funding, 1),
        "bridge_m": round(bridge, 2)
    }


def main():
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    # 无增长、无净投资，10%折现的永续每年10元恰值100元，两条路径应独立复现。
    hand = dict(data, revenue_ttm=100, shares=1, starting_ebit_margin=0.1, tax=0,
                bridge=dict.fromkeys(data["bridge"], 0), contracted_construction_h1=0,
                construction_budget_floor_years_1_to_5=[0]*5, da_to_revenue=0)
    flat = dict(growth=0, ending_ebit_margin=0.1, capex_ratio=0, working_capital_ratio=0,
                wacc=0.1, exit_nopat_multiple=10, perpetual_growth=0, mature_roic=0.1)
    assert value(hand, flat)["value"] == value(hand, flat)["fcf_value"] == 100
    paths = {name: value(data, case) for name, case in data["scenarios"].items()}
    anchors = {name: path["value"] for name, path in paths.items()}
    assert 0 <= anchors["structural_bear"] <= anchors["cyclical_bear"] <= anchors["base_low"] <= anchors["base_high"] <= anchors["bull"]
    result = {
        "symbol": data["symbol"], "report_period": data["report_period"],
        "value_range": {"currency":"CNY", "low":anchors["base_low"], "high":anchors["base_high"]},
        "return_model": None,
        "scenarios": {**anchors, "currency":"CNY", "horizon_note":"五年经营路径折现至资料截止日，每股人民币。"},
        "paths": paths,
    }
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
