"""在本目录运行 python 2026-H1.py，生成同名周期的 output.json。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = json.loads((ROOT / "2026-H1-input.json").read_text())
facts, assumptions = source["facts"], source["assumptions"]
paths = source["paths"]
fx = facts["fx"]
shares = facts["issued"] - facts["trust"] + facts["dilution"] + facts["antidilutive"]
ufsg = facts["ufsg_fy25"] + facts["ufsg_h126"] - facts["ufsg_h125"]
reference_price = facts["buyback_hkd"] / facts["cancelled"]
assert facts["ufsg_h126"] - facts["nb_capital_h126"] - facts["central_h126"] - facts["finance_h126"] == facts["net_fsg_h126"]
assert facts["free_open"] + facts["net_fsg_h126"] + facts["investment_variances"] - facts["paid_dividend"] - facts["buyback_usd"] == facts["free_close"]
assert facts["adjusted_net_worth"] + facts["vif"] == facts["ev"]
assert facts["shareholders_equity"] + facts["nci"] == facts["equity"]


def present_value(dividends, terminal, rate):
    return sum(value / (1 + rate)**year for year, value in enumerate(dividends, 1)) + terminal / (1 + rate)**len(dividends)


def value_path(params):
    cash_engine, count = ufsg, shares
    dividends, repurchases, capital_needs, surpluses = [], [], [], []
    for growth in params["growth"]:
        cash_engine *= 1 + growth
        capital = cash_engine * params["strain"]
        net = cash_engine * (1 - params["central"]) - capital
        dividend = net * params["dividend"]
        funded = net * (params["payout"] - params["dividend"])
        employee_cash = assumptions["annual_trust_cash_usdm"]
        repurchase = max(0, funded - employee_cash)
        retained = net - dividend - repurchase - employee_cash
        assert retained >= 0 and isclose(retained + dividend + employee_cash + repurchase, net)
        execution_price = reference_price * cash_engine / ufsg
        units_retired = repurchase * fx / execution_price
        issued = assumptions["annual_new_grants_m"]
        # 分红按期初股数，年末执行注销及新增激励发行。
        dividends.append(dividend * fx / count)
        repurchases.append((units_retired - issued) * execution_price / count)
        capital_needs.append(capital)
        surpluses.append(net)
        count += issued - units_retired
    # 第六年起将持续可返还金额资本化；末期股权买方享有全部剩余分配能力。
    # 受托计划耗用与新增激励的经济成本持续扣除，后者按第六年执行参考价折成现金。
    steady_cost = (employee_cash + issued * execution_price / fx) * (1 + params["g"])
    next_distributable = net * (1 + params["g"]) * params["mature_payout"] - steady_cost
    terminal = next_distributable * fx / count / (params["r"] - params["g"])
    value = present_value(dividends, terminal, params["r"])
    return dict(value=value, dividends=dividends, terminal=terminal, closing_shares=count,
                net_buyback=repurchases, terminal_weight=terminal / (1+params["r"])**5 / value,
                new_business_capital=capital_needs, net_fsg=surpluses)


assert isclose(present_value([2] * 5, 20, 0.10), 20)
results = {name:value_path(params) for name, params in paths.items()}
low, high = results["base_low"], results["base_high"]
assert low["dividends"] == high["dividends"]
anchors = {name:round(result["value"], 2) for name, result in results.items()}
assert list(anchors.values()) == sorted(anchors.values())


def prospective_ev(haircut, realization, rate):
    # H1已生效保单加已公告Q3新增，扣除9月已付股息。未计10–11月签单、投资偏差和折现回拨。
    current_ev = (facts["ev"] + facts["vnb_q326"]) * (1 - haircut)
    current_ev -= facts["interim_div"] * facts["issued"] / fx
    vnb = facts["vnb_fy25"] + facts["vnb_9m26"] - facts["vnb_9m25"]
    # 每个新年度获客批次的VONB已扣承保、获取成本及资本成本。
    future = sum(vnb * realization / (1 + rate)**n for n in range(1, assumptions["secondary_vintage_years"] + 1))
    return (current_ev + future) * fx / shares


secondary = [prospective_ev(h, v, paths[name]["r"]) for name, h, v in zip(
    ("base_low","base_high"), assumptions["secondary_ev_haircuts"], assumptions["secondary_vnb_realization"])]
output = dict(symbol=source["symbol"], report_period=source["report_period"],
              value_range={"low":anchors["base_low"],"high":anchors["base_high"],"currency":"HKD"},
              return_model={"schema_version":1, "method":"annual_common_equity_irr_v1","currency":"HKD",
              "model_as_of":source["as_of"], "base_case_distributions_per_share":[round(n,4) for n in low["dividends"]],
              "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(low["terminal"],4),"high":round(high["terminal"],4)}}},
              scenarios=anchors, secondary_ev_hkd=[round(n,2) for n in secondary],
              net_buyback_hkd_y1=round(low["net_buyback"][0],4), starting_diluted_shares_m=round(shares,3),
              shares_y5_m=round(low["closing_shares"],3), terminal_weights=[round(x["terminal_weight"],4) for x in (low,high)],
              base_net_fsg_usdm=[round(n) for n in low["net_fsg"]], base_new_business_capital_usdm=[round(n) for n in low["new_business_capital"]],
              base_low_discount_plus_one_point=round(value_path(dict(paths["base_low"],r=paths["base_low"]["r"]+0.01))["value"],2))
(ROOT / "2026-H1-output.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
