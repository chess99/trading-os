"""执行 python 2026-H1.py 复算海天国际。现金、利润、资本单位人民币百万元。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "2026-H1-input.json").read_text())
facts = data["facts"]
policy = data["policy"]


def discounted_value(dividends, terminal, rate):
    return sum(value / (1 + rate) ** year for year, value in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def cash_projection(path):
    sales = facts["sales_2025"] + facts["sales_h1_2026"] - facts["sales_h1_2025"]
    opening = (facts["cash"] + facts["time_deposits"] - facts["pledged_time_deposits"]
               + facts["fair_value_portfolio"] * (1 - path["portfolio_discount"])
               - facts["loans"] - facts["lease_debt"] - facts["minority_equity"]
               - facts["contingent_upstream_tax"] - policy["operating_cash"])
    cash = opening
    parent = facts["parent_reserves"] - facts["dividend_since_year_end"]
    dividends, profits, investments, gross_capex = [], [], [], []
    retained = 0
    for year, (growth, margin) in enumerate(zip(path["sales_growth"], path["margin"], strict=True)):
        extra_sales = sales * growth
        sales += extra_sales
        earnings = sales * margin * (1 - policy["tax_and_upstream"])
        # 需求萎缩时不假设应收及专用产线可变现。维持性资本开支与折旧相抵。
        new_fixed = max(path["net_fixed_floor"], max(extra_sales, 0) * path["fixed_per_sale"])
        working = max(extra_sales, 0) * path["working_per_sale"]
        strain = path["first_year_receivable_charge"] if year == 0 else 0
        investment = new_fixed + working + strain
        free = earnings - investment
        interest = cash * policy["cash_yield_net"]
        parent += max(free, 0) * path["parent_remittance"]
        dividend = max(0, min(earnings * path["payout"], free, parent))
        retained += free + interest - dividend
        cash += free + interest - dividend
        parent -= dividend
        assert cash >= 0 and parent >= -1e-8
        dividends.append(dividend)
        profits.append(earnings)
        investments.append(investment)
        gross_capex.append(facts["normal_maintenance"] + new_fixed)
    assert abs(opening + retained - cash) < 1e-6
    assert gross_capex[0] >= facts["capital_commitment"]
    return opening, cash, dividends, profits, investments, gross_capex


def valuation(path, exit_multiple=None):
    opening, cash, dividends, profits, investments, capex = cash_projection(path)
    rate, growth, roic = (path[key] for key in ("discount_rate", "terminal_growth", "terminal_roic"))
    assert rate > growth and roic > growth
    operating_terminal = profits[-1] * (1 + growth) * (1 - growth / roic) / (rate - growth)
    if exit_multiple is not None:
        operating_terminal = profits[-1] * exit_multiple
    divisor = facts["diluted_shares"] * facts["cny_per_hkd"]
    terminal = (cash + operating_terminal) / divisor
    dps = [p / divisor for p in dividends]
    fair = discounted_value(dps, terminal, rate)
    return {"value":round(fair, 2),"terminal":round(terminal, 2),"dps":[round(p, 3) for p in dps],
            "opening_surplus":round(opening,1),"closing_surplus":round(cash,1),
            "terminal_pv_share":round(terminal / (1 + rate) ** 5 / fair, 4),
            "operating_earnings_y1_y5":[round(profits[k],1) for k in (0,4)],
            "net_investment_y2_y5":round(sum(investments[1:]),1),
            "incremental_return_y1_to_y5":round((profits[-1]-profits[0])/sum(investments[1:]),4),
            "gross_capex_y1_y5":[round(x,1) for x in capex]}


if __name__ == "__main__":
    assert abs(discounted_value([10,10], 100, 0.1) - 100) < 1e-9
    paths = {k:v for k,v in data["paths"].items() if k != "base"}
    for k, end in data["base_endpoints"].items():
        paths[k] = data["paths"]["base"] | end
    names = ["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"]
    rows = {k:valuation(paths[k]) for k in names}
    anchors = {k:v["value"] for k,v in rows.items()}
    assert list(anchors.values()) == sorted(anchors.values()) and min(anchors.values()) >= 0
    assert rows["base_low"]["dps"] == rows["base_high"]["dps"]
    low, high = rows["base_low"], rows["base_high"]
    ends = list(data["base_endpoints"])
    secondary = [valuation(paths[k], m)["value"] for k,m in zip(ends,data["secondary_terminal_operating_earnings_multiples"],strict=True)]
    weaker = [valuation(paths[k] | {"margin":[m - 0.01 for m in paths[k]["margin"]]})["value"] for k in ends]
    output = {
        "symbol":data["symbol"],"report_period":data["report_period"],
        "value_range":{"low":low["value"],"high":high["value"],"currency":"HKD"},
        "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD",
                        "model_as_of":data["as_of"],"base_case_distributions_per_share":low["dps"],
                        "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["terminal"],"high":high["terminal"]}}},
        "anchors":anchors,"scenario_details":rows,"secondary_value_range_hkd":secondary,
        "one_point_lower_operating_margin_range_hkd":weaker}
    (ROOT / "2026-H1-output.json").write_text(json.dumps(output,ensure_ascii=False,indent=2) + "\n")
