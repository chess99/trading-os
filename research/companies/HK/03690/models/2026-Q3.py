"""运行 python3 2026-Q3.py；模型按同目录输入重建简明结果。"""
import json
from pathlib import Path

PERIOD = "2026-Q3"
HERE = Path(__file__).resolve().parent


def terminal_values(nopat, liquid_assets, investment_value, multiple, growth, roic, rate):
    assert rate > growth >= 0 and roic > growth
    continuing_fcf = nopat * (1 + growth) * (1 - growth / roic)
    equity_bridge = liquid_assets + investment_value
    return continuing_fcf / (rate - growth) + equity_bridge, nopat * multiple + equity_bridge


def project(inputs, assumptions):
    financial = inputs["financial_basis"]
    revenues = [sum(segments) for segments in zip(financial["q4_25_segment_revenue"],
                financial["h1_26_segment_revenue"], financial["q3_26_segment_revenue"])]
    bridge = inputs["common_equity"]
    cash = (bridge["cash"] + bridge["short_treasury"] - bridge["bank_debt"]
            - bridge["notes_including_convertibles"] - bridge["settlement_and_operating_buffer"]
            - bridge["acquisition_usd"] * inputs["fx_cny_per_usd"])
    investment_value = sum(bridge["financial_assets"]) * bridge["investment_realisation_fraction"]
    shares = (bridge["class_a"] + bridge["class_b"] - bridge["pending_cancellation"]
              + sum(bridge["options"]) + bridge["awards"])
    conversion = shares * inputs["fx_cny_per_hkd"]
    initial_cash = cash
    net_investments, operating_profits, retained_flows = [], [], []
    p = dict(zip(inputs["parameter_order"], assumptions))
    cost = p["discount"]
    for year in range(1, 6):
        previous = sum(revenues)
        revenues = [revenues[0] * (1 + p["core_growth"]), revenues[1] * (1 + p["new_growth"])]
        margins = [p[f"first_{s}_margin"] + (year-1)/4 * (p[f"fifth_{s}_margin"] - p[f"first_{s}_margin"])
                   for s in ("core","new")]
        revenue = sum(revenues)
        operating_profit = sum(sales * margin for sales, margin in zip(revenues, margins)) - revenue * p["hq_cost_pct"]
        nopat = operating_profit - max(operating_profit, 0) * inputs["tax_on_positive_operating_profit"]
        net_investment = (revenue - previous) * p["net_investment_per_incremental_revenue"]
        retained_flow = nopat - net_investment
        previous_cash = cash
        cash = previous_cash * (1 + inputs["cash_carry"]) + retained_flow
        assert abs(cash - previous_cash - previous_cash * inputs["cash_carry"] - retained_flow) < 1e-8
        assert cash >= 0, "新增融资缺口须显式建模"
        net_investments.append(net_investment)
        operating_profits.append(nopat)
        retained_flows.append(retained_flow)

    primary, secondary = terminal_values(nopat, cash, investment_value, p["exit_nopat_multiple"],
                                        p["continuing_growth"], p["continuing_roic"], cost)
    assert abs(nopat * p["exit_nopat_multiple"] + cash + investment_value - secondary) < 1e-8
    return {"value":round(primary / conversion / (1+cost)**5,2),
            "multiple_check_value":round(secondary/conversion/(1+cost)**5,2),
            "year_5":round(primary/conversion,2), "core_new_revenue_y5":[round(x,2) for x in revenues],
            "initial_surplus_cash":round(initial_cash,2), "recoverable_investments":round(investment_value,2),
            "fully_diluted_common_shares":round(shares,6),"year_5_cash":round(cash,2),
            "year_1_5_nopat":[round(n,2) for n in operating_profits],
            "year_1_5_fcf":[round(n,2) for n in retained_flows],
            "y1_to_y5_incremental_investment":round(sum(net_investments[1:]),2),
            "operating_terminal_share":round((primary-cash-investment_value)/primary,4)}


def main():
    inputs = json.loads((HERE / f"{PERIOD}-input.json").read_text())
    assert terminal_values(10, 2, 3, 10, 0, .15, .1) == (105,105)
    cases = {name:project(inputs, parameters) for name,parameters in inputs["scenarios"].items()}
    values = {name:case["value"] for name,case in cases.items()}
    assert list(values.values()) == sorted(values.values()) and min(values.values()) >= 0
    sensitivity = list(inputs["scenarios"]["base_low"])
    sensitivity[inputs["parameter_order"].index("fifth_core_margin")] -= .01
    result = {"symbol":inputs["symbol"],"report_period":PERIOD,"value_range":{"low":values["base_low"],
              "high":values["base_high"],"currency":"HKD"},"return_model":{"schema_version":1,
              "method":"annual_common_equity_irr_v1","currency":"HKD","model_as_of":inputs["as_of"],
              "base_case_distributions_per_share":[0]*5,
              "base_case_terminal_equity_value_range_per_share":{"year_5":{
                  "low":cases["base_low"]["year_5"],"high":cases["base_high"]["year_5"]}}},
              "scenario_values":values,"scenario_details":cases,
              "base_low_core_margin_minus_one_pt":project(inputs,sensitivity)["value"]}
    (HERE / f"{PERIOD}-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    main()
