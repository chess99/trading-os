"""申洲国际。运行 python 2026-H1.py，以同目录输入重算港元每股结果。"""
import json
from math import isclose
from pathlib import Path

directory = Path(__file__).resolve().parent
inputs = json.loads((directory / "2026-H1-input.json").read_text())
facts = inputs["facts"]
policy = inputs["policy"]
sales_start = facts["sales_2025"] - facts["sales_2025_h1"] + facts["sales_2026_h1"]
diluted_shares = facts["issued"] - facts["treasury"] + facts["potential_dilution"]
unit = diluted_shares / 1e9 * facts["cny_per_hkd"]
financial_net = facts["deposit_assets"] - facts["borrowings"] - facts["leases"]
cash_start = financial_net - policy["operating_cash"] - facts["interim_dividend"]
capital_start = facts["equity"] - financial_net + policy["operating_cash"]
headroom = facts["parent_reserves_2025"] - facts["final_paid"] - facts["interim_dividend"]


def discounted_value(dividends, terminal, rate):
    return sum(cash / (1 + rate) ** t for t, cash in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def run_case(case):
    path = inputs["paths"][case["path"]]
    sales, cash, capital, room = sales_start, cash_start, capital_start, headroom
    payouts, annual = [], []
    for growth, margin, extra in zip(path["growth"], path["ebit_margin"], path["extra_fixed"], strict=True):
        sales_gain = sales * growth
        sales += sales_gain
        profit = sales * margin * (1 - policy["tax"])
        fixed = extra + max(sales_gain, 0) * path["fixed_per_sale"]
        working = sales_gain * path["working_per_sale"]
        if sales_gain < 0:
            working *= path["wc_release"]
        reinvest = fixed + working
        capital += reinvest
        cash_earned = profit + cash * policy["nominal_cash_yield_after_tax"] - reinvest
        room += profit * path["upstream"]
        dividend = min(profit * path["payout"], room, max(0, cash + cash_earned))
        cash_end = cash + cash_earned - dividend
        assert isclose(cash_end + dividend + reinvest, cash * (1 + policy["nominal_cash_yield_after_tax"]) + profit)
        room -= dividend
        assert min(room, cash_end) >= -1e-9
        cash = cash_end
        payouts.append(dividend)
        annual.append(dict(sales=sales, profit=profit, gross_capex=policy["annual_replacement"] + fixed,
                           new_working_capital=working, capital=capital, cash=cash, dividend=dividend))
    # 承诺支出计入第一年购建预算，营运现金在经营资本内。
    assert annual[0]["gross_capex"] >= facts["committed_capex"]
    rate, growth, roic = case["discount"], case["growth"], case["incremental_return"]
    assert rate > growth and roic > growth
    terminal_operating = profit * (1 + growth) * (1 - growth / roic) / (rate - growth)
    terminal = terminal_operating + cash
    value = discounted_value(payouts, terminal, rate)
    return dict(value=value / unit, terminal=terminal / unit, dividends=[p / unit for p in payouts],
                terminal_share=terminal / (1 + rate) ** 5 / value, annual=annual)


assert isclose(discounted_value([11, 12.1], 121, 0.1), 120)
assert isclose(capital_start + cash_start, facts["equity"] - facts["interim_dividend"])
results = {name: run_case(case) for name, case in inputs["cases"].items()}
anchors = {name: round(row["value"], 2) for name, row in results.items()}
assert list(anchors.values()) == sorted(anchors.values())
lo, hi = results["base_low"], results["base_high"]
assert lo["dividends"] == hi["dividends"]
alternative = inputs["asset_check"]
asset_values = [(capital_start * (ret - growth) / (rate - growth) + cash_start) / unit
                for ret, rate, growth in zip(alternative["normalized_operating_return"], alternative["discount"], alternative["steady_growth"], strict=True)]
year1, year5 = lo["annual"][0], lo["annual"][-1]
output = {
    "symbol": inputs["symbol"], "report_period": inputs["report_period"],
    "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "HKD"},
    "scenarios": anchors,
    "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
                     "model_as_of": inputs["as_of"], "base_case_distributions_per_share": [round(p, 4) for p in lo["dividends"]],
                     "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(lo["terminal"], 4), "high": round(hi["terminal"], 4)}}},
    "asset_check_hkd": [round(v, 2) for v in asset_values],
    "terminal_pv_weight": [round(res["terminal_share"], 4) for res in (lo, hi)],
    "cash_start_cny_bn": round(cash_start, 4), "capital_start_cny_bn": round(capital_start, 4),
    "incremental_return_y1_to_y5": round((year5["profit"] - year1["profit"]) / (year5["capital"] - year1["capital"]), 4),
    "base_annual_cny_bn": [{k: round(v, 4) for k, v in year.items()} for year in lo["annual"]],
    "sensitivity_ebit_1pct": None
}
# 敏感性沿用正式函数，五个年度同时平移 1 个百分点，资本预算沿用基准。
base = inputs["paths"]["base"]
base["ebit_margin"] = [m - 0.01 for m in base["ebit_margin"]]
stressed = [run_case(inputs["cases"][name])["value"] for name in ("base_low", "base_high")]
output["sensitivity_ebit_1pct"] = [round(v, 2) for v in stressed]
(directory / "2026-H1-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
