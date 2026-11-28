"""在本目录以 Python 3 执行本文件，读取同周期输入并生成输出。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def present_value(payments, terminal, rate):
    return sum(amount / (1 + rate) ** year for year, amount in enumerate(payments, 1)) + terminal / (1 + rate) ** len(payments)


def simulate(path, initial_sales, opening_cash, shares_in_yi):
    cash = opening_cash
    sales_before = initial_sales
    distributions = []
    profits = []
    investments = []
    for sales, margin, runoff in zip(path["sales"], path["margin"], path["runoff"], strict=True):
        profit = sales * margin
        growth = max(0, sales - sales_before)
        investment = growth * (path["fixed_per_growth"] + path["working_per_growth"]) + runoff
        free_cash = profit - investment
        payment = min(profit * path["payout"], max(0, free_cash))
        cash += free_cash - payment
        assert cash >= 0, "盈余资金耗尽，需要重新预算融资"
        distributions.append(payment / shares_in_yi)
        profits.append(profit)
        investments.append(investment)
        sales_before = sales
    assert abs(cash - (opening_cash + sum(profits) - sum(investments) - sum(distributions) * shares_in_yi)) < 1e-8
    terminals = [(profits[-1] * multiple + cash) / shares_in_yi for multiple in path["multiples"]]
    values = [present_value(distributions, terminal, path["rate"]) for terminal in terminals]
    return {
        "distributions": distributions, "terminal_per_share": terminals, "pv_per_share": values,
        "terminal_pv_fraction": [t / (1 + path["rate"]) ** len(distributions) / v for t, v in zip(terminals, values)],
        "cash_at_year5_yi": cash, "operating_earnings_yi": profits, "net_reinvestment_yi": investments,
    }


def main():
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    balance = data["balance"]
    denom = (balance["a_shares"] + balance["h_shares"] + balance["extra_dilution_budget"]) / 1e8
    cash = balance["cash_equivalents"] + balance["trading_assets"] - sum(balance[k] for k in ("debt_short","debt_due","debt_long","lease_noncurrent","operating_cash_floor"))
    assert sum(r["shares"] for r in data["buyback_transactions"]) + 855600 == balance["h_treasury"]
    assert sum(r["hkd"] for r in data["buyback_transactions"]) == balance["post_quarter_hkd_buybacks"]
    post_cash = (balance["october_awards"] * balance["october_award_price"] - balance["post_quarter_hkd_buybacks"] * balance["assumed_cny_per_hkd"]) / 1e8
    cash += post_cash
    sales = data["operating"]
    ttm_sales = sales["prior_fy_sales"] - sales["prior_9m_sales"] + sales["latest_9m_sales"]
    modeled = {key: simulate(path, ttm_sales, cash, denom) for key, path in data["paths"].items()}
    base = modeled["base"]
    lo, hi = [round(x, 2) for x in base["pv_per_share"]]
    terminal = [round(x, 5) for x in base["terminal_per_share"]]
    distribution = [round(x, 5) for x in base["distributions"]]
    config = data["steady_check"]
    checks = []
    for growth, roic in zip(config["growth"],config["new_capital_returns"],strict=True):
        cash_flow_6 = base["operating_earnings_yi"][-1] * (1 + growth) * (1 - growth / roic)
        terminal_steady = (cash_flow_6 / (config["rate"] - growth) + base["cash_at_year5_yi"]) / denom
        checks.append(round(present_value(base["distributions"],terminal_steady,config["rate"]), 2))
    scenarios = {
        "currency":"CNY", "structural_bear":round(modeled["structural_bear"]["pv_per_share"][0],2),
        "cyclical_bear":round(modeled["cyclical_bear"]["pv_per_share"][0],2),
        "base_low":lo,"base_high":hi,"bull":round(modeled["bull"]["pv_per_share"][0],2),
        "horizon_note":"五年逐年预算验收收入、研发后利润、客户预收回落及资本投入，第五年经营权益和未分配盈余资金折现到本期。"
    }
    anchors = [scenarios[k] for k in ("structural_bear","cyclical_bear","base_low","base_high","bull")]
    assert anchors == sorted(anchors) and min(anchors) >= 0
    assert present_value([2], 9, 0.10) == 10
    single = dict(sales=[10],margin=[0.2],runoff=[0],fixed_per_growth=0,working_per_growth=0,payout=0.5,rate=0,multiples=[5,5])
    assert simulate(single,10,0,1)["pv_per_share"] == [12,12]
    margin_shock = data["paths"]["base"].copy()
    margin_shock["margin"] = [value - 0.01 for value in margin_shock["margin"]]
    margin_check = simulate(margin_shock, ttm_sales, cash, denom)["pv_per_share"]
    result = {
        "symbol":data["symbol"],"report_period":data["report_period"],"value_range":{"low":lo,"high":hi,"currency":"CNY"},
        "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY","model_as_of":data["cutoff"],
          "base_case_distributions_per_share":distribution,"base_case_terminal_equity_value_range_per_share":{"year_5":{"low":terminal[0],"high":terminal[1]}}},
        "scenarios":scenarios,"cash_bridge":{"opening_excess_yi":cash,"post_quarter_cash_yi":post_cash,"diluted_shares_yi":denom,
          "current_non_treasury_shares":balance["a_shares"]+balance["h_shares"]-balance["a_treasury"]-balance["h_treasury"]},
        "steady_cash_flow_check_per_share":checks,"margin_down_one_point":margin_check,"paths":modeled,
    }
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2) + "\n")


if __name__ == "__main__":
    main()
