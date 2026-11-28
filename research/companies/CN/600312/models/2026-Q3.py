"""在本文件目录保留同周期 input.json，直接运行即可复算。"""
import json
from math import isclose
from pathlib import Path

folder = Path(__file__).resolve().parent
data = json.loads((folder / "2026-Q3-input.json").read_text())
facts = data["facts"]
shares = facts["shares"]


def cash_path(plan, opening):
    """归母经营净利、净投入、股利与留存的逐年资金守恒。"""
    cash = opening
    earnings, dividends = [], []
    for sales, margin, fixed, working in zip(
        plan["revenue"], plan["margin"], plan["net_fixed_rd"], plan["working"], strict=True
    ):
        income = sales * margin
        available = cash + income - fixed - working
        assert available >= 0
        dividend = min(income * plan["payout"], available)
        cash = available - dividend
        earnings.append(income)
        dividends.append(dividend)
    assert isclose(opening + sum(earnings) - sum(plan["net_fixed_rd"]) - sum(plan["working"]), sum(dividends) + cash)
    return earnings, dividends, cash


def discounted(dividends, terminal, rate, count):
    return (sum(d / (1 + rate) ** i for i, d in enumerate(dividends, 1)) +
            terminal / (1 + rate) ** len(dividends)) / count


assert discounted([2], 9, .10, 2) == 5
example = dict(revenue=[10], margin=[.5], net_fixed_rd=[2], working=[1], payout=.8)
assert cash_path(example, 0) == ([5.0], [2.0], 0.0)
net_cash = facts["cash_equivalents"] - facts["interim_dividend_paid"] - facts["bank_debt"] - facts["lease_and_current_debt"]
attribution = facts["parent_equity"] / (facts["parent_equity"] + facts["minority_equity"])
profiles = {}
for label, plan in data["paths"].items():
    opening = max(net_cash - plan["cash_reserve"], 0) * attribution
    earnings, dividends, cash = cash_path(plan, opening)
    terminal = [earnings[-1] * m + cash for m in plan["multiples"]]
    values = [discounted(dividends, t, plan["rate"], shares) for t in terminal]
    new_capital = sum(plan["net_fixed_rd"][1:]) + sum(plan["working"][1:])
    profiles[label] = {
        "opening_parent_excess": round(opening, 3), "y5_earnings": round(earnings[-1], 3),
        "y5_excess": round(cash, 3), "end_values_per_share": [round(t / shares, 4) for t in terminal],
        "dividends_per_share": [round(d / shares, 4) for d in dividends],
        "value": [round(v, 2) for v in values],
        "terminal_pv_weight": [round(t / (1 + plan["rate"]) ** 5 / shares / v, 4) for t, v in zip(terminal, values)],
        "incremental_return_y1_to_y5": round((earnings[-1] - earnings[0]) / new_capital, 4)
    }
    if label == "base":
        crosscheck = []
        for steady in data["steady_checks"]:
            g = steady["growth"]
            distribution = earnings[-1] * (1 + g) * (1 - g / steady["incremental_return"])
            exit_value = distribution / (steady["required_return"] - g) + cash
            crosscheck.append(round(discounted(dividends, exit_value, plan["rate"], shares), 2))
        sensitivity = {}
        for change, bucket in [(.01, "plus_1pt_margin"), (-.01, "minus_1pt_margin")]:
            shifted = dict(plan, margin=[m + change for m in plan["margin"]])
            e, d, c = cash_path(shifted, opening)
            sensitivity[bucket] = round(discounted(d, e[-1] * 13 + c, plan["rate"], shares), 2)

base = profiles["base"]
low, high = base["value"]
scenarios = {
    "currency": "CNY", "structural_bear": profiles["structural_bear"]["value"][0],
    "cyclical_bear": profiles["cyclical_bear"]["value"][0], "base_low": low,
    "base_high": high, "bull": profiles["bull"]["value"][0],
    "horizon_note": "五年末按各路径归母经营盈利资本化并加入尚存的超额现金；结构受损假定重复中标下滑、现金结算负担加重，周期偏弱假定验收推后，乐观情景要求新厂提高利用率与利润率。"
}
anchors = [scenarios[x] for x in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")]
assert anchors == sorted(anchors) and min(anchors) >= 0
result = {
    "symbol": data["symbol"], "report_period": data["report_period"],
    "value_range": dict(currency="CNY", low=low, high=high), "scenarios": scenarios,
    "return_model": {
        "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
        "model_as_of": data["as_of"], "base_case_distributions_per_share": base["dividends_per_share"],
        "base_case_terminal_equity_value_range_per_share": {"year_5": dict(zip(("low", "high"), base["end_values_per_share"]))}
    },
    "post_distribution_net_cash_before_operating_reserve": round(net_cash, 3),
    "paths": profiles, "steady_fcfe_crosscheck": crosscheck, "sensitivity": sensitivity
}
(folder / "2026-Q3-output.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
