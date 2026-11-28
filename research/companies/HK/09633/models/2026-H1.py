"""在任意目录执行 python3 2026-H1.py，从相邻输入重建简明输出。"""
import json
from math import isclose
from pathlib import Path

HOME_DIR = Path(__file__).resolve().parent


def present_value(distributions, terminal, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(distributions, 1)) + terminal / (1 + rate) ** len(distributions)


def interpolate(start, end, fraction):
    return start + (end - start) * fraction


def opening_cash(facts):
    financial_assets = facts["cash_and_bank"] + facts["long_term_deposit"] + facts["wealth_products"] * facts["financial_asset_recovery"]
    obligations = sum(facts[key] for key in ("bank_debt", "lease_debt", "fy25_declared", "preexisting_plant_payables_allowance", "operating_cash_floor"))
    return financial_assets - obligations


def forecast(facts, path):
    sales = [annual + current - previous for annual, current, previous in zip(facts["fy25_sales"], facts["h126_sales"], facts["h125_sales"])]
    surplus_cash = opening_cash(facts)
    distributable = facts["fy25_parent_distributable"] - facts["fy25_declared"]
    years = []
    for year in range(5):
        fraction = year / 4
        last_sales = sum(sales)
        rates = [interpolate(start, end, fraction) for start, end in zip(path["growth_start"], path["growth_end"])]
        sales = [revenue * (1 + rate) for revenue, rate in zip(sales, rates)]
        total = sum(sales)
        increase = max(0.0, total - last_sales)
        profit = total * interpolate(path["margin_start"], path["margin_end"], fraction)
        depreciation = total * facts["depreciation_ratio"]
        net_plant = max(increase * path["plant_per_incremental_sale"], path["net_plant_floors"][year])
        gross_plant = max(depreciation + net_plant, facts["contracted_capex"] if year == 0 else 0)
        invested = gross_plant - depreciation + increase * facts["working_capital_per_incremental_sale"]
        free_cash = profit - invested
        legal_income = profit * path["legal_remittance"]
        dividend = min(profit * path["payout"], max(0, free_cash), distributable + legal_income)
        surplus_cash += free_cash - dividend
        distributable += legal_income - dividend
        assert min(surplus_cash, distributable) >= 0 and dividend >= 0
        assert isclose(free_cash + invested, profit)
        years.append(dict(revenue=total, profit=profit, invested=invested, gross_capex=gross_plant, dividend=dividend))
    assert isclose(surplus_cash - opening_cash(facts), sum(y["profit"] - y["invested"] - y["dividend"] for y in years))
    return years, surplus_cash


def terminal_value(years, cash, path, discount):
    growth_5 = years[-1]["revenue"] / years[-2]["revenue"] - 1
    growth_final = path["steady_growth"]
    incremental_roic = path["steady_roic"]
    flows = []
    profit = years[-1]["profit"]
    for step in range(1, 6):
        growth = interpolate(growth_5, growth_final, step / 5)
        next_profit = profit * (1 + growth)
        # 本期净投入与上期末到本期末的利润增量相配，延续前五年的期末资本口径。
        flows.append(next_profit - (next_profit - profit) / incremental_roic)
        profit = next_profit
    perpetual = profit * (1 + growth_final - growth_final / incremental_roic) / (discount - growth_final)
    return cash + present_value(flows, perpetual, discount)


def evaluate(facts):
    divisor = (facts["issued_h"] + facts["issued_domestic"]) * facts["rmb_per_hkd"]
    values = {}
    for name, path in facts["paths"].items():
        years, cash = forecast(facts, path)
        divs = [y["dividend"] / divisor for y in years]
        terminals = [terminal_value(years, cash, path, discount) / divisor for discount in path["discount"]]
        values[name] = [round(present_value(divs, terminal, discount), 2) for terminal, discount in zip(terminals, path["discount"])]
        if name == "base":
            base_divs = [round(d, 4) for d in divs]
            base_terminals = dict(zip(("low","high"), (round(v, 4) for v in terminals)))
            fractions = [round(t / (1+r)**5 / present_value(divs, t, r), 3) for t, r in zip(terminals, path["discount"])]
            secondary = [round(present_value(divs, (years[-1]["profit"] * pe + cash) / divisor, r), 2)
                         for pe, r in zip(facts["secondary_exit_pe"], path["discount"])]
            increment = (years[-1]["profit"] - years[0]["profit"]) / sum(y["invested"] for y in years[1:])
            bridge = {"opening_excess_cash": round(opening_cash(facts), 3), "year5_excess_cash": round(cash, 3),
                      "terminal_pv_fraction": fractions, "secondary_range_hkd": secondary,
                      "incremental_return_y1_to_y5": round(increment, 3),
                      "years": [{k:round(v,3) for k,v in row.items()} for row in years]}
    anchors = [*values["structural"], *values["cyclical"], *values["base"], *values["bull"]]
    assert 0 <= min(anchors) and anchors == sorted(anchors)
    value_range = {"low": anchors[2], "high": anchors[3], "currency": "HKD"}
    return {"symbol":facts["symbol"], "report_period": facts["period"], "value_range": value_range,
            "return_model":{"schema_version":1, "method":"annual_common_equity_irr_v1", "currency":"HKD",
                            "model_as_of": facts["as_of"], "base_case_distributions_per_share": base_divs,
                            "base_case_terminal_equity_value_range_per_share": {"year_5":base_terminals}},
            "scenarios":dict(zip(("structural_bear", "cyclical_bear", "base_low", "base_high", "bull"), anchors)),
            "base_bridge_rmb_billions":bridge}


if __name__ == "__main__":
    # 单期持有，期末收取10并持有价值100的股权，折现10%，今天应值100。
    assert isclose(present_value([10], 100, 0.10), 100)
    facts = json.loads((HOME_DIR / "2026-H1-input.json").read_text())
    result = evaluate(facts)
    (HOME_DIR / "2026-H1-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
