"""用法：python 2026-Q3.py。读取同目录输入，将简明结果写回同目录。"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def terminal_business(income, discount, growth, reinvestment_return, mature_growth):
    """第5年末经营权益；第6至10年现金按增长与增量资本回报配对。"""
    value = 0
    for year in range(1, 6):
        investment = income * growth / reinvestment_return
        income *= 1 + growth
        value += (income - investment) / (1 + discount) ** year
    steady_cash = income * (1 + mature_growth) - income * mature_growth / reinvestment_return
    return value + steady_cash / (discount - mature_growth) / (1 + discount) ** 5


def value_path(facts, strategy, path, shares, opening_cash, opening_working):
    owner = facts["ownership"]
    retained = opening_cash - path["cash_loss"] * owner
    working = opening_working
    dividends = []
    flows = []
    for sales, margin, planned in zip(path["sales"], path["margin"], strategy["base_dividends"], strict=True):
        income = sales * margin * owner
        next_working = sales * path["working_ratio"]
        investment = (next_working - working + sales * path["net_capex_ratio"]) * owner
        flow = income - investment
        distribution = round(planned * path["dividend_factor"], 4)
        retained += flow - distribution * shares
        dividends.append(distribution)
        flows.append(flow)
        working = next_working
        assert retained >= 0, "需融资：重新协同计算现金与摊薄。"
    assert math.isclose(retained + sum(dividends) * shares,
                        opening_cash - path["cash_loss"] * owner + sum(flows))
    business = terminal_business(income, path["discount"], path["transition_growth"],
                                 path["return_on_capital"], path["mature_growth"])
    terminal = (business + retained) / shares
    pv_terminal = terminal / (1 + path["discount"]) ** 5
    value = pv_terminal + sum(d / (1 + path["discount"]) ** i for i, d in enumerate(dividends, 1))
    return {"value": round(value, 2), "terminal": round(terminal, 2), "distributions": dividends,
            "terminal_pv_fraction": round(pv_terminal / value, 3), "retained_common_cash": round(retained, 2),
            "first_last_owner_free_cash": [round(flows[0], 2), round(flows[-1], 2)]}


def run(input_data):
    facts = input_data["facts"]
    strategy = input_data["strategy"]
    shares = math.ceil(100 * sum(facts[k] for k in ("registered_shares", "granted_shares",
                                                    "prior_awards", "options_ceiling"))) / 100
    debt = sum(facts[k] for k in ("debt_due", "long_debt", "lease_debt"))
    opening = ((facts["cash"] + facts["liquid_investments"] - strategy["cash_floor"]) * facts["ownership"]
               - debt - facts["repurchase_budget"])
    working = (sum(facts[k] for k in ("ar", "notes_receivable", "receivable_financing", "prepayments", "stock"))
               - sum(facts[k] for k in ("ap", "notes_payable", "deferred_revenue")))
    assert 0 < facts["repurchase_paid"] < facts["repurchase_budget"]
    paths = {name: value_path(facts, strategy, p, shares, opening, working)
             for name, p in input_data["paths"].items()}
    low, high = paths["base_low"], paths["base_high"]
    ordered = [paths[k]["value"] for k in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")]
    assert ordered == sorted(ordered) and ordered[0] >= 0
    assert low["distributions"] == high["distributions"]
    multiple = facts["sub_transaction_equity"] / facts["sub_2025_income"]
    parent_net = facts["parent_h1_liquid"] - facts["parent_h1_dividend_payable"] - debt - facts["repurchase_budget"]
    secondary = [(p * multiple * facts["ownership"] + parent_net) / shares for p in strategy["second_sub_income"]]
    return {"symbol": input_data["symbol"], "report_period": input_data["period"],
            "value_range": {"low":low["value"], "high":high["value"], "currency":"CNY"},
            "return_model": {"schema_version":1, "method":"annual_common_equity_irr_v1", "currency":"CNY",
                             "model_as_of":input_data["as_of"], "base_case_distributions_per_share":low["distributions"],
                             "base_case_terminal_equity_value_range_per_share":
                                 {"year_5":{"low":low["terminal"],"high":high["terminal"]}}},
            "scenarios":{"currency":"CNY", **{k:v["value"] for k,v in paths.items()},
                         "horizon_note":input_data["horizon_note"]},
            "diluted_100m_shares":shares, "opening_common_cash_100m":round(opening,2),
            "opening_trade_working_capital_100m":round(working,2),
            "secondary_per_share":[round(v,2) for v in secondary], "paths":paths}


if __name__ == "__main__":
    # 永续零增长、无再投资、权益成本10%时，10亿元年利润值100亿元。
    assert math.isclose(terminal_business(10, 0.10, 0, 0.20, 0), 100)
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    result = run(data)
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
