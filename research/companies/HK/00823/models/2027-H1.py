"""运行 python 2027-H1.py，在同目录重建结果。币种为港元。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "2027-H1-input.json").read_text())


def discounted_cashflows(cash, terminal, rate):
    return sum(d / (1 + rate)**t for t, d in enumerate(cash, 1)) + terminal / (1 + rate)**len(cash)


def simulate(f, c, p):
    units = f["total_units"] - f["treasury_units"]
    # 登记日前持有人可获中期分派。假设其中20%转为单位，留下的现金减债。
    scrip_cash = f["distributable_h1"] * c["nov_scrip_election"]
    units += scrip_cash / c["nov_scrip_issue_price_proxy"]
    npi = 2 * f["npi_h1"]
    proceeds = f["nathan_proceeds"] + f["logistics_proceeds"]
    npi -= proceeds * c["disposal_npi_yield"]
    debt = f["debt_face"] - c["debt_reduction_after_settlement"] - scrip_cash
    finance_delta = debt * p["debt_rate"] - f["debt_face"] * f["observed_borrowing_cost"]
    previous_dpu = 0.0
    cash = []
    for growth in p["npi_growth"]:
        npi *= 1 + growth
        income = (2 * f["distributable_h1"] + (npi - 2 * f["npi_h1"]) *
                  c["marginal_npi_to_distributable"] - finance_delta)
        budget = income * p["payout"]
        dpu = budget / units
        # 预测优先使用分配留存，余下翻新开支由选择分派再投资的持有人出资。
        funding = max(0, p["capex"] - (income - budget))
        assert funding <= budget and income - budget <= p["capex"]
        assert isclose(income - (budget - funding), p["capex"])
        added_units = funding / (p["issue_multiple"] * dpu)
        cash.append((previous_dpu + dpu) / 2)
        previous_dpu = dpu
        unit_growth = added_units / units
        units += added_units

    # 第六年起，总可分派收入和资本预算同速增长，分派再投资使每单位增长低于组合增长。
    steady_growth = (1 + p["steady_income_growth"]) / (1 + unit_growth) - 1
    next_cash = dpu * (1 + steady_growth / 2)
    ends, present, terminal_share = [], [], []
    for rate in sorted(p["discount"], reverse=True):
        assert rate > steady_growth
        terminal = next_cash / (rate - steady_growth)
        value = discounted_cashflows(cash, terminal, rate)
        ends.append(round(terminal, 2))
        present.append(round(value, 2))
        terminal_share.append(round(terminal / (1 + rate)**5 / value, 4))
    return {"annual_cash": [round(x, 3) for x in cash], "value": present, "terminal": ends,
            "terminal_pv_share": terminal_share, "steady_dpu_growth": round(steady_growth, 5),
            "units_y5_million": round(units, 2), "net_income_y5_million": round(income, 2)}


def nav(f, c):
    holders = f["assets"] - f["liabilities"] - f["minority_equity"]
    assert holders == 147559
    # 已除息，现金型和单位型分派须同时从净资产及分母衔接。
    claim = f["distributable_h1"]
    reinvested = claim * c["nov_scrip_election"]
    adjusted = holders - claim + reinvested
    units = f["total_units"] - f["treasury_units"] + reinvested / c["nov_scrip_issue_price_proxy"]
    adjusted -= f["nathan_book"] - f["nathan_proceeds"]
    adjusted -= f["logistics_proceeds"] / (1 - f["logistics_discount"]) - f["logistics_proceeds"]
    pool = f["hk_retail"] + f["hk_parking"] - f["nathan_book"]
    cap = c["hk_portfolio_cap_proxy"]
    return sorted(round((adjusted - pool * shift / (cap + shift)) / units, 2)
                  for shift in c["nav_cap_widening"])


def main():
    assert isclose(discounted_cashflows([1, 1], 10, 0.10), 10)
    f, c = DATA["facts"], DATA["common"]
    assert isclose(f["total_units"] - f["treasury_units"], 2588.998106)
    paths = {name: simulate(f, c, path) for name, path in DATA["forecast"].items()}
    base = paths["base"]
    low, high = base["value"]
    anchors = {"structural_bear": paths["structural_bear"]["value"][0],
               "cyclical_bear": paths["cyclical_bear"]["value"][0], "base_low": low,
               "base_high": high, "bull": paths["bull"]["value"][0]}
    assert list(anchors.values()) == sorted(anchors.values())
    assert anchors["bull"] < f["conversion_price"]
    output = {
        "symbol": DATA["symbol"], "report_period": DATA["report_period"],
        "value_range": {"low": low, "high": high, "currency": "HKD"},
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1",
            "currency": "HKD", "model_as_of": DATA["as_of"],
            "base_case_distributions_per_share": base["annual_cash"],
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": dict(zip(["low", "high"], base["terminal"]))}},
        "scenarios": {"currency": "HKD", **anchors}, "adjusted_nav_check": nav(f, c),
        "paths": paths,
        "basis": "每基金单位、税前、除去11月26日登记的中期分派；永续部分扣计维护与改造的融资稀释。"
    }
    (HERE / "2027-H1-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
