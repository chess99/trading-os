"""美亚光电，直接运行本文件生成相邻的简明结果。金额为百万元。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def terminal_value(revenue, margin, growth, return_on_capital, discount):
    """稳态首年利润扣除为增长所需再投资，折现到稳态起点。"""
    assert 0 <= growth < min(discount, return_on_capital)
    first_profit = revenue * (1 + growth) * margin
    return first_profit * (1 - growth / return_on_capital) / (discount - growth)


def evaluate(data, path):
    facts = data["disclosed"]
    shares = facts["diluted_shares"]
    revenue = facts["FY25_revenue"] + facts["9m26_revenue"] - facts["9m25_revenue"]
    segments = [revenue * weight for weight in data["starting_mix_sort_medical_other"]]
    assert isclose(sum(segments), revenue)
    opening_surplus = (facts["cash_equivalents"] + facts["treasury_products"]
                       - data["cash_reserve"] - facts["debt_and_minority_claims"])
    equity_asset = facts["equity_investment"] * data["equity_investment_recovery"]
    surplus = opening_surplus
    parent_retained = facts["parent_H1_retained"]
    distributions, profits, investments = [], [], []
    cumulative_free_cash = 0
    growth_paths = [path[key] for key in ("sort_growth", "medical_growth", "other_growth")]
    for i, margin in enumerate(path["margins"]):
        previous_revenue = revenue
        segments = [balance * (1 + rates[i]) for balance, rates in zip(segments, growth_paths)]
        revenue = sum(segments)
        operating_profit = revenue * margin
        interest = surplus * data["cash_net_yield"]
        # 销售收缩时不预支存货和固定资产变现；逾期回款、呆滞存货另占去现金。
        new_sales = max(0, revenue - previous_revenue)
        investment = (data["plant_payments"][i] + path["additional_cash_costs"][i]
                      + new_sales * (path["working_capital_intensity"] + path["net_fixed_intensity"]))
        free_cash = operating_profit + interest - investment
        available_cash = surplus + free_cash
        parent_retained += (operating_profit + interest) * data["parent_share_of_income"]
        payment = max(0, min(path["payout"] * (operating_profit + interest), available_cash, parent_retained))
        surplus = available_cash - payment
        parent_retained -= payment
        cumulative_free_cash += free_cash
        distributions.append(payment / shares)
        profits.append(operating_profit)
        investments.append(investment)
        assert min(surplus, parent_retained) >= 0
        assert isclose(surplus + sum(distributions) * shares, opening_surplus + cumulative_free_cash)
    discount = path["discount"]
    operating_terminal = terminal_value(revenue,path["terminal_margin"],path["terminal_growth"],
                                       path["terminal_roic"],discount)
    equity_terminal = (operating_terminal + surplus + equity_asset) / shares
    terminal_pv = equity_terminal / (1 + discount) ** 5
    value = terminal_pv + sum(d / (1 + discount) ** year for year,d in enumerate(distributions, 1))
    return {"value":value,"share_distributions":distributions,"terminal":equity_terminal,
            "terminal_pv_share":terminal_pv/value,"year5_revenue":revenue,"year5_operating_profit":profits[-1],
            "year5_excess_cash":surplus,"year1_operating_profit":profits[0],"Y2_to_Y5_investment":sum(investments[1:]),
            "Y1_to_Y5_incremental_profit":profits[-1]-profits[0],"opening_excess_cash":opening_surplus}


def main():
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    # 无增长且年利润为10，资本成本10%，经营终值为100。
    assert isclose(terminal_value(100,0.10,0,0.20,0.10),100)
    paths = data["paths"]
    names = ["structural_bear","cyclical_bear","base_low","base_high","bull"]
    outputs = {}
    for name in names:
        path = (paths["base"] | data["base_endpoints"][name]) if name in data["base_endpoints"] else paths[name]
        outputs[name] = evaluate(data,path)
    anchors = {key:round(value["value"],2) for key,value in outputs.items()}
    assert sorted(anchors.values()) == list(anchors.values())
    base = outputs["base_low"]
    assert base["share_distributions"] == outputs["base_high"]["share_distributions"]
    facts = data["disclosed"]
    nonoperating = base["opening_excess_cash"] + facts["equity_investment"] * data["equity_investment_recovery"]
    # 盈利资本化按正常经营利润定价；单列工程余款的现值，其他常规增长支出包含在倍数中。
    project_pv = sum(payment/1.091**i for i,payment in enumerate(data["plant_payments"],1))
    secondary = [(base["year1_operating_profit"]*multiple+nonoperating-project_pv)/facts["diluted_shares"]
                 for multiple in data["secondary_normalized_operating_earnings_multiple"]]
    output = {"symbol":data["symbol"],"report_period":data["report_period"],
              "value_range":{"low":anchors["base_low"],"high":anchors["base_high"],"currency":"CNY"},
              "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY",
                  "model_as_of":data["as_of"],"base_case_distributions_per_share":[round(v,4) for v in base["share_distributions"]],
                  "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(base["terminal"],2),
                       "high":round(outputs["base_high"]["terminal"],2)}}},
              "scenario_values":anchors,"secondary_per_share":[round(v,2) for v in secondary],
              "scenario_diagnostics":{key:{k:round(v,4) for k,v in row.items() if k not in ("share_distributions","value")}
                                      for key,row in outputs.items()}}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    main()
