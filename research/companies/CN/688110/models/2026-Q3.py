"""东芯股份。人民币亿元、亿股，同币种普通股。直接运行生成同目录结果。"""
import json
from pathlib import Path
from math import isclose

DIRECTORY = Path(__file__).resolve().parent


def discounted(distributions, terminal, discount):
    return sum(cash / (1 + discount) ** t for t, cash in enumerate(distributions, 1)) + terminal / (1 + discount) ** len(distributions)


def terminal_business(fcfe, growth, discount):
    assert discount > growth
    return max(fcfe, 0) / (discount - growth)


def evaluate(data, scenario):
    b = data["balance"]
    shares = data["issued"] - data["treasury"] + data["award_allowance"]
    liquid = b["equivalents"] + b["trading_deposits"] + b["estimated_other_cash_recovery"] + b["estimated_long_cd"]
    opening_cash = liquid - sum(b[k] for k in ["interest_debt", "tax_due", "employee_due", "minimum_cash", "minority_cash_allowance"])
    cash = opening_cash
    wc = b["receivables"] + b["prepaid"] + b["inventory"] - b["payables"] - b["advance"]
    opening_wc = wc
    rows = []
    for i, volume in enumerate(scenario["volume"]):
        sales = volume * data["base_revenue"] * scenario["price"][i]
        production = volume * data["base_cogs"] * scenario["unit_cost"][i]
        gross = sales - production
        pre_tax = gross - scenario["expenses"][i] - sales * scenario["loss_rate"]
        nopat = pre_tax - max(pre_tax, 0) * data["tax_rate"]
        next_wc = sales * scenario["ar_days"] / 365 + production * (scenario["inventory_cost_years"] - scenario["payable_cost_ratio"])
        next_wc += min(i + 1, 2) / 2 * data["project_budget"]["working_capital"]
        net_capex = scenario["net_capex"][i]
        owner_fraction = 1 - scenario["minority"]
        available = (nopat - net_capex - next_wc + wc) * owner_fraction - scenario["funding"][i]
        cash = cash * (1 + data["steady_cash_yield"]) + available - scenario["payout"][i] * shares
        assert cash >= 0, "流动性缺口需要另列融资"
        rows.append(dict(sales=sales, gross_margin=gross/sales, nopat=nopat, owner_profit=nopat*owner_fraction, working_capital=next_wc, net_capex=net_capex, available=available, retained=cash))
        wc = next_wc
    growth = scenario["growth"]
    rate = scenario["rate"]
    # 稳态净资本开支覆盖设备与研发设施扩充，留存营运资本与收入同速增长。
    year6_owner_cash = ((nopat - net_capex)*(1 + growth) - wc*growth) * owner_fraction
    operating_terminal = terminal_business(year6_owner_cash, growth, rate)
    terminal = (cash + operating_terminal + scenario["exit"] + b["fund_recovery_y5"]) / shares
    matrix_terminal = (cash + max(rows[-1]["owner_profit"], 0)*scenario["pe"] + scenario["exit"] + b["fund_recovery_y5"]) / shares
    value = discounted(scenario["payout"], terminal, rate)
    terminal_weight = terminal/(1+rate)**5/value
    assert isclose(cash, opening_cash*(1+data["steady_cash_yield"])**5 + sum((r["available"]-scenario["payout"][i]*shares)*(1+data["steady_cash_yield"])**(4-i) for i,r in enumerate(rows)))
    return dict(pv=value, year5_terminal=terminal, matrix=discounted(scenario["payout"], matrix_terminal, rate), year6_owner_cash=year6_owner_cash, opening_cash=opening_cash, opening_wc=opening_wc, shares=shares, total_terminal_weight=terminal_weight, operating_terminal_weight=operating_terminal/shares/(1+rate)**5/value, years=rows)


def main():
    # 与正式现值及永续价值函数共用的零增长现金年金手算特例。
    assert terminal_business(1, 0, 0.1) == 10
    assert isclose(discounted([1]*5, 10, 0.1), 10)
    data = json.loads((DIRECTORY/'2026-Q3-input.json').read_text())
    cases = {k:evaluate(data, v) for k,v in data["scenarios"].items()}
    anchors = {k:round(v["pv"], 2) for k,v in cases.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    base = ("base_low", "base_high")
    bands = {k.split("_")[1]: round(cases[k]["year5_terminal"], 2) for k in base}
    value_range = dict(currency="CNY", low=anchors["base_low"], high=anchors["base_high"])
    returns = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="CNY", model_as_of=data["as_of"], base_case_distributions_per_share=data["scenarios"]["base_low"]["payout"], base_case_terminal_equity_value_range_per_share={"year_5":bands})
    sensitivities = {}
    for k in base:
        original = data["scenarios"][k]
        sensitivities[k] = {}
        for label, patch in [("price_index_down_10pct", {"price":[p*.90 for p in original["price"]]}), ("volume_down_10pct", {"volume":[v*.9 for v in original["volume"]]}), ("unit_cost_up_10pct", {"unit_cost":[c*1.1 for c in original["unit_cost"]]}), ("bad_debt_plus_1pct", {"loss_rate":original["loss_rate"]+.01}), ("extra_funding_1yi_y1",{"funding":[original["funding"][0]+1,*original["funding"][1:]]})]:
            sensitivities[k][label] = evaluate(data, original|patch)["pv"]-cases[k]["pv"]
    out = dict(symbol=data["symbol"], report_period=data["report_period"], value_range=value_range, return_model=returns, scenarios=anchors, cases=cases, sensitivities=sensitivities)
    (DIRECTORY/'2026-Q3-output.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')


if __name__ == "__main__":
    main()
