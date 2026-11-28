"""在本文件所在目录读输入，以亿元、亿股复算估值并写出简明结果。"""
import json
from copy import deepcopy
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def balance(sales, new_sales, p, depreciation_rate):
    """净利包含折旧及经常租赁成本。下行时不预支库存或应收回收。"""
    increment = max(new_sales - sales, 0)
    profit = new_sales * p["margin"]
    maintenance = new_sales * p["maintenance"]
    depreciation = new_sales * depreciation_rate
    growth_assets = increment * p["growth_capital"]
    working_capital = increment * p["working_capital"]
    reinvestment = maintenance - depreciation + growth_assets + working_capital
    return profit, profit - reinvestment, reinvestment


def forecast(facts, operations, path):
    shares = facts["issued"] + facts["incentive_reserve"]
    opening_cash = facts["parent_cash_equivalent"] + facts["parent_financial_assets"] - facts["operating_reserve"]
    cash = opening_cash
    testing, other = operations["testing_sales"], operations["other_sales"]
    flows, payments, profits, capital = [], [], [], []
    for year in range(1, operations["horizon"] + 1):
        old_sales = testing + other
        testing *= 1 + path["testing_growth"]
        other *= 1 + path["other_growth"]
        profit, flow, reinvestment = balance(old_sales, testing + other, path, operations["nonlease_depreciation_ratio"])
        if year == 1:
            flow -= path["collection_charge"]
        payment = max(0, min(profit * path["payout"], flow))
        cash += flow - payment
        flows.append(flow)
        profits.append(profit)
        payments.append(payment / shares)
        capital.append(reinvestment)
    assert isclose(cash, opening_cash + sum(flows) - sum(payments) * shares)
    assert cash >= 0
    terminal = (profits[-1] * path["multiple"] + cash) / shares
    discount = 1 + path["discount"]
    terminal_pv = terminal / discount ** len(flows)
    value = terminal_pv + sum(entry / discount ** year for year, entry in enumerate(payments, 1))
    return dict(value=value, terminal=terminal, terminal_fraction=terminal_pv/value, payments=payments,
                profit=profits[-1], sales=testing + other, opening_cash=opening_cash,
                terminal_cash=cash, y1_y5_profit_change=profits[-1]-profits[0],
                y1_y5_reinvestment=sum(capital[1:]), flows=flows)


def operating_dcf(base, case, operations, inputs, shares):
    """前五年普通股可用现金，六至十年增速线性收敛，第十一年起永续。"""
    flows = list(base["flows"])
    sales = base["sales"]
    for year in range(6, 11):
        growth = inputs["early_growth"] + (inputs["steady_growth"] - inputs["early_growth"]) * (year - 6) / 4
        next_sales = sales * (1 + growth)
        flows.append(balance(sales, next_sales, case, operations["nonlease_depreciation_ratio"])[1])
        sales = next_sales
    growth = inputs["steady_growth"]
    steady_flow = balance(sales, sales*(1+growth), case, operations["nonlease_depreciation_ratio"])[1]
    rate = inputs["discount"]
    assert rate > growth
    pv = sum(flow / (1+rate)**year for year, flow in enumerate(flows, 1))
    pv += steady_flow / (rate - growth) / (1+rate)**len(flows)
    return (base["opening_cash"] + pv) / shares


def run(i):
    facts, operations, paths = i["equity"], i["operations"], i["paths"]
    results = {key: forecast(facts, operations, p) for key, p in paths.items()}
    low, high = results["base_low"], results["base_high"]
    assert low["payments"] == high["payments"]
    values = {key: round(data["value"], 2) for key, data in results.items()}
    assert list(values.values()) == sorted(values.values())
    shares = facts["issued"] + facts["incentive_reserve"]
    alternative = operating_dcf(low, paths["base_low"], operations, i["cross_check"], shares)
    path = deepcopy(paths["base_low"])
    path["margin"] -= 0.01
    sensitivity = forecast(facts, operations, path)["value"] / low["value"] - 1
    # 手算：一股公司、每年收入10、净利1、无增长或资本支出，全部派发，
    # 无期初现金、零折现，期末10倍净利。五年合计5 + 10 = 15。
    hand = dict(paths["base_low"], testing_growth=0, other_growth=0, margin=.1, maintenance=0,
                payout=1, discount=0, multiple=10)
    unit = dict(issued=1, incentive_reserve=0, parent_cash_equivalent=0, parent_financial_assets=0, operating_reserve=0)
    assert isclose(forecast(unit, dict(operations, testing_sales=10, other_sales=0, nonlease_depreciation_ratio=0), hand)["value"], 15)
    return {
        "symbol": i["symbol"], "report_period": i["report_period"],
        "value_range": {"low": values["base_low"], "high": values["base_high"], "currency":"CNY"},
        "return_model": {"schema_version":1, "method":"annual_common_equity_irr_v1", "currency":"CNY",
                         "model_as_of":i["cutoff"],
                         "base_case_distributions_per_share":[round(n, 4) for n in low["payments"]],
                         "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(low["terminal"], 4), "high":round(high["terminal"], 4)}}},
        "scenarios": {"currency":"CNY", **values, "horizon_note":"五年经营路径按测试服务增速、其他订单、验收损失、资本预算和终态盈利能力区别。锚点均为截止日每股现值。"},
        "company_bridge": {"diluted_shares_100m": shares, "opening_excess_cash_100m": round(low["opening_cash"],3),
                           "year5_retained_cash_100m": round(low["terminal_cash"],3),
                           "dcf_per_share":round(alternative,2), "one_point_margin_loss_pct":round(100*sensitivity,1)},
        "path_metrics": {k:{item:round(res[item],3) for item in ("profit","sales","terminal_fraction","y1_y5_profit_change","y1_y5_reinvestment")} for k,res in results.items()}
    }


if __name__ == "__main__":
    source = json.loads((HERE / "2026-Q3-input.json").read_text())
    (HERE / "2026-Q3-output.json").write_text(json.dumps(run(source),ensure_ascii=False,indent=2)+"\n")
