"""以标准库运行 Python 3.10+ 执行 2027-H1.py，在同目录更新模型输出。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERIOD = "2027-H1"
AS_OF = "2026-11-27T18:00:00+08:00"


def project(revenue, cash, conversion, case):
    """分配后剩余现金按零利率累计，第五年末与成熟经营价值一并归属普通股。"""
    annual = []
    accumulated = cash
    for growth, margin in zip(case["growth"], case["margin"], strict=True):
        previous = revenue
        revenue *= 1 + growth
        reinvestment = revenue * case["net_maintenance"] + max(revenue - previous, 0) * case["capital_per_new_sale"]
        available = revenue * margin - reinvestment
        dividend = max(0, available) * case["payout"]
        accumulated += available - dividend
        assert accumulated >= 0
        annual.append((revenue, available, dividend, reinvestment))
    g = case["terminal_growth"]
    k = case["discount"]
    assert g < k and len(annual) == 5
    year6_cash = revenue * (1 + g) * (case["margin"][-1] - case["net_maintenance"]) - revenue * g * case["capital_per_new_sale"]
    terminal = (year6_cash / (k - g) + accumulated) / conversion
    payouts = [row[2] / conversion for row in annual]
    pv_terminal = terminal / (1 + k) ** 5
    present = pv_terminal + sum(d / (1 + k) ** y for y, d in enumerate(payouts, 1))
    assert abs(accumulated - cash - sum(row[1] - row[2] for row in annual)) < 1e-8
    return dict(pv=present, terminal=terminal, payouts=payouts, terminal_weight=pv_terminal / present,
                year5_reserve=accumulated, year1_profit=annual[0][0]*case["margin"][0],
                year5_profit=revenue*case["margin"][-1], growth_capital_year2_to_5=sum(
                    max(annual[y][0]-annual[y-1][0], 0)*case["capital_per_new_sale"] for y in range(1,5)))


def run(inputs):
    f, a = inputs["facts"], inputs["assumptions"]
    revenue = f["fy_revenue"] - f["prior_h1_revenue"] + f["h1_revenue"]
    fx = f["interim_dividend_rmb"] / f["interim_dividend_hkd"]
    shares = f["issued_shares"] + f["october_options"] - f["november_options_exercised"]
    cash = (f["cash"] + f["time_deposits"] + f["short_financial_assets"] * a["short_financial_realization"]
            - f["financial_debt"] - a["liquidity_buffer"] - f["post_september_buyback_hkd"] * fx)
    scale = fx * shares
    cases = {name: project(revenue, cash, scale, a[name]) for name in ("base","structural_bear","cyclical_bear","bull")}
    for name, rate in zip(("base_high","base_low"), a["base_discount_band"], strict=True):
        cases[name] = project(revenue, cash, scale, dict(a["base"], discount=rate))
    order = ["structural_bear","cyclical_bear","base_low","base_high","bull"]
    values = [round(cases[name]["pv"], 2) for name in order]
    assert values == sorted(values) and values[0] > 0
    base = cases["base"]
    costs = ("annual_tax_paid","annual_interest_paid","annual_capex","annual_lease_principal","annual_share_compensation","annual_minority_profit")
    observed = [pre - sum(f[key][y] for key in costs) for y,pre in enumerate(f["annual_cash_before_working_capital"])]
    normalized = sum(observed) / len(observed)
    check = [(cash + normalized / cap_rate) / scale for cap_rate in reversed(a["cash_power_discount_band"])]
    sensitivities = {}
    for key, alt in {
            "terminal_growth_zero": dict(a["base"],terminal_growth=0.0),
            "margin_minus_one_point": dict(a["base"],margin=[v-0.01 for v in a["base"]["margin"]])}.items():
        sensitivities[key] = round(project(revenue,cash,scale,alt)["pv"],2)
    return {"symbol":"HK:03998","report_period":PERIOD,"value_range":{"low":values[2],"high":values[3],"currency":"HKD"},
            "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD","model_as_of":AS_OF,
                            "base_case_distributions_per_share":[round(x,4) for x in base["payouts"]],
                            "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(cases["base_low"]["terminal"],2),"high":round(cases["base_high"]["terminal"],2)}}},
            "scenarios":{"currency":"HKD",**dict(zip(order,values,strict=True)),
                         "horizon_note":"未来五年的直营售罄、渠道库存及门店费用共同决定收入与现金利润率，各情景同步调整资本占用、实际派息和折现率；金额为资料截止日每股港元。"},
            "normalized_cash_power_cross_check":{"annual_cny_bn":observed,"value_hkd":[round(v,2) for v in check]},
            "bridge":{"ttm_revenue_cny_bn":revenue,"opening_excess_cny_bn":cash,"diluted_shares_bn":shares,"cny_per_hkd":fx},
            "base_diagnostics":{k:round(v,4) for k,v in base.items() if k!="payouts"},"sensitivities_hkd":sensitivities}


if __name__ == "__main__":
    flat = dict(growth=[0]*5,margin=[0.1]*5,net_maintenance=0,capital_per_new_sale=0,payout=1,discount=0.1,terminal_growth=0)
    assert abs(project(100,0,1,flat)["pv"] - 100) < 1e-8  # 年付10，永续折现10%
    inputs = json.loads((HERE/f"{PERIOD}-input.json").read_text())
    (HERE/f"{PERIOD}-output.json").write_text(json.dumps(run(inputs),indent=2,ensure_ascii=False)+"\n")
