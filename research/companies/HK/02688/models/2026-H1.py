"""在任意目录执行 python 2026-H1.py，从同目录输入重建结果。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def discount(distributions, terminal, rate):
    return sum(d / (1 + rate)**t for t, d in enumerate(distributions, 1)) + terminal / (1 + rate)**len(distributions)


def project(facts, assumptions, path):
    shares = facts["issued"] - facts["treasury"] + facts["options"]
    hk_per_million = 1 / (facts["cny_per_hkd"] * shares)
    earnings = facts["fy25_core"] + facts["h126_core"] - facts["h125_core"] - assumptions["normal_core_charge"]
    volume = facts["fy25_retail_vol"] + facts["h126_retail_vol"] - facts["h125_retail_vol"]
    gp = facts["fy25_retail_gp"] + facts["h126_retail_gp"] - facts["h125_retail_gp"]
    attribution = facts["h126_owners"] / facts["h126_pbt"]
    retained = 0
    dividends = []
    available = []
    for t, ratio in enumerate(path["volume"]):
        # 存量销量变化按滚动分部毛利计算，采购价差变动只作用于对应合并销量。
        gp_change = (ratio - 1) * gp + volume * ratio * assumptions["scope_share"] * path["spread"][t]
        profit = earnings + gp_change * attribution + path["other"][t]
        capital_index = (1 + path["cash_growth"])**t
        net_reinvestment = (path["capex"] - assumptions["da_year1"]) * capital_index
        reserve = (assumptions["conversion_reserve"] + path["reserve_extra"]) * capital_index
        cash = profit - net_reinvestment - reserve
        distribution = min(assumptions["payout_target"] * profit, max(cash, 0) * path["distribution_share"])
        retained += cash - distribution
        assert cash >= distribution >= 0
        dividends.append(distribution * hk_per_million)
        available.append(cash)
    # 兑现预算包括维护、扩建与营运资金，永续增速保持相同资本强度。
    operating_terminal = available[-1] * (1 + path["g"]) / (path["r"] - path["g"])
    terminal = (operating_terminal + retained) * hk_per_million
    value = discount(dividends, terminal, path["r"])
    assert abs(sum(available) - sum(dividends) / hk_per_million - retained) < 1e-7
    return {"value": round(value, 2), "distributions":[round(d, 2) for d in dividends],
            "year5":round(terminal, 2), "terminal_pv_share":round(terminal / (1 + path["r"])**5 / value, 4),
            "year1_cash_rmb_m":round(available[0]),"year5_cash_rmb_m":round(available[-1]),"retained_rmb_m":round(retained)}


def main():
    assert abs(discount([1, 1], 10, 0.1) - 10) < 1e-12
    data = json.loads((HERE / "2026-H1-input.json").read_text())
    f, a = data["facts"], data["assumptions"]
    assert f["h126_pbt"] - f["h126_income_tax"] - f["h126_nci"] == f["h126_owners"]
    paths = {name: project(f, a, p) for name, p in a["paths"].items()}
    values = [v["value"] for v in paths.values()]
    assert 0 <= min(values) and values == sorted(values)
    low, high = paths["base_low"], paths["base_high"]
    assert low["distributions"] == high["distributions"]
    shares = f["issued"] - f["treasury"] + f["options"]
    bvps = f["parent_equity"] / (shares * f["cny_per_hkd"])
    check = {k: round(bvps * x["roe"] * x["cash_payout"] / (x["r"] - x["g"]), 2) for k,x in a["book_check"].items()}
    adverse_spread = {**a["paths"]["base_low"],"spread":[-0.02]*5}
    result = {"symbol":data["symbol"], "report_period":data["report_period"],
              "value_range":{"low":low["value"],"high":high["value"],"currency":"HKD"},
              "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD","model_as_of":data["as_of"],
                              "base_case_distributions_per_share":low["distributions"],
                              "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["year5"],"high":high["year5"]}}},
              "paths":paths,"book_check":check,"spread_minus_002_base_low":project(f,a,adverse_spread)["value"]}
    (HERE / "2026-H1-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2) + "\n")


if __name__ == "__main__":
    main()
