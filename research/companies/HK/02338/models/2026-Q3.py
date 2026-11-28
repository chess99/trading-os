"""运行 python 2026-Q3.py，以同目录输入复算当前权益与第五年末除息价值。"""

import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def equity_path(initial_profit, unit_divisor, path):
    """母公司普通股口径。每年分配后留存，次年产生增量利润。"""
    payout = path["years_1_5_payout"]
    initial_return = path["early_incremental_roe"]
    mature_payout = path["mature_payout"]
    growth = path["mature_growth"]
    rate = path["discount"]
    assert 0 < mature_payout < 1 and rate > growth
    mature_return = growth / (1 - mature_payout)
    profit = initial_profit * path["profit_ratio"]
    opening_profit = profit
    dividends, earnings, retained = [], [], []
    for year in range(1, 11):
        blend = max(0, year - 5) / 5
        share_paid = payout + (mature_payout - payout) * blend
        reinvestment_return = initial_return + (mature_return - initial_return) * blend
        distribution = profit * share_paid
        capital = profit - distribution
        assert isclose(distribution + capital, profit) and capital >= 0
        earnings.append(profit)
        retained.append(capital)
        dividends.append(distribution / unit_divisor)
        recovery = path["idle_capacity_recovery"][year - 1] if year <= 5 else 0
        profit += capital * reinvestment_return + recovery
    continuing_value = profit * mature_payout / unit_divisor / (rate - growth)
    year_five = sum(dividends[i] / (1 + rate) ** (i - 4) for i in range(5, 10))
    year_five += continuing_value / (1 + rate) ** 5
    value = sum(div / (1 + rate) ** year for year, div in enumerate(dividends[:5], 1))
    value += year_five / (1 + rate) ** 5
    assert isclose(earnings[4] - opening_profit,
                   sum(retained[:4]) * initial_return + sum(path["idle_capacity_recovery"][:4]),
                   abs_tol=1e-10)
    return dict(value=value, terminal=year_five, dividends=dividends[:5],
                first_profit=opening_profit, fifth_profit=earnings[4], retention_y1_y4=sum(retained[:4]),
                fifth_year_pv_share=year_five / (1 + rate) ** 5 / value)


def calculate(inputs):
    facts = inputs["facts"]
    shares = facts["a_shares"] + facts["h_shares"]
    unit = shares / 1e8 * facts["cny_per_hkd"]
    prior = facts["nine_month_recurring_profit"] / (1 + facts["nine_month_recurring_yoy"])
    ttm = facts["fy25_recurring_profit"] + facts["nine_month_recurring_profit"] - prior
    paths = {name: equity_path(ttm, unit, path) for name, path in inputs["paths"].items()}
    low, high = paths["base_low"], paths["base_high"]
    assert low["dividends"] == high["dividends"]
    anchors = {name: round(path["value"], 2) for name, path in paths.items()}
    seq = [anchors[name] for name in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")]
    assert seq == sorted(seq)
    cross = inputs["method_two"]
    sotp = [(non_kion * multiple + kion * facts["kion_ownership"] * kion_multiple) / unit
            for non_kion, multiple, kion, kion_multiple in zip(
                cross["non_kion_common_profit"], cross["non_kion_pe"],
                cross["kion_whole_profit"], cross["kion_pe"])]
    test = dict(inputs["paths"]["base_low"], profit_ratio=1, years_1_5_payout=0.5,
                early_incremental_roe=0, mature_growth=0, mature_payout=0.5, discount=0.1)
    assert isclose(equity_path(10, 2, test)["value"], 25)  # 永续分红 2.5，每股价值 25
    return {
        "symbol":inputs["symbol"], "report_period":inputs["period"],
        "value_range":dict(low=anchors["base_low"],high=anchors["base_high"],currency="HKD"),
        "return_model":dict(schema_version=1,method="annual_common_equity_irr_v1",currency="HKD",
            model_as_of=inputs["as_of"],
            base_case_distributions_per_share=[round(x,4) for x in low["dividends"]],
            base_case_terminal_equity_value_range_per_share={"year_5":{
                "low":round(low["terminal"],2),"high":round(high["terminal"],2)}}),
        "anchors":anchors, "sotp_hkd":[round(x,2) for x in sotp],
        "ttm_recurring_profit_cny_100m":round(ttm,2),"eligible_shares":shares,
        "interim_dividend_already_ex_cny_100m":round(shares*facts["interim_dps_cny"]/1e8,2),
        "base_y1_y5_profit_cny_100m":[round(low[k],2) for k in ("first_profit","fifth_profit")],
        "base_retention_y1_y4_cny_100m":round(low["retention_y1_y4"],2),
        "year5_pv_fraction":[round(i["fifth_year_pv_share"],3) for i in (low,high)],
        "base_y1_roe_on_q3_book":round(low["first_profit"]/facts["closing_equity_q3"],4)
    }


if __name__ == "__main__":
    inputs = json.loads((HERE / "2026-Q3-input.json").read_text())
    output = calculate(inputs)
    (HERE / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
