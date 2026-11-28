"""从本目录独立复算长江基建普通股权益（金额为百万港元）。"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def present_value(payments, terminal, rate):
    return sum(amount / (1 + rate) ** year for year, amount in enumerate(payments, 1)) + terminal / (1 + rate) ** len(payments)


def normalise(f, n):
    ukpn = f["ukpn_distribution_all_owners"] * f["ukpn_stake_each"]
    ffo = f["fy_parent_cfo"] + f["fy_assoc_div"] + f["fy_jv_div"]
    direct = (ffo - f["fy_pah_div_in_assoc"] - ukpn - n["rail_and_fx_reserve"]
              - f["fy_bank_interest_received"] + f["fy_finance_cost_paid"] - f["fy_perpetual_coupon"]
              - f["fy_capex_ppe"] - f["fy_capex_intangible"] - f["fy_lease_payments"])
    pah = f["pah_fy_ffo"] - ukpn - n["pah_exit_and_funding_adjustment"]
    return direct, pah


def project(data, case, r_override=None):
    f, n = data["facts"], data["normalisation"]
    direct, pah = normalise(f, n)
    stake, shares = f["stake_pah"], f["shares"]
    rate = case["r"] if r_override is None else r_override
    deposit, growth = case["deposit"], case["growth"]
    direct_net = f["group_cash"] - f["short_debt"] - f["long_debt"]
    pah_net = f["pah_cash"] - f["pah_debt"]
    # 半年至截止日按已付中期股息和统一基准运营现金估算，所有情景同起点。
    frac = n["days_since_june"] / 365
    base = data["scenarios"]["base_low"]
    direct_cash = (direct_net + (direct - base["capital"][0] + direct_net * base["deposit"]) * frac
                   - f["interim_dividend_paid"] + f["pah_interim_paid"] * stake - f["commitments"])
    pah_cash = pah_net + (pah - base["capital"][1] + pah_net * base["deposit"]) * frac - f["pah_interim_paid"]
    start = [direct_cash, pah_cash]
    direct_cash -= case["acquisition"]
    new_income = case["acquisition"] * case["acq_yield"]
    for year, dividend in enumerate(case["dps"]):
        direct_flow = (direct * case["factor"] - case["capital"][0]) * (1 + growth) ** year
        pah_flow = (pah * case["factor"] - case["capital"][1]) * (1 + growth) ** year
        before = direct_cash + stake * pah_cash
        interest = before * deposit
        direct_cash += direct_cash * deposit + direct_flow + new_income + stake * case["pah_dps_total"] - shares * dividend
        pah_cash += pah_cash * deposit + pah_flow - case["pah_dps_total"]
        assert direct_cash >= 0 and pah_cash >= 0
        after = before + interest + direct_flow + new_income + stake * pah_flow - shares * dividend
        assert math.isclose(direct_cash + stake * pah_cash, after, abs_tol=1e-7)
    steady = (direct_flow + stake * pah_flow) * (1 + case["g"]) / (rate - case["g"])
    # 收购本金已扣，新资产零增长净上划额独立资本化。
    terminal = (steady + new_income / rate + direct_cash + stake * pah_cash) / shares
    pv = present_value(case["dps"], terminal, rate)
    return dict(pv=round(pv, 2), terminal=round(terminal, 2), terminal_weight=round(terminal / (1 + rate)**5 / pv, 3),
                opening_cash=[round(x) for x in start], ending_cash=[round(direct_cash), round(pah_cash)])


def main():
    data = json.loads((HERE / '2026-H1-input.json').read_text())
    f = data["facts"]
    assert f["group_total_equity"] == f["group_ordinary_equity"] + f["perpetual"] + f["nci"]
    assert math.isclose(present_value([10]*5,100,0.1),100)
    paths = {k: project(data, v) for k,v in data["scenarios"].items()}
    values = [x["pv"] for x in paths.values()]
    assert values == sorted(values)
    low, high = paths["base_low"], paths["base_high"]
    cash = low["opening_cash"]
    net = f["group_cash"] - f["long_debt"] - f["short_debt"]
    pah_net = f["pah_cash"] - f["pah_debt"]
    # 账面普通权益中已包含电能的权益份额，先扣两层净现金再重估其余业务。
    equity_ex_cash = f["group_ordinary_equity"] - net - f["stake_pah"] * pah_net
    book = [(equity_ex_cash * factor + cash[0] + f["stake_pah"]*cash[1]) / f["shares"] for factor in data["book_factors"]]
    result = {
        "symbol": data["symbol"], "report_period": data["report_period"],
        "value_range": {"low":low["pv"],"high":high["pv"],"currency":"HKD"},
        "return_model": {"schema_version":1,"method":"annual_common_equity_irr_v1","model_as_of":data["as_of"],
                         "currency":"HKD","base_case_distributions_per_share":data["scenarios"]["base_low"]["dps"],
                         "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["terminal"],"high":high["terminal"]}}},
        "paths": paths,"book_check": [round(x, 2) for x in book],
        "normalised_pre_topup": normalise(f, data["normalisation"]),
        "base_low_rate_plus_100bp": project(data,data["scenarios"]["base_low"],data["scenarios"]["base_low"]["r"]+.01)["pv"]
    }
    (HERE/'2026-H1-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    main()
